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


# ---------------------------------------------------------------------------
# resolve_beneath — the path-safety helper behind `[[descendants]]` blocks.
#
# Spec: nested-projects-spec (lore codex show nested-projects-spec) — F1, D-12
# Requirement: N-5 — the config must not become an arbitrary-filesystem-read
# primitive, so a value that escapes the project root resolves to nothing.
#
# Existence is deliberately not this function's job: whether a resolved path
# holds a Lore project is a separate question, and asking it here would make a
# pure path calculation touch the filesystem for a fact it does not need.
# ---------------------------------------------------------------------------


def test_resolve_beneath_resolves_a_plain_relative_name(tmp_path):
    # nested-projects-spec — F1: a relative name resolves under the root
    from lore.paths import resolve_beneath

    assert resolve_beneath(tmp_path, "lore") == (tmp_path / "lore").resolve()


def test_resolve_beneath_resolves_a_nested_relative_path(tmp_path):
    # nested-projects-spec — F1: several segments still resolve
    from lore.paths import resolve_beneath

    assert resolve_beneath(tmp_path, "apps/realm") == (tmp_path / "apps" / "realm").resolve()


def test_resolve_beneath_returns_the_root_for_a_dot(tmp_path):
    # nested-projects-spec — F1: "." returns the root itself
    from lore.paths import resolve_beneath

    assert resolve_beneath(tmp_path, ".") == tmp_path.resolve()


def test_resolve_beneath_rejects_a_parent_segment(tmp_path):
    # nested-projects-spec — F1 / N-5: ".." escapes and is refused
    from lore.paths import resolve_beneath

    root = tmp_path / "camelot"
    root.mkdir()
    assert resolve_beneath(root, "..") is None


def test_resolve_beneath_rejects_an_embedded_parent_segment(tmp_path):
    # nested-projects-spec — F1 / N-5: a `..` anywhere in the value escapes
    from lore.paths import resolve_beneath

    root = tmp_path / "camelot"
    root.mkdir()
    assert resolve_beneath(root, "lore/../../outside") is None


def test_resolve_beneath_rejects_an_absolute_path(tmp_path):
    # nested-projects-spec — F1 / N-5: an absolute value never resolves beneath
    from lore.paths import resolve_beneath

    assert resolve_beneath(tmp_path, "/etc") is None


def test_resolve_beneath_rejects_a_symlink_pointing_outside(tmp_path):
    # nested-projects-spec — F1 / N-5: both sides are resolved, so a symlink
    # out of the subtree is refused like a literal `..`
    from lore.paths import resolve_beneath

    root = tmp_path / "camelot"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "escape").symlink_to(outside, target_is_directory=True)

    assert resolve_beneath(root, "escape") is None


def test_resolve_beneath_accepts_a_symlink_that_stays_inside(tmp_path):
    # nested-projects-spec — F1: a symlink whose target is still beneath the
    # root is legitimate, and resolves to the target
    from lore.paths import resolve_beneath

    root = tmp_path / "camelot"
    (root / "real").mkdir(parents=True)
    (root / "link").symlink_to(root / "real", target_is_directory=True)

    assert resolve_beneath(root, "link/file") == (root / "real" / "file").resolve()


def test_resolve_beneath_resolves_a_path_that_does_not_exist(tmp_path):
    # nested-projects-spec — F1: existence is not this function's job
    from lore.paths import resolve_beneath

    assert not (tmp_path / "nowhere").exists()
    assert resolve_beneath(tmp_path, "nowhere/at/all") == (
        tmp_path / "nowhere" / "at" / "all"
    ).resolve()


# ---------------------------------------------------------------------------
# Doctrine directory layout.
#
# Spec: doctrine-missions-spec (lore codex show doctrine-missions-spec) — F2, D20.
#
# A doctrine is a directory holding `<stem>.design.md` beside `missions/`, so
# these three helpers take the DOCTRINE DIRECTORY rather than the project root
# — `derive_group` and `group_matches_filter` already set that precedent in
# this module. `doctrine.py` and `health.py` both need the same calculation,
# which is why it lives here once (standards-dry).
# ---------------------------------------------------------------------------


def test_design_suffix_is_the_paired_file_extension():
    from lore.paths import DESIGN_SUFFIX

    assert DESIGN_SUFFIX == ".design.md"


def test_missions_dirname_is_missions():
    from lore.paths import MISSIONS_DIRNAME

    assert MISSIONS_DIRNAME == "missions"


def test_doctrine_design_path_is_named_for_its_directory(tmp_path):
    from lore.paths import doctrine_design_path

    doctrine_dir = tmp_path / ".lore" / "doctrines" / "tdd-lite"
    assert doctrine_design_path(doctrine_dir) == doctrine_dir / "tdd-lite.design.md"


def test_doctrine_design_path_follows_a_grouped_directory(tmp_path):
    # The group lives in the path handed in; the helper adds nothing to it.
    from lore.paths import doctrine_design_path, doctrines_dir

    doctrine_dir = doctrines_dir(tmp_path) / "default" / "feature-implementation" / "tdd"
    assert doctrine_design_path(doctrine_dir) == doctrine_dir / "tdd.design.md"


def test_doctrine_missions_dir_sits_inside_the_doctrine(tmp_path):
    from lore.paths import doctrine_missions_dir

    doctrine_dir = tmp_path / ".lore" / "doctrines" / "tdd-lite"
    assert doctrine_missions_dir(doctrine_dir) == doctrine_dir / "missions"


def test_doctrine_mission_path_is_a_markdown_file_under_missions(tmp_path):
    from lore.paths import doctrine_mission_path

    doctrine_dir = tmp_path / ".lore" / "doctrines" / "tdd-lite"
    assert doctrine_mission_path(doctrine_dir, "recon") == (
        doctrine_dir / "missions" / "recon.md"
    )


def test_doctrine_mission_path_agrees_with_the_missions_dir_helper(tmp_path):
    from lore.paths import doctrine_mission_path, doctrine_missions_dir

    doctrine_dir = tmp_path / ".lore" / "doctrines" / "tdd-lite"
    assert doctrine_mission_path(doctrine_dir, "recon").parent == doctrine_missions_dir(
        doctrine_dir
    )


def test_the_three_doctrine_helpers_create_nothing(tmp_path):
    # A path calculation never touches the filesystem: every one of these is
    # called on a directory that does not exist, and none of it appears.
    from lore.paths import (
        doctrine_design_path,
        doctrine_mission_path,
        doctrine_missions_dir,
    )

    doctrine_dir = tmp_path / ".lore" / "doctrines" / "tdd-lite"
    doctrine_design_path(doctrine_dir)
    doctrine_missions_dir(doctrine_dir)
    doctrine_mission_path(doctrine_dir, "recon")

    assert list(tmp_path.iterdir()) == []
