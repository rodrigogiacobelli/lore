"""E2E CLI tests for frontmatter field-edit mode.

Spec: ``transient-frontmatter-field-edit-spec`` Sections B and D.

Covers:
- Mutual exclusion between ``-f / --from`` and field-edit flags.
- KEY=VALUE parsing across all four entity ``edit`` commands.
- JSON envelope parity with the API.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from lore.cli import main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


KNIGHT_MD = (
    "---\n"
    "id: tester\n"
    "title: Tester\n"
    "summary: A test knight.\n"
    "---\n"
    "# body\n"
)

ARTIFACT_MD = (
    "---\n"
    "id: tmpl\n"
    "title: Template\n"
    "summary: A test artifact.\n"
    "---\n"
    "body\n"
)

DOCTRINE_YAML = (
    "id: workflow\n"
    "title: Workflow\n"
    "summary: A doctrine.\n"
    "steps:\n"
    "  - id: s1\n"
    "    title: Step 1\n"
    "    type: human\n"
)

WATCHER_YAML = (
    "id: watch\n"
    "title: Watcher\n"
    "summary: A test watcher.\n"
    "watch_target:\n"
    "  - src/a.py\n"
    "  - src/b.py\n"
    "interval: on_commit\n"
    "action:\n"
    "  - bash: echo hi\n"
)

CODEX_MD = (
    "---\n"
    "id: my-codex\n"
    "title: Codex Doc\n"
    "summary: A test codex doc.\n"
    "---\n"
    "# body\n"
)


def _seed_all(project_dir: Path) -> None:
    (project_dir / ".lore" / "knights").mkdir(parents=True, exist_ok=True)
    (project_dir / ".lore" / "artifacts").mkdir(parents=True, exist_ok=True)
    (project_dir / ".lore" / "doctrines").mkdir(parents=True, exist_ok=True)
    (project_dir / ".lore" / "watchers").mkdir(parents=True, exist_ok=True)
    (project_dir / ".lore" / "codex").mkdir(parents=True, exist_ok=True)
    (project_dir / ".lore" / "knights" / "tester.md").write_text(KNIGHT_MD)
    (project_dir / ".lore" / "artifacts" / "tmpl.md").write_text(ARTIFACT_MD)
    (project_dir / ".lore" / "doctrines" / "workflow.yaml").write_text(DOCTRINE_YAML)
    (project_dir / ".lore" / "watchers" / "watch.yaml").write_text(WATCHER_YAML)
    (project_dir / ".lore" / "codex" / "my-codex.md").write_text(CODEX_MD)


# ---------------------------------------------------------------------------
# Mutual exclusion: -f cannot be combined with --set/--unset/--add/--remove
# ---------------------------------------------------------------------------


class TestMutualExclusion:
    @pytest.mark.parametrize(
        "kind,name,filename",
        [
            ("knight", "tester", "tester.md"),
            ("artifact", "tmpl", "tmpl.md"),
            ("doctrine", "workflow", "workflow.yaml"),
            ("watcher", "watch", "watch.yaml"),
            ("codex", "my-codex", "my-codex.md"),
        ],
    )
    def test_from_and_set_conflict(
        self, runner, project_dir, kind, name, filename
    ):
        _seed_all(project_dir)
        src = project_dir / "source.txt"
        src.write_text("dummy: 1\n")
        result = runner.invoke(
            main,
            [
                kind,
                "edit",
                name,
                "--from",
                str(src),
                "--set",
                "summary=Updated",
            ],
        )
        assert result.exit_code != 0
        combined = (result.stdout or "") + (result.stderr or "")
        assert "Cannot combine" in combined


# ---------------------------------------------------------------------------
# Happy-path --set on each kind.
# ---------------------------------------------------------------------------


class TestSetSummaryHappyPath:
    def test_knight_set_summary(self, runner, project_dir):
        _seed_all(project_dir)
        result = runner.invoke(
            main, ["knight", "edit", "tester", "--set", "summary=New summary."]
        )
        assert result.exit_code == 0, result.output
        text = (project_dir / ".lore" / "knights" / "tester.md").read_text()
        parts = text.split("---", 2)
        meta = yaml.safe_load(parts[1])
        assert meta["summary"] == "New summary."

    def test_artifact_set_title(self, runner, project_dir):
        _seed_all(project_dir)
        result = runner.invoke(
            main, ["artifact", "edit", "tmpl", "--set", "title=Brand New"]
        )
        assert result.exit_code == 0, result.output
        text = (project_dir / ".lore" / "artifacts" / "tmpl.md").read_text()
        parts = text.split("---", 2)
        meta = yaml.safe_load(parts[1])
        assert meta["title"] == "Brand New"

    def test_doctrine_set_summary(self, runner, project_dir):
        _seed_all(project_dir)
        result = runner.invoke(
            main, ["doctrine", "edit", "workflow", "--set", "summary=Refreshed"]
        )
        assert result.exit_code == 0, result.output
        data = yaml.safe_load(
            (project_dir / ".lore" / "doctrines" / "workflow.yaml").read_text()
        )
        assert data["summary"] == "Refreshed"

    def test_watcher_set_interval(self, runner, project_dir):
        _seed_all(project_dir)
        result = runner.invoke(
            main, ["watcher", "edit", "watch", "--set", "interval=daily"]
        )
        assert result.exit_code == 0, result.output
        data = yaml.safe_load(
            (project_dir / ".lore" / "watchers" / "watch.yaml").read_text()
        )
        assert data["interval"] == "daily"


# ---------------------------------------------------------------------------
# --add / --remove on watcher.watch_target (list field).
# ---------------------------------------------------------------------------


class TestAddRemoveWatchTarget:
    def test_add_watch_target(self, runner, project_dir):
        _seed_all(project_dir)
        result = runner.invoke(
            main,
            ["watcher", "edit", "watch", "--add", "watch_target=src/new.py"],
        )
        assert result.exit_code == 0, result.output
        data = yaml.safe_load(
            (project_dir / ".lore" / "watchers" / "watch.yaml").read_text()
        )
        assert "src/new.py" in data["watch_target"]

    def test_remove_watch_target(self, runner, project_dir):
        _seed_all(project_dir)
        result = runner.invoke(
            main,
            ["watcher", "edit", "watch", "--remove", "watch_target=src/a.py"],
        )
        assert result.exit_code == 0, result.output
        data = yaml.safe_load(
            (project_dir / ".lore" / "watchers" / "watch.yaml").read_text()
        )
        assert "src/a.py" not in data["watch_target"]


# ---------------------------------------------------------------------------
# --set on list field uses comma-split.
# ---------------------------------------------------------------------------


class TestSetListCommaSplit:
    def test_watcher_set_watch_target_csv(self, runner, project_dir):
        _seed_all(project_dir)
        result = runner.invoke(
            main,
            [
                "watcher",
                "edit",
                "watch",
                "--set",
                "watch_target=src/x.py, src/y.py",
            ],
        )
        assert result.exit_code == 0, result.output
        data = yaml.safe_load(
            (project_dir / ".lore" / "watchers" / "watch.yaml").read_text()
        )
        assert data["watch_target"] == ["src/x.py", "src/y.py"]


# ---------------------------------------------------------------------------
# JSON envelope parity with update_frontmatter_fields.
# ---------------------------------------------------------------------------


class TestJsonEnvelopeParity:
    @pytest.mark.parametrize(
        "kind,name,filename",
        [
            ("knight", "tester", "tester.md"),
            ("artifact", "tmpl", "tmpl.md"),
            ("doctrine", "workflow", "workflow.yaml"),
            ("watcher", "watch", "watch.yaml"),
            ("codex", "my-codex", "my-codex.md"),
        ],
    )
    def test_cli_json_matches_api(
        self, runner, project_dir, kind, name, filename
    ):
        from lore.api import update_frontmatter_fields

        _seed_all(project_dir)

        cli_result = runner.invoke(
            main,
            ["--json", kind, "edit", name, "--set", "title=New Title"],
        )
        assert cli_result.exit_code == 0, cli_result.output
        cli_env = json.loads(cli_result.stdout)

        # API call on a fresh seed to get the equivalent envelope.
        # Re-seed to ensure same starting point.
        _seed_all(project_dir)
        api_env = update_frontmatter_fields(
            project_dir,
            kind,
            name,
            set_fields={"title": "New Title"},
            unset_fields=None,
            add_to_list=None,
            remove_from_list=None,
        )
        assert cli_env == api_env
        assert set(api_env.keys()) == {"id", "filename", "updated_at"}
        assert api_env["updated_at"] is None


# ---------------------------------------------------------------------------
# CLI rejects --set on structured-item field (watcher.action).
# ---------------------------------------------------------------------------


class TestStructuredFieldRejected:
    def test_watcher_set_action_rejected(self, runner, project_dir):
        _seed_all(project_dir)
        result = runner.invoke(
            main, ["watcher", "edit", "watch", "--set", "action=do-something"]
        )
        assert result.exit_code != 0
        combined = (result.stdout or "") + (result.stderr or "")
        assert "structured" in combined.lower()


# ---------------------------------------------------------------------------
# Full-update CLI envelope now includes updated_at: None for parity.
# ---------------------------------------------------------------------------


class TestFullEditEnvelopeUpdatedAt:
    def test_knight_full_edit_envelope_has_updated_at(self, runner, project_dir):
        _seed_all(project_dir)
        # Full update via --from
        src = project_dir / "new.md"
        src.write_text(KNIGHT_MD)
        result = runner.invoke(
            main,
            ["--json", "knight", "edit", "tester", "--from", str(src)],
        )
        assert result.exit_code == 0, result.output
        env = json.loads(result.stdout)
        assert "updated_at" in env
        assert env["updated_at"] is None
