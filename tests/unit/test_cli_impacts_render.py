"""Unit tests for `lore.cli._render_impacts_json` + `_render_impacts_default`.

G3 Red phase — pins the renderers' hoist UP to the CLI module per the
`transient-public-api-facade-plan` (chunk G3). The hoist follows
`standards-separation-of-concerns`: presentation (text + JSON shaping of
`ImpactsResult`) belongs in `lore.cli`, not the operational `lore.impacts`
module.

Acceptance covered here:

* The two renderer names exist as attributes of `lore.cli` (the cli module
  hosts the bodies after the hoist).
* The bodies produce byte-identical output for representative inputs —
  goldens captured from the pre-hoist implementation that currently lives
  in `lore.impacts`. After Green, the CLI-hosted versions MUST emit the
  exact same strings (envelope-rule).
* Negative assertions: `_render_impacts_json` and `_render_impacts_default`
  are no longer attributes of `lore.impacts` once the hoist lands. These
  assertions fail today because the bodies still live in `lore.impacts`.

VERIFY (Review-Ledger FLAG #6, mirrored from the glossary side): the
renderer hoist is presentation-only. The future `read_documents_with_glossary`
op fn (chunk G11) returns RAW items, not pre-rendered text. The renderers
must stay outside the op-fn surface for that reason — hosting them in the
CLI module is the canonical home.
"""

from __future__ import annotations

import json


import lore.cli as cli_mod
import lore.impacts as impacts_mod
from lore.impacts import CodeBinding, CodexBinding, ImpactsResult


# ---------------------------------------------------------------------------
# Surface assertions — renderers reachable on lore.cli (post-hoist target)
# ---------------------------------------------------------------------------


def test_render_impacts_json_reachable_on_cli_module():
    """`_render_impacts_json` must be an attribute of `lore.cli` after G3."""
    assert hasattr(cli_mod, "_render_impacts_json"), (
        "G3 hoist: `_render_impacts_json` body must live on `lore.cli`."
    )
    assert callable(cli_mod._render_impacts_json)


def test_render_impacts_default_reachable_on_cli_module():
    """`_render_impacts_default` must be an attribute of `lore.cli` after G3."""
    assert hasattr(cli_mod, "_render_impacts_default"), (
        "G3 hoist: `_render_impacts_default` body must live on `lore.cli`."
    )
    assert callable(cli_mod._render_impacts_default)


# ---------------------------------------------------------------------------
# Negative surface assertions — operational module must NOT expose renderers
# ---------------------------------------------------------------------------


def test_render_impacts_json_removed_from_impacts_module():
    """`lore.impacts._render_impacts_json` removed by G3 hoist.

    Presentation does not belong in the operational module
    (`standards-separation-of-concerns`).
    """
    assert hasattr(impacts_mod, "_render_impacts_json") is False, (
        "G3 hoist: `_render_impacts_json` must be REMOVED from `lore.impacts`."
    )


def test_render_impacts_default_removed_from_impacts_module():
    """`lore.impacts._render_impacts_default` removed by G3 hoist."""
    assert hasattr(impacts_mod, "_render_impacts_default") is False, (
        "G3 hoist: `_render_impacts_default` must be REMOVED from `lore.impacts`."
    )


# ---------------------------------------------------------------------------
# Golden output — codex-seed branch
# ---------------------------------------------------------------------------
# Goldens captured from the pre-hoist `lore.impacts` bodies.  The hoisted
# CLI versions MUST emit byte-identical strings for the same inputs.


def test_codex_seed_default_renders_one_path_per_line():
    """Codex seed text mode: bare paths, declaration order, trailing \\n each."""
    result = ImpactsResult(
        kind="codex",
        codex_items=(
            CodexBinding(path="src/lore/cli.py", kind="exact"),
            CodexBinding(path="src/lore/**/*.py", kind="glob"),
        ),
    )
    out = cli_mod._render_impacts_default(result)
    assert out == "src/lore/cli.py\nsrc/lore/**/*.py\n"


def test_codex_seed_default_empty_returns_empty_string():
    """Codex seed text mode with no bindings emits the empty string (FR-14)."""
    result = ImpactsResult(kind="codex")
    assert cli_mod._render_impacts_default(result) == ""


