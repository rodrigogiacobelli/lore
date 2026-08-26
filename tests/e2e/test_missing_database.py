"""E2E tests for a project whose `.lore/lore.db` is not there.

Spec: conceptual-workflows-error-handling
(lore codex show conceptual-workflows-error-handling)

This is not an exotic state. `.lore/lore.db` is generated and correctly
gitignored, so **every clone of a Lore project is in it** until somebody runs
`lore init`. What a teammate used to get on their first command was a raw
`sqlite3.OperationalError: no such table: lore_meta` out of `db._run_migrations`
— and, on the way down, a 4096-byte empty database file the failing command had
created itself.

The rule the rest of the CLI already keeps (`ProjectNotFoundError` names the
cause and the repair) is the one asserted here, for every command that opens the
database rather than only the one the smoke test happened to run.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from lore.cli import main


DB_COMMANDS = (
    ["stats"],
    ["list"],
    ["ready"],
    ["missions"],
    ["show", "q-0000"],
    ["new", "quest", "Anything"],
    ["claim", "q-0000/m-0000"],
    ["done", "q-0000/m-0000"],
    ["block", "q-0000/m-0000", "reason"],
    ["board", "add", "q-0000", "hello"],
    ["oracle"],
)
"""One entry per command group that opens the database."""

DB_FREE_COMMANDS = (
    ["health"],
    ["codex", "list"],
)
"""Commands that never touch it — they must keep working in a fresh clone."""


@pytest.fixture()
def cloned(tmp_path, monkeypatch):
    """A project as it arrives from a clone: every tracked file, no database."""
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(main, ["init", "--agent", "none", "--yes"])
    assert result.exit_code == 0, result.output
    (tmp_path / ".lore" / "lore.db").unlink()
    return tmp_path


class TestEveryCommandThatOpensTheDatabase:
    @pytest.mark.parametrize("argv", DB_COMMANDS, ids=lambda argv: " ".join(argv))
    def test_it_names_the_cause_and_the_repair_instead_of_a_traceback(
        self, runner, cloned, argv
    ):
        result = runner.invoke(main, argv)

        assert result.exit_code != 0, result.output
        message = result.stderr + result.stdout
        assert "Traceback" not in message
        assert "sqlite3" not in message
        assert "lore.db" in message
        assert "lore init" in message

    @pytest.mark.parametrize("argv", DB_COMMANDS, ids=lambda argv: " ".join(argv))
    def test_it_does_not_create_an_empty_database_on_its_way_down(
        self, runner, cloned, argv
    ):
        runner.invoke(main, argv)
        assert not (cloned / ".lore" / "lore.db").exists()

    def test_json_mode_reports_it_as_json(self, runner, cloned):
        import json

        result = runner.invoke(main, ["--json", "stats"])

        assert result.exit_code != 0, result.output
        assert "lore.db" in json.loads(result.stderr)["error"]


class TestCommandsThatNeverOpenIt:
    @pytest.mark.parametrize("argv", DB_FREE_COMMANDS, ids=lambda argv: " ".join(argv))
    def test_they_still_work(self, runner, cloned, argv):
        result = runner.invoke(main, argv)
        assert result.exit_code == 0, result.output


class TestTheRepair:
    def test_lore_init_rebuilds_the_database_and_the_commands_come_back(
        self, runner, cloned
    ):
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        result = runner.invoke(main, ["stats"])
        assert result.exit_code == 0, result.output
