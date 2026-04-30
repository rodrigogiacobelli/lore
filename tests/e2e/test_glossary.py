"""E2E tests for the glossary file format, Python API, and CLI surfaces.

Spec: glossary-us-001 (lore codex show glossary-us-001) — Python API parity
Spec: glossary-us-002 (lore codex show glossary-us-002) — CLI commands
Workflow: conceptual-workflows-glossary
"""

from __future__ import annotations

import dataclasses
import json

import pytest
from click.testing import CliRunner

from lore.cli import main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


CONSTABLE_QUEST_YAML = """\
items:
  - keyword: Constable
    definition: Mission type for orchestrator-handled chores (commits, housekeeping). Not dispatched to a worker.
    aliases: [constable mission, chore mission]
    do_not_use: [bot mission]
  - keyword: Quest
    definition: A live grouping of Missions representing one body of work.
    do_not_use: [epic, story group]
"""


FIVE_ITEM_FIXTURE = """\
items:
  - keyword: Codex
    definition: The documentation system at .lore/codex/. Markdown files with YAML frontmatter.
  - keyword: Constable
    definition: Mission type for orchestrator-handled chores (commits, housekeeping). Not dispatched to a worker.
    aliases: [constable mission, chore mission]
    do_not_use: [bot mission]
  - keyword: Doctrine
    definition: A reusable, passive workflow template stored as paired YAML and markdown.
  - keyword: Mission
    definition: The unit of work an agent executes and closes.
  - keyword: Quest
    definition: A live grouping of Missions representing one body of work.
    do_not_use: [epic, story group]
"""


def _write_fixture(project_dir, content):
    """Write the canonical glossary YAML to .lore/codex/glossary.yaml."""
    target = project_dir / ".lore" / "codex" / "glossary.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


# ===========================================================================
# US-001 — Python API
# ===========================================================================


def test_python_api_scan_returns_glossary_items(project_dir):
    # conceptual-workflows-glossary — Python-API parity (US-001 Scenario 1, ADR-011)
    from lore.glossary import scan_glossary
    from lore.models import GlossaryItem

    _write_fixture(project_dir, CONSTABLE_QUEST_YAML)
    items = scan_glossary(project_dir)
    assert items[0] == GlossaryItem(
        keyword="Constable",
        definition="Mission type for orchestrator-handled chores (commits, housekeeping). Not dispatched to a worker.",
        aliases=("constable mission", "chore mission"),
        do_not_use=("bot mission",),
    )
    assert items[1] == GlossaryItem(
        keyword="Quest",
        definition="A live grouping of Missions representing one body of work.",
        aliases=(),
        do_not_use=("epic", "story group"),
    )


def test_python_api_scan_missing_file(project_dir):
    # conceptual-workflows-glossary — missing-file silent (US-001 Scenario 2)
    from lore.glossary import scan_glossary

    assert scan_glossary(project_dir) == []


def test_python_api_scan_malformed_raises(project_dir):
    # conceptual-workflows-glossary — fail-loud on Python API (US-001 Scenario 3)
    from lore.glossary import GlossaryError, scan_glossary

    _write_fixture(project_dir, "items: not-a-list")
    with pytest.raises(GlossaryError):
        scan_glossary(project_dir)


def test_python_api_scan_missing_required_field(project_dir):
    # conceptual-workflows-glossary — schema rule reference (US-001 Scenario 4)
    from lore.glossary import GlossaryError, scan_glossary

    _write_fixture(project_dir, "items:\n  - keyword: Mission\n")
    with pytest.raises(GlossaryError, match="required.*definition"):
        scan_glossary(project_dir)


def test_python_api_read_glossary_item_case_insensitive(project_dir):
    # conceptual-workflows-glossary — case-insensitive lookup (US-001 Scenario 5)
    from lore.glossary import read_glossary_item

    _write_fixture(project_dir, CONSTABLE_QUEST_YAML)
    item = read_glossary_item(project_dir, "constable")
    assert item is not None
    assert item.keyword == "Constable"


