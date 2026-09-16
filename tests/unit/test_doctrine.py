"""Unit tests for doctrine discovery, reading and reference resolution.

Workflow: conceptual-workflows-doctrine-list (lore codex show conceptual-workflows-doctrine-list)
Workflow: conceptual-workflows-doctrine-show

A doctrine is a directory: ``D`` is one iff ``D/<D.name>.design.md`` exists, and
its missions are the ``.md`` files under ``D/missions/``. Nothing here parses a
step, a phase or a dependency — Lore reads frontmatter for identity and treats
every body as an opaque string.
"""

from pathlib import Path

import pytest

from lore import doctrine as doctrine_module
from lore.doctrine import (
    _find_doctrine_dir,
    _doctrine_mission_stem,
    _resolve_doctrine_mission,
    list_doctrines,
    load_mission_sources,
    read_doctrine,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


DESIGN = "---\nid: {stem}\ntitle: {title}\nsummary: {summary}\n---\n\n# {stem}\n"
MISSION = "---\nid: {mid}\ntitle: {title}\nsummary: {summary}\n---\n\n# {title}\n\nBody of {mid}.\n"


def _design(stem: str, *, title: str | None = None, summary: str = "A doctrine.") -> str:
    return DESIGN.format(stem=stem, title=title if title is not None else stem, summary=summary)


def _mission(mid: str, *, title: str | None = None, summary: str = "A mission.") -> str:
    return MISSION.format(
        mid=mid, title=title if title is not None else mid, summary=summary
    )


def _make_doctrine(
    doctrines_dir: Path,
    stem: str,
    *,
    group: str = "",
    missions: tuple[str, ...] = ("recon",),
    design: str | None = None,
    dirname: str | None = None,
) -> Path:
    """Write a doctrine directory and return it."""
    base = doctrines_dir / group if group else doctrines_dir
    directory = base / (dirname if dirname is not None else stem)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{directory.name}.design.md").write_text(
        design if design is not None else _design(stem)
    )
    for mission_id in missions:
        missions_dir = directory / "missions"
        missions_dir.mkdir(parents=True, exist_ok=True)
        (missions_dir / f"{mission_id}.md").write_text(_mission(mission_id))
    return directory


@pytest.fixture()
def doctrines_dir(tmp_path):
    target = tmp_path / ".lore" / "doctrines"
    target.mkdir(parents=True)
    return target


# ---------------------------------------------------------------------------
# list_doctrines — discovery is directory identity
# ---------------------------------------------------------------------------


def test_a_directory_with_its_design_file_is_listed(tmp_path, doctrines_dir):
    _make_doctrine(doctrines_dir, "tdd-lite")

    records = list_doctrines(tmp_path)

    assert [r["id"] for r in records] == ["tdd-lite"]


def test_a_directory_without_a_design_file_is_not_listed(tmp_path, doctrines_dir):
    (doctrines_dir / "tdd-lite" / "missions").mkdir(parents=True)
    (doctrines_dir / "tdd-lite" / "missions" / "recon.md").write_text(_mission("recon"))

    assert list_doctrines(tmp_path) == []


def test_a_design_file_whose_stem_is_not_its_directory_is_not_a_doctrine(
    tmp_path, doctrines_dir
):
    directory = doctrines_dir / "tdd-lite"
    directory.mkdir(parents=True)
    (directory / "something-else.design.md").write_text(_design("something-else"))

    assert list_doctrines(tmp_path) == []


def test_an_empty_doctrines_dir_returns_an_empty_list(tmp_path, doctrines_dir):
    assert list_doctrines(tmp_path) == []


def test_a_missing_doctrines_dir_returns_an_empty_list(tmp_path):
    assert list_doctrines(tmp_path) == []


def test_a_dot_prefixed_directory_is_invisible(tmp_path, doctrines_dir):
    _make_doctrine(doctrines_dir, "tdd-lite", dirname=".tdd-lite.lore-tmp")

    assert list_doctrines(tmp_path) == []


def test_a_deleted_directory_is_invisible(tmp_path, doctrines_dir):
    _make_doctrine(doctrines_dir, "tdd-lite", dirname="tdd-lite.deleted")

    assert list_doctrines(tmp_path) == []


def test_a_deleted_group_segment_hides_everything_below_it(tmp_path, doctrines_dir):
    _make_doctrine(doctrines_dir, "tdd-lite", group="old.deleted")

    assert list_doctrines(tmp_path) == []


