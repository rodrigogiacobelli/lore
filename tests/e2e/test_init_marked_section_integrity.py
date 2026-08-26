"""E2E tests for the marked block `lore init` writes into a file the user owns.

Adversarial smoke round 2 ran six `lore init` processes at a 4000-line
`CLAUDE.md` that carried no markers yet. One run in twelve came out **1121
lines short** and holding **two** `<!-- lore:begin -->` pairs: the writer was a
read-modify-write whose final `write_text` truncated the file in place, so a
process reading during another's write spliced its block onto a torn prefix.

The corruption then hid itself. Reconciliation digests the *first* marker pair,
found it already equal to the desired block, and took the unreported no-op row
— so the next `lore init` exited 0 reporting success over a file missing a
quarter of the user's content, and the code that objects to a doubled pair was
never reached.

Two properties, one per half:

* a section write lands **whole or not at all**, so no reader can see a torn
  file and no second writer can splice onto one;
* a file carrying more than one marker pair is a **loud error**, at every stage
  that looks at it — never a silent success.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from lore import init as init_module
from lore import manifest
from lore.cli import main

BEGIN = "<!-- lore:begin -->"
END = "<!-- lore:end -->"
MARKERS = (BEGIN, END)

INIT = {
    "--agent": "claude",
    "--skills": "all",
    "--access": "native",
    "--skills-gitignore": "lore-only",
    "--on-existing-agent-file": "append",
}


def init_args(changes: dict[str, str] | None = None) -> list[str]:
    answers = {**INIT, **(changes or {})}
    args = ["init"]
    for flag, value in answers.items():
        args += [flag, value]
    return [*args, "--yes"]


def run_init(runner, changes: dict[str, str] | None = None):
    return runner.invoke(main, init_args(changes))


@pytest.fixture()
def project(tmp_path, monkeypatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture()
def installed(runner, project) -> Path:
    result = run_init(runner)
    assert result.exit_code == 0, result.output
    return project


# ---------------------------------------------------------------------------
# The write lands whole or not at all
# ---------------------------------------------------------------------------


class TestTheSectionWriteIsAtomic:
    def test_a_hardlinked_companion_keeps_its_content(self, project):
        """An in-place write changes the shared inode and takes every other
        name for it with it; a replace cannot."""
        target = project / "CLAUDE.md"
        target.write_text("# My project\n")
        companion = project / "companion.md"
        os.link(target, companion)

        init_module.write_marked_section(target, "block\n", markers=MARKERS)

        assert companion.read_text() == "# My project\n"
        assert BEGIN in target.read_text()

    def test_a_concurrent_reader_never_sees_a_torn_file(self, project):
        target = project / "CLAUDE.md"
        body = "# My project\n" + "padding line\n" * 40000
        target.write_text(body)
        torn: list[int] = []
        stop = threading.Event()

        def reader() -> None:
            while not stop.is_set():
                seen = target.read_text()
                if seen.count("padding line\n") != 40000:
                    torn.append(len(seen))

        watcher = threading.Thread(target=reader)
        watcher.start()
        try:
            for index in range(20):
                init_module.write_marked_section(
                    target, f"block {index}\n" * 40, markers=MARKERS
                )
        finally:
            stop.set()
            watcher.join()

        assert torn == [], f"{len(torn)} torn reads"

    def test_the_user_content_survives_concurrent_inits(self, project):
        """The smoke round's own reproduction, staggered so the reads of one
        run land inside the writes of another."""
        target = project / "CLAUDE.md"
        body = "# My project\n" + "padding line\n" * 20000
        target.write_text(body)

        _race_inits(project, count=6, stagger=0.02)

        text = target.read_text()
        assert text.count("padding line\n") == 20000
        assert text.count(BEGIN) == 1
        assert text.count(END) == 1


def _race_inits(project: Path, *, count: int, stagger: float) -> None:
    """Start *count* real `lore init` processes, each a little after the last."""
    running = []
    for _ in range(count):
        running.append(
            subprocess.Popen(
                [sys.executable, "-m", "lore", *init_args()],
                cwd=project,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        )
        time.sleep(stagger)
    for process in running:
        process.wait()


# ---------------------------------------------------------------------------
# A doubled marker pair is never a silent success
# ---------------------------------------------------------------------------


def double_the_block(target: Path, relative: str = "CLAUDE.md") -> None:
    """Append a second copy of the block already in *target*.

    The shape a torn concurrent write left behind: two well-formed pairs, the
    first of them exactly what Lore would put there.
    """
    begin, end = init_module._marker_pair(relative)
    text = target.read_text()
    block = manifest.section_text(text, begin, end)
    assert block is not None, text
    target.write_text(f"{text}{begin}\n{block}{end}\n")


class TestMoreThanOneMarkerPair:
    """`CLAUDE.md` alone: it is the only marked block a run still writes.

    The root `.gitignore` was the second, and no release writes one now. A
    doubled pair in a `.gitignore` an older release left behind stops a run the
    same way, through the same reader — the removal path reads the block before
    it deletes it.
    """

    def test_the_next_run_stops_rather_than_reporting_success(
        self, runner, installed, relative="CLAUDE.md"
    ):
        target = installed / relative
        double_the_block(target, relative)

        result = run_init(runner)

        assert result.exit_code == 1, result.output
        assert "Initialized Lore project" not in result.stdout
        assert "more than one Lore marker block" in result.stderr
        assert "Traceback" not in result.stderr

    def test_the_damaged_file_is_left_exactly_as_it_was(self, runner, installed):
        target = installed / "CLAUDE.md"
        double_the_block(target)
        before = target.read_bytes()

        run_init(runner)

        assert target.read_bytes() == before

    def test_a_dry_run_reports_it_too(self, runner, installed):
        double_the_block(installed / "CLAUDE.md")

        result = runner.invoke(main, [*init_args(), "--dry-run"])

        assert result.exit_code == 1, result.output
        assert "more than one Lore marker block" in result.stderr

    def test_reading_the_block_refuses_to_pick_the_first_pair(self):
        text = f"{BEGIN}\nfirst\n{END}\ntail\n{BEGIN}\nsecond\n{END}\n"

        with pytest.raises(ValueError) as caught:
            manifest.section_text(text, BEGIN, END, source="CLAUDE.md")

        assert "more than one Lore marker block" in str(caught.value)
        assert "CLAUDE.md" in str(caught.value)
