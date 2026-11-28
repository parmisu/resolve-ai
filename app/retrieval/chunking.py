import hashlib
import json
import re
from typing import Any

from app.retrieval.documents import LoadedDocument

CHUNKER_VERSION = "markdown-sections-v1"
MAX_SECTION_CHARS = 6000

HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


class ChunkingError(ValueError):
    """A document cannot be split without violating the chunking rules."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def section_boundaries(body: str) -> list[tuple[int, list[str], str]]:
    boundaries = [(0, [], "document-root")]
    hierarchy: list[tuple[int, str]] = []
    position = 0
    heading_number = 0
    fence_character = None
    fence_length = 0

    for line in body.splitlines(keepends=True):
        text = line.rstrip("\n")
        fence_match = FENCE.match(text)

        if fence_character is not None:
            if fence_match:
                marker, remainder = fence_match.groups()
                if (
                    marker[0] == fence_character
                    and len(marker) >= fence_length
                    and not remainder.strip()
                ):
                    fence_character = None
            position += len(line)
            continue

        if fence_match:
            marker, _ = fence_match.groups()
            fence_character = marker[0]
            fence_length = len(marker)
            position += len(line)
            continue

        heading_match = HEADING.match(text)
        if heading_match:
            markers, title = heading_match.groups()
            title = re.sub(r"[ \t]+#+[ \t]*$", "", title).strip()
            level = len(markers)

            while hierarchy and hierarchy[-1][0] >= level:
                hierarchy.pop()

            hierarchy.append((level, title))
            heading_number += 1
            boundaries.append(
                (
                    position,
                    [item[1] for item in hierarchy],
                    f"heading-{heading_number:04d}",
                )
            )

        position += len(line)

    if fence_character is not None:
        raise ChunkingError("Document contains an unclosed code fence.")

    return boundaries


def chunk_document(
    document: LoadedDocument,
    *,
    max_section_chars: int = MAX_SECTION_CHARS,
) -> list[dict[str, Any]]:
    if type(max_section_chars) is not int or max_section_chars < 1:
        raise ChunkingError("max_section_chars must be a positive integer.")

    config_json = canonical_json(
        {
            "strategy": "one-chunk-per-section",
            "max_section_chars": max_section_chars,
            "overlap_chars": 0,
        }
    )
    boundaries = section_boundaries(document.body)
    chunks = []
    metadata = document.metadata

    for index, (start, section_path, anchor) in enumerate(boundaries):
        end = (
            boundaries[index + 1][0]
            if index + 1 < len(boundaries)
            else len(document.body)
        )
        text = document.body[start:end]

        if not text.strip():
            continue

        if len(text) > max_section_chars:
            raise ChunkingError(
                f"{metadata.document_id}: section {anchor} exceeds "
                f"{max_section_chars} characters; no chunks were returned."
            )

        identity = {
            "metadata_schema_version": 1,
            "document_id": metadata.document_id,
            "document_version": metadata.version,
            "document_sha256": document.document_sha256,
            "normalization_version": document.normalization_version,
            "chunker_version": CHUNKER_VERSION,
            "chunker_config_json": config_json,
            "section_anchor": anchor,
            "chunk_index": len(chunks),
            "body_char_start": start,
            "body_char_end": end,
            "chunk_sha256": sha256_text(text),
        }

        chunks.append(
            {
                **identity,
                "chunk_id": sha256_text(canonical_json(identity)),
                "title": metadata.title,
                "effective_from": metadata.effective_from.isoformat(),
                "document_status": metadata.status,
                "source_path": metadata.source_path,
                "source_commit": document.source_commit,
                "section_path": section_path,
                "chunk_text": text,
            }
        )

    return chunks
