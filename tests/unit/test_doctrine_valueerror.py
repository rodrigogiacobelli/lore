"""``lore.doctrine`` raises plain ``ValueError`` and guards every path it builds.

Anchor: standards-separation-of-concerns — an operational module raises plain
Python exceptions; a Click-subclass exception is forbidden outside ``cli.py``.

Also pins the path-traversal guard. ``doctrine.py`` carries the strict/permissive
resolver pair the retired entity's module proved: ``_find_doctrine_dir`` refuses a
separator in a *user-supplied* name outright, while ``_resolve_doctrine_mission``
accepts the one separator a *stored* reference legitimately carries and refuses
anything that would climb out of ``.lore/doctrines/``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import click
import pytest

from lore import doctrine as doctrine_module
from lore.doctrine import (
    _find_doctrine_dir,
    _resolve_doctrine_mission,
    create_doctrine,
    delete_doctrine,
    load_mission_sources,
    read_doctrine,
    update_doctrine,
)


DESIGN = "---\nid: tdd-lite\ntitle: TDD Lite\nsummary: A doctrine.\n---\n\n# TDD Lite\n"
RECON = "---\nid: recon\ntitle: Recon\nsummary: A mission.\n---\n\nBody.\n"


@pytest.fixture()
def project(tmp_path):
    (tmp_path / ".lore" / "doctrines").mkdir(parents=True)
    return tmp_path


@pytest.fixture()
def created(project):
    create_doctrine(project, "tdd-lite", DESIGN, {"recon": RECON})
    return project


def _assert_plain_value_error(excinfo) -> None:
    assert isinstance(excinfo.value, ValueError)
    assert not isinstance(excinfo.value, click.ClickException)
    assert not isinstance(excinfo.value, click.UsageError)


# ---------------------------------------------------------------------------
# Every failure path raises a plain ValueError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,design,missions",
    [
        ("bad name", DESIGN, {"recon": RECON}),
        ("tdd-lite", "---\nid: other\ntitle: T\nsummary: S\n---\n", {"recon": RECON}),
        ("tdd-lite", "no frontmatter at all\n", {"recon": RECON}),
        ("tdd-lite", DESIGN, {}),
        ("tdd-lite", DESIGN, {"bad id": RECON}),
        ("tdd-lite", DESIGN, {"recon": "---\nid: nope\ntitle: T\nsummary: S\n---\n"}),
    ],
)
def test_create_raises_a_plain_value_error(project, name, design, missions):
    with pytest.raises(ValueError) as excinfo:
        create_doctrine(project, name, design, missions)

    _assert_plain_value_error(excinfo)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"design_content": "---\nid: other\ntitle: T\nsummary: S\n---\n"},
        {"missions": {"bad id": RECON}},
        {"remove_missions": ["nope"]},
        {"remove_missions": ["recon"]},
    ],
)
def test_update_raises_a_plain_value_error(created, kwargs):
    with pytest.raises(ValueError) as excinfo:
        update_doctrine(created, "tdd-lite", **kwargs)

    _assert_plain_value_error(excinfo)


def test_update_on_a_missing_doctrine_raises_a_plain_value_error(project):
    with pytest.raises(ValueError) as excinfo:
        update_doctrine(project, "nope", design_content=DESIGN)

    _assert_plain_value_error(excinfo)


def test_delete_on_a_missing_doctrine_raises_a_plain_value_error(project):
    with pytest.raises(ValueError) as excinfo:
        delete_doctrine(project, "nope")

    _assert_plain_value_error(excinfo)


def test_load_mission_sources_raises_a_plain_value_error(tmp_path):
    with pytest.raises(ValueError) as excinfo:
        load_mission_sources([tmp_path / "gone.md"])

    _assert_plain_value_error(excinfo)


# ---------------------------------------------------------------------------
# The path-traversal guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["../secrets", "a/b", "a\\b", "/etc/passwd"])
def test_find_doctrine_dir_refuses_a_user_supplied_path(project, name):
    if "/" not in name and "\\" not in name:  # pragma: no cover - guard the table
        pytest.fail("every case here carries a separator")

    with pytest.raises(ValueError) as excinfo:
        _find_doctrine_dir(project, name)

    _assert_plain_value_error(excinfo)
    assert str(excinfo.value) == "Invalid doctrine name: path separators not allowed"


@pytest.mark.parametrize("mission", ["../../etc/passwd", "a/b", "a\\b"])
def test_read_doctrine_refuses_a_mission_id_that_could_escape(created, mission):
    with pytest.raises(ValueError) as excinfo:
        read_doctrine(created, "tdd-lite", mission=mission)

    _assert_plain_value_error(excinfo)


def test_a_stored_reference_that_would_escape_resolves_to_nothing(created, tmp_path):
    secret = tmp_path / "secret.md"
    secret.write_text("secret")

    assert _resolve_doctrine_mission(created, "../../secret") is None
    assert _resolve_doctrine_mission(created, str(secret)) is None
    assert _resolve_doctrine_mission(created, "tdd-lite/../../../secret") is None


def test_a_stored_reference_never_raises_on_a_bad_shape(created):
    for ref in ("", "/", "//", "a/b/c", "..", "tdd-lite/"):
        assert _resolve_doctrine_mission(created, ref) is None


# ---------------------------------------------------------------------------
# No Click inside an operational module
# ---------------------------------------------------------------------------


def test_the_module_source_imports_no_click():
    source = Path(doctrine_module.__file__).read_text()

    assert "import click" not in source


def test_the_module_ast_imports_no_click():
    tree = ast.parse(Path(doctrine_module.__file__).read_text())

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name != "click" for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.module != "click"
