"""Unit tests for lore.glossary — scan_glossary, read_glossary_item,
search_glossary, and GlossaryError.

Spec: glossary-us-001 (lore codex show glossary-us-001)
Workflow: conceptual-workflows-glossary
"""

from __future__ import annotations

import pytest

from lore.glossary import (
    GlossaryError,
    read_glossary_item,
    scan_glossary,
    search_glossary,
)


CONSTABLE_QUEST_YAML = """\
items:
  - keyword: Constable
    definition: Mission type for orchestrator-handled chores (commits, housekeeping). Not dispatched to a worker.
    aliases: [constable mission, chore mission]
    do_not_use: [bot mission]
  - keyword: Quest
    definition: A live grouping of Missions representing one body of work.
    do_not_use: [epic, story group]
"""


def _write_glossary(root, content):
    """Write the glossary YAML at the canonical path."""
    target = root / ".lore" / "codex" / "glossary.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# scan_glossary
# ---------------------------------------------------------------------------


def test_scan_glossary_returns_empty_when_file_missing(tmp_path):
    # conceptual-workflows-glossary — scan_glossary missing-file behaviour
    assert scan_glossary(tmp_path) == []


def test_scan_glossary_returns_items_in_source_order(tmp_path):
    # conceptual-workflows-glossary — happy-path scan (US-001 Scenario 1)
    _write_glossary(tmp_path, CONSTABLE_QUEST_YAML)
    items = scan_glossary(tmp_path)
    assert [i.keyword for i in items] == ["Constable", "Quest"]
    assert items[0].aliases == ("constable mission", "chore mission")
    assert items[0].do_not_use == ("bot mission",)
    assert items[1].aliases == ()  # default empty tuple
    assert items[1].do_not_use == ("epic", "story group")


def test_scan_glossary_returns_list_of_glossary_item(tmp_path):
    # conceptual-workflows-glossary — return type contract
    from lore.models import GlossaryItem

    _write_glossary(tmp_path, CONSTABLE_QUEST_YAML)
    items = scan_glossary(tmp_path)
    assert all(isinstance(i, GlossaryItem) for i in items)
    assert len(items) == 2


def test_scan_glossary_raises_on_malformed_yaml(tmp_path):
    # conceptual-workflows-glossary — malformed YAML fail-loud (US-001 Scenario 3)
    _write_glossary(tmp_path, "items: not-a-list")
    with pytest.raises(GlossaryError, match="items"):
        scan_glossary(tmp_path)


def test_scan_glossary_raises_on_missing_required_definition(tmp_path):
    # conceptual-workflows-glossary — schema rejects missing required (US-001 Scenario 4)
    _write_glossary(tmp_path, "items:\n  - keyword: Mission\n")
    with pytest.raises(GlossaryError, match="required.*definition"):
        scan_glossary(tmp_path)


def test_scan_glossary_raises_on_tab_indentation(tmp_path):
    # conceptual-workflows-glossary — YAML parse fail
    _write_glossary(tmp_path, "items:\n\t- keyword: X\n")
    with pytest.raises(GlossaryError):
        scan_glossary(tmp_path)


def test_scan_glossary_raises_on_extra_top_level_key(tmp_path):
    # conceptual-workflows-glossary — additionalProperties rule
    _write_glossary(tmp_path, "items: []\nextra: nope\n")
    with pytest.raises(GlossaryError):
        scan_glossary(tmp_path)


def test_scan_glossary_raises_on_non_list_items(tmp_path):
    # conceptual-workflows-glossary — items type rule
    _write_glossary(tmp_path, "items: not-a-list\n")
    with pytest.raises(GlossaryError):
        scan_glossary(tmp_path)


def test_scan_glossary_raises_on_multiline_keyword(tmp_path):
    # conceptual-workflows-glossary — pattern rule on keyword
    _write_glossary(
        tmp_path,
        'items:\n  - keyword: "two\\nlines"\n    definition: D\n',
    )
    with pytest.raises(GlossaryError):
        scan_glossary(tmp_path)


def test_scan_glossary_raises_on_oversized_definition(tmp_path):
    # conceptual-workflows-glossary — maxLength rule on definition
    _write_glossary(
        tmp_path,
        f"items:\n  - keyword: K\n    definition: {'x' * 1001}\n",
    )
    with pytest.raises(GlossaryError):
        scan_glossary(tmp_path)


