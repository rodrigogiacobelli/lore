"""Three-way reconciliation — what `lore init` should do to each path.

Every `lore init` after the first is an upgrade, and the release now installed
ships a different file set from the one that installed the project. Rather than
a per-version migration chain — where each step becomes permanent code and a
0.8 → 0.14 hop has to replay all of them in order — this module asks what is
true rather than what changed::

    desired  = the paths and rendered bytes this release would write
    recorded = manifest.files and the historical hashes, ranked
    on_disk  = the bytes actually at each of those paths

One comparison, correct for any version hop including skipped releases and a
downgrade. Its last row is the safety property the whole mechanism exists to
hold: **a path in neither set is never read, never written and never deleted.**
The one file Lore reads that it did not install is a path it is about to write,
and hashing it first is exactly what turns a silent overwrite into a reported
conflict.

Inside those two sets the rule is the opposite one, and it is a product ruling
rather than an inference: **Lore owns its own files.** A file Lore installed and
still ships is rewritten however it has been edited, and one Lore installed and
has since retired is removed with its successor named. Neither asks. That is
already what happens to `.lore/knights/default/**`, `.lore/doctrines/default/**`,
`.lore/artifacts/default/**` and `.lore/watchers/default/**` — every one of them
overwritten in place on every run — and skills were the single tree that
behaved differently. The two rules meet at the same question, "did Lore install
here?", and the answer decides everything: yes means Lore's file, no means never
touched.

`REMOVE` is a hard unlink. `decisions-003-soft-delete-semantics` governs
entities the `lore` CLI manages — quests, missions, dependency rows and the file
entities with a `lore delete` path — and a skill is none of those: no ID
retrieval, no CRUD surface, no delete command for a soft-delete policy to
attach to. What stands in for that guarantee is the *record*: a path is
unlinked only when something says Lore installed it and this release no longer
ships it. The bytes there are not part of that test — under the ownership
ruling an edited retired file is removed like any other — so the record has to
be one that means it, which is why ``legacy_records`` admits a guess about a
path only from a tree it can prove Lore wrote into, and why the caller drops
the guess entirely once it holds a record of the project itself.

That is also why ``recorded`` is *ranked* rather than chosen. The manifest is a
record of what one run wrote and says nothing about what has happened since —
an older release re-initialising the project is the case that proves it — while
a historical-hash hit is a statement about the bytes that are there now. Both
speak about *this* project, so the caller merges them, strongest last;
``legacy_records`` keeps its grades of evidence apart so there is something to
rank, and so the grade that is only a guess about the tree can be left out
where a manifest already answers the question about the path.

That last guarantee is stated in terms of *paths*, and a symlink is exactly
where a path and a file stop being the same thing — so the third column of the
comparison has three states, not two, and ``lore.safewrite`` owns the question
of whether a path may be followed at all.

The module imports ``lore.initplan``, ``lore.manifest``, ``lore.agents`` and
``lore.safewrite`` and nothing else from ``lore`` — never ``init.py``, which is
the direction ``standards-dependency-inversion`` requires. ``agents`` is the
packaged registry, a sibling data module with no dependency of its own beyond
``initplan``; the legacy fallback reads it for the skills directories a
pre-manifest project could be holding. The two things this module would
otherwise have to take from above are injected as callables instead: the
retirement ledger from ``skills.py`` and the marker pair from ``init.py``.
"""

from __future__ import annotations

import functools
import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Container, Iterable, Mapping, Protocol

from lore import agents as agent_registry
from lore import manifest, safewrite
from lore.initplan import DesiredFile, FileAction, PlannedFile
from lore.manifest import RecordedEntry

PACKAGED_LEGACY_HASHES = "src/lore/defaults/legacy-hashes.json"
"""Where the historical hashes are authored — quoted in the build-defect message."""

LEGACY_SKILLS_ROOT = ".lore/skills"
"""Where Lore installed every pre-feature skill, and how the historical table is keyed."""

ON_CONFLICT_SKIP = "skip"
ON_CONFLICT_OVERWRITE = "overwrite"
ON_CONFLICT_TOKENS = (ON_CONFLICT_SKIP, ON_CONFLICT_OVERWRITE)

NOT_INSTALLED_BY_LORE = "not installed by Lore"
NO_LONGER_INSTALLED = "no longer installed here"

EDIT_DISCARDED = "your edit is discarded"
"""Said of every row that destroys something the project wrote.

Lore owning its own files means an edit to one is not a question, and that is
the ruling. It does not mean the loss goes unmentioned: the row that takes the
file back says so, and — for a skill — says where a copy of their own would
have survived.
"""

