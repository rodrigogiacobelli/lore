"""Unit tests for lore.config — load_config, Config, DEFAULT_CONFIG, _FROM_TOML.

Spec: glossary-us-003 (lore codex show glossary-us-003)
Workflow: conceptual-workflows-glossary
Standards: decisions-010-public-api-stability, decisions-011-api-parity-with-cli,
           conceptual-workflows-error-handling, standards-single-responsibility,
           standards-dependency-inversion
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from lore.config import _FROM_TOML, DEFAULT_CONFIG, Config, load_config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_config(root: Path, content: str) -> None:
    """Write content to ``root/.lore/config.toml`` (creating dirs as needed)."""
    lore_dir = root / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    (lore_dir / "config.toml").write_text(content)


@pytest.fixture(autouse=True)
def _reset_warned_latch():
    """Reset the per-process warning latch between tests so each test sees a
    fresh ``_warned`` state. Each test's stderr expectations assume a clean
    latch.
    """
    import lore.config as cfg_mod
    cfg_mod._warned = False
    yield
    cfg_mod._warned = False


# ---------------------------------------------------------------------------
# load_config — happy paths and defaults
# ---------------------------------------------------------------------------


def test_load_config_missing_file_returns_default(tmp_path, capsys):
    # conceptual-workflows-glossary — fail-soft missing config (US-003 Scenario 1)
    cfg = load_config(tmp_path)
    assert cfg == DEFAULT_CONFIG
    assert capsys.readouterr().err == ""


def test_load_config_explicit_true(tmp_path, capsys):
    # conceptual-workflows-glossary — happy parse true (US-003 Scenario 2)
    _write_config(tmp_path, "show-glossary-on-codex-commands = true\n")
    cfg = load_config(tmp_path)
    assert cfg.show_glossary_on_codex_commands is True
    assert cfg.extras == {}
    assert capsys.readouterr().err == ""


def test_load_config_explicit_false(tmp_path, capsys):
    # conceptual-workflows-glossary — happy parse false (US-003 Scenario 3)
    _write_config(tmp_path, "show-glossary-on-codex-commands = false\n")
    cfg = load_config(tmp_path)
    assert cfg.show_glossary_on_codex_commands is False
    assert cfg.extras == {}
    assert capsys.readouterr().err == ""


def test_load_config_missing_known_key_uses_default(tmp_path, capsys):
    # conceptual-workflows-glossary — default fallback (US-003 Scenario 4)
    _write_config(tmp_path, 'some-future-key = "ignored"\n')
    cfg = load_config(tmp_path)
    assert cfg.show_glossary_on_codex_commands is True
    assert cfg.extras == {"some-future-key": "ignored"}
    assert capsys.readouterr().err == ""


def test_load_config_unknown_root_keys_preserved(tmp_path, capsys):
    # conceptual-workflows-glossary — forward-compat extras (US-003 Scenario 5)
    _write_config(
        tmp_path,
        "show-glossary-on-codex-commands = true\n"
        'realm-orchestrator-mode = "auto"\n'
        "[future-table]\n"
        "nested = 42\n",
    )
    cfg = load_config(tmp_path)
    assert cfg.show_glossary_on_codex_commands is True
    assert cfg.extras == {
        "realm-orchestrator-mode": "auto",
        "future-table": {"nested": 42},
    }
    assert capsys.readouterr().err == ""


def test_load_config_nested_table_preserved_in_extras(tmp_path):
    # conceptual-workflows-glossary — nested TOML tables preserved verbatim (Unit row 6)
    _write_config(tmp_path, "[future-table]\nnested = 42\n")
    cfg = load_config(tmp_path)
    assert cfg.extras == {"future-table": {"nested": 42}}
    assert isinstance(cfg.extras["future-table"], dict)


# ---------------------------------------------------------------------------
# load_config — fail-closed warnings
# ---------------------------------------------------------------------------


def test_load_config_malformed_toml_warns_once(tmp_path, capsys):
    # conceptual-workflows-glossary — fail-closed + warn (US-003 Scenario 6)
    _write_config(tmp_path, "not = valid = toml")
    cfg = load_config(tmp_path)
    assert cfg == DEFAULT_CONFIG
    err1 = capsys.readouterr().err
    assert "lore: invalid config at" in err1
    assert "(using defaults)" in err1
    expected_path = str(tmp_path / ".lore" / "config.toml")
    assert expected_path in err1
    # Exactly one stderr line
    assert err1.count("lore: invalid config at") == 1


def test_load_config_malformed_toml_second_call_does_not_rewarn(tmp_path, capsys):
    # conceptual-workflows-glossary — per-process latch (US-003 Scenario 6, second call)
    _write_config(tmp_path, "not = valid = toml")
    _ = load_config(tmp_path)
    capsys.readouterr()  # discard first-call stderr
    cfg2 = load_config(tmp_path)
    assert cfg2 == DEFAULT_CONFIG
    assert capsys.readouterr().err == ""


def test_load_config_wrong_type_known_key_warns_once(tmp_path, capsys):
    # conceptual-workflows-glossary — wrong-type fail-closed (US-003 Scenario 7)
    _write_config(tmp_path, 'show-glossary-on-codex-commands = "yes"\n')
    cfg = load_config(tmp_path)
    assert cfg.show_glossary_on_codex_commands is True
    err = capsys.readouterr().err
    assert "lore: invalid type for show-glossary-on-codex-commands at" in err
    assert "(expected bool); using default" in err
    expected_path = str(tmp_path / ".lore" / "config.toml")
    assert expected_path in err
    # Exactly one warning line
    assert err.count("lore: invalid type for show-glossary-on-codex-commands at") == 1


def test_load_config_wrong_type_second_call_does_not_rewarn(tmp_path, capsys):
    # conceptual-workflows-glossary — per-process latch shared across warning kinds
    _write_config(tmp_path, 'show-glossary-on-codex-commands = "yes"\n')
    _ = load_config(tmp_path)
    capsys.readouterr()
    cfg2 = load_config(tmp_path)
    assert cfg2.show_glossary_on_codex_commands is True
    assert capsys.readouterr().err == ""


# ---------------------------------------------------------------------------
# DEFAULT_CONFIG and Config dataclass
# ---------------------------------------------------------------------------


def test_default_config_constant():
    # conceptual-workflows-glossary — default singleton (Unit row 10)
    assert DEFAULT_CONFIG == Config(show_glossary_on_codex_commands=True, extras={})


def test_default_config_show_glossary_true():
    # conceptual-workflows-glossary — explicit attribute check on default
    assert DEFAULT_CONFIG.show_glossary_on_codex_commands is True


def test_default_config_extras_empty():
    # conceptual-workflows-glossary — extras default empty mapping
    assert DEFAULT_CONFIG.extras == {}


def test_config_is_frozen():
    # conceptual-workflows-glossary — immutability (Unit row 11)
    cfg = Config()
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        cfg.show_glossary_on_codex_commands = False  # type: ignore[misc]


def test_config_extras_is_frozen():
    # conceptual-workflows-glossary — extras attribute also frozen
    cfg = Config()
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        cfg.extras = {"x": 1}  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _FROM_TOML mapping
# ---------------------------------------------------------------------------


def test_from_toml_mapping_kebab_to_snake():
    # conceptual-workflows-glossary — _FROM_TOML mapping (Unit row 12)
    from lore.config import _FROM_TOML
    assert _FROM_TOML["show-glossary-on-codex-commands"] == "show_glossary_on_codex_commands"


# ---------------------------------------------------------------------------
# health-report-retention — new constrained-string setting
#
# Spec: tech spec "Health report retention policy".
# Contract: "none" (default) | "latest" | "all"; anything else falls back to
# "none" with one fail-soft stderr warning.
# ---------------------------------------------------------------------------


def test_load_config_health_report_retention_absent_defaults_to_none(tmp_path, capsys):
    """Key absent from an otherwise valid config → default ``"none"``."""
    _write_config(tmp_path, "show-glossary-on-codex-commands = true\n")
    cfg = load_config(tmp_path)
    assert cfg.health_report_retention == "none"
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("value", ["none", "latest", "all"])
def test_load_config_health_report_retention_accepts_each_allowed_value(
    tmp_path, capsys, value
):
    """Each of the three allowed tokens parses straight through."""
    _write_config(tmp_path, f'health-report-retention = "{value}"\n')
    cfg = load_config(tmp_path)
    assert cfg.health_report_retention == value
    assert capsys.readouterr().err == ""


def test_load_config_health_report_retention_parses_alongside_glossary_key(
    tmp_path, capsys
):
    """Both known keys parse in the same file without interfering."""
    _write_config(
        tmp_path,
        "show-glossary-on-codex-commands = false\n"
        'health-report-retention = "latest"\n',
    )
    cfg = load_config(tmp_path)
    assert cfg.show_glossary_on_codex_commands is False
    assert cfg.health_report_retention == "latest"
    assert cfg.extras == {}
    assert capsys.readouterr().err == ""


def test_load_config_health_report_retention_wrong_type_warns_expected_str(
    tmp_path, capsys
):
    """Integer value → default + one ``invalid type ... (expected str)`` line."""
    _write_config(tmp_path, "health-report-retention = 3\n")
    cfg = load_config(tmp_path)
    assert cfg.health_report_retention == "none"
    err = capsys.readouterr().err
    assert "lore: invalid type for health-report-retention at" in err
    assert "(expected str); using default" in err
    assert str(tmp_path / ".lore" / "config.toml") in err
    assert err.count("lore: invalid type for health-report-retention at") == 1


def test_load_config_health_report_retention_bool_is_wrong_type(tmp_path, capsys):
    """``true`` is not a string — the bool check stays strict for the str key."""
    _write_config(tmp_path, "health-report-retention = true\n")
    cfg = load_config(tmp_path)
    assert cfg.health_report_retention == "none"
    err = capsys.readouterr().err
    assert "lore: invalid type for health-report-retention at" in err
    assert "(expected str); using default" in err


def test_load_config_health_report_retention_wrong_type_does_not_rewarn(
    tmp_path, capsys
):
    """The per-process latch is shared — second call is silent."""
    _write_config(tmp_path, "health-report-retention = 3\n")
    _ = load_config(tmp_path)
    capsys.readouterr()
    cfg2 = load_config(tmp_path)
    assert cfg2.health_report_retention == "none"
    assert capsys.readouterr().err == ""


def test_load_config_health_report_retention_out_of_set_warns_invalid_value(
    tmp_path, capsys
):
    """Out-of-set token → default + one ``invalid value ...`` line."""
    _write_config(tmp_path, 'health-report-retention = "weekly"\n')
    cfg = load_config(tmp_path)
    assert cfg.health_report_retention == "none"
    err = capsys.readouterr().err
    assert "lore: invalid value for health-report-retention at" in err
    assert "(expected one of: none, latest, all); using default" in err
    assert str(tmp_path / ".lore" / "config.toml") in err
    assert err.count("lore: invalid value for health-report-retention at") == 1


def test_load_config_health_report_retention_out_of_set_is_not_a_type_warning(
    tmp_path, capsys
):
    """A correctly typed but disallowed value must NOT report a type error."""
    _write_config(tmp_path, 'health-report-retention = "weekly"\n')
    load_config(tmp_path)
    err = capsys.readouterr().err
    assert "invalid type for health-report-retention" not in err


def test_load_config_health_report_retention_out_of_set_does_not_rewarn(
    tmp_path, capsys
):
    """Out-of-set warning also flips the shared per-process latch."""
    _write_config(tmp_path, 'health-report-retention = "weekly"\n')
    _ = load_config(tmp_path)
    capsys.readouterr()
    cfg2 = load_config(tmp_path)
    assert cfg2.health_report_retention == "none"
    assert capsys.readouterr().err == ""


def test_load_config_health_report_retention_is_case_sensitive(tmp_path, capsys):
    """``"All"`` is not ``"all"`` — no silent normalisation."""
    _write_config(tmp_path, 'health-report-retention = "All"\n')
    cfg = load_config(tmp_path)
    assert cfg.health_report_retention == "none"
    assert "lore: invalid value for health-report-retention at" in capsys.readouterr().err


def test_load_config_health_report_retention_invalid_does_not_block_other_keys(
    tmp_path, capsys
):
    """A rejected retention value must not stop the glossary key from parsing."""
    _write_config(
        tmp_path,
        'health-report-retention = "weekly"\n'
        "show-glossary-on-codex-commands = false\n",
    )
    cfg = load_config(tmp_path)
    assert cfg.health_report_retention == "none"
    assert cfg.show_glossary_on_codex_commands is False


def test_load_config_glossary_key_invalid_does_not_block_retention(tmp_path, capsys):
    """Symmetric case — a rejected bool key must not stop the retention key."""
    _write_config(
        tmp_path,
        'show-glossary-on-codex-commands = "yes"\n'
        'health-report-retention = "all"\n',
    )
    cfg = load_config(tmp_path)
    assert cfg.show_glossary_on_codex_commands is True
    assert cfg.health_report_retention == "all"
    err = capsys.readouterr().err
    assert "(expected bool); using default" in err


def test_load_config_glossary_wrong_type_message_still_says_expected_bool(
    tmp_path, capsys
):
    """The existing bool wording is untouched by the generalised type table."""
    _write_config(tmp_path, "show-glossary-on-codex-commands = 3\n")
    cfg = load_config(tmp_path)
    assert cfg.show_glossary_on_codex_commands is True
    err = capsys.readouterr().err
    assert "lore: invalid type for show-glossary-on-codex-commands at" in err
    assert "(expected bool); using default" in err
    assert "expected str" not in err


def test_load_config_glossary_key_has_no_allowed_value_constraint(tmp_path, capsys):
    """The allowed-value table is per-key — a bool key never gets a value warning."""
    _write_config(tmp_path, "show-glossary-on-codex-commands = false\n")
    cfg = load_config(tmp_path)
    assert cfg.show_glossary_on_codex_commands is False
    assert "invalid value for" not in capsys.readouterr().err


def test_load_config_both_keys_invalid_warns_exactly_once(tmp_path, capsys):
    """The latch caps the process at ONE config warning across warning kinds."""
    _write_config(
        tmp_path,
        'show-glossary-on-codex-commands = "yes"\n'
        'health-report-retention = "weekly"\n',
    )
    cfg = load_config(tmp_path)
    assert cfg.show_glossary_on_codex_commands is True
    assert cfg.health_report_retention == "none"
    err = capsys.readouterr().err
    assert err.count("lore: invalid") == 1


def test_load_config_health_report_retention_never_leaks_into_extras(tmp_path):
    """A known key never lands in the forward-compat bucket."""
    _write_config(tmp_path, 'health-report-retention = "all"\n')
    cfg = load_config(tmp_path)
    assert "health-report-retention" not in cfg.extras
    assert cfg.extras == {}


def test_load_config_rejected_retention_value_never_leaks_into_extras(tmp_path, capsys):
    """A rejected value falls back to the default — it is not stashed in extras."""
    _write_config(tmp_path, 'health-report-retention = "weekly"\n')
    cfg = load_config(tmp_path)
    assert cfg.extras == {}
    capsys.readouterr()


def test_load_config_rejected_retention_type_never_leaks_into_extras(tmp_path, capsys):
    """Same for a wrong-typed value."""
    _write_config(tmp_path, "health-report-retention = 3\n")
    cfg = load_config(tmp_path)
    assert cfg.extras == {}
    capsys.readouterr()


def test_load_config_missing_file_health_report_retention_is_none(tmp_path, capsys):
    """Missing config file → DEFAULT_CONFIG carrying ``"none"``."""
    cfg = load_config(tmp_path)
    assert cfg == DEFAULT_CONFIG
    assert cfg.health_report_retention == "none"
    assert capsys.readouterr().err == ""


def test_load_config_malformed_toml_health_report_retention_is_none(tmp_path, capsys):
    """Malformed TOML → DEFAULT_CONFIG carrying ``"none"``."""
    _write_config(tmp_path, 'health-report-retention = "all"\nnot = valid = toml\n')
    cfg = load_config(tmp_path)
    assert cfg == DEFAULT_CONFIG
    assert cfg.health_report_retention == "none"
    assert "lore: invalid config at" in capsys.readouterr().err


def test_default_config_health_report_retention_is_none():
    """The default singleton carries ``"none"`` — no local persistence."""
    assert DEFAULT_CONFIG.health_report_retention == "none"


def test_config_health_report_retention_field_default():
    """The dataclass field itself defaults to ``"none"``."""
    assert Config().health_report_retention == "none"


def test_config_health_report_retention_is_frozen():
    """The new field is immutable like the rest of the frozen dataclass."""
    cfg = Config()
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        cfg.health_report_retention = "all"  # type: ignore[misc]


def test_config_field_order_keeps_extras_last():
    """Field order: every known setting, then ``extras``.

    ``extras`` is the forward-compatibility bucket and stays the final field so
    a new setting is always appended before it. The list itself grows —
    interactive-init-us-013 adds the four ``init_*`` answers, and
    nested-projects-spec adds the two table-backed ones — so the invariant is
    the position of the two anchors, not a frozen roster.

    A setting reaches ``Config`` by one of exactly two routes: a flat root key
    registered in ``_FROM_TOML``, or a table named in ``_KNOWN_TABLES``. A
    field arriving by neither is a setting the loader cannot parse.
    """
    from lore.config import _KNOWN_TABLES

    names = [f.name for f in dataclasses.fields(Config)]
    assert names[0] == "show_glossary_on_codex_commands"
    assert names[1] == "health_report_retention"
    assert names[-1] == "extras"
    from lore.config import _RETIRED_KEYS

    assert set(names) - {"extras"} == (
        set(_FROM_TOML.values()) | set(_KNOWN_TABLES) | set(_RETIRED_KEYS.values()) | {"legacy_init_interim"}
    )


def test_from_toml_maps_health_report_retention():
    """``_FROM_TOML`` gains the kebab → snake entry."""
    from lore.config import _FROM_TOML
    assert _FROM_TOML["health-report-retention"] == "health_report_retention"


# ---------------------------------------------------------------------------
# The four init-* keys — the answers `lore init` records and reuses.
#
# Spec: interactive-init-us-013 (lore codex show interactive-init-us-013)
# Anchor: conceptual-workflows-lore-init — recorded answers
# Standards: decisions-013-toml-for-config-yaml-for-glossary (flat root keys),
#            decisions-021-health-reports-are-ephemeral-by-default (one reader
#            per command-scoped key — `plan_init` is that reader).
#
# Two of the four are lists, which config.py has never carried. Fail-soft
# parity with the scalar path is the rule: a list holding one unknown token
# drops the WHOLE key to its default with one warning.
# ---------------------------------------------------------------------------


PROFILE_QUESTIONS = (
    "route",
    "memory",
    "memory-search",
    "memory-index",
    "memory-graph",
    "quests",
    "watchers",
)
ROUTE_QUESTIONS = ("route",)
BOOL_QUESTIONS = tuple(q for q in PROFILE_QUESTIONS if q not in ROUTE_QUESTIONS)


def test_init_keys_absent_take_their_documented_defaults(tmp_path, capsys):
    # interactive-init-us-013 — Scenario 2
    _write_config(tmp_path, "show-glossary-on-codex-commands = true\n")
    cfg = load_config(tmp_path)
    assert cfg.init_agents == []
    assert cfg.init_skills_gitignore == "lore-only"
    assert capsys.readouterr().err == ""


def test_init_keys_load_from_a_config_that_names_them_all(tmp_path, capsys):
    # interactive-init-us-013 — Scenario 1
    _write_config(
        tmp_path,
        'init-agents = ["claude"]\n'
        'init-route = "harness"\n'
        "init-quests = false\n"
        'init-skills-gitignore = "all"\n',
    )
    cfg = load_config(tmp_path)
    assert cfg.init_agents == ["claude"]
    assert cfg.init_route == "harness"
    assert cfg.init_quests is False
    assert cfg.init_skills_gitignore == "all"
    assert capsys.readouterr().err == ""


def test_a_string_where_a_list_is_expected_is_an_invalid_type(tmp_path, capsys):
    # interactive-init-us-013 — Unit row 3
    _write_config(tmp_path, 'init-agents = "claude"\n')
    cfg = load_config(tmp_path)
    assert cfg.init_agents == []
    err = capsys.readouterr().err
    assert "invalid type for init-agents" in err
    assert "(expected list)" in err


def test_a_non_string_list_element_drops_the_key_with_one_warning(tmp_path, capsys):
    # interactive-init-us-013 — Unit row 4
    _write_config(tmp_path, "init-agents = [\"claude\", 7]\n")
    cfg = load_config(tmp_path)
    assert cfg.init_agents == []
    assert len(capsys.readouterr().err.strip().splitlines()) == 1


def test_an_unknown_agent_id_in_config_drops_the_key(tmp_path, capsys):
    # interactive-init-us-013 — Unit row 6: the item set is the shipped registry
    _write_config(tmp_path, 'init-agents = ["claude", "cline"]\n')
    cfg = load_config(tmp_path)
    assert cfg.init_agents == []
    err = capsys.readouterr().err
    assert "invalid value for init-agents" in err
    assert "claude" in err


def test_an_empty_init_agents_list_is_a_real_value_not_an_absence(tmp_path, capsys):
    # interactive-init-us-013 — Unit row 7
    _write_config(tmp_path, "init-agents = []\n")
    cfg = load_config(tmp_path)
    assert cfg.init_agents == []
    assert capsys.readouterr().err == ""


def test_the_warning_latch_spans_a_scalar_and_a_list_failure(tmp_path, capsys):
    # interactive-init-us-013 — Unit row 8
    _write_config(
        tmp_path,
        'health-report-retention = "sometimes"\ninit-agents = ["typo"]\n',
    )
    load_config(tmp_path)
    assert len(capsys.readouterr().err.strip().splitlines()) == 1


def test_unknown_root_keys_still_land_in_extras_beside_the_init_keys(tmp_path):
    # interactive-init-us-013 — Unit row 9
    _write_config(tmp_path, 'init-route = "cli"\nnot-a-lore-key = 3\n')
    cfg = load_config(tmp_path)
    assert cfg.extras == {"not-a-lore-key": 3}
    assert cfg.init_route == "cli"


def test_a_rejected_init_key_never_leaks_into_extras(tmp_path, capsys):
    # interactive-init-us-013 — fail-soft parity with the scalar path
    _write_config(tmp_path, 'init-skills-gitignore = "sometimes"\n')
    cfg = load_config(tmp_path)
    assert "init-skills-gitignore" not in cfg.extras
    assert cfg.init_skills_gitignore == "lore-only"


def test_every_from_toml_key_has_an_expected_type():
    # interactive-init-us-013 — Unit row 1
    from lore.config import _EXPECTED_TYPE, _FROM_TOML

    assert set(_FROM_TOML) == set(_EXPECTED_TYPE)
    for key in ("init-agents", "init-route", "init-quests", "init-skills-gitignore"):
        assert key in _FROM_TOML
    assert _FROM_TOML["init-route"] == "init_route"


def test_allowed_item_values_covers_every_list_key_and_no_other():
    # interactive-init-us-013 — Unit row 10
    from lore.config import _ALLOWED_ITEM_VALUES, _EXPECTED_TYPE

    list_keys = {key for key, typ in _EXPECTED_TYPE.items() if typ is list}
    assert set(_ALLOWED_ITEM_VALUES) == list_keys
    assert list_keys == {"init-agents"}


def test_config_defaults_for_the_two_unchanged_init_keys():
    # interactive-init-us-013 — Unit row 2
    assert DEFAULT_CONFIG.init_agents == []
    assert DEFAULT_CONFIG.init_skills_gitignore == "lore-only"


def test_the_init_fields_are_frozen():
    # interactive-init-us-013 — Unit row 2 (frozen dataclass)
    cfg = Config()
    for field_name in (
        "init_agents",
        "init_route",
        "init_quests",
        "init_skills_gitignore",
        "legacy_init_access_mode",
    ):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(cfg, field_name, "x")


def test_the_constrained_init_token_sets_match_the_ones_init_enforces():
    """The token sets are authored twice — pin them so they cannot drift.

    ``config.py`` sits below ``init.py`` and cannot import it, so
    ``_ALLOWED_VALUES`` restates what ``plan_init`` enforces. This test is the
    join, the same role ``test_access_modes_constant_matches_the_access_mode_enum``
    plays for the access mode.
    """
    from lore.config import _ALLOWED_VALUES
    from lore.init import SKILLS_GITIGNORE_TOKENS
    from lore.initplan import Route

    assert set(_ALLOWED_VALUES["init-skills-gitignore"]) == set(SKILLS_GITIGNORE_TOKENS)
    assert _ALLOWED_VALUES["init-route"] == tuple(r.value for r in Route)


# ---------------------------------------------------------------------------
# render_known_keys_header — the generated `.lore/config.toml` comment block
# (interactive-init-us-020, FR-36)
# ---------------------------------------------------------------------------


def _key_rows() -> dict[str, str]:
    """Return the header's per-key rows, keyed by the key they name.

    A key row is ``#   <key><padding> : ...``; a description line is indented
    further (``#       ...``), so the character after ``#   `` tells them apart.
    """
    from lore.config import render_known_keys_header

    rows: dict[str, str] = {}
    for line in render_known_keys_header().splitlines():
        if not line.startswith("#   ") or line[4:5] == " ":
            continue
        key = line[4:].split(":", 1)[0].strip()
        assert key not in rows, f"{key} named twice in the header"
        rows[key] = line
    return rows


def _header_row_for(key: str) -> str:
    """Return the header line that opens *key*'s row."""
    rows = _key_rows()
    assert key in rows, f"no header row for {key}; got {sorted(rows)}"
    return rows[key]


def test_render_known_keys_header_names_every_from_toml_key():
    """conceptual-workflows-lore-init — config header regeneration.

    Every key in ``_FROM_TOML`` appears exactly once, with its type, its
    allowed values where it has them, its default and its description.
    """
    from lore.config import (
        _ALLOWED_VALUES,
        _EXPECTED_TYPE,
        _FROM_TOML,
        _KEY_DOC,
        DEFAULT_CONFIG,
        render_known_keys_header,
    )

    header = render_known_keys_header()
    for key, attr in _FROM_TOML.items():
        row = _header_row_for(key)
        allowed = _ALLOWED_VALUES.get(key)
        if allowed is not None:
            for token in allowed:
                assert f'"{token}"' in row, f"{key}: token {token} missing from {row}"
        elif _EXPECTED_TYPE[key] is bool:
            assert "bool" in row, row
        default = getattr(DEFAULT_CONFIG, attr)
        if isinstance(default, bool):
            assert f"default {str(default).lower()}" in row, row
        elif isinstance(default, str):
            assert f'default "{default}"' in row, row
        else:
            rendered = "[" + ", ".join(f'"{item}"' for item in default) + "]"
            assert f"default {rendered}" in row, row
        for doc_line in _KEY_DOC[key].splitlines():
            assert f"#       {doc_line}" in header, f"{key}: missing doc line {doc_line!r}"


def test_header_names_no_key_the_loader_does_not_know():
    """conceptual-workflows-lore-init — config header regeneration."""
    from lore.config import _FROM_TOML

    assert set(_key_rows()) == set(_FROM_TOML)


def test_header_is_all_comment_lines_and_announces_itself():
    """conceptual-workflows-lore-init — config header regeneration."""
    from lore.config import render_known_keys_header

    header = render_known_keys_header()
    assert header.endswith("\n")
    lines = header.splitlines()
    assert all(line.startswith("#") for line in lines), lines
    assert "regenerated by `lore init`" in lines[0] or "regenerated by `lore init`" in "\n".join(lines[:2])


def test_list_typed_key_renders_its_item_set_and_default():
    """conceptual-workflows-lore-init — config header regeneration."""
    from lore.agents import agent_ids
    from lore.config import DEFAULT_CONFIG, render_known_keys_header

    row = _header_row_for("init-agents")
    expected_items = " | ".join(f'"{item}"' for item in agent_ids())
    assert f"list of {expected_items}" in row, row
    rendered_default = (
        "[" + ", ".join(f'"{item}"' for item in DEFAULT_CONFIG.init_agents) + "]"
    )
    assert f"default {rendered_default}" in row, row
    assert render_known_keys_header().count("init-agents") == 1


def test_key_doc_covers_exactly_the_known_keys():
    """conceptual-workflows-lore-init — config header regeneration.

    The table that keeps ``_KEY_DOC``, ``_FROM_TOML`` and the header from
    drifting: a key added to the loader without a description fails here.
    """
    from lore.config import _FROM_TOML, _KEY_DOC

    assert set(_KEY_DOC) == set(_FROM_TOML)


def test_render_default_settings_writes_every_key_at_its_default():
    """conceptual-workflows-lore-init — config header regeneration."""
    import tomllib

    from lore.config import _FROM_TOML, DEFAULT_CONFIG, render_default_settings

    parsed = tomllib.loads(render_default_settings())
    assert set(parsed) == set(_FROM_TOML)
    for key, attr in _FROM_TOML.items():
        assert parsed[key] == getattr(DEFAULT_CONFIG, attr)


def test_header_plus_defaults_loads_back_as_the_default_config(tmp_path):
    """conceptual-workflows-lore-init — config header regeneration."""
    from lore.config import render_default_settings, render_known_keys_header

    _write_config(tmp_path, render_known_keys_header() + render_default_settings())
    assert load_config(tmp_path) == DEFAULT_CONFIG


# ---------------------------------------------------------------------------
# load_config — a config file that cannot be read at all
# ---------------------------------------------------------------------------
#
# Malformed TOML is only one way a config file goes wrong. Bytes that are not
# UTF-8 and a directory sitting where the file belongs are the same condition
# from the loader's point of view: nothing to parse. All three take the
# fail-soft branch, and the warning names the path so the person reading it
# knows which file to look at.


UNREADABLE_CONFIGS: dict[str, bytes | None] = {
    "bytes that are not utf-8": b"\x06\x0f`-\x02_\xdb.\xce\xff\xee\x94\xecVIK",
    "a lone continuation byte": b"\x82version = 1\n",
    "a NUL-padded binary blob": b"\x00\x00\x00\x00\xff\xfe\x00setting\x00",
    "a directory in place of the file": None,
}
"""``None`` means "make it a directory rather than a file"."""


def _plant_unreadable_config(root: Path, payload: bytes | None) -> Path:
    lore_dir = root / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    target = lore_dir / "config.toml"
    if payload is None:
        target.mkdir()
    else:
        target.write_bytes(payload)
    return target


@pytest.mark.parametrize(
    "payload", list(UNREADABLE_CONFIGS.values()), ids=list(UNREADABLE_CONFIGS)
)
def test_load_config_unreadable_file_falls_back_and_names_the_path(
    tmp_path, capsys, payload
):
    target = _plant_unreadable_config(tmp_path, payload)
    assert load_config(tmp_path) == DEFAULT_CONFIG
    err = capsys.readouterr().err
    assert f"lore: invalid config at {target}" in err
    assert "(using defaults)" in err
    assert err.count("lore: invalid config at") == 1


@pytest.mark.parametrize(
    "payload", list(UNREADABLE_CONFIGS.values()), ids=list(UNREADABLE_CONFIGS)
)
def test_recorded_keys_unreadable_file_records_nothing_and_stays_silent(
    tmp_path, capsys, payload
):
    from lore.config import recorded_keys

    _plant_unreadable_config(tmp_path, payload)
    assert recorded_keys(tmp_path) == frozenset()
    assert capsys.readouterr().err == ""


# ---------------------------------------------------------------------------
# recorded_keys — presence *and* validity
# ---------------------------------------------------------------------------
#
# Round 7, N1. `recorded_keys` answered "has this project already answered the
# question?" by asking whether the key is in the file, while `load_config`
# answers "what did it say?" fail-softly — coercing anything it cannot use to
# the built-in default. The two disagreed about exactly one thing, and it was
# the destructive one: an `init-agents` value the loader threw away was still
# reported as an answer, and the default it fell back to is the empty selection
# that uninstalls Lore's skills from every agent directory.
#
# One rule for both functions: a value the loader could not use is not an
# answer. Anything else lets a config Lore cannot understand authorise a
# destructive action.


UNUSABLE_INIT_AGENTS: dict[str, str] = {
    "a typo for a known id": 'init-agents = ["cluade"]\n',
    "a known id beside an unknown one": 'init-agents = ["claude", "windsurf"]\n',
    "numbers rather than ids": "init-agents = [1, 2]\n",
    "a bare string rather than a list": 'init-agents = "claude"\n',
    "a number rather than a list": "init-agents = 42\n",
}
"""Every shape smoke round 7 reached the empty selection through."""


@pytest.mark.parametrize(
    "content", list(UNUSABLE_INIT_AGENTS.values()), ids=list(UNUSABLE_INIT_AGENTS)
)
def test_recorded_keys_omits_a_key_whose_value_the_loader_rejected(
    tmp_path, capsys, content
):
    from lore.config import recorded_keys

    _write_config(tmp_path, content)

    assert "init-agents" not in recorded_keys(tmp_path)


@pytest.mark.parametrize(
    "content", list(UNUSABLE_INIT_AGENTS.values()), ids=list(UNUSABLE_INIT_AGENTS)
)
def test_recorded_keys_stays_silent_about_a_value_it_rejects(
    tmp_path, capsys, content
):
    """The warning belongs to the load that reads the values, and fires once."""
    from lore.config import recorded_keys

    _write_config(tmp_path, content)

    recorded_keys(tmp_path)
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    "content", list(UNUSABLE_INIT_AGENTS.values()), ids=list(UNUSABLE_INIT_AGENTS)
)
def test_a_rejected_key_does_not_hide_its_valid_siblings(tmp_path, capsys, content):
    from lore.config import recorded_keys

    _write_config(tmp_path, content + 'init-route = "cli"\n')

    assert recorded_keys(tmp_path) == frozenset({"init-route"})


