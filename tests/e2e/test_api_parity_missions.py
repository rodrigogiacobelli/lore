"""E2E parity tests for `lore missions` after G12 refactor.

Plan: transient-public-api-facade-plan §G12.
Anchor: decisions-011-api-parity-with-cli.

G12 collapses cli.py's ``missions`` handler — currently hand-rolling
the flat JSON list via ``list_missions`` — to a single call into
``lore.db.list_missions_grouped`` (G6). The CLI then projects the
grouped envelope onto its existing JSON shape.

Pre-refactor CLI JSON envelope (cli.py:945-961):
  {"missions": [
      {id, quest_id, title, status, priority, mission_type, knight,
       created_at},
      ...
  ]}

The flat envelope shape MUST stay byte-identical post-refactor — the
CLI consumes ``list_missions_grouped`` internally and re-projects.
This is the parity gate.

Red phase only.
"""

from __future__ import annotations

import json

from lore.cli import main
from tests.conftest import insert_mission, insert_quest


class TestMissionsJsonParity:
    """`lore --json missions` envelope projects from ``list_missions_grouped``."""

    def test_envelope_top_level_key(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1")
        result = runner.invoke(main, ["--json", "missions"])
        payload = json.loads(result.output)
        assert "missions" in payload, (
            "CLI flat-list envelope must keep top-level `missions` key"
        )

    def test_per_mission_envelope_keys_exact(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(
            project_dir,
            "q-a1b2/m-aaaa",
            "q-a1b2",
            "M1",
            mission_type="knight",
            knight="reviewer.md",
        )
        result = runner.invoke(main, ["--json", "missions"])
        payload = json.loads(result.output)
        assert len(payload["missions"]) == 1
        keys = set(payload["missions"][0].keys())
        assert keys == {
            "id",
            "quest_id",
            "title",
            "status",
            "priority",
            "mission_type",
            "knight",
            "created_at",
        }

    def test_missions_match_list_missions_grouped(self, runner, project_dir):
        from lore.db import list_missions_grouped

        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1")
        insert_mission(project_dir, "q-a1b2/m-bbbb", "q-a1b2", "M2")
        insert_mission(project_dir, "m-cccc", None, "Standalone")

        result = runner.invoke(main, ["--json", "missions"])
        cli_envelope = json.loads(result.output)

        op = list_missions_grouped(project_dir)
        # Project the grouped envelope onto the flat shape and compare.
        flat_ids = []
        for grp in op["groups"]:
            for m in grp["missions"]:
                flat_ids.append(m["id"])
        cli_ids = [m["id"] for m in cli_envelope["missions"]]
        assert sorted(cli_ids) == sorted(flat_ids)

    def test_quest_filter_routes_into_op_fn(self, runner, project_dir):
        from lore.db import list_missions_grouped

        insert_quest(project_dir, "q-a1b2", "Q")
        insert_quest(project_dir, "q-cccc", "Other")
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1")
        insert_mission(project_dir, "q-cccc/m-bbbb", "q-cccc", "M2")

        result = runner.invoke(main, ["--json", "missions", "q-a1b2"])
        cli_envelope = json.loads(result.output)

        op = list_missions_grouped(project_dir, quest_id="q-a1b2")
        flat_ids = []
        for grp in op["groups"]:
            for m in grp["missions"]:
                flat_ids.append(m["id"])
        cli_ids = [m["id"] for m in cli_envelope["missions"]]
        assert sorted(cli_ids) == sorted(flat_ids)

    def test_include_closed_routes_into_op_fn(self, runner, project_dir):
        from lore.db import list_missions_grouped

        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(
            project_dir,
            "q-a1b2/m-aaaa",
            "q-a1b2",
            "M1",
            status="closed",
            closed_at="2025-01-15T09:00:00Z",
        )
        result = runner.invoke(main, ["--json", "missions", "--all"])
        cli_envelope = json.loads(result.output)

        op = list_missions_grouped(project_dir, include_closed=True)
        flat_ids = []
        for grp in op["groups"]:
            for m in grp["missions"]:
                flat_ids.append(m["id"])
        cli_ids = [m["id"] for m in cli_envelope["missions"]]
        assert sorted(cli_ids) == sorted(flat_ids)


class TestMissionsHandlerUsesListMissionsGrouped:
    """G12: CLI missions handler delegates to list_missions_grouped."""

    def test_cli_uses_list_missions_grouped(self):
        from pathlib import Path

        src = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "lore"
            / "cli.py"
        ).read_text()
        assert "list_missions_grouped" in src, (
            "G12: cli.missions must delegate to lore.db.list_missions_grouped"
        )
