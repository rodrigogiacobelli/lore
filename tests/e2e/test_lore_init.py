"""E2E tests for lore init — directory creation, DB setup, file seeding, and idempotency.

Spec: conceptual-workflows-lore-init (lore codex show conceptual-workflows-lore-init)
"""

import json
import sqlite3
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


# ``LORE-AGENT.md`` is no longer one of them: interactive-init-us-007 made it a
# rendered file and interactive-init-us-015 put it in the install manifest, so
# it follows the reconciliation rules rather than the verbatim-copy rules. Its
# own contract is asserted in TestRenderedAgentInstructions and in
# TestManifestTrackedFilesResistSilentOverwrite below.
COPIED_DOCS = [p for p in DEFAULTS_DOCS_DIR.glob("*.md") if p.name != "LORE-AGENT.md"]


class TestDocsMdSeeding:
    """lore init copies .lore/<name>.md verbatim for each file in defaults/docs/."""

    @pytest.fixture(params=COPIED_DOCS, ids=lambda p: p.name)
    def docs_md_file(self, request):
        return request.param

    def test_the_copied_docs_set_is_not_empty(self):
        """A narrowed parameter set that emptied itself would prove nothing."""
        assert COPIED_DOCS

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


class TestManifestTrackedFilesResistSilentOverwrite:
    """A file the manifest tracks is refreshed, restored — or reported.

    Spec: interactive-init-us-015 (lore codex show interactive-init-us-015);
    PRD FR-27 "refused means untouched".
    Anchor: conceptual-workflows-lore-init — idempotency and the conflict gate.

    What the manifest buys is knowing *which* files are Lore's, and the
    ownership ruling settles what that knowledge is for: these two are Lore's,
    so an edit to either is replaced and said out loud rather than left in
    place. FR-27 is untouched by that — it is about a path holding something
    Lore did not install, which neither of these is.
    """

    LORE_TRACKED = (".lore/LORE-AGENT.md", ".lore/skills/store-memory/SKILL.md")

    @pytest.mark.parametrize("relative", LORE_TRACKED)
    def test_a_deleted_file_is_restored_and_reported(self, runner, initialized_dir, relative):
        target = initialized_dir / relative
        assert target.is_file()
        original = target.read_bytes()
        target.unlink()
        result = runner.invoke(main, ["init"])
        assert_exit_ok(result)
        assert target.read_bytes() == original
        assert Path(relative).name in result.output

    @pytest.mark.parametrize("relative", LORE_TRACKED)
    def test_an_edited_file_is_replaced_and_the_write_reported(
        self, runner, initialized_dir, relative
    ):
        target = initialized_dir / relative
        shipped = target.read_bytes()
        target.write_bytes(b"# content I wrote myself\n")
        result = runner.invoke(main, ["init"])
        assert_exit_ok(result)
        assert target.read_bytes() == shipped
        assert "! Kept" not in result.output
        assert Path(relative).name in result.output

    @pytest.mark.parametrize("relative", LORE_TRACKED)
    def test_an_untouched_file_is_neither_rewritten_nor_reported(
        self, runner, initialized_dir, relative
    ):
        """Idempotency: a second run with the same answers reports zero changes."""
        target = initialized_dir / relative
        before = target.stat().st_mtime_ns
        result = runner.invoke(main, ["init"])
        assert_exit_ok(result)
        assert target.stat().st_mtime_ns == before
        assert f"Updated {relative.removeprefix('.lore/')}" not in result.output


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

    def test_reinit_restores_a_deleted_skill_file(self, runner, initialized_dir):
        """Re-init puts back a SKILL.md that went missing, byte for byte.

        Refreshing an *edited* one is a conflict, not an overwrite — see
        TestManifestTrackedFilesResistSilentOverwrite. What re-init still owns
        unconditionally is restoring what is gone.
        """
        skills_dir = initialized_dir / ".lore" / "skills"
        originals = {
            src_dir.name: (skills_dir / src_dir.name / "SKILL.md").read_bytes()
            for src_dir in (DEFAULTS_DIR / "skills").iterdir()
        }
        for name in originals:
            (skills_dir / name / "SKILL.md").unlink()
        runner.invoke(main, ["init"])
        for name, content in originals.items():
            dest = skills_dir / name / "SKILL.md"
            assert dest.read_bytes() == content, f"SKILL.md not restored on reinit: {name}"

    def test_fresh_init_output_mentions_created_skill_file(self, runner, tmp_path, monkeypatch):
        """Fresh init stdout mentions at least one skills/ file as created."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(main, ["init"])
        assert_exit_ok(result)
        assert "skills/" in result.output

    def test_reinit_reports_a_skill_it_had_to_write(self, runner, initialized_dir):
        """Re-init names the skills it wrote — and stays quiet when it wrote none.

        A run that changes nothing reports nothing: that is the idempotency
        guarantee, so the report has to be provoked by an actual absence.
        """
        quiet = runner.invoke(main, ["init"])
        assert_exit_ok(quiet)
        assert "skills/" not in quiet.output

        (initialized_dir / ".lore" / "skills" / "store-memory" / "SKILL.md").unlink()
        result = runner.invoke(main, ["init"])
        assert_exit_ok(result)
        assert "skills/store-memory/SKILL.md" in result.output

    def test_user_skill_file_outside_default_not_deleted(self, runner, initialized_dir):
        """A user-created skill file not from defaults is preserved across re-init."""
        custom_skill = initialized_dir / ".lore" / "skills" / "my-custom-skill.md"
        custom_skill.write_text("# My custom skill\n")
        runner.invoke(main, ["init"])
        assert custom_skill.exists()
        assert custom_skill.read_text() == "# My custom skill\n"


# ---------------------------------------------------------------------------
# The ingest-source and refresh-source seeding scenarios that stood here were
# removed with their subjects: interactive-init-us-005 absorbs both skills into
# `store-memory`, so neither directory ships or seeds any more. The generic
# TestSkillsSeeding class above already proves every shipped skill directory
# reaches `.lore/skills/`, whatever the current catalogue names.
# ---------------------------------------------------------------------------


class TestInitDoesNotTouchDotClaudeSkills:
    """codex-sources-us-005 AC Scenario 5 + PRD FR-19 —
    lore init MUST NOT write anything under .claude/skills/.
    """

    def test_dot_claude_skills_dir_absent_after_init(self, runner, project_dir):
        """AC Scenario 5 — .claude/skills/ must not exist after init."""
        assert not (project_dir / ".claude" / "skills").exists(), (
            "lore init wrote under .claude/skills/ — forbidden by FR-19"
        )

    def test_no_shipped_skill_leaks_under_dot_claude_after_init(self, runner, project_dir):
        """AC Scenario 5 — no shipped skill artefact anywhere under .claude/."""
        dot_claude = project_dir / ".claude"
        if not dot_claude.exists():
            return
        shipped = {p.name for p in (DEFAULTS_DIR / "skills").iterdir() if p.is_dir()}
        leaked = {p.name for p in dot_claude.rglob("*")} & shipped
        assert not leaked, f"{sorted(leaked)} leaked into the .claude/ tree"


# ---------------------------------------------------------------------------
# US-001 — lore init seeds .lore/codex/codex.md
# Spec anchors: init-seed-codex-md-us-1 (Scenarios 1-4);
#               conceptual-workflows-lore-init step 7a (user-tracked seeds);
#               decisions-013-toml-for-config-yaml-for-glossary (idempotency);
#               decisions-006-no-seed-content-tests (structural-only).
# Red state: lore init does not yet seed .lore/codex/codex.md — fresh-init
# tests fail on the existence/substring assertions; re-init tests cannot
# trigger because the file is never seeded; health/list checks fail because
# id 'codex' does not appear in the codex index.
# ---------------------------------------------------------------------------


class TestInitSeedsCodexMd:
    """init-seed-codex-md-us-1 — lore init seeds .lore/codex/codex.md."""

    def test_fresh_init_writes_codex_md_with_rewritten_id(self, tmp_path, monkeypatch):
        # conceptual-workflows-lore-init step 7a — Scenario 1 (Fresh init seeds codex.md)
        # ADR-006: assert structural fields + substring only; no body prose pinning.
        import yaml

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["init"])
        assert_exit_ok(result)
        target = tmp_path / ".lore" / "codex" / "codex.md"
        assert target.is_file()
        # Parse frontmatter — structural assertions only.
        text = target.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        fm_end = text.index("\n---\n", 4)
        front = yaml.safe_load(text[4:fm_end])
        assert front["id"] == "codex"           # rewrite ran
        assert front["id"] != "example-codex"   # source ID never leaks
        assert front.get("title")               # non-empty title (schema-required)
        assert front.get("summary")             # non-empty summary (schema-required)
        # Status line emitted on first seed.
        assert "Created codex/codex.md" in result.output

    def test_reinit_leaves_existing_codex_md_byte_for_byte_untouched(
        self, tmp_path, monkeypatch
    ):
        # conceptual-workflows-lore-init step 7a (idempotency clause) — Scenario 2
        # ADR-013 idempotency rule: re-init never overwrites a user-edited file.
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        first = runner.invoke(main, ["init"])
        assert_exit_ok(first)
        # Init #1 must have created the file — this is what makes the
        # idempotency assertion meaningful (and forces this test to fail in
        # red state, where init never seeds codex.md).
        assert "Created codex/codex.md" in first.output
        target = tmp_path / ".lore" / "codex" / "codex.md"
        assert target.is_file()
        sentinel = (
            b"---\nid: codex\ntitle: My Custom\nsummary: edited by user\n---\n"
            b"\n# Custom body\n"
        )
        target.write_bytes(sentinel)
        result = runner.invoke(main, ["init"])
        assert_exit_ok(result)
        # Byte-for-byte equality is permitted here — sentinel is user-supplied,
        # not seed content, so ADR-006 does not forbid it.
        assert target.read_bytes() == sentinel
        # Silent skip — no "Created" line for the existing file.
        assert "Created codex/codex.md" not in result.output

    def test_fresh_init_then_health_schemas_is_green(self, tmp_path, monkeypatch):
        # conceptual-workflows-lore-init (hard acceptance: schema-green after init)
        # cross-refs conceptual-workflows-health — Scenario 3
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        init_result = runner.invoke(main, ["init"])
        assert_exit_ok(init_result)
        # Pre-condition for this scenario: codex.md must actually be seeded
        # so the schema check has something to validate. Without this the
        # assertion below is vacuously true.
        codex_md = tmp_path / ".lore" / "codex" / "codex.md"
        assert codex_md.is_file()
        result = runner.invoke(main, ["health", "--scope", "schemas"])
        assert_exit_ok(result)
        # Substring assertion — no specific schema-error prose pinned.
        # Match "0 errors" exactly to avoid false positive on the literal
        # word "errors" in the summary line.
        assert "0 errors" in result.output

    def test_fresh_init_lists_codex_root_via_codex_list(self, tmp_path, monkeypatch):
        # conceptual-workflows-codex (codex list surface) + conceptual-workflows-lore-init step 7a
        # Scenario 4 — seeded doc is reachable via the codex ID 'codex'.
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        assert_exit_ok(runner.invoke(main, ["init"]))
        list_result = runner.invoke(main, ["codex", "list"])
        assert_exit_ok(list_result)
        # Structural: the ID 'codex' appears as a row (case-sensitive).
        assert "codex" in list_result.output
        show_result = runner.invoke(main, ["codex", "show", "codex"])
        assert_exit_ok(show_result)
        # Substring only — no body prose assertion (ADR-006).
        assert show_result.output.strip() != ""


# ---------------------------------------------------------------------------
# The agent instruction text is rendered, not copied.
# Spec: interactive-init-us-007 (lore codex show interactive-init-us-007)
# Anchor: conceptual-workflows-lore-init — LORE-AGENT.md rendering.
#
# Structure only (ADR-006): row counts, ids, install paths and the absence of
# generated-region markers. No sentence of the rendered text is pinned.
# ---------------------------------------------------------------------------


SKILLS_TABLE_HEADER = "| Skill | What it does | Where |"


def _rendered_table_rows(text: str) -> list[str]:
    lines = text.splitlines()
    assert SKILLS_TABLE_HEADER in lines, "the instruction text carries no skills table"
    start = lines.index(SKILLS_TABLE_HEADER) + 2
    rows: list[str] = []
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        rows.append(line)
    return rows


class TestRenderedAgentInstructions:
    """conceptual-workflows-lore-init — the skills table names the installed set."""

    def test_skills_table_rows_match_the_installed_selection(self):
        """Scenario 1 — one row per installed skill, pointing at the agent's dir."""
        from lore import skills
        from lore.init import render_agent_instructions
        from lore.initplan import AccessMode

        selected = skills.skills_in_families(("memory", "workflow"))
        text = render_agent_instructions(
            skill_ids=selected,
            install_roots=(Path(".claude/skills"),),
            access_mode=AccessMode.NATIVE,
        )
        rows = _rendered_table_rows(text)
        assert len(rows) == len(selected) == 5
        for skill_id in selected:
            assert any(
                f"`{skill_id}`" in row and f".claude/skills/{skill_id}/" in row
                for row in rows
            ), f"{skill_id} has no row naming its install path"
        assert "<!-- lore:skills-table" not in text
        assert "<!-- lore:access" not in text

    def test_no_agent_selected_points_the_table_at_dot_lore_skills(self):
        """Scenario 2 — the install path follows the target."""
        from lore import skills
        from lore.init import render_agent_instructions
        from lore.initplan import AccessMode

        selected = skills.skills_in_families(("memory", "workflow"))
        text = render_agent_instructions(
            skill_ids=selected,
            install_roots=(Path(".lore/skills"),),
            access_mode=AccessMode.NATIVE,
        )
        rows = _rendered_table_rows(text)
        assert rows
        for row in rows:
            assert ".lore/skills/" in row
            assert ".claude/skills/" not in row

    def test_instruction_text_differs_between_access_modes(self):
        """Scenario 3 — the access mode reaches the instruction text."""
        from lore.init import render_agent_instructions
        from lore.initplan import AccessMode

        rendered = {
            mode: render_agent_instructions(
                skill_ids=("store-memory",),
                install_roots=(Path(".lore/skills"),),
                access_mode=mode,
            )
            for mode in AccessMode
        }
        assert rendered[AccessMode.CLI] != rendered[AccessMode.NATIVE]
        for text in rendered.values():
            assert "<!-- lore:access" not in text

    def test_memory_only_selection_yields_a_two_row_table(self):
        """Scenario 4 — a narrowed family selection narrows the table."""
        from lore import skills
        from lore.init import render_agent_instructions
        from lore.initplan import AccessMode

        memory = skills.skills_in_families(("memory",))
        other = set(skills.skills_in_families(("machinery", "workflow")))
        text = render_agent_instructions(
            skill_ids=memory,
            install_roots=(Path(".claude/skills"),),
            access_mode=AccessMode.CLI,
        )
        rows = _rendered_table_rows(text)
        assert len(rows) == 2
        for row in rows:
            for excluded in other:
                assert f"`{excluded}`" not in row

    def test_init_writes_the_rendered_text_to_dot_lore(self, runner, project_dir):
        """FR-9 parity — .lore/LORE-AGENT.md is written on every run, agent or not."""
        from lore.paths import lore_agent_path

        target = lore_agent_path(project_dir)
        assert target.is_file()
        text = target.read_text(encoding="utf-8")
        assert "<!-- lore:skills-table" not in text
        assert "<!-- lore:access" not in text
        assert _rendered_table_rows(text)


