"""Unit tests for `lore.init._seed_glossary` (US-006).

Spec: glossary-us-006 (lore codex show glossary-us-006)
Workflow: conceptual-workflows-lore-init

Per ADR-006 (no seed content tests), assertions on the seeded files are
structural and substring-based — full content equality lives only in the
E2E byte-for-byte tests, which are themselves driven by the on-disk seed
sources, not hand-written constants.

These tests must FAIL until US-006 Green lands the `_seed_glossary` step
and the corresponding wiring inside ``run_init``.
"""

from __future__ import annotations

import importlib

import pytest


def test_seed_glossary_writes_glossary_yaml_when_absent(tmp_path):
    """conceptual-workflows-lore-init — Unit row 1 (FR-27)."""
    from lore.init import _seed_glossary

    _seed_glossary(tmp_path)
    p = tmp_path / ".lore" / "codex" / "glossary.yaml"
    assert p.exists()
    text = p.read_text()
    assert "items: []" in text


def test_seed_glossary_writes_config_toml_when_absent(tmp_path):
    """conceptual-workflows-lore-init — Unit row 2 (FR-28)."""
    from lore.init import _seed_glossary

    _seed_glossary(tmp_path)
    p = tmp_path / ".lore" / "config.toml"
    assert p.exists()
    assert "show-glossary-on-codex-commands = true" in p.read_text()


def test_seed_glossary_idempotent_does_not_overwrite(tmp_path):
    """conceptual-workflows-lore-init — Unit row 3 (FR-27, FR-28 idempotency)."""
    from lore.init import _seed_glossary

    (tmp_path / ".lore" / "codex").mkdir(parents=True)
    user_glossary = (
        "items:\n"
        "  - keyword: Constable\n"
        "    definition: chore mission.\n"
    )
    user_config = "show-glossary-on-codex-commands = false\n"
    (tmp_path / ".lore" / "codex" / "glossary.yaml").write_text(user_glossary)
    (tmp_path / ".lore" / "config.toml").write_text(user_config)

    _seed_glossary(tmp_path)

    assert (
        tmp_path / ".lore" / "codex" / "glossary.yaml"
    ).read_text() == user_glossary
    assert (tmp_path / ".lore" / "config.toml").read_text() == user_config


def test_seed_glossary_creates_codex_dir(tmp_path):
    """conceptual-workflows-lore-init — Unit row 4 (Scenario 3 mkdir parents)."""
    from lore.init import _seed_glossary

    # No .lore/ at all under tmp_path
    _seed_glossary(tmp_path)
    assert (tmp_path / ".lore" / "codex").is_dir()
    assert (tmp_path / ".lore" / "codex" / "glossary.yaml").is_file()


def test_seed_glossary_emits_created_messages_only_on_first_write(tmp_path):
    """conceptual-workflows-lore-init — Unit row 5 (Scenario 1 / Scenario 2 messages)."""
    from lore.init import _seed_glossary

    msgs1 = _seed_glossary(tmp_path)
    assert any("Created codex/glossary.yaml" in m for m in msgs1)
    assert any("Created config.toml" in m for m in msgs1)

    msgs2 = _seed_glossary(tmp_path)
    assert not any("Created codex/glossary.yaml" in m for m in msgs2)
    assert not any("Created config.toml" in m for m in msgs2)


def test_seed_glossary_no_raise_when_both_files_exist(tmp_path):
    """conceptual-workflows-lore-init — Unit row 6 (idempotent re-entry)."""
    from lore.init import _seed_glossary

    (tmp_path / ".lore" / "codex").mkdir(parents=True)
    (tmp_path / ".lore" / "codex" / "glossary.yaml").write_text("items: []\n")
    (tmp_path / ".lore" / "config.toml").write_text("\n")

    # Must not raise
    _seed_glossary(tmp_path)