def test_python_api_read_glossary_item_alias_rejected(project_dir):
    # conceptual-workflows-glossary — alias NOT lookup key (US-001 Scenario 5)
    from lore.glossary import read_glossary_item

    _write_fixture(project_dir, CONSTABLE_QUEST_YAML)
    assert read_glossary_item(project_dir, "constable mission") is None


def test_python_api_read_glossary_item_unknown_returns_none(project_dir):
    # conceptual-workflows-glossary — unknown keyword (US-001 Scenario 5)
    from lore.glossary import read_glossary_item

    _write_fixture(project_dir, CONSTABLE_QUEST_YAML)
    assert read_glossary_item(project_dir, "nonsense") is None


def test_python_api_search_alphabetised_results(project_dir):
    # conceptual-workflows-glossary — search ordering (US-001 Scenario 6)
    from lore.glossary import search_glossary

    _write_fixture(project_dir, CONSTABLE_QUEST_YAML)
    res = search_glossary(project_dir, "MISSION")
    assert [i.keyword for i in res] == ["Constable", "Quest"]


def test_python_api_search_keyword_match(project_dir):
    # conceptual-workflows-glossary — keyword match (US-001 Scenario 6)
    from lore.glossary import search_glossary

    _write_fixture(project_dir, CONSTABLE_QUEST_YAML)
    res = search_glossary(project_dir, "constable")
    assert [i.keyword for i in res] == ["Constable"]


def test_python_api_search_do_not_use_match(project_dir):
    # conceptual-workflows-glossary — do_not_use match (US-001 Scenario 6)
    from lore.glossary import search_glossary

    _write_fixture(project_dir, CONSTABLE_QUEST_YAML)
    res = search_glossary(project_dir, "epic")
    assert [i.keyword for i in res] == ["Quest"]


def test_glossary_item_is_immutable_via_public_api(project_dir):
    # conceptual-workflows-glossary — frozen dataclass (US-001 Scenario 7)
    import lore.models as mod
    from lore.models import GlossaryItem

    assert "GlossaryItem" in mod.__all__
    item = GlossaryItem(keyword="x", definition="y")
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        item.keyword = "z"


# ===========================================================================
# US-002 — CLI scenarios
# ===========================================================================


# ---------------------------------------------------------------------------
# Scenario 1 — `lore glossary` and `lore glossary list` produce identical tables
# ---------------------------------------------------------------------------


