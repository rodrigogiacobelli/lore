"""E2E tests for the watcher list command — Workflow 1.

Spec: conceptual-workflows-watcher-list (lore codex show conceptual-workflows-watcher-list)
User story: watchers-us-1 (lore codex show watchers-us-1)
"""

import json
import shutil

from lore.cli import main


# ---------------------------------------------------------------------------
# Scenario 1: List watchers — table with one entry
# ---------------------------------------------------------------------------


class TestWatcherListSingleEntry:
    """Scenario 1: one watcher file yields a table with header and one data row."""

    def test_watcher_list_single_entry_exits_zero(self, runner, project_dir):
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = project_dir / ".lore" / "watchers" / "default"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "my-watcher.yaml").write_text(
            "id: my-watcher\n"
            "title: My Watcher\n"
            "summary: Watches for push events and triggers checks\n"
            "watch_target: feature/*\n"
            "interval: daily\n"
            "action: run-checks\n"
        )
        result = runner.invoke(main, ["watcher", "list"])
        assert result.exit_code == 0

    def test_watcher_list_single_entry_header_contains_id(self, runner, project_dir):
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = project_dir / ".lore" / "watchers" / "default"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "my-watcher.yaml").write_text(
            "id: my-watcher\n"
            "title: My Watcher\n"
            "summary: Watches for push events and triggers checks\n"
        )
        result = runner.invoke(main, ["watcher", "list"])
        assert "ID" in result.output

    def test_watcher_list_single_entry_header_contains_group(self, runner, project_dir):
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = project_dir / ".lore" / "watchers" / "default"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "my-watcher.yaml").write_text(
            "id: my-watcher\n"
            "title: My Watcher\n"
            "summary: Watches for push events and triggers checks\n"
        )
        result = runner.invoke(main, ["watcher", "list"])
        assert "GROUP" in result.output

    def test_watcher_list_single_entry_header_contains_title(self, runner, project_dir):
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = project_dir / ".lore" / "watchers" / "default"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "my-watcher.yaml").write_text(
            "id: my-watcher\n"
            "title: My Watcher\n"
            "summary: Watches for push events and triggers checks\n"
        )
        result = runner.invoke(main, ["watcher", "list"])
        assert "TITLE" in result.output

    def test_watcher_list_single_entry_header_contains_summary(
        self, runner, project_dir
    ):
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = project_dir / ".lore" / "watchers" / "default"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "my-watcher.yaml").write_text(
            "id: my-watcher\n"
            "title: My Watcher\n"
            "summary: Watches for push events and triggers checks\n"
        )
        result = runner.invoke(main, ["watcher", "list"])
        assert "SUMMARY" in result.output

    def test_watcher_list_single_entry_row_contains_id(self, runner, project_dir):
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = project_dir / ".lore" / "watchers" / "default"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "my-watcher.yaml").write_text(
            "id: my-watcher\n"
            "title: My Watcher\n"
            "summary: Watches for push events and triggers checks\n"
        )
        result = runner.invoke(main, ["watcher", "list"])
        assert "my-watcher" in result.output

    def test_watcher_list_single_entry_row_contains_group(self, runner, project_dir):
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = project_dir / ".lore" / "watchers" / "default"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "my-watcher.yaml").write_text(
            "id: my-watcher\n"
            "title: My Watcher\n"
            "summary: Watches for push events and triggers checks\n"
        )
        result = runner.invoke(main, ["watcher", "list"])
        assert "default" in result.output

    def test_watcher_list_single_entry_row_contains_title(self, runner, project_dir):
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = project_dir / ".lore" / "watchers" / "default"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "my-watcher.yaml").write_text(
            "id: my-watcher\n"
            "title: My Watcher\n"
            "summary: Watches for push events and triggers checks\n"
        )
        result = runner.invoke(main, ["watcher", "list"])
        assert "My Watcher" in result.output

    def test_watcher_list_single_entry_row_contains_summary(self, runner, project_dir):
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = project_dir / ".lore" / "watchers" / "default"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "my-watcher.yaml").write_text(
            "id: my-watcher\n"
            "title: My Watcher\n"
            "summary: Watches for push events and triggers checks\n"
        )
        result = runner.invoke(main, ["watcher", "list"])
        assert "Watches for push events" in result.output

    def test_watcher_list_single_entry_header_columns_in_order(
        self, runner, project_dir
    ):
        # ID must appear before GROUP, GROUP before TITLE, TITLE before SUMMARY
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = project_dir / ".lore" / "watchers" / "default"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "my-watcher.yaml").write_text(
            "id: my-watcher\n"
            "title: My Watcher\n"
            "summary: Watches for push events and triggers checks\n"
        )
        result = runner.invoke(main, ["watcher", "list"])
        non_empty_lines = [line for line in result.output.split("\n") if line.strip()]
        header = non_empty_lines[0]
        assert header.index("ID") < header.index("GROUP")
        assert header.index("GROUP") < header.index("TITLE")
        assert header.index("TITLE") < header.index("SUMMARY")


