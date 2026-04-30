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
