"""Unit tests for lore.schemas.load_schema (US-001) and validate_entity/_file (US-002).

Specs:
- schema-validation-us-001 — packaged YAML schemas + load_schema loader.
- schema-validation-us-002 — validate_entity and validate_entity_file.
"""

from importlib.resources import files

import jsonschema
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


# ---------------------------------------------------------------------------
# US-001 (codex-sources-us-001) — codex-source-frontmatter schema file
# Anchors:
#   conceptual-workflows-health §Schema checks contract — the codex-source
#   frontmatter is just another kind in the table; the loader contract is the
#   same (load_schema returns a dict whose $id / additionalProperties /
#   required / properties match the authored YAML).
# Red state: src/lore/schemas/codex-source-frontmatter.yaml does NOT exist yet,
# so load_schema("codex-source-frontmatter") must raise FileNotFoundError —
# every US-001 test below therefore fails until the schema file is authored.
# ---------------------------------------------------------------------------


@pytest.fixture
def source_validator():
    """Draft2020 validator bound to the codex-source-frontmatter schema.

    Every US-001 test constructs the same validator against the same schema;
    the fixture de-duplicates that boilerplate without changing behaviour.
    """
    return jsonschema.Draft202012Validator(load_schema("codex-source-frontmatter"))


class TestUs001CodexSourceFrontmatterHappy:
    def test_codex_source_frontmatter_happy(self):
        # conceptual-workflows-health — schema kind registration: load_schema
        # returns a dict whose top-level $id / additionalProperties / required
        # / properties match the authored YAML.
        schema = load_schema("codex-source-frontmatter")
        assert schema["$id"] == "lore://schemas/codex-source-frontmatter"
        assert schema["additionalProperties"] is False
        assert schema["required"] == ["id", "title", "summary", "related"]
        assert schema["properties"]["related"]["minItems"] == 1
        assert schema["properties"]["related"]["uniqueItems"] is True

    def test_codex_source_frontmatter_valid_doc_produces_no_errors(
        self, source_validator
    ):
        # conceptual-workflows-health — positive-path validation (AC Scenario 8).
        doc = {
            "id": "KONE-23335",
            "title": "Integrate retry semantics",
            "summary": "Jira ticket — retry semantics for the foo connector.",
            "related": [
                "technical-backend-retry",
                "conceptual-entities-connector",
            ],
        }
        assert list(source_validator.iter_errors(doc)) == []


class TestUs001CodexSourceFrontmatterRejectsMissingRelated:
    def test_codex_source_frontmatter_rejects_missing_related(
        self, source_validator
    ):
        # conceptual-workflows-health — missing required field emits
        # validator=="required" (AC Scenario 2).
        errors = list(
            source_validator.iter_errors(
                {"id": "KONE-23335", "title": "T", "summary": "S"}
            )
        )
        assert any(
            e.validator == "required" and "related" in str(e.message)
            for e in errors
        )


class TestUs001CodexSourceFrontmatterRejectsEmptyRelated:
    def test_codex_source_frontmatter_rejects_empty_related(
        self, source_validator
    ):
        # conceptual-workflows-health — empty array under minItems constraint
        # (AC Scenario 3). Exactly one minItems error at /related.
        errors = list(
            source_validator.iter_errors(
                {"id": "KONE-23335", "title": "T", "summary": "S", "related": []}
            )
        )
        minitems = [e for e in errors if e.validator == "minItems"]
        assert len(minitems) == 1
        assert list(minitems[0].absolute_path) == ["related"]


class TestUs001CodexSourceFrontmatterRejectsExtraField:
    def test_codex_source_frontmatter_rejects_extra_field(self, source_validator):
        # conceptual-workflows-health — additionalProperties:false contract
        # (AC Scenario 4). Exactly one additionalProperties error naming 'foo'.
        errors = list(
            source_validator.iter_errors(
                {
                    "id": "x",
                    "title": "T",
                    "summary": "S",
                    "related": ["a"],
                    "foo": "bar",
                }
            )
        )
        extras = [e for e in errors if e.validator == "additionalProperties"]
        assert len(extras) == 1
        assert "foo" in str(extras[0].message)


