"""Tests for lore.models — QuestStatus, MissionStatus, DependencyType alias,
Quest, Mission, Dependency, BoardMessage, Artifact, CodexDocument, Doctrine,
DoctrineStep, Knight, DoctrineListEntry model types."""

import dataclasses
import sqlite3

import lore.models as m
import pytest
from lore.models import DependencyType, MissionStatus, QuestStatus


# ---------------------------------------------------------------------------
# QuestStatus is importable and has the complete set of valid values
# ---------------------------------------------------------------------------
class TestQuestStatusImportAndMembers:
    """QuestStatus imports successfully and has exactly 3 members."""

    def test_quest_status_importable(self):
        assert QuestStatus is not None

    def test_quest_status_has_exactly_three_members(self):
        assert len(QuestStatus) == 3

    def test_quest_status_has_open(self):
        assert QuestStatus.OPEN is not None

    def test_quest_status_has_in_progress(self):
        assert QuestStatus.IN_PROGRESS is not None

    def test_quest_status_has_closed(self):
        assert QuestStatus.CLOSED is not None

    def test_quest_status_open_value(self):
        assert QuestStatus.OPEN.value == "open"

    def test_quest_status_in_progress_value(self):
        assert QuestStatus.IN_PROGRESS.value == "in_progress"

    def test_quest_status_closed_value(self):
        assert QuestStatus.CLOSED.value == "closed"


# ---------------------------------------------------------------------------
# MissionStatus is importable and has the complete set of valid values
# ---------------------------------------------------------------------------
class TestMissionStatusImportAndMembers:
    """MissionStatus imports successfully and has exactly 4 members."""

    def test_mission_status_importable(self):
        assert MissionStatus is not None

    def test_mission_status_has_exactly_four_members(self):
        assert len(MissionStatus) == 4

    def test_mission_status_has_open(self):
        assert MissionStatus.OPEN is not None

    def test_mission_status_has_in_progress(self):
        assert MissionStatus.IN_PROGRESS is not None

    def test_mission_status_has_blocked(self):
        assert MissionStatus.BLOCKED is not None

    def test_mission_status_has_closed(self):
        assert MissionStatus.CLOSED is not None

    def test_mission_status_open_value(self):
        assert MissionStatus.OPEN.value == "open"

    def test_mission_status_in_progress_value(self):
        assert MissionStatus.IN_PROGRESS.value == "in_progress"

    def test_mission_status_blocked_value(self):
        assert MissionStatus.BLOCKED.value == "blocked"

    def test_mission_status_closed_value(self):
        assert MissionStatus.CLOSED.value == "closed"


# ---------------------------------------------------------------------------
# DependencyType is importable as a type alias (not a class/enum)
# ---------------------------------------------------------------------------
class TestDependencyTypeIsTypeAlias:
    """DependencyType is a Literal type alias, not a class or enum."""

    def test_dependency_type_importable(self):
        assert DependencyType is not None

    def test_dependency_type_is_not_a_class(self):
        # A Literal type alias is NOT an instance of type (it's a typing special form)
        assert not isinstance(DependencyType, type)

    def test_dependency_type_is_not_an_enum(self):
        import enum
        assert not (isinstance(DependencyType, type) and issubclass(DependencyType, enum.Enum))


# ---------------------------------------------------------------------------
# Status enum values format to plain lowercase strings (StrEnum shim)
# ---------------------------------------------------------------------------
class TestStatusStringFormatting:
    """str() and f-string formatting return plain lowercase strings."""

    def test_str_quest_status_open(self):
        assert str(QuestStatus.OPEN) == "open"

    def test_fstring_quest_status_in_progress(self):
        assert f"{QuestStatus.IN_PROGRESS}" == "in_progress"

    def test_str_quest_status_closed(self):
        assert str(QuestStatus.CLOSED) == "closed"

    def test_str_mission_status_blocked(self):
        assert str(MissionStatus.BLOCKED) == "blocked"

    def test_str_mission_status_open(self):
        assert str(MissionStatus.OPEN) == "open"

    def test_str_mission_status_in_progress(self):
        assert str(MissionStatus.IN_PROGRESS) == "in_progress"

    def test_str_mission_status_closed(self):
        assert str(MissionStatus.CLOSED) == "closed"

    def test_fstring_not_enum_repr(self):
        # Must never produce "QuestStatus.OPEN"
        assert "QuestStatus" not in f"{QuestStatus.OPEN}"

    def test_fstring_mission_not_enum_repr(self):
        assert "MissionStatus" not in f"{MissionStatus.BLOCKED}"


# ---------------------------------------------------------------------------
# Symmetric equality — enum values compare equal to plain strings both ways
# ---------------------------------------------------------------------------
class TestSymmetricEquality:
    """StrEnum members are equal to their string counterparts in both directions."""

    def test_quest_open_eq_string(self):
        assert QuestStatus.OPEN == "open"

    def test_string_eq_quest_open(self):
        assert "open" == QuestStatus.OPEN

    def test_quest_in_progress_eq_string(self):
        assert QuestStatus.IN_PROGRESS == "in_progress"

    def test_string_eq_quest_in_progress(self):
        assert "in_progress" == QuestStatus.IN_PROGRESS

    def test_quest_closed_eq_string(self):
        assert QuestStatus.CLOSED == "closed"

    def test_mission_blocked_eq_string(self):
        assert MissionStatus.BLOCKED == "blocked"

    def test_string_eq_mission_blocked(self):
        assert "blocked" == MissionStatus.BLOCKED


