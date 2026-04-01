"""E2E tests for lore claim behaviour.

Spec: conceptual-workflows-claim (lore codex show conceptual-workflows-claim)
"""

import json

from lore.cli import main
from lore.db import claim_mission
from tests.conftest import (
    assert_exit_ok,
    assert_exit_err,
    db_conn,
    insert_mission,
    insert_quest,
)


# ---------------------------------------------------------------------------
# Single claim — open → in_progress
# ---------------------------------------------------------------------------


class TestClaimMission:
    """lore claim transitions an open mission to in_progress."""

    def test_exit_code_zero(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r2 = runner.invoke(main, ["--json", "new", "mission", "Task A", "-q", quest_id])
        m_id = json.loads(r2.output)["id"]
        result = runner.invoke(main, ["--json", "claim", m_id])
        assert_exit_ok(result)

    def test_json_output_shape(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r2 = runner.invoke(main, ["--json", "new", "mission", "Task A", "-q", quest_id])
        m_id = json.loads(r2.output)["id"]
        result = runner.invoke(main, ["--json", "claim", m_id])
        data = json.loads(result.output)
        assert "updated" in data
        assert "quest_status_changed" in data
        assert "errors" in data
        assert m_id in data["updated"]
        assert data["errors"] == []

    def test_mission_status_in_progress(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r2 = runner.invoke(main, ["--json", "new", "mission", "Task A", "-q", quest_id])
        m_id = json.loads(r2.output)["id"]
        runner.invoke(main, ["claim", m_id])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id = ?", (m_id,)
            ).fetchone()
        assert row["status"] == "in_progress"

    def test_quest_status_changes_to_in_progress(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r2 = runner.invoke(main, ["--json", "new", "mission", "Task A", "-q", quest_id])
        m_id = json.loads(r2.output)["id"]
        result = runner.invoke(main, ["--json", "claim", m_id])
        data = json.loads(result.output)
        if data["quest_status_changed"]:
            assert any(q["id"] == quest_id for q in data["quest_status_changed"])


class TestSingleClaim:
    """lore claim q-a1b2/m-f3c1 transitions open mission to in_progress."""

    def test_single_claim_exit_code(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug")
        result = runner.invoke(main, ["claim", "q-a1b2/m-f3c1"])
        assert result.exit_code == 0

    def test_single_claim_status_changes(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug")
        runner.invoke(main, ["claim", "q-a1b2/m-f3c1"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status, updated_at FROM missions WHERE id = ?",
                ("q-a1b2/m-f3c1",),
            ).fetchone()
        assert row["status"] == "in_progress"

    def test_single_claim_updated_at_refreshed(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "Fix Bug",
            updated_at="2025-01-15T09:30:00Z",
        )
        runner.invoke(main, ["claim", "q-a1b2/m-f3c1"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT updated_at FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
        assert row["updated_at"] != "2025-01-15T09:30:00Z"


# ---------------------------------------------------------------------------
# Bulk claim
# ---------------------------------------------------------------------------


class TestClaimMultipleMissions:
    """lore claim with multiple IDs transitions all to in_progress."""

    def test_both_missions_in_progress(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M One", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M Two", "-q", quest_id])
        m1 = json.loads(r1.output)["id"]
        m2 = json.loads(r2.output)["id"]
        result = runner.invoke(main, ["claim", m1, m2])
        assert_exit_ok(result)
        with db_conn(project_dir) as conn:
            rows = conn.execute(
                "SELECT id, status FROM missions WHERE id IN (?, ?)", (m1, m2)
            ).fetchall()
        assert all(r["status"] == "in_progress" for r in rows)


class TestBulkClaim:
    """lore claim id1 id2 id3 sets all to in_progress."""

    def test_bulk_claim_exit_code(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Mission 1")
        insert_mission(project_dir, "q-a1b2/m-d2e4", "q-a1b2", "Mission 2")
        insert_mission(project_dir, "q-a1b2/m-ab03", "q-a1b2", "Mission 3")
        result = runner.invoke(
            main, ["claim", "q-a1b2/m-f3c1", "q-a1b2/m-d2e4", "q-a1b2/m-ab03"]
        )
        assert result.exit_code == 0

    def test_bulk_claim_all_in_progress(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Mission 1")
        insert_mission(project_dir, "q-a1b2/m-d2e4", "q-a1b2", "Mission 2")
        insert_mission(project_dir, "q-a1b2/m-ab03", "q-a1b2", "Mission 3")
        runner.invoke(
            main, ["claim", "q-a1b2/m-f3c1", "q-a1b2/m-d2e4", "q-a1b2/m-ab03"]
        )
        for mid in ["q-a1b2/m-f3c1", "q-a1b2/m-d2e4", "q-a1b2/m-ab03"]:
            with db_conn(project_dir) as conn:
                row = conn.execute(
                    "SELECT status FROM missions WHERE id = ?", (mid,)
                ).fetchone()
            assert row["status"] == "in_progress", f"{mid} should be in_progress"


# ---------------------------------------------------------------------------
# Idempotent claim (already in_progress)
# ---------------------------------------------------------------------------


class TestAlreadyInProgress:
    """Claiming an in_progress mission is a no-op with exit code 0."""

    def test_idempotent_exit_code(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "Fix Bug",
            status="in_progress",
        )
        result = runner.invoke(main, ["claim", "q-a1b2/m-f3c1"])
        assert result.exit_code == 0

    def test_idempotent_prints_current_status(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "Fix Bug",
            status="in_progress",
        )
        result = runner.invoke(main, ["claim", "q-a1b2/m-f3c1"])
        assert "in_progress" in result.output

    def test_idempotent_status_unchanged(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "Fix Bug",
            status="in_progress",
            updated_at="2025-01-15T09:30:00Z",
        )
        result = runner.invoke(main, ["claim", "q-a1b2/m-f3c1"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
        assert row["status"] == "in_progress"


# ---------------------------------------------------------------------------
# Claim ignores unresolved dependencies
# ---------------------------------------------------------------------------


class TestClaimIgnoresDependencies:
    """claim succeeds even with unresolved dependencies."""

    def test_claim_with_unresolved_dep(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M One", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M Two", "-q", quest_id])
        m1 = json.loads(r1.output)["id"]
        m2 = json.loads(r2.output)["id"]
        runner.invoke(main, ["needs", f"{m2}:{m1}"])  # m2 depends on m1 (still open)
        result = runner.invoke(main, ["claim", m2])
        assert_exit_ok(result)
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id = ?", (m2,)
            ).fetchone()
        assert row["status"] == "in_progress"


class TestDependenciesNotEnforced:
    """Claiming a mission with unresolved dependencies still succeeds."""

    def test_claim_with_unresolved_deps_succeeds(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="open")
        insert_mission(project_dir, "q-a1b2/m-aaa1", "q-a1b2", "Prereq", status="open")
        runner.invoke(main, ["needs", "q-a1b2/m-f3c1:q-a1b2/m-aaa1"])
        result = runner.invoke(main, ["claim", "q-a1b2/m-f3c1"])
        assert result.exit_code == 0

    def test_claim_with_unresolved_deps_changes_status(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="open")
        insert_mission(project_dir, "q-a1b2/m-aaa1", "q-a1b2", "Prereq", status="open")
        runner.invoke(main, ["needs", "q-a1b2/m-f3c1:q-a1b2/m-aaa1"])
        runner.invoke(main, ["claim", "q-a1b2/m-f3c1"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
        assert row["status"] == "in_progress"


# ---------------------------------------------------------------------------
# Claim blocked mission — error
# ---------------------------------------------------------------------------


class TestClaimBlockedMission:
    """Claiming a blocked mission fails with invalid status transition error."""

    def test_blocked_claim_exit_code(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "Fix Bug",
            status="blocked",
        )
        result = runner.invoke(main, ["claim", "q-a1b2/m-f3c1"])
        assert result.exit_code == 1

    def test_blocked_claim_error_message(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "Fix Bug",
            status="blocked",
        )
        result = runner.invoke(main, ["claim", "q-a1b2/m-f3c1"])
        assert "blocked" in result.output.lower()

    def test_blocked_claim_status_unchanged(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "Fix Bug",
            status="blocked",
        )
        runner.invoke(main, ["claim", "q-a1b2/m-f3c1"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
        assert row["status"] == "blocked"


# ---------------------------------------------------------------------------
# Claim closed mission — error
# ---------------------------------------------------------------------------


class TestClaimClosedMission:
    """Claiming a closed mission fails with invalid status transition error."""

    def test_exit_code_1(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        runner.invoke(main, ["done", m_id])
        result = runner.invoke(main, ["claim", m_id])
        assert result.exit_code == 1

    def test_error_message(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(r1.output)["id"]
        runner.invoke(main, ["done", m_id])
        result = runner.invoke(main, ["claim", m_id])
        combined = result.output + (result.stderr or "")
        assert "closed" in combined.lower() or "already" in combined.lower()

    def test_closed_claim_status_unchanged(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir,
            "q-a1b2/m-f3c1",
            "q-a1b2",
            "Fix Bug",
            status="closed",
        )
        runner.invoke(main, ["claim", "q-a1b2/m-f3c1"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
        assert row["status"] == "closed"


# ---------------------------------------------------------------------------
# Quest status derivation on claim
# ---------------------------------------------------------------------------


class TestQuestStatusDerivationOnClaim:
    """Claiming a mission recomputes the parent quest's status."""

    def test_quest_becomes_in_progress(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest", status="open")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="open")
        insert_mission(project_dir, "q-a1b2/m-d2e4", "q-a1b2", "Write Tests", status="open")
        runner.invoke(main, ["claim", "q-a1b2/m-f3c1"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM quests WHERE id = ?", ("q-a1b2",)
            ).fetchone()
        assert row["status"] == "in_progress"

    def test_quest_updated_at_refreshed(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest", status="open")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="open")
        runner.invoke(main, ["claim", "q-a1b2/m-f3c1"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT updated_at FROM quests WHERE id = ?", ("q-a1b2",)
            ).fetchone()
        assert row["updated_at"] != "2025-01-15T09:00:00Z"


# ---------------------------------------------------------------------------
# Standalone mission claim (no parent quest)
# ---------------------------------------------------------------------------


class TestStandaloneMissionClaim:
    """Standalone mission (no quest) can be claimed."""

    def test_standalone_claim_exit_code(self, runner, project_dir):
        insert_mission(project_dir, "m-f3c1", None, "Standalone Task")
        result = runner.invoke(main, ["claim", "m-f3c1"])
        assert result.exit_code == 0

    def test_standalone_claim_status_changes(self, runner, project_dir):
        insert_mission(project_dir, "m-f3c1", None, "Standalone Task")
        runner.invoke(main, ["claim", "m-f3c1"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("m-f3c1",)
            ).fetchone()
        assert row["status"] == "in_progress"

    def test_standalone_claim_no_quest_side_effects(self, runner, project_dir):
        """Claiming standalone mission doesn't create or modify any quest."""
        insert_mission(project_dir, "m-f3c1", None, "Standalone Task")
        result = runner.invoke(main, ["claim", "m-f3c1"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            count = conn.execute("SELECT COUNT(*) FROM quests").fetchone()[0]
        assert count == 0


# ---------------------------------------------------------------------------
# Bulk partial failure
# ---------------------------------------------------------------------------


class TestBulkPartialFailure:
    """Bulk claim: valid missions claimed, invalid ones error, exit code 1."""

    def test_partial_failure_exit_code(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug")
        result = runner.invoke(main, ["claim", "q-a1b2/m-f3c1", "q-a1b2/m-xxxx"])
        assert result.exit_code == 1

    def test_partial_failure_valid_claimed(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug")
        runner.invoke(main, ["claim", "q-a1b2/m-f3c1", "q-a1b2/m-xxxx"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
        assert row["status"] == "in_progress"

    def test_partial_failure_error_printed(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug")
        result = runner.invoke(main, ["claim", "q-a1b2/m-f3c1", "q-a1b2/m-xxxx"])
        assert "q-a1b2/m-xxxx" in result.output

    def test_partial_failure_blocked_and_valid(self, runner, project_dir):
        """Mix of valid open and invalid blocked missions."""
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Open Mission")
        insert_mission(
            project_dir,
            "q-a1b2/m-d2e4",
            "q-a1b2",
            "Blocked Mission",
            status="blocked",
        )
        result = runner.invoke(main, ["claim", "q-a1b2/m-f3c1", "q-a1b2/m-d2e4"])
        assert result.exit_code == 1
        with db_conn(project_dir) as conn:
            open_row = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-f3c1",)
            ).fetchone()
            blocked_row = conn.execute(
                "SELECT status FROM missions WHERE id = ?", ("q-a1b2/m-d2e4",)
            ).fetchone()
        assert open_row["status"] == "in_progress"
        assert blocked_row["status"] == "blocked"


# ---------------------------------------------------------------------------
# DB-level API: malformed mission ID validation
# ---------------------------------------------------------------------------


class TestMalformedMissionId:
    """claim_mission must reject malformed IDs with a format error, not not-found."""

    def test_garbage_string_returns_ok_false(self, project_dir):
        result = claim_mission(project_dir, "garbage")
        assert result["ok"] is False

    def test_garbage_string_error_mentions_format_or_invalid(self, project_dir):
        """The error must identify the input as badly formatted — not 'not found'."""
        result = claim_mission(project_dir, "garbage")
        assert result["error"] is not None
        lower = result["error"].lower()
        assert "invalid" in lower or "format" in lower, (
            f"Expected format error, got: {result['error']!r}"
        )

    def test_garbage_string_error_is_not_not_found(self, project_dir):
        """Proves format check fires BEFORE the DB lookup."""
        result = claim_mission(project_dir, "garbage")
        assert result["error"] is not None
        assert "not found" not in result["error"].lower(), (
            f"Got a not-found error for malformed ID: {result['error']!r}"
        )

    def test_garbage_string_error_names_the_bad_input(self, project_dir):
        result = claim_mission(project_dir, "garbage")
        assert result["error"] is not None
        assert "garbage" in result["error"], (
            f"Error should name the bad input 'garbage': {result['error']!r}"
        )

    def test_hyphenated_garbage_is_format_error(self, project_dir):
        """A plausible but still-malformed ID also triggers format error."""
        result = claim_mission(project_dir, "bad-id")
        assert result["ok"] is False
        assert result["error"] is not None
        lower = result["error"].lower()
        assert "invalid" in lower or "format" in lower

    def test_bare_quest_id_is_format_error(self, project_dir):
        """A quest ID supplied as a mission ID is a format error."""
        result = claim_mission(project_dir, "q-a1b2")
        assert result["ok"] is False
        assert result["error"] is not None
        lower = result["error"].lower()
        assert "invalid" in lower or "format" in lower

    def test_valid_format_nonexistent_is_not_found_not_format_error(self, project_dir):
        """A correctly-formatted but non-existent ID must return not-found, not format error."""
        result = claim_mission(project_dir, "m-dead1")
        assert result["ok"] is False
        assert result["error"] is not None
        assert "not found" in result["error"].lower() or "m-dead1" in result["error"], (
            f"Expected not-found error for valid-format missing ID, got: {result['error']!r}"
        )
        lower = result["error"].lower()
        assert "format" not in lower and "invalid" not in lower, (
            f"Valid-format ID should not trigger format error: {result['error']!r}"
        )

    def test_malformed_id_has_quest_id_none(self, project_dir):
        """Malformed ID path must also include the three new keys."""
        result = claim_mission(project_dir, "garbage")
        assert "quest_id" in result, "quest_id key missing on format-error path"
        assert result["quest_id"] is None

    def test_malformed_id_has_quest_status_changed_false(self, project_dir):
        result = claim_mission(project_dir, "garbage")
        assert "quest_status_changed" in result, (
            "quest_status_changed key missing on format-error path"
        )
        assert result["quest_status_changed"] is False

    def test_malformed_id_has_quest_status_none(self, project_dir):
        result = claim_mission(project_dir, "garbage")
        assert "quest_status" in result, "quest_status key missing on format-error path"
        assert result["quest_status"] is None


# ---------------------------------------------------------------------------
# DB-level API: quest status keys present on all return paths
# ---------------------------------------------------------------------------


class TestQuestStatusKeysOnSuccess:
    """Successful claim returns quest_id, quest_status_changed, quest_status."""

    def test_quest_transitions_open_to_in_progress_quest_id_present(self, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest", status="open")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug")
        result = claim_mission(project_dir, "q-a1b2/m-f3c1")
        assert result["ok"] is True
        assert "quest_id" in result, "quest_id key missing on success path"
        assert result["quest_id"] == "q-a1b2"

    def test_quest_transitions_open_to_in_progress_changed_true(self, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest", status="open")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug")
        result = claim_mission(project_dir, "q-a1b2/m-f3c1")
        assert "quest_status_changed" in result, (
            "quest_status_changed key missing on success path"
        )
        assert result["quest_status_changed"] is True, (
            "Quest transitioned from open→in_progress; quest_status_changed should be True"
        )

    def test_quest_transitions_open_to_in_progress_quest_status_in_progress(
        self, project_dir
    ):
        insert_quest(project_dir, "q-a1b2", "Test Quest", status="open")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug")
        result = claim_mission(project_dir, "q-a1b2/m-f3c1")
        assert "quest_status" in result, "quest_status key missing on success path"
        assert result["quest_status"] == "in_progress", (
            f"Expected quest_status='in_progress', got {result.get('quest_status')!r}"
        )

    def test_quest_already_in_progress_changed_false(self, project_dir):
        """Claiming a second mission in an already-in-progress quest: no status change."""
        insert_quest(project_dir, "q-a1b2", "Test Quest", status="in_progress")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Mission 1", status="in_progress"
        )
        insert_mission(
            project_dir, "q-a1b2/m-d2e4", "q-a1b2", "Mission 2", status="open"
        )
        result = claim_mission(project_dir, "q-a1b2/m-d2e4")
        assert result["ok"] is True
        assert "quest_status_changed" in result, (
            "quest_status_changed key missing when quest status unchanged"
        )
        assert result["quest_status_changed"] is False, (
            "Quest was already in_progress; quest_status_changed should be False"
        )

    def test_quest_already_in_progress_quest_status_reported(self, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest", status="in_progress")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Mission 1", status="in_progress"
        )
        insert_mission(
            project_dir, "q-a1b2/m-d2e4", "q-a1b2", "Mission 2", status="open"
        )
        result = claim_mission(project_dir, "q-a1b2/m-d2e4")
        assert "quest_status" in result, "quest_status key missing when quest status unchanged"
        assert result["quest_status"] == "in_progress"


class TestQuestStatusKeysOnStandaloneMission:
    """Standalone missions must return quest_id=None and quest_status=None."""

    def test_standalone_claim_succeeds(self, project_dir):
        insert_mission(project_dir, "m-f3c1", None, "Standalone Task")
        result = claim_mission(project_dir, "m-f3c1")
        assert result["ok"] is True

    def test_standalone_quest_id_is_none(self, project_dir):
        """Guard: passing quest_id=None to _derive_quest_status must not crash."""
        insert_mission(project_dir, "m-f3c1", None, "Standalone Task")
        result = claim_mission(project_dir, "m-f3c1")
        assert "quest_id" in result, "quest_id key missing for standalone mission"
        assert result["quest_id"] is None

    def test_standalone_quest_status_changed_false(self, project_dir):
        insert_mission(project_dir, "m-f3c1", None, "Standalone Task")
        result = claim_mission(project_dir, "m-f3c1")
        assert "quest_status_changed" in result, (
            "quest_status_changed key missing for standalone mission"
        )
        assert result["quest_status_changed"] is False

    def test_standalone_quest_status_is_none(self, project_dir):
        insert_mission(project_dir, "m-f3c1", None, "Standalone Task")
        result = claim_mission(project_dir, "m-f3c1")
        assert "quest_status" in result, "quest_status key missing for standalone mission"
        assert result["quest_status"] is None


class TestQuestStatusKeysOnIdempotentPath:
    """Idempotent path (already in_progress) must also carry the three keys."""

    def test_idempotent_has_quest_id(self, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="in_progress"
        )
        result = claim_mission(project_dir, "q-a1b2/m-f3c1")
        assert result["ok"] is True
        assert "quest_id" in result, "quest_id key missing on idempotent path"

    def test_idempotent_has_quest_status_changed(self, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="in_progress"
        )
        result = claim_mission(project_dir, "q-a1b2/m-f3c1")
        assert "quest_status_changed" in result, (
            "quest_status_changed key missing on idempotent path"
        )

    def test_idempotent_has_quest_status(self, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Fix Bug", status="in_progress"
        )
        result = claim_mission(project_dir, "q-a1b2/m-f3c1")
        assert "quest_status" in result, "quest_status key missing on idempotent path"


class TestQuestStatusKeysOnNotFoundPath:
    """Valid-format but missing mission: all three keys must be present."""

    def test_not_found_has_quest_id(self, project_dir):
        result = claim_mission(project_dir, "m-dead1")
        assert result["ok"] is False
        assert "quest_id" in result, "quest_id key missing on not-found path"
        assert result["quest_id"] is None

    def test_not_found_has_quest_status_changed(self, project_dir):
        result = claim_mission(project_dir, "m-dead1")
        assert "quest_status_changed" in result, (
            "quest_status_changed key missing on not-found path"
        )
        assert result["quest_status_changed"] is False

    def test_not_found_has_quest_status(self, project_dir):
        result = claim_mission(project_dir, "m-dead1")
        assert "quest_status" in result, "quest_status key missing on not-found path"
        assert result["quest_status"] is None


class TestQuestStatusKeysOnInvalidTransitionPath:
    """Invalid transition (e.g. claiming a blocked mission) must carry all three keys."""

    def test_blocked_mission_has_quest_id(self, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Blocked", status="blocked"
        )
        result = claim_mission(project_dir, "q-a1b2/m-f3c1")
        assert result["ok"] is False
        assert "quest_id" in result, "quest_id key missing on invalid-transition path"

    def test_blocked_mission_quest_status_changed_false(self, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Blocked", status="blocked"
        )
        result = claim_mission(project_dir, "q-a1b2/m-f3c1")
        assert "quest_status_changed" in result, (
            "quest_status_changed key missing on invalid-transition path"
        )
        assert result["quest_status_changed"] is False

    def test_blocked_mission_has_quest_status(self, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Blocked", status="blocked"
        )
        result = claim_mission(project_dir, "q-a1b2/m-f3c1")
        assert "quest_status" in result, "quest_status key missing on invalid-transition path"

    def test_closed_mission_has_all_three_keys(self, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Closed", status="closed"
        )
        result = claim_mission(project_dir, "q-a1b2/m-f3c1")
        assert result["ok"] is False
        assert "quest_id" in result, "quest_id missing on closed-mission path"
        assert "quest_status_changed" in result, (
            "quest_status_changed missing on closed-mission path"
        )
        assert "quest_status" in result, "quest_status missing on closed-mission path"
