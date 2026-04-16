"""Unit tests for lore.artifact.scan_artifacts with filter_groups parameter.

Spec: filter-list-subcommands-us-3 (lore codex show filter-list-subcommands-us-3)
Workflow: conceptual-workflows-filter-list
"""

from lore.artifact import scan_artifacts


# ---------------------------------------------------------------------------
# Fixtures — artifact file content
# ---------------------------------------------------------------------------

ROOT_ARTIFACT_MD = """\
---
id: root-artifact
title: Root Artifact
summary: A root-level artifact.
---

Root body.
"""

DEFAULT_ARTIFACT_MD = """\
---
id: some-artifact
title: Some Artifact
summary: An artifact in the default group.
---

Default body.
"""

CODEX_ARTIFACT_MD = """\
---
id: fi-user-story
title: FI User Story
summary: A user story artifact in the default/codex namespace.
---

Codex body.
"""

TRANSIENT_ARTIFACT_MD = """\
---
id: scratch
title: Scratch
summary: A transient artifact.
---

Transient body.
"""

INVALID_FRONTMATTER_MD = """\
---
title: Missing ID
summary: This file has no id field.
---

Invalid body.
"""


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _setup_artifacts(artifacts_dir):
    """Populate artifacts_dir with test fixtures covering root, default, default-codex, default-transient."""
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "root-artifact.md").write_text(ROOT_ARTIFACT_MD)
    (artifacts_dir / "default").mkdir()
    (artifacts_dir / "default" / "some-artifact.md").write_text(DEFAULT_ARTIFACT_MD)
    codex_dir = artifacts_dir / "default" / "codex"
    codex_dir.mkdir()
    (codex_dir / "fi-user-story.md").write_text(CODEX_ARTIFACT_MD)
    transient_dir = artifacts_dir / "default" / "transient"
    transient_dir.mkdir()
    (transient_dir / "scratch.md").write_text(TRANSIENT_ARTIFACT_MD)


# ---------------------------------------------------------------------------
# Unit — scan_artifacts filter_groups=["default/codex"] returns default-codex + root only
# Exercises: conceptual-workflows-filter-list step 3 (_apply_filter on artifact records)
# ---------------------------------------------------------------------------


def test_scan_artifacts_filter_returns_matched_group_and_root(tmp_path):
    """scan_artifacts with filter_groups=["default/codex"] returns default-codex and root-level artifacts only."""
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    _setup_artifacts(artifacts_dir)

    results = scan_artifacts(artifacts_dir, filter_groups=["default/codex"])

    ids = [r["id"] for r in results]
    assert "root-artifact" in ids
    assert "fi-user-story" in ids
    assert "some-artifact" not in ids
    assert "scratch" not in ids


# ---------------------------------------------------------------------------
# Unit — scan_artifacts filter — valid count reflects filtered set only (FR-12)
# Exercises: conceptual-workflows-filter-list step 4 (valid/invalid counts on filtered output)
# ---------------------------------------------------------------------------


def test_scan_artifacts_filter_valid_count_reflects_filtered_set(tmp_path):
    """scan_artifacts with filter returns fewer records than without filter."""
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    _setup_artifacts(artifacts_dir)

    all_results = scan_artifacts(artifacts_dir)
    filtered_results = scan_artifacts(artifacts_dir, filter_groups=["default/codex"])

    assert len(filtered_results) < len(all_results)
    assert len(filtered_results) == 2  # root-artifact + fi-user-story


# ---------------------------------------------------------------------------
# Unit — scan_artifacts filter — strict-skip of invalid frontmatter unaffected
# Exercises: conceptual-workflows-filter-list step 1 (discovery unchanged) + artifact-list step 3
# ---------------------------------------------------------------------------


def test_scan_artifacts_filter_invalid_frontmatter_skip_unaffected(tmp_path):
    """Invalid frontmatter files in other groups are still skipped when filter is applied."""
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    _setup_artifacts(artifacts_dir)
    # Add an invalid file in the "default" group — it should be skipped regardless of filter
    (artifacts_dir / "default" / "invalid-no-id.md").write_text(INVALID_FRONTMATTER_MD)

    results = scan_artifacts(artifacts_dir, filter_groups=["default/codex"])

    ids = [r["id"] for r in results]
    # Invalid file should not appear (skipped due to missing id)
    assert "invalid-no-id" not in ids
    # The filter still returns root + codex files
    assert "root-artifact" in ids
    assert "fi-user-story" in ids


# ---------------------------------------------------------------------------
# US-4: scan_artifacts filter_groups=None — backward compatibility (no regression)
# Spec: filter-list-subcommands-us-4 (lore codex show filter-list-subcommands-us-4)
# Exercises: conceptual-workflows-filter-list step 3 (filter_groups=None → return all)
# ---------------------------------------------------------------------------


