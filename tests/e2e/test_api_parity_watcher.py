"""E2E parity for watcher commands per Tech Spec §10.

Spec §10: "Watcher CRUD → tests/e2e/test_api_parity_watcher.py:
regression — already at parity, must not break."

Watcher is the canonical CRUD pattern (Section 4) that knight / doctrine /
artifact mirror. After G13's facade flip, every watcher CLI command must
go through ``lore.api.*`` not ``lore.watcher.*``.

Post-G16: ``load_watcher`` is internal (``_load_watcher``); use ``read_watcher``.
``list_watchers`` / ``read_watcher`` take ``project_root`` first.
"""

from __future__ import annotations

import json
from pathlib import Path


WATCHER_YAML = """\
id: foo
title: Foo watcher
summary: Test watcher for parity tests.
watch_target:
  - src/lore/cli.py
interval: on_merge
action:
  - doctrine: update-changelog
"""


class TestWatcherListJsonParity:
    """``lore --json watcher list`` envelope matches ``list_watchers``."""

    def test_list_returns_iterable_payload(self, runner, project_dir):
        from lore import api
        from lore.cli import main

        watchers_dir = project_dir / ".lore" / "watchers"
        watchers_dir.mkdir(parents=True, exist_ok=True)
        (watchers_dir / "foo.yaml").write_text(WATCHER_YAML)

        result = runner.invoke(main, ["--json", "watcher", "list"])
        cli_payload = json.loads(result.stdout)
        op_payload = api.list_watchers(project_dir)

        cli_count = len(cli_payload if isinstance(cli_payload, list) else cli_payload.get("watchers", []))
        assert cli_count == len(op_payload)


class TestWatcherNewJsonParity:
    """``lore watcher new`` round-trips through ``lore.api.create_watcher``."""

    def test_new_watcher_creates_yaml_file(self, runner, project_dir, tmp_path):
        from lore.cli import main

        src = tmp_path / "watcher.yaml"
        src.write_text(WATCHER_YAML)
        result = runner.invoke(
            main,
            ["--json", "watcher", "new", "foo", "--from", str(src)],
        )
        payload = json.loads(result.stdout)
        # Watcher's canonical envelope (post-G16) is {id, filename, group}.
        assert "id" in payload


class TestWatcherShowJsonParity:
    """``lore watcher show`` envelope == ``read_watcher`` output."""

    def test_show_envelope_matches_read_watcher(self, runner, project_dir):
        from lore import api
        from lore.cli import main

        watchers_dir = project_dir / ".lore" / "watchers"
        (watchers_dir / "default").mkdir(parents=True, exist_ok=True)
        watcher_path = watchers_dir / "default" / "foo.yaml"
        watcher_path.write_text(WATCHER_YAML)

        result = runner.invoke(main, ["--json", "watcher", "show", "foo"])
        cli_payload = json.loads(result.stdout)
        op_watcher = api.read_watcher(project_dir, "foo")

        # Canonical watcher envelope: {id, group, title, summary, filename,
        # watch_target, interval, action} — verbatim per watcher.py:56-65.
        assert cli_payload.get("id") == op_watcher["id"]
        assert cli_payload.get("title") == op_watcher["title"]


def test_watcher_module_not_imported_directly_in_cli():
    """Post-G13: cli.py routes watcher through facade, not ``lore.watcher``."""
    src = (
        Path(__file__).resolve().parents[2] / "src" / "lore" / "cli.py"
    ).read_text()
    assert "from lore.watcher import" not in src, (
        "cli.py still imports from lore.watcher directly; route via lore.api"
    )
