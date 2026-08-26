"""E2E tests for the `lore init` upgrade path — reconciliation against real files.

Spec: conceptual-workflows-init-reconcile
(lore codex show conceptual-workflows-init-reconcile)

`tests/unit/test_reconcile.py` covers the table on synthetic inputs. This file
covers the journey: a real project on disk, initialised by one release and
re-initialised by another, driven through the shipped CLI. Nothing here mocks a
reconcile internal — every assertion reads what `lore init` reported or what it
left in the working tree.

Two inputs are constructed rather than installed, because no previously
released wheel is available to a test run:

* **The pre-consolidation project.** Built by installing this release and then
  *ageing* it: each skill directory is renamed to the retired id the catalogue
  says became it, and the manifest rows are repointed at the new paths. The
  bytes never change, so the recorded hash still matches the disk — which is
  exactly the state the previous release left behind.
* **The historical-hash table**, for a project with no manifest. Substituted at
  ``reconcile._read_legacy_payload``, the seam that module documents for this.
  The table is shipped data, not logic: the walk, the hash test, the removals
  and the pruning downstream of it are all the real thing. The half of that
  scenario that needs no substitution — a file the table cannot match is kept —
  runs against the table Lore actually ships.

Per decisions-006-no-seed-content-tests nothing here pins the wording of a file
under `src/lore/defaults/`. Retirement reasons and successors are read from the
catalogue at run time and asserted to be *quoted*; their text is not the
subject. Skill ids come from the catalogue for the same reason.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from lore import manifest, reconcile, skills


# ---------------------------------------------------------------------------
# Catalogue lookups — structure, never wording
# ---------------------------------------------------------------------------


def retired_alias(skill_id: str) -> str:
    """A retired skill id the catalogue records as having become *skill_id*.

    Read from the ledger rather than hardcoded: the ledger is append-only, so
    the first alphabetical alias for a current skill is stable, and a test that
    derives it cannot pin a name the catalogue no longer uses.
    """
    ledger = skills.load_catalogue().get("retired", {})
    aliases = sorted(old for old, row in ledger.items() if row["into"] == skill_id)
    assert aliases, f"the catalogue records no retired skill that became {skill_id}"
    return aliases[0]


def ledger_reason(skill_id: str) -> str:
    """The reason the catalogue gives for retiring *skill_id*."""
    retirement = skills.retirement_for(skill_id)
    assert retirement is not None, f"{skill_id} is not in the retirement ledger"
    return retirement.reason


def ledger_successor(skill_id: str) -> str:
    """The skill the catalogue says replaced *skill_id*."""
    retirement = skills.retirement_for(skill_id)
    assert retirement is not None, f"{skill_id} is not in the retirement ledger"
    return retirement.into


def assert_names_the_retirement(detail: str | None, alias: str) -> None:
    """Assert *detail* quotes the ledger's reason and names the successor.

    Both, and neither's wording: six of the thirteen reasons named no successor
    at all, and `lore-update -> sync-codex-guide` was not one a reader could
    guess. What a removal line owes them is the reason it went and where its
    content is now.
    """
    assert detail is not None
    assert ledger_reason(alias) in detail, detail
    assert ledger_successor(alias) in detail, detail


CLAUDE_SKILLS = ".claude/skills"
LORE_SKILLS = ".lore/skills"


# ---------------------------------------------------------------------------
# Running the CLI
# ---------------------------------------------------------------------------


def init(runner: CliRunner, *args: str):
    """Run `lore init` with *args* and assert it succeeded."""
    from lore.cli import main

    result = runner.invoke(main, ["init", *args])
    assert result.exit_code == 0, result.output
    return result


def plan(runner: CliRunner, *args: str) -> str:
    """Return the summary `lore init --dry-run` prints, having written nothing."""
    return init(runner, "--dry-run", *args).output


# ---------------------------------------------------------------------------
# Reading what a run reported
# ---------------------------------------------------------------------------


ACTION_LABELS = ("Create", "Section", "Overwrite", "Remove", "Conflict")

COUNT_BUCKETS = ("create", "section", "overwrite", "remove", "conflict")


def plan_rows(output: str) -> dict[str, tuple[str, str | None]]:
    """The summary's listing, as ``path -> (action label, detail)``.

    Paths never contain spaces and details are prose, so splitting on
    whitespace reads both columns without depending on the padding widths.
    """
    rows: dict[str, tuple[str, str | None]] = {}
    for line in output.splitlines():
        if not line.startswith("  "):
            continue
        parts = line.split()
        if not parts or parts[0] not in ACTION_LABELS:
            continue
        rows[parts[1]] = (parts[0], " ".join(parts[2:]) or None)
    return rows


def plan_counts(output: str) -> dict[str, int]:
    """The summary's closing tally, as ``bucket -> count``."""
    lines = [line for line in output.splitlines() if line.strip().endswith("conflict")]
    assert lines, f"no counts line in:\n{output}"
    parts = lines[-1].replace("·", " ").split()
    tally = {name: int(count) for count, name in zip(parts[0::2], parts[1::2])}
    assert set(tally) == set(COUNT_BUCKETS), f"unexpected counts line: {lines[-1]}"
    return tally


def shown(path: str) -> str:
    """A repo-relative path as the applied-run messages name it.

    `lore init` reports a path inside `.lore/` relative to that directory, which
    is the convention its other status lines already follow.
    """
    return path[len(".lore/") :] if path.startswith(".lore/") else path


def removals(output: str) -> dict[str, str | None]:
    """Every ``Removed <path> — <reason>`` line, as ``path -> reason``."""
    reported: dict[str, str | None] = {}
    for line in output.splitlines():
        parts = line.split()
        if parts[:1] != ["Removed"]:
            continue
        reason = line.split("—", 1)[1].strip() if "—" in line else None
        reported[parts[1]] = reason
    return reported


def kept(output: str) -> dict[str, str | None]:
    """Every ``! Kept <path>`` report, as ``path -> the detail line under it``."""
    lines = output.splitlines()
    reported: dict[str, str | None] = {}
    for index, line in enumerate(lines):
        parts = line.split()
        if parts[:2] != ["!", "Kept"]:
            continue
        follower = lines[index + 1].strip() if index + 1 < len(lines) else ""
        detail = (
            follower if follower and not follower.startswith(("!", "Removed")) else None
        )
        reported[parts[2]] = detail
    return reported


def written(output: str) -> set[str]:
    """Every path a run reported creating or updating."""
    return {
        line.split()[1]
        for line in output.splitlines()
        if line.split()[:1] in (["Created"], ["Updated"])
    }


# ---------------------------------------------------------------------------
# The manifest
# ---------------------------------------------------------------------------


def manifest_path(project_dir: Path) -> Path:
    return project_dir / ".lore" / ".install-manifest.json"


def read_manifest(project_dir: Path) -> dict:
    return json.loads(manifest_path(project_dir).read_text(encoding="utf-8"))


def write_manifest(project_dir: Path, payload: dict) -> None:
    manifest_path(project_dir).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


def recorded_paths(project_dir: Path) -> set[str]:
    return {row["path"] for row in read_manifest(project_dir)["files"]}


# ---------------------------------------------------------------------------
# Working with the tree
# ---------------------------------------------------------------------------


def tree(project_dir: Path, root: str) -> dict[str, bytes]:
    """Every file under *root*, as ``repo-relative path -> bytes``."""
    base = project_dir / root
    return {
        candidate.relative_to(project_dir).as_posix(): candidate.read_bytes()
        for candidate in sorted(base.rglob("*"))
        if candidate.is_file()
    }


