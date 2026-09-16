"""E2E tests for ``lore doctrine list`` and ``lore doctrine delete``.

Spec: conceptual-workflows-doctrine-list (lore codex show conceptual-workflows-doctrine-list)

The listing is unchanged by the directory model — same columns, same JSON keys,
same ``--filter`` behaviour. What changed underneath is discovery: a directory
is a doctrine iff it holds ``<name>.design.md``.
"""

import json
import shutil

from lore.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_doctrine(project_dir, stem, *, group="", design=None, missions=("recon",)):
    """Write a doctrine directory under an optional slash-delimited group."""
    base = project_dir / ".lore" / "doctrines"
    if group:
        base = base / group
    directory = base / stem
    (directory / "missions").mkdir(parents=True, exist_ok=True)
    (directory / f"{stem}.design.md").write_text(
        design
        if design is not None
        else f"---\nid: {stem}\ntitle: {stem.title()}\nsummary: A doctrine.\n---\n"
    )
    for mission_id in missions:
        (directory / "missions" / f"{mission_id}.md").write_text(
            f"---\nid: {mission_id}\ntitle: {mission_id.title()}\nsummary: s\n---\n\nBody.\n"
        )
    return directory


def _empty_doctrines_dir(project_dir):
    """Remove everything under .lore/doctrines/, leaving the directory itself."""
    doctrines_dir = project_dir / ".lore" / "doctrines"
    shutil.rmtree(doctrines_dir)
    doctrines_dir.mkdir(parents=True)
    return doctrines_dir


def _entries(result):
    return json.loads(result.output)["doctrines"]


# ---------------------------------------------------------------------------
# E27: the table
# ---------------------------------------------------------------------------


class TestDoctrineListTable:
    """One row per doctrine directory, with the columns it always had."""

    def test_every_doctrine_directory_gets_a_row(self, runner, project_dir):
        _empty_doctrines_dir(project_dir)
        _write_doctrine(project_dir, "feature-implementation", group="default")
        _write_doctrine(project_dir, "update-changelog")

        result = runner.invoke(main, ["doctrine", "list"])

        assert result.exit_code == 0, result.output
        assert "feature-implementation" in result.output
        assert "update-changelog" in result.output
        assert "[INVALID]" not in result.output

    def test_the_group_is_the_directory_chain_above_the_doctrine(
        self, runner, project_dir
    ):
        _empty_doctrines_dir(project_dir)
        _write_doctrine(project_dir, "ranker", group="seo-analysis/keyword-analysers")

        result = runner.invoke(main, ["doctrine", "list"])

        assert result.exit_code == 0, result.output
        assert "seo-analysis/keyword-analysers" in result.output

    def test_the_title_and_summary_come_from_the_design_frontmatter(
        self, runner, project_dir
    ):
        _empty_doctrines_dir(project_dir)
        _write_doctrine(
            project_dir,
            "feature-implementation",
            design=(
                "---\nid: feature-implementation\ntitle: Feature Implementation\n"
                "summary: E2E spec-driven pipeline\n---\n"
            ),
        )

        result = runner.invoke(main, ["doctrine", "list"])

        assert "Feature Implementation" in result.output
        assert "E2E spec-driven pipeline" in result.output

    def test_a_design_with_no_title_falls_back_to_the_id(self, runner, project_dir):
        _empty_doctrines_dir(project_dir)
        _write_doctrine(project_dir, "minimal", design="---\nid: minimal\n---\n")

        result = runner.invoke(main, ["doctrine", "list"])

        assert result.exit_code == 0, result.output
        assert "minimal" in result.output
        assert "[INVALID]" not in result.output

    def test_an_empty_doctrines_directory_lists_nothing(self, runner, project_dir):
        _empty_doctrines_dir(project_dir)

        result = runner.invoke(main, ["doctrine", "list"])

        assert result.exit_code == 0
        assert "No doctrines found." in result.output


