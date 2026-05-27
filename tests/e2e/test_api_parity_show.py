"""E2E parity tests for `lore show` after G12 dispatcher refactor.

Plan: transient-public-api-facade-plan §G12.
Anchor: decisions-011-api-parity-with-cli — when the CLI's top-level
``show`` dispatcher collapses to a one-liner that delegates to
``lore.db.get_quest_detail`` / ``get_mission_detail``, the user-visible
CLI behaviour (exit code, stdout, stderr, JSON envelope, text body)
MUST remain byte-identical to the pre-refactor surface.

These tests pin the parity contract for the refactor that lands in G12
Green:

* JSON envelope from CLI ==  ``json.loads`` of  ``get_quest_detail`` /
  ``get_mission_detail`` op fn result for the same ID.
* Loose-quest-ID DB fallback preserved (test-DB synthetic IDs still
  resolve via ``_classify_entity_id_with_db_fallback``).
* Format-error path on garbage IDs emits a uniform error via
  ``_emit_format_error`` (CHANGED #8).

Red phase — every test MUST fail until G12 Green lands. The test set
also fails earlier than that because some assertions only hold after
the dispatcher refactor (e.g. `quest_deleted` key absence from JSON
envelope per Review-Ledger CHANGED #3).
"""

from __future__ import annotations

import json

from lore.cli import main
from tests.conftest import (
    insert_board_message,
    insert_dependency,
    insert_mission,
    insert_quest,
)


# ---------------------------------------------------------------------------
# Quest show — JSON envelope parity with get_quest_detail
# ---------------------------------------------------------------------------


