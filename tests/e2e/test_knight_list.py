"""E2E tests for the knight list command.

Spec: conceptual-workflows-knight-list (lore codex show conceptual-workflows-knight-list)
"""

import json
import shutil
from pathlib import Path

import pytest

from lore.cli import main, _format_table
from lore.frontmatter import parse_frontmatter_doc

import lore as _lore_pkg

_DEFAULTS_KNIGHTS_DIR = Path(_lore_pkg.__file__).parent / "defaults" / "knights"
_DEFAULT_KNIGHT_FILES = sorted(_DEFAULTS_KNIGHTS_DIR.rglob("*.md"))

# ---------------------------------------------------------------------------
# Basic list behaviour
# ---------------------------------------------------------------------------


class TestKnightListBasic:
    """lore knight list exits 0 and shows default knights."""

    def test_list_exits_zero(self, runner, project_dir):
        result = runner.invoke(main, ["knight", "list"])
        assert result.exit_code == 0

    def test_list_shows_a_default_knight(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "knight", "list"])
        data = json.loads(result.output)
        assert len(data["knights"]) >= 1

    def test_no_subdir_annotation_in_output(self, runner, project_dir):
        result = runner.invoke(main, ["knight", "list"])
        assert "default/" not in result.output


# ---------------------------------------------------------------------------
# Table header
# ---------------------------------------------------------------------------


class TestKnightListTableHeader:
    """lore knight list outputs a table with ID, GROUP, TITLE, SUMMARY columns."""

    def test_header_contains_id(self, runner, project_dir):
        result = runner.invoke(main, ["knight", "list"])
        assert "ID" in result.output

    def test_header_contains_group(self, runner, project_dir):
        result = runner.invoke(main, ["knight", "list"])
        assert "GROUP" in result.output

    def test_header_contains_title(self, runner, project_dir):
        result = runner.invoke(main, ["knight", "list"])
        assert "TITLE" in result.output

    def test_header_contains_summary(self, runner, project_dir):
        result = runner.invoke(main, ["knight", "list"])
        assert "SUMMARY" in result.output

    def test_header_columns_in_correct_order(self, runner, project_dir):
        result = runner.invoke(main, ["knight", "list"])
        non_empty_lines = [l for l in result.output.split("\n") if l.strip()]
        header = non_empty_lines[0]
        id_pos = header.index("ID")
        group_pos = header.index("GROUP")
        title_pos = header.index("TITLE")
        summary_pos = header.index("SUMMARY")
        assert id_pos < group_pos < title_pos < summary_pos

    def test_header_has_two_space_indent(self, runner, project_dir):
        result = runner.invoke(main, ["knight", "list"])
        non_empty_lines = [l for l in result.output.split("\n") if l.strip()]
        header = non_empty_lines[0]
        assert header.startswith("  ")
        assert header[2] != " "

    def test_data_rows_have_two_space_indent(self, runner, project_dir):
        result = runner.invoke(main, ["knight", "list"])
        non_empty_lines = [l for l in result.output.split("\n") if l.strip()]
        for line in non_empty_lines[1:]:
            assert line.startswith("  ")


# ---------------------------------------------------------------------------
# One row per knight
# ---------------------------------------------------------------------------


class TestKnightListOneRowPerKnight:
    """Each knight appears on exactly one row in the table."""

    def test_line_count_matches_knight_count_plus_header(self, runner, project_dir):
        result_list = runner.invoke(main, ["knight", "list"])
        result_json = runner.invoke(main, ["--json", "knight", "list"])
        assert result_list.exit_code == 0
        assert result_json.exit_code == 0
        non_empty_lines = [l for l in result_list.output.split("\n") if l.strip()]
        data = json.loads(result_json.output)
        knight_count = len(data["knights"])
        expected = knight_count + 1
        assert len(non_empty_lines) == expected

    def test_single_knight_produces_exactly_two_lines(self, runner, project_dir):
        knights_dir = project_dir / ".lore" / "knights"
        shutil.rmtree(knights_dir)
        knights_dir.mkdir()
        (knights_dir / "solo-knight.md").write_text(
            "---\nid: solo-knight\ntitle: Solo\nsummary: Only knight.\n---\n"
        )
        result = runner.invoke(main, ["knight", "list"])
        assert result.exit_code == 0
        non_empty_lines = [l for l in result.output.split("\n") if l.strip()]
        assert len(non_empty_lines) == 2

    def test_each_default_knight_appears_exactly_once(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "knight", "list"])
        data = json.loads(result.output)
        ids = [k["id"] for k in data["knights"]]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Column padding
