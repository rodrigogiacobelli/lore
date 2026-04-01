"""Tests for lore.validators.

Covers all five functions defined in lore.validators:

  - validate_message(message)    → str | None
  - validate_entity_id(eid)      → str | None
  - validate_mission_id(mid)     → str | None
  - validate_priority(priority)  → str | None
  - route_entity(eid)            → tuple[str, str]
"""

import pytest

from lore.validators import (
    route_entity,
    validate_entity_id,
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