# ---------------------------------------------------------------------------
# Correct comparison returns True; incorrect comparison returns False
# ---------------------------------------------------------------------------
class TestStatusComparisons:
    """Status comparisons with enum values evaluate correctly."""

    def test_open_status_equals_open_enum(self):
        status = QuestStatus.OPEN
        assert status == QuestStatus.OPEN

    def test_open_status_not_equal_closed_enum(self):
        status = QuestStatus.OPEN
        assert status != QuestStatus.CLOSED
        assert not (status == QuestStatus.CLOSED)

    def test_in_progress_not_equal_open(self):
        status = QuestStatus.IN_PROGRESS
        assert not (status == QuestStatus.OPEN)

    def test_mission_blocked_not_equal_open(self):
        status = MissionStatus.BLOCKED
        assert status == MissionStatus.BLOCKED
        assert not (status == MissionStatus.OPEN)


# ---------------------------------------------------------------------------
# An invalid status string raises ValueError
# ---------------------------------------------------------------------------
class TestInvalidStatusRaisesValueError:
    """Constructing an enum from an unknown string raises ValueError."""

    def test_mission_status_invalid_raises(self):
        with pytest.raises(ValueError):
            MissionStatus("pending")

    def test_quest_status_invalid_raises(self):
        with pytest.raises(ValueError):
            QuestStatus("unknown")

    def test_mission_status_typo_raises(self):
        with pytest.raises(ValueError):
            MissionStatus("in-progress")

    def test_mission_status_empty_raises(self):
        with pytest.raises(ValueError):
            MissionStatus("")


# ---------------------------------------------------------------------------
# QuestStatus, MissionStatus, DependencyType appear in lore.models.__all__
# ---------------------------------------------------------------------------
class TestModelsAllExports:
    """All three names appear in lore.models.__all__."""

    def test_quest_status_in_all(self):
        assert "QuestStatus" in m.__all__

    def test_mission_status_in_all(self):
        assert "MissionStatus" in m.__all__

    def test_dependency_type_in_all(self):
        assert "DependencyType" in m.__all__


# ---------------------------------------------------------------------------
# Helpers — sqlite3.Row factories
# ---------------------------------------------------------------------------


def make_quest_row(**overrides):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE quests (
        id TEXT, title TEXT, description TEXT, status TEXT,
        priority INTEGER, created_at TEXT, updated_at TEXT,
        closed_at TEXT, deleted_at TEXT, auto_close INTEGER
    )""")
    defaults = dict(
        id="q-1", title="T", description="D", status="open",
        priority=2, created_at="2026-01-01", updated_at="2026-01-01",
        closed_at=None, deleted_at=None, auto_close=0,
    )
    defaults.update(overrides)
    conn.execute("INSERT INTO quests VALUES (?,?,?,?,?,?,?,?,?,?)", list(defaults.values()))
    return conn.execute("SELECT * FROM quests").fetchone()


def make_mission_row(**overrides):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE missions (
        id TEXT, quest_id TEXT, title TEXT, description TEXT,
        status TEXT, priority INTEGER, mission_type TEXT, knight TEXT,
        block_reason TEXT, created_at TEXT, updated_at TEXT,
        closed_at TEXT, deleted_at TEXT
    )""")
    defaults = dict(
        id="m-1", quest_id="q-1", title="T", description="D",
        status="open", priority=2, mission_type="feature", knight="knight.md",
        block_reason=None, created_at="2026-01-01", updated_at="2026-01-01",
        closed_at=None, deleted_at=None,
    )
    defaults.update(overrides)
    conn.execute("INSERT INTO missions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", list(defaults.values()))
    return conn.execute("SELECT * FROM missions").fetchone()


# ---------------------------------------------------------------------------
# Quest is importable from lore.models
# ---------------------------------------------------------------------------
class TestQuestImportable:
    """Quest can be imported from lore.models."""

    def test_quest_importable(self):
        from lore.models import Quest
        assert Quest is not None


# ---------------------------------------------------------------------------
# Mission is importable from lore.models
# ---------------------------------------------------------------------------
class TestMissionImportable:
    """Mission can be imported from lore.models."""

    def test_mission_importable(self):
        from lore.models import Mission
        assert Mission is not None