class TestUs001CodexSourceFrontmatterRequiredFields:
    @pytest.mark.parametrize("missing", ["id", "title", "summary", "related"])
    def test_codex_source_frontmatter_requires_id_title_summary_related(
        self, missing, source_validator
    ):
        # conceptual-workflows-health — every required field fails with
        # validator=="required" (AC Scenario 5).
        doc = {"id": "x", "title": "T", "summary": "S", "related": ["a"]}
        doc.pop(missing)
        errors = list(source_validator.iter_errors(doc))
        assert any(
            e.validator == "required" and missing in str(e.message)
            for e in errors
        )


class TestUs001CodexSourceFrontmatterEmptyStrings:
    @pytest.mark.parametrize("field", ["id", "title", "summary"])
    def test_codex_source_frontmatter_empty_strings_rejected(
        self, field, source_validator
    ):
        # conceptual-workflows-health — minLength:1 on each string field
        # (AC Scenario 6).
        doc = {"id": "x", "title": "T", "summary": "S", "related": ["a"]}
        doc[field] = ""
        errors = list(source_validator.iter_errors(doc))
        hits = [
            e
            for e in errors
            if e.validator == "minLength" and list(e.absolute_path) == [field]
        ]
        assert len(hits) >= 1


class TestUs001CodexSourceFrontmatterDuplicateRelated:
    def test_codex_source_frontmatter_rejects_duplicate_related(
        self, source_validator
    ):
        # conceptual-workflows-health — uniqueItems constraint on related[]
        # (AC Scenario 7).
        errors = list(
            source_validator.iter_errors(
                {
                    "id": "x",
                    "title": "T",
                    "summary": "S",
                    "related": ["a", "a"],
                }
            )
        )
        assert any(e.validator == "uniqueItems" for e in errors)


class TestUs001CodexSourceFrontmatterPackagedResource:
    def test_schema_yaml_ships_with_package(self):
        # conceptual-workflows-health — Scenario 1: schema file ships with the
        # package so it is resolvable at import time.
        names = {p.name for p in files("lore.schemas").iterdir()}
        assert "codex-source-frontmatter.yaml" in names


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


# ---------------------------------------------------------------------------
# Glossary kind dispatch (glossary-us-001)
# ---------------------------------------------------------------------------
# Workflow: conceptual-workflows-glossary

def _write_glossary_yaml(tmp_path, body):
    p = tmp_path / "glossary.yaml"
    p.write_text(body, encoding="utf-8")
    return p


