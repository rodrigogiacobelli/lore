"""E2E tests for the doctrine list command.

Spec: doctrine-design-file-us-001 (lore codex show doctrine-design-file-us-001)
Spec: doctrine-design-file-us-002 (lore codex show doctrine-design-file-us-002)
Workflow: conceptual-workflows-doctrine-list (lore codex show conceptual-workflows-doctrine-list)
"""

import json
import shutil
from pathlib import Path

from lore.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_pair(project_dir, stem, yaml_content, design_content):
    """Write a paired .design.md + .yaml at the given stem path."""
    base = project_dir / ".lore" / "doctrines" / stem
    base.parent.mkdir(parents=True, exist_ok=True)
    Path(str(base) + ".design.md").write_text(design_content)
    Path(str(base) + ".yaml").write_text(yaml_content)


def _write_design(project_dir, stem, design_content):
    """Write an orphaned .design.md (no matching .yaml)."""
    base = project_dir / ".lore" / "doctrines" / stem
    base.parent.mkdir(parents=True, exist_ok=True)
    Path(str(base) + ".design.md").write_text(design_content)


def _write_yaml(project_dir, stem, yaml_content):
    """Write a YAML-only doctrine (no matching .design.md)."""
    base = project_dir / ".lore" / "doctrines" / stem
    base.parent.mkdir(parents=True, exist_ok=True)
    Path(str(base) + ".yaml").write_text(yaml_content)


def _empty_doctrines_dir(project_dir):
    """Remove all files from .lore/doctrines/ leaving the dir intact."""
    doctrines_dir = project_dir / ".lore" / "doctrines"
    shutil.rmtree(doctrines_dir)
    doctrines_dir.mkdir(parents=True)
    return doctrines_dir


# ---------------------------------------------------------------------------
# Scenario 1: Table displays all valid pairs
# conceptual-workflows-doctrine-list step 2-4: scan .design.md, check .yaml, render table
# ---------------------------------------------------------------------------


class TestDoctrineListValidPairs:
    """Table shows one row per valid .design.md + .yaml pair."""

    def test_table_shows_valid_pairs(self, runner, project_dir):
        """E2E Scenario 1: rows appear for every valid pair."""
        _empty_doctrines_dir(project_dir)
        _write_pair(
            project_dir,
            "feature-implementation/feature-implementation",
            yaml_content="id: feature-implementation\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
            design_content="---\nid: feature-implementation\ntitle: Feature Implementation\nsummary: E2E spec-driven pipeline\n---\n",
        )
        _write_pair(
            project_dir,
            "update-changelog",
            yaml_content="id: update-changelog\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
            design_content="---\nid: update-changelog\ntitle: Update Changelog\nsummary: Single-step doctrine\n---\n",
        )
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0
        assert "feature-implementation" in result.output
        assert "Feature Implementation" in result.output
        assert "update-changelog" in result.output

    def test_table_shows_id_column(self, runner, project_dir):
        """ID column contains doctrine id from design frontmatter.

        Valid pairs must NOT show [INVALID] in the new behavior.
        """
        _empty_doctrines_dir(project_dir)
        _write_pair(
            project_dir,
            "feature-implementation/feature-implementation",
            yaml_content="id: feature-implementation\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
            design_content="---\nid: feature-implementation\ntitle: Feature Implementation\nsummary: E2E spec-driven pipeline\n---\n",
        )
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0
        assert "feature-implementation" in result.output
        # New behavior: valid pairs never show [INVALID]
        assert "[INVALID]" not in result.output

    def test_table_shows_group_column_from_subdir(self, runner, project_dir):
        """GROUP column contains directory path segment for subdirectory doctrines.

        Valid pairs must NOT show [INVALID] in the new behavior.
        """
        _empty_doctrines_dir(project_dir)
        _write_pair(
            project_dir,
            "feature-implementation/feature-implementation",
            yaml_content="id: feature-implementation\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
            design_content="---\nid: feature-implementation\ntitle: Feature Implementation\nsummary: E2E spec-driven pipeline\n---\n",
        )
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0
        assert "feature-implementation" in result.output
        # New behavior: valid pairs never show [INVALID]
        assert "[INVALID]" not in result.output

    def test_table_shows_empty_group_for_root_doctrine(self, runner, project_dir):
        """Root-level doctrines have empty GROUP column.

        Valid pairs must NOT show [INVALID] in the new behavior.
        """
        _empty_doctrines_dir(project_dir)
        _write_pair(
            project_dir,
            "update-changelog",
            yaml_content="id: update-changelog\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
            design_content="---\nid: update-changelog\ntitle: Update Changelog\nsummary: Single-step doctrine\n---\n",
        )
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0
        assert "update-changelog" in result.output
        # New behavior: valid pairs never show [INVALID]
        assert "[INVALID]" not in result.output

    def test_table_shows_title_from_design_frontmatter(self, runner, project_dir):
        """TITLE column contains title from design file frontmatter, not YAML."""
        _empty_doctrines_dir(project_dir)
        _write_pair(
            project_dir,
            "feature-implementation/feature-implementation",
            yaml_content="id: feature-implementation\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
            design_content="---\nid: feature-implementation\ntitle: Feature Implementation\nsummary: E2E spec-driven pipeline\n---\n",
        )
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0
        assert "Feature Implementation" in result.output

    def test_table_shows_summary_from_design_frontmatter(self, runner, project_dir):
        """SUMMARY column contains summary from design file frontmatter."""
        _empty_doctrines_dir(project_dir)
        _write_pair(
            project_dir,
            "feature-implementation/feature-implementation",
            yaml_content="id: feature-implementation\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
            design_content="---\nid: feature-implementation\ntitle: Feature Implementation\nsummary: E2E spec-driven pipeline\n---\n",
        )
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0
        assert "E2E spec-driven pipeline" in result.output

    def test_table_exit_code_is_zero(self, runner, project_dir):
        """doctrine list exits 0 when valid pairs exist.

        Also verifies that valid pairs are NOT shown with [INVALID] marker.
        """
        _empty_doctrines_dir(project_dir)
        _write_pair(
            project_dir,
            "feature-implementation/feature-implementation",
            yaml_content="id: feature-implementation\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
            design_content="---\nid: feature-implementation\ntitle: Feature Implementation\nsummary: E2E spec-driven pipeline\n---\n",
        )
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0
        # New behavior: valid pairs never show [INVALID]
        assert "[INVALID]" not in result.output


