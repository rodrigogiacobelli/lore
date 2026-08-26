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

from lore.config import Config, DEFAULT_CONFIG, _FROM_TOML, load_config


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
    interactive-init-us-013 adds the four ``init_*`` answers — so the invariant
    is the position of the two anchors, not a frozen roster.
    """
    names = [f.name for f in dataclasses.fields(Config)]
    assert names[0] == "show_glossary_on_codex_commands"
    assert names[1] == "health_report_retention"
    assert names[-1] == "extras"
    assert set(names) - {"extras"} == set(_FROM_TOML.values())


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


DEFAULT_FAMILIES = ["memory", "machinery", "workflow"]


def test_init_keys_absent_take_their_documented_defaults(tmp_path, capsys):
    # interactive-init-us-013 — Scenario 2
    _write_config(tmp_path, "show-glossary-on-codex-commands = true\n")
    cfg = load_config(tmp_path)
    assert cfg.init_agents == []
    assert cfg.init_access_mode == "native"
    assert cfg.init_skill_families == DEFAULT_FAMILIES
    assert cfg.init_skills_gitignore == "lore-only"
    assert capsys.readouterr().err == ""


def test_init_keys_load_from_a_config_that_names_all_four(tmp_path, capsys):
    # interactive-init-us-013 — Scenario 1
    _write_config(
        tmp_path,
        'init-agents = ["claude"]\n'
        'init-access-mode = "cli"\n'
        'init-skill-families = ["memory", "workflow"]\n'
        'init-skills-gitignore = "all"\n',
    )
    cfg = load_config(tmp_path)
    assert cfg.init_agents == ["claude"]
    assert cfg.init_access_mode == "cli"
    assert cfg.init_skill_families == ["memory", "workflow"]
    assert cfg.init_skills_gitignore == "all"
    assert capsys.readouterr().err == ""


def test_out_of_set_family_token_drops_the_whole_key_with_one_warning(tmp_path, capsys):
    # interactive-init-us-013 — Scenario 3 and Unit row 5
    _write_config(tmp_path, 'init-skill-families = ["memory", "typo"]\n')
    cfg = load_config(tmp_path)
    assert cfg.init_skill_families == DEFAULT_FAMILIES
    err = capsys.readouterr().err.strip().splitlines()
    assert len(err) == 1
    assert err[0].startswith("lore: invalid value for init-skill-families at ")
    assert err[0].endswith("(expected items from: machinery, memory, workflow); using default")


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
    _write_config(tmp_path, "init-skill-families = [\"memory\", 7]\n")
    cfg = load_config(tmp_path)
    assert cfg.init_skill_families == DEFAULT_FAMILIES
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
        'health-report-retention = "sometimes"\ninit-skill-families = ["typo"]\n',
    )
    load_config(tmp_path)
    assert len(capsys.readouterr().err.strip().splitlines()) == 1


def test_unknown_root_keys_still_land_in_extras_beside_the_init_keys(tmp_path):
    # interactive-init-us-013 — Unit row 9
    _write_config(tmp_path, 'init-access-mode = "cli"\nnot-a-lore-key = 3\n')
    cfg = load_config(tmp_path)
    assert cfg.extras == {"not-a-lore-key": 3}
    assert cfg.init_access_mode == "cli"


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
    for key in ("init-agents", "init-access-mode", "init-skill-families", "init-skills-gitignore"):
        assert key in _FROM_TOML
    assert _FROM_TOML["init-skill-families"] == "init_skill_families"


def test_allowed_item_values_covers_every_list_key_and_no_other():
    # interactive-init-us-013 — Unit row 10
    from lore.config import _ALLOWED_ITEM_VALUES, _EXPECTED_TYPE

    list_keys = {key for key, typ in _EXPECTED_TYPE.items() if typ is list}
    assert set(_ALLOWED_ITEM_VALUES) == list_keys
    assert list_keys == {"init-agents", "init-skill-families"}


def test_config_defaults_for_the_four_init_keys():
    # interactive-init-us-013 — Unit row 2
    assert DEFAULT_CONFIG.init_agents == []
    assert DEFAULT_CONFIG.init_access_mode == "native"
    assert DEFAULT_CONFIG.init_skill_families == DEFAULT_FAMILIES
    assert DEFAULT_CONFIG.init_skills_gitignore == "lore-only"


def test_the_four_init_fields_are_frozen():
    # interactive-init-us-013 — Unit row 2 (frozen dataclass)
    cfg = Config()
    for field_name in (
        "init_agents",
        "init_access_mode",
        "init_skill_families",
        "init_skills_gitignore",
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
    from lore.config import _ALLOWED_VALUES, DEFAULT_CONFIG
    from lore.init import DEFAULT_ACCESS_MODE, SKILLS_GITIGNORE_TOKENS
    from lore.initplan import AccessMode

    assert set(_ALLOWED_VALUES["init-skills-gitignore"]) == set(SKILLS_GITIGNORE_TOKENS)
    assert set(_ALLOWED_VALUES["init-access-mode"]) == {mode.value for mode in AccessMode}
    # `plan_init` reads the default off `Config`, so `DEFAULT_ACCESS_MODE` is a
    # statement of the same fact rather than a second source for it.
    assert DEFAULT_CONFIG.init_access_mode == DEFAULT_ACCESS_MODE


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
    from lore.config import DEFAULT_CONFIG, render_known_keys_header
    from lore.skills import family_ids

    row = _header_row_for("init-skill-families")
    expected_items = " | ".join(f'"{item}"' for item in family_ids())
    assert f"list of {expected_items}" in row, row
    rendered_default = (
        "[" + ", ".join(f'"{item}"' for item in DEFAULT_CONFIG.init_skill_families) + "]"
    )
    assert f"default {rendered_default}" in row, row
    assert render_known_keys_header().count("init-skill-families") == 1


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

    from lore.config import DEFAULT_CONFIG, _FROM_TOML, render_default_settings

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

    _write_config(tmp_path, content + 'init-access-mode = "cli"\n')

    assert recorded_keys(tmp_path) == frozenset({"init-access-mode"})


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
        'init-access-mode = "cli"\n'
        'init-skill-families = ["memory"]\n'
        'init-skills-gitignore = "all"\n'
        "something-else = 3\n",
    )

    assert recorded_keys(tmp_path) == frozenset(_FROM_TOML)


@pytest.mark.parametrize(
    "content",
    [
        'health-report-retention = "sometimes"\n',
        'init-access-mode = "both"\n',
        'init-skill-families = ["memory", "typo"]\n',
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
