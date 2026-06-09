"""Tests for extra_fields parameter on parse_frontmatter_doc and
parse_frontmatter_doc_full in lore.frontmatter.
"""

import textwrap

from lore.frontmatter import parse_frontmatter_doc, parse_frontmatter_doc_full

# transient-rites-us-5 — the codex `rites:` read side reuses the bindings parse
# pattern: parse_frontmatter_doc(extra_fields=("rites",)) feeds
# `_load_codex_rites_index`, which the wiring test below exercises end to end.
from lore.impacts import _load_codex_rites_index


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(tmp_path, extra_frontmatter: str = "", name: str = "doc.md") -> object:
    """Write a minimal valid codex document with optional extra frontmatter lines."""
    base = textwrap.dedent("""\
        ---
        id: doc-a
        title: Test Document
        summary: A test document
        {extra}
        ---
        Body text.
    """).format(extra=extra_frontmatter)
    path = tmp_path / name
    path.write_text(base)
    return path


# ---------------------------------------------------------------------------
# parse_frontmatter_doc — extra_fields parameter
# ---------------------------------------------------------------------------

# conceptual-workflows-codex-map step 3 (extra_fields on parse_frontmatter_doc — field present)
# tech-arch-frontmatter (extra_fields — field present returns raw list)
def test_parse_frontmatter_doc_extra_fields_returns_related_list(tmp_path):
    """extra_fields=("related",) returns the related list when field is present."""
    path = _make_doc(tmp_path, extra_frontmatter="related:\n  - doc-b\n  - doc-c")
    result = parse_frontmatter_doc(path, extra_fields=("related",))
    assert result is not None
    assert result["related"] == ["doc-b", "doc-c"]


# conceptual-workflows-codex-map step 3 (extra_fields on parse_frontmatter_doc — absent field omitted)
# tech-arch-frontmatter (extra_fields — absent field omitted from dict)
def test_parse_frontmatter_doc_extra_fields_absent_field_omitted(tmp_path):
    """extra_fields=("related",) omits the key when field is absent from frontmatter."""
    path = _make_doc(tmp_path)  # no related field
    result = parse_frontmatter_doc(path, extra_fields=("related",))
    assert result is not None
    assert "related" not in result


# conceptual-workflows-codex-map step 3 (extra_fields default — backward compatible)
# tech-arch-frontmatter (extra_fields — default call backward compatible)
def test_parse_frontmatter_doc_default_call_unaffected(tmp_path):
    """Default call with extra_fields=() does not include related in result."""
    path = _make_doc(tmp_path, extra_frontmatter="related:\n  - doc-b")
    # Explicitly passing the default empty tuple must also work without error,
    # confirming the parameter exists with the correct default.
    result = parse_frontmatter_doc(path, extra_fields=())
    assert result is not None
    assert "related" not in result


# ---------------------------------------------------------------------------
# parse_frontmatter_doc — codex `rites:` read side (transient-rites-us-5)
# tech-arch-frontmatter (a new codex edge is read through extra_fields, exactly
#   like binds/related — no new parse helper)
# decisions-014-link-direction (codex → rite is the only rite edge)
# ---------------------------------------------------------------------------


def _make_codex_file(tmp_path, doc_id: str, rites_block: str = "", name=None):
    """Write a codex doc with required triple plus optional `rites:` block."""
    text = textwrap.dedent(
        """\
        ---
        id: {doc_id}
        title: {doc_id}
        summary: s
        {rites}---
        Body.
        """
    ).format(doc_id=doc_id, rites=rites_block)
    path = tmp_path / (name or f"{doc_id}.md")
    path.write_text(text)
    return path


def test_parse_frontmatter_doc_reads_rites_list(tmp_path):
    """extra_fields=("rites",) returns the rite-id list when the field is present."""
    path = _make_codex_file(tmp_path, "ops-refunds", "rites:\n  - issue-refund\n")
    result = parse_frontmatter_doc(path, extra_fields=("rites",))
    assert result is not None
    assert result.get("rites") == ["issue-refund"]


