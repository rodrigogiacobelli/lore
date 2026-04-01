"""Unit tests for lore.watcher.list_watchers.

Spec: conceptual-workflows-watcher-list (lore codex show conceptual-workflows-watcher-list)
User story: watchers-us-1 (lore codex show watchers-us-1)
"""

from lore.watcher import list_watchers


# ---------------------------------------------------------------------------
# Empty / missing directory
# ---------------------------------------------------------------------------


class TestListWatchersMissingOrEmptyDirectory:
    """list_watchers returns [] when no *.yaml files are found."""

    def test_list_watchers_dir_missing_returns_empty_list(self, tmp_path):
        # Unit: list_watchers returns [] when watchers_dir does not exist
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = tmp_path / ".lore" / "watchers"
        # Directory intentionally NOT created
        result = list_watchers(watchers_dir)
        assert result == []

    def test_list_watchers_no_yaml_files_returns_empty_list(self, tmp_path):
        # Unit: list_watchers returns [] when watchers_dir exists but has no *.yaml files
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        (watchers_dir / "README.txt").write_text("not a yaml file")
        result = list_watchers(watchers_dir)
        assert result == []


# ---------------------------------------------------------------------------
# Group derivation
# ---------------------------------------------------------------------------


class TestListWatchersGroupDerivation:
    """Group is derived from the subdirectory relative to watchers_dir."""

    def test_list_watchers_group_default_for_file_in_default_subdir(self, tmp_path):
        # Unit: list_watchers derives group "default" for a file in watchers_dir/default/
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = tmp_path / ".lore" / "watchers"
        default_dir = watchers_dir / "default"
        default_dir.mkdir(parents=True)
        (default_dir / "my-watcher.yaml").write_text(
            "id: my-watcher\n"
            "title: My Watcher\n"
            "summary: Watches for push events.\n"
        )
        result = list_watchers(watchers_dir)
        assert len(result) == 1
        assert result[0]["group"] == "default"

    def test_list_watchers_group_empty_for_flat_file(self, tmp_path):
        # Unit: list_watchers derives group "" for a file directly in watchers_dir (flat, no subdirectory)
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        (watchers_dir / "my-watcher.yaml").write_text(
            "id: my-watcher\n"
            "title: My Watcher\n"
            "summary: Watches for push events.\n"
        )
        result = list_watchers(watchers_dir)
        assert len(result) == 1
        group = result[0]["group"]
        # Group must be empty string (or ".") for root-level files; we assert empty string
        assert group == ""


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


class TestListWatchersSorting:
    """Results are sorted ascending by id."""

    def test_list_watchers_results_sorted_ascending_by_id(self, tmp_path):
        # Unit: list_watchers results are sorted ascending by id
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        (watchers_dir / "zeta-watcher.yaml").write_text(
            "id: zeta-watcher\ntitle: Zeta\nsummary: Runs last.\n"
        )
        default_dir = watchers_dir / "default"
        default_dir.mkdir()
        (default_dir / "alpha-watcher.yaml").write_text(
            "id: alpha-watcher\ntitle: Alpha\nsummary: Runs first.\n"
        )
        result = list_watchers(watchers_dir)
        assert len(result) == 2
        ids = [w["id"] for w in result]
        assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# Fallback values for missing fields
# ---------------------------------------------------------------------------


class TestListWatchersFallbacks:
    """Missing required fields fall back to safe defaults rather than raising."""

    def test_list_watchers_missing_title_falls_back_to_file_stem(self, tmp_path):
        # Unit: list_watchers — file with missing title gets title fallback equal to file stem
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        (watchers_dir / "my-watcher.yaml").write_text(
            "id: my-watcher\n"
            "summary: No title here.\n"
        )
        result = list_watchers(watchers_dir)
        assert len(result) == 1
        assert result[0]["title"] == "my-watcher"

    def test_list_watchers_missing_summary_falls_back_to_empty_string(self, tmp_path):
        # Unit: list_watchers — file with missing summary gets summary fallback of ""
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        (watchers_dir / "no-summary.yaml").write_text(
            "id: no-summary\n"
            "title: No Summary Watcher\n"
        )
        result = list_watchers(watchers_dir)
        assert len(result) == 1
        assert result[0]["summary"] == ""


# ---------------------------------------------------------------------------
# Excluded files
# ---------------------------------------------------------------------------