def test_recorded_keys_reports_a_key_the_loader_could_use(tmp_path, capsys):
    from lore.config import recorded_keys

    _write_config(tmp_path, 'init-agents = ["claude"]\n')

    assert recorded_keys(tmp_path) == frozenset({"init-agents"})


def test_recorded_keys_reports_an_empty_list_because_it_is_a_real_answer(
    tmp_path, capsys
):
    """The one value that is both the built-in default and a stated choice."""
    from lore.config import recorded_keys

    _write_config(tmp_path, "init-agents = []\n")

    assert recorded_keys(tmp_path) == frozenset({"init-agents"})


def test_recorded_keys_reports_every_known_key_a_full_config_sets(tmp_path, capsys):
    from lore.config import recorded_keys

    _write_config(
        tmp_path,
        "show-glossary-on-codex-commands = true\n"
        'health-report-retention = "latest"\n'
        'init-agents = ["claude"]\n'
        'init-skills-gitignore = "all"\n'
        'project-name = "camelot"\n'
        'default-project-scope = "all"\n'
        + "".join(
            f'init-{q} = "cli"\n' if q in ROUTE_QUESTIONS else f"init-{q} = true\n"
            for q in PROFILE_QUESTIONS
        )
        + "something-else = 3\n",
    )

    assert recorded_keys(tmp_path) == frozenset(_FROM_TOML)


