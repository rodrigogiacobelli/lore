"""Unit tests for lore.initplan — the plan and result vocabulary.

Anchor: conceptual-workflows-python-api — return-type contracts for the
operational dataclasses a Python caller receives from ``plan_init`` and
``apply_init``.

``lore.initplan`` is a stdlib-only leaf module: it sits below ``init.py``,
``reconcile.py`` and ``skills.py`` so those three can construct its values
without a circular import (standards-dependency-inversion).
"""

from __future__ import annotations

import ast
import dataclasses
from enum import StrEnum
from pathlib import Path

import pytest

from lore.initplan import (
    CAPABILITY_FEATURE,
    CORE_FEATURES,
    FILE_FEATURES,
    QUESTIONS,
    SEED_COUNT,
    SUMMARY_ORDER,
    AccessMode,
    AgentTarget,
    Capability,
    DesiredFile,
    Feature,
    FileAction,
    InitAnswers,
    InitPlan,
    InitResult,
    PlannedFile,
    Profile,
    Route,
    question_flag,
    question_key,
    question_kwarg,
)
from tests.unit.conftest import (
    CLI_BARE,
    FIXTURE_PROFILES,
    FULL,
    HARNESS_BARE,
    HARNESS_MEMORY,
    HARNESS_QUESTS,
    EVERY_VALID_PROFILE,
)

INITPLAN_SOURCE = Path(__file__).resolve().parents[2] / "src" / "lore" / "initplan.py"


def _answers(**overrides) -> InitAnswers:
    """Build an InitAnswers with every field defaulted, overridable per test."""
    fields = {
        "agents": (),
        "profile": Profile(),
        "on_existing_agent_file": "append",
        "skills_gitignore": "lore-only",
        "on_conflict": "skip",
    }
    fields.update(overrides)
    return InitAnswers(**fields)


def _planned(path: str, action: FileAction) -> PlannedFile:
    return PlannedFile(
        path=path,
        action=action,
        kind="owned",
        source="skill:example",
        digest=None,
        detail=None,
    )


def _plan(*files: PlannedFile) -> InitPlan:
    return InitPlan(
        project_root=Path("/tmp/x"),
        answers=_answers(),
        targets=(),
        files=files,
        prompts_needed=(),
        conflicts=(),
    )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestAccessMode:
    def test_is_a_str_enum(self):
        assert issubclass(AccessMode, StrEnum)

    def test_has_exactly_cli_and_native(self):
        assert {m.name for m in AccessMode} == {"CLI", "NATIVE"}

    def test_member_values(self):
        assert AccessMode.CLI == "cli"
        assert AccessMode.NATIVE == "native"


class TestFileAction:
    def test_is_a_str_enum(self):
        assert issubclass(FileAction, StrEnum)

    def test_has_exactly_the_five_planner_actions(self):
        assert {m.name for m in FileAction} == {
            "CREATE",
            "OVERWRITE",
            "SECTION",
            "REMOVE",
            "CONFLICT",
        }

    def test_every_value_is_its_lower_cased_name(self):
        for member in FileAction:
            assert member.value == member.name.lower()


# ---------------------------------------------------------------------------
# Dataclass field shapes
# ---------------------------------------------------------------------------


class TestDataclassFieldNames:
    def test_agent_target_fields(self):
        names = [f.name for f in dataclasses.fields(AgentTarget)]
        assert names == ["id", "label", "instruction_file", "skills_dir"]

    def test_agent_target_accepts_none_for_both_conventions(self):
        target = AgentTarget(id="none", label="None", instruction_file=None, skills_dir=None)
        assert target.instruction_file is None
        assert target.skills_dir is None

    def test_planned_file_fields(self):
        names = [f.name for f in dataclasses.fields(PlannedFile)]
        assert names == [
            "path",
            "action",
            "kind",
            "source",
            "digest",
            "detail",
            "reported",
            "observed",
        ]

    def test_planned_file_accepts_none_digest_and_detail(self):
        entry = _planned(".claude/skills/x/SKILL.md", FileAction.REMOVE)
        assert entry.digest is None
        assert entry.detail is None

    def test_init_answers_fields(self):
        names = [f.name for f in dataclasses.fields(InitAnswers)]
        assert names == [
            "agents",
            "profile",
            "on_existing_agent_file",
            "skills_gitignore",
            "on_conflict",
        ]

    def test_init_answers_collections_are_tuples(self):
        answers = _answers(agents=("claude",))
        assert isinstance(answers.agents, tuple)
        assert isinstance(answers.skill_families, tuple)

    def test_init_plan_fields(self):
        names = [f.name for f in dataclasses.fields(InitPlan)]
        assert names == [
            "project_root",
            "answers",
            "targets",
            "files",
            "prompts_needed",
            "seeded",
            "unstated_uninstall",
            "conflicts",
            "notices",
        ]

    def test_init_result_fields(self):
        names = [f.name for f in dataclasses.fields(InitResult)]
        assert names == ["project_root", "messages", "applied", "skipped", "manifest_path"]

    def test_init_result_messages_is_a_tuple_of_str(self):
        result = InitResult(
            project_root=Path("/tmp/x"),
            messages=("Initialized Lore project:",),
            applied=(),
            skipped=(),
            manifest_path=Path("/tmp/x/.lore/.install-manifest.json"),
        )
        assert isinstance(result.messages, tuple)
        assert all(isinstance(m, str) for m in result.messages)


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------


