"""Unit tests for lore.blocklint — the structural lint over blocks and the catalogue.

Spec: adaptive-init-spec (Part 2.15, rules L1 to L10). Anchor:
conceptual-workflows-lore-init.

Every world here is a small block set authored in the test and built in memory:
each test starts from a world that lints clean and breaks exactly one rule. The
lint reads tags, counts and structure — never prose (decisions-006).
"""

from __future__ import annotations

import ast
import copy
from dataclasses import replace
from pathlib import Path

import pytest

from lore import blocklint
from lore.blocklint import LintProblem, lint, lint_rendered
from lore.blocks import Block, parse_block, parse_grants
from tests.unit.conftest import (
    FIXTURE_PROFILES,
    FULL,
    HARNESS_MEMORY,
    EVERY_VALID_PROFILE,
)

BLOCKLINT_SOURCE = Path(__file__).resolve().parents[2] / "src" / "lore" / "blocklint.py"


def _block(block_id: str, feature: str, body: str = "Body.", **tags: str) -> Block:
    lines = [f"id: {block_id}", f"feature: {feature}", *(f"{k}: {v}" for k, v in tags.items())]
    text = "---\n" + "\n".join(lines) + "\n---\n" + body + "\n"
    return parse_block(text, source=f"{feature}/{block_id}.md")


def _world():
    """Blocks, catalogue and grants that lint clean."""
    blocks = {
        b.id: b
        for b in (
            _block("s-head", "memory", "---\nname: s\ndescription: A skill\n---"),
            _block(
                "s-a",
                "memory",
                "Run `lore codex list`.",
                route="cli",
                commands="[codex list]",
            ),
            _block("s-b", "memory", "Plain."),
            _block("s-ref", "memory", "Ref.", capabilities="[memory-index]"),
            _block("d-a", "core", "Intro"),
            _block(
                "i-skills-table",
                "core",
                "<!-- lore:skills-table -->\n<!-- lore:skills-table end -->",
                requires="[pseudo:skills]",
            ),
            _block("g-a", "core", "Getting started"),
        )
    }
    catalogue = {
        "version": 3,
        "legacy_families": {
            "memory": {"description": "m", "features": ["memory"], "skills": ["s"]}
        },
        "skills": [
            {
                "id": "s",
                "head": "s-head",
                "files": [
                    {"path": "SKILL.md", "blocks": ["s-a", "s-b"]},
                    {"path": "references/r.md", "blocks": ["s-ref"]},
                ],
            }
        ],
        "documents": {
            "lore-agent": {"max_lines": 98, "blocks": ["d-a", "i-skills-table"]},
            "getting-started": {"max_lines": 100, "blocks": ["g-a"]},
        },
        "oversize": {},
    }
    grants = parse_grants({"commands": {"codex list": ["memory.cli"]}})
    return blocks, catalogue, grants


def _codes(blocks, catalogue, grants) -> set[str]:
    return {problem.code for problem in lint(blocks=blocks, catalogue=catalogue, grants=grants)}


def _with(blocks, *new: Block):
    merged = dict(blocks)
    merged.update({b.id: b for b in new})
    return merged


class TestCleanTreePasses:
    def test_the_fixture_world_lints_clean(self):
        blocks, catalogue, grants = _world()
        assert lint(blocks=blocks, catalogue=catalogue, grants=grants) == []

    def test_a_problem_names_its_code_where_and_detail(self):
        blocks, catalogue, grants = _world()
        blocks["s-b"] = replace(blocks["s-b"], body="{{ x }}")
        problem = lint(blocks=blocks, catalogue=catalogue, grants=grants)[0]
        assert isinstance(problem, LintProblem)
        assert problem.code == "L7"
        assert "s-b" in problem.where
        assert problem.detail


class TestL1Parse:
    def test_directory_must_equal_feature(self):
        blocks, catalogue, grants = _world()
        blocks["s-b"] = replace(blocks["s-b"], path="doctrines/s-b.md")
        assert _codes(blocks, catalogue, grants) == {"L1"}

    def test_stem_must_equal_id(self):
        blocks, catalogue, grants = _world()
        blocks["s-b"] = replace(blocks["s-b"], path="memory/other.md")
        assert _codes(blocks, catalogue, grants) == {"L1"}

    def test_capability_must_be_a_capability(self):
        blocks, catalogue, grants = _world()
        blocks["s-b"] = replace(blocks["s-b"], capabilities=("memory-nonsense",))
        assert "L1" in _codes(blocks, catalogue, grants)

    def test_conditions_must_parse(self):
        blocks, catalogue, grants = _world()
        blocks["s-b"] = replace(blocks["s-b"], requires=("maybe",))
        assert _codes(blocks, catalogue, grants) == {"L1"}
        blocks["s-b"] = replace(blocks["s-b"], requires=(), unless=("maybe",))
        assert _codes(blocks, catalogue, grants) == {"L1"}


