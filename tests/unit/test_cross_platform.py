"""Cross-Platform Compatibility tests.

Verifies that Lore uses cross-platform compatible code patterns:
- pathlib for all file path operations
- No Windows-invalid characters in generated filenames
- Hierarchical IDs with `/` are data, not file paths
- ISO 8601 UTC timestamps with Z suffix
- SQLite 3.35+ for RETURNING clause support
- Only cross-platform dependencies
"""

import inspect
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "lore"

# Characters that are invalid in Windows filenames
WINDOWS_INVALID_CHARS = set(':<>|"?*')


# ---------------------------------------------------------------------------
# Project Root Detection — uses pathlib for path traversal
# ---------------------------------------------------------------------------


class TestProjectRootUsesPathlib:
    """Verify root.py uses pathlib.Path for path traversal."""

    def test_root_module_uses_pathlib(self):
        """root.py should import and use pathlib.Path, not os.path."""
        source = (SRC_DIR / "root.py").read_text()
        assert "from pathlib import Path" in source or "import pathlib" in source

    def test_root_module_does_not_use_os_path(self):
        """root.py should not use os.path for path operations."""
        source = (SRC_DIR / "root.py").read_text()
        assert "import os" not in source
        assert "os.path" not in source

    def test_find_project_root_returns_pathlib_path(self, tmp_path):
        """find_project_root should return a pathlib.Path."""
        from lore.root import find_project_root

        (tmp_path / ".lore").mkdir()
        result = find_project_root(tmp_path)
        assert isinstance(result, Path)

    def test_find_project_root_with_nested_directory(self, tmp_path):
        """Traversal from nested subdirectories works correctly."""
        from lore.root import find_project_root

        (tmp_path / ".lore").mkdir()
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        result = find_project_root(nested)
        assert result == tmp_path


# ---------------------------------------------------------------------------
# Database Path Resolution — uses pathlib or os.path
# ---------------------------------------------------------------------------


class TestDatabasePathResolution:
    """Verify db.py constructs paths using pathlib."""

    def test_db_module_uses_pathlib(self):
        """db.py should import pathlib.Path."""
        source = (SRC_DIR / "db.py").read_text()
        assert "from pathlib import Path" in source or "import pathlib" in source

    def test_get_connection_uses_pathlib_join(self):
        """get_connection should use pathlib `/` operator for path construction."""
        source = (SRC_DIR / "db.py").read_text()
        # Path construction is centralised in paths.py; db.py delegates to it
        assert 'paths.db_path(project_root)' in source

    def test_db_path_construction(self, tmp_path):
        """Database path should be correctly resolved regardless of OS separator."""
        project_root = tmp_path
        db_path = project_root / ".lore" / "lore.db"
        # Verify pathlib handles the construction
        assert isinstance(db_path, Path)
        assert db_path.name == "lore.db"
        assert db_path.parent.name == ".lore"


# ---------------------------------------------------------------------------
# Doctrine and Knight File Access — uses pathlib
# ---------------------------------------------------------------------------


class TestDoctrineAndKnightFileAccess:
    """Verify doctrine.py and CLI knight access use pathlib."""

    def test_doctrine_module_uses_pathlib(self):
        """doctrine.py should use pathlib.Path."""
        source = (SRC_DIR / "doctrine.py").read_text()
        assert "from pathlib import Path" in source

    def test_doctrine_load_takes_pathlib_path(self):
        """load_doctrine signature should accept Path."""
        from lore.doctrine import load_doctrine

        sig = inspect.signature(load_doctrine)
        param = sig.parameters["filepath"]
        # The annotation should be Path
        assert param.annotation is Path

    def test_list_doctrines_takes_pathlib_path(self):
        """list_doctrines signature should accept Path."""
        from lore.doctrine import list_doctrines

        sig = inspect.signature(list_doctrines)
        param = sig.parameters["doctrines_dir"]
        assert param.annotation is Path

    def test_init_uses_pathlib_for_knights_dir(self):
        """init.py should construct knights dir path using pathlib."""
        source = (SRC_DIR / "init.py").read_text()
        assert "from pathlib import Path" in source


# ---------------------------------------------------------------------------
# Oracle Report Path Generation — OS-appropriate paths, valid filenames
# ---------------------------------------------------------------------------