@pytest.mark.parametrize(
    "content",
    [
        'health-report-retention = "sometimes"\n',
        'init-route = "native"\n',
        'init-quests = "yes"\n',
        'init-skills-gitignore = "some"\n',
        "show-glossary-on-codex-commands = 1\n",
    ],
)
def test_recorded_keys_applies_the_same_rule_to_every_known_key(
    tmp_path, capsys, content
):
    """Not an `init-agents` special case: one loader, one notion of usable."""
    from lore.config import recorded_keys

    _write_config(tmp_path, content)

    assert recorded_keys(tmp_path) == frozenset()


# ---------------------------------------------------------------------------
# Nested Projects — the two new flat keys and the two new tables.
#
# Spec: nested-projects-spec (lore codex show nested-projects-spec) — F3, F4
# Decisions: D-23 (nested-table parsing), D-24 (`project-name` validation),
#            A-1 (tables for repeating records), decisions-013 (TOML config)
# ---------------------------------------------------------------------------


INVALID_NAME_MESSAGE = (
    "Invalid name: must start with alphanumeric and contain only "
    "letters, digits, hyphens, underscores."
)


def _config_path(root: Path) -> Path:
    return root / ".lore" / "config.toml"


# --- project-name ----------------------------------------------------------


def test_project_name_parses(tmp_path, capsys):
    # nested-projects-spec — FR-1: the project names itself
    _write_config(tmp_path, 'project-name = "camelot"\n')
    cfg = load_config(tmp_path)
    assert cfg.project_name == "camelot"
    assert cfg.extras == {}
    assert capsys.readouterr().err == ""