# ---------------------------------------------------------------------------
# Quest has all 10 fields with correct types
# ---------------------------------------------------------------------------
class TestQuestFields:
    """Quest.from_row() produces an object with all 10 fields at correct types."""

    def setup_method(self):
        from lore.models import Quest
        self.Quest = Quest
        self.row = make_quest_row()

    def test_quest_from_row_returns_quest_instance(self):
        quest = self.Quest.from_row(self.row)
        assert isinstance(quest, self.Quest)

    def test_quest_id_is_str(self):
        quest = self.Quest.from_row(self.row)
        assert isinstance(quest.id, str)

    def test_quest_title_is_str(self):
        quest = self.Quest.from_row(self.row)
        assert isinstance(quest.title, str)

    def test_quest_description_is_str(self):
        quest = self.Quest.from_row(self.row)
        assert isinstance(quest.description, str)

    def test_quest_status_is_str(self):
        quest = self.Quest.from_row(self.row)
        assert isinstance(quest.status, str)

    def test_quest_priority_is_int(self):
        quest = self.Quest.from_row(self.row)
        assert isinstance(quest.priority, int)

    def test_quest_created_at_is_str(self):
        quest = self.Quest.from_row(self.row)
        assert isinstance(quest.created_at, str)

    def test_quest_updated_at_is_str(self):
        quest = self.Quest.from_row(self.row)
        assert isinstance(quest.updated_at, str)

    def test_quest_closed_at_field_exists(self):
        quest = self.Quest.from_row(self.row)
        assert hasattr(quest, "closed_at")

    def test_quest_deleted_at_field_exists(self):
        quest = self.Quest.from_row(self.row)
        assert hasattr(quest, "deleted_at")

    def test_quest_auto_close_field_exists(self):
        quest = self.Quest.from_row(self.row)
        assert hasattr(quest, "auto_close")

    def test_quest_field_values_match_row(self):
        quest = self.Quest.from_row(self.row)
        assert quest.id == "q-1"
        assert quest.title == "T"
        assert quest.description == "D"
        assert quest.status == "open"
        assert quest.priority == 2


# ---------------------------------------------------------------------------
# Mission has all 13 fields with correct types
# ---------------------------------------------------------------------------
class TestMissionFields:
    """Mission.from_row() produces an object with all 13 fields at correct types."""

    def setup_method(self):
        from lore.models import Mission
        self.Mission = Mission
        self.row = make_mission_row()

    def test_mission_from_row_returns_mission_instance(self):
        mission = self.Mission.from_row(self.row)
        assert isinstance(mission, self.Mission)

    def test_mission_id_is_str(self):
        mission = self.Mission.from_row(self.row)
        assert isinstance(mission.id, str)

    def test_mission_title_is_str(self):
        mission = self.Mission.from_row(self.row)
        assert isinstance(mission.title, str)

    def test_mission_description_is_str(self):
        mission = self.Mission.from_row(self.row)
        assert isinstance(mission.description, str)

    def test_mission_status_is_str(self):
        mission = self.Mission.from_row(self.row)
        assert isinstance(mission.status, str)

    def test_mission_priority_is_int(self):
        mission = self.Mission.from_row(self.row)
        assert isinstance(mission.priority, int)

    def test_mission_mission_type_is_str(self):
        mission = self.Mission.from_row(self.row)
        assert isinstance(mission.mission_type, str)

    def test_mission_created_at_is_str(self):
        mission = self.Mission.from_row(self.row)
        assert isinstance(mission.created_at, str)

    def test_mission_updated_at_is_str(self):
        mission = self.Mission.from_row(self.row)
        assert isinstance(mission.updated_at, str)

    def test_mission_quest_id_field_exists(self):
        mission = self.Mission.from_row(self.row)
        assert hasattr(mission, "quest_id")

    def test_mission_knight_field_exists(self):
        mission = self.Mission.from_row(self.row)
        assert hasattr(mission, "knight")

    def test_mission_block_reason_field_exists(self):
        mission = self.Mission.from_row(self.row)
        assert hasattr(mission, "block_reason")

    def test_mission_closed_at_field_exists(self):
        mission = self.Mission.from_row(self.row)
        assert hasattr(mission, "closed_at")

    def test_mission_deleted_at_field_exists(self):
        mission = self.Mission.from_row(self.row)
        assert hasattr(mission, "deleted_at")

    def test_mission_field_values_match_row(self):
        mission = self.Mission.from_row(self.row)
        assert mission.id == "m-1"
        assert mission.quest_id == "q-1"
        assert mission.title == "T"
        assert mission.status == "open"
        assert mission.priority == 2
        assert mission.mission_type == "feature"


# ---------------------------------------------------------------------------
# Nullable fields accept None
# ---------------------------------------------------------------------------
class TestNullableFields:
    """Optional fields on Quest and Mission accept None values."""

    def test_quest_closed_at_none(self):
        from lore.models import Quest
        row = make_quest_row(closed_at=None)
        quest = Quest.from_row(row)
        assert quest.closed_at is None

    def test_quest_deleted_at_none(self):
        from lore.models import Quest
        row = make_quest_row(deleted_at=None)
        quest = Quest.from_row(row)
        assert quest.deleted_at is None

    def test_mission_quest_id_none(self):
        from lore.models import Mission
        row = make_mission_row(quest_id=None)
        mission = Mission.from_row(row)
        assert mission.quest_id is None

    def test_mission_knight_none(self):
        from lore.models import Mission
        row = make_mission_row(knight=None)
        mission = Mission.from_row(row)
        assert mission.knight is None

    def test_mission_block_reason_none(self):
        from lore.models import Mission
        row = make_mission_row(block_reason=None)
        mission = Mission.from_row(row)
        assert mission.block_reason is None

    def test_mission_closed_at_none(self):
        from lore.models import Mission
        row = make_mission_row(closed_at=None)
        mission = Mission.from_row(row)
        assert mission.closed_at is None

    def test_mission_deleted_at_none(self):
        from lore.models import Mission
        row = make_mission_row(deleted_at=None)
        mission = Mission.from_row(row)
        assert mission.deleted_at is None


