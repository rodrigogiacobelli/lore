"""Unit tests for lore.health schema-validation walker (_check_schemas).

US-004 Red — schema-validation-us-004
Workflow: conceptual-workflows-health (lore codex show conceptual-workflows-health)

These tests define the behavior of `_check_schemas` and its integration with
`health_check`. Production code does not exist yet — every test MUST fail
(import errors count as red).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lore.health import _ALL_SCOPES, _check_schemas, health_check
from lore.models import HealthIssue


# ---------------------------------------------------------------------------
# Helpers for building per-kind bad files
# ---------------------------------------------------------------------------


def _make_lore_skeleton(root: Path) -> Path:
    lore = root / ".lore"
    for d in ("knights", "doctrines", "codex", "artifacts", "watchers"):
        (lore / d).mkdir(parents=True, exist_ok=True)
    return root


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_bad_knight(root: Path) -> Path:
    """Knight with hallucinated `stability` field (additionalProperties)."""
    p = (
        root
        / ".lore"
        / "knights"
        / "default"
        / "feature-implementation"
        / "pm.md"
    )
    _write(
        p,
        "---\n"
        "id: pm\n"
        "title: Product Manager\n"
        "summary: Writes PRDs.\n"
        "stability: experimental\n"
        "---\n"
        "# Body\n",
    )
    return p


def _write_multi_bad_knight(root: Path) -> Path:
    """Knight missing title+summary AND with unknown `stability` field."""
    p = (
        root
        / ".lore"
        / "knights"
        / "default"
        / "feature-implementation"
        / "pm.md"
    )
    _write(
        p,
        "---\n"
        "id: pm\n"
        "stability: x\n"
        "---\n"
        "# Body\n",
    )
    return p


def _write_bad_doctrine_yaml(root: Path) -> Path:
    p = (
        root
        / ".lore"
        / "doctrines"
        / "default"
        / "broken"
        / "broken.yaml"
    )
    _write(
        p,
        "id: broken\n"
        "title: Broken\n"
        "summary: bad\n"
        "bogus_top_level: nope\n"
        "steps: []\n",
    )
    return p


def _write_bad_doctrine_design(root: Path) -> Path:
    p = (
        root
        / ".lore"
        / "doctrines"
        / "default"
        / "broken"
        / "broken.design.md"
    )
    _write(
        p,
        "---\n"
        "id: broken\n"
        "title: Broken\n"
        "bogus: yes\n"
        "---\n"
        "Body.\n",
    )
    return p


def _write_bad_watcher(root: Path) -> Path:
    p = root / ".lore" / "watchers" / "default" / "bad.yaml"
    _write(
        p,
        "id: bad\n"
        "title: Bad\n"
        "event: quest_close\n"
        "action: 'doctrine: missing'\n"
        "bogus: yes\n",
    )
    return p


def _write_bad_codex(root: Path) -> Path:
    p = root / ".lore" / "codex" / "bad-doc.md"
    _write(
        p,
        "---\n"
        "id: bad-doc\n"
        "title: Bad\n"
        "summary: x\n"
        "bogus: yes\n"
        "---\n"
        "Body.\n",
    )
    return p


def _write_bad_artifact(root: Path) -> Path:
    p = root / ".lore" / "artifacts" / "default" / "group" / "fi-bad.md"
    _write(
        p,
        "---\n"
        "id: fi-bad\n"
        "title: Bad\n"
        "summary: x\n"
        "bogus: yes\n"
        "---\n"
        "Body.\n",
    )
    return p


def _write_frontmatterless_artifact(root: Path) -> Path:
    p = root / ".lore" / "artifacts" / "default" / "group" / "broken.md"
    _write(p, "No frontmatter at all.\n")
    return p


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_project_with_bad_knight(tmp_path):
    _make_lore_skeleton(tmp_path)
    _write_bad_knight(tmp_path)
    return tmp_path


@pytest.fixture()
def tmp_project_with_multi_bad_knight(tmp_path):
    _make_lore_skeleton(tmp_path)
    _write_multi_bad_knight(tmp_path)
    return tmp_path


@pytest.fixture()
def tmp_project_with_bad_file_per_kind(tmp_path):
    _make_lore_skeleton(tmp_path)
    _write_bad_knight(tmp_path)
    _write_bad_doctrine_yaml(tmp_path)
    _write_bad_doctrine_design(tmp_path)
    _write_bad_watcher(tmp_path)
    _write_bad_codex(tmp_path)
    _write_bad_artifact(tmp_path)
    return tmp_path


@pytest.fixture()
def tmp_project_without_watchers(tmp_path):
    lore = tmp_path / ".lore"
    for d in ("knights", "doctrines", "codex", "artifacts"):
        (lore / d).mkdir(parents=True, exist_ok=True)
    _write_bad_knight(tmp_path)
    return tmp_path


@pytest.fixture()
def tmp_project_with_frontmatterless_artifact(tmp_path):
    _make_lore_skeleton(tmp_path)
    _write_frontmatterless_artifact(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# _ALL_SCOPES — FR-12 default on
# ---------------------------------------------------------------------------


def test_schemas_in_all_scopes_list():
    """conceptual-workflows-health — FR-12: schemas runs by default."""
    assert "schemas" in _ALL_SCOPES


def test_schemas_is_last_in_all_scopes():
    """Tech Notes: schemas registered last — schema errors are fail-loud."""
    assert _ALL_SCOPES[-1] == "schemas"


# ---------------------------------------------------------------------------
# _check_schemas — walker + glob coverage + kind labels
# ---------------------------------------------------------------------------


def test_check_schemas_walks_every_entity_dir(tmp_project_with_bad_file_per_kind):
    """conceptual-workflows-health — FR-1..FR-6: every kind covered."""
    issues = _check_schemas(tmp_project_with_bad_file_per_kind)
    kinds = sorted({i.entity_type for i in issues})
    assert kinds == [
        "artifact",
        "codex",
        "doctrine-design-frontmatter",
        "doctrine-yaml",
        "knight",
        "watcher",
    ]


def test_check_schemas_every_entity_type_is_documented_label(
    tmp_project_with_bad_file_per_kind,
):
    """Every violation's entity_type is one of the six documented kind strings."""
    allowed = {
        "doctrine-yaml",
        "doctrine-design-frontmatter",
        "knight",
        "watcher",
        "codex",
        "artifact",
    }
    issues = _check_schemas(tmp_project_with_bad_file_per_kind)
    assert issues, "expected at least one issue per kind"
    for issue in issues:
        assert issue.entity_type in allowed