def age_project(project_dir: Path, aliases: dict[str, str]) -> None:
    """Rewrite an installed project into the state the previous release left.

    Renames each installed skill directory to its retired id and repoints the
    manifest rows at the new paths. Nothing about the bytes changes, so the
    recorded hash still matches the disk: to reconciliation this is a project
    Lore installed and nobody has touched since.
    """
    payload = read_manifest(project_dir)
    moves: set[tuple[str, str, str]] = set()

    for row in payload["files"]:
        for current, retired in aliases.items():
            marker = f"/{current}/"
            if marker not in row["path"]:
                continue
            moves.add((row["path"].split(marker)[0], current, retired))
            row["path"] = row["path"].replace(marker, f"/{retired}/", 1)
            row["source"] = f"skill:{retired}"

    for root, current, retired in moves:
        shutil.move(
            str(project_dir / root / current), str(project_dir / root / retired)
        )

    payload["files"].sort(key=lambda row: row["path"])
    write_manifest(project_dir, payload)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fresh(tmp_path, monkeypatch):
    """An empty directory that is the working directory for the whole test."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture()
def installed(runner, fresh):
    """A project this release installed for Claude, with every skill family."""
    init(runner, "--agent", "claude", "--skills", "all", "--yes")
    return fresh


@pytest.fixture()
def aged(runner, installed):
    """`installed`, rewound to the skill set the release before it shipped.

    Three retired ids, chosen from the ledger rather than named: a plain rename,
    a merge, and a merge of a skill that ships reference files — which is what
    puts a nested directory in the path of the removal sweep.
    """
    age_project(
        installed,
        {
            "update-doctrine": retired_alias("update-doctrine"),
            "retrieve-memory": retired_alias("retrieve-memory"),
            "store-memory": retired_alias("store-memory"),
        },
    )
    return installed


@pytest.fixture()
def hashed_paths(monkeypatch):
    """Every path reconciliation hashes on the way to a plan, in call order.

    `manifest.file_digest` is the one function that reads a whole file Lore did
    not just render, so what it is asked for *is* what `lore init` reads.
    """
    seen: list[Path] = []
    original = manifest.file_digest

    def spy(path):
        seen.append(Path(path))
        return original(path)

    monkeypatch.setattr(manifest, "file_digest", spy)
    return seen


@pytest.fixture()
def legacy_table(monkeypatch):
    """Substitute the packaged historical-hash table for one test.

    Returns a function taking ``path -> digests``. The shipped table records
    releases this test run has no wheel for; everything downstream of the table
    is untouched.
    """

    def install(files: dict[str, list[str]]) -> None:
        payload = {"legacy_hashes_version": 1, "files": files}
        monkeypatch.setattr(reconcile, "_read_legacy_payload", lambda: payload)
        reconcile.load_legacy_hashes.cache_clear()

    yield install
    reconcile.load_legacy_hashes.cache_clear()


# ---------------------------------------------------------------------------
# Scenario 1 — a project on the pre-consolidation skill set is upgraded
# ---------------------------------------------------------------------------


class TestPreConsolidationUpgrade:
    """Re-running `lore init` retires the old skill set and installs the new one."""

    def test_the_plan_removes_every_retired_skill(self, runner, aged):
        rows = plan_rows(plan(runner))
        for current in ("update-doctrine", "retrieve-memory"):
            path = f"{CLAUDE_SKILLS}/{retired_alias(current)}/SKILL.md"
            assert rows[path][0] == "Remove"

    def test_the_plan_creates_every_replacement(self, runner, aged):
        rows = plan_rows(plan(runner))
        for current in ("update-doctrine", "retrieve-memory", "store-memory"):
            assert rows[f"{CLAUDE_SKILLS}/{current}/SKILL.md"][0] == "Create"

    def test_the_plan_reports_no_conflict(self, runner, aged):
        assert plan_counts(plan(runner))["conflict"] == 0

    def test_every_retired_directory_is_gone_after_the_run(self, runner, aged):
        init(runner, "--yes")
        for current in ("update-doctrine", "retrieve-memory", "store-memory"):
            assert not (aged / CLAUDE_SKILLS / retired_alias(current)).exists()

    def test_every_replacement_is_present_after_the_run(self, runner, aged):
        init(runner, "--yes")
        for current in ("update-doctrine", "retrieve-memory", "store-memory"):
            assert (aged / CLAUDE_SKILLS / current / "SKILL.md").is_file()

    def test_the_removal_quotes_the_ledger_reason(self, runner, aged):
        result = init(runner, "--yes")
        reported = removals(result.output)
        for current in ("update-doctrine", "retrieve-memory"):
            alias = retired_alias(current)
            path = shown(f"{CLAUDE_SKILLS}/{alias}/SKILL.md")
            assert_names_the_retirement(reported[path], alias)

    def test_the_plan_carries_the_same_reason_as_the_run(self, runner, aged):
        alias = retired_alias("update-doctrine")
        rows = plan_rows(plan(runner))
        assert_names_the_retirement(rows[f"{CLAUDE_SKILLS}/{alias}/SKILL.md"][1], alias)

    def test_a_retired_skills_reference_files_go_with_it(self, runner, aged):
        alias = retired_alias("store-memory")
        assert (aged / CLAUDE_SKILLS / alias / "references").is_dir()
        init(runner, "--yes")
        assert not (aged / CLAUDE_SKILLS / alias).exists()

    def test_the_replacements_reference_files_are_installed(self, runner, aged):
        init(runner, "--yes")
        references = aged / CLAUDE_SKILLS / "store-memory" / "references"
        assert sorted(path.name for path in references.iterdir()) == sorted(
            Path(relative).name
            for relative in skills.skill_files("store-memory")
            if relative != skills.SKILL_FILE
        )

    def test_the_skills_root_survives_the_sweep(self, runner, aged):
        init(runner, "--yes")
        assert (aged / CLAUDE_SKILLS).is_dir()

    def test_the_manifest_forgets_the_retired_paths(self, runner, aged):
        init(runner, "--yes")
        recorded = recorded_paths(aged)
        for current in ("update-doctrine", "retrieve-memory", "store-memory"):
            alias = retired_alias(current)
            assert not any(f"/{alias}/" in path for path in recorded)

    def test_the_manifest_records_the_replacements(self, runner, aged):
        init(runner, "--yes")
        recorded = recorded_paths(aged)
        for current in ("update-doctrine", "retrieve-memory", "store-memory"):
            assert f"{CLAUDE_SKILLS}/{current}/SKILL.md" in recorded

    def test_the_upgrade_settles_in_one_run(self, runner, aged):
        init(runner, "--yes")
        assert plan_counts(plan(runner)) == dict.fromkeys(COUNT_BUCKETS, 0)


# ---------------------------------------------------------------------------
# Scenario 2 — the user edited an installed skill
# ---------------------------------------------------------------------------


EDIT = "\n<!-- a line the project added -->\n"


def edit(project_dir: Path, relative: str) -> bytes:
    """Append a line to an installed file and return its new bytes."""
    target = project_dir / relative
    target.write_bytes(target.read_bytes() + EDIT.encode("utf-8"))
    return target.read_bytes()


class TestAnEditedSkill:
    """Lore owns the files it installs, so an edit to one is not a question.

    Knights, doctrines, artifacts and watchers have always been overwritten in
    place — they are seeded under `default/`, which is what that directory name
    says. Skills were the one tree that behaved differently, keeping an edited
    file and asking. They no longer do.
    """

    EDITED = f"{CLAUDE_SKILLS}/inquest/SKILL.md"

    def test_the_edit_is_reported_as_an_overwrite(self, runner, installed):
        edit(installed, self.EDITED)
        assert plan_rows(plan(runner))[self.EDITED][0] == "Overwrite"

    def test_the_row_says_the_edit_is_going(self, runner, installed):
        edit(installed, self.EDITED)
        assert reconcile.EDIT_DISCARDED in plan_rows(plan(runner))[self.EDITED][1]

    def test_the_row_names_where_a_skill_of_their_own_belongs(
        self, runner, installed
    ):
        """The one thing `default/` says for the other four entity types.

        Losing an edit is the ruling. Losing an edit with no way to know how to
        avoid the next one is not, and a skills directory carries no convention
        of its own to tell them.
        """
        edit(installed, self.EDITED)
        assert CLAUDE_SKILLS in plan_rows(plan(runner))[self.EDITED][1]

    def test_the_applied_run_names_it_too(self, runner, installed):
        """The plan is not where most projects meet this row.

        A terminal run renders the plan and asks; `--yes`, a pipe, a CI job and
        Realm write without one. The report those runs print built its line
        from the action alone, so the only project that actually loses an edit
        was the only one never told where a copy of its own would have
        survived.
        """
        edit(installed, self.EDITED)

        output = init(runner, "--yes").output

        assert reconcile.EDIT_DISCARDED in output
        assert f"{CLAUDE_SKILLS}/<your-own-id>/" in output

    def test_the_applied_run_still_reports_the_path_as_written(
        self, runner, installed
    ):
        edit(installed, self.EDITED)
        assert self.EDITED in written(init(runner, "--yes").output)

    def test_an_untouched_write_carries_no_detail(self, runner, fresh):
        output = init(runner, "--agent", "claude", "--skills", "all", "--yes").output
        assert reconcile.EDIT_DISCARDED not in output

    def test_the_default_run_restores_what_this_release_ships(
        self, runner, installed
    ):
        pristine = (installed / self.EDITED).read_bytes()
        edit(installed, self.EDITED)
        init(runner, "--yes")
        assert (installed / self.EDITED).read_bytes() == pristine

    def test_the_default_run_reports_the_write(self, runner, installed):
        edit(installed, self.EDITED)
        result = init(runner, "--yes")
        assert self.EDITED in written(result.output)
        assert self.EDITED not in kept(result.output)

    def test_skip_does_not_spare_it(self, runner, installed):
        """The policy is not a way back to the behaviour the ruling replaced."""
        pristine = (installed / self.EDITED).read_bytes()
        edit(installed, self.EDITED)
        init(runner, "--on-conflict", "skip", "--yes")
        assert (installed / self.EDITED).read_bytes() == pristine

    def test_overwrite_replaces_the_edit(self, runner, installed):
        edited = edit(installed, self.EDITED)
        init(runner, "--on-conflict", "overwrite", "--yes")
        assert (installed / self.EDITED).read_bytes() != edited

    def test_overwrite_restores_what_this_release_ships(self, runner, installed):
        pristine = (installed / self.EDITED).read_bytes()
        edit(installed, self.EDITED)
        init(runner, "--on-conflict", "overwrite", "--yes")
        assert (installed / self.EDITED).read_bytes() == pristine

    def test_overwrite_reports_the_write(self, runner, installed):
        edit(installed, self.EDITED)
        result = init(runner, "--on-conflict", "overwrite", "--yes")
        assert self.EDITED in written(result.output)

    def test_overwrite_records_the_file_again(self, runner, installed):
        edit(installed, self.EDITED)
        init(runner, "--on-conflict", "overwrite", "--yes")
        assert self.EDITED in recorded_paths(installed)

    def test_one_run_settles_it(self, runner, installed):
        edit(installed, self.EDITED)
        init(runner, "--yes")
        assert plan_counts(plan(runner)) == dict.fromkeys(COUNT_BUCKETS, 0)

    def test_a_crlf_rewrite_is_an_edit_and_is_replaced(self, runner, installed):
        """A line-ending sweep is a byte change, and byte changes are edits."""
        target = installed / self.EDITED
        pristine = target.read_bytes()
        target.write_bytes(pristine.replace(b"\n", b"\r\n"))
        assert plan_rows(plan(runner))[self.EDITED][0] == "Overwrite"
        init(runner, "--yes")
        assert target.read_bytes() == pristine

    def test_a_deleted_skill_file_is_restored_rather_than_reported(
        self, runner, installed
    ):
        (installed / self.EDITED).unlink()
        assert plan_rows(plan(runner))[self.EDITED][0] == "Create"
        init(runner, "--yes")
        assert (installed / self.EDITED).is_file()


class TestAnEditedSkillThatRetires:
    """A file Lore installed and has since retired goes, and names its successor.

    Round 3's defect 4 was the other half of this: an edited retired skill was
    kept with nothing naming what replaced it, so a project sat on a directory
    no release ships and its agent went on reading it. Under the ownership
    ruling there is no keeping — only a removal that says where the thinking in
    the file now belongs.
    """

    @pytest.fixture()
    def edited_alias(self, aged):
        alias = retired_alias("update-doctrine")
        relative = f"{CLAUDE_SKILLS}/{alias}/SKILL.md"
        edit(aged, relative)
        return alias, relative

    def test_the_default_run_removes_it(self, runner, aged, edited_alias):
        _, relative = edited_alias
        init(runner, "--yes")
        assert not (aged / relative).exists()

    def test_the_report_names_the_successor(self, runner, aged, edited_alias):
        alias, relative = edited_alias
        result = init(runner, "--yes")
        assert_names_the_retirement(removals(result.output)[shown(relative)], alias)

    def test_the_report_admits_the_edit_went_with_it(self, runner, aged, edited_alias):
        _, relative = edited_alias
        result = init(runner, "--yes")
        assert reconcile.EDIT_DISCARDED in removals(result.output)[shown(relative)]

    def test_an_unedited_removal_says_nothing_about_an_edit(self, runner, aged):
        alias = retired_alias("retrieve-memory")
        relative = f"{CLAUDE_SKILLS}/{alias}/SKILL.md"
        result = init(runner, "--yes")
        assert reconcile.EDIT_DISCARDED not in removals(result.output)[shown(relative)]

    def test_the_plan_names_the_successor_too(self, runner, aged, edited_alias):
        alias, relative = edited_alias
        assert ledger_successor(alias) in plan_rows(plan(runner))[relative][1]

    def test_the_replacement_is_installed_in_its_place(
        self, runner, aged, edited_alias
    ):
        init(runner, "--yes")
        assert (aged / CLAUDE_SKILLS / "update-doctrine" / "SKILL.md").is_file()

    def test_skip_does_not_spare_it_either(self, runner, aged, edited_alias):
        _, relative = edited_alias
        init(runner, "--on-conflict", "skip", "--yes")
        assert not (aged / relative).exists()

    def test_one_run_settles_it(self, runner, aged, edited_alias):
        init(runner, "--yes")
        assert plan_counts(plan(runner)) == dict.fromkeys(COUNT_BUCKETS, 0)


# ---------------------------------------------------------------------------
# Scenario 3 — a file the project authored and Lore never installed
# ---------------------------------------------------------------------------


class TestFilesLoreNeverInstalled:
    """The safety property: never read, never written, never deleted."""

    USER_FILE = f"{CLAUDE_SKILLS}/NOTES.md"
    USER_SKILL = f"{CLAUDE_SKILLS}/team-review/SKILL.md"
    USER_CONTENT = b"the project wrote this\n"

    @pytest.fixture()
    def authored(self, installed):
        for relative in (self.USER_FILE, self.USER_SKILL):
            target = installed / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self.USER_CONTENT)
        return installed

    def test_a_user_file_in_the_skills_tree_survives(self, runner, authored):
        init(runner, "--yes")
        assert (authored / self.USER_FILE).read_bytes() == self.USER_CONTENT

    def test_a_user_skill_directory_survives(self, runner, authored):
        init(runner, "--yes")
        assert (authored / self.USER_SKILL).read_bytes() == self.USER_CONTENT

    def test_neither_is_reported_in_the_plan(self, runner, authored):
        rows = plan_rows(plan(runner))
        assert self.USER_FILE not in rows
        assert self.USER_SKILL not in rows

    def test_neither_is_reported_by_the_run(self, runner, authored):
        result = init(runner, "--yes")
        assert self.USER_FILE not in result.output
        assert self.USER_SKILL not in result.output

    def test_neither_enters_the_manifest(self, runner, authored):
        init(runner, "--yes")
        recorded = recorded_paths(authored)
        assert self.USER_FILE not in recorded
        assert self.USER_SKILL not in recorded

    def test_neither_is_ever_read(self, runner, authored, hashed_paths):
        plan(runner)
        read = {path.resolve() for path in hashed_paths}
        assert read, "nothing was hashed at all; the spy is not on the read path"
        assert (authored / self.USER_FILE).resolve() not in read
        assert (authored / self.USER_SKILL).resolve() not in read

    def test_a_user_file_survives_a_retirement_sweep_around_it(self, runner, aged):
        alias = retired_alias("update-doctrine")
        note = aged / CLAUDE_SKILLS / alias / "NOTES.md"
        note.write_bytes(self.USER_CONTENT)

        init(runner, "--yes")

        assert not (aged / CLAUDE_SKILLS / alias / "SKILL.md").exists()
        assert note.read_bytes() == self.USER_CONTENT

    def test_the_directory_it_lives_in_is_not_pruned(self, runner, aged):
        alias = retired_alias("store-memory")
        note = aged / CLAUDE_SKILLS / alias / "references" / "NOTES.md"
        note.write_bytes(self.USER_CONTENT)

        init(runner, "--yes")

        assert note.is_file()
        assert (aged / CLAUDE_SKILLS / alias).is_dir()

    def test_a_file_at_a_path_lore_wants_is_a_conflict_not_an_overwrite(
        self, runner, fresh
    ):
        target = fresh / CLAUDE_SKILLS / "inquest" / "SKILL.md"
        target.parent.mkdir(parents=True)
        target.write_bytes(self.USER_CONTENT)

        result = init(runner, "--agent", "claude", "--skills", "all", "--yes")

        assert target.read_bytes() == self.USER_CONTENT
        relative = f"{CLAUDE_SKILLS}/inquest/SKILL.md"
        assert kept(result.output)[relative] == reconcile.NOT_INSTALLED_BY_LORE

    def test_an_instruction_file_survives_its_block_being_retired(self, runner, fresh):
        (fresh / "AGENTS.md").write_bytes(b"# House rules\n\nours.\n")
        init(runner, "--agent", "claude", "agents-md", "--skills", "all", "--yes")

        init(runner, "--agent", "claude", "--yes")

        assert (fresh / "AGENTS.md").read_bytes() == b"# House rules\n\nours.\n"

    def test_deselecting_the_last_agent_removes_the_file_lore_created(
        self, runner, fresh
    ):
        """A `CLAUDE.md` that held nothing but Lore's block was never the user's."""
        init(runner, "--agent", "claude", "--skills", "memory", "--yes")
        assert (fresh / "CLAUDE.md").is_file()

        init(runner, "--agent", "gemini", "--yes")

        assert not (fresh / "CLAUDE.md").exists()

    def test_deselecting_an_agent_never_leaves_a_zero_byte_instruction_file(
        self, runner, fresh
    ):
        init(runner, "--agent", "claude", "--skills", "memory", "--yes")
        init(runner, "--agent", "gemini", "--yes")

        empty = [
            path.name
            for path in fresh.iterdir()
            if path.is_file() and path.stat().st_size == 0
        ]
        assert empty == []

    def test_the_run_reports_removing_it(self, runner, fresh):
        init(runner, "--agent", "claude", "--skills", "memory", "--yes")

        result = init(runner, "--agent", "gemini", "--yes")

        assert "CLAUDE.md" in removals(result.output)

    def test_deselecting_an_agent_removes_only_its_copy_of_the_skills(
        self, runner, fresh
    ):
        init(runner, "--agent", "claude", "agents-md", "--skills", "all", "--yes")
        assert (fresh / LORE_SKILLS / "inquest" / "SKILL.md").is_file()

        init(runner, "--agent", "claude", "--yes")

        assert not (fresh / LORE_SKILLS / "inquest").exists()
        assert (fresh / CLAUDE_SKILLS / "inquest" / "SKILL.md").is_file()


# ---------------------------------------------------------------------------
# Scenario 2b — the ownership boundary: what proves a path is Lore's
# ---------------------------------------------------------------------------


def retired_ids() -> tuple[str, ...]:
    """Every id in the retirement ledger.

    Read from the catalogue rather than named: the ledger is append-only, so a
    test that enumerates it covers whatever a later release retires, and the
    property under test is about the whole class rather than the id that
    happened to be found.
    """
    return tuple(sorted(skills.load_catalogue().get("retired", {})))


class TestOnlyTheRecordDecidesWhatLoreOwns:
    """The one question the ruling rests on: *did Lore install this path here?*

    Owning its own files means Lore overwrites and removes without asking, so
    the answer now authorises destruction and nothing weaker than a record may
    give it. A manifest is that record — the list of what this project's own
    runs wrote — and a project holding one has no need of a guess. The
    historical table's per-*tree* evidence ("something under this root hashes
    to something Lore shipped") answers a different question, and merging it in
    anyway claimed every path the table names at that root: paths the manifest
    deliberately does not list because the run that met them declined to take
    them, and paths no run ever wrote at all.
    """

    OURS = b"the project wrote this, never Lore\n"

    def plant(self, project_dir: Path, relative: str) -> Path:
        target = project_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.OURS)
        return target

    def retired_path(self, root: str = CLAUDE_SKILLS) -> str:
        return f"{root}/{retired_ids()[0]}/SKILL.md"

    # -- a skill of the project's own at an id Lore has retired -------------

    def test_a_user_skill_at_a_retired_id_survives(self, runner, installed):
        """`lore init --help` promises a skill under an id Lore does not ship
        is never changed or removed. A retired id is such an id, and the
        retirement sweep matched by name — so following the documentation
        picked one of thirteen mines."""
        target = self.plant(installed, self.retired_path())

        init(runner, "--yes")

        assert target.read_bytes() == self.OURS

    def test_every_id_in_the_ledger_survives(self, runner, installed):
        planted = {
            skill_id: self.plant(installed, f"{CLAUDE_SKILLS}/{skill_id}/SKILL.md")
            for skill_id in retired_ids()
        }

        init(runner, "--yes")

        assert planted
        assert [skill_id for skill_id, path in planted.items() if not path.is_file()] == []

    def test_it_is_not_reported_by_the_run(self, runner, installed):
        self.plant(installed, self.retired_path())

        result = init(runner, "--yes")

        assert self.retired_path() not in result.output

    def test_it_is_absent_from_the_plan(self, runner, installed):
        self.plant(installed, self.retired_path())
        assert self.retired_path() not in plan_rows(plan(runner))

    def test_reading_it_is_all_a_run_ever_does_to_it(
        self, runner, installed, hashed_paths
    ):
        """A path the historical table names *is* hashed, and that is the point.

        The safety property is about paths in neither set; this one is in the
        candidate set, because a rollback to an older `lore` reinstalls retired
        skills that no later manifest mentions and hashing them is the only way
        a later run can ever clear them. What the hash decides is the whole
        question: bytes Lore shipped are Lore's file, and anything else is the
        project's and is left exactly as it was found. An id Lore has *never*
        shipped is not a candidate at all — see `TestFilesLoreNeverInstalled`.
        """
        target = self.plant(installed, self.retired_path())
        before = target.stat().st_mtime_ns

        plan(runner)
        init(runner, "--yes")

        assert target.resolve() in {path.resolve() for path in hashed_paths}
        assert target.read_bytes() == self.OURS
        assert target.stat().st_mtime_ns == before

    def test_the_directory_it_lives_in_is_not_pruned(self, runner, installed):
        target = self.plant(installed, self.retired_path())
        init(runner, "--yes")
        assert target.parent.is_dir()

    def test_the_same_holds_in_the_lore_skills_tree(self, runner, fresh):
        init(runner, "--agent", "none", "--skills", "all", "--yes")
        target = self.plant(fresh, self.retired_path(LORE_SKILLS))

        init(runner, "--agent", "none", "--yes")

        assert target.read_bytes() == self.OURS

    def test_a_retired_skill_lore_did_install_is_still_removed(self, runner, aged):
        """The boundary cuts one way only: a path the manifest records is Lore's."""
        alias = retired_alias("update-doctrine")
        target = aged / CLAUDE_SKILLS / alias / "SKILL.md"
        assert target.is_file()

        init(runner, "--yes")

        assert not target.exists()

    # -- the general rule, stated over paths rather than names --------------

    def test_no_path_outside_the_manifest_is_touched(self, runner, installed):
        """The principle, tested over every path the historical table names.

        Whatever the table knows, this project's own record is the statement
        about this project — so a file at any of those paths that the manifest
        does not list is the project's own file and stays byte-identical.
        """
        recorded = recorded_paths(installed)
        candidates = {
            path.replace(LORE_SKILLS, CLAUDE_SKILLS, 1)
            for path in reconcile.load_legacy_hashes()
            if path.startswith(f"{LORE_SKILLS}/")
        }
        planted = {
            relative: self.OURS
            for relative in sorted(candidates)
            if relative not in recorded
        }
        assert planted, "the shipped table names no path outside this manifest"
        for relative in planted:
            self.plant(installed, relative)

        init(runner, "--yes")

        assert {
            relative: (installed / relative).read_bytes()
            if (installed / relative).is_file()
            else None
            for relative in planted
        } == planted