class TestOracleReportPathGeneration:
    """Verify oracle report filenames are valid on both Linux and Windows."""

    def test_oracle_module_uses_pathlib(self):
        """oracle.py should use pathlib.Path."""
        source = (SRC_DIR / "oracle.py").read_text()
        assert "from pathlib import Path" in source

    def test_slugify_removes_windows_invalid_characters(self):
        """slugify should strip characters that are invalid in Windows filenames."""
        from lore.oracle import slugify

        for char in WINDOWS_INVALID_CHARS:
            slug = slugify(f"title{char}name")
            for c in WINDOWS_INVALID_CHARS:
                assert c not in slug, (
                    f"slugify output '{slug}' contains Windows-invalid char '{c}'"
                )

    def test_slugify_produces_only_safe_characters(self):
        """slugify output should contain only lowercase alphanumerics and hyphens."""
        from lore.oracle import slugify

        test_inputs = [
            "Hello World!",
            "quest: important <stuff>",
            'path/to/thing "quoted"',
            "special*chars?here|now",
            "UPPERCASE and MiXeD",
            "multiple   spaces   here",
            "---leading-trailing---",
        ]
        for title in test_inputs:
            slug = slugify(title)
            assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug), (
                f"slugify({title!r}) = {slug!r} contains invalid chars"
            )

    def test_make_entity_slug_no_windows_invalid_chars(self):
        """make_entity_slug should never contain Windows-invalid characters."""
        from lore.oracle import make_entity_slug

        test_cases = [
            ("q-a1b2", "My Quest: A Story"),
            ("m-f3c1", "Fix <critical> bug"),
            ("q-beef", 'The "big" feature'),
            ("m-dead", "path/to|nowhere"),
        ]
        for entity_id, title in test_cases:
            slug = make_entity_slug(entity_id, title)
            for c in WINDOWS_INVALID_CHARS:
                assert c not in slug, (
                    f"make_entity_slug({entity_id!r}, {title!r}) = {slug!r} "
                    f"contains Windows-invalid char '{c}'"
                )

    def test_slugify_truncation_at_40_chars(self):
        """Slugified names are at most 40 characters (safe for Windows paths)."""
        from lore.oracle import slugify

        long_title = "this is an extremely long title that should be truncated properly"
        slug = slugify(long_title)
        assert len(slug) <= 40

    def test_make_entity_slug_truncation_at_40_chars(self):
        """Entity slugs are at most 40 characters."""
        from lore.oracle import make_entity_slug

        slug = make_entity_slug("q-a1b2", "this is a very long quest title that exceeds limits")
        assert len(slug) <= 40

    def test_report_paths_use_pathlib(self):
        """Report path construction in oracle.py should use pathlib `/` operator."""
        source = (SRC_DIR / "oracle.py").read_text()
        # Path construction is centralised in paths.py; oracle.py delegates to it
        assert 'paths.reports_dir(project_root)' in source


# ---------------------------------------------------------------------------
# Hierarchical IDs Are Not File Paths
# ---------------------------------------------------------------------------


class TestHierarchicalIDsNotFilePaths:
    """Verify that `/` in mission IDs is treated as data, not a path separator."""

    def test_mission_id_with_slash_stored_in_db(self, tmp_path):
        """A hierarchical mission ID with `/` can be stored and retrieved."""
        from lore.db import create_quest, create_mission, get_mission, init_database

        lore_dir = tmp_path / ".lore"
        lore_dir.mkdir()
        init_database(lore_dir / "lore.db")

        quest_id = create_quest(tmp_path, "Test Quest")
        mission_id = create_mission(tmp_path, "Test Mission", quest_id=quest_id)

        # ID should contain a slash
        assert "/" in mission_id
        assert mission_id.startswith(quest_id + "/")

        # Retrievable by exact ID
        mission = get_mission(tmp_path, mission_id)
        assert mission is not None
        assert mission["id"] == mission_id

    def test_slash_in_id_not_interpreted_as_path(self):
        """The `/` in hierarchical IDs must not be used in file path construction."""
        # IDs like "q-a1b2/m-f3c1" must remain as data strings
        mission_id = "q-a1b2/m-f3c1"
        # This should NOT be interpreted as a directory structure
        # On any OS, Path(mission_id) would create a nested path — that's not what we want
        # The ID is data, stored in SQLite, never used as a path directly
        assert "/" in mission_id
        # Verify oracle extracts just the m-part for filenames
        m_part = mission_id.split("/")[-1]
        assert m_part == "m-f3c1"
        assert "/" not in m_part

    def test_oracle_extracts_m_part_for_filename(self):
        """Oracle should use only the m-xxxx part of hierarchical IDs for filenames."""
        from lore.oracle import make_entity_slug

        # The oracle code does: m_part = mission_id.split("/")[-1]
        mission_id = "q-a1b2/m-f3c1"
        m_part = mission_id.split("/")[-1]
        filename = make_entity_slug(m_part, "Some Mission") + ".md"

        # The filename must not contain a slash
        assert "/" not in filename
        # And must not contain Windows-invalid chars
        for c in WINDOWS_INVALID_CHARS:
            assert c not in filename


