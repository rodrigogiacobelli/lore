"""E2E parity tests pinning `lore impacts` byte-identical output across G3 hoist.

G3 (`transient-public-api-facade-plan`) hoists `_render_impacts_json` and
`_render_impacts_default` from `lore.impacts` UP into `lore.cli`. The CLI
acceptance criterion is byte-identical text + JSON for `lore impacts`
before and after the hoist.

These tests target representative `lore impacts` invocations with EXACT
expected stdout bytes so any incidental drift during the hoist (extra
newline, key reorder, missing trailing newline) trips them immediately.

The bytes encoded here match the pre-hoist `lore.impacts` body output —
the same strings the unit-level golden tests in
`tests/unit/test_cli_impacts_render.py` assert against the CLI-hosted
renderers.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

import lore.cli as cli_mod
import lore.impacts as impacts_mod
from lore.cli import main


# ---------------------------------------------------------------------------
# Hoist-surface guards — every parity test gates on the hoist landing first,
# so the file fails as a unit today (Red phase). Once Green flips the surface,
# the byte goldens below become the parity contract going forward.
# ---------------------------------------------------------------------------


def _assert_hoist_landed():
    """Skip-style gate: fails loudly while the hoist is incomplete."""
    assert hasattr(cli_mod, "_render_impacts_json"), (
        "G3 hoist incomplete: `_render_impacts_json` must live on `lore.cli`."
    )
    assert hasattr(cli_mod, "_render_impacts_default"), (
        "G3 hoist incomplete: `_render_impacts_default` must live on `lore.cli`."
    )
    assert not hasattr(impacts_mod, "_render_impacts_json"), (
        "G3 hoist incomplete: `_render_impacts_json` still on `lore.impacts`."
    )
    assert not hasattr(impacts_mod, "_render_impacts_default"), (
        "G3 hoist incomplete: `_render_impacts_default` still on `lore.impacts`."
    )


def _write_codex_entry(
    project_dir: Path,
    *,
    entry_id: str,
    binds: list | None = None,
) -> None:
    """Write a minimal codex entry under `.lore/codex/<entry_id>.md`."""
    fm = {
        "id": entry_id,
        "title": entry_id.replace("-", " ").title(),
        "summary": f"Codex entry {entry_id}.",
    }
    if binds is not None:
        fm["binds"] = binds
    front = yaml.safe_dump(fm, sort_keys=False, default_flow_style=False)
    path = project_dir / ".lore" / "codex" / f"{entry_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{front}---\nBody for {entry_id}.\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Codex-seed text mode — byte-identical golden
# ---------------------------------------------------------------------------


def test_lore_impacts_codex_seed_text_byte_identical(project_dir, runner):
    """`lore impacts <codex-id>` text output pinned byte-for-byte."""
    _assert_hoist_landed()
    _write_codex_entry(
        project_dir,
        entry_id="dec-006-id-references",
        binds=[
            "src/lore/cli.py",
            "src/lore/**/*.py",
            "tests/unit/test_models.py",
        ],
    )
    result = runner.invoke(main, ["impacts", "dec-006-id-references"])
    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    assert result.stdout == (
        "src/lore/cli.py\nsrc/lore/**/*.py\ntests/unit/test_models.py\n"
    )


# ---------------------------------------------------------------------------
# Codex-seed JSON mode — byte-identical golden
# ---------------------------------------------------------------------------


def test_lore_impacts_codex_seed_json_byte_identical(project_dir, runner):
    """`lore impacts --json <codex-id>` JSON output pinned byte-for-byte.

    Asserts BOTH the parsed envelope (semantic) AND the raw bytes (incl.
    key order), since the hoist must not perturb `json.dumps` key order.
    """
    _assert_hoist_landed()
    _write_codex_entry(
        project_dir,
        entry_id="entry-mixed",
        binds=["src/lore/cli.py", "src/lore/**/*.py"],
    )
    result = runner.invoke(main, ["impacts", "--json", "entry-mixed"])
    assert result.exit_code == 0, result.output
    # Click's stdout adds a trailing newline from `click.echo`; the envelope
    # JSON itself must NOT add one. Strip the single trailing \n that click
    # adds to compare the JSON bytes verbatim.
    assert result.stdout.endswith("\n")
    body = result.stdout[:-1]
    assert body == (
        '{"impacts": [{"path": "src/lore/cli.py", "kind": "exact"},'
        ' {"path": "src/lore/**/*.py", "kind": "glob"}]}'
    )
    assert json.loads(body) == {
        "impacts": [
            {"path": "src/lore/cli.py", "kind": "exact"},
            {"path": "src/lore/**/*.py", "kind": "glob"},
        ]
    }


# ---------------------------------------------------------------------------
# Empty codex seed — text + JSON byte-identical
# ---------------------------------------------------------------------------


def test_lore_impacts_codex_seed_empty_text_byte_identical(project_dir, runner):
    """Empty `binds: []` codex entry → empty stdout, empty stderr (FR-14)."""
    _assert_hoist_landed()
    _write_codex_entry(project_dir, entry_id="empty-entry", binds=[])
    result = runner.invoke(main, ["impacts", "empty-entry"])
    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert result.stderr == ""


def test_lore_impacts_codex_seed_empty_json_byte_identical(project_dir, runner):
    """Empty `binds: []` codex entry → `{"impacts": []}` JSON envelope."""
    _assert_hoist_landed()
    _write_codex_entry(project_dir, entry_id="empty-entry", binds=[])
    result = runner.invoke(main, ["impacts", "--json", "empty-entry"])
    assert result.exit_code == 0, result.output
    assert result.stdout.endswith("\n")
    assert result.stdout[:-1] == '{"impacts": []}'
