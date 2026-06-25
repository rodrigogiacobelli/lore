"""Unit tests for lore.health module.

Workflow: conceptual-workflows-health (lore codex show conceptual-workflows-health)
"""

import dataclasses
import json
import pathlib
import typing
from pathlib import Path

import pytest
from click.testing import CliRunner

import lore.health
from lore.cli import main
from lore.health import (
    _build_artifact_index,
    _build_doctrine_name_index,
    _check_artifacts,
    _check_codex,
    _check_doctrines,
    _check_knights,
    _check_watchers,
    _write_report,
    health_check,
)
from lore.api import HealthIssue, HealthReport


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def lore_dir(tmp_path):
    """Bare .lore/ directory with all required subdirs."""
    lore = tmp_path / ".lore"
    for d in ["knights", "doctrines", "codex", "artifacts", "watchers"]:
        (lore / d).mkdir(parents=True)
    (lore / "codex" / "transient").mkdir(parents=True)
    return tmp_path


# ---------------------------------------------------------------------------
# HealthReport — property tests
# ---------------------------------------------------------------------------


def test_health_report_has_errors_true_when_errors_present():
    """HealthReport.has_errors is True when errors tuple is non-empty."""
    issue = HealthIssue(
        severity="error",
        entity_type="codex",
        id="doc-1",
        check="missing_frontmatter",
        detail="field 'id' absent",
    )
    report = HealthReport(errors=(issue,), warnings=())
    assert report.has_errors is True


def test_health_report_has_errors_false_when_only_warnings():
    """HealthReport.has_errors is False when errors tuple is empty (warnings only)."""
    issue = HealthIssue(
        severity="warning",
        entity_type="codex",
        id="doc-1",
        check="island_node",
        detail="no documents link here",
    )
    report = HealthReport(errors=(), warnings=(issue,))
    assert report.has_errors is False


def test_health_report_has_errors_false_when_clean():
    """HealthReport.has_errors is False on a fully clean report."""
    report = HealthReport(errors=(), warnings=())
    assert report.has_errors is False


def test_health_report_issues_returns_errors_then_warnings():
    """HealthReport.issues returns errors followed by warnings in that order."""
    error = HealthIssue(
        severity="error",
        entity_type="doctrines",
        id="feat-auth",
        check="broken_knight_ref",
        detail="'senior-engineer' not found (step 2)",
    )
    warning = HealthIssue(
        severity="warning",
        entity_type="codex",
        id="proposals-draft",
        check="island_node",
        detail="no documents link here",
    )
    report = HealthReport(errors=(error,), warnings=(warning,))
    assert report.issues == (error, warning)


# ---------------------------------------------------------------------------
# US-005: _check_codex — missing id frontmatter (exact HealthIssue fields)
# Exercises: conceptual-workflows-health
# ---------------------------------------------------------------------------


def test_check_codex_missing_id_issue_fields(tmp_path):
    """_check_codex returns HealthIssue with correct fields when id field absent."""
    # Exercises: lore codex show conceptual-workflows-health
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "orphan.md").write_text("---\ntitle: Orphan\nsummary: Test\n---\nBody.\n")

    issues = _check_codex(codex_dir)

    missing = [i for i in issues if i.check == "missing_frontmatter"]
    assert len(missing) == 1
    issue = missing[0]
    assert issue.severity == "error"
    assert issue.entity_type == "codex"
    assert issue.detail == "field 'id' absent"
    # id must be the relative file path string (relative to codex_dir)
    assert issue.id == "orphan.md"


def test_check_codex_empty_frontmatter_block_reports_missing_frontmatter(tmp_path):
    """_check_codex returns missing_frontmatter error for file with empty frontmatter block."""
    # Exercises: lore codex show conceptual-workflows-health
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "empty-fm.md").write_text("---\n---\nBody.\n")

    issues = _check_codex(codex_dir)

    missing = [i for i in issues if i.check == "missing_frontmatter"]
    assert len(missing) == 1
    assert missing[0].severity == "error"
    assert missing[0].check == "missing_frontmatter"


def test_check_codex_no_frontmatter_at_all_reports_missing_frontmatter(tmp_path):
    """_check_codex returns missing_frontmatter error for file with no frontmatter delimiters."""
    # Exercises: lore codex show conceptual-workflows-health
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "no-fm.md").write_text("Just plain text with no frontmatter.\n")

    issues = _check_codex(codex_dir)

    missing = [i for i in issues if i.check == "missing_frontmatter"]
    assert len(missing) == 1
    assert missing[0].severity == "error"
    assert missing[0].check == "missing_frontmatter"


def test_check_codex_valid_id_no_missing_frontmatter_issues(tmp_path):
    """_check_codex returns no missing_frontmatter issues when all codex files have id."""
    # Exercises: lore codex show conceptual-workflows-health
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "valid-a.md").write_text(
        "---\nid: valid-a\ntitle: Valid A\nsummary: s\nrelated:\n  - valid-b\n---\nBody.\n"
    )
    (codex_dir / "valid-b.md").write_text(
        "---\nid: valid-b\ntitle: Valid B\nsummary: s\nrelated:\n  - valid-a\n---\nBody.\n"
    )

    issues = _check_codex(codex_dir)

    missing = [i for i in issues if i.check == "missing_frontmatter"]
    assert missing == []


def test_check_codex_missing_id_id_field_is_relative_path(tmp_path):
    """_check_codex sets HealthIssue.id to the file path relative to codex_dir."""
    # Exercises: lore codex show conceptual-workflows-health
    codex_dir = tmp_path / ".lore" / "codex"
    subdir = codex_dir / "decisions"
    subdir.mkdir(parents=True)
    (subdir / "orphan.md").write_text("---\ntitle: Orphan\nsummary: Test\n---\nBody.\n")

    issues = _check_codex(codex_dir)

    missing = [i for i in issues if i.check == "missing_frontmatter"]
    assert len(missing) == 1
    # id must be relative path, not absolute
    assert missing[0].id == "decisions/orphan.md"


def test_check_codex_broken_related_link_reports_error(tmp_path):
    """_check_codex reports error when a related link points to a non-existent doc ID."""
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "doc-a.md").write_text(
        "---\nid: doc-a\ntitle: Doc A\nsummary: s\nrelated:\n  - nonexistent-id\n---\nBody.\n"
    )

    issues = _check_codex(codex_dir)

    error_checks = [i.check for i in issues if i.severity == "error"]
    assert "broken_related_link" in error_checks



def test_check_codex_valid_doc_no_issues(tmp_path):
    """_check_codex returns no issues for a valid codex doc that is referenced."""
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "doc-a.md").write_text(
        "---\nid: doc-a\ntitle: Doc A\nsummary: s\nrelated:\n  - doc-b\n---\nBody.\n"
    )
    (codex_dir / "doc-b.md").write_text(
        "---\nid: doc-b\ntitle: Doc B\nsummary: s\nrelated:\n  - doc-a\n---\nBody.\n"
    )

    issues = _check_codex(codex_dir)

    errors = [i for i in issues if i.severity == "error"]
    assert errors == []


# ---------------------------------------------------------------------------
# US-004: _check_codex broken_related_link — exact detail format
# ---------------------------------------------------------------------------


def test_check_codex_broken_related_link_detail_contains_missing_id(tmp_path):
    """_check_codex broken_related_link detail contains the missing ID text."""
    # Exercises: lore codex show conceptual-workflows-health
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "doc-a.md").write_text(
        "---\nid: doc-a\ntitle: Doc A\nsummary: s\nrelated:\n  - missing-id\n---\nBody.\n"
    )

    issues = _check_codex(codex_dir)

    broken = [i for i in issues if i.check == "broken_related_link"]
    assert len(broken) == 1
    assert "missing-id" in broken[0].detail


def test_check_codex_broken_related_link_detail_exact_format(tmp_path):
    """_check_codex broken_related_link detail is exactly: related ID 'X' does not exist."""
    # Exercises: lore codex show conceptual-workflows-health
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "decisions-008.md").write_text(
        "---\nid: decisions-008\ntitle: D008\nsummary: s\nrelated:\n  - decisions-999\n---\nBody.\n"
    )

    issues = _check_codex(codex_dir)

    broken = [i for i in issues if i.check == "broken_related_link"]
    assert len(broken) == 1
    assert broken[0].detail == "related ID 'decisions-999' does not exist"


def test_check_codex_broken_related_link_issue_fields(tmp_path):
    """_check_codex returns HealthIssue with correct severity, entity_type, and check for broken link."""
    # Exercises: lore codex show conceptual-workflows-health
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "doc-x.md").write_text(
        "---\nid: doc-x\ntitle: X\nsummary: s\nrelated:\n  - ghost-id\n---\nBody.\n"
    )

    issues = _check_codex(codex_dir)

    broken = [i for i in issues if i.check == "broken_related_link"]
    assert len(broken) == 1
    assert broken[0].severity == "error"
    assert broken[0].entity_type == "codex"
    assert broken[0].id == "doc-x"


def test_check_codex_all_valid_related_no_broken_link(tmp_path):
    """_check_codex returns no broken_related_link issues when all related IDs exist."""
    # Exercises: lore codex show conceptual-workflows-health
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "decisions-007.md").write_text(
        "---\nid: decisions-007\ntitle: D007\nsummary: s\nrelated:\n  - decisions-008\n---\nBody.\n"
    )
    (codex_dir / "decisions-008.md").write_text(
        "---\nid: decisions-008\ntitle: D008\nsummary: s\nrelated:\n  - decisions-007\n---\nBody.\n"
    )

    issues = _check_codex(codex_dir)

    broken = [i for i in issues if i.check == "broken_related_link"]
    assert broken == []


def test_check_codex_two_missing_related_ids_two_errors(tmp_path):
    """_check_codex returns two broken_related_link issues when two related IDs are missing."""
    # Exercises: lore codex show conceptual-workflows-health
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "doc-multi.md").write_text(
        "---\nid: doc-multi\ntitle: Multi\nsummary: s\nrelated:\n  - missing-a\n  - missing-b\n---\nBody.\n"
    )

    issues = _check_codex(codex_dir)

    broken = [i for i in issues if i.check == "broken_related_link"]
    assert len(broken) == 2
    broken_details = {i.detail for i in broken}
    assert "related ID 'missing-a' does not exist" in broken_details
    assert "related ID 'missing-b' does not exist" in broken_details


def test_check_codex_no_related_field_no_broken_link_error(tmp_path):
    """_check_codex returns no broken_related_link issues when doc has no related field."""
    # Exercises: lore codex show conceptual-workflows-health
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "doc-no-related.md").write_text(
        "---\nid: doc-no-related\ntitle: No Related\nsummary: s\n---\nBody.\n"
    )

    issues = _check_codex(codex_dir)

    broken = [i for i in issues if i.check == "broken_related_link"]
    assert broken == []


# ---------------------------------------------------------------------------
# US-006: _check_codex — island_node detection (exact HealthIssue fields)
# Exercises: conceptual-workflows-health
# ---------------------------------------------------------------------------


def test_check_codex_island_node_exact_issue_fields(tmp_path):
    """_check_codex returns HealthIssue with exact fields for island node."""
    # Exercises: lore codex show conceptual-workflows-health
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "proposals-draft.md").write_text(
        "---\nid: proposals-draft\ntitle: Proposals\nsummary: s\n---\nBody.\n"
    )

    issues = _check_codex(codex_dir)

    islands = [i for i in issues if i.check == "island_node"]
    assert len(islands) == 1
    issue = islands[0]
    assert issue.severity == "warning"
    assert issue.entity_type == "codex"
    assert issue.id == "proposals-draft"
    assert issue.detail == "no documents link here"


def test_check_codex_linked_doc_not_island(tmp_path):
    """_check_codex returns no island_node issue for a doc referenced by another doc's related field."""
    # Exercises: lore codex show conceptual-workflows-health
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "decisions-007.md").write_text(
        "---\nid: decisions-007\ntitle: D007\nsummary: s\n---\nBody.\n"
    )
    (codex_dir / "decisions-008.md").write_text(
        "---\nid: decisions-008\ntitle: D008\nsummary: s\nrelated:\n  - decisions-007\n---\nBody.\n"
    )

    issues = _check_codex(codex_dir)

    island_ids = [i.id for i in issues if i.check == "island_node"]
    assert "decisions-007" not in island_ids


def test_check_codex_single_doc_is_island(tmp_path):
    """_check_codex returns island_node warning for the only doc in codex (cannot self-link)."""
    # Exercises: lore codex show conceptual-workflows-health
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "solo-doc.md").write_text(
        "---\nid: solo-doc\ntitle: Solo\nsummary: s\n---\nBody.\n"
    )

    issues = _check_codex(codex_dir)

    islands = [i for i in issues if i.check == "island_node"]
    assert len(islands) == 1
    assert islands[0].id == "solo-doc"


def test_check_codex_mutual_related_neither_island(tmp_path):
    """_check_codex returns no island_node issues when two docs each list the other in related."""
    # Exercises: lore codex show conceptual-workflows-health
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "doc-a.md").write_text(
        "---\nid: doc-a\ntitle: Doc A\nsummary: s\nrelated:\n  - doc-b\n---\nBody.\n"
    )
    (codex_dir / "doc-b.md").write_text(
        "---\nid: doc-b\ntitle: Doc B\nsummary: s\nrelated:\n  - doc-a\n---\nBody.\n"
    )

    issues = _check_codex(codex_dir)

    islands = [i for i in issues if i.check == "island_node"]
    assert islands == []


# ---------------------------------------------------------------------------
# _check_artifacts
# ---------------------------------------------------------------------------


def test_check_artifacts_valid_artifact_no_issues(tmp_path):
    """_check_artifacts returns no issues for a fully valid artifact."""
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    artifacts_dir.mkdir(parents=True)
    (artifacts_dir / "valid.md").write_text(
        "---\nid: valid\ntitle: Valid\nsummary: All fields present\n---\nBody.\n"
    )

    issues = _check_artifacts(artifacts_dir)

    assert issues == []


# ---------------------------------------------------------------------------
# US-007: _check_artifacts — exact HealthIssue fields
# Exercises: conceptual-workflows-health
# ---------------------------------------------------------------------------


def test_check_artifacts_missing_id_exact_fields(tmp_path):
    """_check_artifacts returns HealthIssue with correct severity, check, detail, and filepath id when id missing."""
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    artifacts_dir.mkdir(parents=True)
    (artifacts_dir / "fi-broken.md").write_text(
        "---\ntitle: Broken\nsummary: Test\n---\nBody.\n"
    )

    issues = _check_artifacts(artifacts_dir)

    assert len(issues) == 1
    issue = issues[0]
    assert issue.severity == "error"
    assert issue.check == "missing_frontmatter"
    assert issue.detail == "field 'id' absent"
    # id must be a relative filepath (not just the stem, not an absolute path)
    assert issue.id == ".lore/artifacts/fi-broken.md"


def test_check_artifacts_missing_title_exact_fields(tmp_path):
    """_check_artifacts returns HealthIssue with detail="field 'title' absent" and filepath id when title missing."""
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    artifacts_dir.mkdir(parents=True)
    (artifacts_dir / "fi-broken.md").write_text(
        "---\nid: fi-broken\nsummary: Test\n---\nBody.\n"
    )

    issues = _check_artifacts(artifacts_dir)

    assert len(issues) == 1
    issue = issues[0]
    assert issue.severity == "error"
    assert issue.check == "missing_frontmatter"
    assert issue.detail == "field 'title' absent"
    # id must be the relative filepath, not the artifact's id value
    assert issue.id == ".lore/artifacts/fi-broken.md"


def test_check_artifacts_missing_summary_exact_fields(tmp_path):
    """_check_artifacts returns HealthIssue with detail="field 'summary' absent" and filepath id when summary missing."""
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    artifacts_dir.mkdir(parents=True)
    (artifacts_dir / "fi-broken.md").write_text(
        "---\nid: fi-broken\ntitle: Broken\n---\nBody.\n"
    )

    issues = _check_artifacts(artifacts_dir)

    assert len(issues) == 1
    issue = issues[0]
    assert issue.severity == "error"
    assert issue.check == "missing_frontmatter"
    assert issue.detail == "field 'summary' absent"
    # id must be the relative filepath, not the artifact's id value
    assert issue.id == ".lore/artifacts/fi-broken.md"


def test_check_artifacts_empty_frontmatter_reports_exactly_one_issue(tmp_path):
    """_check_artifacts reports exactly one issue for empty frontmatter (first missing field: id)."""
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    artifacts_dir.mkdir(parents=True)
    (artifacts_dir / "fi-empty.md").write_text(
        "---\n---\nBody.\n"
    )

    issues = _check_artifacts(artifacts_dir)

    assert len(issues) == 1
    assert issues[0].check == "missing_frontmatter"
    assert issues[0].detail == "field 'id' absent"
    assert issues[0].id == ".lore/artifacts/fi-empty.md"


def test_check_artifacts_walks_subdirectories(tmp_path):
    """_check_artifacts walks all .md files under artifacts_dir including subdirectories."""
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    subdir = artifacts_dir / "sub"
    subdir.mkdir(parents=True)
    (subdir / "fi-nested.md").write_text(
        "---\ntitle: Nested\nsummary: Test\n---\nBody.\n"
    )

    issues = _check_artifacts(artifacts_dir)

    assert len(issues) == 1
    assert issues[0].check == "missing_frontmatter"
    assert issues[0].detail == "field 'id' absent"
    assert issues[0].id == ".lore/artifacts/sub/fi-nested.md"


# ---------------------------------------------------------------------------
# _check_doctrines
# ---------------------------------------------------------------------------


def _make_doctrine_dirs(tmp_path):
    """Create and return (doctrines_dir, knights_dir, artifacts_dir)."""
    doctrines_dir = tmp_path / ".lore" / "doctrines"
    doctrines_dir.mkdir(parents=True)
    knights_dir = tmp_path / ".lore" / "knights"
    knights_dir.mkdir(parents=True)
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    artifacts_dir.mkdir(parents=True)
    return doctrines_dir, knights_dir, artifacts_dir


def test_check_doctrines_yaml_without_design_md_reports_orphan(tmp_path):
    """_check_doctrines reports error for a .yaml file with no matching .design.md."""
    doctrines_dir, knights_dir, artifacts_dir = _make_doctrine_dirs(tmp_path)
    (doctrines_dir / "orphan.yaml").write_text("id: orphan\ntitle: Orphan\nsummary: s\nsteps: []\n")

    issues = _check_doctrines(doctrines_dir, knights_dir, artifacts_dir)

    assert any(i.check == "orphaned_file" and i.severity == "error" for i in issues)


def test_check_doctrines_design_md_without_yaml_reports_orphan(tmp_path):
    """_check_doctrines reports error for a .design.md file with no matching .yaml."""
    doctrines_dir, knights_dir, artifacts_dir = _make_doctrine_dirs(tmp_path)
    (doctrines_dir / "orphan.design.md").write_text(
        "---\nid: orphan\ntitle: Orphan\nsummary: s\n---\nBody.\n"
    )

    issues = _check_doctrines(doctrines_dir, knights_dir, artifacts_dir)

    assert any(i.check == "orphaned_file" and i.severity == "error" for i in issues)