def test_a_design_file_with_no_id_frontmatter_is_skipped(tmp_path, doctrines_dir):
    _make_doctrine(
        doctrines_dir, "tdd-lite", design="---\ntitle: No Id\n---\n\nBody.\n"
    )

    assert list_doctrines(tmp_path) == []


def test_the_group_is_derived_from_the_directorys_parent_chain(tmp_path, doctrines_dir):
    _make_doctrine(doctrines_dir, "tdd", group="default/feature-implementation")

    assert list_doctrines(tmp_path)[0]["group"] == "default/feature-implementation"


def test_the_group_is_empty_for_a_doctrine_at_the_root(tmp_path, doctrines_dir):
    _make_doctrine(doctrines_dir, "tdd-lite")

    assert list_doctrines(tmp_path)[0]["group"] == ""


def test_filename_is_the_design_documents_name(tmp_path, doctrines_dir):
    _make_doctrine(doctrines_dir, "tdd-lite")

    assert list_doctrines(tmp_path)[0]["filename"] == "tdd-lite.design.md"


def test_a_record_carries_exactly_the_documented_keys(tmp_path, doctrines_dir):
    _make_doctrine(doctrines_dir, "tdd-lite")

    assert set(list_doctrines(tmp_path)[0]) == {
        "id",
        "group",
        "title",
        "summary",
        "valid",
        "filename",
        "origin",
    }


def test_title_falls_back_to_the_id(tmp_path, doctrines_dir):
    _make_doctrine(
        doctrines_dir,
        "tdd-lite",
        design="---\nid: tdd-lite\nsummary: A doctrine.\n---\n\nBody.\n",
    )

    assert list_doctrines(tmp_path)[0]["title"] == "tdd-lite"


def test_summary_falls_back_to_the_empty_string(tmp_path, doctrines_dir):
    _make_doctrine(
        doctrines_dir,
        "tdd-lite",
        design="---\nid: tdd-lite\ntitle: TDD Lite\n---\n\nBody.\n",
    )

    assert list_doctrines(tmp_path)[0]["summary"] == ""


def test_valid_is_true_on_every_record(tmp_path, doctrines_dir):
    _make_doctrine(doctrines_dir, "one")
    _make_doctrine(doctrines_dir, "two")

    assert [r["valid"] for r in list_doctrines(tmp_path)] == [True, True]


def test_a_doctrine_with_no_missions_directory_is_still_listed(tmp_path, doctrines_dir):
    _make_doctrine(doctrines_dir, "solo", missions=())

    assert [r["id"] for r in list_doctrines(tmp_path)] == ["solo"]


def test_filter_groups_selects_by_segment_prefix(tmp_path, doctrines_dir):
    _make_doctrine(doctrines_dir, "kept", group="ops/release")
    _make_doctrine(doctrines_dir, "dropped", group="other")

    assert [r["id"] for r in list_doctrines(tmp_path, ["ops"])] == ["kept"]


# ---------------------------------------------------------------------------
# read_doctrine — the design document plus the mission index
# ---------------------------------------------------------------------------


def test_read_doctrine_returns_the_documented_keys(tmp_path, doctrines_dir):
    _make_doctrine(doctrines_dir, "tdd-lite")

    record = read_doctrine(tmp_path, "tdd-lite")

    assert set(record) == {"id", "title", "summary", "design", "missions", "origin"}


def test_read_doctrine_returns_the_whole_design_file_text(tmp_path, doctrines_dir):
    directory = _make_doctrine(doctrines_dir, "tdd-lite")

    record = read_doctrine(tmp_path, "tdd-lite")

    assert record["design"] == (directory / "tdd-lite.design.md").read_text()
    assert record["design"].startswith("---\n")


def test_read_doctrine_indexes_missions_sorted_by_id(tmp_path, doctrines_dir):
    _make_doctrine(doctrines_dir, "tdd-lite", missions=("scribe", "recon", "feature-spec"))

    record = read_doctrine(tmp_path, "tdd-lite")

    assert [m["id"] for m in record["missions"]] == ["feature-spec", "recon", "scribe"]
    assert set(record["missions"][0]) == {"id", "title", "summary"}


def test_read_doctrine_returns_an_empty_index_with_no_missions_dir(
    tmp_path, doctrines_dir
):
    _make_doctrine(doctrines_dir, "solo", missions=())

    assert read_doctrine(tmp_path, "solo")["missions"] == []


def test_read_doctrine_returns_none_for_an_unknown_doctrine(tmp_path, doctrines_dir):
    assert read_doctrine(tmp_path, "nope") is None