LORE_OWNS_THIS_FILE = f"{EDIT_DISCARDED} — Lore owns this file"
"""The overwrite detail for a Lore file with no "put yours elsewhere" to offer.

`.lore/LORE-AGENT.md`, an agent's marked block, a generated listing: there is
no second copy of any of them a project could keep, so the row states what
happened and stops.
"""

SECTION_KIND = "section"
OWNED_KIND = "owned"

SKILL_SOURCE_PREFIX = "skill:"
SKILLS_GITIGNORE_SOURCE_PREFIX = "skills-gitignore:"

LEGACY_SKILLS_GITIGNORE = ".gitignore"
"""The listing a pre-feature release wrote into the tree it installed skills in."""

LEGACY_FIXED_PATHS = {
    manifest.LORE_AGENT_PATH: "lore-agent",
}
"""Lore-installed files outside the skills trees, and the source that produces them.

The historical table was keyed on ``.lore/skills/**`` alone, so the one other
file every pre-manifest release wrote to a fixed path fell through to "unknown
provenance → keep" and an upgraded project kept its predecessor's agent
instructions for good — the file the coding agent actually reads, still
advertising the skills the same run had just deleted.
"""

_RESOURCE_PACKAGE = "lore.defaults"
_RESOURCE_NAME = "legacy-hashes.json"


class Retirement(Protocol):
    """The shape ``skills.retirement_for`` returns.

    Structural rather than imported: matching ``skills.Retirement`` by shape is
    what lets the ledger be injected without this module depending on the
    catalogue.
    """

    @property
    def into(self) -> str:
        """The skill that replaced the retired one."""

    @property
    def reason(self) -> str:
        """Quoted verbatim in the removal report."""


RetirementLookup = Callable[[str], "Retirement | None"]
"""``skills.retirement_for`` — a skill id in, a ``Retirement`` or ``None`` out."""

MarkerLookup = Callable[[str], tuple[str, str]]
"""``init._marker_pair`` — a repo-relative path in, its begin/end marker pair out."""


@dataclass(frozen=True)
class DiskState:
    """What the third column of the comparison found at one path.

    Three states rather than two. ``digest`` and its ``None`` are the original
    "these bytes" and "nothing there"; ``refusal`` is the one that was missing —
    *something is there and it is not a file Lore may touch*. Collapsing that
    third case into either of the other two is what let a write follow a symlink
    out of the project.
    """

    digest: str | None = None
    refusal: str | None = None


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------


def reconcile(
    desired: Mapping[str, DesiredFile],
    recorded: Mapping[str, RecordedEntry],
    project_root: Path,
    *,
    on_conflict: str = ON_CONFLICT_SKIP,
    retirement_reason: RetirementLookup | None = None,
    section_markers: MarkerLookup | None = None,
    installed_before: Container[str] = frozenset(),
) -> tuple[PlannedFile, ...]:
    """Classify every path in ``recorded ∪ desired``, sorted by path.

    *retirement_reason* is ``skills.retirement_for``, injected rather than
    imported so this module stays testable on synthetic data with no package
    fixtures. *section_markers* is the equivalent for ``init._marker_pair``, and
    is required only when a ``section`` entry has to be compared against a file
    that exists.

    *on_conflict* is a single answer for the whole run, and it governs exactly
    one thing: a path holding a file **Lore did not install**. ``skip``, the
    default, leaves it alone and reports it; ``overwrite`` performs the write
    the row would otherwise have carried. It has no say over Lore's own files —
    see *installed_before*.

    *installed_before* is every path some release of Lore is known to have
    installed to, whatever is there now — ``legacy_records(...).shipped_paths``
    on the pre-manifest path. Together with ``recorded`` it answers the only
    question this table asks about a file in the way: **is this path Lore's?**
    A file Lore installed and still ships is Lore's, so its bytes are replaced
    and the row says the edit went; a file Lore installed and has since retired
    is Lore's too, so it is removed and the row names the successor. Nobody is
    asked, because the same thing has always happened to `.lore/knights/default`
    and `.lore/doctrines/default` without anybody being asked.

    A project that predates the manifest has no record of a **current** skill it
    edited, because editing it is exactly what stops its bytes matching a
    shipped hash. Provenance is a different question from provenance of the
    *bytes*, and the shipped table answers it on its own — which is why
    *installed_before* exists and why it is enough on its own to settle the row.
    """
    if on_conflict not in ON_CONFLICT_TOKENS:
        raise ValueError(
            f"Unknown conflict policy: '{on_conflict}'. "
            f"Accepted tokens: {', '.join(ON_CONFLICT_TOKENS)}."
        )

    relocations = _skill_relocations(desired)
    rows = []
    for path in sorted(set(recorded) | set(desired)):
        want = desired.get(path)
        have = recorded.get(path)
        if want is not None:
            rows.append(
                _classify_desired(
                    path,
                    want,
                    have,
                    disk_state(project_root, path, want.kind, section_markers),
                    on_conflict=on_conflict,
                    shipped_here=path in installed_before,
                )
            )
        elif have is not None:
            row = _classify_retired(
                path,
                have,
                disk_state(project_root, path, have.kind, section_markers),
                retirement_reason=retirement_reason,
                relocations=relocations,
            )
            if row is not None:
                rows.append(row)
    return tuple(rows)


