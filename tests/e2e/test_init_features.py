"""E2E tests for feature-adaptive `lore init` — what each set of answers installs.

Spec: conceptual-workflows-init-features
(lore codex show conceptual-workflows-init-features)

Every fixture profile, and a sample of the random ones, is installed into a
temporary project through the Python surface (the CLI flags for the feature
answers arrive with the surface lane; ``plan_init`` and ``apply_init`` take the
same answers as keywords), and then checked from the outside: the skills on
disk are the skills the profile installs, the instruction text fits its cap and
names no command the profile turns off, the seeded trees follow the plan,
`lore health` is clean and a second run changes nothing.

Per decisions-006-no-seed-content-tests nothing here reads a word of a shipped
block, doctrine, artifact or watcher: the expected skill set is computed from
``skills.installed_skills``, the leak check is the lint API, and the seeded
files are compared against the plan's own listing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from lore import blocklint, blocks, init, skills
from lore.api import apply_init, plan_init
from lore.cli import main
from lore.initplan import Feature, Profile, Route
from lore.legacy_init import profile_from_legacy
from tests.unit.conftest import (
    EVERY_VALID_PROFILE,
    FIXTURE_PROFILES,
    FULL,
    HARNESS_BARE,
    HARNESS_MEMORY,
)

ALL_ON = FULL
ALL_OFF = HARNESS_BARE
MEMORY_HARNESS_ONLY = HARNESS_MEMORY

SAMPLED = {
    **FIXTURE_PROFILES,
    **{f"random-{i}": EVERY_VALID_PROFILE[i] for i in range(0, len(EVERY_VALID_PROFILE), 25)},
}
SKILLS_ROOT = ".claude/skills"
SEEDED_PREFIXES = (
    ".lore/doctrines/default/",
    ".lore/artifacts/default/",
    ".lore/watchers/default/",
)


def install(root: Path, profile: Profile = ALL_ON, **extra):
    """Apply an initialisation of *root* for *profile*, as Claude Code's project."""
    answers = {"agents": ["claude"], **profile.as_answers(), **extra}
    return apply_init(plan_init(root, **answers))


def files_under(root: Path, relative: str) -> set[str]:
    base = root / relative
    if not base.is_dir():
        return set()
    return {path.relative_to(root).as_posix() for path in base.rglob("*") if path.is_file()}


def skill_dirs(root: Path) -> set[str]:
    base = root / SKILLS_ROOT
    if not base.is_dir():
        return set()
    return {child.name for child in base.iterdir() if child.is_dir()}


def health(root: Path):
    return CliRunner().invoke(main, ["health"], catch_exceptions=False)


@pytest.fixture()
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture(params=list(SAMPLED), ids=list(SAMPLED))
def profile(request):
    return SAMPLED[request.param]


