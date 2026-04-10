"""E2E tests for the `lore health` CLI command.

Workflow: conceptual-workflows-health (lore codex show conceptual-workflows-health)
"""

import shutil
from unittest.mock import patch

from lore.cli import main
from lore.health import health_check
from lore.models import HealthReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_codex_doc(project_dir, filename, content):
    path = project_dir / ".lore" / "codex" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _write_artifact(project_dir, filename, content):
    path = project_dir / ".lore" / "artifacts" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _write_doctrine_pair(project_dir, stem, yaml_content, design_content):
    base = project_dir / ".lore" / "doctrines" / stem
    base.parent.mkdir(parents=True, exist_ok=True)
    (base.parent / (base.name + ".design.md")).write_text(design_content)
    (base.parent / (base.name + ".yaml")).write_text(yaml_content)


def _write_watcher(project_dir, filename, content):
    path = project_dir / ".lore" / "watchers" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _write_knight(project_dir, name, content):
    path = project_dir / ".lore" / "knights" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


# ---------------------------------------------------------------------------
# Scenario 1: Clean project — all five types scanned, exit 0
# Exercises: conceptual-workflows-health — clean full audit
# ---------------------------------------------------------------------------


class TestHealthCleanProject:
    """lore health on a clean project exits 0 and prints success message."""

    def test_health_clean_project_exits_zero(self, runner, project_dir):
        """lore health exits 0 on a project with no issues."""
        result = runner.invoke(main, ["health"])
        assert result.exit_code == 0, result.output

    def test_health_clean_project_prints_no_issues_found(self, runner, project_dir):
        """lore health prints 'No issues found.' on a clean project."""
        result = runner.invoke(main, ["health"])
        assert "No issues found." in result.output


# ---------------------------------------------------------------------------
# Scenario 2: Project with errors — all five types scanned, issues reported, exit 1
# Exercises: conceptual-workflows-health — full audit with broken knight ref + invalid watcher YAML
# ---------------------------------------------------------------------------


class TestHealthWithErrors:
    """lore health reports errors from multiple entity types and exits 1."""

    def test_health_broken_knight_ref_and_invalid_watcher_yaml_exits_one(
        self, runner, project_dir
    ):
        """lore health exits 1 when doctrine has broken knight ref and watcher has invalid YAML."""
        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
                "  - id: step-1\n    title: Step 1\n    knight: senior-engineer\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )
        _write_watcher(
            project_dir,
            "on-quest-close.yaml",
            "id: on-quest-close\ntitle: On Close\n  broken: : yaml\n",
        )

        result = runner.invoke(main, ["health"])

        assert result.exit_code == 1, result.output

    def test_health_broken_knight_ref_appears_in_output(self, runner, project_dir):
        """lore health output contains 'ERROR  doctrines' line for broken knight ref."""
        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
                "  - id: step-1\n    title: Step 1\n    knight: senior-engineer\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health"])

        assert "ERROR" in result.output
        assert "doctrines" in result.output

    def test_health_invalid_watcher_yaml_appears_in_output(self, runner, project_dir):
        """lore health output contains 'ERROR  watchers' line for invalid YAML."""
        _write_watcher(
            project_dir,
            "bad.yaml",
            "id: bad\ntitle: Bad\n  broken: : yaml\n",
        )

        result = runner.invoke(main, ["health"])

        assert "ERROR" in result.output
        assert "watchers" in result.output


# ---------------------------------------------------------------------------
# Scenario 3: No flags — five entity types appear in output
# Exercises: conceptual-workflows-health — multi-type error detection
# ---------------------------------------------------------------------------


class TestHealthMultipleTypes:
    """lore health with no flags checks all entity types."""

    def test_health_codex_error_and_watcher_error_both_appear(self, runner, project_dir):
        """lore health reports both codex and watcher errors when both exist."""
        _write_codex_doc(
            project_dir,
            "broken-link.md",
            "---\nid: broken-link\ntitle: Broken\nsummary: s\nrelated:\n  - nonexistent-id\n---\nBody.\n",
        )
        _write_watcher(
            project_dir,
            "bad-ref.yaml",
            "id: bad-ref\ntitle: Bad Ref\nsummary: s\naction: nonexistent-doctrine\n",
        )

        result = runner.invoke(main, ["health"])

        assert result.exit_code == 1, result.output
        assert "codex" in result.output
        assert "watchers" in result.output

    def test_health_codex_error_present_in_output(self, runner, project_dir):
        """lore health stdout contains 'ERROR' and 'codex' for broken related link."""
        _write_codex_doc(
            project_dir,
            "broken.md",
            "---\nid: broken\ntitle: Broken\nsummary: s\nrelated:\n  - ghost-id\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health"])

        assert "ERROR" in result.output
        assert "codex" in result.output

    def test_health_watcher_error_present_in_output(self, runner, project_dir):
        """lore health stdout contains 'ERROR' and 'watchers' for broken doctrine ref."""
        _write_watcher(
            project_dir,
            "ghost-ref.yaml",
            "id: ghost-ref\ntitle: Ghost\nsummary: s\naction: ghost-doctrine\n",
        )

        result = runner.invoke(main, ["health"])

        assert "ERROR" in result.output
        assert "watchers" in result.output


# ---------------------------------------------------------------------------
# Scenario 4 (US-002): --scope watchers — only watcher issues appear
# Exercises: conceptual-workflows-health — targeted watcher audit scope isolation
# ---------------------------------------------------------------------------


class TestHealthScopeWatchersOnly:
    """lore health --scope watchers reports only watcher issues, not codex."""

    def test_health_scope_watchers_only_exits_one_with_watcher_error(
        self, runner, project_dir
    ):
        """lore health --scope watchers exits 1 when watcher has broken doctrine ref."""
        _write_watcher(
            project_dir,
            "on-quest-close.yaml",
            "id: on-quest-close\ntitle: On Close\nsummary: s\naction: feat-payments\n",
        )
        _write_codex_doc(
            project_dir,
            "broken-link.md",
            "---\nid: broken-link\ntitle: Broken\nsummary: s\nrelated:\n  - nonexistent-id\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "watchers"])

        assert result.exit_code == 1, result.output

    def test_health_scope_watchers_only_contains_watcher_error_line(
        self, runner, project_dir
    ):
        """lore health --scope watchers output contains ERROR watchers line."""
        _write_watcher(
            project_dir,
            "on-quest-close.yaml",
            "id: on-quest-close\ntitle: On Close\nsummary: s\naction: feat-payments\n",
        )

        result = runner.invoke(main, ["health", "--scope", "watchers"])

        assert "ERROR" in result.output
        assert "watchers" in result.output

    def test_health_scope_watchers_only_no_codex_error_line(
        self, runner, project_dir
    ):
        """lore health --scope watchers output does NOT contain ERROR codex even when codex error exists."""
        _write_watcher(
            project_dir,
            "on-quest-close.yaml",
            "id: on-quest-close\ntitle: On Close\nsummary: s\naction: feat-payments\n",
        )
        _write_codex_doc(
            project_dir,
            "broken-link.md",
            "---\nid: broken-link\ntitle: Broken\nsummary: s\nrelated:\n  - nonexistent-id\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "watchers"])

        lines = result.output.splitlines()
        codex_error_lines = [line for line in lines if "ERROR" in line and "codex" in line]
        assert codex_error_lines == []


# ---------------------------------------------------------------------------
# Scenario 5 (US-002): --scope doctrines --scope knights — only those two types
# Exercises: conceptual-workflows-health — two-type scope filtering
# ---------------------------------------------------------------------------


class TestHealthScopeTwoTokens:
    """lore health --scope doctrines --scope knights reports only those two types."""

    def test_health_scope_two_tokens_no_codex_errors(self, runner, project_dir):
        """lore health --scope doctrines --scope knights output does not contain codex errors."""
        _write_codex_doc(
            project_dir,
            "broken.md",
            "---\nid: broken\ntitle: Broken\nsummary: s\nrelated:\n  - ghost-id\n---\nBody.\n",
        )
        _write_watcher(
            project_dir,
            "broken.yaml",
            "id: broken-w\ntitle: Broken\nsummary: s\naction: missing-doctrine\n",
        )

        result = runner.invoke(
            main, ["health", "--scope", "doctrines", "--scope", "knights"]
        )

        lines = result.output.splitlines()
        assert not any("codex" in line for line in lines if "ERROR" in line)

    def test_health_scope_two_tokens_no_watcher_errors(self, runner, project_dir):
        """lore health --scope doctrines --scope knights output does not contain watcher errors."""
        _write_watcher(
            project_dir,
            "broken.yaml",
            "id: broken-w\ntitle: Broken\nsummary: s\naction: missing-doctrine\n",
        )

        result = runner.invoke(
            main, ["health", "--scope", "doctrines", "--scope", "knights"]
        )

        lines = result.output.splitlines()
        assert not any("watchers" in line for line in lines if "ERROR" in line)

    def test_health_scope_two_tokens_no_artifacts_errors(self, runner, project_dir):
        """lore health --scope doctrines --scope knights output does not contain artifact errors."""
        _write_artifact(
            project_dir,
            "bad.md",
            "---\ntitle: No ID\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(
            main, ["health", "--scope", "doctrines", "--scope", "knights"]
        )

        lines = result.output.splitlines()
        assert not any("artifacts" in line for line in lines if "ERROR" in line)


# ---------------------------------------------------------------------------
# Scenario 6 (US-002): --scope <invalid> — invalid token, non-zero exit
# Exercises: conceptual-workflows-health — invalid scope token rejection
# ---------------------------------------------------------------------------


class TestHealthScopeInvalidToken:
    """lore health --scope unicorns exits non-zero with error message."""

    def test_health_invalid_scope_token_exits_nonzero(self, runner, project_dir):
        """lore health --scope unicorns exits non-zero."""
        result = runner.invoke(main, ["health", "--scope", "unicorns"])

        assert result.exit_code != 0

    def test_health_invalid_scope_token_mentions_invalid_value(
        self, runner, project_dir
    ):
        """lore health --scope unicorns output contains message indicating invalid token."""
        result = runner.invoke(main, ["health", "--scope", "unicorns"])

        combined = (result.output or "") + (
            str(result.exception) if result.exception else ""
        )
        assert "unicorns" in combined


# ---------------------------------------------------------------------------
# Scenario 7 (US-002): --scope codex — report file written
# Exercises: conceptual-workflows-health — report always written when scope used
# ---------------------------------------------------------------------------


class TestHealthScopeReportFileWritten:
    """lore health --scope codex writes a report file under .lore/codex/transient/."""

    def test_health_scope_codex_creates_report_file(self, runner, project_dir):
        """lore health --scope codex creates a health-*.md file in transient dir."""
        result = runner.invoke(main, ["health", "--scope", "codex"])

        transient_dir = project_dir / ".lore" / "codex" / "transient"
        report_files = list(transient_dir.glob("health-*.md"))
        assert len(report_files) >= 1, f"No report file found. Output: {result.output}"

    def test_health_scope_codex_completes_without_crash(self, runner, project_dir):
        """lore health --scope codex exits 0 or 1 (no unexpected exit code)."""
        result = runner.invoke(main, ["health", "--scope", "codex"])

        assert result.exit_code in (0, 1), f"Unexpected exit code: {result.exit_code}"


# ---------------------------------------------------------------------------
# Scenario 8 (US-003): Warnings only → exit 0
# Exercises: conceptual-workflows-health — warning-only run is non-blocking
# ---------------------------------------------------------------------------


class TestHealthWarningsOnly:
    """lore health with only warnings (no errors) exits 0."""

    def test_health_warnings_only_exits_zero(self, runner, project_dir):
        """lore health exits 0 when the only issues are warnings (island nodes)."""
        # An island codex node produces a warning but no error.
        _write_codex_doc(
            project_dir,
            "island.md",
            "---\nid: island\ntitle: Island\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health"])

        assert result.exit_code == 0, result.output

    def test_health_warnings_only_output_contains_warning(self, runner, project_dir):
        """lore health output contains 'WARNING' when only island-node warnings exist."""
        _write_codex_doc(
            project_dir,
            "island.md",
            "---\nid: island\ntitle: Island\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health"])

        assert "WARNING" in result.output


