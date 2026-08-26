"""Tests for lore.validators.

Covers all five functions defined in lore.validators:

  - validate_message(message)    → str | None
  - validate_entity_id(eid)      → str | None
  - validate_mission_id(mid)     → str | None
  - validate_priority(priority)  → str | None
  - route_entity(eid)            → tuple[str, str]
"""

from pathlib import Path


from lore.validators import (
    route_entity,
    validate_entity_id,
    validate_group,
    validate_message,
    validate_mission_id,
    validate_priority,
)


# ---------------------------------------------------------------------------
# validate_message
# ---------------------------------------------------------------------------


class TestValidateMessage:
    """validate_message(message) → error string or None."""

    def test_validate_message_rejects_empty_string(self):
        result = validate_message("")
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0

    def test_validate_message_rejects_whitespace_only_string(self):
        result = validate_message("   ")
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0

    def test_validate_message_rejects_tab_only_string(self):
        result = validate_message("\t\n")
        assert result is not None
        assert isinstance(result, str)

    def test_validate_message_returns_none_for_valid_message(self):
        result = validate_message("This is a valid board message.")
        assert result is None

    def test_validate_message_returns_none_for_single_character(self):
        result = validate_message("x")
        assert result is None

    def test_validate_message_error_mentions_empty(self):
        result = validate_message("")
        assert result is not None
        assert "empty" in result.lower()

    def test_validate_message_whitespace_error_mentions_empty(self):
        result = validate_message("   ")
        assert result is not None
        assert "empty" in result.lower()


# ---------------------------------------------------------------------------
# validate_entity_id
# ---------------------------------------------------------------------------


class TestValidateEntityId:
    """validate_entity_id(eid) → error string or None."""

    # Valid inputs — expect None

    def test_validate_entity_id_accepts_valid_quest_id(self):
        result = validate_entity_id("q-a1b2")
        assert result is None

    def test_validate_entity_id_accepts_valid_quest_id_six_chars(self):
        result = validate_entity_id("q-a1b2c3")
        assert result is None

    def test_validate_entity_id_accepts_valid_scoped_mission_id(self):
        result = validate_entity_id("q-a1b2/m-f3c1")
        assert result is None

    def test_validate_entity_id_accepts_valid_scoped_mission_id_six_hex(self):
        result = validate_entity_id("q-aabbcc/m-ddeeff")
        assert result is None

    def test_validate_entity_id_accepts_valid_standalone_mission_id(self):
        result = validate_entity_id("m-f3c1")
        assert result is None

    def test_validate_entity_id_accepts_standalone_mission_id_five_chars(self):
        result = validate_entity_id("m-a1b2c")
        assert result is None

    # Invalid inputs — expect error string naming the bad ID

    def test_validate_entity_id_rejects_completely_free_form_string(self):
        result = validate_entity_id("notanid")
        assert result is not None
        assert isinstance(result, str)
        assert "notanid" in result

    def test_validate_entity_id_rejects_plausible_wrong_prefix(self):
        result = validate_entity_id("x-1234")
        assert result is not None
        assert "x-1234" in result

    def test_validate_entity_id_rejects_wrong_prefix_z(self):
        result = validate_entity_id("z-abcd")
        assert result is not None
        assert "z-abcd" in result

    def test_validate_entity_id_rejects_non_hex_characters_in_quest_id(self):
        # g-z are not valid hex digits
        result = validate_entity_id("q-ghij")
        assert result is not None
        assert "q-ghij" in result

    def test_validate_entity_id_rejects_quest_id_too_short(self):
        result = validate_entity_id("q-ab")
        assert result is not None
        assert "q-ab" in result

    def test_validate_entity_id_rejects_empty_string(self):
        result = validate_entity_id("")
        assert result is not None
        assert isinstance(result, str)

    def test_validate_entity_id_error_contains_invalid_format_message(self):
        result = validate_entity_id("notanid")
        assert result is not None
        # Error must identify the supplied value
        assert "notanid" in result

    def test_validate_entity_id_error_contains_format_indicator(self):
        result = validate_entity_id("bad")
        assert result is not None
        # Error must indicate it is a format/ID problem
        lower = result.lower()
        assert "invalid" in lower or "format" in lower or "id" in lower


# ---------------------------------------------------------------------------
# validate_mission_id
# ---------------------------------------------------------------------------


