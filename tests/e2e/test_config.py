"""E2E parity tests for lore.config.load_config.

Workflow: conceptual-workflows-glossary
Spec: glossary-us-003 (lore codex show glossary-us-003)
Standards: decisions-011-api-parity-with-cli (Python-API parity scope)

The config loader has no CLI surface in MVP — parity here is Python-API only:
each E2E scenario in US-003 maps to a direct ``load_config(project_dir)`` call
on a real, on-disk project root.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_warned_latch():
    """Reset the per-process warning latch so each scenario sees a fresh state."""
    import lore.config as cfg_mod
    cfg_mod._warned = False
    yield
    cfg_mod._warned = False


def _ensure_no_config(project_dir):
    """Remove any pre-seeded ``.lore/config.toml`` so the test starts clean."""
    p = project_dir / ".lore" / "config.toml"
    if p.exists():
        p.unlink()


def test_python_api_load_config_missing_file(project_dir, capsys):
    # conceptual-workflows-glossary — Scenario 1 Python-API parity (ADR-011)
    from lore.config import DEFAULT_CONFIG, load_config
    _ensure_no_config(project_dir)
    cfg = load_config(project_dir)
    assert cfg == DEFAULT_CONFIG
    assert cfg.show_glossary_on_codex_commands is True
    assert cfg.extras == {}
    assert capsys.readouterr().err == ""


def test_python_api_load_config_explicit_true(project_dir, capsys):
    # conceptual-workflows-glossary — Scenario 2 Python-API parity
    from lore.config import load_config
    (project_dir / ".lore").mkdir(parents=True, exist_ok=True)
    (project_dir / ".lore" / "config.toml").write_text(
        "show-glossary-on-codex-commands = true\n"
    )
    cfg = load_config(project_dir)
    assert cfg.show_glossary_on_codex_commands is True
    assert cfg.extras == {}
    assert capsys.readouterr().err == ""


def test_python_api_load_config_explicit_false(project_dir, capsys):
    # conceptual-workflows-glossary — Scenario 3 Python-API parity
    from lore.config import load_config
    (project_dir / ".lore").mkdir(parents=True, exist_ok=True)
    (project_dir / ".lore" / "config.toml").write_text(
        "show-glossary-on-codex-commands = false\n"
    )
    cfg = load_config(project_dir)
    assert cfg.show_glossary_on_codex_commands is False
    assert capsys.readouterr().err == ""


def test_python_api_load_config_missing_known_key(project_dir, capsys):
    # conceptual-workflows-glossary — Scenario 4 Python-API parity
    from lore.config import load_config
    (project_dir / ".lore").mkdir(parents=True, exist_ok=True)
    (project_dir / ".lore" / "config.toml").write_text(
        'some-future-key = "ignored"\n'
    )
    cfg = load_config(project_dir)
    assert cfg.show_glossary_on_codex_commands is True
    assert cfg.extras == {"some-future-key": "ignored"}
    assert capsys.readouterr().err == ""


def test_python_api_load_config_extras_preserved(project_dir, capsys):
    # conceptual-workflows-glossary — Scenario 5 Python-API parity
    from lore.config import load_config
    (project_dir / ".lore").mkdir(parents=True, exist_ok=True)
    (project_dir / ".lore" / "config.toml").write_text(
        "show-glossary-on-codex-commands = true\n"
        'realm-orchestrator-mode = "auto"\n'
        "[future-table]\n"
        "nested = 42\n"
    )
    cfg = load_config(project_dir)
    assert cfg.show_glossary_on_codex_commands is True
    assert cfg.extras == {
        "realm-orchestrator-mode": "auto",
        "future-table": {"nested": 42},
    }
    assert capsys.readouterr().err == ""


def test_python_api_load_config_malformed_warns_once(project_dir, capsys):
    # conceptual-workflows-glossary — Scenario 6 Python-API parity
    from lore.config import DEFAULT_CONFIG, load_config
    (project_dir / ".lore").mkdir(parents=True, exist_ok=True)
    (project_dir / ".lore" / "config.toml").write_text("not = valid = toml")
    cfg = load_config(project_dir)
    assert cfg == DEFAULT_CONFIG
    err = capsys.readouterr().err
    assert "lore: invalid config at" in err
    assert "(using defaults)" in err
    assert str(project_dir / ".lore" / "config.toml") in err

    # Second call within the same process — no additional warning line
    cfg2 = load_config(project_dir)
    assert cfg2 == DEFAULT_CONFIG
    assert capsys.readouterr().err == ""


def test_python_api_load_config_wrong_type_warns(project_dir, capsys):
    # conceptual-workflows-glossary — Scenario 7 Python-API parity
    from lore.config import load_config
    (project_dir / ".lore").mkdir(parents=True, exist_ok=True)
    (project_dir / ".lore" / "config.toml").write_text(
        'show-glossary-on-codex-commands = "yes"\n'
    )
    cfg = load_config(project_dir)
    assert cfg.show_glossary_on_codex_commands is True
    err = capsys.readouterr().err
    assert "lore: invalid type for show-glossary-on-codex-commands at" in err
    assert "(expected bool); using default" in err


def test_config_not_exported_from_models():
    # conceptual-workflows-glossary — Scenario 8 (FR-14, ADR-010)
    import lore.models
    assert "Config" not in lore.models.__all__


def test_config_path_helper(project_dir):
    # conceptual-workflows-glossary — Scenario 9 (config_path resolution)
    from lore.paths import config_path
    assert config_path(project_dir) == project_dir / ".lore" / "config.toml"
