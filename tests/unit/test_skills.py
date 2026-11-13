"""Unit tests for lore.skills — the shipped skill catalogue and the access-mode renderer.

The catalogue (``src/lore/defaults/skills-catalogue.yaml``) carries structure —
id, family, reference files, retirement ledger — and nothing an agent reads.

Three rules from decisions-006-no-seed-content-tests shape this file:

* the renderer is proved on fixture text authored here, never on shipped prose;
* the shipped catalogue is proved structurally — parseability, key presence and
  internal consistency — never against a reason string or a family description;
* catalogue *behaviour* — how a family resolves, what a retirement returns — is
  proved against an injected payload, so no shipped row has to hold still.

A skill id is the one shipped value the tests below do name, and only where the
id is the contract rather than the content: it is the directory the skill ships
in, the path it installs to, the manifest key that path is recorded under, and
the ledger row that removes it on the next upgrade. Renaming a skill is a
behavioural change, and a test that cannot name the new id does not prove it
happened.
"""

from __future__ import annotations

import ast
import functools
from pathlib import Path

import pytest
import yaml

from lore import agents as _agents
from lore import blocks as blocks_module
from lore import skills
from lore.initplan import AgentTarget
from lore.legacy_init import profile_from_legacy
from lore.schemas import load_schema, validate_entity
from tests.unit.conftest import (
    CLI_MEMORY,
    FULL,
    HARNESS_BARE,
    HARNESS_MEMORY,
    HARNESS_MEMORY_FULL,
    HARNESS_QUESTS,
    HARNESS_WATCHERS,
)

SRC_LORE = Path(__file__).resolve().parents[2] / "src" / "lore"
SKILLS_SOURCE = SRC_LORE / "skills.py"
SHIPPED_CATALOGUE = SRC_LORE / "defaults" / "skills-catalogue.yaml"
CATALOGUE_SCHEMA = SRC_LORE / "schemas" / "skill-catalogue.yaml"

FIXTURE_CATALOGUE = {
    "version": 3,
    "legacy_families": {
        "alpha": {"description": "First family", "features": ["memory"], "skills": ["one", "two"]},
        "beta": {"description": "Second family", "features": ["quests"], "skills": ["three"]},
    },
    "skills": [
        {
            "id": "one",
            "head": "one-head",
            "files": [
                {"path": "SKILL.md", "blocks": ["one-a", "one-b"]},
                {"path": "references/a.md", "blocks": ["one-ref-a"]},
                {"path": "references/b.md", "blocks": ["one-ref-b"]},
            ],
        },
        {
            "id": "two",
            "head": "two-head",
            "files": [
                {"path": "SKILL.md", "blocks": ["two-a"]},
                {"path": "references/x.md", "blocks": ["two-ref"]},
            ],
        },
        {
            "id": "three",
            "head": "three-head",
            "files": [{"path": "SKILL.md", "blocks": ["three-a"]}],
        },
    ],
    "documents": {
        "lore-agent": {"max_lines": 98, "blocks": ["doc-intro", "doc-table"]},
        "getting-started": {"max_lines": 100, "blocks": ["doc-intro"]},
    },
    "oversize": {},
    "retired": {
        "old-one": {"into": "one", "reason": "renamed"},
        "old-three": {"into": "three", "reason": "merged into three"},
    },
}


@pytest.fixture()
def clear_catalogue_cache():
    """Drop the process-wide catalogue caches around a test that swaps the payload."""
    skills.load_catalogue.cache_clear()
    skills.family_ids.cache_clear()
    yield
    skills.load_catalogue.cache_clear()
    skills.family_ids.cache_clear()


@pytest.fixture()
def fixture_catalogue(monkeypatch, clear_catalogue_cache):
    """Serve FIXTURE_CATALOGUE in place of the shipped file."""
    monkeypatch.setattr(skills, "_read_catalogue_payload", lambda: FIXTURE_CATALOGUE)
    return FIXTURE_CATALOGUE


def _source_tree() -> ast.Module:
    return ast.parse(SKILLS_SOURCE.read_text(encoding="utf-8"), filename=str(SKILLS_SOURCE))


# ---------------------------------------------------------------------------
# Catalogue loading
# ---------------------------------------------------------------------------


class TestLoadCatalogue:
    def test_returns_the_parsed_catalogue(self):
        catalogue = skills.load_catalogue()
        assert isinstance(catalogue, dict)
        assert isinstance(catalogue["legacy_families"], dict)
        assert isinstance(catalogue["skills"], list)

    def test_is_lru_cached_with_a_single_slot(self, clear_catalogue_cache):
        skills.load_catalogue()
        skills.load_catalogue()
        skills.load_catalogue()
        info = skills.load_catalogue.cache_info()
        assert info.misses == 1
        assert info.maxsize == 1

    def test_both_loaders_are_declared_with_lru_cache(self):
        for loader in (skills.load_catalogue, skills.family_ids):
            assert isinstance(loader, functools._lru_cache_wrapper)

    def test_reachable_without_a_project_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert skills.family_ids()
        assert not (tmp_path / ".lore").exists()


class TestFamilyIds:
    def test_is_the_sorted_key_set_of_the_legacy_families_map(self):
        assert skills.family_ids() == tuple(sorted(skills.load_catalogue()["legacy_families"]))

    def test_every_legacy_family_skill_is_a_catalogue_skill(self):
        current = {entry["id"] for entry in skills.load_catalogue()["skills"]}
        for row in skills.load_catalogue()["legacy_families"].values():
            assert set(row["skills"]) <= current

    def test_reflects_an_injected_catalogue(self, fixture_catalogue):
        assert skills.family_ids() == ("alpha", "beta")