# ---------------------------------------------------------------------------
# The marked block Lore owns inside files the user owns.
# Spec: interactive-init-us-012 (lore codex show interactive-init-us-012)
# Anchor: conceptual-workflows-lore-init — instruction-file marker block,
#         root gitignore block, installed-skill tracking.
#
# The story writes its scenarios as `lore init --agent claude ...`. Those flags
# land with the CLI surface (interactive-init-us-016); until then the identical
# call is made through the Python surface the flags will fill, which is the
# surface ADR-011 makes authoritative anyway.
# ---------------------------------------------------------------------------

LORE_BEGIN = "<!-- lore:begin -->"
LORE_END = "<!-- lore:end -->"


def plan_init(**kwargs):
    """Thin indirection so this file collects before ``lore.init`` grows the name."""
    from lore.init import plan_init as _plan_init

    return _plan_init(**kwargs)


def apply_init(plan):
    from lore.init import apply_init as _apply_init

    return _apply_init(plan)


def _init_at(root, **answers):
    """Plan and apply one initialisation at *root*, returning (plan, result)."""
    plan = plan_init(project_root=root, **answers)
    return plan, apply_init(plan)


class TestExistingInstructionFile:
    """interactive-init-us-012 — Scenarios 1, 2, 3 and 7."""

    USER_PROSE = "# Acme\n\nHouse rules I wrote months ago.\n"

    def test_append_preserves_every_original_byte(self, tmp_path):
        """Scenario 1."""
        claude = tmp_path / "CLAUDE.md"
        claude.write_text(self.USER_PROSE, encoding="utf-8")
        _init_at(tmp_path, agents=["claude"], on_existing_agent_file="append")
        after = claude.read_text(encoding="utf-8")
        assert after.startswith(self.USER_PROSE)
        assert LORE_BEGIN in after and LORE_END in after
        assert (tmp_path / ".lore" / "LORE-AGENT.md").is_file()

    def test_skip_leaves_the_file_byte_identical(self, tmp_path):
        """Scenario 2."""
        claude = tmp_path / "CLAUDE.md"
        claude.write_bytes(self.USER_PROSE.encode("utf-8"))
        plan, _ = _init_at(tmp_path, agents=["claude"], on_existing_agent_file="skip")
        assert claude.read_bytes() == self.USER_PROSE.encode("utf-8")
        assert "CLAUDE.md" not in {entry.path for entry in plan.files}
        assert (tmp_path / ".lore" / "LORE-AGENT.md").is_file()

    def test_a_second_run_replaces_only_the_block(self, tmp_path):
        """Scenario 3."""
        claude = tmp_path / "CLAUDE.md"
        claude.write_text(self.USER_PROSE, encoding="utf-8")
        _init_at(tmp_path, agents=["claude"])
        below = "\nMore prose, added after Lore's block.\n"
        claude.write_text(claude.read_text(encoding="utf-8") + below, encoding="utf-8")
        _init_at(tmp_path, agents=["claude"], skill_families=["memory"])
        after = claude.read_text(encoding="utf-8")
        assert after.startswith(self.USER_PROSE)
        assert after.endswith(below)
        assert after.count(LORE_BEGIN) == 1
        assert after.count(LORE_END) == 1

    def test_editing_outside_the_markers_is_not_a_conflict(self, tmp_path):
        """Scenario 7."""
        claude = tmp_path / "CLAUDE.md"
        claude.write_text(self.USER_PROSE, encoding="utf-8")
        _init_at(tmp_path, agents=["claude"])
        claude.write_text(
            claude.read_text(encoding="utf-8") + "\nEdited after install.\n",
            encoding="utf-8",
        )
        plan = plan_init(project_root=tmp_path, agents=["claude"])
        row = next(entry for entry in plan.files if entry.path == "CLAUDE.md")
        assert row.action.value != "conflict"
        apply_init(plan)
        assert "Edited after install." in claude.read_text(encoding="utf-8")