class TestValidateGlossaryKind:
    """validate_entity_file dispatches the glossary kind through the full-YAML
    path and raises SchemaValidationError on schema violations.

    Spec: glossary-us-001 (lore codex show glossary-us-001)
    """

    def test_glossary_schema_loadable(self):
        # conceptual-workflows-glossary — schema present (FR-19)
        schema = load_schema("glossary")
        assert isinstance(schema, dict)
        assert schema["$id"] == "lore://schemas/glossary"

    def test_validate_glossary_happy_does_not_raise(self, tmp_path):
        # conceptual-workflows-health — schema validates happy file
        from lore.schemas import SchemaValidationError  # noqa: F401 — must exist

        p = _write_glossary_yaml(
            tmp_path,
            "items:\n  - keyword: K\n    definition: D\n",
        )
        validate_entity_file(str(p), "glossary")  # no raise

    def test_validate_glossary_missing_keyword_raises(self, tmp_path):
        # conceptual-workflows-health — required rule for keyword
        from lore.schemas import SchemaValidationError

        p = _write_glossary_yaml(tmp_path, "items:\n  - definition: D\n")
        with pytest.raises(SchemaValidationError, match="required.*keyword"):
            validate_entity_file(str(p), "glossary")

    def test_validate_glossary_missing_definition_raises(self, tmp_path):
        # conceptual-workflows-health — required rule for definition
        from lore.schemas import SchemaValidationError

        p = _write_glossary_yaml(tmp_path, "items:\n  - keyword: K\n")
        with pytest.raises(SchemaValidationError, match="required.*definition"):
            validate_entity_file(str(p), "glossary")

    def test_validate_glossary_extra_top_level_key_raises(self, tmp_path):
        # conceptual-workflows-health — additionalProperties false at top level
        from lore.schemas import SchemaValidationError

        p = _write_glossary_yaml(tmp_path, "items: []\nextra: nope\n")
        with pytest.raises(SchemaValidationError, match="additionalProperties|extra"):
            validate_entity_file(str(p), "glossary")

    def test_validate_glossary_non_list_items_raises(self, tmp_path):
        # conceptual-workflows-health — type rule for items
        from lore.schemas import SchemaValidationError

        p = _write_glossary_yaml(tmp_path, "items: not-a-list\n")
        with pytest.raises(SchemaValidationError, match="type"):
            validate_entity_file(str(p), "glossary")

    def test_validate_glossary_multiline_keyword_rejected(self, tmp_path):
        # conceptual-workflows-health — pattern rule on keyword
        from lore.schemas import SchemaValidationError

        p = _write_glossary_yaml(
            tmp_path,
            'items:\n  - keyword: "two\\nlines"\n    definition: D\n',
        )
        with pytest.raises(SchemaValidationError, match="pattern"):
            validate_entity_file(str(p), "glossary")

    def test_validate_glossary_oversized_definition_rejected(self, tmp_path):
        # conceptual-workflows-health — maxLength rule on definition
        from lore.schemas import SchemaValidationError

        p = _write_glossary_yaml(
            tmp_path,
            f"items:\n  - keyword: K\n    definition: {'x' * 1001}\n",
        )
        with pytest.raises(SchemaValidationError, match="maxLength"):
            validate_entity_file(str(p), "glossary")

    def test_validate_glossary_duplicate_aliases_rejected(self, tmp_path):
        # conceptual-workflows-health — uniqueItems on aliases
        from lore.schemas import SchemaValidationError

        p = _write_glossary_yaml(
            tmp_path,
            "items:\n  - keyword: K\n    definition: D\n    aliases: [a, a]\n",
        )
        with pytest.raises(SchemaValidationError, match="uniqueItems"):
            validate_entity_file(str(p), "glossary")


# ---------------------------------------------------------------------------
# Rite schema kinds — main-rite + shared-step (transient-rites-us-1)
# Anchor: tech-arch-schemas — two new full-YAML kinds, $id lore://schemas/<kind>,
# additionalProperties:false; node not/anyOf do-XOR-use enforcement.
#
# validate_entity(kind, data) -> list[SchemaIssue]; [] means valid.
# These MUST fail until US-001 Green ships the two schema YAMLs + registration.
# ---------------------------------------------------------------------------


CANONICAL_MAIN_RITE = {
    "id": "issue-refund",
    "title": "Issue a refund for a returned order",
    "summary": "Confirm the customer is reachable, then refund.",
    "trigger": "Customer requests a refund on a returned order.",
    "nodes": [
        {
            "id": "locate-order",
            "do": "Find the order by id; confirm it is in 'returned' state.",
            "then": "get-contact",
        },
        {"id": "get-contact", "use": "read-contact-info", "then": "review-contact"},
        {
            "id": "review-contact",
            "do": "Decide whether contact details support a refund.",
            "then": [
                {"if": "email and a current mailing address are present", "goto": "do-refund"},
                {"if": "anything is missing or the address looks stale", "goto": "request-update"},
            ],
        },
        {"id": "do-refund", "do": "Post the refund to billing.", "then": "refunded"},
        {"id": "request-update", "do": "Ask the customer to confirm contact.", "then": "contact-requested"},
    ],
    "conclusions": {
        "refunded": {"audience": "customer-care", "response": "Refund posted."},
        "contact-requested": {"audience": "customer-care", "response": "Refund held."},
    },
}

CANONICAL_SHARED_STEP = {
    "id": "read-contact-info",
    "title": "Read the user's contact information",
    "summary": "Read the user's email, phone, and mailing address from admin.",
    "do": "Open the user profile in admin. Read and report back email, phone, address.",
}


def _drop_key(d, key):
    out = {k: v for k, v in d.items() if k != key}
    return out


