"""E2E parity for `lore init` per Tech Spec §10.

Spec §10: "Init / migrations → tests/e2e/test_api_parity_init.py:
``run_init`` reachable through facade. Fixture changes ``cwd`` to
``tmp_path`` and calls ``run_init()`` (no-arg, uses ``Path.cwd()`` per
src/lore/init.py:131). AGENTS.md marker behaviour."

Review-Ledger CHANGED #9: ``run_init`` takes no arguments — caller must
``monkeypatch.chdir(tmp_path)`` first.

Red phase only.
"""

from __future__ import annotations



class TestRunInitReachableThroughFacade:
    """``lore.api.run_init`` is the facade entry — no args."""

    def test_run_init_callable_via_facade(self):
        from lore import api

        assert callable(api.run_init)

    def test_run_init_zero_args_creates_lore_dir(self, tmp_path, monkeypatch):
        from lore import api

        monkeypatch.chdir(tmp_path)
        # Review-Ledger CHANGED #9: run_init() takes NO arguments.
        api.run_init()
        assert (tmp_path / ".lore").is_dir()
        assert (tmp_path / ".lore" / "lore.db").is_file()

    def test_run_init_idempotent(self, tmp_path, monkeypatch):
        from lore import api

        monkeypatch.chdir(tmp_path)
        api.run_init()
        # Second call must not raise nor corrupt state.
        api.run_init()
        assert (tmp_path / ".lore" / "lore.db").is_file()


class TestRunInitProjectStructure:
    """`run_init` post-condition: .lore/ structure is fully seeded."""

    def test_init_creates_codex_directory(self, tmp_path, monkeypatch):
        from lore import api

        monkeypatch.chdir(tmp_path)
        api.run_init()
        assert (tmp_path / ".lore" / "codex").is_dir()

    def test_init_creates_doctrines_directory(self, tmp_path, monkeypatch):
        from lore import api

        monkeypatch.chdir(tmp_path)
        api.run_init()
        assert (tmp_path / ".lore" / "doctrines").is_dir()


class TestCliInitJsonParity:
    """``lore --json init`` envelope mirrors ``run_init`` outcome."""

    def test_cli_init_creates_project(self, tmp_path, monkeypatch):
        from click.testing import CliRunner

        from lore.cli import main

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0
        assert (tmp_path / ".lore" / "lore.db").is_file()