class TestEveryDataclassIsFrozen:
    ALL = (AgentTarget, DesiredFile, PlannedFile, InitAnswers, InitPlan, InitResult)

    def test_dataclass_params_declare_frozen(self):
        for cls in self.ALL:
            assert dataclasses.is_dataclass(cls), f"{cls.__name__} is not a dataclass"
            assert cls.__dataclass_params__.frozen, f"{cls.__name__} is not frozen"

    def test_mutating_any_field_raises(self):
        instances = {
            AgentTarget: (
                AgentTarget(id="claude", label="Claude Code", instruction_file=None, skills_dir=None),
                "id",
            ),
            PlannedFile: (_planned("a", FileAction.CREATE), "path"),
            InitAnswers: (_answers(), "on_conflict"),
            InitPlan: (_plan(), "files"),
            InitResult: (
                InitResult(
                    project_root=Path("/tmp/x"),
                    messages=(),
                    applied=(),
                    skipped=(),
                    manifest_path=Path("/tmp/x/m.json"),
                ),
                "messages",
            ),
        }
        for cls, (instance, field) in instances.items():
            with pytest.raises(dataclasses.FrozenInstanceError):
                setattr(instance, field, ())


# ---------------------------------------------------------------------------
# Derived members
# ---------------------------------------------------------------------------


class TestInitPlanCounts:
    def test_empty_plan_counts_is_empty(self):
        assert _plan().counts() == {}

    def test_tallies_per_action_and_omits_zeroes(self):
        plan = _plan(
            _planned("a", FileAction.CREATE),
            _planned("b", FileAction.CREATE),
            _planned("c", FileAction.REMOVE),
        )
        assert plan.counts() == {"create": 2, "remove": 1}

    def test_keys_are_file_action_values_not_repr(self):
        plan = _plan(_planned("a", FileAction.OVERWRITE))
        assert list(plan.counts()) == ["overwrite"]


class TestInitPlanHasChanges:
    def test_false_for_empty_plan(self):
        assert _plan().has_changes is False

    def test_false_when_every_entry_is_reported_but_never_written(self):
        plan = _plan(
            _planned("a", FileAction.CONFLICT),
            _planned("b", FileAction.CONFLICT),
        )
        assert plan.has_changes is False

    @pytest.mark.parametrize(
        "action",
        [FileAction.CREATE, FileAction.OVERWRITE, FileAction.SECTION, FileAction.REMOVE],
    )
    def test_true_for_any_writing_action(self, action):
        assert _plan(_planned("a", action)).has_changes is True