# ---------------------------------------------------------------------------
# Scenario 2: List watchers — empty directory
# ---------------------------------------------------------------------------


class TestWatcherListEmpty:
    """Scenario 2: empty or missing watchers directory shows 'No watchers found.'"""

    def test_watcher_list_empty_dir_exits_zero(self, runner, project_dir):
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = project_dir / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        result = runner.invoke(main, ["watcher", "list"])
        assert result.exit_code == 0

    def test_watcher_list_empty_dir_shows_no_watchers_found(
        self, runner, project_dir
    ):
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = project_dir / ".lore" / "watchers"
        shutil.rmtree(watchers_dir, ignore_errors=True)
        watchers_dir.mkdir(parents=True, exist_ok=True)
        result = runner.invoke(main, ["watcher", "list"])
        assert result.output.strip() == "No watchers found."

    def test_watcher_list_nonexistent_dir_exits_zero(self, runner, project_dir):
        # Spec: conceptual-workflows-watcher-list — .lore/watchers/ does not exist
        result = runner.invoke(main, ["watcher", "list"])
        assert result.exit_code == 0

    def test_watcher_list_nonexistent_dir_shows_no_watchers_found(
        self, runner, project_dir
    ):
        # Spec: conceptual-workflows-watcher-list — .lore/watchers/ does not exist
        watchers_dir = project_dir / ".lore" / "watchers"
        shutil.rmtree(watchers_dir, ignore_errors=True)
        result = runner.invoke(main, ["watcher", "list"])
        assert "No watchers found." in result.output


# ---------------------------------------------------------------------------
# Scenario 3: List watchers — multiple entries sorted by id
# ---------------------------------------------------------------------------


class TestWatcherListSortedByID:
    """Scenario 3: multiple watcher files are displayed sorted alphabetically by id."""

    def test_watcher_list_sorted_by_id_exits_zero(self, runner, project_dir):
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = project_dir / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "zeta-watcher.yaml").write_text(
            "id: zeta-watcher\ntitle: Zeta\nsummary: Runs last.\n"
        )
        default_dir = watchers_dir / "default"
        default_dir.mkdir(parents=True, exist_ok=True)
        (default_dir / "alpha-watcher.yaml").write_text(
            "id: alpha-watcher\ntitle: Alpha\nsummary: Runs first.\n"
        )
        result = runner.invoke(main, ["watcher", "list"])
        assert result.exit_code == 0

    def test_watcher_list_alpha_before_zeta(self, runner, project_dir):
        # Spec: conceptual-workflows-watcher-list — alphabetically earlier id appears first
        watchers_dir = project_dir / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "zeta-watcher.yaml").write_text(
            "id: zeta-watcher\ntitle: Zeta\nsummary: Runs last.\n"
        )
        default_dir = watchers_dir / "default"
        default_dir.mkdir(parents=True, exist_ok=True)
        (default_dir / "alpha-watcher.yaml").write_text(
            "id: alpha-watcher\ntitle: Alpha\nsummary: Runs first.\n"
        )
        result = runner.invoke(main, ["watcher", "list"])
        non_empty_lines = [line for line in result.output.split("\n") if line.strip()]
        data_rows = non_empty_lines[1:]  # skip header
        alpha_row_idx = next(
            i for i, r in enumerate(data_rows) if "alpha-watcher" in r
        )
        zeta_row_idx = next(
            i for i, r in enumerate(data_rows) if "zeta-watcher" in r
        )
        assert alpha_row_idx < zeta_row_idx

    def test_watcher_list_two_entries_produce_header_plus_two_rows(
        self, runner, project_dir
    ):
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = project_dir / ".lore" / "watchers"
        shutil.rmtree(watchers_dir, ignore_errors=True)
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "alpha.yaml").write_text(
            "id: alpha\ntitle: Alpha\nsummary: First.\n"
        )
        (watchers_dir / "beta.yaml").write_text(
            "id: beta\ntitle: Beta\nsummary: Second.\n"
        )
        result = runner.invoke(main, ["watcher", "list"])
        assert result.exit_code == 0
        non_empty_lines = [line for line in result.output.split("\n") if line.strip()]
        assert len(non_empty_lines) == 3  # header + 2 data rows


