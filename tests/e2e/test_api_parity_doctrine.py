"""E2E parity tests for the doctrine write surface — API and CLI answer alike.

Anchor: decisions-011-api-parity-with-cli — every ``lore.api`` function is
self-contained and behaviourally identical to its CLI command. What the CLI
prints on stderr for a failure is the ``ValueError`` the module raises, and what
it prints under ``--json`` is the envelope the module returns.

The one thing the CLI does that the API cannot is read the files named on the
command line; the rule about what is in them lives in ``lore.doctrine``, which
is what these tests pin.
"""

from __future__ import annotations

import json
import shutil

import pytest

from lore.cli import main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _design(doctrine_id="tdd", *, title="TDD", summary="Test-driven development."):
    return f"---\nid: {doctrine_id}\ntitle: {title}\nsummary: {summary}\n---\n\n# {title}\n"


def _mission(mission_id, *, summary="A mission.", body="Do the work.\n"):
    head = f"---\nid: {mission_id}\ntitle: {mission_id.title()}\n"
    if summary is not None:
        head += f"summary: {summary}\n"
    return f"{head}---\n\n{body}"


def _source(tmp_path, name, text):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _tree(project_dir):
    """Every file under .lore/doctrines/, keyed by relative path."""
    root = project_dir / ".lore" / "doctrines"
    return {
        path.relative_to(root).as_posix(): path.read_text()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _seed(project_dir, stem="tdd", missions=("red", "green")):
    directory = project_dir / ".lore" / "doctrines" / stem
    (directory / "missions").mkdir(parents=True, exist_ok=True)
    (directory / f"{stem}.design.md").write_text(_design(stem))
    for mission_id in missions:
        (directory / "missions" / f"{mission_id}.md").write_text(_mission(mission_id))
    return directory


# ---------------------------------------------------------------------------
# create_doctrine vs lore doctrine new
# ---------------------------------------------------------------------------


class TestCreateDoctrineParity:
    """The same call, made twice, writes the same tree and returns the same dict."""

    def test_the_envelope_is_the_same_object(self, runner, project_dir, tmp_path):
        from lore.api import create_doctrine

        design = _source(tmp_path, "d.md", _design())
        red = _source(tmp_path, "red.md", _mission("red"))

        cli = runner.invoke(
            main,
            ["--json", "doctrine", "new", "tdd", "-d", str(design), "-m", str(red)],
        )
        assert cli.exit_code == 0, cli.output
        cli_envelope = json.loads(cli.stdout)
        cli_tree = _tree(project_dir)

        # Reset the tree so the API call starts where the CLI call did.
        shutil.rmtree(project_dir / ".lore" / "doctrines" / "tdd")

        api_envelope = create_doctrine(
            project_dir, "tdd", _design(), {"red": _mission("red")}
        )

        assert cli_envelope == api_envelope
        assert _tree(project_dir) == cli_tree

    @pytest.mark.parametrize(
        "design_id,missions,message",
        [
            (
                "tdd",
                {},
                "At least one mission file is required (-m)",
            ),
            (
                "elsewhere",
                {"red": _mission("red")},
                'Design file id "elsewhere" does not match command argument "tdd"',
            ),
            (
                "tdd",
                {"red": _mission("recon")},
                'Mission file id "recon" does not match filename stem "red"',
            ),
        ],
    )
    def test_each_failure_message_is_the_modules_own(
        self, runner, project_dir, tmp_path, design_id, missions, message
    ):
        from lore.api import create_doctrine

        argv = ["doctrine", "new", "tdd", "-d", str(_source(tmp_path, "d.md", _design(design_id)))]
        for mission_id, text in missions.items():
            argv += ["-m", str(_source(tmp_path, f"{mission_id}.md", text))]

        cli = runner.invoke(main, argv)
        assert cli.exit_code == 1
        assert cli.stderr.strip() == message

        with pytest.raises(ValueError) as excinfo:
            create_doctrine(project_dir, "tdd", _design(design_id), dict(missions))
        assert str(excinfo.value) == message

    def test_neither_surface_leaves_a_partial_tree(self, runner, project_dir, tmp_path):
        from lore.api import create_doctrine

        before = _tree(project_dir)
        argv = [
            "doctrine", "new", "tdd",
            "-d", str(_source(tmp_path, "d.md", _design())),
            "-m", str(_source(tmp_path, "red.md", _mission("red", summary=None))),
        ]

        assert runner.invoke(main, argv).exit_code == 1
        assert _tree(project_dir) == before

        with pytest.raises(ValueError):
            create_doctrine(
                project_dir, "tdd", _design(), {"red": _mission("red", summary=None)}
            )
        assert _tree(project_dir) == before


# ---------------------------------------------------------------------------
# update_doctrine vs lore doctrine edit
# ---------------------------------------------------------------------------


class TestUpdateDoctrineParity:
    def test_the_envelope_is_the_same_object(self, runner, project_dir, tmp_path):
        from lore.api import update_doctrine

        _seed(project_dir)
        source = _source(tmp_path, "red.md", _mission("red", body="Rewritten.\n"))

        cli = runner.invoke(
            main, ["--json", "doctrine", "edit", "tdd", "-m", str(source)]
        )
        assert cli.exit_code == 0, cli.output
        cli_envelope = json.loads(cli.stdout)
        cli_tree = _tree(project_dir)

        api_envelope = update_doctrine(
            project_dir, "tdd", None, {"red": _mission("red", body="Rewritten.\n")}
        )

        assert cli_envelope == api_envelope
        assert _tree(project_dir) == cli_tree

    def test_a_miss_is_reported_the_same_way_on_both_surfaces(
        self, runner, project_dir, tmp_path
    ):
        from lore.api import update_doctrine

        source = _source(tmp_path, "red.md", _mission("red"))

        cli = runner.invoke(main, ["doctrine", "edit", "nope", "-m", str(source)])
        assert cli.exit_code == 1
        assert cli.stderr.strip() == 'Doctrine "nope" not found.'

        with pytest.raises(ValueError) as excinfo:
            update_doctrine(project_dir, "nope", None, {"red": _mission("red")})
        assert str(excinfo.value) == 'Doctrine "nope" not found.'

    def test_the_last_mission_guard_holds_on_both_surfaces(self, runner, project_dir):
        from lore.api import update_doctrine

        _seed(project_dir, stem="solo", missions=("only",))
        message = "Cannot remove every mission: a doctrine keeps at least one mission."

        cli = runner.invoke(
            main, ["doctrine", "edit", "solo", "--remove-mission", "only"]
        )
        assert cli.exit_code == 1
        assert cli.stderr.strip() == message

        with pytest.raises(ValueError) as excinfo:
            update_doctrine(project_dir, "solo", None, None, ["only"])
        assert str(excinfo.value) == message

    def test_the_cli_refuses_to_call_the_module_with_nothing_to_do(
        self, runner, project_dir
    ):
        """The API no-op is legal; the CLI invocation that means it is a usage error."""
        from lore.api import update_doctrine

        _seed(project_dir)

        cli = runner.invoke(main, ["doctrine", "edit", "tdd"])
        assert cli.exit_code == 2
        assert "Error: Nothing to update: pass -d, -m, or --remove-mission" in cli.stderr

        assert update_doctrine(project_dir, "tdd") == {
            "updated": "tdd",
            "design_replaced": False,
            "missions_replaced": [],
            "missions_removed": [],
        }


# ---------------------------------------------------------------------------
# delete_doctrine vs lore doctrine delete
# ---------------------------------------------------------------------------


class TestDeleteDoctrineParity:
    def test_the_envelope_is_the_same_object(self, runner, project_dir):
        from lore.api import delete_doctrine

        _seed(project_dir)
        cli = runner.invoke(main, ["--json", "doctrine", "delete", "tdd"])
        assert cli.exit_code == 0, cli.output
        cli_envelope = json.loads(cli.stdout)

        shutil.rmtree(project_dir / ".lore" / "doctrines" / "tdd.deleted")
        _seed(project_dir)
        api_envelope = delete_doctrine(project_dir, "tdd")

        assert cli_envelope == api_envelope == {
            "id": "tdd",
            "deleted": True,
            "deleted_at": None,
        }

    def test_both_surfaces_rename_the_directory(self, runner, project_dir):
        from lore.api import delete_doctrine

        directory = _seed(project_dir)
        runner.invoke(main, ["doctrine", "delete", "tdd"])
        assert directory.with_name("tdd.deleted").is_dir()
        cli_tree = _tree(project_dir)

        directory.with_name("tdd.deleted").rename(directory)
        delete_doctrine(project_dir, "tdd")

        assert _tree(project_dir) == cli_tree

    def test_a_miss_is_reported_the_same_way_on_both_surfaces(self, runner, project_dir):
        from lore.api import delete_doctrine

        cli = runner.invoke(main, ["doctrine", "delete", "nope"])
        assert cli.exit_code == 1
        assert cli.stderr.strip() == 'Doctrine "nope" not found'

        with pytest.raises(ValueError) as excinfo:
            delete_doctrine(project_dir, "nope")
        assert str(excinfo.value) == 'Doctrine "nope" not found'


# ---------------------------------------------------------------------------
# read_doctrine vs lore doctrine show
# ---------------------------------------------------------------------------


class TestReadDoctrineParity:
    def test_the_json_envelope_wraps_the_record_the_api_returns(
        self, runner, project_dir
    ):
        from lore.api import read_doctrine

        _seed(project_dir)

        cli = runner.invoke(main, ["--json", "doctrine", "show", "tdd"])
        assert cli.exit_code == 0, cli.output

        assert json.loads(cli.stdout)["doctrine"] == read_doctrine(project_dir, "tdd")

    def test_a_mission_miss_is_a_record_on_one_surface_and_an_error_on_the_other(
        self, runner, project_dir
    ):
        """ADR-011 — the CLI tells the two misses apart from the return value alone."""
        from lore.api import read_doctrine

        _seed(project_dir)

        record = read_doctrine(project_dir, "tdd", mission="nope")
        assert record is not None
        assert record["mission"] is None

        cli = runner.invoke(main, ["doctrine", "show", "tdd", "--mission", "nope"])
        assert cli.exit_code == 1
        assert cli.stderr.strip() == 'Mission "nope" not found in doctrine "tdd"'

    def test_a_doctrine_miss_is_none_on_both_surfaces(self, runner, project_dir):
        from lore.api import read_doctrine

        assert read_doctrine(project_dir, "nope") is None

        cli = runner.invoke(main, ["doctrine", "show", "nope"])
        assert cli.exit_code == 1
        assert cli.stderr.strip() == "Doctrine 'nope' not found"
