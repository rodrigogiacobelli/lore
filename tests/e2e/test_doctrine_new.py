"""E2E tests for doctrine create, edit, delete, and show commands.

Spec: conceptual-workflows-doctrine-new (lore codex show conceptual-workflows-doctrine-new)
"""

import json

import pytest

from lore.cli import main
from lore.doctrine import DoctrineError, validate_doctrine_content


VALID_DOCTRINE_YAML = """\
name: workflow
description: A test workflow
steps:
  - id: build
    title: Build the thing
"""

UPDATED_DOCTRINE_YAML = """\
name: workflow
description: An updated workflow
steps:
- id: deploy
  title: Deploy the thing
"""

DOCTRINE_WITH_FRONTMATTER = """\
id: patrol
title: Patrol Workflow Title
summary: A concise patrol workflow summary
name: patrol
description: Original patrol description
steps:
  - id: scout
    title: Scout the area
"""

UPDATED_WITHOUT_FRONTMATTER = """\
name: patrol
description: Updated patrol description
steps:
  - id: advance
    title: Advance to objective
"""


def _doctrine_path(project_dir, name):
    return project_dir / ".lore" / "doctrines" / f"{name}.yaml"


def _deleted_path(project_dir, name):
    return project_dir / ".lore" / "doctrines" / f"{name}.yaml.deleted"


def _write_doctrine(project_dir, filename, content):
    doctrine_path = project_dir / ".lore" / "doctrines" / filename
    doctrine_path.parent.mkdir(parents=True, exist_ok=True)
    doctrine_path.write_text(content)
    return doctrine_path


# ---------------------------------------------------------------------------
# Create — basic
# ---------------------------------------------------------------------------


class TestDoctrineNewFromFile:
    """lore doctrine new <name> --from <path> creates a doctrine from a file."""

    def test_create_from_file_exits_zero(self, runner, project_dir):
        source = project_dir / "workflow.yaml"
        source.write_text(VALID_DOCTRINE_YAML)
        result = runner.invoke(main, ["doctrine", "new", "workflow", "--from", str(source)])
        assert result.exit_code == 0

    def test_create_from_file_short_flag(self, runner, project_dir):
        source = project_dir / "workflow.yaml"
        source.write_text(VALID_DOCTRINE_YAML)
        result = runner.invoke(main, ["doctrine", "new", "workflow", "-f", str(source)])
        assert result.exit_code == 0
        assert _doctrine_path(project_dir, "workflow").exists()

    def test_create_from_file_appears_in_list(self, runner, project_dir):
        source = project_dir / "workflow.yaml"
        source.write_text(VALID_DOCTRINE_YAML)
        runner.invoke(main, ["doctrine", "new", "workflow", "--from", str(source)])
        result = runner.invoke(main, ["doctrine", "list"])
        assert "workflow" in result.output


class TestDoctrineNewFromStdin:
    """lore doctrine new <name> reads from stdin when --from is not provided."""

    def test_create_from_stdin_exits_zero(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "new", "workflow"], input=VALID_DOCTRINE_YAML)
        assert result.exit_code == 0

    def test_create_from_stdin_content_matches(self, runner, project_dir):
        runner.invoke(main, ["doctrine", "new", "workflow"], input=VALID_DOCTRINE_YAML)
        assert _doctrine_path(project_dir, "workflow").read_text() == VALID_DOCTRINE_YAML

    def test_create_from_stdin_visible_in_list(self, runner, project_dir):
        yaml_content = "name: myuniquedoctrine\ndescription: Unique\nsteps:\n  - id: start\n    title: Start\n"
        runner.invoke(main, ["doctrine", "new", "myuniquedoctrine"], input=yaml_content)
        result = runner.invoke(main, ["doctrine", "list"])
        assert "myuniquedoctrine" in result.output


# ---------------------------------------------------------------------------
# Create — validation errors
# ---------------------------------------------------------------------------