# ---------------------------------------------------------------------------
# auto_close is coerced to bool
# ---------------------------------------------------------------------------
class TestAutoCloseCoercion:
    """auto_close integer values are coerced to Python bool on Quest.from_row()."""

    def test_auto_close_zero_is_false(self):
        from lore.models import Quest
        row = make_quest_row(auto_close=0)
        quest = Quest.from_row(row)
        assert quest.auto_close is False

    def test_auto_close_one_is_true(self):
        from lore.models import Quest
        row = make_quest_row(auto_close=1)
        quest = Quest.from_row(row)
        assert quest.auto_close is True

    def test_auto_close_zero_type_is_bool(self):
        from lore.models import Quest
        row = make_quest_row(auto_close=0)
        quest = Quest.from_row(row)
        assert type(quest.auto_close) is bool

    def test_auto_close_one_type_is_bool(self):
        from lore.models import Quest
        row = make_quest_row(auto_close=1)
        quest = Quest.from_row(row)
        assert type(quest.auto_close) is bool


# ---------------------------------------------------------------------------
# Quest and Mission are immutable (frozen dataclasses)
# ---------------------------------------------------------------------------
class TestImmutability:
    """Assigning to any field on Quest or Mission raises FrozenInstanceError."""

    def test_quest_id_immutable(self):
        from lore.models import Quest
        quest = Quest.from_row(make_quest_row())
        with pytest.raises(dataclasses.FrozenInstanceError):
            quest.id = "q-new"

    def test_quest_title_immutable(self):
        from lore.models import Quest
        quest = Quest.from_row(make_quest_row())
        with pytest.raises(dataclasses.FrozenInstanceError):
            quest.title = "New Title"

    def test_quest_status_immutable(self):
        from lore.models import Quest
        quest = Quest.from_row(make_quest_row())
        with pytest.raises(dataclasses.FrozenInstanceError):
            quest.status = "closed"

    def test_quest_auto_close_immutable(self):
        from lore.models import Quest
        quest = Quest.from_row(make_quest_row())
        with pytest.raises(dataclasses.FrozenInstanceError):
            quest.auto_close = True

    def test_mission_id_immutable(self):
        from lore.models import Mission
        mission = Mission.from_row(make_mission_row())
        with pytest.raises(dataclasses.FrozenInstanceError):
            mission.id = "m-new"

    def test_mission_title_immutable(self):
        from lore.models import Mission
        mission = Mission.from_row(make_mission_row())
        with pytest.raises(dataclasses.FrozenInstanceError):
            mission.title = "New Title"

    def test_mission_status_immutable(self):
        from lore.models import Mission
        mission = Mission.from_row(make_mission_row())
        with pytest.raises(dataclasses.FrozenInstanceError):
            mission.status = "closed"

    def test_mission_quest_id_immutable(self):
        from lore.models import Mission
        mission = Mission.from_row(make_mission_row())
        with pytest.raises(dataclasses.FrozenInstanceError):
            mission.quest_id = "q-new"


# ---------------------------------------------------------------------------
# Quest and Mission appear in lore.models.__all__
# ---------------------------------------------------------------------------
class TestAllExports:
    """Quest and Mission are listed in lore.models.__all__."""

    def test_quest_in_all(self):
        assert "Quest" in m.__all__

    def test_mission_in_all(self):
        assert "Mission" in m.__all__


class TestDependencyImportable:
    def test_dependency_importable(self):
        from lore.models import Dependency  # noqa: F401