class TestTheSeededTreeCountsAsAChange:
    """`plan.seeded` names ~70 files every run rewrites in place.

    Round 5's defect 10 put them in the plan's listing and round 7's N4 found
    the other half still missing: `has_changes` was False and `counts()` was
    empty for a run that then overwrote an edited `.lore/doctrines/default/…`
    file. The CLI reads `render_plan` and Realm reads `has_changes`, and only
    one of them was being told.
    """

    def test_a_plan_with_seeded_paths_has_changes(self):
        plan = dataclasses.replace(_plan(), seeded=(".lore/doctrines/default/a.md",))
        assert plan.has_changes is True

    def test_the_seeded_paths_are_counted(self):
        plan = dataclasses.replace(
            _plan(), seeded=(".lore/doctrines/default/a.md", ".lore/config.toml")
        )
        assert plan.counts()[SEED_COUNT] == 2

    def test_the_seed_bucket_is_absent_when_nothing_is_seeded(self):
        assert SEED_COUNT not in _plan().counts()

    def test_the_reconciled_buckets_are_unaffected(self):
        plan = dataclasses.replace(
            _plan(_planned("a", FileAction.CREATE)), seeded=(".lore/config.toml",)
        )
        assert plan.counts() == {"create": 1, SEED_COUNT: 1}

    def test_the_tally_line_still_reports_the_reconciled_half(self):
        """The seeded block prints its own count under the tally, so the tally
        line stays what it has always been — the reconciled decisions."""
        assert SEED_COUNT not in SUMMARY_ORDER


class TestInitPlanConflicts:
    def test_empty_when_no_entry_conflicts(self):
        plan = _plan(_planned("a", FileAction.CREATE))
        assert plan.conflicts == ()

    def test_holds_exactly_the_conflict_subset_in_order(self):
        first = _planned("a", FileAction.CONFLICT)
        second = _planned("c", FileAction.CONFLICT)
        plan = _plan(first, _planned("b", FileAction.CREATE), second)
        assert plan.conflicts == (first, second)

    def test_there_is_no_second_conflict_subset(self):
        """`KEEP` is gone, and so is the tuple that held its rows.

        A file Lore installed and the project edited is overwritten or removed
        now, so the plan has one conflict set rather than two — the one for
        paths holding something Lore did not install and may not take.
        """
        assert not hasattr(_plan(), "retired_edits")
        assert not hasattr(FileAction, "KEEP")


# ---------------------------------------------------------------------------
# Module purity
# ---------------------------------------------------------------------------


class TestModuleImportPurity:
    def test_module_imports_no_lore_module(self):
        tree = ast.parse(INITPLAN_SOURCE.read_text(encoding="utf-8"), filename=str(INITPLAN_SOURCE))
        offenders: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders += [a.name for a in node.names if a.name.split(".")[0] == "lore"]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.split(".")[0] == "lore":
                    offenders.append(module)
        assert offenders == [], (
            f"src/lore/initplan.py imports lore modules {offenders}; it must stay a stdlib-only leaf"
        )


# ---------------------------------------------------------------------------
# The reported flag
#
# The reconciliation table has two columns — the action and whether the row is
# worth telling the human about. A file already byte-identical to what Lore
# would write is recorded in the manifest but changes nothing, so it must not
# count as a change or appear in the summary.
# ---------------------------------------------------------------------------


class TestPlannedFileReported:
    def test_defaults_to_reported(self):
        assert _planned("a", FileAction.CREATE).reported is True

    def test_can_be_declared_unreported(self):
        entry = dataclasses.replace(_planned("a", FileAction.CREATE), reported=False)
        assert entry.reported is False

    def test_an_unreported_writing_row_is_not_a_change(self):
        entry = dataclasses.replace(_planned("a", FileAction.CREATE), reported=False)
        assert _plan(entry).has_changes is False

    def test_a_reported_writing_row_beside_an_unreported_one_is_a_change(self):
        quiet = dataclasses.replace(_planned("a", FileAction.CREATE), reported=False)
        loud = _planned("b", FileAction.CREATE)
        assert _plan(quiet, loud).has_changes is True


# ---------------------------------------------------------------------------
# DesiredFile — what this release would write, before anything is compared
# ---------------------------------------------------------------------------


class TestDesiredFile:
    def test_fields(self):
        names = [f.name for f in dataclasses.fields(DesiredFile)]
        assert names == ["path", "kind", "source", "content"]

    def test_is_frozen(self):
        entry = DesiredFile(path="a", kind="owned", source="skill:a", content=b"x")
        assert DesiredFile.__dataclass_params__.frozen
        with pytest.raises(dataclasses.FrozenInstanceError):
            entry.path = "b"

    def test_content_is_the_rendered_bytes(self):
        entry = DesiredFile(path="a", kind="owned", source="skill:a", content=b"rendered\n")
        assert isinstance(entry.content, bytes)


# ---------------------------------------------------------------------------
# The answer model: one route, yes/no opt-ins
# ---------------------------------------------------------------------------

BOOL_FIELDS = (
    "memory",
    "memory_search",
    "memory_index",
    "memory_graph",
    "quests",
    "watchers",
)


