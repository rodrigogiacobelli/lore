"""Unit tests for lore.legacy_init — migration and deprecated-alias translation.

Anchor: conceptual-workflows-lore-init.

``lore.legacy_init`` is a pure leaf: it receives values and returns answers; it
reads no file and imports only ``lore.initplan``.
"""

from __future__ import annotations

import ast
import dataclasses
import itertools
from pathlib import Path

import pytest

from lore.initplan import Profile, Route
from lore.legacy_init import (
    AliasTranslation,
    infer_families,
    profile_from_interim,
    profile_from_legacy,
    translate_aliases,
)

LEGACY_SOURCE = Path(__file__).resolve().parents[2] / "src" / "lore" / "legacy_init.py"

FAMILY_SETS = [
    combo
    for size in range(4)
    for combo in itertools.combinations(("memory", "machinery", "workflow"), size)
]


class TestProfileFromLegacy:
    @pytest.mark.parametrize("mode", ["native", "cli"])
    @pytest.mark.parametrize("families", FAMILY_SETS)
    def test_memory_family_is_memory_with_every_opt_in(self, mode, families):
        profile = profile_from_legacy(mode, families)
        on = "memory" in families
        assert profile.memory is on
        assert (profile.memory_search, profile.memory_index, profile.memory_graph) == (on,) * 3

    @pytest.mark.parametrize("mode", ["native", "cli"])
    @pytest.mark.parametrize("families", FAMILY_SETS)
    def test_workflow_is_quests_and_machinery_is_watchers(self, mode, families):
        profile = profile_from_legacy(mode, families)
        assert profile.quests is ("workflow" in families)
        assert profile.watchers is ("machinery" in families)

    @pytest.mark.parametrize("mode", ["native", "cli"])
    def test_route_follows_the_access_mode_when_memory_is_installed(self, mode):
        expected = Route.HARNESS if mode == "native" else Route.CLI
        assert profile_from_legacy(mode, ("memory",)).route is expected
        assert profile_from_legacy(mode, ("memory", "machinery", "workflow")).route is expected

    @pytest.mark.parametrize("families", [("machinery",), ("workflow",), ("machinery", "workflow")])
    def test_entity_skills_without_memory_keep_the_cli(self, families):
        assert profile_from_legacy("native", families).route is Route.CLI

    def test_no_families_follows_the_access_mode(self):
        assert profile_from_legacy("native", ()).route is Route.HARNESS
        assert profile_from_legacy("cli", ()).route is Route.CLI

    @pytest.mark.parametrize("mode", ["native", "cli"])
    @pytest.mark.parametrize("families", FAMILY_SETS)
    def test_every_result_is_already_normalised(self, mode, families):
        profile = profile_from_legacy(mode, families)
        assert profile.normalized() == profile

    def test_full_install_in_cli_mode_equals_the_headless_defaults(self):
        assert profile_from_legacy("cli", ("memory", "machinery", "workflow")) == Profile()

    def test_unknown_access_mode_raises(self):
        with pytest.raises(ValueError, match="bogus"):
            profile_from_legacy("bogus", ())

    def test_unknown_family_raises(self):
        with pytest.raises(ValueError, match="nope"):
            profile_from_legacy("cli", ("nope",))


class TestProfileFromInterim:
    def _migrate(self, interim, **kw):
        return profile_from_interim(
            interim,
            memory_index=kw.get("memory_index", True),
            memory_graph=kw.get("memory_graph", True),
            quests=kw.get("quests", True),
        )

    def test_nothing_recorded_takes_the_interim_defaults(self):
        profile = self._migrate({})
        assert profile.route is Route.CLI
        assert profile.memory and profile.watchers and profile.quests
        assert not profile.memory_search  # memory-read defaulted to harness

    def test_memory_is_on_when_either_route_is_not_off(self):
        read_only = self._migrate({"init-memory-read": "harness", "init-memory-write": "off"})
        assert read_only.memory
        off = self._migrate({"init-memory-read": "off", "init-memory-write": "off"})
        assert not off.memory
        assert not (off.memory_search or off.memory_index or off.memory_graph)

    def test_search_follows_a_cli_read_route(self):
        assert self._migrate({"init-memory-read": "cli"}).memory_search
        assert not self._migrate({"init-memory-read": "harness"}).memory_search

    def test_index_graph_and_quests_are_carried_over(self):
        profile = self._migrate({}, memory_index=False, memory_graph=False, quests=False)
        assert not (profile.memory_index or profile.memory_graph or profile.quests)

    def test_watchers_are_on_when_either_route_is_not_off(self):
        both_off = self._migrate({"init-watchers-read": "off", "init-watchers-write": "off"})
        assert not both_off.watchers
        assert self._migrate({"init-watchers-read": "off", "init-watchers-write": "cli"}).watchers

    def test_route_is_cli_when_any_remaining_route_was_cli(self):
        harness_everywhere = {
            f"init-{f}-{a}": "harness"
            for f in ("memory", "doctrines", "artifacts", "watchers")
            for a in ("read", "write")
        }
        assert self._migrate(harness_everywhere).route is Route.HARNESS
        assert self._migrate({**harness_everywhere, "init-doctrines-write": "cli"}).route is Route.CLI

    def test_a_cli_route_that_was_off_does_not_count(self):
        off_and_harness = {
            f"init-{f}-{a}": "off" if f != "memory" else "harness"
            for f in ("memory", "doctrines", "artifacts", "watchers")
            for a in ("read", "write")
        }
        assert self._migrate(off_and_harness).route is Route.HARNESS

    def test_the_result_is_normalised(self):
        profile = self._migrate({"init-memory-read": "off", "init-memory-write": "off"})
        assert profile.normalized() == profile


