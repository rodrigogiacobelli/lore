"""E2E tests for `lore health --scope index`.

Spec: codex-index-spec — Part 1 workflow W8, Part 2 "`lore health --scope
index`" and Part 4 "E2E". The checker itself is the core lane's; what this file
pins is the surface: that `index` is a scope token Click accepts, that the rows
reach the terminal in the documented wording and order, and that a read-only
audit still writes nothing.

`duplicate_slug` is a WARNING at exit 0 — Pre-Dev escalation E1 demoted it from
the error Part 2's check table first carried.
"""

from __future__ import annotations

import json
from pathlib import Path

from lore.cli import main

W8_WARNINGS = """\
WARNING  index  gamma-hub  unauthored_cluster: cluster of 5 documents has no entry in .lore/index/authored.yaml
WARNING  index  solo  unauthored_cluster: cluster of 1 document has no entry in .lore/index/authored.yaml
WARNING  index  beta-hub  drifted_entry: summary was authored against a digest its members no longer produce
"""


def _render(project_dir: Path) -> Path:
    return project_dir / ".lore" / "index" / "codex.json"


def _entry(hub: str, slug: str, name: str) -> str:
    return (
        f"  {hub}:\n"
        f"    slug: {slug}\n"
        f"    name: {name}\n"
        f"    summary: Everything {slug}.\n"
        f"    authored_against: \"{'0' * 64}\"\n"
    )


def test_health_reports_unauthored_and_drifted(w1_project, runner):
    """W8 — warnings never raise the exit code, and the order is the table's."""
    res = runner.invoke(main, ["health", "--scope", "index"])

    assert res.exit_code == 0, res.output
    assert res.stdout == W8_WARNINGS


def test_health_errors_on_an_unresolvable_hub(index_project, runner, write_authored):
    """W8 — an entry whose hub is no document in this codex is an error."""
    write_authored(index_project, _entry("no-such-doc", "ghost-theme", "Ghost Theme"))

    res = runner.invoke(main, ["health", "--scope", "index"])

    assert res.exit_code == 1, res.output
    assert "ERROR  index  no-such-doc  unresolvable_hub:" in res.stdout


def test_health_warns_on_a_stale_entry(index_project, runner, write_authored):
    """W8 — `alpha-a` is a real document that heads no cluster."""
    write_authored(index_project, _entry("alpha-a", "stale-theme", "Stale Theme"))

    res = runner.invoke(main, ["health", "--scope", "index"])

    assert res.exit_code == 0, res.output
    assert "WARNING  index  alpha-a  stale_entry:" in res.stdout


def test_health_warns_on_a_duplicate_slug(index_project, runner, write_authored):
    """E1 — a collision makes the index ambiguous; it breaks nothing, so exit 0."""
    write_authored(
        index_project,
        _entry("alpha-hub", "alpha-theme", "Alpha Theme")
        + _entry("beta-hub", "alpha-theme", "Alpha Theme Again"),
    )

    res = runner.invoke(main, ["health", "--scope", "index"])

    assert res.exit_code == 0, res.output
    assert "WARNING  index  .lore/index/authored.yaml  duplicate_slug:" in res.stdout


def test_health_is_silent_without_an_authored_file(index_project, runner):
    """W8 — a missing authored file is a valid state, the way a missing
    glossary.yaml is."""
    res = runner.invoke(main, ["health", "--scope", "index"])

    assert res.exit_code == 0, res.output
    assert res.stdout == "Health check passed. No issues found.\n"


def test_health_writes_no_render(w1_project, runner):
    """D20 / ADR-021 — a read-only audit produces no side effect."""
    _render(w1_project).unlink()

    res = runner.invoke(main, ["health", "--scope", "index"])

    assert res.exit_code == 0, res.output
    assert not _render(w1_project).exists()


def test_index_is_a_valid_scope_token(index_project, runner):
    """ADR-017 — adding a token to a closed `click.Choice` set is the additive
    case, so the scope is accepted rather than rejected at exit 2."""
    res = runner.invoke(main, ["health", "--scope", "index", "--json"])

    assert res.exit_code in (0, 1), res.output
    assert "Invalid scope:" not in (res.stderr or "")
    assert "issues" in json.loads(res.stdout)


def test_an_unknown_scope_token_is_still_refused(index_project, runner):
    """ADR-017 — the closed set stays closed; `index` joined it, nothing else.

    `'index'` quoted is the token Click lists as valid, and it is not a
    substring of the quoted `'indexes'` it refuses, so this fails on a tree
    where `index` is not yet a scope.
    """
    res = runner.invoke(main, ["health", "--scope", "indexes"])

    assert res.exit_code == 2, res.output
    assert "'indexes' is not one of" in res.stderr
    assert "'index'" in res.stderr