class TestKeepingAFileIsStableAcrossRuns:
    """A file Lore did not install stays a file Lore did not install.

    `--on-conflict skip` is the answer that leaves such a file alone, and the
    run that gave it deliberately keeps the path out of the manifest. The next
    run then read the *tree* — every current skill the same run installed
    beside it hashes into the historical table — and claimed the path back on
    evidence about its neighbours. A protection that lapses on the second
    invocation is worse than none, because the project watched it work.
    """

    OURS = b"the project wrote this, never Lore\n"
    MINE = f"{CLAUDE_SKILLS}/inquest/SKILL.md"

    @pytest.fixture()
    def theirs(self, runner, fresh):
        target = fresh / self.MINE
        target.parent.mkdir(parents=True)
        target.write_bytes(self.OURS)
        return target

    def run(self, runner, *args):
        return init(runner, "--agent", "claude", "--skills", "all", *args, "--yes")

    def test_the_first_run_keeps_it(self, runner, theirs):
        result = self.run(runner, "--on-conflict", "skip")
        assert theirs.read_bytes() == self.OURS
        assert kept(result.output)[self.MINE] == reconcile.NOT_INSTALLED_BY_LORE

    def test_the_second_run_keeps_it_too(self, runner, theirs):
        self.run(runner, "--on-conflict", "skip")

        self.run(runner, "--on-conflict", "skip")

        assert theirs.read_bytes() == self.OURS

    def test_the_second_run_reports_it_the_same_way(self, runner, theirs):
        self.run(runner, "--on-conflict", "skip")

        result = self.run(runner, "--on-conflict", "skip")

        assert kept(result.output)[self.MINE] == reconcile.NOT_INSTALLED_BY_LORE

    def test_the_third_run_keeps_it_as_well(self, runner, theirs):
        for _ in range(3):
            self.run(runner, "--on-conflict", "skip")
        assert theirs.read_bytes() == self.OURS

    def test_the_default_answer_holds_across_runs_too(self, runner, theirs):
        self.run(runner)

        self.run(runner)

        assert theirs.read_bytes() == self.OURS

    def test_a_hand_made_skills_gitignore_holds_too(self, runner, fresh):
        target = fresh / CLAUDE_SKILLS / ".gitignore"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"# ours\n*.tmp\n")
        self.run(runner)

        self.run(runner)

        assert target.read_bytes() == b"# ours\n*.tmp\n"

    def test_it_never_enters_the_manifest(self, runner, theirs):
        self.run(runner)
        self.run(runner)
        assert self.MINE not in recorded_paths(theirs.parents[3])

    def test_overwrite_still_hands_the_path_over(self, runner, theirs):
        """Stable is not immovable: the flag that takes the file still does."""
        self.run(runner)

        self.run(runner, "--on-conflict", "overwrite")

        assert theirs.read_bytes() != self.OURS

    def test_the_run_after_that_owns_it(self, runner, theirs):
        self.run(runner)
        self.run(runner, "--on-conflict", "overwrite")
        recorded = recorded_paths(theirs.parents[3])
        assert self.MINE in recorded


