"""E2E parity tests for `lore edit` after G12 dispatcher refactor.

Plan: transient-public-api-facade-plan §G12.
Anchor: decisions-011-api-parity-with-cli.

G12 collapses the ``edit`` dispatcher: each branch (quest / mission)
becomes a thin call into ``lore.db.edit_quest_full`` /
``edit_mission_full``. Routing flows through ``route_entity`` — no
``startswith("q-")`` inline checks remain in cli.py.

These tests pin the JSON envelope + exit-code contract for both
success and error paths. Red phase only.
"""

from __future__ import annotations

import json

from lore.cli import main
from tests.conftest import insert_mission, insert_quest


# ---------------------------------------------------------------------------
# `lore edit <quest>` parity with edit_quest_full
# ---------------------------------------------------------------------------


class TestEditQuestJsonParity:
    """`lore --json edit <quest>` envelope matches ``edit_quest_full``."""

    def test_exit_zero_for_existing_quest(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Q")
        result = runner.invoke(
            main, ["--json", "edit", "q-a1b2", "--title", "New Title"]
        )
        assert result.exit_code == 0

    def test_json_envelope_matches_edit_quest_full(self, runner, project_dir):
        from lore.db import update_quest_full

        insert_quest(project_dir, "q-a1b2", "Old", description="d", priority=2)
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1")

        result = runner.invoke(
            main,
            [
                "--json",
                "edit",
                "q-a1b2",
                "--title",
                "Renamed",
                "--priority",
                "4",
            ],
        )
        cli_envelope = json.loads(result.output)

        # Replay equivalent op fn against a fresh DB-state by reading current
        # state — both should agree on every key.
        op_envelope = update_quest_full(
            project_dir, "q-a1b2", title="Renamed", priority=4
        )
        # Drop time-sensitive keys for comparison stability (updated_at can
        # advance between calls). Each remaining key MUST agree.
        for key in ("updated_at",):
            cli_envelope.pop(key, None)
            op_envelope.pop(key, None)
        assert cli_envelope == op_envelope

    def test_missing_quest_exit_one(self, runner, project_dir):
        result = runner.invoke(
            main, ["--json", "edit", "q-dead", "--title", "Z"]
        )
        assert result.exit_code == 1

    def test_missing_quest_json_error_envelope(self, runner, project_dir):
        result = runner.invoke(
            main, ["--json", "edit", "q-dead", "--title", "Z"]
        )
        # stderr (JSON mode) or stdout — combined and parse first JSON line.
        text = (result.output or "") + (
            result.stderr if hasattr(result, "stderr") else ""
        )
        line = next((ln for ln in text.splitlines() if ln.startswith("{")), "")
        payload = json.loads(line) if line else {}
        assert "error" in payload


# ---------------------------------------------------------------------------
# `lore edit <mission>` parity with edit_mission_full
# ---------------------------------------------------------------------------


class TestEditMissionJsonParity:
    """`lore --json edit <mission>` envelope matches ``edit_mission_full``."""

    def test_exit_zero_for_existing_mission(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1")
        result = runner.invoke(
            main, ["--json", "edit", "q-a1b2/m-aaaa", "--title", "Renamed"]
        )
        assert result.exit_code == 0

    def test_json_envelope_matches_edit_mission_full(self, runner, project_dir):
        from lore.db import update_mission_full

        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(
            project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1", knight="reviewer.md"
        )

        result = runner.invoke(
            main,
            [
                "--json",
                "edit",
                "q-a1b2/m-aaaa",
                "--title",
                "Renamed",
            ],
        )
        cli_envelope = json.loads(result.output)

        op_envelope = update_mission_full(
            project_dir, "q-a1b2/m-aaaa", title="Renamed"
        )
        for key in ("updated_at",):
            cli_envelope.pop(key, None)
            op_envelope.pop(key, None)
        assert cli_envelope == op_envelope

    def test_missing_mission_exit_one(self, runner, project_dir):
        result = runner.invoke(
            main, ["--json", "edit", "m-dead", "--title", "Z"]
        )
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Routing must flow through route_entity — garbage IDs format-error
# ---------------------------------------------------------------------------


class TestEditGarbageIdRouting:
    def test_garbage_exits_one(self, runner, project_dir):
        result = runner.invoke(main, ["edit", "garbage", "--title", "T"])
        assert result.exit_code != 0


class TestEditDispatcherStructure:
    """`edit` dispatcher collapses to thin wrapper over `edit_*_full`.

    Spec §G12 + §7: each branch becomes ~one-liner. Inline ``startswith
    ("q-")`` checks at cli.py:1604-1611 area should be replaced by
    ``route_entity`` dispatch.
    """

    def test_edit_uses_route_entity(self):
        from pathlib import Path

        src = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "lore"
            / "cli.py"
        ).read_text()
        # Top-level edit handler must rely on route_entity-style dispatch.
        # We can't AST-walk only the edit subtree easily, but the broad
        # invariant from G12 is: cli.py no longer dispatches edit branches
        # via inline ``startswith("q-")``. The id_dispatch test already
        # covers the absence of that token globally; here we add a
        # positive marker — ``route_entity`` is referenced in cli.py.
        assert "route_entity" in src, (
            "G12: cli.edit dispatch must route through validators.route_entity"
        )
