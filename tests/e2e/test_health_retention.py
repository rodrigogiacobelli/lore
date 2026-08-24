"""E2E tests for the `health-report-retention` config policy.

Spec: tech spec "Health report retention policy".

`lore health` no longer unconditionally writes
`.lore/codex/transient/health-<ts>.md`. A root key in `.lore/config.toml`
decides:

    health-report-retention = "none"     # DEFAULT — nothing written
    health-report-retention = "latest"   # prune every prior report, then write
    health-report-retention = "all"      # write, prune nothing

Anything else (absent key, absent file, wrong type, out-of-set token) falls
back to `"none"` fail-soft, with at most one stderr warning per process.

The CLI grew no new flag and no new output line: text output, `--json`
envelope, and exit codes are unchanged in every mode.

Click 8.3: `CliRunner(mix_stderr=False)` does not exist — read
`result.stdout` / `result.stderr` separately.
"""

from __future__ import annotations

import datetime
import itertools
import json
import re
import shutil
from pathlib import Path

import pytest

from lore.cli import main


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_warned_latch():
    """Reset ``lore.config._warned`` — the latch is per-process and CliRunner
    runs in-process, so a warning fired by an earlier test would otherwise
    swallow this test's expected stderr line."""
    import lore.config as cfg_mod
    cfg_mod._warned = False
    yield
    cfg_mod._warned = False


@pytest.fixture()
def ticking_clock(monkeypatch):
    """Make ``datetime.datetime.now`` advance one second per call.

    ``lore health`` stamps the report filename to whole-second resolution, so
    two back-to-back CLI runs in the same wall-clock second would otherwise
    collide on one filename and hide the retention behaviour.
    """
    counter = itertools.count()
    real = datetime.datetime

    class _Ticking(real):  # type: ignore[misc, valid-type]
        @classmethod
        def now(cls, tz=None):
            return real(2026, 5, 25, 12, 0, next(counter), tzinfo=tz)

    monkeypatch.setattr(datetime, "datetime", _Ticking)
    return _Ticking


def _set_retention(project_dir: Path, value: str) -> None:
    """Write ``health-report-retention = "<value>"`` into the project config."""
    lore_dir = project_dir / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    (lore_dir / "config.toml").write_text(f'health-report-retention = "{value}"\n')


def _remove_config(project_dir: Path) -> None:
    """Delete the seeded ``.lore/config.toml`` entirely."""
    cfg = project_dir / ".lore" / "config.toml"
    if cfg.exists():
        cfg.unlink()


def _transient(project_dir: Path) -> Path:
    """Return (creating if needed) the transient codex layer."""
    d = project_dir / ".lore" / "codex" / "transient"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _reports(project_dir: Path) -> list[Path]:
    """Every ``health-*.md`` directly inside the transient codex layer."""
    d = project_dir / ".lore" / "codex" / "transient"
    return sorted(d.glob("health-*.md")) if d.exists() else []


def _seed_stale_report(project_dir: Path, timestamp: str) -> Path:
    """Drop a stale report into the transient layer, as a prior run would."""
    path = _transient(project_dir) / f"health-{timestamp}.md"
    path.write_text(
        f"---\nid: health-{timestamp}\ntitle: Health Report\n"
        f"summary: stale report\n---\n\nNo issues found.\n"
    )
    return path


def _break_a_doctrine(project_dir: Path) -> None:
    """Introduce one health *error* — a doctrine step naming an absent knight."""
    base = project_dir / ".lore" / "doctrines"
    base.mkdir(parents=True, exist_ok=True)
    (base / "feat-retention.yaml").write_text(
        "id: feat-retention\ntitle: Retention\nsummary: s\n"
        "steps:\n  - knight: no-such-knight-retention\n    mission: impl\n"
    )
    (base / "feat-retention.design.md").write_text(
        "---\nid: feat-retention\ntitle: Retention\nsummary: s\n---\nBody.\n"
    )


# ---------------------------------------------------------------------------
# Default — no key in config → nothing written
# ---------------------------------------------------------------------------


