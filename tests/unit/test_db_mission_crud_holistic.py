"""Red tests for G17: holistic db-backed CRUD sweep — mission slice.

Spec sources:
  lore codex show transient-public-api-facade-plan              # §G17
  lore codex show transient-public-api-facade-create-stdz       # §A1 §A2 §A4 §B

Mission contracts (matches the quest slice — mirror by row in amendment §B):

* `read_mission(project_root, mission_id) -> dict | None`  (RENAME `get_mission`).
* `list_missions(project_root, *, quest_id=None, include_closed=False, ...)
  -> dict[str | None, list[dict]]`  — Rows inside the grouped dict are dicts.
* `create_mission(project_root, title, *, quest_id=None, ...) -> dict
  {id, filename: None, group: None}`  (was bare `str`).
* `update_mission(...)`  (RENAME `edit_mission`); raises on miss / soft-deleted /
  invalid priority; positive envelope `{id, filename: None}`.
* `update_mission_full(...)`  (RENAME `edit_mission_full`).
* `delete_mission(project_root, mission_id) -> dict {id, deleted: True,
  deleted_at}` — drops `already_deleted`, drops `ok`, raises on unknown id.

Inferred-parent-quest (canonical FLAG #4): `create_mission(root, "title")` with
no `quest_id` still auto-attaches to the sole open quest. Behaviour landed in
G12; G17 only changes the return wrapper (dict, not str).

These tests EXPECT the new symbols and shapes. They MUST fail until G17
Green lands. NO production code in this chunk — Red phase only.
"""

from __future__ import annotations

import pytest

from tests.conftest import insert_mission, insert_quest


# ---------------------------------------------------------------------------
# Symbol existence
# ---------------------------------------------------------------------------


class TestNewMissionSymbolsExist:
    @pytest.mark.parametrize(
        "name",
        ["read_mission", "update_mission", "update_mission_full"],
    )
    def test_new_mission_symbol_exists_on_lore_db(self, name):
        from lore import db

        assert hasattr(db, name), (
            f"G17: lore.db.{name} not defined yet (Red phase expected)"
        )
        assert callable(getattr(db, name))


# ---------------------------------------------------------------------------
# read_mission — dict | None
# ---------------------------------------------------------------------------


class TestReadMission:
    def test_returns_dict_for_existing_mission(self, project_dir):
        from lore.db import read_mission

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "Hello")
        record = read_mission(project_dir, "q-aaaa/m-1111")
        assert isinstance(record, dict)
        assert record["id"] == "q-aaaa/m-1111"
        assert record["title"] == "Hello"

    def test_returns_none_for_missing_mission(self, project_dir):
        from lore.db import read_mission

        assert read_mission(project_dir, "m-9999") is None

    def test_returns_none_for_soft_deleted_mission(self, project_dir):
        from lore.db import read_mission

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(
            project_dir,
            "q-aaaa/m-dddd",
            "q-aaaa",
            "Gone",
            deleted_at="2025-02-01T00:00:00Z",
        )
        assert read_mission(project_dir, "q-aaaa/m-dddd") is None

    def test_result_is_not_sqlite_row(self, project_dir):
        import sqlite3

        from lore.db import read_mission

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "Hello")
        record = read_mission(project_dir, "q-aaaa/m-1111")
        assert not isinstance(record, sqlite3.Row)

    def test_old_get_mission_name_removed_from_facade(self):
        from lore import api

        assert "get_mission" not in api.__all__, (
            "G17: `get_mission` must be dropped from lore.api.__all__"
        )


# ---------------------------------------------------------------------------
# list_missions — inner lists become list[dict]
# ---------------------------------------------------------------------------


