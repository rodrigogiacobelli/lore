"""Unit tests for the codex_show CLI handler — auto-surface glossary.

Spec: glossary-us-004 (lore codex show glossary-us-004) — Unit Test Scenarios
rows 25–28 (CLI handler unit tests).
Workflow: conceptual-workflows-glossary

These tests describe the desired behaviour of `lore codex show` after US-004
lands the auto-surface integration. Every test must FAIL against current
production code.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from lore.cli import main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner():
    """Return a Click CliRunner with stderr captured separately."""
    return CliRunner()


@pytest.fixture()
def project_dir(tmp_path, monkeypatch):
    """Initialised lore project in a temp dir with a known codex doc + glossary."""
    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    # Seed a codex doc the test invocations reference.
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    (codex_dir / "doc-id.md").write_text(
        "---\n"
        "id: doc-id\n"
        "title: Doc\n"
        "summary: A test doc.\n"
        "---\n\n"
        "A Mission and a Quest body.\n"
    )

    # Seed a default glossary so tests that don't write their own still match.
    (codex_dir / "glossary.yaml").write_text(
        "items:\n"
        "  - keyword: Mission\n"
        "    definition: The unit of work.\n"
        "  - keyword: Quest\n"
        "    definition: A live grouping of Missions.\n",
        encoding="utf-8",
    )
    return tmp_path


def _write_glossary(root, content):
    """Write the glossary YAML at the canonical path."""
    target = root / ".lore" / "codex" / "glossary.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# Unit row 25 — `--skip-glossary` flag accepted; `match_glossary` NOT called
# ---------------------------------------------------------------------------


def test_codex_show_skip_glossary_flag_skips_match_call(project_dir, monkeypatch, runner):
    # conceptual-workflows-glossary — Unit row 25 (FR-15)
    called = []

    def _spy(*args, **kwargs):
        called.append((args, kwargs))
        return []

    monkeypatch.setattr("lore.glossary.match_glossary", _spy)
    res = runner.invoke(main, ["codex", "show", "doc-id", "--skip-glossary"])
    assert res.exit_code == 0, res.output
    assert called == []


# ---------------------------------------------------------------------------
# Unit row 26 — Config disabled → `match_glossary` NOT called
# ---------------------------------------------------------------------------


def test_codex_show_disabled_config_skips_match_call(project_dir, monkeypatch, runner):
    # conceptual-workflows-glossary — Unit row 26
    (project_dir / ".lore" / "config.toml").write_text(
        "show-glossary-on-codex-commands = false\n"
    )
    called = []

    def _spy(*args, **kwargs):
        called.append((args, kwargs))
        return []

    monkeypatch.setattr("lore.glossary.match_glossary", _spy)
    res = runner.invoke(main, ["codex", "show", "doc-id"])
    assert res.exit_code == 0, res.output
    assert called == []


# ---------------------------------------------------------------------------
# Unit row 27 — Fail-soft on GlossaryError (NFR-Reliability)
# ---------------------------------------------------------------------------


def test_codex_show_fail_soft_on_malformed_glossary(project_dir, runner):
    # conceptual-workflows-glossary — Unit row 27 (NFR-Reliability)
    _write_glossary(project_dir, "items: not-a-list\n")
    res = runner.invoke(main, ["codex", "show", "doc-id"])
    assert res.exit_code == 0
    assert "glossary unavailable:" in res.stderr
    assert "## Glossary" not in res.stdout


# ---------------------------------------------------------------------------
# Unit row 28 — JSON envelope ALWAYS includes "glossary" key (FR-18)
# ---------------------------------------------------------------------------


def test_codex_show_json_envelope_always_has_glossary_key(project_dir, runner):
    # conceptual-workflows-glossary — Unit row 28 (FR-18)
    res = runner.invoke(
        main, ["--json", "codex", "show", "doc-id", "--skip-glossary"]
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.stdout)
    assert "glossary" in payload
