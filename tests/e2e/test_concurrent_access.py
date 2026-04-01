"""E2E tests for concurrent access safety — WAL mode, busy timeout, FK enforcement.

Spec: conceptual-workflows-concurrent-access (lore codex show conceptual-workflows-concurrent-access)
"""

import sqlite3
import threading

import pytest

from lore.db import close_mission, get_connection, list_quests
from tests.conftest import insert_mission, insert_quest


class TestWALMode:
    """Every connection uses WAL journal mode."""

    def test_wal_journal_mode_active(self, project_dir):
        conn = get_connection(project_dir)
        try:
            row = conn.execute("PRAGMA journal_mode").fetchone()
            assert row[0] == "wal", f"Expected 'wal', got '{row[0]}'"
        finally:
            conn.close()

    def test_wal_persists_on_second_connection(self, project_dir):
        conn1 = get_connection(project_dir)
        conn1.close()

        conn2 = get_connection(project_dir)
        try:
            row = conn2.execute("PRAGMA journal_mode").fetchone()
            assert row[0] == "wal", f"Expected 'wal' on second connection, got '{row[0]}'"
        finally:
            conn2.close()


class TestBusyTimeout:
    """Busy timeout is set to 5000ms on every connection."""

    def test_busy_timeout_is_5000(self, project_dir):
        conn = get_connection(project_dir)
        try:
            row = conn.execute("PRAGMA busy_timeout").fetchone()
            assert row[0] == 5000, f"Expected 5000, got {row[0]}"
        finally:
            conn.close()


class TestForeignKeys:
    """Foreign key enforcement is enabled on every connection."""

    def test_foreign_keys_enabled(self, project_dir):
        conn = get_connection(project_dir)
        try:
            row = conn.execute("PRAGMA foreign_keys").fetchone()
            assert row[0] == 1, f"Expected 1 (ON), got {row[0]}"
        finally:
            conn.close()

    def test_foreign_key_violation_raises(self, project_dir):
        conn = get_connection(project_dir)
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO missions (id, quest_id, title, description, status, priority, created_at, updated_at) "
                    "VALUES ('m-test', 'q-nonexistent', 'Test', '', 'open', 2, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')"
                )
        finally:
            conn.close()


class TestConcurrentCloses:
    """Two concurrent mission closes both succeed without deadlock."""

    def test_two_concurrent_closes_no_deadlock(self, project_dir):
        insert_quest(project_dir, "q-ab01", "Auto-Close Quest", auto_close=1)
        insert_mission(
            project_dir, "q-ab01/m-aa01", "q-ab01", "Mission One", status="in_progress"
        )
        insert_mission(
            project_dir, "q-ab01/m-aa02", "q-ab01", "Mission Two", status="in_progress"
        )

        results = {}
        errors = {}

        def close_one(mid):
            try:
                results[mid] = close_mission(project_dir, mid)
            except Exception as exc:
                errors[mid] = exc

        t1 = threading.Thread(target=close_one, args=("q-ab01/m-aa01",))
        t2 = threading.Thread(target=close_one, args=("q-ab01/m-aa02",))
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        assert not t1.is_alive(), "Thread 1 timed out — possible deadlock"
        assert not t2.is_alive(), "Thread 2 timed out — possible deadlock"
        assert not errors, f"Thread exceptions: {errors}"

        assert results.get("q-ab01/m-aa01", {}).get("ok") is True
        assert results.get("q-ab01/m-aa02", {}).get("ok") is True

        conn = sqlite3.connect(str(project_dir / ".lore" / "lore.db"))
        try:
            row1 = conn.execute(
                "SELECT status FROM missions WHERE id = 'q-ab01/m-aa01'"
            ).fetchone()
            row2 = conn.execute(
                "SELECT status FROM missions WHERE id = 'q-ab01/m-aa02'"
            ).fetchone()
        finally:
            conn.close()

        assert row1[0] == "closed", f"Mission 1 not closed: {row1[0]}"
        assert row2[0] == "closed", f"Mission 2 not closed: {row2[0]}"

    def test_no_data_corruption_with_many_concurrent_writes(self, project_dir):
        insert_quest(project_dir, "q-many", "Many Writes Quest")
        mission_ids = []
        for i in range(5):
            mid = f"q-many/m-{i:04x}"
            insert_mission(project_dir, mid, "q-many", f"Mission {i}", status="in_progress")
            mission_ids.append(mid)

        results = {}
        errors = {}

        def do_close(mission_id, key):
            try:
                result = close_mission(project_dir, mission_id)
                results[key] = result
            except Exception as e:
                errors[key] = str(e)

        threads = [
            threading.Thread(target=do_close, args=(mid, f"m{i}"))
            for i, mid in enumerate(mission_ids)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Concurrent writes raised errors: {errors}"
        for key in results:
            assert results[key]["ok"] is True

        conn = get_connection(project_dir)
        try:
            for mid in mission_ids:
                row = conn.execute("SELECT status FROM missions WHERE id = ?", (mid,)).fetchone()
                assert row["status"] == "closed", f"{mid} was not closed"
        finally:
            conn.close()


class TestWALReaderNotBlocked:
    """WAL mode allows readers to see a consistent snapshot while a writer holds an IMMEDIATE lock."""

    def test_reader_sees_pre_commit_value_while_writer_holds_lock(self, project_dir):
        insert_quest(project_dir, "q-cd01", "Quest CD")
        insert_mission(
            project_dir, "q-cd01/m-cd01", "q-cd01", "Mission CD", status="in_progress"
        )

        writer = get_connection(project_dir)
        writer.execute("BEGIN IMMEDIATE")
        writer.execute(
            "UPDATE missions SET status = 'closed' WHERE id = 'q-cd01/m-cd01'"
        )

        reader = get_connection(project_dir)
        try:
            row = reader.execute(
                "SELECT status FROM missions WHERE id = 'q-cd01/m-cd01'"
            ).fetchone()
            assert row[0] == "in_progress", (
                f"Reader should see pre-commit value 'in_progress', got '{row[0]}'"
            )
        finally:
            reader.close()

        writer.commit()
        writer.close()

        reader2 = get_connection(project_dir)
        try:
            row2 = reader2.execute(
                "SELECT status FROM missions WHERE id = 'q-cd01/m-cd01'"
            ).fetchone()
            assert row2[0] == "closed", (
                f"After commit, reader should see 'closed', got '{row2[0]}'"
            )
        finally:
            reader2.close()


class TestNoLingeringConnections:
    """DB functions close their connection before returning — no lingering connections."""

    def test_exclusive_lock_possible_after_list_quests(self, project_dir):
        list_quests(project_dir)

        raw_conn = sqlite3.connect(str(project_dir / ".lore" / "lore.db"))
        try:
            raw_conn.execute("BEGIN EXCLUSIVE")
            raw_conn.rollback()
        except sqlite3.OperationalError as exc:
            pytest.fail(
                f"Could not acquire exclusive lock after list_quests — "
                f"lingering connection suspected: {exc}"
            )
        finally:
            raw_conn.close()

    def test_exclusive_lock_possible_after_close_mission(self, project_dir):
        insert_quest(project_dir, "q-cl", "Close Test Quest")
        insert_mission(project_dir, "q-cl/m-0001", "q-cl", "Mission 1", status="in_progress")

        result = close_mission(project_dir, "q-cl/m-0001")
        assert result["ok"] is True

        conn = sqlite3.connect(str(project_dir / ".lore" / "lore.db"))
        try:
            conn.execute("BEGIN EXCLUSIVE")
            conn.commit()
        finally:
            conn.close()
