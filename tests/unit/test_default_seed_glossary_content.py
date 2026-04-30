"""Unit tests over `src/lore/defaults/` for the glossary feature (US-007).

Spec: glossary-us-007 (lore codex show glossary-us-007)
Workflow: conceptual-workflows-glossary

Per ADR-006, all assertions are substring/structural — never full-content
equality.  Reads the seed sources via ``importlib.resources`` so the tests
exercise the package surface that the wheel ships.

These tests must FAIL until US-007 Green updates the seed sources
(``LORE-AGENT.md``, new ``CODEX.md``, ``explore-codex/SKILL.md``,
``start-quest/SKILL.md``, ``feature-implementation/scout.md``).
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path

import pytest


def _read_default(*parts: str) -> str:
    """Read a seed source file from ``src/lore/defaults/`` via importlib."""
    return importlib.resources.files("lore.defaults").joinpath(*parts).read_text()


# ---------------------------------------------------------------------------
# LORE-AGENT.md (Scenario 1 — orientation surface mentions glossary)
# ---------------------------------------------------------------------------


def test_default_lore_agent_md_mentions_lore_glossary():
    """conceptual-workflows-glossary — Unit row 1 (Scenario 1)."""
    text = _read_default("docs", "LORE-AGENT.md").lower()
    assert "lore glossary" in text, (
        "LORE-AGENT.md must mention the `lore glossary` CLI surface"
    )


def test_default_lore_agent_md_describes_auto_surface():
    """conceptual-workflows-glossary — Unit row 2 (Scenario 1)."""
    text = _read_default("docs", "LORE-AGENT.md").lower()
    assert (
        ("auto-attach" in text)
        or ("auto-surface" in text)
        or ("appends matched glossary" in text)
    ), (
        "LORE-AGENT.md must describe `lore codex show` auto-attaching glossary entries"
    )


# ---------------------------------------------------------------------------
# CODEX.md (Scenario 2 — Glossary subsection explains rule)
# ---------------------------------------------------------------------------


def test_default_codex_md_file_exists_in_defaults_docs():
    """conceptual-workflows-glossary — Scenario 2 prerequisite (CREATE)."""
    root = importlib.resources.files("lore.defaults")
    target = root.joinpath("docs", "CODEX.md")
    assert target.is_file(), (
        "src/lore/defaults/docs/CODEX.md must exist as a seed source "
        "(US-007 creates this file; the existing copier handles distribution)."
    )


def test_default_codex_md_has_glossary_heading():
    """conceptual-workflows-glossary — Unit row 3 (Scenario 2)."""
    text = _read_default("docs", "CODEX.md")
    headings = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("#")]
    assert any(h in ("## Glossary", "### Glossary") for h in headings), (
        f"CODEX.md must contain a `## Glossary` or `### Glossary` heading; "
        f"got headings: {headings}"
    )


def test_default_codex_md_glossary_section_explains_rule():
    """conceptual-workflows-glossary — Unit row 4 (Scenario 2 body)."""
    text = _read_default("docs", "CODEX.md").lower()
    assert "glossary" in text
    assert "entity doc" in text, (
        "CODEX.md Glossary section must explain when an item belongs in the glossary "
        "vs in its own entity doc — assert via the substring `entity doc`."
    )


# ---------------------------------------------------------------------------
# explore-codex skill (Scenario 3 — command table lists glossary commands)
# ---------------------------------------------------------------------------


def test_default_explore_codex_skill_lists_glossary_commands():
    """conceptual-workflows-glossary — Unit row 5 (Scenario 3)."""
    text = _read_default("skills", "explore-codex", "SKILL.md")
    assert "lore glossary list" in text
    assert "lore glossary search" in text
    assert "lore glossary show" in text


# ---------------------------------------------------------------------------
# start-quest skill (Scenario 4 — alignment on vocabulary)
# ---------------------------------------------------------------------------


def test_default_start_quest_skill_mentions_glossary_alignment():
    """conceptual-workflows-glossary — Unit row 6 (Scenario 4)."""
    text = _read_default("skills", "start-quest", "SKILL.md")
    assert "lore glossary" in text, (
        "start-quest/SKILL.md must reference `lore glossary` as a vocabulary "
        "alignment step before drafting missions."
    )
    lower = text.lower()
    assert (
        ("vocabulary" in lower)
        or ("align" in lower)
        or ("before drafting" in lower)
    ), (
        "start-quest/SKILL.md must direct the agent to align on vocabulary "
        "before drafting missions."
    )


# ---------------------------------------------------------------------------
# scout knight (Scenario 5 — glossary as primary input)
# ---------------------------------------------------------------------------


def test_default_scout_knight_lists_glossary_input():
    """conceptual-workflows-glossary — Unit row 7 (Scenario 5)."""
    text = _read_default("knights", "feature-implementation", "scout.md")
    assert "lore glossary list" in text, (
        "scout.md must reference `lore glossary list` as a primary input"
    )


def test_default_scout_knight_inputs_section_explicitly_lists_glossary_input():
    """conceptual-workflows-glossary — Scenario 5 (Inputs section invariant).

    Beyond the bare `lore glossary list` substring, the scout knight must
    name the glossary as a *primary* input alongside the PRD/codex.  The
    spec wording is intentionally flexible — assert that one of the
    canonical Inputs phrasings appears in the file.
    """
    text = _read_default("knights", "feature-implementation", "scout.md").lower()
    # Either an explicit "Inputs" section header OR a phrasing that pairs
    # the glossary with the PRD/codex as a primary input.
    has_inputs_heading = "## inputs" in text or "### inputs" in text
    has_primary_input_pairing = (
        ("primary input" in text and "glossary" in text)
        or ("glossary" in text and "prd" in text and "codex" in text and "input" in text)
    )
    assert has_inputs_heading or has_primary_input_pairing, (
        "scout.md must surface the glossary as a primary input — either via "
        "an explicit Inputs section or a sentence pairing it with PRD/codex."
    )
