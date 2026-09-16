"""Unit tests for the v6 -> v7 migration.

Workflow: conceptual-workflows-schema-migrations
  (lore codex show conceptual-workflows-schema-migrations)

v7 drops ``missions.knight``, puts ``missions.doctrine_mission TEXT`` in its
place and rewrites the ``knight`` ``mission_type`` token to ``agent``. The
column is dropped by the rename-create-copy-drop pattern ``v4_to_v5`` already
uses: ``ALTER TABLE ... DROP COLUMN`` needs SQLite >= 3.35 and would leave the
column order disagreeing with ``schema.sql``.

Nothing is mocked: every test opens a real hand-built v6 database.
"""

from __future__ import annotations

import sqlite3

import pytest

from lore.migrations import v6_to_v7


V6_SCHEMA = """
CREATE TABLE lore_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT INTO lore_meta (key, value) VALUES ('schema_version', '6');

CREATE TABLE quests (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL
);

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
    mission_type TEXT
);

CREATE INDEX idx_missions_quest_id ON missions(quest_id);
CREATE INDEX idx_missions_status_priority ON missions(status, priority, created_at);
"""


@pytest.fixture()
def v6(tmp_path):
    """A real v6 database holding one row of each interesting shape."""
    conn = sqlite3.connect(str(tmp_path / "v6.db"))
    conn.row_factory = sqlite3.Row
    conn.executescript(V6_SCHEMA)
    conn.execute("INSERT INTO quests (id, title) VALUES ('q-aaaa', 'Q')")
    rows = [
        ("q-aaaa/m-1111", "knight", "tdd-feature/recon.md"),
        ("q-aaaa/m-2222", "constable", None),
        ("q-aaaa/m-3333", "human", "some-knight"),
        ("q-aaaa/m-4444", None, None),
    ]
    for mission_id, mission_type, knight in rows:
        conn.execute(
            "INSERT INTO missions (id, quest_id, title, priority, knight, "
            "created_at, updated_at, mission_type) "
            "VALUES (?, 'q-aaaa', 'M', 2, ?, '2026-01-01', '2026-01-01', ?)",
            (mission_id, knight, mission_type),
        )
    conn.commit()
    yield conn
    conn.close()


def _columns(conn) -> list[str]:
    return [r["name"] for r in conn.execute("PRAGMA table_info(missions)")]


def _row(conn, mission_id):
    return conn.execute(
        "SELECT * FROM missions WHERE id = ?", (mission_id,)
    ).fetchone()


def test_the_knight_column_is_gone(v6):
    v6_to_v7.migrate(v6)

    assert "knight" not in _columns(v6)


def test_doctrine_mission_takes_the_position_knight_held(v6):
    before = _columns(v6)
    v6_to_v7.migrate(v6)

    after = _columns(v6)
    assert after == [
        "doctrine_mission" if name == "knight" else name for name in before
    ]


def test_the_stored_value_is_dropped(v6):
    """FR-23: the new column starts empty on every row.

    A stored knight name is not a valid ``<doctrine-id>/<mission-id>``
    reference and can never resolve, so carrying it across would put every
    upgraded project into health errors on missions nobody touched.
    """
    v6_to_v7.migrate(v6)

    assert _row(v6, "q-aaaa/m-1111")["doctrine_mission"] is None
    assert _row(v6, "q-aaaa/m-3333")["doctrine_mission"] is None
    assert _row(v6, "q-aaaa/m-2222")["doctrine_mission"] is None


def test_the_knight_mission_type_token_becomes_agent(v6):
    v6_to_v7.migrate(v6)

    assert _row(v6, "q-aaaa/m-1111")["mission_type"] == "agent"


def test_every_other_mission_type_token_is_untouched(v6):
    v6_to_v7.migrate(v6)

    assert _row(v6, "q-aaaa/m-2222")["mission_type"] == "constable"
    assert _row(v6, "q-aaaa/m-3333")["mission_type"] == "human"
    assert _row(v6, "q-aaaa/m-4444")["mission_type"] is None


def test_no_row_is_lost(v6):
    v6_to_v7.migrate(v6)

    assert v6.execute("SELECT COUNT(*) FROM missions").fetchone()[0] == 4


def test_both_indexes_exist_afterwards(v6):
    v6_to_v7.migrate(v6)

    names = {
        r[0]
        for r in v6.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'missions'"
        )
    }
    assert {"idx_missions_quest_id", "idx_missions_status_priority"} <= names


def test_the_scratch_table_is_dropped(v6):
    v6_to_v7.migrate(v6)

    names = {
        r[0] for r in v6.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert "missions_old" not in names


def test_the_migration_neither_commits_nor_writes_the_version(v6):
    """The runner owns the transaction and the ``schema_version`` write."""
    v6.execute("BEGIN IMMEDIATE")
    v6_to_v7.migrate(v6)

    assert v6.in_transaction
    version = v6.execute(
        "SELECT value FROM lore_meta WHERE key = 'schema_version'"
    ).fetchone()[0]
    assert version == "6"


def test_the_module_exposes_exactly_migrate():
    assert callable(v6_to_v7.migrate)
    assert [
        name
        for name in vars(v6_to_v7)
        if not name.startswith("_") and callable(vars(v6_to_v7)[name])
    ] == ["migrate"]
