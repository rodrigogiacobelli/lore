"""Unit tests for the custom-codex-schema overlay resolver (RED).

Specs:
- custom-codex-schemas-us-1 — paths helpers + pure merge + resolve_merged_schema.
- custom-codex-schemas-us-2 — mtime-keyed project_validator_for cache.
- custom-codex-schemas-us-3 — validate_entity(project_root=...) keyword.

Standards (ADR-006): assert merge structure/behaviour and validation outcomes,
never the byte content of the packaged schema YAML. Overlay files are written
into tmp_path; mtime is bumped via os.utime.
"""

from __future__ import annotations

import os

import jsonschema
import pytest
import yaml

from lore import paths
from lore.schemas import (
    OverlayError,
    load_schema,
    merge_overlay,
    project_validator_for,
    resolve_merged_schema,
    validate_entity,
)

# Protected packaged keys per kind (ADR-014 core edge fields included for codex).
CODEX_PACKAGED_KEYS = ["id", "title", "summary", "type", "related", "binds", "rites"]
SOURCE_PACKAGED_KEYS = ["id", "title", "summary", "type", "related"]


def _write_overlay(root, kind: str, overlay: dict | list | str) -> os.PathLike:
    """Write an overlay YAML file under root/.lore/custom-schemas/<kind>.yaml."""
    path = paths.custom_schema_path(root, kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(overlay, str):
        path.write_text(overlay, encoding="utf-8")
    else:
        path.write_text(yaml.safe_dump(overlay), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# US-1 — path helpers
# --------------------------------------------------------------------------- #


def test_custom_schemas_dir_resolves(tmp_path):
    assert paths.custom_schemas_dir(tmp_path) == tmp_path / ".lore" / "custom-schemas"


@pytest.mark.parametrize("kind", ["codex-frontmatter", "codex-source-frontmatter"])
def test_custom_schema_path_resolves_both_kinds(tmp_path, kind):
    expected = tmp_path / ".lore" / "custom-schemas" / f"{kind}.yaml"
    assert paths.custom_schema_path(tmp_path, kind) == expected


# --------------------------------------------------------------------------- #
# US-1 — merge_overlay
# --------------------------------------------------------------------------- #


def test_merge_overlay_adds_properties():
    base = load_schema("codex-frontmatter")
    overlay = {"properties": {"owner": {"type": "string"}}}
    merged = merge_overlay(base, overlay, "codex-frontmatter")
    assert "owner" in merged["properties"]
    for key in CODEX_PACKAGED_KEYS:
        assert key in merged["properties"]


def test_merge_overlay_appends_required():
    base = load_schema("codex-frontmatter")
    packaged_required = list(base["required"])
    overlay = {
        "properties": {"owner": {"type": "string"}},
        "required": ["owner"],
    }
    merged = merge_overlay(base, overlay, "codex-frontmatter")
    assert merged["required"] == packaged_required + ["owner"]
    # packaged entries preserved and first
    assert merged["required"][: len(packaged_required)] == packaged_required


def test_merge_overlay_keeps_additional_properties_false_when_omitted():
    base = load_schema("codex-frontmatter")
    overlay = {"properties": {"owner": {"type": "string"}}}
    merged = merge_overlay(base, overlay, "codex-frontmatter")
    assert merged["additionalProperties"] is False


def test_merge_overlay_keeps_additional_properties_false_when_overlay_sets_true():
    base = load_schema("codex-frontmatter")
    overlay = {
        "properties": {"owner": {"type": "string"}},
        "additionalProperties": True,
    }
    merged = merge_overlay(base, overlay, "codex-frontmatter")
    assert merged["additionalProperties"] is False


def test_merge_overlay_ignores_overlay_id():
    base = load_schema("codex-frontmatter")
    packaged_id = base["$id"]
    overlay = {
        "properties": {"owner": {"type": "string"}},
        "$id": "lore://schemas/overlay-hijack",
    }
    merged = merge_overlay(base, overlay, "codex-frontmatter")
    assert merged["$id"] == packaged_id


@pytest.mark.parametrize("collision", CODEX_PACKAGED_KEYS)
def test_merge_overlay_rejects_codex_packaged_collision(collision):
    base = load_schema("codex-frontmatter")
    overlay = {"properties": {collision: {"type": "string"}}}
    with pytest.raises(OverlayError) as exc:
        merge_overlay(base, overlay, "codex-frontmatter")
    assert collision in str(exc.value)


@pytest.mark.parametrize("collision", SOURCE_PACKAGED_KEYS)
def test_merge_overlay_rejects_source_packaged_collision(collision):
    base = load_schema("codex-source-frontmatter")
    overlay = {"properties": {collision: {"type": "string"}}}
    with pytest.raises(OverlayError) as exc:
        merge_overlay(base, overlay, "codex-source-frontmatter")
    assert collision in str(exc.value)


def test_merge_overlay_rejects_undeclared_required():
    base = load_schema("codex-frontmatter")
    overlay = {
        "properties": {"owner": {"type": "string"}},
        "required": ["ghost"],
    }
    with pytest.raises(OverlayError) as exc:
        merge_overlay(base, overlay, "codex-frontmatter")
    assert "ghost" in str(exc.value)


def test_merge_overlay_does_not_mutate_base():
    base = load_schema("codex-frontmatter")
    base_props_before = set(base["properties"])
    base_required_before = list(base["required"])
    overlay = {
        "properties": {"owner": {"type": "string"}},
        "required": ["owner"],
    }
    merge_overlay(base, overlay, "codex-frontmatter")
    merge_overlay(base, overlay, "codex-frontmatter")
    assert set(base["properties"]) == base_props_before
    assert base["required"] == base_required_before


# --------------------------------------------------------------------------- #
# US-1 — resolve_merged_schema
# --------------------------------------------------------------------------- #


def test_resolve_no_overlay_returns_packaged(tmp_path):
    assert resolve_merged_schema("codex-frontmatter", tmp_path) == load_schema(
        "codex-frontmatter"
    )


def test_resolve_overlay_merges(tmp_path):
    _write_overlay(tmp_path, "codex-frontmatter", {"properties": {"owner": {"type": "string"}}})
    merged = resolve_merged_schema("codex-frontmatter", tmp_path)
    assert "owner" in merged["properties"]


def test_resolve_unparseable_yaml_raises(tmp_path):
    _write_overlay(tmp_path, "codex-frontmatter", "properties: {owner: : :}\n  bad: [unclosed")
    with pytest.raises(OverlayError) as exc:
        resolve_merged_schema("codex-frontmatter", tmp_path)
    assert "invalid YAML" in str(exc.value)


def test_resolve_non_mapping_overlay_raises(tmp_path):
    _write_overlay(tmp_path, "codex-frontmatter", ["not", "a", "mapping"])
    with pytest.raises(OverlayError) as exc:
        resolve_merged_schema("codex-frontmatter", tmp_path)
    assert "overlay must be a mapping" in str(exc.value)


def test_resolve_missing_properties_raises(tmp_path):
    _write_overlay(tmp_path, "codex-frontmatter", {"required": ["owner"]})
    with pytest.raises(OverlayError) as exc:
        resolve_merged_schema("codex-frontmatter", tmp_path)
    assert "overlay 'properties' must be a mapping" in str(exc.value)


def test_resolve_properties_not_a_mapping_raises(tmp_path):
    _write_overlay(tmp_path, "codex-frontmatter", {"properties": ["owner"]})
    with pytest.raises(OverlayError) as exc:
        resolve_merged_schema("codex-frontmatter", tmp_path)
    assert "overlay 'properties' must be a mapping" in str(exc.value)


def test_overlay_error_is_value_error():
    assert issubclass(OverlayError, ValueError)


# --------------------------------------------------------------------------- #
# US-2 — project_validator_for cache
# --------------------------------------------------------------------------- #


def test_project_validator_uses_merged_schema(tmp_path):
    _write_overlay(tmp_path, "codex-frontmatter", {"properties": {"owner": {"type": "string"}}})
    validator = project_validator_for("codex-frontmatter", tmp_path)
    assert isinstance(validator, jsonschema.Draft202012Validator)
    assert "owner" in validator.schema["properties"]


def test_project_validator_cache_hit_unchanged_overlay(tmp_path):
    _write_overlay(tmp_path, "codex-frontmatter", {"properties": {"owner": {"type": "string"}}})
    first = project_validator_for("codex-frontmatter", tmp_path)
    second = project_validator_for("codex-frontmatter", tmp_path)
    assert first is second


def test_project_validator_rereads_on_mtime_change(tmp_path):
    path = _write_overlay(
        tmp_path, "codex-frontmatter", {"properties": {"owner": {"type": "string"}}}
    )
    first = project_validator_for("codex-frontmatter", tmp_path)
    # rewrite overlay to add reviewed, then bump mtime so st_mtime_ns changes
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string"}, "reviewed": {"type": "boolean"}}},
    )
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
    second = project_validator_for("codex-frontmatter", tmp_path)
    assert second is not first
    assert "reviewed" in second.schema["properties"]


def test_project_validator_sentinel_key_no_collision(tmp_path):
    first = project_validator_for("codex-frontmatter", tmp_path)  # no overlay -> sentinel -1
    assert "owner" not in first.schema["properties"]
    _write_overlay(tmp_path, "codex-frontmatter", {"properties": {"owner": {"type": "string"}}})
    second = project_validator_for("codex-frontmatter", tmp_path)
    assert second is not first
    assert "owner" in second.schema["properties"]


def test_project_validator_propagates_overlay_error(tmp_path):
    _write_overlay(tmp_path, "codex-frontmatter", {"properties": {"title": {"type": "string"}}})
    with pytest.raises(OverlayError):
        project_validator_for("codex-frontmatter", tmp_path)


# --------------------------------------------------------------------------- #
# US-3 — validate_entity(project_root=...)
# --------------------------------------------------------------------------- #


def _valid_codex_doc(**extra):
    data = {"id": "doc-1", "title": "Doc", "summary": "A doc."}
    data.update(extra)
    return data


def test_validate_entity_project_root_accepts_custom_key(tmp_path):
    _write_overlay(tmp_path, "codex-frontmatter", {"properties": {"owner": {"type": "string"}}})
    data = _valid_codex_doc(owner="alice")
    assert validate_entity("codex-frontmatter", data, project_root=tmp_path) == []


def test_validate_entity_project_root_rejects_typo(tmp_path):
    _write_overlay(tmp_path, "codex-frontmatter", {"properties": {"owner": {"type": "string"}}})
    data = _valid_codex_doc(onwer="alice")
    issues = validate_entity("codex-frontmatter", data, project_root=tmp_path)
    assert len(issues) == 1
    assert "Unknown property 'onwer'" in issues[0].message
    assert "owner" in issues[0].message


def test_validate_entity_project_root_missing_required(tmp_path):
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string"}}, "required": ["owner"]},
    )
    data = _valid_codex_doc()  # no owner
    issues = validate_entity("codex-frontmatter", data, project_root=tmp_path)
    assert any("Missing required property 'owner'" in i.message for i in issues)


