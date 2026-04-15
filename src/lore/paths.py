"""Path helpers for locating files within a Lore project.

All functions accept a ``root`` Path (the value returned by
``find_project_root()``) and return a Path inside the ``.lore/``
directory. The magic string ``".lore"`` is centralised here and must
not appear in any other module.
"""

from pathlib import Path


def lore_dir(root: Path) -> Path:
    return root / ".lore"


def knights_dir(root: Path) -> Path:
    return root / ".lore" / "knights"


def doctrines_dir(root: Path) -> Path:
    return root / ".lore" / "doctrines"


def codex_dir(root: Path) -> Path:
    return root / ".lore" / "codex"


def artifacts_dir(root: Path) -> Path:
    return root / ".lore" / "artifacts"


def reports_dir(root: Path) -> Path:
    return root / ".lore" / "reports"


def watchers_dir(root: Path) -> Path:
    return root / ".lore" / "watchers"


def db_path(root: Path) -> Path:
    return root / ".lore" / "lore.db"


def derive_group(filepath: Path, base_dir: Path) -> str:
    """Derive the GROUP value for an entity from its path relative to its base directory.

    The GROUP is built from all directory components between base_dir and the
    file, joined with slashes, excluding the filename itself.  A file stored
    directly in base_dir returns an empty string.

    Raises ValueError if filepath is not located under base_dir (propagated
    from Path.relative_to).
    """
    relative = filepath.relative_to(base_dir)
    parts = relative.parts[:-1]
    return "/".join(parts)


def group_matches_filter(group: str, filter_groups: list[str]) -> bool:
    """Return True if ``group`` should be included for the given filter tokens.

    A group is included when:
    - It is the root group (empty string), or
    - One of the filter tokens, split on ``'/'``, is a segment-prefix of the
      group's own slash-delimited segments.

    Leading and trailing ``'/'`` on tokens are stripped silently. Empty tokens
    (``""`` or ``"/"``) are ignored defensively; CLI validation rejects them
    earlier where required.

    Examples::

        group_matches_filter("", ["a/b"])            # True  (root)
        group_matches_filter("a/b", ["a/b"])         # True  (exact)
        group_matches_filter("a/b/c", ["a/b"])       # True  (segment prefix)
        group_matches_filter("technical/api", ["tech"])  # False (bare substring)
    """
    if group == "":
        return True
    group_segs = group.split("/")
    for token in filter_groups:
        normalized = token.strip("/")
        if not normalized:
            continue
        tok_segs = normalized.split("/")
        if group_segs[: len(tok_segs)] == tok_segs:
            return True
    return False
