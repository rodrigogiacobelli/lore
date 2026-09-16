"""Migration v6 -> v7: ``missions.knight`` is dropped, ``doctrine_mission`` added.

The Knight entity is gone, and a mission now points at a doctrine mission file
by the reference ``<doctrine-id>/<mission-id>``. The new column starts empty
(FR-23): a stored knight value is a bare file name such as ``tech-writer`` or
``feature-implementation/scout.md``, which is not a valid doctrine mission
reference and can never resolve. Carrying those across would put every upgraded
project into ``lore health --scope doctrines`` **errors** on missions its
maintainer never touched, contradicting the decision that an upgrade warns
rather than turns CI red. The audit trail of which persona a historical mission
ran under lives on disk instead: ``reconcile`` names retired and orphaned
knight files in its report (FR-24).

``ALTER TABLE ... DROP COLUMN`` needs SQLite >= 3.35 and would leave the column
order disagreeing with ``schema.sql``, so this uses the rename-create-copy-drop
pattern ``v4_to_v5`` established.

The ``knight`` ``mission_type`` token becomes ``agent`` in the same pass. That
one ``UPDATE`` is the only code anywhere that reads the token: ``mission_type``
is stored and exposed, never interpreted (``decisions-004``).
"""

import sqlite3


def migrate(conn: sqlite3.Connection) -> None:
    """Replace the column with an empty one and rewrite the token."""
    conn.execute("ALTER TABLE missions RENAME TO missions_old")
    conn.execute("""
        CREATE TABLE missions (
            id               TEXT PRIMARY KEY,
            quest_id         TEXT REFERENCES quests(id),
            title            TEXT NOT NULL,
            description      TEXT NOT NULL DEFAULT '',
            status           TEXT NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'in_progress', 'blocked', 'closed')),
            priority         INTEGER NOT NULL DEFAULT 2 CHECK (priority BETWEEN 0 AND 4),
            doctrine_mission TEXT,
            block_reason     TEXT,
            created_at       TEXT NOT NULL,
            updated_at       TEXT NOT NULL,
            closed_at        TEXT,
            deleted_at       TEXT,
            mission_type     TEXT
        )
    """)
    conn.execute(
        "INSERT INTO missions SELECT id, quest_id, title, description, status, "
        "priority, NULL, block_reason, created_at, updated_at, closed_at, "
        "deleted_at, mission_type FROM missions_old"
    )
    conn.execute("DROP TABLE missions_old")
    conn.execute("UPDATE missions SET mission_type = 'agent' WHERE mission_type = 'knight'")
    conn.execute("CREATE INDEX idx_missions_quest_id ON missions(quest_id)")
    conn.execute(
        "CREATE INDEX idx_missions_status_priority ON missions(status, priority, created_at)"
    )
