"""Unit tests for lore.agents — the packaged coding-agent registry.

The registry is shipped data (``src/lore/defaults/agents.yaml``) read through
``importlib.resources`` at import time, because ``lore init`` runs where no
``.lore/`` exists and ``click.Choice`` needs the id set when the decorator runs.

Assertions against the shipped file are structural only — existence,
parseability and required-key presence (decisions-006-no-seed-content-tests).
"""

from __future__ import annotations

import ast
import functools
from pathlib import Path

import pytest
import yaml

from lore import agents
from lore.initplan import AgentTarget
from lore.schemas import load_schema

SRC_LORE = Path(__file__).resolve().parents[2] / "src" / "lore"
AGENTS_SOURCE = SRC_LORE / "agents.py"
SHIPPED_REGISTRY = SRC_LORE / "defaults" / "agents.yaml"
AGENTS_SCHEMA = SRC_LORE / "schemas" / "agents.yaml"

VALID_PAYLOAD = {
    "version": 1,
    "agents": [
        {
            "id": "zeta",
            "label": "Zeta",
            "instruction_file": "ZETA.md",
            "skills_dir": ".zeta/skills",
        },
        {"id": "none", "label": "None", "instruction_file": None, "skills_dir": None},
    ],
}


@pytest.fixture()
def clear_registry_cache():
    """Drop the process-wide registry caches around a test that swaps the payload."""
    agents.load_registry.cache_clear()
    agents.agent_ids.cache_clear()
    yield
    agents.load_registry.cache_clear()
    agents.agent_ids.cache_clear()


def _source_tree() -> ast.Module:
    return ast.parse(AGENTS_SOURCE.read_text(encoding="utf-8"), filename=str(AGENTS_SOURCE))


# ---------------------------------------------------------------------------
# load_registry
# ---------------------------------------------------------------------------


class TestLoadRegistry:
    def test_returns_agent_target_rows(self):
        registry = agents.load_registry()
        assert isinstance(registry, tuple)
        assert registry, "the packaged registry must not be empty"
        assert all(isinstance(row, AgentTarget) for row in registry)

    def test_every_row_carries_a_non_empty_id_and_label(self):
        for row in agents.load_registry():
            assert row.id and row.id.strip()
            assert row.label and row.label.strip()

    def test_is_lru_cached_with_a_single_slot(self, clear_registry_cache):
        agents.load_registry()
        agents.load_registry()
        agents.load_registry()
        info = agents.load_registry.cache_info()
        assert info.misses == 1
        assert info.maxsize == 1

    def test_repeat_calls_return_the_same_object(self):
        assert agents.load_registry() is agents.load_registry()


class TestAgentIds:
    def test_returns_sorted_ids(self):
        ids = agents.agent_ids()
        assert isinstance(ids, tuple)
        assert list(ids) == sorted(ids)

    def test_matches_the_registry_rows(self):
        assert set(agents.agent_ids()) == {row.id for row in agents.load_registry()}

    def test_is_lru_cached_with_a_single_slot(self, clear_registry_cache):
        agents.agent_ids()
        agents.agent_ids()
        info = agents.agent_ids.cache_info()
        assert info.misses == 1
        assert info.maxsize == 1

    def test_reachable_without_a_project_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        ids = agents.agent_ids()
        assert ids
        assert not (tmp_path / ".lore").exists()


class TestGetAgent:
    def test_known_id_returns_the_matching_row(self):
        for row in agents.load_registry():
            assert agents.get_agent(row.id) is row

    def test_claude_row_carries_an_instruction_file_and_a_skills_dir(self):
        claude = agents.get_agent("claude")
        assert claude.id == "claude"
        assert claude.label.strip()
        assert claude.instruction_file == "CLAUDE.md"
        assert claude.skills_dir == ".claude/skills"

    def test_none_row_has_null_instruction_file_and_skills_dir(self):
        row = agents.get_agent("none")
        assert row.instruction_file is None
        assert row.skills_dir is None
        assert "none" in agents.agent_ids()

    def test_unknown_id_raises_valueerror_naming_the_known_ids(self):
        known = ", ".join(agents.agent_ids())
        with pytest.raises(ValueError) as excinfo:
            agents.get_agent("cline")
        assert str(excinfo.value) == f"Unknown agent: 'cline'. Known agents: {known}."


# ---------------------------------------------------------------------------
# Build defects
# ---------------------------------------------------------------------------


