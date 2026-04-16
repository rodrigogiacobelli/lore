"""Artifact scanning and listing."""

from pathlib import Path

import click
import yaml

from lore import frontmatter
from lore.paths import derive_group, group_matches_filter
from lore.schemas import validate_entity
from lore.validators import validate_group, validate_name


_REQUIRED_ARTIFACT_FIELDS = ("id", "title", "summary")


def _validate_frontmatter(data: dict) -> None:
    """Validate artifact frontmatter by delegating to ``lore.schemas.validate_entity``.

    Raises ``click.ClickException`` whose ``.message`` contains every issue's
    human-readable text on any returned issue.
    """
    issues = validate_entity("artifact-frontmatter", data)
    if issues:
        raise click.ClickException("\n".join(i.message for i in issues))


def create_artifact(
    artifacts_dir: Path,
    name: str,
    content: str,
    *,
    group: str | None = None,
) -> dict:
    """Create a new artifact markdown file under ``artifacts_dir``.

    Validation order:
    1. Name format (``validate_name``)
    2. Group format (``validate_group``)
    3. Frontmatter required fields (``id``, ``title``, ``summary``)
    4. Subtree-wide duplicate via ``rglob``
    5. Create target dir (auto-mkdir parents) and write file

    Returns a dict with keys: ``id``, ``group``, ``filename``, ``path``.
    Raises ``ValueError`` on any validation failure.
    """
    name_err = validate_name(name)
    if name_err:
        raise ValueError(name_err)

    group_err = validate_group(group)
    if group_err:
        raise ValueError(group_err)

    # Strict frontmatter validation
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError(
            "Artifact content missing frontmatter block (id, title, summary required)"
        )
    try:
        meta = yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid frontmatter YAML: {e}") from e
    if not isinstance(meta, dict):
        raise ValueError("Frontmatter must be a YAML mapping")
    for field in _REQUIRED_ARTIFACT_FIELDS:
        if field not in meta or meta[field] is None:
            raise ValueError(f"Missing required frontmatter field: {field}")

    if next(iter(artifacts_dir.rglob(f"{name}.md")), None) is not None:
        raise ValueError(f"artifact '{name}' already exists")

    target_dir = artifacts_dir if group is None else artifacts_dir / Path(group)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{name}.md"
    target_path.write_text(content)

    return {
        "id": name,
        "group": group,
        "filename": f"{name}.md",
        "path": str(target_path),
    }


def scan_artifacts(artifacts_dir: Path, filter_groups: list[str] | None = None) -> list[dict]:
    """Walk artifacts_dir recursively, parse frontmatter, return artifact records.

    Returns a list of dicts with keys: id, title, summary, group, path.
    Files without valid frontmatter or missing required fields are skipped.
    Soft-deleted (.md.deleted) files are excluded.
    Results are sorted alphabetically by id.

    If filter_groups is a non-empty list, only artifacts whose group is in
    filter_groups or whose group is root-level (empty string) are returned.
    If filter_groups is None or an empty list, all artifacts are returned.
    """
    if not artifacts_dir.exists():
        return []

    results = []
    for filepath in artifacts_dir.rglob("*.md"):
        record = frontmatter.parse_frontmatter_doc(filepath, required_fields=("id", "title", "summary"))
        if record is not None:
            record["group"] = derive_group(filepath, artifacts_dir)
            results.append(record)

    if filter_groups:
        results = [r for r in results if group_matches_filter(r["group"], filter_groups)]

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