# ---------------------------------------------------------------------------


class TestKnightListColumnPadding:
    """Columns are padded to the widest value with consistent spacing."""

    def test_id_column_padded_to_longest_value(self, runner, project_dir):
        knights_dir = project_dir / ".lore" / "knights"
        shutil.rmtree(knights_dir)
        knights_dir.mkdir()
        (knights_dir / "short.md").write_text(
            "---\nid: short\ntitle: Short\nsummary: A.\n---\n"
        )
        (knights_dir / "very-long-knight-identifier.md").write_text(
            "---\nid: very-long-knight-identifier\ntitle: Long ID\nsummary: B.\n---\n"
        )
        result = runner.invoke(main, ["knight", "list"])
        assert result.exit_code == 0
        non_empty_lines = [l for l in result.output.split("\n") if l.strip()]
        data_rows = non_empty_lines[1:]
        long_id_len = len("very-long-knight-identifier")
        short_row = next(r for r in data_rows if r.strip().startswith("short"))
        id_section = short_row[2: 2 + long_id_len]
        assert id_section == "short" + " " * (long_id_len - len("short"))

    def test_format_table_produces_correct_output(self, runner, project_dir):
        knights_dir = project_dir / ".lore" / "knights"
        shutil.rmtree(knights_dir)
        knights_dir.mkdir()
        (knights_dir / "test-k.md").write_text(
            "---\nid: test-k\ntitle: Test Knight\nsummary: A test knight.\n---\n"
        )
        result = runner.invoke(main, ["knight", "list"])
        assert result.exit_code == 0
        expected_lines = _format_table(
            ["ID", "GROUP", "TITLE", "SUMMARY"],
            [["test-k", "", "Test Knight", "A test knight."]],
        )
        expected_output = "\n".join(expected_lines) + "\n"
        assert result.output == expected_output


# ---------------------------------------------------------------------------
# Empty / no-knights case
# ---------------------------------------------------------------------------


class TestKnightListEmpty:
    """When no knights exist, "No knights found." is shown instead of a table."""

    def test_empty_dir_exits_zero(self, runner, project_dir):
        knights_dir = project_dir / ".lore" / "knights"
        shutil.rmtree(knights_dir)
        knights_dir.mkdir()
        result = runner.invoke(main, ["knight", "list"])
        assert result.exit_code == 0

    def test_empty_dir_shows_no_knights_found(self, runner, project_dir):
        knights_dir = project_dir / ".lore" / "knights"
        shutil.rmtree(knights_dir)
        knights_dir.mkdir()
        result = runner.invoke(main, ["knight", "list"])
        assert result.output.strip() == "No knights found."

    def test_nonexistent_dir_shows_no_knights_found(self, runner, project_dir):
        knights_dir = project_dir / ".lore" / "knights"
        shutil.rmtree(knights_dir)
        result = runner.invoke(main, ["knight", "list"])
        assert "No knights found." in result.output

    def test_no_knights_found_absent_when_knights_exist(self, runner, project_dir):
        result = runner.invoke(main, ["knight", "list"])
        assert "No knights found." not in result.output


# ---------------------------------------------------------------------------
# Frontmatter fields
# ---------------------------------------------------------------------------


class TestKnightListFrontmatterFields:
    """Knights display id, title, group, and summary from frontmatter."""

    def test_id_from_frontmatter(self, runner, project_dir):
        knights_dir = project_dir / ".lore" / "knights"
        (knights_dir / "test-knight.md").write_text(
            "---\nid: my-custom-id\ntitle: Test Title\nsummary: Test summary.\n---\n"
        )
        result = runner.invoke(main, ["knight", "list"])
        assert "my-custom-id" in result.output

    def test_title_from_frontmatter(self, runner, project_dir):
        knights_dir = project_dir / ".lore" / "knights"
        (knights_dir / "title-knight.md").write_text(
            "---\nid: title-knight\ntitle: Magnificent Title\nsummary: A great summary.\n---\n"
        )
        result = runner.invoke(main, ["knight", "list"])
        assert "Magnificent Title" in result.output

    def test_summary_from_frontmatter(self, runner, project_dir):
        knights_dir = project_dir / ".lore" / "knights"
        (knights_dir / "summary-knight.md").write_text(
            "---\nid: summary-knight\ntitle: Summary Knight\nsummary: A distinctive one-liner.\n---\n"
        )
        result = runner.invoke(main, ["knight", "list"])
        assert "A distinctive one-liner." in result.output

    def test_group_from_subdirectory(self, runner, project_dir):
        knights_dir = project_dir / ".lore" / "knights"
        sub_dir = knights_dir / "myteam"
        sub_dir.mkdir()
        (sub_dir / "team-knight.md").write_text(
            "---\nid: team-knight\ntitle: Team Knight\nsummary: Team summary.\n---\n"
        )
        result = runner.invoke(main, ["knight", "list"])
        assert "myteam" in result.output