class TestListWatchersExcludedFiles:
    """*.yaml.deleted files are excluded from results."""

    def test_list_watchers_excludes_yaml_deleted_files(self, tmp_path):
        # Unit: list_watchers — *.yaml.deleted files are excluded from results
        # Spec: conceptual-workflows-watcher-list
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        # Valid watcher
        (watchers_dir / "active-watcher.yaml").write_text(
            "id: active-watcher\ntitle: Active\nsummary: Active watcher.\n"
        )
        # Soft-deleted watcher — must not appear
        (watchers_dir / "deleted-watcher.yaml.deleted").write_text(
            "id: deleted-watcher\ntitle: Deleted\nsummary: Soft-deleted watcher.\n"
        )
        result = list_watchers(watchers_dir)
        assert len(result) == 1
        assert result[0]["id"] == "active-watcher"
        ids = [w["id"] for w in result]
        assert "deleted-watcher" not in ids


# ---------------------------------------------------------------------------
# Return type and field contract
# ---------------------------------------------------------------------------


class TestListWatchersReturnShape:
    """Each returned dict has the expected keys."""

    def test_list_watchers_returns_list_of_dicts(self, tmp_path):
        # Each result entry is a dict
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        (watchers_dir / "sample.yaml").write_text(
            "id: sample\ntitle: Sample\nsummary: A sample watcher.\n"
        )
        result = list_watchers(watchers_dir)
        assert isinstance(result, list)
        assert all(isinstance(w, dict) for w in result)

    def test_list_watchers_each_dict_has_id_key(self, tmp_path):
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        (watchers_dir / "sample.yaml").write_text(
            "id: sample\ntitle: Sample\nsummary: A sample watcher.\n"
        )
        result = list_watchers(watchers_dir)
        assert "id" in result[0]

    def test_list_watchers_each_dict_has_group_key(self, tmp_path):
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        (watchers_dir / "sample.yaml").write_text(
            "id: sample\ntitle: Sample\nsummary: A sample watcher.\n"
        )
        result = list_watchers(watchers_dir)
        assert "group" in result[0]

    def test_list_watchers_each_dict_has_title_key(self, tmp_path):
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        (watchers_dir / "sample.yaml").write_text(
            "id: sample\ntitle: Sample\nsummary: A sample watcher.\n"
        )
        result = list_watchers(watchers_dir)
        assert "title" in result[0]

    def test_list_watchers_each_dict_has_summary_key(self, tmp_path):
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        (watchers_dir / "sample.yaml").write_text(
            "id: sample\ntitle: Sample\nsummary: A sample watcher.\n"
        )
        result = list_watchers(watchers_dir)
        assert "summary" in result[0]


# ---------------------------------------------------------------------------
# Unit tests for find_watcher (US-2)
# ---------------------------------------------------------------------------


class TestFindWatcher:
    """find_watcher(watchers_dir, name) — lookup by filename stem."""

    def test_find_watcher_returns_path_when_stem_matches(self, tmp_path):
        # Spec: watchers-us-2 — find_watcher returns Path to the correct file
        from lore.watcher import find_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        default_dir = watchers_dir / "default"
        default_dir.mkdir(parents=True)
        expected = default_dir / "my-watcher.yaml"
        expected.write_text("id: my-watcher\ntitle: X\nsummary: Y\n")
        result = find_watcher(watchers_dir, "my-watcher")
        assert result == expected

    def test_find_watcher_returns_none_when_no_stem_matches(self, tmp_path):
        # Spec: watchers-us-2 — find_watcher returns None when no file with matching stem exists
        from lore.watcher import find_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        result = find_watcher(watchers_dir, "nonexistent")
        assert result is None

    def test_find_watcher_finds_file_in_subdirectory(self, tmp_path):
        # Spec: watchers-us-2 — find_watcher searches recursively via rglob
        from lore.watcher import find_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        ci_dir = watchers_dir / "ci"
        ci_dir.mkdir(parents=True)
        expected = ci_dir / "run-tests.yaml"
        expected.write_text("id: run-tests\ntitle: Run\nsummary: Tests.\n")
        result = find_watcher(watchers_dir, "run-tests")
        assert result == expected

    def test_find_watcher_raises_value_error_for_name_with_slash(self, tmp_path):
        # Spec: watchers-us-2 — path-traversal guard: ValueError for name containing /
        import pytest
        from lore.watcher import find_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            find_watcher(watchers_dir, "../etc/passwd")

    def test_find_watcher_raises_value_error_for_name_with_backslash(self, tmp_path):
        # Spec: watchers-us-2 — path-traversal guard: ValueError for name containing backslash
        import pytest
        from lore.watcher import find_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            find_watcher(watchers_dir, "foo\\bar")

    def test_find_watcher_returns_none_when_dir_missing(self, tmp_path):
        # Spec: watchers-us-2 — graceful handling when watchers_dir does not exist
        from lore.watcher import find_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        # intentionally NOT created
        result = find_watcher(watchers_dir, "anything")
        assert result is None


