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


class DatabaseNotFoundError(Exception):
    """Raised when a project has a `.lore/` directory and no database in it.

    Not an exotic state: `.lore/lore.db` is generated and gitignored, so every
    clone of a Lore project is in it until somebody runs `lore init`. What used
    to happen instead was that ``sqlite3.connect`` created an empty file, the
    first query hit no ``lore_meta`` table, and a teammate's first command
    printed a stack trace out of ``_run_migrations``.
    """


DATABASE_NOT_FOUND = (
    "No Lore database here (.lore/lore.db is missing). It is generated and "
    'never committed — run "lore init" to create it.'
)
"""Names the cause and the repair, in the shape ``ProjectNotFoundError`` uses."""


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

    Raises ``DatabaseNotFoundError`` when there is no database to open. The
    check comes before ``sqlite3.connect`` and not after, because connecting
    *creates* the file: the failing command used to leave a 4096-byte empty
    database behind on its way down, which is a worse state than the one it
    was called in.
    """
    db_path = paths.db_path(project_root)
    if not db_path.is_file():
        raise DatabaseNotFoundError(DATABASE_NOT_FOUND)
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


def list_quests(project_root: Path, include_closed: bool = False) -> list[dict]:
    """List quests sorted by priority asc, then created_at asc.

    Returns ``list[dict]`` (amendment Section B Quest row, F-READ-ROW-MIGRATION).
    """
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
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def read_quest(project_root: Path, quest_id: str) -> dict | None:
    """Fetch a single quest by ID (excludes soft-deleted).

    Returns ``dict | None`` (amendment Section B Quest row,
    F-READ-ROW-MIGRATION). Renamed from ``get_quest``.
    """
    conn = get_connection(project_root)
    try:
        cursor = conn.execute(
            "SELECT * FROM quests WHERE id = ? AND deleted_at IS NULL",
            (quest_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
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


def get_missions_for_quest(project_root: Path, quest_id: str) -> list[dict]:
    """Fetch missions for a quest, sorted by status group, priority, created_at.

    Status order: open/in_progress first, blocked next, closed last.
    Returns ``list[dict]`` (F-READ-ROW-MIGRATION).
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
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def list_missions(
    project_root: Path,
    quest_id: str | None = None,
    include_closed: bool = False,
) -> dict[str | None, list[dict]]:
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

        # Group by quest_id (Row → dict; F-READ-ROW-MIGRATION)
        grouped: dict[str | None, list[dict]] = {}
        for row in rows:
            grouped.setdefault(row["quest_id"], []).append(dict(row))

        return grouped
    finally:
        conn.close()


