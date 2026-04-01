"""E2E tests for the Python DB API contracts — lore.db public functions.

Spec: conceptual-workflows-python-api (lore codex show conceptual-workflows-python-api)
"""

import inspect

import pytest

from lore.db import (
    add_board_message,
    block_mission,
    claim_mission,
    close_mission,
    create_mission,
    create_quest,
    remove_dependency,
    unblock_mission,
)
from lore.priority import get_ready_missions
from tests.conftest import (
    db_conn,
    insert_dependency,
    insert_mission,
    insert_quest,
)


class TestCreateQuest:
    """create_quest returns a string ID; raises ValueError on invalid input."""

    def test_returns_id_string(self, project_dir):
        result = create_quest(project_dir, "My Quest")
        assert isinstance(result, str), f"Expected str, got {type(result)}: {result}"
        assert result.startswith("q-"), f"Expected q- prefix, got: {result}"

        conn = db_conn(project_dir)
        row = conn.execute("SELECT * FROM quests WHERE id = ?", (result,)).fetchone()
        conn.close()
        assert row is not None

    def test_invalid_priority_raises_value_error(self, project_dir):
        with pytest.raises(ValueError, match="5"):
            create_quest(project_dir, "Q", priority=5)

        conn = db_conn(project_dir)
        count = conn.execute("SELECT COUNT(*) FROM quests WHERE title = 'Q'").fetchone()[0]
        conn.close()
        assert count == 0


class TestCreateMission:
    """create_mission returns a string ID; raises ValueError on invalid input."""

    def test_with_quest_id_returns_hierarchical_id(self, project_dir):
        quest_id = create_quest(project_dir, "My Quest")
        result = create_mission(project_dir, "Mission Title", quest_id=quest_id)

        assert isinstance(result, str), f"Expected str, got {type(result)}"
        assert result.startswith(f"{quest_id}/m-"), f"Unexpected ID: {result}"

        conn = db_conn(project_dir)
        row = conn.execute("SELECT quest_id FROM missions WHERE id = ?", (result,)).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == quest_id

    def test_standalone_returns_m_prefix_id(self, project_dir):
        insert_quest(project_dir, "q-aa01", "Quest A")
        insert_quest(project_dir, "q-aa02", "Quest B")

        result = create_mission(project_dir, "Standalone")
        assert isinstance(result, str), f"Expected str, got {type(result)}"
        assert result.startswith("m-"), f"Expected m- prefix, got: {result}"

        conn = db_conn(project_dir)
        row = conn.execute("SELECT quest_id FROM missions WHERE id = ?", (result,)).fetchone()
        conn.close()
        assert row is not None
        assert row[0] is None

    def test_invalid_priority_raises_value_error(self, project_dir):
        with pytest.raises(ValueError, match="5"):
            create_mission(project_dir, "T", priority=5)

    def test_reopens_closed_quest(self, project_dir):
        insert_quest(
            project_dir,
            "q-c001",
            "Closed Quest",
            status="closed",
            closed_at="2025-01-01T00:00:00Z",
        )

        result = create_mission(project_dir, "New Task", quest_id="q-c001")
        assert isinstance(result, str)
        assert result.startswith("q-c001/m-")

        conn = db_conn(project_dir)
        row = conn.execute("SELECT status, closed_at FROM quests WHERE id = 'q-c001'").fetchone()
        conn.close()
        assert row[0] == "open", f"Expected open, got {row[0]}"
        assert row[1] is None, f"Expected NULL closed_at, got {row[1]}"


class TestClaimMission:
    """claim_mission returns a dict with ok and quest-related fields on all paths."""

    def test_success_returns_quest_fields(self, project_dir):
        insert_quest(project_dir, "q-d001", "Quest D")
        insert_mission(project_dir, "q-d001/m-ab01", "q-d001", "Mission One")

        result = claim_mission(project_dir, "q-d001/m-ab01")

        assert result["ok"] is True
        assert result["quest_id"] == "q-d001"
        assert "quest_status" in result
        assert "quest_status_changed" in result
        assert isinstance(result["quest_status_changed"], bool)

    def test_not_found_returns_ok_false(self, project_dir):
        result = claim_mission(project_dir, "q-d001/m-ffff")

        assert isinstance(result, dict)
        assert result["ok"] is False
        assert "error" in result
        assert result["error"] is not None