def test_check_schemas_issue_shape(tmp_project_with_bad_knight):
    """Each HealthIssue carries check, severity, entity_type, schema_id, rule, pointer."""
    issues = _check_schemas(tmp_project_with_bad_knight)
    assert len(issues) == 1
    issue = issues[0]
    assert issue.check == "schema"
    assert issue.severity == "error"
    assert issue.entity_type == "knight"
    assert issue.schema_id == "lore://schemas/knight-frontmatter"
    assert issue.rule == "additionalProperties"
    assert issue.pointer == "/stability"
    assert issue.id.startswith(".lore/knights/")


def test_check_schemas_multi_violation_not_aggregated(
    tmp_project_with_multi_bad_knight,
):
    """conceptual-workflows-health — FR-9: N violations → N distinct records."""
    issues = _check_schemas(tmp_project_with_multi_bad_knight)
    assert len(issues) == 3
    rules = [i.rule for i in issues]
    assert rules.count("required") == 2
    assert rules.count("additionalProperties") == 1


def test_check_schemas_missing_dir_is_noop(tmp_project_without_watchers):
    """conceptual-workflows-health — absent entity root is a silent no-op."""
    issues = _check_schemas(tmp_project_without_watchers)
    assert all(i.entity_type != "watcher" for i in issues)


def test_check_schemas_relative_paths_posix(tmp_project_with_bad_knight):
    """HealthIssue.id is POSIX-style relpath from project root."""
    issues = _check_schemas(tmp_project_with_bad_knight)
    assert len(issues) == 1
    assert "\\" not in issues[0].id
    assert issues[0].id == ".lore/knights/default/feature-implementation/pm.md"


def test_check_schemas_frontmatterless_artifact_is_loud(
    tmp_project_with_frontmatterless_artifact,
):
    """FR-25: previously silent artifact skip is now a loud error."""
    issues = _check_schemas(tmp_project_with_frontmatterless_artifact)
    assert len(issues) == 1
    assert issues[0].rule == "missing-frontmatter"
    assert issues[0].entity_type == "artifact"
    assert issues[0].pointer == "/"


def test_check_schemas_clean_skeleton_no_issues(tmp_path):
    """Empty (but existing) entity dirs yield no schema issues."""
    _make_lore_skeleton(tmp_path)
    assert _check_schemas(tmp_path) == []


