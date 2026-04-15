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
    # Link is either a codex anchor id or a `lore codex show ...` invocation.
    assert (
        "conceptual-workflows-help" in result.output
        or "lore codex show" in result.output
    )
