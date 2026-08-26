"""Lore public API facade — ADR-010 stability boundary.

This module is the only supported import surface for Lore consumers
(Realm, Citadel, third parties). Submodules under ``lore.*`` are
internal — any import outside ``lore.api`` is a consumer bug and may
break without notice.

See ADR-010 (public-api-stability) and ADR-011 (api-parity-with-cli).
"""

# --- Types & enums (from lore.models — leaf type module per ADR-010) ---
from lore.models import (
    QuestStatus, MissionStatus, DependencyType,
    Quest, Mission, Dependency, BoardMessage,
    Artifact, CodexDocument, DoctrineStep, Doctrine, Knight,
    DoctrineListEntry, GlossaryItem, Watcher,
    Rite, RiteNode, RiteBranch, RiteConclusion, SharedStep, RiteError,
)

# --- Operational dataclasses (sourced from their owning modules) ---
from lore.health import HealthIssue, HealthReport
from lore.schemas import SchemaIssue
from lore.impacts import CodeBinding, CodexBinding, ImpactsError, ImpactsResult
from lore.initplan import (
    AccessMode, FileAction, AgentTarget, PlannedFile,
    InitAnswers, InitPlan, InitResult,
)

# --- Project root ---
from lore.root import find_project_root, ProjectNotFoundError

# --- Paths ---
from lore.paths import entity_location

# --- Validators ---
from lore.validators import (
    validate_message, validate_entity_id, validate_mission_id,
    validate_priority, validate_name, validate_group,
    validate_quest_id_loose, validate_chaos_threshold,
    validate_binds_entry, is_glob_pattern, route_entity,
    validate_rite_id,
    validate_access_mode, validate_skill_family,
    validate_agent_id, validate_agent_selection,
)

# --- DB (CRUD + envelopes + bulk ops) ---
from lore.db import (
    # connections / migrations
    get_connection, init_database,
    # quest CRUD
    create_quest, list_quests, read_quest, update_quest, delete_quest, close_quest,
    # mission CRUD
    create_mission, list_missions, read_mission, update_mission, delete_mission,
    # status transitions (single + bulk)
    claim_mission, claim_missions,
    close_mission, close_entities,
    block_mission, unblock_mission,
    # dependencies (single + bulk)
    add_dependency, remove_dependency,
    add_dependencies, remove_dependencies,
    # dependency reads
    list_mission_depends_on, list_mission_blocks,
    get_all_dependencies_for_quest,
    # board
    add_board_message, list_board_messages, delete_board_message,
    # dashboard / stats
    get_dashboard_quests, get_aggregate_stats,
    get_deleted_at, get_missions_for_quest,
    # NEW envelopes (this spec)
    get_mission_detail, get_quest_detail,
    list_missions_grouped,
    update_quest_full, update_mission_full,
    delete_entity,
)

# --- Priority ---
from lore.priority import get_ready_missions

# --- Knight ---
from lore.knight import (
    list_knights, read_knight,
    create_knight, update_knight, delete_knight,
)

# --- Doctrine ---
from lore.doctrine import (
    list_doctrines, read_doctrine,
    create_doctrine, update_doctrine, delete_doctrine,
)

# --- Artifact ---
from lore.artifact import (
    list_artifacts, read_artifact,
    create_artifact, update_artifact, delete_artifact,
)

# --- Watcher ---
from lore.watcher import (
    list_watchers, read_watcher,
    create_watcher, update_watcher, delete_watcher,
)

# --- Frontmatter field-edit (cross-entity) ---
from lore.frontmatter_edit import update_frontmatter_fields

# --- Codex ---
from lore.codex import (
    list_codex, search_documents, read_document,
    read_documents_with_glossary,
    map_documents, chaos_documents,
    create_document, update_document, delete_document,
    ConflictingDepthFlags,
)

# --- Glossary ---
from lore.glossary import (
    scan_glossary, read_glossary_item, search_glossary,
    match_glossary, GlossaryError,
    create_glossary_item, update_glossary_item, delete_glossary_item,
)

# --- Impacts ---
from lore.impacts import impacts, classify_token