def test_check_doctrines_broken_artifact_ref_in_notes_reports_error(tmp_path):
    """_check_doctrines reports error when step notes reference a non-existent artifact ID."""
    doctrines_dir, knights_dir, artifacts_dir = _make_doctrine_dirs(tmp_path)

    (doctrines_dir / "feat-y.design.md").write_text(
        "---\nid: feat-y\ntitle: Y\nsummary: s\n---\nBody.\n"
    )
    (doctrines_dir / "feat-y.yaml").write_text(
        "id: feat-y\ntitle: Y\nsummary: s\nsteps:\n"
        "  - id: step-1\n    title: Step 1\n    notes: see fi-missing-artifact\n"
    )

    issues = _check_doctrines(doctrines_dir, knights_dir, artifacts_dir)

    assert any(i.check == "broken_artifact_ref" and i.severity == "error" for i in issues)


# ---------------------------------------------------------------------------
# _check_knights
# ---------------------------------------------------------------------------


def test_check_knights_mission_refs_missing_knight_reports_error(lore_dir):
    """_check_knights reports error when a mission references a non-existent knight file."""
    from tests.conftest import insert_mission, insert_quest

    insert_quest(lore_dir, "q-0001", "Test Quest")
    insert_mission(lore_dir, "m-0001", "q-0001", "Test Mission", knight="missing-knight")

    knights_dir = lore_dir / ".lore" / "knights"
    issues = _check_knights(knights_dir, lore_dir)

    assert any(i.check == "missing_file" and i.severity == "error" for i in issues)


def test_check_knights_mission_refs_soft_deleted_knight_no_error(lore_dir):
    """_check_knights does not report error when referenced knight has .md.deleted suffix."""
    from tests.conftest import insert_mission, insert_quest

    insert_quest(lore_dir, "q-0002", "Test Quest 2")
    insert_mission(lore_dir, "m-0002", "q-0002", "Test Mission 2", knight="soft-deleted-knight")
    knights_dir = lore_dir / ".lore" / "knights"
    (knights_dir / "soft-deleted-knight.md.deleted").write_text("deleted")

    issues = _check_knights(knights_dir, lore_dir)

    assert not any(i.check == "missing_file" for i in issues)


def test_check_knights_mission_refs_present_knight_no_issues(lore_dir):
    """_check_knights returns no issues when the referenced knight file exists."""
    from tests.conftest import insert_mission, insert_quest

    insert_quest(lore_dir, "q-0003", "Test Quest 3")
    insert_mission(lore_dir, "m-0003", "q-0003", "Test Mission 3", knight="existing-knight")
    knights_dir = lore_dir / ".lore" / "knights"
    (knights_dir / "existing-knight.md").write_text(
        "---\nid: existing-knight\ntitle: Knight\nsummary: s\n---\nBody.\n"
    )

    issues = _check_knights(knights_dir, lore_dir)

    assert issues == []


def test_check_knights_no_missions_with_knights_no_issues(lore_dir):
    """_check_knights returns no issues when no missions reference any knight."""
    from tests.conftest import insert_mission, insert_quest

    insert_quest(lore_dir, "q-0004", "Test Quest 4")
    insert_mission(lore_dir, "m-0004", "q-0004", "Test Mission 4", knight=None)

    knights_dir = lore_dir / ".lore" / "knights"
    issues = _check_knights(knights_dir, lore_dir)

    assert issues == []


# ---------------------------------------------------------------------------
# US-011: _check_knights — detail contains knight name and mission ID
# ---------------------------------------------------------------------------


def test_check_knights_missing_file_detail_contains_not_found_phrase(lore_dir):
    """_check_knights HealthIssue.detail contains the phrase 'not found on disk'."""
    # Exercises: lore codex show conceptual-workflows-health
    # AC: detail format is "referenced by <ids> but not found on disk"
    from tests.conftest import insert_mission, insert_quest

    insert_quest(lore_dir, "q-a001", "Quest A")
    insert_mission(lore_dir, "m-a042", "q-a001", "Mission 42", knight="tech-lead")

    knights_dir = lore_dir / ".lore" / "knights"
    issues = _check_knights(knights_dir, lore_dir)

    missing = [i for i in issues if i.check == "missing_file"]
    assert len(missing) == 1
    assert "not found on disk" in missing[0].detail


def test_check_knights_missing_file_detail_contains_mission_id(lore_dir):
    """_check_knights HealthIssue.detail contains the referencing mission ID."""
    # Exercises: lore codex show conceptual-workflows-health
    from tests.conftest import insert_mission, insert_quest

    insert_quest(lore_dir, "q-b001", "Quest B")
    insert_mission(lore_dir, "m-b042", "q-b001", "Mission 42", knight="tech-lead")

    knights_dir = lore_dir / ".lore" / "knights"
    issues = _check_knights(knights_dir, lore_dir)

    missing = [i for i in issues if i.check == "missing_file"]
    assert len(missing) == 1
    assert "m-b042" in missing[0].detail


def test_check_knights_multiple_missions_same_missing_knight_one_issue(lore_dir):
    """_check_knights emits one HealthIssue per unique missing knight — detail includes 'referenced by'."""
    # Exercises: lore codex show conceptual-workflows-health
    # AC: one issue per unique knight; detail says "referenced by ..."
    from tests.conftest import insert_mission, insert_quest

    insert_quest(lore_dir, "q-c001", "Quest C")
    insert_mission(lore_dir, "m-c010", "q-c001", "Mission 10", knight="tech-lead")
    insert_mission(lore_dir, "m-c011", "q-c001", "Mission 11", knight="tech-lead")
    insert_mission(lore_dir, "m-c012", "q-c001", "Mission 12", knight="tech-lead")

    knights_dir = lore_dir / ".lore" / "knights"
    issues = _check_knights(knights_dir, lore_dir)

    missing = [i for i in issues if i.check == "missing_file"]
    assert len(missing) == 1
    assert "referenced by" in missing[0].detail


def test_check_knights_multiple_missions_same_missing_knight_detail_contains_all_ids(lore_dir):
    """_check_knights single HealthIssue detail contains all referencing mission IDs."""
    # Exercises: lore codex show conceptual-workflows-health
    from tests.conftest import insert_mission, insert_quest

    insert_quest(lore_dir, "q-d001", "Quest D")
    insert_mission(lore_dir, "m-d010", "q-d001", "Mission 10", knight="tech-lead")
    insert_mission(lore_dir, "m-d011", "q-d001", "Mission 11", knight="tech-lead")
    insert_mission(lore_dir, "m-d012", "q-d001", "Mission 12", knight="tech-lead")

    knights_dir = lore_dir / ".lore" / "knights"
    issues = _check_knights(knights_dir, lore_dir)

    missing = [i for i in issues if i.check == "missing_file"]
    assert len(missing) == 1
    detail = missing[0].detail
    assert "m-d010" in detail
    assert "m-d011" in detail
    assert "m-d012" in detail


# ---------------------------------------------------------------------------
# _check_watchers
# ---------------------------------------------------------------------------


def test_check_watchers_broken_doctrine_ref_in_action_reports_error(tmp_path):
    """_check_watchers reports error when action references a non-existent doctrine."""
    watchers_dir = tmp_path / ".lore" / "watchers"
    watchers_dir.mkdir(parents=True)
    doctrines_dir = tmp_path / ".lore" / "doctrines"
    doctrines_dir.mkdir(parents=True)
    (watchers_dir / "broken-ref.yaml").write_text(
        "id: broken-ref\ntitle: Broken\nsummary: s\naction: nonexistent-doctrine\n"
    )

    issues = _check_watchers(watchers_dir, doctrines_dir)

    assert any(i.check == "broken_doctrine_ref" and i.severity == "error" for i in issues)


def test_check_watchers_valid_watcher_no_issues(tmp_path):
    """_check_watchers returns no issues for a watcher with a valid doctrine ref."""
    watchers_dir = tmp_path / ".lore" / "watchers"
    watchers_dir.mkdir(parents=True)
    doctrines_dir = tmp_path / ".lore" / "doctrines"
    doctrines_dir.mkdir(parents=True)

    (doctrines_dir / "real-doctrine.design.md").write_text(
        "---\nid: real-doctrine\ntitle: Real\nsummary: s\n---\nBody.\n"
    )
    (doctrines_dir / "real-doctrine.yaml").write_text(
        "id: real-doctrine\ntitle: Real\nsummary: s\nsteps: []\n"
    )
    (watchers_dir / "valid.yaml").write_text(
        "id: valid\ntitle: Valid\nsummary: s\naction: real-doctrine\n"
    )

    issues = _check_watchers(watchers_dir, doctrines_dir)

    assert issues == []


def test_check_watchers_deleted_files_excluded(tmp_path):
    """_check_watchers does not check .yaml.deleted files."""
    watchers_dir = tmp_path / ".lore" / "watchers"
    watchers_dir.mkdir(parents=True)
    doctrines_dir = tmp_path / ".lore" / "doctrines"
    doctrines_dir.mkdir(parents=True)
    (watchers_dir / "deleted.yaml.deleted").write_text(
        "id: deleted\ntitle: Deleted\nsummary: s\naction: nonexistent-doctrine\n"
    )

    issues = _check_watchers(watchers_dir, doctrines_dir)

    assert issues == []


def test_check_watchers_only_design_md_no_yaml_reports_broken_ref(tmp_path):
    """_check_watchers reports broken_doctrine_ref when doctrine has only .design.md (incomplete pair)."""
    # Exercises: lore codex show conceptual-workflows-health
    # Requires _build_doctrine_name_index to enforce complete pairs (both .yaml AND .design.md)
    watchers_dir = tmp_path / ".lore" / "watchers"
    watchers_dir.mkdir(parents=True)
    doctrines_dir = tmp_path / ".lore" / "doctrines"
    doctrines_dir.mkdir(parents=True)
    # Only .design.md — no .yaml — incomplete pair, should NOT be in doctrine index
    (doctrines_dir / "feat-auth.design.md").write_text(
        "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n"
    )
    (watchers_dir / "on-quest-close.yaml").write_text(
        "id: on-quest-close\ntitle: On Close\nsummary: s\naction: feat-auth\n"
    )

    issues = _check_watchers(watchers_dir, doctrines_dir)

    broken = [i for i in issues if i.check == "broken_doctrine_ref"]
    assert len(broken) == 1
    assert broken[0].detail == "'feat-auth' not found"


# ---------------------------------------------------------------------------
# US-012: _build_doctrine_name_index — complete pairs only
# Exercises: conceptual-workflows-health
# ---------------------------------------------------------------------------


def test_build_doctrine_name_index_only_design_md_not_included(tmp_path):
    """_build_doctrine_name_index excludes stem when only .design.md exists (no .yaml)."""
    # Exercises: lore codex show conceptual-workflows-health
    # This test MUST fail until _build_doctrine_name_index enforces complete pairs
    doctrines_dir = tmp_path / ".lore" / "doctrines"
    doctrines_dir.mkdir(parents=True)
    (doctrines_dir / "feat-payments.design.md").write_text("body")
    # No feat-payments.yaml — incomplete pair

    result = _build_doctrine_name_index(doctrines_dir)

    assert "feat-payments" not in result


def test_build_doctrine_name_index_multiple_complete_pairs(tmp_path):
    """_build_doctrine_name_index returns all stems with complete pairs."""
    # Exercises: lore codex show conceptual-workflows-health
    doctrines_dir = tmp_path / ".lore" / "doctrines"
    doctrines_dir.mkdir(parents=True)
    for stem in ("feat-auth", "feat-payments"):
        (doctrines_dir / f"{stem}.design.md").write_text("body")
        (doctrines_dir / f"{stem}.yaml").write_text(f"id: {stem}")
    # Partial pair — should NOT be included
    (doctrines_dir / "feat-orphan.design.md").write_text("body")

    result = _build_doctrine_name_index(doctrines_dir)

    assert result == {"feat-auth", "feat-payments"}


# ---------------------------------------------------------------------------
# _write_report
# ---------------------------------------------------------------------------


def test_write_report_creates_file_at_correct_path(tmp_path):
    """_write_report creates the report file at codex_dir/transient/health-{timestamp}.md."""
    codex_dir = tmp_path / ".lore" / "codex"
    report = HealthReport(errors=(), warnings=())
    timestamp = "2026-04-09T14-32-00"

    path = _write_report(report, codex_dir, timestamp)

    assert path == codex_dir / "transient" / "health-2026-04-09T14-32-00.md"
    assert path.exists()


def test_write_report_clean_run_contains_no_issues_text(tmp_path):
    """_write_report produces 'No issues found.' in content for a clean run."""
    codex_dir = tmp_path / ".lore" / "codex"
    report = HealthReport(errors=(), warnings=())
    timestamp = "2026-04-09T14-32-00"

    path = _write_report(report, codex_dir, timestamp)

    content = path.read_text()
    assert "No issues found." in content


def test_write_report_with_issues_contains_markdown_table(tmp_path):
    """_write_report produces a markdown table when issues are present."""
    codex_dir = tmp_path / ".lore" / "codex"
    issue = HealthIssue(
        severity="error",
        entity_type="doctrines",
        id="feat-auth",
        check="broken_knight_ref",
        detail="'senior-engineer' not found (step 2)",
    )
    report = HealthReport(errors=(issue,), warnings=())
    timestamp = "2026-04-09T14-32-00"

    path = _write_report(report, codex_dir, timestamp)

    content = path.read_text()
    assert "| ERROR" in content or "| error" in content.lower()
    assert "feat-auth" in content


def test_write_report_file_begins_with_yaml_frontmatter(tmp_path):
    """_write_report file begins with YAML frontmatter block containing id, title, and summary."""
    codex_dir = tmp_path / ".lore" / "codex"
    report = HealthReport(errors=(), warnings=())
    timestamp = "2026-04-09T14-32-00"

    path = _write_report(report, codex_dir, timestamp)

    content = path.read_text()
    assert content.startswith("---\n"), "File must begin with YAML frontmatter '---'"
    lines = content.splitlines()
    closing_index = lines.index("---", 1)
    frontmatter_lines = lines[1:closing_index]
    keys = {line.split(":")[0].strip() for line in frontmatter_lines if ":" in line}
    assert "id" in keys, f"Frontmatter missing 'id'. Keys found: {keys}"
    assert "title" in keys, f"Frontmatter missing 'title'. Keys found: {keys}"
    assert "summary" in keys, f"Frontmatter missing 'summary'. Keys found: {keys}"


def test_write_report_frontmatter_id_includes_timestamp(tmp_path):
    """_write_report frontmatter id field is health-{timestamp}."""
    codex_dir = tmp_path / ".lore" / "codex"
    report = HealthReport(errors=(), warnings=())
    timestamp = "2026-04-09T14-32-00"

    path = _write_report(report, codex_dir, timestamp)

    content = path.read_text()
    assert f"id: health-{timestamp}" in content, (
        f"Expected frontmatter id 'health-{timestamp}' in content."
    )


# ---------------------------------------------------------------------------
# health_check — scope filtering
# ---------------------------------------------------------------------------


def test_health_check_scope_codex_watchers_runs_only_those_two(lore_dir):
    """health_check with scope=['codex', 'watchers'] runs only codex and watchers."""
    artifacts_dir = lore_dir / ".lore" / "artifacts"
    (artifacts_dir / "no-id.md").write_text(
        "---\ntitle: No Title\nsummary: s\n---\nBody.\n"
    )
    watchers_dir = lore_dir / ".lore" / "watchers"
    (watchers_dir / "broken.yaml").write_text(
        "id: broken\ntitle: Broken\nsummary: s\naction: nonexistent-doctrine\n"
    )

    report = health_check(lore_dir, scope=["codex", "watchers"])

    entity_types_with_issues = {i.entity_type for i in report.issues}
    assert "artifacts" not in entity_types_with_issues
    assert "doctrines" not in entity_types_with_issues
    assert "knights" not in entity_types_with_issues


def test_health_check_clean_project_returns_empty_errors(lore_dir):
    """health_check on a fully clean project returns HealthReport with empty errors."""
    report = health_check(lore_dir, scope=None)

    assert report.errors == ()


def test_health_check_scope_none_with_all_type_errors_returns_all_entity_types(lore_dir):
    """health_check scope=None on a project with errors in each type returns all five entity_type values in issues."""
    from tests.conftest import insert_mission, insert_quest

    codex_dir = lore_dir / ".lore" / "codex"
    (codex_dir / "bad.md").write_text("---\ntitle: No ID\nsummary: s\n---\nBody.\n")

    artifacts_dir = lore_dir / ".lore" / "artifacts"
    (artifacts_dir / "bad.md").write_text("---\ntitle: No ID\nsummary: s\n---\nBody.\n")

    doctrines_dir = lore_dir / ".lore" / "doctrines"
    (doctrines_dir / "bad.yaml").write_text(
        "id: bad\ntitle: Bad\nsummary: s\nsteps: []\n"
    )

    watchers_dir = lore_dir / ".lore" / "watchers"
    (watchers_dir / "bad.yaml").write_text(
        "id: bad-watcher\ntitle: Bad\nsummary: s\naction: nonexistent-doctrine\n"
    )

    insert_quest(lore_dir, "q-bb01", "Q")
    insert_mission(lore_dir, "m-bb01", "q-bb01", "M", knight="nonexistent-knight-xyz")

    report = health_check(lore_dir, scope=None)

    entity_types = {i.entity_type for i in report.errors}
    assert "codex" in entity_types
    assert "artifacts" in entity_types
    assert "doctrines" in entity_types
    assert "watchers" in entity_types
    assert "knights" in entity_types


def test_health_check_scope_doctrines_knights_skips_other_types(lore_dir):
    """health_check with scope=['doctrines', 'knights'] returns only doctrines/knights issues."""
    # Inject codex error and artifacts error — must not appear in report
    codex_dir = lore_dir / ".lore" / "codex"
    (codex_dir / "bad.md").write_text("---\ntitle: No ID\nsummary: s\n---\nBody.\n")
    artifacts_dir = lore_dir / ".lore" / "artifacts"
    (artifacts_dir / "bad.md").write_text("---\ntitle: No ID\nsummary: s\n---\nBody.\n")
    # Inject watchers error — must not appear in report
    watchers_dir = lore_dir / ".lore" / "watchers"
    (watchers_dir / "broken.yaml").write_text(
        "id: broken\ntitle: Broken\nsummary: s\naction: missing-doctrine\n"
    )
    # Inject doctrines error — must appear in report
    doctrines_dir = lore_dir / ".lore" / "doctrines"
    (doctrines_dir / "orphan.design.md").write_text(
        "---\nid: orphan\ntitle: Orphan\nsummary: s\n---\nBody.\n"
    )

    report = health_check(lore_dir, scope=["doctrines", "knights"])

    entity_types = {i.entity_type for i in report.issues}
    assert "codex" not in entity_types
    assert "artifacts" not in entity_types
    assert "watchers" not in entity_types