class TestAFixedPathWithNothingToVouchForIt:
    """`.lore/LORE-AGENT.md` asked for no evidence at all.

    The skills half of the same fallback asks whether anything under the root
    proves Lore installed there; the fixed-path half added its keys to the
    claimed set unconditionally, so a hand-written agent doc in a directory
    Lore has never written to was overwritten and its content lost. Two halves
    of one question answered by different rules.
    """

    MINE = b"# our own agent notes\n"

    def test_a_hand_written_agent_doc_is_kept(self, runner, fresh):
        target = fresh / ".lore" / "LORE-AGENT.md"
        target.parent.mkdir(parents=True)
        target.write_bytes(self.MINE)

        init(runner, "--agent", "claude", "--skills", "all", "--yes")

        assert target.read_bytes() == self.MINE

    def test_it_is_reported_as_a_file_lore_did_not_install(self, runner, fresh):
        target = fresh / ".lore" / "LORE-AGENT.md"
        target.parent.mkdir(parents=True)
        target.write_bytes(self.MINE)

        result = init(runner, "--agent", "claude", "--skills", "all", "--yes")

        assert kept(result.output)["LORE-AGENT.md"] == reconcile.NOT_INSTALLED_BY_LORE

    def test_a_project_lore_did_install_into_still_owns_its_agent_doc(
        self, runner, installed
    ):
        target = installed / ".lore" / "LORE-AGENT.md"
        edited = target.read_bytes() + b"\nmine\n"
        target.write_bytes(edited)

        init(runner, "--yes")

        assert target.read_bytes() != edited