class TestValidateMissionId:
    """validate_mission_id(mid) → error string or None."""

    # Valid mission IDs — expect None

    def test_validate_mission_id_accepts_valid_scoped_mission_id(self):
        result = validate_mission_id("q-a1b2/m-f3c1")
        assert result is None

    def test_validate_mission_id_accepts_valid_standalone_mission_id(self):
        result = validate_mission_id("m-f3c1")
        assert result is None

    def test_validate_mission_id_accepts_standalone_mission_id_five_hex(self):
        result = validate_mission_id("m-a1b2c")
        assert result is None

    # Quest ID is NOT a valid mission ID

    def test_validate_mission_id_rejects_quest_id(self):
        result = validate_mission_id("q-a1b2")
        assert result is not None
        assert isinstance(result, str)

    def test_validate_mission_id_rejects_quest_id_names_the_bad_id(self):
        result = validate_mission_id("q-a1b2")
        assert result is not None
        assert "q-a1b2" in result

    # Free-form strings

    def test_validate_mission_id_rejects_free_form_string(self):
        result = validate_mission_id("not-a-mission")
        assert result is not None
        assert isinstance(result, str)

    def test_validate_mission_id_rejects_free_form_string_names_bad_id(self):
        result = validate_mission_id("bad-id")
        assert result is not None
        assert "bad-id" in result

    def test_validate_mission_id_rejects_empty_string(self):
        result = validate_mission_id("")
        assert result is not None
        assert isinstance(result, str)

    def test_validate_mission_id_error_mentions_mission_or_format(self):
        result = validate_mission_id("q-a1b2")
        assert result is not None
        lower = result.lower()
        assert "mission" in lower or "format" in lower or "invalid" in lower


# ---------------------------------------------------------------------------
# validate_priority
# ---------------------------------------------------------------------------


class TestValidatePriority:
    """validate_priority(priority) → error string or None."""

    # Boundary values — expect None

    def test_validate_priority_accepts_zero(self):
        result = validate_priority(0)
        assert result is None

    def test_validate_priority_accepts_four(self):
        result = validate_priority(4)
        assert result is None

    def test_validate_priority_accepts_middle_value(self):
        result = validate_priority(2)
        assert result is None

    def test_validate_priority_accepts_one(self):
        result = validate_priority(1)
        assert result is None

    def test_validate_priority_accepts_three(self):
        result = validate_priority(3)
        assert result is None

    def test_validate_priority_accepts_none(self):
        result = validate_priority(None)
        assert result is None

    # Out-of-range values — expect error string

    def test_validate_priority_rejects_negative_one(self):
        result = validate_priority(-1)
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0

    def test_validate_priority_rejects_five(self):
        result = validate_priority(5)
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0

    def test_validate_priority_rejects_large_negative(self):
        result = validate_priority(-100)
        assert result is not None
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# US-004: validate_chaos_threshold unit stubs
# ---------------------------------------------------------------------------


# Unit — validate_chaos_threshold returns (True, None) for boundary and mid-range valid values
# conceptual-workflows-codex-chaos (validate_chaos_threshold: 30 and 100 are valid boundaries per FR-8/FR-9)
def test_validate_chaos_threshold_valid_values():
    # validate_chaos_threshold(30) == (True, None)
    # validate_chaos_threshold(50) == (True, None)
    # validate_chaos_threshold(100) == (True, None)
    pass


# Unit — validate_chaos_threshold returns (False, message) for value=29
# conceptual-workflows-codex-chaos (validate_chaos_threshold: 29 is below minimum floor of 30)
def test_validate_chaos_threshold_returns_false_for_29():
    # ok, msg = validate_chaos_threshold(29)
    # assert ok is False; assert "30" in msg and "100" in msg
    pass


# Unit — validate_chaos_threshold returns (False, message) for value=0
# conceptual-workflows-codex-chaos (validate_chaos_threshold: 0 is far below minimum)
def test_validate_chaos_threshold_returns_false_for_0():
    # ok, msg = validate_chaos_threshold(0)
    # assert ok is False
    pass


# Unit — validate_chaos_threshold returns (False, message) for value=-1
# conceptual-workflows-codex-chaos (validate_chaos_threshold: negative values are invalid)
def test_validate_chaos_threshold_returns_false_for_negative():
    # ok, msg = validate_chaos_threshold(-1)
    # assert ok is False
    pass


# Unit — validate_chaos_threshold returns (False, message) for value=101
# conceptual-workflows-codex-chaos (validate_chaos_threshold: 101 exceeds ceiling of 100 per FR-9)
def test_validate_chaos_threshold_returns_false_for_101():
    # ok, msg = validate_chaos_threshold(101)
    # assert ok is False
    pass


