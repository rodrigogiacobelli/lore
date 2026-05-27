"""Red tests for G17: holistic db-backed CRUD sweep — quest slice.

Spec sources:
  lore codex show transient-public-api-facade-plan              # §G17
  lore codex show transient-public-api-facade-create-stdz       # §A1 §A2 §A4 §B

This chunk is the FINAL BREAKING wave. Per amendment Section A2 + Section B
"Quest" row, every db-backed CRUD on quest must now match:

* `read_quest(project_root, quest_id) -> dict | None`  (RENAME `get_quest`).
* `list_quests(project_root, *, include_closed=False) -> list[dict]`
  (Row → dict; same key strings as columns).
* `create_quest(project_root, title, *, description="", priority=2,
  auto_close=0) -> dict {id, filename: None, group: None}`  (was bare `str`).
* `update_quest(project_root, quest_id, *, title=None, description=None,
  priority=None, auto_close=None) -> dict {id, filename: None}`
  (RENAME `edit_quest`; raises `ValueError` on miss / soft-deleted / invalid).
* `update_quest_full(...)`  (RENAME `edit_quest_full`).
* `delete_quest(project_root, quest_id, *, cascade=False) -> dict
  {id, deleted: True, deleted_at, cascade: list[str] | None}` — `already_deleted`
  key DROPPED per amendment Review Ledger; idempotent re-delete returns the
  same envelope (timestamp identifies the prior delete).

Validation: every `create_quest` / `update_quest` now raises `ValueError`
on invalid `priority` (drops the legacy `{ok: False, error: priority_err}`
return at db.py:1267-1270 + db.py:1446-1447).

These tests EXPECT the new symbols and shapes. They MUST fail until G17
Green lands them. NO production code in this chunk — Red phase only.
"""

from __future__ import annotations

import pytest

from tests.conftest import insert_mission, insert_quest


# ---------------------------------------------------------------------------
# Symbol existence — new names on lore.db
# ---------------------------------------------------------------------------


class TestNewQuestSymbolsExist:
    """All renamed db callables must appear under their new names."""

    @pytest.mark.parametrize(
        "name",
        ["read_quest", "update_quest", "update_quest_full"],
    )
    def test_new_quest_symbol_exists_on_lore_db(self, name):
        from lore import db

        assert hasattr(db, name), (
            f"G17: lore.db.{name} not defined yet (Red phase expected)"
        )
        assert callable(getattr(db, name))


# ---------------------------------------------------------------------------
# read_quest — dict | None (Row dropped per amendment Section B + A2)
# ---------------------------------------------------------------------------


class TestReadQuest:
    def test_returns_dict_for_existing_quest(self, project_dir):
        from lore.db import read_quest

        insert_quest(project_dir, "q-aaaa", "Hello")
        record = read_quest(project_dir, "q-aaaa")
        assert isinstance(record, dict), (
            "amendment A2 + Section B: read_quest must return dict, not sqlite3.Row"
        )
        # column-name keys preserved (same strings as today's Row keys)
        assert record["id"] == "q-aaaa"
        assert record["title"] == "Hello"

    def test_returns_none_for_missing_quest(self, project_dir):
        from lore.db import read_quest

        assert read_quest(project_dir, "q-9999") is None

    def test_returns_none_for_soft_deleted_quest(self, project_dir):
        from lore.db import read_quest

        insert_quest(
            project_dir,
            "q-dddd",
            "Gone",
            deleted_at="2025-02-01T00:00:00Z",
        )
        assert read_quest(project_dir, "q-dddd") is None

    def test_result_is_not_sqlite_row(self, project_dir):
        """F-READ-ROW-MIGRATION: drop Row positional access."""
        import sqlite3

        from lore.db import read_quest

        insert_quest(project_dir, "q-aaaa", "Hello")
        record = read_quest(project_dir, "q-aaaa")
        assert not isinstance(record, sqlite3.Row), (
            "amendment Section E breaking list: read_quest must NOT return Row"
        )

    def test_old_get_quest_name_removed_from_facade(self):
        """`get_quest` no longer in lore.api.__all__ (renamed to `read_quest`)."""
        from lore import api

        assert "get_quest" not in api.__all__, (
            "G17: `get_quest` must be dropped from lore.api.__all__ in favour of `read_quest`"
        )


# ---------------------------------------------------------------------------
# list_quests — list[dict] (Row dropped)
# ---------------------------------------------------------------------------