def test_project_name_defaults_to_the_empty_string(tmp_path, capsys):
    # nested-projects-spec — FR-1: absent means "the directory's name"
    _write_config(tmp_path, "")
    assert load_config(tmp_path).project_name == ""
    assert capsys.readouterr().err == ""


def test_project_name_empty_string_is_a_usable_value(tmp_path, capsys):
    # nested-projects-spec — D-24: the seeded default must not warn
    _write_config(tmp_path, 'project-name = ""\n')
    assert load_config(tmp_path).project_name == ""
    assert capsys.readouterr().err == ""


def test_project_name_wrong_type_falls_back_with_the_exact_line(tmp_path, capsys):
    # nested-projects-spec — Part 2 config fail-soft table, row 1
    _write_config(tmp_path, "project-name = 42\n")
    cfg = load_config(tmp_path)
    assert cfg.project_name == ""
    assert capsys.readouterr().err == (
        f"lore: invalid type for project-name at {_config_path(tmp_path)} "
        "(expected str); using default\n"
    )


def test_project_name_invalid_value_falls_back_with_the_exact_line(tmp_path, capsys):
    # nested-projects-spec — Part 2 config fail-soft table, row 2
    _write_config(tmp_path, 'project-name = "cam:elot"\n')
    cfg = load_config(tmp_path)
    assert cfg.project_name == ""
    assert capsys.readouterr().err == (
        f"lore: invalid value for project-name at {_config_path(tmp_path)} "
        f"({INVALID_NAME_MESSAGE}); using default\n"
    )