# ---------------------------------------------------------------------------
# Unit tests for load_watcher (US-2)
# ---------------------------------------------------------------------------


class TestLoadWatcher:
    """load_watcher(filepath, watchers_dir) — returns dict with all 8 keys."""

    FULL_YAML = (
        "id: my-watcher\n"
        "title: My Watcher\n"
        "summary: Watches for push events and triggers the run-checks doctrine\n"
        "watch_target: feature/*\n"
        "interval: daily\n"
        "action: run-checks\n"
    )

    def _make_watcher_file(self, base_dir, subdir, filename, content):
        path = base_dir / subdir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def test_load_watcher_returns_dict(self, tmp_path):
        # Spec: watchers-us-2 — load_watcher returns a dict
        from lore.watcher import load_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        filepath = self._make_watcher_file(watchers_dir, "default", "my-watcher.yaml", self.FULL_YAML)
        result = load_watcher(filepath, watchers_dir)
        assert isinstance(result, dict)

    def test_load_watcher_has_id_key(self, tmp_path):
        # Spec: watchers-us-2
        from lore.watcher import load_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        filepath = self._make_watcher_file(watchers_dir, "default", "my-watcher.yaml", self.FULL_YAML)
        result = load_watcher(filepath, watchers_dir)
        assert result["id"] == "my-watcher"

    def test_load_watcher_has_title_key(self, tmp_path):
        # Spec: watchers-us-2
        from lore.watcher import load_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        filepath = self._make_watcher_file(watchers_dir, "default", "my-watcher.yaml", self.FULL_YAML)
        result = load_watcher(filepath, watchers_dir)
        assert result["title"] == "My Watcher"

    def test_load_watcher_has_summary_key(self, tmp_path):
        # Spec: watchers-us-2
        from lore.watcher import load_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        filepath = self._make_watcher_file(watchers_dir, "default", "my-watcher.yaml", self.FULL_YAML)
        result = load_watcher(filepath, watchers_dir)
        assert result["summary"] == "Watches for push events and triggers the run-checks doctrine"

    def test_load_watcher_has_watch_target_key(self, tmp_path):
        # Spec: watchers-us-2
        from lore.watcher import load_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        filepath = self._make_watcher_file(watchers_dir, "default", "my-watcher.yaml", self.FULL_YAML)
        result = load_watcher(filepath, watchers_dir)
        assert result["watch_target"] == "feature/*"

    def test_load_watcher_has_interval_key(self, tmp_path):
        # Spec: watchers-us-2
        from lore.watcher import load_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        filepath = self._make_watcher_file(watchers_dir, "default", "my-watcher.yaml", self.FULL_YAML)
        result = load_watcher(filepath, watchers_dir)
        assert result["interval"] == "daily"

    def test_load_watcher_has_action_key(self, tmp_path):
        # Spec: watchers-us-2
        from lore.watcher import load_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        filepath = self._make_watcher_file(watchers_dir, "default", "my-watcher.yaml", self.FULL_YAML)
        result = load_watcher(filepath, watchers_dir)
        assert result["action"] == "run-checks"

    def test_load_watcher_has_filename_key(self, tmp_path):
        # Spec: watchers-us-2 — filename key equals filepath.name
        from lore.watcher import load_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        filepath = self._make_watcher_file(watchers_dir, "default", "my-watcher.yaml", self.FULL_YAML)
        result = load_watcher(filepath, watchers_dir)
        assert result["filename"] == "my-watcher.yaml"

    def test_load_watcher_has_group_key_from_subdir(self, tmp_path):
        # Spec: watchers-us-2 — group derived from parent dir relative to watchers_dir
        from lore.watcher import load_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        filepath = self._make_watcher_file(watchers_dir, "default", "my-watcher.yaml", self.FULL_YAML)
        result = load_watcher(filepath, watchers_dir)
        assert result["group"] == "default"

    def test_load_watcher_has_exactly_eight_keys(self, tmp_path):
        # Spec: watchers-us-2 — exactly 8 keys in returned dict
        from lore.watcher import load_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        filepath = self._make_watcher_file(watchers_dir, "default", "my-watcher.yaml", self.FULL_YAML)
        result = load_watcher(filepath, watchers_dir)
        assert set(result.keys()) == {"id", "group", "title", "summary", "watch_target", "interval", "action", "filename"}

    def test_load_watcher_absent_watch_target_returns_none(self, tmp_path):
        # Spec: watchers-us-2 Scenario 4 — absent optional fields return None
        from lore.watcher import load_watcher
        minimal_yaml = "id: minimal\ntitle: Minimal\nsummary: No optionals.\n"
        watchers_dir = tmp_path / ".lore" / "watchers"
        filepath = self._make_watcher_file(watchers_dir, "default", "minimal.yaml", minimal_yaml)
        result = load_watcher(filepath, watchers_dir)
        assert result["watch_target"] is None

    def test_load_watcher_absent_interval_returns_none(self, tmp_path):
        # Spec: watchers-us-2 Scenario 4
        from lore.watcher import load_watcher
        minimal_yaml = "id: minimal\ntitle: Minimal\nsummary: No optionals.\n"
        watchers_dir = tmp_path / ".lore" / "watchers"
        filepath = self._make_watcher_file(watchers_dir, "default", "minimal.yaml", minimal_yaml)
        result = load_watcher(filepath, watchers_dir)
        assert result["interval"] is None

    def test_load_watcher_absent_action_returns_none(self, tmp_path):
        # Spec: watchers-us-2 Scenario 4
        from lore.watcher import load_watcher
        minimal_yaml = "id: minimal\ntitle: Minimal\nsummary: No optionals.\n"
        watchers_dir = tmp_path / ".lore" / "watchers"
        filepath = self._make_watcher_file(watchers_dir, "default", "minimal.yaml", minimal_yaml)
        result = load_watcher(filepath, watchers_dir)
        assert result["action"] is None