# ---------------------------------------------------------------------------
# Family resolution
# ---------------------------------------------------------------------------


class TestResolveFamilies:
    def test_all_expands_to_every_family(self):
        assert skills.resolve_families(["all"]) == skills.family_ids()

    def test_none_yields_the_empty_tuple(self):
        assert skills.resolve_families(["none"]) == ()

    def test_a_concrete_list_is_sorted_and_deduplicated(self, fixture_catalogue):
        assert skills.resolve_families(["beta", "alpha", "beta"]) == ("alpha", "beta")

    def test_all_combined_with_a_concrete_family_yields_every_family_once(self, fixture_catalogue):
        assert skills.resolve_families(["all", "alpha"]) == ("alpha", "beta")

    def test_empty_input_yields_the_empty_tuple(self):
        assert skills.resolve_families([]) == ()

    def test_returns_a_tuple(self):
        assert isinstance(skills.resolve_families(["all"]), tuple)

    def test_unknown_token_raises_valueerror_listing_the_accepted_tokens(self):
        accepted = ", ".join([*skills.family_ids(), "all", "none"])
        with pytest.raises(ValueError) as excinfo:
            skills.resolve_families(["memory", "typo"])
        message = str(excinfo.value)
        assert "typo" in message
        assert accepted in message


# ---------------------------------------------------------------------------
# The retirement ledger
# ---------------------------------------------------------------------------


class TestRetirementFor:
    def test_a_retired_id_returns_its_successor_and_reason(self, fixture_catalogue):
        record = skills.retirement_for("old-one")
        assert record is not None
        assert record.into == "one"
        assert record.reason == "renamed"

    def test_a_second_retired_id_resolves_independently(self, fixture_catalogue):
        record = skills.retirement_for("old-three")
        assert record is not None
        assert record.into == "three"
        assert record.reason.strip()

    def test_a_current_id_returns_none(self, fixture_catalogue):
        assert skills.retirement_for("one") is None

    def test_an_unknown_id_returns_none(self, fixture_catalogue):
        assert skills.retirement_for("never-existed") is None

    def test_the_record_is_frozen(self, fixture_catalogue):
        import dataclasses

        record = skills.retirement_for("old-one")
        with pytest.raises(dataclasses.FrozenInstanceError):
            record.into = "elsewhere"

    def test_every_shipped_retirement_resolves(self):
        for retired_id in skills.load_catalogue().get("retired", {}):
            record = skills.retirement_for(retired_id)
            assert record is not None
            assert record.into.strip()
            assert record.reason.strip()

    def test_no_shipped_current_skill_is_also_retired(self):
        current = {entry["id"] for entry in skills.load_catalogue()["skills"]}
        for skill_id in current:
            assert skills.retirement_for(skill_id) is None


# ---------------------------------------------------------------------------
# Build defects
# ---------------------------------------------------------------------------


class TestPackagedCatalogueIsABuildDefectWhenInvalid:
    def test_schema_invalid_payload_raises_runtimeerror_naming_the_file(
        self, monkeypatch, clear_catalogue_cache
    ):
        monkeypatch.setattr(skills, "_read_catalogue_payload", lambda: {"version": 3})
        with pytest.raises(RuntimeError) as excinfo:
            skills.load_catalogue()
        assert skills.PACKAGED_CATALOGUE in str(excinfo.value)

    def test_non_mapping_payload_raises_runtimeerror_naming_the_file(
        self, monkeypatch, clear_catalogue_cache
    ):
        monkeypatch.setattr(skills, "_read_catalogue_payload", lambda: [1, 2, 3])
        with pytest.raises(RuntimeError) as excinfo:
            skills.load_catalogue()
        assert skills.PACKAGED_CATALOGUE in str(excinfo.value)


# ---------------------------------------------------------------------------
# Module boundaries
# ---------------------------------------------------------------------------


class TestModuleBoundaries:
    def test_module_level_imports_name_no_lore_module_but_initplan_and_blocks(self):
        allowed = {"lore.initplan", "lore.blocks"}
        offenders: list[str] = []
        for node in _source_tree().body:
            if isinstance(node, ast.Import):
                offenders += [
                    a.name
                    for a in node.names
                    if a.name.split(".")[0] == "lore" and a.name not in allowed
                ]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.split(".")[0] == "lore" and module not in allowed:
                    offenders.append(module)
        assert offenders == [], (
            f"src/lore/skills.py imports {offenders} at module level; the catalogue loader "
            "must stay cheap enough to import when click.Choice evaluates its set"
        )

    def test_validation_goes_through_load_schema(self):
        tree = _source_tree()
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert "load_schema" in names

    def test_validation_never_goes_through_the_overlay_resolver(self):
        assert "resolve_merged_schema" not in SKILLS_SOURCE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The access-mode renderer — fixtures authored here, never read from defaults/
# ---------------------------------------------------------------------------


BOTH_BLOCKS = (
    "# Reading the codex\n"
    "\n"
    "<!-- lore:access cli -->\n"
    "Read documents with `lore codex show <id>`.\n"
    "<!-- lore:access end -->\n"
    "<!-- lore:access native -->\n"
    "Read documents straight off disk with your own file tool.\n"
    "<!-- lore:access end -->\n"
    "\n"
    "Traverse the graph with `lore codex map <id>`.\n"
)