def test_health_check_scope_watchers_skips_all_other_types(lore_dir):
    """health_check with scope=['watchers'] returns only watcher issues, nothing from others."""
    # Inject errors in codex, artifacts, doctrines — must not appear
    codex_dir = lore_dir / ".lore" / "codex"
    (codex_dir / "bad.md").write_text("---\ntitle: No ID\nsummary: s\n---\nBody.\n")
    artifacts_dir = lore_dir / ".lore" / "artifacts"
    (artifacts_dir / "bad.md").write_text("---\ntitle: No ID\nsummary: s\n---\nBody.\n")
    doctrines_dir = lore_dir / ".lore" / "doctrines"
    (doctrines_dir / "orphan.design.md").write_text(
        "---\nid: orphan\ntitle: Orphan\nsummary: s\n---\nBody.\n"
    )
    # Inject watcher error — must appear
    watchers_dir = lore_dir / ".lore" / "watchers"
    (watchers_dir / "broken.yaml").write_text(
        "id: broken\ntitle: Broken\nsummary: s\naction: missing-doctrine\n"
    )

    report = health_check(lore_dir, scope=["watchers"])

    entity_types = {i.entity_type for i in report.issues}
    assert "codex" not in entity_types
    assert "artifacts" not in entity_types
    assert "doctrines" not in entity_types
    assert "knights" not in entity_types


def test_health_check_scope_empty_list_returns_clean_report(lore_dir):
    """health_check with scope=[] runs no checkers and returns a clean HealthReport."""
    # Inject errors into all types — none should appear since scope is empty
    codex_dir = lore_dir / ".lore" / "codex"
    (codex_dir / "bad.md").write_text("---\ntitle: No ID\nsummary: s\n---\nBody.\n")
    artifacts_dir = lore_dir / ".lore" / "artifacts"
    (artifacts_dir / "bad.md").write_text("---\ntitle: No ID\nsummary: s\n---\nBody.\n")
    watchers_dir = lore_dir / ".lore" / "watchers"
    (watchers_dir / "broken.yaml").write_text(
        "id: broken\ntitle: Broken\nsummary: s\naction: missing-doctrine\n"
    )

    report = health_check(lore_dir, scope=[])

    assert report.errors == ()
    assert report.warnings == ()


# ---------------------------------------------------------------------------
# US-008: _check_doctrines — orphaned file detection (exact HealthIssue fields)
# Exercises: lore codex show conceptual-workflows-health
# ---------------------------------------------------------------------------


def test_check_doctrines_orphaned_yaml_detail_is_design_md_missing(tmp_path):
    """`_check_doctrines`: .yaml stem with no matching .design.md returns detail='.design.md missing'."""
    # Exercises: lore codex show conceptual-workflows-health
    doctrines_dir, knights_dir, artifacts_dir = _make_doctrine_dirs(tmp_path)
    (doctrines_dir / "feat-auth.yaml").write_text(
        "id: feat-auth\ntitle: Auth\nsummary: s\nsteps: []\n"
    )

    issues = _check_doctrines(doctrines_dir, knights_dir, artifacts_dir)

    orphans = [i for i in issues if i.check == "orphaned_file"]
    assert len(orphans) == 1
    assert orphans[0].severity == "error"
    assert orphans[0].entity_type == "doctrines"
    assert orphans[0].id == "feat-auth"
    assert orphans[0].detail == ".design.md missing"


def test_check_doctrines_orphaned_design_md_detail_is_yaml_missing(tmp_path):
    """`_check_doctrines`: .design.md stem with no matching .yaml returns detail='.yaml missing'."""
    # Exercises: lore codex show conceptual-workflows-health
    doctrines_dir, knights_dir, artifacts_dir = _make_doctrine_dirs(tmp_path)
    (doctrines_dir / "feat-auth.design.md").write_text(
        "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n"
    )

    issues = _check_doctrines(doctrines_dir, knights_dir, artifacts_dir)

    orphans = [i for i in issues if i.check == "orphaned_file"]
    assert len(orphans) == 1
    assert orphans[0].severity == "error"
    assert orphans[0].entity_type == "doctrines"
    assert orphans[0].id == "feat-auth"
    assert orphans[0].detail == ".yaml missing"


def test_check_doctrines_complete_pair_no_orphaned_file_issue(tmp_path):
    """`_check_doctrines`: complete pair (both files present) returns no orphaned_file issue."""
    # Exercises: lore codex show conceptual-workflows-health
    doctrines_dir, knights_dir, artifacts_dir = _make_doctrine_dirs(tmp_path)
    (doctrines_dir / "feat-auth.yaml").write_text(
        "id: feat-auth\ntitle: Auth\nsummary: s\nsteps: []\n"
    )
    (doctrines_dir / "feat-auth.design.md").write_text(
        "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n"
    )

    issues = _check_doctrines(doctrines_dir, knights_dir, artifacts_dir)

    orphans = [i for i in issues if i.check == "orphaned_file"]
    assert orphans == []


def test_check_doctrines_multiple_orphans_each_produce_own_issue(tmp_path):
    """`_check_doctrines`: multiple orphans in same directory each produce their own HealthIssue."""
    # Exercises: lore codex show conceptual-workflows-health
    doctrines_dir, knights_dir, artifacts_dir = _make_doctrine_dirs(tmp_path)
    # feat-auth.yaml with no .design.md
    (doctrines_dir / "feat-auth.yaml").write_text(
        "id: feat-auth\ntitle: Auth\nsummary: s\nsteps: []\n"
    )
    # feat-payments.design.md with no .yaml
    (doctrines_dir / "feat-payments.design.md").write_text(
        "---\nid: feat-payments\ntitle: Payments\nsummary: s\n---\nBody.\n"
    )

    issues = _check_doctrines(doctrines_dir, knights_dir, artifacts_dir)

    orphans = [i for i in issues if i.check == "orphaned_file"]
    assert len(orphans) == 2
    ids = {i.id for i in orphans}
    assert "feat-auth" in ids
    assert "feat-payments" in ids


# ---------------------------------------------------------------------------
# US-009: _check_doctrines — broken knight ref detection (exact HealthIssue fields)
# Exercises: conceptual-workflows-health
# ---------------------------------------------------------------------------


def test_check_doctrines_broken_knight_ref_exact_issue_fields(tmp_path):
    """_check_doctrines returns HealthIssue with correct fields when knight not found."""
    # Exercises: lore codex show conceptual-workflows-health
    doctrines_dir, knights_dir, artifacts_dir = _make_doctrine_dirs(tmp_path)

    (doctrines_dir / "feat-auth.design.md").write_text(
        "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n"
    )
    (doctrines_dir / "feat-auth.yaml").write_text(
        "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
        "  - id: step-1\n    title: Step 1\n"
        "  - id: step-2\n    title: Step 2\n    knight: missing-knight\n"
    )

    issues = _check_doctrines(doctrines_dir, knights_dir, artifacts_dir)

    broken = [i for i in issues if i.check == "broken_knight_ref"]
    assert len(broken) == 1
    issue = broken[0]
    assert issue.severity == "error"
    assert issue.entity_type == "doctrines"
    assert issue.id == "feat-auth"
    assert issue.check == "broken_knight_ref"
    assert issue.detail == "'missing-knight' not found (step 2)"


def test_check_doctrines_broken_knight_ref_step_number_one_based(tmp_path):
    """_check_doctrines uses 1-based step numbering in the detail field."""
    # Exercises: lore codex show conceptual-workflows-health
    doctrines_dir, knights_dir, artifacts_dir = _make_doctrine_dirs(tmp_path)

    (doctrines_dir / "feat-auth.design.md").write_text(
        "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n"
    )
    # First step (index 0, step number 1) references missing knight
    (doctrines_dir / "feat-auth.yaml").write_text(
        "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
        "  - id: step-1\n    title: Step 1\n    knight: missing-knight\n"
    )

    issues = _check_doctrines(doctrines_dir, knights_dir, artifacts_dir)

    broken = [i for i in issues if i.check == "broken_knight_ref"]
    assert len(broken) == 1
    assert broken[0].detail == "'missing-knight' not found (step 1)"


def test_check_doctrines_present_knight_no_broken_knight_ref(tmp_path):
    """_check_doctrines returns no broken_knight_ref when step knight file exists."""
    # Exercises: lore codex show conceptual-workflows-health
    doctrines_dir, knights_dir, artifacts_dir = _make_doctrine_dirs(tmp_path)

    (knights_dir / "tech-lead.md").write_text(
        "---\nid: tech-lead\ntitle: Tech Lead\nsummary: s\n---\nBody.\n"
    )
    (doctrines_dir / "feat-auth.design.md").write_text(
        "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n"
    )
    (doctrines_dir / "feat-auth.yaml").write_text(
        "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
        "  - id: step-1\n    title: Step 1\n"
        "  - id: step-2\n    title: Step 2\n    knight: tech-lead\n"
    )

    issues = _check_doctrines(doctrines_dir, knights_dir, artifacts_dir)

    broken = [i for i in issues if i.check == "broken_knight_ref"]
    assert broken == []


def test_check_doctrines_soft_deleted_knight_no_broken_knight_ref(tmp_path):
    """_check_doctrines returns no broken_knight_ref when knight is soft-deleted (.md.deleted)."""
    # Exercises: lore codex show conceptual-workflows-health
    doctrines_dir, knights_dir, artifacts_dir = _make_doctrine_dirs(tmp_path)

    (knights_dir / "senior-engineer.md.deleted").write_text("deleted")
    (doctrines_dir / "feat-auth.design.md").write_text(
        "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n"
    )
    (doctrines_dir / "feat-auth.yaml").write_text(
        "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
        "  - id: step-1\n    title: Step 1\n"
        "  - id: step-2\n    title: Step 2\n    knight: senior-engineer\n"
    )

    issues = _check_doctrines(doctrines_dir, knights_dir, artifacts_dir)

    broken = [i for i in issues if i.check == "broken_knight_ref"]
    assert broken == []


def test_check_doctrines_step_without_knight_field_no_broken_knight_ref(tmp_path):
    """_check_doctrines returns no broken_knight_ref issue when step has no knight field."""
    # Exercises: lore codex show conceptual-workflows-health
    doctrines_dir, knights_dir, artifacts_dir = _make_doctrine_dirs(tmp_path)

    (doctrines_dir / "feat-auth.design.md").write_text(
        "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n"
    )
    (doctrines_dir / "feat-auth.yaml").write_text(
        "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
        "  - id: step-1\n    title: Step 1\n"
        "  - id: step-2\n    title: Step 2\n"
    )

    issues = _check_doctrines(doctrines_dir, knights_dir, artifacts_dir)

    broken = [i for i in issues if i.check == "broken_knight_ref"]
    assert broken == []


def test_check_doctrines_multiple_broken_knight_refs_separate_issues(tmp_path):
    """_check_doctrines returns separate HealthIssue per broken knight ref step."""
    # Exercises: lore codex show conceptual-workflows-health
    doctrines_dir, knights_dir, artifacts_dir = _make_doctrine_dirs(tmp_path)

    (doctrines_dir / "feat-auth.design.md").write_text(
        "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n"
    )
    (doctrines_dir / "feat-auth.yaml").write_text(
        "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
        "  - id: step-1\n    title: Step 1\n    knight: missing-a\n"
        "  - id: step-2\n    title: Step 2\n"
        "  - id: step-3\n    title: Step 3\n    knight: missing-b\n"
    )

    issues = _check_doctrines(doctrines_dir, knights_dir, artifacts_dir)

    broken = [i for i in issues if i.check == "broken_knight_ref"]
    assert len(broken) == 2
    details = {i.detail for i in broken}
    assert "'missing-a' not found (step 1)" in details
    assert "'missing-b' not found (step 3)" in details


# ---------------------------------------------------------------------------
# US-010: _check_doctrines — broken artifact ref detection (exact HealthIssue fields)
# Exercises: conceptual-workflows-health
# ---------------------------------------------------------------------------


def test_check_doctrines_broken_artifact_ref_exact_detail_format(tmp_path):
    """_check_doctrines detail for broken_artifact_ref is exactly: 'fi-prd-v2' not found (step 3)."""
    # Exercises: lore codex show conceptual-workflows-health
    doctrines_dir, knights_dir, artifacts_dir = _make_doctrine_dirs(tmp_path)

    (doctrines_dir / "feat-auth.design.md").write_text(
        "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n"
    )
    (doctrines_dir / "feat-auth.yaml").write_text(
        "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
        "  - id: step-1\n    title: Step 1\n"
        "  - id: step-2\n    title: Step 2\n"
        "  - id: step-3\n    title: Step 3\n    notes: 'see artifact: fi-prd-v2'\n"
    )

    issues = _check_doctrines(doctrines_dir, knights_dir, artifacts_dir)

    broken = [i for i in issues if i.check == "broken_artifact_ref"]
    assert len(broken) == 1
    assert broken[0].detail == "'fi-prd-v2' not found (step 3)"


def test_check_doctrines_broken_artifact_ref_exact_issue_fields(tmp_path):
    """_check_doctrines returns HealthIssue with correct severity, entity_type, id, and check."""
    # Exercises: lore codex show conceptual-workflows-health
    doctrines_dir, knights_dir, artifacts_dir = _make_doctrine_dirs(tmp_path)

    (doctrines_dir / "feat-auth.design.md").write_text(
        "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n"
    )
    (doctrines_dir / "feat-auth.yaml").write_text(
        "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
        "  - id: step-1\n    title: Step 1\n    notes: see fi-prd-v2\n"
    )

    issues = _check_doctrines(doctrines_dir, knights_dir, artifacts_dir)

    broken = [i for i in issues if i.check == "broken_artifact_ref"]
    assert len(broken) == 1
    issue = broken[0]
    assert issue.severity == "error"
    assert issue.entity_type == "doctrines"
    assert issue.id == "feat-auth"
    assert issue.check == "broken_artifact_ref"
    assert issue.detail == "'fi-prd-v2' not found (step 1)"


def test_check_doctrines_present_artifact_no_broken_artifact_ref(tmp_path):
    """_check_doctrines returns no broken_artifact_ref when referenced artifact exists in index."""
    # Exercises: lore codex show conceptual-workflows-health
    doctrines_dir, knights_dir, artifacts_dir = _make_doctrine_dirs(tmp_path)

    (doctrines_dir / "feat-auth.design.md").write_text(
        "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n"
    )
    (doctrines_dir / "feat-auth.yaml").write_text(
        "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
        "  - id: step-3\n    title: Step 3\n    notes: see fi-prd-template\n"
    )
    (artifacts_dir / "fi-prd-template.md").write_text(
        "---\nid: fi-prd-template\ntitle: PRD Template\nsummary: s\n---\nContent.\n"
    )

    issues = _check_doctrines(doctrines_dir, knights_dir, artifacts_dir)

    broken = [i for i in issues if i.check == "broken_artifact_ref"]
    assert broken == []


def test_check_doctrines_step_without_notes_no_broken_artifact_ref(tmp_path):
    """_check_doctrines returns no broken_artifact_ref issue when step has no notes field."""
    # Exercises: lore codex show conceptual-workflows-health
    doctrines_dir, knights_dir, artifacts_dir = _make_doctrine_dirs(tmp_path)

    (doctrines_dir / "feat-auth.design.md").write_text(
        "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n"
    )
    (doctrines_dir / "feat-auth.yaml").write_text(
        "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
        "  - id: step-1\n    title: Step 1\n"
        "  - id: step-2\n    title: Step 2\n    knight: some-knight\n"
    )

    issues = _check_doctrines(doctrines_dir, knights_dir, artifacts_dir)

    broken = [i for i in issues if i.check == "broken_artifact_ref"]
    assert broken == []


def test_check_doctrines_notes_no_fi_pattern_no_broken_artifact_ref(tmp_path):
    """_check_doctrines returns no broken_artifact_ref when notes contain no fi-* tokens."""
    # Exercises: lore codex show conceptual-workflows-health
    doctrines_dir, knights_dir, artifacts_dir = _make_doctrine_dirs(tmp_path)

    (doctrines_dir / "feat-auth.design.md").write_text(
        "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n"
    )
    (doctrines_dir / "feat-auth.yaml").write_text(
        "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
        "  - id: step-1\n    title: Step 1\n    notes: See the design doc for details.\n"
    )

    issues = _check_doctrines(doctrines_dir, knights_dir, artifacts_dir)

    broken = [i for i in issues if i.check == "broken_artifact_ref"]
    assert broken == []


def test_check_doctrines_multiple_missing_artifact_refs_separate_issues(tmp_path):
    """_check_doctrines returns one broken_artifact_ref issue per missing artifact ref in same step."""
    # Exercises: lore codex show conceptual-workflows-health
    doctrines_dir, knights_dir, artifacts_dir = _make_doctrine_dirs(tmp_path)

    (doctrines_dir / "feat-auth.design.md").write_text(
        "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n"
    )
    (doctrines_dir / "feat-auth.yaml").write_text(
        "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
        "  - id: step-2\n    title: Step 2\n    notes: fi-missing-a and fi-missing-b\n"
    )

    issues = _check_doctrines(doctrines_dir, knights_dir, artifacts_dir)

    broken = [i for i in issues if i.check == "broken_artifact_ref"]
    assert len(broken) == 2
    details = {i.detail for i in broken}
    assert "'fi-missing-a' not found (step 2)" in details
    assert "'fi-missing-b' not found (step 2)" in details


def test_check_doctrines_broken_artifact_ref_step_number_one_based(tmp_path):
    """_check_doctrines uses 1-based step numbering in broken_artifact_ref detail."""
    # Exercises: lore codex show conceptual-workflows-health
    doctrines_dir, knights_dir, artifacts_dir = _make_doctrine_dirs(tmp_path)

    (doctrines_dir / "feat-auth.design.md").write_text(
        "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n"
    )
    (doctrines_dir / "feat-auth.yaml").write_text(
        "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
        "  - id: step-1\n    title: Step 1\n"
        "  - id: step-2\n    title: Step 2\n"
        "  - id: step-3\n    title: Step 3\n    notes: fi-ghost-art\n"
    )

    issues = _check_doctrines(doctrines_dir, knights_dir, artifacts_dir)

    broken = [i for i in issues if i.check == "broken_artifact_ref"]
    assert len(broken) == 1
    assert broken[0].detail == "'fi-ghost-art' not found (step 3)"


# ---------------------------------------------------------------------------
# US-010: _build_artifact_index
# Exercises: conceptual-workflows-health
# ---------------------------------------------------------------------------


def test_build_artifact_index_returns_valid_ids(tmp_path):
    """_build_artifact_index returns a set containing IDs from valid artifact files."""
    # Exercises: lore codex show conceptual-workflows-health
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    artifacts_dir.mkdir(parents=True)

    (artifacts_dir / "fi-prd-v1.md").write_text(
        "---\nid: fi-prd-v1\ntitle: PRD v1\nsummary: s\n---\nContent.\n"
    )
    (artifacts_dir / "fi-spec-alpha.md").write_text(
        "---\nid: fi-spec-alpha\ntitle: Spec Alpha\nsummary: s\n---\nContent.\n"
    )

    result = _build_artifact_index(artifacts_dir)

    assert "fi-prd-v1" in result
    assert "fi-spec-alpha" in result


