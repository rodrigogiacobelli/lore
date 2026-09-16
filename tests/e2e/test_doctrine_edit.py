"""E2E tests for ``lore doctrine edit`` — whole-file mode over a doctrine directory.

Spec: conceptual-workflows-doctrine-edit (lore codex show conceptual-workflows-doctrine-edit)

``-d`` replaces the design document, ``-m`` replaces or adds mission files by
filename stem, and ``--remove-mission`` soft-deletes them. Everything is
validated first: a failure leaves the tree exactly as it was.
"""

import json

from lore.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _design_text(doctrine_id="tdd-lite", title="TDD Lite", summary="A small loop."):
    return f"---\nid: {doctrine_id}\ntitle: {title}\nsummary: {summary}\n---\n\n# {title}\n"


def _mission_text(mission_id, body="The instructions.\n", *, summary="s"):
    head = f"---\nid: {mission_id}\ntitle: {mission_id.title()}\n"
    if summary is not None:
        head += f"summary: {summary}\n"
    return f"{head}---\n\n{body}"


def _doctrine(project_dir, stem="tdd-lite", missions=("recon", "lint", "refactor")):
    directory = project_dir / ".lore" / "doctrines" / stem
    (directory / "missions").mkdir(parents=True, exist_ok=True)
    (directory / f"{stem}.design.md").write_text(_design_text(stem))
    for mission_id in missions:
        (directory / "missions" / f"{mission_id}.md").write_text(_mission_text(mission_id))
    return directory


def _source(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text)
    return str(path)