def read_mission(project_root: Path, mission_id: str) -> dict | None:
    """Fetch a single mission by ID (excludes soft-deleted).

    Returns ``dict | None`` (F-READ-ROW-MIGRATION). Renamed from ``get_mission``.
    """
    conn = get_connection(project_root)
    try:
        cursor = conn.execute(
            "SELECT * FROM missions WHERE id = ? AND deleted_at IS NULL",
            (mission_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    finally:
        conn.close()


def _mission_depends_on_ids(project_root: Path, mission_id: str) -> list[str]:
    """Internal helper: IDs this mission depends on. Public facade dropped.

    Callers should use ``list_mission_depends_on(...)`` and project the ``id``
    field (amendment Section B Dependency row).
    """
    conn = get_connection(project_root)
    try:
        cursor = conn.execute(
            "SELECT to_id FROM dependencies WHERE from_id = ? AND deleted_at IS NULL", (mission_id,)
        )
        return [row["to_id"] for row in cursor.fetchall()]
    finally:
        conn.close()


def _mission_blocks_ids(project_root: Path, mission_id: str) -> list[str]:
    """Internal helper: IDs blocked by this mission. Public facade dropped.

    Callers should use ``list_mission_blocks(...)`` and project the ``id``
    field (amendment Section B Dependency row).
    """
    conn = get_connection(project_root)
    try:
        cursor = conn.execute(
            "SELECT from_id FROM dependencies WHERE to_id = ? AND deleted_at IS NULL", (mission_id,)
        )
        return [row["from_id"] for row in cursor.fetchall()]
    finally:
        conn.close()


def list_mission_depends_on(project_root: Path, mission_id: str) -> list[dict]:
    """Return details (id, title, status) of missions that this mission depends on.

    Renamed from ``get_mission_depends_on_details`` (amendment Section B).
    """
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


def list_mission_blocks(project_root: Path, mission_id: str) -> list[dict]:
    """Return details (id, title, status) of missions that depend on this mission.

    Renamed from ``get_mission_blocks_details`` (amendment Section B).
    """
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
        quest_status_after = None
        quest_status_changed = False
        if quest_id is not None:
            quest_status_before, quest_status_after = _derive_quest_status_diff(
                conn, quest_id, now
            )
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
            status_before, status_after = _derive_quest_status_diff(
                conn, quest_id, now
            )
            if status_after == "closed" and status_before != "closed":
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


def _derive_quest_status_diff(
    conn: sqlite3.Connection, quest_id: str, now: str
) -> tuple[str | None, str | None]:
    """Recompute a quest's status and return its (before, after) status.

    Reads the quest's status, runs `_derive_quest_status`, then reads the
    status again. Returns `(status_before, status_after)`; either side is
    `None` if the quest row is missing. Caller is responsible for the
    surrounding transaction.
    """
    before = conn.execute(
        "SELECT status FROM quests WHERE id = ?", (quest_id,)
    ).fetchone()
    status_before = before["status"] if before else None
    _derive_quest_status(conn, quest_id, now)
    after = conn.execute(
        "SELECT status FROM quests WHERE id = ?", (quest_id,)
    ).fetchone()
    status_after = after["status"] if after else None
    return status_before, status_after


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

    Returns ``{"from": from_id, "to": to_id, "created": True}`` on success
    (amendment Section B Dependency row). Raises ``ValueError`` on:
    - missing from_id or to_id mission
    - duplicate (single-shot diverges from bulk per amendment B)
    - cycle detection
    """
    conn = get_connection(project_root)
    try:
        conn.execute("BEGIN IMMEDIATE")

        # Check from_id mission exists
        cursor = conn.execute("SELECT id, status FROM missions WHERE id = ?", (from_id,))
        from_mission = cursor.fetchone()
        if from_mission is None:
            conn.rollback()
            raise ValueError(f'Mission "{from_id}" not found')

        # Check to_id mission exists
        cursor = conn.execute("SELECT id, status FROM missions WHERE id = ?", (to_id,))
        to_mission = cursor.fetchone()
        if to_mission is None:
            conn.rollback()
            raise ValueError(f'Mission "{to_id}" not found')

        # Check for duplicate — single-shot raises (amendment B Dependency row)
        cursor = conn.execute(
            "SELECT id FROM dependencies WHERE from_id = ? AND to_id = ? AND type = 'blocks' AND deleted_at IS NULL",
            (from_id, to_id),
        )
        if cursor.fetchone() is not None:
            conn.rollback()
            raise ValueError(
                f'Dependency already exists: {from_id} -> {to_id}'
            )

        # Check for cycles (includes self-dependency since from_id == to_id is trivially a cycle)
        if _would_create_cycle(conn, from_id, to_id):
            conn.rollback()
            raise ValueError(
                f"Circular dependency detected: adding {from_id} -> {to_id} would create a cycle"
            )

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

        return {"from": from_id, "to": to_id, "created": True}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def remove_dependency(project_root: Path, from_id: str, to_id: str) -> dict:
    """Remove (soft-delete) a dependency where from_id depends on to_id.

    Returns ``{"from": from_id, "to": to_id, "removed": bool}``. Preserves the
    ADR-011 existence-based contract: missing dependency returns
    ``{..., "removed": False}`` (no raise).
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
        removed = cursor.rowcount > 0
        return {"from": from_id, "to": to_id, "removed": removed}
    finally:
        conn.close()


def claim_missions(project_root: Path, mission_ids: list[str]) -> dict:
    """Claim multiple missions in one call.

    Returns an envelope with EXACT keys (cli.py:495-503):
      {"updated": [...], "quest_status_changed": [...], "errors": [...]}

    Each transitions open -> in_progress per the single-shot semantics; one
    failing mission does NOT roll back earlier successes (per-mission
    BEGIN IMMEDIATE). The quest-status recompute is coalesced so
    `_derive_quest_status` runs at most once per affected quest.
    """
    updated: list[str] = []
    quest_status_changed: list[dict] = []
    errors: list[str] = []
    affected_quests: list[str] = []
    seen_quests: set[str] = set()

    for mid in mission_ids:
        err = validators.validate_mission_id(mid)
        if err:
            errors.append(err)
            continue
        conn = get_connection(project_root)
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM missions WHERE id = ?", (mid,)
            ).fetchone()
            if row is None:
                conn.rollback()
                errors.append(f'Mission "{mid}" not found')
                continue
            current = row["status"]
            if current == "in_progress":
                conn.rollback()
                continue
            if current != "open":
                conn.rollback()
                errors.append(
                    f'Cannot claim mission "{mid}": status is {current}'
                )
                continue
            now = _now_utc()
            conn.execute(
                "UPDATE missions SET status = 'in_progress', updated_at = ? WHERE id = ?",
                (now, mid),
            )
            qid = row["quest_id"]
            conn.commit()
            updated.append(mid)
            if qid is not None and qid not in seen_quests:
                affected_quests.append(qid)
                seen_quests.add(qid)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    for qid in affected_quests:
        conn = get_connection(project_root)
        try:
            conn.execute("BEGIN IMMEDIATE")
            status_before, status_after = _derive_quest_status_diff(
                conn, qid, _now_utc()
            )
            conn.commit()
            if status_after != status_before:
                quest_status_changed.append({"id": qid, "status": status_after})
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    return {
        "updated": updated,
        "quest_status_changed": quest_status_changed,
        "errors": errors,
    }


def close_entities(project_root: Path, entity_ids: list[str]) -> dict:
    """Close a mixed list of mission and quest IDs in one call.

    Returns an envelope with EXACT keys (cli.py:570-578):
      {"updated": [...], "quest_closed": [...], "errors": [...]}

    Quest IDs (`q-…` with no `/`) dispatch via single-shot `close_quest`.
    Mission IDs close inline with per-id BEGIN IMMEDIATE; `_derive_quest_status`
    is coalesced to at most one call per affected quest at the end.
    Already-closed entities are no-op successes (counted in `updated`,
    not in `errors`). One failing entity never rolls back prior successes.
    """
    updated: list[str] = []
    quest_closed: list[str] = []
    errors: list[str] = []
    affected_quests: list[str] = []
    seen_quests: set[str] = set()

    for eid in entity_ids:
        if eid.startswith("q-") and "/" not in eid:
            result = close_quest(project_root, eid)
            if not result["ok"]:
                errors.append(result["error"])
            else:
                updated.append(eid)
            continue
        err = validators.validate_mission_id(eid)
        if err:
            errors.append(err)
            continue
        conn = get_connection(project_root)
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM missions WHERE id = ?", (eid,)
            ).fetchone()
            if row is None:
                conn.rollback()
                errors.append(f'Mission "{eid}" not found')
                continue
            current = row["status"]
            if current == "closed":
                conn.rollback()
                updated.append(eid)
                continue
            now = _now_utc()
            conn.execute(
                "UPDATE missions SET status = 'closed', block_reason = NULL, "
                "closed_at = ?, updated_at = ? WHERE id = ?",
                (now, now, eid),
            )
            qid = row["quest_id"]
            conn.commit()
            updated.append(eid)
            if qid is not None and qid not in seen_quests:
                affected_quests.append(qid)
                seen_quests.add(qid)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    for qid in affected_quests:
        conn = get_connection(project_root)
        try:
            conn.execute("BEGIN IMMEDIATE")
            status_before, status_after = _derive_quest_status_diff(
                conn, qid, _now_utc()
            )
            conn.commit()
            if status_after == "closed" and status_before != "closed":
                quest_closed.append(qid)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    return {
        "updated": updated,
        "quest_closed": quest_closed,
        "errors": errors,
    }


