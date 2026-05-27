"""Tests for lore.frontmatter.parse_frontmatter_text (G9 RED).

Spec: transient-public-api-facade-tech-spec §8 (Frontmatter Parse Dedup).
Plan chunk: transient-public-api-facade-plan G9.

`parse_frontmatter_text(text, *, required_fields=("id","title","summary"),
extra_fields=()) -> dict | None` mirrors `parse_frontmatter_doc` semantics but
takes an in-memory string instead of a filepath. Used by `create_*`/`update_*`
paths that receive content from stdin or a source file.

Helper is internal — NOT exported from `lore.api.__all__`.

Acceptance:
- Same text content as a `parse_frontmatter_doc` roundtrip MUST produce
  identical dict (modulo the `path` key which is filepath-only).
- Missing `---` delimiter → None.
- Bad YAML → None.
- required_fields missing → None.
- extra_fields accepted and surfaced in result.
"""

import textwrap

import pytest

from lore.frontmatter import parse_frontmatter_doc, parse_frontmatter_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_text(extra_frontmatter: str = "") -> str:
    """Return a minimal valid markdown document with optional extra frontmatter."""
    return textwrap.dedent("""\
        ---
        id: doc-a
        title: Test Document
        summary: A test document
        {extra}
        ---
        Body text.
    """).format(extra=extra_frontmatter)


# ---------------------------------------------------------------------------
# Signature + happy path
# ---------------------------------------------------------------------------


def test_parse_frontmatter_text_returns_dict_for_valid_text():
    """Valid frontmatter text → dict with id/title/summary keys."""
    text = _make_text()
    result = parse_frontmatter_text(text)
    assert result is not None
    assert result["id"] == "doc-a"
    assert result["title"] == "Test Document"
    assert result["summary"] == "A test document"


def test_parse_frontmatter_text_stringifies_required_fields():
    """Required fields are coerced to str, matching parse_frontmatter_doc."""
    text = textwrap.dedent("""\
        ---
        id: 42
        title: 99
        summary: 100
        ---
        Body.
    """)
    result = parse_frontmatter_text(text)
    assert result is not None
    assert result["id"] == "42"
    assert result["title"] == "99"
    assert result["summary"] == "100"


def test_parse_frontmatter_text_no_path_key():
    """Result dict has no `path` key — that's filepath-only territory."""
    text = _make_text()
    result = parse_frontmatter_text(text)
    assert result is not None
    assert "path" not in result


# ---------------------------------------------------------------------------
# Parity with parse_frontmatter_doc
# ---------------------------------------------------------------------------


def test_parse_frontmatter_text_matches_doc_roundtrip(tmp_path):
    """Identical text → identical dict (modulo `path`) between text + doc helpers."""
    text = _make_text(extra_frontmatter="related:\n  - doc-b\n  - doc-c")
    filepath = tmp_path / "doc.md"
    filepath.write_text(text)

    text_result = parse_frontmatter_text(text, extra_fields=("related",))
    doc_result = parse_frontmatter_doc(filepath, extra_fields=("related",))

    assert text_result is not None
    assert doc_result is not None

    doc_copy = dict(doc_result)
    doc_copy.pop("path", None)
    assert text_result == doc_copy


def test_parse_frontmatter_text_matches_doc_roundtrip_default_required(tmp_path):
    """Default required_fields call produces identical content."""
    text = _make_text()
    filepath = tmp_path / "doc.md"
    filepath.write_text(text)

    text_result = parse_frontmatter_text(text)
    doc_result = parse_frontmatter_doc(filepath)

    assert text_result is not None
    assert doc_result is not None
    doc_copy = dict(doc_result)
    doc_copy.pop("path", None)
    assert text_result == doc_copy


# ---------------------------------------------------------------------------
# Failure modes — must return None
# ---------------------------------------------------------------------------


def test_parse_frontmatter_text_missing_delimiter_returns_none():
    """Text with no `---` delimiters → None (fewer than three parts)."""
    text = "id: doc-a\ntitle: T\nsummary: S\nBody.\n"
    assert parse_frontmatter_text(text) is None


def test_parse_frontmatter_text_single_delimiter_returns_none():
    """Text with only opening `---` (no closing) → None."""
    text = "---\nid: doc-a\ntitle: T\nsummary: S\nBody.\n"
    assert parse_frontmatter_text(text) is None


