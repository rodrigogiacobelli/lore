"""E2E tests for `lore health --scope voice`.

Spec: the `codex-voice` artifact (`lore artifact show codex-voice`) — its
"Enforcement" table names the five mechanical issue ids and the layers each is
skipped in; "Which Rules Apply Where" is the per-layer tense budget those skips
implement.

Covers the five checks (`voice_past_narration`, `voice_expiry_hedge`,
`voice_forward_promise`, `voice_dangling_deixis`, `voice_sales_register`), the
per-layer skips for `decisions/`, `transient/`, `sources/`, and `vision/`, the
warnings-only severity contract (exit stays 0 with rows present), the JSON
envelope, multi-scope dispatch (`--scope codex voice`), the regions that are
never read (frontmatter values other than `summary`, fenced code blocks), the
self-reference guard on the generated `transient/health-*.md` report, and the
tuned false-positive carve-outs.
"""

from __future__ import annotations

import json
from pathlib import Path

from lore.cli import main


# ---------------------------------------------------------------------------
# Fixture authoring helpers
# ---------------------------------------------------------------------------


def write_codex(
    project_dir: Path,
    doc_id: str,
    body: str,
    *,
    layer: str = "",
    summary: str = "summary text",
) -> Path:
    """Write a codex doc under `.lore/codex/<layer>/<doc_id>.md`.

    `layer=""` writes to the codex root — a canonical doc, where every voice
    check applies.
    """
    text = (
        "---\n"
        f"id: {doc_id}\n"
        f"title: {doc_id}\n"
        f"summary: {summary}\n"
        "---\n"
        f"{body}\n"
    )
    d = project_dir / ".lore" / "codex"
    if layer:
        d = d / layer
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{doc_id}.md"
    path.write_text(text, encoding="utf-8")
    return path


def voice_checks(result) -> set[str]:
    """Return the set of `voice_*` issue ids present in human-readable output."""
    return {
        token.rstrip(":")
        for line in result.stdout.splitlines()
        for token in line.split()
        if token.startswith("voice_")
    }


def voice_rows(result) -> list[dict]:
    """Return the `voice_*` rows from a `--json health` result."""
    return [
        issue
        for issue in json.loads(result.stdout)["issues"]
        if issue["check"].startswith("voice_")
    ]


CONTROL_ID = "tech-control"


def seed_control(project_dir: Path) -> None:
    """Write a canonical doc that must always fire.

    Every "this does not fire" assertion pairs with the control so it cannot
    pass vacuously — an empty result set would otherwise prove nothing about
    whether the scope ran at all.
    """
    write_codex(project_dir, CONTROL_ID, "The resolver is robust.")


# ---------------------------------------------------------------------------
# Canonical fixture bodies
# ---------------------------------------------------------------------------

# One line per rule, so a per-check assertion is unambiguous about its source.
ALL_FIVE_VIOLATIONS = "\n".join([
    "The parser previously read each file twice.",
    "The flag currently accepts one token.",
    "Validation will be added in a later release.",
    "As mentioned above, the new flag takes a token.",
    "The resolver is robust and simply works.",
])

ALL_FIVE_IDS = {
    "voice_past_narration",
    "voice_expiry_hedge",
    "voice_forward_promise",
    "voice_dangling_deixis",
    "voice_sales_register",
}


# ---------------------------------------------------------------------------
# Scenario 1: Each of the five checks fires on a canonical doc
# ---------------------------------------------------------------------------


def test_voice_scope_accepted_on_clean_project(project_dir, runner):
    """`--scope voice` is a valid token: a freshly initialised project is clean."""
    r = runner.invoke(main, ["health", "--scope", "voice"])
    assert r.exit_code == 0, r.output
    assert r.stdout == "Health check passed. No issues found.\n"


def test_voice_all_five_checks_fire(project_dir, runner):
    """A canonical doc carrying all five violations produces all five issue ids."""
    write_codex(project_dir, "tech-parser", ALL_FIVE_VIOLATIONS)
    r = runner.invoke(main, ["health", "--scope", "voice"])
    assert voice_checks(r) == ALL_FIVE_IDS, r.stdout


