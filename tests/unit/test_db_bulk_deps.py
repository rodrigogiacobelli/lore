"""Red tests for G5: `lore.db.add_dependencies` / `remove_dependencies` bulk ops.

Spec source:
  lore codex show transient-public-api-facade-plan      # §G5
  lore codex show transient-public-api-facade-tech-spec # §5

Envelopes (per cli.py:768-776 and cli.py:862-869, byte-exact):

  add_dependencies(project_root, pairs) -> dict
      {"created": [...], "existing": [...], "errors": [...]}
      `created` / `existing` entries: {"from": <id>, "to": <id>}
      Keys are EXACTLY "from"/"to" — NOT "from_id"/"to_id".

  remove_dependencies(project_root, pairs) -> dict
      {"removed": [...], "not_found": [...], "errors": [...]}
      `removed` / `not_found` entries: {"from": <id>, "to": <id>}.

Behaviour contract (per plan G5):
  * delegates to single-shot `add_dependency` / `remove_dependency` per pair
  * per-pair BEGIN IMMEDIATE preserved by wrapping single-shot
  * `_derive_quest_status` NEVER called from dep bulks (dependency changes
    do not affect quest status derivation)
  * one bad pair does NOT roll back prior successful pairs

These tests EXPECT the bulk fns to exist at `lore.db.add_dependencies` and
`lore.db.remove_dependencies`. They MUST fail until G5 Green lands the impl.
"""

from __future__ import annotations


from tests.conftest import insert_dependency, insert_mission, insert_quest


# ---------------------------------------------------------------------------
# Symbol existence
# ---------------------------------------------------------------------------


def test_add_dependencies_symbol_exists_on_lore_db():
    from lore import db

    assert hasattr(db, "add_dependencies"), (
        "G5: lore.db.add_dependencies not defined yet (Red phase expected)"
    )
    assert callable(db.add_dependencies)


def test_remove_dependencies_symbol_exists_on_lore_db():
    from lore import db

    assert hasattr(db, "remove_dependencies"), (
        "G5: lore.db.remove_dependencies not defined yet (Red phase expected)"
    )
    assert callable(db.remove_dependencies)


# ---------------------------------------------------------------------------
# add_dependencies envelope
# ---------------------------------------------------------------------------


class TestAddDependenciesEnvelopeShape:
    def test_envelope_keys_exact_on_empty_input(self, project_dir):
        from lore.db import add_dependencies

        result = add_dependencies(project_dir, [])
        assert set(result.keys()) == {"created", "existing", "errors"}, (
            "Envelope keys must be EXACTLY {created, existing, errors} "
            f"(cli.py:768-776); got {sorted(result.keys())}"
        )

    def test_envelope_keys_exact_on_single_create(self, project_dir):
        from lore.db import add_dependencies

        insert_quest(project_dir, "q-cc01", "Q")
        insert_mission(project_dir, "q-cc01/m-aaaa", "q-cc01", "A", status="open")
        insert_mission(project_dir, "q-cc01/m-bbbb", "q-cc01", "B", status="open")

        result = add_dependencies(
            project_dir,
            [("q-cc01/m-aaaa", "q-cc01/m-bbbb")],
        )
        assert set(result.keys()) == {"created", "existing", "errors"}

    def test_created_entry_uses_from_and_to_keys_not_from_id_to_id(self, project_dir):
        """Plan G5 emphasis: EXACT `from`/`to` keys — NOT `from_id`/`to_id`."""
        from lore.db import add_dependencies

        insert_quest(project_dir, "q-cc02", "Q")
        insert_mission(project_dir, "q-cc02/m-aaaa", "q-cc02", "A", status="open")
        insert_mission(project_dir, "q-cc02/m-bbbb", "q-cc02", "B", status="open")

        result = add_dependencies(
            project_dir,
            [("q-cc02/m-aaaa", "q-cc02/m-bbbb")],
        )

        assert result["created"], "Expected one created entry"
        entry = result["created"][0]
        assert set(entry.keys()) == {"from", "to"}, (
            "created entry keys must be EXACTLY {from, to} per cli.py:767; "
            f"got {sorted(entry.keys())}"
        )
        assert entry["from"] == "q-cc02/m-aaaa"
        assert entry["to"] == "q-cc02/m-bbbb"
        # Belt-and-braces: must NOT use the legacy/internal column names.
        assert "from_id" not in entry
        assert "to_id" not in entry

    def test_existing_entry_uses_from_and_to_keys(self, project_dir):
        from lore.db import add_dependencies

        insert_quest(project_dir, "q-cc03", "Q")
        insert_mission(project_dir, "q-cc03/m-aaaa", "q-cc03", "A", status="open")
        insert_mission(project_dir, "q-cc03/m-bbbb", "q-cc03", "B", status="open")
        insert_dependency(project_dir, "q-cc03/m-aaaa", "q-cc03/m-bbbb")

        result = add_dependencies(
            project_dir,
            [("q-cc03/m-aaaa", "q-cc03/m-bbbb")],
        )
        assert result["existing"], "Expected one existing entry (duplicate)"
        entry = result["existing"][0]
        assert set(entry.keys()) == {"from", "to"}, (
            "existing entry keys must be EXACTLY {from, to} per cli.py:765; "
            f"got {sorted(entry.keys())}"
        )
        assert "from_id" not in entry
        assert "to_id" not in entry