def _rules(issues):
    return [i.rule for i in issues]


class TestRiteSchemaKindRegistration:
    """The two rite kinds are registered and load via load_schema with the
    canonical $id values."""

    def test_main_rite_schema_loadable_with_id(self):
        # tech-arch-schemas — main-rite kind reachable via load_schema
        schema = load_schema("main-rite")
        assert isinstance(schema, dict)
        assert schema["$id"] == "lore://schemas/main-rite"

    def test_shared_step_schema_loadable_with_id(self):
        # tech-arch-schemas — shared-step kind reachable via load_schema
        schema = load_schema("shared-step")
        assert isinstance(schema, dict)
        assert schema["$id"] == "lore://schemas/shared-step"

    def test_main_rite_schema_yaml_ships_with_package(self):
        # tech-arch-schemas — schema file packaged as a resource
        names = {p.name for p in files("lore.schemas").iterdir()}
        assert "main-rite.yaml" in names

    def test_shared_step_schema_yaml_ships_with_package(self):
        names = {p.name for p in files("lore.schemas").iterdir()}
        assert "shared-step.yaml" in names


class TestMainRiteSchemaHappy:
    def test_canonical_main_rite_validates_clean(self):
        # transient-rites-us-1 — happy fixture produces no issues
        assert validate_entity("main-rite", CANONICAL_MAIN_RITE) == []


class TestMainRiteSchemaViolations:
    def test_missing_summary_fails_required(self):
        # transient-rites-us-1 — required keyword
        issues = validate_entity("main-rite", _drop_key(CANONICAL_MAIN_RITE, "summary"))
        assert "required" in _rules(issues)

    def test_missing_trigger_fails_required(self):
        issues = validate_entity("main-rite", _drop_key(CANONICAL_MAIN_RITE, "trigger"))
        assert "required" in _rules(issues)

    def test_missing_nodes_fails_required(self):
        issues = validate_entity("main-rite", _drop_key(CANONICAL_MAIN_RITE, "nodes"))
        assert "required" in _rules(issues)

    def test_missing_conclusions_fails_required(self):
        issues = validate_entity("main-rite", _drop_key(CANONICAL_MAIN_RITE, "conclusions"))
        assert "required" in _rules(issues)

    def test_unknown_root_key_fails_additional_properties(self):
        # transient-rites-us-1 — additionalProperties:false at root
        issues = validate_entity("main-rite", {**CANONICAL_MAIN_RITE, "xtra": 1})
        assert "additionalProperties" in _rules(issues)

    def test_related_root_key_rejected(self):
        # ADR-014 — rite schema rejects outbound links automatically
        issues = validate_entity("main-rite", {**CANONICAL_MAIN_RITE, "related": ["x"]})
        assert "additionalProperties" in _rules(issues)

    def test_binds_root_key_rejected(self):
        issues = validate_entity("main-rite", {**CANONICAL_MAIN_RITE, "binds": ["x"]})
        assert "additionalProperties" in _rules(issues)

    def test_summary_wrong_type_fails_type(self):
        # transient-rites-us-1 — type keyword
        issues = validate_entity("main-rite", {**CANONICAL_MAIN_RITE, "summary": 123})
        assert "type" in _rules(issues)

    def test_empty_nodes_fails_min_items(self):
        # transient-rites-us-1 — minItems on nodes
        issues = validate_entity("main-rite", {**CANONICAL_MAIN_RITE, "nodes": []})
        assert "minItems" in _rules(issues)

    def test_empty_title_fails_min_length(self):
        # transient-rites-us-1 — minLength on string fields
        issues = validate_entity("main-rite", {**CANONICAL_MAIN_RITE, "title": ""})
        assert "minLength" in _rules(issues)

    def test_node_with_both_do_and_use_rejected(self):
        # transient-rites-us-1 — node not:{required:[do,use]} (do-XOR-use)
        bad = {
            **CANONICAL_MAIN_RITE,
            "nodes": [{"id": "n", "do": "x", "use": "y", "then": "done"}],
            "conclusions": {"done": {"audience": "a", "response": "r"}},
        }
        assert validate_entity("main-rite", bad) != []

    def test_node_with_neither_do_nor_use_rejected(self):
        # transient-rites-us-1 — node anyOf:[{required:[do]},{required:[use]}]
        bad = {
            **CANONICAL_MAIN_RITE,
            "nodes": [{"id": "n", "then": "done"}],
            "conclusions": {"done": {"audience": "a", "response": "r"}},
        }
        assert validate_entity("main-rite", bad) != []