# --- Rite ---
from lore.rite import (
    scan_rites, read_rite, search_rites,
    create_rite, update_rite, delete_rite,
)

# --- Health ---
from lore.health import health_check

# --- Schemas ---
from lore.schemas import (
    OverlayError,
    load_schema,
    project_validator_for,
    resolve_merged_schema,
    validate_entity,
    validate_entity_file,
)

# --- Project setup / reports ---
from lore.init import run_init, plan_init, apply_init
from lore.oracle import generate_reports

# --- Config (read-only) ---
from lore.config import load_config, Config

# ---------------------------------------------------------------------------
# Private CLI-only re-exports (NOT part of the public surface).
#
# Leading underscore keeps these names out of ``dir(lore.api)`` per Spec §1's
# "no public name outside __all__" rule, while still letting the CLI (a
# facade consumer like Realm or Citadel would be) avoid direct
# ``from lore.<module>`` imports. Internal submodules are re-exported as
# namespace aliases so the CLI keeps the ``paths.knights_dir(...)`` style
# without leaking the bare submodule name publicly.
#
# The aliases also serve as monkeypatch anchors: unit tests patch
# ``lore.api._<name>`` instead of reaching into ``lore.<module>`` directly,
# which would bypass the facade boundary the ADR-010 contract enforces.
#
# ``noqa: F401`` is required because ruff cannot detect re-export intent
# for renamed imports (only same-name ``as`` aliases count as explicit
# re-exports under PEP 484 / ruff's F401 rules).
# ---------------------------------------------------------------------------
from lore import __version__ as _lore_version  # noqa: F401
from lore import paths as _paths  # noqa: F401
from lore import frontmatter_edit as _frontmatter_edit  # noqa: F401
from lore import graph as _graph  # noqa: F401
from lore import knight as _knight  # noqa: F401
from lore import validators as _validators  # noqa: F401
from lore import watcher as _watcher  # noqa: F401
from lore import glossary as _glossary  # noqa: F401
from lore import impacts as _impacts  # noqa: F401
from lore import doctrine as _doctrine  # noqa: F401
from lore import health as _health  # noqa: F401
from lore import rite as _rite  # noqa: F401
from lore.knight import _validate_frontmatter as _validate_frontmatter  # noqa: F401
from lore import init as _init  # noqa: F401
from lore import reconcile as _reconcile  # noqa: F401
from lore import agents as _agents  # noqa: F401
from lore import db as _db  # noqa: F401
from lore import skills as _skills  # noqa: F401
from lore import prompts as _prompts  # noqa: F401

__all__ = [
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
    # operational dataclasses — initialisation
    "AccessMode",
    "FileAction",
    "AgentTarget",
    "PlannedFile",
    "InitAnswers",
    "InitPlan",
    "InitResult",
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
    # validators — initialisation (interactive-init-us-017)
    "validate_access_mode",
    "validate_skill_family",
    "validate_agent_id",
    "validate_agent_selection",
    # db: quest CRUD
    "create_quest",
    "list_quests",
    "read_quest",
    "update_quest",
    "update_quest_full",
    "delete_quest",
    "close_quest",
    # db: mission CRUD
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
    # db: dependencies
    "add_dependency",
    "remove_dependency",
    "add_dependencies",
    "remove_dependencies",
    "list_mission_depends_on",
    "list_mission_blocks",
    "get_all_dependencies_for_quest",
    # db: board
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
    # knight
    "list_knights",
    "read_knight",
    "create_knight",
    "update_knight",
    "delete_knight",
    # doctrine
    "list_doctrines",
    "read_doctrine",
    "create_doctrine",
    "update_doctrine",
    "delete_doctrine",
    # artifact
    "list_artifacts",
    "read_artifact",
    "create_artifact",
    "update_artifact",
    "delete_artifact",
    # watcher
    "list_watchers",
    "read_watcher",
    "create_watcher",
    "update_watcher",
    "delete_watcher",
    # frontmatter field-edit (cross-entity)
    "update_frontmatter_fields",
    # codex
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
]
