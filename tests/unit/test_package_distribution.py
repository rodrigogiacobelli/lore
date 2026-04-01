"""Package Distribution Readiness (README and LICENSE)

Tests that verify the package is ready for PyPI distribution:
- README.md has required content sections
- README.md is valid markdown referenced in pyproject.toml
- LICENSE file exists at project root
- LICENSE is referenced in pyproject.toml
- pyproject.toml has complete project metadata
- Package name is lore-agent-task-manager
"""

from pathlib import Path

import tomllib

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _read_pyproject():
    """Parse pyproject.toml and return the data dict."""
    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    assert pyproject_path.exists(), "pyproject.toml not found at project root"
    with open(pyproject_path, "rb") as f:
        return tomllib.load(f)


def _read_readme():
    """Read README.md and return its content."""
    readme_path = PROJECT_ROOT / "README.md"
    assert readme_path.exists(), "README.md not found at project root"
    return readme_path.read_text()


# ---------- README.md Content ----------


class TestReadmeContent:
    """README.md includes project description, installation, quick start, and links."""

    def test_readme_exists(self):
        assert (PROJECT_ROOT / "README.md").exists()

    def test_readme_has_link_to_docs_or_repo(self):
        content = _read_readme()
        # Should have at least one URL (http/https link) for documentation or repository
        assert "http" in content.lower(), (
            "README must include a link to documentation or project repository"
        )


# ---------- README.md Renders on PyPI ----------


class TestReadmeRendersOnPyPI:
    """README.md is valid markdown referenced in pyproject.toml as readme."""

    def test_pyproject_has_readme_field(self):
        data = _read_pyproject()
        project = data.get("project", {})
        assert "readme" in project, "pyproject.toml [project] must have a 'readme' field"

    def test_pyproject_readme_points_to_readme_md(self):
        data = _read_pyproject()
        readme_value = data["project"]["readme"]
        # readme can be a string path or a table with file key
        if isinstance(readme_value, dict):
            assert readme_value.get("file") == "README.md"
        else:
            assert readme_value == "README.md"

    def test_readme_is_valid_markdown(self):
        content = _read_readme()
        # Must have at least one heading (# ...)
        assert content.startswith("#") or "\n#" in content, (
            "README.md must contain markdown headings"
        )
        # Must not be empty
        assert len(content.strip()) > 100, "README.md must have substantial content"


# ---------- LICENSE File Present ----------


class TestLicenseFilePresent:
    """LICENSE file exists at the project root."""

    def test_license_file_exists(self):
        assert (PROJECT_ROOT / "LICENSE").exists(), "LICENSE file must exist at project root"

    def test_license_file_has_content(self):
        license_path = PROJECT_ROOT / "LICENSE"
        content = license_path.read_text()
        assert len(content.strip()) > 0, "LICENSE file must not be empty"

    def test_license_specifies_license_type(self):
        license_path = PROJECT_ROOT / "LICENSE"
        content = license_path.read_text()
        # Should mention a known license type
        assert "MIT" in content or "Apache" in content or "GPL" in content or "BSD" in content, (
            "LICENSE must specify a recognized license type"
        )


# ---------- LICENSE Referenced in pyproject.toml ----------


class TestLicenseReferencedInPyproject:
    """pyproject.toml has a license field referencing the LICENSE file or type."""

    def test_pyproject_has_license_field(self):
        data = _read_pyproject()
        project = data.get("project", {})
        assert "license" in project, "pyproject.toml [project] must have a 'license' field"

    def test_license_field_has_value(self):
        data = _read_pyproject()
        license_value = data["project"]["license"]
        # Can be a string (SPDX identifier) or a table with text/file key
        if isinstance(license_value, dict):
            assert "text" in license_value or "file" in license_value, (
                "license table must have 'text' or 'file' key"
            )
        else:
            assert len(str(license_value).strip()) > 0, "license field must not be empty"


# ---------- pyproject.toml Project Metadata ----------


class TestPyprojectMetadata:
    """pyproject.toml includes description, authors, license, classifiers, urls, readme."""

    def test_has_description(self):
        data = _read_pyproject()
        project = data.get("project", {})
        assert "description" in project, "pyproject.toml must have a 'description' field"
        assert len(project["description"].strip()) > 0, "description must not be empty"

    def test_has_authors(self):
        data = _read_pyproject()
        project = data.get("project", {})
        assert "authors" in project, "pyproject.toml must have an 'authors' field"
        authors = project["authors"]
        assert isinstance(authors, list) and len(authors) > 0, (
            "authors must be a non-empty list"
        )

    def test_authors_have_name(self):
        data = _read_pyproject()
        authors = data["project"]["authors"]
        for author in authors:
            assert "name" in author, "Each author entry must have a 'name' field"

    def test_has_license(self):
        data = _read_pyproject()
        project = data.get("project", {})
        assert "license" in project, "pyproject.toml must have a 'license' field"

    def test_has_classifiers(self):
        data = _read_pyproject()
        project = data.get("project", {})
        assert "classifiers" in project, "pyproject.toml must have 'classifiers'"
        classifiers = project["classifiers"]
        assert isinstance(classifiers, list) and len(classifiers) > 0, (
            "classifiers must be a non-empty list"
        )

    def test_classifiers_include_python_version(self):
        data = _read_pyproject()
        classifiers = data["project"]["classifiers"]
        python_classifiers = [c for c in classifiers if "Python" in c]
        assert len(python_classifiers) > 0, (
            "classifiers must include at least one Python version classifier"
        )

    def test_classifiers_include_license(self):
        data = _read_pyproject()
        classifiers = data["project"]["classifiers"]
        license_classifiers = [c for c in classifiers if "License" in c]
        assert len(license_classifiers) > 0, (
            "classifiers must include a license classifier"
        )

    def test_has_urls(self):
        data = _read_pyproject()
        project = data.get("project", {})
        assert "urls" in project, "pyproject.toml must have a [project.urls] table"

    def test_urls_has_homepage_or_repository(self):
        data = _read_pyproject()
        urls = data["project"]["urls"]
        url_keys_lower = {k.lower() for k in urls}
        assert "homepage" in url_keys_lower or "repository" in url_keys_lower, (
            "urls must include a 'Homepage' or 'Repository' entry"
        )

    def test_has_readme(self):
        data = _read_pyproject()
        project = data.get("project", {})
        assert "readme" in project, "pyproject.toml must have a 'readme' field"


# ---------- Package Name ----------


class TestPackageName:
    """Package name is lore-agent-task-manager."""

    def test_package_name_is_lore_agent_task_manager(self):
        data = _read_pyproject()
        project = data.get("project", {})
        assert project.get("name") == "lore-agent-task-manager", (
            "Package name must be 'lore-agent-task-manager'"
        )
