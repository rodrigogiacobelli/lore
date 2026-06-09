"""`lore impacts` business logic — codex-seed + code-seed branches.

This module is the public home for token classification and codex<->code
binding surfacing, sibling to ``codex.py`` and ``artifact.py``.
"""

from __future__ import annotations

import dataclasses
import functools
import re
from pathlib import Path, PurePosixPath
from typing import Literal

from lore import frontmatter
from lore.validators import is_glob_pattern


# ---------------------------------------------------------------------------
# Error model
# ---------------------------------------------------------------------------


class ImpactsError(ValueError):
    """Raised on unknown codex id, path outside repo, or malformed token."""


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class CodexBinding:
    """One row of codex-seed output."""

    path: str
    kind: Literal["exact", "glob"]


@dataclasses.dataclass(frozen=True)
class CodeBinding:
    """One row of code-seed output."""

    id: str
    match: Literal["exact", "glob"]
    pattern: str | None = None


@dataclasses.dataclass(frozen=True)
class ImpactsResult:
    """Tagged-union container for codex-seed or code-seed lookups."""

    kind: Literal["codex", "code"]
    codex_items: tuple[CodexBinding, ...] = ()
    code_items: tuple[CodeBinding, ...] = ()


# ---------------------------------------------------------------------------
# Token classification
# ---------------------------------------------------------------------------


def classify_token(token: str) -> Literal["codex", "path"]:
    """Return ``"path"`` if *token* contains ``/`` or ``.``; else ``"codex"``."""
    if "/" in token or "." in token:
        return "path"
    return "codex"


# ---------------------------------------------------------------------------
# Glob matching
# ---------------------------------------------------------------------------


def _has_glob_chars(s: str) -> bool:
    """Return ``True`` iff *s* contains any of ``*``, ``?``, ``[``.

    Hot-loop local mirror of ``validators.is_glob_pattern``; both must agree.
    """
    return any(c in s for c in "*?[")


def _normalize_slashes(s: str) -> str:
    """Normalise backslash separators to POSIX ``/``."""
    return s.replace("\\", "/")