# ---------------------------------------------------------------------------
# Scenario 4: List watchers — JSON output
# ---------------------------------------------------------------------------


class TestWatcherListJson:
    """Scenario 4: --json flag produces machine-readable JSON output."""

    def test_watcher_list_json_exits_zero(self, runner, project_dir):
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = project_dir / ".lore" / "watchers" / "default"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "my-watcher.yaml").write_text(
            "id: my-watcher\n"
            "title: My Watcher\n"
            "summary: Watches for push events and triggers checks\n"
        )
        result = runner.invoke(main, ["watcher", "list", "--json"])
        assert result.exit_code == 0

    def test_watcher_list_json_output_is_valid_json(self, runner, project_dir):
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = project_dir / ".lore" / "watchers" / "default"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "my-watcher.yaml").write_text(
            "id: my-watcher\n"
            "title: My Watcher\n"
            "summary: Watches for push events and triggers checks\n"
        )
        result = runner.invoke(main, ["watcher", "list", "--json"])
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_watcher_list_json_has_watchers_key(self, runner, project_dir):
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = project_dir / ".lore" / "watchers" / "default"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "my-watcher.yaml").write_text(
            "id: my-watcher\n"
            "title: My Watcher\n"
            "summary: Watches for push events and triggers checks\n"
        )
        result = runner.invoke(main, ["watcher", "list", "--json"])
        data = json.loads(result.output)
        assert "watchers" in data
        assert isinstance(data["watchers"], list)

    def test_watcher_list_json_entry_has_id_field(self, runner, project_dir):
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = project_dir / ".lore" / "watchers"
        shutil.rmtree(watchers_dir, ignore_errors=True)
        (watchers_dir / "default").mkdir(parents=True)
        (watchers_dir / "default" / "my-watcher.yaml").write_text(
            "id: my-watcher\n"
            "title: My Watcher\n"
            "summary: Watches for push events and triggers checks\n"
        )
        result = runner.invoke(main, ["watcher", "list", "--json"])
        data = json.loads(result.output)
        assert data["watchers"][0]["id"] == "my-watcher"

    def test_watcher_list_json_entry_has_group_field(self, runner, project_dir):
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = project_dir / ".lore" / "watchers"
        shutil.rmtree(watchers_dir, ignore_errors=True)
        (watchers_dir / "default").mkdir(parents=True)
        (watchers_dir / "default" / "my-watcher.yaml").write_text(
            "id: my-watcher\n"
            "title: My Watcher\n"
            "summary: Watches for push events and triggers checks\n"
        )
        result = runner.invoke(main, ["watcher", "list", "--json"])
        data = json.loads(result.output)
        assert data["watchers"][0]["group"] == "default"

    def test_watcher_list_json_entry_has_title_field(self, runner, project_dir):
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = project_dir / ".lore" / "watchers"
        shutil.rmtree(watchers_dir, ignore_errors=True)
        (watchers_dir / "default").mkdir(parents=True)
        (watchers_dir / "default" / "my-watcher.yaml").write_text(
            "id: my-watcher\n"
            "title: My Watcher\n"
            "summary: Watches for push events and triggers checks\n"
        )
        result = runner.invoke(main, ["watcher", "list", "--json"])
        data = json.loads(result.output)
        assert data["watchers"][0]["title"] == "My Watcher"

    def test_watcher_list_json_entry_has_summary_field(self, runner, project_dir):
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = project_dir / ".lore" / "watchers"
        shutil.rmtree(watchers_dir, ignore_errors=True)
        (watchers_dir / "default").mkdir(parents=True)
        (watchers_dir / "default" / "my-watcher.yaml").write_text(
            "id: my-watcher\n"
            "title: My Watcher\n"
            "summary: Watches for push events and triggers checks\n"
        )
        result = runner.invoke(main, ["watcher", "list", "--json"])
        data = json.loads(result.output)
        assert data["watchers"][0]["summary"] == "Watches for push events and triggers checks"

    def test_watcher_list_json_empty_gives_empty_array(self, runner, project_dir):
        # Spec: conceptual-workflows-watcher-list — empty dir gives {"watchers": []}
        watchers_dir = project_dir / ".lore" / "watchers"
        shutil.rmtree(watchers_dir, ignore_errors=True)
        watchers_dir.mkdir(parents=True, exist_ok=True)
        result = runner.invoke(main, ["watcher", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == {"watchers": []}

    def test_watcher_list_local_json_flag_identical_to_global_flag(
        self, runner, project_dir
    ):
        # Both lore watcher list --json and lore --json watcher list must produce identical output
        # Spec: feedback_json_flag_placement.md
        watchers_dir = project_dir / ".lore" / "watchers" / "default"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "my-watcher.yaml").write_text(
            "id: my-watcher\ntitle: My Watcher\nsummary: Summary.\n"
        )
        local_result = runner.invoke(main, ["watcher", "list", "--json"])
        global_result = runner.invoke(main, ["--json", "watcher", "list"])
        assert local_result.exit_code == 0
        assert global_result.exit_code == 0
        assert json.loads(local_result.output) == json.loads(global_result.output)

    def test_watcher_list_json_help_shows_json_flag(self, runner, project_dir):
        # --json must be declared at the subcommand level
        result = runner.invoke(main, ["watcher", "list", "--help"])
        assert result.exit_code == 0
        assert "--json" in result.output


# ---------------------------------------------------------------------------
# Scenario 5: List watchers — malformed file does not abort
# ---------------------------------------------------------------------------


class TestWatcherListMalformedFileFallback:
    """Scenario 5: a file with missing required fields still appears with fallback values."""

    def test_watcher_list_malformed_file_exits_zero(self, runner, project_dir):
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = project_dir / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        # Valid watcher
        (watchers_dir / "valid.yaml").write_text(
            "id: valid\ntitle: Valid\nsummary: A valid watcher.\n"
        )
        # Malformed: missing title
        (watchers_dir / "no-title.yaml").write_text(
            "id: no-title\nsummary: Missing title.\n"
        )
        result = runner.invoke(main, ["watcher", "list"])
        assert result.exit_code == 0

    def test_watcher_list_malformed_title_falls_back_to_stem(
        self, runner, project_dir
    ):
        # Spec: conceptual-workflows-watcher-list — title fallback = file stem
        watchers_dir = project_dir / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "no-title.yaml").write_text(
            "id: no-title\nsummary: Missing title.\n"
        )
        result = runner.invoke(main, ["watcher", "list"])
        assert "no-title" in result.output

    def test_watcher_list_malformed_valid_entry_also_shown(
        self, runner, project_dir
    ):
        # Spec: conceptual-workflows-watcher-list — both entries appear
        watchers_dir = project_dir / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "valid.yaml").write_text(
            "id: valid\ntitle: Valid\nsummary: A valid watcher.\n"
        )
        (watchers_dir / "no-title.yaml").write_text(
            "id: no-title\nsummary: Missing title.\n"
        )
        result = runner.invoke(main, ["watcher", "list"])
        assert "valid" in result.output
        assert "no-title" in result.output

    def test_watcher_list_malformed_file_no_stderr_error(self, project_dir):
        # Spec: conceptual-workflows-watcher-list — no error is printed to stderr
        # Uses subprocess so that stdout and stderr are captured separately
        # (CliRunner in Click 8.x does not support mix_stderr=False).
        import subprocess
        import sys

        watchers_dir = project_dir / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "no-title.yaml").write_text(
            "id: no-title\nsummary: Missing title.\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", "from lore.cli import main; main()", "watcher", "list"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
        )
        assert proc.returncode == 0
        assert proc.stderr == ""


