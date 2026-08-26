"""The install manifest — the record of what `lore init` wrote.

`.lore/.install-manifest.json` is the only thing that tells a file Lore
installed apart from a file the project authored, and every decision the
reconciliation table makes rests on it. It is generated, never hand-edited, and
already ignored by the ``*`` that opens `.lore/.gitignore`.

Its entries name paths **outside** ``.lore/`` — ``.claude/skills/…``,
``CLAUDE.md``, ``.gitignore`` — so every path is stored repo-root-relative in
POSIX form regardless of platform and rehydrated against a supplied root.

**Hashing lives here, once.** Content is hashed as raw bytes with no newline
normalisation, so a CRLF checkout registers as an edit — the honest answer,
since Lore wrote LF. The digest covers the *rendered* content, after
access-mode selection, which is what makes flipping the access mode a clean
overwrite of an unmodified file rather than a wall of phantom user edits. For a
``section`` entry it covers only the text between the markers, so editing prose
elsewhere in the same file never registers as a conflict.

An unreadable, unrecognised or structurally invalid manifest is a fall-soft
condition, never an error: one stderr warning, ``None`` back, and the caller
drops to the legacy-hash fallback. That holds for *any* failure — a manifest is
generated and never hand-edited, so a payload that parses as JSON and still
contradicts the recorded shape is a corrupt file, not an older format. The bias
stays toward keeping files, which keeps a downgrade safe
(conceptual-workflows-error-handling).
"""

from __future__ import annotations

import functools
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, NoReturn

from lore import safewrite
from lore.initplan import PlannedFile
from lore.paths import install_manifest_path

MANIFEST_VERSION = 1
"""The only format this release understands. Anything else is unreadable."""

MULTIPLE_BLOCKS = "more than one Lore marker block — remove the extra pair, then re-run"
"""Said by every reader of a marked file, so none of them can normalise it away."""

_DIGEST_PREFIX = "sha256:"
_REQUIRED_ENTRY_KEYS = ("path", "kind", "source", "hash")


@dataclass(frozen=True)
class RecordedEntry:
    """One file Lore wrote last time, with the hash it wrote."""

    path: str
    """Repo-root-relative POSIX path."""

    kind: str
    """``"owned"`` — Lore wrote the whole file, and it is eligible for removal.

    ``"section"`` — Lore wrote a marked block inside a file the project owns.
    ``hash`` covers only that block, and the entry is never removable as a file:
    retiring its source deletes the block and leaves the rest byte-identical.
    """

    source: str
    """What produced it: ``"skill:store-memory"``, ``"agent-instructions:claude"``, …"""

    hash: str
    """``sha256:…`` of the rendered content this entry covers."""


@dataclass(frozen=True)
class Manifest:
    """A parsed `.lore/.install-manifest.json`."""

    manifest_version: int
    lore_version: str
    catalogue_version: int
    generated_at: str
    answers: dict[str, Any]
    """Informational — lets a report say the access mode moved native → cli."""

    targets: dict[str, str]
    """Informational — lets a deselected agent with an empty skill set be detected."""

    files: tuple[RecordedEntry, ...]
    """Sorted by path. The reconciliation algorithm reads this and nothing else."""

    @property
    def by_path(self) -> dict[str, RecordedEntry]:
        """Index ``files`` by path — the shape the reconciliation table consumes."""
        return {entry.path: entry for entry in self.files}


# ---------------------------------------------------------------------------
# Hashing — one function, one place
# ---------------------------------------------------------------------------


def bytes_digest(data: bytes) -> str:
    """Return ``"sha256:" + hexdigest`` for *data*."""
    return _DIGEST_PREFIX + hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> str:
    """Return the digest of *path*'s raw bytes.

    No newline normalisation: a CRLF checkout hashes differently from the LF
    bytes Lore wrote, and registering that as an edit is the honest answer.
    """
    return bytes_digest(Path(path).read_bytes())