# ---------------------------------------------------------------------------
# Unit tests for create_watcher (US-3)
# ---------------------------------------------------------------------------


VALID_WATCHER_YAML = (
    "id: run-tests-on-push\n"
    "title: Run Tests\n"
    "summary: Triggers test suite on push\n"
    "watch_target: feature/*\n"
    "interval: on_push\n"
    "action: run-tests\n"
)


class TestCreateWatcher:
    """create_watcher(watchers_dir, name, content) — unit tests for US-3."""

    def test_create_watcher_creates_file(self, tmp_path):
        # Unit: create_watcher creates file at watchers_dir/{name}.yaml with provided content
        # Spec: watchers-us-3 unit scenarios
        from lore.watcher import create_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        create_watcher(watchers_dir, "run-tests-on-push", VALID_WATCHER_YAML)
        expected = watchers_dir / "run-tests-on-push.yaml"
        assert expected.exists()
        assert expected.read_text() == VALID_WATCHER_YAML

    def test_create_watcher_creates_watchers_dir_if_absent(self, tmp_path):
        # Unit: create_watcher creates watchers_dir if it does not exist
        # Spec: watchers-us-3 unit scenarios
        from lore.watcher import create_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        assert not watchers_dir.exists()
        create_watcher(watchers_dir, "run-tests-on-push", VALID_WATCHER_YAML)
        assert watchers_dir.exists()
        assert (watchers_dir / "run-tests-on-push.yaml").exists()

    def test_create_watcher_raises_value_error_on_duplicate(self, tmp_path):
        # Unit: create_watcher raises ValueError matching "already exists" when name is duplicate
        # Spec: watchers-us-3 unit scenarios — rglob detects existing file
        import pytest
        from lore.watcher import create_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        (watchers_dir / "run-tests-on-push.yaml").write_text(VALID_WATCHER_YAML)
        with pytest.raises(ValueError, match="already exists"):
            create_watcher(watchers_dir, "run-tests-on-push", VALID_WATCHER_YAML)

    def test_create_watcher_raises_value_error_for_empty_content(self, tmp_path):
        # Unit: create_watcher raises ValueError for empty content string
        # Spec: watchers-us-3 unit scenarios
        import pytest
        from lore.watcher import create_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            create_watcher(watchers_dir, "my-watcher", "")

    def test_create_watcher_raises_value_error_for_whitespace_only_content(self, tmp_path):
        # Unit: create_watcher raises ValueError for whitespace-only content (still empty)
        # Spec: watchers-us-3 unit scenarios
        import pytest
        from lore.watcher import create_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            create_watcher(watchers_dir, "my-watcher", "   \n  ")

    def test_create_watcher_raises_value_error_for_invalid_yaml(self, tmp_path):
        # Unit: create_watcher raises ValueError when content fails yaml.safe_load
        # Spec: watchers-us-3 unit scenarios
        import pytest
        from lore.watcher import create_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            create_watcher(watchers_dir, "bad-watcher", ": invalid: yaml: [")

    def test_create_watcher_raises_value_error_for_path_traversal(self, tmp_path):
        # Unit: create_watcher raises ValueError for name containing "/" (path-traversal guard)
        # Spec: watchers-us-3 unit scenarios
        import pytest
        from lore.watcher import create_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            create_watcher(watchers_dir, "../etc/passwd", VALID_WATCHER_YAML)

    def test_create_watcher_returns_dict_with_id_and_filename(self, tmp_path):
        # Unit: create_watcher returns {"id": name, "filename": f"{name}.yaml"} on success
        # Spec: watchers-us-3 unit scenarios
        from lore.watcher import create_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        result = create_watcher(watchers_dir, "run-tests-on-push", VALID_WATCHER_YAML)
        assert result == {"id": "run-tests-on-push", "filename": "run-tests-on-push.yaml"}

    def test_create_watcher_duplicate_detected_via_rglob_in_subdir(self, tmp_path):
        # Unit: rglob detects duplicate even when existing file is in a subdirectory
        # Spec: watchers-us-3 unit scenarios — duplicate check via rglob
        import pytest
        from lore.watcher import create_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        subdir = watchers_dir / "default"
        subdir.mkdir(parents=True)
        # Existing watcher in a subdirectory
        (subdir / "run-tests-on-push.yaml").write_text(VALID_WATCHER_YAML)
        with pytest.raises(ValueError, match="already exists"):
            create_watcher(watchers_dir, "run-tests-on-push", VALID_WATCHER_YAML)


