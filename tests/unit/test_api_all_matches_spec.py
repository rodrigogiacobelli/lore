"""`lore.api.__all__` must equal Tech Spec §1 final list element-for-element.

Anchor: ``transient-public-api-facade-tech-spec`` §1 — "lore.api Module
Design". Spec §1's literal ``__all__`` block is the contract; the source
file MUST match its ordering AND membership, not just the set.

Earlier chunks (G1-G12) landed names additively in alphabetical order.
G13 is the "done gate" — flip ``__all__`` to the Spec §1 grouped order
so the public surface reads as documented.

Why ordering matters
--------------------
Spec §1 groups names by category (types/exceptions, project root,
validators, db quest CRUD, db mission CRUD, …). Ordering documents the
SHAPE of the API to humans reading ``api.py`` and ``help(lore.api)``.
Alphabetical order erases the categories; ADR-010 + Spec §1 explicitly
hand-list to preserve them.

Red today
---------
Current ``lore.api.__all__`` is alphabetical; Spec §1 is grouped. Element
-equal assertion fails on the FIRST mismatched index.

Source spec docs:
  lore codex show transient-public-api-facade-tech-spec   # §1
  lore codex show decisions-010-public-api-stability
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Spec §1 literal list — copied verbatim from the tech-spec ``__all__``
# block. Comments preserved as inline tags so a future re-order audit can
# trace each name back to its category.
# ---------------------------------------------------------------------------

SPEC_SECTION_1_ALL: tuple[str, ...] = (
    # types & enums
    "QuestStatus",
    "MissionStatus",
    "DependencyType",
    "Quest",
    "Mission",
    "Dependency",
    "BoardMessage",
    "Artifact",
    "CodexDocument",
    "DoctrineStep",
    "Doctrine",
    "Knight",
    "DoctrineListEntry",
    "GlossaryItem",
    "Watcher",
    "HealthIssue",
    "HealthReport",
    "SchemaIssue",
    "CodeBinding",
    "CodexBinding",
    "ImpactsError",
    "ImpactsResult",
    "GlossaryError",
    "ProjectNotFoundError",
    "ConflictingDepthFlags",
    "Config",
    # project root
    "find_project_root",
    # validators
    "validate_message",
    "validate_entity_id",
    "validate_mission_id",
    "validate_priority",
    "validate_name",
    "validate_group",
    "validate_quest_id_loose",
    "validate_chaos_threshold",
    "validate_binds_entry",
    "is_glob_pattern",
    "route_entity",
    # db: quest CRUD (G17 — get_quest/edit_quest renamed)
    "create_quest",
    "list_quests",
    "read_quest",
    "update_quest",
    "update_quest_full",
    "delete_quest",
    "close_quest",
    # db: mission CRUD (G17 — get_mission/edit_mission renamed)
    "create_mission",
    "list_missions",
    "list_missions_grouped",
    "read_mission",
    "update_mission",
    "update_mission_full",
    "delete_mission",
    # db: status transitions
    "claim_mission",
    "claim_missions",
    "close_mission",
    "close_entities",
    "block_mission",
    "unblock_mission",
    # db: dependencies (G17 — _details renamed; str-list variants dropped)
    "add_dependency",
    "remove_dependency",
    "add_dependencies",
    "remove_dependencies",
    "list_mission_depends_on",
    "list_mission_blocks",
    "get_all_dependencies_for_quest",
    # db: board (G17 — get_board_messages renamed)
    "add_board_message",
    "list_board_messages",
    "delete_board_message",
    # db: dashboard / stats / soft-delete
    "get_dashboard_quests",
    "get_aggregate_stats",
    "get_deleted_at",
    "get_missions_for_quest",
    # db: envelopes
    "get_mission_detail",
    "get_quest_detail",
    "delete_entity",
    "get_connection",
    "init_database",
    # priority
    "get_ready_missions",
    # knight (G16 — find_knight reclassified internal)
    "list_knights",
    "read_knight",
    "create_knight",
    "update_knight",
    "delete_knight",
    # doctrine (G16 — show_doctrine renamed to read_doctrine)
    "list_doctrines",
    "read_doctrine",
    "create_doctrine",
    "update_doctrine",
    "delete_doctrine",
    # artifact (G16 — scan_artifacts renamed to list_artifacts)
    "list_artifacts",
    "read_artifact",
    "create_artifact",
    "update_artifact",
    "delete_artifact",
    # watcher (G16 — find_watcher/load_watcher reclassified internal)
    "list_watchers",
    "read_watcher",
    "create_watcher",
    "update_watcher",
    "delete_watcher",
    # frontmatter field-edit (cross-entity)
    "update_frontmatter_fields",
    # codex (G16 — scan_codex renamed to list_codex)
    "list_codex",
    "search_documents",
    "read_document",
    "read_documents_with_glossary",
    "map_documents",
    "chaos_documents",
    "create_document",
    "update_document",
    "delete_document",
    # glossary
    "scan_glossary",
    "read_glossary_item",
    "search_glossary",
    "match_glossary",
    "create_glossary_item",
    "update_glossary_item",
    "delete_glossary_item",
    # impacts
    "impacts",
    "classify_token",
    # health
    "health_check",
    # schemas
    "load_schema",
    "validate_entity",
    "validate_entity_file",
    "resolve_merged_schema",
    "project_validator_for",
    "OverlayError",
    # init / reports / config
    "run_init",
    "generate_reports",
    "load_config",
    # paths (G15 — amendment C1)
    "entity_location",
    # rite (US-007 — functions + types + validator)
    "scan_rites",
    "read_rite",
    "search_rites",
    "create_rite",
    "update_rite",
    "delete_rite",
    "Rite",
    "RiteNode",
    "RiteBranch",
    "RiteConclusion",
    "SharedStep",
    "RiteError",
    "validate_rite_id",
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestApiAllMatchesSpecSection1:
    """``lore.api.__all__`` equals Spec §1 list element-for-element."""

    def test_api_all_length_matches_spec(self):
        from lore import api

        assert len(api.__all__) == len(SPEC_SECTION_1_ALL), (
            f"len(lore.api.__all__) = {len(api.__all__)}; "
            f"Spec §1 has {len(SPEC_SECTION_1_ALL)} names."
        )

    def test_api_all_membership_matches_spec(self):
        """Set-equality — every Spec §1 name present, no extras."""
        from lore import api

        actual = set(api.__all__)
        expected = set(SPEC_SECTION_1_ALL)
        assert actual == expected, (
            f"Missing from lore.api.__all__: {sorted(expected - actual)}; "
            f"Unexpected in lore.api.__all__: {sorted(actual - expected)}"
        )

    def test_api_all_ordering_matches_spec_exactly(self):
        """List-equality — names appear in Spec §1 order, not alphabetical.

        Pinpoints the first index where ordering diverges so the Green-phase
        author can see exactly where to re-shuffle the source-of-truth.
        """
        from lore import api

        actual = list(api.__all__)
        expected = list(SPEC_SECTION_1_ALL)

        first_mismatch: int | None = None
        for i, (a, e) in enumerate(zip(actual, expected)):
            if a != e:
                first_mismatch = i
                break
        assert actual == expected, (
            "lore.api.__all__ does not match Spec §1 ordering.\n"
            f"First mismatch at index {first_mismatch}: "
            f"got {actual[first_mismatch] if first_mismatch is not None else '?'!r}, "
            f"expected {expected[first_mismatch] if first_mismatch is not None else '?'!r}.\n"
            "Spec §1 groups names by category (types, validators, db: quest CRUD, …); "
            "alphabetical order is rejected."
        )

    def test_api_all_has_no_duplicates(self):
        """Sanity — no duplicates would let a category be split silently."""
        from lore import api

        assert len(api.__all__) == len(set(api.__all__)), (
            "__all__ must not contain duplicates"
        )