class TestDoctrineNewValidation:
    """Invalid content is rejected with a descriptive error."""

    def test_malformed_steps_rejected(self, runner, project_dir):
        bad = "name: workflow\ndescription: Bad\nsteps: \"not a list\"\n"
        source = project_dir / "workflow.yaml"
        source.write_text(bad)
        result = runner.invoke(main, ["doctrine", "new", "workflow", "--from", str(source)])
        assert result.exit_code == 1
        assert not _doctrine_path(project_dir, "workflow").exists()

    def test_empty_steps_rejected(self, runner, project_dir):
        bad = "name: workflow\ndescription: Empty\nsteps: []\n"
        source = project_dir / "workflow.yaml"
        source.write_text(bad)
        result = runner.invoke(main, ["doctrine", "new", "workflow", "--from", str(source)])
        assert result.exit_code == 1

    def test_yaml_parse_error_rejected(self, runner, project_dir):
        source = project_dir / "workflow.yaml"
        source.write_text("name: workflow\ndescription: [unterminated\n")
        result = runner.invoke(main, ["doctrine", "new", "workflow", "--from", str(source)])
        assert result.exit_code == 1

    def test_not_a_mapping_rejected(self, runner, project_dir):
        source = project_dir / "workflow.yaml"
        source.write_text("just a string\n")
        result = runner.invoke(main, ["doctrine", "new", "workflow", "--from", str(source)])
        assert result.exit_code == 1

    def test_cycle_in_steps_rejected(self, runner, project_dir):
        cycle = "name: workflow\ndescription: Cycle\nsteps:\n  - id: a\n    title: A\n    needs: [b]\n  - id: b\n    title: B\n    needs: [a]\n"
        source = project_dir / "workflow.yaml"
        source.write_text(cycle)
        result = runner.invoke(main, ["doctrine", "new", "workflow", "--from", str(source)])
        assert result.exit_code == 1
        assert "cycle" in result.output.lower()

    def test_missing_name_field_rejected(self, runner, project_dir):
        bad = "description: No name\nsteps:\n  - id: a\n    title: A\n"
        source = project_dir / "workflow.yaml"
        source.write_text(bad)
        result = runner.invoke(main, ["doctrine", "new", "workflow", "--from", str(source)])
        assert result.exit_code == 1
        assert "name" in result.output.lower()


class TestDoctrineNewNameMismatch:
    """YAML name field must match the CLI argument."""

    def test_name_mismatch_exits_one(self, runner, project_dir):
        yaml_content = "name: alpha\ndescription: Alpha\nsteps:\n  - id: start\n    title: Start\n"
        source = project_dir / "file.yaml"
        source.write_text(yaml_content)
        result = runner.invoke(main, ["doctrine", "new", "beta", "--from", str(source)])
        assert result.exit_code == 1

    def test_name_mismatch_error_message(self, runner, project_dir):
        yaml_content = "name: alpha\ndescription: Alpha\nsteps:\n  - id: start\n    title: Start\n"
        source = project_dir / "file.yaml"
        source.write_text(yaml_content)
        result = runner.invoke(main, ["doctrine", "new", "beta", "--from", str(source)])
        assert 'Doctrine name "alpha" does not match command argument "beta"' in result.output


class TestDoctrineNewIdMismatch:
    """YAML id field must match the CLI argument when present."""

    def test_id_mismatch_exits_one(self, runner, project_dir):
        yaml_content = "id: wrong-name\nname: right-name\ndescription: Test\nsteps:\n  - id: s\n    title: S\n"
        result = runner.invoke(main, ["doctrine", "new", "right-name"], input=yaml_content)
        assert result.exit_code == 1

    def test_id_mismatch_mentions_wrong_id_in_output(self, runner, project_dir):
        yaml_content = "id: wrong-name\nname: right-name\ndescription: Test\nsteps:\n  - id: s\n    title: S\n"
        result = runner.invoke(main, ["doctrine", "new", "right-name"], input=yaml_content)
        assert "wrong-name" in result.output

    def test_id_mismatch_json_returns_error_key(self, runner, project_dir):
        yaml_content = "id: wrong-name\nname: right-name\ndescription: Test\nsteps:\n  - id: s\n    title: S\n"
        result = runner.invoke(main, ["--json", "doctrine", "new", "right-name"], input=yaml_content)
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert "error" in data

    def test_validate_doctrine_content_raises_on_id_mismatch(self):
        yaml_with_wrong_id = "id: wrong-id\nname: right-name\ndescription: D\nsteps:\n  - id: s\n    title: S\n"
        with pytest.raises(DoctrineError, match="command argument"):
            validate_doctrine_content(yaml_with_wrong_id, "right-name")


