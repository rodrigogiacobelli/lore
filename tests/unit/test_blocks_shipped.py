"""Structural tests of the shipped block tree, catalogue and grant table.

Spec: adaptive-init-spec (Parts 2.15 and 5). Anchor:
conceptual-workflows-lore-init.

Nothing here reads a word of a shipped block (decisions-006-no-seed-content-tests):
the tests assert the properties the block set is built to have — it lints clean,
every profile renders within its caps, no rendering mentions a command whose
capability is off, every skill a rendering names is installed — for every
fixture profile and for every valid profile.
"""

from __future__ import annotations

import re

import pytest

from lore import blocks, skills
from lore.blocklint import lint, lint_rendered
from lore.initplan import Profile
from tests.unit.conftest import (
    FIXTURE_PROFILES,
    FULL,
    HARNESS_BARE,
    EVERY_VALID_PROFILE,
)

ALL_PROFILES = [*FIXTURE_PROFILES.values(), *EVERY_VALID_PROFILE]
ALL_IDS = [*FIXTURE_PROFILES, *(f"valid-{i}" for i in range(len(EVERY_VALID_PROFILE)))]

_SLASH_SKILL = re.compile(r"(?<![\w/.-])/([a-z][a-z0-9-]*)(?![\w/.-])")


class TestShippedTreeIsLintClean:
    def test_lint_finds_nothing(self):
        assert lint() == []

    def test_every_grant_row_names_a_command_the_extractor_can_produce(self):
        known_first_words = set(blocks._GROUP_WORDS) | set(blocks._TOP_LEVEL_WORDS)
        known_first_words |= {"health", *blocks._GLOBAL_FLAGS}
        for phrase in blocks.load_grants():
            assert phrase.split(" ")[0] in known_first_words, phrase

    def test_every_block_lives_in_the_directory_of_its_feature(self):
        for block in blocks.load_blocks().values():
            assert block.path.split("/")[0] == block.feature

    def test_the_catalogue_names_ten_skills(self):
        assert len(skills.load_catalogue()["skills"]) == 11


class TestRenderedProperties:
    @pytest.mark.parametrize("profile", ALL_PROFILES, ids=ALL_IDS)
    def test_every_rendering_is_within_its_caps_and_leaks_nothing(self, profile):
        assert lint_rendered(profile) == []

    @pytest.mark.parametrize("profile", ALL_PROFILES, ids=ALL_IDS)
    def test_the_instruction_text_is_within_the_predicted_bound(self, profile):
        catalogue = skills.load_catalogue()
        table = blocks.load_blocks()
        for name, document in catalogue["documents"].items():
            text = skills.render_document(name, profile)
            if text is None:
                continue
            predicted = blocks.max_lines(document["blocks"], table)
            assert len(text.splitlines()) <= predicted
            assert len(text.splitlines()) <= document["max_lines"]

    @pytest.mark.parametrize("profile", ALL_PROFILES, ids=ALL_IDS)
    def test_every_skill_a_rendering_names_is_installed(self, profile):
        installed = set(skills.installed_skills(profile))
        known = {entry["id"] for entry in skills.load_catalogue()["skills"]}
        texts = [
            skills.render_document(name, profile)
            for name in skills.load_catalogue()["documents"]
        ]
        for skill_id in installed:
            for relative in skills.skill_files(skill_id, profile):
                texts.append(skills.render_skill_file(skill_id, relative, profile))
        for text in filter(None, texts):
            named = set(_SLASH_SKILL.findall(text)) & known
            named |= {m for m in re.findall(r"`([a-z][a-z0-9-]*)`", text) if m in known}
            assert named <= installed, sorted(named - installed)

    @pytest.mark.parametrize("profile", ALL_PROFILES, ids=ALL_IDS)
    def test_installed_skills_are_exactly_those_with_a_surviving_body_block(self, profile):
        catalogue = skills.load_catalogue()
        table = blocks.load_blocks()
        expected = tuple(
            entry["id"]
            for entry in catalogue["skills"]
            if blocks.assemble(entry["files"][0]["blocks"], profile, blocks=table)
        )
        assert skills.installed_skills(profile) == expected
        desired = skills.desired_files(targets=[], profile=profile)
        assert {path.split("/")[2] for path in desired} == set(expected)

    @pytest.mark.parametrize("profile", ALL_PROFILES, ids=ALL_IDS)
    def test_the_instruction_text_exists_for_every_profile(self, profile):
        assert skills.render_document("lore-agent", profile) is not None
        assert skills.render_document("getting-started", profile) is not None

    def test_the_bare_core_installs_the_doctrine_and_artifact_skills_only(self):
        assert skills.installed_skills(HARNESS_BARE) == ("update-doctrine", "update-artifact", "run-doctrine")

    def test_the_full_lore_installs_every_catalogue_skill(self):
        assert skills.installed_skills(FULL) == tuple(
            entry["id"] for entry in skills.load_catalogue()["skills"]
        )

    def test_only_store_memory_ships_reference_files(self):
        for entry in skills.load_catalogue()["skills"]:
            extra = [row["path"] for row in entry["files"] if row["path"] != skills.SKILL_FILE]
            assert extra == ([] if entry["id"] != "store-memory" else extra), entry["id"]
            if entry["id"] == "store-memory":
                assert sorted(extra) == [
                    "references/codex-doc.md",
                    "references/rite.md",
                    "references/source.md",
                ]

    def test_the_skills_table_markers_appear_exactly_when_a_skill_is_installed(self):
        for profile in ALL_PROFILES:
            text = skills.render_document("lore-agent", profile)
            if text is None:
                continue
            has_markers = "<!-- lore:skills-table -->" in text
            assert has_markers == bool(skills.installed_skills(profile))

    def test_random_profiles_are_normalised_and_varied(self):
        assert all(isinstance(p, Profile) and p.normalized() == p for p in EVERY_VALID_PROFILE)
        assert len(set(EVERY_VALID_PROFILE)) == 72


