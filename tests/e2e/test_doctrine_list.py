"""E2E tests for the doctrine list command.

Spec: conceptual-workflows-doctrine-list (lore codex show conceptual-workflows-doctrine-list)
"""

import json
import shutil
from pathlib import Path

import pytest

from lore.cli import main, _format_table
import lore as _lore_pkg

_DEFAULTS_DOCTRINES_DIR = Path(_lore_pkg.__file__).parent / "defaults" / "doctrines"
_DEFAULT_DOCTRINE_FILES = sorted(_DEFAULTS_DOCTRINES_DIR.rglob("*.yaml"))


def _write_doctrine(project_dir, filename, content):
    """Helper to write a doctrine YAML file into .lore/doctrines/."""
    doctrine_path = project_dir / ".lore" / "doctrines" / filename
    doctrine_path.parent.mkdir(parents=True, exist_ok=True)
    doctrine_path.write_text(content)
    return doctrine_path


# ---------------------------------------------------------------------------
# Basic list behaviour
# ---------------------------------------------------------------------------


class TestDoctrineListBasic:
    """lore doctrine list exits 0 and shows default doctrines."""

    def test_list_exits_zero(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0

    def test_list_shows_a_default_doctrine(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "doctrine", "list"])
        data = json.loads(result.output)
        assert len(data["doctrines"]) >= 1

    def test_no_subdir_annotation_in_output(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "list"])
        assert "default/" not in result.output


# ---------------------------------------------------------------------------
# Table header
# ---------------------------------------------------------------------------


class TestDoctrineListTableHeader:
    """lore doctrine list outputs a table with ID, GROUP, TITLE, SUMMARY columns."""

    def test_header_contains_id(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "list"])
        assert "ID" in result.output

    def test_header_contains_group(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "list"])
        assert "GROUP" in result.output

    def test_header_contains_title(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "list"])
        assert "TITLE" in result.output

    def test_header_contains_summary(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "list"])
        assert "SUMMARY" in result.output

    def test_header_columns_in_correct_order(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "list"])
        non_empty_lines = [line for line in result.output.split("\n") if line.strip()]
        header = non_empty_lines[0]
        id_pos = header.index("ID")
        group_pos = header.index("GROUP")
        title_pos = header.index("TITLE")
        summary_pos = header.index("SUMMARY")
        assert id_pos < group_pos < title_pos < summary_pos


# ---------------------------------------------------------------------------
# Invalid doctrine marking
# ---------------------------------------------------------------------------


class TestDoctrineListInvalidMarking:
    """Invalid doctrines appear in list marked with [INVALID]."""

    def test_invalid_doctrine_marked_in_list(self, runner, project_dir):
        _write_doctrine(project_dir, "broken.yaml", "name: broken\n")
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0
        assert "broken" in result.output
        assert "[INVALID]" in result.output

    def test_valid_doctrines_not_marked_invalid(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "list"])
        assert "[INVALID]" not in result.output

    def test_invalid_marker_uses_single_space(self, runner, project_dir):
        doctrines_dir = project_dir / ".lore" / "doctrines"
        shutil.rmtree(doctrines_dir)
        doctrines_dir.mkdir()
        (doctrines_dir / "bad-doc.yaml").write_text(
            "name: bad-doc\ndescription: broken summary\n"
        )
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0
        expected_lines = _format_table(
            ["ID", "GROUP", "TITLE", "SUMMARY"],
            [["bad-doc", "", "bad-doc", "broken summary [INVALID]"]],
        )
        expected_output = "\n".join(expected_lines) + "\n"
        assert result.output == expected_output


# ---------------------------------------------------------------------------
# Empty doctrine directory
# ---------------------------------------------------------------------------


class TestDoctrineListEmpty:
    """When no doctrines exist, "No doctrines found." is shown."""

    def test_empty_dir_exits_zero(self, runner, project_dir):
        doctrines_dir = project_dir / ".lore" / "doctrines"
        shutil.rmtree(doctrines_dir)
        doctrines_dir.mkdir()
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0

    def test_empty_dir_shows_no_doctrines_found(self, runner, project_dir):
        doctrines_dir = project_dir / ".lore" / "doctrines"
        shutil.rmtree(doctrines_dir)
        doctrines_dir.mkdir()
        result = runner.invoke(main, ["doctrine", "list"])
        assert "No doctrines found." in result.output


# ---------------------------------------------------------------------------
# Nested doctrines discovery
# ---------------------------------------------------------------------------