CLI_LINE = "Read documents with `lore codex show <id>`.\n"
NATIVE_LINE = "Read documents straight off disk with your own file tool.\n"
TRAILING = "Traverse the graph with `lore codex map <id>`.\n"


# ---------------------------------------------------------------------------
# The shipped catalogue and its schema (structure only — ADR 006)
# ---------------------------------------------------------------------------


class TestShippedCatalogueFile:
    def _data(self) -> dict:
        return yaml.safe_load(SHIPPED_CATALOGUE.read_text(encoding="utf-8"))

    def test_exists_and_parses(self):
        assert SHIPPED_CATALOGUE.is_file()
        assert isinstance(self._data(), dict)

    def test_lives_beside_agents_yaml_not_inside_the_skills_tree(self):
        assert SHIPPED_CATALOGUE.parent == SRC_LORE / "defaults"
        assert not (SRC_LORE / "defaults" / "skills").exists()

    def test_declares_the_v3_sections(self):
        data = self._data()
        assert data["version"] == 3
        assert isinstance(data["legacy_families"], dict)
        assert isinstance(data["skills"], list)
        assert isinstance(data["documents"], dict)
        assert isinstance(data["oversize"], dict)
        assert isinstance(data["retired"], dict)

    def test_every_legacy_family_carries_a_description_features_and_skills(self):
        for row in self._data()["legacy_families"].values():
            assert row["description"].strip()
            assert row["features"]
            assert row["skills"]

    def test_every_skill_declares_an_id_a_head_and_a_skill_md(self):
        for entry in self._data()["skills"]:
            assert entry["id"].strip()
            assert entry["head"].strip()
            assert entry["files"][0]["path"] == "SKILL.md"

    def test_the_two_instruction_documents_are_declared(self):
        assert set(self._data()["documents"]) == {"lore-agent", "getting-started"}

    def test_skill_ids_are_unique(self):
        ids = [entry["id"] for entry in self._data()["skills"]]
        assert len(ids) == len(set(ids))

    def test_no_skill_carries_a_description(self):
        for entry in self._data()["skills"]:
            assert "description" not in entry, (
                "a skill's description is authored once in its SKILL.md frontmatter"
            )

    def test_declared_file_paths_are_relative_and_unique_per_skill(self):
        for entry in self._data()["skills"]:
            paths = [row["path"] for row in entry["files"]]
            assert len(paths) == len(set(paths))
            for path in paths:
                assert not path.startswith("/")
                assert ".." not in path.split("/")

    def test_every_retirement_names_a_current_skill_and_a_reason(self):
        data = self._data()
        current = {entry["id"] for entry in data["skills"]}
        for retired_id, record in data["retired"].items():
            assert _follow_retirement_chain(retired_id) in current, (
                f"{retired_id} retires into an unknown skill"
            )
            assert record["reason"].strip()

    def test_no_retired_id_is_also_a_current_skill(self):
        data = self._data()
        current = {entry["id"] for entry in data["skills"]}
        assert current.isdisjoint(data["retired"])

    def test_validates_against_the_packaged_schema(self):
        assert validate_entity("skill-catalogue", self._data()) == []


class TestSkillCatalogueSchemaKind:
    def test_schema_file_ships_beside_the_other_kinds(self):
        assert CATALOGUE_SCHEMA.is_file()

    def test_loads_through_load_schema_with_the_canonical_id(self):
        schema = load_schema("skill-catalogue")
        assert isinstance(schema, dict)
        assert schema["$id"] == "lore://schemas/skill-catalogue"

    def _minimal(self) -> dict:
        return {
            "version": 3,
            "legacy_families": {
                "alpha": {"description": "First", "features": ["memory"], "skills": ["one"]}
            },
            "skills": [
                {"id": "one", "head": "h", "files": [{"path": "SKILL.md", "blocks": ["b"]}]}
            ],
            "documents": {"lore-agent": {"max_lines": 98, "blocks": ["b"]}},
        }

    def test_accepts_a_minimal_catalogue_without_retired_or_oversize(self):
        assert validate_entity("skill-catalogue", self._minimal()) == []

    def test_rejects_a_skill_missing_its_head(self):
        payload = self._minimal()
        del payload["skills"][0]["head"]
        assert validate_entity("skill-catalogue", payload) != []

    def test_rejects_a_skill_with_no_files(self):
        payload = self._minimal()
        payload["skills"][0]["files"] = []
        assert validate_entity("skill-catalogue", payload) != []

    def test_rejects_a_file_with_no_blocks(self):
        payload = self._minimal()
        payload["skills"][0]["files"][0]["blocks"] = []
        assert validate_entity("skill-catalogue", payload) != []

    def test_rejects_the_v2_family_and_references_keys(self):
        payload = self._minimal()
        payload["skills"][0]["family"] = "alpha"
        assert validate_entity("skill-catalogue", payload) != []
        payload = self._minimal()
        payload["skills"][0]["references"] = ["a.md"]
        assert validate_entity("skill-catalogue", payload) != []

    def test_rejects_a_missing_documents_section(self):
        payload = self._minimal()
        del payload["documents"]
        assert validate_entity("skill-catalogue", payload) != []

    def test_rejects_a_legacy_family_without_features(self):
        payload = self._minimal()
        del payload["legacy_families"]["alpha"]["features"]
        assert validate_entity("skill-catalogue", payload) != []

    def test_rejects_a_retirement_missing_its_reason(self):
        payload = self._minimal()
        payload["retired"] = {"old": {"into": "one"}}
        assert validate_entity("skill-catalogue", payload) != []

    def test_rejects_an_unknown_skill_key(self):
        payload = self._minimal()
        payload["skills"][0]["description"] = "no"
        assert validate_entity("skill-catalogue", payload) != []

    def test_rejects_a_non_integer_oversize_bound(self):
        payload = self._minimal()
        payload["oversize"] = {"one/SKILL.md": "big"}
        assert validate_entity("skill-catalogue", payload) != []


