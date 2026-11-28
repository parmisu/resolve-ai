import argparse
import json
import sys
from datetime import date
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from app.database import engine
from app.retrieval.indexing import ingest_repository


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Index a committed TaskFlow knowledge-base snapshot."
    )
    parser.add_argument(
        "--repository",
        type=Path,
        default=Path.cwd(),
        help="Repository root; defaults to the current directory.",
    )
    parser.add_argument(
        "--ref",
        default="HEAD",
        help="Git branch, tag, or commit to ingest.",
    )
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=None,
        help="Policy selection date in YYYY-MM-DD format; defaults to UTC today.",
    )
    arguments = parser.parse_args()

    try:
        result = ingest_repository(
            arguments.repository.resolve(),
            engine,
            ref=arguments.ref,
            as_of=arguments.as_of,
        )
    except SQLAlchemyError:
        print(
            "Ingestion could not complete because of a database error. "
            "Check PostgreSQL availability and migrations.",
            file=sys.stderr,
        )
        return 1
    except ValueError as exc:
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()

    summary = {
        "ingestion_run_id": result["ingestion_run_id"],
        "status": result["status"],
        "source_commit": result["source_commit"],
        "as_of": result["as_of"],
        "accepted_documents": len(result["accepted"]),
        "excluded_documents": len(result["excluded"]),
        "created_chunks": result["created_chunks"],
        "reused_chunks": result["reused_chunks"],
        "published": result["published"],
        "error": result["error"],
    }
    print(json.dumps(summary, indent=2))
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
