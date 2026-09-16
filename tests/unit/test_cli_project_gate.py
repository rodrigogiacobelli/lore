"""The FR-14 gate: which commands accept ``--project``.

Spec: ``nested-projects-spec`` — Part 4 "Unit", unit S3.

D-6 puts this rejection entirely in ``cli.py``, and that does not narrow
``decisions-011-api-parity-with-cli``: write functions have no ``scope``
parameter at all, so a Python caller cannot express the mistake and there is
nothing for a core counterpart to reject. The rule that *does* need a core
home is FR-17, and ``projects.reject_foreign`` is it.

The allow-list is a set of literal strings, so the tests here walk the real
Click tree: a typo in one of them would silently disable ``--project`` on a
command the spec says accepts it, and no other test would notice.
"""

from __future__ import annotations

import json

import click
import pytest
from click.testing import CliRunner

from lore import cli
from lore.cli import main


REJECTION = '--project is a read selector; it is not accepted on "{label}".'


# Part 2, "Commands that accept --project" — FR-13's list plus FR-13a's
# `watcher list|show` and `rite search`. Held here as well as in `cli.py` on
# purpose: this is the spec's list, and the point of the comparison below is
# that the shipped one still equals it.
SPEC_READ_COMMANDS: frozenset[str] = frozenset(
    {
        "codex list",
        "codex show",
        "codex search",
        "codex map",
        "doctrine list",
        "doctrine show",
        "artifact list",
        "artifact show",
        "watcher list",
        "watcher show",
        "rite list",
        "rite show",
        "rite search",
        "glossary list",
        "glossary search",
        "glossary show",
        "impacts",
    }
)


def resolve(label: str) -> click.Command:
    """Return the Click command named by a whitespace-joined ``label``."""
    command: click.Command = main
    for token in label.split():
        assert isinstance(command, click.Group), f"{label}: {token} has no parent group"
        command = command.commands[token]
    return command


def every_label() -> list[str]:
    """Every ``<group> <cmd>`` and top-level ``<cmd>`` label the CLI answers."""
    labels: list[str] = []
    for name, command in main.commands.items():
        if isinstance(command, click.Group):
            labels.extend(f"{name} {sub}" for sub in command.commands)
        else:
            labels.append(name)
    return labels


REJECTED_LABELS = sorted(
    label for label in every_label() if label not in SPEC_READ_COMMANDS
)


# ---------------------------------------------------------------------------
# The allow-list is real
# ---------------------------------------------------------------------------


def test_the_allow_list_has_seventeen_members():
    # nested-projects-spec — FR-13 + FR-13a: seventeen commands plus
    # `watcher list|show` and `rite search`, which G-1 and G-2 added, less the
    # two commands of the entity this release removed
    assert len(cli._PROJECT_READ_COMMANDS) == 17


def test_the_allow_list_matches_the_spec_exactly():
    # nested-projects-spec — Part 2 "Commands that accept --project"
    assert cli._PROJECT_READ_COMMANDS == SPEC_READ_COMMANDS


@pytest.mark.parametrize("label", sorted(SPEC_READ_COMMANDS))
def test_every_allow_listed_label_is_a_real_command(label):
    # nested-projects-spec — S3: a typo in the set disables the flag silently
    assert resolve(label) is not None


# ---------------------------------------------------------------------------
# Every command outside the allow-list rejects the flag
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("label", REJECTED_LABELS)
def test_a_command_outside_the_allow_list_rejects_the_flag(label, project_dir):
    # nested-projects-spec — FR-14 / failure table: exit 2 with the exact
    # message, raised in `invoke` and so ahead of the command's own body
    result = CliRunner().invoke(main, ["--project", "realm", *label.split(), "--help"])

    assert result.exit_code == 2, result.output
    assert f"Error: {REJECTION.format(label=label)}" in result.stderr


def test_the_bare_glossary_group_rejects_without_interpolating_none(project_dir):
    # nested-projects-spec — S3: `glossary` is invoke_without_command, so its
    # own invoke sees `invoked_subcommand is None`; the label is the group's
    # own name and never the literal "glossary None"
    result = CliRunner().invoke(main, ["--project", "realm", "glossary"])

    assert result.exit_code == 2, result.output
    assert f"Error: {REJECTION.format(label='glossary')}" in result.stderr


def test_the_bare_dashboard_rejects_without_interpolating_none(project_dir):
    # nested-projects-spec — S3: `lore` with no subcommand falls through to
    # the dashboard, which is a quest read
    result = CliRunner().invoke(main, ["--project", "realm"])

    assert result.exit_code == 2, result.output
    assert f"Error: {REJECTION.format(label='lore')}" in result.stderr


def test_the_rejection_is_an_error_envelope_under_json(project_dir):
    # nested-projects-spec — FR-14: `codex map`'s ConflictingDepthFlags
    # precedent — an envelope on stderr, still exit 2
    result = CliRunner().invoke(
        main, ["--json", "--project", "realm", "codex", "delete", "x"]
    )

    assert result.exit_code == 2
    assert json.loads(result.stderr) == {"error": REJECTION.format(label="codex delete")}


def test_an_allow_listed_command_is_not_gated(project_dir):
    # nested-projects-spec — FR-13 / FR-18: the gate refuses nothing on a
    # read command; an unknown project name is a runtime not-found at exit 1
    result = CliRunner().invoke(main, ["--project", "nope", "codex", "list"])

    assert result.exit_code == 1
    assert "read selector" not in result.stderr


def test_no_flag_means_no_gate(project_dir):
    # nested-projects-spec — SC-7: a command run without `--project` is
    # untouched by the gate. Passes at red by design — it pins behaviour this
    # feature must NOT change.
    result = CliRunner().invoke(main, ["stats"])

    assert result.exit_code == 0, result.output
    assert "read selector" not in result.stderr


# ---------------------------------------------------------------------------
# The health scope is untouched (S-1)
# ---------------------------------------------------------------------------


def test_lore_health_gains_no_scope_token():
    # nested-projects-spec — S-1 / B-2: `lore health` never reads another
    # project, so no scope, no flag and no column joins it, and the
    # pre-existing order divergence between the two tuples is left alone.
    # Passes at red by design.
    assert cli._VALID_SCOPES == (
        "codex",
        "artifacts",
        "doctrines",
        "watchers",
        "schemas",
        "glossary",
        "bindings",
        "rites",
        "voice",
        "skills",
    )