def test_build_artifact_index_excludes_files_without_id(tmp_path):
    """_build_artifact_index does not include IDs from files missing the id frontmatter field."""
    # Exercises: lore codex show conceptual-workflows-health
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    artifacts_dir.mkdir(parents=True)

    (artifacts_dir / "fi-valid.md").write_text(
        "---\nid: fi-valid\ntitle: Valid\nsummary: s\n---\nContent.\n"
    )
    (artifacts_dir / "fi-broken.md").write_text(
        "---\ntitle: No ID\nsummary: s\n---\nContent.\n"
    )

    result = _build_artifact_index(artifacts_dir)

    assert "fi-valid" in result
    assert len([x for x in result if "broken" in x]) == 0


def test_build_artifact_index_returns_set_type(tmp_path):
    """_build_artifact_index returns a set object."""
    # Exercises: lore codex show conceptual-workflows-health
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    artifacts_dir.mkdir(parents=True)

    result = _build_artifact_index(artifacts_dir)

    assert isinstance(result, set)


def test_build_artifact_index_empty_dir_returns_empty_set(tmp_path):
    """_build_artifact_index returns empty set when artifacts directory has no .md files."""
    # Exercises: lore codex show conceptual-workflows-health
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    artifacts_dir.mkdir(parents=True)

    result = _build_artifact_index(artifacts_dir)

    assert result == set()


def test_build_artifact_index_two_valid_one_missing_id_returns_two(tmp_path):
    """_build_artifact_index with two valid and one missing-id artifact returns set of two."""
    # Exercises: lore codex show conceptual-workflows-health
    artifacts_dir = tmp_path / ".lore" / "artifacts"
    artifacts_dir.mkdir(parents=True)

    (artifacts_dir / "fi-a.md").write_text(
        "---\nid: fi-a\ntitle: A\nsummary: s\n---\nContent.\n"
    )
    (artifacts_dir / "fi-b.md").write_text(
        "---\nid: fi-b\ntitle: B\nsummary: s\n---\nContent.\n"
    )
    (artifacts_dir / "fi-no-id.md").write_text(
        "---\ntitle: No ID\nsummary: s\n---\nContent.\n"
    )

    result = _build_artifact_index(artifacts_dir)

    assert len(result) == 2
    assert "fi-a" in result


# ---------------------------------------------------------------------------
# US-013: _check_watchers — invalid YAML with line number
# ---------------------------------------------------------------------------


def test_check_watchers_invalid_yaml_detail_contains_parse_failed_at_line(tmp_path):
    """_check_watchers detail says 'parse failed at line N' for YAML syntax error."""
    # Exercises: lore codex show conceptual-workflows-health
    # detail must use exact phrase format: "parse failed at line N"
    watchers_dir = tmp_path / ".lore" / "watchers"
    watchers_dir.mkdir(parents=True)
    doctrines_dir = tmp_path / ".lore" / "doctrines"
    doctrines_dir.mkdir(parents=True)
    # Error is on line 3 (1-indexed): indented key under scalar
    (watchers_dir / "bad.yaml").write_text("id: bad\ntitle: Bad\n  broken: indented\n")

    issues = _check_watchers(watchers_dir, doctrines_dir)

    invalid_yaml_issues = [i for i in issues if i.check == "invalid_yaml"]
    assert len(invalid_yaml_issues) == 1, f"Expected 1 invalid_yaml issue, got {invalid_yaml_issues}"
    assert "parse failed at line" in invalid_yaml_issues[0].detail, (
        f"Expected 'parse failed at line' in detail, got: {invalid_yaml_issues[0].detail!r}"
    )


def test_check_watchers_invalid_yaml_line_number_from_problem_mark(tmp_path):
    """_check_watchers detail includes accurate line number from yaml.YAMLError.problem_mark."""
    # Exercises: lore codex show conceptual-workflows-health
    # e.problem_mark.line is 0-indexed; detail must show 1-indexed line number
    watchers_dir = tmp_path / ".lore" / "watchers"
    watchers_dir.mkdir(parents=True)
    doctrines_dir = tmp_path / ".lore" / "doctrines"
    doctrines_dir.mkdir(parents=True)
    # 5 valid lines then error on line 6 (1-indexed)
    content = (
        "id: my-watcher\n"
        "title: My Watcher\n"
        "summary: s\n"
        "trigger: quest_close\n"
        "action: some-doctrine\n"
        "  nested_under_scalar: bad\n"
    )
    (watchers_dir / "line6-error.yaml").write_text(content)

    issues = _check_watchers(watchers_dir, doctrines_dir)

    invalid_yaml_issues = [i for i in issues if i.check == "invalid_yaml"]
    assert len(invalid_yaml_issues) == 1
    detail = invalid_yaml_issues[0].detail
    assert "parse failed at line 6" in detail, (
        f"Expected 'parse failed at line 6' in detail, got: {detail!r}"
    )


def test_check_watchers_valid_yaml_no_invalid_yaml_issue(tmp_path):
    """_check_watchers returns no invalid_yaml issue for syntactically valid YAML."""
    # Exercises: lore codex show conceptual-workflows-health
    # Valid YAML must not produce any issue with check="invalid_yaml"
    # AND must not produce any issue with detail matching "parse failed at line"
    watchers_dir = tmp_path / ".lore" / "watchers"
    watchers_dir.mkdir(parents=True)
    doctrines_dir = tmp_path / ".lore" / "doctrines"
    doctrines_dir.mkdir(parents=True)
    (watchers_dir / "valid.yaml").write_text(
        "id: valid-watcher\ntitle: Valid\nsummary: s\naction: some-doctrine\n"
    )

    issues = _check_watchers(watchers_dir, doctrines_dir)

    parse_failed_issues = [
        i for i in issues if "parse failed at line" in (i.detail or "")
    ]
    assert parse_failed_issues == [], (
        f"Expected no 'parse failed at line' issues for valid YAML, got: {parse_failed_issues}"
    )


def test_check_watchers_deleted_yaml_invalid_content_no_issue(tmp_path):
    """_check_watchers returns no 'parse failed at line' issue for .yaml.deleted files."""
    # Exercises: lore codex show conceptual-workflows-health
    # .yaml.deleted files must be excluded; specifically no "parse failed at line" detail
    watchers_dir = tmp_path / ".lore" / "watchers"
    watchers_dir.mkdir(parents=True)
    doctrines_dir = tmp_path / ".lore" / "doctrines"
    doctrines_dir.mkdir(parents=True)
    (watchers_dir / "deleted-watcher.yaml.deleted").write_text(
        "id: deleted\ntitle: Deleted\n  broken: : yaml\n"
    )

    issues = _check_watchers(watchers_dir, doctrines_dir)

    parse_failed_issues = [
        i for i in issues if "parse failed at line" in (i.detail or "")
    ]
    assert parse_failed_issues == [], (
        f"Expected no 'parse failed at line' issues for .yaml.deleted, got: {parse_failed_issues}"
    )


def test_check_watchers_invalid_yaml_issue_has_entity_type_watchers(tmp_path):
    """_check_watchers invalid_yaml issue has entity_type='watchers' and detail 'parse failed at line N'."""
    # Exercises: lore codex show conceptual-workflows-health
    # Tests that the new detail format co-exists with correct severity/entity_type
    watchers_dir = tmp_path / ".lore" / "watchers"
    watchers_dir.mkdir(parents=True)
    doctrines_dir = tmp_path / ".lore" / "doctrines"
    doctrines_dir.mkdir(parents=True)
    (watchers_dir / "bad.yaml").write_text("id: bad\ntitle: Bad\n  broken: indented\n")

    issues = _check_watchers(watchers_dir, doctrines_dir)

    invalid_yaml_issues = [i for i in issues if i.check == "invalid_yaml"]
    assert len(invalid_yaml_issues) == 1
    assert invalid_yaml_issues[0].entity_type == "watchers"
    assert invalid_yaml_issues[0].severity == "error"
    # New behavior: detail must use "parse failed at line N" format
    assert "parse failed at line" in invalid_yaml_issues[0].detail, (
        f"Expected 'parse failed at line' in detail, got: {invalid_yaml_issues[0].detail!r}"
    )


def test_check_watchers_invalid_yaml_issue_id_and_detail_format(tmp_path):
    """_check_watchers invalid_yaml issue id is file stem and detail uses 'parse failed at line N'."""
    # Exercises: lore codex show conceptual-workflows-health
    # Both id format and detail format must be correct simultaneously
    watchers_dir = tmp_path / ".lore" / "watchers"
    watchers_dir.mkdir(parents=True)
    doctrines_dir = tmp_path / ".lore" / "doctrines"
    doctrines_dir.mkdir(parents=True)
    (watchers_dir / "on-sprint-start.yaml").write_text(
        "id: on-sprint-start\ntitle: Start\n  broken: indented\n"
    )

    issues = _check_watchers(watchers_dir, doctrines_dir)

    invalid_yaml_issues = [i for i in issues if i.check == "invalid_yaml"]
    assert len(invalid_yaml_issues) == 1
    assert invalid_yaml_issues[0].id == "on-sprint-start"
    assert "parse failed at line" in invalid_yaml_issues[0].detail, (
        f"Expected 'parse failed at line' in detail, got: {invalid_yaml_issues[0].detail!r}"
    )


# ---------------------------------------------------------------------------
# US-015 Unit: HealthIssue.from_dict — round-trip
# ---------------------------------------------------------------------------


def test_health_issue_from_dict_round_trips_all_fields():
    """HealthIssue.from_dict round-trips correctly from a dict representation."""
    original = HealthIssue(
        severity="error",
        entity_type="doctrines",
        id="feat-auth",
        check="broken_knight_ref",
        detail="'senior-engineer' not found (step 2)",
    )
    d = dataclasses.asdict(original)
    reconstructed = HealthIssue.from_dict(d)
    assert reconstructed == original


def test_health_issue_from_dict_warning_round_trips():
    """HealthIssue.from_dict round-trips a warning issue correctly."""
    original = HealthIssue(
        severity="warning",
        entity_type="codex",
        id="solo-doc",
        check="island_node",
        detail="no documents link here",
    )
    d = dataclasses.asdict(original)
    reconstructed = HealthIssue.from_dict(d)
    assert reconstructed == original


def test_health_issue_from_dict_produces_health_issue_instance():
    """HealthIssue.from_dict returns a HealthIssue instance."""
    d = {
        "severity": "error",
        "entity_type": "knights",
        "id": "missing-knight",
        "check": "broken_knight_ref",
        "detail": "knight file not found",
    }
    result = HealthIssue.from_dict(d)
    assert isinstance(result, HealthIssue)


# ---------------------------------------------------------------------------
# US-015 Unit: HealthReport.issues — errors before warnings
# ---------------------------------------------------------------------------


def test_health_report_issues_returns_errors_before_warnings_us015():
    """HealthReport.issues returns errors tuple followed by warnings tuple in that order."""
    error = HealthIssue(
        severity="error",
        entity_type="doctrines",
        id="feat-auth",
        check="broken_knight_ref",
        detail="'senior-engineer' not found (step 2)",
    )
    warning = HealthIssue(
        severity="warning",
        entity_type="codex",
        id="orphan-doc",
        check="island_node",
        detail="no documents link here",
    )
    report = HealthReport(errors=(error,), warnings=(warning,))
    issues = report.issues
    assert issues[0] == error, "First issue must be the error"
    assert issues[1] == warning, "Second issue must be the warning"


def test_health_report_issues_errors_only_no_warnings():
    """HealthReport.issues returns only errors when no warnings exist."""
    error = HealthIssue(
        severity="error",
        entity_type="watchers",
        id="bad-watcher",
        check="invalid_yaml",
        detail="parse failed at line 2",
    )
    report = HealthReport(errors=(error,), warnings=())
    assert report.issues == (error,)


def test_health_report_issues_warnings_only_no_errors():
    """HealthReport.issues returns only warnings when no errors exist."""
    warning = HealthIssue(
        severity="warning",
        entity_type="codex",
        id="solo-doc",
        check="island_node",
        detail="no documents link here",
    )
    report = HealthReport(errors=(), warnings=(warning,))
    assert report.issues == (warning,)


# ---------------------------------------------------------------------------
# US-015 Unit: CLI handler — output format with/without --json
# ---------------------------------------------------------------------------


def test_health_cli_handler_json_flag_output_is_valid_json(tmp_path, monkeypatch):
    """CLI handler: with --json, output is valid JSON parseable by json.loads."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["init"])

    # Plant a broken watcher to produce at least one issue
    watchers_dir = tmp_path / ".lore" / "watchers"
    watchers_dir.mkdir(parents=True, exist_ok=True)
    (watchers_dir / "broken.yaml").write_text(
        "id: broken\ntitle: Broken\nsummary: s\naction: nonexistent-doctrine\n"
    )

    result = runner.invoke(main, ["health", "--json"])

    data = json.loads(result.output)
    assert isinstance(data, dict)
    assert "has_errors" in data
    assert "issues" in data


def test_health_cli_handler_no_json_flag_output_not_json(tmp_path, monkeypatch):
    """CLI handler: without --json, output contains ERROR/WARNING prefix not JSON."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["init"])

    watchers_dir = tmp_path / ".lore" / "watchers"
    watchers_dir.mkdir(parents=True, exist_ok=True)
    (watchers_dir / "broken.yaml").write_text(
        "id: broken\ntitle: Broken\nsummary: s\naction: nonexistent-doctrine\n"
    )

    result = runner.invoke(main, ["health"])

    # Output must contain ERROR or WARNING prefix per severity
    assert "ERROR" in result.output or "WARNING" in result.output, (
        f"Expected 'ERROR' or 'WARNING' in output.\nOutput:\n{result.output}"
    )
    # Output must NOT be parseable as JSON
    try:
        json.loads(result.output)
        raise AssertionError(
            f"Output should not be valid JSON in text mode.\nOutput:\n{result.output}"
        )
    except json.JSONDecodeError:
        pass  # expected


