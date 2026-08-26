"""The gate every byte `lore init` writes passes through.

Adversarial smoke testing put a 6757-byte file **outside the project** by
leaving a dangling symlink at a path Lore wanted, and truncated a user's file
outside the project by leaving a live one there under `--on-conflict
overwrite`. Neither was a bug in the code that chose those paths: both were the
same missing property in the code that wrote them. A path and a file stop being
the same thing the moment a link is involved, and every writer in the stdlib —
``write_bytes``, ``write_text``, ``open``— follows one without a word.

The same round had two concurrent runs eat 1121 lines of a user's `CLAUDE.md`,
because a read-modify-write ended in a ``write_text`` that truncates in place:
a reader in that window sees a torn file, and a second writer splices onto it.

So three properties, stated once here rather than at thirty call sites:

* **Never through a link.** A symlink at a path Lore wants to write is a
  user-owned object whatever it points at, so it is refused rather than
  followed. Detection is ``lstat``-based (``Path.is_symlink``), which is the
  only kind that does not resolve the thing it is asked about.
* **Never outside the project root.** Both sides of the containment test are
  resolved before they are compared, so no chain of links smuggles a write past
  it — and a project root that is itself reached through a link, which every
  macOS ``/tmp`` is, still contains its own files.
* **Never a torn file.** A write goes to a temporary file in the target's own
  directory and arrives by ``os.replace``, which is atomic: a concurrent reader
  sees the whole old file or the whole new one, and a failed write leaves the
  old one exactly as it was.

Stdlib only, and it imports nothing from ``lore`` — the leaf of the write path,
below ``manifest``, ``reconcile`` and ``init``, all three of which use it.

Every refusal is a ``ValueError`` naming the path and the repair, because
`conceptual-workflows-error-handling` asks for a message a person can act on
and because that is the exception `cli.py` already turns into a clean error.
"""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

THROUGH_A_LINK = "Lore never writes or removes through a link"
"""Quoted in the refusal, and asserted against by the tests."""

OUTSIDE_THE_ROOT = "resolves outside the project root"

_REPAIR = "move or remove it, then re-run"

_TEMP_SUFFIX = ".lore-tmp"


# ---------------------------------------------------------------------------
# Is this path safe to write or remove?
# ---------------------------------------------------------------------------


def link_or_escape_reason(
    target: Path, *, project_root: Path | None = None
) -> str | None:
    """Why *target* is not a path Lore may follow to a file, or ``None``.

    The half of the rule that is about the **path** rather than about what is
    sitting on it: a symlink, or somewhere outside the project. Both describe a
    user-authored object at a path Lore wants, which is the definition of a
    conflict — so reconciliation reads this one and reports rather than stops.

    A directory in the way is deliberately not here. That is not a decision
    anyone can take a policy on; it is breakage the user has to clear, and it
    stops the run with the repair named.
    """
    target = Path(target)
    reason = _link_reason(target)
    if reason is not None:
        return reason
    if project_root is None:
        return None
    return outside_root_reason(target, Path(project_root))


def unsafe_reason(target: Path, *, project_root: Path | None = None) -> str | None:
    """Why Lore must not write to or remove *target*, or ``None`` when it may.

    A phrase, not a sentence: it is both the tail of the ``ValueError``
    ``refuse_unsafe`` raises and the ``detail`` line a reconciliation conflict
    reports, so it names what is there and what to do about it.

    *project_root* is optional only because a few writers legitimately do not
    know one — every path a `lore init` run computes passes its own root.
    """
    return link_or_escape_reason(target, project_root=project_root) or _occupied_reason(
        Path(target)
    )


def refuse_unsafe(target: Path, *, project_root: Path | None = None) -> None:
    """Raise ``ValueError`` naming *target* when it is not safe to write."""
    reason = unsafe_reason(target, project_root=project_root)
    if reason is not None:
        raise ValueError(f"{target}: {reason}")


def refuse_unsafe_directory(target: Path, *, project_root: Path | None = None) -> None:
    """Raise ``ValueError`` when a directory Lore creates would not be its own.

    Weaker than ``refuse_unsafe`` on purpose. A *file* that is a link is a file
    Lore did not install, so following it is always wrong; a *directory* that is
    a link is just a place, and every file written under it is checked on its
    own — so the only thing that matters here is that the place is inside the
    project.
    """
    target = Path(target)
    if project_root is not None:
        reason = outside_root_reason(target, Path(project_root))
        if reason is not None:
            raise ValueError(f"{target}: {reason}")
    if target.is_dir():
        return
    # A link to a real directory inside the project is a place, and it returned
    # above. A link to nothing is not a place at all, and `mkdir` on one says
    # only "file exists".
    link = _link_reason(target)
    if link is not None:
        raise ValueError(f"{target}: {link}")
    if target.exists():
        raise ValueError(
            f"{target}: not a directory, and Lore has to put its files in one — "
            f"{_REPAIR}"
        )


def _link_reason(target: Path) -> str | None:
    """The refusal for a symlink, naming what it points at.

    ``is_symlink`` is an ``lstat``, so it answers for a dangling link and a
    looping one exactly as it does for a live one — which is the whole point:
    the three of them were three different outcomes before, and none of them
    was "refused".
    """
    if not target.is_symlink():
        return None
    return f"a symlink to {_points_at(target)!r} — {THROUGH_A_LINK}; {_REPAIR}"


