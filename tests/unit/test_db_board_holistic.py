"""Red tests for G17: holistic db-backed CRUD sweep — board slice.

Spec sources:
  lore codex show transient-public-api-facade-plan              # §G17
  lore codex show transient-public-api-facade-create-stdz       # §A2 §A4 §B (Board row)

Board contracts:

* `add_board_message(project_root, entity_id, message, *, sender=None)
  -> dict {id, entity_id, sender, created_at}` — DROPS the `ok` wrapper
  (amendment Review Ledger CHANGED row); raises `ValueError` on validation
  / not-found / soft-deleted entity.
* `list_board_messages(project_root, entity_id) -> list[dict]` — RENAME from
  `get_board_messages` (amendment B Board row).
* `delete_board_message(project_root, entity_id, message_id) -> dict
  {id, deleted: True, deleted_at}` — drops `ok` wrapper; raises on miss
  OR on cross-entity mismatch (entity_id arg disagrees with stored row).

These tests EXPECT the new shapes. They MUST fail until G17 Green lands.
NO production code in this chunk — Red phase only.
"""

from __future__ import annotations

import pytest

from tests.conftest import insert_board_message, insert_quest


# ---------------------------------------------------------------------------
# Symbol existence — list_board_messages rename
# ---------------------------------------------------------------------------


def test_list_board_messages_symbol_exists_on_lore_db():
    from lore import db

    assert hasattr(db, "list_board_messages"), (
        "G17: lore.db.list_board_messages not defined yet (Red phase expected)"
    )
    assert callable(db.list_board_messages)


def test_old_get_board_messages_name_removed_from_facade():
    from lore import api

    assert "get_board_messages" not in api.__all__, (
        "G17: `get_board_messages` must be renamed to `list_board_messages`"
    )


# ---------------------------------------------------------------------------
# add_board_message — drop ok wrapper, raise on errors
# ---------------------------------------------------------------------------


ADD_BOARD_KEYS: frozenset[str] = frozenset(
    {"id", "entity_id", "sender", "created_at"}
)


class TestAddBoardMessageDropsOkWrapper:
    def test_add_board_message_success_envelope_keys_exact(self, project_dir):
        """Amendment Review Ledger: drop `ok`, return positive envelope."""
        from lore.db import add_board_message

        insert_quest(project_dir, "q-aaaa", "Q")
        result = add_board_message(project_dir, "q-aaaa", "hello", sender="alice")
        assert isinstance(result, dict)
        assert "ok" not in result, (
            "amendment Review Ledger CHANGED: add_board_message MUST drop `ok` wrapper"
        )
        assert set(result.keys()) == ADD_BOARD_KEYS, (
            f"add_board_message envelope MUST have EXACTLY "
            f"{sorted(ADD_BOARD_KEYS)}; got {sorted(result.keys())}"
        )

    def test_add_board_message_field_values(self, project_dir):
        from lore.db import add_board_message

        insert_quest(project_dir, "q-aaaa", "Q")
        result = add_board_message(project_dir, "q-aaaa", "hello", sender="alice")
        assert result["entity_id"] == "q-aaaa"
        assert result["sender"] == "alice"
        assert isinstance(result["created_at"], str)
        assert isinstance(result["id"], int)

    def test_add_board_message_raises_on_empty_message(self, project_dir):
        from lore.db import add_board_message

        insert_quest(project_dir, "q-aaaa", "Q")
        with pytest.raises(ValueError):
            add_board_message(project_dir, "q-aaaa", "")

    def test_add_board_message_raises_on_unknown_entity(self, project_dir):
        from lore.db import add_board_message

        with pytest.raises(ValueError):
            add_board_message(project_dir, "q-9999", "hi")

    def test_add_board_message_raises_on_soft_deleted_entity(self, project_dir):
        from lore.db import add_board_message

        insert_quest(
            project_dir,
            "q-dddd",
            "Gone",
            deleted_at="2025-02-01T00:00:00Z",
        )
        with pytest.raises(ValueError):
            add_board_message(project_dir, "q-dddd", "hi")

    def test_add_board_message_raises_on_bad_entity_id_format(self, project_dir):
        from lore.db import add_board_message

        with pytest.raises(ValueError):
            add_board_message(project_dir, "not-an-id!!", "hi")


# ---------------------------------------------------------------------------
# list_board_messages — rename
# ---------------------------------------------------------------------------


class TestListBoardMessages:
    def test_list_board_messages_returns_list_of_dicts(self, project_dir):
        from lore.db import list_board_messages

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_board_message(project_dir, "q-aaaa", "first")
        insert_board_message(project_dir, "q-aaaa", "second")

        results = list_board_messages(project_dir, "q-aaaa")
        assert isinstance(results, list)
        assert all(isinstance(r, dict) for r in results)
        assert len(results) == 2

    def test_list_board_messages_empty_for_unknown_entity(self, project_dir):
        from lore.db import list_board_messages

        assert list_board_messages(project_dir, "q-9999") == []


# ---------------------------------------------------------------------------
# delete_board_message — drop ok wrapper, raise on miss
# ---------------------------------------------------------------------------


DELETE_BOARD_KEYS: frozenset[str] = frozenset({"id", "deleted", "deleted_at"})


class TestDeleteBoardMessageHolistic:
    def _seed_message(self, project_dir, entity_id="q-aaaa") -> int:
        from lore.db import add_board_message

        insert_quest(project_dir, entity_id, "Q")
        envelope = add_board_message(project_dir, entity_id, "hello")
        return envelope["id"]

    def test_delete_board_message_envelope_keys_exact(self, project_dir):
        from lore.db import delete_board_message

        mid = self._seed_message(project_dir)
        result = delete_board_message(project_dir, "q-aaaa", mid)
        assert set(result.keys()) == DELETE_BOARD_KEYS, (
            f"delete_board_message envelope MUST have EXACTLY "
            f"{sorted(DELETE_BOARD_KEYS)}; got {sorted(result.keys())}"
        )

    def test_delete_board_message_drops_ok(self, project_dir):
        from lore.db import delete_board_message

        mid = self._seed_message(project_dir)
        result = delete_board_message(project_dir, "q-aaaa", mid)
        assert "ok" not in result

    def test_delete_board_message_positive_fields(self, project_dir):
        from lore.db import delete_board_message

        mid = self._seed_message(project_dir)
        result = delete_board_message(project_dir, "q-aaaa", mid)
        assert result["id"] == mid
        assert result["deleted"] is True
        assert isinstance(result["deleted_at"], str)

    def test_delete_board_message_raises_on_unknown_id(self, project_dir):
        from lore.db import delete_board_message

        with pytest.raises(ValueError, match="not found"):
            delete_board_message(project_dir, "q-aaaa", 9999)

    def test_delete_board_message_raises_on_entity_mismatch(self, project_dir):
        """Cross-entity ID collision guard: row exists but stored entity differs."""
        from lore.db import delete_board_message

        mid = self._seed_message(project_dir, entity_id="q-aaaa")
        insert_quest(project_dir, "q-bbbb", "Other")
        with pytest.raises(ValueError, match="does not belong"):
            delete_board_message(project_dir, "q-bbbb", mid)
