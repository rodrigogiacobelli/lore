"""Unit tests for lore.schemas.load_schema (US-001) and validate_entity/_file (US-002).

Specs:
- schema-validation-us-001 — packaged YAML schemas + load_schema loader.
- schema-validation-us-002 — validate_entity and validate_entity_file.
"""

from importlib.resources import files

import pytest

from lore.schemas import (
    SchemaIssue,
    load_schema,
    validate_entity,
    validate_entity_file,
)

KINDS = [
    "doctrine-yaml",
    "doctrine-design-frontmatter",
    "knight-frontmatter",
    "watcher-yaml",
    "codex-frontmatter",
    "artifact-frontmatter",
]


def _walk_objects(node):
    """Yield every dict node inside a schema tree."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk_objects(v)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_objects(item)


class TestLoadSchemaReturnsDict:
    def test_returns_dict_for_every_known_kind(self):
        for kind in KINDS:
            schema = load_schema(kind)
            assert isinstance(schema, dict), f"{kind}: expected dict, got {type(schema)}"


class TestLoadSchemaDraft2020:
    def test_returns_draft_2020_schema_for_every_kind(self):
        for kind in KINDS:
            schema = load_schema(kind)
            assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema", (
                f"{kind}: wrong $schema"
            )


class TestLoadSchemaId:
    def test_returns_lore_scheme_id_for_every_kind(self):
        for kind in KINDS:
            schema = load_schema(kind)
            assert schema["$id"] == f"lore://schemas/{kind}", f"{kind}: wrong $id"


class TestLoadSchemaCache:
    def test_second_call_returns_same_object(self):
        for kind in KINDS:
            assert load_schema(kind) is load_schema(kind), f"{kind}: cache miss"


class TestLoadSchemaUnknownKind:
    def test_unknown_kind_raises_file_not_found_with_clear_message(self):
        with pytest.raises(FileNotFoundError, match="Unknown schema kind: 'nope'"):
            load_schema("nope")


class TestLoadSchemaAdditionalPropertiesFalse:
    def test_every_schema_preserves_additional_properties_false_somewhere(self):
        # Every packaged schema declares additionalProperties: false at least once
        # (root or nested in $defs). Guards against YAML round-trip drift.
        for kind in KINDS:
            schema = load_schema(kind)
            found = any(
                node.get("additionalProperties") is False
                for node in _walk_objects(schema)
            )
            assert found, f"{kind}: no 'additionalProperties: false' survived load"


class TestPackageShipsEverySchemaYaml:
    def test_importlib_resources_lists_every_schema(self):
        names = {p.name for p in files("lore.schemas").iterdir()}
        for kind in KINDS:
            assert f"{kind}.yaml" in names, f"missing packaged resource: {kind}.yaml"


# ---------------------------------------------------------------------------
# US-002 — validate_entity / validate_entity_file
# ---------------------------------------------------------------------------


def _good_watcher(**overrides):
    base = {
        "id": "w",
        "title": "W",
        "summary": "s",
        "watch_target": ["src/"],
        "interval": "on_merge",
        "action": [{"doctrine": "d"}],
    }
    base.update(overrides)
    return base


def _good_doctrine(**overrides):
    base = {
        "id": "d",
        "steps": [
            {"id": "s1", "title": "S1", "type": "knight", "knight": "pm"},
        ],
    }
    base.update(overrides)
    return base


def _doctrine_with_step(**step_overrides):
    step = {"id": "s1", "title": "S1", "type": "knight", "knight": "pm"}
    step.update(step_overrides)
    return {"id": "d", "steps": [step]}


GOOD = {
    "knight-frontmatter": {"id": "pm", "title": "PM", "summary": "s"},
    "codex-frontmatter": {"id": "c", "title": "C", "summary": "s"},
    "artifact-frontmatter": {"id": "a", "title": "A", "summary": "s"},
    "doctrine-design-frontmatter": {"id": "d", "title": "D", "summary": "s"},
    "doctrine-yaml": _good_doctrine(),
    "watcher-yaml": _good_watcher(),
}


VALID_DOCTRINE_YAML_TEXT = (
    "id: d\n"
    "steps:\n"
    "  - id: s1\n"
    "    title: S1\n"
    "    type: knight\n"
    "    knight: pm\n"
)


class TestSchemaIssueDataclass:
    def test_is_frozen_dataclass_with_three_fields(self):
        issue = SchemaIssue(rule="required", pointer="/", message="Missing required property 'title'.")
        assert issue.rule == "required"
        assert issue.pointer == "/"
        assert issue.message == "Missing required property 'title'."
        with pytest.raises(Exception):
            issue.rule = "other"  # frozen


class TestValidateEntityHappyPath:
    def test_every_known_kind_accepts_its_good_fixture(self):
        for kind, data in GOOD.items():
            assert validate_entity(kind, data) == [], f"{kind}: expected no issues"


class TestValidateEntityRequired:
    def test_missing_summary_on_knight_frontmatter(self):
        issues = validate_entity("knight-frontmatter", {"id": "pm", "title": "PM"})
        assert len(issues) == 1
        assert issues[0].rule == "required"
        assert issues[0].pointer == "/"


class TestValidateEntityAdditionalProperties:
    def test_stability_rejected_on_codex_frontmatter(self):
        issues = validate_entity(
            "codex-frontmatter",
            {"id": "x", "title": "T", "summary": "s", "stability": "stable"},
        )
        matching = [i for i in issues if i.rule == "additionalProperties"]
        assert len(matching) == 1
        assert matching[0].pointer == "/stability"


class TestValidateEntityType:
    def test_related_mapping_rejected_on_codex_frontmatter(self):
        issues = validate_entity(
            "codex-frontmatter",
            {"id": "x", "title": "T", "summary": "s", "related": {"foo": "bar"}},
        )
        matching = [i for i in issues if i.rule == "type"]
        assert len(matching) == 1
        assert matching[0].pointer == "/related"


class TestValidateEntityEnum:
    def test_watcher_interval_rejects_unknown_value(self):
        issues = validate_entity("watcher-yaml", _good_watcher(interval="sometimes"))
        matching = [i for i in issues if i.rule == "enum"]
        assert len(matching) == 1
        assert matching[0].pointer == "/interval"


class TestValidateEntityMinItems:
    def test_watcher_watch_target_rejects_empty_list(self):
        issues = validate_entity("watcher-yaml", _good_watcher(watch_target=[]))
        matching = [i for i in issues if i.rule == "minItems"]
        assert len(matching) == 1
        assert matching[0].pointer == "/watch_target"


class TestValidateEntityUniqueItems:
    def test_codex_related_rejects_duplicates(self):
        issues = validate_entity(
            "codex-frontmatter",
            {"id": "x", "title": "T", "summary": "s", "related": ["a", "a"]},
        )
        matching = [i for i in issues if i.rule == "uniqueItems"]
        assert len(matching) == 1
        assert matching[0].pointer == "/related"


class TestValidateEntityMinLength:
    def test_knight_summary_empty_string_rejected(self):
        issues = validate_entity(
            "knight-frontmatter",
            {"id": "pm", "title": "PM", "summary": ""},
        )
        matching = [i for i in issues if i.rule == "minLength"]
        assert len(matching) == 1
        assert matching[0].pointer == "/summary"


class TestValidateEntityOneOf:
    def test_watcher_action_with_both_doctrine_and_bash(self):
        issues = validate_entity(
            "watcher-yaml",
            _good_watcher(action=[{"doctrine": "d", "bash": "b"}]),
        )
        matching = [i for i in issues if i.rule == "oneOf"]
        assert len(matching) >= 1
        assert all(i.pointer.startswith("/action") for i in matching)


class TestValidateEntityIfThenElse:
    def test_doctrine_step_empty_knight_string_flagged(self):
        issues = validate_entity("doctrine-yaml", _doctrine_with_step(knight=""))
        assert any(i.pointer.startswith("/steps/") for i in issues)


class TestValidateEntityMultiError:
    def test_collects_both_missing_title_and_unknown_stability(self):
        issues = validate_entity(
            "knight-frontmatter",
            {"id": "pm", "stability": "x"},
        )
        rules = sorted(i.rule for i in issues)
        assert rules == ["additionalProperties", "required"]


class TestValidateEntityUnknownKind:
    def test_raises_file_not_found_mentioning_kind(self):
        with pytest.raises(FileNotFoundError, match="nope"):
            validate_entity("nope", {})


class TestValidateEntityFileFullYamlDispatch:
    def test_doctrine_yaml_loaded_via_yaml_safe_load(self, tmp_path):
        p = tmp_path / "d.yaml"
        p.write_text(VALID_DOCTRINE_YAML_TEXT)
        assert validate_entity_file(str(p), "doctrine-yaml") == []

    def test_watcher_yaml_loaded_via_yaml_safe_load(self, tmp_path):
        import yaml as _yaml

        p = tmp_path / "w.yaml"
        p.write_text(_yaml.safe_dump(_good_watcher()))
        assert validate_entity_file(str(p), "watcher-yaml") == []


class TestValidateEntityFileFrontmatterDispatch:
    def test_knight_frontmatter_via_parse_frontmatter_raw(self, tmp_path):
        p = tmp_path / "k.md"
        p.write_text("---\nid: pm\ntitle: PM\nsummary: s\n---\nbody\n")
        assert validate_entity_file(str(p), "knight-frontmatter") == []

    def test_codex_frontmatter_via_parse_frontmatter_raw(self, tmp_path):
        p = tmp_path / "c.md"
        p.write_text("---\nid: c\ntitle: C\nsummary: s\n---\nbody\n")
        assert validate_entity_file(str(p), "codex-frontmatter") == []

    def test_artifact_frontmatter_via_parse_frontmatter_raw(self, tmp_path):
        p = tmp_path / "a.md"
        p.write_text("---\nid: a\ntitle: A\nsummary: s\n---\nbody\n")
        assert validate_entity_file(str(p), "artifact-frontmatter") == []

    def test_doctrine_design_frontmatter_via_parse_frontmatter_raw(self, tmp_path):
        p = tmp_path / "d.md"
        p.write_text("---\nid: d\ntitle: D\nsummary: s\n---\nbody\n")
        assert validate_entity_file(str(p), "doctrine-design-frontmatter") == []


class TestValidateEntityFileOSError:
    def test_os_error_during_read_returns_read_failed_issue(self, tmp_path, monkeypatch):
        p = tmp_path / "k.md"
        p.write_text("---\nid: pm\ntitle: PM\nsummary: s\n---\n")

        def boom(*a, **kw):
            raise PermissionError("denied")

        monkeypatch.setattr("builtins.open", boom)
        issues = validate_entity_file(str(p), "knight-frontmatter")
        assert len(issues) == 1
        assert issues[0].rule == "read-failed"
        assert issues[0].pointer == "/"


class TestValidateEntityFileUnparseableYaml:
    def test_returns_only_yaml_parse_issue(self, tmp_path):
        p = tmp_path / "w.yaml"
        p.write_text("key: : : nope")
        issues = validate_entity_file(str(p), "watcher-yaml")
        assert len(issues) == 1
        assert issues[0].rule == "yaml-parse"
        assert issues[0].pointer == "/"


class TestValidateEntityFileMissingFrontmatter:
    def test_returns_missing_frontmatter_issue(self, tmp_path):
        p = tmp_path / "k.md"
        p.write_text("just body\n")
        issues = validate_entity_file(str(p), "knight-frontmatter")
        assert len(issues) == 1
        assert issues[0].rule == "missing-frontmatter"
        assert issues[0].pointer == "/"


class TestValidateEntityMessageFormatting:
    def test_additional_properties_message_lists_allowed_keys(self):
        issues = validate_entity(
            "knight-frontmatter",
            {"id": "pm", "title": "PM", "summary": "s", "stability": "x"},
        )
        matching = [i for i in issues if i.rule == "additionalProperties"]
        assert len(matching) == 1
        msg = matching[0].message
        assert "stability" in msg
        assert "allowed keys" in msg

    def test_required_message_names_missing_property(self):
        issues = validate_entity("knight-frontmatter", {"id": "pm", "title": "PM"})
        matching = [i for i in issues if i.rule == "required"]
        assert len(matching) == 1
        assert "summary" in matching[0].message
        assert "Missing required property" in matching[0].message


# ---------------------------------------------------------------------------
# US-006 — Unparseable YAML, missing frontmatter, and read-failed short-circuit
# schema-validation-us-006 / conceptual-workflows-health — FR-10, FR-11, FR-25
# ---------------------------------------------------------------------------


class TestUs006YamlParseSingleIssue:
    def test_yaml_parse_error_message_is_parser_text(self, tmp_path):
        """FR-10: message == str(exc) — non-empty yaml.YAMLError text."""
        import yaml as _yaml

        p = tmp_path / "w.yaml"
        p.write_text("watch_target: : :")
        issues = validate_entity_file(str(p), "watcher-yaml")
        assert len(issues) == 1
        assert issues[0].rule == "yaml-parse"
        assert issues[0].pointer == "/"
        # Must equal str(exc) — reproduce to compare.
        try:
            _yaml.safe_load("watch_target: : :")
        except _yaml.YAMLError as exc:
            expected = str(exc)
        assert issues[0].message == expected

    def test_yaml_parse_short_circuits_other_schema_rules(self, tmp_path):
        """FR-10: malformed doctrine yaml returns exactly one yaml-parse issue,
        not additional required/additionalProperties issues for same file."""
        p = tmp_path / "d.yaml"
        # Content both fails YAML parsing and (if it parsed) would be missing
        # required fields like steps.
        p.write_text("id: : :\nsteps: :")
        issues = validate_entity_file(str(p), "doctrine-yaml")
        assert len(issues) == 1
        assert issues[0].rule == "yaml-parse"

    def test_yaml_parse_short_circuits_on_frontmatter_kind(self, tmp_path):
        """FR-10: bad yaml inside frontmatter block → one yaml-parse, no others."""
        p = tmp_path / "k.md"
        p.write_text("---\nid: : :\ntitle: [unclosed\n---\nbody\n")
        issues = validate_entity_file(str(p), "knight-frontmatter")
        assert len(issues) == 1
        assert issues[0].rule == "yaml-parse"
        assert issues[0].pointer == "/"


class TestUs006MissingFrontmatterExactMessage:
    def test_missing_frontmatter_message_exact_no_period(self, tmp_path):
        """FR-11: message == 'File has no YAML frontmatter block' (no trailing period)."""
        p = tmp_path / "c.md"
        p.write_text("just some notes\n")
        issues = validate_entity_file(str(p), "codex-frontmatter")
        assert len(issues) == 1
        assert issues[0].rule == "missing-frontmatter"
        assert issues[0].pointer == "/"
        assert issues[0].message == "File has no YAML frontmatter block"

    def test_missing_frontmatter_empty_file(self, tmp_path):
        """Zero-byte frontmatter-kind file emits a single missing-frontmatter issue."""
        p = tmp_path / "k.md"
        p.write_text("")
        issues = validate_entity_file(str(p), "knight-frontmatter")
        assert len(issues) == 1
        assert issues[0].rule == "missing-frontmatter"
        assert issues[0].message == "File has no YAML frontmatter block"

    def test_missing_frontmatter_bom_prefix(self, tmp_path):
        """UTF-8 BOM before body (no ---) still produces a loud missing-frontmatter issue."""
        p = tmp_path / "c.md"
        p.write_bytes(b"\xef\xbb\xbfjust notes\n")
        issues = validate_entity_file(str(p), "codex-frontmatter")
        assert len(issues) == 1
        assert issues[0].rule == "missing-frontmatter"
        assert issues[0].message == "File has no YAML frontmatter block"

    def test_missing_frontmatter_short_circuits_no_other_rules(self, tmp_path):
        """No stray required/additionalProperties issues emitted alongside missing-frontmatter."""
        p = tmp_path / "a.md"
        p.write_text("plain body only\n")
        issues = validate_entity_file(str(p), "artifact-frontmatter")
        assert [i.rule for i in issues] == ["missing-frontmatter"]


class TestUs006ReadFailedBranch:
    def test_permission_error_message_contains_os_text(self, tmp_path, monkeypatch):
        """read-failed issue carries OS error text (substring 'Permission denied')."""
        p = tmp_path / "k.md"
        p.write_text("---\nid: pm\ntitle: PM\nsummary: s\n---\n")
        real_open = open

        def boom(path, *a, **kw):
            if str(path) == str(p):
                raise PermissionError("Permission denied")
            return real_open(path, *a, **kw)

        monkeypatch.setattr("builtins.open", boom)
        issues = validate_entity_file(str(p), "knight-frontmatter")
        assert len(issues) == 1
        assert issues[0].rule == "read-failed"
        assert issues[0].pointer == "/"
        assert "Permission denied" in issues[0].message

    def test_unicode_decode_error_becomes_read_failed(self, tmp_path):
        """Non-UTF8 bytes (latin-1 0xff) produce one read-failed issue — no crash."""
        p = tmp_path / "k.md"
        # 0xff is invalid as UTF-8 start byte.
        p.write_bytes(b"---\nid: pm\ntitle: \xff\xfe\nsummary: s\n---\n")
        issues = validate_entity_file(str(p), "knight-frontmatter")
        assert len(issues) == 1
        assert issues[0].rule == "read-failed"
        assert issues[0].pointer == "/"
        assert issues[0].message  # non-empty OS/Unicode error text

    def test_read_failed_short_circuits_no_other_rules(self, tmp_path, monkeypatch):
        """A read failure emits exactly one issue — no yaml-parse or schema rules follow."""
        p = tmp_path / "w.yaml"
        p.write_text("id: w\n")

        def boom(*a, **kw):
            raise OSError("disk gone")

        monkeypatch.setattr("builtins.open", boom)
        issues = validate_entity_file(str(p), "watcher-yaml")
        assert [i.rule for i in issues] == ["read-failed"]
        assert "disk gone" in issues[0].message


# ---------------------------------------------------------------------------
# US-010 — Structural regression: create-time modules must not inline rules
# Spec: schema-validation-us-010
# Workflow: conceptual-workflows-validators
# ---------------------------------------------------------------------------


class TestUs010CreateTimeModulesDelegateToSchemas:
    """After US-010 green, the four create-time modules must import validate_entity
    from lore.schemas and must not hand-code JSON-Schema-style rules."""

    _MODULES = ("doctrine.py", "knight.py", "watcher.py", "artifact.py")

    def _read(self, name: str) -> str:
        import pathlib
        return (pathlib.Path(__file__).resolve().parents[2] / "src" / "lore" / name).read_text()

    def test_doctrine_module_imports_validate_entity(self):
        assert "validate_entity" in self._read("doctrine.py")

    def test_knight_module_imports_validate_entity(self):
        assert "validate_entity" in self._read("knight.py")

    def test_watcher_module_imports_validate_entity(self):
        assert "validate_entity" in self._read("watcher.py")

    def test_artifact_module_imports_validate_entity(self):
        assert "validate_entity" in self._read("artifact.py")

    def test_no_inline_required_field_strings(self):
        """Hand-coded 'Missing required field:' strings must be gone after delegation."""
        for name in self._MODULES:
            text = self._read(name)
            assert "Missing required field" not in text, (
                f"{name} still hand-codes 'Missing required field' — should delegate to lore.schemas"
            )

    def test_no_inline_unexpected_field_strings(self):
        """Hand-coded 'Unexpected field' strings must be gone after delegation."""
        for name in self._MODULES:
            text = self._read(name)
            assert "Unexpected field" not in text, (
                f"{name} still hand-codes 'Unexpected field' — should delegate to lore.schemas"
            )
