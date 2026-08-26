"""Package Distribution Readiness (README and LICENSE)

Tests that verify the package is ready for PyPI distribution:
- README.md has required content sections
- README.md is valid markdown referenced in pyproject.toml
- LICENSE file exists at project root
- LICENSE is referenced in pyproject.toml
- pyproject.toml has complete project metadata
- Package name is lore-agent-task-manager
"""

import importlib.util
import json
import re
from importlib.metadata import version as installed_version
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


# ---------- Schema Resources Shipped in Wheel (US-001) ----------


SCHEMA_KINDS = [
    "doctrine-yaml",
    "doctrine-design-frontmatter",
    "knight-frontmatter",
    "watcher-yaml",
    "codex-frontmatter",
    "artifact-frontmatter",
]


class TestSchemaResourcesInWheel:
    """Every packaged schema YAML ships with the wheel (US-001 FR-19)."""

    def test_schema_source_directory_exists(self):
        schema_dir = PROJECT_ROOT / "src" / "lore" / "schemas"
        assert schema_dir.is_dir(), (
            "src/lore/schemas/ must exist as a Python package directory"
        )

    def test_schema_package_has_init(self):
        init = PROJECT_ROOT / "src" / "lore" / "schemas" / "__init__.py"
        assert init.exists(), "src/lore/schemas/__init__.py required for package discovery"

    def test_every_schema_yaml_present_on_disk(self):
        schema_dir = PROJECT_ROOT / "src" / "lore" / "schemas"
        for kind in SCHEMA_KINDS:
            path = schema_dir / f"{kind}.yaml"
            assert path.exists(), f"missing schema file: {path}"

    def test_importlib_resources_lists_every_schema(self):
        from importlib.resources import files

        names = {p.name for p in files("lore.schemas").iterdir()}
        for kind in SCHEMA_KINDS:
            assert f"{kind}.yaml" in names, f"{kind}.yaml not discoverable via importlib.resources"

    def test_jsonschema_is_a_runtime_dependency(self):
        data = _read_pyproject()
        deps = data.get("project", {}).get("dependencies", [])
        assert any("jsonschema" in d for d in deps), (
            "jsonschema must be declared as a runtime dependency in [project].dependencies"
        )

    def test_wheel_build_config_includes_schema_yaml(self):
        data = _read_pyproject()
        tool = data.get("tool", {}).get("hatch", {}).get("build", {})
        wheel_cfg = tool.get("targets", {}).get("wheel", {})
        # Must either include schemas via an explicit pattern, or rely on
        # force-include / artifacts / package-data covering *.yaml under lore.schemas.
        serialized = repr(wheel_cfg) + repr(tool)
        assert "schemas" in serialized or "*.yaml" in serialized or "yaml" in serialized, (
            "hatch wheel build config must ship src/lore/schemas/*.yaml "
            "(via include / artifacts / force-include / package-data)"
        )


# ---------------------------------------------------------------------------
# Runtime dependencies and packaged data files
#
# `lore init` prompts through questionary and reads three packaged data files.
# A wheel missing either fails on a fresh install rather than in CI, so both
# facts are pinned here against pyproject.toml.
# ---------------------------------------------------------------------------


EXPECTED_RUNTIME_DEPENDENCIES = {"click", "pyyaml", "jsonschema", "questionary"}

MIN_CLICK_FLOOR = (8, 3)

DEFAULTS_DIR = PROJECT_ROOT / "src" / "lore" / "defaults"
SCHEMAS_DIR = PROJECT_ROOT / "src" / "lore" / "schemas"


def _requirement_name(requirement: str) -> str:
    """Return the distribution name from a PEP 508 requirement string."""
    return re.split(r"[\s<>=!~\[;]", requirement.strip(), maxsplit=1)[0].lower()


def _requirement(name: str) -> str:
    deps = _read_pyproject()["project"]["dependencies"]
    matches = [d for d in deps if _requirement_name(d) == name]
    assert len(matches) == 1, f"expected exactly one '{name}' requirement, got {matches}"
    return matches[0]


def _version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", text))


def _wheel_artifact_patterns() -> list[str]:
    build = _read_pyproject().get("tool", {}).get("hatch", {}).get("build", {})
    return list(build.get("targets", {}).get("wheel", {}).get("artifacts", []))