def test_health_cli_handler_no_json_flag_severity_prefix_per_issue(tmp_path, monkeypatch):
    """CLI handler: without --json, each issue line starts with its severity in uppercase."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["init"])

    watchers_dir = tmp_path / ".lore" / "watchers"
    watchers_dir.mkdir(parents=True, exist_ok=True)
    (watchers_dir / "broken.yaml").write_text(
        "id: broken\ntitle: Broken\nsummary: s\naction: nonexistent-doctrine\n"
    )

    result = runner.invoke(main, ["health"])

    issue_lines = [
        line for line in result.output.splitlines()
        if line.startswith("ERROR") or line.startswith("WARNING")
    ]
    assert len(issue_lines) >= 1, (
        f"Expected at least one issue line with ERROR/WARNING prefix.\nOutput:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# US-016: health_check() Python API — no stdout, no file, returns HealthReport
# Exercises: conceptual-workflows-health — Python API contract
# ---------------------------------------------------------------------------


def test_health_check_returns_health_report_instance(lore_dir):
    """health_check returns an instance of HealthReport (not a dict or None)."""
    # Exercises: lore codex show conceptual-workflows-health
    result = health_check(lore_dir, scope=None)
    assert isinstance(result, HealthReport)


def test_health_check_no_stdout_when_called_directly(lore_dir, capsys):
    """health_check produces no stdout output when called as Python API.

    Exercises: lore codex show conceptual-workflows-health
    """
    # Inject an error so the function has something to report internally
    codex_dir = lore_dir / ".lore" / "codex"
    (codex_dir / "broken.md").write_text(
        "---\nid: broken-doc\ntitle: Broken\nsummary: s\nrelated:\n  - nonexistent-id\n---\nBody.\n"
    )

    health_check(lore_dir, scope=["codex"])

    captured = capsys.readouterr()
    assert captured.out == "", f"Expected no stdout, got: {captured.out!r}"


def test_health_check_no_file_side_effect(lore_dir):
    """health_check does not create any files under .lore/codex/transient/ when called directly.

    Exercises: lore codex show conceptual-workflows-health
    """
    transient_dir = lore_dir / ".lore" / "codex" / "transient"

    before = set(transient_dir.glob("health-*.md")) if transient_dir.exists() else set()

    health_check(lore_dir, scope=None)

    after = set(transient_dir.glob("health-*.md")) if transient_dir.exists() else set()
    new_files = after - before
    assert not new_files, f"Expected no new report files, found: {new_files}"


def test_health_check_scope_codex_only_check_codex_runs(lore_dir):
    """health_check with scope=['codex'] runs only _check_codex; no issues from other types.

    Exercises: lore codex show conceptual-workflows-health
    """
    from unittest.mock import patch

    # Inject artifacts error — must NOT appear because scope is ["codex"]
    artifacts_dir = lore_dir / ".lore" / "artifacts"
    (artifacts_dir / "missing-id.md").write_text(
        "---\ntitle: No ID\nsummary: s\n---\nBody.\n"
    )

    with patch("lore.health._check_artifacts") as mock_artifacts, \
         patch("lore.health._check_doctrines") as mock_doctrines, \
         patch("lore.health._check_knights") as mock_knights, \
         patch("lore.health._check_watchers") as mock_watchers:
        mock_artifacts.return_value = []
        mock_doctrines.return_value = []
        mock_knights.return_value = []
        mock_watchers.return_value = []

        health_check(lore_dir, scope=["codex"])

        mock_artifacts.assert_not_called()
        mock_doctrines.assert_not_called()
        mock_knights.assert_not_called()
        mock_watchers.assert_not_called()


def test_health_check_scope_none_same_as_all_five_explicit(lore_dir):
    """health_check scope=None is equivalent to the full _ALL_SCOPES list.

    Updated by US-004: _ALL_SCOPES now includes 'schemas'.
    Exercises: lore codex show conceptual-workflows-health
    """
    # Inject watcher error to produce non-empty results
    watchers_dir = lore_dir / ".lore" / "watchers"
    (watchers_dir / "bad.yaml").write_text(
        "id: bad\ntitle: Bad\nsummary: s\naction: missing-doctrine-us016\n"
    )

    report_none = health_check(lore_dir, scope=None)
    report_all = health_check(
        lore_dir,
        scope=["codex", "artifacts", "doctrines", "knights", "watchers", "schemas"],
    )

    assert report_none.errors == report_all.errors
    assert report_none.warnings == report_all.warnings


# ---------------------------------------------------------------------------
# US-017 Unit: HealthReport — type annotations
# Exercises: conceptual-workflows-health (lore codex show conceptual-workflows-health)
# ---------------------------------------------------------------------------


def test_health_report_errors_field_type_annotation_is_typed_tuple():
    """HealthReport.errors field annotation is tuple[HealthIssue, ...] not bare tuple."""
    # Exercises: lore codex show conceptual-workflows-health
    hints = typing.get_type_hints(HealthReport)
    errors_hint = hints.get("errors")
    # Must be parameterized tuple[HealthIssue, ...], not bare tuple
    assert errors_hint is not tuple, (
        "HealthReport.errors must be annotated as tuple[HealthIssue, ...], not bare tuple. "
        f"Got: {errors_hint!r}"
    )
    assert errors_hint == tuple[HealthIssue, ...], (
        f"HealthReport.errors annotation must be tuple[HealthIssue, ...], got: {errors_hint!r}"
    )


def test_health_report_warnings_field_type_annotation_is_typed_tuple():
    """HealthReport.warnings field annotation is tuple[HealthIssue, ...] not bare tuple."""
    # Exercises: lore codex show conceptual-workflows-health
    hints = typing.get_type_hints(HealthReport)
    warnings_hint = hints.get("warnings")
    assert warnings_hint is not tuple, (
        "HealthReport.warnings must be annotated as tuple[HealthIssue, ...], not bare tuple. "
        f"Got: {warnings_hint!r}"
    )
    assert warnings_hint == tuple[HealthIssue, ...], (
        f"HealthReport.warnings annotation must be tuple[HealthIssue, ...], got: {warnings_hint!r}"
    )


def test_health_report_issues_property_return_type_annotation_is_typed_tuple():
    """HealthReport.issues property return annotation is tuple[HealthIssue, ...] not bare tuple."""
    # Exercises: lore codex show conceptual-workflows-health
    hints = typing.get_type_hints(HealthReport.issues.fget)
    return_hint = hints.get("return")
    assert return_hint is not tuple, (
        "HealthReport.issues must be annotated to return tuple[HealthIssue, ...], not bare tuple. "
        f"Got: {return_hint!r}"
    )
    assert return_hint == tuple[HealthIssue, ...], (
        f"HealthReport.issues return annotation must be tuple[HealthIssue, ...], got: {return_hint!r}"
    )


# ---------------------------------------------------------------------------
# US-018: health_check registered in lore.api.__all__
# Exercises: lore codex show conceptual-workflows-health
# ---------------------------------------------------------------------------


def test_health_check_in_all():
    """'health_check' must appear in lore.api.__all__."""
    # Exercises: lore codex show conceptual-workflows-health
    import lore.api
    assert "health_check" in lore.api.__all__, (
        "'health_check' not found in lore.api.__all__. "
        f"Current __all__: {lore.api.__all__!r}"
    )


def test_health_check_importable_from_lore_api():
    """from lore.api import health_check must succeed and be callable."""
    # Exercises: lore codex show conceptual-workflows-health
    from lore.api import health_check  # noqa: F401
    assert callable(health_check), (
        f"health_check imported from lore.api is not callable: {health_check!r}"
    )


# ---------------------------------------------------------------------------
# US-019: Scan failure isolation — one broken checker does not abort others
# Exercises: lore codex show conceptual-workflows-health
# ---------------------------------------------------------------------------


def test_health_check_scan_failure_issue_fields(lore_dir):
    """health_check emits exactly one scan_failed error with correct fields when a checker raises."""
    # Exercises: lore codex show conceptual-workflows-health
    from unittest.mock import patch

    with patch(
        "lore.health._check_watchers",
        side_effect=RuntimeError("unexpected crash message"),
    ):
        report = health_check(lore_dir, scope=None)

    scan_failed_issues = [i for i in report.errors if i.check == "scan_failed"]
    assert len(scan_failed_issues) == 1, (
        f"Expected exactly one scan_failed issue, got: {scan_failed_issues!r}"
    )
    issue = scan_failed_issues[0]
    assert issue.severity == "error"
    assert issue.entity_type == "watchers"
    assert issue.id == "watchers"
    assert "unexpected crash message" in issue.detail, (
        f"Expected exception message in detail, got: {issue.detail!r}"
    )


def test_health_check_other_checkers_run_when_watchers_raises(lore_dir):
    """health_check still runs all other checkers when _check_watchers raises."""
    # Exercises: lore codex show conceptual-workflows-health
    # Write a codex doc with valid frontmatter so _check_codex produces a warning (island_node).
    codex_dir = lore_dir / ".lore" / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    (codex_dir / "lone-doc.md").write_text(
        "---\nid: lone-doc\ntitle: Lone\nsummary: s\n---\nBody.\n"
    )

    from unittest.mock import patch

    with patch(
        "lore.health._check_watchers",
        side_effect=RuntimeError("boom"),
    ):
        report = health_check(lore_dir, scope=None)

    # codex checker ran → should see an island_node warning for lone-doc
    island_issues = [
        i for i in report.warnings if i.check == "island_node" and i.id == "lone-doc"
    ]
    assert island_issues, (
        "Expected island_node warning from codex checker but none found. "
        f"All issues: {report.issues!r}"
    )


# ---------------------------------------------------------------------------
# US-005 — HealthIssue new fields, JSON serialization, exact message wording
# Workflow: conceptual-workflows-health
# ---------------------------------------------------------------------------


class TestUS005HealthIssueFields:
    """HealthIssue is additively widened with schema_id/rule/pointer."""

    def test_new_fields_default_to_none_for_non_schema_issue(self):
        """conceptual-workflows-health — widening is strictly additive."""
        issue = HealthIssue(
            severity="error",
            entity_type="knights",
            id="pm",
            check="broken_ref",
            detail="x",
        )
        assert issue.schema_id is None
        assert issue.rule is None
        assert issue.pointer is None

    def test_new_fields_assignable_for_schema_issue(self):
        """conceptual-workflows-health — schema issues carry full triple."""
        issue = HealthIssue(
            severity="error",
            entity_type="knight",
            id=".lore/knights/default/feature-implementation/pm.md",
            check="schema",
            detail="Unknown property 'stability' — allowed keys are id, title, summary.",
            schema_id="lore://schemas/knight-frontmatter",
            rule="additionalProperties",
            pointer="/stability",
        )
        assert issue.schema_id == "lore://schemas/knight-frontmatter"
        assert issue.rule == "additionalProperties"
        assert issue.pointer == "/stability"


class TestUS005HealthIssueAsdict:
    """dataclasses.asdict must expose all new fields for every issue."""

    def test_asdict_non_schema_emits_null_extras(self):
        """conceptual-workflows-json-output — keys present, values None."""
        issue = HealthIssue(
            severity="error",
            entity_type="codex",
            id="doc-1",
            check="missing_frontmatter",
            detail="field 'id' absent",
        )
        d = dataclasses.asdict(issue)
        assert "schema_id" in d
        assert "rule" in d
        assert "pointer" in d
        assert d["schema_id"] is None
        assert d["rule"] is None
        assert d["pointer"] is None

    def test_asdict_schema_issue_full_shape(self):
        """conceptual-workflows-json-output — PRD W5 canonical dict shape."""
        issue = HealthIssue(
            severity="error",
            entity_type="knight",
            id=".lore/knights/default/feature-implementation/pm.md",
            check="schema",
            detail="Unknown property 'stability' — allowed keys are id, title, summary.",
            schema_id="lore://schemas/knight-frontmatter",
            rule="additionalProperties",
            pointer="/stability",
        )
        assert dataclasses.asdict(issue) == {
            "severity": "error",
            "entity_type": "knight",
            "id": ".lore/knights/default/feature-implementation/pm.md",
            "check": "schema",
            "detail": "Unknown property 'stability' — allowed keys are id, title, summary.",
            "schema_id": "lore://schemas/knight-frontmatter",
            "rule": "additionalProperties",
            "pointer": "/stability",
        }

    def test_asdict_round_trip_json_safe(self):
        """conceptual-workflows-json-output — asdict output must serialize cleanly."""
        issue = HealthIssue(
            severity="error",
            entity_type="knights",
            id="ghost",
            check="broken_ref",
            detail="x",
        )
        d = dataclasses.asdict(issue)
        serialized = json.loads(json.dumps(d))
        assert serialized["schema_id"] is None
        assert serialized["rule"] is None
        assert serialized["pointer"] is None


class TestUS005SchemaMessageWording:
    """Formatter wording is frozen: em dash, exact punctuation, exact order."""

    def test_additional_properties_message_verbatim(self):
        """conceptual-workflows-health — additionalProperties wording with em dash."""
        import jsonschema

        schema = {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "title": {"type": "string"},
                "summary": {"type": "string"},
            },
            "additionalProperties": False,
        }
        instance = {
            "id": "pm",
            "title": "PM",
            "summary": "s",
            "stability": "experimental",
        }
        validator = jsonschema.Draft202012Validator(schema)
        errors = [e for e in validator.iter_errors(instance) if e.validator == "additionalProperties"]
        assert errors, "Expected an additionalProperties error"

        from lore.schemas import _format_message

        assert (
            _format_message(errors[0])
            == "Unknown property 'stability' — allowed keys are id, title, summary."
        )

    def test_required_message_verbatim(self):
        """conceptual-workflows-doctrine-show — required wording verbatim."""
        import jsonschema

        schema = {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "title": {"type": "string"},
                "summary": {"type": "string"},
            },
            "required": ["id", "title", "summary"],
        }
        instance = {"id": "x", "title": "t"}
        validator = jsonschema.Draft202012Validator(schema)
        errors = [e for e in validator.iter_errors(instance) if e.validator == "required"]
        assert errors

        from lore.schemas import _format_message

        assert _format_message(errors[0]) == "Missing required property 'summary'."


class TestUS005HasErrorsContract:
    """has_errors = any issue with severity == 'error' regardless of check."""

    def test_has_errors_true_for_schema_issue_alone(self):
        """conceptual-workflows-health — schema errors block green (FR-7)."""
        schema_issue = HealthIssue(
            severity="error",
            entity_type="knight",
            id=".lore/knights/default/feature-implementation/pm.md",
            check="schema",
            detail="x",
            schema_id="lore://schemas/knight-frontmatter",
            rule="additionalProperties",
            pointer="/stability",
        )
        report = HealthReport(errors=(schema_issue,), warnings=())
        assert report.has_errors is True

    def test_has_errors_true_for_mixed_schema_and_non_schema_errors(self):
        """conceptual-workflows-health — check value irrelevant to has_errors."""
        schema_issue = HealthIssue(
            severity="error", entity_type="knight", id="x", check="schema",
            detail="x", schema_id="s", rule="r", pointer="/p",
        )
        ref_issue = HealthIssue(
            severity="error", entity_type="knights", id="ghost",
            check="broken_ref", detail="x",
        )
        report = HealthReport(errors=(schema_issue, ref_issue), warnings=())
        assert report.has_errors is True


# ---------------------------------------------------------------------------
# US-008 Red — _write_report Schema validation section
# story: schema-validation-us-008
# workflow: conceptual-workflows-oracle (lore codex show conceptual-workflows-oracle)
# ---------------------------------------------------------------------------


def _schema_issue(kind: str, path: str, rule: str, pointer: str, message: str) -> HealthIssue:
    return HealthIssue(
        severity="error",
        entity_type=kind,
        id=path,
        check="schema",
        detail=message,
        schema_id=f"lore://schemas/{kind}",
        rule=rule,
        pointer=pointer,
    )


def _non_schema_issue() -> HealthIssue:
    return HealthIssue(
        severity="error",
        entity_type="codex",
        id="some-doc",
        check="broken_related_link",
        detail="related ID 'x' does not exist",
    )


def test_us008_write_report_zero_schema_issues_section(tmp_path):
    """US-008: zero schema issues, schemas_ran=True → exact two-line block."""
    codex_dir = tmp_path / ".lore" / "codex"
    report = HealthReport(errors=(), warnings=())
    path = _write_report(report, codex_dir, "2026-04-15T10-00-00", schemas_ran=True)
    text = path.read_text()
    assert "## Schema validation\n\nNo schema errors.\n" in text


def test_us008_write_report_schema_section_multi_kind_exact_format(tmp_path):
    """US-008: multi-kind sorted block verbatim (em dashes, backticks, punctuation)."""
    codex_dir = tmp_path / ".lore" / "codex"
    issues = (
        _schema_issue(
            kind="knight",
            path=".lore/knights/default/feature-implementation/pm.md",
            rule="additionalProperties",
            pointer="/stability",
            message="Unknown property 'stability' — allowed keys are id, title, summary.",
        ),
        _schema_issue(
            kind="doctrine-design-frontmatter",
            path=".lore/doctrines/feature-implementation/feature-implementation.design.md",
            rule="required",
            pointer="/",
            message="Missing required property 'summary'.",
        ),
    )
    report = HealthReport(errors=issues, warnings=())
    path = _write_report(report, codex_dir, "2026-04-15T10-00-00", schemas_ran=True)
    text = path.read_text()

    expected = (
        "## Schema validation\n\n"
        "### doctrine-design-frontmatter\n"
        "- `.lore/doctrines/feature-implementation/feature-implementation.design.md` — "
        "`required` at `/` — Missing required property 'summary'.\n\n"
        "### knight\n"
        "- `.lore/knights/default/feature-implementation/pm.md` — "
        "`additionalProperties` at `/stability` — "
        "Unknown property 'stability' — allowed keys are id, title, summary.\n"
    )
    assert expected in text


def test_us008_write_report_kinds_sorted_alphabetically(tmp_path):
    """US-008: kinds appear in alphabetical order within the Schema validation section."""
    codex_dir = tmp_path / ".lore" / "codex"
    issues = (
        _schema_issue("watcher", ".lore/watchers/w.yaml", "required", "/", "m"),
        _schema_issue("artifact", ".lore/artifacts/a.md", "required", "/", "m"),
        _schema_issue("knight", ".lore/knights/k.md", "required", "/", "m"),
    )
    report = HealthReport(errors=issues, warnings=())
    path = _write_report(report, codex_dir, "2026-04-15T10-00-00", schemas_ran=True)
    text = path.read_text()
    section = text[text.index("## Schema validation"):]
    assert section.index("### artifact") < section.index("### knight") < section.index("### watcher")


def test_us008_write_report_paths_sorted_within_kind(tmp_path):
    """US-008: within a kind, entries are sorted by file path."""
    codex_dir = tmp_path / ".lore" / "codex"
    issues = (
        _schema_issue("knight", ".lore/knights/b.md", "required", "/", "m"),
        _schema_issue("knight", ".lore/knights/a.md", "required", "/", "m"),
        _schema_issue("knight", ".lore/knights/c.md", "required", "/", "m"),
    )
    report = HealthReport(errors=issues, warnings=())
    path = _write_report(report, codex_dir, "2026-04-15T10-00-00", schemas_ran=True)
    text = path.read_text()
    section = text[text.index("## Schema validation"):]
    assert section.index("a.md") < section.index("b.md") < section.index("c.md")


def test_us008_write_report_entry_format_verbatim(tmp_path):
    """US-008: each entry renders exactly as '- `<path>` — `<rule>` at `<pointer>` — <message>'."""
    codex_dir = tmp_path / ".lore" / "codex"
    issue = _schema_issue(
        kind="knight",
        path=".lore/knights/pm.md",
        rule="additionalProperties",
        pointer="/stability",
        message="Unknown property 'stability'.",
    )
    report = HealthReport(errors=(issue,), warnings=())
    path = _write_report(report, codex_dir, "2026-04-15T10-00-00", schemas_ran=True)
    text = path.read_text()
    line = "- `.lore/knights/pm.md` — `additionalProperties` at `/stability` — Unknown property 'stability'."
    assert line in text


def test_us008_write_report_section_omitted_when_schemas_not_run(tmp_path):
    """US-008: section omitted entirely when schemas_ran=False (scope gating)."""
    codex_dir = tmp_path / ".lore" / "codex"
    report = HealthReport(errors=(_non_schema_issue(),), warnings=())
    path = _write_report(report, codex_dir, "2026-04-15T10-00-00", schemas_ran=False)
    text = path.read_text()
    assert "## Schema validation" not in text
    assert "No schema errors." not in text


def test_us008_write_report_section_appended_after_existing_issues_table(tmp_path):
    """US-008: Schema validation section comes AFTER the existing issues table."""
    codex_dir = tmp_path / ".lore" / "codex"
    ref_issue = _non_schema_issue()
    schema_issue = _schema_issue(
        "knight", ".lore/knights/pm.md", "required", "/", "m",
    )
    report = HealthReport(errors=(ref_issue, schema_issue), warnings=())
    path = _write_report(report, codex_dir, "2026-04-15T10-00-00", schemas_ran=True)
    text = path.read_text()
    # The existing issues table contains the markdown header row.
    assert "| Severity | Entity Type | ID | Check | Detail |" in text
    assert "## Schema validation" in text
    assert text.index("| Severity | Entity Type | ID | Check | Detail |") < text.index("## Schema validation")


def test_us008_write_report_zero_schema_issues_section_still_emitted_with_other_issues(tmp_path):
    """US-008: even with non-schema issues, zero-schema zero-case prints 'No schema errors.'."""
    codex_dir = tmp_path / ".lore" / "codex"
    report = HealthReport(errors=(_non_schema_issue(),), warnings=())
    path = _write_report(report, codex_dir, "2026-04-15T10-00-00", schemas_ran=True)
    text = path.read_text()
    assert "## Schema validation\n\nNo schema errors.\n" in text


# ---------------------------------------------------------------------------
# US-009: Python API parity — health_check parity + scan_failed wrapping
# Exercises: lore codex show schema-validation-us-009
#            lore codex show conceptual-workflows-python-api
# ---------------------------------------------------------------------------


def _write_bad_knight(lore_dir):
    knight_dir = lore_dir / ".lore" / "knights"
    knight_dir.mkdir(parents=True, exist_ok=True)
    (knight_dir / "pm.md").write_text(
        "---\n"
        "id: pm\n"
        "title: Product Manager\n"
        "summary: Writes PRDs.\n"
        "stability: x\n"
        "---\n"
        "# Body\n"
    )


def test_us009_health_check_scan_failed_on_schema_load_error(lore_dir):
    """schema-validation-us-009 — load_schema failure surfaces as scan_failed.

    NFR-Reliability contract: a failure to load the authoritative schema must
    NOT silently skip the schema check (false-green). It must propagate as a
    scan_failed HealthIssue whose detail identifies the offending schema.
    """
    _write_bad_knight(lore_dir)

    from lore.health import _check_schemas
    from lore.schemas import _validator_for

    def boom(kind):
        if kind == "knight-frontmatter":
            raise FileNotFoundError("knight-frontmatter resource missing")
        return _validator_for(kind)

    issues = _check_schemas(lore_dir, get_validator=boom)

    scan_failed = [i for i in issues if i.check == "scan_failed"]
    assert scan_failed, (
        f"expected scan_failed issue, got issues: {issues!r}"
    )
    # Spec — unit AC: "scan_failed issue has detail containing the schema id
    # that failed to load" (not merely the exception text). That identifies
    # which authoritative schema the oracle could not load.
    assert any(
        "lore://schemas/knight-frontmatter" in (i.detail or "") for i in scan_failed
    ), (
        "expected 'lore://schemas/knight-frontmatter' in scan_failed detail, "
        f"got: {[i.detail for i in scan_failed]!r}"
    )
    # Original exception message must also be carried through for debuggability.
    assert any(
        "knight-frontmatter resource missing" in (i.detail or "") for i in scan_failed
    )
    # No schema false-green: a schema check that could not load its authoritative
    # schema must not emit check='schema' entries pretending success.
    schema_issues = [i for i in issues if i.check == "schema"]
    assert not any(
        i.schema_id == "lore://schemas/knight-frontmatter" for i in schema_issues
    )


def test_us009_health_check_callable_without_project_root(lore_dir, monkeypatch):
    """schema-validation-us-009 — project_root is optional; defaults to CLI discovery.

    Unit AC: "accepts an optional project_root argument (or uses the same
    discovery as the CLI)". Calling health_check() with no arguments from a
    project root must succeed and return a HealthReport.
    """
    monkeypatch.chdir(lore_dir)
    report = health_check()  # No positional project_root.
    from lore.api import HealthReport as _HR
    assert isinstance(report, _HR)


# ---------------------------------------------------------------------------
# G2 Red — Codex sources layer (US-002, US-003, US-008)
# Exercises:
#   lore codex show codex-sources-us-002 codex-sources-us-003 codex-sources-us-008
# Anchors:
#   conceptual-workflows-health
#   decisions-006-no-seed-content-tests (structural assertions, no seed content)
# ---------------------------------------------------------------------------


def _fm(fields: dict) -> str:
    """Render a YAML frontmatter block for a markdown file.

    Keeps key order stable so tests that grep the payload are predictable.
    """
    import yaml as _yaml

    return "---\n" + _yaml.safe_dump(fields, sort_keys=False) + "---\nBody.\n"


def _make_lore_project(tmp_path):
    """Create a minimal .lore/ skeleton under tmp_path (no seed content).

    Matches the fixture shape used by _check_codex / _check_schemas directly,
    without going through `lore init` — keeps the unit tests hermetic.
    """
    lore = tmp_path / ".lore"
    for d in ("codex", "knights", "doctrines", "artifacts", "watchers"):
        (lore / d).mkdir(parents=True, exist_ok=True)
    (lore / "codex" / "transient").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _write_canonical(project, doc_id: str, related=None):
    """Write a canonical codex doc at .lore/codex/<doc_id>.md with the given id."""
    codex_dir = project / ".lore" / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    fields = {"id": doc_id, "title": doc_id, "summary": "s"}
    if related is not None:
        fields["related"] = list(related)
    path = codex_dir / f"{doc_id}.md"
    path.write_text(_fm(fields))
    return path


def _write_source(project, system: str, src_id: str, related):
    """Write a source doc at .lore/codex/sources/<system>/<src_id>.md."""
    path = project / ".lore" / "codex" / "sources" / system / f"{src_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = {"id": src_id, "title": src_id, "summary": "s", "related": list(related)}
    path.write_text(_fm(fields))
    return path


# --- US-003: _check_codex island-skip + refactor ----------------------------


def test_check_codex_skips_sources_for_islands(tmp_path):
    """codex-sources-us-003 — Unit Scenario 1: island-node skip is source-scoped.

    Given one canonical doc plus three valid sources all pointing at it, zero
    island_node issues are emitted for any of the three source IDs.
    """
    project = _make_lore_project(tmp_path)
    _write_canonical(project, "conceptual-entities-foo")
    for system, src_id in [("jira", "K-1"), ("jira", "K-2"), ("meetings", "2026-04-21")]:
        _write_source(project, system, src_id, related=["conceptual-entities-foo"])

    issues = _check_codex(project / ".lore" / "codex")

    island_hits = [
        i for i in issues
        if i.check == "island_node" and i.id in {"K-1", "K-2", "2026-04-21"}
    ]
    assert island_hits == []


def test_check_codex_canonical_island_still_reported(tmp_path):
    """codex-sources-us-003 — Unit Scenario 2: skip is scoped to source IDs.

    A canonical doc with no inbound references still triggers island_node.
    Proves the skip is source-scoped, not a global island suppression.
    """
    project = _make_lore_project(tmp_path)
    _write_canonical(project, "conceptual-entities-foo")
    _write_canonical(project, "conceptual-foo")  # zero inbound, zero outbound
    _write_source(project, "jira", "K-1", related=["conceptual-entities-foo"])

    issues = _check_codex(project / ".lore" / "codex")

    island = [i for i in issues if i.check == "island_node" and i.id == "conceptual-foo"]
    assert len(island) == 1


def test_check_codex_source_broken_related_link_still_fires(tmp_path):
    """codex-sources-us-003 — Unit Scenario 3: sources ARE in known_ids.

    A source whose related points at a nonexistent id emits exactly one
    broken_related_link issue attributed to the source id. This proves the
    island-skip does NOT exclude sources from the broken-link pass.
    """
    project = _make_lore_project(tmp_path)
    _write_canonical(project, "conceptual-entities-foo")
    _write_source(project, "jira", "K-4", related=["nonexistent-id"])

    issues = _check_codex(project / ".lore" / "codex")

    hits = [i for i in issues if i.check == "broken_related_link" and i.id == "K-4"]
    assert len(hits) == 1


def test_check_codex_handles_missing_sources_dir(tmp_path):
    """codex-sources-us-003 — Unit Scenario 4: absent sources/ is a no-op.

    _check_codex must not raise when .lore/codex/sources/ does not exist and
    must not emit any issue whose id references 'sources'.
    """
    project = _make_lore_project(tmp_path)
    _write_canonical(
        project, "conceptual-entities-foo", related=["conceptual-entities-bar"]
    )
    _write_canonical(project, "conceptual-entities-bar")

    issues = _check_codex(project / ".lore" / "codex")

    assert not any("sources" in (i.id or "") for i in issues)


# --- US-008: canonical_links_to_source error -------------------------------


def test_check_codex_emits_canonical_links_to_source(tmp_path):
    """codex-sources-us-008 — Unit Scenario 1: canonical back-link is an error.

    A canonical doc whose related names a source id emits exactly one
    canonical_links_to_source error with severity=error, id=canonical id,
    and detail naming the offending source id.
    """
    project = _make_lore_project(tmp_path)
    _write_source(project, "jira", "KONE-23335", related=["conceptual-entities-foo"])
    _write_canonical(
        project, "conceptual-entities-foo", related=["KONE-23335"]
    )  # illegal back-link

    issues = _check_codex(project / ".lore" / "codex")

    hits = [i for i in issues if i.check == "canonical_links_to_source"]
    assert len(hits) == 1
    assert hits[0].severity == "error"
    assert hits[0].entity_type == "codex"
    assert hits[0].id == "conceptual-entities-foo"
    assert "KONE-23335" in (hits[0].detail or "")


def test_check_codex_source_to_source_link_is_ok(tmp_path):
    """codex-sources-us-008 — Unit Scenario 2: source-to-source is permitted."""
    project = _make_lore_project(tmp_path)
    _write_canonical(project, "conceptual-entities-foo")
    _write_source(project, "jira", "A", related=["conceptual-entities-foo", "B"])
    _write_source(project, "jira", "B", related=["conceptual-entities-foo"])

    issues = _check_codex(project / ".lore" / "codex")

    assert [i for i in issues if i.check == "canonical_links_to_source"] == []


def test_check_codex_broken_related_link_not_reclassified(tmp_path):
    """codex-sources-us-008 — Unit Scenario 3: classification is preserved.

    A canonical doc linking to a non-existent id stays broken_related_link.
    The new check must NOT swallow that case (no source with that id exists).
    """
    project = _make_lore_project(tmp_path)
    _write_canonical(
        project, "conceptual-entities-foo", related=["nonexistent-id"]
    )

    issues = _check_codex(project / ".lore" / "codex")

    broken = [i for i in issues if i.check == "broken_related_link"]
    ctls = [i for i in issues if i.check == "canonical_links_to_source"]
    assert len(broken) == 1
    assert ctls == []


def test_check_codex_canonical_links_to_source_one_per_pair(tmp_path):
    """codex-sources-us-008 — Unit Scenario 4: one issue per offending canonical.

    Two canonical docs that both back-link to the same source id produce two
    distinct canonical_links_to_source issues, one per canonical doc.
    """
    project = _make_lore_project(tmp_path)
    _write_source(project, "jira", "K-1", related=["conceptual-entities-foo"])
    _write_canonical(project, "conceptual-entities-foo", related=["K-1"])
    _write_canonical(project, "conceptual-entities-bar", related=["K-1"])

    issues = _check_codex(project / ".lore" / "codex")

    hits = [i for i in issues if i.check == "canonical_links_to_source"]
    assert {h.id for h in hits} == {
        "conceptual-entities-foo",
        "conceptual-entities-bar",
    }
    assert len(hits) == 2


# --- US-002: _check_schemas per-file dispatch to codex-source schema --------


def test_check_schemas_dispatches_sources_to_source_schema(tmp_path):
    """codex-sources-us-002 — Unit: files under sources/ route to codex-source schema.

    A source with empty `related: []` must fail the codex-source-frontmatter
    schema with rule=minItems, pointer=/related, entity_type=codex-source,
    schema_id=lore://schemas/codex-source-frontmatter.
    """
    from lore.health import _check_schemas

    project = _make_lore_project(tmp_path)
    _write_canonical(project, "conceptual-entities-foo")
    bad_source = project / ".lore" / "codex" / "sources" / "jira" / "KONE-23335.md"
    bad_source.parent.mkdir(parents=True, exist_ok=True)
    bad_source.write_text(
        _fm({"id": "KONE-23335", "title": "T", "summary": "S", "related": []})
    )

    issues = _check_schemas(project)

    hits = [i for i in issues if i.id.endswith("KONE-23335.md")]
    assert len(hits) == 1
    assert hits[0].entity_type == "codex-source"
    assert hits[0].schema_id == "lore://schemas/codex-source-frontmatter"
    assert hits[0].rule == "minItems"
    assert hits[0].pointer == "/related"


def test_check_schemas_canonical_codex_unaffected_by_sources(tmp_path):
    """codex-sources-us-002 — Unit: canonical files still use codex-frontmatter.

    A clean project whose canonical docs reference each other and whose lone
    source points at a canonical id must produce zero schema issues.
    """
    from lore.health import _check_schemas

    project = _make_lore_project(tmp_path)
    _write_canonical(
        project,
        "conceptual-entities-foo",
        related=["conceptual-entities-bar"],
    )
    _write_canonical(project, "conceptual-entities-bar")
    _write_source(project, "jira", "K-1", related=["conceptual-entities-foo"])

    assert _check_schemas(project) == []


def test_check_schemas_valid_source_file_produces_no_issue(tmp_path):
    """codex-sources-us-002 — Unit: a well-formed source yields zero issues."""
    from lore.health import _check_schemas

    project = _make_lore_project(tmp_path)
    _write_canonical(project, "conceptual-entities-foo")
    _write_source(project, "jira", "K-1", related=["conceptual-entities-foo"])

    issues = [i for i in _check_schemas(project) if "sources/jira/K-1.md" in i.id]
    assert issues == []


def test_check_schemas_sources_override_reports_scan_failure_loudly(
    tmp_path, monkeypatch
):
    """codex-sources-us-002 — Unit: sources override init failure surfaces loudly.

    When the codex-source-frontmatter validator resolution raises, _check_schemas
    must emit a HealthIssue(check='scan_failed', entity_type='codex-source',
    schema_id='lore://schemas/codex-source-frontmatter') whose detail carries
    the exception message. Post G2 the sources/* override resolves through the
    project-aware seam `health.project_get_validator`, so the boom is injected
    there (the behavior contract is unchanged; only the seam moved).
    """
    import lore.health as health

    def boom(kind, project_root):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(health, "project_get_validator", boom, raising=False)

    project = _make_lore_project(tmp_path)
    issues = health._check_schemas(project)

    hit = [
        i for i in issues
        if i.check == "scan_failed" and i.entity_type == "codex-source"
    ]
    assert len(hit) == 1
    assert hit[0].schema_id == "lore://schemas/codex-source-frontmatter"
    assert "kaboom" in (hit[0].detail or "")


def test_frontmatter_schema_kinds_includes_codex_source():
    """codex-sources-us-002 — Unit: _FRONTMATTER_SCHEMA_KINDS covers source kind.

    Ensures _load_schema_payload's frontmatter-aware branch applies to source
    files (they carry frontmatter, not top-level YAML).
    """
    from lore.health import _FRONTMATTER_SCHEMA_KINDS

    assert "codex-source-frontmatter" in _FRONTMATTER_SCHEMA_KINDS


# ===========================================================================
# US-005 — _check_glossary + --scope glossary plumbing
# Spec: glossary-us-005 (lore codex show glossary-us-005)
# Workflow: conceptual-workflows-health, conceptual-workflows-glossary
#
# Tests the new lore.health._check_glossary helper, the extended _ALL_SCOPES
# tuple, the _SCHEMA_KINDS row for the glossary kind, and CLI --scope wiring.
# Import-failure counts as red until US-005 Green lands the implementation.
# ===========================================================================


def _write_glossary_yaml(project_dir: Path, content: str) -> Path:
    """Write the glossary YAML at the canonical path under .lore/codex/."""
    target = project_dir / ".lore" / "codex" / "glossary.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def _seed_codex_doc_for_health(
    project_dir: Path,
    doc_id: str,
    *,
    body: str = "",
    binds: list[str] | None = None,
    related: list[str] | None = None,
) -> Path:
    """Write a codex doc with frontmatter + body under .lore/codex/<doc_id>.md.

    Optional `binds` / `related` keywords add the corresponding frontmatter
    blocks (per Tech Spec § "Test Conventions" for health-bindings-glossary).
    Pass `binds=[]` to emit an explicit empty list.
    """
    codex_dir = project_dir / ".lore" / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    fields: dict = {"id": doc_id, "title": doc_id, "summary": "s"}
    if binds is not None:
        fields["binds"] = list(binds)
    if related is not None:
        fields["related"] = list(related)
    fm = _fm(fields)
    # _fm appends a default body — replace it with the requested body.
    fm = fm.replace("Body.", body)
    path = codex_dir / f"{doc_id}.md"
    path.write_text(fm, encoding="utf-8")
    return path


def test_check_glossary_empty_items_no_issues(tmp_path):
    """_check_glossary on `items: []` produces no issues (Unit row 7)."""
    from lore.health import _check_glossary

    project = _make_lore_project(tmp_path)
    _write_glossary_yaml(project, "items: []\n")
    assert _check_glossary(project) == []


def test_check_glossary_schema_violation_emits_one_schema_error(tmp_path):
    """Schema violation surfaces a single schema HealthIssue with all fields (Unit row 8)."""
    from lore.health import _check_glossary

    project = _make_lore_project(tmp_path)
    _write_glossary_yaml(project, "items:\n  - keyword: Mission\n")  # missing definition
    issues = _check_glossary(project)
    schema_errors = [i for i in issues if i.check == "schema"]
    assert len(schema_errors) == 1
    err = schema_errors[0]
    assert err.severity == "error"
    assert err.entity_type == "glossary"
    assert err.schema_id == "lore://schemas/glossary"
    assert err.rule == "required"
    assert err.pointer is not None


def test_check_glossary_schema_failure_short_circuits_intra_checks(tmp_path):
    """Schema violation suppresses intra-glossary checks for that file (Unit row 9)."""
    from lore.health import _check_glossary

    project = _make_lore_project(tmp_path)
    # Two items, both missing required `definition` AND duplicating keyword.
    _write_glossary_yaml(
        project, "items:\n  - keyword: Mission\n  - keyword: mission\n"
    )
    issues = _check_glossary(project)
    assert all(i.check == "schema" for i in issues)
    assert not any(i.check == "duplicate_keyword" for i in issues)


def test_check_glossary_duplicate_keyword_error(tmp_path):
    """Two items sharing a casefolded keyword emit one duplicate_keyword error (Unit row 10)."""
    from lore.health import _check_glossary

    project = _make_lore_project(tmp_path)
    _write_glossary_yaml(
        project,
        "items:\n"
        "  - keyword: Mission\n    definition: First.\n"
        "  - keyword: mission\n    definition: Second.\n",
    )
    issues = _check_glossary(project)
    dup = [i for i in issues if i.check == "duplicate_keyword"]
    assert len(dup) == 1
    assert dup[0].severity == "error"
    assert dup[0].entity_type == "glossary"
    assert dup[0].id == ".lore/codex/glossary.yaml"
    assert dup[0].detail == "'mission' appears in items[0] and items[1]"


def test_check_glossary_alias_keyword_collision_warning(tmp_path):
    """Alias colliding with another item's keyword emits one warning (Unit row 11)."""
    from lore.health import _check_glossary

    project = _make_lore_project(tmp_path)
    _write_glossary_yaml(
        project,
        "items:\n"
        "  - keyword: Quest\n    definition: g\n    aliases: [Mission]\n"
        "  - keyword: Mission\n    definition: u\n",
    )
    issues = _check_glossary(project)
    coll = [i for i in issues if i.check == "alias_keyword_collision"]
    assert len(coll) == 1
    assert coll[0].severity == "warning"
    assert coll[0].entity_type == "glossary"
    assert coll[0].detail == "alias 'mission' on 'Quest' collides with keyword 'Mission'"


def test_check_glossary_do_not_use_collision_error(tmp_path):
    """do_not_use colliding with any keyword/alias emits one error (Unit row 12)."""
    from lore.health import _check_glossary

    project = _make_lore_project(tmp_path)
    _write_glossary_yaml(
        project,
        "items:\n"
        "  - keyword: Knight\n    definition: agent persona.\n    do_not_use: [Mission]\n"
        "  - keyword: Mission\n    definition: unit of work.\n",
    )
    issues = _check_glossary(project)
    dnu = [i for i in issues if i.check == "do_not_use_collision"]
    assert len(dnu) == 1
    assert dnu[0].severity == "error"
    assert dnu[0].entity_type == "glossary"
    assert dnu[0].detail == (
        "'mission' in do_not_use of 'Knight' collides with keyword/alias 'Mission'"
    )


def test_health_scope_choice_includes_glossary(tmp_path, monkeypatch):
    """`--scope glossary` is accepted by Click — no Invalid value error (Unit row 15a, FR-22)."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["init"])
    res = runner.invoke(main, ["health", "--scope", "glossary"])
    combined = res.output + (res.stderr if res.stderr else "")
    assert "Invalid value" not in combined


def test_health_combined_scope_codex_glossary_accepted(tmp_path, monkeypatch):
    """`--scope codex glossary` is accepted (multi-value per ADR-012, Unit row 15b).

    Today both tokens fail validation in different ways: `glossary` is rejected
    as an invalid choice when alone, and as an unexpected extra argument when
    paired with `codex`. After Green, the multi-value `--scope` accepts both
    tokens cleanly with exit code 0 or 1 (depending on project state) — never
    a Click usage-error 2.
    """
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["init"])
    res = runner.invoke(main, ["health", "--scope", "codex", "glossary"])
    combined = res.output + (res.stderr if res.stderr else "")
    assert "Invalid value" not in combined
    assert "unexpected extra argument" not in combined.lower()
    # Click usage errors exit with code 2; a clean health invocation exits 0/1.
    assert res.exit_code in (0, 1), (res.exit_code, combined)


def test_health_unknown_scope_lists_glossary_in_valid(tmp_path, monkeypatch):
    """Unknown scope error message lists `glossary` among valid tokens (Unit row 16)."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["init"])
    res = runner.invoke(main, ["health", "--scope", "nonsense"])
    err = res.stderr if res.stderr else res.output
    assert "glossary" in err
    assert res.exit_code != 0


def test_all_scopes_contains_glossary():
    """`_ALL_SCOPES` contains the literal `glossary` token (Unit row 17, FR-22)."""
    from lore.health import _ALL_SCOPES

    assert "glossary" in _ALL_SCOPES


def test_schema_kinds_contains_glossary_row():
    """`_SCHEMA_KINDS` contains the glossary row (Unit row 18, Tech Spec Health Glob Wiring)."""
    from lore.health import _SCHEMA_KINDS

    assert ("glossary", "glossary", "codex", "glossary.yaml") in _SCHEMA_KINDS


# ===========================================================================
# US-001 — Scope vocabulary unit tests (health-bindings-glossary)
# Workflow: conceptual-workflows-health
# ===========================================================================


def test_all_scopes_contains_bindings():
    """US-001 unit — `_ALL_SCOPES` contains `bindings`; total token count is 9 (US-006 added rites)."""
    from lore.health import _ALL_SCOPES

    assert "bindings" in _ALL_SCOPES
    assert len(_ALL_SCOPES) == 9


def test_health_check_scope_bindings_only_routes_to_check_bindings(tmp_path):
    """US-001 unit — `scope=["bindings"]` invokes `_check_bindings` only.

    Seeds both a binding miss (would fire `_check_bindings`) and a broken
    related link (would fire `_check_codex`). Asserts only the bindings row
    appears — proves the dispatcher routes the `"bindings"` token to
    `_check_bindings` and does NOT bleed into the codex checker.
    """
    from lore.health import health_check

    project = _make_lore_project(tmp_path)
    # Doc that exercises _check_codex (broken_related_link) — must NOT surface
    # under scope=["bindings"].
    _seed_codex_doc_for_health(project, "entry-a", related=["nonexistent"])
    # Doc that exercises _check_bindings (dead_binding) — MUST surface.
    _seed_codex_doc_for_health(project, "entry-b", binds=["src/missing.py"])

    report = health_check(project, scope=["bindings"])
    checks = {i.check for i in report.issues}

    assert "dead_binding" in checks
    assert "broken_related_link" not in checks  # codex scope NOT routed


def test_health_check_scope_bindings_and_codex_routes_both(tmp_path):
    """US-001 unit — `scope=["bindings", "codex"]` routes both checkers exactly once."""
    from lore.health import health_check

    project = _make_lore_project(tmp_path)
    _seed_codex_doc_for_health(project, "entry-a", related=["nonexistent"])
    _seed_codex_doc_for_health(project, "entry-b", binds=["src/missing.py"])

    report = health_check(project, scope=["bindings", "codex"])
    checks = {i.check for i in report.issues}

    assert "dead_binding" in checks
    assert "broken_related_link" in checks


# ===========================================================================
# US-002 — `_check_bindings` literal-path branch
# Workflow: conceptual-workflows-health
# ===========================================================================


class TestCheckBindingsLiteral:
    """Unit coverage for the literal half of `health._check_bindings` (US-002)."""

    def test_existing_literal_silent(self, tmp_path):
        """Literal pointing at an on-disk file emits zero rows."""
        from lore.health import _check_bindings

        project = _make_lore_project(tmp_path)
        (project / "existing").mkdir()
        (project / "existing" / "file.py").write_text("")
        _seed_codex_doc_for_health(
            project, "entry-a", binds=["existing/file.py"]
        )
        assert _check_bindings(project) == []

    def test_missing_literal_one_issue(self, tmp_path):
        """Missing literal emits exactly one HealthIssue with the exact field shape."""
        from lore.health import _check_bindings

        project = _make_lore_project(tmp_path)
        _seed_codex_doc_for_health(project, "entry-a", binds=["missing.py"])

        issues = _check_bindings(project)

        assert issues == [HealthIssue(
            severity="error",
            entity_type="codex",
            id="entry-a",
            check="dead_binding",
            detail='"missing.py" — file not found',
            schema_id=None,
            rule=None,
            pointer=None,
        )]

    def test_two_literals_preserve_declaration_order(self, tmp_path):
        """Two literals in one entry emit two rows in declaration order."""
        from lore.health import _check_bindings

        project = _make_lore_project(tmp_path)
        _seed_codex_doc_for_health(
            project,
            "entry-a",
            binds=["a-missing.py", "b-missing.py"],
        )

        issues = _check_bindings(project)

        assert [i.detail for i in issues] == [
            '"a-missing.py" — file not found',
            '"b-missing.py" — file not found',
        ]

    def test_symlink_target_outside_project_root(self, tmp_path):
        """Symlink whose target resolves outside project_root → "resolves outside project root"."""
        from lore.health import _check_bindings

        project = _make_lore_project(tmp_path)
        # Stage the symlink target as a sibling of the project root so
        # Path.resolve() lands outside project_root.resolve().
        outside_root = tmp_path.parent / "outside_repo"
        outside_root.mkdir(exist_ok=True)
        target = outside_root / "target.py"
        target.write_text("")
        try:
            (project / "src").mkdir()
            (project / "src" / "escape.py").symlink_to(target)
            _seed_codex_doc_for_health(
                project, "entry-a", binds=["src/escape.py"]
            )

            issues = _check_bindings(project)

            assert len(issues) == 1
            assert issues[0].check == "dead_binding"
            assert issues[0].detail.endswith("— resolves outside project root")
        finally:
            if target.exists():
                target.unlink()
            if outside_root.exists():
                outside_root.rmdir()

    def test_absent_or_empty_binds_silent(self, tmp_path):
        """Entries with `binds:` absent or `[]` produce no rows."""
        from lore.health import _check_bindings

        project = _make_lore_project(tmp_path)
        _seed_codex_doc_for_health(project, "no-binds")  # no binds key
        _seed_codex_doc_for_health(project, "empty-binds", binds=[])

        assert _check_bindings(project) == []

    def test_empty_codex_index_no_crash(self, tmp_path):
        """Empty `_load_codex_binds_index` mapping → `[]` (no crash, no codex docs)."""
        from lore.health import _check_bindings

        project = _make_lore_project(tmp_path)
        # No codex docs seeded.
        assert _check_bindings(project) == []

    def test_sorted_by_id_then_declaration_order(self, tmp_path):
        """Rows sorted by codex id ASC; within an entry, declaration order preserved."""
        from lore.health import _check_bindings

        project = _make_lore_project(tmp_path)
        _seed_codex_doc_for_health(
            project, "z-entry", binds=["z1.py", "z2.py"]
        )
        _seed_codex_doc_for_health(
            project, "a-entry", binds=["a1.py", "a2.py"]
        )

        issues = _check_bindings(project)

        assert [i.id for i in issues] == [
            "a-entry",
            "a-entry",
            "z-entry",
            "z-entry",
        ]
        assert [i.detail for i in issues] == [
            '"a1.py" — file not found',
            '"a2.py" — file not found',
            '"z1.py" — file not found',
            '"z2.py" — file not found',
        ]

    def test_literal_directory_is_silent(self, tmp_path):
        """Literal that resolves to a directory is silent (Path.exists True for dirs)."""
        from lore.health import _check_bindings

        project = _make_lore_project(tmp_path)
        (project / "src" / "lore").mkdir(parents=True)  # directory exists
        _seed_codex_doc_for_health(project, "entry-a", binds=["src/lore"])

        assert _check_bindings(project) == []


# ===========================================================================
# US-003 — `_check_bindings` glob branch + `_walk_repo_files` helper
# Workflow: conceptual-workflows-health
# Workflow: conceptual-workflows-impacts (token classification, glob semantics)
# ===========================================================================


class TestCheckBindingsGlob:
    """Unit coverage for the glob half of `health._check_bindings` (US-003)."""

    def test_glob_no_matches_one_warning(self, tmp_path):
        """Zero-match glob emits one HealthIssue with exact warning shape (FR-13)."""
        from lore.health import _check_bindings

        project = _make_lore_project(tmp_path)
        _seed_codex_doc_for_health(
            project, "entry-a", binds=["src/missing/**/*.py"]
        )

        issues = _check_bindings(project)

        assert issues == [HealthIssue(
            severity="warning",
            entity_type="codex",
            id="entry-a",
            check="empty_glob_binding",
            detail='"src/missing/**/*.py" — pattern matches zero files',
            schema_id=None,
            rule=None,
            pointer=None,
        )]

    def test_glob_with_match_silent(self, tmp_path):
        """Glob with at least one match emits zero rows for THAT entry (FR-14).

        Paired with a sibling zero-match glob: a no-op glob branch would also
        suppress the warning, so the test fails red until the branch is wired.
        """
        from lore.health import _check_bindings

        project = _make_lore_project(tmp_path)
        (project / "src" / "lore").mkdir(parents=True)
        (project / "src" / "lore" / "cli.py").write_text("")
        _seed_codex_doc_for_health(project, "entry-a", binds=["src/lore/*.py"])
        _seed_codex_doc_for_health(project, "entry-b", binds=["nowhere/**/*.py"])

        issues = _check_bindings(project)

        # entry-a's glob matched → no row.
        assert not any(i.id == "entry-a" for i in issues)
        # entry-b's glob did NOT match → exactly one warning row.
        entry_b = [i for i in issues if i.id == "entry-b"]
        assert len(entry_b) == 1
        assert entry_b[0].check == "empty_glob_binding"
        assert entry_b[0].severity == "warning"

    @pytest.mark.parametrize("binding", [
        "with*star.py",
        "with?qmark.py",
        "with[ab].py",
    ])
    def test_classifier_routes_glob_chars_to_glob_branch(self, tmp_path, binding):
        """Strings containing `*`, `?`, or `[` route to glob branch → empty_glob_binding (FR-7).

        The literal-vs-dead branch is already covered by US-002 tests; this
        parametrize locks ONLY the new glob-routing rule introduced in US-003.
        """
        from lore.health import _check_bindings

        project = _make_lore_project(tmp_path)
        _seed_codex_doc_for_health(project, "entry-a", binds=[binding])

        issues = _check_bindings(project)

        assert len(issues) == 1
        assert issues[0].check == "empty_glob_binding"

    def test_literals_only_skips_walk(self, tmp_path, monkeypatch):
        """Literal-only entry never invokes `_walk_repo_files` (NFR-Performance lazy)."""
        from lore.health import _check_bindings

        project = _make_lore_project(tmp_path)
        _seed_codex_doc_for_health(
            project, "entry-a", binds=["missing-literal.py"]
        )
        calls = {"n": 0}
        real = lore.health._walk_repo_files

        def wrapper(p):
            calls["n"] += 1
            return real(p)

        monkeypatch.setattr(lore.health, "_walk_repo_files", wrapper)
        _check_bindings(project)
        assert calls["n"] == 0  # NEVER walked

    def test_multiple_globs_single_walk(self, tmp_path, monkeypatch):
        """Many globs share the walk: `_walk_repo_files` invoked exactly once per call."""
        from lore.health import _check_bindings

        project = _make_lore_project(tmp_path)
        _seed_codex_doc_for_health(
            project,
            "entry-a",
            binds=["a/**/*.py", "b/**/*.py", "c/**/*.py"],
        )
        calls = {"n": 0}
        real = lore.health._walk_repo_files

        def wrapper(p):
            calls["n"] += 1
            return real(p)

        monkeypatch.setattr(lore.health, "_walk_repo_files", wrapper)
        _check_bindings(project)
        assert calls["n"] == 1