class TestRetentionDefaultNone:
    """A project with no retention key persists no report at all."""

    def test_no_config_file_leaves_transient_free_of_reports(self, runner, project_dir):
        _remove_config(project_dir)

        runner.invoke(main, ["health"])

        assert _reports(project_dir) == []

    def test_key_absent_leaves_transient_free_of_reports(self, runner, project_dir):
        (project_dir / ".lore" / "config.toml").write_text(
            "show-glossary-on-codex-commands = true\n"
        )

        runner.invoke(main, ["health"])

        assert _reports(project_dir) == []

    def test_freshly_initialised_project_writes_no_report(self, runner, project_dir):
        """``lore init`` must leave the project on the no-persistence default.

        ADR-006: assert the resulting behaviour, never the seeded file text.
        """
        runner.invoke(main, ["health"])

        assert _reports(project_dir) == []

    def test_explicit_none_leaves_transient_free_of_reports(self, runner, project_dir):
        _set_retention(project_dir, "none")

        runner.invoke(main, ["health"])

        assert _reports(project_dir) == []

    def test_none_does_not_delete_pre_existing_reports(self, runner, project_dir):
        """``none`` suppresses the write; it never cleans up the past."""
        _set_retention(project_dir, "none")
        stale = _seed_stale_report(project_dir, "2020-01-01T00-00-00")

        runner.invoke(main, ["health"])

        assert stale.exists()
        assert _reports(project_dir) == [stale]

    def test_none_does_not_create_the_transient_directory(self, runner, project_dir):
        """Nothing is written, so the layer is not conjured into existence."""
        _set_retention(project_dir, "none")
        transient = project_dir / ".lore" / "codex" / "transient"
        if transient.exists():
            shutil.rmtree(transient)

        runner.invoke(main, ["health"])

        assert not transient.exists()

    def test_repeated_runs_never_accumulate_reports(self, runner, project_dir):
        _set_retention(project_dir, "none")

        for _ in range(3):
            runner.invoke(main, ["health"])

        assert _reports(project_dir) == []


# ---------------------------------------------------------------------------
# Console output and exit codes are unchanged in every mode
# ---------------------------------------------------------------------------


class TestConsoleOutputUnchanged:
    """No new output line, no new flag, no exit-code change."""

    def test_clean_run_prints_the_historic_success_line(self, runner, project_dir):
        result = runner.invoke(main, ["health"])

        assert "Health check passed. No issues found." in result.stdout
        assert result.exit_code == 0

    def test_clean_run_stdout_identical_across_all_three_modes(
        self, runner, project_dir
    ):
        outputs = {}
        for value in ("none", "latest", "all"):
            _set_retention(project_dir, value)
            outputs[value] = runner.invoke(main, ["health"]).stdout

        assert outputs["none"] == outputs["latest"] == outputs["all"]

    def test_stdout_never_mentions_the_report_path(self, runner, project_dir):
        _set_retention(project_dir, "all")

        result = runner.invoke(main, ["health"])

        assert "transient" not in result.stdout
        assert "health-" not in result.stdout

    def test_error_run_still_exits_one_under_none(self, runner, project_dir):
        _set_retention(project_dir, "none")
        _break_a_doctrine(project_dir)

        result = runner.invoke(main, ["health"])

        assert result.exit_code == 1
        assert _reports(project_dir) == []

    def test_error_run_exit_code_identical_across_all_three_modes(
        self, runner, project_dir
    ):
        _break_a_doctrine(project_dir)
        codes = {}
        for value in ("none", "latest", "all"):
            _set_retention(project_dir, value)
            codes[value] = runner.invoke(main, ["health"]).exit_code

        assert codes == {"none": 1, "latest": 1, "all": 1}

    def test_scope_flag_still_works_under_none(self, runner, project_dir):
        _set_retention(project_dir, "none")

        result = runner.invoke(main, ["health", "--scope", "codex"])

        assert result.exit_code == 0
        assert _reports(project_dir) == []

    def test_unknown_scope_still_exits_one_under_none(self, runner, project_dir):
        _set_retention(project_dir, "none")

        result = runner.invoke(main, ["health", "nonsense-scope"])

        assert result.exit_code == 1
        assert "Invalid scope:" in result.stderr