class TestVocabulary:
    def test_enums_are_str_enums_with_plain_values(self):
        for enum in (Feature, Route, Capability):
            assert issubclass(enum, StrEnum)
        assert [r.value for r in Route] == ["harness", "cli"]
        assert [f.value for f in Feature] == [
            "memory",
            "doctrines",
            "artifacts",
            "watchers",
            "quests",
        ]
        assert [c.value for c in Capability] == [
            "validate",
            "memory-search",
            "memory-index",
            "memory-graph",
        ]

    def test_core_features_are_doctrines_and_artifacts(self):
        assert CORE_FEATURES == (Feature.DOCTRINES, Feature.ARTIFACTS)

    def test_file_features_are_the_four_with_a_route(self):
        assert FILE_FEATURES == (
            Feature.MEMORY,
            Feature.DOCTRINES,
            Feature.ARTIFACTS,
            Feature.WATCHERS,
        )

    def test_validate_is_core_and_the_rest_belong_to_memory(self):
        assert CAPABILITY_FEATURE[Capability.VALIDATE] is None
        for capability in Capability:
            if capability is not Capability.VALIDATE:
                assert CAPABILITY_FEATURE[capability] is Feature.MEMORY


class TestQuestions:
    def test_question_order_is_the_prompt_order(self):
        assert QUESTIONS == (
            "route",
            "memory",
            "memory-search",
            "memory-index",
            "memory-graph",
            "quests",
            "watchers",
        )

    def test_kwarg_key_and_flag_derive_from_the_id(self):
        assert question_kwarg("memory-search") == "memory_search"
        assert question_key("memory-search") == "init-memory-search"
        assert question_flag("memory-search") == "--memory-search"
        assert question_kwarg("route") == "route"
        assert question_key("route") == "init-route"
        assert question_flag("route") == "--route"

    def test_every_kwarg_is_a_profile_field(self):
        fields = {f.name for f in dataclasses.fields(Profile)}
        assert {question_kwarg(q) for q in QUESTIONS} == fields

    def test_unknown_question_id_raises(self):
        with pytest.raises(ValueError, match="nope"):
            question_kwarg("nope")


class TestProfileDefaults:
    def test_defaults_are_the_full_lore(self):
        profile = Profile()
        assert profile.route is Route.CLI
        for name in BOOL_FIELDS:
            assert getattr(profile, name) is True

    def test_is_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            Profile().quests = False  # type: ignore[misc]

    def test_equal_profiles_hash_equal(self):
        assert hash(Profile()) == hash(Profile())
        assert len({Profile(), Profile(), HARNESS_BARE}) == 2


class TestFeatureOn:
    def test_doctrines_and_artifacts_are_always_on(self):
        for profile in FIXTURE_PROFILES.values():
            assert profile.feature_on(Feature.DOCTRINES)
            assert profile.feature_on(Feature.ARTIFACTS)

    @pytest.mark.parametrize("feature", ["memory", "watchers", "quests"])
    def test_optional_features_follow_their_flag(self, feature):
        assert Profile(**{feature: True}).feature_on(Feature(feature))
        assert not Profile(**{feature: False}).feature_on(Feature(feature))


class TestHas:
    def test_validate_is_always_on(self):
        for profile in FIXTURE_PROFILES.values():
            assert profile.has(Capability.VALIDATE)

    def test_a_memory_capability_needs_memory_and_its_flag(self):
        assert FULL.has(Capability.MEMORY_INDEX)
        assert not HARNESS_MEMORY.has(Capability.MEMORY_GRAPH)
        stale = Profile(memory=False, memory_search=True)
        assert not stale.has(Capability.MEMORY_SEARCH)


class TestDerivedFlags:
    def test_link_is_quests(self):
        assert HARNESS_QUESTS.link_on
        assert not HARNESS_BARE.link_on
        assert FULL.link_on

    def test_cli_taught_when_route_is_cli_or_a_cli_only_thing_is_on(self):
        assert not HARNESS_BARE.cli_taught
        assert not HARNESS_MEMORY.cli_taught
        assert CLI_BARE.cli_taught
        assert HARNESS_QUESTS.cli_taught
        assert dataclasses.replace(HARNESS_MEMORY, memory_search=True).cli_taught
        assert dataclasses.replace(HARNESS_MEMORY, memory_graph=True).cli_taught

    def test_cli_taught_ignores_a_stale_capability_of_memory_off(self):
        assert not Profile(
            route=Route.HARNESS, memory=False, quests=False, watchers=False
        ).cli_taught