def test_voice_past_narration_detail_names_line_and_phrase(project_dir, runner):
    """A `voice_past_narration` row quotes the offending phrase and its line."""
    write_codex(project_dir, "tech-parser", "The parser previously read each file twice.")
    r = runner.invoke(main, ["health", "--scope", "voice"])
    assert (
        'voice_past_narration: line 6: "previously" — past-tense change narration (V1, V2)'
        in r.stdout
    ), r.stdout


def test_voice_expiry_hedge_fires(project_dir, runner):
    """"currently" in a canonical doc is an expiry hedge (V3)."""
    write_codex(project_dir, "tech-flags", "The flag currently accepts one token.")
    r = runner.invoke(main, ["health", "--scope", "voice"])
    assert voice_checks(r) == {"voice_expiry_hedge"}, r.stdout


def test_voice_forward_promise_fires(project_dir, runner):
    """"will be added" in a canonical doc promises future work (V4)."""
    write_codex(project_dir, "tech-flags", "Validation will be added in a later release.")
    r = runner.invoke(main, ["health", "--scope", "voice"])
    assert voice_checks(r) == {"voice_forward_promise"}, r.stdout


def test_voice_dangling_deixis_fires(project_dir, runner):
    """"as mentioned above" points outside the document (V5)."""
    write_codex(project_dir, "tech-flags", "As mentioned above, the token is required.")
    r = runner.invoke(main, ["health", "--scope", "voice"])
    assert voice_checks(r) == {"voice_dangling_deixis"}, r.stdout


def test_voice_sales_register_fires(project_dir, runner):
    """"robust" and "simply" are sales register (V9)."""
    write_codex(project_dir, "tech-flags", "The resolver is robust and simply works.")
    r = runner.invoke(main, ["health", "--scope", "voice"])
    assert voice_checks(r) == {"voice_sales_register"}, r.stdout


def test_voice_reads_the_summary_frontmatter_value(project_dir, runner):
    """`summary` is prose and is linted; the rest of the frontmatter is not."""
    write_codex(project_dir, "tech-flags", "Body with no violation.", summary="A robust parser.")
    r = runner.invoke(main, ["health", "--scope", "voice"])
    assert voice_checks(r) == {"voice_sales_register"}, r.stdout
    assert 'line 4: "robust"' in r.stdout, r.stdout


# ---------------------------------------------------------------------------
# Scenario 2: Per-layer skips
# ---------------------------------------------------------------------------


def test_voice_decisions_layer_skips_past_narration_only(project_dir, runner):
    """`decisions/` may narrate prior state (V1, V2 off); V3, V4, V5, V9 still apply."""
    write_codex(project_dir, "decisions-001-x", ALL_FIVE_VIOLATIONS, layer="decisions")
    r = runner.invoke(main, ["health", "--scope", "voice"])
    assert voice_checks(r) == ALL_FIVE_IDS - {"voice_past_narration"}, r.stdout


def test_voice_transient_layer_skips_v1_to_v4(project_dir, runner):
    """`transient/` is in-flight work: V1-V4 off; V5 and V9 still apply."""
    write_codex(project_dir, "prd-thing", ALL_FIVE_VIOLATIONS, layer="transient")
    r = runner.invoke(main, ["health", "--scope", "voice"])
    assert voice_checks(r) == {
        "voice_dangling_deixis",
        "voice_sales_register",
    }, r.stdout


def test_voice_sources_layer_is_never_linted(project_dir, runner):
    """`sources/` bodies are verbatim upstream text: no voice rule applies."""
    write_codex(project_dir, "src-ticket", ALL_FIVE_VIOLATIONS, layer="sources")
    seed_control(project_dir)
    res = runner.invoke(main, ["--json", "health", "--scope", "voice"])
    assert {i["id"] for i in voice_rows(res)} == {CONTROL_ID}
    assert res.exit_code == 0, res.output


