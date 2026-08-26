"""Unit tests for lore.reconcile — the three-way reconciliation table.

``reconcile`` compares what this release would write (``desired``), what Lore
recorded writing last time (``recorded``) and the bytes actually on disk, and
returns one outcome per path. There is no migration chain: the same comparison
is correct for any version hop, forward or back.

The safety property under test throughout is the last row of the table — a path
in neither set is never read, never written and never deleted.

``legacy_recorded`` builds a synthetic ``recorded`` set for a project that
predates the manifest, and ``prune_empty_dirs`` clears the directories removals
leave behind.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lore import manifest, reconcile
from lore.initplan import DesiredFile, FileAction
from lore.manifest import RecordedEntry
from lore.skills import Retirement

BEGIN = "<!-- lore:begin -->"
END = "<!-- lore:end -->"

LEDGER = {
    "old-skill": Retirement(into="new-skill", reason="renamed"),
    "merged-skill": Retirement(into="store-memory", reason="merged into store-memory"),
}


def ledger(skill_id: str) -> Retirement | None:
    return LEDGER.get(skill_id)


def markers(path: str) -> tuple[str, str]:
    return BEGIN, END


def desired_file(
    path: str, content: bytes, *, kind: str = "owned", source: str = "skill:demo"
) -> DesiredFile:
    return DesiredFile(path=path, kind=kind, source=source, content=content)


def recorded_entry(
    path: str, digest: str, *, kind: str = "owned", source: str = "skill:old-skill"
) -> RecordedEntry:
    return RecordedEntry(path=path, kind=kind, source=source, hash=digest)


def plant(root: Path, path: str, content: bytes) -> Path:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def single_row(rows):
    """Assert the reconciliation produced exactly one outcome, and return it."""
    assert len(rows) == 1, rows
    return rows[0]


# ---------------------------------------------------------------------------
# The eleven rows of the table
# ---------------------------------------------------------------------------


class TestNotRecordedButDesired:
    def test_absent_on_disk_is_a_reported_create(self, tmp_path):
        desired = {"a/SKILL.md": desired_file("a/SKILL.md", b"new")}
        row = single_row(reconcile.reconcile(desired, {}, tmp_path))

        assert row.action is FileAction.CREATE
        assert row.reported is True
        assert row.digest == manifest.bytes_digest(b"new")

    def test_already_byte_identical_on_disk_is_an_unreported_create(self, tmp_path):
        plant(tmp_path, "a/SKILL.md", b"same")
        desired = {"a/SKILL.md": desired_file("a/SKILL.md", b"same")}
        row = single_row(reconcile.reconcile(desired, {}, tmp_path))

        assert row.action is FileAction.CREATE
        assert row.reported is False

    def test_different_bytes_on_disk_is_a_conflict_not_installed_by_lore(self, tmp_path):
        plant(tmp_path, "a/SKILL.md", b"mine")
        desired = {"a/SKILL.md": desired_file("a/SKILL.md", b"theirs")}
        row = single_row(reconcile.reconcile(desired, {}, tmp_path))

        assert row.action is FileAction.CONFLICT
        assert row.detail == "not installed by Lore"
        assert row.reported is True

    def test_the_conflicting_file_is_left_on_disk_untouched(self, tmp_path):
        target = plant(tmp_path, "a/SKILL.md", b"mine")
        desired = {"a/SKILL.md": desired_file("a/SKILL.md", b"theirs")}
        reconcile.reconcile(desired, {}, tmp_path)

        assert target.read_bytes() == b"mine"


class TestAPathLoreShippedButCannotProve:
    """The third grade of evidence: Lore installed here, the bytes are not its.

    A pre-manifest project has no record but the packaged historical table,
    which admits a path only when its bytes match one Lore shipped. Editing a
    **current** skill is exactly what disqualifies it, so the run had no record
    of a file Lore installed — round 7's N5, and round 6's F8 in a different
    place. "Was this path ever ours" is a question the shipped table answers on
    its own, and under the ownership ruling it is the whole question: a path
    Lore installed to and still ships is Lore's, so its bytes are replaced.
    """

    def test_a_path_lore_shipped_is_overwritten_rather_than_reported(self, tmp_path):
        plant(tmp_path, "a/SKILL.md", b"mine")
        desired = {"a/SKILL.md": desired_file("a/SKILL.md", b"theirs")}

        row = single_row(
            reconcile.reconcile(
                desired, {}, tmp_path, installed_before={"a/SKILL.md"}
            )
        )

        assert row.action is FileAction.OVERWRITE
        assert row.digest == manifest.bytes_digest(b"theirs")

    def test_a_path_lore_never_shipped_still_reads_as_not_installed(self, tmp_path):
        plant(tmp_path, "a/SKILL.md", b"mine")
        desired = {"a/SKILL.md": desired_file("a/SKILL.md", b"theirs")}

        row = single_row(
            reconcile.reconcile(desired, {}, tmp_path, installed_before={"b/SKILL.md"})
        )

        assert row.action is FileAction.CONFLICT
        assert row.detail == reconcile.NOT_INSTALLED_BY_LORE

    def test_n5_cannot_recur_for_the_class_that_is_left(self, tmp_path):
        """`not installed by Lore` is now said of exactly one thing, and truly.

        N5 was that sentence printed about a file Lore installed. The only row
        that can still print it is one with neither grade of evidence behind
        it — no manifest record and no shipped path — which is the definition
        of a file Lore never installed.
        """
        plant(tmp_path, "a/SKILL.md", b"mine")
        desired = {"a/SKILL.md": desired_file("a/SKILL.md", b"theirs")}
        recorded = {
            "a/SKILL.md": recorded_entry("a/SKILL.md", manifest.bytes_digest(b"was"))
        }

        with_record = single_row(reconcile.reconcile(desired, recorded, tmp_path))
        with_shipped = single_row(
            reconcile.reconcile(desired, {}, tmp_path, installed_before={"a/SKILL.md"})
        )

        assert reconcile.NOT_INSTALLED_BY_LORE not in (
            with_record.detail,
            with_shipped.detail,
        )

    def test_an_unedited_path_is_unaffected(self, tmp_path):
        plant(tmp_path, "a/SKILL.md", b"same")
        desired = {"a/SKILL.md": desired_file("a/SKILL.md", b"same")}

        row = single_row(
            reconcile.reconcile(
                desired, {}, tmp_path, installed_before={"a/SKILL.md"}
            )
        )

        assert row.reported is False

    def test_the_default_is_the_old_answer(self, tmp_path):
        """Nothing is claimed without evidence: the argument is opt-in."""
        plant(tmp_path, "a/SKILL.md", b"mine")
        desired = {"a/SKILL.md": desired_file("a/SKILL.md", b"theirs")}

        row = single_row(reconcile.reconcile(desired, {}, tmp_path))

        assert row.detail == reconcile.NOT_INSTALLED_BY_LORE


class TestLegacyRecordsNamesThePathsInATreeItInstalledInto:
    """`legacy_records` knows which paths the shipped table covers; it used to
    keep that to itself, so the caller could not tell "never ours" from "ours,
    edited".

    Naming a path is claiming the *path*, never the bytes — but under the
    ownership ruling that is the whole decision, so the claim is gated on the
    *tree*: a root yielding no exact match at all is not a root Lore wrote into,
    and a project that authored its own file at a name Lore uses keeps it.
    """

    def _records(self, tmp_path, monkeypatch, table):
        monkeypatch.setattr(
            reconcile, "_read_legacy_payload", lambda: {"files": table}
        )
        reconcile.load_legacy_hashes.cache_clear()
        try:
            return reconcile.legacy_records(tmp_path)
        finally:
            reconcile.load_legacy_hashes.cache_clear()

    def _installed_tree(self, tmp_path) -> dict[str, list[str]]:
        """A skills root holding one file at bytes Lore shipped, and one edited."""
        pristine = plant(tmp_path, ".lore/skills/kept/SKILL.md", b"as shipped")
        plant(tmp_path, ".lore/skills/current/SKILL.md", b"edited")
        return {
            ".lore/skills/kept/SKILL.md": [manifest.file_digest(pristine)],
            ".lore/skills/current/SKILL.md": ["sha256:whatever-lore-shipped"],
        }

    def test_a_shipped_path_with_edited_bytes_is_named(self, tmp_path, monkeypatch):
        table = self._installed_tree(tmp_path)

        records = self._records(tmp_path, monkeypatch, table)

        assert ".lore/skills/current/SKILL.md" in records.shipped_paths
        assert ".lore/skills/current/SKILL.md" not in records.installed

    def test_the_edited_file_is_still_left_on_disk(self, tmp_path, monkeypatch):
        table = self._installed_tree(tmp_path)

        self._records(tmp_path, monkeypatch, table)

        target = tmp_path / ".lore" / "skills" / "current" / "SKILL.md"
        assert target.read_bytes() == b"edited"

    def test_a_path_the_table_does_not_know_is_not_named(self, tmp_path, monkeypatch):
        table = self._installed_tree(tmp_path)
        plant(tmp_path, ".lore/skills/mine/SKILL.md", b"mine")

        records = self._records(tmp_path, monkeypatch, table)

        assert ".lore/skills/mine/SKILL.md" not in records.shipped_paths

    def test_a_tree_holding_nothing_lore_shipped_names_nothing(
        self, tmp_path, monkeypatch
    ):
        """FR-28 the right way round: a project's own file at a name Lore uses
        is not evidence that Lore ever installed here."""
        plant(tmp_path, ".lore/skills/current/SKILL.md", b"my own skill")
        table = {".lore/skills/current/SKILL.md": ["sha256:whatever-lore-shipped"]}

        records = self._records(tmp_path, monkeypatch, table)

        assert records.shipped_paths == frozenset()

    def test_a_fixed_path_with_nothing_to_vouch_for_it_is_not_named(
        self, tmp_path, monkeypatch
    ):
        """The skills half of this walk asks for evidence; this half did not.

        `LEGACY_FIXED_PATHS` added its keys to the claimed set unconditionally,
        so a hand-written `.lore/LORE-AGENT.md` in a directory Lore has never
        written to was claimed on nothing at all — the identical question
        ("did Lore install here?") answered by two different rules.
        """
        target = plant(tmp_path, ".lore/LORE-AGENT.md", b"# our own notes\n")
        table = {".lore/LORE-AGENT.md": ["sha256:whatever-lore-shipped"]}

        records = self._records(tmp_path, monkeypatch, table)

        assert records.shipped_paths == frozenset()
        assert target.read_bytes() == b"# our own notes\n"

    def test_a_fixed_path_is_named_once_something_proves_lore_installed_here(
        self, tmp_path, monkeypatch
    ):
        plant(tmp_path, ".lore/LORE-AGENT.md", b"# edited since\n")
        table = self._installed_tree(tmp_path)
        table[".lore/LORE-AGENT.md"] = ["sha256:whatever-lore-shipped"]

        records = self._records(tmp_path, monkeypatch, table)

        assert ".lore/LORE-AGENT.md" in records.shipped_paths

    def test_a_fixed_path_at_shipped_bytes_is_recorded_as_installed(
        self, tmp_path, monkeypatch
    ):
        agent_doc = plant(tmp_path, ".lore/LORE-AGENT.md", b"as shipped\n")
        table = {".lore/LORE-AGENT.md": [manifest.file_digest(agent_doc)]}

        records = self._records(tmp_path, monkeypatch, table)

        assert ".lore/LORE-AGENT.md" in records.installed
        assert ".lore/LORE-AGENT.md" in records.shipped_paths

    def _guessing_records(self, tmp_path, monkeypatch, table):
        monkeypatch.setattr(
            reconcile, "_read_legacy_payload", lambda: {"files": table}
        )
        reconcile.load_legacy_hashes.cache_clear()
        try:
            return reconcile.legacy_records(tmp_path, retirement_reason=ledger)
        finally:
            reconcile.load_legacy_hashes.cache_clear()

    def test_a_retired_edit_is_named_when_the_tree_proves_the_root_is_lores(
        self, tmp_path, monkeypatch
    ):
        pristine = plant(tmp_path, ".lore/skills/kept/SKILL.md", b"as shipped")
        plant(tmp_path, ".lore/skills/old-skill/SKILL.md", b"mine now")
        table = {
            ".lore/skills/kept/SKILL.md": [manifest.file_digest(pristine)],
            ".lore/skills/old-skill/SKILL.md": ["sha256:whatever-lore-shipped"],
        }

        records = self._guessing_records(tmp_path, monkeypatch, table)

        assert ".lore/skills/old-skill/SKILL.md" in records.retired_edits

    def test_a_retired_edit_in_a_tree_lore_cannot_claim_is_not_named(
        self, tmp_path, monkeypatch
    ):
        """The guess now authorises an unlink, so it needs the same evidence.

        Under the ownership ruling a `retired_edits` record is what removes the
        file. "The historical table has a row at this name" was never evidence
        that Lore wrote to that name *here*, and a project that authored its own
        `old-skill/SKILL.md` in a directory holding nothing of Lore's would have
        had it deleted.
        """
        target = plant(tmp_path, ".lore/skills/old-skill/SKILL.md", b"my own skill")
        table = {".lore/skills/old-skill/SKILL.md": ["sha256:whatever-lore-shipped"]}

        records = self._guessing_records(tmp_path, monkeypatch, table)

        assert records.retired_edits == {}
        assert target.read_bytes() == b"my own skill"


class TestRecordedAndDesired:
    def test_absent_on_disk_is_a_reported_restore(self, tmp_path):
        desired = {"a/SKILL.md": desired_file("a/SKILL.md", b"new")}
        recorded = {"a/SKILL.md": recorded_entry("a/SKILL.md", manifest.bytes_digest(b"new"))}
        row = single_row(reconcile.reconcile(desired, recorded, tmp_path))

        assert row.action is FileAction.CREATE
        assert row.reported is True

    def test_unchanged_on_disk_and_unchanged_content_is_an_unreported_no_op(self, tmp_path):
        plant(tmp_path, "a/SKILL.md", b"same")
        digest = manifest.bytes_digest(b"same")
        desired = {"a/SKILL.md": desired_file("a/SKILL.md", b"same")}
        recorded = {"a/SKILL.md": recorded_entry("a/SKILL.md", digest)}
        row = single_row(reconcile.reconcile(desired, recorded, tmp_path))

        assert row.reported is False
        assert row.digest == digest

    def test_unchanged_on_disk_and_new_content_is_a_reported_overwrite(self, tmp_path):
        plant(tmp_path, "a/SKILL.md", b"old")
        desired = {"a/SKILL.md": desired_file("a/SKILL.md", b"new")}
        recorded = {"a/SKILL.md": recorded_entry("a/SKILL.md", manifest.bytes_digest(b"old"))}
        row = single_row(reconcile.reconcile(desired, recorded, tmp_path))

        assert row.action is FileAction.OVERWRITE
        assert row.reported is True
        assert row.digest == manifest.bytes_digest(b"new")

    def test_edited_into_exactly_the_shipped_bytes_is_an_unreported_no_op(self, tmp_path):
        """The write would be a no-op, so calling it a conflict is a false alarm.

        Someone who hand-applied the new shipped content — copied it in, or
        merged it — has a file whose bytes are precisely what Lore would write.
        Reporting it as edited-since-install would also drop it from the next
        manifest, and the run after that would call it "not installed by Lore".
        """
        plant(tmp_path, "a/SKILL.md", b"new")
        desired = {"a/SKILL.md": desired_file("a/SKILL.md", b"new")}
        recorded = {"a/SKILL.md": recorded_entry("a/SKILL.md", manifest.bytes_digest(b"old"))}
        row = single_row(reconcile.reconcile(desired, recorded, tmp_path))

        assert row.action is FileAction.CREATE
        assert row.reported is False
        assert row.detail is None
        assert row.digest == manifest.bytes_digest(b"new")

    def test_a_section_edited_into_the_shipped_block_is_an_unreported_no_op(self, tmp_path):
        block = "shipped\n"
        plant(tmp_path, "CLAUDE.md", f"mine\n{BEGIN}\n{block}{END}\n".encode())
        desired = {
            "CLAUDE.md": desired_file(
                "CLAUDE.md", block.encode(), kind="section", source="agent-instructions:claude"
            )
        }
        recorded = {
            "CLAUDE.md": recorded_entry(
                "CLAUDE.md",
                manifest.bytes_digest(b"older\n"),
                kind="section",
                source="agent-instructions:claude",
            )
        }
        row = single_row(
            reconcile.reconcile(desired, recorded, tmp_path, section_markers=markers)
        )

        assert row.action is FileAction.SECTION
        assert row.reported is False

    def test_edited_since_install_is_an_overwrite(self, tmp_path):
        """Lore installed it and still ships it, so the file is Lore's.

        The edit is discarded rather than asked about — the same answer
        `.lore/knights/default/**` and `.lore/doctrines/default/**` have always
        given, now given by the one tree that used to differ.
        """
        plant(tmp_path, "a/SKILL.md", b"edited")
        desired = {"a/SKILL.md": desired_file("a/SKILL.md", b"new")}
        recorded = {"a/SKILL.md": recorded_entry("a/SKILL.md", manifest.bytes_digest(b"installed"))}
        row = single_row(reconcile.reconcile(desired, recorded, tmp_path))

        assert row.action is FileAction.OVERWRITE
        assert row.reported is True
        assert row.digest == manifest.bytes_digest(b"new")

    def test_the_overwrite_says_the_edit_is_going(self, tmp_path):
        plant(tmp_path, "a/SKILL.md", b"edited")
        desired = {"a/SKILL.md": desired_file("a/SKILL.md", b"new")}
        recorded = {"a/SKILL.md": recorded_entry("a/SKILL.md", manifest.bytes_digest(b"installed"))}
        row = single_row(reconcile.reconcile(desired, recorded, tmp_path))

        assert row.detail is not None
        assert reconcile.EDIT_DISCARDED in row.detail

    def test_an_untouched_overwrite_still_carries_no_detail(self, tmp_path):
        """Only the row that destroys something explains itself."""
        plant(tmp_path, "a/SKILL.md", b"old")
        desired = {"a/SKILL.md": desired_file("a/SKILL.md", b"new")}
        recorded = {"a/SKILL.md": recorded_entry("a/SKILL.md", manifest.bytes_digest(b"old"))}
        row = single_row(reconcile.reconcile(desired, recorded, tmp_path))

        assert row.detail is None

    def test_an_edited_skill_is_told_where_its_own_copy_belongs(self, tmp_path):
        """Knights and doctrines have `default/` to say it; skills have nowhere.

        A user losing an edit is the ruling. A user losing an edit with no idea
        how to avoid the next one is not, so the row that takes the file back
        names the directory a skill of their own would survive in.
        """
        plant(tmp_path, ".claude/skills/inquest/SKILL.md", b"edited")
        desired = {
            ".claude/skills/inquest/SKILL.md": desired_file(
                ".claude/skills/inquest/SKILL.md", b"new", source="skill:inquest"
            )
        }
        row = single_row(
            reconcile.reconcile(
                desired,
                {},
                tmp_path,
                installed_before={".claude/skills/inquest/SKILL.md"},
            )
        )

        assert ".claude/skills/" in row.detail

    def test_a_file_that_is_not_a_skill_names_no_directory(self, tmp_path):
        """`.lore/LORE-AGENT.md` has no "put your own beside it" story to tell."""
        plant(tmp_path, ".lore/LORE-AGENT.md", b"edited")
        desired = {
            ".lore/LORE-AGENT.md": desired_file(
                ".lore/LORE-AGENT.md", b"new", source="lore-agent"
            )
        }
        recorded = {
            ".lore/LORE-AGENT.md": recorded_entry(
                ".lore/LORE-AGENT.md",
                manifest.bytes_digest(b"installed"),
                source="lore-agent",
            )
        }
        row = single_row(reconcile.reconcile(desired, recorded, tmp_path))

        assert row.detail == reconcile.LORE_OWNS_THIS_FILE


class TestRecordedButNoLongerDesired:
    def test_unchanged_on_disk_is_a_removal_carrying_the_ledger_reason(self, tmp_path):
        plant(tmp_path, "old-skill/SKILL.md", b"shipped")
        recorded = {
            "old-skill/SKILL.md": recorded_entry(
                "old-skill/SKILL.md", manifest.bytes_digest(b"shipped")
            )
        }
        row = single_row(reconcile.reconcile({}, recorded, tmp_path, retirement_reason=ledger))

        assert row.action is FileAction.REMOVE
        # The reason the ledger gives, and the skill it points at: six of the
        # thirteen reasons name no successor, and one of those six is not a
        # successor anybody could guess.
        assert row.detail == "renamed → new-skill"
        assert row.digest is None

    def test_a_reason_that_already_names_the_successor_does_not_repeat_it(
        self, tmp_path
    ):
        plant(tmp_path, "merged-skill/SKILL.md", b"shipped")
        recorded = {
            "merged-skill/SKILL.md": recorded_entry(
                "merged-skill/SKILL.md",
                manifest.bytes_digest(b"shipped"),
                source="skill:merged-skill",
            )
        }
        row = single_row(reconcile.reconcile({}, recorded, tmp_path, retirement_reason=ledger))

        assert row.detail == "merged into store-memory"

    def test_a_skill_that_only_moved_says_where_it_went(self, tmp_path):
        plant(tmp_path, ".lore/skills/kept-skill/SKILL.md", b"shipped")
        desired = {
            ".claude/skills/kept-skill/SKILL.md": desired_file(
                ".claude/skills/kept-skill/SKILL.md",
                b"shipped",
                source="skill:kept-skill",
            )
        }
        recorded = {
            ".lore/skills/kept-skill/SKILL.md": recorded_entry(
                ".lore/skills/kept-skill/SKILL.md",
                manifest.bytes_digest(b"shipped"),
                source="skill:kept-skill",
            )
        }
        rows = reconcile.reconcile(desired, recorded, tmp_path, retirement_reason=ledger)
        removal = next(row for row in rows if row.action is FileAction.REMOVE)

        assert removal.detail == "moved to .claude/skills/"

    def test_a_skill_this_run_installs_nowhere_says_so(self, tmp_path):
        plant(tmp_path, ".lore/skills/kept-skill/SKILL.md", b"shipped")
        recorded = {
            ".lore/skills/kept-skill/SKILL.md": recorded_entry(
                ".lore/skills/kept-skill/SKILL.md",
                manifest.bytes_digest(b"shipped"),
                source="skill:kept-skill",
            )
        }
        row = single_row(reconcile.reconcile({}, recorded, tmp_path, retirement_reason=ledger))

        assert row.detail == reconcile.NO_LONGER_INSTALLED

    def test_edited_on_disk_is_a_removal_naming_the_successor(self, tmp_path):
        """A file Lore installed and has since retired is still Lore's.

        Keeping it left a project holding a directory no release ships, with a
        successor nobody named. It goes, and the row says both why it went and
        where the thinking in it now belongs.
        """
        plant(tmp_path, "old-skill/SKILL.md", b"edited")
        recorded = {
            "old-skill/SKILL.md": recorded_entry(
                "old-skill/SKILL.md", manifest.bytes_digest(b"shipped")
            )
        }
        row = single_row(reconcile.reconcile({}, recorded, tmp_path, retirement_reason=ledger))

        assert row.action is FileAction.REMOVE
        assert "new-skill" in row.detail
        assert reconcile.EDIT_DISCARDED in row.detail
        assert row.digest is None

    def test_an_unedited_removal_says_nothing_about_an_edit(self, tmp_path):
        plant(tmp_path, "old-skill/SKILL.md", b"shipped")
        recorded = {
            "old-skill/SKILL.md": recorded_entry(
                "old-skill/SKILL.md", manifest.bytes_digest(b"shipped")
            )
        }
        row = single_row(reconcile.reconcile({}, recorded, tmp_path, retirement_reason=ledger))

        assert reconcile.EDIT_DISCARDED not in row.detail

    def test_an_edited_removal_with_no_ledger_entry_still_says_so(self, tmp_path):
        plant(tmp_path, "CLAUDE.md", b"edited")
        recorded = {
            "CLAUDE.md": recorded_entry(
                "CLAUDE.md",
                manifest.bytes_digest(b"shipped"),
                source="agent-instructions:claude",
            )
        }
        row = single_row(reconcile.reconcile({}, recorded, tmp_path))

        assert row.action is FileAction.REMOVE
        assert row.detail == reconcile.EDIT_DISCARDED

    def test_absent_on_disk_is_forgotten_entirely(self, tmp_path):
        recorded = {
            "old-skill/SKILL.md": recorded_entry(
                "old-skill/SKILL.md", manifest.bytes_digest(b"shipped")
            )
        }
        assert reconcile.reconcile({}, recorded, tmp_path, retirement_reason=ledger) == ()

    def test_a_source_with_no_ledger_entry_removes_without_a_reason(self, tmp_path):
        plant(tmp_path, "CLAUDE.md", b"shipped")
        recorded = {
            "CLAUDE.md": recorded_entry(
                "CLAUDE.md", manifest.bytes_digest(b"shipped"), source="agent-instructions:claude"
            )
        }
        row = single_row(reconcile.reconcile({}, recorded, tmp_path, retirement_reason=ledger))

        assert row.action is FileAction.REMOVE
        assert row.detail is None


class TestPathsInNeitherSet:
    def test_a_path_in_neither_set_is_absent_from_the_result(self, tmp_path):
        plant(tmp_path, "mine/SKILL.md", b"mine")
        assert reconcile.reconcile({}, {}, tmp_path) == ()

    def test_a_path_in_neither_set_is_never_read(self, tmp_path, monkeypatch):
        plant(tmp_path, "mine/SKILL.md", b"mine")
        plant(tmp_path, "theirs/SKILL.md", b"theirs")
        read: list[Path] = []
        original = manifest.file_digest
        monkeypatch.setattr(
            manifest, "file_digest", lambda path: (read.append(Path(path)), original(path))[1]
        )

        desired = {"theirs/SKILL.md": desired_file("theirs/SKILL.md", b"theirs")}
        reconcile.reconcile(desired, {}, tmp_path)

        assert tmp_path / "mine" / "SKILL.md" not in read

    def test_a_path_in_neither_set_keeps_its_bytes(self, tmp_path):
        target = plant(tmp_path, "mine/SKILL.md", b"mine")
        reconcile.reconcile({}, {}, tmp_path)
        assert target.read_bytes() == b"mine"


# ---------------------------------------------------------------------------
# Section entries
# ---------------------------------------------------------------------------


class TestSectionEntries:
    def test_only_the_marked_block_is_compared(self, tmp_path):
        plant(tmp_path, "CLAUDE.md", f"MY PROSE\n{BEGIN}\nblock\n{END}\ntail\n".encode())
        digest = manifest.bytes_digest(b"block\n")
        desired = {
            "CLAUDE.md": desired_file(
                "CLAUDE.md", b"block\n", kind="section", source="agent-instructions:claude"
            )
        }
        recorded = {"CLAUDE.md": recorded_entry("CLAUDE.md", digest, kind="section")}
        row = single_row(
            reconcile.reconcile(desired, recorded, tmp_path, section_markers=markers)
        )

        assert row.reported is False

    def test_editing_prose_outside_the_markers_is_not_a_conflict(self, tmp_path):
        plant(tmp_path, "CLAUDE.md", f"REWRITTEN\n{BEGIN}\nblock\n{END}\nNEW TAIL\n".encode())
        digest = manifest.bytes_digest(b"block\n")
        desired = {
            "CLAUDE.md": desired_file(
                "CLAUDE.md", b"newblock\n", kind="section", source="agent-instructions:claude"
            )
        }
        recorded = {"CLAUDE.md": recorded_entry("CLAUDE.md", digest, kind="section")}
        row = single_row(
            reconcile.reconcile(desired, recorded, tmp_path, section_markers=markers)
        )

        assert row.action is FileAction.SECTION
        assert row.reported is True

    def test_editing_inside_the_markers_is_rewritten(self, tmp_path):
        """What the markers enclose is Lore's, which is what the markers mean."""
        plant(tmp_path, "CLAUDE.md", f"prose\n{BEGIN}\nEDITED\n{END}\n".encode())
        digest = manifest.bytes_digest(b"block\n")
        desired = {
            "CLAUDE.md": desired_file(
                "CLAUDE.md", b"block\n", kind="section", source="agent-instructions:claude"
            )
        }
        recorded = {"CLAUDE.md": recorded_entry("CLAUDE.md", digest, kind="section")}
        row = single_row(
            reconcile.reconcile(desired, recorded, tmp_path, section_markers=markers)
        )

        assert row.action is FileAction.SECTION
        assert row.detail == reconcile.LORE_OWNS_THIS_FILE

    def test_a_write_into_a_user_owned_file_is_a_section_action(self, tmp_path):
        plant(tmp_path, "CLAUDE.md", b"only my prose\n")
        desired = {
            "CLAUDE.md": desired_file(
                "CLAUDE.md", b"block\n", kind="section", source="agent-instructions:claude"
            )
        }
        row = single_row(reconcile.reconcile(desired, {}, tmp_path, section_markers=markers))

        assert row.action is FileAction.SECTION
        assert row.kind == "section"

    def test_a_missing_block_in_an_existing_file_is_a_restore(self, tmp_path):
        plant(tmp_path, "CLAUDE.md", b"prose with no markers\n")
        digest = manifest.bytes_digest(b"block\n")
        desired = {
            "CLAUDE.md": desired_file(
                "CLAUDE.md", b"block\n", kind="section", source="agent-instructions:claude"
            )
        }
        recorded = {"CLAUDE.md": recorded_entry("CLAUDE.md", digest, kind="section")}
        row = single_row(
            reconcile.reconcile(desired, recorded, tmp_path, section_markers=markers)
        )

        assert row.action is FileAction.SECTION
        assert row.reported is True

    def test_a_retired_section_whose_block_is_intact_is_removed(self, tmp_path):
        plant(tmp_path, "CLAUDE.md", f"prose\n{BEGIN}\nblock\n{END}\n".encode())
        digest = manifest.bytes_digest(b"block\n")
        recorded = {
            "CLAUDE.md": recorded_entry(
                "CLAUDE.md", digest, kind="section", source="agent-instructions:claude"
            )
        }
        row = single_row(reconcile.reconcile({}, recorded, tmp_path, section_markers=markers))

        assert row.action is FileAction.REMOVE
        assert row.kind == "section"

    def test_a_retired_section_whose_block_was_edited_is_removed(self, tmp_path):
        """The block goes; the prose around it is the user's and never moves."""
        plant(tmp_path, "CLAUDE.md", f"prose\n{BEGIN}\nEDITED\n{END}\n".encode())
        digest = manifest.bytes_digest(b"block\n")
        recorded = {
            "CLAUDE.md": recorded_entry(
                "CLAUDE.md", digest, kind="section", source="agent-instructions:claude"
            )
        }
        row = single_row(reconcile.reconcile({}, recorded, tmp_path, section_markers=markers))

        assert row.action is FileAction.REMOVE
        assert row.kind == "section"

    def test_a_section_entry_without_markers_supplied_raises(self, tmp_path):
        plant(tmp_path, "CLAUDE.md", b"prose\n")
        desired = {
            "CLAUDE.md": desired_file(
                "CLAUDE.md", b"block\n", kind="section", source="agent-instructions:claude"
            )
        }
        with pytest.raises(ValueError):
            reconcile.reconcile(desired, {}, tmp_path)


