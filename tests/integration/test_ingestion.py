import subprocess
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.config import get_settings
from app.database import Base
from app.models import IngestionRun, KnowledgeChunk, KnowledgeDocument
from app.retrieval.indexing import ingest_repository

AS_OF = date(2026, 11, 28)


def git(repository, *arguments):
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def write_revision(
    repository,
    *,
    version="1.0.0",
    effective="2026-11-28",
    status="active",
    body="Original policy.",
):
    path = repository / "data/knowledge_base/example.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "document_id: TF-TST-001\n"
        f'version: "{version}"\n'
        "title: Indexing example\n"
        f'effective_from: "{effective}"\n'
        f"status: {status}\n"
        "owner: Support\n"
        "source_path: data/knowledge_base/example.md\n"
        "---\n"
        f"# Example\n\n{body}\n",
        encoding="utf-8",
    )
    git(repository, "add", ".")
    git(repository, "commit", "-m", f"Write policy {version}")


@pytest.fixture
def repository(tmp_path):
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.name", "ResolveAI Tests")
    git(tmp_path, "config", "user.email", "tests@example.com")
    git(tmp_path, "config", "commit.gpgsign", "false")
    write_revision(tmp_path)
    return tmp_path


@pytest.fixture
def database_engine():
    url = get_settings().database_url.set(database="resolve_ai_test")
    engine = create_engine(url)
    schema = f"ingestion_test_{uuid4().hex}"
    test_engine = engine.execution_options(schema_translate_map={None: schema})
    created = False

    try:
        with engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        created = True

        Base.metadata.create_all(test_engine)
        yield test_engine
    finally:
        try:
            if created:
                with engine.begin() as connection:
                    connection.execute(DropSchema(schema, cascade=True))
        finally:
            engine.dispose()


def ingest(repository, database_engine):
    return ingest_repository(
        repository,
        database_engine,
        as_of=AS_OF,
    )


def active_ids(database_engine):
    with Session(database_engine) as session:
        return set(
            session.scalars(
                select(KnowledgeChunk.chunk_id).where(
                    KnowledgeChunk.is_active.is_(True)
                )
            )
        )


def count_records(database_engine, model):
    with Session(database_engine) as session:
        return session.scalar(select(func.count()).select_from(model))


def test_repeated_ingestion_reuses_chunks(database_engine, repository):
    first = ingest(repository, database_engine)
    initial_ids = active_ids(database_engine)
    second = ingest(repository, database_engine)

    assert first["status"] == "completed"
    assert first["created_chunks"] == 1
    assert second["status"] == "completed"
    assert second["created_chunks"] == 0
    assert second["reused_chunks"] == 1
    assert active_ids(database_engine) == initial_ids
    assert count_records(database_engine, KnowledgeDocument) == 1
    assert count_records(database_engine, KnowledgeChunk) == 1
    assert count_records(database_engine, IngestionRun) == 2
    assert first["ingestion_run_id"] != second["ingestion_run_id"]


def test_new_version_retires_previous_chunks(database_engine, repository):
    ingest(repository, database_engine)
    old_ids = active_ids(database_engine)

    write_revision(repository, version="1.1.0", body="Updated policy.")
    result = ingest(repository, database_engine)
    new_ids = active_ids(database_engine)

    assert result["status"] == "completed"
    assert len(new_ids) == 1
    assert old_ids.isdisjoint(new_ids)
    assert count_records(database_engine, KnowledgeDocument) == 2
    assert count_records(database_engine, KnowledgeChunk) == 2

    with Session(database_engine) as session:
        old_chunk = session.get(KnowledgeChunk, next(iter(old_ids)))
        assert old_chunk.is_active is False
        assert "Original policy." in old_chunk.chunk_text


def test_changed_content_requires_new_version(database_engine, repository):
    ingest(repository, database_engine)
    initial_ids = active_ids(database_engine)

    write_revision(repository, body="Changed without a version bump.")
    result = ingest(repository, database_engine)

    assert result["status"] == "failed"
    assert result["published"] is False
    assert "without a version change" in result["error"]
    assert active_ids(database_engine) == initial_ids
    assert count_records(database_engine, KnowledgeDocument) == 1

    with Session(database_engine) as session:
        statuses = list(session.scalars(select(IngestionRun.status)))
        assert sorted(statuses) == ["completed", "failed"]


def test_chunking_failure_rolls_back_new_revision(database_engine, repository):
    ingest(repository, database_engine)
    initial_ids = active_ids(database_engine)

    write_revision(repository, version="1.1.0", body="x" * 7000)
    result = ingest(repository, database_engine)

    assert result["status"] == "failed"
    assert result["failed"][0]["stage"] == "chunk"
    assert active_ids(database_engine) == initial_ids
    assert count_records(database_engine, KnowledgeDocument) == 1
    assert count_records(database_engine, KnowledgeChunk) == 1


def test_empty_selection_keeps_previous_index(database_engine, repository):
    ingest(repository, database_engine)
    initial_ids = active_ids(database_engine)

    write_revision(
        repository,
        version="2.0.0",
        effective="2026-12-01",
        body="Future policy.",
    )
    result = ingest(repository, database_engine)

    assert result["status"] == "failed"
    assert result["excluded"][0]["reason"] == "future_effective_date"
    assert active_ids(database_engine) == initial_ids


def test_unrelated_commit_preserves_ids_and_updates_provenance(
    database_engine, repository
):
    first = ingest(repository, database_engine)
    initial_ids = active_ids(database_engine)

    (repository / "notes.txt").write_text("Unrelated change\n", encoding="utf-8")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "Add unrelated notes")

    second = ingest(repository, database_engine)

    assert second["status"] == "completed"
    assert second["created_chunks"] == 0
    assert second["reused_chunks"] == 1
    assert first["source_commit"] != second["source_commit"]
    assert active_ids(database_engine) == initial_ids

    with Session(database_engine) as session:
        chunk = session.get(KnowledgeChunk, next(iter(initial_ids)))
        assert chunk.chunk_metadata["source_commit"] == second["source_commit"]
        assert str(chunk.last_ingestion_run_id) == second["ingestion_run_id"]

        runs = list(session.scalars(select(IngestionRun)))
        assert {run.source_commit for run in runs} == {
            first["source_commit"],
            second["source_commit"],
        }


def test_storage_failure_preserves_active_index(database_engine, repository):
    ingest(repository, database_engine)
    initial_ids = active_ids(database_engine)

    write_revision(repository, version="1.1.0", body="New policy.")

    def fail_chunk_insert(mapper, connection, target):
        raise SQLAlchemyError("Simulated storage failure")

    event.listen(KnowledgeChunk, "before_insert", fail_chunk_insert)
    try:
        result = ingest(repository, database_engine)
    finally:
        event.remove(KnowledgeChunk, "before_insert", fail_chunk_insert)

    assert result["status"] == "failed"
    assert result["published"] is False
    assert result["failed"][0]["stage"] == "persist"
    assert active_ids(database_engine) == initial_ids
    assert count_records(database_engine, KnowledgeDocument) == 1
    assert count_records(database_engine, KnowledgeChunk) == 1

    with Session(database_engine) as session:
        statuses = list(session.scalars(select(IngestionRun.status)))
        assert sorted(statuses) == ["completed", "failed"]
