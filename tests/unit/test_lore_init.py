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


# ---------------------------------------------------------------------------
# LORE-AGENT.md is rendered, not copied.
# Spec: interactive-init-us-007 (lore codex show interactive-init-us-007)
# Workflow: conceptual-workflows-lore-init
#
# ADR-006 boundary: the assertions below read the shipped template only for its
# generated-region markers and for the absence of a hand-maintained table. No
# sentence of its prose is pinned.
# ---------------------------------------------------------------------------

import re as _re
from pathlib import Path as _Path

TEMPLATE_PATH = (
    _Path(__file__).resolve().parents[2]
    / "src" / "lore" / "defaults" / "docs" / "LORE-AGENT.md"
)
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
    from lore.initplan import AccessMode

    text = init_mod.render_agent_instructions(
        skill_ids=("store-memory",),
        install_roots=(_Path(".lore/skills"),),
        access_mode=AccessMode.CLI,
    )
    assert isinstance(text, str)
    assert "<!-- lore:skills-table" not in text
    assert "<!-- lore:access" not in text


def test_skills_table_rows_sorted_and_one_per_id():
    """interactive-init-us-007 — Unit: one markdown row per id, sorted."""
    from lore.init import _render_skills_table

    table = _render_skills_table(
        ("update-knight", "inquest", "store-memory"), (_Path(".claude/skills"),)
    )
    rows = _table_rows(table)
    assert len(rows) == 3
    assert [row.split("|")[1].strip().strip("`") for row in rows] == [
        "inquest",
        "store-memory",
        "update-knight",
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


def test_unterminated_skills_table_region_raises_naming_the_line(monkeypatch):
    """interactive-init-us-007 — Unit: an unterminated generated region is a defect."""
    from lore import init as init_mod
    from lore.initplan import AccessMode

    monkeypatch.setattr(
        init_mod,
        "_read_agent_template",
        lambda: f"# Lore\n\nintro\n{TABLE_OPENER}\nplaceholder\n",
    )
    with pytest.raises(ValueError) as excinfo:
        init_mod.render_agent_instructions(
            skill_ids=(), install_roots=(_Path(".lore/skills"),), access_mode=AccessMode.CLI
        )
    assert ":4" in str(excinfo.value)


def test_a_skills_table_closer_with_no_opener_raises(monkeypatch):
    """interactive-init-us-007 — Unit: the mirror defect is caught too."""
    from lore import init as init_mod
    from lore.initplan import AccessMode

    monkeypatch.setattr(
        init_mod, "_read_agent_template", lambda: f"# Lore\n{TABLE_CLOSER}\n"
    )
    with pytest.raises(ValueError) as excinfo:
        init_mod.render_agent_instructions(
            skill_ids=(), install_roots=(_Path(".lore/skills"),), access_mode=AccessMode.CLI
        )
    assert ":2" in str(excinfo.value)


def test_two_identical_render_calls_are_byte_identical():
    """interactive-init-us-007 — Unit: determinism, because the manifest hashes this."""
    from lore import init as init_mod
    from lore.initplan import AccessMode

    kwargs = {
        "skill_ids": ("store-memory", "inquest"),
        "install_roots": (_Path(".claude/skills"),),
        "access_mode": AccessMode.NATIVE,
    }
    first = init_mod.render_agent_instructions(**kwargs)
    second = init_mod.render_agent_instructions(**kwargs)
    assert first.encode("utf-8") == second.encode("utf-8")


def test_shipped_template_has_one_skills_table_region_and_terminated_access_blocks():
    """interactive-init-us-007 — Unit: the shipped template is structurally correct."""
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert text.count(TABLE_OPENER) == 1
    assert text.count(TABLE_CLOSER) == 1
    assert text.index(TABLE_OPENER) < text.index(TABLE_CLOSER)

    marker = _re.compile(r"^<!--\s*lore:access\s+(\S+)\s*-->$")
    depth = 0
    for lineno, line in enumerate(text.splitlines(), start=1):
        match = marker.match(line.strip())
        if match is None:
            continue
        depth += -1 if match.group(1) == "end" else 1
        assert depth in (0, 1), f"LORE-AGENT.md:{lineno}: unbalanced access marker"
    assert depth == 0, "LORE-AGENT.md: unterminated access block"


def test_template_has_no_table_row_naming_a_retired_skill():
    """interactive-init-us-007 — Unit: no hand-written skills table survives."""
    from lore import skills as skills_mod

    retired = set(skills_mod.load_catalogue().get("retired", {}))
    rows = [
        line
        for line in TEMPLATE_PATH.read_text(encoding="utf-8").splitlines()
        if line.startswith("|")
    ]
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

import json as _json  # noqa: E402
import os as _os  # noqa: E402

from lore import init as _init  # noqa: E402
from lore import manifest as _manifest  # noqa: E402
from lore import safewrite as _safewrite  # noqa: E402
from lore.initplan import FileAction as _FileAction  # noqa: E402


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

    def test_nothing_installed_means_no_listing_anywhere(self, tmp_path):
        """The file governs installed skills; with none there is nothing to say."""
        plan = _init.plan_init(
            project_root=tmp_path, agents=["claude"], skill_families=["none"]
        )
        paths = {entry.path for entry in plan.files}
        assert not [path for path in paths if path.endswith("skills/.gitignore")]

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
        assert _init.plan_init(project_root=tmp_path).answers.access_mode == "native"

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
        assert _init.plan_init(project_root=tmp_path).answers.skill_families == ("memory",)
        assert (
            _init.plan_init(
                project_root=tmp_path, skill_families=["workflow"]
            ).answers.skill_families
            == ("workflow",)
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
        ):
            real = getattr(validators, name)

            def spy(*args, _name=name, _real=real, **kwargs):
                called.append(_name)
                return _real(*args, **kwargs)

            monkeypatch.setattr(validators, name, spy)

        _init.plan_init(project_root=tmp_path, agents=["claude"], skill_families=["memory"])
        assert set(called) == {
            "validate_agent_id",
            "validate_agent_selection",
            "validate_access_mode",
            "validate_skill_family",
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
        assert plan.answers.skill_families == ()
        assert not [entry for entry in plan.files if entry.source.startswith("skill:")]


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

    def test_an_empty_family_selection_still_carries_the_instruction_text(self, tmp_path):
        plan = _init.plan_init(project_root=tmp_path, skill_families=["none"])
        paths = {entry.path for entry in plan.files}
        assert ".lore/LORE-AGENT.md" in paths
        assert not [path for path in paths if path.startswith(".lore/skills/")]

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
        assert plan.answers.access_mode == "native"
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
            _index_of(recorded_writes, "doctrines/default/update-changelog.yaml"),
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
        for skill_id in skills_mod.skills_in_families(skills_mod.family_ids()):
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
    from lore.initplan import AccessMode, InitAnswers, InitPlan

    answers = InitAnswers(
        agents=agents,
        access_mode=AccessMode.NATIVE,
        skill_families=families,
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

    def test_it_names_the_root_the_agents_the_mode_and_the_families(self, tmp_path):
        plan = _synthetic_plan(tmp_path, [])
        first = _init.render_plan(plan).splitlines()[0]
        assert first == (
            f"Plan for {tmp_path} (agents: claude · access: native · "
            "families: memory, workflow)"
        )

    def test_several_agents_are_listed_in_the_plans_order(self, tmp_path):
        plan = _synthetic_plan(tmp_path, [], agents=("claude", "agents-md"))
        assert "agents: claude, agents-md" in _init.render_plan(plan)

    def test_an_empty_selection_reads_as_none_rather_than_blank(self, tmp_path):
        plan = _synthetic_plan(tmp_path, [], agents=(), families=())
        header = _init.render_plan(plan).splitlines()[0]
        assert "agents: none" in header
        assert "families: none" in header


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
        assert _init.answered_prompts(tmp_path) == frozenset(
            {
                _init.PROMPT_AGENTS,
                _init.PROMPT_ACCESS_MODE,
                _init.PROMPT_SKILL_FAMILIES,
                _init.PROMPT_SKILLS_GITIGNORE,
            }
        )

    def test_a_key_at_its_default_value_still_counts_as_recorded(self, tmp_path):
        target = tmp_path / ".lore" / "config.toml"
        target.parent.mkdir(parents=True)
        target.write_text('init-access-mode = "native"\n', encoding="utf-8")
        assert _init.answered_prompts(tmp_path) == frozenset({_init.PROMPT_ACCESS_MODE})

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
