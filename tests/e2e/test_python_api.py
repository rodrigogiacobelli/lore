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
    """create_quest returns a dict envelope; raises ValueError on invalid input.

    G17 (amendment Section B Quest row): return shape is
    ``{id, filename: None, group: None}`` (was bare str).
    """

    def test_returns_id_string(self, project_dir):
        result = create_quest(project_dir, "My Quest")
        # G17: returns dict envelope.
        assert isinstance(result, dict)
        qid = result["id"]
        assert qid.startswith("q-"), f"Expected q- prefix, got: {qid}"
        assert result["filename"] is None
        assert result["group"] is None

        conn = db_conn(project_dir)
        row = conn.execute("SELECT * FROM quests WHERE id = ?", (qid,)).fetchone()
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
    """create_mission returns a dict envelope; raises ValueError on invalid input.

    G17 (amendment Section B Mission row): return shape is
    ``{id, filename: None, group: None}`` (was bare str).
    """

    def test_with_quest_id_returns_hierarchical_id(self, project_dir):
        quest_id = create_quest(project_dir, "My Quest")["id"]
        result = create_mission(project_dir, "Mission Title", quest_id=quest_id)

        assert isinstance(result, dict)
        mid = result["id"]
        assert mid.startswith(f"{quest_id}/m-"), f"Unexpected ID: {mid}"

        conn = db_conn(project_dir)
        row = conn.execute("SELECT quest_id FROM missions WHERE id = ?", (mid,)).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == quest_id

    def test_standalone_returns_m_prefix_id(self, project_dir):
        insert_quest(project_dir, "q-aa01", "Quest A")
        insert_quest(project_dir, "q-aa02", "Quest B")

        result = create_mission(project_dir, "Standalone")
        assert isinstance(result, dict)
        mid = result["id"]
        assert mid.startswith("m-"), f"Expected m- prefix, got: {mid}"

        conn = db_conn(project_dir)
        row = conn.execute("SELECT quest_id FROM missions WHERE id = ?", (mid,)).fetchone()
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
        assert isinstance(result, dict)
        assert result["id"].startswith("q-c001/m-")

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
    """add_board_message returns positive envelope on success; raises ValueError on bad input.

    G17 (amendment Review Ledger CHANGED): the ``ok`` wrapper is dropped;
    validation/lookup failures raise ``ValueError``.
    """

    def test_empty_message_rejected_at_api_layer(self, project_dir):
        insert_quest(project_dir, "q-a001", "Quest A")
        insert_mission(project_dir, "q-a001/m-ab01", "q-a001", "Mission One")

        with pytest.raises(ValueError):
            add_board_message(project_dir, "q-a001/m-ab01", "")

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

        # G17: positive envelope, no `ok`.
        assert "ok" not in result
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
        # G17: existence-based contract preserved; envelope is
        # ``{from, to, removed: False}`` (no `not_found` flag).
        result = remove_dependency(project_dir, "notanid", "q-ab12/m-bb01")

        assert isinstance(result, dict)
        assert result["removed"] is False
        assert result["from"] == "notanid"
        assert result["to"] == "q-ab12/m-bb01"


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

        # G17: returns dict envelope.
        assert isinstance(result, dict)
        mid = result["id"]
        # Either assigned to deleted quest (known bug) or standalone (correct) — record actual behaviour
        assert mid.startswith("q-ab01/m-") or mid.startswith("m-"), (
            f"Unexpected mission ID format: {mid}"
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
        # G17: positive envelope, no `ok`.
        assert "ok" not in result
        assert result["entity_id"] == "q-ab01"


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

        _wdir = watchers_dir(project_dir)
        watchers = list_watchers(project_dir)

        assert len(watchers) >= 1, "Expected at least one watcher after lore init"
        entry = watchers[0]
        for key in ("id", "group", "title", "summary", "filename"):
            assert key in entry, f"Missing key {key!r} in list entry: {entry}"
            assert entry[key] is not None, f"Key {key!r} is None in: {entry}"

    def test_list_watchers_filename_matches_yaml_file(self, project_dir):
        # Spec: watchers-us-7 — filename key is the actual .yaml filename for each watcher
        from lore.paths import watchers_dir
        from lore.watcher import list_watchers

        _wdir = watchers_dir(project_dir)
        watchers = list_watchers(project_dir)

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
        from lore.watcher import list_watchers, _load_watcher as load_watcher

        wdir = watchers_dir(project_dir)
        watchers = list_watchers(project_dir)
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
        from lore.watcher import list_watchers, _load_watcher as load_watcher

        wdir = watchers_dir(project_dir)
        watchers = list_watchers(project_dir)
        assert len(watchers) >= 1, "Expected at least one watcher after lore init"
        filepath = wdir / watchers[0]["group"] / watchers[0]["filename"] if watchers[0]["group"] else wdir / watchers[0]["filename"]
        data = load_watcher(filepath)

        assert "id" in data, f"Missing id key in: {data}"
        assert "group" in data, f"Missing group key in: {data}"

    def test_load_watcher_optional_fields_passthrough(self, project_dir):
        # Spec: watchers-us-7 Scenario 2 — watch_target, interval, action returned as-is
        import textwrap

        from lore.watcher import _load_watcher as load_watcher

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
        from lore.watcher import _load_watcher as load_watcher

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
        from lore.watcher import list_watchers, _load_watcher as load_watcher

        wdir = watchers_dir(project_dir)
        watchers = list_watchers(project_dir)
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
        from lore.watcher import create_watcher, _find_watcher as find_watcher, _load_watcher as load_watcher

        _wdir = watchers_dir(project_dir)
        create_watcher(project_dir, "realm-hook", "id: realm-hook\ntitle: Realm Hook\nsummary: Test\n")

        filepath = find_watcher(project_dir, "realm-hook")
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
        from lore.watcher import create_watcher, _find_watcher as find_watcher, _load_watcher as load_watcher, update_watcher

        _wdir = watchers_dir(project_dir)
        create_watcher(project_dir, "my-watcher", "id: my-watcher\ntitle: My Watcher\nsummary: Original\n")
        new_content = "id: my-watcher\ntitle: Updated\nsummary: Updated summary\n"
        update_watcher(project_dir, "my-watcher", new_content)

        filepath = find_watcher(project_dir, "my-watcher")
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

        _wdir = watchers_dir(project_dir)
        create_watcher(project_dir, "to-delete", "id: to-delete\ntitle: To Delete\nsummary: Will be deleted\n")
        delete_watcher(project_dir, "to-delete")
        create_watcher(project_dir, "new-hook", "id: new-hook\ntitle: New Hook\nsummary: Test\n")

        watchers = list_watchers(project_dir)
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


# ---------------------------------------------------------------------------
# Python API: the doctrine directory model
# Workflow: conceptual-workflows-doctrine-list / -show / -new
# ---------------------------------------------------------------------------


def _design_text(doctrine_id="my-workflow", title="My Workflow", summary="Does things"):
    return f"---\nid: {doctrine_id}\ntitle: {title}\nsummary: {summary}\n---\n\n# {title}\n"


def _mission_text(mission_id, title=None, summary="A mission.", body="Do the work.\n"):
    return (
        f"---\nid: {mission_id}\ntitle: {title or mission_id}\nsummary: {summary}\n"
        f"---\n\n{body}"
    )


def _author_doctrine(root, stem="my-workflow", *, group="", missions=("recon",)):
    """Write a doctrine directory under ``root/.lore/doctrines``."""
    base = root / ".lore" / "doctrines"
    if group:
        base = base / group
    directory = base / stem
    (directory / "missions").mkdir(parents=True, exist_ok=True)
    (directory / f"{stem}.design.md").write_text(_design_text(stem))
    for mission_id in missions:
        (directory / "missions" / f"{mission_id}.md").write_text(_mission_text(mission_id))
    return directory


class TestPythonApiListDoctrines:
    """``list_doctrines`` reads the directory model and keeps its record shape."""

    def test_a_doctrine_directory_is_one_entry(self, tmp_path):
        from lore.doctrine import list_doctrines

        _author_doctrine(tmp_path)

        assert list_doctrines(tmp_path) == [
            {
                "id": "my-workflow",
                "group": "",
                "title": "My Workflow",
                "summary": "Does things",
                "filename": "my-workflow.design.md",
                "valid": True,
                # nested-projects-spec — D-15: `origin` is on every record, always
                "origin": "self",
            }
        ]

    def test_a_loose_design_file_is_not_a_doctrine(self, tmp_path):
        from lore.doctrine import list_doctrines

        (tmp_path / ".lore" / "doctrines").mkdir(parents=True)
        (tmp_path / ".lore" / "doctrines" / "orphan.design.md").write_text(
            _design_text("orphan")
        )

        assert list_doctrines(tmp_path) == []

    def test_a_stray_yaml_is_not_a_doctrine(self, tmp_path):
        from lore.doctrine import list_doctrines

        (tmp_path / ".lore" / "doctrines").mkdir(parents=True)
        (tmp_path / ".lore" / "doctrines" / "legacy.yaml").write_text("id: legacy\n")

        assert list_doctrines(tmp_path) == []

    def test_the_group_comes_from_the_directory_chain(self, tmp_path):
        from lore.doctrine import list_doctrines

        _author_doctrine(tmp_path, group="default/feature-implementation")

        assert list_doctrines(tmp_path)[0]["group"] == "default/feature-implementation"

    def test_an_empty_doctrines_directory_is_an_empty_list(self, tmp_path):
        from lore.doctrine import list_doctrines

        (tmp_path / ".lore" / "doctrines").mkdir(parents=True)

        assert list_doctrines(tmp_path) == []


class TestPythonApiReadDoctrine:
    """``read_doctrine`` answers with the design document and the mission index."""

    def test_the_record_shape(self, tmp_path):
        from lore.doctrine import read_doctrine

        _author_doctrine(tmp_path, missions=("recon", "scribe"))

        record = read_doctrine(tmp_path, "my-workflow")

        assert record == {
            "id": "my-workflow",
            "title": "My Workflow",
            "summary": "Does things",
            "design": _design_text(),
            "missions": [
                {"id": "recon", "title": "recon", "summary": "A mission."},
                {"id": "scribe", "title": "scribe", "summary": "A mission."},
            ],
            "origin": "self",
        }

    def test_the_design_is_the_whole_file(self, tmp_path):
        from lore.doctrine import read_doctrine

        _author_doctrine(tmp_path)

        assert read_doctrine(tmp_path, "my-workflow")["design"] == _design_text()

    def test_a_mission_selector_adds_the_body(self, tmp_path):
        from lore.doctrine import read_doctrine

        _author_doctrine(tmp_path)

        record = read_doctrine(tmp_path, "my-workflow", mission="recon")

        assert record["mission"] == {
            "id": "recon",
            "title": "recon",
            "summary": "A mission.",
            "body": "Do the work.\n",
        }

    def test_a_mission_miss_is_a_record_with_a_null_mission(self, tmp_path):
        from lore.doctrine import read_doctrine

        _author_doctrine(tmp_path)

        record = read_doctrine(tmp_path, "my-workflow", mission="nope")

        assert record is not None
        assert record["mission"] is None

    def test_a_doctrine_miss_is_none(self, tmp_path):
        from lore.doctrine import read_doctrine

        _author_doctrine(tmp_path)

        assert read_doctrine(tmp_path, "nope") is None

    def test_a_nested_doctrine_is_found(self, tmp_path):
        from lore.doctrine import read_doctrine

        _author_doctrine(tmp_path, group="default/feature-implementation")

        assert read_doctrine(tmp_path, "my-workflow") is not None

    def test_a_malformed_design_is_a_miss_and_never_raises(self, tmp_path):
        """A read answers ``None`` on a miss; it never raises on bad content."""
        from lore.doctrine import read_doctrine

        directory = tmp_path / ".lore" / "doctrines" / "broken"
        directory.mkdir(parents=True)
        (directory / "broken.design.md").write_text("---\nid: broken\n: : :\n---\nBody.\n")

        assert read_doctrine(tmp_path, "broken") is None

    def test_a_mission_id_with_a_separator_is_refused(self, tmp_path):
        from lore.doctrine import read_doctrine

        _author_doctrine(tmp_path)

        with pytest.raises(ValueError, match="path separators not allowed"):
            read_doctrine(tmp_path, "my-workflow", mission="../secrets")


class TestPythonApiCreateDoctrine:
    """``create_doctrine`` takes content, not paths, and writes the whole tree."""

    def test_the_envelope_and_the_files(self, tmp_path):
        from lore.doctrine import create_doctrine

        (tmp_path / ".lore" / "doctrines").mkdir(parents=True)

        result = create_doctrine(
            tmp_path,
            "my-workflow",
            _design_text(),
            {"recon": _mission_text("recon"), "scribe": _mission_text("scribe")},
        )

        assert result == {
            "created": "my-workflow",
            "group": None,
            "missions": ["recon", "scribe"],
            "path": ".lore/doctrines/my-workflow/",
        }
        directory = tmp_path / ".lore" / "doctrines" / "my-workflow"
        assert (directory / "my-workflow.design.md").read_text() == _design_text()
        assert sorted(p.name for p in (directory / "missions").iterdir()) == [
            "recon.md",
            "scribe.md",
        ]

    def test_a_group_nests_the_directory(self, tmp_path):
        from lore.doctrine import create_doctrine

        (tmp_path / ".lore" / "doctrines").mkdir(parents=True)

        result = create_doctrine(
            tmp_path, "my-workflow", _design_text(), {"recon": _mission_text("recon")},
            group="default",
        )

        assert result["group"] == "default"
        assert result["path"] == ".lore/doctrines/default/my-workflow/"

    def test_a_design_id_that_is_not_the_name_is_refused(self, tmp_path):
        from lore.doctrine import create_doctrine

        (tmp_path / ".lore" / "doctrines").mkdir(parents=True)

        with pytest.raises(
            ValueError,
            match='Design file id "other" does not match command argument "my-workflow"',
        ):
            create_doctrine(
                tmp_path, "my-workflow", _design_text("other"),
                {"recon": _mission_text("recon")},
            )
        assert not (tmp_path / ".lore" / "doctrines" / "my-workflow").exists()

    def test_a_mission_id_that_is_not_its_stem_is_refused(self, tmp_path):
        from lore.doctrine import create_doctrine

        (tmp_path / ".lore" / "doctrines").mkdir(parents=True)

        with pytest.raises(ValueError, match="does not match filename stem"):
            create_doctrine(
                tmp_path, "my-workflow", _design_text(),
                {"recon": _mission_text("reconnaissance")},
            )
        assert not (tmp_path / ".lore" / "doctrines" / "my-workflow").exists()

    def test_no_missions_is_refused(self, tmp_path):
        from lore.doctrine import create_doctrine

        (tmp_path / ".lore" / "doctrines").mkdir(parents=True)

        with pytest.raises(
            ValueError, match=r"At least one mission file is required \(-m\)"
        ):
            create_doctrine(tmp_path, "my-workflow", _design_text(), {})

    def test_a_duplicate_anywhere_in_the_subtree_is_refused(self, tmp_path):
        from lore.doctrine import create_doctrine

        _author_doctrine(tmp_path, group="default")

        with pytest.raises(ValueError, match="already exists at"):
            create_doctrine(
                tmp_path, "my-workflow", _design_text(),
                {"recon": _mission_text("recon")},
            )

    def test_a_failure_leaves_no_staging_directory(self, tmp_path):
        from lore.doctrine import create_doctrine

        doctrines = tmp_path / ".lore" / "doctrines"
        doctrines.mkdir(parents=True)

        with pytest.raises(ValueError, match='Mission "recon"'):
            create_doctrine(
                tmp_path, "my-workflow", _design_text(),
                {"recon": "---\nid: recon\ntitle: Recon\n---\n\nNo summary.\n"},
            )

        assert list(doctrines.iterdir()) == []


class TestPythonApiUpdateAndDeleteDoctrine:
    """``update_doctrine`` merges by stem; ``delete_doctrine`` renames the directory."""

    def test_update_replaces_one_mission_and_leaves_the_others(self, tmp_path):
        from lore.doctrine import update_doctrine

        directory = _author_doctrine(tmp_path, missions=("recon", "scribe"))
        before = (directory / "missions" / "scribe.md").read_text()

        result = update_doctrine(
            tmp_path, "my-workflow", None,
            {"recon": _mission_text("recon", body="Rewritten.\n")},
        )

        assert result == {
            "updated": "my-workflow",
            "design_replaced": False,
            "missions_replaced": ["recon"],
            "missions_removed": [],
        }
        assert "Rewritten." in (directory / "missions" / "recon.md").read_text()
        assert (directory / "missions" / "scribe.md").read_text() == before

    def test_a_removal_soft_deletes(self, tmp_path):
        from lore.doctrine import update_doctrine

        directory = _author_doctrine(tmp_path, missions=("recon", "scribe"))

        update_doctrine(tmp_path, "my-workflow", None, None, ["scribe"])

        assert (directory / "missions" / "scribe.md.deleted").is_file()
        assert not (directory / "missions" / "scribe.md").exists()

    def test_delete_renames_the_directory(self, tmp_path):
        from lore.doctrine import delete_doctrine

        directory = _author_doctrine(tmp_path)

        assert delete_doctrine(tmp_path, "my-workflow") == {
            "id": "my-workflow",
            "deleted": True,
            "deleted_at": None,
        }
        assert directory.with_name("my-workflow.deleted").is_dir()


class TestPythonApiDoctrineDeletions:
    """The step-graph machinery is gone from the module, not relocated."""

    @pytest.mark.parametrize(
        "name",
        [
            "load_doctrine",
            "validate_doctrine_content",
            "scaffold_doctrine",
            "_validate_steps",
            "_check_cycles",
            "_normalize",
            "_validate_yaml_schema",
        ],
    )
    def test_the_step_graph_helpers_are_absent(self, name):
        import lore.doctrine as doctrine

        assert not hasattr(doctrine, name)


class TestDoctrineListEntryFromDictNewShape:
    """DoctrineListEntry.from_dict() constructs correctly from new two-file schema shape."""

    def test_doctrine_list_entry_from_dict_new_shape(self):
        # Spec: US-009 E2E Scenario 4 — DoctrineListEntry.from_dict() constructs from new shape
        from lore.models import DoctrineListEntry

        d = {
            "id": "feature-implementation",
            "group": "feature-implementation",
            "title": "Feature Implementation",
            "summary": "E2E spec-driven pipeline...",
            "filename": "feature-implementation.design.md",
            "valid": True,
        }
        entry = DoctrineListEntry.from_dict(d)
        assert entry.id == "feature-implementation"
        assert entry.group == "feature-implementation"
        assert entry.title == "Feature Implementation"
        assert entry.summary == "E2E spec-driven pipeline..."
        assert entry.filename == "feature-implementation.design.md"
        assert entry.valid is True

    def test_doctrine_list_entry_no_legacy_attributes(self):
        # Spec: US-009 E2E Scenario 5 — name, description, errors removed
        from lore.models import DoctrineListEntry

        d = {
            "id": "x",
            "group": "",
            "title": "X",
            "summary": "",
            "filename": "x.design.md",
            "valid": True,
        }
        entry = DoctrineListEntry.from_dict(d)
        assert not hasattr(entry, "name")
        assert not hasattr(entry, "description")
        assert not hasattr(entry, "errors")


class TestLoadSchemaPythonAPI:
    """US-001 — `from lore.schemas import load_schema` is a Python API contract.

    Runs in a subprocess against the currently-installed lore (the wheel install
    in the dev venv) so the test exercises the real import path a Realm consumer
    would use. Spec: schema-validation-us-001 E2E scenarios 1-3.
    """

    def test_load_schema_prints_id_for_a_doctrine_mission(self):
        import subprocess
        import sys

        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "from lore.schemas import load_schema; "
                "print(load_schema('doctrine-mission-frontmatter')['$id'])",
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"
        assert proc.stdout.strip() == "lore://schemas/doctrine-mission-frontmatter"

    def test_every_packaged_kind_loads_silently(self):
        import subprocess
        import sys

        code = (
            "from lore.schemas import load_schema; "
            "[load_schema(k) for k in "
            "['doctrine-design-frontmatter','doctrine-mission-frontmatter',"
            "'watcher-yaml','codex-frontmatter','artifact-frontmatter']]"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"
        assert proc.stdout == ""

    def test_unknown_kind_reports_clear_error(self):
        import subprocess
        import sys

        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "from lore.schemas import load_schema; load_schema('nope')",
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode != 0
        assert "Unknown schema kind: 'nope'" in proc.stderr


class TestValidateEntityPythonAPI:
    """US-002 — validate_entity / validate_entity_file Python API contract.

    PRD scenarios for schema-validation-us-002. Exercises the real install via
    a subprocess so the test matches the exact usage pattern a Realm or Citadel
    consumer would hit.
    """

    def test_scenario_1_valid_mission_dict_prints_empty_list(self):
        import subprocess
        import sys

        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "from lore.schemas import validate_entity; "
                "print(validate_entity('doctrine-mission-frontmatter', "
                "{'id':'pm','title':'Product Manager','summary':'Writes PRDs.'}))",
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"
        assert proc.stdout.strip() == "[]"

    def test_scenario_2_additional_properties_single_issue_at_stability(self):
        import json
        import subprocess
        import sys

        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "from lore.schemas import validate_entity; import json; "
                "print(json.dumps([{'rule':i.rule,'pointer':i.pointer,'message':i.message} "
                "for i in validate_entity('doctrine-mission-frontmatter', "
                "{'id':'pm','title':'PM','summary':'s','stability':'x'})]))",
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"
        data = json.loads(proc.stdout)
        assert len(data) == 1
        assert data[0]["rule"] == "additionalProperties"
        assert data[0]["pointer"] == "/stability"

    def test_scenario_3_validate_entity_file_good_doctrine_design(self, tmp_path):
        import subprocess
        import sys

        p = tmp_path / "good.design.md"
        p.write_text("---\nid: d\ntitle: D\nsummary: s\n---\n\nDesign prose.\n")
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                f"from lore.schemas import validate_entity_file; "
                f"print(validate_entity_file('{p}', 'doctrine-design-frontmatter'))",
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"
        assert proc.stdout.strip() == "[]"

    def test_scenario_4_validate_entity_file_unparseable_yaml(self, tmp_path):
        import subprocess
        import sys

        p = tmp_path / "bad.yaml"
        p.write_text("key: : : nope")
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                f"from lore.schemas import validate_entity_file; "
                f"r = validate_entity_file('{p}', 'watcher-yaml'); "
                f"print(r[0].rule, r[0].pointer); print(len(r))",
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"
        lines = proc.stdout.splitlines()
        assert lines[0] == "yaml-parse /"
        assert lines[1] == "1"


class TestParseFrontmatterRawPythonAPI:
    """US-003 — `from lore.frontmatter import parse_frontmatter_raw` contract.

    PRD scenarios for schema-validation-us-003. Runs in a subprocess against
    the installed wheel so the test exercises the real import path a Realm
    consumer would use.
    """

    def test_scenario_1_preserves_unknown_keys(self, tmp_path):
        import subprocess
        import sys

        p = tmp_path / "k.md"
        p.write_text(
            "---\nid: pm\ntitle: PM\nsummary: s\nstability: experimental\n---\nbody\n"
        )
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "from lore.frontmatter import parse_frontmatter_raw; "
                f"print(parse_frontmatter_raw('{p}'))",
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"
        assert proc.stdout.strip() == (
            "({'id': 'pm', 'title': 'PM', 'summary': 's', "
            "'stability': 'experimental'}, None)"
        )

    def test_scenario_2_missing_frontmatter(self, tmp_path):
        import subprocess
        import sys

        p = tmp_path / "plain.md"
        p.write_text("hello world\n")
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "from lore.frontmatter import parse_frontmatter_raw; "
                f"print(parse_frontmatter_raw('{p}'))",
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"
        assert proc.stdout.strip() == "(None, None)"

    def test_scenario_3_unparseable_yaml(self, tmp_path):
        import subprocess
        import sys

        p = tmp_path / "broken.md"
        p.write_text("---\nid: : :\n---\n")
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "from lore.frontmatter import parse_frontmatter_raw; "
                f"r = parse_frontmatter_raw('{p}'); "
                "print(r[0], type(r[1]).__name__)",
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"
        assert proc.stdout.strip().startswith("None str")


class TestUS009HealthCheckPythonAPI:
    """US-009 — `lore.models` schema-validation Python API parity.

    Spec: schema-validation-us-009 E2E scenarios 1-5.
          conceptual-workflows-python-api — ADR-011 parity.

    Runs in a subprocess against the currently-installed lore so the test
    exercises the real import path a Realm or Citadel consumer would hit.
    """

    def _write_bad_doctrine_mission(self, project_dir):
        """One mission file carrying a field its schema does not allow."""
        missions = project_dir / ".lore" / "doctrines" / "feat" / "missions"
        missions.mkdir(parents=True, exist_ok=True)
        (project_dir / ".lore" / "doctrines" / "feat" / "feat.design.md").write_text(
            "---\nid: feat\ntitle: Feature\nsummary: s\n---\n\nDesign.\n"
        )
        (missions / "pm.md").write_text(
            "---\n"
            "id: pm\n"
            "title: Product Manager\n"
            "summary: Writes PRDs.\n"
            "stability: x\n"
            "---\n"
            "# Body\n"
        )

    def test_scenario_2_public_symbols_present_in_all(self):
        """schema-validation-us-009 — Scenario 2: health_check, validate_entity_file, load_schema in __all__."""
        import subprocess
        import sys

        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import lore.api as m; "
                "print('health_check' in m.__all__, "
                "'validate_entity_file' in m.__all__, "
                "'load_schema' in m.__all__)",
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"
        assert proc.stdout.strip() == "True True True"

    def test_scenario_3_validate_entity_file_standalone(self, tmp_path):
        """schema-validation-us-009 — Scenario 3: validate_entity_file via lore.models."""
        import subprocess
        import sys

        p = tmp_path / "pm.md"
        p.write_text(
            "---\nid: pm\ntitle: PM\nsummary: s\nstability: x\n---\n"
        )
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "from lore.api import validate_entity_file; "
                f"r = validate_entity_file({str(p)!r}, 'doctrine-mission-frontmatter'); "
                "print(r[0].rule, r[0].pointer)",
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"
        assert proc.stdout.strip() == "additionalProperties /stability"

    def test_scenario_1_health_check_parity_with_cli_json(self, project_dir):
        """schema-validation-us-009 — Scenario 1: health_check == lore health --json schema issues."""
        import json as _j
        import subprocess
        import sys

        self._write_bad_doctrine_mission(project_dir)

        # CLI path
        cli_proc = subprocess.run(
            [sys.executable, "-m", "lore.cli", "health", "--json"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
        )
        assert cli_proc.returncode in (0, 1), f"stderr: {cli_proc.stderr}"
        cli_payload = _j.loads(cli_proc.stdout)
        cli_schema_issues = [
            i for i in cli_payload["issues"] if i["check"] == "schema"
        ]
        assert len(cli_schema_issues) == 1, (
            f"expected 1 cli schema issue, got: {cli_schema_issues!r}"
        )

        # Python API path
        py_proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "from lore.api import health_check; import json; "
                "r = health_check(); "
                "print(json.dumps("
                "[{'check':i.check,'rule':i.rule,'pointer':i.pointer,"
                "'schema_id':i.schema_id} for i in r.issues if i.check == 'schema']"
                "))",
            ],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
        )
        assert py_proc.returncode == 0, f"stderr: {py_proc.stderr}"
        py_schema_issues = _j.loads(py_proc.stdout)
        assert len(py_schema_issues) == 1
        assert py_schema_issues[0]["rule"] == cli_schema_issues[0]["rule"]
        assert py_schema_issues[0]["pointer"] == cli_schema_issues[0]["pointer"]
        assert py_schema_issues[0]["schema_id"] == cli_schema_issues[0]["schema_id"]

    def test_scenario_1_exact_stdout_shape(self, project_dir):
        """schema-validation-us-009 — Scenario 1 literal stdout shape."""
        import subprocess
        import sys

        self._write_bad_doctrine_mission(project_dir)
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "from lore.api import health_check; import json; "
                "r = health_check(); "
                "print(json.dumps("
                "[{'check':i.check,'rule':i.rule,'pointer':i.pointer,"
                "'schema_id':i.schema_id} for i in r.issues if i.check == 'schema']"
                "))",
            ],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"
        assert proc.stdout.strip() == (
            '[{"check": "schema", "rule": "additionalProperties", '
            '"pointer": "/stability", '
            '"schema_id": "lore://schemas/doctrine-mission-frontmatter"}]'
        )

    def test_scenario_4_scan_failed_on_missing_schema(self, project_dir):
        """schema-validation-us-009 — Scenario 4: load_schema failure → scan_failed (no false-green)."""
        import subprocess
        import sys

        self._write_bad_doctrine_mission(project_dir)
        code = (
            "import lore.schemas as s\n"
            "def boom(kind):\n"
            "    raise FileNotFoundError('doctrine-mission-frontmatter resource missing')\n"
            "s.load_schema = boom\n"
            "try: s._validator_for.cache_clear()\n"
            "except Exception: pass\n"
            "from lore.api import health_check\n"
            "r = health_check()\n"
            "print(r.has_errors)\n"
            "scan_failed = [i for i in r.issues if i.check == 'scan_failed']\n"
            "print(any('doctrine-mission-frontmatter resource missing' in (i.detail or '') "
            "for i in scan_failed))\n"
            "schema = [i for i in r.issues if i.check == 'schema' "
            "and i.schema_id == 'lore://schemas/doctrine-mission-frontmatter']\n"
            "print(len(schema))\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"
        lines = proc.stdout.strip().splitlines()
        assert lines[0] == "True", f"expected has_errors True, got: {proc.stdout!r}"
        assert lines[1] == "True", (
            f"expected scan_failed detail substring match, got: {proc.stdout!r}"
        )
        assert lines[2] == "0", (
            f"expected no schema false-green entries, got: {proc.stdout!r}"
        )

    def test_scenario_5_no_cli_side_effects(self, project_dir):
        """schema-validation-us-009 — Scenario 5: health_check writes nothing to stdout/stderr."""
        import subprocess
        import sys

        self._write_bad_doctrine_mission(project_dir)
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "from lore.api import health_check; "
                "r = health_check(); "
                "assert r.has_errors is True",
            ],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"
        assert proc.stdout == ""
        assert proc.stderr == ""

    def test_scenario_5_no_transient_report_written(self, project_dir):
        """schema-validation-us-009 — Scenario 5: no transient health-*.md file written by Python API."""
        import subprocess
        import sys

        self._write_bad_doctrine_mission(project_dir)
        transient = project_dir / ".lore" / "codex" / "transient"
        before = set(transient.glob("health-*.md")) if transient.exists() else set()
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "from lore.api import health_check; health_check()",
            ],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"
        after = set(transient.glob("health-*.md")) if transient.exists() else set()
        assert after == before, (
            f"expected no new transient report, new files: {after - before}"
        )


