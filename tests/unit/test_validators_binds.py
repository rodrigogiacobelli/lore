"""Unit tests for lore.validators.validate_binds_entry.

US-002 Red — schema-validation-us-002 (`lore impacts` feature).
Workflow: conceptual-workflows-impacts (lore codex show conceptual-workflows-impacts)

Defines the contract for the pure validator that enforces `binds:` entry
rules independently of the JSON-Schema YAML layer. Mirrors the shape of
`validate_group`: returns a non-None error string on bad input, `None`
on valid.

Every test MUST fail before US-002 Green lands. Import failure counts
as red — `validate_binds_entry` is not exported yet.
"""

from __future__ import annotations

import pytest

# Red: this import is expected to fail until US-002 Green lands.
from lore.validators import validate_binds_entry


# ---------------------------------------------------------------------------
# Rejection cases — non-None error string returned
# ---------------------------------------------------------------------------


def test_validate_binds_entry_rejects_non_string_int():
    """conceptual-workflows-impacts — Failure Modes: non-string item rejected."""
    result = validate_binds_entry(123)
    assert result is not None
    assert isinstance(result, str)
    assert len(result) > 0


def test_validate_binds_entry_rejects_non_string_none():
    """Non-string sentinel — None payload — must be rejected."""
    result = validate_binds_entry(None)
    assert result is not None
    assert isinstance(result, str)


def test_validate_binds_entry_rejects_non_string_list():
    """A nested list as an item must be rejected."""
    result = validate_binds_entry(["nested"])
    assert result is not None
    assert isinstance(result, str)


def test_validate_binds_entry_rejects_empty_string():
    """conceptual-workflows-impacts — Preconditions: minLength: 1 / non-empty."""
    result = validate_binds_entry("")
    assert result is not None
    assert isinstance(result, str)


def test_validate_binds_entry_rejects_leading_slash_etc_passwd():
    """conceptual-workflows-impacts — Step 1 path normalisation: absolute banned."""
    result = validate_binds_entry("/etc/passwd")
    assert result is not None
    assert isinstance(result, str)


def test_validate_binds_entry_rejects_leading_slash_other():
    """Any leading `/` is rejected, not just well-known paths."""
    result = validate_binds_entry("/abs/path/foo.py")
    assert result is not None


def test_validate_binds_entry_rejects_leading_dotdot():
    """conceptual-workflows-impacts — Failure Modes: leading `..` traversal banned."""
    result = validate_binds_entry("../up")
    assert result is not None
    assert isinstance(result, str)


def test_validate_binds_entry_rejects_leading_dotdot_with_path():
    """Leading `../` followed by a longer path is rejected."""
    result = validate_binds_entry("../up/foo.py")
    assert result is not None


def test_validate_binds_entry_rejects_embedded_dotdot():
    """conceptual-workflows-impacts — Failure Modes: embedded `..` segment banned."""
    result = validate_binds_entry("src/../foo")
    assert result is not None
    assert isinstance(result, str)


def test_validate_binds_entry_rejects_embedded_dotdot_deeper():
    """Embedded `..` mid-path with deeper trailing segments is rejected."""
    result = validate_binds_entry("src/lore/../../etc/passwd")
    assert result is not None


def test_validate_binds_entry_rejects_trailing_dotdot():
    """A trailing `/..` segment is also a traversal violation."""
    result = validate_binds_entry("src/..")
    assert result is not None


# ---------------------------------------------------------------------------
# Acceptance cases — returns None for valid bindings
# ---------------------------------------------------------------------------


def test_validate_binds_entry_accepts_literal_path():
    """conceptual-workflows-impacts — Token Classification: literal bindings valid."""
    assert validate_binds_entry("src/lore/cli.py") is None


def test_validate_binds_entry_accepts_recursive_glob():
    """conceptual-workflows-impacts — Step 3 'Match every binding': `**` glob valid."""
    assert validate_binds_entry("src/lore/**/*.py") is None


def test_validate_binds_entry_accepts_single_star_glob():
    """conceptual-workflows-impacts — Token Classification: `*` glob valid."""
    assert validate_binds_entry("tests/unit/test_*.py") is None


def test_validate_binds_entry_accepts_question_mark_glob():
    """`?` single-char glob is a valid binding."""
    assert validate_binds_entry("src/lore/?.py") is None


def test_validate_binds_entry_accepts_bracket_class_glob():
    """`[abc]` character-class glob is a valid binding."""
    assert validate_binds_entry("src/lore/[abc].py") is None


def test_validate_binds_entry_accepts_single_segment_filename():
    """A bare filename (no `/`) is a valid repo-relative binding."""
    assert validate_binds_entry("Makefile") is None


def test_validate_binds_entry_accepts_dotfile_not_traversal():
    """A leading `.` that is NOT `..` (e.g. `.lore/foo`) is valid — only `..` segments are banned."""
    assert validate_binds_entry(".lore/foo.yaml") is None


# ---------------------------------------------------------------------------
# Return-shape contract
# ---------------------------------------------------------------------------


def test_validate_binds_entry_return_type_is_str_or_none():
    """Mirrors `validate_group`: returns str on error, None on valid."""
    bad = validate_binds_entry("/abs")
    good = validate_binds_entry("src/lore/cli.py")
    assert isinstance(bad, str)
    assert good is None


# ---------------------------------------------------------------------------
# Dependency-inversion guard (standards-dependency-inversion)
# ---------------------------------------------------------------------------


def test_validators_module_has_no_lore_imports():
    """conceptual-workflows-impacts — validators.py keeps zero `lore.*` imports.

    Inspect the source text of `lore.validators` to ensure the new function
    is added without dragging `lore.paths` or any other lore.* dependency.
    """
    import inspect

    import lore.validators as validators_mod

    source = inspect.getsource(validators_mod)
    # Every `from lore...` or `import lore...` line is a violation here.
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("from lore") or stripped.startswith("import lore"):
            pytest.fail(
                f"lore.validators must not import from lore.*; offending line: {stripped!r}"
            )


