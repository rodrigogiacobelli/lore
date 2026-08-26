"""The rules `plan_init` / `apply_init` enforce for a caller with no CLI.

Spec: `lore codex show decisions-011-api-self-contained` — a rule the CLI
enforces and the API does not is a rule Realm does not have. Realm reaches
initialisation through `lore.api`, so every guard `lore init` applies before it
writes has to live below the click layer or it protects nobody who matters.

Round 5 of adversarial API smoke testing found the four shapes covered here:

* a `reconfigure=True` call that supplies none of the four recorded answers is
  the "uninstall" run `--reconfigure` refuses at the terminal, and nothing
  stopped it on the API path;
* a relative `project_root` was stored verbatim, so a plan built in one
  directory applied itself in whichever directory the caller was standing in at
  apply time;
* `InitPlan.counts()` tallied rows `render_plan` and `has_changes` exclude, so
  the only tally on the public type said "17 changes" for a plan that changes
  nothing — and, once that was fixed, went on excluding the seventy files every
  run refreshes in place, so it said "no changes" for a run that rewrites them
  (round 7, N4);
* every hostile argument shape reached the interpreter's own `TypeError` or
  `KeyError` from inside rather than a rejection naming the parameter.

`apply_init` re-reading disk before it writes is the fifth: the conflict
machinery exists to turn a silent overwrite into a reported one, and it ran at
plan time only.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from lore import api
from lore.init import apply_init, plan_init, render_plan
from lore.initplan import SEED_COUNT, FileAction, InitPlan, PlannedFile


# ---------------------------------------------------------------------------
# A1 — reconfigure has a safety gate on the API path, not only on the CLI's
# ---------------------------------------------------------------------------


class TestReconfigureNeedsItsAnswers:
    """`reconfigure=True` means "ask me again", and a library call cannot ask."""

    def test_bare_reconfigure_is_rejected(self, tmp_path):
        apply_init(plan_init(tmp_path, agents=["claude"], skill_families=["all"]))

        with pytest.raises(ValueError) as excinfo:
            plan_init(tmp_path, reconfigure=True)

        message = str(excinfo.value)
        for parameter in ("agents", "access_mode", "skill_families", "skills_gitignore"):
            assert parameter in message, message

    def test_a_partially_answered_reconfigure_names_only_what_is_missing(self, tmp_path):
        apply_init(plan_init(tmp_path, agents=["claude"]))

        with pytest.raises(ValueError) as excinfo:
            plan_init(
                tmp_path,
                reconfigure=True,
                agents=["claude"],
                access_mode="cli",
            )

        message = str(excinfo.value)
        assert "skill_families" in message
        assert "skills_gitignore" in message
        assert "agents" not in message
        assert "access_mode" not in message

    def test_all_four_answers_make_reconfigure_legal(self, tmp_path):
        apply_init(plan_init(tmp_path, agents=["claude"]))

        plan = plan_init(
            tmp_path,
            reconfigure=True,
            agents=["claude"],
            access_mode="cli",
            skill_families=["memory"],
            skills_gitignore="none",
        )

        assert plan.answers.agents == ("claude",)
        assert plan.answers.skill_families == ("memory",)

    def test_the_gate_is_reachable_through_the_facade(self, tmp_path):
        apply_init(api.plan_init(tmp_path, agents=["claude"]))

        with pytest.raises(ValueError):
            api.plan_init(tmp_path, reconfigure=True)

    def test_the_cli_and_the_api_read_one_table(self, tmp_path):
        from lore.init import missing_recorded_answers

        assert missing_recorded_answers({}) == (
            "agents",
            "access_mode",
            "skill_families",
            "skills_gitignore",
        )
        assert missing_recorded_answers({"agents": ["claude"], "access_mode": "cli"}) == (
            "skill_families",
            "skills_gitignore",
        )


# ---------------------------------------------------------------------------
# A2 — a manifest path that leaves the project is a corrupt manifest
# ---------------------------------------------------------------------------


class TestManifestPathsStayInsideTheProject:
    """`manifest._parse` type-checks every field; it has to check paths too."""

    def _install(self, project: Path) -> Path:
        apply_init(plan_init(project))
        return project / ".lore" / ".install-manifest.json"

    def _with_row(self, manifest_file: Path, path: str) -> None:
        payload = json.loads(manifest_file.read_text(encoding="utf-8"))
        payload["files"].append(
            {
                "path": path,
                "kind": "owned",
                "source": "skill:retired-thing",
                "hash": "sha256:deadbeef",
            }
        )
        manifest_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @pytest.mark.parametrize(
        "escaping",
        ["../VICTIM.txt", "a/../../VICTIM.txt", "/etc/passwd"],
    )
    def test_parse_rejects_an_escaping_path(self, tmp_path, escaping):
        from lore import manifest

        manifest_file = self._install(tmp_path)
        self._with_row(manifest_file, escaping)
        payload = json.loads(manifest_file.read_text(encoding="utf-8"))

        with pytest.raises(ValueError) as excinfo:
            manifest._parse(payload)

        assert escaping in str(excinfo.value)

    def test_an_escaping_row_never_becomes_a_removal(self, tmp_path, capsys):
        victim = tmp_path.parent / "PLAN_VICTIM.txt"
        victim.write_text("precious\n", encoding="utf-8")
        project = tmp_path / "project"
        project.mkdir()

        manifest_file = self._install(project)
        self._with_row(manifest_file, "../PLAN_VICTIM.txt")

        plan = plan_init(project, on_conflict="overwrite")
        assert not [
            row for row in plan.files if row.action is FileAction.REMOVE
            and "PLAN_VICTIM" in row.path
        ]

        apply_init(plan)
        assert victim.is_file()

    def test_a_fabricated_plan_row_is_refused_before_any_write(self, tmp_path):
        victim = tmp_path.parent / "ROW_VICTIM.txt"
        victim.write_text("precious\n", encoding="utf-8")
        project = tmp_path / "project"
        project.mkdir()

        plan = plan_init(project)
        evil = PlannedFile(
            path="../ROW_VICTIM.txt",
            action=FileAction.CREATE,
            kind="owned",
            source="skill:evil",
            digest="sha256:00",
            detail=None,
        )

        with pytest.raises(ValueError) as excinfo:
            apply_init(dataclasses.replace(plan, files=(evil,)))

        assert "../ROW_VICTIM.txt" in str(excinfo.value)
        assert victim.read_text(encoding="utf-8") == "precious\n"


# ---------------------------------------------------------------------------
# N3 — a removal is as constrained as a write
# ---------------------------------------------------------------------------
#
# Containment is real: nothing leaves the project root. *Inside* it, the write
# side and the removal side were held to different standards, and the
# destructive one was the permissive one — `_reject_unplannable_rows` refuses a
# write to any path this release does not produce, while a `REMOVE` row could
# name any file in the project and have it unlinked:
#
#     {"path": ".git/config", "kind": "owned", "source": "skill:gone", ...}
#     Removed .git/config — no longer installed here            (exit 0)


class TestARemovalOnlyTargetsAPathLoreInstalls:
    def _install(self, project: Path) -> Path:
        apply_init(plan_init(project, agents=["claude"], skill_families=["memory"]))
        return project / ".lore" / ".install-manifest.json"

    def _with_row(self, manifest_file: Path, path: str) -> None:
        payload = json.loads(manifest_file.read_text(encoding="utf-8"))
        payload["files"].append(
            {
                "path": path,
                "kind": "owned",
                "source": "skill:gone",
                "hash": "sha256:deadbeef",
            }
        )
        manifest_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @pytest.mark.parametrize(
        "victim", [".git/config", "src/main.py", "README.md", ".env"]
    )
    def test_a_manifest_row_naming_a_project_file_never_removes_it(
        self, tmp_path, capsys, victim
    ):
        target = tmp_path / victim
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("precious\n", encoding="utf-8")

        manifest_file = self._install(tmp_path)
        self._with_row(manifest_file, victim)
        with open(manifest_file, encoding="utf-8") as handle:
            row_hash = json.load(handle)["files"][-1]["hash"]
        assert row_hash

        plan = plan_init(tmp_path, agents=["claude"], skill_families=["memory"])
        apply_init(plan)

        assert target.read_text(encoding="utf-8") == "precious\n"

    def test_the_corrupt_manifest_is_reported_and_the_run_completes(
        self, tmp_path, capsys
    ):
        """Fail-soft, like every other corrupt manifest: a warning, not a stop."""
        manifest_file = self._install(tmp_path)
        self._with_row(manifest_file, ".git/config")
        capsys.readouterr()

        result = apply_init(plan_init(tmp_path, agents=["claude"], skill_families=["memory"]))

        assert result.manifest_path.is_file()
        assert "unreadable install manifest" in capsys.readouterr().err

    def test_a_fabricated_removal_row_is_refused_before_any_write(self, tmp_path):
        victim = tmp_path / ".git" / "config"
        victim.parent.mkdir(parents=True)
        victim.write_text("precious\n", encoding="utf-8")

        plan = plan_init(tmp_path, agents=["claude"], skill_families=["memory"])
        evil = PlannedFile(
            path=".git/config",
            action=FileAction.REMOVE,
            kind="owned",
            source="skill:gone",
            digest=None,
            detail="no longer installed here",
        )

        with pytest.raises(ValueError) as excinfo:
            apply_init(dataclasses.replace(plan, files=(evil,)))

        assert ".git/config" in str(excinfo.value)
        assert victim.read_text(encoding="utf-8") == "precious\n"

    def test_a_real_removal_row_still_applies(self, tmp_path):
        """The rule refuses paths this release never installs, and nothing else."""
        apply_init(plan_init(tmp_path, agents=["claude"], skill_families=["memory"]))
        installed = tmp_path / ".claude" / "skills"
        assert list(installed.iterdir())

        apply_init(plan_init(tmp_path, agents=["claude"], skill_families=["none"]))

        assert not (installed.is_dir() and any(
            child.is_dir() for child in installed.iterdir()
        ))


# ---------------------------------------------------------------------------
# A3 — the plan names the directory it describes, absolutely
# ---------------------------------------------------------------------------


class TestProjectRootIsResolvedAtPlanTime:
    """A plan a caller has inspected is the plan that gets applied — anywhere."""

    def test_a_relative_root_is_resolved(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        plan = plan_init(".")
        assert plan.project_root.is_absolute()
        assert plan.project_root == tmp_path.resolve()

    def test_an_empty_root_is_resolved(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert plan_init("").project_root == tmp_path.resolve()

    def test_apply_writes_where_the_plan_was_built(self, tmp_path, monkeypatch):
        planned_in = tmp_path / "planned"
        applied_from = tmp_path / "elsewhere"
        planned_in.mkdir()
        applied_from.mkdir()

        monkeypatch.chdir(planned_in)
        plan = plan_init(".")
        monkeypatch.chdir(applied_from)
        result = apply_init(plan)

        assert (planned_in / ".lore").is_dir()
        assert not (applied_from / ".lore").exists()
        assert result.project_root == planned_in.resolve()

    def test_render_plan_names_an_absolute_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert render_plan(plan_init(".")).startswith(f"Plan for {tmp_path.resolve()} ")


# ---------------------------------------------------------------------------
# A4 — counts() is the tally render_plan prints
# ---------------------------------------------------------------------------


class TestCountsAgreesWithTheSummary:
    """The only tally on the public type has to be the truthful one."""

    def test_a_repeat_run_reconciles_nothing(self, tmp_path):
        apply_init(plan_init(tmp_path, agents=["claude"]))
        plan = plan_init(tmp_path, agents=["claude"])

        assert {
            name: number for name, number in plan.counts().items() if name != SEED_COUNT
        } == {}

    def test_a_repeat_run_still_reports_the_files_it_refreshes(self, tmp_path):
        """Round 7, N4. The reconciled half of a second run is empty and the run
        still rewrites the seeded tree, the config and the manifest — so "no
        changes" was a plan describing a different run from the one that ran."""
        apply_init(plan_init(tmp_path, agents=["claude"]))
        plan = plan_init(tmp_path, agents=["claude"])

        assert plan.counts()[SEED_COUNT] == len(plan.seeded)
        assert plan.has_changes is True

    def test_counts_matches_the_rendered_tally(self, tmp_path):
        plan = plan_init(tmp_path, agents=["claude"], skill_families=["memory"])
        tally = {
            name: number for name, number in plan.counts().items() if name != SEED_COUNT
        }

        rendered = render_plan(plan)
        counts_line = [line for line in rendered.splitlines() if " · " in line][-1]
        printed = dict(
            (name, int(number))
            for number, name in (
                part.split() for part in counts_line.strip().split(" · ")
            )
        )
        assert {name: printed[name] for name in tally} == tally
        assert sum(printed.values()) == sum(tally.values())

    def test_the_seed_bucket_is_the_number_the_render_prints(self, tmp_path):
        from lore.init import SEEDED_HEADING

        plan = plan_init(tmp_path, agents=["claude"], skill_families=["memory"])

        headings = [
            line for line in render_plan(plan).splitlines() if SEEDED_HEADING in line
        ]
        assert headings == [
            f"  {SEEDED_HEADING} ({plan.counts()[SEED_COUNT]} files):"
        ]

    def test_both_kinds_of_conflict_count_as_conflicts(self, tmp_path):
        from lore.initplan import InitAnswers, AccessMode

        answers = InitAnswers(
            agents=(),
            access_mode=AccessMode.NATIVE,
            skill_families=(),
            on_existing_agent_file="append",
            skills_gitignore="none",
            on_conflict="skip",
        )
        rows = (
            PlannedFile(
                path="a",
                action=FileAction.CONFLICT,
                kind="owned",
                source="skill:x",
                digest=None,
                detail="is a symlink",
            ),
            PlannedFile(
                path="b",
                action=FileAction.CONFLICT,
                kind="owned",
                source="skill:y",
                digest=None,
                detail="not installed by Lore",
            ),
        )
        plan = InitPlan(
            project_root=Path("/tmp/x"),
            answers=answers,
            targets=(),
            files=rows,
            prompts_needed=(),
        )
        assert plan.counts() == {"conflict": 2}