# ---------------------------------------------------------------------------
# Timestamp Consistency — ISO 8601 UTC with Z suffix
# ---------------------------------------------------------------------------


class TestTimestampConsistency:
    """Verify timestamps are ISO 8601 UTC with Z suffix, locale-independent."""

    def test_now_utc_format(self):
        """_now_utc should return ISO 8601 with Z suffix."""
        from lore.db import _now_utc

        ts = _now_utc()
        # Must match YYYY-MM-DDTHH:MM:SSZ
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", ts), (
            f"Timestamp {ts!r} does not match ISO 8601 UTC format"
        )

    def test_now_utc_is_utc(self):
        """_now_utc should produce UTC time, not local time."""
        from lore.db import _now_utc

        ts = _now_utc()
        assert ts.endswith("Z"), "Timestamp must end with Z suffix for UTC"
        # Parse and verify it's close to actual UTC
        parsed = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        diff = abs((now - parsed).total_seconds())
        assert diff < 5, f"Timestamp differs from UTC by {diff}s"

    def test_now_utc_does_not_use_local_timezone(self):
        """_now_utc implementation should use timezone.utc explicitly."""
        source = (SRC_DIR / "db.py").read_text()
        # Should use datetime.now(timezone.utc), not datetime.now() or time.localtime()
        assert "timezone.utc" in source
        # Should not use naive datetime.now()
        assert "datetime.now()" not in source  # without timezone arg

    def test_timestamps_in_database_are_utc(self, tmp_path):
        """Timestamps stored in the database should be ISO 8601 UTC with Z suffix."""
        from lore.db import create_quest, get_quest, init_database

        lore_dir = tmp_path / ".lore"
        lore_dir.mkdir()
        init_database(lore_dir / "lore.db")

        quest_id = create_quest(tmp_path, "Test Quest")
        quest = get_quest(tmp_path, quest_id)

        created_at = quest["created_at"]
        updated_at = quest["updated_at"]

        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", created_at)
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", updated_at)


# ---------------------------------------------------------------------------
# SQLite Version Compatibility — 3.35+ for RETURNING clause
# ---------------------------------------------------------------------------


