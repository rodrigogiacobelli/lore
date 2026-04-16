"""Unit tests for lore.health module.

Workflow: conceptual-workflows-health (lore codex show conceptual-workflows-health)
"""

import dataclasses
import json
import typing

import pytest
from click.testing import CliRunner

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
from lore.models import HealthIssue, HealthReport


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
# US-018: health_check registered in lore.models.__all__
# Exercises: lore codex show conceptual-workflows-health
# ---------------------------------------------------------------------------


def test_health_check_in_all():
    """'health_check' must appear in lore.models.__all__."""
    # Exercises: lore codex show conceptual-workflows-health
    import lore.models
    assert "health_check" in lore.models.__all__, (
        "'health_check' not found in lore.models.__all__. "
        f"Current __all__: {lore.models.__all__!r}"
    )


def test_health_check_importable_from_lore_models():
    """from lore.models import health_check must succeed and be callable."""
    # Exercises: lore codex show conceptual-workflows-health
    from lore.models import health_check  # noqa: F401
    assert callable(health_check), (
        f"health_check imported from lore.models is not callable: {health_check!r}"
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
    from lore.models import HealthReport as _HR
    assert isinstance(report, _HR)

