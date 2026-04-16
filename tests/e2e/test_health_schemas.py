"""E2E tests for `lore health` schema validation.

US-004 Red — schema-validation-us-004
Workflow: conceptual-workflows-health (lore codex show conceptual-workflows-health)

Covers PRD Workflows 1, 2, 3, plus FR-1..FR-6 full-kind coverage, FR-9
multi-violation, and FR-25 previously-silent skip. Every test MUST fail
until US-004 Green lands.
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


def _knight_path(project_dir: Path) -> Path:
    return (
        project_dir
        / ".lore"
        / "knights"
        / "default"
        / "feature-implementation"
        / "pm.md"
    )


def _doctrine_design_path(project_dir: Path) -> Path:
    return (
        project_dir
        / ".lore"
        / "doctrines"
        / "default"
        / "feature-implementation"
        / "feature-implementation.design.md"
    )


# ---------------------------------------------------------------------------
# Scenario 1: Green audit on a clean project (PRD Workflow 1)
# ---------------------------------------------------------------------------


def test_e2e_workflow_1_green_on_fresh_init(runner, project_dir):
    """conceptual-workflows-lore-init — W1 green audit on pristine init."""
    result = runner.invoke(main, ["health"])
    assert result.exit_code == 0, result.output
    assert "Schema validation: 0 errors" in result.output


# ---------------------------------------------------------------------------
# Scenario 2: Hallucinated knight field caught (PRD Workflow 2)
# ---------------------------------------------------------------------------


def test_e2e_workflow_2_hallucinated_knight_field(runner, project_dir):
    """conceptual-workflows-knight-list — W2 stability field on a knight."""
    _write(
        _knight_path(project_dir),
        "---\n"
        "id: pm\n"
        "title: Product Manager\n"
        "summary: Writes PRDs.\n"
        "stability: experimental\n"
        "---\n"
        "# Body\n",
    )

    result = runner.invoke(main, ["health"])

    assert result.exit_code != 0, result.output
    assert (
        "ERROR .lore/knights/default/feature-implementation/pm.md"
        in result.output
    )
    assert "  kind: knight" in result.output
    assert "  schema: lore://schemas/knight-frontmatter" in result.output
    assert "  rule: additionalProperties" in result.output
    assert "  path: /stability" in result.output
    assert "Schema validation: 1 error" in result.output


# ---------------------------------------------------------------------------
# Scenario 3: Missing required field on doctrine design (PRD Workflow 3)
# ---------------------------------------------------------------------------


def test_e2e_workflow_3_missing_required_doctrine_design(runner, project_dir):
    """conceptual-workflows-doctrine-show — W3 missing summary on design."""
    path = _doctrine_design_path(project_dir)
    text = path.read_text(encoding="utf-8")
    new_text = "\n".join(
        line for line in text.splitlines() if not line.startswith("summary:")
    ) + "\n"
    path.write_text(new_text, encoding="utf-8")

    result = runner.invoke(main, ["health"])

    assert result.exit_code != 0, result.output
    assert "  kind: doctrine-design-frontmatter" in result.output
    assert "  schema: lore://schemas/doctrine-design-frontmatter" in result.output
    assert "  rule: required" in result.output
    assert "  path: /" in result.output
    assert "Schema validation: 1 error" in result.output


# ---------------------------------------------------------------------------
# Scenario 4: Every kind is covered (FR-1..FR-6)
# ---------------------------------------------------------------------------


def test_e2e_every_kind_covered(runner, project_dir):
    """conceptual-workflows-health — FR-1..FR-6 end-to-end, one bad per kind."""
    # Bad doctrine .yaml
    _write(
        project_dir
        / ".lore"
        / "doctrines"
        / "default"
        / "broken"
        / "broken.yaml",
        "id: broken\ntitle: Broken\nsummary: s\nbogus_top_level: nope\nsteps: []\n",
    )
    # Bad doctrine .design.md
    _write(
        project_dir
        / ".lore"
        / "doctrines"
        / "default"
        / "broken"
        / "broken.design.md",
        "---\nid: broken\ntitle: Broken\nbogus: yes\n---\nBody.\n",
    )
    # Bad knight
    _write(
        _knight_path(project_dir),
        "---\nid: pm\ntitle: Product Manager\nsummary: s\nstability: x\n---\n",
    )
    # Bad watcher
    _write(
        project_dir / ".lore" / "watchers" / "default" / "bad.yaml",
        "id: bad\ntitle: Bad\nevent: quest_close\naction: noop\nbogus: yes\n",
    )
    # Bad codex
    _write(
        project_dir / ".lore" / "codex" / "bad-doc.md",
        "---\nid: bad-doc\ntitle: Bad\nsummary: s\nbogus: yes\n---\nBody.\n",
    )
    # Bad artifact
    _write(
        project_dir / ".lore" / "artifacts" / "default" / "group" / "fi-bad.md",
        "---\nid: fi-bad\ntitle: Bad\nsummary: s\nbogus: yes\n---\nBody.\n",
    )

    result = runner.invoke(main, ["health"])

    assert result.exit_code != 0, result.output
    assert "Schema validation: 6 errors" in result.output
    for label in (
        "kind: doctrine-yaml",
        "kind: doctrine-design-frontmatter",
        "kind: knight",
        "kind: watcher",
        "kind: codex",
        "kind: artifact",
    ):
        assert label in result.output, f"missing {label!r} in:\n{result.output}"


# ---------------------------------------------------------------------------
# Scenario 5: Multiple violations per file all reported (FR-9)
# ---------------------------------------------------------------------------


def test_e2e_multiple_violations_one_file(runner, project_dir):
    """conceptual-workflows-health — FR-9 no short-circuit; three distinct blocks."""
    _write(
        _knight_path(project_dir),
        "---\nid: pm\nstability: x\n---\n",
    )

    result = runner.invoke(main, ["health"])

    assert result.exit_code != 0, result.output
    assert "Schema validation: 3 errors" in result.output
    # One additionalProperties + two required (title + summary)
    assert result.output.count("rule: additionalProperties") == 1
    assert result.output.count("rule: required") == 2


# ---------------------------------------------------------------------------
# Scenario 6: Previously silent skips are now loud (FR-25)
# ---------------------------------------------------------------------------


def test_e2e_previously_silent_skip_is_loud(runner, project_dir):
    """conceptual-workflows-artifact-new — FR-25 loud failure on no-frontmatter artifact."""
    _write(
        project_dir
        / ".lore"
        / "artifacts"
        / "default"
        / "group"
        / "broken.md",
        "No frontmatter at all.\n",
    )

    result = runner.invoke(main, ["health"])

    assert result.exit_code != 0, result.output
    assert "rule: missing-frontmatter" in result.output
    assert (
        "ERROR .lore/artifacts/default/group/broken.md" in result.output
    )


# ---------------------------------------------------------------------------
# US-006 — unparseable YAML, missing frontmatter, read-failed
# schema-validation-us-006 / conceptual-workflows-health — FR-10, FR-11, FR-25
# ---------------------------------------------------------------------------


def _good_watcher_text() -> str:
    return (
        "id: good\n"
        "title: Good\n"
        "summary: ok\n"
        "watch_target:\n  - src/\n"
        "interval: on_merge\n"
        "action:\n  - doctrine: feature-implementation\n"
    )


def test_us006_e2e_unparseable_watcher_yaml_scan_continues(runner, project_dir):
    """Scenario 1: one broken watcher + one good watcher — exactly one yaml-parse
    ERROR block, scan did not abort, summary reads 'Schema validation: 1 error'."""
    _write(
        project_dir / ".lore" / "watchers" / "default" / "broken.yaml",
        "watch_target: : :",
    )
    _write(
        project_dir / ".lore" / "watchers" / "default" / "good.yaml",
        _good_watcher_text(),
    )

    result = runner.invoke(main, ["health"])

    assert result.exit_code != 0, result.output
    # Exactly one yaml-parse rule line.
    assert result.output.count("rule: yaml-parse") == 1
    assert "  path: /" in result.output
    # Exactly one schema-block ERROR for the broken watcher — the good one is silent.
    schema_error_lines = [
        l for l in result.output.splitlines() if l.startswith("ERROR .lore/")
    ]
    assert len(schema_error_lines) == 1
    assert "broken.yaml" in schema_error_lines[0]
    assert "ERROR .lore/watchers/default/good.yaml" not in result.output
    # Summary line is exactly "Schema validation: 1 error".
    assert "Schema validation: 1 error\n" in result.output + "\n"
    assert "Schema validation: 1 errors" not in result.output


def test_us006_e2e_missing_frontmatter_exact_message(runner, project_dir):
    """Scenario 2: orphan.md with no frontmatter emits message line
    'message: File has no YAML frontmatter block' (no trailing period)."""
    _write(
        project_dir / ".lore" / "codex" / "notes" / "orphan.md",
        "just some notes\n",
    )

    result = runner.invoke(main, ["health"])

    assert result.exit_code != 0, result.output
    assert "  rule: missing-frontmatter" in result.output
    assert "  path: /" in result.output
    # Exact message line — no trailing period.
    assert "  message: File has no YAML frontmatter block\n" in (result.output + "\n")
    assert "  message: File has no YAML frontmatter block." not in result.output
    assert "Schema validation: 1 error" in result.output


def test_us006_e2e_read_failed_permission_denied_on_locked_knight(
    runner, project_dir, monkeypatch
):
    """Scenario 3: permission-denied file becomes one read-failed ERROR block
    whose message contains 'Permission denied'."""
    p = (
        project_dir
        / ".lore"
        / "knights"
        / "default"
        / "locked"
        / "pm.md"
    )
    _write(p, "---\nid: pm\ntitle: PM\nsummary: s\n---\n")

    real_read_text = Path.read_text
    real_open = open

    def boom_rt(self, *a, **kw):
        if self == p:
            raise PermissionError("Permission denied")
        return real_read_text(self, *a, **kw)

    def boom_open(path, *a, **kw):
        if str(path) == str(p):
            raise PermissionError("Permission denied")
        return real_open(path, *a, **kw)

    monkeypatch.setattr(Path, "read_text", boom_rt)
    monkeypatch.setattr("builtins.open", boom_open)

    result = runner.invoke(main, ["health"])

    assert result.exit_code != 0, result.output
    assert "  rule: read-failed" in result.output
    assert "Permission denied" in result.output
    # Exactly one read-failed block.
    assert result.output.count("rule: read-failed") == 1


def test_us006_e2e_yaml_parse_single_error_block_no_cascade(runner, project_dir):
    """Scenario 4: an unparseable doctrine yaml that would also fail schema
    validation if it parsed produces exactly one ERROR block (FR-10)."""
    _write(
        project_dir
        / ".lore"
        / "doctrines"
        / "default"
        / "broken"
        / "broken.yaml",
        # Both bad YAML and missing all required fields.
        "id: : :\nsteps: : : nope",
    )

    result = runner.invoke(main, ["health"])

    assert result.exit_code != 0, result.output
    error_lines = [l for l in result.output.splitlines() if l.startswith("ERROR ")]
    # Only one ERROR block for broken.yaml (may coexist with other kinds on a
    # pristine project — so filter).
    broken_errors = [l for l in error_lines if "broken.yaml" in l]
    assert len(broken_errors) == 1
    # And only one rule line for that file: yaml-parse. No cascading required
    # or additionalProperties rule lines from a second pass on the same file.
    assert result.output.count("rule: yaml-parse") == 1
    # The summary must count exactly one schema violation.
    assert "Schema validation: 1 error" in result.output
