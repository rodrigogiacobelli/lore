"""E2E parity tests for `lore done` after G12 bulk-op refactor.

Plan: transient-public-api-facade-plan §G12.
Anchor: decisions-011-api-parity-with-cli.

G12 swaps the hand-rolled accumulator loop in cli.py's ``done`` handler
for a single call to ``lore.db.close_entities`` (G5). The closure
``_is_quest_id`` is deleted; the CLI emits the bulk-op envelope
verbatim.

Envelope (cli.py:570-578, replicated in close_entities):
  {"updated": [...], "quest_closed": [...], "errors": [...]}

Red phase only.
"""

from __future__ import annotations

import json

from lore.cli import main
from tests.conftest import insert_mission, insert_quest


# ---------------------------------------------------------------------------
# JSON envelope parity with close_entities
# ---------------------------------------------------------------------------


class TestDoneJsonParity:
    """`lore --json done <ids...>` envelope matches ``close_entities``."""

    def test_envelope_keys_exact(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(
            project_dir,
            "q-a1b2/m-aaaa",
            "q-a1b2",
            "M1",
            status="in_progress",
        )
        result = runner.invoke(main, ["--json", "done", "q-a1b2/m-aaaa"])
        payload = json.loads(result.output)
        assert set(payload.keys()) == {"updated", "quest_closed", "errors"}

    def test_envelope_matches_close_entities(self, runner, project_dir):
        from lore.db import close_entities

        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(
            project_dir,
            "q-a1b2/m-aaaa",
            "q-a1b2",
            "M1",
            status="in_progress",
        )
        insert_mission(
            project_dir,
            "q-a1b2/m-bbbb",
            "q-a1b2",
            "M2",
            status="in_progress",
        )

        # Replay the same call sequence through both surfaces. Use a fresh
        # project for each side to keep idempotent recompute equal.
        # CLI path:
        result = runner.invoke(
            main, ["--json", "done", "q-a1b2/m-aaaa", "q-a1b2/m-bbbb"]
        )
        cli_envelope = json.loads(result.output)

        # Op-fn path needs an isolated DB state; the CLI already closed
        # the missions, so re-running close_entities on them will hit
        # the "already closed" no-op path — both surfaces should still
        # produce the SAME shape with `updated` populated (close_entities
        # treats already-closed as success). Compare KEY SETS exactly.
        op_envelope = close_entities(
            project_dir, ["q-a1b2/m-aaaa", "q-a1b2/m-bbbb"]
        )
        assert set(cli_envelope.keys()) == set(op_envelope.keys())

    def test_mixed_quest_and_mission_routes_via_close_entities(
        self, runner, project_dir
    ):
        """Mixed ID list dispatches inside ``close_entities`` (no _is_quest_id)."""
        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(
            project_dir,
            "q-a1b2/m-aaaa",
            "q-a1b2",
            "M1",
            status="in_progress",
        )
        result = runner.invoke(
            main, ["--json", "done", "q-a1b2/m-aaaa", "q-a1b2"]
        )
        payload = json.loads(result.output)
        # Quest auto-close triggered by the mission means q-a1b2 will
        # show up in updated. Even if not, the envelope keys are the
        # same — the partial-flow tolerance just requires no crash.
        assert "updated" in payload
        assert "quest_closed" in payload
        assert "errors" in payload

    def test_done_handler_does_not_define_inline_is_quest_id(self):
        """G12: cli.done must NOT define a closure named ``_is_quest_id``."""
        import ast
        from pathlib import Path

        cli_path = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "lore"
            / "cli.py"
        )
        tree = ast.parse(cli_path.read_text())
        # Find the ``done`` top-level function (decorated @main.command).
        done_fn = None
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "done"
            ):
                done_fn = node
                break
        assert done_fn is not None, "cli.done function not found"
        bad = [
            n.name
            for n in ast.walk(done_fn)
            if isinstance(n, ast.FunctionDef) and n.name == "_is_quest_id"
        ]
        assert bad == [], (
            "G12: cli.done must not contain inline `_is_quest_id` closure; "
            "use close_entities + route_entity dispatch instead"
        )

    def test_cli_uses_close_entities_op_fn(self):
        """G12: CLI done handler delegates to close_entities."""
        from pathlib import Path

        src = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "lore"
            / "cli.py"
        ).read_text()
        assert "close_entities" in src, (
            "G12: cli.done must delegate to lore.db.close_entities"
        )

    def test_already_closed_no_error(self, runner, project_dir):
        """Already-closed mission counts in `updated`, not `errors`."""
        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(
            project_dir,
            "q-a1b2/m-aaaa",
            "q-a1b2",
            "M1",
            status="closed",
            closed_at="2025-01-15T09:00:00Z",
        )
        result = runner.invoke(main, ["--json", "done", "q-a1b2/m-aaaa"])
        payload = json.loads(result.output)
        assert payload["errors"] == []
        assert "q-a1b2/m-aaaa" in payload["updated"]
