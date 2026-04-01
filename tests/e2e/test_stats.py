"""E2E tests for aggregate statistics — lore stats command.

Spec: conceptual-workflows-stats (lore codex show conceptual-workflows-stats)
"""

import json

from lore.cli import main
from tests.conftest import (
    assert_exit_ok,
    insert_mission,
    insert_quest,
)


class TestStatsEmpty:
    """lore stats on an empty project returns all zeros with exit code 0."""

    def test_exit_code_zero(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "stats"])
        assert_exit_ok(result)

    def test_valid_json(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "stats"])
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_quests_key_present(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "stats"])
        data = json.loads(result.output)
        assert "quests" in data

    def test_missions_key_present(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "stats"])
        data = json.loads(result.output)
        assert "missions" in data

    def test_all_quest_counts_zero(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "stats"])
        data = json.loads(result.output)
        quests = data["quests"]
        assert quests["open"] == 0
        assert quests["in_progress"] == 0
        assert quests["closed"] == 0

    def test_all_mission_counts_zero(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "stats"])
        data = json.loads(result.output)
        missions = data["missions"]
        assert missions["open"] == 0
        assert missions["in_progress"] == 0
        assert missions["blocked"] == 0
        assert missions["closed"] == 0

    def test_human_output_shows_stats(self, runner, project_dir):
        result = runner.invoke(main, ["stats"])
        assert_exit_ok(result)
        assert result.output  # non-empty output

    def test_human_output_shows_all_status_labels(self, runner, project_dir):
        result = runner.invoke(main, ["stats"])
        assert_exit_ok(result)
        assert "Quests" in result.output
        assert "Missions" in result.output
        assert "open" in result.output
        assert "closed" in result.output


class TestStatsAccurateCounts:
    """Stats counts match the actual DB state including standalone missions."""

    def _setup(self, project_dir):
        insert_quest(project_dir, "q-aa01", "Open Quest 1", status="open")
        insert_quest(project_dir, "q-aa02", "Open Quest 2", status="open")
        insert_quest(project_dir, "q-aa03", "InProgress Quest", status="in_progress")
        insert_quest(
            project_dir, "q-aa04", "Closed Quest", status="closed",
            closed_at="2025-01-16T09:00:00Z"
        )
        insert_mission(project_dir, "q-aa01/m-0001", "q-aa01", "Open M1", status="open")
        insert_mission(project_dir, "q-aa01/m-0002", "q-aa01", "Open M2", status="open")
        insert_mission(project_dir, "q-aa02/m-0003", "q-aa02", "Open M3", status="open")
        insert_mission(project_dir, "q-aa03/m-0004", "q-aa03", "InProg M", status="in_progress")
        insert_mission(project_dir, "q-aa03/m-0005", "q-aa03", "Blocked M", status="blocked",
                       block_reason="Waiting")
        insert_mission(project_dir, "q-aa04/m-0006", "q-aa04", "Closed M1", status="closed",
                       closed_at="2025-01-16T09:00:00Z")
        insert_mission(project_dir, "q-aa04/m-0007", "q-aa04", "Closed M2", status="closed",
                       closed_at="2025-01-16T09:00:00Z")
        insert_mission(project_dir, "m-s001", None, "Standalone", status="open")

    def test_quest_open_count(self, runner, project_dir):
        self._setup(project_dir)
        result = runner.invoke(main, ["--json", "stats"])
        data = json.loads(result.output)
        assert data["quests"]["open"] == 2

    def test_quest_in_progress_count(self, runner, project_dir):
        self._setup(project_dir)
        result = runner.invoke(main, ["--json", "stats"])
        data = json.loads(result.output)
        assert data["quests"]["in_progress"] == 1

    def test_quest_closed_count(self, runner, project_dir):
        self._setup(project_dir)
        result = runner.invoke(main, ["--json", "stats"])
        data = json.loads(result.output)
        assert data["quests"]["closed"] == 1

    def test_mission_open_count(self, runner, project_dir):
        self._setup(project_dir)
        result = runner.invoke(main, ["--json", "stats"])
        data = json.loads(result.output)
        assert data["missions"]["open"] == 4  # 3 quest + 1 standalone

    def test_mission_in_progress_count(self, runner, project_dir):
        self._setup(project_dir)
        result = runner.invoke(main, ["--json", "stats"])
        data = json.loads(result.output)
        assert data["missions"]["in_progress"] == 1

    def test_mission_blocked_count(self, runner, project_dir):
        self._setup(project_dir)
        result = runner.invoke(main, ["--json", "stats"])
        data = json.loads(result.output)
        assert data["missions"]["blocked"] == 1

    def test_mission_closed_count(self, runner, project_dir):
        self._setup(project_dir)
        result = runner.invoke(main, ["--json", "stats"])
        data = json.loads(result.output)
        assert data["missions"]["closed"] == 2

    def test_human_output_shows_counts(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Open Quest 1", status="open")
        insert_quest(project_dir, "q-bbbb", "Open Quest 2", status="open")
        insert_quest(project_dir, "q-cccc", "IP Quest", status="in_progress")
        insert_quest(project_dir, "q-dddd", "Closed Quest", status="closed",
                     closed_at="2025-01-16T09:00:00Z")
        result = runner.invoke(main, ["stats"])
        assert result.exit_code == 0
        assert "open: 2" in result.output
        assert "in_progress: 1" in result.output
        assert "closed: 1" in result.output


class TestStatsSoftDeletedExcluded:
    """Soft-deleted quests and missions are not counted."""

    def test_soft_deleted_quest_excluded(self, runner, project_dir):
        insert_quest(project_dir, "q-bb01", "Active", status="open")
        insert_quest(
            project_dir, "q-bb02", "Deleted", status="open",
            deleted_at="2025-01-15T10:00:00Z"
        )
        result = runner.invoke(main, ["--json", "stats"])
        data = json.loads(result.output)
        assert data["quests"]["open"] == 1

    def test_soft_deleted_mission_excluded(self, runner, project_dir):
        insert_quest(project_dir, "q-cc01", "Q", status="open")
        insert_mission(project_dir, "q-cc01/m-0001", "q-cc01", "Active M", status="open")
        insert_mission(
            project_dir, "q-cc01/m-0002", "q-cc01", "Deleted M", status="open",
            deleted_at="2025-01-15T10:00:00Z"
        )
        result = runner.invoke(main, ["--json", "stats"])
        data = json.loads(result.output)
        assert data["missions"]["open"] == 1

    def test_deleted_not_in_any_count(self, runner, project_dir):
        insert_quest(
            project_dir, "q-dd01", "Deleted Quest", status="open",
            deleted_at="2025-01-15T10:00:00Z"
        )
        insert_mission(
            project_dir, "m-d001", None, "Deleted Mission", status="open",
            deleted_at="2025-01-15T10:00:00Z"
        )
        result = runner.invoke(main, ["--json", "stats"])
        data = json.loads(result.output)
        total_quests = sum(data["quests"].values())
        total_missions = sum(data["missions"].values())
        assert total_quests == 0
        assert total_missions == 0