# ---------------------------------------------------------------------------
# The shipped skills tree (structure only — ADR 006)
# ---------------------------------------------------------------------------
#
# ADR 006 governs the *content* of a seeded file: no test below reads a word of
# a SKILL.md body. A skill's id is a different thing — it is the install
# contract. It names the directory the file ships in, the path it installs to
# (`.claude/skills/<id>/`), the manifest key that path is recorded under, and
# the ledger row that removes it on the next upgrade. Renaming five skills is
# the whole of US-006, so the ids are named here on purpose.


def _shipped_skill_dirs() -> set[str]:
    """The skill ids the release ships: the catalogue's, since a skill is its blocks."""
    return {entry["id"] for entry in skills.load_catalogue()["skills"]}


def _catalogue_ids() -> set[str]:
    return {entry["id"] for entry in skills.load_catalogue()["skills"]}


def _head_frontmatter(skill_id: str) -> dict:
    """The parsed frontmatter of a skill's head block."""
    entry = next(e for e in skills.load_catalogue()["skills"] if e["id"] == skill_id)
    text = blocks_module.load_blocks()[entry["head"]].body
    assert text.startswith("---"), f"{skill_id}: head block has no frontmatter"
    parts = text.split("---", 2)
    assert len(parts) >= 3, f"{skill_id}: malformed head frontmatter block"
    data = yaml.safe_load(parts[1])
    assert isinstance(data, dict), f"{skill_id}: head frontmatter is not a mapping"
    return data


def _follow_retirement_chain(skill_id: str) -> str:
    """Walk `into` hops until one lands on a skill the release still ships.

    The ledger is append-only, so a skill retired twice leaves a chain: the
    first row points at the id that replaced it, and that id carries its own
    row when it is retired in turn.
    """
    seen: set[str] = set()
    current = skill_id
    while (record := skills.retirement_for(current)) is not None:
        assert current not in seen, f"retirement cycle at {current}"
        seen.add(current)
        current = record.into
    return current


class TestShippedSkillsTree:
    """Structure of the shipped skills: the catalogue and the block tree, never prose."""

    def test_the_release_ships_ten_skills(self):
        assert len(_shipped_skill_dirs()) == 11

    def test_every_skill_has_a_skill_md_with_at_least_one_block(self):
        for entry in skills.load_catalogue()["skills"]:
            paths = [row["path"] for row in entry["files"]]
            assert "SKILL.md" in paths, f"{entry['id']} ships no SKILL.md"
            skill_md = next(row for row in entry["files"] if row["path"] == "SKILL.md")
            assert skill_md["blocks"], f"{entry['id']}/SKILL.md lists no block"

    def test_every_listed_block_exists_in_the_block_tree(self):
        table = blocks_module.load_blocks()
        for entry in skills.load_catalogue()["skills"]:
            for row in entry["files"]:
                for block_id in row["blocks"]:
                    assert block_id in table, f"{entry['id']}/{row['path']}: no block {block_id}"

    def test_every_head_names_its_own_skill(self):
        for name in sorted(_shipped_skill_dirs()):
            assert _head_frontmatter(name).get("name") == name

    def test_every_head_carries_a_non_empty_description(self):
        for name in sorted(_shipped_skill_dirs()):
            description = _head_frontmatter(name).get("description")
            assert isinstance(description, str) and description.strip(), (
                f"{name} carries no description"
            )

    def test_no_retired_id_survives_as_a_shipped_skill(self):
        retired = set(skills.load_catalogue().get("retired", {}))
        assert retired.isdisjoint(_shipped_skill_dirs())

    def test_every_retired_row_resolves_to_a_skill_that_still_ships(self):
        shipped = _shipped_skill_dirs()
        for retired_id in skills.load_catalogue().get("retired", {}):
            record = skills.retirement_for(retired_id)
            assert record is not None
            assert _follow_retirement_chain(retired_id) in shipped, (
                f"{retired_id} retires into {record.into}, which resolves to no shipped skill"
            )

    def test_every_extra_file_is_a_markdown_reference_with_a_unique_path(self):
        for entry in skills.load_catalogue()["skills"]:
            paths = [row["path"] for row in entry["files"]]
            assert len(paths) == len(set(paths)), f"{entry['id']}: duplicate file path"
            for path in paths:
                assert path == "SKILL.md" or (
                    path.startswith("references/") and path.endswith(".md")
                ), f"{entry['id']}: unexpected file {path}"

    def test_the_old_prose_trees_are_gone(self):
        assert not (SRC_LORE / "defaults" / "skills").exists()
        assert not (SRC_LORE / "defaults" / "docs").exists()