class TestL2Commands:
    def test_an_undeclared_command_is_reported(self):
        blocks, catalogue, grants = _world()
        blocks["s-b"] = replace(blocks["s-b"], body="Use `lore codex list` here.")
        assert _codes(blocks, catalogue, grants) == {"L2"}

    def test_a_declared_command_missing_from_the_body_is_reported(self):
        blocks, catalogue, grants = _world()
        blocks["s-a"] = replace(blocks["s-a"], body="No command now.")
        assert _codes(blocks, catalogue, grants) == {"L2"}

    def test_a_declared_command_with_no_grant_row_is_reported(self):
        blocks, catalogue, grants = _world()
        blocks["s-a"] = replace(
            blocks["s-a"], body="Run `lore codex show`.", commands=("codex show",)
        )
        assert _codes(blocks, catalogue, grants) == {"L2"}

    def test_a_block_whose_tags_do_not_imply_a_grant_is_reported(self):
        blocks, catalogue, grants = _world()
        blocks["s-a"] = replace(blocks["s-a"], route=None)
        assert _codes(blocks, catalogue, grants) == {"L2"}

    def test_a_literal_requires_condition_implies_the_grant(self):
        blocks, catalogue, grants = _world()
        blocks["s-a"] = replace(blocks["s-a"], route=None, requires=("memory.cli",))
        assert _codes(blocks, catalogue, grants) == set()

    def test_unless_never_implies(self):
        blocks, catalogue, grants = _world()
        blocks["s-a"] = replace(blocks["s-a"], route=None, unless=("memory.cli",))
        assert _codes(blocks, catalogue, grants) == {"L2"}

    @pytest.mark.parametrize(
        ("phrase", "grant", "tags"),
        [
            ("--help", "pseudo:cli", {"route": "cli"}),
            ("--help", "pseudo:cli", {"capabilities": ("memory-index",)}),
            ("--help", "pseudo:cli", {"requires": ("pseudo:cli",)}),
            ("health", "cap:validate", {}),
            ("codex search", "cap:memory-search", {"capabilities": ("memory-search",)}),
        ],
    )
    def test_the_fixed_axioms_imply_pseudo_grants(self, phrase, grant, tags):
        blocks, catalogue, _ = _world()
        grants = parse_grants({"commands": {"codex list": ["memory.cli"], phrase: [grant]}})
        body = f"Run `lore {phrase}`."
        blocks["s-b"] = replace(blocks["s-b"], body=body, commands=(phrase,), **tags)
        assert _codes(blocks, catalogue, grants) == set()

    def test_quests_imply_pseudo_cli_and_the_quests_grant(self):
        blocks, catalogue, _ = _world()
        grants = parse_grants(
            {
                "commands": {
                    "codex list": ["memory.cli"],
                    "--help": ["pseudo:cli"],
                    "done": ["quests"],
                }
            }
        )
        blocks["q"] = _block("q", "quests", "Run `lore --help`.", commands="[--help]")
        catalogue["documents"]["getting-started"]["blocks"].append("q")
        assert _codes(blocks, catalogue, grants) == set()
        blocks["q"] = replace(blocks["q"], body="Run `lore done`.", commands=("done",))
        assert _codes(blocks, catalogue, grants) == set()
        blocks["s-b"] = replace(blocks["s-b"], body="Run `lore done`.", commands=("done",))
        assert _codes(blocks, catalogue, grants) == {"L2"}

    def test_doctrines_artifacts_and_validate_hold_everywhere(self):
        blocks, catalogue, _ = _world()
        grants = parse_grants(
            {
                "commands": {
                    "codex list": ["memory.cli"],
                    "doctrine show": ["doctrines.cli"],
                    "health": ["cap:validate"],
                }
            }
        )
        blocks["s-b"] = replace(
            blocks["s-b"],
            body="Run `lore health`.",
            commands=("health",),
        )
        assert _codes(blocks, catalogue, grants) == set()
        blocks["s-b"] = replace(
            blocks["s-b"], body="Run `lore doctrine show`.", commands=("doctrine show",)
        )
        assert _codes(blocks, catalogue, grants) == {"L2"}
        blocks["s-b"] = replace(blocks["s-b"], route="cli")
        assert _codes(blocks, catalogue, grants) == set()

    def test_a_memory_capability_does_not_imply_the_quests_grant(self):
        blocks, catalogue, _ = _world()
        grants = parse_grants(
            {"commands": {"codex list": ["memory.cli"], "done": ["quests"]}}
        )
        blocks["s-b"] = replace(
            blocks["s-b"],
            body="Run `lore done`.",
            commands=("done",),
            capabilities=("memory-index",),
        )
        assert _codes(blocks, catalogue, grants) == {"L2"}