def test_voice_vision_layer_is_never_linted(project_dir, runner):
    """`vision/` is deferred until the rule is settled — the scope skips it."""
    write_codex(project_dir, "vision-thing", ALL_FIVE_VIOLATIONS, layer="vision")
    seed_control(project_dir)
    res = runner.invoke(main, ["--json", "health", "--scope", "voice"])
    assert {i["id"] for i in voice_rows(res)} == {CONTROL_ID}
    assert res.exit_code == 0, res.output


def test_voice_nested_layer_subdirectory_still_skips(project_dir, runner):
    """The skip keys off the top-level layer, so `sources/jira/x.md` is skipped too."""
    write_codex(project_dir, "src-nested", ALL_FIVE_VIOLATIONS, layer="sources/jira")
    seed_control(project_dir)
    res = runner.invoke(main, ["--json", "health", "--scope", "voice"])
    assert {i["id"] for i in voice_rows(res)} == {CONTROL_ID}


def test_voice_nested_canonical_subdirectory_is_linted(project_dir, runner):
    """A canonical doc nested under `conceptual/entities/` gets the full rule set."""
    write_codex(project_dir, "conceptual-entities-x", ALL_FIVE_VIOLATIONS, layer="conceptual/entities")
    r = runner.invoke(main, ["health", "--scope", "voice"])
    assert voice_checks(r) == ALL_FIVE_IDS, r.stdout


# ---------------------------------------------------------------------------
# Scenario 3: Warnings only — severity and exit code
# ---------------------------------------------------------------------------


def test_voice_rows_are_always_warnings(project_dir, runner):
    """Every voice row is a WARNING; the scope emits no ERROR row."""
    write_codex(project_dir, "tech-parser", ALL_FIVE_VIOLATIONS)
    r = runner.invoke(main, ["health", "--scope", "voice"])
    voice_lines = [ln for ln in r.stdout.splitlines() if "voice_" in ln]
    assert voice_lines, r.stdout
    assert all(ln.startswith("WARNING") for ln in voice_lines), r.stdout
    assert "ERROR" not in r.stdout, r.stdout


def test_voice_exit_code_stays_zero_with_warnings_present(project_dir, runner):
    """Voice never escalates: exit stays 0 even with rows on the report."""
    write_codex(project_dir, "tech-parser", ALL_FIVE_VIOLATIONS)
    r = runner.invoke(main, ["health", "--scope", "voice"])
    assert "voice_past_narration" in r.stdout, r.stdout
    assert r.exit_code == 0, r.output


def test_voice_does_not_flip_exit_code_on_a_full_audit(project_dir, runner):
    """A default (all-scope) run with voice warnings and no errors still exits 0."""
    write_codex(project_dir, "tech-parser", ALL_FIVE_VIOLATIONS)
    r = runner.invoke(main, ["health"])
    assert "voice_sales_register" in r.stdout, r.stdout
    assert r.exit_code == 0, r.output


# ---------------------------------------------------------------------------
# Scenario 4: JSON envelope
# ---------------------------------------------------------------------------


def test_voice_json_envelope(project_dir, runner):
    """JSON rows carry entity_type `codex`, the doc id, and null schema fields."""
    write_codex(project_dir, "tech-parser", "The resolver is robust and simply works.")
    res = runner.invoke(main, ["--json", "health", "--scope", "voice"])
    out = json.loads(res.stdout)
    assert out["has_errors"] is False
    assert {
        "severity": "warning",
        "entity_type": "codex",
        "id": "tech-parser",
        "check": "voice_sales_register",
        "detail": 'line 6: "robust" — sales register (V9)',
        "schema_id": None,
        "rule": None,
        "pointer": None,
    } in out["issues"]
    assert res.exit_code == 0, res.output


