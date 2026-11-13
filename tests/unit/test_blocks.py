"""Unit tests for lore.blocks — the block parser, gate evaluator and assembler.

Spec: adaptive-init-spec (Parts 2.3, 2.4, 2.5, 2.15). Anchor:
conceptual-workflows-lore-init.

Every block here is a literal string authored in the test. Nothing asserts what
the shipped blocks say (decisions-006-no-seed-content-tests); the shipped tree
is checked structurally in ``test_blocks_shipped.py``.
"""

from __future__ import annotations

import ast
import itertools
import random
from pathlib import Path

import pytest

from lore import blocks
from lore.blocks import (
    Block,
    BlockDefect,
    assemble,
    commands_in,
    join,
    leaked_commands,
    max_lines,
    parse_block,
    parse_condition,
    survives,
)
from lore.initplan import Profile, Route
from tests.unit.conftest import (
    CLI_BARE,
    CLI_MEMORY,
    FULL,
    HARNESS_BARE,
    HARNESS_MEMORY,
    HARNESS_MEMORY_FULL,
    HARNESS_QUESTS,
)

BLOCKS_SOURCE = Path(__file__).resolve().parents[2] / "src" / "lore" / "blocks.py"


@pytest.fixture(autouse=True)
def _fresh_loader_cache():
    blocks.load_blocks.cache_clear()
    blocks.load_grants.cache_clear()
    yield
    blocks.load_blocks.cache_clear()
    blocks.load_grants.cache_clear()


def _text(
    block_id: str = "b-one",
    feature: str = "core",
    *,
    body: str = "Body.",
    **extra: object,
) -> str:
    lines = [f"id: {block_id}", f"feature: {feature}"]
    for key, value in extra.items():
        lines.append(f"{key}: {value}")
    return "---\n" + "\n".join(lines) + "\n---\n" + body + "\n"


def _block(block_id: str = "b-one", feature: str = "core", *, body: str = "Body.", **extra) -> Block:
    return parse_block(_text(block_id, feature, body=body, **extra), source=f"{block_id}.md")


# ---------------------------------------------------------------------------
# parse_block
# ---------------------------------------------------------------------------


