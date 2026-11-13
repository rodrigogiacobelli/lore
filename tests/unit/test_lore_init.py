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
import json as _json
import re as _re
import shutil as _shutil
from dataclasses import replace as _dc_replace
from pathlib import Path as _Path

import pytest

from lore import init as _init
from lore import manifest as _manifest
from lore import safewrite as _safewrite
from lore.initplan import FileAction as _FileAction
from lore.initplan import Feature as _Feature
from lore.initplan import Profile as _Profile
from lore.initplan import Route as _Route
from lore.legacy_init import profile_from_legacy as _profile_from_legacy
from tests.unit.conftest import HARNESS_BARE as _ALL_OFF
from tests.unit.conftest import FIXTURE_PROFILES as _FIXTURE_PROFILES
from tests.unit.conftest import EVERY_VALID_PROFILE as _RANDOM_PROFILES



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
    """conceptual-workflows-lore-init — Unit row 3 (FR-27, FR-28 idempotency).

    The glossary is left byte-for-byte alone. So is every settings line in the
    config; interactive-init-us-020 regenerates the comment header above them,
    and nothing else.
    """
    from lore.config import render_known_keys_header
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
    assert (tmp_path / ".lore" / "config.toml").read_text() == (
        render_known_keys_header() + user_config
    )


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

    The artifacts and doctrines seeding (the ``_copy_defaults_tree`` calls) must
    precede ``_seed_glossary``; watcher seeding must follow it. The ``docs`` tree
    is no longer copied: the getting-started page is rendered.
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
    assert "copy:docs" not in calls, f"the docs tree is rendered, not copied: {calls}"
    assert calls.index("copy:artifacts") < calls.index("seed_glossary"), (
        f"artifacts seeding must precede glossary seeding: {calls}"
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


# ---------------------------------------------------------------------------
# LORE-AGENT.md is rendered, not copied.
# Spec: interactive-init-us-007 (lore codex show interactive-init-us-007)
# Workflow: conceptual-workflows-lore-init
#
# ADR-006 boundary: the assertions below read the rendered text only for its
# generated-region markers and for the absence of a hand-maintained table. No
# sentence of any block's prose is pinned.
# ---------------------------------------------------------------------------

TABLE_OPENER = "<!-- lore:skills-table -->"
TABLE_CLOSER = "<!-- lore:skills-table end -->"
TABLE_HEADER = "| Skill | What it does | Where |"


def _table_rows(text: str) -> list[str]:
    """The body rows of the generated skills table, header and rule excluded."""
    lines = text.splitlines()
    assert TABLE_HEADER in lines, f"no generated skills table in:\n{text[:400]}"
    start = lines.index(TABLE_HEADER) + 2
    rows: list[str] = []
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        rows.append(line)
    return rows


def test_rendered_text_carries_no_generated_region_markers():
    """interactive-init-us-007 — Unit: neither generated region survives rendering."""
    from lore import init as init_mod

    text = init_mod.render_agent_instructions(
        profile=_Profile(), install_roots=(_Path(".lore/skills"),)
    )
    assert isinstance(text, str)
    assert "<!-- lore:skills-table" not in text
    assert "<!-- lore:access" not in text


def test_skills_table_rows_sorted_and_one_per_id():
    """interactive-init-us-007 — Unit: one markdown row per id, sorted."""
    from lore.init import _render_skills_table

    table = _render_skills_table(
        ("update-watcher", "inquest", "store-memory"), (_Path(".claude/skills"),)
    )
    rows = _table_rows(table)
    assert len(rows) == 3
    assert [row.split("|")[1].strip().strip("`") for row in rows] == [
        "inquest",
        "store-memory",
        "update-watcher",
    ]


def test_skills_table_middle_column_is_populated_from_the_skill_frontmatter():
    """interactive-init-us-007 — Unit: the description column is filled, never asserted."""
    from lore.init import _render_skills_table

    table = _render_skills_table(("store-memory",), (_Path(".lore/skills"),))
    cells = [cell.strip() for cell in _table_rows(table)[0].split("|") if cell.strip()]
    assert len(cells) == 3
    assert cells[1], "the What it does column is empty"


def test_empty_selection_renders_header_only():
    """interactive-init-us-007 — Unit: no skills selected is a header-only table."""
    from lore.init import _render_skills_table

    table = _render_skills_table((), (_Path(".lore/skills"),))
    assert TABLE_HEADER in table
    assert _table_rows(table) == []


def test_a_skill_installed_into_two_roots_lists_both():
    """Lane I finding 8 — `.lore/LORE-AGENT.md` is canonical for every agent.

    A project selecting Claude Code and Gemini installs each skill twice, and
    the Gemini user is pointed at this same file: naming only the
    alphabetically first root sends half the readers to a path they have not
    got.
    """
    from lore.init import _render_skills_table

    table = _render_skills_table(("inquest",), (".claude/skills", ".lore/skills"))
    row = _table_rows(table)[0]
    assert ".claude/skills/inquest/" in row
    assert ".lore/skills/inquest/" in row


def test_table_paths_use_posix_separators():
    """interactive-init-us-007 — Unit: the path column is POSIX on every platform."""
    from pathlib import PureWindowsPath

    from lore.init import _render_skills_table

    table = _render_skills_table(("inquest",), (PureWindowsPath(r".claude\skills"),))
    assert ".claude/skills/inquest/" in table
    assert "\\" not in table


def test_unterminated_skills_table_region_raises_naming_the_line():
    """interactive-init-us-007 — Unit: an unterminated generated region is a defect."""
    from lore import init as init_mod

    with pytest.raises(ValueError) as excinfo:
        init_mod._replace_skills_table_region(
            f"# Lore\n\nintro\n{TABLE_OPENER}\nplaceholder\n", "table\n", "lore-agent"
        )
    assert ":4" in str(excinfo.value)


def test_a_skills_table_closer_with_no_opener_raises():
    """interactive-init-us-007 — Unit: the mirror defect is caught too."""
    from lore import init as init_mod

    with pytest.raises(ValueError) as excinfo:
        init_mod._replace_skills_table_region(
            f"# Lore\n{TABLE_CLOSER}\n", "table\n", "lore-agent"
        )
    assert ":2" in str(excinfo.value)


def test_two_identical_render_calls_are_byte_identical():
    """interactive-init-us-007 — Unit: determinism, because the manifest hashes this."""
    from lore import init as init_mod

    kwargs = {"profile": _Profile(), "install_roots": (_Path(".claude/skills"),)}
    first = init_mod.render_agent_instructions(**kwargs)
    second = init_mod.render_agent_instructions(**kwargs)
    assert first.encode("utf-8") == second.encode("utf-8")


def test_the_shipped_instruction_document_has_exactly_one_skills_table_region():
    """interactive-init-us-007 — Unit: the document is structurally correct."""
    from lore import skills as skills_mod

    text = skills_mod.render_document("lore-agent", _Profile())
    assert text is not None
    assert text.count(TABLE_OPENER) == 1
    assert text.count(TABLE_CLOSER) == 1
    assert text.index(TABLE_OPENER) < text.index(TABLE_CLOSER)


def test_the_rendered_document_has_no_table_row_naming_a_retired_skill():
    """interactive-init-us-007 — Unit: no hand-written skills table survives."""
    from lore import init as init_mod
    from lore import skills as skills_mod

    retired = set(skills_mod.load_catalogue().get("retired", {}))
    text = init_mod.render_agent_instructions(
        profile=_Profile(), install_roots=(_Path(".lore/skills"),)
    )
    rows = [line for line in text.splitlines() if line.startswith("|")]
    assert rows
    for row in rows:
        for retired_id in retired:
            assert f"`{retired_id}`" not in row, f"stale table row names {retired_id}"


# ---------------------------------------------------------------------------
# Lore owns a marked block inside files the user owns.
# Spec: interactive-init-us-012 (lore codex show interactive-init-us-012)
# Anchor: conceptual-workflows-lore-init — instruction-file marker block,
#         root gitignore block, installed-skill tracking.
#
# Every branch below is a user-file-safety branch: what survives a write is the
# whole point, so each one is asserted on bytes rather than on substrings.
# ---------------------------------------------------------------------------

HTML_BEGIN = "<!-- lore:begin -->"
HTML_END = "<!-- lore:end -->"


def _md_markers() -> tuple[str, str]:
    return _init._marker_pair("CLAUDE.md")


class TestMarkerPairSelection:
    """interactive-init-us-012 — Unit: the marker form follows the target."""

    def test_html_markers_for_markdown_targets(self):
        for target in ("CLAUDE.md", "AGENTS.md", ".cursor/rules/lore.mdc"):
            begin, end = _init._marker_pair(target)
            assert begin == HTML_BEGIN
            assert end == HTML_END

    def test_hash_comment_markers_for_gitignore(self):
        begin, end = _init._marker_pair(".gitignore")
        assert begin.startswith("# lore:begin")
        assert end == "# lore:end"

    def test_the_gitignore_opener_says_the_block_is_managed(self):
        begin, _ = _init._marker_pair(".gitignore")
        assert "lore init" in begin
        assert "replaced" in begin


class TestWriteMarkedSection:
    """interactive-init-us-012 — Unit: create, append, replace."""

    def test_creates_the_file_when_absent(self, tmp_path):
        target = tmp_path / "CLAUDE.md"
        _init.write_marked_section(target, "hello\n", markers=_md_markers())
        assert target.read_text(encoding="utf-8") == f"{HTML_BEGIN}\nhello\n{HTML_END}\n"

    def test_creates_parent_directories(self, tmp_path):
        target = tmp_path / ".cursor" / "rules" / "lore.mdc"
        _init.write_marked_section(target, "hello\n", markers=_md_markers())
        assert target.is_file()

    def test_appends_when_the_file_has_no_markers(self, tmp_path):
        target = tmp_path / "CLAUDE.md"
        original = "# My project\n\nSome prose I wrote.\n"
        target.write_text(original, encoding="utf-8")
        _init.write_marked_section(target, "block\n", markers=_md_markers())
        after = target.read_text(encoding="utf-8")
        assert after.startswith(original)
        assert HTML_BEGIN in after and HTML_END in after

    def test_replaces_only_the_text_between_the_markers(self, tmp_path):
        target = tmp_path / "CLAUDE.md"
        before = "above\n"
        after_text = "below\n"
        target.write_text(
            f"{before}{HTML_BEGIN}\nold\n{HTML_END}\n{after_text}", encoding="utf-8"
        )
        _init.write_marked_section(target, "new\n", markers=_md_markers())
        result = target.read_text(encoding="utf-8")
        assert result == f"{before}{HTML_BEGIN}\nnew\n{HTML_END}\n{after_text}"

    def test_a_second_write_leaves_exactly_one_marker_pair(self, tmp_path):
        target = tmp_path / "CLAUDE.md"
        _init.write_marked_section(target, "one\n", markers=_md_markers())
        _init.write_marked_section(target, "two\n", markers=_md_markers())
        text = target.read_text(encoding="utf-8")
        assert text.count(HTML_BEGIN) == 1
        assert text.count(HTML_END) == 1
        assert "one" not in text

    def test_two_marker_pairs_raise_naming_the_file(self, tmp_path):
        target = tmp_path / "CLAUDE.md"
        target.write_text(
            f"{HTML_BEGIN}\na\n{HTML_END}\n{HTML_BEGIN}\nb\n{HTML_END}\n", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="CLAUDE.md"):
            _init.write_marked_section(target, "new\n", markers=_md_markers())

    def test_an_opener_with_no_closer_raises_naming_the_file(self, tmp_path):
        target = tmp_path / "CLAUDE.md"
        target.write_text(f"{HTML_BEGIN}\na\n", encoding="utf-8")
        with pytest.raises(ValueError, match="CLAUDE.md"):
            _init.write_marked_section(target, "new\n", markers=_md_markers())

    def test_the_block_the_manifest_hashes_is_what_was_written(self, tmp_path):
        target = tmp_path / "CLAUDE.md"
        target.write_text("above\n", encoding="utf-8")
        _init.write_marked_section(target, "block body\n", markers=_md_markers())
        begin, end = _md_markers()
        extracted = _manifest.section_text(
            target.read_text(encoding="utf-8"), begin, end
        )
        assert extracted == "block body\n"


class TestRemoveMarkedSection:
    """interactive-init-us-012 — Unit: retiring a source deletes the block alone."""

    def test_deletes_the_block_and_both_markers(self, tmp_path):
        target = tmp_path / "CLAUDE.md"
        target.write_text(
            f"above\n{HTML_BEGIN}\nblock\n{HTML_END}\nbelow\n", encoding="utf-8"
        )
        assert _init.remove_marked_section(target, markers=_md_markers()) is True
        assert target.read_text(encoding="utf-8") == "above\nbelow\n"

    def test_a_file_with_no_markers_is_left_untouched(self, tmp_path):
        target = tmp_path / "CLAUDE.md"
        original = b"just prose\n"
        target.write_bytes(original)
        assert _init.remove_marked_section(target, markers=_md_markers()) is False
        assert target.read_bytes() == original

    def test_an_absent_file_is_not_an_error(self, tmp_path):
        assert (
            _init.remove_marked_section(tmp_path / "nope.md", markers=_md_markers())
            is False
        )

    def test_the_file_survives_the_removal(self, tmp_path):
        target = tmp_path / "CLAUDE.md"
        target.write_text(f"{HTML_BEGIN}\nblock\n{HTML_END}\n", encoding="utf-8")
        _init.remove_marked_section(target, markers=_md_markers())
        assert target.is_file()


class TestNothingRendersARootGitignoreBlock:
    """The block is retired — no release renders one, so nothing can write one.

    Every line it carried named a path already ignored by the ``*`` opening
    `.lore/.gitignore`, so it decided nothing. What replaced it is a removal:
    `tests/e2e/test_init_root_gitignore_retired.py` covers the upgrade that
    takes the block back out of a project already carrying one.
    """

    def test_the_renderer_is_gone(self):
        assert not hasattr(_init, "render_root_gitignore_block")

    def test_the_entries_it_named_are_gone(self):
        assert not hasattr(_init, "ROOT_GITIGNORE_ENTRIES")

    def test_the_source_token_that_produced_it_is_gone(self):
        assert not hasattr(_init, "ROOT_GITIGNORE_SOURCE")

    def test_the_markers_stay_so_an_upgrade_can_still_find_the_block(self):
        begin, end = _init.GITIGNORE_MARKERS
        assert begin.startswith("# lore:begin")
        assert end == "# lore:end"


class TestSkillsGitignore:
    """interactive-init-us-012 — Unit: the listing written beside the skills."""

    def test_lore_only_lists_the_installed_directories_sorted_with_a_header(self):
        text = _init.render_skills_gitignore(("store-memory", "inquest"), "lore-only")
        lines = text.splitlines()
        comments = [line for line in lines if line.startswith("#")]
        entries = [line for line in lines if line and not line.startswith("#")]
        assert len(comments) == 2
        assert entries == ["inquest/", "store-memory/"]

    def test_none_signals_that_no_file_is_written(self):
        assert _init.render_skills_gitignore(("store-memory",), "none") is None

    def test_all_ignores_the_whole_directory_and_keeps_the_rule_itself_tracked(self):
        text = _init.render_skills_gitignore(("store-memory",), "all")
        entries = [
            line for line in text.splitlines() if line and not line.startswith("#")
        ]
        assert entries == ["*", "!.gitignore"]
        assert "store-memory/" not in entries

    def test_an_empty_selection_still_renders_the_header(self):
        text = _init.render_skills_gitignore((), "lore-only")
        assert text is not None
        assert [line for line in text.splitlines() if not line.startswith("#")] == []


class TestTheListingReachesEveryInstallRoot:
    """The answer governs where the skills went, not who the agent is.

    Five of the six agents have no native skills directory, so their skills go
    to `.lore/skills/`. The listing used to be written only for the other one,
    which left the blanket `skills/` line in the seeded `.lore/.gitignore`
    deciding all three answers for every one of them — including by hiding the
    user's own authored skills, which `lore-only` exists to keep.
    """

    FALLBACK = ".lore/skills/.gitignore"

    def test_the_fallback_root_gets_one(self, tmp_path):
        plan = _init.plan_init(project_root=tmp_path, agents=["agents-md"])
        assert self.FALLBACK in {entry.path for entry in plan.files}

    def test_a_project_with_no_agent_gets_one(self, tmp_path):
        plan = _init.plan_init(project_root=tmp_path, agents=["none"])
        assert self.FALLBACK in {entry.path for entry in plan.files}

    def test_a_native_root_still_gets_one(self, tmp_path):
        plan = _init.plan_init(project_root=tmp_path, agents=["claude"])
        assert ".claude/skills/.gitignore" in {entry.path for entry in plan.files}

    def test_a_mixed_selection_gets_one_in_each(self, tmp_path):
        plan = _init.plan_init(project_root=tmp_path, agents=["claude", "gemini"])
        paths = {entry.path for entry in plan.files}
        assert {self.FALLBACK, ".claude/skills/.gitignore"} <= paths

    def test_the_none_token_writes_none_of_them(self, tmp_path):
        plan = _init.plan_init(
            project_root=tmp_path, agents=["claude", "gemini"], skills_gitignore="none"
        )
        paths = {entry.path for entry in plan.files}
        assert not [path for path in paths if path.endswith("skills/.gitignore")]

    def test_the_all_token_writes_them_too(self, tmp_path):
        plan = _init.plan_init(
            project_root=tmp_path, agents=["claude", "gemini"], skills_gitignore="all"
        )
        paths = {entry.path for entry in plan.files}
        assert {self.FALLBACK, ".claude/skills/.gitignore"} <= paths

    def test_the_fallback_listing_is_sourced_the_way_a_legacy_one_is_read(
        self, tmp_path
    ):
        """`reconcile` already names this file `skills-gitignore:lore`."""
        plan = _init.plan_init(project_root=tmp_path, agents=["gemini"])
        entry = next(row for row in plan.files if row.path == self.FALLBACK)
        assert entry.source == "skills-gitignore:lore"

    def test_the_core_skills_alone_still_get_the_listing(self, tmp_path):
        """The core skills are always installed, so the listing is always written."""
        plan = _init.plan_init(
            project_root=tmp_path, agents=["claude"], skill_families=["none"]
        )
        paths = {entry.path for entry in plan.files}
        assert ".claude/skills/.gitignore" in paths

    def test_run_init_writes_one_under_dot_lore_skills(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _init.run_init()
        assert (tmp_path / ".lore" / "skills" / ".gitignore").is_file()


class TestTheSeededLoreIgnore:
    """The line that used to decide skill tracking for five of six agents."""

    def _seeded(self) -> list[str]:
        from importlib import resources

        text = resources.files("lore.defaults").joinpath("gitignore").read_text()
        return text.splitlines()

    def test_it_no_longer_ignores_the_skills_tree_wholesale(self):
        assert "skills/" not in self._seeded()

    def test_it_un_ignores_the_skills_tree_the_way_it_does_every_other_one(self):
        lines = self._seeded()
        assert "!skills" in lines
        assert "!skills/**" in lines


# ---------------------------------------------------------------------------
# plan_init computes an initialisation without performing it.
# Spec: interactive-init-us-014 (lore codex show interactive-init-us-014)
# Anchor: conceptual-workflows-lore-init — recorded answers, plan shape,
#         conditional prompts, plan/apply split.
# ---------------------------------------------------------------------------


ALL_FAMILIES = ("machinery", "memory", "workflow")


def _tree(root: _Path) -> dict[str, tuple[int, int]]:
    """Every file under *root*, with its size and mtime — a write detector."""
    snapshot: dict[str, tuple[int, int]] = {}
    for path in sorted(root.rglob("*")):
        stat = path.stat()
        snapshot[path.relative_to(root).as_posix()] = (
            stat.st_size if path.is_file() else -1,
            stat.st_mtime_ns,
        )
    return snapshot


def _write_config_toml(root: _Path, body: str) -> None:
    (root / ".lore").mkdir(parents=True, exist_ok=True)
    (root / ".lore" / "config.toml").write_text(body, encoding="utf-8")


def _record_a_retired_edit(root: _Path) -> _Path:
    """Leave one edited file behind that this release no longer ships.

    Records a manifest row for a path outside the desired set whose bytes do
    not match what was recorded — the retired-and-edited row, reached without
    waiting for a real retirement.
    """
    stale = root / ".lore" / "skills" / "gone-in-this-release" / "SKILL.md"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("# mine now\n", encoding="utf-8")

    installed = root / ".lore" / ".install-manifest.json"
    payload = _json.loads(installed.read_text(encoding="utf-8"))
    payload["files"].append(
        {
            "path": ".lore/skills/gone-in-this-release/SKILL.md",
            "kind": "owned",
            "source": "skill:gone-in-this-release",
            "hash": "sha256:" + "0" * 64,
        }
    )
    installed.write_text(_json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return stale


class TestPlanInitWritesNothing:
    """interactive-init-us-014 — Scenario 1 and Unit row 12."""

    def test_an_empty_directory_stays_empty(self, tmp_path):
        before = _tree(tmp_path)
        plan = _init.plan_init(project_root=tmp_path)
        assert plan.files
        assert _tree(tmp_path) == before
        assert not (tmp_path / ".lore").exists()

    def test_an_initialised_project_is_untouched(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _init.run_init()
        before = _tree(tmp_path)
        _init.plan_init(project_root=tmp_path)
        assert _tree(tmp_path) == before


class TestPlanInitResolutionOrder:
    """interactive-init-us-014 — Scenario 2 and Unit row 2: argument > config > default."""

    def test_access_mode(self, tmp_path):
        _write_config_toml(tmp_path, 'init-access-mode = "cli"\n')
        assert _init.plan_init(project_root=tmp_path).answers.access_mode == "cli"
        assert (
            _init.plan_init(project_root=tmp_path, access_mode="native").answers.access_mode
            == "native"
        )

    def test_access_mode_without_a_config_file(self, tmp_path):
        assert _init.plan_init(project_root=tmp_path).answers.access_mode == "cli"

    def test_agents(self, tmp_path):
        _write_config_toml(tmp_path, 'init-agents = ["claude"]\n')
        assert _init.plan_init(project_root=tmp_path).answers.agents == ("claude",)
        assert _init.plan_init(project_root=tmp_path, agents=[]).answers.agents == ()
        assert (
            _init.plan_init(project_root=tmp_path, agents=["gemini"]).answers.agents
            == ("gemini",)
        )

    def test_skill_families(self, tmp_path):
        _write_config_toml(tmp_path, 'init-skill-families = ["memory"]\n')
        assert _init.plan_init(project_root=tmp_path).answers.skill_families == (
            "machinery",
            "memory",
        )
        assert (
            _init.plan_init(
                project_root=tmp_path, skill_families=["workflow"]
            ).answers.skill_families
            == ("machinery", "workflow")
        )

    def test_skill_families_default_is_every_family(self, tmp_path):
        assert _init.plan_init(project_root=tmp_path).answers.skill_families == ALL_FAMILIES

    def test_skills_gitignore(self, tmp_path):
        _write_config_toml(tmp_path, 'init-skills-gitignore = "none"\n')
        assert _init.plan_init(project_root=tmp_path).answers.skills_gitignore == "none"
        assert (
            _init.plan_init(project_root=tmp_path, skills_gitignore="all").answers.skills_gitignore
            == "all"
        )

    def test_the_two_unpersisted_answers_take_their_argument_or_their_default(self, tmp_path):
        default = _init.plan_init(project_root=tmp_path).answers
        assert default.on_existing_agent_file == "append"
        assert default.on_conflict == "skip"
        chosen = _init.plan_init(
            project_root=tmp_path,
            on_existing_agent_file="skip",
            on_conflict="overwrite",
        ).answers
        assert chosen.on_existing_agent_file == "skip"
        assert chosen.on_conflict == "overwrite"


class TestPlanInitReconfigure:
    """interactive-init-us-014 — Scenario 3 and Unit row 3.

    Scenario 3 as written — a bare ``reconfigure=True`` returning the built-in
    defaults — is the run `--reconfigure` itself refuses at the terminal, and
    ADR-011 does not let that refusal live in `cli.py` alone. So the rule the
    story wanted is held one layer up: `reconfigure=True` drops the config layer
    for the four persisted answers, and a call that supplies none of them is
    rejected rather than answered from the defaults.
    """

    def test_reconfigure_skips_the_config_layer_for_the_four_persisted_answers(self, tmp_path):
        _write_config_toml(
            tmp_path,
            'init-agents = ["claude"]\n'
            'init-access-mode = "cli"\n'
            'init-skill-families = ["memory"]\n'
            'init-skills-gitignore = "none"\n',
        )
        answers = _init.plan_init(
            project_root=tmp_path,
            reconfigure=True,
            agents=[],
            access_mode="native",
            skill_families=list(ALL_FAMILIES),
            skills_gitignore="lore-only",
        ).answers
        assert answers.agents == ()
        assert answers.access_mode == "native"
        assert answers.skill_families == ALL_FAMILIES
        assert answers.skills_gitignore == "lore-only"

    def test_reconfigure_with_no_new_answers_is_refused(self, tmp_path):
        _write_config_toml(
            tmp_path,
            'init-agents = ["claude"]\n'
            'init-access-mode = "cli"\n'
            'init-skill-families = ["memory"]\n'
            'init-skills-gitignore = "none"\n',
        )
        with pytest.raises(ValueError) as excinfo:
            _init.plan_init(project_root=tmp_path, reconfigure=True)
        assert "reconfigure" in str(excinfo.value)

    def test_the_recorded_answers_stay_readable_from_a_plain_plan_call(self, tmp_path):
        """The CLI preselects from `InitPlan.answers` on the first call (§3.3)."""
        _write_config_toml(tmp_path, 'init-agents = ["claude"]\ninit-access-mode = "cli"\n')
        recorded = _init.plan_init(project_root=tmp_path).answers
        assert recorded.agents == ("claude",)
        assert recorded.access_mode == "cli"

    def test_reconfigure_leaves_an_explicit_argument_alone(self, tmp_path):
        _write_config_toml(tmp_path, 'init-access-mode = "cli"\n')
        answers = _init.plan_init(
            project_root=tmp_path,
            access_mode="cli",
            reconfigure=True,
            agents=[],
            skill_families=["memory"],
            skills_gitignore="none",
        ).answers
        assert answers.access_mode == "cli"


class TestPlanInitProjectRoot:
    """interactive-init-us-014 — Unit row 1."""

    def test_project_root_none_resolves_to_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert _init.plan_init().project_root == _Path.cwd()


class TestPlanInitTokenValidation:
    """interactive-init-us-014 — Scenario 5 and Unit row 5."""

    def test_an_unknown_agent_raises_with_the_documented_wording(self, tmp_path):
        with pytest.raises(ValueError) as excinfo:
            _init.plan_init(project_root=tmp_path, agents=["cline"])
        assert str(excinfo.value) == (
            "Unknown agent: 'cline'. Known agents: agents-md, claude, cursor, gemini, none, qwen."
        )

    def test_none_combined_with_another_agent_raises(self, tmp_path):
        with pytest.raises(ValueError) as excinfo:
            _init.plan_init(project_root=tmp_path, agents=["none", "claude"])
        assert str(excinfo.value) == "--agent none cannot be combined with other agents."

    def test_an_unknown_access_mode_raises_naming_the_accepted_set(self, tmp_path):
        with pytest.raises(ValueError) as excinfo:
            _init.plan_init(project_root=tmp_path, access_mode="agentic")
        assert "agentic" in str(excinfo.value)
        assert "cli" in str(excinfo.value) and "native" in str(excinfo.value)

    def test_an_unknown_skill_family_raises_naming_the_token(self, tmp_path):
        with pytest.raises(ValueError) as excinfo:
            _init.plan_init(project_root=tmp_path, skill_families=["memory", "typo"])
        assert "typo" in str(excinfo.value)

    def test_an_unknown_conflict_policy_raises(self, tmp_path):
        with pytest.raises(ValueError, match="keep-new"):
            _init.plan_init(project_root=tmp_path, on_conflict="keep-new")

    def test_the_conflict_policy_message_matches_the_reconcilers(self, tmp_path):
        """`plan_init` checks the token up front so nothing is computed on a typo.

        `reconcile.reconcile` checks it again at its own boundary. Two checks,
        one wording — pinned here so they cannot drift apart.
        """
        from lore import reconcile

        with pytest.raises(ValueError) as through_plan:
            _init.plan_init(project_root=tmp_path, on_conflict="keep-new")
        with pytest.raises(ValueError) as through_reconcile:
            reconcile.reconcile({}, {}, tmp_path, on_conflict="keep-new")
        assert str(through_plan.value) == str(through_reconcile.value)

    def test_an_unknown_skills_gitignore_token_raises(self, tmp_path):
        with pytest.raises(ValueError, match="sometimes"):
            _init.plan_init(project_root=tmp_path, skills_gitignore="sometimes")

    def test_an_unknown_existing_file_policy_raises(self, tmp_path):
        with pytest.raises(ValueError, match="clobber"):
            _init.plan_init(project_root=tmp_path, on_existing_agent_file="clobber")

    def test_plan_init_routes_every_token_through_lore_validators(self, tmp_path, monkeypatch):
        """Unit row 5 — the wiring; the rules themselves are US-017."""
        from lore import validators

        called: list[str] = []
        for name in (
            "validate_agent_id",
            "validate_agent_selection",
            "validate_access_mode",
            "validate_skill_family",
            "validate_route",
            "validate_profile_answers",
        ):
            real = getattr(validators, name)

            def spy(*args, _name=name, _real=real, **kwargs):
                called.append(_name)
                return _real(*args, **kwargs)

            monkeypatch.setattr(validators, name, spy)

        _init.plan_init(
            project_root=tmp_path,
            agents=["claude"],
            access_mode="native",
            skill_families=["memory"],
            route="cli",
        )
        assert set(called) == {
            "validate_agent_id",
            "validate_agent_selection",
            "validate_access_mode",
            "validate_skill_family",
            "validate_route",
            "validate_profile_answers",
        }


class TestPlanInitAggregateFamilyTokens:
    """interactive-init-us-014 — Unit row 4: `all` and `none` on the Python surface."""

    def test_all_expands_to_every_family(self, tmp_path):
        assert (
            _init.plan_init(project_root=tmp_path, skill_families=["all"]).answers.skill_families
            == ALL_FAMILIES
        )

    def test_none_installs_no_skill(self, tmp_path):
        plan = _init.plan_init(project_root=tmp_path, skill_families=["none"])
        assert plan.answers.skill_families == ("machinery",)
        installed = {entry.source for entry in plan.files if entry.source.startswith("skill:")}
        assert installed == {"skill:update-doctrine", "skill:update-artifact", "skill:run-doctrine"}


class TestPlanShape:
    """interactive-init-us-014 — Unit rows 6, 7 and 13."""

    def test_files_are_sorted_by_path(self, tmp_path):
        plan = _init.plan_init(project_root=tmp_path, agents=["claude"])
        paths = [entry.path for entry in plan.files]
        assert paths == sorted(paths)

    def test_conflicts_is_exactly_the_conflict_subset(self, tmp_path):
        plan = _init.plan_init(project_root=tmp_path, agents=["claude"])
        assert plan.conflicts == tuple(
            entry for entry in plan.files if entry.action is _FileAction.CONFLICT
        )

    def test_targets_hold_one_row_per_selected_agent_in_registry_order(self, tmp_path):
        from lore import agents as agents_mod

        registry_order = [row.id for row in agents_mod.load_registry()]
        plan = _init.plan_init(project_root=tmp_path, agents=["gemini", "claude"])
        selected = [target.id for target in plan.targets]
        assert selected == [row for row in registry_order if row in {"claude", "gemini"}]

    def test_two_identical_calls_produce_equal_plans(self, tmp_path):
        first = _init.plan_init(project_root=tmp_path, agents=["claude"])
        second = _init.plan_init(project_root=tmp_path, agents=["claude"])
        assert first.files == second.files
        assert first.answers == second.answers


class TestPromptsNeeded:
    """interactive-init-us-014 — Scenario 6 and Unit rows 8-11."""

    def test_only_the_tracking_question_on_a_fresh_project_with_no_agent(self, tmp_path):
        """Its skills go to `.lore/skills/`, so the answer still decides something."""
        assert _init.plan_init(project_root=tmp_path).prompts_needed == (
            _init.PROMPT_SKILLS_GITIGNORE,
        )

    def test_the_existing_instruction_file_prompt_needs_a_file_without_markers(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("my own prose\n", encoding="utf-8")
        plan = _init.plan_init(project_root=tmp_path, agents=["claude"])
        assert _init.PROMPT_EXISTING_AGENT_FILE in plan.prompts_needed

    def test_a_file_that_already_carries_markers_does_not_ask(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text(
            f"prose\n{HTML_BEGIN}\nblock\n{HTML_END}\n", encoding="utf-8"
        )
        plan = _init.plan_init(project_root=tmp_path, agents=["claude"])
        assert _init.PROMPT_EXISTING_AGENT_FILE not in plan.prompts_needed

    def test_an_absent_file_does_not_ask(self, tmp_path):
        plan = _init.plan_init(project_root=tmp_path, agents=["claude"])
        assert _init.PROMPT_EXISTING_AGENT_FILE not in plan.prompts_needed

    def test_the_skills_tracking_prompt_fires_for_every_install_root(self, tmp_path):
        """Every project installs skills somewhere, so every project is asked.

        The gate used to read the agent's *native* directory, which is null for
        five of the six — so the projects whose skills land in `.lore/skills/`
        were never asked the question that decides whether their own authored
        skills survive a clone.
        """
        native = _init.plan_init(project_root=tmp_path, agents=["claude"])
        assert _init.PROMPT_SKILLS_GITIGNORE in native.prompts_needed
        fallback = _init.plan_init(project_root=tmp_path, agents=["agents-md"])
        assert _init.PROMPT_SKILLS_GITIGNORE in fallback.prompts_needed

    def test_the_conflict_prompt_needs_a_conflict(self, tmp_path, monkeypatch):
        """A file the project put where Lore writes — the one class left."""
        monkeypatch.chdir(tmp_path)
        mine = tmp_path / ".lore" / "skills" / "store-memory" / "SKILL.md"
        mine.parent.mkdir(parents=True)
        mine.write_text("# mine, and Lore never installed here\n", encoding="utf-8")
        plan = _init.plan_init(project_root=tmp_path)
        assert plan.conflicts
        assert _init.PROMPT_ON_CONFLICT in plan.prompts_needed

    def test_an_edited_lore_file_does_not_ask(self, tmp_path, monkeypatch):
        """Lore's own file is not a question, so it opens no prompt.

        The prompt used to fire here and offer "take the shipped version",
        which is now what happens anyway — a question with one real answer.
        """
        monkeypatch.chdir(tmp_path)
        _init.run_init()
        edited = tmp_path / ".lore" / "skills" / "store-memory" / "SKILL.md"
        edited.write_text("# mine now\n", encoding="utf-8")
        plan = _init.plan_init(project_root=tmp_path)
        assert plan.conflicts == ()
        assert _init.PROMPT_ON_CONFLICT not in plan.prompts_needed

    def test_no_conflict_means_no_conflict_prompt(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _init.run_init()
        plan = _init.plan_init(project_root=tmp_path)
        assert plan.conflicts == ()
        assert _init.PROMPT_ON_CONFLICT not in plan.prompts_needed

    def test_a_retired_and_edited_file_does_not_ask_either(
        self, tmp_path, monkeypatch
    ):
        """It is removed and its successor named, so there is nothing to ask."""
        monkeypatch.chdir(tmp_path)
        _init.run_init()
        stale = _record_a_retired_edit(tmp_path)

        plan = _init.plan_init(project_root=tmp_path)

        row = next(
            entry
            for entry in plan.files
            if entry.path.endswith("gone-in-this-release/SKILL.md")
        )
        assert row.action is _FileAction.REMOVE
        assert plan.conflicts == ()
        assert _init.PROMPT_ON_CONFLICT not in plan.prompts_needed
        assert stale.is_file()

    def test_a_conflict_the_answer_cannot_settle_does_not_ask(
        self, tmp_path, monkeypatch
    ):
        """A link is a conflict neither answer moves, so it opens no question."""
        monkeypatch.chdir(tmp_path)
        outside = tmp_path.parent / "outside-the-project"
        outside.mkdir(exist_ok=True)
        (outside / "notes.md").write_text("my notes\n", encoding="utf-8")
        planted = tmp_path / ".lore" / "skills" / "store-memory" / "SKILL.md"
        planted.parent.mkdir(parents=True)
        planted.symlink_to(outside / "notes.md")

        plan = _init.plan_init(project_root=tmp_path)

        assert plan.conflicts
        assert _init.PROMPT_ON_CONFLICT not in plan.prompts_needed


class TestUnmarkedInstructionFiles:
    """The FR-4 gate and the question it opens read one list, so they agree."""

    def test_it_names_a_file_that_exists_without_markers(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("my own prose\n", encoding="utf-8")
        plan = _init.plan_init(project_root=tmp_path, agents=["claude"])
        assert _init.unmarked_instruction_files(tmp_path, plan.targets) == ("CLAUDE.md",)

    def test_it_leaves_out_an_agent_whose_file_does_not_exist_yet(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("my own prose\n", encoding="utf-8")
        plan = _init.plan_init(project_root=tmp_path, agents=["claude", "gemini"])
        assert _init.unmarked_instruction_files(tmp_path, plan.targets) == ("CLAUDE.md",)

    def test_it_leaves_out_a_file_that_already_carries_markers(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text(
            f"prose\n{HTML_BEGIN}\nblock\n{HTML_END}\n", encoding="utf-8"
        )
        plan = _init.plan_init(project_root=tmp_path, agents=["claude"])
        assert _init.unmarked_instruction_files(tmp_path, plan.targets) == ()

    def test_it_is_what_the_prompt_gate_reads(self, tmp_path):
        (tmp_path / "GEMINI.md").write_text("my own prose\n", encoding="utf-8")
        plan = _init.plan_init(project_root=tmp_path, agents=["claude", "gemini"])
        assert _init.unmarked_instruction_files(tmp_path, plan.targets) == ("GEMINI.md",)
        assert _init.PROMPT_EXISTING_AGENT_FILE in plan.prompts_needed


class TestDesiredSetComposition:
    """interactive-init-us-011 Scenario 6 and interactive-init-us-014 Tech Notes.

    The composed desired set carries more than the skills: the rendered
    instruction text, each selected agent's marked block, the root gitignore
    block and the skills gitignore.
    """

    def test_an_empty_family_selection_leaves_the_core_text_and_skills(self, tmp_path):
        """`--skills none` switches every optional feature off; the core stays."""
        plan = _init.plan_init(project_root=tmp_path, skill_families=["none"])
        paths = {entry.path for entry in plan.files}
        assert ".lore/LORE-AGENT.md" in paths
        skill_dirs = {
            path.split("/")[2]
            for path in paths
            if path.startswith(".lore/skills/") and path.endswith("SKILL.md")
        }
        assert skill_dirs == {"update-doctrine", "update-artifact", "run-doctrine"}

    def test_a_selected_agent_contributes_a_section_entry_for_its_file(self, tmp_path):
        plan = _init.plan_init(project_root=tmp_path, agents=["claude"])
        entry = next(row for row in plan.files if row.path == "CLAUDE.md")
        assert entry.kind == "section"
        assert entry.source == "agent-instructions:claude"

    def test_no_agent_contributes_no_instruction_file_outside_dot_lore(self, tmp_path):
        plan = _init.plan_init(project_root=tmp_path, agents=["none"])
        for entry in plan.files:
            assert entry.kind != "section"

    def test_no_run_desires_the_root_gitignore(self, tmp_path):
        plan = _init.plan_init(project_root=tmp_path)
        assert ".gitignore" not in {entry.path for entry in plan.files}

    def test_the_skills_gitignore_rides_on_every_install_root(self, tmp_path):
        native = _init.plan_init(project_root=tmp_path, agents=["claude"])
        assert ".claude/skills/.gitignore" in {entry.path for entry in native.files}
        fallback = _init.plan_init(project_root=tmp_path, agents=["agents-md"])
        assert ".lore/skills/.gitignore" in {entry.path for entry in fallback.files}

    def test_the_none_token_writes_no_skills_gitignore(self, tmp_path):
        plan = _init.plan_init(
            project_root=tmp_path, agents=["claude"], skills_gitignore="none"
        )
        assert ".claude/skills/.gitignore" not in {entry.path for entry in plan.files}

    def test_the_canonical_text_names_every_root_the_skills_went_to(self, tmp_path):
        """Two agents, two skills roots, and one canonical file describing both."""
        plan = _init.plan_init(
            project_root=tmp_path, agents=["claude", "gemini"], skill_families=["memory"]
        )
        desired = _init.build_desired(
            project_root=tmp_path, targets=plan.targets, answers=plan.answers
        )
        text = desired[".lore/LORE-AGENT.md"].content.decode("utf-8")
        assert ".claude/skills/store-memory/" in text
        assert ".lore/skills/store-memory/" in text

    def test_an_agents_own_block_names_only_its_own_root(self, tmp_path):
        plan = _init.plan_init(
            project_root=tmp_path, agents=["claude", "gemini"], skill_families=["memory"]
        )
        desired = _init.build_desired(
            project_root=tmp_path, targets=plan.targets, answers=plan.answers
        )
        claude = desired["CLAUDE.md"].content.decode("utf-8")
        gemini = desired["GEMINI.md"].content.decode("utf-8")
        assert ".claude/skills/store-memory/" in claude
        assert ".lore/skills/store-memory/" not in claude
        assert ".lore/skills/store-memory/" in gemini
        assert ".claude/skills/store-memory/" not in gemini

    def test_skip_drops_the_section_entry_for_an_existing_unmarked_file(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("mine\n", encoding="utf-8")
        plan = _init.plan_init(
            project_root=tmp_path, agents=["claude"], on_existing_agent_file="skip"
        )
        assert "CLAUDE.md" not in {entry.path for entry in plan.files}
        assert ".lore/LORE-AGENT.md" in {entry.path for entry in plan.files}


class TestHeadlessPlanReproducesThePreFeatureFileSet:
    """interactive-init-us-014 — Scenario 4."""

    def test_no_keyword_arguments_selects_no_agent_and_every_family(self, tmp_path):
        plan = _init.plan_init(project_root=tmp_path)
        assert plan.answers.agents == ()
        assert plan.answers.access_mode == "cli"
        assert plan.answers.skill_families == ALL_FAMILIES

    def test_every_skill_path_sits_under_dot_lore_skills(self, tmp_path):
        plan = _init.plan_init(project_root=tmp_path)
        skill_paths = [entry.path for entry in plan.files if entry.source.startswith("skill:")]
        assert skill_paths
        for path in skill_paths:
            assert path.startswith(".lore/skills/")

    def test_no_path_falls_outside_dot_lore(self, tmp_path):
        """With no agent selected there is nowhere outside `.lore/` to write.

        The root `.gitignore` used to be the one exception. It is not written by
        any release now, so a headless plan for a project with no agent touches
        nothing the project owns at all.
        """
        plan = _init.plan_init(project_root=tmp_path)
        outside = {entry.path for entry in plan.files if not entry.path.startswith(".lore/")}
        assert outside == set()


# ---------------------------------------------------------------------------
# apply_init performs a computed plan; run_init still takes no arguments.
# Spec: interactive-init-us-015 (lore codex show interactive-init-us-015)
# Anchor: conceptual-workflows-lore-init — apply ordering, apply report,
#         error paths; conceptual-workflows-python-api — return-type contracts.
# ---------------------------------------------------------------------------


@pytest.fixture()
def recorded_writes(monkeypatch):
    """Every file write during a test, in order, as the path written.

    A write now lands by replacing the target with a temporary file rather than
    by opening it, so the observable event is ``safewrite.atomic_write_bytes``.
    The two ``Path`` writers are traced as well: a write site that ever bypassed
    the gate would show up here rather than quietly vanish from the order.
    """
    order: list[str] = []
    real_atomic = _safewrite.atomic_write_bytes
    real_text = _Path.write_text
    real_bytes = _Path.write_bytes

    def trace_atomic(target, data, **kwargs):
        order.append(str(target))
        return real_atomic(target, data, **kwargs)

    def trace_text(self, *args, **kwargs):
        order.append(str(self))
        return real_text(self, *args, **kwargs)

    def trace_bytes(self, *args, **kwargs):
        order.append(str(self))
        return real_bytes(self, *args, **kwargs)

    monkeypatch.setattr(_safewrite, "atomic_write_bytes", trace_atomic)
    monkeypatch.setattr(_Path, "write_text", trace_text)
    monkeypatch.setattr(_Path, "write_bytes", trace_bytes)
    return order


def _index_of(order: list[str], suffix: str) -> int:
    """Where *suffix* was first written. Suffix, so callers pass a relative path."""
    for position, path in enumerate(order):
        if path.endswith(suffix):
            return position
    raise AssertionError(f"{suffix} was never written; wrote {order}")


class TestApplyOrdering:
    """interactive-init-us-015 — Unit rows 1, 2 and 7 (Tech Spec §6.7)."""

    def test_the_manifest_is_the_final_write(self, tmp_path, recorded_writes):
        _init.apply_init(_init.plan_init(project_root=tmp_path, agents=["claude"]))
        assert recorded_writes[-1].endswith(".install-manifest.json")

    def test_the_documented_step_order_holds(self, tmp_path, recorded_writes):
        _init.apply_init(_init.plan_init(project_root=tmp_path, agents=["claude"]))
        steps = [
            _index_of(
                recorded_writes,
                "doctrines/default/update-changelog/update-changelog.design.md",
            ),
            _index_of(recorded_writes, ".claude/skills/store-memory/SKILL.md"),
            _index_of(recorded_writes, ".lore/LORE-AGENT.md"),
            _index_of(recorded_writes, "CLAUDE.md"),
            _index_of(recorded_writes, ".claude/skills/.gitignore"),
            _index_of(recorded_writes, ".install-manifest.json"),
        ]
        assert steps == sorted(steps), (
            "Tech Spec §6.7: seeded trees, skills, LORE-AGENT.md, instruction "
            f"blocks, skills gitignore, manifest — got {steps}"
        )

    def test_the_persisted_answers_are_written_before_the_manifest(
        self, tmp_path, recorded_writes
    ):
        _init.apply_init(_init.plan_init(project_root=tmp_path, agents=["claude"]))
        assert _index_of(recorded_writes, "config.toml") < _index_of(
            recorded_writes, ".install-manifest.json"
        )


class TestApplyResult:
    """interactive-init-us-015 — Scenario 2 and Unit rows 3 and 6."""

    def test_applied_and_skipped_partition_the_plan(self, tmp_path):
        plan = _init.plan_init(project_root=tmp_path, agents=["claude"])
        result = _init.apply_init(plan)
        assert set(result.applied) | set(result.skipped) == set(plan.files)
        assert not set(result.applied) & set(result.skipped)

    def test_the_manifest_path_comes_from_the_paths_helper(self, tmp_path):
        from lore.paths import install_manifest_path

        result = _init.apply_init(_init.plan_init(project_root=tmp_path))
        assert result.manifest_path == install_manifest_path(tmp_path)
        assert result.manifest_path.is_file()

    def test_every_planned_write_lands_with_the_planned_bytes(self, tmp_path):
        plan = _init.plan_init(
            project_root=tmp_path, agents=["claude"], skill_families=["memory"]
        )
        _init.apply_init(plan)
        for entry in plan.files:
            if entry.action is not _FileAction.CREATE:
                continue
            target = _manifest.resolve_path(tmp_path, entry.path)
            assert target.is_file(), entry.path
            assert _manifest.bytes_digest(target.read_bytes()) == entry.digest

    def test_the_result_names_the_project_root(self, tmp_path):
        result = _init.apply_init(_init.plan_init(project_root=tmp_path))
        assert result.project_root == tmp_path


class TestApplyRemovals:
    """interactive-init-us-015 — Scenarios 5 and 6, Unit rows 4 and 5."""

    def test_a_section_removal_deletes_the_block_and_never_unlinks(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _init.apply_init(_init.plan_init(project_root=tmp_path, agents=["claude"]))
        claude = tmp_path / "CLAUDE.md"
        claude.write_text(
            "mine above\n" + claude.read_text(encoding="utf-8") + "mine below\n",
            encoding="utf-8",
        )
        block_gone = _init.plan_init(project_root=tmp_path, agents=[])
        removals = [
            entry
            for entry in block_gone.files
            if entry.path == "CLAUDE.md" and entry.action is _FileAction.REMOVE
        ]
        assert removals, "retiring the agent must plan the block's removal"

        unlinked: list[str] = []
        real_unlink = _Path.unlink
        monkeypatch.setattr(
            _Path,
            "unlink",
            lambda self, *a, **k: (unlinked.append(str(self)), real_unlink(self, *a, **k))[1],
        )
        _init.apply_init(block_gone)
        assert claude.is_file()
        assert HTML_BEGIN not in claude.read_text(encoding="utf-8")
        assert "mine above" in claude.read_text(encoding="utf-8")
        assert "mine below" in claude.read_text(encoding="utf-8")
        assert not [path for path in unlinked if path.endswith("CLAUDE.md")]

    def test_an_oserror_on_unlink_is_reported_and_the_run_continues(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        _init.apply_init(_init.plan_init(project_root=tmp_path, agents=["claude"]))
        plan = _init.plan_init(project_root=tmp_path, agents=[])
        removals = [entry for entry in plan.files if entry.action is _FileAction.REMOVE]
        assert len(removals) >= 2, "need two removals to prove the run continues"
        doomed = removals[0].path

        real_unlink = _Path.unlink

        def flaky_unlink(self, *args, **kwargs):
            if self.as_posix().endswith(doomed):
                raise OSError("permission denied")
            return real_unlink(self, *args, **kwargs)

        monkeypatch.setattr(_Path, "unlink", flaky_unlink)
        result = _init.apply_init(plan)
        assert any("could not remove" in line for line in result.messages)
        survivor = _manifest.resolve_path(tmp_path, removals[1].path)
        assert not survivor.exists()

    def test_a_failed_removal_stays_in_the_next_manifest(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _init.apply_init(_init.plan_init(project_root=tmp_path, agents=["claude"]))
        plan = _init.plan_init(project_root=tmp_path, agents=[])
        doomed = next(
            entry.path for entry in plan.files if entry.action is _FileAction.REMOVE
        )
        real_unlink = _Path.unlink

        def flaky_unlink(self, *args, **kwargs):
            if self.as_posix().endswith(doomed):
                raise OSError("permission denied")
            return real_unlink(self, *args, **kwargs)

        monkeypatch.setattr(_Path, "unlink", flaky_unlink)
        _init.apply_init(plan)
        payload = _json.loads(
            (tmp_path / ".lore" / ".install-manifest.json").read_text(encoding="utf-8")
        )
        assert doomed in {row["path"] for row in payload["files"]}


class TestApplyReport:
    """interactive-init-us-015 — Scenario 7."""

    def test_a_kept_conflict_is_reported_with_its_detail(self, tmp_path, monkeypatch):
        """A file Lore never installed, at a path Lore wants: reported, untouched."""
        monkeypatch.chdir(tmp_path)
        mine = tmp_path / ".lore" / "skills" / "store-memory" / "SKILL.md"
        mine.parent.mkdir(parents=True)
        mine.write_text("# mine now\n", encoding="utf-8")
        result = _init.apply_init(_init.plan_init(project_root=tmp_path))
        kept = [line for line in result.messages if "! Kept" in line]
        assert kept
        assert any("store-memory" in line for line in kept)
        assert mine.read_text(encoding="utf-8") == "# mine now\n"

    def test_an_edited_lore_file_is_reported_as_an_overwrite(self, tmp_path, monkeypatch):
        """The ruling's report line: what happened, and how to avoid it next time."""
        monkeypatch.chdir(tmp_path)
        _init.run_init()
        edited = tmp_path / ".lore" / "skills" / "store-memory" / "SKILL.md"
        shipped = edited.read_text(encoding="utf-8")
        edited.write_text("# mine now\n", encoding="utf-8")

        result = _init.apply_init(_init.plan_init(project_root=tmp_path))

        assert edited.read_text(encoding="utf-8") == shipped
        assert not [line for line in result.messages if "! Kept" in line]
        assert any(
            "Updated" in line and "store-memory" in line for line in result.messages
        )


class TestRunInitStillTakesNoArguments:
    """interactive-init-us-015 — Scenario 1 and Unit rows 8-10."""

    def test_the_signature_takes_zero_parameters(self):
        import inspect

        assert inspect.signature(_init.run_init).parameters == {}

    def test_it_returns_a_list_of_strings(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        messages = _init.run_init()
        assert isinstance(messages, list)
        assert all(isinstance(line, str) for line in messages)

    def test_it_is_apply_init_of_plan_init(self, tmp_path, monkeypatch):
        first = tmp_path / "a"
        second = tmp_path / "b"
        first.mkdir()
        second.mkdir()
        monkeypatch.chdir(first)
        through_wrapper = _init.run_init()
        monkeypatch.chdir(second)
        through_parts = list(_init.apply_init(_init.plan_init()).messages)
        assert through_wrapper == through_parts

    def test_the_headless_run_writes_no_instruction_file_outside_dot_lore(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        _init.run_init()
        for name in ("CLAUDE.md", "AGENTS.md", "GEMINI.md", "QWEN.md"):
            assert not (tmp_path / name).exists()
        assert (tmp_path / ".lore" / "LORE-AGENT.md").is_file()

    def test_the_headless_run_puts_every_skill_under_dot_lore_skills(
        self, tmp_path, monkeypatch
    ):
        from lore import skills as skills_mod

        monkeypatch.chdir(tmp_path)
        _init.run_init()
        for skill_id in skills_mod.installed_skills(_Profile()):
            assert (tmp_path / ".lore" / "skills" / skill_id / "SKILL.md").is_file()

    def test_format_db_status_still_returns_its_three_branches(self):
        assert len(_init._format_db_status("created")) == 1
        assert len(_init._format_db_status("existing")) == 1
        assert len(_init._format_db_status("reinitialized")) == 1
        assert _init._format_db_status("unknown") == []


# ---------------------------------------------------------------------------
# render_plan — the summary a person reads before anything is written
#
# interactive-init-us-019 Scenario 3 and its unit rows. The renderer lives in
# `init.py` rather than `cli.py` so a unit test can reach it without importing
# `lore.cli` (technical-test-guidelines §2 and §6); `cli.py` calls it through
# the facade and keeps only the orchestration.
# ---------------------------------------------------------------------------


def _planned(path, action, *, kind="owned", source="skill:x", detail=None, reported=True):
    return _init.PlannedFile(
        path=path,
        action=action,
        kind=kind,
        source=source,
        digest=None if action is _FileAction.REMOVE else "sha256:abc",
        detail=detail,
        reported=reported,
    )


def _synthetic_plan(root, files, *, agents=("claude",), families=("memory", "workflow")):
    from lore.initplan import InitAnswers, InitPlan
    from lore.legacy_init import profile_from_legacy

    answers = InitAnswers(
        agents=agents,
        profile=profile_from_legacy("native", families),
        on_existing_agent_file="append",
        skills_gitignore="lore-only",
        on_conflict="skip",
    )
    return InitPlan(
        project_root=root,
        answers=answers,
        targets=(),
        files=tuple(files),
        prompts_needed=(),
    )


class TestRenderPlanHeader:
    """The header states where, for whom, and with what."""

    def test_it_names_the_root_the_agents_and_the_features_that_are_on(self, tmp_path):
        plan = _synthetic_plan(tmp_path, [])
        first = _init.render_plan(plan).splitlines()[0]
        assert first == (
            f"Plan for {tmp_path} (agents: claude · {plan.answers.profile.summary()})"
        )
        assert "route: harness" in first
        assert "memory" in first
        assert "quests" in first

    def test_several_agents_are_listed_in_the_plans_order(self, tmp_path):
        plan = _synthetic_plan(tmp_path, [], agents=("claude", "agents-md"))
        assert "agents: claude, agents-md" in _init.render_plan(plan)

    def test_an_empty_selection_reads_as_none_rather_than_blank(self, tmp_path):
        plan = _synthetic_plan(tmp_path, [], agents=(), families=())
        header = _init.render_plan(plan).splitlines()[0]
        assert "agents: none" in header
        assert "route:" in header


class TestRenderPlanLines:
    """One line per acted-on path, prefixed by what would happen to it."""

    def test_each_action_gets_its_own_word(self, tmp_path):
        plan = _synthetic_plan(
            tmp_path,
            [
                _planned("a/SKILL.md", _FileAction.CREATE),
                _planned("CLAUDE.md", _FileAction.SECTION, kind="section"),
                _planned("b/SKILL.md", _FileAction.OVERWRITE),
                _planned("c/SKILL.md", _FileAction.REMOVE, detail="renamed"),
                _planned("d/SKILL.md", _FileAction.CONFLICT, detail="you edited this"),
            ],
        )
        rendered = _init.render_plan(plan)
        assert "  Create   a/SKILL.md" in rendered
        assert "  Section  CLAUDE.md" in rendered
        assert "  Overwrite b/SKILL.md" in rendered
        assert "  Remove   c/SKILL.md" in rendered
        assert "  Conflict d/SKILL.md" in rendered

    def test_a_remove_line_quotes_its_retirement_reason_verbatim(self, tmp_path):
        reason = "merged into store-memory"
        plan = _synthetic_plan(
            tmp_path, [_planned("x/SKILL.md", _FileAction.REMOVE, detail=reason)]
        )
        line = next(
            row for row in _init.render_plan(plan).splitlines() if "x/SKILL.md" in row
        )
        assert line.endswith(reason)

    def test_a_conflict_line_quotes_its_explanation_verbatim(self, tmp_path):
        detail = "you edited this since Lore installed it"
        plan = _synthetic_plan(
            tmp_path, [_planned("y/SKILL.md", _FileAction.CONFLICT, detail=detail)]
        )
        line = next(
            row for row in _init.render_plan(plan).splitlines() if "y/SKILL.md" in row
        )
        assert line.endswith(detail)

    def test_a_path_lore_may_not_touch_reads_as_a_conflict(self, tmp_path):
        plan = _synthetic_plan(
            tmp_path,
            [_planned("z/SKILL.md", _FileAction.CONFLICT, detail="is a symlink")],
        )
        rendered = _init.render_plan(plan)
        assert "  Conflict z/SKILL.md" in rendered
        assert rendered.splitlines()[-1].strip().endswith("1 conflict")

    def test_a_no_op_entry_is_not_rendered(self, tmp_path):
        plan = _synthetic_plan(
            tmp_path,
            [
                _planned("kept/SKILL.md", _FileAction.CREATE, reported=False),
                _planned("new/SKILL.md", _FileAction.CREATE),
            ],
        )
        rendered = _init.render_plan(plan)
        assert "kept/SKILL.md" not in rendered
        assert "new/SKILL.md" in rendered

    def test_lines_keep_the_plans_path_order(self, tmp_path):
        plan = _synthetic_plan(
            tmp_path,
            [
                _planned("a.md", _FileAction.CREATE),
                _planned("b.md", _FileAction.CREATE),
                _planned("c.md", _FileAction.CREATE),
            ],
        )
        rendered = _init.render_plan(plan)
        assert rendered.index("a.md") < rendered.index("b.md") < rendered.index("c.md")


class TestRenderPlanCounts:
    """The closing tally, in the fixed order, zeroes included."""

    def test_the_counts_line_uses_the_five_action_words_in_order(self, tmp_path):
        plan = _synthetic_plan(
            tmp_path,
            [
                _planned("a", _FileAction.CREATE),
                _planned("b", _FileAction.CREATE),
                _planned("c", _FileAction.SECTION, kind="section"),
                _planned("d", _FileAction.OVERWRITE),
                _planned("e", _FileAction.REMOVE, detail="renamed"),
                _planned("f", _FileAction.CONFLICT, detail="edited"),
            ],
        )
        assert _init.render_plan(plan).splitlines()[-1] == (
            "  2 create · 1 section · 1 overwrite · 1 remove · 1 conflict"
        )

    def test_an_empty_plan_still_closes_with_zeroes(self, tmp_path):
        plan = _synthetic_plan(tmp_path, [])
        assert _init.render_plan(plan).splitlines()[-1] == (
            "  0 create · 0 section · 0 overwrite · 0 remove · 0 conflict"
        )

    def test_unreported_rows_are_not_counted(self, tmp_path):
        plan = _synthetic_plan(
            tmp_path, [_planned("a", _FileAction.CREATE, reported=False)]
        )
        assert _init.render_plan(plan).splitlines()[-1].strip().startswith("0 create")


class TestRecordedAnswerLookup:
    """Which of the four persisted answers a project has already settled.

    The CLI must know so it can stop asking (FR-10) — but it never reads a
    config key itself (ADR-021 constraint 2), so the lookup lives here beside
    `plan_init`, the key's only reader.
    """

    def test_a_project_with_no_config_has_recorded_nothing(self, tmp_path):
        assert _init.answered_prompts(tmp_path) == frozenset()

    def test_each_written_key_reports_its_prompt(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _init.run_init()
        from lore.initplan import QUESTIONS

        assert _init.answered_prompts(tmp_path) == frozenset(
            {
                _init.PROMPT_AGENTS,
                _init.PROMPT_SKILLS_GITIGNORE,
                *QUESTIONS,
            }
        )

    def test_a_key_at_its_default_value_still_counts_as_recorded(self, tmp_path):
        target = tmp_path / ".lore" / "config.toml"
        target.parent.mkdir(parents=True)
        target.write_text('init-quests = true\n', encoding="utf-8")
        assert "quests" in _init.answered_prompts(tmp_path)

    def test_a_retired_key_answers_nothing(self, tmp_path):
        target = tmp_path / ".lore" / "config.toml"
        target.parent.mkdir(parents=True)
        target.write_text('init-access-mode = "native"\n', encoding="utf-8")
        assert _init.answered_prompts(tmp_path) == frozenset()

    def test_an_unreadable_config_records_nothing_rather_than_raising(self, tmp_path):
        target = tmp_path / ".lore" / "config.toml"
        target.parent.mkdir(parents=True)
        target.write_text("this is not = = toml\n", encoding="utf-8")
        assert _init.answered_prompts(tmp_path) == frozenset()


# ---------------------------------------------------------------------------
# `_replace_leading_comment_block` — the regenerated config header
# (interactive-init-us-020, FR-36)
# ---------------------------------------------------------------------------


HEADER = "# generated line one\n# generated line two\n"


class TestReplaceLeadingCommentBlock:
    """conceptual-workflows-lore-init — config header regeneration.

    Only the leading contiguous run of `#` lines moves. Everything from the
    first non-comment line onward is left byte-identical, which is what lets a
    project's own values, ordering, blank lines and inline comments survive a
    header refresh.
    """

    def _write(self, tmp_path, text):
        target = tmp_path / "config.toml"
        target.write_text(text, encoding="utf-8")
        return target

    def test_touches_only_the_leading_run(self, tmp_path):
        body = (
            'show-glossary-on-codex-commands = false\n'
            "\n"
            'health-report-retention = "all"   # keep them all\n'
            "my-team-setting = 3\n"
        )
        target = self._write(tmp_path, "# old one\n# old two\n" + body)

        _init._replace_leading_comment_block(target, HEADER)

        assert target.read_text(encoding="utf-8") == HEADER + body

    def test_prepends_when_the_file_has_no_leading_comments(self, tmp_path):
        body = "show-glossary-on-codex-commands = true\n"
        target = self._write(tmp_path, body)

        _init._replace_leading_comment_block(target, HEADER)

        assert target.read_text(encoding="utf-8") == HEADER + body

    def test_a_comment_after_a_setting_line_is_untouched(self, tmp_path):
        body = (
            "show-glossary-on-codex-commands = true\n"
            "# a note the project wrote about the next key\n"
            'health-report-retention = "all"\n'
        )
        target = self._write(tmp_path, body)

        _init._replace_leading_comment_block(target, HEADER)

        assert target.read_text(encoding="utf-8") == HEADER + body

    def test_a_blank_line_ends_the_leading_run(self, tmp_path):
        body = "\n# a second block the project owns\nkey = 1\n"
        target = self._write(tmp_path, "# old one\n" + body)

        _init._replace_leading_comment_block(target, HEADER)

        assert target.read_text(encoding="utf-8") == HEADER + body

    def test_an_empty_file_yields_header_only(self, tmp_path):
        target = self._write(tmp_path, "")

        _init._replace_leading_comment_block(target, HEADER)

        assert target.read_text(encoding="utf-8") == HEADER

    def test_an_all_comment_file_yields_header_only(self, tmp_path):
        target = self._write(tmp_path, "# old one\n# old two\n")

        _init._replace_leading_comment_block(target, HEADER)

        assert target.read_text(encoding="utf-8") == HEADER

    def test_a_final_line_with_no_newline_is_not_glued_to_the_header(self, tmp_path):
        target = self._write(tmp_path, "# old\nkey = 1")

        _init._replace_leading_comment_block(target, HEADER)

        assert target.read_text(encoding="utf-8") == HEADER + "key = 1"

    def test_is_idempotent(self, tmp_path):
        target = self._write(tmp_path, "# old\nkey = 1\n")

        _init._replace_leading_comment_block(target, HEADER)
        once = target.read_text(encoding="utf-8")
        _init._replace_leading_comment_block(target, HEADER)

        assert target.read_text(encoding="utf-8") == once


def test_config_skeleton_constant_is_gone_from_init():
    """conceptual-workflows-lore-init — config header regeneration.

    The header is generated from `lore.config`'s own registry, so a
    hand-written copy of it in `init.py` is the drift this story removes.
    """
    assert not hasattr(_init, "_CONFIG_SKELETON")


def test_seeded_config_carries_the_generated_header_and_every_default(tmp_path):
    """conceptual-workflows-lore-init — config header regeneration."""
    import tomllib

    from lore.config import _FROM_TOML, render_known_keys_header

    _init._seed_glossary(tmp_path)

    text = (tmp_path / ".lore" / "config.toml").read_text(encoding="utf-8")
    assert text.startswith(render_known_keys_header())
    assert set(tomllib.loads(text)) == set(_FROM_TOML)


def test_seeding_an_existing_config_refreshes_only_its_header(tmp_path):
    """conceptual-workflows-lore-init — config header regeneration."""
    from lore.config import render_known_keys_header

    target = tmp_path / ".lore" / "config.toml"
    target.parent.mkdir(parents=True)
    body = "show-glossary-on-codex-commands = false\nmy-team-setting = 3\n"
    target.write_text("# a header from an older release\n" + body, encoding="utf-8")

    messages = _init._seed_glossary(tmp_path)

    assert target.read_text(encoding="utf-8") == render_known_keys_header() + body
    assert not any("Created config.toml" in m for m in messages)


# ---------------------------------------------------------------------------
# `_format_db_status` — the real schema version (interactive-init-us-022, FR-38)
# ---------------------------------------------------------------------------


class TestFormatDbStatus:
    """conceptual-workflows-lore-init — database creation.

    The created-database line interpolates `lore.db.SCHEMA_VERSION`, so the
    next migration updates the message for free. Every assertion builds its
    expectation from the constant rather than from a literal, for the same
    reason.
    """

    def test_created_uses_the_schema_version_constant(self):
        from lore import db

        assert _init._format_db_status("created") == [
            f"  Created lore.db (schema version {db.SCHEMA_VERSION})"
        ]

    def test_created_carries_no_stale_version_digit(self):
        from lore import db

        line = _init._format_db_status("created")[0]
        digits = {token for token in _re.findall(r"\d+", line)}
        assert digits == {str(db.SCHEMA_VERSION)}, line

    def test_existing_and_reinitialized_are_unchanged(self):
        assert _init._format_db_status("existing") == [
            "  Skipped lore.db (already exists)"
        ]
        assert _init._format_db_status("reinitialized") == [
            "  Warning: Existing database appears corrupted. Reinitialized lore.db"
        ]

    def test_an_unknown_status_still_returns_an_empty_list(self):
        assert _init._format_db_status("no-such-status") == []

    def test_schema_version_is_imported_from_lore_db(self):
        """One constant, one source — `init` reads `db`'s, never its own copy."""
        from lore import db

        assert _init.SCHEMA_VERSION is db.SCHEMA_VERSION


class TestTheRecordedSetIsWhatAuthorisesDestruction:
    """`init._recorded_entries` — which of three records may claim a path.

    The set this returns decides what `lore init` overwrites and unlinks, so
    every grade in it has to be a statement about *this* project. Two are: an
    install manifest is the list of what this project's own runs wrote, and a
    historical-hash hit is a statement about the bytes on disk right now. The
    third is a guess — the historical table has a row at this name, and
    something else under the same root proves Lore installed *somewhere* in it
    — and a guess is evidence about the tree rather than the path.

    A project holding a manifest needs no guess: it has the answer. Merging one
    in anyway let the packaged table claim paths the manifest deliberately
    omits, which is every path a run met and declined to take.
    """

    RETIRED = ".lore/skills/new-rite/SKILL.md"
    CURRENT = ".lore/skills/inquest/SKILL.md"

    def _project(self, tmp_path, monkeypatch):
        from lore import manifest as manifest_mod
        from lore import reconcile as reconcile_mod

        for relative, content in (
            (self.RETIRED, b"our own team process\n"),
            (self.CURRENT, b"as shipped\n"),
        ):
            target = tmp_path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

        table = {
            self.RETIRED: ["sha256:whatever-lore-shipped"],
            self.CURRENT: [manifest_mod.file_digest(tmp_path / self.CURRENT)],
        }
        payload = {"legacy_hashes_version": 1, "files": table}
        monkeypatch.setattr(reconcile_mod, "_read_legacy_payload", lambda: payload)
        reconcile_mod.load_legacy_hashes.cache_clear()
        return tmp_path

    def _record_manifest(self, project_root, paths):
        import json

        from lore import manifest as manifest_mod

        payload = {
            "manifest_version": manifest_mod.MANIFEST_VERSION,
            "lore_version": "0.10.0",
            "catalogue_version": 1,
            "generated_at": "2026-01-01T00:00:00Z",
            "answers": {},
            "targets": {},
            "files": [
                {
                    "path": path,
                    "kind": "owned",
                    "source": "skill:inquest",
                    "hash": manifest_mod.file_digest(project_root / path),
                }
                for path in paths
            ],
        }
        target = project_root / ".lore" / ".install-manifest.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _entries(self, project_root):
        from lore import init as init_mod
        from lore import reconcile as reconcile_mod

        try:
            return init_mod._recorded_entries(project_root)
        finally:
            reconcile_mod.load_legacy_hashes.cache_clear()

    def test_a_manifest_project_admits_no_guess_at_a_path_it_omits(
        self, tmp_path, monkeypatch
    ):
        project = self._project(tmp_path, monkeypatch)
        self._record_manifest(project, [self.CURRENT])

        recorded, _ = self._entries(project)

        assert self.RETIRED not in recorded

    def test_a_manifest_project_claims_no_path_it_omits(self, tmp_path, monkeypatch):
        project = self._project(tmp_path, monkeypatch)
        self._record_manifest(project, [self.CURRENT])

        _, shipped = self._entries(project)

        assert self.RETIRED not in shipped

    def test_the_manifest_itself_is_still_the_record(self, tmp_path, monkeypatch):
        project = self._project(tmp_path, monkeypatch)
        self._record_manifest(project, [self.CURRENT])

        recorded, _ = self._entries(project)

        assert self.CURRENT in recorded

    def test_a_hash_hit_outside_the_manifest_is_still_admitted(
        self, tmp_path, monkeypatch
    ):
        """A rollback reinstalls files no later manifest mentions, and their
        bytes are Lore's own — which the disk agrees with right now."""
        project = self._project(tmp_path, monkeypatch)
        self._record_manifest(project, [])

        recorded, _ = self._entries(project)

        assert self.CURRENT in recorded

    def test_a_project_with_no_manifest_still_gets_the_guess(
        self, tmp_path, monkeypatch
    ):
        """The fallback exists for projects that predate the manifest, and
        removing an edited retired skill there is the whole reason it does."""
        project = self._project(tmp_path, monkeypatch)

        recorded, shipped = self._entries(project)

        assert self.RETIRED in recorded
        assert self.RETIRED in shipped


# ---------------------------------------------------------------------------
# A seeded tree this release stopped shipping is removed by an explicit list.
# Workflow: conceptual-workflows-init-reconcile
#
# Deleting the row from SEEDED_TREES is not enough: `_prune_seeded_tree` only
# walks trees still in that tuple, so the seeded files would stay on disk in
# every upgraded project forever.
# ---------------------------------------------------------------------------


def _seed_retired_knights(project_root: _Path) -> _Path:
    target = project_root / ".lore" / "knights" / "default"
    (target / "feature-implementation").mkdir(parents=True)
    (target / "changelog-scribe.md").write_text("---\nid: x\n---\nbody\n")
    (target / "feature-implementation" / "architect.md").write_text(
        "---\nid: y\n---\nbody\n"
    )
    return target


def test_knights_is_no_longer_a_seed_tree():
    assert all(spec.package != "knights" for spec in _init.SEEDED_TREES)


def test_retired_seed_trees_names_the_knights_default_tree():
    assert [tree.relative for tree in _init.RETIRED_SEED_TREES] == ["knights/default"]


def test_seeded_paths_names_no_knight_path():
    assert not any("knights" in path for path in _init.seeded_paths(_Profile()))


def test_the_retired_tree_walk_unlinks_every_file_and_reports_each(tmp_path):
    _seed_retired_knights(tmp_path)

    messages = _init._remove_retired_seed_trees(tmp_path)

    assert messages == [
        "  Removed knights/default/changelog-scribe.md — no longer shipped",
        "  Removed knights/default/feature-implementation/architect.md"
        " — no longer shipped",
    ]


def test_the_retired_tree_walk_prunes_the_emptied_directories(tmp_path):
    _seed_retired_knights(tmp_path)

    _init._remove_retired_seed_trees(tmp_path)

    assert not (tmp_path / ".lore" / "knights" / "default").exists()


def test_the_retired_tree_walk_leaves_a_symlink_alone(tmp_path):
    target = _seed_retired_knights(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("mine\n")
    (target / "linked.md").symlink_to(outside)

    _init._remove_retired_seed_trees(tmp_path)

    assert (target / "linked.md").is_symlink()
    assert outside.read_text() == "mine\n"


def test_the_retired_tree_walk_survives_an_unlinkable_file(tmp_path, monkeypatch):
    _seed_retired_knights(tmp_path)
    real_unlink = _Path.unlink

    def refuse(self, *args, **kwargs):
        if self.name == "changelog-scribe.md":
            raise PermissionError("denied")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(_Path, "unlink", refuse)

    messages = _init._remove_retired_seed_trees(tmp_path)

    assert messages == [
        "  Removed knights/default/feature-implementation/architect.md"
        " — no longer shipped",
    ]
    assert (tmp_path / ".lore" / "knights" / "default" / "changelog-scribe.md").exists()


def test_a_project_with_no_knights_tree_produces_no_messages(tmp_path):
    (tmp_path / ".lore").mkdir()

    assert _init._remove_retired_seed_trees(tmp_path) == []


def test_an_authored_knight_outside_default_is_named_and_kept(tmp_path):
    _seed_retired_knights(tmp_path)
    authored = tmp_path / ".lore" / "knights" / "my-reviewer.md"
    authored.write_text("mine\n")

    messages = _init._remove_retired_seed_trees(tmp_path)

    assert authored.read_text() == "mine\n"
    assert messages[-1] == (
        "  Knights outside default/ are no longer read by Lore: "
        ".lore/knights/my-reviewer.md"
    )


def test_several_authored_knights_are_named_on_one_line(tmp_path):
    knights = tmp_path / ".lore" / "knights"
    (knights / "team").mkdir(parents=True)
    (knights / "my-reviewer.md").write_text("mine\n")
    (knights / "team" / "sre.md").write_text("mine\n")

    messages = _init._remove_retired_seed_trees(tmp_path)

    assert messages == [
        "  Knights outside default/ are no longer read by Lore: "
        ".lore/knights/my-reviewer.md, .lore/knights/team/sre.md"
    ]


def test_the_authored_notice_is_absent_when_nothing_was_authored(tmp_path):
    _seed_retired_knights(tmp_path)

    messages = _init._remove_retired_seed_trees(tmp_path)

    assert all("no longer read by Lore" not in message for message in messages)


def test_seeding_a_lore_directory_removes_the_retired_tree(tmp_path):
    _seed_retired_knights(tmp_path)
    (tmp_path / ".lore" / "codex").mkdir(parents=True, exist_ok=True)

    messages = _init._seed_lore_directory(tmp_path, _Profile())

    assert any("Removed knights/default/" in message for message in messages)
    assert not (tmp_path / ".lore" / "knights" / "default").exists()


# ===========================================================================
# Feature answers: resolution, migration, persistence
# Spec: adaptive-init-spec, Parts 2.8, 2.8.1, 2.9 and 5 "Lane B tests".
# Anchor: conceptual-workflows-lore-init.
#
# Nothing below reads a word of a shipped block or seed: assertions are about
# the resolved Profile, the planned paths and the recorded keys.
# ===========================================================================

def _reported_rows(plan) -> list:
    """The reconciled rows a run would act on (the seeded files are always refreshed)."""
    return [entry for entry in plan.files if entry.reported]


def _apply(root: _Path, **answers):
    return _init.apply_init(_init.plan_init(project_root=root, **answers))


def _manifest_payload(root: _Path) -> dict:
    return _json.loads((root / ".lore" / ".install-manifest.json").read_text(encoding="utf-8"))


def _write_manifest_payload(root: _Path, payload: dict) -> None:
    (root / ".lore" / ".install-manifest.json").write_text(
        _json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


class TestResolveProfile:
    """Precedence: explicit keyword > deprecated alias > recorded key > base layer."""

    def test_nothing_recorded_anywhere_is_the_headless_profile(self, tmp_path):
        plan = _init.plan_init(project_root=tmp_path)
        assert plan.answers.profile == _Profile()
        assert plan.notices == ()

    def test_a_recorded_key_beats_the_base_layer(self, tmp_path):
        _write_config_toml(tmp_path, 'init-route = "harness"\n')
        profile = _init.plan_init(project_root=tmp_path).answers.profile
        assert profile.route is _Route.HARNESS

    def test_a_recorded_opt_in_is_read_as_a_bool(self, tmp_path):
        _write_config_toml(tmp_path, "init-memory-index = false\n")
        assert _init.plan_init(project_root=tmp_path).answers.profile.memory_index is False

    def test_an_alias_beats_a_recorded_key(self, tmp_path):
        _write_config_toml(tmp_path, 'init-route = "harness"\n')
        profile = _init.plan_init(project_root=tmp_path, access_mode="cli").answers.profile
        assert profile.route is _Route.CLI

    def test_an_explicit_keyword_beats_an_alias(self, tmp_path):
        plan = _init.plan_init(project_root=tmp_path, access_mode="cli", route="harness")
        assert plan.answers.profile.route is _Route.HARNESS

    def test_an_explicit_keyword_beats_a_recorded_key(self, tmp_path):
        _write_config_toml(tmp_path, "init-quests = true\n")
        profile = _init.plan_init(project_root=tmp_path, quests=False).answers.profile
        assert profile.quests is False

    def test_a_route_keyword_takes_a_string_or_a_route(self, tmp_path):
        as_text = _init.plan_init(project_root=tmp_path, route="harness").answers.profile
        as_enum = _init.plan_init(project_root=tmp_path, route=_Route.HARNESS).answers.profile
        assert as_text == as_enum
        assert as_text.route is _Route.HARNESS

    def test_every_fixture_profile_round_trips_through_the_keywords(self, tmp_path):
        for name, profile in _FIXTURE_PROFILES.items():
            resolved = _init.plan_init(
                project_root=tmp_path, **profile.as_answers()
            ).answers.profile
            assert resolved == profile.normalized(), name

    def test_a_skills_alias_yields_the_complete_legacy_profile(self, tmp_path):
        plan = _init.plan_init(
            project_root=tmp_path, access_mode="cli", skill_families=["memory", "workflow"]
        )
        assert plan.answers.profile == _profile_from_legacy("cli", ("memory", "workflow"))

    def test_a_skills_alias_alone_keeps_the_recorded_route(self, tmp_path):
        _write_config_toml(tmp_path, 'init-route = "harness"\n')
        plan = _init.plan_init(project_root=tmp_path, skill_families=["memory"])
        assert plan.answers.profile.route is _Route.HARNESS

    def test_an_alias_is_named_in_the_plans_notices(self, tmp_path):
        plan = _init.plan_init(project_root=tmp_path, access_mode="native")
        assert plan.notices
        assert "--access" in plan.notices[0]

    def test_an_unknown_route_token_is_rejected_with_the_accepted_set(self, tmp_path):
        with pytest.raises(ValueError, match="Unknown route: 'native'. Accepted tokens: harness, cli"):
            _init.plan_init(project_root=tmp_path, route="native")

    @pytest.mark.parametrize("bad", [True, 3, ["cli"], "off"])
    def test_a_route_keyword_must_be_a_token(self, tmp_path, bad):
        with pytest.raises(ValueError, match="Unknown route"):
            _init.plan_init(project_root=tmp_path, route=bad)

    @pytest.mark.parametrize("bad", ["yes", "true", 1, 0])
    def test_an_opt_in_keyword_must_be_a_bool(self, tmp_path, bad):
        with pytest.raises(ValueError, match="memory_search"):
            _init.plan_init(project_root=tmp_path, memory_search=bad)

    def test_the_alias_tokens_are_still_checked(self, tmp_path):
        with pytest.raises(ValueError, match="Unknown access mode"):
            _init.plan_init(project_root=tmp_path, access_mode="both")
        with pytest.raises(ValueError, match="Unknown skill family"):
            _init.plan_init(project_root=tmp_path, skill_families=["nope"])

    def test_a_bad_answer_is_refused_before_any_io(self, tmp_path):
        before = _tree(tmp_path)
        with pytest.raises(ValueError):
            _init.plan_init(project_root=tmp_path, route="nope")
        assert _tree(tmp_path) == before


class TestPartialConfigUsesDefaults:
    def test_one_recorded_new_key_does_not_trigger_a_migration(self, tmp_path):
        _write_config_toml(
            tmp_path, 'init-route = "cli"\ninit-skill-families = ["memory"]\n'
        )
        plan = _init.plan_init(project_root=tmp_path)
        assert plan.answers.profile == _Profile()
        assert plan.notices == ()

    def test_a_partial_config_fills_its_gaps_with_the_headless_defaults(self, tmp_path):
        _write_config_toml(tmp_path, "init-watchers = false\n")
        profile = _init.plan_init(project_root=tmp_path).answers.profile
        assert profile.route is _Route.CLI
        assert profile.memory and profile.quests
        assert not profile.feature_on(_Feature.WATCHERS)


class TestInterimMigration:
    """The fifteen keys the unreleased 0.14.0 build wrote map onto the new answers."""

    def _plan(self, tmp_path, text):
        _write_config_toml(tmp_path, text)
        return _init.plan_init(project_root=tmp_path)

    def test_memory_is_on_when_either_route_was_not_off(self, tmp_path):
        plan = self._plan(tmp_path, 'init-memory-read = "harness"\ninit-memory-write = "off"\n')
        assert plan.answers.profile.memory
        assert any("Migrated" in notice for notice in plan.notices)

    def test_memory_is_off_when_both_routes_were_off(self, tmp_path):
        plan = self._plan(tmp_path, 'init-memory-read = "off"\ninit-memory-write = "off"\n')
        profile = plan.answers.profile
        assert not profile.memory
        assert not (profile.memory_search or profile.memory_index or profile.memory_graph)

    def test_search_follows_a_cli_read_route(self, tmp_path):
        assert self._plan(tmp_path, 'init-memory-read = "cli"\n').answers.profile.memory_search

    def test_index_graph_and_quests_keep_their_values(self, tmp_path):
        profile = self._plan(
            tmp_path, "init-memory-index = false\ninit-memory-graph = false\ninit-quests = false\n"
            'init-memory-read = "cli"\n'
        ).answers.profile
        assert not (profile.memory_index or profile.memory_graph or profile.quests)

    def test_the_route_is_cli_when_any_remaining_route_was_cli(self, tmp_path):
        harness = "".join(
            f'init-{f}-{a} = "harness"\n'
            for f in ("memory", "doctrines", "artifacts", "watchers")
            for a in ("read", "write")
        )
        assert self._plan(tmp_path, harness).answers.profile.route is _Route.HARNESS
        profile = self._plan(tmp_path, harness + 'init-doctrines-write = "cli"\n').answers.profile
        assert profile.route is _Route.CLI

    def test_the_new_keys_are_recorded_after_the_first_run_and_it_migrates_once(self, tmp_path):
        from lore.config import recorded_keys

        _write_config_toml(tmp_path, 'init-memory-read = "cli"\ninit-watchers-write = "off"\n')
        first = _init.plan_init(project_root=tmp_path)
        _init.apply_init(first)
        assert {"init-route", "init-memory", "init-watchers"} <= recorded_keys(tmp_path)
        second = _init.plan_init(project_root=tmp_path)
        assert second.answers.profile == first.answers.profile
        assert second.notices == ()
        text = (tmp_path / ".lore" / "config.toml").read_text(encoding="utf-8")
        assert 'init-memory-read = "cli"' in text

    def test_the_notice_names_the_retired_keys(self, tmp_path):
        plan = self._plan(tmp_path, 'init-memory-read = "cli"\n')
        assert "init-memory-read" in plan.notices[0]


class TestMigrationSources:
    """Old keys, then the old manifest answers, then the recorded skills, then nothing."""

    def test_the_retired_config_keys_are_migrated_and_announced(self, tmp_path):
        _write_config_toml(
            tmp_path,
            'init-access-mode = "cli"\ninit-skill-families = ["memory", "machinery"]\n',
        )
        plan = _init.plan_init(project_root=tmp_path)
        assert plan.answers.profile == _profile_from_legacy("cli", ("machinery", "memory"))
        assert any("Migrated" in notice for notice in plan.notices)

    def test_a_single_retired_key_takes_the_other_from_the_defaults(self, tmp_path):
        _write_config_toml(tmp_path, 'init-access-mode = "cli"\n')
        plan = _init.plan_init(project_root=tmp_path)
        assert plan.answers.profile == _profile_from_legacy(
            "cli", ("machinery", "memory", "workflow")
        )

    def test_the_old_manifest_answers_stand_in_when_no_key_is_recorded(self, tmp_path):
        _apply(tmp_path, agents=["none"])
        (tmp_path / ".lore" / "config.toml").write_text("", encoding="utf-8")
        payload = _manifest_payload(tmp_path)
        payload["answers"] = {
            "agents": [],
            "access_mode": "cli",
            "skill_families": ["workflow"],
            "skills_gitignore": "lore-only",
        }
        _write_manifest_payload(tmp_path, payload)
        plan = _init.plan_init(project_root=tmp_path)
        assert plan.answers.profile == _profile_from_legacy("cli", ("workflow",))
        assert any("Migrated" in notice for notice in plan.notices)

    def test_the_recorded_skills_stand_in_when_the_manifest_has_no_answers(self, tmp_path):
        _apply(tmp_path, agents=["none"], skill_families=["memory"])
        (tmp_path / ".lore" / "config.toml").write_text("", encoding="utf-8")
        payload = _manifest_payload(tmp_path)
        payload["answers"] = {}
        # What an earlier release recorded for a memory-only install: those two
        # skills, and nothing the capabilities of a newer one add.
        older = {"skill:retrieve-memory", "skill:store-memory"}
        payload["files"] = [
            row
            for row in payload["files"]
            if not row["source"].startswith("skill:") or row["source"] in older
        ]
        _write_manifest_payload(tmp_path, payload)
        for skill_dir in (tmp_path / ".lore" / "skills").iterdir():
            if skill_dir.is_dir() and f"skill:{skill_dir.name}" not in older:
                _shutil.rmtree(skill_dir)
        plan = _init.plan_init(project_root=tmp_path)
        assert plan.answers.profile == _profile_from_legacy("native", ("memory",))

    def test_a_skill_kept_under_a_retired_id_counts_as_its_successors_family(self, tmp_path):
        from lore import skills as skills_mod
        from lore.initplan import PlannedFile

        retired = next(
            old
            for old in skills_mod.load_catalogue()["retired"]
            if skills_mod.retirement_for(old).into == "retrieve-memory"
        )
        path = f".lore/skills/{retired}/SKILL.md"
        (tmp_path / path).parent.mkdir(parents=True)
        (tmp_path / path).write_text("old\n", encoding="utf-8")
        _manifest.write(
            tmp_path,
            answers={},
            targets={},
            files=[
                PlannedFile(
                    path=path,
                    action=_FileAction.CREATE,
                    kind="owned",
                    source=f"skill:{retired}",
                    digest=_manifest.bytes_digest(b"old\n"),
                    detail=None,
                )
            ],
            lore_version="0.0.1",
            catalogue_version=1,
        )
        plan = _init.plan_init(project_root=tmp_path)
        assert plan.answers.profile == _profile_from_legacy("native", ("memory",))

    def test_a_migrated_install_is_stable_after_one_apply(self, tmp_path):
        _write_config_toml(tmp_path, 'init-access-mode = "cli"\ninit-skill-families = ["memory"]\n')
        first = _init.plan_init(project_root=tmp_path)
        _init.apply_init(first)
        second = _init.plan_init(project_root=tmp_path)
        assert second.answers.profile == first.answers.profile
        assert second.notices == ()
        assert _reported_rows(second) == []

    def test_a_dry_plan_writes_nothing_while_migrating(self, tmp_path):
        _write_config_toml(tmp_path, 'init-access-mode = "cli"\n')
        before = _tree(tmp_path)
        _init.plan_init(project_root=tmp_path)
        assert _tree(tmp_path) == before


class TestExplicitInapplicableAnswerRaises:
    def test_a_memory_opt_in_while_the_call_switches_memory_off(self, tmp_path):
        with pytest.raises(ValueError, match=r"memory_graph needs Memory on"):
            _init.plan_init(project_root=tmp_path, memory=False, memory_graph=True)

    def test_a_memory_opt_in_while_the_config_switches_memory_off(self, tmp_path):
        _write_config_toml(tmp_path, "init-memory = false\n")
        with pytest.raises(ValueError, match="memory_index needs Memory on"):
            _init.plan_init(project_root=tmp_path, memory_index=True)

    def test_quests_is_always_legal(self, tmp_path):
        plan = _init.plan_init(project_root=tmp_path, memory=False, quests=True)
        assert plan.answers.profile.quests is True

    def test_an_explicit_false_is_never_an_error(self, tmp_path):
        plan = _init.plan_init(project_root=tmp_path, memory=False, memory_search=False)
        assert plan.answers.profile.memory_search is False


class TestRecordedInapplicableAnswerIsDropped:
    def test_a_recorded_memory_opt_in_of_an_off_memory_is_dropped_silently(self, tmp_path):
        _write_config_toml(tmp_path, "init-memory = false\ninit-memory-graph = true\n")
        profile = _init.plan_init(project_root=tmp_path).answers.profile
        assert profile.memory_graph is False


class TestReconfigureBase:
    def _answers(self, **overrides):
        base = {"route": "cli", "memory": True, "quests": True, "watchers": True}
        base.update(overrides)
        return base

    def test_reconfigure_ignores_the_recorded_profile(self, tmp_path):
        _write_config_toml(tmp_path, 'init-route = "harness"\ninit-quests = false\n')
        profile = _init.plan_init(
            project_root=tmp_path,
            reconfigure=True,
            agents=[],
            skills_gitignore="none",
            **self._answers(),
        ).answers.profile
        assert profile.route is _Route.CLI
        assert profile.quests is True

    def test_reconfigure_ignores_the_retired_keys_too(self, tmp_path):
        _write_config_toml(tmp_path, 'init-skill-families = ["memory"]\n')
        plan = _init.plan_init(
            project_root=tmp_path,
            reconfigure=True,
            agents=[],
            skills_gitignore="none",
            **self._answers(),
        )
        assert plan.notices == ()
        assert plan.answers.profile.feature_on(_Feature.WATCHERS)

    def test_the_alias_pair_satisfies_reconfigure(self, tmp_path):
        plan = _init.plan_init(
            project_root=tmp_path,
            reconfigure=True,
            agents=[],
            skills_gitignore="none",
            access_mode="cli",
            skill_families=["memory"],
        )
        assert plan.answers.profile == _profile_from_legacy("cli", ("memory",))

    def test_reconfigure_names_what_it_is_missing(self, tmp_path):
        with pytest.raises(ValueError, match="reconfigure") as excinfo:
            _init.plan_init(project_root=tmp_path, reconfigure=True, agents=[])
        text = str(excinfo.value)
        assert "skills_gitignore" in text
        assert "route" in text


class TestMissingRecordedAnswers:
    def _all(self, **overrides):
        given = {
            "agents": [],
            "skills_gitignore": "none",
            "route": "cli",
            "memory": True,
            "quests": True,
            "watchers": True,
        }
        given.update(overrides)
        return given

    def test_everything_supplied_leaves_nothing_missing(self):
        assert _init.missing_recorded_answers(self._all()) == ()

    def test_nothing_supplied_names_every_recorded_question(self):
        missing = _init.missing_recorded_answers({})
        assert set(missing) == {
            "agents", "skills_gitignore", "route", "memory", "quests", "watchers",
        }

    def test_the_alias_pair_counts_as_every_profile_question(self):
        missing = _init.missing_recorded_answers(
            {
                "agents": [],
                "skills_gitignore": "none",
                "access_mode": "cli",
                "skill_families": ["memory"],
            }
        )
        assert missing == ()

    def test_one_alias_alone_does_not(self):
        missing = _init.missing_recorded_answers(
            {"agents": [], "skills_gitignore": "none", "access_mode": "cli"}
        )
        assert set(missing) == {"route", "memory", "quests", "watchers"}

    def test_memory_opt_ins_are_never_required(self):
        assert not any(
            name.startswith("memory_") for name in _init.missing_recorded_answers({})
        )

    def test_every_name_has_a_key_and_a_flag(self):
        for field in _init.missing_recorded_answers({}):
            key, flag = _init.RECORDED_ANSWER_FLAGS[field]
            assert key.startswith("init-")
            assert flag.startswith("--")


class TestPersistAnswersWritesTheFeatureKeys:
    def test_every_profile_key_and_the_two_old_answers_are_written(self, tmp_path):
        from lore.config import recorded_keys
        from lore.initplan import QUESTIONS, question_key

        _apply(tmp_path)
        expected = {"init-agents", "init-skills-gitignore", *(question_key(q) for q in QUESTIONS)}
        assert expected <= recorded_keys(tmp_path)

    def test_a_second_apply_leaves_the_file_byte_identical(self, tmp_path):
        _apply(tmp_path)
        target = tmp_path / ".lore" / "config.toml"
        first = target.read_bytes()
        _apply(tmp_path)
        assert target.read_bytes() == first

    def test_the_recorded_profile_is_what_was_applied(self, tmp_path):
        _apply(tmp_path, **_FIXTURE_PROFILES["HARNESS_MEMORY"].as_answers())
        again = _init.plan_init(project_root=tmp_path)
        assert again.answers.profile == _FIXTURE_PROFILES["HARNESS_MEMORY"]

    def test_the_retired_lines_and_the_projects_own_lines_are_left_alone(self, tmp_path):
        _write_config_toml(
            tmp_path,
            "# my notes\n"
            'init-access-mode = "cli"   # old\n'
            'init-skill-families = ["memory"]\n'
            "show-glossary-on-codex-commands = false\n",
        )
        _apply(tmp_path)
        text = (tmp_path / ".lore" / "config.toml").read_text(encoding="utf-8")
        assert 'init-access-mode = "cli"   # old\n' in text
        assert 'init-skill-families = ["memory"]\n' in text
        assert "show-glossary-on-codex-commands = false\n" in text

    def test_a_present_key_is_rewritten_in_place_and_not_duplicated(self, tmp_path):
        _write_config_toml(tmp_path, 'init-quests = true\ninit-route = "cli"\n')
        _apply(tmp_path, quests=False)
        lines = (tmp_path / ".lore" / "config.toml").read_text(encoding="utf-8").splitlines()
        assert lines.count("init-quests = false") == 1
        assert sum(line.startswith("init-quests") for line in lines) == 1
        assert lines.index("init-quests = false") < lines.index('init-route = "cli"')


class TestBuildDesiredBareCoreRendersTheCore:
    def _plan(self, root):
        return _init.plan_init(project_root=root, agents=["claude"], **_ALL_OFF.as_answers())

    def test_the_core_text_and_the_core_skills_are_desired(self, tmp_path):
        plan = self._plan(tmp_path)
        desired = _init.build_desired(
            project_root=tmp_path, targets=plan.targets, answers=plan.answers
        )
        assert ".lore/LORE-AGENT.md" in desired
        assert "CLAUDE.md" in desired
        skills = {p.split("/")[2] for p in desired if p.startswith(".claude/skills/") and p.endswith("SKILL.md")}
        assert skills == {"update-doctrine", "update-artifact", "run-doctrine"}

    def test_turning_the_optional_features_off_removes_their_skills(self, tmp_path):
        _apply(tmp_path, agents=["claude"])
        plan = self._plan(tmp_path)
        removed = {e.path for e in plan.files if e.action is _FileAction.REMOVE}
        assert ".claude/skills/store-memory/SKILL.md" in removed
        assert ".claude/skills/start-quest/SKILL.md" in removed
        assert ".lore/LORE-AGENT.md" not in removed

    def test_the_agent_file_the_user_owns_keeps_their_text(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("mine\n", encoding="utf-8")
        _apply(tmp_path, agents=["claude"])
        _init.apply_init(self._plan(tmp_path))
        text = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert text.startswith("mine")


class TestSkillsGitignorePromptNeedsInstalledSkills:
    def test_a_project_that_installs_skills_is_asked(self, tmp_path):
        plan = _init.plan_init(project_root=tmp_path)
        assert _init.PROMPT_SKILLS_GITIGNORE in plan.prompts_needed

    def test_the_bare_core_still_installs_skills_so_it_is_asked(self, tmp_path):
        plan = _init.plan_init(project_root=tmp_path, **_ALL_OFF.as_answers())
        assert _init.PROMPT_SKILLS_GITIGNORE in plan.prompts_needed


class TestPromptTokens:
    def test_every_profile_question_has_a_prompt_and_a_persisted_key(self):
        from lore.initplan import QUESTIONS, question_key

        for question in QUESTIONS:
            assert _init.PERSISTED_ANSWER_PROMPTS[question_key(question)] == question

    def test_the_two_old_answers_keep_their_prompts(self):
        assert _init.PERSISTED_ANSWER_PROMPTS["init-agents"] == _init.PROMPT_AGENTS
        assert (
            _init.PERSISTED_ANSWER_PROMPTS["init-skills-gitignore"]
            == _init.PROMPT_SKILLS_GITIGNORE
        )

    def test_the_two_retired_keys_have_no_prompt(self):
        assert "init-access-mode" not in _init.PERSISTED_ANSWER_PROMPTS
        assert "init-skill-families" not in _init.PERSISTED_ANSWER_PROMPTS


_SAMPLED_PROFILES = {
    **_FIXTURE_PROFILES,
    **{f"random-{index}": profile for index, profile in enumerate(_RANDOM_PROFILES[:30])},
}
_TABLE_ROW_ID = _re.compile(r"^\| `([a-z-]+)` \|")


def _desired_for(root: _Path, profile: _Profile, agents=("claude",)):
    plan = _init.plan_init(project_root=root, agents=list(agents), **profile.as_answers())
    return plan, _init.build_desired(
        project_root=root, targets=plan.targets, answers=plan.answers
    )


class TestInstructionTextIsRenderedFromBlocks:
    """`.lore/LORE-AGENT.md` and every agent block come from `skills.render_document`."""

    @pytest.mark.parametrize("name", list(_SAMPLED_PROFILES))
    def test_the_canonical_file_and_the_agent_block_stay_within_the_cap(self, tmp_path, name):
        profile = _SAMPLED_PROFILES[name]
        _, desired = _desired_for(tmp_path, profile)
        for path in (".lore/LORE-AGENT.md", "CLAUDE.md"):
            text = desired[path].content.decode("utf-8")
            assert len(text.splitlines()) <= 100, path
            assert "<!-- lore:skills-table" not in text, path
            assert "<!-- lore:block" not in text, path

    @pytest.mark.parametrize("name", list(_SAMPLED_PROFILES))
    def test_the_skills_table_lists_exactly_the_installed_skills(self, tmp_path, name):
        from lore import skills as skills_mod

        profile = _SAMPLED_PROFILES[name]
        _, desired = _desired_for(tmp_path, profile)
        installed = set(skills_mod.installed_skills(profile))
        text = desired[".lore/LORE-AGENT.md"].content.decode("utf-8")
        listed = {m.group(1) for line in text.splitlines() if (m := _TABLE_ROW_ID.match(line))}
        assert listed == installed

    @pytest.mark.parametrize("name", list(_SAMPLED_PROFILES))
    def test_the_desired_skill_files_are_those_of_the_installed_skills(self, tmp_path, name):
        from lore import skills as skills_mod

        profile = _SAMPLED_PROFILES[name]
        _, desired = _desired_for(tmp_path, profile)
        sources = {row.source for row in desired.values() if row.source.startswith("skill:")}
        assert sources == {f"skill:{skill}" for skill in skills_mod.installed_skills(profile)}

    def test_the_canonical_text_is_the_document_the_catalogue_renders(self, tmp_path, monkeypatch):
        from lore import skills as skills_mod

        calls = []
        real = skills_mod.render_document

        def spy(name, profile):
            calls.append(name)
            return real(name, profile)

        monkeypatch.setattr(skills_mod, "render_document", spy)
        _desired_for(tmp_path, _Profile())
        assert "lore-agent" in calls

    def test_a_document_no_block_survives_for_is_not_desired(self, tmp_path, monkeypatch):
        from lore import skills as skills_mod

        monkeypatch.setattr(skills_mod, "render_document", lambda name, profile: None)
        _, desired = _desired_for(tmp_path, _Profile())
        assert ".lore/LORE-AGENT.md" not in desired
        assert "CLAUDE.md" not in desired

    def test_the_core_skills_are_always_in_the_table(self, tmp_path):
        _, desired = _desired_for(tmp_path, _FIXTURE_PROFILES["HARNESS_BARE"])
        text = desired[".lore/LORE-AGENT.md"].content.decode("utf-8")
        listed = {m.group(1) for line in text.splitlines() if (m := _TABLE_ROW_ID.match(line))}
        assert listed == {"update-doctrine", "update-artifact", "run-doctrine"}

    def test_render_agent_instructions_is_never_none_for_a_valid_profile(self):
        for profile in _FIXTURE_PROFILES.values():
            assert (
                _init.render_agent_instructions(
                    profile=profile, install_roots=(_Path(".lore/skills"),)
                )
                is not None
            )

    def test_the_old_template_reader_is_gone(self):
        assert not hasattr(_init, "_read_agent_template")
        assert not hasattr(_init, "AGENT_TEMPLATE")


# ---------------------------------------------------------------------------
# Seeding follows the features that are on.
# Spec: adaptive-init-spec 2.13, with the ruling that default pipeline content is
# gated by every capability it speaks of.
#
# Gating is by tree and by file. Nothing here reads a seeded file
# (decisions-006-no-seed-content-tests): the tests ask which paths a profile
# seeds, never what a seeded path says.
# ---------------------------------------------------------------------------


def _profile(**overrides) -> _Profile:
    """The headless profile with *overrides*, normalised."""
    return _dc_replace(_Profile(), **overrides).normalized()


def _seeded(profile: _Profile) -> tuple[str, ...]:
    return _init.seeded_paths(profile)


def _under(paths: tuple[str, ...], prefix: str) -> list[str]:
    return [path for path in paths if path.startswith(prefix)]


def _without(feature: str) -> _Profile:
    return _profile(**{feature: False})


class TestSeededPathsFollowProfile:
    def test_every_run_seeds_the_database_config_and_ignore_file(self):
        for profile in (_Profile(), _ALL_OFF):
            seeded = _seeded(profile)
            for path in (".lore/lore.db", ".lore/config.toml", ".lore/.gitignore"):
                assert path in seeded

    def test_the_bare_core_seeds_doctrines_and_artifacts_but_nothing_optional(self):
        seeded = _seeded(_ALL_OFF)
        assert _under(seeded, ".lore/doctrines/default/")
        assert _under(seeded, ".lore/artifacts/default/")
        for prefix in (".lore/watchers/", ".lore/codex/", ".lore/rites/"):
            assert not _under(seeded, prefix), prefix
        assert ".lore/GETTING-STARTED.md" in seeded

    def test_every_default_doctrine_is_seeded_whatever_the_answers(self):
        everything = {
            f".lore/doctrines/default/{relative}"
            for relative, _ in _init._defaults_tree_files("doctrines")
        }
        for name, profile in _FIXTURE_PROFILES.items():
            assert everything <= set(_seeded(profile)), name

    def test_memory_seeds_the_codex_root_and_glossary_either_route(self):
        for profile in (
            _FIXTURE_PROFILES["HARNESS_MEMORY"],
            _FIXTURE_PROFILES["CLI_MEMORY"],
        ):
            seeded = _seeded(profile)
            assert ".lore/codex/codex.md" in seeded
            assert ".lore/codex/glossary.yaml" in seeded

    def test_without_memory_there_is_no_codex_root_or_glossary(self):
        seeded = _seeded(_without("memory"))
        assert ".lore/codex/codex.md" not in seeded
        assert ".lore/codex/glossary.yaml" not in seeded

    def test_the_getting_started_file_is_seeded_exactly_when_it_renders(self):
        from lore import skills as skills_mod

        for name, profile in _FIXTURE_PROFILES.items():
            rendered = skills_mod.render_document("getting-started", profile) is not None
            assert (".lore/GETTING-STARTED.md" in _seeded(profile)) is rendered, name

    def test_no_seeded_path_names_the_retired_docs_tree(self):
        assert not any("docs/" in path for path in _seeded(_Profile()))

    def test_the_full_profile_seeds_every_default_tree(self):
        seeded = _seeded(_Profile())
        for prefix in (".lore/doctrines/default/", ".lore/artifacts/default/", ".lore/watchers/default/"):
            assert _under(seeded, prefix), prefix

    def test_the_codex_skeleton_and_memory_design_documents_need_memory(self):
        owned = (
            ".lore/artifacts/default/codex/",
            ".lore/artifacts/default/rites/",
            ".lore/artifacts/default/lore-design-documents/codex-voice.md",
            ".lore/artifacts/default/lore-design-documents/glossary-design.md",
            ".lore/artifacts/default/lore-design-documents/rite-design.md",
            ".lore/artifacts/default/lore-design-documents/inquest-design.md",
        )
        with_memory = _seeded(_FIXTURE_PROFILES["HARNESS_MEMORY"])
        without = _seeded(_FIXTURE_PROFILES["HARNESS_BARE"])
        for prefix in owned:
            assert _under(with_memory, prefix), prefix
            assert not _under(without, prefix), prefix

    def test_the_mission_design_document_needs_quests(self):
        path = ".lore/artifacts/default/lore-design-documents/mission-design.md"
        assert path in _seeded(_FIXTURE_PROFILES["HARNESS_QUESTS"])
        assert path not in _seeded(_FIXTURE_PROFILES["HARNESS_BARE"])

    def test_the_core_artifacts_are_seeded_without_any_optional_feature(self):
        seeded = _seeded(_FIXTURE_PROFILES["HARNESS_BARE"])
        assert ".lore/artifacts/default/lore-design-documents/doctrine-design.md" in seeded
        assert _under(seeded, ".lore/artifacts/default/feature-implementation/")

    def test_the_route_does_not_gate_a_tree(self):
        harness = _seeded(_profile(route=_Route.HARNESS))
        cli = _seeded(_profile(route=_Route.CLI))
        assert harness == cli

    def test_memory_opt_ins_do_not_gate_a_tree(self):
        full = _seeded(_Profile())
        for capability in ("memory_graph", "memory_search", "memory_index"):
            assert _seeded(_profile(**{capability: False})) == full, capability

    def test_watchers_off_seeds_no_watcher(self):
        assert not _under(_seeded(_without("watchers")), ".lore/watchers/")

    def test_every_gate_row_parses_in_the_block_grammar(self):
        from lore import blocks as blocks_mod

        for gate in _init.SEED_GATES:
            for condition in gate.requires:
                blocks_mod.parse_condition(condition)


class TestSeedKeepPredicate:
    def test_the_changelog_doctrine_is_core_and_its_watcher_follows_watchers(self):
        for name, profile in _FIXTURE_PROFILES.items():
            seeded = _seeded(profile)
            assert any("update-changelog" in path for path in seeded), name
            watcher = any(path.startswith(".lore/watchers/default/") for path in seeded)
            assert watcher is profile.watchers, name

    def test_a_keep_predicate_narrows_the_walk(self):
        everything = _init._defaults_tree_files("doctrines")
        assert everything
        none = _init._defaults_tree_files("doctrines", keep=lambda relative: False)
        assert none == ()
        one = everything[0][0]
        only = _init._defaults_tree_files("doctrines", keep=lambda relative: relative == one)
        assert [relative for relative, _ in only] == [one]

    def test_the_copy_skips_what_the_predicate_drops(self, tmp_path):
        messages = _init._copy_defaults_tree("artifacts", tmp_path, keep=lambda relative: False)
        assert messages == []
        assert list(tmp_path.rglob("*")) == []

    def test_the_prune_removes_a_file_the_predicate_no_longer_keeps(self, tmp_path):
        spec = next(tree for tree in _init.SEEDED_TREES if tree.package == "watchers")
        target = spec.target(tmp_path)
        _init._copy_defaults_tree("watchers", target)
        shipped = sorted(path for path in target.rglob("*") if path.is_file())
        assert shipped
        messages = _init._prune_seeded_tree(target, spec, keep=lambda relative: False)
        assert not [path for path in target.rglob("*") if path.is_file()]
        assert messages and all("no longer shipped" in message for message in messages)

    def test_the_prune_leaves_what_the_predicate_keeps(self, tmp_path):
        spec = next(tree for tree in _init.SEEDED_TREES if tree.package == "watchers")
        target = spec.target(tmp_path)
        _init._copy_defaults_tree("watchers", target)
        assert _init._prune_seeded_tree(target, spec, keep=lambda relative: True) == []

    def test_a_tree_with_no_gate_keeps_nothing(self):
        spec = _init._SeedTree("watchers", "watchers/default", prune=True)
        keep = spec.keep(_Profile())
        assert keep("not-a-shipped-file.yaml") is False


class TestSeedGatesCoverEveryShippedFile:
    """Every shipped seed matches exactly one gate: a new file cannot arrive ungated."""

    @pytest.mark.parametrize("package", ["doctrines", "artifacts", "watchers"])
    def test_each_file_matches_exactly_one_row(self, package):
        spec = next(tree for tree in _init.SEEDED_TREES if tree.package == package)
        files = _init._defaults_tree_files(
            package, set(spec.exclude) or None, set(spec.exclude_files) or None
        )
        assert files
        for relative, _ in files:
            matches = [g for g in _init.SEED_GATES if g.matches(package, relative)]
            assert len(matches) == 1, relative

    def test_no_row_is_dead(self):
        for gate in _init.SEED_GATES:
            files = _init._defaults_tree_files(gate.package)
            assert any(gate.matches(gate.package, relative) for relative, _ in files), gate


class TestSeedLoreDirectoryByProfile:
    def test_the_bare_core_creates_the_infrastructure_and_the_core_trees(self, tmp_path):
        _init._seed_lore_directory(tmp_path, _ALL_OFF)
        lore = tmp_path / ".lore"
        assert (lore / "lore.db").is_file()
        assert (lore / "config.toml").is_file()
        assert (lore / ".gitignore").is_file()
        for name in ("doctrines", "artifacts", "GETTING-STARTED.md"):
            assert (lore / name).exists(), name
        for name in ("codex", "rites", "watchers"):
            assert not (lore / name).exists(), name

    def test_memory_creates_its_codex_root_glossary_and_rite_directories(self, tmp_path):
        _init._seed_lore_directory(tmp_path, _FIXTURE_PROFILES["HARNESS_MEMORY"])
        lore = tmp_path / ".lore"
        assert (lore / "codex" / "codex.md").is_file()
        assert (lore / "codex" / "glossary.yaml").is_file()
        assert (lore / "rites" / "main").is_dir()
        assert (lore / "rites" / "shared").is_dir()

    def test_getting_started_is_the_rendered_document(self, tmp_path):
        from lore import skills as skills_mod

        _init._seed_lore_directory(tmp_path, _Profile())
        written = (tmp_path / ".lore" / "GETTING-STARTED.md").read_text(encoding="utf-8")
        assert written == skills_mod.render_document("getting-started", _Profile())

    def test_a_getting_started_file_that_no_longer_renders_is_removed(
        self, tmp_path, monkeypatch
    ):
        from lore import skills as skills_mod

        _init._seed_lore_directory(tmp_path, _Profile())
        monkeypatch.setattr(skills_mod, "render_document", lambda name, profile: None)
        messages = _init._seed_lore_directory(tmp_path, _Profile())
        assert not (tmp_path / ".lore" / "GETTING-STARTED.md").exists()
        assert any("GETTING-STARTED.md" in message for message in messages)

    def test_what_the_user_authored_survives_a_feature_turning_off(self, tmp_path):
        _init._seed_lore_directory(tmp_path, _Profile())
        mine = tmp_path / ".lore" / "watchers" / "mine.yaml"
        mine.write_text("name: mine\n", encoding="utf-8")
        codex = tmp_path / ".lore" / "codex" / "codex.md"
        before = codex.read_bytes()
        _init._seed_lore_directory(tmp_path, _without("watchers"))
        assert mine.read_text(encoding="utf-8") == "name: mine\n"
        assert not [
            path
            for path in (tmp_path / ".lore" / "watchers" / "default").rglob("*")
            if path.is_file()
        ]
        assert codex.read_bytes() == before

    def test_the_run_orders_artifacts_then_codex_files_then_watchers(self, tmp_path, monkeypatch):
        calls: list[str] = []
        real_copy = _init._copy_defaults_tree
        real_seed = _init._seed_glossary

        def trace_copy(pkg, *args, **kwargs):
            calls.append(f"copy:{pkg}")
            return real_copy(pkg, *args, **kwargs)

        def trace_seed(root):
            calls.append("seed_glossary")
            return real_seed(root)

        monkeypatch.setattr(_init, "_copy_defaults_tree", trace_copy)
        monkeypatch.setattr(_init, "_seed_glossary", trace_seed)
        _init._seed_lore_directory(tmp_path, _Profile())
        assert calls.index("copy:artifacts") < calls.index("seed_glossary") < calls.index("copy:watchers")
        assert "copy:docs" not in calls


class TestTheManifestRecordsTheProfile:
    def test_the_answers_carry_the_profile_and_the_derived_old_ones(self, tmp_path):
        _apply(tmp_path, **_FIXTURE_PROFILES["CLI_MEMORY"].as_answers())
        answers = _manifest_payload(tmp_path)["answers"]
        profile = _FIXTURE_PROFILES["CLI_MEMORY"]
        assert answers["profile"] == profile.as_answers()
        assert _Profile.from_answers(answers["profile"]) == profile
        assert answers["access_mode"] == "cli"
        assert answers["skill_families"] == ["machinery", "memory"]
        assert answers["agents"] == []
        assert answers["skills_gitignore"] == "lore-only"

    def test_the_catalogue_version_is_the_catalogues(self, tmp_path):
        from lore import skills as skills_mod

        _apply(tmp_path)
        assert _manifest_payload(tmp_path)["catalogue_version"] == skills_mod.load_catalogue()["version"]
        assert skills_mod.load_catalogue()["version"] == 3

    def test_the_manifest_format_version_is_unchanged(self, tmp_path):
        _apply(tmp_path)
        assert _manifest_payload(tmp_path)["manifest_version"] == 1
