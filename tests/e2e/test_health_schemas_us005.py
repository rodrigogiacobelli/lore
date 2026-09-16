"""E2E tests for US-005 — schema errors render in text and JSON with exact fields.

US-005 Red — schema-validation-us-005
Workflow: conceptual-workflows-health (lore codex show conceptual-workflows-health)

Tightens US-004's "contains substring" assertions into verbatim golden-block
and golden-JSON-object equality so the public contract promised by the PRD
is frozen. Every test MUST fail until US-005 Green lands.
"""

from __future__ import annotations

import json
from pathlib import Path

from lore.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _bad_mission(project_dir: Path) -> Path:
    path = (
        project_dir
        / ".lore"
        / "doctrines"
        / "default"
        / "feature-implementation"
        / "feature-implementation"
        / "missions"
        / "pm.md"
    )
    _write(
        path,
        "---\n"
        "id: pm\n"
        "title: Product Manager\n"
        "summary: Writes PRDs.\n"
        "stability: experimental\n"
        "---\n"
        "# Body\n",
    )
    return path


def _design_without_summary(project_dir: Path) -> Path:
    path = (
        project_dir
        / ".lore"
        / "doctrines"
        / "default"
        / "feature-implementation"
        / "feature-implementation"
        / "feature-implementation.design.md"
    )
    text = path.read_text(encoding="utf-8")
    new_text = (
        "\n".join(
            line for line in text.splitlines() if not line.startswith("summary:")
        )
        + "\n"
    )
    path.write_text(new_text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Scenario 1: Text output — verbatim PRD Workflow 2 block
# ---------------------------------------------------------------------------


def test_e2e_workflow_2_verbatim_text_block(runner, project_dir):
    """conceptual-workflows-doctrine-show — PRD W2 full golden block contiguous."""
    _bad_mission(project_dir)

    result = runner.invoke(main, ["health"])

    expected = (
        "ERROR .lore/doctrines/default/feature-implementation/feature-implementation/missions/pm.md\n"
        "  kind: doctrine-mission-frontmatter\n"
        "  schema: lore://schemas/doctrine-mission-frontmatter\n"
        "  rule: additionalProperties\n"
        "  path: /stability\n"
        "  message: Unknown property 'stability' — allowed keys are id, title, summary.\n"
    )
    assert expected in result.output, (
        f"Expected verbatim block not present.\nOutput:\n{result.output}"
    )
    assert "Schema validation: 1 error\n" in result.output
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Scenario 2: Text output — verbatim PRD Workflow 3 block
# ---------------------------------------------------------------------------


def test_e2e_workflow_3_verbatim_text_block(runner, project_dir):
    """conceptual-workflows-doctrine-show — PRD W3 full golden block contiguous."""
    _design_without_summary(project_dir)

    result = runner.invoke(main, ["health"])

    expected = (
        "ERROR .lore/doctrines/default/feature-implementation/feature-implementation/feature-implementation.design.md\n"
        "  kind: doctrine-design-frontmatter\n"
        "  schema: lore://schemas/doctrine-design-frontmatter\n"
        "  rule: required\n"
        "  path: /\n"
        "  message: Missing required property 'summary'.\n"
    )
    assert expected in result.output, (
        f"Expected verbatim block not present.\nOutput:\n{result.output}"
    )
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Scenario 3: JSON output shape — exact object equality
# ---------------------------------------------------------------------------


def test_e2e_json_schema_issue_exact_shape(runner, project_dir):
    """conceptual-workflows-json-output — PRD W5 JSON issue is exactly the documented dict."""
    _bad_mission(project_dir)

    result = runner.invoke(main, ["health", "--json"])
    assert result.exit_code == 1, result.output

    data = json.loads(result.output)
    assert data["has_errors"] is True

    schema_issues = [i for i in data["issues"] if i["check"] == "schema"]
    assert len(schema_issues) == 1, schema_issues

    assert schema_issues[0] == {
        "severity": "error",
        "entity_type": "doctrine-mission-frontmatter",
        "id": ".lore/doctrines/default/feature-implementation/feature-implementation/missions/pm.md",
        "check": "schema",
        "detail": "Unknown property 'stability' — allowed keys are id, title, summary.",
        "schema_id": "lore://schemas/doctrine-mission-frontmatter",
        "rule": "additionalProperties",
        "pointer": "/stability",
    }


def test_e2e_json_schema_issue_required_exact_shape(runner, project_dir):
    """conceptual-workflows-json-output — PRD W3 required rule JSON shape."""
    _design_without_summary(project_dir)

    result = runner.invoke(main, ["health", "--json"])
    assert result.exit_code == 1, result.output

    data = json.loads(result.output)
    schema_issues = [i for i in data["issues"] if i["check"] == "schema"]
    assert len(schema_issues) == 1, schema_issues
    assert schema_issues[0] == {
        "severity": "error",
        "entity_type": "doctrine-design-frontmatter",
        "id": ".lore/doctrines/default/feature-implementation/feature-implementation/feature-implementation.design.md",
        "check": "schema",
        "detail": "Missing required property 'summary'.",
        "schema_id": "lore://schemas/doctrine-design-frontmatter",
        "rule": "required",
        "pointer": "/",
    }


# ---------------------------------------------------------------------------
# Scenario 4: JSON — non-schema issues still serialize with null extras
# ---------------------------------------------------------------------------


def test_e2e_json_non_schema_issue_has_null_schema_fields(runner, project_dir):
    """conceptual-workflows-json-output — non-schema issues always carry
    schema_id/rule/pointer keys set to null (not absent)."""
    # A design document whose declared id is not its directory name → id_mismatch
    doctrines = project_dir / ".lore" / "doctrines" / "default" / "feat-auth"
    _write(
        doctrines / "feat-auth.design.md",
        "---\nid: something-else\ntitle: Auth\nsummary: s\n---\nBody.\n",
    )
    _write(
        doctrines / "missions" / "recon.md",
        "---\nid: recon\ntitle: Recon\nsummary: s\n---\nBody.\n",
    )

    result = runner.invoke(
        main, ["health", "--scope", "doctrines", "--json"]
    )
    assert result.exit_code == 1, result.output

    data = json.loads(result.output)
    assert data["has_errors"] is True
    non_schema = [i for i in data["issues"] if i["check"] != "schema"]
    assert non_schema, f"Expected an id_mismatch issue.\n{data}"
    broken = next(i for i in non_schema if i["check"] == "id_mismatch")

    # Keys must be PRESENT, values must be None.
    assert "schema_id" in broken
    assert "rule" in broken
    assert "pointer" in broken
    assert broken["schema_id"] is None
    assert broken["rule"] is None
    assert broken["pointer"] is None


# ---------------------------------------------------------------------------
# Scenario 5: Exit-code contract (FR-16)
# ---------------------------------------------------------------------------


def test_e2e_exit_code_zero_on_clean_project(runner, project_dir):
    """conceptual-workflows-health — FR-16 exit 0 when every check passes."""
    result = runner.invoke(main, ["health"])
    assert result.exit_code == 0, result.output


def test_e2e_exit_code_nonzero_on_any_schema_error(runner, project_dir):
    """conceptual-workflows-health — FR-16 non-zero exit with ≥1 schema error."""
    _bad_mission(project_dir)
    result = runner.invoke(main, ["health"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Scenario 6: JSON output always includes new keys on every issue
# ---------------------------------------------------------------------------


def test_e2e_json_every_issue_carries_new_keys(runner, project_dir):
    """conceptual-workflows-json-output — every issue object has the three
    new keys regardless of check type (mixed-issue report)."""
    _bad_mission(project_dir)

    # Also inject a non-schema issue in the same run.
    doctrines = project_dir / ".lore" / "doctrines" / "default" / "feat-x"
    _write(
        doctrines / "feat-x.design.md",
        "---\nid: something-else\ntitle: X\nsummary: s\n---\nBody.\n",
    )
    _write(
        doctrines / "missions" / "recon.md",
        "---\nid: recon\ntitle: Recon\nsummary: s\n---\nBody.\n",
    )

    result = runner.invoke(main, ["health", "--json"])
    data = json.loads(result.output)
    assert data["issues"], "expected issues in output"
    for issue in data["issues"]:
        assert "schema_id" in issue, issue
        assert "rule" in issue, issue
        assert "pointer" in issue, issue
        if issue["check"] != "schema":
            assert issue["schema_id"] is None, issue
            assert issue["rule"] is None, issue
            assert issue["pointer"] is None, issue
        else:
            assert issue["schema_id"] is not None, issue
            assert issue["rule"] is not None, issue
            assert issue["pointer"] is not None, issue


# ---------------------------------------------------------------------------
# Scenario 7: Exact summary-line wording (singular vs plural)
# ---------------------------------------------------------------------------


def test_e2e_summary_line_plural_wording(runner, project_dir):
    """conceptual-workflows-health — plural 'errors' with N != 1."""
    _bad_mission(project_dir)
    # A second bad mission file, so the count is 2.
    _write(
        project_dir
        / ".lore"
        / "doctrines"
        / "default"
        / "feature-implementation"
        / "missions"
        / "eng.md",
        "---\nid: eng\ntitle: E\nsummary: s\nbogus: x\n---\n",
    )
    result = runner.invoke(main, ["health"])
    assert "Schema validation: 2 errors\n" in result.output, result.output
    assert "Schema validation: 2 error\n" not in result.output


def test_e2e_summary_line_zero_plural(runner, project_dir):
    """conceptual-workflows-health — plural 'errors' at N == 0."""
    result = runner.invoke(main, ["health"])
    assert "Schema validation: 0 errors" in result.output
