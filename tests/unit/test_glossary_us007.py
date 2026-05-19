"""Unit tests for US-007 — `lore.glossary.find_deprecated_terms` removal.

Spec: lore codex show health-bindings-glossary-us-007
PRD: health-bindings-glossary-prd (FR-19, FR-23)

The function `find_deprecated_terms` is a non-public Python API break:
it has been removed from `src/lore/glossary.py` while the shared tokeniser
(`_normalise_tokens`, `_build_lookup`, `_iter_runs`, `_scan_runs`,
`match_glossary`) stays — auto-surface still depends on it (PRD FR-23).

Notes:
  * This file intentionally does NOT do a top-level
    `from lore.glossary import find_deprecated_terms`. Doing so would
    break test collection post-removal (Tech Spec §
    "`find_deprecated_terms` import in tests"). The shape is:
    import the module, then assert the symbol is gone / not importable.
  * Auto-surface dependency assertions (US-007 Scenario 2) live as
    importability + smoke calls on the shared tokeniser — not as
    `lore codex show` regression tests, which already exist elsewhere
    and stay green throughout.
"""

from __future__ import annotations

import inspect
import pathlib

import pytest


# ===========================================================================
# US-007 — Symbol disappears from lore.glossary
# ===========================================================================


def test_lore_glossary_hasattr_find_deprecated_terms_false():
    """US-007 unit — FR-19.

    After import, `lore.glossary` has no `find_deprecated_terms` attribute.
    """
    import lore.glossary

    assert hasattr(lore.glossary, "find_deprecated_terms") is False


def test_find_deprecated_terms_not_importable():
    """US-007 E2E Scenario 1 — `from lore.glossary import find_deprecated_terms`
    raises ImportError.
    """
    import lore.glossary  # noqa: F401

    with pytest.raises(ImportError):
        from lore.glossary import find_deprecated_terms  # noqa: F401


def test_lore_glossary_source_no_find_deprecated_terms():
    """US-007 E2E Scenario 4 — source-level deletion.

    `inspect.getsource(lore.glossary)` does not contain the symbol name
    anywhere — function definition gone, US-005 docstring header gone.
    """
    import lore.glossary

    src = inspect.getsource(lore.glossary)
    assert "find_deprecated_terms" not in src


# ===========================================================================
# US-007 — Shared tokeniser stays (PRD FR-23 regression guard)
# ===========================================================================


def test_shared_tokeniser_symbols_still_importable():
    """US-007 unit — FR-23.

    All five shared tokeniser symbols are still importable from
    `lore.glossary` and produce non-empty smoke results.
    """
    from lore.glossary import (
        _build_lookup,
        _iter_runs,
        _normalise_tokens,
        _scan_runs,
        match_glossary,
    )

    # Smoke — exact behaviour pinned by the existing tokeniser tests.
    assert _normalise_tokens("Hello world") != []
    # _build_lookup signature accepts an iterable of items. Use
    # GlossaryItem to match the production call site.
    from lore.models import GlossaryItem

    lookup = _build_lookup(
        [GlossaryItem(keyword="Foo", definition="d")], source="canonical"
    )
    assert lookup
    # _iter_runs / _scan_runs are used internally; importability is the guard.
    assert _iter_runs is not None
    assert _scan_runs is not None
    # match_glossary still surfaces glossary terms in body prose.
    items = [GlossaryItem(keyword="Foo", definition="d")]
    hits = match_glossary(["foo bar"], items=items)
    assert hits

    # Forward-looking pair — find_deprecated_terms is gone.
    import lore.glossary

    assert not hasattr(lore.glossary, "find_deprecated_terms")


# ===========================================================================
# US-007 — Test inventory meta-check
# ===========================================================================


def test_test_glossary_no_module_level_find_deprecated_terms_import():
    """US-007 unit (meta) — Tech Spec § "find_deprecated_terms import in tests".

    `tests/unit/test_glossary.py` must NOT contain a module-level
    `from lore.glossary import find_deprecated_terms`, or pytest
    collection aborts the entire file with ImportError once the symbol
    is gone.
    """
    test_file = pathlib.Path(__file__).resolve().parent / "test_glossary.py"
    src = test_file.read_text(encoding="utf-8")
    assert "from lore.glossary import find_deprecated_terms" not in src


def test_no_remaining_references_in_tests():
    """US-007 E2E Scenario 3 — orphan-reference sweep.

    `tests/` contains zero references to `find_deprecated_terms` or
    `glossary_deprecated_term` after the feature lands. Implemented as
    a grep-style assertion over every `.py` file under `tests/`.

    NOTE: this Red test will obviously fail today because the existing
    Green codebase still references both names from the pre-feature
    suite. It is restored to green by Green when those references are
    deleted.
    """
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    tests_dir = repo_root / "tests"
    # Skip this Red file itself — it legitimately references both
    # strings as quoted needles, and once Green lands those references
    # disappear from every OTHER test file. We still grep this file,
    # but exclude the literal-needle quotations from the count.
    self_path = pathlib.Path(__file__).resolve()
    health_red_path = self_path.with_name("test_health_us006_us007.py")
    e2e_red_path = repo_root / "tests" / "e2e" / "test_health_glossary_us006_us007.py"
    skip = {self_path, health_red_path, e2e_red_path}
    for needle in ("find_deprecated_terms", "glossary_deprecated_term"):
        matches: list[pathlib.Path] = []
        for path in tests_dir.rglob("*.py"):
            if path.resolve() in skip:
                continue
            if needle in path.read_text(encoding="utf-8"):
                matches.append(path)
        assert matches == [], f"orphan references to {needle}: {matches}"
