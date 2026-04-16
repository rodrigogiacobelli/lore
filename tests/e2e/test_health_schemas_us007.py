"""E2E tests for US-007 — `--scope schemas` filter.

US-007 Red — schema-validation-us-007
Workflow: conceptual-workflows-health (lore codex show conceptual-workflows-health)

Covers PRD Workflow 4 scenarios: scoped-only, scoped-excluding, scope
composition, default run (schemas on), invalid-scope typo, plus exit-code
contract and summary-line gating.
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


def _inject_bad_knight(project_dir: Path) -> Path:
    p = (
        project_dir
        / ".lore"
        / "knights"
        / "default"
        / "feature-implementation"
        / "pm.md"
    )
    _write(
        p,
        "---\n"
        "id: pm\n"
        "title: Product Manager\n"
        "summary: Writes PRDs.\n"
        "stability: experimental\n"
        "---\n"
        "# Body\n",
    )
    return p


def _inject_broken_knight_ref_doctrine(project_dir: Path) -> None:
    """Create a doctrine whose step references a knight that does not exist."""
    d = project_dir / ".lore" / "doctrines" / "default" / "feat-auth"
    _write(
        d / "feat-auth.yaml",
        "id: feat-auth\nsteps:\n"
        "  - id: step-1\n    title: Step 1\n    type: knight\n"
        "    knight: ghost-knight\n",
    )
    _write(
        d / "feat-auth.design.md",
        "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
    )


@pytest.fixture()
def project_with_schema_and_ref_errors(project_dir):
    """Project that has exactly ONE schema error and ONE broken knight ref."""
    _inject_bad_knight(project_dir)
    _inject_broken_knight_ref_doctrine(project_dir)
    return project_dir


# ---------------------------------------------------------------------------
# PRD Workflow 4 Scenario 1 — --scope schemas runs only schema checks
# ---------------------------------------------------------------------------


def test_scope_schemas_only_emits_schema_block(
    runner, project_with_schema_and_ref_errors
):
    """conceptual-workflows-health — W4 S1: only schema ERROR block present."""
    result = runner.invoke(main, ["health", "--scope", "schemas"])

    assert result.exit_code != 0, result.output
    # Schema block for the bad knight is present.
    assert (
        "ERROR .lore/knights/default/feature-implementation/pm.md"
        in result.output
    )
    assert "  rule: additionalProperties" in result.output
    # No broken-knight-ref block emitted.
    assert "broken_knight_ref" not in result.output
    assert "ghost-knight" not in result.output


def test_scope_schemas_only_summary_exact_one_error(
    runner, project_with_schema_and_ref_errors
):
    """Summary line reads exactly 'Schema validation: 1 error'."""
    result = runner.invoke(main, ["health", "--scope", "schemas"])
    assert "Schema validation: 1 error\n" in result.output
    assert "Schema validation: 1 errors" not in result.output


def test_scope_schemas_only_exit_code_one(
    runner, project_with_schema_and_ref_errors
):
    """Exit code is 1 when only schema errors exist under scope=schemas."""
    result = runner.invoke(main, ["health", "--scope", "schemas"])
    assert result.exit_code == 1, result.output


# ---------------------------------------------------------------------------
# PRD Workflow 4 Scenario 2 — --scope doctrines excludes schema validation
# ---------------------------------------------------------------------------


def test_scope_doctrines_excludes_schema_summary_line(
    runner, project_with_schema_and_ref_errors
):
    """conceptual-workflows-health — W4 S2: no 'Schema validation:' line at all."""
    result = runner.invoke(main, ["health", "--scope", "doctrines"])
    assert result.exit_code != 0, result.output
    assert "Schema validation:" not in result.output


def test_scope_doctrines_excludes_schema_error_blocks(
    runner, project_with_schema_and_ref_errors
):
    """No schema ERROR blocks are printed when schemas scope is excluded."""
    result = runner.invoke(main, ["health", "--scope", "doctrines"])
    # Non-schema issue IS present.
    assert "broken_knight_ref" in result.output
    # No schema ERROR block for the bad knight.
    assert (
        "ERROR .lore/knights/default/feature-implementation/pm.md"
        not in result.output
    )
    assert "kind: knight" not in result.output


# ---------------------------------------------------------------------------
# PRD Workflow 4 Scenario 3 — --scope doctrines schemas runs BOTH
# ---------------------------------------------------------------------------


def test_scope_doctrines_schemas_composed_runs_both(
    runner, project_with_schema_and_ref_errors
):
    """conceptual-workflows-health — W4 S3: ADR-012 space-separated composition."""
    result = runner.invoke(
        main, ["health", "--scope", "doctrines", "--scope", "schemas"]
    )
    assert result.exit_code != 0, result.output
    # Both error kinds present.
    assert "broken_knight_ref" in result.output
    assert (
        "ERROR .lore/knights/default/feature-implementation/pm.md"
        in result.output
    )
    # Summary line reports exactly one schema violation.
    assert "Schema validation: 1 error\n" in result.output


def test_scope_composition_order_independent(
    runner, project_with_schema_and_ref_errors
):
    """Order of --scope values does not change which checks run."""
    a = runner.invoke(
        main, ["health", "--scope", "doctrines", "--scope", "schemas"]
    )
    b = runner.invoke(
        main, ["health", "--scope", "schemas", "--scope", "doctrines"]
    )
    # Same summary line present in both outputs.
    assert "Schema validation: 1 error\n" in a.output
    assert "Schema validation: 1 error\n" in b.output
    assert "broken_knight_ref" in a.output
    assert "broken_knight_ref" in b.output


# ---------------------------------------------------------------------------
# PRD Workflow 4 Scenario 4 — default run includes schemas
# ---------------------------------------------------------------------------


def test_default_run_includes_schema_validation(
    runner, project_with_schema_and_ref_errors
):
    """conceptual-workflows-health — W4 S4: no flags → schemas runs."""
    result = runner.invoke(main, ["health"])
    assert result.exit_code != 0, result.output
    assert "Schema validation: 1 error\n" in result.output
    assert (
        "ERROR .lore/knights/default/feature-implementation/pm.md"
        in result.output
    )
    assert "broken_knight_ref" in result.output


# ---------------------------------------------------------------------------
# PRD Workflow 4 Scenario 5 — typo 'schema' rejected with exit 2
# ---------------------------------------------------------------------------


def test_scope_typo_schema_rejected_exit_2(runner, project_dir):
    """conceptual-workflows-health — W4 S5: click Choice rejects 'schema'."""
    result = runner.invoke(main, ["health", "--scope", "schema"])
    assert result.exit_code == 2
    # Click renders usage errors to output; mix_stderr default merges streams.
    assert "Invalid value for '--scope'" in result.output


def test_scope_typo_schemas_plural_typo_rejected(runner, project_dir):
    """Common typos 'schemass' / 'schemes' are rejected too."""
    for typo in ("schemass", "schemes", "Schemas", "SCHEMAS"):
        result = runner.invoke(main, ["health", "--scope", typo])
        assert result.exit_code == 2, f"typo {typo!r} unexpectedly accepted"


# ---------------------------------------------------------------------------
# Summary-line gating — omitted when schemas is NOT in active scope
# ---------------------------------------------------------------------------


def test_summary_line_omitted_when_scope_excludes_schemas(
    runner, project_dir
):
    """conceptual-workflows-health — renderer gating: no summary line when
    `schemas` is not in the active scope set, even on a clean project."""
    result = runner.invoke(main, ["health", "--scope", "codex"])
    assert "Schema validation:" not in result.output


def test_summary_line_printed_when_scope_is_schemas_zero_case(
    runner, project_dir
):
    """conceptual-workflows-health — zero-case still prints the summary line
    when `schemas` is the active scope (pristine project)."""
    result = runner.invoke(main, ["health", "--scope", "schemas"])
    assert "Schema validation: 0 errors" in result.output


def test_summary_line_printed_on_composition_zero_case(runner, project_dir):
    """Composed scope that includes `schemas` prints the summary line even
    when schema count is zero."""
    result = runner.invoke(
        main, ["health", "--scope", "codex", "--scope", "schemas"]
    )
    assert "Schema validation: 0 errors" in result.output


# ---------------------------------------------------------------------------
# Exit-code contract — only schema errors → exit 1
# ---------------------------------------------------------------------------


def test_exit_code_one_when_only_schema_errors_exist(runner, project_dir):
    """FR-16: non-zero exit when schema errors are the sole failure mode."""
    _inject_bad_knight(project_dir)
    result = runner.invoke(main, ["health"])
    assert result.exit_code == 1, result.output


def test_exit_code_zero_when_schemas_scope_clean(runner, project_dir):
    """FR-16: pristine `--scope schemas` run exits 0."""
    result = runner.invoke(main, ["health", "--scope", "schemas"])
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# --help text surfaces 'schemas' end-to-end
# ---------------------------------------------------------------------------


def test_health_help_output_mentions_schemas(runner):
    """`lore health --help` output contains the literal token 'schemas'."""
    result = runner.invoke(main, ["health", "--help"])
    assert result.exit_code == 0
    assert "schemas" in result.output
