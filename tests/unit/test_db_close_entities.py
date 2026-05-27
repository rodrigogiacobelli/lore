"""Red tests for G5: `lore.db.close_entities` bulk op.

Spec source:
  lore codex show transient-public-api-facade-plan      # §G5
  lore codex show transient-public-api-facade-tech-spec # §5

Envelope (per cli.py:570-578, byte-exact):
  {"updated": [...], "quest_closed": [...], "errors": [...]}

Behaviour contract (per plan G5):
  * accepts mixed mission AND quest IDs in one call
  * delegates to single-shot `close_mission` / `close_quest` per id
  * idempotency on already-closed → success path, no error
  * `_derive_quest_status` coalesced to at most ONE call per affected quest
  * one failing entity does NOT roll back prior successes

These tests EXPECT the bulk fn to exist at `lore.db.close_entities`. They
MUST fail until G5 Green lands the implementation.
"""

from __future__ import annotations


from tests.conftest import insert_mission, insert_quest


# ---------------------------------------------------------------------------
# Symbol existence
# ---------------------------------------------------------------------------


def test_close_entities_symbol_exists_on_lore_db():
    from lore import db

    assert hasattr(db, "close_entities"), (
        "G5: lore.db.close_entities not defined yet (Red phase expected)"
    )
    assert callable(db.close_entities)


# ---------------------------------------------------------------------------
# Envelope shape — keys EXACTLY {updated, quest_closed, errors}
# ---------------------------------------------------------------------------


class TestCloseEntitiesEnvelopeShape:
    def test_envelope_keys_exact_on_empty_input(self, project_dir):
        from lore.db import close_entities

        result = close_entities(project_dir, [])
        assert set(result.keys()) == {"updated", "quest_closed", "errors"}, (
            "Envelope keys must be EXACTLY {updated, quest_closed, errors} "
            f"(cli.py:570-578); got {sorted(result.keys())}"
        )
        assert result["updated"] == []
        assert result["quest_closed"] == []
        assert result["errors"] == []

    def test_envelope_keys_exact_on_single_mission_close(self, project_dir):
        from lore.db import close_entities

        insert_quest(project_dir, "q-bb01", "Q")
        insert_mission(
            project_dir,
            "q-bb01/m-1111",
            "q-bb01",
            "M",
            status="in_progress",
        )

        result = close_entities(project_dir, ["q-bb01/m-1111"])
        assert set(result.keys()) == {"updated", "quest_closed", "errors"}

    def test_quest_closed_entries_are_quest_ids_not_dicts(self, project_dir):
        """Per cli.py:569 — `quest_closed.append(result['quest_id'])` — plain id strings."""
        from lore.db import close_entities

        # auto_close so closing the last mission collapses quest.
        insert_quest(project_dir, "q-bb02", "Q", auto_close=1)
        insert_mission(
            project_dir,
            "q-bb02/m-1111",
            "q-bb02",
            "M",
            status="in_progress",
        )

        result = close_entities(project_dir, ["q-bb02/m-1111"])
        if result["quest_closed"]:
            assert all(isinstance(qid, str) for qid in result["quest_closed"]), (
                "`quest_closed` must be a list of quest-id strings (cli.py:569), "
                f"not dicts; got {result['quest_closed']!r}"
            )


# ---------------------------------------------------------------------------
# Mixed quest + mission IDs in one call
# ---------------------------------------------------------------------------


class TestCloseEntitiesMixedIds:
    def test_mix_of_quest_and_mission_ids_in_same_call(self, project_dir):
        from lore.db import close_entities

        insert_quest(project_dir, "q-bb10", "QA")
        insert_quest(project_dir, "q-bb11", "QB")
        insert_mission(
            project_dir,
            "q-bb11/m-1111",
            "q-bb11",
            "M",
            status="in_progress",
        )

        # Mix: bare quest ID and a quest-scoped mission id.
        result = close_entities(
            project_dir, ["q-bb10", "q-bb11/m-1111"]
        )

        assert "q-bb10" in result["updated"]
        assert "q-bb11/m-1111" in result["updated"]
        assert result["errors"] == []

    def test_quest_id_dispatch_recognises_bare_q_prefix(self, project_dir):
        """Same rule as cli._is_quest_id: starts with 'q-' AND has no '/'."""
        from lore.db import close_entities

        insert_quest(project_dir, "q-bb12", "Q")

        result = close_entities(project_dir, ["q-bb12"])
        assert "q-bb12" in result["updated"]


