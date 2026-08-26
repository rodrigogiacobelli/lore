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
* The only ``lore`` module it reaches is ``lore.initplan``, which gives it
  ``AccessMode`` and nothing else. The registry rows and family ids arrive as
  arguments, from the caller that already holds them.

``questionary`` returns ``None`` when the user presses Ctrl-C. Every function
passes that through unchanged; the caller turns it into an abort at the CLI
boundary, which is what keeps this module free of any command-framework import.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from lore.initplan import AccessMode, AgentTarget


DEFAULT_AGENTS: tuple[str, ...] = ("claude",)
"""Preselected in the agent checkbox when a project has recorded nothing."""

DEFAULT_SKILL_FAMILIES: tuple[str, ...] = ("memory", "workflow")
"""Preselected in the family checkbox. Machinery is opt-in: a project that
never edits a doctrine or a knight does not need the five skills that do."""

ACCESS_SCOPE_NOTE = (
    "  (codex, rites and the glossary only — quests, missions, artifacts,\n"
    "   knights, doctrines and watchers always go through the Lore CLI)"
)
"""The access-mode answer's blast radius, stated at the prompt because it is
not guessable from the question."""


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


def ask_access_mode(current: str = AccessMode.NATIVE) -> str | None:
    """Ask whether agents use their own file tools or the Lore CLI."""
    import questionary

    choices = [
        questionary.Choice(
            title="Their own tools     Read/Write/Edit directly; `lore health` validates after",
            value=AccessMode.NATIVE.value,
        ),
        questionary.Choice(
            title="The Lore CLI        every read and write goes through `lore ...`",
            value=AccessMode.CLI.value,
        ),
    ]
    return questionary.select(
        f"How should agents read and write Lore's local files?\n{ACCESS_SCOPE_NOTE}",
        choices=choices,
        default=str(current),
    ).ask()


def ask_skill_families(
    families: Iterable[str], selected: Sequence[str] = ()
) -> list[str] | None:
    """Ask which skill families to install. Returns concrete family ids.

    The aggregates ``all`` and ``none`` are a flag convenience; a checkbox
    already says the same thing by having every box ticked or none.
    """
    import questionary

    preselected = set(selected) or set(DEFAULT_SKILL_FAMILIES)
    choices = [
        questionary.Choice(title=family, value=family, checked=family in preselected)
        for family in families
    ]
    return questionary.checkbox(
        "Which skill families should be installed?",
        choices=choices,
        instruction="(space to toggle, enter to accept)",
    ).ask()


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