class TestPackagedDataIsABuildDefectWhenInvalid:
    def test_schema_invalid_payload_raises_runtimeerror_naming_the_file(
        self, monkeypatch, clear_registry_cache
    ):
        monkeypatch.setattr(agents, "_read_registry_payload", lambda: {"version": 1})
        with pytest.raises(RuntimeError) as excinfo:
            agents.load_registry()
        assert agents.PACKAGED_REGISTRY in str(excinfo.value)

    def test_non_mapping_payload_raises_runtimeerror_naming_the_file(
        self, monkeypatch, clear_registry_cache
    ):
        monkeypatch.setattr(agents, "_read_registry_payload", lambda: ["not", "a", "mapping"])
        with pytest.raises(RuntimeError) as excinfo:
            agents.load_registry()
        assert agents.PACKAGED_REGISTRY in str(excinfo.value)

    def test_a_valid_injected_payload_still_loads(self, monkeypatch, clear_registry_cache):
        monkeypatch.setattr(agents, "_read_registry_payload", lambda: VALID_PAYLOAD)
        assert agents.agent_ids() == ("none", "zeta")
        assert agents.get_agent("zeta").skills_dir == ".zeta/skills"


# ---------------------------------------------------------------------------
# Module boundaries
# ---------------------------------------------------------------------------


class TestModuleBoundaries:
    def test_module_level_imports_name_no_lore_module_but_initplan(self):
        offenders: list[str] = []
        for node in _source_tree().body:
            if isinstance(node, ast.Import):
                offenders += [
                    a.name
                    for a in node.names
                    if a.name.split(".")[0] == "lore" and a.name != "lore.initplan"
                ]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.split(".")[0] == "lore" and module != "lore.initplan":
                    offenders.append(module)
        assert offenders == [], (
            f"src/lore/agents.py imports {offenders} at module level; the registry loader "
            "must stay cheap enough to import when click.Choice evaluates its set"
        )

    def test_validation_goes_through_load_schema(self):
        names = {n.id for n in ast.walk(_source_tree()) if isinstance(n, ast.Name)}
        names |= {n.attr for n in ast.walk(_source_tree()) if isinstance(n, ast.Attribute)}
        assert "load_schema" in names, (
            "agents.py must validate the packaged registry through schemas.load_schema"
        )

    def test_validation_never_goes_through_the_overlay_resolver(self):
        source = AGENTS_SOURCE.read_text(encoding="utf-8")
        assert "resolve_merged_schema" not in source, (
            "the packaged registry is not overlayable — a project must not be able to "
            "change how a file inside the wheel validates"
        )

    def test_both_loaders_are_declared_with_lru_cache(self):
        for loader in (agents.load_registry, agents.agent_ids):
            assert isinstance(loader, functools._lru_cache_wrapper), (
                f"{loader} must carry functools.lru_cache"
            )


# ---------------------------------------------------------------------------
# The shipped file and its schema (structure only — ADR 006)
# ---------------------------------------------------------------------------


class TestShippedRegistryFile:
    def test_exists_and_parses(self):
        assert SHIPPED_REGISTRY.is_file()
        assert isinstance(yaml.safe_load(SHIPPED_REGISTRY.read_text(encoding="utf-8")), dict)

    def test_has_a_version_integer_and_an_agents_list(self):
        data = yaml.safe_load(SHIPPED_REGISTRY.read_text(encoding="utf-8"))
        assert isinstance(data["version"], int)
        assert isinstance(data["agents"], list)
        assert data["agents"]

    def test_every_row_declares_the_four_keys(self):
        data = yaml.safe_load(SHIPPED_REGISTRY.read_text(encoding="utf-8"))
        for row in data["agents"]:
            assert set(row) == {"id", "label", "instruction_file", "skills_dir"}

    def test_ids_are_unique(self):
        data = yaml.safe_load(SHIPPED_REGISTRY.read_text(encoding="utf-8"))
        ids = [row["id"] for row in data["agents"]]
        assert len(ids) == len(set(ids))

    def test_no_row_declares_a_verified_field(self):
        data = yaml.safe_load(SHIPPED_REGISTRY.read_text(encoding="utf-8"))
        assert all("verified" not in row for row in data["agents"])

    def test_validates_against_the_packaged_schema(self):
        from lore.schemas import validate_entity

        data = yaml.safe_load(SHIPPED_REGISTRY.read_text(encoding="utf-8"))
        assert validate_entity("agents", data) == []


class TestAgentsSchemaKind:
    def test_schema_file_ships_beside_the_other_kinds(self):
        assert AGENTS_SCHEMA.is_file()

    def test_loads_through_load_schema_with_the_canonical_id(self):
        schema = load_schema("agents")
        assert isinstance(schema, dict)
        assert schema["$id"] == "lore://schemas/agents"

    def test_rejects_a_row_missing_a_required_key(self):
        from lore.schemas import validate_entity

        payload = {"version": 1, "agents": [{"id": "x", "label": "X"}]}
        assert validate_entity("agents", payload) != []

    def test_rejects_an_unknown_row_key(self):
        from lore.schemas import validate_entity

        payload = {
            "version": 1,
            "agents": [
                {
                    "id": "x",
                    "label": "X",
                    "instruction_file": None,
                    "skills_dir": None,
                    "verified": True,
                }
            ],
        }
        assert validate_entity("agents", payload) != []
