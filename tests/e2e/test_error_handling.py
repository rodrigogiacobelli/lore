"""E2E tests for CLI error handling — exit codes, stderr routing, and error formats.

Spec: conceptual-workflows-error-handling (lore codex show conceptual-workflows-error-handling)
"""

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from lore.cli import main
from tests.conftest import (
    assert_exit_err,
    assert_exit_ok,
    db_conn,
    insert_mission,
    insert_quest,
)


# ---------------------------------------------------------------------------
# Helpers (module-level, not fixtures)
# ---------------------------------------------------------------------------


def _create_quest_direct(project_dir, quest_id, title, status="open", priority=2):
    conn = db_conn(project_dir)
    conn.execute(
        "INSERT INTO quests (id, title, description, status, priority, created_at, updated_at, closed_at) "
        "VALUES (?, ?, '', ?, ?, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z', ?)",
        (quest_id, title, status, priority,
         "2025-01-15T10:00:00Z" if status == "closed" else None),
    )
    conn.commit()
    conn.close()


def _create_mission_direct(project_dir, mission_id, quest_id, title, status="open", priority=2):
    conn = db_conn(project_dir)
    conn.execute(
        "INSERT INTO missions (id, quest_id, title, description, status, priority, created_at, updated_at) "
        "VALUES (?, ?, ?, '', ?, ?, '2025-01-15T09:30:00Z', '2025-01-15T09:30:00Z')",
        (mission_id, quest_id, title, status, priority),
    )
    conn.commit()
    conn.close()


def _create_dependency(project_dir, from_id, to_id):
    conn = db_conn(project_dir)
    conn.execute(
        "INSERT INTO dependencies (from_id, to_id, type) VALUES (?, ?, 'blocks')",
        (from_id, to_id),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Non-existent entity errors — exit codes and error messages
# ---------------------------------------------------------------------------


class TestShowNonExistentQuest:
    """lore show q-zzzz exits 1 when quest does not exist."""

    def test_exit_code_one(self, runner, project_dir):
        result = runner.invoke(main, ["show", "q-zzzz"])
        assert_exit_err(result, 1)

    def test_error_message_not_found(self, runner, project_dir):
        result = runner.invoke(main, ["show", "q-zzzz"])
        assert "not found" in result.output.lower() or "q-zzzz" in result.output

    def test_json_error_shape(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "show", "q-zzzz"])
        data = json.loads(result.output)
        assert "error" in data


class TestShowNonExistentMission:
    """lore show q-xxxx/m-zzzz exits 1 when mission does not exist."""

    def test_exit_code_one(self, runner, project_dir):
        result = runner.invoke(main, ["show", "q-xxxx/m-zzzz"])
        assert_exit_err(result, 1)

    def test_error_message_not_found(self, runner, project_dir):
        result = runner.invoke(main, ["show", "q-xxxx/m-zzzz"])
        assert "not found" in result.output.lower() or "m-zzzz" in result.output

    def test_json_error_shape(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "show", "q-xxxx/m-zzzz"])
        data = json.loads(result.output)
        assert "error" in data


class TestClaimNonExistentMission:
    """lore claim q-xxxx/m-zzzz exits 1 when mission does not exist."""

    def test_exit_code_one(self, runner, project_dir):
        result = runner.invoke(main, ["claim", "q-xxxx/m-zzzz"])
        assert_exit_err(result, 1)

    def test_error_in_output(self, runner, project_dir):
        result = runner.invoke(main, ["claim", "q-xxxx/m-zzzz"])
        assert result.output.strip()

    def test_json_errors_array(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "claim", "q-xxxx/m-zzzz"])
        data = json.loads(result.output)
        assert "errors" in data
        assert len(data["errors"]) >= 1


class TestBlockNonExistentMission:
    """lore block q-xxxx/m-zzzz exits 1 when mission does not exist."""

    def test_exit_code_one(self, runner, project_dir):
        result = runner.invoke(main, ["block", "q-xxxx/m-zzzz", "reason"])
        assert_exit_err(result, 1)

    def test_error_message(self, runner, project_dir):
        result = runner.invoke(main, ["block", "q-xxxx/m-zzzz", "reason"])
        assert "not found" in result.output.lower() or "m-zzzz" in result.output


