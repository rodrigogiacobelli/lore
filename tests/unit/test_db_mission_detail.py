"""Red tests for G6: `lore.db.get_mission_detail` envelope.

Spec source:
  lore codex show transient-public-api-facade-plan      # §G6
  lore codex show transient-public-api-facade-tech-spec # §3

Envelope (per cli.py:2030-2057, byte-exact). EXPLICIT key set (NOT superset):
  {
    "id", "quest_id", "title", "description", "status", "priority",
    "mission_type", "doctrine_mission", "doctrine_mission_contents",
    "block_reason",
    "created_at", "updated_at", "closed_at",
    "dependencies",     # {"needs": [...], "blocks": [...]}
    "board",            # [{"id","sender","message","created_at"}, ...]
  }

Review-Ledger CHANGED #3: NO `quest_deleted` key (text-mode-only at cli.py:2061).

Behaviour:
  * `get_mission_detail` returns None on miss.
  * `include_doctrine_mission=False` skips the read (contents=None).
  * An unresolvable reference → contents=None (no exception, no warning).
  * dependency entries are dicts with EXACTLY {id, title, status} per
    cli.py:2022-2028 (`_dep_to_json`).
  * board entries are dicts with EXACTLY {id, sender, message, created_at}.
  * standalone mission (quest_id=None) returns envelope with quest_id=None.

These tests EXPECT the symbol at `lore.db.get_mission_detail`. They MUST
fail until G6 Green lands the implementation. NO production code in this
chunk — Red phase only.
"""

from __future__ import annotations


from tests.conftest import insert_dependency, insert_mission, insert_quest, insert_board_message


MISSION_DETAIL_KEYS: frozenset[str] = frozenset(
    {
        "id",
        "quest_id",
        "title",
        "description",
        "status",
        "priority",
        "mission_type",
        "doctrine_mission",
        "doctrine_mission_contents",
        "block_reason",
        "created_at",
        "updated_at",
        "closed_at",
        "dependencies",
        "board",
    }
)

DEP_ENTRY_KEYS: frozenset[str] = frozenset({"id", "title", "status"})
BOARD_ENTRY_KEYS: frozenset[str] = frozenset({"id", "sender", "message", "created_at"})


# ---------------------------------------------------------------------------
# Symbol existence
# ---------------------------------------------------------------------------


def test_get_mission_detail_symbol_exists_on_lore_db():
    from lore import db

    assert hasattr(db, "get_mission_detail"), (
        "G6: lore.db.get_mission_detail not defined yet (Red phase expected)"
    )
    assert callable(db.get_mission_detail)


# ---------------------------------------------------------------------------
# Envelope shape — EXPLICIT key set
# ---------------------------------------------------------------------------


class TestMissionDetailEnvelopeShape:
    def test_envelope_keys_exact_for_quest_bound_mission(self, project_dir):
        from lore.db import get_mission_detail

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1111", "q-aaaa", "M")

        data = get_mission_detail(project_dir, "q-aaaa/m-1111")
        assert data is not None
        assert set(data.keys()) == MISSION_DETAIL_KEYS, (
            f"Mission-detail envelope MUST have EXACTLY "
            f"{sorted(MISSION_DETAIL_KEYS)}; got {sorted(data.keys())} "
            f"(extra: {set(data.keys()) - MISSION_DETAIL_KEYS}, "
            f"missing: {MISSION_DETAIL_KEYS - set(data.keys())})"
        )

    def test_envelope_has_no_quest_deleted_key(self, project_dir):
        """Review-Ledger CHANGED #3: `quest_deleted` is TEXT-mode-only."""
        from lore.db import get_mission_detail

        # Insert mission whose parent quest is soft-deleted.
        insert_quest(project_dir, "q-bbbb", "Q", deleted_at="2025-02-01T00:00:00Z")
        insert_mission(project_dir, "q-bbbb/m-2222", "q-bbbb", "M")

        data = get_mission_detail(project_dir, "q-bbbb/m-2222")
        assert data is not None
        assert "quest_deleted" not in data, (
            "Review-Ledger CHANGED #3: `quest_deleted` MUST NOT appear in JSON envelope"
        )

    def test_envelope_keys_exact_for_standalone_mission(self, project_dir):
        from lore.db import get_mission_detail

        insert_mission(project_dir, "m-3333", None, "Standalone")

        data = get_mission_detail(project_dir, "m-3333")
        assert data is not None
        assert set(data.keys()) == MISSION_DETAIL_KEYS
        assert data["quest_id"] is None


# ---------------------------------------------------------------------------
# Return None on miss
# ---------------------------------------------------------------------------


class TestMissionDetailMiss:
    def test_returns_none_for_unknown_mission(self, project_dir):
        from lore.db import get_mission_detail

        assert get_mission_detail(project_dir, "q-aaaa/m-9999") is None

    def test_returns_none_for_soft_deleted_mission(self, project_dir):
        from lore.db import get_mission_detail

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(
            project_dir, "q-aaaa/m-4444", "q-aaaa", "M",
            deleted_at="2025-02-01T00:00:00Z",
        )

        assert get_mission_detail(project_dir, "q-aaaa/m-4444") is None