class TestListMissionsReturnsDicts:
    def test_inner_rows_are_dicts(self, project_dir):
        import sqlite3

        from lore.db import list_missions

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "A")
        insert_mission(project_dir, "q-aaaa/m-2222", "q-aaaa", "B")

        grouped = list_missions(project_dir)
        # grouped is a dict mapping quest_id (or None) to a list of rows
        all_rows: list = []
        for v in grouped.values():
            all_rows.extend(v)
        assert all(isinstance(r, dict) for r in all_rows), (
            "amendment Section B: list_missions inner rows must be dicts (was Row)"
        )
        assert all(not isinstance(r, sqlite3.Row) for r in all_rows)


# ---------------------------------------------------------------------------
# create_mission — dict envelope, inferred-parent preserved
# ---------------------------------------------------------------------------


class TestCreateMissionReturnsDict:
    def test_create_mission_returns_dict_envelope(self, project_dir):
        from lore.db import create_mission

        insert_quest(project_dir, "q-aaaa", "Q")
        result = create_mission(project_dir, "New mission", quest_id="q-aaaa")
        assert isinstance(result, dict), (
            "amendment Section B: create_mission must return dict (was bare str)"
        )

    def test_create_mission_envelope_keys_exact(self, project_dir):
        from lore.db import create_mission

        insert_quest(project_dir, "q-aaaa", "Q")
        result = create_mission(project_dir, "New mission", quest_id="q-aaaa")
        assert set(result.keys()) == {"id", "filename", "group"}, (
            f"create_mission envelope MUST have EXACTLY "
            f"{{'id', 'filename', 'group'}}; got {sorted(result.keys())}"
        )

    def test_create_mission_filename_and_group_are_none(self, project_dir):
        from lore.db import create_mission

        insert_quest(project_dir, "q-aaaa", "Q")
        result = create_mission(project_dir, "New mission", quest_id="q-aaaa")
        assert result["filename"] is None
        assert result["group"] is None

    def test_create_mission_id_has_quest_prefix(self, project_dir):
        from lore.db import create_mission

        insert_quest(project_dir, "q-aaaa", "Q")
        result = create_mission(project_dir, "New mission", quest_id="q-aaaa")
        assert result["id"].startswith("q-aaaa/m-")

    def test_create_mission_inferred_parent_quest_preserved(self, project_dir):
        """G12 behaviour: with exactly one open quest, no quest_id auto-attaches.

        After G17, return is a dict, but the inference logic survives.
        """
        from lore.db import create_mission

        insert_quest(project_dir, "q-aaaa", "Sole open quest")
        result = create_mission(project_dir, "Inferred mission")
        assert isinstance(result, dict)
        assert result["id"].startswith("q-aaaa/m-"), (
            "G12 inferred-parent-quest behaviour must survive the G17 dict-return flip"
        )

    def test_create_mission_invalid_priority_raises_valueerror(self, project_dir):
        from lore.db import create_mission

        insert_quest(project_dir, "q-aaaa", "Q")
        with pytest.raises(ValueError):
            create_mission(
                project_dir, "Bad priority", quest_id="q-aaaa", priority=99
            )


# ---------------------------------------------------------------------------
# update_mission — rename + raise + positive envelope
# ---------------------------------------------------------------------------


class TestUpdateMissionRaisesAndReturnsEnvelope:
    def test_update_mission_success_envelope_keys(self, project_dir):
        from lore.db import update_mission

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "Old")
        result = update_mission(project_dir, "q-aaaa/m-1111", title="New")
        assert isinstance(result, dict)
        assert "ok" not in result
        assert set(result.keys()) == {"id", "filename"}, (
            f"update_mission envelope MUST have EXACTLY {{'id', 'filename'}}; "
            f"got {sorted(result.keys())}"
        )
        assert result["filename"] is None
        assert result["id"] == "q-aaaa/m-1111"

    def test_update_mission_raises_valueerror_on_miss(self, project_dir):
        from lore.db import update_mission

        with pytest.raises(ValueError):
            update_mission(project_dir, "m-9999", title="X")

    def test_update_mission_raises_valueerror_on_soft_deleted(self, project_dir):
        from lore.db import update_mission

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(
            project_dir,
            "q-aaaa/m-dddd",
            "q-aaaa",
            "Gone",
            deleted_at="2025-02-01T00:00:00Z",
        )
        with pytest.raises(ValueError):
            update_mission(project_dir, "q-aaaa/m-dddd", title="X")

    def test_update_mission_raises_valueerror_on_invalid_priority(self, project_dir):
        from lore.db import update_mission

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "Hello")
        with pytest.raises(ValueError):
            update_mission(project_dir, "q-aaaa/m-1111", priority=99)

    def test_old_edit_mission_name_removed_from_facade(self):
        from lore import api

        assert "edit_mission" not in api.__all__, (
            "G17: `edit_mission` must be dropped from lore.api.__all__"
        )


