"""Unit tests for `health._check_voice` and the `voice` scope routing.

Spec: the `codex-voice` artifact (`lore artifact show codex-voice`).

Calls `_check_voice(project_root)` directly against a hermetic `.lore/`
skeleton — no `lore init`, no seed content (ADR-006) — and pins the scope
dispatcher so `scope=["voice"]` runs the voice checker and nothing else.
"""

from __future__ import annotations

from pathlib import Path

from lore.health import _ALL_SCOPES, _check_voice, _voice_lintable_lines, health_check


# ---------------------------------------------------------------------------
# Fixture authoring helpers
# ---------------------------------------------------------------------------


def make_project(tmp_path: Path) -> Path:
    """Create a minimal `.lore/codex/` skeleton (no seed content)."""
    (tmp_path / ".lore" / "codex").mkdir(parents=True, exist_ok=True)
    return tmp_path


def write_codex(
    root: Path,
    doc_id: str,
    body: str,
    *,
    layer: str = "",
    summary: str = "summary text",
) -> Path:
    """Write a codex doc at `.lore/codex/<layer>/<doc_id>.md`."""
    d = root / ".lore" / "codex"
    if layer:
        d = d / layer
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{doc_id}.md"
    path.write_text(
        f"---\nid: {doc_id}\ntitle: {doc_id}\nsummary: {summary}\n---\n{body}\n",
        encoding="utf-8",
    )
    return path


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


def checks(issues) -> set[str]:
    return {i.check for i in issues}


# ---------------------------------------------------------------------------
# Scope vocabulary and routing
# ---------------------------------------------------------------------------


def test_voice_is_registered_in_all_scopes():
    """`voice` ships in the default-all scope set, appended after `rites`."""
    assert "voice" in _ALL_SCOPES
    assert _ALL_SCOPES[-1] == "voice"


def test_scope_voice_routes_to_check_voice_only(tmp_path):
    """`scope=["voice"]` runs the voice checker and no other checker.

    Seeds a doc that would fire `_check_codex` (broken related link) alongside
    one that fires `_check_voice`. Only the voice row may surface.
    """
    root = make_project(tmp_path)
    write_codex(root, "tech-parser", "The resolver is robust.")
    (root / ".lore" / "codex" / "tech-broken.md").write_text(
        "---\nid: tech-broken\ntitle: t\nsummary: s\nrelated:\n  - nonexistent\n---\nBody.\n",
        encoding="utf-8",
    )

    report = health_check(root, scope=["voice"])
    found = checks(report.issues)

    assert "voice_sales_register" in found
    assert "broken_related_link" not in found
    assert "island_node" not in found


def test_scope_voice_and_codex_routes_both(tmp_path):
    """`scope=["voice", "codex"]` runs both checkers."""
    root = make_project(tmp_path)
    write_codex(root, "tech-parser", "The resolver is robust.")
    (root / ".lore" / "codex" / "tech-broken.md").write_text(
        "---\nid: tech-broken\ntitle: t\nsummary: s\nrelated:\n  - nonexistent\n---\nBody.\n",
        encoding="utf-8",
    )

    found = checks(health_check(root, scope=["voice", "codex"]).issues)

    assert "voice_sales_register" in found
    assert "broken_related_link" in found


def test_scope_codex_alone_does_not_run_voice(tmp_path):
    """Voice rides on its own token — `scope=["codex"]` emits no voice row."""
    root = make_project(tmp_path)
    write_codex(root, "tech-parser", "The resolver is robust.")

    found = checks(health_check(root, scope=["codex"]).issues)

    assert not any(c.startswith("voice_") for c in found)


def test_voice_rows_land_in_warnings_never_errors(tmp_path):
    """No voice id is escalated: every row lands in `HealthReport.warnings`."""
    root = make_project(tmp_path)
    write_codex(root, "tech-parser", ALL_FIVE_VIOLATIONS)

    report = health_check(root, scope=["voice"])

    assert checks(report.warnings) == ALL_FIVE_IDS
    assert report.errors == ()
    assert report.has_errors is False


