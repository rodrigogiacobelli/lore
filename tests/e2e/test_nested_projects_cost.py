"""The zero-cost proof: a project in no tree pays nothing for Nested Projects.

Spec: nested-projects-spec (lore codex show nested-projects-spec) — F11
Success criteria: SC-6 (zero directory scans outside the project's own
``.lore/``, and no ``config.toml`` read but its own) and SC-7 (byte-identical
stdout for every FR-13 command).

These are characterisation tests. They pass before the feature exists and must
keep passing after it — that is the whole point: A-7 records that the downward
axis is off unless asked, and SC-6/SC-7 are what make a later change that
collapses the two axes onto one ``scope`` value visibly a breach rather than a
simplification.

``monkeypatch`` here only counts calls (``Path.rglob``, ``Path.iterdir``,
``os.walk``, ``Path.open``) and never replaces behaviour — the walks, the TOML
parser and the real tree are all exercised for real.

The SC-7 golden capture in ``goldens/nested_projects_sc7.json`` was taken from
the pre-change tree. Capturing it after a change proves nothing, so the test
only ever reads it; there is deliberately no regeneration switch here.

The fixture drops every seeded ``default/`` subtree and authors one entity of
each readable kind instead, so the capture pins only text this file wrote.
``adr-no-default-content-tests`` rules out asserting what a seeded template
contains, and a golden capture over seeded rows would be exactly that.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from lore.cli import main


GOLDEN_PATH = Path(__file__).parent / "goldens" / "nested_projects_sc7.json"


# The FR-13 list, plus FR-13a's two additions: every read command that will
# accept ``--project``. Each entry is the argv a standalone project must
# answer byte-for-byte the way it does today.
FR13_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("codex", "list"),
    ("codex", "show", "sc7-anchor"),
    ("codex", "search", "anchor"),
    ("codex", "map", "sc7-anchor"),
    ("doctrine", "list"),
    ("doctrine", "show", "sc7-doctrine"),
    ("artifact", "list"),
    ("artifact", "show", "sc7-artifact"),
    ("rite", "list"),
    ("rite", "show", "sc7-rite"),
    ("rite", "search", "refund"),
    ("watcher", "list"),
    ("watcher", "show", "sc7-watcher"),
    ("glossary", "list"),
    ("glossary", "search", "sc7"),
    ("glossary", "show", "sc7-term"),
    ("impacts", "sc7-anchor"),
)


# Every seeded subtree `lore init` installs, plus the two user-owned files it
# writes once (ADR-013 constraints 2 and 3). None of them may reach a golden.
_SEEDED_TREES = ("doctrines", "artifacts", "watchers")


_ANCHOR_DOC = """\
---
id: sc7-anchor
title: SC-7 Anchor
summary: The document the byte-identity capture reads, authored by this test.
related:
  - sc7-neighbour
binds:
  - src/lore/projects.py
---

# SC-7 Anchor

The body exists so `lore codex show` has something to print.
"""

_NEIGHBOUR_DOC = """\
---
id: sc7-neighbour
title: SC-7 Neighbour
summary: A second document, so `lore codex map` has an edge to traverse.
---

# SC-7 Neighbour

Reached from the anchor.
"""

_ARTIFACT_MD = """\
---
id: sc7-artifact
title: SC-7 Artifact
summary: An artifact authored by this test so `artifact list` has a row.
---

# SC-7 Artifact

A template with no content worth pinning.
"""

_DOCTRINE_DESIGN = """\
---
id: sc7-doctrine
title: SC-7 Doctrine
summary: A doctrine authored by this test so `doctrine list` has a row.
---

# SC-7 Doctrine

One mission.
"""

_DOCTRINE_MISSION = """\
---
id: only-mission
title: Do the thing
summary: The one mission this doctrine carries.
---

Do the thing.
"""

_WATCHER_YAML = """\
id: sc7-watcher
title: SC-7 Watcher
summary: A watcher authored by this test so `watcher list` has a row.
watch_target:
  - src/lore/projects.py
interval: on_merge
action:
  - doctrine: sc7-doctrine
"""

_RITE_YAML = """\
id: sc7-rite
title: Issue a refund for a returned order
summary: Confirm the customer is reachable, then refund.
trigger: Customer requests a refund on a returned order.
nodes:
  - id: only-step
    do: Find the order by id; confirm it is in 'returned' state.
    then: refunded
conclusions:
  refunded:
    audience: customer-care
    response: Refund posted; share the transaction id.
