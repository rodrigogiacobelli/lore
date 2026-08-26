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
import re
from pathlib import Path

import pytest
import yaml

from lore import skills
from lore.initplan import AccessMode
from lore.schemas import load_schema, validate_entity

SRC_LORE = Path(__file__).resolve().parents[2] / "src" / "lore"
SKILLS_SOURCE = SRC_LORE / "skills.py"
SHIPPED_CATALOGUE = SRC_LORE / "defaults" / "skills-catalogue.yaml"
SHIPPED_SKILLS_DIR = SRC_LORE / "defaults" / "skills"
SHIPPED_DOCS_DIR = SRC_LORE / "defaults" / "docs"
CATALOGUE_SCHEMA = SRC_LORE / "schemas" / "skill-catalogue.yaml"

FIXTURE_CATALOGUE = {
    "version": 2,
    "families": {
        "alpha": "First family",
        "beta": "Second family",
    },
    "skills": [
        {"id": "one", "family": "alpha", "references": ["a.md", "b.md"]},
        {"id": "two", "family": "alpha"},
        {"id": "three", "family": "beta"},
    ],
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
        assert isinstance(catalogue["families"], dict)
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
    def test_is_the_sorted_key_set_of_the_families_map(self):
        assert skills.family_ids() == tuple(sorted(skills.load_catalogue()["families"]))

    def test_every_declared_skill_names_a_known_family(self):
        known = set(skills.family_ids())
        for entry in skills.load_catalogue()["skills"]:
            assert entry["family"] in known

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


class TestSkillsInFamilies:
    def test_selects_exactly_the_catalogue_entries_of_those_families(self, fixture_catalogue):
        assert skills.skills_in_families(("alpha",)) == ("one", "two")

    def test_spans_several_families(self, fixture_catalogue):
        assert skills.skills_in_families(("alpha", "beta")) == ("one", "two", "three")

    def test_no_families_yields_the_empty_tuple(self):
        assert skills.skills_in_families(()) == ()

    def test_shipped_catalogue_selection_matches_the_declared_families(self):
        for family in skills.family_ids():
            expected = tuple(
                entry["id"]
                for entry in skills.load_catalogue()["skills"]
                if entry["family"] == family
            )
            assert skills.skills_in_families((family,)) == expected

    def test_unknown_family_raises_valueerror(self):
        with pytest.raises(ValueError):
            skills.skills_in_families(("nope",))


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
        monkeypatch.setattr(skills, "_read_catalogue_payload", lambda: {"version": 2})
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


class TestRenderSelectsTheChosenLayer:
    def test_cli_mode_keeps_the_cli_block_and_drops_the_native_one(self):
        out = skills.render(BOTH_BLOCKS, AccessMode.CLI)
        assert CLI_LINE in out
        assert NATIVE_LINE not in out
        assert "<!-- lore:access" not in out
        assert TRAILING in out

    def test_native_mode_is_the_mirror(self):
        out = skills.render(BOTH_BLOCKS, AccessMode.NATIVE)
        assert NATIVE_LINE in out
        assert CLI_LINE not in out
        assert "<!-- lore:access" not in out
        assert TRAILING in out

    def test_the_two_modes_render_exactly_the_expected_documents(self):
        header = "# Reading the codex\n\n"
        tail = "\n" + TRAILING
        assert skills.render(BOTH_BLOCKS, AccessMode.CLI) == header + CLI_LINE + tail
        assert skills.render(BOTH_BLOCKS, AccessMode.NATIVE) == header + NATIVE_LINE + tail

    def test_text_outside_any_block_is_identical_in_both_modes(self):
        cli = skills.render(BOTH_BLOCKS, AccessMode.CLI)
        native = skills.render(BOTH_BLOCKS, AccessMode.NATIVE)
        unconditional = ["# Reading the codex\n", TRAILING]
        for line in unconditional:
            assert line in cli
            assert line in native

    def test_a_document_without_markers_is_returned_unchanged(self):
        text = "No markers here.\n\nJust prose."
        assert skills.render(text, AccessMode.CLI) == text
        assert skills.render(text, AccessMode.NATIVE) == text

    def test_an_empty_document_is_returned_unchanged(self):
        assert skills.render("", AccessMode.CLI) == ""

    def test_adjacent_blocks_resolve_independently(self):
        text = (
            "<!-- lore:access cli -->\n"
            "one\n"
            "<!-- lore:access end -->\n"
            "<!-- lore:access cli -->\n"
            "two\n"
            "<!-- lore:access end -->\n"
        )
        assert skills.render(text, AccessMode.CLI) == "one\ntwo\n"
        assert skills.render(text, AccessMode.NATIVE) == ""

    def test_a_dropped_block_removes_markers_body_and_its_own_newlines(self):
        text = "before\n<!-- lore:access cli -->\nbody\n<!-- lore:access end -->\nafter\n"
        assert skills.render(text, AccessMode.NATIVE) == "before\nafter\n"

    def test_a_dropped_block_leaves_the_surrounding_blank_lines_alone(self):
        text = (
            "before\n"
            "\n"
            "<!-- lore:access cli -->\n"
            "body\n"
            "<!-- lore:access end -->\n"
            "\n"
            "after\n"
        )
        assert skills.render(text, AccessMode.NATIVE) == "before\n\n\nafter\n"

    def test_a_block_closing_at_end_of_file_without_a_trailing_newline(self):
        text = "before\n<!-- lore:access cli -->\nbody\n<!-- lore:access end -->"
        assert skills.render(text, AccessMode.CLI) == "before\nbody\n"
        assert skills.render(text, AccessMode.NATIVE) == "before\n"

    def test_a_kept_body_ending_without_a_trailing_newline_gains_none(self):
        text = "<!-- lore:access cli -->\nbody\n<!-- lore:access end -->"
        assert skills.render(text, AccessMode.CLI) == "body\n"

    def test_markers_may_be_indented(self):
        text = "  <!-- lore:access cli -->\nbody\n  <!-- lore:access end -->\n"
        assert skills.render(text, AccessMode.CLI) == "body\n"
        assert skills.render(text, AccessMode.NATIVE) == ""

    def test_a_line_that_merely_mentions_a_marker_is_body_text(self):
        text = "Author blocks with `<!-- lore:access cli -->` markers.\n"
        assert skills.render(text, AccessMode.CLI) == text


class TestRenderRejectsMalformedBlocks:
    def test_an_unterminated_block_names_the_opener_line(self):
        text = "one\ntwo\n<!-- lore:access cli -->\nbody\n"
        with pytest.raises(ValueError) as excinfo:
            skills.render(text, AccessMode.CLI)
        assert ":3" in str(excinfo.value)

    def test_an_unknown_mode_token_names_the_token_and_the_line(self):
        text = "<!-- lore:access agentic -->\nbody\n<!-- lore:access end -->\n"
        with pytest.raises(ValueError) as excinfo:
            skills.render(text, AccessMode.CLI)
        message = str(excinfo.value)
        assert "agentic" in message
        assert ":1" in message

    def test_an_end_with_no_opener_names_the_line(self):
        text = "body\n<!-- lore:access end -->\n"
        with pytest.raises(ValueError) as excinfo:
            skills.render(text, AccessMode.CLI)
        assert ":2" in str(excinfo.value)

    def test_a_nested_opener_is_rejected(self):
        text = (
            "<!-- lore:access cli -->\n"
            "<!-- lore:access native -->\n"
            "body\n"
            "<!-- lore:access end -->\n"
            "<!-- lore:access end -->\n"
        )
        with pytest.raises(ValueError) as excinfo:
            skills.render(text, AccessMode.CLI)
        assert ":2" in str(excinfo.value)

    def test_the_error_names_the_source_when_one_is_given(self):
        text = "<!-- lore:access cli -->\n"
        with pytest.raises(ValueError) as excinfo:
            skills.render(text, AccessMode.CLI, source="skills/example/SKILL.md")
        assert "skills/example/SKILL.md" in str(excinfo.value)

    def test_a_dropped_block_is_still_validated(self):
        text = "<!-- lore:access cli -->\nbody\n"
        with pytest.raises(ValueError):
            skills.render(text, AccessMode.NATIVE)


class TestRenderIsTheOnlyBlockSelector:
    def test_no_other_source_module_reads_the_access_markers(self):
        offenders = [
            path.name
            for path in sorted(SRC_LORE.glob("*.py"))
            if path.name != "skills.py" and "lore:access" in path.read_text(encoding="utf-8")
        ]
        assert offenders == [], (
            f"{offenders} also read the access markers; block selection lives in skills.render alone"
        )


class TestShippedFilesAreWellFormedUnderBothModes:
    def _shipped_text_files(self) -> list[Path]:
        candidates: list[Path] = []
        if SHIPPED_SKILLS_DIR.is_dir():
            candidates += [p for p in sorted(SHIPPED_SKILLS_DIR.rglob("*.md")) if p.is_file()]
        if SHIPPED_DOCS_DIR.is_dir():
            candidates += [p for p in sorted(SHIPPED_DOCS_DIR.rglob("*.md")) if p.is_file()]
        return candidates

    def test_the_shipped_tree_is_not_empty(self):
        assert self._shipped_text_files(), "no shipped markdown found to sweep"

    def test_every_shipped_file_renders_in_both_modes_without_raising(self):
        for path in self._shipped_text_files():
            text = path.read_text(encoding="utf-8")
            for mode in AccessMode:
                skills.render(text, mode, source=str(path))

    def test_every_shipped_access_region_is_terminated_and_names_a_known_mode(self):
        # A marker pattern written here on purpose: the sweep must not lean on the
        # parser it is auditing.
        marker = re.compile(r"^<!--\s*lore:access\s+(\S+)\s*-->$")
        for path in self._shipped_text_files():
            depth = 0
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                match = marker.match(line.strip())
                if match is None:
                    continue
                token = match.group(1)
                if token == "end":
                    depth -= 1
                    assert depth == 0, f"{path}:{lineno}: unbalanced access marker"
                else:
                    assert token in {m.value for m in AccessMode}, (
                        f"{path}:{lineno}: unknown access-mode token {token!r}"
                    )
                    depth += 1
                    assert depth == 1, f"{path}:{lineno}: access blocks never nest"
            assert depth == 0, f"{path}: unterminated access block"


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
        assert not (SHIPPED_SKILLS_DIR / "skills-catalogue.yaml").exists()

    def test_declares_version_families_skills_and_retired(self):
        data = self._data()
        assert isinstance(data["version"], int)
        assert isinstance(data["families"], dict)
        assert isinstance(data["skills"], list)
        assert isinstance(data["retired"], dict)

    def test_every_family_carries_a_description(self):
        for description in self._data()["families"].values():
            assert isinstance(description, str)
            assert description.strip()

    def test_every_skill_declares_an_id_and_a_known_family(self):
        data = self._data()
        for entry in data["skills"]:
            assert entry["id"].strip()
            assert entry["family"] in data["families"]

    def test_skill_ids_are_unique(self):
        ids = [entry["id"] for entry in self._data()["skills"]]
        assert len(ids) == len(set(ids))

    def test_no_skill_carries_a_description(self):
        for entry in self._data()["skills"]:
            assert "description" not in entry, (
                "a skill's description is authored once in its SKILL.md frontmatter"
            )

    def test_declared_references_are_plain_file_names(self):
        for entry in self._data()["skills"]:
            for reference in entry.get("references", []):
                assert isinstance(reference, str)
                assert reference.strip()
                assert not reference.startswith("/")

    def test_every_retirement_names_a_current_skill_and_a_reason(self):
        data = self._data()
        current = {entry["id"] for entry in data["skills"]}
        for retired_id, record in data["retired"].items():
            assert record["into"] in current, f"{retired_id} retires into an unknown skill"
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

    def test_accepts_a_minimal_catalogue_without_retired(self):
        payload = {
            "version": 2,
            "families": {"alpha": "First"},
            "skills": [{"id": "one", "family": "alpha"}],
        }
        assert validate_entity("skill-catalogue", payload) == []

    def test_rejects_a_skill_missing_its_family(self):
        payload = {
            "version": 2,
            "families": {"alpha": "First"},
            "skills": [{"id": "one"}],
        }
        assert validate_entity("skill-catalogue", payload) != []

    def test_rejects_a_retirement_missing_its_reason(self):
        payload = {
            "version": 2,
            "families": {"alpha": "First"},
            "skills": [{"id": "one", "family": "alpha"}],
            "retired": {"old": {"into": "one"}},
        }
        assert validate_entity("skill-catalogue", payload) != []

    def test_rejects_an_unknown_skill_key(self):
        payload = {
            "version": 2,
            "families": {"alpha": "First"},
            "skills": [{"id": "one", "family": "alpha", "description": "no"}],
        }
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
    return {path.name for path in SHIPPED_SKILLS_DIR.iterdir() if path.is_dir()}


def _catalogue_ids() -> set[str]:
    return {entry["id"] for entry in skills.load_catalogue()["skills"]}


def _skill_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---"), f"{path}: no frontmatter block"
    parts = text.split("---", 2)
    assert len(parts) >= 3, f"{path}: malformed frontmatter block"
    data = yaml.safe_load(parts[1])
    assert isinstance(data, dict), f"{path}: frontmatter is not a mapping"
    return data


def _skill_md(skill_id: str) -> Path:
    return SHIPPED_SKILLS_DIR / skill_id / "SKILL.md"


class TestShippedSkillsTree:
    def test_the_release_ships_ten_skill_directories(self):
        assert len(_shipped_skill_dirs()) == 10

    def test_every_shipped_directory_holds_a_skill_md(self):
        for name in _shipped_skill_dirs():
            assert _skill_md(name).is_file(), f"{name}/ ships no SKILL.md"

    def test_the_directory_set_equals_the_catalogue_id_set(self):
        assert _shipped_skill_dirs() == _catalogue_ids()

    def test_every_frontmatter_name_is_its_own_directory_name(self):
        for name in sorted(_shipped_skill_dirs()):
            assert _skill_frontmatter(_skill_md(name)).get("name") == name

    def test_every_frontmatter_carries_a_non_empty_description(self):
        for name in sorted(_shipped_skill_dirs()):
            description = _skill_frontmatter(_skill_md(name)).get("description")
            assert isinstance(description, str) and description.strip(), (
                f"{name}/SKILL.md carries no description"
            )

    def test_no_retired_id_survives_as_a_shipped_directory(self):
        retired = set(skills.load_catalogue().get("retired", {}))
        assert retired.isdisjoint(_shipped_skill_dirs())

    def test_every_retired_row_resolves_to_a_directory_that_still_ships(self):
        shipped = _shipped_skill_dirs()
        for retired_id in skills.load_catalogue().get("retired", {}):
            record = skills.retirement_for(retired_id)
            assert record is not None
            assert record.into in shipped, (
                f"{retired_id} retires into {record.into}, which ships no directory"
            )

    def test_declared_references_match_the_directory_in_both_directions(self):
        for entry in skills.load_catalogue()["skills"]:
            declared = set(entry.get("references", []))
            references_dir = SHIPPED_SKILLS_DIR / entry["id"] / "references"
            on_disk = (
                {path.name for path in references_dir.iterdir() if path.is_file()}
                if references_dir.is_dir()
                else set()
            )
            assert on_disk == declared, f"{entry['id']}: {on_disk} != {declared}"


class TestFamilyMembershipMatchesTheShippedTree:
    def test_the_memory_family_is_one_writer_and_one_reader(self):
        assert skills.skills_in_families(("memory",)) == ("retrieve-memory", "store-memory")

    def test_the_machinery_family_is_five_update_skills(self):
        assert skills.skills_in_families(("machinery",)) == (
            "update-artifact",
            "update-custom-schema",
            "update-doctrine",
            "update-knight",
            "update-watcher",
        )

    def test_the_workflow_family_is_three_multi_step_processes(self):
        assert skills.skills_in_families(("workflow",)) == (
            "inquest",
            "start-quest",
            "sync-codex-guide",
        )

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


class TestEverySkillIsAuthoredForBothAccessModes:
    def _memory_family_files(self) -> list[Path]:
        files = [_skill_md("store-memory"), _skill_md("retrieve-memory")]
        files += sorted((SHIPPED_SKILLS_DIR / "store-memory" / "references").glob("*.md"))
        return files

    def test_every_memory_family_file_renders_in_both_modes_without_markers(self):
        for path in self._memory_family_files():
            text = path.read_text(encoding="utf-8")
            for mode in AccessMode:
                rendered = skills.render(text, mode, source=str(path))
                assert "<!-- lore:access" not in rendered

    def test_every_shipped_skill_renders_differently_per_access_mode(self):
        for name in sorted(_shipped_skill_dirs()):
            text = _skill_md(name).read_text(encoding="utf-8")
            cli = skills.render(text, AccessMode.CLI, source=name)
            native = skills.render(text, AccessMode.NATIVE, source=name)
            assert cli != native, (
                f"{name}/SKILL.md renders identically in both modes — it carries no "
                "access-mode block, so the mode never reaches it"
            )

    def test_the_graph_commands_survive_both_modes_of_the_retrieval_skill(self):
        # FR-18: no file tool reproduces a precomputed traversal, so these three
        # are authored outside every block. Command-token presence, not prose.
        text = _skill_md("retrieve-memory").read_text(encoding="utf-8")
        for mode in AccessMode:
            rendered = skills.render(text, mode, source="retrieve-memory")
            for command in ("lore codex map", "lore codex chaos", "lore impacts"):
                assert command in rendered, f"{command} dropped in {mode.value} mode"


# ---------------------------------------------------------------------------
# Where skills install, and what bytes land there.
# Spec: interactive-init-us-011 (lore codex show interactive-init-us-011)
# Anchor: conceptual-workflows-init-interactive — The Prompts, prompts 1-3
#
# ADR-006 boundary: the assertions below name skill *ids* — the directory a
# skill ships in and the path it installs to, which is the contract — and never
# a sentence of the prose inside a SKILL.md.
# ---------------------------------------------------------------------------

from lore import agents as _agents  # noqa: E402


MEMORY_AND_WORKFLOW = ("memory", "workflow")


def _targets(*agent_ids: str) -> tuple:
    """Registry rows for *agent_ids*, in the order given."""
    return tuple(_agents.get_agent(agent_id) for agent_id in agent_ids)


def _desired(agent_ids=(), families=MEMORY_AND_WORKFLOW, mode=AccessMode.NATIVE):
    return skills.desired_files(
        targets=_targets(*agent_ids),
        skill_families=families,
        access_mode=mode,
    )


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
        selected = skills.skills_in_families(MEMORY_AND_WORKFLOW)
        desired = _desired(("claude",))
        for skill_id in selected:
            assert f".claude/skills/{skill_id}/SKILL.md" in desired
        for reference in ("codex-doc.md", "rite.md", "source.md"):
            assert f".claude/skills/store-memory/references/{reference}" in desired
        assert not [path for path in desired if path.startswith(".lore/skills/")]

    def test_an_agent_with_no_native_directory_gets_dot_lore_skills(self):
        """Scenario 2."""
        desired = _desired(("agents-md",))
        assert desired
        for path in desired:
            assert path.startswith(".lore/skills/")

    def test_two_agents_produce_two_independently_tracked_copies(self):
        """Scenario 3."""
        selected = skills.skills_in_families(MEMORY_AND_WORKFLOW)
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

    def test_the_access_mode_changes_bytes_not_paths(self):
        """Scenario 5."""
        native = _desired(("claude",), mode=AccessMode.NATIVE)
        cli = _desired(("claude",), mode=AccessMode.CLI)
        assert set(native) == set(cli)
        differing = [path for path in native if native[path].content != cli[path].content]
        for path in native:
            if path.endswith("SKILL.md"):
                assert b"<!-- lore:access" not in native[path].content
                assert b"<!-- lore:access" not in cli[path].content
        assert differing, "no rendered file responded to the access mode"

    def test_every_packaged_file_is_rendered_exactly_once(self, monkeypatch):
        seen: list[str] = []
        real_render = skills.render

        def counting_render(text, mode, source=None):
            seen.append(source or "<text>")
            return real_render(text, mode, source)

        monkeypatch.setattr(skills, "render", counting_render)
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
        for reference in ("codex-doc.md", "rite.md", "source.md"):
            entry = desired[f".claude/skills/store-memory/references/{reference}"]
            assert entry.source == "skill:store-memory"
            assert entry.kind == "owned"

    def test_keys_use_forward_slashes_on_every_platform(self):
        for path in _desired(("claude",)):
            assert "\\" not in path

    def test_an_empty_family_selection_installs_no_skill(self):
        """Scenario 6, first half — the composed half lives in test_lore_init.py."""
        assert _desired(("claude",), families=()) == {}
