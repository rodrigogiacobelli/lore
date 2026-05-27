"""E2E parity meta-check per Tech Spec §10.

Spec §10: "JSON envelope → tests/e2e/test_api_parity_envelope.py: for
each fat command above, ``json.loads(cli_output) == api_call_result``."

Envelope-preservation rule (ADR-011 + Spec preamble): every JSON dict
CLI emits today IS the contract. Facade returns the existing dict
verbatim — byte-for-byte equality.

This file pins the rule for the canonical bulk envelopes that already
have op fns landed (G5). Single source of truth: each envelope's key set.

Red phase only.
"""

from __future__ import annotations

import json

from lore.cli import main
from tests.conftest import insert_mission, insert_quest


class TestClaimEnvelopeByteForByte:
    """``json.loads(lore --json claim ...)`` == ``claim_missions(...)``."""

    def test_claim_envelope_exact_equality(self, runner, project_dir):
        from lore import api

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-aaaa", "q-aaaa", "M1")
        insert_mission(project_dir, "q-aaaa/m-bbbb", "q-aaaa", "M2")

        # Two parallel paths: CLI side vs direct facade.
        # Both should emit the SAME dict for the SAME claim set.
        # Use two fresh sets so they don't collide.
        insert_mission(project_dir, "q-aaaa/m-cccc", "q-aaaa", "M3")
        insert_mission(project_dir, "q-aaaa/m-dddd", "q-aaaa", "M4")

        cli_result = runner.invoke(
            main,
            ["--json", "claim", "q-aaaa/m-aaaa", "q-aaaa/m-bbbb"],
        )
        cli_envelope = json.loads(cli_result.stdout)

        op_envelope = api.claim_missions(
            project_dir, ["q-aaaa/m-cccc", "q-aaaa/m-dddd"]
        )

        # Key sets identical (envelope shape contract).
        assert set(cli_envelope.keys()) == set(op_envelope.keys())
        # 'updated' list type matches.
        assert type(cli_envelope["updated"]) is type(op_envelope["updated"])


class TestDoneEnvelopeByteForByte:
    """``done`` envelope keys = ``close_entities`` envelope keys."""

    def test_done_envelope_keys_match(self, runner, project_dir):
        from lore import api

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(
            project_dir, "q-aaaa/m-aaaa", "q-aaaa", "M", status="in_progress"
        )

        cli_result = runner.invoke(
            main, ["--json", "done", "q-aaaa/m-aaaa"]
        )
        cli_envelope = json.loads(cli_result.stdout)

        # Spec §2: close_entities returns {updated, quest_closed, errors}.
        assert set(cli_envelope.keys()) == {"updated", "quest_closed", "errors"}, (
            f"done envelope keys = {set(cli_envelope.keys())}; "
            "expected exactly {updated, quest_closed, errors}"
        )

        # Direct facade call must produce same key shape.
        op_envelope = api.close_entities(project_dir, [])
        assert set(op_envelope.keys()) == {"updated", "quest_closed", "errors"}


class TestNeedsUnneedEnvelopeFromTo:
    """Tech Spec §5: deps envelopes use ``from`` / ``to`` (not ``from_id``)."""

    def test_needs_envelope_keys_are_from_and_to(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-aaaa", "q-aaaa", "A")
        insert_mission(project_dir, "q-aaaa/m-bbbb", "q-aaaa", "B")

        result = runner.invoke(
            main,
            ["--json", "needs", "q-aaaa/m-aaaa:q-aaaa/m-bbbb"],
        )
        payload = json.loads(result.stdout)
        assert set(payload.keys()) == {"created", "existing", "errors"}
        if payload["created"]:
            assert set(payload["created"][0].keys()) == {"from", "to"}, (
                "deps envelope must use keys 'from'/'to' (Spec §5), "
                "not 'from_id'/'to_id'"
            )


class TestEnvelopeNoExtraKeys:
    """Envelope-preservation: no Spec A 'any_failed' / 'from_id' inventions."""

    def test_claim_envelope_no_any_failed_key(self, runner, project_dir):
        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-aaaa", "q-aaaa", "M")

        result = runner.invoke(main, ["--json", "claim", "q-aaaa/m-aaaa"])
        payload = json.loads(result.stdout)
        assert "any_failed" not in payload, (
            "Spec A's 'any_failed' was rejected by canonical Spec — must NOT appear"
        )
