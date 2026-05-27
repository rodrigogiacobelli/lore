"""Unit tests for lore.artifact.list_artifacts with filter_groups parameter.

Spec: filter-list-subcommands-us-3 (lore codex show filter-list-subcommands-us-3)
Workflow: conceptual-workflows-filter-list

Post-G16: list_artifacts replaces scan_artifacts; first arg is project_root.
"""

from lore.artifact import list_artifacts


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


def _setup_artifacts(project_root):
    """Populate project_root/.lore/artifacts/ with test fixtures."""
    artifacts_dir = project_root / ".lore" / "artifacts"
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
    return artifacts_dir


def test_list_artifacts_filter_returns_matched_group_and_root(tmp_path):
    """list_artifacts with filter_groups=["default/codex"] returns default-codex and root-level artifacts only."""
    _setup_artifacts(tmp_path)

    results = list_artifacts(tmp_path, filter_groups=["default/codex"])

    ids = [r["id"] for r in results]
    assert "root-artifact" in ids
    assert "fi-user-story" in ids
    assert "some-artifact" not in ids
    assert "scratch" not in ids


def test_list_artifacts_filter_valid_count_reflects_filtered_set(tmp_path):
    """list_artifacts with filter returns fewer records than without filter."""
    _setup_artifacts(tmp_path)

    all_results = list_artifacts(tmp_path)
    filtered_results = list_artifacts(tmp_path, filter_groups=["default/codex"])

    assert len(filtered_results) < len(all_results)
    assert len(filtered_results) == 2  # root-artifact + fi-user-story


def test_list_artifacts_filter_invalid_frontmatter_skip_unaffected(tmp_path):
    """Invalid frontmatter files in other groups are still skipped when filter is applied."""
    artifacts_dir = _setup_artifacts(tmp_path)
    # Add an invalid file in the "default" group — it should be skipped regardless of filter
    (artifacts_dir / "default" / "invalid-no-id.md").write_text(INVALID_FRONTMATTER_MD)

    results = list_artifacts(tmp_path, filter_groups=["default/codex"])

    ids = [r["id"] for r in results]
    assert "invalid-no-id" not in ids
    assert "root-artifact" in ids
    assert "fi-user-story" in ids


def test_list_artifacts_filter_none_no_regression(tmp_path):
    """list_artifacts with filter_groups=None returns all artifacts across all groups."""
    _setup_artifacts(tmp_path)

    results = list_artifacts(tmp_path, filter_groups=None)

    ids = [r["id"] for r in results]
    assert "root-artifact" in ids
    assert "some-artifact" in ids
    assert "fi-user-story" in ids
    assert "scratch" in ids


def test_list_artifacts_no_filter_argument_returns_all(tmp_path):
    """list_artifacts called without filter_groups (default) returns all artifacts."""
    _setup_artifacts(tmp_path)

    results = list_artifacts(tmp_path)

    ids = [r["id"] for r in results]
    assert "root-artifact" in ids
    assert "some-artifact" in ids
    assert "fi-user-story" in ids
    assert "scratch" in ids


# ---------------------------------------------------------------------------
# US-004: create_artifact unit matrix
# Spec: group-param-us-004 (lore codex show group-param-us-004)
# anchor: conceptual-workflows-artifact-list (first write path)
#
# Post-G16: create_artifact(project_root, name, content, *, group=None)
# ---------------------------------------------------------------------------

import inspect  # noqa: E402

import pytest  # noqa: E402
from click.testing import CliRunner  # noqa: E402

from lore.cli import main  # noqa: E402

_VALID_BODY = "---\nid: a\ntitle: T\nsummary: s\n---\nbody\n"


def _import_create_artifact():
    from lore.artifact import create_artifact

    return create_artifact


@pytest.fixture()
def create_artifact():
    return _import_create_artifact()