class TestSharedStepSchemaHappy:
    def test_canonical_shared_step_validates_clean(self):
        # transient-rites-us-1 — pure procedure (id, title, do) validates clean
        assert validate_entity("shared-step", CANONICAL_SHARED_STEP) == []


class TestSharedStepSchemaViolations:
    def test_then_key_fails_additional_properties(self):
        # transient-rites-us-1 — branching key 'then' rejected (pure-step rule)
        issues = validate_entity("shared-step", {**CANONICAL_SHARED_STEP, "then": "next"})
        assert "additionalProperties" in _rules(issues)

    def test_nodes_key_fails_additional_properties(self):
        issues = validate_entity("shared-step", {**CANONICAL_SHARED_STEP, "nodes": []})
        assert "additionalProperties" in _rules(issues)

    def test_conclusions_key_fails_additional_properties(self):
        issues = validate_entity("shared-step", {**CANONICAL_SHARED_STEP, "conclusions": {}})
        assert "additionalProperties" in _rules(issues)

    def test_missing_do_fails_required(self):
        # transient-rites-us-1 — required do
        issues = validate_entity("shared-step", _drop_key(CANONICAL_SHARED_STEP, "do"))
        assert "required" in _rules(issues)

    def test_missing_summary_fails_required(self):
        # tech-arch-frontmatter — summary required on every entity, shared step included
        issues = validate_entity("shared-step", _drop_key(CANONICAL_SHARED_STEP, "summary"))
        assert "required" in _rules(issues)

    def test_empty_summary_fails_min_length(self):
        issues = validate_entity("shared-step", {**CANONICAL_SHARED_STEP, "summary": ""})
        assert "minLength" in _rules(issues)


# ---------------------------------------------------------------------------
# Codex `rites:` frontmatter field + rite link-direction (transient-rites-us-5)
# Anchors:
#   tech-arch-schemas — validate_entity against codex-frontmatter; the new
#     `rites:` property is an array of unique non-empty strings (no path-pattern
#     `not.anyOf` rules — rite ids are plain slugs). additionalProperties:false
#     rejects it until added (KNOWN FINDING, Scout).
#   decisions-014-link-direction — codex → rite is the only rite edge; the rite
#     schemas reject `related`/`binds` via their own additionalProperties:false
#     (constraint 1).
# ---------------------------------------------------------------------------


CODEX_FM = {"id": "ops-refunds", "title": "Refunds", "summary": "s"}


def _keyword_for(issues, pointer):
    """Return the rule of the first issue whose pointer targets `pointer`."""
    for i in issues:
        if i.pointer == pointer or i.pointer.startswith(pointer):
            return i.rule
    return None


class TestCodexRitesSchemaAccepts:
    """A well-formed `rites:` array validates clean (absent == [])."""

    def test_accepts_array_of_unique_nonempty_strings(self):
        # tech-arch-schemas — happy path: rites: [a, b] is valid
        assert validate_entity("codex-frontmatter", {**CODEX_FM, "rites": ["a", "b"]}) == []

    def test_accepts_single_rite_id(self):
        assert validate_entity(
            "codex-frontmatter", {**CODEX_FM, "rites": ["issue-refund"]}
        ) == []

    def test_accepts_empty_rites_list(self):
        # absent and [] behave identically (additive, backward-compatible)
        assert validate_entity("codex-frontmatter", {**CODEX_FM, "rites": []}) == []

    def test_accepts_absent_rites_field(self):
        # backward-compatible: a doc with no rites: validates clean
        assert validate_entity("codex-frontmatter", {**CODEX_FM}) == []


