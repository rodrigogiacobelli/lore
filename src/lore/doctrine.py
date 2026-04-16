"""Doctrine loading and validation."""

import shutil
import textwrap
from pathlib import Path

import click
import yaml

from lore.frontmatter import parse_frontmatter_doc
from lore.paths import derive_group, group_matches_filter
from lore.schemas import validate_entity
from lore.validators import validate_group, validate_name


class DoctrineError(click.ClickException):
    """Raised when a doctrine fails validation.

    Subclasses ``click.ClickException`` so both exception types catch it.
    """

    def __str__(self) -> str:
        return self.message


def scaffold_doctrine(name: str) -> str:
    """Return a minimal valid doctrine YAML skeleton for the given name."""
    return textwrap.dedent(f"""\
        id: {name}
        title: {name.capitalize()}
        summary: A short summary of the {name} doctrine.
        description: A longer description of the {name} doctrine.
        steps:
          - name: Example step
            description: Describe what this step does.
        """)


def _raise_click_from_issues(issues: list) -> None:
    """Raise ``DoctrineError`` whose message contains every issue message."""
    if not issues:
        return
    raise DoctrineError("\n".join(i.message for i in issues))


def _validate_yaml_schema(data: dict, name: str) -> None:
    """Validate the top-level YAML schema for a doctrine.

    Delegates to ``lore.schemas.validate_entity('doctrine-yaml', data)`` and
    raises ``click.ClickException`` on any returned issue. Additionally checks
    that the doctrine id matches the ``name`` argument.
    """
    issues = validate_entity("doctrine-yaml", data)
    if issues:
        raise DoctrineError("\n".join(i.message for i in issues))

    if str(data["id"]) != name:
        raise DoctrineError(
            f'Doctrine id "{data["id"]}" does not match command argument "{name}"'
        )


def _validate_design_frontmatter(meta: dict | None, name: str) -> None:
    """Validate design file frontmatter.

    Delegates to ``lore.schemas.validate_entity('doctrine-design-frontmatter', data)``
    and raises ``click.ClickException`` on any returned issue. Additionally checks
    that the id matches the ``name`` argument.
    """
    data = meta if meta is not None else {}

    # Check id presence and match before full schema validation so id-mismatch
    # errors surface ahead of any other schema complaint.
    if "id" not in data:
        issues = validate_entity("doctrine-design-frontmatter", data)
        id_issues = [i for i in issues if "'id'" in i.message]
        raise DoctrineError(
            "\n".join(i.message for i in (id_issues or issues))
        )
    if str(data["id"]) != name:
        raise DoctrineError(
            f'Design file id "{data["id"]}" does not match command argument "{name}"'
        )

    issues = validate_entity("doctrine-design-frontmatter", data)
    if issues:
        raise DoctrineError("\n".join(i.message for i in issues))


def _check_duplicate_in_subtree(name: str, doctrines_dir: Path) -> None:
    """Raise DoctrineError if a doctrine with the given name exists anywhere under doctrines_dir."""
    if not doctrines_dir.exists():
        return
    for suffix in (".yaml", ".design.md"):
        existing = next(iter(doctrines_dir.rglob(f"{name}{suffix}")), None)
        if existing is not None:
            raise DoctrineError(
                f"Error: doctrine '{name}' already exists at {existing}"
            )


def _parse_design_frontmatter(design_text: str) -> dict | None:
    """Extract the YAML frontmatter block from a design file, or None if absent/invalid."""
    parts = design_text.split("---")
    if len(parts) < 3:
        return None
    try:
        meta = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None
    return meta if isinstance(meta, dict) else None


def _validate_source_files(
    name: str, yaml_source_path: Path, design_source_path: Path
) -> None:
    """Validate both source files exist and contain well-formed, name-matching content."""
    if not yaml_source_path.exists():
        raise DoctrineError(f"File not found: {yaml_source_path}")
    if not design_source_path.exists():
        raise DoctrineError(f"File not found: {design_source_path}")

    try:
        yaml_data = yaml.safe_load(yaml_source_path.read_text())
    except yaml.YAMLError as e:
        raise DoctrineError(f"YAML parsing error: {e}") from e
    if not isinstance(yaml_data, dict):
        raise DoctrineError("Doctrine must be a YAML mapping")
    _validate_yaml_schema(yaml_data, name)

    meta = _parse_design_frontmatter(design_source_path.read_text())
    _validate_design_frontmatter(meta, name)


