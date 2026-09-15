"""`lore impacts` business logic — codex-seed + code-seed branches.

This module is the public home for token classification and codex<->code
binding surfacing, sibling to ``codex.py`` and ``artifact.py``.

Post nested-projects: a codex-id seed is split by D-8 and run against the
project the id resolves to; a repo-relative path seed means a different file
in each project, so it is resolved against every in-scope project's own root
and every row carries its ``origin`` (D-28).
"""

from __future__ import annotations

import dataclasses
import functools
import re
from pathlib import Path, PurePosixPath
from typing import Literal

from lore import codex, frontmatter, projects, scoped
from lore.paths import codex_dir
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
    """One row of codex-seed output.

    ``path`` is the bound source file, repo-relative to the project that
    declared the binding; ``origin`` names that project.
    """

    path: str
    kind: Literal["exact", "glob"]
    origin: str = "self"


@dataclasses.dataclass(frozen=True)
class CodeBinding:
    """One row of code-seed output.

    ``id`` is origin-qualified for a foreign document, which already names
    the source — ``impacts`` renders bare lines rather than a table, so there
    is no ORIGIN column for FR-16's rule to attach to (D-28).
    """

    id: str
    match: Literal["exact", "glob"]
    pattern: str | None = None
    origin: str = "self"


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
    scope: str | None = None,
) -> ImpactsResult:
    """Surface codex<->code bindings for *token* across the projects in scope.

    Codex-seed: returns ``ImpactsResult(kind="codex", codex_items=...)``
    preserving declaration order from the source frontmatter. The seed is
    resolved the way every other id is — a bare id locally first, a qualified
    id never locally (D-8) — and the bindings come from the project that owns
    it.

    Code-seed: returns ``ImpactsResult(kind="code", code_items=...)``
    sorted alphabetically by codex id — the qualified id for a foreign
    document — deduped per id with exact-precedence over glob (FR-9).
    ``direct_links=True`` drops glob rows. A repo-relative path is resolved
    against each in-scope project's own root, because it names a different
    file in each (D-28).

    Raises ``ImpactsError`` on unknown codex id, outside-repo path, or
    ``..`` traversal, and ``UnknownProjectError`` when ``scope`` names no
    project in scope.
    """
    visible = codex.list_codex(project_root, scope=scope)

    if classify_token(token) == "codex":
        return _codex_seed(token, project_root, scope, visible)
    return _code_seed(token, project_root, scope, visible, direct_links)


def _codex_seed(
    token: str, project_root: Path, scope: str | None, visible: list[dict]
) -> ImpactsResult:
    """Return the bindings the document *token* names declares."""
    row = scoped.select(visible, token)
    if row is None:
        raise ImpactsError(f'Unknown codex id: "{token}"')
    owner_root, local_id = scoped.locate(project_root, scope, row)
    index = _load_codex_binds_index(codex_dir(owner_root))
    if local_id not in index:
        # Visible as a document but absent from the binds index: its
        # ``binds:`` is malformed, and this is a read tool — authoritative
        # rejection lives in `lore health`.
        raise ImpactsError(f'Unknown codex id: "{token}"')
    items = tuple(
        CodexBinding(
            path=path,
            kind="glob" if is_glob_pattern(path) else "exact",
            origin=row["origin"],
        )
        for path in index[local_id]
    )
    return ImpactsResult(kind="codex", codex_items=items)


def _code_seed(
    token: str,
    project_root: Path,
    scope: str | None,
    visible: list[dict],
    direct_links: bool,
) -> ImpactsResult:
    """Return the documents binding the file *token* names, per project."""
    visible_ids = {row["id"] for row in visible}
    matches: dict[str, CodeBinding] = {}
    for position, ref in enumerate(projects.resolve_scope(project_root, scope)):
        origin = scoped.SELF if ref.relation == scoped.SELF else ref.name
        try:
            normalised = _normalize_path_input(token, ref.root)
        except ImpactsError:
            # The seed is the reader's own path, so its own project answers
            # for it; a project further out that cannot hold it contributes
            # nothing rather than failing the command (N-7).
            if position == 0:
                raise
            continue
        for entry_id, binds in _load_codex_binds_index(codex_dir(ref.root)).items():
            qualified = projects.qualify(origin, entry_id)
            if qualified not in visible_ids:
                continue
            _record_matches(matches, qualified, origin, normalised, binds)

    code_items = tuple(matches[key] for key in sorted(matches))
    if direct_links:
        code_items = tuple(b for b in code_items if b.match == "exact")
    return ImpactsResult(kind="code", code_items=code_items)


def _record_matches(
    matches: dict[str, CodeBinding],
    entry_id: str,
    origin: str,
    normalised: str,
    binds: list[str],
) -> None:
    """Record the best row for one document: exact takes precedence (FR-9)."""
    for pattern in binds:
        pat_norm = _normalize_slashes(pattern)
        if not _has_glob_chars(pat_norm):
            if normalised == pat_norm:
                matches[entry_id] = CodeBinding(
                    id=entry_id, match="exact", pattern=None, origin=origin
                )
            continue
        if not _match_pattern(normalised, pat_norm):
            continue
        if matches.get(entry_id) is None:
            matches[entry_id] = CodeBinding(
                id=entry_id, match="glob", pattern=pattern, origin=origin
            )
        # existing exact wins; existing glob keeps first.
