"""Project initialization logic for `lore init`."""

from importlib import resources
from pathlib import Path

from lore.db import init_database


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
    messages = []

    # Step 1: Create .lore/ directory
    if lore_dir.is_dir():
        messages.append("  .lore/ directory already exists")
    else:
        lore_dir.mkdir()
        messages.append("  Created .lore/ directory")

    # Step 2: Create .lore/.gitignore
    gitignore_path = lore_dir / ".gitignore"
    default_gitignore = (
        resources.files("lore.defaults").joinpath("gitignore").read_text()
    )
    verb = "Updated" if gitignore_path.exists() else "Created"
    gitignore_path.write_text(default_gitignore)
    messages.append(f"  {verb} .gitignore")

    # Step 3: Create/verify .lore/lore.db
    db_path = lore_dir / "lore.db"
    db_status = init_database(db_path)
    match db_status:
        case "created":
            messages.append("  Created lore.db (schema version 1)")
        case "existing":
            messages.append("  Skipped lore.db (already exists)")
        case "reinitialized":
            messages.append(
                "  Warning: Existing database appears corrupted. Reinitialized lore.db"
            )

    # Step 4: Copy default doctrines
    messages.extend(
        _copy_defaults_tree(
            "doctrines", lore_dir / "doctrines" / "default", label="doctrines/default"
        )
    )

    # Step 5: Copy default knights
    messages.extend(
        _copy_defaults_tree(
            "knights", lore_dir / "knights" / "default", label="knights/default"
        )
    )

    # Step 6: Copy default artifacts
    messages.extend(
        _copy_defaults_tree(
            "artifacts",
            lore_dir / "artifacts" / "default",
            exclude={"bootstrap"},
            label="artifacts/default",
        )
    )

    # Step 8: Copy default watchers
    messages.extend(
        _copy_defaults_tree(
            "watchers", lore_dir / "watchers" / "default", label="watchers/default"
        )
    )

    # Step 9: Seed LORE-AGENT.md
    lore_agent_path = lore_dir / "LORE-AGENT.md"
    lore_agent_content = resources.files("lore.defaults").joinpath("LORE-AGENT.md").read_text()
    verb = "Updated" if lore_agent_path.exists() else "Created"
    lore_agent_path.write_text(lore_agent_content)
    messages.append(f"  {verb} LORE-AGENT.md")

    # Step 10: Seed GETTING-STARTED.md
    getting_started_path = lore_dir / "GETTING-STARTED.md"
    getting_started_content = resources.files("lore.defaults").joinpath("GETTING-STARTED.md").read_text()
    verb = "Updated" if getting_started_path.exists() else "Created"
    getting_started_path.write_text(getting_started_content)
    messages.append(f"  {verb} GETTING-STARTED.md")

    # Step 11: Copy default skills
    messages.extend(
        _copy_defaults_tree("skills", lore_dir / "skills", label="skills")
    )

    return messages
