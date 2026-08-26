"""Unit tests for lore.safewrite — the gate every `lore init` write passes.

Adversarial smoke round 2 found `lore init` creating a 6757-byte file **outside
the project** through a dangling symlink, reporting it as a normal create and
exiting 0; and `--on-conflict overwrite` truncating an existing outside file by
the same route. Both were one missing property rather than two bugs: a target
path was resolved lexically and handed to ``Path.write_bytes``, which follows
links.

The same round found two concurrent runs eating 1121 lines of a user's
`CLAUDE.md`, because the marked-section writer was a read-modify-write whose
final ``write_text`` truncated the file in place.

This module is where all three answers live:

* **never through a link** — a symlink at a path Lore wants is a user-owned
  object, whatever it points at;
* **never outside the project root** — resolved, so no chain of links can
  smuggle a write past a lexical containment check;
* **never a torn file** — a write lands whole or not at all.

The tables below are the *class* of hostile path, not the two fixtures the
smoke round happened to find.
"""

from __future__ import annotations

import os
import stat
import threading
from pathlib import Path

import pytest

from lore import safewrite


# ---------------------------------------------------------------------------
# The class of hostile path
# ---------------------------------------------------------------------------


def link_to_a_file_outside(root: Path, target: Path) -> None:
    outside = root.parent / "outside" / "secret.md"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_text("USER SECRET NOTES\n")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(outside)


def link_to_a_file_inside(root: Path, target: Path) -> None:
    neighbour = root / "notes.md"
    neighbour.write_text("mine\n")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(neighbour)