def test_read_doctrine_carries_no_raw_yaml_or_steps_key(tmp_path, doctrines_dir):
    _make_doctrine(doctrines_dir, "tdd-lite")

    record = read_doctrine(tmp_path, "tdd-lite")

    assert "raw_yaml" not in record
    assert "steps" not in record


def test_read_doctrine_with_a_mission_returns_its_stripped_body(tmp_path, doctrines_dir):
    _make_doctrine(doctrines_dir, "tdd-lite")

    record = read_doctrine(tmp_path, "tdd-lite", mission="recon")

    assert record["mission"]["id"] == "recon"
    assert record["mission"]["title"] == "recon"
    assert record["mission"]["body"] == "# recon\n\nBody of recon.\n"
    assert not record["mission"]["body"].startswith("---")


def test_read_doctrine_with_a_missing_mission_carries_a_null_mission(
    tmp_path, doctrines_dir
):
    _make_doctrine(doctrines_dir, "tdd-lite")

    record = read_doctrine(tmp_path, "tdd-lite", mission="nope")

    assert record is not None
    assert record["mission"] is None
    assert record["id"] == "tdd-lite"


def test_read_doctrine_with_a_mission_on_an_unknown_doctrine_returns_none(
    tmp_path, doctrines_dir
):
    assert read_doctrine(tmp_path, "nope", mission="recon") is None


def test_read_doctrine_has_no_mission_key_when_mission_is_not_asked_for(
    tmp_path, doctrines_dir
):
    _make_doctrine(doctrines_dir, "tdd-lite")

    assert "mission" not in read_doctrine(tmp_path, "tdd-lite")


@pytest.mark.parametrize("bad", ["a/b", "a\\b", "../etc/passwd"])
def test_read_doctrine_rejects_a_mission_id_with_a_path_separator(
    tmp_path, doctrines_dir, bad
):
    _make_doctrine(doctrines_dir, "tdd-lite")

    with pytest.raises(ValueError) as excinfo:
        read_doctrine(tmp_path, "tdd-lite", mission=bad)

    assert str(excinfo.value) == "Invalid mission id: path separators not allowed"


def test_a_soft_deleted_mission_is_neither_indexed_nor_readable(tmp_path, doctrines_dir):
    directory = _make_doctrine(doctrines_dir, "tdd-lite", missions=("recon", "lint"))
    lint = directory / "missions" / "lint.md"
    lint.rename(lint.with_name("lint.md.deleted"))

    record = read_doctrine(tmp_path, "tdd-lite", mission="lint")

    assert [m["id"] for m in record["missions"]] == ["recon"]
    assert record["mission"] is None


def test_a_mission_title_falls_back_to_its_id(tmp_path, doctrines_dir):
    directory = _make_doctrine(doctrines_dir, "tdd-lite", missions=())
    (directory / "missions").mkdir()
    (directory / "missions" / "recon.md").write_text("---\nid: recon\n---\n\nBody.\n")

    record = read_doctrine(tmp_path, "tdd-lite")

    assert record["missions"] == [{"id": "recon", "title": "recon", "summary": ""}]


def test_a_mission_index_entry_is_keyed_on_the_filename_stem(tmp_path, doctrines_dir):
    directory = _make_doctrine(doctrines_dir, "tdd-lite", missions=())
    (directory / "missions").mkdir()
    (directory / "missions" / "recon.md").write_text(
        "---\nid: disagrees\ntitle: T\nsummary: S\n---\n\nBody.\n"
    )

    record = read_doctrine(tmp_path, "tdd-lite", mission="recon")

    assert record["missions"][0]["id"] == "recon"
    assert record["mission"]["id"] == "recon"


# ---------------------------------------------------------------------------
# load_mission_sources — path list to {stem: content}
# ---------------------------------------------------------------------------


def test_load_mission_sources_maps_stem_to_content(tmp_path):
    first = tmp_path / "recon.md"
    second = tmp_path / "scribe.md"
    first.write_text("one")
    second.write_text("two")

    assert load_mission_sources([first, second]) == {"recon": "one", "scribe": "two"}


def test_load_mission_sources_raises_on_a_missing_file(tmp_path):
    missing = tmp_path / "recon.md"

    with pytest.raises(ValueError) as excinfo:
        load_mission_sources([missing])

    assert str(excinfo.value) == f"File not found: {missing}"


