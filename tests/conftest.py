"""Shared fixtures and helpers for the E2E test suite."""

import json
import re
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from lore.cli import main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner():
    """Return a Click CliRunner instance."""
    return CliRunner()


@pytest.fixture()
def project_dir(tmp_path, monkeypatch):
    """Create an initialised Lore project in an isolated temp directory.

    Changes the working directory to ``tmp_path`` and runs ``lore init``.
    Returns the path to the temp directory.
    """
    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])
    return tmp_path


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def db_conn(project_dir: Path) -> sqlite3.Connection:
    """Open a connection to the test project's SQLite database."""
    conn = sqlite3.connect(str(project_dir / ".lore" / "lore.db"))
    conn.row_factory = sqlite3.Row
    return conn


def insert_quest(
    project_dir: Path,
    quest_id: str,
    title: str,
    status: str = "open",
    priority: int = 2,
    auto_close: int = 0,
    description: str = "",
    deleted_at: str | None = None,
    closed_at: str | None = None,
) -> None:
    """Insert a quest row directly into the database."""
    conn = sqlite3.connect(str(project_dir / ".lore" / "lore.db"))
    try:
        conn.execute(
            "INSERT INTO quests "
            "(id, title, description, status, priority, auto_close, "
            "created_at, updated_at, closed_at, deleted_at) "
            "VALUES (?, ?, ?, ?, ?, ?, "
            "'2025-01-15T09:00:00Z', '2025-01-15T09:00:00Z', ?, ?)",
            (
                quest_id,
                title,
                description,
                status,
                priority,
                auto_close,
                closed_at,
                deleted_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def insert_mission(
    project_dir: Path,
    mission_id: str,
    quest_id: str | None,
    title: str,
    status: str = "open",
    priority: int = 2,
    mission_type: str | None = None,
    knight: str | None = None,
    block_reason: str | None = None,
    deleted_at: str | None = None,
    closed_at: str | None = None,
    created_at: str = "2025-01-15T09:00:00Z",
    updated_at: str = "2025-01-15T09:00:00Z",
) -> None:
    """Insert a mission row directly into the database."""
    conn = sqlite3.connect(str(project_dir / ".lore" / "lore.db"))
    try:
        conn.execute(
            "INSERT INTO missions "
            "(id, quest_id, title, description, status, priority, mission_type, "
            "knight, block_reason, created_at, updated_at, closed_at, deleted_at) "
            "VALUES (?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                mission_id,
                quest_id,
                title,
                status,
                priority,
                mission_type,
                knight,
                block_reason,
                created_at,
                updated_at,
                closed_at,
                deleted_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def insert_dependency(
    project_dir: Path,
    from_id: str,
    to_id: str,
    deleted_at: str | None = None,
) -> None:
    """Insert a dependency row directly into the database."""
    conn = sqlite3.connect(str(project_dir / ".lore" / "lore.db"))
    try:
        conn.execute(
            "INSERT INTO dependencies (from_id, to_id, type, deleted_at) "
            "VALUES (?, ?, 'blocks', ?)",
            (from_id, to_id, deleted_at),
        )
        conn.commit()
    finally:
        conn.close()


def insert_board_message(
    project_dir: Path,
    entity_id: str,
    message: str,
    sender: str | None = None,
) -> None:
    """Insert a board message row directly into the database."""
    conn = sqlite3.connect(str(project_dir / ".lore" / "lore.db"))
    try:
        conn.execute(
            "INSERT INTO board_messages (entity_id, message, sender, created_at) "
            "VALUES (?, ?, ?, '2025-01-15T09:00:00Z')",
            (entity_id, message, sender),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# ID extraction helpers
# ---------------------------------------------------------------------------


def parse_json_id(result) -> str:
    """Extract ``id`` from the JSON output of a CLI result."""
    return json.loads(result.output)["id"]


def extract_quest_id(output: str) -> str:
    """Extract the first quest ID (``q-xxxx``) from human-readable output."""
    m = re.search(r"(q-[a-f0-9]{4,6})", output)
    return m.group(1) if m else ""


def extract_mission_id(output: str) -> str:
    """Extract the first mission ID from human-readable output."""
    m = re.search(r"(q-[a-f0-9]+/m-[a-f0-9]+|m-[a-f0-9]+)", output)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------


def assert_exit_ok(result) -> None:
    """Assert that a CLI invocation exited with code 0."""
    assert result.exit_code == 0, result.output


def assert_exit_err(result, code: int = 1) -> None:
    """Assert that a CLI invocation exited with a non-zero error code."""
    assert result.exit_code == code, result.output