# ---------------------------------------------------------------------------
# update_mission_full — rename
# ---------------------------------------------------------------------------


class TestUpdateMissionFull:
    def test_old_edit_mission_full_name_removed_from_facade(self):
        from lore import api

        assert "edit_mission_full" not in api.__all__, (
            "G17: `edit_mission_full` must be renamed to `update_mission_full`"
        )

    def test_update_mission_full_returns_envelope(self, project_dir):
        from lore.db import update_mission_full

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "Old")
        data = update_mission_full(project_dir, "q-aaaa/m-1111", title="New")
        assert isinstance(data, dict)
        assert "ok" not in data

    def test_update_mission_full_raises_on_miss(self, project_dir):
        from lore.db import update_mission_full

        with pytest.raises(ValueError):
            update_mission_full(project_dir, "m-9999", title="X")


# ---------------------------------------------------------------------------
# delete_mission — drop `already_deleted`, drop `ok`, raise on miss,
# idempotent re-delete returns same envelope.
# ---------------------------------------------------------------------------


DELETE_MISSION_KEYS: frozenset[str] = frozenset({"id", "deleted", "deleted_at"})


class TestDeleteMissionEnvelopeHolistic:
    def test_delete_mission_envelope_keys_exact(self, project_dir):
        from lore.db import delete_mission

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "Hi")
        result = delete_mission(project_dir, "q-aaaa/m-1111")
        assert set(result.keys()) == DELETE_MISSION_KEYS, (
            f"delete_mission envelope MUST have EXACTLY "
            f"{sorted(DELETE_MISSION_KEYS)}; got {sorted(result.keys())}"
        )

    def test_delete_mission_drops_already_deleted(self, project_dir):
        from lore.db import delete_mission

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "Hi")
        result = delete_mission(project_dir, "q-aaaa/m-1111")
        assert "already_deleted" not in result

    def test_delete_mission_drops_ok(self, project_dir):
        from lore.db import delete_mission

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "Hi")
        result = delete_mission(project_dir, "q-aaaa/m-1111")
        assert "ok" not in result

    def test_delete_mission_positive_fields(self, project_dir):
        from lore.db import delete_mission

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "Hi")
        result = delete_mission(project_dir, "q-aaaa/m-1111")
        assert result["id"] == "q-aaaa/m-1111"
        assert result["deleted"] is True
        assert isinstance(result["deleted_at"], str)

    def test_delete_mission_raises_valueerror_on_unknown_id(self, project_dir):
        from lore.db import delete_mission

        with pytest.raises(ValueError):
            delete_mission(project_dir, "m-9999")

    def test_delete_mission_idempotent_returns_same_envelope(self, project_dir):
        from lore.db import delete_mission

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "Hi")
        first = delete_mission(project_dir, "q-aaaa/m-1111")
        second = delete_mission(project_dir, "q-aaaa/m-1111")
        assert set(second.keys()) == DELETE_MISSION_KEYS
        assert second["id"] == "q-aaaa/m-1111"
        assert second["deleted"] is True
        assert second["deleted_at"] == first["deleted_at"]
        assert "already_deleted" not in second
