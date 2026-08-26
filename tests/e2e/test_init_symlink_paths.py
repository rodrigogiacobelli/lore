"""E2E tests for `lore init` against a path that is a link rather than a file.

Adversarial smoke round 2 found two ways a write crossed the project boundary:

* a **dangling** symlink at a wanted path classified as a plain create, so
  `write_bytes` followed it and put 6757 bytes of skill text at an
  attacker-chosen path outside the project — reported as
  `Created .claude/skills/store-memory/SKILL.md`, exit 0;
* a **live** symlink to a file outside the project, which under
  `--on-conflict overwrite` truncated 18 bytes of the user's notes and replaced
  them with the same skill text, reported only as `Updated …`.

One mechanism, two outcomes: every target path was resolved lexically and
handed to a writer that follows links. The property under test here is the one
that was missing, stated once for every write site `lore init` has:

    Lore never writes or removes through a link, and every path it touches
    resolves inside the project root.

The tables are the *class* of hostile path — a link to a file, to a directory,
a dangling one, a looping one, one pointing inside the project and one
climbing out of it — not the two fixtures the smoke round happened to find.
A hard link is here too, at the end: it was recorded as unfixable, because no
stat can tell one from the file it is, and replacing rather than truncating
settles it anyway.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from lore.cli import main


# ---------------------------------------------------------------------------
# Planting a hostile path
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Planted:
    """A link put at a path `lore init` wants, and what must survive the run."""

    link: Path
    witness: Path | None = None
    """A path inside the project whose content the run must not change."""

    content: bytes | None = None
    """The witness's bytes, or None when it must stay absent."""


def live_link_outside(project: Path, link: Path) -> Planted:
    outside = project.parent / "outside" / "secret.md"
    outside.write_bytes(b"USER SECRET NOTES\n")
    link.symlink_to(outside)
    return Planted(link)


def dangling_link_outside(project: Path, link: Path) -> Planted:
    link.symlink_to(project.parent / "outside" / "PWNED.md")
    return Planted(link)


def live_link_inside(project: Path, link: Path) -> Planted:
    neighbour = project / "user-notes.md"
    neighbour.write_bytes(b"USER NOTES\n")
    link.symlink_to(neighbour)
    return Planted(link, witness=neighbour, content=b"USER NOTES\n")


def dangling_link_inside(project: Path, link: Path) -> Planted:
    neighbour = project / "never-created.md"
    link.symlink_to(neighbour)
    return Planted(link, witness=neighbour, content=None)


def link_to_a_directory(project: Path, link: Path) -> Planted:
    elsewhere = project.parent / "outdir"
    elsewhere.mkdir(parents=True, exist_ok=True)
    link.symlink_to(elsewhere)
    return Planted(link)


def symlink_loop(project: Path, link: Path) -> Planted:
    link.symlink_to(link.name)
    return Planted(link)


def relative_link_climbing_out(project: Path, link: Path) -> Planted:
    depth = len(link.relative_to(project).parts)
    link.symlink_to(Path(*[".."] * depth) / "outside" / "climbed.md")
    return Planted(link)


LINKS = {
    "a live link to a file outside the project": live_link_outside,
    "a dangling link pointing outside the project": dangling_link_outside,
    "a live link to a file inside the project": live_link_inside,
    "a dangling link pointing inside the project": dangling_link_inside,
    "a link to a directory": link_to_a_directory,
    "a symlink loop": symlink_loop,
    "a relative link climbing out of the project": relative_link_climbing_out,
}


RECONCILED_SITES = (
    ".claude/skills/store-memory/SKILL.md",
    ".claude/skills/.gitignore",
    ".lore/LORE-AGENT.md",
    "CLAUDE.md",
)
"""One path per reconciliation write site: an installed skill, the skills
listing, the rendered doc, and the marked block inside a project file.

The root `.gitignore` was the second marked block and is no longer written by
any release, so a link at that path is a file no run reads or writes."""

SEEDED_SITES = (
    ".lore/config.toml",
    ".lore/codex/codex.md",
    ".lore/codex/glossary.yaml",
    ".lore/.gitignore",
    ".lore/GETTING-STARTED.md",
    ".lore/artifacts/default/rites/rite-main.md",
    ".lore/lore.db",
    ".lore/.install-manifest.json",
)
"""One path per `.lore/` write site: the seeded skeletons, the copied default
trees, the database and the manifest. None of these is reconciled."""

ALL_SITES = RECONCILED_SITES + SEEDED_SITES

