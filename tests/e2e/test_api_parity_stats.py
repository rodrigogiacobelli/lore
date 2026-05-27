"""E2E parity for `lore stats` per Tech Spec §10.

Spec §10: "Stats → tests/e2e/test_api_parity_stats.py: aggregate stats
parity."

CLI envelope must equal ``lore.api.get_aggregate_stats``.

Red phase only.
"""

from __future__ import annotations

import json

from lore.cli import main
from tests.conftest import insert_mission, insert_quest


class TestStatsJsonParity:
    """``lore --json stats`` == ``get_aggregate_stats``."""

    def test_stats_envelope_equals_op_fn(self, runner, project_dir):
        from lore import api

        insert_quest(project_dir, "q-aaaa", "Q1")
        insert_quest(project_dir, "q-bbbb", "Q2", status="in_progress")
        insert_mission(project_dir, "q-aaaa/m-aaaa", "q-aaaa", "M1")
        insert_mission(
            project_dir,
            "q-bbbb/m-bbbb",
            "q-bbbb",
            "M2",
            status="in_progress",
        )

        result = runner.invoke(main, ["--json", "stats"])
        cli_payload = json.loads(result.stdout)
        op_payload = api.get_aggregate_stats(project_dir)

        # Envelope-preservation: byte-for-byte equality.
        assert cli_payload == op_payload, (
            f"stats CLI envelope != get_aggregate_stats return.\n"
            f"CLI:  {cli_payload}\n"
            f"API:  {op_payload}"
        )

    def test_stats_envelope_has_expected_keys(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "stats"])
        cli_payload = json.loads(result.stdout)
        assert isinstance(cli_payload, dict)
        # Aggregate stats today reports at minimum quest + mission counts.
        # Key set comes from get_aggregate_stats. Test pins shape stability.
        assert "quests" in cli_payload or "quest_count" in cli_payload