def test_project_name_is_wired_through_the_value_check_table(tmp_path):
    # nested-projects-spec — F3: one name grammar, wired in rather than restated
    from lore.config import _VALUE_CHECK
    from lore.validators import validate_project_name

    assert _VALUE_CHECK["project-name"] is validate_project_name


# --- default-project-scope -------------------------------------------------


@pytest.mark.parametrize("token", ["self", "all"])
def test_default_project_scope_parses_each_token(tmp_path, capsys, token):
    # nested-projects-spec — FR-2
    _write_config(tmp_path, f'default-project-scope = "{token}"\n')
    assert load_config(tmp_path).default_project_scope == token
    assert capsys.readouterr().err == ""


def test_default_project_scope_defaults_to_self(tmp_path, capsys):
    # nested-projects-spec — FR-2 / A-7: the downward axis is off unless asked
    _write_config(tmp_path, "")
    assert load_config(tmp_path).default_project_scope == "self"
    assert capsys.readouterr().err == ""


def test_default_project_scope_out_of_set_falls_back_with_the_exact_line(
    tmp_path, capsys
):
    # nested-projects-spec — Part 2 config fail-soft table, row 3
    _write_config(tmp_path, 'default-project-scope = "everything"\n')
    cfg = load_config(tmp_path)
    assert cfg.default_project_scope == "self"
    assert capsys.readouterr().err == (
        f"lore: invalid value for default-project-scope at {_config_path(tmp_path)} "
        "(expected one of: self, all); using default\n"
    )


