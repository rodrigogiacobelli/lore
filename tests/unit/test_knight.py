"""Unit tests for lore.knight.list_knights with filter_groups parameter.

Spec: filter-list-subcommands-us-3 (lore codex show filter-list-subcommands-us-3)
Workflow: conceptual-workflows-filter-list
"""

import inspect

import pytest

from lore.cli import main
from lore.knight import list_knights

try:
    from lore.knight import create_knight
except ImportError:  # pragma: no cover — red phase, helper not implemented yet
    create_knight = None


# ---------------------------------------------------------------------------
# Fixtures — knight file content
# ---------------------------------------------------------------------------

FEATURE_IMPL_BA_MD = """\
---
id: feature-implementation/ba
title: BA Knight
summary: Business analyst persona.
---

BA body.
"""

OPS_DEPLOY_MD = """\
---
id: ops/deploy
title: Deploy Knight
summary: Ops deployment persona.
---

Deploy body.
"""

MISSING_FIELDS_MD = """\
---
title: Knight with no id or summary
---

No id or summary body.
"""


# ---------------------------------------------------------------------------
# Unit — list_knights filter_groups=["feature-implementation"] returns matched group only
# Exercises: conceptual-workflows-filter-list step 3 (_apply_filter on knight records)
# ---------------------------------------------------------------------------


def test_list_knights_filter_returns_matched_group(tmp_path):
    """list_knights with filter_groups=["feature-implementation"] returns only feature-implementation knights."""
    knights_dir = tmp_path / ".lore" / "knights"
    feature_dir = knights_dir / "feature-implementation"
    feature_dir.mkdir(parents=True)
    (feature_dir / "ba.md").write_text(FEATURE_IMPL_BA_MD)
    ops_dir = knights_dir / "ops"
    ops_dir.mkdir()
    (ops_dir / "deploy.md").write_text(OPS_DEPLOY_MD)

    results = list_knights(knights_dir, filter_groups=["feature-implementation"])

    groups = [r["group"] for r in results]
    # Only feature-implementation group (and root, which is empty string) should appear
    for group in groups:
        assert group in ("feature-implementation", ""), f"Unexpected group: {group}"
    ids = [r["id"] for r in results]
    # feature-implementation/ba must be present; ops/deploy must not
    assert any("ba" in knight_id or "feature-implementation" in knight_id for knight_id in ids)
    assert not any("deploy" in knight_id for knight_id in ids)


# ---------------------------------------------------------------------------
# Unit — list_knights filter — fallback values preserved on filtered records
# Exercises: conceptual-workflows-filter-list step 3 + conceptual-workflows-knight-list (lenient fallback)
# ---------------------------------------------------------------------------


def test_list_knights_filter_fallback_values_preserved(tmp_path):
    """list_knights with filter preserves id=stem and summary="" fallbacks on filtered records."""
    knights_dir = tmp_path / ".lore" / "knights"
    feature_dir = knights_dir / "feature-implementation"
    feature_dir.mkdir(parents=True)
    # Write a knight file with missing id and summary — fallbacks must apply
    (feature_dir / "no-meta.md").write_text(MISSING_FIELDS_MD)

    results = list_knights(knights_dir, filter_groups=["feature-implementation"])

    assert len(results) == 1
    record = results[0]
    # Fallback: id == file stem
    assert record["id"] == "no-meta"
    # Fallback: summary == ""
    assert record["summary"] == ""
    # Group must be feature-implementation
    assert record["group"] == "feature-implementation"


# ---------------------------------------------------------------------------
# US-4: list_knights filter_groups=None — backward compatibility (no regression)
# Spec: filter-list-subcommands-us-4 (lore codex show filter-list-subcommands-us-4)
# Exercises: conceptual-workflows-filter-list step 3 (filter_groups=None → return all)
# ---------------------------------------------------------------------------


def _setup_knights(knights_dir):
    """Populate knights_dir with knights in two groups."""
    feature_dir = knights_dir / "feature-implementation"
    feature_dir.mkdir(parents=True)
    (feature_dir / "ba.md").write_text(FEATURE_IMPL_BA_MD)
    ops_dir = knights_dir / "ops"
    ops_dir.mkdir()
    (ops_dir / "deploy.md").write_text(OPS_DEPLOY_MD)


# Unit — list_knights filter_groups=None returns all knights (no regression)
# Exercises: conceptual-workflows-filter-list step 3 (filter_groups=None → return all)
def test_list_knights_filter_none_no_regression(tmp_path):
    """list_knights with filter_groups=None returns all knights across all groups — pre-filter behavior."""
    knights_dir = tmp_path / ".lore" / "knights"
    _setup_knights(knights_dir)

    results = list_knights(knights_dir, filter_groups=None)

    ids = [r["id"] for r in results]
    assert any("ba" in kid or "feature-implementation" in kid for kid in ids)
    assert any("deploy" in kid or "ops" in kid for kid in ids)


# Unit — list_knights called without filter_groups returns all knights (backward compat)
# Exercises: backward compat — old callers that never passed filter_groups still work
def test_list_knights_no_filter_argument_returns_all(tmp_path):
    """list_knights called without filter_groups (default) returns all knights — backward compatible."""
    knights_dir = tmp_path / ".lore" / "knights"
    _setup_knights(knights_dir)

    results = list_knights(knights_dir)

    ids = [r["id"] for r in results]
    assert any("ba" in kid or "feature-implementation" in kid for kid in ids)
    assert any("deploy" in kid or "ops" in kid for kid in ids)


# ---------------------------------------------------------------------------
# US-002: create_knight — Python API with --group kwarg
# Spec: group-param-us-002 (lore codex show group-param-us-002)
# anchor: conceptual-workflows-knight-crud
# ---------------------------------------------------------------------------