# ---------------------------------------------------------------------------
# Custom and nested knights
# ---------------------------------------------------------------------------


class TestKnightListCustom:
    """Custom knight files appear alongside defaults."""

    def test_custom_knight_appears(self, runner, project_dir):
        knights_dir = project_dir / ".lore" / "knights"
        (knights_dir / "backend-expert.md").write_text(
            "# Backend Expert\nSpecializes in backend systems."
        )
        result = runner.invoke(main, ["knight", "list"])
        assert "backend-expert" in result.output

    def test_custom_and_defaults_both_appear(self, runner, project_dir):
        knights_dir = project_dir / ".lore" / "knights"
        (knights_dir / "backend-expert.md").write_text(
            "# Backend Expert\nSpecializes in backend systems."
        )
        result = runner.invoke(main, ["--json", "knight", "list"])
        data = json.loads(result.output)
        ids = [k["id"] for k in data["knights"]]
        assert "backend-expert" in ids
        assert len(ids) >= 2


class TestKnightListDeeplyNested:
    """Knights in deeply nested subdirectories appear in lore knight list."""

    def test_deeply_nested_knight_appears(self, runner, project_dir):
        knights_dir = project_dir / ".lore" / "knights"
        nested_dir = knights_dir / "team" / "more-knights"
        nested_dir.mkdir(parents=True)
        (nested_dir / "cool-knight.md").write_text("# Cool Knight\nNested content.")
        result = runner.invoke(main, ["knight", "list"])
        assert "cool-knight" in result.output

    def test_deeply_nested_appears_in_json(self, runner, project_dir):
        knights_dir = project_dir / ".lore" / "knights"
        nested_dir = knights_dir / "team" / "more-knights"
        nested_dir.mkdir(parents=True)
        (nested_dir / "cool-knight.md").write_text("# Cool Knight\nNested content.")
        result = runner.invoke(main, ["--json", "knight", "list"])
        data = json.loads(result.output)
        ids = [k["id"] for k in data["knights"]]
        assert "cool-knight" in ids


class TestKnightListDuplicateNames:
    """Duplicate knight names across subdirectories both appear."""

    def test_duplicate_names_both_appear(self, runner, project_dir):
        knights_dir = project_dir / ".lore" / "knights"
        (knights_dir / "backend-expert.md").write_text("# Backend Expert flat")
        team_dir = knights_dir / "team"
        team_dir.mkdir()
        (team_dir / "backend-expert.md").write_text("# Backend Expert team")
        result = runner.invoke(main, ["knight", "list"])
        count = result.output.count("backend-expert")
        assert count >= 2

    def test_duplicate_names_both_in_json(self, runner, project_dir):
        knights_dir = project_dir / ".lore" / "knights"
        (knights_dir / "backend-expert.md").write_text("# Backend Expert flat")
        team_dir = knights_dir / "team"
        team_dir.mkdir()
        (team_dir / "backend-expert.md").write_text("# Backend Expert team")
        result = runner.invoke(main, ["--json", "knight", "list"])
        data = json.loads(result.output)
        matching = [k for k in data["knights"] if k["id"] == "backend-expert"]
        assert len(matching) == 2


# ---------------------------------------------------------------------------
# JSON output schema
# ---------------------------------------------------------------------------