def test_codex_seed_json_envelope_shape():
    """Codex seed JSON mode emits `{"impacts": [{"path":..., "kind":...}]}` order-preserving."""
    result = ImpactsResult(
        kind="codex",
        codex_items=(
            CodexBinding(path="src/lore/cli.py", kind="exact"),
            CodexBinding(path="src/lore/**/*.py", kind="glob"),
        ),
    )
    out = cli_mod._render_impacts_json(result)
    # Byte-identical golden (key order: path then kind, mirroring pre-hoist body).
    assert out == (
        '{"impacts": [{"path": "src/lore/cli.py", "kind": "exact"},'
        ' {"path": "src/lore/**/*.py", "kind": "glob"}]}'
    )
    # Also assert parseable as JSON to make any future key-order tweak visible.
    assert json.loads(out) == {
        "impacts": [
            {"path": "src/lore/cli.py", "kind": "exact"},
            {"path": "src/lore/**/*.py", "kind": "glob"},
        ]
    }


def test_codex_seed_json_envelope_empty():
    """Codex seed JSON mode with no bindings emits the empty-list envelope."""
    result = ImpactsResult(kind="codex")
    assert cli_mod._render_impacts_json(result) == '{"impacts": []}'


# ---------------------------------------------------------------------------
# Golden output — code-seed branch
# ---------------------------------------------------------------------------


def test_code_seed_default_exact_is_bare_id():
    """Code seed text mode: exact match emits bare `id\\n`."""
    result = ImpactsResult(
        kind="code",
        code_items=(CodeBinding(id="entry-a", match="exact"),),
    )
    assert cli_mod._render_impacts_default(result) == "entry-a\n"


def test_code_seed_default_glob_annotated_with_pattern():
    """Code seed text mode: glob match emits `id  (glob: pattern)\\n` (two spaces)."""
    result = ImpactsResult(
        kind="code",
        code_items=(
            CodeBinding(id="entry-b", match="glob", pattern="src/**/*.py"),
        ),
    )
    assert cli_mod._render_impacts_default(result) == "entry-b  (glob: src/**/*.py)\n"


def test_code_seed_default_mixed_exact_then_glob():
    """Code seed text mode: mixed bindings keep declaration order across exact + glob."""
    result = ImpactsResult(
        kind="code",
        code_items=(
            CodeBinding(id="entry-a", match="exact"),
            CodeBinding(id="entry-b", match="glob", pattern="src/**/*.py"),
        ),
    )
    assert (
        cli_mod._render_impacts_default(result)
        == "entry-a\nentry-b  (glob: src/**/*.py)\n"
    )


def test_code_seed_default_empty_returns_empty_string():
    """Code seed text mode with no bindings emits the empty string."""
    result = ImpactsResult(kind="code")
    assert cli_mod._render_impacts_default(result) == ""


def test_code_seed_json_exact_omits_pattern_key():
    """Code seed JSON mode: exact rows MUST NOT carry a `pattern` key."""
    result = ImpactsResult(
        kind="code",
        code_items=(CodeBinding(id="entry-a", match="exact"),),
    )
    out = cli_mod._render_impacts_json(result)
    assert out == '{"impacts": [{"id": "entry-a", "match": "exact"}]}'
    parsed = json.loads(out)
    assert "pattern" not in parsed["impacts"][0]


def test_code_seed_json_glob_includes_pattern_key():
    """Code seed JSON mode: glob rows include the matched pattern verbatim."""
    result = ImpactsResult(
        kind="code",
        code_items=(
            CodeBinding(id="entry-b", match="glob", pattern="src/**/*.py"),
        ),
    )
    out = cli_mod._render_impacts_json(result)
    assert out == (
        '{"impacts": [{"id": "entry-b", "match": "glob", "pattern": "src/**/*.py"}]}'
    )


def test_code_seed_json_envelope_empty():
    """Code seed JSON mode with no bindings emits the empty-list envelope."""
    result = ImpactsResult(kind="code")
    assert cli_mod._render_impacts_json(result) == '{"impacts": []}'