"""


def author_standalone_project(root: Path) -> None:
    """Build the fixture the SC-7 goldens were captured from.

    Shared by the capture and the comparison, so the two cannot drift. The
    caller has already changed the working directory to ``root``.
    """
    runner = CliRunner()
    runner.invoke(main, ["init"])

    lore = root / ".lore"
    for tree in _SEEDED_TREES:
        shutil.rmtree(lore / tree / "default", ignore_errors=True)
    (lore / "codex" / "codex.md").unlink(missing_ok=True)

    (lore / "codex" / "sc7-anchor.md").write_text(_ANCHOR_DOC, encoding="utf-8")
    (lore / "codex" / "sc7-neighbour.md").write_text(_NEIGHBOUR_DOC, encoding="utf-8")
    (lore / "artifacts" / "sc7-artifact.md").write_text(_ARTIFACT_MD, encoding="utf-8")
    doctrine = lore / "doctrines" / "sc7-doctrine"
    (doctrine / "missions").mkdir(parents=True, exist_ok=True)
    (doctrine / "sc7-doctrine.design.md").write_text(
        _DOCTRINE_DESIGN, encoding="utf-8"
    )
    (doctrine / "missions" / "only-mission.md").write_text(
        _DOCTRINE_MISSION, encoding="utf-8"
    )
    (lore / "watchers" / "sc7-watcher.yaml").write_text(_WATCHER_YAML, encoding="utf-8")
    (lore / "rites" / "main" / "sc7-rite.yaml").write_text(_RITE_YAML, encoding="utf-8")

    runner.invoke(
        main,
        [
            "glossary",
            "new",
            "sc7-term",
            "-d",
            "A term this test authors so the glossary commands have a row.",
        ],
    )


def capture_fr13_stdout() -> dict[str, str]:
    """Run every FR-13 command and return ``{argv: stdout}``."""
    runner = CliRunner()
    captured: dict[str, str] = {}
    for command in FR13_COMMANDS:
        result = runner.invoke(main, list(command))
        captured[" ".join(command)] = result.stdout
    return captured


@pytest.fixture()
def sc7_project(tmp_path, monkeypatch):
    """A standalone project holding one authored entity of each readable kind."""
    monkeypatch.chdir(tmp_path)
    author_standalone_project(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# SC-7 — byte-identical stdout in a project with no tree
# ---------------------------------------------------------------------------


def test_the_golden_capture_covers_every_fr13_command():
    # nested-projects-spec — SC-7: a command missing from the capture is a
    # command whose output nothing pins
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert set(golden) == {" ".join(command) for command in FR13_COMMANDS}


def test_the_golden_capture_pins_no_seeded_content(sc7_project):
    # adr-no-default-content-tests — the fixture removes every `default/`
    # subtree before the capture, so no golden asserts what a template says
    lore = sc7_project / ".lore"
    for tree in _SEEDED_TREES:
        assert not (lore / tree / "default").exists()
    assert not (lore / "codex" / "codex.md").exists()


@pytest.mark.parametrize("command", FR13_COMMANDS, ids=lambda c: " ".join(c))
def test_stdout_is_byte_identical_to_the_pre_change_capture(sc7_project, command):
    # nested-projects-spec — SC-7 / FR-16: the ORIGIN column appears only when
    # the result set holds a non-`self` row, so a project in no tree prints
    # exactly what it printed before the feature existed
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    result = CliRunner().invoke(main, list(command))

    assert result.stdout == golden[" ".join(command)]


# ---------------------------------------------------------------------------
# SC-6 — zero directory scans, and no foreign config read
# ---------------------------------------------------------------------------


class _CallCounter:
    """Records every scan and every open, then delegates to the real call."""

    def __init__(self) -> None:
        self.scans: list[Path] = []
        self.opens: list[Path] = []

    def install(self, monkeypatch) -> None:
        real_rglob = Path.rglob
        real_iterdir = Path.iterdir
        real_walk = os.walk
        real_open = Path.open

        def rglob(path, *args, **kwargs):
            self.scans.append(Path(path))
            return real_rglob(path, *args, **kwargs)

        def iterdir(path, *args, **kwargs):
            self.scans.append(Path(path))
            return real_iterdir(path, *args, **kwargs)

        def walk(top, *args, **kwargs):
            self.scans.append(Path(top))
            return real_walk(top, *args, **kwargs)

        def opener(path, *args, **kwargs):
            self.opens.append(Path(path))
            return real_open(path, *args, **kwargs)

        monkeypatch.setattr(Path, "rglob", rglob)
        monkeypatch.setattr(Path, "iterdir", iterdir)
        monkeypatch.setattr(os, "walk", walk)
        monkeypatch.setattr(Path, "open", opener)


def test_a_standalone_read_scans_nothing_outside_its_own_lore(sc7_project, monkeypatch):
    # nested-projects-spec — SC-6 / FR-11 / N-3: downward discovery runs only
    # when the resolved scope asks for it
    counter = _CallCounter()
    counter.install(monkeypatch)

    CliRunner().invoke(main, ["codex", "list"])

    lore_dir = (sc7_project / ".lore").resolve()
    outside = [p for p in counter.scans if not p.resolve().is_relative_to(lore_dir)]
    assert outside == []


def test_a_standalone_read_opens_no_config_but_its_own(sc7_project, monkeypatch):
    # nested-projects-spec — SC-6 / N-4: the upward probe is `is_dir()`, not a
    # read, so no directory above contributes an open
    counter = _CallCounter()
    counter.install(monkeypatch)

    CliRunner().invoke(main, ["codex", "list"])

    own_config = (sc7_project / ".lore" / "config.toml").resolve()
    configs = {p.resolve() for p in counter.opens if p.name == "config.toml"}
    assert configs <= {own_config}


def test_a_standalone_read_opens_no_file_outside_its_own_project(
    sc7_project, monkeypatch
):
    # nested-projects-spec — N-6 / SC-6: a read command touches its own project
    # and nothing else
    counter = _CallCounter()
    counter.install(monkeypatch)

    CliRunner().invoke(main, ["codex", "list"])

    root = sc7_project.resolve()
    outside = [p for p in counter.opens if not p.resolve().is_relative_to(root)]
    assert outside == []