class TestEachProfileInstallsOnlyWhatItUses:
    def test_the_skill_directories_are_the_installed_skills_and_no_others(self, project, profile):
        install(project, profile)
        assert skill_dirs(project) == set(skills.installed_skills(profile))

    def test_every_materialised_skill_file_exists_and_no_other(self, project, profile):
        install(project, profile)
        expected = {
            f"{SKILLS_ROOT}/{skill}/{relative}"
            for skill in skills.installed_skills(profile)
            for relative in skills.skill_files(skill, profile)
        }
        on_disk = {p for p in files_under(project, SKILLS_ROOT) if not p.endswith(".gitignore")}
        assert on_disk == expected

    def test_the_instruction_files_always_exist(self, project, profile):
        install(project, profile)
        assert (project / ".lore" / "LORE-AGENT.md").is_file()
        assert (project / "CLAUDE.md").is_file()

    def test_lore_health_is_taught_to_every_profile(self, project, profile):
        install(project, profile)
        text = (project / ".lore" / "LORE-AGENT.md").read_text(encoding="utf-8")
        assert "lore health" in text

    def test_the_rendered_instruction_text_fits_the_cap(self, project, profile):
        install(project, profile)
        for relative in (".lore/LORE-AGENT.md", "CLAUDE.md"):
            target = project / relative
            if target.is_file():
                assert len(target.read_text(encoding="utf-8").splitlines()) <= 100, relative

    def test_no_installed_file_names_a_command_the_profile_turns_off(self, project, profile):
        install(project, profile)
        installed = bool(skills.installed_skills(profile))
        for path in [project / ".lore" / "LORE-AGENT.md", project / "CLAUDE.md"]:
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                assert blocks.leaked_commands(text, profile, skills_installed=installed) == (), path
        for relative in files_under(project, SKILLS_ROOT):
            if relative.endswith(".md"):
                text = (project / relative).read_text(encoding="utf-8")
                assert blocks.leaked_commands(text, profile) == (), relative
        assert blocklint.lint_rendered(profile) == []

    def test_the_bare_harness_teaches_no_command_but_health(self, project):
        install(project, HARNESS_BARE)
        text = (project / ".lore" / "LORE-AGENT.md").read_text(encoding="utf-8")
        phrases = set(blocks.commands_in(text))
        assert phrases
        assert all(phrase == "health" or phrase.startswith("health --scope") for phrase in phrases)

    def test_the_seeded_trees_are_those_the_plan_listed(self, project, profile):
        plan = plan_init(project, agents=["claude"], **profile.as_answers())
        apply_init(plan)
        for prefix in SEEDED_PREFIXES:
            listed = {path for path in plan.seeded if path.startswith(prefix)}
            assert files_under(project, prefix.rstrip("/")) == listed, prefix

    def test_the_database_is_always_created(self, project, profile):
        install(project, profile)
        assert (project / ".lore" / "lore.db").is_file()

    def test_memory_files_follow_the_memory_feature(self, project, profile):
        install(project, profile)
        memory = profile.feature_on(Feature.MEMORY)
        assert (project / ".lore" / "codex" / "codex.md").is_file() is memory
        assert (project / ".lore" / "codex" / "glossary.yaml").is_file() is memory
        assert (project / ".lore" / "rites" / "main").is_dir() is memory

    def test_lore_health_is_clean(self, project, profile):
        install(project, profile)
        result = health(project)
        assert result.exit_code == 0, result.output
        assert "ERROR" not in result.output, result.output

    def test_a_second_run_changes_nothing_that_is_reconciled(self, project, profile):
        install(project, profile)
        again = plan_init(project, agents=["claude"], **profile.as_answers())
        assert [row for row in again.files if row.reported] == []
        assert again.notices == ()

    def test_a_second_run_leaves_the_tree_and_the_manifest_stable(self, project, profile):
        install(project, profile)
        before = {
            path: (project / path).read_bytes()
            for path in files_under(project, ".lore") | files_under(project, SKILLS_ROOT)
            if path != ".lore/lore.db"
        }
        install(project, profile)
        after = {
            path: (project / path).read_bytes()
            for path in files_under(project, ".lore") | files_under(project, SKILLS_ROOT)
            if path != ".lore/lore.db"
        }
        manifest_path = ".lore/.install-manifest.json"
        for payload in (before, after):
            data = json.loads(payload[manifest_path])
            data.pop("generated_at")
            payload[manifest_path] = json.dumps(data, sort_keys=True).encode()
        assert after == before


class TestHeadlessDefaultsInstallThePreviousFileSet:
    """No flag, no config, no terminal: everything on, as the earlier release did."""

    def test_all_eleven_skills_and_the_default_trees_and_memory_files(self, project):
        init.run_init()
        installed = {p.name for p in (project / ".lore" / "skills").iterdir() if p.is_dir()}
        assert installed == {entry["id"] for entry in skills.load_catalogue()["skills"]}
        assert len(installed) == 11
        for prefix in SEEDED_PREFIXES:
            assert files_under(project, prefix.rstrip("/")), prefix
        for relative in (
            ".lore/codex/codex.md",
            ".lore/codex/glossary.yaml",
            ".lore/lore.db",
            ".lore/LORE-AGENT.md",
            ".lore/GETTING-STARTED.md",
        ):
            assert (project / relative).is_file(), relative
        assert (project / ".lore" / "rites" / "main").is_dir()
        assert (project / ".lore" / "rites" / "shared").is_dir()

    def test_the_headless_plan_is_the_all_on_profile(self, project):
        assert plan_init(project).answers.profile == ALL_ON