def test_voice_json_rows_all_have_warning_severity(project_dir, runner):
    """No JSON voice row carries severity `error`."""
    write_codex(project_dir, "tech-parser", ALL_FIVE_VIOLATIONS)
    res = runner.invoke(main, ["--json", "health", "--scope", "voice"])
    rows = [i for i in json.loads(res.stdout)["issues"] if i["check"].startswith("voice_")]
    assert rows
    assert {i["severity"] for i in rows} == {"warning"}


# ---------------------------------------------------------------------------
# Scenario 5: Scope isolation and multi-scope dispatch
# ---------------------------------------------------------------------------


def test_voice_scope_alone_does_not_run_codex_checks(project_dir, runner):
    """`--scope voice` runs no codex reference-integrity check."""
    write_codex(project_dir, "tech-parser", "The resolver is robust.")
    (project_dir / ".lore" / "codex" / "tech-broken.md").write_text(
        "---\nid: tech-broken\ntitle: t\nsummary: s\nrelated:\n  - nonexistent\n---\nBody.\n",
        encoding="utf-8",
    )
    r = runner.invoke(main, ["health", "--scope", "voice"])
    assert "voice_sales_register" in r.stdout, r.stdout
    assert "broken_related_link" not in r.stdout, r.stdout
    assert "island_node" not in r.stdout, r.stdout


def test_voice_scope_multi_runs_both(project_dir, runner):
    """`--scope codex voice` dispatches both checkers."""
    write_codex(project_dir, "tech-parser", "The resolver is robust.")
    (project_dir / ".lore" / "codex" / "tech-broken.md").write_text(
        "---\nid: tech-broken\ntitle: t\nsummary: s\nrelated:\n  - nonexistent\n---\nBody.\n",
        encoding="utf-8",
    )
    r = runner.invoke(main, ["health", "--scope", "codex", "voice"])
    assert "voice_sales_register" in r.stdout, r.stdout
    assert "broken_related_link" in r.stdout, r.stdout
    assert r.exit_code == 1, r.output  # the codex error owns the exit code


def test_voice_unknown_scope_still_rejected_by_click_choice(project_dir, runner):
    """ADR-017 holds: an out-of-set token is a usage error (exit 2), now listing `voice`."""
    r = runner.invoke(main, ["health", "--scope", "xyz"])
    assert r.exit_code == 2, r.output
    assert "'xyz' is not one of" in r.stderr
    assert "'voice'" in r.stderr


# ---------------------------------------------------------------------------
# Scenario 6: Regions the linter never reads
# ---------------------------------------------------------------------------


def test_voice_skips_fenced_code_blocks(project_dir, runner):
    """Prose inside a fenced block is code, not voice."""
    write_codex(
        project_dir,
        "tech-parser",
        "Run the command.\n\n```python\n# the parser previously read each file twice\nx = 1  # simply\n```\n\nDone.",
    )
    seed_control(project_dir)
    res = runner.invoke(main, ["--json", "health", "--scope", "voice"])
    assert {i["id"] for i in voice_rows(res)} == {CONTROL_ID}


def test_voice_skips_tilde_fenced_code_blocks(project_dir, runner):
    """Tilde fences are code fences too."""
    write_codex(project_dir, "tech-parser", "Intro.\n\n~~~\ncurrently robust\n~~~\n")
    seed_control(project_dir)
    res = runner.invoke(main, ["--json", "health", "--scope", "voice"])
    assert {i["id"] for i in voice_rows(res)} == {CONTROL_ID}


def test_voice_resumes_after_a_closed_fence(project_dir, runner):
    """A violation after the closing fence still fires — the fence is not sticky."""
    write_codex(project_dir, "tech-parser", "Intro.\n\n```\ncurrently\n```\n\nThe flag is robust.")
    r = runner.invoke(main, ["health", "--scope", "voice"])
    assert voice_checks(r) == {"voice_sales_register"}, r.stdout
    assert 'line 12: "robust"' in r.stdout, r.stdout


def test_voice_skips_inline_code_spans(project_dir, runner):
    """A flagged word inside backticks is an identifier, not prose."""
    write_codex(project_dir, "tech-parser", "The `simply_parse` helper and the `robust` flag.")
    seed_control(project_dir)
    res = runner.invoke(main, ["--json", "health", "--scope", "voice"])
    assert {i["id"] for i in voice_rows(res)} == {CONTROL_ID}


