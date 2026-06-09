"""E2E tests for keyword-browsing rites with lore rite search.

Spec: conceptual-workflows-rite-search (lore codex show conceptual-workflows-rite-search)

search is a case-insensitive substring browse over a main rite's
id/title/summary/trigger — NOT the deferred situational matcher. Matching rites
render in the same ID/TRIGGER/SUMMARY table as list. A miss is success (exit 0)
with the message ``No rites matching "<keyword>".`` and a ``{"rites": []}`` JSON
envelope (group key omitted, decisions-016-rite-json-envelope-omits-group).

Per Click 8.3 the runner exposes stdout/stderr separately (no mix_stderr).
Every test MUST fail until US-002 Green lands lore rite search.
"""

from __future__ import annotations

import json
from pathlib import Path

from lore.cli import main


CANONICAL_MAIN_RITE_YAML = """\
id: issue-refund
title: Issue a refund for a returned order
summary: Confirm the customer is reachable, then refund.
trigger: Customer requests a refund on a returned order.
nodes:
  - id: only-step
    do: Find the order by id; confirm it is in 'returned' state.
    then: refunded
conclusions:
  refunded:
    audience: customer-care
    response: Refund posted; share the transaction id.
"""


def _seed_main(project_dir: Path, name: str, text: str) -> None:
    path = project_dir / ".lore" / "rites" / "main" / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Scenario 5: search hit — same ID/TRIGGER/SUMMARY table as list
# ---------------------------------------------------------------------------


class TestSearchHit:
    def test_exit_zero(self, runner, project_dir):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE_YAML)
        result = runner.invoke(main, ["rite", "search", "refund"])
        assert result.exit_code == 0

    def test_lists_matching_rite(self, runner, project_dir):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE_YAML)
        result = runner.invoke(main, ["rite", "search", "refund"])
        assert "issue-refund" in result.stdout

    def test_renders_same_columns_as_list(self, runner, project_dir):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE_YAML)
        result = runner.invoke(main, ["rite", "search", "refund"])
        header = result.stdout.splitlines()[0]
        assert "ID" in header
        assert "TRIGGER" in header
        assert "SUMMARY" in header

    def test_case_insensitive_match(self, runner, project_dir):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE_YAML)
        result = runner.invoke(main, ["rite", "search", "REFUND"])
        assert "issue-refund" in result.stdout

    def test_json_hit_envelope_no_group(self, runner, project_dir):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE_YAML)
        out = json.loads(
            runner.invoke(main, ["--json", "rite", "search", "refund"]).stdout
        )
        assert out == {
            "rites": [
                {
                    "id": "issue-refund",
                    "trigger": "Customer requests a refund on a returned order.",
                    "summary": "Confirm the customer is reachable, then refund.",
                }
            ]
        }
        assert "group" not in out["rites"][0]


# ---------------------------------------------------------------------------
# Scenario 6: search miss — exit 0, miss message, empty JSON envelope
# ---------------------------------------------------------------------------


class TestSearchMiss:
    def test_miss_message_and_exit_zero(self, runner, project_dir):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE_YAML)
        result = runner.invoke(main, ["rite", "search", "zzzznomatch"])
        assert result.stdout.strip() == 'No rites matching "zzzznomatch".'
        assert result.exit_code == 0

    def test_miss_json_empty_envelope(self, runner, project_dir):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE_YAML)
        out = json.loads(
            runner.invoke(main, ["--json", "rite", "search", "zzzznomatch"]).stdout
        )
        assert out == {"rites": []}
