"""Plan and result types for `lore init`.

``plan_init`` computes what an initialisation would do and returns an
``InitPlan``; ``apply_init`` performs one and returns an ``InitResult``. The
vocabulary both use lives here rather than in ``init.py`` because ``reconcile``
and ``skills`` construct ``PlannedFile`` values and ``init`` imports both — the
types have to sit below all three (standards-dependency-inversion).

Stdlib only. This module imports nothing from ``lore``, which keeps it the leaf
of the initialisation dependency graph and keeps ``import lore.initplan`` cheap
enough for ``cli.py`` to reach at decorator time.

Every type is frozen: a plan a caller has inspected is the plan that gets
applied.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class AccessMode(StrEnum):
    """Which command layer a project's installed skills are rendered with."""

    CLI = "cli"
    NATIVE = "native"


class FileAction(StrEnum):
    """What an initialisation would do to one path."""

    CREATE = "create"
    """Not on disk, or on disk and byte-identical to what Lore would write."""

    OVERWRITE = "overwrite"
    """Lore installed it and this release ships different bytes for it.

    Whether the project edited it since is not part of the test: the file is
    Lore's, and the row that replaces an edited one says so in its detail.
    """

    SECTION = "section"
    """A marked block inside a file the user owns."""

    REMOVE = "remove"
    """Lore installed it and this release no longer ships it."""

    CONFLICT = "conflict"
    """Something Lore did not install, or may not touch, is in the way.

    The one thing an initialisation reports and does not act on. A file Lore
    installed is Lore's whatever has been done to it since — overwritten if
    this release still ships it, removed if it has been retired — so the rows
    left here are a path holding a file the project put there and a path Lore
    refuses to follow, such as a symlink.
    """


WRITING_ACTIONS = frozenset(
    {FileAction.CREATE, FileAction.OVERWRITE, FileAction.SECTION, FileAction.REMOVE}
)
"""The actions that change the working tree. ``CONFLICT`` alone only reports."""


SUMMARY_ACTIONS: dict[FileAction, str] = {
    FileAction.CREATE: "create",
    FileAction.SECTION: "section",
    FileAction.OVERWRITE: "overwrite",
    FileAction.REMOVE: "remove",
    FileAction.CONFLICT: "conflict",
}
"""What each action is called when a plan is tallied.

It lives here rather than beside ``render_plan`` because ``InitPlan.counts`` and
the rendered summary have to agree, and a second table is a second way to
disagree — which is exactly what they did (round 5, defect 9): ``counts()``
reported 17 changes for a plan the summary printed as five zeroes.
"""

SUMMARY_ORDER = ("create", "section", "overwrite", "remove", "conflict")
"""The counts line, in a fixed order, so two runs of the same project compare.

The reconciled half only. The seeded files are counted under
:data:`SEED_COUNT`, which the plan reports in its own block with its own total
— they take no conflict and are never left alone, so tallying them beside the
decisions the run made would say they were decisions too.
"""

SEED_COUNT = "seed"
"""The ``counts()`` bucket for the files refreshed in place, outside the table.

``InitPlan.seeded`` names roughly seventy of them on every run — the packaged
``default/`` trees, the copied docs, the database, the config and the manifest.
They were in the rendered plan and in neither ``counts()`` nor ``has_changes``,
so a run about to overwrite an edited ``.lore/knights/default/…`` file reported
no changes to every caller that asks in Python. The CLI reads the render and
Realm reads the predicate; both are told now.
"""


@dataclass(frozen=True)
class AgentTarget:
    """One coding agent's file conventions, as shipped in the agent registry."""

    id: str
    label: str
    instruction_file: str | None
    """Repo-root-relative POSIX path, or None when the agent has no instruction file."""

    skills_dir: str | None
    """Repo-root-relative POSIX path, or None when skills go to ``.lore/skills/``."""


@dataclass(frozen=True)
class DesiredFile:
    """One path this release would write, and the bytes it would put there.

    The ``desired`` half of the reconciliation comparison, produced from the
    answers before anything on disk is looked at. ``content`` is the rendered
    bytes — after access-mode selection for a skill, and the marked block alone
    for a ``section`` entry, which is what makes its digest comparable with the
    block extracted from the file on disk.
    """

    path: str
    """Repo-root-relative POSIX path."""

    kind: str
    """``"owned"`` — Lore writes the whole file. ``"section"`` — a marked block inside it."""

    source: str
    """What produced it: ``"skill:store-memory"``, ``"agent-instructions:claude"``, …"""

    content: bytes


