"""E2E parity tests for `lore delete` after G17 dispatcher refactor.

Plan: transient-public-api-facade-plan §G17.
Anchor: decisions-011-api-parity-with-cli.

G12 collapsed the ``delete`` dispatcher: ``_delete_quest`` and
``_delete_mission`` helpers are removed; the top-level handler calls
``lore.db.delete_entity(..., cascade=…)`` directly. G17 BREAKING swap
(amendment Review Ledger CHANGED row): the envelope drops the
``already_deleted`` flag and the ``ok`` wrapper, returning a positive
shape on success and on the idempotent re-delete path. CLI emits the
``delete_entity`` envelope verbatim.

JSON envelope shapes per amendment A2 + Section B:

  quest (cascade=False) -> {id, deleted: True, deleted_at, cascade: None}
  quest (cascade=True)  -> {id, deleted: True, deleted_at, cascade: list[str]}
  mission               -> {id, deleted: True, deleted_at}
  idempotent re-delete  -> same envelope with the prior deleted_at timestamp.
"""

from __future__ import annotations

import json

from lore.cli import main
from tests.conftest import insert_mission, insert_quest


# ---------------------------------------------------------------------------
# Quest delete parity
# ---------------------------------------------------------------------------


class TestDeleteQuestParity:
    """`lore --json delete <quest>` envelope matches ``delete_entity``."""

    def test_exit_zero_on_existing_quest(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Q")
        result = runner.invoke(main, ["--json", "delete", "q-a1b2"])
        assert result.exit_code == 0

    def test_success_envelope_keys_no_cascade(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Q")
        result = runner.invoke(main, ["--json", "delete", "q-a1b2"])
        payload = json.loads(result.output)
        assert set(payload.keys()) == {"id", "deleted", "deleted_at", "cascade"}, (
            "G17 quest delete (no cascade) envelope must be EXACTLY "
            "{id, deleted, deleted_at, cascade}"
        )
        assert payload["id"] == "q-a1b2"
        assert payload["deleted"] is True
        assert payload["cascade"] is None

    def test_success_envelope_keys_with_cascade(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1")
        result = runner.invoke(
            main, ["--json", "delete", "q-a1b2", "--cascade"]
        )
        payload = json.loads(result.output)
        assert set(payload.keys()) == {"id", "deleted", "deleted_at", "cascade"}
        assert payload["id"] == "q-a1b2"
        assert "q-a1b2/m-aaaa" in payload["cascade"]

    def test_idempotent_re_delete_returns_same_envelope(self, runner, project_dir):
        """G17: prior-deleted entity returns the same positive envelope with
        the original deleted_at timestamp (no `already_deleted` flag)."""
        insert_quest(
            project_dir, "q-a1b2", "Q", deleted_at="2025-01-15T08:00:00Z"
        )
        result = runner.invoke(main, ["--json", "delete", "q-a1b2"])
        payload = json.loads(result.output)
        assert "already_deleted" not in payload
        assert "ok" not in payload
        assert payload["deleted"] is True
        assert payload["deleted_at"] == "2025-01-15T08:00:00Z"

    def test_loose_quest_id_in_db_resolves(self, runner, project_dir):
        """Loose-pattern (non-hex) quest ID still resolves via DB fallback."""
        insert_quest(project_dir, "q-zzzz", "Loose")
        result = runner.invoke(main, ["--json", "delete", "q-zzzz"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["id"] == "q-zzzz"


# ---------------------------------------------------------------------------
# Mission delete parity
# ---------------------------------------------------------------------------


class TestDeleteMissionParity:
    """`lore --json delete <mission>` envelope matches ``delete_entity``."""

    def test_exit_zero_on_existing_mission(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1")
        result = runner.invoke(main, ["--json", "delete", "q-a1b2/m-aaaa"])
        assert result.exit_code == 0

    def test_success_envelope_keys_exact(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1")
        result = runner.invoke(main, ["--json", "delete", "q-a1b2/m-aaaa"])
        payload = json.loads(result.output)
        assert set(payload.keys()) == {"id", "deleted", "deleted_at"}

    def test_idempotent_re_delete_returns_same_envelope(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(
            project_dir,
            "q-a1b2/m-aaaa",
            "q-a1b2",
            "M1",
            deleted_at="2025-01-15T08:00:00Z",
        )
        result = runner.invoke(main, ["--json", "delete", "q-a1b2/m-aaaa"])
        payload = json.loads(result.output)
        assert "already_deleted" not in payload
        assert payload["deleted"] is True
        assert payload["deleted_at"] == "2025-01-15T08:00:00Z"


# ---------------------------------------------------------------------------
# Dispatcher routes through route_entity / classifier — no inline branching
# ---------------------------------------------------------------------------


class TestDeleteDispatcherRouting:
    """CLI top-level ``delete`` no longer hand-rolls quest/mission branches."""

    def test_garbage_id_emits_format_error(self, runner, project_dir):
        result = runner.invoke(main, ["delete", "garbage"])
        assert result.exit_code == 1
        combined = (result.output or "") + (
            result.stderr if hasattr(result, "stderr") else ""
        )
        assert "format" in combined.lower() or "invalid" in combined.lower()

    def test_helpers_removed_from_cli(self):
        from lore import cli

        assert not hasattr(cli, "_delete_quest")
        assert not hasattr(cli, "_delete_mission")

    def test_cli_uses_delete_entity_op_fn(self):
        """G12: CLI delete handler delegates to lore.db.delete_entity."""
        from pathlib import Path

        src = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "lore"
            / "cli.py"
        ).read_text()
        assert "delete_entity" in src, (
            "G12: cli.delete must delegate to lore.db.delete_entity"
        )