class TestDoctrineNewDuplicateName:
    """Creating a doctrine with an existing name fails."""

    def test_duplicate_exits_one(self, runner, project_dir):
        source = project_dir / "workflow.yaml"
        source.write_text(VALID_DOCTRINE_YAML)
        runner.invoke(main, ["doctrine", "new", "workflow", "--from", str(source)])
        result = runner.invoke(main, ["doctrine", "new", "workflow", "--from", str(source)])
        assert result.exit_code == 1

    def test_duplicate_error_mentions_already_exists(self, runner, project_dir):
        source = project_dir / "workflow.yaml"
        source.write_text(VALID_DOCTRINE_YAML)
        runner.invoke(main, ["doctrine", "new", "workflow", "--from", str(source)])
        result = runner.invoke(main, ["doctrine", "new", "workflow", "--from", str(source)])
        assert "already exists" in result.output

    def test_duplicate_default_doctrine_fails(self, runner, project_dir):
        yaml_content = "name: feature-implementation\ndescription: Standard feature development workflow\nsteps:\n  - id: build\n    title: Build\n"
        source = project_dir / "feature-implementation.yaml"
        source.write_text(yaml_content)
        result = runner.invoke(main, ["doctrine", "new", "feature-implementation", "--from", str(source)])
        assert result.exit_code == 1
        assert "already exists" in result.output


class TestDoctrineNewEmptyStdin:
    """Empty or whitespace-only stdin triggers the scaffold path (exit 0)."""

    def test_empty_stdin_exits_zero(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "new", "workflow"], input="")
        assert result.exit_code == 0

    def test_empty_stdin_creates_doctrine_file(self, runner, project_dir):
        runner.invoke(main, ["doctrine", "new", "workflow"], input="")
        assert _doctrine_path(project_dir, "workflow").exists()

    def test_whitespace_only_stdin_scaffolds(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "new", "workflow"], input="   \n\n  ")
        assert result.exit_code == 0


class TestDoctrineNewFileNotFound:
    """--from pointing to a non-existent file fails."""

    def test_file_not_found_exits_one(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "new", "workflow", "--from", "/nonexistent/file.yaml"])
        assert result.exit_code == 1
        assert "File not found" in result.output


class TestDoctrineNewInvalidName:
    """Names that don't match naming rules are rejected."""

    def test_invalid_name_with_space_exits_one(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "new", "my workflow"])
        assert result.exit_code == 1

    def test_invalid_name_error_message(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "new", "my workflow"])
        assert "invalid" in result.output.lower() or "name" in result.output.lower()


class TestDoctrineNewJsonOutput:
    """--json flag produces structured JSON on success."""

    def test_json_output_from_stdin(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "doctrine", "new", "workflow"], input=VALID_DOCTRINE_YAML)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "workflow"
        assert data["filename"] == "workflow.yaml"

    def test_json_error_on_duplicate(self, runner, project_dir):
        source = project_dir / "workflow.yaml"
        source.write_text(VALID_DOCTRINE_YAML)
        runner.invoke(main, ["doctrine", "new", "workflow", "--from", str(source)])
        result = runner.invoke(main, ["--json", "doctrine", "new", "workflow", "--from", str(source)])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert "error" in data


# ---------------------------------------------------------------------------
# New doctrines include metadata fields (new doctrine metadata)
# ---------------------------------------------------------------------------