def test_default_project_scope_token_set_lives_in_allowed_values(tmp_path):
    # nested-projects-spec — decisions-017: the token set lives in the loader,
    # never in a hand-rolled CLI validator
    from lore.config import _ALLOWED_VALUES

    assert _ALLOWED_VALUES["default-project-scope"] == ("self", "all")


# --- the registry tables ---------------------------------------------------


def test_both_new_flat_keys_are_registered_everywhere(tmp_path):
    # nested-projects-spec — F3 / decisions-013
    from lore.config import _EXPECTED_TYPE, _FROM_TOML, _KEY_DOC

    for key, attr in (
        ("project-name", "project_name"),
        ("default-project-scope", "default_project_scope"),
    ):
        assert _FROM_TOML[key] == attr
        assert _EXPECTED_TYPE[key] is str
        assert key in _KEY_DOC


def test_render_known_keys_header_names_both_new_keys():
    # nested-projects-spec — F3: the generated header teaches the new settings
    from lore.config import render_known_keys_header

    header = render_known_keys_header()
    assert header.count("project-name") == 1
    assert header.count("default-project-scope") == 1


def test_render_default_settings_seeds_both_new_keys_at_their_defaults():
    # nested-projects-spec — W5: `lore init` writes them and asks no question
    import tomllib

    from lore.config import render_default_settings

    parsed = tomllib.loads(render_default_settings())
    assert parsed["project-name"] == ""
    assert parsed["default-project-scope"] == "self"


# --- [shared] --------------------------------------------------------------


def test_shared_table_parses_into_typed_fields(tmp_path, capsys):
    # nested-projects-spec — FR-3 / F4
    from lore.config import SharedExports

    _write_config(
        tmp_path,
        "[shared]\nexports = [\"standards-*\", \"tech-db\"]\nglossary = true\n",
    )
    cfg = load_config(tmp_path)
    assert cfg.shared == SharedExports(exports=("standards-*", "tech-db"), glossary=True)
    assert capsys.readouterr().err == ""


def test_shared_glossary_defaults_to_false(tmp_path, capsys):
    # nested-projects-spec — FR-3: the glossary is opt-in
    _write_config(tmp_path, '[shared]\nexports = ["a"]\n')
    cfg = load_config(tmp_path)
    assert cfg.shared.exports == ("a",)
    assert cfg.shared.glossary is False
    assert capsys.readouterr().err == ""


def test_shared_absent_is_the_default_shared_exports(tmp_path, capsys):
    # nested-projects-spec — F4: `Config()` construction is unaffected
    from lore.config import SharedExports

    _write_config(tmp_path, "")
    assert load_config(tmp_path).shared == SharedExports()
    assert SharedExports() == SharedExports(exports=(), glossary=False)
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    "content,reason",
    [
        ('shared = "everything"\n', "expected a table"),
        ("shared = [1]\n", "expected a table"),
        ("[shared]\nexports = 3\n", "exports must be a list of strings"),
        ("[shared]\nexports = [1, 2]\n", "exports must be a list of strings"),
        ('[shared]\nglossary = "yes"\n', "glossary must be a boolean"),
    ],
)
def test_malformed_shared_falls_back_with_the_exact_line(
    tmp_path, capsys, content, reason
):
    # nested-projects-spec — Part 2 config fail-soft table, row 4
    from lore.config import SharedExports

    _write_config(tmp_path, content)
    cfg = load_config(tmp_path)
    assert cfg.shared == SharedExports()
    assert capsys.readouterr().err == (
        f"lore: invalid [shared] table at {_config_path(tmp_path)} "
        f"({reason}); using default\n"
    )


# --- [[descendants]] -------------------------------------------------------


DESCENDANTS_TOML = """\
[[descendants]]
name = "lore"
path = "lore"
exports = ["camelot-dispatch-contract"]

[[descendants]]
name = "realm"
path = "apps/realm"
"""


def test_descendants_parse_into_a_tuple_of_typed_records(tmp_path, capsys):
    # nested-projects-spec — FR-4 / F4
    from lore.config import DescendantExport

    _write_config(tmp_path, DESCENDANTS_TOML)
    cfg = load_config(tmp_path)
    assert cfg.descendants == (
        DescendantExport(
            name="lore", path="lore", exports=("camelot-dispatch-contract",)
        ),
        DescendantExport(name="realm", path="apps/realm", exports=()),
    )
    assert capsys.readouterr().err == ""


def test_descendants_absent_is_an_empty_tuple(tmp_path, capsys):
    # nested-projects-spec — F4: `Config()` construction is unaffected
    _write_config(tmp_path, "")
    assert load_config(tmp_path).descendants == ()
    assert capsys.readouterr().err == ""


NAME_REASON = "name must be a non-empty string"
PATH_REASON = "path must be a non-empty string"


@pytest.mark.parametrize(
    "content,reason",
    [
        ('descendants = "lore"\n', "expected an array of tables"),
        ("descendants = [1]\n", "expected an array of tables"),
        ('[[descendants]]\npath = "lore"\n', NAME_REASON),
        ('[[descendants]]\nname = 1\npath = "lore"\n', NAME_REASON),
        ('[[descendants]]\nname = ""\npath = "lore"\n', NAME_REASON),
        ('[[descendants]]\nname = "lore"\n', PATH_REASON),
        ('[[descendants]]\nname = "lore"\npath = 1\n', PATH_REASON),
        ('[[descendants]]\nname = "lore"\npath = ""\n', PATH_REASON),
        ('[[descendants]]\nname = "lore"\npath = "lore"\nexports = 3\n',
         "exports must be a list of strings"),
        ('[[descendants]]\nname = "lore"\npath = "lore"\nexports = ["a", 2]\n',
         "exports must be a list of strings"),
    ],
)
def test_one_malformed_descendant_drops_the_whole_key_with_the_exact_line(
    tmp_path, capsys, content, reason
):
    # nested-projects-spec — Part 2 config fail-soft table, row 5:
    # half a selection is not a selection
    _write_config(tmp_path, content)
    cfg = load_config(tmp_path)
    assert cfg.descendants == ()
    assert capsys.readouterr().err == (
        f"lore: invalid [[descendants]] entry at {_config_path(tmp_path)} "
        f"({reason}); using default\n"
    )


def test_one_malformed_entry_drops_its_valid_siblings_too(tmp_path, capsys):
    # nested-projects-spec — D-23: the WHOLE key falls back, not just the entry
    _write_config(
        tmp_path,
        '[[descendants]]\nname = "lore"\npath = "lore"\n\n[[descendants]]\nname = "realm"\n',
    )
    assert load_config(tmp_path).descendants == ()
    assert "invalid [[descendants]] entry" in capsys.readouterr().err


# --- the path-escape refusal (N-5) -----------------------------------------


def test_a_descendant_path_that_escapes_the_root_drops_only_that_entry(
    tmp_path, capsys
):
    # nested-projects-spec — Part 2 config fail-soft table, row 6 / N-5:
    # a security refusal drops one entry; a shape error drops the key
    from lore.config import DescendantExport

    _write_config(
        tmp_path,
        '[[descendants]]\nname = "outside"\npath = "../outside"\n\n'
        '[[descendants]]\nname = "lore"\npath = "lore"\n',
    )
    cfg = load_config(tmp_path)
    assert cfg.descendants == (DescendantExport(name="lore", path="lore", exports=()),)
    assert capsys.readouterr().err == (
        f'lore: descendant path "../outside" at {_config_path(tmp_path)} '
        "escapes the project root; ignored\n"
    )