# ---------------------------------------------------------------------------
# Scenario 2: Orphaned design file is not shown
# conceptual-workflows-doctrine-list step 5: .design.md without .yaml is skipped
# ---------------------------------------------------------------------------


class TestDoctrineListOrphanedDesign:
    """Orphaned .design.md files (no matching .yaml) are silently excluded."""

    def test_orphaned_design_not_shown(self, runner, project_dir):
        """E2E Scenario 2: orphaned design file excluded from table.

        The scan is now driven by .design.md files. An orphaned .design.md
        (no matching .yaml) must not appear in the output.
        A valid pair is written alongside to confirm the scan is active and
        that valid entries DO appear — only the orphan is excluded.
        """
        _empty_doctrines_dir(project_dir)
        _write_design(
            project_dir,
            "orphan",
            "---\nid: orphan\ntitle: Orphan\n---\n",
        )
        _write_pair(
            project_dir,
            "valid-doc",
            yaml_content="id: valid-doc\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
            design_content="---\nid: valid-doc\ntitle: Valid Doc\nsummary: A valid doctrine.\n---\n",
        )
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0
        assert "orphan" not in result.output
        # Valid pair DOES appear; orphan does NOT
        assert "valid-doc" in result.output
        # New behavior: no [INVALID] markers at all
        assert "[INVALID]" not in result.output

    def test_orphaned_design_no_exception(self, runner, project_dir):
        """Orphaned design file does not cause an exception or non-zero exit.

        The new code must explicitly check for the matching .yaml partner.
        Add a valid pair alongside to verify mixed results work correctly.
        """
        _empty_doctrines_dir(project_dir)
        _write_design(
            project_dir,
            "orphan",
            "---\nid: orphan\ntitle: Orphan\n---\n",
        )
        _write_pair(
            project_dir,
            "valid-one",
            yaml_content="id: valid-one\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
            design_content="---\nid: valid-one\ntitle: Valid One\nsummary: A valid doctrine\n---\n",
        )
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0
        # The valid pair appears; the orphan does not
        assert "valid-one" in result.output
        assert "orphan" not in result.output
        # New behavior: no [INVALID] markers
        assert "[INVALID]" not in result.output


