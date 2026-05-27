"""Unit tests for `lore.cli._render_glossary_block`.

G3 Red phase — pins the renderer hoist UP to the CLI module per the
`transient-public-api-facade-plan` (chunk G3). The hoist follows
`standards-separation-of-concerns`: presentation belongs in `lore.cli`,
not the operational `lore.glossary` module.

VERIFY (Review-Ledger FLAG #6): `_render_glossary_block` is being hoisted
because the future G11 op fn `read_documents_with_glossary` will return
RAW glossary items (`list[GlossaryItem]`), not pre-rendered text. The
renderer therefore belongs on the CLI side — every Python caller of
`read_documents_with_glossary` gets raw items and renders (or not) as it
sees fit; only `lore codex show` re-runs the markdown block format.

Acceptance covered here:

* `_render_glossary_block` is reachable on `lore.cli` after Green.
* Bodies emit byte-identical output for representative inputs — goldens
  captured from the pre-hoist body that currently lives in `lore.glossary`.
* Negative assertion: `_render_glossary_block` is REMOVED from
  `lore.glossary` once the hoist lands.
"""

from __future__ import annotations

import lore.cli as cli_mod
import lore.glossary as glossary_mod
from lore.models import GlossaryItem


# ---------------------------------------------------------------------------
# Surface assertions
# ---------------------------------------------------------------------------


def test_render_glossary_block_reachable_on_cli_module():
    """`_render_glossary_block` must be an attribute of `lore.cli` after G3."""
    assert hasattr(cli_mod, "_render_glossary_block"), (
        "G3 hoist: `_render_glossary_block` body must live on `lore.cli`."
    )
    assert callable(cli_mod._render_glossary_block)


# ---------------------------------------------------------------------------
# Negative surface assertion — operational module must NOT expose renderer
# ---------------------------------------------------------------------------


def test_render_glossary_block_removed_from_glossary_module():
    """`lore.glossary._render_glossary_block` removed by G3 hoist.

    Presentation does not belong in the operational module
    (`standards-separation-of-concerns`).  FLAG #6 verified: the future
    `read_documents_with_glossary` op fn returns RAW items, so the
    rendering surface lives CLI-side.
    """
    assert hasattr(glossary_mod, "_render_glossary_block") is False, (
        "G3 hoist: `_render_glossary_block` must be REMOVED from `lore.glossary`."
    )


# ---------------------------------------------------------------------------
# Golden output — empty / single / multi-item cases
# ---------------------------------------------------------------------------
# Goldens captured from the pre-hoist `lore.glossary` body.  The hoisted
# CLI version MUST emit byte-identical strings for the same inputs.


def test_empty_glossary_renders_empty_string():
    """Empty list → empty string (no `## Glossary` header)."""
    assert cli_mod._render_glossary_block([]) == ""


def test_two_items_sorted_by_casefolded_keyword():
    """Items render sorted by casefolded keyword regardless of input order."""
    items = [
        GlossaryItem(
            keyword="Quest",
            definition="A live grouping of Missions representing one body of work.",
        ),
        GlossaryItem(
            keyword="Constable",
            definition="Mission type for orchestrator-handled chores.",
        ),
    ]
    out = cli_mod._render_glossary_block(items)
    # Byte-identical golden — keep verbatim. Two blank lines: header padding
    # and inter-paragraph separator.
    assert out == (
        "\n## Glossary\n\n"
        "**Constable** — Mission type for orchestrator-handled chores.\n\n"
        "**Quest** — A live grouping of Missions representing one body of work.\n"
    )


def test_multiline_definition_whitespace_collapsed():
    """Multiline / multi-space definitions collapse to single spaces."""
    items = [
        GlossaryItem(
            keyword="Knight",
            definition="An agent\n persona.   Reusable.",
        ),
    ]
    out = cli_mod._render_glossary_block(items)
    assert out == "\n## Glossary\n\n**Knight** — An agent persona. Reusable.\n"


def test_single_item_uses_em_dash_separator():
    """Single item → `## Glossary` header + `**keyword** — definition\\n`."""
    items = [
        GlossaryItem(
            keyword="Mission",
            definition="A single executable task assigned to an agent.",
        ),
    ]
    out = cli_mod._render_glossary_block(items)
    assert out == (
        "\n## Glossary\n\n"
        "**Mission** — A single executable task assigned to an agent.\n"
    )
