"""E2E tests for US-008 — transient health report Schema validation section.

US-008 Red — schema-validation-us-008
Workflow: conceptual-workflows-oracle (lore codex show conceptual-workflows-oracle)

PRD FR-15: the transient markdown health report
(`.lore/codex/transient/health-<ts>.md`) gains a ``## Schema validation``
section that lists every schema error grouped by entity kind.

Every test MUST fail until US-008 Green lands.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lore.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _latest_health_report(project_dir: Path) -> Path:
    transient = project_dir / ".lore" / "codex" / "transient"
    reports = sorted(transient.glob("health-*.md"))
    assert reports, f"no health-*.md report written under {transient}"
    return reports[-1]


def _inject_bad_knight(project_dir: Path) -> None:
    _write(
        project_dir
        / ".lore"
        / "knights"
        / "default"
        / "feature-implementation"
        / "pm.md",
        "---\n"
        "id: pm\n"
        "title: Product Manager\n"
        "summary: Writes PRDs.\n"
        "stability: experimental\n"
        "---\n"
        "# Body\n",
    )


def _inject_doctrine_design_missing_summary(project_dir: Path) -> None:
    """Write a complete doctrine pair where the design frontmatter omits `summary`."""
    base = (
        project_dir
        / ".lore"
        / "doctrines"
        / "feature-implementation"
    )
    _write(
        base / "feature-implementation.yaml",
        "id: feature-implementation\n"
        "title: Feature Implementation\n"
        "summary: s\n"
        "steps: []\n",
    )
    _write(
        base / "feature-implementation.design.md",
        "---\n"
        "id: feature-implementation\n"
        "title: Feature Implementation\n"
        "---\n"
        "# Body\n",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_clean(project_dir):
    """Fresh init project — zero schema errors expected."""
    return project_dir


@pytest.fixture()
def project_with_two_schema_errors(project_dir):
    """Project with exactly two schema errors: one knight + one doctrine-design."""
    _inject_bad_knight(project_dir)
    _inject_doctrine_design_missing_summary(project_dir)
    return project_dir


@pytest.fixture()
def project_with_bad_knight(project_dir):
    """Project with a single schema error on a knight file."""
    _inject_bad_knight(project_dir)
    return project_dir


# ---------------------------------------------------------------------------
# Scenario 1 — clean project writes the zero-case block
# ---------------------------------------------------------------------------


def test_e2e_report_section_clean_project(runner, project_clean):
    """conceptual-workflows-oracle — transient report zero-case block exact."""
    result = runner.invoke(main, ["health"])
    assert result.exit_code == 0, result.output

    text = _latest_health_report(project_clean).read_text()
    assert "## Schema validation\n\nNo schema errors.\n" in text


# ---------------------------------------------------------------------------
# Scenario 2 — multi-kind, sorted, verbatim formatting
# ---------------------------------------------------------------------------


def test_e2e_report_section_multi_kind_contains_both_headings(
    runner, project_with_two_schema_errors
):
    """conceptual-workflows-oracle — both kind subheadings present."""
    result = runner.invoke(main, ["health"])
    assert result.exit_code != 0, result.output

    text = _latest_health_report(project_with_two_schema_errors).read_text()
    assert "## Schema validation" in text
    assert "### doctrine-design-frontmatter" in text
    assert "### knight" in text


def test_e2e_report_section_multi_kind_alphabetical_order(
    runner, project_with_two_schema_errors
):
    """conceptual-workflows-oracle — kinds sorted alphabetically in report."""
    runner.invoke(main, ["health"])
    text = _latest_health_report(project_with_two_schema_errors).read_text()
    assert text.index("### doctrine-design-frontmatter") < text.index("### knight")


def test_e2e_report_section_multi_kind_exact_block(
    runner, project_with_two_schema_errors
):
    """conceptual-workflows-oracle — exact two-kind block appears verbatim."""
    runner.invoke(main, ["health"])
    text = _latest_health_report(project_with_two_schema_errors).read_text()

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


# ---------------------------------------------------------------------------
# Scenario 3 — section omitted when scope excludes schemas
# ---------------------------------------------------------------------------


def test_e2e_report_section_omitted_when_scope_excludes_schemas(
    runner, project_dir
):
    """conceptual-workflows-oracle — scope gating, differential: default has the
    section, non-schema scope does not."""
    _inject_bad_knight(project_dir)

    # Default run — schemas scope active, section MUST be present.
    runner.invoke(main, ["health"])
    default_text = _latest_health_report(project_dir).read_text()

    # Non-schema scope — section MUST be absent.
    runner.invoke(main, ["health", "--scope", "codex"])
    codex_text = _latest_health_report(project_dir).read_text()

    assert "## Schema validation" in default_text
    assert "## Schema validation" not in codex_text


# ---------------------------------------------------------------------------
# Placement — section appended after existing issues table
# ---------------------------------------------------------------------------


def test_e2e_report_section_placed_after_existing_issues_table(
    runner, project_with_two_schema_errors
):
    """conceptual-workflows-oracle — new section placed AFTER existing issues table."""
    runner.invoke(main, ["health"])
    text = _latest_health_report(project_with_two_schema_errors).read_text()
    # Existing issues table header is present because we have schema errors
    # rendered into the main table as well as into the new section.
    assert "| Severity | Entity Type | ID | Check | Detail |" in text
    assert "## Schema validation" in text
    assert text.index("| Severity | Entity Type | ID | Check | Detail |") < text.index(
        "## Schema validation"
    )