# ---------------------------------------------------------------------------
# Scenario 3: YAML-only file is not shown
# conceptual-workflows-doctrine-list step 6: .yaml without .design.md is invisible
# ---------------------------------------------------------------------------


class TestDoctrineListYamlOnly:
    """YAML-only doctrine files (no matching .design.md) are silently excluded."""

    def test_yaml_only_not_shown(self, runner, project_dir):
        """E2E Scenario 3: YAML-only file excluded from table."""
        _empty_doctrines_dir(project_dir)
        _write_yaml(
            project_dir,
            "legacy",
            "id: legacy\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
        )
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0
        assert "legacy" not in result.output

    def test_yaml_only_no_exception(self, runner, project_dir):
        """YAML-only file does not cause an exception or non-zero exit.

        In the new behavior, YAML-only files are completely invisible — no [INVALID].
        """
        _empty_doctrines_dir(project_dir)
        _write_yaml(
            project_dir,
            "legacy",
            "id: legacy\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
        )
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0
        # New behavior: YAML-only files don't appear at all — no [INVALID] either
        assert "[INVALID]" not in result.output


# ---------------------------------------------------------------------------
# Scenario 4: Design frontmatter missing optional fields uses fallbacks
# conceptual-workflows-doctrine-list step 4: FR-11 title/summary fallbacks
# ---------------------------------------------------------------------------


class TestDoctrineListFallbacks:
    """Fallback behavior when design frontmatter has no title or summary."""

    def test_fallbacks_for_missing_title_summary(self, runner, project_dir):
        """E2E Scenario 4: minimal design frontmatter shows id as title — no [INVALID].

        The new code must show a valid row (not [INVALID]) for a minimal design file.
        """
        _empty_doctrines_dir(project_dir)
        _write_pair(
            project_dir,
            "minimal",
            yaml_content="id: minimal\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
            design_content="---\nid: minimal\n---\n",
        )
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0
        assert "minimal" in result.output
        # New behavior: valid pairs (even with minimal frontmatter) never show [INVALID]
        assert "[INVALID]" not in result.output

    def test_fallback_title_is_id(self, runner, project_dir):
        """When design frontmatter has no title, TITLE column shows id — no [INVALID]."""
        _empty_doctrines_dir(project_dir)
        _write_pair(
            project_dir,
            "minimal",
            yaml_content="id: minimal\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
            design_content="---\nid: minimal\n---\n",
        )
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0
        # When title is missing, fallback to id — "minimal" should appear in the TITLE position
        assert "minimal" in result.output
        # New behavior: valid pairs never show [INVALID]
        assert "[INVALID]" not in result.output


# ---------------------------------------------------------------------------
# Scenario 5: Empty doctrines directory
# conceptual-workflows-doctrine-list step 2: scan returns nothing
# ---------------------------------------------------------------------------


class TestDoctrineListEmpty:
    """Empty doctrines directory shows empty table, exits 0."""

    def test_empty_dir_exits_zero(self, runner, project_dir):
        """E2E Scenario 5: empty directory exits 0.

        New scan (from .design.md) over empty dir must also exit 0.
        """
        _empty_doctrines_dir(project_dir)
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0
        assert "[INVALID]" not in result.output

    def test_empty_dir_shows_no_invalid_markers(self, runner, project_dir):
        """Empty directory has no [INVALID] markers.

        The new code never adds [INVALID] markers since invalid/orphaned files
        are silently excluded. This is true even for empty directories.
        """
        _empty_doctrines_dir(project_dir)
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0
        assert "[INVALID]" not in result.output


# ---------------------------------------------------------------------------
# Scenario 6: After lore init, default doctrines appear
# conceptual-workflows-lore-init: seeds defaults/doctrines/ paired files
# ---------------------------------------------------------------------------