# ---------------------------------------------------------------------------
# Rite Python API parity — the six functions, types, exception, and validator
# are importable from `lore.api`, and read_rite behaviour matches `rite show
# --json`. Per ADR-011 every CLI command is a thin wrapper over a self-
# contained lore.api function; per ADR-010 these names live in lore.api.__all__.
# Spec: conceptual-workflows-python-api / transient-rites-us-7.
# ---------------------------------------------------------------------------


_RITE_MAIN_YAML = """\
id: issue-refund
title: Issue a refund for a returned order
summary: Confirm the customer is reachable, then refund.
trigger: Customer requests a refund on a returned order.
nodes:
  - id: locate-order
    do: Find the order by id; confirm it is in 'returned' state.
    then: get-contact
  - id: get-contact
    use: read-contact-info
    then: review-contact
  - id: review-contact
    do: Decide whether contact details support a refund.
    then:
      - if: email and a current mailing address are present
        goto: do-refund
      - if: anything is missing or the address looks stale
        goto: request-update
  - id: do-refund
    do: Post the refund to billing. Record the txn id.
    then: refunded
  - id: request-update
    do: Ask the customer to confirm contact details first.
    then: contact-requested
conclusions:
  refunded:
    audience: customer-care
    response: Refund posted; share the transaction id.
  contact-requested:
    audience: customer-care
    response: Refund held pending a contact-details update.
"""

