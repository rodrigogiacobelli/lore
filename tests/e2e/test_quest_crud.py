"""E2E tests for quest CRUD operations.

Spec: conceptual-workflows-quest-crud (lore codex show conceptual-workflows-quest-crud)
"""

import json
import re
import sqlite3
from datetime import datetime, timezone

from lore.cli import main
from tests.conftest import (
    assert_exit_ok,
    assert_exit_err,
    db_conn,
    insert_dependency,
    insert_mission,
    insert_quest,
)


# ---------------------------------------------------------------------------
# Create quest — title only
# ---------------------------------------------------------------------------


class TestCreateQuestTitleOnly:
    """lore new quest creates a quest with defaults."""

    def test_exit_code_zero(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "new", "quest", "Build Login Feature"])
        assert_exit_ok(result)

    def test_json_id_starts_with_q(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "new", "quest", "Build Login Feature"])
        data = json.loads(result.output)
        assert data["id"].startswith("q-")

    def test_id_format_matches_pattern(self, runner, project_dir):
        result = runner.invoke(main, ["new", "quest", "Redesign checkout flow"])
        assert result.exit_code == 0
        assert re.search(r"q-[a-f0-9]{4,6}", result.output)

    def test_db_title_stored(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "new", "quest", "Build Login Feature"])
        quest_id = json.loads(result.output)["id"]
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT title, status, priority, auto_close, description, deleted_at, closed_at "
                "FROM quests WHERE id = ?",
                (quest_id,),
            ).fetchone()
        assert row["title"] == "Build Login Feature"
        assert row["status"] == "open"
        assert row["priority"] == 2
        assert row["auto_close"] == 0
        assert row["description"] == ""
        assert row["deleted_at"] is None
        assert row["closed_at"] is None

    def test_timestamps_are_iso8601_utc(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "new", "quest", "Build Login Feature"])
        quest_id = json.loads(result.output)["id"]
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT created_at, updated_at FROM quests WHERE id = ?", (quest_id,)
            ).fetchone()
        assert row["created_at"].endswith("Z")
        assert row["updated_at"].endswith("Z")

    def test_created_at_in_range(self, runner, project_dir):
        before = datetime.now(timezone.utc).replace(microsecond=0)
        result = runner.invoke(main, ["new", "quest", "Timestamp test"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT created_at FROM quests"
            ).fetchone()
        created_at = datetime.strptime(row["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        after = datetime.now(timezone.utc).replace(microsecond=0)
        assert before <= created_at <= after

    def test_description_defaults_to_empty_string(self, runner, project_dir):
        runner.invoke(main, ["new", "quest", "No description"])
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT description FROM quests").fetchone()
        assert row["description"] == ""
        assert row["description"] is not None


# ---------------------------------------------------------------------------
# Create quest — all flags
# ---------------------------------------------------------------------------


class TestCreateQuestAllFlags:
    """lore new quest with -d, -p, --auto-close stores all fields."""

    def test_all_flags_stored(self, runner, project_dir):
        result = runner.invoke(
            main,
            [
                "--json",
                "new",
                "quest",
                "Feature X",
                "-d",
                "Full redesign of checkout.",
                "-p",
                "0",
                "--auto-close",
            ],
        )
        assert_exit_ok(result)
        quest_id = json.loads(result.output)["id"]
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT description, priority, auto_close FROM quests WHERE id = ?",
                (quest_id,),
            ).fetchone()
        assert row["description"] == "Full redesign of checkout."
        assert row["priority"] == 0
        assert row["auto_close"] == 1

    def test_priority_boundary_0_accepted(self, runner, project_dir):
        result = runner.invoke(main, ["new", "quest", "P0 quest", "-p", "0"])
        assert result.exit_code == 0

    def test_priority_boundary_4_accepted(self, runner, project_dir):
        result = runner.invoke(main, ["new", "quest", "P4 quest", "-p", "4"])
        assert result.exit_code == 0

    def test_unique_ids_for_multiple_quests(self, runner, project_dir):
        results = [runner.invoke(main, ["--json", "new", "quest", f"Quest {i}"]) for i in range(10)]
        ids = {json.loads(r.output)["id"] for r in results}
        assert len(ids) == 10

    def test_duplicate_title_allowed(self, runner, project_dir):
        r1 = runner.invoke(main, ["--json", "new", "quest", "Same Title"])
        r2 = runner.invoke(main, ["--json", "new", "quest", "Same Title"])
        assert_exit_ok(r1)
        assert_exit_ok(r2)
        id1 = json.loads(r1.output)["id"]
        id2 = json.loads(r2.output)["id"]
        assert id1 != id2

    def test_both_duplicate_quests_in_list(self, runner, project_dir):
        runner.invoke(main, ["new", "quest", "Same Title"])
        runner.invoke(main, ["new", "quest", "Same Title"])
        result = runner.invoke(main, ["--json", "list"])
        data = json.loads(result.output)
        titles = [q["title"] for q in data["quests"]]
        assert titles.count("Same Title") == 2


# ---------------------------------------------------------------------------
# Create quest — priority out of range
# ---------------------------------------------------------------------------


class TestCreateQuestPriorityOutOfRange:
    """lore new quest with -p 5 errors."""

    def test_exit_code_nonzero(self, runner, project_dir):
        result = runner.invoke(main, ["new", "quest", "Bad Quest", "-p", "5"])
        assert result.exit_code != 0

    def test_error_mentions_priority(self, runner, project_dir):
        result = runner.invoke(main, ["new", "quest", "Bad Quest", "-p", "5"])
        assert "priority" in result.output.lower() or "0" in result.output

    def test_no_quest_row_created(self, runner, project_dir):
        runner.invoke(main, ["new", "quest", "Bad Quest", "-p", "5"])
        with db_conn(project_dir) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM quests WHERE title = 'Bad Quest'"
            ).fetchone()[0]
        assert count == 0

    def test_negative_priority_rejected(self, runner, project_dir):
        result = runner.invoke(main, ["new", "quest", "Bad priority", "-p", "-1"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# List quests — default (open only)
# ---------------------------------------------------------------------------


class TestListQuestsOpenOnly:
    """lore list returns only open quests by default."""

    def test_only_open_returned(self, runner, project_dir):
        insert_quest(project_dir, "q-aaa1", "Open Quest A")
        insert_quest(project_dir, "q-bbb2", "Open Quest B")
        insert_quest(project_dir, "q-ccc3", "Closed Quest", status="closed", closed_at="2025-01-20T00:00:00Z")
        result = runner.invoke(main, ["--json", "list"])
        assert_exit_ok(result)
        data = json.loads(result.output)
        ids = [q["id"] for q in data["quests"]]
        assert "q-aaa1" in ids
        assert "q-bbb2" in ids
        assert "q-ccc3" not in ids

    def test_exactly_two_open_quests(self, runner, project_dir):
        insert_quest(project_dir, "q-aaa1", "Open Quest A")
        insert_quest(project_dir, "q-bbb2", "Open Quest B")
        insert_quest(project_dir, "q-ccc3", "Closed Quest", status="closed", closed_at="2025-01-20T00:00:00Z")
        result = runner.invoke(main, ["--json", "list"])
        data = json.loads(result.output)
        assert len(data["quests"]) == 2

    def test_in_progress_quests_shown(self, runner, project_dir):
        insert_quest(project_dir, "q-bbbb", "In Progress Quest", status="in_progress")
        result = runner.invoke(main, ["list"])
        assert result.exit_code == 0
        assert "In Progress Quest" in result.output

    def test_sorted_by_priority_then_created_at(self, runner, project_dir):
        with db_conn(project_dir) as conn:
            conn.execute(
                "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-bbbb', 'P1 Quest', '', 'open', 1, '2025-01-16T09:00:00Z', '2025-01-16T09:00:00Z')"
            )
            conn.execute(
                "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-aaaa', 'P0 Quest', '', 'open', 0, '2025-01-15T09:00:00Z', '2025-01-15T09:00:00Z')"
            )
        result = runner.invoke(main, ["list"])
        p0_pos = result.output.index("P0 Quest")
        p1_pos = result.output.index("P1 Quest")
        assert p0_pos < p1_pos

    def test_no_quests_message_when_empty(self, runner, project_dir):
        result = runner.invoke(main, ["list"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# List quests — --all includes closed
# ---------------------------------------------------------------------------


class TestListQuestsAll:
    """lore list --all includes closed quests."""

    def test_both_quests_present(self, runner, project_dir):
        insert_quest(project_dir, "q-aaa1", "Open Quest")
        insert_quest(project_dir, "q-bbb2", "Closed Quest", status="closed", closed_at="2025-01-20T00:00:00Z")
        result = runner.invoke(main, ["--json", "list", "--all"])
        assert_exit_ok(result)
        data = json.loads(result.output)
        ids = [q["id"] for q in data["quests"]]
        assert "q-aaa1" in ids
        assert "q-bbb2" in ids


# ---------------------------------------------------------------------------
# List quests — soft-deleted excluded even with --all
# ---------------------------------------------------------------------------


class TestListQuestsSoftDeletedExcluded:
    """Soft-deleted quests do not appear even with --all."""

    def test_soft_deleted_excluded(self, runner, project_dir):
        insert_quest(project_dir, "q-aaa1", "Active Quest")
        insert_quest(
            project_dir,
            "q-bbb2",
            "Deleted Quest",
            deleted_at="2025-01-18T00:00:00Z",
        )
        result = runner.invoke(main, ["--json", "list", "--all"])
        assert_exit_ok(result)
        data = json.loads(result.output)
        ids = [q["id"] for q in data["quests"]]
        assert "q-aaa1" in ids
        assert "q-bbb2" not in ids


# ---------------------------------------------------------------------------
# Show quest — detail view
# ---------------------------------------------------------------------------


class TestShowQuest:
    """lore show q-xxxx returns quest detail."""

    def test_json_has_expected_fields(self, runner, project_dir):
        insert_quest(project_dir, "q-aaa1", "My Quest", description="Desc here")
        insert_mission(project_dir, "q-aaa1/m-m001", "q-aaa1", "Mission One")
        insert_mission(project_dir, "q-aaa1/m-m002", "q-aaa1", "Mission Two")
        insert_dependency(project_dir, "q-aaa1/m-m002", "q-aaa1/m-m001")
        result = runner.invoke(main, ["--json", "show", "q-aaa1"])
        assert_exit_ok(result)
        data = json.loads(result.output)
        assert data["id"] == "q-aaa1"
        assert data["title"] == "My Quest"
        assert "description" in data
        assert "status" in data
        assert "priority" in data
        assert "auto_close" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert "closed_at" in data
        assert "missions" in data
        assert len(data["missions"]) == 2

    def test_auto_close_is_bool(self, runner, project_dir):
        insert_quest(project_dir, "q-aaa1", "My Quest")
        result = runner.invoke(main, ["--json", "show", "q-aaa1"])
        data = json.loads(result.output)
        assert isinstance(data["auto_close"], bool)

    def test_human_output_contains_missions(self, runner, project_dir):
        insert_quest(project_dir, "q-aaa1", "My Quest")
        insert_mission(project_dir, "q-aaa1/m-m001", "q-aaa1", "Task Alpha")
        result = runner.invoke(main, ["show", "q-aaa1"])
        assert_exit_ok(result)
        assert "Task Alpha" in result.output

    def test_show_title_and_description(self, runner, project_dir):
        with db_conn(project_dir) as conn:
            conn.execute(
                "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-aaaa', 'My Quest', 'Quest desc', 'open', 1, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')"
            )
        result = runner.invoke(main, ["show", "q-aaaa"])
        assert result.exit_code == 0
        assert "My Quest" in result.output
        assert "Quest desc" in result.output

    def test_show_not_found(self, runner, project_dir):
        result = runner.invoke(main, ["show", "q-abcd"])
        assert result.exit_code == 1
        assert 'Quest "q-abcd" not found' in result.output


# ---------------------------------------------------------------------------
# Edit quest — change title and priority
# ---------------------------------------------------------------------------


class TestEditQuestTitlePriority:
    """lore edit q-xxxx --title --priority updates the quest."""

    def test_title_and_priority_updated(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Original Title"])
        quest_id = json.loads(r.output)["id"]
        result = runner.invoke(
            main,
            ["--json", "edit", quest_id, "--title", "New Title", "--priority", "1"],
        )
        assert_exit_ok(result)
        data = json.loads(result.output)
        assert data["title"] == "New Title"
        assert data["priority"] == 1

    def test_status_unchanged_after_edit(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Original Title"])
        quest_id = json.loads(r.output)["id"]
        runner.invoke(main, ["edit", quest_id, "--title", "New Title"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status, description FROM quests WHERE id = ?", (quest_id,)
            ).fetchone()
        assert row["status"] == "open"

    def test_updated_at_is_not_none(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Original"])
        quest_id = json.loads(r.output)["id"]
        runner.invoke(main, ["edit", quest_id, "--title", "Updated"])
        result = runner.invoke(main, ["--json", "show", quest_id])
        updated = json.loads(result.output)
        assert updated["updated_at"] is not None

    def test_edit_title_short_flag(self, runner, project_dir):
        with db_conn(project_dir) as conn:
            conn.execute(
                "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-a1b2', 'Original Title', '', 'open', 2, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')"
            )
        result = runner.invoke(main, ["edit", "q-a1b2", "-t", "Short flag title"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT title FROM quests WHERE id = ?", ("q-a1b2",)).fetchone()
        assert row["title"] == "Short flag title"

    def test_edit_title_confirmed_in_output(self, runner, project_dir):
        with db_conn(project_dir) as conn:
            conn.execute(
                "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-a1b2', 'Original Title', '', 'open', 2, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')"
            )
        result = runner.invoke(main, ["edit", "q-a1b2", "--title", "Revised title"])
        assert result.exit_code == 0
        assert "q-a1b2" in result.output

    def test_edit_description(self, runner, project_dir):
        with db_conn(project_dir) as conn:
            conn.execute(
                "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-a1b2', 'Title', 'Old desc', 'open', 2, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')"
            )
        result = runner.invoke(main, ["edit", "q-a1b2", "--description", "New description"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT description FROM quests WHERE id = ?", ("q-a1b2",)).fetchone()
        assert row["description"] == "New description"

    def test_edit_preserves_unchanged_fields(self, runner, project_dir):
        with db_conn(project_dir) as conn:
            conn.execute(
                "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-a1b2', 'Title', 'Keep me', 'open', 3, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')"
            )
        result = runner.invoke(main, ["edit", "q-a1b2", "--title", "New Title"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT title, description, priority FROM quests WHERE id = ?", ("q-a1b2",)).fetchone()
        assert row["title"] == "New Title"
        assert row["description"] == "Keep me"
        assert row["priority"] == 3

    def test_edit_updates_updated_at_timestamp(self, runner, project_dir):
        old_updated = "2025-01-15T09:30:00Z"
        with db_conn(project_dir) as conn:
            conn.execute(
                "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-a1b2', 'Title', '', 'open', 2, ?, ?)",
                (old_updated, old_updated),
            )
        before = datetime.now(timezone.utc).replace(microsecond=0)
        result = runner.invoke(main, ["edit", "q-a1b2", "--title", "New Title"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT updated_at FROM quests WHERE id = ?", ("q-a1b2",)).fetchone()
        new_updated = datetime.strptime(row["updated_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        assert new_updated >= before
        assert row["updated_at"] != old_updated

    def test_edit_json_output_structure(self, runner, project_dir):
        with db_conn(project_dir) as conn:
            conn.execute(
                "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-a1b2', 'Title', 'Desc', 'open', 2, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')"
            )
        result = runner.invoke(main, ["--json", "edit", "q-a1b2", "--title", "New Title"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "q-a1b2"
        assert data["title"] == "New Title"
        assert "description" in data
        assert "priority" in data
        assert "status" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert "closed_at" in data
        assert "missions" in data

    def test_edit_priority_out_of_range(self, runner, project_dir):
        with db_conn(project_dir) as conn:
            conn.execute(
                "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-a1b2', 'Title', '', 'open', 2, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')"
            )
        result = runner.invoke(main, ["edit", "q-a1b2", "-p", "5"])
        assert result.exit_code != 0
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT priority FROM quests WHERE id = ?", ("q-a1b2",)).fetchone()
        assert row["priority"] == 2


# ---------------------------------------------------------------------------
# Edit quest — no flags provided
# ---------------------------------------------------------------------------


class TestEditQuestNoFlags:
    """lore edit q-xxxx with no flags is a usage error."""

    def test_exit_code_2(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Some Quest"])
        quest_id = json.loads(r.output)["id"]
        result = runner.invoke(main, ["edit", quest_id])
        assert_exit_err(result, code=2)

    def test_error_message_mentions_required(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Some Quest"])
        quest_id = json.loads(r.output)["id"]
        result = runner.invoke(main, ["edit", quest_id])
        assert "required" in result.output.lower() or "required" in (result.output + (result.stderr or "")).lower()

    def test_no_status_flag_available(self, runner, project_dir):
        with db_conn(project_dir) as conn:
            conn.execute(
                "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-a1b2', 'Title', '', 'open', 2, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')"
            )
        result = runner.invoke(main, ["edit", "q-a1b2", "--status", "closed"])
        assert result.exit_code == 2


# ---------------------------------------------------------------------------
# Edit quest — enable and disable auto-close
# ---------------------------------------------------------------------------


class TestEditQuestAutoClose:
    """--auto-close and --no-auto-close toggle the flag."""

    def test_enable_auto_close(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "AC Quest"])
        quest_id = json.loads(r.output)["id"]
        result = runner.invoke(main, ["edit", quest_id, "--auto-close"])
        assert_exit_ok(result)
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT auto_close FROM quests WHERE id = ?", (quest_id,)
            ).fetchone()
        assert row["auto_close"] == 1

    def test_disable_auto_close(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "AC Quest", "--auto-close"])
        quest_id = json.loads(r.output)["id"]
        result = runner.invoke(main, ["edit", quest_id, "--no-auto-close"])
        assert_exit_ok(result)
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT auto_close FROM quests WHERE id = ?", (quest_id,)
            ).fetchone()
        assert row["auto_close"] == 0

    def test_no_auto_close_visible_in_help(self, runner, project_dir):
        result = runner.invoke(main, ["edit", "--help"])
        assert "--no-auto-close" in result.output

    def test_edit_nonexistent_quest_exits_1(self, runner, project_dir):
        result = runner.invoke(main, ["edit", "q-a1b2", "--title", "Title"])
        assert result.exit_code == 1

    def test_edit_nonexistent_quest_shows_error(self, runner, project_dir):
        result = runner.invoke(main, ["edit", "q-a1b2", "--title", "Title"])
        assert "not found" in result.output.lower()

    def test_edit_soft_deleted_quest_exits_1(self, runner, project_dir):
        with db_conn(project_dir) as conn:
            conn.execute(
                "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at, deleted_at) "
                "VALUES ('q-a1b2', 'Deleted Quest', '', 'open', 2, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z', '2025-01-20T12:00:00Z')"
            )
        result = runner.invoke(main, ["edit", "q-a1b2", "--title", "New title"])
        assert result.exit_code == 1

    def test_edit_soft_deleted_quest_shows_deletion_info(self, runner, project_dir):
        with db_conn(project_dir) as conn:
            conn.execute(
                "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at, deleted_at) "
                "VALUES ('q-a1b2', 'Deleted Quest', '', 'open', 2, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z', '2025-01-20T12:00:00Z')"
            )
        result = runner.invoke(main, ["edit", "q-a1b2", "--title", "New title"])
        assert "not found" in result.output.lower()
        assert "2025-01-20" in result.output
        assert "deleted" in result.output.lower()


# ---------------------------------------------------------------------------
# Delete quest — soft delete (no cascade)
# ---------------------------------------------------------------------------


class TestDeleteQuestSoftDelete:
    """lore delete q-xxxx soft-deletes without cascade."""

    def test_exit_code_zero(self, runner, project_dir):
        insert_quest(project_dir, "q-aaa1", "Target Quest")
        insert_mission(project_dir, "q-aaa1/m-m001", "q-aaa1", "M One")
        insert_mission(project_dir, "q-aaa1/m-m002", "q-aaa1", "M Two")
        insert_dependency(project_dir, "q-aaa1/m-m002", "q-aaa1/m-m001")
        result = runner.invoke(main, ["delete", "q-aaa1"])
        assert_exit_ok(result)

    def test_quest_deleted_at_set(self, runner, project_dir):
        insert_quest(project_dir, "q-aaa1", "Target Quest")
        runner.invoke(main, ["delete", "q-aaa1"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT deleted_at FROM quests WHERE id = ?", ("q-aaa1",)
            ).fetchone()
        assert row["deleted_at"] is not None

    def test_missions_not_cascade_deleted(self, runner, project_dir):
        insert_quest(project_dir, "q-aaa1", "Target Quest")
        insert_mission(project_dir, "q-aaa1/m-m001", "q-aaa1", "M One")
        insert_mission(project_dir, "q-aaa1/m-m002", "q-aaa1", "M Two")
        runner.invoke(main, ["delete", "q-aaa1"])
        with db_conn(project_dir) as conn:
            rows = conn.execute(
                "SELECT deleted_at FROM missions WHERE quest_id = ?", ("q-aaa1",)
            ).fetchall()
        assert all(r["deleted_at"] is None for r in rows)

    def test_quest_not_in_list_after_delete(self, runner, project_dir):
        insert_quest(project_dir, "q-aaa1", "Target Quest")
        runner.invoke(main, ["delete", "q-aaa1"])
        result = runner.invoke(main, ["--json", "list"])
        data = json.loads(result.output)
        ids = [q["id"] for q in data["quests"]]
        assert "q-aaa1" not in ids

    def test_deleted_quest_hidden_from_dashboard(self, runner, project_dir):
        with db_conn(project_dir) as conn:
            conn.execute(
                "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-a1b2', 'My Quest', '', 'open', 2, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')"
            )
        runner.invoke(main, ["delete", "q-a1b2"])
        result = runner.invoke(main, [])
        assert "q-a1b2" not in result.output

    def test_show_after_delete_exits_1(self, runner, project_dir):
        insert_quest(project_dir, "q-aaa1", "Target Quest")
        runner.invoke(main, ["delete", "q-aaa1"])
        result = runner.invoke(main, ["show", "q-aaa1"])
        assert result.exit_code == 1
        assert "deleted on" in result.output

    def test_dependency_rows_unaffected_by_non_cascade_delete(self, runner, project_dir):
        insert_quest(project_dir, "q-aaa1", "Target Quest")
        insert_mission(project_dir, "q-aaa1/m-m001", "q-aaa1", "M One")
        insert_mission(project_dir, "q-aaa1/m-m002", "q-aaa1", "M Two")
        insert_dependency(project_dir, "q-aaa1/m-m002", "q-aaa1/m-m001")
        runner.invoke(main, ["delete", "q-aaa1"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT deleted_at FROM dependencies WHERE from_id = ?",
                ("q-aaa1/m-m002",),
            ).fetchone()
        assert row is not None
        assert row["deleted_at"] is None

    def test_delete_output_confirms_deletion(self, runner, project_dir):
        with db_conn(project_dir) as conn:
            conn.execute(
                "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-a1b2', 'My Quest', '', 'open', 2, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')"
            )
        result = runner.invoke(main, ["delete", "q-a1b2"])
        assert "q-a1b2" in result.output
        assert "deleted" in result.output.lower()

    def test_orphaned_missions_visible_with_annotation(self, runner, project_dir):
        with db_conn(project_dir) as conn:
            conn.execute(
                "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-a1b2', 'My Quest', '', 'open', 2, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')"
            )
            conn.execute(
                "INSERT INTO missions (id, quest_id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-a1b2/m-0001', 'q-a1b2', 'Mission 1', '', 'open', 2, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')"
            )
        runner.invoke(main, ["delete", "q-a1b2"])
        result = runner.invoke(main, ["missions", "--all"])
        assert "quest deleted" in result.output.lower()

    def test_json_non_cascade_structure(self, runner, project_dir):
        with db_conn(project_dir) as conn:
            conn.execute(
                "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-a1b2', 'My Quest', '', 'open', 2, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')"
            )
        result = runner.invoke(main, ["--json", "delete", "q-a1b2"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "q-a1b2"
        assert "deleted_at" in data


# ---------------------------------------------------------------------------
# Delete quest — cascade
# ---------------------------------------------------------------------------


class TestDeleteQuestCascade:
    """lore delete q-xxxx --cascade also deletes missions and deps."""

    def test_exit_code_zero(self, runner, project_dir):
        insert_quest(project_dir, "q-aaa1", "Quest To Cascade")
        insert_mission(project_dir, "q-aaa1/m-m001", "q-aaa1", "M One")
        insert_mission(project_dir, "q-aaa1/m-m002", "q-aaa1", "M Two")
        insert_dependency(project_dir, "q-aaa1/m-m002", "q-aaa1/m-m001")
        result = runner.invoke(main, ["delete", "q-aaa1", "--cascade"])
        assert_exit_ok(result)

    def test_quest_deleted_at_set(self, runner, project_dir):
        insert_quest(project_dir, "q-aaa1", "Quest To Cascade")
        runner.invoke(main, ["delete", "q-aaa1", "--cascade"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT deleted_at FROM quests WHERE id = ?", ("q-aaa1",)
            ).fetchone()
        assert row["deleted_at"] is not None

    def test_missions_also_deleted(self, runner, project_dir):
        insert_quest(project_dir, "q-aaa1", "Quest To Cascade")
        insert_mission(project_dir, "q-aaa1/m-m001", "q-aaa1", "M One")
        insert_mission(project_dir, "q-aaa1/m-m002", "q-aaa1", "M Two")
        insert_dependency(project_dir, "q-aaa1/m-m002", "q-aaa1/m-m001")
        runner.invoke(main, ["delete", "q-aaa1", "--cascade"])
        with db_conn(project_dir) as conn:
            rows = conn.execute(
                "SELECT deleted_at FROM missions WHERE quest_id = ?", ("q-aaa1",)
            ).fetchall()
        assert all(r["deleted_at"] is not None for r in rows)

    def test_dependencies_also_deleted(self, runner, project_dir):
        insert_quest(project_dir, "q-aaa1", "Quest To Cascade")
        insert_mission(project_dir, "q-aaa1/m-m001", "q-aaa1", "M One")
        insert_mission(project_dir, "q-aaa1/m-m002", "q-aaa1", "M Two")
        insert_dependency(project_dir, "q-aaa1/m-m002", "q-aaa1/m-m001")
        runner.invoke(main, ["delete", "q-aaa1", "--cascade"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT deleted_at FROM dependencies WHERE from_id = ?",
                ("q-aaa1/m-m002",),
            ).fetchone()
        assert row["deleted_at"] is not None

    def test_cascade_on_empty_quest(self, runner, project_dir):
        with db_conn(project_dir) as conn:
            conn.execute(
                "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-a1b2', 'Empty Quest', '', 'open', 2, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')"
            )
        result = runner.invoke(main, ["--json", "delete", "q-a1b2", "--cascade"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["cascade"] == []

    def test_cascade_output_lists_deleted_missions(self, runner, project_dir):
        with db_conn(project_dir) as conn:
            conn.execute(
                "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-a1b2', 'My Quest', '', 'open', 2, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')"
            )
            conn.execute(
                "INSERT INTO missions (id, quest_id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-a1b2/m-0001', 'q-a1b2', 'M1', '', 'open', 2, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')"
            )
            conn.execute(
                "INSERT INTO missions (id, quest_id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-a1b2/m-0002', 'q-a1b2', 'M2', '', 'open', 2, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')"
            )
        result = runner.invoke(main, ["delete", "q-a1b2", "--cascade"])
        assert result.exit_code == 0
        assert "q-a1b2/m-0001" in result.output
        assert "q-a1b2/m-0002" in result.output

    def test_cascade_cross_quest_dependency_deleted(self, runner, project_dir):
        with db_conn(project_dir) as conn:
            conn.execute(
                "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-a1b2', 'Quest A', '', 'open', 2, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')"
            )
            conn.execute(
                "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-c3d4', 'Quest B', '', 'open', 2, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')"
            )
            conn.execute(
                "INSERT INTO missions (id, quest_id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-a1b2/m-0001', 'q-a1b2', 'Mission A1', '', 'open', 2, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')"
            )
            conn.execute(
                "INSERT INTO missions (id, quest_id, title, description, status, priority, created_at, updated_at) "
                "VALUES ('q-c3d4/m-0001', 'q-c3d4', 'Mission B1', '', 'open', 2, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')"
            )
            conn.execute(
                "INSERT INTO dependencies (from_id, to_id, type) VALUES ('q-c3d4/m-0001', 'q-a1b2/m-0001', 'blocks')"
            )
        runner.invoke(main, ["delete", "q-a1b2", "--cascade"])
        with db_conn(project_dir) as conn:
            dep = conn.execute(
                "SELECT deleted_at FROM dependencies WHERE from_id = ? AND to_id = ?",
                ("q-c3d4/m-0001", "q-a1b2/m-0001"),
            ).fetchone()
        assert dep["deleted_at"] is not None


# ---------------------------------------------------------------------------
# Delete quest — non-existent ID
# ---------------------------------------------------------------------------


class TestDeleteQuestNonExistent:
    """lore delete non-existent ID exits 1."""

    def test_exit_code_1(self, runner, project_dir):
        result = runner.invoke(main, ["delete", "q-zzzz"])
        assert_exit_err(result, code=1)

    def test_error_mentions_not_found(self, runner, project_dir):
        result = runner.invoke(main, ["delete", "q-zzzz"])
        assert "not found" in result.output.lower() or "not found" in (result.output + (result.stderr or "")).lower()

    def test_json_nonexistent_quest_error(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "delete", "q-zzzz"])
        assert result.exit_code == 1
        assert '"error"' in result.output


# ---------------------------------------------------------------------------
# Delete quest — already deleted (idempotent)
# ---------------------------------------------------------------------------


class TestDeleteQuestAlreadyDeleted:
    """lore delete on already-deleted quest exits 0 with warning."""

    def test_exit_code_zero(self, runner, project_dir):
        insert_quest(
            project_dir,
            "q-aaa1",
            "Already Gone",
            deleted_at="2025-01-10T00:00:00Z",
        )
        result = runner.invoke(main, ["delete", "q-aaa1"])
        assert_exit_ok(result)

    def test_warning_message(self, runner, project_dir):
        insert_quest(
            project_dir,
            "q-aaa1",
            "Already Gone",
            deleted_at="2025-01-10T00:00:00Z",
        )
        result = runner.invoke(main, ["delete", "q-aaa1"])
        assert "already deleted" in result.output.lower() or "warning" in result.output.lower()


# ---------------------------------------------------------------------------
# Dashboard — empty project
# ---------------------------------------------------------------------------


class TestDashboardEmpty:
    """lore on empty project shows 'No quests yet' message."""

    def test_exit_code_zero(self, runner, project_dir):
        result = runner.invoke(main, [])
        assert_exit_ok(result)

    def test_no_quests_message(self, runner, project_dir):
        result = runner.invoke(main, [])
        assert "No quests yet" in result.output


# ---------------------------------------------------------------------------
# Dashboard — shows open quests with mission counts
# ---------------------------------------------------------------------------


class TestDashboardWithMissionCounts:
    """lore --json shows quest with mission counts per status."""

    def test_mission_counts_in_json(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "My Quest"])
        quest_id = json.loads(r.output)["id"]

        runner.invoke(main, ["new", "mission", "Open M1", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "Open M2", "-q", quest_id])
        m2_id = json.loads(r2.output)["id"]

        r3 = runner.invoke(main, ["--json", "new", "mission", "In Progress M", "-q", quest_id])
        m3_id = json.loads(r3.output)["id"]
        runner.invoke(main, ["claim", m3_id])

        r4 = runner.invoke(main, ["--json", "new", "mission", "Closed M", "-q", quest_id])
        m4_id = json.loads(r4.output)["id"]
        runner.invoke(main, ["done", m4_id])

        result = runner.invoke(main, ["--json"])
        assert_exit_ok(result)
        data = json.loads(result.output)
        quest_data = next(q for q in data["quests"] if q["id"] == quest_id)
        m = quest_data["missions"]
        assert m["open"] == 2
        assert m["in_progress"] == 1
        assert m["closed"] == 1

    def test_closed_quest_not_in_dashboard(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Open Quest"])
        open_id = json.loads(r.output)["id"]
        insert_quest(
            project_dir,
            "q-closed1",
            "Closed Quest",
            status="closed",
            closed_at="2025-01-20T00:00:00Z",
        )
        result = runner.invoke(main, ["--json"])
        data = json.loads(result.output)
        ids = [q["id"] for q in data["quests"]]
        assert open_id in ids
        assert "q-closed1" not in ids