# ---------------------------------------------------------------------------
# add_dependencies — partial failure
# ---------------------------------------------------------------------------


class TestAddDependenciesPartialFailure:
    def test_bad_pair_does_not_block_good_pair(self, project_dir):
        from lore.db import add_dependencies

        insert_quest(project_dir, "q-cc10", "Q")
        insert_mission(project_dir, "q-cc10/m-aaaa", "q-cc10", "A", status="open")
        insert_mission(project_dir, "q-cc10/m-bbbb", "q-cc10", "B", status="open")

        result = add_dependencies(
            project_dir,
            [
                ("q-cc10/m-aaaa", "q-cc10/m-bbbb"),  # good
                ("q-cc10/m-aaaa", "q-cc10/m-ZZZZ"),  # bad — target missing
            ],
        )
        # First pair lands as created; second goes to errors.
        assert any(
            e == {"from": "q-cc10/m-aaaa", "to": "q-cc10/m-bbbb"}
            for e in result["created"]
        ), "Successful pair must persist into created"
        assert result["errors"], "Failing pair must surface in errors"


# ---------------------------------------------------------------------------
# add_dependencies — per-pair BEGIN IMMEDIATE preserved (wraps single-shot)
# ---------------------------------------------------------------------------


class TestAddDependenciesPerPairTransaction:
    def test_each_pair_dispatches_via_single_shot_add_dependency(
        self, project_dir, monkeypatch
    ):
        """Bulk MUST wrap `add_dependency` — not re-implement its SQL.

        Each pair gets its own BEGIN IMMEDIATE via single-shot. Spying the
        single-shot proves the wrap.
        """
        import lore.db as db_module

        insert_quest(project_dir, "q-cc20", "Q")
        for mid in (
            "q-cc20/m-aaaa",
            "q-cc20/m-bbbb",
            "q-cc20/m-cccc",
            "q-cc20/m-dddd",
        ):
            insert_mission(project_dir, mid, "q-cc20", "M", status="open")

        calls: list[tuple[str, str]] = []
        real = db_module.add_dependency

        def spy(project_root, from_id, to_id):
            calls.append((from_id, to_id))
            return real(project_root, from_id, to_id)

        monkeypatch.setattr(db_module, "add_dependency", spy)

        pairs = [
            ("q-cc20/m-aaaa", "q-cc20/m-bbbb"),
            ("q-cc20/m-cccc", "q-cc20/m-dddd"),
        ]
        db_module.add_dependencies(project_dir, pairs)

        assert calls == pairs, (
            "add_dependencies must dispatch single-shot add_dependency once per pair "
            "(preserves per-pair BEGIN IMMEDIATE). "
            f"Expected {pairs}, got {calls}"
        )


# ---------------------------------------------------------------------------
# add_dependencies — NO `_derive_quest_status` invocation
# ---------------------------------------------------------------------------