def test_run_init_calls_seed_glossary_in_order(tmp_path, monkeypatch):
    """conceptual-workflows-lore-init — Unit row 7 (Scenario 8 ordering).

    docs/AGENTS.md / LORE-AGENT.md seeding (the ``_copy_defaults_tree("docs", ...)``
    call) must precede ``_seed_glossary``; watcher seeding must follow it.
    """
    from lore import init as init_mod

    monkeypatch.chdir(tmp_path)
    calls: list[str] = []

    real_copy = init_mod._copy_defaults_tree
    real_seed = init_mod._seed_glossary

    def trace_copy(pkg, *args, **kwargs):
        calls.append(f"copy:{pkg}")
        return real_copy(pkg, *args, **kwargs)

    def trace_seed(root):
        calls.append("seed_glossary")
        return real_seed(root)

    monkeypatch.setattr(init_mod, "_copy_defaults_tree", trace_copy)
    monkeypatch.setattr(init_mod, "_seed_glossary", trace_seed)

    init_mod.run_init()

    assert "seed_glossary" in calls, f"_seed_glossary must be called by run_init: {calls}"
    assert "copy:docs" in calls, f"docs copy must occur in run_init: {calls}"
    assert calls.index("copy:docs") < calls.index("seed_glossary"), (
        f"docs (LORE-AGENT.md) seeding must precede glossary seeding: {calls}"
    )
    if "copy:watchers" in calls:
        assert calls.index("seed_glossary") < calls.index("copy:watchers"), (
            f"glossary seeding must precede watchers seeding: {calls}"
        )


def test_seed_glossary_uses_paths_helpers(tmp_path, monkeypatch):
    """conceptual-workflows-lore-init — Unit row 8 (DRY — paths.py is the SSOT)."""
    from lore import init as init_mod
    from lore import paths as paths_mod

    seen: list[str] = []
    real_g = paths_mod.glossary_path
    real_c = paths_mod.config_path

    def patched_g(root):
        seen.append("glossary_path")
        return real_g(root)

    def patched_c(root):
        seen.append("config_path")
        return real_c(root)

    # Patch on both paths and the init module — _seed_glossary may import
    # either form.  At least one path through init.py must use both helpers.
    monkeypatch.setattr(paths_mod, "glossary_path", patched_g)
    monkeypatch.setattr(paths_mod, "config_path", patched_c)
    if hasattr(init_mod, "glossary_path"):
        monkeypatch.setattr(init_mod, "glossary_path", patched_g, raising=False)
    if hasattr(init_mod, "config_path"):
        monkeypatch.setattr(init_mod, "config_path", patched_c, raising=False)

    init_mod._seed_glossary(tmp_path)

    assert "glossary_path" in seen, (
        "_seed_glossary must resolve glossary location via lore.paths.glossary_path"
    )
    assert "config_path" in seen, (
        "_seed_glossary must resolve config location via lore.paths.config_path"
    )


# ---------------------------------------------------------------------------
# ADR-006 structural assertions on seeded contents (Unit rows 10–12 surfaced
# at the unit level so they fail fast independent of CLI plumbing).
# ---------------------------------------------------------------------------


def test_seed_glossary_writes_yaml_parsing_to_dict_with_items_list(tmp_path):
    """conceptual-workflows-lore-init — Unit row 10 (ADR-006 structural)."""
    import yaml
    from lore.init import _seed_glossary

    _seed_glossary(tmp_path)
    data = yaml.safe_load(
        (tmp_path / ".lore" / "codex" / "glossary.yaml").read_text()
    )
    assert isinstance(data, dict)
    assert isinstance(data.get("items"), list)


def test_seed_glossary_writes_toml_with_show_glossary_true(tmp_path):
    """conceptual-workflows-lore-init — Unit row 11 (ADR-006 structural)."""
    import tomllib
    from lore.init import _seed_glossary

    _seed_glossary(tmp_path)
    with (tmp_path / ".lore" / "config.toml").open("rb") as f:
        data = tomllib.load(f)
    assert data.get("show-glossary-on-codex-commands") is True


# ---------------------------------------------------------------------------
# Defaults gitignore — Unit row 9 (US-006).
# ---------------------------------------------------------------------------


def test_default_gitignore_un_ignores_config_toml():
    """conceptual-workflows-lore-init — Unit row 9 (Scenario 7 source side)."""
    text = importlib.resources.files("lore.defaults").joinpath("gitignore").read_text()
    assert "!config.toml" in text.splitlines(), (
        "src/lore/defaults/gitignore must contain a literal `!config.toml` line "
        "so .lore/config.toml stays version-controlled despite the catch-all `*` rule."
    )