@dataclass(frozen=True)
class PlannedFile:
    """One path an initialisation would act on."""

    path: str
    """Repo-root-relative POSIX path."""

    action: FileAction
    kind: str
    """``"owned"`` — Lore wrote the whole file. ``"section"`` — a marked block inside it."""

    source: str
    """What produced it: ``"skill:store-memory"``, ``"agent-instructions:claude"``, …"""

    digest: str | None
    """``sha256:…`` of the rendered bytes. None for REMOVE, and for a conflict
    on a path this release no longer writes."""

    detail: str | None
    """The ledger reason for a removal, or the explanation for a conflict."""

    reported: bool = True
    """Whether this row is worth telling the human about.

    The reconciliation table has two columns, and this is the second one. A file
    already byte-identical to what Lore would write still belongs in the
    manifest — otherwise the next run forgets Lore installed it — but it changes
    nothing, so it is neither summarised nor counted as a change.
    """

    observed: str | None = None
    """``sha256:…`` of what was at ``path`` when the plan was computed, or None.

    None means "nothing was there" — an absent file, or a ``section`` entry
    whose marked block was missing. It is the third column of the reconciliation
    comparison, kept on the row so ``apply_init`` can ask whether that column is
    still true before it writes.

    Every decision on this row was taken from this value, so a plan applied to a
    tree where it no longer holds is a plan describing a different tree. The
    conflict machinery exists to turn a silent overwrite into a reported one and
    it used to run at plan time only, which left the window between a plan and
    its confirm — however long a programmatic caller holds one — as the one
    place an edit was destroyed without a word.
    """


@dataclass(frozen=True)
class InitAnswers:
    """The resolved answer to every question `lore init` can ask."""

    agents: tuple[str, ...]
    access_mode: AccessMode
    skill_families: tuple[str, ...]
    on_existing_agent_file: str
    """``"append"`` | ``"skip"``"""

    skills_gitignore: str
    """``"lore-only"`` | ``"none"`` | ``"all"``"""

    on_conflict: str
    """``"skip"`` | ``"overwrite"`` — what to do with a path holding something
    Lore did not install. It has no say over Lore's own files."""


@dataclass(frozen=True)
class InitPlan:
    """What an initialisation would do, computed without performing any of it."""

    project_root: Path
    answers: InitAnswers
    targets: tuple[AgentTarget, ...]
    files: tuple[PlannedFile, ...]
    """Sorted by path."""

    prompts_needed: tuple[str, ...]
    """The conditional prompts this plan justifies, for the CLI to ask and re-plan."""

    seeded: tuple[str, ...] = ()
    """Repo-relative paths the run writes that reconciliation does not manage.

    Lore's own files inside `.lore/`: the seeded ``default/`` trees, the copied
    docs, the database and the manifest. They carry no hash, take no conflict
    and are refreshed in place on every run — which is why they are a separate
    tuple from ``files`` rather than rows in it. They are named because the plan
    is what the confirm gate shows, and a plan that listed only the tracked half
    asked for consent to a fraction of the writes.
    """

    unstated_uninstall: str | None = None
    """Why this plan may not be applied, when it uninstalls without being asked to.

    Set by ``plan_init`` for the one plan whose damage nobody on this run
    consented to: every agent deselected, files Lore installed for an agent
    about to be removed, and no ``--agent none`` on the run performing it.
    ``apply_init`` raises it rather than writing.

    It is a field on the plan rather than an exception out of ``plan_init``
    because a plan is a description: ``--dry-run`` and a programmatic caller
    both get to *see* the refusal and the removals it covers, and only the
    attempt to apply one stops.

    Deselecting every agent is the only answer whose effect is purely
    destructive, and smoke testing reached it twice without anybody asking —
    once from an unanswered question, once from a config value the loader could
    not use. Guarding each route as it was found is what let there be a second
    one, so this guards the *outcome*: whatever produced the empty selection, a
    run that uninstalls everything says so on its own command line.
    """

    conflicts: tuple[PlannedFile, ...] = ()
    """The ``FileAction.CONFLICT`` subset of ``files``, in ``files`` order.

    Derived from ``files`` so the two can never disagree — the conflict gate
    reads this and the summary reads ``files``.

    One tuple, because there is one kind of conflict left. There used to be a
    second — a retired file the project had edited — and it needed its own,
    because the single ``on_conflict`` answer meant two different things across
    the two. Lore's own files are no longer settled by an answer at all, so the
    split has nothing left to keep apart.
    """

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "conflicts",
            tuple(entry for entry in self.files if entry.action is FileAction.CONFLICT),
        )

    @property
    def has_changes(self) -> bool:
        """True when applying this plan would write, replace or remove anything.

        Both halves of the plan, because the run writes both. An unreported
        writing row is a file already exactly as Lore would write it, so it is
        not a change; a ``seeded`` path is refreshed in place whatever is there,
        so it always is one. Answering for the reconciled half alone said "no
        changes" about a run that then overwrote seventy files, several of them
        edited.
        """
        return bool(self.seeded) or any(
            entry.action in WRITING_ACTIONS and entry.reported for entry in self.files
        )

    def counts(self) -> dict[str, int]:
        """Tally the reported rows per summary word. Zeroes are absent.

        The same numbers ``render_plan`` prints, from the same table: an
        unreported row is a file already exactly as Lore would write it, so it
        is a change in neither. The seeded files land in :data:`SEED_COUNT` —
        the block the render gives them, with the total it prints there.
        """
        tally = Counter(
            SUMMARY_ACTIONS[entry.action] for entry in self.files if entry.reported
        )
        if self.seeded:
            tally[SEED_COUNT] = len(self.seeded)
        return dict(tally)


@dataclass(frozen=True)
class InitResult:
    """What an applied initialisation did."""

    project_root: Path
    messages: tuple[str, ...]
    """The lines ``run_init()`` returns."""

    applied: tuple[PlannedFile, ...]
    skipped: tuple[PlannedFile, ...]
    manifest_path: Path