def _skill_relocations(desired: Mapping[str, DesiredFile]) -> dict[str, tuple[str, ...]]:
    """Where this release puts each skill, keyed by its ``skill:<id>`` source.

    A skill leaves a directory for two unrelated reasons — it was retired, or
    the answers moved the install root — and the two call for opposite
    responses from whoever reads the report. This is the evidence that tells
    them apart: a removed path whose source still appears in ``desired`` is a
    move, and this says where to.
    """
    roots: dict[str, set[str]] = {}
    for path, want in desired.items():
        if not want.source.startswith(SKILL_SOURCE_PREFIX):
            continue
        skill_id = want.source[len(SKILL_SOURCE_PREFIX) :]
        head, separator, _ = path.partition(f"/{skill_id}/")
        if separator:
            roots.setdefault(want.source, set()).add(head)
    return {source: tuple(sorted(dirs)) for source, dirs in roots.items()}


def _classify_desired(
    path: str,
    want: DesiredFile,
    have: RecordedEntry | None,
    state: DiskState,
    *,
    on_conflict: str,
    shipped_here: bool = False,
) -> PlannedFile:
    """The rows where this release wants to write *path*.

    *shipped_here* is the second grade of "Lore installed here", carrying the
    same weight as a record — see ``reconcile``.
    """
    kind, source = want.kind, want.source
    wanted = manifest.bytes_digest(want.content)
    create = _write_action(kind, FileAction.CREATE)
    replace = _write_action(kind, FileAction.OVERWRITE)

    if state.refusal is not None:
        # A link, or a path that resolves out of the project. Not a file Lore
        # installed and not a file Lore may write, so it is a conflict — and
        # one `on_conflict` does not settle. "Overwrite the file I edited" is
        # an answer about a file inside the project; performing it here would
        # write through the link, which is the escape itself.
        return _row(
            path,
            FileAction.CONFLICT,
            kind,
            source,
            digest=wanted,
            detail=state.refusal,
        )

    on_disk = state.digest
    if on_disk is None:
        # Absent, or the marked block is gone: create it, or restore it.
        return _row(path, create, kind, source, digest=wanted)

    if on_disk == wanted:
        # Already exactly what Lore would write. Recorded, but nothing to do.
        #
        # The recorded hash is not consulted: a file whose bytes are the ones
        # this release would put there needs no decision from anyone, however
        # they got there. A project that hand-applied the new content, and a run
        # interrupted after the write and before the manifest, both land here —
        # and calling either a conflict would report a write that would change
        # nothing, then drop the path from the next manifest, which is what
        # makes the run after that call it "not installed by Lore".
        return _row(
            path, create, kind, source, digest=wanted, reported=False, observed=on_disk
        )

    if have is not None and on_disk == have.hash:
        # Lore wrote it, nobody touched it, the content has moved on.
        return _row(path, replace, kind, source, digest=wanted, observed=on_disk)

    if have is not None or shipped_here:
        # Lore installed here and still ships this file, so the file is Lore's
        # and the bytes in it are not the question — the same answer the seeded
        # `default/` trees have always given. Either grade of evidence is
        # enough: a pre-manifest project cannot hold a record of a current
        # skill it edited, because editing it is what breaks the hash.
        return _row(
            path,
            replace,
            kind,
            source,
            digest=wanted,
            detail=_overwrite_detail(path, source),
            observed=on_disk,
        )

    if on_conflict == ON_CONFLICT_OVERWRITE:
        return _row(path, replace, kind, source, digest=wanted, observed=on_disk)

    # Nothing has ever installed to this path. The file is the project's own,
    # and this is the only row `on_conflict` still has anything to say about.
    return _row(
        path,
        FileAction.CONFLICT,
        kind,
        source,
        digest=wanted,
        detail=NOT_INSTALLED_BY_LORE,
        observed=on_disk,
    )


