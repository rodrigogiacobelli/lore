"""E2E tests for the root `.gitignore` block Lore no longer writes, and removes.

Spec: conceptual-workflows-lore-init (lore codex show conceptual-workflows-lore-init)

Lore used to write a marked block into the project's own root `.gitignore`
naming its generated artefacts — the database and its two siblings,
`.lore/reports/`, the install manifest. Every one of those paths is already
ignored by the `*` that opens `.lore/.gitignore`, so not one line of the block
ever decided anything: deleting the whole block from a real project leaves
`git check-ignore -v` reporting the identical deciding rule for every path.
It was a write into a file the user owns in exchange for nothing.

So the block is retired, and retiring it has two halves. This release writes no
root `.gitignore` at all — the fresh half. And every project initialised before
this one still carries the block, sitting inside markers Lore itself wrote, so
it is unambiguously Lore's to take back — the upgrade half, which is the one
these tests are mostly about:

* a `.gitignore` of the user's, carrying Lore's block, keeps every byte outside
  the markers and loses the block;
* a `.gitignore` holding nothing but the block is a file Lore created and
  nothing of the user's remains in, so it goes;
* a `.gitignore` carrying no markers, or none at all, is not Lore's business
  and is never read, written or created.

The pre-change project is constructed rather than installed — no previously
released wheel is available to a test run — by writing the block Lore used to
render and the manifest row it used to record. Both are historical bytes and
are spelled out here for that reason: what an upgrade has to clean up is what
old releases actually left, not what this one would render.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from lore import init as init_module
from lore import manifest


# ---------------------------------------------------------------------------
# What a release before this one wrote
# ---------------------------------------------------------------------------


LEGACY_BEGIN = (
    "# lore:begin — managed by `lore init`; edits between these markers are replaced"
)
LEGACY_END = "# lore:end"
"""The marker pair old releases wrote into the root `.gitignore`.