def _pattern_to_regex(pattern: str) -> str:
    """Translate a glob pattern to a regex source string.

    Semantics:
      - ``**/`` matches zero or more leading path segments (incl. empty).
      - ``/**`` at end matches zero or more trailing segments.
      - ``**`` standalone matches any sequence of characters including ``/``.
      - ``*`` matches any sequence of characters except ``/`` (segment-bounded).
      - ``?`` matches a single character except ``/``.
      - ``[...]`` character classes are passed through.
      - Everything else is escaped.
    """
    out: list[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        c = pattern[i]
        if c == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                # ``**`` — check for surrounding slashes for the zero-segment case.
                if i + 2 < n and pattern[i + 2] == "/":
                    # ``**/`` — zero or more segments
                    out.append("(?:.*/)?")
                    i += 3
                else:
                    out.append(".*")
                    i += 2
            else:
                out.append("[^/]*")
                i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c == "[":
            j = i + 1
            if j < n and pattern[j] == "!":
                j += 1
            if j < n and pattern[j] == "]":
                j += 1
            while j < n and pattern[j] != "]":
                j += 1
            if j >= n:
                out.append(re.escape(c))
                i += 1
            else:
                cls = pattern[i + 1 : j]
                if cls.startswith("!"):
                    cls = "^" + cls[1:]
                out.append("[" + cls + "]")
                i = j + 1
        else:
            out.append(re.escape(c))
            i += 1
    return "".join(out)


def _match_pattern(path_str: str, pattern: str) -> bool:
    """Match *path_str* against *pattern*.

    Literal patterns are compared via string equality. Glob patterns use
    a custom regex bridge: ``**`` spans segments, ``*``/``?`` do not.
    Both sides are backslash-normalised to POSIX ``/`` first.
    """
    path = _normalize_slashes(path_str)
    pat = _normalize_slashes(pattern)
    if not _has_glob_chars(pat):
        return path == pat
    regex = "^" + _pattern_to_regex(pat) + "$"
    return re.match(regex, path) is not None


# ---------------------------------------------------------------------------
# Path normalisation
# ---------------------------------------------------------------------------


def _normalize_path_input(raw: str, project_root: Path) -> str:
    """Normalise *raw* to a repo-relative POSIX path string.

    Raises ``ImpactsError`` with the exact contract messages on traversal
    or outside-repo inputs.
    """
    normalised = _normalize_slashes(raw)
    posix = PurePosixPath(normalised)
    if ".." in posix.parts:
        raise ImpactsError(f'Path traversal not allowed: "{raw}"')

    if posix.is_absolute():
        candidate = Path(str(posix))
    else:
        candidate = project_root / normalised

    try:
        resolved = candidate.resolve()
        root_resolved = project_root.resolve()
        rel = resolved.relative_to(root_resolved)
    except (ValueError, OSError):
        raise ImpactsError(f'Path is outside the project root: "{raw}"')

    return rel.as_posix()


# ---------------------------------------------------------------------------
# Codex bindings index
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _load_codex_binds_index(codex_dir: Path) -> dict[str, list[str]]:
    """Return ``{entry_id: [binds...]}`` for every parseable codex entry.

    Missing ``binds:`` materialises as an empty list (FR-4). Malformed
    ``binds:`` entries (non-list, or list containing non-string items)
    are silently dropped: this is a read tool; authoritative rejection
    lives in ``lore health``.
    """
    index: dict[str, list[str]] = {}
    if not codex_dir.exists():
        return index
    for filepath in codex_dir.rglob("*.md"):
        record = frontmatter.parse_frontmatter_doc(
            filepath, extra_fields=("binds",)
        )
        if record is None:
            continue
        binds = record.get("binds")
        if binds is None:
            binds = []
        elif not isinstance(binds, list):
            # Malformed (e.g. scalar): skip the entry entirely.
            continue
        elif not all(isinstance(b, str) for b in binds):
            # Malformed item inside the list: skip the entry entirely.
            continue
        index[record["id"]] = list(binds)
    return index


@functools.lru_cache(maxsize=1)
def _load_codex_rites_index(codex_dir: Path) -> dict[str, list[str]]:
    """Return ``{entry_id: [rites...]}`` for every parseable codex entry.

    Missing ``rites:`` materialises as an empty list. Malformed ``rites:``
    entries (non-list, or list containing non-string items) are silently
    dropped: this is a read tool; authoritative rejection lives in
    ``lore health``.
    """
    index: dict[str, list[str]] = {}
    if not codex_dir.exists():
        return index
    for filepath in codex_dir.rglob("*.md"):
        record = frontmatter.parse_frontmatter_doc(
            filepath, extra_fields=("rites",)
        )
        if record is None:
            continue
        rites = record.get("rites")
        if rites is None:
            rites = []
        elif not isinstance(rites, list):
            # Malformed (e.g. scalar): skip the entry entirely.
            continue
        elif not all(isinstance(r, str) for r in rites):
            # Malformed item inside the list: skip the entry entirely.
            continue
        index[record["id"]] = list(rites)
    return index


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------


def impacts(
    token: str,
    *,
    project_root: Path,
    direct_links: bool = False,
) -> ImpactsResult:
    """Surface codex<->code bindings for *token*.

    Codex-seed: returns ``ImpactsResult(kind="codex", codex_items=...)``
    preserving declaration order from the source frontmatter.

    Code-seed: returns ``ImpactsResult(kind="code", code_items=...)``
    sorted alphabetically by codex id, deduped per id with exact-precedence
    over glob (FR-9). ``direct_links=True`` drops glob rows.

    Raises ``ImpactsError`` on unknown codex id, outside-repo path, or
    ``..`` traversal.
    """
    kind = classify_token(token)
    codex_dir = project_root / ".lore" / "codex"
    index = _load_codex_binds_index(codex_dir)

    if kind == "codex":
        if token not in index:
            raise ImpactsError(f'Unknown codex id: "{token}"')
        bindings = index[token]
        items = tuple(
            CodexBinding(
                path=path,
                kind="glob" if is_glob_pattern(path) else "exact",
            )
            for path in bindings
        )
        return ImpactsResult(kind="codex", codex_items=items)

    # Path seed
    normalised = _normalize_path_input(token, project_root)

    # Collect per codex id: exact takes precedence over glob (FR-9).
    matches: dict[str, CodeBinding] = {}
    for entry_id, binds in index.items():
        for pattern in binds:
            pat_norm = _normalize_slashes(pattern)
            if not _has_glob_chars(pat_norm):
                if normalised == pat_norm:
                    matches[entry_id] = CodeBinding(
                        id=entry_id, match="exact", pattern=None
                    )
                continue
            if not _match_pattern(normalised, pat_norm):
                continue
            existing = matches.get(entry_id)
            if existing is None:
                matches[entry_id] = CodeBinding(
                    id=entry_id, match="glob", pattern=pattern
                )
            # existing exact wins; existing glob keeps first.

    code_items = tuple(matches[k] for k in sorted(matches))
    if direct_links:
        code_items = tuple(b for b in code_items if b.match == "exact")
    return ImpactsResult(kind="code", code_items=code_items)