class TestAFileThatAlreadyHoldsTheShippedBytes:
    """A write that would change nothing is a no-op, never a conflict.

    The recorded hash and the disk can disagree while the disk holds exactly
    what this release would write — someone applied the new content by hand, or
    a run was interrupted after the write and before the manifest. Either way
    there is nothing to overwrite, so there is nothing to ask about.
    """

    @pytest.fixture()
    def misrecorded(self, runner, fresh):
        """An installed project whose manifest disagrees with an untouched file."""
        init(runner, "--agent", "claude", "--skills", "memory", "--yes")
        payload = read_manifest(fresh)
        row = next(
            row for row in payload["files"] if row["path"].endswith("/SKILL.md")
        )
        row["hash"] = "sha256:" + "0" * 64
        write_manifest(fresh, payload)
        return row["path"]

    def test_the_summary_calls_it_nothing_at_all(self, runner, fresh, misrecorded):
        summary = plan(runner, "--agent", "claude", "--skills", "memory")

        assert misrecorded not in plan_rows(summary)
        assert plan_counts(summary)["conflict"] == 0

    def test_the_run_reports_no_conflict(self, runner, fresh, misrecorded):
        result = init(runner, "--agent", "claude", "--skills", "memory", "--yes")

        assert kept(result.output) == {}

    def test_the_file_stays_in_the_manifest(self, runner, fresh, misrecorded):
        init(runner, "--agent", "claude", "--skills", "memory", "--yes")

        assert misrecorded in recorded_paths(fresh)

    def test_the_next_run_still_knows_lore_installed_it(
        self, runner, fresh, misrecorded
    ):
        init(runner, "--agent", "claude", "--skills", "memory", "--yes")

        summary = plan(runner, "--agent", "claude", "--skills", "memory")

        assert reconcile.NOT_INSTALLED_BY_LORE not in summary

    def test_the_recorded_hash_becomes_the_bytes_on_disk(
        self, runner, fresh, misrecorded
    ):
        init(runner, "--agent", "claude", "--skills", "memory", "--yes")

        row = next(
            row for row in read_manifest(fresh)["files"] if row["path"] == misrecorded
        )
        assert row["hash"] == manifest.file_digest(fresh / misrecorded)


# ---------------------------------------------------------------------------
# Scenario 4 — a project that predates the install manifest
# ---------------------------------------------------------------------------


class TestProjectWithNoManifest:
    """The legacy-hash fallback: match what Lore shipped, keep everything else."""

    @pytest.fixture()
    def unmanifested(self, runner, fresh):
        """A project whose skills live in `.lore/skills/` and that has no manifest.

        `--agent none` puts the skills where every pre-feature release installed
        them. `TestPreFeatureSkillsInTheAgentDirectory` covers the other tree the
        fallback walks — the copy the pre-feature docs told people to make.
        """
        init(runner, "--agent", "none", "--skills", "all", "--yes")
        age_project(fresh, {"update-doctrine": retired_alias("update-doctrine")})
        manifest_path(fresh).unlink()
        return fresh

    def alias_path(self) -> str:
        return f"{LORE_SKILLS}/{retired_alias('update-doctrine')}/SKILL.md"

    def matching_table(self, project_dir: Path) -> dict[str, list[str]]:
        """A historical table that recognises the aged file exactly as shipped."""
        relative = self.alias_path()
        return {relative: [manifest.file_digest(project_dir / relative)]}

    def test_a_matched_file_is_removed(self, runner, unmanifested, legacy_table):
        legacy_table(self.matching_table(unmanifested))
        init(runner, "--yes")
        assert not (unmanifested / self.alias_path()).exists()

    def test_the_removal_quotes_the_ledger_reason(
        self, runner, unmanifested, legacy_table
    ):
        legacy_table(self.matching_table(unmanifested))
        result = init(runner, "--yes")
        alias = retired_alias("update-doctrine")
        assert_names_the_retirement(
            removals(result.output)[shown(self.alias_path())], alias
        )

    def test_the_replacement_is_installed(self, runner, unmanifested, legacy_table):
        legacy_table(self.matching_table(unmanifested))
        init(runner, "--yes")
        assert (unmanifested / LORE_SKILLS / "update-doctrine" / "SKILL.md").is_file()

    def test_an_edited_file_in_a_tree_lore_cannot_claim_is_kept(
        self, runner, unmanifested, legacy_table
    ):
        """The guess is admitted from a tree, never from a path.

        This table knows one path and the bytes there no longer match it, so
        nothing under `.lore/skills/` proves Lore ever wrote into it. A guess is
        all that would authorise the unlink, and a guess is not enough to
        destroy a file — FR-28 read the way the ruling leaves it.
        """
        legacy_table(self.matching_table(unmanifested))
        expected = edit(unmanifested, self.alias_path())
        init(runner, "--yes")
        assert (unmanifested / self.alias_path()).read_bytes() == expected

    def test_an_edited_file_in_a_tree_lore_can_claim_is_removed(
        self, runner, unmanifested
    ):
        """No substitution: the shipped table recognises this release's own files.

        So the tree is demonstrably one Lore installed into, and the aged
        directory in it is Lore's whatever its bytes are now.
        """
        init(runner, "--yes")
        assert not (unmanifested / self.alias_path()).exists()

    def test_that_removal_is_reported_with_its_successor(self, runner, unmanifested):
        # Round 3's defect 4: this used to be the one file in the sweep the
        # report said nothing at all about.
        row = plan_rows(plan(runner))[self.alias_path()]
        assert row[0] == "Remove"
        assert ledger_successor(retired_alias("update-doctrine")) in row[1]

    def test_a_path_the_table_does_not_know_is_kept(
        self, runner, unmanifested, legacy_table
    ):
        legacy_table(self.matching_table(unmanifested))
        stray = unmanifested / LORE_SKILLS / "house-style" / "SKILL.md"
        stray.parent.mkdir(parents=True)
        stray.write_bytes(b"ours\n")

        init(runner, "--yes")

        assert stray.read_bytes() == b"ours\n"

    def test_untouched_current_skills_are_left_alone(
        self, runner, unmanifested, legacy_table
    ):
        legacy_table(self.matching_table(unmanifested))
        before = tree(unmanifested, f"{LORE_SKILLS}/inquest")
        init(runner, "--yes")
        assert tree(unmanifested, f"{LORE_SKILLS}/inquest") == before

    def test_the_run_writes_a_fresh_manifest(self, runner, unmanifested, legacy_table):
        legacy_table(self.matching_table(unmanifested))
        init(runner, "--yes")
        assert manifest_path(unmanifested).is_file()

    def test_the_fresh_manifest_records_what_is_installed_now(
        self, runner, unmanifested, legacy_table
    ):
        legacy_table(self.matching_table(unmanifested))
        init(runner, "--yes")
        recorded = recorded_paths(unmanifested)
        assert f"{LORE_SKILLS}/update-doctrine/SKILL.md" in recorded
        assert self.alias_path() not in recorded

    def test_the_fallback_never_runs_for_that_project_again(
        self, runner, unmanifested, legacy_table
    ):
        legacy_table(self.matching_table(unmanifested))
        init(runner, "--yes")
        legacy_table({})
        assert plan_counts(plan(runner)) == dict.fromkeys(COUNT_BUCKETS, 0)

    def test_an_unreadable_manifest_falls_back_and_warns(self, runner, installed):
        manifest_path(installed).write_text("not json", encoding="utf-8")
        from lore.cli import main

        result = runner.invoke(main, ["init", "--dry-run"])

        assert result.exit_code == 0, result.output
        assert "unreadable install manifest" in result.stderr

    def test_an_unreadable_manifest_destroys_nothing(self, runner, installed):
        before = tree(installed, CLAUDE_SKILLS)
        manifest_path(installed).write_text("not json", encoding="utf-8")

        init(runner, "--yes")

        assert tree(installed, CLAUDE_SKILLS) == before

    def test_an_unreadable_manifest_is_replaced_by_a_readable_one(
        self, runner, installed
    ):
        manifest_path(installed).write_text("not json", encoding="utf-8")
        init(runner, "--yes")
        assert read_manifest(installed)["files"]


