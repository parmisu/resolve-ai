from dataclasses import dataclass
from datetime import date

from app.retrieval.documents import DocumentLoadError, LoadedDocument


@dataclass(frozen=True)
class DocumentSelection:
    selected: tuple[LoadedDocument, ...]
    excluded: tuple[dict[str, str], ...]


def select_documents(
    documents: list[LoadedDocument],
    *,
    as_of: date,
) -> DocumentSelection:
    revisions: dict[tuple[str, str], str] = {}
    candidates: dict[str, list[LoadedDocument]] = {}
    excluded = []

    def exclude(document: LoadedDocument, reason: str) -> None:
        excluded.append(
            {
                "document_id": document.metadata.document_id,
                "document_version": document.metadata.version,
                "source_path": document.metadata.source_path,
                "document_sha256": document.document_sha256,
                "reason": reason,
            }
        )

    for document in documents:
        metadata = document.metadata
        revision = (metadata.document_id, metadata.version)

        if revision in revisions:
            if revisions[revision] != document.document_sha256:
                raise DocumentLoadError(
                    f"Conflicting content for document revision {revision}."
                )
            raise DocumentLoadError(f"Duplicate document revision {revision}.")

        revisions[revision] = document.document_sha256

        if metadata.status != "active":
            exclude(document, "superseded")
        elif metadata.effective_from > as_of:
            exclude(document, "future_effective_date")
        else:
            candidates.setdefault(metadata.document_id, []).append(document)

    selected = []

    for document_id in sorted(candidates):
        versions = sorted(
            candidates[document_id],
            key=lambda document: tuple(
                int(part) for part in document.metadata.version.split(".")
            ),
            reverse=True,
        )
        selected.append(versions[0])

        for document in versions[1:]:
            exclude(document, "older_applicable_version")

    excluded.sort(
        key=lambda item: (
            item["document_id"],
            item["document_version"],
            item["source_path"],
        )
    )

    return DocumentSelection(
        selected=tuple(selected),
        excluded=tuple(excluded),
    )