def test_load_mission_sources_raises_on_a_duplicate_stem(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    first = tmp_path / "a" / "recon.md"
    second = tmp_path / "b" / "recon.md"
    first.write_text("one")
    second.write_text("two")

    with pytest.raises(ValueError) as excinfo:
        load_mission_sources([first, second])

    assert str(excinfo.value) == (
        'Duplicate mission id "recon": two -m files share a filename stem'
    )


def test_load_mission_sources_returns_an_empty_mapping_for_no_paths():
    assert load_mission_sources([]) == {}


# ---------------------------------------------------------------------------
# _find_doctrine_dir — the strict resolver for a user-supplied name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["a/b", "a\\b"])
def test_find_doctrine_dir_rejects_a_path_separator(tmp_path, doctrines_dir, bad):
    with pytest.raises(ValueError) as excinfo:
        _find_doctrine_dir(tmp_path, bad)

    assert str(excinfo.value) == "Invalid doctrine name: path separators not allowed"


def test_find_doctrine_dir_prefers_the_shallower_match(tmp_path, doctrines_dir):
    shallow = _make_doctrine(doctrines_dir, "tdd-lite")
    _make_doctrine(doctrines_dir, "tdd-lite", group="default/nested")

    assert _find_doctrine_dir(tmp_path, "tdd-lite") == shallow


def test_find_doctrine_dir_finds_a_nested_doctrine(tmp_path, doctrines_dir):
    nested = _make_doctrine(doctrines_dir, "tdd-lite", group="default")

    assert _find_doctrine_dir(tmp_path, "tdd-lite") == nested


def test_find_doctrine_dir_returns_none_when_the_doctrines_dir_is_absent(tmp_path):
    assert _find_doctrine_dir(tmp_path, "tdd-lite") is None


def test_find_doctrine_dir_returns_none_on_a_miss(tmp_path, doctrines_dir):
    assert _find_doctrine_dir(tmp_path, "nope") is None


def test_find_doctrine_dir_ignores_a_deleted_directory(tmp_path, doctrines_dir):
    _make_doctrine(doctrines_dir, "tdd-lite", dirname="tdd-lite.deleted")

    assert _find_doctrine_dir(tmp_path, "tdd-lite") is None


# ---------------------------------------------------------------------------
# _resolve_doctrine_mission — the permissive resolver for a stored reference
# ---------------------------------------------------------------------------


def test_resolve_doctrine_mission_resolves_a_stored_reference(tmp_path, doctrines_dir):
    directory = _make_doctrine(doctrines_dir, "tdd-lite")

    resolved = _resolve_doctrine_mission(tmp_path, "tdd-lite/recon")

    assert resolved == directory / "missions" / "recon.md"


def test_resolve_doctrine_mission_resolves_inside_a_nested_group(
    tmp_path, doctrines_dir
):
    directory = _make_doctrine(doctrines_dir, "tdd-lite", group="default/lanes")

    resolved = _resolve_doctrine_mission(tmp_path, "tdd-lite/recon")

    assert resolved == directory / "missions" / "recon.md"


@pytest.mark.parametrize(
    "ref",
    [
        "recon",
        "tdd-lite/lanes/recon",
        "../../etc/passwd",
        "/etc/passwd",
        "tdd-lite/../../../etc/passwd",
        "",
    ],
)
def test_resolve_doctrine_mission_refuses_a_reference_it_cannot_own(
    tmp_path, doctrines_dir, ref
):
    _make_doctrine(doctrines_dir, "tdd-lite")

    assert _resolve_doctrine_mission(tmp_path, ref) is None


def test_resolve_doctrine_mission_returns_none_when_the_file_is_absent(
    tmp_path, doctrines_dir
):
    _make_doctrine(doctrines_dir, "tdd-lite")

    assert _resolve_doctrine_mission(tmp_path, "tdd-lite/nope") is None


def test_resolve_doctrine_mission_returns_none_when_the_doctrine_is_absent(
    tmp_path, doctrines_dir
):
    assert _resolve_doctrine_mission(tmp_path, "gone/missing") is None


def test_resolve_doctrine_mission_ignores_a_soft_deleted_sibling(
    tmp_path, doctrines_dir
):
    directory = _make_doctrine(doctrines_dir, "tdd-lite", missions=("recon", "lint"))
    lint = directory / "missions" / "lint.md"
    lint.rename(lint.with_name("lint.md.deleted"))

    assert _resolve_doctrine_mission(tmp_path, "tdd-lite/recon") == (
        directory / "missions" / "recon.md"
    )
    assert _resolve_doctrine_mission(tmp_path, "tdd-lite/lint") is None


def test_resolve_doctrine_mission_accepts_a_backslash_separator(
    tmp_path, doctrines_dir
):
    directory = _make_doctrine(doctrines_dir, "tdd-lite")

    assert _resolve_doctrine_mission(tmp_path, "tdd-lite\\recon") == (
        directory / "missions" / "recon.md"
    )


def test_doctrine_mission_stem_returns_the_bare_mission_id():
    assert _doctrine_mission_stem("tdd-lite/recon") == "recon"
    assert _doctrine_mission_stem("tdd-lite\\recon") == "recon"
    assert _doctrine_mission_stem("recon") == "recon"


# ---------------------------------------------------------------------------
# The step graph is gone — nothing relocated it under another name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "load_doctrine",
        "validate_doctrine_content",
        "scaffold_doctrine",
        "_validate_steps",
        "_check_cycles",
        "_normalize",
        "_validate_yaml_schema",
        "_parse_yaml",
    ],
)
def test_the_yaml_step_graph_callables_are_gone(name):
    assert not hasattr(doctrine_module, name)


