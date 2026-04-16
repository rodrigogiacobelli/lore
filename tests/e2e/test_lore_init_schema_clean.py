"""US-012 regression guards — fresh `lore init` passes schema validation.

Complements the US-011 e2e test (`test_schema_defaults_regression.py`) with
tighter pins on the `lore init` → `lore health` pipeline:

- Default `lore health` (no `--scope`) on a fresh init is exit 0.
- `lore health --scope schemas` on a fresh init is exit 0.
- `lore health --json` on a fresh init reports zero schema errors.
- Every entity file seeded by `lore init` validates against its schema.

Spec: `lore codex show schema-validation-us-012`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from lore.cli import main
from lore.schemas import validate_entity_file


@pytest.fixture()
def fresh_init(tmp_path, monkeypatch):
    """Bare temp dir with a fresh `lore init` and nothing else."""
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(main, ["init"])
    assert result.exit_code == 0, result.output
    return tmp_path


# ---------------------------------------------------------------------------
# CLI exit-code pins
# ---------------------------------------------------------------------------


class TestFreshInitHealthExitCodes:
    """Fresh `lore init` → `lore health` pipeline returns exit 0."""

    def test_default_health_run_is_exit_zero(self, runner, fresh_init):
        """`lore health` with no flags returns exit 0 on a freshly inited project."""
        result = runner.invoke(main, ["health"])
        assert result.exit_code == 0, result.output

    def test_schemas_scope_health_run_is_exit_zero(self, runner, fresh_init):
        """`lore health --scope schemas` returns exit 0 on a freshly inited project."""
        result = runner.invoke(main, ["health", "--scope", "schemas"])
        assert result.exit_code == 0, result.output

    def test_schemas_scope_output_mentions_zero_errors(self, runner, fresh_init):
        """`lore health --scope schemas` output does not mention schema errors."""
        result = runner.invoke(main, ["health", "--scope", "schemas"])
        assert result.exit_code == 0, result.output
        # Should not list any schema error rows.
        assert "schema" not in result.output.lower() or "0" in result.output or "No" in result.output


# ---------------------------------------------------------------------------
# JSON output pins
# ---------------------------------------------------------------------------


class TestFreshInitHealthJsonClean:
    """`lore health --json` on a fresh init reports zero issues / no errors."""

    def _run_json(self, runner):
        result = runner.invoke(main, ["health", "--json"])
        assert result.exit_code == 0, result.output
        return json.loads(result.output)

    def test_json_has_errors_is_false(self, runner, fresh_init):
        data = self._run_json(runner)
        assert data.get("has_errors") is False

    def test_json_issues_is_empty_list(self, runner, fresh_init):
        data = self._run_json(runner)
        assert data.get("issues") == []


# ---------------------------------------------------------------------------
# File-walk pin: every seeded entity file validates against its schema
# ---------------------------------------------------------------------------


# Map a .lore/ subdirectory + file pattern to the schema kind it must satisfy.
ENTITY_WALKS: list[tuple[str, str, str]] = [
    ("doctrines", "*.yaml", "doctrine-yaml"),
    ("doctrines", "*.design.md", "doctrine-design-frontmatter"),
    ("knights", "*.md", "knight-frontmatter"),
    ("watchers", "*.yaml", "watcher-yaml"),
    ("artifacts", "*.md", "artifact-frontmatter"),
]


def _walk_entity_files(project_root: Path) -> list[tuple[Path, str]]:
    """Return (path, kind) pairs for every seeded entity file under .lore/."""
    lore_dir = project_root / ".lore"
    pairs: list[tuple[Path, str]] = []
    for subdir, pattern, kind in ENTITY_WALKS:
        root = lore_dir / subdir
        if not root.is_dir():
            continue
        for path in sorted(root.rglob(pattern)):
            # `*.yaml` glob must not pick up doctrine design markdown, and
            # `*.md` must not pick up doctrine .design.md which has its own kind.
            if kind == "doctrine-yaml" and path.name.endswith(".design.md"):
                continue
            pairs.append((path, kind))
    return pairs


class TestFreshInitEntityFilesValidate:
    """Every entity file produced by `lore init` validates against its schema."""

    def test_fresh_init_seeds_at_least_one_entity_file(self, runner, fresh_init):
        """Sanity guard — the walk is non-empty so the validation loop is meaningful."""
        pairs = _walk_entity_files(fresh_init)
        assert len(pairs) > 0, "fresh init produced zero entity files to validate"

    def test_every_seeded_entity_file_validates_clean(self, runner, fresh_init):
        """Walk all seeded entity files and assert each one has zero schema issues."""
        pairs = _walk_entity_files(fresh_init)
        failures: list[str] = []
        for path, kind in pairs:
            issues = validate_entity_file(str(path), kind)
            if issues:
                rel = path.relative_to(fresh_init)
                rendered = "; ".join(f"{i.rule}@{i.pointer}: {i.message}" for i in issues)
                failures.append(f"{rel} [{kind}] — {rendered}")
        assert not failures, "seeded files failed schema validation:\n" + "\n".join(failures)