def test_voice_skips_frontmatter_values_other_than_summary(project_dir, runner):
    """`title` and other frontmatter keys are metadata, not prose."""
    path = project_dir / ".lore" / "codex" / "tech-parser.md"
    path.write_text(
        "---\n"
        "id: tech-parser\n"
        "title: The robust parser that simply works\n"
        "summary: A parser.\n"
        "---\n"
        "Body with no violation.\n",
        encoding="utf-8",
    )
    seed_control(project_dir)
    res = runner.invoke(main, ["--json", "health", "--scope", "voice"])
    assert {i["id"] for i in voice_rows(res)} == {CONTROL_ID}


def test_voice_reads_a_block_scalar_summary(project_dir, runner):
    """A folded-block `summary` is prose across its continuation lines."""
    path = project_dir / ".lore" / "codex" / "tech-parser.md"
    path.write_text(
        "---\n"
        "id: tech-parser\n"
        "title: t\n"
        "summary: >\n"
        "  The parser is robust.\n"
        "related: []\n"
        "---\n"
        "Body with no violation.\n",
        encoding="utf-8",
    )
    r = runner.invoke(main, ["health", "--scope", "voice"])
    assert voice_checks(r) == {"voice_sales_register"}, r.stdout
    assert 'line 5: "robust"' in r.stdout, r.stdout


# ---------------------------------------------------------------------------
# Scenario 7: The linter never fires on its own generated report
# ---------------------------------------------------------------------------


def test_voice_ignores_its_own_generated_health_report(project_dir, runner):
    """`transient/health-*.md` quotes violations verbatim; that is not a violation.

    `transient/` is exempt from V1-V4 but NOT from V5 or V9, so a report whose
    table quotes "simply" or "the new flag" would otherwise flag itself on the
    next run — and every run would add one more self-referential row.
    """
    write_codex(project_dir, "tech-parser", ALL_FIVE_VIOLATIONS)

    first = runner.invoke(main, ["health", "--scope", "voice"])
    assert "voice_sales_register" in first.stdout, first.stdout
    reports = sorted((project_dir / ".lore" / "codex" / "transient").glob("health-*.md"))
    assert reports, "health run must have written a report"
    assert "simply" in reports[-1].read_text(encoding="utf-8")

    second = runner.invoke(main, ["--json", "health", "--scope", "voice"])
    ids = {i["id"] for i in json.loads(second.stdout)["issues"]}
    assert not any(i.startswith("health-") for i in ids), sorted(ids)
    assert ids == {"tech-parser"}, sorted(ids)


def test_voice_still_lints_non_report_transient_docs(project_dir, runner):
    """The report carve-out is scoped to `health-*.md`, not to `transient/`."""
    write_codex(project_dir, "prd-thing", "The resolver is robust.", layer="transient")
    r = runner.invoke(main, ["health", "--scope", "voice"])
    assert "voice_sales_register" in r.stdout, r.stdout
    assert "prd-thing" in r.stdout, r.stdout


# ---------------------------------------------------------------------------
# Scenario 8: Tuned false-positive carve-outs
# ---------------------------------------------------------------------------


def test_voice_no_longer_describing_present_state_does_not_fire(project_dir, runner):
    """"no longer visible" states a fact about today — not change narration."""
    write_codex(project_dir, "tech-tree", "A collapsed node leaves the parent no longer visible.")
    seed_control(project_dir)
    res = runner.invoke(main, ["--json", "health", "--scope", "voice"])
    assert {i["id"] for i in voice_rows(res)} == {CONTROL_ID}


def test_voice_no_longer_exists_fires_in_a_main_clause(project_dir, runner):
    """"The `bootstrap/` subdirectory no longer exists" is changelog content."""
    write_codex(project_dir, "tech-layout", "The bootstrap subdirectory no longer exists.")
    r = runner.invoke(main, ["health", "--scope", "voice"])
    assert voice_checks(r) == {"voice_past_narration"}, r.stdout