# ---------------------------------------------------------------------------
# The conflict policy
# ---------------------------------------------------------------------------


class TestOnConflict:
    """One conflict class is left, and the answer governs that one alone.

    Lore's own files are settled by the ownership ruling rather than by an
    answer, so the policy no longer has any say over them. What it still
    decides is the file *the project* put where Lore wants to write.
    """

    def test_skip_is_the_default_for_a_file_lore_never_installed(self, tmp_path):
        plant(tmp_path, "a/SKILL.md", b"mine")
        desired = {"a/SKILL.md": desired_file("a/SKILL.md", b"theirs")}

        row = single_row(reconcile.reconcile(desired, {}, tmp_path))

        assert row.action is FileAction.CONFLICT

    def test_overwrite_turns_a_never_installed_file_into_an_overwrite(self, tmp_path):
        plant(tmp_path, "a/SKILL.md", b"mine")
        desired = {"a/SKILL.md": desired_file("a/SKILL.md", b"theirs")}
        row = single_row(reconcile.reconcile(desired, {}, tmp_path, on_conflict="overwrite"))

        assert row.action is FileAction.OVERWRITE

    def test_skip_does_not_spare_a_file_lore_installed(self, tmp_path):
        """The policy is not a way back to the behaviour the ruling replaced."""
        plant(tmp_path, "a/SKILL.md", b"edited")
        desired = {"a/SKILL.md": desired_file("a/SKILL.md", b"new")}
        recorded = {"a/SKILL.md": recorded_entry("a/SKILL.md", manifest.bytes_digest(b"old"))}

        row = single_row(
            reconcile.reconcile(desired, recorded, tmp_path, on_conflict="skip")
        )

        assert row.action is FileAction.OVERWRITE

    def test_skip_does_not_spare_a_retired_file_lore_installed(self, tmp_path):
        plant(tmp_path, "old-skill/SKILL.md", b"edited")
        recorded = {
            "old-skill/SKILL.md": recorded_entry(
                "old-skill/SKILL.md", manifest.bytes_digest(b"shipped")
            )
        }
        row = single_row(
            reconcile.reconcile(
                {}, recorded, tmp_path, on_conflict="skip", retirement_reason=ledger
            )
        )

        assert row.action is FileAction.REMOVE

    def test_a_never_installed_section_target_is_written_either_way(self, tmp_path):
        """A file with no marked block is not a conflict: the block is added."""
        plant(tmp_path, "CLAUDE.md", b"only my prose\n")
        desired = {
            "CLAUDE.md": desired_file(
                "CLAUDE.md", b"block\n", kind="section", source="agent-instructions:claude"
            )
        }
        row = single_row(
            reconcile.reconcile(desired, {}, tmp_path, section_markers=markers)
        )

        assert row.action is FileAction.SECTION

    def test_an_unknown_conflict_policy_raises(self, tmp_path):
        with pytest.raises(ValueError):
            reconcile.reconcile({}, {}, tmp_path, on_conflict="merge")


