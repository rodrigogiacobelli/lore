"""Red tests for G6: `lore.db.get_quest_detail` envelope.

Spec source:
  lore codex show transient-public-api-facade-plan      # §G6
  lore codex show transient-public-api-facade-tech-spec # §3

Envelope (per cli.py:2182-2202, byte-exact). EXPLICIT key set (NOT superset):
  {
    "id", "title", "description", "status", "priority",
    "created_at", "updated_at", "closed_at", "auto_close",
    "missions", "board",
  }

Per-mission entry shape (per cli.py:2167-2180):
  {"id", "title", "status", "priority", "mission_type", "knight", "dependencies"}
where dependencies = {"needs": [{id,title,status}, ...], "blocks": [...]}.

Review-Ledger CHANGED #2:
  * Missions in INSERTION ORDER (not topo). Topo sort is TEXT-only.
  * NO `parents` field anywhere in the JSON envelope.

These tests EXPECT `lore.db.get_quest_detail`. They MUST fail until G6 Green
lands. Red phase only — no production code.
"""

from __future__ import annotations


from tests.conftest import (
    insert_board_message,
    insert_dependency,
    insert_mission,
    insert_quest,
)


QUEST_DETAIL_KEYS: frozenset[str] = frozenset(
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
        "board",
    }
)

MISSION_ENTRY_KEYS: frozenset[str] = frozenset(
    {"id", "title", "status", "priority", "mission_type", "knight", "dependencies"}
)

DEP_REF_KEYS: frozenset[str] = frozenset({"id", "title", "status"})
BOARD_ENTRY_KEYS: frozenset[str] = frozenset({"id", "sender", "message", "created_at"})


# ---------------------------------------------------------------------------
# Symbol existence
# ---------------------------------------------------------------------------


def test_get_quest_detail_symbol_exists_on_lore_db():
    from lore import db

    assert hasattr(db, "get_quest_detail"), (
        "G6: lore.db.get_quest_detail not defined yet (Red phase expected)"
    )
    assert callable(db.get_quest_detail)


# ---------------------------------------------------------------------------
# Envelope shape — EXPLICIT keys + NO `parents`
# ---------------------------------------------------------------------------


class TestQuestDetailEnvelopeShape:
    def test_envelope_keys_exact_empty_quest(self, project_dir):
        from lore.db import get_quest_detail

        insert_quest(project_dir, "q-eeee", "Empty quest")

        data = get_quest_detail(project_dir, "q-eeee")
        assert data is not None
        assert set(data.keys()) == QUEST_DETAIL_KEYS, (
            f"Quest-detail envelope MUST have EXACTLY {sorted(QUEST_DETAIL_KEYS)}; "
            f"got {sorted(data.keys())} "
            f"(extra: {set(data.keys()) - QUEST_DETAIL_KEYS}, "
            f"missing: {QUEST_DETAIL_KEYS - set(data.keys())})"
        )
        assert data["missions"] == []
        assert data["board"] == []

    def test_envelope_has_no_parents_field(self, project_dir):
        """Review-Ledger CHANGED #2: NO `parents` field in JSON envelope."""
        from lore.db import get_quest_detail

        insert_quest(project_dir, "q-eeee", "Q")
        insert_mission(project_dir, "q-eeee/m-1111", "q-eeee", "A")
        insert_mission(project_dir, "q-eeee/m-2222", "q-eeee", "B")
        insert_dependency(project_dir, "q-eeee/m-2222", "q-eeee/m-1111")

        data = get_quest_detail(project_dir, "q-eeee")
        assert "parents" not in data, (
            "Review-Ledger CHANGED #2: top-level `parents` MUST NOT exist"
        )
        for m in data["missions"]:
            assert "parents" not in m, (
                f"per-mission `parents` MUST NOT exist; got mission with keys {sorted(m.keys())}"
            )

    def test_auto_close_is_bool(self, project_dir):
        """cli.py:2191 wraps in `bool(...)` — assert envelope-side."""
        from lore.db import get_quest_detail

        insert_quest(project_dir, "q-eeee", "Q", auto_close=1)

        data = get_quest_detail(project_dir, "q-eeee")
        assert isinstance(data["auto_close"], bool)
        assert data["auto_close"] is True

    def test_auto_close_false_when_zero(self, project_dir):
        from lore.db import get_quest_detail

        insert_quest(project_dir, "q-eeee", "Q", auto_close=0)

        data = get_quest_detail(project_dir, "q-eeee")
        assert data["auto_close"] is False


# ---------------------------------------------------------------------------
# Missing quest → None
# ---------------------------------------------------------------------------


class TestQuestDetailMiss:
    def test_returns_none_for_unknown_quest(self, project_dir):
        from lore.db import get_quest_detail

        assert get_quest_detail(project_dir, "q-9999") is None

    def test_returns_none_for_soft_deleted_quest(self, project_dir):
        from lore.db import get_quest_detail

        insert_quest(
            project_dir, "q-dddd", "Deleted Q",
            deleted_at="2025-02-01T00:00:00Z",
        )

        assert get_quest_detail(project_dir, "q-dddd") is None


# ---------------------------------------------------------------------------
# Missions ordering — INSERTION ORDER (NOT topological)
# ---------------------------------------------------------------------------