# ---------------------------------------------------------------------------
# Scenario 4b — a project that predates the manifest and followed the old docs
# ---------------------------------------------------------------------------


class TestACloneOfAProjectThatCommitsItsSkills:
    """`--skills-gitignore none` commits the skills; `.lore/.gitignore` drops the manifest.

    So every fresh clone of such a project reconciles through the shipped
    historical table, on the files this release itself installed. Nothing is
    substituted here: the table under test is the one the wheel carries.
    """

    INSTALL = ("--agent", "claude", "--skills", "all", "--skills-gitignore", "none")

    SKILL = f"{CLAUDE_SKILLS}/inquest/SKILL.md"

    @pytest.fixture()
    def cloned(self, runner, fresh):
        """A clone holding skills an earlier release installed, and no manifest.

        `.lore/.gitignore` drops the manifest and `.lore/LORE-AGENT.md`, so a
        fresh clone starts without either; the skills under `.claude/skills/`
        are committed, which is what the `none` tracking answer is for.

        The access mode stands in for the release: the committed files are
        rendered for `cli`, the run under test renders `native`, so every one of
        them differs from what this release would write. That is an upgrade
        arriving with nothing but the historical table to recognise it by — and
        a file installed by 0.10.0 or later is a *rendered* file, so a table
        holding only the unrendered sources matches none of them.
        """
        init(runner, *self.INSTALL, "--access", "cli", "--yes")
        manifest_path(fresh).unlink()
        (fresh / ".lore" / "LORE-AGENT.md").unlink()
        return fresh

    def upgrade(self, runner):
        return plan(runner, *self.INSTALL, "--access", "native")

    def skill_rows(self, summary):
        return {
            path: row
            for path, row in plan_rows(summary).items()
            if path.startswith(f"{CLAUDE_SKILLS}/")
        }

    def test_no_committed_skill_reads_as_a_stranger(self, runner, cloned):
        details = {row[1] for row in self.skill_rows(self.upgrade(runner)).values()}

        assert reconcile.NOT_INSTALLED_BY_LORE not in details

    def test_every_committed_skill_is_a_clean_overwrite(self, runner, cloned):
        labels = {row[0] for row in self.skill_rows(self.upgrade(runner)).values()}

        assert labels == {"Overwrite"}

    def test_the_upgrade_actually_lands_on_disk(self, runner, cloned):
        init(runner, *self.INSTALL, "--access", "native", "--yes")

        desired = skills.desired_files(
            targets=(), skill_families=skills.family_ids(), access_mode="native"
        )
        installed = desired[f"{LORE_SKILLS}/inquest/SKILL.md"].content
        assert (cloned / self.SKILL).read_bytes() == installed

    def test_the_rebuilt_manifest_records_the_committed_skills(self, runner, cloned):
        init(runner, *self.INSTALL, "--access", "native", "--yes")

        assert self.SKILL in recorded_paths(cloned)

    def test_the_downgrade_direction_works_the_same(self, runner, fresh):
        init(runner, *self.INSTALL, "--access", "native", "--yes")
        manifest_path(fresh).unlink()

        summary = plan(runner, *self.INSTALL, "--access", "cli")
        rows = self.skill_rows(summary)

        assert {row[0] for row in rows.values()} == {"Overwrite"}

    def test_a_file_the_clone_edited_is_taken_back(self, runner, cloned):
        """The clone committed Lore's files, so the historical table knows them.

        Which makes the tree one Lore installed into, and the edited file in it
        Lore's — the same answer a project with a manifest gets.
        """
        edited = cloned / self.SKILL
        edited.write_text("# ours now\n", encoding="utf-8")

        init(runner, *self.INSTALL, "--access", "native", "--yes")

        assert edited.read_text(encoding="utf-8") != "# ours now\n"
        assert self.SKILL in recorded_paths(cloned)