def test_parse_frontmatter_text_empty_string_returns_none():
    """Empty input → None."""
    assert parse_frontmatter_text("") is None


def test_parse_frontmatter_text_bad_yaml_returns_none():
    """Unparseable YAML between delimiters → None."""
    text = "---\nid: : :\ntitle: x\nsummary: y\n---\nBody.\n"
    assert parse_frontmatter_text(text) is None


def test_parse_frontmatter_text_non_mapping_returns_none():
    """Top-level YAML that isn't a dict → None."""
    text = "---\n- one\n- two\n---\nBody.\n"
    assert parse_frontmatter_text(text) is None


def test_parse_frontmatter_text_missing_required_field_returns_none():
    """Missing required field → None."""
    text = textwrap.dedent("""\
        ---
        id: doc-a
        title: T
        ---
        Body.
    """)
    # `summary` missing from defaults
    assert parse_frontmatter_text(text) is None


def test_parse_frontmatter_text_null_required_field_returns_none():
    """A required field present but null → None."""
    text = textwrap.dedent("""\
        ---
        id: doc-a
        title: T
        summary: null
        ---
        Body.
    """)
    assert parse_frontmatter_text(text) is None


# ---------------------------------------------------------------------------
# required_fields parameter
# ---------------------------------------------------------------------------


def test_parse_frontmatter_text_custom_required_fields():
    """Custom required_fields tuple replaces the default trio."""
    text = textwrap.dedent("""\
        ---
        name: knight-x
        role: pm
        ---
        Body.
    """)
    result = parse_frontmatter_text(text, required_fields=("name", "role"))
    assert result is not None
    assert result["name"] == "knight-x"
    assert result["role"] == "pm"


def test_parse_frontmatter_text_custom_required_fields_missing_returns_none():
    """Missing key from custom required_fields → None."""
    text = textwrap.dedent("""\
        ---
        name: knight-x
        ---
        Body.
    """)
    assert parse_frontmatter_text(text, required_fields=("name", "role")) is None


# ---------------------------------------------------------------------------
# extra_fields parameter
# ---------------------------------------------------------------------------


def test_parse_frontmatter_text_extra_fields_present():
    """extra_fields=("related",) returns the related list when present."""
    text = _make_text(extra_frontmatter="related:\n  - doc-b\n  - doc-c")
    result = parse_frontmatter_text(text, extra_fields=("related",))
    assert result is not None
    assert result["related"] == ["doc-b", "doc-c"]


def test_parse_frontmatter_text_extra_fields_absent_omitted():
    """extra_fields=("related",) omits the key when field is absent."""
    text = _make_text()  # no related field
    result = parse_frontmatter_text(text, extra_fields=("related",))
    assert result is not None
    assert "related" not in result


def test_parse_frontmatter_text_extra_fields_null_preserved():
    """extra_fields=("related",) keeps a None value when frontmatter sets null."""
    text = _make_text(extra_frontmatter="related: null")
    result = parse_frontmatter_text(text, extra_fields=("related",))
    assert result is not None
    assert "related" in result
    assert result["related"] is None


def test_parse_frontmatter_text_extra_fields_empty_list():
    """extra_fields=("related",) returns empty list when frontmatter sets []."""
    text = _make_text(extra_frontmatter="related: []")
    result = parse_frontmatter_text(text, extra_fields=("related",))
    assert result is not None
    assert result["related"] == []


def test_parse_frontmatter_text_extra_fields_default_unaffected():
    """Default extra_fields=() does NOT surface extra keys in result."""
    text = _make_text(extra_frontmatter="related:\n  - doc-b")
    result = parse_frontmatter_text(text)
    assert result is not None
    assert "related" not in result


# ---------------------------------------------------------------------------
# Keyword-only kwargs (matches spec signature: `*, required_fields=...`)
# ---------------------------------------------------------------------------


def test_parse_frontmatter_text_required_fields_is_keyword_only():
    """Per spec signature, required_fields and extra_fields are keyword-only."""
    text = _make_text()
    with pytest.raises(TypeError):
        parse_frontmatter_text(text, ("id", "title", "summary"))


# ---------------------------------------------------------------------------
# Internal helper — not exported from lore.api
# ---------------------------------------------------------------------------


def test_parse_frontmatter_text_not_in_lore_api_all():
    """G9 spec: helper stays internal — must NOT be in lore.api.__all__."""
    import lore.api as api

    assert "parse_frontmatter_text" not in api.__all__
