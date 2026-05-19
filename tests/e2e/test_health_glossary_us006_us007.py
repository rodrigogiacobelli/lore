"""E2E tests for US-006 + US-007 (group G4).

US-006: `lore health --scope glossary` stops emitting
`glossary_deprecated_term` rows; families 1 (schema) + 2 (collisions)
still fire; envelope shape unchanged.

US-007: `from lore.glossary import find_deprecated_terms` raises
ImportError; auto-surface still highlights glossary terms.

Spec: lore codex show health-bindings-glossary-us-006 health-bindings-glossary-us-007
PRD: health-bindings-glossary-prd (FR-19, FR-20, FR-21, FR-22, FR-23, FR-24)
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from lore.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_glossary(project_dir: Path, content: str) -> Path:
    target = project_dir / ".lore" / "codex" / "glossary.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def _seed_codex_doc(project_dir: Path, doc_id: str, *, body: str = "") -> Path:
    """Write a codex doc at `.lore/codex/<doc_id>.md` with frontmatter + body."""
    fm_body = textwrap.dedent(
        f"""\
        ---
        id: {doc_id}
        title: {doc_id}
        summary: summary for {doc_id}
        ---
        {body}
        """
    )
    codex_dir = project_dir / ".lore" / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    path = codex_dir / f"{doc_id}.md"
    path.write_text(fm_body, encoding="utf-8")
    return path


# ===========================================================================
# US-006 — Observable behaviour: zero glossary_deprecated_term rows
# ===========================================================================


def test_no_deprecated_term_rows_when_prose_mentions_seeded(project_dir, runner):
    """US-006 E2E Scenario 1 — FR-22.

    Three codex docs each contain the `do_not_use` phrase in body prose.
    `lore health --scope glossary --json` returns zero
    `glossary_deprecated_term` rows.
    """
    _write_glossary(
        project_dir,
        "items:\n"
        "  - keyword: Mission\n"
        "    definition: Unit of work.\n"
        "    do_not_use: [mission step]\n",
    )
    for doc_id in ("doc-a", "doc-b", "doc-c"):
        _seed_codex_doc(
            project_dir, doc_id, body="The mission step framing is deprecated."
        )
    res = runner.invoke(main, ["--json", "health", "--scope", "glossary"])
    payload = json.loads(res.stdout)
    assert [
        i for i in payload["issues"] if i["check"] == "glossary_deprecated_term"
    ] == []


def test_do_not_use_collision_still_fires(project_dir, runner):
    """US-006 E2E Scenario 2 — FR-21.

    Two items both list `do_not_use: ["foobar"]` — `do_not_use_collision`
    (family 2) still fires with exit code 1.
    """
    _write_glossary(
        project_dir,
        "items:\n"
        "  - keyword: Foo\n"
        "    definition: f\n"
        "    do_not_use: [foobar]\n"
        "  - keyword: Bar\n"
        "    definition: b\n"
        "    do_not_use: [foobar]\n",
    )
    res = runner.invoke(main, ["--json", "health", "--scope", "glossary"])
    assert res.exit_code == 1, res.output
    payload = json.loads(res.stdout)
    collisions = [i for i in payload["issues"] if i["check"] == "do_not_use_collision"]
    assert len(collisions) >= 1
    assert all(i["severity"] == "error" for i in collisions)


def test_schema_validation_still_fires_on_bad_do_not_use(project_dir, runner):
    """US-006 E2E Scenario 3 — FR-24 regression guard + family-3 absence.

    A malformed `do_not_use` (non-list scalar) is rejected by the glossary
    schema under `--scope schemas` (exit code 1, glossary schema error).
    Paired forward-looking assertion: an unscoped run with prose that
    would otherwise trip family 3 surfaces zero `glossary_deprecated_term`
    rows — the family-3 removal is observable on this fixture.
    """
    _write_glossary(
        project_dir,
        textwrap.dedent(
            """\
            items:
              - keyword: Foo
                definition: f
                do_not_use: not-a-list
            """
        ),
    )
    res = runner.invoke(main, ["--json", "health", "--scope", "schemas"])
    assert res.exit_code == 1, res.output
    payload = json.loads(res.stdout)
    schema_errs = [i for i in payload["issues"] if i["entity_type"] == "glossary"]
    assert len(schema_errs) >= 1

    # Forward-looking pairing: rewrite the glossary with a valid do_not_use
    # plus prose that family 3 would have matched. Post-Green this MUST
    # produce zero glossary_deprecated_term rows.
    _write_glossary(
        project_dir,
        "items:\n"
        "  - keyword: Mission\n"
        "    definition: Unit of work.\n"
        "    do_not_use: [mission step]\n",
    )
    _seed_codex_doc(
        project_dir, "doc-a", body="The mission step framing is deprecated."
    )
    res2 = runner.invoke(main, ["--json", "health", "--scope", "glossary"])
    payload2 = json.loads(res2.stdout)
    assert [
        i for i in payload2["issues"] if i["check"] == "glossary_deprecated_term"
    ] == []


def test_default_scope_zero_deprecated_term_rows(project_dir, runner):
    """US-006 E2E Scenario 5 — FR-22.

    Default-all-scopes run (`lore health --json` with no `--scope`)
    produces zero `glossary_deprecated_term` rows even when a `do_not_use`
    term appears in codex prose — proving family 3 is gone, not merely
    quiet because no docs trip it.
    """
    _write_glossary(
        project_dir,
        "items:\n"
        "  - keyword: Mission\n"
        "    definition: Unit of work.\n"
        "    do_not_use: [mission step]\n",
    )
    _seed_codex_doc(
        project_dir, "doc-a", body="The mission step framing is deprecated."
    )
    res = runner.invoke(main, ["--json", "health"])
    payload = json.loads(res.stdout)
    assert [
        i for i in payload["issues"] if i["check"] == "glossary_deprecated_term"
    ] == []


def test_glossary_scope_envelope_keys_unchanged(project_dir, runner):
    """US-006 E2E Scenario 6 — FR-21, FR-26.

    Envelope shape unchanged: `issues` and `has_errors` keys present;
    no `glossary_deprecated_term` rows in `issues` even when a codex doc
    contains prose that would have surfaced one pre-feature.
    """
    _write_glossary(
        project_dir,
        "items:\n"
        "  - keyword: Foo\n"
        "    definition: f\n"
        "    do_not_use: [foobar]\n"
        "  - keyword: Bar\n"
        "    definition: b\n"
        "    do_not_use: [foobar]\n",
    )
    # Seed prose that the family-3 scan would match today — proves the
    # absence of `glossary_deprecated_term` rows is the removal, not
    # vacuous "no mentions".
    _seed_codex_doc(project_dir, "doc-a", body="The foobar pattern is deprecated.")
    res = runner.invoke(main, ["--json", "health", "--scope", "glossary"])
    payload = json.loads(res.stdout)
    assert "issues" in payload
    assert "has_errors" in payload
    assert all(i["check"] != "glossary_deprecated_term" for i in payload["issues"])


# ===========================================================================
# US-007 — Code-surface deletions exposed through E2E
# ===========================================================================


def test_find_deprecated_terms_not_importable_e2e():
    """US-007 E2E Scenario 1 — `from lore.glossary import find_deprecated_terms`
    raises ImportError; attribute lookup also fails.
    """
    import lore.glossary

    assert not hasattr(lore.glossary, "find_deprecated_terms")
    with pytest.raises(ImportError):
        from lore.glossary import find_deprecated_terms  # noqa: F401


def test_auto_surface_still_highlights_glossary_terms(project_dir, runner):
    """US-007 E2E Scenario 2 — FR-23 auto-surface regression guard.

    A codex doc whose body contains the keyword "mission" still surfaces
    the glossary term "Mission" when rendered through `lore codex show`.
    The shared tokeniser is intact. Paired with a forward-looking
    assertion that `find_deprecated_terms` is no longer importable
    from `lore.glossary` — keeps this test Red until US-007 ships.
    """
    _write_glossary(
        project_dir,
        "items:\n"
        "  - keyword: Mission\n"
        "    definition: A unit of executable work.\n",
    )
    _seed_codex_doc(project_dir, "doc-a", body="Discuss the mission lifecycle.")
    res = runner.invoke(main, ["codex", "show", "doc-a"])
    assert res.exit_code == 0, res.output
    # Auto-surface contract: "Mission" rendered in the glossary block.
    assert "Mission" in res.output

    # Forward-looking pair — find_deprecated_terms is gone from lore.glossary.
    import lore.glossary

    assert not hasattr(lore.glossary, "find_deprecated_terms")


def test_lore_health_source_no_family_three():
    """US-007 E2E Scenario 5 — FR-20.

    `lore.health` source code contains zero references to the deleted
    family-3 surface (the function, the two private helpers, the string
    literal check name).
    """
    import inspect

    import lore.health

    src = inspect.getsource(lore.health)
    for symbol in (
        "find_deprecated_terms",
        "_glossary_deprecated_term_issues",
        "_read_codex_bodies",
        '"glossary_deprecated_term"',
    ):
        assert symbol not in src, f"orphan health.py reference: {symbol}"
