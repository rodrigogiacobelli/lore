"""E2E tests for lore init — directory creation, DB setup, file seeding, and idempotency.

Spec: conceptual-workflows-lore-init (lore codex show conceptual-workflows-lore-init)
"""

import sqlite3
from importlib import resources
from pathlib import Path

import pytest
from click.testing import CliRunner

from lore.cli import main
from tests.conftest import assert_exit_err, assert_exit_ok


EXPECTED_GITIGNORE_CONTENT = (
    "# Ignore everything in .lore/\n"
    "*\n"
    "!.gitignore\n"
    "!codex\n"
    "!codex/**\n"
    "!artifacts\n"
    "!artifacts/**\n"
)


# ---------------------------------------------------------------------------
# Helpers for init tests that need an already-initialized directory
# ---------------------------------------------------------------------------


@pytest.fixture()
def initialized_dir(tmp_path, monkeypatch):
    """Temp directory that has already been initialized once via lore init."""
    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])
    return tmp_path


# ---------------------------------------------------------------------------
# Fresh init — directory and file structure
# ---------------------------------------------------------------------------


class TestFreshInit:
    """lore init creates the expected project structure."""

    @pytest.fixture()
    def fresh_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        return tmp_path

    def test_exit_code_zero(self, runner, fresh_dir):
        result = runner.invoke(main, ["init"])
        assert_exit_ok(result)

    def test_lore_db_created(self, runner, fresh_dir):
        runner.invoke(main, ["init"])
        assert (fresh_dir / ".lore" / "lore.db").is_file()

    def test_doctrines_dir_created(self, runner, fresh_dir):
        runner.invoke(main, ["init"])
        assert (fresh_dir / ".lore" / "doctrines").is_dir()

    def test_knights_dir_created(self, runner, fresh_dir):
        runner.invoke(main, ["init"])
        assert (fresh_dir / ".lore" / "knights").is_dir()

    def test_artifacts_dir_created(self, runner, fresh_dir):
        runner.invoke(main, ["init"])
        assert (fresh_dir / ".lore" / "artifacts").is_dir()

    def test_schema_version_is_6(self, runner, fresh_dir):
        runner.invoke(main, ["init"])
        db_path = fresh_dir / ".lore" / "lore.db"
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                "SELECT value FROM lore_meta WHERE key = 'schema_version'"
            ).fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row[0] == "6"

    def test_default_knight_present(self, runner, fresh_dir):
        runner.invoke(main, ["init"])
        knights_default = fresh_dir / ".lore" / "knights" / "default"
        md_files = list(knights_default.glob("**/*.md"))
        assert len(md_files) > 0, "No default knight .md files found"

    def test_output_confirms_creation(self, runner, fresh_dir):
        result = runner.invoke(main, ["init"])
        assert "Initialized Lore project" in result.output


# ---------------------------------------------------------------------------
# Database initialization
# ---------------------------------------------------------------------------


class TestDatabaseInitialization:
    """lore.db contains full schema with correct tables, indexes, and meta."""

    def _get_tables(self, db_path):
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return tables

    def _get_indexes(self, db_path):
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        indexes = [row[0] for row in cursor.fetchall()]
        conn.close()
        return indexes

    def test_lore_meta_table_exists(self, runner, project_dir):
        tables = self._get_tables(project_dir / ".lore" / "lore.db")
        assert "lore_meta" in tables

    def test_quests_table_exists(self, runner, project_dir):
        tables = self._get_tables(project_dir / ".lore" / "lore.db")
        assert "quests" in tables

    def test_missions_table_exists(self, runner, project_dir):
        tables = self._get_tables(project_dir / ".lore" / "lore.db")
        assert "missions" in tables

    def test_dependencies_table_exists(self, runner, project_dir):
        tables = self._get_tables(project_dir / ".lore" / "lore.db")
        assert "dependencies" in tables

    def test_idx_quests_status(self, runner, project_dir):
        indexes = self._get_indexes(project_dir / ".lore" / "lore.db")
        assert "idx_quests_status" in indexes

    def test_idx_missions_quest_id(self, runner, project_dir):
        indexes = self._get_indexes(project_dir / ".lore" / "lore.db")
        assert "idx_missions_quest_id" in indexes

    def test_idx_missions_status_priority(self, runner, project_dir):
        indexes = self._get_indexes(project_dir / ".lore" / "lore.db")
        assert "idx_missions_status_priority" in indexes

    def test_idx_deps_from(self, runner, project_dir):
        indexes = self._get_indexes(project_dir / ".lore" / "lore.db")
        assert "idx_deps_from" in indexes

    def test_idx_deps_to(self, runner, project_dir):
        indexes = self._get_indexes(project_dir / ".lore" / "lore.db")
        assert "idx_deps_to" in indexes