_HEADING = re.compile(r"^(#{1,6}) ")
_STEP_HEADING = re.compile(r"^#{2,3} (?:Step )?(\d+)[.:]")
_DEFAULT_PATH = re.compile(r"\.lore/artifacts/default/[\w./-]+\.md")
_ARTIFACT_ID = re.compile(r"lore artifact show ([\w-]+)")


def _rendered_texts(profile: Profile) -> list[tuple[str, str]]:
    """Every instruction document and skill file *profile* writes, as ``(where, text)``."""
    texts = [
        (f"document {name}", text)
        for name in skills.load_catalogue()["documents"]
        if (text := skills.render_document(name, profile)) is not None
    ]
    for skill_id in skills.installed_skills(profile):
        for relative in skills.skill_files(skill_id, profile):
            texts.append((f"{skill_id}/{relative}", skills.render_skill_file(skill_id, relative, profile) or ""))
    return texts


def _outside_fences(text: str) -> list[str]:
    """The lines outside code fences; a fence itself stays as one placeholder line."""
    lines, inside = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            if not inside:
                lines.append("<code>")
            inside = not inside
            continue
        if not inside:
            lines.append(line)
    return lines


class TestRenderedStructure:
    """Properties of how the blocks join, never of what they say."""

    @pytest.mark.parametrize("profile", ALL_PROFILES, ids=ALL_IDS)
    def test_no_heading_is_followed_by_the_end_of_the_text_or_a_same_level_heading(self, profile):
        for where, text in _rendered_texts(profile):
            lines = _outside_fences(text)
            for index, line in enumerate(lines):
                match = _HEADING.match(line)
                if not match:
                    continue
                following = next((ln for ln in lines[index + 1 :] if ln.strip()), None)
                assert following is not None, f"{where}: heading '{line}' ends the text"
                other = _HEADING.match(following)
                assert not other or len(other.group(1)) > len(match.group(1)), (
                    f"{where}: heading '{line}' is empty"
                )

    @pytest.mark.parametrize("profile", ALL_PROFILES, ids=ALL_IDS)
    def test_numbered_steps_run_without_a_gap(self, profile):
        for where, text in _rendered_texts(profile):
            steps = [
                int(m.group(1)) for ln in _outside_fences(text) if (m := _STEP_HEADING.match(ln))
            ]
            if steps:
                assert steps == list(range(steps[0], steps[0] + len(steps))), f"{where}: steps {steps}"

    @pytest.mark.parametrize("profile", ALL_PROFILES, ids=ALL_IDS)
    def test_no_paragraph_repeats_within_a_file(self, profile):
        for where, text in _rendered_texts(profile):
            paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 60]
            assert len(paragraphs) == len(set(paragraphs)), f"{where}: a paragraph repeats"