class TestTheRootGitignoreIsNeverWritten:
    """The block Lore used to write there is retired — see FR-11's reversal.

    Every path it named was already ignored by the ``*`` opening
    `.lore/.gitignore`, so the block decided nothing and cost the project a
    write into a file it owns. `tests/e2e/test_init_root_gitignore_retired.py`
    covers the other half: a project that already carries one has it removed.
    """

    def test_a_user_gitignore_keeps_every_byte(self, tmp_path):
        gitignore = tmp_path / ".gitignore"
        user_lines = "node_modules/\n*.log\n"
        gitignore.write_text(user_lines, encoding="utf-8")
        _init_at(tmp_path)
        assert gitignore.read_text(encoding="utf-8") == user_lines

    def test_no_file_is_created_and_no_row_names_it(self, tmp_path):
        plan, _ = _init_at(tmp_path)
        assert not (tmp_path / ".gitignore").exists()
        assert ".gitignore" not in {entry.path for entry in plan.files}


class TestSkillsGitignoreE2E:
    """interactive-init-us-012 — Scenario 6: the token decides the file."""

    def test_lore_only_lists_the_installed_directories(self, tmp_path):
        from lore import skills as skills_mod

        _init_at(
            tmp_path,
            agents=["claude"],
            skill_families=["memory"],
            skills_gitignore="lore-only",
        )
        listing = tmp_path / ".claude" / "skills" / ".gitignore"
        assert listing.is_file()
        entries = [
            line for line in listing.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        ]
        installed = sorted(skills_mod.skills_in_families(("memory",)))
        assert entries == [f"{skill_id}/" for skill_id in installed]

    def test_none_removes_a_previously_written_listing(self, tmp_path):
        _init_at(tmp_path, agents=["claude"], skills_gitignore="lore-only")
        listing = tmp_path / ".claude" / "skills" / ".gitignore"
        assert listing.is_file()
        _init_at(tmp_path, agents=["claude"], skills_gitignore="none")
        assert not listing.exists()

    def test_all_replaces_the_listing_with_a_whole_directory_rule(self, tmp_path):
        _init_at(tmp_path, agents=["claude"], skills_gitignore="lore-only")
        _init_at(tmp_path, agents=["claude"], skills_gitignore="all")
        listing = tmp_path / ".claude" / "skills" / ".gitignore"
        entries = [
            line
            for line in listing.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        ]
        assert entries == ["*", "!.gitignore"]
        # The `all` answer used to reach the native root a second way, through a
        # `.claude/skills/` line in the root block. Nothing writes that file now.
        assert not (tmp_path / ".gitignore").exists()

    def test_the_fallback_root_gets_the_same_listing(self, tmp_path):
        from lore import skills as skills_mod

        _init_at(
            tmp_path,
            agents=["gemini"],
            skill_families=["memory"],
            skills_gitignore="lore-only",
        )
        listing = tmp_path / ".lore" / "skills" / ".gitignore"
        assert listing.is_file()
        entries = [
            line for line in listing.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        ]
        installed = sorted(skills_mod.skills_in_families(("memory",)))
        assert entries == [f"{skill_id}/" for skill_id in installed]