# ---------------------------------------------------------------------------
# Scoped reads across nested projects
#
# Spec: nested-projects-spec — D-8 (resolution), D-16 (ordering)
# ---------------------------------------------------------------------------


class TestScopedListDoctrines:
    def test_an_ancestors_export_arrives_qualified_and_tagged(self, tree):
        tree.configure(tree.camelot, '[shared]\nexports = ["*"]\n')
        tree.doctrine(tree.camelot, "shipped-flow")
        tree.doctrine(tree.lore, "local-flow")

        records = {d["id"]: d for d in list_doctrines(tree.lore)}

        assert records["camelot:shipped-flow"]["origin"] == "camelot"
        assert records["local-flow"]["origin"] == "self"

    def test_a_seeded_default_never_crosses_a_boundary(self, tree):
        tree.configure(tree.camelot, '[shared]\nexports = ["*"]\n')
        tree.doctrine(tree.camelot, "tdd-feature", group="default")
        tree.doctrine(tree.camelot, "authored-flow")

        ids = [d["id"] for d in list_doctrines(tree.lore)]

        assert ids == ["camelot:authored-flow"]

    def test_a_descendants_seeded_default_is_kept(self, tree):
        tree.doctrine(tree.lore, "tdd-feature", group="default")

        records = list_doctrines(tree.lore)

        assert [d["id"] for d in records] == ["tdd-feature"]
        assert records[0]["origin"] == "self"

    def test_a_group_filter_applies_inside_every_project(self, tree):
        tree.configure(tree.camelot, '[shared]\nexports = ["*"]\n')
        tree.doctrine(tree.camelot, "kept-flow", group="ops")
        tree.doctrine(tree.camelot, "dropped-flow", group="other")

        ids = [d["id"] for d in list_doctrines(tree.lore, ["ops"])]

        assert ids == ["camelot:kept-flow"]

    def test_an_unknown_project_name_raises(self, tree):
        from lore.projects import UnknownProjectError

        with pytest.raises(UnknownProjectError):
            list_doctrines(tree.lore, scope="nope")


class TestScopedReadDoctrine:
    def test_it_reads_an_inherited_doctrine_by_qualified_id(self, tree):
        tree.configure(tree.camelot, '[shared]\nexports = ["*"]\n')
        tree.doctrine(tree.camelot, "shipped-flow")

        record = read_doctrine(tree.lore, "camelot:shipped-flow")

        assert record["id"] == "camelot:shipped-flow"
        assert record["origin"] == "camelot"
        assert [m["id"] for m in record["missions"]] == ["only"]

    def test_it_reads_one_inherited_mission_body(self, tree):
        tree.configure(tree.camelot, '[shared]\nexports = ["*"]\n')
        tree.doctrine(tree.camelot, "shipped-flow")

        record = read_doctrine(tree.lore, "camelot:shipped-flow", mission="only")

        assert record["mission"]["body"] == "Do only.\n"

    def test_a_bare_id_resolves_locally_first(self, tree):
        tree.configure(tree.camelot, '[shared]\nexports = ["*"]\n')
        tree.doctrine(tree.camelot, "twin")
        tree.doctrine(tree.lore, "twin")

        assert read_doctrine(tree.lore, "twin")["origin"] == "self"

    def test_an_unexported_ancestor_doctrine_reads_as_a_miss(self, tree):
        tree.configure(tree.camelot, '[shared]\nexports = ["nothing-*"]\n')
        tree.doctrine(tree.camelot, "private-flow")

        assert read_doctrine(tree.lore, "camelot:private-flow") is None

    def test_a_local_record_carries_the_self_origin(self, tree):
        tree.doctrine(tree.lore, "local-flow")

        assert read_doctrine(tree.lore, "local-flow")["origin"] == "self"