class TestParseBlock:
    def test_a_minimal_block_takes_the_documented_defaults(self):
        block = parse_block(_text("i-intro", "core", body="Hello."), source="core/i-intro.md")
        assert block == Block(
            id="i-intro",
            feature="core",
            route=None,
            capabilities=(),
            requires=(),
            unless=(),
            commands=(),
            mentions=(),
            glue="blank",
            body="Hello.",
            path="core/i-intro.md",
        )

    def test_every_key_is_read(self):
        text = (
            "---\n"
            "id: sm-x\n"
            "feature: memory\n"
            "route: cli\n"
            "capabilities: [memory-index]\n"
            "requires: [pseudo:cli]\n"
            "unless: [quests]\n"
            "commands: [codex list, codex show]\n"
            "mentions: [retrieve-memory]\n"
            "glue: tight\n"
            "---\n"
            "Line one.\n"
            "\n"
            "Line two.\n"
        )
        block = parse_block(text, source="memory/sm-x.md")
        assert (block.route, block.glue) == ("cli", "tight")
        assert block.capabilities == ("memory-index",)
        assert block.requires == ("pseudo:cli",)
        assert block.unless == ("quests",)
        assert block.commands == ("codex list", "codex show")
        assert block.mentions == ("retrieve-memory",)
        assert block.body == "Line one.\n\nLine two."

    def test_blank_lines_around_the_body_are_trimmed_but_indentation_is_kept(self):
        block = parse_block(_text(body="\n\n    indented\nnext\n\n"), source="x.md")
        assert block.body == "    indented\nnext"

    def test_missing_id_raises_naming_the_source(self):
        with pytest.raises(ValueError, match="core/x.md"):
            parse_block("---\nfeature: core\n---\nBody\n", source="core/x.md")

    def test_missing_feature_raises(self):
        with pytest.raises(ValueError, match="x.md"):
            parse_block("---\nid: x\n---\nBody\n", source="x.md")

    def test_unknown_key_raises(self):
        with pytest.raises(ValueError, match="x.md"):
            parse_block(_text(colour="red"), source="x.md")

    def test_bad_glue_raises(self):
        with pytest.raises(ValueError, match="glue"):
            parse_block(_text(glue="loose"), source="x.md")

    def test_unknown_feature_raises(self):
        with pytest.raises(ValueError, match="x.md"):
            parse_block(_text(feature="plugins"), source="x.md")

    def test_action_is_no_longer_a_key(self):
        with pytest.raises(ValueError, match="x.md"):
            parse_block(_text(feature="memory", action="read"), source="x.md")

    def test_unknown_route_raises(self):
        with pytest.raises(ValueError, match="x.md"):
            parse_block(_text(feature="memory", route="off"), source="x.md")

    def test_no_frontmatter_raises(self):
        with pytest.raises(ValueError, match="x.md"):
            parse_block("Just a body\n", source="x.md")

    def test_unterminated_frontmatter_raises(self):
        with pytest.raises(ValueError, match="x.md"):
            parse_block("---\nid: x\nfeature: core\nBody\n", source="x.md")

    def test_invalid_yaml_raises(self):
        with pytest.raises(ValueError, match="x.md"):
            parse_block("---\nid: [unclosed\n---\nBody\n", source="x.md")

    def test_frontmatter_must_be_a_mapping(self):
        with pytest.raises(ValueError, match="x.md"):
            parse_block("---\n- a\n- b\n---\nBody\n", source="x.md")

    def test_a_bad_id_shape_raises(self):
        with pytest.raises(ValueError, match="x.md"):
            parse_block(_text(block_id="Bad Id"), source="x.md")


# ---------------------------------------------------------------------------
# The loader
# ---------------------------------------------------------------------------


class TestLoadBlocks:
    def _install(self, monkeypatch, files: dict[str, str]):
        monkeypatch.setattr(blocks, "_read_block_files", lambda: files)

    def test_loads_every_file_keyed_by_id(self, monkeypatch):
        self._install(
            monkeypatch,
            {
                "core/i-a.md": _text("i-a", "core"),
                "memory/sm-b.md": _text("sm-b", "memory"),
            },
        )
        loaded = blocks.load_blocks()
        assert set(loaded) == {"i-a", "sm-b"}
        assert loaded["sm-b"].path == "memory/sm-b.md"

    def test_a_stem_that_differs_from_the_id_is_a_build_defect_naming_the_file(self, monkeypatch):
        self._install(monkeypatch, {"core/other.md": _text("i-a", "core")})
        with pytest.raises(BlockDefect, match="src/lore/defaults/blocks/core/other.md"):
            blocks.load_blocks()

    def test_an_unparseable_file_is_a_build_defect_naming_the_file(self, monkeypatch):
        self._install(monkeypatch, {"core/i-a.md": "no frontmatter\n"})
        with pytest.raises(BlockDefect, match="src/lore/defaults/blocks/core/i-a.md"):
            blocks.load_blocks()

    def test_a_repeated_id_is_a_build_defect(self, monkeypatch):
        self._install(
            monkeypatch,
            {"core/i-a.md": _text("i-a", "core"), "memory/i-a.md": _text("i-a", "memory")},
        )
        with pytest.raises(BlockDefect, match="i-a"):
            blocks.load_blocks()

    def test_a_block_defect_is_a_runtime_error(self):
        assert issubclass(BlockDefect, RuntimeError)

    def test_the_result_is_cached(self, monkeypatch):
        self._install(monkeypatch, {"core/i-a.md": _text("i-a", "core")})
        assert blocks.load_blocks() is blocks.load_blocks()


