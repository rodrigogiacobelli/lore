"""Migration v1 -> v2: Add deleted_at columns for soft-delete support."""

import sqlite3


def migrate(conn: sqlite3.Connection) -> None:
    """Add deleted_at TEXT column to quests, missions, and dependencies."""
    conn.execute("ALTER TABLE quests ADD COLUMN deleted_at TEXT")
    conn.execute("ALTER TABLE missions ADD COLUMN deleted_at TEXT")
    conn.execute("ALTER TABLE dependencies ADD COLUMN deleted_at TEXT")