class TestUnsettledConflicts:
    """Which rows the `on_conflict` answer can still do anything about.

    The gate that opens the prompt reads this. A conflict the answer cannot
    settle — a symlink, a path resolving out of the project — must not open a
    question whose every answer leaves the row exactly as it is.
    """

    def test_a_file_lore_never_installed_is_settleable(self, tmp_path):
        plant(tmp_path, "a/SKILL.md", b"mine")
        desired = {"a/SKILL.md": desired_file("a/SKILL.md", b"theirs")}
        rows = reconcile.reconcile(desired, {}, tmp_path)

        assert reconcile.unsettled(rows) == rows

    def test_a_refusal_is_not_settleable(self, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.md").write_bytes(b"USER SECRET NOTES\n")
        root = tmp_path / "project"
        root.mkdir()
        (root / "SKILL.md").symlink_to(outside / "secret.md")
        desired = {"SKILL.md": desired_file("SKILL.md", b"shipped")}

        rows = reconcile.reconcile(desired, {}, root)

        assert single_row(rows).action is FileAction.CONFLICT
        assert reconcile.unsettled(rows) == ()

    def test_a_write_is_not_settleable(self, tmp_path):
        desired = {"a/SKILL.md": desired_file("a/SKILL.md", b"new")}
        rows = reconcile.reconcile(desired, {}, tmp_path)

        assert reconcile.unsettled(rows) == ()


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------


class TestOrdering:
    def test_rows_are_sorted_by_path(self, tmp_path):
        desired = {
            "z/SKILL.md": desired_file("z/SKILL.md", b"z"),
            "a/SKILL.md": desired_file("a/SKILL.md", b"a"),
            "m/SKILL.md": desired_file("m/SKILL.md", b"m"),
        }
        rows = reconcile.reconcile(desired, {}, tmp_path)

        assert [row.path for row in rows] == ["a/SKILL.md", "m/SKILL.md", "z/SKILL.md"]

    def test_the_same_inputs_in_any_order_produce_the_same_result(self, tmp_path):
        plant(tmp_path, "b/SKILL.md", b"shipped")
        forward = {
            "a/SKILL.md": desired_file("a/SKILL.md", b"a"),
            "c/SKILL.md": desired_file("c/SKILL.md", b"c"),
        }
        backward = dict(reversed(list(forward.items())))
        recorded = {"b/SKILL.md": recorded_entry("b/SKILL.md", manifest.bytes_digest(b"shipped"))}

        assert reconcile.reconcile(forward, recorded, tmp_path, retirement_reason=ledger) == (
            reconcile.reconcile(backward, recorded, tmp_path, retirement_reason=ledger)
        )


# ---------------------------------------------------------------------------
# A path that is a link rather than a file
# ---------------------------------------------------------------------------


@pytest.fixture()
def sandbox(tmp_path) -> tuple[Path, Path]:
    """A project root with somewhere outside it for a link to point at."""
    root = tmp_path / "proj"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    return root, outside


class TestAPathThatIsALink:
    """`_disk_digest` tested ``is_file()``, which follows a link: a dangling one
    read as absent and became a CREATE that wrote outside the project, and a
    live one hashed the *target's* bytes, so `overwrite` truncated a file the
    user keeps somewhere else entirely."""

    def test_a_dangling_link_is_a_conflict_rather_than_a_create(self, sandbox):
        root, outside = sandbox
        (root / "SKILL.md").symlink_to(outside / "PWNED.md")
        desired = {"SKILL.md": desired_file("SKILL.md", b"shipped")}

        row = single_row(reconcile.reconcile(desired, {}, root))

        assert row.action is FileAction.CONFLICT
        assert "link" in row.detail

    def test_a_live_link_is_a_conflict_rather_than_a_write(self, sandbox):
        root, outside = sandbox
        (outside / "secret.md").write_bytes(b"USER SECRET NOTES\n")
        (root / "SKILL.md").symlink_to(outside / "secret.md")
        desired = {"SKILL.md": desired_file("SKILL.md", b"shipped")}

        row = single_row(reconcile.reconcile(desired, {}, root))

        assert row.action is FileAction.CONFLICT

    def test_overwrite_does_not_turn_a_link_into_a_write(self, sandbox):
        root, outside = sandbox
        (outside / "secret.md").write_bytes(b"USER SECRET NOTES\n")
        (root / "SKILL.md").symlink_to(outside / "secret.md")
        desired = {"SKILL.md": desired_file("SKILL.md", b"shipped")}

        row = single_row(reconcile.reconcile(desired, {}, root, on_conflict="overwrite"))

        assert row.action is FileAction.CONFLICT

    def test_a_link_whose_target_matches_is_still_a_conflict(self, sandbox):
        """Hashing the target is exactly the read that made a link look like an
        installed file."""
        root, outside = sandbox
        (outside / "shipped.md").write_bytes(b"shipped")
        (root / "SKILL.md").symlink_to(outside / "shipped.md")
        desired = {"SKILL.md": desired_file("SKILL.md", b"shipped")}

        row = single_row(reconcile.reconcile(desired, {}, root))

        assert row.action is FileAction.CONFLICT
        assert row.reported is True

    def test_a_link_at_a_recorded_path_is_a_conflict_rather_than_a_removal(
        self, sandbox
    ):
        """The one row a retired path can still take other than removal.

        Ownership settles what happens to Lore's *file*; a link is not that
        file, and the hash that would otherwise authorise the unlink was read
        through it.
        """
        root, outside = sandbox
        (outside / "secret.md").write_bytes(b"shipped")
        (root / "SKILL.md").symlink_to(outside / "secret.md")
        recorded = {
            "SKILL.md": recorded_entry("SKILL.md", manifest.bytes_digest(b"shipped"))
        }

        row = single_row(reconcile.reconcile({}, recorded, root))

        assert row.action is FileAction.CONFLICT
        assert (root / "SKILL.md").is_symlink()

    def test_overwrite_does_not_remove_through_a_link_either(self, sandbox):
        root, outside = sandbox
        (outside / "secret.md").write_bytes(b"shipped")
        (root / "SKILL.md").symlink_to(outside / "secret.md")
        recorded = {
            "SKILL.md": recorded_entry("SKILL.md", manifest.bytes_digest(b"shipped"))
        }

        row = single_row(reconcile.reconcile({}, recorded, root, on_conflict="overwrite"))

        assert row.action is FileAction.CONFLICT

    def test_a_path_reached_through_a_linked_directory_is_a_conflict(self, sandbox):
        root, outside = sandbox
        (root / "skills").symlink_to(outside)
        desired = {
            "skills/inquest/SKILL.md": desired_file("skills/inquest/SKILL.md", b"shipped")
        }

        row = single_row(reconcile.reconcile(desired, {}, root))

        assert row.action is FileAction.CONFLICT
        assert "outside the project root" in row.detail

    def test_a_section_target_that_is_a_link_is_a_conflict(self, sandbox):
        root, outside = sandbox
        (outside / "notes.md").write_text(f"prose\n{BEGIN}\nblock\n{END}\n")
        (root / "CLAUDE.md").symlink_to(outside / "notes.md")
        desired = {"CLAUDE.md": desired_file("CLAUDE.md", b"block\n", kind="section")}

        row = single_row(
            reconcile.reconcile(desired, {}, root, section_markers=markers)
        )

        assert row.action is FileAction.CONFLICT

    def test_an_ordinary_file_is_unaffected_by_the_guard(self, sandbox):
        root, _ = sandbox
        plant(root, "SKILL.md", b"shipped")
        desired = {"SKILL.md": desired_file("SKILL.md", b"shipped")}

        row = single_row(reconcile.reconcile(desired, {}, root))

        assert row.action is FileAction.CREATE
        assert row.reported is False


# ---------------------------------------------------------------------------
# prune_empty_dirs
# ---------------------------------------------------------------------------


class TestPruneEmptyDirs:
    def test_an_empty_chain_is_removed_up_to_the_target_root(self, tmp_path):
        root = tmp_path / ".claude" / "skills"
        removed = root / "gone" / "references" / "rite.md"
        removed.parent.mkdir(parents=True)

        pruned = reconcile.prune_empty_dirs([removed], root)

        assert not (root / "gone").exists()
        assert set(pruned) == {root / "gone", root / "gone" / "references"}

    def test_the_target_root_itself_is_never_removed(self, tmp_path):
        root = tmp_path / ".claude" / "skills"
        removed = root / "gone" / "SKILL.md"
        removed.parent.mkdir(parents=True)

        reconcile.prune_empty_dirs([removed], root)

        assert root.is_dir()

    def test_the_walk_stops_at_the_first_non_empty_ancestor(self, tmp_path):
        root = tmp_path / ".claude" / "skills"
        removed = root / "keep" / "nested" / "SKILL.md"
        removed.parent.mkdir(parents=True)
        (root / "keep" / "mine.md").write_text("mine")

        reconcile.prune_empty_dirs([removed], root)

        assert not (root / "keep" / "nested").exists()
        assert (root / "keep" / "mine.md").read_text() == "mine"

    def test_a_directory_holding_a_user_file_survives(self, tmp_path):
        root = tmp_path / ".claude" / "skills"
        removed = root / "gone" / "SKILL.md"
        removed.parent.mkdir(parents=True)
        (root / "gone" / "notes.md").write_text("mine")

        assert reconcile.prune_empty_dirs([removed], root) == ()
        assert (root / "gone").is_dir()

    def test_a_path_outside_the_target_root_is_never_removed(self, tmp_path):
        root = tmp_path / ".claude" / "skills"
        root.mkdir(parents=True)
        outside = tmp_path / "elsewhere" / "SKILL.md"
        outside.parent.mkdir(parents=True)

        assert reconcile.prune_empty_dirs([outside], root) == ()
        assert (tmp_path / "elsewhere").is_dir()

    def test_a_sibling_directory_is_untouched(self, tmp_path):
        root = tmp_path / ".claude" / "skills"
        removed = root / "gone" / "SKILL.md"
        removed.parent.mkdir(parents=True)
        (root / "sibling").mkdir()
        (root / "sibling" / "SKILL.md").write_text("still here")

        reconcile.prune_empty_dirs([removed], root)

        assert (root / "sibling" / "SKILL.md").exists()

    def test_the_result_is_deterministic(self, tmp_path):
        root = tmp_path / ".claude" / "skills"
        for name in ("b", "a"):
            (root / name).mkdir(parents=True)

        pruned = reconcile.prune_empty_dirs([root / "b" / "x.md", root / "a" / "x.md"], root)

        assert list(pruned) == sorted(pruned)


class TestPruneSurvivesADirectoryItCannotRemove:
    """`is_dir()` follows a link and `rmdir()` does not, so a symlinked skill
    directory reached `rmdir` on a link and raised `NotADirectoryError` — and
    the pass was unguarded, so that one failure abandoned every later prune."""

    def test_a_symlinked_directory_is_skipped_rather_than_raising(self, tmp_path):
        root = tmp_path / ".claude" / "skills"
        root.mkdir(parents=True)
        elsewhere = tmp_path / "outdir"
        elsewhere.mkdir()
        (root / "linked").symlink_to(elsewhere)

        assert reconcile.prune_empty_dirs([root / "linked" / "SKILL.md"], root) == ()
        assert (root / "linked").is_symlink()
        assert elsewhere.is_dir()

    def test_one_unprunable_directory_does_not_orphan_the_rest(self, tmp_path):
        root = tmp_path / ".claude" / "skills"
        root.mkdir(parents=True)
        (root / "aaa-linked").symlink_to(tmp_path / "outdir")
        (tmp_path / "outdir").mkdir()
        for name in ("bbb", "ccc", "ddd"):
            (root / name).mkdir()
        removed = [root / name / "SKILL.md" for name in ("aaa-linked", "bbb", "ccc", "ddd")]

        pruned = reconcile.prune_empty_dirs(removed, root)

        assert set(pruned) == {root / "bbb", root / "ccc", root / "ddd"}

    def test_a_directory_the_filesystem_refuses_is_skipped(self, tmp_path):
        root = tmp_path / ".claude" / "skills"
        (root / "locked").mkdir(parents=True)
        (root / "later").mkdir()
        root.chmod(0o555)
        try:
            pruned = reconcile.prune_empty_dirs(
                [root / "locked" / "SKILL.md", root / "later" / "SKILL.md"], root
            )
        finally:
            root.chmod(0o755)

        assert pruned == ()
        assert (root / "locked").is_dir()

    def test_a_directory_reached_through_a_link_is_never_climbed_past(self, tmp_path):
        """A prune must not walk out of the tree it was given, however the
        path got there."""
        root = tmp_path / ".claude" / "skills"
        root.mkdir(parents=True)
        outside = tmp_path / "outdir" / "nested"
        outside.mkdir(parents=True)
        (root / "linked").symlink_to(tmp_path / "outdir")

        reconcile.prune_empty_dirs([root / "linked" / "nested" / "SKILL.md"], root)

        assert outside.is_dir()


# ---------------------------------------------------------------------------
# legacy_recorded
# ---------------------------------------------------------------------------


TABLE = {
    ".lore/skills/old-skill/SKILL.md": ("sha256:one", "sha256:two"),
    ".lore/skills/other-skill/SKILL.md": ("sha256:three",),
}


@pytest.fixture()
def fake_table(monkeypatch):
    """Replace the packaged historical-hash table with a synthetic one."""
    monkeypatch.setattr(reconcile, "load_legacy_hashes", lambda: TABLE)
    return TABLE


class TestLegacyRecorded:
    def test_a_hash_hit_becomes_an_owned_recorded_entry(self, tmp_path, monkeypatch, fake_table):
        target = plant(tmp_path, ".lore/skills/old-skill/SKILL.md", b"shipped")
        monkeypatch.setattr(
            manifest, "file_digest", lambda path: "sha256:two" if Path(path) == target else "sha256:x"
        )

        found = reconcile.legacy_recorded(tmp_path)

        assert set(found) == {".lore/skills/old-skill/SKILL.md"}
        entry = found[".lore/skills/old-skill/SKILL.md"]
        assert entry.kind == "owned"
        assert entry.hash == "sha256:two"

    def test_the_entry_carries_the_skill_source_token(self, tmp_path, monkeypatch, fake_table):
        plant(tmp_path, ".lore/skills/old-skill/SKILL.md", b"shipped")
        monkeypatch.setattr(manifest, "file_digest", lambda path: "sha256:one")

        entry = reconcile.legacy_recorded(tmp_path)[".lore/skills/old-skill/SKILL.md"]
        assert entry.source == "skill:old-skill"

    def test_a_known_path_with_an_unmatched_hash_is_absent(self, tmp_path, monkeypatch, fake_table):
        plant(tmp_path, ".lore/skills/old-skill/SKILL.md", b"edited")
        monkeypatch.setattr(manifest, "file_digest", lambda path: "sha256:edited")

        assert reconcile.legacy_recorded(tmp_path) == {}

    def test_an_unknown_path_is_absent(self, tmp_path, monkeypatch, fake_table):
        plant(tmp_path, ".lore/skills/my-own/SKILL.md", b"mine")
        monkeypatch.setattr(manifest, "file_digest", lambda path: "sha256:one")

        assert reconcile.legacy_recorded(tmp_path) == {}

    def test_a_project_with_no_skills_tree_returns_an_empty_mapping(self, tmp_path):
        assert reconcile.legacy_recorded(tmp_path) == {}

    def test_an_agent_skills_directory_is_walked_too(self, tmp_path, monkeypatch, fake_table):
        # The pre-feature GETTING-STARTED told people to copy `.lore/skills/`
        # into their agent's directory, so that is where the orphans really are.
        plant(tmp_path, ".claude/skills/old-skill/SKILL.md", b"shipped")
        monkeypatch.setattr(manifest, "file_digest", lambda path: "sha256:one")

        found = reconcile.legacy_recorded(tmp_path)

        assert set(found) == {".claude/skills/old-skill/SKILL.md"}

    def test_an_agent_copy_is_recorded_at_its_own_path(self, tmp_path, monkeypatch, fake_table):
        plant(tmp_path, ".claude/skills/old-skill/SKILL.md", b"shipped")
        monkeypatch.setattr(manifest, "file_digest", lambda path: "sha256:one")

        entry = reconcile.legacy_recorded(tmp_path)[".claude/skills/old-skill/SKILL.md"]

        assert entry.path == ".claude/skills/old-skill/SKILL.md"
        assert entry.source == "skill:old-skill"

    def test_both_trees_are_recorded_in_one_walk(self, tmp_path, monkeypatch, fake_table):
        plant(tmp_path, ".lore/skills/old-skill/SKILL.md", b"shipped")
        plant(tmp_path, ".claude/skills/old-skill/SKILL.md", b"shipped")
        monkeypatch.setattr(manifest, "file_digest", lambda path: "sha256:one")

        found = reconcile.legacy_recorded(tmp_path)

        assert set(found) == {
            ".lore/skills/old-skill/SKILL.md",
            ".claude/skills/old-skill/SKILL.md",
        }

    def test_a_path_lore_never_shipped_is_never_read(self, tmp_path, monkeypatch, fake_table):
        mine = plant(tmp_path, ".claude/skills/my-own/SKILL.md", b"mine")
        read: list[Path] = []
        monkeypatch.setattr(
            manifest, "file_digest", lambda path: (read.append(Path(path)), "sha256:one")[1]
        )

        found = reconcile.legacy_recorded(tmp_path)

        assert found == {}
        assert mine not in read

    def test_an_agent_copy_with_an_unmatched_hash_is_absent(
        self, tmp_path, monkeypatch, fake_table
    ):
        plant(tmp_path, ".claude/skills/old-skill/SKILL.md", b"edited")
        monkeypatch.setattr(manifest, "file_digest", lambda path: "sha256:edited")

        assert reconcile.legacy_recorded(tmp_path) == {}

    def test_only_registry_skills_directories_are_walked(
        self, tmp_path, monkeypatch, fake_table
    ):
        stray = plant(tmp_path, "vendor/skills/old-skill/SKILL.md", b"shipped")
        read: list[Path] = []
        monkeypatch.setattr(
            manifest, "file_digest", lambda path: (read.append(Path(path)), "sha256:one")[1]
        )

        assert reconcile.legacy_recorded(tmp_path) == {}
        assert stray not in read


class TestLegacySkillsRoots:
    def test_the_lore_skills_tree_is_always_a_root(self):
        assert ".lore/skills" in reconcile.legacy_skills_roots()

    def test_every_registry_skills_dir_is_a_root(self):
        from lore.agents import load_registry

        declared = {row.skills_dir for row in load_registry() if row.skills_dir}
        assert declared <= set(reconcile.legacy_skills_roots())

    def test_the_roots_are_deduplicated_and_sorted(self):
        roots = reconcile.legacy_skills_roots()
        assert list(roots) == sorted(set(roots))

    def test_nested_reference_files_are_matched_by_their_full_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            reconcile,
            "load_legacy_hashes",
            lambda: {".lore/skills/old-skill/references/rite.md": ("sha256:ref",)},
        )
        plant(tmp_path, ".lore/skills/old-skill/references/rite.md", b"shipped")
        monkeypatch.setattr(manifest, "file_digest", lambda path: "sha256:ref")

        found = reconcile.legacy_recorded(tmp_path)
        assert set(found) == {".lore/skills/old-skill/references/rite.md"}
        assert found[".lore/skills/old-skill/references/rite.md"].source == "skill:old-skill"


