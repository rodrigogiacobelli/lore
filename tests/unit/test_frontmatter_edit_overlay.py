"""Unit tests for overlay-aware field-edit mode (RED).

``lore codex edit --set/--unset/--add/--remove`` routes through
``frontmatter_edit.update_frontmatter_fields``, which validated the mutated
frontmatter against the *packaged* schema only. That made the documented
remediation for a newly required custom field — backfill the docs — impossible
from the CLI. Field-edit must resolve the same merged schema every other codex
writer uses, with the same transient exemption: overlays govern canonical codex
docs and sources, never ``codex/transient/*``.

Standards (ADR-006): assert edit outcomes, not packaged byte content.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lore import paths
from lore.frontmatter_edit import update_frontmatter_fields


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_skeleton(root: Path) -> Path:
    (root / ".lore" / "codex").mkdir(parents=True, exist_ok=True)
    return root


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


# ---------------------------------------------------------------------------
# canonical docs — merged schema
# ---------------------------------------------------------------------------


def test_field_edit_accepts_declared_custom_key(tmp_path):
    """With ``owner`` declared in the overlay, ``--set owner=alice`` writes it."""
    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string"}}},
    )
    path = _write_doc(tmp_path, "doc.md")

    update_frontmatter_fields(tmp_path, "codex", "doc", set_fields={"owner": "alice"})

    assert _meta_of(path).get("owner") == "alice"


def test_field_edit_backfills_newly_required_custom_key(tmp_path):
    """The remediation `lore health` prescribes — backfill a doc that predates a
    newly required custom field — must succeed."""
    _make_skeleton(tmp_path)
    _write_doc(tmp_path, "doc.md")
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string"}}, "required": ["owner"]},
    )

    update_frontmatter_fields(tmp_path, "codex", "doc", set_fields={"owner": "alice"})

    assert _meta_of(tmp_path / ".lore" / "codex" / "doc.md").get("owner") == "alice"


def test_field_edit_rejects_undeclared_key(tmp_path):
    """A typo is still rejected — the merged schema pins
    ``additionalProperties: false``."""
    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string"}}},
    )
    _write_doc(tmp_path, "doc.md")

    with pytest.raises(ValueError) as exc:
        update_frontmatter_fields(
            tmp_path, "codex", "doc", set_fields={"onwer": "alice"}
        )
    assert "Unknown property 'onwer'" in str(exc.value)


def test_field_edit_no_overlay_unchanged(tmp_path):
    """No overlay -> a custom key is still an unknown property (pre-feature)."""
    _make_skeleton(tmp_path)
    _write_doc(tmp_path, "doc.md")

    with pytest.raises(ValueError) as exc:
        update_frontmatter_fields(
            tmp_path, "codex", "doc", set_fields={"owner": "alice"}
        )
    assert "Unknown property 'owner'" in str(exc.value)


def test_field_edit_source_uses_source_overlay(tmp_path):
    """A source doc resolves the merged ``codex-source-frontmatter`` schema."""
    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-source-frontmatter",
        {"properties": {"ingested_at": {"type": "string"}}},
    )
    path = _write_doc(tmp_path, "sources/src.md", related=["doc"])

    update_frontmatter_fields(
        tmp_path, "codex", "src", set_fields={"ingested_at": "2026-06-18"}
    )

    assert _meta_of(path).get("ingested_at") == "2026-06-18"


# ---------------------------------------------------------------------------
# transient/* is out of overlay scope — packaged schema only
# ---------------------------------------------------------------------------


def test_field_edit_transient_ignores_overlay_required(tmp_path):
    """A required custom field must not block an unrelated edit to a transient
    working doc."""
    _make_skeleton(tmp_path)
    path = _write_doc(tmp_path, "transient/wip.md")
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string"}}, "required": ["owner"]},
    )

    update_frontmatter_fields(
        tmp_path, "codex", "wip", set_fields={"title": "Renamed"}
    )

    assert _meta_of(path).get("title") == "Renamed"


def test_field_edit_transient_rejects_custom_key(tmp_path):
    """Transient docs validate against the packaged schema, so the declared
    custom key is unknown there."""
    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string"}}},
    )
    _write_doc(tmp_path, "transient/wip.md")

    with pytest.raises(ValueError) as exc:
        update_frontmatter_fields(
            tmp_path, "codex", "wip", set_fields={"owner": "alice"}
        )
    assert "Unknown property 'owner'" in str(exc.value)


# ---------------------------------------------------------------------------
# CLI scalar coercion resolves the merged schema too
# ---------------------------------------------------------------------------


def test_coerce_scalar_splits_custom_array_field(tmp_path):
    """A custom array-of-string field comma-splits like a packaged one."""
    from lore.frontmatter_edit import _coerce_scalar_for_schema

    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"tags": {"type": "array", "items": {"type": "string"}}}},
    )

    out = _coerce_scalar_for_schema(
        "codex-frontmatter", "tags", "a, b", project_root=tmp_path
    )

    assert out == ["a", "b"]


def test_coerce_scalar_without_project_root_is_packaged(tmp_path):
    """Omitting ``project_root`` keeps the packaged-only behaviour."""
    from lore.frontmatter_edit import _coerce_scalar_for_schema

    assert (
        _coerce_scalar_for_schema("codex-frontmatter", "title", "hi") == "hi"
    )


# ---------------------------------------------------------------------------
# _coercion_context — which schema, and which overlay root, coercion resolves.
#
# The CLI used to hard-code "codex-frontmatter" plus ``project_root`` for the
# whole codex kind. A source doc therefore coerced against the canonical
# schema and never saw its own overlay, so a declared integer field reached
# validation as a string. ADR-019 fixes the overlay-eligible set at canonical
# codex docs *and* sources, stopping only at transient/.
# ---------------------------------------------------------------------------


def test_coercion_context_source_doc_resolves_the_source_schema(tmp_path):
    from lore.frontmatter_edit import _coercion_context

    _make_skeleton(tmp_path)
    _write_doc(tmp_path, "sources/src.md", related=["doc"])

    schema_kind, overlay_root = _coercion_context(tmp_path, "codex", "src")

    assert schema_kind == "codex-source-frontmatter"
    assert overlay_root == tmp_path


def test_coercion_context_canonical_doc_resolves_the_codex_schema(tmp_path):
    from lore.frontmatter_edit import _coercion_context

    _make_skeleton(tmp_path)
    _write_doc(tmp_path, "doc.md")

    schema_kind, overlay_root = _coercion_context(tmp_path, "codex", "doc")

    assert schema_kind == "codex-frontmatter"
    assert overlay_root == tmp_path


def test_coercion_context_transient_doc_has_no_overlay_root(tmp_path):
    """ADR-019: the transient subtree never consults the overlay."""
    from lore.frontmatter_edit import _coercion_context

    _make_skeleton(tmp_path)
    _write_doc(tmp_path, "transient/wip.md")

    schema_kind, overlay_root = _coercion_context(tmp_path, "codex", "wip")

    assert schema_kind == "codex-frontmatter"
    assert overlay_root is None


def test_coercion_context_non_codex_kind_has_no_overlay_root(tmp_path):
    from lore.frontmatter_edit import _coercion_context

    _make_skeleton(tmp_path)
    knights = tmp_path / ".lore" / "knights"
    knights.mkdir(parents=True, exist_ok=True)
    (knights / "tester.md").write_text(
        "---\nid: tester\ntitle: T\nsummary: s\n---\nBody.\n", encoding="utf-8"
    )

    schema_kind, overlay_root = _coercion_context(tmp_path, "knight", "tester")

    assert schema_kind == "knight-frontmatter"
    assert overlay_root is None


def test_coercion_context_unlocatable_doc_falls_back_to_the_canonical_schema(tmp_path):
    """A missing doc must not raise here — update_frontmatter_fields owns the
    canonical not-found error."""
    from lore.frontmatter_edit import _coercion_context

    _make_skeleton(tmp_path)

    schema_kind, overlay_root = _coercion_context(tmp_path, "codex", "nope")

    assert schema_kind == "codex-frontmatter"
    assert overlay_root is None


def test_coercion_context_only_returns_a_root_for_overlay_eligible_kinds(tmp_path):
    """Drift guard: the coercion path and ``validate_entity`` must agree on the
    eligible set, which lives in ``schemas._OVERLAY_KINDS`` (ADR-019)."""
    from lore import schemas as _schemas
    from lore.frontmatter_edit import _KINDS, _coercion_context

    _make_skeleton(tmp_path)
    _write_doc(tmp_path, "doc.md")
    _write_doc(tmp_path, "sources/src.md", related=["doc"])
    _write_doc(tmp_path, "transient/wip.md")

    for kind in _KINDS:
        for name in ("doc", "src", "wip", "tester", "nope"):
            schema_kind, overlay_root = _coercion_context(tmp_path, kind, name)
            if overlay_root is not None:
                assert schema_kind in _schemas._OVERLAY_KINDS
