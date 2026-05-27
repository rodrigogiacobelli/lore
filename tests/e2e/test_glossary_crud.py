"""E2E tests for `lore glossary new` / `edit` / `delete`.

Spec: .lore/codex/transient/glossary-crud-spec.md §5.
Decisions: comments preserved; keyword is identity; writes require existing
glossary.yaml. CLI/API envelopes are byte-identical (ADR-011 parity).
"""

from __future__ import annotations

import json

from lore.cli import main


GLOSSARY_HEADER = (
    "# Project glossary — see `lore codex show conceptual-entities-glossary`.\n"
    "# Before adding a term, run: `lore artifact show glossary-design`.\n"
    "# Auto-surfaced on `lore codex show`. Toggle via .lore/config.toml.\n"
)


SEED_YAML = GLOSSARY_HEADER + (
    "items:\n"
    "  - keyword: Constable\n"
    "    definition: Mission type for orchestrator-handled chores.\n"
    "    aliases:\n"
    "      - constable mission\n"
    "      - chore mission\n"
)


def _seed_glossary(project_dir, content=SEED_YAML):
    path = project_dir / ".lore" / "codex" / "glossary.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Spec §7 test 8 — round-trip JSON
# ---------------------------------------------------------------------------


def test_glossary_new_edit_delete_round_trip_json(runner, project_dir):
    _seed_glossary(project_dir)

    # new
    result = runner.invoke(
        main,
        [
            "--json", "glossary", "new", "Quest",
            "--definition", "A body of work tracked in lore.",
            "--alias", "questline",
        ],
    )
    assert result.exit_code == 0, result.stderr
    new_env = json.loads(result.stdout)
    assert new_env == {"keyword": "Quest", "filename": "glossary.yaml"}

    # edit
    result = runner.invoke(
        main,
        [
            "--json", "glossary", "edit", "Quest",
            "--definition", "A body of work tracked in lore (v2).",
        ],
    )
    assert result.exit_code == 0, result.stderr
    edit_env = json.loads(result.stdout)
    assert edit_env == {"keyword": "Quest", "filename": "glossary.yaml"}

    # delete
    result = runner.invoke(
        main, ["--json", "glossary", "delete", "Quest"],
    )
    assert result.exit_code == 0, result.stderr
    del_env = json.loads(result.stdout)
    assert del_env["keyword"] == "Quest"
    assert del_env["deleted"] is True
    assert isinstance(del_env["deleted_at"], str)


# ---------------------------------------------------------------------------
# Spec §7 test 9 — CLI/API parity
# ---------------------------------------------------------------------------


def test_cli_and_api_outputs_match_for_create_and_delete(runner, project_dir):
    from lore import api

    _seed_glossary(project_dir)

    cli_result = runner.invoke(
        main,
        ["--json", "glossary", "new", "Quest", "--definition", "def"],
    )
    assert cli_result.exit_code == 0
    cli_env = json.loads(cli_result.stdout)

    # API on a freshly-seeded peer dir for independent comparison.
    peer = project_dir.parent / "peer"
    peer.mkdir()
    _seed_glossary(peer)
    api_env = api.create_glossary_item(peer, "Quest", "def")
    assert cli_env == api_env

    cli_result = runner.invoke(
        main, ["--json", "glossary", "delete", "Quest"],
    )
    cli_env = json.loads(cli_result.stdout)
    api_env = api.delete_glossary_item(peer, "Quest")
    # deleted_at differs by the wall-clock moment; compare structural keys.
    assert set(cli_env.keys()) == set(api_env.keys()) == {"keyword", "deleted", "deleted_at"}
    assert cli_env["keyword"] == api_env["keyword"] == "Quest"
    assert cli_env["deleted"] is True
    assert api_env["deleted"] is True


# ---------------------------------------------------------------------------
# CLI surface details (Section 5)
# ---------------------------------------------------------------------------


def test_glossary_new_text_output(runner, project_dir):
    _seed_glossary(project_dir)
    result = runner.invoke(
        main, ["glossary", "new", "Quest", "--definition", "A body of work."],
    )
    assert result.exit_code == 0, result.stderr
    assert 'Created glossary item "Quest".' in result.stdout


def test_glossary_edit_text_output(runner, project_dir):
    _seed_glossary(project_dir)
    result = runner.invoke(
        main, ["glossary", "edit", "Constable", "--definition", "Updated."],
    )
    assert result.exit_code == 0, result.stderr
    assert 'Updated glossary item "Constable".' in result.stdout


def test_glossary_delete_text_output(runner, project_dir):
    _seed_glossary(project_dir)
    result = runner.invoke(main, ["glossary", "delete", "Constable"])
    assert result.exit_code == 0, result.stderr
    assert 'Deleted glossary item "Constable".' in result.stdout


def test_glossary_edit_no_aliases_clears_field(runner, project_dir):
    path = _seed_glossary(project_dir)
    result = runner.invoke(
        main, ["glossary", "edit", "Constable", "--no-aliases"],
    )
    assert result.exit_code == 0, result.stderr
    assert "aliases" not in path.read_text(encoding="utf-8")


def test_glossary_edit_alias_and_no_aliases_conflict(runner, project_dir):
    _seed_glossary(project_dir)
    result = runner.invoke(
        main,
        ["glossary", "edit", "Constable", "--alias", "x", "--no-aliases"],
    )
    assert result.exit_code == 1
    assert "cannot combine" in result.stderr.lower()


def test_glossary_edit_noop_errors(runner, project_dir):
    _seed_glossary(project_dir)
    result = runner.invoke(main, ["glossary", "edit", "Constable"])
    assert result.exit_code == 1
    assert "at least one field" in result.stderr.lower()


def test_glossary_new_duplicate_keyword_errors(runner, project_dir):
    _seed_glossary(project_dir)
    result = runner.invoke(
        main, ["glossary", "new", "constable", "--definition", "dup"],
    )
    assert result.exit_code == 1
    assert "already exists" in result.stderr.lower()


def test_glossary_group_help_drops_read_only_sentence(runner, project_dir):
    _seed_glossary(project_dir)
    result = runner.invoke(main, ["glossary", "--help"])
    assert result.exit_code == 0
    assert "read-only" not in result.stdout.lower()


def test_glossary_new_preserves_comments(runner, project_dir):
    path = _seed_glossary(project_dir)
    result = runner.invoke(
        main, ["glossary", "new", "Quest", "--definition", "A body of work."],
    )
    assert result.exit_code == 0, result.stderr
    raw = path.read_text(encoding="utf-8")
    assert "# Project glossary" in raw
    assert "# Before adding a term" in raw
    assert "# Auto-surfaced on" in raw
