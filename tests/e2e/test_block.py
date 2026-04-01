"""E2E tests for lore block behaviour.

Spec: conceptual-workflows-block (lore codex show conceptual-workflows-block)
"""

from lore.cli import main
from tests.conftest import (
    assert_exit_ok,
    assert_exit_err,
    db_conn,
    insert_mission,
    insert_quest,
)


# ---------------------------------------------------------------------------
# Block from open
# ---------------------------------------------------------------------------


class TestBlockMissionOpen:
    """lore block on an open mission sets status to blocked with reason."""

    def test_open_to_blocked(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="open"
        )
        result = runner.invoke(
            main, ["block", "q-a1b2/m-f3c1", "Dependency resolved externally"]
        )
        assert_exit_ok(result)
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
        assert row["status"] == "blocked"

    def test_block_open_status(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="open"
        )
        runner.invoke(main, ["block", "q-a1b2/m-f3c1", "Waiting on API access"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
        assert row["status"] == "blocked"

    def test_block_open_reason(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="open"
        )
        runner.invoke(main, ["block", "q-a1b2/m-f3c1", "Waiting on API access"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT block_reason FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
        assert row["block_reason"] == "Waiting on API access"


# ---------------------------------------------------------------------------
# Block from in_progress
# ---------------------------------------------------------------------------


class TestBlockMissionInProgress:
    """lore block on in_progress mission sets status to blocked."""

    def test_mission_blocked(self, runner, project_dir):
        from tests.conftest import insert_quest, insert_mission
        import json
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        runner.invoke(main, ["claim", m_id])
        result = runner.invoke(main, ["block", m_id, "Waiting on API credentials"])
        assert_exit_ok(result)
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status, block_reason FROM missions WHERE id = ?", (m_id,)
            ).fetchone()
        assert row["status"] == "blocked"
        assert row["block_reason"] == "Waiting on API credentials"

    def test_show_displays_block_reason(self, runner, project_dir):
        import json
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        runner.invoke(main, ["claim", m_id])
        runner.invoke(main, ["block", m_id, "Waiting on API credentials"])
        result = runner.invoke(main, ["show", m_id])
        assert "Block Reason" in result.output

    def test_block_in_progress_exit_code(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="in_progress"
        )
        result = runner.invoke(
            main, ["block", "q-a1b2/m-f3c1", "External service is down"]
        )
        assert result.exit_code == 0

    def test_block_in_progress_status(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="in_progress"
        )
        runner.invoke(main, ["block", "q-a1b2/m-f3c1", "External service is down"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
        assert row["status"] == "blocked"

    def test_block_in_progress_reason(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="in_progress"
        )
        runner.invoke(main, ["block", "q-a1b2/m-f3c1", "External service is down"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT block_reason FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
        assert row["block_reason"] == "External service is down"


# ---------------------------------------------------------------------------
# Block reason is required
# ---------------------------------------------------------------------------


class TestBlockMissionNoReason:
    """lore block without reason exits 2 (Click usage error)."""

    def test_exit_code_2(self, runner, project_dir):
        import json
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        runner.invoke(main, ["claim", m_id])
        result = runner.invoke(main, ["block", m_id])
        assert result.exit_code == 2


class TestBlockReasonRequired:
    """lore block without a reason fails with usage error."""

    def test_missing_reason_exit_code(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="open"
        )
        result = runner.invoke(main, ["block", "q-a1b2/m-f3c1"])
        assert result.exit_code == 2


# ---------------------------------------------------------------------------
# Block closed mission — error
# ---------------------------------------------------------------------------


class TestBlockClosedMission:
    """lore block on a closed mission fails with invalid status transition."""

    def test_block_closed_exit_code(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="closed"
        )
        result = runner.invoke(main, ["block", "q-a1b2/m-f3c1", "Reason"])
        assert result.exit_code == 1

    def test_block_closed_error_message(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="closed"
        )
        result = runner.invoke(main, ["block", "q-a1b2/m-f3c1", "Reason"])
        assert "closed" in result.output.lower()

    def test_block_closed_status_unchanged(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="closed"
        )
        runner.invoke(main, ["block", "q-a1b2/m-f3c1", "Reason"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
        assert row["status"] == "closed"


# ---------------------------------------------------------------------------
# Block already-blocked mission — error
# ---------------------------------------------------------------------------


class TestBlockAlreadyBlocked:
    """lore block on an already blocked mission fails."""

    def test_block_blocked_exit_code(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "Fix Bug",
            status="blocked",
            block_reason="Old reason",
        )
        result = runner.invoke(main, ["block", "q-a1b2/m-f3c1", "New reason"])
        assert result.exit_code == 1

    def test_block_blocked_reason_unchanged(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "Fix Bug",
            status="blocked",
            block_reason="Old reason",
        )
        runner.invoke(main, ["block", "q-a1b2/m-f3c1", "New reason"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT block_reason FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
        assert row["block_reason"] == "Old reason"


# ---------------------------------------------------------------------------
# Unblock
# ---------------------------------------------------------------------------


class TestUnblockMission:
    """lore unblock returns mission to open."""

    def test_mission_open_after_unblock(self, runner, project_dir):
        import json
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        runner.invoke(main, ["claim", m_id])
        runner.invoke(main, ["block", m_id, "Waiting"])
        result = runner.invoke(main, ["unblock", m_id])
        assert_exit_ok(result)
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status, block_reason FROM missions WHERE id = ?", (m_id,)
            ).fetchone()
        assert row["status"] == "open"
        assert row["block_reason"] is None

    def test_mission_appears_in_ready_after_unblock(self, runner, project_dir):
        import json
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        runner.invoke(main, ["claim", m_id])
        runner.invoke(main, ["block", m_id, "Waiting"])
        runner.invoke(main, ["unblock", m_id])
        result = runner.invoke(main, ["--json", "ready", "10"])
        data = json.loads(result.output)
        ids = [m["id"] for m in data["missions"]]
        assert m_id in ids


class TestUnblockBlockedMission:
    """lore unblock on a blocked mission sets status to open and clears reason."""

    def test_unblock_exit_code(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "Fix Bug",
            status="blocked",
            block_reason="Waiting on API",
        )
        result = runner.invoke(main, ["unblock", "q-a1b2/m-f3c1"])
        assert result.exit_code == 0

    def test_unblock_status(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "Fix Bug",
            status="blocked",
            block_reason="Waiting on API",
        )
        runner.invoke(main, ["unblock", "q-a1b2/m-f3c1"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
        assert row["status"] == "open"

    def test_unblock_clears_reason(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "Fix Bug",
            status="blocked",
            block_reason="Waiting on API",
        )
        runner.invoke(main, ["unblock", "q-a1b2/m-f3c1"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT block_reason FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
        assert row["block_reason"] is None


# ---------------------------------------------------------------------------
# Unblock clears previous claim state
# ---------------------------------------------------------------------------


class TestUnblockClearsClaim:
    """Unblocking returns to open (not in_progress), must be re-claimed."""

    def test_unblock_returns_to_open(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "Fix Bug",
            status="blocked",
            block_reason="Blocked while in progress",
        )
        runner.invoke(main, ["unblock", "q-a1b2/m-f3c1"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
        assert row["status"] == "open"


# ---------------------------------------------------------------------------
# Unblock non-blocked mission — error
# ---------------------------------------------------------------------------


class TestUnblockNonBlockedMission:
    """lore unblock on non-blocked mission exits 1."""

    def test_exit_code_1(self, runner, project_dir):
        import json
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        result = runner.invoke(main, ["unblock", m_id])
        assert result.exit_code == 1

    def test_error_message(self, runner, project_dir):
        import json
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        result = runner.invoke(main, ["unblock", m_id])
        combined = result.output + (result.stderr or "")
        assert (
            "unblock" in combined.lower()
            or "status" in combined.lower()
            or "blocked" in combined.lower()
        )


class TestUnblockNonBlocked:
    """lore unblock on a non-blocked mission fails."""

    def test_unblock_open_exit_code(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="open"
        )
        result = runner.invoke(main, ["unblock", "q-a1b2/m-f3c1"])
        assert result.exit_code == 1

    def test_unblock_in_progress_exit_code(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="in_progress"
        )
        result = runner.invoke(main, ["unblock", "q-a1b2/m-f3c1"])
        assert result.exit_code == 1

    def test_unblock_closed_exit_code(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="closed"
        )
        result = runner.invoke(main, ["unblock", "q-a1b2/m-f3c1"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Quest status recomputed after block/unblock
# ---------------------------------------------------------------------------


class TestQuestStatusAfterBlock:
    """Quest status is recomputed after blocking a mission."""

    def test_quest_remains_open_after_block(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest", status="in_progress")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "M1", status="in_progress"
        )
        insert_mission(
            project_dir, "q-a1b2/m-d2e4", "q-a1b2", "M2", status="open"
        )
        runner.invoke(main, ["block", "q-a1b2/m-f3c1", "Blocked reason"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM quests WHERE id = ?", ("q-a1b2",)
            ).fetchone()
        assert row["status"] == "open"

    def test_quest_stays_in_progress_when_other_in_progress(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest", status="in_progress")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "M1", status="in_progress"
        )
        insert_mission(
            project_dir, "q-a1b2/m-d2e4", "q-a1b2", "M2", status="in_progress"
        )
        runner.invoke(main, ["block", "q-a1b2/m-f3c1", "Blocked reason"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM quests WHERE id = ?", ("q-a1b2",)
            ).fetchone()
        assert row["status"] == "in_progress"