class TestShowQuestJsonParity:
    """`lore --json show <quest-id>` envelope matches ``get_quest_detail``."""

    def test_exit_zero_for_existing_quest(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Q")
        result = runner.invoke(main, ["--json", "show", "q-a1b2"])
        assert result.exit_code == 0

    def test_json_envelope_matches_get_quest_detail(self, runner, project_dir):
        from lore.db import get_quest_detail

        insert_quest(project_dir, "q-a1b2", "Q", description="desc", priority=3)
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1")
        insert_mission(project_dir, "q-a1b2/m-bbbb", "q-a1b2", "M2")
        insert_dependency(project_dir, "q-a1b2/m-bbbb", "q-a1b2/m-aaaa")
        insert_board_message(project_dir, "q-a1b2", "hello")

        result = runner.invoke(main, ["--json", "show", "q-a1b2"])
        assert result.exit_code == 0
        cli_envelope = json.loads(result.output)

        op_envelope = get_quest_detail(project_dir, "q-a1b2")
        assert op_envelope is not None
        assert cli_envelope == op_envelope, (
            "G12: lore --json show <quest> must emit byte-identical envelope "
            "from lore.db.get_quest_detail"
        )

    def test_json_envelope_has_no_parents_field(self, runner, project_dir):
        """Review-Ledger CHANGED #2 — no ``parents`` key in quest envelope."""
        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1")
        result = runner.invoke(main, ["--json", "show", "q-a1b2"])
        payload = json.loads(result.output)
        for m in payload["missions"]:
            assert "parents" not in m, (
                "G12 + Review-Ledger CHANGED #2: quest envelope must NOT carry parents"
            )

    def test_json_envelope_uses_insertion_order(self, runner, project_dir):
        """Review-Ledger CHANGED #2 — missions in insertion order, not topo."""
        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "First")
        insert_mission(project_dir, "q-a1b2/m-bbbb", "q-a1b2", "Second")
        insert_dependency(
            project_dir, "q-a1b2/m-aaaa", "q-a1b2/m-bbbb"
        )  # aaaa needs bbbb
        result = runner.invoke(main, ["--json", "show", "q-a1b2"])
        payload = json.loads(result.output)
        ids = [m["id"] for m in payload["missions"]]
        # Insertion order must be aaaa, bbbb — NOT topologically swapped.
        assert ids == ["q-a1b2/m-aaaa", "q-a1b2/m-bbbb"]

    def test_missing_quest_exits_one(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "show", "q-dead"])
        assert result.exit_code == 1

    def test_loose_quest_id_present_in_db_resolves(self, runner, project_dir):
        """Synthetic test-DB ID (non-hex) still resolves via DB fallback."""
        insert_quest(project_dir, "q-zzzz", "Loose")
        result = runner.invoke(main, ["--json", "show", "q-zzzz"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["id"] == "q-zzzz"

    def test_loose_quest_id_absent_is_format_error(self, runner, project_dir):
        """Non-existent loose-pattern ID surfaces format error (not not-found)."""
        result = runner.invoke(main, ["--json", "show", "q-zzzz"])
        assert result.exit_code == 1
        combined = (result.output or "") + (
            result.stderr if hasattr(result, "stderr") else ""
        )
        assert "format" in combined.lower() or "invalid" in combined.lower()


# ---------------------------------------------------------------------------
# Mission show — JSON envelope parity with get_mission_detail
# ---------------------------------------------------------------------------


class TestShowMissionJsonParity:
    """`lore --json show <mission-id>` envelope matches ``get_mission_detail``."""

    def test_exit_zero_for_existing_mission(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1")
        result = runner.invoke(main, ["--json", "show", "q-a1b2/m-aaaa"])
        assert result.exit_code == 0

    def test_json_envelope_matches_get_mission_detail(self, runner, project_dir):
        from lore.db import get_mission_detail

        insert_quest(project_dir, "q-a1b2", "Q")
        insert_mission(
            project_dir,
            "q-a1b2/m-aaaa",
            "q-a1b2",
            "M1",
            mission_type="knight",
            knight="reviewer.md",
        )
        insert_mission(project_dir, "q-a1b2/m-bbbb", "q-a1b2", "M2")
        insert_dependency(project_dir, "q-a1b2/m-aaaa", "q-a1b2/m-bbbb")
        insert_board_message(project_dir, "q-a1b2/m-aaaa", "note")

        result = runner.invoke(
            main, ["--json", "show", "--no-knight", "q-a1b2/m-aaaa"]
        )
        assert result.exit_code == 0
        cli_envelope = json.loads(result.output)

        op_envelope = get_mission_detail(
            project_dir, "q-a1b2/m-aaaa", include_knight=False
        )
        assert op_envelope is not None
        assert cli_envelope == op_envelope, (
            "G12: lore --json show <mission> must emit byte-identical envelope "
            "from lore.db.get_mission_detail"
        )

    def test_json_envelope_omits_quest_deleted(self, runner, project_dir):
        """Review-Ledger CHANGED #3 — ``quest_deleted`` is text-mode-only."""
        insert_quest(project_dir, "q-a1b2", "Q", deleted_at="2025-01-15T10:00:00Z")
        insert_mission(project_dir, "q-a1b2/m-aaaa", "q-a1b2", "M1")
        result = runner.invoke(main, ["--json", "show", "q-a1b2/m-aaaa"])
        payload = json.loads(result.output)
        assert "quest_deleted" not in payload, (
            "G12 + Review-Ledger CHANGED #3: mission JSON must NOT carry quest_deleted"
        )

    def test_missing_mission_exits_one(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "show", "m-dead"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Garbage-ID dispatch — uniform format error via _emit_format_error
# ---------------------------------------------------------------------------


class TestShowGarbageIdFormatError:
    """Garbage IDs emit format error; classification logic centralized."""

    def test_garbage_exits_one(self, runner, project_dir):
        result = runner.invoke(main, ["show", "garbage"])
        assert result.exit_code == 1

    def test_garbage_json_envelope_has_error_key(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "show", "garbage"])
        combined = (result.output or "") + (
            result.stderr if hasattr(result, "stderr") else ""
        )
        payload = json.loads(combined.splitlines()[0])
        assert "error" in payload

    def test_bad_quest_format_message_names_input(self, runner, project_dir):
        result = runner.invoke(main, ["show", "q-aaaaaaaaa"])  # too long
        combined = (result.output or "") + (
            result.stderr if hasattr(result, "stderr") else ""
        )
        assert "q-aaaaaaaaa" in combined


# ---------------------------------------------------------------------------
# Structural assertions — proves show dispatcher uses op fns post-G12
# ---------------------------------------------------------------------------


class TestShowDispatcherStructure:
    """`show` becomes a thin wrapper over get_quest_detail / get_mission_detail.

    The CLI handler no longer hand-rolls envelope assembly inline — it
    calls the op fns and emits their dict. The previous private helpers
    ``_show_quest`` / ``_show_mission`` (cli.py:1961+, 2100+) carried
    the inline assembly; they should be removed or reduced.
    """

    def test_show_uses_classifier_helper(self):
        """Top-level show handler must call _classify_entity_id_with_db_fallback."""
        from pathlib import Path
        import ast

        src = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "lore"
            / "cli.py"
        ).read_text()
        # Post-G12 the show handler routes via the new classifier helper.
        assert "_classify_entity_id_with_db_fallback" in src, (
            "G12: cli.show should route via _classify_entity_id_with_db_fallback"
        )
        # Sanity: the helper is actually a defined function, not a stray
        # string literal somewhere in a docstring.
        tree = ast.parse(src)
        defined = {
            n.name
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef)
            and n.name == "_classify_entity_id_with_db_fallback"
        }
        assert defined, (
            "G12: _classify_entity_id_with_db_fallback must be defined in cli.py"
        )
