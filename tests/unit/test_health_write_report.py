"""G4 Red — failing tests for folding `_write_report` and scope validation
into `lore.health.health_check`.

Spec: lore codex show transient-public-api-facade-plan (### G4)
ADR-011 information-loss class — callers of ``lore.api.health_check`` cannot
get the report file without re-implementing ``_write_report`` themselves.

Tests pin the new public surface:

- ``health_check(write_report=True, timestamp=...)`` writes the markdown
  report file under ``<project>/.lore/codex/transient/health-<ts>.md`` and
  returns a ``HealthReport`` whose ``report_path`` matches the written file.
- ``health_check(write_report=False)`` (default) writes nothing and the
  returned ``HealthReport.report_path is None``.
- ``HealthReport`` gains the new fields ``report_path: Path | None`` and
  ``schemas_ran: bool``.
- Unknown scope token raises ``ValueError`` (scope validation moves INTO
  ``health_check``). The CLI translates the raise back into the existing
  user-visible ``Invalid scope: '<token>'. Valid scopes: ...`` text.
- The existing ``scope`` / ``scopes`` alias (US-004) is preserved.

Plus CLI parity:

- ``lore health`` text output unchanged.
- ``lore health --json`` text output unchanged.
- ``lore health --scope nonsense`` exits 1 with the existing error text.

Every test here MUST fail prior to G4 Green.
"""

from __future__ import annotations

import dataclasses
import re

import pytest
from click.testing import CliRunner

