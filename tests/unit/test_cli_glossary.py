"""Unit tests for the lore glossary CLI handlers and group registration.

Spec: glossary-us-002 (lore codex show glossary-us-002)
Workflow: conceptual-workflows-glossary
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner


# ---------------------------------------------------------------------------
# Group registration
# ---------------------------------------------------------------------------


def test_glossary_group_invoke_without_command_calls_list():
    # conceptual-workflows-glossary — group registration (Unit row 1)
    from lore.cli import glossary as group

    assert group.invoke_without_command is True


def test_cli_command_order_glossary_between_codex_and_artifact():
    # conceptual-workflows-glossary — registration order (Unit row 11, Pre-Arch Note 4)
    from lore.cli import main

    cmds = list(main.commands)
    assert "codex" in cmds
    assert "glossary" in cmds
    assert "artifact" in cmds
    assert cmds.index("codex") < cmds.index("glossary") < cmds.index("artifact")


# ---------------------------------------------------------------------------
# Text formatter for `glossary list`
# ---------------------------------------------------------------------------


def test_glossary_list_text_em_dash_for_empty_aliases():
    # conceptual-workflows-glossary — formatter (Unit row 2)
    from lore.cli import render_glossary_list_text
    from lore.models import GlossaryItem

    items = [GlossaryItem(keyword="Codex", definition="x")]
    out = render_glossary_list_text(items)
    assert "—" in out  # em-dash sentinel for empty aliases


def test_glossary_list_text_truncates_at_80_chars():
    # conceptual-workflows-glossary — formatter (Unit row 2) — truncation w/ ellipsis
    from lore.cli import render_glossary_list_text
    from lore.models import GlossaryItem

    items = [GlossaryItem(keyword="K", definition="x" * 200)]
    out = render_glossary_list_text(items)
    assert "…" in out


def test_glossary_list_text_columns_present():
    # conceptual-workflows-glossary — column headers (Unit row 2)
    from lore.cli import render_glossary_list_text
    from lore.models import GlossaryItem

    items = [GlossaryItem(keyword="Codex", definition="d")]
    out = render_glossary_list_text(items)
    assert "KEYWORD" in out
    assert "ALIASES" in out
    assert "DEFINITION" in out


def test_glossary_list_text_alphabetised_by_casefold():
    # conceptual-workflows-glossary — alphabetical sort by casefolded keyword
    from lore.cli import render_glossary_list_text
    from lore.models import GlossaryItem

    items = [
        GlossaryItem(keyword="quest", definition="b"),
        GlossaryItem(keyword="Constable", definition="a"),
    ]
    out = render_glossary_list_text(items)
    assert out.index("Constable") < out.index("quest")


# ---------------------------------------------------------------------------
# JSON formatter for `glossary list`
# ---------------------------------------------------------------------------


def test_glossary_list_json_arrays_present_when_empty():
    # conceptual-workflows-glossary — formatter / json-output (Unit row 3)
    from lore.cli import render_glossary_list_json
    from lore.models import GlossaryItem

    items = [GlossaryItem(keyword="K", definition="d")]
    payload = render_glossary_list_json(items)
    assert "glossary" in payload
    assert payload["glossary"][0]["aliases"] == []
    assert payload["glossary"][0]["do_not_use"] == []


def test_glossary_list_json_envelope_has_all_four_keys():
    # conceptual-workflows-glossary — every entry has keyword/definition/aliases/do_not_use
    from lore.cli import render_glossary_list_json
    from lore.models import GlossaryItem

    items = [
        GlossaryItem(
            keyword="K",
            definition="d",
            aliases=("a",),
            do_not_use=("b",),
        )
    ]
    payload = render_glossary_list_json(items)
    entry = payload["glossary"][0]
    assert set(entry.keys()) >= {"keyword", "definition", "aliases", "do_not_use"}
    assert entry["aliases"] == ["a"]
    assert entry["do_not_use"] == ["b"]


# ---------------------------------------------------------------------------
# Search formatter
# ---------------------------------------------------------------------------


def test_glossary_search_lowercases_query_and_alphabetises(tmp_path, monkeypatch):
    # conceptual-workflows-glossary — search formatter (Unit row 4)
    from lore.cli import main

    fixture = (
        tmp_path / ".lore" / "codex" / "glossary.yaml"
    )
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(
        "items:\n"
        "  - keyword: Quest\n"
        "    definition: Mission grouping.\n"
        "  - keyword: Constable\n"
        "    definition: Mission orchestrator chore.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    res = CliRunner().invoke(main, ["glossary", "search", "MISSION"])
    # Alphabetised across both matches
    assert res.exit_code == 0
    assert res.output.index("Constable") < res.output.index("Quest")


def test_glossary_search_no_match_emits_text_message(tmp_path, monkeypatch):
    # conceptual-workflows-glossary — no-match path text (Unit row 5)
    from lore.cli import main

    fixture = tmp_path / ".lore" / "codex" / "glossary.yaml"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(
        "items:\n  - keyword: K\n    definition: D\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    res = CliRunner().invoke(main, ["glossary", "search", "zzz"])
    assert res.exit_code == 0
    assert res.output == 'No glossary entries matching "zzz".\n'


def test_glossary_search_no_match_emits_empty_json(tmp_path, monkeypatch):
    # conceptual-workflows-glossary — no-match path JSON (Unit row 5)
    from lore.cli import main

    fixture = tmp_path / ".lore" / "codex" / "glossary.yaml"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(
        "items:\n  - keyword: K\n    definition: D\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    res = CliRunner().invoke(main, ["--json", "glossary", "search", "zzz"])
    assert res.exit_code == 0
    assert res.output.strip() == '{"glossary": []}'


# ---------------------------------------------------------------------------
# Show formatter
# ---------------------------------------------------------------------------


def test_glossary_show_text_uses_em_dash_for_empty(tmp_path, monkeypatch):
    # conceptual-workflows-glossary — show formatter (Unit row 10)
    from lore.cli import main

    fixture = tmp_path / ".lore" / "codex" / "glossary.yaml"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(
        "items:\n  - keyword: Codex\n    definition: D\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    res = CliRunner().invoke(main, ["glossary", "show", "Codex"])
    assert res.exit_code == 0
    assert "Aliases: —" in res.output
    assert "Do not use: —" in res.output


def test_glossary_show_alphabetises_regardless_of_input_order(tmp_path, monkeypatch):
    # conceptual-workflows-glossary — show ordering (Unit row 6)
    from lore.cli import main

    fixture = tmp_path / ".lore" / "codex" / "glossary.yaml"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(
        "items:\n"
        "  - keyword: Quest\n"
        "    definition: Q.\n"
        "  - keyword: Constable\n"
        "    definition: C.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    res = CliRunner().invoke(main, ["glossary", "show", "Quest", "Constable"])
    assert res.exit_code == 0
    assert res.output.index("=== Constable ===") < res.output.index("=== Quest ===")


def test_glossary_show_keyword_resolution_case_insensitive(tmp_path, monkeypatch):
    # conceptual-workflows-glossary — show case-insensitive (Unit row 7)
    from lore.cli import main

    fixture = tmp_path / ".lore" / "codex" / "glossary.yaml"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(
        "items:\n  - keyword: Constable\n    definition: D.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    res = CliRunner().invoke(main, ["glossary", "show", "constable"])
    assert res.exit_code == 0
    # display preserves source casing
    assert "=== Constable ===" in res.output


def test_glossary_show_alias_argument_is_not_found(tmp_path, monkeypatch):
    # conceptual-workflows-glossary — alias-not-lookup (Unit row 8)
    from lore.cli import main

    fixture = tmp_path / ".lore" / "codex" / "glossary.yaml"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(
        "items:\n"
        "  - keyword: Constable\n"
        "    definition: D.\n"
        "    aliases: [chore mission]\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    res = CliRunner().invoke(main, ["glossary", "show", "chore mission"])
    assert res.exit_code == 1


def test_glossary_show_fail_fast_no_partial_stdout(tmp_path, monkeypatch):
    # conceptual-workflows-glossary — fail-fast (Unit row 9)
    from lore.cli import main

    fixture = tmp_path / ".lore" / "codex" / "glossary.yaml"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(
        "items:\n"
        "  - keyword: Constable\n"
        "    definition: D.\n"
        "  - keyword: Quest\n"
        "    definition: Q.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    res = CliRunner().invoke(
        main, ["glossary", "show", "Constable", "NoSuch", "Quest"]
    )
    assert res.exit_code == 1
    assert res.stdout == ""