class TestDoctrineNewMetadataFields:
    """New doctrines with id/title/summary frontmatter fields are written verbatim."""

    def test_doctrine_with_metadata_fields_written_correctly(self, runner, project_dir):
        yaml_with_meta = "id: real-workflow\nname: real-workflow\ntitle: Real Title\nsummary: Real summary\ndescription: A workflow\nsteps:\n  - id: start\n    title: Start\n"
        result = runner.invoke(main, ["doctrine", "new", "real-workflow"], input=yaml_with_meta)
        assert result.exit_code == 0
        content = _doctrine_path(project_dir, "real-workflow").read_text()
        assert "id: real-workflow" in content
        assert "title: Real Title" in content
        assert "summary: Real summary" in content

    def test_doctrine_with_todo_placeholders_is_accepted(self, runner, project_dir):
        yaml_with_todos = "id: my-workflow\nname: my-workflow\ntitle: \"TODO: Replace\"\nsummary: \"TODO: Summary\"\ndescription: Workflow\nsteps:\n  - id: start\n    title: Start\n"
        result = runner.invoke(main, ["doctrine", "new", "my-workflow"], input=yaml_with_todos)
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------


@pytest.fixture()
def existing_doctrine(runner, project_dir):
    """Create an existing doctrine named 'workflow' for edit tests."""
    source = project_dir / "workflow.yaml"
    source.write_text(VALID_DOCTRINE_YAML)
    runner.invoke(main, ["doctrine", "new", "workflow", "--from", str(source)])
    return project_dir


class TestDoctrineEdit:
    """lore doctrine edit replaces doctrine content."""

    def test_edit_from_file_exits_zero(self, runner, existing_doctrine):
        source = existing_doctrine / "updated.yaml"
        source.write_text(UPDATED_DOCTRINE_YAML)
        result = runner.invoke(main, ["doctrine", "edit", "workflow", "--from", str(source)])
        assert result.exit_code == 0

    def test_edit_from_file_replaces_content(self, runner, existing_doctrine):
        source = existing_doctrine / "updated.yaml"
        source.write_text(UPDATED_DOCTRINE_YAML)
        runner.invoke(main, ["doctrine", "edit", "workflow", "--from", str(source)])
        assert _doctrine_path(existing_doctrine, "workflow").read_text() == UPDATED_DOCTRINE_YAML

    def test_edit_from_stdin_exits_zero(self, runner, existing_doctrine):
        result = runner.invoke(main, ["doctrine", "edit", "workflow"], input=UPDATED_DOCTRINE_YAML)
        assert result.exit_code == 0

    def test_edit_from_stdin_replaces_content(self, runner, existing_doctrine):
        runner.invoke(main, ["doctrine", "edit", "workflow"], input=UPDATED_DOCTRINE_YAML)
        assert _doctrine_path(existing_doctrine, "workflow").read_text() == UPDATED_DOCTRINE_YAML

    def test_edit_rejects_invalid_content(self, runner, existing_doctrine):
        bad = "name: workflow\ndescription: Bad\nsteps: \"not a list\"\n"
        source = existing_doctrine / "bad.yaml"
        source.write_text(bad)
        result = runner.invoke(main, ["doctrine", "edit", "workflow", "--from", str(source)])
        assert result.exit_code == 1
        assert _doctrine_path(existing_doctrine, "workflow").read_text() == VALID_DOCTRINE_YAML

    def test_edit_nonexistent_exits_one(self, runner, project_dir):
        valid_yaml = "name: ghost\ndescription: Ghost\nsteps:\n  - id: s\n    title: S\n"
        result = runner.invoke(main, ["doctrine", "edit", "ghost"], input=valid_yaml)
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_edit_name_mismatch_error(self, runner, existing_doctrine):
        mismatch = "name: other\ndescription: Mismatch\nsteps:\n  - id: s\n    title: S\n"
        source = existing_doctrine / "mismatch.yaml"
        source.write_text(mismatch)
        result = runner.invoke(main, ["doctrine", "edit", "workflow", "--from", str(source)])
        assert result.exit_code == 1
        assert 'Doctrine name "other" does not match command argument "workflow"' in result.output


