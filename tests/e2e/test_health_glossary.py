"""E2E tests for `lore health --scope glossary` and the glossary schema/scan integration.

Spec: conceptual-workflows-health (lore codex show conceptual-workflows-health)
Workflow: conceptual-workflows-glossary (lore codex show conceptual-workflows-glossary)

Covers all 11 E2E scenarios for health audits over the glossary: schema
validation, intra-glossary collision checks, the cross-codex deprecated-term
scan, and the `--scope glossary` token semantics. Production code does not
exist yet — every test MUST fail (import errors / behaviour mismatches both
count as red).
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from lore.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_glossary(project_dir: Path, content: str) -> Path:
    target = project_dir / ".lore" / "codex" / "glossary.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def _seed_codex_doc(
    project_dir: Path,
    doc_id: str,
    *,
    body: str = "",
    related: list[str] | None = None,
) -> Path:
    """Write a codex document at .lore/codex/<doc_id>.md with frontmatter + body."""
    related_block = ""
    if related is not None:
        if related:
            items = "\n".join(f"  - {r}" for r in related)
            related_block = f"related:\n{items}\n"
        else:
            related_block = "related: []\n"
    fm_body = textwrap.dedent(
        f"""\
        ---
        id: {doc_id}
        title: {doc_id}
        summary: summary for {doc_id}
        {related_block}---
        {body}
        """
    )
    codex_dir = project_dir / ".lore" / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    path = codex_dir / f"{doc_id}.md"
    path.write_text(fm_body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Scenario 1: Clean glossary — `lore health --scope glossary` exit 0
# ---------------------------------------------------------------------------


def test_clean_glossary_health_passes(project_dir, runner):
    """Scenario 1 — clean glossary: text mode prints success + 0 schema errors."""
    _write_glossary(
        project_dir,
        "items:\n"
        "  - keyword: Knight\n"
        "    definition: A reusable agent persona attached to missions.\n",
    )
    res = runner.invoke(main, ["health", "--scope", "glossary"])
    assert res.exit_code == 0, res.output
    assert "Health check passed. No issues found." in res.output
    assert "Schema validation: 0 errors" in res.output


def test_clean_glossary_health_passes_json(project_dir, runner):
    """Scenario 1 — clean glossary in JSON mode: exact envelope."""
    _write_glossary(
        project_dir,
        "items:\n  - keyword: Knight\n    definition: A reusable agent persona.\n",
    )
    res = runner.invoke(main, ["--json", "health", "--scope", "glossary"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.stdout)
    assert payload == {"has_errors": False, "issues": []}


# ---------------------------------------------------------------------------
# Scenario 2: Schema violation — exits 1, intra-glossary checks short-circuited
# ---------------------------------------------------------------------------


def test_schema_violation_short_circuits_intra_checks_json(project_dir, runner):
    """Scenario 2 — schema violation emits one schema error and suppresses other checks."""
    _write_glossary(project_dir, "items:\n  - keyword: Mission\n")
    res = runner.invoke(main, ["--json", "health", "--scope", "glossary"])
    assert res.exit_code == 1, res.output
    payload = json.loads(res.stdout)
    assert payload["has_errors"] is True
    schema_issues = [i for i in payload["issues"] if i["check"] == "schema"]
    assert len(schema_issues) == 1
    issue = schema_issues[0]
    assert issue["severity"] == "error"
    assert issue["entity_type"] == "glossary"
    assert issue["id"] == ".lore/codex/glossary.yaml"
    assert issue["schema_id"] == "lore://schemas/glossary"
    assert issue["rule"] == "required"
    for forbidden in (
        "duplicate_keyword",
        "alias_keyword_collision",
        "do_not_use_collision",
        "glossary_deprecated_term",
    ):
        assert not any(i["check"] == forbidden for i in payload["issues"]), (
            f"forbidden check {forbidden!r} surfaced despite schema violation"
        )


# ---------------------------------------------------------------------------
# Scenario 3: Duplicate keyword — error
# ---------------------------------------------------------------------------


def test_duplicate_keyword_error_text(project_dir, runner):
    """Scenario 3 — duplicate keyword (casefolded) produces an ERROR row."""
    _write_glossary(
        project_dir,
        "items:\n"
        "  - keyword: Mission\n    definition: First definition.\n"
        "  - keyword: mission\n    definition: Second definition (same keyword, different case).\n",
    )
    res = runner.invoke(main, ["health", "--scope", "glossary"])
    assert res.exit_code == 1, res.output
    assert "ERROR" in res.output
    assert "glossary" in res.output
    assert ".lore/codex/glossary.yaml" in res.output
    assert "duplicate_keyword" in res.output
    assert "'mission' appears in items[0] and items[1]" in res.output


# ---------------------------------------------------------------------------
# Scenario 4: Alias colliding with another item's keyword — warning
# ---------------------------------------------------------------------------


def test_alias_keyword_collision_warning(project_dir, runner):
    """Scenario 4 — alias colliding with another keyword: WARNING row, exit 1."""
    _write_glossary(
        project_dir,
        "items:\n"
        "  - keyword: Quest\n    definition: A live grouping of Missions.\n    aliases: [Mission]\n"
        "  - keyword: Mission\n    definition: Unit of work.\n",
    )
    res = runner.invoke(main, ["health", "--scope", "glossary"])
    assert res.exit_code == 1, res.output
    assert "alias_keyword_collision" in res.output
    assert "alias 'mission' on 'Quest' collides with keyword 'Mission'" in res.output


# ---------------------------------------------------------------------------
# Scenario 5: `do_not_use` colliding with any keyword/alias — error
# ---------------------------------------------------------------------------


def test_do_not_use_collision_error(project_dir, runner):
    """Scenario 5 — do_not_use colliding with a keyword: ERROR row, exit 1."""
    _write_glossary(
        project_dir,
        "items:\n"
        "  - keyword: Knight\n    definition: A reusable agent persona.\n    do_not_use: [Mission]\n"
        "  - keyword: Mission\n    definition: Unit of work.\n",
    )
    res = runner.invoke(main, ["health", "--scope", "glossary"])
    assert res.exit_code == 1, res.output
    assert "do_not_use_collision" in res.output
    assert (
        "'mission' in do_not_use of 'Knight' collides with keyword/alias 'Mission'"
        in res.output
    )


# ---------------------------------------------------------------------------
# Scenario 6: Cross-codex deprecated-term scan — one warning per occurrence per doc
# ---------------------------------------------------------------------------


def test_cross_codex_deprecated_term_scan_json(project_dir, runner):
    """Scenario 6 — one warning per deprecated occurrence per doc, alphabetised."""
    _write_glossary(
        project_dir,
        "items:\n"
        "  - keyword: Knight\n    definition: A reusable agent persona.\n    do_not_use: [agent]\n"
        "  - keyword: Quest\n    definition: A live grouping of Missions.\n    do_not_use: [epic]\n",
    )
    _seed_codex_doc(project_dir, "doc-a", body="The agent retrieves the codex.")
    _seed_codex_doc(
        project_dir,
        "doc-b",
        body="An epic encompasses many features. Another agent collaborates here.",
    )
    res = runner.invoke(main, ["--json", "health", "--scope", "glossary"])
    assert res.exit_code == 1, res.output
    payload = json.loads(res.stdout)
    warns = [i for i in payload["issues"] if i["check"] == "glossary_deprecated_term"]
    assert len(warns) == 3
    assert all(
        i["severity"] == "warning" and i["entity_type"] == "codex" for i in warns
    )
    # Sorted by (id, matched_term) — alphabetical.
    assert (warns[0]["id"], warns[0]["detail"]) == (
        "doc-a",
        'document uses deprecated term "agent" — prefer "Knight"',
    )
    assert (warns[1]["id"], warns[1]["detail"]) == (
        "doc-b",
        'document uses deprecated term "agent" — prefer "Knight"',
    )
    assert (warns[2]["id"], warns[2]["detail"]) == (
        "doc-b",
        'document uses deprecated term "epic" — prefer "Quest"',
    )
    assert payload["has_errors"] is True


# ---------------------------------------------------------------------------
# Scenario 7: Combined scope `--scope codex glossary` runs both checker sets
# ---------------------------------------------------------------------------


def test_combined_scope_codex_glossary_runs_both_checkers(project_dir, runner):
    """Scenario 7 — multi-scope (ADR-012): codex scope and glossary scope both run."""
    _seed_codex_doc(
        project_dir, "doc-x", body="See related doc.", related=["nonexistent-doc"]
    )
    _write_glossary(
        project_dir,
        "items:\n"
        "  - keyword: Mission\n    definition: a.\n"
        "  - keyword: mission\n    definition: b.\n",
    )
    res = runner.invoke(main, ["health", "--scope", "codex", "glossary"])
    assert res.exit_code == 1, res.output
    assert "broken_related_link" in res.output
    assert "duplicate_keyword" in res.output


# ---------------------------------------------------------------------------
# Scenario 8: `--scope schemas` validates glossary schema even without `glossary` token
# ---------------------------------------------------------------------------


def test_scope_schemas_validates_glossary_without_glossary_token(project_dir, runner):
    """Scenario 8 — --scope schemas surfaces glossary schema errors on its own."""
    _write_glossary(project_dir, "items:\n  - keyword: Mission\n")
    res = runner.invoke(main, ["--json", "health", "--scope", "schemas"])
    assert res.exit_code == 1, res.output
    payload = json.loads(res.stdout)
    glossary_schema = [
        i
        for i in payload["issues"]
        if i["check"] == "schema" and i["entity_type"] == "glossary"
    ]
    assert len(glossary_schema) >= 1
    assert glossary_schema[0]["schema_id"] == "lore://schemas/glossary"


# ---------------------------------------------------------------------------
# Scenario 9: Unknown `--scope` token rejected with extended valid list
# ---------------------------------------------------------------------------


def test_unknown_scope_message_lists_glossary(project_dir, runner):
    """Scenario 9 — unknown scope: error message names `glossary` among valid tokens."""
    res = runner.invoke(main, ["health", "--scope", "nonsense"])
    err = res.stderr if res.stderr else res.output
    assert "glossary" in err
    assert res.exit_code != 0


# ---------------------------------------------------------------------------
# Scenario 10: Missing glossary file — `--scope glossary` clean run
# ---------------------------------------------------------------------------


def test_missing_glossary_clean_run(project_dir, runner):
    """Scenario 10 — no glossary.yaml: --scope glossary is a clean exit-0 run."""
    glossary = project_dir / ".lore" / "codex" / "glossary.yaml"
    if glossary.exists():
        glossary.unlink()
    res = runner.invoke(main, ["health", "--scope", "glossary"])
    assert res.exit_code == 0, res.output
    assert "Health check passed." in res.output


# ---------------------------------------------------------------------------
# Scenario 11: Tokeniser substring guard — deprecated-term scan does NOT match `missionary`
# ---------------------------------------------------------------------------


def test_tokeniser_substring_guard_no_warnings(project_dir, runner):
    """Scenario 11 — substring guard: `missionary` and `taskforce` do not trigger warnings."""
    _write_glossary(
        project_dir,
        "items:\n"
        "  - keyword: Mission\n    definition: u.\n    do_not_use: [task]\n",
    )
    _seed_codex_doc(
        project_dir,
        "doc-a",
        body="The taskforce reviewed the missionary work.",
    )
    res = runner.invoke(main, ["health", "--scope", "glossary"])
    assert res.exit_code == 0, res.output
    assert "glossary_deprecated_term" not in res.output
