"""Unit tests for the `binds:` field on the codex-frontmatter schema.

US-001 + US-002 Red — schema cluster of the `lore impacts` feature.
Workflow: conceptual-workflows-impacts (lore codex show conceptual-workflows-impacts)

These tests pin the JSON-Schema layer in
``src/lore/schemas/codex-frontmatter.yaml`` to its declarative contract:

- US-001 acceptance: well-formed `binds:` arrays validate clean
  (literal paths, glob patterns, missing key, empty list).
- US-002 rejection: malformed entries fail with a message that names
  the `binds` path (non-string item, absolute path, leading / embedded
  `..` segments, empty string, duplicates).
- Regression: `additionalProperties: false` continues to reject
  unrelated top-level keys — the patch is purely additive.

Every test MUST fail until the schema patch is applied. Until then,
`validate_entity('codex-frontmatter', {..., 'binds': [...]})` flags
`binds:` as an unknown property under `additionalProperties: false`,
so the acceptance tests fail (issues list non-empty), and the
rejection tests for `binds`-shape rules (uniqueItems, minLength,
pattern) also fail because the schema does not yet enforce them.
"""

from __future__ import annotations

from lore.schemas import SchemaIssue, validate_entity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base() -> dict:
    """Minimal valid codex-frontmatter dict — required keys only."""
    return {"id": "x", "title": "X", "summary": "S"}


def _validate(data: dict) -> list[SchemaIssue]:
    return validate_entity("codex-frontmatter", data)


def _issue_paths(issues: list[SchemaIssue]) -> list[str]:
    return [i.pointer for i in issues]


def _mentions_binds(issues: list[SchemaIssue]) -> bool:
    """Return True if any issue's pointer or message references `binds`."""
    return any(
        "binds" in i.pointer or "binds" in i.message for i in issues
    )


def _non_additionalproperties_issues(issues: list[SchemaIssue]) -> list[SchemaIssue]:
    """Drop `additionalProperties` issues — they fire today for `binds:` itself
    because the schema does not yet declare it. Rejection tests must show
    that the NEW rules (pattern / minLength / uniqueItems / items.type) fire
    on malformed items, independent of `additionalProperties`.
    """
    return [i for i in issues if i.rule != "additionalProperties"]


# ===========================================================================
# US-001 Acceptance — well-formed `binds:` passes
# ===========================================================================


class TestSchemaAcceptsBinds:
    """US-001 unit scenarios: well-formed values pass schema validation."""

    def test_accepts_single_literal_path_binding(self):
        """conceptual-workflows-impacts — Step 2 codex-seed reads bindings as-is."""
        data = _base() | {"binds": ["src/lore/cli.py"]}
        assert _validate(data) == []

    def test_accepts_multiple_literal_path_bindings(self):
        """Scenario 1: literal paths from US-001."""
        data = _base() | {"binds": ["src/lore/cli.py", "src/lore/impacts.py"]}
        assert _validate(data) == []

    def test_accepts_recursive_glob_binding(self):
        """conceptual-workflows-impacts — Token Classification: `**` glob valid."""
        data = _base() | {"binds": ["src/lore/**/*.py"]}
        assert _validate(data) == []

    def test_accepts_mixed_glob_and_literal_bindings(self):
        """Scenario 2: mixed glob shapes from US-001 pass."""
        data = _base() | {
            "binds": [
                "src/lore/**/*.py",
                "tests/unit/test_*.py",
                "src/lore/?.py",
            ]
        }
        assert _validate(data) == []

    def test_accepts_empty_binds_list(self):
        """Scenario 4: `binds: []` is accepted (FR-4 empty == missing)."""
        data = _base() | {"binds": []}
        assert _validate(data) == []


# ===========================================================================
# US-001 Regression — additive patch keeps additionalProperties: false intact
# ===========================================================================


class TestSchemaAdditivePatchRegression:
    """US-001 unit scenario 5: schema preserves `additionalProperties: false`."""

    def test_unknown_top_level_key_alongside_valid_binds_still_rejected(self):
        """Unknown key beside a valid `binds:` does not get a free pass.

        After Green: `binds:` is a recognized property AND `foo` is still
        flagged. Today: `foo` fires AND `binds:` also fires — the
        additive contract is violated, so an issue mentioning `foo` AND
        no issue mentioning `binds` must hold. That stricter shape is
        what Green delivers.
        """
        data = _base() | {"binds": ["src/lore/cli.py"], "foo": "bar"}
        issues = _validate(data)
        foo_issues = [
            i for i in issues
            if i.rule == "additionalProperties" and "foo" in i.message
        ]
        assert foo_issues, "expected `foo` to still be flagged after patch"
        # The additive contract: `binds:` itself must NOT show up as a
        # violation pointer once it is a recognized property.
        assert not any("binds" in i.pointer for i in issues), (
            f"binds: must be recognized; got issues for binds: "
            f"{[i for i in issues if 'binds' in i.pointer]}"
        )