# ---------------------------------------------------------------------------
# Exit code 0 on success
# ---------------------------------------------------------------------------


class TestExitCodeZeroOnSuccess:
    """Valid commands return exit code 0."""

    def test_list_returns_zero(self, runner, project_dir):
        result = runner.invoke(main, ["list"])
        assert result.exit_code == 0

    def test_stats_returns_zero(self, runner, project_dir):
        result = runner.invoke(main, ["stats"])
        assert result.exit_code == 0

    def test_dashboard_returns_zero(self, runner, project_dir):
        result = runner.invoke(main, [])
        assert result.exit_code == 0

    def test_new_quest_returns_zero(self, runner, project_dir):
        result = runner.invoke(main, ["new", "quest", "Test Quest"])
        assert result.exit_code == 0

    def test_show_quest_returns_zero(self, runner, project_dir):
        _create_quest_direct(project_dir, "q-abcd", "Test Quest")
        result = runner.invoke(main, ["show", "q-abcd"])
        assert result.exit_code == 0

    def test_claim_returns_zero(self, runner, project_dir):
        _create_quest_direct(project_dir, "q-abcd", "Test Quest")
        _create_mission_direct(project_dir, "q-abcd/m-ef01", "q-abcd", "Test Mission")
        result = runner.invoke(main, ["claim", "q-abcd/m-ef01"])
        assert result.exit_code == 0

    def test_done_returns_zero(self, runner, project_dir):
        _create_quest_direct(project_dir, "q-abcd", "Test Quest")
        _create_mission_direct(project_dir, "q-abcd/m-ef01", "q-abcd", "Test Mission", status="in_progress")
        result = runner.invoke(main, ["done", "q-abcd/m-ef01"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Exit code 1 on application error
# ---------------------------------------------------------------------------


class TestExitCodeOneOnAppError:
    """Nonexistent entities return exit code 1 with error to stderr."""

    def test_show_nonexistent_quest(self, runner, project_dir):
        result = runner.invoke(main, ["show", "q-dead"])
        assert result.exit_code == 1

    def test_show_nonexistent_mission(self, runner, project_dir):
        result = runner.invoke(main, ["show", "m-dead"])
        assert result.exit_code == 1

    def test_claim_nonexistent_mission(self, runner, project_dir):
        result = runner.invoke(main, ["claim", "m-dead"])
        assert result.exit_code == 1

    def test_done_nonexistent_mission(self, runner, project_dir):
        result = runner.invoke(main, ["done", "m-dead"])
        assert result.exit_code == 1

    def test_block_nonexistent_mission(self, runner, project_dir):
        result = runner.invoke(main, ["block", "m-dead", "some reason"])
        assert result.exit_code == 1

    def test_unblock_nonexistent_mission(self, runner, project_dir):
        result = runner.invoke(main, ["unblock", "m-dead"])
        assert result.exit_code == 1

    def test_missions_nonexistent_quest(self, runner, project_dir):
        result = runner.invoke(main, ["missions", "q-dead"])
        assert result.exit_code == 1

    def test_knight_show_nonexistent(self, runner, project_dir):
        result = runner.invoke(main, ["knight", "show", "nonexistent"])
        assert result.exit_code == 1

    def test_doctrine_show_nonexistent(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "show", "nonexistent"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Exit code 2 on CLI usage error
# ---------------------------------------------------------------------------


class TestExitCodeTwoOnUsageError:
    """Wrong arguments produce Click exit code 2."""

    def test_new_quest_missing_title(self, runner, project_dir):
        result = runner.invoke(main, ["new", "quest"])
        assert result.exit_code == 2

    def test_new_mission_missing_title(self, runner, project_dir):
        result = runner.invoke(main, ["new", "mission"])
        assert result.exit_code == 2

    def test_block_missing_reason(self, runner, project_dir):
        result = runner.invoke(main, ["block", "m-abcd"])
        assert result.exit_code == 2

    def test_claim_no_args(self, runner, project_dir):
        result = runner.invoke(main, ["claim"])
        assert result.exit_code == 2

    def test_done_no_args(self, runner, project_dir):
        result = runner.invoke(main, ["done"])
        assert result.exit_code == 2

    def test_unknown_subcommand(self, runner, project_dir):
        result = runner.invoke(main, ["nonexistent-command"])
        assert result.exit_code == 2

    def test_show_missing_id(self, runner, project_dir):
        result = runner.invoke(main, ["show"])
        assert result.exit_code == 2


# ---------------------------------------------------------------------------
# Errors to stderr (not stdout)
# ---------------------------------------------------------------------------


class TestErrorsToStderr:
    """Error messages go to stderr, not stdout."""

    def test_show_nonexistent_quest_error_on_stderr(self, runner, project_dir):
        result = runner.invoke(main, ["show", "q-dead"])
        assert result.exit_code == 1
        assert result.stdout == ""
        assert "not found" in result.stderr

    def test_show_nonexistent_mission_error_on_stderr(self, runner, project_dir):
        result = runner.invoke(main, ["show", "m-dead"])
        assert result.exit_code == 1
        assert result.stdout == ""
        assert "not found" in result.stderr

    def test_claim_nonexistent_error_on_stderr(self, runner, project_dir):
        result = runner.invoke(main, ["claim", "m-dead"])
        assert result.exit_code == 1
        assert result.stdout == ""
        assert "not found" in result.stderr

    def test_done_nonexistent_error_on_stderr(self, runner, project_dir):
        result = runner.invoke(main, ["done", "m-dead"])
        assert result.exit_code == 1
        assert result.stdout == ""
        assert "not found" in result.stderr

    def test_block_nonexistent_error_on_stderr(self, runner, project_dir):
        result = runner.invoke(main, ["block", "m-dead", "reason"])
        assert result.exit_code == 1
        assert result.stdout == ""
        assert "not found" in result.stderr

    def test_unblock_nonexistent_error_on_stderr(self, runner, project_dir):
        result = runner.invoke(main, ["unblock", "m-dead"])
        assert result.exit_code == 1
        assert result.stdout == ""
        assert "not found" in result.stderr

    def test_project_not_found_error_on_stderr(self, tmp_path, monkeypatch):
        """When no .lore project exists, error should go to stderr."""
        monkeypatch.chdir(tmp_path)
        r = CliRunner()
        result = r.invoke(main, ["list"])
        assert result.exit_code == 1
        assert result.stdout == ""
        assert result.stderr != ""

    def test_invalid_status_transition_error_on_stderr(self, runner, project_dir):
        """Claiming a closed mission should put the error on stderr."""
        _create_quest_direct(project_dir, "q-abcd", "Quest")
        _create_mission_direct(project_dir, "q-abcd/m-ef01", "q-abcd", "Mission", status="closed")
        result = runner.invoke(main, ["claim", "q-abcd/m-ef01"])
        assert result.exit_code == 1
        assert result.stdout == ""
        assert "Cannot claim" in result.stderr


# ---------------------------------------------------------------------------
# JSON error format
# ---------------------------------------------------------------------------


class TestJsonErrorFormat:
    """--json errors produce {"error": "..."} on stderr."""

    def test_show_nonexistent_quest_json_error(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "show", "q-dead"])
        assert result.exit_code == 1
        error_data = json.loads(result.stderr)
        assert "error" in error_data
        assert "not found" in error_data["error"]
        assert result.stdout == ""

    def test_show_nonexistent_mission_json_error(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "show", "m-dead"])
        assert result.exit_code == 1
        error_data = json.loads(result.stderr)
        assert "error" in error_data
        assert "not found" in error_data["error"]

    def test_claim_nonexistent_json_error(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "claim", "m-dead"])
        assert result.exit_code == 1
        assert result.stdout == "" or "error" in result.stdout

    def test_knight_show_nonexistent_json_error(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "knight", "show", "nonexistent"])
        assert result.exit_code == 1
        error_data = json.loads(result.stderr)
        assert "error" in error_data

    def test_doctrine_show_nonexistent_json_error(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "doctrine", "show", "nonexistent"])
        assert result.exit_code == 1
        error_data = json.loads(result.stderr)
        assert "error" in error_data

    def test_project_not_found_json_error(self, tmp_path, monkeypatch):
        """ProjectNotFoundError in --json mode produces JSON on stderr."""
        monkeypatch.chdir(tmp_path)
        r = CliRunner()
        result = r.invoke(main, ["--json", "list"])
        assert result.exit_code == 1
        error_data = json.loads(result.stderr)
        assert "error" in error_data
        assert result.stdout == ""

    def test_invalid_status_transition_json_error(self, runner, project_dir):
        """Claiming a closed mission in --json mode returns JSON error."""
        _create_quest_direct(project_dir, "q-abcd", "Quest")
        _create_mission_direct(project_dir, "q-abcd/m-ef01", "q-abcd", "Mission", status="closed")
        result = runner.invoke(main, ["--json", "claim", "q-abcd/m-ef01"])
        assert result.exit_code == 1
        combined = result.stderr + result.stdout
        assert "Cannot claim" in combined or "error" in combined