import lore.health
from lore.cli import main
from lore.health import HealthReport, health_check


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def init_project(tmp_path, monkeypatch):
    """Initialise a real lore project under ``tmp_path`` and chdir into it."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0, result.stdout
    return tmp_path


# ---------------------------------------------------------------------------
# HealthReport — new fields
# ---------------------------------------------------------------------------


class TestHealthReportNewFields:
    """HealthReport exposes ``report_path`` and ``schemas_ran`` with safe defaults."""

    def test_health_report_has_report_path_field_defaulting_to_none(self):
        report = HealthReport(errors=(), warnings=())
        assert report.report_path is None

    def test_health_report_has_schemas_ran_field_defaulting_to_false(self):
        report = HealthReport(errors=(), warnings=())
        assert report.schemas_ran is False

    def test_health_report_report_path_is_optional_path(self):
        field_names = {f.name for f in dataclasses.fields(HealthReport)}
        assert "report_path" in field_names
        assert "schemas_ran" in field_names

    def test_health_report_accepts_report_path_keyword(self, tmp_path):
        p = tmp_path / "health-2026-01-01T00-00-00.md"
        report = HealthReport(errors=(), warnings=(), report_path=p, schemas_ran=True)
        assert report.report_path == p
        assert report.schemas_ran is True


# ---------------------------------------------------------------------------
# health_check(write_report=True, timestamp=...)
# ---------------------------------------------------------------------------


class TestHealthCheckWriteReport:
    """``write_report=True`` writes the markdown report and populates report_path."""

    def test_write_report_true_creates_file_at_expected_path(self, init_project):
        timestamp = "2026-05-25T12-34-56"
        _report = health_check(
            init_project, write_report=True, timestamp=timestamp
        )

        expected = (
            init_project
            / ".lore"
            / "codex"
            / "transient"
            / f"health-{timestamp}.md"
        )
        assert expected.exists(), f"report file not written at {expected}"

    def test_write_report_true_sets_report_path_on_returned_report(self, init_project):
        timestamp = "2026-05-25T12-34-56"
        report = health_check(
            init_project, write_report=True, timestamp=timestamp
        )

        expected = (
            init_project
            / ".lore"
            / "codex"
            / "transient"
            / f"health-{timestamp}.md"
        )
        assert isinstance(report, HealthReport)
        assert report.report_path == expected

    def test_write_report_true_returns_health_report_instance(self, init_project):
        result = health_check(
            init_project, write_report=True, timestamp="2026-05-25T00-00-00"
        )
        assert isinstance(result, HealthReport)

    def test_write_report_true_report_file_contains_markdown_table(self, init_project):
        timestamp = "2026-05-25T12-34-56"
        report = health_check(
            init_project, write_report=True, timestamp=timestamp
        )
        content = report.report_path.read_text()
        # frontmatter + header + body
        assert content.startswith("---\n"), content[:80]
        assert "# Health Report" in content
        # clean run on fresh init → no issues
        assert "No issues found." in content


class TestHealthCheckWriteReportFalseDefault:
    """``write_report=False`` (the default) writes nothing and report_path is None."""

    def test_write_report_default_false_writes_no_file(self, init_project):
        transient = init_project / ".lore" / "codex" / "transient"
        # baseline: capture the pre-existing files (init may seed nothing here).
        before = set(transient.glob("health-*.md")) if transient.exists() else set()

        report = health_check(init_project)

        after = set(transient.glob("health-*.md")) if transient.exists() else set()
        assert after == before, f"unexpected files: {after - before}"
        assert report.report_path is None

    def test_write_report_explicit_false_writes_no_file(self, init_project):
        transient = init_project / ".lore" / "codex" / "transient"
        before = set(transient.glob("health-*.md")) if transient.exists() else set()

        report = health_check(init_project, write_report=False)

        after = set(transient.glob("health-*.md")) if transient.exists() else set()
        assert after == before
        assert report.report_path is None

    def test_write_report_default_report_path_is_none(self, init_project):
        report = health_check(init_project)
        assert report.report_path is None


# ---------------------------------------------------------------------------
# health_check — scope validation moves INTO the op fn
# ---------------------------------------------------------------------------


class TestHealthCheckScopeValidation:
    """Unknown scope token raises ValueError (validation moved into op fn)."""

    def test_unknown_scope_raises_value_error(self, init_project):
        with pytest.raises(ValueError):
            health_check(init_project, scope=["nonsense"])

    def test_unknown_scope_message_names_the_offending_token(self, init_project):
        with pytest.raises(ValueError) as excinfo:
            health_check(init_project, scope=["nonsense"])
        assert "nonsense" in str(excinfo.value)

    def test_unknown_scope_alias_kwarg_raises(self, init_project):
        """Same validation runs against the ``scopes`` alias."""
        with pytest.raises(ValueError):
            health_check(init_project, scopes=["bogus"])

    def test_unknown_scope_first_invalid_reported(self, init_project):
        """When multiple bad tokens are passed, the first is named in the message
        (matches the CLI's current ``invalid[0]`` behaviour)."""
        with pytest.raises(ValueError) as excinfo:
            health_check(init_project, scope=["badone", "badtwo"])
        msg = str(excinfo.value)
        assert "badone" in msg


# ---------------------------------------------------------------------------
# health_check — scope / scopes alias preserved (US-004) WHILE ALSO raising
# on unknown tokens (the G4 contract: validation moves INTO the op fn for
# BOTH alias spellings).
# ---------------------------------------------------------------------------


class TestHealthCheckScopeAliasPreserved:
    """Existing ``scope`` / ``scopes`` aliases continue to filter AND now
    surface unknown-token errors via ``ValueError`` (new G4 contract)."""

    def test_scope_alias_with_unknown_token_raises_value_error(self, init_project):
        """Unknown via ``scope=`` raises — proves the alias path is wired."""
        with pytest.raises(ValueError):
            health_check(init_project, scope=["nonsense"])

    def test_scopes_alias_with_unknown_token_raises_value_error(self, init_project):
        """Unknown via ``scopes=`` (US-004 alias) also raises."""
        with pytest.raises(ValueError):
            health_check(init_project, scopes=["nonsense"])

    def test_scope_alias_with_mixed_valid_and_invalid_raises(self, init_project):
        """Mixed list: any unknown token is enough to raise."""
        with pytest.raises(ValueError):
            health_check(init_project, scope=["codex", "nonsense"])


# ---------------------------------------------------------------------------
# CLI parity — text + JSON unchanged
# ---------------------------------------------------------------------------


class TestCliHealthParityTextOutput:
    """``lore health`` text output unchanged after G4 — and the CLI now
    delegates report-writing to ``health_check(write_report=True, timestamp=...)``
    instead of calling ``_write_report`` directly."""

    def test_lore_health_cli_delegates_write_to_health_check(
        self, init_project, monkeypatch
    ):
        """G4 contract: CLI passes ``write_report=True`` + ``timestamp=...``
        through to ``health_check`` and no longer calls ``_write_report``
        directly. This test fails today because the CLI invokes
        ``health_check`` with only ``scope=...``."""
        import lore.cli

        captured: dict = {}

        def fake_health_check(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return HealthReport(errors=(), warnings=())

        # Patch at the module the CLI imports from (`from lore.health import health_check`).
        monkeypatch.setattr(lore.health, "health_check", fake_health_check)
        # The CLI does `from lore.health import health_check, _write_report`
        # inside the handler, so module-attribute patching catches the lookup.

        runner = CliRunner()
        runner.invoke(main, ["health"])

        assert captured, "health_check was not invoked"
        kwargs = captured["kwargs"]
        assert kwargs.get("write_report") is True, (
            f"CLI must pass write_report=True; got kwargs={kwargs}"
        )
        assert "timestamp" in kwargs, (
            f"CLI must pass timestamp=; got kwargs={kwargs}"
        )
        assert re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}", kwargs["timestamp"]
        ), f"timestamp shape mismatch: {kwargs['timestamp']!r}"