KNIGHT_MD = "---\nid: {name}\ntitle: T\nsummary: S\n---\n# body\n"


class TestCreateKnight:
    """Unit tests for the lore.knight.create_knight helper."""

    def test_signature_group_is_keyword_only_default_none(self):
        # AC: function exists with (knights_dir, name, content, *, group=None) signature
        sig = inspect.signature(create_knight)
        assert "group" in sig.parameters
        assert sig.parameters["group"].kind is inspect.Parameter.KEYWORD_ONLY
        assert sig.parameters["group"].default is None

    def test_group_none_writes_to_root(self, tmp_path):
        # AC: group=None writes to knights_dir/"<name>.md"
        create_knight(tmp_path, "reviewer", KNIGHT_MD.format(name="reviewer"))
        assert (tmp_path / "reviewer.md").exists()

    def test_nested_group_writes_to_subdir_with_auto_mkdir(self, tmp_path):
        # AC: group="a/b" writes nested with intermediate dirs created
        create_knight(
            tmp_path, "lead", KNIGHT_MD.format(name="lead"), group="a/b"
        )
        assert (tmp_path / "a").is_dir()
        assert (tmp_path / "a" / "b").is_dir()
        assert (tmp_path / "a" / "b" / "lead.md").exists()

    def test_mkdir_idempotent_with_preexisting_dir(self, tmp_path):
        # AC: pre-existing target dir does not raise
        (tmp_path / "a").mkdir()
        create_knight(tmp_path, "k", KNIGHT_MD.format(name="k"), group="a")
        assert (tmp_path / "a" / "k.md").exists()

    def test_duplicate_subtree_raises_value_error(self, tmp_path):
        # AC: raises ValueError when name exists anywhere in subtree (rglob)
        (tmp_path / "x").mkdir()
        (tmp_path / "x" / "k.md").write_text(KNIGHT_MD.format(name="k"))
        with pytest.raises(ValueError, match="already exists"):
            create_knight(
                tmp_path, "k", KNIGHT_MD.format(name="k"), group="y"
            )

    def test_duplicate_subtree_does_not_create_file(self, tmp_path):
        # AC: no file written under new group when duplicate detected
        (tmp_path / "x").mkdir()
        (tmp_path / "x" / "k.md").write_text(KNIGHT_MD.format(name="k"))
        with pytest.raises(ValueError):
            create_knight(
                tmp_path, "k", KNIGHT_MD.format(name="k"), group="y"
            )
        assert not (tmp_path / "y" / "k.md").exists()

    def test_return_dict_contains_required_keys(self, tmp_path):
        # AC: returns dict containing name, group, filename, path keys
        result = create_knight(
            tmp_path, "k", KNIGHT_MD.format(name="k"), group="a"
        )
        assert isinstance(result, dict)
        assert set(result.keys()) >= {"name", "group", "filename", "path"}

    def test_return_dict_values_match_inputs(self, tmp_path):
        # AC: returned values reflect what was written
        result = create_knight(
            tmp_path, "k", KNIGHT_MD.format(name="k"), group="a"
        )
        assert result["name"] == "k"
        assert result["group"] == "a"
        assert result["filename"] == "k.md"
        assert result["path"].endswith("a/k.md")

    def test_return_dict_group_none_at_root(self, tmp_path):
        # AC: group key is None when created at root
        result = create_knight(
            tmp_path, "k", KNIGHT_MD.format(name="k")
        )
        assert result["group"] is None

    def test_invalid_group_raises_before_filesystem_write(self, tmp_path):
        # AC: validate_group rejects, raises ValueError, no file written
        with pytest.raises(ValueError):
            create_knight(
                tmp_path, "k", KNIGHT_MD.format(name="k"), group=".."
            )
        assert not any(tmp_path.rglob("*.md"))


# ---------------------------------------------------------------------------
# US-002: CLI knight_new thin-wrapper smoke test
# anchor: decisions-011-api-parity-with-cli
# ---------------------------------------------------------------------------


class TestCliKnightNewThinWrapper:
    """CLI handler must delegate to create_knight with the parsed --group value."""

    def test_cli_delegates_group_kwarg_to_create_knight(
        self, monkeypatch, runner, project_dir
    ):
        # AC: thin-wrapper smoke — handler calls create_knight with group kwarg
        captured = {}

        def fake_create_knight(knights_dir, name, content, *, group=None):
            captured["knights_dir"] = knights_dir
            captured["name"] = name
            captured["content"] = content
            captured["group"] = group
            return {
                "name": name,
                "group": group,
                "filename": f"{name}.md",
                "path": str(knights_dir / (group or "") / f"{name}.md"),
            }

        monkeypatch.setattr("lore.cli.create_knight", fake_create_knight)
        (project_dir / "p.md").write_text(KNIGHT_MD.format(name="k"))
        result = runner.invoke(
            main,
            ["knight", "new", "k", "--group", "a/b", "--from", "p.md"],
        )
        assert result.exit_code == 0
        assert captured["group"] == "a/b"
        assert captured["name"] == "k"

    def test_cli_delegates_with_group_none_when_flag_omitted(
        self, monkeypatch, runner, project_dir
    ):
        # AC: omitting --group passes group=None
        captured = {}

        def fake_create_knight(knights_dir, name, content, *, group=None):
            captured["group"] = group
            return {
                "name": name,
                "group": group,
                "filename": f"{name}.md",
                "path": str(knights_dir / f"{name}.md"),
            }

        monkeypatch.setattr("lore.cli.create_knight", fake_create_knight)
        (project_dir / "p.md").write_text(KNIGHT_MD.format(name="k"))
        result = runner.invoke(
            main, ["knight", "new", "k", "--from", "p.md"]
        )
        assert result.exit_code == 0
        assert captured["group"] is None
