"""Unit tests for glossary item CRUD — create/update/delete.

Spec: .lore/codex/transient/glossary-crud-spec.md
Decisions: comments preserved across writes; keyword is the identity (no
rename via update); writes raise ValueError if glossary.yaml missing.
"""

from __future__ import annotations

import pytest
import yaml

from lore.glossary import (
    create_glossary_item,
    delete_glossary_item,
    read_glossary_item,
    scan_glossary,
    update_glossary_item,
)


GLOSSARY_HEADER = (
    "# Project glossary — see `lore codex show conceptual-entities-glossary`.\n"
    "# Before adding a term, run: `lore artifact show glossary-design`.\n"
    "# Auto-surfaced on `lore codex show`. Toggle via .lore/config.toml.\n"
)


SEED_YAML = GLOSSARY_HEADER + (
    "items:\n"
    "  - keyword: Constable\n"
    "    definition: Mission type for orchestrator-handled chores.\n"
    "    aliases:\n"
    "      - constable mission\n"
    "      - chore mission\n"
)


def _write_glossary(root, content=SEED_YAML):
    target = root / ".lore" / "codex" / "glossary.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# Spec §7 — six unit tests
# ---------------------------------------------------------------------------


def test_create_appends_item_returns_envelope(tmp_path):
    _write_glossary(tmp_path)
    result = create_glossary_item(
        tmp_path,
        "Quest",
        "A body of work tracked in lore.",
    )
    assert result == {"keyword": "Quest", "filename": "glossary.yaml"}

    items = scan_glossary(tmp_path)
    keywords = [i.keyword for i in items]
    assert keywords == ["Constable", "Quest"]  # append-at-end order preserved
    quest = items[1]
    assert quest.definition == "A body of work tracked in lore."
    assert quest.aliases == ()
    assert quest.do_not_use == ()


def test_create_rejects_duplicate_keyword_case_insensitive(tmp_path):
    _write_glossary(tmp_path)
    with pytest.raises(ValueError, match="already exists"):
        create_glossary_item(tmp_path, "constable", "Lowercase clash.")


def test_create_rejects_invalid_keyword_format(tmp_path):
    _write_glossary(tmp_path)

    with pytest.raises(ValueError, match="1-80"):
        create_glossary_item(tmp_path, "   ", "Empty keyword.")

    with pytest.raises(ValueError, match="1-80"):
        create_glossary_item(tmp_path, "x" * 81, "Too long.")

    with pytest.raises(ValueError, match="1-80"):
        create_glossary_item(tmp_path, "bad\nkeyword", "Line break.")


def test_update_only_definition_preserves_aliases(tmp_path):
    _write_glossary(tmp_path)
    result = update_glossary_item(
        tmp_path,
        "Constable",
        definition="New definition.",
    )
    assert result == {"keyword": "Constable", "filename": "glossary.yaml"}

    item = read_glossary_item(tmp_path, "Constable")
    assert item.definition == "New definition."
    # aliases NOT touched (None means leave-alone)
    assert item.aliases == ("constable mission", "chore mission")


def test_update_empty_list_clears_field_and_removes_yaml_key(tmp_path):
    path = _write_glossary(tmp_path)
    update_glossary_item(tmp_path, "Constable", aliases=[])

    item = read_glossary_item(tmp_path, "Constable")
    assert item.aliases == ()

    # The YAML key 'aliases:' must be omitted entirely (template rule).
    raw = path.read_text(encoding="utf-8")
    assert "aliases" not in raw


def test_update_with_all_none_raises_value_error(tmp_path):
    _write_glossary(tmp_path)
    with pytest.raises(ValueError, match="at least one field"):
        update_glossary_item(tmp_path, "Constable")


def test_delete_then_redelete_returns_same_envelope_no_already_deleted_key(tmp_path):
    _write_glossary(tmp_path)
    first = delete_glossary_item(tmp_path, "Constable")
    second = delete_glossary_item(tmp_path, "Constable")

    for env in (first, second):
        assert env["keyword"] == "Constable"
        assert env["deleted"] is True
        assert "deleted_at" in env and isinstance(env["deleted_at"], str)
        assert "already_deleted" not in env

    # Item is gone.
    assert read_glossary_item(tmp_path, "Constable") is None


# ---------------------------------------------------------------------------
# Decision-driven tests (Q1, Q2, Q6)
# ---------------------------------------------------------------------------


def test_create_preserves_leading_comments(tmp_path):
    path = _write_glossary(tmp_path)
    create_glossary_item(tmp_path, "Quest", "A body of work.")
    raw = path.read_text(encoding="utf-8")
    # All three header comments survive the round-trip.
    assert "# Project glossary" in raw
    assert "# Before adding a term" in raw
    assert "# Auto-surfaced on" in raw