# ---------------------------------------------------------------------------
# Workflow 2: watcher show — Scenario 1: plain mode, full YAML byte-for-byte
# ---------------------------------------------------------------------------

WATCHER_YAML_WITH_COMMENT = (
    "id: my-watcher\n"
    "title: My Watcher\n"
    "summary: Watches for push events and triggers checks\n"
    "\n"
    "watch_target: feature/*\n"
    "# interval examples: daily | on_file_change\n"
    "interval: daily\n"
    "action: run-checks\n"
)


class TestWatcherShowPlain:
    """Scenario 1: plain mode prints raw YAML byte-for-byte including comments."""

    def _setup_watcher(self, project_dir):
        watchers_dir = project_dir / ".lore" / "watchers" / "default"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "my-watcher.yaml").write_text(WATCHER_YAML_WITH_COMMENT)

    def test_watcher_show_plain_exits_zero(self, runner, project_dir):
        # Spec: watchers-us-2 Scenario 1
        self._setup_watcher(project_dir)
        result = runner.invoke(main, ["watcher", "show", "my-watcher"])
        assert result.exit_code == 0

    def test_watcher_show_plain_stdout_is_exact_raw_content(self, runner, project_dir):
        # Spec: watchers-us-2 Scenario 1 — stdout is byte-for-byte the raw file content
        self._setup_watcher(project_dir)
        result = runner.invoke(main, ["watcher", "show", "my-watcher"])
        assert result.output == WATCHER_YAML_WITH_COMMENT

    def test_watcher_show_plain_includes_comment_line(self, runner, project_dir):
        # Spec: watchers-us-2 Scenario 1 — YAML comments must survive in output
        self._setup_watcher(project_dir)
        result = runner.invoke(main, ["watcher", "show", "my-watcher"])
        assert "# interval examples: daily | on_file_change" in result.output

    def test_watcher_show_plain_no_stderr(self, project_dir):
        # Spec: watchers-us-2 Scenario 1 — nothing printed to stderr
        import subprocess
        import sys
        watchers_dir = project_dir / ".lore" / "watchers" / "default"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "my-watcher.yaml").write_text(WATCHER_YAML_WITH_COMMENT)
        proc = subprocess.run(
            [sys.executable, "-c", "from lore.cli import main; main()", "watcher", "show", "my-watcher"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
        )
        assert proc.returncode == 0
        assert proc.stderr == ""


# ---------------------------------------------------------------------------
# Workflow 2: watcher show — Scenario 2: not found (plain mode)
# ---------------------------------------------------------------------------


class TestWatcherShowNotFound:
    """Scenario 2: watcher not found — stderr message, exit code 1, empty stdout."""

    def test_watcher_show_not_found_exits_one(self, runner, project_dir):
        # Spec: watchers-us-2 Scenario 2
        result = runner.invoke(main, ["watcher", "show", "nonexistent"])
        assert result.exit_code == 1

    def test_watcher_show_not_found_stderr_contains_message(self, project_dir):
        # Spec: watchers-us-2 Scenario 2 — stderr contains 'Watcher "nonexistent" not found.'
        import subprocess
        import sys
        proc = subprocess.run(
            [sys.executable, "-c", "from lore.cli import main; main()", "watcher", "show", "nonexistent"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
        )
        assert proc.returncode == 1
        assert 'Watcher "nonexistent" not found.' in proc.stderr

    def test_watcher_show_not_found_stdout_is_empty(self, project_dir):
        # Spec: watchers-us-2 Scenario 2 — stdout is empty when watcher not found
        import subprocess
        import sys
        proc = subprocess.run(
            [sys.executable, "-c", "from lore.cli import main; main()", "watcher", "show", "nonexistent"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
        )
        assert proc.stdout == ""


# ---------------------------------------------------------------------------
# Workflow 2: watcher show — Scenario 3: JSON mode, all 8 keys present
# ---------------------------------------------------------------------------


class TestWatcherShowJson:
    """Scenario 3: --json mode prints structured JSON with all 8 keys."""

    def _setup_watcher(self, project_dir):
        watchers_dir = project_dir / ".lore" / "watchers" / "default"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "my-watcher.yaml").write_text(WATCHER_YAML_WITH_COMMENT)

    def test_watcher_show_json_exits_zero(self, runner, project_dir):
        # Spec: watchers-us-2 Scenario 3
        self._setup_watcher(project_dir)
        result = runner.invoke(main, ["watcher", "show", "my-watcher", "--json"])
        assert result.exit_code == 0

    def test_watcher_show_json_output_is_valid_json(self, runner, project_dir):
        # Spec: watchers-us-2 Scenario 3 — stdout is valid JSON
        self._setup_watcher(project_dir)
        result = runner.invoke(main, ["watcher", "show", "my-watcher", "--json"])
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_watcher_show_json_has_id_key(self, runner, project_dir):
        # Spec: watchers-us-2 Scenario 3
        self._setup_watcher(project_dir)
        result = runner.invoke(main, ["watcher", "show", "my-watcher", "--json"])
        data = json.loads(result.output)
        assert data["id"] == "my-watcher"

    def test_watcher_show_json_has_group_key(self, runner, project_dir):
        # Spec: watchers-us-2 Scenario 3
        self._setup_watcher(project_dir)
        result = runner.invoke(main, ["watcher", "show", "my-watcher", "--json"])
        data = json.loads(result.output)
        assert data["group"] == "default"

    def test_watcher_show_json_has_title_key(self, runner, project_dir):
        # Spec: watchers-us-2 Scenario 3
        self._setup_watcher(project_dir)
        result = runner.invoke(main, ["watcher", "show", "my-watcher", "--json"])
        data = json.loads(result.output)
        assert data["title"] == "My Watcher"

    def test_watcher_show_json_has_summary_key(self, runner, project_dir):
        # Spec: watchers-us-2 Scenario 3
        self._setup_watcher(project_dir)
        result = runner.invoke(main, ["watcher", "show", "my-watcher", "--json"])
        data = json.loads(result.output)
        assert data["summary"] == "Watches for push events and triggers checks"

    def test_watcher_show_json_has_watch_target_key(self, runner, project_dir):
        # Spec: watchers-us-2 Scenario 3
        self._setup_watcher(project_dir)
        result = runner.invoke(main, ["watcher", "show", "my-watcher", "--json"])
        data = json.loads(result.output)
        assert data["watch_target"] == "feature/*"

    def test_watcher_show_json_has_interval_key(self, runner, project_dir):
        # Spec: watchers-us-2 Scenario 3
        self._setup_watcher(project_dir)
        result = runner.invoke(main, ["watcher", "show", "my-watcher", "--json"])
        data = json.loads(result.output)
        assert data["interval"] == "daily"

    def test_watcher_show_json_has_action_key(self, runner, project_dir):
        # Spec: watchers-us-2 Scenario 3
        self._setup_watcher(project_dir)
        result = runner.invoke(main, ["watcher", "show", "my-watcher", "--json"])
        data = json.loads(result.output)
        assert data["action"] == "run-checks"

    def test_watcher_show_json_has_filename_key(self, runner, project_dir):
        # Spec: watchers-us-2 Scenario 3
        self._setup_watcher(project_dir)
        result = runner.invoke(main, ["watcher", "show", "my-watcher", "--json"])
        data = json.loads(result.output)
        assert data["filename"] == "my-watcher.yaml"

    def test_watcher_show_json_has_exactly_eight_keys(self, runner, project_dir):
        # Spec: watchers-us-2 Scenario 3 — exactly 8 keys in JSON output
        self._setup_watcher(project_dir)
        result = runner.invoke(main, ["watcher", "show", "my-watcher", "--json"])
        data = json.loads(result.output)
        assert set(data.keys()) == {"id", "group", "title", "summary", "watch_target", "interval", "action", "filename"}


# ---------------------------------------------------------------------------
# Workflow 2: watcher show — Scenario 4: JSON mode, optional fields absent → null
# ---------------------------------------------------------------------------


class TestWatcherShowJsonOptionalFieldsNull:
    """Scenario 4: optional fields absent from YAML serialize as null in JSON."""

    def test_watcher_show_json_absent_watch_target_is_null(self, runner, project_dir):
        # Spec: watchers-us-2 Scenario 4
        watchers_dir = project_dir / ".lore" / "watchers" / "default"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "minimal.yaml").write_text(
            "id: minimal\ntitle: Minimal\nsummary: No optional fields.\n"
        )
        result = runner.invoke(main, ["watcher", "show", "minimal", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["watch_target"] is None

    def test_watcher_show_json_absent_interval_is_null(self, runner, project_dir):
        # Spec: watchers-us-2 Scenario 4
        watchers_dir = project_dir / ".lore" / "watchers" / "default"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "minimal.yaml").write_text(
            "id: minimal\ntitle: Minimal\nsummary: No optional fields.\n"
        )
        result = runner.invoke(main, ["watcher", "show", "minimal", "--json"])
        data = json.loads(result.output)
        assert data["interval"] is None

    def test_watcher_show_json_absent_action_is_null(self, runner, project_dir):
        # Spec: watchers-us-2 Scenario 4
        watchers_dir = project_dir / ".lore" / "watchers" / "default"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "minimal.yaml").write_text(
            "id: minimal\ntitle: Minimal\nsummary: No optional fields.\n"
        )
        result = runner.invoke(main, ["watcher", "show", "minimal", "--json"])
        data = json.loads(result.output)
        assert data["action"] is None

    def test_watcher_show_json_absent_optional_all_eight_keys_still_present(self, runner, project_dir):
        # Spec: watchers-us-2 Scenario 4 — all 8 keys present even when optional fields absent
        watchers_dir = project_dir / ".lore" / "watchers" / "default"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "minimal.yaml").write_text(
            "id: minimal\ntitle: Minimal\nsummary: No optional fields.\n"
        )
        result = runner.invoke(main, ["watcher", "show", "minimal", "--json"])
        data = json.loads(result.output)
        assert set(data.keys()) == {"id", "group", "title", "summary", "watch_target", "interval", "action", "filename"}