def section_text(
    text: str, begin: str, end: str, *, source: object | None = None
) -> str | None:
    """Return the text between the marker lines, markers excluded.

    ``None`` when *text* carries no complete block — either marker missing. An
    empty block is ``""``, which is a block, not an absence. A missing marker
    stays lenient on purpose: the block is simply restored, and the writer
    raises if it cannot tell where to put it.

    A **doubled** pair is the one shape that cannot be lenient. Taking the
    first match there is what let a `CLAUDE.md` torn by two concurrent runs
    digest as already-correct, so the run that would have objected took the
    no-op row and reported success over a file missing a quarter of the user's
    content. Every reader of a marked file goes through here, so raising here
    is what makes that impossible to normalise away.
    """
    lines = text.splitlines(keepends=True)
    reject_duplicate_markers(lines, begin, end, source=source)
    opener = next(iter(_marker_indices(lines, begin)), None)
    if opener is None:
        return None
    closer = next(
        (index for index in _marker_indices(lines, end) if index > opener), None
    )
    if closer is None:
        return None
    return "".join(lines[opener + 1 : closer])


def section_digest(
    text: str, begin: str, end: str, *, source: object | None = None
) -> str:
    """Return the digest of the marked block inside *text*, markers excluded.

    Raises ``ValueError`` when *text* carries no complete block — the caller
    decides whether that means "restore it" or "nothing to remove".
    """
    block = section_text(text, begin, end, source=source)
    if block is None:
        raise ValueError(f"no complete block between {begin!r} and {end!r}")
    return bytes_digest(block.encode("utf-8"))


def reject_duplicate_markers(
    lines: list[str], begin: str, end: str, *, source: object | None = None
) -> None:
    """Raise when *lines* carries more than one of either marker.

    One rule, one message, reached by both the reader and the writer — the two
    used to disagree, and a file only the reader looked at went unreported.
    """
    if len(_marker_indices(lines, begin)) > 1 or len(_marker_indices(lines, end)) > 1:
        raise ValueError(_named(source, MULTIPLE_BLOCKS))


def marker_span(
    lines: list[str], begin: str, end: str, *, source: object | None = None
) -> tuple[int, int] | None:
    """Return the marker line indices in *lines*, or None when there is no block.

    Raises ``ValueError`` naming *source* rather than guessing whenever the
    markers do not form exactly one well-ordered pair. Guessing here would put
    Lore's block somewhere the user did not agree to.
    """
    reject_duplicate_markers(lines, begin, end, source=source)
    openers = _marker_indices(lines, begin)
    closers = _marker_indices(lines, end)

    if openers and not closers:
        return _raise(source, f"{begin.strip()!r} has no closing {end.strip()!r}")
    if closers and not openers:
        return _raise(source, f"{end.strip()!r} has no opening {begin.strip()!r}")
    if not openers:
        return None
    if closers[0] < openers[0]:
        return _raise(source, "the Lore markers are in the wrong order")
    return openers[0], closers[0]


def _marker_indices(lines: list[str], marker: str) -> list[int]:
    """Every index whose line is *marker*, ignoring surrounding space."""
    needle = marker.strip()
    return [index for index, line in enumerate(lines) if line.strip() == needle]


def _named(source: object | None, message: str) -> str:
    """*message*, prefixed with the file it is about when there is one."""
    return message if source is None else f"{source}: {message}"


def _raise(source: object | None, message: str) -> NoReturn:
    raise ValueError(_named(source, message))


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def to_posix(path: str) -> str:
    """Normalise a repo-relative path to the POSIX form the manifest stores."""
    return path.replace("\\", "/")


