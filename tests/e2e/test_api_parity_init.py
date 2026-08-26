"""E2E parity for `lore init`.

Spec: conceptual-workflows-python-api (lore codex show conceptual-workflows-python-api)

Tech Spec §10: "Init / migrations → tests/e2e/test_api_parity_init.py:
``run_init`` reachable through facade. Fixture changes ``cwd`` to
``tmp_path`` and calls ``run_init()`` (no-arg, uses ``Path.cwd()`` per
src/lore/init.py:131). AGENTS.md marker behaviour."

Review-Ledger CHANGED #9: ``run_init`` takes no arguments — caller must
``monkeypatch.chdir(tmp_path)`` first.

Red phase only.
"""

from __future__ import annotations



class TestRunInitReachableThroughFacade:
    """``lore.api.run_init`` is the facade entry — no args."""

    def test_run_init_callable_via_facade(self):
        from lore import api

        assert callable(api.run_init)

    def test_run_init_zero_args_creates_lore_dir(self, tmp_path, monkeypatch):
        from lore import api

        monkeypatch.chdir(tmp_path)
        # Review-Ledger CHANGED #9: run_init() takes NO arguments.
        api.run_init()
        assert (tmp_path / ".lore").is_dir()
        assert (tmp_path / ".lore" / "lore.db").is_file()

    def test_run_init_idempotent(self, tmp_path, monkeypatch):
        from lore import api

        monkeypatch.chdir(tmp_path)
        api.run_init()
        # Second call must not raise nor corrupt state.
        api.run_init()
        assert (tmp_path / ".lore" / "lore.db").is_file()


class TestRunInitProjectStructure:
    """`run_init` post-condition: .lore/ structure is fully seeded."""

    def test_init_creates_codex_directory(self, tmp_path, monkeypatch):
        from lore import api

        monkeypatch.chdir(tmp_path)
        api.run_init()
        assert (tmp_path / ".lore" / "codex").is_dir()

    def test_init_creates_doctrines_directory(self, tmp_path, monkeypatch):
        from lore import api

        monkeypatch.chdir(tmp_path)
        api.run_init()
        assert (tmp_path / ".lore" / "doctrines").is_dir()


class TestCliInitJsonParity:
    """``lore --json init`` envelope mirrors ``run_init`` outcome."""

    def test_cli_init_creates_project(self, tmp_path, monkeypatch):
        from click.testing import CliRunner

        from lore.cli import main

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0
        assert (tmp_path / ".lore" / "lore.db").is_file()


class TestInitPlanTypesOnThePythonSurface:
    """The plan vocabulary a library caller inspects before applying anything.

    Spec: conceptual-workflows-python-api — return-type contracts.
    """

    def test_plan_types_importable_and_constructible(self):
        from pathlib import Path

        from lore.initplan import (
            AccessMode,
            AgentTarget,
            FileAction,
            InitAnswers,
            InitPlan,
            InitResult,
            PlannedFile,
        )

        assert AgentTarget is not None
        assert PlannedFile is not None
        assert InitResult is not None
        assert FileAction.CREATE

        answers = InitAnswers(
            agents=(),
            access_mode=AccessMode.NATIVE,
            skill_families=(),
            on_existing_agent_file="append",
            skills_gitignore="lore-only",
            on_conflict="skip",
        )
        plan = InitPlan(
            project_root=Path("/tmp/x"),
            answers=answers,
            targets=(),
            files=(),
            prompts_needed=(),
            conflicts=(),
        )
        assert plan.has_changes is False
        assert plan.counts() == {}

    def test_plan_types_are_frozen(self):
        import dataclasses
        from pathlib import Path

        import pytest

        from lore.initplan import (
            AccessMode,
            AgentTarget,
            FileAction,
            InitAnswers,
            InitPlan,
            InitResult,
            PlannedFile,
        )

        answers = InitAnswers(
            agents=(),
            access_mode=AccessMode.CLI,
            skill_families=(),
            on_existing_agent_file="append",
            skills_gitignore="none",
            on_conflict="skip",
        )
        specimens = [
            (AgentTarget(id="none", label="None", instruction_file=None, skills_dir=None), "id"),
            (
                PlannedFile(
                    path="a",
                    action=FileAction.CREATE,
                    kind="owned",
                    source="skill:x",
                    digest=None,
                    detail=None,
                ),
                "path",
            ),
            (answers, "agents"),
            (
                InitPlan(
                    project_root=Path("/tmp/x"),
                    answers=answers,
                    targets=(),
                    files=(),
                    prompts_needed=(),
                    conflicts=(),
                ),
                "files",
            ),
            (
                InitResult(
                    project_root=Path("/tmp/x"),
                    messages=(),
                    applied=(),
                    skipped=(),
                    manifest_path=Path("/tmp/x/m.json"),
                ),
                "messages",
            ),
        ]
        for instance, field in specimens:
            with pytest.raises(dataclasses.FrozenInstanceError):
                setattr(instance, field, ())

    def test_importing_initplan_pulls_in_no_other_lore_module(self):
        import json
        import subprocess
        import sys

        probe = (
            "import sys, json;"
            "import lore.initplan;"
            "print(json.dumps(sorted(m for m in sys.modules if m == 'lore' or m.startswith('lore.'))))"
        )
        completed = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True,
            text=True,
            check=True,
        )
        loaded = json.loads(completed.stdout.strip().splitlines()[-1])
        assert loaded == ["lore", "lore.initplan"], (
            f"importing lore.initplan pulled in {loaded}; it must stay a stdlib-only leaf"
        )


