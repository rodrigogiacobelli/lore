"""Tests for `lore.db.delete_entity` unified delete envelope.

Spec source:
  lore codex show transient-public-api-facade-plan              # §G17
  lore codex show transient-public-api-facade-create-stdz       # §A2 §B

Routing happens via `lore.validators.route_entity`. CLI top-level `delete`
becomes a one-liner per Spec §7.

G17 BREAKING (amendment A2): every delete returns a positive envelope.

Quest envelope (no cascade): {id, deleted: True, deleted_at, cascade: None}
Quest envelope (cascade=True): {id, deleted: True, deleted_at, cascade: list[str]}
Mission envelope: {id, deleted: True, deleted_at}

Error contract (amendment A4): unknown IDs raise ``ValueError``.
``already_deleted`` flag is DROPPED (amendment Review Ledger CHANGED);
idempotent re-delete returns the same envelope with the prior ``deleted_at``.
"""

from __future__ import annotations

import pytest

from tests.conftest import insert_mission, insert_quest


# ---------------------------------------------------------------------------
# Symbol existence
# ---------------------------------------------------------------------------


def test_delete_entity_symbol_exists_on_lore_db():
    from lore import db

    assert hasattr(db, "delete_entity")
    assert callable(db.delete_entity)


# ---------------------------------------------------------------------------
# Quest deletion — no cascade
# ---------------------------------------------------------------------------


class TestDeleteEntityQuestNoCascade:
    def test_success_envelope_keys_exact(self, project_dir):
        from lore.db import delete_entity

        insert_quest(project_dir, "q-aaaa", "Q")

        result = delete_entity(project_dir, "q-aaaa")
        assert set(result.keys()) == {"id", "deleted", "deleted_at", "cascade"}, (
            f"Quest delete (no cascade) envelope MUST be EXACTLY "
            f"{{id, deleted, deleted_at, cascade}}; got {sorted(result.keys())}"
        )
        assert result["id"] == "q-aaaa"
        assert result["deleted"] is True
        assert isinstance(result["deleted_at"], str) and result["deleted_at"]
        # cascade=False ⇒ cascade is None
        assert result["cascade"] is None

    def test_cascade_none_when_cascade_false(self, project_dir):
        from lore.db import delete_entity

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "M")

        result = delete_entity(project_dir, "q-aaaa", cascade=False)
        assert result["cascade"] is None


# ---------------------------------------------------------------------------
# Quest deletion — cascade
# ---------------------------------------------------------------------------


class TestDeleteEntityQuestCascade:
    def test_cascade_true_envelope_keys_exact(self, project_dir):
        from lore.db import delete_entity

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "M")

        result = delete_entity(project_dir, "q-aaaa", cascade=True)
        assert set(result.keys()) == {"id", "deleted", "deleted_at", "cascade"}
        assert isinstance(result["cascade"], list)
        assert "q-aaaa/m-1111" in result["cascade"]

    def test_cascade_empty_list_when_no_missions(self, project_dir):
        from lore.db import delete_entity

        insert_quest(project_dir, "q-aaaa", "Q")
        result = delete_entity(project_dir, "q-aaaa", cascade=True)
        assert result["cascade"] == []


# ---------------------------------------------------------------------------
# Quest idempotent re-delete — no `already_deleted` flag (amendment A2)
# ---------------------------------------------------------------------------


class TestDeleteEntityQuestIdempotent:
    def test_re_delete_returns_same_envelope(self, project_dir):
        from lore.db import delete_entity

        insert_quest(
            project_dir, "q-aaaa", "Q",
            deleted_at="2025-02-01T00:00:00Z",
        )

        result = delete_entity(project_dir, "q-aaaa")
        # New envelope: positive shape with prior timestamp; no `already_deleted` key.
        assert "already_deleted" not in result
        assert "ok" not in result
        assert result["id"] == "q-aaaa"
        assert result["deleted"] is True
        assert result["deleted_at"] == "2025-02-01T00:00:00Z"


# ---------------------------------------------------------------------------
# Quest error — unknown
# ---------------------------------------------------------------------------


class TestDeleteEntityQuestError:
    def test_unknown_quest_raises_valueerror(self, project_dir):
        from lore.db import delete_entity

        with pytest.raises(ValueError) as excinfo:
            delete_entity(project_dir, "q-9999")
        assert "q-9999" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Mission deletion
# ---------------------------------------------------------------------------


class TestDeleteEntityMission:
    def test_success_envelope_keys_exact(self, project_dir):
        from lore.db import delete_entity

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "M")

        result = delete_entity(project_dir, "q-aaaa/m-1111")
        assert set(result.keys()) == {"id", "deleted", "deleted_at"}, (
            f"Mission delete envelope MUST be EXACTLY "
            f"{{id, deleted, deleted_at}}; got {sorted(result.keys())}"
        )
        assert result["id"] == "q-aaaa/m-1111"
        assert result["deleted"] is True

    def test_idempotent_re_delete_returns_same_envelope(self, project_dir):
        from lore.db import delete_entity

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(
            project_dir, "q-aaaa/m-1111", "q-aaaa", "M",
            deleted_at="2025-02-01T00:00:00Z",
        )

        result = delete_entity(project_dir, "q-aaaa/m-1111")
        assert "already_deleted" not in result
        assert "ok" not in result
        assert result["id"] == "q-aaaa/m-1111"
        assert result["deleted"] is True
        assert result["deleted_at"] == "2025-02-01T00:00:00Z"

    def test_unknown_mission_raises_valueerror(self, project_dir):
        from lore.db import delete_entity

        with pytest.raises(ValueError) as excinfo:
            delete_entity(project_dir, "q-aaaa/m-9999")
        assert "q-aaaa/m-9999" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Routing — uses route_entity internally (verified by ValueError on bad ID)
# ---------------------------------------------------------------------------


class TestDeleteEntityRouting:
    def test_unroutable_id_raises_value_error(self, project_dir):
        """delete_entity MUST use `lore.validators.route_entity` to dispatch.

        `route_entity` raises ValueError for IDs that match NEITHER pattern.
        Caller (CLI) is responsible for translating to its UX message.
        """
        from lore.db import delete_entity

        with pytest.raises(ValueError):
            delete_entity(project_dir, "garbage-id-shape")