# ---------------------------------------------------------------------------
# The answers are recorded in config.toml and reused.
# Spec: interactive-init-us-013 (lore codex show interactive-init-us-013)
# Anchor: conceptual-workflows-lore-init — recorded answers.
# ---------------------------------------------------------------------------


class TestAnswersArePersistedAndReused:
    """interactive-init-us-013 — Scenarios 4 and 5."""

    def test_the_four_answers_are_written_back_and_reused(self, tmp_path):
        """Scenario 4."""
        import tomllib

        from lore.config import load_config

        _init_at(
            tmp_path,
            agents=["claude"],
            access_mode="cli",
            skill_families=["memory", "workflow"],
            skills_gitignore="none",
        )
        raw = tomllib.loads((tmp_path / ".lore" / "config.toml").read_text(encoding="utf-8"))
        assert raw["init-agents"] == ["claude"]
        assert raw["init-access-mode"] == "cli"
        assert raw["init-skill-families"] == ["memory", "workflow"]
        assert raw["init-skills-gitignore"] == "none"

        before = load_config(tmp_path)
        _init_at(tmp_path)
        after = load_config(tmp_path)
        assert (before.init_agents, before.init_access_mode) == (
            after.init_agents,
            after.init_access_mode,
        )
        assert before.init_skill_families == after.init_skill_families
        assert before.init_skills_gitignore == after.init_skills_gitignore

    def test_an_aggregate_token_is_never_persisted(self, tmp_path):
        """Scenario 5."""
        import tomllib

        _init_at(tmp_path, skill_families=["all"])
        raw = tomllib.loads((tmp_path / ".lore" / "config.toml").read_text(encoding="utf-8"))
        assert raw["init-skill-families"] == ["machinery", "memory", "workflow"]
        assert "all" not in raw["init-skill-families"]

    def test_a_user_setting_line_survives_the_write_back(self, tmp_path):
        _init_at(tmp_path)
        config = tmp_path / ".lore" / "config.toml"
        config.write_text(
            config.read_text(encoding="utf-8") + "\nmy-own-key = 42\n", encoding="utf-8"
        )
        _init_at(tmp_path, access_mode="cli")
        text = config.read_text(encoding="utf-8")
        assert "my-own-key = 42" in text
        assert 'init-access-mode = "cli"' in text
        # Settings lines only: the generated header names every known key too
        # (interactive-init-us-020), and a comment is not a second answer.
        settings = [line for line in text.splitlines() if not line.startswith("#")]
        assert sum(line.startswith("init-access-mode") for line in settings) == 1


