"""Shared frontmatter parsing for markdown files with YAML front matter.

Replaces the near-identical private ``_parse_doc`` and ``_parse_artifact``
functions that previously existed separately in ``codex.py`` and
``artifact.py``.
"""

from pathlib import Path

import yaml

_REQUIRED_FIELDS = ("id", "title", "summary")


def parse_frontmatter_doc(
    filepath: Path,
    required_fields: tuple[str, ...] | None = None,
    extra_fields: tuple[str, ...] = (),
) -> dict | None:
    """Read frontmatter metadata only from a markdown file.

    Returns a record dict with keys for each field in ``required_fields`` plus
    ``path`` if all required fields are present. Returns ``None`` if required
    fields are missing, YAML is invalid, or the file has fewer than three
    ``---``-separated parts.

    When ``required_fields`` is not provided, defaults to the module-level
    ``_REQUIRED_FIELDS`` (``id``, ``title``, ``summary``) for
    backward compatibility.

    Reads the file exactly once.
    """
    effective_required = required_fields if required_fields is not None else _REQUIRED_FIELDS

    try:
        text = filepath.read_text()
        parts = text.split("---")
        if len(parts) < 3:
            return None
        frontmatter = yaml.safe_load(parts[1])
    except Exception:
        return None

    if not isinstance(frontmatter, dict):
        return None
    if any(field not in frontmatter or frontmatter[field] is None for field in effective_required):
        return None

    result = {field: str(frontmatter[field]) for field in effective_required}
    result["path"] = filepath
    for field in extra_fields:
        if field in frontmatter:
            result[field] = frontmatter[field]
    return result


def parse_frontmatter_doc_full(
    filepath: Path,
    required_fields: tuple[str, ...] | None = None,
    extra_fields: tuple[str, ...] = (),
) -> dict | None:
    """Read frontmatter metadata and document body from a markdown file.

    Returns the same dict as ``parse_frontmatter_doc`` plus a ``body`` key
    containing all content after the second ``---`` delimiter, with leading
    newlines stripped.

    Returns ``None`` under the same conditions as ``parse_frontmatter_doc``.

    Reads the file exactly once, eliminating the double-read pattern.
    """
    effective_required = required_fields if required_fields is not None else _REQUIRED_FIELDS

    try:
        text = filepath.read_text()
        parts = text.split("---", 2)
        if len(parts) < 3:
            return None
        frontmatter = yaml.safe_load(parts[1])
    except Exception:
        return None

    if not isinstance(frontmatter, dict):
        return None
    if any(field not in frontmatter or frontmatter[field] is None for field in effective_required):
        return None

    body = parts[2].lstrip("\n")

    result = {field: str(frontmatter[field]) for field in effective_required}
    result["path"] = filepath
    result["body"] = body
    for field in extra_fields:
        if field in frontmatter:
            result[field] = frontmatter[field]
    return result
