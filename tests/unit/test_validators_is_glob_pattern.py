"""Unit tests for `lore.validators.is_glob_pattern` (US-004).

Workflow: conceptual-workflows-impacts.
Tech Spec: lore-impacts-tech-spec § "Exact-vs-glob dedup".

`is_glob_pattern(s) -> bool` is a shared helper used by both:
  - the codex-seed JSON renderer (FR-12 `kind` classification), and
  - the path-seed exact/glob dedup (FR-9, sibling story).

Rule: returns True iff any of `*`, `?`, `[` appears in the string.
Empty string returns False.

Lives in its own file rather than `test_validators_binds.py` so that
the import failure (Red phase) does not block collection of the
already-green US-002 tests in that file.
"""

from __future__ import annotations

# Red: this import fails until US-004 Green adds `is_glob_pattern` to
# `lore/validators.py`. Wrapped in try/except so collection succeeds and
# the surrounding test suite is not blocked — matches the pattern used
# by other red-phase test files (see tests/unit/test_knight.py). The
# tests below still fail at run time (calling None raises TypeError).
try:
    from lore.validators import is_glob_pattern  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover — red phase, helper not implemented yet
    is_glob_pattern = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# True cases — any of *, ?, [ makes the string a glob
# ---------------------------------------------------------------------------


def test_is_glob_pattern_true_for_star():
    """conceptual-workflows-impacts — Step 3 'Match every binding': `*` is glob."""
    assert is_glob_pattern("foo/*.py") is True


def test_is_glob_pattern_true_for_question_mark():
    """conceptual-workflows-impacts — Step 3: `?` glob char."""
    assert is_glob_pattern("foo?.py") is True


def test_is_glob_pattern_true_for_bracket():
    """conceptual-workflows-impacts — Step 3: `[` character class is a glob."""
    assert is_glob_pattern("foo[ab].py") is True


def test_is_glob_pattern_true_for_double_star():
    """conceptual-workflows-impacts — Step 3: `**` recursive glob."""
    assert is_glob_pattern("foo/**/*.py") is True


def test_is_glob_pattern_true_for_unmatched_bracket():
    """Tech Spec exact-vs-glob: `[` alone triggers glob classification (broad)."""
    assert is_glob_pattern("foo[bar") is True


# ---------------------------------------------------------------------------
# False cases — literal paths and the empty string
# ---------------------------------------------------------------------------


def test_is_glob_pattern_false_for_simple_filename():
    """conceptual-workflows-impacts — Step 3: literal path → exact equality, not glob."""
    assert is_glob_pattern("foo.py") is False


def test_is_glob_pattern_false_for_nested_literal_path():
    """A multi-segment literal path is not a glob."""
    assert is_glob_pattern("src/lore/cli.py") is False


def test_is_glob_pattern_false_for_empty_string():
    """conceptual-workflows-impacts — empty string is not a glob.

    The validator banned empty strings upstream, but the helper must still
    return False so downstream callers can rely on it without raising.
    """
    assert is_glob_pattern("") is False


# ---------------------------------------------------------------------------
# Return-shape contract
# ---------------------------------------------------------------------------


def test_is_glob_pattern_return_type_is_bool():
    """`is_glob_pattern` must return a real bool — not a truthy str/int."""
    assert isinstance(is_glob_pattern("foo/*.py"), bool)
    assert isinstance(is_glob_pattern("foo.py"), bool)
