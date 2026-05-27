"""Glossary YAML loading and lookup.

Spec: glossary-us-001 (lore codex show glossary-us-001)
Workflow: conceptual-workflows-glossary

This module owns IO and matching for the glossary. Schema validation lives
in `lore.schemas`; CLI rendering lives in `lore.cli`. Keep it that way —
see `standards-single-responsibility`.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import yaml

from lore.models import GlossaryItem
from lore.paths import glossary_path
from lore.schemas import SchemaValidationError, validate_entity, validate_entity_file


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
# Auto-surface tokeniser, matcher, renderer.
#
# The ``_normalise_tokens`` / ``_build_lookup`` / ``_scan_runs`` triple is the
# shared word-boundary matching primitive. ``match_glossary`` consumes it in
# canonical mode (auto-surface). Keep these primitives stable and free of
# caller-specific logic.
# ---------------------------------------------------------------------------


def _normalise_tokens(text: str) -> list[str]:
    """Split ``text`` on non-word runs, casefold, drop empties.

    Shared tokeniser for canonical auto-surface. Casefold + Unicode-aware
    ``\\W`` split — see standards-no-substring-in-prose.
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
    indexes only do_not_use; retained as a primitive for symmetry with
    the canonical lookup (no production caller after the deprecated-term
    scan removal — exercised by unit tests for shape parity).
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
    deduplication. Empty ``lookup`` → no yields. Shared primitive for the
    canonical auto-surface (``_scan_runs``).
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


# ---------------------------------------------------------------------------
# Write surface — create / update / delete a single glossary item.
#
# Spec: .lore/codex/transient/glossary-crud-spec.md
# Comments in glossary.yaml are project-meaningful guidance: we preserve any
# header text that appears BEFORE the first `items:` line by treating it as a
# raw prefix and only round-tripping the items list through PyYAML. Inline
# item-level comments are dropped — documented limitation.
# ---------------------------------------------------------------------------


_KEYWORD_MAX = 80
_DEFINITION_MAX = 1000


def _validate_keyword_format(keyword: str) -> None:
    if not isinstance(keyword, str) or not keyword.strip():
        raise ValueError("Glossary keyword must be 1-80 chars, no line breaks.")
    if len(keyword) > _KEYWORD_MAX or "\n" in keyword or "\r" in keyword:
        raise ValueError("Glossary keyword must be 1-80 chars, no line breaks.")


def _validate_definition(definition: str) -> None:
    if not isinstance(definition, str) or not definition.strip():
        raise ValueError("Glossary definition must be 1-1000 chars, not empty.")
    if len(definition) > _DEFINITION_MAX:
        raise ValueError("Glossary definition must be 1-1000 chars, not empty.")


def _validate_alias_list(values: list[str]) -> None:
    """Per-string + uniqueness rules for aliases / do_not_use lists."""
    seen: set[str] = set()
    for v in values:
        if (
            not isinstance(v, str)
            or not v.strip()
            or len(v) > _KEYWORD_MAX
            or "\n" in v
            or "\r" in v
        ):
            raise ValueError(
                "Glossary aliases/do_not_use entries must be 1-80 chars, "
                "no line breaks, no duplicates."
            )
        if v in seen:
            raise ValueError(
                "Glossary aliases/do_not_use entries must be 1-80 chars, "
                "no line breaks, no duplicates."
            )
        seen.add(v)


def _split_header_and_items(text: str) -> tuple[str, dict]:
    """Split file text into a comment/blank prefix and the parsed YAML body.

    Strategy per Q1 decision: locate the first line whose lstrip starts with
    ``items:`` and treat everything before it as a raw prefix to be preserved
    verbatim on write. The body (from that line on) is parsed with safe_load.
    If no such line exists (file may be e.g. ``items: []`` on one line), the
    whole document parses as body with empty prefix.
    """
    lines = text.splitlines(keepends=True)
    split_idx: int | None = None
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("items:") or stripped.startswith("items :"):
            split_idx = i
            break
    if split_idx is None:
        prefix = ""
        body_text = text
    else:
        prefix = "".join(lines[:split_idx])
        body_text = "".join(lines[split_idx:])
    data = yaml.safe_load(body_text) or {}
    if not isinstance(data, dict):
        raise ValueError("Glossary file body must parse to a mapping.")
    return prefix, data


def _serialise_item(item: dict) -> dict:
    """Produce the storage-shaped dict for an item — drops empty optional lists."""
    out: dict = {"keyword": item["keyword"], "definition": item["definition"]}
    aliases = item.get("aliases") or []
    if aliases:
        out["aliases"] = list(aliases)
    do_not_use = item.get("do_not_use") or []
    if do_not_use:
        out["do_not_use"] = list(do_not_use)
    return out


def _load_for_write(root: Path) -> tuple[Path, str, dict]:
    """Open glossary.yaml for a write op; raise ValueError if absent or invalid.

    Returns ``(path, prefix, data_dict)`` where ``data_dict["items"]`` is the
    items list (list of dicts) ready for mutation.
    """
    path = glossary_path(root)
    if not path.exists():
        raise ValueError(
            "Glossary file not found — run lore init or restore "
            ".lore/codex/glossary.yaml."
        )
    try:
        validate_entity_file(str(path), "glossary")
    except SchemaValidationError as e:
        raise ValueError(str(e)) from e
    text = path.read_text(encoding="utf-8")
    prefix, data = _split_header_and_items(text)
    if "items" not in data or not isinstance(data["items"], list):
        raise ValueError("Glossary file must contain an `items:` list.")
    return path, prefix, data