# Unit — validate_chaos_threshold returns (False, message) for value=200
# conceptual-workflows-codex-chaos (validate_chaos_threshold: values far above ceiling also rejected)
def test_validate_chaos_threshold_returns_false_for_200():
    # ok, msg = validate_chaos_threshold(200)
    # assert ok is False
    pass

    def test_validate_priority_rejects_large_positive(self):
        result = validate_priority(100)
        assert result is not None
        assert isinstance(result, str)

    def test_validate_priority_error_mentions_valid_range(self):
        result = validate_priority(-1)
        assert result is not None
        assert "-1" in result or "Priority" in result

    def test_validate_priority_error_for_five_mentions_value(self):
        result = validate_priority(5)
        assert result is not None
        assert "5" in result


# ---------------------------------------------------------------------------
# route_entity
# ---------------------------------------------------------------------------


class TestRouteEntity:
    """route_entity(eid) → (table, id_col) tuple."""

    def test_route_entity_quest_id_returns_quests_table(self):
        table, id_col = route_entity("q-a1b2")
        assert table == "quests"

    def test_route_entity_quest_id_returns_id_column(self):
        table, id_col = route_entity("q-a1b2")
        assert id_col == "id"

    def test_route_entity_scoped_mission_id_returns_missions_table(self):
        table, id_col = route_entity("q-a1b2/m-f3c1")
        assert table == "missions"

    def test_route_entity_scoped_mission_id_returns_id_column(self):
        table, id_col = route_entity("q-a1b2/m-f3c1")
        assert id_col == "id"

    def test_route_entity_standalone_mission_id_returns_missions_table(self):
        table, id_col = route_entity("m-f3c1")
        assert table == "missions"

    def test_route_entity_standalone_mission_id_returns_id_column(self):
        table, id_col = route_entity("m-f3c1")
        assert id_col == "id"

    def test_route_entity_quest_id_six_hex_chars_returns_quests(self):
        table, id_col = route_entity("q-aabbcc")
        assert table == "quests"
        assert id_col == "id"

    def test_route_entity_standalone_mission_five_hex_chars_returns_missions(self):
        table, id_col = route_entity("m-a1b2c")
        assert table == "missions"
        assert id_col == "id"

    def test_route_entity_returns_tuple_of_two_strings(self):
        result = route_entity("q-a1b2")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(v, str) for v in result)


# ---------------------------------------------------------------------------
# US-005: validate_group
# ---------------------------------------------------------------------------


class TestValidateGroup:
    """validate_group(group) → error string or None."""

    def test_none_returns_none(self):
        assert validate_group(None) is None

    def test_valid_single_segment(self):
        assert validate_group("a") is None

    def test_valid_nested(self):
        assert validate_group("a/b/c") is None

    def test_valid_hyphen_underscore(self):
        assert validate_group("a-b/c_d") is None

    def test_empty_string_error(self):
        err = validate_group("")
        assert err is not None
        assert "empty" in err

    def test_dotdot_root_error(self):
        err = validate_group("..")
        assert err is not None
        assert "path traversal" in err

    def test_dotdot_prefix_error(self):
        err = validate_group("../x")
        assert err is not None
        assert "path traversal" in err

    def test_dotdot_suffix_error(self):
        err = validate_group("x/..")
        assert err is not None
        assert "path traversal" in err

    def test_backslash_error_leading(self):
        err = validate_group("\\x")
        assert err is not None
        assert "backslash" in err

    def test_backslash_error_middle(self):
        err = validate_group("a\\b")
        assert err is not None
        assert "backslash" in err

    def test_leading_slash_error(self):
        err = validate_group("/x")
        assert err is not None
        assert ("absolute" in err or "leading" in err)

    def test_trailing_slash_error(self):
        err = validate_group("x/")
        assert err is not None
        assert "trailing" in err

    def test_empty_segment_error(self):
        err = validate_group("a//b")
        assert err is not None
        assert "empty segment" in err

    def test_bad_chars_in_segment_error(self):
        err = validate_group("a/!/b")
        assert err is not None
        assert ("segment" in err or "characters" in err)

    def test_leading_hyphen_in_segment_error(self):
        # _NAME_RE requires alphanumeric start
        assert validate_group("-a") is not None


# ---------------------------------------------------------------------------
# validate_rite_id — raising validator for rite names (new/edit/delete)
# Spec: conceptual-workflows-rite-crud "Name validation" + decisions-011-api-parity-with-cli
# ---------------------------------------------------------------------------


