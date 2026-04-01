"""Migration v2 -> v3: Add auto_close column to quests.

DEFAULT 1 preserves existing behavior (auto-close enabled) for quests
created before this feature. Fresh schema.sql uses DEFAULT 0 so new
quests default to manual close.
"""

import sqlite3


def migrate(conn: sqlite3.Connection) -> None:
    """Add auto_close INTEGER column to quests with DEFAULT 1 for existing rows."""
    # Check if column already exists (idempotent for databases created with v3 schema)
    cursor = conn.execute("PRAGMA table_info(quests)")
    columns = {row[1] for row in cursor.fetchall()}
    if "auto_close" not in columns:
        conn.execute(
            "ALTER TABLE quests ADD COLUMN auto_close INTEGER NOT NULL DEFAULT 1 "
            "CHECK (auto_close IN (0, 1))"
        )
    else:
        # Column exists (e.g., fresh v3 schema downgraded to v2 for testing).
        # Ensure existing quests preserve old auto-close behavior (enabled).
        conn.execute("UPDATE quests SET auto_close = 1")
