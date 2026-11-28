import hashlib

import pytest

from app.retrieval.documents import DocumentLoadError, load_document

SOURCE_PATH = "data/knowledge_base/example.md"
SOURCE_COMMIT = "a" * 40

SOURCE = """---
document_id: TF-TST-001
version: "1.0.0"
title: Example policy
effective_from: "2026-11-28"
status: active
owner: Support
source_path: data/knowledge_base/example.md
---

# Example policy

Keep this text exactly.
"""


def load(raw=SOURCE.encode("utf-8"), **overrides):
    arguments = {
        "source_path": SOURCE_PATH,
        "source_commit": SOURCE_COMMIT,
    }
    arguments.update(overrides)
    return load_document(raw, **arguments)


def test_metadata_and_body_are_loaded():
    document = load()

    assert document.metadata.document_id == "TF-TST-001"
    assert document.metadata.version == "1.0.0"
    assert document.metadata.effective_from.isoformat() == "2026-11-28"
    assert document.source_commit == SOURCE_COMMIT
    assert document.body == "\n# Example policy\n\nKeep this text exactly.\n"
    assert (
        document.document_sha256 == hashlib.sha256(SOURCE.encode("utf-8")).hexdigest()
    )


def test_normalization_preserves_body_and_hashes_original_bytes():
    raw = SOURCE.replace("\n", "\r\n").encode("utf-8")

    document = load(raw)

    assert document.body == load().body
    assert document.document_sha256 == hashlib.sha256(raw).hexdigest()
    assert document.document_sha256 != load().document_sha256


def test_duplicate_metadata_keys_are_rejected():
    raw = SOURCE.replace(
        'version: "1.0.0"',
        'version: "1.0.0"\nversion: "2.0.0"',
    ).encode("utf-8")

    with pytest.raises(DocumentLoadError, match="Duplicate metadata key"):
        load(raw)


@pytest.mark.parametrize(
    "path",
    [
        "/tmp/example.md",
        "data/knowledge_base/../example.md",
        "data/knowledge_base/README.md",
        "data/synthetic_tickets/example.md",
        "data/knowledge_base/example.txt",
    ],
)
def test_invalid_source_paths_are_rejected(path):
    with pytest.raises(DocumentLoadError):
        load(source_path=path)


def test_source_path_must_match_metadata():
    with pytest.raises(DocumentLoadError, match="does not match"):
        load(source_path="data/knowledge_base/another.md")


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('version: "1.0.0"', 'version: "01.0.0"'),
        ('version: "1.0.0"', 'version: "latest"'),
        ("status: active", "status: unknown"),
        ('effective_from: "2026-11-28"', 'effective_from: "2026-99-28"'),
        ("title: Example policy", 'title: "   "'),
    ],
)
def test_invalid_metadata_is_rejected(old, new):
    with pytest.raises(DocumentLoadError):
        load(SOURCE.replace(old, new).encode("utf-8"))


def test_missing_front_matter_is_rejected():
    with pytest.raises(DocumentLoadError, match="begin with YAML"):
        load(b"# A document without metadata")


def test_empty_body_is_rejected():
    front_matter = SOURCE.split("\n---\n", 1)[0] + "\n---\n"

    with pytest.raises(DocumentLoadError, match="body must not be empty"):
        load(front_matter.encode("utf-8"))


def test_unsafe_yaml_tag_is_rejected():
    raw = SOURCE.replace(
        "owner: Support",
        "owner: !!python/object:builtins.object {}",
    ).encode("utf-8")

    with pytest.raises(DocumentLoadError, match="Invalid or unsupported YAML"):
        load(raw)


def test_short_commit_hash_is_rejected():
    with pytest.raises(DocumentLoadError, match="full lowercase Git commit"):
        load(source_commit="abc123")