class TestCloseMission:
    """close_mission returns quest_id and quest_closed bool on all paths."""

    def test_returns_quest_id_and_quest_closed_bool(self, project_dir):
        insert_quest(project_dir, "q-e001", "Quest E")
        insert_mission(
            project_dir, "q-e001/m-ab01", "q-e001", "Mission One", status="in_progress"
        )

        result = close_mission(project_dir, "q-e001/m-ab01")

        assert result["ok"] is True
        assert "quest_id" in result
        assert "quest_closed" in result
        assert isinstance(result["quest_closed"], bool)

    def test_auto_close_quest_reflected_in_return(self, project_dir):
        insert_quest(project_dir, "q-f001", "Auto-Close Quest", auto_close=1)
        insert_mission(
            project_dir, "q-f001/m-ab01", "q-f001", "Last Mission", status="in_progress"
        )

        result = close_mission(project_dir, "q-f001/m-ab01")

        assert result["ok"] is True
        assert result["quest_closed"] is True
        assert result["quest_id"] == "q-f001"

    def test_quest_id_present_on_not_found_path(self, project_dir):
        result = close_mission(project_dir, "q-f001/m-ffff")
        assert result["ok"] is False
        assert "quest_id" in result


class TestBlockUnblockMission:
    """block_mission and unblock_mission update status and block_reason in DB."""

    def test_block_sets_status_and_reason(self, project_dir):
        insert_quest(project_dir, "q-b001", "Quest B")
        insert_mission(
            project_dir, "q-b001/m-ab01", "q-b001", "Mission One", status="in_progress"
        )

        result = block_mission(project_dir, "q-b001/m-ab01", "Need access token")

        assert result["ok"] is True

        conn = db_conn(project_dir)
        row = conn.execute(
            "SELECT status, block_reason FROM missions WHERE id = 'q-b001/m-ab01'"
        ).fetchone()
        conn.close()
        assert row[0] == "blocked"
        assert row[1] == "Need access token"

    def test_unblock_clears_reason_and_sets_open(self, project_dir):
        insert_quest(project_dir, "q-ba01", "Quest BA")
        insert_mission(
            project_dir,
            "q-ba01/m-ab01",
            "q-ba01",
            "Mission One",
            status="blocked",
            block_reason="Waiting on vendor",
        )

        result = unblock_mission(project_dir, "q-ba01/m-ab01")

        assert result["ok"] is True

        conn = db_conn(project_dir)
        row = conn.execute(
            "SELECT status, block_reason FROM missions WHERE id = 'q-ba01/m-ab01'"
        ).fetchone()
        conn.close()
        assert row[0] == "open"
        assert row[1] is None


class TestAddBoardMessage:
    """add_board_message returns ok=True with id on success; ok=False on empty message."""

    def test_empty_message_rejected_at_api_layer(self, project_dir):
        insert_quest(project_dir, "q-a001", "Quest A")
        insert_mission(project_dir, "q-a001/m-ab01", "q-a001", "Mission One")

        result = add_board_message(project_dir, "q-a001/m-ab01", "")

        assert isinstance(result, dict)
        assert result["ok"] is False
        assert "error" in result

        conn = db_conn(project_dir)
        count = conn.execute("SELECT COUNT(*) FROM board_messages").fetchone()[0]
        conn.close()
        assert count == 0

    def test_success_with_optional_sender(self, project_dir):
        insert_quest(project_dir, "q-a001", "Quest A")
        insert_mission(project_dir, "q-a001/m-ab01", "q-a001", "Mission One")
        sender_label = "q-a001/m-ab00"

        result = add_board_message(
            project_dir,
            "q-a001/m-ab01",
            "See codex doc x",
            sender=sender_label,
        )

        assert result["ok"] is True, f"Expected ok=True, got: {result}"
        assert isinstance(result["id"], int)
        assert result["sender"] == sender_label