# ---------------------------------------------------------------------------
# Field passthrough — values come from the row
# ---------------------------------------------------------------------------


class TestMissionDetailFieldPassthrough:
    def test_scalar_fields_match_row(self, project_dir):
        from lore.db import get_mission_detail

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(
            project_dir,
            "q-aaaa/m-5555",
            "q-aaaa",
            "Title text",
            status="blocked",
            priority=1,
            mission_type="agent",
            doctrine_mission=None,
            block_reason="waiting upstream",
        )

        data = get_mission_detail(project_dir, "q-aaaa/m-5555")
        assert data["id"] == "q-aaaa/m-5555"
        assert data["quest_id"] == "q-aaaa"
        assert data["title"] == "Title text"
        assert data["status"] == "blocked"
        assert data["priority"] == 1
        assert data["mission_type"] == "agent"
        assert data["doctrine_mission"] is None
        assert data["block_reason"] == "waiting upstream"

    def test_closed_at_passthrough(self, project_dir):
        from lore.db import get_mission_detail

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(
            project_dir, "q-aaaa/m-6666", "q-aaaa", "Done",
            status="closed", closed_at="2025-03-01T12:00:00Z",
        )

        data = get_mission_detail(project_dir, "q-aaaa/m-6666")
        assert data["closed_at"] == "2025-03-01T12:00:00Z"


# ---------------------------------------------------------------------------
# Doctrine mission contents — the include flag, resolution and the traversal guard
# ---------------------------------------------------------------------------


def _write_doctrine(project_dir, stem="tdd-lite", mission="recon", body="Do the recon.\n"):
    directory = project_dir / ".lore" / "doctrines" / stem
    (directory / "missions").mkdir(parents=True, exist_ok=True)
    (directory / f"{stem}.design.md").write_text(
        f"---\nid: {stem}\ntitle: {stem}\nsummary: A doctrine.\n---\n\nDesign.\n"
    )
    (directory / "missions" / f"{mission}.md").write_text(
        f"---\nid: {mission}\ntitle: {mission}\nsummary: A mission.\n---\n\n{body}"
    )
    return directory


class TestMissionDetailDoctrineMissionContents:
    def test_no_reference_yields_none_contents(self, project_dir):
        from lore.db import get_mission_detail

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-7777", "q-aaaa", "M", doctrine_mission=None)

        data = get_mission_detail(project_dir, "q-aaaa/m-7777")
        assert data["doctrine_mission_contents"] is None

    def test_a_resolving_reference_yields_the_stripped_body(self, project_dir):
        from lore.db import get_mission_detail

        _write_doctrine(project_dir)
        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(
            project_dir, "q-aaaa/m-7778", "q-aaaa", "M",
            doctrine_mission="tdd-lite/recon",
        )

        data = get_mission_detail(project_dir, "q-aaaa/m-7778")
        assert data["doctrine_mission"] == "tdd-lite/recon"
        assert data["doctrine_mission_contents"] == "Do the recon.\n"

    def test_include_false_skips_the_read_even_if_assigned(self, project_dir):
        """`include_doctrine_mission=False` MUST suppress the read entirely."""
        from lore.db import get_mission_detail

        _write_doctrine(project_dir)
        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(
            project_dir, "q-aaaa/m-8888", "q-aaaa", "M",
            doctrine_mission="tdd-lite/recon",
        )

        data = get_mission_detail(
            project_dir, "q-aaaa/m-8888", include_doctrine_mission=False
        )
        assert data["doctrine_mission"] == "tdd-lite/recon", (
            "the stored reference must still pass through"
        )
        assert data["doctrine_mission_contents"] is None

    def test_an_unresolvable_reference_yields_none_contents(self, project_dir):
        """An unresolvable reference is silent here — `lore health` is the reporter."""
        from lore.db import get_mission_detail

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(
            project_dir, "q-aaaa/m-9990", "q-aaaa", "M",
            doctrine_mission="gone/missing",
        )

        data = get_mission_detail(project_dir, "q-aaaa/m-9990")
        assert data is not None
        assert data["doctrine_mission"] == "gone/missing"
        assert data["doctrine_mission_contents"] is None

    def test_a_reference_with_a_traversal_segment_reads_nothing(self, project_dir):
        from lore.db import get_mission_detail

        (project_dir / "secret.md").write_text("top secret")
        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(
            project_dir, "q-aaaa/m-9991", "q-aaaa", "M",
            doctrine_mission="../../secret",
        )

        data = get_mission_detail(project_dir, "q-aaaa/m-9991")
        assert data["doctrine_mission_contents"] is None

    def test_the_envelope_carries_no_knight_key(self, project_dir):
        from lore.db import get_mission_detail

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-9992", "q-aaaa", "M")

        data = get_mission_detail(project_dir, "q-aaaa/m-9992")
        assert "knight" not in data
        assert "knight_contents" not in data