class TestListQuestsReturnsDicts:
    def test_returns_list_of_dicts(self, project_dir):
        from lore.db import list_quests

        insert_quest(project_dir, "q-aaaa", "A")
        insert_quest(project_dir, "q-bbbb", "B")

        rows = list_quests(project_dir)
        assert isinstance(rows, list)
        assert all(isinstance(r, dict) for r in rows), (
            "amendment Section B: list_quests must return list[dict] (was list[Row])"
        )

    def test_no_row_in_result(self, project_dir):
        import sqlite3

        from lore.db import list_quests

        insert_quest(project_dir, "q-aaaa", "A")
        rows = list_quests(project_dir)
        assert all(not isinstance(r, sqlite3.Row) for r in rows)


# ---------------------------------------------------------------------------
# create_quest — returns dict, not bare str
# ---------------------------------------------------------------------------


class TestCreateQuestReturnsDict:
    def test_create_quest_returns_dict_envelope(self, project_dir):
        from lore.db import create_quest

        result = create_quest(project_dir, "New quest")
        assert isinstance(result, dict), (
            "amendment Section B: create_quest must return dict (was bare str)"
        )

    def test_create_quest_envelope_keys_exact(self, project_dir):
        from lore.db import create_quest

        result = create_quest(project_dir, "New quest")
        # canonical create shape per amendment A2:
        # {"id": str, "filename": str | None, "group": str | None}
        assert set(result.keys()) == {"id", "filename", "group"}, (
            f"create_quest envelope MUST have EXACTLY "
            f"{{'id', 'filename', 'group'}}; got {sorted(result.keys())}"
        )

    def test_create_quest_filename_and_group_are_none(self, project_dir):
        """db-backed → no on-disk file; filename and group are None."""
        from lore.db import create_quest

        result = create_quest(project_dir, "New quest")
        assert result["filename"] is None
        assert result["group"] is None

    def test_create_quest_id_format(self, project_dir):
        from lore.db import create_quest

        result = create_quest(project_dir, "Quest title")
        qid = result["id"]
        assert qid.startswith("q-")
        # ID is the same shape produced today (q-<hex>)

    def test_create_quest_invalid_priority_raises_valueerror(self, project_dir):
        """A4: priority validation must raise (dropped {ok: False, ...} return)."""
        from lore.db import create_quest

        with pytest.raises(ValueError):
            create_quest(project_dir, "Bad priority", priority=99)


# ---------------------------------------------------------------------------
# update_quest — rename + raise-on-error (A2 + A4)
# ---------------------------------------------------------------------------


class TestUpdateQuestRaisesAndReturnsEnvelope:
    def test_update_quest_success_envelope_keys(self, project_dir):
        from lore.db import update_quest

        insert_quest(project_dir, "q-aaaa", "Old")
        result = update_quest(project_dir, "q-aaaa", title="New")
        assert isinstance(result, dict)
        assert "ok" not in result, (
            "amendment A2: update_quest success envelope MUST NOT include `ok`"
        )
        assert set(result.keys()) == {"id", "filename"}, (
            f"update_quest envelope MUST have EXACTLY {{'id', 'filename'}}; "
            f"got {sorted(result.keys())}"
        )

    def test_update_quest_filename_is_none(self, project_dir):
        from lore.db import update_quest

        insert_quest(project_dir, "q-aaaa", "Old")
        result = update_quest(project_dir, "q-aaaa", title="New")
        assert result["filename"] is None

    def test_update_quest_raises_valueerror_on_miss(self, project_dir):
        from lore.db import update_quest

        with pytest.raises(ValueError):
            update_quest(project_dir, "q-9999", title="X")

    def test_update_quest_raises_valueerror_on_soft_deleted(self, project_dir):
        from lore.db import update_quest

        insert_quest(
            project_dir,
            "q-dddd",
            "Old",
            deleted_at="2025-02-01T00:00:00Z",
        )
        with pytest.raises(ValueError):
            update_quest(project_dir, "q-dddd", title="X")

    def test_update_quest_raises_valueerror_on_invalid_priority(self, project_dir):
        from lore.db import update_quest

        insert_quest(project_dir, "q-aaaa", "Hello")
        with pytest.raises(ValueError):
            update_quest(project_dir, "q-aaaa", priority=99)

    def test_old_edit_quest_name_removed_from_facade(self):
        from lore import api

        assert "edit_quest" not in api.__all__, (
            "G17: `edit_quest` must be dropped from lore.api.__all__ in favour of `update_quest`"
        )


# ---------------------------------------------------------------------------
# update_quest_full — rename from edit_quest_full
# ---------------------------------------------------------------------------


