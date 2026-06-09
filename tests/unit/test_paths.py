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


# ---------------------------------------------------------------------------
# Rite directory paths.
# Spec: transient-rites-us-1 (lore codex show transient-rites-us-1)
# Workflow: conceptual-workflows-rite-crud (scan_rites uses these dirs)
# ---------------------------------------------------------------------------


def test_rites_dir_returns_canonical_location(tmp_path):
    # transient-rites-us-1 — Unit: rites_dir -> <root>/.lore/rites
    from lore.paths import rites_dir

    assert rites_dir(tmp_path) == tmp_path / ".lore" / "rites"


def test_rites_main_dir_returns_canonical_location(tmp_path):
    # transient-rites-us-1 — Unit: rites_main_dir -> <root>/.lore/rites/main
    from lore.paths import rites_main_dir

    assert rites_main_dir(tmp_path) == tmp_path / ".lore" / "rites" / "main"


def test_rites_shared_dir_returns_canonical_location(tmp_path):
    # transient-rites-us-1 — Unit: rites_shared_dir -> <root>/.lore/rites/shared
    from lore.paths import rites_shared_dir

    assert rites_shared_dir(tmp_path) == tmp_path / ".lore" / "rites" / "shared"
