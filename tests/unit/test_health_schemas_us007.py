"""Unit tests for US-007 — `--scope schemas` filter composition and gating.

US-007 Red — schema-validation-us-007
Workflow: conceptual-workflows-health (lore codex show conceptual-workflows-health)

Sharpens coverage of the `--scope schemas` filter beyond what US-004/US-005
already pinned. Focuses on:

- `_check_schemas` is the ONLY checker invoked when `scopes=['schemas']`
- Non-schema checkers run untouched when `schemas` is excluded
- ADR-012 composition of `--scope <non-schema> schemas`
- CLI `--scope` click.Choice explicitly lists `schemas` as a tuple member
- CLI `--help` output mentions `schemas` (docstring + example)
- CLI rejects a typo like `--scope schema` with exit 2

No production code. Some tests may already pass against US-004/US-005 green —
the intent is a freezing contract for US-007.
"""

from __future__ import annotations

from pathlib import Path

import click
import pytest

import lore.cli as cli
import lore.health as health_mod
from lore.health import _ALL_SCOPES, health_check


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _skeleton(root: Path) -> Path:
    lore = root / ".lore"
    for d in ("knights", "doctrines", "codex", "artifacts", "watchers"):
        (lore / d).mkdir(parents=True, exist_ok=True)
    return root


def _bad_knight(root: Path) -> Path:
    p = (
        root
        / ".lore"
        / "knights"
        / "default"
        / "feature-implementation"
        / "pm.md"
    )
    _write(
        p,
        "---\nid: pm\ntitle: PM\nsummary: s\nstability: x\n---\n# body\n",
    )
    return p


def _doctrine_with_broken_knight_ref(root: Path) -> None:
    d = root / ".lore" / "doctrines" / "default" / "feat-x"
    _write(
        d / "feat-x.yaml",
        "id: feat-x\nsteps:\n"
        "  - id: step-1\n    title: S1\n    type: knight\n"
        "    knight: ghost-knight\n",
    )
    _write(
        d / "feat-x.design.md",
        "---\nid: feat-x\ntitle: X\nsummary: s\n---\nBody.\n",
    )


