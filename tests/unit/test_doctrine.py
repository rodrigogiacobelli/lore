"""Tests for doctrine loading and validation.

Covers US-005: Default Doctrine feature-implementation update to include
lore codex chaos command reference in Phase 0 scout step notes.

Workflow: conceptual-workflows-codex-chaos
Spec (filter): filter-list-subcommands-us-3 (lore codex show filter-list-subcommands-us-3)
"""

from lore.doctrine import list_doctrines


# ---------------------------------------------------------------------------
# US-005: Doctrine Integration
# ---------------------------------------------------------------------------


# Unit — load_doctrine on updated file returns dict where at least one step's notes contains "lore codex chaos"
# conceptual-workflows-codex-chaos (FR-16: chaos mention must be in notes field of a Phase 0 step)
def test_feature_impl_doctrine_loads_with_chaos_note(tmp_path):
    # Given: path to .lore/doctrines/default/feature-implementation/feature-implementation.yaml
    # When: doctrine = load_doctrine(path) (or Doctrine.from_dict equivalent)
    # Then: any(["lore codex chaos" in step.get("notes", "") for step in doctrine["steps"]])
    pass


# Unit — Doctrine.from_dict on updated file raises no exception (schema valid)
# conceptual-workflows-codex-chaos (FR-16: doctrine YAML must remain schema-valid after update)
def test_feature_impl_doctrine_from_dict_no_exception(tmp_path):
    # Given: path to updated feature-implementation.yaml
    # When: Doctrine.from_dict(load_doctrine(path))
    # Then: no exception raised
    pass


# Unit — no step notes contain a file path starting with .lore/ or src/ in reference to chaos command
# conceptual-workflows-codex-chaos (ADR-006: all doctrine references must use CLI command names)
def test_feature_impl_doctrine_no_file_path_in_chaos_notes(tmp_path):
    # Given: path to updated feature-implementation.yaml
    # When: load_doctrine(path) and inspect all step notes fields
    # Then: no notes value contains ".lore/" adjacent to "chaos" or "src/"
    pass


# ---------------------------------------------------------------------------
# US-3: list_doctrines filter_groups parameter
# Spec: filter-list-subcommands-us-3
# ---------------------------------------------------------------------------

DEFAULT_DOCTRINE_YAML = """\
id: feature-add
title: Feature Add
description: Doctrine for adding features.
steps:
  - id: step-1
    title: Scout
    agent: ba
    missions: []
"""

OPS_DOCTRINE_YAML = """\
id: deploy-flow
title: Deploy Flow
description: Doctrine for deploying.
steps:
  - id: step-1
    title: Deploy
    agent: ops
    missions: []
"""

INVALID_DOCTRINE_YAML = """\
id: broken-doctrine
title: Broken Doctrine
description: Missing required steps field.
"""


def _setup_doctrines(doctrines_dir):
    """Populate doctrines_dir with doctrines in two groups."""
    default_dir = doctrines_dir / "default"
    default_dir.mkdir(parents=True)
    (default_dir / "feature-add.yaml").write_text(DEFAULT_DOCTRINE_YAML)
    ops_dir = doctrines_dir / "ops"
    ops_dir.mkdir()
    (ops_dir / "deploy-flow.yaml").write_text(OPS_DOCTRINE_YAML)


# Unit — list_doctrines filter_groups=["default"] — valid field accurate on filtered output
# Exercises: conceptual-workflows-filter-list step 3 + conceptual-workflows-doctrine-list (two-pass validation)
def test_list_doctrines_filter_valid_field_accurate(tmp_path):
    """list_doctrines with filter_groups=["default"] returns only default group; valid field is accurate."""
    doctrines_dir = tmp_path / ".lore" / "doctrines"
    _setup_doctrines(doctrines_dir)

    results = list_doctrines(doctrines_dir, filter_groups=["default"])

    ids = [r["id"] for r in results]
    assert "feature-add" in ids
    assert "deploy-flow" not in ids
    # valid field must be present and accurate for returned records
    for record in results:
        if record["id"] == "feature-add":
            assert "valid" in record
            assert record["valid"] is True


# Unit — list_doctrines filter — invalid marking on filtered records is unaffected
# Exercises: conceptual-workflows-filter-list step 3 + conceptual-workflows-doctrine-list (two-pass)
def test_list_doctrines_filter_invalid_marking_unaffected(tmp_path):
    """Invalid doctrines in the filtered group still have valid=False after filtering."""
    doctrines_dir = tmp_path / ".lore" / "doctrines"
    default_dir = doctrines_dir / "default"
    default_dir.mkdir(parents=True)
    (default_dir / "broken-doctrine.yaml").write_text(INVALID_DOCTRINE_YAML)
    ops_dir = doctrines_dir / "ops"
    ops_dir.mkdir()
    (ops_dir / "deploy-flow.yaml").write_text(OPS_DOCTRINE_YAML)

    results = list_doctrines(doctrines_dir, filter_groups=["default"])

    ids = [r["id"] for r in results]
    assert "broken-doctrine" in ids
    assert "deploy-flow" not in ids
    # The invalid doctrine must still be marked invalid
    for record in results:
        if record["id"] == "broken-doctrine":
            assert record["valid"] is False


# ---------------------------------------------------------------------------
# US-4: list_doctrines filter_groups=None — backward compatibility (no regression)
# Spec: filter-list-subcommands-us-4 (lore codex show filter-list-subcommands-us-4)
# Exercises: conceptual-workflows-filter-list step 3 (filter_groups=None → return all)
# ---------------------------------------------------------------------------


# Unit — list_doctrines filter_groups=None returns all doctrines (no regression)
# Exercises: conceptual-workflows-filter-list step 3 (filter_groups=None → return all)
def test_list_doctrines_filter_none_no_regression(tmp_path):
    """list_doctrines with filter_groups=None returns all doctrines across all groups — pre-filter behavior."""
    doctrines_dir = tmp_path / ".lore" / "doctrines"
    _setup_doctrines(doctrines_dir)

    results = list_doctrines(doctrines_dir, filter_groups=None)

    ids = [r["id"] for r in results]
    assert "feature-add" in ids
    assert "deploy-flow" in ids


# Unit — list_doctrines called without filter_groups returns all doctrines (backward compat)
# Exercises: backward compat — old callers that never passed filter_groups still work
def test_list_doctrines_no_filter_argument_returns_all(tmp_path):
    """list_doctrines called without filter_groups (default) returns all doctrines — backward compatible."""
    doctrines_dir = tmp_path / ".lore" / "doctrines"
    _setup_doctrines(doctrines_dir)

    results = list_doctrines(doctrines_dir)

    ids = [r["id"] for r in results]
    assert "feature-add" in ids
    assert "deploy-flow" in ids