WRITE_LINES = {
    ".claude/skills/store-memory/SKILL.md": (
        "Created .claude/skills/store-memory/SKILL.md"
    ),
    ".claude/skills/.gitignore": "Created .claude/skills/.gitignore",
    ".lore/LORE-AGENT.md": "Created LORE-AGENT.md",
    "CLAUDE.md": "Updated CLAUDE.md (Lore section)",
}
"""The line a successful write puts in the report for each reconciled site.

Spelled out rather than derived: the point of the test is that this exact
sentence — the one that reported a file landing outside the project — is not
printed, and deriving it from the same code that prints it would prove nothing.
"""


# ---------------------------------------------------------------------------
# Running the CLI
# ---------------------------------------------------------------------------


INIT = {
    "--agent": "claude",
    "--skills": "all",
    "--access": "native",
    "--skills-gitignore": "lore-only",
    "--on-existing-agent-file": "append",
}
"""Every recorded answer as a flag, so no run depends on a prompt or a default."""


@pytest.fixture()
def project(tmp_path, monkeypatch) -> Path:
    """An empty project directory, with room beside it for a link to escape to.

    ``outside/`` exists and is empty, which is the state the smoke round's
    dangling-link reproduction ran in: the destination directory is there, only
    the file is missing, so a writer that follows the link succeeds.
    """
    root = tmp_path / "proj"
    root.mkdir()
    (tmp_path / "outside").mkdir()
    monkeypatch.chdir(root)
    return root


def run_init(runner, changes: dict[str, str] | None = None):
    """Run `lore init` with every answer flagged, *changes* overriding INIT.

    The flags are multi-value, so an override has to replace the answer rather
    than be appended after it.
    """
    answers = {**INIT, **(changes or {})}
    args = ["init"]
    for flag, value in answers.items():
        args += [flag, value]
    return runner.invoke(main, [*args, "--yes"])


def plant(project: Path, relative: str, build) -> Planted:
    link = project / relative
    link.parent.mkdir(parents=True, exist_ok=True)
    return build(project, link)


def snapshot(root: Path, skip: Path) -> dict[str, object]:
    """Every path under *root* except *skip*, without following a link."""
    seen: dict[str, object] = {}
    for path in sorted(root.rglob("*")):
        if path == skip or skip in path.parents:
            continue
        if path.is_symlink():
            seen[str(path)] = ("link", os.readlink(path))
        elif path.is_dir():
            seen[str(path)] = ("dir",)
        else:
            seen[str(path)] = ("file", path.read_bytes())
    return seen


def assert_untouched(result, planted: Planted) -> None:
    """The whole invariant, asserted the same way for every site and link."""
    assert "Traceback" not in result.stderr + result.stdout, result.output
    assert result.exit_code in (0, 1), result.output
    assert planted.link.is_symlink(), "Lore replaced the user's link"
    if planted.witness is None:
        return
    if planted.content is None:
        assert not planted.witness.exists(), "a write landed through the link"
    else:
        assert planted.witness.read_bytes() == planted.content


# ---------------------------------------------------------------------------
# Nothing crosses the project boundary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("build", list(LINKS.values()), ids=list(LINKS))
@pytest.mark.parametrize("relative", ALL_SITES)
class TestALinkAtAWantedPath:
    def test_nothing_outside_the_project_changes(self, runner, project, relative, build):
        planted = plant(project, relative, build)
        before = snapshot(project.parent, skip=project)

        result = run_init(runner)

        assert_untouched(result, planted)
        assert snapshot(project.parent, skip=project) == before

    def test_overwrite_does_not_reach_through_the_link_either(
        self, runner, project, relative, build
    ):
        planted = plant(project, relative, build)
        before = snapshot(project.parent, skip=project)

        result = run_init(runner, {"--on-conflict": "overwrite"})

        assert_untouched(result, planted)
        assert snapshot(project.parent, skip=project) == before


# ---------------------------------------------------------------------------
# What the run says about it
# ---------------------------------------------------------------------------


