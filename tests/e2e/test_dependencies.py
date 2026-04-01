"""E2E tests for mission dependency declaration and removal.

Spec: conceptual-workflows-dependencies (lore codex show conceptual-workflows-dependencies)
"""

import json

from lore.cli import main
from lore.db import remove_dependency
from tests.conftest import (
    assert_exit_ok,
    assert_exit_err,
    db_conn,
    insert_dependency,
    insert_mission,
    insert_quest,
)


# ---------------------------------------------------------------------------
# Declare a single dependency
# ---------------------------------------------------------------------------


class TestDeclareSingleDependency:
    """lore needs A:B creates a dependency where A depends on B."""

    def test_exit_code_zero(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M B", "-q", quest_id])
        m_a = json.loads(r1.output)["id"]
        m_b = json.loads(r2.output)["id"]
        result = runner.invoke(main, ["needs", f"{m_b}:{m_a}"])
        assert_exit_ok(result)

    def test_dependency_row_in_db(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M B", "-q", quest_id])
        m_a = json.loads(r1.output)["id"]
        m_b = json.loads(r2.output)["id"]
        runner.invoke(main, ["needs", f"{m_b}:{m_a}"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT from_id, to_id, type, deleted_at "
                "FROM dependencies WHERE from_id = ? AND to_id = ?",
                (m_b, m_a),
            ).fetchone()
        assert row is not None
        assert row["from_id"] == m_b
        assert row["to_id"] == m_a
        assert row["type"] == "blocks"
        assert row["deleted_at"] is None

    def test_output_mentions_both_ids(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B")
        result = runner.invoke(main, ["needs", "q-a1b2/m-abc1:q-a1b2/m-def2"])
        assert result.exit_code == 0
        assert "q-a1b2/m-abc1" in result.output
        assert "q-a1b2/m-def2" in result.output


# ---------------------------------------------------------------------------
# Bulk dependency declaration
# ---------------------------------------------------------------------------


class TestDeclareMultipleDependencies:
    """lore needs with multiple pairs creates all rows."""

    def test_two_dependency_rows_created(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M B", "-q", quest_id])
        r3 = runner.invoke(main, ["--json", "new", "mission", "M C", "-q", quest_id])
        m_a = json.loads(r1.output)["id"]
        m_b = json.loads(r2.output)["id"]
        m_c = json.loads(r3.output)["id"]
        result = runner.invoke(main, ["needs", f"{m_b}:{m_a}", f"{m_c}:{m_b}"])
        assert_exit_ok(result)
        with db_conn(project_dir) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM dependencies WHERE deleted_at IS NULL"
            ).fetchone()[0]
        assert count == 2

    def test_bulk_both_created(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B")
        insert_mission(project_dir, "q-a1b2/m-ghi3", "q-a1b2", "Mission C")
        runner.invoke(main, [
            "needs",
            "q-a1b2/m-abc1:q-a1b2/m-def2",
            "q-a1b2/m-ghi3:q-a1b2/m-def2",
        ])
        with db_conn(project_dir) as conn:
            rows = conn.execute(
                "SELECT from_id, to_id FROM dependencies WHERE deleted_at IS NULL"
            ).fetchall()
        pairs = {(r["from_id"], r["to_id"]) for r in rows}
        assert ("q-a1b2/m-abc1", "q-a1b2/m-def2") in pairs
        assert ("q-a1b2/m-ghi3", "q-a1b2/m-def2") in pairs


# ---------------------------------------------------------------------------
# Cross-quest dependencies
# ---------------------------------------------------------------------------


class TestCrossQuestDependency:
    """Cross-quest dependencies are allowed."""

    def test_cross_quest_dep_created(self, runner, project_dir):
        r1 = runner.invoke(main, ["--json", "new", "quest", "Quest A"])
        r2 = runner.invoke(main, ["--json", "new", "quest", "Quest B"])
        qa = json.loads(r1.output)["id"]
        qb = json.loads(r2.output)["id"]
        rm1 = runner.invoke(main, ["--json", "new", "mission", "M1", "-q", qa])
        rm2 = runner.invoke(main, ["--json", "new", "mission", "M2", "-q", qb])
        m1 = json.loads(rm1.output)["id"]
        m2 = json.loads(rm2.output)["id"]
        result = runner.invoke(main, ["needs", f"{m1}:{m2}"])
        assert_exit_ok(result)
        show_result = runner.invoke(main, ["--json", "show", m1])
        data = json.loads(show_result.output)
        needs_ids = [d["id"] for d in data["dependencies"]["needs"]]
        assert m2 in needs_ids

    def test_cross_quest_dependency_in_db(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest A")
        insert_quest(project_dir, "q-b2c3", "Quest B")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-b2c3/m-def2", "q-b2c3", "Mission B")
        runner.invoke(main, ["needs", "q-a1b2/m-abc1:q-b2c3/m-def2"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT from_id, to_id FROM dependencies WHERE from_id = ? AND to_id = ?",
                ("q-a1b2/m-abc1", "q-b2c3/m-def2"),
            ).fetchone()
        assert row is not None


# ---------------------------------------------------------------------------
# Standalone-to-quest and quest-to-standalone
# ---------------------------------------------------------------------------


class TestStandaloneToQuestDependencies:
    """Dependencies between standalone and quest-bound missions are allowed."""

    def test_standalone_to_quest(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest A")
        insert_mission(project_dir, "m-abc1", None, "Standalone Mission")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Quest Mission")
        result = runner.invoke(main, ["needs", "m-abc1:q-a1b2/m-def2"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT from_id, to_id FROM dependencies WHERE from_id = ? AND to_id = ?",
                ("m-abc1", "q-a1b2/m-def2"),
            ).fetchone()
        assert row is not None

    def test_quest_to_standalone(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Quest Mission")
        insert_mission(project_dir, "m-abc1", None, "Standalone Mission")
        result = runner.invoke(main, ["needs", "q-a1b2/m-def2:m-abc1"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Duplicate dependency (idempotent)
# ---------------------------------------------------------------------------


class TestDuplicateDependency:
    """Duplicate dependency is a no-op with warning and exit code 0."""

    def test_duplicate_exit_code_zero(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B")
        insert_dependency(project_dir, "q-a1b2/m-abc1", "q-a1b2/m-def2")
        result = runner.invoke(main, ["needs", "q-a1b2/m-abc1:q-a1b2/m-def2"])
        assert result.exit_code == 0

    def test_duplicate_warning_message(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B")
        insert_dependency(project_dir, "q-a1b2/m-abc1", "q-a1b2/m-def2")
        result = runner.invoke(main, ["needs", "q-a1b2/m-abc1:q-a1b2/m-def2"])
        assert "already exists" in result.output.lower()

    def test_duplicate_no_extra_row(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B")
        insert_dependency(project_dir, "q-a1b2/m-abc1", "q-a1b2/m-def2")
        runner.invoke(main, ["needs", "q-a1b2/m-abc1:q-a1b2/m-def2"])
        with db_conn(project_dir) as conn:
            count = conn.execute("SELECT COUNT(*) FROM dependencies").fetchone()[0]
        assert count == 1


# ---------------------------------------------------------------------------
# Cycle detection — direct cycle
# ---------------------------------------------------------------------------


class TestCycleDetectionDirect:
    """Direct cycle A→B, B→A is detected and rejected."""

    def test_exit_code_1(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M B", "-q", quest_id])
        m_a = json.loads(r1.output)["id"]
        m_b = json.loads(r2.output)["id"]
        runner.invoke(main, ["needs", f"{m_a}:{m_b}"])
        result = runner.invoke(main, ["needs", f"{m_b}:{m_a}"])
        assert result.exit_code == 1

    def test_error_mentions_cycle(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M B", "-q", quest_id])
        m_a = json.loads(r1.output)["id"]
        m_b = json.loads(r2.output)["id"]
        runner.invoke(main, ["needs", f"{m_a}:{m_b}"])
        result = runner.invoke(main, ["needs", f"{m_b}:{m_a}"])
        combined = result.output + (result.stderr or "")
        assert "circular" in combined.lower() or "cycle" in combined.lower()

    def test_no_new_row_inserted(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M B", "-q", quest_id])
        m_a = json.loads(r1.output)["id"]
        m_b = json.loads(r2.output)["id"]
        runner.invoke(main, ["needs", f"{m_a}:{m_b}"])
        runner.invoke(main, ["needs", f"{m_b}:{m_a}"])
        with db_conn(project_dir) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM dependencies WHERE deleted_at IS NULL"
            ).fetchone()[0]
        assert count == 1

    def test_direct_cycle_from_db_state(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B")
        insert_dependency(project_dir, "q-a1b2/m-def2", "q-a1b2/m-abc1")
        result = runner.invoke(main, ["needs", "q-a1b2/m-abc1:q-a1b2/m-def2"])
        assert result.exit_code == 1
        assert "circular" in result.output.lower() or "cycle" in result.output.lower()


# ---------------------------------------------------------------------------
# Cycle detection — indirect/transitive cycle
# ---------------------------------------------------------------------------


class TestCycleDetectionIndirect:
    """Indirect cycle A→B→C→A is detected."""

    def test_indirect_cycle_rejected(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M B", "-q", quest_id])
        r3 = runner.invoke(main, ["--json", "new", "mission", "M C", "-q", quest_id])
        m_a = json.loads(r1.output)["id"]
        m_b = json.loads(r2.output)["id"]
        m_c = json.loads(r3.output)["id"]
        runner.invoke(main, ["needs", f"{m_a}:{m_b}"])
        runner.invoke(main, ["needs", f"{m_b}:{m_c}"])
        result = runner.invoke(main, ["needs", f"{m_c}:{m_a}"])
        assert result.exit_code == 1
        combined = result.output + (result.stderr or "")
        assert "circular" in combined.lower() or "cycle" in combined.lower()

    def test_transitive_cycle_from_db_state(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-aaa1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-bbb2", "q-a1b2", "Mission B")
        insert_mission(project_dir, "q-a1b2/m-ccc3", "q-a1b2", "Mission C")
        insert_dependency(project_dir, "q-a1b2/m-bbb2", "q-a1b2/m-aaa1")
        insert_dependency(project_dir, "q-a1b2/m-ccc3", "q-a1b2/m-bbb2")
        result = runner.invoke(main, ["needs", "q-a1b2/m-aaa1:q-a1b2/m-ccc3"])
        assert result.exit_code == 1
        with db_conn(project_dir) as conn:
            count = conn.execute("SELECT COUNT(*) FROM dependencies").fetchone()[0]
        assert count == 2


# ---------------------------------------------------------------------------
# Self-dependency rejected
# ---------------------------------------------------------------------------


class TestSelfDependencyRejected:
    """A mission cannot depend on itself."""

    def test_self_dep_exit_code_1(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id])
        m_a = json.loads(r1.output)["id"]
        result = runner.invoke(main, ["needs", f"{m_a}:{m_a}"])
        assert result.exit_code == 1

    def test_self_dep_error_message(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id])
        m_a = json.loads(r1.output)["id"]
        result = runner.invoke(main, ["needs", f"{m_a}:{m_a}"])
        combined = result.output + (result.stderr or "")
        assert "circular" in combined.lower() or "cycle" in combined.lower() or "self" in combined.lower()

    def test_self_dep_from_db_state(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        result = runner.invoke(main, ["needs", "q-a1b2/m-abc1:q-a1b2/m-abc1"])
        assert result.exit_code == 1
        with db_conn(project_dir) as conn:
            count = conn.execute("SELECT COUNT(*) FROM dependencies").fetchone()[0]
        assert count == 0


# ---------------------------------------------------------------------------
# Malformed pair format
# ---------------------------------------------------------------------------


class TestMalformedPairFormat:
    """Arguments without exactly one colon fail with a format error."""

    def test_no_colon_exit_code(self, runner, project_dir):
        result = runner.invoke(main, ["needs", "bad-arg"])
        assert result.exit_code == 1

    def test_no_colon_error_message(self, runner, project_dir):
        result = runner.invoke(main, ["needs", "bad-arg"])
        assert 'Invalid dependency pair format' in result.output
        assert '"bad-arg"' in result.output
        assert 'Expected "from:to"' in result.output

    def test_too_many_colons_exit_code(self, runner, project_dir):
        result = runner.invoke(main, ["needs", "a:b:c"])
        assert result.exit_code == 1

    def test_empty_pair_side(self, runner, project_dir):
        result = runner.invoke(main, ["needs", ":m-abc1"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Non-existent mission in pair
# ---------------------------------------------------------------------------


class TestNonexistentMission:
    """A pair referencing a nonexistent mission fails with not found error."""

    def test_nonexistent_to_mission_exit_code(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        result = runner.invoke(main, ["needs", "q-a1b2/m-abc1:q-a1b2/m-xxxx"])
        assert result.exit_code == 1

    def test_nonexistent_to_mission_error_message(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        result = runner.invoke(main, ["needs", "q-a1b2/m-abc1:q-a1b2/m-xxxx"])
        assert "not found" in result.output.lower()

    def test_nonexistent_from_mission_exit_code(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B")
        result = runner.invoke(main, ["needs", "q-a1b2/m-xxxx:q-a1b2/m-def2"])
        assert result.exit_code == 1

    def test_nonexistent_mission_no_dependency_created(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        runner.invoke(main, ["needs", "q-a1b2/m-abc1:q-a1b2/m-xxxx"])
        with db_conn(project_dir) as conn:
            count = conn.execute("SELECT COUNT(*) FROM dependencies").fetchone()[0]
        assert count == 0


# ---------------------------------------------------------------------------
# Dependency on a closed mission
# ---------------------------------------------------------------------------


class TestDependencyOnClosedMission:
    """Dependency on a closed mission is allowed; it does not block the dependent."""

    def test_closed_target_exit_code_zero(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A", status="open")
        insert_mission(
            project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B",
            status="closed", closed_at="2025-01-15T10:00:00Z",
        )
        result = runner.invoke(main, ["needs", "q-a1b2/m-abc1:q-a1b2/m-def2"])
        assert result.exit_code == 0

    def test_closed_target_note_message(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A", status="open")
        insert_mission(
            project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B",
            status="closed", closed_at="2025-01-15T10:00:00Z",
        )
        result = runner.invoke(main, ["needs", "q-a1b2/m-abc1:q-a1b2/m-def2"])
        assert "already closed" in result.output.lower()
        assert "not blocked" in result.output.lower()

    def test_mission_in_ready_despite_dep_on_closed(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M B", "-q", quest_id])
        m_a = json.loads(r1.output)["id"]
        m_b = json.loads(r2.output)["id"]
        runner.invoke(main, ["done", m_b])
        runner.invoke(main, ["needs", f"{m_a}:{m_b}"])
        result = runner.invoke(main, ["--json", "ready", "10"])
        data = json.loads(result.output)
        ids = [m["id"] for m in data["missions"]]
        assert m_a in ids


# ---------------------------------------------------------------------------
# Bulk partial failure
# ---------------------------------------------------------------------------


class TestBulkPartialFailure:
    """Valid pairs commit; invalid pairs error; exit 1 if any failed."""

    def test_partial_failure_exit_code_1(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B")
        result = runner.invoke(main, [
            "needs",
            "q-a1b2/m-abc1:q-a1b2/m-def2",
            "q-a1b2/m-abc1:q-a1b2/m-xxxx",
        ])
        assert result.exit_code == 1

    def test_partial_failure_valid_pair_committed(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B")
        runner.invoke(main, [
            "needs",
            "q-a1b2/m-abc1:q-a1b2/m-def2",
            "q-a1b2/m-abc1:q-a1b2/m-xxxx",
        ])
        with db_conn(project_dir) as conn:
            rows = conn.execute(
                "SELECT from_id, to_id FROM dependencies WHERE deleted_at IS NULL"
            ).fetchall()
        assert len(rows) == 1
        assert rows[0]["from_id"] == "q-a1b2/m-abc1"
        assert rows[0]["to_id"] == "q-a1b2/m-def2"

    def test_all_valid_exit_code_zero(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B")
        insert_mission(project_dir, "q-a1b2/m-ghi3", "q-a1b2", "Mission C")
        result = runner.invoke(main, [
            "needs",
            "q-a1b2/m-abc1:q-a1b2/m-def2",
            "q-a1b2/m-ghi3:q-a1b2/m-def2",
        ])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Remove dependency
# ---------------------------------------------------------------------------


class TestRemoveDependency:
    """lore unneed soft-deletes a dependency row."""

    def test_exit_code_zero(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M B", "-q", quest_id])
        m_a = json.loads(r1.output)["id"]
        m_b = json.loads(r2.output)["id"]
        runner.invoke(main, ["needs", f"{m_b}:{m_a}"])
        result = runner.invoke(main, ["unneed", f"{m_b}:{m_a}"])
        assert_exit_ok(result)

    def test_dependency_row_soft_deleted(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M B", "-q", quest_id])
        m_a = json.loads(r1.output)["id"]
        m_b = json.loads(r2.output)["id"]
        runner.invoke(main, ["needs", f"{m_b}:{m_a}"])
        runner.invoke(main, ["unneed", f"{m_b}:{m_a}"])
        with db_conn(project_dir) as conn:
            row = conn.execute(
                "SELECT deleted_at FROM dependencies WHERE from_id = ? AND to_id = ?",
                (m_b, m_a),
            ).fetchone()
        assert row["deleted_at"] is not None

    def test_dependency_absent_from_show(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M B", "-q", quest_id])
        m_a = json.loads(r1.output)["id"]
        m_b = json.loads(r2.output)["id"]
        runner.invoke(main, ["needs", f"{m_b}:{m_a}"])
        runner.invoke(main, ["unneed", f"{m_b}:{m_a}"])
        result = runner.invoke(main, ["--json", "show", m_b])
        data = json.loads(result.output)
        needs_ids = [d["id"] for d in data["dependencies"]["needs"]]
        assert m_a not in needs_ids

    def test_soft_deleted_row_only_one_copy(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B")
        insert_dependency(project_dir, "q-a1b2/m-def2", "q-a1b2/m-abc1")
        runner.invoke(main, ["unneed", "q-a1b2/m-def2:q-a1b2/m-abc1"])
        with db_conn(project_dir) as conn:
            count = conn.execute("SELECT COUNT(*) FROM dependencies").fetchone()[0]
        assert count == 1
        with db_conn(project_dir) as conn:
            count_active = conn.execute(
                "SELECT COUNT(*) FROM dependencies WHERE deleted_at IS NULL"
            ).fetchone()[0]
        assert count_active == 0

    def test_mission_no_longer_blocked_after_removal(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B", priority=0)
        insert_dependency(project_dir, "q-a1b2/m-def2", "q-a1b2/m-abc1")
        runner.invoke(main, ["unneed", "q-a1b2/m-def2:q-a1b2/m-abc1"])
        result = runner.invoke(main, ["ready"])
        assert "q-a1b2/m-def2" in result.output


# ---------------------------------------------------------------------------
# Remove multiple dependencies
# ---------------------------------------------------------------------------


class TestRemoveMultipleDependencies:
    """lore unneed with multiple pairs removes all specified dependencies."""

    def test_remove_multiple_exit_code_zero(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Mission C")
        insert_mission(project_dir, "q-a1b2/m-f3d2", "q-a1b2", "Mission D")
        insert_dependency(project_dir, "q-a1b2/m-def2", "q-a1b2/m-abc1")
        insert_dependency(project_dir, "q-a1b2/m-f3c1", "q-a1b2/m-f3d2")
        result = runner.invoke(main, [
            "unneed",
            "q-a1b2/m-def2:q-a1b2/m-abc1",
            "q-a1b2/m-f3c1:q-a1b2/m-f3d2",
        ])
        assert result.exit_code == 0

    def test_remove_multiple_all_soft_deleted(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Mission C")
        insert_mission(project_dir, "q-a1b2/m-f3d2", "q-a1b2", "Mission D")
        insert_dependency(project_dir, "q-a1b2/m-def2", "q-a1b2/m-abc1")
        insert_dependency(project_dir, "q-a1b2/m-f3c1", "q-a1b2/m-f3d2")
        runner.invoke(main, [
            "unneed",
            "q-a1b2/m-def2:q-a1b2/m-abc1",
            "q-a1b2/m-f3c1:q-a1b2/m-f3d2",
        ])
        with db_conn(project_dir) as conn:
            count_active = conn.execute(
                "SELECT COUNT(*) FROM dependencies WHERE deleted_at IS NULL"
            ).fetchone()[0]
        assert count_active == 0


# ---------------------------------------------------------------------------
# Remove non-existent dependency (idempotent)
# ---------------------------------------------------------------------------


class TestRemoveNonExistentDependency:
    """Removing a non-existent dependency is a no-op with warning and exit 0."""

    def test_exit_code_zero(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M B", "-q", quest_id])
        m_a = json.loads(r1.output)["id"]
        m_b = json.loads(r2.output)["id"]
        result = runner.invoke(main, ["unneed", f"{m_b}:{m_a}"])
        assert_exit_ok(result)

    def test_warning_in_output(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B")
        result = runner.invoke(main, ["unneed", "q-a1b2/m-abc1:q-a1b2/m-def2"])
        output = result.output.lower()
        assert "not found" in output or "no dependency" in output or "warning" in output

    def test_already_deleted_dep_treated_as_not_found(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B")
        insert_dependency(
            project_dir, "q-a1b2/m-def2", "q-a1b2/m-abc1",
            deleted_at="2025-01-20T12:00:00Z",
        )
        result = runner.invoke(main, ["unneed", "q-a1b2/m-def2:q-a1b2/m-abc1"])
        assert result.exit_code == 0
        output = result.output.lower()
        assert "not found" in output or "no dependency" in output or "warning" in output


# ---------------------------------------------------------------------------
# Re-add dependency after removal
# ---------------------------------------------------------------------------


class TestReAddDependencyAfterRemoval:
    """Re-adding a removed dependency reactivates the soft-deleted row."""

    def test_only_one_active_row_after_readd(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M B", "-q", quest_id])
        m_a = json.loads(r1.output)["id"]
        m_b = json.loads(r2.output)["id"]
        runner.invoke(main, ["needs", f"{m_b}:{m_a}"])
        runner.invoke(main, ["unneed", f"{m_b}:{m_a}"])
        result = runner.invoke(main, ["needs", f"{m_b}:{m_a}"])
        assert_exit_ok(result)
        with db_conn(project_dir) as conn:
            active_count = conn.execute(
                "SELECT COUNT(*) FROM dependencies "
                "WHERE from_id = ? AND to_id = ? AND deleted_at IS NULL",
                (m_b, m_a),
            ).fetchone()[0]
            total_count = conn.execute(
                "SELECT COUNT(*) FROM dependencies WHERE from_id = ? AND to_id = ?",
                (m_b, m_a),
            ).fetchone()[0]
        assert active_count == 1
        assert total_count == 1

    def test_readd_from_db_state(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B")
        insert_dependency(project_dir, "q-a1b2/m-def2", "q-a1b2/m-abc1")
        runner.invoke(main, ["unneed", "q-a1b2/m-def2:q-a1b2/m-abc1"])
        result = runner.invoke(main, ["needs", "q-a1b2/m-def2:q-a1b2/m-abc1"])
        assert result.exit_code == 0
        with db_conn(project_dir) as conn:
            active = conn.execute(
                "SELECT COUNT(*) FROM dependencies "
                "WHERE from_id = ? AND to_id = ? AND deleted_at IS NULL",
                ("q-a1b2/m-def2", "q-a1b2/m-abc1"),
            ).fetchone()[0]
        assert active == 1


# ---------------------------------------------------------------------------
# Invalid ID format in unneed
# ---------------------------------------------------------------------------


class TestInvalidMissionIdFormatInUnneed:
    """Invalid mission IDs in colon-pairs are rejected by unneed."""

    def test_invalid_from_id_exit_code(self, runner, project_dir):
        result = runner.invoke(main, ["unneed", "invalid:q-a1b2/m-abc1"])
        assert result.exit_code == 1

    def test_invalid_to_id_exit_code(self, runner, project_dir):
        result = runner.invoke(main, ["unneed", "q-a1b2/m-abc1:invalid"])
        assert result.exit_code == 1

    def test_invalid_id_error_message(self, runner, project_dir):
        result = runner.invoke(main, ["unneed", "invalid:format"])
        assert "invalid" in result.output.lower()

    def test_malformed_no_colon(self, runner, project_dir):
        result = runner.invoke(main, ["unneed", "bad-arg"])
        assert result.exit_code == 1

    def test_malformed_too_many_colons(self, runner, project_dir):
        result = runner.invoke(main, ["unneed", "a:b:c"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Ready queue updates after removal
# ---------------------------------------------------------------------------


class TestReadyQueueUpdatesAfterRemoval:
    """After removing the only dependency, mission appears in ready queue."""

    def test_mission_becomes_ready_after_removal(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B", priority=0)
        insert_dependency(project_dir, "q-a1b2/m-def2", "q-a1b2/m-abc1")
        result = runner.invoke(main, ["ready"])
        assert "q-a1b2/m-def2" not in result.output
        runner.invoke(main, ["unneed", "q-a1b2/m-def2:q-a1b2/m-abc1"])
        result = runner.invoke(main, ["ready"])
        assert "q-a1b2/m-def2" in result.output

    def test_mission_stays_blocked_if_other_dependencies_remain(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Dep A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Dep B")
        insert_mission(project_dir, "q-a1b2/m-f3c1", "q-a1b2", "Blocked Mission", priority=0)
        insert_dependency(project_dir, "q-a1b2/m-f3c1", "q-a1b2/m-abc1")
        insert_dependency(project_dir, "q-a1b2/m-f3c1", "q-a1b2/m-def2")
        result = runner.invoke(main, ["unneed", "q-a1b2/m-f3c1:q-a1b2/m-abc1"])
        assert result.exit_code == 0
        result = runner.invoke(main, ["ready", "10"])
        assert "q-a1b2/m-f3c1" not in result.output


# ---------------------------------------------------------------------------
# JSON output for unneed
# ---------------------------------------------------------------------------


class TestUnneedJsonOutput:
    """--json flag on unneed produces structured output."""

    def test_json_output_removed(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B")
        insert_dependency(project_dir, "q-a1b2/m-def2", "q-a1b2/m-abc1")
        result = runner.invoke(main, ["unneed", "--json", "q-a1b2/m-def2:q-a1b2/m-abc1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "removed" in data
        assert "not_found" in data
        assert "errors" in data
        assert len(data["removed"]) == 1
        assert data["removed"][0]["from"] == "q-a1b2/m-def2"
        assert data["removed"][0]["to"] == "q-a1b2/m-abc1"

    def test_json_output_not_found(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B")
        result = runner.invoke(main, ["unneed", "--json", "q-a1b2/m-abc1:q-a1b2/m-def2"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["not_found"]) == 1
        assert len(data["removed"]) == 0

    def test_json_output_errors(self, runner, project_dir):
        result = runner.invoke(main, ["unneed", "--json", "invalid:format"])
        data = json.loads(result.output)
        assert len(data["errors"]) >= 1


# ---------------------------------------------------------------------------
# Cycle detection ignores soft-deleted edges
# ---------------------------------------------------------------------------


class TestCycleDetectionIgnoresSoftDeleted:
    """Cycle detection does not consider soft-deleted dependency edges."""

    def test_unneed_deleted_edge_allows_reverse(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B")
        insert_dependency(project_dir, "q-a1b2/m-abc1", "q-a1b2/m-def2")
        runner.invoke(main, ["unneed", "q-a1b2/m-abc1:q-a1b2/m-def2"])
        result = runner.invoke(main, ["needs", "q-a1b2/m-def2:q-a1b2/m-abc1"])
        assert result.exit_code == 0
        assert "cycle" not in result.output.lower()

    def test_deleted_dependency_insert_allows_add(self, runner, project_dir):
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
# DB API: remove_dependency
# ---------------------------------------------------------------------------


class TestRemoveDependencyDbApi:
    """remove_dependency() DB function returns existence-based result (not format error)."""

    def test_malformed_from_id_returns_not_found(self, project_dir):
        result = remove_dependency(project_dir, "bad", "q-a1b2/m-f3c1")
        assert result == {"removed": False, "not_found": True}

    def test_malformed_to_id_returns_not_found(self, project_dir):
        result = remove_dependency(project_dir, "q-a1b2/m-f3c1", "also-bad")
        assert result == {"removed": False, "not_found": True}

    def test_both_ids_malformed_returns_not_found(self, project_dir):
        result = remove_dependency(project_dir, "bad", "also-bad")
        assert result == {"removed": False, "not_found": True}

    def test_valid_ids_proceed_to_db_lookup(self, project_dir):
        result = remove_dependency(project_dir, "q-a1b2/m-f3c1", "q-a1b2/m-f3d2")
        assert result.get("ok") is not False
        assert "error" not in result

    def test_valid_scoped_id_accepted(self, project_dir):
        result = remove_dependency(project_dir, "q-a1b2/m-f3c1", "q-a1b2/m-f3d2")
        assert result.get("ok") is not False

    def test_valid_standalone_id_accepted(self, project_dir):
        result = remove_dependency(project_dir, "m-f3c1", "q-a1b2/m-f3d2")
        assert result.get("ok") is not False

    def test_no_error_key_for_valid_ids(self, project_dir):
        result = remove_dependency(project_dir, "q-a1b2/m-f3c1", "q-a1b2/m-f3d2")
        assert "error" not in result


# ---------------------------------------------------------------------------
# View dependencies via mission show
# ---------------------------------------------------------------------------


class TestViewDependenciesViaShow:
    """lore show returns needs and blocks in JSON and human output."""

    def test_needs_and_blocks_populated(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M B", "-q", quest_id])
        r3 = runner.invoke(main, ["--json", "new", "mission", "M C", "-q", quest_id])
        m_a = json.loads(r1.output)["id"]
        m_b = json.loads(r2.output)["id"]
        m_c = json.loads(r3.output)["id"]
        runner.invoke(main, ["needs", f"{m_b}:{m_a}"])
        runner.invoke(main, ["needs", f"{m_c}:{m_b}"])

        result = runner.invoke(main, ["--json", "show", m_b])
        assert_exit_ok(result)
        data = json.loads(result.output)
        needs_ids = [d["id"] for d in data["dependencies"]["needs"]]
        blocks_ids = [d["id"] for d in data["dependencies"]["blocks"]]
        assert m_a in needs_ids
        assert m_c in blocks_ids

    def test_dependencies_section_present_in_human_output(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M B", "-q", quest_id])
        m_a = json.loads(r1.output)["id"]
        m_b = json.loads(r2.output)["id"]
        runner.invoke(main, ["needs", f"{m_b}:{m_a}"])
        result = runner.invoke(main, ["show", m_b])
        assert_exit_ok(result)
        assert "Dependencies" in result.output or "Needs" in result.output

    def test_no_dependencies_section_when_none(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id])
        m_a = json.loads(r1.output)["id"]
        result = runner.invoke(main, ["show", m_a])
        assert_exit_ok(result)
        assert "Dependencies:" not in result.output

    def test_needs_subsection_in_human_output(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Prereq B")
        insert_dependency(project_dir, "q-a1b2/m-abc1", "q-a1b2/m-def2")
        result = runner.invoke(main, ["show", "q-a1b2/m-abc1"])
        assert "  Needs:" in result.output

    def test_upstream_title_in_needs(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Design the schema", status="closed",
                       closed_at="2025-01-15T10:00:00Z")
        insert_dependency(project_dir, "q-a1b2/m-abc1", "q-a1b2/m-def2")
        result = runner.invoke(main, ["show", "q-a1b2/m-abc1"])
        assert "Design the schema" in result.output

    def test_dependency_graph_heading_replaced(self, runner, project_dir):
        """Old 'Dependency Graph:' heading is replaced by 'Dependencies:'."""
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Mission B")
        insert_dependency(project_dir, "q-a1b2/m-abc1", "q-a1b2/m-def2")
        result = runner.invoke(main, ["show", "q-a1b2/m-abc1"])
        assert "Dependency Graph:" not in result.output
        assert "Dependencies:" in result.output


# ---------------------------------------------------------------------------
# Quest topological sort
# ---------------------------------------------------------------------------


class TestQuestTopologicalSort:
    """lore show q-xxxx shows missions in topological order."""

    def test_topological_order_in_output(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M B", "-q", quest_id])
        r3 = runner.invoke(main, ["--json", "new", "mission", "M C", "-q", quest_id])
        m_a = json.loads(r1.output)["id"]
        m_b = json.loads(r2.output)["id"]
        m_c = json.loads(r3.output)["id"]
        runner.invoke(main, ["needs", f"{m_b}:{m_a}"])
        runner.invoke(main, ["needs", f"{m_c}:{m_b}"])
        result = runner.invoke(main, ["show", quest_id])
        assert_exit_ok(result)
        out = result.output
        pos_a = out.find("M A")
        pos_b = out.find("M B")
        pos_c = out.find("M C")
        assert pos_a < pos_b < pos_c


# ---------------------------------------------------------------------------
# Invalid ID format in needs
# ---------------------------------------------------------------------------


class TestInvalidIdFormatInNeeds:
    """lore needs with invalid IDs exits 1 with validation error."""

    def test_invalid_ids_rejected(self, runner, project_dir):
        result = runner.invoke(main, ["needs", "notanid:notanid"])
        assert result.exit_code == 1

    def test_error_mentions_format(self, runner, project_dir):
        result = runner.invoke(main, ["needs", "notanid:notanid"])
        combined = result.output + (result.stderr or "")
        assert "invalid" in combined.lower() or "format" in combined.lower() or "not found" in combined.lower()


# ---------------------------------------------------------------------------
# Status symbols in dependency view
# ---------------------------------------------------------------------------


class TestStatusSymbolsInDependencyView:
    """Status symbols in the dependency view reflect mission state."""

    def test_closed_dependency_shows_filled_circle(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(
            project_dir, "q-a1b2/m-def2", "q-a1b2", "Done task",
            status="closed", closed_at="2025-01-15T10:00:00Z",
        )
        insert_dependency(project_dir, "q-a1b2/m-abc1", "q-a1b2/m-def2")
        result = runner.invoke(main, ["show", "q-a1b2/m-abc1"])
        assert "●" in result.output

    def test_open_dependency_shows_empty_circle(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(project_dir, "q-a1b2/m-abc1", "q-a1b2", "Mission A")
        insert_mission(project_dir, "q-a1b2/m-def2", "q-a1b2", "Pending task", status="open")
        insert_dependency(project_dir, "q-a1b2/m-abc1", "q-a1b2/m-def2")
        result = runner.invoke(main, ["show", "q-a1b2/m-abc1"])
        assert "○" in result.output