class TestPlanAndApplyOnThePythonSurface:
    """The plan/apply split a library caller drives without a terminal.

    Spec: interactive-init-us-014, interactive-init-us-015.
    Anchor: conceptual-workflows-python-api — return-type contracts.
    """

    def test_plan_init_returns_a_plan_and_writes_nothing(self, tmp_path):
        from lore.init import plan_init
        from lore.initplan import InitPlan

        before = sorted(p.name for p in tmp_path.rglob("*"))
        plan = plan_init(project_root=tmp_path)
        assert isinstance(plan, InitPlan)
        assert plan.files
        assert sorted(p.name for p in tmp_path.rglob("*")) == before
        assert not (tmp_path / ".lore").exists()

    def test_apply_init_returns_a_result_and_produces_the_planned_paths(self, tmp_path):
        from lore.init import apply_init, plan_init
        from lore.initplan import FileAction, InitResult
        from lore.manifest import resolve_path

        plan = plan_init(project_root=tmp_path, agents=["claude"], skill_families=["memory"])
        result = apply_init(plan)
        assert isinstance(result, InitResult)
        for entry in plan.files:
            if entry.action in (FileAction.CREATE, FileAction.OVERWRITE, FileAction.SECTION):
                assert resolve_path(tmp_path, entry.path).is_file(), entry.path

    def test_run_init_still_takes_zero_arguments(self):
        import inspect

        from lore.init import run_init

        assert inspect.signature(run_init).parameters == {}

    def test_run_init_returns_a_list_not_a_tuple(self, tmp_path, monkeypatch):
        from lore.init import run_init

        monkeypatch.chdir(tmp_path)
        messages = run_init()
        assert type(messages) is list

    def test_run_init_matches_apply_of_plan(self, tmp_path, monkeypatch):
        from lore.init import apply_init, plan_init, run_init

        wrapper_dir = tmp_path / "wrapper"
        parts_dir = tmp_path / "parts"
        wrapper_dir.mkdir()
        parts_dir.mkdir()

        monkeypatch.chdir(wrapper_dir)
        wrapper = run_init()
        monkeypatch.chdir(parts_dir)
        parts = list(apply_init(plan_init()).messages)
        assert wrapper == parts

    def test_the_headless_run_adds_only_the_manifest_outside_the_pre_feature_set(
        self, tmp_path, monkeypatch
    ):
        from lore.init import run_init

        monkeypatch.chdir(tmp_path)
        run_init()
        assert (tmp_path / ".lore" / ".install-manifest.json").is_file()
        assert (tmp_path / ".lore" / "lore.db").is_file()
        assert (tmp_path / ".lore" / "LORE-AGENT.md").is_file()
        assert not (tmp_path / "CLAUDE.md").exists()
        assert not (tmp_path / "AGENTS.md").exists()