# ---------------------------------------------------------------------------
# "all" — every run leaves a new report behind
# ---------------------------------------------------------------------------


class TestRetentionAll:
    """``all`` is the historic behaviour: write, prune nothing."""

    def test_single_run_writes_one_report(self, runner, project_dir):
        _set_retention(project_dir, "all")

        runner.invoke(main, ["health"])

        assert len(_reports(project_dir)) == 1

    def test_two_runs_leave_two_reports(self, runner, project_dir, ticking_clock):
        _set_retention(project_dir, "all")

        runner.invoke(main, ["health"])
        runner.invoke(main, ["health"])

        assert len(_reports(project_dir)) == 2

    def test_all_keeps_reports_written_before_the_run(self, runner, project_dir):
        _set_retention(project_dir, "all")
        stale = _seed_stale_report(project_dir, "2020-01-01T00-00-00")

        runner.invoke(main, ["health"])

        assert stale.exists()
        assert len(_reports(project_dir)) == 2

    def test_report_filename_keeps_the_utc_timestamp_shape(self, runner, project_dir):
        _set_retention(project_dir, "all")

        runner.invoke(main, ["health"])

        pattern = re.compile(r"^health-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}\.md$")
        assert all(pattern.match(p.name) for p in _reports(project_dir))

    def test_report_content_shape_unchanged(self, runner, project_dir):
        _set_retention(project_dir, "all")

        runner.invoke(main, ["health"])

        content = _reports(project_dir)[0].read_text()
        assert content.startswith("---\n")
        assert "# Health Report" in content
        assert "No issues found." in content

    def test_json_run_also_writes_under_all(self, runner, project_dir):
        """``--json`` never suppressed the report and still does not."""
        _set_retention(project_dir, "all")

        runner.invoke(main, ["health", "--json"])

        assert len(_reports(project_dir)) == 1


# ---------------------------------------------------------------------------
# "latest" — exactly one report survives
# ---------------------------------------------------------------------------


class TestRetentionLatest:
    """``latest`` prunes every prior report, then writes the new one."""

    def test_two_runs_leave_exactly_one_report(self, runner, project_dir, ticking_clock):
        _set_retention(project_dir, "latest")

        runner.invoke(main, ["health"])
        runner.invoke(main, ["health"])

        assert len(_reports(project_dir)) == 1

    def test_surviving_report_is_the_one_from_the_second_run(
        self, runner, project_dir, ticking_clock
    ):
        _set_retention(project_dir, "latest")

        runner.invoke(main, ["health"])
        first = _reports(project_dir)[0].name
        runner.invoke(main, ["health"])

        survivors = _reports(project_dir)
        assert len(survivors) == 1
        assert survivors[0].name != first

    def test_pre_existing_reports_are_pruned(self, runner, project_dir):
        _set_retention(project_dir, "latest")
        stale_a = _seed_stale_report(project_dir, "2020-01-01T00-00-00")
        stale_b = _seed_stale_report(project_dir, "2021-02-02T00-00-00")

        runner.invoke(main, ["health"])

        assert not stale_a.exists()
        assert not stale_b.exists()
        assert len(_reports(project_dir)) == 1

    def test_non_health_transient_docs_survive(self, runner, project_dir):
        _set_retention(project_dir, "latest")
        notes = _transient(project_dir) / "notes.md"
        notes.write_text(
            "---\nid: notes\ntitle: Notes\nsummary: working notes\n---\n\nKeep me.\n"
        )
        _seed_stale_report(project_dir, "2020-01-01T00-00-00")

        runner.invoke(main, ["health"])

        assert notes.exists()
        assert notes.read_text().endswith("Keep me.\n")

    def test_ten_runs_still_leave_one_report(self, runner, project_dir, ticking_clock):
        _set_retention(project_dir, "latest")

        for _ in range(10):
            runner.invoke(main, ["health"])

        assert len(_reports(project_dir)) == 1

    def test_json_run_also_prunes_under_latest(self, runner, project_dir):
        _set_retention(project_dir, "latest")
        _seed_stale_report(project_dir, "2020-01-01T00-00-00")

        runner.invoke(main, ["health", "--json"])

        assert len(_reports(project_dir)) == 1