class TestDoctrineListNested:
    """Doctrines in subdirectories appear in list output."""

    def test_default_subdir_doctrines_appear(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "doctrine", "list"])
        data = json.loads(result.output)
        assert len(data["doctrines"]) >= 1

    def test_flat_level_doctrine_appears(self, runner, project_dir):
        _write_doctrine(
            project_dir,
            "my-workflow.yaml",
            "name: my-workflow\ndescription: My custom workflow\nsteps:\n  - id: work\n    title: Do work\n",
        )
        result = runner.invoke(main, ["doctrine", "list"])
        assert "my-workflow" in result.output

    def test_deeply_nested_doctrine_appears(self, runner, project_dir):
        _write_doctrine(
            project_dir,
            "team/sprints/retro.yaml",
            "name: retro\ndescription: Retrospective workflow\nsteps:\n  - id: discuss\n    title: Discuss\n",
        )
        result = runner.invoke(main, ["doctrine", "list"])
        assert "retro" in result.output


# ---------------------------------------------------------------------------
# JSON output schema
# ---------------------------------------------------------------------------


class TestDoctrineListJsonSchema:
    """JSON output envelope and field contracts."""

    def test_json_has_doctrines_key(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "doctrine", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "doctrines" in data
        assert isinstance(data["doctrines"], list)

    def test_json_records_have_group_key(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "doctrine", "list"])
        parsed = json.loads(result.output)
        missing = [r for r in parsed["doctrines"] if "group" not in r]
        assert missing == []

    def test_json_records_have_only_five_fields(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "doctrine", "list"])
        data = json.loads(result.output)
        for doctrine in data["doctrines"]:
            extra = set(doctrine.keys()) - {"id", "group", "title", "summary", "valid"}
            assert not extra

    def test_json_no_name_key(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "doctrine", "list"])
        parsed = json.loads(result.output)
        records_with_name = [r for r in parsed["doctrines"] if "name" in r]
        assert records_with_name == []

    def test_json_no_description_key(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "doctrine", "list"])
        parsed = json.loads(result.output)
        records_with_description = [r for r in parsed["doctrines"] if "description" in r]
        assert records_with_description == []

    def test_json_no_errors_key(self, runner, project_dir):
        _write_doctrine(project_dir, "broken.yaml", "name: broken\n")
        result = runner.invoke(main, ["--json", "doctrine", "list"])
        parsed = json.loads(result.output)
        records_with_errors = [r for r in parsed["doctrines"] if "errors" in r]
        assert records_with_errors == []

    def test_json_invalid_doctrine_valid_false(self, runner, project_dir):
        _write_doctrine(project_dir, "broken.yaml", "name: broken\n")
        result = runner.invoke(main, ["--json", "doctrine", "list"])
        parsed = json.loads(result.output)
        broken = [r for r in parsed["doctrines"] if r["id"] == "broken"]
        assert len(broken) == 1
        assert broken[0]["valid"] is False

    def test_json_count_matches_table_rows(self, runner, project_dir):
        table_result = runner.invoke(main, ["doctrine", "list"])
        json_result = runner.invoke(main, ["--json", "doctrine", "list"])
        assert json_result.exit_code == 0
        parsed = json.loads(json_result.output)
        table_lines = [line for line in table_result.output.strip().split("\n") if line.strip()]
        doctrine_table_rows = len(table_lines) - 1
        assert len(parsed["doctrines"]) == doctrine_table_rows


# ---------------------------------------------------------------------------
# Default doctrines have descriptive metadata
# ---------------------------------------------------------------------------


class TestDefaultDoctrineMetadata:
    """After lore init, default doctrines have id, title, and summary metadata."""

    def test_default_doctrines_visible_in_json(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "doctrine", "list"])
        data = json.loads(result.output)
        assert len(data["doctrines"]) >= 1


# ---------------------------------------------------------------------------
# Local --json flag (US-3)
# ---------------------------------------------------------------------------


