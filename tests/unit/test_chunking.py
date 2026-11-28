import pytest

from app.retrieval.chunking import ChunkingError, chunk_document
from app.retrieval.documents import load_document


def document(body, commit="a" * 40):
    source = (
        "---\n"
        "document_id: TF-TST-001\n"
        'version: "1.0.0"\n'
        "title: Chunking example\n"
        'effective_from: "2026-11-28"\n'
        "status: active\n"
        "owner: Support\n"
        "source_path: data/knowledge_base/example.md\n"
        "---\n" + body
    )
    return load_document(
        source.encode("utf-8"),
        source_path="data/knowledge_base/example.md",
        source_commit=commit,
    )


def test_sections_have_exact_offsets_and_hierarchy():
    source = document(
        "# Guide\n\nIntroduction.\n\n"
        "## Billing\n\nPay monthly.\n\n"
        "### Invoices\n\nDownload invoices.\n"
    )
    chunks = chunk_document(source)

    assert len(chunks) == 3
    assert chunks[2]["section_path"] == ["Guide", "Billing", "Invoices"]
    assert [chunk["chunk_index"] for chunk in chunks] == [0, 1, 2]

    for chunk in chunks:
        start = chunk["body_char_start"]
        end = chunk["body_char_end"]
        assert chunk["chunk_text"] == source.body[start:end]


def test_repeated_chunking_preserves_identifiers():
    source = document("# Guide\n\nHello.\n")
    assert chunk_document(source) == chunk_document(source)


def test_unrelated_git_commit_does_not_change_chunk_id():
    body = "# Guide\n\nSame source content.\n"
    first = chunk_document(document(body, commit="a" * 40))
    second = chunk_document(document(body, commit="b" * 40))

    assert first[0]["chunk_id"] == second[0]["chunk_id"]
    assert first[0]["source_commit"] != second[0]["source_commit"]


def test_content_change_changes_identifier():
    first = chunk_document(document("# Guide\n\nFirst answer.\n"))
    second = chunk_document(document("# Guide\n\nDifferent answer.\n"))

    assert first[0]["chunk_id"] != second[0]["chunk_id"]


def test_duplicate_headings_have_distinct_anchors():
    chunks = chunk_document(document("## Help\n\nFirst.\n\n## Help\n\nSecond.\n"))

    assert chunks[0]["section_path"] == chunks[1]["section_path"]
    assert chunks[0]["section_anchor"] != chunks[1]["section_anchor"]
    assert chunks[0]["chunk_id"] != chunks[1]["chunk_id"]


def test_table_stays_in_one_chunk():
    table = "| Plan | Price |\n|---|---|\n| Starter | $12 |\n"
    chunks = chunk_document(
        document("# Plans\n\n" + table + "\n## Notes\n\nTaxes excluded.\n")
    )

    assert len(chunks) == 2
    assert table in chunks[0]["chunk_text"]


def test_heading_inside_code_fence_is_not_a_section():
    chunks = chunk_document(document("# Guide\n\n```text\n## Not a heading\n```\n"))

    assert len(chunks) == 1
    assert "## Not a heading" in chunks[0]["chunk_text"]


def test_unicode_offsets_count_characters():
    source = document("# راهنما\n\nسلام 🌸\n\n## Next\n\nHello.\n")
    chunks = chunk_document(source)

    for chunk in chunks:
        assert (
            chunk["chunk_text"]
            == source.body[chunk["body_char_start"] : chunk["body_char_end"]]
        )


def test_oversized_section_is_rejected():
    with pytest.raises(ChunkingError, match="exceeds"):
        chunk_document(document("# Guide\n\n" + "x" * 100), max_section_chars=50)


def test_unclosed_code_fence_is_rejected():
    with pytest.raises(ChunkingError, match="unclosed"):
        chunk_document(document("# Guide\n\n```text\nExample\n"))


def test_text_before_first_heading_has_root_provenance():
    chunks = chunk_document(document("Introduction.\n\n# Guide\n\nDetails.\n"))

    assert chunks[0]["section_anchor"] == "document-root"
    assert chunks[0]["section_path"] == []