def _overwrite_detail(path: str, source: str) -> str:
    """Why the bytes at *path* are going, and where a copy of them would live.

    Knights, doctrines, artifacts and watchers are seeded under a ``default/``
    subdirectory, and that directory name is the whole explanation: Lore owns
    what is inside it, so a project's own version goes beside it rather than in
    it. Skills install straight into ``.claude/skills/`` with no such marker, so
    the convention that would have told somebody where to put their copy does
    not exist for the one tree that most needs it — and now that the edit is
    discarded rather than reported, this row is the only place they can be
    told. It names the directory, because the directory is the answer: a skill
    under an id Lore does not ship is one no run ever looks at.
    """
    root = _skill_root(path, source)
    if root is None:
        return LORE_OWNS_THIS_FILE
    return (
        f"{EDIT_DISCARDED} — Lore owns this skill; "
        f"put your own in {root}/<your-own-id>/"
    )


def _skill_root(path: str, source: str) -> str | None:
    """The directory *path*'s skill installs into, or ``None`` if it is no skill."""
    if not source.startswith(SKILL_SOURCE_PREFIX):
        return None
    skill_id = source[len(SKILL_SOURCE_PREFIX) :]
    head, separator, _ = path.partition(f"/{skill_id}/")
    return head if separator else None


def _write_action(kind: str, default: FileAction) -> FileAction:
    """Every write into a file the project owns is a ``SECTION``, whatever the row."""
    return FileAction.SECTION if kind == SECTION_KIND else default


def _classify_retired(
    path: str,
    have: RecordedEntry,
    state: DiskState,
    *,
    retirement_reason: RetirementLookup | None,
    relocations: Mapping[str, tuple[str, ...]] | None = None,
) -> PlannedFile | None:
    """The three rows where Lore installed *path* and no longer ships it.

    An edit buys nothing here. A file Lore installed is Lore's, and one Lore
    has retired is a directory no release ships any more — keeping it left the
    project holding a skill its agent still reads, whose successor nothing
    named. So it goes, and the row says where the thinking in it now belongs.
    """
    kind, source = have.kind, have.source
    if state.refusal is not None:
        # Whatever Lore installed here, this is not it any more. Unlinking a
        # link would destroy something the user made, and the hash that would
        # otherwise authorise the removal was read through it. Ownership
        # settles what happens to Lore's *file*; this is not that file.
        return _row(path, FileAction.CONFLICT, kind, source, detail=state.refusal)

    on_disk = state.digest
    if on_disk is None:
        # Already gone. Forget it: it leaves the next manifest and says nothing.
        return None

    return _row(
        path,
        FileAction.REMOVE,
        kind,
        source,
        detail=_removal_detail(
            source,
            _retirement(source, retirement_reason),
            relocations or {},
            edited=on_disk != have.hash,
        ),
        observed=on_disk,
    )


def _removal_detail(
    source: str,
    retirement: Retirement | None,
    relocations: Mapping[str, tuple[str, ...]],
    *,
    edited: bool = False,
) -> str | None:
    """Why *path* is being removed, in the words the reader needs.

    Three causes reach one report line and they are not interchangeable. A
    retirement asks the reader to port their thinking into the successor, so it
    names it — the ledger knows which skill replaced which and dropping that on
    the way out left ``lore-update → sync-codex-guide`` unguessable. A move asks
    for nothing and says where the file now lives. A deselected family asks for
    nothing either and says so, which is what stops "retired" and "uninstalled"
    from printing identically.

    A source with no ledger entry that is not a skill at all — an agent's
    instruction block, a gitignore listing — keeps its silence: the action word
    already says everything true about it.

    *edited* adds the one thing none of those three says. A removal that takes
    somebody's own words with it is still a removal, and under the ownership
    ruling it happens without being asked — which is precisely why the line has
    to admit it rather than read like an ordinary tidy-up.
    """
    if retirement is not None:
        reason = retirement.reason
        into = retirement.into
        base = reason if not into or into in reason else f"{reason} → {into}"
    elif not source.startswith(SKILL_SOURCE_PREFIX):
        base = None
    elif relocations.get(source):
        base = "moved to " + ", ".join(f"{root}/" for root in relocations[source])
    else:
        base = NO_LONGER_INSTALLED
    if not edited:
        return base
    return f"{base}; {EDIT_DISCARDED}" if base else EDIT_DISCARDED