class TestLocalJsonFlag:
    """lore doctrine list --json local flag produces identical JSON to global --json flag.

    Ref: conceptual-workflows-doctrine-list (lore codex show conceptual-workflows-doctrine-list)
    """

    def test_local_json_flag_exits_zero(self, runner, project_dir):
        # Ref: conceptual-workflows-doctrine-list step 1 and step 2
        result = runner.invoke(main, ["doctrine", "list", "--json"])
        assert result.exit_code == 0

    def test_local_json_flag_returns_doctrines_key(self, runner, project_dir):
        # Ref: conceptual-workflows-doctrine-list step 2 (top-level key is "doctrines")
        result = runner.invoke(main, ["doctrine", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "doctrines" in data
        assert isinstance(data["doctrines"], list)

    def test_local_json_flag_records_have_exactly_five_fields(self, runner, project_dir):
        # Ref: conceptual-workflows-doctrine-list step 5 (JSON mode: id, group, title, summary, valid)
        result = runner.invoke(main, ["doctrine", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["doctrines"]) > 0
        for doctrine in data["doctrines"]:
            assert set(doctrine.keys()) == {"id", "group", "title", "summary", "valid"}

    def test_local_json_flag_valid_doctrine_has_valid_true(self, runner, project_dir):
        # Ref: conceptual-workflows-doctrine-list step 2 (valid boolean field)
        result = runner.invoke(main, ["doctrine", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert any(d["valid"] is True for d in data["doctrines"])

    def test_local_json_flag_invalid_doctrine_has_valid_false(self, runner, project_dir):
        # Ref: conceptual-workflows-doctrine-list step 2 (invalid doctrine → valid: false)
        # Ref: conceptual-workflows-doctrine-list step 3 (Pass B — validation failure)
        _write_doctrine(project_dir, "broken-local.yaml", "name: broken-local\n")
        result = runner.invoke(main, ["doctrine", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        broken = [d for d in data["doctrines"] if d["id"] == "broken-local"]
        assert len(broken) == 1
        assert broken[0]["valid"] is False

    def test_local_json_flag_invalid_doctrine_summary_has_no_invalid_suffix(self, runner, project_dir):
        # Ref: conceptual-workflows-doctrine-list step 2 (field note: [INVALID] not in JSON summary)
        # Ref: conceptual-workflows-doctrine-list step 5 (JSON mode: no [INVALID] suffix)
        _write_doctrine(project_dir, "broken-suffix.yaml", "name: broken-suffix\n")
        result = runner.invoke(main, ["doctrine", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        broken = [d for d in data["doctrines"] if d["id"] == "broken-suffix"]
        assert len(broken) == 1
        assert "[INVALID]" not in broken[0]["summary"]

    def test_local_json_flag_identical_to_global_flag(self, runner, project_dir):
        # Ref: conceptual-workflows-doctrine-list step 1 (decision point: flag position)
        # Both lore doctrine list --json and lore --json doctrine list must produce identical output
        local_result = runner.invoke(main, ["doctrine", "list", "--json"])
        global_result = runner.invoke(main, ["--json", "doctrine", "list"])
        assert local_result.exit_code == 0
        assert global_result.exit_code == 0
        assert json.loads(local_result.output) == json.loads(global_result.output)

    def test_local_json_flag_empty_doctrines_returns_empty_array(self, runner, project_dir):
        # Ref: conceptual-workflows-doctrine-list step 3 (empty result → {"doctrines": []})
        # Ref: conceptual-workflows-doctrine-list step 1 (non-existent dir → empty result)
        doctrines_dir = project_dir / ".lore" / "doctrines"
        shutil.rmtree(doctrines_dir)
        doctrines_dir.mkdir()
        result = runner.invoke(main, ["doctrine", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == {"doctrines": []}

    def test_local_json_flag_declared_at_subcommand_level(self, runner, project_dir):
        # Ref: conceptual-workflows-json-output — local flag position (not only global lore --json)
        # Invokes `lore doctrine list --help` and asserts "--json" appears in the subcommand help text
        result = runner.invoke(main, ["doctrine", "list", "--help"])
        assert result.exit_code == 0
        assert "--json" in result.output

    def test_local_json_flag_group_empty_for_root_doctrine(self, runner, project_dir):
        # Ref: conceptual-workflows-doctrine-list step 2 (group derivation: flat root → group = "")
        # Doctrine file is at .lore/doctrines/<name>.yaml (not in a subdirectory)
        _write_doctrine(
            project_dir,
            "root-level-doctrine.yaml",
            "name: root-level-doctrine\ndescription: Root doctrine.\nsteps:\n  - id: step1\n    title: Step One\n",
        )
        result = runner.invoke(main, ["doctrine", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        root_doctrines = [d for d in data["doctrines"] if d["id"] == "root-level-doctrine"]
        assert len(root_doctrines) == 1
        assert root_doctrines[0]["group"] == ""

    def test_local_json_flag_group_is_subdirectory_name(self, runner, project_dir):
        # Ref: conceptual-workflows-doctrine-list step 2 (group derivation: subdirectory name → group)
        # Doctrine file is at .lore/doctrines/default/<name>.yaml; JSON record "group" must equal "default"
        _write_doctrine(
            project_dir,
            "default/subdir-doctrine.yaml",
            "name: subdir-doctrine\ndescription: Subdirectory doctrine.\nsteps:\n  - id: step1\n    title: Step One\n",
        )
        result = runner.invoke(main, ["doctrine", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        subdir_doctrines = [d for d in data["doctrines"] if d["id"] == "subdir-doctrine"]
        assert len(subdir_doctrines) == 1
        assert subdir_doctrines[0]["group"] == "default"
