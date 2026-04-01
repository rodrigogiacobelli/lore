"""E2E tests for the artifact list and show commands.

Spec: conceptual-workflows-artifact-list (lore codex show conceptual-workflows-artifact-list)
"""

import json
import shutil
from pathlib import Path

import pytest

from lore.artifact import scan_artifacts
from lore.cli import main, _format_table
from lore.frontmatter import parse_frontmatter_doc
from lore.doctrine import list_doctrines
from lore.knight import list_knights

import lore as _lore_pkg

_DEFAULTS_ARTIFACTS_DIR = Path(_lore_pkg.__file__).parent / "defaults" / "artifacts"
_ALL_ARTIFACT_MD_FILES = sorted(_DEFAULTS_ARTIFACTS_DIR.rglob("*.md"))
_TEMPLATE_FILES = [f for f in _ALL_ARTIFACT_MD_FILES if f.name != "README.md"]
_README_FILES = [f for f in _ALL_ARTIFACT_MD_FILES if f.name == "README.md"]
_EXPECTED_ARTIFACT_COUNT = len(_TEMPLATE_FILES)


# ---------------------------------------------------------------------------
# Helpers and fixtures
# ---------------------------------------------------------------------------


def _write_artifact(project_dir, rel_path, content):
    """Helper to write a markdown file into .lore/artifacts/."""
    artifact_path = project_dir / ".lore" / "artifacts" / rel_path
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(content)
    return artifact_path


@pytest.fixture()
def bare_project_dir(tmp_path, monkeypatch):
    """Create a minimal Lore project with .lore/ but no artifact files."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".lore").mkdir()
    return tmp_path


# Fixture artifacts used across tests

VALID_ARTIFACT = """\
---
id: transient-business-spec
title: Business Spec Template
summary: Template for writing a business spec.
---

# Business Spec Template

Body content here.
"""

VALID_ARTIFACT_B = """\
---
id: transient-full-spec
title: Full Spec Template
summary: Template for writing a full technical spec.
---

# Full Spec Template

More body content.
"""

ARTIFACT_WITH_BODY = """\
---
id: show-biz-spec
title: Business Spec Template
summary: Template for writing a business spec.
---

# Business Spec Template

Body content here.
"""

ARTIFACT_B_FOR_MULTI = """\
---
id: show-full-spec
title: Full Spec Template
summary: Full spec template.
---

# Full Spec Template

More body.
"""

ARTIFACT_ALPHA = """\
---
id: alpha-artifact
title: Alpha Artifact
summary: The first artifact alphabetically.
---

# Alpha Artifact
"""

ARTIFACT_BRAVO = """\
---
id: bravo-artifact
title: Bravo Artifact
summary: The second artifact alphabetically.
---

# Bravo Artifact
"""

NESTED_ARTIFACT = """\
---
id: nested-one
title: Nested One
summary: Lives inside a subdirectory.
---

# Nested One
"""

ROOT_LEVEL_ARTIFACT = """\
---
id: root-level
title: Root Level Artifact
summary: Sits at the top level with no subdirectory.
---

# Root Level Artifact
"""

ARTIFACT_ROOT = """\
---
id: root-artifact
title: Root Artifact
summary: An artifact at the top level, no subdirectory.
---

# Root Artifact
"""

ARTIFACT_IN_SUBDIR = """\
---
id: sub-artifact
title: Sub Artifact
summary: An artifact inside a subdirectory.
---

# Sub Artifact
"""

ARTIFACT_IN_DEEP_SUBDIR = """\
---
id: deep-artifact
title: Deep Artifact
summary: An artifact inside a nested subdirectory.
---