class TestFamilyMembershipMatchesTheShippedTree:
    """The retired family table, which the deprecated `--skills` alias reads."""

    @staticmethod
    def _members(family: str) -> tuple[str, ...]:
        return tuple(skills.load_catalogue()["legacy_families"][family]["skills"])

    def test_the_memory_family_is_one_writer_and_one_reader(self):
        assert self._members("memory") == ("retrieve-memory", "store-memory")

    def test_the_machinery_family_is_five_update_skills(self):
        assert self._members("machinery") == (
            "update-artifact",
            "update-custom-schema",
            "update-doctrine",
            "update-index",
            "update-watcher",
        )

    def test_the_workflow_family_is_three_multi_step_processes(self):
        assert self._members("workflow") == ("inquest", "start-quest", "sync-codex-guide")

    def test_no_directory_named_by_a_superseded_skill_survives(self):
        superseded = {
            "new-artifact",
            "new-custom-schema",
            "new-doctrine",
            "new-knight",
            "new-rite",
            "new-watcher",
            "lore-update",
            "update-codex",
            "ingest-source",
            "refresh-source",
            "explore-codex",
            "explore-rite",
            "explore-codex-rite",
        }
        assert superseded.isdisjoint(_shipped_skill_dirs())
# ---------------------------------------------------------------------------
# Where skills install, and what bytes land there.
# Spec: interactive-init-us-011 (lore codex show interactive-init-us-011)
# Anchor: conceptual-workflows-init-interactive — The Prompts, prompts 1-3
#
# ADR-006 boundary: the assertions below name skill *ids* — the directory a
# skill ships in and the path it installs to, which is the contract — and never
# a sentence of the prose inside a SKILL.md.
# ---------------------------------------------------------------------------

MEMORY_AND_WORKFLOW_PROFILE = profile_from_legacy("native", ("memory", "workflow"))


def _targets(*agent_ids: str) -> tuple:
    """Registry rows for *agent_ids*, in the order given."""
    return tuple(_agents.get_agent(agent_id) for agent_id in agent_ids)


def _desired(agent_ids=(), profile=MEMORY_AND_WORKFLOW_PROFILE):
    return skills.desired_files(targets=_targets(*agent_ids), profile=profile)


class TestInstallRoots:
    """interactive-init-us-011 — Tech Spec §7.5's four placement rows."""

    def test_an_agent_with_a_native_directory_takes_it_alone(self):
        assert skills.install_roots(_targets("claude")) == (".claude/skills",)

    def test_an_agent_without_one_falls_back_to_dot_lore_skills(self):
        assert skills.install_roots(_targets("agents-md")) == (".lore/skills",)

    def test_two_agents_produce_both_roots(self):
        assert skills.install_roots(_targets("claude", "agents-md")) == (
            ".claude/skills",
            ".lore/skills",
        )

    def test_none_and_no_agent_both_use_dot_lore_skills(self):
        assert skills.install_roots(_targets("none")) == (".lore/skills",)
        assert skills.install_roots(()) == (".lore/skills",)

    def test_roots_are_deduplicated_and_sorted(self):
        roots = skills.install_roots(_targets("agents-md", "gemini", "claude", "qwen"))
        assert roots == (".claude/skills", ".lore/skills")
        assert list(roots) == sorted(roots)


class TestDesiredFilesPlacement:
    """interactive-init-us-011 — Scenarios 1-4: where the rendered bytes land."""

    def test_a_claude_project_gets_its_skills_under_dot_claude_skills(self):
        """Scenario 1."""
        selected = skills.installed_skills(MEMORY_AND_WORKFLOW_PROFILE)
        desired = _desired(("claude",))
        for skill_id in selected:
            assert f".claude/skills/{skill_id}/SKILL.md" in desired
        assert not [path for path in desired if path.startswith(".lore/skills/")]

    def test_an_agent_with_no_native_directory_gets_dot_lore_skills(self):
        """Scenario 2."""
        desired = _desired(("agents-md",))
        assert desired
        for path in desired:
            assert path.startswith(".lore/skills/")

    def test_two_agents_produce_two_independently_tracked_copies(self):
        """Scenario 3."""
        selected = skills.installed_skills(MEMORY_AND_WORKFLOW_PROFILE)
        desired = _desired(("claude", "agents-md"))
        for skill_id in selected:
            native = desired[f".claude/skills/{skill_id}/SKILL.md"]
            fallback = desired[f".lore/skills/{skill_id}/SKILL.md"]
            assert native.content == fallback.content
            assert native is not fallback

    def test_none_and_no_agent_both_land_in_dot_lore_skills(self):
        """Scenario 4."""
        for agent_ids in ((("none",)), ()):
            desired = _desired(agent_ids)
            assert desired
            for path in desired:
                assert path.startswith(".lore/skills/")


class TestDesiredFilesRendering:
    """interactive-init-us-011 — Scenario 5 and the render contract."""

    def test_a_changed_answer_changes_the_file_set_and_never_the_roots(self):
        """Scenario 5."""
        full = _desired(("claude",), FULL)
        narrow = _desired(("claude",), HARNESS_MEMORY)
        assert set(narrow) < set(full)
        for path in (*full, *narrow):
            assert path.startswith(".claude/skills/")

    def test_no_marker_survives_into_a_desired_file(self):
        for entry in _desired(("claude",), FULL).values():
            assert b"<!-- lore:" not in entry.content

    def test_every_packaged_file_is_rendered_exactly_once_per_root(self, monkeypatch):
        seen: list[tuple[str, str]] = []
        real = skills.render_skill_file

        def counting(skill_id, relative, profile):
            seen.append((skill_id, relative))
            return real(skill_id, relative, profile)

        monkeypatch.setattr(skills, "render_skill_file", counting)
        desired = _desired(("claude",))
        assert len(seen) == len(desired)
        assert len(set(seen)) == len(seen)

    def test_desired_files_is_deterministic(self):
        first = _desired(("claude",))
        second = _desired(("claude",))
        assert {p: e.content for p, e in first.items()} == {
            p: e.content for p, e in second.items()
        }