class TestLoadGrants:
    def test_parses_each_row_into_conditions(self, monkeypatch):
        monkeypatch.setattr(
            blocks,
            "_read_commands_payload",
            lambda: {
                "commands": {
                    "codex list": ["memory.cli"],
                    "board add": ["quests", "pseudo:cli"],
                }
            },
        )
        grants = blocks.load_grants()
        assert set(grants) == {"codex list", "board add"}
        assert [c.text for c in grants["board add"]] == ["quests", "pseudo:cli"]

    def test_a_row_with_no_grant_is_a_build_defect(self, monkeypatch):
        monkeypatch.setattr(
            blocks, "_read_commands_payload", lambda: {"commands": {"codex list": []}}
        )
        with pytest.raises(BlockDefect, match="commands.yaml"):
            blocks.load_grants()

    def test_an_unknown_condition_is_a_build_defect(self, monkeypatch):
        monkeypatch.setattr(
            blocks, "_read_commands_payload", lambda: {"commands": {"codex list": ["maybe"]}}
        )
        with pytest.raises(BlockDefect, match="commands.yaml"):
            blocks.load_grants()

    def test_the_payload_must_match_the_schema(self, monkeypatch):
        monkeypatch.setattr(blocks, "_read_commands_payload", lambda: {"rows": []})
        with pytest.raises(BlockDefect, match="commands.yaml"):
            blocks.load_grants()

    def test_the_shipped_table_loads_and_every_condition_parses(self):
        grants = blocks.load_grants()
        assert grants
        assert all(conditions for conditions in grants.values())


# ---------------------------------------------------------------------------
# Condition grammar
# ---------------------------------------------------------------------------


class TestConditionGrammar:
    @pytest.mark.parametrize(
        "text",
        [
            "memory",
            "doctrines",
            "artifacts",
            "watchers",
            "quests",
            "route=cli",
            "route=harness",
            "memory.cli",
            "watchers.harness",
            "cap:validate",
            "cap:memory-search",
            "cap:memory-index",
            "pseudo:cli",
            "pseudo:skills",
        ],
    )
    def test_every_form_parses_and_keeps_its_text(self, text):
        assert parse_condition(text).text == text

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "plugins",
            "route=off",
            "route=native",
            "route",
            "memory.read=cli",
            "memory.read",
            "memory.sideways",
            "memory.native",
            "cap:nothing",
            "cap:watchers-validate",
            "pseudo:nothing",
            "pseudo:validate",
            "pseudo:link",
            "quests.cli",
            "memory and doctrines",
            "not memory",
            "memory or doctrines",
            " memory",
            "Memory",
        ],
    )
    def test_an_unknown_form_raises(self, text):
        with pytest.raises(ValueError, match="condition"):
            parse_condition(text)


# ---------------------------------------------------------------------------
# survives
# ---------------------------------------------------------------------------