def read_text(path: Path) -> str:
    """Return *path*'s text, or raise ``ValueError`` naming the file.

    Every text read the reconciliation path performs on a file the *project*
    owns goes through here. Nothing guarantees such a file is text — a recorded
    path can name a binary file the project put there — and the decoder's own
    message says a byte offset and no filename, which tells nobody which file to
    look at (conceptual-workflows-error-handling). The bytes Lore itself hashes
    are read as bytes and never come here.
    """
    try:
        return Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"{path}: not valid UTF-8 text ({exc.reason} at byte {exc.start}) — "
            "Lore has to read this file as text; restore or remove it, then re-run"
        ) from exc


def escape_reason(path: str) -> str | None:
    """Why *path* describes a file outside the project, or ``None``.

    A recorded path is repo-root-relative by construction, and the two shapes
    that are not describe a file outside the project: ``..`` walks out one level
    per segment, and an **absolute** path leaves entirely, because
    ``Path.joinpath`` resets on an absolute component rather than appending it.

    The containment half of :func:`unownable_reason`, and the half every
    *planned* row is held to — a plan carries paths this release computed as
    well as paths a manifest recorded, so it is asked the question that is
    about the project boundary alone.
    """
    posix = to_posix(path)
    if not posix.strip():
        return "is empty"
    pure = PurePosixPath(posix)
    if pure.is_absolute():
        return "is absolute"
    if ".." in pure.parts:
        return "walks out of the project with '..'"
    return None


def unownable_reason(path: str) -> str | None:
    """Why *path* cannot be a path Lore installed to, or ``None`` when it can.

    Asked at the boundary where a manifest becomes data — :func:`_parse` —
    because that is the only place these values arrive from outside, and this
    module's own contract calls a manifest untrusted input. Three questions,
    weakest first:

    * does it leave the project (:func:`escape_reason`);
    * does it hold a character no path Lore writes can carry — a NUL is the one
      that mattered, because it is none of the escape shapes, so the row was
      accepted and the first ``lstat`` on it raised a ``ValueError`` naming no
      file and wedging every later run;
    * is it **somewhere this release installs to, or removes from** at all.

    That third question is what makes a removal as constrained as a write. The
    plan side already refuses to write a path this release does not produce;
    the removal side had no equivalent, so a row appended to the manifest by
    hand could unlink any file inside the project — the destructive direction
    was the permissive one.

    Derived from the shipped registry and the skills roots rather than
    authored, so a path this release can write is never one it then refuses to
    read back.
    """
    escape = escape_reason(path)
    if escape is not None:
        return escape
    posix = to_posix(path)
    unusable = _unusable_character(posix)
    if unusable is not None:
        return unusable
    parts = PurePosixPath(posix).parts
    if parts in _ownable_files():
        return None
    if any(parts[: len(root)] == root for root in _ownable_roots()):
        return None
    return "names a file this release never installs or removes"


def _unusable_character(posix: str) -> str | None:
    """The refusal for a character no path `lore init` writes can hold."""
    for char in posix:
        if char == "\x00":
            return "holds a NUL byte, which no filesystem path can carry"
        if ord(char) < 0x20 or ord(char) == 0x7F:
            return f"holds the control character {ord(char):#04x}"
    return None


LORE_AGENT_PATH = ".lore/LORE-AGENT.md"
"""The canonical rendered agent-instruction text, written on every run."""

ROOT_GITIGNORE_PATH = ".gitignore"
"""The project's own gitignore, which Lore used to write a marked block inside.

No release writes it any more — every line the block carried was already
ignored by the ``*`` opening `.lore/.gitignore`. It stays named here because a
record of it outlives the writer: every project initialised before that change
has a ``section`` row at this path, and a release that stopped calling the path
ownable would reject those manifests whole, fall back to the legacy hashes and
lose the record of everything else Lore installed there.
"""


