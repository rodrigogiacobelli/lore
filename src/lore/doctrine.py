"""Doctrine loading and validation."""

import textwrap
from pathlib import Path

import yaml

from lore.paths import derive_group, group_matches_filter


class DoctrineError(Exception):
    """Raised when a doctrine fails validation."""


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
        raise DoctrineError("Missing required field: name")
    for field in ("description", "steps"):
        if field not in data:
            raise DoctrineError(f"Missing required field: {field}")


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


def list_doctrines(doctrines_dir: Path, filter_groups: list[str] | None = None) -> list[dict]:
    """List all doctrines with validation status.

    Returns a list of dicts with keys: id, group, title, summary, valid, name,
    filename, description, and optional errors.

    Fallback behaviour when metadata is missing:
    - ``id``: filename stem
    - ``title``: id value
    - ``summary``: explicit summary field; if absent, description truncated to
      ~80 chars; if neither present, empty string
    - ``group``: derived from subdirectory path
    """
    if not doctrines_dir.exists():
        return []

    results = []
    for filepath in sorted(doctrines_dir.rglob("*.yaml")):
        stem = filepath.stem
        entry = {"name": stem, "filename": filepath.name}
        # Always read raw YAML for enriched metadata fields
        try:
            raw_text = filepath.read_text()
            raw = yaml.safe_load(raw_text)
            if not isinstance(raw, dict):
                raw = {}
        except Exception:
            raw = {}
        try:
            doctrine = load_doctrine(filepath)
            entry["description"] = doctrine["description"]
            entry["valid"] = True
        except DoctrineError as e:
            entry["description"] = raw.get("description", "") or ""
            entry["valid"] = False
            entry["errors"] = [str(e)]
        except Exception:
            entry["description"] = ""
            entry["valid"] = False
            entry["errors"] = ["Failed to parse YAML"]

        # Enriched fields
        doctrine_id = str(raw["id"]) if "id" in raw and raw["id"] is not None else stem
        title = str(raw["title"]) if "title" in raw and raw["title"] is not None else doctrine_id
        if "summary" in raw and raw["summary"] is not None:
            summary = str(raw["summary"])
        elif entry.get("description"):
            summary = _truncate_description(str(entry["description"]))
        else:
            summary = ""

        entry["id"] = doctrine_id
        entry["group"] = derive_group(filepath, doctrines_dir)
        entry["title"] = title
        entry["summary"] = summary

        results.append(entry)

    if filter_groups:
        results = [r for r in results if group_matches_filter(r.get("group", ""), filter_groups)]

    return results