class TestPreFeatureSkillsInTheAgentDirectory:
    """The fallback reaches the tree the pre-feature docs told people to use.

    Lore's own `GETTING-STARTED.md` shipped `cp -r .lore/skills/. .claude/skills/`
    until this feature rewrote it, so a project on an old release has its skills
    under the agent's directory, not — or not only — under `.lore/skills/`. The
    historical table is keyed `.lore/skills/<rel>` whatever root the copy landed
    in, because that is the path Lore wrote it to when it hashed it.
    """

    ALIASED = ("update-doctrine", "retrieve-memory", "store-memory")
    """A rename, a merge, and a merge of a skill that ships reference files."""

    MINE = f"{CLAUDE_SKILLS}/house-style/SKILL.md"
    """A skill the project wrote. Lore has never shipped this path."""

    @pytest.fixture()
    def aliases(self) -> dict[str, str]:
        return {current: retired_alias(current) for current in self.ALIASED}

    @pytest.fixture()
    def copied(self, runner, fresh, aliases):
        """A no-manifest project whose skills sit where the old docs put them."""
        init(runner, "--agent", "claude", "--skills", "all", "--yes")
        age_project(fresh, aliases)
        manifest_path(fresh).unlink()
        return fresh

    @pytest.fixture()
    def both_trees(self, copied):
        """`copied` plus the `.lore/skills/` originals the copy was made from."""
        shutil.copytree(
            copied / CLAUDE_SKILLS, copied / LORE_SKILLS, dirs_exist_ok=True
        )
        return copied

    def historical(self, project_dir: Path, aliases: dict[str, str]) -> dict[str, list[str]]:
        """A table recognising the aged files, keyed the way Lore wrote them.

        Every row is `.lore/skills/<rel>` — the path of the install, not the
        path of the copy — so a hit under `.claude/skills/` is a lookup the
        table was never rekeyed for.
        """
        table: dict[str, list[str]] = {}
        for alias in aliases.values():
            for path, content in tree(project_dir, f"{CLAUDE_SKILLS}/{alias}").items():
                within = path[len(CLAUDE_SKILLS) + 1 :]
                table[f"{LORE_SKILLS}/{within}"] = [manifest.bytes_digest(content)]
        return table

    def plant_own_skill(self, project_dir: Path) -> Path:
        target = project_dir / self.MINE
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"ours\n")
        return target

    # -- the retired copies are found and removed ---------------------------

    def test_every_aged_directory_is_removed(
        self, runner, copied, aliases, legacy_table
    ):
        legacy_table(self.historical(copied, aliases))
        init(runner, "--yes")
        assert not [
            alias
            for alias in aliases.values()
            if (copied / CLAUDE_SKILLS / alias).exists()
        ]

    def test_every_removal_quotes_the_ledger_reason(
        self, runner, copied, aliases, legacy_table
    ):
        legacy_table(self.historical(copied, aliases))
        reported = removals(init(runner, "--yes").output)
        for alias in aliases.values():
            assert_names_the_retirement(
                reported.get(f"{CLAUDE_SKILLS}/{alias}/SKILL.md"), alias
            )

    def test_a_nested_reference_file_is_removed_with_its_skill(
        self, runner, copied, aliases, legacy_table
    ):
        table = self.historical(copied, aliases)
        nested = [path for path in table if "/references/" in path]
        assert nested, "no aged skill in this fixture ships reference files"
        legacy_table(table)

        init(runner, "--yes")

        alias_root = copied / CLAUDE_SKILLS / aliases["store-memory"]
        assert not alias_root.exists()

    def test_the_replacements_are_installed(
        self, runner, copied, aliases, legacy_table
    ):
        legacy_table(self.historical(copied, aliases))
        init(runner, "--yes")
        assert not [
            current
            for current in aliases
            if not (copied / CLAUDE_SKILLS / current / "SKILL.md").is_file()
        ]

    def test_the_fresh_manifest_records_the_replacements_not_the_aliases(
        self, runner, copied, aliases, legacy_table
    ):
        legacy_table(self.historical(copied, aliases))
        init(runner, "--yes")
        recorded = recorded_paths(copied)
        assert all(
            f"{CLAUDE_SKILLS}/{current}/SKILL.md" in recorded for current in aliases
        )
        assert not [
            alias
            for alias in aliases.values()
            if f"{CLAUDE_SKILLS}/{alias}/SKILL.md" in recorded
        ]

    def test_an_agent_without_a_skills_directory_still_clears_the_copy(
        self, runner, copied, aliases, legacy_table
    ):
        # Scanning only the agents selected this run would leave these behind.
        legacy_table(self.historical(copied, aliases))
        init(runner, "--agent", "gemini", "--yes")
        assert not [
            alias
            for alias in aliases.values()
            if (copied / CLAUDE_SKILLS / alias).exists()
        ]

    # -- a file Lore never installed is never read, moved or deleted --------

    def test_a_skill_lore_never_shipped_survives(
        self, runner, copied, aliases, legacy_table
    ):
        legacy_table(self.historical(copied, aliases))
        mine = self.plant_own_skill(copied)
        init(runner, "--yes")
        assert mine.read_bytes() == b"ours\n"

    def test_a_skill_lore_never_shipped_is_absent_from_the_plan(
        self, runner, copied, aliases, legacy_table
    ):
        legacy_table(self.historical(copied, aliases))
        self.plant_own_skill(copied)
        assert self.MINE not in plan_rows(plan(runner))

    def test_a_skill_lore_never_shipped_is_never_read(
        self, runner, copied, aliases, legacy_table, hashed_paths
    ):
        legacy_table(self.historical(copied, aliases))
        mine = self.plant_own_skill(copied)
        plan(runner)
        assert mine not in hashed_paths

    # -- an edited copy goes with the rest ----------------------------------

    def test_an_edited_copy_is_removed_too(
        self, runner, copied, aliases, legacy_table
    ):
        """The other two aliases still match, so the tree is provably Lore's."""
        legacy_table(self.historical(copied, aliases))
        edited = f"{CLAUDE_SKILLS}/{aliases['update-doctrine']}/SKILL.md"
        edit(copied, edited)

        init(runner, "--yes")

        assert not (copied / edited).exists()

    def test_an_edited_copy_is_reported_with_its_successor(
        self, runner, copied, aliases, legacy_table
    ):
        legacy_table(self.historical(copied, aliases))
        alias = aliases["update-doctrine"]
        edited = f"{CLAUDE_SKILLS}/{alias}/SKILL.md"
        edit(copied, edited)

        reported = removals(init(runner, "--yes").output)

        assert_names_the_retirement(reported.get(edited), alias)
        assert reconcile.EDIT_DISCARDED in reported[edited]

    # -- both trees are cleaned in one run ----------------------------------

    def test_both_trees_are_cleaned_in_one_run(
        self, runner, both_trees, aliases, legacy_table
    ):
        legacy_table(self.historical(both_trees, aliases))

        init(runner, "--yes")

        assert not [
            root
            for root in (CLAUDE_SKILLS, LORE_SKILLS)
            for alias in aliases.values()
            if (both_trees / root / alias).exists()
        ]

    def test_both_trees_report_their_removals(
        self, runner, both_trees, aliases, legacy_table
    ):
        legacy_table(self.historical(both_trees, aliases))
        reported = set(removals(init(runner, "--yes").output))
        assert {
            shown(f"{root}/{alias}/SKILL.md")
            for root in (CLAUDE_SKILLS, LORE_SKILLS)
            for alias in aliases.values()
        } <= reported

    # -- and it settles ------------------------------------------------------

    def test_the_second_run_plans_no_change(
        self, runner, copied, aliases, legacy_table
    ):
        legacy_table(self.historical(copied, aliases))
        init(runner, "--yes")
        legacy_table({})
        assert plan_counts(plan(runner)) == dict.fromkeys(COUNT_BUCKETS, 0)

    def test_the_second_run_leaves_the_tree_byte_identical(
        self, runner, copied, aliases, legacy_table
    ):
        legacy_table(self.historical(copied, aliases))
        self.plant_own_skill(copied)
        init(runner, "--yes")
        before = tree(copied, CLAUDE_SKILLS)

        init(runner, "--yes")

        assert tree(copied, CLAUDE_SKILLS) == before


# ---------------------------------------------------------------------------
# Scenario 5 — running init twice in a row changes nothing
# ---------------------------------------------------------------------------


class TestIdempotency:
    """The second run has nothing to say, and nothing to do."""

    def test_the_second_run_plans_no_change(self, runner, installed):
        assert plan_counts(plan(runner)) == dict.fromkeys(COUNT_BUCKETS, 0)

    def test_the_second_run_lists_no_path(self, runner, installed):
        assert plan_rows(plan(runner)) == {}

    def test_the_second_run_writes_no_skill_file(self, runner, installed):
        result = init(runner, "--yes")
        assert not [path for path in written(result.output) if CLAUDE_SKILLS in path]

    def test_the_second_run_removes_nothing(self, runner, installed):
        assert removals(init(runner, "--yes").output) == {}

    def test_the_second_run_leaves_every_installed_file_byte_identical(
        self, runner, installed
    ):
        before = tree(installed, CLAUDE_SKILLS)
        init(runner, "--yes")
        assert tree(installed, CLAUDE_SKILLS) == before

    def test_the_second_run_leaves_the_instruction_file_byte_identical(
        self, runner, installed
    ):
        before = (installed / "CLAUDE.md").read_bytes()
        init(runner, "--yes")
        assert (installed / "CLAUDE.md").read_bytes() == before

    def test_the_second_run_records_the_same_files(self, runner, installed):
        before = read_manifest(installed)["files"]
        init(runner, "--yes")
        assert read_manifest(installed)["files"] == before

    def test_a_third_run_still_plans_no_change(self, runner, installed):
        init(runner, "--yes")
        assert plan_counts(plan(runner)) == dict.fromkeys(COUNT_BUCKETS, 0)

    def test_an_upgrade_is_idempotent_once_it_has_settled(self, runner, aged):
        init(runner, "--yes")
        before = tree(aged, CLAUDE_SKILLS)
        init(runner, "--yes")
        assert tree(aged, CLAUDE_SKILLS) == before


class TestAnInterruptedRun:
    """The manifest is written last, so an interrupted run recovers on the next.

    Simulated by restoring the manifest a completed run replaced: the files on
    disk are what this release writes, and the record still describes what the
    one before it wrote — the state an `lore init` killed mid-write leaves.

    Nothing about that state needs a decision from anyone. A file already
    holding this release's bytes is a write that would change nothing, so the
    recovering run neither performs it nor reports it; a file the interruption
    left the user's is still the conflict it always was.
    """

    @pytest.fixture()
    def interrupted(self, runner, installed):
        stale = read_manifest(installed)
        init(runner, "--access", "cli", "--yes")
        write_manifest(installed, stale)
        return installed

    def test_the_already_written_files_are_neither_rewritten_nor_flagged(
        self, runner, interrupted
    ):
        counts = plan_counts(plan(runner))
        assert counts["conflict"] == 0
        assert counts["overwrite"] == 0

    def test_a_file_edited_during_the_interruption_is_taken_back(
        self, runner, interrupted
    ):
        """The recovering run still notices; what it does about it is rewrite."""
        edited = interrupted / CLAUDE_SKILLS / "inquest" / "SKILL.md"
        pristine = edited.read_bytes()
        edited.write_text("# mine now\n", encoding="utf-8")

        assert plan_counts(plan(runner))["overwrite"] > 0

        init(runner, "--yes")

        assert edited.read_bytes() == pristine

    def test_nothing_on_disk_is_changed_by_the_recovering_run(
        self, runner, interrupted
    ):
        before = tree(interrupted, CLAUDE_SKILLS)
        init(runner, "--yes")
        assert tree(interrupted, CLAUDE_SKILLS) == before

    def test_the_run_after_that_reconciles_to_a_correct_state(
        self, runner, interrupted
    ):
        init(runner, "--yes")
        assert plan_counts(plan(runner)) == dict.fromkeys(COUNT_BUCKETS, 0)


# ---------------------------------------------------------------------------
# Scenario 6 — the access mode flips
# ---------------------------------------------------------------------------