# ---------------------------------------------------------------------------
# apply_init performs a computed plan; interrupted runs recover.
# Spec: interactive-init-us-015 (lore codex show interactive-init-us-015)
# Anchor: conceptual-workflows-lore-init — idempotency, interrupted run
#         recovery, apply report.
# ---------------------------------------------------------------------------


class TestIdempotency:
    """interactive-init-us-015 — Scenario 4."""

    def test_a_second_run_reports_zero_reconciled_changes(self, tmp_path):
        """The reconciled half is idempotent. The seeded tree is refreshed on
        every run by design, so it is counted rather than claimed to be nothing
        (`SEED_COUNT`, round 7's N4)."""
        _init_at(tmp_path, agents=["claude"])
        plan = plan_init(project_root=tmp_path, agents=["claude"])
        counts = plan.counts()
        assert counts.get("create", 0) == 0
        assert counts.get("section", 0) == 0
        assert counts.get("overwrite", 0) == 0
        assert counts.get("remove", 0) == 0
        assert counts.get("conflict", 0) == 0

    def test_the_manifest_matches_apart_from_its_timestamp(self, tmp_path):
        import json

        manifest_path = tmp_path / ".lore" / ".install-manifest.json"
        _init_at(tmp_path, agents=["claude"])
        first = json.loads(manifest_path.read_text(encoding="utf-8"))
        _init_at(tmp_path, agents=["claude"])
        second = json.loads(manifest_path.read_text(encoding="utf-8"))
        first.pop("generated_at")
        second.pop("generated_at")
        assert first == second


