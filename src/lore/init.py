"""Project initialization logic for `lore init`."""

from importlib import resources
from pathlib import Path

from lore import paths
from lore.db import init_database


_GLOSSARY_SKELETON = (
    "# Project glossary — see `lore codex show conceptual-entities-glossary`.\n"
    "# Before adding a term, run: `lore artifact show glossary-design`.\n"
    "# Auto-surfaced on `lore codex show`. Toggle via .lore/config.toml.\n"
    "items: []\n"
)

_CONFIG_SKELETON = (
    "# Project-level Lore configuration.\n"
    "# Known keys (additional keys are accepted and ignored):\n"
    "#   show-glossary-on-codex-commands : bool, default true\n"
    "show-glossary-on-codex-commands = true\n"
)


def _seed_skeleton_if_absent(target: Path, content: str, label: str) -> list[str]:
    """Write ``content`` to ``target`` only when the file does not exist.

    Creates parent directories as needed.  Idempotent — existing files are
    left byte-for-byte untouched.  Returns a single-element status message
    list when a file is created, or an empty list when skipped.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return []
    target.write_text(content)
    return [f"  Created {label}"]


def _seed_glossary(project_root: Path) -> list[str]:
    """Seed `.lore/codex/glossary.yaml` and `.lore/config.toml` if absent.

    Idempotent: existing files are left byte-for-byte untouched.  Both files
    are user-tracked skeletons that the `lore glossary` feature relies on.
    """
    messages = _seed_skeleton_if_absent(
        paths.glossary_path(project_root),
        _GLOSSARY_SKELETON,
        "codex/glossary.yaml",
    )
    messages.extend(
        _seed_skeleton_if_absent(
            paths.config_path(project_root),
            _CONFIG_SKELETON,
            "config.toml",
        )
    )
    return messages


def _copy_defaults_tree(
    source_package: str,
    target_dir: Path,
    exclude: set[str] | None = None,
    label: str | None = None,
) -> list[str]:
    """Copy default files from a nested package subdirectory tree, overwriting existing files.

    Args:
        source_package: Subdirectory name within ``lore.defaults`` to copy from.
        target_dir: Destination directory where files are written.
        exclude: Optional set of directory names to skip at the top level.
        label: Prefix used in status messages instead of ``source_package``.
               Useful when the target path differs from the package name.

    Returns:
        List of human-readable status messages (one per file copied).
    """
    messages = []
    source_root = resources.files("lore.defaults").joinpath(source_package)

    def _walk(node, rel: Path) -> None:
        for item in node.iterdir():
            if item.is_dir():
                if exclude and item.name in exclude:
                    continue
                _walk(item, rel / item.name)
            elif item.is_file():
                dest = target_dir / rel / item.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                verb = "Updated" if dest.exists() else "Created"
                dest.write_text(item.read_text())
                messages.append(
                    f"  {verb} {label or source_package}/{(rel / item.name).as_posix()}"
                )

    _walk(source_root, Path())
    return messages


def run_init() -> list[str]:
    """Run the full lore init sequence in the current working directory.

    Returns a list of human-readable status messages.
    """
    cwd = Path.cwd()
    lore_dir = cwd / ".lore"
    messages: list[str] = []

    # Create the .lore/ directory (idempotent)
    if lore_dir.is_dir():
        messages.append("  .lore/ directory already exists")
    else:
        lore_dir.mkdir()
        messages.append("  Created .lore/ directory")

    # Refresh .lore/.gitignore from the seed template (always overwrite)
    messages.append(_write_lore_gitignore(lore_dir / ".gitignore"))

    # Create or verify the SQLite database
    messages.extend(_format_db_status(init_database(lore_dir / "lore.db")))

    # Copy default doctrines, knights, and artifacts (Lore overwrites its own files)
    messages.extend(
        _copy_defaults_tree(
            "doctrines", lore_dir / "doctrines" / "default", label="doctrines/default"
        )
    )
    messages.extend(
        _copy_defaults_tree(
            "knights", lore_dir / "knights" / "default", label="knights/default"
        )
    )
    messages.extend(
        _copy_defaults_tree(
            "artifacts",
            lore_dir / "artifacts" / "default",
            exclude={"bootstrap"},
            label="artifacts/default",
        )
    )

    # Seed flat docs (LORE-AGENT.md, GETTING-STARTED.md, CODEX.md) into .lore/.
    # Must precede the user-tracked skeletons so docs appear first in stdout
    # (Scenario 8 ordering invariant).
    messages.extend(_copy_defaults_tree("docs", lore_dir, label="docs"))

    # Seed user-tracked skeletons (idempotent — never overwrite user edits)
    messages.extend(_seed_glossary(cwd))

    # Copy default watchers and skills
    messages.extend(
        _copy_defaults_tree(
            "watchers", lore_dir / "watchers" / "default", label="watchers/default"
        )
    )
    messages.extend(
        _copy_defaults_tree("skills", lore_dir / "skills", label="skills")
    )

    # Generate skills/.gitignore listing every Lore-shipped skill, so when the
    # user copies this directory into .claude/skills/ the bundled skills are
    # ignored without manual gitignore edits.
    messages.append(_write_skills_gitignore(lore_dir / "skills" / ".gitignore"))

    return messages


def _write_lore_gitignore(target: Path) -> str:
    """Write `.lore/.gitignore` from the seed template; return status message."""
    content = resources.files("lore.defaults").joinpath("gitignore").read_text()
    verb = "Updated" if target.exists() else "Created"
    target.write_text(content)
    return f"  {verb} .gitignore"


def _write_skills_gitignore(target: Path) -> str:
    """Write the auto-generated `skills/.gitignore`; return status message."""
    skills_root = resources.files("lore.defaults").joinpath("skills")
    shipped_skills = sorted(
        item.name for item in skills_root.iterdir() if item.is_dir()
    )
    content = (
        "# Auto-generated by `lore init`. Lists skills shipped by Lore so they\n"
        "# stay untracked when this directory is copied into .claude/skills/.\n"
        "# Your own skills added here are not ignored.\n"
        + "".join(f"{name}/\n" for name in shipped_skills)
    )
    verb = "Updated" if target.exists() else "Created"
    target.write_text(content)
    return f"  {verb} skills/.gitignore"


def _format_db_status(status: str) -> list[str]:
    """Render an `init_database` status code as a status-message list.

    Returns an empty list for unknown statuses (matching the original
    silent-fallthrough behaviour).
    """
    match status:
        case "created":
            return ["  Created lore.db (schema version 1)"]
        case "existing":
            return ["  Skipped lore.db (already exists)"]
        case "reinitialized":
            return [
                "  Warning: Existing database appears corrupted. Reinitialized lore.db"
            ]
    return []
