"""Tests for project root detection."""


import pytest

from lore.root import find_project_root, ProjectNotFoundError


class TestUpwardDirectorySearch:
    """Upward Directory Search — find .lore/ in a parent directory."""

    def test_finds_lore_in_parent(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        (project / ".lore").mkdir()
        subdir = project / "src" / "components"
        subdir.mkdir(parents=True)

        assert find_project_root(subdir) == project

    def test_finds_lore_multiple_levels_up(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        (project / ".lore").mkdir()
        deep = project / "a" / "b" / "c" / "d"
        deep.mkdir(parents=True)

        assert find_project_root(deep) == project


class TestCurrentDirectoryMatch:
    """Current Directory Match — .lore/ in CWD is found immediately."""

    def test_finds_lore_in_cwd(self, tmp_path):
        (tmp_path / ".lore").mkdir()

        assert find_project_root(tmp_path) == tmp_path


class TestNoProjectFound:
    """No Project Found — raises ProjectNotFoundError."""

    def test_raises_when_no_lore_dir(self, tmp_path):
        subdir = tmp_path / "empty" / "nested"
        subdir.mkdir(parents=True)

        with pytest.raises(ProjectNotFoundError):
            find_project_root(subdir)

    def test_error_message(self, tmp_path):
        with pytest.raises(ProjectNotFoundError, match="Not a lore project"):
            find_project_root(tmp_path)


class TestFilesystemRootBoundary:
    """Filesystem Root Boundary — search stops at /."""

    def test_stops_at_filesystem_root(self, tmp_path):
        """Search should not hang or error when walking up to /."""
        # tmp_path has no .lore/ anywhere above it
        with pytest.raises(ProjectNotFoundError):
            find_project_root(tmp_path)


class TestInitAlwaysUsesCwd:
    """Init Always Uses Current Directory — lore init creates .lore/ in CWD,
    even when a parent .lore/ already exists."""

    def test_init_creates_in_cwd_not_parent(self, tmp_path, monkeypatch):
        from click.testing import CliRunner
        from lore.cli import main

        # Create a parent project with .lore/
        parent = tmp_path / "parent"
        parent.mkdir()
        (parent / ".lore").mkdir()

        # Create a child directory (no .lore/)
        child = parent / "child"
        child.mkdir()

        # Run lore init from the child directory
        monkeypatch.chdir(child)
        runner = CliRunner()
        result = runner.invoke(main, ["init"])

        assert result.exit_code == 0
        assert (child / ".lore").is_dir()


class TestCliProjectRequired:
    """No Project Found — CLI commands (other than init) fail with
    the expected error message and exit code 1."""

    def test_dashboard_fails_without_project(self, tmp_path, monkeypatch):
        """Running `lore` (dashboard) outside a project should fail."""
        monkeypatch.chdir(tmp_path)
        from click.testing import CliRunner
        from lore.cli import main

        runner = CliRunner()
        result = runner.invoke(main, [])

        assert result.exit_code == 1
        assert 'Not a lore project (no .lore/ directory found)' in result.output
        assert 'Run "lore init" to initialize.' in result.output


class TestDefaultsToCwd:
    """find_project_root with no argument should default to CWD."""

    def test_defaults_to_cwd(self, tmp_path, monkeypatch):
        (tmp_path / ".lore").mkdir()
        monkeypatch.chdir(tmp_path)

        assert find_project_root() == tmp_path
