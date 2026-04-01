"""Tests for doctrine loading and validation.

Covers US-005: Default Doctrine feature-implementation update to include
lore codex chaos command reference in Phase 0 scout step notes.

Workflow: conceptual-workflows-codex-chaos
"""

import pytest


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
