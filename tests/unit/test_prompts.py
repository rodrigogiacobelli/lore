"""Unit tests for `lore.prompts` — one questionary function per question.

Spec: conceptual-workflows-init-interactive (lore codex show
conceptual-workflows-init-interactive) — The Prompts.

`prompt_toolkit` is a dependency, not a subject: every test here stubs
`questionary` and asserts on the choices offered, the preselection, and the
shape each function normalises its answer into. Nothing drives a terminal.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest


PROMPTS_SOURCE = Path(__file__).resolve().parents[2] / "src" / "lore" / "prompts.py"


# ---------------------------------------------------------------------------
# A questionary stand-in that records what it was asked to render
# ---------------------------------------------------------------------------


class FakeChoice:
    """The two fields the prompts set, and the one they read back in tests."""

    def __init__(self, title, value=None, checked=False, **kwargs):
        self.title = title
        self.value = value if value is not None else title
        self.checked = checked
        self.kwargs = kwargs


class FakeQuestion:
    def __init__(self, answer):
        self._answer = answer

    def ask(self):
        return self._answer


class FakeQuestionary:
    """Records every prompt constructed and hands back a canned answer."""

    Choice = FakeChoice

    def __init__(self, answer=None):
        self.answer = answer
        self.calls = []

    def _record(self, kind, message, choices=None, **kwargs):
        self.calls.append(
            {"kind": kind, "message": message, "choices": choices, "kwargs": kwargs}
        )
        return FakeQuestion(self.answer)

    def checkbox(self, message, choices=None, **kwargs):
        return self._record("checkbox", message, choices, **kwargs)

    def select(self, message, choices=None, **kwargs):
        return self._record("select", message, choices, **kwargs)

    def confirm(self, message, **kwargs):
        return self._record("confirm", message, **kwargs)

    @property
    def call(self):
        assert len(self.calls) == 1, f"expected one prompt, got {len(self.calls)}"
        return self.calls[0]


@pytest.fixture()
def fake_questionary(monkeypatch):
    """Install a recording `questionary` for the lazy import inside each prompt."""

    def install(answer=None):
        fake = FakeQuestionary(answer)
        monkeypatch.setitem(sys.modules, "questionary", fake)
        return fake

    return install


REGISTRY_ROWS = (
    ("claude", "Claude Code", "CLAUDE.md", ".claude/skills"),
    ("agents-md", "AGENTS.md — Codex, Cursor, Windsurf", "AGENTS.md", None),
    ("gemini", "Gemini CLI", "GEMINI.md", None),
    ("none", "None — skills to .lore/skills/", None, None),
)


def _targets():
    from lore.initplan import AgentTarget

    return tuple(
        AgentTarget(id=row[0], label=row[1], instruction_file=row[2], skills_dir=row[3])
        for row in REGISTRY_ROWS
    )


FAMILIES = ("machinery", "memory", "workflow")


def _values(call):
    return [choice.value for choice in call["choices"]]


def _checked(call):
    return [choice.value for choice in call["choices"] if choice.checked]


def _titles(call):
    return [str(choice.title) for choice in call["choices"]]


# ---------------------------------------------------------------------------
# The lazy-import and dependency-direction invariants
# ---------------------------------------------------------------------------


class TestModuleShape:
    """`prompts.py` costs nothing to import and reaches no business module."""

    def test_questionary_is_imported_only_inside_functions(self):
        tree = ast.parse(PROMPTS_SOURCE.read_text(encoding="utf-8"))
        module_level = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                module_level += [a.name for a in node.names if a.name == "questionary"]
            elif isinstance(node, ast.ImportFrom) and node.module == "questionary":
                module_level.append("questionary")
        assert module_level == [], (
            "src/lore/prompts.py imports questionary at module level; "
            "api.py aliases _prompts, so that would pull prompt_toolkit into "
            "every `lore ready`."
        )

    def test_questionary_is_imported_somewhere_inside_a_function(self):
        tree = ast.parse(PROMPTS_SOURCE.read_text(encoding="utf-8"))
        nested = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            and any(a.name == "questionary" for a in node.names)
        ]
        assert nested, "no function-level `import questionary` found"

    def test_the_only_lore_module_it_names_is_initplan(self):
        tree = ast.parse(PROMPTS_SOURCE.read_text(encoding="utf-8"))
        reached = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                reached |= {a.name for a in node.names if a.name.startswith("lore")}
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "lore":
                    reached |= {f"lore.{a.name}" for a in node.names}
                elif module.startswith("lore"):
                    reached.add(module)
        assert reached <= {"lore.initplan"}, (
            f"prompts.py reaches {sorted(reached)}; only lore.initplan is allowed"
        )


# ---------------------------------------------------------------------------
# Prompt 1 — agents
# ---------------------------------------------------------------------------


class TestAskAgents:
    def test_offers_one_choice_per_registry_row(self, fake_questionary):
        from lore import prompts

        fake = fake_questionary(["claude"])
        prompts.ask_agents(_targets())
        assert _values(fake.call) == [row[0] for row in REGISTRY_ROWS]

    def test_each_choice_shows_its_label_and_its_convention(self, fake_questionary):
        from lore import prompts

        fake = fake_questionary(["claude"])
        prompts.ask_agents(_targets())
        titles = {choice.value: str(choice.title) for choice in fake.call["choices"]}
        assert "Claude Code" in titles["claude"]
        assert "CLAUDE.md" in titles["claude"]
        assert ".claude/skills" in titles["claude"]
        assert "AGENTS.md" in titles["agents-md"]
        assert ".lore/skills" in titles["none"]

    def test_claude_is_preselected_when_nothing_is_recorded(self, fake_questionary):
        from lore import prompts

        fake = fake_questionary(["claude"])
        prompts.ask_agents(_targets())
        assert _checked(fake.call) == ["claude"]

    def test_a_recorded_selection_is_preselected_instead(self, fake_questionary):
        from lore import prompts

        fake = fake_questionary(["gemini"])
        prompts.ask_agents(_targets(), selected=("gemini", "agents-md"))
        assert sorted(_checked(fake.call)) == ["agents-md", "gemini"]

    def test_returns_a_list_of_registry_ids(self, fake_questionary):
        from lore import prompts

        fake_questionary(["claude", "gemini"])
        assert prompts.ask_agents(_targets()) == ["claude", "gemini"]

    def test_it_is_a_checkbox(self, fake_questionary):
        from lore import prompts

        fake = fake_questionary([])
        prompts.ask_agents(_targets())
        assert fake.call["kind"] == "checkbox"


# ---------------------------------------------------------------------------
# Prompt 2 — access mode
# ---------------------------------------------------------------------------


class TestAskAccessMode:
    def test_offers_exactly_two_choices(self, fake_questionary):
        from lore import prompts

        fake = fake_questionary("native")
        prompts.ask_access_mode()
        assert _values(fake.call) == ["native", "cli"]

    def test_native_is_preselected(self, fake_questionary):
        from lore import prompts

        fake = fake_questionary("native")
        prompts.ask_access_mode()
        assert fake.call["kwargs"]["default"] == "native"

    def test_a_recorded_answer_is_preselected_instead(self, fake_questionary):
        from lore import prompts

        fake = fake_questionary("cli")
        prompts.ask_access_mode(current="cli")
        assert fake.call["kwargs"]["default"] == "cli"

    def test_the_prompt_states_that_the_choice_covers_three_stores_only(
        self, fake_questionary
    ):
        from lore import prompts

        fake = fake_questionary("native")
        prompts.ask_access_mode()
        message = fake.call["message"]
        for word in ("codex", "rites", "glossary"):
            assert word in message
        assert "CLI" in message

    def test_returns_an_access_mode_token(self, fake_questionary):
        from lore import prompts

        fake_questionary("cli")
        assert prompts.ask_access_mode() == "cli"


# ---------------------------------------------------------------------------
# Prompt 3 — skill families
# ---------------------------------------------------------------------------


class TestAskSkillFamilies:
    def test_offers_one_choice_per_family(self, fake_questionary):
        from lore import prompts

        fake = fake_questionary(["memory"])
        prompts.ask_skill_families(FAMILIES)
        assert sorted(_values(fake.call)) == sorted(FAMILIES)

    def test_memory_and_workflow_are_preselected_and_machinery_is_not(
        self, fake_questionary
    ):
        from lore import prompts

        fake = fake_questionary(["memory", "workflow"])
        prompts.ask_skill_families(FAMILIES)
        assert sorted(_checked(fake.call)) == ["memory", "workflow"]

    def test_a_recorded_selection_is_preselected_instead(self, fake_questionary):
        from lore import prompts

        fake = fake_questionary(["machinery"])
        prompts.ask_skill_families(FAMILIES, selected=("machinery",))
        assert _checked(fake.call) == ["machinery"]

    def test_never_offers_or_returns_an_aggregate_token(self, fake_questionary):
        from lore import prompts

        fake = fake_questionary(["memory", "workflow"])
        answer = prompts.ask_skill_families(FAMILIES)
        assert "all" not in _values(fake.call)
        assert "none" not in _values(fake.call)
        assert answer == ["memory", "workflow"]
        assert "all" not in answer and "none" not in answer

    def test_an_empty_selection_is_an_empty_list_not_none(self, fake_questionary):
        from lore import prompts

        fake_questionary([])
        assert prompts.ask_skill_families(FAMILIES) == []


# ---------------------------------------------------------------------------
# Prompt 4 — an instruction file that exists and carries no markers
# ---------------------------------------------------------------------------


class TestAskExistingAgentFile:
    def test_offers_append_and_skip_only(self, fake_questionary):
        from lore import prompts

        fake = fake_questionary("append")
        prompts.ask_existing_agent_file(("CLAUDE.md",))
        assert _values(fake.call) == ["append", "skip"]
        assert "separate" not in _values(fake.call)

    def test_the_prompt_names_the_file(self, fake_questionary):
        from lore import prompts

        fake = fake_questionary("append")
        prompts.ask_existing_agent_file(("CLAUDE.md",))
        assert "CLAUDE.md" in fake.call["message"]

    def test_append_is_preselected(self, fake_questionary):
        from lore import prompts

        fake = fake_questionary("append")
        prompts.ask_existing_agent_file(("CLAUDE.md",))
        assert fake.call["kwargs"]["default"] == "append"

    def test_returns_the_token(self, fake_questionary):
        from lore import prompts

        fake_questionary("skip")
        assert prompts.ask_existing_agent_file(("CLAUDE.md",)) == "skip"


# ---------------------------------------------------------------------------
# Prompt 5 — how the installed skills are tracked in git
# ---------------------------------------------------------------------------


class TestAskSkillsGitignore:
    def test_offers_exactly_three_options(self, fake_questionary):
        from lore import prompts

        fake = fake_questionary("lore-only")
        prompts.ask_skills_gitignore()
        assert _values(fake.call) == ["lore-only", "none", "all"]

    def test_lore_only_is_preselected(self, fake_questionary):
        from lore import prompts

        fake = fake_questionary("lore-only")
        prompts.ask_skills_gitignore()
        assert fake.call["kwargs"]["default"] == "lore-only"

    def test_a_recorded_answer_is_preselected_instead(self, fake_questionary):
        from lore import prompts

        fake = fake_questionary("all")
        prompts.ask_skills_gitignore(current="all")
        assert fake.call["kwargs"]["default"] == "all"

    def test_returns_the_token(self, fake_questionary):
        from lore import prompts

        fake_questionary("none")
        assert prompts.ask_skills_gitignore() == "none"


# ---------------------------------------------------------------------------
# Prompt 6 — a file Lore did not install, where Lore would write
# ---------------------------------------------------------------------------


class TestAskOnConflict:
    def test_offers_exactly_two_options_with_skip_preselected(self, fake_questionary):
        from lore import prompts

        fake = fake_questionary("skip")
        prompts.ask_on_conflict(2)
        assert _values(fake.call) == ["skip", "overwrite"]
        assert fake.call["kwargs"]["default"] == "skip"

    def test_the_prompt_carries_the_conflict_count(self, fake_questionary):
        from lore import prompts

        fake = fake_questionary("skip")
        prompts.ask_on_conflict(7)
        assert "7" in fake.call["message"]

    def test_returns_the_token(self, fake_questionary):
        from lore import prompts

        fake_questionary("overwrite")
        assert prompts.ask_on_conflict(1) == "overwrite"

    def test_it_asks_about_files_lore_did_not_install(self, fake_questionary):
        """The question names the only class of file it can still settle.

        It used to be asked about Lore's own files too, offering to "take the
        shipped version" — which for a retired file deleted it, and which is
        now simply what a run does. A question is owed to somebody only where
        both answers do something.
        """
        from lore import prompts

        fake = fake_questionary("skip")
        prompts.ask_on_conflict(2)
        assert "did not install" in fake.call["message"]

    def test_it_does_not_speak_of_edits_at_all(self, fake_questionary):
        """These are not files anybody edited: Lore never wrote them."""
        from lore import prompts

        fake = fake_questionary("skip")
        prompts.ask_on_conflict(2)
        rendered = fake.call["message"] + " ".join(_titles(fake.call))
        assert "edit" not in rendered.lower()
        assert "shipped version" not in rendered

    def test_the_two_tokens_never_change_whatever_the_count(self, fake_questionary):
        from lore import prompts

        for count in (1, 2, 9):
            fake = fake_questionary("skip")
            prompts.ask_on_conflict(count)
            assert _values(fake.call) == ["skip", "overwrite"], count
            assert fake.call["kwargs"]["default"] == "skip"


# ---------------------------------------------------------------------------
# Prompt 7 — the summary confirm
# ---------------------------------------------------------------------------


class TestAskConfirmPlan:
    def test_is_a_confirm_defaulting_to_yes(self, fake_questionary):
        from lore import prompts

        fake = fake_questionary(True)
        prompts.ask_confirm_plan()
        assert fake.call["kind"] == "confirm"
        assert fake.call["kwargs"]["default"] is True

    def test_the_prompt_asks_whether_to_apply(self, fake_questionary):
        from lore import prompts

        fake = fake_questionary(True)
        prompts.ask_confirm_plan()
        assert "Apply this plan?" in fake.call["message"]

    def test_returns_a_bool(self, fake_questionary):
        from lore import prompts

        fake_questionary(False)
        assert prompts.ask_confirm_plan() is False


# ---------------------------------------------------------------------------
# The abort signal — uniform across every function
# ---------------------------------------------------------------------------


def _every_prompt_call(prompts):
    """One zero-work invocation per prompt function, with its required arguments."""
    return {
        "ask_agents": lambda: prompts.ask_agents(_targets()),
        "ask_access_mode": lambda: prompts.ask_access_mode(),
        "ask_skill_families": lambda: prompts.ask_skill_families(FAMILIES),
        "ask_existing_agent_file": lambda: prompts.ask_existing_agent_file(("CLAUDE.md",)),
        "ask_skills_gitignore": lambda: prompts.ask_skills_gitignore(),
        "ask_on_conflict": lambda: prompts.ask_on_conflict(1),
        "ask_confirm_plan": lambda: prompts.ask_confirm_plan(),
    }


class TestTheAbortSignal:
    """questionary returns None on Ctrl-C; every function passes that through."""

    def test_every_prompt_returns_none_when_questionary_does(self, fake_questionary):
        from lore import prompts

        fake_questionary(None)
        for name, call in _every_prompt_call(prompts).items():
            assert call() is None, f"{name} did not pass the abort signal through"

    def test_the_module_exposes_exactly_the_seven_questions(self):
        from lore import prompts

        asks = sorted(name for name in dir(prompts) if name.startswith("ask_"))
        assert asks == sorted(_every_prompt_call(prompts))

    def test_prompts_raises_no_click_abort_of_its_own(self):
        """The abort surfaces at the CLI boundary; `prompts.py` stays click-free."""
        source = PROMPTS_SOURCE.read_text(encoding="utf-8")
        assert "click" not in source
