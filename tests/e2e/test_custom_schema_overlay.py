"""E2E tests for custom codex frontmatter schema overlays (RED).

Specs:
- custom-codex-schemas-us-4 — `lore health` overlay-aware schema audit
  (codex-frontmatter + codex-source-frontmatter merged validators;
  malformed overlay -> one clean ``scan_failed``; no-overlay baseline).
- custom-codex-schemas-us-5 — `lore codex new` / `lore codex edit` accept
  declared custom keys at write time, reject typos, surface collision
  ``OverlayError`` as a clean ValueError.

Standards (ADR-006): assert audit/CLI behaviour, never packaged byte content.
Click CLI tested via CliRunner reading ``result.stdout`` / ``result.stderr``
separately (no ``mix_stderr``). Every test MUST fail until G2 Green wires the
``project_get_validator`` health seam and the create/edit ``project_root``
keyword.
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


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_overlay(root: Path, kind: str, overlay: dict) -> Path:
    path = paths.custom_schema_path(root, kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(overlay), encoding="utf-8")
    return path


def _clean_canonical_doc(project_dir: Path, name: str = "clean-doc") -> Path:
    p = project_dir / ".lore" / "codex" / f"{name}.md"
    _write(
        p,
        "---\n"
        f"id: {name}\n"
        "title: Clean Doc\n"
        "summary: A clean canonical doc.\n"
        "---\n"
        "# Body\n",
    )
    return p


def _source_doc(project_dir: Path, name: str, extra_fm: str = "") -> Path:
    """A codex source doc (related minItems:1 required)."""
    p = project_dir / ".lore" / "codex" / "sources" / f"{name}.md"
    _write(
        p,
        "---\n"
        f"id: {name}\n"
        "title: Source Doc\n"
        "summary: A source snapshot.\n"
        "related:\n"
        "  - clean-doc\n"
        f"{extra_fm}"
        "---\n"
        "# Body\n",
    )
    return p


# ===========================================================================
# US-4 — health overlay-aware schema audit
# ===========================================================================


# E2E — source overlay honored, canonical unaffected (Scenario 1, FR-8)
def test_health_honors_source_overlay(runner, project_dir):
    """Source doc's declared ``ingested_at`` validates against the merged
    codex-source-frontmatter; canonical doc validates against the unmodified
    merged canonical schema; exit 0, schemas OK."""
    _write_overlay(
        project_dir,
        "codex-source-frontmatter",
        {"properties": {"ingested_at": {"type": "string"}}},
    )
    _clean_canonical_doc(project_dir)
    _source_doc(project_dir, "src-doc", extra_fm="ingested_at: '2026-06-18'\n")

    result = runner.invoke(main, ["health", "--scope", "schemas"])

    assert result.exit_code == 0, result.stdout
    assert "Schema validation: 0 errors" in result.stdout


# E2E — malformed collision overlay -> one scan_failed, audit continues
# (Scenario 2, FR-10)
def test_health_malformed_overlay_scan_failed(runner, project_dir):
    """A codex-frontmatter overlay that collides with packaged ``title`` yields
    exactly one ``scan_failed`` issue naming the overlay path, schema_id
    ``lore://schemas/codex-frontmatter``, no traceback, other kinds still
    scanned."""
    _write_overlay(
        project_dir,
        "codex-frontmatter",
        {"properties": {"title": {"type": "string"}}},
    )

    result = runner.invoke(main, ["--json", "health", "--scope", "schemas"])

    assert result.exit_code != 0, result.stdout
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr
    envelope = json.loads(result.stdout)
    scan_failed = [i for i in envelope["issues"] if i["check"] == "scan_failed"]
    assert len(scan_failed) == 1, scan_failed
    issue = scan_failed[0]
    assert issue["schema_id"] == "lore://schemas/codex-frontmatter"
    assert (
        ".lore/custom-schemas/codex-frontmatter.yaml: property 'title' "
        "collides with a packaged field and cannot be overridden"
    ) in issue["detail"]


def test_health_malformed_overlay_other_kinds_still_scanned(runner, project_dir):
    """FR-10: after the collision overlay aborts the codex kind, a bad knight
    is still caught — failure isolation across kinds."""
    _write_overlay(
        project_dir,
        "codex-frontmatter",
        {"properties": {"title": {"type": "string"}}},
    )
    # Hallucinated knight field — must still be caught.
    _write(
        project_dir
        / ".lore"
        / "knights"
        / "default"
        / "feature-implementation"
        / "pm.md",
        "---\nid: pm\ntitle: PM\nsummary: s\nstability: x\n---\n# Body\n",
    )

    result = runner.invoke(main, ["--json", "health", "--scope", "schemas"])

    assert result.exit_code != 0, result.stdout
    envelope = json.loads(result.stdout)
    knight_issues = [
        i
        for i in envelope["issues"]
        if i["entity_type"] == "knight" and i["check"] == "schema"
    ]
    assert knight_issues, envelope["issues"]


# E2E — no-overlay baseline identical (Scenario 3, FR-2)
def test_health_no_overlay_baseline_clean(runner, project_dir):
    """No ``.lore/custom-schemas/`` -> pristine project still passes."""
    assert not (project_dir / ".lore" / "custom-schemas").exists()
    result = runner.invoke(main, ["health", "--scope", "schemas"])
    assert result.exit_code == 0, result.stdout
    assert "Schema validation: 0 errors" in result.stdout


def test_health_no_overlay_undeclared_key_still_unknown(runner, project_dir):
    """No overlay -> a doc with a custom key still fails as Unknown property."""
    _write(
        project_dir / ".lore" / "codex" / "tagged.md",
        "---\nid: tagged\ntitle: T\nsummary: s\nowner: alice\n---\n# Body\n",
    )
    result = runner.invoke(main, ["--json", "health", "--scope", "schemas"])
    assert result.exit_code != 0, result.stdout
    envelope = json.loads(result.stdout)
    assert any(
        "Unknown property 'owner'" in i["detail"] for i in envelope["issues"]
    ), envelope["issues"]


# ===========================================================================
# US-5 — codex create/edit overlay validation
# ===========================================================================


# E2E — create accepts declared custom key (Scenario 1, FR-9)
def test_codex_create_accepts_custom_key(runner, project_dir):
    """Overlay declares ``owner`` -> ``codex new`` with ``owner: alice``
    succeeds and ``codex show`` returns the key."""
    _write_overlay(
        project_dir,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string", "minLength": 1}}},
    )
    src = project_dir / "doc.md"
    _write(
        src,
        "---\nid: owned\ntitle: Owned\nsummary: s\nowner: alice\n---\n# Body\n",
    )

    result = runner.invoke(main, ["codex", "new", "owned", "-f", str(src)])

    assert result.exit_code == 0, (result.stdout, result.stderr)
    written = project_dir / ".lore" / "codex" / "owned.md"
    assert written.exists()
    # codex show is body-only by contract (test_codex_show_glossary_parity);
    # the custom key lives in frontmatter, so assert it on the written file.
    meta = yaml.safe_load(written.read_text(encoding="utf-8").split("---\n")[1])
    assert meta.get("owner") == "alice"


# E2E — create rejects typo, owner listed allowed (Scenario 2, FR-6)
def test_codex_create_rejects_typo(runner, project_dir):
    """Overlay declares ``owner`` -> a doc with ``onwer`` typo is rejected;
    stderr names the typo and lists ``owner`` among allowed keys."""
    _write_overlay(
        project_dir,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string", "minLength": 1}}},
    )
    src = project_dir / "doc.md"
    _write(
        src,
        "---\nid: typo\ntitle: Typo\nsummary: s\nonwer: alice\n---\n# Body\n",
    )

    result = runner.invoke(main, ["codex", "new", "typo", "-f", str(src)])

    assert result.exit_code != 0, result.stdout
    assert "Unknown property 'onwer'" in result.stderr
    assert "owner" in result.stderr


# E2E — collision overlay -> clean ValueError text, no traceback (Scenario 3,
# FR-10)
def test_codex_create_collision_overlay_clean_error(runner, project_dir):
    """Overlay declaring ``title`` (collision) -> ``codex new`` fails with the
    OverlayError collision text and no Python traceback."""
    _write_overlay(
        project_dir,
        "codex-frontmatter",
        {"properties": {"title": {"type": "string"}}},
    )
    src = project_dir / "doc.md"
    _write(
        src,
        "---\nid: any-doc\ntitle: Any\nsummary: s\n---\n# Body\n",
    )

    result = runner.invoke(main, ["codex", "new", "any-doc", "-f", str(src)])

    assert result.exit_code != 0, result.stdout
    assert (
        "property 'title' collides with a packaged field and cannot be "
        "overridden"
    ) in result.stderr
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr
