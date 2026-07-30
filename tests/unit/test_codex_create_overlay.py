"""Unit tests for overlay-aware codex create/update validation (RED).

Spec: custom-codex-schemas-us-5 — ``codex.create_document`` and
``codex.update_document`` validate in-memory frontmatter against the merged
(packaged + overlay) schema by passing ``project_root`` into
``validate_entity``. A declared custom key is accepted; a typo raises
``ValueError`` (Unknown property, ``owner`` listed allowed); a collision
overlay raises ``ValueError`` carrying the ``OverlayError`` text. With no
overlay, behaviour is unchanged (pre-feature Unknown property).

Standards (ADR-006): assert create/edit outcomes, not packaged byte content.
Every test MUST fail until G2 Green threads ``project_root=project_root`` into
the two ``validate_entity`` calls. Import-level failures count as red.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lore import paths
from lore.codex import create_document, update_document


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


def _doc(name: str, **fm) -> str:
    meta = {"id": name, "title": "Doc", "summary": "s"}
    meta.update(fm)
    return "---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n# Body\n"


# ---------------------------------------------------------------------------
# create_document — declared key / typo / collision / no-overlay
# ---------------------------------------------------------------------------


def test_create_document_accepts_custom_key(tmp_path):
    """Overlay adds ``owner`` -> creating a doc with ``owner`` writes the file
    and returns normally (FR-9)."""
    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string"}}},
    )
    result = create_document(
        tmp_path, "owned", _doc("owned", owner="alice")
    )
    assert (tmp_path / ".lore" / "codex" / "owned.md").exists()
    assert result["id"] == "owned"


def test_create_document_rejects_undeclared(tmp_path):
    """An undeclared key (typo) raises ``ValueError`` whose message names the
    typo and lists ``owner`` among allowed keys."""
    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string"}}},
    )
    with pytest.raises(ValueError) as exc:
        create_document(tmp_path, "typo", _doc("typo", onwer="alice"))
    msg = str(exc.value)
    assert "Unknown property 'onwer'" in msg
    assert "owner" in msg


def test_create_document_collision_overlay_value_error(tmp_path):
    """A collision overlay (declares ``title``) raises ``ValueError`` carrying
    the ``OverlayError`` collision text (FR-10)."""
    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"title": {"type": "string"}}},
    )
    with pytest.raises(ValueError) as exc:
        create_document(tmp_path, "any-doc", _doc("any-doc"))
    assert (
        "property 'title' collides with a packaged field and cannot be "
        "overridden"
    ) in str(exc.value)


def test_create_document_collision_raises_overlay_error_subclass(tmp_path):
    """The collision error is specifically an ``OverlayError`` (ValueError
    subclass) propagating through the create contract unchanged."""
    from lore.schemas import OverlayError

    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"title": {"type": "string"}}},
    )
    with pytest.raises(OverlayError):
        create_document(tmp_path, "any-doc", _doc("any-doc"))


def test_create_document_no_overlay_unchanged(tmp_path):
    """No ``.lore/custom-schemas/`` -> a custom key still raises Unknown
    property (pre-feature behaviour, FR-2)."""
    _make_skeleton(tmp_path)
    assert not (tmp_path / ".lore" / "custom-schemas").exists()
    with pytest.raises(ValueError) as exc:
        create_document(tmp_path, "owned", _doc("owned", owner="alice"))
    assert "Unknown property 'owner'" in str(exc.value)


# ---------------------------------------------------------------------------
# update_document — re-validate merged schema, declared key persists
# ---------------------------------------------------------------------------


def test_update_document_revalidates_custom_key(tmp_path):
    """An edit re-validates merged frontmatter against the merged schema; a
    declared custom key persists (FR-9)."""
    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string"}}},
    )
    create_document(tmp_path, "owned", _doc("owned"))

    update_document(tmp_path, "owned", _doc("owned", owner="bob"))

    text = (tmp_path / ".lore" / "codex" / "owned.md").read_text()
    meta = yaml.safe_load(text.split("---\n")[1])
    assert meta.get("owner") == "bob"


def test_update_document_rejects_undeclared_key(tmp_path):
    """An edit setting an undeclared key raises ``ValueError`` (Unknown
    property) — edit accepts exactly what the merged schema declares."""
    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string"}}},
    )
    create_document(tmp_path, "owned", _doc("owned"))

    with pytest.raises(ValueError) as exc:
        update_document(tmp_path, "owned", _doc("owned", onwer="bob"))
    assert "Unknown property 'onwer'" in str(exc.value)


# ---------------------------------------------------------------------------
# transient/* is out of overlay scope — packaged schema only
# ---------------------------------------------------------------------------


def test_create_document_transient_ignores_overlay_required(tmp_path):
    """A required custom field must not block creating a transient working doc
    — overlays govern canonical codex docs only."""
    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string"}}, "required": ["owner"]},
    )

    result = create_document(tmp_path, "wip", _doc("wip"), group="transient")

    assert (tmp_path / ".lore" / "codex" / "transient" / "wip.md").exists()
    assert result["id"] == "wip"


def test_create_document_transient_nested_group_ignores_overlay_required(tmp_path):
    """The exemption covers the whole transient subtree, not just its root."""
    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string"}}, "required": ["owner"]},
    )

    create_document(tmp_path, "wip", _doc("wip"), group="transient/feat-x")

    assert (
        tmp_path / ".lore" / "codex" / "transient" / "feat-x" / "wip.md"
    ).exists()


def test_create_document_canonical_still_requires_overlay_field(tmp_path):
    """The exemption is scoped — a canonical doc still needs the custom field."""
    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string"}}, "required": ["owner"]},
    )

    with pytest.raises(ValueError) as exc:
        create_document(tmp_path, "doc", _doc("doc"), group="vision")
    assert "Missing required property 'owner'" in str(exc.value)


def test_create_document_transient_rejects_custom_key(tmp_path):
    """A transient doc validates against the packaged schema, so a declared
    custom key is still an unknown property there."""
    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string"}}},
    )

    with pytest.raises(ValueError) as exc:
        create_document(
            tmp_path, "wip", _doc("wip", owner="alice"), group="transient"
        )
    assert "Unknown property 'owner'" in str(exc.value)


def test_create_document_transient_survives_collision_overlay(tmp_path):
    """A malformed overlay never reaches transient docs — creating one still
    works while the canonical path raises ``OverlayError``."""
    _make_skeleton(tmp_path)
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"title": {"type": "string"}}},
    )

    create_document(tmp_path, "wip", _doc("wip"), group="transient")

    assert (tmp_path / ".lore" / "codex" / "transient" / "wip.md").exists()


def test_update_document_transient_ignores_overlay_required(tmp_path):
    """Editing a transient doc does not demand the required custom field."""
    _make_skeleton(tmp_path)
    create_document(tmp_path, "wip", _doc("wip"), group="transient")
    _write_overlay(
        tmp_path,
        "codex-frontmatter",
        {"properties": {"owner": {"type": "string"}}, "required": ["owner"]},
    )

    update_document(tmp_path, "wip", _doc("wip", summary="updated"))

    text = (tmp_path / ".lore" / "codex" / "transient" / "wip.md").read_text()
    meta = yaml.safe_load(text.split("---\n")[1])
    assert meta.get("summary") == "updated"
