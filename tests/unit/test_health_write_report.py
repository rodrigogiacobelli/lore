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
from pathlib import Path

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
    """``write_report=True`` writes the markdown report and populates report_path.

    Post health-report-retention: ``write_report=True`` alone is no longer
    enough — the effective retention policy decides. These tests pin the
    ``retention="all"`` behaviour (today's unconditional-write semantics).
    """

    def test_write_report_true_creates_file_at_expected_path(self, init_project):
        timestamp = "2026-05-25T12-34-56"
        _report = health_check(
            init_project, write_report=True, timestamp=timestamp, retention="all"
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
            init_project, write_report=True, timestamp=timestamp, retention="all"
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
            init_project,
            write_report=True,
            timestamp="2026-05-25T00-00-00",
            retention="all",
        )
        assert isinstance(result, HealthReport)

    def test_write_report_true_report_file_contains_markdown_table(self, init_project):
        timestamp = "2026-05-25T12-34-56"
        report = health_check(
            init_project, write_report=True, timestamp=timestamp, retention="all"
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


# ===========================================================================
# health-report-retention — the persistence policy gate in front of the write
#
# Spec: tech spec "Health report retention policy".
#   none   (DEFAULT) — nothing written, report_path stays None
#   latest           — prune every transient/health-*.md, then write
#   all              — write, prune nothing
# `retention=None` resolves from `.lore/config.toml`; an explicit value wins.
# ===========================================================================


@pytest.fixture(autouse=True)
def _reset_config_warned_latch():
    """Reset ``lore.config._warned`` so config warnings are not swallowed by a
    latch flipped in an earlier test in the same process."""
    import lore.config as cfg_mod
    cfg_mod._warned = False
    yield
    cfg_mod._warned = False


def _set_retention(root: Path, value: str) -> None:
    """Write ``health-report-retention = "<value>"`` into the project config."""
    lore_dir = root / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    (lore_dir / "config.toml").write_text(f'health-report-retention = "{value}"\n')


def _remove_config(root: Path) -> None:
    """Delete the seeded ``.lore/config.toml`` so no key is present at all."""
    cfg = root / ".lore" / "config.toml"
    if cfg.exists():
        cfg.unlink()


def _transient(root: Path) -> Path:
    """Return (creating if needed) the project's transient codex directory."""
    d = root / ".lore" / "codex" / "transient"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _seed_stale_report(root: Path, timestamp: str) -> Path:
    """Drop a stale ``health-<timestamp>.md`` into the transient layer."""
    path = _transient(root) / f"health-{timestamp}.md"
    path.write_text(
        f"---\nid: health-{timestamp}\ntitle: Health Report\n"
        f"summary: stale report\n---\n\nNo issues found.\n"
    )
    return path


def _reports(root: Path) -> list[Path]:
    """Every ``health-*.md`` sitting directly in the transient layer."""
    d = root / ".lore" / "codex" / "transient"
    return sorted(d.glob("health-*.md")) if d.exists() else []


def _spy_on_load_config(monkeypatch) -> list[Path]:
    """Record every ``load_config`` call, whichever way health imports it."""
    import lore.config as cfg_mod

    calls: list[Path] = []
    real = cfg_mod.load_config

    def spy(root):
        calls.append(root)
        return real(root)

    monkeypatch.setattr(cfg_mod, "load_config", spy)
    if hasattr(lore.health, "load_config"):
        monkeypatch.setattr(lore.health, "load_config", spy)
    return calls


class TestRetentionDefaultsToNone:
    """Absent config / absent key → nothing is written even with write_report=True."""

    def test_write_report_true_with_no_config_file_writes_no_report(self, init_project):
        _remove_config(init_project)
        before = _reports(init_project)

        health_check(init_project, write_report=True, timestamp="2026-05-25T12-34-56")

        assert _reports(init_project) == before

    def test_write_report_true_with_no_config_file_leaves_report_path_none(
        self, init_project
    ):
        _remove_config(init_project)

        report = health_check(
            init_project, write_report=True, timestamp="2026-05-25T12-34-56"
        )

        assert report.report_path is None

    def test_write_report_true_with_key_absent_writes_no_report(self, init_project):
        (init_project / ".lore" / "config.toml").write_text(
            "show-glossary-on-codex-commands = true\n"
        )

        report = health_check(
            init_project, write_report=True, timestamp="2026-05-25T12-34-56"
        )

        assert _reports(init_project) == []
        assert report.report_path is None

    def test_write_report_true_with_config_none_writes_no_report(self, init_project):
        _set_retention(init_project, "none")

        report = health_check(
            init_project, write_report=True, timestamp="2026-05-25T12-34-56"
        )

        assert _reports(init_project) == []
        assert report.report_path is None

    def test_none_does_not_delete_pre_existing_reports(self, init_project):
        """``none`` means "write nothing" — NOT "clean up what is already there"."""
        _set_retention(init_project, "none")
        stale = _seed_stale_report(init_project, "2020-01-01T00-00-00")

        health_check(init_project, write_report=True, timestamp="2026-05-25T12-34-56")

        assert stale.exists()

    def test_none_still_returns_a_populated_health_report(self, init_project):
        """Disk policy must not change the in-memory audit result."""
        _set_retention(init_project, "none")

        report = health_check(
            init_project, write_report=True, timestamp="2026-05-25T12-34-56"
        )

        assert isinstance(report, HealthReport)
        assert report.has_errors is False
        assert report.report_path is None


class TestRetentionAll:
    """``all`` reproduces the historic unconditional-write behaviour."""

    def test_explicit_all_writes_the_report_file(self, init_project):
        timestamp = "2026-05-25T12-34-56"

        report = health_check(
            init_project, write_report=True, timestamp=timestamp, retention="all"
        )

        expected = _transient(init_project) / f"health-{timestamp}.md"
        assert expected.exists()
        assert report.report_path == expected

    def test_config_all_writes_the_report_file_without_explicit_retention(
        self, init_project
    ):
        _set_retention(init_project, "all")
        timestamp = "2026-05-25T12-34-56"

        report = health_check(init_project, write_report=True, timestamp=timestamp)

        expected = _transient(init_project) / f"health-{timestamp}.md"
        assert expected.exists()
        assert report.report_path == expected

    def test_all_keeps_previously_written_reports(self, init_project):
        _set_retention(init_project, "all")
        stale = _seed_stale_report(init_project, "2020-01-01T00-00-00")

        health_check(init_project, write_report=True, timestamp="2026-05-25T12-34-56")

        assert stale.exists()
        assert len(_reports(init_project)) == 2


class TestRetentionLatest:
    """``latest`` prunes every prior report, then writes exactly one."""

    def test_latest_leaves_exactly_one_report(self, init_project):
        _seed_stale_report(init_project, "2020-01-01T00-00-00")
        _seed_stale_report(init_project, "2021-02-02T00-00-00")

        health_check(
            init_project,
            write_report=True,
            timestamp="2026-05-25T12-34-56",
            retention="latest",
        )

        assert len(_reports(init_project)) == 1

    def test_latest_surviving_report_is_the_new_one(self, init_project):
        _seed_stale_report(init_project, "2020-01-01T00-00-00")
        _seed_stale_report(init_project, "2021-02-02T00-00-00")
        timestamp = "2026-05-25T12-34-56"

        report = health_check(
            init_project,
            write_report=True,
            timestamp=timestamp,
            retention="latest",
        )

        survivors = _reports(init_project)
        assert [p.name for p in survivors] == [f"health-{timestamp}.md"]
        assert report.report_path == survivors[0]

    def test_latest_deletes_the_stale_files_from_disk(self, init_project):
        stale_a = _seed_stale_report(init_project, "2020-01-01T00-00-00")
        stale_b = _seed_stale_report(init_project, "2021-02-02T00-00-00")

        health_check(
            init_project,
            write_report=True,
            timestamp="2026-05-25T12-34-56",
            retention="latest",
        )

        assert not stale_a.exists()
        assert not stale_b.exists()

    def test_latest_leaves_non_health_transient_docs_untouched(self, init_project):
        notes = _transient(init_project) / "notes.md"
        notes.write_text(
            "---\nid: notes\ntitle: Notes\nsummary: working notes\n---\n\nKeep me.\n"
        )
        _seed_stale_report(init_project, "2020-01-01T00-00-00")

        health_check(
            init_project,
            write_report=True,
            timestamp="2026-05-25T12-34-56",
            retention="latest",
        )

        assert notes.exists()
        assert notes.read_text().endswith("Keep me.\n")

    def test_latest_prune_is_not_recursive(self, init_project):
        """The glob is scoped to the transient dir itself, not its subtrees."""
        nested_dir = _transient(init_project) / "archive"
        nested_dir.mkdir(parents=True, exist_ok=True)
        nested = nested_dir / "health-2019-01-01T00-00-00.md"
        nested.write_text(
            "---\nid: health-2019-01-01T00-00-00\ntitle: Old\nsummary: s\n---\n\nx\n"
        )

        health_check(
            init_project,
            write_report=True,
            timestamp="2026-05-25T12-34-56",
            retention="latest",
        )

        assert nested.exists()

    def test_config_latest_prunes_without_explicit_retention(self, init_project):
        _set_retention(init_project, "latest")
        _seed_stale_report(init_project, "2020-01-01T00-00-00")
        timestamp = "2026-05-25T12-34-56"

        health_check(init_project, write_report=True, timestamp=timestamp)

        assert [p.name for p in _reports(init_project)] == [f"health-{timestamp}.md"]

    def test_latest_with_no_prior_reports_just_writes_one(self, init_project):
        timestamp = "2026-05-25T12-34-56"

        health_check(
            init_project,
            write_report=True,
            timestamp=timestamp,
            retention="latest",
        )

        assert [p.name for p in _reports(init_project)] == [f"health-{timestamp}.md"]

    def test_latest_swallows_unlink_errors_and_still_writes(
        self, init_project, monkeypatch
    ):
        """An undeletable stale report must not abort the audit (fail-soft)."""
        stuck = _seed_stale_report(init_project, "2020-01-01T00-00-00")
        _seed_stale_report(init_project, "2021-02-02T00-00-00")

        import os

        real_path_unlink = Path.unlink
        real_os_unlink = os.unlink
        real_os_remove = os.remove

        def _blocked(target) -> bool:
            return os.path.basename(os.fspath(target)) == stuck.name

        def flaky_path_unlink(self, *args, **kwargs):
            if _blocked(self):
                raise OSError("permission denied")
            return real_path_unlink(self, *args, **kwargs)

        def flaky_os_unlink(path, *args, **kwargs):
            if _blocked(path):
                raise OSError("permission denied")
            return real_os_unlink(path, *args, **kwargs)

        def flaky_os_remove(path, *args, **kwargs):
            if _blocked(path):
                raise OSError("permission denied")
            return real_os_remove(path, *args, **kwargs)

        # Cover every plausible delete call the implementation might make.
        monkeypatch.setattr(Path, "unlink", flaky_path_unlink)
        monkeypatch.setattr(os, "unlink", flaky_os_unlink)
        monkeypatch.setattr(os, "remove", flaky_os_remove)
        timestamp = "2026-05-25T12-34-56"

        report = health_check(
            init_project,
            write_report=True,
            timestamp=timestamp,
            retention="latest",
        )

        assert report.report_path == _transient(init_project) / f"health-{timestamp}.md"
        assert report.report_path.exists()
        assert stuck.exists()


class TestExplicitRetentionOverridesConfig:
    """An explicitly passed ``retention`` always beats the config value."""

    def test_explicit_none_beats_config_all(self, init_project):
        _set_retention(init_project, "all")

        report = health_check(
            init_project,
            write_report=True,
            timestamp="2026-05-25T12-34-56",
            retention="none",
        )

        assert _reports(init_project) == []
        assert report.report_path is None

    def test_explicit_all_beats_config_none(self, init_project):
        _set_retention(init_project, "none")
        timestamp = "2026-05-25T12-34-56"

        report = health_check(
            init_project, write_report=True, timestamp=timestamp, retention="all"
        )

        assert report.report_path == _transient(init_project) / f"health-{timestamp}.md"

    def test_explicit_latest_beats_config_all(self, init_project):
        _set_retention(init_project, "all")
        _seed_stale_report(init_project, "2020-01-01T00-00-00")

        health_check(
            init_project,
            write_report=True,
            timestamp="2026-05-25T12-34-56",
            retention="latest",
        )

        assert len(_reports(init_project)) == 1


class TestRetentionValidation:
    """An unknown token raises ``ValueError``, mirroring unknown-scope handling."""

    def test_bogus_retention_raises_value_error(self, init_project):
        with pytest.raises(ValueError):
            health_check(
                init_project,
                write_report=True,
                timestamp="2026-05-25T12-34-56",
                retention="bogus",
            )

    def test_bogus_retention_message_matches_the_scope_error_shape(self, init_project):
        with pytest.raises(ValueError) as excinfo:
            health_check(init_project, write_report=True, retention="bogus")
        assert str(excinfo.value) == (
            "Unknown retention: 'bogus'. Valid values: none, latest, all."
        )

    def test_bogus_retention_raises_before_any_checker_runs(
        self, init_project, monkeypatch
    ):
        """Validation happens up front, exactly like scope validation."""
        called: list[str] = []

        def spy_check_codex(codex_dir):
            called.append("codex")
            return []

        monkeypatch.setattr(lore.health, "_check_codex", spy_check_codex)

        with pytest.raises(ValueError):
            health_check(init_project, write_report=True, retention="bogus")

        assert called == []

    def test_bogus_retention_raises_even_without_write_report(self, init_project):
        with pytest.raises(ValueError):
            health_check(init_project, retention="bogus")

    def test_bogus_retention_writes_nothing(self, init_project):
        _set_retention(init_project, "all")

        with pytest.raises(ValueError):
            health_check(
                init_project,
                write_report=True,
                timestamp="2026-05-25T12-34-56",
                retention="bogus",
            )

        assert _reports(init_project) == []

    def test_invalid_config_value_falls_back_to_none(self, init_project, capsys):
        """A bad value in config is fail-soft (warn + default), never a raise."""
        _set_retention(init_project, "weekly")

        report = health_check(
            init_project, write_report=True, timestamp="2026-05-25T12-34-56"
        )

        assert _reports(init_project) == []
        assert report.report_path is None
        assert "lore: invalid value for health-report-retention at" in capsys.readouterr().err


class TestRetentionConfigReadOnlyWhenWriting:
    """A read-only audit must never touch ``.lore/config.toml``."""

    def test_write_report_false_does_not_load_config(self, init_project, monkeypatch):
        _set_retention(init_project, "all")
        calls = _spy_on_load_config(monkeypatch)

        health_check(init_project)

        assert calls == [], f"config read during a write_report=False audit: {calls}"

    def test_write_report_false_writes_nothing_even_under_config_all(
        self, init_project
    ):
        _set_retention(init_project, "all")

        report = health_check(init_project, write_report=False)

        assert _reports(init_project) == []
        assert report.report_path is None

    def test_write_report_true_loads_config_when_retention_not_given(
        self, init_project, monkeypatch
    ):
        _set_retention(init_project, "all")
        calls = _spy_on_load_config(monkeypatch)

        health_check(init_project, write_report=True, timestamp="2026-05-25T12-34-56")

        assert calls == [init_project]