class TestDependencyFields:
    def test_direct_construction(self):
        from lore.models import Dependency
        dep = Dependency(id=1, from_id="m-aaa", to_id="m-bbb", type="blocks", deleted_at=None)
        assert dep.id == 1
        assert dep.from_id == "m-aaa"
        assert dep.to_id == "m-bbb"
        assert dep.type == "blocks"
        assert dep.deleted_at is None

    def test_from_row_with_sqlite(self):
        import sqlite3
        from lore.models import Dependency
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id TEXT NOT NULL,
            to_id TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'blocks',
            deleted_at TEXT
        )""")
        conn.execute("INSERT INTO dependencies (from_id, to_id, type, deleted_at) VALUES (?,?,?,?)",
                     ("m-aaa", "m-bbb", "blocks", None))
        row = conn.execute("SELECT * FROM dependencies").fetchone()
        dep = Dependency.from_row(row)
        assert dep.id == 1
        assert dep.from_id == "m-aaa"
        assert dep.to_id == "m-bbb"
        assert dep.type == "blocks"
        assert dep.deleted_at is None


class TestDependencyImmutability:
    def test_frozen(self):
        import dataclasses
        from lore.models import Dependency
        dep = Dependency(id=1, from_id="m-aaa", to_id="m-bbb", type="blocks", deleted_at=None)
        with pytest.raises(dataclasses.FrozenInstanceError):
            dep.from_id = "m-zzz"  # type: ignore[misc]


class TestDependencyAllExport:
    def test_dependency_in_all(self):
        import lore.models as m
        assert "Dependency" in m.__all__


# ── BoardMessage ──────────────────────────────────────────────────────────────

class TestBoardMessageImportable:
    def test_board_message_importable(self):
        from lore.models import BoardMessage  # noqa: F401

class TestBoardMessageFields:
    def _make(self, **overrides):
        from lore.models import BoardMessage
        data = {"id": 1, "entity_id": "q-abc1", "message": "hello",
                "sender": None, "created_at": "2025-01-01T00:00:00Z"}
        data.update(overrides)
        return BoardMessage.from_dict(data)

    def test_id_field(self):
        msg = self._make()
        assert msg.id == 1
        assert type(msg.id) is int

    def test_entity_id_field(self):
        msg = self._make()
        assert msg.entity_id == "q-abc1"

    def test_message_field(self):
        msg = self._make()
        assert msg.message == "hello"

    def test_sender_none(self):
        msg = self._make(sender=None)
        assert msg.sender is None

    def test_sender_set(self):
        msg = self._make(sender="knight-1")
        assert msg.sender == "knight-1"

    def test_created_at_field(self):
        msg = self._make()
        assert msg.created_at == "2025-01-01T00:00:00Z"

class TestBoardMessageKeyError:
    def test_missing_sender_key_raises(self):
        from lore.models import BoardMessage
        data = {"id": 1, "entity_id": "q-abc1", "message": "hello",
                "created_at": "2025-01-01T00:00:00Z"}  # no sender key
        with pytest.raises(KeyError):
            BoardMessage.from_dict(data)

class TestBoardMessageImmutability:
    def test_frozen(self):
        import dataclasses
        from lore.models import BoardMessage
        msg = BoardMessage.from_dict({"id": 1, "entity_id": "q-abc1",
                                      "message": "hello", "sender": None,
                                      "created_at": "2025-01-01T00:00:00Z"})
        with pytest.raises(dataclasses.FrozenInstanceError):
            msg.message = "edited"  # type: ignore[misc]

class TestBoardMessageAllExport:
    def test_board_message_in_all(self):
        import lore.models as m
        assert "BoardMessage" in m.__all__


# ── Artifact ──────────────────────────────────────────────────────────────────

class TestArtifactImportable:
    def test_artifact_importable(self):
        from lore.models import Artifact  # noqa: F401

class TestArtifactFields:
    _data = {"id": "tpl-1", "title": "My Template",
             "summary": "A summary", "body": "Template content here"}

    def test_id_field(self):
        from lore.models import Artifact
        a = Artifact.from_dict(self._data)
        assert a.id == "tpl-1"

    def test_title_field(self):
        from lore.models import Artifact
        a = Artifact.from_dict(self._data)
        assert a.title == "My Template"

    def test_summary_field(self):
        from lore.models import Artifact
        a = Artifact.from_dict(self._data)
        assert a.summary == "A summary"

    def test_body_maps_to_content(self):
        from lore.models import Artifact
        a = Artifact.from_dict(self._data)
        assert a.content == "Template content here"

class TestArtifactExtraKeysIgnored:
    def test_extra_key_ignored(self):
        from pathlib import Path
        from lore.models import Artifact
        data = {"id": "x", "title": "T", "summary": "S",
                "body": "B", "path": Path("/some/path")}
        a = Artifact.from_dict(data)
        assert a.content == "B"

class TestArtifactScanOutputRaisesKeyError:
    def test_missing_body_key_raises(self):
        from lore.models import Artifact
        data = {"id": "x", "title": "T", "summary": "S",
                "path": "/some/path"}  # no 'body' key
        with pytest.raises(KeyError):
            Artifact.from_dict(data)

class TestArtifactImmutability:
    def test_frozen(self):
        import dataclasses
        from lore.models import Artifact
        a = Artifact.from_dict({"id": "x", "title": "T",
                                 "summary": "S", "body": "B"})
        with pytest.raises(dataclasses.FrozenInstanceError):
            a.content = "changed"  # type: ignore[misc]

class TestArtifactAllExport:
    def test_artifact_in_all(self):
        import lore.models as m
        assert "Artifact" in m.__all__


# remove-type-field-us-7 — AttributeError test added (not deleted)
def test_artifact_type_attr_raises_attribute_error():
    from lore.models import Artifact
    a = Artifact.from_dict({"id": "x", "title": "T", "summary": "S", "group": "g", "body": ""})
    with pytest.raises(AttributeError):
        _ = a.type


# ── CodexDocument ─────────────────────────────────────────────────────────────

class TestCodexDocumentImportable:
    def test_codex_document_importable(self):
        from lore.models import CodexDocument  # noqa: F401

class TestCodexDocumentFields:
    def test_from_scan_dict(self):
        from pathlib import Path
        from lore.models import CodexDocument
        data = {"id": "tech-1", "title": "Overview",
                "summary": "A summary", "path": Path("/a/b.md")}
        doc = CodexDocument.from_dict(data)
        assert doc.id == "tech-1"
        assert doc.title == "Overview"
        assert doc.summary == "A summary"

    def test_from_read_dict(self):
        from lore.models import CodexDocument
        data = {"id": "tech-1", "title": "Overview",
                "summary": "A summary", "body": "Full content here"}
        doc = CodexDocument.from_dict(data)
        assert doc.id == "tech-1"

    def test_no_body_field(self):
        from lore.models import CodexDocument
        data = {"id": "x", "title": "T", "summary": "S", "body": "B"}
        doc = CodexDocument.from_dict(data)
        assert not hasattr(doc, "body")

    def test_no_path_field(self):
        from pathlib import Path
        from lore.models import CodexDocument
        data = {"id": "x", "title": "T", "summary": "S",
                "path": Path("/a.md")}
        doc = CodexDocument.from_dict(data)
        assert not hasattr(doc, "path")

class TestCodexDocumentImmutability:
    def test_frozen(self):
        import dataclasses
        from lore.models import CodexDocument
        doc = CodexDocument.from_dict({"id": "x", "title": "T", "summary": "S"})
        with pytest.raises(dataclasses.FrozenInstanceError):
            doc.title = "changed"  # type: ignore[misc]

class TestCodexDocumentAllExport:
    def test_codex_document_in_all(self):
        import lore.models as m
        assert "CodexDocument" in m.__all__


# remove-type-field-us-7 — AttributeError test added (not deleted)
def test_codex_document_type_attr_raises_attribute_error():
    from lore.models import CodexDocument
    doc = CodexDocument.from_dict({"id": "y", "title": "Y", "summary": "s"})
    with pytest.raises(AttributeError):
        _ = doc.type


# ── Doctrine + DoctrineStep ───────────────────────────────────────────────────

class TestDoctrineImportable:
    def test_doctrine_importable(self):
        from lore.models import Doctrine, DoctrineStep  # noqa: F401

class TestDoctrineStepFields:
    def _make_step(self, **overrides):
        from lore.models import DoctrineStep
        data = {"id": "plan", "title": "Plan work", "priority": 1,
                "type": "knight", "knight": "tdd-red.md",
                "notes": "Some notes", "needs": ["intake"]}
        data.update(overrides)
        return DoctrineStep.from_dict(data)

    def test_id_field(self):
        assert self._make_step().id == "plan"

    def test_title_field(self):
        assert self._make_step().title == "Plan work"

    def test_priority_field(self):
        assert self._make_step().priority == 1

    def test_type_field(self):
        assert self._make_step().type == "knight"

    def test_knight_field(self):
        assert self._make_step().knight == "tdd-red.md"

    def test_notes_field(self):
        assert self._make_step().notes == "Some notes"

    def test_needs_field(self):
        assert self._make_step().needs == ["intake"]

    def test_needs_defaults_to_empty_list(self):
        step = self._make_step()
        data = {"id": "plan", "title": "Plan work", "priority": 1}
        from lore.models import DoctrineStep
        step = DoctrineStep.from_dict(data)
        assert step.needs == []
        assert step.type is None
        assert step.knight is None
        assert step.notes is None

class TestDoctrineFields:
    def _make_doctrine(self):
        from lore.models import Doctrine
        data = {
            "name": "bugfix",
            "description": "Bug fix workflow",
            "steps": [
                {"id": "intake", "title": "Intake", "priority": 0},
                {"id": "fix", "title": "Fix bug", "priority": 1, "type": "knight"},
            ]
        }
        return Doctrine.from_dict(data)

    def test_name_field(self):
        assert self._make_doctrine().name == "bugfix"

    def test_description_field(self):
        assert self._make_doctrine().description == "Bug fix workflow"

    def test_steps_is_tuple(self):
        import lore.models as m
        doctrine = self._make_doctrine()
        assert isinstance(doctrine.steps, tuple)
        assert isinstance(doctrine.steps[0], m.DoctrineStep)

    def test_steps_count(self):
        assert len(self._make_doctrine().steps) == 2

class TestDoctrineListDictRaisesKeyError:
    def test_list_doctrines_dict_raises(self):
        from lore.models import Doctrine
        # list_doctrines() output — no 'steps' key
        data = {"name": "bugfix", "filename": "bugfix.yaml",
                "description": "Bug fix", "valid": True}
        with pytest.raises(KeyError):
            Doctrine.from_dict(data)

class TestDoctrineImmutability:
    def test_doctrine_frozen(self):
        import dataclasses
        from lore.models import Doctrine
        d = Doctrine.from_dict({"name": "x", "description": "y", "steps": []})
        with pytest.raises(dataclasses.FrozenInstanceError):
            d.name = "changed"  # type: ignore[misc]

    def test_steps_tuple_no_append(self):
        from lore.models import Doctrine
        d = Doctrine.from_dict({"name": "x", "description": "y", "steps": []})
        with pytest.raises(AttributeError):
            d.steps.append("anything")  # type: ignore[attr-defined]

    def test_doctrine_step_frozen(self):
        import dataclasses
        from lore.models import DoctrineStep
        step = DoctrineStep.from_dict({"id": "s", "title": "T", "priority": 0})
        with pytest.raises(dataclasses.FrozenInstanceError):
            step.title = "changed"  # type: ignore[misc]

class TestDoctrineAllExport:
    def test_doctrine_in_all(self):
        import lore.models as m
        assert "Doctrine" in m.__all__
        assert "DoctrineStep" in m.__all__


# ── Knight ────────────────────────────────────────────────────────────────────

class TestKnightImportable:
    def test_knight_importable(self):
        from lore.models import Knight  # noqa: F401

class TestKnightFields:
    def test_direct_construction(self):
        from lore.models import Knight
        k = Knight(name="developer", content="# Developer\nYou are a dev.")
        assert k.name == "developer"
        assert k.content == "# Developer\nYou are a dev."

    def test_no_from_dict(self):
        from lore.models import Knight
        assert not hasattr(Knight, "from_dict")

    def test_no_from_row(self):
        from lore.models import Knight
        assert not hasattr(Knight, "from_row")

class TestKnightImmutability:
    def test_frozen(self):
        import dataclasses
        from lore.models import Knight
        k = Knight(name="developer", content="# Developer")
        with pytest.raises(dataclasses.FrozenInstanceError):
            k.content = "changed"  # type: ignore[misc]

class TestKnightAllExport:
    def test_knight_in_all(self):
        import lore.models as m
        assert "Knight" in m.__all__


# ── DoctrineListEntry ─────────────────────────────────────────────────────────

class TestDoctrineListEntryImportable:
    def test_importable(self):
        from lore.models import DoctrineListEntry  # noqa: F401

class TestDoctrineListEntryValidEntry:
    def _valid(self):
        from lore.models import DoctrineListEntry
        return DoctrineListEntry.from_dict({
            "name": "bugfix", "filename": "bugfix.yaml",
            "description": "Bug fix workflow", "valid": True
        })

    def test_name(self):
        assert self._valid().name == "bugfix"

    def test_filename(self):
        assert self._valid().filename == "bugfix.yaml"

    def test_description(self):
        assert self._valid().description == "Bug fix workflow"

    def test_valid_true(self):
        assert self._valid().valid is True

    def test_errors_empty_tuple(self):
        entry = self._valid()
        assert entry.errors == ()
        assert type(entry.errors) is tuple
        assert bool(entry.errors) is False

class TestDoctrineListEntryInvalidEntry:
    def _invalid(self):
        from lore.models import DoctrineListEntry
        return DoctrineListEntry.from_dict({
            "name": "bad", "filename": "bad.yaml", "description": "",
            "valid": False, "errors": ["Missing required field: steps"]
        })

    def test_valid_false(self):
        assert self._invalid().valid is False

    def test_errors_tuple(self):
        entry = self._invalid()
        assert entry.errors == ("Missing required field: steps",)
        assert type(entry.errors) is tuple
        assert isinstance(entry.errors, tuple)

class TestDoctrineListEntryImmutability:
    def test_frozen(self):
        import dataclasses
        from lore.models import DoctrineListEntry
        entry = DoctrineListEntry.from_dict({
            "name": "x", "filename": "x.yaml", "description": "", "valid": True
        })
        with pytest.raises(dataclasses.FrozenInstanceError):
            entry.valid = False  # type: ignore[misc]

class TestDoctrineListEntryAllExport:
    def test_in_all(self):
        import lore.models as m
        assert "DoctrineListEntry" in m.__all__

class TestDoctrineListEntryIntegration:
    def test_real_list_doctrines(self, tmp_path, monkeypatch):
        """Integration: list_doctrines output can be wrapped in DoctrineListEntry."""
        from lore.models import DoctrineListEntry
        from lore.doctrine import list_doctrines
        # Create a minimal doctrine file
        doctrines_dir = tmp_path / "doctrines"
        doctrines_dir.mkdir()
        (doctrines_dir / "test.yaml").write_text(
            "name: test\ndescription: Test doctrine\nsteps:\n  - id: s1\n    title: Step 1\n"
        )
        entries = list_doctrines(doctrines_dir)
        assert len(entries) == 1
        wrapped = [DoctrineListEntry.from_dict(e) for e in entries]
        assert wrapped[0].name == "test"
        assert wrapped[0].valid is True
        assert wrapped[0].errors == ()


# ── py.typed ──────────────────────────────────────────────────────────────────

class TestPyTyped:
    def test_py_typed_exists(self):
        """py.typed PEP 561 marker must exist in the installed package."""
        import importlib.util
        import pathlib
        spec = importlib.util.find_spec("lore")
        assert spec is not None
        package_dir = pathlib.Path(spec.origin).parent
        py_typed = package_dir / "py.typed"
        assert py_typed.exists(), f"py.typed not found at {py_typed}"

    def test_py_typed_is_empty(self):
        """py.typed must be empty per PEP 561."""
        import importlib.util
        import pathlib
        spec = importlib.util.find_spec("lore")
        assert spec is not None
        package_dir = pathlib.Path(spec.origin).parent
        py_typed = package_dir / "py.typed"
        assert py_typed.exists()
        assert py_typed.read_text() == ""


# ── CHANGELOG + version ──────────────────────────────────────────────────────

class TestChangelog:
    _root = __import__("pathlib").Path(__file__).parent.parent.parent

    def test_changelog_exists(self):
        assert (self._root / "CHANGELOG.md").exists()

    def test_changelog_starts_with_heading(self):
        content = (self._root / "CHANGELOG.md").read_text()
        assert content.startswith("# Changelog")

    def test_changelog_has_unreleased_section(self):
        content = (self._root / "CHANGELOG.md").read_text()
        assert "## [Unreleased]" in content



# ── mypy CI ───────────────────────────────────────────────────────────────────

class TestMypyConfig:
    _root = __import__("pathlib").Path(__file__).parent.parent.parent

    def test_mypy_in_dev_deps(self):
        content = (self._root / "pyproject.toml").read_text()
        assert "mypy" in content

    def test_tool_mypy_section_exists(self):
        content = (self._root / "pyproject.toml").read_text()
        assert "[tool.mypy]" in content

    def test_disallow_untyped_defs(self):
        content = (self._root / "pyproject.toml").read_text()
        assert "disallow_untyped_defs = true" in content

    def test_no_implicit_optional(self):
        content = (self._root / "pyproject.toml").read_text()
        assert "no_implicit_optional = true" in content

    def test_warn_redundant_casts(self):
        content = (self._root / "pyproject.toml").read_text()
        assert "warn_redundant_casts = true" in content

    def test_warn_unused_ignores(self):
        content = (self._root / "pyproject.toml").read_text()
        assert "warn_unused_ignores = true" in content

class TestMypyClean:
    def test_models_py_mypy_clean(self):
        """mypy must report no errors in src/lore/models.py."""
        import subprocess
        result = subprocess.run(
            ["uv", "run", "mypy", "src/lore/models.py"],
            capture_output=True, text=True,
            cwd=str(__import__("pathlib").Path(__file__).parent.parent.parent)
        )
        assert result.returncode == 0, (
            f"mypy reported errors:\n{result.stdout}\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# Watcher frozen dataclass — construction, from_dict, optional fields, __all__
# Spec: watchers-us-7 (lore codex show watchers-us-7)
# Fails until Watcher dataclass is added to lore/models.py
# ---------------------------------------------------------------------------


class TestWatcherImportable:
    """Watcher can be imported from lore.models and is listed in __all__."""

    def test_watcher_importable(self):
        # Spec: watchers-us-7 Unit — Watcher is importable
        from lore.models import Watcher
        assert Watcher is not None

    def test_watcher_in_models_all(self):
        # Spec: watchers-us-7 Unit — Watcher listed in models.__all__
        import lore.models as m
        assert "Watcher" in m.__all__, f"'Watcher' not found in __all__: {m.__all__}"


class TestWatcherFrozen:
    """Watcher is a frozen dataclass — assignment to any field raises FrozenInstanceError."""

    def test_watcher_frozen_raises_on_id_assignment(self):
        # Spec: watchers-us-7 Unit — frozen dataclass
        import dataclasses

        from lore.models import Watcher

        watcher = Watcher(
            id="test-id",
            group="default",
            title="Test",
            summary="Summary",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            watcher.id = "changed"  # type: ignore[misc]

    def test_watcher_frozen_raises_on_title_assignment(self):
        # Spec: watchers-us-7 Unit — frozen applies to all fields
        import dataclasses

        from lore.models import Watcher

        watcher = Watcher(
            id="test-id",
            group="default",
            title="Test",
            summary="Summary",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            watcher.title = "new title"  # type: ignore[misc]


class TestWatcherFromDictFull:
    """Watcher.from_dict constructs a correct instance from a full dict (all 8 keys)."""

    def test_from_dict_full_constructs_correct_instance(self):
        # Spec: watchers-us-7 Unit — from_dict with all 8 keys present
        from lore.models import Watcher

        d = {
            "id": "my-watcher",
            "group": "my-group",
            "title": "My Watcher",
            "summary": "Watches for push events",
            "watch_target": "feature/*",
            "interval": "daily",
            "action": "run-checks",
            "filename": "my-watcher.yaml",
        }
        watcher = Watcher.from_dict(d)

        assert watcher.id == "my-watcher"
        assert watcher.group == "my-group"
        assert watcher.title == "My Watcher"
        assert watcher.summary == "Watches for push events"
        assert watcher.watch_target == "feature/*"
        assert watcher.interval == "daily"
        assert watcher.action == "run-checks"
        assert watcher.filename == "my-watcher.yaml"

    def test_from_dict_full_returns_watcher_instance(self):
        # Spec: watchers-us-7 Unit — result is a Watcher instance
        from lore.models import Watcher

        d = {
            "id": "w-1",
            "group": "grp",
            "title": "T",
            "summary": "S",
            "watch_target": "feature/*",
            "interval": "daily",
            "action": "run-tests",
            "filename": "w-1.yaml",
        }
        watcher = Watcher.from_dict(d)
        assert isinstance(watcher, Watcher)


class TestWatcherFromDictOptionalNone:
    """Watcher.from_dict defaults optional fields to None when absent from dict."""

    def test_watch_target_defaults_to_none_when_absent(self):
        # Spec: watchers-us-7 Unit / Scenario 8
        from lore.models import Watcher

        watcher = Watcher.from_dict({"id": "x", "group": "", "title": "T", "summary": "S"})
        assert watcher.watch_target is None

    def test_interval_defaults_to_none_when_absent(self):
        # Spec: watchers-us-7 Unit / Scenario 8
        from lore.models import Watcher

        watcher = Watcher.from_dict({"id": "x", "group": "", "title": "T", "summary": "S"})
        assert watcher.interval is None

    def test_action_defaults_to_none_when_absent(self):
        # Spec: watchers-us-7 Unit / Scenario 8
        from lore.models import Watcher

        watcher = Watcher.from_dict({"id": "x", "group": "", "title": "T", "summary": "S"})
        assert watcher.action is None

    def test_filename_defaults_to_none_when_absent(self):
        # Spec: watchers-us-7 Unit / Scenario 8
        from lore.models import Watcher

        watcher = Watcher.from_dict({"id": "x", "group": "", "title": "T", "summary": "S"})
        assert watcher.filename is None

    def test_from_dict_list_dict_shape_constructs_correctly(self):
        # Spec: watchers-us-7 Unit — constructs from list dict (has group field, no optionals)
        from lore.models import Watcher

        list_dict = {
            "id": "my-watcher",
            "group": "my-group",
            "title": "My Watcher",
            "summary": "Watches for push events",
            "filename": "my-watcher.yaml",
        }
        watcher = Watcher.from_dict(list_dict)

        assert watcher.id == "my-watcher"
        assert watcher.group == "my-group"
        assert watcher.watch_target is None
        assert watcher.interval is None
        assert watcher.action is None
