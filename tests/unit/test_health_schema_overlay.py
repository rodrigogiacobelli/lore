"""Unit tests for overlay-aware `_check_schemas` routing (RED).

Spec: custom-codex-schemas-us-4 — health resolves the two codex kinds
(``codex-frontmatter``, ``codex-source-frontmatter``) through a new
module-level ``health.project_get_validator`` seam re-exporting
``schemas.project_validator_for``; all other kinds keep ``get_validator``.
A malformed (collision) overlay -> exactly one ``scan_failed`` HealthIssue,
no exception escapes, other kinds still scanned. The ``sources/*`` in-loop
override stays; the new seam is monkeypatchable via ``sys.modules[__name__]``.

Standards (ADR-006): assert audit behaviour, not packaged byte content.
Every test MUST fail until G2 Green adds ``project_get_validator`` and routes
the two codex kinds through it. Import-level failures count as red.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from lore import paths
from lore.health import _check_schemas


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_skeleton(root: Path) -> Path:
    lore = root / ".lore"
    for d in ("knights", "doctrines", "codex", "artifacts", "watchers"):
        (lore / d).mkdir(parents=True, exist_ok=True)
    return root


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_overlay(root: Path, kind: str, overlay: dict) -> Path:
    path = paths.custom_schema_path(root, kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(overlay), encoding="utf-8")
    return path


def _canonical(root: Path, name: str = "doc", extra: str = "") -> Path:
    p = root / ".lore" / "codex" / f"{name}.md"
    _write(
        p,
        "---\n"
        f"id: {name}\n"
        "title: Doc\n"
        "summary: s\n"
        f"{extra}"
        "---\n"
        "# Body\n",
    )
    return p


def _transient(root: Path, name: str = "wip", extra: str = "") -> Path:
    p = root / ".lore" / "codex" / "transient" / f"{name}.md"
    _write(
        p,
        "---\n"
        f"id: {name}\n"
        "title: WIP\n"
        "summary: s\n"
        f"{extra}"
        "---\n"
        "# Body\n",
    )
    return p


def _source(root: Path, name: str = "src", extra: str = "") -> Path:
    p = root / ".lore" / "codex" / "sources" / f"{name}.md"
    _write(
        p,
        "---\n"
        f"id: {name}\n"
        "title: Source\n"
        "summary: s\n"
        "related:\n"
        "  - doc\n"
        f"{extra}"
        "---\n"
        "# Body\n",
    )
    return p


# ---------------------------------------------------------------------------
# project_get_validator seam
# ---------------------------------------------------------------------------


def test_project_get_validator_reexports_resolver(tmp_path):
    """`health.project_get_validator(kind, root)` returns the same validator
    object as `schemas.project_validator_for(kind, root)`."""
    from lore import health, schemas

    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string"}}},
    )
    got = health.project_get_validator("codex-frontmatter", tmp_path)
    expected = schemas.project_validator_for("codex-frontmatter", tmp_path)
    assert got is expected


# ---------------------------------------------------------------------------
# routing: two codex kinds via project_get_validator, rest via get_validator
# ---------------------------------------------------------------------------


def test_check_schemas_routes_codex_kinds_project_aware(tmp_path, monkeypatch):
    """The two codex kinds resolve via ``project_get_validator``; all other
    kinds via ``get_validator`` (FR-8)."""
    from lore import health

    _make_skeleton(tmp_path)
    _canonical(tmp_path)

    project_calls: list[str] = []
    plain_calls: list[str] = []

    real_project = health.project_get_validator
    real_plain = health.get_validator

    def spy_project(kind, project_root):
        project_calls.append(kind)
        return real_project(kind, project_root)

    def spy_plain(kind):
        plain_calls.append(kind)
        return real_plain(kind)

    monkeypatch.setattr(health, "project_get_validator", spy_project)
    monkeypatch.setattr(health, "get_validator", spy_plain)

    _check_schemas(tmp_path)

    assert "codex-frontmatter" in project_calls
    assert "codex-source-frontmatter" in project_calls
    # non-codex kinds never go through the project-aware seam
    assert "knight-frontmatter" not in project_calls
    assert "knight-frontmatter" in plain_calls
    # codex kinds never go through the plain seam
    assert "codex-frontmatter" not in plain_calls
    assert "codex-source-frontmatter" not in plain_calls


def test_project_get_validator_monkeypatchable(tmp_path, monkeypatch):
    """Monkeypatching ``health.project_get_validator`` is honored — the stub is
    resolved via ``sys.modules[__name__]`` inside ``_check_schemas``."""
    from lore import health

    _make_skeleton(tmp_path)
    _canonical(tmp_path)

    calls: list[str] = []

    def stub(kind, project_root):
        calls.append(kind)
        return health.get_validator(kind)

    monkeypatch.setattr(health, "project_get_validator", stub)
    _check_schemas(tmp_path)

    assert "codex-frontmatter" in calls
    assert "codex-source-frontmatter" in calls


# ---------------------------------------------------------------------------
# collision overlay -> exactly one scan_failed, no raise, other kinds scanned
# ---------------------------------------------------------------------------


def test_check_schemas_overlay_error_scan_failed(tmp_path):
    """A codex-frontmatter collision overlay yields exactly one
    ``HealthIssue(check="scan_failed")`` naming the overlay path; no exception
    escapes (FR-10)."""
    _make_skeleton(tmp_path)
    _canonical(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"title": {"type": "string"}}},
    )

    issues = _check_schemas(tmp_path)  # must not raise

    scan_failed = [i for i in issues if i.check == "scan_failed"]
    assert len(scan_failed) == 1, scan_failed
    issue = scan_failed[0]
    assert issue.schema_id == "lore://schemas/codex-frontmatter"
    assert "custom-schemas/codex-frontmatter.yaml" in issue.detail
    assert "collides with a packaged field" in issue.detail


def test_check_schemas_overlay_error_other_kinds_still_scanned(tmp_path):
    """FR-10: the collision aborts only the codex kind; a bad knight is still
    caught."""
    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"title": {"type": "string"}}},
    )
    _write(
        tmp_path
        / ".lore"
        / "knights"
        / "default"
        / "feature-implementation"
        / "pm.md",
        "---\nid: pm\ntitle: PM\nsummary: s\nstability: x\n---\n# Body\n",
    )

    issues = _check_schemas(tmp_path)

    knight_schema_issues = [
        i for i in issues if i.entity_type == "knight" and i.check == "schema"
    ]
    assert knight_schema_issues, issues


# ---------------------------------------------------------------------------
# sources/* in-loop override preserved, fed the merged source validator
# ---------------------------------------------------------------------------


def test_check_schemas_source_override_preserved(tmp_path):
    """With a source overlay declaring ``ingested_at``, a source doc carrying
    it validates clean (routed to the merged codex-source-frontmatter), while a
    canonical doc carrying ``ingested_at`` still fails Unknown property — proves
    the in-loop override is intact and source-only."""
    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-source-frontmatter",
        {"properties": {"ingested_at": {"type": "string"}}},
    )
    _canonical(tmp_path)
    _source(tmp_path, "src", extra="ingested_at: '2026-06-18'\n")

    issues = _check_schemas(tmp_path)

    # source doc with the declared key -> no schema issue for it
    src_issues = [
        i for i in issues if i.check == "schema" and "sources/src.md" in i.id
    ]
    assert src_issues == [], src_issues


def test_check_schemas_source_override_rejects_canonical_custom_key(tmp_path):
    """The source overlay must NOT leak into the canonical validator: a
    canonical doc with ``ingested_at`` still fails Unknown property."""
    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-source-frontmatter",
        {"properties": {"ingested_at": {"type": "string"}}},
    )
    _canonical(tmp_path, name="doc", extra="ingested_at: '2026-06-18'\n")
    _source(tmp_path, "src")

    issues = _check_schemas(tmp_path)

    canonical_issues = [
        i
        for i in issues
        if i.check == "schema"
        and i.id.endswith("codex/doc.md")
        and "Unknown property 'ingested_at'" in i.detail
    ]
    assert canonical_issues, issues


# ---------------------------------------------------------------------------
# transient/* is out of overlay scope — packaged schema only
# ---------------------------------------------------------------------------


def test_check_schemas_transient_exempt_from_overlay_required(tmp_path):
    """An overlay that marks ``owner`` required must not reach transient working
    docs: a transient doc without ``owner`` produces no schema issue."""
    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string"}}, "required": ["owner"]},
    )
    _canonical(tmp_path, "doc", extra="owner: alice\n")
    _transient(tmp_path, "wip")

    issues = _check_schemas(tmp_path)

    transient_issues = [
        i for i in issues if i.check == "schema" and "transient/wip.md" in i.id
    ]
    assert transient_issues == [], transient_issues


def test_check_schemas_health_report_shape_survives_required_overlay(tmp_path):
    """`lore health` writes its own reports into ``codex/transient/`` with only
    id/title/summary — a required-field overlay must never flag them."""
    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string"}}, "required": ["owner"]},
    )
    _transient(tmp_path, "health-2026-06-25T10-00-00")

    issues = _check_schemas(tmp_path)

    report_issues = [i for i in issues if i.check == "schema" and "health-" in i.id]
    assert report_issues == [], report_issues


def test_check_schemas_canonical_still_requires_overlay_field(tmp_path):
    """The transient exemption is scoped — a canonical doc missing the required
    custom field is still an error."""
    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string"}}, "required": ["owner"]},
    )
    _canonical(tmp_path, "doc")
    _transient(tmp_path, "wip")

    issues = _check_schemas(tmp_path)

    canonical_issues = [
        i
        for i in issues
        if i.check == "schema"
        and i.id.endswith("codex/doc.md")
        and "Missing required property 'owner'" in i.detail
    ]
    assert canonical_issues, issues


def test_check_schemas_transient_rejects_custom_key(tmp_path):
    """Custom fields are canonical-codex governance: a transient doc carrying
    the declared custom key fails against the packaged schema."""
    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string"}}},
    )
    _transient(tmp_path, "wip", extra="owner: alice\n")

    issues = _check_schemas(tmp_path)

    transient_issues = [
        i
        for i in issues
        if i.check == "schema"
        and "transient/wip.md" in i.id
        and "Unknown property 'owner'" in i.detail
    ]
    assert transient_issues, issues


def test_check_schemas_transient_still_packaged_validated(tmp_path):
    """Exempt from the overlay, not from validation — a transient doc missing a
    packaged required field is still an error."""
    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string"}}, "required": ["owner"]},
    )
    _write(
        tmp_path / ".lore" / "codex" / "transient" / "wip.md",
        "---\nid: wip\ntitle: WIP\n---\n# Body\n",
    )

    issues = _check_schemas(tmp_path)

    transient_issues = [
        i
        for i in issues
        if i.check == "schema"
        and "transient/wip.md" in i.id
        and "Missing required property 'summary'" in i.detail
    ]
    assert transient_issues, issues


def test_check_schemas_transient_routes_through_packaged_seam(tmp_path, monkeypatch):
    """Transient docs resolve ``codex-frontmatter`` through the packaged
    ``get_validator`` seam; canonical/source docs keep the project-aware seam."""
    from lore import health

    _make_skeleton(tmp_path)
    _canonical(tmp_path)
    _transient(tmp_path, "wip")

    project_calls: list[str] = []
    plain_calls: list[str] = []

    real_project = health.project_get_validator
    real_plain = health.get_validator

    def spy_project(kind, project_root):
        project_calls.append(kind)
        return real_project(kind, project_root)

    def spy_plain(kind):
        plain_calls.append(kind)
        return real_plain(kind)

    monkeypatch.setattr(health, "project_get_validator", spy_project)
    monkeypatch.setattr(health, "get_validator", spy_plain)

    _check_schemas(tmp_path)

    assert "codex-frontmatter" in plain_calls
    assert "codex-frontmatter" in project_calls


def test_check_schemas_transient_scanned_despite_broken_overlay(tmp_path):
    """A malformed canonical overlay must not blind the transient subtree — it
    never used the overlay, so its packaged validation still runs."""
    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"title": {"type": "string"}}},
    )
    _write(
        tmp_path / ".lore" / "codex" / "transient" / "wip.md",
        "---\nid: wip\ntitle: WIP\n---\n# Body\n",
    )

    issues = _check_schemas(tmp_path)

    transient_issues = [
        i
        for i in issues
        if i.check == "schema"
        and "transient/wip.md" in i.id
        and "Missing required property 'summary'" in i.detail
    ]
    assert transient_issues, issues