def test_scan_glossary_raises_on_duplicate_aliases(tmp_path):
    # conceptual-workflows-glossary — uniqueItems rule on aliases
    _write_glossary(
        tmp_path,
        "items:\n  - keyword: K\n    definition: D\n    aliases: [a, a]\n",
    )
    with pytest.raises(GlossaryError):
        scan_glossary(tmp_path)


# ---------------------------------------------------------------------------
# read_glossary_item
# ---------------------------------------------------------------------------


def test_read_glossary_item_case_insensitive_hit(tmp_path):
    # conceptual-workflows-glossary — case-insensitive keyword lookup (US-001 Scenario 5)
    _write_glossary(tmp_path, CONSTABLE_QUEST_YAML)
    item = read_glossary_item(tmp_path, "constable")
    assert item is not None
    assert item.keyword == "Constable"


def test_read_glossary_item_alias_returns_none(tmp_path):
    # conceptual-workflows-glossary — aliases NOT lookup keys (FR-7, US-001 Scenario 5)
    _write_glossary(tmp_path, CONSTABLE_QUEST_YAML)
    assert read_glossary_item(tmp_path, "CONSTABLE MISSION") is None


def test_read_glossary_item_missing_returns_none(tmp_path):
    # conceptual-workflows-glossary — not-found behaviour
    _write_glossary(tmp_path, CONSTABLE_QUEST_YAML)
    assert read_glossary_item(tmp_path, "nonsense") is None


def test_read_glossary_item_missing_file_returns_none(tmp_path):
    # conceptual-workflows-glossary — missing file is not an error for reads
    assert read_glossary_item(tmp_path, "anything") is None


# ---------------------------------------------------------------------------
# search_glossary
# ---------------------------------------------------------------------------


def test_search_glossary_matches_keyword(tmp_path):
    # conceptual-workflows-glossary — search across keyword (US-001 Scenario 6)
    _write_glossary(tmp_path, CONSTABLE_QUEST_YAML)
    res = search_glossary(tmp_path, "constable")
    assert [i.keyword for i in res] == ["Constable"]


def test_search_glossary_matches_do_not_use(tmp_path):
    # conceptual-workflows-glossary — search across do_not_use (US-001 Scenario 6)
    _write_glossary(tmp_path, CONSTABLE_QUEST_YAML)
    res = search_glossary(tmp_path, "epic")
    assert [i.keyword for i in res] == ["Quest"]


def test_search_glossary_alphabetised_across_aliases_and_definition(tmp_path):
    # conceptual-workflows-glossary — alphabetised + multi-field (US-001 Scenario 6)
    _write_glossary(tmp_path, CONSTABLE_QUEST_YAML)
    res = search_glossary(tmp_path, "MISSION")
    assert [i.keyword for i in res] == ["Constable", "Quest"]


def test_search_glossary_no_match_returns_empty(tmp_path):
    # conceptual-workflows-glossary — no-match path
    _write_glossary(tmp_path, CONSTABLE_QUEST_YAML)
    assert search_glossary(tmp_path, "zzz") == []


def test_search_glossary_substring_match_in_definition(tmp_path):
    # conceptual-workflows-glossary — substring (not whole-token) match in definition
    _write_glossary(tmp_path, CONSTABLE_QUEST_YAML)
    res = search_glossary(tmp_path, "grouping")
    assert [i.keyword for i in res] == ["Quest"]


def test_search_glossary_preserves_display_casing(tmp_path):
    # conceptual-workflows-glossary — sort is casefolded; display preserves source casing
    _write_glossary(tmp_path, CONSTABLE_QUEST_YAML)
    res = search_glossary(tmp_path, "MISSION")
    # casing in display preserved (Constable, Quest), order based on casefold
    assert res[0].keyword == "Constable"
    assert res[1].keyword == "Quest"


# ---------------------------------------------------------------------------
# GlossaryError
# ---------------------------------------------------------------------------


def test_glossary_error_subclass_of_exception():
    # conceptual-workflows-glossary — error type contract
    assert issubclass(GlossaryError, Exception)


