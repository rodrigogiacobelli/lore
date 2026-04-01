"""SQLite schema and operations."""

import importlib
import sqlite3
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

from lore import paths
from lore import validators
from lore.ids import generate_id

SCHEMA_VERSION = 6


def get_schema_sql() -> str:
    """Read the DDL from the bundled schema.sql file."""
    return resources.files("lore.defaults").joinpath("schema.sql").read_text()


def init_database(db_path: Path) -> str:
    """Initialize the SQLite database with the full schema.

    Returns a status string: 'created', 'existing', or 'reinitialized'.
    """
    db_existed = db_path.exists()

    if db_existed:
        # Check if lore_meta table exists (corruption check)
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='lore_meta'"
            )
            has_meta = cursor.fetchone() is not None
        finally:
            conn.close()

        if has_meta:
            return "existing"

        # Corrupted: lore_meta missing — reinitialize from scratch
        db_path.unlink()
        _create_database(db_path)
        return "reinitialized"

    _create_database(db_path)
    return "created"


def _create_database(db_path: Path) -> None:
    """Create a fresh database with the full schema."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(get_schema_sql())
    finally:
        conn.close()


def get_connection(project_root: Path) -> sqlite3.Connection:
    """Open a connection to the project database with standard pragmas.

    Checks schema version and runs any pending migrations before returning.
    """
    db_path = paths.db_path(project_root)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    _run_migrations(conn)
    return conn


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Check schema version and run pending migrations sequentially."""
    cursor = conn.execute(
        "SELECT value FROM lore_meta WHERE key = 'schema_version'"
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("Missing schema_version in lore_meta")
    current = int(row[0])

    if current == SCHEMA_VERSION:
        return

    if current > SCHEMA_VERSION:
        raise RuntimeError(
            f"Database schema version {current} is newer than "
            f"supported version {SCHEMA_VERSION}. Upgrade Lore."
        )

    # Run migrations sequentially from current to SCHEMA_VERSION
    conn.execute("BEGIN IMMEDIATE")
    try:
        # Re-check version after acquiring lock (another connection may have migrated)
        cursor = conn.execute(
            "SELECT value FROM lore_meta WHERE key = 'schema_version'"
        )
        row = cursor.fetchone()
        current = int(row[0])
        if current >= SCHEMA_VERSION:
            conn.rollback()
            return

        for from_ver in range(current, SCHEMA_VERSION):
            to_ver = from_ver + 1
            module_name = f"lore.migrations.v{from_ver}_to_v{to_ver}"
            try:
                mod = importlib.import_module(module_name)
            except ImportError:
                raise RuntimeError(
                    f"Migration module {module_name} not found"
                )
            if not hasattr(mod, "migrate"):
                raise RuntimeError(
                    f"Migration module {module_name} has no migrate() function"
                )
            mod.migrate(conn)
            conn.execute(
                "UPDATE lore_meta SET value = ? WHERE key = 'schema_version'",
                (str(to_ver),),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _now_utc() -> str:
    """Return current UTC time as ISO 8601 string with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def list_quests(project_root: Path, include_closed: bool = False) -> list[sqlite3.Row]:
    """List quests sorted by priority asc, then created_at asc."""
    conn = get_connection(project_root)
    try:
        if include_closed:
            cursor = conn.execute(
                "SELECT * FROM quests WHERE deleted_at IS NULL ORDER BY priority ASC, created_at ASC"
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM quests WHERE status != 'closed' AND deleted_at IS NULL "
                "ORDER BY priority ASC, created_at ASC"
            )
        return cursor.fetchall()
    finally:
        conn.close()


def get_quest(project_root: Path, quest_id: str) -> sqlite3.Row | None:
    """Fetch a single quest by ID (excludes soft-deleted)."""
    conn = get_connection(project_root)
    try:
        cursor = conn.execute(
            "SELECT * FROM quests WHERE id = ? AND deleted_at IS NULL",
            (quest_id,),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def get_deleted_at(project_root: Path, entity_id: str) -> str | None:
    """Return the deleted_at timestamp if the entity is soft-deleted, else None.

    Determines the table from the ID format: 'q-xxxx' for quests,
    anything containing 'm-' for missions.
    """
    table = "quests" if entity_id.startswith("q-") and "/" not in entity_id else "missions"
    conn = get_connection(project_root)
    try:
        cursor = conn.execute(
            f"SELECT deleted_at FROM {table} WHERE id = ? AND deleted_at IS NOT NULL",
            (entity_id,),
        )
        row = cursor.fetchone()
        return row["deleted_at"] if row else None
    finally:
        conn.close()


def get_missions_for_quest(project_root: Path, quest_id: str) -> list[sqlite3.Row]:
    """Fetch missions for a quest, sorted by status group, priority, created_at.

    Status order: open/in_progress first, blocked next, closed last.
    """
    conn = get_connection(project_root)
    try:
        cursor = conn.execute(
            "SELECT * FROM missions WHERE quest_id = ? AND deleted_at IS NULL "
            "ORDER BY "
            "  CASE status "
            "    WHEN 'open' THEN 0 "
            "    WHEN 'in_progress' THEN 0 "
            "    WHEN 'blocked' THEN 1 "
            "    WHEN 'closed' THEN 2 "
            "  END ASC, "
            "  priority ASC, "
            "  created_at ASC",
            (quest_id,),
        )
        return cursor.fetchall()
    finally:
        conn.close()


def list_missions(
    project_root: Path,
    quest_id: str | None = None,
    include_closed: bool = False,
) -> dict[str | None, list[sqlite3.Row]]:
    """List missions grouped by quest_id.

    Returns a dict mapping quest_id (or None for standalone) to lists of missions.
    Sorted by priority ascending, then created_at ascending within each group.
    If quest_id is specified, only that quest's missions are returned.
    If include_closed is False, only active (open, in_progress, blocked) missions are returned.
    """
    conn = get_connection(project_root)
    try:
        conditions = ["m.deleted_at IS NULL"]
        params: list[str] = []

        if quest_id is not None:
            conditions.append("m.quest_id = ?")
            params.append(quest_id)

        if not include_closed:
            conditions.append("m.status IN ('open', 'in_progress', 'blocked')")

        where = "WHERE " + " AND ".join(conditions)

        cursor = conn.execute(
            f"SELECT m.* FROM missions m {where} ORDER BY priority ASC, created_at ASC",
            params,
        )
        rows = cursor.fetchall()

        # Group by quest_id
        grouped: dict[str | None, list[sqlite3.Row]] = {}
        for row in rows:
            grouped.setdefault(row["quest_id"], []).append(row)

        return grouped
    finally:
        conn.close()


def get_mission(project_root: Path, mission_id: str) -> sqlite3.Row | None:
    """Fetch a single mission by ID (excludes soft-deleted)."""
    conn = get_connection(project_root)
    try:
        cursor = conn.execute(
            "SELECT * FROM missions WHERE id = ? AND deleted_at IS NULL",
            (mission_id,),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def get_mission_depends_on(project_root: Path, mission_id: str) -> list[str]:
    """Return IDs of missions that this mission depends on (needs done first)."""
    conn = get_connection(project_root)
    try:
        cursor = conn.execute(
            "SELECT to_id FROM dependencies WHERE from_id = ? AND deleted_at IS NULL", (mission_id,)
        )
        return [row["to_id"] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_mission_blocks(project_root: Path, mission_id: str) -> list[str]:
    """Return IDs of missions that this mission blocks (waiting on this one)."""
    conn = get_connection(project_root)
    try:
        cursor = conn.execute(
            "SELECT from_id FROM dependencies WHERE to_id = ? AND deleted_at IS NULL", (mission_id,)
        )
        return [row["from_id"] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_mission_depends_on_details(project_root: Path, mission_id: str) -> list[dict]:
    """Return details (id, title, status) of missions that this mission depends on."""
    conn = get_connection(project_root)
    try:
        cursor = conn.execute(
            "SELECT d.to_id, m.id, m.title, m.status, m.deleted_at FROM dependencies d "
            "LEFT JOIN missions m ON d.to_id = m.id "
            "WHERE d.from_id = ? AND d.deleted_at IS NULL",
            (mission_id,),
        )
        return [
            {
                "id": row["to_id"],
                "title": row["title"],
                "status": row["status"],
                "deleted_at": row["deleted_at"],
            }
            for row in cursor.fetchall()
        ]
    finally:
        conn.close()


def get_mission_blocks_details(project_root: Path, mission_id: str) -> list[dict]:
    """Return details (id, title, status) of missions that depend on this mission."""
    conn = get_connection(project_root)
    try:
        cursor = conn.execute(
            "SELECT d.from_id, m.id, m.title, m.status, m.deleted_at FROM dependencies d "
            "LEFT JOIN missions m ON d.from_id = m.id "
            "WHERE d.to_id = ? AND d.deleted_at IS NULL",
            (mission_id,),
        )
        return [
            {
                "id": row["from_id"],
                "title": row["title"],
                "status": row["status"],
                "deleted_at": row["deleted_at"],
            }
            for row in cursor.fetchall()
        ]
    finally:
        conn.close()


def get_all_dependencies_for_quest(project_root: Path, quest_id: str) -> list[dict]:
    """Return all active dependency edges where from_id belongs to the quest.

    Returns a list of {"from_id": ..., "to_id": ...} dicts.
    Cross-quest upstream nodes (to_id belonging to a different quest) are included.
    """
    conn = get_connection(project_root)
    try:
        cursor = conn.execute(
            "SELECT d.from_id, d.to_id "
            "FROM dependencies d "
            "JOIN missions m ON m.id = d.from_id "
            "WHERE m.quest_id = ? "
            "AND m.deleted_at IS NULL "
            "AND d.deleted_at IS NULL",
            (quest_id,),
        )
        return [{"from_id": row["from_id"], "to_id": row["to_id"]} for row in cursor.fetchall()]
    finally:
        conn.close()


def claim_mission(project_root: Path, mission_id: str) -> dict:
    """Claim a mission by transitioning it from open to in_progress.

    Returns a dict with keys: ok (bool), status (str|None), error (str|None),
    quest_id (str|None), quest_status_changed (bool), quest_status (str|None).
    Also recomputes parent quest status if the mission belongs to a quest.
    """
    # Step 1: ID format validation before any DB access
    err = validators.validate_mission_id(mission_id)
    if err:
        return {"ok": False, "status": None, "error": err,
                "quest_id": None, "quest_status_changed": False, "quest_status": None}

    conn = get_connection(project_root)
    try:
        conn.execute("BEGIN IMMEDIATE")

        cursor = conn.execute("SELECT * FROM missions WHERE id = ?", (mission_id,))
        mission = cursor.fetchone()
        if mission is None:
            conn.rollback()
            return {"ok": False, "status": None, "error": f'Mission "{mission_id}" not found',
                    "quest_id": None, "quest_status_changed": False, "quest_status": None}

        current_status = mission["status"]

        # Idempotent: already in_progress
        if current_status == "in_progress":
            conn.rollback()
            return {"ok": True, "status": "in_progress", "error": None,
                    "quest_id": None, "quest_status_changed": False, "quest_status": None}

        # Only open -> in_progress is valid
        if current_status != "open":
            conn.rollback()
            return {
                "ok": False,
                "status": current_status,
                "error": f'Cannot claim mission "{mission_id}": status is {current_status}',
                "quest_id": None, "quest_status_changed": False, "quest_status": None,
            }

        now = _now_utc()
        conn.execute(
            "UPDATE missions SET status = 'in_progress', updated_at = ? WHERE id = ?",
            (now, mission_id),
        )

        # Recompute parent quest status and track changes
        quest_id = mission["quest_id"]
        quest_status_before = None
        if quest_id is not None:
            row = conn.execute("SELECT status FROM quests WHERE id = ?", (quest_id,)).fetchone()
            quest_status_before = row["status"] if row else None
            _derive_quest_status(conn, quest_id, now)

        quest_status_after = None
        quest_status_changed = False
        if quest_id is not None:
            row = conn.execute("SELECT status FROM quests WHERE id = ?", (quest_id,)).fetchone()
            quest_status_after = row["status"] if row else None
            quest_status_changed = quest_status_after != quest_status_before

        conn.commit()
        return {"ok": True, "status": "in_progress", "error": None,
                "quest_id": quest_id,
                "quest_status_changed": quest_status_changed,
                "quest_status": quest_status_after}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def close_mission(project_root: Path, mission_id: str) -> dict:
    """Close a mission, cascade unblock dependents, and recompute quest status.

    Returns a dict with 'ok' (bool), 'status', 'error', and 'quest_closed' (bool).
    """
    conn = get_connection(project_root)
    try:
        conn.execute("BEGIN IMMEDIATE")

        cursor = conn.execute("SELECT * FROM missions WHERE id = ?", (mission_id,))
        mission = cursor.fetchone()
        if mission is None:
            conn.rollback()
            return {"ok": False, "status": None, "error": f'Mission "{mission_id}" not found', "quest_closed": False, "quest_id": None}

        current_status = mission["status"]

        # Idempotent: already closed
        if current_status == "closed":
            conn.rollback()
            return {"ok": True, "status": "closed", "error": None, "quest_closed": False, "quest_id": None}

        # Any non-closed status can transition to closed
        now = _now_utc()
        conn.execute(
            "UPDATE missions SET status = 'closed', block_reason = NULL, closed_at = ?, updated_at = ? WHERE id = ?",
            (now, now, mission_id),
        )

        # Cascade: recompute parent quest status
        quest_id = mission["quest_id"]
        quest_closed = False
        if quest_id is not None:
            # Get quest status before derivation
            cursor = conn.execute("SELECT status FROM quests WHERE id = ?", (quest_id,))
            quest_before = cursor.fetchone()
            old_quest_status = quest_before["status"] if quest_before else None

            _derive_quest_status(conn, quest_id, now)

            # Check if quest was auto-closed
            cursor = conn.execute("SELECT status FROM quests WHERE id = ?", (quest_id,))
            quest_after = cursor.fetchone()
            if quest_after and quest_after["status"] == "closed" and old_quest_status != "closed":
                quest_closed = True

        conn.commit()
        return {"ok": True, "status": "closed", "error": None, "quest_closed": quest_closed, "quest_id": quest_id}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def block_mission(project_root: Path, mission_id: str, reason: str) -> dict:
    """Block a mission with a reason.

    Valid transitions: open -> blocked, in_progress -> blocked.
    Returns a dict with 'ok', 'status', 'error'.
    """
    conn = get_connection(project_root)
    try:
        conn.execute("BEGIN IMMEDIATE")

        cursor = conn.execute("SELECT * FROM missions WHERE id = ?", (mission_id,))
        mission = cursor.fetchone()
        if mission is None:
            conn.rollback()
            return {"ok": False, "status": None, "error": f'Mission "{mission_id}" not found'}

        current_status = mission["status"]

        if current_status not in ("open", "in_progress"):
            conn.rollback()
            return {
                "ok": False,
                "status": current_status,
                "error": f'Cannot block mission "{mission_id}": status is {current_status}',
            }

        now = _now_utc()
        conn.execute(
            "UPDATE missions SET status = 'blocked', block_reason = ?, updated_at = ? WHERE id = ?",
            (reason, now, mission_id),
        )

        # Recompute parent quest status
        quest_id = mission["quest_id"]
        if quest_id is not None:
            _derive_quest_status(conn, quest_id, now)

        conn.commit()
        return {"ok": True, "status": "blocked", "error": None}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def unblock_mission(project_root: Path, mission_id: str) -> dict:
    """Unblock a mission, returning it to open status.

    Valid transition: blocked -> open.
    Returns a dict with 'ok', 'status', 'error'.
    """
    conn = get_connection(project_root)
    try:
        conn.execute("BEGIN IMMEDIATE")

        cursor = conn.execute("SELECT * FROM missions WHERE id = ?", (mission_id,))
        mission = cursor.fetchone()
        if mission is None:
            conn.rollback()
            return {"ok": False, "status": None, "error": f'Mission "{mission_id}" not found'}

        current_status = mission["status"]

        if current_status != "blocked":
            conn.rollback()
            return {
                "ok": False,
                "status": current_status,
                "error": f'Cannot unblock mission "{mission_id}": status is {current_status}',
            }

        now = _now_utc()
        conn.execute(
            "UPDATE missions SET status = 'open', block_reason = NULL, updated_at = ? WHERE id = ?",
            (now, mission_id),
        )

        # Recompute parent quest status
        quest_id = mission["quest_id"]
        if quest_id is not None:
            _derive_quest_status(conn, quest_id, now)

        conn.commit()
        return {"ok": True, "status": "open", "error": None}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _derive_quest_status(conn: sqlite3.Connection, quest_id: str, now: str) -> None:
    """Recompute and update a quest's status based on its missions.

    Rules:
    - If any mission is in_progress -> quest is in_progress
    - If all missions are closed -> quest is closed
    - Otherwise -> open
    - If no missions -> open
    """
    # Check quest's auto_close setting
    auto_close = conn.execute(
        "SELECT auto_close FROM quests WHERE id = ?", (quest_id,)
    ).fetchone()["auto_close"]

    cursor = conn.execute(
        "SELECT status FROM missions WHERE quest_id = ? AND deleted_at IS NULL", (quest_id,)
    )
    statuses = [row["status"] for row in cursor.fetchall()]

    if not statuses:
        new_status = "open"
    elif any(s == "in_progress" for s in statuses):
        new_status = "in_progress"
    elif all(s == "closed" for s in statuses):
        new_status = "closed"
    elif any(s == "closed" for s in statuses):
        # Mix of closed and non-closed means work is in progress
        new_status = "in_progress"
    else:
        new_status = "open"

    # When auto_close is disabled, prevent automatic transition to closed
    if not auto_close and new_status == "closed":
        new_status = "open"

    if new_status == "closed":
        conn.execute(
            "UPDATE quests SET status = ?, closed_at = ?, updated_at = ? WHERE id = ?",
            (new_status, now, now, quest_id),
        )
    else:
        conn.execute(
            "UPDATE quests SET status = ?, closed_at = NULL, updated_at = ? WHERE id = ?",
            (new_status, now, quest_id),
        )


def _would_create_cycle(conn: sqlite3.Connection, from_id: str, to_id: str) -> bool:
    """Return True if adding from_id->to_id would create a cycle.

    Starting from to_id, follows forward dependency edges (what does current
    depend on?) to see if from_id is reachable. If so, adding from_id->to_id
    would close a cycle.
    """
    visited: set[str] = set()
    stack = [to_id]
    while stack:
        current = stack.pop()
        if current == from_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        # Follow forward edges: what does current depend on?
        cursor = conn.execute(
            "SELECT to_id FROM dependencies WHERE from_id = ? AND deleted_at IS NULL", (current,)
        )
        for row in cursor.fetchall():
            stack.append(row[0])
    return False


def add_dependency(project_root: Path, from_id: str, to_id: str) -> dict:
    """Create a dependency where from_id depends on to_id.

    Returns a dict with:
    - 'ok' (bool): True if dependency was created or already exists
    - 'created' (bool): True if a new row was inserted
    - 'duplicate' (bool): True if dependency already existed
    - 'closed_target' (bool): True if to_id mission is closed
    - 'error' (str or None): Error message if failed
    """
    conn = get_connection(project_root)
    try:
        conn.execute("BEGIN IMMEDIATE")

        # Check from_id mission exists
        cursor = conn.execute("SELECT id, status FROM missions WHERE id = ?", (from_id,))
        from_mission = cursor.fetchone()
        if from_mission is None:
            conn.rollback()
            return {"ok": False, "created": False, "duplicate": False, "closed_target": False,
                    "error": f'Mission "{from_id}" not found'}

        # Check to_id mission exists
        cursor = conn.execute("SELECT id, status FROM missions WHERE id = ?", (to_id,))
        to_mission = cursor.fetchone()
        if to_mission is None:
            conn.rollback()
            return {"ok": False, "created": False, "duplicate": False, "closed_target": False,
                    "error": f'Mission "{to_id}" not found'}

        # Check for duplicate
        cursor = conn.execute(
            "SELECT id FROM dependencies WHERE from_id = ? AND to_id = ? AND type = 'blocks' AND deleted_at IS NULL",
            (from_id, to_id),
        )
        if cursor.fetchone() is not None:
            conn.rollback()
            return {"ok": True, "created": False, "duplicate": True, "closed_target": False,
                    "error": None}

        # Check for cycles (includes self-dependency since from_id == to_id is trivially a cycle)
        if _would_create_cycle(conn, from_id, to_id):
            conn.rollback()
            return {"ok": False, "created": False, "duplicate": False, "closed_target": False,
                    "error": f"Circular dependency detected: adding {from_id} -> {to_id} would create a cycle"}

        # Check for soft-deleted row to reactivate instead of inserting
        cursor = conn.execute(
            "SELECT id FROM dependencies WHERE from_id = ? AND to_id = ? AND type = 'blocks' AND deleted_at IS NOT NULL",
            (from_id, to_id),
        )
        existing_deleted = cursor.fetchone()
        if existing_deleted:
            conn.execute(
                "UPDATE dependencies SET deleted_at = NULL WHERE id = ?",
                (existing_deleted["id"],),
            )
        else:
            conn.execute(
                "INSERT INTO dependencies (from_id, to_id, type) VALUES (?, ?, 'blocks')",
                (from_id, to_id),
            )
        conn.commit()

        closed_target = to_mission["status"] == "closed"
        return {"ok": True, "created": True, "duplicate": False, "closed_target": closed_target,
                "error": None}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def remove_dependency(project_root: Path, from_id: str, to_id: str) -> dict:
    """Remove (soft-delete) a dependency where from_id depends on to_id.

    Returns a dict with:
    - 'removed' (bool): True if a row was soft-deleted
    - 'not_found' (bool): True if no active dependency existed
    """
    conn = get_connection(project_root)
    try:
        now = _now_utc()
        cursor = conn.execute(
            "UPDATE dependencies SET deleted_at = ? "
            "WHERE from_id = ? AND to_id = ? AND type = 'blocks' AND deleted_at IS NULL",
            (now, from_id, to_id),
        )
        conn.commit()
        if cursor.rowcount > 0:
            return {"removed": True, "not_found": False}
        else:
            return {"removed": False, "not_found": True}
    finally:
        conn.close()


def get_dashboard_quests(project_root: Path) -> list[dict]:
    """Return non-closed quests with mission count breakdowns for the dashboard.

    Each quest dict includes: id, title, status, priority, and missions dict
    with counts for open, in_progress, blocked, closed.
    Sorted by priority ascending, then created_at ascending.
    """
    conn = get_connection(project_root)
    try:
        cursor = conn.execute(
            "SELECT * FROM quests WHERE status != 'closed' AND deleted_at IS NULL "
            "ORDER BY priority ASC, created_at ASC"
        )
        quests = cursor.fetchall()

        result = []
        for q in quests:
            # Count missions by status for this quest
            mcursor = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM missions "
                "WHERE quest_id = ? AND deleted_at IS NULL GROUP BY status",
                (q["id"],),
            )
            counts = {"open": 0, "in_progress": 0, "blocked": 0, "closed": 0}
            for row in mcursor.fetchall():
                if row["status"] in counts:
                    counts[row["status"]] = row["cnt"]

            result.append({
                "id": q["id"],
                "title": q["title"],
                "status": q["status"],
                "priority": q["priority"],
                "missions": counts,
            })

        return result
    finally:
        conn.close()


def get_aggregate_stats(project_root: Path) -> dict:
    """Return aggregate counts of quests and missions by status."""
    conn = get_connection(project_root)
    try:
        quest_counts = {"open": 0, "in_progress": 0, "closed": 0}
        cursor = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM quests WHERE deleted_at IS NULL GROUP BY status"
        )
        for row in cursor.fetchall():
            if row["status"] in quest_counts:
                quest_counts[row["status"]] = row["cnt"]

        mission_counts = {"open": 0, "in_progress": 0, "blocked": 0, "closed": 0}
        cursor = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM missions WHERE deleted_at IS NULL GROUP BY status"
        )
        for row in cursor.fetchall():
            if row["status"] in mission_counts:
                mission_counts[row["status"]] = row["cnt"]

        return {"quests": quest_counts, "missions": mission_counts}
    finally:
        conn.close()



def create_mission(
    project_root: Path,
    title: str,
    quest_id: str | None = None,
    description: str = "",
    priority: int = 2,
    knight: str | None = None,
    mission_type: str | None = None,
) -> str:
    """Create a new mission and return its ID.

    If quest_id is provided, the mission belongs to that quest (hierarchical ID).
    If quest_id is None and exactly one non-closed quest exists, infer it.
    If quest_id is None and zero or multiple non-closed quests exist, standalone.
    Raises ValueError if the quest does not exist.
    """
    if not (0 <= priority <= 4):
        raise ValueError(f"priority {priority!r} out of range 0-4")
    conn = get_connection(project_root)
    try:
        conn.execute("BEGIN IMMEDIATE")

        # Validate quest exists if specified
        if quest_id is not None:
            cursor = conn.execute("SELECT id, status FROM quests WHERE id = ?", (quest_id,))
            quest = cursor.fetchone()
            if quest is None:
                raise ValueError(f'Quest "{quest_id}" not found')

            # Reopen closed quest
            if quest["status"] == "closed":
                now = _now_utc()
                conn.execute(
                    "UPDATE quests SET status = 'open', closed_at = NULL, updated_at = ? WHERE id = ?",
                    (now, quest_id),
                )

        # Generate mission ID
        if quest_id is not None:
            cursor = conn.execute(
                "SELECT id FROM missions WHERE quest_id = ?", (quest_id,)
            )
            existing_ids = set()
            for row in cursor.fetchall():
                # Extract the m-xxxx part from q-xxxx/m-xxxx
                parts = row["id"].split("/")
                if len(parts) == 2:
                    existing_ids.add(parts[1])
            m_part = generate_id("m", existing_ids)
            mission_id = f"{quest_id}/{m_part}"
        else:
            cursor = conn.execute(
                "SELECT id FROM missions WHERE quest_id IS NULL"
            )
            existing_ids = {row["id"] for row in cursor.fetchall()}
            mission_id = generate_id("m", existing_ids)

        now = _now_utc()
        conn.execute(
            "INSERT INTO missions (id, quest_id, title, description, status, priority, knight, created_at, updated_at, mission_type) "
            "VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)",
            (mission_id, quest_id, title, description, priority, knight, now, now, mission_type),
        )
        conn.commit()
        return mission_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_quest(project_root: Path, quest_id: str, cascade: bool = False) -> dict:
    """Soft-delete a quest (and optionally cascade to missions/dependencies).

    Returns a dict with:
    - 'ok' (bool)
    - 'deleted_at' (str or None): timestamp of deletion
    - 'already_deleted' (bool): True if quest was already soft-deleted
    - 'cascade' (list[str] or None): IDs of cascade-deleted missions (only if cascade=True)
    - 'error' (str or None)
    """
    conn = get_connection(project_root)
    try:
        conn.execute("BEGIN IMMEDIATE")

        # Check if quest exists at all
        cursor = conn.execute("SELECT id, deleted_at FROM quests WHERE id = ?", (quest_id,))
        quest = cursor.fetchone()

        if quest is None:
            conn.rollback()
            return {"ok": False, "deleted_at": None, "already_deleted": False, "cascade": None,
                    "error": f'Quest "{quest_id}" not found'}

        # Already deleted - idempotent
        if quest["deleted_at"] is not None:
            conn.rollback()
            return {"ok": True, "deleted_at": quest["deleted_at"], "already_deleted": True,
                    "cascade": None, "error": None}

        now = _now_utc()

        # Soft-delete the quest
        conn.execute(
            "UPDATE quests SET deleted_at = ?, updated_at = ? WHERE id = ?",
            (now, now, quest_id),
        )

        cascaded_ids: list[str] = []
        if cascade:
            # Collect mission IDs before soft-deleting
            cursor = conn.execute(
                "SELECT id FROM missions WHERE quest_id = ? AND deleted_at IS NULL",
                (quest_id,),
            )
            cascaded_ids = [row["id"] for row in cursor.fetchall()]

            # Soft-delete missions
            if cascaded_ids:
                conn.execute(
                    "UPDATE missions SET deleted_at = ?, updated_at = ? WHERE quest_id = ? AND deleted_at IS NULL",
                    (now, now, quest_id),
                )

                # Soft-delete dependencies involving these missions
                conn.execute(
                    "UPDATE dependencies SET deleted_at = ? WHERE deleted_at IS NULL AND "
                    "(from_id IN (SELECT id FROM missions WHERE quest_id = ?) "
                    "OR to_id IN (SELECT id FROM missions WHERE quest_id = ?))",
                    (now, quest_id, quest_id),
                )

        conn.commit()
        return {"ok": True, "deleted_at": now, "already_deleted": False,
                "cascade": cascaded_ids if cascade else None, "error": None}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_mission(project_root: Path, mission_id: str) -> dict:
    """Soft-delete a mission, its dependencies, and re-derive parent quest status.

    Returns a dict with:
    - 'ok' (bool)
    - 'deleted_at' (str or None): timestamp of deletion
    - 'already_deleted' (bool): True if mission was already soft-deleted
    - 'error' (str or None)
    """
    conn = get_connection(project_root)
    try:
        conn.execute("BEGIN IMMEDIATE")

        # Check if mission exists at all
        cursor = conn.execute("SELECT id, quest_id, deleted_at FROM missions WHERE id = ?", (mission_id,))
        mission = cursor.fetchone()

        if mission is None:
            conn.rollback()
            return {"ok": False, "deleted_at": None, "already_deleted": False,
                    "error": f'Mission "{mission_id}" not found'}

        # Already deleted - idempotent
        if mission["deleted_at"] is not None:
            conn.rollback()
            return {"ok": True, "deleted_at": mission["deleted_at"], "already_deleted": True,
                    "error": None}

        now = _now_utc()

        # Soft-delete the mission
        conn.execute(
            "UPDATE missions SET deleted_at = ?, updated_at = ? WHERE id = ?",
            (now, now, mission_id),
        )

        # Soft-delete all dependencies involving this mission
        conn.execute(
            "UPDATE dependencies SET deleted_at = ? WHERE (from_id = ? OR to_id = ?) AND deleted_at IS NULL",
            (now, mission_id, mission_id),
        )

        # Re-derive parent quest status
        quest_id = mission["quest_id"]
        if quest_id is not None:
            _derive_quest_status(conn, quest_id, now)

        conn.commit()
        return {"ok": True, "deleted_at": now, "already_deleted": False, "error": None}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def edit_quest(
    project_root: Path,
    quest_id: str,
    title: str | None = None,
    description: str | None = None,
    priority: int | None = None,
    auto_close: int | None = None,
) -> dict:
    """Edit a quest's fields. Only provided (non-None) fields are updated.

    Returns a dict with 'ok' (bool) and 'error' (str or None).
    On error, may include 'deleted_at' if the quest was soft-deleted.
    """
    if priority is not None:
        err = validators.validate_priority(priority)
        if err:
            return {"ok": False, "error": err}

    conn = get_connection(project_root)
    try:
        conn.execute("BEGIN IMMEDIATE")

        # Check if quest exists (including soft-deleted)
        cursor = conn.execute("SELECT * FROM quests WHERE id = ?", (quest_id,))
        quest = cursor.fetchone()

        if quest is None:
            conn.rollback()
            return {"ok": False, "error": f'Quest "{quest_id}" not found'}

        if quest["deleted_at"] is not None:
            conn.rollback()
            return {
                "ok": False,
                "error": f'Quest "{quest_id}" not found (deleted on {quest["deleted_at"]})',
                "deleted_at": quest["deleted_at"],
            }

        # Build dynamic UPDATE
        set_clauses = []
        params: list = []
        if title is not None:
            set_clauses.append("title = ?")
            params.append(title)
        if description is not None:
            set_clauses.append("description = ?")
            params.append(description)
        if priority is not None:
            set_clauses.append("priority = ?")
            params.append(priority)
        if auto_close is not None:
            set_clauses.append("auto_close = ?")
            params.append(auto_close)

        now = _now_utc()
        set_clauses.append("updated_at = ?")
        params.append(now)
        params.append(quest_id)

        conn.execute(
            f"UPDATE quests SET {', '.join(set_clauses)} WHERE id = ?",
            params,
        )
        conn.commit()
        return {"ok": True, "error": None}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def edit_mission(
    project_root: Path,
    mission_id: str,
    title: str | None = None,
    description: str | None = None,
    priority: int | None = None,
    knight: str | None = None,
    remove_knight: bool = False,
    mission_type: str | None = None,
) -> dict:
    """Edit a mission's fields. Only provided (non-None) fields are updated.

    Returns a dict with 'ok' (bool) and 'error' (str or None).
    On error, may include 'deleted_at' if the mission was soft-deleted.
    """
    if priority is not None:
        err = validators.validate_priority(priority)
        if err:
            return {"ok": False, "error": err}

    conn = get_connection(project_root)
    try:
        conn.execute("BEGIN IMMEDIATE")

        # Check if mission exists (including soft-deleted)
        cursor = conn.execute("SELECT * FROM missions WHERE id = ?", (mission_id,))
        mission = cursor.fetchone()

        if mission is None:
            conn.rollback()
            return {"ok": False, "error": f'Mission "{mission_id}" not found'}

        if mission["deleted_at"] is not None:
            conn.rollback()
            return {
                "ok": False,
                "error": f'Mission "{mission_id}" not found (deleted on {mission["deleted_at"]})',
                "deleted_at": mission["deleted_at"],
            }

        # Build dynamic UPDATE
        set_clauses = []
        params: list = []
        if title is not None:
            set_clauses.append("title = ?")
            params.append(title)
        if description is not None:
            set_clauses.append("description = ?")
            params.append(description)
        if priority is not None:
            set_clauses.append("priority = ?")
            params.append(priority)
        if remove_knight:
            set_clauses.append("knight = NULL")
        elif knight is not None:
            set_clauses.append("knight = ?")
            params.append(knight)
        if mission_type is not None:
            set_clauses.append("mission_type = ?")
            params.append(mission_type)

        now = _now_utc()
        set_clauses.append("updated_at = ?")
        params.append(now)
        params.append(mission_id)

        conn.execute(
            f"UPDATE missions SET {', '.join(set_clauses)} WHERE id = ?",
            params,
        )
        conn.commit()
        return {"ok": True, "error": None}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def close_quest(project_root: Path, quest_id: str) -> dict:
    """Close a quest by ID.

    Returns a dict with 'ok' (bool), 'status', 'closed_at', 'already_closed', and 'error'.
    """
    conn = get_connection(project_root)
    try:
        conn.execute("BEGIN IMMEDIATE")

        # First check including soft-deleted to give informative error
        cursor = conn.execute("SELECT * FROM quests WHERE id = ?", (quest_id,))
        quest = cursor.fetchone()

        if quest is None:
            conn.rollback()
            return {"ok": False, "error": f'Quest "{quest_id}" not found'}

        if quest["deleted_at"] is not None:
            conn.rollback()
            return {"ok": False, "error": f'Quest "{quest_id}" not found (deleted on {quest["deleted_at"]})'}

        if quest["status"] == "closed":
            conn.rollback()
            return {"ok": True, "status": "closed", "closed_at": quest["closed_at"], "already_closed": True, "error": None}

        now = _now_utc()
        conn.execute(
            "UPDATE quests SET status = 'closed', closed_at = ?, updated_at = ? WHERE id = ?",
            (now, now, quest_id),
        )
        conn.commit()
        return {"ok": True, "status": "closed", "closed_at": now, "already_closed": False, "error": None}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_quest(project_root: Path, title: str, description: str = "", priority: int = 2, auto_close: int = 0) -> str:
    """Create a new quest and return its ID."""
    if not (0 <= priority <= 4):
        raise ValueError(f"priority {priority!r} out of range 0-4")
    conn = get_connection(project_root)
    try:
        conn.execute("BEGIN IMMEDIATE")
        # Get existing quest IDs for collision avoidance
        cursor = conn.execute("SELECT id FROM quests")
        existing_ids = {row["id"] for row in cursor.fetchall()}
        quest_id = generate_id("q", existing_ids)

        now = _now_utc()
        conn.execute(
            "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at, auto_close) "
            "VALUES (?, ?, ?, 'open', ?, ?, ?, ?)",
            (quest_id, title, description, priority, now, now, auto_close),
        )
        conn.commit()
        return quest_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def add_board_message(
    project_root: Path, entity_id: str, message: str, sender: str | None = None
) -> dict:
    """Insert a board message for the given entity and return the new row as a dict."""
    # 1. Validate entity ID format
    err = validators.validate_entity_id(entity_id)
    if err:
        return {"ok": False, "error": err}

    # 2. Validate message
    err = validators.validate_message(message)
    if err:
        return {"ok": False, "error": err}

    # 3. Route entity to table
    table, id_col = validators.route_entity(entity_id)

    conn = get_connection(project_root)
    try:
        # Validate entity existence
        entity_label = "Quest" if table == "quests" else "Mission"
        row_check = conn.execute(
            f"SELECT id FROM {table} WHERE {id_col} = ? AND deleted_at IS NULL",
            (entity_id,),
        ).fetchone()
        if row_check is None:
            return {"ok": False, "error": f'{entity_label} "{entity_id}" not found'}

        cursor = conn.execute(
            "INSERT INTO board_messages (entity_id, message, sender) VALUES (?, ?, ?)",
            (entity_id, message, sender),
        )
        conn.commit()
        row_id = cursor.lastrowid
        row = conn.execute(
            "SELECT id, entity_id, sender, created_at FROM board_messages WHERE id = ?",
            (row_id,),
        ).fetchone()
        return {
            "ok": True,
            "id": row["id"],
            "entity_id": row["entity_id"],
            "sender": row["sender"],
            "created_at": row["created_at"],
        }
    finally:
        conn.close()


def get_board_messages(project_root: Path, entity_id: str) -> list[dict]:
    """Return all non-deleted board messages for the given entity, oldest first."""
    conn = get_connection(project_root)
    try:
        cursor = conn.execute(
            "SELECT id, entity_id, message, sender, created_at FROM board_messages "
            "WHERE entity_id = ? AND deleted_at IS NULL ORDER BY created_at ASC",
            (entity_id,),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": row["id"],
                "entity_id": row["entity_id"],
                "message": row["message"],
                "sender": row["sender"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    finally:
        conn.close()


def delete_board_message(project_root: Path, message_id: int) -> dict:
    """Soft-delete a board message by its integer ID."""
    conn = get_connection(project_root)
    try:
        now = _now_utc()
        cursor = conn.execute(
            "UPDATE board_messages SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
            (now, message_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return {"ok": False, "error": f"Board message {message_id} not found."}
        return {"ok": True, "id": message_id, "deleted_at": now}
    finally:
        conn.close()