# ---------------------------------------------------------------------------
# health_check — default path includes schemas; scoped path can exclude it
# ---------------------------------------------------------------------------


def test_health_check_default_runs_schemas(tmp_project_with_bad_knight):
    """conceptual-workflows-health — FR-12: default run includes schemas."""
    report = health_check(project_root=tmp_project_with_bad_knight)
    assert any(i.check == "schema" for i in report.issues)


def test_health_check_scope_references_skips_schemas(tmp_project_with_bad_knight):
    """Scoped run without `schemas` emits no schema issues."""
    report = health_check(
        project_root=tmp_project_with_bad_knight,
        scopes=["codex"],
    )
    assert all(i.check != "schema" for i in report.issues)


def test_health_check_scope_schemas_only_runs_schemas(
    tmp_project_with_bad_file_per_kind,
):
    """scopes=['schemas'] runs only the schema walker."""
    report = health_check(
        project_root=tmp_project_with_bad_file_per_kind,
        scopes=["schemas"],
    )
    assert report.issues
    assert all(i.check == "schema" for i in report.issues)


def test_health_check_schema_issues_populate_has_errors(
    tmp_project_with_bad_knight,
):
    """Schema errors trip report.has_errors."""
    report = health_check(project_root=tmp_project_with_bad_knight)
    assert report.has_errors is True


# ---------------------------------------------------------------------------
# US-006 — fail-loud walker: yaml-parse / missing-frontmatter / read-failed
# schema-validation-us-006 — FR-10, FR-11, FR-25, NFR-Reliability
# ---------------------------------------------------------------------------


def _write_broken_watcher(root: Path) -> Path:
    p = root / ".lore" / "watchers" / "default" / "broken.yaml"
    _write(p, "watch_target: : :")
    return p


def _write_good_watcher(root: Path) -> Path:
    p = root / ".lore" / "watchers" / "default" / "good.yaml"
    _write(
        p,
        "id: good\n"
        "title: Good\n"
        "summary: ok\n"
        "watch_target:\n  - src/\n"
        "interval: on_merge\n"
        "action:\n  - doctrine: d\n",
    )
    return p


@pytest.fixture()
def tmp_project_broken_and_good_watcher(tmp_path):
    _make_lore_skeleton(tmp_path)
    _write_broken_watcher(tmp_path)
    _write_good_watcher(tmp_path)
    return tmp_path


@pytest.fixture()
def tmp_project_orphan_codex(tmp_path):
    _make_lore_skeleton(tmp_path)
    p = tmp_path / ".lore" / "codex" / "notes" / "orphan.md"
    _write(p, "just some notes\n")
    return tmp_path


def test_check_schemas_yaml_parse_does_not_abort_scan(
    tmp_project_broken_and_good_watcher,
):
    """NFR-Reliability: one broken watcher never prevents the good one from being visited."""
    issues = _check_schemas(tmp_project_broken_and_good_watcher)
    yaml_parse = [i for i in issues if i.rule == "yaml-parse"]
    assert len(yaml_parse) == 1
    assert yaml_parse[0].id.endswith("broken.yaml")
    # Good watcher produced no issues (it parses cleanly and validates).
    good_issues = [i for i in issues if i.id.endswith("good.yaml")]
    assert good_issues == []


def test_check_schemas_yaml_parse_single_issue_per_file(
    tmp_project_broken_and_good_watcher,
):
    """FR-10: exactly one ERROR for broken.yaml — no stray required/additionalProperties."""
    issues = _check_schemas(tmp_project_broken_and_good_watcher)
    broken = [i for i in issues if i.id.endswith("broken.yaml")]
    assert len(broken) == 1
    assert broken[0].rule == "yaml-parse"


def test_check_schemas_missing_frontmatter_exact_message(tmp_project_orphan_codex):
    """FR-11: exact message (no trailing period) for missing frontmatter."""
    issues = _check_schemas(tmp_project_orphan_codex)
    mf = [i for i in issues if i.rule == "missing-frontmatter"]
    assert len(mf) == 1
    assert mf[0].pointer == "/"
    assert mf[0].detail == "File has no YAML frontmatter block"