# ===========================================================================
# US-004 — Auto-surface on `lore codex show`
# Spec: glossary-us-004 (lore codex show glossary-us-004)
# Workflow: conceptual-workflows-glossary
#
# These tests cover the new symbols added to lore.glossary by US-004:
#   _normalise_tokens, _build_lookup, _scan_runs, match_glossary,
#   _render_glossary_block.
# Import-failure-as-red is expected until G3-Green lands the implementation.
# ===========================================================================


from lore.glossary import (  # noqa: E402  — imports under test
    _build_lookup,
    _normalise_tokens,
    _render_glossary_block,
    _scan_runs,
    match_glossary,
)
from lore.models import GlossaryItem  # noqa: E402


# ---------------------------------------------------------------------------
# _normalise_tokens (Unit rows 1–5)
# ---------------------------------------------------------------------------


def test_normalise_tokens_ascii_split():
    # conceptual-workflows-glossary — tokeniser ASCII (Unit row 1)
    assert _normalise_tokens("Hello, world!") == ["hello", "world"]


def test_normalise_tokens_unicode_punctuation():
    # conceptual-workflows-glossary — tokeniser Unicode (Unit row 2)
    # Non-breaking space, en-dash, fullwidth comma all split as non-word.
    assert _normalise_tokens("foo bar–baz，qux") == [
        "foo",
        "bar",
        "baz",
        "qux",
    ]


def test_normalise_tokens_casefold_basic_ascii():
    # conceptual-workflows-glossary — casefold ASCII (Unit row 3a)
    assert _normalise_tokens("Bee") == ["bee"]


def test_normalise_tokens_casefold_unicode_dotted_i():
    # conceptual-workflows-glossary — casefold Unicode (Unit row 3b)
    # Turkish capital dotted I casefolds to "i̇".
    assert _normalise_tokens("İ") == ["i̇"]


def test_normalise_tokens_apostrophe_split():
    # conceptual-workflows-glossary — apostrophe split (Unit row 4)
    assert _normalise_tokens("source's") == ["source", "s"]


def test_normalise_tokens_empty_returns_empty_list():
    # conceptual-workflows-glossary — empty input (Unit row 5a)
    assert _normalise_tokens("") == []


def test_normalise_tokens_punctuation_only_returns_empty_list():
    # conceptual-workflows-glossary — punctuation only (Unit row 5b)
    assert _normalise_tokens("...!?") == []


# ---------------------------------------------------------------------------
# _build_lookup (Unit rows 6–10)
# ---------------------------------------------------------------------------


def test_build_lookup_single_word_keyword_one_tuple():
    # conceptual-workflows-glossary — lookup single-word (Unit row 6)
    items = [GlossaryItem(keyword="Mission", definition="d")]
    lookup = _build_lookup(items, source="canonical")
    assert ("mission",) in lookup


def test_build_lookup_multi_word_keyword_tuple():
    # conceptual-workflows-glossary — lookup multi-word (Unit row 7)
    items = [GlossaryItem(keyword="Codex Source", definition="d")]
    lookup = _build_lookup(items, source="canonical")
    assert ("codex", "source") in lookup


def test_build_lookup_aliases_indexed():
    # conceptual-workflows-glossary — aliases indexed (Unit row 8)
    items = [GlossaryItem(keyword="K", definition="d", aliases=("alpha beta",))]
    lookup = _build_lookup(items, source="canonical")
    assert ("alpha", "beta") in lookup


def test_build_lookup_canonical_excludes_do_not_use():
    # conceptual-workflows-glossary — FR-17, canonical excludes do_not_use (Unit row 9)
    items = [GlossaryItem(keyword="K", definition="d", do_not_use=("bad",))]
    lookup = _build_lookup(items, source="canonical")
    assert ("bad",) not in lookup


def test_build_lookup_records_source_tag():
    # conceptual-workflows-glossary — source tag recorded (Unit row 10)
    items = [
        GlossaryItem(
            keyword="K", definition="d", aliases=("a",), do_not_use=("b",)
        )
    ]
    can = _build_lookup(items, source="canonical")
    dep = _build_lookup(items, source="deprecated")
    assert can[("k",)][1] == "keyword"
    assert can[("a",)][1] == "alias"
    assert dep[("b",)][1] == "do_not_use"


# ---------------------------------------------------------------------------
# _scan_runs (Unit rows 11–15)
# ---------------------------------------------------------------------------