class TestKnightListJsonSchema:
    """JSON output envelope and field contracts."""

    def test_json_has_knights_key(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "knight", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "knights" in data
        assert isinstance(data["knights"], list)

    def test_json_entries_have_only_four_fields(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "knight", "list"])
        data = json.loads(result.output)
        for knight in data["knights"]:
            extra = set(knight.keys()) - {"id", "group", "title", "summary"}
            assert not extra

    def test_json_no_name_key(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "knight", "list"])
        parsed = json.loads(result.output)
        records_with_name = [r for r in parsed["knights"] if "name" in r]
        assert records_with_name == []

    def test_json_no_filename_key(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "knight", "list"])
        data = json.loads(result.output)
        for knight in data["knights"]:
            assert "filename" not in knight

    def test_json_id_is_stem_not_path(self, runner, project_dir):
        knights_dir = project_dir / ".lore" / "knights"
        nested_dir = knights_dir / "nested"
        nested_dir.mkdir()
        (nested_dir / "path-check.md").write_text("# Path Check")
        result = runner.invoke(main, ["--json", "knight", "list"])
        data = json.loads(result.output)
        matching = [k for k in data["knights"] if "path-check" in k["id"]]
        assert len(matching) == 1
        assert matching[0]["id"] == "path-check"

    def test_json_group_is_dirname_not_full_path(self, runner, project_dir):
        knights_dir = project_dir / ".lore" / "knights"
        nested_dir = knights_dir / "nested"
        nested_dir.mkdir()
        (nested_dir / "path-check.md").write_text("# Path Check")
        result = runner.invoke(main, ["--json", "knight", "list"])
        data = json.loads(result.output)
        matching = [k for k in data["knights"] if k["id"] == "path-check"]
        assert matching[0]["group"] == "nested"

    def test_json_empty_gives_empty_array(self, runner, project_dir):
        knights_dir = project_dir / ".lore" / "knights"
        shutil.rmtree(knights_dir)
        knights_dir.mkdir()
        result = runner.invoke(main, ["--json", "knight", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["knights"] == []


# ---------------------------------------------------------------------------
# Default knights have descriptive metadata
# ---------------------------------------------------------------------------


class TestDefaultKnightMetadata:
    """After lore init, every built-in knight has a descriptive title and summary."""

    @pytest.mark.parametrize("knight_file", _DEFAULT_KNIGHT_FILES, ids=lambda f: f.stem)
    def test_default_knight_frontmatter_has_required_fields(self, knight_file):
        meta = parse_frontmatter_doc(knight_file, required_fields=("id", "title", "summary"))
        assert meta is not None



# ---------------------------------------------------------------------------
# knight show command
# ---------------------------------------------------------------------------


class TestKnightShow:
    """lore knight show <name> displays knight contents."""

    def test_show_flat_custom_knight(self, runner, project_dir):
        knights_dir = project_dir / ".lore" / "knights"
        (knights_dir / "my-knight.md").write_text("# My Knight\nFlat-level persona.")
        result = runner.invoke(main, ["knight", "show", "my-knight"])
        assert result.exit_code == 0
        assert "Flat-level persona." in result.output

    def test_show_nested_knight_by_stem(self, runner, project_dir):
        knights_dir = project_dir / ".lore" / "knights"
        team_dir = knights_dir / "team"
        team_dir.mkdir()
        (team_dir / "backend-expert.md").write_text("# Backend Expert\nTeam persona.")
        result = runner.invoke(main, ["knight", "show", "backend-expert"])
        assert result.exit_code == 0
        assert "Team persona." in result.output

    def test_show_nonexistent_exits_one(self, runner, project_dir):
        result = runner.invoke(main, ["knight", "show", "nonexistent"])
        assert result.exit_code == 1

    def test_path_separator_name_exits_one(self, runner, project_dir):
        result = runner.invoke(main, ["knight", "show", "default/developer"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Local --json flag (US-2)
# ---------------------------------------------------------------------------


class TestLocalJsonFlag:
    # Ref: conceptual-workflows-knight-list step 1 (flag position)

    def test_local_json_flag_exits_zero(self, runner, project_dir):
        # Ref: conceptual-workflows-knight-list step 1 and step 2
        result = runner.invoke(main, ["knight", "list", "--json"])
        assert result.exit_code == 0

    def test_local_json_flag_returns_knights_key(self, runner, project_dir):
        # Ref: conceptual-workflows-knight-list step 2 (top-level key is "knights")
        result = runner.invoke(main, ["knight", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "knights" in data
        assert isinstance(data["knights"], list)

    def test_local_json_flag_records_have_exactly_four_fields(self, runner, project_dir):
        # Ref: conceptual-workflows-knight-list step 6 (JSON mode: id, group, title, summary)
        result = runner.invoke(main, ["knight", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        for knight in data["knights"]:
            assert set(knight.keys()) == {"id", "group", "title", "summary"}

    def test_local_json_flag_identical_to_global_flag(self, runner, project_dir):
        # Ref: conceptual-workflows-knight-list step 1 (decision point: flag position)
        # Both lore knight list --json and lore --json knight list must produce identical output
        local_result = runner.invoke(main, ["knight", "list", "--json"])
        global_result = runner.invoke(main, ["--json", "knight", "list"])
        assert local_result.exit_code == 0
        assert global_result.exit_code == 0
        assert json.loads(local_result.output) == json.loads(global_result.output)

    def test_local_json_flag_empty_knights_returns_empty_array(self, runner, project_dir):
        # Ref: conceptual-workflows-knight-list step 3 (empty result)
        # Ref: conceptual-workflows-knight-list step 1 (non-existent dir -> empty result)
        knights_dir = project_dir / ".lore" / "knights"
        shutil.rmtree(knights_dir)
        result = runner.invoke(main, ["knight", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == {"knights": []}

    def test_local_json_flag_output_pipeable_to_jq(self, runner, project_dir):
        # Ref: conceptual-workflows-knight-list step 4 (pipe to jq .knights | length)
        # Verifies stdout is valid JSON parseable externally
        result = runner.invoke(main, ["knight", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data["knights"], list)

    def test_local_json_flag_declared_at_subcommand_level(self, runner, project_dir):
        # Ref: conceptual-workflows-json-output -- local flag position (not only global lore --json)
        # Invokes `lore knight list --help` and asserts "--json" appears in the subcommand help text
        result = runner.invoke(main, ["knight", "list", "--help"])
        assert result.exit_code == 0
        assert "--json" in result.output

    def test_local_json_flag_title_fallback_to_id_when_absent(self, runner, project_dir):
        # Ref: conceptual-workflows-knight-list step 4 (title fallback: missing frontmatter -> use id)
        # Knight file has no title in frontmatter; JSON record "title" must equal the knight id
        knights_dir = project_dir / ".lore" / "knights"
        shutil.rmtree(knights_dir)
        knights_dir.mkdir()
        (knights_dir / "no-title-knight.md").write_text(
            "---\nid: no-title-knight\nsummary: Has no title.\n---\n"
        )
        result = runner.invoke(main, ["knight", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        record = next(k for k in data["knights"] if k["id"] == "no-title-knight")
        assert record["title"] == "no-title-knight"

    def test_local_json_flag_summary_fallback_to_empty_string_when_absent(self, runner, project_dir):
        # Ref: conceptual-workflows-knight-list step 4 (summary fallback: missing frontmatter -> "")
        # Knight file has no summary in frontmatter; JSON record "summary" must equal ""
        knights_dir = project_dir / ".lore" / "knights"
        shutil.rmtree(knights_dir)
        knights_dir.mkdir()
        (knights_dir / "no-summary-knight.md").write_text(
            "---\nid: no-summary-knight\ntitle: No Summary Knight\n---\n"
        )
        result = runner.invoke(main, ["knight", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        record = next(k for k in data["knights"] if k["id"] == "no-summary-knight")
        assert record["summary"] == ""

    def test_local_json_flag_group_empty_for_root_knight(self, runner, project_dir):
        # Ref: conceptual-workflows-knight-list step 3 (group derivation: flat root -> group = "")
        # Knight file is at .lore/knights/<name>.md (not in a subdirectory)
        knights_dir = project_dir / ".lore" / "knights"
        shutil.rmtree(knights_dir)
        knights_dir.mkdir()
        (knights_dir / "root-knight.md").write_text(
            "---\nid: root-knight\ntitle: Root Knight\nsummary: Lives in root.\n---\n"
        )
        result = runner.invoke(main, ["knight", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        record = next(k for k in data["knights"] if k["id"] == "root-knight")
        assert record["group"] == ""

    def test_local_json_flag_group_is_subdirectory_name(self, runner, project_dir):
        # Ref: conceptual-workflows-knight-list step 3 (group derivation: subdirectory name -> group)
        # Knight file is at .lore/knights/ops/<name>.md; JSON record "group" must equal "ops"
        knights_dir = project_dir / ".lore" / "knights"
        shutil.rmtree(knights_dir)
        knights_dir.mkdir()
        ops_dir = knights_dir / "ops"
        ops_dir.mkdir()
        (ops_dir / "ops-knight.md").write_text(
            "---\nid: ops-knight\ntitle: Ops Knight\nsummary: Lives in ops.\n---\n"
        )
        result = runner.invoke(main, ["knight", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        record = next(k for k in data["knights"] if k["id"] == "ops-knight")
        assert record["group"] == "ops"


# ---------------------------------------------------------------------------
# knight show command
# ---------------------------------------------------------------------------


