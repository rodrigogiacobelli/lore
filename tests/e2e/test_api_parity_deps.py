"""E2E parity tests for `lore needs` / `lore unneed` after G12 bulk-op refactor.

Plan: transient-public-api-facade-plan §G12.
Anchor: decisions-011-api-parity-with-cli.

G12 collapses cli.py's hand-rolled accumulator loops on ``needs`` and
``unneed`` into thin wrappers over ``lore.db.add_dependencies`` /
``remove_dependencies`` (G5). Colon-pair parsing stays in the CLI;
the bulk op fns receive ``list[tuple[from_id, to_id]]``.

Envelopes (cli.py:768-776 / 862-869):
  needs:  {"created": [...], "existing": [...], "errors": [...]}
  unneed: {"removed": [...], "not_found": [...], "errors": [...]}

Each entry in created/existing/removed/not_found has keys EXACTLY
``from`` + ``to`` (NEVER ``from_id``/``to_id``).

Red phase only.
"""

from __future__ import annotations

import json

from lore.cli import main
from tests.conftest import insert_dependency, insert_mission, insert_quest


# ---------------------------------------------------------------------------
# `lore needs` parity with add_dependencies
# ---------------------------------------------------------------------------


class TestNeedsJsonParity:
    """`lore --json needs <pairs...>` envelope matches ``add_dependencies``."""

    def test_envelope_keys_exact(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1")
        insert_mission(project_dir, "q-a1b2/m-bbbb", "q-a1b2", "M2")
        result = runner.invoke(
            main,
            ["--json", "needs", "q-a1b2/m-aaaa:q-a1b2/m-bbbb"],
        )
        payload = json.loads(result.output)
        assert set(payload.keys()) == {"created", "existing", "errors"}

    def test_pair_uses_from_to_keys_not_from_id_to_id(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1")
        insert_mission(project_dir, "q-a1b2/m-bbbb", "q-a1b2", "M2")
        result = runner.invoke(
            main,
            ["--json", "needs", "q-a1b2/m-aaaa:q-a1b2/m-bbbb"],
        )
        payload = json.loads(result.output)
        assert len(payload["created"]) == 1
        entry = payload["created"][0]
        assert set(entry.keys()) == {"from", "to"}
        assert "from_id" not in entry
        assert "to_id" not in entry

    def test_duplicate_routes_into_existing(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1")
        insert_mission(project_dir, "q-a1b2/m-bbbb", "q-a1b2", "M2")
        insert_dependency(project_dir, "q-a1b2/m-aaaa", "q-a1b2/m-bbbb")
        result = runner.invoke(
            main,
            ["--json", "needs", "q-a1b2/m-aaaa:q-a1b2/m-bbbb"],
        )
        payload = json.loads(result.output)
        assert payload["created"] == []
        assert any(
            p == {"from": "q-a1b2/m-aaaa", "to": "q-a1b2/m-bbbb"}
            for p in payload["existing"]
        )

    def test_envelope_keys_match_add_dependencies(self, runner, project_dir):
        from lore.db import add_dependencies

        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1")
        insert_mission(project_dir, "q-a1b2/m-bbbb", "q-a1b2", "M2")
        result = runner.invoke(
            main,
            ["--json", "needs", "q-a1b2/m-aaaa:q-a1b2/m-bbbb"],
        )
        cli_envelope = json.loads(result.output)
        op_envelope = add_dependencies(project_dir, [])
        assert set(cli_envelope.keys()) == set(op_envelope.keys())

    def test_bad_pair_format_collected_in_errors(self, runner, project_dir):
        result = runner.invoke(
            main, ["--json", "needs", "garbage-without-colon"]
        )
        payload = json.loads(result.output)
        assert payload["created"] == []
        assert payload["existing"] == []
        assert len(payload["errors"]) == 1


# ---------------------------------------------------------------------------
# `lore unneed` parity with remove_dependencies
# ---------------------------------------------------------------------------


class TestUnneedJsonParity:
    """`lore --json unneed <pairs...>` envelope matches ``remove_dependencies``."""

    def test_envelope_keys_exact(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1")
        insert_mission(project_dir, "q-a1b2/m-bbbb", "q-a1b2", "M2")
        insert_dependency(project_dir, "q-a1b2/m-aaaa", "q-a1b2/m-bbbb")
        result = runner.invoke(
            main,
            ["--json", "unneed", "q-a1b2/m-aaaa:q-a1b2/m-bbbb"],
        )
        payload = json.loads(result.output)
        assert set(payload.keys()) == {"removed", "not_found", "errors"}

    def test_removed_entry_uses_from_to_keys(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1")
        insert_mission(project_dir, "q-a1b2/m-bbbb", "q-a1b2", "M2")
        insert_dependency(project_dir, "q-a1b2/m-aaaa", "q-a1b2/m-bbbb")
        result = runner.invoke(
            main,
            ["--json", "unneed", "q-a1b2/m-aaaa:q-a1b2/m-bbbb"],
        )
        payload = json.loads(result.output)
        assert len(payload["removed"]) == 1
        entry = payload["removed"][0]
        assert set(entry.keys()) == {"from", "to"}

    def test_missing_dependency_lands_in_not_found(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1")
        insert_mission(project_dir, "q-a1b2/m-bbbb", "q-a1b2", "M2")
        # No dep inserted — should land in not_found.
        result = runner.invoke(
            main,
            ["--json", "unneed", "q-a1b2/m-aaaa:q-a1b2/m-bbbb"],
        )
        payload = json.loads(result.output)
        assert payload["removed"] == []
        assert len(payload["not_found"]) == 1

    def test_envelope_keys_match_remove_dependencies(self, runner, project_dir):
        from lore.db import remove_dependencies

        result = runner.invoke(main, ["--json", "unneed", "m-aaaa:m-bbbb"])
        cli_envelope = json.loads(result.output)
        op_envelope = remove_dependencies(project_dir, [])
        assert set(cli_envelope.keys()) == set(op_envelope.keys())


# ---------------------------------------------------------------------------
# Structural assertions — CLI handlers delegate to bulk op fns
# ---------------------------------------------------------------------------


class TestDepsHandlersUseBulkOpFns:
    """G12: needs/unneed handlers delegate to add_dependencies/remove_dependencies."""

    def test_cli_uses_add_dependencies(self):
        from pathlib import Path

        src = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "lore"
            / "cli.py"
        ).read_text()
        assert "add_dependencies" in src, (
            "G12: cli.needs must delegate to lore.db.add_dependencies"
        )

    def test_cli_uses_remove_dependencies(self):
        from pathlib import Path

        src = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "lore"
            / "cli.py"
        ).read_text()
        assert "remove_dependencies" in src, (
            "G12: cli.unneed must delegate to lore.db.remove_dependencies"
        )