class TestNormalized:
    def test_drops_memory_capabilities_when_memory_is_off(self):
        normal = Profile(memory=False).normalized()
        assert not (normal.memory_search or normal.memory_index or normal.memory_graph)
        assert normal.quests and normal.watchers

    def test_is_idempotent_and_leaves_a_normal_profile_alone(self):
        assert FULL.normalized() == FULL
        for profile in EVERY_VALID_PROFILE:
            assert profile.normalized() == profile

    def test_unnormalised_profile_behaves_like_its_normal_form(self):
        raw = Profile(route=Route.HARNESS, memory=False, quests=False, memory_graph=True)
        normal = raw.normalized()
        assert raw.cli_taught == normal.cli_taught
        assert raw.link_on == normal.link_on
        assert raw.summary() == normal.summary()


class TestApplies:
    @pytest.mark.parametrize("profile", FIXTURE_PROFILES.values(), ids=FIXTURE_PROFILES.keys())
    def test_only_the_memory_capability_questions_are_conditional(self, profile):
        for question in QUESTIONS:
            expected = profile.memory if question.startswith("memory-") else True
            assert profile.applies(question) == expected

    def test_unknown_question_raises(self):
        with pytest.raises(ValueError, match="nope"):
            FULL.applies("nope")


class TestAsAnswersRoundTrip:
    def test_has_seven_plain_values_keyed_by_kwarg(self):
        answers = FULL.as_answers()
        assert set(answers) == {question_kwarg(q) for q in QUESTIONS}
        assert answers["route"] == "cli"
        assert type(answers["route"]) is str
        assert answers["quests"] is True

    @pytest.mark.parametrize("profile", FIXTURE_PROFILES.values(), ids=FIXTURE_PROFILES.keys())
    def test_round_trips_each_fixture(self, profile):
        assert Profile.from_answers(profile.as_answers()) == profile

    def test_round_trips_every_valid_profile(self):
        for profile in EVERY_VALID_PROFILE:
            assert Profile.from_answers(profile.as_answers()) == profile

    def test_partial_mapping_fills_defaults(self):
        assert Profile.from_answers({"route": "harness"}) == Profile(route=Route.HARNESS)

    def test_unknown_route_token_raises(self):
        with pytest.raises(ValueError, match="native"):
            Profile.from_answers({"route": "native"})

    def test_off_is_not_a_route(self):
        with pytest.raises(ValueError, match="off"):
            Profile.from_answers({"route": "off"})

    def test_non_bool_answer_raises(self):
        with pytest.raises(ValueError, match="memory_search"):
            Profile.from_answers({"memory_search": "yes"})

    def test_unknown_key_raises(self):
        with pytest.raises(ValueError, match="bogus"):
            Profile.from_answers({"bogus": True})


class TestSummary:
    def test_lists_route_and_what_is_on(self):
        profile = Profile(
            route=Route.HARNESS, memory_graph=False, watchers=False
        ).normalized()
        assert profile.summary() == "route: harness \u00b7 memory +search +index \u00b7 quests"

    def test_the_bare_core_says_so(self):
        assert HARNESS_BARE.summary() == "route: harness"


class TestInitAnswersDerivedProperties:
    def _answers(self, profile: Profile) -> InitAnswers:
        return _answers(profile=profile)

    def test_access_mode_follows_the_route(self):
        assert self._answers(HARNESS_BARE).access_mode is AccessMode.NATIVE
        assert self._answers(CLI_BARE).access_mode is AccessMode.CLI

    @pytest.mark.parametrize(
        ("profile", "families"),
        [
            (FULL, ("machinery", "memory", "workflow")),
            (HARNESS_BARE, ("machinery",)),
            (HARNESS_MEMORY, ("machinery", "memory")),
            (HARNESS_QUESTS, ("machinery", "workflow")),
        ],
    )
    def test_skill_families_follow_the_features(self, profile, families):
        assert self._answers(profile).skill_families == families


class TestPlanNotices:
    def test_notices_default_to_empty(self):
        assert _plan().notices == ()

    def test_notices_are_carried(self):
        plan = dataclasses.replace(_plan(), notices=("one", "two"))
        assert plan.notices == ("one", "two")