@functools.lru_cache(maxsize=1)
def _ownable_files() -> frozenset[tuple[str, ...]]:
    """Every single file Lore may install to or remove from outside a skills tree.

    As path parts. The rendered agent doc and each registry row's instruction
    file — read from the registry so adding an agent stays one YAML block
    (``lore.agents``) and does not also need a line here — plus the root
    gitignore, which this release only ever *removes* a block from.
    """
    from lore.agents import load_registry

    paths = {LORE_AGENT_PATH, ROOT_GITIGNORE_PATH}
    paths.update(row.instruction_file for row in load_registry() if row.instruction_file)
    return frozenset(PurePosixPath(path).parts for path in paths)


@functools.lru_cache(maxsize=1)
def _ownable_roots() -> frozenset[tuple[str, ...]]:
    """Every directory a skill can install into, as path parts.

    ``.lore/skills`` and every registry ``skills_dir``. A pre-manifest release
    installed only to the first; the documented ``cp -r`` put copies in the
    second, and both are trees `lore init` removes from.
    """
    from lore.agents import load_registry
    from lore.skills import LORE_SKILLS_ROOT

    roots = {LORE_SKILLS_ROOT}
    roots.update(row.skills_dir for row in load_registry() if row.skills_dir)
    return frozenset(PurePosixPath(root).parts for root in roots)


def resolve_path(project_root: Path, path: str) -> Path:
    """Rehydrate a stored POSIX path against *project_root*.

    Joining alone, deliberately: this is used by readers as well as writers, and
    a reader that raised would turn a path Lore wants to *report* on into a run
    that stops. Containment is enforced where it matters — ``escape_reason`` at
    parse time, and ``safewrite`` at the write and the unlink.
    """
    return project_root.joinpath(*PurePosixPath(to_posix(path)).parts)


# ---------------------------------------------------------------------------
# Reading and writing
# ---------------------------------------------------------------------------


def write(
    project_root: Path,
    *,
    answers: Mapping[str, Any],
    targets: Mapping[str, str],
    files: Iterable[PlannedFile],
    lore_version: str,
    catalogue_version: int,
) -> Path:
    """Write the manifest for *project_root* and return its path.

    Records every entry that carries a digest, sorted by path. An entry with no
    digest is a removal or a keep — there is nothing for the next run to
    compare against, so there is nothing to record.

    ``generated_at`` is the only field that differs between two manifests
    written from the same content, which is what makes idempotency assertable.

    Written through ``safewrite`` like everything else `lore init` writes: the
    file arrives whole, and a link left at this path is refused rather than
    followed. The manifest is small enough that the old truncating write
    happened to land in one syscall, which was luck of size and not a promise.
    """
    recorded = []
    for entry in files:
        if entry.digest is None:
            # A removal or a keep — nothing was written, so nothing to record.
            continue
        recorded.append(
            {
                "path": to_posix(entry.path),
                "kind": entry.kind,
                "source": entry.source,
                "hash": entry.digest,
            }
        )
    recorded.sort(key=lambda row: row["path"])

    payload = {
        "manifest_version": MANIFEST_VERSION,
        "lore_version": lore_version,
        "catalogue_version": catalogue_version,
        "generated_at": _now(),
        "answers": dict(answers),
        "targets": dict(targets),
        "files": recorded,
    }

    target = install_manifest_path(project_root)
    safewrite.atomic_write_text(
        target, json.dumps(payload, indent=2) + "\n", project_root=project_root
    )
    return target


def load(project_root: Path) -> Manifest | None:
    """Return the parsed manifest for *project_root*, or ``None``.

    An absent manifest is silent — a project that has never been initialised by
    a release that writes one is the normal case. An unparseable one, or one
    whose ``manifest_version`` this release does not understand, emits exactly
    one stderr warning and returns ``None`` so the caller falls through to the
    legacy-hash path. Every failing call warns; this is not routed through
    ``lore.config``'s one-warning-per-process latch, which belongs to config
    parsing.
    """
    path = install_manifest_path(project_root)
    if not path.is_file():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _parse(payload)
    except (OSError, ValueError) as exc:
        _warn_unreadable(path, str(exc))
        return None
    except Exception as exc:
        # The contract above is unconditional, so the catch has to be too. A
        # manifest is untrusted input and `_recorded_entries` has no other
        # branch: anything that escapes here is a raw traceback in place of a
        # run that should simply have fallen back. The type is named, because a
        # failure this clause sees is one `_parse` was expected to have
        # rejected as a ValueError and did not.
        _warn_unreadable(path, f"unexpected {type(exc).__name__}: {exc}")
        return None