class TestTheRunReportsTheLink:
    @pytest.mark.parametrize("relative", RECONCILED_SITES)
    def test_a_reconciled_path_is_reported_as_a_conflict(
        self, runner, project, relative
    ):
        planted = plant(project, relative, dangling_link_outside)

        result = run_init(runner)

        assert result.exit_code == 0, result.output
        assert f"! Kept  {relative.removeprefix('.lore/')}" in result.stdout
        assert os.readlink(planted.link) in result.stdout

    @pytest.mark.parametrize(
        "relative, write_line", list(WRITE_LINES.items()), ids=list(WRITE_LINES)
    )
    def test_a_reconciled_path_is_never_reported_as_written(
        self, runner, project, relative, write_line
    ):
        """The defect's worst half was the report: a write that landed outside
        the project was announced as an ordinary create at the path inside it."""
        plant(project, relative, dangling_link_outside)

        result = run_init(runner)

        assert write_line not in result.stdout

    @pytest.mark.parametrize("relative", SEEDED_SITES)
    def test_a_seeded_path_stops_the_run_with_the_path_named(
        self, runner, project, relative
    ):
        planted = plant(project, relative, dangling_link_outside)

        result = run_init(runner)

        assert result.exit_code == 1, result.output
        assert "Traceback" not in result.stderr
        assert str(planted.link) in result.stderr


# ---------------------------------------------------------------------------
# The same links against a project this release already installed
# ---------------------------------------------------------------------------


@pytest.fixture()
def installed(runner, project) -> Path:
    result = run_init(runner)
    assert result.exit_code == 0, result.output
    return project


class TestALinkThatReplacesAnInstalledFile:
    @pytest.mark.parametrize("relative", RECONCILED_SITES)
    @pytest.mark.parametrize(
        "build",
        [live_link_outside, dangling_link_outside, symlink_loop],
        ids=["live outside", "dangling outside", "loop"],
    )
    def test_the_upgrade_refuses_to_write_through_it(
        self, runner, installed, relative, build
    ):
        (installed / relative).unlink()
        planted = plant(installed, relative, build)
        before = snapshot(installed.parent, skip=installed)

        result = run_init(
            runner, {"--access": "cli", "--on-conflict": "overwrite"}
        )

        assert_untouched(result, planted)
        assert snapshot(installed.parent, skip=installed) == before

    @pytest.mark.parametrize("relative", RECONCILED_SITES)
    def test_a_teardown_never_removes_through_it(self, runner, installed, relative):
        (installed / relative).unlink()
        planted = plant(installed, relative, live_link_outside)
        before = snapshot(installed.parent, skip=installed)

        result = run_init(runner, {"--skills": "none", "--agent": "none"})

        assert_untouched(result, planted)
        assert snapshot(installed.parent, skip=installed) == before


# ---------------------------------------------------------------------------
# The other kind of link
# ---------------------------------------------------------------------------


class TestAHardlinkAtAWantedPath:
    """A hard link *is* the file — no stat can tell Lore otherwise, which is
    why the smoke round recorded this one as unfixable. Replacing rather than
    truncating settles it anyway: the new bytes land on a new inode, and the
    user's other name for the old one keeps every byte."""

    def test_overwrite_no_longer_reaches_the_other_name(self, runner, project):
        outside = project.parent / "outside" / "notes.md"
        outside.write_bytes(b"USER NOTES\n")
        wanted = project / ".claude" / "skills" / "store-memory" / "SKILL.md"
        wanted.parent.mkdir(parents=True)
        os.link(outside, wanted)

        result = run_init(runner, {"--on-conflict": "overwrite"})

        assert result.exit_code == 0, result.output
        assert outside.read_bytes() == b"USER NOTES\n"
        assert wanted.read_bytes() != b"USER NOTES\n"


# ---------------------------------------------------------------------------
# The removal pass — one unprunable directory must not orphan the rest
# ---------------------------------------------------------------------------


class TestASymlinkedSkillDirectory:
    """`prune_empty_dirs` tested `is_dir()`, which follows links, then called
    `rmdir()`, which does not — and the prune loop was one unguarded pass, so
    the `NotADirectoryError` abandoned every remaining prune."""

    @pytest.fixture()
    def linked_skill_dir(self, runner, project) -> Path:
        real = project / "shared-skill"
        real.mkdir()
        skills_root = project / ".claude" / "skills"
        skills_root.mkdir(parents=True)
        (skills_root / "inquest").symlink_to(real)
        result = run_init(runner)
        assert result.exit_code == 0, result.output
        return project

    def test_the_teardown_finishes_without_a_traceback(self, runner, linked_skill_dir):
        result = run_init(runner, {"--skills": "none"})

        assert "Traceback" not in result.stderr + result.stdout, result.output
        assert result.exit_code == 0, result.output

    def test_every_other_empty_skill_directory_is_still_pruned(
        self, runner, linked_skill_dir
    ):
        run_init(runner, {"--skills": "none"})

        skills_root = linked_skill_dir / ".claude" / "skills"
        left = sorted(
            path.name
            for path in skills_root.iterdir()
            if path.is_dir() and not path.is_symlink()
        )
        assert left == [], f"orphaned directories: {left}"

    def test_the_link_itself_is_left_alone(self, runner, linked_skill_dir):
        run_init(runner, {"--skills": "none"})

        assert (linked_skill_dir / ".claude" / "skills" / "inquest").is_symlink()


