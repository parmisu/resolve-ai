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