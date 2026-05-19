"""Unit tests for US-006 + US-007 (group G4).

US-006: glossary deprecated-term scan removal — observable behaviour at
the `_check_glossary` and `_ESCALATED_WARNING_CHECKS` surfaces.
US-007: glossary deprecated-term scan removal — code surface deletion
inside `lore.health` (no orphan family-3 symbols left behind).

Spec: lore codex show health-bindings-glossary-us-006 health-bindings-glossary-us-007
PRD: health-bindings-glossary-prd (FR-19, FR-20, FR-21, FR-22, FR-23, FR-24)
"""

from __future__ import annotations

import inspect
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Helpers (local to keep this file hermetic — TDD-Red MUST NOT refactor
# existing test helpers).
# ---------------------------------------------------------------------------


def _make_lore_project(tmp_path: Path) -> Path:
    """Minimal .lore/ skeleton — mirrors tests/unit/test_health.py helper."""
    lore = tmp_path / ".lore"
    for d in ("codex", "knights", "doctrines", "artifacts", "watchers"):
        (lore / d).mkdir(parents=True, exist_ok=True)
    (lore / "codex" / "transient").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _write_glossary_yaml(project: Path, content: str) -> Path:
    target = project / ".lore" / "codex" / "glossary.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def _seed_glossary_for_health(project: Path, *, items: list[dict]) -> Path:
    """Write `.lore/codex/glossary.yaml` from a list of item dicts."""
    return _write_glossary_yaml(project, yaml.safe_dump({"items": items}, sort_keys=False))


def _seed_codex_doc_for_health(project: Path, doc_id: str, *, body: str) -> Path:
    """Write a codex doc with frontmatter id/title/summary and the given body."""
    codex_dir = project / ".lore" / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    fm = (
        "---\n"
        f"id: {doc_id}\n"
        f"title: {doc_id}\n"
        "summary: s\n"
        "---\n"
        f"{body}\n"
    )
    path = codex_dir / f"{doc_id}.md"
    path.write_text(fm, encoding="utf-8")
    return path


# ===========================================================================
# US-006 Unit — `_check_glossary` no longer surfaces deprecated-term rows
# ===========================================================================


def test_check_glossary_emits_no_deprecated_term_rows(tmp_path):
    """US-006 unit row 1 — FR-22.

    Even when a `do_not_use` term appears in body prose across the codex,
    `_check_glossary` returns zero `glossary_deprecated_term` rows.
    """
    from lore.health import _check_glossary

    project = _make_lore_project(tmp_path)
    _seed_glossary_for_health(
        project,
        items=[
            {
                "keyword": "Mission",
                "definition": "Unit of executable work.",
                "do_not_use": ["mission step"],
            },
        ],
    )
    _seed_codex_doc_for_health(
        project, "doc-a", body="Discussing mission step deprecation."
    )
    _seed_codex_doc_for_health(
        project, "doc-b", body="Another mission step note here."
    )
    issues = _check_glossary(project)
    assert [i for i in issues if i.check == "glossary_deprecated_term"] == []


def test_check_glossary_collision_family_intact(tmp_path):
    """US-006 unit row 2 — FR-21 family-2 wiring still fires.

    `do_not_use_collision` (intra-file) is independent of the deleted family-3
    cross-codex scan and MUST keep producing exactly one error row.
    """
    from lore.health import _check_glossary

    project = _make_lore_project(tmp_path)
    _seed_glossary_for_health(
        project,
        items=[
            {"keyword": "Foo", "definition": "f", "do_not_use": ["clash"]},
            {"keyword": "Bar", "definition": "b", "do_not_use": ["clash"]},
        ],
    )
    issues = _check_glossary(project)
    collisions = [i for i in issues if i.check == "do_not_use_collision"]
    assert len(collisions) == 1
    assert collisions[0].severity == "error"


def test_escalated_warning_checks_no_glossary_deprecated_term():
    """US-006 unit row 3 — FR-22 regression guard.

    `_ESCALATED_WARNING_CHECKS` MUST NOT contain `"glossary_deprecated_term"`.
    """
    from lore.health import _ESCALATED_WARNING_CHECKS

    assert "glossary_deprecated_term" not in _ESCALATED_WARNING_CHECKS


def test_escalated_warning_checks_shrinks_to_alias_keyword_collision_only():
    """G3 deferred — `_ESCALATED_WARNING_CHECKS` shrinks to a single entry.

    PRD FR-22 + US-006 Implementation Approach: resulting set is exactly
    `frozenset({"alias_keyword_collision"})`. This pins the cumulative
    end-state after US-004 (drop `empty_glob_binding`) and US-006 (drop
    `glossary_deprecated_term`).

    Restored per G4 orchestrator note — G3 Red's
    `test_escalated_warning_checks_post_us004_shape` was removed but the
    cumulative-shape assertion belongs in this Red set.
    """
    from lore.health import _ESCALATED_WARNING_CHECKS

    assert _ESCALATED_WARNING_CHECKS == frozenset({"alias_keyword_collision"})


def test_do_not_use_schema_field_unchanged(tmp_path):
    """US-006 unit row 7 — FR-24 schema field preserved + family-3 absent.

    The `do_not_use` schema field validation (1-80 char strings) is
    unchanged. A too-long value (81 chars) still surfaces a glossary
    schema error. Paired with a forward-looking assertion: on a valid
    fixture with prose mentions, `_check_glossary` produces zero
    `glossary_deprecated_term` rows — proves the family-3 wiring is gone
    while family-1 still fires.
    """
    from lore.health import _check_glossary, _check_schemas

    project = _make_lore_project(tmp_path)
    _seed_glossary_for_health(
        project,
        items=[
            {
                "keyword": "Mission",
                "definition": "Unit of work.",
                "do_not_use": ["x" * 81],
            },
        ],
    )
    issues = _check_schemas(project)
    schema_errs = [i for i in issues if i.entity_type == "glossary"]
    assert len(schema_errs) >= 1

    # Forward-looking pair: valid glossary + prose still produces zero
    # `glossary_deprecated_term` rows post-Green.
    _seed_glossary_for_health(
        project,
        items=[
            {
                "keyword": "Mission",
                "definition": "Unit of work.",
                "do_not_use": ["mission step"],
            },
        ],
    )
    _seed_codex_doc_for_health(
        project, "doc-a", body="The mission step framing is deprecated."
    )
    glossary_issues = _check_glossary(project)
    assert [
        i for i in glossary_issues if i.check == "glossary_deprecated_term"
    ] == []


# ===========================================================================
# US-007 Unit — `lore.health` source surface no longer mentions family 3
# ===========================================================================


def test_health_module_source_no_family_three_symbols():
    """US-006/US-007 unit — FR-20 deletion blast radius.

    `lore.health` module source contains no references to the removed
    family-3 helpers, the removed glossary import, or the removed check
    name string literal.
    """
    import lore.health

    src = inspect.getsource(lore.health)
    assert "find_deprecated_terms" not in src
    assert "_glossary_deprecated_term_issues" not in src
    assert "_read_codex_bodies" not in src
    assert '"glossary_deprecated_term"' not in src


def test_lore_health_family_three_symbols_gone():
    """US-007 unit — FR-20.

    The private family-3 helpers are no longer attributes of `lore.health`.
    """
    import lore.health

    assert hasattr(lore.health, "_glossary_deprecated_term_issues") is False
    assert hasattr(lore.health, "_read_codex_bodies") is False
