"""Unit tests for lore.paths.glossary_path and lore.paths.config_path.

Spec: glossary-us-001 (lore codex show glossary-us-001)
Spec: glossary-us-003 (lore codex show glossary-us-003)
Workflow: conceptual-workflows-glossary
"""

from __future__ import annotations

from lore.paths import glossary_path


def test_glossary_path_returns_canonical_location(tmp_path):
    # conceptual-workflows-glossary — path resolution (US-001 unit row)
    assert glossary_path(tmp_path) == tmp_path / ".lore" / "codex" / "glossary.yaml"


def test_config_path(tmp_path):
    # conceptual-workflows-glossary — config_path resolution (US-003 Scenario 9, Unit row 13)
    from lore.paths import config_path
    assert config_path(tmp_path) == tmp_path / ".lore" / "config.toml"