Spelled out rather than imported: these are the bytes sitting in projects on
disk today, and an upgrade that cleaned up only what the current constant says
would strand every project whose markers were written before it changed.
"""

LEGACY_BLOCK_BODY = (
    ".lore/lore.db\n"
    ".lore/lore.db-wal\n"
    ".lore/lore.db-shm\n"
    ".lore/reports/\n"
    ".lore/.install-manifest.json\n"
)
"""The five lines the retired block named, between the markers."""

LEGACY_BLOCK = f"{LEGACY_BEGIN}\n{LEGACY_BLOCK_BODY}{LEGACY_END}\n"

ROOT_GITIGNORE = ".gitignore"
LEGACY_SOURCE = "root-gitignore"


# ---------------------------------------------------------------------------
# Running the CLI
# ---------------------------------------------------------------------------


def init(runner: CliRunner, *args: str):
    """Run `lore init` with *args* and assert it succeeded."""
    from lore.cli import main

    result = runner.invoke(main, ["init", *args])
    assert result.exit_code == 0, result.output
    return result


def manifest_path(project_dir: Path) -> Path:
    return project_dir / ".lore" / ".install-manifest.json"


def read_manifest(project_dir: Path) -> dict:
    return json.loads(manifest_path(project_dir).read_text(encoding="utf-8"))


def recorded_paths(project_dir: Path) -> set[str]:
    return {row["path"] for row in read_manifest(project_dir)["files"]}


def age_to_carry_the_block(project_dir: Path, user_lines: str = "") -> Path:
    """Put a project into the state a release before this one left it in.

    *user_lines* is whatever the project itself had in its `.gitignore` before
    Lore ever ran; the block is appended after it, which is where
    ``write_marked_section`` used to put it. The manifest gains the row that
    release recorded, hashing the block body alone — a ``section`` entry covers
    only the text between the markers.
    """
    gitignore = project_dir / ROOT_GITIGNORE
    gitignore.write_text(user_lines + LEGACY_BLOCK, encoding="utf-8")

    payload = read_manifest(project_dir)
    payload["files"].append(
        {
            "path": ROOT_GITIGNORE,
            "kind": "section",
            "source": LEGACY_SOURCE,
            "hash": manifest.bytes_digest(LEGACY_BLOCK_BODY.encode("utf-8")),
        }
    )
    payload["files"].sort(key=lambda row: row["path"])
    manifest_path(project_dir).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    return gitignore


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
    """A project this release installed for Claude Code."""
    init(runner, "--agent", "claude", "--skills", "memory", "--yes")
    return fresh


# ---------------------------------------------------------------------------
# This release writes no root `.gitignore`
# ---------------------------------------------------------------------------


class TestNoRunWritesTheRootGitignore:
    """The fresh half: a project Lore initialises today gains no root block."""

    def test_a_fresh_init_creates_no_root_gitignore(self, installed):
        assert not (installed / ROOT_GITIGNORE).exists()

    def test_no_plan_row_names_it(self, runner, fresh):
        from lore.init import plan_init

        plan = plan_init(project_root=fresh, agents=["claude"])
        assert ROOT_GITIGNORE not in {entry.path for entry in plan.files}

    def test_the_manifest_records_no_root_gitignore(self, installed):
        assert ROOT_GITIGNORE not in recorded_paths(installed)

    def test_the_only_paths_outside_dot_lore_are_the_agents_own(self, installed):
        outside = {
            path for path in recorded_paths(installed) if not path.startswith(".lore/")
        }
        assert outside
        assert ROOT_GITIGNORE not in outside
        for path in outside:
            assert path == "CLAUDE.md" or path.startswith(".claude/skills/")

    def test_a_user_gitignore_is_left_byte_identical(self, runner, fresh):
        theirs = fresh / ROOT_GITIGNORE
        original = "node_modules/\n*.log\n"
        theirs.write_text(original, encoding="utf-8")
        init(runner, "--agent", "claude", "--skills", "memory", "--yes")
        assert theirs.read_text(encoding="utf-8") == original

    def test_the_flag_that_asked_about_it_is_gone(self, runner):
        from lore.cli import main

        result = runner.invoke(main, ["init", "--help"])
        assert "--gitignore" not in result.output
        assert "--no-gitignore" not in result.output

    def test_plan_init_takes_no_root_gitignore_keyword(self, fresh):
        from lore.init import plan_init

        with pytest.raises(TypeError):
            plan_init(project_root=fresh, root_gitignore=True)

    def test_the_answers_carry_no_root_gitignore(self, fresh):
        from lore.init import plan_init

        assert not hasattr(plan_init(project_root=fresh).answers, "root_gitignore")

    def test_the_prompt_that_asked_about_it_is_gone(self):
        from lore import prompts

        assert not hasattr(prompts, "ask_root_gitignore")


# ---------------------------------------------------------------------------
# An existing project's block is taken back
# ---------------------------------------------------------------------------


class TestAnExistingProjectsBlockIsRemoved:
    """The upgrade half: Lore removes what Lore wrote, and nothing else."""

    USER_LINES = "node_modules/\n*.log\n\n# my own section\ndist/\n"

    def test_the_block_is_gone(self, runner, installed):
        gitignore = age_to_carry_the_block(installed, self.USER_LINES)
        init(runner, "--agent", "claude", "--skills", "memory", "--yes")
        text = gitignore.read_text(encoding="utf-8")
        assert LEGACY_BEGIN not in text
        assert LEGACY_END not in text
        assert ".lore/lore.db" not in text

    def test_every_line_outside_the_markers_survives(self, runner, installed):
        gitignore = age_to_carry_the_block(installed, self.USER_LINES)
        init(runner, "--agent", "claude", "--skills", "memory", "--yes")
        assert gitignore.read_text(encoding="utf-8") == self.USER_LINES

    def test_content_after_the_block_survives_too(self, runner, installed):
        """A project that added lines below the block keeps them where they were."""
        gitignore = installed / ROOT_GITIGNORE
        age_to_carry_the_block(installed, self.USER_LINES)
        trailing = "# added after Lore ran\ncoverage/\n"
        gitignore.write_text(
            gitignore.read_text(encoding="utf-8") + trailing, encoding="utf-8"
        )
        init(runner, "--agent", "claude", "--skills", "memory", "--yes")
        assert gitignore.read_text(encoding="utf-8") == self.USER_LINES + trailing

    def test_the_run_reports_the_removal(self, runner, installed):
        age_to_carry_the_block(installed, self.USER_LINES)
        output = init(runner, "--agent", "claude", "--skills", "memory", "--yes").output
        assert ROOT_GITIGNORE in output

    def test_the_path_leaves_the_manifest(self, runner, installed):
        age_to_carry_the_block(installed, self.USER_LINES)
        init(runner, "--agent", "claude", "--skills", "memory", "--yes")
        assert ROOT_GITIGNORE not in recorded_paths(installed)

    def test_a_second_run_touches_the_file_no_further(self, runner, installed):
        gitignore = age_to_carry_the_block(installed, self.USER_LINES)
        init(runner, "--agent", "claude", "--skills", "memory", "--yes")
        after_first = gitignore.read_bytes()
        init(runner, "--agent", "claude", "--skills", "memory", "--yes")
        assert gitignore.read_bytes() == after_first

    def test_an_edited_block_goes_the_same_way(self, runner, installed):
        """Lore owns what it wrote, so an edit inside the markers buys nothing."""
        gitignore = age_to_carry_the_block(installed, self.USER_LINES)
        gitignore.write_text(
            gitignore.read_text(encoding="utf-8").replace(
                ".lore/reports/", ".lore/reports/\n.lore/scratch/"
            ),
            encoding="utf-8",
        )
        init(runner, "--agent", "claude", "--skills", "memory", "--yes")
        assert gitignore.read_text(encoding="utf-8") == self.USER_LINES


class TestAGitignoreLoreCreatedIsRemovedEntirely:
    """Lore created the file, and nothing of the project's is left in it."""

    def test_a_file_holding_nothing_but_the_block_goes(self, runner, installed):
        gitignore = age_to_carry_the_block(installed)
        assert gitignore.is_file()
        init(runner, "--agent", "claude", "--skills", "memory", "--yes")
        assert not gitignore.exists()

    def test_whitespace_left_behind_does_not_keep_it_alive(self, runner, installed):
        gitignore = age_to_carry_the_block(installed, "\n\n   \n")
        init(runner, "--agent", "claude", "--skills", "memory", "--yes")
        assert not gitignore.exists()

    def test_one_line_of_their_own_keeps_it(self, runner, installed):
        gitignore = age_to_carry_the_block(installed, "dist/\n")
        init(runner, "--agent", "claude", "--skills", "memory", "--yes")
        assert gitignore.read_text(encoding="utf-8") == "dist/\n"