# ---------------------------------------------------------------------------
# A6 — a plan is checked against the tree it is applied to
# ---------------------------------------------------------------------------


class TestApplyRecheckesDiskBeforeItWrites:
    """The conflict machinery's promise, held at the moment of the write."""

    def test_a_file_edited_after_planning_is_not_overwritten(self, tmp_path):
        apply_init(plan_init(tmp_path, agents=["claude"], access_mode="native"))
        plan = plan_init(tmp_path, agents=["claude"], access_mode="cli")

        skill = tmp_path / ".claude" / "skills" / "inquest" / "SKILL.md"
        assert [row for row in plan.files if row.path.endswith("inquest/SKILL.md")]
        skill.write_text("MY IMPORTANT LOCAL EDIT\n", encoding="utf-8")

        result = apply_init(plan)

        assert skill.read_text(encoding="utf-8") == "MY IMPORTANT LOCAL EDIT\n"
        assert [row for row in result.skipped if row.path.endswith("inquest/SKILL.md")]

    def test_the_refusal_names_the_file_and_the_repair(self, tmp_path):
        apply_init(plan_init(tmp_path, agents=["claude"], access_mode="native"))
        plan = plan_init(tmp_path, agents=["claude"], access_mode="cli")

        skill = tmp_path / ".claude" / "skills" / "inquest" / "SKILL.md"
        skill.write_text("MY IMPORTANT LOCAL EDIT\n", encoding="utf-8")

        messages = "\n".join(apply_init(plan).messages)
        assert ".claude/skills/inquest/SKILL.md" in messages
        assert "changed since the plan was computed" in messages

    def test_a_file_created_after_planning_is_not_clobbered(self, tmp_path):
        plan = plan_init(tmp_path, agents=["claude"], skill_families=["memory"])
        created = [row for row in plan.files if row.action is FileAction.CREATE]
        assert created

        target = tmp_path / created[0].path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("SOMEBODY GOT HERE FIRST\n", encoding="utf-8")

        result = apply_init(plan)

        assert target.read_text(encoding="utf-8") == "SOMEBODY GOT HERE FIRST\n"
        assert [row for row in result.skipped if row.path == created[0].path]

    def test_a_removal_whose_file_changed_is_kept(self, tmp_path):
        apply_init(plan_init(tmp_path, agents=["claude"], skill_families=["all"]))
        plan = plan_init(tmp_path, agents=["claude"], skill_families=["memory"])
        removals = [row for row in plan.files if row.action is FileAction.REMOVE]
        assert removals

        doomed = tmp_path / removals[0].path
        doomed.write_text("EDITED AFTER THE PLAN\n", encoding="utf-8")

        result = apply_init(plan)

        assert doomed.is_file()
        assert doomed.read_text(encoding="utf-8") == "EDITED AFTER THE PLAN\n"
        assert [row for row in result.skipped if row.path == removals[0].path]

    def test_an_untouched_tree_applies_every_row(self, tmp_path):
        plan = plan_init(tmp_path, agents=["claude"], skill_families=["memory"])
        result = apply_init(plan)

        assert result.skipped == ()
        assert len(result.applied) == len(plan.files)