# ---------------------------------------------------------------------------
# A skills root, or `.lore/` itself, that is a link out of the project
# ---------------------------------------------------------------------------
#
# Round 7, X1 and X5 — the two ends of one question.
#
# `.claude/skills` symlinked to a shared tree outside the project is a real
# workflow, and round 2 recorded it as working as designed. Containment refuses
# it, and the ruling is that containment wins: a link at that path is not
# distinguishable from one Lore was tricked into following. A repository can
# *carry* a symlink, so "the user chose where their skills live" is a claim
# about the person running `lore init`, not about the tree it runs on, and
# honouring it would let a clone decide where a later run writes.
#
# What was wrong was the shape of the refusal, not the refusal. Fourteen
# identical `! Kept` rows on exit 0 left the project with no skills, no manifest
# rows, and `lore health` passing — a CI job that runs `lore init && lore health`
# was green with nothing installed. And `.lore/` linked outside named
# `.lore/.gitignore`, the first file under the link, rather than the link.
#
# So: one refusal, naming the directory that causes it, before anything is
# written, exit 1.


LINKED_ROOTS = {
    ".claude/skills": ".claude/skills",
    ".lore": ".lore",
}


def link_root_outside(project: Path, relative: str) -> Path:
    """Point *relative* at a directory beside the project and return the target."""
    outside = project.parent / "shared"
    outside.mkdir(exist_ok=True)
    link = project / relative
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside)
    return outside


@pytest.mark.parametrize("relative", list(LINKED_ROOTS), ids=list(LINKED_ROOTS))
class TestADirectoryLoreInstallsIntoThatLeavesTheProject:
    def test_the_run_stops(self, runner, project, relative):
        link_root_outside(project, relative)

        result = run_init(runner)

        assert result.exit_code == 1, result.output

    def test_nothing_is_written_outside_the_project(self, runner, project, relative):
        outside = link_root_outside(project, relative)

        run_init(runner)

        assert list(outside.iterdir()) == []

    def test_the_message_names_the_directory_that_causes_it(
        self, runner, project, relative
    ):
        link_root_outside(project, relative)

        result = run_init(runner)

        assert relative in result.output

    def test_the_message_does_not_name_a_file_under_the_link(
        self, runner, project, relative
    ):
        """X5: the first file under the link is a symptom, not the cause."""
        link_root_outside(project, relative)

        result = run_init(runner)

        assert f"{relative}/.gitignore" not in result.output

    def test_the_message_says_why(self, runner, project, relative):
        link_root_outside(project, relative)

        result = run_init(runner)

        assert "outside the project root" in result.output

    def test_the_message_offers_a_way_forward(self, runner, project, relative):
        link_root_outside(project, relative)

        result = run_init(runner)

        assert "link to it from" in result.output

    def test_it_is_one_refusal_and_not_a_row_per_file(self, runner, project, relative):
        link_root_outside(project, relative)

        result = run_init(runner)

        assert result.output.count("outside the project root") == 1, result.output

    def test_no_traceback_reaches_the_terminal(self, runner, project, relative):
        link_root_outside(project, relative)

        result = run_init(runner)

        assert "Traceback" not in result.output + result.stderr

    def test_the_link_itself_is_left_alone(self, runner, project, relative):
        link_root_outside(project, relative)

        run_init(runner)

        assert (project / relative).is_symlink()


@pytest.mark.parametrize("relative", list(LINKED_ROOTS), ids=list(LINKED_ROOTS))
class TestTheSameLinkPointingInsideStillWorks:
    """The rule is about the project boundary, not about links."""

    def test_the_run_succeeds_and_installs_under_the_target(
        self, runner, project, relative
    ):
        inside = project / "shared-tree"
        inside.mkdir()
        link = project / relative
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(inside)

        result = run_init(runner)

        assert result.exit_code == 0, result.output
        assert any(inside.rglob("*"))


class TestAHealthCheckCannotPassWithNothingInstalled:
    """The aggravating half of X1: `lore init && lore health` was green with an
    empty skills tree, because the manifest had no rows for health to walk."""

    def test_init_fails_before_health_can_be_asked(self, runner, project):
        link_root_outside(project, ".claude/skills")

        result = run_init(runner)

        assert result.exit_code == 1
        assert not (project / ".lore" / ".install-manifest.json").is_file()