# ---------------------------------------------------------------------------
# ID generation failure
# ---------------------------------------------------------------------------


class TestIdGenerationFailure:
    """When ID generation exhausts all lengths, produce specific error and exit code 1."""

    def test_quest_id_generation_failure(self, runner, project_dir):
        with patch("lore.db.generate_id", side_effect=RuntimeError("ID collision after 6 chars for prefix q")):
            result = runner.invoke(main, ["new", "quest", "Test Quest"])
        assert result.exit_code == 1
        combined = result.stdout + result.stderr
        assert "ID generation failed: collision after maximum length. Please retry." in combined

    def test_mission_id_generation_failure(self, runner, project_dir):
        _create_quest_direct(project_dir, "q-abcd", "Test Quest")
        with patch("lore.db.generate_id", side_effect=RuntimeError("ID collision after 6 chars for prefix m")):
            result = runner.invoke(main, ["new", "mission", "Test Mission", "-q", "q-abcd"])
        assert result.exit_code == 1
        combined = result.stdout + result.stderr
        assert "ID generation failed: collision after maximum length. Please retry." in combined

    def test_quest_id_generation_failure_json(self, runner, project_dir):
        with patch("lore.db.generate_id", side_effect=RuntimeError("ID collision after 6 chars for prefix q")):
            result = runner.invoke(main, ["--json", "new", "quest", "Test Quest"])
        assert result.exit_code == 1
        error_data = json.loads(result.stderr)
        assert "error" in error_data
        assert "ID generation failed" in error_data["error"]