class TestCodexRitesSchemaRejects:
    """Malformed `rites:` fires the named JSON-Schema rule on /rites."""

    def test_rejects_non_array_with_type_rule(self):
        # tech-arch-schemas — rites: scalar -> type rule on /rites
        issues = validate_entity("codex-frontmatter", {**CODEX_FM, "rites": "x"})
        assert _keyword_for(issues, "/rites") == "type"

    def test_rejects_mapping_with_type_rule(self):
        issues = validate_entity("codex-frontmatter", {**CODEX_FM, "rites": {"a": "b"}})
        assert _keyword_for(issues, "/rites") == "type"

    def test_rejects_duplicates_with_unique_items_rule(self):
        issues = validate_entity("codex-frontmatter", {**CODEX_FM, "rites": ["a", "a"]})
        assert any(i.rule == "uniqueItems" for i in issues), _rules(issues)

    def test_rejects_empty_string_item_with_min_length_rule(self):
        issues = validate_entity("codex-frontmatter", {**CODEX_FM, "rites": [""]})
        assert any(i.rule == "minLength" for i in issues), _rules(issues)


class TestCodexRitesNoPathPatternRules:
    """`rites:` ids are plain slugs — unlike `binds:`, the path-pattern
    `not.anyOf` rules (absolute / `..`) MUST NOT be applied. A slug that would
    be rejected as a binds path validates clean as a rite id."""

    def test_slug_that_looks_like_relative_path_is_accepted(self):
        # rite ids are slugs; the binds-only `..`/leading-slash bans do not apply
        assert validate_entity(
            "codex-frontmatter", {**CODEX_FM, "rites": ["issue-refund"]}
        ) == []


class TestSharedStepRejectsOutboundLinks:
    """decisions-014-link-direction constraint 1: the shared-step schema rejects
    `related`/`binds` via its own additionalProperties:false (no extra rule).
    Mirrors the main-rite assertions already pinned above."""

    def test_related_root_key_rejected(self):
        issues = validate_entity(
            "shared-step", {**CANONICAL_SHARED_STEP, "related": ["x"]}
        )
        assert "additionalProperties" in _rules(issues)

    def test_binds_root_key_rejected(self):
        issues = validate_entity(
            "shared-step", {**CANONICAL_SHARED_STEP, "binds": ["x"]}
        )
        assert "additionalProperties" in _rules(issues)


# ---------------------------------------------------------------------------
# Packaged data kinds — agents registry + skill catalogue.
#
# Both describe files that ship inside the wheel, so neither is overlayable:
# validation goes through load_schema, never through resolve_merged_schema
# (decisions-018-overlays-are-path-discovered-config).
# ---------------------------------------------------------------------------


PACKAGED_DATA_KINDS = ["agents", "skill-catalogue"]


class TestPackagedDataSchemaKinds:
    def test_each_kind_loads_as_a_draft_2020_schema(self):
        for kind in PACKAGED_DATA_KINDS:
            schema = load_schema(kind)
            assert isinstance(schema, dict), f"{kind}: expected dict"
            assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"

    def test_each_kind_carries_the_canonical_id(self):
        for kind in PACKAGED_DATA_KINDS:
            assert load_schema(kind)["$id"] == f"lore://schemas/{kind}"

    def test_each_kind_pins_additional_properties_false_somewhere(self):
        for kind in PACKAGED_DATA_KINDS:
            found = any(
                node.get("additionalProperties") is False
                for node in _walk_objects(load_schema(kind))
            )
            assert found, f"{kind}: no 'additionalProperties: false' survived load"

    def test_each_kind_ships_as_a_package_resource(self):
        names = {p.name for p in files("lore.schemas").iterdir()}
        for kind in PACKAGED_DATA_KINDS:
            assert f"{kind}.yaml" in names, f"missing packaged resource: {kind}.yaml"

    def test_neither_kind_is_registered_as_overlayable(self):
        from lore.schemas import _OVERLAY_KINDS

        for kind in PACKAGED_DATA_KINDS:
            assert kind not in _OVERLAY_KINDS, (
                f"{kind} describes a file inside the wheel — a project must not be able "
                "to change how it validates"
            )
