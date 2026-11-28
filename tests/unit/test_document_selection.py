from datetime import date

import pytest

from app.retrieval.documents import DocumentLoadError, load_document
from app.retrieval.selection import select_documents

AS_OF = date(2026, 11, 28)


def document(
    version="1.0.0",
    effective="2026-11-28",
    status="active",
    body="Example content.",
):
    source = (
        "---\n"
        "document_id: TF-TST-001\n"
        f'version: "{version}"\n'
        "title: Selection example\n"
        f'effective_from: "{effective}"\n'
        f"status: {status}\n"
        "owner: Support\n"
        "source_path: data/knowledge_base/example.md\n"
        "---\n"
        f"# Example\n\n{body}\n"
    )
    return load_document(
        source.encode("utf-8"),
        source_path="data/knowledge_base/example.md",
        source_commit="a" * 40,
    )


def test_effective_date_is_inclusive():
    result = select_documents([document()], as_of=AS_OF)

    assert len(result.selected) == 1
    assert result.excluded == ()


def test_version_order_is_numeric():
    result = select_documents(
        [document(version="1.9.0"), document(version="1.10.0")],
        as_of=AS_OF,
    )

    assert result.selected[0].metadata.version == "1.10.0"
    assert result.excluded[0]["reason"] == "older_applicable_version"


def test_future_version_does_not_replace_current_version():
    result = select_documents(
        [
            document(version="1.0.0"),
            document(version="2.0.0", effective="2026-12-01"),
        ],
        as_of=AS_OF,
    )

    assert result.selected[0].metadata.version == "1.0.0"
    assert result.excluded[0]["reason"] == "future_effective_date"


def test_superseded_document_is_excluded():
    result = select_documents(
        [document(status="superseded")],
        as_of=AS_OF,
    )

    assert result.selected == ()
    assert result.excluded[0]["reason"] == "superseded"


def test_conflicting_content_for_same_version_is_rejected():
    with pytest.raises(DocumentLoadError, match="Conflicting content"):
        select_documents(
            [document(body="First policy."), document(body="Different policy.")],
            as_of=AS_OF,
        )


def test_duplicate_revision_is_rejected():
    source = document()

    with pytest.raises(DocumentLoadError, match="Duplicate document revision"):
        select_documents([source, source], as_of=AS_OF)


def test_selection_is_independent_of_input_order():
    sources = [document(version="1.0.0"), document(version="1.1.0")]

    assert select_documents(sources, as_of=AS_OF) == select_documents(
        list(reversed(sources)),
        as_of=AS_OF,
    )