def outside_root_reason(target: Path, project_root: Path) -> str | None:
    """The refusal for a path that lands outside *project_root* once resolved.

    Names the **link** that takes it out rather than the path that tripped over
    it, whenever an ancestor is one. A `.lore/` symlinked out of the project
    reported `.lore/.gitignore` — the first file the run happened to want under
    it — which names a symptom and leaves the reader looking at a file that is
    not there. The cause is one directory up, and it is the same cause for
    every path under it.

    Public because it is the containment half of the rule on its own: a
    *directory* Lore installs into is refused for leaving the project and for
    nothing else, while a *file* is refused for being a link at all.
    """
    resolved = _resolved(target)
    root = _resolved(project_root)
    if resolved.is_relative_to(root):
        return None
    cause = _escaping_ancestor(Path(target), Path(project_root))
    if cause is None:
        return (
            f"{OUTSIDE_THE_ROOT}, at {resolved} — Lore never writes outside the "
            f"project it was run in; {_REPAIR}"
        )
    link, points_at = cause
    return (
        f"{OUTSIDE_THE_ROOT}: {link} is a symlink to {points_at!r}, at "
        f"{_resolved(Path(project_root) / link)} — Lore never writes outside "
        f"the project it was run in; {_REPAIR}"
    )


def _escaping_ancestor(target: Path, project_root: Path) -> tuple[str, str] | None:
    """The outermost directory link above *target* that leaves *project_root*.

    Outermost, not nearest: a chain of links has one first step out, and that is
    the one to move. ``None`` when nothing above *target* is a link — an
    absolute path handed straight in, or a root that is not an ancestor at all.
    """
    root = _resolved(project_root)
    try:
        within = target.relative_to(project_root)
    except ValueError:
        return None
    prefix = project_root
    for part in within.parts[:-1]:
        prefix = prefix / part
        if prefix.is_symlink() and not _resolved(prefix).is_relative_to(root):
            return prefix.relative_to(project_root).as_posix(), _points_at(prefix)
    return None


def _points_at(link: Path) -> str:
    """What *link* points at, or a phrase saying it cannot be read."""
    try:
        return os.readlink(link)
    except OSError:  # pragma: no cover - it is a link; readlink answers
        return "an unreadable destination"


def _occupied_reason(target: Path) -> str | None:
    """The refusal for anything at *target* that is not a regular file."""
    try:
        mode = target.lstat().st_mode
    except FileNotFoundError:
        return None
    except OSError as exc:
        return f"could not be inspected ({exc.strerror}) — {_REPAIR}"

    if stat.S_ISREG(mode):
        return None
    what = "a directory" if stat.S_ISDIR(mode) else "something that is not a regular file"
    return f"{what} sits where Lore has to write a file — {_REPAIR}"


def _resolved(path: Path) -> Path:
    """*path* with every link followed, absolute, without needing it to exist.

    ``Path.resolve`` is non-strict here: it resolves the part of the path that
    is there and appends the rest, and it returns a looping path unresolved
    rather than raising. The ``OSError`` branch is for the filesystems that do
    raise anyway — an unreadable ancestor — where refusing is the right answer
    and an absolute lexical path is enough to produce one.
    """
    try:
        return Path(path).resolve()
    except OSError:  # pragma: no cover - platform dependent
        return Path(os.path.abspath(path))


# ---------------------------------------------------------------------------
# Writing — whole, or not at all
# ---------------------------------------------------------------------------


def atomic_write_bytes(
    target: Path, data: bytes, *, project_root: Path | None = None
) -> None:
    """Write *data* to *target*, creating its parents, replacing it whole.

    The bytes go to a temporary file in *target*'s own directory — the same
    filesystem, so the rename cannot fail across devices — and arrive by
    ``os.replace``. Nothing ever truncates the file that is there: a run
    interrupted mid-write, or a second process reading during one, finds the
    previous file intact.

    The mode of an existing file is carried across, so a skill the project made
    read-only stays read-only. Replacing a file needs write permission on its
    *directory* rather than on the file, which is why a `chmod 444` install no
    longer stops an upgrade that has to rewrite it.
    """
    target = Path(target)
    refuse_unsafe(target, project_root=project_root)

    mode = _mode_for(target)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        handle, name = tempfile.mkstemp(
            dir=target.parent, prefix=f".{target.name}.", suffix=_TEMP_SUFFIX
        )
    except OSError as exc:
        raise _write_failure(target, exc) from exc

    temporary = Path(name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
        os.chmod(temporary, mode)
        os.replace(temporary, target)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise _write_failure(target, exc) from exc
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def atomic_write_text(
    target: Path,
    text: str,
    *,
    encoding: str = "utf-8",
    project_root: Path | None = None,
) -> None:
    """``atomic_write_bytes`` for text. Lore writes UTF-8 and reads UTF-8."""
    atomic_write_bytes(target, text.encode(encoding), project_root=project_root)


def _mode_for(target: Path) -> int:
    """The permissions the written file should end up with."""
    try:
        return stat.S_IMODE(target.lstat().st_mode)
    except OSError:
        return 0o666 & ~_umask()


_umask_value: int | None = None


def _umask() -> int:
    """The process umask, read once.

    There is no way to read it without setting it, so this does the usual
    set-and-restore and remembers the answer rather than repeating the trick on
    every write.
    """
    global _umask_value
    if _umask_value is None:
        _umask_value = os.umask(0o022)
        os.umask(_umask_value)
    return _umask_value


def _write_failure(target: Path, exc: OSError) -> ValueError:
    """A filesystem refusal, as a message naming the file rather than a traceback.

    A read-only directory, a full disk and a name too long for the filesystem
    all arrive here. None of them is a Lore defect and all of them used to
    reach the terminal as a stack of stdlib frames with an empty stdout.
    """
    return ValueError(
        f"{target}: could not be written ({exc.strerror or exc}) — "
        "check the path and its permissions, then re-run"
    )
