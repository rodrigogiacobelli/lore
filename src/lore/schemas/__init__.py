"""Packaged JSON-Schema (draft 2020-12) resources, loader, and validators.

Public API:
    from lore.schemas import load_schema, validate_entity, validate_entity_file, SchemaIssue
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

import jsonschema
import yaml

__all__ = [
    "load_schema",
    "validate_entity",
    "validate_entity_file",
    "SchemaIssue",
]


@functools.lru_cache(maxsize=None)
def load_schema(kind: str) -> dict[str, Any]:
    """Load a packaged JSON Schema YAML resource by kind.

    Returns the parsed schema dict. Cached — repeat calls return the same object.
    Raises FileNotFoundError with message "Unknown schema kind: '<kind>'" when
    the kind does not correspond to a packaged ``<kind>.yaml`` resource.
    """
    resource = files("lore.schemas") / f"{kind}.yaml"
    if not resource.is_file():
        raise FileNotFoundError(f"Unknown schema kind: '{kind}'")
    return yaml.safe_load(resource.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class SchemaIssue:
    rule: str
    pointer: str
    message: str


@functools.lru_cache(maxsize=None)
def _validator_for(kind: str) -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(load_schema(kind))


_FRONTMATTER_KINDS = {
    "knight-frontmatter",
    "codex-frontmatter",
    "artifact-frontmatter",
    "doctrine-design-frontmatter",
}

_YAML_KINDS = {"doctrine-yaml", "watcher-yaml"}


def _pointer_from_path(path_parts: list) -> str:
    if not path_parts:
        return "/"
    return "/" + "/".join(str(p) for p in path_parts)


def _unexpected_keys(err: jsonschema.ValidationError) -> list[str]:
    """Return keys present on the instance but absent from the schema's properties."""
    allowed = set(err.schema.get("properties", {}))
    return sorted(set(err.instance) - allowed)


def _missing_required_key(err: jsonschema.ValidationError) -> str:
    """Extract the missing property name from a jsonschema ``required`` error."""
    return err.message.split("'")[1] if "'" in err.message else ""


def _format_message(err: jsonschema.ValidationError) -> str:
    if err.validator == "additionalProperties":
        unexpected = _unexpected_keys(err)
        allowed = list(err.schema.get("properties", {}).keys())
        key = unexpected[0] if unexpected else ""
        return f"Unknown property '{key}' — allowed keys are {', '.join(allowed)}."
    if err.validator == "required":
        return f"Missing required property '{_missing_required_key(err)}'."
    return err.message


def _issue_from_error(err: jsonschema.ValidationError) -> SchemaIssue:
    path = list(err.absolute_path)
    if err.validator == "additionalProperties":
        unexpected = _unexpected_keys(err)
        if unexpected:
            path = path + [unexpected[0]]
    return SchemaIssue(
        rule=str(err.validator),
        pointer=_pointer_from_path(path),
        message=_format_message(err),
    )


def validate_entity(kind: str, data: Any) -> list[SchemaIssue]:
    """Validate an in-memory dict against a named schema.

    Returns a list of SchemaIssue records. Never raises on validation failure.
    Raises FileNotFoundError if ``kind`` is not a known schema.
    """
    validator = _validator_for(kind)
    issues: list[SchemaIssue] = []
    required_by_pointer: dict[str, SchemaIssue] = {}
    required_missing: dict[str, list[str]] = {}

    for err in validator.iter_errors(data):
        issue = _issue_from_error(err)
        if err.validator == "required":
            missing = _missing_required_key(err)
            pointer = issue.pointer
            if pointer in required_by_pointer:
                required_missing[pointer].append(missing)
                existing = required_by_pointer[pointer]
                names = required_missing[pointer]
                merged_msg = "Missing required properties " + ", ".join(
                    f"'{n}'" for n in names
                ) + "."
                new_issue = SchemaIssue(rule="required", pointer=pointer, message=merged_msg)
                idx = issues.index(existing)
                issues[idx] = new_issue
                required_by_pointer[pointer] = new_issue
            else:
                required_by_pointer[pointer] = issue
                required_missing[pointer] = [missing]
                issues.append(issue)
        else:
            issues.append(issue)

    return issues


MISSING_FRONTMATTER_MESSAGE = "File has no YAML frontmatter block"
NON_MAPPING_FRONTMATTER_MESSAGE = "Frontmatter block is not a mapping."


def _missing_frontmatter_issue(message: str = MISSING_FRONTMATTER_MESSAGE) -> list[SchemaIssue]:
    return [SchemaIssue(rule="missing-frontmatter", pointer="/", message=message)]


def validate_entity_file(path: str, kind: str) -> list[SchemaIssue]:
    """Validate a file on disk against a named schema.

    Dispatches on kind suffix: ``-yaml`` kinds go through ``yaml.safe_load``,
    frontmatter kinds go through a frontmatter parser. Returns a list of
    SchemaIssue records; never raises on read/parse failure.
    """
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        return [SchemaIssue(rule="read-failed", pointer="/", message=str(e))]

    if kind in _YAML_KINDS:
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as e:
            return [SchemaIssue(rule="yaml-parse", pointer="/", message=str(e))]
    elif kind in _FRONTMATTER_KINDS:
        if not text.startswith("---"):
            return _missing_frontmatter_issue()
        parts = text.split("---", 2)
        if len(parts) < 3:
            return _missing_frontmatter_issue()
        try:
            data = yaml.safe_load(parts[1])
        except yaml.YAMLError as e:
            return [SchemaIssue(rule="yaml-parse", pointer="/", message=str(e))]
        if not isinstance(data, dict):
            return _missing_frontmatter_issue(NON_MAPPING_FRONTMATTER_MESSAGE)
    else:
        # Unknown kind — surface through validate_entity's FileNotFoundError path.
        load_schema(kind)
        data = None

    return validate_entity(kind, data)
