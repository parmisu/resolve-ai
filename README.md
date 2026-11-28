# ResolveAI

An agentic AI customer support platform for a fictional SaaS company.

## Development status

Initial project structure and Python tooling are configured.
Application features are under development.

## Local setup

The initial dependency lock was generated on macOS with Python 3.11.17.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements-lock.txt
```

## Code quality

```bash
python -m pip check
python -m ruff check .
python -m ruff format --check .
```

To apply formatting:

```bash
python -m ruff format .
```

## Update the dependency lock

After changing dependencies in pyproject.toml:

```bash
python -m piptools compile --extra dev --generate-hashes --output-file requirements-lock.txt pyproject.toml
```

## Tests

Test directories are prepared. Automated tests will be added alongside implementation.

## Local database setup

Prerequisites: Python 3.11+, Docker Desktop with Docker Compose, and a
running Docker engine.

Run these commands from the repository root.

### Configure the environment

Create `.env` from `.env.example` if it does not already exist:

```bash
cp -n .env.example .env
```

Set a local development password in `.env`. Never commit this file.

The application connects to PostgreSQL at `127.0.0.1:5433`.
Docker maps this port to PostgreSQL's internal port `5432`.

### Install dependencies

With the Python virtual environment activated:

```bash
python -m pip install --require-hashes -r requirements-lock.txt
```

### Start PostgreSQL and apply migrations

```bash
docker compose up -d --wait db
python -m alembic upgrade head
python -m alembic current
python -m alembic check
```

### Load synthetic demo data

Set `APP_ENV=development` in `.env`, then run:

```bash
python -m app.seed
```

The seed creates four users, two customers, two subscriptions, and three
tickets. Repeated runs skip existing demo records without overwriting them.

All seed data is fictional. Subscription dates are fixed for reproducibility.
Seeded users are database fixtures; they do not provide a login mechanism.

### Run checks

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

### Stop PostgreSQL

```bash
docker compose stop db
```

Database data is retained in the Docker volume.

## Ticket API

Start the database, then run the API from the repository root with the
virtual environment activated:

```bash
docker compose up -d --wait db
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Interactive documentation: http://127.0.0.1:8000/docs

### Development authentication

Ticket endpoints require a Bearer token. With `APP_ENV=development`,
configure `DEV_API_TOKENS` in `.env` as a JSON mapping from a seeded user's
`auth_subject` to a unique, randomly generated token.

Generate a token locally:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Configuration structure; replace each placeholder with a different token:

```dotenv
DEV_API_TOKENS='{"synthetic:customer-alex":"REPLACE_WITH_RANDOM_TOKEN","synthetic:customer-sam":"REPLACE_WITH_ANOTHER_RANDOM_TOKEN","synthetic:support-agent":"REPLACE_WITH_ANOTHER_RANDOM_TOKEN","synthetic:administrator":"REPLACE_WITH_ANOTHER_RANDOM_TOKEN"}'
```

Restart the API after changing `.env`. In Swagger's **Authorize** dialog,
paste only the token into **Value**. Authentication may need to be repeated
after refreshing the page.

These tokens are for local development only. Never commit real tokens.
Authentication for public deployment is not yet implemented; protected
endpoints reject requests outside the development environment.

### Endpoints

| Method | Path | Behavior |
|---|---|---|
| POST | `/tickets` | Create a ticket for the authenticated customer |
| GET | `/tickets` | List accessible tickets with filters and pagination |
| GET | `/tickets/{ticket_id}` | Retrieve an accessible ticket |
| PATCH | `/tickets/{ticket_id}` | Update permitted fields using the current version |
| POST | `/tickets/{ticket_id}/close` | Allow staff to close a resolved ticket |

List filters: `status`, `category`, and `priority`.
Pagination: `limit` (1–100, default 20) and `offset` (default 0).

