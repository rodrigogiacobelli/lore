"""Unit tests for subtree filter matching in scan_codex and related list functions.

These tests are RED-first: they describe the desired subtree-match behaviour
after the fix is in place. Every test MUST fail against the current
exact-match implementation.

Spec: filter-list (lore codex show filter-list)
Quest: q-c3e1 / Mission: m-2518
"""

import textwrap
from pathlib import Path

from lore.codex import scan_codex


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_doc(base_dir: Path, rel_path: str, doc_id: str, title: str = "Title") -> Path:
    """Write a minimal valid codex document at base_dir/rel_path."""
    path = base_dir / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(f"""\
            ---
            id: {doc_id}
            title: {title}
            summary: Summary for {doc_id}.
            ---

            Body of {doc_id}.
        """)
    )
    return path


# ---------------------------------------------------------------------------
# Subtree matching: token matches its own group AND child groups
# ---------------------------------------------------------------------------


def test_scan_codex_filter_matches_exact_group(tmp_path):
    """scan_codex with filter_groups=['conceptual'] returns docs with group='conceptual'."""
    codex_dir = tmp_path / ".lore" / "codex"
    _write_doc(codex_dir, "conceptual/concept-one.md", "concept-one")
    _write_doc(codex_dir, "technical/tech-one.md", "tech-one")

    results = scan_codex(codex_dir, filter_groups=["conceptual"])

    ids = [d["id"] for d in results]
    assert "concept-one" in ids


def test_scan_codex_filter_matches_child_group_via_subtree(tmp_path):
    """scan_codex with filter_groups=['conceptual'] also returns docs with group='conceptual-workflows'.

    Currently FAILS because the implementation uses exact-match only.
    """
    codex_dir = tmp_path / ".lore" / "codex"
    # group = "conceptual" (exact match — control)
    _write_doc(codex_dir, "conceptual/concept-one.md", "concept-one")
    # group = "conceptual-workflows" (subtree — should now be matched)
    _write_doc(codex_dir, "conceptual/workflows/workflow-one.md", "workflow-one")
    # group = "technical" (unrelated — must NOT be matched)
    _write_doc(codex_dir, "technical/tech-one.md", "tech-one")

    results = scan_codex(codex_dir, filter_groups=["conceptual"])

    ids = [d["id"] for d in results]
    assert "workflow-one" in ids, (
        "filter_groups=['conceptual'] must match docs in group 'conceptual-workflows' "
        "(subtree semantics), but 'workflow-one' was absent. "
        "Current implementation uses exact-match only — this test is intentionally RED."
    )


def test_scan_codex_filter_subtree_excludes_unrelated_group(tmp_path):
    """scan_codex with filter_groups=['conceptual'] does NOT match group='technical'."""
    codex_dir = tmp_path / ".lore" / "codex"
    _write_doc(codex_dir, "conceptual/concept-one.md", "concept-one")
    _write_doc(codex_dir, "conceptual/workflows/workflow-one.md", "workflow-one")
    _write_doc(codex_dir, "technical/tech-one.md", "tech-one")

    results = scan_codex(codex_dir, filter_groups=["conceptual"])

    ids = [d["id"] for d in results]
    assert "tech-one" not in ids


def test_scan_codex_filter_technical_matches_technical_api(tmp_path):
    """scan_codex with filter_groups=['technical'] returns docs with group='technical-api'.

    Currently FAILS because the implementation uses exact-match only.
    """
    codex_dir = tmp_path / ".lore" / "codex"
    # group = "technical" (exact match — control)
    _write_doc(codex_dir, "technical/tech-overview.md", "tech-overview")
    # group = "technical-api" (subtree — should be matched by 'technical' token)
    _write_doc(codex_dir, "technical/api/tech-api-spec.md", "tech-api-spec")
    # group = "decisions" (unrelated — must NOT be matched)
    _write_doc(codex_dir, "decisions/decision-001.md", "decision-001")

    results = scan_codex(codex_dir, filter_groups=["technical"])

    ids = [d["id"] for d in results]
    assert "tech-api-spec" in ids, (
        "filter_groups=['technical'] must match docs in group 'technical-api' "
        "(subtree semantics), but 'tech-api-spec' was absent. "
        "Current implementation uses exact-match only — this test is intentionally RED."
    )


def test_scan_codex_filter_subtree_does_not_match_prefix_without_hyphen(tmp_path):
    """filter_groups=['tech'] does NOT match group='technical' (must be separated by a hyphen).

    This ensures the subtree match is 'token-' prefix, not a bare string prefix.
    """
    codex_dir = tmp_path / ".lore" / "codex"
    _write_doc(codex_dir, "technical/tech-overview.md", "tech-overview")
    _write_doc(codex_dir, "tech/tech-doc.md", "tech-doc")

    results = scan_codex(codex_dir, filter_groups=["tech"])

    ids = [d["id"] for d in results]
    # 'tech-doc' is an exact group match — must be present
    assert "tech-doc" in ids
    # 'tech-overview' is in group 'technical' (not 'tech-...') — must NOT be present
    assert "tech-overview" not in ids, (
        "filter_groups=['tech'] must NOT match group='technical' "
        "(only 'tech' exact match and 'tech-...' subtree prefixes should be included)."
    )


def test_scan_codex_filter_root_docs_always_included_with_subtree(tmp_path):
    """Root-level docs (group='') are always included regardless of filter token and subtree."""
    codex_dir = tmp_path / ".lore" / "codex"
    # Root doc — no subdirectory
    _write_doc(codex_dir, "CODEX.md", "CODEX.md")
    _write_doc(codex_dir, "conceptual/workflows/workflow-one.md", "workflow-one")
    _write_doc(codex_dir, "technical/tech-one.md", "tech-one")

    results = scan_codex(codex_dir, filter_groups=["conceptual"])

    ids = [d["id"] for d in results]
    assert "CODEX.md" in ids


def test_scan_codex_filter_multiple_tokens_each_matches_subtree(tmp_path):
    """filter_groups=['conceptual', 'technical'] matches subtrees of both tokens.

    Currently FAILS because exact-match only returns 'conceptual' and 'technical' groups,
    not 'conceptual-workflows' or 'technical-api'.
    """
    codex_dir = tmp_path / ".lore" / "codex"
    _write_doc(codex_dir, "conceptual/concept-one.md", "concept-one")
    _write_doc(codex_dir, "conceptual/workflows/workflow-one.md", "workflow-one")
    _write_doc(codex_dir, "technical/tech-one.md", "tech-one")
    _write_doc(codex_dir, "technical/api/tech-api-spec.md", "tech-api-spec")
    _write_doc(codex_dir, "decisions/decision-001.md", "decision-001")

    results = scan_codex(codex_dir, filter_groups=["conceptual", "technical"])

    ids = [d["id"] for d in results]
    assert "concept-one" in ids
    assert "workflow-one" in ids, (
        "'workflow-one' (group='conceptual-workflows') must be matched by token 'conceptual'. RED."
    )
    assert "tech-one" in ids
    assert "tech-api-spec" in ids, (
        "'tech-api-spec' (group='technical-api') must be matched by token 'technical'. RED."
    )
    assert "decision-001" not in ids