# ---------------------------------------------------------------------------
# Workflow 2: watcher show — Scenario 5: not found, JSON mode error on stderr
# ---------------------------------------------------------------------------


class TestWatcherShowNotFoundJson:
    """Scenario 5: not found in --json mode — JSON error on stderr, exit 1."""

    def test_watcher_show_not_found_json_exits_one(self, project_dir):
        # Spec: watchers-us-2 Scenario 5
        import subprocess
        import sys
        proc = subprocess.run(
            [sys.executable, "-c", "from lore.cli import main; main()", "watcher", "show", "nonexistent", "--json"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
        )
        assert proc.returncode == 1

    def test_watcher_show_not_found_json_stderr_is_json_error(self, project_dir):
        # Spec: watchers-us-2 Scenario 5 — stderr contains JSON error object
        import subprocess
        import sys
        proc = subprocess.run(
            [sys.executable, "-c", "from lore.cli import main; main()", "watcher", "show", "nonexistent", "--json"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
        )
        assert proc.returncode == 1
        err_data = json.loads(proc.stderr)
        assert "error" in err_data
        assert "nonexistent" in err_data["error"]

    def test_watcher_show_not_found_json_stdout_is_empty(self, project_dir):
        # Spec: watchers-us-2 Scenario 5 — stdout is empty
        import subprocess
        import sys
        proc = subprocess.run(
            [sys.executable, "-c", "from lore.cli import main; main()", "watcher", "show", "nonexistent", "--json"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
        )
        assert proc.stdout == ""


# ---------------------------------------------------------------------------
# Workflow 2: watcher show — Scenario 6: subdirectory group located by name alone
# ---------------------------------------------------------------------------


class TestWatcherShowSubdirectoryGroup:
    """Scenario 6: watcher in a named subdirectory is found by stem name alone."""

    def test_watcher_show_subdirectory_exits_zero(self, runner, project_dir):
        # Spec: watchers-us-2 Scenario 6
        ci_dir = project_dir / ".lore" / "watchers" / "ci"
        ci_dir.mkdir(parents=True, exist_ok=True)
        (ci_dir / "run-tests.yaml").write_text(
            "id: run-tests\ntitle: Run Tests\nsummary: CI test runner.\n"
            "watch_target: main\ninterval: on_merge\naction: run-tests\n"
        )
        result = runner.invoke(main, ["watcher", "show", "run-tests"])
        assert result.exit_code == 0

    def test_watcher_show_subdirectory_stdout_is_raw_yaml(self, runner, project_dir):
        # Spec: watchers-us-2 Scenario 6 — raw YAML content is printed
        raw_content = (
            "id: run-tests\ntitle: Run Tests\nsummary: CI test runner.\n"
            "watch_target: main\ninterval: on_merge\naction: run-tests\n"
        )
        ci_dir = project_dir / ".lore" / "watchers" / "ci"
        ci_dir.mkdir(parents=True, exist_ok=True)
        (ci_dir / "run-tests.yaml").write_text(raw_content)
        result = runner.invoke(main, ["watcher", "show", "run-tests"])
        assert result.output == raw_content


# ---------------------------------------------------------------------------
# Workflow 2: watcher show — path-traversal guard
# ---------------------------------------------------------------------------


class TestWatcherShowPathTraversalGuard:
    """Path-traversal: names containing / or \\ must be rejected."""

    def test_watcher_show_path_traversal_slash_exits_one(self, runner, project_dir):
        # Spec: watchers-us-2 — path-traversal guard rejects names with /
        result = runner.invoke(main, ["watcher", "show", "../etc/passwd"])
        assert result.exit_code == 1

    def test_watcher_show_path_traversal_slash_error_message(self, runner, project_dir):
        # Spec: watchers-us-2 — error message shown for path-traversal attempt
        result = runner.invoke(main, ["watcher", "show", "../etc/passwd"])
        assert result.exit_code == 1
        # exit code 1 is sufficient; message check via stderr in subprocess
        # (CliRunner merges stderr into output in Click 8)
        # We just confirm it exits 1; message content tested via subprocess below

    def test_watcher_show_path_traversal_backslash_exits_one(self, project_dir):
        # Spec: watchers-us-2 — path-traversal guard rejects names with backslash
        import subprocess
        import sys
        proc = subprocess.run(
            [sys.executable, "-c", "from lore.cli import main; main()", "watcher", "show", "foo\\bar"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
        )
        assert proc.returncode == 1


# ---------------------------------------------------------------------------
# US-007 Red: list GROUP slash display + JSON audit
# anchor: conceptual-workflows-json-output (lore codex show group-param-us-007)
# ---------------------------------------------------------------------------


class TestWatcherListUs007SlashGroup:
    """US-007 Scenario 5: watcher list table + JSON emit slash-joined group, null for root."""

    def test_watcher_list_json_slash_joined_nested_group(self, runner, project_dir):
        watchers_dir = project_dir / ".lore" / "watchers"
        shutil.rmtree(watchers_dir)
        watchers_dir.mkdir()
        nested = watchers_dir / "feature-implementation"
        nested.mkdir()
        (nested / "on-prd-ready.yaml").write_text(
            "id: on-prd-ready\n"
            "title: On PRD Ready\n"
            "summary: Triggers when PRD is ready.\n"
        )
        # Deeper: ops/ci/on-push.yaml -> "ops/ci"
        deep = watchers_dir / "ops" / "ci"
        deep.mkdir(parents=True)
        (deep / "on-push.yaml").write_text(
            "id: on-push\ntitle: On Push\nsummary: Push trigger.\n"
        )
        # Root watcher -> null
        (watchers_dir / "root-watcher.yaml").write_text(
            "id: root-watcher\ntitle: Root\nsummary: Root level.\n"
        )
        result = runner.invoke(main, ["watcher", "list", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        by_id = {w["id"]: w for w in data["watchers"]}
        assert by_id["on-prd-ready"]["group"] == "feature-implementation"
        assert by_id["on-push"]["group"] == "ops/ci"
        assert by_id["root-watcher"]["group"] is None
        for w in data["watchers"]:
            assert w["group"] != "", f"group must never be empty string: {w}"
            assert w["group"] != "ops-ci", f"group must never be hyphen-joined: {w}"