def test_scan_runs_match_at_index_zero_mid_and_end():
    # conceptual-workflows-glossary — match positions (Unit row 11)
    items = [GlossaryItem(keyword="X", definition="d")]
    lookup = _build_lookup(items, source="canonical")
    assert _scan_runs(["x", "a", "b"], lookup)
    assert _scan_runs(["a", "x", "b"], lookup)
    assert _scan_runs(["a", "b", "x"], lookup)


def test_scan_runs_longest_match_wins():
    # conceptual-workflows-glossary — longest-match prefers multi-word (Unit row 12)
    items = [
        GlossaryItem(keyword="Codex Source", definition="long"),
        GlossaryItem(keyword="Codex", definition="short"),
    ]
    lookup = _build_lookup(items, source="canonical")
    matched = _scan_runs(["codex", "source", "extra"], lookup)
    keywords = [m[0].keyword for m in matched]
    assert "Codex Source" in keywords
    # Greedy: the run is consumed by the longer match, so "Codex" alone
    # should NOT also be emitted from the same starting position.
    assert keywords.count("Codex") == 0


def test_scan_runs_missionary_does_not_match_mission():
    # conceptual-workflows-glossary — substring guard (Unit row 13)
    items = [GlossaryItem(keyword="Mission", definition="d")]
    lookup = _build_lookup(items, source="canonical")
    assert _scan_runs(["missionary"], lookup) == []


def test_scan_runs_multi_word_run_is_greedy():
    # conceptual-workflows-glossary — greedy multi-word (Unit row 14)
    items = [GlossaryItem(keyword="A B C", definition="d")]
    lookup = _build_lookup(items, source="canonical")
    matched = _scan_runs(["a", "b", "c", "tail"], lookup)
    assert matched and matched[0][0].keyword == "A B C"


def test_scan_runs_set_semantics_per_call():
    # conceptual-workflows-glossary — emit-once per item per call (Unit row 15)
    items = [GlossaryItem(keyword="X", definition="d")]
    lookup = _build_lookup(items, source="canonical")
    out = _scan_runs(["x", "x", "x"], lookup)
    assert len({m[0] for m in out}) == 1


# ---------------------------------------------------------------------------
# match_glossary (Unit rows 16–21)
# ---------------------------------------------------------------------------


def test_match_glossary_excludes_do_not_use_term():
    # conceptual-workflows-glossary — FR-17, do_not_use does NOT surface (Unit row 16)
    items = [
        GlossaryItem(keyword="Mission", definition="d", do_not_use=("task",))
    ]
    res = match_glossary(["The task force convened."], items=items)
    assert res == []


def test_match_glossary_alphabetises_results():
    # conceptual-workflows-glossary — alphabetised by casefolded keyword (Unit row 17)
    items = [
        GlossaryItem(keyword="Quest", definition="d"),
        GlossaryItem(keyword="Mission", definition="d"),
    ]
    res = match_glossary(["Mission Quest"], items=items)
    assert [i.keyword for i in res] == ["Mission", "Quest"]


def test_match_glossary_no_match_returns_empty_list():
    # conceptual-workflows-glossary — no-match (Unit row 18)
    items = [GlossaryItem(keyword="Mission", definition="d")]
    assert match_glossary(["nothing relevant"], items=items) == []


def test_match_glossary_multi_word_apostrophe_regression():
    # conceptual-workflows-glossary — multi-word + apostrophe regression (Unit row 19)
    items = [GlossaryItem(keyword="Codex Source", definition="d")]
    res = match_glossary(["the codex source's structure"], items=items)
    assert [i.keyword for i in res] == ["Codex Source"]


def test_match_glossary_missing_file_returns_empty(tmp_path):
    # conceptual-workflows-glossary — missing-file silent skip (Unit row 20)
    assert match_glossary(["any body"], root=tmp_path) == []


def test_match_glossary_malformed_file_raises_glossary_error(tmp_path):
    # conceptual-workflows-glossary — malformed propagates (Unit row 21)
    _write_glossary(tmp_path, "items: not-a-list\n")
    with pytest.raises(GlossaryError):
        match_glossary(["any body"], root=tmp_path)


# ---------------------------------------------------------------------------
# _render_glossary_block (Unit rows 22–24)
# ---------------------------------------------------------------------------