class TestGetReadyMissions:
    """get_ready_missions orders by priority and excludes blocked and dep-blocked missions."""

    def test_ordering_and_filtering(self, project_dir):
        insert_quest(project_dir, "q-ab01", "Quest AB")

        insert_mission(
            project_dir, "q-ab01/m-ab11", "q-ab01", "Priority 1",
            priority=1, created_at="2025-01-15T09:00:00Z",
        )
        insert_mission(
            project_dir, "q-ab01/m-ab33", "q-ab01", "Priority 3",
            priority=3, created_at="2025-01-15T09:01:00Z",
        )
        insert_mission(
            project_dir, "q-ab01/m-ab00", "q-ab01", "Blocked",
            priority=0, status="blocked",
        )
        insert_mission(
            project_dir, "q-ab01/m-ab0d", "q-ab01", "Dep-blocked",
            priority=0,
        )
        insert_mission(
            project_dir, "q-ab01/m-ab0b", "q-ab01", "Blocker",
            priority=2,
        )
        insert_dependency(project_dir, "q-ab01/m-ab0d", "q-ab01/m-ab0b")

        results = get_ready_missions(project_dir, count=10)

        ids = [row["id"] for row in results]
        assert "q-ab01/m-ab00" not in ids, "Blocked mission should not appear"
        assert "q-ab01/m-ab0d" not in ids, "Dep-blocked mission should not appear"
        assert "q-ab01/m-ab11" in ids
        assert "q-ab01/m-ab33" in ids

        pri1_idx = ids.index("q-ab01/m-ab11")
        pri3_idx = ids.index("q-ab01/m-ab33")
        assert pri1_idx < pri3_idx


