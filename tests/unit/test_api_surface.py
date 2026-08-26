"""Tests for lore.api facade scaffold (G1 chunk).

Pin Spec §1 facade module shape: pure re-export, literal `__all__`,
zero `def`/`class` in body, docstring ref ADR-010, identity (not copy)
of every re-export.

G1 slice = names that EXIST TODAY only. Bulk ops, `*_full`, `*_detail`,
new CRUD parity names (update_knight, delete_artifact, etc.) land in
later chunks per `transient-public-api-facade-plan`.

Source spec docs:
  lore codex show transient-public-api-facade-tech-spec
  lore codex show transient-public-api-facade-plan
  lore codex show decisions-010-public-api-stability
  lore codex show decisions-011-api-parity-with-cli
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Expected `__all__` slice — G1 baseline + G5 bulk-op additions.
# Authoritative source of truth; later chunks (G6-G17) extend additively.
# ---------------------------------------------------------------------------

G6_NEW_NAMES: tuple[str, ...] = (
    # G6: lore.db envelope-assembling functions per Tech Spec §3 + §2.
    # G17 RENAMES `edit_*_full` to `update_*_full` per amendment Section B.
    # Each replaces a CLI hand-rolled stitch (Review-Ledger CHANGED #2 + #3
    # lock the envelope keys down — see test_db_*_detail / *_full /
    # delete_entity / list_missions_grouped suites).
    "get_mission_detail",
    "get_quest_detail",
    "list_missions_grouped",
    "update_quest_full",
    "update_mission_full",
    "delete_entity",
)


G1_EXPECTED_ALL: tuple[str, ...] = (
    # types & enums (lore.models)
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
    # operational dataclasses — initialisation (interactive-init-us-023)
    "AccessMode",
    "FileAction",
    "AgentTarget",
    "PlannedFile",
    "InitAnswers",
    "InitPlan",
    "InitResult",
    # exceptions
    "GlossaryError",
    "ProjectNotFoundError",
    "ConflictingDepthFlags",
    # config type
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
    # validators — initialisation (interactive-init-us-017)
    "validate_access_mode",
    "validate_skill_family",
    "validate_agent_id",
    "validate_agent_selection",
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
    # db: G6 envelopes (Tech Spec §3 + §2)
    "get_mission_detail",
    "get_quest_detail",
    "delete_entity",
    # db: status transitions (single-shot + G5 bulks)
    "claim_mission",
    "claim_missions",
    "close_mission",
    "close_entities",
    "block_mission",
    "unblock_mission",
    # db: dependencies (G17 — _details renamed to list_*, str-list variants dropped)
    "add_dependency",
    "add_dependencies",
    "remove_dependency",
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
    # db: low-level connection / migration
    "get_connection",
    "init_database",
    # priority
    "get_ready_missions",
    # knight (G16 — find_knight reclassified internal; read_knight is dict)
    "list_knights",
    "create_knight",
    "read_knight",
    "update_knight",
    "delete_knight",
    # doctrine (G16 — show_doctrine renamed to read_doctrine; None-on-miss)
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
    # watcher (G16 — find_watcher/load_watcher reclassified internal; read_watcher added)
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
    "plan_init",
    "apply_init",
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
# (name, source-module) pairs for identity checks.
# Identity (`api.X is module.X`) — not value-equal — proves re-export
# is `from X import Y` style and not a wrapper.
# ---------------------------------------------------------------------------

G1_IDENTITY_SOURCES: dict[str, str] = {
    # types & enums
    "QuestStatus": "lore.models",
    "MissionStatus": "lore.models",
    "DependencyType": "lore.models",
    "Quest": "lore.models",
    "Mission": "lore.models",
    "Dependency": "lore.models",
    "BoardMessage": "lore.models",
    "Artifact": "lore.models",
    "CodexDocument": "lore.models",
    "DoctrineStep": "lore.models",
    "Doctrine": "lore.models",
    "Knight": "lore.models",
    "DoctrineListEntry": "lore.models",
    "GlossaryItem": "lore.models",
    "Watcher": "lore.models",
    "HealthIssue": "lore.health",
    "HealthReport": "lore.health",
    "SchemaIssue": "lore.schemas",
    "CodeBinding": "lore.impacts",
    "CodexBinding": "lore.impacts",
    "ImpactsError": "lore.impacts",
    "ImpactsResult": "lore.impacts",
    # operational dataclasses — initialisation (interactive-init-us-023)
    "AccessMode": "lore.initplan",
    "FileAction": "lore.initplan",
    "AgentTarget": "lore.initplan",
    "PlannedFile": "lore.initplan",
    "InitAnswers": "lore.initplan",
    "InitPlan": "lore.initplan",
    "InitResult": "lore.initplan",
    # exceptions
    "GlossaryError": "lore.glossary",
    "ProjectNotFoundError": "lore.root",
    "ConflictingDepthFlags": "lore.codex",
    # config
    "Config": "lore.config",
    # project root
    "find_project_root": "lore.root",
    # validators
    "validate_message": "lore.validators",
    "validate_entity_id": "lore.validators",
    "validate_mission_id": "lore.validators",
    "validate_priority": "lore.validators",
    "validate_name": "lore.validators",
    "validate_group": "lore.validators",
    "validate_quest_id_loose": "lore.validators",
    "validate_chaos_threshold": "lore.validators",
    "validate_binds_entry": "lore.validators",
    "is_glob_pattern": "lore.validators",
    "route_entity": "lore.validators",
    "validate_access_mode": "lore.validators",
    "validate_skill_family": "lore.validators",
    "validate_agent_id": "lore.validators",
    "validate_agent_selection": "lore.validators",
    # db (G17 — get_*/edit_* renamed to read_*/update_*; *_details to list_*)
    "create_quest": "lore.db",
    "list_quests": "lore.db",
    "read_quest": "lore.db",
    "update_quest": "lore.db",
    "update_quest_full": "lore.db",
    "delete_quest": "lore.db",
    "close_quest": "lore.db",
    "create_mission": "lore.db",
    "list_missions": "lore.db",
    "list_missions_grouped": "lore.db",
    "read_mission": "lore.db",
    "update_mission": "lore.db",
    "update_mission_full": "lore.db",
    "delete_mission": "lore.db",
    # G6 envelopes (retained)
    "get_mission_detail": "lore.db",
    "get_quest_detail": "lore.db",
    "delete_entity": "lore.db",
    "claim_mission": "lore.db",
    "claim_missions": "lore.db",
    "close_mission": "lore.db",
    "close_entities": "lore.db",
    "block_mission": "lore.db",
    "unblock_mission": "lore.db",
    "add_dependency": "lore.db",
    "add_dependencies": "lore.db",
    "remove_dependency": "lore.db",
    "remove_dependencies": "lore.db",
    "list_mission_depends_on": "lore.db",
    "list_mission_blocks": "lore.db",
    "get_all_dependencies_for_quest": "lore.db",
    "add_board_message": "lore.db",
    "list_board_messages": "lore.db",
    "delete_board_message": "lore.db",
    "get_dashboard_quests": "lore.db",
    "get_aggregate_stats": "lore.db",
    "get_deleted_at": "lore.db",
    "get_missions_for_quest": "lore.db",
    "get_connection": "lore.db",
    "init_database": "lore.db",
    # priority
    "get_ready_missions": "lore.priority",
    # knight
    "list_knights": "lore.knight",
    "create_knight": "lore.knight",
    "read_knight": "lore.knight",
    "update_knight": "lore.knight",
    "delete_knight": "lore.knight",
    # doctrine
    "list_doctrines": "lore.doctrine",
    "read_doctrine": "lore.doctrine",
    "create_doctrine": "lore.doctrine",
    "update_doctrine": "lore.doctrine",
    "delete_doctrine": "lore.doctrine",
    # artifact
    "list_artifacts": "lore.artifact",
    "read_artifact": "lore.artifact",
    "create_artifact": "lore.artifact",
    "update_artifact": "lore.artifact",
    "delete_artifact": "lore.artifact",
    # watcher
    "list_watchers": "lore.watcher",
    "read_watcher": "lore.watcher",
    "create_watcher": "lore.watcher",
    "update_watcher": "lore.watcher",
    "delete_watcher": "lore.watcher",
    # frontmatter field-edit
    "update_frontmatter_fields": "lore.frontmatter_edit",
    # codex
    "list_codex": "lore.codex",
    "search_documents": "lore.codex",
    "read_document": "lore.codex",
    "read_documents_with_glossary": "lore.codex",
    "map_documents": "lore.codex",
    "chaos_documents": "lore.codex",
    "create_document": "lore.codex",
    "update_document": "lore.codex",
    "delete_document": "lore.codex",
    # glossary
    "scan_glossary": "lore.glossary",
    "read_glossary_item": "lore.glossary",
    "search_glossary": "lore.glossary",
    "match_glossary": "lore.glossary",
    "create_glossary_item": "lore.glossary",
    "update_glossary_item": "lore.glossary",
    "delete_glossary_item": "lore.glossary",
    # impacts
    "impacts": "lore.impacts",
    "classify_token": "lore.impacts",
    # health
    "health_check": "lore.health",
    # schemas
    "load_schema": "lore.schemas",
    "validate_entity": "lore.schemas",
    "validate_entity_file": "lore.schemas",
    "resolve_merged_schema": "lore.schemas",
    "project_validator_for": "lore.schemas",
    "OverlayError": "lore.schemas",
    # init / oracle / config
    "run_init": "lore.init",
    "plan_init": "lore.init",
    "apply_init": "lore.init",
    "generate_reports": "lore.oracle",
    "load_config": "lore.config",
    # paths (G15 — amendment C1)
    "entity_location": "lore.paths",
    # rite (US-007)
    "scan_rites": "lore.rite",
    "read_rite": "lore.rite",
    "search_rites": "lore.rite",
    "create_rite": "lore.rite",
    "update_rite": "lore.rite",
    "delete_rite": "lore.rite",
    "Rite": "lore.models",
    "RiteNode": "lore.models",
    "RiteBranch": "lore.models",
    "RiteConclusion": "lore.models",
    "SharedStep": "lore.models",
    "RiteError": "lore.models",
    "validate_rite_id": "lore.validators",
}


API_MODULE_PATH = Path(__file__).resolve().parents[2] / "src" / "lore" / "api.py"


# ---------------------------------------------------------------------------
# Import + docstring
# ---------------------------------------------------------------------------


class TestApiModuleImport:
    """`from lore import api` succeeds and module docstring anchors ADR-010."""

    def test_api_module_importable(self):
        from lore import api  # noqa: F401

    def test_api_module_has_docstring(self):
        from lore import api

        assert api.__doc__, "lore.api must have a module docstring"

    def test_api_docstring_references_adr_010(self):
        from lore import api

        assert "ADR-010" in (api.__doc__ or ""), (
            "Docstring must anchor to ADR-010 (public-api-stability)"
        )

    def test_api_docstring_warns_about_internal_imports(self):
        """Docstring must flag that any `lore.<X>` direct import is a consumer bug."""
        from lore import api

        doc = (api.__doc__ or "").lower()
        # Spec §1 skeleton: 'Consumers ... import exclusively from `lore.api`'
        # OR an explicit 'internal' warning. Accept either phrasing.
        assert "internal" in doc or "exclusively" in doc, (
            "Docstring must warn that submodules are internal / consumers import "
            "exclusively from lore.api"
        )


# ---------------------------------------------------------------------------
# __all__ membership matches G1 slice exactly
# ---------------------------------------------------------------------------


class TestApiAllSlice:
    """`__all__` exposes exactly the G1 slice — no more, no less."""

    def test_api_has_dunder_all(self):
        from lore import api

        assert hasattr(api, "__all__"), "lore.api must define __all__"

    def test_api_all_is_list_or_tuple(self):
        from lore import api

        assert isinstance(api.__all__, (list, tuple))

    def test_api_all_matches_g1_slice_exactly(self):
        from lore import api

        assert set(api.__all__) == set(G1_EXPECTED_ALL), (
            f"Missing: {set(G1_EXPECTED_ALL) - set(api.__all__)}; "
            f"Unexpected: {set(api.__all__) - set(G1_EXPECTED_ALL)}"
        )

    def test_api_all_has_no_duplicates(self):
        from lore import api

        assert len(api.__all__) == len(set(api.__all__)), (
            "__all__ must not contain duplicates"
        )

    def test_api_all_excludes_future_chunk_names(self):
        """Names landing in later chunks (G12-G17) must NOT appear yet.

        G11 landed `read_documents_with_glossary` — no longer in this set.
        """
        from lore import api

        future_names: set[str] = set()
        leaked = future_names & set(api.__all__)
        assert not leaked, f"Names from future chunks leaked into G1 __all__: {leaked}"


# ---------------------------------------------------------------------------
# Every name in __all__ importable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", G1_EXPECTED_ALL)
def test_g1_name_is_importable_from_api(name: str):
    """Each G1 name resolvable as `from lore.api import <name>`."""
    from lore import api

    assert hasattr(api, name), f"lore.api missing expected name: {name}"
    obj = getattr(api, name)
    assert obj is not None, f"lore.api.{name} resolved to None"


# ---------------------------------------------------------------------------
# Identity (not copy) — `api.X is module.X`
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,source_module", sorted(G1_IDENTITY_SOURCES.items()))
def test_g1_name_is_identity_reexport(name: str, source_module: str):
    """`lore.api.<name> is lore.<src>.<name>` — re-export, not wrapper."""
    import importlib

    from lore import api

    src = importlib.import_module(source_module)
    api_obj = getattr(api, name)
    src_obj = getattr(src, name)
    assert api_obj is src_obj, (
        f"lore.api.{name} must be identity re-export of {source_module}.{name} "
        f"(got copies: {api_obj!r} vs {src_obj!r})"
    )


# ---------------------------------------------------------------------------
# Body contains zero `def` and zero `class` (parsed via AST)
# ---------------------------------------------------------------------------


class TestApiBodyIsPureReexport:
    """`src/lore/api.py` body has no function or class definitions."""

    def test_api_source_file_exists(self):
        assert API_MODULE_PATH.is_file(), (
            f"Expected facade at {API_MODULE_PATH}; not found"
        )

    def test_api_body_has_zero_def(self):
        tree = ast.parse(API_MODULE_PATH.read_text())
        defs = [
            n
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        assert defs == [], (
            f"api.py must contain zero `def` (pure re-export); found: "
            f"{[n.name for n in defs]}"
        )

    def test_api_body_has_zero_class(self):
        tree = ast.parse(API_MODULE_PATH.read_text())
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        assert classes == [], (
            f"api.py must contain zero `class` (pure re-export); found: "
            f"{[n.name for n in classes]}"
        )

    def test_api_body_only_imports_and_all_assignment(self):
        """Module body = imports + docstring + literal `__all__`. Nothing else."""
        tree = ast.parse(API_MODULE_PATH.read_text())
        allowed_node_types = (
            ast.Import,
            ast.ImportFrom,
            ast.Assign,  # __all__ = [...]
            ast.AnnAssign,  # __all__: list[str] = [...]
            ast.Expr,  # docstring (Expr wrapping Constant str)
        )
        offenders = [
            type(n).__name__
            for n in tree.body
            if not isinstance(n, allowed_node_types)
        ]
        assert offenders == [], (
            f"api.py top-level should be imports + __all__ only; found: {offenders}"
        )


# ---------------------------------------------------------------------------
# dir() does not advertise non-__all__ names beyond stdlib / dunders
# ---------------------------------------------------------------------------


RITE_PUBLIC_NAMES: frozenset[str] = frozenset(
    {
        # functions (lore.rite)
        "scan_rites",
        "read_rite",
        "search_rites",
        "create_rite",
        "update_rite",
        "delete_rite",
        # dataclasses + exception (lore.models)
        "Rite",
        "RiteNode",
        "RiteBranch",
        "RiteConclusion",
        "SharedStep",
        "RiteError",
        # validator (lore.validators)
        "validate_rite_id",
    }
)


class TestApiRiteSurface:
    """Rite public surface is in `lore.api.__all__`; `_rite` alias stays private.

    Per ADR-010/011 every `lore rite` command is backed by a self-contained
    `lore.api` function, and its types + validator are exported through
    `lore.api.__all__`. The `_rite` underscore alias `cli.py` consumes is the
    internal facade boundary and must NOT appear in `__all__`.
    """

    def test_rite_public_names_in_all(self):
        from lore import api

        missing = RITE_PUBLIC_NAMES - set(api.__all__)
        assert missing == set(), (
            f"rite public names missing from lore.api.__all__: {sorted(missing)}"
        )

    @pytest.mark.parametrize("name", sorted(RITE_PUBLIC_NAMES))
    def test_rite_public_name_importable_from_api(self, name: str):
        from lore import api

        assert hasattr(api, name), f"lore.api missing rite name: {name}"
        assert getattr(api, name) is not None, f"lore.api.{name} resolved to None"

    def test_rite_error_is_value_error_subclass(self):
        from lore.api import RiteError

        assert issubclass(RiteError, ValueError)


class TestApiDirCleanliness:
    """`dir(api)` filtered by `__all__` source-of-truth surfaces nothing extra.

    Spec §1: 'No wildcard re-export. ADR-010 hand-listed.' Implementation
    detail names (imported helper modules, etc.) must NOT appear as public
    via `__all__`.
    """

    def test_no_public_dir_name_outside_all(self):
        from lore import api

        # public = no leading underscore, not in __all__
        public_names = {
            n for n in dir(api) if not n.startswith("_") and n not in api.__all__
        }
        # Submodule attributes accidentally bound via `from lore import X` would
        # leak here. Pure `from lore.X import Y` style does NOT leak X itself.
        # We allow nothing extra.
        assert public_names == set(), (
            f"lore.api advertises names outside __all__: {sorted(public_names)}"
        )
