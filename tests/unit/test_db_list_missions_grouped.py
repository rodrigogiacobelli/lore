"""Red tests for G6: `lore.db.list_missions_grouped` envelope.

Spec source:
  lore codex show transient-public-api-facade-plan      # §G6
  lore codex show transient-public-api-facade-tech-spec # §2 ("missions" row)

Envelope (per Tech Spec §2):
  {
    "groups": [
      {
        "quest_id": str | None,
        "quest_title": str | None,
        "quest_deleted_at": str | None,
        "missions": [
          {
            "id", "quest_id", "title", "status", "priority",
            "mission_type", "knight", "created_at",
          },
          ...
        ],
      },
      ...
    ],
  }

Per-mission keys mirror cli.py:946-960 (the `flat` builder).

Behaviour:
  * `quest_id=None` (default) returns every quest's missions grouped + a
    standalone group for `quest_id=None` missions.
  * `quest_id="q-..."` scopes to one quest.
  * `include_closed=False` (default) excludes status='closed'.
  * `include_closed=True` includes closed missions.
  * `quest_deleted_at` annotates standalone-mission groups too (None there).

These tests EXPECT `lore.db.list_missions_grouped`. Red phase only.
"""

from __future__ import annotations


from tests.conftest import insert_mission, insert_quest


ENVELOPE_KEYS: frozenset[str] = frozenset({"groups"})

GROUP_KEYS: frozenset[str] = frozenset(
    {"quest_id", "quest_title", "quest_deleted_at", "missions"}
)

MISSION_ENTRY_KEYS: frozenset[str] = frozenset(
    {
        "id",
        "quest_id",
        "title",
        "status",
        "priority",
        "mission_type",
        "knight",
        "created_at",
    }
)


# ---------------------------------------------------------------------------
# Symbol existence
# ---------------------------------------------------------------------------


def test_list_missions_grouped_symbol_exists_on_lore_db():
    from lore import db

    assert hasattr(db, "list_missions_grouped"), (
        "G6: lore.db.list_missions_grouped not defined yet (Red phase expected)"
    )
    assert callable(db.list_missions_grouped)


# ---------------------------------------------------------------------------
# Envelope shape
# ---------------------------------------------------------------------------


class TestListMissionsGroupedEnvelopeShape:
    def test_envelope_keys_exact_on_empty_project(self, project_dir):
        from lore.db import list_missions_grouped

        result = list_missions_grouped(project_dir)
        assert set(result.keys()) == ENVELOPE_KEYS, (
            f"Envelope MUST have EXACTLY {sorted(ENVELOPE_KEYS)}; "
            f"got {sorted(result.keys())}"
        )
        assert result["groups"] == []

    def test_group_keys_exact_for_quest_bound_missions(self, project_dir):
        from lore.db import list_missions_grouped

        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "M1")

        result = list_missions_grouped(project_dir)
        assert len(result["groups"]) == 1
        group = result["groups"][0]
        assert set(group.keys()) == GROUP_KEYS, (
            f"Group MUST have EXACTLY {sorted(GROUP_KEYS)}; "
            f"got {sorted(group.keys())} "
            f"(extra: {set(group.keys()) - GROUP_KEYS}, "
            f"missing: {GROUP_KEYS - set(group.keys())})"
        )

    def test_mission_entry_keys_exact(self, project_dir):
        from lore.db import list_missions_grouped

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(
            project_dir, "q-aaaa/m-1111", "q-aaaa", "M",
            mission_type="knight", knight="someone.md",
        )

        result = list_missions_grouped(project_dir)
        m = result["groups"][0]["missions"][0]
        assert set(m.keys()) == MISSION_ENTRY_KEYS, (
            f"Mission entry MUST have EXACTLY {sorted(MISSION_ENTRY_KEYS)}; "
            f"got {sorted(m.keys())}"
        )


# ---------------------------------------------------------------------------
# Quest-title / quest_deleted_at annotation
# ---------------------------------------------------------------------------


class TestListMissionsGroupedAnnotations:
    def test_quest_title_populated_for_alive_quest(self, project_dir):
        from lore.db import list_missions_grouped

        insert_quest(project_dir, "q-aaaa", "Hello Quest")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "M")

        result = list_missions_grouped(project_dir)
        group = next(g for g in result["groups"] if g["quest_id"] == "q-aaaa")
        assert group["quest_title"] == "Hello Quest"
        assert group["quest_deleted_at"] is None

    def test_quest_deleted_at_populated_when_quest_soft_deleted(self, project_dir):
        from lore.db import list_missions_grouped

        insert_quest(
            project_dir, "q-aaaa", "Q",
            deleted_at="2025-02-01T00:00:00Z",
        )
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "M")

        result = list_missions_grouped(project_dir)
        group = next(g for g in result["groups"] if g["quest_id"] == "q-aaaa")
        assert group["quest_deleted_at"] == "2025-02-01T00:00:00Z"

    def test_standalone_group_has_none_quest_fields(self, project_dir):
        from lore.db import list_missions_grouped

        insert_mission(project_dir, "m-2222", None, "Standalone")

        result = list_missions_grouped(project_dir)
        groups = [g for g in result["groups"] if g["quest_id"] is None]
        assert len(groups) == 1
        sg = groups[0]
        assert sg["quest_id"] is None
        assert sg["quest_title"] is None
        assert sg["quest_deleted_at"] is None
        assert len(sg["missions"]) == 1
        assert sg["missions"][0]["id"] == "m-2222"


# ---------------------------------------------------------------------------
# Scoping by quest_id
# ---------------------------------------------------------------------------


class TestListMissionsGroupedScoping:
    def test_quest_id_scopes_to_single_quest(self, project_dir):
        from lore.db import list_missions_grouped

        insert_quest(project_dir, "q-aaaa", "A")
        insert_quest(project_dir, "q-bbbb", "B")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "MA")
        insert_mission(project_dir, "q-bbbb/m-2222", "q-bbbb", "MB")

        result = list_missions_grouped(project_dir, quest_id="q-aaaa")
        assert len(result["groups"]) == 1
        assert result["groups"][0]["quest_id"] == "q-aaaa"


# ---------------------------------------------------------------------------
# include_closed flag
# ---------------------------------------------------------------------------


class TestListMissionsGroupedClosedFilter:
    def test_default_excludes_closed_missions(self, project_dir):
        from lore.db import list_missions_grouped

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "Open")
        insert_mission(
            project_dir, "q-aaaa/m-2222", "q-aaaa", "Closed",
            status="closed", closed_at="2025-02-01T00:00:00Z",
        )

        result = list_missions_grouped(project_dir)
        groups = [g for g in result["groups"] if g["quest_id"] == "q-aaaa"]
        # If there are zero non-closed missions the group itself may be absent;
        # but here one open mission means the group surfaces with one entry.
        all_ids = {m["id"] for g in groups for m in g["missions"]}
        assert "q-aaaa/m-1111" in all_ids
        assert "q-aaaa/m-2222" not in all_ids

    def test_include_closed_true_includes_closed_missions(self, project_dir):
        from lore.db import list_missions_grouped

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(
            project_dir, "q-aaaa/m-1111", "q-aaaa", "Closed",
            status="closed", closed_at="2025-02-01T00:00:00Z",
        )

        result = list_missions_grouped(project_dir, include_closed=True)
        all_ids = {m["id"] for g in result["groups"] for m in g["missions"]}
        assert "q-aaaa/m-1111" in all_ids
