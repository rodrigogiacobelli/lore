"""E2E cross-surface tests for custom fields on codex *source* docs (RED).

A custom field declared only in ``.lore/custom-schemas/codex-source-frontmatter.yaml``
validated fine through ``lore.api`` (which takes native Python values) but was
never coerced on the CLI: field-edit mode hard-coded ``codex-frontmatter`` plus
``project_root`` for the whole codex kind, so a source doc's own overlay was
never consulted and ``--set review_year=2026`` reached the validator as the
string ``'2026'``.

ADR-019 fixes the overlay-eligible set at canonical codex docs *and* the
sources layer, stopping only at ``transient/``. ADR-011: both surfaces must
agree.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from lore import paths
from lore.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_overlay(root: Path, kind: str, overlay: dict) -> Path:
    path = paths.custom_schema_path(root, kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(overlay), encoding="utf-8")
    return path


def _write_doc(root: Path, relpath: str, **fm) -> Path:
    name = Path(relpath).stem
    meta = {"id": name, "title": "Doc", "summary": "s"}
    meta.update(fm)
    path = root / ".lore" / "codex" / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n# Body\n",
        encoding="utf-8",
    )
    return path


def _meta_of(path: Path) -> dict:
    return yaml.safe_load(path.read_text().split("---\n")[1])


REVIEW_YEAR = {"properties": {"review_year": {"type": "integer"}}}


# ---------------------------------------------------------------------------
# A typed custom field on a source doc — both surfaces
# ---------------------------------------------------------------------------


class TestSourceOverlayIntegerField:
    def test_cli_set_coerces_the_declared_integer(self, runner, project_dir):
        _write_overlay(project_dir, "codex-source-frontmatter", REVIEW_YEAR)
        path = _write_doc(project_dir, "sources/mysrc.md", related=["codex"])

        result = runner.invoke(
            main, ["codex", "edit", "mysrc", "--set", "review_year=2026"]
        )

        assert result.exit_code == 0, (result.stdout or "") + (result.stderr or "")
        assert _meta_of(path)["review_year"] == 2026

    def test_api_set_accepts_the_same_field_natively(self, runner, project_dir):
        from lore.api import update_frontmatter_fields

        _write_overlay(project_dir, "codex-source-frontmatter", REVIEW_YEAR)
        path = _write_doc(project_dir, "sources/mysrc.md", related=["codex"])

        update_frontmatter_fields(
            project_dir, "codex", "mysrc", set_fields={"review_year": 2026}
        )

        assert _meta_of(path)["review_year"] == 2026

    def test_cli_and_api_write_the_same_frontmatter(self, runner, project_dir):
        from lore.api import update_frontmatter_fields

        _write_overlay(project_dir, "codex-source-frontmatter", REVIEW_YEAR)
        cli_doc = _write_doc(project_dir, "sources/clisrc.md", related=["codex"])
        api_doc = _write_doc(project_dir, "sources/apisrc.md", related=["codex"])

        result = runner.invoke(
            main, ["codex", "edit", "clisrc", "--set", "review_year=2026"]
        )
        assert result.exit_code == 0, (result.stdout or "") + (result.stderr or "")
        update_frontmatter_fields(
            project_dir, "codex", "apisrc", set_fields={"review_year": 2026}
        )

        assert _meta_of(cli_doc)["review_year"] == _meta_of(api_doc)["review_year"]

    def test_cli_rejects_a_non_integer_with_the_field_named(self, runner, project_dir):
        """Coercion runs, so the error names the field rather than the value."""
        _write_overlay(project_dir, "codex-source-frontmatter", REVIEW_YEAR)
        _write_doc(project_dir, "sources/mysrc.md", related=["codex"])

        result = runner.invoke(
            main, ["codex", "edit", "mysrc", "--set", "review_year=soon"]
        )

        assert result.exit_code == 1
        assert "review_year" in (result.stderr or "") + (result.stdout or "")


class TestSourceOverlayListField:
    def test_cli_add_splits_a_declared_array_field(self, runner, project_dir):
        _write_overlay(
            project_dir,
            "codex-source-frontmatter",
            {"properties": {"tags": {"type": "array", "items": {"type": "string"}}}},
        )
        path = _write_doc(project_dir, "sources/mysrc.md", related=["codex"])

        result = runner.invoke(
            main, ["codex", "edit", "mysrc", "--set", "tags=a, b"]
        )

        assert result.exit_code == 0, (result.stdout or "") + (result.stderr or "")
        assert _meta_of(path)["tags"] == ["a", "b"]


# ---------------------------------------------------------------------------
# Canonical docs keep working; transient stays out of overlay scope (ADR-019)
# ---------------------------------------------------------------------------


class TestOverlayScopeBoundaries:
    def test_cli_still_coerces_a_canonical_doc_custom_integer(self, runner, project_dir):
        _write_overlay(project_dir, "codex-frontmatter", REVIEW_YEAR)
        path = _write_doc(project_dir, "doc.md")

        result = runner.invoke(
            main, ["codex", "edit", "doc", "--set", "review_year=2026"]
        )

        assert result.exit_code == 0, (result.stdout or "") + (result.stderr or "")
        assert _meta_of(path)["review_year"] == 2026

    def test_transient_doc_rejects_the_custom_field_on_both_surfaces(
        self, runner, project_dir
    ):
        import pytest

        from lore.api import update_frontmatter_fields

        _write_overlay(project_dir, "codex-frontmatter", REVIEW_YEAR)
        _write_doc(project_dir, "transient/wip.md")

        result = runner.invoke(
            main, ["--json", "codex", "edit", "wip", "--set", "review_year=2026"]
        )
        assert result.exit_code == 1
        assert "Unknown property 'review_year'" in json.loads(result.stderr)["error"]

        with pytest.raises(ValueError, match="Unknown property 'review_year'"):
            update_frontmatter_fields(
                project_dir, "codex", "wip", set_fields={"review_year": 2026}
            )