def add_dependencies(project_root: Path, pairs: list[tuple[str, str]]) -> dict:
    """Add multiple dependencies in one call by wrapping `add_dependency`.

    Returns an envelope with EXACT keys (cli.py:768-776):
      {"created": [...], "existing": [...], "errors": [...]}

    Each entry in `created`/`existing` is `{"from": <id>, "to": <id>}` —
    EXACTLY `from`/`to`, never `from_id`/`to_id`. Per-pair BEGIN IMMEDIATE
    is preserved by dispatching to the single-shot. Never calls
    `_derive_quest_status` — dependency changes don't affect quest status.
    """
    created: list[dict] = []
    existing: list[dict] = []
    errors: list[str] = []
    for from_id, to_id in pairs:
        # Single-shot now raises on duplicate AND error per amendment B; bulk
        # preserves multi-branch envelope by translating the duplicate case
        # back into the `existing` list.
        try:
            add_dependency(project_root, from_id, to_id)
        except ValueError as exc:
            msg = str(exc)
            if msg.startswith("Dependency already exists"):
                existing.append({"from": from_id, "to": to_id})
            else:
                errors.append(msg)
        else:
            created.append({"from": from_id, "to": to_id})
    return {"created": created, "existing": existing, "errors": errors}


def remove_dependencies(project_root: Path, pairs: list[tuple[str, str]]) -> dict:
    """Remove multiple dependencies in one call by wrapping `remove_dependency`.

    Returns an envelope with EXACT keys (cli.py:862-869):
      {"removed": [...], "not_found": [...], "errors": [...]}

    Each entry in `removed`/`not_found` is `{"from": <id>, "to": <id>}` —
    EXACTLY `from`/`to`, never `from_id`/`to_id`. Per-pair BEGIN IMMEDIATE
    is preserved by dispatching to the single-shot. Never calls
    `_derive_quest_status`.
    """
    removed: list[dict] = []
    not_found: list[dict] = []
    errors: list[str] = []
    for from_id, to_id in pairs:
        try:
            result = remove_dependency(project_root, from_id, to_id)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if result.get("removed", False):
            removed.append({"from": from_id, "to": to_id})
        else:
            not_found.append({"from": from_id, "to": to_id})
    return {"removed": removed, "not_found": not_found, "errors": errors}


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
) -> dict:
    """Create a new mission.

    Returns ``{"id": mission_id, "filename": None, "group": None}``
    (amendment Section B Mission row). ``filename`` and ``group`` are None
    for db-backed entities.

    If quest_id is provided, the mission belongs to that quest (hierarchical ID).
    If quest_id is None and exactly one non-closed quest exists, infer it.
    If quest_id is None and zero or multiple non-closed quests exist, standalone.
    Raises ValueError if the quest does not exist or priority is invalid.
    """
    if not (0 <= priority <= 4):
        raise ValueError(f"priority {priority!r} out of range 0-4")
    conn = get_connection(project_root)
    try:
        conn.execute("BEGIN IMMEDIATE")

        # Inferred-parent-quest lookup (FLAG #4 — G12 behaviour change):
        # if quest_id was not supplied AND exactly one non-closed quest
        # exists, auto-attach. Previously lived in cli.new_mission; now
        # direct-Python callers see the same inference.
        if quest_id is None:
            cursor = conn.execute(
                "SELECT id FROM quests WHERE status != 'closed' AND deleted_at IS NULL"
            )
            active_quests = cursor.fetchall()
            if len(active_quests) == 1:
                quest_id = active_quests[0]["id"]

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
        return {"id": mission_id, "filename": None, "group": None}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_quest(project_root: Path, quest_id: str, cascade: bool = False) -> dict:
    """Soft-delete a quest (and optionally cascade to missions/dependencies).

    Returns ``{id, deleted: True, deleted_at, cascade: list[str] | None}``
    (amendment A2 delete shape). ``cascade`` is a list[str] when ``cascade=True``
    is passed, otherwise None. Raises ``ValueError`` if the quest does not exist.
    Idempotent re-delete returns the same envelope with the prior ``deleted_at``
    timestamp (no ``already_deleted`` flag — amendment Review Ledger CHANGED).
    """
    conn = get_connection(project_root)
    try:
        conn.execute("BEGIN IMMEDIATE")

        # Check if quest exists at all
        cursor = conn.execute("SELECT id, deleted_at FROM quests WHERE id = ?", (quest_id,))
        quest = cursor.fetchone()

        if quest is None:
            conn.rollback()
            raise ValueError(f'Quest "{quest_id}" not found')

        # Already deleted - idempotent (same envelope; deleted_at identifies prior delete)
        if quest["deleted_at"] is not None:
            conn.rollback()
            return {
                "id": quest_id,
                "deleted": True,
                "deleted_at": quest["deleted_at"],
                "cascade": [] if cascade else None,
            }

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
        return {
            "id": quest_id,
            "deleted": True,
            "deleted_at": now,
            "cascade": cascaded_ids if cascade else None,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_mission(project_root: Path, mission_id: str) -> dict:
    """Soft-delete a mission, its dependencies, and re-derive parent quest status.

    Returns ``{id, deleted: True, deleted_at}`` (amendment A2 delete shape).
    Raises ``ValueError`` if the mission does not exist. Idempotent re-delete
    returns the same envelope with the prior ``deleted_at`` (no
    ``already_deleted`` flag).
    """
    conn = get_connection(project_root)
    try:
        conn.execute("BEGIN IMMEDIATE")

        # Check if mission exists at all
        cursor = conn.execute("SELECT id, quest_id, deleted_at FROM missions WHERE id = ?", (mission_id,))
        mission = cursor.fetchone()

        if mission is None:
            conn.rollback()
            raise ValueError(f'Mission "{mission_id}" not found')

        # Already deleted - idempotent (deleted_at identifies prior delete)
        if mission["deleted_at"] is not None:
            conn.rollback()
            return {
                "id": mission_id,
                "deleted": True,
                "deleted_at": mission["deleted_at"],
            }

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
        return {"id": mission_id, "deleted": True, "deleted_at": now}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_quest(
    project_root: Path,
    quest_id: str,
    title: str | None = None,
    description: str | None = None,
    priority: int | None = None,
    auto_close: int | None = None,
) -> dict:
    """Edit a quest's fields. Only provided (non-None) fields are updated.

    Returns ``{"id": quest_id, "filename": None}`` on success
    (amendment Section B Quest row). Raises ``ValueError`` on miss / soft-deleted /
    invalid priority. Renamed from ``edit_quest``.
    """
    if priority is not None:
        err = validators.validate_priority(priority)
        if err:
            raise ValueError(err)

    conn = get_connection(project_root)
    try:
        conn.execute("BEGIN IMMEDIATE")

        # Check if quest exists (including soft-deleted)
        cursor = conn.execute("SELECT * FROM quests WHERE id = ?", (quest_id,))
        quest = cursor.fetchone()

        if quest is None:
            conn.rollback()
            raise ValueError(f'Quest "{quest_id}" not found')

        if quest["deleted_at"] is not None:
            conn.rollback()
            raise ValueError(
                f'Quest "{quest_id}" not found (deleted on {quest["deleted_at"]})'
            )

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
        return {"id": quest_id, "filename": None}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_mission(
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

    Returns ``{"id": mission_id, "filename": None}`` on success
    (amendment Section B Mission row). Raises ``ValueError`` on miss /
    soft-deleted / invalid priority. Renamed from ``edit_mission``.
    """
    if priority is not None:
        err = validators.validate_priority(priority)
        if err:
            raise ValueError(err)

    conn = get_connection(project_root)
    try:
        conn.execute("BEGIN IMMEDIATE")

        # Check if mission exists (including soft-deleted)
        cursor = conn.execute("SELECT * FROM missions WHERE id = ?", (mission_id,))
        mission = cursor.fetchone()

        if mission is None:
            conn.rollback()
            raise ValueError(f'Mission "{mission_id}" not found')

        if mission["deleted_at"] is not None:
            conn.rollback()
            raise ValueError(
                f'Mission "{mission_id}" not found (deleted on {mission["deleted_at"]})'
            )

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
        return {"id": mission_id, "filename": None}
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


def create_quest(project_root: Path, title: str, description: str = "", priority: int = 2, auto_close: int = 0) -> dict:
    """Create a new quest.

    Returns ``{"id": quest_id, "filename": None, "group": None}``
    (amendment Section B Quest row). ``filename`` and ``group`` are None for
    db-backed entities. Raises ``ValueError`` if priority is out of range.
    """
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
        return {"id": quest_id, "filename": None, "group": None}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def add_board_message(
    project_root: Path, entity_id: str, message: str, sender: str | None = None
) -> dict:
    """Insert a board message for the given entity.

    Returns ``{id, entity_id, sender, created_at}`` (amendment A2 — drops the
    ``ok`` wrapper per Review Ledger CHANGED row). Raises ``ValueError`` on
    invalid entity ID, empty message, unknown entity, or soft-deleted entity.
    """
    # 1. Validate entity ID format
    err = validators.validate_entity_id(entity_id)
    if err:
        raise ValueError(err)

    # 2. Validate message
    err = validators.validate_message(message)
    if err:
        raise ValueError(err)

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
            raise ValueError(f'{entity_label} "{entity_id}" not found')

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
            "id": row["id"],
            "entity_id": row["entity_id"],
            "sender": row["sender"],
            "created_at": row["created_at"],
        }
    finally:
        conn.close()


def list_board_messages(project_root: Path, entity_id: str) -> list[dict]:
    """Return all non-deleted board messages for the given entity, oldest first.

    Renamed from ``get_board_messages`` (amendment Section B Board row).
    """
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


def delete_board_message(
    project_root: Path, entity_id: str, message_id: int
) -> dict:
    """Soft-delete a board message by its integer ID, scoped to ``entity_id``.

    Board message IDs are a global ``INTEGER PRIMARY KEY AUTOINCREMENT`` —
    a single namespace across every quest + mission. Requiring an explicit
    ``entity_id`` prevents cross-entity ID collisions where ``board delete N``
    silently soft-deletes the wrong message.

    Returns ``{id, deleted: True, deleted_at}`` on success (amendment A2
    delete shape). Raises ``ValueError`` if the message does not exist (or
    is already soft-deleted) or if the stored ``entity_id`` does not match
    the one passed in.
    """
    conn = get_connection(project_root)
    try:
        row = conn.execute(
            "SELECT entity_id FROM board_messages "
            "WHERE id = ? AND deleted_at IS NULL",
            (message_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Board message {message_id} not found.")
        stored_entity_id = row["entity_id"]
        if stored_entity_id != entity_id:
            raise ValueError(
                f"Board message {message_id} does not belong to {entity_id}."
            )
        now = _now_utc()
        conn.execute(
            "UPDATE board_messages SET deleted_at = ? WHERE id = ?",
            (now, message_id),
        )
        conn.commit()
        return {"id": message_id, "deleted": True, "deleted_at": now}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# G6: Envelope-assembling functions (per Tech Spec §3 + §2)
# Byte-exact match to existing CLI JSON envelopes.
# ---------------------------------------------------------------------------


def _dep_to_json(dep: dict) -> dict:
    """Render a dependency-details row into the JSON envelope shape.

    Matches cli.py:2022-2028 — deleted upstream surfaces as title=[unknown],
    status=None.
    """
    deleted = dep.get("deleted_at") is not None
    return {
        "id": dep["id"],
        "title": "[unknown]" if deleted else (dep.get("title") or "[unknown]"),
        "status": None if deleted else dep.get("status"),
    }


def get_mission_detail(
    project_root: Path,
    mission_id: str,
    *,
    include_knight: bool = True,
) -> dict | None:
    """Return the full mission-detail envelope, or None if missing.

    Envelope keys match cli.py:2030-2057 EXACTLY (byte-for-byte). No
    `quest_deleted` key (text-mode-only at cli.py:2061).

    Knight resolution delegates to ``lore.knight.read_knight`` (G7 swap).
    """
    mission = read_mission(project_root, mission_id)
    if mission is None:
        return None

    knight_contents: str | None = None
    if include_knight and mission["knight"]:
        from lore.knight import read_knight

        knight_name = Path(mission["knight"]).stem
        try:
            knight_record = read_knight(project_root, knight_name)
        except ValueError:
            knight_record = None
        knight_contents = knight_record["body"] if knight_record else None

    depends_on_details = list_mission_depends_on(project_root, mission_id)
    blocks_details = list_mission_blocks(project_root, mission_id)
    board_messages = list_board_messages(project_root, mission_id)

    return {
        "id": mission["id"],
        "quest_id": mission["quest_id"],
        "title": mission["title"],
        "description": mission["description"],
        "status": mission["status"],
        "priority": mission["priority"],
        "mission_type": mission["mission_type"],
        "knight": mission["knight"],
        "knight_contents": knight_contents,
        "block_reason": mission["block_reason"],
        "created_at": mission["created_at"],
        "updated_at": mission["updated_at"],
        "closed_at": mission["closed_at"],
        "dependencies": {
            "needs": [_dep_to_json(d) for d in depends_on_details],
            "blocks": [_dep_to_json(d) for d in blocks_details],
        },
        "board": [
            {
                "id": m["id"],
                "sender": m["sender"],
                "message": m["message"],
                "created_at": m["created_at"],
            }
            for m in board_messages
        ],
    }


def get_quest_detail(project_root: Path, quest_id: str) -> dict | None:
    """Return the full quest-detail envelope, or None if missing.

    Envelope keys match cli.py:2182-2202 EXACTLY. Missions in INSERTION
    ORDER (the order from `get_missions_for_quest`); NO `parents` field;
    NO topological sort (those are CLI text-renderer concerns).
    """
    quest = read_quest(project_root, quest_id)
    if quest is None:
        return None

    missions = get_missions_for_quest(project_root, quest_id)
    board_messages = list_board_messages(project_root, quest_id)
    edges = get_all_dependencies_for_quest(project_root, quest_id)

    mission_map = {m["id"]: m for m in missions}
    needs_map: dict[str, list[str]] = {}
    blocks_map: dict[str, list[str]] = {}
    for edge in edges:
        needs_map.setdefault(edge["from_id"], []).append(edge["to_id"])
        blocks_map.setdefault(edge["to_id"], []).append(edge["from_id"])

    def _mission_ref(mid: str) -> dict:
        m = mission_map.get(mid)
        if m is None:
            m = read_mission(project_root, mid)
        if m is None:
            return {"id": mid, "title": "[unknown]", "status": None}
        return {"id": mid, "title": m["title"], "status": m["status"]}

    missions_json = []
    for m in missions:
        mid = m["id"]
        needs_refs = [_mission_ref(tid) for tid in needs_map.get(mid, [])]
        blocks_refs = [_mission_ref(fid) for fid in blocks_map.get(mid, [])]
        missions_json.append(
            {
                "id": mid,
                "title": m["title"],
                "status": m["status"],
                "priority": m["priority"],
                "mission_type": m["mission_type"],
                "knight": m["knight"],
                "dependencies": {
                    "needs": needs_refs,
                    "blocks": blocks_refs,
                },
            }
        )

    return {
        "id": quest["id"],
        "title": quest["title"],
        "description": quest["description"],
        "status": quest["status"],
        "priority": quest["priority"],
        "created_at": quest["created_at"],
        "updated_at": quest["updated_at"],
        "closed_at": quest["closed_at"],
        "auto_close": bool(quest["auto_close"]),
        "missions": missions_json,
        "board": [
            {
                "id": msg["id"],
                "sender": msg["sender"],
                "message": msg["message"],
                "created_at": msg["created_at"],
            }
            for msg in board_messages
        ],
    }


def list_missions_grouped(
    project_root: Path,
    *,
    quest_id: str | None = None,
    include_closed: bool = False,
) -> dict:
    """List missions grouped by quest, annotated with quest title/deleted_at.

    Returns ``{"groups": [{quest_id, quest_title, quest_deleted_at, missions: [...]}]}``.
    Each per-mission entry mirrors cli.py:946-960 (the JSON flat builder)
    with EXACT keys: id, quest_id, title, status, priority, mission_type,
    knight, created_at.
    """
    grouped = list_missions(
        project_root, quest_id=quest_id, include_closed=include_closed
    )

    groups: list[dict] = []
    for qid, rows in grouped.items():
        if qid is None:
            quest_title: str | None = None
            quest_deleted_at: str | None = None
        else:
            quest = read_quest(project_root, qid)
            if quest is not None:
                quest_title = quest["title"]
                quest_deleted_at = None
            else:
                quest_title = None
                quest_deleted_at = get_deleted_at(project_root, qid)

        groups.append(
            {
                "quest_id": qid,
                "quest_title": quest_title,
                "quest_deleted_at": quest_deleted_at,
                "missions": [
                    {
                        "id": m["id"],
                        "quest_id": m["quest_id"],
                        "title": m["title"],
                        "status": m["status"],
                        "priority": m["priority"],
                        "mission_type": m["mission_type"],
                        "knight": m["knight"],
                        "created_at": m["created_at"],
                    }
                    for m in rows
                ],
            }
        )

    return {"groups": groups}


def update_quest_full(
    project_root: Path,
    quest_id: str,
    *,
    title: str | None = None,
    description: str | None = None,
    priority: int | None = None,
    auto_close: int | None = None,
) -> dict:
    """Edit a quest and return the full post-edit envelope.

    Success envelope: full quest detail (matches cli.py:1648-1670 EXACTLY).
    Raises ``ValueError`` on miss / soft-deleted / invalid priority
    (amendment A4 — error contract). Renamed from ``edit_quest_full``.
    """
    update_quest(
        project_root,
        quest_id,
        title=title,
        description=description,
        priority=priority,
        auto_close=auto_close,
    )

    quest = read_quest(project_root, quest_id)
    missions = get_missions_for_quest(project_root, quest_id)
    return {
        "id": quest["id"],
        "title": quest["title"],
        "description": quest["description"],
        "status": quest["status"],
        "priority": quest["priority"],
        "created_at": quest["created_at"],
        "updated_at": quest["updated_at"],
        "closed_at": quest["closed_at"],
        "auto_close": bool(quest["auto_close"]),
        "missions": [
            {
                "id": m["id"],
                "title": m["title"],
                "status": m["status"],
                "priority": m["priority"],
                "mission_type": m["mission_type"],
                "knight": m["knight"],
            }
            for m in missions
        ],
    }


def update_mission_full(
    project_root: Path,
    mission_id: str,
    *,
    title: str | None = None,
    description: str | None = None,
    priority: int | None = None,
    knight: str | None = None,
    remove_knight: bool = False,
    mission_type: str | None = None,
) -> dict:
    """Edit a mission and return the full post-edit envelope.

    Success envelope matches cli.py:1716-1734 EXACTLY (incl.
    ``dependencies: {needs, blocks}`` — list[str] of mission IDs). Raises
    ``ValueError`` on miss / soft-deleted / invalid priority (amendment A4).
    Renamed from ``edit_mission_full``.
    """
    update_mission(
        project_root,
        mission_id,
        title=title,
        description=description,
        priority=priority,
        knight=knight,
        remove_knight=remove_knight,
        mission_type=mission_type,
    )

    mission = read_mission(project_root, mission_id)
    depends_on = _mission_depends_on_ids(project_root, mission_id)
    blocks = _mission_blocks_ids(project_root, mission_id)
    return {
        "id": mission["id"],
        "quest_id": mission["quest_id"],
        "title": mission["title"],
        "description": mission["description"],
        "status": mission["status"],
        "priority": mission["priority"],
        "knight": mission["knight"],
        "mission_type": mission["mission_type"],
        "block_reason": mission["block_reason"],
        "created_at": mission["created_at"],
        "updated_at": mission["updated_at"],
        "closed_at": mission["closed_at"],
        "dependencies": {
            "needs": depends_on,
            "blocks": blocks,
        },
    }


def delete_entity(
    project_root: Path,
    entity_id: str,
    *,
    cascade: bool = False,
) -> dict:
    """Delete a quest or mission via route_entity dispatch.

    Routing uses ``lore.validators.route_entity`` (raises ValueError on
    unrecognised IDs — caller translates).

    Returns the underlying ``delete_quest`` / ``delete_mission`` envelope
    verbatim (amendment A2 — positive envelope; idempotent re-delete returns
    same shape with prior ``deleted_at``). Raises ``ValueError`` on unknown
    entity ID (propagated from the underlying delete).
    """
    table, _ = validators.route_entity(entity_id)

    if table == "quests":
        return delete_quest(project_root, entity_id, cascade=cascade)

    return delete_mission(project_root, entity_id)