# ---------------------------------------------------------------------------
# Dependencies — needs / blocks sub-envelopes
# ---------------------------------------------------------------------------


class TestMissionDetailDependencies:
    def test_dependencies_keys_exact(self, project_dir):
        from lore.db import get_mission_detail

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1110", "q-aaaa", "M")

        data = get_mission_detail(project_dir, "q-aaaa/m-1110")
        assert set(data["dependencies"].keys()) == {"needs", "blocks"}, (
            f"dependencies MUST have EXACTLY {{needs, blocks}}; "
            f"got {sorted(data['dependencies'].keys())}"
        )
        assert data["dependencies"]["needs"] == []
        assert data["dependencies"]["blocks"] == []

    def test_needs_entry_shape_exact(self, project_dir):
        """Each dep entry has EXACTLY {id, title, status} (cli.py:2022-2028)."""
        from lore.db import get_mission_detail

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-1110", "q-aaaa", "Downstream")
        insert_mission(
            project_dir, "q-aaaa/m-1111", "q-aaaa", "Upstream", status="open",
        )
        # m-1110 needs m-1111
        insert_dependency(project_dir, "q-aaaa/m-1110", "q-aaaa/m-1111")

        data = get_mission_detail(project_dir, "q-aaaa/m-1110")
        needs = data["dependencies"]["needs"]
        assert len(needs) == 1
        entry = needs[0]
        assert set(entry.keys()) == DEP_ENTRY_KEYS, (
            f"needs entry keys MUST be EXACTLY {sorted(DEP_ENTRY_KEYS)}; "
            f"got {sorted(entry.keys())}"
        )
        assert entry["id"] == "q-aaaa/m-1111"
        assert entry["title"] == "Upstream"
        assert entry["status"] == "open"

    def test_blocks_entry_shape_exact(self, project_dir):
        from lore.db import get_mission_detail

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-2220", "q-aaaa", "Upstream")
        insert_mission(project_dir, "q-aaaa/m-2221", "q-aaaa", "Downstream")
        # downstream needs upstream → upstream blocks downstream
        insert_dependency(project_dir, "q-aaaa/m-2221", "q-aaaa/m-2220")

        data = get_mission_detail(project_dir, "q-aaaa/m-2220")
        blocks = data["dependencies"]["blocks"]
        assert len(blocks) == 1
        entry = blocks[0]
        assert set(entry.keys()) == DEP_ENTRY_KEYS
        assert entry["id"] == "q-aaaa/m-2221"

    def test_deleted_dep_renders_unknown_title_and_none_status(self, project_dir):
        """`_dep_to_json` semantics (cli.py:2022-2028) — deleted upstream surfaces
        as title=`[unknown]`, status=None.
        """
        from lore.db import get_mission_detail

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-3330", "q-aaaa", "Downstream")
        insert_mission(
            project_dir, "q-aaaa/m-3331", "q-aaaa", "Upstream",
            deleted_at="2025-02-01T00:00:00Z",
        )
        insert_dependency(project_dir, "q-aaaa/m-3330", "q-aaaa/m-3331")

        data = get_mission_detail(project_dir, "q-aaaa/m-3330")
        needs = data["dependencies"]["needs"]
        # The dep edge itself is not deleted, only the upstream mission row.
        # `_dep_to_json` checks dep.deleted_at — when upstream is missing/deleted,
        # the LEFT JOIN brings back a deleted_at marker on the dep row.
        assert len(needs) == 1
        entry = needs[0]
        assert entry["title"] == "[unknown]"
        assert entry["status"] is None


# ---------------------------------------------------------------------------
# Board — entry shape
# ---------------------------------------------------------------------------


class TestMissionDetailBoard:
    def test_board_empty_for_no_messages(self, project_dir):
        from lore.db import get_mission_detail

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-4440", "q-aaaa", "M")

        data = get_mission_detail(project_dir, "q-aaaa/m-4440")
        assert data["board"] == []

    def test_board_entry_keys_exact(self, project_dir):
        from lore.db import get_mission_detail

        insert_quest(project_dir, "q-aaaa", "Q")
        insert_mission(project_dir, "q-aaaa/m-5550", "q-aaaa", "M")
        insert_board_message(project_dir, "q-aaaa/m-5550", "hello", sender="alice")

        data = get_mission_detail(project_dir, "q-aaaa/m-5550")
        assert len(data["board"]) == 1
        entry = data["board"][0]
        assert set(entry.keys()) == BOARD_ENTRY_KEYS, (
            f"board entry MUST have EXACTLY {sorted(BOARD_ENTRY_KEYS)}; "
            f"got {sorted(entry.keys())}"
        )
        assert entry["sender"] == "alice"
        assert entry["message"] == "hello"