def test_parse_frontmatter_doc_absent_rites_yields_none(tmp_path):
    """Absent `rites:` is omitted from the dict — .get('rites') is None (== empty)."""
    path = _make_codex_file(tmp_path, "plain")  # no rites:
    result = parse_frontmatter_doc(path, extra_fields=("rites",))
    assert result is not None
    assert result.get("rites") is None


def test_codex_rites_index_consumes_parsed_rites(tmp_path):
    """transient-rites-us-5 — the codex read side wires the parsed `rites:` into
    `_load_codex_rites_index`: the parsed list round-trips into the index."""
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    _make_codex_file(codex_dir, "ops-refunds", "rites:\n  - issue-refund\n")
    index = _load_codex_rites_index(codex_dir)
    assert index["ops-refunds"] == ["issue-refund"]


# conceptual-workflows-codex-map step 3 (extra_fields — related: null returns None)
# tech-arch-frontmatter (extra_fields — related: null returns None value)
def test_parse_frontmatter_doc_extra_fields_null_related_returns_none(tmp_path):
    """extra_fields=("related",) returns None value when related: null in frontmatter."""
    path = _make_doc(tmp_path, extra_frontmatter="related: null")
    result = parse_frontmatter_doc(path, extra_fields=("related",))
    assert result is not None
    assert "related" in result
    assert result["related"] is None


# conceptual-workflows-codex-map step 3 (extra_fields — related: [] returns empty list)
# tech-arch-frontmatter (extra_fields — related: [] returns empty list)
def test_parse_frontmatter_doc_extra_fields_empty_list_returns_empty(tmp_path):
    """extra_fields=("related",) returns an empty list when related: [] in frontmatter."""
    path = _make_doc(tmp_path, extra_frontmatter="related: []")
    result = parse_frontmatter_doc(path, extra_fields=("related",))
    assert result is not None
    assert result["related"] == []


# ---------------------------------------------------------------------------
# parse_frontmatter_doc_full — extra_fields parameter
# ---------------------------------------------------------------------------

# conceptual-workflows-codex-map step 3 (extra_fields on parse_frontmatter_doc_full — field present)
# tech-arch-frontmatter (parse_frontmatter_doc_full — extra_fields present)
def test_parse_frontmatter_doc_full_extra_fields_returns_related(tmp_path):
    """parse_frontmatter_doc_full with extra_fields=("related",) returns related list."""
    path = _make_doc(tmp_path, extra_frontmatter="related:\n  - doc-b")
    result = parse_frontmatter_doc_full(path, extra_fields=("related",))
    assert result is not None
    assert result["related"] == ["doc-b"]


# conceptual-workflows-codex-map step 3 (extra_fields on parse_frontmatter_doc_full — absent omitted)
# tech-arch-frontmatter (parse_frontmatter_doc_full — extra_fields absent omitted)
def test_parse_frontmatter_doc_full_extra_fields_absent_omitted(tmp_path):
    """parse_frontmatter_doc_full omits key when extra field absent from frontmatter."""
    path = _make_doc(tmp_path)  # no related field
    result = parse_frontmatter_doc_full(path, extra_fields=("related",))
    assert result is not None
    assert "related" not in result


# conceptual-workflows-codex-map step 3 (extra_fields on parse_frontmatter_doc_full — default unaffected)
# tech-arch-frontmatter (parse_frontmatter_doc_full — default call unaffected)
def test_parse_frontmatter_doc_full_default_call_unaffected(tmp_path):
    """Default call with extra_fields=() does not include related in parse_frontmatter_doc_full."""
    path = _make_doc(tmp_path, extra_frontmatter="related:\n  - doc-b")
    # Explicitly passing the default empty tuple must also work without error,
    # confirming the parameter exists with the correct default.
    result = parse_frontmatter_doc_full(path, extra_fields=())
    assert result is not None
    assert "related" not in result