class TestAFileLoreNeverWroteIsUntouched:
    """No markers, or no file: Lore has nothing to take back and takes nothing."""

    def test_an_unmarked_gitignore_is_byte_identical(self, runner, installed):
        gitignore = installed / ROOT_GITIGNORE
        original = "node_modules/\n.lore/lore.db\n"
        gitignore.write_text(original, encoding="utf-8")
        init(runner, "--agent", "claude", "--skills", "memory", "--yes")
        assert gitignore.read_text(encoding="utf-8") == original

    def test_an_absent_gitignore_is_not_created(self, runner, installed):
        init(runner, "--agent", "claude", "--skills", "memory", "--yes")
        assert not (installed / ROOT_GITIGNORE).exists()

    def test_a_recorded_path_whose_block_is_already_gone_says_nothing(
        self, runner, installed
    ):
        """The project deleted the block itself. There is nothing left to report."""
        gitignore = age_to_carry_the_block(installed, "dist/\n")
        gitignore.write_text("dist/\n", encoding="utf-8")
        output = init(runner, "--agent", "claude", "--skills", "memory", "--yes").output
        assert gitignore.read_text(encoding="utf-8") == "dist/\n"
        assert "Removed .gitignore" not in output


class TestTheMarkersStillMatchWhatOldReleasesWrote:
    """The upgrade can only find the block if it still knows the marker pair."""

    def test_the_shipped_pair_is_the_pair_on_disk(self):
        assert init_module.GITIGNORE_MARKERS == (LEGACY_BEGIN, LEGACY_END)

    def test_the_root_gitignore_stays_a_path_lore_may_remove_from(self):
        """A manifest recording it has to keep parsing, or the record is lost.

        ``manifest._parse`` rejects the whole file when a row names a path this
        release does not own — and every project carrying the block has exactly
        such a row. Dropping `.gitignore` from the ownable set would fall the
        upgrade back to the legacy hashes, which know nothing about it, and the
        block would sit there for good.
        """
        assert manifest.unownable_reason(ROOT_GITIGNORE) is None


# ---------------------------------------------------------------------------
# The two hostile-file failures that existed only because Lore wrote here
# ---------------------------------------------------------------------------