class TestDesiredFilesRecordShape:
    """interactive-init-us-011 — the DesiredFile each entry carries."""

    def test_keys_are_posix_and_values_carry_kind_and_source(self):
        desired = _desired(("claude",))
        entry = desired[".claude/skills/store-memory/SKILL.md"]
        assert entry.path == ".claude/skills/store-memory/SKILL.md"
        assert entry.kind == "owned"
        assert entry.source == "skill:store-memory"
        assert isinstance(entry.content, bytes)

    def test_reference_files_carry_their_skills_source_token(self):
        desired = _desired(("claude",))
        references = [path for path in desired if "/references/" in path]
        assert references
        for path in references:
            entry = desired[path]
            assert entry.source == f"skill:{path.split('/')[2]}"
            assert entry.kind == "owned"

    def test_keys_use_forward_slashes_on_every_platform(self):
        for path in _desired(("claude",)):
            assert "\\" not in path

    def test_the_bare_core_installs_the_doctrine_and_artifact_skills_only(self):
        paths = _desired(("claude",), HARNESS_BARE)
        assert set(paths) == {
            ".claude/skills/run-doctrine/SKILL.md",
            ".claude/skills/update-artifact/SKILL.md",
            ".claude/skills/update-doctrine/SKILL.md",
        }


# ---------------------------------------------------------------------------
# Catalogue v3 — skills assembled from blocks.
#
# Spec: adaptive-init-spec (Parts 2.5, 2.6). The catalogue and the blocks are
# authored in this file; nothing below asserts what a shipped block says
# (decisions-006-no-seed-content-tests).
# ---------------------------------------------------------------------------

def _fixture_block(block_id: str, feature: str, body: str, **tags: str) -> str:
    lines = [f"id: {block_id}", f"feature: {feature}", *(f"{k}: {v}" for k, v in tags.items())]
    return "---\n" + "\n".join(lines) + "\n---\n" + body + "\n"


FIXTURE_BLOCK_FILES = {
    "memory/one-head.md": _fixture_block(
        "one-head", "memory", "---\nname: one\ndescription: First skill\n---"
    ),
    "watchers/two-head.md": _fixture_block(
        "two-head", "watchers", "---\nname: two\ndescription: Second skill\n---"
    ),
    "quests/three-head.md": _fixture_block(
        "three-head", "quests", "---\nname: three\ndescription: Third skill\n---"
    ),
    "memory/one-a.md": _fixture_block("one-a", "memory", "One A"),
    "memory/one-b.md": _fixture_block("one-b", "memory", "One B"),
    "memory/one-ref-a.md": _fixture_block("one-ref-a", "memory", "Ref A\nRef A2"),
    "memory/one-ref-b.md": _fixture_block(
        "one-ref-b", "memory", "Ref B", capabilities="[memory-index]"
    ),
    "watchers/two-a.md": _fixture_block("two-a", "watchers", "Two A"),
    "memory/two-ref.md": _fixture_block("two-ref", "memory", "Two ref"),
    "quests/three-a.md": _fixture_block("three-a", "quests", "Three A"),
    "core/doc-intro.md": _fixture_block("doc-intro", "core", "Intro"),
    "core/doc-table.md": _fixture_block("doc-table", "core", "Table", requires="[pseudo:skills]"),
}

TARGET_CLAUDE = AgentTarget(
    id="claude", label="Claude", instruction_file="CLAUDE.md", skills_dir=".claude/skills"
)
TARGET_PLAIN = AgentTarget(id="plain", label="Plain", instruction_file=None, skills_dir=None)


@pytest.fixture()
def fixture_world(monkeypatch, clear_catalogue_cache):
    """Serve the fixture catalogue and the fixture blocks in place of the shipped ones."""
    blocks_module.load_blocks.cache_clear()
    monkeypatch.setattr(skills, "_read_catalogue_payload", lambda: FIXTURE_CATALOGUE)
    monkeypatch.setattr(blocks_module, "_read_block_files", lambda: FIXTURE_BLOCK_FILES)
    yield
    blocks_module.load_blocks.cache_clear()


class TestZeroBlockSkillIsNotMaterialised:
    def test_a_skill_with_no_surviving_body_block_is_not_installed(self, fixture_world):
        assert skills.installed_skills(HARNESS_MEMORY) == ("one",)
        assert "two" not in skills.installed_skills(HARNESS_MEMORY)

    def test_installed_skills_follow_catalogue_order(self, fixture_world):
        assert skills.installed_skills(FULL) == ("one", "two", "three")

    def test_the_bare_core_installs_no_optional_skill(self, fixture_world):
        assert skills.installed_skills(HARNESS_BARE) == ()

    def test_desired_files_omit_the_uninstalled_skill(self, fixture_world):
        desired = skills.desired_files(targets=[TARGET_CLAUDE], profile=HARNESS_MEMORY)
        assert all("/two/" not in path and "/three/" not in path for path in desired)
        assert ".claude/skills/one/SKILL.md" in desired

    def test_render_returns_none_for_an_uninstalled_skill(self, fixture_world):
        assert skills.render_skill_file("two", "SKILL.md", HARNESS_MEMORY) is None
        assert skills.rendered_bytes("two", "SKILL.md", HARNESS_MEMORY) is None

    def test_a_skill_made_only_of_core_blocks_is_a_catalogue_defect(
        self, monkeypatch, clear_catalogue_cache
    ):
        files = dict(FIXTURE_BLOCK_FILES)
        del files["watchers/two-a.md"]
        files["core/two-a.md"] = _fixture_block("two-a", "core", "Two A")
        blocks_module.load_blocks.cache_clear()
        monkeypatch.setattr(skills, "_read_catalogue_payload", lambda: FIXTURE_CATALOGUE)
        monkeypatch.setattr(blocks_module, "_read_block_files", lambda: files)
        try:
            with pytest.raises(RuntimeError) as excinfo:
                skills.installed_skills(FULL)
        finally:
            blocks_module.load_blocks.cache_clear()
        assert skills.PACKAGED_CATALOGUE in str(excinfo.value)
        assert "two" in str(excinfo.value)