def create_doctrine(
    name: str,
    yaml_source_path: Path,
    design_source_path: Path,
    doctrines_dir: Path,
    *,
    group: str | None = None,
) -> dict:
    """Register both source files as a new doctrine in doctrines_dir.

    Validation order:
    1. Name format
    2. Group format
    3. Duplicate check (recursive subtree)
    4. Source files exist and contain valid content
    5. Write both files (atomic — no partial writes)

    When ``group`` is provided, files are placed in ``doctrines_dir / group``
    with intermediate directories created as needed. When ``group`` is None,
    files land directly in ``doctrines_dir``.

    Raises DoctrineError on any validation failure.
    """
    name_err = validate_name(name)
    if name_err:
        raise DoctrineError(name_err)

    group_err = validate_group(group)
    if group_err:
        raise DoctrineError(group_err)

    _check_duplicate_in_subtree(name, doctrines_dir)
    _validate_source_files(name, yaml_source_path, design_source_path)

    target_dir = doctrines_dir if group is None else doctrines_dir / group
    yaml_dest = target_dir / f"{name}.yaml"
    design_dest = target_dir / f"{name}.design.md"

    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(yaml_source_path, yaml_dest)
    shutil.copy2(design_source_path, design_dest)

    return {
        "name": name,
        "group": group,
        "yaml_filename": f"{name}.yaml",
        "design_filename": f"{name}.design.md",
        "path": str(yaml_dest),
    }


def load_doctrine(filepath: Path) -> dict:
    """Load and validate a doctrine YAML file.

    Returns the parsed doctrine dict on success.
    Raises DoctrineError on validation failure.
    """
    text = filepath.read_text()
    data = _parse_yaml(text)
    _validate(data, filepath.name)
    return _normalize(data)


def _parse_yaml(text: str) -> dict:
    """Parse YAML text and ensure it is a mapping.

    Raises DoctrineError on parse failure or non-dict content.
    """
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise DoctrineError(f"YAML parsing error: {e}") from e

    if not isinstance(data, dict):
        raise DoctrineError("Doctrine must be a YAML mapping")

    return data


def _validate(data: dict, filename: str) -> None:
    """Validate doctrine data against schema rules."""
    _validate_required_fields(data)

    # Name must match filename; accept id as fallback for name
    doctrine_name = data.get("name") or data.get("id")
    expected_name = filename.removesuffix(".yaml")
    if doctrine_name != expected_name:
        raise DoctrineError(
            f'Doctrine name "{doctrine_name}" does not match filename "{filename}"'
        )

    _validate_steps(data["steps"])


def _validate_required_fields(data: dict) -> None:
    """Check that required top-level fields are present."""
    # Accept id as fallback for name
    if "name" not in data and "id" not in data:
        raise DoctrineError("Missing required property 'name'.")
    for field in ("description", "steps"):
        if field not in data:
            raise DoctrineError(f"Missing required property '{field}'.")


def _validate_steps(steps) -> None:
    """Validate the steps list: structure, fields, deps, and cycles."""
    if not isinstance(steps, list) or len(steps) == 0:
        raise DoctrineError("Steps must be a non-empty list")

    seen_ids = set()
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise DoctrineError(f"Step {i} must be a mapping")

        if "id" not in step:
            raise DoctrineError(f"Step {i} missing required field: id")
        if "title" not in step:
            raise DoctrineError(f'Step "{step["id"]}" missing required field: title')

        step_id = step["id"]
        if step_id in seen_ids:
            raise DoctrineError(f'Duplicate step id: "{step_id}"')
        seen_ids.add(step_id)

        if "priority" in step:
            pri = step["priority"]
            if not isinstance(pri, int) or pri < 0 or pri > 4:
                raise DoctrineError(
                    f'Step "{step_id}" has invalid priority: {pri} (must be 0-4)'
                )

        if "type" in step and not isinstance(step["type"], str):
            raise DoctrineError(f'Step "{step_id}" type must be a string')

    for step in steps:
        for dep in step.get("needs", []):
            if dep not in seen_ids:
                raise DoctrineError(
                    f'Step "{step["id"]}" references unknown dependency "{dep}"'
                )

    _check_cycles(steps)