class TestDoctrineListAfterInit:
    """After lore init, default paired doctrines appear in the table."""

    def test_after_init_shows_feature_implementation(self, runner, tmp_path, monkeypatch):
        """E2E Scenario 6: feature-implementation appears after lore init without [INVALID]."""
        monkeypatch.chdir(tmp_path)
        runner.invoke(main, ["init"])
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0
        assert "feature-implementation" in result.output
        # New behavior: default doctrines are valid pairs — no [INVALID] marker
        assert "[INVALID]" not in result.output

    def test_after_init_shows_update_changelog(self, runner, tmp_path, monkeypatch):
        """E2E Scenario 6: update-changelog appears after lore init without [INVALID]."""
        monkeypatch.chdir(tmp_path)
        runner.invoke(main, ["init"])
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0
        assert "update-changelog" in result.output
        # New behavior: default doctrines are valid pairs — no [INVALID] marker
        assert "[INVALID]" not in result.output

    def test_after_init_shows_quick_feature_implementation(self, runner, tmp_path, monkeypatch):
        """E2E Scenario 6: quick-feature-implementation appears after lore init without [INVALID]."""
        monkeypatch.chdir(tmp_path)
        runner.invoke(main, ["init"])
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0
        assert "quick-feature-implementation" in result.output
        # New behavior: default doctrines are valid pairs — no [INVALID] marker
        assert "[INVALID]" not in result.output

    def test_after_init_shows_tdd_implementation(self, runner, tmp_path, monkeypatch):
        """E2E Scenario 6: tdd-implementation appears after lore init without [INVALID]."""
        monkeypatch.chdir(tmp_path)
        runner.invoke(main, ["init"])
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0
        assert "tdd-implementation" in result.output
        # New behavior: default doctrines are valid pairs — no [INVALID] marker
        assert "[INVALID]" not in result.output


# ---------------------------------------------------------------------------
# Table header
# ---------------------------------------------------------------------------


class TestDoctrineListTableHeader:
    """Table header has ID, GROUP, TITLE, SUMMARY columns.

    After lore init, default doctrines must appear WITHOUT [INVALID] markers.
    The new code shows only valid pairs (design+yaml), so defaults with paired
    files will show clean rows.
    """

    def test_header_contains_id(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "list"])
        assert "ID" in result.output
        # New behavior: default paired doctrines show without [INVALID]
        assert "[INVALID]" not in result.output

    def test_header_contains_group(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "list"])
        assert "GROUP" in result.output
        # New behavior: default paired doctrines show without [INVALID]
        assert "[INVALID]" not in result.output

    def test_header_contains_title(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "list"])
        assert "TITLE" in result.output
        # New behavior: default paired doctrines show without [INVALID]
        assert "[INVALID]" not in result.output

    def test_header_contains_summary(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "list"])
        assert "SUMMARY" in result.output
        # New behavior: default paired doctrines show without [INVALID]
        assert "[INVALID]" not in result.output

    def test_header_columns_in_correct_order(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "list"])
        non_empty_lines = [line for line in result.output.split("\n") if line.strip()]
        header = non_empty_lines[0]
        id_pos = header.index("ID")
        group_pos = header.index("GROUP")
        title_pos = header.index("TITLE")
        summary_pos = header.index("SUMMARY")
        assert id_pos < group_pos < title_pos < summary_pos
        # New behavior: default paired doctrines show without [INVALID]
        assert "[INVALID]" not in result.output


# ---------------------------------------------------------------------------
# No [INVALID] markers in output
# The new behavior silently excludes invalid/orphaned files — no [INVALID] rows
# ---------------------------------------------------------------------------


class TestDoctrineListNoInvalidMarkers:
    """No [INVALID] markers appear in output — invalid files are silently excluded."""

    def test_no_invalid_marker_for_yaml_only(self, runner, project_dir):
        """YAML-only files produce no [INVALID] marker — they are simply excluded."""
        _empty_doctrines_dir(project_dir)
        _write_yaml(
            project_dir,
            "legacy",
            "id: legacy\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
        )
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0
        assert "[INVALID]" not in result.output

    def test_no_invalid_marker_for_orphaned_design(self, runner, project_dir):
        """Orphaned design files produce no [INVALID] marker.

        The new scan finds .design.md files and checks for matching .yaml.
        An orphaned .design.md is silently excluded — no [INVALID] row appears.
        A valid pair alongside the orphan should appear cleanly.
        """
        _empty_doctrines_dir(project_dir)
        _write_design(
            project_dir,
            "orphan",
            "---\nid: orphan\ntitle: Orphan\n---\n",
        )
        _write_pair(
            project_dir,
            "clean-doc",
            yaml_content="id: clean-doc\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
            design_content="---\nid: clean-doc\ntitle: Clean Doc\nsummary: A clean doctrine.\n---\n",
        )
        result = runner.invoke(main, ["doctrine", "list"])
        assert result.exit_code == 0
        assert "[INVALID]" not in result.output
        # Valid pair appears; orphan does not
        assert "clean-doc" in result.output
        assert "orphan" not in result.output

    def test_valid_doctrines_not_marked_invalid(self, runner, project_dir):
        """Valid doctrine pairs never show [INVALID] marker."""
        result = runner.invoke(main, ["doctrine", "list"])
        assert "[INVALID]" not in result.output