# ===========================================================================
# US-002 Rejection — JSON-Schema layer catches malformed entries
# ===========================================================================


class TestSchemaRejectsBinds:
    """US-002 unit scenarios: malformed entries fail with `binds`-pointing issues."""

    def test_rejects_non_string_item_int(self):
        """conceptual-workflows-impacts — items.type: string.

        After Green: the violation must fire on the item shape (e.g. `type`),
        NOT only because `additionalProperties: false` rejects `binds:`
        wholesale. Strip additionalProperties-rule noise before asserting.
        """
        data = _base() | {"binds": [123]}
        issues = _non_additionalproperties_issues(_validate(data))
        assert issues, "expected items.type rule (or similar) to fire on int item"
        assert any("binds" in i.pointer for i in issues)

    def test_rejects_non_string_item_null(self):
        """A null item also violates items.type: string."""
        data = _base() | {"binds": [None]}
        issues = _non_additionalproperties_issues(_validate(data))
        assert issues
        assert any("binds" in i.pointer for i in issues)

    def test_rejects_absolute_path(self):
        """conceptual-workflows-impacts — NFR-Security: leading `/` banned.

        Must fire on a pattern/`not` rule applied to the item, not on
        `additionalProperties` against the `binds:` key itself.
        """
        data = _base() | {"binds": ["/etc/passwd"]}
        issues = _non_additionalproperties_issues(_validate(data))
        assert issues, "expected pattern/not rule to reject absolute path"
        assert any("binds" in i.pointer for i in issues)

    def test_rejects_absolute_path_arbitrary(self):
        """Any leading `/` (not only /etc/passwd) is rejected."""
        data = _base() | {"binds": ["/abs"]}
        issues = _non_additionalproperties_issues(_validate(data))
        assert issues
        assert any("binds" in i.pointer for i in issues)

    def test_rejects_leading_dotdot(self):
        """conceptual-workflows-impacts — Failure Modes: leading `..` banned."""
        data = _base() | {"binds": ["../foo"]}
        issues = _non_additionalproperties_issues(_validate(data))
        assert issues
        assert any("binds" in i.pointer for i in issues)

    def test_rejects_leading_dotdot_with_extension(self):
        """Leading `../up/foo.py` (Scenario 3 wire form) is rejected."""
        data = _base() | {"binds": ["../up/foo.py"]}
        issues = _non_additionalproperties_issues(_validate(data))
        assert issues
        assert any("binds" in i.pointer for i in issues)

    def test_rejects_embedded_dotdot_segment(self):
        """conceptual-workflows-impacts — Failure Modes: ANY `..` segment banned."""
        data = _base() | {"binds": ["src/../x"]}
        issues = _non_additionalproperties_issues(_validate(data))
        assert issues
        assert any("binds" in i.pointer for i in issues)

    def test_rejects_embedded_dotdot_with_etc_passwd(self):
        """`src/../etc/passwd` (Scenario 4 wire form) is rejected."""
        data = _base() | {"binds": ["src/../etc/passwd"]}
        issues = _non_additionalproperties_issues(_validate(data))
        assert issues
        assert any("binds" in i.pointer for i in issues)

    def test_rejects_empty_string_item(self):
        """conceptual-workflows-impacts — Preconditions: minLength: 1."""
        data = _base() | {"binds": [""]}
        issues = _validate(data)
        # The minLength rule specifically must fire — not only the
        # additionalProperties blanket rejection.
        assert any(i.rule == "minLength" for i in issues), (
            f"expected minLength rule, got {[i.rule for i in issues]}"
        )

    def test_rejects_duplicate_items(self):
        """conceptual-workflows-impacts — Preconditions: uniqueItems."""
        data = _base() | {"binds": ["src/lore/cli.py", "src/lore/cli.py"]}
        issues = _validate(data)
        assert any(i.rule == "uniqueItems" for i in issues), (
            f"expected uniqueItems rule, got {[i.rule for i in issues]}"
        )


# ===========================================================================
# Top-level shape — binds must be an array
# ===========================================================================


class TestSchemaBindsShape:
    """The shape of `binds:` itself is an array — not a string, not a mapping."""

    def test_rejects_string_value_instead_of_array(self):
        """`binds: src/lore/cli.py` (scalar) is rejected — must be array.

        Must fire a `type` rule on `/binds`, not only the
        `additionalProperties` blanket rejection that exists today.
        """
        data = _base() | {"binds": "src/lore/cli.py"}
        issues = _non_additionalproperties_issues(_validate(data))
        assert issues, "expected type-rule rejection of scalar binds:"
        assert any(i.pointer == "/binds" or i.pointer.startswith("/binds") for i in issues)

    def test_rejects_mapping_value_instead_of_array(self):
        """`binds: {a: b}` is rejected — must be array."""
        data = _base() | {"binds": {"a": "b"}}
        issues = _non_additionalproperties_issues(_validate(data))
        assert issues
        assert any(i.pointer == "/binds" or i.pointer.startswith("/binds") for i in issues)
