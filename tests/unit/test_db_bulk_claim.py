"""Red tests for G5: `lore.db.claim_missions` bulk op.

Spec source:
  lore codex show transient-public-api-facade-plan      # §G5
  lore codex show transient-public-api-facade-tech-spec # §5

Envelope (per cli.py:495-503, byte-exact):
  {"updated": [...], "quest_status_changed": [...], "errors": [...]}

Each `quest_status_changed` entry: `{"id": <quest_id>, "status": <new_status>}`.

Behaviour contract (per plan G5):
  * wraps existing single-shot `claim_mission` — never re-implements its logic
  * per-mission idempotency: already in_progress → no-op success (no error)
  * one failing mission does NOT roll back successful ones in the same call
  * `_derive_quest_status` invoked at most ONCE per affected quest (coalesce)
  * per-mission BEGIN IMMEDIATE preserved by wrapping single-shot

These tests EXPECT the bulk fn to exist at `lore.db.claim_missions`. They
MUST fail until G5 Green lands the implementation.
"""

from __future__ import annotations


# Re-use shared DB-row inserter helpers from the package-level conftest.
from tests.conftest import insert_mission, insert_quest


# ---------------------------------------------------------------------------
# Import-level guard — the symbol must exist or every test fails loudly.
# ---------------------------------------------------------------------------


def test_claim_missions_symbol_exists_on_lore_db():
    """`lore.db.claim_missions` exists as a top-level callable."""
    from lore import db

    assert hasattr(db, "claim_missions"), (
        "G5: lore.db.claim_missions not defined yet (Red phase expected)"
    )
    assert callable(db.claim_missions), "claim_missions must be callable"


# ---------------------------------------------------------------------------
# Envelope shape — keys EXACTLY {updated, quest_status_changed, errors}
# ---------------------------------------------------------------------------


class TestClaimMissionsEnvelopeShape:
    """Return value matches cli.py:495-503 dict-literal verbatim."""

    def test_envelope_keys_exact_on_empty_input(self, project_dir):
        from lore.db import claim_missions

        result = claim_missions(project_dir, [])
        assert set(result.keys()) == {"updated", "quest_status_changed", "errors"}, (
            "Envelope keys must be EXACTLY {updated, quest_status_changed, errors} "
            f"(cli.py:495-503); got {sorted(result.keys())}"
        )
        assert result["updated"] == []
        assert result["quest_status_changed"] == []
        assert result["errors"] == []

    def test_envelope_keys_exact_on_single_success(self, project_dir):
        from lore.db import claim_missions

        insert_quest(project_dir, "q-aa01", "Q")
        insert_mission(project_dir, "q-aa01/m-1111", "q-aa01", "M1", status="open")

        result = claim_missions(project_dir, ["q-aa01/m-1111"])
        assert set(result.keys()) == {"updated", "quest_status_changed", "errors"}

    def test_quest_status_changed_entry_shape_id_and_status(self, project_dir):
        """Each `quest_status_changed` entry has EXACTLY keys {id, status}."""
        from lore.db import claim_missions

        insert_quest(project_dir, "q-aa02", "Q", status="open")
        insert_mission(project_dir, "q-aa02/m-1111", "q-aa02", "M", status="open")

        result = claim_missions(project_dir, ["q-aa02/m-1111"])
        if result["quest_status_changed"]:
            entry = result["quest_status_changed"][0]
            assert set(entry.keys()) == {"id", "status"}, (
                "quest_status_changed entry keys must be EXACTLY {id, status} "
                "per cli.py:493; got " + str(sorted(entry.keys()))
            )
            assert entry["id"] == "q-aa02"
            assert isinstance(entry["status"], str)


# ---------------------------------------------------------------------------
# Updated list contains the claimed mission IDs (in input order)
# ---------------------------------------------------------------------------


class TestClaimMissionsUpdatesList:
    def test_single_open_mission_lands_in_updated(self, project_dir):
        from lore.db import claim_missions

        insert_quest(project_dir, "q-aa10", "Q")
        insert_mission(project_dir, "q-aa10/m-1111", "q-aa10", "M", status="open")

        result = claim_missions(project_dir, ["q-aa10/m-1111"])
        assert result["updated"] == ["q-aa10/m-1111"]
        assert result["errors"] == []

    def test_multiple_open_missions_all_land_in_updated(self, project_dir):
        from lore.db import claim_missions

        insert_quest(project_dir, "q-aa11", "Q")
        for mid in ("q-aa11/m-1111", "q-aa11/m-2222", "q-aa11/m-3333"):
            insert_mission(project_dir, mid, "q-aa11", "M", status="open")

        result = claim_missions(
            project_dir,
            ["q-aa11/m-1111", "q-aa11/m-2222", "q-aa11/m-3333"],
        )
        assert set(result["updated"]) == {
            "q-aa11/m-1111",
            "q-aa11/m-2222",
            "q-aa11/m-3333",
        }
        assert result["errors"] == []


# ---------------------------------------------------------------------------
# Per-mission idempotency: already in_progress → success, NO error
# ---------------------------------------------------------------------------