class TestInterruptedRunRecovery:
    """interactive-init-us-015 — Scenario 3: the manifest is written last."""

    def test_files_written_before_a_stale_manifest_are_reconciled(self, tmp_path):
        """The manifest is written last, so the next run finds the disagreement.

        What it does about one is write: the path is Lore's either way, and the
        bytes this release wants there are the bytes that end up there — which
        is what makes an interrupted run recoverable in a single re-run.
        """
        _init_at(tmp_path, agents=["claude"])
        # Simulate a run that wrote a skill and died before the manifest.
        skill = tmp_path / ".claude" / "skills" / "store-memory" / "SKILL.md"
        recorded_bytes = skill.read_bytes()
        skill.write_text("# written by the interrupted run\n", encoding="utf-8")

        plan = plan_init(project_root=tmp_path, agents=["claude"])
        row = next(
            entry for entry in plan.files
            if entry.path == ".claude/skills/store-memory/SKILL.md"
        )
        assert row.action.value == "overwrite"
        apply_init(plan)
        assert skill.read_bytes() == recorded_bytes

        # Resolving the conflict returns the project to zero reconciled changes.
        skill.write_bytes(recorded_bytes)
        settled = plan_init(project_root=tmp_path, agents=["claude"])
        assert [entry for entry in settled.files if entry.reported] == []


class TestAFileLoreNeverInstalled:
    """interactive-init-us-015 / Tech Spec §6.5 — the FR-28 safety property."""

    def test_a_user_authored_file_at_a_desired_path_is_never_overwritten(self, tmp_path):
        target = tmp_path / ".claude" / "skills" / "store-memory" / "SKILL.md"
        target.parent.mkdir(parents=True)
        mine = b"---\nname: store-memory\n---\n\nMy own skill.\n"
        target.write_bytes(mine)
        plan, _ = _init_at(tmp_path, agents=["claude"])
        row = next(
            entry for entry in plan.files
            if entry.path == ".claude/skills/store-memory/SKILL.md"
        )
        assert row.action.value == "conflict"
        assert row.detail == "not installed by Lore"
        assert target.read_bytes() == mine

    def test_a_path_in_neither_set_is_never_touched(self, tmp_path):
        _init_at(tmp_path, agents=["claude"])
        stranger = tmp_path / ".claude" / "skills" / "my-own" / "SKILL.md"
        stranger.parent.mkdir(parents=True)
        mine = b"mine alone\n"
        stranger.write_bytes(mine)
        _init_at(tmp_path, agents=["claude"])
        assert stranger.read_bytes() == mine


class TestChangingTheAccessMode:
    """Tech Spec §2.1 — flipping --access is a clean overwrite, not a conflict."""

    def test_every_installed_skill_is_an_overwrite_not_a_conflict(self, tmp_path):
        _init_at(tmp_path, agents=["claude"], access_mode="native")
        plan = plan_init(project_root=tmp_path, agents=["claude"], access_mode="cli")
        skill_rows = [entry for entry in plan.files if entry.source.startswith("skill:")]
        assert skill_rows
        assert not [row for row in skill_rows if row.action.value == "conflict"]
        assert [row for row in skill_rows if row.action.value == "overwrite"]

    def test_an_edited_skill_is_rewritten_across_the_flip(self, tmp_path):
        _init_at(tmp_path, agents=["claude"], access_mode="native")
        edited = tmp_path / ".claude" / "skills" / "store-memory" / "SKILL.md"
        edited.write_text("# mine\n", encoding="utf-8")
        plan = plan_init(project_root=tmp_path, agents=["claude"], access_mode="cli")
        row = next(
            entry for entry in plan.files
            if entry.path == ".claude/skills/store-memory/SKILL.md"
        )
        assert row.action.value == "overwrite"