def test_lore_glossary_and_list_produce_identical_tables(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 1 (lore glossary aliases list)
    _write_fixture(project_dir, FIVE_ITEM_FIXTURE)
    out_a = runner.invoke(main, ["glossary"])
    out_b = runner.invoke(main, ["glossary", "list"])
    assert out_a.exit_code == 0
    assert out_b.exit_code == 0
    assert out_a.output == out_b.output
    assert "KEYWORD" in out_a.output
    assert "ALIASES" in out_a.output
    assert "DEFINITION" in out_a.output


def test_glossary_list_text_truncates_long_definition(project_dir, runner):
    # conceptual-workflows-glossary — text formatter (Scenario 1, Unit row 2)
    _write_fixture(project_dir, FIVE_ITEM_FIXTURE)
    res = runner.invoke(main, ["glossary", "list"])
    assert res.exit_code == 0
    assert res.output.endswith("\n")
    assert "…" in res.output


def test_glossary_list_text_em_dash_for_empty_aliases(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 1 em-dash sentinel
    _write_fixture(project_dir, FIVE_ITEM_FIXTURE)
    res = runner.invoke(main, ["glossary", "list"])
    assert res.exit_code == 0
    # Codex has no aliases — em-dash expected
    assert "—" in res.output


def test_glossary_list_alphabetised_in_table(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 1 alphabetised order
    _write_fixture(project_dir, FIVE_ITEM_FIXTURE)
    res = runner.invoke(main, ["glossary", "list"])
    assert res.exit_code == 0
    out = res.output
    assert (
        out.index("Codex")
        < out.index("Constable")
        < out.index("Doctrine")
        < out.index("Mission")
        < out.index("Quest")
    )


# ---------------------------------------------------------------------------
# Scenario 2 — JSON envelope on list
# ---------------------------------------------------------------------------


def test_glossary_list_json_envelope(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 2 (JSON envelope shape)
    _write_fixture(project_dir, FIVE_ITEM_FIXTURE)
    res = runner.invoke(main, ["--json", "glossary", "list"])
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert list(payload.keys()) == ["glossary"]
    for entry in payload["glossary"]:
        assert {"keyword", "definition", "aliases", "do_not_use"} <= set(entry.keys())
    # arrays present, empty-not-omitted on the Codex entry
    codex = next(e for e in payload["glossary"] if e["keyword"] == "Codex")
    assert codex["aliases"] == []
    assert codex["do_not_use"] == []


def test_glossary_list_json_exact_envelope_string(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 2 exact string match
    _write_fixture(project_dir, FIVE_ITEM_FIXTURE)
    res = runner.invoke(main, ["--json", "glossary", "list"])
    expected = (
        '{"glossary": [{"keyword": "Codex", "definition": "The documentation system at .lore/codex/. Markdown files with YAML frontmatter.", "aliases": [], "do_not_use": []},'
        ' {"keyword": "Constable", "definition": "Mission type for orchestrator-handled chores (commits, housekeeping). Not dispatched to a worker.", "aliases": ["constable mission", "chore mission"], "do_not_use": ["bot mission"]},'
        ' {"keyword": "Doctrine", "definition": "A reusable, passive workflow template stored as paired YAML and markdown.", "aliases": [], "do_not_use": []},'
        ' {"keyword": "Mission", "definition": "The unit of work an agent executes and closes.", "aliases": [], "do_not_use": []},'
        ' {"keyword": "Quest", "definition": "A live grouping of Missions representing one body of work.", "aliases": [], "do_not_use": ["epic", "story group"]}]}'
    )
    assert res.output.strip() == expected


# ---------------------------------------------------------------------------
# Scenario 3 — search matches
# ---------------------------------------------------------------------------


def test_glossary_search_matches_keyword(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 3 keyword match
    _write_fixture(project_dir, FIVE_ITEM_FIXTURE)
    res = runner.invoke(main, ["glossary", "search", "constable"])
    assert res.exit_code == 0
    assert "Constable" in res.output
    assert "Quest" not in res.output


def test_glossary_search_matches_do_not_use_case_insensitive(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 3 do_not_use match (EPIC)
    _write_fixture(project_dir, FIVE_ITEM_FIXTURE)
    res = runner.invoke(main, ["glossary", "search", "EPIC"])
    assert res.exit_code == 0
    assert "Quest" in res.output
    assert "Constable" not in res.output


def test_glossary_search_json_envelope(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 3 JSON
    _write_fixture(project_dir, FIVE_ITEM_FIXTURE)
    res = runner.invoke(main, ["--json", "glossary", "search", "constable"])
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert [i["keyword"] for i in payload["glossary"]] == ["Constable"]
    expected = (
        '{"glossary": [{"keyword": "Constable", "definition": "Mission type for orchestrator-handled chores (commits, housekeeping). Not dispatched to a worker.", "aliases": ["constable mission", "chore mission"], "do_not_use": ["bot mission"]}]}'
    )
    assert res.output.strip() == expected


# ---------------------------------------------------------------------------
# Scenario 4 — no-match
# ---------------------------------------------------------------------------


def test_glossary_search_no_match_text(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 4 text no-match
    _write_fixture(project_dir, FIVE_ITEM_FIXTURE)
    res = runner.invoke(main, ["glossary", "search", "nonexistent"])
    assert res.exit_code == 0
    assert res.output == 'No glossary entries matching "nonexistent".\n'


def test_glossary_search_no_match_json(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 4 JSON no-match
    _write_fixture(project_dir, FIVE_ITEM_FIXTURE)
    res = runner.invoke(main, ["--json", "glossary", "search", "nonexistent"])
    assert res.exit_code == 0
    assert res.output.strip() == '{"glossary": []}'


# ---------------------------------------------------------------------------
# Scenario 5 — show with multiple keywords, alphabetised
# ---------------------------------------------------------------------------


def test_glossary_show_multi_keyword_alphabetises(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 5 (multi-arg + alphabetisation)
    _write_fixture(project_dir, FIVE_ITEM_FIXTURE)
    res = runner.invoke(main, ["glossary", "show", "Quest", "constable"])
    assert res.exit_code == 0
    assert res.output.index("=== Constable ===") < res.output.index("=== Quest ===")
    assert "Aliases: constable mission, chore mission" in res.output
    assert "Aliases: —" in res.output  # Quest has no aliases
    assert "Do not use: bot mission" in res.output
    assert "Do not use: epic, story group" in res.output


def test_glossary_show_text_exact_output(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 5 exact stdout
    _write_fixture(project_dir, FIVE_ITEM_FIXTURE)
    res = runner.invoke(main, ["glossary", "show", "Quest", "constable"])
    assert res.exit_code == 0
    expected = (
        "=== Constable ===\n"
        "Keyword: Constable\n"
        "Aliases: constable mission, chore mission\n"
        "Do not use: bot mission\n"
        "Definition:\n"
        "  Mission type for orchestrator-handled chores (commits, housekeeping). Not dispatched to a worker.\n"
        "\n"
        "=== Quest ===\n"
        "Keyword: Quest\n"
        "Aliases: —\n"
        "Do not use: epic, story group\n"
        "Definition:\n"
        "  A live grouping of Missions representing one body of work.\n"
    )
    assert res.output == expected


def test_glossary_show_json(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 5 JSON envelope
    _write_fixture(project_dir, FIVE_ITEM_FIXTURE)
    res = runner.invoke(main, ["--json", "glossary", "show", "Quest", "constable"])
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert [i["keyword"] for i in payload["glossary"]] == ["Constable", "Quest"]
    expected = (
        '{"glossary": [{"keyword": "Constable", "definition": "Mission type for orchestrator-handled chores (commits, housekeeping). Not dispatched to a worker.", "aliases": ["constable mission", "chore mission"], "do_not_use": ["bot mission"]},'
        ' {"keyword": "Quest", "definition": "A live grouping of Missions representing one body of work.", "aliases": [], "do_not_use": ["epic", "story group"]}]}'
    )
    assert res.output.strip() == expected


# ---------------------------------------------------------------------------
# Scenario 6 — show rejects aliases
# ---------------------------------------------------------------------------


def test_glossary_show_alias_treated_as_not_found(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 6 (FR-7 aliases not lookup keys)
    _write_fixture(project_dir, FIVE_ITEM_FIXTURE)
    res = runner.invoke(main, ["glossary", "show", "constable mission"])
    assert res.exit_code == 1
    assert res.stdout == ""
    assert (
        res.stderr
        == 'Error: glossary keyword "constable mission" not found.\n'
    )


def test_glossary_show_alias_not_found_json(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 6 JSON variant
    _write_fixture(project_dir, FIVE_ITEM_FIXTURE)
    res = runner.invoke(
        main, ["--json", "glossary", "show", "constable mission"]
    )
    assert res.exit_code == 1
    assert res.stdout == ""
    payload = json.loads(res.stderr)
    assert payload == {
        "error": 'glossary keyword "constable mission" not found.'
    }


# ---------------------------------------------------------------------------
# Scenario 7 — fail-fast on first missing keyword
# ---------------------------------------------------------------------------


def test_glossary_show_fail_fast_no_partial_output(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 7 (fail-fast policy)
    _write_fixture(project_dir, FIVE_ITEM_FIXTURE)
    res = runner.invoke(
        main, ["glossary", "show", "Constable", "NoSuchKeyword", "Quest"]
    )
    assert res.exit_code == 1
    assert res.stdout == ""
    assert (
        'Error: glossary keyword "NoSuchKeyword" not found.' in res.stderr
    )


# ---------------------------------------------------------------------------
# Scenario 8 — missing glossary file behaviour across commands
# ---------------------------------------------------------------------------


def test_glossary_list_missing_file_text(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 8 (missing file fail-soft for read)
    res = runner.invoke(main, ["glossary", "list"])
    assert res.exit_code == 0
    assert res.output == "No glossary defined.\n"


def test_glossary_search_missing_file_text(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 8
    res = runner.invoke(main, ["glossary", "search", "anything"])
    assert res.exit_code == 0
    assert res.output == "No glossary defined.\n"


def test_glossary_show_missing_file_errors(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 8 show on missing file errors
    res = runner.invoke(main, ["glossary", "show", "Mission"])
    assert res.exit_code == 1
    assert res.stdout == ""
    assert 'Error: glossary keyword "Mission" not found.' in res.stderr


def test_glossary_list_missing_file_json(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 8 JSON list on missing file
    res = runner.invoke(main, ["--json", "glossary", "list"])
    assert res.exit_code == 0
    assert res.output.strip() == '{"glossary": []}'


# ---------------------------------------------------------------------------
# Scenario 9 — malformed glossary fails loud
# ---------------------------------------------------------------------------


def test_glossary_list_malformed_text_fail_loud(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 9 (fail-loud per error-handling)
    _write_fixture(project_dir, "items: not-a-list")
    res = runner.invoke(main, ["glossary", "list"])
    assert res.exit_code == 1
    assert res.stdout == ""
    assert res.stderr.startswith("Error: glossary unavailable:")


def test_glossary_list_malformed_json_fail_loud(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 9 JSON variant
    _write_fixture(project_dir, "items: not-a-list")
    res = runner.invoke(main, ["--json", "glossary", "list"])
    assert res.exit_code == 1
    assert res.stdout == ""
    payload = json.loads(res.stderr)
    assert payload["error"].startswith("glossary unavailable:")


# ---------------------------------------------------------------------------
# Scenario 10 — no new/edit/delete subcommands
# ---------------------------------------------------------------------------


def test_glossary_no_new_subcommand(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 10 (read-only CLI; FR-8)
    # Group must exist; only its `new` subcommand must be rejected.
    assert "glossary" in main.commands
    res = runner.invoke(main, ["glossary", "new"])
    assert res.exit_code == 2
    assert "No such command 'new'" in (res.stderr or res.output)


def test_glossary_no_edit_subcommand(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 10
    assert "glossary" in main.commands
    res = runner.invoke(main, ["glossary", "edit"])
    assert res.exit_code == 2
    assert "No such command 'edit'" in (res.stderr or res.output)


def test_glossary_no_delete_subcommand(project_dir, runner):
    # conceptual-workflows-glossary — Scenario 10
    assert "glossary" in main.commands
    res = runner.invoke(main, ["glossary", "delete"])
    assert res.exit_code == 2
    assert "No such command 'delete'" in (res.stderr or res.output)


# ---------------------------------------------------------------------------
# Scenario 11 — help-listing position between codex and artifact
# ---------------------------------------------------------------------------


def test_lore_help_lists_glossary_between_codex_and_artifact(runner):
    # conceptual-workflows-glossary — Scenario 11 (help ordering, Pre-Arch Note 4)
    res = runner.invoke(main, ["--help"])
    out = res.output
    assert out.index("codex") < out.index("glossary") < out.index("artifact")