class TestValidateRiteId:
    """validate_rite_id(s): accepts valid slugs, raises on invalid."""

    def test_accepts_hyphenated_slug(self):
        from lore.validators import validate_rite_id

        # valid — must not raise
        validate_rite_id("issue-refund")

    def test_accepts_underscore_and_digit(self):
        from lore.validators import validate_rite_id

        # valid — must not raise
        validate_rite_id("a_1")

    def test_accepts_alphanumeric_start(self):
        from lore.validators import validate_rite_id

        validate_rite_id("read-contact-info")

    def test_rejects_leading_hyphen(self):
        import pytest

        from lore.validators import validate_rite_id

        with pytest.raises(Exception):
            validate_rite_id("-lead")

    def test_rejects_space(self):
        import pytest

        from lore.validators import validate_rite_id

        with pytest.raises(Exception):
            validate_rite_id("has space")

    def test_rejects_slash(self):
        import pytest

        from lore.validators import validate_rite_id

        with pytest.raises(Exception):
            validate_rite_id("a/b")

    def test_rejects_empty(self):
        import pytest

        from lore.validators import validate_rite_id

        with pytest.raises(Exception):
            validate_rite_id("")

    def test_rejects_dot(self):
        import pytest

        from lore.validators import validate_rite_id

        with pytest.raises(Exception):
            validate_rite_id("dot.name")