# ---------------------------------------------------------------------------
# _check_voice — direct calls
# ---------------------------------------------------------------------------


def test_check_voice_returns_empty_without_a_codex_dir(tmp_path):
    """A project with no `.lore/codex/` yields no rows and does not raise."""
    assert _check_voice(tmp_path) == []


def test_check_voice_clean_doc_returns_empty(tmp_path):
    """A doc in the voice yields no rows."""
    root = make_project(tmp_path)
    write_codex(root, "tech-parser", "`lore health` rejects any file with an undeclared key.")
    assert _check_voice(root) == []


def test_check_voice_all_five_checks_on_a_canonical_doc(tmp_path):
    """All ten rules that have a mechanical check fire on a canonical doc."""
    root = make_project(tmp_path)
    write_codex(root, "tech-parser", ALL_FIVE_VIOLATIONS)
    assert checks(_check_voice(root)) == ALL_FIVE_IDS


def test_check_voice_row_shape(tmp_path):
    """Rows are warnings, entity_type `codex`, id'd by the doc's frontmatter id."""
    root = make_project(tmp_path)
    write_codex(root, "tech-parser", "The resolver is robust.")

    (issue,) = _check_voice(root)

    assert issue.severity == "warning"
    assert issue.entity_type == "codex"
    assert issue.id == "tech-parser"
    assert issue.check == "voice_sales_register"
    assert issue.detail == 'line 6: "robust" — sales register (V9)'
    assert issue.schema_id is None
    assert issue.rule is None
    assert issue.pointer is None


def test_check_voice_falls_back_to_the_relative_path_without_an_id(tmp_path):
    """A doc with no frontmatter id is identified by its path under `codex/`."""
    root = make_project(tmp_path)
    (root / ".lore" / "codex" / "orphan.md").write_text(
        "No frontmatter here. The resolver is robust.\n", encoding="utf-8"
    )

    (issue,) = _check_voice(root)

    assert issue.id == "orphan.md"


def test_check_voice_rows_sort_by_id_then_line(tmp_path):
    """Rows come back ordered by codex id ascending, then line number."""
    root = make_project(tmp_path)
    write_codex(root, "zzz-doc", "The resolver is robust.")
    write_codex(root, "aaa-doc", "Intro line.\nThe parser is robust.\nIt is simply fast.")

    issues = _check_voice(root)

    assert [(i.id, i.detail.split(":")[0]) for i in issues] == [
        ("aaa-doc", "line 7"),
        ("aaa-doc", "line 8"),
        ("zzz-doc", "line 6"),
    ]


def test_check_voice_deduplicates_a_repeated_phrase_on_one_line(tmp_path):
    """The same phrase twice on one line is one row, not two."""
    root = make_project(tmp_path)
    write_codex(root, "tech-parser", "It is robust, and the cache is robust.")

    assert len(_check_voice(root)) == 1


def test_check_voice_distinct_phrases_on_one_line_are_distinct_rows(tmp_path):
    """Two different flagged phrases on one line produce two rows."""
    root = make_project(tmp_path)
    write_codex(root, "tech-parser", "It is robust and simply fast.")

    assert len(_check_voice(root)) == 2


# ---------------------------------------------------------------------------
# Per-layer skips
# ---------------------------------------------------------------------------


def test_check_voice_decisions_layer_drops_past_narration(tmp_path):
    """V1 and V2 are off in `decisions/`; V3, V4, V5, V9 stay on."""
    root = make_project(tmp_path)
    write_codex(root, "decisions-001-x", ALL_FIVE_VIOLATIONS, layer="decisions")
    assert checks(_check_voice(root)) == ALL_FIVE_IDS - {"voice_past_narration"}


def test_check_voice_transient_layer_drops_v1_to_v4(tmp_path):
    """V1-V4 are off in `transient/`; V5 and V9 stay on."""
    root = make_project(tmp_path)
    write_codex(root, "prd-thing", ALL_FIVE_VIOLATIONS, layer="transient")
    assert checks(_check_voice(root)) == {"voice_dangling_deixis", "voice_sales_register"}


