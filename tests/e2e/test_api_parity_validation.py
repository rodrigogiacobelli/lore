"""E2E parity for validation per Tech Spec §10.

Spec §10: "Validation → tests/e2e/test_api_parity_validation.py: empty
board message rejection at API layer; priority bounds; entity-ID format."

ADR-011 Decision 1 (locked): validation owned by ``lore.validators``; CLI
keeps thin UX translators that DELEGATE. No new rule lives in CLI.

Red phase only.
"""

from __future__ import annotations

import json

import pytest

from lore.cli import main


class TestValidatePriorityBounds:
    """``validate_priority`` is the single source — CLI delegates."""

    def test_priority_below_min_rejected(self, runner, project_dir):
        """Negative priority must be rejected (validate_priority range [0, 4])."""
        result = runner.invoke(
            main, ["--json", "new", "quest", "Q", "--priority", "-1"]
        )
        assert result.exit_code != 0 or "error" in result.stdout.lower()

    def test_priority_above_max_rejected(self, runner, project_dir):
        """Priority > 4 must be rejected (validate_priority range [0, 4])."""
        result = runner.invoke(
            main, ["--json", "new", "quest", "Q", "--priority", "6"]
        )
        assert result.exit_code != 0 or "error" in result.stdout.lower()

    def test_facade_exposes_validate_priority(self):
        """ADR-010: validate_priority is reachable via lore.api."""
        from lore import api

        assert callable(api.validate_priority)


class TestValidateMissionIdFormat:
    """Entity-ID format errors must surface through the same code path."""

    def test_invalid_mission_id_format_in_claim_envelope(
        self, runner, project_dir
    ):
        result = runner.invoke(
            main, ["--json", "claim", "not-an-id"]
        )
        payload = json.loads(result.stdout)
        # Per Tech Spec §2 claim_missions envelope: errors list collects bad IDs.
        assert "errors" in payload
        assert len(payload["errors"]) >= 1
        assert "not-an-id" in payload["errors"][0]


class TestValidateBoardMessageAtApiLayer:
    """ADR-011 + audit: empty board message rejected by op fn, not CLI."""

    def test_validate_message_rejects_empty(self):
        """``validate_message`` returns an error string for empty input."""
        from lore import api

        err = api.validate_message("")
        assert err is not None, "Empty message must produce an error"
        assert "empty" in err.lower()

    def test_validate_message_accepts_nonempty(self):
        from lore import api

        assert api.validate_message("hello") is None


class TestValidateRouteEntity:
    """``route_entity`` reachable via facade and dispatches on quest/mission."""

    def test_route_entity_resolves_quest(self):
        from lore import api

        table, _ = api.route_entity("q-a1b2")
        assert table == "quests"

    def test_route_entity_resolves_mission(self):
        from lore import api

        table, _ = api.route_entity("q-a1b2/m-aaaa")
        assert table == "missions"

    def test_route_entity_rejects_garbage(self):
        from lore import api

        with pytest.raises(ValueError):
            api.route_entity("garbage")