# ---------------------------------------------------------------------------
# The headless guarantees — no terminal, and the permanent `--json` exception
#
# Spec: interactive-init-us-016 Scenario 8, interactive-init-us-019 Scenario 4.
# `conceptual-workflows-lore-init` is this file's one anchor; both scenarios
# are behaviour that document describes.
# ---------------------------------------------------------------------------


class TestJsonFlagOnInitIsAcceptedAndIgnored:
    """`lore --json init` is accepted, has no effect, prints text and exits 0.

    The permanent exception recorded in `ref-lore_cli-commands`, pinned here:
    rejecting it at exit 2 the way `lore oracle` does would turn a working
    `lore --json init` in someone's CI into a hard failure that initialises
    nothing.
    """

    def test_json_flag_exits_zero_and_initialises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(main, ["--json", "init", "--yes"])
        assert result.exit_code == 0, result.output
        assert (tmp_path / ".lore" / "lore.db").is_file()

    def test_json_flag_emits_no_json_object(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(main, ["--json", "init", "--yes"])
        assert result.exit_code == 0, result.output
        with pytest.raises(ValueError):
            json.loads(result.output)
        assert "Initialized Lore project:" in result.output

    def test_json_output_matches_the_flagless_run(self, tmp_path, monkeypatch):
        plain_dir = tmp_path / "plain"
        json_dir = tmp_path / "json"
        plain_dir.mkdir()
        json_dir.mkdir()

        monkeypatch.chdir(plain_dir)
        plain = CliRunner().invoke(main, ["init", "--yes"])
        monkeypatch.chdir(json_dir)
        flagged = CliRunner().invoke(main, ["--json", "init", "--yes"])

        assert plain.exit_code == flagged.exit_code == 0
        assert plain.output == flagged.output


class TestNoTerminalMeansNoPrompt:
    """FR-9 — absence of a terminal selects defaults silently, never a hang.

    `CliRunner` gives the command a non-tty stdout, which is exactly the
    condition Realm and CI run under.
    """

    def test_no_prompt_function_is_called(self, tmp_path, monkeypatch):
        from lore import prompts

        for name in [n for n in dir(prompts) if n.startswith("ask_")]:
            monkeypatch.setattr(
                prompts,
                name,
                lambda *a, _n=name, **k: pytest.fail(f"{_n} fired without a terminal"),
            )
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(main, ["init"])
        assert result.exit_code == 0, result.output

    def test_the_default_plan_applies_with_no_summary(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(main, ["init"])
        assert result.exit_code == 0, result.output
        assert "Plan for" not in result.output
        assert "Apply this plan?" not in result.output
        assert "Initialized Lore project:" in result.output

    def test_skills_land_under_lore_and_no_instruction_file_is_written(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(main, ["init"])
        assert result.exit_code == 0, result.output
        assert (tmp_path / ".lore" / "skills").is_dir()
        assert (tmp_path / ".lore" / "LORE-AGENT.md").is_file()
        for name in ("CLAUDE.md", "AGENTS.md", "GEMINI.md", "QWEN.md"):
            assert not (tmp_path / name).exists()
        assert not (tmp_path / ".claude").exists()

    def test_a_headless_run_never_blocks_on_stdin(self, tmp_path, monkeypatch):
        """`lore init < /dev/null` completes rather than waiting for an answer."""
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(main, ["init"], input="")
        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# The regenerated known-key header (interactive-init-us-020, FR-36)
# Exercises: lore codex show conceptual-workflows-lore-init
# ---------------------------------------------------------------------------


class TestConfigHeaderRegeneration:
    """`lore init` refreshes the leading comment block and nothing else."""

    @pytest.fixture()
    def fresh_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        return tmp_path

    def test_absent_config_seeded_with_header_and_defaults(self, runner, fresh_dir):
        """Scenario 2 — header plus every known key at its default."""
        import tomllib

        from lore.config import DEFAULT_CONFIG, _FROM_TOML, load_config, render_known_keys_header

        result = runner.invoke(main, ["init", "--yes"])
        assert result.exit_code == 0, result.output

        text = (fresh_dir / ".lore" / "config.toml").read_text(encoding="utf-8")
        assert text.startswith(render_known_keys_header())
        assert set(tomllib.loads(text)) == set(_FROM_TOML)

        # Every key loads back at its default value. The families are compared
        # as a set: `lore init` rewrites that line with the answer it resolved,
        # and `skills.resolve_families` sorts what it returns.
        loaded = load_config(fresh_dir)
        assert loaded.show_glossary_on_codex_commands is DEFAULT_CONFIG.show_glossary_on_codex_commands
        assert loaded.health_report_retention == DEFAULT_CONFIG.health_report_retention
        assert loaded.init_agents == DEFAULT_CONFIG.init_agents
        assert loaded.init_access_mode == DEFAULT_CONFIG.init_access_mode
        assert loaded.init_skills_gitignore == DEFAULT_CONFIG.init_skills_gitignore
        assert sorted(loaded.init_skill_families) == sorted(
            DEFAULT_CONFIG.init_skill_families
        )

    def test_existing_config_header_regenerated_and_settings_untouched(
        self, runner, fresh_dir
    ):
        """Scenario 1 — a pre-feature config gains the keys and loses nothing."""
        from lore.config import render_known_keys_header

        target = fresh_dir / ".lore" / "config.toml"
        target.parent.mkdir(parents=True)
        body = (
            "show-glossary-on-codex-commands = false\n"
            "\n"
            'health-report-retention = "all"  # keep every report\n'
            "my-team-setting = 3\n"
        )
        target.write_text(
            "# Project-level Lore configuration.\n"
            "# Known keys (additional keys are accepted and ignored):\n"
            "#   show-glossary-on-codex-commands : bool, default true\n" + body,
            encoding="utf-8",
        )

        result = runner.invoke(main, ["init", "--yes"])
        assert result.exit_code == 0, result.output

        text = target.read_text(encoding="utf-8")
        header = render_known_keys_header()
        assert text.startswith(header)
        # Every line from the first non-comment line onward survives, in order,
        # byte-identical — the four recorded answers join them at the end.
        rest = text[len(header):]
        assert rest.startswith(body), rest
        for key in ("init-agents", "init-access-mode", "init-skill-families", "init-skills-gitignore"):
            assert f"{key} = " in rest

    def test_header_covers_every_known_key(self, runner, fresh_dir):
        """Scenario 3 — the header names exactly what the loader knows."""
        from lore.config import _FROM_TOML

        result = runner.invoke(main, ["init", "--yes"])
        assert result.exit_code == 0, result.output

        text = (fresh_dir / ".lore" / "config.toml").read_text(encoding="utf-8")
        named = {
            line[4:].split(":", 1)[0].strip()
            for line in text.splitlines()
            if line.startswith("#   ") and line[4:5] != " "
        }
        assert named == set(_FROM_TOML)

    def test_header_regeneration_is_byte_identical_on_a_second_run(
        self, runner, fresh_dir
    ):
        """Scenario 4 — regeneration is idempotent."""
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        first = (fresh_dir / ".lore" / "config.toml").read_text(encoding="utf-8")
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0
        assert (fresh_dir / ".lore" / "config.toml").read_text(encoding="utf-8") == first

    def test_headerless_config_gains_a_header_and_keeps_every_line(
        self, runner, fresh_dir
    ):
        """Scenario 5 — a prepend that loses no line."""
        from lore.config import render_known_keys_header

        target = fresh_dir / ".lore" / "config.toml"
        target.parent.mkdir(parents=True)
        body = "show-glossary-on-codex-commands = true\nmy-team-setting = 3\n"
        target.write_text(body, encoding="utf-8")

        result = runner.invoke(main, ["init", "--yes"])
        assert result.exit_code == 0, result.output

        text = target.read_text(encoding="utf-8")
        assert text.startswith(render_known_keys_header() + body)


# ---------------------------------------------------------------------------
# The database status line (interactive-init-us-022, FR-38)
# Exercises: lore codex show conceptual-workflows-lore-init
# ---------------------------------------------------------------------------


class TestDatabaseStatusMessage:
    """The created-database line names the schema version the database carries."""

    @pytest.fixture()
    def fresh_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        return tmp_path

    def test_init_reports_the_current_schema_version(self, runner, fresh_dir):
        """Scenario 1 — asserted against the constant, not against a literal."""
        from lore import db

        result = runner.invoke(main, ["init", "--yes"])
        assert result.exit_code == 0, result.output
        assert f"  Created lore.db (schema version {db.SCHEMA_VERSION})" in result.output

    def test_existing_and_corrupt_database_messages_unchanged(
        self, runner, fresh_dir
    ):
        """Scenario 2 — the other two branches are byte-identical to before."""
        assert runner.invoke(main, ["init", "--yes"]).exit_code == 0

        again = runner.invoke(main, ["init", "--yes"])
        assert again.exit_code == 0, again.output
        assert "  Skipped lore.db (already exists)" in again.output

        # Corrupt, as `init_database` defines it: a readable SQLite file with
        # no `lore_meta` table.
        db_path = fresh_dir / ".lore" / "lore.db"
        db_path.unlink()
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE stray (id INTEGER)")
        conn.commit()
        conn.close()

        corrupt = runner.invoke(main, ["init", "--yes"])
        assert corrupt.exit_code == 0, corrupt.output
        assert (
            "  Warning: Existing database appears corrupted. Reinitialized lore.db"
            in corrupt.output
        )
