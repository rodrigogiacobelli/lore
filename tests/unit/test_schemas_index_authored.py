"""Unit tests for the packaged ``lore://schemas/index-authored`` schema.

Spec: codex-index-spec (lore codex show codex-index-spec) — Part 2 "Data and
Storage", the Part 4 schema unit row, Part 5 unit F3.

The schema is the single authoritative contract for `.lore/index/authored.yaml`
(tech-arch-schemas), so every rule it states is asserted here against in-memory
documents. No test reads a seeded default file or asserts on one's field values
(decisions-006-no-seed-content-tests).
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml

from lore.schemas import (
    SchemaValidationError,
    load_schema,
    validate_entity,
    validate_entity_file,
)

KIND = "index-authored"

REQUIRED_ENTRY_KEYS = ("slug", "name", "summary", "authored_against")


def _entry(**overrides: Any) -> dict[str, Any]:
    """A well-formed authored entry, with any field replaced or removed."""
    entry: dict[str, Any] = {
        "slug": "alpha-theme",
        "name": "Alpha Theme",
        "summary": "Everything alpha, and the documents that explain it.",
        "authored_against": "a" * 64,
    }
    entry.update(overrides)
    return entry


def _document(
    entries: dict[str, Any] | None = None, **overrides: Any
) -> dict[str, Any]:
    """A well-formed authored file, keyed by hub, with top-level overrides."""
    document: dict[str, Any] = {
        "version": 1,
        "entries": {"alpha-hub": _entry()} if entries is None else entries,
    }
    document.update(overrides)
    return document


def _keyed(entry: dict[str, Any], hub: str = "alpha-hub") -> dict[str, Any]:
    """A document holding exactly one entry, keyed by *hub*."""
    return _document({hub: entry})


def _entry_missing(key: str) -> dict[str, Any]:
    """An entry with one of its four required keys removed."""
    entry = _entry()
    del entry[key]
    return entry


# ---------------------------------------------------------------------------
# The packaged resource.
# ---------------------------------------------------------------------------


def test_load_schema_resolves_the_index_authored_kind():
    schema = load_schema(KIND)

    assert isinstance(schema, dict)
    assert schema["$id"] == f"lore://schemas/{KIND}"


def test_the_schema_is_draft_2020_12():
    draft = "https://json-schema.org/draft/2020-12/schema"

    assert load_schema(KIND)["$schema"] == draft


# ---------------------------------------------------------------------------
# The clean case.
# ---------------------------------------------------------------------------


def test_a_minimal_valid_document_validates_clean():
    assert validate_entity(KIND, _document()) == []


def test_several_entries_keyed_by_hub_validate_clean():
    document = _document(
        {
            "alpha-hub": _entry(),
            "beta-hub": _entry(slug="beta-theme", name="Beta Theme"),
        }
    )

    assert validate_entity(KIND, document) == []


# ---------------------------------------------------------------------------
# Every rejection the schema owes.
# ---------------------------------------------------------------------------


REJECTED: list[tuple[str, dict[str, Any]]] = [
    ("missing version", {"entries": {"alpha-hub": _entry()}}),
    ("missing entries", {"version": 1}),
    ("version is not 1", _document(version=2)),
    ("unknown top-level key", _document(schema_version=1)),
    *(
        (f"entry missing {key}", _keyed(_entry_missing(key)))
        for key in REQUIRED_ENTRY_KEYS
    ),
    ("unknown key inside an entry", _keyed(_entry(digest="x"))),
    ("slug with an uppercase letter", _keyed(_entry(slug="Alpha"))),
    ("slug with a leading hyphen", _keyed(_entry(slug="-alpha"))),
    ("name containing a newline", _keyed(_entry(name="Alpha\nTheme"))),
    ("authored_against too short", _keyed(_entry(authored_against="a" * 63))),
    ("authored_against not hex", _keyed(_entry(authored_against="g" + "a" * 63))),
    ("entry key containing a slash", _keyed(_entry(), hub="alpha/hub")),
]


@pytest.mark.parametrize(
    "document", [case for _, case in REJECTED], ids=[name for name, _ in REJECTED]
)
def test_an_invalid_document_produces_at_least_one_issue(document):
    assert validate_entity(KIND, document) != []


# ---------------------------------------------------------------------------
# Registration: a full-YAML kind that raises rather than returning issues.
# ---------------------------------------------------------------------------


def test_a_valid_file_validates_clean_through_validate_entity_file(tmp_path):
    path = tmp_path / "authored.yaml"
    path.write_text(yaml.safe_dump(_document()), encoding="utf-8")

    assert validate_entity_file(str(path), KIND) == []


def test_broken_yaml_raises_schema_validation_error(tmp_path):
    path = tmp_path / "authored.yaml"
    path.write_text("entries: [\n", encoding="utf-8")

    with pytest.raises(SchemaValidationError):
        validate_entity_file(str(path), KIND)


def test_a_schema_violation_in_a_file_raises_schema_validation_error(tmp_path):
    path = tmp_path / "authored.yaml"
    path.write_text(yaml.safe_dump(_document(version=2)), encoding="utf-8")

    with pytest.raises(SchemaValidationError):
        validate_entity_file(str(path), KIND)