class TestWalkRepoFiles:
    """Unit coverage for `health._walk_repo_files` (US-003 helper)."""

    def test_skips_excluded_dirs(self, tmp_path):
        """Walk excludes `.git/`, `.lore/`, `node_modules/`, `__pycache__/`."""
        from lore.health import _walk_repo_files

        project = _make_lore_project(tmp_path)
        for skip in (".git", ".lore", "node_modules", "__pycache__"):
            (project / skip).mkdir(exist_ok=True)
            (project / skip / "file.py").write_text("")
        (project / "src").mkdir()
        (project / "src" / "visible.py").write_text("")

        paths = _walk_repo_files(project)

        assert "src/visible.py" in paths
        for skip in (".git", ".lore", "node_modules", "__pycache__"):
            assert not any(p.startswith(skip + "/") for p in paths)
            assert not any(p == f"{skip}/file.py" for p in paths)

    def test_drops_symlink_escapers(self, tmp_path):
        """Symlink whose target resolves outside `project_root.resolve()` is dropped (NFR-Security)."""
        from lore.health import _walk_repo_files

        project = _make_lore_project(tmp_path)
        outside = tmp_path.parent / "outside_repo_walk"
        outside.mkdir(exist_ok=True)
        target = outside / "target.py"
        target.write_text("")
        try:
            (project / "src").mkdir()
            (project / "src" / "escape.py").symlink_to(target)

            paths = _walk_repo_files(project)

            assert "src/escape.py" not in paths
        finally:
            if target.exists():
                target.unlink()
            if outside.exists():
                outside.rmdir()

    def test_keeps_symlinks_inside_repo(self, tmp_path):
        """Symlink whose target resolves inside `project_root.resolve()` is included."""
        from lore.health import _walk_repo_files

        project = _make_lore_project(tmp_path)
        (project / "src").mkdir()
        (project / "src" / "real.py").write_text("")
        (project / "src" / "alias.py").symlink_to(project / "src" / "real.py")

        paths = _walk_repo_files(project)

        assert "src/alias.py" in paths
        assert "src/real.py" in paths

    def test_permission_error_skips_subtree(self, tmp_path, monkeypatch):
        """`PermissionError` on subdir does NOT abort walk; siblings continue (NFR-Reliability)."""
        from lore.health import _walk_repo_files

        project = _make_lore_project(tmp_path)
        (project / "src").mkdir()
        (project / "src" / "visible.py").write_text("")
        (project / "forbidden").mkdir()
        (project / "forbidden" / "hidden.py").write_text("")

        real_iterdir = pathlib.Path.iterdir

        def fake_iterdir(self):
            if self.name == "forbidden":
                raise PermissionError("simulated")
            return real_iterdir(self)

        monkeypatch.setattr(pathlib.Path, "iterdir", fake_iterdir)

        paths = _walk_repo_files(project)

        assert "src/visible.py" in paths  # sibling continued
        assert not any(p.startswith("forbidden/") for p in paths)

    def test_returns_posix_paths(self, tmp_path):
        """All returned paths use POSIX separators regardless of platform."""
        from lore.health import _walk_repo_files

        project = _make_lore_project(tmp_path)
        (project / "a" / "b").mkdir(parents=True)
        (project / "a" / "b" / "c.py").write_text("")

        paths = _walk_repo_files(project)

        assert "a/b/c.py" in paths
        for p in paths:
            assert "\\" not in p

    def test_sorted_output(self, tmp_path):
        """Returned list is sorted ascending."""
        from lore.health import _walk_repo_files

        project = _make_lore_project(tmp_path)
        (project / "z.py").write_text("")
        (project / "a.py").write_text("")
        (project / "m.py").write_text("")

        paths = _walk_repo_files(project)

        assert paths == sorted(paths)