class TestInitValidatorsOnThePythonSurface:
    """The four initialisation validators are reachable from the facade.

    Spec: interactive-init-us-017 — Scenario 7. Every one of the twelve
    functions in ``validators.py`` is already in ``lore.api.__all__``;
    shipping three of the four new ones as importable-but-unexported would
    recreate the contract nobody honours that ADR-010 replaced.
    """

    INIT_VALIDATORS = (
        "validate_access_mode",
        "validate_skill_family",
        "validate_agent_id",
        "validate_agent_selection",
    )

    def test_all_four_importable_from_lore_api(self):
        from lore.api import (  # noqa: F401
            validate_access_mode,
            validate_agent_id,
            validate_agent_selection,
            validate_skill_family,
        )

        assert callable(validate_access_mode)
        assert callable(validate_skill_family)
        assert callable(validate_agent_id)
        assert callable(validate_agent_selection)

    def test_all_four_are_in_api_all(self):
        from lore import api

        missing = [name for name in self.INIT_VALIDATORS if name not in api.__all__]
        assert missing == [], f"missing from lore.api.__all__: {missing}"

    def test_each_is_the_identical_object_from_lore_validators(self):
        from lore import api, validators

        for name in self.INIT_VALIDATORS:
            assert getattr(api, name) is getattr(validators, name), name


# ---------------------------------------------------------------------------
# interactive-init-us-023 — the thirteen names and the release obligations
# Exercises: lore codex show conceptual-workflows-python-api — the public surface
# ---------------------------------------------------------------------------


THIRTEEN_NEW_NAMES: tuple[str, ...] = (
    # operational dataclasses
    "AccessMode",
    "FileAction",
    "AgentTarget",
    "PlannedFile",
    "InitAnswers",
    "InitPlan",
    "InitResult",
    # init functions
    "plan_init",
    "apply_init",
    # validators
    "validate_access_mode",
    "validate_skill_family",
    "validate_agent_id",
    "validate_agent_selection",
)

# The public surface as `0.9.0` shipped it. Nothing here may ever leave
# `lore.api.__all__` without an explicit breaking-change notice, so the list is
# frozen at the release boundary rather than recomputed.
PREVIOUS_RELEASE_ALL: frozenset[str] = frozenset(
    {
        "QuestStatus", "MissionStatus", "DependencyType", "Quest", "Mission",
        "Dependency", "BoardMessage", "Artifact", "CodexDocument", "DoctrineStep",
        "Doctrine", "Knight", "DoctrineListEntry", "GlossaryItem", "Watcher",
        "HealthIssue", "HealthReport", "SchemaIssue", "CodeBinding", "CodexBinding",
        "ImpactsError", "ImpactsResult", "GlossaryError", "ProjectNotFoundError",
        "ConflictingDepthFlags", "Config", "find_project_root", "validate_message",
        "validate_entity_id", "validate_mission_id", "validate_priority",
        "validate_name", "validate_group", "validate_quest_id_loose",
        "validate_chaos_threshold", "validate_binds_entry", "is_glob_pattern",
        "route_entity", "create_quest", "list_quests", "read_quest", "update_quest",
        "update_quest_full", "delete_quest", "close_quest", "create_mission",
        "list_missions", "list_missions_grouped", "read_mission", "update_mission",
        "update_mission_full", "delete_mission", "claim_mission", "claim_missions",
        "close_mission", "close_entities", "block_mission", "unblock_mission",
        "add_dependency", "remove_dependency", "add_dependencies",
        "remove_dependencies", "list_mission_depends_on", "list_mission_blocks",
        "get_all_dependencies_for_quest", "add_board_message", "list_board_messages",
        "delete_board_message", "get_dashboard_quests", "get_aggregate_stats",
        "get_deleted_at", "get_missions_for_quest", "get_mission_detail",
        "get_quest_detail", "delete_entity", "get_connection", "init_database",
        "get_ready_missions", "list_knights", "read_knight", "create_knight",
        "update_knight", "delete_knight", "list_doctrines", "read_doctrine",
        "create_doctrine", "update_doctrine", "delete_doctrine", "list_artifacts",
        "read_artifact", "create_artifact", "update_artifact", "delete_artifact",
        "list_watchers", "read_watcher", "create_watcher", "update_watcher",
        "delete_watcher", "update_frontmatter_fields", "list_codex",
        "search_documents", "read_document", "read_documents_with_glossary",
        "map_documents", "chaos_documents", "create_document", "update_document",
        "delete_document", "scan_glossary", "read_glossary_item", "search_glossary",
        "match_glossary", "create_glossary_item", "update_glossary_item",
        "delete_glossary_item", "impacts", "classify_token", "health_check",
        "load_schema", "validate_entity", "validate_entity_file",
        "resolve_merged_schema", "project_validator_for", "OverlayError",
        "run_init", "generate_reports", "load_config", "entity_location",
        "scan_rites", "read_rite", "search_rites", "create_rite", "update_rite",
        "delete_rite", "Rite", "RiteNode", "RiteBranch", "RiteConclusion",
        "SharedStep", "RiteError", "validate_rite_id",
    }
)