def unsettled(rows: Iterable[PlannedFile]) -> tuple[PlannedFile, ...]:
    """The rows in *rows* that the ``on_conflict`` answer could still change.

    A conflict comes from one of two places and only one of them has a second
    answer. A file the project put where Lore wants to write can be handed over
    (``overwrite``) or left (``skip``); a path Lore refuses to follow — a
    symlink, an ancestor that resolves out of the project — reads the same in
    the plan and moves for neither answer, because performing the write *is*
    the escape.

    The prompt gate reads this. Offering a question whose every answer leaves
    the tree identical is worse than not asking: it tells somebody a decision
    is theirs when it is not.
    """
    return tuple(
        row
        for row in rows
        if row.action is FileAction.CONFLICT and row.detail == NOT_INSTALLED_BY_LORE
    )


def _row(
    path: str,
    action: FileAction,
    kind: str,
    source: str,
    *,
    digest: str | None = None,
    detail: str | None = None,
    reported: bool = True,
    observed: str | None = None,
) -> PlannedFile:
    return PlannedFile(
        path=path,
        action=action,
        kind=kind,
        source=source,
        digest=digest,
        detail=detail,
        reported=reported,
        observed=observed,
    )


def _retirement(source: str, lookup: RetirementLookup | None) -> Retirement | None:
    """Look the ledger up for a ``skill:<id>`` source. Anything else has no entry."""
    if lookup is None or ":" not in source:
        return None
    prefix, _, skill_id = source.partition(":")
    if prefix != "skill":
        return None
    return lookup(skill_id)


def disk_state(
    project_root: Path,
    path: str,
    kind: str,
    section_markers: MarkerLookup | None = None,
) -> DiskState:
    """What is at *path* now: a digest, an absence, or a reason to touch nothing.

    Public because ``apply_init`` asks it a second time, immediately before it
    writes: a plan's rows were all decided from this answer, so a tree where it
    has changed is not the tree the plan describes. Two implementations of "what
    is at this path" would be two ways for the plan and the write to disagree.

    The refusal comes first and is the only branch that reads nothing at all.
    A symlink was the case where "the path" and "the file" stopped being the
    same thing: hashing what it points at is what made a dangling link look
    absent and a live one look like an installed file Lore could overwrite, and
    both of those answers wrote outside the project. So the question asked here
    is about the path itself (``lstat``), before any content is looked at.

    Otherwise, for a ``section`` entry "what is at *path*" is the marked block
    alone, so a file whose block has been deleted reads as absent and the block
    is restored. That block is text, and the file holding it belongs to the
    project, so it is read through ``manifest.read_text`` — a recorded path can
    name something that will not decode, and a bare decoder error names no
    file. An ``owned`` entry is hashed as raw bytes and is never decoded at all.
    """
    target = manifest.resolve_path(project_root, path)
    refusal = safewrite.link_or_escape_reason(target, project_root=project_root)
    if refusal is not None:
        return DiskState(refusal=refusal)

    if not target.is_file():
        return DiskState()

    if kind != SECTION_KIND:
        return DiskState(digest=manifest.file_digest(target))

    if section_markers is None:
        raise ValueError(
            f"reconciling the section entry at {path} needs its marker pair; "
            "pass section_markers"
        )
    begin, end = section_markers(path)
    block = manifest.section_text(manifest.read_text(target), begin, end, source=target)
    if block is None:
        return DiskState()
    return DiskState(digest=manifest.bytes_digest(block.encode("utf-8")))


# ---------------------------------------------------------------------------
# Directory pruning
# ---------------------------------------------------------------------------


def prune_empty_dirs(removed_paths: Iterable[Path], stop_at: Path) -> tuple[Path, ...]:
    """Remove directories that *removed_paths* left empty, and return them sorted.

    Walks each removed path's ancestors upward, stopping at the first directory
    that still holds something or at *stop_at*, whichever comes first. *stop_at*
    itself is never removed, and a directory containing anything Lore did not
    install is by definition non-empty and survives. A path outside *stop_at* is
    never touched.

    Tidying is the least important thing an initialisation does, so it never
    costs anything else: a directory that cannot be removed is skipped and the
    walk moves to the next removed path. It used to be one unguarded pass —
    ``is_dir()`` follows a link and ``rmdir()`` does not, so a symlinked skill
    directory raised ``NotADirectoryError`` and abandoned every prune after it,
    leaving ten empty directories no later run had a removal left to clean up.
    """
    pruned: set[Path] = set()
    for removed in removed_paths:
        candidate = Path(removed).parent
        while _is_prunable(candidate, stop_at):
            try:
                candidate.rmdir()
            except OSError:
                break
            pruned.add(candidate)
            candidate = candidate.parent
    return tuple(sorted(pruned))