class TestClaimMissionsIdempotency:
    def test_already_in_progress_is_noop_success(self, project_dir):
        from lore.db import claim_missions

        insert_quest(project_dir, "q-aa20", "Q")
        insert_mission(
            project_dir,
            "q-aa20/m-1111",
            "q-aa20",
            "M",
            status="in_progress",
        )

        result = claim_missions(project_dir, ["q-aa20/m-1111"])
        # Mirrors single-shot claim_mission: idempotent → ok=True, no error.
        # Bulk surfaces same as "no error", no echo into errors list.
        assert result["errors"] == [], (
            "Already in_progress is a no-op success — must NOT appear in errors"
        )

    def test_mixed_already_in_progress_and_open(self, project_dir):
        from lore.db import claim_missions

        insert_quest(project_dir, "q-aa21", "Q")
        insert_mission(
            project_dir, "q-aa21/m-1111", "q-aa21", "A", status="in_progress"
        )
        insert_mission(
            project_dir, "q-aa21/m-2222", "q-aa21", "B", status="open"
        )

        result = claim_missions(
            project_dir, ["q-aa21/m-1111", "q-aa21/m-2222"]
        )
        assert result["errors"] == []
        # Both should be treated as ok; updated includes at minimum the open one
        # that transitioned. Idempotent already-claimed pattern matches cli
        # behaviour where success path appends to `updated`.
        assert "q-aa21/m-2222" in result["updated"]


# ---------------------------------------------------------------------------
# Partial failure: one bad mission does NOT roll back successful ones
# ---------------------------------------------------------------------------


class TestClaimMissionsPartialFailureNoRollback:
    def test_failing_mission_does_not_revert_prior_success(self, project_dir):
        from lore.db import claim_missions, read_mission

        insert_quest(project_dir, "q-aa30", "Q")
        insert_mission(project_dir, "q-aa30/m-1111", "q-aa30", "Good", status="open")
        # Second one does NOT exist — must produce an error, not undo first.

        result = claim_missions(
            project_dir, ["q-aa30/m-1111", "q-aa30/m-9999"]
        )

        assert "q-aa30/m-1111" in result["updated"], (
            "Successful claim must persist even when a later one fails"
        )
        assert result["errors"], "Missing mission must surface in errors list"

        # Persistence check: the successful one is actually in_progress in DB.
        m = read_mission(project_dir, "q-aa30/m-1111")
        assert m is not None
        # Tolerate either model attr or dict-like access.
        status = getattr(m, "status", None) or (m["status"] if hasattr(m, "__getitem__") else None)
        assert status == "in_progress", (
            "Successful mission must remain in_progress after partial failure "
            f"(got {status!r})"
        )

    def test_invalid_mission_id_format_lands_in_errors_only(self, project_dir):
        from lore.db import claim_missions

        insert_quest(project_dir, "q-aa31", "Q")
        insert_mission(project_dir, "q-aa31/m-1111", "q-aa31", "M", status="open")

        result = claim_missions(
            project_dir, ["not-a-mission-id", "q-aa31/m-1111"]
        )
        assert "q-aa31/m-1111" in result["updated"]
        assert result["errors"], "Bad ID format must record an error"


# ---------------------------------------------------------------------------
# `_derive_quest_status` coalescing: at most ONE call per affected quest
# ---------------------------------------------------------------------------


class TestClaimMissionsQuestStatusCoalescing:
    """Plan G5: `_derive_quest_status` runs at most once per affected quest.

    The single-shot `claim_mission` calls it per mission. The bulk fn MUST
    coalesce so a quest with N transitions still recomputes only once.
    """

    def test_derive_quest_status_called_at_most_once_per_quest(
        self, project_dir, monkeypatch
    ):
        import lore.db as db_module

        insert_quest(project_dir, "q-aa40", "Q")
        for mid in ("q-aa40/m-1111", "q-aa40/m-2222", "q-aa40/m-3333"):
            insert_mission(project_dir, mid, "q-aa40", "M", status="open")

        call_args: list[str] = []
        real = db_module._derive_quest_status

        def spy(conn, quest_id, now):
            call_args.append(quest_id)
            return real(conn, quest_id, now)

        monkeypatch.setattr(db_module, "_derive_quest_status", spy)

        db_module.claim_missions(
            project_dir,
            ["q-aa40/m-1111", "q-aa40/m-2222", "q-aa40/m-3333"],
        )

        # All three missions share quest q-aa40. Coalesce → 1 invocation.
        assert call_args.count("q-aa40") == 1, (
            f"_derive_quest_status must be coalesced to 1 call per quest "
            f"(saw {call_args.count('q-aa40')} for q-aa40; all calls = {call_args})"
        )

    def test_derive_quest_status_called_once_per_distinct_quest(
        self, project_dir, monkeypatch
    ):
        import lore.db as db_module

        insert_quest(project_dir, "q-aa41", "QA")
        insert_quest(project_dir, "q-aa42", "QB")
        insert_mission(project_dir, "q-aa41/m-1111", "q-aa41", "M", status="open")
        insert_mission(project_dir, "q-aa41/m-2222", "q-aa41", "M", status="open")
        insert_mission(project_dir, "q-aa42/m-1111", "q-aa42", "M", status="open")

        call_args: list[str] = []
        real = db_module._derive_quest_status

        def spy(conn, quest_id, now):
            call_args.append(quest_id)
            return real(conn, quest_id, now)

        monkeypatch.setattr(db_module, "_derive_quest_status", spy)

        db_module.claim_missions(
            project_dir,
            ["q-aa41/m-1111", "q-aa41/m-2222", "q-aa42/m-1111"],
        )

        assert call_args.count("q-aa41") == 1
        assert call_args.count("q-aa42") == 1


# ---------------------------------------------------------------------------
# Facade re-export — identity, not copy
# ---------------------------------------------------------------------------


def test_claim_missions_reexported_from_lore_api():
    """Plan G5 acceptance: `lore.api.claim_missions is lore.db.claim_missions`."""
    from lore import api, db

    assert hasattr(api, "claim_missions"), (
        "G5: lore.api must re-export claim_missions"
    )
    assert api.claim_missions is db.claim_missions, (
        "lore.api.claim_missions must be IDENTITY re-export of lore.db.claim_missions"
    )