# ---------------------------------------------------------------------------
# Fail-soft — a bad config value warns once and behaves as "none"
# ---------------------------------------------------------------------------


class TestRetentionInvalidConfigValue:
    """An out-of-set token warns on stderr and falls back to ``none``."""

    def test_out_of_set_value_warns_on_stderr(self, runner, project_dir):
        _set_retention(project_dir, "weekly")

        result = runner.invoke(main, ["health"])

        assert "lore: invalid value for health-report-retention at" in result.stderr
        assert "(expected one of: none, latest, all); using default" in result.stderr

    def test_out_of_set_value_writes_no_report(self, runner, project_dir):
        _set_retention(project_dir, "weekly")

        runner.invoke(main, ["health"])

        assert _reports(project_dir) == []

    def test_out_of_set_value_keeps_exit_code_zero_on_a_clean_project(
        self, runner, project_dir
    ):
        _set_retention(project_dir, "weekly")

        result = runner.invoke(main, ["health"])

        assert result.exit_code == 0
        assert "Health check passed. No issues found." in result.stdout

    def test_out_of_set_value_does_not_pollute_stdout(self, runner, project_dir):
        _set_retention(project_dir, "weekly")

        result = runner.invoke(main, ["health"])

        assert "invalid value" not in result.stdout

    def test_wrong_type_value_warns_and_writes_no_report(self, runner, project_dir):
        (project_dir / ".lore" / "config.toml").write_text(
            "health-report-retention = 3\n"
        )

        result = runner.invoke(main, ["health"])

        assert "lore: invalid type for health-report-retention at" in result.stderr
        assert "(expected str); using default" in result.stderr
        assert _reports(project_dir) == []
        assert result.exit_code == 0

    def test_malformed_toml_falls_back_to_none(self, runner, project_dir):
        (project_dir / ".lore" / "config.toml").write_text("not = valid = toml")

        result = runner.invoke(main, ["health"])

        assert "lore: invalid config at" in result.stderr
        assert _reports(project_dir) == []
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# --json envelope shape is identical in every mode
# ---------------------------------------------------------------------------


class TestJsonEnvelopeUnchanged:
    """The JSON envelope stays exactly ``{has_errors, issues}``."""

    @pytest.mark.parametrize("value", ["none", "latest", "all"])
    def test_json_keys_unchanged(self, runner, project_dir, value):
        _set_retention(project_dir, value)

        result = runner.invoke(main, ["health", "--json"])

        payload = json.loads(result.stdout)
        assert set(payload) == {"has_errors", "issues"}
        assert payload["has_errors"] is False
        assert payload["issues"] == []

    @pytest.mark.parametrize("value", ["none", "latest", "all"])
    def test_json_never_leaks_report_path(self, runner, project_dir, value):
        _set_retention(project_dir, value)

        result = runner.invoke(main, ["health", "--json"])

        assert "report_path" not in result.stdout

    def test_json_payload_identical_across_all_three_modes(self, runner, project_dir):
        payloads = {}
        for value in ("none", "latest", "all"):
            _set_retention(project_dir, value)
            payloads[value] = json.loads(
                runner.invoke(main, ["health", "--json"]).stdout
            )

        assert payloads["none"] == payloads["latest"] == payloads["all"]

    def test_json_issue_rows_identical_across_modes_on_a_dirty_project(
        self, runner, project_dir
    ):
        _break_a_doctrine(project_dir)
        payloads = {}
        for value in ("none", "latest", "all"):
            _set_retention(project_dir, value)
            payloads[value] = json.loads(
                runner.invoke(main, ["health", "--json"]).stdout
            )

        assert payloads["none"] == payloads["latest"] == payloads["all"]
        assert payloads["none"]["has_errors"] is True

    def test_json_out_of_set_value_envelope_unchanged(self, runner, project_dir):
        _set_retention(project_dir, "weekly")

        result = runner.invoke(main, ["health", "--json"])

        payload = json.loads(result.stdout)
        assert set(payload) == {"has_errors", "issues"}
        assert result.exit_code == 0
