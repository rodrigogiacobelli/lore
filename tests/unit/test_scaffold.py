"""Smoke tests for package scaffolding and pip installation, plus doctrine scaffold unit tests."""

import subprocess
import sys
from pathlib import Path



ROOT = Path(__file__).resolve().parent.parent.parent


class TestPackageStructure:
    """Verify src-layout and required files exist."""

    def test_pyproject_toml_exists(self):
        assert (ROOT / "pyproject.toml").is_file()

    def test_readme_exists(self):
        assert (ROOT / "README.md").is_file()

    def test_license_exists(self):
        assert (ROOT / "LICENSE").is_file()

    def test_init_py_exists(self):
        assert (ROOT / "src" / "lore" / "__init__.py").is_file()

    def test_main_py_exists(self):
        assert (ROOT / "src" / "lore" / "__main__.py").is_file()

    def test_cli_py_exists(self):
        assert (ROOT / "src" / "lore" / "cli.py").is_file()

    def test_module_stubs_exist(self):
        for module in ("db.py", "models.py", "ids.py", "priority.py"):
            assert (ROOT / "src" / "lore" / module).is_file(), f"Missing {module}"

    def test_migrations_directory_exists(self):
        assert (ROOT / "src" / "lore" / "migrations").is_dir()

    def test_defaults_bundled(self):
        defaults = ROOT / "src" / "lore" / "defaults"
        assert (defaults / "LORE-AGENT.md").is_file()
        assert (defaults / "gitignore").is_file()
        assert (defaults / "schema.sql").is_file()
        assert any((defaults / "doctrines").rglob("*.yaml"))
        assert any((defaults / "knights").rglob("*.md"))


class TestPyprojectToml:
    """Verify pyproject.toml declares the right metadata."""

    def test_pyyaml_dependency(self):
        content = (ROOT / "pyproject.toml").read_text()
        assert "pyyaml" in content.lower()


class TestVersionFlag:
    """Verify --version works."""

    def test_version_importable(self):
        from lore import __version__
        assert __version__  # non-empty string

    def test_version_matches_pyproject(self):
        from lore import __version__
        content = (ROOT / "pyproject.toml").read_text()
        assert __version__ in content

    def test_lore_version_cli(self):
        result = subprocess.run(
            [sys.executable, "-m", "lore", "--version"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        from lore import __version__
        assert __version__ in result.stdout


class TestCLIEntryPoint:
    """Verify CLI responds to --help."""

    def test_help_flag(self):
        result = subprocess.run(
            [sys.executable, "-m", "lore", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "lore" in result.stdout.lower()


class TestModuleInvocation:
    """Verify python -m lore works identically."""

    def test_module_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "lore", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "lore" in result.stdout.lower()


# ---------------------------------------------------------------------------
# Doctrine scaffold unit tests (US-1)
# ---------------------------------------------------------------------------


class TestScaffoldDoctrine:
    # Ref: conceptual-workflows-doctrine-new step 3 (scaffold_doctrine() function)

    def test_scaffold_doctrine_returns_valid_yaml(self):
        # Ref: list-enrichment-gaps-tech-spec — scaffold must pass yaml.safe_load
        import yaml
        from lore.doctrine import scaffold_doctrine
        result = scaffold_doctrine("hotfix")
        data = yaml.safe_load(result)
        assert isinstance(data, dict)

    def test_scaffold_doctrine_id_equals_name(self):
        # Ref: conceptual-workflows-doctrine-new step 3 (id field = name argument — hard constraint)
        import yaml
        from lore.doctrine import scaffold_doctrine
        result = scaffold_doctrine("hotfix")
        data = yaml.safe_load(result)
        assert data["id"] == "hotfix"

    def test_scaffold_doctrine_title_is_capitalized(self):
        # Ref: list-enrichment-gaps-tech-spec — title = name.capitalize()
        import yaml
        from lore.doctrine import scaffold_doctrine
        result = scaffold_doctrine("hotfix")
        data = yaml.safe_load(result)
        assert data["title"] == "hotfix".capitalize()

    def test_scaffold_doctrine_summary_present_and_nonempty(self):
        # Ref: list-enrichment-gaps-tech-spec — summary placeholder is non-empty
        import yaml
        from lore.doctrine import scaffold_doctrine
        result = scaffold_doctrine("hotfix")
        data = yaml.safe_load(result)
        assert "summary" in data
        assert data["summary"]

    def test_scaffold_doctrine_description_present_and_nonempty(self):
        # Ref: list-enrichment-gaps-tech-spec — description placeholder is non-empty
        import yaml
        from lore.doctrine import scaffold_doctrine
        result = scaffold_doctrine("hotfix")
        data = yaml.safe_load(result)
        assert "description" in data
        assert data["description"]

    def test_scaffold_doctrine_steps_is_nonempty_list(self):
        # Ref: list-enrichment-gaps-tech-spec — steps has one example step
        import yaml
        from lore.doctrine import scaffold_doctrine
        result = scaffold_doctrine("hotfix")
        data = yaml.safe_load(result)
        assert isinstance(data["steps"], list)
        assert len(data["steps"]) > 0

    def test_scaffold_doctrine_step_has_name_and_description(self):
        # Ref: list-enrichment-gaps-tech-spec — each step has name and description keys
        import yaml
        from lore.doctrine import scaffold_doctrine
        result = scaffold_doctrine("hotfix")
        data = yaml.safe_load(result)
        for step in data["steps"]:
            assert "name" in step
            assert "description" in step