def test_render_glossary_block_empty_returns_empty_string():
    # conceptual-workflows-glossary — render empty (Unit row 22)
    assert _render_glossary_block([]) == ""


def test_render_glossary_block_one_item_exact_format():
    # conceptual-workflows-glossary — render one item exact format (Unit row 23a)
    items = [GlossaryItem(keyword="K", definition="d")]
    assert _render_glossary_block(items) == "\n## Glossary\n\n**K** — d\n"


def test_render_glossary_block_collapses_internal_whitespace():
    # conceptual-workflows-glossary — internal whitespace collapse (Unit row 23b)
    items = [GlossaryItem(keyword="K", definition="line one\n  line   two")]
    out = _render_glossary_block(items)
    assert "**K** — line one line two\n" in out


def test_render_glossary_block_multiple_items_alphabetised_blank_line_separated():
    # conceptual-workflows-glossary — multi-item alphabetised, blank line separated (Unit row 24)
    items = [
        GlossaryItem(keyword="B", definition="b"),
        GlossaryItem(keyword="A", definition="a"),
    ]
    out = _render_glossary_block(items)
    assert out.index("**A**") < out.index("**B**")
    assert "\n\n**" in out


# ===========================================================================
# US-005 — find_deprecated_terms (cross-codex deprecated-term scan)
# Spec: glossary-us-005 (lore codex show glossary-us-005)
# Workflow: conceptual-workflows-glossary
#
# Tests the new lore.glossary.find_deprecated_terms public API. Import-failure
# counts as red until US-005 Green lands the implementation.
# ===========================================================================


from lore.glossary import find_deprecated_terms  # noqa: E402  — import under test


def test_find_deprecated_terms_only_do_not_use_surfaces():
    # conceptual-workflows-glossary — Unit row 1 (FR-17 deprecated-only matching)
    items = [
        GlossaryItem(keyword="Knight", definition="d", do_not_use=("agent",)),
        GlossaryItem(keyword="Quest", definition="d"),  # no do_not_use
    ]
    bodies = {"doc-a": "the Knight wields a Quest and another agent helps."}
    out = find_deprecated_terms(bodies, items=items)
    # Canonical Knight + Quest in body do NOT surface; only `agent` (do_not_use).
    assert [t[2] for t in out] == ["agent"]


def test_find_deprecated_terms_one_tuple_per_occurrence_per_doc():
    # conceptual-workflows-glossary — Unit row 2 (FR-21 one-per-occurrence-per-doc)
    items = [
        GlossaryItem(keyword="Knight", definition="d", do_not_use=("agent",)),
        GlossaryItem(keyword="Quest", definition="d", do_not_use=("epic",)),
    ]
    bodies = {
        "doc-a": "The agent retrieves the codex.",
        "doc-b": "An epic encompasses many features. Another agent collaborates here.",
    }
    out = find_deprecated_terms(bodies, items=items)
    assert len(out) == 3


def test_find_deprecated_terms_tuple_shape():
    # conceptual-workflows-glossary — Unit row 3 (tuple shape contract)
    items = [GlossaryItem(keyword="Knight", definition="d", do_not_use=("agent",))]
    bodies = {"doc-a": "the agent."}
    out = find_deprecated_terms(bodies, items=items)
    assert len(out) == 1
    item, doc_id, term = out[0]
    assert isinstance(item, GlossaryItem)
    assert item.keyword == "Knight"
    assert doc_id == "doc-a"
    assert term == "agent"


def test_find_deprecated_terms_substring_guard():
    # conceptual-workflows-glossary — Unit row 4 (FR-16 reuse: contiguous-token-run only)
    items = [GlossaryItem(keyword="Mission", definition="d", do_not_use=("task",))]
    bodies = {"doc-a": "The taskforce reviewed the missionary work."}
    assert find_deprecated_terms(bodies, items=items) == []


def test_find_deprecated_terms_empty_bodies():
    # conceptual-workflows-glossary — Unit row 5 (no bodies = no results)
    items = [GlossaryItem(keyword="Knight", definition="d", do_not_use=("agent",))]
    assert find_deprecated_terms({}, items=items) == []


def test_find_deprecated_terms_missing_glossary_returns_empty(tmp_path):
    # conceptual-workflows-glossary — Unit row 6 (missing file returns [])
    assert find_deprecated_terms({"doc-a": "anything"}, root=tmp_path) == []
