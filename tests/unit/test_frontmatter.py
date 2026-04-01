"""Tests for extra_fields parameter on parse_frontmatter_doc and
parse_frontmatter_doc_full in lore.frontmatter.
"""

import textwrap

from lore.frontmatter import parse_frontmatter_doc, parse_frontmatter_doc_full


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
