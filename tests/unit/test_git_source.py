import subprocess

import pytest

from app.retrieval.documents import DocumentLoadError
from app.retrieval.git_source import load_git_documents

SOURCE = """---
document_id: TF-TST-001
version: "1.0.0"
title: Snapshot example
effective_from: "2026-11-28"
status: active
owner: Support
source_path: data/knowledge_base/example.md
---

# Snapshot example

Original committed content.
"""


def git(repository, *arguments):
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def repository(tmp_path):
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.name", "ResolveAI Tests")
    git(tmp_path, "config", "user.email", "tests@example.com")
    git(tmp_path, "config", "commit.gpgsign", "false")

    folder = tmp_path / "data" / "knowledge_base"
    folder.mkdir(parents=True)
    (folder / "example.md").write_text(SOURCE, encoding="utf-8")
    (folder / "README.md").write_text(
        "# Registry without document metadata\n",
        encoding="utf-8",
    )

    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "Add synthetic source")
    return tmp_path


def test_reads_committed_document_and_excludes_readme(repository):
    commit, documents = load_git_documents(repository)

    assert commit == git(repository, "rev-parse", "HEAD")
    assert len(documents) == 1
    assert documents[0].source_commit == commit
    assert documents[0].metadata.document_id == "TF-TST-001"
    assert "Original committed content." in documents[0].body


def test_uncommitted_changes_do_not_change_snapshot(repository):
    path = repository / "data/knowledge_base/example.md"
    path.write_text("Uncommitted invalid content", encoding="utf-8")

    _, documents = load_git_documents(repository)

    assert "Original committed content." in documents[0].body
    assert "Uncommitted" not in documents[0].body


def test_explicit_old_commit_remains_reproducible(repository):
    old_commit, old_documents = load_git_documents(repository)

    path = repository / "data/knowledge_base/example.md"
    updated = SOURCE.replace('"1.0.0"', '"1.1.0"').replace(
        "Original committed content.", "Updated committed content."
    )
    path.write_text(updated, encoding="utf-8")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "Update source revision")

    _, current_documents = load_git_documents(repository)
    _, repeated_documents = load_git_documents(repository, old_commit)

    assert current_documents[0].metadata.version == "1.1.0"
    assert repeated_documents == old_documents


def test_invalid_ref_is_rejected(repository):
    with pytest.raises(DocumentLoadError, match="Git snapshot"):
        load_git_documents(repository, "missing-ref")


def test_invalid_committed_document_fails_snapshot(repository):
    path = repository / "data/knowledge_base/example.md"
    path.write_text("# Missing metadata\n", encoding="utf-8")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "Add invalid source")

    with pytest.raises(DocumentLoadError):
        load_git_documents(repository)
