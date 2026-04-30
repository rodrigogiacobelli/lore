"""Glossary YAML loading and lookup.

Spec: glossary-us-001 (lore codex show glossary-us-001)
Workflow: conceptual-workflows-glossary

This module owns IO and matching for the glossary. Schema validation lives
in `lore.schemas`; CLI rendering lives in `lore.cli`. Keep it that way —
see `standards-single-responsibility`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml

from lore.models import GlossaryItem
from lore.paths import glossary_path
from lore.schemas import SchemaValidationError, validate_entity_file


_TOKEN_RE = re.compile(r"[^\w]+", re.UNICODE)


class GlossaryError(Exception):
    """Raised when the glossary file is unreadable or violates the schema."""


def scan_glossary(root: Path) -> list[GlossaryItem]:
    """Return the glossary items in source order, or [] if file missing.

    Raises GlossaryError on read error, malformed YAML, or schema violation.
    """
    path = glossary_path(root)
    if not path.exists():
        return []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise GlossaryError(str(e)) from e

    # validate_entity_file re-reads + re-parses + validates atomically and
    # raises SchemaValidationError for both yaml-parse and schema-rule failures
    # under the "glossary" raise-mode kind. We translate that into GlossaryError.
    try:
        validate_entity_file(str(path), "glossary")
    except SchemaValidationError as e:
        raise GlossaryError(str(e)) from e

    # Parse once for hydration. Validation already passed, so safe_load is safe.
    data = yaml.safe_load(text)
    return [GlossaryItem.from_dict(d) for d in data["items"]]


def _find_match(items: list[GlossaryItem], keyword: str) -> GlossaryItem | None:
    """Return the first item whose keyword casefold-equals ``keyword``."""
    needle = keyword.casefold()
    for item in items:
        if item.keyword.casefold() == needle:
            return item
    return None


def read_glossary_item(root: Path, keyword: str) -> GlossaryItem | None:
    """Look up an item by exact keyword (case-insensitive). Aliases NOT consulted (FR-7)."""
    return _find_match(scan_glossary(root), keyword)


def _item_haystacks(item: GlossaryItem) -> list[str]:
    """Casefolded text fields searched by ``search_glossary`` substring matching."""
    return [
        item.keyword.casefold(),
        item.definition.casefold(),
        *(a.casefold() for a in item.aliases),
        *(d.casefold() for d in item.do_not_use),
    ]


def search_glossary(root: Path, query: str) -> list[GlossaryItem]:
    """Return items containing ``query`` (case-insensitive substring) across
    keyword/aliases/do_not_use/definition. Result alphabetised by casefolded keyword."""
    needle = query.casefold()
    matched = [
        item
        for item in scan_glossary(root)
        if any(needle in h for h in _item_haystacks(item))
    ]
    matched.sort(key=lambda i: i.keyword.casefold())
    return matched


# ---------------------------------------------------------------------------
# US-004 — Auto-surface tokeniser, matcher, renderer.
# Spec: glossary-us-004
#
# The ``_normalise_tokens`` / ``_build_lookup`` / ``_scan_runs`` triple is the
# shared word-boundary matching primitive. ``match_glossary`` consumes it in
# canonical mode (US-004 auto-surface). US-005's ``find_deprecated_terms``
# (lore.health) reuses the same primitives in deprecated mode — keep them
# stable and free of caller-specific logic.
# ---------------------------------------------------------------------------


def _normalise_tokens(text: str) -> list[str]:
    """Split ``text`` on non-word runs, casefold, drop empties.

    Shared tokeniser for canonical auto-surface (US-004) and the deprecated-
    term health scan (US-005). Casefold + Unicode-aware ``\\W`` split — see
    standards-no-substring-in-prose.
    """
    return [t.casefold() for t in _TOKEN_RE.split(text) if t]


def _build_lookup(
    items: list[GlossaryItem],
    *,
    source: Literal["canonical", "deprecated"],
) -> dict[tuple[str, ...], tuple[GlossaryItem, str]]:
    """Map token-tuple → (item, source_tag) for word-boundary lookup.

    ``source="canonical"`` indexes keywords + aliases (FR-17 excludes
    do_not_use) and powers ``match_glossary``. ``source="deprecated"``
    indexes only do_not_use and powers the US-005 health scan.
    Source tags returned in the value: ``"keyword"``, ``"alias"``, or
    ``"do_not_use"`` — callers can reconstruct what triggered the match.
    """
    lookup: dict[tuple[str, ...], tuple[GlossaryItem, str]] = {}
    for item in items:
        if source == "canonical":
            key_tokens = tuple(_normalise_tokens(item.keyword))
            if key_tokens:
                lookup[key_tokens] = (item, "keyword")
            for alias in item.aliases:
                alias_tokens = tuple(_normalise_tokens(alias))
                if alias_tokens:
                    lookup[alias_tokens] = (item, "alias")
        else:
            for term in item.do_not_use:
                term_tokens = tuple(_normalise_tokens(term))
                if term_tokens:
                    lookup[term_tokens] = (item, "do_not_use")
    return lookup


def _iter_runs(
    tokens: list[str],
    lookup: dict[tuple[str, ...], tuple[GlossaryItem, str]],
):
    """Walk ``tokens`` left-to-right, yield ``(match_key, item, tag)`` per hit.

    Longest-match wins at each position; on a hit the cursor jumps past the
    matched run so a multi-word keyword does not also yield its single-word
    prefix. Yields one tuple per occurrence — callers apply their own
    deduplication. Empty ``lookup`` → no yields. Shared primitive for both
    the canonical auto-surface (``_scan_runs``) and the deprecated-term
    health scan (``find_deprecated_terms``).
    """
    if not lookup:
        return
    max_len = max(len(k) for k in lookup)
    i = 0
    n = len(tokens)
    while i < n:
        match_len = 0
        match_key: tuple[str, ...] | None = None
        for length in range(min(max_len, n - i), 0, -1):
            candidate = tuple(tokens[i : i + length])
            if candidate in lookup:
                match_len = length
                match_key = candidate
                break
        if match_key is not None:
            item, tag = lookup[match_key]
            yield match_key, item, tag
            i += match_len
        else:
            i += 1


def _scan_runs(
    tokens: list[str],
    lookup: dict[tuple[str, ...], tuple[GlossaryItem, str]],
) -> list[tuple[GlossaryItem, str]]:
    """Return one ``(item, tag)`` per distinct item appearing in ``tokens``.

    Set semantics per call: the same item is emitted at most once even if it
    occurs multiple times. Powers the canonical auto-surface scan.
    """
    seen: set[int] = set()
    out: list[tuple[GlossaryItem, str]] = []
    for _key, item, tag in _iter_runs(tokens, lookup):
        item_id = id(item)
        if item_id in seen:
            continue
        seen.add(item_id)
        out.append((item, tag))
    return out


def match_glossary(
    bodies: list[str],
    *,
    items: list[GlossaryItem] | None = None,
    root: Path | None = None,
) -> list[GlossaryItem]:
    """Return canonical glossary items whose keyword/aliases appear in ``bodies``.

    Alphabetised by casefolded keyword, deduplicated. ``do_not_use`` does
    NOT auto-surface (FR-17). Missing glossary file → []. Malformed →
    propagates ``GlossaryError``.
    """
    if items is None:
        if root is None:
            return []
        items = scan_glossary(root)
    if not items:
        return []
    lookup = _build_lookup(items, source="canonical")
    matched: dict[int, GlossaryItem] = {}
    for body in bodies:
        tokens = _normalise_tokens(body)
        for item, _tag in _scan_runs(tokens, lookup):
            matched[id(item)] = item
    return sorted(matched.values(), key=lambda i: i.keyword.casefold())


def find_deprecated_terms(
    bodies: dict[str, str],
    *,
    items: list[GlossaryItem] | None = None,
    root: Path | None = None,
) -> list[tuple[GlossaryItem, str, str]]:
    """Return ``(item, doc_id, matched_term)`` for each deprecated-term hit per body.

    Only ``do_not_use`` entries surface (FR-17). Reuses the shared tokeniser
    and lookup primitives. Sorted by ``(doc_id, matched_term)`` (FR-21).
    Missing glossary file → []. Empty bodies dict → [].
    """
    if items is None:
        if root is None:
            return []
        items = scan_glossary(root)
    if not items or not bodies:
        return []
    lookup = _build_lookup(items, source="deprecated")
    if not lookup:
        return []
    # Reverse-map the token-tuple keys to the original do_not_use string so
    # callers see the matched term in its source form (lowercase per fixture).
    term_by_tokens: dict[tuple[str, ...], str] = {}
    for item in items:
        for term in item.do_not_use:
            tokens = tuple(_normalise_tokens(term))
            if tokens and tokens not in term_by_tokens:
                term_by_tokens[tokens] = term
    out: list[tuple[GlossaryItem, str, str]] = [
        (item, doc_id, term_by_tokens[key])
        for doc_id, body in bodies.items()
        for key, item, _tag in _iter_runs(_normalise_tokens(body), lookup)
    ]
    out.sort(key=lambda t: (t[1], t[2]))
    return out


def _render_glossary_block(items: list[GlossaryItem]) -> str:
    """Render ``## Glossary`` block. Empty list → empty string."""
    if not items:
        return ""
    ordered = sorted(items, key=lambda i: i.keyword.casefold())
    paragraphs = [
        f"**{i.keyword}** — {' '.join(i.definition.split())}"
        for i in ordered
    ]
    return "\n## Glossary\n\n" + "\n\n".join(paragraphs) + "\n"