class TestSurvives:
    def test_core_survives_everything(self):
        block = _block(feature="core")
        assert survives(block, HARNESS_BARE)
        assert survives(block, FULL)

    def test_doctrines_and_artifacts_blocks_always_survive(self):
        for feature in ("doctrines", "artifacts"):
            assert survives(_block(feature=feature), HARNESS_BARE)

    def test_a_feature_block_needs_its_feature_on(self):
        block = _block(feature="memory")
        assert survives(block, HARNESS_MEMORY)
        assert not survives(block, HARNESS_BARE)

    def test_quests_follows_its_flag_alone(self):
        block = _block(feature="quests")
        assert survives(block, HARNESS_QUESTS)
        assert not survives(block, HARNESS_BARE)

    @pytest.mark.parametrize(
        ("profile", "expected"),
        [(HARNESS_MEMORY, False), (CLI_MEMORY, True), (HARNESS_BARE, False)],
    )
    def test_route_pins_the_global_route(self, profile, expected):
        block = _block(feature="memory", route="cli")
        assert survives(block, profile) is expected

    def test_a_route_on_a_core_feature_follows_the_route_alone(self):
        block = _block(feature="doctrines", route="harness")
        assert survives(block, HARNESS_BARE)
        assert not survives(block, CLI_BARE)

    def test_capabilities_must_all_be_on(self):
        block = _block(feature="memory", capabilities="[memory-search, memory-index]")
        assert survives(block, HARNESS_MEMORY_FULL)
        assert not survives(block, HARNESS_MEMORY)

    def test_validate_is_on_everywhere(self):
        block = _block(feature="core", capabilities="[validate]")
        assert survives(block, HARNESS_BARE)

    def test_a_capability_of_a_dead_feature_is_off(self):
        block = _block(feature="core", capabilities="[memory-index]")
        stale = Profile(route=Route.CLI, memory=False, memory_index=True)
        assert not survives(block, stale)

    def test_every_requires_must_hold(self):
        block = _block(feature="core", requires="[memory, quests]")
        assert survives(block, FULL)
        assert not survives(block, HARNESS_MEMORY)

    def test_any_unless_that_holds_removes_the_block(self):
        block = _block(feature="core", unless="[quests, cap:memory-index]")
        assert survives(block, HARNESS_MEMORY)
        assert not survives(block, HARNESS_MEMORY_FULL)
        assert not survives(block, HARNESS_QUESTS)

    def test_requires_and_unless_combine(self):
        block = _block(feature="core", requires="[memory.cli]", unless="[quests]")
        assert survives(block, CLI_MEMORY)
        assert not survives(block, FULL)

    @pytest.mark.parametrize(
        ("condition", "profile", "expected"),
        [
            ("pseudo:cli", HARNESS_BARE, False),
            ("pseudo:cli", HARNESS_MEMORY, False),
            ("pseudo:cli", HARNESS_QUESTS, True),
            ("pseudo:cli", CLI_BARE, True),
            ("pseudo:cli", HARNESS_MEMORY_FULL, True),
        ],
    )
    def test_pseudo_cli_follows_what_is_taught(self, condition, profile, expected):
        block = _block(feature="core", requires=f"[{condition}]")
        assert survives(block, profile) is expected

    def test_pseudo_skills_is_the_callers_flag(self):
        block = _block(feature="core", requires="[pseudo:skills]")
        assert not survives(block, FULL)
        assert survives(block, FULL, skills_installed=True)

    def test_feature_route_conditions_need_the_feature_and_the_route(self):
        assert survives(_block(feature="core", requires="[memory.cli]"), CLI_MEMORY)
        assert not survives(_block(feature="core", requires="[memory.cli]"), HARNESS_MEMORY)
        assert not survives(_block(feature="core", requires="[memory.cli]"), CLI_BARE)
        assert survives(_block(feature="core", requires="[doctrines.harness]"), HARNESS_BARE)


# ---------------------------------------------------------------------------
# assemble and join
# ---------------------------------------------------------------------------


class TestHolds:
    """`holds` evaluates one condition string, the way a block gate does."""

    def test_a_feature_id_is_true_when_the_feature_is_on(self):
        assert blocks.holds("memory", HARNESS_MEMORY)
        assert not blocks.holds("memory", HARNESS_BARE)
        assert blocks.holds("doctrines", HARNESS_BARE)

    def test_a_route_condition_follows_the_profile(self):
        assert blocks.holds("route=cli", CLI_BARE)
        assert not blocks.holds("route=cli", HARNESS_BARE)
        assert blocks.holds("memory.cli", CLI_MEMORY)
        assert not blocks.holds("memory.cli", HARNESS_MEMORY)

    def test_a_capability_needs_its_feature(self):
        assert blocks.holds("cap:memory-index", HARNESS_MEMORY_FULL)
        assert not blocks.holds("cap:memory-index", HARNESS_MEMORY)
        assert blocks.holds("cap:validate", HARNESS_BARE)

    def test_pseudo_conditions_are_evaluated(self):
        assert blocks.holds("pseudo:cli", CLI_MEMORY)
        assert not blocks.holds("pseudo:cli", HARNESS_MEMORY)
        assert blocks.holds("pseudo:skills", FULL, skills_installed=True)

    def test_an_unknown_form_raises(self):
        with pytest.raises(ValueError):
            blocks.holds("memory or doctrines", FULL)


