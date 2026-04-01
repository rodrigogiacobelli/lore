"""E2E tests for schema migrations — version detection and sequential application.

Spec: conceptual-workflows-schema-migrations (lore codex show conceptual-workflows-schema-migrations)
"""

import sqlite3
import sys
import types

import pytest

import lore.db as lore_db
from lore.db import add_board_message, get_board_messages, get_connection
from tests.conftest import db_conn


# ---------------------------------------------------------------------------
# Helper: downgrade schema version in an existing DB
# ---------------------------------------------------------------------------


def _set_schema_version(project_dir, version: int) -> None:
    """Overwrite the schema_version in lore_meta to simulate a downgrade."""
    conn = sqlite3.connect(str(project_dir / ".lore" / "lore.db"))
    try:
        conn.execute(
            "UPDATE lore_meta SET value = ? WHERE key = 'schema_version'",
            (str(version),),
        )
        conn.commit()
    finally:
        conn.close()


class TestFreshInitSchemaVersion:
    """After lore init, schema_version is at the current supported version."""

    def test_fresh_init_schema_version_is_6(self, project_dir):
        conn = db_conn(project_dir)
        try:
            row = conn.execute(
                "SELECT value FROM lore_meta WHERE key = 'schema_version'"
            ).fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row[0] == "6", f"Expected schema_version '6', got '{row[0]}'"


class TestAutoMigrationOnConnect:
    """get_connection auto-runs migration when DB is behind the current version."""

    def test_migration_runs_when_behind(self, project_dir, monkeypatch):
        _set_schema_version(project_dir, 1)

        migration_ran = []

        fake_mod = types.ModuleType("lore.migrations.v1_to_v2")

        def fake_migrate(conn):
            conn.execute("CREATE TABLE IF NOT EXISTS _test_migration_ran (marker TEXT)")
            migration_ran.append("v1_to_v2")

        fake_mod.migrate = fake_migrate

        module_key = "lore.migrations.v1_to_v2"
        old_module = sys.modules.get(module_key)
        sys.modules[module_key] = fake_mod
        monkeypatch.setattr(lore_db, "SCHEMA_VERSION", 2, raising=False)

        try:
            conn = get_connection(project_dir)
            conn.close()
        finally:
            if old_module is None:
                sys.modules.pop(module_key, None)
            else:
                sys.modules[module_key] = old_module

        assert migration_ran == ["v1_to_v2"], f"Migration did not run: {migration_ran}"

        raw = db_conn(project_dir)
        try:
            row = raw.execute(
                "SELECT value FROM lore_meta WHERE key = 'schema_version'"
            ).fetchone()
        finally:
            raw.close()
        assert row[0] == "2"


class TestSequentialMigrations:
    """Multiple pending migrations run in strict version order."""

    def test_sequential_order(self, project_dir, monkeypatch):
        _set_schema_version(project_dir, 1)

        execution_order = []

        def make_fake_mod(name, label):
            mod = types.ModuleType(name)

            def _migrate(conn, _label=label):
                execution_order.append(_label)

            mod.migrate = _migrate
            return mod

        fake_v1_to_v2 = make_fake_mod("lore.migrations.v1_to_v2", "v1_to_v2")
        fake_v2_to_v3 = make_fake_mod("lore.migrations.v2_to_v3", "v2_to_v3")

        saved = {}
        for key in ("lore.migrations.v1_to_v2", "lore.migrations.v2_to_v3"):
            saved[key] = sys.modules.get(key)

        sys.modules["lore.migrations.v1_to_v2"] = fake_v1_to_v2
        sys.modules["lore.migrations.v2_to_v3"] = fake_v2_to_v3
        monkeypatch.setattr(lore_db, "SCHEMA_VERSION", 3, raising=False)

        try:
            conn = get_connection(project_dir)
            conn.close()
        finally:
            for key, val in saved.items():
                if val is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = val

        assert execution_order == ["v1_to_v2", "v2_to_v3"], (
            f"Unexpected execution order: {execution_order}"
        )

        raw = db_conn(project_dir)
        try:
            row = raw.execute(
                "SELECT value FROM lore_meta WHERE key = 'schema_version'"
            ).fetchone()
        finally:
            raw.close()
        assert row[0] == "3"