# Unit — scan_artifacts filter_groups=None returns all artifacts (no regression)
# Exercises: conceptual-workflows-filter-list step 3 (filter_groups=None → return all)
def test_scan_artifacts_filter_none_no_regression(tmp_path):
    """scan_artifacts with filter_groups=None returns all artifacts across all groups — pre-filter behavior."""
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    _setup_artifacts(artifacts_dir)

    results = scan_artifacts(artifacts_dir, filter_groups=None)

    ids = [r["id"] for r in results]
    assert "root-artifact" in ids
    assert "some-artifact" in ids
    assert "fi-user-story" in ids
    assert "scratch" in ids


# Unit — scan_artifacts called without filter_groups returns all artifacts (backward compat)
# Exercises: backward compat — old callers that never passed filter_groups still work
def test_scan_artifacts_no_filter_argument_returns_all(tmp_path):
    """scan_artifacts called without filter_groups (default) returns all artifacts — backward compatible."""
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    _setup_artifacts(artifacts_dir)

    results = scan_artifacts(artifacts_dir)

    ids = [r["id"] for r in results]
    assert "root-artifact" in ids
    assert "some-artifact" in ids
    assert "fi-user-story" in ids
    assert "scratch" in ids


# ---------------------------------------------------------------------------
# US-004: create_artifact unit matrix
# Spec: group-param-us-004 (lore codex show group-param-us-004)
# anchor: conceptual-workflows-artifact-list (first write path)
# ---------------------------------------------------------------------------

import inspect

import pytest
from click.testing import CliRunner

from lore.cli import main

_VALID_BODY = "---\nid: a\ntitle: T\nsummary: s\n---\nbody\n"


def _import_create_artifact():
    """Import create_artifact lazily — fails red until US-004 Green lands."""
    from lore.artifact import create_artifact

    return create_artifact


@pytest.fixture()
def create_artifact():
    """Lazy import — test errors red until US-004 Green adds the function."""
    return _import_create_artifact()


class TestCreateArtifact:
    """Unit matrix for lore.artifact.create_artifact — US-004."""

    def test_signature_group_is_kwarg_only_with_none_default(self, create_artifact):
        # AC unit: signature `(artifacts_dir, name, content, *, group=None) -> dict`
        sig = inspect.signature(create_artifact)
        assert sig.parameters["group"].kind is inspect.Parameter.KEYWORD_ONLY
        assert sig.parameters["group"].default is None

    def test_group_none_writes_to_artifacts_dir_root(self, create_artifact, tmp_path):
        # AC unit: group=None writes to artifacts_dir / "<name>.md"
        create_artifact(tmp_path, "a", _VALID_BODY)
        assert (tmp_path / "a.md").exists()

    def test_group_nested_writes_to_subdir_with_auto_mkdir(
        self, create_artifact, tmp_path
    ):
        # AC unit: group="a/b" auto-creates intermediate dirs
        create_artifact(tmp_path, "a", _VALID_BODY, group="a/b")
        assert (tmp_path / "a" / "b" / "a.md").exists()

    def test_duplicate_stem_anywhere_in_subtree_raises(
        self, create_artifact, tmp_path
    ):
        # AC unit: rglob duplicate check
        (tmp_path / "x").mkdir()
        (tmp_path / "x" / "a.md").write_text(_VALID_BODY)
        with pytest.raises(ValueError, match="already exists"):
            create_artifact(tmp_path, "a", _VALID_BODY, group="y")

    def test_missing_required_frontmatter_summary_raises(
        self, create_artifact, tmp_path
    ):
        # AC unit: strict frontmatter — missing 'summary'
        bad = "---\nid: a\ntitle: T\n---\nbody\n"
        with pytest.raises(ValueError, match="summary"):
            create_artifact(tmp_path, "a", bad)

    def test_missing_required_frontmatter_id_raises(self, create_artifact, tmp_path):
        # AC unit: strict frontmatter — missing 'id'
        bad = "---\ntitle: T\nsummary: s\n---\nbody\n"
        with pytest.raises(ValueError, match="id"):
            create_artifact(tmp_path, "a", bad)

    def test_missing_required_frontmatter_title_raises(
        self, create_artifact, tmp_path
    ):
        # AC unit: strict frontmatter — missing 'title'
        bad = "---\nid: a\nsummary: s\n---\nbody\n"
        with pytest.raises(ValueError, match="title"):
            create_artifact(tmp_path, "a", bad)

    def test_return_dict_contains_required_keys(self, create_artifact, tmp_path):
        # AC unit: return dict has id, group, filename, path
        result = create_artifact(tmp_path, "a", _VALID_BODY, group="a/b")
        assert set(result.keys()) >= {"id", "group", "filename", "path"}
        assert result["id"] == "a"
        assert result["group"] == "a/b"
        assert result["filename"] == "a.md"
        assert "a/b/a.md" in result["path"]

    def test_return_dict_group_none_when_flat(self, create_artifact, tmp_path):
        # AC unit: return dict group key is None when group omitted
        result = create_artifact(tmp_path, "a", _VALID_BODY)
        assert result["group"] is None

    def test_invalid_group_rejected_before_filesystem_write(
        self, create_artifact, tmp_path
    ):
        # AC unit: validate_group failure raises before any write
        with pytest.raises(ValueError):
            create_artifact(tmp_path, "a", _VALID_BODY, group="../escape")
        assert not any(tmp_path.rglob("*.md"))