Customers can access only their own tickets and edit their message while
the ticket is open. Staff can change priority on tickets that are not
resolved or closed, but cannot rewrite customer messages.

Update and close requests require the current `version` from a GET
response. A stale version returns `409 Conflict`.

Only support agents and administrators can close tickets, and only from
the `resolved` state. Resolution through human review is a later milestone.

Responses currently use the public ticket schema. Staff-specific response
fields are not yet exposed.

### API tests

Create the dedicated test database once:

```bash
docker compose exec db createdb -U resolve_ai resolve_ai_test
```

If it already exists, continue with migrations:

```bash
POSTGRES_DB=resolve_ai_test python -m alembic upgrade head
python -m pytest -q
```

Integration tests require PostgreSQL to be running. They use synthetic
fixtures and test-only tokens, and roll back database changes after each
test. Uvicorn does not need to be running.

### Troubleshooting

- `401`: authorize with a valid token for an active user.
- `403`: the authenticated user cannot perform the requested action.
- `404`: the ticket does not exist or is not accessible to the customer.
- `409`: fetch the latest version and check the ticket's current state.
- `422`: check the request body, UUID, and query parameters.
- PostgreSQL connection refused: start Docker Desktop and the `db` service.

Database outages currently produce a generic `500` response. A dedicated
readiness check and graceful database-unavailable handling remain to be added.

## Knowledge-base ingestion

The ingestion pipeline loads committed Markdown documents from
`data/knowledge_base/`, validates front matter, selects applicable active
versions, and stores section-based chunks in PostgreSQL.

Prerequisites: Git, installed project dependencies, a running database,
and migrations applied.

```bash
docker compose up -d --wait db
python -m alembic upgrade head
python -m app.retrieval.ingest --ref HEAD --as-of 2026-11-28
```

`--ref` accepts a Git branch, tag, or full commit hash.
`--as-of` selects the policy applicability date; if omitted, UTC today is used.

The source snapshot is resolved to a full commit hash before loading.
Uncommitted document edits are not ingested. Commit document changes first
and increment the document version whenever its content changes.

### Chunking and provenance

- Each ATX-heading section becomes one chunk, with no overlap.
- Tables and fenced code blocks remain intact within a section.
- Sections exceeding 6,000 Unicode characters fail ingestion.
- Chunk IDs are deterministic and exclude run IDs and timestamps.
- Metadata retains document identity, version, section, source commit,
  content hashes, and exact character offsets.

See [the metadata contract](docs/retrieval-metadata.md).

### Repeated runs and failures

Re-ingesting identical sources with the same chunking configuration reuses
existing chunk records. Each execution creates a separate ingestion-run
record and updates the reused chunks' latest ingestion metadata.

A successful run publishes a complete active snapshot. Previously active
chunks absent from that snapshot become inactive; their records remain
available for provenance.

Conflicting content under an existing document ID and version is rejected.
An empty eligible selection is rejected to prevent accidental empty-index
publication.

Document and chunk changes are transactional. Processing or storage
failures roll back those changes and preserve the previous active index.
A failed-run report is retained when the database transaction remains usable.

Invalid Git references and unavailable database connections may prevent
creation of a run record. The CLI exits with a nonzero status on failure.

### Validation

Run the complete test suite with PostgreSQL available:

```bash
POSTGRES_DB=resolve_ai_test python -m alembic upgrade head
python -m pytest -q
```

Tests cover document validation, immutable Git snapshots, deterministic
chunking, version selection, repeated indexing, revision replacement,
and rollback after chunking or storage failures.

### Current limitations

This pipeline stores text and metadata; it does not generate embeddings
or perform semantic retrieval.

The initial parser supports ATX headings and fenced code blocks rather
than full CommonMark. Published versions use numeric MAJOR.MINOR.PATCH;
prerelease versions are not supported.

Ingestion replaces the entire TaskFlow knowledge-base snapshot and must
not be used as a partial-document update operation.