def test_an_absolute_descendant_path_is_refused(tmp_path, capsys):
    # nested-projects-spec — N-5: the config is not a filesystem-read primitive
    _write_config(tmp_path, '[[descendants]]\nname = "etc"\npath = "/etc"\n')
    assert load_config(tmp_path).descendants == ()
    assert 'escapes the project root; ignored' in capsys.readouterr().err


# --- extras and forward compatibility --------------------------------------


def test_the_two_known_tables_never_land_in_extras(tmp_path, capsys):
    # nested-projects-spec — D-23(a): two homes for one fact is the
    # standards-dry failure, and it breaks `Config.extras`' own contract
    _write_config(tmp_path, '[shared]\nexports = ["a"]\n\n' + DESCENDANTS_TOML)
    cfg = load_config(tmp_path)
    assert cfg.extras == {}
    assert capsys.readouterr().err == ""


def test_an_unknown_table_still_lands_in_extras(tmp_path, capsys):
    # nested-projects-spec — FR-6: forward compatibility is unchanged
    _write_config(tmp_path, '[shared]\nexports = ["a"]\n\n[future]\nkey = "value"\n')
    cfg = load_config(tmp_path)
    assert cfg.extras == {"future": {"key": "value"}}
    assert capsys.readouterr().err == ""


def test_a_malformed_known_table_is_still_not_kept_in_extras(tmp_path, capsys):
    # nested-projects-spec — D-23(a): a known table is known whether or not it
    # parses; the fallback is the default, never a verbatim copy
    _write_config(tmp_path, 'shared = "everything"\n')
    assert load_config(tmp_path).extras == {}
    assert "invalid [shared] table" in capsys.readouterr().err


# --- recorded_keys ---------------------------------------------------------


def test_recorded_keys_counts_a_table_that_parses(tmp_path):
    # nested-projects-spec — D-23(b): a table that parses cleanly is an
    # answered key on the same rule the flat keys follow
    from lore.config import recorded_keys

    _write_config(tmp_path, '[shared]\nexports = ["a"]\n\n' + DESCENDANTS_TOML)
    assert recorded_keys(tmp_path) == frozenset({"shared", "descendants"})


def test_recorded_keys_ignores_a_table_the_loader_could_not_use(tmp_path):
    # nested-projects-spec — D-23(b): a value the loader could not use is not
    # an answer
    from lore.config import recorded_keys

    _write_config(tmp_path, 'shared = "everything"\ndescendants = 3\n')
    assert recorded_keys(tmp_path) == frozenset()


def test_recorded_keys_is_silent_about_a_broken_table(tmp_path, capsys):
    # nested-projects-spec — D-23(b): the warning belongs to the load that
    # reads the values
    from lore.config import recorded_keys

    _write_config(tmp_path, 'shared = "everything"\n')
    recorded_keys(tmp_path)
    assert capsys.readouterr().err == ""


# --- the whole file together -----------------------------------------------


def test_a_full_nested_projects_config_parses_with_no_warning(tmp_path, capsys):
    # nested-projects-spec — Part 2 "Data and Storage", the documented file
    from lore.config import DescendantExport, SharedExports

    _write_config(
        tmp_path,
        'project-name = "camelot"\n'
        'default-project-scope = "self"\n'
        "\n"
        "[shared]\n"
        'exports = ["standards-*"]\n'
        "glossary = true\n"
        "\n"
        "[[descendants]]\n"
        'name = "lore"\n'
        'path = "lore"\n'
        'exports = ["camelot-dispatch-contract"]\n',
    )
    cfg = load_config(tmp_path)
    assert cfg.project_name == "camelot"
    assert cfg.default_project_scope == "self"
    assert cfg.shared == SharedExports(exports=("standards-*",), glossary=True)
    assert cfg.descendants == (
        DescendantExport(
            name="lore", path="lore", exports=("camelot-dispatch-contract",)
        ),
    )
    assert cfg.extras == {}
    assert capsys.readouterr().err == ""


def test_the_new_table_fields_are_frozen():
    # nested-projects-spec — F4: `Config` stays a frozen view of the file
    cfg = Config()
    for field_name in ("shared", "descendants"):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(cfg, field_name, ())


def test_shared_exports_and_descendant_export_are_frozen():
    # nested-projects-spec — A-1: every table is a frozen dataclass on Config
    from lore.config import DescendantExport, SharedExports

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(SharedExports(), "glossary", True)
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(DescendantExport(name="a", path="b"), "name", "c")


def test_an_unknown_key_inside_a_known_table_is_ignored(tmp_path, capsys):
    # nested-projects-spec — FR-6: a newer release may add a key to either
    # table, and an older one must still parse the file it is given
    from lore.config import DescendantExport, SharedExports

    _write_config(
        tmp_path,
        '[shared]\nexports = ["a"]\nrites = true\n\n'
        '[[descendants]]\nname = "lore"\npath = "lore"\nfuture = 1\n',
    )
    cfg = load_config(tmp_path)
    assert cfg.shared == SharedExports(exports=("a",), glossary=False)
    assert cfg.descendants == (DescendantExport(name="lore", path="lore", exports=()),)
    assert capsys.readouterr().err == ""


# ---------------------------------------------------------------------------
# Adaptive init — the fifteen feature answers and the two retired keys.
#
# Spec: adaptive-init-spec (Part 2.7). Standards: decisions-013 (flat root keys,
# header generated from the tables), decisions-022 (no [init] table).
# ---------------------------------------------------------------------------


def _attr(question: str) -> str:
    return "init_" + question.replace("-", "_")


class TestProfileKeys:
    @pytest.mark.parametrize("question", ROUTE_QUESTIONS)
    @pytest.mark.parametrize("token", ["harness", "cli"])
    def test_every_route_key_reads_each_valid_token(self, tmp_path, capsys, question, token):
        _write_config(tmp_path, f'init-{question} = "{token}"\n')
        assert getattr(load_config(tmp_path), _attr(question)) == token
        assert capsys.readouterr().err == ""

    @pytest.mark.parametrize("question", BOOL_QUESTIONS)
    @pytest.mark.parametrize("value", [True, False])
    def test_every_opt_in_key_reads_a_bool(self, tmp_path, capsys, question, value):
        _write_config(tmp_path, f"init-{question} = {str(value).lower()}\n")
        assert getattr(load_config(tmp_path), _attr(question)) is value
        assert capsys.readouterr().err == ""

    @pytest.mark.parametrize("question", PROFILE_QUESTIONS)
    def test_absent_keys_take_the_headless_defaults(self, tmp_path, question):
        from lore.initplan import Profile

        _write_config(tmp_path, "show-glossary-on-codex-commands = true\n")
        expected = Profile().as_answers()[question.replace("-", "_")]
        assert getattr(load_config(tmp_path), _attr(question)) == expected

    @pytest.mark.parametrize("question", ROUTE_QUESTIONS)
    def test_an_out_of_set_route_warns_once_and_falls_back(self, tmp_path, capsys, question):
        _write_config(tmp_path, f'init-{question} = "native"\n')
        value = getattr(load_config(tmp_path), _attr(question))
        assert value == getattr(DEFAULT_CONFIG, _attr(question))
        err = capsys.readouterr().err.strip().splitlines()
        assert len(err) == 1
        assert err[0].startswith(f"lore: invalid value for init-{question} at ")
        assert err[0].endswith("(expected one of: harness, cli); using default")

    @pytest.mark.parametrize("question", ROUTE_QUESTIONS)
    def test_a_non_string_route_is_an_invalid_type(self, tmp_path, capsys, question):
        _write_config(tmp_path, f"init-{question} = true\n")
        assert getattr(load_config(tmp_path), _attr(question)) == getattr(
            DEFAULT_CONFIG, _attr(question)
        )
        assert f"invalid type for init-{question}" in capsys.readouterr().err

    def test_off_is_not_a_route(self, tmp_path, capsys):
        _write_config(tmp_path, 'init-route = "off"\n')
        assert load_config(tmp_path).init_route == DEFAULT_CONFIG.init_route
        assert "invalid value for init-route" in capsys.readouterr().err

    @pytest.mark.parametrize("question", BOOL_QUESTIONS)
    @pytest.mark.parametrize("value", ['"yes"', "1"])
    def test_a_non_bool_opt_in_is_an_invalid_type(self, tmp_path, capsys, question, value):
        _write_config(tmp_path, f"init-{question} = {value}\n")
        assert getattr(load_config(tmp_path), _attr(question)) is True
        err = capsys.readouterr().err
        assert f"invalid type for init-{question}" in err
        assert "(expected bool)" in err

    def test_a_rejected_profile_key_never_leaks_into_extras(self, tmp_path, capsys):
        _write_config(tmp_path, 'init-route = "native"\n')
        assert "init-route" not in load_config(tmp_path).extras

    def test_the_keys_restate_the_question_table(self):
        from lore.config import _FROM_TOML
        from lore.initplan import QUESTIONS, question_key, question_kwarg

        for question in QUESTIONS:
            assert _FROM_TOML[question_key(question)] == "init_" + question_kwarg(question)
        assert PROFILE_QUESTIONS == QUESTIONS

    def test_the_defaults_restate_the_profile_defaults(self):
        from lore.initplan import Profile

        for name, value in Profile().as_answers().items():
            assert getattr(DEFAULT_CONFIG, f"init_{name}") == value


