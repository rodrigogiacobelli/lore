"""Unit tests for ``lore.doctrine`` writes — create, update and delete.

Workflow: conceptual-workflows-doctrine-new (lore codex show conceptual-workflows-doctrine-new)
Workflow: conceptual-workflows-doctrine-edit

Every validation the CLI surfaces is enforced here (``decisions-011``), in the
order the spec's validation table states, and every failure leaves the tree
exactly as it was — ``create_doctrine`` stages the whole directory and renames
it into place, so a failure leaves neither the target nor the staging directory
behind.
"""

from pathlib import Path

import pytest

from lore.doctrine import create_doctrine, delete_doctrine, read_doctrine, update_doctrine
from lore.projects import ForeignEntityError


DESIGN = "---\nid: {stem}\ntitle: {title}\nsummary: A doctrine.\n---\n\n# {title}\n"
MISSION = "---\nid: {mid}\ntitle: {title}\nsummary: A mission.\n---\n\nBody of {mid}.\n"


def _design(stem: str, *, title: str = "TDD Lite") -> str:
    return DESIGN.format(stem=stem, title=title)


def _mission(mid: str, *, title: str | None = None) -> str:
    return MISSION.format(mid=mid, title=title if title is not None else mid)


@pytest.fixture()
def project(tmp_path):
    (tmp_path / ".lore" / "doctrines").mkdir(parents=True)
    return tmp_path


def _doctrines_dir(project: Path) -> Path:
    return project / ".lore" / "doctrines"


def _snapshot(directory: Path) -> dict[str, str]:
    return {
        str(p.relative_to(directory)): p.read_text()
        for p in sorted(directory.rglob("*"))
        if p.is_file()
    }


# ---------------------------------------------------------------------------
# create_doctrine — the envelope and what lands on disk
# ---------------------------------------------------------------------------


def test_create_returns_the_documented_envelope(project):
    result = create_doctrine(
        project,
        "tdd-lite",
        _design("tdd-lite"),
        {"recon": _mission("recon"), "scribe": _mission("scribe")},
        group="default",
    )

    assert result == {
        "created": "tdd-lite",
        "group": "default",
        "missions": ["recon", "scribe"],
        "path": ".lore/doctrines/default/tdd-lite/",
    }


def test_create_sorts_the_mission_list(project):
    result = create_doctrine(
        project,
        "tdd-lite",
        _design("tdd-lite"),
        {"scribe": _mission("scribe"), "feature-spec": _mission("feature-spec")},
    )

    assert result["missions"] == ["feature-spec", "scribe"]


def test_create_without_a_group_writes_at_the_doctrines_root(project):
    result = create_doctrine(
        project, "solo", _design("solo"), {"only": _mission("only")}
    )

    assert result["group"] is None
    assert result["path"] == ".lore/doctrines/solo/"
    assert (_doctrines_dir(project) / "solo" / "solo.design.md").exists()


def test_create_writes_every_file_at_its_documented_path(project):
    create_doctrine(
        project,
        "tdd-lite",
        _design("tdd-lite"),
        {"recon": _mission("recon"), "scribe": _mission("scribe")},
        group="default",
    )

    directory = _doctrines_dir(project) / "default" / "tdd-lite"
    assert (directory / "tdd-lite.design.md").read_text() == _design("tdd-lite")
    assert (directory / "missions" / "recon.md").read_text() == _mission("recon")
    assert (directory / "missions" / "scribe.md").read_text() == _mission("scribe")


def test_create_leaves_no_staging_directory_behind(project):
    create_doctrine(project, "solo", _design("solo"), {"only": _mission("only")})

    assert [p.name for p in _doctrines_dir(project).iterdir()] == ["solo"]


def test_a_created_doctrine_reads_back(project):
    create_doctrine(
        project, "tdd-lite", _design("tdd-lite"), {"recon": _mission("recon")}
    )

    record = read_doctrine(project, "tdd-lite")

    assert record["title"] == "TDD Lite"
    assert [m["id"] for m in record["missions"]] == ["recon"]


def test_a_crashed_runs_staging_directory_is_replaced_not_merged(project):
    stale = _doctrines_dir(project) / ".tdd-lite.lore-tmp"
    (stale / "tdd-lite" / "missions").mkdir(parents=True)
    (stale / "tdd-lite" / "missions" / "ghost.md").write_text("stale")

    create_doctrine(
        project, "tdd-lite", _design("tdd-lite"), {"recon": _mission("recon")}
    )

    directory = _doctrines_dir(project) / "tdd-lite"
    assert not (directory / "missions" / "ghost.md").exists()
    assert not stale.exists()