def test_check_voice_sources_layer_is_exempt(tmp_path):
    """No voice rule applies to `sources/` — bodies are verbatim upstream text."""
    root = make_project(tmp_path)
    write_codex(root, "src-ticket", ALL_FIVE_VIOLATIONS, layer="sources")
    assert _check_voice(root) == []


def test_check_voice_vision_layer_is_exempt(tmp_path):
    """`vision/` is deferred until the rule is settled."""
    root = make_project(tmp_path)
    write_codex(root, "vision-thing", ALL_FIVE_VIOLATIONS, layer="vision")
    assert _check_voice(root) == []


def test_check_voice_skips_its_own_generated_report(tmp_path):
    """`transient/health-*.md` quotes violations; that is not committing one."""
    root = make_project(tmp_path)
    transient = root / ".lore" / "codex" / "transient"
    transient.mkdir(parents=True, exist_ok=True)
    (transient / "health-2026-05-25T12-34-56.md").write_text(
        "---\n"
        "id: health-2026-05-25T12-34-56\n"
        "title: Health Report\n"
        "summary: lore health report\n"
        "---\n"
        "| WARNING | codex | x | voice_sales_register | line 6: \"simply\" |\n"
        "| WARNING | codex | y | voice_dangling_deixis | line 9: \"the new flag\" |\n",
        encoding="utf-8",
    )

    assert _check_voice(root) == []


def test_check_voice_still_lints_other_transient_docs(tmp_path):
    """The carve-out is scoped to `health-*.md`, not to the whole layer."""
    root = make_project(tmp_path)
    write_codex(root, "prd-thing", "The resolver is robust.", layer="transient")

    (issue,) = _check_voice(root)

    assert issue.id == "prd-thing"
    assert issue.check == "voice_sales_register"


# ---------------------------------------------------------------------------
# _voice_lintable_lines — the regions a check may read
# ---------------------------------------------------------------------------


def test_lintable_lines_keeps_only_the_summary_frontmatter_value():
    """`id`/`title`/`related` are metadata; `summary` is prose."""
    text = (
        "---\n"
        "id: tech-parser\n"
        "title: The robust parser\n"
        "summary: A simply fast parser.\n"
        "related: []\n"
        "---\n"
        "Body line.\n"
    )
    assert _voice_lintable_lines(text) == [
        (4, "A simply fast parser."),
        (7, "Body line."),
        (8, ""),
    ]


def test_lintable_lines_keeps_a_block_scalar_summary():
    """A folded `summary:` keeps its continuation lines, dropping the header."""
    text = (
        "---\n"
        "id: tech-parser\n"
        "summary: >\n"
        "  The parser is robust\n"
        "  across restarts.\n"
        "title: t\n"
        "---\n"
        "Body.\n"
    )
    kept = dict(_voice_lintable_lines(text))
    assert kept[4] == "  The parser is robust"
    assert kept[5] == "  across restarts."
    assert 6 not in kept  # title, back out of the summary block


def test_lintable_lines_drops_fenced_blocks_and_keeps_line_numbers():
    """Fenced content is dropped; surviving lines keep their original numbers."""
    text = "Before.\n```\ninside\n```\nAfter.\n"
    assert _voice_lintable_lines(text) == [(1, "Before."), (5, "After."), (6, "")]


def test_lintable_lines_blanks_inline_code_spans():
    """Backticked spans are replaced, so identifiers do not read as prose."""
    assert _voice_lintable_lines("The `simply_parse` helper.\n")[0] == (1, "The   helper.")


def test_lintable_lines_handles_a_file_without_frontmatter():
    """A body-only file is linted in full."""
    assert _voice_lintable_lines("Just a body.\n") == [(1, "Just a body."), (2, "")]


# ---------------------------------------------------------------------------
# Tuned false-positive carve-outs
# ---------------------------------------------------------------------------