def _matched_by_artifacts() -> set[Path]:
    matched: set[Path] = set()
    for pattern in _wheel_artifact_patterns():
        matched.update(p for p in PROJECT_ROOT.glob(pattern) if p.is_file())
    return matched


def _shipped_data_files() -> set[Path]:
    """Every non-Python file under the two packaged data directories."""
    found: set[Path] = set()
    for root in (DEFAULTS_DIR, SCHEMAS_DIR):
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix == ".py" or "__pycache__" in path.parts:
                continue
            found.add(path)
    return found


class TestRuntimeDependencies:
    def test_declares_exactly_the_four_runtime_dependencies(self):
        deps = _read_pyproject()["project"]["dependencies"]
        assert {_requirement_name(d) for d in deps} == EXPECTED_RUNTIME_DEPENDENCIES

    def test_questionary_is_a_hard_dependency_not_an_extra(self):
        assert "questionary" in _requirement("questionary")
        optional = _read_pyproject()["project"].get("optional-dependencies", {})
        for extra, requirements in optional.items():
            names = {_requirement_name(r) for r in requirements}
            assert "questionary" not in names, (
                f"questionary must not be optional; it appears in extra '{extra}'"
            )

    def test_questionary_specifier_is_the_verified_range(self):
        requirement = _requirement("questionary")
        assert ">=2.0" in requirement
        assert "<3.0" in requirement


class TestClickFloorProtectsTheParserHook:
    def test_floor_is_at_least_the_verified_minor(self):
        requirement = _requirement("click")
        lower = re.search(r">=\s*([0-9][0-9.]*)", requirement)
        assert lower, f"click requirement declares no lower bound: {requirement}"
        assert _version_tuple(lower.group(1))[:2] >= MIN_CLICK_FLOOR, (
            "the space-separated option parser reaches Click parser internals verified "
            f"on {MIN_CLICK_FLOOR[0]}.{MIN_CLICK_FLOOR[1]} and above"
        )

    def test_upper_bound_stays_below_the_next_major(self):
        assert "<9.0" in _requirement("click")

    def test_declared_floor_is_not_below_the_installed_click(self):
        requirement = _requirement("click")
        lower = re.search(r">=\s*([0-9][0-9.]*)", requirement).group(1)
        assert _version_tuple(lower)[:2] <= _version_tuple(installed_version("click"))[:2], (
            "the declared floor must not sit above the Click the suite exercises"
        )

    def test_installed_click_satisfies_the_declared_specifier(self):
        installed = _version_tuple(installed_version("click"))
        assert (8, 3) <= installed[:2] < (9, 0)


class TestWheelCarriesEveryPackagedDataFile:
    def test_no_artifact_pattern_names_a_missing_path(self):
        for pattern in _wheel_artifact_patterns():
            assert any(PROJECT_ROOT.glob(pattern)), (
                f"wheel artifacts pattern '{pattern}' matches nothing on disk"
            )

    def test_no_artifact_pattern_names_the_retired_agents_md(self):
        assert not any("defaults/AGENTS.md" in p for p in _wheel_artifact_patterns())

    def test_every_packaged_data_file_is_covered_by_a_pattern(self):
        uncovered = sorted(
            str(p.relative_to(PROJECT_ROOT)) for p in _shipped_data_files() - _matched_by_artifacts()
        )
        assert uncovered == [], (
            f"these packaged data files ride in no wheel artifacts pattern: {uncovered}"
        )

    def test_the_defaults_tree_is_covered_recursively(self):
        matched = _matched_by_artifacts()
        nested = [p for p in _shipped_data_files() if p.is_relative_to(DEFAULTS_DIR) and p.parent != DEFAULTS_DIR]
        assert nested, "expected nested files under src/lore/defaults/"
        assert all(p in matched for p in nested)

    def test_the_wheel_still_packages_the_lore_source_tree(self):
        build = _read_pyproject()["tool"]["hatch"]["build"]["targets"]["wheel"]
        assert build["packages"] == ["src/lore"]