_RITE_SHARED_YAML = """\
id: read-contact-info
title: Read the user's contact information
do: |
  Open the user profile in admin. Read and report back:
    - email
    - phone
    - mailing address, with its last-confirmed date
"""


def _seed_rite_main(project_dir, name, text):
    path = project_dir / ".lore" / "rites" / "main" / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_rite_shared(project_dir, name, text):
    path = project_dir / ".lore" / "rites" / "shared" / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestPythonApiRiteFunctionsImportable:
    """The six rite functions import from lore.api and back the CLI."""

    def test_six_rite_functions_importable_from_api(self):
        from lore.api import (  # noqa: F401
            create_rite,
            delete_rite,
            read_rite,
            scan_rites,
            search_rites,
            update_rite,
        )

    def test_read_rite_matches_cli_show_json(self, project_dir):
        import json

        from lore.api import read_rite
        from lore.cli import main

        _seed_rite_main(project_dir, "issue-refund", _RITE_MAIN_YAML)
        _seed_rite_shared(project_dir, "read-contact-info", _RITE_SHARED_YAML)

        from click.testing import CliRunner

        rdir = project_dir / ".lore" / "rites"
        api_out = read_rite(rdir, "issue-refund")

        result = CliRunner().invoke(
            main, ["--json", "rite", "show", "issue-refund"]
        )
        assert result.exit_code == 0
        cli_out = json.loads(result.stdout)
        # nested-projects-spec — FR-16 / D-15: `rite show` resolves through
        # `find_rite`, which is `read_rite`'s record plus `origin`. The parity
        # this test exists for — the CLI adds no shaping of its own — holds.
        assert cli_out["rites"][0] == {**api_out, "origin": "self"}


class TestPythonApiRiteTypesExported:
    """Types, exception, and validator import from lore.api."""

    def test_types_exception_validator_importable(self):
        from lore.api import (  # noqa: F401
            Rite,
            RiteBranch,
            RiteConclusion,
            RiteError,
            RiteNode,
            SharedStep,
            validate_rite_id,
        )

    def test_rite_error_is_value_error(self):
        from lore.api import RiteError

        assert issubclass(RiteError, ValueError)

    def test_rite_from_dict_round_trips_read_rite(self, project_dir):
        from lore.api import Rite, read_rite

        _seed_rite_main(project_dir, "issue-refund", _RITE_MAIN_YAML)
        _seed_rite_shared(project_dir, "read-contact-info", _RITE_SHARED_YAML)

        rdir = project_dir / ".lore" / "rites"
        rite = Rite.from_dict(read_rite(rdir, "issue-refund"))
        assert rite.id == "issue-refund"
        assert rite.nodes
