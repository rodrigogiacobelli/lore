"""E2E tests for the ready queue — lore ready command.

Spec: conceptual-workflows-ready (lore codex show conceptual-workflows-ready)
"""

import json

from lore.cli import main
from tests.conftest import (
    assert_exit_ok,
    insert_mission,
    insert_quest,
)


class TestReadyHighestPriority:
    """lore ready returns the highest-priority (lowest numeric) unblocked open mission."""

    def test_returns_priority_zero_mission(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "High P", "-q", quest_id, "-p", "0"])
        runner.invoke(main, ["--json", "new", "mission", "Mid P", "-q", quest_id, "-p", "2"])
        runner.invoke(main, ["--json", "new", "mission", "Low P", "-q", quest_id, "-p", "4"])
        m_high = json.loads(r1.output)["id"]
        result = runner.invoke(main, ["--json", "ready"])
        assert_exit_ok(result)
        data = json.loads(result.output)
        assert "missions" in data
        assert len(data["missions"]) == 1
        assert data["missions"][0]["id"] == m_high

    def test_json_shape(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        runner.invoke(main, ["new", "mission", "M", "-q", quest_id])
        result = runner.invoke(main, ["--json", "ready"])
        data = json.loads(result.output)
        assert "missions" in data
        assert isinstance(data["missions"], list)


class TestReadyExcludesBlocked:
    """Blocked missions do not appear in the ready queue."""

    def test_blocked_excluded(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "P0 Blocked", "-q", quest_id, "-p", "0"])
        r2 = runner.invoke(main, ["--json", "new", "mission", "P2 Open", "-q", quest_id, "-p", "2"])
        m_blocked = json.loads(r1.output)["id"]
        m_open = json.loads(r2.output)["id"]
        runner.invoke(main, ["claim", m_blocked])
        runner.invoke(main, ["block", m_blocked, "External dep"])
        result = runner.invoke(main, ["--json", "ready"])
        data = json.loads(result.output)
        ids = [m["id"] for m in data["missions"]]
        assert m_blocked not in ids
        assert m_open in ids


class TestReadyExcludesUnresolvedDeps:
    """Missions with unresolved dependencies are excluded; they re-enter when deps close."""

    def test_dep_excluded_before_close(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id, "-p", "1"])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M B", "-q", quest_id, "-p", "0"])
        r3 = runner.invoke(main, ["--json", "new", "mission", "M C", "-q", quest_id, "-p", "1"])
        m_a = json.loads(r1.output)["id"]
        m_b = json.loads(r2.output)["id"]
        m_c = json.loads(r3.output)["id"]
        runner.invoke(main, ["needs", f"{m_b}:{m_a}"])  # B (p0) needs A
        result = runner.invoke(main, ["--json", "ready", "10"])
        ids = [m["id"] for m in json.loads(result.output)["missions"]]
        assert m_b not in ids
        assert m_a in ids
        assert m_c in ids

    def test_dep_eligible_after_close(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id, "-p", "1"])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M B", "-q", quest_id, "-p", "0"])
        m_a = json.loads(r1.output)["id"]
        m_b = json.loads(r2.output)["id"]
        runner.invoke(main, ["needs", f"{m_b}:{m_a}"])
        runner.invoke(main, ["done", m_a])
        result = runner.invoke(main, ["--json", "ready", "10"])
        ids = [m["id"] for m in json.loads(result.output)["missions"]]
        assert m_b in ids


