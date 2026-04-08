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
    file, joined with dashes, excluding the filename itself.  A file stored
    directly in base_dir returns an empty string.

    Raises ValueError if filepath is not located under base_dir (propagated
    from Path.relative_to).
    """
    relative = filepath.relative_to(base_dir)
    parts = relative.parts[:-1]
    return "-".join(parts)


def group_matches_filter(group: str, filter_groups: list[str]) -> bool:
    """Return True if ``group`` should be included for the given filter tokens.

    A group is included when:
    - It is the root group (empty string), or
    - It equals one of the filter tokens exactly, or
    - It starts with a filter token followed by ``'-'`` (subtree semantics).

    Examples::

        group_matches_filter("", ["conceptual"])           # True  (root)
        group_matches_filter("conceptual", ["conceptual"]) # True  (exact)
        group_matches_filter("conceptual-workflows", ["conceptual"])  # True  (subtree)
        group_matches_filter("technical", ["conceptual"])  # False (unrelated)
        group_matches_filter("technical", ["tech"])        # False (no bare-prefix match)
    """
    if group == "":
        return True
    for token in filter_groups:
        if group == token or group.startswith(token + "-"):
            return True
    return False