class TestDoctrineEditPreservesFrontmatter:
    """Editing a doctrine preserves its id, title, summary frontmatter fields."""

    @pytest.fixture()
    def doctrine_with_frontmatter(self, runner, project_dir):
        source = project_dir / "patrol.yaml"
        source.write_text(DOCTRINE_WITH_FRONTMATTER)
        runner.invoke(main, ["doctrine", "new", "patrol", "--from", str(source)])
        return project_dir

    def test_id_preserved_after_edit(self, runner, doctrine_with_frontmatter):
        runner.invoke(main, ["doctrine", "edit", "patrol"], input=UPDATED_WITHOUT_FRONTMATTER)
        content = _doctrine_path(doctrine_with_frontmatter, "patrol").read_text()
        assert "id: patrol" in content

    def test_title_preserved_after_edit(self, runner, doctrine_with_frontmatter):
        runner.invoke(main, ["doctrine", "edit", "patrol"], input=UPDATED_WITHOUT_FRONTMATTER)
        content = _doctrine_path(doctrine_with_frontmatter, "patrol").read_text()
        assert "title: Patrol Workflow Title" in content

    def test_summary_preserved_after_edit(self, runner, doctrine_with_frontmatter):
        runner.invoke(main, ["doctrine", "edit", "patrol"], input=UPDATED_WITHOUT_FRONTMATTER)
        content = _doctrine_path(doctrine_with_frontmatter, "patrol").read_text()
        assert "summary: A concise patrol workflow summary" in content

    def test_doctrine_list_shows_original_title_after_edit(self, runner, doctrine_with_frontmatter):
        runner.invoke(main, ["doctrine", "edit", "patrol"], input=UPDATED_WITHOUT_FRONTMATTER)
        result = runner.invoke(main, ["doctrine", "list"])
        assert "Patrol Workflow Title" in result.output

    def test_doctrine_list_shows_original_summary_after_edit(self, runner, doctrine_with_frontmatter):
        runner.invoke(main, ["doctrine", "edit", "patrol"], input=UPDATED_WITHOUT_FRONTMATTER)
        result = runner.invoke(main, ["doctrine", "list"])
        assert "A concise patrol workflow summary" in result.output


# ---------------------------------------------------------------------------
# Delete (soft-delete)
# ---------------------------------------------------------------------------


