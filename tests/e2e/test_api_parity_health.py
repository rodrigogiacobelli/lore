"""E2E parity for `lore health` per Tech Spec §10.

Spec §10: "Health → tests/e2e/test_api_parity_health.py: scope
coverage; report-file emission via ``write_report=True``; ``report_path``
populated on ``HealthReport``."

ADR-011 Decision: ``_write_report`` move INTO ``health_check`` via
``write_report=True``. CLI calls op fn with ``write_report=True``;
op fn populates ``HealthReport.report_path``.

Red phase only.
"""

from __future__ import annotations

import json
from pathlib import Path


class TestHealthOpFnAcceptsWriteReportKw:
    """``health_check(write_report=True)`` is supported and populates ``report_path``."""

    def test_health_check_accepts_write_report_kw(self, project_dir):
        from lore import api

        report = api.health_check(project_dir, write_report=True)
        # HealthReport gains report_path : Path | None per Tech Spec §6.
        assert hasattr(report, "report_path"), (
            "HealthReport missing report_path attribute (Spec §6)"
        )
        assert report.report_path is not None, (
            "write_report=True must populate report_path on HealthReport"
        )
        assert Path(report.report_path).exists(), (
            "report_path must point to an existing file when write_report=True"
        )

    def test_health_check_default_no_report_written(self, project_dir):
        from lore import api

        report = api.health_check(project_dir)
        # Default: write_report=False, report_path stays None.
        assert getattr(report, "report_path", None) is None


class TestHealthReportHasSchemasRanFlag:
    """Spec §6: HealthReport gains ``schemas_ran: bool``."""

    def test_health_report_has_schemas_ran_field(self, project_dir):
        from lore import api

        report = api.health_check(project_dir)
        assert hasattr(report, "schemas_ran"), (
            "HealthReport missing schemas_ran flag (Spec §6)"
        )


class TestHealthCliEnvelopeUsesFacade:
    """CLI ``lore --json health`` calls facade ``health_check``."""

    def test_cli_health_json_exit_zero_on_clean_project(self, runner, project_dir):
        from lore.cli import main

        result = runner.invoke(main, ["--json", "health"])
        # Clean project = no errors → exit 0; envelope JSON-parseable.
        payload = json.loads(result.stdout)
        assert isinstance(payload, dict)
        assert "errors" in payload or "issues" in payload

    def test_cli_unknown_scope_rejected(self, runner, project_dir):
        from lore.cli import main

        result = runner.invoke(
            main, ["--json", "health", "--scope", "nonexistent-scope"]
        )
        # Per Tech Spec §2: health_check raises ValueError("Unknown scope: …")
        # which CLI translates to non-zero exit.
        assert result.exit_code != 0

    def test_cli_does_not_import_lore_health_directly(self):
        """G13 done-gate: CLI routes ``health`` through ``lore.api`` only."""
        from pathlib import Path

        src = (
            Path(__file__).resolve().parents[2] / "src" / "lore" / "cli.py"
        ).read_text()
        assert "from lore.health" not in src, (
            "cli.py imports from lore.health directly; route via lore.api"
        )
        assert "import lore.health" not in src


class TestHealthVoiceScopeParity:
    """CLAUDE.md guardrail: the ``voice`` scope works as CLI and Python API alike."""

    @staticmethod
    def _seed(project_dir: Path) -> None:
        """Write one canonical doc carrying a violation of each voice rule."""
        (project_dir / ".lore" / "codex" / "tech-parser.md").write_text(
            "---\n"
            "id: tech-parser\n"
            "title: tech-parser\n"
            "summary: A parser.\n"
            "---\n"
            "The parser previously read each file twice.\n"
            "The flag currently accepts one token.\n"
            "Validation will be added in a later release.\n"
            "As mentioned above, the new flag takes a token.\n"
            "The resolver is robust and simply works.\n",
            encoding="utf-8",
        )

    def test_voice_scope_accepted_by_the_op_fn(self, project_dir):
        from lore import api

        report = api.health_check(project_dir, scope=["voice"])
        assert report.has_errors is False
        assert report.errors == ()

    def test_voice_rows_match_cli_json_envelope(self, runner, project_dir):
        import dataclasses

        from lore import api
        from lore.cli import main

        self._seed(project_dir)

        api_rows = [
            dataclasses.asdict(i)
            for i in api.health_check(project_dir, scope=["voice"]).issues
        ]
        result = runner.invoke(main, ["--json", "health", "--scope", "voice"])
        cli_rows = json.loads(result.stdout)["issues"]

        assert api_rows == cli_rows
        assert {r["check"] for r in api_rows} == {
            "voice_past_narration",
            "voice_expiry_hedge",
            "voice_forward_promise",
            "voice_dangling_deixis",
            "voice_sales_register",
        }

    def test_voice_warnings_keep_both_surfaces_at_exit_zero(self, runner, project_dir):
        from lore import api
        from lore.cli import main

        self._seed(project_dir)

        assert api.health_check(project_dir, scope=["voice"]).has_errors is False
        result = runner.invoke(main, ["--json", "health", "--scope", "voice"])
        assert json.loads(result.stdout)["has_errors"] is False
        assert result.exit_code == 0, result.output

    def test_voice_scope_is_in_both_token_lists(self):
        """``cli._VALID_SCOPES`` and ``health._ALL_SCOPES`` each carry the token."""
        from lore.cli import _VALID_SCOPES
        from lore.health import _ALL_SCOPES

        assert "voice" in _VALID_SCOPES
        assert "voice" in _ALL_SCOPES