class TestFailedMigrationRollback:
    """A failed migration rolls back — schema_version remains unchanged."""

    def test_failed_migration_rolls_back(self, project_dir, monkeypatch):
        _set_schema_version(project_dir, 1)

        fake_mod = types.ModuleType("lore.migrations.v1_to_v2")

        def bad_migrate(conn):
            conn.execute("CREATE TABLE _should_not_exist (x TEXT)")
            raise RuntimeError("Intentional migration failure")

        fake_mod.migrate = bad_migrate

        module_key = "lore.migrations.v1_to_v2"
        old_module = sys.modules.get(module_key)
        sys.modules[module_key] = fake_mod
        monkeypatch.setattr(lore_db, "SCHEMA_VERSION", 2, raising=False)

        try:
            with pytest.raises(RuntimeError, match="Intentional migration failure"):
                conn = get_connection(project_dir)
                conn.close()
        finally:
            if old_module is None:
                sys.modules.pop(module_key, None)
            else:
                sys.modules[module_key] = old_module

        raw = db_conn(project_dir)
        try:
            row = raw.execute(
                "SELECT value FROM lore_meta WHERE key = 'schema_version'"
            ).fetchone()
            table_exists = raw.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='_should_not_exist'"
            ).fetchone()
        finally:
            raw.close()

        assert row[0] == "1", f"Expected schema_version '1', got '{row[0]}'"
        assert table_exists is None, "_should_not_exist table should not exist (rollback)"


class TestUnknownSchemaVersion:
    """A DB schema newer than supported raises RuntimeError."""

    def test_future_version_raises(self, project_dir):
        _set_schema_version(project_dir, 9999)

        with pytest.raises(RuntimeError, match="newer than supported"):
            conn = get_connection(project_dir)
            conn.close()


class TestV5ToV6Migration:
    """v5 to v6 migration adds board_messages table and index."""

    def test_v5_to_v6_creates_board_messages_and_index(self, project_dir):
        raw = sqlite3.connect(str(project_dir / ".lore" / "lore.db"))
        try:
            raw.execute("DROP TABLE IF EXISTS board_messages")
            raw.execute("DROP INDEX IF EXISTS idx_board_entity")
            raw.commit()
        finally:
            raw.close()

        _set_schema_version(project_dir, 5)

        conn = get_connection(project_dir)
        try:
            table_row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='board_messages'"
            ).fetchone()
            assert table_row is not None, "board_messages table not created by v5 to v6"

            idx_row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_board_entity'"
            ).fetchone()
            assert idx_row is not None, "idx_board_entity index not created by v5 to v6"
        finally:
            conn.close()

        raw = db_conn(project_dir)
        try:
            row = raw.execute(
                "SELECT value FROM lore_meta WHERE key = 'schema_version'"
            ).fetchone()
        finally:
            raw.close()
        assert row[0] == "6"

        _insert_quest_direct(project_dir)
        result = add_board_message(project_dir, "q-ab01", "Hello board")
        assert result.get("ok") is True, f"add_board_message failed: {result}"

        messages = get_board_messages(project_dir, "q-ab01")
        assert len(messages) == 1
        assert messages[0]["message"] == "Hello board"


def _insert_quest_direct(project_dir):
    """Insert a minimal quest row for use in migration tests."""
    conn = sqlite3.connect(str(project_dir / ".lore" / "lore.db"))
    try:
        conn.execute(
            "INSERT OR IGNORE INTO quests (id, title, description, status, priority, created_at, updated_at, auto_close) "
            "VALUES ('q-ab01', 'Test Quest', '', 'open', 2, '2025-01-01T00:00:00Z', '2025-01-01T00:00:00Z', 0)"
        )
        conn.commit()
    finally:
        conn.close()


