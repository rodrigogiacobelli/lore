"""E2E parity tests pinning `lore codex show` glossary block byte-identical.

G3 (`transient-public-api-facade-plan`) hoists `_render_glossary_block`
from `lore.glossary` UP into `lore.cli`. CLI text mode for
`lore codex show` is the only surface that renders the `## Glossary`
block — the JSON envelope returns raw items via `_glossary_entry_dict`,
which is unaffected. These tests pin the EXACT bytes the renderer
emits in text mode through the CLI.

VERIFY (Review-Ledger FLAG #6): the future op fn
`read_documents_with_glossary` (chunk G11) returns RAW items, NOT
pre-rendered text. The renderer therefore belongs CLI-side; this test
file is the bytes-on-the-wire guard ensuring the hoist does not perturb
the rendered `## Glossary` markdown.
"""

from __future__ import annotations

import json
from pathlib import Path

import lore.cli as cli_mod
import lore.glossary as glossary_mod
from lore.cli import main


def _assert_hoist_landed():
    """Skip-style gate: fails loudly while the hoist is incomplete."""
    assert hasattr(cli_mod, "_render_glossary_block"), (
        "G3 hoist incomplete: `_render_glossary_block` must live on `lore.cli`."
    )
    assert not hasattr(glossary_mod, "_render_glossary_block"), (
        "G3 hoist incomplete: `_render_glossary_block` still on `lore.glossary`."
    )


GLOSSARY_FIXTURE = """\
items:
  - keyword: Mission
    definition: The unit of work an agent executes and closes.
  - keyword: Quest
    definition: A live grouping of Missions representing one body of work.
"""


MISSION_DOC_BODY = (
    "A Mission is the unit of work an agent executes and closes.\n"
    "A Mission may belong to a Quest.\n"
)


MISSION_DOC = (
    "---\n"
    "id: conceptual-entities-mission\n"
    "title: Mission\n"
    "summary: Mission entity doc.\n"
    "---\n"
    "\n"
    + MISSION_DOC_BODY
)


def _seed(project_dir: Path) -> None:
    """Write the glossary YAML and a single codex doc that mentions both terms."""
    (project_dir / ".lore" / "codex").mkdir(parents=True, exist_ok=True)
    (project_dir / ".lore" / "codex" / "glossary.yaml").write_text(
        GLOSSARY_FIXTURE, encoding="utf-8"
    )
    (project_dir / ".lore" / "codex" / "conceptual-entities-mission.md").write_text(
        MISSION_DOC, encoding="utf-8"
    )


def test_codex_show_text_mode_glossary_block_byte_identical(project_dir, runner):
    """`lore codex show <id>` (text mode) glossary block pinned byte-for-byte.

    The output is:
        === <id> ===\\n
        <body lines>\\n
        \\n
        \\n
        ## Glossary\\n
        \\n
        **Mission** — …\\n
        \\n
        **Quest** — …\\n
    There are TWO blank lines (3 newlines) between the doc body and
    ``## Glossary``: the doc body itself ends with ``\\n``, ``click.echo``
    appends its own trailing ``\\n``, and the renderer prefix
    ``"\\n## Glossary\\n\\n"`` contributes one more leading ``\\n``.

    The golden bytes here are authorised by board message dated
    2026-05-25T20:29:45Z on mission q-6317/m-2632, which records that
    the original Red-phase golden (1 blank line) was an authoring bug
    and that the verified pre-hoist output has 2 blank lines / 3
    newlines at this seam.
    """
    _assert_hoist_landed()
    _seed(project_dir)
    result = runner.invoke(main, ["codex", "show", "conceptual-entities-mission"])
    assert result.exit_code == 0, result.output
    assert result.stderr == ""

    expected_body = (
        "=== conceptual-entities-mission ===\n"
        + MISSION_DOC_BODY
        + "\n"
        + "\n"
        + "## Glossary\n"
        + "\n"
        + "**Mission** — The unit of work an agent executes and closes.\n"
        + "\n"
        + "**Quest** — A live grouping of Missions representing one body of work.\n"
    )
    assert result.stdout == expected_body


def test_codex_show_json_mode_glossary_block_NOT_rendered(project_dir, runner):
    """`lore codex show --json <id>` returns raw items, never the `## Glossary` block.

    Guards the FLAG #6 invariant: JSON mode bypasses the renderer entirely.
    This test must STILL pass after the hoist (renderer moved but never
    invoked in JSON mode), so it doubles as a regression guard.
    """
    _assert_hoist_landed()
    _seed(project_dir)
    result = runner.invoke(
        main, ["--json", "codex", "show", "conceptual-entities-mission"]
    )
    assert result.exit_code == 0, result.output
    assert "## Glossary" not in result.stdout
    data = json.loads(result.stdout)
    assert "glossary" in data
    keywords = [g["keyword"] for g in data["glossary"]]
    # Raw items in alphabetised order (casefolded).
    assert keywords == ["Mission", "Quest"]