class TestReadyCountArgument:
    """The optional count argument limits and sorts the returned missions."""

    def test_returns_exactly_n(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        for i in range(5):
            runner.invoke(main, ["new", "mission", f"M{i}", "-q", quest_id, "-p", str(i % 5)])
        result = runner.invoke(main, ["--json", "ready", "3"])
        assert_exit_ok(result)
        data = json.loads(result.output)
        assert len(data["missions"]) == 3

    def test_sorted_by_priority(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        for i in range(5):
            runner.invoke(main, ["new", "mission", f"M{i}", "-q", quest_id, "-p", str(i % 5)])
        result = runner.invoke(main, ["--json", "ready", "3"])
        data = json.loads(result.output)
        priorities = [m["priority"] for m in data["missions"]]
        assert priorities == sorted(priorities)

    def test_limits_results(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        for i, (mid, pri) in enumerate([
            ("q-a1b2/m-aaa1", 0), ("q-a1b2/m-bbb2", 1),
            ("q-a1b2/m-ccc3", 2), ("q-a1b2/m-ddd4", 3),
        ]):
            insert_mission(
                project_dir, mid, "q-a1b2", f"M{i}", priority=pri,
                created_at=f"2025-01-15T09:0{i}:00Z",
                updated_at=f"2025-01-15T09:0{i}:00Z",
            )
        result = runner.invoke(main, ["ready", "2"])
        assert "q-a1b2/m-aaa1" in result.output
        assert "q-a1b2/m-bbb2" in result.output
        assert "q-a1b2/m-ccc3" not in result.output
        assert "q-a1b2/m-ddd4" not in result.output


class TestReadyExcludesInProgress:
    """in_progress missions do not appear in the ready queue."""

    def test_in_progress_excluded(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        r1 = runner.invoke(main, ["--json", "new", "mission", "M A", "-q", quest_id])
        r2 = runner.invoke(main, ["--json", "new", "mission", "M B", "-q", quest_id])
        m_a = json.loads(r1.output)["id"]
        m_b = json.loads(r2.output)["id"]
        runner.invoke(main, ["claim", m_a])
        result = runner.invoke(main, ["--json", "ready", "10"])
        ids = [m["id"] for m in json.loads(result.output)["missions"]]
        assert m_a not in ids
        assert m_b in ids


class TestReadyEmptyQueue:
    """Empty queue returns empty mission list and exit code 0."""

    def test_empty_queue_json(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "ready"])
        assert_exit_ok(result)
        data = json.loads(result.output)
        assert data == {"missions": []}

    def test_empty_queue_human_output(self, runner, project_dir):
        result = runner.invoke(main, ["ready"])
        assert_exit_ok(result)
        assert "no missions" in result.output.lower() or "ready" in result.output.lower()


class TestReadyTieBreakingByCreatedAt:
    """Within the same priority, older missions (earlier created_at) are returned first."""

    def test_earlier_created_first(self, runner, project_dir):
        insert_quest(project_dir, "q-aaa1", "Q")
        insert_mission(
            project_dir, "q-aaa1/m-m001", "q-aaa1", "Earlier",
            priority=1,
            created_at="2025-01-10T09:00:00Z",
            updated_at="2025-01-10T09:00:00Z",
        )
        insert_mission(
            project_dir, "q-aaa1/m-m002", "q-aaa1", "Later",
            priority=1,
            created_at="2025-01-11T09:00:00Z",
            updated_at="2025-01-11T09:00:00Z",
        )
        result = runner.invoke(main, ["--json", "ready", "2"])
        assert_exit_ok(result)
        data = json.loads(result.output)
        assert len(data["missions"]) == 2
        assert data["missions"][0]["id"] == "q-aaa1/m-m001"
        assert data["missions"][1]["id"] == "q-aaa1/m-m002"

    def test_sorted_globally_by_priority_then_created_at(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest A")
        insert_quest(project_dir, "q-b2c3", "Quest B")
        insert_mission(
            project_dir, "q-a1b2/m-aaa1", "q-a1b2", "Quest A P2",
            priority=2, created_at="2025-01-15T09:00:00Z", updated_at="2025-01-15T09:00:00Z",
        )
        insert_mission(
            project_dir, "q-b2c3/m-bbb2", "q-b2c3", "Quest B P0",
            priority=0, created_at="2025-01-15T09:01:00Z", updated_at="2025-01-15T09:01:00Z",
        )
        insert_mission(
            project_dir, "m-ccc3", None, "Standalone P1",
            priority=1, created_at="2025-01-15T09:02:00Z", updated_at="2025-01-15T09:02:00Z",
        )
        result = runner.invoke(main, ["ready", "10"])
        output = result.output
        pos_p0 = output.index("q-b2c3/m-bbb2")
        pos_p1 = output.index("m-ccc3")
        pos_p2 = output.index("q-a1b2/m-aaa1")
        assert pos_p0 < pos_p1 < pos_p2


class TestReadyMissionTypeDisplay:
    """mission_type is displayed in ready output; null type shows no bracket."""

    def test_typed_mission_shows_bracket(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        runner.invoke(main, ["--json", "new", "mission", "Sprint M", "-q", quest_id, "-T", "sprint"])
        runner.invoke(main, ["new", "mission", "Normal M", "-q", quest_id])
        result = runner.invoke(main, ["ready", "2"])
        assert_exit_ok(result)
        assert "[sprint]" in result.output

    def test_null_type_mission_no_bracket(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        runner.invoke(main, ["new", "mission", "Normal M", "-q", quest_id])
        result = runner.invoke(main, ["ready"])
        assert_exit_ok(result)
        lines = result.output.split("\n")
        for line in lines:
            if "Normal M" in line:
                assert "[sprint]" not in line


class TestReadyDependencyFiltering:
    """Missions with open/in_progress/blocked dependencies do not appear in ready."""

    def test_open_dependency_excludes_mission(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-abc1", "q-a1b2", "Blocked By Dep",
            priority=0, created_at="2025-01-15T09:00:00Z", updated_at="2025-01-15T09:00:00Z",
        )
        insert_mission(
            project_dir, "q-a1b2/m-def2", "q-a1b2", "The Dependency",
            priority=2, created_at="2025-01-15T09:01:00Z", updated_at="2025-01-15T09:01:00Z",
        )
        from tests.conftest import insert_dependency
        insert_dependency(project_dir, "q-a1b2/m-abc1", "q-a1b2/m-def2")
        result = runner.invoke(main, ["ready", "10"])
        assert "q-a1b2/m-abc1" not in result.output
        assert "q-a1b2/m-def2" in result.output

    def test_closed_dependency_allows_mission(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-abc1", "q-a1b2", "Ready After Dep",
            priority=0, created_at="2025-01-15T09:00:00Z", updated_at="2025-01-15T09:00:00Z",
        )
        insert_mission(
            project_dir, "q-a1b2/m-def2", "q-a1b2", "Closed Dep",
            status="closed", priority=2,
            created_at="2025-01-15T09:01:00Z", updated_at="2025-01-15T09:01:00Z",
        )
        from tests.conftest import insert_dependency
        insert_dependency(project_dir, "q-a1b2/m-abc1", "q-a1b2/m-def2")
        result = runner.invoke(main, ["ready"])
        assert "q-a1b2/m-abc1" in result.output

    def test_only_open_status_eligible(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Test Quest")
        insert_mission(
            project_dir, "q-a1b2/m-ip01", "q-a1b2", "In Progress",
            status="in_progress", priority=0,
            created_at="2025-01-15T09:00:00Z", updated_at="2025-01-15T09:00:00Z",
        )
        insert_mission(
            project_dir, "q-a1b2/m-blk1", "q-a1b2", "Blocked",
            status="blocked", priority=0, block_reason="Waiting",
            created_at="2025-01-15T09:01:00Z", updated_at="2025-01-15T09:01:00Z",
        )
        insert_mission(
            project_dir, "q-a1b2/m-cls1", "q-a1b2", "Closed",
            status="closed", priority=0,
            created_at="2025-01-15T09:02:00Z", updated_at="2025-01-15T09:02:00Z",
        )
        insert_mission(
            project_dir, "q-a1b2/m-opn1", "q-a1b2", "Open",
            status="open", priority=2,
            created_at="2025-01-15T09:03:00Z", updated_at="2025-01-15T09:03:00Z",
        )
        result = runner.invoke(main, ["ready", "10"])
        assert "q-a1b2/m-opn1" in result.output
        assert "q-a1b2/m-ip01" not in result.output
        assert "q-a1b2/m-blk1" not in result.output
        assert "q-a1b2/m-cls1" not in result.output

    def test_cross_quest_all_included(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Quest A")
        insert_quest(project_dir, "q-b2c3", "Quest B")
        insert_mission(
            project_dir, "q-a1b2/m-aaa1", "q-a1b2", "Quest A Mission",
            priority=1, created_at="2025-01-15T09:00:00Z", updated_at="2025-01-15T09:00:00Z",
        )
        insert_mission(
            project_dir, "q-b2c3/m-bbb2", "q-b2c3", "Quest B Mission",
            priority=2, created_at="2025-01-15T09:01:00Z", updated_at="2025-01-15T09:01:00Z",
        )
        insert_mission(
            project_dir, "m-ccc3", None, "Standalone Mission",
            priority=0, created_at="2025-01-15T09:02:00Z", updated_at="2025-01-15T09:02:00Z",
        )
        result = runner.invoke(main, ["ready", "10"])
        assert "q-a1b2/m-aaa1" in result.output
        assert "q-b2c3/m-bbb2" in result.output
        assert "m-ccc3" in result.output
