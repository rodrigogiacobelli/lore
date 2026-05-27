"""E2E parity for `lore glossary` commands per Tech Spec §10.

Spec §10: "Glossary → tests/e2e/test_api_parity_glossary.py: list,
search, show; canonical-only matching preserved."

CLI envelope must equal ``lore.api.scan_glossary`` / ``search_glossary``
/ ``read_glossary_item``.

Red phase only.
"""

from __future__ import annotations

import json

from lore.cli import main


GLOSSARY_YAML = """\
items:
  - keyword: quest
    aliases:
      - quests
    do_not_use:
      - task
    definition: A body of work tracked in lore.
  - keyword: mission
    definition: A single executable task assigned to a knight.
"""


def _seed_glossary(project_dir):
    path = project_dir / ".lore" / "codex" / "glossary.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(GLOSSARY_YAML)


class TestGlossaryListJsonParity:
    """``lore --json glossary list`` matches ``scan_glossary``."""

    def test_list_envelope_count_matches(self, runner, project_dir):
        from lore import api

        _seed_glossary(project_dir)
        result = runner.invoke(main, ["--json", "glossary", "list"])
        cli_payload = json.loads(result.stdout)
        op_items = api.scan_glossary(project_dir)

        cli_items = cli_payload if isinstance(cli_payload, list) else cli_payload.get("glossary", cli_payload)
        assert len(cli_items) == len(op_items)


class TestGlossarySearchJsonParity:
    """``lore --json glossary search`` matches ``search_glossary``."""

    def test_search_finds_canonical(self, runner, project_dir):
        from lore import api

        _seed_glossary(project_dir)
        result = runner.invoke(
            main, ["--json", "glossary", "search", "quest"]
        )
        cli_payload = json.loads(result.stdout)
        op_items = api.search_glossary(project_dir, "quest")

        cli_items = cli_payload if isinstance(cli_payload, list) else cli_payload.get("results", cli_payload)
        assert len(cli_items) == len(op_items)


class TestGlossaryShowJsonParity:
    """``lore --json glossary show <kw>`` matches ``read_glossary_item``."""

    def test_show_envelope_definition_matches(self, runner, project_dir):
        from lore import api

        _seed_glossary(project_dir)
        result = runner.invoke(
            main, ["--json", "glossary", "show", "quest"]
        )
        cli_payload = json.loads(result.stdout)
        op_item = api.read_glossary_item(project_dir, "quest")

        # CLI envelope: {"glossary": [{keyword, definition, …}]} (verbatim).
        items = cli_payload.get("glossary", []) if isinstance(cli_payload, dict) else []
        assert items, "glossary show envelope missing 'glossary' list"
        cli_def = items[0].get("definition")
        op_def = getattr(op_item, "definition", None) if op_item else None
        assert cli_def == op_def