class TestL3Catalogue:
    def test_an_unreferenced_block_is_reported(self):
        blocks, catalogue, grants = _world()
        blocks = _with(blocks, _block("orphan", "memory"))
        assert _codes(blocks, catalogue, grants) == {"L3"}

    def test_a_listed_block_that_does_not_exist_is_reported(self):
        blocks, catalogue, grants = _world()
        catalogue["documents"]["getting-started"]["blocks"].append("ghost")
        assert _codes(blocks, catalogue, grants) == {"L3"}

    def test_a_block_twice_in_one_list_is_reported(self):
        blocks, catalogue, grants = _world()
        catalogue["skills"][0]["files"][0]["blocks"].append("s-b")
        assert _codes(blocks, catalogue, grants) == {"L3"}

    def test_a_head_that_does_not_exist_is_reported(self):
        blocks, catalogue, grants = _world()
        catalogue["skills"][0]["head"] = "ghost-head"
        codes = _codes(blocks, catalogue, grants)
        assert "L3" in codes

    def test_a_head_whose_name_is_not_its_skill_is_reported(self):
        blocks, catalogue, grants = _world()
        blocks["s-head"] = replace(
            blocks["s-head"], body="---\nname: other\ndescription: A skill\n---"
        )
        assert _codes(blocks, catalogue, grants) == {"L3"}

    def test_a_head_without_a_description_is_reported(self):
        blocks, catalogue, grants = _world()
        blocks["s-head"] = replace(blocks["s-head"], body="---\nname: s\ndescription: ''\n---")
        assert _codes(blocks, catalogue, grants) == {"L3"}

    def test_a_head_that_is_not_frontmatter_is_reported(self):
        blocks, catalogue, grants = _world()
        blocks["s-head"] = replace(blocks["s-head"], body="no frontmatter")
        assert _codes(blocks, catalogue, grants) == {"L3"}


class TestL4LineCap:
    def test_an_instruction_document_over_its_cap_is_reported(self):
        blocks, catalogue, grants = _world()
        catalogue["documents"]["getting-started"]["max_lines"] = 1
        assert _codes(blocks, catalogue, grants) == {"L4"}

    def test_the_skills_table_bound_counts_against_the_instruction_cap(self):
        blocks, catalogue, grants = _world()
        # d-a (2) + table block (3) = 5 lines; the table adds 4 + one row per skill.
        catalogue["documents"]["lore-agent"]["max_lines"] = 9
        assert _codes(blocks, catalogue, grants) == {"L4"}
        catalogue["documents"]["lore-agent"]["max_lines"] = 10
        assert _codes(blocks, catalogue, grants) == set()

    def test_a_skill_file_over_one_hundred_lines_is_reported(self):
        blocks, catalogue, grants = _world()
        blocks["s-b"] = replace(blocks["s-b"], body="\n".join(f"line {i}" for i in range(100)))
        assert _codes(blocks, catalogue, grants) == {"L4"}

    def test_the_head_counts_against_the_skill_file(self):
        blocks, catalogue, grants = _world()
        # head (4 lines + 1 separator) + s-a (1 + 1) + s-b (n + 1) = n + 8.
        blocks["s-b"] = replace(blocks["s-b"], body="\n".join(f"l{i}" for i in range(92)))
        assert _codes(blocks, catalogue, grants) == set()
        blocks["s-b"] = replace(blocks["s-b"], body="\n".join(f"l{i}" for i in range(93)))
        assert _codes(blocks, catalogue, grants) == {"L4"}

    def test_a_listed_exception_allows_up_to_its_bound(self):
        blocks, catalogue, grants = _world()
        blocks["s-b"] = replace(blocks["s-b"], body="\n".join(f"line {i}" for i in range(100)))
        catalogue["oversize"] = {"s/SKILL.md": 120}
        assert _codes(blocks, catalogue, grants) == set()

    def test_an_exception_is_still_a_cap(self):
        blocks, catalogue, grants = _world()
        blocks["s-b"] = replace(blocks["s-b"], body="\n".join(f"line {i}" for i in range(100)))
        catalogue["oversize"] = {"s/SKILL.md": 105}
        assert _codes(blocks, catalogue, grants) == {"L4"}