# ---------------------------------------------------------------------------
# Scenario 9 (US-003): --json + errors → exit 1
# Exercises: conceptual-workflows-health — exit code independent of output format
# ---------------------------------------------------------------------------


class TestHealthJsonFlagWithErrors:
    """lore health --json still exits 1 when errors are present."""

    def test_health_json_with_errors_exits_one(self, runner, project_dir):
        """lore health --json exits 1 when the project has an error."""
        _write_watcher(
            project_dir,
            "broken.yaml",
            "id: broken\ntitle: Broken\nsummary: s\naction: nonexistent-doctrine\n",
        )

        result = runner.invoke(main, ["health", "--json"])

        assert result.exit_code == 1, result.output

    def test_health_json_with_errors_output_is_valid_json(self, runner, project_dir):
        """lore health --json output is parseable JSON even when errors exist."""
        import json

        _write_watcher(
            project_dir,
            "broken.yaml",
            "id: broken\ntitle: Broken\nsummary: s\naction: nonexistent-doctrine\n",
        )

        result = runner.invoke(main, ["health", "--json"])

        data = json.loads(result.output)
        assert data["has_errors"] is True


# ---------------------------------------------------------------------------
# Scenario 10 (US-003): --scope filters to a clean scope → exit 0
# Exercises: conceptual-workflows-health — scoped clean run is non-blocking
# ---------------------------------------------------------------------------


class TestHealthScopeCleanScope:
    """lore health --scope <type> exits 0 when that scope has no errors."""

    def test_health_scope_watchers_clean_exits_zero(self, runner, project_dir):
        """lore health --scope watchers exits 0 when watchers have no errors, even if codex has errors."""
        _write_codex_doc(
            project_dir,
            "broken.md",
            "---\nid: broken\ntitle: Broken\nsummary: s\nrelated:\n  - nonexistent-id\n---\nBody.\n",
        )
        # No watcher files → watchers scope is clean.

        result = runner.invoke(main, ["health", "--scope", "watchers"])

        assert result.exit_code == 0, result.output

    def test_health_scope_codex_clean_exits_zero(self, runner, project_dir):
        """lore health --scope codex exits 0 when codex has no errors (only watcher errors exist)."""
        _write_watcher(
            project_dir,
            "broken.yaml",
            "id: broken\ntitle: Broken\nsummary: s\naction: nonexistent-doctrine\n",
        )
        # No codex docs beyond default init state → codex scope is clean.

        result = runner.invoke(main, ["health", "--scope", "codex"])

        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# US-004: Broken related link — exact output format
# Exercises: lore codex show conceptual-workflows-health
# ---------------------------------------------------------------------------


