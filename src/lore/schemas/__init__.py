"""Packaged JSON-Schema (draft 2020-12) resources, loader, and validators.

The public API is the set of names in ``__all__``: the schema loader, the entity
validators, the project-overlay resolver, and their issue/error types.
"""

from __future__ import annotations

import copy
import functools
import os
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from lore import paths

__all__ = [
    "load_schema",
    "validate_entity",
    "validate_entity_file",
    "SchemaIssue",
    "SchemaValidationError",
    "OverlayError",
    "merge_overlay",
    "resolve_merged_schema",
    "project_validator_for",
]


class OverlayError(ValueError):
    """Raised when a custom-schema overlay is malformed or collides with packaged keys."""


class SchemaValidationError(Exception):
    """Raised when a full-YAML kind fails schema validation in raise-mode."""

    def __init__(self, message: str, issues: list["SchemaIssue"] | None = None) -> None:
        super().__init__(message)
        self.issues = issues or []


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


_OVERLAY_KINDS = frozenset({"codex-frontmatter", "codex-source-frontmatter"})


def merge_overlay(base: dict, overlay: dict, kind: str) -> dict:
    """Merge a project overlay onto a packaged schema (add-only, defaults-authoritative).

    Overlay ``properties`` are injected; overlay ``required`` entries are appended
    after the packaged ones. ``additionalProperties`` is pinned ``False`` and ``$id``
    is left as the packaged value. A property colliding with a packaged key, or a
    ``required`` entry naming a property not declared in the overlay, raises
    ``OverlayError``. The ``base`` dict is not mutated.
    """
    merged = copy.deepcopy(base)
    packaged_keys = set(merged.get("properties", {}))
    overlay_props = overlay.get("properties", {}) or {}

    for key in overlay_props:
        if key in packaged_keys:
            raise OverlayError(
                f"property '{key}' collides with a packaged field and cannot be overridden"
            )

    merged.setdefault("properties", {}).update(overlay_props)

    overlay_required = overlay.get("required", []) or []
    for name in overlay_required:
        if name not in overlay_props:
            raise OverlayError(
                f"required entry '{name}' is not declared in this overlay"
            )
    merged["required"] = list(merged.get("required", [])) + list(overlay_required)

    merged["additionalProperties"] = False
    return merged


def resolve_merged_schema(kind: str, project_root: Path) -> dict:
    """Return the packaged schema for ``kind`` merged with the project overlay, if any.

    Absent overlay file -> the packaged ``load_schema(kind)`` content unchanged.
    Present -> parse the overlay YAML, validate its shape, and ``merge_overlay``.
    Malformed overlays raise ``OverlayError``.
    """
    overlay_path = paths.custom_schema_path(project_root, kind)
    try:
        text = overlay_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return load_schema(kind)

    try:
        overlay = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise OverlayError(f"{overlay_path}: invalid YAML: {e}") from e

    if not isinstance(overlay, dict):
        raise OverlayError(f"{overlay_path}: overlay must be a mapping")
    if not isinstance(overlay.get("properties"), dict):
        raise OverlayError(f"{overlay_path}: overlay 'properties' must be a mapping")

    try:
        return merge_overlay(load_schema(kind), overlay, kind)
    except OverlayError as e:
        raise OverlayError(f"{overlay_path}: {e}") from e


_project_validator_cache: dict[tuple[str, str, int], jsonschema.Draft202012Validator] = {}


def project_validator_for(kind: str, project_root: Path) -> jsonschema.Draft202012Validator:
    """Return a validator for ``kind`` merged with the project overlay, cached on mtime.

    Cache key is ``(kind, str(project_root), overlay_mtime_ns)`` where the mtime is
    ``-1`` when the overlay file is absent. An edited overlay (changed mtime) yields
    a fresh validator. ``OverlayError`` from resolution propagates.
    """
    overlay_path = paths.custom_schema_path(project_root, kind)
    try:
        mtime_ns = os.stat(overlay_path).st_mtime_ns
    except FileNotFoundError:
        mtime_ns = -1

    key = (kind, str(project_root), mtime_ns)
    cached = _project_validator_cache.get(key)
    if cached is not None:
        return cached

    validator = jsonschema.Draft202012Validator(resolve_merged_schema(kind, project_root))
    _project_validator_cache[key] = validator
    return validator


_FRONTMATTER_KINDS = {
    "knight-frontmatter",
    "codex-frontmatter",
    "artifact-frontmatter",
    "doctrine-design-frontmatter",
}

_YAML_KINDS = {"doctrine-yaml", "watcher-yaml", "glossary", "main-rite", "shared-step"}

_RAISE_KINDS = {"glossary"}


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


def validate_entity(
    kind: str, data: Any, project_root: Path | None = None
) -> list[SchemaIssue]:
    """Validate an in-memory dict against a named schema.

    Returns a list of SchemaIssue records. Never raises on validation failure.
    Raises FileNotFoundError if ``kind`` is not a known schema.

    When ``project_root`` is provided and ``kind`` is overlay-eligible
    (``codex-frontmatter`` / ``codex-source-frontmatter``), the project's merged
    validator is used; otherwise the packaged validator is used.
    """
    if project_root is not None and kind in _OVERLAY_KINDS:
        validator = project_validator_for(kind, project_root)
    else:
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
            if kind in _RAISE_KINDS:
                raise SchemaValidationError(f"yaml-parse: {e}") from e
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

    issues = validate_entity(kind, data)
    if kind in _RAISE_KINDS and issues:
        msg_parts = [f"{i.rule} at {i.pointer}: {i.message}" for i in issues]
        raise SchemaValidationError("; ".join(msg_parts), issues=issues)
    return issues