def test_validate_entity_none_root_is_packaged(tmp_path):
    data = _valid_codex_doc()
    assert validate_entity("codex-frontmatter", data) == validate_entity(
        "codex-frontmatter", data, project_root=None
    )


def test_validate_entity_non_overlay_kind_ignores_root(tmp_path):
    # Write a would-be overlay for a non-eligible kind; it must be ignored.
    _write_overlay(tmp_path, "glossary", {"properties": {"owner": {"type": "string"}}})
    data = {"terms": []}
    assert validate_entity("glossary", data, project_root=tmp_path) == validate_entity(
        "glossary", data
    )


def test_validate_entity_project_root_propagates_overlay_error(tmp_path):
    _write_overlay(tmp_path, "codex-frontmatter", {"properties": {"title": {"type": "string"}}})
    with pytest.raises(OverlayError):
        validate_entity("codex-frontmatter", _valid_codex_doc(), project_root=tmp_path)


# --------------------------------------------------------------------------- #
# US-6 — public API surface (lore.api re-export + facade purity + parity)
# --------------------------------------------------------------------------- #

_RESOLVER_PUBLIC_NAMES = ("resolve_merged_schema", "project_validator_for", "OverlayError")


@pytest.mark.parametrize("name", _RESOLVER_PUBLIC_NAMES)
def test_resolver_name_in_api_all(name):
    import lore.api as api

    assert name in api.__all__


