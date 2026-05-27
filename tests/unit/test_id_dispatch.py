"""Red tests for G12: CLI ID-shape dispatch helpers.

Spec source:
  lore codex show transient-public-api-facade-plan      # §G12
  lore codex show transient-public-api-facade-tech-spec # §3, §7

G12 introduces two CLI-local helpers that consolidate ID dispatch
inside ``src/lore/cli.py``:

* ``_emit_format_error(ctx, entity_id)`` — uniform format-error emission
  for both JSON and text modes. Replaces the inline duplicate string
  at cli.py:1893 / 1919 (CHANGED #8 — does not exist today).

* ``_classify_entity_id_with_db_fallback(project_root, entity_id)`` —
  wraps ``lore.validators.route_entity`` with a loose-quest-ID DB-probe
  fallback. Returns the table name (``"quests"`` or ``"missions"``) or
  ``None`` if classification is impossible (bad format AND DB miss).

The plan keeps ``route_entity`` STRICT (Review-Ledger KEPT). This file
pins both helpers' contracts plus the strictness invariant.

Red phase — every test MUST fail until G12 Green lands.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.conftest import insert_quest


CLI_PATH = Path(__file__).resolve().parents[2] / "src" / "lore" / "cli.py"


# ---------------------------------------------------------------------------
# route_entity strictness — proves the "KEPT" Review-Ledger row holds.
# ---------------------------------------------------------------------------


class TestRouteEntityStrict:
    """``route_entity`` rejects loose patterns (Spec §A: widen option rejected).

    Strict means: hex-only character class (``[0-9a-f]``), length 4–6, and
    the canonical anchors. Anything else raises ``ValueError``.
    """

    def test_quest_strict_hex_ok(self):
        from lore.validators import route_entity

        assert route_entity("q-abcd") == ("quests", "id")
        assert route_entity("q-abcdef") == ("quests", "id")

    def test_quest_non_hex_letters_rejected(self):
        from lore.validators import route_entity

        # 'g'..'z' are allowed by the loose pattern but NOT by strict.
        with pytest.raises(ValueError):
            route_entity("q-zzzz")
        with pytest.raises(ValueError):
            route_entity("q-ghij")

    def test_quest_too_short_rejected(self):
        from lore.validators import route_entity

        with pytest.raises(ValueError):
            route_entity("q-abc")

    def test_quest_too_long_rejected(self):
        from lore.validators import route_entity

        with pytest.raises(ValueError):
            route_entity("q-abcdefgh")

    def test_uppercase_hex_rejected(self):
        from lore.validators import route_entity

        with pytest.raises(ValueError):
            route_entity("q-ABCD")

    def test_mission_standalone_ok(self):
        from lore.validators import route_entity

        assert route_entity("m-abcd") == ("missions", "id")

    def test_mission_scoped_ok(self):
        from lore.validators import route_entity

        assert route_entity("q-aaaa/m-bbbb") == ("missions", "id")

    def test_unknown_prefix_rejected(self):
        from lore.validators import route_entity

        with pytest.raises(ValueError):
            route_entity("x-aaaa")

    def test_empty_rejected(self):
        from lore.validators import route_entity

        with pytest.raises(ValueError):
            route_entity("")

    def test_bare_prefix_rejected(self):
        from lore.validators import route_entity

        with pytest.raises(ValueError):
            route_entity("q-")

    def test_trailing_slash_rejected(self):
        from lore.validators import route_entity

        with pytest.raises(ValueError):
            route_entity("q-aaaa/")

    @pytest.mark.parametrize(
        "loose_id",
        ["q-zzzz", "q-1z2y", "q-0ghj"],
    )
    def test_loose_quest_ids_rejected_by_strict(self, loose_id: str):
        from lore.validators import route_entity, validate_quest_id_loose

        # Loose validator accepts (no error string)
        assert validate_quest_id_loose(loose_id) is None
        # Strict route_entity refuses
        with pytest.raises(ValueError):
            route_entity(loose_id)


# ---------------------------------------------------------------------------
# _classify_entity_id_with_db_fallback — symbol + behaviour
# ---------------------------------------------------------------------------


class TestClassifyEntityIdSymbol:
    """CLI module exposes the new classifier helper."""

    def test_helper_imports_from_cli(self):
        from lore import cli

        assert hasattr(cli, "_classify_entity_id_with_db_fallback"), (
            "G12: cli._classify_entity_id_with_db_fallback not defined yet"
        )
        assert callable(cli._classify_entity_id_with_db_fallback)


class TestClassifyEntityIdStrictPath:
    """Strict-matching IDs route via ``route_entity`` — no DB hit needed."""

    def test_strict_quest_id_returns_quests(self, project_dir):
        from lore.cli import _classify_entity_id_with_db_fallback

        # No row inserted — strict match short-circuits before any DB probe.
        assert _classify_entity_id_with_db_fallback(project_dir, "q-abcd") == "quests"

    def test_strict_standalone_mission_returns_missions(self, project_dir):
        from lore.cli import _classify_entity_id_with_db_fallback

        assert (
            _classify_entity_id_with_db_fallback(project_dir, "m-abcd") == "missions"
        )

    def test_strict_scoped_mission_returns_missions(self, project_dir):
        from lore.cli import _classify_entity_id_with_db_fallback

        assert (
            _classify_entity_id_with_db_fallback(project_dir, "q-aaaa/m-bbbb")
            == "missions"
        )


class TestClassifyEntityIdLooseQuestFallback:
    """Loose quest IDs (test-DB-inserted) classify via DB probe."""

    def test_loose_quest_id_present_in_db_classifies_as_quests(self, project_dir):
        from lore.cli import _classify_entity_id_with_db_fallback

        # 'z' is non-hex — strict route_entity would raise.
        insert_quest(project_dir, "q-zzzz", "Loose")
        assert _classify_entity_id_with_db_fallback(project_dir, "q-zzzz") == "quests"

    def test_loose_quest_id_absent_from_db_returns_none(self, project_dir):
        from lore.cli import _classify_entity_id_with_db_fallback

        # Loose-pattern OK, but no DB row -> classification fails.
        assert _classify_entity_id_with_db_fallback(project_dir, "q-zzzz") is None


class TestClassifyEntityIdRejectsGarbage:
    """Garbage IDs return None — caller emits a format error."""

    def test_completely_garbage_returns_none(self, project_dir):
        from lore.cli import _classify_entity_id_with_db_fallback

        assert _classify_entity_id_with_db_fallback(project_dir, "garbage") is None

    def test_empty_string_returns_none(self, project_dir):
        from lore.cli import _classify_entity_id_with_db_fallback

        assert _classify_entity_id_with_db_fallback(project_dir, "") is None

    def test_quest_with_trailing_slash_returns_none(self, project_dir):
        from lore.cli import _classify_entity_id_with_db_fallback

        assert _classify_entity_id_with_db_fallback(project_dir, "q-aaaa/") is None


# ---------------------------------------------------------------------------
# _emit_format_error — symbol presence
# ---------------------------------------------------------------------------


class TestEmitFormatErrorSymbol:
    """CLI module exposes the format-error emitter helper."""

    def test_helper_imports_from_cli(self):
        from lore import cli

        assert hasattr(cli, "_emit_format_error"), (
            "G12: cli._emit_format_error not defined yet (CHANGED #8)"
        )
        assert callable(cli._emit_format_error)


# ---------------------------------------------------------------------------
# Removed symbols — `_is_quest_id`, `_delete_quest`, `_delete_mission`
# ---------------------------------------------------------------------------


class TestDeletedHelpersRemovedFromCli:
    """G12 deletes private helpers that the new dispatch path supersedes."""

    def test_delete_quest_helper_not_importable_from_cli(self):
        from lore import cli

        assert not hasattr(cli, "_delete_quest"), (
            "G12: cli._delete_quest should be removed (delete_entity supersedes)"
        )

    def test_delete_mission_helper_not_importable_from_cli(self):
        from lore import cli

        assert not hasattr(cli, "_delete_mission"), (
            "G12: cli._delete_mission should be removed (delete_entity supersedes)"
        )

    def test_is_quest_id_not_present_in_cli_source(self):
        """Inline ``_is_quest_id`` closures must be gone after G12.

        Parses cli.py via AST and asserts no function (top-level or nested)
        is named ``_is_quest_id``. The dispatcher refactor replaces every
        such closure with ``_classify_entity_id_with_db_fallback`` or a
        direct ``route_entity`` call.
        """
        tree = ast.parse(CLI_PATH.read_text())
        bad = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "_is_quest_id"
        ]
        assert bad == [], (
            f"G12: cli.py still defines `_is_quest_id` ({len(bad)} occurrence(s)); "
            "use _classify_entity_id_with_db_fallback or route_entity instead"
        )

    def test_no_inline_quest_prefix_dispatch_in_cli(self):
        """Hand-rolled ``startswith('q-')`` dispatch tokens must be gone.

        After G12, ID-shape classification flows exclusively through
        ``_classify_entity_id_with_db_fallback`` and ``route_entity``.
        A grep-style scan of the source enforces this — the audit
        Pattern 6 / Spec §7 rationale.
        """
        src = CLI_PATH.read_text()
        # Allow the substring in comments/docstrings, but not in dispatcher logic.
        # We count occurrences of the literal `startswith("q-")` and
        # `startswith('q-')`. After G12 both should be zero.
        assert "startswith(\"q-\")" not in src, (
            'G12: cli.py still uses startswith("q-") dispatch'
        )
        assert "startswith('q-')" not in src, (
            "G12: cli.py still uses startswith('q-') dispatch"
        )
