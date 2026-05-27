"""Red tests for G17: holistic db-backed CRUD sweep — dependency slice.

Spec sources:
  lore codex show transient-public-api-facade-plan              # §G17
  lore codex show transient-public-api-facade-create-stdz       # §A2 §A4 §B (Dependency row)

Dependency contracts:

* `list_mission_depends_on(project_root, mission_id) -> list[dict]` — RENAME
  from `get_mission_depends_on_details`.
* `list_mission_blocks(project_root, mission_id) -> list[dict]` — RENAME
  from `get_mission_blocks_details`.
* str-list returning `get_mission_depends_on` / `get_mission_blocks` REMOVED
  from `lore.api.__all__` (callers project `id` from the dict list).
* `add_dependency(project_root, from_id, to_id) -> dict
  {from, to, created: True}` — positive envelope on success; RAISES
  `ValueError` on malformed ID, missing entity, OR DUPLICATE (behaviour
  change vs the multi-branch dict — locked per amendment §B Dependency).
* `remove_dependency(project_root, from_id, to_id) -> dict
  {from, to, removed: True}` — preserves ADR-011 existence-based contract.
* Bulk variants `add_dependencies` / `remove_dependencies` unchanged
  (canonical Section 5 envelope shape preserved).

These tests EXPECT the new shapes. They MUST fail until G17 Green lands.
NO production code in this chunk — Red phase only.
"""

from __future__ import annotations

import pytest

from tests.conftest import insert_dependency, insert_mission, insert_quest


# ---------------------------------------------------------------------------
# Renames — list_mission_depends_on / list_mission_blocks
# ---------------------------------------------------------------------------


class TestDependencyReadRenames:
    def test_list_mission_depends_on_symbol_exists(self):
        from lore import db

        assert hasattr(db, "list_mission_depends_on"), (
            "G17: lore.db.list_mission_depends_on not defined yet "
            "(rename of get_mission_depends_on_details)"
        )
        assert callable(db.list_mission_depends_on)

    def test_list_mission_blocks_symbol_exists(self):
        from lore import db

        assert hasattr(db, "list_mission_blocks"), (
            "G17: lore.db.list_mission_blocks not defined yet "
            "(rename of get_mission_blocks_details)"
        )
        assert callable(db.list_mission_blocks)

    def test_old_get_mission_depends_on_details_dropped_from_facade(self):
        from lore import api

        assert "get_mission_depends_on_details" not in api.__all__, (
            "G17: `get_mission_depends_on_details` must be renamed to "
            "`list_mission_depends_on`"
        )

    def test_old_get_mission_blocks_details_dropped_from_facade(self):
        from lore import api

        assert "get_mission_blocks_details" not in api.__all__, (
            "G17: `get_mission_blocks_details` must be renamed to "
            "`list_mission_blocks`"
        )

    def test_str_list_get_mission_depends_on_removed_from_facade(self):
        """Amendment Section B Dependency row: drop the str-list variants."""
        from lore import api

        assert "get_mission_depends_on" not in api.__all__, (
            "G17: str-list `get_mission_depends_on` removed from facade — "
            "callers project `id` from `list_mission_depends_on`"
        )

    def test_str_list_get_mission_blocks_removed_from_facade(self):
        from lore import api

        assert "get_mission_blocks" not in api.__all__, (
            "G17: str-list `get_mission_blocks` removed from facade"
        )


# ---------------------------------------------------------------------------
# list_mission_depends_on / list_mission_blocks return list[dict]
# ---------------------------------------------------------------------------


class TestListDepsReturnDictList:
    def test_list_mission_depends_on_returns_list_of_dicts(self, project_dir):
        from lore.db import list_mission_depends_on

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "Downstream")
        insert_mission(project_dir, "q-aaaa/m-2222", "q-aaaa", "Upstream")
        insert_dependency(project_dir, "q-aaaa/m-1111", "q-aaaa/m-2222")

        rows = list_mission_depends_on(project_dir, "q-aaaa/m-1111")
        assert isinstance(rows, list)
        assert all(isinstance(r, dict) for r in rows)
        assert {r["id"] for r in rows} == {"q-aaaa/m-2222"}

    def test_list_mission_blocks_returns_list_of_dicts(self, project_dir):
        from lore.db import list_mission_blocks

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "Downstream")
        insert_mission(project_dir, "q-aaaa/m-2222", "q-aaaa", "Upstream")
        insert_dependency(project_dir, "q-aaaa/m-1111", "q-aaaa/m-2222")

        rows = list_mission_blocks(project_dir, "q-aaaa/m-2222")
        assert isinstance(rows, list)
        assert all(isinstance(r, dict) for r in rows)
        assert {r["id"] for r in rows} == {"q-aaaa/m-1111"}


# ---------------------------------------------------------------------------
# add_dependency single-shot — positive envelope + raise on duplicate
# ---------------------------------------------------------------------------


ADD_DEP_OK_KEYS: frozenset[str] = frozenset({"from", "to", "created"})


