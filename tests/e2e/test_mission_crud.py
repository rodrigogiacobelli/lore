"""E2E tests for mission CRUD operations.

Spec: conceptual-workflows-mission-crud (lore codex show conceptual-workflows-mission-crud)
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from lore.cli import main
from lore.db import list_missions
from tests.conftest import (
    assert_exit_ok,
    assert_exit_err,
    db_conn,
    insert_dependency,
    insert_mission,
    insert_quest,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_knight_file(project_dir: Path, filename: str, content: str) -> None:
    """Create a knight file in .lore/knights/."""
    knights_dir = project_dir / ".lore" / "knights"
    knights_dir.mkdir(parents=True, exist_ok=True)
    (knights_dir / filename).write_text(content)


# ---------------------------------------------------------------------------
# Create mission in a quest
# ---------------------------------------------------------------------------


class TestCreateMissionInQuest:
    """lore new mission with -q creates a mission within a quest."""

    def test_exit_code_zero(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q One"])
        quest_id = json.loads(r.output)["id"]
        result = runner.invoke(
            main,
            ["--json", "new", "mission", "Implement OAuth", "-q", quest_id,
             "-d", "Use PKCE flow.", "-p", "1"],
        )
        assert_exit_ok(result)

    def test_id_has_quest_prefix(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q One"])
        quest_id = json.loads(r.output)["id"]
        result = runner.invoke(
            main, ["--json", "new", "mission", "Implement OAuth", "-q", quest_id]
        )
        mission_id = json.loads(result.output)["id"]
        assert mission_id.startswith(quest_id + "/m-")

    def test_id_format_matches_pattern(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        result = runner.invoke(main, ["new", "mission", "Update payment API", "-q", "q-a1b2"])
        assert result.exit_code == 0
        assert re.search(r"q-a1b2/m-[a-f0-9]{4,6}", result.output)

    def test_db_fields_stored_correctly(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q One"])
        quest_id = json.loads(r.output)["id"]
        result = runner.invoke(
            main,
            ["--json", "new", "mission", "Implement OAuth", "-q", quest_id,
             "-d", "Use PKCE flow.", "-p", "1"],
        )
        mission_id = json.loads(result.output)["id"]
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT quest_id, title, description, priority, mission_type "
                "FROM missions WHERE id = ?",
                (mission_id,),
            ).fetchone()
        assert row["quest_id"] == quest_id
        assert row["title"] == "Implement OAuth"
        assert row["description"] == "Use PKCE flow."
        assert row["priority"] == 1
        assert row["mission_type"] is None

    def test_mission_has_open_status(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        runner.invoke(main, ["new", "mission", "Update payment API", "-q", "q-a1b2"])
        with db_conn(project_dir) as conn:
            rows = conn.execute("SELECT status FROM missions").fetchall()
        assert rows[0]["status"] == "open"

    def test_mission_quest_id_set(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        runner.invoke(main, ["new", "mission", "Update payment API", "-q", "q-a1b2"])
        with db_conn(project_dir) as conn:
            rows = conn.execute("SELECT quest_id FROM missions").fetchall()
        assert rows[0]["quest_id"] == "q-a1b2"

    def test_with_knight_flag(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q One"])
        quest_id = json.loads(r.output)["id"]
        result = runner.invoke(
            main,
            ["--json", "new", "mission", "Auth Task", "-q", quest_id, "-k", "developer.md"],
        )
        assert_exit_ok(result)
        mission_id = json.loads(result.output)["id"]
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT knight FROM missions WHERE id = ?", (mission_id,)
            ).fetchone()
        assert row["knight"] == "developer.md"


# ---------------------------------------------------------------------------
# Create mission with mission type
# ---------------------------------------------------------------------------


class TestCreateMissionWithType:
    """lore new mission with -T sets mission_type."""

    def test_mission_type_stored(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q One"])
        quest_id = json.loads(r.output)["id"]
        result = runner.invoke(
            main,
            ["--json", "new", "mission", "Review PR", "-q", quest_id, "-T", "review"],
        )
        assert_exit_ok(result)
        mission_id = json.loads(result.output)["id"]
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT mission_type FROM missions WHERE id = ?", (mission_id,)
            ).fetchone()
        assert row["mission_type"] == "review"


# ---------------------------------------------------------------------------
# Create standalone mission (no quest)
# ---------------------------------------------------------------------------


class TestCreateStandaloneMission:
    """lore new mission without -q creates a standalone m-yyyy mission."""

    def test_standalone_id_format(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "new", "mission", "Fix a standalone bug"])
        assert_exit_ok(result)
        mission_id = json.loads(result.output)["id"]
        assert mission_id.startswith("m-")
        assert "/" not in mission_id

    def test_id_format_regex(self, runner, project_dir):
        runner.invoke(main, ["new", "mission", "Fix a standalone bug"])
        with db_conn(project_dir) as conn:
            rows = conn.execute("SELECT id FROM missions").fetchall()
        assert re.match(r"^m-[a-f0-9]{4,6}$", rows[0]["id"])

    def test_quest_id_is_null_in_db(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "new", "mission", "Fix a standalone bug"])
        mission_id = json.loads(result.output)["id"]
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT quest_id FROM missions WHERE id = ?", (mission_id,)
            ).fetchone()
        assert row["quest_id"] is None

    def test_standalone_when_two_open_quests(self, runner, project_dir):
        runner.invoke(main, ["new", "quest", "Quest A"])
        runner.invoke(main, ["new", "quest", "Quest B"])
        result = runner.invoke(main, ["--json", "new", "mission", "Ambiguous mission"])
        assert_exit_ok(result)
        mission_id = json.loads(result.output)["id"]
        assert mission_id.startswith("m-")
        assert "/" not in mission_id


# ---------------------------------------------------------------------------
# Create mission — priority out of range
# ---------------------------------------------------------------------------


class TestCreateMissionPriorityOutOfRange:
    """lore new mission -p 5 exits with an error."""

    def test_exit_code_nonzero(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        result = runner.invoke(
            main, ["new", "mission", "Bad", "-q", quest_id, "-p", "5"]
        )
        assert result.exit_code != 0

    def test_error_mentions_priority(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        result = runner.invoke(
            main, ["new", "mission", "Bad", "-q", quest_id, "-p", "5"]
        )
        combined = result.output + (result.stderr or "")
        assert "priority" in combined.lower() or "0" in combined

    def test_priority_5_rejected(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        result = runner.invoke(
            main, ["new", "mission", "Bad priority", "-q", "q-a1b2", "-p", "5"]
        )
        assert result.exit_code != 0

    def test_priority_negative_rejected(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        result = runner.invoke(
            main, ["new", "mission", "Bad priority", "-q", "q-a1b2", "-p", "-1"]
        )
        assert result.exit_code != 0

    def test_no_mission_created_on_invalid_priority(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        runner.invoke(main, ["new", "mission", "Bad priority", "-q", "q-a1b2", "-p", "5"])
        with db_conn(project_dir) as conn:
            rows = conn.execute("SELECT id FROM missions").fetchall()
        assert len(rows) == 0

    def test_priority_0_accepted(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        result = runner.invoke(main, ["new", "mission", "P0 mission", "-q", "q-a1b2", "-p", "0"])
        assert result.exit_code == 0

    def test_priority_4_accepted(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        result = runner.invoke(main, ["new", "mission", "P4 mission", "-q", "q-a1b2", "-p", "4"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Mission default values
# ---------------------------------------------------------------------------


class TestMissionDefaultValues:
    """Mission created without optional flags has correct defaults."""

    def test_default_priority(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        runner.invoke(main, ["new", "mission", "Simple task", "-q", "q-a1b2"])
        with db_conn(project_dir) as conn:
            rows = conn.execute("SELECT priority FROM missions").fetchall()
        assert rows[0]["priority"] == 2

    def test_default_description(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        runner.invoke(main, ["new", "mission", "Simple task", "-q", "q-a1b2"])
        with db_conn(project_dir) as conn:
            rows = conn.execute("SELECT description FROM missions").fetchall()
        assert rows[0]["description"] == ""

    def test_default_knight_is_null(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        runner.invoke(main, ["new", "mission", "Simple task", "-q", "q-a1b2"])
        with db_conn(project_dir) as conn:
            rows = conn.execute("SELECT knight FROM missions").fetchall()
        assert rows[0]["knight"] is None

    def test_default_status_is_open(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        runner.invoke(main, ["new", "mission", "Simple task", "-q", "q-a1b2"])
        with db_conn(project_dir) as conn:
            rows = conn.execute("SELECT status FROM missions").fetchall()
        assert rows[0]["status"] == "open"


# ---------------------------------------------------------------------------
# Automatic timestamps on mission creation
# ---------------------------------------------------------------------------


class TestMissionTimestamps:
    """Missions get created_at, updated_at set to now; closed_at is null."""

    def test_created_at_set(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        before = datetime.now(timezone.utc).replace(microsecond=0)
        runner.invoke(main, ["new", "mission", "Timestamp test", "-q", "q-a1b2"])
        with db_conn(project_dir) as conn:
            rows = conn.execute("SELECT created_at FROM missions").fetchall()
        created_at = datetime.strptime(rows[0]["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        after = datetime.now(timezone.utc).replace(microsecond=0)
        assert before <= created_at <= after

    def test_created_at_utc_format(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        runner.invoke(main, ["new", "mission", "Timestamp test", "-q", "q-a1b2"])
        with db_conn(project_dir) as conn:
            rows = conn.execute("SELECT created_at FROM missions").fetchall()
        assert rows[0]["created_at"].endswith("Z")
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", rows[0]["created_at"])

    def test_closed_at_is_null(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        runner.invoke(main, ["new", "mission", "Timestamp test", "-q", "q-a1b2"])
        with db_conn(project_dir) as conn:
            rows = conn.execute("SELECT closed_at FROM missions").fetchall()
        assert rows[0]["closed_at"] is None


# ---------------------------------------------------------------------------
# Unique mission IDs
# ---------------------------------------------------------------------------


class TestUniqueMissionIds:
    """Multiple missions in a quest get unique IDs."""

    def test_no_id_collision(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        for i in range(10):
            result = runner.invoke(main, ["new", "mission", f"Mission {i}", "-q", "q-a1b2"])
            assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            rows = conn.execute("SELECT id FROM missions").fetchall()
        ids = {r["id"] for r in rows}
        assert len(ids) == 10


# ---------------------------------------------------------------------------
# Creating a mission in a nonexistent quest
# ---------------------------------------------------------------------------


class TestMissionInNonexistentQuest:
    """Creating a mission in a nonexistent quest fails."""

    def test_exit_code_1(self, runner, project_dir):
        result = runner.invoke(main, ["new", "mission", "Task", "-q", "q-xxxx"])
        assert result.exit_code == 1

    def test_no_mission_created(self, runner, project_dir):
        runner.invoke(main, ["new", "mission", "Task", "-q", "q-xxxx"])
        with db_conn(project_dir) as conn:
            rows = conn.execute("SELECT id FROM missions").fetchall()
        assert len(rows) == 0


# ---------------------------------------------------------------------------
# Quest inference when exactly one non-closed quest exists
# ---------------------------------------------------------------------------


class TestQuestInference:
    """lore new mission without -q infers quest when exactly one non-closed exists."""

    def test_infers_single_open_quest(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Only Quest"])
        quest_id = json.loads(r.output)["id"]
        result = runner.invoke(main, ["--json", "new", "mission", "Auto-assigned"])
        assert_exit_ok(result)
        mission_id = json.loads(result.output)["id"]
        assert mission_id.startswith(quest_id + "/m-")

    def test_db_quest_id_set(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Only Quest"])
        quest_id = json.loads(r.output)["id"]
        result = runner.invoke(main, ["--json", "new", "mission", "Auto-assigned"])
        mission_id = json.loads(result.output)["id"]
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT quest_id FROM missions WHERE id = ?", (mission_id,)
            ).fetchone()
        assert row["quest_id"] == quest_id

    def test_no_inference_with_zero_quests(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "new", "mission", "No Quest"])
        assert_exit_ok(result)
        mission_id = json.loads(result.output)["id"]
        assert mission_id.startswith("m-")
        assert "/" not in mission_id

    def test_no_inference_with_two_open_quests(self, runner, project_dir):
        runner.invoke(main, ["new", "quest", "Quest A"])
        runner.invoke(main, ["new", "quest", "Quest B"])
        result = runner.invoke(main, ["--json", "new", "mission", "Ambiguous"])
        assert_exit_ok(result)
        mission_id = json.loads(result.output)["id"]
        assert mission_id.startswith("m-")
        assert "/" not in mission_id


# ---------------------------------------------------------------------------
# Adding a mission to a closed quest reopens it
# ---------------------------------------------------------------------------


class TestAddMissionToClosedQuest:
    """Adding a mission to a closed quest reopens it."""

    def test_quest_reopens(self, runner, project_dir):
        insert_quest(
            project_dir, "q-closed1", "Closed Quest",
            status="closed", closed_at="2025-01-20T00:00:00Z",
        )
        result = runner.invoke(main, ["new", "mission", "New Task", "-q", "q-closed1"])
        assert_exit_ok(result)
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status, closed_at FROM quests WHERE id = ?", ("q-closed1",)
            ).fetchone()
        assert row["status"] == "open"
        assert row["closed_at"] is None

    def test_mission_created_successfully(self, runner, project_dir):
        insert_quest(
            project_dir, "q-closed1", "Closed Quest",
            status="closed", closed_at="2025-01-20T00:00:00Z",
        )
        result = runner.invoke(main, ["--json", "new", "mission", "New Task", "-q", "q-closed1"])
        assert_exit_ok(result)
        mission_id = json.loads(result.output)["id"]
        assert mission_id.startswith("q-closed1/m-")


# ---------------------------------------------------------------------------
# List missions — default shows only active (open, in_progress, blocked)
# ---------------------------------------------------------------------------


class TestListMissionsActiveOnly:
    """lore missions shows only active missions by default."""

    def test_active_missions_present(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "Open M", "-q", quest_id])
        m_open = json.loads(r1.output)["id"]
        r2 = runner.invoke(main, ["--json", "new", "mission", "To Close", "-q", quest_id])
        m_close = json.loads(r2.output)["id"]
        runner.invoke(main, ["done", m_close])

        result = runner.invoke(main, ["--json", "missions"])
        assert_exit_ok(result)
        data = json.loads(result.output)
        ids = [m["id"] for m in data["missions"]]
        assert m_open in ids
        assert m_close not in ids

    def test_standalone_mission_in_output(self, runner, project_dir):
        result_m = runner.invoke(main, ["--json", "new", "mission", "Standalone Task"])
        standalone_id = json.loads(result_m.output)["id"]
        result = runner.invoke(main, ["--json", "missions"])
        data = json.loads(result.output)
        ids = [m["id"] for m in data["missions"]]
        assert standalone_id in ids

    def test_in_progress_included_in_default(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_mission(project_dir, "q-aaaa/m-bb01", "q-aaaa", "Open Mission", status="open")
        insert_mission(project_dir, "q-aaaa/m-bb02", "q-aaaa", "IP Mission", status="in_progress")
        result = runner.invoke(main, ["missions"])
        assert "Open Mission" in result.output
        assert "IP Mission" in result.output

    def test_blocked_included_in_default(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_mission(project_dir, "q-aaaa/m-bb01", "q-aaaa", "Open Mission", status="open")
        insert_mission(project_dir, "q-aaaa/m-bb02", "q-aaaa", "Blocked Mission", status="blocked")
        result = runner.invoke(main, ["missions"])
        assert "Open Mission" in result.output
        assert "Blocked Mission" in result.output

    def test_closed_excluded_by_default(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_mission(project_dir, "q-aaaa/m-bb01", "q-aaaa", "Open Mission", status="open")
        insert_mission(
            project_dir, "q-aaaa/m-bb02", "q-aaaa", "Closed Mission",
            status="closed", closed_at="2025-01-15T10:00:00Z",
        )
        result = runner.invoke(main, ["missions"])
        assert "Open Mission" in result.output
        assert "Closed Mission" not in result.output

    def test_grouped_by_quest(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest Alpha")
        insert_quest(project_dir, "q-bbbb", "Quest Beta")
        insert_mission(project_dir, "q-aaaa/m-aa01", "q-aaaa", "Alpha Mission")
        insert_mission(project_dir, "q-bbbb/m-bb01", "q-bbbb", "Beta Mission")
        result = runner.invoke(main, ["missions"])
        assert "Quest Alpha" in result.output
        assert "Alpha Mission" in result.output
        assert "Quest Beta" in result.output
        assert "Beta Mission" in result.output

    def test_sorted_by_priority_then_created_at(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_mission(
            project_dir, "q-aaaa/m-bb01", "q-aaaa", "P3 Mission",
            priority=3, created_at="2025-01-15T09:00:00Z",
        )
        insert_mission(
            project_dir, "q-aaaa/m-bb02", "q-aaaa", "P1 Mission",
            priority=1, created_at="2025-01-15T10:00:00Z",
        )
        result = runner.invoke(main, ["missions"])
        p1_pos = result.output.index("P1 Mission")
        p3_pos = result.output.index("P3 Mission")
        assert p1_pos < p3_pos


# ---------------------------------------------------------------------------
# List missions — --all includes closed
# ---------------------------------------------------------------------------


class TestListMissionsAll:
    """lore missions --all includes closed missions."""

    def test_both_present(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "Open M", "-q", quest_id])
        m_open = json.loads(r1.output)["id"]
        r2 = runner.invoke(main, ["--json", "new", "mission", "Closed M", "-q", quest_id])
        m_closed = json.loads(r2.output)["id"]
        runner.invoke(main, ["done", m_closed])

        result = runner.invoke(main, ["--json", "missions", "--all"])
        assert_exit_ok(result)
        data = json.loads(result.output)
        ids = [m["id"] for m in data["missions"]]
        assert m_open in ids
        assert m_closed in ids

    def test_all_flag_includes_blocked(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_mission(project_dir, "q-aaaa/m-bb01", "q-aaaa", "Blocked Mission", status="blocked")
        result = runner.invoke(main, ["missions", "--all"])
        assert "Blocked Mission" in result.output

    def test_all_flag_includes_in_progress(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_mission(project_dir, "q-aaaa/m-bb01", "q-aaaa", "IP Mission", status="in_progress")
        result = runner.invoke(main, ["missions", "--all"])
        assert "IP Mission" in result.output


# ---------------------------------------------------------------------------
# List missions — scoped to one quest
# ---------------------------------------------------------------------------


class TestListMissionsScopedToQuest:
    """lore missions q-xxxx shows only missions for that quest."""

    def test_only_target_quest_missions(self, runner, project_dir):
        r1 = runner.invoke(main, ["--json", "new", "quest", "Quest A"])
        qid_a = json.loads(r1.output)["id"]
        r2 = runner.invoke(main, ["--json", "new", "quest", "Quest B"])
        qid_b = json.loads(r2.output)["id"]

        ra1 = runner.invoke(main, ["--json", "new", "mission", "A Mission 1", "-q", qid_a])
        ra2 = runner.invoke(main, ["--json", "new", "mission", "A Mission 2", "-q", qid_a])
        rb1 = runner.invoke(main, ["--json", "new", "mission", "B Mission 1", "-q", qid_b])

        m_a1 = json.loads(ra1.output)["id"]
        m_a2 = json.loads(ra2.output)["id"]
        m_b1 = json.loads(rb1.output)["id"]

        result = runner.invoke(main, ["--json", "missions", qid_a])
        assert_exit_ok(result)
        data = json.loads(result.output)
        ids = [m["id"] for m in data["missions"]]
        assert m_a1 in ids
        assert m_a2 in ids
        assert m_b1 not in ids

    def test_filters_by_quest_human_output(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_quest(project_dir, "q-bbbb", "Quest B")
        insert_mission(project_dir, "q-aaaa/m-aa01", "q-aaaa", "Alpha Mission")
        insert_mission(project_dir, "q-bbbb/m-bb01", "q-bbbb", "Beta Mission")
        result = runner.invoke(main, ["missions", "q-aaaa"])
        assert result.exit_code == 0
        assert "Alpha Mission" in result.output
        assert "Beta Mission" not in result.output

    def test_quest_not_found_exits_code_1(self, runner, project_dir):
        result = runner.invoke(main, ["missions", "q-xxxx"])
        assert result.exit_code == 1

    def test_quest_not_found_message(self, runner, project_dir):
        result = runner.invoke(main, ["missions", "q-xxxx"])
        assert 'Quest "q-xxxx" not found' in result.output

    def test_quest_filter_with_all_flag(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_mission(project_dir, "q-aaaa/m-bb01", "q-aaaa", "Open Mission", status="open")
        insert_mission(
            project_dir, "q-aaaa/m-bb02", "q-aaaa", "Closed Mission",
            status="closed", closed_at="2025-01-15T10:00:00Z",
        )
        insert_mission(project_dir, "q-aaaa/m-bb03", "q-aaaa", "IP Mission", status="in_progress")
        result = runner.invoke(main, ["missions", "q-aaaa", "--all"])
        assert result.exit_code == 0
        assert "Open Mission" in result.output
        assert "Closed Mission" in result.output
        assert "IP Mission" in result.output


# ---------------------------------------------------------------------------
# Standalone missions appear in listings
# ---------------------------------------------------------------------------


class TestStandaloneMissionsInListing:
    """Standalone missions appear in a 'Standalone' section."""

    def test_standalone_section_shown(self, runner, project_dir):
        insert_mission(project_dir, "m-aa01", None, "Standalone Task")
        result = runner.invoke(main, ["missions"])
        assert result.exit_code == 0
        assert "Standalone" in result.output
        assert "Standalone Task" in result.output

    def test_standalone_and_quest_missions(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_mission(project_dir, "q-aaaa/m-aa01", "q-aaaa", "Quest Mission")
        insert_mission(project_dir, "m-bb01", None, "Standalone Task")
        result = runner.invoke(main, ["missions"])
        assert "Quest A" in result.output
        assert "Quest Mission" in result.output
        assert "Standalone" in result.output
        assert "Standalone Task" in result.output


# ---------------------------------------------------------------------------
# Empty mission listing
# ---------------------------------------------------------------------------


class TestEmptyMissionListing:
    """lore missions with no missions shows empty result, no error."""

    def test_empty_no_error(self, runner, project_dir):
        result = runner.invoke(main, ["missions"])
        assert result.exit_code == 0

    def test_empty_with_quest_filter(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        result = runner.invoke(main, ["missions", "q-aaaa"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# DB API: list_missions() uses include_closed parameter
# ---------------------------------------------------------------------------


class TestListMissionsDbApi:
    """list_missions() accepts include_closed parameter."""

    def test_include_closed_param_exists(self, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_mission(project_dir, "q-aaaa/m-0001", "q-aaaa", "Open Task", status="open")
        result = list_missions(project_dir, include_closed=False)
        assert result is not None

    def test_include_closed_false_excludes_closed(self, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_mission(project_dir, "q-aaaa/m-0001", "q-aaaa", "Open Task", status="open")
        insert_mission(project_dir, "q-aaaa/m-0002", "q-aaaa", "IP Task", status="in_progress")
        insert_mission(project_dir, "q-aaaa/m-0003", "q-aaaa", "Blocked Task", status="blocked")
        insert_mission(
            project_dir, "q-aaaa/m-0004", "q-aaaa", "Closed Task",
            status="closed", closed_at="2025-01-15T10:00:00Z",
        )
        grouped = list_missions(project_dir, include_closed=False)
        all_titles = [m["title"] for missions in grouped.values() for m in missions]
        assert "Open Task" in all_titles
        assert "IP Task" in all_titles
        assert "Blocked Task" in all_titles
        assert "Closed Task" not in all_titles

    def test_include_closed_true_includes_closed(self, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_mission(project_dir, "q-aaaa/m-0001", "q-aaaa", "Open Task", status="open")
        insert_mission(
            project_dir, "q-aaaa/m-0002", "q-aaaa", "Closed Task",
            status="closed", closed_at="2025-01-15T10:00:00Z",
        )
        grouped = list_missions(project_dir, include_closed=True)
        all_titles = [m["title"] for missions in grouped.values() for m in missions]
        assert "Open Task" in all_titles
        assert "Closed Task" in all_titles

    def test_default_param_shows_active_statuses(self, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_mission(project_dir, "q-aaaa/m-0001", "q-aaaa", "Open Task", status="open")
        insert_mission(project_dir, "q-aaaa/m-0002", "q-aaaa", "IP Task", status="in_progress")
        insert_mission(project_dir, "q-aaaa/m-0003", "q-aaaa", "Blocked Task", status="blocked")
        insert_mission(
            project_dir, "q-aaaa/m-0004", "q-aaaa", "Closed Task",
            status="closed", closed_at="2025-01-15T10:00:00Z",
        )
        grouped = list_missions(project_dir)
        all_titles = [m["title"] for missions in grouped.values() for m in missions]
        assert "Open Task" in all_titles
        assert "IP Task" in all_titles
        assert "Blocked Task" in all_titles
        assert "Closed Task" not in all_titles


# ---------------------------------------------------------------------------
# Show mission — full detail
# ---------------------------------------------------------------------------


class TestShowMissionFull:
    """lore show q-xxxx/m-yyyy returns full detail with deps and board."""

    def test_json_has_expected_fields(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(
            main, ["--json", "new", "mission", "Task A", "-q", quest_id, "-d", "Desc A"]
        )
        m_id = json.loads(r1.output)["id"]

        result = runner.invoke(main, ["--json", "show", m_id])
        assert_exit_ok(result)
        data = json.loads(result.output)
        assert data["id"] == m_id
        assert data["title"] == "Task A"
        assert data["description"] == "Desc A"
        assert "status" in data
        assert "mission_type" in data
        assert "priority" in data
        assert "knight" in data
        assert "knight_contents" in data
        assert "block_reason" in data
        assert "dependencies" in data
        assert "needs" in data["dependencies"]
        assert "blocks" in data["dependencies"]
        assert "board" in data

    def test_dependencies_populated(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M One", "-q", quest_id])
        m1 = json.loads(r1.output)["id"]
        r2 = runner.invoke(main, ["--json", "new", "mission", "M Two", "-q", quest_id])
        m2 = json.loads(r2.output)["id"]
        runner.invoke(main, ["needs", f"{m2}:{m1}"])

        result = runner.invoke(main, ["--json", "show", m2])
        data = json.loads(result.output)
        needs_ids = [d["id"] for d in data["dependencies"]["needs"]]
        assert m1 in needs_ids

    def test_shows_title(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Login Bug")
        result = runner.invoke(main, ["show", "q-a1b2/m-f3c1"])
        assert result.exit_code == 0
        assert "Fix Login Bug" in result.output

    def test_shows_status(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Login Bug", status="in_progress")
        result = runner.invoke(main, ["show", "q-a1b2/m-f3c1"])
        assert result.exit_code == 0
        assert "in_progress" in result.output

    def test_shows_block_reason(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Login Bug",
            status="blocked", block_reason="Waiting for API key",
        )
        result = runner.invoke(main, ["show", "q-a1b2/m-f3c1"])
        assert result.exit_code == 0
        assert "Waiting for API key" in result.output

    def test_shows_timestamps(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Login Bug",
            created_at="2025-01-15T09:30:00Z",
            updated_at="2025-01-16T10:00:00Z",
        )
        result = runner.invoke(main, ["show", "q-a1b2/m-f3c1"])
        assert result.exit_code == 0
        assert "2025-01-15T09:30:00Z" in result.output
        assert "2025-01-16T10:00:00Z" in result.output

    def test_shows_dependencies(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Login Bug")
        insert_mission(project_dir, "q-a1b2/m-aaa1", "q-a1b2", "Setup DB")
        insert_dependency(project_dir, "q-a1b2/m-f3c1", "q-a1b2/m-aaa1")
        result = runner.invoke(main, ["show", "q-a1b2/m-f3c1"])
        assert result.exit_code == 0
        assert "m-aaa1" in result.output

    def test_shows_what_mission_blocks(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Login Bug")
        insert_mission(project_dir, "q-a1b2/m-bbb1", "q-a1b2", "Deploy")
        insert_dependency(project_dir, "q-a1b2/m-bbb1", "q-a1b2/m-f3c1")
        result = runner.invoke(main, ["show", "q-a1b2/m-f3c1"])
        assert result.exit_code == 0
        assert "m-bbb1" in result.output


# ---------------------------------------------------------------------------
# Show mission — null mission_type not shown in human output
# ---------------------------------------------------------------------------


class TestShowMissionNullType:
    """mission_type=NULL means 'Type:' is absent in human output."""

    def test_type_not_in_human_output(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "No Type M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]

        result = runner.invoke(main, ["show", m_id])
        assert_exit_ok(result)
        assert "Type:" not in result.output

    def test_mission_type_null_in_json(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "No Type M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]

        result = runner.invoke(main, ["--json", "show", m_id])
        data = json.loads(result.output)
        assert data["mission_type"] is None


# ---------------------------------------------------------------------------
# Show mission — knight file inline
# ---------------------------------------------------------------------------


class TestKnightContentsInline:
    """When knight file exists, show includes its contents inline."""

    def test_knight_contents_displayed(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Login Bug", knight="developer.md")
        _create_knight_file(project_dir, "developer.md", "# Developer Knight\nWrite clean code.")
        result = runner.invoke(main, ["show", "q-a1b2/m-f3c1"])
        assert result.exit_code == 0
        assert "# Developer Knight" in result.output
        assert "Write clean code." in result.output

    def test_no_knight_flag_omits_contents(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Login Bug", knight="developer.md")
        _create_knight_file(project_dir, "developer.md", "# Developer Knight\nWrite clean code.")
        result = runner.invoke(main, ["show", "q-a1b2/m-f3c1", "--no-knight"])
        assert result.exit_code == 0
        assert "Write clean code." not in result.output

    def test_no_knight_flag_still_shows_mission_details(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Login Bug", knight="developer.md")
        _create_knight_file(project_dir, "developer.md", "# Developer Knight\nWrite clean code.")
        result = runner.invoke(main, ["show", "q-a1b2/m-f3c1", "--no-knight"])
        assert result.exit_code == 0
        assert "Fix Login Bug" in result.output
        assert "developer.md" in result.output

    def test_missing_knight_file_shows_warning(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Login Bug", knight="foo.md")
        result = runner.invoke(main, ["show", "q-a1b2/m-f3c1"])
        assert result.exit_code == 0
        assert 'Warning: knight file "foo.md" not found in .lore/knights/' in result.output

    def test_no_knight_assigned_no_warning(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Login Bug")
        result = runner.invoke(main, ["show", "q-a1b2/m-f3c1"])
        assert result.exit_code == 0
        assert "Fix Login Bug" in result.output
        assert "not found in .lore/knights/" not in result.output


# ---------------------------------------------------------------------------
# Show mission — ID routing and not-found
# ---------------------------------------------------------------------------


class TestMissionIdRouting:
    """Mission ID (containing m-) routes to mission display."""

    def test_qualified_mission_id_routes_to_mission(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Login Bug")
        result = runner.invoke(main, ["show", "q-a1b2/m-f3c1"])
        assert result.exit_code == 0
        assert "Fix Login Bug" in result.output

    def test_standalone_mission_id_routes_to_mission(self, runner, project_dir):
        insert_mission(project_dir, "m-f3c1", None, "Standalone Task")
        result = runner.invoke(main, ["show", "m-f3c1"])
        assert result.exit_code == 0
        assert "Standalone Task" in result.output

    def test_quest_id_still_routes_to_quest(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        result = runner.invoke(main, ["show", "q-a1b2"])
        assert result.exit_code == 0
        assert "Test Quest" in result.output

    def test_not_found_exit_code(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        result = runner.invoke(main, ["show", "q-a1b2/m-9999"])
        assert result.exit_code == 1

    def test_not_found_message(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        result = runner.invoke(main, ["show", "q-a1b2/m-9999"])
        assert 'Mission "q-a1b2/m-9999" not found' in result.output

    def test_standalone_not_found(self, runner, project_dir):
        result = runner.invoke(main, ["show", "m-9999"])
        assert result.exit_code == 1
        assert 'Mission "m-9999" not found' in result.output

    def test_standalone_mission_no_quest_association(self, runner, project_dir):
        insert_mission(project_dir, "m-f3c1", None, "Standalone Task")
        result = runner.invoke(main, ["show", "m-f3c1"])
        assert result.exit_code == 0
        assert "Standalone Task" in result.output

    def test_standalone_with_knight(self, runner, project_dir):
        insert_mission(project_dir, "m-f3c1", None, "Standalone Task", knight="developer.md")
        _create_knight_file(project_dir, "developer.md", "Knight instructions here.")
        result = runner.invoke(main, ["show", "m-f3c1"])
        assert result.exit_code == 0
        assert "Knight instructions here." in result.output


# ---------------------------------------------------------------------------
# Edit mission — title, description, priority, knight
# ---------------------------------------------------------------------------


class TestEditMissionFields:
    """lore edit q-xxxx/m-yyyy with multiple flags updates fields."""

    def test_all_fields_updated(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "Old Title", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]

        result = runner.invoke(
            main,
            ["--json", "edit", m_id, "--title", "New Title",
             "--description", "New desc", "--priority", "0", "--knight", "reviewer.md"],
        )
        assert_exit_ok(result)
        data = json.loads(result.output)
        assert data["title"] == "New Title"
        assert data["description"] == "New desc"
        assert data["priority"] == 0
        assert data["knight"] == "reviewer.md"

    def test_updated_at_in_output(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "Old", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        result = runner.invoke(main, ["--json", "edit", m_id, "--title", "New"])
        data = json.loads(result.output)
        assert data["updated_at"] is not None

    def test_edit_title_short_flag(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Original Title")
        result = runner.invoke(main, ["edit", "q-a1b2/m-c3d4", "-t", "Short flag title"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT title FROM missions WHERE id = ?", ("q-a1b2/m-c3d4",)).fetchone()
        assert row["title"] == "Short flag title"

    def test_edit_description_short_flag(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Title")
        result = runner.invoke(main, ["edit", "q-a1b2/m-c3d4", "-d", "Short flag desc"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT description FROM missions WHERE id = ?", ("q-a1b2/m-c3d4",)).fetchone()
        assert row["description"] == "Short flag desc"

    def test_edit_priority_short_flag(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Title", priority=2)
        result = runner.invoke(main, ["edit", "q-a1b2/m-c3d4", "-p", "1"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT priority FROM missions WHERE id = ?", ("q-a1b2/m-c3d4",)).fetchone()
        assert row["priority"] == 1

    def test_edit_id_confirmed_in_output(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Original Title")
        result = runner.invoke(main, ["edit", "q-a1b2/m-c3d4", "--title", "Revised title"])
        assert result.exit_code == 0
        assert "q-a1b2/m-c3d4" in result.output


# ---------------------------------------------------------------------------
# Edit mission — knight assignment and removal
# ---------------------------------------------------------------------------


class TestEditMissionKnight:
    """Edit mission knight: set, reassign, remove."""

    def test_reassign_knight(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Title", knight="reviewer.md")
        result = runner.invoke(main, ["edit", "q-a1b2/m-c3d4", "--knight", "coder.md"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT knight FROM missions WHERE id = ?", ("q-a1b2/m-c3d4",)).fetchone()
        assert row["knight"] == "coder.md"

    def test_no_knight_clears_knight(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(
            main,
            ["--json", "new", "mission", "M", "-q", quest_id, "-k", "developer.md"],
        )
        m_id = json.loads(r1.output)["id"]
        result = runner.invoke(main, ["edit", m_id, "--no-knight"])
        assert_exit_ok(result)
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT knight FROM missions WHERE id = ?", (m_id,)).fetchone()
        assert row["knight"] is None

    def test_knight_and_no_knight_mutually_exclusive(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Title", knight="reviewer.md")
        result = runner.invoke(main, ["edit", "q-a1b2/m-c3d4", "--knight", "coder.md", "--no-knight"])
        assert result.exit_code == 2
        assert "mutually exclusive" in result.output.lower() or (
            "knight" in result.output.lower() and "no-knight" in result.output.lower()
        )


# ---------------------------------------------------------------------------
# Edit mission — set mission type
# ---------------------------------------------------------------------------


class TestEditMissionType:
    """lore edit q-xxxx/m-yyyy -T sets mission_type."""

    def test_mission_type_set(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        result = runner.invoke(main, ["--json", "edit", m_id, "-T", "constable"])
        assert_exit_ok(result)
        data = json.loads(result.output)
        assert data["mission_type"] == "constable"

    def test_db_mission_type_updated(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        runner.invoke(main, ["edit", m_id, "-T", "constable"])
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT mission_type FROM missions WHERE id = ?", (m_id,)).fetchone()
        assert row["mission_type"] == "constable"


# ---------------------------------------------------------------------------
# Edit mission — no flags required
# ---------------------------------------------------------------------------


class TestEditMissionRequiresFlag:
    """lore edit q-a1b2/m-c3d4 with no flags exits with code 2."""

    def test_no_flags_exits_code_2(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Title")
        result = runner.invoke(main, ["edit", "q-a1b2/m-c3d4"])
        assert result.exit_code == 2
        assert "at least one" in result.output.lower()
        assert "knight" in result.output.lower() or "-k" in result.output

    def test_no_flags_does_not_modify_mission(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(
            project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Title",
            updated_at="2025-01-15T09:30:00Z",
        )
        result = runner.invoke(main, ["edit", "q-a1b2/m-c3d4"])
        assert result.exit_code == 2
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT title, updated_at FROM missions WHERE id = ?", ("q-a1b2/m-c3d4",)
            ).fetchone()
        assert row["title"] == "Title"
        assert row["updated_at"] == "2025-01-15T09:30:00Z"
        # But providing a flag should work
        result2 = runner.invoke(main, ["edit", "q-a1b2/m-c3d4", "--title", "New Title"])
        assert result2.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT title FROM missions WHERE id = ?", ("q-a1b2/m-c3d4",)).fetchone()
        assert row["title"] == "New Title"


# ---------------------------------------------------------------------------
# Edit routes by ID format
# ---------------------------------------------------------------------------


class TestEditRoutesByIdFormat:
    """lore edit routes to quest or mission based on ID format."""

    def test_edit_quest_and_mission_both_work(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest Title")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Mission Title")
        result_q = runner.invoke(main, ["edit", "q-a1b2", "--title", "Updated Quest"])
        assert result_q.exit_code == 0
        result_m = runner.invoke(main, ["edit", "q-a1b2/m-c3d4", "--title", "Updated Mission"])
        assert result_m.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT title FROM missions WHERE id = ?", ("q-a1b2/m-c3d4",)).fetchone()
        assert row["title"] == "Updated Mission"


# ---------------------------------------------------------------------------
# Edit mission — non-existent and soft-deleted
# ---------------------------------------------------------------------------


class TestEditNonExistentMission:
    """lore edit on a non-existent mission exits with code 1."""

    def test_exit_code_1(self, runner, project_dir):
        result = runner.invoke(main, ["edit", "q-a1b2/m-c3d4", "--title", "Title"])
        assert result.exit_code == 1

    def test_shows_not_found(self, runner, project_dir):
        result = runner.invoke(main, ["edit", "q-a1b2/m-c3d4", "--title", "Title"])
        assert "not found" in result.output.lower()

    def test_json_error_output(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "edit", "q-a1b2/m-c3d4", "--title", "Title"])
        assert result.exit_code == 1
        assert '"error"' in result.output


class TestEditSoftDeletedMission:
    """lore edit on a soft-deleted mission exits with code 1."""

    def test_exit_code_1(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(
            project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Deleted Mission",
            deleted_at="2025-01-20T12:00:00Z",
        )
        result = runner.invoke(main, ["edit", "q-a1b2/m-c3d4", "--title", "New title"])
        assert result.exit_code == 1

    def test_shows_deletion_timestamp(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(
            project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Deleted Mission",
            deleted_at="2025-01-20T12:00:00Z",
        )
        result = runner.invoke(main, ["edit", "q-a1b2/m-c3d4", "--title", "New title"])
        assert "not found" in result.output.lower()
        assert "2025-01-20" in result.output
        assert "deleted" in result.output.lower()

    def test_json_error_includes_deleted_at(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(
            project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Deleted Mission",
            deleted_at="2025-01-20T12:00:00Z",
        )
        result = runner.invoke(main, ["--json", "edit", "q-a1b2/m-c3d4", "--title", "Title"])
        assert result.exit_code == 1
        assert '"error"' in result.output
        assert "2025-01-20" in result.output


# ---------------------------------------------------------------------------
# Edit mission — status flag not exposed
# ---------------------------------------------------------------------------


class TestEditMissionStatusNotEditable:
    """The edit command does not expose a --status flag for missions."""

    def test_no_status_flag_rejected(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Title", status="open")
        result = runner.invoke(main, ["edit", "q-a1b2/m-c3d4", "--status", "done"])
        assert result.exit_code == 2
        result2 = runner.invoke(main, ["edit", "q-a1b2/m-c3d4", "--title", "New"])
        assert result2.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-c3d4",)).fetchone()
        assert row["status"] == "open"


# ---------------------------------------------------------------------------
# Edit mission — priority validation
# ---------------------------------------------------------------------------


class TestEditMissionPriorityValidation:
    """Priority must be between 0 and 4."""

    def test_priority_5_rejected(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Title", priority=2)
        result = runner.invoke(main, ["edit", "q-a1b2/m-c3d4", "-p", "5"])
        assert result.exit_code == 1
        assert "priority" in result.output.lower()
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT priority FROM missions WHERE id = ?", ("q-a1b2/m-c3d4",)).fetchone()
        assert row["priority"] == 2

    def test_priority_negative_rejected(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Title", priority=2)
        result = runner.invoke(main, ["edit", "q-a1b2/m-c3d4", "-p", "-1"])
        assert result.exit_code == 1
        assert "priority" in result.output.lower()
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT priority FROM missions WHERE id = ?", ("q-a1b2/m-c3d4",)).fetchone()
        assert row["priority"] == 2

    def test_priority_0_accepted(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Title", priority=2)
        result = runner.invoke(main, ["edit", "q-a1b2/m-c3d4", "-p", "0"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT priority FROM missions WHERE id = ?", ("q-a1b2/m-c3d4",)).fetchone()
        assert row["priority"] == 0

    def test_priority_4_accepted(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Title", priority=2)
        result = runner.invoke(main, ["edit", "q-a1b2/m-c3d4", "-p", "4"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT priority FROM missions WHERE id = ?", ("q-a1b2/m-c3d4",)).fetchone()
        assert row["priority"] == 4


# ---------------------------------------------------------------------------
# Edit mission — updated_at refreshed
# ---------------------------------------------------------------------------


class TestEditMissionUpdatedTimestamp:
    """Editing a mission refreshes its updated_at timestamp."""

    def test_updated_at_refreshed(self, runner, project_dir):
        old_updated = "2025-01-15T09:30:00Z"
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(
            project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Title",
            updated_at=old_updated,
        )
        before = datetime.now(timezone.utc).replace(microsecond=0)
        result = runner.invoke(main, ["edit", "q-a1b2/m-c3d4", "--title", "New Title"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT updated_at FROM missions WHERE id = ?", ("q-a1b2/m-c3d4",)).fetchone()
        new_updated = datetime.strptime(row["updated_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        assert new_updated >= before
        assert row["updated_at"] != old_updated

    def test_status_unchanged_after_edit(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Title", status="in_progress")
        result = runner.invoke(main, ["edit", "q-a1b2/m-c3d4", "--title", "New Title"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-c3d4",)).fetchone()
        assert row["status"] == "in_progress"


# ---------------------------------------------------------------------------
# Edit mission — JSON output
# ---------------------------------------------------------------------------


class TestEditMissionJsonOutput:
    """lore edit --json returns full updated mission as JSON."""

    def test_json_output_structure(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(
            project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Title",
            knight="reviewer.md",
        )
        result = runner.invoke(main, ["--json", "edit", "q-a1b2/m-c3d4", "--title", "New Title"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "q-a1b2/m-c3d4"
        assert data["quest_id"] == "q-a1b2"
        assert data["title"] == "New Title"
        assert "description" in data
        assert "priority" in data
        assert "status" in data
        assert "knight" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert "closed_at" in data
        assert "block_reason" in data
        assert "dependencies" in data

    def test_json_output_reflects_changes(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(
            project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Old Title",
            knight="reviewer.md",
        )
        result = runner.invoke(
            main,
            ["--json", "edit", "q-a1b2/m-c3d4", "-t", "New Title",
             "-d", "New Desc", "-p", "1", "-k", "coder.md"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["title"] == "New Title"
        assert data["description"] == "New Desc"
        assert data["priority"] == 1
        assert data["knight"] == "coder.md"

    def test_json_dependencies_present(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Title")
        result = runner.invoke(main, ["--json", "edit", "q-a1b2/m-c3d4", "--title", "New"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "dependencies" in data
        assert "needs" in data["dependencies"]
        assert "blocks" in data["dependencies"]


# ---------------------------------------------------------------------------
# Edit mission — preserves unchanged fields
# ---------------------------------------------------------------------------


class TestEditMissionPreservesUnchangedFields:
    """Editing one field does not affect other fields."""

    def test_edit_title_preserves_other_fields(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(
            project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Title",
            knight="reviewer.md", priority=3,
        )
        result = runner.invoke(main, ["edit", "q-a1b2/m-c3d4", "--title", "New Title"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT * FROM missions WHERE id = ?", ("q-a1b2/m-c3d4",)).fetchone()
        assert row["title"] == "New Title"
        assert row["priority"] == 3
        assert row["knight"] == "reviewer.md"

    def test_edit_knight_preserves_title_and_description(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(
            project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Keep Title",
            knight="reviewer.md",
        )
        result = runner.invoke(main, ["edit", "q-a1b2/m-c3d4", "-k", "coder.md"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT * FROM missions WHERE id = ?", ("q-a1b2/m-c3d4",)).fetchone()
        assert row["title"] == "Keep Title"
        assert row["knight"] == "coder.md"


# ---------------------------------------------------------------------------
# Soft-delete a mission
# ---------------------------------------------------------------------------


class TestSoftDeleteMission:
    """lore delete q-a1b2/m-c3d4 soft-deletes the mission."""

    def test_exit_code_zero(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Mission")
        result = runner.invoke(main, ["delete", "q-a1b2/m-c3d4"])
        assert result.exit_code == 0

    def test_sets_deleted_at(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Mission")
        runner.invoke(main, ["delete", "q-a1b2/m-c3d4"])
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT deleted_at FROM missions WHERE id = ?", ("q-a1b2/m-c3d4",)).fetchone()
        assert row["deleted_at"] is not None

    def test_deleted_mission_hidden_from_listing(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Mission")
        runner.invoke(main, ["delete", "q-a1b2/m-c3d4"])
        result = runner.invoke(main, ["missions", "--all"])
        assert "q-a1b2/m-c3d4" not in result.output

    def test_deleted_mission_not_counted_in_dashboard(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-0001", "q-a1b2", "Mission B")
        delete_result = runner.invoke(main, ["delete", "q-a1b2/m-c3d4"])
        assert delete_result.exit_code == 0
        result = runner.invoke(main, [])
        assert "open:1" in result.output
        assert "open:2" not in result.output

    def test_delete_output_confirms_deletion(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Mission")
        result = runner.invoke(main, ["delete", "q-a1b2/m-c3d4"])
        assert "q-a1b2/m-c3d4" in result.output
        assert "deleted" in result.output.lower()


# ---------------------------------------------------------------------------
# Mission delete cascades dependencies
# ---------------------------------------------------------------------------


class TestDependencyCleanupOnMissionDelete:
    """Deleting a mission soft-deletes all dependency links involving it."""

    def test_dependency_rows_cascaded(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M One", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M Two", "-q", quest_id])
        r3 = runner.invoke(main, ["--json", "new", "mission", "M Three", "-q", quest_id])
        m1 = json.loads(r1.output)["id"]
        m2 = json.loads(r2.output)["id"]
        m3 = json.loads(r3.output)["id"]
        runner.invoke(main, ["needs", f"{m2}:{m1}"])
        runner.invoke(main, ["needs", f"{m3}:{m2}"])

        runner.invoke(main, ["delete", m2])
        with db_conn(project_dir) as conn:
            rows = conn.execute(
                "SELECT deleted_at FROM dependencies WHERE from_id = ? OR to_id = ?",
                (m2, m2),
            ).fetchall()
        assert len(rows) == 2
        assert all(r["deleted_at"] is not None for r in rows)

    def test_incoming_dependencies_soft_deleted(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-0001", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-0002", "q-a1b2", "Mission B")
        insert_dependency(project_dir, "q-a1b2/m-0002", "q-a1b2/m-0001")
        runner.invoke(main, ["delete", "q-a1b2/m-0001"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT deleted_at FROM dependencies WHERE from_id = ? AND to_id = ?",
                ("q-a1b2/m-0002", "q-a1b2/m-0001"),
            ).fetchone()
        assert row["deleted_at"] is not None

    def test_cross_quest_dependencies_soft_deleted(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest A")
        insert_quest(project_dir, "q-c3d4", "Quest B")
        insert_mission(project_dir, "q-a1b2/m-0001", "q-a1b2", "Mission A1")
        insert_mission(project_dir, "q-c3d4/m-0001", "q-c3d4", "Mission B1")
        insert_dependency(project_dir, "q-c3d4/m-0001", "q-a1b2/m-0001")
        runner.invoke(main, ["delete", "q-a1b2/m-0001"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT deleted_at FROM dependencies WHERE from_id = ? AND to_id = ?",
                ("q-c3d4/m-0001", "q-a1b2/m-0001"),
            ).fetchone()
        assert row["deleted_at"] is not None


# ---------------------------------------------------------------------------
# Parent quest status re-derives on mission delete
# ---------------------------------------------------------------------------


class TestParentQuestStatusReDerives:
    """Deleting a mission re-derives the parent quest status."""

    def test_quest_becomes_closed_when_open_mission_deleted(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest", status="in_progress", auto_close=1)
        insert_mission(
            project_dir, "q-a1b2/m-0001", "q-a1b2", "Done Mission",
            status="closed", closed_at="2025-01-15T10:00:00Z",
        )
        insert_mission(project_dir, "q-a1b2/m-0002", "q-a1b2", "Open Mission", status="open")
        runner.invoke(main, ["delete", "q-a1b2/m-0002"])
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT status FROM quests WHERE id = ?", ("q-a1b2",)).fetchone()
        assert row["status"] == "closed"

    def test_quest_becomes_open_when_all_missions_deleted(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest", status="in_progress")
        insert_mission(project_dir, "q-a1b2/m-0001", "q-a1b2", "Mission A", status="open")
        insert_mission(project_dir, "q-a1b2/m-0002", "q-a1b2", "Mission B", status="open")
        runner.invoke(main, ["delete", "q-a1b2/m-0001"])
        runner.invoke(main, ["delete", "q-a1b2/m-0002"])
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT status FROM quests WHERE id = ?", ("q-a1b2",)).fetchone()
        assert row["status"] == "open"


# ---------------------------------------------------------------------------
# Delete non-existent and already-deleted missions
# ---------------------------------------------------------------------------


class TestDeleteNonExistentMission:
    """lore delete on a non-existent mission exits with code 1."""

    def test_exit_code_1(self, runner, project_dir):
        result = runner.invoke(main, ["delete", "q-a1b2/m-dead"])
        assert result.exit_code == 1

    def test_shows_not_found(self, runner, project_dir):
        result = runner.invoke(main, ["delete", "q-a1b2/m-dead"])
        assert "not found" in result.output.lower()


class TestDeleteAlreadyDeletedMission:
    """Re-deleting a soft-deleted mission succeeds with a warning."""

    def test_redelete_exits_code_0(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(
            project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Deleted Mission",
            deleted_at="2025-01-20T12:00:00Z",
        )
        result = runner.invoke(main, ["delete", "q-a1b2/m-c3d4"])
        assert result.exit_code == 0

    def test_redelete_shows_warning(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(
            project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Deleted Mission",
            deleted_at="2025-01-20T12:00:00Z",
        )
        result = runner.invoke(main, ["delete", "q-a1b2/m-c3d4"])
        assert "already" in result.output.lower() or "warning" in result.output.lower()


# ---------------------------------------------------------------------------
# Show a deleted mission reports not found
# ---------------------------------------------------------------------------


class TestShowDeletedMission:
    """lore show on a deleted mission reports not found with deletion timestamp."""

    def test_reports_not_found(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Mission")
        runner.invoke(main, ["delete", "q-a1b2/m-c3d4"])
        result = runner.invoke(main, ["show", "q-a1b2/m-c3d4"])
        assert "not found" in result.output.lower()

    def test_includes_deletion_timestamp(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Mission")
        runner.invoke(main, ["delete", "q-a1b2/m-c3d4"])
        result = runner.invoke(main, ["show", "q-a1b2/m-c3d4"])
        assert "deleted" in result.output.lower()


# ---------------------------------------------------------------------------
# Deleted mission does not block others
# ---------------------------------------------------------------------------


class TestDeletedMissionDoesNotBlockOthers:
    """After deleting mission A, mission B (which depended on A) is unblocked."""

    def test_deleted_blocker_unblocks_dependent_in_ready_queue(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-0001", "q-a1b2", "Blocker", status="open")
        insert_mission(project_dir, "q-a1b2/m-0002", "q-a1b2", "Blocked", status="open")
        insert_dependency(project_dir, "q-a1b2/m-0002", "q-a1b2/m-0001")
        runner.invoke(main, ["delete", "q-a1b2/m-0001"])
        result = runner.invoke(main, ["ready"])
        assert "q-a1b2/m-0002" in result.output

    def test_parent_quest_show_excludes_deleted_mission(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-0001", "q-a1b2", "Active Mission")
        insert_mission(project_dir, "q-a1b2/m-0002", "q-a1b2", "To Delete")
        runner.invoke(main, ["delete", "q-a1b2/m-0002"])
        result = runner.invoke(main, ["show", "q-a1b2"])
        assert "m-0001" in result.output
        assert "m-0002" not in result.output


# ---------------------------------------------------------------------------
# JSON output for mission delete
# ---------------------------------------------------------------------------


class TestJsonOutputMissionDelete:
    """lore --json delete <mission-id> returns {id, deleted_at}."""

    def test_json_delete_structure(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Mission")
        result = runner.invoke(main, ["--json", "delete", "q-a1b2/m-c3d4"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "q-a1b2/m-c3d4"
        assert "deleted_at" in data

    def test_json_delete_nonexistent_error(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "delete", "q-a1b2/m-dead"])
        assert result.exit_code == 1
        assert '"error"' in result.output

    def test_json_delete_no_cascade_key(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest")
        insert_mission(project_dir, "q-a1b2/m-c3d4", "q-a1b2", "Mission")
        result = runner.invoke(main, ["--json", "delete", "q-a1b2/m-c3d4"])
        data = json.loads(result.output)
        assert "cascade" not in data


# ---------------------------------------------------------------------------
# Soft-delete visibility: cross-cutting filtering
# ---------------------------------------------------------------------------


class TestSoftDeleteVisibility:
    """Soft-deleted entities are excluded from all normal views."""

    def test_deleted_mission_excluded_from_all_listing(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_mission(project_dir, "q-aaaa/m-aa01", "q-aaaa", "Active Mission", status="closed",
                       closed_at="2025-01-15T10:00:00Z")
        insert_mission(
            project_dir, "q-aaaa/m-aa02", "q-aaaa", "Deleted Mission",
            deleted_at="2025-01-20T12:00:00Z",
        )
        result = runner.invoke(main, ["missions", "--all"])
        assert result.exit_code == 0
        assert "Active Mission" in result.output
        assert "Deleted Mission" not in result.output

    def test_deleted_quest_excluded_from_list(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Active Quest", status="open")
        insert_quest(
            project_dir, "q-bbbb", "Deleted Quest", status="open",
            deleted_at="2025-01-20T12:00:00Z",
        )
        result = runner.invoke(main, ["list"])
        assert result.exit_code == 0
        assert "Active Quest" in result.output
        assert "Deleted Quest" not in result.output

    def test_deleted_mission_not_in_ready_queue(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_mission(
            project_dir, "q-aaaa/m-aa01", "q-aaaa", "Deleted Mission",
            priority=0, deleted_at="2025-01-20T12:00:00Z",
        )
        insert_mission(project_dir, "q-aaaa/m-aa02", "q-aaaa", "Active Mission", priority=4)
        result = runner.invoke(main, ["ready"])
        assert result.exit_code == 0
        assert "Active Mission" in result.output
        assert "Deleted Mission" not in result.output

    def test_soft_deleted_dependency_does_not_block(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_mission(project_dir, "q-aaaa/m-aa01", "q-aaaa", "Mission A", status="open")
        insert_mission(project_dir, "q-aaaa/m-aa02", "q-aaaa", "Mission B", status="open", priority=0)
        insert_dependency(
            project_dir, "q-aaaa/m-aa02", "q-aaaa/m-aa01",
            deleted_at="2025-01-20T12:00:00Z",
        )
        result = runner.invoke(main, ["ready"])
        assert result.exit_code == 0
        assert "q-aaaa/m-aa02" in result.output

    def test_show_deleted_mission_error(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_mission(
            project_dir, "q-aaaa/m-aa01", "q-aaaa", "Deleted Mission",
            deleted_at="2025-01-20T12:00:00Z",
        )
        result = runner.invoke(main, ["show", "q-aaaa/m-aa01"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()
        assert "2025-01-20" in result.output
        assert "deleted" in result.output.lower()

    def test_show_deleted_mission_json_error(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_mission(
            project_dir, "q-aaaa/m-aa01", "q-aaaa", "Deleted Mission",
            deleted_at="2025-01-20T12:00:00Z",
        )
        result = runner.invoke(main, ["show", "q-aaaa/m-aa01", "--json"])
        assert result.exit_code == 1
        assert "deleted_at" in result.output
        assert "2025-01-20" in result.output

    def test_cycle_detection_ignores_deleted_dependencies(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_mission(project_dir, "q-aaaa/m-aa01", "q-aaaa", "Mission A")
        insert_mission(project_dir, "q-aaaa/m-aa02", "q-aaaa", "Mission B")
        insert_dependency(
            project_dir, "q-aaaa/m-aa01", "q-aaaa/m-aa02",
            deleted_at="2025-01-20T12:00:00Z",
        )
        result = runner.invoke(main, ["needs", "q-aaaa/m-aa02:q-aaaa/m-aa01"])
        assert result.exit_code == 0
        assert "cycle" not in result.output.lower()


# ---------------------------------------------------------------------------
# Mission listing: no dependency count tokens
# ---------------------------------------------------------------------------


EXPECTED_MISSION_LISTING_FIELDS = {
    "id",
    "quest_id",
    "title",
    "status",
    "priority",
    "mission_type",
    "knight",
    "created_at",
}


class TestNoDepTokensInMissionListing:
    """lore missions output contains no needs:/blocks: tokens."""

    def test_no_needs_token_anywhere(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_mission(project_dir, "q-aaaa/m-aa01", "q-aaaa", "Alpha")
        insert_mission(project_dir, "q-aaaa/m-aa02", "q-aaaa", "Beta")
        insert_mission(project_dir, "q-aaaa/m-aa03", "q-aaaa", "Gamma")
        insert_dependency(project_dir, "q-aaaa/m-aa02", "q-aaaa/m-aa01")
        insert_dependency(project_dir, "q-aaaa/m-aa03", "q-aaaa/m-aa02")
        result = runner.invoke(main, ["missions"])
        assert result.exit_code == 0
        assert "needs:" not in result.output

    def test_no_blocks_token_anywhere(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_mission(project_dir, "q-aaaa/m-aa01", "q-aaaa", "Root")
        insert_mission(project_dir, "q-aaaa/m-aa02", "q-aaaa", "Middle")
        insert_mission(project_dir, "q-aaaa/m-aa03", "q-aaaa", "Leaf")
        insert_dependency(project_dir, "q-aaaa/m-aa02", "q-aaaa/m-aa01")
        insert_dependency(project_dir, "q-aaaa/m-aa03", "q-aaaa/m-aa02")
        result = runner.invoke(main, ["missions"])
        assert result.exit_code == 0
        assert "blocks:" not in result.output

    def test_json_no_dependencies_key_for_any_mission(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_mission(project_dir, "q-aaaa/m-aa01", "q-aaaa", "A")
        insert_mission(project_dir, "q-aaaa/m-aa02", "q-aaaa", "B")
        insert_mission(project_dir, "q-aaaa/m-aa03", "q-aaaa", "C")
        insert_dependency(project_dir, "q-aaaa/m-aa02", "q-aaaa/m-aa01")
        insert_dependency(project_dir, "q-aaaa/m-aa03", "q-aaaa/m-aa02")
        result = runner.invoke(main, ["--json", "missions"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        for m in data["missions"]:
            assert "dependencies" not in m
            assert "needs" not in m

    def test_json_mission_objects_have_expected_fields(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Quest A")
        insert_mission(project_dir, "q-aaaa/m-aa01", "q-aaaa", "No Deps")
        insert_mission(project_dir, "q-aaaa/m-aa02", "q-aaaa", "Has Dep")
        insert_mission(project_dir, "q-aaaa/m-aa03", "q-aaaa", "Is Blocked By")
        insert_dependency(project_dir, "q-aaaa/m-aa02", "q-aaaa/m-aa03")
        result = runner.invoke(main, ["--json", "missions"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        for m in data["missions"]:
            actual_keys = set(m.keys())
            assert actual_keys == EXPECTED_MISSION_LISTING_FIELDS, (
                f"Mission {m['id']}: unexpected keys {actual_keys - EXPECTED_MISSION_LISTING_FIELDS}, "
                f"missing keys {EXPECTED_MISSION_LISTING_FIELDS - actual_keys}"
            )