# ---------------------------------------------------------------------------
# create_doctrine — the validation table, in order
# ---------------------------------------------------------------------------


def test_a_qualified_name_is_refused_before_name_validation(project):
    with pytest.raises(ForeignEntityError) as excinfo:
        create_doctrine(project, "camelot:bad name", _design("x"), {})

    assert str(excinfo.value) == (
        'Cannot write "camelot:bad name": an entity from another project is read-only.'
    )


def test_an_invalid_name_raises(project):
    with pytest.raises(ValueError) as excinfo:
        create_doctrine(project, "bad name", _design("bad name"), {})

    assert str(excinfo.value) == (
        "Invalid name: must start with alphanumeric and contain only "
        "letters, digits, hyphens, underscores."
    )


def test_an_invalid_group_raises(project):
    with pytest.raises(ValueError) as excinfo:
        create_doctrine(
            project,
            "tdd-lite",
            _design("tdd-lite"),
            {"recon": _mission("recon")},
            group="/bad",
        )

    assert "group" in str(excinfo.value).lower()


def test_a_duplicate_anywhere_in_the_subtree_raises(project):
    create_doctrine(
        project,
        "tdd-lite",
        _design("tdd-lite"),
        {"recon": _mission("recon")},
        group="default",
    )
    existing = _doctrines_dir(project) / "default" / "tdd-lite"

    with pytest.raises(ValueError) as excinfo:
        create_doctrine(
            project, "tdd-lite", _design("tdd-lite"), {"recon": _mission("recon")}
        )

    assert str(excinfo.value) == f"Error: doctrine 'tdd-lite' already exists at {existing}"


def test_a_design_id_that_disagrees_with_the_argument_raises(project):
    with pytest.raises(ValueError) as excinfo:
        create_doctrine(
            project, "tdd-lite", _design("other"), {"recon": _mission("recon")}
        )

    assert str(excinfo.value) == (
        'Design file id "other" does not match command argument "tdd-lite"'
    )


def test_a_design_failing_its_schema_raises_the_schema_messages(project):
    design = "---\nid: tdd-lite\ntitle: TDD Lite\n---\n\nBody.\n"

    with pytest.raises(ValueError) as excinfo:
        create_doctrine(project, "tdd-lite", design, {"recon": _mission("recon")})

    assert str(excinfo.value) == "Missing required property 'summary'."


def test_no_missions_raises(project):
    with pytest.raises(ValueError) as excinfo:
        create_doctrine(project, "tdd-lite", _design("tdd-lite"), {})

    assert str(excinfo.value) == "At least one mission file is required (-m)"


def test_an_invalid_mission_id_raises(project):
    with pytest.raises(ValueError) as excinfo:
        create_doctrine(
            project, "tdd-lite", _design("tdd-lite"), {"bad id": _mission("bad id")}
        )

    assert str(excinfo.value) == (
        'Invalid mission id "bad id": must start with alphanumeric and contain only '
        "letters, digits, hyphens, underscores."
    )


def test_a_mission_id_that_disagrees_with_its_stem_raises(project):
    with pytest.raises(ValueError) as excinfo:
        create_doctrine(
            project, "tdd-lite", _design("tdd-lite"), {"recon": _mission("other")}
        )

    assert str(excinfo.value) == (
        'Mission file id "other" does not match filename stem "recon"'
    )


def test_a_mission_failing_its_schema_raises_a_prefixed_message(project):
    bad = "---\nid: bad\ntitle: Bad\n---\n\nBody.\n"

    with pytest.raises(ValueError) as excinfo:
        create_doctrine(
            project,
            "tdd-lite",
            _design("tdd-lite"),
            {"good": _mission("good"), "bad": bad},
        )

    assert str(excinfo.value) == "Mission \"bad\": Missing required property 'summary'."


def test_a_mission_with_no_frontmatter_at_all_raises_its_schema_messages(project):
    with pytest.raises(ValueError) as excinfo:
        create_doctrine(
            project, "tdd-lite", _design("tdd-lite"), {"recon": "Just a body.\n"}
        )

    assert str(excinfo.value).startswith('Mission "recon": ')


