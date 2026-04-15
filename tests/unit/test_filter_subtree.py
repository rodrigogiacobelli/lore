"""Unit tests for lore.paths.group_matches_filter — slash-delimited segment-prefix grammar.

These tests are RED-first for US-008: they describe the desired segment-prefix
behaviour after the grammar migration. Every test MUST fail against the current
hyphen/exact implementation.

Spec: group-param-us-008 (lore codex show group-param-us-008)
Anchor: conceptual-workflows-filter-list
"""

from lore.paths import group_matches_filter


# ---------------------------------------------------------------------------
# Root inclusion — empty group is always matched regardless of tokens
# ---------------------------------------------------------------------------


def test_root_group_always_matches():
    """Empty string group matches any filter (root inclusion rule, unchanged)."""
    assert group_matches_filter("", ["a/b"]) is True


def test_root_group_matches_bare_token():
    """Empty string group still matches a bare single-segment filter."""
    assert group_matches_filter("", ["seo-analysis"]) is True


# ---------------------------------------------------------------------------
# Exact and segment-prefix matches
# ---------------------------------------------------------------------------


def test_exact_match_single_segment():
    """Group equals token, single segment."""
    assert group_matches_filter("a", ["a"]) is True


def test_exact_match_multi_segment():
    """Group equals token with multiple slash-joined segments."""
    assert group_matches_filter("a/b", ["a/b"]) is True


def test_proper_prefix_match_one_extra_segment():
    """Group has one more trailing segment than the token."""
    assert group_matches_filter("a/b/c", ["a/b"]) is True


def test_proper_prefix_match_deeper():
    """Group has several more trailing segments than the token."""
    assert group_matches_filter("seo-analysis/keyword-analysers/ranker", ["seo-analysis"]) is True


# ---------------------------------------------------------------------------
# Non-matches
# ---------------------------------------------------------------------------


def test_non_prefix_rejected_sibling_segment():
    """Different final segment at the same depth does NOT match."""
    assert group_matches_filter("a/b", ["a/c"]) is False


def test_non_prefix_rejected_different_root():
    """Different root segment does NOT match."""
    assert group_matches_filter("other/foo", ["seo-analysis"]) is False


def test_bare_substring_rejected():
    """Bare string prefix of a segment is NOT a match — must be a whole segment."""
    assert group_matches_filter("technical/api", ["tech"]) is False


def test_bare_substring_rejected_single_segment():
    """Single-segment group rejects partial-string token."""
    assert group_matches_filter("technical", ["tech"]) is False


def test_token_longer_than_group_rejected():
    """Token with more segments than the group cannot be a prefix."""
    assert group_matches_filter("a", ["a/b"]) is False


# ---------------------------------------------------------------------------
# Leading / trailing slash stripping on tokens
# ---------------------------------------------------------------------------


def test_trailing_slash_token_stripped():
    """Trailing slash on the filter token is silently stripped."""
    assert group_matches_filter("a/b", ["a/b/"]) is True


def test_leading_slash_token_stripped():
    """Leading slash on the filter token is silently stripped."""
    assert group_matches_filter("a/b", ["/a/b"]) is True


def test_leading_and_trailing_slash_token_stripped():
    """Both leading and trailing slashes on token are stripped."""
    assert group_matches_filter("a/b/c", ["/a/b/"]) is True


# ---------------------------------------------------------------------------
# Multi-token OR semantics
# ---------------------------------------------------------------------------


def test_multi_token_or_second_matches():
    """Any token match wins — second token is the matching one."""
    assert group_matches_filter("a/b", ["z", "a"]) is True


def test_multi_token_or_none_match():
    """No token matches → False."""
    assert group_matches_filter("a/b", ["z", "y/x"]) is False


# ---------------------------------------------------------------------------
# Hyphen preservation — hyphens are part of a segment, not a delimiter
# ---------------------------------------------------------------------------


def test_hyphen_in_segment_preserved_exact():
    """Hyphens inside a segment are part of that segment (exact match)."""
    assert group_matches_filter("a-b/c", ["a-b"]) is True


def test_hyphen_in_segment_not_split_by_dash():
    """A bare 'a' token does NOT match a group whose first segment is 'a-b'."""
    assert group_matches_filter("a-b/c", ["a"]) is False


def test_hyphen_delimited_legacy_token_rejected():
    """Legacy hyphen-joined token ('default-codex') does NOT match nested group 'default/codex'."""
    assert group_matches_filter("default/codex", ["default-codex"]) is False