def test_validators_has_no_lore_imports():
    """Enforces standards-dependency-inversion: validators.py must not import lore.*."""
    import ast

    src = (Path(__file__).parents[2] / "src/lore/validators.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or not node.module.startswith("lore")
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("lore")


def test_access_modes_constant_matches_the_access_mode_enum():
    """The two token sets are authored twice — pin them so they cannot drift.

    ``validators.py`` may not import ``lore.initplan`` (see
    ``test_validators_has_no_lore_imports``), so ``ACCESS_MODES`` restates what
    ``AccessMode`` declares. This test is the join.
    """
    from lore.initplan import AccessMode
    from lore.validators import ACCESS_MODES

    assert set(ACCESS_MODES) == {mode.value for mode in AccessMode}


# ---------------------------------------------------------------------------
# The four initialisation validators — interactive-init-us-017
#
# `--agent none` exclusivity is a business rule about a selection, not argv
# parsing, so it lives here and both `plan_init` and `cli.py` call it
# (decisions-011-api-parity-with-cli). These tests exercise the rules in
# isolation; the matched CLI/API pairs live in tests/e2e/test_error_handling.py.
#
# Spec: conceptual-workflows-validators — validator contracts
# ---------------------------------------------------------------------------


KNOWN_AGENT_IDS = ("agents-md", "claude", "cursor", "gemini", "none", "qwen")
ACCEPTED_FAMILIES = ("machinery", "memory", "workflow", "all", "none")


class TestValidateAccessMode:
    """validate_access_mode(mode) → None for the two tokens, a message otherwise."""

    def test_accepts_cli_and_native(self):
        from lore.validators import validate_access_mode

        assert validate_access_mode("cli") is None
        assert validate_access_mode("native") is None

    def test_rejects_an_unknown_token_naming_it_and_the_accepted_set(self):
        from lore.validators import validate_access_mode

        message = validate_access_mode("agentic")
        assert message is not None
        assert "agentic" in message
        assert "cli" in message and "native" in message

    def test_rejects_none_and_a_non_string(self):
        from lore.validators import validate_access_mode

        assert validate_access_mode(None) is not None
        assert validate_access_mode(7) is not None

    def test_the_accepted_set_mirrors_the_access_mode_enum(self):
        """`validators.py` may not import `lore.initplan`; this pins the two together."""
        from lore.initplan import AccessMode
        from lore.validators import ACCESS_MODES

        assert set(ACCESS_MODES) == {mode.value for mode in AccessMode}


class TestValidateSkillFamily:
    """validate_skill_family(family, accepted) → None for an accepted token."""

    def test_accepts_every_concrete_family_and_both_aggregates(self):
        from lore.validators import validate_skill_family

        for token in ACCEPTED_FAMILIES:
            assert validate_skill_family(token, ACCEPTED_FAMILIES) is None

    def test_rejects_an_unknown_token_naming_it_and_the_accepted_set(self):
        from lore.validators import validate_skill_family

        message = validate_skill_family("typo", ACCEPTED_FAMILIES)
        assert message is not None
        assert "typo" in message
        for token in ACCEPTED_FAMILIES:
            assert token in message

    def test_rejects_none_and_a_non_string(self):
        from lore.validators import validate_skill_family

        assert validate_skill_family(None, ACCEPTED_FAMILIES) is not None
        assert validate_skill_family(["memory"], ACCEPTED_FAMILIES) is not None

    def test_the_accepted_set_is_the_callers_not_a_hardcoded_one(self):
        """The catalogue is data; the validator never compiles a family list in."""
        from lore.validators import validate_skill_family

        assert validate_skill_family("memory", ("workflow",)) is not None
        assert validate_skill_family("workflow", ("workflow",)) is None


class TestValidateAgentId:
    """validate_agent_id(agent_id, known_ids) → None for a registry id."""

    def test_accepts_every_registry_id(self):
        from lore import agents
        from lore.validators import validate_agent_id

        known = agents.agent_ids()
        for agent_id in known:
            assert validate_agent_id(agent_id, known) is None

    def test_rejects_an_unknown_id_listing_the_known_ones(self):
        from lore.validators import validate_agent_id

        message = validate_agent_id("cline", KNOWN_AGENT_IDS)
        assert message == (
            "Unknown agent: 'cline'. Known agents: "
            "agents-md, claude, cursor, gemini, none, qwen."
        )

    def test_rejects_none_and_a_non_string(self):
        from lore.validators import validate_agent_id

        assert validate_agent_id(None, KNOWN_AGENT_IDS) is not None
        assert validate_agent_id(3, KNOWN_AGENT_IDS) is not None


class TestValidateAgentSelection:
    """validate_agent_selection(agents, known_ids) — the `none` exclusivity rule."""

    def test_accepts_the_empty_selection(self):
        from lore.validators import validate_agent_selection

        assert validate_agent_selection([], KNOWN_AGENT_IDS) is None

    def test_accepts_none_alone(self):
        from lore.validators import validate_agent_selection

        assert validate_agent_selection(["none"], KNOWN_AGENT_IDS) is None

    def test_accepts_any_combination_of_non_none_ids(self):
        from lore.validators import validate_agent_selection

        assert validate_agent_selection(["claude", "agents-md"], KNOWN_AGENT_IDS) is None
        assert (
            validate_agent_selection(
                ["claude", "agents-md", "gemini", "qwen", "cursor"], KNOWN_AGENT_IDS
            )
            is None
        )

    def test_rejects_none_combined_in_either_order(self):
        from lore.validators import validate_agent_selection

        expected = "--agent none cannot be combined with other agents."
        assert validate_agent_selection(["none", "claude"], KNOWN_AGENT_IDS) == expected
        assert validate_agent_selection(["claude", "none"], KNOWN_AGENT_IDS) == expected

    def test_an_unknown_id_is_reported_before_the_exclusivity_rule(self):
        from lore.validators import validate_agent_selection

        message = validate_agent_selection(["none", "cline"], KNOWN_AGENT_IDS)
        assert message is not None
        assert message.startswith("Unknown agent: 'cline'.")

    def test_duplicate_ids_are_not_an_error(self):
        from lore.validators import validate_agent_selection

        assert validate_agent_selection(["claude", "claude"], KNOWN_AGENT_IDS) is None
        assert validate_agent_selection(["none", "none"], KNOWN_AGENT_IDS) is None


class TestTheFourValidatorsFollowTheModuleContract:
    """Error-message-or-`None`, and no `click` anywhere near it."""

    def test_every_new_validator_returns_none_or_a_string(self):
        from lore.validators import (
            validate_access_mode,
            validate_agent_id,
            validate_agent_selection,
            validate_skill_family,
        )

        outcomes = [
            validate_access_mode("cli"),
            validate_access_mode("nope"),
            validate_skill_family("memory", ACCEPTED_FAMILIES),
            validate_skill_family("nope", ACCEPTED_FAMILIES),
            validate_agent_id("claude", KNOWN_AGENT_IDS),
            validate_agent_id("nope", KNOWN_AGENT_IDS),
            validate_agent_selection(["claude"], KNOWN_AGENT_IDS),
            validate_agent_selection(["none", "claude"], KNOWN_AGENT_IDS),
        ]
        assert all(item is None or isinstance(item, str) for item in outcomes)

    def test_validators_module_imports_no_click(self):
        import ast
        from pathlib import Path

        source = Path(__file__).resolve().parents[2] / "src" / "lore" / "validators.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders += [a.name for a in node.names if a.name.split(".")[0] == "click"]
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] == "click":
                    offenders.append(node.module)
        assert offenders == [], f"validators.py imports click: {offenders}"
