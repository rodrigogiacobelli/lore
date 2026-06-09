"""E2E tests for browsing rites with lore rite list / list --shared.

Spec: conceptual-workflows-rite-list (lore codex show conceptual-workflows-rite-list)

Covers list (main rites), list --shared (shared steps), empty states, the
GROUP column, ``--filter``, and the JSON envelopes. Rites are recursive and
grouped like every other entity (decisions-016): the list JSON envelope
CARRIES ``group`` (root → null). The field-presence-always rule holds: an
empty result is ``{"rites": []}`` / ``{"shared_steps": []}``.

Per Click 8.3 the runner exposes stdout/stderr separately (no mix_stderr).
Every test MUST fail until US-002 Green lands lore rite list.
"""

from __future__ import annotations

import json
from pathlib import Path

from lore.cli import main


# Canonical design-doc fixtures (Tech Spec §Exact YAML schemas).
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

CANONICAL_SHARED_STEP_YAML = """\
id: read-contact-info
title: Read the user's contact information
summary: Read the user's email, phone, and mailing address from admin.
do: |
  Open the user profile in admin. Read and report back:
    - email
    - phone
    - mailing address, with its last-confirmed date
"""


def _seed_main(project_dir: Path, name: str, text: str) -> None:
    path = project_dir / ".lore" / "rites" / "main" / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_shared(project_dir: Path, name: str, text: str) -> None:
    path = project_dir / ".lore" / "rites" / "shared" / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_main_grouped(project_dir: Path, group: str, name: str, text: str) -> None:
    path = project_dir / ".lore" / "rites" / "main" / group / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Scenario 1: list main rites (text) — columns ID / TRIGGER / SUMMARY
# ---------------------------------------------------------------------------


class TestListMainRitesText:
    def test_exit_zero(self, runner, project_dir):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE_YAML)
        result = runner.invoke(main, ["rite", "list"])
        assert result.exit_code == 0

    def test_header_columns(self, runner, project_dir):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE_YAML)
        result = runner.invoke(main, ["rite", "list"])
        header = result.stdout.splitlines()[0]
        assert "ID" in header
        assert "GROUP" in header
        assert "TRIGGER" in header
        assert "SUMMARY" in header

    def test_lists_seeded_rite_id(self, runner, project_dir):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE_YAML)
        result = runner.invoke(main, ["rite", "list"])
        assert "issue-refund" in result.stdout


# ---------------------------------------------------------------------------
# Scenario 2: list shared steps (text) — columns ID / GROUP / TITLE / SUMMARY
# ---------------------------------------------------------------------------


class TestListSharedStepsText:
    def test_exit_zero(self, runner, project_dir):
        _seed_shared(project_dir, "read-contact-info", CANONICAL_SHARED_STEP_YAML)
        result = runner.invoke(main, ["rite", "list", "--shared"])
        assert result.exit_code == 0

    def test_header_columns_id_group_title_summary_no_trigger(self, runner, project_dir):
        _seed_shared(project_dir, "read-contact-info", CANONICAL_SHARED_STEP_YAML)
        result = runner.invoke(main, ["rite", "list", "--shared"])
        header = result.stdout.splitlines()[0]
        assert "ID" in header
        assert "GROUP" in header
        assert "TITLE" in header
        assert "SUMMARY" in header
        assert "TRIGGER" not in header

    def test_lists_seeded_shared_id(self, runner, project_dir):
        _seed_shared(project_dir, "read-contact-info", CANONICAL_SHARED_STEP_YAML)
        result = runner.invoke(main, ["rite", "list", "--shared"])
        assert "read-contact-info" in result.stdout

    def test_lists_shared_summary(self, runner, project_dir):
        _seed_shared(project_dir, "read-contact-info", CANONICAL_SHARED_STEP_YAML)
        result = runner.invoke(main, ["rite", "list", "--shared"])
        assert "Read the user's email, phone, and mailing address from admin." in result.stdout


# ---------------------------------------------------------------------------
# Scenario 3: empty states
# ---------------------------------------------------------------------------


class TestListEmptyStates:
    def test_main_empty_message(self, runner, project_dir):
        result = runner.invoke(main, ["rite", "list"])
        assert result.stdout.strip() == "No rites found."
        assert result.exit_code == 0

    def test_shared_empty_message(self, runner, project_dir):
        result = runner.invoke(main, ["rite", "list", "--shared"])
        assert result.stdout.strip() == "No shared steps found."
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Scenario 4: JSON envelopes — group key carried; field-presence-always
# ---------------------------------------------------------------------------