class TestQuestDetailMissionOrdering:
    def test_missions_in_insertion_order_not_topological(self, project_dir):
        """Review-Ledger CHANGED #2: order matches `get_missions_for_quest`
        (status-bucket + priority + created_at), NOT topo.
        """
        from lore.db import get_missions_for_quest, get_quest_detail

        insert_quest(project_dir, "q-eeee", "Q")
        # downstream first, upstream second; topo would put upstream first.
        insert_mission(
            project_dir, "q-eeee/m-aaa1", "q-eeee", "Downstream",
            created_at="2025-01-15T09:00:01Z",
        )
        insert_mission(
            project_dir, "q-eeee/m-aaa2", "q-eeee", "Upstream",
            created_at="2025-01-15T09:00:02Z",
        )
        # downstream needs upstream — topo would put aaa2 BEFORE aaa1
        insert_dependency(project_dir, "q-eeee/m-aaa1", "q-eeee/m-aaa2")

        data = get_quest_detail(project_dir, "q-eeee")
        ids = [m["id"] for m in data["missions"]]
        expected = [m["id"] for m in get_missions_for_quest(project_dir, "q-eeee")]
        assert ids == expected, (
            "Missions MUST follow `get_missions_for_quest` order (insertion / "
            "status-bucket / priority / created_at). Got topo order or other."
        )

    def test_soft_deleted_missions_excluded(self, project_dir):
        from lore.db import get_quest_detail

        insert_quest(project_dir, "q-eeee", "Q")
        insert_mission(project_dir, "q-eeee/m-aaa1", "q-eeee", "Alive")
        insert_mission(
            project_dir, "q-eeee/m-aaa2", "q-eeee", "Dead",
            deleted_at="2025-02-01T00:00:00Z",
        )

        data = get_quest_detail(project_dir, "q-eeee")
        ids = [m["id"] for m in data["missions"]]
        assert "q-eeee/m-aaa2" not in ids


# ---------------------------------------------------------------------------
# Per-mission entry shape — EXPLICIT keys
# ---------------------------------------------------------------------------


class TestQuestDetailMissionEntryShape:
    def test_mission_entry_keys_exact(self, project_dir):
        from lore.db import get_quest_detail

        insert_quest(project_dir, "q-eeee", "Q")
        insert_mission(
            project_dir, "q-eeee/m-aaa1", "q-eeee", "M",
            mission_type="knight", knight="some-knight.md",
        )

        data = get_quest_detail(project_dir, "q-eeee")
        assert len(data["missions"]) == 1
        m = data["missions"][0]
        assert set(m.keys()) == MISSION_ENTRY_KEYS, (
            f"Mission entry MUST have EXACTLY {sorted(MISSION_ENTRY_KEYS)}; "
            f"got {sorted(m.keys())} "
            f"(extra: {set(m.keys()) - MISSION_ENTRY_KEYS}, "
            f"missing: {MISSION_ENTRY_KEYS - set(m.keys())})"
        )
        assert m["mission_type"] == "knight"
        assert m["knight"] == "some-knight.md"

    def test_mission_entry_dependencies_subkeys(self, project_dir):
        from lore.db import get_quest_detail

        insert_quest(project_dir, "q-eeee", "Q")
        insert_mission(project_dir, "q-eeee/m-aaa1", "q-eeee", "Solo")

        data = get_quest_detail(project_dir, "q-eeee")
        deps = data["missions"][0]["dependencies"]
        assert set(deps.keys()) == {"needs", "blocks"}
        assert deps["needs"] == []
        assert deps["blocks"] == []

    def test_mission_dep_ref_shape_exact(self, project_dir):
        from lore.db import get_quest_detail

        insert_quest(project_dir, "q-eeee", "Q")
        insert_mission(project_dir, "q-eeee/m-aaa1", "q-eeee", "Downstream")
        insert_mission(
            project_dir, "q-eeee/m-aaa2", "q-eeee", "Upstream",
            status="open",
        )
        insert_dependency(project_dir, "q-eeee/m-aaa1", "q-eeee/m-aaa2")

        data = get_quest_detail(project_dir, "q-eeee")
        ms = {m["id"]: m for m in data["missions"]}
        needs = ms["q-eeee/m-aaa1"]["dependencies"]["needs"]
        assert len(needs) == 1
        entry = needs[0]
        assert set(entry.keys()) == DEP_REF_KEYS, (
            f"per-mission dependency ref MUST have EXACTLY {sorted(DEP_REF_KEYS)}; "
            f"got {sorted(entry.keys())}"
        )
        assert entry["id"] == "q-eeee/m-aaa2"
        assert entry["title"] == "Upstream"
        assert entry["status"] == "open"


# ---------------------------------------------------------------------------
# Board
# ---------------------------------------------------------------------------


class TestQuestDetailBoard:
    def test_board_entry_keys_exact(self, project_dir):
        from lore.db import get_quest_detail

        insert_quest(project_dir, "q-eeee", "Q")
        insert_board_message(project_dir, "q-eeee", "kickoff", sender="alice")

        data = get_quest_detail(project_dir, "q-eeee")
        assert len(data["board"]) == 1
        entry = data["board"][0]
        assert set(entry.keys()) == BOARD_ENTRY_KEYS
        assert entry["sender"] == "alice"
        assert entry["message"] == "kickoff"