# ---------------------------------------------------------------------------
# Gitignore seeding
# ---------------------------------------------------------------------------


class TestGitignoreSeeding:
    """lore init creates .lore/.gitignore with codex and artifacts exceptions."""

    def test_gitignore_created(self, runner, project_dir):
        assert (project_dir / ".lore" / ".gitignore").is_file()

    def test_gitignore_contains_codex_exception(self, runner, project_dir):
        content = (project_dir / ".lore" / ".gitignore").read_text()
        assert "!codex" in content

    def test_gitignore_contains_codex_subtree_exception(self, runner, project_dir):
        content = (project_dir / ".lore" / ".gitignore").read_text()
        assert "!codex/**" in content

    def test_gitignore_contains_artifacts_exception(self, runner, project_dir):
        content = (project_dir / ".lore" / ".gitignore").read_text()
        assert "!artifacts" in content

    def test_gitignore_contains_artifacts_glob_exception(self, runner, project_dir):
        content = (project_dir / ".lore" / ".gitignore").read_text()
        assert "!artifacts/**" in content

    def test_gitignore_wildcard_comes_before_codex_exception(self, runner, project_dir):
        content = (project_dir / ".lore" / ".gitignore").read_text()
        patterns = [
            ln.strip() for ln in content.splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        wildcard_idx = patterns.index("*")
        codex_idx = patterns.index("!codex")
        assert wildcard_idx < codex_idx


class TestReinitUpdatesGitignore:
    """Re-running lore init updates .lore/.gitignore to the latest content."""

    def test_reinit_adds_codex_exception_to_old_gitignore(self, runner, initialized_dir):
        gitignore_path = initialized_dir / ".lore" / ".gitignore"
        gitignore_path.write_text("# Ignore everything in .lore/\n*\n!.gitignore\n")
        runner.invoke(main, ["init"])
        content = gitignore_path.read_text()
        assert "!codex" in content


# ---------------------------------------------------------------------------
# Default doctrines and knights
# ---------------------------------------------------------------------------


class TestCopyDefaultsTree:
    """Unit tests for _copy_defaults_tree in src/lore/init.py."""

    def test_import_copy_defaults_tree(self):
        from lore.init import _copy_defaults_tree  # noqa: F401

    def test_excluded_dir_skipped(self, tmp_path):
        from lore.init import _copy_defaults_tree
        target = tmp_path / "artifacts"
        _copy_defaults_tree("artifacts", target, exclude={"bootstrap"})
        assert not (target / "bootstrap").exists()

    def test_created_verb_for_new_files(self, tmp_path):
        from lore.init import _copy_defaults_tree
        target = tmp_path / "artifacts"
        messages = _copy_defaults_tree("artifacts", target, exclude={"bootstrap"})
        assert any("Created artifacts/" in msg for msg in messages)
        assert not any("Updated artifacts/" in msg for msg in messages)

    def test_updated_verb_for_existing_files(self, tmp_path):
        from lore.init import _copy_defaults_tree
        target = tmp_path / "artifacts"
        _copy_defaults_tree("artifacts", target, exclude={"bootstrap"})
        messages = _copy_defaults_tree("artifacts", target, exclude={"bootstrap"})
        assert any("Updated artifacts/" in msg for msg in messages)
        assert not any("Created artifacts/" in msg for msg in messages)

    def test_returns_list_of_strings(self, tmp_path):
        from lore.init import _copy_defaults_tree
        target = tmp_path / "artifacts"
        messages = _copy_defaults_tree("artifacts", target, exclude={"bootstrap"})
        assert isinstance(messages, list)
        assert all(isinstance(m, str) for m in messages)

    def test_target_directory_created_if_missing(self, tmp_path):
        from lore.init import _copy_defaults_tree
        target = tmp_path / "deep" / "nested" / "artifacts"
        assert not target.exists()
        _copy_defaults_tree("artifacts", target, exclude={"bootstrap"})
        assert target.is_dir()


# ---------------------------------------------------------------------------
# Bootstrap source directory must not exist
# ---------------------------------------------------------------------------


class TestBootstrapSourceFilesDeleted:
    """src/lore/defaults/artifacts/bootstrap/ must be absent from the package."""

    def test_bootstrap_source_directory_absent(self):
        import lore
        package_root = Path(lore.__file__).parent
        bootstrap_src = package_root / "defaults" / "artifacts" / "bootstrap"
        assert not bootstrap_src.exists()

    def test_bootstrap_absent_after_fresh_init(self, runner, project_dir):
        assert (project_dir / ".lore" / "artifacts").is_dir()
        assert not (project_dir / ".lore" / "artifacts" / "bootstrap").exists()

    def test_bootstrap_absent_after_reinit(self, runner, project_dir):
        runner.invoke(main, ["init"])
        assert not (project_dir / ".lore" / "artifacts" / "bootstrap").exists()


# ---------------------------------------------------------------------------
# Re-init idempotency
# ---------------------------------------------------------------------------


class TestReInit:
    """lore init on an already-initialised project is idempotent."""

    def test_exit_code_zero(self, runner, initialized_dir):
        result = runner.invoke(main, ["init"])
        assert_exit_ok(result)

    def test_user_knight_preserved(self, runner, initialized_dir):
        custom_knight = initialized_dir / ".lore" / "knights" / "custom-knight.md"
        custom_knight.write_text("# My custom knight\n")
        runner.invoke(main, ["init"])
        assert custom_knight.exists()
        assert custom_knight.read_text() == "# My custom knight\n"

    def test_user_doctrine_preserved(self, runner, initialized_dir):
        custom_doctrine = initialized_dir / ".lore" / "doctrines" / "my-workflow.yaml"
        custom_doctrine.write_text("name: my-workflow\nsteps: []\n")
        runner.invoke(main, ["init"])
        assert custom_doctrine.exists()
        assert custom_doctrine.read_text() == "name: my-workflow\nsteps: []\n"

    def test_db_data_survives_reinit(self, runner, initialized_dir):
        import json
        runner.invoke(main, ["--json", "new", "quest", "Survive Quest"])
        runner.invoke(main, ["init"])
        result = runner.invoke(main, ["--json", "list"])
        data = json.loads(result.output)
        titles = [q["title"] for q in data["quests"]]
        assert "Survive Quest" in titles

    def test_db_not_modified_on_reinit(self, runner, initialized_dir):
        db_path = initialized_dir / ".lore" / "lore.db"
        mtime1 = db_path.stat().st_mtime
        runner.invoke(main, ["init"])
        mtime2 = db_path.stat().st_mtime
        assert mtime1 == mtime2

    def test_reinit_shows_updated_for_doctrine(self, runner, initialized_dir):
        result = runner.invoke(main, ["init"])
        assert "Updated doctrines/" in result.output

    def test_reinit_shows_updated_for_knight(self, runner, initialized_dir):
        result = runner.invoke(main, ["init"])
        assert "Updated knights/" in result.output

    def test_reinit_does_not_show_skipped_for_defaults(self, runner, initialized_dir):
        result = runner.invoke(main, ["init"])
        assert "Skipped doctrines/" not in result.output
        assert "Skipped knights/" not in result.output



# ---------------------------------------------------------------------------
# Init from nested subdirectory
# ---------------------------------------------------------------------------


class TestInitFromNestedSubdirectory:
    """lore init from a nested subdir creates .lore/ there, not in root."""

    def test_creates_lore_in_cwd_not_parent(self, tmp_path, monkeypatch):
        nested = tmp_path / "src" / "components"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        result = CliRunner().invoke(main, ["init"])
        assert result.exit_code == 0
        assert (nested / ".lore").is_dir()
        assert (nested / ".lore" / "lore.db").is_file()

    def test_parent_dir_unchanged(self, tmp_path, monkeypatch):
        nested = tmp_path / "src" / "components"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        CliRunner().invoke(main, ["init"])
        assert not (tmp_path / ".lore").exists()
        assert not (tmp_path / "src" / ".lore").exists()

    def test_two_independent_lore_projects(self, tmp_path, monkeypatch):
        dir_a = tmp_path / "project_a"
        dir_b = tmp_path / "project_b"
        dir_a.mkdir()
        dir_b.mkdir()
        monkeypatch.chdir(dir_a)
        CliRunner().invoke(main, ["init"])
        monkeypatch.chdir(dir_b)
        CliRunner().invoke(main, ["init"])
        assert (dir_a / ".lore" / "lore.db").is_file()
        assert (dir_b / ".lore" / "lore.db").is_file()


# ---------------------------------------------------------------------------
# Init-specific edge cases
# ---------------------------------------------------------------------------


class TestInitEdgeCases:
    """Edge cases for init: JSON flag position, corrupted DB, no reports dir."""

    def test_init_json_after_subcommand_is_usage_error(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(main, ["init", "--json"])
        assert_exit_err(result, code=2)

    def test_no_lore_dir_created_on_usage_error(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner.invoke(main, ["init", "--json"])
        assert not (tmp_path / ".lore").exists()

    def test_json_flag_before_init_does_not_cause_error(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "init"])
        assert result.exit_code == 0

    def test_no_reports_directory_created(self, runner, project_dir):
        assert (project_dir / ".lore").is_dir()
        assert not (project_dir / ".lore" / "reports").exists()

    def test_missing_lore_meta_triggers_reinit(self, runner, project_dir):
        lore_dir = project_dir / ".lore"
        db_path = lore_dir / "lore.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("DROP TABLE IF EXISTS lore_meta")
        conn.execute("CREATE TABLE dummy (id INTEGER)")
        conn.close()
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0
        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT value FROM lore_meta WHERE key='schema_version'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "6"

    def test_reinit_output_mentions_skipped_or_already(self, runner, project_dir):
        result = runner.invoke(main, ["init"])
        output = result.output.lower()
        assert "skip" in output or "already" in output or "exist" in output


# ---------------------------------------------------------------------------
# Workflow 6 — lore init watcher seeding
# Spec: watchers-us-6 (lore codex show watchers-us-6)
# ---------------------------------------------------------------------------


class TestInitSeedsDefaultWatcher:
    """Scenario 1: lore init seeds .lore/watchers/default/change-log-updates.yaml."""

    def test_watcher_file_exists_after_init(self, runner, project_dir):
        """After lore init, the default watcher YAML is present on disk."""
        watcher_path = (
            project_dir / ".lore" / "watchers" / "default" / "change-log-updates.yaml"
        )
        assert watcher_path.is_file()

    def test_watcher_file_is_valid_yaml(self, runner, project_dir):
        """The seeded watcher file parses as valid YAML without errors."""
        import yaml

        watcher_path = (
            project_dir / ".lore" / "watchers" / "default" / "change-log-updates.yaml"
        )
        content = watcher_path.read_text()
        data = yaml.safe_load(content)
        assert isinstance(data, dict)

    def test_watcher_file_contains_id(self, runner, project_dir):
        """Seeded watcher file has an id field."""
        import yaml

        watcher_path = (
            project_dir / ".lore" / "watchers" / "default" / "change-log-updates.yaml"
        )
        data = yaml.safe_load(watcher_path.read_text())
        assert "id" in data

    def test_watcher_file_contains_interval(self, runner, project_dir):
        """Seeded watcher file has an interval field."""
        import yaml

        watcher_path = (
            project_dir / ".lore" / "watchers" / "default" / "change-log-updates.yaml"
        )
        data = yaml.safe_load(watcher_path.read_text())
        assert "interval" in data

    def test_watcher_list_shows_seeded_watcher(self, runner, project_dir):
        """lore watcher list shows at least one watcher after init."""
        result = runner.invoke(main, ["watcher", "list"])
        assert_exit_ok(result)
        assert "No watchers found." not in result.output

    def test_watcher_list_shows_default_group(self, runner, project_dir):
        """lore watcher list shows the group column as 'default'."""
        result = runner.invoke(main, ["watcher", "list"])
        assert_exit_ok(result)
        assert "default" in result.output

    def test_init_exit_code_zero(self, runner, project_dir):
        """lore init exits with code 0 on a fresh project."""
        # project_dir fixture already ran init; run again to verify idempotent exit
        result = runner.invoke(main, ["init"])
        assert_exit_ok(result)


class TestInitSeedsCompanionDoctrine:
    """Scenario 2: lore init seeds .lore/doctrines/default/update-changelog.yaml."""

    def test_companion_doctrine_file_exists_after_init(self, runner, project_dir):
        """After lore init, the companion doctrine YAML is present on disk."""
        doctrine_path = (
            project_dir / ".lore" / "doctrines" / "default" / "update-changelog.yaml"
        )
        assert doctrine_path.is_file()

    def test_doctrine_list_shows_seeded_doctrine(self, runner, project_dir):
        """lore doctrine list shows at least one doctrine after init."""
        result = runner.invoke(main, ["doctrine", "list"])
        assert_exit_ok(result)
        assert "No doctrines found." not in result.output


class TestInitWatcherIdempotency:
    """Scenario 3: Re-running lore init overwrites default watcher; preserves user watchers."""

    @pytest.fixture()
    def initialized_with_user_watcher(self, tmp_path, monkeypatch):
        """Init once, then create a user watcher outside default/."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        runner.invoke(main, ["init"])
        user_watcher = tmp_path / ".lore" / "watchers" / "my-custom-hook.yaml"
        user_watcher.write_text(
            "id: my-custom-hook\ntitle: My Hook\nsummary: Custom hook.\n"
        )
        return tmp_path

    def test_reinit_exits_zero(self, runner, initialized_with_user_watcher):
        """Re-running lore init succeeds (exit code 0)."""
        result = runner.invoke(main, ["init"])
        assert_exit_ok(result)

    def test_reinit_preserves_user_watcher(self, runner, initialized_with_user_watcher):
        """User-created watcher outside default/ is not touched by re-init."""
        user_watcher = (
            initialized_with_user_watcher / ".lore" / "watchers" / "my-custom-hook.yaml"
        )
        original_content = user_watcher.read_text()
        runner.invoke(main, ["init"])
        assert user_watcher.exists()
        assert user_watcher.read_text() == original_content

    def test_reinit_overwrites_default_watcher(self, runner, initialized_with_user_watcher):
        """Re-init replaces the default watcher file (reset to seeded content)."""
        default_watcher = (
            initialized_with_user_watcher
            / ".lore" / "watchers" / "default" / "change-log-updates.yaml"
        )
        default_watcher.write_text("id: change-log-updates\ntitle: Modified Title\nsummary: x\n")
        runner.invoke(main, ["init"])
        import yaml
        data = yaml.safe_load(default_watcher.read_text())
        assert data.get("title") != "Modified Title"


class TestInitGitignoreWatcherEntries:
    """Scenario 4: lore init adds watcher entries to .lore/.gitignore."""

    def test_gitignore_contains_watchers_exception(self, runner, project_dir):
        """After init, .lore/.gitignore contains the !watchers exception."""
        content = (project_dir / ".lore" / ".gitignore").read_text()
        assert "!watchers" in content

    def test_gitignore_contains_watchers_glob_exception(self, runner, project_dir):
        """After init, .lore/.gitignore contains the !watchers/** glob exception."""
        content = (project_dir / ".lore" / ".gitignore").read_text()
        assert "!watchers/**" in content

    def test_gitignore_contains_watchers_default_reignore(self, runner, project_dir):
        """After init, .lore/.gitignore contains watchers/default/ to re-ignore seeded files."""
        content = (project_dir / ".lore" / ".gitignore").read_text()
        assert "watchers/default/" in content

    def test_gitignore_watcher_exception_before_default_reignore(self, runner, project_dir):
        """!watchers appears before watchers/default/ in .lore/.gitignore (order matters)."""
        content = (project_dir / ".lore" / ".gitignore").read_text()
        exception_idx = content.index("!watchers")
        reignore_idx = content.index("watchers/default/")
        assert exception_idx < reignore_idx


class TestInitSummaryIncludesWatcher:
    """Scenario 5: lore init stdout mentions the seeded watcher file."""

    @pytest.fixture()
    def fresh_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        return tmp_path

    def test_fresh_init_output_mentions_created_watcher(self, runner, fresh_dir):
        """Fresh init stdout contains 'Created watchers/default/change-log-updates.yaml'."""
        result = runner.invoke(main, ["init"])
        assert_exit_ok(result)
        assert "Created watchers/default/change-log-updates.yaml" in result.output

    def test_reinit_output_mentions_updated_watcher(self, runner, initialized_dir):
        """Re-init stdout contains 'Updated watchers/default/change-log-updates.yaml'."""
        result = runner.invoke(main, ["init"])
        assert_exit_ok(result)
        assert "Updated watchers/default/change-log-updates.yaml" in result.output


class TestInitGitignoreNoDuplicates:
    """Scenario 6: Re-running lore init does not duplicate .gitignore watcher entries."""

    def test_reinit_no_duplicate_watchers_exception(self, runner, initialized_dir):
        """Running lore init twice does not produce duplicate !watchers lines."""
        runner.invoke(main, ["init"])
        content = (initialized_dir / ".lore" / ".gitignore").read_text()
        lines = [ln.strip() for ln in content.splitlines()]
        assert lines.count("!watchers") == 1

    def test_reinit_no_duplicate_watchers_glob_exception(self, runner, initialized_dir):
        """Running lore init twice does not produce duplicate !watchers/** lines."""
        runner.invoke(main, ["init"])
        content = (initialized_dir / ".lore" / ".gitignore").read_text()
        lines = [ln.strip() for ln in content.splitlines()]
        assert lines.count("!watchers/**") == 1

    def test_reinit_no_duplicate_watchers_default_reignore(self, runner, initialized_dir):
        """Running lore init twice does not produce duplicate watchers/default/ lines."""
        runner.invoke(main, ["init"])
        content = (initialized_dir / ".lore" / ".gitignore").read_text()
        lines = [ln.strip() for ln in content.splitlines()]
        assert lines.count("watchers/default/") == 1


# ---------------------------------------------------------------------------
# LORE-AGENT.md seeding
# ---------------------------------------------------------------------------


DEFAULTS_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "lore" / "defaults"
DEFAULTS_DOCS_DIR = DEFAULTS_DIR / "docs"


# ---------------------------------------------------------------------------
# docs/ markdown seeding (LORE-AGENT.md, GETTING-STARTED.md, etc.)
# ---------------------------------------------------------------------------


def test_agents_md_not_created_at_project_root(runner, project_dir):
    """lore init no longer creates AGENTS.md at the project root."""
    assert not (project_dir / "AGENTS.md").exists()


class TestDocsMdSeeding:
    """lore init seeds .lore/<name>.md for every file in src/lore/defaults/docs/."""

    @pytest.fixture(params=list(DEFAULTS_DOCS_DIR.glob("*.md")), ids=lambda p: p.name)
    def docs_md_file(self, request):
        return request.param

    def test_docs_md_created_on_fresh_init(self, runner, project_dir, docs_md_file):
        """Fresh init creates .lore/<name>.md for each file in defaults/docs/."""
        assert (project_dir / ".lore" / docs_md_file.name).is_file()

    def test_docs_md_content_is_non_empty(self, runner, project_dir, docs_md_file):
        """Content of .lore/<name>.md is non-empty after init."""
        content = (project_dir / ".lore" / docs_md_file.name).read_text()
        assert content.strip()

    def test_reinit_overwrites_docs_md(self, runner, initialized_dir, docs_md_file):
        """Re-init replaces stale content in .lore/<name>.md."""
        dest = initialized_dir / ".lore" / docs_md_file.name
        dest.write_text("# stale content\n")
        runner.invoke(main, ["init"])
        assert "# stale content" not in dest.read_text()

    def test_fresh_init_output_mentions_created_docs_md(self, runner, tmp_path, monkeypatch, docs_md_file):
        """Fresh init stdout mentions <name>.md as created."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(main, ["init"])
        assert_exit_ok(result)
        assert docs_md_file.name in result.output

    def test_reinit_output_mentions_updated_docs_md(self, runner, initialized_dir, docs_md_file):
        """Re-init stdout mentions <name>.md as updated."""
        result = runner.invoke(main, ["init"])
        assert_exit_ok(result)
        assert docs_md_file.name in result.output


# ---------------------------------------------------------------------------
# skills/ directory seeding
# ---------------------------------------------------------------------------


class TestSkillsSeeding:
    """lore init seeds .lore/skills/ from src/lore/defaults/skills/."""

    def test_skills_dir_created_on_fresh_init(self, runner, project_dir):
        """Fresh init creates .lore/skills/ directory."""
        assert (project_dir / ".lore" / "skills").is_dir()

    def test_all_skill_files_present(self, runner, project_dir):
        """Every skill directory in src/lore/defaults/skills/ is present in .lore/skills/."""
        source_skills = list((DEFAULTS_DIR / "skills").iterdir())
        assert len(source_skills) > 0, "No skill directories found in defaults/skills/"
        for src_dir in source_skills:
            dest = project_dir / ".lore" / "skills" / src_dir.name
            assert dest.is_dir(), f"Missing skill directory: {src_dir.name}"
            assert (dest / "SKILL.md").is_file(), f"Missing SKILL.md in: {src_dir.name}"

    def test_skill_files_are_non_empty(self, runner, project_dir):
        """Each seeded SKILL.md is non-empty after init."""
        for src_dir in (DEFAULTS_DIR / "skills").iterdir():
            dest = project_dir / ".lore" / "skills" / src_dir.name / "SKILL.md"
            assert dest.read_text().strip(), f"SKILL.md is empty: {src_dir.name}"

    def test_reinit_overwrites_skill_files(self, runner, initialized_dir):
        """Re-init replaces stale content in SKILL.md files."""
        skills_dir = initialized_dir / ".lore" / "skills"
        for src_dir in (DEFAULTS_DIR / "skills").iterdir():
            (skills_dir / src_dir.name / "SKILL.md").write_text("# stale skill content\n")
        runner.invoke(main, ["init"])
        for src_dir in (DEFAULTS_DIR / "skills").iterdir():
            dest = skills_dir / src_dir.name / "SKILL.md"
            assert "# stale skill content" not in dest.read_text(), (
                f"SKILL.md not refreshed on reinit: {src_dir.name}"
            )

    def test_fresh_init_output_mentions_created_skill_file(self, runner, tmp_path, monkeypatch):
        """Fresh init stdout mentions at least one skills/ file as created."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(main, ["init"])
        assert_exit_ok(result)
        assert "skills/" in result.output

    def test_reinit_output_mentions_updated_skill_file(self, runner, initialized_dir):
        """Re-init stdout mentions at least one skills/ file as updated."""
        result = runner.invoke(main, ["init"])
        assert_exit_ok(result)
        assert "skills/" in result.output

    def test_user_skill_file_outside_default_not_deleted(self, runner, initialized_dir):
        """A user-created skill file not from defaults is preserved across re-init."""
        custom_skill = initialized_dir / ".lore" / "skills" / "my-custom-skill.md"
        custom_skill.write_text("# My custom skill\n")
        runner.invoke(main, ["init"])
        assert custom_skill.exists()
        assert custom_skill.read_text() == "# My custom skill\n"


# ---------------------------------------------------------------------------
# US-005 / US-006 (codex-sources) — lore init seeds the ingest-source and
# refresh-source skill dirs; no file is written under .claude/skills/.
# Spec anchors: codex-sources-us-005 AC Scenarios 1, 2, 5;
#               codex-sources-us-006 AC Scenario 1;
#               conceptual-workflows-lore-init §Step "seed skills";
#               decisions-006-no-seed-content-tests (structural-only).
# Red state: the default skill files for ingest-source and refresh-source
# do not exist under src/lore/defaults/skills/ yet — the _copy_defaults_tree
# call therefore produces no destination files and these tests fail at the
# existence / frontmatter assertions. The .claude/skills/ negative assertion
# already holds under the current implementation (no regression risk).
# ---------------------------------------------------------------------------


class TestInitSeedsIngestSourceSkill:
    """codex-sources-us-005 — init copies the default ingest-source skill."""

    def _load_frontmatter(self, path: Path) -> dict:
        import yaml

        text = path.read_text(encoding="utf-8")
        assert text.startswith("---"), f"{path} missing frontmatter"
        parts = text.split("---", 2)
        assert len(parts) >= 3, f"{path} malformed frontmatter"
        data = yaml.safe_load(parts[1])
        assert isinstance(data, dict)
        return data

    def test_init_seeds_ingest_source_skill_file(self, runner, project_dir):
        """AC Scenario 1 — .lore/skills/ingest-source/SKILL.md exists after init."""
        path = project_dir / ".lore" / "skills" / "ingest-source" / "SKILL.md"
        assert path.is_file(), f"missing seeded skill: {path}"

    def test_seeded_ingest_source_skill_frontmatter_name(self, runner, project_dir):
        """AC Scenario 2 — seeded skill frontmatter has name == 'ingest-source'."""
        path = project_dir / ".lore" / "skills" / "ingest-source" / "SKILL.md"
        fm = self._load_frontmatter(path)
        assert fm.get("name") == "ingest-source"


class TestInitSeedsRefreshSourceSkill:
    """codex-sources-us-006 — init copies the default refresh-source skill."""

    def _load_frontmatter(self, path: Path) -> dict:
        import yaml

        text = path.read_text(encoding="utf-8")
        assert text.startswith("---"), f"{path} missing frontmatter"
        parts = text.split("---", 2)
        assert len(parts) >= 3, f"{path} malformed frontmatter"
        data = yaml.safe_load(parts[1])
        assert isinstance(data, dict)
        return data

    def test_init_seeds_refresh_source_skill_file(self, runner, project_dir):
        """AC Scenario 1 — .lore/skills/refresh-source/SKILL.md exists after init."""
        path = project_dir / ".lore" / "skills" / "refresh-source" / "SKILL.md"
        assert path.is_file(), f"missing seeded skill: {path}"

    def test_seeded_refresh_source_skill_frontmatter_name(self, runner, project_dir):
        """AC Scenario 2 — seeded skill frontmatter has name == 'refresh-source'."""
        path = project_dir / ".lore" / "skills" / "refresh-source" / "SKILL.md"
        fm = self._load_frontmatter(path)
        assert fm.get("name") == "refresh-source"


class TestInitDoesNotTouchDotClaudeSkills:
    """codex-sources-us-005 AC Scenario 5 + PRD FR-19 —
    lore init MUST NOT write anything under .claude/skills/.
    """

    def test_dot_claude_skills_dir_absent_after_init(self, runner, project_dir):
        """AC Scenario 5 — .claude/skills/ must not exist after init."""
        assert not (project_dir / ".claude" / "skills").exists(), (
            "lore init wrote under .claude/skills/ — forbidden by FR-19"
        )

    def test_no_ingest_source_under_dot_claude_after_init(self, runner, project_dir):
        """AC Scenario 5 — no ingest-source artefact anywhere under .claude/."""
        dot_claude = project_dir / ".claude"
        if dot_claude.exists():
            assert not any(
                p.name == "ingest-source" for p in dot_claude.rglob("*")
            ), "ingest-source leaked into .claude/ tree"

    def test_no_refresh_source_under_dot_claude_after_init(self, runner, project_dir):
        """AC Scenario 5 — no refresh-source artefact anywhere under .claude/."""
        dot_claude = project_dir / ".claude"
        if dot_claude.exists():
            assert not any(
                p.name == "refresh-source" for p in dot_claude.rglob("*")
            ), "refresh-source leaked into .claude/ tree"
