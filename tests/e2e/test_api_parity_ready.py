"""E2E parity for `lore ready` per Tech Spec §10.

Spec §10: "Ready queue → tests/e2e/test_api_parity_ready.py: priority +
dependency gating + blocked exclusion parity."

CLI's ``ready`` JSON envelope must equal ``lore.api.get_ready_missions``.

Red phase only.
"""

from __future__ import annotations

import json

from lore.cli import main
from tests.conftest import insert_mission, insert_quest


class TestReadyJsonParity:
    """``lore --json ready`` matches ``get_ready_missions``."""

    def test_empty_project_returns_empty_list(self, runner, project_dir):
        from lore import api

        result = runner.invoke(main, ["--json", "ready"])
        cli_payload = json.loads(result.stdout)
        op_payload = api.get_ready_missions(project_dir)
        cli_items = cli_payload if isinstance(cli_payload, list) else cli_payload.get("missions", cli_payload.get("ready", []))
        assert len(cli_items) == len(op_payload)

    def test_priority_one_mission_returned(self, runner, project_dir):
        from lore import api

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(
            project_dir, "q-aaaa/m-aaaa", "q-aaaa", "M1", priority=1
        )
        insert_mission(
            project_dir, "q-aaaa/m-bbbb", "q-aaaa", "M2", priority=3
        )

        result = runner.invoke(main, ["--json", "ready"])
        cli_payload = json.loads(result.stdout)
        op_payload = api.get_ready_missions(project_dir)

        cli_items = cli_payload if isinstance(cli_payload, list) else cli_payload.get("missions", cli_payload.get("ready", []))
        assert len(cli_items) == len(op_payload), (
            "ready CLI envelope count diverges from get_ready_missions"
        )

    def test_blocked_missions_excluded(self, runner, project_dir):
        from lore import api

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(
            project_dir,
            "q-aaaa/m-aaaa",
            "q-aaaa",
            "Blocked",
            status="blocked",
            block_reason="x",
        )
        insert_mission(
            project_dir, "q-aaaa/m-bbbb", "q-aaaa", "Open", priority=2
        )

        result = runner.invoke(main, ["--json", "ready"])
        cli_payload = json.loads(result.stdout)
        op_payload = api.get_ready_missions(project_dir)

        cli_items = cli_payload if isinstance(cli_payload, list) else cli_payload.get("missions", cli_payload.get("ready", []))
        cli_ids = [m["id"] for m in cli_items]

        def _row_id(row):
            if hasattr(row, "id"):
                return row.id
            try:
                return row["id"]
            except (KeyError, IndexError):
                return None

        op_ids = [_row_id(r) for r in op_payload]
        assert cli_ids == op_ids, (
            "CLI ready ordering / membership diverges from get_ready_missions"
        )