# ---------------------------------------------------------------------------
# A7 — the API boundary rejects, it does not crash from inside
# ---------------------------------------------------------------------------


class TestArgumentShapesAreRejectedAtTheBoundary:
    """Every wrong-typed argument names the parameter it arrived on."""

    @pytest.mark.parametrize("value", [5, True, 3.5, object()])
    def test_a_non_iterable_agents_names_the_parameter(self, tmp_path, value):
        with pytest.raises(ValueError) as excinfo:
            plan_init(tmp_path, agents=value)
        assert "agents" in str(excinfo.value)

    @pytest.mark.parametrize("value", [5, True, 3.5, object()])
    def test_a_non_iterable_skill_families_names_the_parameter(self, tmp_path, value):
        with pytest.raises(ValueError) as excinfo:
            plan_init(tmp_path, skill_families=value)
        assert "skill_families" in str(excinfo.value)

    def test_a_bare_string_agents_is_not_iterated_per_character(self, tmp_path):
        with pytest.raises(ValueError) as excinfo:
            plan_init(tmp_path, agents="claude")
        message = str(excinfo.value)
        assert "agents" in message
        assert "'c'" not in message

    def test_a_bare_string_skill_families_is_not_iterated_per_character(self, tmp_path):
        with pytest.raises(ValueError) as excinfo:
            plan_init(tmp_path, skill_families="all")
        message = str(excinfo.value)
        assert "skill_families" in message
        assert "'a'" not in message

    def test_bytes_are_rejected_like_a_string(self, tmp_path):
        with pytest.raises(ValueError) as excinfo:
            plan_init(tmp_path, agents=b"claude")
        assert "agents" in str(excinfo.value)

    @pytest.mark.parametrize("value", ["yes", 0, 1, ""])
    def test_reconfigure_is_not_truthiness_coerced(self, tmp_path, value):
        with pytest.raises(ValueError) as excinfo:
            plan_init(tmp_path, reconfigure=value)
        assert "reconfigure" in str(excinfo.value)

    def test_the_one_boolean_left_still_accepts_true_and_false(self, tmp_path):
        assert plan_init(tmp_path, reconfigure=False) is not None
        with pytest.raises(ValueError):
            plan_init(tmp_path, reconfigure="yes")

    def test_a_sequence_of_agent_ids_still_works(self, tmp_path):
        assert plan_init(tmp_path, agents=["claude"]).answers.agents == ("claude",)
        assert plan_init(tmp_path, agents=("claude",)).answers.agents == ("claude",)
        assert plan_init(tmp_path, agents=[]).answers.agents == ()
        assert plan_init(tmp_path, agents=None) is not None

    @pytest.mark.parametrize("value", [None, "hello", 42, {"files": ()}, object()])
    def test_apply_init_rejects_a_non_plan_with_a_typeerror(self, value):
        with pytest.raises(TypeError) as excinfo:
            apply_init(value)
        assert "InitPlan" in str(excinfo.value)

    def test_a_plan_row_naming_a_path_the_plan_cannot_produce_is_refused(self, tmp_path):
        plan = plan_init(tmp_path, agents=["claude"], skill_families=["memory"])
        stray = PlannedFile(
            path=".claude/skills/not-a-skill/SKILL.md",
            action=FileAction.CREATE,
            kind="owned",
            source="skill:not-a-skill",
            digest="sha256:00",
            detail=None,
        )

        with pytest.raises(ValueError) as excinfo:
            apply_init(dataclasses.replace(plan, files=(stray,)))

        assert ".claude/skills/not-a-skill/SKILL.md" in str(excinfo.value)


# ---------------------------------------------------------------------------
# A5 — the plan names every path the run writes (landed with the Seed listing)
# ---------------------------------------------------------------------------


class TestThePlanNamesEveryWrite:
    """The plan is the consent surface, so nothing may be written unnamed."""

    def test_the_seeded_trees_are_named(self, tmp_path):
        plan = plan_init(tmp_path, agents=["claude"])
        seeded = set(plan.seeded)

        assert any(path.startswith(".lore/knights/default/") for path in seeded)
        assert any(path.startswith(".lore/doctrines/default/") for path in seeded)
        assert ".lore/.install-manifest.json" in seeded
        assert ".lore/config.toml" in seeded

    def test_every_file_the_run_writes_appears_in_the_plan(self, tmp_path):
        plan = plan_init(tmp_path, agents=["claude"], skill_families=["memory"])
        named = {row.path for row in plan.files} | set(plan.seeded)

        apply_init(plan)

        on_disk = {
            path.relative_to(tmp_path).as_posix()
            for path in tmp_path.rglob("*")
            if path.is_file()
        }
        assert on_disk - named == set()
