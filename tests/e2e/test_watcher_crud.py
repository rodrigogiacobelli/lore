"""E2E tests for the watcher new, edit, and delete commands — Workflows 3, 4, 5.

Spec: conceptual-workflows-watcher-crud (lore codex show conceptual-workflows-watcher-crud)
User stories: watchers-us-3, watchers-us-4, watchers-us-5
"""

import json

from lore.cli import main

VALID_YAML = (
    "id: run-tests-on-push\n"
    "title: Run Tests\n"
    "summary: Triggers test suite on push\n"
    "watch_target:\n"
    "  - feature/*\n"
    "interval: on_merge\n"
    "action:\n"
    "  - bash: run-tests\n"
)


# ---------------------------------------------------------------------------
# Scenario 1: Create watcher — stdin, happy path
# ---------------------------------------------------------------------------


class TestWatcherNewStdin:
    """Scenario 1: watcher new reads content from stdin and creates the file."""

    def test_watcher_new_stdin_exits_zero(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 1 — exit code 0 on success
        result = runner.invoke(
            main, ["watcher", "new", "run-tests-on-push"], input=VALID_YAML
        )
        assert result.exit_code == 0

    def test_watcher_new_stdin_stdout_message(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 1 — stdout contains "Created watcher run-tests-on-push"
        result = runner.invoke(
            main, ["watcher", "new", "run-tests-on-push"], input=VALID_YAML
        )
        assert "Created watcher run-tests-on-push" in result.output

    def test_watcher_new_stdin_file_exists(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 1 — file is written to .lore/watchers/run-tests-on-push.yaml
        runner.invoke(
            main, ["watcher", "new", "run-tests-on-push"], input=VALID_YAML
        )
        watcher_file = project_dir / ".lore" / "watchers" / "run-tests-on-push.yaml"
        assert watcher_file.exists()

    def test_watcher_new_stdin_file_content_matches_input(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 1 — file content matches provided YAML
        runner.invoke(
            main, ["watcher", "new", "run-tests-on-push"], input=VALID_YAML
        )
        watcher_file = project_dir / ".lore" / "watchers" / "run-tests-on-push.yaml"
        assert watcher_file.read_text() == VALID_YAML


# ---------------------------------------------------------------------------
# Scenario 2: Create watcher — --from <file>, happy path
# ---------------------------------------------------------------------------


class TestWatcherNewFromFile:
    """Scenario 2: watcher new reads content from --from <file>."""

    def test_watcher_new_from_file_exits_zero(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 2 — exit code 0 on success
        source = project_dir / "watcher.yaml"
        source.write_text(VALID_YAML)
        result = runner.invoke(
            main, ["watcher", "new", "run-tests-on-push", "--from", str(source)]
        )
        assert result.exit_code == 0

    def test_watcher_new_from_file_stdout_message(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 2 — stdout contains "Created watcher run-tests-on-push"
        source = project_dir / "watcher.yaml"
        source.write_text(VALID_YAML)
        result = runner.invoke(
            main, ["watcher", "new", "run-tests-on-push", "--from", str(source)]
        )
        assert "Created watcher run-tests-on-push" in result.output

    def test_watcher_new_from_file_creates_watcher_file(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 2 — .lore/watchers/run-tests-on-push.yaml exists
        source = project_dir / "watcher.yaml"
        source.write_text(VALID_YAML)
        runner.invoke(
            main, ["watcher", "new", "run-tests-on-push", "--from", str(source)]
        )
        watcher_file = project_dir / ".lore" / "watchers" / "run-tests-on-push.yaml"
        assert watcher_file.exists()


# ---------------------------------------------------------------------------
# Scenario 3: Create watcher — duplicate name rejected
# ---------------------------------------------------------------------------


class TestWatcherNewDuplicate:
    """Scenario 3: duplicate name is rejected with error on stderr, exit code 1."""

    def test_watcher_new_duplicate_exits_one(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 3 — exit code 1 when name already exists
        watchers_dir = project_dir / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "run-tests-on-push.yaml").write_text(VALID_YAML)
        result = runner.invoke(
            main, ["watcher", "new", "run-tests-on-push"], input=VALID_YAML
        )
        assert result.exit_code == 1

    def test_watcher_new_duplicate_stderr_message(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 3 — stderr contains 'Watcher "run-tests-on-push" already exists.'
        watchers_dir = project_dir / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "run-tests-on-push.yaml").write_text(VALID_YAML)
        result = runner.invoke(
            main,
            ["watcher", "new", "run-tests-on-push"],
            input=VALID_YAML,
            catch_exceptions=False,
        )
        output = (result.output or "") + (result.stderr if hasattr(result, "stderr") else "")
        assert 'Watcher "run-tests-on-push" already exists.' in output

    def test_watcher_new_duplicate_does_not_overwrite_file(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 3 — existing file is not overwritten
        watchers_dir = project_dir / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        original_content = VALID_YAML
        watcher_file = watchers_dir / "run-tests-on-push.yaml"
        watcher_file.write_text(original_content)
        new_content = "id: run-tests-on-push\ntitle: Different\nsummary: Changed\n"
        runner.invoke(
            main, ["watcher", "new", "run-tests-on-push"], input=new_content
        )
        assert watcher_file.read_text() == original_content


# ---------------------------------------------------------------------------
# Scenario 4: Create watcher — invalid name rejected before filesystem access
# ---------------------------------------------------------------------------


class TestWatcherNewInvalidName:
    """Scenario 4: invalid name is rejected before any filesystem access."""

    def test_watcher_new_invalid_name_exits_one(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 4 — exit code 1 for name with spaces
        result = runner.invoke(
            main, ["watcher", "new", "invalid name with spaces"], input=VALID_YAML
        )
        assert result.exit_code == 1

    def test_watcher_new_invalid_name_error_message(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 4 — error message mentions invalid name and pattern
        result = runner.invoke(
            main, ["watcher", "new", "invalid name with spaces"], input=VALID_YAML
        )
        output = (result.output or "") + (result.stderr if hasattr(result, "stderr") else "")
        assert "invalid name with spaces" in output
        assert "invalid" in output.lower() or "^[a-zA-Z0-9]" in output

    def test_watcher_new_invalid_name_no_file_created(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 4 — watchers/ directory is not modified
        runner.invoke(
            main, ["watcher", "new", "invalid name with spaces"], input=VALID_YAML
        )
        watchers_dir = project_dir / ".lore" / "watchers"
        # No file should exist with the invalid name
        if watchers_dir.exists():
            yaml_files = list(watchers_dir.rglob("*.yaml"))
            assert not any("invalid" in f.stem for f in yaml_files)


# ---------------------------------------------------------------------------
# Scenario 5: Create watcher — empty stdin rejected
# ---------------------------------------------------------------------------


class TestWatcherNewEmptyStdin:
    """Scenario 5: empty stdin is rejected with error, exit code 1."""

    def test_watcher_new_empty_stdin_exits_one(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 5 — exit code 1 for empty stdin
        result = runner.invoke(
            main, ["watcher", "new", "my-watcher"], input=""
        )
        assert result.exit_code == 1

    def test_watcher_new_empty_stdin_error_message(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 5 — stderr contains "No content provided on stdin."
        result = runner.invoke(
            main, ["watcher", "new", "my-watcher"], input=""
        )
        output = (result.output or "") + (result.stderr if hasattr(result, "stderr") else "")
        assert "No content provided on stdin." in output

    def test_watcher_new_empty_stdin_no_file_written(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 5 — no file is written on empty stdin
        runner.invoke(main, ["watcher", "new", "my-watcher"], input="")
        watcher_file = project_dir / ".lore" / "watchers" / "my-watcher.yaml"
        assert not watcher_file.exists()


# ---------------------------------------------------------------------------
# Scenario 6: Create watcher — --from file not found
# ---------------------------------------------------------------------------


class TestWatcherNewFromFileMissing:
    """Scenario 6: --from with a non-existent file produces error, exit code 1."""

    def test_watcher_new_from_missing_file_exits_one(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 6 — exit code 1 when --from file does not exist
        result = runner.invoke(
            main, ["watcher", "new", "my-watcher", "--from", "nonexistent.yaml"]
        )
        assert result.exit_code == 1

    def test_watcher_new_from_missing_file_error_message(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 6 — stderr contains "File not found: nonexistent.yaml"
        result = runner.invoke(
            main, ["watcher", "new", "my-watcher", "--from", "nonexistent.yaml"]
        )
        output = (result.output or "") + (result.stderr if hasattr(result, "stderr") else "")
        assert "File not found: nonexistent.yaml" in output

    def test_watcher_new_from_missing_file_no_file_written(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 6 — no file is written
        runner.invoke(
            main, ["watcher", "new", "my-watcher", "--from", "nonexistent.yaml"]
        )
        watcher_file = project_dir / ".lore" / "watchers" / "my-watcher.yaml"
        assert not watcher_file.exists()


# ---------------------------------------------------------------------------
# Scenario 7: Create watcher — invalid YAML content rejected
# ---------------------------------------------------------------------------


class TestWatcherNewInvalidYaml:
    """Scenario 7: invalid YAML content is rejected before writing to disk."""

    INVALID_YAML = ": invalid: yaml: ["

    def test_watcher_new_invalid_yaml_exits_one(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 7 — exit code 1 for invalid YAML
        result = runner.invoke(
            main, ["watcher", "new", "bad-watcher"], input=self.INVALID_YAML
        )
        assert result.exit_code == 1

    def test_watcher_new_invalid_yaml_error_message(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 7 — stderr contains YAML error indication
        result = runner.invoke(
            main, ["watcher", "new", "bad-watcher"], input=self.INVALID_YAML
        )
        output = (result.output or "") + (result.stderr if hasattr(result, "stderr") else "")
        # Error must indicate content is not valid YAML
        assert any(
            keyword in output.lower()
            for keyword in ("yaml", "invalid", "parse", "content")
        )

    def test_watcher_new_invalid_yaml_no_file_written(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 7 — no file is written when YAML is invalid
        runner.invoke(
            main, ["watcher", "new", "bad-watcher"], input=self.INVALID_YAML
        )
        watcher_file = project_dir / ".lore" / "watchers" / "bad-watcher.yaml"
        assert not watcher_file.exists()


# ---------------------------------------------------------------------------
# Scenario 8: Create watcher — JSON mode success
# ---------------------------------------------------------------------------


class TestWatcherNewJson:
    """Scenario 8: --json flag returns structured confirmation object."""

    def test_watcher_new_json_exits_zero(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 8 — exit code 0 in JSON mode
        result = runner.invoke(
            main,
            ["watcher", "new", "run-tests-on-push", "--json"],
            input=VALID_YAML,
        )
        assert result.exit_code == 0

    def test_watcher_new_json_output_is_valid_json(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 8 — stdout is parseable JSON
        result = runner.invoke(
            main,
            ["watcher", "new", "run-tests-on-push", "--json"],
            input=VALID_YAML,
        )
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_watcher_new_json_output_has_id_key(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 8 — JSON output contains "id" key
        result = runner.invoke(
            main,
            ["watcher", "new", "run-tests-on-push", "--json"],
            input=VALID_YAML,
        )
        data = json.loads(result.output)
        assert data["id"] == "run-tests-on-push"

    def test_watcher_new_json_output_has_filename_key(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 8 — JSON output contains "filename" key
        result = runner.invoke(
            main,
            ["watcher", "new", "run-tests-on-push", "--json"],
            input=VALID_YAML,
        )
        data = json.loads(result.output)
        assert data["filename"] == "run-tests-on-push.yaml"


# ---------------------------------------------------------------------------
# Scenario 9: Create watcher — creates .lore/watchers/ directory if absent
# ---------------------------------------------------------------------------


class TestWatcherNewCreatesDirectory:
    """Scenario 9: creates .lore/watchers/ when it does not exist."""

    def test_watcher_new_creates_watchers_dir(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 9 — .lore/watchers/ is created if absent
        watchers_dir = project_dir / ".lore" / "watchers"
        # Ensure it does not exist before the test
        import shutil
        if watchers_dir.exists():
            shutil.rmtree(watchers_dir)
        assert not watchers_dir.exists()
        result = runner.invoke(
            main, ["watcher", "new", "run-tests-on-push"], input=VALID_YAML
        )
        assert result.exit_code == 0
        assert watchers_dir.exists()

    def test_watcher_new_creates_watchers_dir_and_file(self, runner, project_dir):
        # Spec: watchers-us-3 Scenario 9 — file is written inside newly created dir
        watchers_dir = project_dir / ".lore" / "watchers"
        import shutil
        if watchers_dir.exists():
            shutil.rmtree(watchers_dir)
        runner.invoke(
            main, ["watcher", "new", "run-tests-on-push"], input=VALID_YAML
        )
        watcher_file = watchers_dir / "run-tests-on-push.yaml"
        assert watcher_file.exists()


# ===========================================================================
# Workflow 4: watcher edit — US-4
# ===========================================================================


EDIT_YAML = (
    "id: my-watcher\n"
    "title: My Watcher\n"
    "summary: Updated summary\n"
    "watch_target: feature/*\n"
    "interval: daily\n"
    "action: new-action\n"
)

ORIGINAL_YAML = (
    "id: my-watcher\n"
    "title: My Watcher\n"
    "summary: Original summary\n"
    "watch_target: feature/*\n"
    "interval: daily\n"
    "action: run-checks\n"
)


def _make_existing_watcher(project_dir, subdir="default", name="my-watcher"):
    """Helper: create a watcher file at .lore/watchers/{subdir}/{name}.yaml."""
    watchers_dir = project_dir / ".lore" / "watchers" / subdir
    watchers_dir.mkdir(parents=True, exist_ok=True)
    watcher_file = watchers_dir / f"{name}.yaml"
    watcher_file.write_text(ORIGINAL_YAML)
    return watcher_file


# ---------------------------------------------------------------------------
# Scenario 1: Edit watcher — stdin, happy path
# ---------------------------------------------------------------------------


class TestWatcherEditStdin:
    """Scenario 1: watcher edit reads content from stdin and overwrites the file."""

    def test_watcher_edit_stdin_exits_zero(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 1 — exit code 0 on success
        _make_existing_watcher(project_dir)
        result = runner.invoke(
            main, ["watcher", "edit", "my-watcher"], input=EDIT_YAML
        )
        assert result.exit_code == 0

    def test_watcher_edit_stdin_stdout_message(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 1 — stdout contains "Updated watcher my-watcher"
        _make_existing_watcher(project_dir)
        result = runner.invoke(
            main, ["watcher", "edit", "my-watcher"], input=EDIT_YAML
        )
        assert "Updated watcher my-watcher" in result.output

    def test_watcher_edit_stdin_file_content_replaced(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 1 — file content is replaced with new YAML
        watcher_file = _make_existing_watcher(project_dir)
        runner.invoke(
            main, ["watcher", "edit", "my-watcher"], input=EDIT_YAML
        )
        assert watcher_file.read_text() == EDIT_YAML

    def test_watcher_edit_stdin_file_remains_at_same_path(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 1 — file is NOT moved to a different path
        watcher_file = _make_existing_watcher(project_dir)
        runner.invoke(
            main, ["watcher", "edit", "my-watcher"], input=EDIT_YAML
        )
        assert watcher_file.exists()
        assert watcher_file.parent.name == "default"


# ---------------------------------------------------------------------------
# Scenario 2: Edit watcher — --from <file>, happy path
# ---------------------------------------------------------------------------


class TestWatcherEditFromFile:
    """Scenario 2: watcher edit reads content from --from <file>."""

    def test_watcher_edit_from_file_exits_zero(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 2 — exit code 0 on success
        _make_existing_watcher(project_dir)
        source = project_dir / "updated.yaml"
        source.write_text(EDIT_YAML)
        result = runner.invoke(
            main,
            ["watcher", "edit", "my-watcher", "--from", str(source)],
        )
        assert result.exit_code == 0

    def test_watcher_edit_from_file_stdout_message(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 2 — stdout contains "Updated watcher my-watcher"
        _make_existing_watcher(project_dir)
        source = project_dir / "updated.yaml"
        source.write_text(EDIT_YAML)
        result = runner.invoke(
            main,
            ["watcher", "edit", "my-watcher", "--from", str(source)],
        )
        assert "Updated watcher my-watcher" in result.output

    def test_watcher_edit_from_file_content_replaced(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 2 — file content is replaced
        watcher_file = _make_existing_watcher(project_dir)
        source = project_dir / "updated.yaml"
        source.write_text(EDIT_YAML)
        runner.invoke(
            main,
            ["watcher", "edit", "my-watcher", "--from", str(source)],
        )
        assert watcher_file.read_text() == EDIT_YAML


# ---------------------------------------------------------------------------
# Scenario 3: Edit watcher — not found
# ---------------------------------------------------------------------------


class TestWatcherEditNotFound:
    """Scenario 3: not-found error on stderr, exit code 1."""

    def test_watcher_edit_not_found_exits_one(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 3 — exit code 1 when watcher does not exist
        result = runner.invoke(
            main, ["watcher", "edit", "nonexistent"], input=EDIT_YAML
        )
        assert result.exit_code == 1

    def test_watcher_edit_not_found_stderr_message(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 3 — stderr contains 'Watcher "nonexistent" not found.'
        result = runner.invoke(
            main,
            ["watcher", "edit", "nonexistent"],
            input=EDIT_YAML,
            catch_exceptions=False,
        )
        output = (result.output or "") + (result.stderr if hasattr(result, "stderr") else "")
        assert 'Watcher "nonexistent" not found' in output

    def test_watcher_edit_not_found_no_files_modified(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 3 — no files are created or modified
        watcher_file = project_dir / ".lore" / "watchers" / "nonexistent.yaml"
        runner.invoke(main, ["watcher", "edit", "nonexistent"], input=EDIT_YAML)
        assert not watcher_file.exists()


# ---------------------------------------------------------------------------
# Scenario 4: Edit watcher — empty stdin rejected
# ---------------------------------------------------------------------------


class TestWatcherEditEmptyStdin:
    """Scenario 4: empty stdin is rejected; existing file is unchanged."""

    def test_watcher_edit_empty_stdin_exits_one(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 4 — exit code 1 for empty stdin
        _make_existing_watcher(project_dir)
        result = runner.invoke(
            main, ["watcher", "edit", "my-watcher"], input=""
        )
        assert result.exit_code == 1

    def test_watcher_edit_empty_stdin_error_message(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 4 — stderr contains "No content provided on stdin."
        _make_existing_watcher(project_dir)
        result = runner.invoke(
            main, ["watcher", "edit", "my-watcher"], input=""
        )
        output = (result.output or "") + (result.stderr if hasattr(result, "stderr") else "")
        assert "No content provided on stdin." in output

    def test_watcher_edit_empty_stdin_file_unchanged(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 4 — existing file content is not modified
        watcher_file = _make_existing_watcher(project_dir)
        runner.invoke(
            main, ["watcher", "edit", "my-watcher"], input=""
        )
        assert watcher_file.read_text() == ORIGINAL_YAML


# ---------------------------------------------------------------------------
# Scenario 5: Edit watcher — invalid YAML rejected before write
# ---------------------------------------------------------------------------


class TestWatcherEditInvalidYaml:
    """Scenario 5: invalid YAML content is rejected; existing file is unchanged."""

    INVALID_YAML = ": invalid: ["

    def test_watcher_edit_invalid_yaml_exits_one(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 5 — exit code 1 for invalid YAML
        _make_existing_watcher(project_dir)
        result = runner.invoke(
            main,
            ["watcher", "edit", "my-watcher"],
            input=self.INVALID_YAML,
        )
        assert result.exit_code == 1

    def test_watcher_edit_invalid_yaml_error_message(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 5 — stderr indicates content is not valid YAML
        _make_existing_watcher(project_dir)
        result = runner.invoke(
            main,
            ["watcher", "edit", "my-watcher"],
            input=self.INVALID_YAML,
        )
        output = (result.output or "") + (result.stderr if hasattr(result, "stderr") else "")
        assert any(
            keyword in output.lower()
            for keyword in ("yaml", "invalid", "parse", "content")
        )

    def test_watcher_edit_invalid_yaml_file_unchanged(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 5 — existing file is NOT modified when YAML is invalid
        watcher_file = _make_existing_watcher(project_dir)
        runner.invoke(
            main,
            ["watcher", "edit", "my-watcher"],
            input=self.INVALID_YAML,
        )
        assert watcher_file.read_text() == ORIGINAL_YAML


# ---------------------------------------------------------------------------
# Scenario 6: Edit watcher — JSON mode success
# ---------------------------------------------------------------------------


class TestWatcherEditJson:
    """Scenario 6: --json flag returns structured confirmation object."""

    def test_watcher_edit_json_exits_zero(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 6 — exit code 0 in JSON mode
        _make_existing_watcher(project_dir)
        result = runner.invoke(
            main,
            ["watcher", "edit", "my-watcher", "--json"],
            input=EDIT_YAML,
        )
        assert result.exit_code == 0

    def test_watcher_edit_json_output_is_valid_json(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 6 — stdout is parseable JSON
        _make_existing_watcher(project_dir)
        result = runner.invoke(
            main,
            ["watcher", "edit", "my-watcher", "--json"],
            input=EDIT_YAML,
        )
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_watcher_edit_json_output_has_id_key(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 6 — JSON output contains "id" key
        _make_existing_watcher(project_dir)
        result = runner.invoke(
            main,
            ["watcher", "edit", "my-watcher", "--json"],
            input=EDIT_YAML,
        )
        data = json.loads(result.output)
        assert data["id"] == "my-watcher"

    def test_watcher_edit_json_output_has_filename_key(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 6 — JSON output contains "filename" key
        _make_existing_watcher(project_dir)
        result = runner.invoke(
            main,
            ["watcher", "edit", "my-watcher", "--json"],
            input=EDIT_YAML,
        )
        data = json.loads(result.output)
        assert data["filename"] == "my-watcher.yaml"


# ---------------------------------------------------------------------------
# Scenario 7: Edit watcher in subdirectory group located by name alone
# ---------------------------------------------------------------------------


class TestWatcherEditSubdirectoryGroup:
    """Scenario 7: rglob finds watcher in a subdirectory group; file stays in place."""

    def test_watcher_edit_subdir_exits_zero(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 7 — exit code 0 when watcher is in a subdirectory
        _make_existing_watcher(project_dir, subdir="ci", name="run-tests")
        result = runner.invoke(
            main, ["watcher", "edit", "run-tests"], input=EDIT_YAML
        )
        assert result.exit_code == 0

    def test_watcher_edit_subdir_stdout_message(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 7 — stdout contains "Updated watcher run-tests"
        _make_existing_watcher(project_dir, subdir="ci", name="run-tests")
        result = runner.invoke(
            main, ["watcher", "edit", "run-tests"], input=EDIT_YAML
        )
        assert "Updated watcher run-tests" in result.output

    def test_watcher_edit_subdir_file_overwritten_in_place(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 7 — .lore/watchers/ci/run-tests.yaml is overwritten
        watcher_file = _make_existing_watcher(project_dir, subdir="ci", name="run-tests")
        runner.invoke(main, ["watcher", "edit", "run-tests"], input=EDIT_YAML)
        assert watcher_file.exists()
        assert watcher_file.read_text() == EDIT_YAML

    def test_watcher_edit_subdir_file_not_moved_to_root(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 7 — file is NOT moved to watchers root
        _make_existing_watcher(project_dir, subdir="ci", name="run-tests")
        runner.invoke(main, ["watcher", "edit", "run-tests"], input=EDIT_YAML)
        root_file = project_dir / ".lore" / "watchers" / "run-tests.yaml"
        ci_file = project_dir / ".lore" / "watchers" / "ci" / "run-tests.yaml"
        assert not root_file.exists()
        assert ci_file.exists()
        assert ci_file.parent.name == "ci"


# ---------------------------------------------------------------------------
# Scenario 8: Edit watcher — not found, JSON mode
# ---------------------------------------------------------------------------


class TestWatcherEditNotFoundJson:
    """Scenario 8: not-found error in JSON mode appears on stderr."""

    def test_watcher_edit_not_found_json_exits_one(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 8 — exit code 1 in JSON mode when not found
        result = runner.invoke(
            main,
            ["watcher", "edit", "nonexistent", "--json"],
            input=EDIT_YAML,
        )
        assert result.exit_code == 1

    def test_watcher_edit_not_found_json_stderr_contains_json_error(self, runner, project_dir):
        # Spec: watchers-us-4 Scenario 8 — stderr contains JSON error object
        result = runner.invoke(
            main,
            ["watcher", "edit", "nonexistent", "--json"],
            input=EDIT_YAML,
            catch_exceptions=False,
        )
        output = (result.output or "") + (result.stderr if hasattr(result, "stderr") else "")
        error_data = json.loads(output.strip())
        assert "error" in error_data
        assert "nonexistent" in error_data["error"]


# ===========================================================================
# Workflow 5: watcher delete — US-5
# ===========================================================================


DELETE_WATCHER_YAML = (
    "id: run-tests-on-push\n"
    "title: Run Tests\n"
    "summary: Triggers test suite on push\n"
    "watch_target: feature/*\n"
    "interval: on_push\n"
    "action: run-tests\n"
)


def _make_flat_watcher(project_dir, name="run-tests-on-push", content=None):
    """Helper: create a watcher file at .lore/watchers/{name}.yaml (flat, no subdir)."""
    watchers_dir = project_dir / ".lore" / "watchers"
    watchers_dir.mkdir(parents=True, exist_ok=True)
    watcher_file = watchers_dir / f"{name}.yaml"
    watcher_file.write_text(content or DELETE_WATCHER_YAML)
    return watcher_file


def _make_subdir_watcher(project_dir, subdir, name, content=None):
    """Helper: create a watcher file at .lore/watchers/{subdir}/{name}.yaml."""
    watchers_dir = project_dir / ".lore" / "watchers" / subdir
    watchers_dir.mkdir(parents=True, exist_ok=True)
    watcher_file = watchers_dir / f"{name}.yaml"
    watcher_file.write_text(content or DELETE_WATCHER_YAML)
    return watcher_file


# ---------------------------------------------------------------------------
# Scenario 1: Delete watcher — happy path
# ---------------------------------------------------------------------------


class TestWatcherDeleteHappyPath:
    """Scenario 1: soft-delete renames .yaml to .yaml.deleted; exit 0."""

    def test_watcher_delete_exits_zero(self, runner, project_dir):
        # Spec: watchers-us-5 Scenario 1 — exit code 0 on success
        _make_flat_watcher(project_dir)
        result = runner.invoke(main, ["watcher", "delete", "run-tests-on-push"])
        assert result.exit_code == 0

    def test_watcher_delete_stdout_message(self, runner, project_dir):
        # Spec: watchers-us-5 Scenario 1 — stdout is "Deleted watcher run-tests-on-push"
        _make_flat_watcher(project_dir)
        result = runner.invoke(main, ["watcher", "delete", "run-tests-on-push"])
        assert "Deleted watcher run-tests-on-push" in result.output

    def test_watcher_delete_deleted_file_exists(self, runner, project_dir):
        # Spec: watchers-us-5 Scenario 1 — .yaml.deleted file exists after deletion
        _make_flat_watcher(project_dir)
        runner.invoke(main, ["watcher", "delete", "run-tests-on-push"])
        deleted_file = project_dir / ".lore" / "watchers" / "run-tests-on-push.yaml.deleted"
        assert deleted_file.exists()

    def test_watcher_delete_original_yaml_absent(self, runner, project_dir):
        # Spec: watchers-us-5 Scenario 1 — original .yaml file does not exist after deletion
        _make_flat_watcher(project_dir)
        runner.invoke(main, ["watcher", "delete", "run-tests-on-push"])
        original_file = project_dir / ".lore" / "watchers" / "run-tests-on-push.yaml"
        assert not original_file.exists()


# ---------------------------------------------------------------------------
# Scenario 2: Delete watcher — no longer appears in list
# ---------------------------------------------------------------------------


class TestWatcherDeleteInvisibleToList:
    """Scenario 2: deleted watcher does not appear in lore watcher list."""

    def test_watcher_delete_invisible_to_list(self, runner, project_dir):
        # Spec: watchers-us-5 Scenario 2 — run-tests-on-push absent from list after delete
        _make_flat_watcher(project_dir)
        runner.invoke(main, ["watcher", "delete", "run-tests-on-push"])
        list_result = runner.invoke(main, ["watcher", "list"])
        assert list_result.exit_code == 0
        assert "run-tests-on-push" not in list_result.output

    def test_watcher_delete_list_exits_zero_after_delete(self, runner, project_dir):
        # Spec: watchers-us-5 Scenario 2 — lore watcher list exit code 0 after delete
        _make_flat_watcher(project_dir)
        runner.invoke(main, ["watcher", "delete", "run-tests-on-push"])
        list_result = runner.invoke(main, ["watcher", "list"])
        assert list_result.exit_code == 0


# ---------------------------------------------------------------------------
# Scenario 3: Delete watcher — not found, plain mode
# ---------------------------------------------------------------------------


class TestWatcherDeleteNotFound:
    """Scenario 3: not-found error on stderr, exit code 1, no files modified."""

    def test_watcher_delete_not_found_exits_one(self, runner, project_dir):
        # Spec: watchers-us-5 Scenario 3 — exit code 1 when watcher does not exist
        result = runner.invoke(main, ["watcher", "delete", "nonexistent"])
        assert result.exit_code == 1

    def test_watcher_delete_not_found_stderr_message(self, runner, project_dir):
        # Spec: watchers-us-5 Scenario 3 — stderr contains 'Watcher "nonexistent" not found in .lore/watchers/'
        result = runner.invoke(
            main,
            ["watcher", "delete", "nonexistent"],
            catch_exceptions=False,
        )
        output = (result.output or "") + (result.stderr if hasattr(result, "stderr") else "")
        assert 'Watcher "nonexistent" not found in .lore/watchers/' in output

    def test_watcher_delete_not_found_no_files_created(self, runner, project_dir):
        # Spec: watchers-us-5 Scenario 3 — no files are created or modified
        runner.invoke(main, ["watcher", "delete", "nonexistent"])
        watchers_dir = project_dir / ".lore" / "watchers"
        deleted_candidates = list(watchers_dir.rglob("nonexistent*")) if watchers_dir.exists() else []
        assert deleted_candidates == []


# ---------------------------------------------------------------------------
# Scenario 4: Delete watcher — JSON mode success
# ---------------------------------------------------------------------------


class TestWatcherDeleteJson:
    """Scenario 4: --json flag returns {"id": ..., "deleted": true} on success."""

    def test_watcher_delete_json_exits_zero(self, runner, project_dir):
        # Spec: watchers-us-5 Scenario 4 — exit code 0 in JSON mode
        _make_flat_watcher(project_dir)
        result = runner.invoke(main, ["watcher", "delete", "run-tests-on-push", "--json"])
        assert result.exit_code == 0

    def test_watcher_delete_json_output_is_valid_json(self, runner, project_dir):
        # Spec: watchers-us-5 Scenario 4 — stdout is parseable JSON
        _make_flat_watcher(project_dir)
        result = runner.invoke(main, ["watcher", "delete", "run-tests-on-push", "--json"])
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_watcher_delete_json_output_id(self, runner, project_dir):
        # Spec: watchers-us-5 Scenario 4 — JSON output has "id": "run-tests-on-push"
        _make_flat_watcher(project_dir)
        result = runner.invoke(main, ["watcher", "delete", "run-tests-on-push", "--json"])
        data = json.loads(result.output)
        assert data["id"] == "run-tests-on-push"

    def test_watcher_delete_json_output_deleted_true(self, runner, project_dir):
        # Spec: watchers-us-5 Scenario 4 — JSON output has "deleted": true
        _make_flat_watcher(project_dir)
        result = runner.invoke(main, ["watcher", "delete", "run-tests-on-push", "--json"])
        data = json.loads(result.output)
        assert data["deleted"] is True

    def test_watcher_delete_json_renames_file(self, runner, project_dir):
        # Spec: watchers-us-5 Scenario 4 — file is renamed to .yaml.deleted in JSON mode too
        _make_flat_watcher(project_dir)
        runner.invoke(main, ["watcher", "delete", "run-tests-on-push", "--json"])
        deleted_file = project_dir / ".lore" / "watchers" / "run-tests-on-push.yaml.deleted"
        assert deleted_file.exists()


# ---------------------------------------------------------------------------
# Scenario 5: Delete watcher in subdirectory group located by name alone
# ---------------------------------------------------------------------------


class TestWatcherDeleteSubdirectoryGroup:
    """Scenario 5: rglob finds watcher in subdirectory; deletes it there."""

    def test_watcher_delete_subdir_exits_zero(self, runner, project_dir):
        # Spec: watchers-us-5 Scenario 5 — exit code 0 for watcher in ci/ subdir
        _make_subdir_watcher(project_dir, subdir="ci", name="run-tests")
        result = runner.invoke(main, ["watcher", "delete", "run-tests"])
        assert result.exit_code == 0

    def test_watcher_delete_subdir_stdout_message(self, runner, project_dir):
        # Spec: watchers-us-5 Scenario 5 — stdout is "Deleted watcher run-tests"
        _make_subdir_watcher(project_dir, subdir="ci", name="run-tests")
        result = runner.invoke(main, ["watcher", "delete", "run-tests"])
        assert "Deleted watcher run-tests" in result.output

    def test_watcher_delete_subdir_deleted_file_exists_in_subdir(self, runner, project_dir):
        # Spec: watchers-us-5 Scenario 5 — .yaml.deleted exists at .lore/watchers/ci/run-tests.yaml.deleted
        _make_subdir_watcher(project_dir, subdir="ci", name="run-tests")
        runner.invoke(main, ["watcher", "delete", "run-tests"])
        deleted_file = project_dir / ".lore" / "watchers" / "ci" / "run-tests.yaml.deleted"
        assert deleted_file.exists()

    def test_watcher_delete_subdir_original_yaml_absent(self, runner, project_dir):
        # Spec: watchers-us-5 Scenario 5 — original .yaml does not exist after deletion
        _make_subdir_watcher(project_dir, subdir="ci", name="run-tests")
        runner.invoke(main, ["watcher", "delete", "run-tests"])
        original_file = project_dir / ".lore" / "watchers" / "ci" / "run-tests.yaml"
        assert not original_file.exists()


# ---------------------------------------------------------------------------
# Scenario 6: Delete watcher — not found, JSON mode error on stderr
# ---------------------------------------------------------------------------


class TestWatcherDeleteNotFoundJson:
    """Scenario 6: not-found JSON error on stderr, exit code 1."""

    def test_watcher_delete_not_found_json_exits_one(self, runner, project_dir):
        # Spec: watchers-us-5 Scenario 6 — exit code 1 in JSON mode when not found
        result = runner.invoke(main, ["watcher", "delete", "nonexistent", "--json"])
        assert result.exit_code == 1

    def test_watcher_delete_not_found_json_stderr_error_key(self, runner, project_dir):
        # Spec: watchers-us-5 Scenario 6 — stderr contains {"error": "Watcher \"nonexistent\" not found in .lore/watchers/"}
        result = runner.invoke(
            main,
            ["watcher", "delete", "nonexistent", "--json"],
            catch_exceptions=False,
        )
        output = (result.output or "") + (result.stderr if hasattr(result, "stderr") else "")
        error_data = json.loads(output.strip())
        assert "error" in error_data
        assert "nonexistent" in error_data["error"]


# ---------------------------------------------------------------------------
# Scenario 7: Show returns not found after delete
# ---------------------------------------------------------------------------


class TestWatcherShowNotFoundAfterDelete:
    """Scenario 7: lore watcher show returns not-found after deletion."""

    def test_watcher_show_exits_one_after_delete(self, runner, project_dir):
        # Spec: watchers-us-5 Scenario 7 — show exits 1 after watcher is deleted
        _make_flat_watcher(project_dir)
        runner.invoke(main, ["watcher", "delete", "run-tests-on-push"])
        show_result = runner.invoke(main, ["watcher", "show", "run-tests-on-push"])
        assert show_result.exit_code == 1

    def test_watcher_show_stderr_not_found_after_delete(self, runner, project_dir):
        # Spec: watchers-us-5 Scenario 7 — show stderr contains 'Watcher "run-tests-on-push" not found.'
        _make_flat_watcher(project_dir)
        runner.invoke(main, ["watcher", "delete", "run-tests-on-push"])
        show_result = runner.invoke(
            main,
            ["watcher", "show", "run-tests-on-push"],
            catch_exceptions=False,
        )
        output = (show_result.output or "") + (show_result.stderr if hasattr(show_result, "stderr") else "")
        assert 'Watcher "run-tests-on-push" not found' in output


# ---------------------------------------------------------------------------
# US-003: watcher new --group
# anchor: conceptual-workflows-watcher-crud
# ---------------------------------------------------------------------------


class TestWatcherNewGroup:
    """E2E: lore watcher new --group creates nested watchers."""

    def test_watcher_new_nested_target_exists(self, runner, project_dir):
        # Scenario 1 — target dir pre-exists, mkdir idempotent
        (project_dir / ".lore" / "watchers" / "feature-implementation").mkdir(parents=True)
        (project_dir / "watcher.yaml").write_text(
            "id: on-prd-ready\ntitle: T\nsummary: s\n"
            "watch_target:\n  - f\n"
            "interval: daily\n"
            "action:\n  - bash: x\n"
        )
        result = runner.invoke(
            main,
            [
                "watcher", "new", "on-prd-ready",
                "--group", "feature-implementation",
                "-f", "watcher.yaml",
            ],
        )
        assert result.exit_code == 0
        assert result.output.strip() == "Created watcher on-prd-ready (group: feature-implementation)"
        assert (project_dir / ".lore" / "watchers" / "feature-implementation" / "on-prd-ready.yaml").exists()

    def test_watcher_new_nested_success_message_includes_group(self, runner, project_dir):
        # Scenario 1 — success line contains group annotation
        (project_dir / "watcher.yaml").write_text(
            "id: on-prd-ready\ntitle: T\nsummary: s\n"
            "watch_target:\n  - f\n"
            "interval: daily\n"
            "action:\n  - bash: x\n"
        )
        result = runner.invoke(
            main,
            [
                "watcher", "new", "on-prd-ready",
                "--group", "feature-implementation",
                "-f", "watcher.yaml",
            ],
        )
        assert "Created watcher on-prd-ready (group: feature-implementation)" in result.output

    def test_watcher_new_nested_json_envelope(self, runner, project_dir):
        # Scenario 2 — JSON envelope carries group + path
        (project_dir / "watcher.yaml").write_text(
            "id: on-prd-ready\ntitle: T\nsummary: s\n"
            "watch_target:\n  - f\n"
            "interval: daily\n"
            "action:\n  - bash: x\n"
        )
        result = runner.invoke(
            main,
            [
                "watcher", "new", "on-prd-ready",
                "--group", "feature-implementation",
                "-f", "watcher.yaml",
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["group"] == "feature-implementation"
        assert data["path"] == ".lore/watchers/feature-implementation/on-prd-ready.yaml"

    def test_watcher_new_deep_path_auto_mkdir(self, runner, project_dir):
        # Scenario 3 — intermediate dirs auto-created for team-a/triggers
        (project_dir / "w.yaml").write_text(
            "id: nightly\ntitle: T\nsummary: s\n"
            "watch_target:\n  - f\n"
            "interval: daily\n"
            "action:\n  - bash: x\n"
        )
        result = runner.invoke(
            main,
            [
                "watcher", "new", "nightly",
                "--group", "team-a/triggers",
                "-f", "w.yaml",
            ],
        )
        assert result.exit_code == 0
        assert (project_dir / ".lore" / "watchers" / "team-a" / "triggers" / "nightly.yaml").exists()

    def test_watcher_new_root_unchanged(self, runner, project_dir):
        # Scenario 4 — omitting --group still writes flat at root
        (project_dir / "w.yaml").write_text(
            "id: root-watcher\ntitle: T\nsummary: s\n"
            "watch_target:\n  - f\n"
            "interval: daily\n"
            "action:\n  - bash: x\n"
        )
        result = runner.invoke(
            main, ["watcher", "new", "root-watcher", "-f", "w.yaml"]
        )
        assert result.exit_code == 0
        assert (project_dir / ".lore" / "watchers" / "root-watcher.yaml").exists()

    def test_watcher_new_duplicate_subtree_rejected(self, runner, project_dir):
        # Scenario 5 — duplicate anywhere in subtree, exit 1 + error stderr, no file in new group
        (project_dir / ".lore" / "watchers" / "team-b").mkdir(parents=True)
        (project_dir / ".lore" / "watchers" / "team-b" / "nightly.yaml").write_text("id: nightly\n")
        (project_dir / "w.yaml").write_text(
            "id: nightly\ntitle: T\nsummary: s\n"
            "watch_target:\n  - f\n"
            "interval: daily\n"
            "action:\n  - bash: x\n"
        )
        result = runner.invoke(
            main,
            [
                "watcher", "new", "nightly",
                "--group", "team-a",
                "-f", "w.yaml",
            ],
        )
        assert result.exit_code == 1
        combined = (result.output or "") + (result.stderr if hasattr(result, "stderr") else "")
        assert "already exists" in combined
        assert not (project_dir / ".lore" / "watchers" / "team-a" / "nightly.yaml").exists()


# ---------------------------------------------------------------------------
# US-010 — Create-time watcher validator delegates to lore.schemas
# Spec: schema-validation-us-010
# Workflow: conceptual-workflows-watcher-crud
# ---------------------------------------------------------------------------


_US010_VALID_WATCHER_YAML = (
    "id: wx\n"
    "title: WX\n"
    "summary: desc\n"
    "watch_target:\n  - 'src/**'\n"
    "interval: on_merge\n"
    "action:\n  - bash: echo hi\n"
)

_US010_BOTH_ACTIONS_YAML = (
    "id: wx\n"
    "title: WX\n"
    "summary: desc\n"
    "watch_target:\n  - 'src/**'\n"
    "interval: on_merge\n"
    "action:\n  - doctrine: foo\n    bash: echo hi\n"
)


def test_us010_watcher_new_rejects_both_doctrine_and_bash(runner, project_dir):
    """A watcher action item carrying both `doctrine:` and `bash:` must be rejected."""
    result = runner.invoke(main, ["watcher", "new", "wx"], input=_US010_BOTH_ACTIONS_YAML)
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr if hasattr(result, "stderr") else "")
    assert ("oneOf" in combined) or ("/action" in combined) or ("action" in combined)
    assert not (project_dir / ".lore" / "watchers" / "wx.yaml").exists()


def test_us010_watcher_new_missing_summary_rejected(runner, project_dir):
    """A watcher YAML missing `summary:` must be rejected by schema at create time."""
    yaml_text = (
        "id: wx\n"
        "title: WX\n"
        "watch_target:\n  - 'src/**'\n"
        "interval: on_merge\n"
        "action:\n  - bash: echo hi\n"
    )
    result = runner.invoke(main, ["watcher", "new", "wx"], input=yaml_text)
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr if hasattr(result, "stderr") else "")
    assert "Missing required property 'summary'" in combined
    assert not (project_dir / ".lore" / "watchers" / "wx.yaml").exists()