# ===========================================================================
# US-004 — envelope shape + exit-code partition + scan_failed envelope
# Workflow: conceptual-workflows-health (lore codex show conceptual-workflows-health)
# ===========================================================================


class TestCheckBindingsEnvelope:
    """Unit envelope/exit-code/scan_failed coverage for `_check_bindings` (US-004)."""

    def test_check_bindings_rows_null_schema_fields(self, tmp_path):
        """US-004 unit — every row from `_check_bindings` has null schema_id/rule/pointer."""
        from lore.health import _check_bindings

        project = _make_lore_project(tmp_path)
        _seed_codex_doc_for_health(project, "dead-one", binds=["src/missing.py"])
        _seed_codex_doc_for_health(
            project, "empty-one", binds=["src/no-such/**/*.py"]
        )
        issues = _check_bindings(project)
        assert issues, "expected at least one issue for the seeded project"
        for issue in issues:
            assert issue.schema_id is None
            assert issue.rule is None
            assert issue.pointer is None

    def test_check_bindings_severities(self, tmp_path):
        """US-004 unit — `dead_binding` severity error; `empty_glob_binding` severity warning."""
        from lore.health import _check_bindings

        project = _make_lore_project(tmp_path)
        _seed_codex_doc_for_health(project, "a", binds=["src/missing.py"])
        _seed_codex_doc_for_health(project, "b", binds=["src/no-such/**/*.py"])
        by_check = {i.check: i for i in _check_bindings(project)}
        assert by_check["dead_binding"].severity == "error"
        assert by_check["empty_glob_binding"].severity == "warning"

    def test_empty_glob_binding_not_escalated(self):
        """US-004 unit — `empty_glob_binding` is NOT in `_ESCALATED_WARNING_CHECKS`.

        If it were, warnings-only runs would flip to exit 1 (regression guard
        on FR-27 isolation of empty_glob_binding).
        """
        from lore.health import _ESCALATED_WARNING_CHECKS

        assert "empty_glob_binding" not in _ESCALATED_WARNING_CHECKS


    def test_health_check_warnings_only_has_errors_false(self, tmp_path):
        """US-004 unit — warnings-only bindings run keeps `has_errors` False."""
        project = _make_lore_project(tmp_path)
        _seed_codex_doc_for_health(project, "a", binds=["src/no-such/**/*.py"])
        report = health_check(project, scope=["bindings"])
        assert report.has_errors is False

    def test_health_check_dead_binding_has_errors_true(self, tmp_path):
        """US-004 unit — at least one `dead_binding` flips `has_errors` True."""
        project = _make_lore_project(tmp_path)
        _seed_codex_doc_for_health(project, "a", binds=["src/missing.py"])
        report = health_check(project, scope=["bindings"])
        assert report.has_errors is True

    def test_health_check_bindings_crash_emits_scan_failed(self, tmp_path, monkeypatch):
        """US-004 unit — `_check_bindings` raise → one scan_failed row; other scopes survive."""
        project = _make_lore_project(tmp_path)
        _seed_codex_doc_for_health(
            project, "entry-broken", related=["nonexistent"]
        )

        def _boom(_p):
            raise RuntimeError("boom")

        monkeypatch.setattr(lore.health, "_check_bindings", _boom)
        report = health_check(project, scope=["bindings", "codex"])
        scan_failed = [i for i in report.issues if i.check == "scan_failed"]
        assert len(scan_failed) == 1
        row = scan_failed[0]
        assert row.entity_type == "bindings"
        assert row.id == "bindings"
        assert row.severity == "error"
        assert "boom" in row.detail
        assert row.schema_id is None
        assert row.rule is None
        assert row.pointer is None

        # codex scope still ran despite the bindings crash.
        related = [i for i in report.issues if i.check == "broken_related_link"]
        assert len(related) == 1


