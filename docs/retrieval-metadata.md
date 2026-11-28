# Retrieval Metadata Contract

Status: specification
Metadata schema version: 1

This contract defines the metadata required when TaskFlow documents are
ingested and split into retrievable chunks. The ingestion implementation
will enforce this contract in a later task.

## Document identity

A document ID identifies one logical document across revisions.

Example: TF-SUB-001 identifies the subscription policy, while version
1.0.0 identifies a specific published revision of that document.

The pair (document_id, document_version) must identify immutable content.
If the content changes, its document version must change.

## Required chunk fields

| Field | Type | Meaning |
|---|---|---|
| metadata_schema_version | integer | Metadata contract version; initially 1 |
| document_id | string | Stable ID from document front matter |
| title | string | Document title from front matter |
| document_version | string | Published version from the front-matter `version` field |
| effective_from | date | Date when the document becomes applicable |
| document_status | string | Source status; only active documents are indexed |
| source_path | string | Repository-relative POSIX path of the source file |
| source_commit | string | Full Git commit hash identifying the source snapshot |
| document_sha256 | string | SHA-256 of the original source file bytes |
| section_path | array of strings | Heading hierarchy containing this chunk |
| section_anchor | string | Unique heading identifier within this revision |
| chunk_id | string | Deterministic identifier for this chunk |
| chunk_index | integer | Zero-based position within the document |
| chunk_text | string | Exact text indexed for retrieval |
| chunk_sha256 | string | SHA-256 of chunk_text encoded as UTF-8 |
| body_char_start | integer | Inclusive character offset in normalized document body |
| body_char_end | integer | Exclusive character offset in normalized document body |
| normalization_version | string | Version of the body normalization rules |
| chunker_version | string | Version of the chunking implementation |
| chunker_config_json | string | Canonical JSON containing chunking parameters |
| ingestion_run_id | UUID string | Identifier shared by chunks processed in one ingestion run |
| ingested_at | UTC datetime | Timestamp when the chunk record was persisted |

Repository-relative paths must never contain local absolute paths,
credentials, or parent-directory traversal.

## Source and citation

The source path is a file location, not an external web URL.

An immutable GitHub source URL can be constructed as:

https://github.com/parmisu/resolve-ai/blob/{source_commit}/{source_path}

Customer-facing citations should contain:

- Document title.
- Document ID and version.
- Section heading.
- A link to the immutable source revision.

Example citation label:

TaskFlow Subscription Plans — Available plans
[TF-SUB-001 v1.0.0]

The application constructs citations from stored metadata.
The LLM must not invent source IDs, versions, or URLs.

## Normalization and offsets

Normalization version `markdown-body-v1`:

1. Decode the source file as UTF-8.
2. Normalize CRLF and CR line endings to LF.
3. Remove the YAML front matter and its delimiters.
4. Preserve the remaining Markdown body, including whitespace and headings.

Offsets count Unicode characters in this normalized body, not UTF-8 bytes.

The following invariant must hold:

```python
chunk_text == normalized_body[body_char_start:body_char_end]
```

Do not prepend generated headings or summaries to chunk_text.
Pass heading context separately through section_path.

Source front matter is metadata, not answer evidence.
The original file hash includes front matter.

## Sections

section_path contains the enclosing heading hierarchy, including the
document's top-level heading.

Example:

["TaskFlow Subscription Plans", "Available plans"]

section_anchor is an internal provenance identifier, not a GitHub URL
fragment. Assign headings sequential identifiers such as `heading-0001`
in document order. Duplicate heading titles receive different identifiers.

Use `document-root` and an empty section_path for content before the first
heading.

Chunks must not cross section boundaries. Overlap is allowed within a
section, with offsets recorded separately for each chunk.

A section may produce multiple chunks. Tables should remain intact where
possible; oversized tables require an explicitly documented splitting rule.

## Deterministic chunk identity

Compute chunk_id as the SHA-256 of a canonical JSON object containing:

- metadata_schema_version
- document_id
- document_version
- document_sha256
- normalization_version
- chunker_version
- chunker_config_json
- section_anchor
- chunk_index
- body_char_start
- body_char_end
- chunk_sha256

Canonical JSON uses sorted keys, UTF-8 encoding, no insignificant
whitespace, and no NaN values.

Do not include ingestion timestamps, run IDs, or source_commit in the
chunk ID. Re-ingesting identical content with identical chunking settings
must preserve chunk IDs even if an unrelated repository commit changes.

An ingestion run records which source commit was used. Re-ingestion
updates the current record's ingestion metadata and retains run history
in an ingestion manifest.

## Ingestion manifest

Each completed run must record:

- ingestion_run_id
- source_commit
- start and completion timestamps in UTC
- normalization and chunker versions
- chunker configuration
- document IDs, versions, file hashes, and generated chunk IDs
- accepted, excluded, and failed documents with reasons

Source files must be read from the recorded Git revision.
Uncommitted local content must not be attributed to a Git commit.

A failed ingestion must not replace the previously active index with a
partial result.

## Version handling

For each document, select the newest applicable active revision using
validated semantic-version ordering.

Do not activate future-dated or superseded revisions.
Reject two different contents claiming the same document ID and version.

When a revision is replaced, retire its chunks from current-policy
retrieval. Preserve provenance for previously generated responses.

Historical questions require an explicitly selected historical revision.
Do not use current policy alone as evidence for a past billing period.

## Validation rules

Reject a chunk if:

- Required metadata is missing or invalid.
- The source document ID or version does not match its front matter.
- The recorded source snapshot cannot reproduce the document hash.
- chunk_text is empty or whitespace-only.
- Offsets are negative, reversed, out of bounds, or inconsistent with text.
- chunk_index is negative.
- The chunk hash or deterministic chunk ID does not match.
- ingested_at is missing a timezone or is not stored in UTC.
- The source path points outside the knowledge-base directory.

Exclude the knowledge-base README from ingestion.

## Retrieval storage

Store metadata with each chunk alongside its text and, later, its embedding.

PostgreSQL JSONB may store section_path and chunker configuration.
If a vector store requires scalar metadata, serialize structured values as
canonical JSON strings and decode them at the retrieval boundary.

Document metadata does not establish trust or grant permissions.
Instructions found inside retrieved text must never override application
authorization or human-review rules.

## Initial chunker implementation

`markdown-sections-v1` supports ATX headings (`#` through `######`)
and ignores heading-like text inside fenced code blocks.

Each section produces one chunk, with no overlap. Blank sections are
skipped. Tables and code blocks remain intact within their section.

The section limit is 6,000 Unicode characters, including the heading.
Oversized sections and unclosed code fences fail chunking. Oversized
tables are rejected rather than split. This is a character limit, not
an embedding-model token limit.

Setext headings and full CommonMark parsing are not supported by this
initial implementation. Source documents must use ATX headings.