class TestAccessModeFlip:
    """Rendered content changes, so an unmodified file is a clean overwrite."""

    def test_unmodified_skills_are_overwrites(self, runner, installed):
        assert plan_counts(plan(runner, "--access", "cli"))["overwrite"] > 0

    def test_no_unmodified_skill_is_a_conflict(self, runner, installed):
        assert plan_counts(plan(runner, "--access", "cli"))["conflict"] == 0

    def test_every_reported_skill_row_is_an_overwrite(self, runner, installed):
        rows = plan_rows(plan(runner, "--access", "cli"))
        actions = {
            action
            for path, (action, _) in rows.items()
            if path.startswith(CLAUDE_SKILLS)
        }
        assert actions == {"Overwrite"}

    def test_the_flip_changes_the_installed_bytes(self, runner, installed):
        before = tree(installed, CLAUDE_SKILLS)
        init(runner, "--access", "cli", "--yes")
        assert tree(installed, CLAUDE_SKILLS) != before

    def test_flipping_back_restores_the_original_bytes(self, runner, installed):
        before = tree(installed, CLAUDE_SKILLS)
        init(runner, "--access", "cli", "--yes")
        init(runner, "--access", "native", "--yes")
        assert tree(installed, CLAUDE_SKILLS) == before

    def test_the_flipped_project_settles_in_one_run(self, runner, installed):
        init(runner, "--access", "cli", "--yes")
        assert plan_counts(plan(runner)) == dict.fromkeys(COUNT_BUCKETS, 0)

    def test_an_edited_skill_raises_no_conflict_in_a_flip(self, runner, installed):
        edited = f"{CLAUDE_SKILLS}/inquest/SKILL.md"
        edit(installed, edited)

        rows = plan_rows(plan(runner, "--access", "cli"))

        assert not [path for path, (action, _) in rows.items() if action == "Conflict"]
        assert rows[edited][0] == "Overwrite"

    def test_the_edit_does_not_survive_the_flip(self, runner, installed):
        edited = f"{CLAUDE_SKILLS}/inquest/SKILL.md"
        expected = edit(installed, edited)
        init(runner, "--access", "cli", "--yes")
        assert (installed / edited).read_bytes() != expected

    def test_a_flip_and_an_upgrade_in_one_run_do_both(self, runner, aged):
        alias = retired_alias("update-doctrine")

        result = init(runner, "--access", "cli", "--yes")

        assert shown(f"{CLAUDE_SKILLS}/{alias}/SKILL.md") in removals(result.output)
        assert f"{CLAUDE_SKILLS}/update-doctrine/SKILL.md" in written(result.output)


# ---------------------------------------------------------------------------
# An instruction file whose markers the run cannot make sense of
# ---------------------------------------------------------------------------


STRAY_BLOCK = "\n<!-- lore:begin -->\nstray\n<!-- lore:end -->\n"


class TestAnInstructionFileWithMarkersLoreWillNotGuessAt:
    """A section write that cannot proceed is an error, never a traceback.

    Reconciliation reads only the first marked block, so a second pair reaches
    the write, which refuses to guess which one is Lore's. The message names
    the file and the repair, and `conceptual-workflows-error-handling` says a
    message for a person leaves as `Error: …` on stderr with exit 1.
    """

    @pytest.fixture()
    def doubled(self, runner, installed):
        target = installed / "CLAUDE.md"
        prose = target.read_text(encoding="utf-8")
        target.write_text(prose + STRAY_BLOCK, encoding="utf-8")
        return installed

    def run(self, runner, *args: str):
        from lore.cli import main

        return runner.invoke(main, ["init", *args])

    def test_the_run_exits_one(self, runner, doubled):
        assert self.run(runner, "--access", "cli", "--yes").exit_code == 1

    def test_the_failure_is_not_an_unhandled_exception(self, runner, doubled):
        result = self.run(runner, "--access", "cli", "--yes")
        assert isinstance(result.exception, SystemExit)

    def test_the_message_names_the_file(self, runner, doubled):
        result = self.run(runner, "--access", "cli", "--yes")
        assert "CLAUDE.md" in result.stderr

    def test_the_message_reaches_stderr_as_an_error(self, runner, doubled):
        result = self.run(runner, "--access", "cli", "--yes")
        assert result.stderr.startswith("Error: ")

    def test_the_file_is_left_alone(self, runner, doubled):
        expected = (doubled / "CLAUDE.md").read_bytes()
        self.run(runner, "--access", "cli", "--yes")
        assert (doubled / "CLAUDE.md").read_bytes() == expected

    def test_removing_the_extra_pair_lets_the_run_through(self, runner, doubled):
        target = doubled / "CLAUDE.md"
        target.write_text(
            target.read_text(encoding="utf-8").replace(STRAY_BLOCK, ""),
            encoding="utf-8",
        )
        assert self.run(runner, "--access", "cli", "--yes").exit_code == 0

    def test_the_manifest_still_describes_the_run_before_it(self, runner, doubled):
        before = read_manifest(doubled)["files"]
        self.run(runner, "--access", "cli", "--yes")
        assert read_manifest(doubled)["files"] == before

    def test_the_next_run_picks_up_the_write_this_one_never_reached(
        self, runner, doubled
    ):
        """The manifest is unwritten, so the block is still pending — and only it.

        The files this run did write already hold what the next one would put
        there, so they are no-ops rather than rows anybody has to answer for.
        """
        self.run(runner, "--access", "cli", "--yes")
        target = doubled / "CLAUDE.md"
        target.write_text(
            target.read_text(encoding="utf-8").replace(STRAY_BLOCK, ""),
            encoding="utf-8",
        )

        summary = plan(runner, "--access", "cli")

        assert plan_rows(summary)["CLAUDE.md"][0] == "Section"
        assert plan_counts(summary)["conflict"] == 0

    def test_the_run_after_the_repair_leaves_nothing_outstanding(
        self, runner, doubled
    ):
        self.run(runner, "--access", "cli", "--yes")
        target = doubled / "CLAUDE.md"
        target.write_text(
            target.read_text(encoding="utf-8").replace(STRAY_BLOCK, ""),
            encoding="utf-8",
        )

        init(runner, "--access", "cli", "--yes")

        assert plan_counts(plan(runner, "--access", "cli")) == dict.fromkeys(
            COUNT_BUCKETS, 0
        )


# ---------------------------------------------------------------------------
# A conflicted path has to stay in the manifest, or the next run lies about it
# ---------------------------------------------------------------------------


class TestAConflictedPathStaysRecorded:
    """The record of what Lore installed does not expire after one conflict.

    A conflict is Lore declining to write, not Lore forgetting it ever wrote.
    Dropping the row made the run after next report `not installed by Lore`
    about a file Lore installed two runs earlier and whose markers it had
    written — a statement the file on disk contradicts.

    The rows that reach it are narrower than they were: an edited file Lore
    installed is now rewritten rather than reported, so what is left here is a
    recorded path Lore may no longer touch at all.
    """

    LINKED = f"{CLAUDE_SKILLS}/inquest/SKILL.md"

    @pytest.fixture()
    def linked(self, installed, tmp_path_factory):
        """A recorded path replaced by a link pointing out of the project."""
        outside = tmp_path_factory.mktemp("outside-the-project")
        (outside / "notes.md").write_text("my notes\n", encoding="utf-8")
        target = installed / self.LINKED
        target.unlink()
        target.symlink_to(outside / "notes.md")
        return installed

    def test_the_run_reports_it_and_touches_nothing(self, runner, linked):
        result = init(runner, "--yes")
        assert self.LINKED in kept(result.output)
        assert (linked / self.LINKED).is_symlink()

    def test_the_row_survives_the_run_that_reported_the_conflict(
        self, runner, linked
    ):
        init(runner, "--yes")
        assert self.LINKED in recorded_paths(linked)

    def test_it_keeps_the_hash_lore_wrote_rather_than_hashing_the_link(
        self, runner, linked
    ):
        before = {row["path"]: row for row in read_manifest(linked)["files"]}
        init(runner, "--yes")
        after = {row["path"]: row for row in read_manifest(linked)["files"]}
        assert after[self.LINKED] == before[self.LINKED]

    def test_the_third_run_still_knows_lore_installed_it(self, runner, linked):
        init(runner, "--yes")
        init(runner, "--yes")
        assert reconcile.NOT_INSTALLED_BY_LORE not in plan(runner)

    def test_a_file_lore_never_installed_is_still_not_claimed(self, runner, fresh):
        """FR-28 unchanged: only a path already recorded is carried forward."""
        relative = f"{CLAUDE_SKILLS}/inquest/SKILL.md"
        target = fresh / relative
        target.parent.mkdir(parents=True)
        target.write_bytes(b"mine, and Lore has never written here\n")

        init(runner, "--agent", "claude", "--skills", "all", "--yes")

        assert relative not in recorded_paths(fresh)
        assert target.read_bytes() == b"mine, and Lore has never written here\n"

    def test_replacing_the_link_with_the_file_re_adopts_the_path(
        self, runner, linked
    ):
        """The refusal is about what is at the path, so it expires with it."""
        init(runner, "--yes")
        target = linked / self.LINKED
        target.unlink()
        target.write_bytes(b"whatever was here\n")
        init(runner, "--yes")
        assert plan_counts(plan(runner))["conflict"] == 0
