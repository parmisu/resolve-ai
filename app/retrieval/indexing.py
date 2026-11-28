from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Engine, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import IngestionRun, KnowledgeChunk, KnowledgeDocument
from app.retrieval.chunking import (
    CHUNKER_VERSION,
    MAX_SECTION_CHARS,
    canonical_json,
    chunk_document,
)
from app.retrieval.documents import DocumentLoadError
from app.retrieval.git_source import load_git_documents, run_git
from app.retrieval.selection import select_documents

INDEX_LOCK_ID = 74120312


def ingest_repository(
    repository: Path,
    database_engine: Engine,
    *,
    ref: str = "HEAD",
    as_of: date | None = None,
) -> dict:
    effective_date = as_of or datetime.now(timezone.utc).date()

    # Resolve once, then read only from this immutable commit.
    commit = (
        run_git(
            repository,
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{ref}^{{commit}}",
        )
        .decode("ascii")
        .strip()
    )

    run_id = uuid4()
    started_at = datetime.now(timezone.utc)
    manifest = {
        "source_commit": commit,
        "as_of": effective_date.isoformat(),
        "normalization_version": "markdown-body-v1",
        "chunker_version": CHUNKER_VERSION,
        "chunker_config_json": canonical_json(
            {
                "strategy": "one-chunk-per-section",
                "max_section_chars": MAX_SECTION_CHARS,
                "overlap_chars": 0,
            }
        ),
        "accepted": [],
        "excluded": [],
        "failed": [],
        "created_chunks": 0,
        "reused_chunks": 0,
    }
    outcome = "completed"
    error_message = None
    stage = "load"

    with Session(database_engine) as session:
        with session.begin():
            # Serialize ingestion writers for this knowledge base.
            session.execute(
                text("SELECT pg_advisory_xact_lock(:lock_id)"),
                {"lock_id": INDEX_LOCK_ID},
            )

            run = IngestionRun(
                id=run_id,
                source_commit=commit,
                status="running",
                started_at=started_at,
                manifest={},
            )
            session.add(run)
            session.flush()

            try:
                # Roll back document/chunk changes if any step fails,
                # while keeping the run record in the outer transaction.
                with session.begin_nested():
                    _, documents = load_git_documents(repository, commit)

                    stage = "select"
                    selection = select_documents(
                        documents,
                        as_of=effective_date,
                    )
                    manifest["excluded"] = list(selection.excluded)

                    if not selection.selected:
                        raise DocumentLoadError(
                            "No eligible documents; refusing to replace "
                            "the active index with an empty snapshot."
                        )

                    stage = "validate_revisions"
                    revisions = {}

                    # Validate all source revisions, including excluded ones.
                    for document in documents:
                        metadata = document.metadata
                        revision = session.scalar(
                            select(KnowledgeDocument).where(
                                KnowledgeDocument.document_id == metadata.document_id,
                                KnowledgeDocument.document_version == metadata.version,
                            )
                        )

                        if revision is not None:
                            if revision.document_sha256 != document.document_sha256:
                                raise DocumentLoadError(
                                    f"{metadata.document_id} v{metadata.version}: "
                                    "content changed without a version change."
                                )
                        else:
                            revision = KnowledgeDocument(
                                document_id=metadata.document_id,
                                document_version=metadata.version,
                                document_sha256=document.document_sha256,
                                source_path=metadata.source_path,
                                first_source_commit=commit,
                            )
                            session.add(revision)

                        revisions[(metadata.document_id, metadata.version)] = revision

                    session.flush()

                    stage = "chunk"
                    prepared = []
                    for document in selection.selected:
                        chunks = chunk_document(document)
                        metadata = document.metadata

                        if not chunks:
                            raise DocumentLoadError(
                                f"{metadata.document_id}: no chunks generated."
                            )

                        prepared.append((document, chunks))
                        manifest["accepted"].append(
                            {
                                "document_id": metadata.document_id,
                                "document_version": metadata.version,
                                "document_sha256": document.document_sha256,
                                "source_path": metadata.source_path,
                                "chunk_ids": [chunk["chunk_id"] for chunk in chunks],
                            }
                        )

                    stage = "persist"
                    ingested_at = datetime.now(timezone.utc)

                    # Full-snapshot replacement, inside the same transaction.
                    session.execute(update(KnowledgeChunk).values(is_active=False))

                    for document, chunks in prepared:
                        revision = revisions[
                            (
                                document.metadata.document_id,
                                document.metadata.version,
                            )
                        ]

                        for chunk in chunks:
                            chunk_id = chunk["chunk_id"]
                            record = session.get(KnowledgeChunk, chunk_id)
                            chunk_metadata = {
                                key: value
                                for key, value in chunk.items()
                                if key != "chunk_text"
                            }
                            chunk_metadata.update(
                                {
                                    "ingestion_run_id": str(run_id),
                                    "ingested_at": ingested_at.isoformat(),
                                }
                            )

                            if record is None:
                                record = KnowledgeChunk(
                                    chunk_id=chunk_id,
                                    document_revision_id=revision.id,
                                    chunk_text=chunk["chunk_text"],
                                )
                                session.add(record)
                                manifest["created_chunks"] += 1
                            else:
                                if (
                                    record.chunk_text != chunk["chunk_text"]
                                    or record.document_revision_id != revision.id
                                ):
                                    raise DocumentLoadError(
                                        "Stored chunk identity conflicts "
                                        "with the generated chunk."
                                    )
                                manifest["reused_chunks"] += 1

                            record.chunk_metadata = chunk_metadata
                            record.is_active = True
                            record.last_ingestion_run_id = run_id
                            record.ingested_at = ingested_at

                    session.flush()

            except (ValueError, SQLAlchemyError) as exc:
                outcome = "failed"
                error_message = (
                    f"{stage}: database operation failed."
                    if isinstance(exc, SQLAlchemyError)
                    else f"{stage}: {exc}"
                )
                manifest["failed"] = [{"stage": stage, "reason": error_message}]
                # All writes inside the savepoint were rolled back.
                manifest["created_chunks"] = 0
                manifest["reused_chunks"] = 0

            completed_at = datetime.now(timezone.utc)
            manifest["started_at"] = started_at.isoformat()
            manifest["completed_at"] = completed_at.isoformat()
            manifest["published"] = outcome == "completed"

            run.status = outcome
            run.completed_at = completed_at
            run.error_message = error_message
            run.manifest = manifest

    return {
        "ingestion_run_id": str(run_id),
        "status": outcome,
        "error": error_message,
        **manifest,
    }
