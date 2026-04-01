"""Migration v3 -> v4: Add mission_type column to missions.

DEFAULT 'knight' preserves existing behavior for missions created before
this feature. The CHECK constraint limits values to 'knight', 'constable',
and 'human'.
"""

import sqlite3


def migrate(conn: sqlite3.Connection) -> None:
    """Add mission_type TEXT column to missions with DEFAULT 'knight'."""
    cursor = conn.execute("PRAGMA table_info(missions)")
    columns = {row[1] for row in cursor.fetchall()}
    if "mission_type" not in columns:
        conn.execute(
            "ALTER TABLE missions ADD COLUMN mission_type TEXT NOT NULL DEFAULT 'knight' "
            "CHECK (mission_type IN ('knight', 'constable', 'human'))"
        )
