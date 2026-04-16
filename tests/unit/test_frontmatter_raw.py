"""Unit tests for lore.frontmatter.parse_frontmatter_raw (US-003).

Spec: schema-validation-us-003 (lore codex show schema-validation-us-003).

The helper must return the full raw frontmatter mapping — every key on disk,
none dropped — plus a distinct error signal for yaml-parse vs missing
frontmatter, enabling schema-validation FR-10/FR-11 enforcement.
"""

from lore.frontmatter import parse_frontmatter_doc, parse_frontmatter_raw


def test_happy_path_preserves_every_key_including_unknown(tmp_path):
    # conceptual-workflows-validators — preserve unknown keys so schema can flag them
    p = tmp_path / "k.md"
    p.write_text(
        "---\nid: pm\ntitle: PM\nsummary: s\nstability: experimental\n---\nbody\n"
    )
    data, err = parse_frontmatter_raw(str(p))
    assert err is None
    assert data == {
        "id": "pm",
        "title": "PM",
        "summary": "s",
        "stability": "experimental",
    }


def test_no_leading_delimiter_returns_none_none(tmp_path):
    # conceptual-workflows-health — FR-11 missing-frontmatter branch signal
    p = tmp_path / "plain.md"
    p.write_text("hello world\n")
    assert parse_frontmatter_raw(str(p)) == (None, None)


def test_empty_file_returns_none_none(tmp_path):
    # conceptual-workflows-health — empty artifact file
    p = tmp_path / "empty.md"
    p.write_text("")
    assert parse_frontmatter_raw(str(p)) == (None, None)


def test_unparseable_yaml_returns_none_and_error_string(tmp_path):
    # conceptual-workflows-health — FR-10 yaml-parse branch signal
    p = tmp_path / "broken.md"
    p.write_text("---\nid: : :\n---\n")
    data, err = parse_frontmatter_raw(str(p))
    assert data is None
    assert isinstance(err, str) and err


def test_frontmatter_is_not_a_mapping(tmp_path):
    # conceptual-workflows-validators — non-dict frontmatter rejected with explicit string
    p = tmp_path / "list.md"
    p.write_text("---\n- a\n- b\n---\n")
    assert parse_frontmatter_raw(str(p)) == (None, "frontmatter is not a mapping")


def test_existing_parse_frontmatter_doc_behaviour_unchanged(tmp_path):
    # conceptual-workflows-validators — existing callers must not shift
    p = tmp_path / "k.md"
    p.write_text("---\nid: pm\ntitle: PM\nsummary: s\n---\nbody\n")
    before = parse_frontmatter_doc(p)
    # Call raw helper in between, then confirm doc parser still identical
    parse_frontmatter_raw(str(p))
    assert parse_frontmatter_doc(p) == before


def test_source_order_preserved(tmp_path):
    # conceptual-workflows-health — deterministic error pointers rely on insertion order
    p = tmp_path / "k.md"
    p.write_text("---\ntitle: T\nid: pm\nsummary: s\n---\n")
    data, _ = parse_frontmatter_raw(str(p))
    assert list(data.keys()) == ["title", "id", "summary"]