def _check_cycles(steps: list[dict]) -> None:
    """Detect dependency cycles using DFS."""
    # Build adjacency: step_id -> list of step_ids it depends on
    graph = {}
    for step in steps:
        graph[step["id"]] = step.get("needs", [])

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {sid: WHITE for sid in graph}

    def dfs(node):
        color[node] = GRAY
        for neighbor in graph.get(node, []):
            if color[neighbor] == GRAY:
                raise DoctrineError(
                    f'Dependency cycle detected involving step "{node}"'
                )
            if color[neighbor] == WHITE:
                dfs(neighbor)
        color[node] = BLACK

    for node in graph:
        if color[node] == WHITE:
            dfs(node)


def _normalize(data: dict) -> dict:
    """Normalize doctrine data, applying defaults."""
    steps = []
    for step in data["steps"]:
        steps.append(
            {
                "id": step["id"],
                "title": step["title"],
                "priority": step.get("priority", 2),
                "type": step.get("type", None),
                "needs": step.get("needs", []),
                "knight": step.get("knight"),
                "notes": step.get("notes"),
            }
        )
    result = {
        "name": data.get("name") or data.get("id"),
        "description": data["description"],
        "steps": steps,
    }
    for key in ("id", "title", "summary"):
        if key in data:
            result[key] = data[key]
    return result


def validate_doctrine_content(text: str, expected_name: str) -> dict:
    """Validate raw doctrine YAML text against schema rules.

    Returns the parsed data dict on success.
    Raises DoctrineError on validation failure.
    """
    data = _parse_yaml(text)

    _validate_required_fields(data)

    # Name must match command argument
    doctrine_name = data.get("name") or data.get("id")
    if str(doctrine_name) != expected_name:
        raise DoctrineError(
            f'Doctrine name "{doctrine_name}" does not match command argument "{expected_name}"'
        )

    # If id field is present, it must match the command argument
    if "id" in data and str(data["id"]) != expected_name:
        raise DoctrineError(
            f'Doctrine id "{data["id"]}" does not match command argument "{expected_name}"'
        )

    _validate_steps(data["steps"])

    return data


def _truncate_description(text: str, width: int = 80) -> str:
    """Truncate a description to approximately ``width`` characters at a word boundary.

    If ``text`` fits within ``width`` characters, returns it unchanged.
    Otherwise returns the longest prefix that ends on a word boundary and appends "...".
    The total length of the returned string is at most ``width + 3`` characters.
    """
    if len(text) <= width:
        return text
    # Truncate to width chars then backtrack to last space
    truncated = text[:width]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated + "..."


def _find_doctrine_files(doctrine_id: str, doctrines_dir: Path) -> tuple[Path | None, Path | None]:
    """Search recursively for <id>.design.md and <id>.yaml under doctrines_dir.

    Returns a tuple (design_file, yaml_file). Either or both may be None if not found.

    When multiple matches exist, shallower paths (fewer directory levels from doctrines_dir)
    are preferred so that user-managed files take priority over defaults in subdirectories.
    The shallower of the primary YAML or primary DESIGN determines which directory is used
    as the source of truth; the other file is expected to be co-located there.
    """
    if not doctrines_dir.exists():
        return None, None

    def _depth(p: Path) -> int:
        return len(p.relative_to(doctrines_dir).parts)

    def _by_depth(p: Path) -> tuple[int, str]:
        return (_depth(p), str(p))

    yaml_matches = sorted(doctrines_dir.rglob(f"{doctrine_id}.yaml"), key=_by_depth)
    design_matches = sorted(doctrines_dir.rglob(f"{doctrine_id}.design.md"), key=_by_depth)

    if not yaml_matches and not design_matches:
        return None, None

    primary_yaml = yaml_matches[0] if yaml_matches else None
    primary_design = design_matches[0] if design_matches else None

    if primary_yaml is None:
        # Only design files found; check if a co-located YAML exists
        co_located_yaml = primary_design.parent / f"{doctrine_id}.yaml"
        if co_located_yaml.exists():
            return primary_design, co_located_yaml
        return primary_design, None

    if primary_design is None:
        # Only YAML files found; check if a co-located design exists
        co_located_design = primary_yaml.parent / f"{doctrine_id}.design.md"
        if co_located_design.exists():
            return co_located_design, primary_yaml
        return None, primary_yaml

    yaml_depth = _depth(primary_yaml)
    design_depth = _depth(primary_design)

    if design_depth <= yaml_depth:
        # Design is shallower (or equal depth) — it is the anchor; check for co-located YAML
        co_located_yaml = primary_design.parent / f"{doctrine_id}.yaml"
        if co_located_yaml.exists():
            return primary_design, co_located_yaml
        return primary_design, None

    # YAML is shallower — it is the anchor; check for co-located design
    co_located_design = primary_yaml.parent / f"{doctrine_id}.design.md"
    if co_located_design.exists():
        return co_located_design, primary_yaml
    return None, primary_yaml


