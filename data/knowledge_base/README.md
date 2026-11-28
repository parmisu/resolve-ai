# TaskFlow Knowledge Base

All documents describe a fictional SaaS product and synthetic operations.

## Source registry

| Document ID | Version | File |
|---|---|---|
| TF-POL-001 | 1.0.0 | support-policy.md |
| TF-BIL-001 | 1.0.0 | billing-and-refunds.md |
| TF-SUB-001 | 1.0.0 | subscription-plans.md |
| TF-PRD-001 | 1.0.0 | product-guide.md |
| TF-TRB-001 | 1.0.0 | troubleshooting.md |

All initial documents are effective from 2026-11-28.

## Versioning rules

- Keep document_id stable when updating the same document.
- Increment version whenever document content changes.
- Update effective_from when a policy change takes effect.
- Preserve previous revisions in Git; do not overwrite published history.
- Record the Git commit when creating an ingestion snapshot.
- Ingest only active documents whose effective date has arrived.
- Exclude this README from retrieval.

Each indexed passage must retain document_id, version, title,
effective_from, source_path, section heading, and ingestion commit.

Citation format:

TF-SUB-001 v1.0.0 — Available plans
(data/knowledge_base/subscription-plans.md)

## Evidence rules

Use these documents for general policies and procedures.
Use authorized tools for customer-specific facts.

Historical billing questions require evidence applicable to that billing
period. Current policy alone is insufficient.

Do not silently resolve conflicting active sources. Identify the conflict
and route the case for human review.

Version metadata and citations are requirements for the later ingestion
pipeline; this task creates the source documents only.