class TestAssemble:
    def _catalogue(self) -> dict[str, Block]:
        return {
            b.id: b
            for b in (
                _block("a", "core", body="A"),
                _block("b", "memory", body="B"),
                _block("c", "doctrines", body="C"),
            )
        }

    def test_returns_survivors_in_list_order(self):
        result = assemble(["c", "a", "b"], FULL, blocks=self._catalogue())
        assert [b.id for b in result] == ["c", "a", "b"]

    def test_drops_the_blocks_that_do_not_survive(self):
        result = assemble(["a", "b", "c"], HARNESS_BARE, blocks=self._catalogue())
        assert [b.id for b in result] == ["a", "c"]

    def test_the_bare_core_drops_the_optional_features(self):
        result = assemble(["a", "b", "c"], HARNESS_MEMORY, blocks=self._catalogue())
        assert [b.id for b in result] == ["a", "b", "c"]

    def test_an_unknown_id_raises_naming_it(self):
        with pytest.raises(ValueError, match="nope"):
            assemble(["a", "nope"], FULL, blocks=self._catalogue())

    def test_skills_installed_reaches_the_gate(self):
        table = {"t": _block("t", "core", requires="[pseudo:skills]")}
        assert assemble(["t"], FULL, blocks=table) == []
        assert len(assemble(["t"], FULL, blocks=table, skills_installed=True)) == 1


class TestAssembleUnknownId:
    def test_even_a_block_that_would_not_survive_must_exist(self):
        table = {"a": _block("a", "memory")}
        with pytest.raises(ValueError, match="ghost"):
            assemble(["a", "ghost"], HARNESS_BARE, blocks=table)


class TestJoin:
    def test_empty_input_is_the_empty_string(self):
        assert join([]) == ""

    def test_blocks_are_separated_by_one_blank_line(self):
        assert join([_block("a", body="A"), _block("b", body="B")]) == "A\n\nB\n"

    def test_a_tight_block_joins_without_a_blank_line(self):
        first, second = _block("a", body="- one"), _block("b", body="- two", glue="tight")
        assert join([first, second]) == "- one\n- two\n"

    def test_a_tight_first_block_has_nothing_to_join_to(self):
        assert join([_block("a", body="- one", glue="tight")]) == "- one\n"

    def test_leading_and_trailing_blank_lines_never_double_the_gap(self):
        first = parse_block(_text("a", body="\n\nA\n\n\n"), source="a.md")
        second = parse_block(_text("b", body="\n\nB\n\n"), source="b.md")
        assert join([first, second]) == "A\n\nB\n"

    def test_exactly_one_final_newline(self):
        assert join([_block("a", body="A\n\n\n")]).endswith("A\n")
        assert not join([_block("a", body="A")]).endswith("\n\n")

    def test_the_line_count_includes_separators(self):
        text = join([_block("a", body="A\nA2"), _block("b", body="B")])
        assert len(text.splitlines()) == 4


# ---------------------------------------------------------------------------
# commands_in
# ---------------------------------------------------------------------------