def show_doctrine(doctrine_id: str, doctrines_dir: Path) -> dict:
    """Load and return a doctrine by ID for display.

    Searches recursively for <id>.design.md and <id>.yaml under doctrines_dir.
    Returns a dict with keys: id, title, summary, design, raw_yaml, steps.
    Raises DoctrineError with specific messages when files are missing or invalid.
    """
    design_file, yaml_file = _find_doctrine_files(doctrine_id, doctrines_dir)

    if design_file is None and yaml_file is None:
        raise DoctrineError(f"Doctrine '{doctrine_id}' not found")
    if design_file is None:
        raise DoctrineError(f"Doctrine '{doctrine_id}' not found: design file missing")
    if yaml_file is None:
        raise DoctrineError(f"Doctrine '{doctrine_id}' not found: YAML file missing")

    design_text = design_file.read_text()
    yaml_text = yaml_file.read_text()

    data = _parse_yaml(yaml_text)

    # Normalize steps with defaults (no description required unlike load_doctrine)
    raw_steps = data.get("steps") or []
    steps = [
        {
            "id": step["id"],
            "title": step["title"],
            "priority": step.get("priority", 2),
            "type": step.get("type", None),
            "needs": step.get("needs", []),
            "knight": step.get("knight"),
            "notes": step.get("notes"),
        }
        for step in raw_steps
        if isinstance(step, dict)
    ]

    meta = parse_frontmatter_doc(design_file, required_fields=("id",), extra_fields=("title", "summary"))
    title = (meta.get("title") if meta else None) or doctrine_id
    summary = (meta.get("summary") if meta else None) or ""

    return {
        "id": doctrine_id,
        "title": title,
        "summary": summary,
        "design": design_text,
        "raw_yaml": yaml_text,
        "steps": steps,
    }


def list_doctrines(doctrines_dir: Path, filter_groups: list[str] | None = None) -> list[dict]:
    """List all valid doctrine pairs (design + yaml).

    Scans for ``*.design.md`` files; for each, checks a matching ``*.yaml``
    exists in the same directory. Parses frontmatter from the design file.
    Silently skips orphaned design files, YAML-only files, and design files
    with missing or invalid ``id`` frontmatter.

    Returns a list of dicts with keys: id, group, title, summary, valid, filename.
    """
    if not doctrines_dir.exists():
        return []

    results = []
    for design_file in sorted(doctrines_dir.rglob("*.design.md")):
        # Check matching .yaml exists in the same directory
        stem = design_file.name.removesuffix(".design.md")
        yaml_file = design_file.parent / (stem + ".yaml")
        if not yaml_file.exists():
            continue

        # Parse design frontmatter; id is required
        meta = parse_frontmatter_doc(design_file, required_fields=("id",), extra_fields=("title", "summary"))
        if meta is None:
            continue

        doctrine_id = meta["id"]
        title = meta.get("title") or doctrine_id
        summary = meta.get("summary") or ""

        entry = {
            "id": doctrine_id,
            "group": derive_group(design_file, doctrines_dir),
            "title": title,
            "summary": summary,
            "valid": True,
            "filename": design_file.name,
        }
        results.append(entry)

    if filter_groups:
        results = [r for r in results if group_matches_filter(r.get("group", ""), filter_groups)]

    return results
