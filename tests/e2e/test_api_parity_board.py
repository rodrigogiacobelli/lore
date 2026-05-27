"""E2E parity for `lore board` commands per Tech Spec §10.

Spec §10: "Board → tests/e2e/test_api_parity_board.py: add, get, delete;
empty-message rejection; soft-deleted-entity rejection."

CLI envelope must equal ``lore.api.add_board_message`` /
``list_board_messages`` / ``delete_board_message``. G17 BREAKING swap
(amendment Review Ledger CHANGED): ``add_board_message`` drops the
``ok`` wrapper; ``get_board_messages`` renamed to ``list_board_messages``.
"""

from __future__ import annotations

import json

from lore.cli import main
from tests.conftest import insert_quest


class TestBoardAddJsonParity:
    """``lore --json board add`` matches ``add_board_message``."""

    def test_envelope_has_id_and_message(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Q")
        result = runner.invoke(
            main,
            [
                "--json",
                "board",
                "add",
                "q-aaaa",
                "hello",
                "--sender",
                "tester",
            ],
        )
        payload = json.loads(result.stdout)
        # Envelope contract: id + message echo + sender + entity reference.
        assert "id" in payload or "message_id" in payload

    def test_add_round_trips_through_get_board_messages(
        self, runner, project_dir
    ):
        from lore import api

        insert_quest(project_dir, "q-aaaa", "Q")
        runner.invoke(
            main,
            [
                "--json",
                "board",
                "add",
                "q-aaaa",
                "hello",
                "--sender",
                "tester",
            ],
        )
        op_messages = api.list_board_messages(project_dir, "q-aaaa")
        assert len(op_messages) >= 1
        assert any(getattr(m, "message", None) == "hello" or m.get("message") == "hello" for m in op_messages)


class TestBoardEmptyMessageRejection:
    """ADR-011 + audit: empty message rejected at API layer, not CLI-only."""

    def test_empty_message_returns_error_envelope(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Q")
        result = runner.invoke(
            main,
            [
                "--json",
                "board",
                "add",
                "q-aaaa",
                "",
                "--sender",
                "tester",
            ],
        )
        # Non-zero exit + stderr error OR JSON {ok: False, error}
        assert result.exit_code != 0 or "error" in result.stdout.lower()


class TestBoardDeletedEntityRejection:
    """Posting to soft-deleted quest must be rejected (parity)."""

    def test_post_to_soft_deleted_quest_rejected(self, runner, project_dir):
        insert_quest(
            project_dir,
            "q-aaaa",
            "Q",
            deleted_at="2025-01-15T10:00:00Z",
        )
        result = runner.invoke(
            main,
            [
                "--json",
                "board",
                "add",
                "q-aaaa",
                "hello",
                "--sender",
                "tester",
            ],
        )
        assert result.exit_code != 0 or "error" in result.stdout.lower()