def test_no_longer_present_state_does_not_fire(tmp_path):
    """"no longer visible" is a fact about today."""
    root = make_project(tmp_path)
    write_codex(root, "tech-tree", "A collapsed node leaves the parent no longer visible.")
    assert _check_voice(root) == []


def test_no_longer_exists_in_a_main_clause_fires(tmp_path):
    """"no longer exists" as a standalone claim is changelog content."""
    root = make_project(tmp_path)
    write_codex(root, "tech-layout", "The bootstrap subdirectory no longer exists.")
    assert checks(_check_voice(root)) == {"voice_past_narration"}


def test_no_longer_exists_in_a_subordinate_clause_does_not_fire(tmp_path):
    """A subordinator before the phrase makes it a present condition."""
    root = make_project(tmp_path)
    write_codex(root, "tech-show", "If the Knight file no longer exists, the CLI warns.")
    assert _check_voice(root) == []


def test_used_to_meaning_employed_for_does_not_fire(tmp_path):
    """Only "used to be" fires; the "employed in order to" sense does not."""
    root = make_project(tmp_path)
    write_codex(root, "tech-regex", "The regex used to match paths is compiled once.")
    assert _check_voice(root) == []


def test_used_to_be_fires(tmp_path):
    """"used to be" is prior-state narration."""
    root = make_project(tmp_path)
    write_codex(root, "tech-regex", "The field used to be a string.")
    assert checks(_check_voice(root)) == {"voice_past_narration"}


def test_conditional_perfect_passive_does_not_fire(tmp_path):
    """Generic change verbs in the perfect passive are process description."""
    root = make_project(tmp_path)
    write_codex(root, "tech-transient", "Delete it after its facts have been folded into stable docs.")
    assert _check_voice(root) == []


def test_renamed_perfect_passive_fires(tmp_path):
    """"has been renamed" can only be describing the system's own history."""
    root = make_project(tmp_path)
    write_codex(root, "tech-fields", "The board field has been renamed.")
    assert checks(_check_voice(root)) == {"voice_past_narration"}


def test_being_planned_does_not_fire(tmp_path):
    """"work being planned" is a gerund object, not a promise."""
    root = make_project(tmp_path)
    write_codex(root, "tech-layers", "The layer holds work being planned or developed.")
    assert _check_voice(root) == []


def test_as_planned_does_not_fire(tmp_path):
    """"as planned" is a comparison, not a promise."""
    root = make_project(tmp_path)
    write_codex(root, "tech-run", "The migration completes as planned.")
    assert _check_voice(root) == []


def test_planned_as_a_predicate_fires(tmp_path):
    """"is planned for" promises future work."""
    root = make_project(tmp_path)
    write_codex(root, "tech-roadmap", "Soft-delete is planned for the two-file model.")
    assert checks(_check_voice(root)) == {"voice_forward_promise"}


def test_procedural_the_new_x_does_not_fire(tmp_path):
    """"the new value"/"the new file" resolve inside the sentence."""
    root = make_project(tmp_path)
    write_codex(root, "tech-migrations", "Update the INSERT line to the new value, then write the new file.")
    assert _check_voice(root) == []


def test_the_new_flag_fires(tmp_path):
    """"the new flag" names a system element with no antecedent."""
    root = make_project(tmp_path)
    write_codex(root, "tech-cli", "Pass the new flag to limit the audit.")
    assert checks(_check_voice(root)) == {"voice_dangling_deixis"}


def test_temporal_just_does_not_fire(tmp_path):
    """"just before"/"just as"/"just-in-time" are temporal."""
    root = make_project(tmp_path)
    write_codex(root, "tech-timing", "It warms just before the read, just as the pool opens, just-in-time.")
    assert _check_voice(root) == []


def test_minimising_just_fires(tmp_path):
    """"is just one kind of" minimises — the sales register V9 names."""
    root = make_project(tmp_path)
    write_codex(root, "tech-notes", "An Artifact ID is just one kind of content.")
    assert checks(_check_voice(root)) == {"voice_sales_register"}
