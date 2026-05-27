"""E2E parity tests for `lore new mission` after G12 inferred-quest refactor.

Plan: transient-public-api-facade-plan §G12.
Anchor: decisions-011-api-parity-with-cli.
Review-Ledger FLAG #4: behaviour change for direct-Python callers.

Today's split:
  * CLI handler (cli.py:422-431) runs a raw SQL probe for the
    sole-open-quest case before calling ``create_mission``.
  * Direct-Python callers of ``create_mission`` get NO inferred-quest
    behaviour — they pass either an explicit ``quest_id`` or get a
    standalone mission.

G12 pushes the probe INTO ``lore.db.create_mission``:
  * CLI handler drops the raw SQL probe entirely; just calls
    ``create_mission(project_root, title, quest_id=quest_id, ...)``.
  * Direct-Python ``create_mission(project_root, "title")`` (no
    quest_id) now AUTO-ATTACHES to the sole-open-quest when exactly
    one exists. This is the BREAKING behaviour change called out in
    Review-Ledger FLAG #4 / Open Item #4 — release notes + CHANGELOG.

These tests pin BOTH layers of the contract:
  1. CLI behaviour preserved byte-for-byte.
  2. Direct-Python ``create_mission`` learns the new inferred-quest
     behaviour.

Red phase only.
"""

from __future__ import annotations

import json

from lore.cli import main
from tests.conftest import insert_quest


# ---------------------------------------------------------------------------
# CLI parity — `lore new mission` behaviour unchanged from user perspective
# ---------------------------------------------------------------------------


class TestNewMissionCliParity:
    """CLI ``new mission`` keeps the same envelope through the refactor."""

    def test_with_explicit_quest_attaches(self, runner, project_dir):
        insert_quest(project_dir, "q-a1b2", "Q")
        result = runner.invoke(
            main,
            ["--json", "new", "mission", "Title", "-q", "q-a1b2"],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["id"].startswith("q-a1b2/m-")

    def test_with_no_quest_and_single_open_quest_infers(self, runner, project_dir):
        """Single open quest + omitted -q  ->  mission attaches to it."""
        insert_quest(project_dir, "q-a1b2", "Q")
        result = runner.invoke(
            main, ["--json", "new", "mission", "Title"]
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["id"].startswith("q-a1b2/m-"), (
            "Sole-open-quest inference must keep working from CLI"
        )

    def test_with_no_quest_and_zero_quests_standalone(self, runner, project_dir):
        result = runner.invoke(
            main, ["--json", "new", "mission", "Title"]
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["id"].startswith("m-")  # standalone
        assert "/" not in payload["id"]

    def test_with_no_quest_and_two_open_quests_standalone(
        self, runner, project_dir
    ):
        """Two open quests + omitted -q  ->  standalone (ambiguous case)."""
        insert_quest(project_dir, "q-aaaa", "Q1")
        insert_quest(project_dir, "q-bbbb", "Q2")
        result = runner.invoke(
            main, ["--json", "new", "mission", "Title"]
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["id"].startswith("m-")
        assert "/" not in payload["id"]

    def test_with_closed_quest_still_standalone(self, runner, project_dir):
        """Closed quests don't count toward 'sole open' inference."""
        insert_quest(
            project_dir,
            "q-aaaa",
            "Q",
            status="closed",
            closed_at="2025-01-15T09:00:00Z",
        )
        result = runner.invoke(
            main, ["--json", "new", "mission", "Title"]
        )
        payload = json.loads(result.output)
        assert payload["id"].startswith("m-")
        assert "/" not in payload["id"]


# ---------------------------------------------------------------------------
# Direct-Python parity — FLAG #4 BREAKING CHANGE for create_mission
# ---------------------------------------------------------------------------


class TestCreateMissionInferredQuestPushedToDb:
    """Direct-Python ``create_mission`` learns the inferred-quest behaviour.

    Today (pre-G12) ``create_mission(project_root, "title")`` returns a
    standalone mission ID even when exactly one open quest exists —
    the SQL probe lives in cli.py only.

    Post-G12 the probe is inside ``create_mission`` itself, so direct
    callers see the SAME inference as the CLI. This is the documented
    behaviour change in Review-Ledger FLAG #4 — both release notes and
    CHANGELOG must call it out.
    """

    def test_sole_open_quest_auto_attaches_via_direct_python(self, project_dir):
        from lore.db import create_mission

        insert_quest(project_dir, "q-a1b2", "Q")
        # G17: create_mission returns dict envelope; extract `id`.
        mission_id = create_mission(project_dir, "Direct title")["id"]
        assert mission_id.startswith("q-a1b2/m-"), (
            "FLAG #4: create_mission(project_root, title) with no quest_id "
            "must auto-attach to the sole open quest (G12 behaviour change)"
        )

    def test_zero_quests_returns_standalone_via_direct_python(self, project_dir):
        from lore.db import create_mission

        mission_id = create_mission(project_dir, "Direct title")["id"]
        assert mission_id.startswith("m-")
        assert "/" not in mission_id

    def test_two_open_quests_returns_standalone_via_direct_python(self, project_dir):
        from lore.db import create_mission

        insert_quest(project_dir, "q-aaaa", "Q1")
        insert_quest(project_dir, "q-bbbb", "Q2")
        mission_id = create_mission(project_dir, "Direct title")["id"]
        # Ambiguous -> standalone, NOT a crash.
        assert mission_id.startswith("m-")
        assert "/" not in mission_id

    def test_closed_quest_excluded_from_inference(self, project_dir):
        from lore.db import create_mission

        insert_quest(
            project_dir,
            "q-aaaa",
            "Q",
            status="closed",
            closed_at="2025-01-15T09:00:00Z",
        )
        mission_id = create_mission(project_dir, "Direct title")["id"]
        assert mission_id.startswith("m-")
        assert "/" not in mission_id

    def test_explicit_quest_id_overrides_inference(self, project_dir):
        from lore.db import create_mission

        insert_quest(project_dir, "q-aaaa", "Q1")
        insert_quest(project_dir, "q-bbbb", "Q2")
        mission_id = create_mission(
            project_dir, "Direct title", quest_id="q-aaaa"
        )["id"]
        assert mission_id.startswith("q-aaaa/m-")


# ---------------------------------------------------------------------------
# CLI handler no longer hand-rolls the SQL probe
# ---------------------------------------------------------------------------


class TestCliNewMissionDropsRawSqlProbe:
    """G12: cli.new_mission must NOT execute a raw SQL probe.

    Spec §G12: 'CLI drops raw SQL probe' — pushes probe into db.create_mission.
    A grep-style scan of cli.py asserts the raw SQL string is gone.
    """

    def test_cli_no_longer_contains_inline_sql_for_open_quest_count(self):
        from pathlib import Path

        cli_src = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "lore"
            / "cli.py"
        ).read_text()
        # The exact probe today is
        #   "SELECT id FROM quests WHERE status != 'closed'"
        # G12 removes it from cli.py (moves into db.create_mission).
        assert "SELECT id FROM quests WHERE status != 'closed'" not in cli_src, (
            "G12: cli.py must not hand-roll the open-quests SQL probe; "
            "let db.create_mission infer the parent quest instead"
        )
