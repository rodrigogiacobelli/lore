"""Migration v5 -> v6: Add board_messages table and idx_board_entity index."""

import sqlite3


def migrate(conn: sqlite3.Connection) -> None:
    """Create board_messages table and idx_board_entity index."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS board_messages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id  TEXT NOT NULL,
            message    TEXT NOT NULL,
            sender     TEXT,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
            deleted_at TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_board_entity ON board_messages(entity_id)")
