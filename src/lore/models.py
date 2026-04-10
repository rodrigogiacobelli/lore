"""Quest, Mission, and related data models."""

import dataclasses
import enum
import sqlite3
from typing import Literal

from lore.health import HealthIssue, HealthReport, health_check

try:
    from enum import StrEnum
except ImportError:
    class StrEnum(str, enum.Enum):  # type: ignore[no-redef]
        def __str__(self) -> str:
            return self.value


class QuestStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


class MissionStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    CLOSED = "closed"


DependencyType = Literal["blocks"]


@dataclasses.dataclass(frozen=True)
class Quest:
    id: str
    title: str
    description: str
    status: QuestStatus
    priority: int
    auto_close: bool
    created_at: str
    updated_at: str
    closed_at: str | None
    deleted_at: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Quest":
        return cls(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            status=QuestStatus(row["status"]),
            priority=row["priority"],
            auto_close=bool(row["auto_close"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            closed_at=row["closed_at"],
            deleted_at=row["deleted_at"],
        )


@dataclasses.dataclass(frozen=True)
class Mission:
    id: str
    quest_id: str | None
    title: str
    description: str
    status: MissionStatus
    mission_type: str | None
    priority: int
    knight: str | None
    block_reason: str | None
    created_at: str
    updated_at: str
    closed_at: str | None
    deleted_at: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Mission":
        return cls(
            id=row["id"],
            quest_id=row["quest_id"],
            title=row["title"],
            description=row["description"],
            status=MissionStatus(row["status"]),
            mission_type=row["mission_type"],
            priority=row["priority"],
            knight=row["knight"],
            block_reason=row["block_reason"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            closed_at=row["closed_at"],
            deleted_at=row["deleted_at"],
        )


@dataclasses.dataclass(frozen=True)
class Dependency:
    """Typed representation of a row from the dependencies table.

    No public db.py function currently returns a full dependencies row as a
    sqlite3.Row. get_mission_depends_on_details() and get_mission_blocks_details()
    return joined summary dicts — not the full row shape. A get_dependency()
    function must be added to db.py before runtime hydration via from_row() is
    possible.
    """

    id: int
    from_id: str
    to_id: str
    type: DependencyType
    deleted_at: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Dependency":
        return cls(
            id=row["id"],
            from_id=row["from_id"],
            to_id=row["to_id"],
            type=row["type"],
            deleted_at=row["deleted_at"],
        )


@dataclasses.dataclass(frozen=True)
class BoardMessage:
    """Typed representation of a board message from get_board_messages() output.

    from_dict() is designed for get_board_messages() output only.
    Passing add_board_message() output raises KeyError('message').
    """
    id: int
    entity_id: str
    sender: str | None
    message: str
    created_at: str

    @classmethod
    def from_dict(cls, d: dict) -> "BoardMessage":
        return cls(
            id=d["id"],
            entity_id=d["entity_id"],
            sender=d["sender"],
            message=d["message"],
            created_at=d["created_at"],
        )


@dataclasses.dataclass(frozen=True)
class Artifact:
    """Typed representation of read_artifact() output.

    The 'body' key from read_artifact() is exposed as 'content'.
    Do not pass scan_artifacts() output — it has no 'body' key and raises KeyError.
    """
    id: str
    title: str
    summary: str
    content: str

    @classmethod
    def from_dict(cls, d: dict) -> "Artifact":
        return cls(
            id=d["id"],
            title=d["title"],
            summary=d["summary"],
            content=d["body"],
        )


@dataclasses.dataclass(frozen=True)
class CodexDocument:
    """Listing-level typed representation from scan_codex() or read_document().

    Only the three metadata fields are exposed — no body content.
    Extra keys (path, body, type) in the source dict are silently ignored.
    """
    id: str
    title: str
    summary: str

    @classmethod
    def from_dict(cls, d: dict) -> "CodexDocument":
        return cls(
            id=d["id"],
            title=d["title"],
            summary=d["summary"],
        )


@dataclasses.dataclass(frozen=True)
class DoctrineStep:
    """Typed representation of a single step in a doctrine.

    Note: needs is list[str] per spec. frozen=True prevents reassignment
    but not list mutation (step.needs.append(...) is not blocked).
    """

    id: str
    title: str
    priority: int
    type: str | None
    knight: str | None
    notes: str | None
    needs: list[str]

    @classmethod
    def from_dict(cls, d: dict) -> "DoctrineStep":
        return cls(
            id=d["id"],
            title=d["title"],
            priority=d.get("priority", 2),
            type=d.get("type"),
            knight=d.get("knight"),
            notes=d.get("notes"),
            needs=list(d.get("needs", [])),
        )


@dataclasses.dataclass(frozen=True)
class Doctrine:
    """Typed representation of load_doctrine() output.

    from_dict() requires load_doctrine(filepath) output — NOT list_doctrines() output.
    Passing list_doctrines() output raises KeyError('steps').
    """

    id: str
    title: str
    summary: str
    steps: tuple[DoctrineStep, ...]

    @classmethod
    def from_dict(cls, d: dict) -> "Doctrine":
        return cls(
            id=d["id"],
            title=d.get("title", d["id"]),
            summary=d.get("summary", ""),
            steps=tuple(DoctrineStep.from_dict(s) for s in d["steps"]),
        )


@dataclasses.dataclass(frozen=True)
class Knight:
    """Typed representation of a knight persona.

    No from_dict() or from_row() — construct directly:
        Knight(name=path.stem, content=path.read_text())

    name: filename stem, e.g. "developer" (not full filename or path)
    content: full markdown body to pass verbatim to worker agents
    """
    name: str
    content: str


@dataclasses.dataclass(frozen=True)
class Watcher:
    """Typed representation of a watcher definition from load_watcher() output."""
    id: str
    group: str
    title: str
    summary: str
    watch_target: object = None
    interval: object = None
    action: object = None
    filename: object = None

    @classmethod
    def from_dict(cls, d: dict) -> "Watcher":
        return cls(
            id=d["id"],
            group=d["group"],
            title=d["title"],
            summary=d["summary"],
            watch_target=d.get("watch_target"),
            interval=d.get("interval"),
            action=d.get("action"),
            filename=d.get("filename"),
        )


@dataclasses.dataclass(frozen=True)
class DoctrineListEntry:
    """Typed representation of a single entry from list_doctrines() output.

    This is NOT a full Doctrine. To get full doctrine data, call
    load_doctrine(filepath) and use Doctrine.from_dict().

    All entries from list_doctrines() have valid=True.
    filename points to the .design.md file, not the .yaml file.
    """
    id: str
    group: str
    title: str
    summary: str
    valid: bool
    filename: str

    @classmethod
    def from_dict(cls, d: dict) -> "DoctrineListEntry":
        return cls(
            id=d["id"],
            group=d["group"],
            title=d["title"],
            summary=d["summary"],
            valid=d["valid"],
            filename=d["filename"],
        )


__all__ = [
    "QuestStatus",
    "MissionStatus",
    "DependencyType",
    "Quest",
    "Mission",
    "Dependency",
    "BoardMessage",
    "Artifact",
    "CodexDocument",
    "DoctrineStep",
    "Doctrine",
    "Knight",
    "DoctrineListEntry",
    "Watcher",
    "HealthIssue",
    "HealthReport",
    "health_check",
]
