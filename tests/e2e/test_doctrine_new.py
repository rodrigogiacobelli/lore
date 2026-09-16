"""E2E tests for ``lore doctrine new`` — one design document and N mission files.

Spec: conceptual-workflows-doctrine-new (lore codex show conceptual-workflows-doctrine-new)

``lore doctrine new NAME -d DESIGN -m FILE [FILE ...]`` builds the whole
doctrine directory or none of it: everything is validated first, the tree is
staged under a dot-prefixed directory, and one rename puts it in place.
"""

import json

from lore.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _design(tmp_path, doctrine_id="tdd-lite", *, summary="A small loop."):
    path = tmp_path / "design.md"
    path.write_text(
        f"---\nid: {doctrine_id}\ntitle: TDD Lite\nsummary: {summary}\n---\n\n# TDD Lite\n"
    )
    return str(path)


def _mission_file(tmp_path, stem, *, mission_id=None, summary="s", subdir=None):
    directory = tmp_path if subdir is None else tmp_path / subdir
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{stem}.md"
    frontmatter = f"---\nid: {mission_id or stem}\ntitle: {stem.title()}\n"
    if summary is not None:
        frontmatter += f"summary: {summary}\n"
    path.write_text(f"{frontmatter}---\n\nThe {stem} instructions.\n")
    return str(path)


def _doctrines_dir(project_dir):
    return project_dir / ".lore" / "doctrines"


# ---------------------------------------------------------------------------
# E9-E11: the happy paths
# ---------------------------------------------------------------------------