@pytest.mark.parametrize(
    "design,missions",
    [
        ("---\nid: other\ntitle: T\nsummary: S\n---\n", {"recon": None}),
        ("---\nid: tdd-lite\ntitle: T\nsummary: S\n---\n", {"bad id": None}),
        ("---\nid: tdd-lite\ntitle: T\nsummary: S\n---\n", {}),
    ],
)
def test_a_failed_create_leaves_nothing_on_disk(project, design, missions):
    sources = {
        mission_id: (content if content is not None else _mission(mission_id))
        for mission_id, content in missions.items()
    }

    with pytest.raises(ValueError):
        create_doctrine(project, "tdd-lite", design, sources)

    assert list(_doctrines_dir(project).iterdir()) == []


# ---------------------------------------------------------------------------
# update_doctrine
# ---------------------------------------------------------------------------


@pytest.fixture()
def seeded(project):
    """A three-mission doctrine under ``default/`` — the shape every seed has."""
    create_doctrine(
        project,
        "tdd-lite",
        _design("tdd-lite"),
        {
            "recon": _mission("recon"),
            "lint": _mission("lint"),
            "refactor": _mission("refactor"),
        },
        group="default",
    )
    return _doctrines_dir(project) / "default" / "tdd-lite"


def test_update_resolves_a_doctrine_below_the_doctrines_root(project, seeded):
    result = update_doctrine(project, "tdd-lite", missions={"recon": _mission("recon")})

    assert result["updated"] == "tdd-lite"


def test_update_returns_the_documented_envelope(project, seeded):
    result = update_doctrine(
        project,
        "tdd-lite",
        design_content=_design("tdd-lite", title="V2"),
        missions={"recon": _mission("recon")},
        remove_missions=["lint"],
    )

    assert result == {
        "updated": "tdd-lite",
        "design_replaced": True,
        "missions_replaced": ["recon"],
        "missions_removed": ["lint"],
    }


def test_update_sorts_both_lists(project, seeded):
    result = update_doctrine(
        project,
        "tdd-lite",
        missions={"recon": _mission("recon"), "feature-spec": _mission("feature-spec")},
        remove_missions=["refactor", "lint"],
    )

    assert result["missions_replaced"] == ["feature-spec", "recon"]
    assert result["missions_removed"] == ["lint", "refactor"]


def test_replacing_one_mission_leaves_every_other_file_byte_identical(project, seeded):
    before = _snapshot(seeded)

    update_doctrine(
        project, "tdd-lite", missions={"recon": _mission("recon", title="Rewritten")}
    )

    after = _snapshot(seeded)
    assert after["tdd-lite.design.md"] == before["tdd-lite.design.md"]
    assert after["missions/lint.md"] == before["missions/lint.md"]
    assert after["missions/refactor.md"] == before["missions/refactor.md"]
    assert after["missions/recon.md"] == _mission("recon", title="Rewritten")


def test_replacing_the_design_leaves_every_mission_byte_identical(project, seeded):
    before = _snapshot(seeded)

    update_doctrine(project, "tdd-lite", design_content=_design("tdd-lite", title="V2"))

    after = _snapshot(seeded)
    assert after["missions/recon.md"] == before["missions/recon.md"]
    assert after["tdd-lite.design.md"] == _design("tdd-lite", title="V2")


def test_an_unknown_stem_adds_a_mission(project, seeded):
    result = update_doctrine(
        project, "tdd-lite", missions={"scribe": _mission("scribe")}
    )

    assert result["missions_replaced"] == ["scribe"]
    assert (seeded / "missions" / "scribe.md").read_text() == _mission("scribe")
    assert (seeded / "missions" / "recon.md").exists()


def test_removing_a_mission_soft_deletes_it(project, seeded):
    update_doctrine(project, "tdd-lite", remove_missions=["lint", "refactor"])

    assert (seeded / "missions" / "lint.md.deleted").exists()
    assert (seeded / "missions" / "refactor.md.deleted").exists()
    assert not (seeded / "missions" / "lint.md").exists()
    assert not (seeded / "missions" / "refactor.md").exists()


def test_update_with_nothing_to_do_is_a_no_op(project, seeded):
    before = _snapshot(seeded)

    result = update_doctrine(project, "tdd-lite")

    assert result == {
        "updated": "tdd-lite",
        "design_replaced": False,
        "missions_replaced": [],
        "missions_removed": [],
    }
    assert _snapshot(seeded) == before


def test_update_refuses_a_qualified_name(project):
    with pytest.raises(ForeignEntityError):
        update_doctrine(project, "camelot:tdd-lite", design_content=_design("tdd-lite"))


def test_update_on_a_missing_doctrine_raises(project):
    with pytest.raises(ValueError) as excinfo:
        update_doctrine(project, "nope", missions={"recon": _mission("recon")})

    assert str(excinfo.value) == 'Doctrine "nope" not found.'


