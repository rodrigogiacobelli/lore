"""Unit tests for US-009 --help enrichment on new + list subcommands.

anchor: conceptual-workflows-help (ADR-008 teaching contract)
Spec: lore codex show group-param-us-009

Asserts the Click command objects' help surface (docstring + option help)
contain the teaching substrings required by the acceptance criteria.
"""

import pytest


def _help_surface(cmd) -> str:
    """Concatenate Click command help + per-option help strings."""
    parts = [cmd.help or "", cmd.callback.__doc__ or ""]
    for p in cmd.params:
        parts.append(getattr(p, "help", "") or "")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# `new` subcommands: --group + slash example
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "handler_name",
    ["doctrine_new", "knight_new", "watcher_new", "artifact_new"],
)
def test_new_click_help_contains_group_and_slash(handler_name):
    from lore import cli

    cmd = getattr(cli, handler_name)
    text = _help_surface(cmd)
    assert "--group" in text, f"{handler_name} help missing --group:\n{text}"
    assert "/" in text, f"{handler_name} help missing slash example:\n{text}"


@pytest.mark.parametrize(
    "handler_name",
    # doctrine_new already ships a hyphenated nested example — exclude from red.
    ["knight_new", "watcher_new", "artifact_new"],
)
def test_new_group_option_help_includes_example(handler_name):
    """The --group option's help= string shows a concrete `a/b` example."""
    from lore import cli

    cmd = getattr(cli, handler_name)
    group_opt = next(
        (p for p in cmd.params if "--group" in getattr(p, "opts", [])),
        None,
    )
    assert group_opt is not None, f"{handler_name} has no --group option"
    help_str = group_opt.help or ""
    import re as _re

    # Match a hyphenated multi-segment nested example (e.g. `seo-analysis/keyword-analysers`),
    # not a mere path hint like `.lore/knights/`. Require at least one hyphen in
    # one of the segments to distinguish from bare directory names.
    assert _re.search(
        r"(?<![./\w])[a-z][a-z0-9\-_]*-[a-z0-9\-_]*/[a-z][a-z0-9\-_/]*",
        help_str,
    ), f"{handler_name} --group help missing hyphenated nested example: {help_str!r}"


# ---------------------------------------------------------------------------
# `list` subcommands: --filter documents slash-delimited grammar
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "handler_name",
    [
        "doctrine_list",
        "knight_list",
        "watcher_list",
        "artifact_list",
        "codex_list",
    ],
)
def test_list_click_help_documents_slash_filter(handler_name):
    from lore import cli

    cmd = getattr(cli, handler_name)
    text = _help_surface(cmd)
    assert "--filter" in text, f"{handler_name} help missing --filter:\n{text}"
    assert "/" in text, f"{handler_name} help missing slash example:\n{text}"


@pytest.mark.parametrize(
    "handler_name",
    [
        "doctrine_list",
        "knight_list",
        "watcher_list",
        "artifact_list",
        "codex_list",
    ],
)
def test_list_filter_option_help_teaches_slash_delimited(handler_name):
    """The --filter option's own help= string teaches slash-delimited tokens."""
    from lore import cli

    cmd = getattr(cli, handler_name)
    filter_opt = next(
        (p for p in cmd.params if "--filter" in getattr(p, "opts", [])),
        None,
    )
    assert filter_opt is not None, f"{handler_name} has no --filter option"
    opt_help = (filter_opt.help or "").lower()
    assert "slash" in opt_help or "/" in (filter_opt.help or "")
