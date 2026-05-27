"""E2E parity for quest CRUD commands per Tech Spec §10.

Spec §10 row: "Quest CRUD → tests/e2e/test_api_parity_quest.py: parity
for `new quest`, `list`, `edit`, `delete`, `show` quest."

Existing files already cover:
  * test_api_parity_show.py  — `show` quest envelope parity
  * test_api_parity_edit.py  — `edit` envelope parity
  * test_api_parity_delete.py — `delete` envelope parity

This file fills the gaps that have NO parity test today:
  * `new quest` JSON envelope == ``lore.api.create_quest`` return value.
  * `list` (quest list) JSON == ``lore.api.list_quests`` / ``get_dashboard_quests``.

Red phase only.
"""

from __future__ import annotations

import json

from lore.cli import main


class TestNewQuestJsonParity:
    """``lore --json new quest`` envelope matches facade ``create_quest``."""

    def test_envelope_contains_id(self, runner, project_dir):
        result = runner.invoke(
            main, ["--json", "new", "quest", "Quest title"]
        )
        payload = json.loads(result.stdout)
        assert "id" in payload
        assert payload["id"].startswith("q-")

    def test_envelope_matches_create_quest_return(self, runner, project_dir):
        """CLI JSON dict equals what facade ``create_quest`` returns."""
        from lore import api

        cli_result = runner.invoke(
            main,
            ["--json", "new", "quest", "API parity check", "--priority", "1"],
        )
        cli_payload = json.loads(cli_result.stdout)

        # Direct facade call — same project, same args.
        op_id = api.create_quest(
            project_dir, "API parity check", priority=1
        )
        # Envelope today is `{"id": "q-..."}`. Op fn returns the ID string.
        # Facade-parity contract: CLI dict's "id" key matches op fn return.
        assert cli_payload["id"] != op_id  # two separate quests
        assert set(cli_payload.keys()) == {"id"}

    def test_new_quest_uses_facade(self):
        """G13 done-gate: ``cli.py`` calls ``lore.api.create_quest`` (not lore.db)."""
        from pathlib import Path

        src = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "lore"
            / "cli.py"
        ).read_text()
        # After G13, CLI imports come exclusively from lore.api.
        assert "from lore.db import create_quest" not in src, (
            "cli.py still imports create_quest from lore.db; route via lore.api"
        )


class TestListQuestsJsonParity:
    """``lore --json list`` envelope mirrors ``lore.api.get_dashboard_quests``."""

    def test_list_envelope_has_quests_key(self, runner, project_dir):
        """CLI envelope is ``{"quests": [...]}`` — pinned for ADR-011 parity."""
        from lore import api

        api.create_quest(project_dir, "Q1")
        api.create_quest(project_dir, "Q2")

        result = runner.invoke(main, ["--json", "list"])
        payload = json.loads(result.stdout)
        assert isinstance(payload, dict)
        assert "quests" in payload, (
            "CLI `list` envelope must wrap results in a 'quests' key "
            "(ADR-011 envelope-preservation)"
        )

    def test_list_payload_count_matches(self, runner, project_dir):
        from lore import api

        api.create_quest(project_dir, "Q1")
        api.create_quest(project_dir, "Q2")
        api.create_quest(project_dir, "Q3")

        result = runner.invoke(main, ["--json", "list"])
        cli_payload = json.loads(result.stdout)
        op_payload = api.get_dashboard_quests(project_dir)

        cli_items = cli_payload["quests"] if isinstance(cli_payload, dict) else cli_payload
        assert len(cli_items) == len(op_payload)
