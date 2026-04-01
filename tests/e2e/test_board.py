"""E2E tests for board messages — posting, displaying, and deleting board messages.

Spec: conceptual-workflows-board (lore codex show conceptual-workflows-board)
"""

import json
import re

from lore.cli import main
from tests.conftest import (
    assert_exit_ok,
    assert_exit_err,
    db_conn,
    insert_board_message,
    insert_mission,
    insert_quest,
)


# ---------------------------------------------------------------------------
# Add board message to a mission
# ---------------------------------------------------------------------------


class TestAddBoardMessageToMission:
    """lore board add posts a message to a mission."""

    def test_exit_code_zero(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        result = runner.invoke(main, ["board", "add", m_id, "Handoff note"])
        assert_exit_ok(result)

    def test_output_contains_id(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        result = runner.invoke(main, ["board", "add", m_id, "Handoff note"])
        assert "Board message posted" in result.output
        assert "id:" in result.output

    def test_exact_confirmation_format(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Test Mission")
        result = runner.invoke(main, ["board", "add", "q-a1b2/m-f3c1", "my note"])
        assert result.exit_code == 0
        assert "Board message posted (id: 1)." in result.output

    def test_row_in_db(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        runner.invoke(main, ["board", "add", m_id, "Handoff note"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT entity_id, message, sender, deleted_at "
                "FROM board_messages WHERE entity_id = ?",
                (m_id,),
            ).fetchone()
        assert row is not None
        assert row["entity_id"] == m_id
        assert row["message"] == "Handoff note"
        assert row["sender"] is None
        assert row["deleted_at"] is None


# ---------------------------------------------------------------------------
# Add board message to a quest
# ---------------------------------------------------------------------------


class TestAddBoardMessageToQuest:
    """lore board add posts a message to a quest."""

    def test_row_in_db_with_quest_entity_id(self, runner, project_dir):
        insert_quest(project_dir, "q-aaa1", "Test Quest")
        result = runner.invoke(main, ["board", "add", "q-aaa1", "Quest-level note"])
        assert_exit_ok(result)
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT entity_id FROM board_messages WHERE entity_id = ?", ("q-aaa1",)
            ).fetchone()
        assert row is not None
        assert row["entity_id"] == "q-aaa1"

    def test_nonexistent_quest_fails(self, runner, project_dir):
        result = runner.invoke(main, ["board", "add", "q-0000", "some note"])
        assert result.exit_code != 0

    def test_existing_quest_message_appears_in_show(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        runner.invoke(main, ["board", "add", "q-a1b2", "phase 1 complete"])
        result = runner.invoke(main, ["show", "q-a1b2"])
        assert "phase 1 complete" in result.output


# ---------------------------------------------------------------------------
# Sender flag
# ---------------------------------------------------------------------------


class TestAddBoardMessageWithSender:
    """--sender flag stores the sender in the board_messages row."""

    def test_sender_stored(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M Cur", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M Prev", "-q", quest_id])
        m_cur = json.loads(r1.output)["id"]
        m_prev = json.loads(r2.output)["id"]
        result = runner.invoke(
            main, ["board", "add", m_cur, "See codex doc", "--sender", m_prev]
        )
        assert_exit_ok(result)
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT sender FROM board_messages WHERE entity_id = ?", (m_cur,)
            ).fetchone()
        assert row["sender"] == m_prev


# ---------------------------------------------------------------------------
# Board messages appear in lore show
# ---------------------------------------------------------------------------


class TestBoardMessageInMissionShow:
    """Board messages appear in lore show mission output."""

    def test_board_section_present(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        runner.invoke(main, ["board", "add", m_id, "No sender message"])
        result = runner.invoke(main, ["show", m_id])
        assert_exit_ok(result)
        assert "Board" in result.output
        assert "No sender message" in result.output

    def test_message_with_sender_in_show(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M Cur", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M Prev", "-q", quest_id])
        m_cur = json.loads(r1.output)["id"]
        m_prev = json.loads(r2.output)["id"]
        runner.invoke(main, ["board", "add", m_cur, "With sender msg", "--sender", m_prev])
        result = runner.invoke(main, ["show", m_cur])
        assert "With sender msg" in result.output
        assert m_prev in result.output

    def test_message_formatted_with_timestamp(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Test Mission")
        runner.invoke(main, ["board", "add", "q-a1b2/m-f3c1", "timestamped note"])
        result = runner.invoke(main, ["show", "q-a1b2/m-f3c1"])
        iso_pattern = re.compile(r"\s+\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
        assert iso_pattern.search(result.output)

    def test_no_board_section_when_no_messages(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        result = runner.invoke(main, ["show", m_id])
        assert_exit_ok(result)
        assert "Board:" not in result.output


class TestBoardMessageInQuestShow:
    """Board messages appear in lore show quest output."""

    def test_board_section_in_quest_show(self, runner, project_dir):
        insert_quest(project_dir, "q-aaa1", "Test Quest")
        runner.invoke(main, ["board", "add", "q-aaa1", "Quest board note"])
        result = runner.invoke(main, ["show", "q-aaa1"])
        assert_exit_ok(result)
        assert "Board" in result.output
        assert "Quest board note" in result.output

    def test_quest_board_and_mission_board_are_independent(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Test Mission")
        runner.invoke(main, ["board", "add", "q-a1b2", "quest-level note"])
        runner.invoke(main, ["board", "add", "q-a1b2/m-f3c1", "mission-level note"])
        quest_show = runner.invoke(main, ["show", "q-a1b2"])
        assert "quest-level note" in quest_show.output
        assert "mission-level note" not in quest_show.output
        mission_show = runner.invoke(main, ["show", "q-a1b2/m-f3c1"])
        assert "mission-level note" in mission_show.output
        assert "quest-level note" not in mission_show.output

    def test_messages_ordered_oldest_first(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        with db_conn(project_dir) as conn:
            conn.execute(
                "INSERT INTO board_messages (entity_id, message, created_at) VALUES (?, ?, ?)",
                ("q-a1b2", "first older message", "2026-01-01T10:00:00Z"),
            )
            conn.execute(
                "INSERT INTO board_messages (entity_id, message, created_at) VALUES (?, ?, ?)",
                ("q-a1b2", "second newer message", "2026-01-01T11:00:00Z"),
            )
            conn.commit()
        result = runner.invoke(main, ["show", "q-a1b2"])
        output = result.output
        pos_first = output.find("first older message")
        pos_second = output.find("second newer message")
        assert pos_first < pos_second


# ---------------------------------------------------------------------------
# Delete board message
# ---------------------------------------------------------------------------


class TestDeleteBoardMessage:
    """lore board delete soft-deletes a message."""

    def test_message_deleted(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        runner.invoke(main, ["board", "add", m_id, "To be deleted"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT id FROM board_messages WHERE entity_id = ?", (m_id,)
            ).fetchone()
        msg_id = row["id"]
        result = runner.invoke(main, ["board", "delete", str(msg_id)])
        assert_exit_ok(result)
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT deleted_at FROM board_messages WHERE id = ?", (msg_id,)
            ).fetchone()
        assert row["deleted_at"] is not None

    def test_deleted_message_not_in_show(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        runner.invoke(main, ["board", "add", m_id, "Deleted note"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT id FROM board_messages WHERE entity_id = ?", (m_id,)
            ).fetchone()
        msg_id = row["id"]
        runner.invoke(main, ["board", "delete", str(msg_id)])
        result = runner.invoke(main, ["show", m_id])
        assert "Deleted note" not in result.output

    def test_json_shape(self, runner, project_dir):
        insert_quest(project_dir, "q-aaa1", "Q")
        insert_board_message(project_dir, "q-aaa1", "Test message")
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT id FROM board_messages WHERE entity_id = ?", ("q-aaa1",)
            ).fetchone()
        msg_id = row["id"]
        result = runner.invoke(main, ["--json", "board", "delete", str(msg_id)])
        assert_exit_ok(result)
        data = json.loads(result.output)
        assert "id" in data
        assert "deleted_at" in data
        assert data["id"] == msg_id
        assert isinstance(data["id"], int)

    def test_not_found_exits_1(self, runner, project_dir):
        result = runner.invoke(main, ["board", "delete", "9999"])
        assert result.exit_code == 1

    def test_not_found_error_message(self, runner, project_dir):
        result = runner.invoke(main, ["board", "delete", "9999"])
        combined = result.output + (result.stderr or "")
        assert "9999" in combined
        assert "not found" in combined.lower()


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestAddEmptyMessageRejected:
    """Empty or whitespace-only messages are rejected."""

    def test_empty_exits_1(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        result = runner.invoke(main, ["board", "add", m_id, ""])
        assert result.exit_code == 1

    def test_empty_no_row_inserted(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        runner.invoke(main, ["board", "add", m_id, ""])
        with db_conn(project_dir) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM board_messages WHERE entity_id = ?", (m_id,)
            ).fetchone()[0]
        assert count == 0

    def test_whitespace_exits_1(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        result = runner.invoke(main, ["board", "add", m_id, "   "])
        assert result.exit_code == 1


class TestAddBoardMessageEntityNotFound:
    """board add to a non-existent entity fails with exit code 1."""

    def test_exit_code_1(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        result = runner.invoke(main, ["board", "add", f"{quest_id}/m-0000", "Note"])
        assert result.exit_code == 1

    def test_error_mentions_not_found(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        result = runner.invoke(main, ["board", "add", f"{quest_id}/m-0000", "Note"])
        combined = result.output + (result.stderr or "")
        assert "not found" in combined.lower() or "invalid" in combined.lower()


class TestAddBoardMessageMalformedId:
    """board add with an invalid entity ID format fails with exit code 1."""

    def test_exit_code_1(self, runner, project_dir):
        result = runner.invoke(main, ["board", "add", "not-a-valid-id", "Note"])
        assert result.exit_code == 1

    def test_no_row_inserted(self, runner, project_dir):
        runner.invoke(main, ["board", "add", "not-a-valid-id", "Note"])
        with db_conn(project_dir) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM board_messages WHERE entity_id = ?",
                ("not-a-valid-id",),
            ).fetchone()[0]
        assert count == 0


# ---------------------------------------------------------------------------
# Entity ID format validation at the DB layer
# ---------------------------------------------------------------------------


class TestEntityIdFormatValidation:
    """add_board_message rejects badly-formatted entity IDs before any DB access."""

    def test_free_form_string_returns_ok_false(self, project_dir):
        from lore.db import add_board_message as _add
        result = _add(project_dir, "notanid", "hello")
        assert result["ok"] is False
        assert result.get("error") == 'Invalid entity ID format: "notanid"'

    def test_wrong_prefix_returns_ok_false(self, project_dir):
        from lore.db import add_board_message as _add
        result = _add(project_dir, "x-1234", "hello")
        assert result["ok"] is False

    def test_malformed_id_stores_no_row(self, project_dir):
        from lore.db import add_board_message as _add
        _add(project_dir, "notanid", "hello")
        with db_conn(project_dir) as conn:
            count = conn.execute("SELECT COUNT(*) FROM board_messages").fetchone()[0]
        assert count == 0

    def test_format_check_fires_before_message_check(self, project_dir):
        from lore.db import add_board_message as _add
        result = _add(project_dir, "notanid", "")
        assert result.get("error") == 'Invalid entity ID format: "notanid"'

    def test_message_check_fires_before_existence_check(self, project_dir):
        from lore.db import add_board_message as _add
        result = _add(project_dir, "q-a1b2", "")
        assert result["ok"] is False
        assert result.get("error") == "Message cannot be empty."
        assert "not found" not in result.get("error", "").lower()


# ---------------------------------------------------------------------------
# Standalone mission routing
# ---------------------------------------------------------------------------


class TestStandaloneMissionRouting:
    """add_board_message routes m-xxxx to the missions table, not the quests table."""

    def test_post_to_standalone_mission_returns_ok_true(self, project_dir):
        from lore.db import add_board_message as _add
        insert_mission(project_dir, "m-a1b2", None, "Standalone Mission")
        result = _add(project_dir, "m-a1b2", "standalone note")
        assert result["ok"] is True

    def test_nonexistent_standalone_mission_error_mentions_mission(self, project_dir):
        from lore.db import add_board_message as _add
        result = _add(project_dir, "m-0000", "a note")
        assert result["ok"] is False
        error = result.get("error", "")
        assert "Mission" in error
        assert "Quest" not in error
