"""Unit tests for group-qualified knight references in the health scan (RED).

Doctrines write a mission's ``knight`` field — and a doctrine step's ``knight``
key — in group-qualified form: ``tdd-feature/defaults-reviewer.md``. Both
health checks handed that string straight to ``_find_knight``, whose
path-traversal guard rejects any name containing a separator, so the whole
``knights`` scope died with ``scan_failed`` for as long as a single
doctrine-driven mission stayed open.

The guard stays where it belongs: ``_find_knight`` takes an untrusted,
user-supplied name. A reference read back out of the database or a doctrine
file is resolved by ``_resolve_knight_ref`` instead, which accepts the group
and refuses only references that would climb out of ``.lore/knights/``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lore.health import _check_doctrines, _check_knights
from lore.knight import _find_knight, _resolve_knight_ref

KNIGHT_MD = "---\nid: {name}\ntitle: Reviewer\nsummary: s\n---\nBody.\n"


@pytest.fixture()
def lore_dir(tmp_path):
    """Bare .lore/ directory with all required subdirs."""
    lore = tmp_path / ".lore"
    for d in ["knights", "doctrines", "codex", "artifacts", "watchers"]:
        (lore / d).mkdir(parents=True)
    (lore / "codex" / "transient").mkdir(parents=True)
    return tmp_path


def _write_grouped_knight(root: Path, group: str, name: str) -> Path:
    target = root / ".lore" / "knights" / group
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{name}.md"
    path.write_text(KNIGHT_MD.format(name=name))
    return path


def _make_doctrine_dirs(tmp_path):
    doctrines_dir = tmp_path / ".lore" / "doctrines"
    doctrines_dir.mkdir(parents=True, exist_ok=True)
    knights_dir = tmp_path / ".lore" / "knights"
    knights_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return doctrines_dir, knights_dir, artifacts_dir


def _write_doctrine(doctrines_dir: Path, stem: str, knight_ref: str) -> None:
    (doctrines_dir / f"{stem}.design.md").write_text(
        f"---\nid: {stem}\ntitle: D\nsummary: s\n---\nBody.\n"
    )
    (doctrines_dir / f"{stem}.yaml").write_text(
        f"id: {stem}\ntitle: D\nsummary: s\nsteps:\n"
        f"  - id: step-1\n    title: Step 1\n    knight: {knight_ref}\n"
    )


# ---------------------------------------------------------------------------
# _resolve_knight_ref — the stored-reference resolver
# ---------------------------------------------------------------------------


def test_resolve_knight_ref_accepts_a_group_qualified_filename(lore_dir):
    """The exact form a doctrine writes resolves to the file in that group."""
    path = _write_grouped_knight(lore_dir, "tdd-feature", "defaults-reviewer")

    assert _resolve_knight_ref(lore_dir, "tdd-feature/defaults-reviewer.md") == path


def test_resolve_knight_ref_accepts_a_group_without_the_md_suffix(lore_dir):
    path = _write_grouped_knight(lore_dir, "tdd-feature", "defaults-reviewer")

    assert _resolve_knight_ref(lore_dir, "tdd-feature/defaults-reviewer") == path


def test_resolve_knight_ref_accepts_a_bare_name(lore_dir):
    """A knight in a group is still reachable by its bare stem, as before."""
    path = _write_grouped_knight(lore_dir, "tdd-feature", "defaults-reviewer")

    assert _resolve_knight_ref(lore_dir, "defaults-reviewer") == path


def test_resolve_knight_ref_returns_none_for_an_unknown_group_qualified_ref(lore_dir):
    assert _resolve_knight_ref(lore_dir, "tdd-feature/nobody.md") is None


def test_resolve_knight_ref_refuses_to_climb_out_of_the_knights_directory(lore_dir):
    """A traversal reference resolves to nothing — never to a file outside."""
    (lore_dir / "secret.md").write_text("top secret")

    assert _resolve_knight_ref(lore_dir, "../../secret.md") is None
    assert _resolve_knight_ref(lore_dir, "../secret.md") is None


def test_resolve_knight_ref_refuses_an_absolute_reference(lore_dir):
    _write_grouped_knight(lore_dir, "tdd-feature", "defaults-reviewer")

    assert _resolve_knight_ref(lore_dir, "/etc/passwd") is None


def test_resolve_knight_ref_returns_none_for_an_empty_reference(lore_dir):
    assert _resolve_knight_ref(lore_dir, "") is None


def test_find_knight_still_rejects_path_separators(lore_dir):
    """The traversal guard on the user-facing locator is untouched."""
    _write_grouped_knight(lore_dir, "tdd-feature", "defaults-reviewer")

    with pytest.raises(ValueError, match="path separators not allowed"):
        _find_knight(lore_dir, "tdd-feature/defaults-reviewer")


# ---------------------------------------------------------------------------
# _check_knights — mission refs
# ---------------------------------------------------------------------------


def test_check_knights_resolves_a_group_qualified_mission_ref(lore_dir):
    """An open doctrine-driven mission no longer kills the scan."""
    from tests.conftest import insert_mission, insert_quest

    _write_grouped_knight(lore_dir, "tdd-feature", "defaults-reviewer")
    insert_quest(lore_dir, "q-g001", "Quest G")
    insert_mission(
        lore_dir,
        "m-g001",
        "q-g001",
        "Mission G",
        knight="tdd-feature/defaults-reviewer.md",
    )

    issues = _check_knights(lore_dir / ".lore" / "knights", lore_dir)

    assert issues == []


def test_check_knights_group_qualified_ref_with_no_file_reports_missing_file(lore_dir):
    """An unresolvable grouped ref is an ordinary finding, not a scan failure."""
    from tests.conftest import insert_mission, insert_quest

    insert_quest(lore_dir, "q-g002", "Quest G2")
    insert_mission(
        lore_dir,
        "m-g002",
        "q-g002",
        "Mission G2",
        knight="tdd-feature/nobody.md",
    )

    issues = _check_knights(lore_dir / ".lore" / "knights", lore_dir)

    assert [i.check for i in issues] == ["missing_file"]
    assert issues[0].id == "tdd-feature/nobody.md"
    assert "m-g002" in issues[0].detail


def test_check_knights_group_qualified_soft_deleted_knight_is_not_an_error(lore_dir):
    """A soft-deleted knight in a group stays exempt, as it is ungrouped."""
    from tests.conftest import insert_mission, insert_quest

    target = lore_dir / ".lore" / "knights" / "tdd-feature"
    target.mkdir(parents=True)
    (target / "defaults-reviewer.md.deleted").write_text("deleted")
    insert_quest(lore_dir, "q-g003", "Quest G3")
    insert_mission(
        lore_dir,
        "m-g003",
        "q-g003",
        "Mission G3",
        knight="tdd-feature/defaults-reviewer.md",
    )

    issues = _check_knights(lore_dir / ".lore" / "knights", lore_dir)

    assert issues == []


def test_check_knights_traversal_mission_ref_reports_missing_file(lore_dir):
    """A hand-edited traversal ref is reported, never resolved."""
    from tests.conftest import insert_mission, insert_quest

    (lore_dir / "secret.md").write_text("top secret")
    insert_quest(lore_dir, "q-g004", "Quest G4")
    insert_mission(
        lore_dir, "m-g004", "q-g004", "Mission G4", knight="../../secret.md"
    )

    issues = _check_knights(lore_dir / ".lore" / "knights", lore_dir)

    assert [i.check for i in issues] == ["missing_file"]


# ---------------------------------------------------------------------------
# _check_doctrines — step refs
# ---------------------------------------------------------------------------


def test_check_doctrines_resolves_a_group_qualified_step_knight(tmp_path):
    doctrines_dir, knights_dir, artifacts_dir = _make_doctrine_dirs(tmp_path)
    _write_grouped_knight(tmp_path, "tdd-feature", "scout")
    _write_doctrine(doctrines_dir, "feat-x", "tdd-feature/scout.md")

    issues = _check_doctrines(doctrines_dir, knights_dir, artifacts_dir)

    assert [i for i in issues if i.check == "broken_knight_ref"] == []


def test_check_doctrines_group_qualified_step_knight_missing_is_a_broken_ref(tmp_path):
    doctrines_dir, knights_dir, artifacts_dir = _make_doctrine_dirs(tmp_path)
    _write_doctrine(doctrines_dir, "feat-x", "tdd-feature/nobody.md")

    issues = _check_doctrines(doctrines_dir, knights_dir, artifacts_dir)

    broken = [i for i in issues if i.check == "broken_knight_ref"]
    assert len(broken) == 1
    assert "tdd-feature/nobody.md" in broken[0].detail