class TestTranslateAliases:
    def test_neither_alias_translates_to_nothing(self):
        result = translate_aliases(access_mode=None, skill_families=None, current_route=Route.CLI)
        assert result.answers == {} and result.notices == ()

    @pytest.mark.parametrize(("mode", "route"), [("native", Route.HARNESS), ("cli", Route.CLI)])
    def test_access_sets_the_route_only(self, mode, route):
        result = translate_aliases(access_mode=mode, skill_families=None, current_route=Route.CLI)
        assert result.answers == {"route": route}

    def test_access_notice_names_the_alias_and_the_replacement_flag(self):
        result = translate_aliases(access_mode="cli", skill_families=None, current_route=Route.CLI)
        (notice,) = result.notices
        assert "--access cli" in notice and "deprecated" in notice and "--route cli" in notice

    def test_skills_alias_yields_the_complete_legacy_profile(self):
        result = translate_aliases(
            access_mode=None, skill_families=("memory", "workflow"), current_route=Route.CLI
        )
        expected = profile_from_legacy("cli", ("memory", "workflow"))
        assert Profile.from_answers(
            {k: (v.value if isinstance(v, Route) else v) for k, v in result.answers.items()}
        ) == expected

    def test_skills_alias_takes_the_mode_from_the_current_route(self):
        harness = translate_aliases(
            access_mode=None, skill_families=("memory",), current_route=Route.HARNESS
        )
        assert harness.answers["route"] is Route.HARNESS

    def test_explicit_access_beats_the_current_route_beside_skills(self):
        result = translate_aliases(
            access_mode="cli", skill_families=("memory",), current_route=Route.HARNESS
        )
        assert result.answers["route"] is Route.CLI

    def test_skills_none_turns_every_optional_feature_off(self):
        result = translate_aliases(access_mode=None, skill_families=(), current_route=Route.CLI)
        assert not any(
            result.answers[name] for name in ("memory", "quests", "watchers")
        )
        assert "none" in result.notices[0]

    def test_skills_notice_names_the_alias_and_the_families(self):
        result = translate_aliases(
            access_mode=None, skill_families=("memory", "workflow"), current_route=Route.CLI
        )
        (notice,) = result.notices
        assert "--skills memory workflow" in notice and "deprecated" in notice

    def test_both_aliases_give_two_notices(self):
        result = translate_aliases(
            access_mode="cli", skill_families=("memory",), current_route=Route.HARNESS
        )
        assert any("--skills" in n for n in result.notices)
        assert any("--access" in n for n in result.notices)

    def test_the_result_is_frozen(self):
        assert dataclasses.is_dataclass(AliasTranslation)
        assert AliasTranslation.__dataclass_params__.frozen


class TestInferFamilies:
    def test_maps_recorded_skill_ids_to_their_families(self):
        assert infer_families(["retrieve-memory"]) == ("memory",)
        assert infer_families(["update-doctrine", "inquest"]) == ("machinery", "workflow")

    def test_accepts_the_source_form_of_a_recorded_id(self):
        assert infer_families(["skill:store-memory"]) == ("memory",)

    def test_ignores_ids_it_does_not_know(self):
        assert infer_families(["nothing", "agent-instructions:claude"]) == ()

    def test_empty_input_is_empty(self):
        assert infer_families([]) == ()

    def test_the_id_lists_mirror_the_catalogue_legacy_families(self):
        from lore.legacy_init import LEGACY_FAMILY_SKILLS
        from lore.skills import load_catalogue

        shipped = load_catalogue()["legacy_families"]
        assert {family: set(ids) for family, ids in LEGACY_FAMILY_SKILLS.items()} == {
            family: set(row["skills"]) for family, row in shipped.items()
        }


class TestModuleBoundary:
    def test_imports_only_initplan_from_lore(self):
        tree = ast.parse(LEGACY_SOURCE.read_text(encoding="utf-8"))
        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("lore"):
                if node.module != "lore.initplan":
                    offenders.append(node.module)
            elif isinstance(node, ast.Import):
                offenders += [a.name for a in node.names if a.name.startswith("lore")]
        assert offenders == []
