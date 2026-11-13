"""The questions `lore init` asks a person, one function per question.

This is a CLI-layer module. Each function renders one prompt and returns the
answer in the exact shape ``plan_init`` accepts — nothing here decides
anything, and nothing here reads the project. Deciding *when* to ask, in what
order, and what to do with the answers is the orchestration in ``cli.py``
(decisions-011-api-parity-with-cli: a prompt fills a parameter, it never owns
a rule).

Two import rules hold this module in place, and both are pinned by tests:

* ``questionary`` is imported **inside** each function. ``api.py`` aliases
  ``_prompts`` so the CLI can reach it, and a module-level import would pull
  ``prompt_toolkit`` into every ``lore ready`` — ADR-001 makes per-invocation
  cost a design constraint.
* The only ``lore`` module it reaches is ``lore.initplan``, which gives it the
  agent row type and the headless defaults a question falls back to. The
  registry rows arrive as arguments, from the caller that already holds them.

``questionary`` returns ``None`` when the user presses Ctrl-C. Every function
passes that through unchanged; the caller turns it into an abort at the CLI
boundary, which is what keeps this module free of any command-framework import.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from lore.initplan import AgentTarget, Profile


DEFAULT_AGENTS: tuple[str, ...] = ("claude",)
"""Preselected in the agent checkbox when a project has recorded nothing."""


ROUTE_TITLE = (
    "Do you want your agents to use the Lore CLI, or let their own tools "
    "(the harness) handle creating, reading, updating and deleting Lore's files?"
)
"""The one question for the core (Doctrines, Artifacts) and every optional file feature."""

ROUTE_CHOICES: tuple[tuple[str, str], ...] = (
    (
        "harness",
        "Their own tools   Read, Write, Edit and Grep on the files under .lore/ "
        "(`lore health` still validates)",
    ),
    ("cli", "The Lore CLI      lore doctrine|artifact|codex|rite|glossary|watcher list, show, new, edit, delete"),
)
"""The route tokens with the line each is offered under."""

OPT_IN_QUESTIONS: dict[str, str] = {
    "memory": (
        "Memory: keep a codex, rites and glossary? (reading and writing follow the "
        "choice above)"
    ),
    "memory-search": (
        "Memory: use `lore codex|rite|glossary search`? (needs the Lore CLI)"
    ),
    "memory-index": (
        "Memory: use the codex index (`lore index`)? (the cheapest first search on a "
        "codex nobody has read; needs the Lore CLI and an authored index, which the "
        "update-index skill writes)"
    ),
    "memory-graph": (
        "Memory: use graph traversal and code bindings "
        "(`lore codex map`, `lore codex chaos`, `lore impacts`)? (needs the Lore CLI)"
    ),
    "quests": (
        "Quests & Missions: track work on Lore's board? (needs the Lore CLI: create, "
        "claim, done, block, dependencies, board messages, ready, list, show, stats, "
        "oracle)"
    ),
    "watchers": "Watchers: define watchers that react to project state? (they follow the choice above)",
}
"""The yes/no questions by id: the full prompt text."""


def _convention(target: AgentTarget) -> str:
    """The files an agent expects, as one short line beside its label."""
    parts = [target.instruction_file, f"{target.skills_dir}/" if target.skills_dir else None]
    return " + ".join(part for part in parts if part)


def ask_agents(
    targets: Iterable[AgentTarget], selected: Sequence[str] = ()
) -> list[str] | None:
    """Ask which coding agents the project uses. Returns registry ids.

    Every registry row is offered with its label and the files it expects, so
    the choice is legible without knowing the registry. *selected* preselects
    what the project already recorded; an empty one falls back to Claude Code.
    """
    import questionary

    rows = tuple(targets)
    preselected = set(selected) or set(DEFAULT_AGENTS)
    choices = [
        questionary.Choice(
            title=f"{row.label:<24}  {_convention(row)}".rstrip(),
            value=row.id,
            checked=row.id in preselected,
        )
        for row in rows
    ]
    return questionary.checkbox(
        "Which coding agents does this project use?",
        choices=choices,
        instruction="(space to toggle, enter to accept)",
    ).ask()


def ask_route(current: str | None = None) -> str | None:
    """Ask how agents work with Lore's files. Returns a route token.

    *current* places the cursor: the recorded or migrated route, else the
    headless default.
    """
    import questionary

    if current is None:
        current = Profile().route.value
    choices = [questionary.Choice(title=title, value=token) for token, title in ROUTE_CHOICES]
    return questionary.select(ROUTE_TITLE, choices=choices, default=str(current)).ask()


def ask_opt_in(question_id: str, current: bool = False) -> bool | None:
    """Ask a yes/no. Defaults to *current*."""
    import questionary

    if question_id not in OPT_IN_QUESTIONS:
        raise ValueError(f"'{question_id}' is not a yes/no question.")
    return questionary.confirm(OPT_IN_QUESTIONS[question_id], default=bool(current)).ask()


def ask_existing_agent_file(instruction_files: Iterable[str]) -> str | None:
    """Ask what to do with instruction files that exist and carry no markers.

    Two answers, not three: ``.lore/LORE-AGENT.md`` is written either way, so a
    third "write it separately" option would produce identical bytes to
    ``skip``.
    """
    import questionary

    named = ", ".join(instruction_files)
    choices = [
        questionary.Choice(
            title="Append a Lore section    wrapped in <!-- lore:begin --> … <!-- lore:end -->",
            value="append",
        ),
        questionary.Choice(
            title="Leave it alone           .lore/LORE-AGENT.md is written either way",
            value="skip",
        ),
    ]
    return questionary.select(
        f"{named} already exists and carries no Lore markers. What should Lore do?",
        choices=choices,
        default="append",
    ).ask()


def ask_skills_gitignore(current: str = "lore-only") -> str | None:
    """Ask how the installed skills should be tracked in git."""
    import questionary

    choices = [
        questionary.Choice(
            title="Ignore Lore's skills, track my own    writes a .gitignore beside them",
            value="lore-only",
        ),
        questionary.Choice(
            title="Track everything                      teammates get skills without installing lore",
            value="none",
        ),
        questionary.Choice(
            title="Ignore the whole directory            your own skills there included",
            value="all",
        ),
    ]
    return questionary.select(
        "How should the installed skills be tracked in git?",
        choices=choices,
        default=str(current),
    ).ask()


def ask_on_conflict(unrecognised: int) -> str | None:
    """Ask what to do about paths holding a file Lore did not install.

    The one conflict a person is still asked about, and the question says
    exactly which files it means. It used to also cover Lore's own files that
    the project had edited, offering to "take the shipped version" — an answer
    that for a retired file deleted it, and that is now simply what happens:
    Lore owns what Lore installed, so there is nothing there to ask.

    What is left is a file **the project** put where Lore wants to write one.
    Both answers are real. ``skip`` leaves it and Lore writes nothing at that
    path; ``overwrite`` hands the path to Lore.
    """
    import questionary

    choices = [
        questionary.Choice(title=_LEAVE_MINE_ALONE, value="skip"),
        questionary.Choice(title=_TAKE_THE_PATH, value="overwrite"),
    ]
    return questionary.select(
        f"{unrecognised} file(s) Lore did not install sit where Lore would "
        "write. What should Lore do?",
        choices=choices,
        default="skip",
    ).ask()


_LEAVE_MINE_ALONE = (
    "Leave mine alone    Lore writes nothing there; the report names each one"
)

_TAKE_THE_PATH = (
    "Overwrite           discard my file and let Lore own the path"
)


def ask_confirm_plan() -> bool | None:
    """Ask for the go-ahead on the rendered plan. Nothing is written before it."""
    import questionary

    return questionary.confirm("Apply this plan?", default=True).ask()
