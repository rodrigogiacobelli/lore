"""Tests for `lore.db.update_quest_full` + `lore.db.update_mission_full`.

Spec source:
  lore codex show transient-public-api-facade-plan              # §G17
  lore codex show transient-public-api-facade-create-stdz       # §A2 §A4 §B

G17 BREAKING rename (per amendment Section B):
* `edit_quest_full`   -> `update_quest_full`
* `edit_mission_full` -> `update_mission_full`

G17 error contract (amendment A4): operational layer raises ``ValueError``
on every failure path; CLI translator catches and renders. Old
``{ok: False, error, deleted_at?}`` envelope is gone.

`update_quest_full` success (per cli.py:1648-1670). EXPLICIT keys:
  {
    "id", "title", "description", "status", "priority",
    "created_at", "updated_at", "closed_at", "auto_close",
    "missions",
  }
where each mission entry has EXACTLY:
  {"id", "title", "status", "priority", "mission_type", "knight"}.

`update_mission_full` success (per cli.py:1712-1740). EXPLICIT keys:
  {
    "id", "quest_id", "title", "description", "status", "priority",
    "knight", "mission_type", "block_reason",
    "created_at", "updated_at", "closed_at",
    "dependencies",
  }
where dependencies = {"needs": [...], "blocks": [...]} (list[str] of mission IDs).
"""

from __future__ import annotations

import pytest

from tests.conftest import insert_dependency, insert_mission, insert_quest


# ---------------------------------------------------------------------------
# Envelope key sets
# ---------------------------------------------------------------------------


QUEST_FULL_SUCCESS_KEYS: frozenset[str] = frozenset(
    {
        "id",
        "title",
        "description",
        "status",
        "priority",
        "created_at",
        "updated_at",
        "closed_at",
        "auto_close",
        "missions",
    }
)

QUEST_FULL_MISSION_ENTRY_KEYS: frozenset[str] = frozenset(
    {"id", "title", "status", "priority", "mission_type", "knight"}
)

MISSION_FULL_SUCCESS_KEYS: frozenset[str] = frozenset(
    {
        "id",
        "quest_id",
        "title",
        "description",
        "status",
        "priority",
        "knight",
        "mission_type",
        "block_reason",
        "created_at",
        "updated_at",
        "closed_at",
        "dependencies",
    }
)


# ===========================================================================
# update_quest_full
# ===========================================================================


def test_update_quest_full_symbol_exists_on_lore_db():
    from lore import db

    assert hasattr(db, "update_quest_full"), (
        "G17: lore.db.update_quest_full not defined (rename from edit_quest_full)"
    )
    assert callable(db.update_quest_full)


class TestUpdateQuestFullSuccessEnvelope:
    def test_keys_exact_on_success(self, project_dir):
        from lore.db import update_quest_full

        insert_quest(project_dir, "q-aaaa", "Old", priority=2, auto_close=0)

        data = update_quest_full(project_dir, "q-aaaa", title="New title")
        # success envelope has NO `ok` key per cli.py:1648-1670
        assert "ok" not in data, (
            "update_quest_full success envelope MUST NOT include `ok` "
            "(cli.py:1648-1670 emits the dict directly)"
        )
        assert set(data.keys()) == QUEST_FULL_SUCCESS_KEYS, (
            f"update_quest_full success keys MUST be EXACTLY "
            f"{sorted(QUEST_FULL_SUCCESS_KEYS)}; got {sorted(data.keys())} "
            f"(extra: {set(data.keys()) - QUEST_FULL_SUCCESS_KEYS}, "
            f"missing: {QUEST_FULL_SUCCESS_KEYS - set(data.keys())})"
        )

    def test_title_applied(self, project_dir):
        from lore.db import update_quest_full

        insert_quest(project_dir, "q-aaaa", "Old")
        data = update_quest_full(project_dir, "q-aaaa", title="Shiny")
        assert data["title"] == "Shiny"

    def test_priority_applied(self, project_dir):
        from lore.db import update_quest_full

        insert_quest(project_dir, "q-aaaa", "Q", priority=2)
        data = update_quest_full(project_dir, "q-aaaa", priority=0)
        assert data["priority"] == 0

    def test_auto_close_is_bool(self, project_dir):
        """cli.py:1657 wraps in `bool(...)`."""
        from lore.db import update_quest_full

        insert_quest(project_dir, "q-aaaa", "Q", auto_close=1)
        data = update_quest_full(project_dir, "q-aaaa", title="x")
        assert isinstance(data["auto_close"], bool)
        assert data["auto_close"] is True

    def test_missions_list_entry_keys_exact(self, project_dir):
        from lore.db import update_quest_full

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(
            project_dir, "q-aaaa/m-1111", "q-aaaa", "M",
            mission_type="knight", knight="someone.md",
        )

        data = update_quest_full(project_dir, "q-aaaa", title="x")
        assert len(data["missions"]) == 1
        m = data["missions"][0]
        assert set(m.keys()) == QUEST_FULL_MISSION_ENTRY_KEYS, (
            f"Mission entry in update_quest_full MUST have EXACTLY "
            f"{sorted(QUEST_FULL_MISSION_ENTRY_KEYS)}; got {sorted(m.keys())}"
        )

    def test_missions_entry_has_no_dependencies_subkey(self, project_dir):
        """cli.py:1658-1668 does NOT embed `dependencies` in edit-quest envelope."""
        from lore.db import update_quest_full

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "M")

        data = update_quest_full(project_dir, "q-aaaa", title="x")
        assert "dependencies" not in data["missions"][0]