class TestAddDependencySingleShotHolistic:
    def test_add_dependency_success_envelope_keys_exact(self, project_dir):
        from lore.db import add_dependency

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "A")
        insert_mission(project_dir, "q-aaaa/m-2222", "q-aaaa", "B")

        result = add_dependency(project_dir, "q-aaaa/m-1111", "q-aaaa/m-2222")
        assert isinstance(result, dict)
        assert "ok" not in result, (
            "amendment A2: add_dependency single-shot drops `ok` wrapper"
        )
        assert set(result.keys()) == ADD_DEP_OK_KEYS, (
            f"add_dependency envelope MUST have EXACTLY "
            f"{sorted(ADD_DEP_OK_KEYS)}; got {sorted(result.keys())}"
        )
        assert result["from"] == "q-aaaa/m-1111"
        assert result["to"] == "q-aaaa/m-2222"
        assert result["created"] is True

    def test_add_dependency_raises_on_duplicate(self, project_dir):
        """Amendment B Dependency row: single-shot RAISES on duplicate.

        Bulk variant `add_dependencies` keeps the multi-branch envelope
        (`{created, existing, errors}`) — single-shot diverges.
        """
        from lore.db import add_dependency

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "A")
        insert_mission(project_dir, "q-aaaa/m-2222", "q-aaaa", "B")

        add_dependency(project_dir, "q-aaaa/m-1111", "q-aaaa/m-2222")
        with pytest.raises(ValueError):
            add_dependency(project_dir, "q-aaaa/m-1111", "q-aaaa/m-2222")

    def test_add_dependency_raises_on_unknown_from(self, project_dir):
        from lore.db import add_dependency

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-2222", "q-aaaa", "B")
        with pytest.raises(ValueError):
            add_dependency(project_dir, "q-aaaa/m-9999", "q-aaaa/m-2222")

    def test_add_dependency_raises_on_unknown_to(self, project_dir):
        from lore.db import add_dependency

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "A")
        with pytest.raises(ValueError):
            add_dependency(project_dir, "q-aaaa/m-1111", "q-aaaa/m-9999")


# ---------------------------------------------------------------------------
# remove_dependency single-shot — positive envelope
# ---------------------------------------------------------------------------


REMOVE_DEP_KEYS: frozenset[str] = frozenset({"from", "to", "removed"})


class TestRemoveDependencySingleShotHolistic:
    def test_remove_dependency_success_envelope_keys_exact(self, project_dir):
        from lore.db import add_dependency, remove_dependency

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "A")
        insert_mission(project_dir, "q-aaaa/m-2222", "q-aaaa", "B")
        add_dependency(project_dir, "q-aaaa/m-1111", "q-aaaa/m-2222")

        result = remove_dependency(project_dir, "q-aaaa/m-1111", "q-aaaa/m-2222")
        assert isinstance(result, dict)
        assert set(result.keys()) == REMOVE_DEP_KEYS, (
            f"remove_dependency envelope MUST have EXACTLY "
            f"{sorted(REMOVE_DEP_KEYS)}; got {sorted(result.keys())}"
        )
        assert result["from"] == "q-aaaa/m-1111"
        assert result["to"] == "q-aaaa/m-2222"
        assert result["removed"] is True


# ---------------------------------------------------------------------------
# Bulk variants UNCHANGED (canonical Section 5 envelope preserved).
# ---------------------------------------------------------------------------


class TestBulkDepsEnvelopeUnchanged:
    def test_add_dependencies_envelope_keys_preserved(self, project_dir):
        from lore.db import add_dependencies

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "A")
        insert_mission(project_dir, "q-aaaa/m-2222", "q-aaaa", "B")

        result = add_dependencies(
            project_dir, [("q-aaaa/m-1111", "q-aaaa/m-2222")]
        )
        assert set(result.keys()) == {"created", "existing", "errors"}, (
            "G17: bulk add_dependencies envelope unchanged per canonical Section 5"
        )

    def test_add_dependencies_existing_branch_still_populated_on_duplicate(
        self, project_dir
    ):
        """Single-shot raises on duplicate; BULK preserves `existing` branch."""
        from lore.db import add_dependencies

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "A")
        insert_mission(project_dir, "q-aaaa/m-2222", "q-aaaa", "B")

        add_dependencies(project_dir, [("q-aaaa/m-1111", "q-aaaa/m-2222")])
        result = add_dependencies(
            project_dir, [("q-aaaa/m-1111", "q-aaaa/m-2222")]
        )
        assert result["existing"] == [
            {"from": "q-aaaa/m-1111", "to": "q-aaaa/m-2222"}
        ], (
            "Bulk `existing` branch MUST survive the single-shot raise-on-dup change"
        )
        assert result["errors"] == []
        assert result["created"] == []

    def test_remove_dependencies_envelope_keys_preserved(self, project_dir):
        from lore.db import remove_dependencies

        result = remove_dependencies(project_dir, [])
        assert set(result.keys()) == {"removed", "not_found", "errors"}, (
            "G17: bulk remove_dependencies envelope unchanged per canonical Section 5"
        )
