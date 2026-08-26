"""Unit tests for the `lore health` CLI surface — US-001 scope vocabulary.

Workflow: conceptual-workflows-health (lore codex show conceptual-workflows-health)

Pins the click `--scope` choice plumbing for the `bindings` token:

- `cli._VALID_SCOPES` declaration order and length.
- The click `--scope` parameter on `health_cmd` exposes a `click.Choice` whose
  `choices` list mirrors `_VALID_SCOPES` exactly (so `--help` and the
  click usage-error string both surface `bindings`).

These tests assert the post-US-001 shape and will fail until Green lands.
"""

from __future__ import annotations

import click


def test_valid_scopes_tuple_shape():
    """US-001 unit — `_VALID_SCOPES` token tuple; `skills` appended last after `voice`."""
    from lore.cli import _VALID_SCOPES

    assert _VALID_SCOPES == (
        "codex",
        "artifacts",
        "doctrines",
        "knights",
        "watchers",
        "schemas",
        "glossary",
        "bindings",
        "rites",
        "voice",
        "skills",
    )
    assert _VALID_SCOPES[-1] == "skills"
    assert len(_VALID_SCOPES) == 11


def test_valid_scopes_matches_the_health_scope_vocabulary():
    """interactive-init-us-021 — one vocabulary, declared in two places.

    `click.Choice` needs a list at decorator time and `health_check` needs the
    default scan set; a token in one and not the other is a scope reachable
    from only one surface (ADR-011).
    """
    from lore.cli import _VALID_SCOPES
    from lore.health import _ALL_SCOPES

    assert set(_VALID_SCOPES) == set(_ALL_SCOPES)


def test_health_cmd_scope_choice_matches_valid_scopes():
    """US-001 unit — health_cmd `--scope` option is a click.Choice over `_VALID_SCOPES`."""
    from lore.cli import _VALID_SCOPES, health_cmd

    scope_param = next(p for p in health_cmd.params if p.name == "scope")
    assert isinstance(scope_param.type, click.Choice)
    assert tuple(scope_param.type.choices) == _VALID_SCOPES
