"""E2E tests for ``lore doctrine show`` — the design document and the mission index.

Spec: conceptual-workflows-doctrine-show (lore codex show conceptual-workflows-doctrine-show)

A doctrine is a directory: ``<stem>/<stem>.design.md`` plus ``<stem>/missions/<id>.md``.
``lore doctrine show`` answers with the design document and an index of the
missions in one call; ``--mission <id>`` answers with one mission body instead.
"""

import json

from lore.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _design(stem: str, title: str = "TDD Lite", summary: str = "A small loop.") -> str:
    return (
        f"---\nid: {stem}\ntitle: {title}\nsummary: {summary}\n---\n"
        f"\n# {title}\n\nThe design prose an orchestrator reads.\n"
    )


def _mission(mission_id: str, title: str, summary: str = "s", body: str = "Do the work.\n") -> str:
    return f"---\nid: {mission_id}\ntitle: {title}\nsummary: {summary}\n---\n\n{body}"


def _write_doctrine(project_dir, stem, missions: dict[str, str], group: str = "") -> None:
    """Write a doctrine directory: the design document plus its mission files."""
    base = project_dir / ".lore" / "doctrines"
    if group:
        base = base / group
    directory = base / stem
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{stem}.design.md").write_text(_design(stem))
    if missions:
        (directory / "missions").mkdir(exist_ok=True)
        for mission_id, content in missions.items():
            (directory / "missions" / f"{mission_id}.md").write_text(content)


def _tdd_lite(project_dir) -> None:
    _write_doctrine(
        project_dir,
        "tdd-lite",
        {
            "recon": _mission("recon", "Map the codex", body="Read the codex first.\n"),
            "feature-spec": _mission("feature-spec", "Write the feature spec"),
        },
    )


# ---------------------------------------------------------------------------
# E1-E2: the design document and the mission index
# ---------------------------------------------------------------------------


def test_doctrine_show_prints_the_design_then_the_mission_index(project_dir, runner):
    """E1 — design verbatim, a blank line, the index sorted by id."""
    _tdd_lite(project_dir)

    result = runner.invoke(main, ["doctrine", "show", "tdd-lite"])

    assert result.exit_code == 0, result.output
    assert result.stdout == (
        _design("tdd-lite")
        + "\n"
        + "--- Missions ---\n"
        + "feature-spec  Write the feature spec\n"
        + "recon         Map the codex\n"
    )


def test_doctrine_show_with_no_missions_directory_says_none(project_dir, runner):
    """E2 — a doctrine with no missions/ still resolves."""
    _write_doctrine(project_dir, "solo", {})

    result = runner.invoke(main, ["doctrine", "show", "solo"])

    assert result.exit_code == 0, result.output
    assert result.stdout == _design("solo") + "\n--- Missions ---\n(none)\n"


# ---------------------------------------------------------------------------
# E3: the JSON envelope
# ---------------------------------------------------------------------------


