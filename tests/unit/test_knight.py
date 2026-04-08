"""Unit tests for lore.knight.list_knights with filter_groups parameter.

Spec: filter-list-subcommands-us-3 (lore codex show filter-list-subcommands-us-3)
Workflow: conceptual-workflows-filter-list
"""

from lore.knight import list_knights


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