class TestDoctrineDelete:
    """lore doctrine delete soft-deletes the doctrine file."""

    def test_delete_exits_zero(self, runner, existing_doctrine):
        result = runner.invoke(main, ["doctrine", "delete", "workflow"])
        assert result.exit_code == 0

    def test_delete_creates_deleted_file(self, runner, existing_doctrine):
        runner.invoke(main, ["doctrine", "delete", "workflow"])
        assert _deleted_path(existing_doctrine, "workflow").exists()

    def test_delete_preserves_content_in_deleted_file(self, runner, existing_doctrine):
        runner.invoke(main, ["doctrine", "delete", "workflow"])
        assert _deleted_path(existing_doctrine, "workflow").read_text() == VALID_DOCTRINE_YAML

    def test_delete_removes_active_yaml(self, runner, existing_doctrine):
        runner.invoke(main, ["doctrine", "delete", "workflow"])
        assert not _doctrine_path(existing_doctrine, "workflow").exists()

    def test_doctrine_not_in_list_after_delete(self, runner, existing_doctrine):
        runner.invoke(main, ["doctrine", "delete", "workflow"])
        result = runner.invoke(main, ["doctrine", "list"])
        assert "workflow" not in result.output

    def test_show_after_delete_exits_one(self, runner, existing_doctrine):
        runner.invoke(main, ["doctrine", "delete", "workflow"])
        result = runner.invoke(main, ["doctrine", "show", "workflow"])
        assert result.exit_code == 1

    def test_delete_nonexistent_exits_one(self, runner, existing_doctrine):
        result = runner.invoke(main, ["doctrine", "delete", "ghost"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_re_delete_exits_one(self, runner, existing_doctrine):
        runner.invoke(main, ["doctrine", "delete", "workflow"])
        result = runner.invoke(main, ["doctrine", "delete", "workflow"])
        assert result.exit_code == 1

    def test_json_output_on_delete(self, runner, existing_doctrine):
        result = runner.invoke(main, ["--json", "doctrine", "delete", "workflow"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "workflow"
        assert data["deleted"] is True

    def test_create_after_delete_succeeds(self, runner, existing_doctrine):
        runner.invoke(main, ["doctrine", "delete", "workflow"])
        source = existing_doctrine / "workflow2.yaml"
        source.write_text(VALID_DOCTRINE_YAML)
        result = runner.invoke(main, ["doctrine", "new", "workflow", "--from", str(source)])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Show and validation
# ---------------------------------------------------------------------------


class TestDoctrineShow:
    """lore doctrine show displays full doctrine contents."""

    def test_show_feature_implementation_exits_zero(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "show", "feature-implementation"])
        assert result.exit_code == 0

    def test_show_displays_name(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "show", "feature-implementation"])
        assert "feature-implementation" in result.output

    def test_show_invalid_doctrine_exits_one(self, runner, project_dir):
        _write_doctrine(project_dir, "broken.yaml", """\
name: broken
description: A broken doctrine
steps:
  - id: test
    title: Run tests
    needs: [tset]
""")
        result = runner.invoke(main, ["doctrine", "show", "broken"])
        assert result.exit_code == 1

    def test_show_nonexistent_exits_one(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "show", "nonexistent"])
        assert result.exit_code == 1

    def test_json_show_has_steps(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "doctrine", "show", "feature-implementation"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "steps" in data
        assert isinstance(data["steps"], list)
        assert len(data["steps"]) > 0


# ---------------------------------------------------------------------------
# Step type field
# ---------------------------------------------------------------------------


class TestDoctrineStepType:
    """Doctrine steps accept any string type, or null when absent."""

    def test_knight_type_shown(self, runner, project_dir):
        _write_doctrine(project_dir, "typed.yaml", "name: typed\ndescription: D\nsteps:\n  - id: plan\n    title: Plan\n    type: knight\n")
        result = runner.invoke(main, ["doctrine", "show", "typed"])
        assert "Type: knight" in result.output

    def test_custom_type_accepted(self, runner, project_dir):
        _write_doctrine(project_dir, "custom.yaml", "name: custom\ndescription: D\nsteps:\n  - id: s\n    title: S\n    type: spike\n")
        result = runner.invoke(main, ["doctrine", "show", "custom"])
        assert result.exit_code == 0
        assert "Type: spike" in result.output

    def test_omitted_type_produces_no_type_line(self, runner, project_dir):
        _write_doctrine(project_dir, "notype.yaml", "name: notype\ndescription: D\nsteps:\n  - id: work\n    title: Work\n")
        result = runner.invoke(main, ["doctrine", "show", "notype"])
        assert "Type:" not in result.output

    def test_omitted_type_null_in_json(self, runner, project_dir):
        _write_doctrine(project_dir, "notype-j.yaml", "name: notype-j\ndescription: D\nsteps:\n  - id: work\n    title: Work\n")
        result = runner.invoke(main, ["--json", "doctrine", "show", "notype-j"])
        data = json.loads(result.output)
        assert data["steps"][0]["type"] is None

    def test_integer_type_rejected(self, runner, project_dir):
        _write_doctrine(project_dir, "int-type.yaml", "name: int-type\ndescription: D\nsteps:\n  - id: broken\n    title: Broken\n    type: 42\n")
        result = runner.invoke(main, ["doctrine", "show", "int-type"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# validate_doctrine_content function
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Scaffold path (US-1)
# ---------------------------------------------------------------------------


class TestScaffoldPath:
    # Ref: conceptual-workflows-doctrine-new step 2 (scaffold decision point) and step 3

    def test_scaffold_exits_zero(self, runner, project_dir):
        # Ref: conceptual-workflows-doctrine-new step 3 (TTY path) and step 6
        from unittest.mock import patch
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            result = runner.invoke(main, ["doctrine", "new", "hotfix"])
        assert result.exit_code == 0

    def test_scaffold_file_created_on_disk(self, runner, project_dir):
        # Ref: conceptual-workflows-doctrine-new step 5 (write the file)
        from unittest.mock import patch
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            runner.invoke(main, ["doctrine", "new", "hotfix"])
        assert _doctrine_path(project_dir, "hotfix").exists()

    def test_scaffold_yaml_is_valid(self, runner, project_dir):
        # Ref: conceptual-workflows-doctrine-new step 3 (skeleton is valid YAML)
        import yaml
        from unittest.mock import patch
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            runner.invoke(main, ["doctrine", "new", "hotfix"])
        content = _doctrine_path(project_dir, "hotfix").read_text()
        data = yaml.safe_load(content)
        assert isinstance(data, dict)

    def test_scaffold_contains_required_keys(self, runner, project_dir):
        # Ref: conceptual-workflows-doctrine-new step 3 (skeleton fields: id, title, summary, description, steps)
        import yaml
        from unittest.mock import patch
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            runner.invoke(main, ["doctrine", "new", "hotfix"])
        content = _doctrine_path(project_dir, "hotfix").read_text()
        data = yaml.safe_load(content)
        assert set(data.keys()) == {"id", "title", "summary", "description", "steps"}

    def test_scaffold_id_matches_name_argument(self, runner, project_dir):
        # Ref: conceptual-workflows-doctrine-new step 3 (id must equal name — hard constraint)
        import yaml
        from unittest.mock import patch
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            runner.invoke(main, ["doctrine", "new", "hotfix"])
        content = _doctrine_path(project_dir, "hotfix").read_text()
        data = yaml.safe_load(content)
        assert data["id"] == "hotfix"

    def test_scaffold_title_is_capitalized_name(self, runner, project_dir):
        # Ref: list-enrichment-gaps-tech-spec — scaffold_doctrine() title = name.capitalize()
        import yaml
        from unittest.mock import patch
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            runner.invoke(main, ["doctrine", "new", "hotfix"])
        content = _doctrine_path(project_dir, "hotfix").read_text()
        data = yaml.safe_load(content)
        assert data["title"] == "Hotfix"

    def test_scaffold_steps_is_nonempty_list(self, runner, project_dir):
        # Ref: conceptual-workflows-doctrine-new step 2 (skeleton has one example step)
        import yaml
        from unittest.mock import patch
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            runner.invoke(main, ["doctrine", "new", "hotfix"])
        content = _doctrine_path(project_dir, "hotfix").read_text()
        data = yaml.safe_load(content)
        assert isinstance(data["steps"], list)
        assert len(data["steps"]) > 0

    def test_scaffold_stdout_contains_created_message(self, runner, project_dir):
        # Ref: conceptual-workflows-doctrine-new step 6 (success output: "Created doctrine <name>")
        from unittest.mock import patch
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            result = runner.invoke(main, ["doctrine", "new", "hotfix"])
        assert "Created doctrine hotfix" in result.output

    def test_scaffold_conflict_guard_exits_one(self, runner, project_dir):
        # Ref: conceptual-workflows-doctrine-new step 1 (edit vs create decision point)
        # Ref: conceptual-workflows-doctrine-new step 2 (duplicate check)
        # Must exit 1 with the PRD-specified message (not the old "No content" error)
        from unittest.mock import patch
        _write_doctrine(project_dir, "hotfix.yaml", VALID_DOCTRINE_YAML)
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            result = runner.invoke(main, ["doctrine", "new", "hotfix"])
        assert result.exit_code == 1
        assert "Error: doctrine 'hotfix' already exists. Use 'lore doctrine edit hotfix' to modify it." in result.output

    def test_scaffold_conflict_guard_message(self, runner, project_dir):
        # Ref: conceptual-workflows-doctrine-new step 2 (error message form)
        from unittest.mock import patch
        _write_doctrine(project_dir, "hotfix.yaml", VALID_DOCTRINE_YAML)
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            result = runner.invoke(main, ["doctrine", "new", "hotfix"])
        assert "Error: doctrine 'hotfix' already exists. Use 'lore doctrine edit hotfix' to modify it." in result.output

    def test_scaffold_conflict_guard_does_not_overwrite(self, runner, project_dir):
        # Ref: conceptual-workflows-doctrine-new step 2 (no file written on conflict)
        # Must show conflict message (not "No content provided") — scaffold path conflict detection
        from unittest.mock import patch
        _write_doctrine(project_dir, "hotfix.yaml", VALID_DOCTRINE_YAML)
        original_content = _doctrine_path(project_dir, "hotfix").read_text()
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            result = runner.invoke(main, ["doctrine", "new", "hotfix"])
        assert _doctrine_path(project_dir, "hotfix").read_text() == original_content
        assert "Error: doctrine 'hotfix' already exists. Use 'lore doctrine edit hotfix' to modify it." in result.output

    def test_scaffold_creates_parent_directory(self, runner, project_dir):
        # Ref: conceptual-workflows-doctrine-new step 5 (mkdir parents=True, exist_ok=True)
        import shutil
        from unittest.mock import patch
        doctrines_dir = project_dir / ".lore" / "doctrines"
        shutil.rmtree(doctrines_dir)
        assert not doctrines_dir.exists()
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            runner.invoke(main, ["doctrine", "new", "my-flow"])
        assert doctrines_dir.exists()
        assert (doctrines_dir / "my-flow.yaml").exists()

    def test_scaffold_rglob_catches_subdirectory_conflict(self, runner, project_dir):
        # Ref: conceptual-workflows-doctrine-new step 2 (rglob duplicate check)
        # Must produce the PRD-specified error message form, not "No content provided"
        from unittest.mock import patch
        subdir = project_dir / ".lore" / "doctrines" / "default"
        subdir.mkdir(parents=True, exist_ok=True)
        (subdir / "hotfix.yaml").write_text(VALID_DOCTRINE_YAML)
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            result = runner.invoke(main, ["doctrine", "new", "hotfix"])
        assert result.exit_code == 1
        assert "Error: doctrine 'hotfix' already exists. Use 'lore doctrine edit hotfix' to modify it." in result.output

    def test_nontty_stdin_takes_validation_path_not_scaffold(self, runner, project_dir):
        # Ref: conceptual-workflows-doctrine-new step 3 (non-TTY stdin → existing path)
        yaml_content = (
            "id: my-flow\n"
            "title: \"My Flow\"\n"
            "summary: \"A test doctrine.\"\n"
            "description: \"Longer description.\"\n"
            "steps:\n"
            "  - name: \"Step One\"\n"
            "    description: \"Do the thing.\"\n"
        )
        result = runner.invoke(main, ["doctrine", "new", "my-flow"], input=yaml_content)
        assert result.exit_code == 0
        assert _doctrine_path(project_dir, "my-flow").exists()
        content = _doctrine_path(project_dir, "my-flow").read_text()
        assert content == yaml_content


# ---------------------------------------------------------------------------
# validate_doctrine_content function
# ---------------------------------------------------------------------------


class TestValidateDoctrineContent:
    """The validate_doctrine_content function validates raw YAML text."""

    def test_accepts_valid_content(self):
        validate_doctrine_content(VALID_DOCTRINE_YAML, "workflow")

    def test_rejects_name_mismatch(self):
        with pytest.raises(DoctrineError, match="does not match command argument"):
            validate_doctrine_content(VALID_DOCTRINE_YAML, "other-name")

    def test_rejects_missing_name(self):
        bad = "description: test\nsteps:\n  - id: a\n    title: A\n"
        with pytest.raises(DoctrineError, match="name"):
            validate_doctrine_content(bad, "test")

    def test_rejects_id_mismatch(self):
        yaml_with_wrong_id = "id: wrong-id\nname: right-name\ndescription: D\nsteps:\n  - id: s\n    title: S\n"
        with pytest.raises(DoctrineError, match="command argument"):
            validate_doctrine_content(yaml_with_wrong_id, "right-name")

    def test_rejects_bad_yaml(self):
        with pytest.raises(DoctrineError):
            validate_doctrine_content("not: [valid yaml", "test")