class TestUpdateQuestFullRaisesOnError:
    """G17 amendment A4: operational layer raises on every error path."""

    def test_missing_quest_raises_valueerror(self, project_dir):
        from lore.db import update_quest_full

        with pytest.raises(ValueError) as excinfo:
            update_quest_full(project_dir, "q-zzzz", title="x")
        assert "q-zzzz" in str(excinfo.value)

    def test_deleted_quest_raises_with_deleted_at_in_message(self, project_dir):
        from lore.db import update_quest_full

        insert_quest(
            project_dir, "q-aaaa", "Q",
            deleted_at="2025-02-01T00:00:00Z",
        )

        with pytest.raises(ValueError) as excinfo:
            update_quest_full(project_dir, "q-aaaa", title="x")
        # G17: error message text is identical to G6 — just raises instead of return.
        assert "2025-02-01T00:00:00Z" in str(excinfo.value)


# ===========================================================================
# update_mission_full
# ===========================================================================


def test_update_mission_full_symbol_exists_on_lore_db():
    from lore import db

    assert hasattr(db, "update_mission_full"), (
        "G17: lore.db.update_mission_full not defined (rename from edit_mission_full)"
    )
    assert callable(db.update_mission_full)


class TestUpdateMissionFullSuccessEnvelope:
    def test_keys_exact_on_success(self, project_dir):
        from lore.db import update_mission_full

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "Old title")

        data = update_mission_full(project_dir, "q-aaaa/m-1111", title="New")
        assert "ok" not in data, (
            "update_mission_full success envelope MUST NOT include `ok` "
            "(cli.py:1716-1734 emits the dict directly)"
        )
        assert set(data.keys()) == MISSION_FULL_SUCCESS_KEYS, (
            f"update_mission_full success keys MUST be EXACTLY "
            f"{sorted(MISSION_FULL_SUCCESS_KEYS)}; got {sorted(data.keys())} "
            f"(extra: {set(data.keys()) - MISSION_FULL_SUCCESS_KEYS}, "
            f"missing: {MISSION_FULL_SUCCESS_KEYS - set(data.keys())})"
        )

    def test_dependencies_subkeys_exact(self, project_dir):
        from lore.db import update_mission_full

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "M")

        data = update_mission_full(project_dir, "q-aaaa/m-1111", title="x")
        deps = data["dependencies"]
        assert set(deps.keys()) == {"needs", "blocks"}
        assert deps["needs"] == []
        assert deps["blocks"] == []

    def test_dependencies_needs_lists_upstream_ids(self, project_dir):
        """cli.py:1729-1732 passes the result of the dependency-id projector
        THROUGH — list[str] of mission IDs.
        """
        from lore.db import update_mission_full

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "Downstream")
        insert_mission(project_dir, "q-aaaa/m-2222", "q-aaaa", "Upstream")
        insert_dependency(project_dir, "q-aaaa/m-1111", "q-aaaa/m-2222")

        data = update_mission_full(project_dir, "q-aaaa/m-1111", title="x")
        assert data["dependencies"]["needs"] == ["q-aaaa/m-2222"]

    def test_dependencies_blocks_lists_downstream_ids(self, project_dir):
        from lore.db import update_mission_full

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "Upstream")
        insert_mission(project_dir, "q-aaaa/m-2222", "q-aaaa", "Downstream")
        insert_dependency(project_dir, "q-aaaa/m-2222", "q-aaaa/m-1111")

        data = update_mission_full(project_dir, "q-aaaa/m-1111", title="x")
        assert data["dependencies"]["blocks"] == ["q-aaaa/m-2222"]

    def test_remove_knight_clears_knight(self, project_dir):
        from lore.db import update_mission_full

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(
            project_dir, "q-aaaa/m-1111", "q-aaaa", "M",
            knight="someone.md",
        )

        data = update_mission_full(
            project_dir, "q-aaaa/m-1111", remove_knight=True,
        )
        assert data["knight"] is None

    def test_mission_type_applied(self, project_dir):
        from lore.db import update_mission_full

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "M")

        data = update_mission_full(
            project_dir, "q-aaaa/m-1111", mission_type="constable",
        )
        assert data["mission_type"] == "constable"


class TestUpdateMissionFullRaisesOnError:
    """G17 amendment A4: operational layer raises on every error path."""

    def test_missing_mission_raises_valueerror(self, project_dir):
        from lore.db import update_mission_full

        with pytest.raises(ValueError) as excinfo:
            update_mission_full(project_dir, "q-aaaa/m-9999", title="x")
        assert "q-aaaa/m-9999" in str(excinfo.value)

    def test_deleted_mission_raises_with_deleted_at_in_message(self, project_dir):
        from lore.db import update_mission_full

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(
            project_dir, "q-aaaa/m-1111", "q-aaaa", "Dead",
            deleted_at="2025-02-01T00:00:00Z",
        )

        with pytest.raises(ValueError) as excinfo:
            update_mission_full(project_dir, "q-aaaa/m-1111", title="x")
        assert "2025-02-01T00:00:00Z" in str(excinfo.value)