# Deep Artifact
"""

SPEC_KEY_ORDER = ["id", "group", "title", "summary"]


# ---------------------------------------------------------------------------
# Unit tests: scan_artifacts()
# ---------------------------------------------------------------------------


class TestScanArtifactsReturnsAllArtifacts:
    """scan_artifacts() returns all valid artifacts."""

    def test_returns_list(self, tmp_path):
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "art-a.md").write_text(VALID_ARTIFACT)
        result = scan_artifacts(artifacts_dir)
        assert isinstance(result, list)

    def test_artifact_has_id_field(self, tmp_path):
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "art-a.md").write_text(VALID_ARTIFACT)
        result = scan_artifacts(artifacts_dir)
        assert len(result) == 1
        assert result[0]["id"] == "transient-business-spec"

    def test_artifact_has_title_field(self, tmp_path):
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "art-a.md").write_text(VALID_ARTIFACT)
        result = scan_artifacts(artifacts_dir)
        assert result[0]["title"] == "Business Spec Template"

    def test_artifact_has_summary_field(self, tmp_path):
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "art-a.md").write_text(VALID_ARTIFACT)
        result = scan_artifacts(artifacts_dir)
        assert result[0]["summary"] == "Template for writing a business spec."

    def test_artifact_has_path_field(self, tmp_path):
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "art-a.md").write_text(VALID_ARTIFACT)
        result = scan_artifacts(artifacts_dir)
        assert "path" in result[0]

    def test_walks_subdirectories_recursively(self, tmp_path):
        artifacts_dir = tmp_path / "artifacts"
        subdir = artifacts_dir / "sub"
        subdir.mkdir(parents=True)
        (subdir / "nested.md").write_text(VALID_ARTIFACT)
        result = scan_artifacts(artifacts_dir)
        assert len(result) == 1
        assert result[0]["id"] == "transient-business-spec"


class TestScanArtifactsEmptyOrMissingDirectory:
    """scan_artifacts() returns empty list when directory is absent or empty."""

    def test_missing_dir_returns_empty_list(self, tmp_path):
        artifacts_dir = tmp_path / "nonexistent"
        result = scan_artifacts(artifacts_dir)
        assert result == []

    def test_empty_dir_returns_empty_list(self, tmp_path):
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        result = scan_artifacts(artifacts_dir)
        assert result == []

    def test_missing_dir_does_not_raise(self, tmp_path):
        artifacts_dir = tmp_path / "no" / "such" / "path"
        result = scan_artifacts(artifacts_dir)
        assert result == []


class TestScanArtifactsInvalidFrontmatterSkipped:
    """scan_artifacts() silently skips files with missing or invalid frontmatter."""

    def test_file_without_frontmatter_skipped(self, tmp_path):
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "no-fm.md").write_text("# No Frontmatter\n")
        result = scan_artifacts(artifacts_dir)
        assert result == []

    def test_invalid_file_skipped_valid_still_returned(self, tmp_path):
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "no-fm.md").write_text("# No Frontmatter\n")
        (artifacts_dir / "valid.md").write_text(VALID_ARTIFACT)
        result = scan_artifacts(artifacts_dir)
        assert len(result) == 1
        assert result[0]["id"] == "transient-business-spec"

class TestScanArtifactsSoftDeletedExcluded:
    """scan_artifacts() excludes .md.deleted files."""

    def test_soft_deleted_file_excluded(self, tmp_path):
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "art-a.md.deleted").write_text(VALID_ARTIFACT)
        result = scan_artifacts(artifacts_dir)
        assert result == []

    def test_soft_deleted_excluded_valid_still_returned(self, tmp_path):
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "art-a.md.deleted").write_text(VALID_ARTIFACT)
        (artifacts_dir / "valid.md").write_text(VALID_ARTIFACT_B)
        result = scan_artifacts(artifacts_dir)
        assert len(result) == 1
        assert result[0]["id"] == "transient-full-spec"


class TestScanArtifactsSortedAlphabetically:
    """scan_artifacts() returns artifacts sorted alphabetically by id."""

    def test_multiple_artifacts_sorted_by_id(self, tmp_path):
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "zzz.md").write_text(ARTIFACT_BRAVO)
        (artifacts_dir / "aaa.md").write_text(ARTIFACT_ALPHA)
        result = scan_artifacts(artifacts_dir)
        ids = [a["id"] for a in result]
        assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# Integration tests: lore artifact list (human-readable)
# ---------------------------------------------------------------------------


class TestArtifactListHumanOutput:
    """lore artifact list renders table with correct columns and content."""

    def test_exit_code_0_with_artifacts(self, runner, project_dir):
        result = runner.invoke(main, ["artifact", "list"])
        assert result.exit_code == 0

    def test_output_contains_id(self, runner, project_dir):
        _write_artifact(project_dir, "art-a.md", VALID_ARTIFACT)
        result = runner.invoke(main, ["artifact", "list"])
        assert "transient-business-spec" in result.output

    def test_output_contains_title(self, runner, project_dir):
        _write_artifact(project_dir, "art-a.md", VALID_ARTIFACT)
        result = runner.invoke(main, ["artifact", "list"])
        assert "Business Spec Template" in result.output

    def test_output_contains_summary(self, runner, project_dir):
        _write_artifact(project_dir, "art-a.md", VALID_ARTIFACT)
        result = runner.invoke(main, ["artifact", "list"])
        assert "Template for writing a business spec." in result.output

    def test_table_has_id_column_header(self, runner, project_dir):
        result = runner.invoke(main, ["artifact", "list"])
        assert "ID" in result.output

    def test_table_has_group_column_header(self, runner, project_dir):
        result = runner.invoke(main, ["artifact", "list"])
        assert "GROUP" in result.output

    def test_table_has_title_column_header(self, runner, project_dir):
        result = runner.invoke(main, ["artifact", "list"])
        assert "TITLE" in result.output

    def test_table_has_summary_column_header(self, runner, project_dir):
        result = runner.invoke(main, ["artifact", "list"])
        assert "SUMMARY" in result.output

class TestArtifactListEmptyState:
    """lore artifact list with no artifacts outputs correct empty message."""

    def test_exit_code_0_when_no_artifacts(self, runner, bare_project_dir):
        result = runner.invoke(main, ["artifact", "list"])
        assert result.exit_code == 0

    def test_empty_message_displayed(self, runner, bare_project_dir):
        result = runner.invoke(main, ["artifact", "list"])
        assert "No artifacts found." in result.output


# ---------------------------------------------------------------------------
# Integration tests: lore artifact list --json
# ---------------------------------------------------------------------------


class TestArtifactListJsonOutput:
    """lore artifact list --json emits valid JSON with correct schema."""

    def test_exit_code_0_with_json_flag(self, runner, bare_project_dir):
        _write_artifact(bare_project_dir, "art-a.md", VALID_ARTIFACT)
        result = runner.invoke(main, ["artifact", "list", "--json"])
        assert result.exit_code == 0

    def test_json_output_is_valid_json(self, runner, bare_project_dir):
        _write_artifact(bare_project_dir, "art-a.md", VALID_ARTIFACT)
        result = runner.invoke(main, ["artifact", "list", "--json"])
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_json_output_has_artifacts_key(self, runner, bare_project_dir):
        _write_artifact(bare_project_dir, "art-a.md", VALID_ARTIFACT)
        result = runner.invoke(main, ["artifact", "list", "--json"])
        data = json.loads(result.output)
        assert "artifacts" in data

    def test_json_artifacts_is_a_list(self, runner, bare_project_dir):
        _write_artifact(bare_project_dir, "art-a.md", VALID_ARTIFACT)
        result = runner.invoke(main, ["artifact", "list", "--json"])
        data = json.loads(result.output)
        assert isinstance(data["artifacts"], list)

    def test_json_artifact_has_id_field(self, runner, bare_project_dir):
        _write_artifact(bare_project_dir, "art-a.md", VALID_ARTIFACT)
        result = runner.invoke(main, ["artifact", "list", "--json"])
        data = json.loads(result.output)
        assert data["artifacts"][0]["id"] == "transient-business-spec"

    def test_json_artifact_has_group_field(self, runner, bare_project_dir):
        _write_artifact(bare_project_dir, "art-a.md", VALID_ARTIFACT)
        result = runner.invoke(main, ["artifact", "list", "--json"])
        data = json.loads(result.output)
        assert "group" in data["artifacts"][0]

    def test_json_artifact_has_title_field(self, runner, bare_project_dir):
        _write_artifact(bare_project_dir, "art-a.md", VALID_ARTIFACT)
        result = runner.invoke(main, ["artifact", "list", "--json"])
        data = json.loads(result.output)
        assert data["artifacts"][0]["title"] == "Business Spec Template"

    def test_json_artifact_has_summary_field(self, runner, bare_project_dir):
        _write_artifact(bare_project_dir, "art-a.md", VALID_ARTIFACT)
        result = runner.invoke(main, ["artifact", "list", "--json"])
        data = json.loads(result.output)
        assert data["artifacts"][0]["summary"] == "Template for writing a business spec."

    def test_json_artifact_does_not_have_path_field(self, runner, bare_project_dir):
        _write_artifact(bare_project_dir, "art-a.md", VALID_ARTIFACT)
        result = runner.invoke(main, ["artifact", "list", "--json"])
        data = json.loads(result.output)
        assert "path" not in data["artifacts"][0]

    def test_json_empty_state_returns_empty_artifacts_array(self, runner, bare_project_dir):
        result = runner.invoke(main, ["artifact", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == {"artifacts": []}

    def test_json_artifacts_sorted_by_id(self, runner, bare_project_dir):
        _write_artifact(bare_project_dir, "zzz.md", ARTIFACT_BRAVO)
        _write_artifact(bare_project_dir, "aaa.md", ARTIFACT_ALPHA)
        result = runner.invoke(main, ["artifact", "list", "--json"])
        data = json.loads(result.output)
        ids = [a["id"] for a in data["artifacts"]]
        assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# Integration tests: lore artifact show (human-readable)
# ---------------------------------------------------------------------------


class TestArtifactShowHumanOutput:
    """lore artifact show <id> renders body with separator for a known ID."""

    def test_exit_code_0_for_known_id(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        result = runner.invoke(main, ["artifact", "show", "show-biz-spec"])
        assert result.exit_code == 0

    def test_output_contains_separator_with_id(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        result = runner.invoke(main, ["artifact", "show", "show-biz-spec"])
        assert "=== show-biz-spec ===" in result.output

    def test_output_contains_body_content(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        result = runner.invoke(main, ["artifact", "show", "show-biz-spec"])
        assert "# Business Spec Template" in result.output

    def test_output_does_not_contain_frontmatter(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        result = runner.invoke(main, ["artifact", "show", "show-biz-spec"])
        assert "id: show-biz-spec" not in result.output
        assert "title: Business Spec Template" not in result.output


class TestArtifactShowUnknownId:
    """lore artifact show <id> exits 1 and writes error to stderr for unknown ID."""

    def test_exit_code_1_for_unknown_id(self, runner, project_dir):
        result = runner.invoke(main, ["artifact", "show", "no-such-artifact"])
        assert result.exit_code == 1

    def test_error_message_written_to_stderr(self, runner, project_dir):
        result = runner.invoke(main, ["artifact", "show", "no-such-artifact"])
        assert "no-such-artifact" in result.stderr

    def test_error_message_format(self, runner, project_dir):
        result = runner.invoke(main, ["artifact", "show", "missing-artifact"])
        assert 'Artifact "missing-artifact" not found' in result.stderr

    def test_no_output_to_stdout_for_unknown_id(self, runner, project_dir):
        result = runner.invoke(main, ["artifact", "show", "missing-artifact"])
        assert result.stdout == ""


class TestArtifactShowMultipleIds:
    """lore artifact show with multiple IDs shows each in order with separators."""

    def test_exit_code_0_for_two_known_ids(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        _write_artifact(project_dir, "full-spec.md", ARTIFACT_B_FOR_MULTI)
        result = runner.invoke(
            main, ["artifact", "show", "show-biz-spec", "show-full-spec"]
        )
        assert result.exit_code == 0

    def test_both_separators_present(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        _write_artifact(project_dir, "full-spec.md", ARTIFACT_B_FOR_MULTI)
        result = runner.invoke(
            main, ["artifact", "show", "show-biz-spec", "show-full-spec"]
        )
        assert "=== show-biz-spec ===" in result.output
        assert "=== show-full-spec ===" in result.output

    def test_first_id_separator_appears_before_second(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        _write_artifact(project_dir, "full-spec.md", ARTIFACT_B_FOR_MULTI)
        result = runner.invoke(
            main, ["artifact", "show", "show-full-spec", "show-biz-spec"]
        )
        full_idx = result.output.index("=== show-full-spec ===")
        biz_idx = result.output.index("=== show-biz-spec ===")
        assert full_idx < biz_idx


class TestArtifactShowFailFast:
    """lore artifact show fails fast on first missing ID — no stdout emitted."""

    def test_exit_code_1_when_second_id_missing(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        result = runner.invoke(
            main, ["artifact", "show", "show-biz-spec", "nonexistent-id"]
        )
        assert result.exit_code == 1

    def test_no_stdout_when_any_id_missing(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        result = runner.invoke(
            main, ["artifact", "show", "show-biz-spec", "nonexistent-id"]
        )
        assert result.exit_code == 1
        assert result.stdout == ""

    def test_error_to_stderr_for_missing_id(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        result = runner.invoke(
            main, ["artifact", "show", "show-biz-spec", "nonexistent-id"]
        )
        assert "nonexistent-id" in result.stderr

    def test_error_message_format_for_missing_id(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        result = runner.invoke(
            main, ["artifact", "show", "show-biz-spec", "nonexistent-id"]
        )
        assert 'Artifact "nonexistent-id" not found' in result.stderr

    def test_no_stdout_when_first_id_missing(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        result = runner.invoke(
            main, ["artifact", "show", "nonexistent-id", "show-biz-spec"]
        )
        assert result.exit_code == 1
        assert result.stdout == ""


# ---------------------------------------------------------------------------
# Integration tests: lore artifact show --json
# ---------------------------------------------------------------------------


class TestArtifactShowJsonOutput:
    """lore artifact show --json emits valid JSON with correct schema."""

    def test_exit_code_0_for_known_id_with_json_flag(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        result = runner.invoke(main, ["--json", "artifact", "show", "show-biz-spec"])
        assert result.exit_code == 0

    def test_json_output_is_valid_json(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        result = runner.invoke(main, ["--json", "artifact", "show", "show-biz-spec"])
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_json_output_has_artifacts_key(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        result = runner.invoke(main, ["--json", "artifact", "show", "show-biz-spec"])
        data = json.loads(result.output)
        assert "artifacts" in data

    def test_json_artifacts_is_a_list(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        result = runner.invoke(main, ["--json", "artifact", "show", "show-biz-spec"])
        data = json.loads(result.output)
        assert isinstance(data["artifacts"], list)

    def test_json_artifacts_has_one_entry_for_single_id(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        result = runner.invoke(main, ["--json", "artifact", "show", "show-biz-spec"])
        data = json.loads(result.output)
        assert len(data["artifacts"]) == 1

    def test_json_artifact_has_id_field(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        result = runner.invoke(main, ["--json", "artifact", "show", "show-biz-spec"])
        data = json.loads(result.output)
        assert data["artifacts"][0]["id"] == "show-biz-spec"

    def test_json_artifact_has_title_field(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        result = runner.invoke(main, ["--json", "artifact", "show", "show-biz-spec"])
        data = json.loads(result.output)
        assert data["artifacts"][0]["title"] == "Business Spec Template"

    def test_json_artifact_has_summary_field(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        result = runner.invoke(main, ["--json", "artifact", "show", "show-biz-spec"])
        data = json.loads(result.output)
        assert (
            data["artifacts"][0]["summary"] == "Template for writing a business spec."
        )

    def test_json_artifact_has_body_field(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        result = runner.invoke(main, ["--json", "artifact", "show", "show-biz-spec"])
        data = json.loads(result.output)
        assert "body" in data["artifacts"][0]

    def test_json_body_contains_template_content(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        result = runner.invoke(main, ["--json", "artifact", "show", "show-biz-spec"])
        data = json.loads(result.output)
        assert "# Business Spec Template" in data["artifacts"][0]["body"]

    def test_json_body_does_not_contain_frontmatter(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        result = runner.invoke(main, ["--json", "artifact", "show", "show-biz-spec"])
        data = json.loads(result.output)
        body = data["artifacts"][0]["body"]
        assert "id: show-biz-spec" not in body
        assert "title: Business Spec Template" not in body

    def test_json_multi_id_returns_two_entries(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        _write_artifact(project_dir, "full-spec.md", ARTIFACT_B_FOR_MULTI)
        result = runner.invoke(
            main,
            ["--json", "artifact", "show", "show-biz-spec", "show-full-spec"],
        )
        data = json.loads(result.output)
        assert len(data["artifacts"]) == 2

    def test_json_multi_id_entries_have_correct_ids(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        _write_artifact(project_dir, "full-spec.md", ARTIFACT_B_FOR_MULTI)
        result = runner.invoke(
            main,
            ["--json", "artifact", "show", "show-biz-spec", "show-full-spec"],
        )
        data = json.loads(result.output)
        ids = [a["id"] for a in data["artifacts"]]
        assert "show-biz-spec" in ids
        assert "show-full-spec" in ids


class TestArtifactShowJsonUnknownId:
    """lore artifact show --json exits 1 with JSON error on stderr for unknown ID."""

    def test_exit_code_1_for_unknown_id_with_json_flag(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "artifact", "show", "no-such-artifact"])
        assert result.exit_code == 1

    def test_json_error_written_to_stderr(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "artifact", "show", "no-such-artifact"])
        assert result.exit_code == 1
        assert result.stderr.strip() != ""

    def test_json_error_is_valid_json(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "artifact", "show", "no-such-artifact"])
        data = json.loads(result.stderr)
        assert isinstance(data, dict)

    def test_json_error_has_error_key(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "artifact", "show", "no-such-artifact"])
        data = json.loads(result.stderr)
        assert "error" in data

    def test_json_error_message_names_the_missing_id(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "artifact", "show", "missing-artifact"])
        data = json.loads(result.stderr)
        assert "missing-artifact" in data["error"]

    def test_json_error_message_format(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "artifact", "show", "missing-artifact"])
        data = json.loads(result.stderr)
        assert data["error"] == 'Artifact "missing-artifact" not found'

    def test_no_output_to_stdout_for_unknown_id_with_json_flag(
        self, runner, project_dir
    ):
        result = runner.invoke(main, ["--json", "artifact", "show", "missing-artifact"])
        assert result.exit_code == 1
        assert result.stdout == ""


class TestArtifactShowVariadicApi:
    """lore artifact show uses nargs=-1 (variadic) — tests for single-ID path."""

    def test_single_id_works_as_positional_arg(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        result = runner.invoke(main, ["artifact", "show", "show-biz-spec"])
        assert result.exit_code == 0

    def test_single_id_produces_separator(self, runner, project_dir):
        _write_artifact(project_dir, "biz-spec.md", ARTIFACT_WITH_BODY)
        result = runner.invoke(main, ["artifact", "show", "show-biz-spec"])
        assert "=== show-biz-spec ===" in result.output

    def test_no_id_given_exits_with_code_2(self, runner, project_dir):
        result = runner.invoke(main, ["artifact", "show"])
        assert result.exit_code == 2
        assert "No such command" not in result.output


# ---------------------------------------------------------------------------
# JSON flag position consistency
# ---------------------------------------------------------------------------


class TestArtifactJsonConsistency:
    """JSON output is identical regardless of flag position; edge-cases are handled correctly."""

    def test_global_json_flag_and_subcommand_json_flag_produce_identical_list_output(
        self, runner, bare_project_dir
    ):
        _write_artifact(bare_project_dir, "biz-spec.md", VALID_ARTIFACT)
        global_flag_result = runner.invoke(main, ["--json", "artifact", "list"])
        subcommand_flag_result = runner.invoke(main, ["artifact", "list", "--json"])
        assert global_flag_result.exit_code == 0
        assert subcommand_flag_result.exit_code == 0
        assert global_flag_result.output == subcommand_flag_result.output

    def test_artifact_show_with_json_flag_and_no_id_exits_with_code_2(
        self, runner, project_dir
    ):
        result = runner.invoke(main, ["artifact", "show", "--json"])
        assert result.exit_code == 2

    def test_artifact_show_with_global_json_flag_and_no_id_exits_with_code_2(
        self, runner, project_dir
    ):
        result = runner.invoke(main, ["--json", "artifact", "show"])
        assert result.exit_code == 2

    def test_list_json_elements_do_not_contain_body_field(
        self, runner, bare_project_dir
    ):
        _write_artifact(bare_project_dir, "biz-spec.md", VALID_ARTIFACT)
        result = runner.invoke(main, ["artifact", "list", "--json"])
        data = json.loads(result.output)
        assert len(data["artifacts"]) > 0
        for element in data["artifacts"]:
            assert "body" not in element

    def test_show_json_elements_contain_body_field_but_list_json_elements_do_not(
        self, runner, project_dir
    ):
        list_result = runner.invoke(main, ["artifact", "list", "--json"])
        show_result = runner.invoke(
            main, ["--json", "artifact", "show", "example-codex"]
        )
        list_data = json.loads(list_result.output)
        show_data = json.loads(show_result.output)
        assert "body" not in list_data["artifacts"][0]
        assert "body" in show_data["artifacts"][0]


# ---------------------------------------------------------------------------
# AC1: GROUP column appears between TYPE and TITLE in the header
# ---------------------------------------------------------------------------


class TestArtifactListHeaderContainsGroupColumns:
    """AC1: The artifact list header must include GROUP column."""

    def test_artifact_list_header_contains_group_column(self, runner, project_dir):
        result = runner.invoke(main, ["artifact", "list"])
        assert result.exit_code == 0, result.output
        non_empty_lines = [l for l in result.output.split("\n") if l.strip()]
        assert len(non_empty_lines) >= 1
        header = non_empty_lines[0]
        assert "GROUP" in header

    def test_artifact_list_header_has_four_columns(self, runner, project_dir):
        result = runner.invoke(main, ["artifact", "list"])
        assert result.exit_code == 0, result.output
        non_empty_lines = [l for l in result.output.split("\n") if l.strip()]
        header = non_empty_lines[0]
        for col in ("ID", "GROUP", "TITLE", "SUMMARY"):
            assert col in header

    def test_artifact_list_columns_appear_in_order_id_group_title_summary(
        self, runner, project_dir
    ):
        result = runner.invoke(main, ["artifact", "list"])
        assert result.exit_code == 0, result.output
        non_empty_lines = [l for l in result.output.split("\n") if l.strip()]
        header = non_empty_lines[0]
        id_pos = header.index("ID")
        group_pos = header.index("GROUP")
        title_pos = header.index("TITLE")
        summary_pos = header.index("SUMMARY")
        assert id_pos < group_pos < title_pos < summary_pos

    def test_group_column_appears_before_title(self, runner, project_dir):
        result = runner.invoke(main, ["artifact", "list"])
        assert result.exit_code == 0, result.output
        non_empty_lines = [l for l in result.output.split("\n") if l.strip()]
        header = non_empty_lines[0]
        group_pos = header.index("GROUP")
        title_pos = header.index("TITLE")
        assert group_pos < title_pos


class TestArtifactListDataRowsIncludeGroup:
    """AC1: Each artifact data row must include the group value in the GROUP column."""

    def test_artifact_id_value_appears_in_output(self, runner, project_dir):
        artifacts_dir = project_dir / ".lore" / "artifacts"
        shutil.rmtree(artifacts_dir)
        artifacts_dir.mkdir(parents=True)
        _write_artifact(project_dir, "alpha.md", ARTIFACT_ALPHA)

        result = runner.invoke(main, ["artifact", "list"])
        assert result.exit_code == 0, result.output
        assert "alpha-artifact" in result.output

    def test_format_table_called_with_four_column_headers_for_artifact_list(
        self, runner, project_dir
    ):
        artifacts_dir = project_dir / ".lore" / "artifacts"
        shutil.rmtree(artifacts_dir)
        artifacts_dir.mkdir(parents=True)
        _write_artifact(project_dir, "alpha.md", ARTIFACT_ALPHA)

        result = runner.invoke(main, ["artifact", "list"])
        assert result.exit_code == 0, result.output

        expected_lines = _format_table(
            ["ID", "GROUP", "TITLE", "SUMMARY"],
            [["alpha-artifact", "", "Alpha Artifact", "The first artifact alphabetically."]],
        )
        expected_output = "\n".join(expected_lines) + "\n"
        assert result.output == expected_output


# ---------------------------------------------------------------------------
# AC2: group value in table matches derivation
# ---------------------------------------------------------------------------


class TestArtifactListGroupValuesInTableMatchDerivation:
    """AC2: The table GROUP column values match derive_group() for nested artifacts."""

    def test_nested_artifact_group_in_table_matches_subdirectory_name(
        self, runner, project_dir
    ):
        artifacts_dir = project_dir / ".lore" / "artifacts"
        shutil.rmtree(artifacts_dir)
        artifacts_dir.mkdir(parents=True)
        sub = artifacts_dir / "codex"
        sub.mkdir()
        _write_artifact(project_dir, "codex/nested.md", NESTED_ARTIFACT)

        result = runner.invoke(main, ["artifact", "list"])
        assert result.exit_code == 0, result.output
        non_empty_lines = [l for l in result.output.split("\n") if l.strip()]
        header = non_empty_lines[0]
        assert "GROUP" in header
        assert "codex" in result.output

    def test_two_level_nested_artifact_group_in_table_uses_dash_separator(
        self, runner, project_dir
    ):
        artifacts_dir = project_dir / ".lore" / "artifacts"
        shutil.rmtree(artifacts_dir)
        artifacts_dir.mkdir(parents=True)
        sub = artifacts_dir / "codex" / "specs"
        sub.mkdir(parents=True)
        _write_artifact(project_dir, "codex/specs/nested.md", NESTED_ARTIFACT)

        result = runner.invoke(main, ["artifact", "list"])
        assert result.exit_code == 0, result.output
        non_empty_lines = [l for l in result.output.split("\n") if l.strip()]
        header = non_empty_lines[0]
        assert "GROUP" in header
        assert "codex-specs" in result.output

    def test_group_column_in_table_shows_correct_value_for_nested_artifact(
        self, runner, project_dir
    ):
        artifacts_dir = project_dir / ".lore" / "artifacts"
        shutil.rmtree(artifacts_dir)
        artifacts_dir.mkdir(parents=True)
        sub = artifacts_dir / "workflow"
        sub.mkdir()
        _write_artifact(project_dir, "workflow/nested.md", NESTED_ARTIFACT)

        result = runner.invoke(main, ["artifact", "list"])
        assert result.exit_code == 0, result.output

        expected_lines = _format_table(
            ["ID", "GROUP", "TITLE", "SUMMARY"],
            [["nested-one", "workflow", "Nested One", "Lives inside a subdirectory."]],
        )
        expected_output = "\n".join(expected_lines) + "\n"
        assert result.output == expected_output


# ---------------------------------------------------------------------------
# AC3: Root-level artifacts show empty group
# ---------------------------------------------------------------------------


class TestArtifactListRootLevelArtifactsShowEmptyGroup:
    """AC3: Artifacts at the top level of the artifacts directory show an empty group."""

    def test_root_level_artifact_shows_empty_group_in_table_output(
        self, runner, project_dir
    ):
        artifacts_dir = project_dir / ".lore" / "artifacts"
        shutil.rmtree(artifacts_dir)
        artifacts_dir.mkdir(parents=True)
        _write_artifact(project_dir, "root.md", ROOT_LEVEL_ARTIFACT)

        result = runner.invoke(main, ["artifact", "list"])
        assert result.exit_code == 0, result.output

        expected_lines = _format_table(
            ["ID", "GROUP", "TITLE", "SUMMARY"],
            [["root-level", "", "Root Level Artifact", "Sits at the top level with no subdirectory."]],
        )
        expected_output = "\n".join(expected_lines) + "\n"
        assert result.output == expected_output

    def test_root_and_nested_table_groups_differ(self, runner, project_dir):
        artifacts_dir = project_dir / ".lore" / "artifacts"
        shutil.rmtree(artifacts_dir)
        artifacts_dir.mkdir(parents=True)
        _write_artifact(project_dir, "root.md", ROOT_LEVEL_ARTIFACT)
        sub = artifacts_dir / "subdir"
        sub.mkdir()
        _write_artifact(project_dir, "subdir/nested.md", NESTED_ARTIFACT)

        result = runner.invoke(main, ["artifact", "list"])
        assert result.exit_code == 0, result.output

        expected_lines = _format_table(
            ["ID", "GROUP", "TITLE", "SUMMARY"],
            [
                ["nested-one", "subdir", "Nested One", "Lives inside a subdirectory."],
                ["root-level", "", "Root Level Artifact", "Sits at the top level with no subdirectory."],
            ],
        )
        expected_output = "\n".join(expected_lines) + "\n"
        assert result.output == expected_output


# ---------------------------------------------------------------------------
# AC4: Table alignment with five columns
# ---------------------------------------------------------------------------


class TestArtifactListTableAlignmentWithFourColumns:
    """AC4: The table remains aligned with ID, GROUP, TITLE, SUMMARY columns."""

    def test_artifact_list_output_matches_four_column_format_table_exactly(
        self, runner, project_dir
    ):
        artifacts_dir = project_dir / ".lore" / "artifacts"
        shutil.rmtree(artifacts_dir)
        artifacts_dir.mkdir(parents=True)
        _write_artifact(project_dir, "alpha.md", ARTIFACT_ALPHA)
        _write_artifact(project_dir, "bravo.md", ARTIFACT_BRAVO)

        result = runner.invoke(main, ["artifact", "list"])
        assert result.exit_code == 0, result.output

        expected_lines = _format_table(
            ["ID", "GROUP", "TITLE", "SUMMARY"],
            [
                ["alpha-artifact", "", "Alpha Artifact", "The first artifact alphabetically."],
                ["bravo-artifact", "", "Bravo Artifact", "The second artifact alphabetically."],
            ],
        )
        expected_output = "\n".join(expected_lines) + "\n"
        assert result.output == expected_output


# ---------------------------------------------------------------------------
# Sort order: artifact list must be A-to-Z
# ---------------------------------------------------------------------------


class TestArtifactListSortOrderIsAscending:
    """artifact list table must display artifacts in A-to-Z order."""

    def test_artifact_list_table_first_row_is_alphabetically_first_artifact(
        self, runner, project_dir
    ):
        artifacts_dir = project_dir / ".lore" / "artifacts"
        shutil.rmtree(artifacts_dir)
        artifacts_dir.mkdir(parents=True)
        _write_artifact(project_dir, "alpha.md", ARTIFACT_ALPHA)
        _write_artifact(project_dir, "bravo.md", ARTIFACT_BRAVO)

        result = runner.invoke(main, ["artifact", "list"])
        assert result.exit_code == 0, result.output

        non_empty_lines = [l for l in result.output.split("\n") if l.strip()]
        assert len(non_empty_lines) >= 3
        first_data_row = non_empty_lines[1]
        assert "alpha-artifact" in first_data_row

    def test_artifact_list_table_ids_are_in_ascending_order(
        self, runner, project_dir
    ):
        artifacts_dir = project_dir / ".lore" / "artifacts"
        shutil.rmtree(artifacts_dir)
        artifacts_dir.mkdir(parents=True)
        _write_artifact(project_dir, "alpha.md", ARTIFACT_ALPHA)
        _write_artifact(project_dir, "bravo.md", ARTIFACT_BRAVO)

        result = runner.invoke(main, ["artifact", "list"])
        assert result.exit_code == 0, result.output

        non_empty_lines = [l for l in result.output.split("\n") if l.strip()]
        data_rows = non_empty_lines[1:]
        ids_in_table = [row.strip().split()[0] for row in data_rows]
        assert ids_in_table == sorted(ids_in_table)

    def test_artifact_list_table_order_matches_json_order(
        self, runner, project_dir
    ):
        artifacts_dir = project_dir / ".lore" / "artifacts"
        shutil.rmtree(artifacts_dir)
        artifacts_dir.mkdir(parents=True)
        _write_artifact(project_dir, "alpha.md", ARTIFACT_ALPHA)
        _write_artifact(project_dir, "bravo.md", ARTIFACT_BRAVO)

        result_table = runner.invoke(main, ["artifact", "list"])
        result_json = runner.invoke(main, ["--json", "artifact", "list"])

        assert result_table.exit_code == 0
        assert result_json.exit_code == 0

        non_empty_lines = [l for l in result_table.output.split("\n") if l.strip()]
        table_ids = [row.strip().split()[0] for row in non_empty_lines[1:]]

        data = json.loads(result_json.output)
        json_ids = [a["id"] for a in data["artifacts"]]
        assert table_ids == json_ids


# ---------------------------------------------------------------------------
# JSON key order for artifact list
# ---------------------------------------------------------------------------


class TestArtifactListJsonGroupKeyPresentInSpecOrder:
    """Each artifact record must include 'group' in the spec-defined position."""

    def test_record_keys_match_spec_defined_order(
        self, runner, bare_project_dir
    ):
        artifacts_dir = bare_project_dir / ".lore" / "artifacts"
        _write_artifact(bare_project_dir, "root.md", ARTIFACT_ROOT)

        result = runner.invoke(main, ["artifact", "list", "--json"])
        assert result.exit_code == 0, result.output
        parsed = json.loads(result.output)
        record = parsed["artifacts"][0]
        actual_keys = list(record.keys())
        assert actual_keys == SPEC_KEY_ORDER

    def test_root_artifact_has_empty_group_in_spec_position(
        self, runner, bare_project_dir
    ):
        artifacts_dir = bare_project_dir / ".lore" / "artifacts"
        _write_artifact(bare_project_dir, "root.md", ARTIFACT_ROOT)

        result = runner.invoke(main, ["artifact", "list", "--json"])
        assert result.exit_code == 0, result.output
        parsed = json.loads(result.output)
        record = next(r for r in parsed["artifacts"] if r["id"] == "root-artifact")
        assert record["group"] == ""
        keys = list(record.keys())
        assert keys == SPEC_KEY_ORDER

    def test_subdirectory_artifact_has_folder_group_in_spec_position(
        self, runner, bare_project_dir
    ):
        artifacts_dir = bare_project_dir / ".lore" / "artifacts"
        _write_artifact(bare_project_dir, "my-team/sub.md", ARTIFACT_IN_SUBDIR)

        result = runner.invoke(main, ["artifact", "list", "--json"])
        assert result.exit_code == 0, result.output
        parsed = json.loads(result.output)
        record = next(r for r in parsed["artifacts"] if r["id"] == "sub-artifact")
        assert record["group"] == "my-team"
        keys = list(record.keys())
        assert keys == SPEC_KEY_ORDER

    def test_deep_nested_artifact_has_dash_group_in_spec_position(
        self, runner, bare_project_dir
    ):
        artifacts_dir = bare_project_dir / ".lore" / "artifacts"
        _write_artifact(bare_project_dir, "alpha/beta/deep.md", ARTIFACT_IN_DEEP_SUBDIR)

        result = runner.invoke(main, ["artifact", "list", "--json"])
        assert result.exit_code == 0, result.output
        parsed = json.loads(result.output)
        record = next(r for r in parsed["artifacts"] if r["id"] == "deep-artifact")
        assert record["group"] == "alpha-beta"
        keys = list(record.keys())
        assert keys == SPEC_KEY_ORDER


# ---------------------------------------------------------------------------
# Default artifacts have complete metadata
# ---------------------------------------------------------------------------


class TestDefaultArtifactMetadata:
    """After lore init, default artifacts have complete id, title, summary, group fields."""

    @pytest.fixture(scope="class")
    def artifact_records(self):
        return scan_artifacts(_DEFAULTS_ARTIFACTS_DIR)

    def test_scan_artifacts_returns_expected_count_of_templates(
        self, artifact_records
    ):
        assert len(artifact_records) == _EXPECTED_ARTIFACT_COUNT

    def test_each_artifact_record_has_group_key(self, artifact_records):
        records_missing_group = [
            r["id"] for r in artifact_records if "group" not in r
        ]
        assert not records_missing_group

    def test_scan_artifacts_excludes_readme_files(self, artifact_records):
        for readme in _README_FILES:
            readme_in_results = any(
                r.get("path") == readme for r in artifact_records
            )
            assert not readme_in_results

    @pytest.mark.parametrize(
        "artifact_file",
        _TEMPLATE_FILES,
        ids=lambda f: str(f.relative_to(_DEFAULTS_ARTIFACTS_DIR)),
    )
    def test_template_file_is_returned_by_scan_artifacts(
        self, artifact_file, artifact_records
    ):
        returned_paths = {r["path"] for r in artifact_records}
        assert artifact_file in returned_paths

    def test_default_artifacts_visible_in_json(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "artifact", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["artifacts"]) >= _EXPECTED_ARTIFACT_COUNT

    def test_artifact_list_json_contains_group_key_for_every_artifact(
        self, runner, project_dir
    ):
        result = runner.invoke(main, ["--json", "artifact", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        records_missing_group = [
            r.get("id", "<no id>")
            for r in data["artifacts"]
            if "group" not in r
        ]
        assert not records_missing_group


# ---------------------------------------------------------------------------
# _format_table unit tests
# ---------------------------------------------------------------------------


class TestFormatTableColumnPadding:
    """_format_table pads columns to the widest value in each column."""

    def test_id_column_padded_to_widest_value(self):
        lines = _format_table(
            ["ID", "TITLE"],
            [["a", "Long Title"], ["abc", "X"]],
        )
        assert len(lines) == 3
        row_short_id = lines[1]
        assert row_short_id[:7] == "  a    "

    def test_spec_example_id_padded_to_three_title_not_padded(self):
        lines = _format_table(
            ["ID", "TITLE"],
            [["a", "Long Title"], ["abc", "X"]],
        )
        header = lines[0]
        assert header.startswith("  ")
        assert "ID " in header
        assert header.rstrip() == header

    def test_exact_spec_example_from_tech_notes(self):
        lines = _format_table(
            ["ID", "GROUP", "TITLE", "SUMMARY"],
            [["pm", "default", "Product Manager", "Writes PRDs"]],
        )
        assert lines[0] == "  ID  GROUP    TITLE            SUMMARY"
        assert lines[1] == "  pm  default  Product Manager  Writes PRDs"

    def test_every_line_starts_with_two_space_indent(self):
        lines = _format_table(
            ["ID", "TITLE"],
            [["a1", "Alpha"], ["b2", "Beta"]],
        )
        for line in lines:
            assert line[:2] == "  "
            assert line[2] != " "

    def test_columns_separated_by_two_spaces(self):
        lines = _format_table(
            ["ID", "TITLE"],
            [["ab", "My Title"]],
        )
        data_row = lines[1]
        assert data_row == "  ab  My Title"

    def test_returns_list_of_strings(self):
        result = _format_table(
            ["ID", "TITLE"],
            [["x", "y"]],
        )
        assert isinstance(result, list)
        assert all(isinstance(line, str) for line in result)

    def test_returns_header_plus_one_line_per_row(self):
        rows = [["a", "b"], ["c", "d"], ["e", "f"]]
        lines = _format_table(["ID", "TITLE"], rows)
        assert len(lines) == 4

    def test_empty_rows_returns_only_header(self):
        lines = _format_table(["ID", "TITLE", "SUMMARY"], [])
        assert len(lines) == 1
        header = lines[0]
        assert header.startswith("  ")
        assert "ID" in header

    def test_data_row_last_column_not_padded(self):
        lines = _format_table(
            ["ID", "TITLE", "SUMMARY"],
            [["ab", "A Title", "Short summary"],
             ["cd", "Another Title", "A much much longer summary"]],
        )
        row1 = lines[1]
        assert row1.endswith("Short summary")
        assert not row1.endswith("Short summary ")

    def test_all_three_list_commands_use_consistent_two_space_indent(
        self, runner, project_dir
    ):
        for cmd in [["knight", "list"], ["doctrine", "list"], ["artifact", "list"]]:
            result = runner.invoke(main, cmd)
            assert result.exit_code == 0
            non_empty_lines = [l for l in result.output.split("\n") if l.strip()]
            if non_empty_lines:
                header = non_empty_lines[0]
                assert header.startswith("  ")


# ---------------------------------------------------------------------------
# Missing metadata fallback behaviour
# ---------------------------------------------------------------------------


class TestMissingMetadataFallbackKnight:
    """Knight files missing metadata fields fall back gracefully."""

    def test_knight_missing_id_field_uses_filename_stem_as_id(self, tmp_path):
        knights_dir = tmp_path / "knights"
        knights_dir.mkdir()
        (knights_dir / "my-knight.md").write_text(
            "---\ntitle: My Knight\nsummary: Does knight things\n---\n\n# My Knight\n"
        )
        records = list_knights(knights_dir)
        assert len(records) == 1
        assert records[0]["id"] == "my-knight"

    def test_knight_with_no_frontmatter_uses_filename_stem_as_id(self, tmp_path):
        knights_dir = tmp_path / "knights"
        knights_dir.mkdir()
        (knights_dir / "bare-knight.md").write_text("# Bare Knight\n")
        records = list_knights(knights_dir)
        assert len(records) == 1
        assert records[0]["id"] == "bare-knight"

    def test_knight_missing_title_uses_id_as_title(self, tmp_path):
        knights_dir = tmp_path / "knights"
        knights_dir.mkdir()
        (knights_dir / "silent-knight.md").write_text(
            "---\nid: silent-knight\nsummary: Stays quiet\n---\n\n# Content\n"
        )
        records = list_knights(knights_dir)
        assert len(records) == 1
        assert records[0]["title"] == "silent-knight"

    def test_knight_missing_summary_has_empty_string_summary(self, tmp_path):
        knights_dir = tmp_path / "knights"
        knights_dir.mkdir()
        (knights_dir / "brief-knight.md").write_text(
            "---\nid: brief-knight\ntitle: Brief Knight\n---\n\n# Brief Knight\n"
        )
        records = list_knights(knights_dir)
        assert len(records) == 1
        assert records[0]["summary"] == ""

    def test_list_knights_does_not_crash_with_malformed_yaml_frontmatter(
        self, tmp_path
    ):
        knights_dir = tmp_path / "knights"
        knights_dir.mkdir()
        (knights_dir / "malformed.md").write_text("---\n: invalid yaml\n---\n\n# Content\n")
        records = list_knights(knights_dir)
        assert len(records) == 1
        record = records[0]
        assert "id" in record
        assert "group" in record
        assert "title" in record
        assert "summary" in record

    def test_list_knights_malformed_yaml_returns_stem_based_fallback(self, tmp_path):
        knights_dir = tmp_path / "knights"
        knights_dir.mkdir()
        (knights_dir / "malformed-knight.md").write_text("---\n: invalid yaml\n---\n\n# Content\n")
        records = list_knights(knights_dir)
        assert len(records) == 1
        record = records[0]
        assert record["id"] == "malformed-knight"
        assert record["title"] == "malformed-knight"
        assert record["summary"] == ""

    def test_cli_knight_list_does_not_crash_with_malformed_knight_files(
        self, runner, project_dir
    ):
        knights_dir = project_dir / ".lore" / "knights"
        knights_dir.mkdir(exist_ok=True)
        (knights_dir / "broken.md").write_text("---\n: invalid yaml\n---\n")
        result = runner.invoke(main, ["knight", "list"])
        assert result.exit_code == 0
        assert "broken.md" not in result.output

    def test_cli_knight_list_shows_malformed_knight_in_output(
        self, runner, project_dir
    ):
        knights_dir = project_dir / ".lore" / "knights"
        knights_dir.mkdir(exist_ok=True)
        (knights_dir / "broken-visible.md").write_text("---\n: invalid yaml\n---\n")
        result = runner.invoke(main, ["knight", "list"])
        assert "broken-visible" in result.output
        assert "broken-visible.md" not in result.output


class TestMissingMetadataFallbackDoctrine:
    """Doctrine files missing metadata fields fall back gracefully."""

    def test_doctrine_missing_id_field_uses_filename_stem_as_id(self, tmp_path):
        doctrines_dir = tmp_path / "doctrines"
        doctrines_dir.mkdir()
        (doctrines_dir / "my-workflow.yaml").write_text(
            "name: my-workflow\ntitle: My Workflow\nsummary: A workflow\n"
            "description: Does workflow things.\nsteps:\n  - id: step-1\n    title: Step One\n"
        )
        records = list_doctrines(doctrines_dir)
        assert len(records) == 1
        assert records[0]["id"] == "my-workflow"

    def test_doctrine_missing_title_uses_id_as_title(self, tmp_path):
        doctrines_dir = tmp_path / "doctrines"
        doctrines_dir.mkdir()
        (doctrines_dir / "no-title-doc.yaml").write_text(
            "name: no-title-doc\nid: no-title-doc\nsummary: A workflow\n"
            "description: Short description.\nsteps:\n  - id: step-1\n    title: Step One\n"
        )
        records = list_doctrines(doctrines_dir)
        assert len(records) == 1
        assert records[0]["title"] == "no-title-doc"

    def test_doctrine_missing_summary_and_description_has_empty_string_summary(
        self, tmp_path
    ):
        doctrines_dir = tmp_path / "doctrines"
        doctrines_dir.mkdir()
        (doctrines_dir / "no-summary.yaml").write_text(
            "name: no-summary\nid: no-summary\ntitle: No Summary Doctrine\n"
            "steps:\n  - id: step-1\n    title: Step One\n"
        )
        records = list_doctrines(doctrines_dir)
        assert len(records) == 1
        assert records[0]["summary"] == ""
        assert isinstance(records[0]["summary"], str)

    def test_long_description_is_used_as_summary_when_summary_missing(self, tmp_path):
        doctrines_dir = tmp_path / "doctrines"
        doctrines_dir.mkdir()
        long_desc = (
            "This is a very long description that goes well beyond eighty characters "
            "and should be truncated at a word boundary"
        )
        (doctrines_dir / "long-desc.yaml").write_text(
            f"name: long-desc\nid: long-desc\ntitle: Long Description Doctrine\n"
            f"description: {long_desc!r}\nsteps:\n  - id: step-1\n    title: Step One\n"
        )
        records = list_doctrines(doctrines_dir)
        assert len(records) == 1
        summary = records[0]["summary"]
        assert summary.endswith("...")

    def test_short_description_is_used_whole_without_ellipsis(self, tmp_path):
        doctrines_dir = tmp_path / "doctrines"
        doctrines_dir.mkdir()
        short_desc = "Short description."
        (doctrines_dir / "short-desc.yaml").write_text(
            f"name: short-desc\nid: short-desc\ntitle: Short Desc\n"
            f"description: {short_desc!r}\nsteps:\n  - id: step-1\n    title: Step One\n"
        )
        records = list_doctrines(doctrines_dir)
        assert len(records) == 1
        assert records[0]["summary"] == short_desc

    def test_summary_field_takes_precedence_over_description(self, tmp_path):
        doctrines_dir = tmp_path / "doctrines"
        doctrines_dir.mkdir()
        (doctrines_dir / "has-both.yaml").write_text(
            "name: has-both\nid: has-both\ntitle: Has Both\n"
            "summary: This is the explicit summary.\n"
            "description: This is a long description that would otherwise be used.\n"
            "steps:\n  - id: step-1\n    title: Step One\n"
        )
        records = list_doctrines(doctrines_dir)
        assert len(records) == 1
        assert records[0]["summary"] == "This is the explicit summary."

    def test_list_doctrines_does_not_crash_with_empty_yaml_file(self, tmp_path):
        doctrines_dir = tmp_path / "doctrines"
        doctrines_dir.mkdir()
        (doctrines_dir / "empty.yaml").write_text("")
        records = list_doctrines(doctrines_dir)
        assert len(records) == 1
        record = records[0]
        assert "id" in record
        assert "group" in record
        assert "title" in record
        assert "summary" in record

    def test_list_doctrines_record_has_valid_key_and_new_fields_together(self, tmp_path):
        doctrines_dir = tmp_path / "doctrines"
        doctrines_dir.mkdir()
        (doctrines_dir / "my-doctrine.yaml").write_text(
            "name: my-doctrine\ndescription: X.\nsteps:\n  - id: s\n    title: S\n"
        )
        records = list_doctrines(doctrines_dir)
        assert "valid" in records[0]
        assert "id" in records[0]
        assert "group" in records[0]
        assert "title" in records[0]
        assert "summary" in records[0]


class TestMissingMetadataFallbackReturnShape:
    """list_knights() and list_doctrines() emit required field shapes."""

    def test_list_knights_record_has_id_key(self, tmp_path):
        knights_dir = tmp_path / "knights"
        knights_dir.mkdir()
        (knights_dir / "tester.md").write_text("# Tester\n")
        records = list_knights(knights_dir)
        assert "id" in records[0]

    def test_list_knights_record_has_group_key(self, tmp_path):
        knights_dir = tmp_path / "knights"
        knights_dir.mkdir()
        (knights_dir / "tester.md").write_text("# Tester\n")
        records = list_knights(knights_dir)
        assert "group" in records[0]

    def test_list_knights_record_has_title_key(self, tmp_path):
        knights_dir = tmp_path / "knights"
        knights_dir.mkdir()
        (knights_dir / "tester.md").write_text("# Tester\n")
        records = list_knights(knights_dir)
        assert "title" in records[0]

    def test_list_knights_record_has_summary_key(self, tmp_path):
        knights_dir = tmp_path / "knights"
        knights_dir.mkdir()
        (knights_dir / "tester.md").write_text("# Tester\n")
        records = list_knights(knights_dir)
        assert "summary" in records[0]

    def test_list_knights_sorted_by_id(self, tmp_path):
        knights_dir = tmp_path / "knights"
        knights_dir.mkdir()
        (knights_dir / "zebra.md").write_text("# Zebra\n")
        (knights_dir / "alpha.md").write_text("# Alpha\n")
        (knights_dir / "mango.md").write_text("# Mango\n")
        records = list_knights(knights_dir)
        ids = [r["id"] for r in records]
        assert ids == sorted(ids)

    def test_list_knights_group_is_empty_string_for_root_level_file(self, tmp_path):
        knights_dir = tmp_path / "knights"
        knights_dir.mkdir()
        (knights_dir / "root-knight.md").write_text("# Root\n")
        records = list_knights(knights_dir)
        assert records[0]["group"] == ""

    def test_list_knights_group_is_subdirectory_name_for_nested_file(self, tmp_path):
        knights_dir = tmp_path / "knights"
        subdir = knights_dir / "special"
        subdir.mkdir(parents=True)
        (subdir / "special-knight.md").write_text("# Special\n")
        records = list_knights(knights_dir)
        assert records[0]["group"] == "special"

    def test_list_doctrines_group_is_empty_string_for_root_level_file(self, tmp_path):
        doctrines_dir = tmp_path / "doctrines"
        doctrines_dir.mkdir()
        (doctrines_dir / "root-doc.yaml").write_text(
            "name: root-doc\ndescription: X.\nsteps:\n  - id: s\n    title: S\n"
        )
        records = list_doctrines(doctrines_dir)
        assert records[0]["group"] == ""

    def test_list_doctrines_group_is_subdirectory_name_for_nested_file(self, tmp_path):
        doctrines_dir = tmp_path / "doctrines"
        subdir = doctrines_dir / "workflow"
        subdir.mkdir(parents=True)
        (subdir / "nested-doc.yaml").write_text(
            "name: nested-doc\ndescription: X.\nsteps:\n  - id: s\n    title: S\n"
        )
        records = list_doctrines(doctrines_dir)
        assert records[0]["group"] == "workflow"


# ---------------------------------------------------------------------------
# parse_frontmatter_doc — required_fields parameter
# ---------------------------------------------------------------------------


class TestParseFrontmatterDocRequiredFieldsParameter:
    """parse_frontmatter_doc must accept a required_fields keyword argument."""

    def test_parse_frontmatter_doc_accepts_required_fields_kwarg(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text(
            "---\nid: my-id\ntitle: My Title\nsummary: My summary\n---\n\n# Body\n"
        )
        result = parse_frontmatter_doc(md_file, required_fields=("id", "title", "summary"))
        assert result is not None

    def test_parse_frontmatter_doc_with_three_field_required_fields_returns_id_title_summary(
        self, tmp_path
    ):
        md_file = tmp_path / "knight.md"
        md_file.write_text(
            "---\nid: my-knight\ntitle: My Knight\nsummary: Does things\n---\n\n# Knight\n"
        )
        result = parse_frontmatter_doc(md_file, required_fields=("id", "title", "summary"))
        assert result is not None
        assert result["id"] == "my-knight"
        assert result["title"] == "My Knight"
        assert result["summary"] == "Does things"

    def test_parse_frontmatter_doc_returns_none_when_required_fields_missing(
        self, tmp_path
    ):
        md_file = tmp_path / "missing.md"
        md_file.write_text(
            "---\ntitle: Missing ID Knight\nsummary: Has no id\n---\n\n# Content\n"
        )
        result = parse_frontmatter_doc(md_file, required_fields=("id", "title", "summary"))
        assert result is None

    def test_parse_frontmatter_doc_with_knight_fields_ignores_type_absence(
        self, tmp_path
    ):
        md_file = tmp_path / "no-type-ok.md"
        md_file.write_text(
            "---\nid: no-type-ok\ntitle: Fine Without Type\nsummary: OK\n---\n\n# Body\n"
        )
        result = parse_frontmatter_doc(
            md_file, required_fields=("id", "title", "summary")
        )
        assert result is not None
        assert result["id"] == "no-type-ok"

    def test_parse_frontmatter_doc_returns_only_required_fields_plus_path(
        self, tmp_path
    ):
        md_file = tmp_path / "shaped.md"
        md_file.write_text(
            "---\nid: shaped\ntitle: Shaped\nsummary: Has shape\ntype: knight\n---\n\n# Body\n"
        )
        result = parse_frontmatter_doc(
            md_file, required_fields=("id", "title", "summary")
        )
        assert result is not None
        assert set(result.keys()) == {"id", "title", "summary", "path"}
