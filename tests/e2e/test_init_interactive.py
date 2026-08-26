"""E2E tests for interactive `lore init` — prompts, flags, summary, TTY gate.

Spec: conceptual-workflows-init-interactive
(lore codex show conceptual-workflows-init-interactive)

No test here drives `prompt_toolkit`. The prompt library is a dependency, not
a subject: every scenario monkeypatches the functions in `lore.prompts` and
forces `sys.stdout.isatty()` to `True`, which is the gate `cli.py` evaluates
and nothing else in Lore ever consults.

The `SpaceSeparatedChoice` parser cases live here rather than in a unit file
because they need a `CliRunner`, and `technical-test-guidelines` §2 and §8 put
anything that invokes the CLI in `tests/e2e/`.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import click
import click.testing
import pytest
from click.testing import CliRunner

from lore.cli import main


CLI_SOURCE = Path(__file__).resolve().parents[2] / "src" / "lore" / "cli.py"

LORE_BEGIN = "<!-- lore:begin -->"

PROMPT_NAMES = (
    "ask_agents",
    "ask_access_mode",
    "ask_skill_families",
    "ask_existing_agent_file",
    "ask_skills_gitignore",
    "ask_on_conflict",
    "ask_confirm_plan",
)

DEFAULT_ANSWERS = {
    "ask_agents": ["claude"],
    "ask_access_mode": "native",
    "ask_skill_families": ["memory", "workflow"],
    "ask_existing_agent_file": "append",
    "ask_skills_gitignore": "lore-only",
    "ask_on_conflict": "skip",
    "ask_confirm_plan": True,
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def terminal(monkeypatch):
    """Force `sys.stdout.isatty()` to True for the duration of one CLI run.

    `CliRunner` hands the command a pipe, which is the headless case. Patching
    the runner's own stream class is how a test says "a person is watching"
    without giving `cli.py` a seam that only tests use.
    """
    stream = getattr(click.testing, "_NamedTextIOWrapper", None)
    assert stream is not None, "click.testing stream class moved; update this fixture"
    monkeypatch.setattr(stream, "isatty", lambda self: True, raising=False)


class PromptLog:
    """Every prompt call, in order, with the arguments it was rendered from."""

    def __init__(self):
        self.calls: list[tuple[str, tuple, dict]] = []

    @property
    def names(self) -> list[str]:
        return [name for name, _, _ in self.calls]

    def args_for(self, name: str) -> tuple[tuple, dict]:
        for called, args, kwargs in self.calls:
            if called == name:
                return args, kwargs
        raise AssertionError(f"{name} was never called; saw {self.names}")


@pytest.fixture()
def prompts(monkeypatch):
    """Install canned answers for every prompt and record the call order."""

    def install(**overrides):
        from lore import prompts as prompts_module

        answers = dict(DEFAULT_ANSWERS)
        answers.update(overrides)
        log = PromptLog()

        for name in PROMPT_NAMES:

            def stub(*args, _name=name, **kwargs):
                log.calls.append((_name, args, kwargs))
                return answers[_name]

            monkeypatch.setattr(prompts_module, name, stub)
        return log

    return install


@pytest.fixture()
def no_prompts(monkeypatch):
    """Make any prompt call a test failure — the assertion for a silent run."""
    from lore import prompts as prompts_module

    for name in PROMPT_NAMES:
        monkeypatch.setattr(
            prompts_module,
            name,
            lambda *a, _n=name, **k: pytest.fail(f"{_n} fired but must not"),
        )


def _snapshot(root: Path) -> dict[str, tuple]:
    """Every path under *root* with its size and mtime — a write detector."""
    snapshot = {}
    for path in sorted(root.rglob("*")):
        key = path.relative_to(root).as_posix()
        if path.is_dir():
            snapshot[key] = ("dir", None, None)
        else:
            stat = path.stat()
            snapshot[key] = ("file", stat.st_size, stat.st_mtime_ns)
    return snapshot


def _run(tmp_path, monkeypatch, *argv):
    monkeypatch.chdir(tmp_path)
    return CliRunner().invoke(main, ["init", *argv])


def _init_params():
    return {param.name: param for param in main.commands["init"].params}


def _retire_an_edited_skill(tmp_path, monkeypatch) -> Path:
    """Leave the project holding one edited file this release no longer ships.

    Installs, then records a manifest row for a path that is not in the desired
    set and whose bytes do not match what was recorded — which is the
    retired-and-edited row, reached without waiting for a real retirement.
    """
    assert _run(tmp_path, monkeypatch, "--agent", "none", "--yes").exit_code == 0

    stale = tmp_path / ".lore" / "skills" / "gone-in-this-release" / "SKILL.md"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("# mine now\n", encoding="utf-8")

    installed = tmp_path / ".lore" / ".install-manifest.json"
    payload = json.loads(installed.read_text(encoding="utf-8"))
    payload["files"].append(
        {
            "path": ".lore/skills/gone-in-this-release/SKILL.md",
            "kind": "owned",
            "source": "skill:gone-in-this-release",
            "hash": "sha256:" + "0" * 64,
        }
    )
    installed.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return stale


# ---------------------------------------------------------------------------
# The flag surface — interactive-init-us-016
# ---------------------------------------------------------------------------


class TestTheDeclaredOptions:
    """The nine options of Tech Spec §3.3, asserted on the command object.

    §3.3 declared ten. `--gitignore/--no-gitignore` is gone with the block it
    answered for — every line of that block was already ignored by
    `.lore/.gitignore`, so both answers left the tree identically ignored.
    """

    EXPECTED = {
        "agent": None,
        "access_mode": None,
        "skill_families": None,
        "on_existing_agent_file": "append",
        "skills_gitignore": None,
        "on_conflict": "skip",
        "yes": False,
        "reconfigure": False,
        "dry_run": False,
    }

    def test_init_declares_the_nine_documented_options(self):
        params = _init_params()
        missing = [name for name in self.EXPECTED if name not in params]
        assert missing == [], f"`lore init` is missing options: {missing}"

    @pytest.mark.parametrize("name,default", sorted(EXPECTED.items()))
    def test_each_option_carries_the_documented_click_default(self, name, default):
        assert _init_params()[name].default == default

    def test_the_multi_value_flags_use_space_separated_choice(self):
        from lore.cli import SpaceSeparatedChoice

        params = _init_params()
        assert isinstance(params["agent"], SpaceSeparatedChoice)
        assert isinstance(params["skill_families"], SpaceSeparatedChoice)

    def test_the_constrained_scalar_flags_use_click_choice(self):
        params = _init_params()
        for name in ("access_mode", "on_existing_agent_file", "skills_gitignore", "on_conflict"):
            assert isinstance(params[name].type, click.Choice), name

    def test_the_retired_gitignore_flag_is_declared_nowhere(self):
        assert "root_gitignore" not in _init_params()

    def test_no_option_default_comes_from_config(self):
        """ADR-021 constraint 2 — `plan_init` is the only reader of the four keys."""
        tree = ast.parse(CLI_SOURCE.read_text(encoding="utf-8"))
        handler = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "init"
        )
        segment = ast.dump(handler) + "".join(
            ast.dump(decorator) for decorator in handler.decorator_list
        )
        assert "load_config" not in segment
        assert "init-agents" not in segment
        assert "init_access_mode" not in segment


class TestSpaceSeparatedChoiceShape:
    """The subclass changes the parser and nothing else (ADR-012 + ADR-017)."""

    def test_it_subclasses_click_option(self):
        from lore.cli import SpaceSeparatedChoice

        assert issubclass(SpaceSeparatedChoice, click.Option)

    def test_it_overrides_only_add_to_parser(self):
        from lore.cli import SpaceSeparatedChoice

        overridden = {
            name
            for name in vars(SpaceSeparatedChoice)
            if not name.startswith("__") and callable(getattr(SpaceSeparatedChoice, name))
        }
        assert overridden == {"add_to_parser"}

    def test_the_validator_is_still_click_choice(self):
        params = _init_params()
        assert isinstance(params["agent"].type, click.Choice)
        assert isinstance(params["skill_families"].type, click.Choice)


class TestChoiceSetsComeFromTheData:
    """The registry and the catalogue decide the token sets, not a literal."""

    def test_agent_choices_are_the_registry_ids(self):
        from lore import agents

        assert tuple(_init_params()["agent"].type.choices) == agents.agent_ids()

    def test_skill_choices_are_the_families_plus_the_two_aggregates(self):
        from lore import skills

        offered = tuple(_init_params()["skill_families"].type.choices)
        assert set(offered) == set(skills.family_ids()) | {"all", "none"}


class TestSpaceSeparatedParsing:
    """The five parser cases ADR-012 needs and ADR-017 must survive."""

    def test_both_multi_value_flags_parse_and_apply(self, tmp_path, monkeypatch):
        result = _run(
            tmp_path,
            monkeypatch,
            "--agent", "claude", "agents-md",
            "--skills", "memory", "workflow",
            "--yes",
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / ".claude" / "skills" / "store-memory" / "SKILL.md").is_file()
        assert (tmp_path / ".lore" / "skills" / "store-memory" / "SKILL.md").is_file()
        installed = {p.name for p in (tmp_path / ".claude" / "skills").iterdir() if p.is_dir()}
        assert "update-doctrine" not in installed, "machinery was not selected"
        recorded = (tmp_path / ".lore" / "config.toml").read_text(encoding="utf-8")
        assert "init-agents = " in recorded
        assert "claude" in recorded and "agents-md" in recorded

    def test_a_following_flag_stops_greedy_consumption(self, tmp_path, monkeypatch):
        result = _run(
            tmp_path, monkeypatch, "--agent", "claude", "--skills", "memory", "--yes"
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / ".claude" / "skills" / "store-memory" / "SKILL.md").is_file()
        assert not (tmp_path / ".lore" / "skills").exists()
        assert not (tmp_path / ".claude" / "skills" / "start-quest").exists()

    def test_a_bare_dash_is_consumed_as_a_value_and_rejected(self, tmp_path, monkeypatch):
        result = _run(tmp_path, monkeypatch, "--agent", "claude", "-", "--yes")
        assert result.exit_code == 2, result.output
        assert (
            "Error: Invalid value for '--agent': '-' is not one of "
            "'agents-md', 'claude', 'cursor', 'gemini', 'none', 'qwen'."
        ) in result.stderr
        assert not (tmp_path / ".lore").exists()

    def test_an_out_of_set_token_in_the_tail_still_exits_two(self, tmp_path, monkeypatch):
        result = _run(tmp_path, monkeypatch, "--agent", "claude", "bogus")
        assert result.exit_code == 2, result.output
        assert (
            "Error: Invalid value for '--agent': 'bogus' is not one of "
            "'agents-md', 'claude', 'cursor', 'gemini', 'none', 'qwen'."
        ) in result.stderr
        assert not (tmp_path / ".lore").exists()

    def test_a_repeated_flag_accumulates_rather_than_raising(self, tmp_path, monkeypatch):
        result = _run(
            tmp_path,
            monkeypatch,
            "--agent", "claude", "agents-md",
            "--agent", "gemini",
            "--yes",
        )
        assert result.exit_code == 0, result.output
        recorded = (tmp_path / ".lore" / "config.toml").read_text(encoding="utf-8")
        for agent_id in ("claude", "agents-md", "gemini"):
            assert agent_id in recorded
        assert (tmp_path / "GEMINI.md").is_file()

    def test_a_multi_value_flag_accepts_a_single_token(self, tmp_path, monkeypatch):
        result = _run(tmp_path, monkeypatch, "--agent", "claude", "--yes")
        assert result.exit_code == 0, result.output
        assert (tmp_path / "CLAUDE.md").is_file()


# ---------------------------------------------------------------------------
# The prompt layer — interactive-init-us-018
# ---------------------------------------------------------------------------


class TestThePromptLibraryStaysUnloaded:
    """ADR-001 — an interactive command must cost every other command nothing."""

    def test_importing_lore_api_loads_neither_questionary_nor_prompt_toolkit(self):
        probe = (
            "import sys, json;"
            "import lore.api;"
            "print(json.dumps(sorted("
            "m for m in sys.modules if m in ('questionary', 'prompt_toolkit')"
            ")))"
        )
        completed = subprocess.run(
            [sys.executable, "-c", probe], capture_output=True, text=True, check=True
        )
        loaded = json.loads(completed.stdout.strip().splitlines()[-1])
        assert loaded == [], f"importing lore.api pulled in {loaded}"

    def test_importing_lore_prompts_loads_neither_either(self):
        probe = (
            "import sys, json;"
            "import lore.prompts;"
            "print(json.dumps(sorted("
            "m for m in sys.modules if m in ('questionary', 'prompt_toolkit')"
            ")))"
        )
        completed = subprocess.run(
            [sys.executable, "-c", probe], capture_output=True, text=True, check=True
        )
        loaded = json.loads(completed.stdout.strip().splitlines()[-1])
        assert loaded == [], f"importing lore.prompts pulled in {loaded}"

    def test_the_api_facade_aliases_the_prompt_module_privately(self):
        from lore import api, prompts

        assert api._prompts is prompts
        assert "_prompts" not in api.__all__


class TestCallingAPromptReachesQuestionary:
    """Scenario 2 — the lazy import resolves, against the real questionary."""

    def test_ask_agents_builds_one_checkbox(self, monkeypatch):
        import questionary

        from lore import agents, prompts

        calls = []

        class Answer:
            def ask(self):
                return ["claude"]

        def checkbox(message, choices=None, **kwargs):
            calls.append((message, choices, kwargs))
            return Answer()

        monkeypatch.setattr(questionary, "checkbox", checkbox)
        answer = prompts.ask_agents(agents.load_registry())

        assert len(calls) == 1
        _, choices, _ = calls[0]
        assert [choice.value for choice in choices] == list(
            row.id for row in agents.load_registry()
        )
        assert answer == ["claude"]

    def test_every_prompt_returns_the_plan_init_parameter_shape(self, monkeypatch):
        import questionary

        from lore import agents, prompts, skills

        canned = {
            "checkbox": None,
            "select": None,
            "confirm": None,
        }

        class Answer:
            def __init__(self, kind):
                self.kind = kind

            def ask(self):
                return canned[self.kind]

        for kind in canned:
            monkeypatch.setattr(
                questionary, kind, lambda *a, _k=kind, **k: Answer(_k)
            )

        canned["checkbox"] = ["claude", "gemini"]
        assert prompts.ask_agents(agents.load_registry()) == ["claude", "gemini"]

        canned["checkbox"] = ["memory"]
        families = prompts.ask_skill_families(skills.family_ids())
        assert families == ["memory"]
        assert "all" not in families and "none" not in families

        canned["select"] = "cli"
        assert prompts.ask_access_mode() == "cli"

        canned["select"] = "skip"
        assert prompts.ask_existing_agent_file(("CLAUDE.md",)) == "skip"

        canned["select"] = "all"
        assert prompts.ask_skills_gitignore() == "all"

        canned["select"] = "overwrite"
        assert prompts.ask_on_conflict(3) == "overwrite"

        canned["confirm"] = True
        assert prompts.ask_confirm_plan() is True


class TestCtrlCAtAPrompt:
    """Scenario 4 — questionary answers None; nothing is written and exit is 1."""

    def test_abort_at_the_first_prompt_writes_nothing(
        self, tmp_path, monkeypatch, terminal, prompts
    ):
        prompts(ask_agents=None)
        before = _snapshot(tmp_path)
        result = _run(tmp_path, monkeypatch)
        assert result.exit_code == 1, result.output
        assert "Aborted!" in result.stderr
        assert _snapshot(tmp_path) == before

    def test_abort_at_the_summary_confirm_writes_nothing(
        self, tmp_path, monkeypatch, terminal, prompts
    ):
        prompts(ask_confirm_plan=None)
        before = _snapshot(tmp_path)
        result = _run(tmp_path, monkeypatch)
        assert result.exit_code == 1, result.output
        assert "Aborted!" in result.stderr
        assert _snapshot(tmp_path) == before


# ---------------------------------------------------------------------------
# The orchestration — interactive-init-us-019
# ---------------------------------------------------------------------------


class TestAFirstInteractiveRun:
    """Scenario 1 — the fixed order, the summary before any write, then apply."""

    ORDER = [
        "ask_agents",
        "ask_access_mode",
        "ask_skill_families",
        "ask_existing_agent_file",
        "ask_skills_gitignore",
        "ask_confirm_plan",
    ]

    @pytest.fixture()
    def project(self, tmp_path):
        """A repository with house rules already in CLAUDE.md and no `.lore/`."""
        (tmp_path / "CLAUDE.md").write_text("# Acme\n\nHouse rules.\n", encoding="utf-8")
        return tmp_path

    def test_the_prompts_fire_in_the_fixed_order(
        self, project, monkeypatch, terminal, prompts
    ):
        log = prompts()
        result = _run(project, monkeypatch)
        assert result.exit_code == 0, result.output
        assert log.names == self.ORDER

    def test_the_summary_is_printed_before_the_confirm(
        self, project, monkeypatch, terminal, prompts
    ):
        prompts()
        result = _run(project, monkeypatch)
        assert result.exit_code == 0, result.output
        assert f"Plan for {project}" in result.output
        assert result.output.index("Plan for") < result.output.index(
            "Initialized Lore project:"
        )

    def test_confirmation_produces_the_whole_selection(
        self, project, monkeypatch, terminal, prompts
    ):
        prompts()
        result = _run(project, monkeypatch)
        assert result.exit_code == 0, result.output

        skills_dir = project / ".claude" / "skills"
        assert (skills_dir / "store-memory" / "SKILL.md").is_file()
        assert (skills_dir / "start-quest" / "SKILL.md").is_file()
        assert not (skills_dir / "update-doctrine").exists()

        assert LORE_BEGIN in (project / "CLAUDE.md").read_text(encoding="utf-8")
        assert "House rules." in (project / "CLAUDE.md").read_text(encoding="utf-8")
        assert not (project / ".gitignore").exists()

        config = (project / ".lore" / "config.toml").read_text(encoding="utf-8")
        for key in (
            "init-agents",
            "init-access-mode",
            "init-skill-families",
            "init-skills-gitignore",
        ):
            assert key in config
        assert (project / ".lore" / ".install-manifest.json").is_file()

    def test_an_empty_directory_does_not_ask_the_existing_file_question(
        self, tmp_path, monkeypatch, terminal, prompts
    ):
        log = prompts()
        result = _run(tmp_path, monkeypatch)
        assert result.exit_code == 0, result.output
        assert log.names == [
            name for name in self.ORDER if name != "ask_existing_agent_file"
        ]


class TestDecliningTheSummary:
    """Scenario 2 — refused means untouched."""

    def test_nothing_is_written_and_the_exit_is_zero(
        self, tmp_path, monkeypatch, terminal, prompts
    ):
        prompts(ask_confirm_plan=False)
        before = _snapshot(tmp_path)
        result = _run(tmp_path, monkeypatch)
        assert result.exit_code == 0, result.output
        assert "No changes applied." in result.output
        assert _snapshot(tmp_path) == before

    def test_the_summary_is_still_shown(self, tmp_path, monkeypatch, terminal, prompts):
        prompts(ask_confirm_plan=False)
        result = _run(tmp_path, monkeypatch)
        assert "Plan for" in result.output
        assert "Initialized Lore project:" not in result.output


class TestTheSummaryFormat:
    """Scenario 3 — one line per action, and a counts line that closes it."""

    def test_the_header_names_the_root_and_the_three_recorded_answers(
        self, tmp_path, monkeypatch, terminal, prompts
    ):
        prompts()
        result = _run(tmp_path, monkeypatch)
        header = next(
            line for line in result.output.splitlines() if line.startswith("Plan for")
        )
        assert header == (
            f"Plan for {tmp_path} (agents: claude · access: native · "
            "families: memory, workflow)"
        )

    def test_every_line_carries_one_action_word(
        self, tmp_path, monkeypatch, terminal, prompts
    ):
        prompts()
        result = _run(tmp_path, monkeypatch)
        body = result.output.split("Plan for")[1].split("Initialized")[0]
        action_lines = [
            line for line in body.splitlines() if line.startswith("  ") and line.strip()
        ]
        assert any(line.strip().startswith("Create ") for line in action_lines)
        assert any(line.strip().startswith("Section ") for line in action_lines)

    def test_the_counts_line_closes_the_summary(
        self, tmp_path, monkeypatch, terminal, prompts
    ):
        prompts()
        result = _run(tmp_path, monkeypatch)
        counts = next(
            line for line in result.output.splitlines() if " create · " in line
        )
        assert counts.strip().endswith("conflict")
        assert " section · " in counts
        assert " overwrite · " in counts
        assert " remove · " in counts

    def test_a_second_identical_run_reports_no_changes(
        self, tmp_path, monkeypatch, terminal, prompts
    ):
        prompts()
        assert _run(tmp_path, monkeypatch).exit_code == 0
        prompts()
        result = _run(tmp_path, monkeypatch)
        counts = next(
            line for line in result.output.splitlines() if " create · " in line
        )
        assert counts.strip() == "0 create · 0 section · 0 overwrite · 0 remove · 0 conflict"


class TestTheYesFlag:
    """Scenario 5 — `--yes` answers every prompt, and still shows the plan."""

    def test_no_prompt_fires(self, tmp_path, monkeypatch, terminal, no_prompts):
        result = _run(tmp_path, monkeypatch, "--yes")
        assert result.exit_code == 0, result.output

    def test_the_summary_is_still_printed_at_a_terminal(
        self, tmp_path, monkeypatch, terminal, no_prompts
    ):
        result = _run(tmp_path, monkeypatch, "--yes")
        assert "Plan for" in result.output
        assert "Initialized Lore project:" in result.output

    def test_conflicts_take_the_default_skip_policy(
        self, tmp_path, monkeypatch, terminal, no_prompts
    ):
        """A file Lore never installed, at a path Lore wants: left alone."""
        mine = "# mine, and Lore has never written here\n"
        planted = tmp_path / ".lore" / "skills" / "store-memory" / "SKILL.md"
        planted.parent.mkdir(parents=True)
        planted.write_text(mine, encoding="utf-8")
        result = _run(tmp_path, monkeypatch, "--yes")
        assert result.exit_code == 0, result.output
        assert planted.read_text(encoding="utf-8") == mine


class TestDryRun:
    """Scenario 6 — the plan is printed and the working tree is untouched."""

    def test_it_prints_the_plan_and_writes_nothing(self, tmp_path, monkeypatch):
        before = _snapshot(tmp_path)
        result = _run(tmp_path, monkeypatch, "--dry-run")
        assert result.exit_code == 0, result.output
        assert "Plan for" in result.output
        assert result.output.rstrip().endswith("Dry run — no files written.")
        assert _snapshot(tmp_path) == before

    def test_it_wins_over_yes(self, tmp_path, monkeypatch):
        before = _snapshot(tmp_path)
        result = _run(tmp_path, monkeypatch, "--dry-run", "--yes")
        assert result.exit_code == 0, result.output
        assert "Dry run — no files written." in result.output
        assert _snapshot(tmp_path) == before

    def test_at_a_terminal_it_asks_first_and_then_writes_nothing(
        self, tmp_path, monkeypatch, terminal, prompts
    ):
        """The plan shown is the plan for the answers you gave, applied to nothing."""
        log = prompts()
        before = _snapshot(tmp_path)
        result = _run(tmp_path, monkeypatch, "--dry-run")
        assert result.exit_code == 0, result.output
        assert "ask_agents" in log.names
        assert "ask_confirm_plan" not in log.names
        assert "Dry run — no files written." in result.output
        assert _snapshot(tmp_path) == before

    def test_yes_at_a_terminal_asks_nothing_and_still_writes_nothing(
        self, tmp_path, monkeypatch, terminal, no_prompts
    ):
        result = _run(tmp_path, monkeypatch, "--dry-run", "--yes")
        assert result.exit_code == 0, result.output
        assert not (tmp_path / ".lore").exists()

    def test_it_shows_the_upgrade_a_pipe_would_apply_unseen(self, tmp_path, monkeypatch):
        assert _run(tmp_path, monkeypatch, "--yes").exit_code == 0
        retired = tmp_path / ".lore" / "skills" / "new-doctrine"
        retired.mkdir(parents=True)
        (retired / "SKILL.md").write_text("stale\n", encoding="utf-8")
        result = _run(tmp_path, monkeypatch, "--dry-run")
        assert result.exit_code == 0, result.output
        assert (retired / "SKILL.md").is_file()


class TestRecordedAnswers:
    """Scenario 7 — a project is asked once, and `--reconfigure` asks again."""

    @pytest.fixture()
    def recorded(self, tmp_path, monkeypatch):
        result = _run(
            tmp_path,
            monkeypatch,
            "--agent", "claude",
            "--access", "cli",
            "--skills", "memory",
            "--skills-gitignore", "none",
            "--yes",
        )
        assert result.exit_code == 0, result.output
        return tmp_path

    RECORDED_PROMPTS = (
        "ask_agents",
        "ask_access_mode",
        "ask_skill_families",
        "ask_skills_gitignore",
    )

    def test_a_recorded_project_asks_none_of_the_four(
        self, recorded, monkeypatch, terminal, prompts
    ):
        log = prompts()
        result = _run(recorded, monkeypatch)
        assert result.exit_code == 0, result.output
        for name in self.RECORDED_PROMPTS:
            assert name not in log.names
        assert "ask_confirm_plan" in log.names

    def test_reconfigure_asks_all_four_again(
        self, recorded, monkeypatch, terminal, prompts
    ):
        log = prompts()
        result = _run(recorded, monkeypatch, "--reconfigure")
        assert result.exit_code == 0, result.output
        for name in self.RECORDED_PROMPTS:
            assert name in log.names

    def test_reconfigure_preselects_what_the_project_recorded(
        self, recorded, monkeypatch, terminal, prompts
    ):
        log = prompts()
        assert _run(recorded, monkeypatch, "--reconfigure").exit_code == 0

        _, agents_kwargs = log.args_for("ask_agents")
        assert list(agents_kwargs["selected"]) == ["claude"]

        _, access_kwargs = log.args_for("ask_access_mode")
        assert access_kwargs["current"] == "cli"

        _, families_kwargs = log.args_for("ask_skill_families")
        assert list(families_kwargs["selected"]) == ["memory"]

        _, gitignore_kwargs = log.args_for("ask_skills_gitignore")
        assert gitignore_kwargs["current"] == "none"

    def test_a_flag_suppresses_only_its_own_prompt(
        self, tmp_path, monkeypatch, terminal, prompts
    ):
        log = prompts()
        result = _run(tmp_path, monkeypatch, "--access", "cli")
        assert result.exit_code == 0, result.output
        assert "ask_access_mode" not in log.names
        assert "ask_agents" in log.names
        assert "ask_skill_families" in log.names


class TestTheConditionalPrompts:
    """Scenario 8 — each fires only in the case that justifies it."""

    def test_an_unmarked_instruction_file_asks_and_an_absent_one_does_not(
        self, tmp_path, monkeypatch, terminal, prompts
    ):
        (tmp_path / "CLAUDE.md").write_text("mine\n", encoding="utf-8")
        log = prompts()
        assert _run(tmp_path, monkeypatch).exit_code == 0
        assert "ask_existing_agent_file" in log.names

        other = tmp_path / "fresh"
        other.mkdir()
        fresh_log = prompts()
        assert _run(other, monkeypatch).exit_code == 0
        assert "ask_existing_agent_file" not in fresh_log.names

    def test_the_question_names_only_the_instruction_files_that_exist(
        self, tmp_path, monkeypatch, terminal, prompts
    ):
        """One unmarked file opens the question; it is not about the absent ones."""
        (tmp_path / "CLAUDE.md").write_text("mine\n", encoding="utf-8")
        log = prompts(ask_agents=["claude", "gemini"])
        assert _run(tmp_path, monkeypatch).exit_code == 0
        args, _ = log.args_for("ask_existing_agent_file")
        assert list(args[0]) == ["CLAUDE.md"]

    def test_an_agent_without_a_native_skills_directory_is_asked_too(
        self, tmp_path, monkeypatch, terminal, prompts
    ):
        """Its skills land in `.lore/skills/`, where the answer now decides."""
        log = prompts(ask_agents=["agents-md"])
        result = _run(tmp_path, monkeypatch)
        assert result.exit_code == 0, result.output
        assert "ask_skills_gitignore" in log.names

    def test_an_agent_with_a_native_skills_directory_is_asked(
        self, tmp_path, monkeypatch, terminal, prompts
    ):
        log = prompts(ask_agents=["claude"])
        assert _run(tmp_path, monkeypatch).exit_code == 0
        assert "ask_skills_gitignore" in log.names

    def test_a_file_lore_never_installed_asks_the_conflict_question(
        self, tmp_path, monkeypatch, terminal, prompts
    ):
        planted = tmp_path / ".lore" / "skills" / "store-memory" / "SKILL.md"
        planted.parent.mkdir(parents=True)
        planted.write_text("# mine, and Lore never wrote here\n", encoding="utf-8")

        log = prompts(ask_agents=["none"])
        result = _run(tmp_path, monkeypatch)
        assert result.exit_code == 0, result.output
        assert "ask_on_conflict" in log.names

    def test_an_edited_installed_skill_asks_nothing(
        self, tmp_path, monkeypatch, terminal, prompts
    ):
        """Lore owns what Lore installed, so there is no question to put.

        The prompt used to fire here offering "take the shipped version" —
        which is now what the run does anyway.
        """
        assert _run(tmp_path, monkeypatch, "--agent", "none", "--yes").exit_code == 0
        edited = tmp_path / ".lore" / "skills" / "store-memory" / "SKILL.md"
        shipped = edited.read_text(encoding="utf-8")
        edited.write_text("# mine now\n", encoding="utf-8")

        log = prompts(ask_agents=["none"])
        result = _run(tmp_path, monkeypatch)
        assert result.exit_code == 0, result.output
        assert "ask_on_conflict" not in log.names
        assert edited.read_text(encoding="utf-8") == shipped

    def test_a_project_with_no_conflict_is_not_asked(
        self, tmp_path, monkeypatch, terminal, prompts
    ):
        log = prompts()
        assert _run(tmp_path, monkeypatch).exit_code == 0
        assert "ask_on_conflict" not in log.names

    def test_an_edited_retired_skill_asks_nothing_either(
        self, tmp_path, monkeypatch, terminal, prompts
    ):
        """It is removed and its successor named, so there is nothing to ask."""
        stale = _retire_an_edited_skill(tmp_path, monkeypatch)
        log = prompts(ask_agents=["none"])
        result = _run(tmp_path, monkeypatch)
        assert result.exit_code == 0, result.output
        assert "ask_on_conflict" not in log.names
        assert not stale.exists()

    def test_the_conflict_question_is_told_how_many_there_are(
        self, tmp_path, monkeypatch, terminal, prompts
    ):
        planted = tmp_path / ".lore" / "skills" / "store-memory" / "SKILL.md"
        planted.parent.mkdir(parents=True)
        planted.write_text("# mine\n", encoding="utf-8")

        log = prompts(ask_agents=["none"])
        assert _run(tmp_path, monkeypatch).exit_code == 0

        args, kwargs = log.args_for("ask_on_conflict")
        counted = (*args, *kwargs.values())
        assert counted[0] == 1, f"one file would be written over, got {counted}"

    def test_overwrite_at_the_prompt_hands_the_path_over(
        self, tmp_path, monkeypatch, terminal, prompts
    ):
        planted = tmp_path / ".lore" / "skills" / "store-memory" / "SKILL.md"
        planted.parent.mkdir(parents=True)
        planted.write_text("# mine\n", encoding="utf-8")

        prompts(ask_agents=["none"], ask_on_conflict="overwrite")
        assert _run(tmp_path, monkeypatch).exit_code == 0
        assert planted.read_text(encoding="utf-8") != "# mine\n"


class TestThePlanIsComputedTwice:
    """The two-pass shape ADR-011 requires: no prompt lives inside `plan_init`."""

    def test_a_run_with_no_conditional_prompt_plans_exactly_twice(
        self, tmp_path, monkeypatch, terminal, prompts
    ):
        from lore import init as init_module

        calls = []
        real = init_module.plan_init

        def counted(*args, **kwargs):
            calls.append(kwargs)
            return real(*args, **kwargs)

        monkeypatch.setattr(init_module, "plan_init", counted)
        prompts(ask_agents=["agents-md"])
        result = _run(tmp_path, monkeypatch)
        assert result.exit_code == 0, result.output
        assert len(calls) == 2, f"planned {len(calls)} times"

    def test_a_headless_run_plans_once(self, tmp_path, monkeypatch, no_prompts):
        from lore import init as init_module

        calls = []
        real = init_module.plan_init

        def counted(*args, **kwargs):
            calls.append(kwargs)
            return real(*args, **kwargs)

        monkeypatch.setattr(init_module, "plan_init", counted)
        result = _run(tmp_path, monkeypatch)
        assert result.exit_code == 0, result.output
        assert len(calls) == 1


class TestReconfigureWithoutAPromptToAskIn:
    """`--reconfigure` asks again — and a run with no prompt cannot ask.

    The recorded answers are the only record of what a project installed, so a
    headless `--reconfigure` that dropped them would deselect every agent and
    uninstall the lot. It stops with a usage error instead, and says which
    flags would answer the questions it cannot ask.
    """

    FLAGS = ("--agent", "--access", "--skills", "--skills-gitignore")

    @pytest.fixture()
    def installed(self, tmp_path, monkeypatch):
        result = _run(
            tmp_path, monkeypatch, "--agent", "claude", "--skills", "all", "--yes"
        )
        assert result.exit_code == 0, result.output
        return tmp_path

    def test_it_is_a_usage_error(self, installed, monkeypatch):
        result = _run(installed, monkeypatch, "--reconfigure", "--yes")
        assert result.exit_code == 2, result.output

    def test_it_writes_nothing(self, installed, monkeypatch):
        before = _snapshot(installed)
        _run(installed, monkeypatch, "--reconfigure", "--yes")
        assert _snapshot(installed) == before

    def test_the_installed_skills_survive(self, installed, monkeypatch):
        _run(installed, monkeypatch, "--reconfigure", "--yes")
        assert list((installed / ".claude" / "skills").glob("*/SKILL.md"))

    def test_the_instruction_file_survives(self, installed, monkeypatch):
        before = (installed / "CLAUDE.md").read_bytes()
        _run(installed, monkeypatch, "--reconfigure", "--yes")
        assert (installed / "CLAUDE.md").read_bytes() == before

    def test_the_recorded_answers_survive(self, installed, monkeypatch):
        config = installed / ".lore" / "config.toml"
        before = config.read_bytes()
        _run(installed, monkeypatch, "--reconfigure", "--yes")
        assert config.read_bytes() == before

    def test_a_pipe_without_yes_is_refused_too(self, installed, monkeypatch):
        """`CliRunner` is not a terminal, which is the CI and pipe case."""
        result = _run(installed, monkeypatch, "--reconfigure")
        assert result.exit_code == 2, result.output

    def test_dry_run_is_refused_rather_than_printing_a_plan_nobody_asked_for(
        self, installed, monkeypatch
    ):
        result = _run(installed, monkeypatch, "--reconfigure", "--dry-run")
        assert result.exit_code == 2, result.output
        assert "Plan for" not in result.output

    def test_the_message_names_the_flags_that_would_answer(
        self, installed, monkeypatch
    ):
        result = _run(installed, monkeypatch, "--reconfigure", "--yes")
        for flag in self.FLAGS:
            assert flag in result.output, result.output

    def test_the_message_names_the_flag_that_is_still_open_only(
        self, installed, monkeypatch
    ):
        result = _run(
            installed,
            monkeypatch,
            "--reconfigure",
            "--agent", "claude",
            "--access", "native",
            "--skills", "all",
            "--yes",
        )
        assert result.exit_code == 2, result.output
        assert "--skills-gitignore" in result.output
        assert "--access" not in result.output

    def test_answering_all_four_by_flag_is_allowed(self, installed, monkeypatch):
        result = _run(
            installed,
            monkeypatch,
            "--reconfigure",
            "--agent", "agents-md",
            "--access", "cli",
            "--skills", "memory",
            "--skills-gitignore", "none",
            "--yes",
        )
        assert result.exit_code == 0, result.output
        recorded = (installed / ".lore" / "config.toml").read_text(encoding="utf-8")
        assert 'init-agents = ["agents-md"]' in recorded

    def test_a_terminal_still_asks_all_four(
        self, installed, monkeypatch, terminal, prompts
    ):
        log = prompts()
        result = _run(installed, monkeypatch, "--reconfigure")
        assert result.exit_code == 0, result.output
        for name in ("ask_agents", "ask_access_mode", "ask_skill_families"):
            assert name in log.names

    def test_the_help_says_it_needs_a_terminal(self, tmp_path, monkeypatch):
        result = _run(tmp_path, monkeypatch, "--help")
        help_text = " ".join(result.output.split())
        assert "--reconfigure" in help_text
        assert "terminal" in help_text.split("--reconfigure", 1)[1]


class TestARecordedAnswerThatNoLongerValidates:
    """A `config.toml` that cannot resolve is reported, never raised.

    `init-agents = ["none", "claude"]` loads — both are registry ids — and then
    fails the exclusivity rule inside `plan_init`. Every later `lore init` hits
    it, so the message has to carry the way out with it.
    """

    @pytest.fixture()
    def wedged(self, tmp_path, monkeypatch):
        result = _run(tmp_path, monkeypatch, "--agent", "claude", "--yes")
        assert result.exit_code == 0, result.output
        config = tmp_path / ".lore" / "config.toml"
        config.write_text(
            config.read_text(encoding="utf-8").replace(
                'init-agents = ["claude"]', 'init-agents = ["none", "claude"]'
            ),
            encoding="utf-8",
        )
        return tmp_path

    def test_the_run_fails_without_a_traceback(self, wedged, monkeypatch):
        result = _run(wedged, monkeypatch, "--yes")
        assert result.exit_code == 1, result.output
        assert not isinstance(result.exception, ValueError), result.exception

    def test_the_message_quotes_the_rule_that_rejected_it(self, wedged, monkeypatch):
        result = _run(wedged, monkeypatch, "--yes")
        assert "--agent none cannot be combined with other agents." in result.output

    def test_the_message_names_the_recorded_answer(self, wedged, monkeypatch):
        result = _run(wedged, monkeypatch, "--yes")
        assert "init-agents" in result.output
        assert "config.toml" in result.output

    def test_the_message_names_the_flag_that_replaces_it(self, wedged, monkeypatch):
        result = _run(wedged, monkeypatch, "--yes")
        assert "--agent" in result.output

    def test_the_named_flag_actually_recovers_the_project(self, wedged, monkeypatch):
        result = _run(wedged, monkeypatch, "--agent", "claude", "--yes")
        assert result.exit_code == 0, result.output
        recorded = (wedged / ".lore" / "config.toml").read_text(encoding="utf-8")
        assert 'init-agents = ["claude"]' in recorded

    def test_a_terminal_run_reports_it_the_same_way(
        self, wedged, monkeypatch, terminal, prompts
    ):
        prompts()
        result = _run(wedged, monkeypatch)
        assert result.exit_code == 1, result.output
        assert not isinstance(result.exception, ValueError), result.exception
        assert "--agent none cannot be combined with other agents." in result.output


class TestAnIllegalAgentSelectionAtThePrompt:
    """The checkbox offers `none` beside the real agents; ticking both is asked again."""

    @pytest.fixture()
    def answers_then(self, monkeypatch):
        """Make `ask_agents` return each canned selection in turn."""

        def install(*selections):
            from lore import prompts as prompts_module

            remaining = list(selections)
            asked = []

            def stub(*args, **kwargs):
                asked.append(kwargs.get("selected"))
                return remaining.pop(0)

            monkeypatch.setattr(prompts_module, "ask_agents", stub)
            return asked

        return install

    def test_it_re_asks_instead_of_raising(
        self, tmp_path, monkeypatch, terminal, prompts, answers_then
    ):
        prompts()
        asked = answers_then(["none", "claude"], ["claude"])
        result = _run(tmp_path, monkeypatch)
        assert result.exit_code == 0, result.output
        assert len(asked) == 2, f"asked {len(asked)} times"

    def test_it_reports_why_before_asking_again(
        self, tmp_path, monkeypatch, terminal, prompts, answers_then
    ):
        prompts()
        answers_then(["none", "claude"], ["claude"])
        result = _run(tmp_path, monkeypatch)
        assert "--agent none cannot be combined with other agents." in result.output

    def test_the_second_answer_is_the_one_that_gets_applied(
        self, tmp_path, monkeypatch, terminal, prompts, answers_then
    ):
        prompts()
        answers_then(["none", "claude"], ["agents-md"])
        assert _run(tmp_path, monkeypatch).exit_code == 0
        recorded = (tmp_path / ".lore" / "config.toml").read_text(encoding="utf-8")
        assert 'init-agents = ["agents-md"]' in recorded

    def test_the_re_ask_preselects_what_was_just_chosen(
        self, tmp_path, monkeypatch, terminal, prompts, answers_then
    ):
        prompts()
        asked = answers_then(["none", "claude"], ["claude"])
        assert _run(tmp_path, monkeypatch).exit_code == 0
        assert sorted(asked[1]) == ["claude", "none"]

    def test_a_legal_selection_is_asked_exactly_once(
        self, tmp_path, monkeypatch, terminal, prompts, answers_then
    ):
        prompts()
        asked = answers_then(["claude"])
        assert _run(tmp_path, monkeypatch).exit_code == 0
        assert len(asked) == 1


class TestTheApplyStepIsSkippedWhenItShouldBe:
    """`--dry-run` and a declined confirm never reach `apply_init`."""

    @pytest.fixture()
    def apply_forbidden(self, monkeypatch):
        from lore import init as init_module

        def boom(plan):
            raise AssertionError("apply_init must not run")

        monkeypatch.setattr(init_module, "apply_init", boom)

    def test_dry_run_never_reaches_apply(self, tmp_path, monkeypatch, apply_forbidden):
        result = _run(tmp_path, monkeypatch, "--dry-run")
        assert result.exit_code == 0, result.output

    def test_a_declined_confirm_never_reaches_apply(
        self, tmp_path, monkeypatch, terminal, prompts, apply_forbidden
    ):
        prompts(ask_confirm_plan=False)
        result = _run(tmp_path, monkeypatch)
        assert result.exit_code == 0, result.output


class TestTheTtyGate:
    """Tech Spec §1 — one gate, in `cli.py`, and nowhere else in the package."""

    def test_isatty_appears_exactly_once_in_the_cli(self):
        source = CLI_SOURCE.read_text(encoding="utf-8")
        assert source.count("isatty") == 1

    def test_no_business_module_consults_isatty(self):
        src = CLI_SOURCE.parent
        offenders = [
            path.name
            for path in sorted(src.glob("*.py"))
            if path.name != "cli.py" and "isatty" in path.read_text(encoding="utf-8")
        ]
        assert offenders == [], f"isatty consulted outside cli.py: {offenders}"

    def test_the_gate_is_read_from_sys_stdout(self):
        source = CLI_SOURCE.read_text(encoding="utf-8")
        assert "sys.stdout.isatty()" in source
