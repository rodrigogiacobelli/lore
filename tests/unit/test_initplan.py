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
    SEED_COUNT,
    SUMMARY_ORDER,
    AccessMode,
    AgentTarget,
    DesiredFile,
    FileAction,
    InitAnswers,
    InitPlan,
    InitResult,
    PlannedFile,
)

INITPLAN_SOURCE = Path(__file__).resolve().parents[2] / "src" / "lore" / "initplan.py"


def _answers(**overrides) -> InitAnswers:
    """Build an InitAnswers with every field defaulted, overridable per test."""
    fields = {
        "agents": (),
        "access_mode": AccessMode.NATIVE,
        "skill_families": (),
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
            "access_mode",
            "skill_families",
            "on_existing_agent_file",
            "skills_gitignore",
            "on_conflict",
        ]

    def test_init_answers_collections_are_tuples(self):
        answers = _answers(agents=("claude",), skill_families=("memory",))
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
    empty for a run that then overwrote an edited `.lore/knights/default/…`
    file. The CLI reads `render_plan` and Realm reads `has_changes`, and only
    one of them was being told.
    """

    def test_a_plan_with_seeded_paths_has_changes(self):
        plan = dataclasses.replace(_plan(), seeded=(".lore/knights/default/a.md",))
        assert plan.has_changes is True

    def test_the_seeded_paths_are_counted(self):
        plan = dataclasses.replace(
            _plan(), seeded=(".lore/knights/default/a.md", ".lore/config.toml")
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
