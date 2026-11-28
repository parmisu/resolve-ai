import hashlib
import re
from datetime import date
from pathlib import PurePosixPath
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class DocumentLoadError(ValueError):
    """A source document cannot be safely loaded."""


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str = Field(pattern=r"^TF-[A-Z]+-[0-9]{3}$")
    version: str = Field(pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
    title: str = Field(min_length=1)
    effective_from: date
    status: Literal["active", "superseded"]
    owner: str = Field(min_length=1)
    source_path: str = Field(min_length=1)


class LoadedDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    metadata: DocumentMetadata
    source_commit: str
    document_sha256: str
    body: str
    normalization_version: Literal["markdown-body-v1"] = "markdown-body-v1"


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate or non-string keys."""


def construct_unique_mapping(loader, node, deep=False):
    mapping = {}

    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)

        if not isinstance(key, str):
            raise DocumentLoadError("Metadata keys must be strings.")
        if key in mapping:
            raise DocumentLoadError(f"Duplicate metadata key: {key}")

        mapping[key] = loader.construct_object(value_node, deep=deep)

    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    construct_unique_mapping,
)


def validate_source_path(source_path: str) -> None:
    path = PurePosixPath(source_path)

    if (
        "\\" in source_path
        or path.is_absolute()
        or ".." in path.parts
        or path.as_posix() != source_path
        or path.parts[:2] != ("data", "knowledge_base")
        or path.suffix != ".md"
        or path.name.lower() == "readme.md"
    ):
        raise DocumentLoadError(
            "Source must be a Markdown document inside data/knowledge_base."
        )


def load_document(
    raw_bytes: bytes,
    *,
    source_path: str,
    source_commit: str,
) -> LoadedDocument:
    validate_source_path(source_path)

    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", source_commit):
        raise DocumentLoadError("A full lowercase Git commit hash is required.")

    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DocumentLoadError("Source must use UTF-8 encoding.") from exc

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.splitlines(keepends=True)

    if not lines or lines[0] != "---\n":
        raise DocumentLoadError("Document must begin with YAML front matter.")

    closing_index = next(
        (index for index in range(1, len(lines)) if lines[index].rstrip("\n") == "---"),
        None,
    )
    if closing_index is None:
        raise DocumentLoadError("Front matter has no closing delimiter.")

    metadata_text = "".join(lines[1:closing_index])
    body = "".join(lines[closing_index + 1 :])

    try:
        values = yaml.load(metadata_text, Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise DocumentLoadError("Invalid or unsupported YAML metadata.") from exc

    if not isinstance(values, dict):
        raise DocumentLoadError("Front matter must contain a mapping.")

    try:
        metadata = DocumentMetadata.model_validate(values)
    except ValidationError as exc:
        raise DocumentLoadError(f"Invalid document metadata: {exc}") from exc

    if metadata.source_path != source_path:
        raise DocumentLoadError("Metadata source_path does not match the source.")

    if not metadata.title.strip() or not metadata.owner.strip():
        raise DocumentLoadError("Title and owner must not be whitespace-only.")

    if not body.strip():
        raise DocumentLoadError("Document body must not be empty.")

    return LoadedDocument(
        metadata=metadata,
        source_commit=source_commit,
        document_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        body=body,
    )