def test_voice_no_longer_exists_in_a_conditional_does_not_fire(project_dir, runner):
    """"if the Knight file no longer exists" states a present condition."""
    write_codex(
        project_dir,
        "tech-show",
        "If a Mission references a Knight that no longer exists on disk, the CLI warns.",
    )
    seed_control(project_dir)
    res = runner.invoke(main, ["--json", "health", "--scope", "voice"])
    assert {i["id"] for i in voice_rows(res)} == {CONTROL_ID}


def test_voice_being_planned_does_not_fire(project_dir, runner):
    """"work being planned" names a kind of content, not a promise."""
    write_codex(project_dir, "tech-layers", "The in-flight layer holds work being planned or developed.")
    seed_control(project_dir)
    res = runner.invoke(main, ["--json", "health", "--scope", "voice"])
    assert {i["id"] for i in voice_rows(res)} == {CONTROL_ID}


def test_voice_planned_as_a_promise_does_fire(project_dir, runner):
    """A bare "planned" predicate is still a future-work promise."""
    write_codex(project_dir, "tech-roadmap", "Soft-delete is planned for the two-file model.")
    r = runner.invoke(main, ["health", "--scope", "voice"])
    assert voice_checks(r) == {"voice_forward_promise"}, r.stdout


def test_voice_the_new_procedural_referent_does_not_fire(project_dir, runner):
    """"the new value"/"the new file" resolve inside the sentence."""
    write_codex(
        project_dir,
        "tech-migrations",
        "Bump SCHEMA_VERSION, update the INSERT line to the new value, then write the new file.",
    )
    seed_control(project_dir)
    res = runner.invoke(main, ["--json", "health", "--scope", "voice"])
    assert {i["id"] for i in voice_rows(res)} == {CONTROL_ID}


def test_voice_the_new_flag_does_fire(project_dir, runner):
    """"the new flag" names a system element the reader cannot resolve."""
    write_codex(project_dir, "tech-cli", "Pass the new flag to limit the audit.")
    r = runner.invoke(main, ["health", "--scope", "voice"])
    assert voice_checks(r) == {"voice_dangling_deixis"}, r.stdout


def test_voice_temporal_just_does_not_fire(project_dir, runner):
    """"just as"/"just before"/"just-in-time" are temporal, not sales register."""
    write_codex(
        project_dir,
        "tech-timing",
        "The cache warms just before the first read, just as the pool opens, just-in-time.",
    )
    seed_control(project_dir)
    res = runner.invoke(main, ["--json", "health", "--scope", "voice"])
    assert {i["id"] for i in voice_rows(res)} == {CONTROL_ID}


def test_voice_minimising_just_does_fire(project_dir, runner):
    """"is just one kind of" is the minimising sales register the rule names."""
    write_codex(project_dir, "tech-notes", "An Artifact ID is just one kind of content.")
    r = runner.invoke(main, ["health", "--scope", "voice"])
    assert voice_checks(r) == {"voice_sales_register"}, r.stdout


def test_voice_conditional_past_passive_does_not_fire(project_dir, runner):
    """A conditional perfect passive ("after its facts have been folded") is process, not history."""
    write_codex(
        project_dir,
        "tech-transient",
        "Safe to delete after the feature ships and its facts have been folded into stable docs.",
    )
    seed_control(project_dir)
    res = runner.invoke(main, ["--json", "health", "--scope", "voice"])
    assert {i["id"] for i in voice_rows(res)} == {CONTROL_ID}


def test_voice_renamed_perfect_passive_does_fire(project_dir, runner):
    """"has been renamed" is the change narration the rule names."""
    write_codex(project_dir, "tech-fields", "The board field has been renamed.")
    r = runner.invoke(main, ["health", "--scope", "voice"])
    assert voice_checks(r) == {"voice_past_narration"}, r.stdout