class TestReleaseMetadata:
    def test_version_is_the_minor_bump(self):
        assert _read_pyproject()["project"]["version"] == "0.10.0"

    def test_requires_python_is_unchanged(self):
        assert _read_pyproject()["project"]["requires-python"] == ">=3.11"

    def test_classifiers_still_name_both_supported_minors(self):
        classifiers = _read_pyproject()["project"]["classifiers"]
        assert "Programming Language :: Python :: 3.11" in classifiers
        assert "Programming Language :: Python :: 3.12" in classifiers


# ---------------------------------------------------------------------------
# Historical skill hashes
#
# `src/lore/defaults/legacy-hashes.json` lets a project that predates the
# install manifest still be reconciled: a file under `.lore/skills/` whose
# bytes match a hash Lore has shipped for that path is a file Lore installed
# and nobody edited. The file is packaged data, so ADR 006 applies — these
# assertions cover existence, parseability and shape, never a hash value.
#
# `scripts/update_legacy_hashes.py` regenerates it as a release pre-flight
# step. It unions; it never removes a row, because a project may hop several
# releases at once and needs every intermediate hash.
# ---------------------------------------------------------------------------


LEGACY_HASHES = DEFAULTS_DIR / "legacy-hashes.json"
UPDATE_SCRIPT = PROJECT_ROOT / "scripts" / "update_legacy_hashes.py"


def _load_update_script():
    """Import the release script by path — `scripts/` is not an installed package."""
    spec = importlib.util.spec_from_file_location("update_legacy_hashes", UPDATE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _skill_tree(root: Path, files: dict[str, str]) -> Path:
    skills = root / "skills"
    for relative, body in files.items():
        target = skills / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)
    return skills


class TestShippedLegacyHashes:
    def test_the_file_exists(self):
        assert LEGACY_HASHES.is_file()

    def test_the_file_parses_as_json(self):
        json.loads(LEGACY_HASHES.read_text(encoding="utf-8"))

    def test_it_declares_its_format_version(self):
        payload = json.loads(LEGACY_HASHES.read_text(encoding="utf-8"))
        assert isinstance(payload.get("legacy_hashes_version"), int)

    def test_files_is_an_object(self):
        payload = json.loads(LEGACY_HASHES.read_text(encoding="utf-8"))
        assert isinstance(payload.get("files"), dict)

    def test_every_row_is_a_non_empty_list_of_prefixed_digests(self):
        payload = json.loads(LEGACY_HASHES.read_text(encoding="utf-8"))
        for path, hashes in payload["files"].items():
            assert isinstance(hashes, list) and hashes, f"{path} carries no hashes"
            assert all(isinstance(h, str) and h.startswith("sha256:") for h in hashes), path

    def test_every_key_is_a_path_lore_installed_to(self):
        # The skills tree, plus the fixed paths outside it that every
        # pre-manifest release also wrote. Nothing else: a key the walk never
        # visits is a row that can never match anything.
        from lore import reconcile

        payload = json.loads(LEGACY_HASHES.read_text(encoding="utf-8"))
        allowed = set(reconcile.LEGACY_FIXED_PATHS)
        assert all(
            key.startswith(".lore/skills/") or key in allowed
            for key in payload["files"]
        )

    def test_it_carries_the_generated_files_the_hand_copy_era_produced(self):
        """The two rows the generator does not write, and must not lose.

        Both were copied verbatim by every release up to 0.9.0 and are rendered
        per project from 0.10.0, so they are historical-only. Without them the
        listing that the pre-feature `GETTING-STARTED.md` told people to copy
        into `.claude/skills/` reads as the user's own file and survives an
        upgrade pointing at deleted directories, and the agent doc goes on
        advertising skills the same run removed.
        """
        payload = json.loads(LEGACY_HASHES.read_text(encoding="utf-8"))
        assert payload["files"].get(".lore/skills/.gitignore")
        assert payload["files"].get(".lore/LORE-AGENT.md")

    def test_it_rides_in_the_wheel(self):
        assert LEGACY_HASHES in _matched_by_artifacts()

    def test_it_recognises_every_file_this_release_installs(self):
        """The release pre-flight, asserted rather than remembered.

        A project that commits its skills and gitignores its manifest is
        reconciled from this table on every fresh clone. A skill edited without
        re-running the script leaves that clone unable to recognise the file it
        installed itself, so it can never take an upgrade.
        """
        from lore import skills as skills_module
        from lore.initplan import AccessMode
        from lore.manifest import bytes_digest

        table = json.loads(LEGACY_HASHES.read_text(encoding="utf-8"))["files"]
        missing = []
        for mode in AccessMode:
            desired = skills_module.desired_files(
                targets=(),
                skill_families=skills_module.family_ids(),
                access_mode=mode,
            )
            missing += [
                f"{path} ({mode.value})"
                for path, entry in sorted(desired.items())
                if bytes_digest(entry.content) not in table.get(path, [])
            ]
        assert missing == [], (
            "run `python scripts/update_legacy_hashes.py` — these installed "
            f"files match no shipped hash: {missing}"
        )


