"""E2E --help enrichment tests for US-009.

anchor: conceptual-workflows-help (ADR-008 teaching contract)
Spec: lore codex show group-param-us-009
"""

import re

import pytest

from lore.cli import main


# ---------------------------------------------------------------------------
# Scenarios 1-4: `new` subcommands surface --group + nested example
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cmd",
    [
        ["doctrine", "new", "--help"],
        ["knight", "new", "--help"],
        ["watcher", "new", "--help"],
        ["artifact", "new", "--help"],
    ],
)
def test_new_help_contains_group_and_nested_example(runner, cmd):
    """Each `new --help` advertises --group plus a concrete nested example.

    Must contain an actual `--group a/b` style example in an invocation line —
    not just path hints like ``.lore/knights/``.
    """
    result = runner.invoke(main, cmd)
    assert result.exit_code == 0, result.output
    assert "--group" in result.output
    # Require a literal `--group <token>/<token>` example invocation.
    assert re.search(
        r"--group\s+[a-z][a-z0-9\-_]*/[a-z][a-z0-9\-_/]*",
        result.output,
    ), f"no `--group a/b` example in {cmd} help:\n{result.output}"


@pytest.mark.parametrize(
    "cmd",
    [
        ["doctrine", "new", "--help"],
        ["knight", "new", "--help"],
        ["watcher", "new", "--help"],
        ["artifact", "new", "--help"],
    ],
)
def test_new_help_contains_example_invocation(runner, cmd):
    """Each `new --help` shows a full `lore ... new ... --group a/b` example."""
    result = runner.invoke(main, cmd)
    assert result.exit_code == 0, result.output
    assert re.search(
        r"lore\s+\w+\s+new\s+\S+.*--group\s+\S+/\S+",
        result.output,
    ), f"no full example invocation in {cmd} help:\n{result.output}"


def test_doctrine_new_help_mentions_default_root(runner):
    """doctrine new --help teaches the default root (.lore/doctrines)."""
    result = runner.invoke(main, ["doctrine", "new", "--help"])
    assert result.exit_code == 0
    assert "--group" in result.output
    # Hints that omitting --group lands at the root.
    assert "default" in result.output.lower() or "root" in result.output.lower()


# ---------------------------------------------------------------------------
# Scenario 5: doctrine list --help documents slash-delimited filter
# ---------------------------------------------------------------------------


def test_doctrine_list_help_shows_slash_filter(runner):
    result = runner.invoke(main, ["doctrine", "list", "--help"])
    assert result.exit_code == 0
    assert "--filter" in result.output
    assert re.search(r"\S+/\S+", result.output), result.output


# ---------------------------------------------------------------------------
# Scenario 6: all five list commands advertise slash-delimited filter
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cmd",
    [
        ["doctrine", "list", "--help"],
        ["knight", "list", "--help"],
        ["watcher", "list", "--help"],
        ["artifact", "list", "--help"],
        ["codex", "list", "--help"],
    ],
)
def test_all_list_help_advertise_slash_filter(runner, cmd):
    result = runner.invoke(main, cmd)
    assert result.exit_code == 0, result.output
    assert "--filter" in result.output
    assert "/" in result.output
    # An example with an actual slash-delimited token.
    assert re.search(r"\S+/\S+", result.output), (
        f"no slash example in {cmd} help:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# Link to conceptual-workflows-help doctrine anchor (teaching contract)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cmd",
    [
        ["doctrine", "list", "--help"],
        ["knight", "list", "--help"],
        ["watcher", "list", "--help"],
        ["artifact", "list", "--help"],
        ["codex", "list", "--help"],
    ],
)
def test_list_help_links_to_filter_grammar_doc(runner, cmd):
    """Each list --help points the reader at the filter grammar doctrine."""
    result = runner.invoke(main, cmd)
    assert result.exit_code == 0
    # Link is a codex anchor id, a `lore codex show ...` invocation, or
    # a codex.md path pointer (post-bootstrap-restructure form).
    assert (
        "conceptual-workflows-help" in result.output
        or "lore codex show" in result.output
        or "codex.md" in result.output
    )


# ---------------------------------------------------------------------------
# `lore init --help` — the flag surface and the JSON exception
# Spec: interactive-init-us-016 Scenario 7 (ADR-008 teaching contract)
# ---------------------------------------------------------------------------


INIT_FLAGS = (
    "--agent",
    "--access",
    "--skills",
    "--on-existing-agent-file",
    "--skills-gitignore",
    "--on-conflict",
    "--yes",
    "--reconfigure",
    "--dry-run",
)

JSON_EXCEPTION_SENTENCE = (
    "JSON output is not supported for this command. Use the Python API — "
    "lore.api.plan_init() returns a typed InitPlan describing every create, "
    "overwrite, removal and conflict without performing any of them."
)


def _init_help(runner) -> str:
    result = runner.invoke(main, ["init", "--help"])
    assert result.exit_code == 0, result.output
    return result.output


@pytest.mark.parametrize("flag", INIT_FLAGS)
def test_init_help_names_every_flag(runner, flag):
    """Every prompt's flag equivalent is discoverable from the help alone."""
    assert flag in _init_help(runner)


def test_init_help_states_the_json_exception(runner):
    """ADR-008: help teaches the fact rather than leaving a silently-ignored flag."""
    collapsed = " ".join(_init_help(runner).split())
    assert JSON_EXCEPTION_SENTENCE in collapsed


def test_init_help_shows_multi_value_flags_in_their_space_separated_form(runner):
    """ADR-012: the documented form is `--agent ID [ID ...]`, never a repeated flag."""
    text = _init_help(runner)
    assert "--agent ID [ID ...]" in text or "ID [ID ...]" in text
    assert "FAMILY [FAMILY ...]" in text
    assert "--agent ID --agent" not in text


def test_init_help_shows_the_short_yes_flag(runner):
    assert "-y, --yes" in _init_help(runner)


def test_init_help_says_lore_replaces_the_files_it_installed(runner):
    """ADR-008: the destructive half of a command is taught, never discovered.

    Re-running `lore init` discards an edit to a skill, knight, doctrine,
    artifact or watcher Lore shipped, and asks nobody first.
    """
    collapsed = " ".join(_init_help(runner).split())
    assert "Lore owns the files it installs" in collapsed


def test_init_help_says_where_a_skill_of_your_own_goes(runner):
    """The convention `default/` states for the other four entity types.

    Knights, doctrines, artifacts and watchers are seeded under a `default/`
    subdirectory, which tells a reader where the boundary is. Skills install
    straight into the agent's own directory and have no such marker, so the
    help is where the boundary has to be stated — losing an edit is the ruling,
    losing one with no way to avoid the next is not.
    """
    collapsed = " ".join(_init_help(runner).split())
    assert ".claude/skills/<your-own-id>/" in collapsed
    assert "an id Lore does not ship" in collapsed