def test_check_schemas_failure_modes_are_errors_with_check_schema(tmp_path):
    """FR-7: yaml-parse, missing-frontmatter, and read-failed each surface as
    HealthIssue(check='schema', severity='error')."""
    _make_lore_skeleton(tmp_path)
    # yaml-parse
    _write(tmp_path / ".lore" / "watchers" / "default" / "bad.yaml", "a: : :")
    # missing-frontmatter
    _write(tmp_path / ".lore" / "codex" / "orph.md", "plain body\n")
    issues = _check_schemas(tmp_path)
    rules = {i.rule for i in issues}
    assert "yaml-parse" in rules
    assert "missing-frontmatter" in rules
    for i in issues:
        if i.rule in ("yaml-parse", "missing-frontmatter", "read-failed"):
            assert i.check == "schema"
            assert i.severity == "error"


def test_check_schemas_unexpected_exception_becomes_read_failed(
    tmp_project_with_bad_knight, monkeypatch
):
    """NFR-Reliability safety net: any unexpected per-file exception becomes
    a read-failed HealthIssue rather than aborting the walk."""
    import lore.health as health_mod

    def boom(path, kind):
        raise RuntimeError("kaboom-" + str(path))

    monkeypatch.setattr(health_mod, "_load_schema_payload", boom, raising=False)

    # Even with the loader blown up, _check_schemas must not raise.
    issues = _check_schemas(tmp_project_with_bad_knight)
    assert any(i.rule == "read-failed" for i in issues), (
        "expected defensive read-failed wrapper to catch RuntimeError"
    )
    rf = [i for i in issues if i.rule == "read-failed"][0]
    assert rf.check == "schema"
    assert rf.severity == "error"
    assert "kaboom" in rf.detail


def test_check_schemas_unreadable_file_emits_read_failed(tmp_path, monkeypatch):
    """PermissionError on read becomes one read-failed HealthIssue with 'Permission denied'."""
    _make_lore_skeleton(tmp_path)
    p = tmp_path / ".lore" / "knights" / "default" / "locked" / "pm.md"
    _write(p, "---\nid: pm\ntitle: PM\nsummary: s\n---\n")

    real_read_bytes = Path.read_bytes
    real_read_text = Path.read_text
    real_open = open

    def boom_read_text(self, *a, **kw):
        if self == p:
            raise PermissionError("Permission denied")
        return real_read_text(self, *a, **kw)

    def boom_read_bytes(self, *a, **kw):
        if self == p:
            raise PermissionError("Permission denied")
        return real_read_bytes(self, *a, **kw)

    def boom_open(path, *a, **kw):
        if str(path) == str(p):
            raise PermissionError("Permission denied")
        return real_open(path, *a, **kw)

    monkeypatch.setattr(Path, "read_text", boom_read_text)
    monkeypatch.setattr(Path, "read_bytes", boom_read_bytes)
    monkeypatch.setattr("builtins.open", boom_open)

    issues = _check_schemas(tmp_path)
    rf = [i for i in issues if i.rule == "read-failed"]
    assert len(rf) == 1
    assert rf[0].check == "schema"
    assert rf[0].severity == "error"
    assert rf[0].pointer == "/"
    assert "Permission denied" in rf[0].detail


# ---------------------------------------------------------------------------
# US-005 — single-file (no-`*`) glob branch in _check_schemas
# Spec: glossary-us-005 (lore codex show glossary-us-005)
# Workflow: conceptual-workflows-health
#
# When a `_SCHEMA_KINDS` row's glob has no `*` characters, _check_schemas
# treats it as a literal filename validated only via
# `(project_root / ".lore" / root_name / glob).is_file()` (no rglob walk).
# This is how the new `glossary` row points at exactly
# `.lore/codex/glossary.yaml`.
# ---------------------------------------------------------------------------


def test_check_schemas_literal_filename_glob(tmp_path):
    """Unit row 19 — a no-`*` glob is validated as a single literal file.

    A malformed glossary at the literal `.lore/codex/glossary.yaml` path must
    surface a schema error from `_check_schemas`, proving the no-`*` glob
    branch routed the literal filename through validation (not via rglob,
    which would also walk the codex tree picking up `.md` files unrelated to
    the glossary kind).
    """
    _make_lore_skeleton(tmp_path)
    target = tmp_path / ".lore" / "codex" / "glossary.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    # Missing required `definition` — forces a schema-required error.
    target.write_text("items:\n  - keyword: Mission\n", encoding="utf-8")

    issues = _check_schemas(tmp_path)

    glossary_schema = [
        i for i in issues if i.entity_type == "glossary" and i.check == "schema"
    ]
    assert len(glossary_schema) >= 1
    assert glossary_schema[0].schema_id == "lore://schemas/glossary"
    assert glossary_schema[0].id.endswith("glossary.yaml")