# ---------------------------------------------------------------------------
# Unit tests for update_watcher (US-4)
# ---------------------------------------------------------------------------


UPDATED_WATCHER_YAML = (
    "id: my-watcher\n"
    "title: My Watcher\n"
    "summary: Updated summary\n"
    "watch_target: feature/*\n"
    "interval: daily\n"
    "action: new-action\n"
)

ORIGINAL_WATCHER_YAML = (
    "id: my-watcher\n"
    "title: My Watcher\n"
    "summary: Original summary\n"
    "watch_target: feature/*\n"
    "interval: daily\n"
    "action: run-checks\n"
)


class TestUpdateWatcher:
    """update_watcher(watchers_dir, name, content) — unit tests for US-4."""

    def test_update_watcher_overwrites_file_with_new_content(self, tmp_path):
        # Unit: update_watcher overwrites the file with new content at the same path
        # Spec: watchers-us-4 unit scenarios
        from lore.watcher import update_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        default_dir = watchers_dir / "default"
        default_dir.mkdir(parents=True)
        watcher_file = default_dir / "my-watcher.yaml"
        watcher_file.write_text(ORIGINAL_WATCHER_YAML)
        update_watcher(watchers_dir, "my-watcher", UPDATED_WATCHER_YAML)
        assert watcher_file.read_text() == UPDATED_WATCHER_YAML

    def test_update_watcher_raises_value_error_when_not_found(self, tmp_path):
        # Unit: update_watcher raises ValueError matching "not found" when watcher does not exist
        # Spec: watchers-us-4 unit scenarios
        import pytest
        from lore.watcher import update_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        with pytest.raises(ValueError, match="not found"):
            update_watcher(watchers_dir, "nonexistent", UPDATED_WATCHER_YAML)

    def test_update_watcher_raises_value_error_for_empty_content(self, tmp_path):
        # Unit: update_watcher raises ValueError for empty content string
        # Spec: watchers-us-4 unit scenarios
        import pytest
        from lore.watcher import update_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        default_dir = watchers_dir / "default"
        default_dir.mkdir(parents=True)
        (default_dir / "my-watcher.yaml").write_text(ORIGINAL_WATCHER_YAML)
        with pytest.raises(ValueError):
            update_watcher(watchers_dir, "my-watcher", "")

    def test_update_watcher_raises_value_error_for_whitespace_only_content(self, tmp_path):
        # Unit: update_watcher raises ValueError for whitespace-only content
        # Spec: watchers-us-4 unit scenarios
        import pytest
        from lore.watcher import update_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        default_dir = watchers_dir / "default"
        default_dir.mkdir(parents=True)
        (default_dir / "my-watcher.yaml").write_text(ORIGINAL_WATCHER_YAML)
        with pytest.raises(ValueError):
            update_watcher(watchers_dir, "my-watcher", "   \n  ")

    def test_update_watcher_raises_value_error_for_invalid_yaml(self, tmp_path):
        # Unit: update_watcher raises ValueError when content fails yaml.safe_load
        # Spec: watchers-us-4 unit scenarios
        import pytest
        from lore.watcher import update_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        default_dir = watchers_dir / "default"
        default_dir.mkdir(parents=True)
        (default_dir / "my-watcher.yaml").write_text(ORIGINAL_WATCHER_YAML)
        with pytest.raises(ValueError):
            update_watcher(watchers_dir, "my-watcher", ": invalid: [")

    def test_update_watcher_raises_value_error_for_path_traversal(self, tmp_path):
        # Unit: update_watcher raises ValueError for name containing "/" (path-traversal guard)
        # Spec: watchers-us-4 unit scenarios
        import pytest
        from lore.watcher import update_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            update_watcher(watchers_dir, "../etc/passwd", UPDATED_WATCHER_YAML)

    def test_update_watcher_uses_rglob_finds_in_subdirectory(self, tmp_path):
        # Unit: update_watcher uses rglob to locate watcher in subdirectory groups
        # Spec: watchers-us-4 unit scenarios
        from lore.watcher import update_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        ci_dir = watchers_dir / "ci"
        ci_dir.mkdir(parents=True)
        watcher_file = ci_dir / "run-tests.yaml"
        watcher_file.write_text(ORIGINAL_WATCHER_YAML)
        # Should not raise — rglob must find it in the ci/ subdir
        update_watcher(watchers_dir, "run-tests", UPDATED_WATCHER_YAML)
        assert watcher_file.read_text() == UPDATED_WATCHER_YAML

    def test_update_watcher_does_not_move_file(self, tmp_path):
        # Unit: update_watcher does not move the file — parent directory unchanged after update
        # Spec: watchers-us-4 unit scenarios
        from lore.watcher import update_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        ci_dir = watchers_dir / "ci"
        ci_dir.mkdir(parents=True)
        watcher_file = ci_dir / "run-tests.yaml"
        watcher_file.write_text(ORIGINAL_WATCHER_YAML)
        original_parent = watcher_file.parent
        update_watcher(watchers_dir, "run-tests", UPDATED_WATCHER_YAML)
        assert watcher_file.parent == original_parent
        assert watcher_file.parent.name == "ci"
        # File must not appear at the root level
        assert not (watchers_dir / "run-tests.yaml").exists()

    def test_update_watcher_returns_dict_with_id_and_filename(self, tmp_path):
        # Unit: update_watcher returns {"id": name, "filename": filepath.name} on success
        # Spec: watchers-us-4 unit scenarios
        from lore.watcher import update_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        default_dir = watchers_dir / "default"
        default_dir.mkdir(parents=True)
        (default_dir / "my-watcher.yaml").write_text(ORIGINAL_WATCHER_YAML)
        result = update_watcher(watchers_dir, "my-watcher", UPDATED_WATCHER_YAML)
        assert result == {"id": "my-watcher", "filename": "my-watcher.yaml"}

    def test_update_watcher_invalid_yaml_does_not_modify_file(self, tmp_path):
        # Unit: update_watcher rejects invalid YAML before any write reaches disk
        # Spec: watchers-us-4 unit scenarios
        import pytest
        from lore.watcher import update_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        default_dir = watchers_dir / "default"
        default_dir.mkdir(parents=True)
        watcher_file = default_dir / "my-watcher.yaml"
        watcher_file.write_text(ORIGINAL_WATCHER_YAML)
        with pytest.raises(ValueError):
            update_watcher(watchers_dir, "my-watcher", ": invalid: [")
        # Original content must be intact
        assert watcher_file.read_text() == ORIGINAL_WATCHER_YAML


