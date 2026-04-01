"""Migration v4 -> v5: Remove NOT NULL, DEFAULT 'knight', and CHECK constraint from mission_type.

SQLite does not support ALTER TABLE ... DROP CONSTRAINT or ALTER COLUMN.
The rename-create-copy-drop pattern is used to recreate the missions table
with mission_type as a plain nullable TEXT field.
"""

import sqlite3


def migrate(conn: sqlite3.Connection) -> None:
    """Remove NOT NULL, DEFAULT, and CHECK constraint from mission_type column."""
    conn.execute("ALTER TABLE missions RENAME TO missions_old")
    conn.execute("""
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
        )
    """)
    conn.execute(
        "INSERT INTO missions SELECT id, quest_id, title, description, status, "
        "priority, knight, block_reason, created_at, updated_at, closed_at, "
        "deleted_at, mission_type FROM missions_old"
    )
    conn.execute("DROP TABLE missions_old")
    conn.execute("CREATE INDEX idx_missions_quest_id ON missions(quest_id)")
    conn.execute(
        "CREATE INDEX idx_missions_status_priority ON missions(status, priority, created_at)"
    )