class TestHeadDoesNotCount:
    def test_the_head_alone_never_installs_a_skill(self, fixture_world):
        # `two` has a head block gated on watchers; with watchers off the
        # head would survive its own gate if it were consulted, yet nothing renders.
        assert skills.render_skill_file("two", "SKILL.md", HARNESS_MEMORY) is None

    def test_the_head_precedes_the_body_after_one_blank_line(self, fixture_world):
        text = skills.render_skill_file("one", "SKILL.md", HARNESS_MEMORY)
        assert text == (
            "---\nname: one\ndescription: First skill\n---\n\nOne A\n\nOne B\n"
        )


class TestReferenceFollowsSkill:
    def test_a_reference_is_written_when_one_of_its_blocks_survives(self, fixture_world):
        assert skills.skill_files("one", HARNESS_MEMORY) == ("SKILL.md", "references/a.md")

    def test_a_reference_with_no_surviving_block_is_not_materialised(self, fixture_world):
        assert "references/b.md" not in skills.skill_files("one", HARNESS_MEMORY)
        assert skills.render_skill_file("one", "references/b.md", HARNESS_MEMORY) is None
        assert "references/b.md" in skills.skill_files("one", HARNESS_MEMORY_FULL)

    def test_a_reference_is_never_written_for_an_uninstalled_skill(self, fixture_world):
        # `two`'s reference block survives under a memory profile, but its
        # SKILL.md blocks (doctrines) do not, so the skill is not installed.
        assert skills.skill_files("two", HARNESS_MEMORY) == ()
        assert skills.render_skill_file("two", "references/x.md", HARNESS_MEMORY) is None
        assert skills.skill_files("two", HARNESS_WATCHERS) == ("SKILL.md",)

    def test_a_reference_renders_its_blocks_without_a_head(self, fixture_world):
        text = skills.render_skill_file("one", "references/a.md", HARNESS_MEMORY)
        assert text == "Ref A\nRef A2\n"

    def test_skill_files_without_a_profile_list_every_declared_file(self, fixture_world):
        assert skills.skill_files("one") == ("SKILL.md", "references/a.md", "references/b.md")

    def test_unknown_skill_raises(self, fixture_world):
        with pytest.raises(ValueError, match="nope"):
            skills.skill_files("nope")
        with pytest.raises(ValueError, match="nope"):
            skills.render_skill_file("nope", "SKILL.md", FULL)


class TestProfileDesiredFilesPlacement:
    def test_an_agent_with_a_skills_dir_receives_them_there(self, fixture_world):
        desired = skills.desired_files(targets=[TARGET_CLAUDE], profile=FULL)
        assert set(desired) == {
            ".claude/skills/one/SKILL.md",
            ".claude/skills/one/references/a.md",
            ".claude/skills/one/references/b.md",
            ".claude/skills/two/SKILL.md",
            ".claude/skills/two/references/x.md",
            ".claude/skills/three/SKILL.md",
        }

    def test_an_agent_without_one_receives_them_in_lore_skills(self, fixture_world):
        desired = skills.desired_files(targets=[TARGET_PLAIN], profile=HARNESS_MEMORY)
        assert set(desired) == {
            ".lore/skills/one/SKILL.md",
            ".lore/skills/one/references/a.md",
        }

    def test_no_agent_at_all_installs_into_lore_skills(self, fixture_world):
        desired = skills.desired_files(targets=[], profile=HARNESS_MEMORY)
        assert all(path.startswith(".lore/skills/") for path in desired)

    def test_both_kinds_of_agent_get_both_roots(self, fixture_world):
        desired = skills.desired_files(targets=[TARGET_CLAUDE, TARGET_PLAIN], profile=HARNESS_MEMORY)
        assert ".claude/skills/one/SKILL.md" in desired
        assert ".lore/skills/one/SKILL.md" in desired

    def test_entries_are_owned_skill_files_carrying_the_rendered_bytes(self, fixture_world):
        entry = skills.desired_files(targets=[TARGET_CLAUDE], profile=HARNESS_MEMORY)[
            ".claude/skills/one/SKILL.md"
        ]
        assert entry.kind == "owned"
        assert entry.source == "skill:one"
        assert entry.content == skills.rendered_bytes("one", "SKILL.md", HARNESS_MEMORY)

    def test_all_off_desires_nothing(self, fixture_world):
        assert skills.desired_files(targets=[TARGET_CLAUDE], profile=HARNESS_BARE) == {}

    def test_the_result_is_deterministic(self, fixture_world):
        first = skills.desired_files(targets=[TARGET_CLAUDE], profile=FULL)
        second = skills.desired_files(targets=[TARGET_CLAUDE], profile=FULL)
        assert first == second