class TestRemoveDependency:
    """remove_dependency soft-deletes the dependency row; returns removed=True on success."""

    def test_soft_deletes_active_dependency(self, project_dir):
        insert_quest(project_dir, "q-ab12", "Quest AB12")
        insert_mission(project_dir, "q-ab12/m-aa01", "q-ab12", "Mission A")
        insert_mission(project_dir, "q-ab12/m-bb01", "q-ab12", "Mission B")
        insert_dependency(project_dir, "q-ab12/m-aa01", "q-ab12/m-bb01")

        result = remove_dependency(project_dir, "q-ab12/m-aa01", "q-ab12/m-bb01")

        assert result.get("removed") is True, f"Expected removed=True, got: {result}"

        conn = db_conn(project_dir)
        row = conn.execute(
            "SELECT deleted_at FROM dependencies WHERE from_id = 'q-ab12/m-aa01' AND to_id = 'q-ab12/m-bb01'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] is not None, "deleted_at should be set after remove_dependency"

    def test_invalid_id_format_rejected(self, project_dir):
        result = remove_dependency(project_dir, "notanid", "q-ab12/m-bb01")

        assert isinstance(result, dict)
        assert result.get("not_found") is True
        assert result.get("removed") is False


class TestEdgeCaseBehaviours:
    """Edge-case characterisation tests for documented DB API behaviours."""

    def test_quest_inference_soft_deleted_quest(self, project_dir):
        """create_mission when only available quest is soft-deleted — characterisation test."""
        insert_quest(
            project_dir,
            "q-ab01",
            "Soft-Deleted Quest",
            status="open",
            deleted_at="2025-01-01T00:00:00Z",
        )

        result = create_mission(project_dir, "Task")

        assert isinstance(result, str), f"create_mission should return a string ID, got {type(result)}"
        # Either assigned to deleted quest (known bug) or standalone (correct) — record actual behaviour
        assert result.startswith("q-ab01/m-") or result.startswith("m-"), (
            f"Unexpected mission ID format: {result}"
        )

    def test_add_board_message_race_window_documented(self, project_dir):
        """add_board_message existence check does not use BEGIN IMMEDIATE — race window documented."""
        source = inspect.getsource(add_board_message)

        has_begin_immediate = "BEGIN IMMEDIATE" in source
        assert not has_begin_immediate, (
            "add_board_message now uses BEGIN IMMEDIATE — the race window may be fixed. "
            "Update this test if the implementation has changed."
        )

        insert_quest(project_dir, "q-ab01", "Quest AB01")
        result = add_board_message(project_dir, "q-ab01", "Test message")
        assert result.get("ok") is True, f"add_board_message failed: {result}"


# ---------------------------------------------------------------------------
# Workflow 7 — Realm reads watchers via Python API
# Spec: watchers-us-7 (lore codex show watchers-us-7)
# ---------------------------------------------------------------------------


class TestPythonApiListWatchers:
    """list_watchers returns a sorted list[dict] with all required keys including filename.

    Scenario 1: Realm enumerates watchers via Python API.
    Fails until list_watchers returns dicts with a 'filename' key.
    """

    def test_list_watchers_entry_has_required_keys_including_filename(self, project_dir):
        # Spec: watchers-us-7 Scenario 1 — id, group, title, summary, filename all non-None
        # Fails: current list_watchers does not include 'filename' key in returned dicts
        from lore.paths import watchers_dir
        from lore.watcher import list_watchers

        wdir = watchers_dir(project_dir)
        watchers = list_watchers(wdir)

        assert len(watchers) >= 1, "Expected at least one watcher after lore init"
        entry = watchers[0]
        for key in ("id", "group", "title", "summary", "filename"):
            assert key in entry, f"Missing key {key!r} in list entry: {entry}"
            assert entry[key] is not None, f"Key {key!r} is None in: {entry}"

    def test_list_watchers_filename_matches_yaml_file(self, project_dir):
        # Spec: watchers-us-7 — filename key is the actual .yaml filename for each watcher
        from lore.paths import watchers_dir
        from lore.watcher import list_watchers

        wdir = watchers_dir(project_dir)
        watchers = list_watchers(wdir)

        assert len(watchers) >= 1, "Expected at least one watcher after lore init"
        entry = watchers[0]
        assert "filename" in entry, f"Missing filename key in: {entry}"
        assert entry["filename"].endswith(".yaml"), (
            f"filename should end with .yaml: {entry.get('filename')!r}"
        )


class TestPythonApiLoadWatcher:
    """load_watcher(filepath) returns all 8 fields; optional fields are None when absent.

    Scenario 2: Realm loads full watcher definition and hydrates Watcher dataclass.
    Fails until load_watcher accepts a single filepath argument.
    """

    def test_load_watcher_returns_all_eight_keys(self, project_dir):
        # Spec: watchers-us-7 Scenario 2
        from lore.paths import watchers_dir
        from lore.watcher import list_watchers, load_watcher

        wdir = watchers_dir(project_dir)
        watchers = list_watchers(wdir)
        assert len(watchers) >= 1, "Expected at least one watcher after lore init"
        w = watchers[0]
        filepath = wdir / w["group"] / w["filename"] if w["group"] else wdir / w["filename"]
        assert filepath.exists(), f"Watcher file not found: {filepath}"

        # load_watcher should accept a single filepath argument (Post-MVP deferred to green phase)
        data = load_watcher(filepath)

        for key in ("id", "group", "title", "summary", "filename", "watch_target", "interval", "action"):
            assert key in data, f"Missing key {key!r} in load_watcher output: {data}"

    def test_load_watcher_has_id_and_group_keys(self, project_dir):
        # Spec: watchers-us-7 Scenario 2
        from lore.paths import watchers_dir
        from lore.watcher import list_watchers, load_watcher

        wdir = watchers_dir(project_dir)
        watchers = list_watchers(wdir)
        assert len(watchers) >= 1, "Expected at least one watcher after lore init"
        from pathlib import Path
        filepath = wdir / watchers[0]["group"] / watchers[0]["filename"] if watchers[0]["group"] else wdir / watchers[0]["filename"]
        data = load_watcher(filepath)

        assert "id" in data, f"Missing id key in: {data}"
        assert "group" in data, f"Missing group key in: {data}"

    def test_load_watcher_optional_fields_passthrough(self, project_dir):
        # Spec: watchers-us-7 Scenario 2 — watch_target, interval, action returned as-is
        import textwrap

        from lore.watcher import load_watcher

        watcher_yaml = textwrap.dedent("""
            id: my-watcher
            title: My Watcher
            summary: Testing optional fields passthrough.
            watch_target: feature/*
            interval: daily
            action: run-checks
        """).strip()
        filepath = project_dir / ".lore" / "watchers" / "my-watcher.yaml"
        filepath.write_text(watcher_yaml)
        data = load_watcher(filepath)

        assert data["watch_target"] == "feature/*", f"Unexpected watch_target: {data['watch_target']!r}"
        assert data["interval"] == "daily", f"Unexpected interval: {data['interval']!r}"
        assert data["action"] == "run-checks", f"Unexpected action: {data['action']!r}"

    def test_load_watcher_hydrates_watcher_dataclass(self, project_dir):
        # Spec: watchers-us-7 Scenario 2 — Watcher.from_dict(data) succeeds
        import textwrap

        from lore.models import Watcher
        from lore.watcher import load_watcher

        watcher_yaml = textwrap.dedent("""
            id: hydrate-watcher
            title: Hydrate Watcher
            summary: Testing dataclass hydration.
            watch_target: feature/*
            interval: daily
            action: run-checks
        """).strip()
        watcher_subdir = project_dir / ".lore" / "watchers" / "mygroup"
        watcher_subdir.mkdir(parents=True, exist_ok=True)
        filepath = watcher_subdir / "hydrate-watcher.yaml"
        filepath.write_text(watcher_yaml)
        data = load_watcher(filepath)
        watcher = Watcher.from_dict(data)

        assert watcher.id == "hydrate-watcher"
        assert watcher.group == "mygroup"
        assert watcher.watch_target == "feature/*"
        assert watcher.interval == "daily"
        assert watcher.action == "run-checks"
        assert watcher.filename == "hydrate-watcher.yaml"

    def test_load_watcher_frozen_dataclass_is_immutable(self, project_dir):
        # Spec: watchers-us-7 Scenario 2 — watcher is frozen (immutable)
        import dataclasses

        from lore.models import Watcher
        from lore.paths import watchers_dir
        from lore.watcher import list_watchers, load_watcher

        wdir = watchers_dir(project_dir)
        watchers = list_watchers(wdir)
        assert len(watchers) >= 1, "Expected at least one watcher after lore init"
        w = watchers[0]
        filepath = wdir / w["group"] / w["filename"] if w["group"] else wdir / w["filename"]
        data = load_watcher(filepath)
        watcher = Watcher.from_dict(data)

        with pytest.raises(dataclasses.FrozenInstanceError):
            watcher.id = "changed"  # type: ignore[misc]


class TestPythonApiCreateWatcher:
    """create_watcher creates a new watcher file; load_watcher(filepath) reads it back.

    Scenario 3: Realm creates a watcher via Python API, then loads it back with single-arg
    load_watcher. Fails until load_watcher accepts a single filepath argument.
    """

    def test_create_then_load_watcher_single_arg(self, project_dir):
        # Spec: watchers-us-7 Scenario 3 — create then load via single-arg load_watcher
        # Fails: load_watcher currently requires two arguments (filepath, watchers_dir)
        from lore.paths import watchers_dir
        from lore.watcher import create_watcher, find_watcher, load_watcher

        wdir = watchers_dir(project_dir)
        create_watcher(wdir, "realm-hook", "id: realm-hook\ntitle: Realm Hook\nsummary: Test\n")

        filepath = find_watcher(wdir, "realm-hook")
        assert filepath is not None, "realm-hook.yaml not found after create_watcher"

        # Single-arg load_watcher — fails until production code supports it
        data = load_watcher(filepath)
        assert data["id"] == "realm-hook"
        assert data["filename"] == "realm-hook.yaml"


class TestPythonApiUpdateWatcher:
    """update_watcher replaces watcher file content; load_watcher(filepath) reads it back.

    Scenario 4: Realm updates a watcher via Python API, verified via single-arg load_watcher.
    Fails until load_watcher accepts a single filepath argument.
    """

    def test_update_then_load_watcher_single_arg(self, project_dir):
        # Spec: watchers-us-7 Scenario 4 — update then reload via single-arg load_watcher
        # Fails: load_watcher currently requires two arguments (filepath, watchers_dir)
        from lore.paths import watchers_dir
        from lore.watcher import create_watcher, find_watcher, load_watcher, update_watcher

        wdir = watchers_dir(project_dir)
        create_watcher(wdir, "my-watcher", "id: my-watcher\ntitle: My Watcher\nsummary: Original\n")
        new_content = "id: my-watcher\ntitle: Updated\nsummary: Updated summary\n"
        update_watcher(wdir, "my-watcher", new_content)

        filepath = find_watcher(wdir, "my-watcher")
        assert filepath is not None

        # Single-arg load_watcher — fails until production code supports it
        data = load_watcher(filepath)
        assert data["title"] == "Updated"
        assert data["summary"] == "Updated summary"


class TestPythonApiDeleteWatcher:
    """delete_watcher soft-deletes a watcher; list_watchers no longer includes filename.

    Scenario 5: Realm deletes a watcher via Python API, verified via list_watchers with filename.
    Fails until list_watchers includes 'filename' in returned dicts.
    """

    def test_delete_watcher_then_create_and_list_has_filename_key(self, project_dir):
        # Spec: watchers-us-7 Scenario 5 + Scenario 1 — after delete and recreate, list entry has filename
        # Fails until list_watchers returns dicts with 'filename' key
        from lore.paths import watchers_dir
        from lore.watcher import create_watcher, delete_watcher, list_watchers

        wdir = watchers_dir(project_dir)
        create_watcher(wdir, "to-delete", "id: to-delete\ntitle: To Delete\nsummary: Will be deleted\n")
        delete_watcher(wdir, "to-delete")
        create_watcher(wdir, "new-hook", "id: new-hook\ntitle: New Hook\nsummary: Test\n")

        watchers = list_watchers(wdir)
        assert len(watchers) >= 1, "Expected new-hook to appear in list"
        entry = next(w for w in watchers if w["id"] == "new-hook")
        assert "filename" in entry, f"Missing 'filename' key in list entry: {entry}"
        assert entry["filename"] == "new-hook.yaml", f"Unexpected filename: {entry['filename']!r}"


class TestPythonApiWatcherFromDictOptionalNone:
    """Watcher.from_dict handles optional fields absent.

    Scenario 8: Watcher.from_dict handles optional fields absent.
    Fails until Watcher dataclass exists in lore.models.
    """

    def test_watcher_from_dict_optional_fields_are_none(self, project_dir):
        # Spec: watchers-us-7 Scenario 8
        from lore.models import Watcher

        watcher = Watcher.from_dict({"id": "x", "title": "T", "summary": "S", "group": ""})

        assert watcher.watch_target is None, f"Expected None, got {watcher.watch_target!r}"
        assert watcher.interval is None, f"Expected None, got {watcher.interval!r}"
        assert watcher.action is None, f"Expected None, got {watcher.action!r}"
        assert watcher.filename is None, f"Expected None, got {watcher.filename!r}"