def test_doctrine_new_writes_the_design_and_every_mission(runner, project_dir, tmp_path):
    """E9 — the whole directory lands under the group."""
    result = runner.invoke(
        main,
        [
            "doctrine", "new", "tdd-lite", "--group", "default",
            "-d", _design(tmp_path),
            "-m",
            _mission_file(tmp_path, "recon"),
            _mission_file(tmp_path, "feature-spec"),
            _mission_file(tmp_path, "scribe"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == "Created doctrine tdd-lite with 3 missions in group default\n"
    directory = _doctrines_dir(project_dir) / "default" / "tdd-lite"
    assert (directory / "tdd-lite.design.md").is_file()
    assert sorted(p.name for p in (directory / "missions").iterdir()) == [
        "feature-spec.md",
        "recon.md",
        "scribe.md",
    ]


def test_doctrine_new_with_one_mission_and_no_group(runner, project_dir, tmp_path):
    """E10 — singular in the message, and the doctrine sits at the root."""
    result = runner.invoke(
        main,
        [
            "doctrine", "new", "solo",
            "-d", _design(tmp_path, "solo"),
            "-m", _mission_file(tmp_path, "only"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.stdout == "Created doctrine solo with 1 mission\n"
    assert (_doctrines_dir(project_dir) / "solo" / "solo.design.md").is_file()


def test_doctrine_new_json_envelope(runner, project_dir, tmp_path):
    """E11 — four keys, missions sorted, and a path that ends in a slash."""
    result = runner.invoke(
        main,
        [
            "--json", "doctrine", "new", "tdd-lite", "--group", "default",
            "-d", _design(tmp_path),
            "-m",
            _mission_file(tmp_path, "recon"),
            _mission_file(tmp_path, "feature-spec"),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload == {
        "created": "tdd-lite",
        "group": "default",
        "missions": ["feature-spec", "recon"],
        "path": ".lore/doctrines/default/tdd-lite/",
    }


def test_doctrine_new_json_group_is_null_without_the_flag(runner, project_dir, tmp_path):
    """No --group is a null group, not an empty string."""
    result = runner.invoke(
        main,
        [
            "--json", "doctrine", "new", "solo",
            "-d", _design(tmp_path, "solo"),
            "-m", _mission_file(tmp_path, "only"),
        ],
    )

    assert json.loads(result.stdout)["group"] is None


# ---------------------------------------------------------------------------
# E12-E16: every failure leaves the doctrines directory as it was
# ---------------------------------------------------------------------------


def test_doctrine_new_without_missions_is_refused(runner, project_dir, tmp_path):
    """E12 — a doctrine keeps at least one mission, from its first moment."""
    result = runner.invoke(
        main, ["doctrine", "new", "tdd-lite", "-d", _design(tmp_path)]
    )

    assert result.exit_code == 1
    assert result.stderr.strip() == "At least one mission file is required (-m)"
    assert not (_doctrines_dir(project_dir) / "tdd-lite").exists()


def test_doctrine_new_without_a_design_is_refused(runner, project_dir, tmp_path):
    """E13 — the design document is what makes the directory a doctrine."""
    result = runner.invoke(
        main, ["doctrine", "new", "tdd-lite", "-m", _mission_file(tmp_path, "recon")]
    )

    assert result.exit_code == 1
    assert result.stderr.strip() == "Error: -d/--design is required"
    assert not (_doctrines_dir(project_dir) / "tdd-lite").exists()


def test_doctrine_new_rejects_two_mission_files_sharing_a_stem(
    runner, project_dir, tmp_path
):
    """E14 — the stem is the mission id, so two of them collide."""
    result = runner.invoke(
        main,
        [
            "doctrine", "new", "tdd-lite",
            "-d", _design(tmp_path),
            "-m",
            _mission_file(tmp_path, "recon", subdir="x"),
            _mission_file(tmp_path, "recon", subdir="y"),
        ],
    )

    assert result.exit_code == 1
    assert result.stderr.strip() == (
        'Duplicate mission id "recon": two -m files share a filename stem'
    )
    assert not (_doctrines_dir(project_dir) / "tdd-lite").exists()


def test_doctrine_new_missing_mission_file_is_reported_by_path(
    runner, project_dir, tmp_path
):
    """A source file named on the command line that is not there."""
    missing = str(tmp_path / "gone.md")
    result = runner.invoke(
        main, ["doctrine", "new", "tdd-lite", "-d", _design(tmp_path), "-m", missing]
    )

    assert result.exit_code == 1
    assert result.stderr.strip() == f"File not found: {missing}"


def test_doctrine_new_missing_design_file_is_reported_by_path(
    runner, project_dir, tmp_path
):
    """The same answer for the design document."""
    missing = str(tmp_path / "gone.md")
    result = runner.invoke(
        main,
        [
            "doctrine", "new", "tdd-lite",
            "-d", missing,
            "-m", _mission_file(tmp_path, "recon"),
        ],
    )

    assert result.exit_code == 1
    assert result.stderr.strip() == f"File not found: {missing}"


def test_doctrine_new_leaves_nothing_behind_when_one_mission_is_invalid(
    runner, project_dir, tmp_path
):
    """E15 — not the directory, and not the staging directory either."""
    result = runner.invoke(
        main,
        [
            "doctrine", "new", "tdd-lite",
            "-d", _design(tmp_path),
            "-m",
            _mission_file(tmp_path, "good"),
            _mission_file(tmp_path, "bad", summary=None),
        ],
    )

    assert result.exit_code == 1
    assert result.stderr.startswith('Mission "bad": ')
    assert sorted(p.name for p in _doctrines_dir(project_dir).iterdir()) == ["default"]


def test_doctrine_new_refuses_a_name_already_taken_anywhere_in_the_subtree(
    runner, project_dir, tmp_path
):
    """E16 — a doctrine id is unique across the whole doctrines tree."""
    argv = [
        "doctrine", "new", "tdd-lite",
        "-d", _design(tmp_path),
        "-m", _mission_file(tmp_path, "recon"),
    ]
    assert runner.invoke(main, argv).exit_code == 0

    result = runner.invoke(main, argv + ["--group", "default"])

    assert result.exit_code == 1
    existing = _doctrines_dir(project_dir) / "tdd-lite"
    assert result.stderr.strip() == f"Error: doctrine 'tdd-lite' already exists at {existing}"


def test_doctrine_new_refuses_a_design_whose_id_is_not_the_command_argument(
    runner, project_dir, tmp_path
):
    """The directory name and the declared id are one fact, stated twice."""
    result = runner.invoke(
        main,
        [
            "doctrine", "new", "tdd-lite",
            "-d", _design(tmp_path, "something-else"),
            "-m", _mission_file(tmp_path, "recon"),
        ],
    )

    assert result.exit_code == 1
    assert result.stderr.strip() == (
        'Design file id "something-else" does not match command argument "tdd-lite"'
    )


def test_doctrine_new_refuses_a_mission_whose_id_is_not_its_stem(
    runner, project_dir, tmp_path
):
    """The filename is the mission id an orchestrator addresses."""
    result = runner.invoke(
        main,
        [
            "doctrine", "new", "tdd-lite",
            "-d", _design(tmp_path),
            "-m", _mission_file(tmp_path, "recon", mission_id="reconnaissance"),
        ],
    )

    assert result.exit_code == 1
    assert result.stderr.strip() == (
        'Mission file id "reconnaissance" does not match filename stem "recon"'
    )


def test_doctrine_new_refuses_an_invalid_name(runner, project_dir, tmp_path):
    """Name validation runs before anything reaches disk."""
    result = runner.invoke(
        main,
        [
            "doctrine", "new", "-bad-name",
            "-d", _design(tmp_path),
            "-m", _mission_file(tmp_path, "recon"),
            "--",
        ],
    )

    assert result.exit_code != 0


def test_doctrine_new_json_error_goes_to_stderr(runner, project_dir, tmp_path):
    """An error envelope never lands on stdout."""
    result = runner.invoke(
        main, ["--json", "doctrine", "new", "tdd-lite", "-d", _design(tmp_path)]
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert json.loads(result.stderr) == {
        "error": "At least one mission file is required (-m)"
    }


def test_doctrine_new_result_is_readable_by_doctrine_show(runner, project_dir, tmp_path):
    """What new writes is what show reads."""
    runner.invoke(
        main,
        [
            "doctrine", "new", "tdd-lite",
            "-d", _design(tmp_path),
            "-m",
            _mission_file(tmp_path, "recon"),
            _mission_file(tmp_path, "scribe"),
        ],
    )

    result = runner.invoke(main, ["doctrine", "show", "tdd-lite", "--mission", "recon"])

    assert result.exit_code == 0, result.output
    assert result.stdout == "The recon instructions.\n"