def _is_prunable(candidate: Path, stop_at: Path) -> bool:
    """True when *candidate* is an empty directory strictly inside *stop_at*.

    "Inside" is tested twice: lexically, and again on the resolved paths, so a
    linked directory cannot present a chain of ancestors that climbs out of the
    tree this prune was given. A link is never itself removed — it is not a
    directory Lore created, whatever it points at.
    """
    if candidate == stop_at or not candidate.is_relative_to(stop_at):
        return False
    if candidate.is_symlink() or not candidate.is_dir():
        return False
    resolved, root = candidate.resolve(), stop_at.resolve()
    if resolved == root or not resolved.is_relative_to(root):
        return False
    try:
        return not any(candidate.iterdir())
    except OSError:
        return False


# ---------------------------------------------------------------------------
# The legacy fallback — a project that predates the manifest
# ---------------------------------------------------------------------------


def legacy_skills_roots() -> tuple[str, ...]:
    """Every tree a project that predates the manifest could be holding a skill in.

    ``.lore/skills/`` is where Lore wrote them. The rest are the ``skills_dir``
    values of the packaged registry, because the pre-feature
    ``GETTING-STARTED.md`` shipped ``cp -r .lore/skills/. .claude/skills/`` —
    so the documented workflow put a copy of every skill in the agent's own
    directory, and a fallback that walks only ``.lore/skills/`` cannot reach the
    people who followed the instructions.

    Every registry row is a root, not only the agents selected this run: a
    project that copied into ``.claude/skills/`` and now initialises for Gemini
    still needs the stale directories gone.
    """
    roots = {LEGACY_SKILLS_ROOT}
    roots.update(row.skills_dir for row in agent_registry.load_registry() if row.skills_dir)
    return tuple(sorted(roots))


@dataclass(frozen=True)
class LegacyRecords:
    """What the historical table found on disk, in two grades of evidence.

    They are kept apart because a caller merging them with an install manifest
    has to rank all three, and the two halves do not rank the same way.
    """

    installed: dict[str, RecordedEntry]
    """Paths whose bytes *are* bytes Lore shipped there. The strongest record
    anything can hold: it answers "did somebody edit this?" with something the
    disk agrees with right now, which a manifest hash — true when it was
    written, and silent about everything since — cannot."""

    retired_edits: dict[str, RecordedEntry]
    """Paths Lore shipped, holding bytes it never did, for skills it has since
    retired. The weakest record: it establishes only that the path is Lore's,
    and is never enough to outrank something that knows the bytes.

    Admitted only from a tree that also yielded an ``installed`` hit, which is
    the same evidence test ``shipped_paths`` applies and for the same reason.
    Under the ownership ruling this record authorises a **removal** rather than
    a report, so "the historical table has a row at this name" stopped being
    enough on its own: a project that wrote its own `new-rite/SKILL.md` in a
    directory holding nothing of Lore's would have had it deleted.

    A tree gate is still not a path gate, and it is the last resort rather than
    the rule: a caller holding an install manifest knows what Lore installed
    *here* and drops this mapping unread. See ``init._recorded_entries``."""

    shipped_paths: frozenset[str] = frozenset()
    """Paths in a tree Lore installed into, that Lore installs to, whatever the
    bytes there are now.

    Not a record and never merged into one: it authorises nothing, carries no
    hash and cannot decide an action. It answers the one question the two
    mappings above cannot, because both of them are about *bytes* — has Lore
    ever installed to this path at all. A conflict on a **current** skill in a
    pre-manifest project is the case that needs it: no record can exist there,
    since editing the file is what stops its bytes matching a shipped hash, and
    the run said "not installed by Lore" about a file Lore installed.

    A skills root holding nothing Lore shipped contributes nothing here, and
    neither does a fixed path in a project holding nothing Lore shipped. That
    is the difference between "this tree is one Lore installed into and this
    file in it has been edited" and "this project wrote its own file at a name
    Lore happens to use", and only the first is evidence of anything.

    Evidence about a *tree* is still not evidence about a *path*, which is why
    a caller holding a real record of this project — an install manifest —
    drops this set rather than merging it. See ``init._recorded_entries``."""

    def merged(self) -> dict[str, RecordedEntry]:
        """Both halves as one mapping, the stronger grade winning."""
        return {**self.retired_edits, **self.installed}