class TestUpdateLegacyHashesScript:
    def test_the_script_exists(self):
        assert UPDATE_SCRIPT.is_file()

    def test_it_records_every_file_prefixed_with_the_legacy_skills_root(self, tmp_path):
        script = _load_update_script()
        skills = _skill_tree(tmp_path, {"demo/SKILL.md": "body\n", "demo/references/r.md": "ref\n"})
        target = tmp_path / "legacy-hashes.json"

        script.update(skills, target)

        payload = json.loads(target.read_text(encoding="utf-8"))
        assert set(payload["files"]) == {
            ".lore/skills/demo/SKILL.md",
            ".lore/skills/demo/references/r.md",
        }

    def test_the_recorded_digest_matches_the_shared_hash_function(self, tmp_path):
        from lore.manifest import bytes_digest

        script = _load_update_script()
        skills = _skill_tree(tmp_path, {"demo/SKILL.md": "body\n"})
        target = tmp_path / "legacy-hashes.json"

        script.update(skills, target)

        payload = json.loads(target.read_text(encoding="utf-8"))
        assert payload["files"][".lore/skills/demo/SKILL.md"] == [bytes_digest(b"body\n")]

    def test_it_never_removes_an_existing_row(self, tmp_path):
        script = _load_update_script()
        skills = _skill_tree(tmp_path, {"demo/SKILL.md": "body\n"})
        target = tmp_path / "legacy-hashes.json"
        target.write_text(
            json.dumps(
                {
                    "legacy_hashes_version": 1,
                    "files": {".lore/skills/retired/SKILL.md": ["sha256:kept"]},
                }
            )
        )

        script.update(skills, target)

        payload = json.loads(target.read_text(encoding="utf-8"))
        assert payload["files"][".lore/skills/retired/SKILL.md"] == ["sha256:kept"]

    def test_it_unions_a_new_digest_onto_an_existing_row(self, tmp_path):
        script = _load_update_script()
        skills = _skill_tree(tmp_path, {"demo/SKILL.md": "rewritten\n"})
        target = tmp_path / "legacy-hashes.json"
        target.write_text(
            json.dumps(
                {
                    "legacy_hashes_version": 1,
                    "files": {".lore/skills/demo/SKILL.md": ["sha256:previous"]},
                }
            )
        )

        script.update(skills, target)

        payload = json.loads(target.read_text(encoding="utf-8"))
        assert "sha256:previous" in payload["files"][".lore/skills/demo/SKILL.md"]
        assert len(payload["files"][".lore/skills/demo/SKILL.md"]) == 2

    def test_it_is_idempotent_on_an_unchanged_tree(self, tmp_path):
        script = _load_update_script()
        skills = _skill_tree(tmp_path, {"b/SKILL.md": "b\n", "a/SKILL.md": "a\n"})
        target = tmp_path / "legacy-hashes.json"

        script.update(skills, target)
        first = target.read_bytes()
        script.update(skills, target)

        assert target.read_bytes() == first

    def test_it_skips_the_generated_skills_gitignore(self, tmp_path):
        script = _load_update_script()
        skills = _skill_tree(tmp_path, {"demo/SKILL.md": "body\n", ".gitignore": "demo/\n"})
        target = tmp_path / "legacy-hashes.json"

        script.update(skills, target)

        payload = json.loads(target.read_text(encoding="utf-8"))
        assert ".lore/skills/.gitignore" not in payload["files"]

    def test_it_starts_a_file_that_does_not_exist_yet(self, tmp_path):
        script = _load_update_script()
        skills = _skill_tree(tmp_path, {"demo/SKILL.md": "body\n"})
        target = tmp_path / "nested" / "legacy-hashes.json"

        script.update(skills, target)

        assert json.loads(target.read_text(encoding="utf-8"))["legacy_hashes_version"] == 1

    def test_it_records_the_bytes_that_get_installed_not_the_raw_source(self, tmp_path):
        """An installed skill is rendered for its access mode; the raw file never lands.

        A `--skills-gitignore none` project commits its skills and gitignores
        the manifest, so a fresh clone always reconciles through this table. A
        row holding only the unrendered source matches nothing it ever wrote.
        """
        from lore.initplan import AccessMode
        from lore.manifest import bytes_digest
        from lore.skills import render

        source = (
            "# demo\n"
            "<!-- lore:access native -->\nuse your own tools\n<!-- lore:access end -->\n"
            "<!-- lore:access cli -->\nuse `lore ...`\n<!-- lore:access end -->\n"
        )
        script = _load_update_script()
        skills = _skill_tree(tmp_path, {"demo/SKILL.md": source})
        target = tmp_path / "legacy-hashes.json"

        script.update(skills, target)

        recorded = json.loads(target.read_text(encoding="utf-8"))["files"][
            ".lore/skills/demo/SKILL.md"
        ]
        for mode in AccessMode:
            rendered = bytes_digest(render(source, mode).encode("utf-8"))
            assert rendered in recorded, f"{mode} is unrecognisable to the fallback"
        assert bytes_digest(source.encode("utf-8")) not in recorded

    def test_a_file_with_no_access_blocks_records_one_digest(self, tmp_path):
        """Both modes render it identically, so the row does not grow a duplicate."""
        from lore.manifest import bytes_digest

        script = _load_update_script()
        skills = _skill_tree(tmp_path, {"demo/SKILL.md": "body\n"})
        target = tmp_path / "legacy-hashes.json"

        script.update(skills, target)

        payload = json.loads(target.read_text(encoding="utf-8"))
        assert payload["files"][".lore/skills/demo/SKILL.md"] == [bytes_digest(b"body\n")]

    def test_it_stays_idempotent_on_a_tree_with_access_blocks(self, tmp_path):
        script = _load_update_script()
        skills = _skill_tree(
            tmp_path,
            {"demo/SKILL.md": "<!-- lore:access cli -->\nx\n<!-- lore:access end -->\n"},
        )
        target = tmp_path / "legacy-hashes.json"

        script.update(skills, target)
        first = target.read_bytes()
        script.update(skills, target)

        assert target.read_bytes() == first

    def test_main_defaults_to_the_packaged_locations(self, tmp_path, monkeypatch):
        script = _load_update_script()
        written: list[tuple[Path, Path]] = []
        monkeypatch.setattr(script, "update", lambda skills, target: written.append((skills, target)))

        assert script.main([]) == 0
        assert written == [(script.DEFAULT_SKILLS_DIR, script.DEFAULT_TARGET)]


# ---------- CHANGELOG.md and the declared version ----------


class TestChangelogVersion:
    """interactive-init-us-023 — the changelog and `pyproject.toml` agree.

    ADR-010's Consequences require `CHANGELOG.md` and `lore.api.__all__` to move
    together; a release whose top-most section names a different version than
    the package declares is the drift that requirement exists to catch.
    """

    @staticmethod
    def _released_headings() -> list[str]:
        text = (PROJECT_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        return [
            line[3:].strip()
            for line in text.splitlines()
            if line.startswith("## ") and not line[3:].strip().startswith("[Unreleased]")
        ]

    def test_changelog_top_version_matches_pyproject(self):
        version = _read_pyproject()["project"]["version"]
        heading = self._released_headings()[0]
        assert re.match(r"^\[" + re.escape(version) + r"\]", heading), (
            f"CHANGELOG.md's top released section is {heading!r}; "
            f"pyproject.toml declares {version!r}"
        )

    def test_changelog_still_carries_an_unreleased_section(self):
        text = (PROJECT_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        assert "## [Unreleased]" in text