class TestRenderedReferencesAreSeeded:
    """A text points only at a Lore default the profile actually seeds."""

    @staticmethod
    def _seeded_ids() -> dict[str, str]:
        from pathlib import Path

        defaults = Path(skills.__file__).parent / "defaults" / "artifacts"
        found = {}
        for path in defaults.rglob("*.md"):
            match = re.search(r"^id: (\S+)", path.read_text(encoding="utf-8"), re.MULTILINE)
            if match:
                found[match.group(1)] = ".lore/artifacts/default/" + path.relative_to(defaults).as_posix()
        return found

    @pytest.mark.parametrize("profile", ALL_PROFILES, ids=ALL_IDS)
    def test_every_named_default_artifact_is_seeded_for_the_profile(self, profile):
        from lore import init

        seeded = set(init.seeded_paths(profile))
        by_id = self._seeded_ids()
        for where, text in _rendered_texts(profile):
            for path in _DEFAULT_PATH.findall(text):
                assert path in seeded, f"{where} points at {path}, which this profile does not seed"
            for artifact_id in _ARTIFACT_ID.findall(text):
                assert by_id.get(artifact_id) in seeded, (
                    f"{where} names artifact '{artifact_id}', which this profile does not seed"
                )


_INSTALLED = {
    **FIXTURE_PROFILES,
    **{f"valid-{i}": EVERY_VALID_PROFILE[i] for i in range(0, len(EVERY_VALID_PROFILE), 15)},
}


class TestInstallsVerify:
    """An install of any profile is clean to `lore health --scope skills` and stable."""

    @pytest.mark.parametrize("profile", list(_INSTALLED.values()), ids=list(_INSTALLED))
    def test_the_installed_skills_audit_clean_and_a_second_run_changes_nothing(self, tmp_path, profile):
        from lore.api import apply_init, health_check, plan_init

        answers = {"agents": ["claude"], **profile.as_answers()}
        apply_init(plan_init(tmp_path, **answers))

        report = health_check(tmp_path, scope=["skills"])
        assert list(report.issues) == []
        assert [row for row in plan_init(tmp_path, **answers).files if row.reported] == []


_APPARATUS = ("lore new", "lore needs", "lore list", "lore show", "lore ready", "lore board", " -D ", "q-xxxx")


class TestRunDoctrineIsCore:
    """run-doctrine is core and quest-free; start-quest is the quest flow and needs Quests."""

    @staticmethod
    def _text(skill, profile):
        text = skills.render_skill_file(skill, "SKILL.md", profile)
        assert text is not None
        return text

    @pytest.mark.parametrize("profile", ALL_PROFILES, ids=ALL_IDS)
    def test_run_doctrine_is_installed_everywhere_within_the_line_cap(self, profile):
        assert "run-doctrine" in skills.installed_skills(profile)
        assert len(self._text("run-doctrine", profile).splitlines()) <= 100

    @pytest.mark.parametrize("profile", ALL_PROFILES, ids=ALL_IDS)
    def test_run_doctrine_never_uses_the_quest_apparatus(self, profile):
        text = self._text("run-doctrine", profile)
        assert not [token for token in _APPARATUS if token in text]

    @pytest.mark.parametrize("profile", ALL_PROFILES, ids=ALL_IDS)
    def test_start_quest_is_installed_only_with_quests(self, profile):
        assert ("start-quest" in skills.installed_skills(profile)) == bool(profile.quests)

    @pytest.mark.parametrize("profile", [p for p in ALL_PROFILES if p.quests], ids=lambda p: repr(p)[:60])
    def test_start_quest_creates_the_quest(self, profile):
        assert "lore new quest" in self._text("start-quest", profile)

    @pytest.mark.parametrize("profile", ALL_PROFILES, ids=ALL_IDS)
    def test_the_instruction_file_points_at_exactly_one_way_to_run_a_doctrine(self, profile):
        text = skills.render_document("lore-agent", profile)
        assert text is not None
        assert text.count("`/run-doctrine`") == (0 if profile.quests else 1)
        assert text.count("`/start-quest`") == (1 if profile.quests else 0)