@pytest.fixture()
def tmp_project_with_bad_knight_and_bad_ref(tmp_path):
    _skeleton(tmp_path)
    _bad_knight(tmp_path)
    _doctrine_with_broken_knight_ref(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# _ALL_SCOPES — tuple identity (freeze API shape)
# ---------------------------------------------------------------------------


def test_all_scopes_is_tuple_and_contains_schemas():
    """US-007 contract: _ALL_SCOPES is a tuple and registers 'schemas'."""
    assert isinstance(_ALL_SCOPES, tuple)
    assert "schemas" in _ALL_SCOPES


def test_all_scopes_length_is_six_after_schemas_added():
    """Adding schemas grows _ALL_SCOPES (US-005 added glossary, bringing it to 7)."""
    assert len(_ALL_SCOPES) == 7


# ---------------------------------------------------------------------------
# scope=['schemas'] — only _check_schemas runs, other checkers are untouched
# ---------------------------------------------------------------------------


def test_scope_schemas_does_not_invoke_codex_checker(
    tmp_project_with_bad_knight_and_bad_ref, monkeypatch
):
    """conceptual-workflows-health — scoped runs must not call other checkers."""
    called = []

    def spy(*args, **kwargs):
        called.append("_check_codex")
        return []

    monkeypatch.setattr(health_mod, "_check_codex", spy)
    health_check(
        project_root=tmp_project_with_bad_knight_and_bad_ref,
        scopes=["schemas"],
    )
    assert called == []


def test_scope_schemas_does_not_invoke_doctrines_checker(
    tmp_project_with_bad_knight_and_bad_ref, monkeypatch
):
    called = []

    def spy(*args, **kwargs):
        called.append("_check_doctrines")
        return []

    monkeypatch.setattr(health_mod, "_check_doctrines", spy)
    health_check(
        project_root=tmp_project_with_bad_knight_and_bad_ref,
        scopes=["schemas"],
    )
    assert called == []


def test_scope_schemas_does_not_invoke_artifacts_watchers_knights_checkers(
    tmp_project_with_bad_knight_and_bad_ref, monkeypatch
):
    called: list[str] = []
    for name in ("_check_artifacts", "_check_watchers", "_check_knights"):
        def make(n=name):
            def spy(*args, **kwargs):
                called.append(n)
                return []
            return spy
        monkeypatch.setattr(health_mod, name, make())

    health_check(
        project_root=tmp_project_with_bad_knight_and_bad_ref,
        scopes=["schemas"],
    )
    assert called == []


def test_scope_schemas_does_invoke_check_schemas(
    tmp_project_with_bad_knight_and_bad_ref, monkeypatch
):
    """scopes=['schemas'] wires _check_schemas exactly once."""
    calls = []
    real = health_mod._check_schemas

    def spy(project_root):
        calls.append(project_root)
        return real(project_root)

    monkeypatch.setattr(health_mod, "_check_schemas", spy)
    health_check(
        project_root=tmp_project_with_bad_knight_and_bad_ref,
        scopes=["schemas"],
    )
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# scope excluding schemas — _check_schemas is NOT called and no schema issues
# ---------------------------------------------------------------------------


def test_scope_without_schemas_does_not_call_check_schemas(
    tmp_project_with_bad_knight_and_bad_ref, monkeypatch
):
    called = []

    def spy(project_root):
        called.append(project_root)
        return []

    monkeypatch.setattr(health_mod, "_check_schemas", spy)
    health_check(
        project_root=tmp_project_with_bad_knight_and_bad_ref,
        scopes=["doctrines"],
    )
    assert called == []


def test_scope_doctrines_only_reports_non_schema_issues(
    tmp_project_with_bad_knight_and_bad_ref,
):
    """scopes=['doctrines'] returns broken_knight_ref and no schema issues."""
    report = health_check(
        project_root=tmp_project_with_bad_knight_and_bad_ref,
        scopes=["doctrines"],
    )
    checks = {i.check for i in report.issues}
    assert "schema" not in checks
    assert "broken_knight_ref" in checks


# ---------------------------------------------------------------------------
# ADR-012 composition — `--scope doctrines schemas` runs both
# ---------------------------------------------------------------------------


def test_scope_composition_runs_both_doctrines_and_schemas(
    tmp_project_with_bad_knight_and_bad_ref,
):
    """scopes=['doctrines','schemas'] yields BOTH schema and broken_knight_ref."""
    report = health_check(
        project_root=tmp_project_with_bad_knight_and_bad_ref,
        scopes=["doctrines", "schemas"],
    )
    checks = {i.check for i in report.issues}
    assert "schema" in checks
    assert "broken_knight_ref" in checks


def test_scope_composition_order_independent(
    tmp_project_with_bad_knight_and_bad_ref,
):
    """ADR-012 compose: scope order does not change the set of checks that run."""
    a = health_check(
        project_root=tmp_project_with_bad_knight_and_bad_ref,
        scopes=["doctrines", "schemas"],
    )
    b = health_check(
        project_root=tmp_project_with_bad_knight_and_bad_ref,
        scopes=["schemas", "doctrines"],
    )
    assert {i.check for i in a.issues} == {i.check for i in b.issues}


# ---------------------------------------------------------------------------
# CLI click.Choice — exact tuple membership + typo rejection
# ---------------------------------------------------------------------------


def _scope_param():
    return next(p for p in cli.health_cmd.params if p.name == "scope")


def test_cli_scope_param_is_multi_value():
    """ADR-012: --scope must be a multi-value click option."""
    param = _scope_param()
    assert param.multiple is True


def test_cli_scope_choice_contains_schemas_literal():
    """click.Choice explicitly lists the string 'schemas'."""
    param = _scope_param()
    assert isinstance(param.type, click.Choice)
    assert "schemas" in tuple(param.type.choices)


def test_cli_scope_choice_does_not_contain_typo_schema():
    """'schema' (singular typo) MUST NOT be a valid choice."""
    param = _scope_param()
    assert "schema" not in tuple(param.type.choices)


def test_cli_scope_choice_is_exact_six_scopes():
    """US-007 freezes the exact choice set to the six _ALL_SCOPES values."""
    param = _scope_param()
    assert sorted(param.type.choices) == sorted(_ALL_SCOPES)


# ---------------------------------------------------------------------------
# CLI --help text — mentions 'schemas'
# ---------------------------------------------------------------------------


def test_cli_health_help_mentions_schemas(runner=None):
    """`lore health --help` output contains the literal 'schemas'."""
    from click.testing import CliRunner

    result = CliRunner().invoke(cli.main, ["health", "--help"])
    assert result.exit_code == 0
    assert "schemas" in result.output


def test_cli_health_help_example_includes_schemas():
    """The --scope help string gives an example that mentions 'schemas'."""
    param = _scope_param()
    assert param.help is not None
    assert "schemas" in param.help


def test_cli_health_docstring_not_stale_five():
    """health_cmd docstring must not still claim 'five' entity types now
    that schemas is a sixth scope."""
    assert cli.health_cmd.help is not None
    assert "five" not in cli.health_cmd.help.lower()