class TestCliHealthExitCodeFromHasErrors:
    """CLI regression guard — exit code mirrors `report.has_errors` (US-004)."""

    def test_cli_health_warnings_only_exit_zero(self, tmp_path, monkeypatch):
        """US-004 unit — warnings-only bindings invocation through the CLI exits 0."""
        monkeypatch.chdir(tmp_path)
        CliRunner().invoke(main, ["init"])
        _seed_codex_doc_for_health(tmp_path, "a", binds=["src/no-such/**/*.py"])
        res = CliRunner().invoke(main, ["health", "--scope", "bindings"])
        assert res.exit_code == 0, res.output

    def test_cli_health_dead_binding_exit_one(self, tmp_path, monkeypatch):
        """US-004 unit — one dead_binding flips CLI exit code to 1."""
        monkeypatch.chdir(tmp_path)
        CliRunner().invoke(main, ["init"])
        _seed_codex_doc_for_health(tmp_path, "a", binds=["src/no-such/**/*.py"])
        _seed_codex_doc_for_health(tmp_path, "b", binds=["src/missing.py"])
        res = CliRunner().invoke(main, ["health", "--scope", "bindings"])
        assert res.exit_code == 1, res.output


# ===========================================================================
# US-005 — Python API parity, thin pass-through, signature contract
# Workflow: conceptual-workflows-health (lore codex show conceptual-workflows-health)
# ADR-011 — decisions-011-api-parity-with-cli
# ===========================================================================


class TestHealthCheckBindingsApi:
    """Unit coverage of `lore.api.health_check` over the bindings scope (US-005)."""

    def test_health_check_signature_accepts_bindings_scope(self, tmp_path):
        """US-005 unit — signature accepts `scope=["bindings"]`; smoke call on empty project."""
        import inspect

        from lore.api import health_check

        sig = inspect.signature(health_check)
        assert "scope" in sig.parameters

        project = _make_lore_project(tmp_path)
        report = health_check(project, scope=["bindings"])
        assert report.issues == ()
        assert report.has_errors is False

    def test_health_check_thin_pass_through_to_check_bindings(self, tmp_path):
        """US-005 unit — `report.issues` equals `_check_bindings(project_root)` row-for-row."""
        from lore.api import health_check
        from lore.health import _check_bindings

        project = _make_lore_project(tmp_path)
        _seed_codex_doc_for_health(project, "entry-a", binds=["src/missing.py"])

        report = health_check(project, scope=["bindings"])
        assert list(report.issues) == _check_bindings(project)


class TestHealthIssueFieldShape:
    """Dataclass field-set regression guard (US-005)."""

    def test_health_issue_field_set_unchanged(self):
        """US-005 unit — `HealthIssue` field names match the locked set, no additions."""
        from lore.api import HealthIssue

        field_names = {f.name for f in dataclasses.fields(HealthIssue)}
        assert field_names == {
            "severity",
            "entity_type",
            "id",
            "check",
            "detail",
            "schema_id",
            "rule",
            "pointer",
        }


# ===========================================================================
# _check_rites — reference integrity, graph well-formedness, orphan asymmetry
#
# Spec: conceptual-workflows-health (lore codex show conceptual-workflows-health)
#
# `lore.health._check_rites` does not exist yet — these tests import it lazily
# inside each function so the rest of this module still collects. Every test
# below MUST fail (ImportError on the absent `_check_rites`, the absent `rites`
# scope token, or the old `Unknown scope:` wording).
# ===========================================================================


import yaml as _rites_yaml  # noqa: E402


def _make_rites_root(tmp_path):
    """Create a project root with empty .lore/rites/{main,shared} + codex."""
    root = tmp_path / "proj"
    for sub in ("rites/main", "rites/shared", "codex"):
        (root / ".lore" / sub).mkdir(parents=True, exist_ok=True)
    return root


def _write_main(root, rite_id, body):
    p = root / ".lore" / "rites" / "main" / f"{rite_id}.yaml"
    p.write_text(_rites_yaml.safe_dump(body, sort_keys=False), encoding="utf-8")


def _write_shared(root, step_id, body):
    p = root / ".lore" / "rites" / "shared" / f"{step_id}.yaml"
    p.write_text(_rites_yaml.safe_dump(body, sort_keys=False), encoding="utf-8")


def _write_codex_rites(root, doc_id, rites):
    items = "\n".join(f"  - {r}" for r in rites)
    text = (
        "---\n"
        f"id: {doc_id}\n"
        f"title: {doc_id}\n"
        f"summary: s\n"
        f"rites:\n{items}\n"
        "---\nbody\n"
    )
    (root / ".lore" / "codex" / f"{doc_id}.md").write_text(text, encoding="utf-8")


# A rite exhibiting every check defect at once (each check name appears once).
def _seed_all_defects(root):
    # dangling_use + dangling_then on issue-refund.
    _write_main(root, "issue-refund", {
        "id": "issue-refund",
        "title": "Issue refund",
        "summary": "s",
        "trigger": "t",
        "nodes": [
            {"id": "get-contact", "use": "read-contact-info", "then": "review-contact"},
            {"id": "review-contact", "do": "review", "then": "do-refnud"},
        ],
        "conclusions": {"done": {"audience": "agent", "response": "r"}},
    })
    # dangling_codex_rite: codex points at a missing rite.
    _write_codex_rites(root, "ops-refunds", ["totally-missing-rite"])
    # no_entry_node: 2-cycle, every node has inbound.
    _write_main(root, "rite-no-entry", {
        "id": "rite-no-entry", "title": "t", "summary": "s", "trigger": "t",
        "nodes": [
            {"id": "a", "do": "a", "then": "b"},
            {"id": "b", "do": "b", "then": "a"},
        ],
        "conclusions": {"k": {"audience": "agent", "response": "r"}},
    })
    # multiple_entry_nodes: two no-inbound nodes that BOTH route onward through
    # the same downstream node, so every node is reachable from an entry — the
    # sole defect is the two entry points (no spurious unreachable_node here).
    _write_main(root, "rite-multi-entry", {
        "id": "rite-multi-entry", "title": "t", "summary": "s", "trigger": "t",
        "nodes": [
            {"id": "locate-order", "do": "x", "then": "merge"},
            {"id": "do-refund", "do": "y", "then": "merge"},
            {"id": "merge", "do": "z", "then": "done"},
        ],
        "conclusions": {"done": {"audience": "agent", "response": "r"}},
    })
    # unreachable_node: a single entry `start` reaching `done`, plus a
    # disconnected self-looping node `request-update`. The self-loop gives
    # `request-update` an inbound edge (so it is NOT an entry → exactly one
    # entry, no multiple_entry_nodes) yet leaves it unreachable from `start`.
    _write_main(root, "rite-unreachable", {
        "id": "rite-unreachable", "title": "t", "summary": "s", "trigger": "t",
        "nodes": [
            {"id": "start", "do": "x", "then": "done"},
            {"id": "request-update", "do": "y", "then": "request-update"},
        ],
        "conclusions": {"done": {"audience": "agent", "response": "r"}},
    })
    # conclusion_never_reached.
    _write_main(root, "rite-conc-unreached", {
        "id": "rite-conc-unreached", "title": "t", "summary": "s", "trigger": "t",
        "nodes": [{"id": "start", "do": "x", "then": "done"}],
        "conclusions": {
            "done": {"audience": "agent", "response": "r"},
            "contact-requested": {"audience": "agent", "response": "r2"},
        },
    })
    # undefined_conclusion.
    _write_main(root, "rite-undef-conc", {
        "id": "rite-undef-conc", "title": "t", "summary": "s", "trigger": "t",
        "nodes": [{"id": "do-refund", "do": "x", "then": "refunded"}],
        "conclusions": {"other": {"audience": "agent", "response": "r"}},
    })


def test_check_rites_each_check(tmp_path):
    """_check_rites emits one issue per check name with exact detail + HealthIssue fields."""
    from lore.health import _check_rites

    root = _make_rites_root(tmp_path)
    _seed_all_defects(root)
    issues = _check_rites(root)
    by_check = {i.check: i for i in issues}

    assert by_check["dangling_use"].detail == (
        'node "get-contact" uses missing shared step "read-contact-info"'
    )
    assert by_check["dangling_use"].entity_type == "rites"
    assert by_check["dangling_use"].id == "issue-refund"
    # Null on non-schema rows.
    assert by_check["dangling_use"].schema_id is None
    assert by_check["dangling_use"].rule is None
    assert by_check["dangling_use"].pointer is None

    assert by_check["dangling_then"].detail == (
        'node "review-contact" routes to unknown target "do-refnud"'
    )
    assert by_check["dangling_codex_rite"].id == "ops-refunds"
    assert by_check["dangling_codex_rite"].entity_type == "rites"

    for name in [
        "dangling_then",
        "dangling_codex_rite",
        "no_entry_node",
        "multiple_entry_nodes",
        "unreachable_node",
        "conclusion_never_reached",
        "undefined_conclusion",
    ]:
        assert name in by_check, f"missing check: {name}"


def test_check_rites_graph_detail_strings(tmp_path):
    """Graph-walk check details match the codex spec verbatim.

    Each graph defect is seeded in its OWN project root so a single rite triggers
    exactly the check under test, with no cross-rite collisions on the same check
    name (e.g. two rites each emitting `conclusion_never_reached` would clobber a
    shared `by_check` dict). The `multiple_entry_nodes` and `unreachable_node`
    fixtures are structurally distinct: the former has every node reachable from
    an entry (sole defect = two entries); the latter has one entry plus a
    disconnected self-looping node (sole defect = an unreachable node).
    """
    from lore.health import _check_rites

    def detail_for(rite_id, body, check):
        sub = tmp_path / rite_id
        root = _make_rites_root(sub)
        _write_main(root, rite_id, body)
        matches = [i for i in _check_rites(root) if i.check == check]
        assert matches, f"expected a {check} issue for {rite_id}"
        assert len(matches) == 1, f"expected exactly one {check} issue, got {matches}"
        return matches[0].detail

    # no_entry_node: a 2-cycle (every node has an inbound edge).
    assert detail_for("rite-no-entry", {
        "id": "rite-no-entry", "title": "t", "summary": "s", "trigger": "t",
        "nodes": [
            {"id": "a", "do": "a", "then": "b"},
            {"id": "b", "do": "b", "then": "a"},
        ],
        # Conclusion intentionally omitted so no_entry_node is the only defect.
        "conclusions": {},
    }, "no_entry_node") == "no entry node — every node has an inbound edge"

    # multiple_entry_nodes: two entries, every node still reachable via `merge`.
    assert detail_for("rite-multi-entry", {
        "id": "rite-multi-entry", "title": "t", "summary": "s", "trigger": "t",
        "nodes": [
            {"id": "locate-order", "do": "x", "then": "merge"},
            {"id": "do-refund", "do": "y", "then": "merge"},
            {"id": "merge", "do": "z", "then": "done"},
        ],
        "conclusions": {"done": {"audience": "agent", "response": "r"}},
    }, "multiple_entry_nodes") == "multiple entry nodes: locate-order, do-refund"

    # unreachable_node: single entry `start`; `request-update` self-loops (has an
    # inbound edge so it is not an entry) yet is unreachable from `start`.
    assert detail_for("rite-unreachable", {
        "id": "rite-unreachable", "title": "t", "summary": "s", "trigger": "t",
        "nodes": [
            {"id": "start", "do": "x", "then": "done"},
            {"id": "request-update", "do": "y", "then": "request-update"},
        ],
        "conclusions": {"done": {"audience": "agent", "response": "r"}},
    }, "unreachable_node") == 'node "request-update" is unreachable'

    # conclusion_never_reached: a reachable node, but a second conclusion is
    # defined that nothing routes to.
    assert detail_for("rite-conc-unreached", {
        "id": "rite-conc-unreached", "title": "t", "summary": "s", "trigger": "t",
        "nodes": [{"id": "start", "do": "x", "then": "done"}],
        "conclusions": {
            "done": {"audience": "agent", "response": "r"},
            "contact-requested": {"audience": "agent", "response": "r2"},
        },
    }, "conclusion_never_reached") == (
        'conclusion "contact-requested" is defined but never reached'
    )

    # undefined_conclusion: an entry node routes to a target that is neither a
    # node nor a declared conclusion.
    assert detail_for("rite-undef-conc", {
        "id": "rite-undef-conc", "title": "t", "summary": "s", "trigger": "t",
        "nodes": [{"id": "do-refund", "do": "x", "then": "refunded"}],
        "conclusions": {"other": {"audience": "agent", "response": "r"}},
    }, "undefined_conclusion") == (
        'node "do-refund" routes to "refunded" — no node or conclusion'
    )


def test_check_rites_valid_rite_clean(tmp_path):
    """A well-formed main rite (single entry, all reachable, conclusions reached) emits no issue."""
    from lore.health import _check_rites

    root = _make_rites_root(tmp_path)
    _write_main(root, "valid-rite", {
        "id": "valid-rite", "title": "t", "summary": "s", "trigger": "t",
        "nodes": [
            {"id": "locate-order", "do": "find", "then": "do-refund"},
            {"id": "do-refund", "do": "refund", "then": "refunded"},
        ],
        "conclusions": {"refunded": {"audience": "agent", "response": "r"}},
    })
    assert _check_rites(root) == []


def test_check_rites_orphans(tmp_path):
    """orphan_shared_step warns; an orphan main rite is NOT flagged."""
    from lore.health import _check_rites

    root = _make_rites_root(tmp_path)
    _write_shared(root, "read-contact-info", {
        "id": "read-contact-info", "title": "t", "do": "read",
    })
    _write_main(root, "lonely", {
        "id": "lonely", "title": "t", "summary": "s", "trigger": "t",
        "nodes": [{"id": "n", "do": "x", "then": "done"}],
        "conclusions": {"done": {"audience": "agent", "response": "r"}},
    })
    issues = _check_rites(root)
    orphans = [i for i in issues if i.check == "orphan_shared_step"]
    assert len(orphans) == 1
    assert orphans[0].severity == "warning"
    assert orphans[0].id == "read-contact-info"
    assert orphans[0].detail == "no main rite uses this shared step"
    # Orphan main rite emits NO issue.
    assert not any(i.id == "lonely" for i in issues)


def test_check_rites_used_shared_step_not_orphan(tmp_path):
    """A shared step that a main rite use:es is not flagged as orphan."""
    from lore.health import _check_rites

    root = _make_rites_root(tmp_path)
    _write_shared(root, "read-contact-info", {
        "id": "read-contact-info", "title": "t", "do": "read",
    })
    _write_main(root, "uses-it", {
        "id": "uses-it", "title": "t", "summary": "s", "trigger": "t",
        "nodes": [{"id": "n", "use": "read-contact-info", "then": "done"}],
        "conclusions": {"done": {"audience": "agent", "response": "r"}},
    })
    issues = _check_rites(root)
    assert not any(i.check == "orphan_shared_step" for i in issues)


def test_check_rites_skips_deleted(tmp_path):
    """`.yaml.deleted` rite files are ignored by _check_rites."""
    from lore.health import _check_rites

    root = _make_rites_root(tmp_path)
    p = root / ".lore" / "rites" / "main" / "broken.yaml"
    p.write_text(_rites_yaml.safe_dump({
        "id": "broken", "title": "t", "summary": "s", "trigger": "t",
        "nodes": [{"id": "n", "use": "missing-step", "then": "gone"}],
        "conclusions": {"done": {"audience": "agent", "response": "r"}},
    }), encoding="utf-8")
    p.rename(p.with_name("broken.yaml.deleted"))
    assert _check_rites(root) == []


# ---------------------------------------------------------------------------
# scope-token validation + multi-scope dispatch
# ---------------------------------------------------------------------------


def test_health_scope_tokens_includes_rites():
    """The valid-scope token set includes `rites`."""
    import lore.health as h

    assert "rites" in h._ALL_SCOPES


def test_health_check_unknown_scope_message_verbatim(tmp_path):
    """An unknown scope raises ValueError with the shipped `Unknown scope:` text incl. rites.

    The library-level `health_check` keeps its historic `Unknown scope:` wording
    (the CLI Choice validation is the user-facing guard). `rites` now appears in
    the listed valid scopes since it was added to `_ALL_SCOPES`.
    """
    root = _make_rites_root(tmp_path)
    with pytest.raises(ValueError) as exc:
        health_check(root, scope=["xyz"])
    assert str(exc.value) == (
        "Unknown scope: 'xyz'. Valid scopes: codex, artifacts, "
        "doctrines, knights, watchers, glossary, schemas, bindings, rites."
    )


def test_health_check_scope_rites_runs_rite_checks(tmp_path):
    """scope=['rites'] surfaces a dangling_use rite issue."""
    root = _make_rites_root(tmp_path)
    (root / ".lore" / "codex" / "transient").mkdir(parents=True, exist_ok=True)
    _write_main(root, "issue-refund", {
        "id": "issue-refund", "title": "t", "summary": "s", "trigger": "t",
        "nodes": [{"id": "get-contact", "use": "read-contact-info", "then": "done"}],
        "conclusions": {"done": {"audience": "agent", "response": "r"}},
    })
    report = health_check(root, scope=["rites"], write_report=False)
    checks = {i.check for i in report.issues}
    assert "dangling_use" in checks


def test_health_check_scope_codex_rites_dispatches_both(tmp_path):
    """scope=['codex', 'rites'] runs codex checks AND rite checks; dangling_codex_rite fires."""
    root = _make_rites_root(tmp_path)
    (root / ".lore" / "codex" / "transient").mkdir(parents=True, exist_ok=True)
    _write_codex_rites(root, "ops-refunds", ["totally-missing-rite"])
    report = health_check(root, scope=["codex", "rites"], write_report=False)
    assert any(i.check == "dangling_codex_rite" for i in report.issues)


def test_health_check_dangling_codex_rite_under_rites_alone(tmp_path):
    """dangling_codex_rite fires under scope=['rites'] alone (dual-scope codex check)."""
    root = _make_rites_root(tmp_path)
    (root / ".lore" / "codex" / "transient").mkdir(parents=True, exist_ok=True)
    _write_codex_rites(root, "ops-refunds", ["totally-missing-rite"])
    report = health_check(root, scope=["rites"], write_report=False)
    assert any(i.check == "dangling_codex_rite" for i in report.issues)


def test_health_check_dangling_codex_rite_under_codex_alone(tmp_path):
    """dangling_codex_rite also fires under scope=['codex'] alone (dual-scope)."""
    root = _make_rites_root(tmp_path)
    (root / ".lore" / "codex" / "transient").mkdir(parents=True, exist_ok=True)
    _write_codex_rites(root, "ops-refunds", ["totally-missing-rite"])
    report = health_check(root, scope=["codex"], write_report=False)
    assert any(i.check == "dangling_codex_rite" for i in report.issues)


def test_health_check_orphan_shared_step_keeps_exit_zero(tmp_path):
    """An orphan shared step is a warning — report.has_errors stays False."""
    root = _make_rites_root(tmp_path)
    (root / ".lore" / "codex" / "transient").mkdir(parents=True, exist_ok=True)
    _write_shared(root, "read-contact-info", {
        "id": "read-contact-info", "title": "t", "do": "read",
    })
    report = health_check(root, scope=["rites"], write_report=False)
    assert any(
        i.check == "orphan_shared_step" and i.severity == "warning"
        for i in report.issues
    )
    assert report.has_errors is False