# ---------------------------------------------------------------------------
# Unit tests for delete_watcher (US-5)
# ---------------------------------------------------------------------------


SAMPLE_WATCHER_YAML = (
    "id: run-tests-on-push\n"
    "title: Run Tests\n"
    "summary: Triggers test suite on push\n"
)


class TestDeleteWatcher:
    """delete_watcher(watchers_dir, name) — unit tests for US-5."""

    def test_delete_watcher_renames_file(self, tmp_path):
        # Unit: delete_watcher renames {name}.yaml to {name}.yaml.deleted in same directory
        # Spec: watchers-us-5 unit scenarios
        from lore.watcher import delete_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        watcher_file = watchers_dir / "run-tests-on-push.yaml"
        watcher_file.write_text(SAMPLE_WATCHER_YAML)
        delete_watcher(watchers_dir, "run-tests-on-push")
        deleted_file = watchers_dir / "run-tests-on-push.yaml.deleted"
        assert deleted_file.exists()

    def test_delete_watcher_original_removed(self, tmp_path):
        # Unit: delete_watcher — original .yaml file does not exist after deletion
        # Spec: watchers-us-5 unit scenarios
        from lore.watcher import delete_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        watcher_file = watchers_dir / "run-tests-on-push.yaml"
        watcher_file.write_text(SAMPLE_WATCHER_YAML)
        delete_watcher(watchers_dir, "run-tests-on-push")
        assert not watcher_file.exists()

    def test_delete_watcher_deleted_file_content(self, tmp_path):
        # Unit: delete_watcher — .yaml.deleted file exists after deletion and contains original content
        # Spec: watchers-us-5 unit scenarios
        from lore.watcher import delete_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        watcher_file = watchers_dir / "run-tests-on-push.yaml"
        watcher_file.write_text(SAMPLE_WATCHER_YAML)
        delete_watcher(watchers_dir, "run-tests-on-push")
        deleted_file = watchers_dir / "run-tests-on-push.yaml.deleted"
        assert deleted_file.read_text() == SAMPLE_WATCHER_YAML

    def test_delete_watcher_not_found(self, tmp_path):
        # Unit: delete_watcher raises ValueError matching "not found" when watcher does not exist
        # Spec: watchers-us-5 unit scenarios
        import pytest
        from lore.watcher import delete_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        with pytest.raises(ValueError, match="not found"):
            delete_watcher(watchers_dir, "nonexistent")

    def test_delete_watcher_path_traversal(self, tmp_path):
        # Unit: delete_watcher raises ValueError for name containing "/" (path-traversal guard)
        # Spec: watchers-us-5 unit scenarios
        import pytest
        from lore.watcher import delete_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            delete_watcher(watchers_dir, "../etc/passwd")

    def test_delete_watcher_finds_in_subdir(self, tmp_path):
        # Unit: delete_watcher uses rglob — finds watcher in subdirectory group
        # Spec: watchers-us-5 unit scenarios
        from lore.watcher import delete_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        ci_dir = watchers_dir / "ci"
        ci_dir.mkdir(parents=True)
        watcher_file = ci_dir / "run-tests.yaml"
        watcher_file.write_text(SAMPLE_WATCHER_YAML)
        delete_watcher(watchers_dir, "run-tests")
        deleted_file = ci_dir / "run-tests.yaml.deleted"
        assert deleted_file.exists()
        assert not watcher_file.exists()

    def test_delete_watcher_return_value(self, tmp_path):
        # Unit: delete_watcher returns {"id": name, "deleted": True} on success
        # Spec: watchers-us-5 unit scenarios
        from lore.watcher import delete_watcher
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        (watchers_dir / "run-tests-on-push.yaml").write_text(SAMPLE_WATCHER_YAML)
        result = delete_watcher(watchers_dir, "run-tests-on-push")
        assert result == {"id": "run-tests-on-push", "deleted": True}

    def test_list_watchers_excludes_deleted_after_delete(self, tmp_path):
        # Unit: list_watchers does not return entry for a .yaml.deleted file
        # Spec: watchers-us-5 unit scenarios (cross-story confirmation)
        from lore.watcher import delete_watcher, list_watchers
        watchers_dir = tmp_path / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True)
        (watchers_dir / "run-tests-on-push.yaml").write_text(SAMPLE_WATCHER_YAML)
        delete_watcher(watchers_dir, "run-tests-on-push")
        result = list_watchers(watchers_dir)
        ids = [w["id"] for w in result]
        assert "run-tests-on-push" not in ids
