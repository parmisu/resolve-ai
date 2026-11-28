import subprocess
from pathlib import Path

from app.retrieval.documents import (
    DocumentLoadError,
    LoadedDocument,
    load_document,
)


def run_git(repository: Path, *arguments: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=True,
            capture_output=True,
            timeout=30,
        )
    except FileNotFoundError as exc:
        raise DocumentLoadError("Git is not installed or available.") from exc
    except subprocess.TimeoutExpired as exc:
        raise DocumentLoadError("Reading the Git snapshot timed out.") from exc
    except subprocess.CalledProcessError as exc:
        raise DocumentLoadError(
            "Could not read the Git snapshot. Check the repository and ref."
        ) from exc

    return result.stdout


def load_git_documents(
    repository: Path,
    ref: str = "HEAD",
) -> tuple[str, list[LoadedDocument]]:
    commit = (
        run_git(
            repository,
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{ref}^{{commit}}",
        )
        .decode("ascii")
        .strip()
    )

    entries = run_git(
        repository,
        "ls-tree",
        "-r",
        "-z",
        commit,
        "--",
        "data/knowledge_base/",
    )

    documents = []
    revisions = {}

    for entry in entries.split(b"\0"):
        if not entry:
            continue

        description, raw_path = entry.split(b"\t", 1)
        mode, object_type, object_id = description.decode("ascii").split()

        try:
            source_path = raw_path.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DocumentLoadError("Source paths must use UTF-8.") from exc

        if not source_path.endswith(".md"):
            continue
        if source_path.rsplit("/", 1)[-1].lower() == "readme.md":
            continue

        if object_type != "blob" or mode not in {"100644", "100755"}:
            raise DocumentLoadError(f"Source must be a regular file: {source_path}")

        raw_bytes = run_git(repository, "cat-file", "blob", object_id)
        document = load_document(
            raw_bytes,
            source_path=source_path,
            source_commit=commit,
        )

        revision = (
            document.metadata.document_id,
            document.metadata.version,
        )
        if revision in revisions:
            raise DocumentLoadError(
                f"Duplicate document revision {revision}: "
                f"{revisions[revision]} and {source_path}"
            )

        revisions[revision] = source_path
        documents.append(document)

    if not documents:
        raise DocumentLoadError("No knowledge-base documents found in snapshot.")

    documents.sort(key=lambda item: item.metadata.source_path)
    return commit, documents