class TestCreateArtifact:
    """Unit matrix for lore.artifact.create_artifact — US-004."""

    def test_signature_group_is_kwarg_only_with_none_default(self, create_artifact):
        sig = inspect.signature(create_artifact)
        assert sig.parameters["group"].kind is inspect.Parameter.KEYWORD_ONLY
        assert sig.parameters["group"].default is None

    def test_group_none_writes_to_artifacts_dir_root(self, create_artifact, tmp_path):
        (tmp_path / ".lore" / "artifacts").mkdir(parents=True)
        create_artifact(tmp_path, "a", _VALID_BODY)
        assert (tmp_path / ".lore" / "artifacts" / "a.md").exists()

    def test_group_nested_writes_to_subdir_with_auto_mkdir(
        self, create_artifact, tmp_path
    ):
        (tmp_path / ".lore" / "artifacts").mkdir(parents=True)
        create_artifact(tmp_path, "a", _VALID_BODY, group="a/b")
        assert (tmp_path / ".lore" / "artifacts" / "a" / "b" / "a.md").exists()

    def test_duplicate_stem_anywhere_in_subtree_raises(
        self, create_artifact, tmp_path
    ):
        artifacts_dir = tmp_path / ".lore" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        (artifacts_dir / "x").mkdir()
        (artifacts_dir / "x" / "a.md").write_text(_VALID_BODY)
        with pytest.raises(ValueError, match="already exists"):
            create_artifact(tmp_path, "a", _VALID_BODY, group="y")

    def test_missing_required_frontmatter_summary_raises(
        self, create_artifact, tmp_path
    ):
        (tmp_path / ".lore" / "artifacts").mkdir(parents=True)
        bad = "---\nid: a\ntitle: T\n---\nbody\n"
        with pytest.raises(ValueError):
            create_artifact(tmp_path, "a", bad)

    def test_missing_required_frontmatter_id_raises(self, create_artifact, tmp_path):
        (tmp_path / ".lore" / "artifacts").mkdir(parents=True)
        bad = "---\ntitle: T\nsummary: s\n---\nbody\n"
        with pytest.raises(ValueError):
            create_artifact(tmp_path, "a", bad)

    def test_missing_required_frontmatter_title_raises(
        self, create_artifact, tmp_path
    ):
        (tmp_path / ".lore" / "artifacts").mkdir(parents=True)
        bad = "---\nid: a\nsummary: s\n---\nbody\n"
        with pytest.raises(ValueError):
            create_artifact(tmp_path, "a", bad)

    def test_return_dict_contains_required_keys(self, create_artifact, tmp_path):
        (tmp_path / ".lore" / "artifacts").mkdir(parents=True)
        result = create_artifact(tmp_path, "a", _VALID_BODY, group="a/b")
        # Post-G16: returns {id, filename, group} — no path key.
        assert set(result.keys()) == {"id", "filename", "group"}
        assert result["id"] == "a"
        assert result["group"] == "a/b"
        assert result["filename"] == "a.md"

    def test_return_dict_group_none_when_flat(self, create_artifact, tmp_path):
        (tmp_path / ".lore" / "artifacts").mkdir(parents=True)
        result = create_artifact(tmp_path, "a", _VALID_BODY)
        assert result["group"] is None

    def test_invalid_group_rejected_before_filesystem_write(
        self, create_artifact, tmp_path
    ):
        (tmp_path / ".lore" / "artifacts").mkdir(parents=True)
        with pytest.raises(ValueError):
            create_artifact(tmp_path, "a", _VALID_BODY, group="../escape")
        assert not any((tmp_path / ".lore" / "artifacts").rglob("*.md"))


# ---------------------------------------------------------------------------
# US-004: CLI thin-wrapper smoke — artifact_new forwards --group kwarg
# Post-G16: monkeypatch fake takes project_root (not artifacts_dir).
# ---------------------------------------------------------------------------


class TestCliArtifactNewThinWrapper:
    def test_cli_artifact_new_forwards_group_kwarg(self, monkeypatch, tmp_path):
        captured = {}

        def fake_create(project_root, name, content, *, group=None):
            captured["name"] = name
            captured["group"] = group
            captured["content"] = content
            return {
                "id": name,
                "filename": f"{name}.md",
                "group": group,
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
        captured = {}

        def fake_create(project_root, name, content, *, group=None):
            captured["group"] = group
            return {
                "id": name,
                "filename": f"{name}.md",
                "group": group,
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
# ---------------------------------------------------------------------------


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
