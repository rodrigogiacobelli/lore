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


# ---------------------------------------------------------------------------
# US-001 (init-seed-codex-md-us-1) — _seed_codex_md + _seed_user_tracked
# umbrella seeder + paths.codex_md_path. ADR-006 enforced — exactly ONE
# full-equality assertion (test_seed_codex_md_rewrites_id_to_codex_byte_for_byte)
# pinning the literal `id: example-codex` -> `id: codex` substitution.
# ---------------------------------------------------------------------------


def test_seed_codex_md_writes_file_when_absent(tmp_path):
    """conceptual-workflows-lore-init step 7a — first bullet (codex.md seed-when-absent).

    init-seed-codex-md-us-1 Unit row 1.
    """
    from lore.init import _seed_codex_md

    msgs = _seed_codex_md(tmp_path)
    target = tmp_path / ".lore" / "codex" / "codex.md"
    assert target.is_file()
    # Structural list-shape only — single-element list with the expected message.
    assert msgs == ["  Created codex/codex.md"]


def test_seed_codex_md_idempotent_returns_empty_when_target_exists(tmp_path):
    """conceptual-workflows-lore-init step 7a (idempotency clause) — ADR-013.

    init-seed-codex-md-us-1 Unit row 2.
    """
    from lore.init import _seed_codex_md

    target = tmp_path / ".lore" / "codex" / "codex.md"
    target.parent.mkdir(parents=True)
    target.write_text("pre-existing user content\n", encoding="utf-8")
    msgs = _seed_codex_md(tmp_path)
    assert msgs == []
    # User content (not seed content) — ADR-006 permits direct equality here.
    assert (
        target.read_text(encoding="utf-8") == "pre-existing user content\n"
    )


def test_seed_codex_md_rewrites_id_to_codex_byte_for_byte(tmp_path):
    """conceptual-workflows-lore-init step 7a — `id:` rewrite contract.

    init-seed-codex-md-us-1 Unit row 3.

    ADR-006 EXCEPTION: this is the ONE allowed full-equality assertion on
    seeded content, pinning the literal one-line substitution per the Tech
    Spec "Core Architectural Decisions" row 3. All other tests in this
    module/file stay structural / substring-only on seeded content.
    """
    from importlib import resources

    from lore.init import _seed_codex_md

    _seed_codex_md(tmp_path)
    written = (tmp_path / ".lore" / "codex" / "codex.md").read_text(
        encoding="utf-8"
    )
    source = (
        resources.files("lore.defaults")
        .joinpath("artifacts/codex/codex.md")
        .read_text(encoding="utf-8")
    )
    # ADR-006 sanctioned full-equality assertion — pins the one-line id rewrite.
    assert written == source.replace("id: example-codex", "id: codex", 1)


def test_seed_codex_md_frontmatter_id_is_codex_not_example(tmp_path):
    """conceptual-workflows-lore-init step 7a — schema-valid frontmatter (id == 'codex').

    init-seed-codex-md-us-1 Unit row 4. Structural-only assertion (ADR-006).
    """
    import yaml

    from lore.init import _seed_codex_md

    _seed_codex_md(tmp_path)
    text = (tmp_path / ".lore" / "codex" / "codex.md").read_text(
        encoding="utf-8"
    )
    fm_end = text.index("\n---\n", 4)
    front = yaml.safe_load(text[4:fm_end])
    assert front["id"] == "codex"
    assert front["id"] != "example-codex"


def test_seed_codex_md_creates_codex_parent_dir(tmp_path):
    """conceptual-workflows-lore-init step 7a — parent dir created on the fly.

    init-seed-codex-md-us-1 Unit row 5. Mirrors _seed_skeleton_if_absent's
    existing mkdir(parents=True, exist_ok=True) contract.
    """
    from lore.init import _seed_codex_md

    assert not (tmp_path / ".lore" / "codex").exists()
    _seed_codex_md(tmp_path)
    assert (tmp_path / ".lore" / "codex").is_dir()
    assert (tmp_path / ".lore" / "codex" / "codex.md").is_file()


def test_seed_user_tracked_fresh_project_messages_in_order(tmp_path):
    """conceptual-workflows-lore-init step 7a — umbrella seeder message order.

    init-seed-codex-md-us-1 Unit row 6. codex.md first, glossary.yaml second,
    config.toml third (Tech Spec row 5).
    """
    from lore.init import _seed_user_tracked

    msgs = _seed_user_tracked(tmp_path)
    joined = "\n".join(msgs)
    i_codex = joined.index("Created codex/codex.md")
    i_gloss = joined.index("Created codex/glossary.yaml")
    i_conf = joined.index("Created config.toml")
    assert i_codex < i_gloss < i_conf


def test_seed_user_tracked_all_present_returns_empty(tmp_path):
    """conceptual-workflows-lore-init step 7a (idempotency across all three files).

    init-seed-codex-md-us-1 Unit row 7.
    """
    from lore.init import _seed_user_tracked

    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "codex.md").write_text("user\n", encoding="utf-8")
    (codex_dir / "glossary.yaml").write_text("items: []\n", encoding="utf-8")
    (tmp_path / ".lore" / "config.toml").write_text("\n", encoding="utf-8")
    assert _seed_user_tracked(tmp_path) == []


def test_seed_user_tracked_mixed_state_seeds_only_missing(tmp_path):
    """conceptual-workflows-lore-init step 7a — per-file independence of idempotency.

    init-seed-codex-md-us-1 Unit row 8. codex.md exists, glossary/config missing.
    """
    from lore.init import _seed_user_tracked

    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    user_codex = "---\nid: codex\ntitle: Mine\nsummary: mine\n---\n"
    (codex_dir / "codex.md").write_text(user_codex, encoding="utf-8")
    msgs = _seed_user_tracked(tmp_path)
    joined = "\n".join(msgs)
    assert "Created codex/codex.md" not in joined      # untouched
    assert "Created codex/glossary.yaml" in joined     # seeded
    assert "Created config.toml" in joined             # seeded
    # User content preserved (user-supplied, not seed content — ADR-006 allows).
    assert (codex_dir / "codex.md").read_text(encoding="utf-8") == user_codex


def test_codex_md_path_returns_expected_subpath(tmp_path):
    """conceptual-workflows-lore-init step 7a — new paths helper mirrors glossary_path.

    init-seed-codex-md-us-1 Unit row 9 — covers src/lore/paths.py.
    """
    from lore.paths import codex_md_path

    assert codex_md_path(tmp_path) == tmp_path / ".lore" / "codex" / "codex.md"


# ---------------------------------------------------------------------------
# Rite directory seeding on `lore init`.
# Spec: transient-rites-us-1 (lore codex show transient-rites-us-1)
# Anchor: tech-arch-source-layout (init.py seeding obligation)
#
# After init, .lore/rites/main/ and .lore/rites/shared/ must exist as dirs.
# ---------------------------------------------------------------------------


def test_init_creates_rite_main_dir(tmp_path, monkeypatch):
    """transient-rites-us-1 — Unit: after run_init, .lore/rites/main/ exists."""
    from lore import init as init_mod

    monkeypatch.chdir(tmp_path)
    init_mod.run_init()
    assert (tmp_path / ".lore" / "rites" / "main").is_dir()


def test_init_creates_rite_shared_dir(tmp_path, monkeypatch):
    """transient-rites-us-1 — Unit: after run_init, .lore/rites/shared/ exists."""
    from lore import init as init_mod

    monkeypatch.chdir(tmp_path)
    init_mod.run_init()
    assert (tmp_path / ".lore" / "rites" / "shared").is_dir()
