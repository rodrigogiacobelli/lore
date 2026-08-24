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

from lore.config import Config, DEFAULT_CONFIG, load_config


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


def test_config_field_order_places_retention_before_extras():
    """Field order: ``show_glossary...`` → ``health_report_retention`` → ``extras``."""
    names = [f.name for f in dataclasses.fields(Config)]
    assert names == [
        "show_glossary_on_codex_commands",
        "health_report_retention",
        "extras",
    ]


def test_from_toml_maps_health_report_retention():
    """``_FROM_TOML`` gains the kebab → snake entry."""
    from lore.config import _FROM_TOML
    assert _FROM_TOML["health-report-retention"] == "health_report_retention"
