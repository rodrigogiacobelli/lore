"""Ready queue logic."""

import sqlite3
from pathlib import Path

from lore.db import get_connection


def get_ready_missions(project_root: Path, count: int = 1) -> list[sqlite3.Row]:
    """Return unblocked open missions sorted by priority then created_at.

    Uses the priority queue query from database.md: only open missions with
    no unresolved (non-closed) blocking dependencies are returned.
    """
    conn = get_connection(project_root)
    try:
        cursor = conn.execute(
            "SELECT m.* FROM missions m "
            "WHERE m.status = 'open' "
            "  AND m.deleted_at IS NULL "
            "  AND NOT EXISTS ( "
            "    SELECT 1 FROM dependencies d "
            "    JOIN missions dep ON dep.id = d.to_id "
            "    WHERE d.from_id = m.id "
            "      AND d.type = 'blocks' "
            "      AND d.deleted_at IS NULL "
            "      AND dep.status != 'closed' "
            "      AND dep.deleted_at IS NULL "
            "  ) "
            "ORDER BY m.priority ASC, m.created_at ASC "
            "LIMIT ?",
            (count,),
        )
        return cursor.fetchall()
    finally:
        conn.close()