class TestFeatureTurnedOffRemovesItsSeedsAndSkills:
    def test_turning_watchers_off_takes_its_seeds_and_skill_and_leaves_the_users_files(
        self, project
    ):
        install(project, ALL_ON)
        assert files_under(project, ".lore/watchers/default")
        assert "update-watcher" in skill_dirs(project)
        mine = project / ".lore" / "watchers" / "mine.yaml"
        mine.write_text("name: mine\n", encoding="utf-8")
        codex = project / ".lore" / "codex" / "codex.md"
        codex_before = codex.read_bytes()

        narrower = Profile(watchers=False).normalized()
        result = install(project, narrower)

        assert files_under(project, ".lore/watchers/default") == set()
        assert "update-watcher" not in skill_dirs(project)
        assert mine.read_text(encoding="utf-8") == "name: mine\n"
        assert codex.read_bytes() == codex_before
        assert any("update-watcher" in message and "Removed" in message for message in result.messages)

    def test_the_changelog_doctrine_stays_when_the_watcher_goes(self, project):
        install(project, ALL_ON)
        assert any("update-changelog" in p for p in files_under(project, ".lore/doctrines"))
        install(project, Profile(watchers=False).normalized())
        assert any("update-changelog" in p for p in files_under(project, ".lore/doctrines"))
        assert not files_under(project, ".lore/watchers/default")

    def test_a_skill_the_user_authored_beside_the_installed_ones_survives(self, project):
        install(project, ALL_ON)
        mine = project / SKILLS_ROOT / "house-style" / "SKILL.md"
        mine.parent.mkdir(parents=True)
        mine.write_text("mine\n", encoding="utf-8")
        install(project, MEMORY_HARNESS_ONLY)
        assert mine.read_text(encoding="utf-8") == "mine\n"
        assert skill_dirs(project) - {"house-style"} == set(
            skills.installed_skills(MEMORY_HARNESS_ONLY)
        )


class TestSkillsNoLongerWantedAreRemoved:
    @pytest.mark.parametrize(
        "narrower",
        [name for name in FIXTURE_PROFILES if name != "ALL_ON"],
    )
    def test_narrowing_from_everything_leaves_exactly_the_narrower_set(self, project, narrower):
        install(project, ALL_ON)
        target = FIXTURE_PROFILES[narrower]
        result = install(project, target)
        assert skill_dirs(project) == set(skills.installed_skills(target))
        removed = set(skills.installed_skills(ALL_ON)) - set(skills.installed_skills(target))
        for skill in removed:
            assert any(f"{SKILLS_ROOT}/{skill}/" in m or f"{skill}/SKILL.md" in m for m in result.messages)


class TestFeatureTurnedOnLater:
    def test_widening_the_profile_installs_what_the_wider_one_uses(self, project):
        install(project, MEMORY_HARNESS_ONLY)
        assert skill_dirs(project) == set(skills.installed_skills(MEMORY_HARNESS_ONLY))
        assert not files_under(project, ".lore/watchers/default")

        install(project, ALL_ON)

        assert skill_dirs(project) == set(skills.installed_skills(ALL_ON))
        for prefix in SEEDED_PREFIXES:
            assert files_under(project, prefix.rstrip("/")), prefix
        assert health(project).exit_code == 0

    def test_the_codex_root_survives_a_round_trip(self, project):
        install(project, ALL_ON)
        codex = project / ".lore" / "codex" / "codex.md"
        codex.write_text(codex.read_text(encoding="utf-8") + "\nmine\n", encoding="utf-8")
        before = codex.read_bytes()
        install(project, ALL_OFF)
        install(project, ALL_ON)
        assert codex.read_bytes() == before


class TestBareCoreInstallsTheCoreOnly:
    def test_the_core_text_skills_and_seeds_are_installed_and_nothing_optional(self, project):
        install(project, HARNESS_BARE)
        assert (project / ".lore" / "LORE-AGENT.md").is_file()
        assert skill_dirs(project) == {"update-doctrine", "update-artifact", "run-doctrine"}
        assert files_under(project, ".lore/doctrines/default")
        assert files_under(project, ".lore/artifacts/default")
        assert not files_under(project, ".lore/watchers/default")
        assert not (project / ".lore" / "codex").exists()
        assert (project / ".lore" / "lore.db").is_file()
        assert health(project).exit_code == 0

    def test_a_users_own_claude_file_keeps_everything_but_lores_block(self, project):
        (project / "CLAUDE.md").write_text("# mine\n", encoding="utf-8")
        install(project, ALL_ON)
        assert "lore:begin" in (project / "CLAUDE.md").read_text(encoding="utf-8")
        text = (project / "CLAUDE.md").read_text(encoding="utf-8")
        assert text.startswith("# mine")


class TestSkillsGitignore:
    def test_every_profile_installs_a_skill_so_it_is_asked(self, project):
        for profile in (ALL_OFF, ALL_ON):
            plan = plan_init(project, agents=["claude"], **profile.as_answers())
            assert init.PROMPT_SKILLS_GITIGNORE in plan.prompts_needed

    def test_the_listing_is_written_beside_the_core_skills(self, project):
        install(project, ALL_OFF)
        assert (project / SKILLS_ROOT / ".gitignore").is_file()