class TestAddDependenciesNoQuestStatusDerive:
    def test_derive_quest_status_never_called(
        self, project_dir, monkeypatch
    ):
        """Plan G5: dep bulks must NEVER recompute quest status."""
        import lore.db as db_module

        insert_quest(project_dir, "q-cc30", "Q")
        insert_mission(project_dir, "q-cc30/m-aaaa", "q-cc30", "A", status="open")
        insert_mission(project_dir, "q-cc30/m-bbbb", "q-cc30", "B", status="open")

        calls: list[str] = []
        real = db_module._derive_quest_status

        def spy(conn, quest_id, now):
            calls.append(quest_id)
            return real(conn, quest_id, now)

        monkeypatch.setattr(db_module, "_derive_quest_status", spy)

        db_module.add_dependencies(
            project_dir,
            [("q-cc30/m-aaaa", "q-cc30/m-bbbb")],
        )

        assert calls == [], (
            "Dep bulks must NEVER invoke _derive_quest_status "
            f"(saw calls for: {calls})"
        )


# ---------------------------------------------------------------------------
# remove_dependencies envelope
# ---------------------------------------------------------------------------


class TestRemoveDependenciesEnvelopeShape:
    def test_envelope_keys_exact_on_empty_input(self, project_dir):
        from lore.db import remove_dependencies

        result = remove_dependencies(project_dir, [])
        assert set(result.keys()) == {"removed", "not_found", "errors"}, (
            "Envelope keys must be EXACTLY {removed, not_found, errors} "
            f"(cli.py:862-869); got {sorted(result.keys())}"
        )

    def test_removed_entry_uses_from_and_to_keys(self, project_dir):
        from lore.db import remove_dependencies

        insert_quest(project_dir, "q-cc40", "Q")
        insert_mission(project_dir, "q-cc40/m-aaaa", "q-cc40", "A", status="open")
        insert_mission(project_dir, "q-cc40/m-bbbb", "q-cc40", "B", status="open")
        insert_dependency(project_dir, "q-cc40/m-aaaa", "q-cc40/m-bbbb")

        result = remove_dependencies(
            project_dir,
            [("q-cc40/m-aaaa", "q-cc40/m-bbbb")],
        )
        assert result["removed"], "Expected one removed entry"
        entry = result["removed"][0]
        assert set(entry.keys()) == {"from", "to"}, (
            "removed entry keys must be EXACTLY {from, to} per cli.py:855-856; "
            f"got {sorted(entry.keys())}"
        )
        assert entry["from"] == "q-cc40/m-aaaa"
        assert entry["to"] == "q-cc40/m-bbbb"
        assert "from_id" not in entry
        assert "to_id" not in entry

    def test_not_found_entry_uses_from_and_to_keys(self, project_dir):
        from lore.db import remove_dependencies

        insert_quest(project_dir, "q-cc41", "Q")
        insert_mission(project_dir, "q-cc41/m-aaaa", "q-cc41", "A", status="open")
        insert_mission(project_dir, "q-cc41/m-bbbb", "q-cc41", "B", status="open")
        # No dependency inserted — removal must report not_found.

        result = remove_dependencies(
            project_dir,
            [("q-cc41/m-aaaa", "q-cc41/m-bbbb")],
        )
        assert result["not_found"], "Expected one not_found entry"
        entry = result["not_found"][0]
        assert set(entry.keys()) == {"from", "to"}, (
            "not_found entry keys must be EXACTLY {from, to} per cli.py:858; "
            f"got {sorted(entry.keys())}"
        )
        assert "from_id" not in entry
        assert "to_id" not in entry


# ---------------------------------------------------------------------------
# remove_dependencies — partial failure isolation
# ---------------------------------------------------------------------------


