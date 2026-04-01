"""Project root detection for Lore."""

from pathlib import Path


class ProjectNotFoundError(Exception):
    """Raised when no .lore/ directory is found in the directory hierarchy."""


def find_project_root(start: Path | None = None) -> Path:
    """Walk upward from `start` looking for a `.lore/` directory.

    Returns the directory containing `.lore/`.
    Raises ProjectNotFoundError if none is found up to the filesystem root.
    """
    current = (start or Path.cwd()).resolve()

    while True:
        if (current / ".lore").is_dir():
            return current
        parent = current.parent
        if parent == current:
            # Reached filesystem root
            raise ProjectNotFoundError(
                'Not a lore project (no .lore/ directory found). Run "lore init" to initialize.'
            )
        current = parent
