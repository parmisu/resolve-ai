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