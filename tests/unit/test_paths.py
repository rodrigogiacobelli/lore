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


# ---------------------------------------------------------------------------
# The install manifest.
# Workflow: conceptual-workflows-init-reconcile
# ---------------------------------------------------------------------------


def test_install_manifest_path_points_into_dot_lore(tmp_path):
    from lore.paths import install_manifest_path

    assert install_manifest_path(tmp_path) == tmp_path / ".lore" / ".install-manifest.json"


def test_install_manifest_is_a_dot_file_the_lore_gitignore_already_covers(tmp_path):
    from lore.paths import install_manifest_path, lore_dir

    target = install_manifest_path(tmp_path)
    assert target.name.startswith(".")
    assert target.parent == lore_dir(tmp_path)


# ---------------------------------------------------------------------------
# The rendered agent instruction text.
# Spec: interactive-init-us-007
# Workflow: conceptual-workflows-lore-init (project structure)
# ---------------------------------------------------------------------------


def test_lore_agent_path_points_into_dot_lore(tmp_path):
    # interactive-init-us-007 — Unit: lore_agent_path -> <root>/.lore/LORE-AGENT.md
    from lore.paths import lore_agent_path

    assert lore_agent_path(tmp_path) == tmp_path / ".lore" / "LORE-AGENT.md"


def test_lore_agent_path_sits_beside_the_other_dot_lore_helpers(tmp_path):
    # interactive-init-us-007 — the ".lore" literal stays centralised in paths.py.
    from lore.paths import lore_agent_path, lore_dir

    assert lore_agent_path(tmp_path).parent == lore_dir(tmp_path)


# ---------------------------------------------------------------------------
# The skills tree.
# Spec: interactive-init-us-011 (lore codex show interactive-init-us-011)
# Anchor: conceptual-workflows-init-interactive — The Prompts, prompt 1 (agents)
#
# `.lore/skills/` is where skills land for an agent with no native skills
# directory, and for a project that selected none at all.
# ---------------------------------------------------------------------------


def test_skills_dir_points_into_dot_lore(tmp_path):
    # interactive-init-us-011 — Unit: paths.skills_dir -> <root>/.lore/skills
    from lore.paths import skills_dir

    assert skills_dir(tmp_path) == tmp_path / ".lore" / "skills"


def test_skills_dir_sits_beside_the_other_dot_lore_helpers(tmp_path):
    # interactive-init-us-011 — Unit: the magic string lives in paths.py alone
    from lore.paths import lore_dir, skills_dir

    assert skills_dir(tmp_path).parent == lore_dir(tmp_path)