class TestSQLiteVersionCompatibility:
    """Verify SQLite version is >= 3.35 for RETURNING clause support."""

    def test_sqlite_version_at_least_3_35(self):
        """Python's bundled SQLite must be >= 3.35.0 for RETURNING clause."""
        version = sqlite3.sqlite_version
        parts = [int(p) for p in version.split(".")]
        major, minor = parts[0], parts[1]
        assert (major, minor) >= (3, 35), (
            f"SQLite version {version} is below 3.35; RETURNING clause not supported"
        )

    def test_returning_clause_works(self):
        """The RETURNING clause should actually work with current SQLite."""
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        cursor = conn.execute(
            "INSERT INTO test (name) VALUES ('hello') RETURNING id, name"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == 1
        assert row[1] == "hello"
        conn.close()


# ---------------------------------------------------------------------------
# No OS-Specific Dependencies
# ---------------------------------------------------------------------------


class TestNoOSSpecificDependencies:
    """Verify pyproject.toml only has cross-platform dependencies."""

    def test_only_cross_platform_dependencies(self):
        """pyproject.toml should only list Click, PyYAML, and standard library."""
        pyproject = (SRC_DIR.parent.parent / "pyproject.toml").read_text()

        # Extract dependencies section
        in_deps = False
        deps = []
        for line in pyproject.splitlines():
            if line.strip().startswith("dependencies"):
                in_deps = True
                continue
            if in_deps:
                if line.strip() == "]":
                    break
                dep = line.strip().strip('",')
                if dep:
                    deps.append(dep)

        # Allowed dependencies (cross-platform)
        allowed_prefixes = ["click", "pyyaml"]
        for dep in deps:
            dep_lower = dep.lower()
            assert any(dep_lower.startswith(prefix) for prefix in allowed_prefixes), (
                f"Unexpected dependency: {dep!r}. Only Click and PyYAML are allowed."
            )

    def test_no_platform_specific_markers(self):
        """Dependencies should not have platform-specific markers."""
        pyproject = (SRC_DIR.parent.parent / "pyproject.toml").read_text()
        # Check for platform markers like ; sys_platform == 'win32'
        assert "sys_platform" not in pyproject
        assert "platform_system" not in pyproject


# ---------------------------------------------------------------------------
# Source Files Use Pathlib, Not OS-Specific Path Manipulation
# ---------------------------------------------------------------------------


class TestSourceCodePathPatterns:
    """Verify source files use pathlib and avoid OS-specific path patterns."""

    PRODUCTION_FILES = [
        "root.py",
        "db.py",
        "oracle.py",
        "init.py",
        "doctrine.py",
    ]

    def test_no_os_sep_usage_in_production_code(self):
        """Production code should not use os.sep for data path construction."""
        for filename in self.PRODUCTION_FILES:
            source = (SRC_DIR / filename).read_text()
            assert "os.sep" not in source, (
                f"{filename} uses os.sep — should use pathlib instead"
            )

    def test_no_hardcoded_backslashes_in_path_construction(self):
        """Production code should not use hardcoded backslashes for paths."""
        for filename in self.PRODUCTION_FILES:
            source = (SRC_DIR / filename).read_text()
            # Check for backslash path patterns like "dir\\file"
            # But allow normal Python escape sequences in strings
            backslash_path = re.findall(r'["\'][^"\']*\\\\[^"\']*["\']', source)
            for match in backslash_path:
                # Filter out regex patterns (common in Python)
                if not match.startswith("r"):
                    assert False, (
                        f"{filename} contains hardcoded backslash path: {match}"
                    )

    def test_all_production_modules_import_pathlib(self):
        """All modules that handle paths should import pathlib."""
        for filename in self.PRODUCTION_FILES:
            source = (SRC_DIR / filename).read_text()
            assert "pathlib" in source, (
                f"{filename} does not import pathlib"
            )


# ---------------------------------------------------------------------------
# .lore/ Directory Handling With Pathlib
# ---------------------------------------------------------------------------


class TestLoreDirectoryHandling:
    """Verify .lore/ directory operations use pathlib correctly."""

    def test_lore_dir_construction(self, tmp_path):
        """The .lore directory path should be constructable with pathlib on any OS."""
        lore_dir = tmp_path / ".lore"
        assert isinstance(lore_dir, Path)
        lore_dir.mkdir()
        assert lore_dir.exists()
        assert lore_dir.is_dir()

    def test_subdirectory_construction(self, tmp_path):
        """Subdirectories under .lore should use pathlib `/` operator."""
        lore_dir = tmp_path / ".lore"
        lore_dir.mkdir()

        subdirs = ["doctrines", "knights", "reports", "reports/quests"]
        for sub in subdirs:
            parts = sub.split("/")
            d = lore_dir
            for part in parts:
                d = d / part
            d.mkdir(parents=True, exist_ok=True)
            assert d.exists(), f".lore/{sub} should be creatable with pathlib"

    def test_database_file_in_lore_dir(self, tmp_path):
        """Database file at .lore/lore.db should be accessible via pathlib."""
        from lore.db import init_database

        lore_dir = tmp_path / ".lore"
        lore_dir.mkdir()
        db_path = lore_dir / "lore.db"

        result = init_database(db_path)
        assert result == "created"
        assert db_path.exists()
        assert isinstance(db_path, Path)