def _snapshot(directory):
    return {
        path.relative_to(directory).as_posix(): path.read_text()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


# ---------------------------------------------------------------------------
# E17-E21: what each clause changes, and what it leaves alone
# ---------------------------------------------------------------------------


def test_doctrine_edit_replaces_one_mission_and_leaves_the_rest(
    runner, project_dir, tmp_path
):
    """E17 — merge by stem: an unnamed file is not re-supplied and not rewritten."""
    directory = _doctrine(project_dir)
    before = _snapshot(directory)
    source = _source(tmp_path, "recon.md", _mission_text("recon", body="Rewritten.\n"))

    result = runner.invoke(main, ["doctrine", "edit", "tdd-lite", "-m", source])

    assert result.exit_code == 0, result.output
    assert result.stdout == "Updated doctrine tdd-lite (missions replaced: recon)\n"
    after = _snapshot(directory)
    assert after["missions/recon.md"] == _mission_text("recon", body="Rewritten.\n")
    assert after["missions/lint.md"] == before["missions/lint.md"]
    assert after["missions/refactor.md"] == before["missions/refactor.md"]
    assert after["tdd-lite.design.md"] == before["tdd-lite.design.md"]


def test_doctrine_edit_replaces_the_design_only(runner, project_dir, tmp_path):
    """E18 — every mission is byte-identical afterwards."""
    directory = _doctrine(project_dir)
    before = _snapshot(directory)
    source = _source(tmp_path, "d.md", _design_text(summary="Rewritten."))

    result = runner.invoke(main, ["doctrine", "edit", "tdd-lite", "-d", source])

    assert result.exit_code == 0, result.output
    assert result.stdout == "Updated doctrine tdd-lite (design replaced)\n"
    after = _snapshot(directory)
    assert after["tdd-lite.design.md"] == _design_text(summary="Rewritten.")
    for name in ("missions/recon.md", "missions/lint.md", "missions/refactor.md"):
        assert after[name] == before[name]


def test_doctrine_edit_with_a_new_stem_adds_a_mission(runner, project_dir, tmp_path):
    """E19 — an unknown stem is an addition, not an error."""
    directory = _doctrine(project_dir)
    source = _source(tmp_path, "scribe.md", _mission_text("scribe"))

    result = runner.invoke(main, ["doctrine", "edit", "tdd-lite", "-m", source])

    assert result.exit_code == 0, result.output
    assert result.stdout == "Updated doctrine tdd-lite (missions replaced: scribe)\n"
    assert (directory / "missions" / "scribe.md").is_file()


def test_doctrine_edit_removes_two_missions_by_soft_delete(runner, project_dir):
    """E20 — removal renames; it never unlinks (ADR-003)."""
    directory = _doctrine(project_dir)

    result = runner.invoke(
        main, ["doctrine", "edit", "tdd-lite", "--remove-mission", "refactor", "lint"]
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == "Updated doctrine tdd-lite (missions removed: lint, refactor)\n"
    missions = directory / "missions"
    assert (missions / "lint.md.deleted").is_file()
    assert (missions / "refactor.md.deleted").is_file()
    assert not (missions / "lint.md").exists()
    assert not (missions / "refactor.md").exists()


def test_doctrine_edit_joins_every_clause_it_performed(runner, project_dir, tmp_path):
    """E21 — one line names the design, the replacements and the removals."""
    _doctrine(project_dir, missions=("recon", "lint", "feature-spec"))

    result = runner.invoke(
        main,
        [
            "doctrine", "edit", "tdd-lite",
            "-d", _source(tmp_path, "d.md", _design_text()),
            "-m", _source(tmp_path, "recon.md", _mission_text("recon")),
            "--remove-mission", "lint",
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == (
        "Updated doctrine tdd-lite "
        "(design replaced; missions replaced: recon; missions removed: lint)\n"
    )


def test_doctrine_edit_replacing_several_missions_lists_them_sorted(
    runner, project_dir, tmp_path
):
    """The clause reads in id order however the files were named."""
    _doctrine(project_dir)

    result = runner.invoke(
        main,
        [
            "doctrine", "edit", "tdd-lite",
            "-m",
            _source(tmp_path, "refactor.md", _mission_text("refactor")),
            _source(tmp_path, "lint.md", _mission_text("lint")),
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == "Updated doctrine tdd-lite (missions replaced: lint, refactor)\n"


# ---------------------------------------------------------------------------
# E22-E24: the refusals
# ---------------------------------------------------------------------------


def test_doctrine_edit_with_no_flags_is_a_usage_error(runner, project_dir):
    """E22 — a command told to change nothing is a usage error, exit 2."""
    _doctrine(project_dir)

    result = runner.invoke(main, ["doctrine", "edit", "tdd-lite"])

    assert result.exit_code == 2
    assert "Error: Nothing to update: pass -d, -m, or --remove-mission" in result.stderr


def test_doctrine_edit_removing_an_unknown_mission_is_refused(runner, project_dir):
    """E23 — and nothing is removed."""
    directory = _doctrine(project_dir)
    before = _snapshot(directory)

    result = runner.invoke(
        main, ["doctrine", "edit", "tdd-lite", "--remove-mission", "nope"]
    )

    assert result.exit_code == 1
    assert result.stderr.strip() == 'Mission "nope" not found in doctrine "tdd-lite"'
    assert _snapshot(directory) == before


def test_doctrine_edit_cannot_remove_the_last_mission(runner, project_dir):
    """E24 — a doctrine keeps at least one mission."""
    directory = _doctrine(project_dir, stem="solo", missions=("only",))

    result = runner.invoke(
        main, ["doctrine", "edit", "solo", "--remove-mission", "only"]
    )

    assert result.exit_code == 1
    assert result.stderr.strip() == (
        "Cannot remove every mission: a doctrine keeps at least one mission."
    )
    assert (directory / "missions" / "only.md").is_file()


def test_doctrine_edit_on_an_unknown_doctrine_is_refused(runner, project_dir, tmp_path):
    """The miss message keeps its trailing period — today's text, unchanged."""
    result = runner.invoke(
        main,
        [
            "doctrine", "edit", "nope",
            "-m", _source(tmp_path, "recon.md", _mission_text("recon")),
        ],
    )

    assert result.exit_code == 1
    assert result.stderr.strip() == 'Doctrine "nope" not found.'


def test_doctrine_edit_rejects_a_mission_file_failing_its_schema(
    runner, project_dir, tmp_path
):
    """A validation failure leaves the tree exactly as it was."""
    directory = _doctrine(project_dir)
    before = _snapshot(directory)
    source = _source(tmp_path, "recon.md", _mission_text("recon", summary=None))

    result = runner.invoke(main, ["doctrine", "edit", "tdd-lite", "-m", source])

    assert result.exit_code == 1
    assert result.stderr.startswith('Mission "recon": ')
    assert _snapshot(directory) == before


def test_doctrine_edit_rejects_a_design_whose_id_disagrees(runner, project_dir, tmp_path):
    """The design document's id is the doctrine's directory name."""
    directory = _doctrine(project_dir)
    before = _snapshot(directory)
    source = _source(tmp_path, "d.md", _design_text("something-else"))

    result = runner.invoke(main, ["doctrine", "edit", "tdd-lite", "-d", source])

    assert result.exit_code == 1
    assert result.stderr.strip() == (
        'Design file id "something-else" does not match command argument "tdd-lite"'
    )
    assert _snapshot(directory) == before


def test_doctrine_edit_missing_source_file_is_reported_by_path(
    runner, project_dir, tmp_path
):
    """A path the user typed that is not there."""
    _doctrine(project_dir)
    missing = str(tmp_path / "gone.md")

    result = runner.invoke(main, ["doctrine", "edit", "tdd-lite", "-m", missing])

    assert result.exit_code == 1
    assert result.stderr.strip() == f"File not found: {missing}"


def test_doctrine_edit_rejects_whole_file_flags_mixed_with_field_edit_flags(
    runner, project_dir, tmp_path
):
    """Whole-file mode and field-edit mode are two ways to edit one document."""
    _doctrine(project_dir)

    result = runner.invoke(
        main,
        [
            "doctrine", "edit", "tdd-lite",
            "-d", _source(tmp_path, "d.md", _design_text()),
            "--set", "title=X",
        ],
    )

    assert result.exit_code == 1
    assert result.stderr.strip() == (
        "Cannot combine -d/--design, -m/--mission or --remove-mission with "
        "--set/--unset/--add/--remove."
    )


# ---------------------------------------------------------------------------
# E25: the JSON envelope, and where errors go in JSON mode
# ---------------------------------------------------------------------------


def test_doctrine_edit_json_envelope(runner, project_dir, tmp_path):
    """E25 — four keys, both lists sorted."""
    _doctrine(project_dir)
    source = _source(tmp_path, "recon.md", _mission_text("recon"))

    result = runner.invoke(
        main, ["--json", "doctrine", "edit", "tdd-lite", "-m", source]
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "updated": "tdd-lite",
        "design_replaced": False,
        "missions_replaced": ["recon"],
        "missions_removed": [],
    }


def test_doctrine_edit_json_error_goes_to_stderr(runner, project_dir):
    """The error envelope lands on stderr, like every other command's."""
    _doctrine(project_dir)

    result = runner.invoke(
        main, ["--json", "doctrine", "edit", "tdd-lite", "--remove-mission", "nope"]
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert json.loads(result.stderr) == {
        "error": 'Mission "nope" not found in doctrine "tdd-lite"'
    }


def test_doctrine_edit_json_missing_file_error_goes_to_stderr(
    runner, project_dir, tmp_path
):
    """Including the CLI's own file-not-found."""
    _doctrine(project_dir)
    missing = str(tmp_path / "gone.md")

    result = runner.invoke(
        main, ["--json", "doctrine", "edit", "tdd-lite", "-m", missing]
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert json.loads(result.stderr) == {"error": f"File not found: {missing}"}


# ---------------------------------------------------------------------------
# The removed flag, and what a removed mission does to a read
# ---------------------------------------------------------------------------


def test_doctrine_edit_no_longer_takes_a_whole_file_from_flag(
    runner, project_dir, tmp_path
):
    """A doctrine is 1 + N files, which one unnamed stream cannot address."""
    _doctrine(project_dir)

    result = runner.invoke(
        main,
        [
            "doctrine", "edit", "tdd-lite",
            "-f", _source(tmp_path, "d.md", _design_text()),
        ],
    )

    assert result.exit_code == 2
    assert "No such option: -f" in result.stderr


def test_a_removed_mission_leaves_the_index(runner, project_dir):
    """What edit soft-deletes, show stops listing."""
    _doctrine(project_dir)
    runner.invoke(main, ["doctrine", "edit", "tdd-lite", "--remove-mission", "lint"])

    result = runner.invoke(main, ["--json", "doctrine", "show", "tdd-lite"])

    ids = [m["id"] for m in json.loads(result.stdout)["doctrine"]["missions"]]
    assert ids == ["recon", "refactor"]