@pytest.mark.parametrize("name", _RESOLVER_PUBLIC_NAMES)
def test_resolver_name_importable_from_api(name):
    import lore.api as api

    assert getattr(api, name, None) is not None


@pytest.mark.parametrize("name", _RESOLVER_PUBLIC_NAMES)
def test_api_resolver_name_is_schemas_object(name):
    import lore.api as api
    import lore.schemas as schemas

    assert getattr(api, name) is getattr(schemas, name)


def test_resolver_names_import_directly_from_api():
    # Scenario 1: the explicit `from lore.api import ...` consumer path.
    from lore.api import OverlayError as api_overlay_error
    from lore.api import project_validator_for as api_project_validator_for
    from lore.api import resolve_merged_schema as api_resolve_merged_schema

    assert api_resolve_merged_schema is resolve_merged_schema
    assert api_project_validator_for is project_validator_for
    assert api_overlay_error is OverlayError


def test_api_facade_has_no_definitions():
    """api.py stays a pure re-export facade — zero FunctionDef / ClassDef."""
    import ast
    from pathlib import Path

    import lore.api as api

    source = Path(api.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    defs = [
        node
        for node in ast.walk(tree)
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        )
    ]
    assert defs == [], [getattr(d, "name", d) for d in defs]


def test_validate_entity_parity_api_vs_schemas(tmp_path):
    """ADR-011: api and schemas validate_entity agree for a declared custom
    key reached via ``project_root``."""
    import lore.api as api
    import lore.schemas as schemas

    _write_overlay(
        tmp_path, "codex-frontmatter", {"properties": {"owner": {"type": "string"}}}
    )
    data = _valid_codex_doc(owner="alice")
    api_result = api.validate_entity("codex-frontmatter", data, project_root=tmp_path)
    schemas_result = schemas.validate_entity(
        "codex-frontmatter", data, project_root=tmp_path
    )
    assert api_result == schemas_result == []