LEGACY_FAMILY_SETS = [
    (),
    ("memory",),
    ("machinery",),
    ("workflow",),
    ("memory", "machinery"),
    ("memory", "workflow"),
    ("machinery", "workflow"),
    ("machinery", "memory", "workflow"),
]


class TestUpgradeFromTheEarlierConfigKeys:
    """An earlier release's `init-access-mode` and `init-skill-families`, once."""

    def _as_the_earlier_release_left_it(self, root: Path, mode: str, families) -> None:
        """Rewrite the project's record to the old form: two keys, and old manifest answers."""
        config = root / ".lore" / "config.toml"
        config.write_text(
            f'init-access-mode = "{mode}"\n'
            f"init-skill-families = {json.dumps(sorted(families))}\n",
            encoding="utf-8",
        )
        manifest = root / ".lore" / ".install-manifest.json"
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["answers"] = {
            "agents": ["claude"],
            "access_mode": mode,
            "skill_families": sorted(families),
            "skills_gitignore": "lore-only",
        }
        manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    @pytest.mark.parametrize("mode", ["native", "cli"])
    @pytest.mark.parametrize("families", LEGACY_FAMILY_SETS, ids=lambda f: "+".join(f) or "none")
    def test_the_same_behaviour_then_stable(self, project, mode, families):
        migrated = profile_from_legacy(mode, families)
        install(project, migrated)
        self._as_the_earlier_release_left_it(project, mode, families)

        first = plan_init(project, agents=["claude"])
        assert first.answers.profile == migrated
        if families:
            assert any("Migrated" in notice for notice in first.notices)
        # Same installed set: nothing is added or removed by the migration itself.
        assert [row for row in first.files if row.reported] == []
        apply_init(first)

        second = plan_init(project, agents=["claude"])
        assert second.notices == ()
        assert second.answers.profile == migrated
        assert [row for row in second.files if row.reported] == []
        assert skill_dirs(project) == set(skills.installed_skills(migrated))
        config = (project / ".lore" / "config.toml").read_text(encoding="utf-8")
        assert 'init-access-mode = "' + mode + '"' in config  # left in place, untouched

    def test_a_workflow_only_project_keeps_start_quest(self, project):
        migrated = profile_from_legacy("native", ("workflow",))
        install(project, migrated)
        self._as_the_earlier_release_left_it(project, "native", ("workflow",))
        apply_init(plan_init(project, agents=["claude"]))
        assert "start-quest" in skill_dirs(project)

    def test_a_project_with_only_the_old_config_keys_and_no_manifest(self, project):
        (project / ".lore").mkdir()
        (project / ".lore" / "config.toml").write_text(
            'init-access-mode = "cli"\ninit-skill-families = ["memory"]\n', encoding="utf-8"
        )
        plan = plan_init(project, agents=["claude"])
        assert plan.answers.profile == profile_from_legacy("cli", ("memory",))
        apply_init(plan)
        assert skill_dirs(project) == set(skills.installed_skills(plan.answers.profile))

    def test_the_retired_lines_stay_where_they_are_and_new_keys_follow(self, project):
        (project / ".lore").mkdir()
        (project / ".lore" / "config.toml").write_text(
            'init-access-mode = "cli"\ninit-skill-families = ["memory"]\n', encoding="utf-8"
        )
        apply_init(plan_init(project, agents=["claude"]))
        text = (project / ".lore" / "config.toml").read_text(encoding="utf-8")
        settings = [line for line in text.splitlines() if not line.startswith("#")]
        assert settings[:2] == ['init-access-mode = "cli"', 'init-skill-families = ["memory"]']
        assert 'init-route = "cli"' in settings
        assert "init-memory = true" in settings


class TestRunDoctrineIsCore:
    def test_a_harness_project_without_quests_gets_run_doctrine_and_no_start_quest(self, project):
        install(project, Profile(route=Route.HARNESS, memory=True, quests=False, watchers=False))
        assert "run-doctrine" in skill_dirs(project)
        assert "start-quest" not in skill_dirs(project)
        text = (project / SKILLS_ROOT / "run-doctrine" / "SKILL.md").read_text(encoding="utf-8")
        assert len(text.splitlines()) <= 100
        assert not [t for t in ("lore new", "lore needs", "lore show", "lore ready", "lore board", " -D ") if t in text]

    def test_turning_quests_on_adds_start_quest_beside_run_doctrine(self, project):
        install(project, Profile(route=Route.CLI, memory=False, quests=True, watchers=False).normalized())
        assert {"run-doctrine", "start-quest"} <= skill_dirs(project)