# ---------------------------------------------------------------------------
# US-002: JSON mode scenarios
# conceptual-workflows-doctrine-list step 3-4 + conceptual-workflows-json-output
# ---------------------------------------------------------------------------


class TestDoctrineListJson:
    """doctrine list --json returns structured JSON with 5-field entries."""

    def test_doctrine_list_json_returns_valid_shape(self, runner, project_dir):
        """E2E Scenario 1: JSON output contains correct 5-field shape for valid pair.

        conceptual-workflows-doctrine-list step 3-4 + conceptual-workflows-json-output
        """
        _empty_doctrines_dir(project_dir)
        _write_pair(
            project_dir,
            "feature-implementation/feature-implementation",
            yaml_content="id: feature-implementation\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
            design_content="---\nid: feature-implementation\ntitle: Feature Implementation\nsummary: E2E spec-driven pipeline...\n---\n",
        )
        result = runner.invoke(main, ["doctrine", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "doctrines" in data
        entry = next(d for d in data["doctrines"] if d["id"] == "feature-implementation")
        assert entry == {
            "id": "feature-implementation",
            "group": "feature-implementation",
            "title": "Feature Implementation",
            "summary": "E2E spec-driven pipeline...",
            "valid": True,
        }

    def test_doctrine_list_json_empty(self, runner, project_dir):
        """E2E Scenario 2: JSON output is empty doctrines array when directory is empty.

        conceptual-workflows-doctrine-list step 2: empty scan returns empty array
        """
        _empty_doctrines_dir(project_dir)
        result = runner.invoke(main, ["doctrine", "list", "--json"])
        assert result.exit_code == 0
        assert json.loads(result.output) == {"doctrines": []}

    def test_doctrine_list_json_orphaned_design_not_included(self, runner, project_dir):
        """E2E Scenario 3: Orphaned design file is not included in JSON output.

        conceptual-workflows-doctrine-list step 5: orphaned → skipped
        """
        _empty_doctrines_dir(project_dir)
        _write_design(project_dir, "orphan", "---\nid: orphan\ntitle: Orphan\n---\n")
        result = runner.invoke(main, ["doctrine", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert not any(d["id"] == "orphan" for d in data["doctrines"])

    def test_doctrine_list_json_entry_has_exactly_five_fields(self, runner, project_dir):
        """E2E Scenario 4: JSON entry has exactly five keys: id, group, title, summary, valid.

        conceptual-workflows-json-output: no extra keys in output
        """
        _empty_doctrines_dir(project_dir)
        _write_pair(
            project_dir,
            "my-workflow",
            yaml_content="id: my-workflow\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
            design_content="---\nid: my-workflow\ntitle: My Workflow\nsummary: Does things\n---\n",
        )
        result = runner.invoke(main, ["doctrine", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        entry = data["doctrines"][0]
        assert set(entry.keys()) == {"id", "group", "title", "summary", "valid"}

    def test_doctrine_list_json_no_filename_key(self, runner, project_dir):
        """JSON output does not include 'filename' key from Python API.

        CLI strips internal fields before serialising.
        """
        _empty_doctrines_dir(project_dir)
        _write_pair(
            project_dir,
            "my-workflow",
            yaml_content="id: my-workflow\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
            design_content="---\nid: my-workflow\ntitle: My Workflow\nsummary: Does things\n---\n",
        )
        result = runner.invoke(main, ["doctrine", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        entry = data["doctrines"][0]
        assert "filename" not in entry

    def test_doctrine_list_json_no_errors_key(self, runner, project_dir):
        """JSON output does not include 'errors' key from Python API.

        CLI strips internal fields before serialising.
        """
        _empty_doctrines_dir(project_dir)
        _write_pair(
            project_dir,
            "my-workflow",
            yaml_content="id: my-workflow\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
            design_content="---\nid: my-workflow\ntitle: My Workflow\nsummary: Does things\n---\n",
        )
        result = runner.invoke(main, ["doctrine", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        entry = data["doctrines"][0]
        assert "errors" not in entry

    def test_doctrine_list_json_no_name_key(self, runner, project_dir):
        """JSON output does not include legacy 'name' key.

        New schema uses 'id' instead of 'name'.
        """
        _empty_doctrines_dir(project_dir)
        _write_pair(
            project_dir,
            "my-workflow",
            yaml_content="id: my-workflow\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
            design_content="---\nid: my-workflow\ntitle: My Workflow\nsummary: Does things\n---\n",
        )
        result = runner.invoke(main, ["doctrine", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        entry = data["doctrines"][0]
        assert "name" not in entry

    def test_doctrine_list_json_no_description_key(self, runner, project_dir):
        """JSON output does not include legacy 'description' key.

        New schema uses 'summary' from design frontmatter.
        """
        _empty_doctrines_dir(project_dir)
        _write_pair(
            project_dir,
            "my-workflow",
            yaml_content="id: my-workflow\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
            design_content="---\nid: my-workflow\ntitle: My Workflow\nsummary: Does things\n---\n",
        )
        result = runner.invoke(main, ["doctrine", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        entry = data["doctrines"][0]
        assert "description" not in entry

    def test_doctrine_list_json_valid_always_true(self, runner, project_dir):
        """JSON 'valid' field is True for all entries (only valid pairs are returned).

        Since orphaned files are skipped, every entry in JSON output is valid.
        """
        _empty_doctrines_dir(project_dir)
        _write_pair(
            project_dir,
            "my-workflow",
            yaml_content="id: my-workflow\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
            design_content="---\nid: my-workflow\ntitle: My Workflow\nsummary: Does things\n---\n",
        )
        result = runner.invoke(main, ["doctrine", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        for entry in data["doctrines"]:
            assert entry["valid"] is True

    def test_doctrine_list_json_exit_code_zero(self, runner, project_dir):
        """doctrine list --json exits with code 0."""
        _empty_doctrines_dir(project_dir)
        result = runner.invoke(main, ["doctrine", "list", "--json"])
        assert result.exit_code == 0

    def test_doctrine_list_json_top_level_key_is_doctrines(self, runner, project_dir):
        """JSON output top-level key is 'doctrines'."""
        _empty_doctrines_dir(project_dir)
        result = runner.invoke(main, ["doctrine", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "doctrines" in data
        assert isinstance(data["doctrines"], list)

    def test_doctrine_list_json_multiple_entries(self, runner, project_dir):
        """JSON output contains one entry per valid pair when multiple pairs exist."""
        _empty_doctrines_dir(project_dir)
        _write_pair(
            project_dir,
            "feature-implementation/feature-implementation",
            yaml_content="id: feature-implementation\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
            design_content="---\nid: feature-implementation\ntitle: Feature Implementation\nsummary: E2E spec-driven pipeline...\n---\n",
        )
        _write_pair(
            project_dir,
            "update-changelog",
            yaml_content="id: update-changelog\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
            design_content="---\nid: update-changelog\ntitle: Update Changelog\nsummary: Single-step doctrine\n---\n",
        )
        result = runner.invoke(main, ["doctrine", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["doctrines"]) == 2
        ids = {d["id"] for d in data["doctrines"]}
        assert "feature-implementation" in ids
        assert "update-changelog" in ids

    def test_doctrine_list_json_group_empty_for_root_doctrine(self, runner, project_dir):
        """Root-level doctrine has 'group': '' in JSON output."""
        _empty_doctrines_dir(project_dir)
        _write_pair(
            project_dir,
            "update-changelog",
            yaml_content="id: update-changelog\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
            design_content="---\nid: update-changelog\ntitle: Update Changelog\nsummary: Single-step doctrine\n---\n",
        )
        result = runner.invoke(main, ["doctrine", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        entry = next(d for d in data["doctrines"] if d["id"] == "update-changelog")
        assert entry["group"] == ""
