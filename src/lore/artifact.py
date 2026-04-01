"""Artifact scanning and listing."""

from pathlib import Path

from lore import frontmatter
from lore.paths import derive_group


def scan_artifacts(artifacts_dir: Path) -> list[dict]:
    """Walk artifacts_dir recursively, parse frontmatter, return artifact records.

    Returns a list of dicts with keys: id, title, summary, group, path.
    Files without valid frontmatter or missing required fields are skipped.
    Soft-deleted (.md.deleted) files are excluded.
    Results are sorted alphabetically by id.
    """
    if not artifacts_dir.exists():
        return []

    results = []
    for filepath in artifacts_dir.rglob("*.md"):
        record = frontmatter.parse_frontmatter_doc(filepath, required_fields=("id", "title", "summary"))
        if record is not None:
            record["group"] = derive_group(filepath, artifacts_dir)
            results.append(record)

    return sorted(results, key=lambda d: d["id"])


def read_artifact(artifacts_dir: Path, artifact_id: str) -> dict | None:
    """Return a full artifact record for the given ID, or None if not found.

    The returned dict has keys: id, title, summary, body.
    The body is the content below the YAML frontmatter block, with leading
    newlines stripped.
    """
    artifacts = scan_artifacts(artifacts_dir)
    for artifact in artifacts:
        if artifact["id"] == artifact_id:
            filepath = artifact["path"]
            record = frontmatter.parse_frontmatter_doc_full(filepath, required_fields=("id", "title", "summary"))
            if record is None:
                return None
            return {
                "id": record["id"],
                "title": record["title"],
                "summary": record["summary"],
                "body": record["body"],
            }
    return None