class TestCommandsIn:
    def test_an_inline_span_yields_group_and_verb(self):
        assert commands_in("Run `lore codex list` first.") == ("codex list",)

    def test_prose_outside_a_span_is_not_extracted(self):
        assert commands_in("Run lore codex list first.") == ()

    def test_every_group_word_takes_the_next_word_as_its_verb(self):
        text = " ".join(
            f"`lore {g} show`"
            for g in ("codex", "rite", "glossary", "index", "doctrine", "artifact", "watcher", "board")
        )
        assert commands_in(text) == tuple(
            f"{g} show"
            for g in ("codex", "rite", "glossary", "index", "doctrine", "artifact", "watcher", "board")
        )

    def test_arguments_after_the_verb_are_ignored(self):
        assert commands_in("`lore codex show <id> --json`") == ("codex show",)

    def test_health_collects_each_scope_token(self):
        assert commands_in("`lore health --scope codex rites glossary`") == (
            "health --scope codex",
            "health --scope rites",
            "health --scope glossary",
        )

    def test_health_scope_tokens_stop_at_the_next_flag_or_non_word(self):
        assert commands_in("`lore health --scope codex --json`") == ("health --scope codex",)
        assert commands_in("`lore health --scope codex <id>`") == ("health --scope codex",)

    def test_bare_health(self):
        assert commands_in("`lore health`") == ("health",)

    def test_new_collapses_to_new_whatever_follows(self):
        assert commands_in("`lore new quest x` then `lore new mission y`") == ("new",)

    def test_top_level_commands_are_their_own_phrase(self):
        assert commands_in("`lore claim q-1` `lore done q-1` `lore impacts`") == (
            "claim",
            "done",
            "impacts",
        )

    def test_global_flags_before_the_command_are_skipped(self):
        assert commands_in("`lore --json list`") == ("list",)

    def test_a_flag_alone_is_its_own_phrase(self):
        assert commands_in("`lore --help` and `lore --version`") == ("--help", "--version")

    def test_init_is_a_command(self):
        assert commands_in("`lore init`") == ("init",)

    def test_a_group_without_a_verb_is_the_bare_group(self):
        assert commands_in("`lore codex --help`") == ("codex",)

    def test_order_of_first_appearance_without_duplicates(self):
        assert commands_in("`lore rite list` `lore codex list` `lore rite list`") == (
            "rite list",
            "codex list",
        )

    def test_fenced_block_lines_are_code(self):
        text = "Text\n```bash\nlore codex search foo\nlore index build\n```\nafter lore codex show\n"
        assert commands_in(text) == ("codex search", "index build")

    def test_several_commands_on_one_line(self):
        assert commands_in("`lore codex list && lore rite list`") == ("codex list", "rite list")

    def test_lore_inside_a_path_or_a_longer_word_is_not_a_command(self):
        assert commands_in("`.lore/codex/x.md` `explore codex list` `lore-cli codex list`") == ()

    def test_an_unrelated_span_is_ignored(self):
        assert commands_in("`ls -la` and `git status`") == ()

    def test_a_span_naming_lore_without_a_command_is_ignored(self):
        assert commands_in("`lore` is the tool") == ()


class TestBareCommands:
    def test_prose_mentions_are_reported(self):
        assert blocks.bare_commands("Use lore codex list to look.") == ("lore codex",)

    def test_code_spans_are_not_bare(self):
        assert blocks.bare_commands("Use `lore codex list` to look.") == ()

    def test_fenced_lines_are_not_bare(self):
        assert blocks.bare_commands("```\nlore codex list\n```\n") == ()

    def test_a_path_is_not_a_command(self):
        assert blocks.bare_commands("Look in .lore/codex for it.") == ()

    def test_the_word_lore_alone_is_not_a_command(self):
        assert blocks.bare_commands("Lore is a memory tool; the lore project.") == ()


# ---------------------------------------------------------------------------
# leaked_commands
# ---------------------------------------------------------------------------

GRANTS_PAYLOAD = {
    "commands": {
        "--help": ["pseudo:cli"],
        "codex list": ["memory.cli"],
        "codex search": ["cap:memory-search"],
        "codex map": ["cap:memory-graph"],
        "health": ["cap:validate"],
        "board add": ["quests"],
        "doctrine show": ["doctrines.cli"],
    }
}


@pytest.fixture()
def fixture_grants(monkeypatch):
    monkeypatch.setattr(blocks, "_read_commands_payload", lambda: GRANTS_PAYLOAD)
    return blocks.load_grants()