class TestV4ToV5Migration:
    """v4 to v5 migration converts mission_type from CHECK-constrained enum to nullable free-form."""

    def test_v4_to_v5_preserves_mission_types(self, project_dir):
        raw = sqlite3.connect(str(project_dir / ".lore" / "lore.db"))
        try:
            raw.execute("DELETE FROM missions")
            raw.execute("DROP INDEX IF EXISTS idx_missions_quest_id")
            raw.execute("DROP INDEX IF EXISTS idx_missions_status_priority")
            raw.execute("ALTER TABLE missions RENAME TO missions_v5")
            raw.execute("""
                CREATE TABLE missions (
                    id           TEXT PRIMARY KEY,
                    quest_id     TEXT REFERENCES quests(id),
                    title        TEXT NOT NULL,
                    description  TEXT NOT NULL DEFAULT '',
                    status       TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open', 'in_progress', 'blocked', 'closed')),
                    priority     INTEGER NOT NULL DEFAULT 2 CHECK (priority BETWEEN 0 AND 4),
                    knight       TEXT,
                    block_reason TEXT,
                    created_at   TEXT NOT NULL,
                    updated_at   TEXT NOT NULL,
                    closed_at    TEXT,
                    deleted_at   TEXT,
                    mission_type TEXT NOT NULL DEFAULT 'knight'
                        CHECK (mission_type IN ('knight', 'constable', 'human'))
                )
            """)
            raw.execute(
                "INSERT OR IGNORE INTO quests (id, title, description, status, priority, created_at, updated_at, auto_close) "
                "VALUES ('q-ab01', 'Test Quest', '', 'open', 2, '2025-01-01T00:00:00Z', '2025-01-01T00:00:00Z', 0)"
            )
            for mid, mtype in [
                ("q-ab01/m-aa01", "knight"),
                ("q-ab01/m-aa02", "constable"),
                ("q-ab01/m-aa03", "human"),
            ]:
                raw.execute(
                    "INSERT INTO missions (id, quest_id, title, description, status, priority, created_at, updated_at, mission_type) "
                    "VALUES (?, 'q-ab01', ?, '', 'open', 2, '2025-01-01T00:00:00Z', '2025-01-01T00:00:00Z', ?)",
                    (mid, f"Mission {mtype}", mtype),
                )
            raw.commit()
            raw.execute("DROP TABLE missions_v5")
            raw.commit()
        finally:
            raw.close()

        _set_schema_version(project_dir, 4)

        conn = get_connection(project_dir)
        try:
            rows = conn.execute(
                "SELECT id, mission_type FROM missions ORDER BY id"
            ).fetchall()
        finally:
            conn.close()

        types_by_id = {row["id"]: row["mission_type"] for row in rows}
        assert types_by_id.get("q-ab01/m-aa01") == "knight"
        assert types_by_id.get("q-ab01/m-aa02") == "constable"
        assert types_by_id.get("q-ab01/m-aa03") == "human"

        raw2 = sqlite3.connect(str(project_dir / ".lore" / "lore.db"))
        try:
            raw2.execute(
                "INSERT INTO missions (id, quest_id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-ab01/m-aa09', 'q-ab01', 'New', '', 'open', 2, '2025-01-01T00:00:00Z', '2025-01-01T00:00:00Z')"
            )
            raw2.commit()
            new_row = raw2.execute(
                "SELECT mission_type FROM missions WHERE id = 'q-ab01/m-aa09'"
            ).fetchone()
            assert new_row[0] is None, "mission_type should be NULL after v4 to v5"
        finally:
            raw2.close()


class TestV2ToV3Migration:
    """v2 to v3 migration adds auto_close column and sets existing quests to auto_close=1."""

    def test_v2_to_v3_sets_auto_close_for_existing_quests(self, project_dir):
        raw = sqlite3.connect(str(project_dir / ".lore" / "lore.db"))
        try:
            raw.execute("ALTER TABLE quests RENAME TO quests_v3")
            raw.execute("""
                CREATE TABLE quests (
                    id          TEXT PRIMARY KEY,
                    title       TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'closed')),
                    priority    INTEGER NOT NULL DEFAULT 2 CHECK (priority BETWEEN 0 AND 4),
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL,
                    closed_at   TEXT,
                    deleted_at  TEXT
                )
            """)
            raw.execute(
                "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-ab01', 'Old Quest', '', 'open', 2, '2025-01-01T00:00:00Z', '2025-01-01T00:00:00Z')"
            )
            raw.commit()
            raw.execute("DROP TABLE quests_v3")
            raw.commit()
        finally:
            raw.close()

        _set_schema_version(project_dir, 2)

        from lore.migrations.v2_to_v3 import migrate as v2_to_v3_migrate

        raw2 = sqlite3.connect(str(project_dir / ".lore" / "lore.db"))
        try:
            v2_to_v3_migrate(raw2)
            raw2.commit()
        finally:
            raw2.close()

        raw3 = sqlite3.connect(str(project_dir / ".lore" / "lore.db"))
        try:
            row = raw3.execute(
                "SELECT auto_close FROM quests WHERE id = 'q-ab01'"
            ).fetchone()
        finally:
            raw3.close()
        assert row is not None
        assert row[0] == 1, f"Existing quest should have auto_close=1, got {row[0]}"

        # After v2 to v3, the column DEFAULT is 1 — new rows also get auto_close=1.
        # This is documented behaviour per the migration module's docstring.
        _set_schema_version(project_dir, 2)
        conn = get_connection(project_dir)
        try:
            conn.execute(
                "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-ab02', 'New Quest', '', 'open', 2, '2025-01-01T00:00:00Z', '2025-01-01T00:00:00Z')"
            )
            conn.commit()
            new_row = conn.execute(
                "SELECT auto_close FROM quests WHERE id = 'q-ab02'"
            ).fetchone()
        finally:
            conn.close()
        assert new_row[0] == 1, (
            f"After v2 to v3 migration, new quests get auto_close=1 (column DEFAULT 1), got {new_row[0]}"
        )
