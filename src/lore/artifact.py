"""Artifact scanning and listing.

Post-G16: every operational callable takes ``project_root: Path`` first
per amendment Section A1; subdir derivation goes through
``lore.paths.entity_location``. ``scan_artifacts`` renamed to
``list_artifacts``. ``read_artifact`` envelope gains ``filename`` + ``group``.
"""

from pathlib import Path

import yaml

from lore import frontmatter
from lore.paths import derive_group, entity_location, group_matches_filter
from lore.schemas import validate_entity
from lore.validators import (
    _validate_content_nonempty,
    validate_group,
    validate_name,
)


_REQUIRED_ARTIFACT_FIELDS = ("id", "title", "summary")


def _validate_frontmatter(data: dict) -> None:
    """Validate artifact frontmatter by delegating to ``lore.schemas.validate_entity``.

    Raises ``ValueError`` whose message contains every issue's human-readable
    text joined by newlines on any returned issue. The CLI translator is
    responsible for converting this into the user-visible error envelope.
    """
    issues = validate_entity("artifact-frontmatter", data)
    if issues:
        raise ValueError("\n".join(i.message for i in issues))


def _parse_and_validate_frontmatter(content: str) -> None:
    """Inline parse + validate of artifact frontmatter from raw markdown.

    Surfaces per-field "Missing required property 'X'." text exactly as the
    schema validator emits it. Raises ``ValueError`` on any failure BEFORE
    any disk write.
    """
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
    _validate_frontmatter(meta)


def create_artifact(
    project_root: Path,
    name: str,
    content: str,
    *,
    group: str | None = None,
) -> dict:
    """Create a new artifact markdown file under ``project_root/.lore/artifacts/``.

    Validation order:
    1. Name format (``validate_name``)
    2. Group format (``validate_group``)
    3. Content non-empty
    4. Frontmatter required fields (``id``, ``title``, ``summary``)
    5. Subtree-wide duplicate via ``rglob``
    6. Create target dir (auto-mkdir parents) and write file

    Returns ``{id, filename, group}`` per amendment B Artifact row.
    Raises ``ValueError`` on any validation failure.
    """
    name_err = validate_name(name)
    if name_err:
        raise ValueError(name_err)

    group_err = validate_group(group)
    if group_err:
        raise ValueError(group_err)

    content_err = _validate_content_nonempty(content)
    if content_err:
        raise ValueError(content_err)

    _parse_and_validate_frontmatter(content)

    artifacts_dir = entity_location(project_root, "artifact")
    if artifacts_dir.exists() and next(iter(artifacts_dir.rglob(f"{name}.md")), None) is not None:
        raise ValueError(f"artifact '{name}' already exists")

    target_dir = entity_location(project_root, "artifact", group=group)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{name}.md"
    target_path.write_text(content)

    return {
        "id": name,
        "filename": f"{name}.md",
        "group": group,
    }


def _find_artifact(project_root: Path, name: str) -> Path | None:
    """Resolve an artifact name to its file path (internal).

    Returns the Path to the artifact ``.md`` file if found, or None if not
    found. Raises ``ValueError`` immediately if ``name`` contains ``/`` or
    ``\\`` (path-traversal guard).
    """
    if "/" in name or "\\" in name:
        raise ValueError(f"Invalid artifact name: {name!r}")

    artifacts_dir = entity_location(project_root, "artifact")
    if not artifacts_dir.exists():
        return None

    direct = artifacts_dir / f"{name}.md"
    if direct.exists():
        return direct

    matches = list(artifacts_dir.rglob(f"{name}.md"))
    if matches:
        return matches[0]

    return None


def update_artifact(project_root: Path, name: str, content: str) -> dict:
    """Overwrite an existing artifact markdown file in place.

    Returns ``{"id": name, "filename": filepath.name}`` on success.
    Raises ``ValueError`` on validation failure.
    """
    if "/" in name or "\\" in name:
        raise ValueError(f"Invalid artifact name: {name!r}")

    filepath = _find_artifact(project_root, name)
    if filepath is None:
        raise ValueError(f'Artifact "{name}" not found.')

    content_err = _validate_content_nonempty(content)
    if content_err:
        raise ValueError(content_err)

    _parse_and_validate_frontmatter(content)

    filepath.write_text(content)
    return {"id": name, "filename": filepath.name, "updated_at": None}


def delete_artifact(project_root: Path, name: str) -> dict:
    """Soft-delete an artifact by renaming ``{name}.md`` to ``{name}.md.deleted``.

    Returns ``{"id": name, "deleted": True, "deleted_at": None}``
    (amendment A2). Idempotent: if the live file is absent but a
    ``.md.deleted`` sibling exists, returns the same envelope without raising.
    """
    if "/" in name or "\\" in name:
        raise ValueError(f"Invalid artifact name: {name!r}")

    artifacts_dir = entity_location(project_root, "artifact")
    filepath = _find_artifact(project_root, name)
    if filepath is None:
        if artifacts_dir.exists():
            deleted_match = next(
                iter(artifacts_dir.rglob(f"{name}.md.deleted")), None
            )
            if deleted_match is not None:
                return {"id": name, "deleted": True, "deleted_at": None}
        raise ValueError(f'Artifact "{name}" not found in .lore/artifacts/')

    deleted_path = filepath.parent / f"{name}.md.deleted"
    filepath.rename(deleted_path)
    return {"id": name, "deleted": True, "deleted_at": None}


def list_artifacts(
    project_root: Path,
    filter_groups: list[str] | None = None,
) -> list[dict]:
    """Walk ``project_root/.lore/artifacts/`` recursively and return artifact records.

    Returns a list of dicts with keys: id, title, summary, group, path.
    Files without valid frontmatter or missing required fields are skipped.
    Soft-deleted (.md.deleted) files are excluded.
    Results are sorted alphabetically by id.
    """
    artifacts_dir = entity_location(project_root, "artifact")
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


def read_artifact(project_root: Path, artifact_id: str) -> dict | None:
    """Return a full artifact record dict for the given ID, or None if not found.

    Shape (amendment B Artifact row — gains ``filename`` and ``group``):
    ``{id, title, summary, body, filename, group}``.
    """
    artifacts = list_artifacts(project_root)
    artifacts_dir = entity_location(project_root, "artifact")
    for artifact in artifacts:
        if artifact["id"] == artifact_id:
            filepath = artifact["path"]
            record = frontmatter.parse_frontmatter_doc_full(
                filepath, required_fields=("id", "title", "summary")
            )
            if record is None:
                return None
            return {
                "id": record["id"],
                "title": record["title"],
                "summary": record["summary"],
                "body": record["body"],
                "filename": Path(filepath).name,
                "group": derive_group(Path(filepath), artifacts_dir),
            }
    return None
