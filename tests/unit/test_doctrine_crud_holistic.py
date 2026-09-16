"""Holistic sweep for ``lore.doctrine`` — signatures, envelopes and shapes.

Workflow: conceptual-workflows-doctrine-new (lore codex show conceptual-workflows-doctrine-new)

Pins the contract ``lore.api`` re-exports:

* every callable takes ``project_root: Path`` first;
* ``create_doctrine(project_root, name, design_content, missions, *, group=None)``;
* ``update_doctrine(project_root, name, design_content=None, missions=None,
  remove_missions=None)``;
* ``read_doctrine(project_root, doctrine_id, *, scope=None, mission=None)``;
* the four envelopes are exact key sets;
* ``read_doctrine`` returns ``None`` on a miss rather than raising.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from lore import doctrine as doctrine_module
from lore.doctrine import (
    create_doctrine,
    delete_doctrine,
    list_doctrines,
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


# ---------------------------------------------------------------------------
# Signatures
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fn",
    [create_doctrine, read_doctrine, update_doctrine, delete_doctrine, list_doctrines],
)
def test_the_first_positional_parameter_is_project_root(fn):
    assert list(inspect.signature(fn).parameters)[0] == "project_root"


def test_create_doctrines_positional_order(project):
    parameters = inspect.signature(create_doctrine).parameters
    positional = [
        name
        for name, p in parameters.items()
        if p.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    ]

    assert positional == ["project_root", "name", "design_content", "missions"]
    assert parameters["group"].kind is inspect.Parameter.KEYWORD_ONLY


def test_update_doctrines_positional_order():
    parameters = inspect.signature(update_doctrine).parameters
    positional = [
        name
        for name, p in parameters.items()
        if p.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    ]

    assert positional == [
        "project_root",
        "name",
        "design_content",
        "missions",
        "remove_missions",
    ]
    assert all(parameters[name].default is None for name in positional[2:])


def test_read_doctrine_takes_scope_and_mission_as_keywords():
    parameters = inspect.signature(read_doctrine).parameters

    assert parameters["scope"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["mission"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["mission"].default is None


def test_no_callable_takes_a_doctrines_dir_parameter():
    for fn in (create_doctrine, read_doctrine, update_doctrine, delete_doctrine):
        assert "doctrines_dir" not in inspect.signature(fn).parameters


def test_every_write_callable_takes_the_project_root_as_a_path(created):
    assert isinstance(created, Path)
    assert read_doctrine(created, "tdd-lite") is not None


# ---------------------------------------------------------------------------
# Envelopes are exact key sets
# ---------------------------------------------------------------------------


def test_create_envelope_key_set(project):
    result = create_doctrine(project, "tdd-lite", DESIGN, {"recon": RECON})

    assert set(result) == {"created", "group", "missions", "path"}


def test_update_envelope_key_set(created):
    result = update_doctrine(created, "tdd-lite", missions={"recon": RECON})

    assert set(result) == {
        "updated",
        "design_replaced",
        "missions_replaced",
        "missions_removed",
    }


def test_delete_envelope_key_set(created):
    assert set(delete_doctrine(created, "tdd-lite")) == {"id", "deleted", "deleted_at"}


def test_read_envelope_key_set(created):
    assert set(read_doctrine(created, "tdd-lite")) == {
        "id",
        "title",
        "summary",
        "design",
        "missions",
        "origin",
    }


def test_read_envelope_key_set_with_a_mission(created):
    assert set(read_doctrine(created, "tdd-lite", mission="recon")) == {
        "id",
        "title",
        "summary",
        "design",
        "missions",
        "origin",
        "mission",
    }


def test_list_envelope_key_set(created):
    assert set(list_doctrines(created)[0]) == {
        "id",
        "group",
        "title",
        "summary",
        "valid",
        "filename",
        "origin",
    }


def test_the_create_envelope_drops_every_legacy_key(project):
    result = create_doctrine(project, "tdd-lite", DESIGN, {"recon": RECON})

    for legacy in ("id", "filename", "design_filename", "yaml_filename"):
        assert legacy not in result


def test_the_update_envelope_drops_every_legacy_key(created):
    result = update_doctrine(created, "tdd-lite", missions={"recon": RECON})

    for legacy in ("id", "filename", "updated_at"):
        assert legacy not in result


# ---------------------------------------------------------------------------
# read_doctrine returns None on a miss rather than raising
# ---------------------------------------------------------------------------


def test_a_miss_returns_none(project):
    assert read_doctrine(project, "nope") is None


def test_a_miss_does_not_raise(project):
    try:
        read_doctrine(project, "nope")
    except Exception as exc:  # pragma: no cover - the assert names the failure
        pytest.fail(f"read_doctrine raised {exc!r} on a miss")


def test_a_malformed_design_frontmatter_is_a_miss_not_a_raise(project):
    directory = project / ".lore" / "doctrines" / "broken"
    directory.mkdir(parents=True)
    (directory / "broken.design.md").write_text("---\nid: [unclosed\n---\n\nBody.\n")

    assert read_doctrine(project, "broken") is None


def test_list_is_empty_when_the_doctrines_dir_is_absent(tmp_path):
    assert list_doctrines(tmp_path) == []


# ---------------------------------------------------------------------------
# The module owns the doctrine directory and nothing else
# ---------------------------------------------------------------------------


def test_the_module_defines_no_doctrine_error():
    assert not hasattr(doctrine_module, "DoctrineError")


def test_the_module_imports_no_database_module():
    source = Path(doctrine_module.__file__).read_text()

    assert "from lore.db" not in source
    assert "from lore import db" not in source