class TestDoctrineListTableHeader:
    """The header columns and their order are unchanged."""

    def test_header_names_every_column(self, runner, project_dir):
        _write_doctrine(project_dir, "one")

        result = runner.invoke(main, ["doctrine", "list"])

        for column in ("ID", "GROUP", "TITLE", "SUMMARY"):
            assert column in result.output

    def test_header_columns_in_correct_order(self, runner, project_dir):
        _write_doctrine(project_dir, "one")

        result = runner.invoke(main, ["doctrine", "list"])

        header = next(line for line in result.output.split("\n") if line.strip())
        assert (
            header.index("ID")
            < header.index("GROUP")
            < header.index("TITLE")
            < header.index("SUMMARY")
        )


# ---------------------------------------------------------------------------
# What discovery skips
# ---------------------------------------------------------------------------


class TestDoctrineListDiscovery:
    """A directory is a doctrine iff it holds its own design document."""

    def test_a_directory_with_no_design_document_is_not_a_doctrine(
        self, runner, project_dir
    ):
        doctrines_dir = _empty_doctrines_dir(project_dir)
        (doctrines_dir / "grouping" / "missions").mkdir(parents=True)
        _write_doctrine(project_dir, "real")

        result = runner.invoke(main, ["doctrine", "list", "--json"])

        assert [d["id"] for d in _entries(result)] == ["real"]

    def test_a_stray_yaml_file_is_not_a_doctrine(self, runner, project_dir):
        doctrines_dir = _empty_doctrines_dir(project_dir)
        (doctrines_dir / "legacy.yaml").write_text("id: legacy\nsteps: []\n")

        result = runner.invoke(main, ["doctrine", "list", "--json"])

        assert _entries(result) == []

    def test_a_loose_design_file_outside_a_directory_is_not_a_doctrine(
        self, runner, project_dir
    ):
        doctrines_dir = _empty_doctrines_dir(project_dir)
        (doctrines_dir / "orphan.design.md").write_text("---\nid: orphan\n---\n")

        result = runner.invoke(main, ["doctrine", "list", "--json"])

        assert _entries(result) == []

    def test_a_dot_prefixed_directory_is_invisible(self, runner, project_dir):
        doctrines_dir = _empty_doctrines_dir(project_dir)
        staging = doctrines_dir / ".half-built.lore-tmp" / "half-built"
        staging.mkdir(parents=True)
        (staging / "half-built.design.md").write_text("---\nid: half-built\n---\n")

        result = runner.invoke(main, ["doctrine", "list", "--json"])

        assert _entries(result) == []


# ---------------------------------------------------------------------------
# The JSON envelope
# ---------------------------------------------------------------------------


class TestDoctrineListJson:
    """Six keys per entry, unchanged by the directory model."""

    def test_entry_shape(self, runner, project_dir):
        _empty_doctrines_dir(project_dir)
        _write_doctrine(
            project_dir,
            "feature-implementation",
            group="feature-implementation",
            design=(
                "---\nid: feature-implementation\ntitle: Feature Implementation\n"
                "summary: E2E spec-driven pipeline...\n---\n"
            ),
        )

        result = runner.invoke(main, ["doctrine", "list", "--json"])

        assert result.exit_code == 0, result.output
        assert _entries(result) == [
            {
                "id": "feature-implementation",
                "group": "feature-implementation",
                "title": "Feature Implementation",
                "summary": "E2E spec-driven pipeline...",
                "valid": True,
                # nested-projects-spec — FR-16 / D-15
                "origin": "self",
            }
        ]

    def test_entry_carries_no_internal_keys(self, runner, project_dir):
        _empty_doctrines_dir(project_dir)
        _write_doctrine(project_dir, "my-workflow")

        result = runner.invoke(main, ["doctrine", "list", "--json"])

        entry = _entries(result)[0]
        assert set(entry) == {"id", "group", "title", "summary", "valid", "origin"}
        assert "filename" not in entry
        assert "missions" not in entry

    def test_empty_directory_is_an_empty_array(self, runner, project_dir):
        _empty_doctrines_dir(project_dir)

        result = runner.invoke(main, ["doctrine", "list", "--json"])

        assert json.loads(result.output) == {"doctrines": []}

    def test_a_nested_group_is_slash_joined(self, runner, project_dir):
        _empty_doctrines_dir(project_dir)
        _write_doctrine(project_dir, "ranker", group="seo-analysis/keyword-analysers")

        result = runner.invoke(main, ["doctrine", "list", "--json"])

        entry = next(d for d in _entries(result) if d["id"] == "ranker")
        assert entry["group"] == "seo-analysis/keyword-analysers"

    def test_a_root_level_doctrine_has_a_null_group(self, runner, project_dir):
        _empty_doctrines_dir(project_dir)
        _write_doctrine(project_dir, "root-doctrine")
        _write_doctrine(project_dir, "child", group="nested/area")

        result = runner.invoke(main, ["doctrine", "list", "--json"])

        for entry in _entries(result):
            assert entry["group"] != "", f"group must never be empty string: {entry}"
            if entry["id"] == "root-doctrine":
                assert entry["group"] is None