# ---------------------------------------------------------------------------
# US-004: CLI thin-wrapper smoke — artifact_new forwards --group kwarg
# anchor: decisions-011-api-parity-with-cli
# ---------------------------------------------------------------------------


class TestCliArtifactNewThinWrapper:
    """Smoke: CLI handler delegates to create_artifact with parsed --group."""

    def test_cli_artifact_new_forwards_group_kwarg(self, monkeypatch, tmp_path):
        # AC unit: CLI wrapper passes --group value unchanged to create_artifact
        captured = {}

        def fake_create(artifacts_dir, name, content, *, group=None):
            captured["name"] = name
            captured["group"] = group
            captured["content"] = content
            return {
                "id": name,
                "group": group,
                "filename": f"{name}.md",
                "path": f".lore/artifacts/{name}.md",
            }

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        runner.invoke(main, ["init"])
        monkeypatch.setattr("lore.artifact.create_artifact", fake_create)
        monkeypatch.setattr("lore.cli.create_artifact", fake_create, raising=False)

        (tmp_path / "b.md").write_text(_VALID_BODY)
        result = runner.invoke(
            main, ["artifact", "new", "a", "--group", "x/y", "--from", "b.md"]
        )
        assert result.exit_code == 0
        assert captured["group"] == "x/y"
        assert captured["name"] == "a"

    def test_cli_artifact_new_forwards_group_none_when_flag_omitted(
        self, monkeypatch, tmp_path
    ):
        # AC unit: --group omitted → create_artifact called with group=None
        captured = {}

        def fake_create(artifacts_dir, name, content, *, group=None):
            captured["group"] = group
            return {
                "id": name,
                "group": group,
                "filename": f"{name}.md",
                "path": f".lore/artifacts/{name}.md",
            }

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        runner.invoke(main, ["init"])
        monkeypatch.setattr("lore.artifact.create_artifact", fake_create)
        monkeypatch.setattr("lore.cli.create_artifact", fake_create, raising=False)

        (tmp_path / "b.md").write_text(_VALID_BODY)
        result = runner.invoke(main, ["artifact", "new", "a", "--from", "b.md"])
        assert result.exit_code == 0
        assert captured["group"] is None


# ---------------------------------------------------------------------------
# US-010 — Artifact create-time validator delegates to lore.schemas
# Spec: schema-validation-us-010
# Workflow: conceptual-workflows-artifact-new
# ---------------------------------------------------------------------------


import click  # noqa: E402

import lore.artifact as _a_mod  # noqa: E402
import lore.schemas as _schemas  # noqa: E402


def test_us010_artifact_create_validator_delegates(monkeypatch):
    """artifact._validate_frontmatter delegates to validate_entity("artifact-frontmatter", data)."""
    kinds = []

    def spy(kind, data):
        kinds.append(kind)
        return []

    monkeypatch.setattr(_schemas, "validate_entity", spy)
    if hasattr(_a_mod, "validate_entity"):
        monkeypatch.setattr(_a_mod, "validate_entity", spy)

    _a_mod._validate_frontmatter({"id": "x", "title": "T", "summary": "s"})
    assert kinds == ["artifact-frontmatter"]


def test_us010_artifact_create_validator_rejects_group_key():
    """A frontmatter dict carrying 'group' must be rejected by additionalProperties."""
    with pytest.raises(click.ClickException) as exc:
        _a_mod._validate_frontmatter({"id": "x", "title": "T", "summary": "s", "group": "foo"})
    msg = str(exc.value.message)
    assert ("additionalProperties" in msg) or ("/group" in msg) or ("group" in msg and "Unknown property" in msg)


def test_us010_artifact_create_validator_raises_click_on_issues(monkeypatch):
    issue = _schemas.SchemaIssue(rule="required", pointer="/", message="Missing required property 'summary'.")
    monkeypatch.setattr(_schemas, "validate_entity", lambda k, d: [issue])
    if hasattr(_a_mod, "validate_entity"):
        monkeypatch.setattr(_a_mod, "validate_entity", lambda k, d: [issue])

    with pytest.raises(click.ClickException) as exc:
        _a_mod._validate_frontmatter({"id": "x"})
    assert "Missing required property 'summary'" in str(exc.value.message)
