"""US-007 Scenario 7 audit: no list command emits hyphen-joined or empty-string group.

Spec: group-param-us-007 (lore codex show group-param-us-007)
anchor: conceptual-workflows-json-output
"""

import json
import shutil

import pytest

from lore.cli import main


# ---------------------------------------------------------------------------
# Seeders — one nested (multi-segment) + one root entity per entity type
# ---------------------------------------------------------------------------


def _seed_doctrines(project_dir):
    doctrines_dir = project_dir / ".lore" / "doctrines"
    shutil.rmtree(doctrines_dir)
    doctrines_dir.mkdir(parents=True)
    # Nested two-segment
    nested = doctrines_dir / "nested-area" / "sub-area"
    nested.mkdir(parents=True)
    (nested / "child.design.md").write_text(
        "---\nid: child\ntitle: Child\nsummary: Nested doctrine.\n---\n"
    )
    (nested / "child.yaml").write_text(
        "id: child\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )
    # Root-level
    (doctrines_dir / "root-doctrine.design.md").write_text(
        "---\nid: root-doctrine\ntitle: Root\nsummary: Root level.\n---\n"
    )
    (doctrines_dir / "root-doctrine.yaml").write_text(
        "id: root-doctrine\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )


def _seed_knights(project_dir):
    knights_dir = project_dir / ".lore" / "knights"
    shutil.rmtree(knights_dir)
    knights_dir.mkdir(parents=True)
    deep = knights_dir / "nested-area" / "sub-area"
    deep.mkdir(parents=True)
    (deep / "child.md").write_text(
        "---\nid: child\ntitle: Child\nsummary: Nested knight.\n---\n"
    )
    (knights_dir / "root-knight.md").write_text(
        "---\nid: root-knight\ntitle: Root\nsummary: Root level.\n---\n"
    )


def _seed_watchers(project_dir):
    watchers_dir = project_dir / ".lore" / "watchers"
    shutil.rmtree(watchers_dir)
    watchers_dir.mkdir(parents=True)
    deep = watchers_dir / "nested-area" / "sub-area"
    deep.mkdir(parents=True)
    (deep / "child.yaml").write_text(
        "id: child\ntitle: Child\nsummary: Nested watcher.\n"
    )
    (watchers_dir / "root-watcher.yaml").write_text(
        "id: root-watcher\ntitle: Root\nsummary: Root level.\n"
    )


def _seed_artifacts(project_dir):
    artifacts_dir = project_dir / ".lore" / "artifacts"
    shutil.rmtree(artifacts_dir)
    artifacts_dir.mkdir(parents=True)
    deep = artifacts_dir / "nested-area" / "sub-area"
    deep.mkdir(parents=True)
    (deep / "child.md").write_text(
        "---\nid: child\ntitle: Child\nsummary: Nested artifact.\n---\n"
    )
    (artifacts_dir / "root-artifact.md").write_text(
        "---\nid: root-artifact\ntitle: Root\nsummary: Root level.\n---\n"
    )


def _seed_codex(project_dir):
    codex_dir = project_dir / ".lore" / "codex"
    if codex_dir.exists():
        shutil.rmtree(codex_dir)
    codex_dir.mkdir(parents=True)
    deep = codex_dir / "nested-area" / "sub-area"
    deep.mkdir(parents=True)
    (deep / "child.md").write_text(
        "---\nid: child\ntitle: Child\nsummary: Nested codex doc.\n---\n"
    )
    (codex_dir / "root-doc.md").write_text(
        "---\nid: root-doc\ntitle: Root\nsummary: Root level.\n---\n"
    )


_SEEDERS = {
    "doctrine": _seed_doctrines,
    "knight": _seed_knights,
    "watcher": _seed_watchers,
    "artifact": _seed_artifacts,
    "codex": _seed_codex,
}


# ---------------------------------------------------------------------------
# Scenario 7: every list JSON emits null or slash-joined; never "" or hyphen-joined
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cmd,envelope_key",
    [
        ("doctrine", "doctrines"),
        ("knight", "knights"),
        ("watcher", "watchers"),
        ("artifact", "artifacts"),
        ("codex", "codex"),
    ],
)
def test_list_json_never_hyphen_or_empty_group(runner, project_dir, cmd, envelope_key):
    """US-007 Scenario 7: every list JSON has group null or slash-joined — never "" or "a-b"."""
    _SEEDERS[cmd](project_dir)
    result = runner.invoke(main, [cmd, "list", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    rows = data[envelope_key]
    # The nested seeded entity must exist with slash-joined group
    nested_rows = [r for r in rows if r["id"] == "child"]
    assert nested_rows, f"{cmd}: expected 'child' entity in {envelope_key}: {rows}"
    assert nested_rows[0]["group"] == "nested-area/sub-area", (
        f"{cmd}: expected slash-joined group, got {nested_rows[0]['group']!r}"
    )
    # The root seeded entity must have group is None
    root_ids = {
        "doctrine": "root-doctrine",
        "knight": "root-knight",
        "watcher": "root-watcher",
        "artifact": "root-artifact",
        "codex": "root-doc",
    }
    root_rows = [r for r in rows if r["id"] == root_ids[cmd]]
    assert root_rows, f"{cmd}: expected root entity {root_ids[cmd]} in {envelope_key}"
    assert root_rows[0]["group"] is None, (
        f"{cmd}: expected group=None for root, got {root_rows[0]['group']!r}"
    )
    # Universal invariant: no row has "" or hyphen-joined "nested-area-sub-area"
    for row in rows:
        assert row["group"] != "", f"{cmd}: group must never be empty string: {row}"
        assert row["group"] != "nested-area-sub-area", (
            f"{cmd}: group must never be hyphen-joined: {row}"
        )