class TestStaleExceptionFails:
    def test_an_exception_for_a_file_that_does_not_exist(self):
        blocks, catalogue, grants = _world()
        catalogue["oversize"] = {"s/references/gone.md": 120}
        assert _codes(blocks, catalogue, grants) == {"L4"}

    def test_an_exception_whose_bound_is_not_above_one_hundred(self):
        blocks, catalogue, grants = _world()
        catalogue["oversize"] = {"s/SKILL.md": 100}
        assert _codes(blocks, catalogue, grants) == {"L4"}

    def test_an_exception_for_a_skill_that_does_not_exist(self):
        blocks, catalogue, grants = _world()
        catalogue["oversize"] = {"nope/SKILL.md": 120}
        assert _codes(blocks, catalogue, grants) == {"L4"}


class TestL5MentionClosure:
    def _two_skills(self):
        blocks, catalogue, grants = _world()
        blocks = _with(
            blocks,
            _block("t-head", "doctrines", "---\nname: t\ndescription: T\n---"),
            _block("t-a", "doctrines", "T body", requires="[quests]"),
        )
        catalogue["skills"].append(
            {"id": "t", "head": "t-head", "files": [{"path": "SKILL.md", "blocks": ["t-a"]}]}
        )
        return blocks, catalogue, grants

    def test_a_mention_of_a_skill_that_can_be_absent_is_reported(self):
        blocks, catalogue, grants = self._two_skills()
        blocks["s-b"] = replace(blocks["s-b"], mentions=("t",))
        assert _codes(blocks, catalogue, grants) == {"L5"}

    def test_a_mention_gated_at_least_as_tightly_as_its_target_passes(self):
        blocks, catalogue, grants = self._two_skills()
        # `t` installs whenever Quests is on.
        blocks["s-b"] = replace(blocks["s-b"], mentions=("t",), requires=("quests",))
        assert _codes(blocks, catalogue, grants) == set()

    def test_a_mention_gated_on_a_different_condition_is_reported(self):
        blocks, catalogue, grants = self._two_skills()
        blocks["s-b"] = replace(blocks["s-b"], mentions=("t",), requires=("watchers",))
        assert _codes(blocks, catalogue, grants) == {"L5"}

    def test_the_same_gate_mentions_itself_safely(self):
        blocks, catalogue, grants = self._two_skills()
        blocks["s-b"] = replace(blocks["s-b"], mentions=("s",))
        assert _codes(blocks, catalogue, grants) == set()

    def test_a_mention_of_an_unknown_skill_is_reported(self):
        blocks, catalogue, grants = _world()
        blocks["s-b"] = replace(blocks["s-b"], mentions=("ghost",))
        assert _codes(blocks, catalogue, grants) == {"L5"}

    def test_a_mention_of_a_reference_file_follows_the_file(self):
        blocks, catalogue, grants = _world()
        # references/r.md exists when the index is on; s-b survives whenever memory is on.
        blocks["s-b"] = replace(blocks["s-b"], mentions=("s/references/r.md",))
        assert _codes(blocks, catalogue, grants) == {"L5"}
        blocks["s-b"] = replace(blocks["s-b"], capabilities=("memory-index",))
        assert _codes(blocks, catalogue, grants) == set()

    def test_a_block_gated_on_installed_skills_may_not_mention_a_skill(self):
        blocks, catalogue, grants = _world()
        blocks["d-a"] = replace(blocks["d-a"], requires=("pseudo:skills",), mentions=("s",))
        assert _codes(blocks, catalogue, grants) == {"L5"}

    def test_pseudo_cli_is_consistent_with_a_cli_route(self):
        blocks, catalogue, grants = _world()
        # s-a needs the CLI route, hence the CLI; a target gated on pseudo:cli
        # must be considered present whenever s-a is.
        blocks = _with(
            blocks,
            _block("u-head", "memory", "---\nname: u\ndescription: U\n---"),
            _block("u-a", "memory", "U body", requires="[pseudo:cli]"),
        )
        catalogue["skills"].append(
            {"id": "u", "head": "u-head", "files": [{"path": "SKILL.md", "blocks": ["u-a"]}]}
        )
        blocks["s-a"] = replace(blocks["s-a"], mentions=("u",))
        assert _codes(blocks, catalogue, grants) == set()