def test_update_preserves_leading_comments(tmp_path):
    path = _write_glossary(tmp_path)
    update_glossary_item(tmp_path, "Constable", definition="Updated.")
    raw = path.read_text(encoding="utf-8")
    assert "# Project glossary" in raw
    assert "# Before adding a term" in raw
    assert "# Auto-surfaced on" in raw


def test_delete_preserves_leading_comments(tmp_path):
    path = _write_glossary(tmp_path)
    delete_glossary_item(tmp_path, "Constable")
    raw = path.read_text(encoding="utf-8")
    assert "# Project glossary" in raw
    assert "# Before adding a term" in raw
    assert "# Auto-surfaced on" in raw


def test_update_does_not_support_renaming_keyword(tmp_path):
    """Keyword is the identity. No `new_keyword` kwarg. Lookup of changed casing
    still resolves to the stored item (case-insensitive), but the stored casing
    is preserved (i.e. no rename happens by passing a different-cased keyword)."""
    _write_glossary(tmp_path)
    # Sanity: update_glossary_item should NOT accept a rename kwarg.
    with pytest.raises(TypeError):
        update_glossary_item(  # type: ignore[call-arg]
            tmp_path, "Constable", new_keyword="Marshal", definition="x"
        )

    # Lookup with different casing finds the item; stored casing unchanged.
    update_glossary_item(tmp_path, "constable", definition="case-insensitive lookup.")
    item = read_glossary_item(tmp_path, "Constable")
    assert item is not None
    assert item.keyword == "Constable"  # source casing preserved
    assert item.definition == "case-insensitive lookup."


def test_create_raises_when_glossary_file_missing(tmp_path):
    # No glossary.yaml ever created.
    with pytest.raises(ValueError, match="Glossary file not found"):
        create_glossary_item(tmp_path, "Quest", "A body of work.")


def test_update_raises_when_glossary_file_missing(tmp_path):
    with pytest.raises(ValueError, match="Glossary file not found"):
        update_glossary_item(tmp_path, "Quest", definition="x")


def test_delete_raises_when_glossary_file_missing(tmp_path):
    with pytest.raises(ValueError, match="Glossary file not found"):
        delete_glossary_item(tmp_path, "Quest")


# ---------------------------------------------------------------------------
# Additional coverage (definition + aliases validation, idempotent delete miss)
# ---------------------------------------------------------------------------


def test_create_rejects_empty_definition(tmp_path):
    _write_glossary(tmp_path)
    with pytest.raises(ValueError, match="1-1000"):
        create_glossary_item(tmp_path, "Quest", "   ")


def test_create_rejects_aliases_with_line_breaks(tmp_path):
    _write_glossary(tmp_path)
    with pytest.raises(ValueError, match="aliases/do_not_use"):
        create_glossary_item(
            tmp_path, "Quest", "def", aliases=["good", "bad\nalias"]
        )


def test_create_rejects_duplicate_aliases_in_same_list(tmp_path):
    _write_glossary(tmp_path)
    with pytest.raises(ValueError, match="aliases/do_not_use"):
        create_glossary_item(
            tmp_path, "Quest", "def", aliases=["dup", "dup"]
        )


def test_delete_missing_keyword_is_idempotent(tmp_path):
    _write_glossary(tmp_path)
    # Deleting a non-existent keyword is NOT an error (spec §3 delete).
    result = delete_glossary_item(tmp_path, "Nonexistent")
    assert result["keyword"] == "Nonexistent"
    assert result["deleted"] is True
    assert "already_deleted" not in result


def test_create_preserves_existing_file_order_when_appending(tmp_path):
    raw = GLOSSARY_HEADER + (
        "items:\n"
        "  - keyword: Zebra\n"
        "    definition: Last alphabetically but first in source.\n"
        "  - keyword: Apple\n"
        "    definition: First alphabetically but second in source.\n"
    )
    _write_glossary(tmp_path, raw)
    create_glossary_item(tmp_path, "Mango", "Inserted at end.")
    items = scan_glossary(tmp_path)
    assert [i.keyword for i in items] == ["Zebra", "Apple", "Mango"]


def test_update_clears_do_not_use_with_empty_list(tmp_path):
    raw = GLOSSARY_HEADER + (
        "items:\n"
        "  - keyword: Quest\n"
        "    definition: A body of work.\n"
        "    do_not_use:\n"
        "      - epic\n"
    )
    path = _write_glossary(tmp_path, raw)
    update_glossary_item(tmp_path, "Quest", do_not_use=[])
    item = read_glossary_item(tmp_path, "Quest")
    assert item.do_not_use == ()
    assert "do_not_use" not in path.read_text(encoding="utf-8")


def test_round_trip_parseable_yaml(tmp_path):
    """After a write the file remains schema-valid (items: list at top level)."""
    path = _write_glossary(tmp_path)
    create_glossary_item(tmp_path, "Quest", "A body of work.")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert "items" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 2