class TestLeakedCommands:
    def test_nothing_leaks_when_there_are_no_commands(self, fixture_grants):
        assert leaked_commands("No commands here.", HARNESS_BARE) == ()

    def test_a_route_grant_follows_the_route_and_the_feature(self, fixture_grants):
        text = "`lore codex list`"
        assert leaked_commands(text, HARNESS_MEMORY) == ("codex list",)
        assert leaked_commands(text, CLI_BARE) == ("codex list",)
        assert leaked_commands(text, CLI_MEMORY) == ()

    def test_a_core_feature_route_grant_follows_the_route_alone(self, fixture_grants):
        text = "`lore doctrine show`"
        assert leaked_commands(text, HARNESS_BARE) == ("doctrine show",)
        assert leaked_commands(text, CLI_BARE) == ()

    def test_a_capability_grant_follows_the_capability_on_any_route(self, fixture_grants):
        text = "`lore codex search`"
        assert leaked_commands(text, HARNESS_MEMORY) == ("codex search",)
        assert leaked_commands(text, HARNESS_MEMORY_FULL) == ()

    def test_health_is_granted_to_every_profile(self, fixture_grants):
        for profile in (HARNESS_BARE, CLI_BARE, HARNESS_MEMORY, FULL):
            assert leaked_commands("`lore health`", profile) == ()

    def test_pseudo_cli_is_not_taught_to_the_bare_harness(self, fixture_grants):
        assert leaked_commands("`lore --help`", HARNESS_BARE) == ("--help",)
        assert leaked_commands("`lore --help`", CLI_BARE) == ()

    def test_quests_grant(self, fixture_grants):
        text = "`lore board add`"
        assert leaked_commands(text, HARNESS_BARE) == ("board add",)
        assert leaked_commands(text, HARNESS_QUESTS) == ()

    def test_any_one_grant_is_enough(self, monkeypatch):
        monkeypatch.setattr(
            blocks,
            "_read_commands_payload",
            lambda: {"commands": {"doctrine show": ["quests", "doctrines.cli"]}},
        )
        assert leaked_commands("`lore doctrine show`", HARNESS_QUESTS) == ()
        assert leaked_commands("`lore doctrine show`", CLI_BARE) == ()
        assert leaked_commands("`lore doctrine show`", HARNESS_BARE) == ("doctrine show",)

    def test_a_phrase_with_no_row_always_leaks(self, fixture_grants):
        assert leaked_commands("`lore codex frobnicate`", FULL) == ("codex frobnicate",)

    def test_a_capability_of_a_dead_feature_does_not_grant(self, fixture_grants):
        stale = Profile(memory=False, memory_graph=True)
        assert leaked_commands("`lore codex map`", stale) == ("codex map",)

    def test_skills_installed_reaches_pseudo_skills(self, monkeypatch):
        monkeypatch.setattr(
            blocks, "_read_commands_payload", lambda: {"commands": {"init": ["pseudo:skills"]}}
        )
        assert leaked_commands("`lore init`", FULL) == ("init",)
        assert leaked_commands("`lore init`", FULL, skills_installed=True) == ()

    def test_an_explicit_grants_mapping_replaces_the_shipped_table(self):
        grants = {"codex list": (parse_condition("memory"),)}
        assert leaked_commands("`lore codex list`", HARNESS_MEMORY, grants=grants) == ()
        assert leaked_commands("`lore codex list`", HARNESS_BARE, grants=grants) == ("codex list",)


# ---------------------------------------------------------------------------
# max_lines
# ---------------------------------------------------------------------------


def _body(lines: int) -> str:
    return "\n".join(f"line {i}" for i in range(lines))


def _brute_force(ids, table) -> int:
    """The largest rendered-size sum over every profile of the small variable space."""
    best = 0
    for route, memory, search, index, quests in itertools.product(
        list(Route), (False, True), (False, True), (False, True), (False, True)
    ):
        profile = Profile(
            route=route,
            memory=memory,
            memory_search=search,
            memory_index=index,
            quests=quests,
        )
        total = sum(
            len(table[i].body.splitlines()) + (0 if table[i].glue == "tight" else 1)
            for i in ids
            if survives(table[i], profile)
        )
        best = max(best, total)
    return best