class TestHealthBrokenRelatedLink:
    """lore health reports broken_related_link errors with exact output format."""

    def test_health_codex_broken_related_link_exits_one(self, runner, project_dir):
        """lore health exits 1 when a codex doc has a related link to non-existent ID."""
        # Given: decisions-008.md with related: [decisions-007, decisions-999] and no decisions-999
        _write_codex_doc(
            project_dir,
            "decisions/decisions-007.md",
            "---\nid: decisions-007\ntitle: D007\nsummary: s\nrelated:\n  - decisions-008\n---\nBody.\n",
        )
        _write_codex_doc(
            project_dir,
            "decisions/decisions-008.md",
            "---\nid: decisions-008\ntitle: D008\nsummary: s\nrelated:\n  - decisions-007\n  - decisions-999\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health"])

        assert result.exit_code == 1, result.output

    def test_health_codex_broken_related_link_exact_output_line(self, runner, project_dir):
        """lore health stdout contains exact broken_related_link line per US-004 spec."""
        # Given: decisions-008.md with related: [decisions-007, decisions-999]; decisions-999 absent
        _write_codex_doc(
            project_dir,
            "decisions/decisions-007.md",
            "---\nid: decisions-007\ntitle: D007\nsummary: s\nrelated:\n  - decisions-008\n---\nBody.\n",
        )
        _write_codex_doc(
            project_dir,
            "decisions/decisions-008.md",
            "---\nid: decisions-008\ntitle: D008\nsummary: s\nrelated:\n  - decisions-007\n  - decisions-999\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "codex"])

        expected = "ERROR  codex  decisions-008  broken_related_link: related ID 'decisions-999' does not exist"
        assert expected in result.output, f"Expected line not found.\nOutput:\n{result.output}"

    def test_health_codex_broken_related_link_scope_codex_exits_one(self, runner, project_dir):
        """lore health --scope codex exits 1 when codex doc has broken related link."""
        _write_codex_doc(
            project_dir,
            "doc-a.md",
            "---\nid: doc-a\ntitle: Doc A\nsummary: s\nrelated:\n  - nonexistent-doc\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "codex"])

        assert result.exit_code == 1, result.output

    def test_health_codex_all_valid_related_no_broken_link_output(self, runner, project_dir):
        """lore health --scope codex does not output broken_related_link when all links valid."""
        _write_codex_doc(
            project_dir,
            "decisions/decisions-007.md",
            "---\nid: decisions-007\ntitle: D007\nsummary: s\nrelated:\n  - decisions-008\n---\nBody.\n",
        )
        _write_codex_doc(
            project_dir,
            "decisions/decisions-008.md",
            "---\nid: decisions-008\ntitle: D008\nsummary: s\nrelated:\n  - decisions-007\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "codex"])

        assert "broken_related_link" not in result.output, result.output
        assert result.exit_code == 0, result.output

    def test_health_codex_two_missing_related_two_error_lines(self, runner, project_dir):
        """lore health reports one error line per missing related ID when multiple are broken."""
        _write_codex_doc(
            project_dir,
            "doc-multi.md",
            "---\nid: doc-multi\ntitle: Multi\nsummary: s\nrelated:\n  - missing-a\n  - missing-b\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "codex"])

        lines = result.output.splitlines()
        broken_lines = [line for line in lines if "broken_related_link" in line]
        assert len(broken_lines) == 2

    def test_health_codex_no_related_field_no_broken_link_in_output(self, runner, project_dir):
        """lore health --scope codex does not output broken_related_link for doc with no related field."""
        _write_codex_doc(
            project_dir,
            "no-related.md",
            "---\nid: no-related\ntitle: No Related\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "codex"])

        assert "broken_related_link" not in result.output, result.output


# ---------------------------------------------------------------------------
# US-005: Missing id frontmatter — exact output format and exit code
# Exercises: lore codex show conceptual-workflows-health
# ---------------------------------------------------------------------------


class TestHealthMissingIdFrontmatter:
    """lore health reports missing_frontmatter errors when codex docs lack id field."""

    def test_health_codex_missing_id_exits_one(self, runner, project_dir):
        """lore health --scope codex exits 1 when a codex doc is missing id field."""
        # Exercises: lore codex show conceptual-workflows-health
        _write_codex_doc(
            project_dir,
            "decisions/orphan.md",
            "---\ntitle: Orphan\nsummary: Test\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "codex"])

        assert result.exit_code == 1, result.output

    def test_health_codex_missing_id_exact_output_line(self, runner, project_dir):
        """lore health --scope codex outputs exact missing_frontmatter line with relative filepath."""
        # Exercises: lore codex show conceptual-workflows-health
        _write_codex_doc(
            project_dir,
            "decisions/orphan.md",
            "---\ntitle: Orphan\nsummary: Test\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "codex"])

        expected = "ERROR  codex  decisions/orphan.md  missing_frontmatter: field 'id' absent"
        assert expected in result.output, f"Expected line not found.\nOutput:\n{result.output}"

    def test_health_codex_all_valid_ids_no_missing_frontmatter_line(self, runner, project_dir):
        """lore health --scope codex does not output missing_frontmatter when all docs have id."""
        # Exercises: lore codex show conceptual-workflows-health
        _write_codex_doc(
            project_dir,
            "valid-a.md",
            "---\nid: valid-a\ntitle: Valid A\nsummary: s\nrelated:\n  - valid-b\n---\nBody.\n",
        )
        _write_codex_doc(
            project_dir,
            "valid-b.md",
            "---\nid: valid-b\ntitle: Valid B\nsummary: s\nrelated:\n  - valid-a\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "codex"])

        assert "missing_frontmatter" not in result.output, result.output
        assert result.exit_code == 0, result.output

    def test_health_codex_empty_frontmatter_block_exits_one(self, runner, project_dir):
        """lore health --scope codex exits 1 for codex file with empty frontmatter block."""
        # Exercises: lore codex show conceptual-workflows-health
        _write_codex_doc(
            project_dir,
            "empty-fm.md",
            "---\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "codex"])

        assert result.exit_code == 1, result.output
        assert "missing_frontmatter" in result.output

    def test_health_codex_no_frontmatter_at_all_exits_one(self, runner, project_dir):
        """lore health --scope codex exits 1 for codex file with no frontmatter delimiters."""
        # Exercises: lore codex show conceptual-workflows-health
        _write_codex_doc(
            project_dir,
            "no-fm.md",
            "Just plain text with no frontmatter at all.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "codex"])

        assert result.exit_code == 1, result.output
        assert "missing_frontmatter" in result.output


# ---------------------------------------------------------------------------
# US-006: Island node warning — exact output format and exit code
# Exercises: lore codex show conceptual-workflows-health
# ---------------------------------------------------------------------------


class TestHealthIslandNodeWarning:
    """lore health reports island_node warnings for codex docs with no inbound links."""

    def test_health_codex_island_node_exact_output_line(self, runner, project_dir):
        """lore health --scope codex outputs exact island_node warning line."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 1: proposals-draft has no inbound links
        _write_codex_doc(
            project_dir,
            "proposals-draft.md",
            "---\nid: proposals-draft\ntitle: Proposals Draft\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "codex"])

        expected = "WARNING  codex  proposals-draft  island_node: no documents link here"
        assert expected in result.output, f"Expected line not found.\nOutput:\n{result.output}"

    def test_health_codex_island_node_exits_zero(self, runner, project_dir):
        """lore health --scope codex exits 0 when only island_node warnings exist."""
        # Exercises: lore codex show conceptual-workflows-health
        _write_codex_doc(
            project_dir,
            "proposals-draft.md",
            "---\nid: proposals-draft\ntitle: Proposals Draft\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "codex"])

        assert result.exit_code == 0, result.output

    def test_health_codex_linked_doc_no_island_warning(self, runner, project_dir):
        """lore health --scope codex does not emit island_node for a doc that is referenced."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 2: decisions-007 is referenced by decisions-008
        _write_codex_doc(
            project_dir,
            "decisions/decisions-007.md",
            "---\nid: decisions-007\ntitle: D007\nsummary: s\n---\nBody.\n",
        )
        _write_codex_doc(
            project_dir,
            "decisions/decisions-008.md",
            "---\nid: decisions-008\ntitle: D008\nsummary: s\nrelated:\n  - decisions-007\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "codex"])

        lines = result.output.splitlines()
        island_lines_007 = [
            line for line in lines if "island_node" in line and "decisions-007" in line
        ]
        assert island_lines_007 == [], f"Unexpected island_node for decisions-007.\nOutput:\n{result.output}"

    def test_health_codex_single_doc_island_warning(self, runner, project_dir):
        """lore health --scope codex emits island_node warning for the only codex doc."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 3: single doc with id solo-doc
        _write_codex_doc(
            project_dir,
            "solo-doc.md",
            "---\nid: solo-doc\ntitle: Solo\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "codex"])

        expected = "WARNING  codex  solo-doc  island_node: no documents link here"
        assert expected in result.output, f"Expected line not found.\nOutput:\n{result.output}"

    def test_health_codex_island_plus_broken_link_exits_one(self, runner, project_dir):
        """lore health --scope codex exits 1 and reports both island_node and broken_related_link."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 4: island node + broken related link → error dominates → exit 1
        _write_codex_doc(
            project_dir,
            "island.md",
            "---\nid: island\ntitle: Island\nsummary: s\n---\nBody.\n",
        )
        _write_codex_doc(
            project_dir,
            "broken.md",
            "---\nid: broken\ntitle: Broken\nsummary: s\nrelated:\n  - nonexistent-id\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "codex"])

        assert result.exit_code == 1, result.output
        assert "WARNING" in result.output
        assert "island_node" in result.output
        assert "ERROR" in result.output
        assert "broken_related_link" in result.output


# ---------------------------------------------------------------------------
# US-007: Artifact missing frontmatter — exact output format and exit code
# Exercises: lore codex show conceptual-workflows-health
# ---------------------------------------------------------------------------


class TestHealthArtifactMissingFrontmatter:
    """lore health reports missing_frontmatter errors for artifact files lacking required fields."""

    def test_health_artifact_missing_id_exits_one(self, runner, project_dir):
        """lore health --scope artifacts exits 1 when artifact is missing id field."""
        # Exercises: lore codex show conceptual-workflows-health
        _write_artifact(
            project_dir,
            "fi-broken.md",
            "---\ntitle: Broken\nsummary: Test\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "artifacts"])

        assert result.exit_code == 1, result.output

    def test_health_artifact_missing_id_exact_output_line(self, runner, project_dir):
        """lore health --scope artifacts outputs exact missing_frontmatter line for missing id."""
        # Exercises: lore codex show conceptual-workflows-health
        _write_artifact(
            project_dir,
            "fi-broken.md",
            "---\ntitle: Broken\nsummary: Test\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "artifacts"])

        expected = "ERROR  artifacts  .lore/artifacts/fi-broken.md  missing_frontmatter: field 'id' absent"
        assert expected in result.output, f"Expected line not found.\nOutput:\n{result.output}"

    def test_health_artifact_missing_title_exact_output_line(self, runner, project_dir):
        """lore health --scope artifacts outputs exact missing_frontmatter line for missing title."""
        # Exercises: lore codex show conceptual-workflows-health
        _write_artifact(
            project_dir,
            "fi-broken.md",
            "---\nid: fi-broken\nsummary: Test\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "artifacts"])

        expected = "ERROR  artifacts  .lore/artifacts/fi-broken.md  missing_frontmatter: field 'title' absent"
        assert expected in result.output, f"Expected line not found.\nOutput:\n{result.output}"

    def test_health_artifact_missing_summary_exact_output_line(self, runner, project_dir):
        """lore health --scope artifacts outputs exact missing_frontmatter line for missing summary."""
        # Exercises: lore codex show conceptual-workflows-health
        _write_artifact(
            project_dir,
            "fi-broken.md",
            "---\nid: fi-broken\ntitle: Broken\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "artifacts"])

        expected = "ERROR  artifacts  .lore/artifacts/fi-broken.md  missing_frontmatter: field 'summary' absent"
        assert expected in result.output, f"Expected line not found.\nOutput:\n{result.output}"

    def test_health_artifact_all_fields_present_no_error(self, runner, project_dir):
        """lore health --scope artifacts does not report missing_frontmatter for valid artifact."""
        # Exercises: lore codex show conceptual-workflows-health
        _write_artifact(
            project_dir,
            "fi-valid.md",
            "---\nid: fi-valid\ntitle: Valid\nsummary: All present\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "artifacts"])

        lines = result.output.splitlines()
        missing_lines = [line for line in lines if "missing_frontmatter" in line and "fi-valid.md" in line]
        assert missing_lines == [], f"Unexpected missing_frontmatter for fi-valid.md.\nOutput:\n{result.output}"

    def test_health_artifact_empty_frontmatter_reports_one_line_for_id(self, runner, project_dir):
        """lore health --scope artifacts reports exactly one missing_frontmatter line for empty frontmatter (id first)."""
        # Exercises: lore codex show conceptual-workflows-health
        _write_artifact(
            project_dir,
            "fi-empty.md",
            "---\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "artifacts"])

        lines = result.output.splitlines()
        missing_lines = [line for line in lines if "missing_frontmatter" in line and "fi-empty.md" in line]
        assert len(missing_lines) == 1, f"Expected exactly one missing_frontmatter line.\nOutput:\n{result.output}"
        assert "field 'id' absent" in missing_lines[0]


# ---------------------------------------------------------------------------
# US-008: Orphaned doctrine files — exact output format and exit code
# Exercises: lore codex show conceptual-workflows-health
# ---------------------------------------------------------------------------


def _write_doctrine_yaml_only(project_dir, stem):
    """Write only the .yaml half of a doctrine pair (no .design.md)."""
    base = project_dir / ".lore" / "doctrines"
    base.mkdir(parents=True, exist_ok=True)
    (base / f"{stem}.yaml").write_text(
        f"id: {stem}\ntitle: {stem}\nsummary: s\nsteps: []\n"
    )


def _write_doctrine_design_only(project_dir, stem):
    """Write only the .design.md half of a doctrine pair (no .yaml)."""
    base = project_dir / ".lore" / "doctrines"
    base.mkdir(parents=True, exist_ok=True)
    (base / f"{stem}.design.md").write_text(
        f"---\nid: {stem}\ntitle: {stem}\nsummary: s\n---\nBody.\n"
    )


class TestHealthOrphanedDoctrine:
    """lore health --scope doctrines reports orphaned doctrine files."""

    def test_health_doctrines_yaml_without_design_md_exits_one(self, runner, project_dir):
        """lore health --scope doctrines exits 1 when .yaml has no matching .design.md."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 1: feat-auth.yaml exists, feat-auth.design.md does not
        _write_doctrine_yaml_only(project_dir, "feat-auth")

        result = runner.invoke(main, ["health", "--scope", "doctrines"])

        assert result.exit_code == 1, result.output

    def test_health_doctrines_yaml_without_design_md_exact_output_line(self, runner, project_dir):
        """lore health --scope doctrines stdout contains exact orphaned_file line for missing .design.md."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 1: feat-auth.yaml exists, feat-auth.design.md does not
        _write_doctrine_yaml_only(project_dir, "feat-auth")

        result = runner.invoke(main, ["health", "--scope", "doctrines"])

        expected = "ERROR  doctrines  feat-auth  orphaned_file: .design.md missing"
        assert expected in result.output, f"Expected line not found.\nOutput:\n{result.output}"

    def test_health_doctrines_design_md_without_yaml_exits_one(self, runner, project_dir):
        """lore health --scope doctrines exits 1 when .design.md has no matching .yaml."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 2: feat-auth.design.md exists, feat-auth.yaml does not
        _write_doctrine_design_only(project_dir, "feat-auth")

        result = runner.invoke(main, ["health", "--scope", "doctrines"])

        assert result.exit_code == 1, result.output

    def test_health_doctrines_design_md_without_yaml_exact_output_line(self, runner, project_dir):
        """lore health --scope doctrines stdout contains exact orphaned_file line for missing .yaml."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 2: feat-auth.design.md exists, feat-auth.yaml does not
        _write_doctrine_design_only(project_dir, "feat-auth")

        result = runner.invoke(main, ["health", "--scope", "doctrines"])

        expected = "ERROR  doctrines  feat-auth  orphaned_file: .yaml missing"
        assert expected in result.output, f"Expected line not found.\nOutput:\n{result.output}"

    def test_health_doctrines_complete_pair_no_orphaned_file_line(self, runner, project_dir):
        """lore health --scope doctrines does not output orphaned_file for feat-auth when both files exist."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 3: both feat-auth.yaml and feat-auth.design.md exist
        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            "id: feat-auth\ntitle: Auth\nsummary: s\nsteps: []\n",
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "doctrines"])

        lines = result.output.splitlines()
        orphan_lines = [line for line in lines if "orphaned_file" in line and "feat-auth" in line]
        assert orphan_lines == [], f"Unexpected orphaned_file line.\nOutput:\n{result.output}"

    def test_health_doctrines_multiple_orphans_both_lines_present(self, runner, project_dir):
        """lore health --scope doctrines reports separate errors for each orphaned doctrine file."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 4: feat-auth.yaml (no .design.md) AND feat-payments.design.md (no .yaml)
        _write_doctrine_yaml_only(project_dir, "feat-auth")
        _write_doctrine_design_only(project_dir, "feat-payments")

        result = runner.invoke(main, ["health", "--scope", "doctrines"])

        assert "ERROR  doctrines  feat-auth  orphaned_file: .design.md missing" in result.output, (
            f"feat-auth orphan line not found.\nOutput:\n{result.output}"
        )
        assert "ERROR  doctrines  feat-payments  orphaned_file: .yaml missing" in result.output, (
            f"feat-payments orphan line not found.\nOutput:\n{result.output}"
        )

    def test_health_doctrines_multiple_orphans_exits_one(self, runner, project_dir):
        """lore health --scope doctrines exits 1 when multiple doctrine files are orphaned."""
        # Exercises: lore codex show conceptual-workflows-health
        _write_doctrine_yaml_only(project_dir, "feat-auth")
        _write_doctrine_design_only(project_dir, "feat-payments")

        result = runner.invoke(main, ["health", "--scope", "doctrines"])

        assert result.exit_code == 1, result.output


# ---------------------------------------------------------------------------
# US-009: Broken knight refs in doctrine steps — exact output format and exit code
# Exercises: lore codex show conceptual-workflows-health
# ---------------------------------------------------------------------------


class TestHealthBrokenKnightRef:
    """lore health reports broken_knight_ref errors for doctrine steps naming missing knights."""

    def test_health_doctrine_broken_knight_ref_exits_one(self, runner, project_dir):
        """lore health exits 1 when doctrine step names a knight not found on disk."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 1: feat-auth.yaml step 2 names senior-engineer; no .md or .md.deleted
        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
                "  - id: step-1\n    title: Step 1\n"
                "  - id: step-2\n    title: Step 2\n    knight: senior-engineer\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health"])

        assert result.exit_code == 1, result.output

    def test_health_doctrine_broken_knight_ref_exact_output_line(self, runner, project_dir):
        """lore health --scope doctrines stdout contains exact broken_knight_ref line per US-009 spec."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 1: exact format: ERROR  doctrines  feat-auth  broken_knight_ref: 'senior-engineer' not found (step 2)
        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
                "  - id: step-1\n    title: Step 1\n"
                "  - id: step-2\n    title: Step 2\n    knight: senior-engineer\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "doctrines"])

        expected = "ERROR  doctrines  feat-auth  broken_knight_ref: 'senior-engineer' not found (step 2)"
        assert expected in result.output, f"Expected line not found.\nOutput:\n{result.output}"

    def test_health_doctrine_present_knight_no_broken_knight_ref(self, runner, project_dir):
        """lore health --scope doctrines does not output broken_knight_ref when knight file exists."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 2: tech-lead.md exists on disk
        _write_knight(project_dir, "tech-lead.md", "---\nid: tech-lead\ntitle: Tech Lead\nsummary: s\n---\nBody.\n")
        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
                "  - id: step-1\n    title: Step 1\n"
                "  - id: step-2\n    title: Step 2\n    knight: tech-lead\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "doctrines"])

        lines = result.output.splitlines()
        broken_lines = [line for line in lines if "broken_knight_ref" in line and "feat-auth" in line]
        assert broken_lines == [], f"Unexpected broken_knight_ref line.\nOutput:\n{result.output}"

    def test_health_doctrine_soft_deleted_knight_no_broken_knight_ref(self, runner, project_dir):
        """lore health --scope doctrines does not flag broken_knight_ref for soft-deleted knight."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 3: senior-engineer.md.deleted exists; no .md
        _write_knight(project_dir, "senior-engineer.md.deleted", "deleted")
        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
                "  - id: step-1\n    title: Step 1\n"
                "  - id: step-2\n    title: Step 2\n    knight: senior-engineer\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "doctrines"])

        lines = result.output.splitlines()
        broken_lines = [line for line in lines if "broken_knight_ref" in line and "feat-auth" in line]
        assert broken_lines == [], f"Unexpected broken_knight_ref for soft-deleted knight.\nOutput:\n{result.output}"

    def test_health_doctrine_multiple_broken_knight_refs_separate_lines(self, runner, project_dir):
        """lore health --scope doctrines reports separate error lines for each broken knight ref step."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 4: step 1 missing-a, step 3 missing-b → two separate lines
        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
                "  - id: step-1\n    title: Step 1\n    knight: missing-a\n"
                "  - id: step-2\n    title: Step 2\n"
                "  - id: step-3\n    title: Step 3\n    knight: missing-b\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "doctrines"])

        assert "broken_knight_ref: 'missing-a' not found (step 1)" in result.output, (
            f"missing-a error line not found.\nOutput:\n{result.output}"
        )
        assert "broken_knight_ref: 'missing-b' not found (step 3)" in result.output, (
            f"missing-b error line not found.\nOutput:\n{result.output}"
        )

    def test_health_doctrine_broken_knight_ref_scope_doctrines_exits_one(self, runner, project_dir):
        """lore health --scope doctrines exits 1 when doctrine has broken knight ref."""
        # Exercises: lore codex show conceptual-workflows-health
        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
                "  - id: step-2\n    title: Step 2\n    knight: senior-engineer\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "doctrines"])

        assert result.exit_code == 1, result.output


# ---------------------------------------------------------------------------
# US-010: Broken artifact ref in doctrine step notes
# Exercises: conceptual-workflows-health
# ---------------------------------------------------------------------------


class TestHealthDoctrineArtifactRef:
    """lore health --scope doctrines detects broken artifact references in step notes."""

    def test_health_doctrine_broken_artifact_ref_exits_one(self, runner, project_dir):
        """lore health --scope doctrines exits 1 when step notes reference missing artifact."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 1: step 3 notes has fi-prd-v2, no such artifact exists
        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
                "  - id: step-1\n    title: Step 1\n"
                "  - id: step-2\n    title: Step 2\n"
                "  - id: step-3\n    title: Step 3\n    notes: 'see artifact: fi-prd-v2'\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "doctrines"])

        assert result.exit_code == 1, result.output

    def test_health_doctrine_broken_artifact_ref_error_line_in_output(self, runner, project_dir):
        """lore health --scope doctrines output contains broken_artifact_ref error line."""
        # Exercises: lore codex show conceptual-workflows-health
        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
                "  - id: step-1\n    title: Step 1\n"
                "  - id: step-2\n    title: Step 2\n"
                "  - id: step-3\n    title: Step 3\n    notes: 'see artifact: fi-prd-v2'\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "doctrines"])

        assert "broken_artifact_ref" in result.output, result.output
        assert "fi-prd-v2" in result.output, result.output
        assert "feat-auth" in result.output, result.output

    def test_health_doctrine_broken_artifact_ref_exact_output_format(self, runner, project_dir):
        """lore health --scope doctrines output line matches exact AC format."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 1: ERROR  doctrines  feat-auth  broken_artifact_ref: 'fi-prd-v2' not found (step 3)
        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
                "  - id: step-1\n    title: Step 1\n"
                "  - id: step-2\n    title: Step 2\n"
                "  - id: step-3\n    title: Step 3\n    notes: 'see artifact: fi-prd-v2'\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "doctrines"])

        assert "broken_artifact_ref: 'fi-prd-v2' not found (step 3)" in result.output, (
            f"Expected exact error format not found.\nOutput:\n{result.output}"
        )

    def test_health_doctrine_present_artifact_no_broken_artifact_ref(self, runner, project_dir):
        """lore health --scope doctrines does not report broken_artifact_ref when artifact exists."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 2: fi-prd-template exists → no error
        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
                "  - id: step-3\n    title: Step 3\n    notes: see fi-prd-template\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )
        _write_artifact(
            project_dir,
            "fi-prd-template.md",
            "---\nid: fi-prd-template\ntitle: PRD Template\nsummary: s\n---\nContent.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "doctrines"])

        lines = result.output.splitlines()
        broken_lines = [
            line for line in lines if "broken_artifact_ref" in line and "feat-auth" in line
        ]
        assert broken_lines == [], f"Unexpected broken_artifact_ref line.\nOutput:\n{result.output}"

    def test_health_doctrine_step_no_notes_no_broken_artifact_ref(self, runner, project_dir):
        """lore health --scope doctrines does not report broken_artifact_ref when step has no notes."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 3: step has no notes field → no broken_artifact_ref error
        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
                "  - id: step-1\n    title: Step 1\n"
                "  - id: step-2\n    title: Step 2\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "doctrines"])

        lines = result.output.splitlines()
        broken_lines = [line for line in lines if "broken_artifact_ref" in line]
        assert broken_lines == [], f"Unexpected broken_artifact_ref line.\nOutput:\n{result.output}"

    def test_health_doctrine_notes_no_fi_pattern_no_broken_artifact_ref(self, runner, project_dir):
        """lore health --scope doctrines does not report broken_artifact_ref for non-fi-pattern notes."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 4: notes = "See the design doc for details." → no fi-* token
        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
                "  - id: step-1\n    title: Step 1\n    notes: See the design doc for details.\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "doctrines"])

        lines = result.output.splitlines()
        broken_lines = [line for line in lines if "broken_artifact_ref" in line]
        assert broken_lines == [], f"Unexpected broken_artifact_ref line.\nOutput:\n{result.output}"

    def test_health_doctrine_multiple_missing_artifact_refs_two_error_lines(self, runner, project_dir):
        """lore health --scope doctrines reports separate error lines for each missing artifact ref."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 5: step 2 notes has fi-missing-a and fi-missing-b → two error lines
        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
                "  - id: step-1\n    title: Step 1\n"
                "  - id: step-2\n    title: Step 2\n    notes: fi-missing-a and fi-missing-b\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "doctrines"])

        assert "broken_artifact_ref: 'fi-missing-a' not found (step 2)" in result.output, (
            f"fi-missing-a error line not found.\nOutput:\n{result.output}"
        )
        assert "broken_artifact_ref: 'fi-missing-b' not found (step 2)" in result.output, (
            f"fi-missing-b error line not found.\nOutput:\n{result.output}"
        )


# ---------------------------------------------------------------------------
# US-011: Missing knight file referenced by active missions
# Exercises: conceptual-workflows-health
# ---------------------------------------------------------------------------


class TestHealthKnightMissingFile:
    """lore health --scope knights detects active missions referencing missing knight files."""

    def test_health_knight_missing_file_exits_one(self, runner, project_dir):
        """lore health exits 1 when active mission references a knight not found on disk."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 1: mission m-0042 knight="ghost-knight"; detail says "referenced by m-0042 but not found on disk"
        from tests.conftest import insert_mission, insert_quest

        insert_quest(project_dir, "q-0042", "Quest 42")
        insert_mission(project_dir, "m-0042", "q-0042", "Mission 42", knight="ghost-knight")

        result = runner.invoke(main, ["health", "--scope", "knights"])

        # AC: exit 1 AND detail says "referenced by ... but not found on disk"
        assert result.exit_code == 1, result.output
        assert "referenced by" in result.output and "not found on disk" in result.output, (
            f"Expected 'referenced by ... not found on disk' in output.\nOutput:\n{result.output}"
        )

    def test_health_knight_missing_file_output_exact_detail_format(self, runner, project_dir):
        """lore health stdout contains exact AC detail: 'referenced by <id> but not found on disk'."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 1 exact output: ERROR  knights  ghost-knight  missing_file: referenced by m-0043 but not found on disk
        from tests.conftest import insert_mission, insert_quest

        insert_quest(project_dir, "q-0043", "Quest 43")
        insert_mission(project_dir, "m-0043", "q-0043", "Mission 43", knight="ghost-knight")

        result = runner.invoke(main, ["health", "--scope", "knights"])

        assert "referenced by" in result.output, (
            f"Expected 'referenced by' in output.\nOutput:\n{result.output}"
        )
        assert "not found on disk" in result.output, (
            f"Expected 'not found on disk' in output.\nOutput:\n{result.output}"
        )
        assert "m-0043" in result.output, (
            f"Expected mission ID m-0043 in output.\nOutput:\n{result.output}"
        )

    def test_health_knight_missing_file_output_contains_mission_id(self, runner, project_dir):
        """lore health stdout contains the referencing mission ID in the missing_file line."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 1: detail must include mission ID per AC
        from tests.conftest import insert_mission, insert_quest

        insert_quest(project_dir, "q-0044", "Quest 44")
        insert_mission(project_dir, "m-0044", "q-0044", "Mission 44", knight="ghost-knight")

        result = runner.invoke(main, ["health", "--scope", "knights"])

        assert "m-0044" in result.output, (
            f"Mission ID m-0044 not in output.\nOutput:\n{result.output}"
        )

    def test_health_knight_multiple_missions_same_missing_knight_one_error_line(
        self, runner, project_dir
    ):
        """lore health --scope knights reports one error line with all referencing mission IDs."""
        # Exercises: lore codex show conceptual-workflows-health
        # Scenario 4: m-0010, m-0011, m-0012 all reference ghost-knight → one ERROR line
        # AND that error line's detail contains all three mission IDs
        from tests.conftest import insert_mission, insert_quest

        insert_quest(project_dir, "q-0047", "Quest 47")
        insert_mission(project_dir, "m-0010", "q-0047", "Mission 10", knight="ghost-knight")
        insert_mission(project_dir, "m-0011", "q-0047", "Mission 11", knight="ghost-knight")
        insert_mission(project_dir, "m-0012", "q-0047", "Mission 12", knight="ghost-knight")

        result = runner.invoke(main, ["health", "--scope", "knights"])

        error_lines = [
            line for line in result.output.splitlines()
            if "ERROR  knights  ghost-knight  missing_file" in line
        ]
        assert len(error_lines) == 1, (
            f"Expected 1 error line, got {len(error_lines)}.\nOutput:\n{result.output}"
        )
        # AC: single error line detail must list all referencing mission IDs
        assert "m-0010" in error_lines[0], f"m-0010 not in error line: {error_lines[0]}"
        assert "m-0011" in error_lines[0], f"m-0011 not in error line: {error_lines[0]}"
        assert "m-0012" in error_lines[0], f"m-0012 not in error line: {error_lines[0]}"


# ---------------------------------------------------------------------------
# US-012: Watcher broken doctrine ref E2E scenarios
# Exercises: conceptual-workflows-health — watcher action doctrine validation
# ---------------------------------------------------------------------------


class TestHealthWatcherBrokenDoctrineRef:
    """lore health reports broken_doctrine_ref for watcher actions naming missing doctrines."""

    def test_health_watcher_incomplete_doctrine_pair_reports_broken_ref(
        self, runner, project_dir
    ):
        """lore health --scope watchers reports broken_doctrine_ref when doctrine has only .design.md."""
        # Exercises: lore codex show conceptual-workflows-health
        # Requires complete pair (both .yaml AND .design.md) to be considered valid
        # This test MUST fail until _build_doctrine_name_index enforces complete pairs
        doctrine_path = project_dir / ".lore" / "doctrines"
        doctrine_path.mkdir(parents=True, exist_ok=True)
        (doctrine_path / "feat-auth.design.md").write_text(
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n"
        )
        # No feat-auth.yaml — incomplete pair
        _write_watcher(
            project_dir,
            "on-quest-close.yaml",
            "id: on-quest-close\ntitle: On Close\nsummary: s\naction: feat-auth\n",
        )

        result = runner.invoke(main, ["health", "--scope", "watchers"])

        assert "broken_doctrine_ref" in result.output, (
            f"Expected broken_doctrine_ref for incomplete doctrine pair.\nOutput:\n{result.output}"
        )
        assert result.exit_code == 1, result.output


# ---------------------------------------------------------------------------
# US-013: Watcher invalid YAML E2E scenarios
# Exercises: conceptual-workflows-health — watcher YAML parse validation
# ---------------------------------------------------------------------------


class TestHealthWatcherInvalidYaml:
    """lore health reports invalid_yaml with 'parse failed at line N' detail for unparseable watchers."""

    def test_health_watcher_invalid_yaml_output_contains_parse_failed_at_line_7(
        self, runner, project_dir
    ):
        """lore health --scope watchers output contains 'parse failed at line 7' for error on line 7."""
        # Scenario 1: exact phrase 'parse failed at line 7' must appear in output
        content = (
            "id: on-sprint-start\n"
            "title: On Sprint Start\n"
            "summary: Fires on sprint start\n"
            "trigger: sprint_start\n"
            "action: some-doctrine\n"
            "tags:\n"
            "  - key: [unmatched bracket\n"
        )
        _write_watcher(project_dir, "on-sprint-start.yaml", content)

        result = runner.invoke(main, ["health", "--scope", "watchers"])

        assert "parse failed at line 7" in result.output, (
            f"Expected 'parse failed at line 7' in output.\nOutput:\n{result.output}"
        )

    def test_health_watcher_invalid_yaml_scope_watchers_exits_one(
        self, runner, project_dir
    ):
        """lore health --scope watchers exits 1 and output contains 'parse failed at line'."""
        # Scenario 1: exit 1 AND new detail format both required
        content = (
            "id: on-sprint-start\n"
            "title: On Sprint Start\n"
            "summary: Fires on sprint start\n"
            "trigger: sprint_start\n"
            "action: some-doctrine\n"
            "tags:\n"
            "  - key: [unmatched bracket\n"
        )
        _write_watcher(project_dir, "on-sprint-start.yaml", content)

        result = runner.invoke(main, ["health", "--scope", "watchers"])

        assert result.exit_code == 1, result.output
        assert "parse failed at line" in result.output, (
            f"Expected 'parse failed at line' in output.\nOutput:\n{result.output}"
        )

    def test_health_watcher_valid_yaml_no_parse_failed_in_output(
        self, runner, project_dir
    ):
        """lore health --scope watchers output does not contain 'parse failed at line' for valid YAML."""
        # Scenario 2: valid watcher → no parse failed detail
        _write_watcher(
            project_dir,
            "on-sprint-start.yaml",
            "id: on-sprint-start\ntitle: On Sprint Start\nsummary: s\naction: some-doctrine\n",
        )

        result = runner.invoke(main, ["health", "--scope", "watchers"])

        assert "parse failed at line" not in result.output, (
            f"Expected no 'parse failed at line' for valid watcher.\nOutput:\n{result.output}"
        )

    def test_health_watcher_soft_deleted_no_parse_failed_in_output(
        self, runner, project_dir
    ):
        """lore health --scope watchers does not report 'parse failed at line' for .yaml.deleted files."""
        # Scenario 3: .yaml.deleted with invalid YAML → no parse failed detail
        _write_watcher(
            project_dir,
            "on-sprint-start.yaml.deleted",
            "id: on-sprint-start\ntitle: Bad\n  broken: : yaml\n",
        )

        result = runner.invoke(main, ["health", "--scope", "watchers"])

        assert "parse failed at line" not in result.output, (
            f"Soft-deleted file should not produce 'parse failed at line'.\nOutput:\n{result.output}"
        )

    def test_health_multiple_invalid_watcher_files_two_parse_failed_lines(
        self, runner, project_dir
    ):
        """lore health --scope watchers reports 'parse failed at line' for each invalid watcher file."""
        # Scenario 4: two invalid watcher files → two separate 'parse failed at line' lines
        _write_watcher(
            project_dir,
            "watcher-alpha.yaml",
            "id: alpha\ntitle: Alpha\n  broken: : yaml\n",
        )
        _write_watcher(
            project_dir,
            "watcher-beta.yaml",
            "id: beta\ntitle: Beta\n  broken: : yaml\n",
        )

        result = runner.invoke(main, ["health", "--scope", "watchers"])

        parse_failed_lines = [
            line for line in result.output.splitlines() if "parse failed at line" in line
        ]
        assert len(parse_failed_lines) == 2, (
            f"Expected 2 'parse failed at line' lines, got {len(parse_failed_lines)}.\n"
            f"Output:\n{result.output}"
        )

    def test_health_multiple_invalid_watcher_files_each_file_named(
        self, runner, project_dir
    ):
        """lore health --scope watchers names each invalid watcher with 'parse failed at line' detail."""
        _write_watcher(
            project_dir,
            "watcher-alpha.yaml",
            "id: alpha\ntitle: Alpha\n  broken: : yaml\n",
        )
        _write_watcher(
            project_dir,
            "watcher-beta.yaml",
            "id: beta\ntitle: Beta\n  broken: : yaml\n",
        )

        result = runner.invoke(main, ["health", "--scope", "watchers"])

        parse_failed_lines = [
            line for line in result.output.splitlines() if "parse failed at line" in line
        ]
        named_alpha = any("watcher-alpha" in line for line in parse_failed_lines)
        named_beta = any("watcher-beta" in line for line in parse_failed_lines)
        assert named_alpha, (
            f"Expected 'watcher-alpha' in a 'parse failed at line' line.\nOutput:\n{result.output}"
        )
        assert named_beta, (
            f"Expected 'watcher-beta' in a 'parse failed at line' line.\nOutput:\n{result.output}"
        )


# ---------------------------------------------------------------------------
# US-014: Write markdown health report to codex/transient on every run
# Exercises: conceptual-workflows-health — report file always written
# ---------------------------------------------------------------------------


class TestHealthReportFileWrittenWithErrors:
    """US-014 Scenario 1: Run with errors → report file written with issues in markdown table."""

    def test_health_errors_run_creates_report_file(self, runner, project_dir):
        """lore health with errors creates a health-*.md file in .lore/codex/transient/."""
        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\n"
                "steps:\n  - knight: nonexistent-knight-us014\n    mission: impl\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health"])

        transient_dir = project_dir / ".lore" / "codex" / "transient"
        report_files = list(transient_dir.glob("health-*.md"))
        assert len(report_files) >= 1, (
            f"No report file found after error run. Output: {result.output}"
        )

    def test_health_errors_run_report_contains_markdown_table(self, runner, project_dir):
        """lore health with errors: report file contains markdown table with error row."""
        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\n"
                "steps:\n  - knight: nonexistent-knight-us014\n    mission: impl\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        runner.invoke(main, ["health"])

        transient_dir = project_dir / ".lore" / "codex" / "transient"
        report_files = list(transient_dir.glob("health-*.md"))
        assert report_files, "No report file found"
        content = report_files[0].read_text()
        assert "|" in content, f"Report file has no markdown table. Content:\n{content}"
        assert "feat-auth" in content or "nonexistent-knight" in content, (
            f"Report missing expected error detail. Content:\n{content}"
        )

    def test_health_errors_run_exits_one(self, runner, project_dir):
        """lore health exits 1 when there are broken knight refs."""
        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\n"
                "steps:\n  - knight: nonexistent-knight-us014\n    mission: impl\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health"])

        assert result.exit_code == 1, result.output


class TestHealthReportFileWrittenCleanRun:
    """US-014 Scenario 2: Clean run → report file written with 'No issues found.'"""

    def test_health_clean_run_creates_report_file(self, runner, project_dir):
        """lore health on a clean project creates a health-*.md file in .lore/codex/transient/."""
        result = runner.invoke(main, ["health"])

        transient_dir = project_dir / ".lore" / "codex" / "transient"
        report_files = list(transient_dir.glob("health-*.md"))
        assert len(report_files) >= 1, (
            f"No report file found after clean run. Output: {result.output}"
        )

    def test_health_clean_run_report_contains_no_issues_found(self, runner, project_dir):
        """lore health clean run: report file contains 'No issues found.'"""
        runner.invoke(main, ["health"])

        transient_dir = project_dir / ".lore" / "codex" / "transient"
        report_files = list(transient_dir.glob("health-*.md"))
        assert report_files, "No report file found"
        content = report_files[0].read_text()
        assert "No issues found." in content, (
            f"Report file missing 'No issues found.'. Content:\n{content}"
        )


class TestHealthReportFileWrittenJsonFlag:
    """US-014 Scenario 3: --json run → report file still written."""

    def test_health_json_flag_still_creates_report_file(self, runner, project_dir):
        """lore health --json creates a health-*.md file (report not suppressed by --json)."""
        runner.invoke(main, ["health", "--json"])

        transient_dir = project_dir / ".lore" / "codex" / "transient"
        report_files = list(transient_dir.glob("health-*.md"))
        assert len(report_files) >= 1, (
            "No report file found after --json run; report must be written regardless of --json."
        )


class TestHealthReportFilenameFormat:
    """US-014 Scenario 4: Report filename matches UTC timestamp format."""

    def test_health_report_filename_matches_timestamp_pattern(self, runner, project_dir):
        """lore health: report filename matches health-YYYY-MM-DDTHH-MM-SS.md pattern."""
        import re

        runner.invoke(main, ["health"])

        transient_dir = project_dir / ".lore" / "codex" / "transient"
        report_files = list(transient_dir.glob("health-*.md"))
        assert report_files, "No report file found"
        pattern = re.compile(r"^health-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}\.md$")
        for f in report_files:
            assert pattern.match(f.name), (
                f"Report filename '{f.name}' does not match expected pattern "
                r"health-YYYY-MM-DDTHH-MM-SS.md"
            )


class TestHealthReportFileFrontmatter:
    """US-014 Scenario 5: Report file has valid frontmatter with id, title, and summary."""

    def test_health_report_file_has_yaml_frontmatter_with_required_keys(self, runner, project_dir):
        """lore health: report file has YAML frontmatter containing id, title, and summary."""
        runner.invoke(main, ["health"])

        transient_dir = project_dir / ".lore" / "codex" / "transient"
        report_files = list(transient_dir.glob("health-*.md"))
        assert report_files, "No report file found"
        content = report_files[0].read_text()
        assert content.startswith("---\n"), (
            "Report file must begin with YAML frontmatter '---'"
        )
        lines = content.splitlines()
        closing_index = lines.index("---", 1)
        frontmatter_text = "\n".join(lines[1:closing_index])
        assert "id:" in frontmatter_text, (
            f"Frontmatter missing 'id' field. Frontmatter:\n{frontmatter_text}"
        )
        assert "title:" in frontmatter_text, (
            f"Frontmatter missing 'title' field. Frontmatter:\n{frontmatter_text}"
        )
        assert "summary:" in frontmatter_text, (
            f"Frontmatter missing 'summary' field. Frontmatter:\n{frontmatter_text}"
        )


# ---------------------------------------------------------------------------
# US-015 Scenario 1: Issues present without --json → human-readable table row
# Exercises: conceptual-workflows-health
# ---------------------------------------------------------------------------


class TestHealthUS015HumanReadableTable:
    """US-015: lore health prints column-aligned issue rows when --json is not set."""

    def test_health_broken_knight_ref_human_readable_exact_line(self, runner, project_dir):
        """lore health stdout contains exact column-aligned ERROR line for broken_knight_ref."""
        # Given: feat-auth.yaml step 2 references knight senior-engineer (missing)
        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
                "  - id: step-1\n    title: Step 1\n"
                "  - id: step-2\n    title: Step 2\n    knight: senior-engineer\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health"])

        expected = "ERROR  doctrines  feat-auth  broken_knight_ref: 'senior-engineer' not found (step 2)"
        assert expected in result.output, (
            f"Expected exact column-aligned ERROR line not found.\nOutput:\n{result.output}"
        )

    def test_health_broken_knight_ref_human_readable_exits_one(self, runner, project_dir):
        """lore health exits 1 when a broken_knight_ref error is present."""
        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
                "  - id: step-2\n    title: Step 2\n    knight: senior-engineer\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health"])

        assert result.exit_code == 1, result.output


# ---------------------------------------------------------------------------
# US-015 Scenario 2: Issues present with --json → valid JSON envelope on stdout
# Exercises: conceptual-workflows-health
# ---------------------------------------------------------------------------


class TestHealthUS015JsonEnvelope:
    """US-015: lore health --json outputs a valid JSON envelope with has_errors and issues array."""

    def test_health_json_envelope_has_errors_true_with_broken_knight_ref(self, runner, project_dir):
        """lore health --json has_errors is True when broken_knight_ref error exists."""
        import json

        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
                "  - id: step-2\n    title: Step 2\n    knight: senior-engineer\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--json"])

        data = json.loads(result.output)
        assert data["has_errors"] is True

    def test_health_json_envelope_issues_contains_broken_knight_ref_dict(self, runner, project_dir):
        """lore health --json issues array contains dict with all required fields for broken_knight_ref."""
        import json

        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
                "  - id: step-2\n    title: Step 2\n    knight: senior-engineer\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--json"])

        data = json.loads(result.output)
        assert len(data["issues"]) >= 1
        issue = next(
            (i for i in data["issues"] if i.get("check") == "broken_knight_ref"),
            None,
        )
        assert issue is not None, f"No broken_knight_ref issue found in: {data['issues']}"
        assert issue["severity"] == "error"
        assert issue["entity_type"] == "doctrines"
        assert issue["id"] == "feat-auth"
        assert issue["detail"] == "'senior-engineer' not found (step 2)"

    def test_health_json_envelope_issues_array_has_required_keys(self, runner, project_dir):
        """lore health --json each issue dict contains severity, entity_type, id, check, detail."""
        import json

        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
                "  - id: step-2\n    title: Step 2\n    knight: senior-engineer\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--json"])

        data = json.loads(result.output)
        required_keys = {"severity", "entity_type", "id", "check", "detail"}
        for issue in data["issues"]:
            assert required_keys <= set(issue.keys()), (
                f"Issue dict missing required keys. Got: {set(issue.keys())}"
            )

    def test_health_json_broken_knight_ref_exits_one(self, runner, project_dir):
        """lore health --json exits 1 when issues contain an error."""
        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
                "  - id: step-2\n    title: Step 2\n    knight: senior-engineer\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--json"])

        assert result.exit_code == 1, result.output


# ---------------------------------------------------------------------------
# US-015 Scenario 3: Clean run without --json → success message on stdout
# Exercises: conceptual-workflows-health
# ---------------------------------------------------------------------------


class TestHealthUS015CleanRunText:
    """US-015: lore health on clean project prints success message and exits 0."""

    def test_health_clean_project_prints_health_check_passed(self, runner, project_dir):
        """lore health clean project stdout contains 'Health check passed. No issues found.'"""
        result = runner.invoke(main, ["health"])

        assert "Health check passed. No issues found." in result.output, (
            f"Expected success message not found.\nOutput:\n{result.output}"
        )

    def test_health_clean_project_exits_zero(self, runner, project_dir):
        """lore health clean project exits 0."""
        result = runner.invoke(main, ["health"])

        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# US-015 Scenario 4: Clean run with --json → {"has_errors": false, "issues": []}
# Exercises: conceptual-workflows-health
# ---------------------------------------------------------------------------


class TestHealthUS015CleanRunJson:
    """US-015: lore health --json on clean project returns exact JSON envelope."""

    def test_health_clean_json_has_errors_false(self, runner, project_dir):
        """lore health --json clean project: has_errors is false."""
        import json

        result = runner.invoke(main, ["health", "--json"])

        data = json.loads(result.output)
        assert data["has_errors"] is False

    def test_health_clean_json_issues_empty_list(self, runner, project_dir):
        """lore health --json clean project: issues is an empty list."""
        import json

        result = runner.invoke(main, ["health", "--json"])

        data = json.loads(result.output)
        assert data["issues"] == []

    def test_health_clean_json_exits_zero(self, runner, project_dir):
        """lore health --json clean project exits 0."""
        result = runner.invoke(main, ["health", "--json"])

        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# US-015 Scenario 5: Warning present without --json → WARNING line in table
# Exercises: conceptual-workflows-health
# ---------------------------------------------------------------------------


class TestHealthUS015WarningInTable:
    """US-015: lore health prints WARNING line for island_node warning and exits 0."""

    def test_health_island_node_warning_human_readable_exact_line(self, runner, project_dir):
        """lore health stdout contains exact WARNING line for island_node."""
        _write_codex_doc(
            project_dir,
            "orphan-doc.md",
            "---\nid: orphan-doc\ntitle: Orphan\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "codex"])

        expected = "WARNING  codex  orphan-doc  island_node: no documents link here"
        assert expected in result.output, (
            f"Expected WARNING line not found.\nOutput:\n{result.output}"
        )

    def test_health_island_node_warning_exits_zero(self, runner, project_dir):
        """lore health exits 0 when only island_node warnings exist (no errors)."""
        _write_codex_doc(
            project_dir,
            "orphan-doc.md",
            "---\nid: orphan-doc\ntitle: Orphan\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--scope", "codex"])

        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# US-015 Scenario 6: --json output does not contain any non-JSON text
# Exercises: conceptual-workflows-health
# ---------------------------------------------------------------------------


class TestHealthUS015JsonOnlyOutput:
    """US-015: lore health --json entire stdout is parseable as a single JSON object."""

    def test_health_json_output_entire_stdout_parseable(self, runner, project_dir):
        """lore health --json: entire stdout content is parseable as a single JSON object."""
        import json

        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
                "  - id: step-2\n    title: Step 2\n    knight: senior-engineer\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--json"])

        # Strip trailing newline — click.echo adds one — then parse
        stripped = result.output.strip()
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise AssertionError(
                f"stdout is not a single JSON object: {exc}\nOutput:\n{result.output}"
            )
        assert isinstance(data, dict), "JSON output must be an object, not an array or scalar"

    def test_health_json_output_no_extra_lines_before_or_after(self, runner, project_dir):
        """lore health --json: no extra text lines appear before or after the JSON object."""
        import json

        _write_doctrine_pair(
            project_dir,
            "feat-auth",
            (
                "id: feat-auth\ntitle: Auth\nsummary: s\nsteps:\n"
                "  - id: step-2\n    title: Step 2\n    knight: senior-engineer\n"
            ),
            "---\nid: feat-auth\ntitle: Auth\nsummary: s\n---\nBody.\n",
        )

        result = runner.invoke(main, ["health", "--json"])

        non_empty_lines = [line for line in result.output.splitlines() if line.strip()]
        assert len(non_empty_lines) == 1, (
            f"Expected exactly 1 non-empty line in JSON output. Got {len(non_empty_lines)} lines:\n"
            + "\n".join(non_empty_lines)
        )
        json.loads(non_empty_lines[0])  # Must be valid JSON


# ---------------------------------------------------------------------------
# US-016: Python API — health_check() returns HealthReport with no stdout
# Exercises: conceptual-workflows-health — Python API used by Realm orchestrator
# ---------------------------------------------------------------------------


class TestHealthCheckPythonAPINoStdout:
    """Scenario 1: health_check(project_root, scope=['codex']) returns HealthReport, no stdout."""

    def test_health_check_python_api_returns_health_report(self, project_dir):
        """health_check returns a HealthReport object when called as Python API."""
        # Exercises: lore codex show conceptual-workflows-health
        result = health_check(project_dir, scope=["codex"])
        assert isinstance(result, HealthReport)

    def test_health_check_python_api_no_stdout_with_broken_related_link(self, project_dir, capsys):
        """health_check produces no stdout when a codex doc has a broken related link."""
        # Exercises: lore codex show conceptual-workflows-health
        _write_codex_doc(
            project_dir,
            "broken-link.md",
            "---\nid: broken-link\ntitle: Broken\nsummary: s\nrelated:\n  - nonexistent-doc-us016\n---\nBody.\n",
        )

        health_check(project_dir, scope=["codex"])

        captured = capsys.readouterr()
        assert captured.out == "", f"Expected empty stdout, got: {captured.out!r}"

    def test_health_check_python_api_has_errors_true_with_broken_link(self, project_dir):
        """health_check returns has_errors=True when codex doc has broken related link."""
        # Exercises: lore codex show conceptual-workflows-health
        _write_codex_doc(
            project_dir,
            "broken-link.md",
            "---\nid: broken-link\ntitle: Broken\nsummary: s\nrelated:\n  - nonexistent-doc-us016\n---\nBody.\n",
        )

        report = health_check(project_dir, scope=["codex"])
        assert report.has_errors is True

    def test_health_check_python_api_error_entity_type_is_codex(self, project_dir):
        """health_check errors[0].entity_type == 'codex' for broken related link."""
        # Exercises: lore codex show conceptual-workflows-health
        _write_codex_doc(
            project_dir,
            "broken-link.md",
            "---\nid: broken-link\ntitle: Broken\nsummary: s\nrelated:\n  - nonexistent-doc-us016\n---\nBody.\n",
        )

        report = health_check(project_dir, scope=["codex"])
        assert len(report.errors) >= 1
        error_entity_types = {e.entity_type for e in report.errors}
        assert "codex" in error_entity_types


class TestHealthCheckPythonAPIScopeNoneAllFive:
    """Scenario 2: health_check(project_root, scope=None) audits all five entity types."""

    def test_health_check_scope_none_returns_issues_from_multiple_types(
        self, project_dir
    ):
        """health_check scope=None finds issues across multiple injected entity types."""
        # Exercises: lore codex show conceptual-workflows-health
        # Inject codex error
        _write_codex_doc(
            project_dir,
            "bad.md",
            "---\ntitle: No ID\nsummary: s\n---\nBody.\n",
        )
        # Inject watcher error
        _write_watcher(
            project_dir,
            "bad.yaml",
            "id: bad-w\ntitle: Bad\nsummary: s\naction: missing-doctrine-us016\n",
        )

        report = health_check(project_dir, scope=None)

        entity_types = {i.entity_type for i in report.issues}
        assert "codex" in entity_types
        assert "watchers" in entity_types


class TestHealthCheckPythonAPINoFileSideEffect:
    """Scenario 3: health_check() called directly does not write a report file."""

    def test_health_check_direct_call_does_not_create_report_file(self, project_dir):
        """health_check() does not write any files to .lore/codex/transient/."""
        # Exercises: lore codex show conceptual-workflows-health
        transient_dir = project_dir / ".lore" / "codex" / "transient"
        transient_dir.mkdir(parents=True, exist_ok=True)

        before = set(transient_dir.glob("health-*.md"))

        health_check(project_dir, scope=None)

        after = set(transient_dir.glob("health-*.md"))
        new_files = after - before
        assert not new_files, (
            f"health_check() must not write report files; found new files: {new_files}"
        )

    def test_health_check_direct_call_no_transient_dir_created(self, project_dir):
        """health_check() does not create .lore/codex/transient/ if it does not exist."""
        # Exercises: lore codex show conceptual-workflows-health
        # Ensure codex dir exists but transient does not
        codex_dir = project_dir / ".lore" / "codex"
        codex_dir.mkdir(parents=True, exist_ok=True)
        transient_dir = codex_dir / "transient"
        if transient_dir.exists():
            shutil.rmtree(transient_dir)

        health_check(project_dir, scope=None)

        assert not transient_dir.exists(), (
            f"health_check() must not create transient dir; it now exists: {transient_dir}"
        )


class TestHealthCheckPythonAPIScopeWatchers:
    """Scenario 4: health_check(project_root, scope=['watchers']) returns only watcher issues."""

    def test_health_check_scope_watchers_returns_only_watcher_issues(self, project_dir):
        """health_check scope=['watchers'] excludes codex issues even when codex has errors."""
        # Exercises: lore codex show conceptual-workflows-health
        # Inject codex error — must NOT appear
        _write_codex_doc(
            project_dir,
            "bad.md",
            "---\ntitle: No ID\nsummary: s\n---\nBody.\n",
        )
        # Inject watcher error — must appear
        _write_watcher(
            project_dir,
            "bad.yaml",
            "id: bad-w\ntitle: Bad\nsummary: s\naction: missing-doctrine-us016\n",
        )

        report = health_check(project_dir, scope=["watchers"])

        entity_types = {i.entity_type for i in report.issues}
        assert "codex" not in entity_types, (
            f"scope=['watchers'] must not include codex issues; found: {entity_types}"
        )

    def test_health_check_scope_watchers_finds_watcher_error(self, project_dir):
        """health_check scope=['watchers'] finds broken doctrine ref in watcher."""
        # Exercises: lore codex show conceptual-workflows-health
        _write_watcher(
            project_dir,
            "bad.yaml",
            "id: bad-w\ntitle: Bad\nsummary: s\naction: missing-doctrine-us016\n",
        )

        report = health_check(project_dir, scope=["watchers"])

        assert report.has_errors is True
        watcher_errors = [e for e in report.errors if e.entity_type == "watchers"]
        assert len(watcher_errors) >= 1


# ---------------------------------------------------------------------------
# US-017: HealthIssue and HealthReport defined in lore.health (not lore.models)
# Exercises: conceptual-workflows-health (lore codex show conceptual-workflows-health)
# ---------------------------------------------------------------------------


class TestHealthTypesDefinedInHealthModule:
    """US-017: HealthIssue and HealthReport must be defined in lore.health, not lore.models."""

    def test_health_issue_module_is_lore_health(self):
        """HealthIssue.__module__ must be 'lore.health' — the type is owned by health.py."""
        # Exercises: lore codex show conceptual-workflows-health
        from lore.health import HealthIssue
        assert HealthIssue.__module__ == "lore.health", (
            f"HealthIssue must be defined in lore.health, got __module__={HealthIssue.__module__!r}"
        )

    def test_health_report_module_is_lore_health(self):
        """HealthReport.__module__ must be 'lore.health' — the type is owned by health.py."""
        # Exercises: lore codex show conceptual-workflows-health
        from lore.health import HealthReport
        assert HealthReport.__module__ == "lore.health", (
            f"HealthReport must be defined in lore.health, got __module__={HealthReport.__module__!r}"
        )


# ---------------------------------------------------------------------------
# US-018: health_check and HealthReport importable from lore.models (E2E)
# Exercises: lore codex show conceptual-workflows-health
# ---------------------------------------------------------------------------


class TestHealthCheckPublicAPI:
    """health_check is accessible via the stable lore.models public API."""

    def test_health_check_importable_from_lore_models(self):
        """from lore.models import health_check succeeds without error."""
        # Exercises: lore codex show conceptual-workflows-health
        from lore.models import health_check  # noqa: F401
        assert health_check is not None

    def test_health_check_is_callable(self):
        """health_check imported from lore.models is callable."""
        # Exercises: lore codex show conceptual-workflows-health
        from lore.models import health_check
        assert callable(health_check), (
            f"health_check from lore.models is not callable: {health_check!r}"
        )

    def test_health_check_in_lore_models_all(self):
        """'health_check' appears in lore.models.__all__."""
        # Exercises: lore codex show conceptual-workflows-health
        import lore.models
        assert "health_check" in lore.models.__all__, (
            f"'health_check' missing from lore.models.__all__: {lore.models.__all__!r}"
        )


# ---------------------------------------------------------------------------
# US-019: Scan failure isolation — missing directory produces scan_failed,
# other entity types still checked
# Exercises: lore codex show conceptual-workflows-health
# ---------------------------------------------------------------------------


class TestHealthScanFailureIsolation:
    """lore health isolates scan failures so one broken entity type does not abort others."""

    def test_health_missing_watchers_dir_reports_scan_failed(self, runner, project_dir):
        """lore health reports scan_failed for watchers when .lore/watchers/ does not exist."""
        # Exercises: lore codex show conceptual-workflows-health
        watchers_dir = project_dir / ".lore" / "watchers"
        if watchers_dir.exists():
            shutil.rmtree(watchers_dir)
        with patch(
            "lore.health._check_watchers",
            side_effect=OSError("No such file or directory: '.lore/watchers'"),
        ):
            result = runner.invoke(main, ["health"])

        assert "scan_failed" in result.output, (
            f"Expected 'scan_failed' in output, got:\n{result.output}"
        )
        assert result.exit_code == 1, (
            f"Expected exit_code=1, got {result.exit_code}. Output:\n{result.output}"
        )

    def test_health_scan_failed_line_contains_watchers_entity_type(self, runner, project_dir):
        """scan_failed output line references 'watchers' entity type."""
        # Exercises: lore codex show conceptual-workflows-health
        with patch(
            "lore.health._check_watchers",
            side_effect=RuntimeError("unexpected crash"),
        ):
            result = runner.invoke(main, ["health"])

        assert "watchers" in result.output, (
            f"Expected 'watchers' in output, got:\n{result.output}"
        )
        assert "scan_failed" in result.output, (
            f"Expected 'scan_failed' in output, got:\n{result.output}"
        )

    def test_health_scan_failure_isolation_other_types_still_run(self, runner, project_dir):
        """When artifacts checker raises, watcher and codex checks still produce output."""
        # Exercises: lore codex show conceptual-workflows-health
        # Write a watcher with invalid YAML so watchers checker reports an error.
        watcher_path = project_dir / ".lore" / "watchers" / "bad.yaml"
        watcher_path.parent.mkdir(parents=True, exist_ok=True)
        watcher_path.write_text("id: bad\ntitle: Bad\n  broken: : yaml\n")
        with patch(
            "lore.health._check_artifacts",
            side_effect=IOError("disk I/O error"),
        ):
            result = runner.invoke(main, ["health"])

        # artifacts scan_failed present
        assert "scan_failed" in result.output, (
            f"Expected 'scan_failed' for artifacts in output, got:\n{result.output}"
        )
        assert "artifacts" in result.output, (
            f"Expected 'artifacts' in output, got:\n{result.output}"
        )
        # watchers checker still ran and produced output
        assert "watchers" in result.output, (
            f"Expected 'watchers' checker output still present, got:\n{result.output}"
        )
