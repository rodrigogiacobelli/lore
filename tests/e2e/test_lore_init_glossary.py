"""E2E tests for `lore init` glossary seeding (US-006) and default-file
glossary updates (US-007).

Specs:
  - lore codex show glossary-us-006
  - lore codex show glossary-us-007
Workflows:
  - conceptual-workflows-lore-init
  - conceptual-workflows-glossary

Per ADR-006, content tests on seeded files are substring/structural; full
byte-for-byte equality is verified only against the on-disk seed sources
(Scenario 7), never against hand-written constants — except for US-006
Scenario 1, where the Tech Spec pins exact 3-line / 4-line skeletons.

These tests must FAIL until US-006 / US-007 Green lands the seeding step
and the default-file updates.
"""

from __future__ import annotations

import subprocess
import tomllib

import pytest
import yaml
from click.testing import CliRunner

from lore.cli import main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fresh_dir(tmp_path, monkeypatch):
    """Empty tmp dir with cwd set; no `.lore/` yet."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture()
def initialised_dir(tmp_path, monkeypatch):
    """Tmp dir already initialised once via `lore init`."""
    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])
    return tmp_path


# ===========================================================================
# US-006 — Init seeding behaviour
# ===========================================================================


# ---------------------------------------------------------------------------
# Scenario 1 — Fresh init creates both files with exact contents
# ---------------------------------------------------------------------------


EXPECTED_GLOSSARY_SKELETON = (
    "# Project glossary — see the Glossary section of .lore/codex/codex.md.\n"
    "# Before adding a term, run: `lore artifact show glossary-design`.\n"
    "# Auto-surfaced on `lore codex show`. Toggle via .lore/config.toml.\n"
    "items: []\n"
)

EXPECTED_CONFIG_SKELETON = (
    "# Project-level Lore configuration.\n"
    "# Known keys (additional keys are accepted and ignored):\n"
    "#   show-glossary-on-codex-commands : bool, default true\n"
    "show-glossary-on-codex-commands = true\n"
)


def test_init_creates_glossary_yaml_with_exact_skeleton(runner, fresh_dir):
    """conceptual-workflows-lore-init — Scenario 1 (glossary half)."""
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0, result.output
    p = fresh_dir / ".lore" / "codex" / "glossary.yaml"
    assert p.is_file()
    assert p.read_text() == EXPECTED_GLOSSARY_SKELETON


def test_init_creates_config_toml_with_exact_skeleton(runner, fresh_dir):
    """conceptual-workflows-lore-init — Scenario 1 (config half)."""
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0, result.output
    p = fresh_dir / ".lore" / "config.toml"
    assert p.is_file()
    assert p.read_text() == EXPECTED_CONFIG_SKELETON


def test_init_stdout_announces_created_glossary_and_config(runner, fresh_dir):
    """conceptual-workflows-lore-init — Scenario 1 (stdout messages)."""
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0, result.output
    assert "Created codex/glossary.yaml" in result.output
    assert "Created config.toml" in result.output


# ---------------------------------------------------------------------------
# Scenario 2 — Re-running init does NOT overwrite user edits
# ---------------------------------------------------------------------------


def test_init_idempotent_does_not_overwrite_user_glossary(runner, initialised_dir):
    """conceptual-workflows-lore-init — Scenario 2 (FR-27)."""
    user_glossary = (
        "items:\n"
        "  - keyword: Constable\n"
        "    definition: orchestrator chore mission.\n"
    )
    glossary_p = initialised_dir / ".lore" / "codex" / "glossary.yaml"
    glossary_p.write_text(user_glossary)

    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0, result.output
    assert glossary_p.read_text() == user_glossary
    assert "Created codex/glossary.yaml" not in result.output


def test_init_idempotent_does_not_overwrite_user_config(runner, initialised_dir):
    """conceptual-workflows-lore-init — Scenario 2 (FR-28).

    The first ``lore init`` (in the fixture) MUST have created
    ``.lore/config.toml`` with the default skeleton.  The user then edits
    it, and a second ``lore init`` must preserve the edit byte-for-byte.
    """
    config_p = initialised_dir / ".lore" / "config.toml"
    # Precondition for the scenario: first init MUST have created the file.
    assert config_p.is_file(), (
        ".lore/config.toml must be created by the first `lore init` before "
        "this test exercises idempotency on user edits."
    )

    user_config = "show-glossary-on-codex-commands = false\n"
    config_p.write_text(user_config)

    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0, result.output
    assert config_p.read_text() == user_config
    assert "Created config.toml" not in result.output


# ---------------------------------------------------------------------------
# Scenario 3 — Init creates parent .lore/codex/
# ---------------------------------------------------------------------------


def test_init_creates_parent_codex_dir(runner, fresh_dir):
    """conceptual-workflows-lore-init — Scenario 3 (mkdir parents)."""
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0, result.output
    assert (fresh_dir / ".lore" / "codex").is_dir()
    assert (fresh_dir / ".lore" / "codex" / "glossary.yaml").is_file()


# ---------------------------------------------------------------------------
# Scenario 4 — Schema-clean after fresh init
# ---------------------------------------------------------------------------


def test_init_followed_by_health_schemas_is_clean(runner, fresh_dir):
    """conceptual-workflows-health — Scenario 4 (schema validity of seeded glossary).

    Pre-asserts that the seeded ``glossary.yaml`` exists (the new behaviour
    from US-006) and parses against the schema, then runs the health check.
    """
    init_res = runner.invoke(main, ["init"])
    assert init_res.exit_code == 0, init_res.output
    glossary_p = fresh_dir / ".lore" / "codex" / "glossary.yaml"
    assert glossary_p.is_file(), (
        "lore init must seed .lore/codex/glossary.yaml — required pre-condition "
        "for the schemas health check to exercise it."
    )
    health_res = runner.invoke(main, ["health", "--scope", "schemas"])
    assert health_res.exit_code == 0, health_res.output


# ---------------------------------------------------------------------------
# Scenario 5 — `lore glossary list` reports empty after init
# ---------------------------------------------------------------------------


def test_init_followed_by_glossary_list_is_empty(runner, fresh_dir):
    """conceptual-workflows-glossary — Scenario 5.

    The seeded ``glossary.yaml`` must exist (US-006) and parse with
    ``items: []``; ``lore glossary list`` then reports an empty result.
    """
    init_res = runner.invoke(main, ["init"])
    assert init_res.exit_code == 0, init_res.output
    glossary_p = fresh_dir / ".lore" / "codex" / "glossary.yaml"
    assert glossary_p.is_file(), (
        "lore init must seed .lore/codex/glossary.yaml — required pre-condition "
        "for glossary list to exercise the seeded skeleton."
    )

    res = runner.invoke(main, ["glossary", "list"])
    assert res.exit_code == 0, res.output
    out = res.output.strip()
    assert (
        out == "No glossary defined."
        or out.startswith("KEYWORD")
        or out == ""
    ), f"unexpected glossary list output: {out!r}"


# ---------------------------------------------------------------------------
# Scenario 6 — `lore codex show` emits no Glossary block (items: [])
# ---------------------------------------------------------------------------


def test_init_then_codex_show_no_glossary_block(runner, fresh_dir):
    """conceptual-workflows-glossary — Scenario 6.

    Pre-asserts the seeded ``glossary.yaml`` exists (US-006) so the
    auto-surface path is exercised against the empty ``items: []``
    skeleton; ``lore codex show`` must NOT emit a ``## Glossary`` block.
    """
    init_res = runner.invoke(main, ["init"])
    assert init_res.exit_code == 0, init_res.output
    glossary_p = fresh_dir / ".lore" / "codex" / "glossary.yaml"
    assert glossary_p.is_file(), (
        "lore init must seed .lore/codex/glossary.yaml — required pre-condition "
        "so the codex show auto-surface path is exercised."
    )

    transient = fresh_dir / ".lore" / "codex" / "transient"
    transient.mkdir(parents=True, exist_ok=True)
    (transient / "sample.md").write_text(
        "---\n"
        "id: sample\n"
        "title: Sample\n"
        "summary: test doc.\n"
        "---\n"
        "# Sample\n"
        "body text.\n"
    )
    res = runner.invoke(main, ["codex", "show", "sample"])
    assert res.exit_code == 0, res.output
    assert "## Glossary" not in res.output


# ---------------------------------------------------------------------------
# Scenario 7 — `.lore/.gitignore` un-ignores config.toml
# ---------------------------------------------------------------------------


def test_init_then_git_status_shows_config_toml_untracked(runner, fresh_dir):
    """conceptual-workflows-lore-init — Scenario 7 (effective un-ignore)."""
    # Initialise a git repo first so .gitignore takes effect
    subprocess.run(["git", "init", "-q"], cwd=fresh_dir, check=True)
    init_res = runner.invoke(main, ["init"])
    assert init_res.exit_code == 0, init_res.output

    proc = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=fresh_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    # `.lore/config.toml` should appear as an untracked file (?? prefix).
    assert ".lore/config.toml" in proc.stdout, (
        f".lore/config.toml must appear as untracked (not ignored). "
        f"git status output:\n{proc.stdout}"
    )


# ---------------------------------------------------------------------------
# Scenario 8 — Seeding step ordering
# ---------------------------------------------------------------------------


def test_init_seeding_step_ordering_docs_before_glossary(runner, fresh_dir):
    """conceptual-workflows-lore-init — Scenario 8 (AGENTS.md before glossary)."""
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0, result.output
    out = result.output

    # docs/* (LORE-AGENT.md) must be reported before glossary/config seeding.
    docs_idx = out.find("LORE-AGENT.md")
    glossary_idx = out.find("Created codex/glossary.yaml")
    config_idx = out.find("Created config.toml")

    assert docs_idx != -1, f"docs seeding output missing from init stdout:\n{out}"
    assert glossary_idx != -1, f"glossary seeding output missing:\n{out}"
    assert config_idx != -1, f"config seeding output missing:\n{out}"
    assert docs_idx < glossary_idx, (
        f"docs/LORE-AGENT.md (idx={docs_idx}) must precede glossary "
        f"(idx={glossary_idx}) in init stdout:\n{out}"
    )
    assert docs_idx < config_idx, (
        f"docs/LORE-AGENT.md (idx={docs_idx}) must precede config "
        f"(idx={config_idx}) in init stdout:\n{out}"
    )


# ---------------------------------------------------------------------------
# ADR-006 structural assertions on seeded contents
# ---------------------------------------------------------------------------


def test_init_seeded_glossary_parses_as_valid_yaml(runner, fresh_dir):
    """conceptual-workflows-lore-init — ADR-006 structural (Unit row 10)."""
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0, result.output
    data = yaml.safe_load(
        (fresh_dir / ".lore" / "codex" / "glossary.yaml").read_text()
    )
    assert isinstance(data, dict)
    assert isinstance(data.get("items"), list)


def test_init_seeded_config_parses_as_toml_with_known_key(runner, fresh_dir):
    """conceptual-workflows-lore-init — ADR-006 structural (Unit row 11)."""
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0, result.output
    with (fresh_dir / ".lore" / "config.toml").open("rb") as f:
        data = tomllib.load(f)
    assert data.get("show-glossary-on-codex-commands") is True


# ===========================================================================
# US-007 — Default-seeded doc, skill, and knight glossary updates
# ===========================================================================
#
# Removed per ADR-006 (decisions-006-no-seed-content-tests). Every US-007
# scenario asserted specific substrings or byte-equality on seeded default
# files (LORE-AGENT.md, codex.md, SKILL.md, scout.md). Existence and
# schema-clean invariants for those files are covered by the US-006 tests
# above and by `lore health --scope schemas`.