class TestRetiredKeys:
    def test_old_keys_parse_into_the_legacy_fields(self, tmp_path, capsys):
        _write_config(
            tmp_path,
            'init-access-mode = "cli"\ninit-skill-families = ["workflow", "memory"]\n',
        )
        cfg = load_config(tmp_path)
        assert cfg.legacy_init_access_mode == "cli"
        assert cfg.legacy_init_skill_families == ("workflow", "memory")
        assert capsys.readouterr().err == ""

    def test_old_keys_never_land_in_extras(self, tmp_path):
        _write_config(
            tmp_path,
            'init-access-mode = "cli"\ninit-skill-families = ["memory"]\nother = 1\n',
        )
        assert load_config(tmp_path).extras == {"other": 1}

    def test_absent_old_keys_are_none(self, tmp_path):
        _write_config(tmp_path, "show-glossary-on-codex-commands = true\n")
        cfg = load_config(tmp_path)
        assert cfg.legacy_init_access_mode is None
        assert cfg.legacy_init_skill_families is None

    @pytest.mark.parametrize(
        "line",
        [
            'init-access-mode = "both"\n',
            "init-access-mode = 3\n",
            'init-skill-families = ["memory", "typo"]\n',
            'init-skill-families = "memory"\n',
            "init-skill-families = [1]\n",
        ],
    )
    def test_an_unusable_old_value_is_none_and_silent(self, tmp_path, capsys, line):
        _write_config(tmp_path, line)
        cfg = load_config(tmp_path)
        assert cfg.legacy_init_access_mode is None
        assert cfg.legacy_init_skill_families is None
        assert capsys.readouterr().err == ""
        assert cfg.extras == {}

    def test_an_empty_family_list_is_a_real_value(self, tmp_path):
        _write_config(tmp_path, "init-skill-families = []\n")
        assert load_config(tmp_path).legacy_init_skill_families == ()

    def test_a_config_holding_only_the_old_keys_loads_with_new_defaults(self, tmp_path, capsys):
        _write_config(tmp_path, 'init-access-mode = "cli"\n')
        cfg = load_config(tmp_path)
        assert cfg.init_route == "cli"
        assert capsys.readouterr().err == ""

    def test_the_interim_route_and_validate_keys_are_collected_not_known(self, tmp_path, capsys):
        _write_config(
            tmp_path,
            'init-memory-read = "cli"\ninit-watchers-write = "off"\n'
            "init-doctrines-validate = false\ninit-quests = false\n",
        )
        cfg = load_config(tmp_path)
        assert dict(cfg.legacy_init_interim) == {
            "init-memory-read": "cli",
            "init-watchers-write": "off",
            "init-doctrines-validate": False,
        }
        assert cfg.init_quests is False
        assert cfg.extras == {}
        assert capsys.readouterr().err == ""

    @pytest.mark.parametrize(
        "line",
        ['init-memory-read = "native"\n', "init-memory-write = true\n", 'init-memory-validate = "yes"\n'],
    )
    def test_an_unusable_interim_value_is_dropped_silently(self, tmp_path, capsys, line):
        _write_config(tmp_path, line)
        cfg = load_config(tmp_path)
        assert dict(cfg.legacy_init_interim) == {}
        assert capsys.readouterr().err == ""

    def test_interim_keys_do_not_count_as_recorded(self, tmp_path):
        from lore.config import recorded_keys

        _write_config(tmp_path, 'init-memory-read = "cli"\ninit-doctrines-validate = true\n')
        assert recorded_keys(tmp_path) == frozenset()

    def test_retired_keys_do_not_count_as_recorded(self, tmp_path):
        from lore.config import recorded_keys

        _write_config(tmp_path, 'init-access-mode = "cli"\ninit-skill-families = ["memory"]\n')
        assert recorded_keys(tmp_path) == frozenset()


class TestGeneratedHeader:
    def test_lists_every_profile_key_once(self):
        from lore.config import render_known_keys_header

        header = render_known_keys_header()
        for question in PROFILE_QUESTIONS:
            assert f"#   init-{question}" in header
            assert _header_row_for(f"init-{question}")

    def test_the_route_key_spells_the_two_tokens_on_separate_lines(self):
        from lore.config import _KEY_DOC

        lines = _KEY_DOC["init-route"].splitlines()
        assert [line.split()[0] for line in lines[-2:]] == ["harness", "cli"]

    def test_ends_with_the_retired_keys_block_built_from_the_table(self):
        from lore.config import _RETIRED_KEYS, render_known_keys_header

        header = render_known_keys_header()
        last = header.splitlines()[-1]
        assert last.startswith("#")
        assert "Retired keys" in last
        for key in _RETIRED_KEYS:
            assert key in last

    def test_retired_keys_have_no_row_of_their_own(self):
        from lore.config import _INTERIM_KEYS, _RETIRED_KEYS

        assert not (set(_RETIRED_KEYS) | set(_INTERIM_KEYS)) & set(_key_rows())

    def test_the_header_names_the_interim_keys_as_retired(self):
        from lore.config import _INTERIM_KEYS, render_known_keys_header

        last = render_known_keys_header().splitlines()[-1]
        for key in _INTERIM_KEYS:
            assert key in last


class TestDefaultSettings:
    def test_writes_the_seven_lines_at_their_defaults(self):
        import tomllib

        from lore.config import render_default_settings
        from lore.initplan import Profile

        parsed = tomllib.loads(render_default_settings())
        for name, value in Profile().as_answers().items():
            assert parsed[f"init-{name.replace('_', '-')}"] == value

    def test_no_longer_writes_the_retired_keys(self):
        import tomllib

        from lore.config import render_default_settings

        parsed = tomllib.loads(render_default_settings())
        assert "init-access-mode" not in parsed
        assert "init-skill-families" not in parsed


class TestRecordedKeys:
    def test_a_valid_new_key_counts_as_answered(self, tmp_path):
        from lore.config import recorded_keys

        _write_config(tmp_path, 'init-route = "harness"\ninit-quests = false\n')
        assert recorded_keys(tmp_path) == frozenset({"init-route", "init-quests"})

    def test_an_invalid_new_key_does_not(self, tmp_path):
        from lore.config import recorded_keys

        _write_config(tmp_path, 'init-route = "yes"\ninit-quests = "no"\n')
        assert recorded_keys(tmp_path) == frozenset()