def legacy_records(
    project_root: Path, *, retirement_reason: RetirementLookup | None = None
) -> LegacyRecords:
    """Rebuild what Lore installed from the hashes it has shipped.

    Walks every root in ``legacy_skills_roots`` that exists on disk, plus the
    handful of fixed paths in ``LEGACY_FIXED_PATHS``. A file whose on-disk hash
    appears in the historical set for its path is one Lore installed and nobody
    edited, and lands in ``installed``.

    Anything else is left out: an unknown path, or a known path whose hash
    matches no shipped version, falls into the never-touched row and stays. The
    bias errs toward keeping files, which is the correct direction when the
    evidence is incomplete.

    *retirement_reason* buys the one exception, and it lands in
    ``retired_edits``. A **retired** skill at a path Lore shipped, whose bytes
    match no shipped hash, is admitted with a shipped digest as its record —
    which by construction cannot equal what is on disk, so it can only ever be
    classified as edited. That is what makes it a file the run acts on rather
    than one nobody mentions: the rule was inverted before, and editing a
    retired skill was what disqualified you from being told where its successor
    went. Under the ownership ruling it is now removed with the successor
    named, which is why its admission is gated on the tree — see
    ``LegacyRecords.retired_edits``.
    """
    table = load_legacy_hashes()
    installed: dict[str, RecordedEntry] = {}
    retired_edits: dict[str, RecordedEntry] = {}
    shipped: set[str] = set()
    for root in legacy_skills_roots():
        found, edited, known = _recorded_under(
            project_root, root, table, retirement_reason
        )
        installed.update(found)
        retired_edits.update(edited)
        shipped.update(known)
    fixed = _recorded_at_fixed_paths(project_root, table)
    installed.update(fixed)
    if installed:
        # The same gate the skills roots apply, asked of the project rather
        # than of one tree: a fixed path is Lore's file only where something
        # here proves Lore installed at all. These keys used to be added
        # unconditionally, so a hand-written `.lore/LORE-AGENT.md` in a
        # directory Lore has never written to was claimed on no evidence
        # whatever — the identical question its skills-tree sibling asks,
        # answered by a different rule.
        shipped.update(path for path in LEGACY_FIXED_PATHS if path in table)
    return LegacyRecords(
        installed=installed,
        retired_edits=retired_edits,
        shipped_paths=frozenset(shipped),
    )


def legacy_recorded(project_root: Path) -> dict[str, RecordedEntry]:
    """The paths the historical table proves Lore installed and nobody edited.

    ``legacy_records(...).installed`` under the name it has always had — the
    ``recorded`` half of the comparison for a project that predates the
    manifest, with no retirement widening because a caller taking one mapping
    has nowhere to rank a weaker grade of evidence against.
    """
    return legacy_records(project_root).installed


def skills_gitignore_source(root: str) -> str:
    """The source token for the generated listing at the top of *root*.

    The agent whose native directory this is, or ``lore`` for the fallback tree
    every agent without one shares. Public because ``init.build_desired`` names
    the file it is about to write and the legacy walk names the file it found,
    and a listing recognised under two different tokens would be removed by one
    run and re-created by the next.
    """
    for row in agent_registry.load_registry():
        if row.skills_dir == root:
            return f"{SKILLS_GITIGNORE_SOURCE_PREFIX}{row.id}"
    return f"{SKILLS_GITIGNORE_SOURCE_PREFIX}lore"


def _legacy_source(root: str, within: PurePosixPath) -> str:
    """The source token for a file found under a legacy skills root.

    Everything in these trees is a skill file except the generated listing at
    the top of one, which Lore writes and its own header says so — so it is not
    the user's file to keep, however it got copied there.
    """
    if len(within.parts) == 1 and within.name == LEGACY_SKILLS_GITIGNORE:
        return skills_gitignore_source(root)
    return f"{SKILL_SOURCE_PREFIX}{within.parts[0]}"