class TestLoadLegacyHashes:
    def test_the_shipped_table_maps_paths_to_hash_tuples(self):
        reconcile.load_legacy_hashes.cache_clear()
        table = reconcile.load_legacy_hashes()

        assert isinstance(table, dict)
        assert all(isinstance(hashes, tuple) for hashes in table.values())

    def test_a_missing_packaged_file_raises_runtimeerror_naming_it(self, monkeypatch):
        reconcile.load_legacy_hashes.cache_clear()

        def boom():
            raise FileNotFoundError("legacy-hashes.json")

        monkeypatch.setattr(reconcile, "_read_legacy_payload", boom)
        with pytest.raises(RuntimeError) as excinfo:
            reconcile.load_legacy_hashes()

        assert reconcile.PACKAGED_LEGACY_HASHES in str(excinfo.value)
        reconcile.load_legacy_hashes.cache_clear()

    def test_an_unparseable_packaged_file_raises_runtimeerror_naming_it(self, monkeypatch):
        reconcile.load_legacy_hashes.cache_clear()

        def boom():
            raise json.JSONDecodeError("bad", "{", 0)

        monkeypatch.setattr(reconcile, "_read_legacy_payload", boom)
        with pytest.raises(RuntimeError) as excinfo:
            reconcile.load_legacy_hashes()

        assert reconcile.PACKAGED_LEGACY_HASHES in str(excinfo.value)
        reconcile.load_legacy_hashes.cache_clear()

    def test_a_payload_that_is_not_a_mapping_raises_runtimeerror(self, monkeypatch):
        reconcile.load_legacy_hashes.cache_clear()
        monkeypatch.setattr(reconcile, "_read_legacy_payload", lambda: [1, 2, 3])

        with pytest.raises(RuntimeError):
            reconcile.load_legacy_hashes()

        reconcile.load_legacy_hashes.cache_clear()