class TestL6Markers:
    def test_a_stray_marker_is_reported(self):
        blocks, catalogue, grants = _world()
        blocks["s-b"] = replace(blocks["s-b"], body="<!-- lore:block s-b -->")
        assert _codes(blocks, catalogue, grants) == {"L6"}

    def test_an_access_marker_is_reported(self):
        blocks, catalogue, grants = _world()
        blocks["s-b"] = replace(blocks["s-b"], body="<!-- lore:access cli -->\nx\n<!-- lore:access end -->")
        assert _codes(blocks, catalogue, grants) == {"L6"}

    def test_the_skills_table_pair_is_allowed_only_in_its_own_block(self):
        blocks, catalogue, grants = _world()
        blocks["s-b"] = replace(
            blocks["s-b"],
            body="<!-- lore:skills-table -->\n<!-- lore:skills-table end -->",
        )
        assert _codes(blocks, catalogue, grants) == {"L6"}

    def test_the_table_block_must_hold_exactly_the_pair(self):
        blocks, catalogue, grants = _world()
        blocks["i-skills-table"] = replace(
            blocks["i-skills-table"], body="<!-- lore:skills-table -->"
        )
        assert _codes(blocks, catalogue, grants) == {"L6"}


class TestL7Syntax:
    @pytest.mark.parametrize("body", ["Hello {{ name }}", "Cost ${price}", "close }} only"])
    def test_template_syntax_is_reported(self, body):
        blocks, catalogue, grants = _world()
        blocks["s-b"] = replace(blocks["s-b"], body=body)
        assert _codes(blocks, catalogue, grants) == {"L7"}

    def test_a_command_outside_a_code_span_is_reported(self):
        blocks, catalogue, grants = _world()
        blocks["s-b"] = replace(blocks["s-b"], body="Use lore codex list to look.")
        assert _codes(blocks, catalogue, grants) == {"L7"}


class TestL8Placement:
    def test_a_skill_body_block_may_not_be_core(self):
        blocks, catalogue, grants = _world()
        blocks["s-b"] = replace(blocks["s-b"], feature="core", path="core/s-b.md")
        assert _codes(blocks, catalogue, grants) == {"L8"}

    def test_a_route_is_legal_on_any_feature(self):
        blocks, catalogue, grants = _world()
        blocks["q"] = _block("q", "quests", route="cli")
        catalogue["documents"]["getting-started"]["blocks"].append("q")
        assert _codes(blocks, catalogue, grants) == set()

    def test_a_skill_block_may_not_use_pseudo_skills(self):
        blocks, catalogue, grants = _world()
        blocks["s-b"] = replace(blocks["s-b"], requires=("pseudo:skills",))
        assert _codes(blocks, catalogue, grants) == {"L8"}

    def test_the_head_may_be_core(self):
        blocks, catalogue, grants = _world()
        blocks["s-head"] = replace(blocks["s-head"], feature="core", path="core/s-head.md")
        assert _codes(blocks, catalogue, grants) == set()


class TestL9Unsatisfiable:
    def test_unless_a_capability_the_block_requires(self):
        blocks, catalogue, grants = _world()
        blocks["s-b"] = replace(
            blocks["s-b"], capabilities=("memory-index",), unless=("cap:memory-index",)
        )
        assert _codes(blocks, catalogue, grants) == {"L9"}

    def test_unless_a_condition_the_block_requires(self):
        blocks, catalogue, grants = _world()
        blocks["s-b"] = replace(blocks["s-b"], requires=("quests",), unless=("quests",))
        assert _codes(blocks, catalogue, grants) == {"L9"}

    def test_unless_its_own_feature(self):
        blocks, catalogue, grants = _world()
        blocks["s-b"] = replace(blocks["s-b"], unless=("memory",))
        assert _codes(blocks, catalogue, grants) == {"L9"}

    def test_an_unrelated_unless_is_fine(self):
        blocks, catalogue, grants = _world()
        blocks["s-b"] = replace(blocks["s-b"], unless=("quests",))
        assert _codes(blocks, catalogue, grants) == set()


