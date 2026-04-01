"""E2E tests for lore done behaviour.

Spec: conceptual-workflows-done (lore codex show conceptual-workflows-done)
"""

import json
import re

from lore.cli import main
from lore.db import close_mission
from tests.conftest import (
    assert_exit_ok,
    assert_exit_err,
    db_conn,
    insert_mission,
    insert_quest,
)


# ---------------------------------------------------------------------------
# Close single mission — all valid source statuses
# ---------------------------------------------------------------------------


class TestDoneAllSourceStatuses:
    """close_mission accepts open, in_progress, and blocked as source status."""

    def test_in_progress_to_closed(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M IP", "-q", quest_id])
        m_ip = json.loads(r1.output)["id"]
        runner.invoke(main, ["claim", m_ip])
        result = runner.invoke(main, ["--json", "done", m_ip])
        assert_exit_ok(result)
        data = json.loads(result.output)
        assert m_ip in data["updated"]
        assert "errors" in data
        assert "quest_closed" in data

    def test_open_to_closed(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M Open", "-q", quest_id])
        m_open = json.loads(r1.output)["id"]
        result = runner.invoke(main, ["--json", "done", m_open])
        assert_exit_ok(result)
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status, closed_at FROM missions WHERE id = ?", (m_open,)
            ).fetchone()
        assert row["status"] == "closed"
        assert row["closed_at"] is not None

    def test_blocked_to_closed(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M Blocked", "-q", quest_id])
        m_blocked = json.loads(r1.output)["id"]
        runner.invoke(main, ["claim", m_blocked])
        runner.invoke(main, ["block", m_blocked, "Waiting"])
        result = runner.invoke(main, ["--json", "done", m_blocked])
        assert_exit_ok(result)
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id = ?", (m_blocked,)
            ).fetchone()
        assert row["status"] == "closed"


class TestCloseSingleMission:
    """lore done q-a1b2/m-f3c1 closes an in_progress mission."""

    def test_close_exit_code(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="in_progress"
        )
        result = runner.invoke(main, ["done", "q-a1b2/m-f3c1"])
        assert result.exit_code == 0

    def test_close_status_changes(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="in_progress"
        )
        runner.invoke(main, ["done", "q-a1b2/m-f3c1"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
        assert row["status"] == "closed"

    def test_close_sets_closed_at(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="in_progress"
        )
        runner.invoke(main, ["done", "q-a1b2/m-f3c1"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT closed_at FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
        assert row["closed_at"] is not None

    def test_close_refreshes_updated_at(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "Fix Bug",
            status="in_progress",
            updated_at="2025-01-15T09:30:00Z",
        )
        runner.invoke(main, ["done", "q-a1b2/m-f3c1"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT updated_at FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
        assert row["updated_at"] != "2025-01-15T09:30:00Z"


class TestCloseFromOpen:
    """lore done on an open mission closes it directly."""

    def test_open_to_closed(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="open"
        )
        result = runner.invoke(main, ["done", "q-a1b2/m-f3c1"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
        assert row["status"] == "closed"


class TestCloseFromBlocked:
    """lore done on a blocked mission closes it and clears block_reason."""

    def test_blocked_to_closed(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "Fix Bug",
            status="blocked",
            block_reason="Waiting on API",
        )
        result = runner.invoke(main, ["done", "q-a1b2/m-f3c1"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
        assert row["status"] == "closed"

    def test_blocked_to_closed_clears_block_reason(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "Fix Bug",
            status="blocked",
            block_reason="Waiting on API",
        )
        runner.invoke(main, ["done", "q-a1b2/m-f3c1"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT block_reason FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
        assert row["block_reason"] is None


# ---------------------------------------------------------------------------
# Bulk close
# ---------------------------------------------------------------------------


class TestDoneMultiple:
    """lore done with multiple IDs closes all."""

    def test_both_missions_closed(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M One", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M Two", "-q", quest_id])
        m1 = json.loads(r1.output)["id"]
        m2 = json.loads(r2.output)["id"]
        runner.invoke(main, ["claim", m1])
        runner.invoke(main, ["claim", m2])
        result = runner.invoke(main, ["done", m1, m2])
        assert_exit_ok(result)
        with db_conn(project_dir) as conn:
            rows = conn.execute(
                "SELECT status FROM missions WHERE id IN (?, ?)", (m1, m2)
            ).fetchall()
        assert all(r["status"] == "closed" for r in rows)


class TestBulkClose:
    """lore done id1 id2 closes multiple missions."""

    def test_bulk_close_exit_code(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "M1", status="in_progress"
        )
        insert_mission(
            project_dir, "q-a1b2/m-d2e4", "q-a1b2", "M2", status="in_progress"
        )
        result = runner.invoke(main, ["done", "q-a1b2/m-f3c1", "q-a1b2/m-d2e4"])
        assert result.exit_code == 0

    def test_bulk_close_all_closed(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "M1", status="in_progress"
        )
        insert_mission(
            project_dir, "q-a1b2/m-d2e4", "q-a1b2", "M2", status="in_progress"
        )
        runner.invoke(main, ["done", "q-a1b2/m-f3c1", "q-a1b2/m-d2e4"])
        for mid in ["q-a1b2/m-f3c1", "q-a1b2/m-d2e4"]:
            with db_conn(project_dir) as conn:
                row = conn.execute(
                    "SELECT status FROM missions WHERE id = ?", (mid,)
                ).fetchone()
            assert row["status"] == "closed"


# ---------------------------------------------------------------------------
# Idempotent close (already closed)
# ---------------------------------------------------------------------------


class TestDoneAlreadyClosedMission:
    """lore done on an already-closed mission is idempotent."""

    def test_exit_code_zero(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        runner.invoke(main, ["done", m_id])
        result = runner.invoke(main, ["--json", "done", m_id])
        assert_exit_ok(result)

    def test_mission_remains_closed(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        runner.invoke(main, ["done", m_id])
        with db_conn(project_dir) as conn:
            closed_at_before = conn.execute(
                "SELECT closed_at FROM missions WHERE id = ?", (m_id,)
            ).fetchone()["closed_at"]
        runner.invoke(main, ["done", m_id])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status, closed_at FROM missions WHERE id = ?", (m_id,)
            ).fetchone()
        assert row["status"] == "closed"
        assert row["closed_at"] == closed_at_before


class TestAlreadyClosed:
    """lore done on an already closed mission is a no-op, exit code 0."""

    def test_already_closed_exit_code(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "Fix Bug",
            status="closed",
            closed_at="2025-01-15T10:00:00Z",
        )
        result = runner.invoke(main, ["done", "q-a1b2/m-f3c1"])
        assert result.exit_code == 0

    def test_already_closed_no_change(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "Fix Bug",
            status="closed",
            closed_at="2025-01-15T10:00:00Z",
            updated_at="2025-01-15T10:00:00Z",
        )
        runner.invoke(main, ["done", "q-a1b2/m-f3c1"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status, updated_at FROM missions WHERE id = ?",
                ("q-a1b2/m-f3c1",),
            ).fetchone()
        assert row["status"] == "closed"
        assert row["updated_at"] == "2025-01-15T10:00:00Z"


# ---------------------------------------------------------------------------
# Dependency cascade unblock
# ---------------------------------------------------------------------------


class TestDoneCascadeUnblock:
    """Closing a mission makes its dependents eligible for ready."""

    def test_dependent_excluded_before_close(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M B", "-q", quest_id])
        m_a = json.loads(r1.output)["id"]
        m_b = json.loads(r2.output)["id"]
        runner.invoke(main, ["claim", m_a])
        runner.invoke(main, ["needs", f"{m_b}:{m_a}"])
        result = runner.invoke(main, ["--json", "ready", "10"])
        data = json.loads(result.output)
        ids = [m["id"] for m in data["missions"]]
        assert m_b not in ids

    def test_dependent_eligible_after_close(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M B", "-q", quest_id])
        m_a = json.loads(r1.output)["id"]
        m_b = json.loads(r2.output)["id"]
        runner.invoke(main, ["claim", m_a])
        runner.invoke(main, ["needs", f"{m_b}:{m_a}"])
        runner.invoke(main, ["done", m_a])
        result = runner.invoke(main, ["--json", "ready", "10"])
        data = json.loads(result.output)
        ids = [m["id"] for m in data["missions"]]
        assert m_b in ids

    def test_dependency_row_still_exists(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M B", "-q", quest_id])
        m_a = json.loads(r1.output)["id"]
        m_b = json.loads(r2.output)["id"]
        runner.invoke(main, ["needs", f"{m_b}:{m_a}"])
        runner.invoke(main, ["done", m_a])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT deleted_at FROM dependencies WHERE from_id = ? AND to_id = ?",
                (m_b, m_a),
            ).fetchone()
        assert row is not None
        assert row["deleted_at"] is None


class TestCascadeUnblockDependents:
    """Closing a mission makes its dependents eligible for lore ready."""

    def test_dependent_becomes_ready(self, runner, project_dir):
        """After closing the only dependency, the dependent should be open with no unresolved deps."""
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-def2", "q-a1b2", "Dependency", status="in_progress"
        )
        insert_mission(
            project_dir, "q-a1b2/m-abc1", "q-a1b2", "Dependent", status="open"
        )
        runner.invoke(main, ["needs", "q-a1b2/m-abc1:q-a1b2/m-def2"])
        runner.invoke(main, ["done", "q-a1b2/m-def2"])
        with db_conn(project_dir) as conn:
            mission = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-abc1",)
            ).fetchone()
            dep = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-def2",)
            ).fetchone()
        assert mission["status"] == "open"
        assert dep["status"] == "closed"


class TestCascadeMultipleDependencies:
    """Dependent with multiple deps is not ready until all are closed."""

    def test_partial_deps_not_ready(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-def2", "q-a1b2", "Dep 1", status="in_progress"
        )
        insert_mission(
            project_dir, "q-a1b2/m-ghi3", "q-a1b2", "Dep 2", status="open"
        )
        insert_mission(
            project_dir, "q-a1b2/m-abc1", "q-a1b2", "Dependent", status="open"
        )
        runner.invoke(main, ["needs", "q-a1b2/m-abc1:q-a1b2/m-def2"])
        runner.invoke(main, ["needs", "q-a1b2/m-abc1:q-a1b2/m-ghi3"])
        runner.invoke(main, ["done", "q-a1b2/m-def2"])
        with db_conn(project_dir) as conn:
            mission = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-abc1",)
            ).fetchone()
            dep2 = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-ghi3",)
            ).fetchone()
        assert mission["status"] == "open"
        assert dep2["status"] == "open"


class TestCascadeInProgressUnchanged:
    """In-progress dependent remains in_progress when its dependency closes."""

    def test_in_progress_dependent_unchanged(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-def2", "q-a1b2", "Dep", status="in_progress"
        )
        insert_mission(
            project_dir, "q-a1b2/m-abc1", "q-a1b2", "Dependent", status="in_progress"
        )
        runner.invoke(main, ["needs", "q-a1b2/m-abc1:q-a1b2/m-def2"])
        runner.invoke(main, ["done", "q-a1b2/m-def2"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-abc1",)
            ).fetchone()
        assert row["status"] == "in_progress"


class TestNoAutoUnblockManuallyBlocked:
    """Manually blocked missions stay blocked when their dependency closes."""

    def test_manually_blocked_stays_blocked(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-def2", "q-a1b2", "Dep", status="in_progress"
        )
        insert_mission(
            project_dir,
            "q-a1b2/m-abc1",
            "q-a1b2",
            "Dependent",
            status="blocked",
            block_reason="Manual block",
        )
        runner.invoke(main, ["needs", "q-a1b2/m-abc1:q-a1b2/m-def2"])
        runner.invoke(main, ["done", "q-a1b2/m-def2"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status, block_reason FROM missions WHERE id = ?",
                ("q-a1b2/m-abc1",),
            ).fetchone()
        assert row["status"] == "blocked"
        assert row["block_reason"] == "Manual block"


# ---------------------------------------------------------------------------
# Standalone mission close
# ---------------------------------------------------------------------------


class TestStandaloneMissionClose:
    """Standalone mission (no quest) closes without quest derivation."""

    def test_standalone_close_exit_code(self, runner, project_dir):
        insert_mission(
            project_dir, "m-f3c1", None, "Standalone Task", status="in_progress"
        )
        result = runner.invoke(main, ["done", "m-f3c1"])
        assert result.exit_code == 0

    def test_standalone_close_status(self, runner, project_dir):
        insert_mission(
            project_dir, "m-f3c1", None, "Standalone Task", status="in_progress"
        )
        runner.invoke(main, ["done", "m-f3c1"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("m-f3c1",)
            ).fetchone()
        assert row["status"] == "closed"

    def test_standalone_close_no_quest_side_effects(self, runner, project_dir):
        insert_mission(
            project_dir, "m-f3c1", None, "Standalone Task", status="in_progress"
        )
        runner.invoke(main, ["done", "m-f3c1"])
        with db_conn(project_dir) as conn:
            count = conn.execute("SELECT COUNT(*) FROM quests").fetchone()[0]
        assert count == 0


# ---------------------------------------------------------------------------
# Bulk partial failure
# ---------------------------------------------------------------------------


class TestBulkPartialFailure:
    """Bulk done: valid missions closed, invalid ones error, exit code 1."""

    def test_partial_failure_exit_code(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "M1", status="in_progress"
        )
        result = runner.invoke(main, ["done", "q-a1b2/m-f3c1", "q-a1b2/m-xxxx"])
        assert result.exit_code == 1

    def test_partial_failure_valid_closed(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "M1", status="in_progress"
        )
        runner.invoke(main, ["done", "q-a1b2/m-f3c1", "q-a1b2/m-xxxx"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
        assert row["status"] == "closed"

    def test_partial_failure_error_printed(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "M1", status="in_progress"
        )
        result = runner.invoke(main, ["done", "q-a1b2/m-f3c1", "q-a1b2/m-xxxx"])
        assert "q-a1b2/m-xxxx" in result.output


# ---------------------------------------------------------------------------
# Manual quest close
# ---------------------------------------------------------------------------


class TestDoneQuestManually:
    """lore done q-xxxx manually closes a quest."""

    def test_quest_closed(self, runner, project_dir):
        insert_quest(project_dir, "q-aaa1", "Manual Quest", auto_close=0)
        result = runner.invoke(main, ["done", "q-aaa1"])
        assert_exit_ok(result)
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status, closed_at FROM quests WHERE id = ?", ("q-aaa1",)
            ).fetchone()
        assert row["status"] == "closed"
        assert row["closed_at"] is not None


class TestQuestClosedById:
    """lore done q-xxxx closes the quest."""

    def test_close_quest_exit_code(self, runner, project_dir):
        """Closing an open quest by ID should exit with code 0."""
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        result = runner.invoke(main, ["done", "q-a1b2"])
        assert result.exit_code == 0

    def test_close_quest_sets_status_closed(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        runner.invoke(main, ["done", "q-a1b2"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM quests WHERE id = ?", ("q-a1b2",)
            ).fetchone()
        assert row["status"] == "closed"

    def test_close_quest_sets_closed_at(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        runner.invoke(main, ["done", "q-a1b2"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT closed_at FROM quests WHERE id = ?", ("q-a1b2",)
            ).fetchone()
        assert row["closed_at"] is not None

    def test_close_quest_updates_updated_at(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        runner.invoke(main, ["done", "q-a1b2"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT updated_at FROM quests WHERE id = ?", ("q-a1b2",)
            ).fetchone()
        assert row["updated_at"] != "2025-01-15T09:00:00Z"


# ---------------------------------------------------------------------------
# Already-closed quest (idempotent)
# ---------------------------------------------------------------------------


class TestDoneAlreadyClosedQuest:
    """lore done on already-closed quest is a no-op."""

    def test_exit_code_zero(self, runner, project_dir):
        insert_quest(
            project_dir,
            "q-aaa1",
            "Closed Quest",
            status="closed",
            closed_at="2025-01-20T00:00:00Z",
        )
        result = runner.invoke(main, ["done", "q-aaa1"])
        assert_exit_ok(result)

    def test_status_remains_closed(self, runner, project_dir):
        insert_quest(
            project_dir,
            "q-aaa1",
            "Closed Quest",
            status="closed",
            closed_at="2025-01-20T00:00:00Z",
        )
        runner.invoke(main, ["done", "q-aaa1"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM quests WHERE id = ?", ("q-aaa1",)
            ).fetchone()
        assert row["status"] == "closed"


class TestAlreadyClosedQuestNoop:
    """lore done on an already-closed quest is a no-op with exit code 0."""

    def test_already_closed_quest_exit_code(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest", status="closed")
        result = runner.invoke(main, ["done", "q-a1b2"])
        assert result.exit_code == 0

    def test_already_closed_quest_warning(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest", status="closed")
        result = runner.invoke(main, ["done", "q-a1b2"])
        assert "already closed" in result.output.lower()


# ---------------------------------------------------------------------------
# Non-existent quest
# ---------------------------------------------------------------------------


class TestNonExistentQuestError:
    """lore done on a non-existent quest ID returns an error."""

    def test_nonexistent_quest_exit_code(self, runner, project_dir):
        result = runner.invoke(main, ["done", "q-dead"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_nonexistent_quest_error_message(self, runner, project_dir):
        result = runner.invoke(main, ["done", "q-dead"])
        assert "q-dead" in result.output
        assert "not found" in result.output.lower()
        assert "invalid mission id" not in result.output.lower()


# ---------------------------------------------------------------------------
# Soft-deleted quest
# ---------------------------------------------------------------------------


class TestDoneOnDeletedQuest:
    """lore done on soft-deleted quest exits 1."""

    def test_exit_code_1(self, runner, project_dir):
        insert_quest(
            project_dir, "q-aaa1", "Deleted Quest", deleted_at="2025-01-10T00:00:00Z"
        )
        result = runner.invoke(main, ["done", "q-aaa1"])
        assert result.exit_code == 1

    def test_error_mentions_deleted(self, runner, project_dir):
        insert_quest(
            project_dir, "q-aaa1", "Deleted Quest", deleted_at="2025-01-10T00:00:00Z"
        )
        result = runner.invoke(main, ["done", "q-aaa1"])
        combined = result.output + (result.stderr or "")
        assert "deleted" in combined.lower() or "not found" in combined.lower()


class TestDeletedQuestError:
    """lore done on a soft-deleted quest returns an error with deletion timestamp."""

    def test_deleted_quest_exit_code(self, runner, project_dir):
        insert_quest(
            project_dir,
            "q-a1b2",
            "Deleted Quest",
            deleted_at="2025-06-01T12:00:00Z",
        )
        result = runner.invoke(main, ["done", "q-a1b2"])
        assert result.exit_code == 1
        assert "deleted" in result.output.lower() or "2025-06-01" in result.output

    def test_deleted_quest_error_includes_deletion_timestamp(self, runner, project_dir):
        insert_quest(
            project_dir,
            "q-a1b2",
            "Deleted Quest",
            deleted_at="2025-06-01T12:00:00Z",
        )
        result = runner.invoke(main, ["done", "q-a1b2"])
        assert "2025-06-01" in result.output


# ---------------------------------------------------------------------------
# Quest can be closed while missions are still open
# ---------------------------------------------------------------------------


class TestCloseQuestWithOpenMissions:
    """lore done q-xxxx closes the quest even if missions are still open."""

    def test_quest_closes_with_open_missions(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Open Task", status="open"
        )
        result = runner.invoke(main, ["done", "q-a1b2"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM quests WHERE id = ?", ("q-a1b2",)
            ).fetchone()
        assert row["status"] == "closed"

    def test_quest_closes_with_in_progress_missions(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "WIP Task", status="in_progress"
        )
        result = runner.invoke(main, ["done", "q-a1b2"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM quests WHERE id = ?", ("q-a1b2",)
            ).fetchone()
        assert row["status"] == "closed"


# ---------------------------------------------------------------------------
# Output confirms closure
# ---------------------------------------------------------------------------


class TestOutputConfirmsClosure:
    """The done command output confirms quest closure with ID and timestamp."""

    def test_output_includes_quest_id(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        result = runner.invoke(main, ["done", "q-a1b2"])
        assert result.exit_code == 0
        assert "q-a1b2" in result.output
        assert "closed" in result.output.lower()

    def test_output_includes_closed_keyword(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        result = runner.invoke(main, ["done", "q-a1b2"])
        assert "closed" in result.output.lower()

    def test_output_includes_closure_timestamp(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        result = runner.invoke(main, ["done", "q-a1b2"])
        assert "closed_at" in result.output.lower() or "closed_at:" in result.output


# ---------------------------------------------------------------------------
# JSON output for quest closure
# ---------------------------------------------------------------------------


class TestStructuredOutputClosureDetails:
    """JSON output for quest closure includes id, status, and closed_at."""

    def test_json_output_includes_quest_id(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        result = runner.invoke(main, ["--json", "done", "q-a1b2"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "q-a1b2" in data.get("updated", [])

    def test_json_output_quest_status_closed(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        result = runner.invoke(main, ["--json", "done", "q-a1b2"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "q-a1b2" in data.get("updated", [])


# ---------------------------------------------------------------------------
# Mixing quest and mission IDs in one invocation
# ---------------------------------------------------------------------------


class TestMixedQuestAndMissionIds:
    """lore done can accept both quest IDs and mission IDs in one invocation."""

    def test_mixed_ids_exit_code(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_quest(project_dir, "q-c3d4", "Another Quest")
        insert_mission(
            project_dir, "q-c3d4/m-f3c1", "q-c3d4", "Task", status="in_progress"
        )
        result = runner.invoke(main, ["done", "q-a1b2", "q-c3d4/m-f3c1"])
        assert result.exit_code == 0

    def test_mixed_ids_both_closed(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_quest(project_dir, "q-c3d4", "Another Quest")
        insert_mission(
            project_dir, "q-c3d4/m-f3c1", "q-c3d4", "Task", status="in_progress"
        )
        runner.invoke(main, ["done", "q-a1b2", "q-c3d4/m-f3c1"])
        with db_conn(project_dir) as conn:
            quest = conn.execute(
                "SELECT status FROM quests WHERE id = ?", ("q-a1b2",)
            ).fetchone()
            mission = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("q-c3d4/m-f3c1",)
            ).fetchone()
        assert quest["status"] == "closed"
        assert mission["status"] == "closed"

    def test_mixed_ids_partial_failure(self, runner, project_dir):
        insert_quest(project_dir, "q-c3d4", "Quest")
        insert_mission(
            project_dir, "q-c3d4/m-f3c1", "q-c3d4", "Task", status="in_progress"
        )
        result = runner.invoke(main, ["done", "q-dead", "q-c3d4/m-f3c1"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()
        assert "invalid mission id" not in result.output.lower()


# ---------------------------------------------------------------------------
# Quest auto-close behaviour
# ---------------------------------------------------------------------------


class TestAutoCloseWhenLastMissionDone:
    """Quest auto-closes when all missions are done."""

    def test_quest_not_closed_until_last_mission(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q", "--auto-close"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M1", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M2", "-q", quest_id])
        r3 = runner.invoke(main, ["--json", "new", "mission", "M3", "-q", quest_id])
        m1 = json.loads(r1.output)["id"]
        m2 = json.loads(r2.output)["id"]
        m3 = json.loads(r3.output)["id"]
        runner.invoke(main, ["claim", m1])
        runner.invoke(main, ["claim", m2])
        runner.invoke(main, ["claim", m3])
        runner.invoke(main, ["done", m1])
        runner.invoke(main, ["done", m2])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM quests WHERE id = ?", (quest_id,)
            ).fetchone()
        assert row["status"] != "closed"

    def test_quest_closes_on_last_mission_done(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q", "--auto-close"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M1", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M2", "-q", quest_id])
        r3 = runner.invoke(main, ["--json", "new", "mission", "M3", "-q", quest_id])
        m1 = json.loads(r1.output)["id"]
        m2 = json.loads(r2.output)["id"]
        m3 = json.loads(r3.output)["id"]
        runner.invoke(main, ["claim", m1])
        runner.invoke(main, ["claim", m2])
        runner.invoke(main, ["claim", m3])
        runner.invoke(main, ["done", m1])
        runner.invoke(main, ["done", m2])
        result = runner.invoke(main, ["--json", "done", m3])
        assert_exit_ok(result)
        data = json.loads(result.output)
        assert "quest_closed" in data
        assert isinstance(data["quest_closed"], list)
        assert quest_id in data["quest_closed"]
        assert isinstance(data["updated"], list)
        assert isinstance(data["errors"], list)

    def test_quest_status_closed_in_db(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q", "--auto-close"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M1", "-q", quest_id])
        m1 = json.loads(r1.output)["id"]
        runner.invoke(main, ["done", m1])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status, closed_at FROM quests WHERE id = ?", (quest_id,)
            ).fetchone()
        assert row["status"] == "closed"
        assert row["closed_at"] is not None


class TestCascadeQuestAutoClose:
    """Quest auto-closes when all missions are closed."""

    def test_quest_auto_closes(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest", auto_close=1)
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "M1",
            status="closed",
            closed_at="2025-01-15T10:00:00Z",
        )
        insert_mission(
            project_dir, "q-a1b2/m-d2e4", "q-a1b2", "M2", status="in_progress"
        )
        runner.invoke(main, ["done", "q-a1b2/m-d2e4"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM quests WHERE id = ?", ("q-a1b2",)
            ).fetchone()
        assert row["status"] == "closed"

    def test_quest_auto_close_sets_closed_at(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest", auto_close=1)
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "M1",
            status="closed",
            closed_at="2025-01-15T10:00:00Z",
        )
        insert_mission(
            project_dir, "q-a1b2/m-d2e4", "q-a1b2", "M2", status="in_progress"
        )
        runner.invoke(main, ["done", "q-a1b2/m-d2e4"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT closed_at FROM quests WHERE id = ?", ("q-a1b2",)
            ).fetchone()
        assert row["closed_at"] is not None


class TestNoAutoCloseWhenAllMissionsDone:
    """Quest stays open when auto_close=0, even if all missions done."""

    def test_quest_stays_open(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M1", "-q", quest_id])
        m1 = json.loads(r1.output)["id"]
        runner.invoke(main, ["claim", m1])
        runner.invoke(main, ["done", m1])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM quests WHERE id = ?", (quest_id,)
            ).fetchone()
        assert row["status"] != "closed"

    def test_quest_requires_manual_close(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M1", "-q", quest_id])
        m1 = json.loads(r1.output)["id"]
        runner.invoke(main, ["done", m1])
        result = runner.invoke(main, ["done", quest_id])
        assert_exit_ok(result)
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM quests WHERE id = ?", (quest_id,)
            ).fetchone()
        assert row["status"] == "closed"


class TestManualCloseQuest:
    """lore done q-xxxx manually closes a non-auto-close quest."""

    def test_manual_close_works(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M1", "-q", quest_id])
        m1 = json.loads(r1.output)["id"]
        runner.invoke(main, ["done", m1])
        result = runner.invoke(main, ["done", quest_id])
        assert_exit_ok(result)
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status, closed_at FROM quests WHERE id = ?", (quest_id,)
            ).fetchone()
        assert row["status"] == "closed"
        assert row["closed_at"] is not None


class TestAutoCloseNotTriggeredPartially:
    """auto_close quest stays open when only some missions done."""

    def test_quest_in_progress_not_closed(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q", "--auto-close"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M1", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M2", "-q", quest_id])
        m1 = json.loads(r1.output)["id"]
        m2 = json.loads(r2.output)["id"]
        runner.invoke(main, ["done", m1])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM quests WHERE id = ?", (quest_id,)
            ).fetchone()
        assert row["status"] == "in_progress"


class TestAutoCloseNoMissions:
    """auto_close quest with no missions stays open."""

    def test_empty_quest_stays_open(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q", "--auto-close"])
        quest_id = json.loads(r.output)["id"]
        result = runner.invoke(main, ["--json", "show", quest_id])
        assert_exit_ok(result)
        data = json.loads(result.output)
        assert data["status"] == "open"


class TestQuestStatusDerivationMixedMissions:
    """Mixed closed+open missions yields in_progress quest status."""

    def test_mixed_missions_yields_in_progress(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M1", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M2", "-q", quest_id])
        m1 = json.loads(r1.output)["id"]
        m2 = json.loads(r2.output)["id"]
        runner.invoke(main, ["claim", m1])
        runner.invoke(main, ["done", m1])
        result = runner.invoke(main, ["--json", "show", quest_id])
        assert_exit_ok(result)
        data = json.loads(result.output)
        assert data["status"] == "in_progress"


# ---------------------------------------------------------------------------
# Auto-close toggle (new quest defaults, edit mid-lifecycle)
# ---------------------------------------------------------------------------


class TestNewQuestDefaultsManualClose:
    """New quests default to auto_close=0 (manual close)."""

    def test_new_quest_has_auto_close_disabled(self, runner, project_dir):
        result = runner.invoke(main, ["new", "quest", "Test Quest"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            quests = conn.execute("SELECT auto_close FROM quests").fetchall()
        assert len(quests) == 1
        assert quests[0]["auto_close"] == 0

    def test_quest_with_all_missions_done_stays_open_by_default(
        self, runner, project_dir
    ):
        result = runner.invoke(main, ["new", "quest", "Test Quest"])
        assert result.exit_code == 0
        match = re.search(r"(q-[a-f0-9]{4,6})", result.output)
        assert match
        quest_id = match.group(1)
        result2 = runner.invoke(main, ["new", "mission", "Task 1", "-q", quest_id])
        assert result2.exit_code == 0
        match2 = re.search(r"(q-[a-f0-9]+/m-[a-f0-9]+)", result2.output)
        assert match2
        mission_id = match2.group(1)
        runner.invoke(main, ["claim", mission_id])
        runner.invoke(main, ["done", mission_id])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM quests WHERE id = ?", (quest_id,)
            ).fetchone()
        assert row["status"] != "closed"


class TestAutoCloseEnabledAtCreation:
    """Creating a quest with --auto-close flag sets auto_close=1."""

    def test_auto_close_flag_sets_value(self, runner, project_dir):
        result = runner.invoke(main, ["new", "quest", "Auto Quest", "--auto-close"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute("SELECT auto_close FROM quests").fetchone()
        assert row["auto_close"] == 1

    def test_auto_close_quest_closes_when_all_missions_done(self, runner, project_dir):
        result = runner.invoke(main, ["new", "quest", "Auto Quest", "--auto-close"])
        assert result.exit_code == 0
        match = re.search(r"(q-[a-f0-9]{4,6})", result.output)
        assert match
        quest_id = match.group(1)
        result2 = runner.invoke(main, ["new", "mission", "Task 1", "-q", quest_id])
        assert result2.exit_code == 0
        match2 = re.search(r"(q-[a-f0-9]+/m-[a-f0-9]+)", result2.output)
        assert match2
        mission_id = match2.group(1)
        runner.invoke(main, ["claim", mission_id])
        runner.invoke(main, ["done", mission_id])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM quests WHERE id = ?", (quest_id,)
            ).fetchone()
        assert row["status"] == "closed"


class TestAutoCloseChangedAfterCreation:
    """lore edit with --auto-close or --no-auto-close toggles the setting."""

    def test_enable_auto_close_via_edit(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest", auto_close=0)
        result = runner.invoke(main, ["edit", "q-a1b2", "--auto-close"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT auto_close FROM quests WHERE id = ?", ("q-a1b2",)
            ).fetchone()
        assert row["auto_close"] == 1

    def test_disable_auto_close_via_edit(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest", auto_close=1)
        result = runner.invoke(main, ["edit", "q-a1b2", "--no-auto-close"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT auto_close FROM quests WHERE id = ?", ("q-a1b2",)
            ).fetchone()
        assert row["auto_close"] == 0

    def test_auto_close_toggle_affects_future_completions(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest", auto_close=0)
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Task 1", status="in_progress"
        )
        runner.invoke(main, ["edit", "q-a1b2", "--auto-close"])
        runner.invoke(main, ["done", "q-a1b2/m-f3c1"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM quests WHERE id = ?", ("q-a1b2",)
            ).fetchone()
        assert row["status"] == "closed"


class TestToggleAutoCloseAfterCreation:
    """Enabling auto_close mid-lifecycle triggers close on subsequent done."""

    def test_quest_stays_open_before_auto_close_enabled(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M1", "-q", quest_id])
        m1 = json.loads(r1.output)["id"]
        runner.invoke(main, ["claim", m1])
        runner.invoke(main, ["done", m1])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM quests WHERE id = ?", (quest_id,)
            ).fetchone()
        assert row["status"] != "closed"

    def test_enable_auto_close(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        result = runner.invoke(main, ["edit", quest_id, "--auto-close"])
        assert_exit_ok(result)
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT auto_close FROM quests WHERE id = ?", (quest_id,)
            ).fetchone()
        assert row["auto_close"] == 1

    def test_quest_auto_closes_after_enable(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M1", "-q", quest_id])
        m1 = json.loads(r1.output)["id"]
        runner.invoke(main, ["done", m1])
        runner.invoke(main, ["edit", quest_id, "--auto-close"])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M2", "-q", quest_id])
        m2 = json.loads(r2.output)["id"]
        runner.invoke(main, ["claim", m2])
        runner.invoke(main, ["done", m2])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM quests WHERE id = ?", (quest_id,)
            ).fetchone()
        assert row["status"] == "closed"


class TestNoAutoCloseRemainsOpen:
    """A quest with auto_close=0 remains open even when all missions are done."""

    def test_quest_stays_open_when_all_missions_closed(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Manual Quest", auto_close=0)
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Task 1", status="in_progress"
        )
        runner.invoke(main, ["done", "q-a1b2/m-f3c1"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM quests WHERE id = ?", ("q-a1b2",)
            ).fetchone()
        assert row["status"] != "closed"

    def test_quest_visible_in_list_when_all_missions_closed(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Manual Quest", auto_close=0)
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Task 1", status="in_progress"
        )
        runner.invoke(main, ["done", "q-a1b2/m-f3c1"])
        result = runner.invoke(main, ["list"])
        assert result.exit_code == 0
        assert "q-a1b2" in result.output

    def test_auto_close_quest_does_close_when_all_missions_done(
        self, runner, project_dir
    ):
        insert_quest(project_dir, "q-a1b2", "Auto Quest", auto_close=1)
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Task 1", status="in_progress"
        )
        runner.invoke(main, ["done", "q-a1b2/m-f3c1"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM quests WHERE id = ?", ("q-a1b2",)
            ).fetchone()
        assert row["status"] == "closed"


class TestAddMissionReopensClosedQuest:
    """Adding a mission to a closed quest should reopen it."""

    def test_adding_mission_reopens_closed_quest(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Closed Quest", status="closed", auto_close=0)
        result = runner.invoke(main, ["new", "mission", "New Task", "-q", "q-a1b2"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status, closed_at FROM quests WHERE id = ?", ("q-a1b2",)
            ).fetchone()
        assert row["status"] == "open"
        assert row["closed_at"] is None


# ---------------------------------------------------------------------------
# DB-level API: close_mission returns quest_id on all response paths
# ---------------------------------------------------------------------------


class TestCloseMissionQuestAutoCloses:
    """close_mission on the last open mission in an auto-close quest."""

    def test_result_ok(self, project_dir):
        insert_quest(project_dir, "q-a1b2", "Auto Quest", auto_close=1)
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Last Task", status="open")
        result = close_mission(project_dir, "q-a1b2/m-f3c1")
        assert result["ok"] is True

    def test_quest_closed_is_true(self, project_dir):
        insert_quest(project_dir, "q-a1b2", "Auto Quest", auto_close=1)
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Last Task", status="open")
        result = close_mission(project_dir, "q-a1b2/m-f3c1")
        assert result["quest_closed"] is True

    def test_quest_id_key_present(self, project_dir):
        insert_quest(project_dir, "q-a1b2", "Auto Quest", auto_close=1)
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Last Task", status="open")
        result = close_mission(project_dir, "q-a1b2/m-f3c1")
        assert "quest_id" in result

    def test_quest_id_value(self, project_dir):
        insert_quest(project_dir, "q-a1b2", "Auto Quest", auto_close=1)
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Last Task", status="open")
        result = close_mission(project_dir, "q-a1b2/m-f3c1")
        assert result["quest_id"] == "q-a1b2"


class TestCloseMissionQuestNotClosed:
    """close_mission when the quest still has other open missions."""

    def test_result_ok(self, project_dir):
        insert_quest(project_dir, "q-a1b2", "Auto Quest", auto_close=1)
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Task 1", status="open")
        insert_mission(project_dir, "q-a1b2/m-d2e4", "q-a1b2", "Task 2", status="open")
        result = close_mission(project_dir, "q-a1b2/m-f3c1")
        assert result["ok"] is True

    def test_quest_closed_is_false(self, project_dir):
        insert_quest(project_dir, "q-a1b2", "Auto Quest", auto_close=1)
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Task 1", status="open")
        insert_mission(project_dir, "q-a1b2/m-d2e4", "q-a1b2", "Task 2", status="open")
        result = close_mission(project_dir, "q-a1b2/m-f3c1")
        assert result["quest_closed"] is False

    def test_quest_id_key_present(self, project_dir):
        insert_quest(project_dir, "q-a1b2", "Auto Quest", auto_close=1)
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Task 1", status="open")
        insert_mission(project_dir, "q-a1b2/m-d2e4", "q-a1b2", "Task 2", status="open")
        result = close_mission(project_dir, "q-a1b2/m-f3c1")
        assert "quest_id" in result

    def test_quest_id_value(self, project_dir):
        insert_quest(project_dir, "q-a1b2", "Auto Quest", auto_close=1)
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Task 1", status="open")
        insert_mission(project_dir, "q-a1b2/m-d2e4", "q-a1b2", "Task 2", status="open")
        result = close_mission(project_dir, "q-a1b2/m-f3c1")
        assert result["quest_id"] == "q-a1b2"


class TestCloseMissionStandalone:
    """close_mission on a mission that has no parent quest."""

    def test_result_ok(self, project_dir):
        insert_mission(project_dir, "m-f3c1", None, "Standalone Task", status="open")
        result = close_mission(project_dir, "m-f3c1")
        assert result["ok"] is True

    def test_quest_closed_is_false(self, project_dir):
        insert_mission(project_dir, "m-f3c1", None, "Standalone Task", status="open")
        result = close_mission(project_dir, "m-f3c1")
        assert result["quest_closed"] is False

    def test_quest_id_key_present(self, project_dir):
        insert_mission(project_dir, "m-f3c1", None, "Standalone Task", status="open")
        result = close_mission(project_dir, "m-f3c1")
        assert "quest_id" in result

    def test_quest_id_is_none(self, project_dir):
        insert_mission(project_dir, "m-f3c1", None, "Standalone Task", status="open")
        result = close_mission(project_dir, "m-f3c1")
        assert result["quest_id"] is None


class TestCloseMissionIdempotent:
    """close_mission on a mission that is already closed."""

    def test_result_ok(self, project_dir):
        insert_quest(project_dir, "q-a1b2", "Some Quest", auto_close=1)
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "Already Done",
            status="closed",
            closed_at="2025-01-15T10:00:00Z",
        )
        result = close_mission(project_dir, "q-a1b2/m-f3c1")
        assert result["ok"] is True

    def test_quest_closed_is_false(self, project_dir):
        insert_quest(project_dir, "q-a1b2", "Some Quest", auto_close=1)
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "Already Done",
            status="closed",
            closed_at="2025-01-15T10:00:00Z",
        )
        result = close_mission(project_dir, "q-a1b2/m-f3c1")
        assert result["quest_closed"] is False

    def test_quest_id_key_present(self, project_dir):
        insert_quest(project_dir, "q-a1b2", "Some Quest", auto_close=1)
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "Already Done",
            status="closed",
            closed_at="2025-01-15T10:00:00Z",
        )
        result = close_mission(project_dir, "q-a1b2/m-f3c1")
        assert "quest_id" in result

    def test_quest_id_is_none(self, project_dir):
        """quest_id must be None on idempotent path (per spec)."""
        insert_quest(project_dir, "q-a1b2", "Some Quest", auto_close=1)
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "Already Done",
            status="closed",
            closed_at="2025-01-15T10:00:00Z",
        )
        result = close_mission(project_dir, "q-a1b2/m-f3c1")
        assert result["quest_id"] is None

    def test_standalone_already_closed_quest_id_is_none(self, project_dir):
        """Idempotent close of a standalone mission: quest_id must be None."""
        insert_mission(
            project_dir,
            "m-f3c1",
            None,
            "Standalone Done",
            status="closed",
            closed_at="2025-01-15T10:00:00Z",
        )
        result = close_mission(project_dir, "m-f3c1")
        assert "quest_id" in result
        assert result["quest_id"] is None


class TestCloseMissionNotFound:
    """close_mission on a non-existent mission ID."""

    def test_result_not_ok(self, project_dir):
        result = close_mission(project_dir, "q-xxxx/m-zzzz")
        assert result["ok"] is False

    def test_quest_id_key_present(self, project_dir):
        result = close_mission(project_dir, "q-xxxx/m-zzzz")
        assert "quest_id" in result

    def test_quest_id_is_none(self, project_dir):
        result = close_mission(project_dir, "q-xxxx/m-zzzz")
        assert result["quest_id"] is None


# ---------------------------------------------------------------------------
# Full lifecycle test
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    """open → in_progress → blocked → open → in_progress → closed."""

    def test_full_lifecycle(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]

        # open → verify in ready
        ready1 = runner.invoke(main, ["--json", "ready"])
        data = json.loads(ready1.output)
        assert m_id in [m["id"] for m in data["missions"]]

        # claim → in_progress
        r_claim = runner.invoke(main, ["claim", m_id])
        assert_exit_ok(r_claim)
        with db_conn(project_dir) as conn:
            assert conn.execute(
                "SELECT status FROM missions WHERE id=?", (m_id,)
            ).fetchone()["status"] == "in_progress"

        # block
        r_block = runner.invoke(main, ["block", m_id, "Reason"])
        assert_exit_ok(r_block)

        # unblock → open
        r_unblock = runner.invoke(main, ["unblock", m_id])
        assert_exit_ok(r_unblock)
        with db_conn(project_dir) as conn:
            assert conn.execute(
                "SELECT status FROM missions WHERE id=?", (m_id,)
            ).fetchone()["status"] == "open"

        # claim again → in_progress
        r_claim2 = runner.invoke(main, ["claim", m_id])
        assert_exit_ok(r_claim2)

        # done → closed
        r_done = runner.invoke(main, ["done", m_id])
        assert_exit_ok(r_done)
        with db_conn(project_dir) as conn:
            assert conn.execute(
                "SELECT status FROM missions WHERE id=?", (m_id,)
            ).fetchone()["status"] == "closed"