class TestTheHostileGitignoreFailuresAreGone:
    """Round 6 F7 and F9. Neither is fixed; both stop being reachable."""

    def test_a_directory_at_the_path_no_longer_stops_the_run(self, runner, fresh):
        """F7 — the run used to refuse, because `.gitignore` was a path it wrote."""
        (fresh / ROOT_GITIGNORE).mkdir()
        init(runner, "--agent", "claude", "--skills", "memory", "--yes")
        assert manifest_path(fresh).is_file()
        assert (fresh / "CLAUDE.md").is_file()
        assert (fresh / ROOT_GITIGNORE).is_dir()

    def test_a_read_only_gitignore_is_not_rewritten(self, runner, fresh):
        """F9 — a file mode said no and the write went through anyway."""
        gitignore = fresh / ROOT_GITIGNORE
        original = "node_modules/\n"
        gitignore.write_text(original, encoding="utf-8")
        gitignore.chmod(0o444)
        try:
            init(runner, "--agent", "claude", "--skills", "memory", "--yes")
            assert gitignore.read_text(encoding="utf-8") == original
            assert gitignore.stat().st_mode & 0o777 == 0o444
        finally:
            gitignore.chmod(0o644)


# ---------------------------------------------------------------------------
# The baseline projects — every shape an upgrade meets
# ---------------------------------------------------------------------------


BASELINES = {
    # id: (agents, skills-gitignore answer, what the root `.gitignore` held)
    "p010": ("claude", "lore-only", None),
    "p020": ("claude", "lore-only", ""),
    "p030": ("claude", "lore-only", "node_modules/\n"),
    "p040": ("claude", "all", "*.log\n\n# theirs\nbuild/\n"),
    "p050": ("claude", "none", "\n \n"),
    "p060": ("agents-md", "lore-only", "dist/\n"),
    "p070": ("agents-md", "all", None),
    "p080": ("none", "lore-only", "coverage/\n"),
    "p090": ("none", "none", ""),
}
"""One project per shape an upgrade can meet, across both install roots.

``None`` means the project had no root `.gitignore` before Lore ever ran, so
the file the upgrade meets is one Lore created outright; a string is whatever
the project itself had, which every one of these has to keep byte-for-byte.
"""


@pytest.mark.parametrize("baseline", sorted(BASELINES))
def test_every_baseline_upgrades_to_a_clean_root_gitignore(
    runner, fresh, baseline
):
    agent, tracking, before = BASELINES[baseline]
    init(runner, "--agent", agent, "--skills-gitignore", tracking, "--skills", "memory", "--yes")
    gitignore = age_to_carry_the_block(fresh, before or "")

    init(runner, "--agent", agent, "--skills-gitignore", tracking, "--skills", "memory", "--yes")

    if before is None or not before.strip():
        assert not gitignore.exists(), baseline
    else:
        assert gitignore.read_text(encoding="utf-8") == before, baseline
    assert ROOT_GITIGNORE not in recorded_paths(fresh), baseline


# ---------------------------------------------------------------------------
# The evidence the removal rests on, asked of git itself
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    shutil.which("git") is None, reason="this test asks git, so it needs git"
)
def test_nothing_lore_generates_needs_a_root_level_rule(runner, fresh):
    """The whole case: `.lore/.gitignore` already covers every generated path.

    Not a re-reading of the ignore files but git's own verdict — the paths Lore
    generates and never commits are ignored with no root `.gitignore` present
    at all, and the files that are meant to reach a teammate still do.
    """
    subprocess.run(["git", "init", "-q", "."], cwd=fresh, check=True)
    init(runner, "--agent", "claude", "--skills", "memory", "--yes")
    assert not (fresh / ROOT_GITIGNORE).exists()

    generated = (
        ".lore/lore.db",
        ".lore/lore.db-wal",
        ".lore/lore.db-shm",
        ".lore/reports/report.md",
        ".lore/.install-manifest.json",
    )
    for path in generated:
        assert (
            subprocess.run(
                ["git", "check-ignore", "-q", "--no-index", path], cwd=fresh
            ).returncode
            == 0
        ), f"{path} is not ignored without a root .gitignore"

    for path in ("CLAUDE.md", ".claude/skills/.gitignore", ".lore/config.toml"):
        assert (
            subprocess.run(
                ["git", "check-ignore", "-q", "--no-index", path], cwd=fresh
            ).returncode
            == 1
        ), f"{path} should still reach a teammate"