class TestNeighborProfiles:
    def test_there_are_seven_neighbours_of_the_full_lore(self):
        assert len(list(skills.neighbor_profiles(FULL))) == 7

    @pytest.mark.parametrize("base", [FULL, HARNESS_BARE, CLI_MEMORY, HARNESS_QUESTS])
    def test_each_differs_from_the_base_in_the_answer_its_label_names(self, base):
        base_answers = base.as_answers()
        for label, neighbour in skills.neighbor_profiles(base):
            assert neighbour != base
            assert neighbour.normalized() == neighbour
            changed = {k for k, v in neighbour.as_answers().items() if v != base_answers[k]}
            question = label.partition("=")[0].replace("-", "_")
            assert question in changed, label

    def test_a_memory_option_is_not_offered_while_memory_is_off(self):
        labels = [label for label, _ in skills.neighbor_profiles(HARNESS_BARE)]
        assert not any(label.startswith("memory-") for label in labels)

    def test_labels_are_unique_and_none_is_the_base(self):
        labels = [label for label, _ in skills.neighbor_profiles(FULL)]
        assert len(labels) == len(set(labels))
        assert all(profile != FULL for _, profile in skills.neighbor_profiles(FULL))

    def test_the_label_names_the_new_value(self):
        labels = dict(skills.neighbor_profiles(FULL))
        assert labels["route=harness"].route.value == "harness"
        assert labels["quests=false"].quests is False


class TestRenderDocument:
    def test_a_document_is_the_joined_surviving_blocks(self, fixture_world):
        assert skills.render_document("getting-started", HARNESS_MEMORY) == "Intro\n"

    def test_the_skills_table_block_follows_whether_a_skill_is_installed(self, fixture_world):
        assert skills.render_document("lore-agent", HARNESS_MEMORY) == "Intro\n\nTable\n"
        assert skills.render_document("lore-agent", HARNESS_WATCHERS) == "Intro\n\nTable\n"

    def test_the_bare_core_still_renders_the_core_blocks(self, fixture_world):
        assert skills.render_document("lore-agent", HARNESS_BARE) == "Intro\n"
        assert skills.render_document("getting-started", HARNESS_BARE) == "Intro\n"

    def test_unknown_document_raises(self, fixture_world):
        with pytest.raises(ValueError, match="nope"):
            skills.render_document("nope", FULL)


class TestSkillDescription:
    def test_reads_the_head_frontmatter(self, fixture_world):
        assert skills.skill_description("one") == "First skill"

    def test_unknown_skill_raises(self, fixture_world):
        with pytest.raises(ValueError, match="nope"):
            skills.skill_description("nope")


class TestUnresolvedMarker:
    def test_detects_a_block_marker_remnant(self):
        assert skills.unresolved_marker("text\n<!-- lore:block sm-x -->\nmore\n") == (
            "<!-- lore:block sm-x -->"
        )

    def test_detects_a_skills_table_remnant(self):
        assert skills.unresolved_marker("<!-- lore:skills-table -->\n") is not None

    def test_still_detects_an_access_marker(self):
        assert skills.unresolved_marker("<!-- lore:access cli -->\n") is not None

    def test_clean_text_has_none(self):
        assert skills.unresolved_marker("nothing to see\n") is None


class TestShippedCatalogue:
    """Structural only: the shipped blocks and catalogue agree with each other."""

    def test_every_listed_block_exists(self):
        known = blocks_module.load_blocks()
        catalogue = skills.load_catalogue()
        listed = [b for s in catalogue["skills"] for f in s["files"] for b in f["blocks"]]
        listed += [s["head"] for s in catalogue["skills"]]
        listed += [b for d in catalogue["documents"].values() for b in d["blocks"]]
        assert set(listed) <= set(known)

    def test_every_head_names_its_own_skill_and_describes_it(self):
        for entry in skills.load_catalogue()["skills"]:
            assert skills.skill_description(entry["id"]).strip()
            head = blocks_module.load_blocks()[entry["head"]]
            assert f"name: {entry['id']}" in head.body

    def test_every_skill_file_renders_non_empty_when_everything_is_on(self):
        for entry in skills.load_catalogue()["skills"]:
            assert entry["id"] in skills.installed_skills(FULL)
            assert skills.render_skill_file(entry["id"], "SKILL.md", FULL).strip()

    def test_every_retirement_still_lands_on_a_catalogue_skill(self):
        current = {entry["id"] for entry in skills.load_catalogue()["skills"]}
        for retired_id in skills.load_catalogue()["retired"]:
            assert _follow_retirement_chain(retired_id) in current

    def test_the_oversize_list_names_real_files_with_real_bounds(self):
        catalogue = skills.load_catalogue()
        paths = {f"{s['id']}/{f['path']}" for s in catalogue["skills"] for f in s["files"]}
        for path, bound in catalogue["oversize"].items():
            assert path in paths
            assert bound > 100

    def test_the_bare_core_installs_only_the_core_skills(self):
        assert skills.installed_skills(HARNESS_BARE) == ("update-doctrine", "update-artifact", "run-doctrine")

    def test_installed_skills_follow_the_features(self):
        installed = skills.installed_skills(CLI_MEMORY)
        assert "retrieve-memory" in installed and "store-memory" in installed
        assert "update-doctrine" in installed and "update-artifact" in installed
        assert "start-quest" not in installed and "update-watcher" not in installed