class TestDoctrineListFilter:
    """--filter takes slash-delimited group tokens, as it always did."""

    def test_filter_keeps_only_the_named_group(self, runner, project_dir):
        _empty_doctrines_dir(project_dir)
        _write_doctrine(project_dir, "ranker", group="default/feature-implementation")
        _write_doctrine(project_dir, "other", group="ops")

        result = runner.invoke(
            main,
            ["doctrine", "list", "--json", "--filter", "default/feature-implementation"],
        )

        assert [d["id"] for d in _entries(result)] == ["ranker"]


# ---------------------------------------------------------------------------
# E28: delete soft-deletes the directory
# ---------------------------------------------------------------------------


class TestDoctrineDelete:
    """The directory is the entity, so the .deleted rename lands on it."""

    def test_delete_renames_the_directory_and_says_so(self, runner, project_dir):
        _empty_doctrines_dir(project_dir)
        directory = _write_doctrine(project_dir, "tdd-lite")

        result = runner.invoke(main, ["doctrine", "delete", "tdd-lite"])

        assert result.exit_code == 0, result.output
        assert result.stdout == "Deleted doctrine tdd-lite\n"
        assert not directory.exists()
        assert directory.with_name("tdd-lite.deleted").is_dir()

    def test_a_deleted_doctrine_leaves_the_listing(self, runner, project_dir):
        _empty_doctrines_dir(project_dir)
        _write_doctrine(project_dir, "tdd-lite")
        _write_doctrine(project_dir, "kept")

        runner.invoke(main, ["doctrine", "delete", "tdd-lite"])
        result = runner.invoke(main, ["doctrine", "list", "--json"])

        assert [d["id"] for d in _entries(result)] == ["kept"]

    def test_a_deleted_doctrine_can_no_longer_be_shown(self, runner, project_dir):
        _empty_doctrines_dir(project_dir)
        _write_doctrine(project_dir, "tdd-lite")
        runner.invoke(main, ["doctrine", "delete", "tdd-lite"])

        result = runner.invoke(main, ["doctrine", "show", "tdd-lite"])

        assert result.exit_code == 1
        assert result.stderr.strip() == "Doctrine 'tdd-lite' not found"

    def test_deleting_an_unknown_doctrine_is_refused(self, runner, project_dir):
        result = runner.invoke(main, ["doctrine", "delete", "nope"])

        assert result.exit_code == 1
        assert result.stderr.strip() == 'Doctrine "nope" not found'

    def test_delete_json_envelope(self, runner, project_dir):
        _empty_doctrines_dir(project_dir)
        _write_doctrine(project_dir, "tdd-lite")

        result = runner.invoke(main, ["--json", "doctrine", "delete", "tdd-lite"])

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == {
            "id": "tdd-lite",
            "deleted": True,
            "deleted_at": None,
        }