def _parse(payload: Any) -> Manifest:
    """Build a ``Manifest`` from a parsed payload, or raise ``ValueError``.

    Every field is type-checked before it is used, not only checked for
    presence. A manifest is generated, so a row carrying a number where a path
    belongs is a corrupt file rather than an older format — and the fields are
    declared types on a frozen dataclass, which a payload that parsed as JSON
    can contradict in any of them. Rejecting the whole file is the fall-soft
    branch the module contract promises: one warning, the legacy-hash fallback,
    and a bias toward keeping files.

    One field is checked for more than its type. ``path`` is the field a removal
    unlinks, so a value naming a file this release never installs is corrupt in
    a way a string type-check cannot see — and this module's own contract calls
    a manifest untrusted input. ``unownable_reason`` is that check, and it
    covers the destination as well as the shape: containment, characters no
    written path can hold, and whether Lore installs there at all.
    """
    if not isinstance(payload, dict):
        raise ValueError("manifest must be a JSON object")

    version = payload.get("manifest_version")
    if version != MANIFEST_VERSION:
        raise ValueError(f"unrecognised manifest_version: {version!r}")

    rows = payload.get("files")
    if not isinstance(rows, list):
        raise ValueError("'files' must be a list")

    entries = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"files entry {index} is not an object")
        missing = [key for key in _REQUIRED_ENTRY_KEYS if key not in row]
        if missing:
            raise ValueError(f"files entry {index} is missing {', '.join(missing)}")
        recorded_path = to_posix(_entry_string(row, "path", index))
        unownable = unownable_reason(recorded_path)
        if unownable is not None:
            raise ValueError(
                f"files entry {index}: 'path' {unownable} — {recorded_path!r} is "
                "not a path this release installs to or removes from, and a "
                "manifest records only what `lore init` wrote"
            )
        entries.append(
            RecordedEntry(
                path=recorded_path,
                kind=_entry_string(row, "kind", index),
                source=_entry_string(row, "source", index),
                hash=_entry_string(row, "hash", index),
            )
        )

    return Manifest(
        manifest_version=version,
        lore_version=_field(payload, "lore_version", str, ""),
        catalogue_version=_field(payload, "catalogue_version", int, 0),
        generated_at=_field(payload, "generated_at", str, ""),
        answers=_field(payload, "answers", dict, {}),
        targets=_field(payload, "targets", dict, {}),
        files=tuple(entries),
    )


def _entry_string(row: Mapping[str, Any], key: str, index: int) -> str:
    """Return ``row[key]``, or raise ``ValueError`` when it is not a string."""
    value = row[key]
    if not isinstance(value, str):
        raise ValueError(
            f"files entry {index}: '{key}' must be a string, "
            f"not {type(value).__name__}"
        )
    return value


def _field(payload: Mapping[str, Any], key: str, expected: type, default: Any) -> Any:
    """Return ``payload[key]`` when it has the declared type, or *default* when absent."""
    if key not in payload:
        return default
    value = payload[key]
    if not isinstance(value, expected):
        raise ValueError(
            f"'{key}' must be a {expected.__name__}, not {type(value).__name__}"
        )
    return value


def _warn_unreadable(path: Path, reason: str) -> None:
    """Warn once for this call; the caller falls through to the legacy-hash path."""
    print(
        f"lore: unreadable install manifest at {path}: {reason} "
        "(falling back to legacy hashes)",
        file=sys.stderr,
    )


def _now() -> str:
    """Return the current UTC time as an ISO-8601 second-resolution stamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