class TestListJsonEnvelopes:
    def test_main_envelope_carries_group(self, runner, project_dir):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE_YAML)
        out = json.loads(runner.invoke(main, ["--json", "rite", "list"]).stdout)
        assert out == {
            "rites": [
                {
                    "id": "issue-refund",
                    "group": None,
                    "trigger": "Customer requests a refund on a returned order.",
                    "summary": "Confirm the customer is reachable, then refund.",
                }
            ]
        }
        assert out["rites"][0]["group"] is None

    def test_main_envelope_grouped_carries_group(self, runner, project_dir):
        _seed_main_grouped(
            project_dir, "diagnostics/network", "issue-refund", CANONICAL_MAIN_RITE_YAML
        )
        out = json.loads(runner.invoke(main, ["--json", "rite", "list"]).stdout)
        assert out["rites"][0]["group"] == "diagnostics/network"

    def test_shared_envelope_carries_group(self, runner, project_dir):
        _seed_shared(project_dir, "read-contact-info", CANONICAL_SHARED_STEP_YAML)
        sh = json.loads(
            runner.invoke(main, ["--json", "rite", "list", "--shared"]).stdout
        )
        assert sh == {
            "shared_steps": [
                {
                    "id": "read-contact-info",
                    "group": None,
                    "title": "Read the user's contact information",
                    "summary": "Read the user's email, phone, and mailing address from admin.",
                }
            ]
        }

    def test_empty_main_envelope(self, runner, project_dir):
        out = json.loads(runner.invoke(main, ["--json", "rite", "list"]).stdout)
        assert out == {"rites": []}

    def test_empty_shared_envelope(self, runner, project_dir):
        out = json.loads(
            runner.invoke(main, ["--json", "rite", "list", "--shared"]).stdout
        )
        assert out == {"shared_steps": []}


# ---------------------------------------------------------------------------
# Scenario 4b: --json honoured in both global and local positions
# Spec: conceptual-workflows-json-output (global-before / local-after flag).
# ---------------------------------------------------------------------------


class TestListJsonFlagPositions:
    def test_global_and_local_json_equivalent(self, runner, project_dir):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE_YAML)
        glob = runner.invoke(main, ["--json", "rite", "list"]).stdout
        loc = runner.invoke(main, ["rite", "list", "--json"]).stdout
        assert json.loads(glob) == json.loads(loc)

    def test_local_json_envelope_carries_group(self, runner, project_dir):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE_YAML)
        out = json.loads(runner.invoke(main, ["rite", "list", "--json"]).stdout)
        assert "group" in out["rites"][0]
        assert out["rites"][0]["group"] is None


# ---------------------------------------------------------------------------
# Scenario 5: recursive discovery + GROUP column + --filter
# ---------------------------------------------------------------------------


class TestRecursiveDiscoveryAndGroup:
    def test_discovers_rite_in_subfolder(self, runner, project_dir):
        _seed_main_grouped(
            project_dir, "diagnostics/network", "diagnose-timeout", CANONICAL_MAIN_RITE_YAML
        )
        result = runner.invoke(main, ["rite", "list"])
        assert result.exit_code == 0
        assert "issue-refund" in result.stdout  # id from fixture body

    def test_group_column_shows_derived_path(self, runner, project_dir):
        _seed_main_grouped(
            project_dir, "diagnostics/network", "diagnose-timeout", CANONICAL_MAIN_RITE_YAML
        )
        result = runner.invoke(main, ["rite", "list"])
        assert "diagnostics/network" in result.stdout

    def test_root_rite_has_empty_group_column(self, runner, project_dir):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE_YAML)
        out = json.loads(runner.invoke(main, ["--json", "rite", "list"]).stdout)
        assert out["rites"][0]["group"] is None

    def test_shared_recursive_discovery(self, runner, project_dir):
        path = (
            project_dir / ".lore" / "rites" / "shared" / "io" / "read-contact-info.yaml"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(CANONICAL_SHARED_STEP_YAML, encoding="utf-8")
        out = json.loads(
            runner.invoke(main, ["--json", "rite", "list", "--shared"]).stdout
        )
        assert out["shared_steps"][0]["group"] == "io"


class TestFilter:
    def _seed_two_groups(self, project_dir):
        _seed_main_grouped(
            project_dir, "diagnostics/network", "diagnose-timeout", CANONICAL_MAIN_RITE_YAML
        )
        billing = CANONICAL_MAIN_RITE_YAML.replace("id: issue-refund", "id: bill-it")
        _seed_main_grouped(project_dir, "billing", "bill-it", billing)

    def test_filter_narrows_to_group(self, runner, project_dir):
        self._seed_two_groups(project_dir)
        out = json.loads(
            runner.invoke(main, ["--json", "rite", "list", "--filter", "billing"]).stdout
        )
        groups = {r["group"] for r in out["rites"]}
        assert groups == {"billing"}

    def test_filter_segment_prefix(self, runner, project_dir):
        self._seed_two_groups(project_dir)
        out = json.loads(
            runner.invoke(
                main, ["--json", "rite", "list", "--filter", "diagnostics"]
            ).stdout
        )
        groups = {r["group"] for r in out["rites"]}
        assert groups == {"diagnostics/network"}

    def test_filter_space_separated_multiple(self, runner, project_dir):
        self._seed_two_groups(project_dir)
        out = json.loads(
            runner.invoke(
                main, ["--json", "rite", "list", "--filter", "billing", "diagnostics"]
            ).stdout
        )
        groups = {r["group"] for r in out["rites"]}
        assert groups == {"billing", "diagnostics/network"}

    def test_empty_filter_token_errors(self, runner, project_dir):
        self._seed_two_groups(project_dir)
        result = runner.invoke(main, ["rite", "list", "--filter", "/"])
        assert result.exit_code != 0