def dangling_link_pointing_outside(root: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(root.parent / "outside" / "PWNED.md")


def dangling_link_pointing_inside(root: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(root / "never-created.md")


def link_to_a_directory(root: Path, target: Path) -> None:
    elsewhere = root.parent / "outdir"
    elsewhere.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(elsewhere)


def a_symlink_loop(root: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(target.name)


def a_relative_link_climbing_out(root: Path, target: Path) -> None:
    escape = Path(*[".."] * (len(target.relative_to(root).parts) + 1)) / "escaped.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(escape)


LINKS = {
    "a live link to a file outside the project": link_to_a_file_outside,
    "a live link to a file inside the project": link_to_a_file_inside,
    "a dangling link pointing outside the project": dangling_link_pointing_outside,
    "a dangling link pointing inside the project": dangling_link_pointing_inside,
    "a link to a directory": link_to_a_directory,
    "a symlink loop": a_symlink_loop,
    "a relative link climbing out of the project": a_relative_link_climbing_out,
}
"""Every shape a symlink can take at a path Lore wants to write."""


@pytest.fixture()
def project(tmp_path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    return root


@pytest.mark.parametrize("build", list(LINKS.values()), ids=list(LINKS))
class TestNeverThroughALink:
    def test_a_link_at_a_wanted_path_is_refused(self, project, build):
        target = project / ".claude" / "skills" / "store-memory" / "SKILL.md"
        build(project, target)

        reason = safewrite.unsafe_reason(target, project_root=project)

        assert reason is not None
        assert safewrite.THROUGH_A_LINK in reason

    def test_the_refusal_names_what_the_link_points_at(self, project, build):
        target = project / ".claude" / "skills" / "store-memory" / "SKILL.md"
        build(project, target)

        reason = safewrite.unsafe_reason(target, project_root=project)

        assert os.readlink(target) in reason

    def test_a_write_through_the_link_raises_rather_than_lands(self, project, build):
        target = project / "CLAUDE.md"
        build(project, target)
        before = _snapshot(project.parent)

        with pytest.raises(ValueError) as caught:
            safewrite.atomic_write_bytes(target, b"lore content\n", project_root=project)

        assert str(target) in str(caught.value)
        assert _snapshot(project.parent) == before

    def test_the_link_itself_survives_the_refusal(self, project, build):
        target = project / "CLAUDE.md"
        build(project, target)
        pointed_at = os.readlink(target)

        with pytest.raises(ValueError):
            safewrite.atomic_write_bytes(target, b"lore content\n", project_root=project)

        assert target.is_symlink()
        assert os.readlink(target) == pointed_at


# ---------------------------------------------------------------------------
# The project boundary
# ---------------------------------------------------------------------------


class TestNeverOutsideTheProjectRoot:
    def test_a_path_reached_through_a_linked_parent_directory_is_refused(self, project):
        elsewhere = project.parent / "outskills"
        elsewhere.mkdir()
        (project / ".claude").mkdir()
        (project / ".claude" / "skills").symlink_to(elsewhere)
        target = project / ".claude" / "skills" / "inquest" / "SKILL.md"

        reason = safewrite.unsafe_reason(target, project_root=project)

        assert reason is not None
        assert safewrite.OUTSIDE_THE_ROOT in reason

    def test_the_write_does_not_land_outside(self, project):
        elsewhere = project.parent / "outskills"
        elsewhere.mkdir()
        (project / ".claude").mkdir()
        (project / ".claude" / "skills").symlink_to(elsewhere)
        target = project / ".claude" / "skills" / "inquest" / "SKILL.md"

        with pytest.raises(ValueError):
            safewrite.atomic_write_bytes(target, b"skill\n", project_root=project)

        assert list(elsewhere.iterdir()) == []

    def test_a_lexically_escaping_path_is_refused(self, project):
        target = project / ".." / "outside.md"

        reason = safewrite.unsafe_reason(target, project_root=project)

        assert reason is not None
        assert safewrite.OUTSIDE_THE_ROOT in reason

    def test_a_project_root_reached_through_a_link_is_not_itself_an_escape(
        self, tmp_path
    ):
        """The root may live under a linked path — macOS `/tmp` is one — so both
        sides of the containment test are resolved before they are compared."""
        real = tmp_path / "real"
        real.mkdir()
        linked_root = tmp_path / "proj"
        linked_root.symlink_to(real)

        target = linked_root / ".lore" / "config.toml"

        assert safewrite.unsafe_reason(target, project_root=linked_root) is None

    def test_a_path_deep_inside_the_root_is_safe(self, project):
        target = project / ".lore" / "codex" / "vision" / "product.md"

        assert safewrite.unsafe_reason(target, project_root=project) is None


# ---------------------------------------------------------------------------
# Anything that is not a regular file
# ---------------------------------------------------------------------------


class TestOnlyARegularFileMayBeReplaced:
    def test_a_directory_is_refused_with_the_repair(self, project):
        target = project / ".lore" / "config.toml"
        target.mkdir(parents=True)

        reason = safewrite.unsafe_reason(target, project_root=project)

        assert reason is not None
        assert "a directory" in reason
        assert "move or remove it" in reason

    @pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX only")
    def test_a_fifo_is_refused_rather_than_opened(self, project):
        target = project / "CLAUDE.md"
        os.mkfifo(target)

        reason = safewrite.unsafe_reason(target, project_root=project)

        assert reason is not None
        assert "not a regular file" in reason

    def test_an_absent_path_is_safe(self, project):
        assert safewrite.unsafe_reason(project / "CLAUDE.md", project_root=project) is None

    def test_an_ordinary_file_is_safe(self, project):
        target = project / "CLAUDE.md"
        target.write_text("mine\n")

        assert safewrite.unsafe_reason(target, project_root=project) is None

    def test_refuse_unsafe_names_the_path(self, project):
        target = project / ".lore" / "config.toml"
        target.mkdir(parents=True)

        with pytest.raises(ValueError) as caught:
            safewrite.refuse_unsafe(target, project_root=project)

        assert str(target) in str(caught.value)


class TestADirectoryLoreCreates:
    """Weaker than the file rule on purpose: a directory that is a link is
    still a place, and every file written under it is checked on its own."""

    def test_a_link_to_a_directory_inside_the_project_is_allowed(self, project):
        real = project / "shared"
        real.mkdir()
        linked = project / ".lore"
        linked.symlink_to(real)

        safewrite.refuse_unsafe_directory(linked, project_root=project)

    def test_a_link_to_a_directory_outside_the_project_is_refused(self, project):
        elsewhere = project.parent / "shared"
        elsewhere.mkdir()
        linked = project / ".lore"
        linked.symlink_to(elsewhere)

        with pytest.raises(ValueError) as caught:
            safewrite.refuse_unsafe_directory(linked, project_root=project)

        assert safewrite.OUTSIDE_THE_ROOT in str(caught.value)

    def test_a_dangling_link_is_refused_rather_than_left_to_mkdir(self, project):
        linked = project / ".lore"
        linked.symlink_to(project / "never-created")

        with pytest.raises(ValueError) as caught:
            safewrite.refuse_unsafe_directory(linked, project_root=project)

        assert safewrite.THROUGH_A_LINK in str(caught.value)

    def test_a_file_where_the_directory_belongs_is_refused(self, project):
        target = project / ".lore"
        target.write_text("not a directory\n")

        with pytest.raises(ValueError) as caught:
            safewrite.refuse_unsafe_directory(target, project_root=project)

        assert "not a directory" in str(caught.value)

    def test_an_absent_directory_is_allowed(self, project):
        safewrite.refuse_unsafe_directory(project / ".lore", project_root=project)


# ---------------------------------------------------------------------------
# The write itself — whole or not at all
# ---------------------------------------------------------------------------


class TestTheWriteLandsWhole:
    def test_it_creates_the_file_and_its_parents(self, project):
        target = project / ".claude" / "skills" / "inquest" / "SKILL.md"

        safewrite.atomic_write_bytes(target, b"skill\n", project_root=project)

        assert target.read_bytes() == b"skill\n"

    def test_it_replaces_rather_than_truncates(self, project):
        target = project / "CLAUDE.md"
        target.write_text("old\n")
        before = target.stat().st_ino

        safewrite.atomic_write_text(target, "new\n", project_root=project)

        assert target.read_text() == "new\n"
        assert target.stat().st_ino != before

    def test_a_hardlinked_companion_keeps_its_content(self, project):
        """The proof that nothing is truncated in place: an in-place write
        changes the shared inode and takes every other name for it with it."""
        target = project / "CLAUDE.md"
        target.write_text("user content\n")
        companion = project / "companion.md"
        os.link(target, companion)

        safewrite.atomic_write_text(target, "lore content\n", project_root=project)

        assert companion.read_text() == "user content\n"

    def test_a_concurrent_reader_never_sees_a_partial_file(self, project):
        target = project / "CLAUDE.md"
        body = "padding line\n" * 40000
        target.write_text(body)
        torn: list[int] = []
        stop = threading.Event()

        def reader() -> None:
            while not stop.is_set():
                try:
                    seen = target.read_text()
                except OSError:  # pragma: no cover - the file always exists
                    continue
                if seen.count("padding line\n") != 40000:
                    torn.append(len(seen))

        watcher = threading.Thread(target=reader)
        watcher.start()
        try:
            for index in range(20):
                safewrite.atomic_write_text(
                    target, body + f"block {index}\n", project_root=project
                )
        finally:
            stop.set()
            watcher.join()

        assert torn == []

    def test_an_existing_file_keeps_its_permissions(self, project):
        target = project / "CLAUDE.md"
        target.write_text("old\n")
        target.chmod(0o444)

        safewrite.atomic_write_text(target, "new\n", project_root=project)

        assert stat.S_IMODE(target.stat().st_mode) == 0o444

    def test_it_leaves_no_temporary_file_behind(self, project):
        target = project / ".lore" / "config.toml"

        safewrite.atomic_write_text(target, "key = 1\n", project_root=project)

        assert [path.name for path in target.parent.iterdir()] == ["config.toml"]

    def test_a_refused_directory_leaves_no_temporary_file_behind(self, project):
        parent = project / ".claude" / "skills"
        parent.mkdir(parents=True)
        parent.chmod(0o555)
        try:
            with pytest.raises(ValueError):
                safewrite.atomic_write_text(
                    parent / "SKILL.md", "skill\n", project_root=project
                )
            assert list(parent.iterdir()) == []
        finally:
            parent.chmod(0o755)

    def test_a_filesystem_refusal_names_the_path_rather_than_escaping(self, project):
        parent = project / ".claude" / "skills"
        parent.mkdir(parents=True)
        parent.chmod(0o555)
        try:
            with pytest.raises(ValueError) as caught:
                safewrite.atomic_write_text(
                    parent / "SKILL.md", "skill\n", project_root=project
                )
        finally:
            parent.chmod(0o755)

        message = str(caught.value)
        assert str(parent / "SKILL.md") in message
        assert "re-run" in message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _snapshot(root: Path) -> dict[str, object]:
    """Every path under *root* with what it is, without following a link."""
    seen: dict[str, object] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            seen[str(path)] = ("link", os.readlink(path))
        elif path.is_dir():
            seen[str(path)] = ("dir",)
        else:
            seen[str(path)] = ("file", path.read_bytes())
    return seen