# ---------------------------------------------------------------------------
# Idempotent operations
# ---------------------------------------------------------------------------


class TestIdempotentOperations:
    """Idempotent operations succeed with exit code 0."""

    def test_claim_already_in_progress(self, runner, project_dir):
        _create_quest_direct(project_dir, "q-abcd", "Quest")
        _create_mission_direct(project_dir, "q-abcd/m-ef01", "q-abcd", "Mission", status="in_progress")
        result = runner.invoke(main, ["claim", "q-abcd/m-ef01"])
        assert result.exit_code == 0

    def test_done_already_closed(self, runner, project_dir):
        _create_quest_direct(project_dir, "q-abcd", "Quest")
        _create_mission_direct(project_dir, "q-abcd/m-ef01", "q-abcd", "Mission", status="closed")
        result = runner.invoke(main, ["done", "q-abcd/m-ef01"])
        assert result.exit_code == 0

    def test_duplicate_dependency(self, runner, project_dir):
        _create_quest_direct(project_dir, "q-abcd", "Quest")
        _create_mission_direct(project_dir, "q-abcd/m-ef01", "q-abcd", "Mission A")
        _create_mission_direct(project_dir, "q-abcd/m-ef02", "q-abcd", "Mission B")
        _create_dependency(project_dir, "q-abcd/m-ef01", "q-abcd/m-ef02")
        result = runner.invoke(main, ["needs", "q-abcd/m-ef01:q-abcd/m-ef02"])
        assert result.exit_code == 0

    def test_duplicate_dependency_message(self, runner, project_dir):
        _create_quest_direct(project_dir, "q-abcd", "Quest")
        _create_mission_direct(project_dir, "q-abcd/m-ef01", "q-abcd", "Mission A")
        _create_mission_direct(project_dir, "q-abcd/m-ef02", "q-abcd", "Mission B")
        _create_dependency(project_dir, "q-abcd/m-ef01", "q-abcd/m-ef02")
        result = runner.invoke(main, ["needs", "q-abcd/m-ef01:q-abcd/m-ef02"])
        assert "already exists" in result.output

    def test_claim_already_in_progress_json(self, runner, project_dir):
        _create_quest_direct(project_dir, "q-abcd", "Quest")
        _create_mission_direct(project_dir, "q-abcd/m-ef01", "q-abcd", "Mission", status="in_progress")
        result = runner.invoke(main, ["--json", "claim", "q-abcd/m-ef01"])
        assert result.exit_code == 0

    def test_done_already_closed_json(self, runner, project_dir):
        _create_quest_direct(project_dir, "q-abcd", "Quest")
        _create_mission_direct(project_dir, "q-abcd/m-ef01", "q-abcd", "Mission", status="closed")
        result = runner.invoke(main, ["--json", "done", "q-abcd/m-ef01"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Invalid status transitions
# ---------------------------------------------------------------------------


class TestInvalidStatusTransitions:
    """Invalid status transitions return exit code 1."""

    def test_claim_closed_mission(self, runner, project_dir):
        _create_quest_direct(project_dir, "q-abcd", "Quest")
        _create_mission_direct(project_dir, "q-abcd/m-ef01", "q-abcd", "Mission", status="closed")
        result = runner.invoke(main, ["claim", "q-abcd/m-ef01"])
        assert result.exit_code == 1
        assert "Cannot claim" in result.stderr

    def test_claim_blocked_mission(self, runner, project_dir):
        _create_quest_direct(project_dir, "q-abcd", "Quest")
        _create_mission_direct(project_dir, "q-abcd/m-ef01", "q-abcd", "Mission", status="blocked")
        result = runner.invoke(main, ["claim", "q-abcd/m-ef01"])
        assert result.exit_code == 1
        assert "Cannot claim" in result.stderr

    def test_unblock_open_mission(self, runner, project_dir):
        _create_quest_direct(project_dir, "q-abcd", "Quest")
        _create_mission_direct(project_dir, "q-abcd/m-ef01", "q-abcd", "Mission", status="open")
        result = runner.invoke(main, ["unblock", "q-abcd/m-ef01"])
        assert result.exit_code == 1
        assert "Cannot unblock" in result.stderr

    def test_unblock_in_progress_mission(self, runner, project_dir):
        _create_quest_direct(project_dir, "q-abcd", "Quest")
        _create_mission_direct(project_dir, "q-abcd/m-ef01", "q-abcd", "Mission", status="in_progress")
        result = runner.invoke(main, ["unblock", "q-abcd/m-ef01"])
        assert result.exit_code == 1
        assert "Cannot unblock" in result.stderr

    def test_unblock_closed_mission(self, runner, project_dir):
        _create_quest_direct(project_dir, "q-abcd", "Quest")
        _create_mission_direct(project_dir, "q-abcd/m-ef01", "q-abcd", "Mission", status="closed")
        result = runner.invoke(main, ["unblock", "q-abcd/m-ef01"])
        assert result.exit_code == 1
        assert "Cannot unblock" in result.stderr

    def test_block_closed_mission(self, runner, project_dir):
        _create_quest_direct(project_dir, "q-abcd", "Quest")
        _create_mission_direct(project_dir, "q-abcd/m-ef01", "q-abcd", "Mission", status="closed")
        result = runner.invoke(main, ["block", "q-abcd/m-ef01", "some reason"])
        assert result.exit_code == 1
        assert "Cannot block" in result.stderr

    def test_claim_closed_mission_json(self, runner, project_dir):
        _create_quest_direct(project_dir, "q-abcd", "Quest")
        _create_mission_direct(project_dir, "q-abcd/m-ef01", "q-abcd", "Mission", status="closed")
        result = runner.invoke(main, ["--json", "claim", "q-abcd/m-ef01"])
        assert result.exit_code == 1

    def test_unblock_open_mission_json(self, runner, project_dir):
        _create_quest_direct(project_dir, "q-abcd", "Quest")
        _create_mission_direct(project_dir, "q-abcd/m-ef01", "q-abcd", "Mission", status="open")
        result = runner.invoke(main, ["--json", "unblock", "q-abcd/m-ef01"])
        assert result.exit_code == 1
        error_data = json.loads(result.stderr)
        assert "error" in error_data
        assert "Cannot unblock" in error_data["error"]


# ---------------------------------------------------------------------------
# Commands outside an initialized project
# ---------------------------------------------------------------------------


class TestCommandOutsideProject:
    """Commands requiring .lore/ exit 1 in a non-project directory."""

    def test_list_outside_project_exits_one(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        r = CliRunner()
        result = r.invoke(main, ["list"])
        assert_exit_err(result, 1)

    def test_error_message_mentions_project(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        r = CliRunner()
        result = r.invoke(main, ["list"])
        assert "lore" in result.output.lower()

    def test_missions_outside_project_exits_one(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        r = CliRunner()
        result = r.invoke(main, ["missions"])
        assert_exit_err(result, 1)


# ---------------------------------------------------------------------------
# Mutually exclusive flags on edit
# ---------------------------------------------------------------------------


class TestEditQuestMutuallyExclusiveFlags:
    """--auto-close and --no-auto-close are mutually exclusive."""

    def test_exit_code_two(self, runner, project_dir):
        rq = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(rq.output)["id"]
        result = runner.invoke(
            main, ["edit", quest_id, "--auto-close", "--no-auto-close"]
        )
        assert_exit_err(result, 2)

    def test_error_mentions_mutual_exclusion(self, runner, project_dir):
        rq = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(rq.output)["id"]
        result = runner.invoke(
            main, ["edit", quest_id, "--auto-close", "--no-auto-close"]
        )
        assert "mutually exclusive" in result.output.lower()


class TestEditMissionMutuallyExclusiveKnightFlags:
    """--knight and --no-knight are mutually exclusive."""

    def test_exit_code_two(self, runner, project_dir):
        rq = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(rq.output)["id"]
        rm = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(rm.output)["id"]
        result = runner.invoke(
            main, ["edit", m_id, "--knight", "dev.md", "--no-knight"]
        )
        assert_exit_err(result, 2)

    def test_error_mentions_mutual_exclusion(self, runner, project_dir):
        rq = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(rq.output)["id"]
        rm = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(rm.output)["id"]
        result = runner.invoke(
            main, ["edit", m_id, "--knight", "dev.md", "--no-knight"]
        )
        assert "mutually exclusive" in result.output.lower()


# ---------------------------------------------------------------------------
# Edit on soft-deleted entity
# ---------------------------------------------------------------------------


class TestEditSoftDeletedEntity:
    """Editing a soft-deleted entity returns JSON error with deleted_at."""

    def test_edit_soft_deleted_quest_exits_one(self, runner, project_dir):
        rq = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(rq.output)["id"]
        runner.invoke(main, ["delete", quest_id])
        result = runner.invoke(main, ["--json", "edit", quest_id, "--title", "X"])
        assert_exit_err(result, 1)

    def test_edit_soft_deleted_quest_json_has_error_key(self, runner, project_dir):
        rq = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(rq.output)["id"]
        runner.invoke(main, ["delete", quest_id])
        result = runner.invoke(main, ["--json", "edit", quest_id, "--title", "X"])
        data = json.loads(result.output)
        assert "error" in data

    def test_edit_soft_deleted_quest_json_has_deleted_at_key(self, runner, project_dir):
        rq = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(rq.output)["id"]
        runner.invoke(main, ["delete", quest_id])
        result = runner.invoke(main, ["--json", "edit", quest_id, "--title", "X"])
        data = json.loads(result.output)
        assert "deleted_at" in data
        assert data["deleted_at"] is not None

    def test_edit_soft_deleted_mission_exits_one(self, runner, project_dir):
        rq = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(rq.output)["id"]
        rm = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(rm.output)["id"]
        runner.invoke(main, ["delete", m_id])
        result = runner.invoke(main, ["--json", "edit", m_id, "--title", "X"])
        assert_exit_err(result, 1)

    def test_edit_soft_deleted_mission_json_has_both_keys(self, runner, project_dir):
        rq = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(rq.output)["id"]
        rm = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(rm.output)["id"]
        runner.invoke(main, ["delete", m_id])
        result = runner.invoke(main, ["--json", "edit", m_id, "--title", "X"])
        data = json.loads(result.output)
        assert "error" in data
        assert "deleted_at" in data


# ---------------------------------------------------------------------------
# Show mission whose parent quest is soft-deleted
# ---------------------------------------------------------------------------


class TestShowMissionDeletedParentQuest:
    """show mission still works when its parent quest is soft-deleted."""

    def _setup(self, runner, project_dir):
        rq = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(rq.output)["id"]
        rm = runner.invoke(main, ["--json", "new", "mission", "M", "-q", quest_id])
        m_id = json.loads(rm.output)["id"]
        runner.invoke(main, ["delete", quest_id])
        return quest_id, m_id

    def test_exit_code_zero(self, runner, project_dir):
        _, m_id = self._setup(runner, project_dir)
        result = runner.invoke(main, ["show", m_id])
        assert_exit_ok(result)

    def test_output_contains_quest_deleted_annotation(self, runner, project_dir):
        _, m_id = self._setup(runner, project_dir)
        result = runner.invoke(main, ["show", m_id])
        assert "quest deleted" in result.output.lower()

    def test_mission_title_in_output(self, runner, project_dir):
        _, m_id = self._setup(runner, project_dir)
        result = runner.invoke(main, ["show", m_id])
        assert "M" in result.output


# ---------------------------------------------------------------------------
# Missions with soft-deleted quest
# ---------------------------------------------------------------------------


class TestMissionsWithSoftDeletedQuest:
    """Missions from a soft-deleted quest still appear with annotation."""

    def _setup(self, runner, project_dir):
        rq = runner.invoke(main, ["--json", "new", "quest", "Q"])
        quest_id = json.loads(rq.output)["id"]
        rm = runner.invoke(main, ["--json", "new", "mission", "M1", "-q", quest_id])
        m_id = json.loads(rm.output)["id"]
        runner.invoke(main, ["delete", quest_id])
        return quest_id, m_id

    def test_missions_still_appear_in_list(self, runner, project_dir):
        _, m_id = self._setup(runner, project_dir)
        result = runner.invoke(main, ["missions"])
        assert_exit_ok(result)
        assert m_id in result.output

    def test_quest_deleted_annotation_in_output(self, runner, project_dir):
        self._setup(runner, project_dir)
        result = runner.invoke(main, ["missions"])
        assert "quest deleted" in result.output.lower()

    def test_json_missions_includes_them(self, runner, project_dir):
        _, m_id = self._setup(runner, project_dir)
        result = runner.invoke(main, ["--json", "missions"])
        data = json.loads(result.output)
        assert any(m["id"] == m_id for m in data["missions"])