def _recorded_under(
    project_root: Path,
    root: str,
    table: Mapping[str, tuple[str, ...]],
    retirement_reason: RetirementLookup | None = None,
) -> tuple[dict[str, RecordedEntry], dict[str, RecordedEntry], set[str]]:
    """The hits under one skills root, as ``(installed, retired_edits, shipped)``.

    The table is keyed by the path Lore *installed* to, so a candidate at
    ``<root>/<rel>`` is looked up as ``.lore/skills/<rel>``; the ``RecordedEntry``
    carries the candidate's real path, which is what a removal has to target.

    The lookup comes before the hash, so a path Lore never shipped is never even
    read — widening the walk cannot widen what gets touched.

    An exact hit records its own digest: Lore wrote these bytes and nobody has
    touched them. A miss on a **retired** skill records a shipped digest
    instead, which cannot match what is on disk and so states the true thing —
    Lore installed this path, the bytes are somebody else's now. A miss on
    anything else is not admitted at all; ``known`` carries those, which is all
    the evidence a path this release still writes needs.

    Both admissions are gated on the same question, asked of the *tree* rather
    than the path: does anything under this root prove Lore installed here? A
    matching hash proves it. Nothing else does — a project that authored its
    own `inquest/SKILL.md` in a directory Lore has never written to is not a
    project Lore may take that file from, whatever the historical table happens
    to hold at that name (FR-28).
    """
    installed: dict[str, RecordedEntry] = {}
    retired_edits: dict[str, RecordedEntry] = {}
    known: set[str] = set()
    skills_root = manifest.resolve_path(project_root, root)
    if not skills_root.is_dir():
        return installed, retired_edits, known

    for candidate in sorted(skills_root.rglob("*")):
        # A link is never adopted into the recorded set, however its target
        # hashes: what the fallback records is what a later run may remove.
        if candidate.is_symlink() or not candidate.is_file():
            continue
        within = PurePosixPath(candidate.relative_to(skills_root).as_posix())
        shipped = table.get(f"{LEGACY_SKILLS_ROOT}/{within}")
        if not shipped:
            continue
        relative = f"{root}/{within}"
        known.add(relative)
        source = _legacy_source(root, within)
        digest = manifest.file_digest(candidate)
        exact = digest in shipped
        if not exact and _retirement(source, retirement_reason) is None:
            continue
        into = installed if exact else retired_edits
        into[relative] = RecordedEntry(
            path=relative,
            kind=OWNED_KIND,
            source=source,
            hash=digest if exact else shipped[0],
        )
    if not installed:
        # Not one file under this root is a file Lore shipped, so this is not a
        # tree Lore installed into — and a path in it that happens to be one
        # Lore *would* install to is somebody else's file at that name. Saying
        # otherwise would tell a project that authored its own `inquest/SKILL.md`
        # that Lore installed it, which is the FR-28 statement inverted.
        #
        # `retired_edits` is cleared for the same reason and only became urgent
        # with the ownership ruling: it used to authorise a report and now
        # authorises an unlink, and "the table has a row at this name" was never
        # evidence that Lore wrote to this name *here*.
        known.clear()
        retired_edits.clear()
    return installed, retired_edits, known


def _recorded_at_fixed_paths(
    project_root: Path, table: Mapping[str, tuple[str, ...]]
) -> dict[str, RecordedEntry]:
    """The hash hits among the Lore-installed files outside the skills trees.

    Exact matches only, with no retirement widening: every one of these paths is
    a file this release still writes, so an unmatched hash is the user's edit
    and stays the conflict it is.
    """
    found: dict[str, RecordedEntry] = {}
    for path, source in LEGACY_FIXED_PATHS.items():
        shipped = table.get(path)
        if not shipped:
            continue
        target = manifest.resolve_path(project_root, path)
        if target.is_symlink() or not target.is_file():
            continue
        digest = manifest.file_digest(target)
        if digest not in shipped:
            continue
        found[path] = RecordedEntry(
            path=path, kind=OWNED_KIND, source=source, hash=digest
        )
    return found


def _read_legacy_payload() -> Any:
    """Parse the packaged historical-hash file.

    The single read step, so a test can inject a payload without touching the
    shipped file.
    """
    text = resources.files(_RESOURCE_PACKAGE).joinpath(_RESOURCE_NAME).read_text(encoding="utf-8")
    return json.loads(text)


@functools.lru_cache(maxsize=1)
def load_legacy_hashes() -> dict[str, tuple[str, ...]]:
    """Return the packaged path → historical digests table.

    Raises ``RuntimeError`` naming the packaged file when it is missing or does
    not parse — a release that ships no historical hashes is a build defect,
    never a user error.
    """
    try:
        payload = _read_legacy_payload()
    except (OSError, ValueError) as exc:
        raise _build_defect(f"{exc}") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("files"), dict):
        raise _build_defect("must be an object carrying a 'files' object")

    return {path: tuple(hashes) for path, hashes in payload["files"].items()}


def _build_defect(reason: str) -> RuntimeError:
    """A shipped file that will not load is a build defect, never a user error."""
    return RuntimeError(f"{PACKAGED_LEGACY_HASHES}: {reason}")