# ---------------------------------------------------------------------------
# Idempotency on already-closed entities
# ---------------------------------------------------------------------------


class TestCloseEntitiesIdempotency:
    def test_already_closed_mission_is_noop_success(self, project_dir):
        from lore.db import close_entities

        insert_quest(project_dir, "q-bb20", "Q")
        insert_mission(
            project_dir,
            "q-bb20/m-1111",
            "q-bb20",
            "M",
            status="closed",
            closed_at="2025-01-15T09:00:00Z",
        )

        result = close_entities(project_dir, ["q-bb20/m-1111"])
        assert result["errors"] == [], (
            "Already-closed mission is a no-op success — must NOT error"
        )

    def test_already_closed_quest_is_noop_success(self, project_dir):
        from lore.db import close_entities

        insert_quest(
            project_dir,
            "q-bb21",
            "Q",
            status="closed",
            closed_at="2025-01-15T09:00:00Z",
        )

        result = close_entities(project_dir, ["q-bb21"])
        assert result["errors"] == [], (
            "Already-closed quest is a no-op success — must NOT error"
        )


# ---------------------------------------------------------------------------
# Partial failure — successful ones persist
# ---------------------------------------------------------------------------


class TestCloseEntitiesPartialFailureNoRollback:
    def test_failing_entity_does_not_revert_prior_success(self, project_dir):
        from lore.db import close_entities, read_mission

        insert_quest(project_dir, "q-bb30", "Q")
        insert_mission(
            project_dir,
            "q-bb30/m-1111",
            "q-bb30",
            "Good",
            status="in_progress",
        )

        result = close_entities(
            project_dir, ["q-bb30/m-1111", "q-bb30/m-9999"]
        )

        assert "q-bb30/m-1111" in result["updated"]
        assert result["errors"], "Missing mission must surface in errors"

        m = read_mission(project_dir, "q-bb30/m-1111")
        status = getattr(m, "status", None) or (m["status"] if hasattr(m, "__getitem__") else None)
        assert status == "closed", (
            "Prior successful close must persist after later failure "
            f"(got {status!r})"
        )

    def test_invalid_mission_id_format_lands_in_errors(self, project_dir):
        from lore.db import close_entities

        insert_quest(project_dir, "q-bb31", "Q")
        insert_mission(
            project_dir,
            "q-bb31/m-1111",
            "q-bb31",
            "M",
            status="in_progress",
        )

        result = close_entities(
            project_dir, ["bogus", "q-bb31/m-1111"]
        )
        assert "q-bb31/m-1111" in result["updated"]
        assert result["errors"]


# ---------------------------------------------------------------------------
# Quest-status coalescing
# ---------------------------------------------------------------------------


class TestCloseEntitiesQuestStatusCoalescing:
    def test_derive_quest_status_called_once_per_quest_for_many_missions(
        self, project_dir, monkeypatch
    ):
        import lore.db as db_module

        insert_quest(project_dir, "q-bb40", "Q", auto_close=1)
        for mid in ("q-bb40/m-1111", "q-bb40/m-2222", "q-bb40/m-3333"):
            insert_mission(
                project_dir, mid, "q-bb40", "M", status="in_progress"
            )

        call_args: list[str] = []
        real = db_module._derive_quest_status

        def spy(conn, quest_id, now):
            call_args.append(quest_id)
            return real(conn, quest_id, now)

        monkeypatch.setattr(db_module, "_derive_quest_status", spy)

        db_module.close_entities(
            project_dir,
            ["q-bb40/m-1111", "q-bb40/m-2222", "q-bb40/m-3333"],
        )

        assert call_args.count("q-bb40") == 1, (
            "_derive_quest_status must be coalesced to 1 call for q-bb40 "
            f"across N closing missions (saw {call_args.count('q-bb40')}; "
            f"all calls = {call_args})"
        )


# ---------------------------------------------------------------------------
# Facade re-export — identity, not copy
# ---------------------------------------------------------------------------


def test_close_entities_reexported_from_lore_api():
    from lore import api, db

    assert hasattr(api, "close_entities"), (
        "G5: lore.api must re-export close_entities"
    )
    assert api.close_entities is db.close_entities
