"""E2E tests for report generation — lore oracle command.

Spec: conceptual-workflows-oracle (lore codex show conceptual-workflows-oracle)
"""

import json

from lore.cli import main
from tests.conftest import (
    assert_exit_ok,
    db_conn,
    insert_mission,
    insert_quest,
)


# ---------------------------------------------------------------------------
# Helpers for direct DB setup (used in oracle tests that need specific metadata)
# ---------------------------------------------------------------------------


def _create_quest_direct(project_dir, quest_id, title, status="open", priority=2, description=""):
    conn = db_conn(project_dir)
    conn.execute(
        "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at, closed_at) "
        "VALUES (?, ?, ?, ?, ?, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z', ?)",
        (quest_id, title, description, status, priority,
         "2025-01-15T10:00:00Z" if status == "closed" else None),
    )
    conn.commit()
    conn.close()


def _create_mission_direct(project_dir, mission_id, quest_id, title, status="open",
                           priority=2, knight=None, description="", block_reason=None,
                           mission_type=None):
    conn = db_conn(project_dir)
    conn.execute(
        "INSERT INTO missions (id, quest_id, title, description, status, priority, knight, "
        "block_reason, mission_type, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')",
        (mission_id, quest_id, title, description, status, priority, knight, block_reason, mission_type),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Directory and file structure
# ---------------------------------------------------------------------------


class TestOracleGeneratesFiles:
    """lore oracle creates .lore/reports/ with the expected directory structure."""

    def _setup(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Build Payment Module"])
        quest_id = json.loads(r.output)["id"]
        r2 = runner.invoke(main, ["--json", "new", "mission", "Design schema", "-q", quest_id])
        m1_id = json.loads(r2.output)["id"]
        r3 = runner.invoke(main, ["--json", "new", "mission", "Implement API", "-q", quest_id])
        m2_id = json.loads(r3.output)["id"]
        runner.invoke(main, ["done", m1_id])
        return quest_id, m1_id, m2_id

    def test_exit_code_zero(self, runner, project_dir):
        self._setup(runner, project_dir)
        result = runner.invoke(main, ["oracle"])
        assert_exit_ok(result)

    def test_reports_dir_exists(self, runner, project_dir):
        self._setup(runner, project_dir)
        runner.invoke(main, ["oracle"])
        assert (project_dir / ".lore" / "reports").is_dir()

    def test_summary_md_exists(self, runner, project_dir):
        self._setup(runner, project_dir)
        runner.invoke(main, ["oracle"])
        assert (project_dir / ".lore" / "reports" / "summary.md").is_file()

    def test_quests_dir_exists(self, runner, project_dir):
        self._setup(runner, project_dir)
        runner.invoke(main, ["oracle"])
        assert (project_dir / ".lore" / "reports" / "quests").is_dir()

    def test_quest_subdir_exists(self, runner, project_dir):
        self._setup(runner, project_dir)
        runner.invoke(main, ["oracle"])
        quest_dirs = list((project_dir / ".lore" / "reports" / "quests").iterdir())
        assert len(quest_dirs) >= 1

    def test_index_md_in_quest_dir(self, runner, project_dir):
        self._setup(runner, project_dir)
        runner.invoke(main, ["oracle"])
        quest_dirs = list((project_dir / ".lore" / "reports" / "quests").iterdir())
        assert any((d / "index.md").is_file() for d in quest_dirs)

    def test_per_mission_md_files_exist(self, runner, project_dir):
        self._setup(runner, project_dir)
        runner.invoke(main, ["oracle"])
        quest_dirs = list((project_dir / ".lore" / "reports" / "quests").iterdir())
        assert len(quest_dirs) >= 1
        md_files = [f for f in quest_dirs[0].iterdir() if f.name != "index.md"]
        assert len(md_files) >= 1

    def test_output_confirms_generation(self, runner, project_dir):
        self._setup(runner, project_dir)
        result = runner.invoke(main, ["oracle"])
        assert "reports" in result.output.lower() or "generated" in result.output.lower()


class TestOracleReportContents:
    """Oracle report files contain correct content reflecting DB state."""

    def _setup(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Build Payment Module"])
        quest_id = json.loads(r.output)["id"]
        r2 = runner.invoke(main, ["--json", "new", "mission", "Design schema", "-q", quest_id])
        m1_id = json.loads(r2.output)["id"]
        r3 = runner.invoke(main, ["--json", "new", "mission", "Implement API", "-q", quest_id])
        m2_id = json.loads(r3.output)["id"]
        runner.invoke(main, ["claim", m2_id])
        runner.invoke(main, ["block", m2_id, "Waiting on API key"])
        runner.invoke(main, ["--json", "new", "mission", "Write tests", "-q", quest_id])
        runner.invoke(main, ["oracle"])
        return quest_id, m1_id, m2_id

    def _quest_dir(self, project_dir):
        return list((project_dir / ".lore" / "reports" / "quests").iterdir())[0]

    def test_quest_index_mentions_title(self, runner, project_dir):
        self._setup(runner, project_dir)
        index = (self._quest_dir(project_dir) / "index.md").read_text()
        assert "Build Payment Module" in index

    def test_quest_index_mentions_all_missions(self, runner, project_dir):
        self._setup(runner, project_dir)
        index = (self._quest_dir(project_dir) / "index.md").read_text()
        assert "Design schema" in index
        assert "Implement API" in index
        assert "Write tests" in index

    def test_blocked_mission_file_contains_block_reason(self, runner, project_dir):
        self._setup(runner, project_dir)
        quest_dir = self._quest_dir(project_dir)
        blocked_file = next(
            (f for f in quest_dir.glob("*.md") if "implement" in f.name.lower()), None
        )
        assert blocked_file is not None
        content = blocked_file.read_text()
        assert "Waiting on API key" in content

    def test_blocked_mission_file_reflects_status(self, runner, project_dir):
        self._setup(runner, project_dir)
        quest_dir = self._quest_dir(project_dir)
        blocked_file = next(
            (f for f in quest_dir.glob("*.md") if "implement" in f.name.lower()), None
        )
        assert blocked_file is not None
        content = blocked_file.read_text()
        assert "blocked" in content


class TestOracleWipeAndRecreate:
    """Oracle wipes and recreates reports on every run — no stale files persist."""

    def test_stale_files_replaced(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        rm = runner.invoke(main, ["--json", "new", "mission", "Task", "-q", quest_id])
        m_id = json.loads(rm.output)["id"]
        runner.invoke(main, ["oracle"])
        first_summary = (project_dir / ".lore" / "reports" / "summary.md").read_text()
        assert "open | 1" in first_summary

        runner.invoke(main, ["done", m_id])
        runner.invoke(main, ["oracle"])
        second_summary = (project_dir / ".lore" / "reports" / "summary.md").read_text()
        assert "closed | 1" in second_summary

    def test_exit_code_zero_second_run(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(r.output)["id"]
        runner.invoke(main, ["oracle"])
        result = runner.invoke(main, ["oracle"])
        assert_exit_ok(result)


class TestOracleEmptyProject:
    """Oracle runs cleanly on an empty project."""

    def test_exit_code_zero(self, runner, project_dir):
        result = runner.invoke(main, ["oracle"])
        assert_exit_ok(result)

    def test_summary_md_exists(self, runner, project_dir):
        runner.invoke(main, ["oracle"])
        assert (project_dir / ".lore" / "reports" / "summary.md").is_file()

    def test_summary_shows_zero_counts(self, runner, project_dir):
        runner.invoke(main, ["oracle"])
        summary = (project_dir / ".lore" / "reports" / "summary.md").read_text()
        assert "0" in summary


class TestOracleStandaloneMissions:
    """Oracle handles standalone missions (no quest) without crashing."""

    def test_exit_code_zero_with_standalone(self, runner, project_dir):
        runner.invoke(main, ["--json", "new", "mission", "Fix a bug"])
        result = runner.invoke(main, ["oracle"])
        assert_exit_ok(result)

    def test_summary_includes_standalone_in_mission_count(self, runner, project_dir):
        runner.invoke(main, ["--json", "new", "mission", "Fix a bug"])
        runner.invoke(main, ["oracle"])
        summary = (project_dir / ".lore" / "reports" / "summary.md").read_text()
        assert "open | 1" in summary

    def test_oracle_with_quest_and_standalone(self, runner, project_dir):
        rq = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(rq.output)["id"]
        runner.invoke(main, ["--json", "new", "mission", "Quest mission", "-q", quest_id])
        runner.invoke(main, ["--json", "new", "mission", "Standalone"])
        result = runner.invoke(main, ["oracle"])
        assert_exit_ok(result)


class TestOracleSlugification:
    """Oracle slugifies quest/mission titles correctly for directory and file names."""

    def test_special_chars_slugified_in_dirname(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "Feature: OAuth 2.0 (v2)"])
        quest_id = json.loads(r.output)["id"]
        runner.invoke(main, ["--json", "new", "mission", "M1", "-q", quest_id])
        runner.invoke(main, ["oracle"])
        quest_dirs = list((project_dir / ".lore" / "reports" / "quests").iterdir())
        assert len(quest_dirs) == 1
        dir_name = quest_dirs[0].name
        assert quest_id in dir_name
        assert ":" not in dir_name
        assert "(" not in dir_name
        assert ")" not in dir_name
        assert " " not in dir_name

    def test_slugified_name_uses_hyphens(self, runner, project_dir):
        r = runner.invoke(main, ["--json", "new", "quest", "My Quest Title"])
        quest_id = json.loads(r.output)["id"]
        runner.invoke(main, ["--json", "new", "mission", "Step one", "-q", quest_id])
        runner.invoke(main, ["oracle"])
        quest_dirs = list((project_dir / ".lore" / "reports" / "quests").iterdir())
        dir_name = quest_dirs[0].name
        assert "-my-quest-title" in dir_name or "my-quest-title" in dir_name


class TestOracleMissionTypeInReports:
    """Oracle includes mission_type in per-mission report files and quest index tables."""

    def test_mission_file_has_type_line(self, runner, project_dir):
        _create_quest_direct(project_dir, "q-aaaa", "Quest Alpha")
        _create_mission_direct(project_dir, "q-aaaa/m-aa01", "q-aaaa", "Mission One",
                               mission_type="human")
        result = runner.invoke(main, ["oracle"])
        assert result.exit_code == 0
        quest_dir = list((project_dir / ".lore" / "reports" / "quests").iterdir())[0]
        mission_files = [f for f in quest_dir.iterdir() if f.name != "index.md"]
        content = mission_files[0].read_text()
        assert "**Type:** human" in content

    def test_quest_index_has_type_column(self, runner, project_dir):
        _create_quest_direct(project_dir, "q-aaaa", "Quest Alpha")
        _create_mission_direct(project_dir, "q-aaaa/m-aa01", "q-aaaa", "Mission One",
                               mission_type="knight")
        result = runner.invoke(main, ["oracle"])
        assert result.exit_code == 0
        quest_dir = list((project_dir / ".lore" / "reports" / "quests").iterdir())[0]
        content = (quest_dir / "index.md").read_text()
        assert "| Type |" in content

    def test_null_mission_type_does_not_crash(self, runner, project_dir):
        _create_quest_direct(project_dir, "q-aaaa", "Quest Alpha")
        _create_mission_direct(project_dir, "q-aaaa/m-aa01", "q-aaaa", "Mission One",
                               mission_type=None)
        result = runner.invoke(main, ["oracle"])
        assert result.exit_code == 0

    def test_standalone_mission_file_has_type_line(self, runner, project_dir):
        _create_mission_direct(project_dir, "m-bb01", None, "Standalone Fix",
                               mission_type="constable")
        result = runner.invoke(main, ["oracle"])
        assert result.exit_code == 0
        missions_dir = project_dir / ".lore" / "reports" / "missions"
        files = list(missions_dir.iterdir())
        assert len(files) == 1
        content = files[0].read_text()
        assert "**Type:** constable" in content