def test_removing_a_mission_that_is_not_there_raises(project, seeded):
    before = _snapshot(seeded)

    with pytest.raises(ValueError) as excinfo:
        update_doctrine(project, "tdd-lite", remove_missions=["nope"])

    assert str(excinfo.value) == 'Mission "nope" not found in doctrine "tdd-lite"'
    assert _snapshot(seeded) == before


def test_removing_an_already_soft_deleted_mission_raises_the_not_found_message(
    project, seeded
):
    update_doctrine(project, "tdd-lite", remove_missions=["lint"])

    with pytest.raises(ValueError) as excinfo:
        update_doctrine(project, "tdd-lite", remove_missions=["lint"])

    assert str(excinfo.value) == 'Mission "lint" not found in doctrine "tdd-lite"'


def test_removing_every_mission_raises(project):
    create_doctrine(project, "solo", _design("solo"), {"only": _mission("only")})
    directory = _doctrines_dir(project) / "solo"

    with pytest.raises(ValueError) as excinfo:
        update_doctrine(project, "solo", remove_missions=["only"])

    assert str(excinfo.value) == (
        "Cannot remove every mission: a doctrine keeps at least one mission."
    )
    assert (directory / "missions" / "only.md").exists()


def test_removing_every_mission_is_allowed_when_one_is_added_back(project):
    create_doctrine(project, "solo", _design("solo"), {"only": _mission("only")})

    result = update_doctrine(
        project,
        "solo",
        missions={"replacement": _mission("replacement")},
        remove_missions=["only"],
    )

    assert result["missions_removed"] == ["only"]
    assert result["missions_replaced"] == ["replacement"]


def test_a_bad_design_leaves_the_tree_byte_identical(project, seeded):
    before = _snapshot(seeded)

    with pytest.raises(ValueError) as excinfo:
        update_doctrine(project, "tdd-lite", design_content=_design("other"))

    assert str(excinfo.value) == (
        'Design file id "other" does not match command argument "tdd-lite"'
    )
    assert _snapshot(seeded) == before


def test_a_bad_mission_leaves_the_tree_byte_identical(project, seeded):
    before = _snapshot(seeded)

    with pytest.raises(ValueError) as excinfo:
        update_doctrine(project, "tdd-lite", missions={"recon": _mission("other")})

    assert str(excinfo.value) == (
        'Mission file id "other" does not match filename stem "recon"'
    )
    assert _snapshot(seeded) == before


def test_an_invalid_mission_id_on_update_raises(project, seeded):
    with pytest.raises(ValueError) as excinfo:
        update_doctrine(project, "tdd-lite", missions={"bad id": _mission("bad id")})

    assert str(excinfo.value) == (
        'Invalid mission id "bad id": must start with alphanumeric and contain only '
        "letters, digits, hyphens, underscores."
    )


def test_a_mission_failing_its_schema_on_update_raises_a_prefixed_message(
    project, seeded
):
    with pytest.raises(ValueError) as excinfo:
        update_doctrine(
            project,
            "tdd-lite",
            missions={"recon": "---\nid: recon\ntitle: T\n---\n\nBody.\n"},
        )

    assert str(excinfo.value) == (
        "Mission \"recon\": Missing required property 'summary'."
    )


# ---------------------------------------------------------------------------
# delete_doctrine
# ---------------------------------------------------------------------------


def test_delete_renames_the_directory(project, seeded):
    result = delete_doctrine(project, "tdd-lite")

    assert result == {"id": "tdd-lite", "deleted": True, "deleted_at": None}
    assert not seeded.exists()
    assert seeded.with_name("tdd-lite.deleted").is_dir()
    assert (seeded.with_name("tdd-lite.deleted") / "missions" / "recon.md").exists()


def test_a_deleted_doctrine_is_invisible_to_list_and_read(project, seeded):
    delete_doctrine(project, "tdd-lite")

    from lore.doctrine import list_doctrines

    assert list_doctrines(project) == []
    assert read_doctrine(project, "tdd-lite") is None


def test_delete_on_a_missing_doctrine_raises(project):
    with pytest.raises(ValueError) as excinfo:
        delete_doctrine(project, "nope")

    assert str(excinfo.value) == 'Doctrine "nope" not found'


def test_delete_refuses_a_qualified_name(project):
    with pytest.raises(ForeignEntityError):
        delete_doctrine(project, "camelot:tdd-lite")