def test_doctrine_show_json_wraps_the_record_under_doctrine(project_dir, runner):
    """E3 — one top-level key, and the step graph is gone."""
    _tdd_lite(project_dir)

    result = runner.invoke(main, ["--json", "doctrine", "show", "tdd-lite"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert list(payload) == ["doctrine"]
    doctrine = payload["doctrine"]
    assert set(doctrine) == {"id", "title", "summary", "design", "missions", "origin"}
    assert "raw_yaml" not in doctrine
    assert "steps" not in doctrine
    assert [m["id"] for m in doctrine["missions"]] == ["feature-spec", "recon"]
    assert set(doctrine["missions"][0]) == {"id", "title", "summary"}


def test_doctrine_show_json_carries_the_whole_design_file(project_dir, runner):
    """The design value is the file as written, frontmatter included."""
    _tdd_lite(project_dir)

    result = runner.invoke(main, ["--json", "doctrine", "show", "tdd-lite"])

    assert json.loads(result.stdout)["doctrine"]["design"] == _design("tdd-lite")


# ---------------------------------------------------------------------------
# E4-E5: one mission body
# ---------------------------------------------------------------------------


def test_doctrine_show_mission_prints_the_body_alone(project_dir, runner):
    """E4 — the body verbatim, frontmatter stripped."""
    _tdd_lite(project_dir)

    result = runner.invoke(main, ["doctrine", "show", "tdd-lite", "--mission", "recon"])

    assert result.exit_code == 0, result.output
    assert result.stdout == "Read the codex first.\n"


def test_doctrine_show_mission_json_wraps_the_record_under_mission(project_dir, runner):
    """E5 — the mission envelope carries exactly four keys."""
    _tdd_lite(project_dir)

    result = runner.invoke(
        main, ["--json", "doctrine", "show", "tdd-lite", "--mission", "recon"]
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert list(payload) == ["mission"]
    assert payload["mission"] == {
        "id": "recon",
        "title": "Map the codex",
        "summary": "s",
        "body": "Read the codex first.\n",
    }


# ---------------------------------------------------------------------------
# E6-E8: the two misses, and where a JSON error goes
# ---------------------------------------------------------------------------


def test_doctrine_show_reports_a_mission_miss_against_its_doctrine(project_dir, runner):
    """E6 — the doctrine resolved; the mission did not."""
    _tdd_lite(project_dir)

    result = runner.invoke(main, ["doctrine", "show", "tdd-lite", "--mission", "nope"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.strip() == 'Mission "nope" not found in doctrine "tdd-lite"'


def test_doctrine_show_reports_a_doctrine_miss_before_the_mission(project_dir, runner):
    """E7 — a doctrine miss is reported as such even when --mission is passed."""
    _tdd_lite(project_dir)

    result = runner.invoke(main, ["doctrine", "show", "nope", "--mission", "recon"])

    assert result.exit_code == 1
    assert result.stderr.strip() == "Doctrine 'nope' not found"


def test_doctrine_show_mission_with_a_path_separator_is_refused(project_dir, runner):
    """A mission id is one segment; a path is not a mission id."""
    _tdd_lite(project_dir)

    result = runner.invoke(
        main, ["doctrine", "show", "tdd-lite", "--mission", "../secrets"]
    )

    assert result.exit_code == 1
    assert result.stderr.strip() == "Invalid mission id: path separators not allowed"


def test_doctrine_show_local_json_flag_writes_its_error_to_stderr(project_dir, runner):
    """E8 — an error envelope never lands on stdout, on either --json path."""
    result = runner.invoke(main, ["doctrine", "show", "nope", "--json"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert json.loads(result.stderr) == {"error": "Doctrine 'nope' not found"}


def test_doctrine_show_global_json_flag_writes_its_error_to_stderr(project_dir, runner):
    """The same routing on the global flag."""
    result = runner.invoke(main, ["--json", "doctrine", "show", "nope"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert json.loads(result.stderr) == {"error": "Doctrine 'nope' not found"}


def test_doctrine_show_mission_miss_json_envelope_goes_to_stderr(project_dir, runner):
    """A mission miss is an error like any other in JSON mode."""
    _tdd_lite(project_dir)

    result = runner.invoke(
        main, ["--json", "doctrine", "show", "tdd-lite", "--mission", "nope"]
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert json.loads(result.stderr) == {
        "error": 'Mission "nope" not found in doctrine "tdd-lite"'
    }


def test_doctrine_show_finds_a_doctrine_in_a_nested_group(project_dir, runner):
    """Discovery is subtree-wide; a seeded doctrine lives under default/."""
    _write_doctrine(
        project_dir,
        "nested",
        {"only": _mission("only", "The only one")},
        group="default/feature-implementation",
    )

    result = runner.invoke(main, ["doctrine", "show", "nested"])

    assert result.exit_code == 0, result.output
    assert "--- Missions ---" in result.stdout
    assert "only  The only one" in result.stdout
