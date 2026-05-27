"""E2E parity tests for `lore claim` after G12 bulk-op refactor.

Plan: transient-public-api-facade-plan §G12.
Anchor: decisions-011-api-parity-with-cli.

G12 collapses the hand-rolled accumulator loop in cli.py's ``claim``
handler into a single call to ``lore.db.claim_missions`` (G5).

Envelope (cli.py:495-503 / claim_missions docstring):
  {"updated": [...], "quest_status_changed": [...], "errors": [...]}

Red phase only.
"""

from __future__ import annotations

import json

from lore.cli import main
from tests.conftest import insert_mission, insert_quest


class TestClaimJsonParity:
    """`lore --json claim <ids...>` envelope matches ``claim_missions``."""

    def test_envelope_keys_exact(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1")
        result = runner.invoke(main, ["--json", "claim", "q-a1b2/m-aaaa"])
        payload = json.loads(result.output)
        assert set(payload.keys()) == {
            "updated",
            "quest_status_changed",
            "errors",
        }

    def test_envelope_keys_match_claim_missions(self, runner, project_dir):
        from lore.db import claim_missions

        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1")
        insert_mission(project_dir, "q-a1b2/m-bbbb", "q-a1b2", "M2")

        result = runner.invoke(
            main, ["--json", "claim", "q-a1b2/m-aaaa", "q-a1b2/m-bbbb"]
        )
        cli_envelope = json.loads(result.output)

        op_envelope = claim_missions(
            project_dir, ["q-a1b2/m-aaaa", "q-a1b2/m-bbbb"]
        )
        assert set(cli_envelope.keys()) == set(op_envelope.keys())

    def test_bulk_partial_failure_collects_errors(self, runner, project_dir):
        """Failing mission ID does not roll back earlier successes."""
        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1")
        result = runner.invoke(
            main, ["--json", "claim", "q-a1b2/m-aaaa", "m-dead1"]
        )
        payload = json.loads(result.output)
        assert "q-a1b2/m-aaaa" in payload["updated"]
        assert len(payload["errors"]) >= 1

    def test_invalid_format_id_collected_in_errors(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "claim", "garbage"])
        payload = json.loads(result.output)
        assert payload["updated"] == []
        assert len(payload["errors"]) == 1
        assert "garbage" in payload["errors"][0]

    def test_cli_claim_uses_claim_missions_op_fn(self):
        """G12: CLI claim handler imports/uses ``lore.db.claim_missions``."""
        from pathlib import Path

        src = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "lore"
            / "cli.py"
        ).read_text()
        assert "claim_missions" in src, (
            "G12: cli.claim must delegate to lore.db.claim_missions"
        )

    def test_quest_status_change_recorded(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1")
        result = runner.invoke(main, ["--json", "claim", "q-a1b2/m-aaaa"])
        payload = json.loads(result.output)
        # quest_status_changed accumulates {id, status} entries.
        assert any(
            isinstance(c, dict) and c.get("id") == "q-a1b2"
            for c in payload["quest_status_changed"]
        )