def _commit(path: Path, prefix: str, data: dict) -> None:
    """Re-validate, serialise, atomic-write (tmp + os.replace)."""
    issues = validate_entity("glossary", data)
    if issues:
        raise ValueError("\n".join(i.message for i in issues))
    body = yaml.safe_dump(
        data, sort_keys=False, allow_unicode=True, default_flow_style=False
    )
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(prefix + body, encoding="utf-8")
    os.replace(tmp, path)


def _find_item_index(items: list[dict], keyword: str) -> int | None:
    needle = keyword.casefold()
    for idx, item in enumerate(items):
        stored = item.get("keyword", "")
        if isinstance(stored, str) and stored.casefold() == needle:
            return idx
    return None


def create_glossary_item(
    project_root: Path,
    keyword: str,
    definition: str,
    *,
    aliases: list[str] | None = None,
    do_not_use: list[str] | None = None,
) -> dict:
    """Append a new glossary item to ``.lore/codex/glossary.yaml``.

    Returns ``{"keyword": str, "filename": "glossary.yaml"}``.

    Raises ``ValueError`` on missing/empty keyword or definition, schema
    violation, duplicate keyword (case-insensitive), or missing glossary file.
    Comments at the top of the file are preserved (Q1 decision); inline
    item-level comments are dropped (documented limitation).
    """
    _validate_keyword_format(keyword)
    _validate_definition(definition)
    if aliases is not None:
        _validate_alias_list(aliases)
    if do_not_use is not None:
        _validate_alias_list(do_not_use)

    path, prefix, data = _load_for_write(project_root)
    items: list[dict] = data["items"]

    if _find_item_index(items, keyword) is not None:
        raise ValueError(f'Glossary keyword "{keyword}" already exists.')

    new_item: dict = {"keyword": keyword, "definition": definition}
    if aliases:
        new_item["aliases"] = list(aliases)
    if do_not_use:
        new_item["do_not_use"] = list(do_not_use)

    items.append(new_item)
    data["items"] = [_serialise_item(i) for i in items]

    _commit(path, prefix, data)
    return {"keyword": keyword, "filename": "glossary.yaml"}


def update_glossary_item(
    project_root: Path,
    keyword: str,
    *,
    definition: str | None = None,
    aliases: list[str] | None = None,
    do_not_use: list[str] | None = None,
) -> dict:
    """Mutate the matched item in-place. ``None`` means "leave field unchanged";
    ``aliases=[]`` / ``do_not_use=[]`` explicitly clears the list (and removes
    the YAML key on write).

    Lookup is case-insensitive on keyword; stored casing is preserved. Renames
    are out of scope — use ``delete_glossary_item`` + ``create_glossary_item``.

    Returns ``{"keyword": str, "filename": "glossary.yaml"}`` (keyword as stored).

    Raises ``ValueError`` on missing file, item not found, schema violation, or
    a no-op call (every kwarg ``None``).
    """
    if definition is None and aliases is None and do_not_use is None:
        raise ValueError(
            "update_glossary_item requires at least one field to change."
        )

    if definition is not None:
        _validate_definition(definition)
    if aliases is not None:
        _validate_alias_list(aliases)
    if do_not_use is not None:
        _validate_alias_list(do_not_use)

    path, prefix, data = _load_for_write(project_root)
    items: list[dict] = data["items"]
    idx = _find_item_index(items, keyword)
    if idx is None:
        raise ValueError(f'Glossary keyword "{keyword}" not found.')

    target = dict(items[idx])
    stored_keyword = target["keyword"]
    if definition is not None:
        target["definition"] = definition
    if aliases is not None:
        target["aliases"] = list(aliases)
    if do_not_use is not None:
        target["do_not_use"] = list(do_not_use)

    items[idx] = target
    data["items"] = [_serialise_item(i) for i in items]

    _commit(path, prefix, data)
    return {"keyword": stored_keyword, "filename": "glossary.yaml"}


def delete_glossary_item(project_root: Path, keyword: str) -> dict:
    """Hard-delete the matched item from ``items[]``. Idempotent — re-deleting
    a missing keyword returns the same envelope shape (no ``already_deleted``
    flag, per canonical A2).

    Returns ``{"keyword": str, "deleted": True, "deleted_at": <UTC ISO str>}``.

    Raises ``ValueError`` only when the glossary file is missing or invalid.
    A missing keyword is NOT an error.
    """
    _validate_keyword_format(keyword)
    path, prefix, data = _load_for_write(project_root)
    items: list[dict] = data["items"]
    idx = _find_item_index(items, keyword)
    if idx is not None:
        items.pop(idx)
        data["items"] = [_serialise_item(i) for i in items]
        _commit(path, prefix, data)
    return {
        "keyword": keyword,
        "deleted": True,
        "deleted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
    }


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
