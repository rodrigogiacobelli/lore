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


def _ensure_db(project_dir: Path) -> None:
    """Ensure the project database is initialized with the schema."""
    from lore.db import init_database

    lore_dir = project_dir / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    init_database(lore_dir / "lore.db")


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
    _ensure_db(project_dir)
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
    doctrine_mission: str | None = None,
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
            "doctrine_mission, block_reason, created_at, updated_at, closed_at, deleted_at) "
            "VALUES (?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                mission_id,
                quest_id,
                title,
                status,
                priority,
                mission_type,
                doctrine_mission,
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


# ---------------------------------------------------------------------------
# Nested-projects fixture
#
# Spec: nested-projects-spec (lore codex show nested-projects-spec) — Part 4
# "Conventions". A real tree on disk, built by real `lore init` runs. Nothing
# here mocks a walk, ``tomllib`` or ``fnmatch``.
# ---------------------------------------------------------------------------


NESTED_CAMELOT_CONFIG = """\
project-name = "camelot"
default-project-scope = "self"

[shared]
exports = ["standards-*"]
glossary = true

[[descendants]]
name = "lore"
path = "lore"
exports = ["camelot-dispatch-contract"]
"""


def write_codex_doc(
    project: Path,
    doc_id: str,
    title: str,
    summary: str,
    *,
    group: str = "",
    related: tuple[str, ...] = (),
) -> Path:
    """Write one codex document into ``project`` and return its path."""
    lines = ["---", f"id: {doc_id}", f"title: {title}", f"summary: {summary}"]
    if related:
        lines.append("related:")
        lines.extend(f"  - {entry}" for entry in related)
    lines += ["---", "", f"# {title}", "", "Body text.", ""]
    directory = project / ".lore" / "codex"
    if group:
        directory = directory / group
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{doc_id}.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


@pytest.fixture()
def nested_tree(tmp_path, monkeypatch):
    """Build ``camelot`` over ``lore``, ``realm`` and ``citadel``.

    The Part 1 tree, on real disk: four initialised projects, camelot's export
    tables, and one authored document per project. The seeded ``codex.md`` is
    removed from each so a codex listing holds only rows this fixture wrote
    (``adr-no-default-content-tests``); every seeded ``default/`` entity tree
    is left in place, because "seeded defaults never cross" is a scenario.

    Returns the ancestor path with the working directory set to it; a test
    reading from a descendant chdirs there itself.
    """
    import lore.config as config_module

    config_module._warned = False

    camelot = tmp_path / "camelot"
    runner = CliRunner()
    for relative in ("", "lore", "realm", "citadel"):
        project = camelot / relative if relative else camelot
        project.mkdir(parents=True, exist_ok=True)
        monkeypatch.chdir(project)
        runner.invoke(main, ["init"])
        (project / ".lore" / "codex" / "codex.md").unlink(missing_ok=True)

    (camelot / ".lore" / "config.toml").write_text(
        NESTED_CAMELOT_CONFIG, encoding="utf-8"
    )

    write_codex_doc(
        camelot,
        "camelot-dispatch-contract",
        "Dispatch Contract",
        "How the three projects hand work to each other.",
        related=(
            "lore:tech-db-schema",
            "realm:tech-dispatch-loop",
            "citadel:tech-views",
        ),
    )
    write_codex_doc(
        camelot,
        "standards-naming",
        "Naming",
        "How every Camelot project names things.",
        group="standards",
    )
    write_codex_doc(
        camelot / "lore",
        "tech-db-schema",
        "DB Schema",
        "The SQLite schema Lore stores state in.",
        group="technical",
    )
    write_codex_doc(
        camelot / "realm",
        "tech-dispatch-loop",
        "Dispatch Loop",
        "How Realm turns a ready mission into a running agent.",
        group="technical",
    )
    write_codex_doc(
        camelot / "citadel",
        "tech-views",
        "Views",
        "The screens Citadel renders.",
        group="technical",
    )

    monkeypatch.chdir(camelot)
    yield camelot
    config_module._warned = False