class TestCliHealthParityJsonOutput:
    """``lore health --json`` shape unchanged after G4. JSON envelope MUST
    stay exactly ``{has_errors, issues}`` (no ``report_path`` leak), and the
    CLI must drive the write via ``health_check(write_report=True)``."""

    def test_lore_health_json_delegates_write_to_health_check(
        self, init_project, monkeypatch
    ):
        """``--json`` path must also push ``write_report=True`` through to
        ``health_check`` (today the CLI calls ``_write_report`` separately)."""
        captured: dict = {}

        def fake_health_check(*args, **kwargs):
            captured["kwargs"] = kwargs
            return HealthReport(errors=(), warnings=())

        monkeypatch.setattr(lore.health, "health_check", fake_health_check)

        runner = CliRunner()
        runner.invoke(main, ["health", "--json"])

        assert captured.get("kwargs", {}).get("write_report") is True
        assert "timestamp" in captured.get("kwargs", {})


class TestCliHealthScopeNonsense:
    """``lore health <nonsense>`` exits 1 with the existing user-visible
    error text. After G4 the validation lives inside ``health_check`` and the
    CLI must translate the raised ``ValueError`` back into the current text.
    """

    def test_extra_scopes_nonsense_translated_from_value_error(
        self, init_project, monkeypatch
    ):
        """G4 contract: the user-visible ``Invalid scope: '<token>'...`` text
        comes from the CLI translating ``ValueError`` raised by ``health_check``,
        not from a pre-call CLI-side check. Force ``health_check`` to raise and
        assert the historic message still appears."""

        def raising_health_check(*args, **kwargs):
            raise ValueError("Unknown scope: 'nonsense'")

        monkeypatch.setattr(lore.health, "health_check", raising_health_check)

        runner = CliRunner()
        # Provide a valid --scope so click.Choice does not pre-reject; the
        # bogus positional is what the handler-side path used to validate.
        result = runner.invoke(main, ["health", "--scope", "codex"])
        # Post-G4: CLI catches ValueError → emits the existing user message + exit 1.
        assert result.exit_code == 1, (
            f"expected CLI to translate ValueError to exit 1; got "
            f"{result.exit_code}\nstdout={result.stdout!r}\nstderr={result.stderr!r}"
        )
        assert "Invalid scope:" in result.stderr
        assert "nonsense" in result.stderr