# ---------------------------------------------------------------------------
# A file on disk that will not decode as text
# ---------------------------------------------------------------------------
#
# A `section` entry is compared against the marked block inside a file the
# project owns, which means reading that file as text. Nothing guarantees it is
# text: the recorded path may name a binary file the project put there, or one
# a previous run recorded before it was replaced. The decoder's own message
# says only a byte offset, which names no file and tells nobody what to do.


NOT_TEXT = b"\x1f\x8b\x08\x82\x00\xff\xfe binary payload"


class TestASectionTargetThatIsNotText:
    def test_a_desired_section_names_the_file_it_could_not_read(self, tmp_path):
        plant(tmp_path, "blob.bin", NOT_TEXT)
        desired = {
            "blob.bin": desired_file(
                "blob.bin", b"block\n", kind="section", source="agent-instructions:claude"
            )
        }
        with pytest.raises(ValueError) as excinfo:
            reconcile.reconcile(desired, {}, tmp_path, section_markers=markers)
        assert "blob.bin" in str(excinfo.value)

    def test_a_retired_section_names_the_file_it_could_not_read(self, tmp_path):
        plant(tmp_path, "blob.bin", NOT_TEXT)
        recorded = {
            "blob.bin": recorded_entry(
                "blob.bin", "sha256:0", kind="section", source="agent-instructions:claude"
            )
        }
        with pytest.raises(ValueError) as excinfo:
            reconcile.reconcile({}, recorded, tmp_path, section_markers=markers)
        assert "blob.bin" in str(excinfo.value)

    def test_the_message_carries_no_bare_codec_jargon(self, tmp_path):
        plant(tmp_path, "blob.bin", NOT_TEXT)
        recorded = {"blob.bin": recorded_entry("blob.bin", "sha256:0", kind="section")}
        with pytest.raises(ValueError) as excinfo:
            reconcile.reconcile({}, recorded, tmp_path, section_markers=markers)
        message = str(excinfo.value)
        assert "codec" not in message
        assert "re-run" in message

    def test_an_owned_entry_is_hashed_as_bytes_and_never_decoded(self, tmp_path):
        target = plant(tmp_path, "blob.bin", NOT_TEXT)
        recorded = {"blob.bin": recorded_entry("blob.bin", manifest.file_digest(target))}
        row = single_row(reconcile.reconcile({}, recorded, tmp_path))
        assert row.action is FileAction.REMOVE