def test_thirteen_new_names_importable_from_lore_api():
    """Scenario 1 — every new name resolves through the facade."""
    from lore.api import (  # noqa: F401
        AccessMode,
        AgentTarget,
        FileAction,
        InitAnswers,
        InitPlan,
        InitResult,
        PlannedFile,
        apply_init,
        plan_init,
        validate_access_mode,
        validate_agent_id,
        validate_agent_selection,
        validate_skill_family,
    )
    from lore import api

    missing = [name for name in THIRTEEN_NEW_NAMES if name not in api.__all__]
    assert missing == [], f"missing from lore.api.__all__: {missing}"
    for name in THIRTEEN_NEW_NAMES:
        assert getattr(api, name) is not None


def test_no_name_removed_from_all():
    """Scenario 2 — the difference against 0.9.0 is exactly the thirteen."""
    from lore import api

    current = set(api.__all__)
    assert PREVIOUS_RELEASE_ALL - current == set(), (
        f"names left the public surface: {sorted(PREVIOUS_RELEASE_ALL - current)}"
    )
    assert current - PREVIOUS_RELEASE_ALL == set(THIRTEEN_NEW_NAMES)


def test_api_module_contains_no_def_or_class():
    """Scenario 4 — facade purity, unchanged by thirteen additions."""
    import ast
    from pathlib import Path

    import lore.api

    tree = ast.parse(Path(lore.api.__file__).read_text(encoding="utf-8"))
    offenders = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    assert offenders == [], f"api.py must define nothing; found {offenders}"


def test_underscore_aliases_include_prompts_agents_and_skills():
    """Scenario 5 — the CLI-only alias block is complete."""
    from lore import agents, api, prompts, skills

    assert api._prompts is prompts
    assert api._agents is agents
    assert api._skills is skills
    for name in ("_prompts", "_agents", "_skills"):
        assert name not in api.__all__


def test_run_init_still_takes_no_arguments():
    """FR-34 — the pinned pre-feature contract survives the additions."""
    import inspect

    from lore import api

    assert inspect.signature(api.run_init).parameters == {}


class TestChangelogReleaseObligation:
    """ADR-010: `CHANGELOG.md` and `lore.api.__all__` move together."""

    @staticmethod
    def _changelog_sections() -> list[tuple[str, str]]:
        """Return `(heading, body)` for each `## ` section, in file order."""
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
        sections: list[tuple[str, str]] = []
        heading: str | None = None
        body: list[str] = []
        for line in text.splitlines():
            if line.startswith("## "):
                if heading is not None:
                    sections.append((heading, "\n".join(body)))
                heading, body = line[3:].strip(), []
            elif heading is not None:
                body.append(line)
        if heading is not None:
            sections.append((heading, "\n".join(body)))
        return sections

    @classmethod
    def _released(cls) -> list[tuple[str, str]]:
        return [
            (heading, body)
            for heading, body in cls._changelog_sections()
            if not heading.startswith("[Unreleased]")
        ]

    def test_top_released_section_is_0_10_0(self):
        """Scenario 3 — the top-most released section."""
        heading, _ = self._released()[0]
        assert heading.startswith("[0.10.0]"), heading

    def test_entry_names_every_addition(self):
        """Scenario 3 — the `Added` section names what this release adds."""
        _, body = self._released()[0]
        added = body.split("### Changed")[0]
        for name in THIRTEEN_NEW_NAMES:
            assert f"`{name}`" in added, f"{name} not named in the Added section"
        for field in (
            "init_agents",
            "init_access_mode",
            "init_skill_families",
            "init_skills_gitignore",
        ):
            assert f"`{field}`" in added, f"Config field {field} not named"
        for key in (
            "init-agents",
            "init-access-mode",
            "init-skill-families",
            "init-skills-gitignore",
        ):
            assert f"`{key}`" in added, f"config key {key} not named"
        assert "`lore health --scope skills`" in added
        assert "`lore init`" in added

    def test_entry_names_the_changed_half(self):
        """Scenario 3 — the `Changed` section names the floors and the catalogue."""
        _, body = self._released()[0]
        assert "### Changed" in body
        changed = body.split("### Changed", 1)[1]
        assert "click" in changed
        assert "questionary" in changed
        assert "skill" in changed.lower()

    def test_entry_has_no_removed_section_and_no_breaking_change_block(self):
        """Scenario 3 — nothing leaves `__all__` and no signature narrows."""
        _, body = self._released()[0]
        assert "### Removed" not in body
        assert "BREAKING CHANGE:" not in body