class TestUpdateQuestFullSymbolPresent:
    def test_old_edit_quest_full_name_removed_from_facade(self):
        from lore import api

        assert "edit_quest_full" not in api.__all__, (
            "G17: `edit_quest_full` must be renamed to `update_quest_full`"
        )

    def test_update_quest_full_returns_envelope(self, project_dir):
        from lore.db import update_quest_full

        insert_quest(project_dir, "q-aaaa", "Old")
        data = update_quest_full(project_dir, "q-aaaa", title="New")
        assert isinstance(data, dict)
        assert "ok" not in data, (
            "amendment A2: update_quest_full success envelope MUST NOT include `ok`"
        )

    def test_update_quest_full_raises_on_miss(self, project_dir):
        from lore.db import update_quest_full

        with pytest.raises(ValueError):
            update_quest_full(project_dir, "q-9999", title="X")


# ---------------------------------------------------------------------------
# delete_quest — drop `already_deleted`, drop `ok`, raise on miss,
# idempotent re-delete returns same envelope.
# ---------------------------------------------------------------------------


DELETE_QUEST_KEYS_NO_CASCADE: frozenset[str] = frozenset(
    {"id", "deleted", "deleted_at", "cascade"}
)


class TestDeleteQuestEnvelopeHolistic:
    def test_delete_quest_envelope_keys_exact_no_cascade(self, project_dir):
        """Amendment A2: `{id, deleted: True, deleted_at, cascade: ... | None}` — no `ok`, no `already_deleted`."""
        from lore.db import delete_quest

        insert_quest(project_dir, "q-aaaa", "Hi")
        result = delete_quest(project_dir, "q-aaaa")
        assert set(result.keys()) == DELETE_QUEST_KEYS_NO_CASCADE, (
            f"delete_quest envelope MUST have EXACTLY "
            f"{sorted(DELETE_QUEST_KEYS_NO_CASCADE)}; got {sorted(result.keys())}"
        )

    def test_delete_quest_drops_already_deleted_key(self, project_dir):
        """Amendment Review Ledger CHANGED: `already_deleted` flag removed."""
        from lore.db import delete_quest

        insert_quest(project_dir, "q-aaaa", "Hi")
        result = delete_quest(project_dir, "q-aaaa")
        assert "already_deleted" not in result, (
            "amendment A2: `already_deleted` key removed from delete envelope"
        )

    def test_delete_quest_drops_ok_key(self, project_dir):
        from lore.db import delete_quest

        insert_quest(project_dir, "q-aaaa", "Hi")
        result = delete_quest(project_dir, "q-aaaa")
        assert "ok" not in result, (
            "amendment A2: delete envelope drops `ok` wrapper"
        )

    def test_delete_quest_positive_fields(self, project_dir):
        from lore.db import delete_quest

        insert_quest(project_dir, "q-aaaa", "Hi")
        result = delete_quest(project_dir, "q-aaaa")
        assert result["id"] == "q-aaaa"
        assert result["deleted"] is True
        assert isinstance(result["deleted_at"], str)
        # `cascade` is the list[str]|None field; cascade=False ⇒ None
        assert result["cascade"] is None

    def test_delete_quest_cascade_returns_list_key(self, project_dir):
        """`cascade=True` ⇒ `cascade` is a list[str]."""
        from lore.db import delete_quest

        insert_quest(project_dir, "q-aaaa", "Hi")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "M1")
        insert_mission(project_dir, "q-aaaa/m-2222", "q-aaaa", "M2")

        result = delete_quest(project_dir, "q-aaaa", cascade=True)
        assert isinstance(result["cascade"], list)
        assert set(result["cascade"]) == {"q-aaaa/m-1111", "q-aaaa/m-2222"}

    def test_delete_quest_raises_valueerror_on_unknown_id(self, project_dir):
        from lore.db import delete_quest

        with pytest.raises(ValueError):
            delete_quest(project_dir, "q-9999")

    def test_delete_quest_idempotent_returns_same_envelope(self, project_dir):
        """Idempotent re-delete returns the same envelope (no `already_deleted` flag).

        The pre-existing `deleted_at` timestamp distinguishes prior-deletion
        from a fresh delete — no boolean flag is needed (amendment A2).
        """
        from lore.db import delete_quest

        insert_quest(project_dir, "q-aaaa", "Hi")
        first = delete_quest(project_dir, "q-aaaa")
        second = delete_quest(project_dir, "q-aaaa")

        # Same key set; same id; deleted_at preserved (matches first call).
        assert set(second.keys()) == DELETE_QUEST_KEYS_NO_CASCADE
        assert second["id"] == "q-aaaa"
        assert second["deleted"] is True
        assert second["deleted_at"] == first["deleted_at"], (
            "Idempotent re-delete must preserve the original deleted_at timestamp"
        )
        assert "already_deleted" not in second