def _random_table(rng: random.Random, count: int, *, allow_pseudo: bool) -> dict[str, Block]:
    gates = [
        {"feature": "core"},
        {"feature": "memory"},
        {"feature": "memory", "route": "harness"},
        {"feature": "memory", "route": "cli"},
        {"feature": "memory", "capabilities": "[memory-search]"},
        {"feature": "memory", "capabilities": "[memory-search, memory-index]"},
        {"feature": "doctrines"},
        {"feature": "doctrines", "route": "harness"},
        {"feature": "doctrines", "unless": "[memory.cli]"},
        {"feature": "core", "requires": "[memory, quests]"},
        {"feature": "core", "requires": "[route=cli]", "unless": "[cap:memory-index]"},
    ]
    if allow_pseudo:
        gates += [
            {"feature": "memory", "requires": "[pseudo:cli]"},
            {"feature": "quests", "requires": "[pseudo:cli]"},
            {"feature": "core", "unless": "[pseudo:cli]"},
        ]
    table: dict[str, Block] = {}
    for n in range(count):
        gate = dict(rng.choice(gates))
        feature = gate.pop("feature")
        glue = rng.choice(["blank", "blank", "tight"])
        table[f"b{n}"] = _block(f"b{n}", feature, body=_body(rng.randint(1, 5)), glue=glue, **gate)
    return table


class TestMaxLines:
    def test_empty_is_zero(self):
        assert max_lines([], {}) == 0

    def test_a_single_unconditional_block_counts_its_lines_and_separator(self):
        table = {"a": _block("a", body=_body(3))}
        assert max_lines(["a"], table) == 4

    def test_a_tight_block_has_no_separator(self):
        table = {"a": _block("a", body=_body(3), glue="tight")}
        assert max_lines(["a"], table) == 3

    def test_mutually_exclusive_blocks_count_once(self):
        table = {
            "h": _block("h", "memory", body=_body(3), route="harness"),
            "c": _block("c", "memory", body=_body(5), route="cli"),
        }
        assert max_lines(["h", "c"], table) == 6

    def test_independent_components_add(self):
        table = {
            "m": _block("m", "memory", body=_body(2)),
            "d": _block("d", "doctrines", body=_body(4)),
        }
        assert max_lines(["m", "d"], table) == 3 + 5

    def test_a_block_that_can_never_survive_adds_nothing(self):
        table = {
            "a": _block("a", "memory", route="cli", unless="[memory.cli]", body=_body(9)),
        }
        assert max_lines(["a"], table) == 0

    def test_unknown_id_raises(self):
        with pytest.raises(ValueError, match="ghost"):
            max_lines(["ghost"], {})

    @pytest.mark.parametrize("seed", range(25))
    def test_equals_brute_force_when_no_pseudo_relaxation_is_involved(self, seed):
        rng = random.Random(seed)
        table = _random_table(rng, rng.randint(2, 9), allow_pseudo=False)
        ids = list(table)
        assert max_lines(ids, table) == _brute_force(ids, table)

    @pytest.mark.parametrize("seed", range(25))
    def test_is_never_below_brute_force_with_pseudo_conditions(self, seed):
        rng = random.Random(1000 + seed)
        table = _random_table(rng, rng.randint(2, 9), allow_pseudo=True)
        ids = list(table)
        assert max_lines(ids, table) >= _brute_force(ids, table)


# ---------------------------------------------------------------------------
# Module boundary
# ---------------------------------------------------------------------------


class TestModuleBoundary:
    def test_imports_only_initplan_from_lore_at_module_level(self):
        tree = ast.parse(BLOCKS_SOURCE.read_text(encoding="utf-8"))
        offenders = []
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("lore"):
                if node.module != "lore.initplan":
                    offenders.append(node.module)
            elif isinstance(node, ast.Import):
                offenders += [a.name for a in node.names if a.name.startswith("lore")]
        assert offenders == []