class TestRemoveDependenciesPartialFailure:
    def test_one_failing_pair_does_not_revert_prior_remove(self, project_dir):
        from lore.db import remove_dependencies

        insert_quest(project_dir, "q-cc50", "Q")
        for mid in (
            "q-cc50/m-aaaa",
            "q-cc50/m-bbbb",
            "q-cc50/m-cccc",
        ):
            insert_mission(project_dir, mid, "q-cc50", "M", status="open")
        insert_dependency(project_dir, "q-cc50/m-aaaa", "q-cc50/m-bbbb")

        # Second pair is not active in DB → not_found, NOT an error,
        # and must not undo the first removal.
        result = remove_dependencies(
            project_dir,
            [
                ("q-cc50/m-aaaa", "q-cc50/m-bbbb"),
                ("q-cc50/m-aaaa", "q-cc50/m-cccc"),
            ],
        )
        assert any(
            e == {"from": "q-cc50/m-aaaa", "to": "q-cc50/m-bbbb"}
            for e in result["removed"]
        )
        assert any(
            e == {"from": "q-cc50/m-aaaa", "to": "q-cc50/m-cccc"}
            for e in result["not_found"]
        )


# ---------------------------------------------------------------------------
# remove_dependencies — per-pair single-shot dispatch
# ---------------------------------------------------------------------------


class TestRemoveDependenciesPerPairTransaction:
    def test_each_pair_dispatches_via_single_shot_remove_dependency(
        self, project_dir, monkeypatch
    ):
        import lore.db as db_module

        insert_quest(project_dir, "q-cc60", "Q")
        for mid in (
            "q-cc60/m-aaaa",
            "q-cc60/m-bbbb",
            "q-cc60/m-cccc",
            "q-cc60/m-dddd",
        ):
            insert_mission(project_dir, mid, "q-cc60", "M", status="open")
        insert_dependency(project_dir, "q-cc60/m-aaaa", "q-cc60/m-bbbb")
        insert_dependency(project_dir, "q-cc60/m-cccc", "q-cc60/m-dddd")

        calls: list[tuple[str, str]] = []
        real = db_module.remove_dependency

        def spy(project_root, from_id, to_id):
            calls.append((from_id, to_id))
            return real(project_root, from_id, to_id)

        monkeypatch.setattr(db_module, "remove_dependency", spy)

        pairs = [
            ("q-cc60/m-aaaa", "q-cc60/m-bbbb"),
            ("q-cc60/m-cccc", "q-cc60/m-dddd"),
        ]
        db_module.remove_dependencies(project_dir, pairs)

        assert calls == pairs, (
            "remove_dependencies must dispatch single-shot remove_dependency once per pair; "
            f"expected {pairs}, got {calls}"
        )


# ---------------------------------------------------------------------------
# remove_dependencies — NO quest-status derivation
# ---------------------------------------------------------------------------


class TestRemoveDependenciesNoQuestStatusDerive:
    def test_derive_quest_status_never_called(
        self, project_dir, monkeypatch
    ):
        import lore.db as db_module

        insert_quest(project_dir, "q-cc70", "Q")
        insert_mission(project_dir, "q-cc70/m-aaaa", "q-cc70", "A", status="open")
        insert_mission(project_dir, "q-cc70/m-bbbb", "q-cc70", "B", status="open")
        insert_dependency(project_dir, "q-cc70/m-aaaa", "q-cc70/m-bbbb")

        calls: list[str] = []
        real = db_module._derive_quest_status

        def spy(conn, quest_id, now):
            calls.append(quest_id)
            return real(conn, quest_id, now)

        monkeypatch.setattr(db_module, "_derive_quest_status", spy)

        db_module.remove_dependencies(
            project_dir,
            [("q-cc70/m-aaaa", "q-cc70/m-bbbb")],
        )

        assert calls == [], (
            "remove_dependencies must NEVER invoke _derive_quest_status "
            f"(saw calls for: {calls})"
        )


# ---------------------------------------------------------------------------
# Facade re-exports — identity, not copy
# ---------------------------------------------------------------------------


def test_add_dependencies_reexported_from_lore_api():
    from lore import api, db

    assert hasattr(api, "add_dependencies"), (
        "G5: lore.api must re-export add_dependencies"
    )
    assert api.add_dependencies is db.add_dependencies


def test_remove_dependencies_reexported_from_lore_api():
    from lore import api, db

    assert hasattr(api, "remove_dependencies"), (
        "G5: lore.api must re-export remove_dependencies"
    )
    assert api.remove_dependencies is db.remove_dependencies
