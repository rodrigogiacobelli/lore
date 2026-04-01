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