class TestL10ReferencePaths:
    def test_a_mention_of_a_file_the_catalogue_does_not_declare(self):
        blocks, catalogue, grants = _world()
        blocks["s-b"] = replace(blocks["s-b"], mentions=("s/references/missing.md",))
        assert "L10" in _codes(blocks, catalogue, grants)

    def test_a_mention_of_a_declared_file_is_fine_for_this_rule(self):
        blocks, catalogue, grants = _world()
        blocks["s-ref"] = replace(blocks["s-ref"], mentions=("s/references/r.md",))
        assert "L10" not in _codes(blocks, catalogue, grants)


class TestDistinctRenders:
    """Every text a skill file can render to, for the release's legacy-hash table."""

    def test_a_route_variant_pair_yields_both_texts(self):
        blocks, catalogue, _ = _world()
        blocks["s-b"] = _block("s-b", "memory", "Harness text.", route="harness")
        blocks["s-a"] = _block(
            "s-a", "memory", "Run `lore codex list`.", route="cli",
            commands="[codex list]",
        )
        texts = blocklint.distinct_renders("s", "SKILL.md", blocks=blocks, catalogue=catalogue)
        assert len(texts) == 2
        assert all(text.startswith("---\nname: s") for text in texts)

    def test_a_file_whose_blocks_never_survive_has_no_render(self):
        blocks, catalogue, _ = _world()
        blocks["s-b"] = _block("s-b", "memory", "Never.", unless="[memory]")
        blocks["s-a"] = _block("s-a", "memory", "Never.", unless="[memory]")
        assert blocklint.distinct_renders("s", "SKILL.md", blocks=blocks, catalogue=catalogue) == set()

    def test_a_reference_is_written_only_beside_an_installed_skill(self):
        blocks, catalogue, _ = _world()
        blocks["s-b"] = _block("s-b", "memory", "Body.")
        blocks["s-ref"] = _block("s-ref", "memory", "Ref.", capabilities="[memory-index]")
        texts = blocklint.distinct_renders(
            "s", "references/r.md", blocks=blocks, catalogue=catalogue
        )
        assert texts == {"Ref.\n"}

    @pytest.mark.parametrize(
        "profile", [*FIXTURE_PROFILES.values(), *EVERY_VALID_PROFILE[:25]]
    )
    def test_a_rendering_for_any_profile_is_among_them(self, profile):
        from lore import skills

        for skill_id in skills.installed_skills(profile):
            for relative in skills.skill_files(skill_id, profile):
                text = skills.render_skill_file(skill_id, relative, profile)
                assert text in blocklint.distinct_renders(skill_id, relative)

    def test_an_unknown_skill_or_file_raises(self):
        blocks, catalogue, _ = _world()
        with pytest.raises(ValueError):
            blocklint.distinct_renders("nope", "SKILL.md", blocks=blocks, catalogue=catalogue)
        with pytest.raises(ValueError):
            blocklint.distinct_renders("s", "nope.md", blocks=blocks, catalogue=catalogue)


class TestLintDoesNotMutate:
    def test_inputs_are_left_alone(self):
        blocks, catalogue, grants = _world()
        before = copy.deepcopy(catalogue)
        lint(blocks=blocks, catalogue=catalogue, grants=grants)
        assert catalogue == before


class TestLintRendered:
    def test_a_profile_that_renders_within_every_limit_is_clean(self):
        assert lint_rendered(HARNESS_MEMORY) == []
        assert lint_rendered(FULL) == []

    def test_reports_a_rendered_document_over_its_cap(self, monkeypatch):
        from lore import skills

        catalogue = copy.deepcopy(skills.load_catalogue())
        catalogue["documents"]["lore-agent"]["max_lines"] = 1
        monkeypatch.setattr(skills, "load_catalogue", lambda: catalogue)
        assert {p.code for p in lint_rendered(FULL)} == {"R1"}


class TestModuleBoundary:
    def test_init_never_imports_the_lint(self):
        init_source = (BLOCKLINT_SOURCE.parent / "init.py").read_text(encoding="utf-8")
        assert "blocklint" not in init_source

    def test_lint_imports_only_blocks_skills_and_initplan_from_lore(self):
        tree = ast.parse(BLOCKLINT_SOURCE.read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("lore"):
                names.add(node.module)
            elif isinstance(node, ast.Import):
                names |= {a.name for a in node.names if a.name.startswith("lore")}
        assert names <= {"lore.blocks", "lore.skills", "lore.initplan", "lore"}
        assert blocklint.lint is lint
