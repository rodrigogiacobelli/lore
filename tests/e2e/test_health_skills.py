"""E2E tests for `lore health --scope skills`.

Spec: `lore codex show conceptual-workflows-health` — the skills scope.

`lore init` seeds the skill files but has never had an audit surface for them,
so a deleted, edited or retired skill was the one thing `lore health` could not
see. The scope reads `.lore/.install-manifest.json` and walks only the paths it
names: never-touch-what-Lore-did-not-install is the same discipline
reconciliation follows.

Covers the five checks (`missing_skill_file`, `modified_skill_file`,
`retired_skill_present`, `missing_skill_frontmatter`, `skills_scan_failed`),
the deliberate silence on a project with no manifest, the scope-token surface
(alone, space-separated, in the full scan, rejected, in `--help`), and the
Python surface's identical verdict.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from lore.cli import main


# ---------------------------------------------------------------------------
# Fixture authoring helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def skills_project(tmp_path, monkeypatch):
    """A project initialised for Claude, so skills land under `.claude/skills/`."""
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(main, ["init", "--agent", "claude", "--yes"])
    assert result.exit_code == 0, result.output
    return tmp_path


def manifest_path(project_dir: Path) -> Path:
    return project_dir / ".lore" / ".install-manifest.json"


def read_manifest(project_dir: Path) -> dict:
    return json.loads(manifest_path(project_dir).read_text(encoding="utf-8"))


def write_manifest(project_dir: Path, payload: dict) -> None:
    manifest_path(project_dir).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


def record_file(project_dir: Path, relative: str, *, source: str, text: str) -> None:
    """Write *text* at *relative* and record it in the manifest with its digest."""
    from lore.manifest import bytes_digest

    target = project_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")

    payload = read_manifest(project_dir)
    payload["files"].append(
        {
            "path": relative,
            "kind": "owned",
            "source": source,
            "hash": bytes_digest(text.encode("utf-8")),
        }
    )
    payload["files"].sort(key=lambda row: row["path"])
    write_manifest(project_dir, payload)


def skills_rows(result) -> list[str]:
    """Return the `skills` rows from human-readable `lore health` output."""
    return [
        line
        for line in result.output.splitlines()
        if line.split()[1:2] == ["skills"]
    ]


def row_for(result, check: str) -> str:
    rows = [line for line in skills_rows(result) if f"{check}:" in line]
    assert len(rows) == 1, f"expected one {check} row; got {rows}\n{result.output}"
    return rows[0]


# ---------------------------------------------------------------------------
# Scenario 1 — a deleted installed skill is an error and exits 1
# ---------------------------------------------------------------------------


def test_missing_installed_skill_is_an_error(skills_project, runner):
    (skills_project / ".claude" / "skills" / "inquest" / "SKILL.md").unlink()

    result = runner.invoke(main, ["health", "--scope", "skills"])

    row = row_for(result, "missing_skill_file")
    assert row.startswith("ERROR")
    assert ".claude/skills/inquest/SKILL.md" in row
    assert (
        "missing_skill_file: recorded in the install manifest but missing on disk"
        in row
    )
    assert result.exit_code == 1, result.output


# ---------------------------------------------------------------------------
# Scenario 2 — an edited installed skill is a warning
# ---------------------------------------------------------------------------


def test_edited_installed_skill_is_a_warning(skills_project, runner):
    target = skills_project / ".claude" / "skills" / "start-quest" / "SKILL.md"
    target.write_text(target.read_text(encoding="utf-8") + "\nmy note\n", encoding="utf-8")

    result = runner.invoke(main, ["health", "--scope", "skills"])

    row = row_for(result, "modified_skill_file")
    assert row.startswith("WARNING")
    assert ".claude/skills/start-quest/SKILL.md" in row
    assert (
        "modified_skill_file: edited since install; lore init will replace it "
        "with the shipped version" in row
    )
    assert "ERROR" not in result.output, result.output
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# Scenario 3 — a retired skill still on disk names its successor
# ---------------------------------------------------------------------------


def test_retired_skill_present_names_its_successor(skills_project, runner):
    record_file(
        skills_project,
        ".claude/skills/new-doctrine/SKILL.md",
        source="skill:new-doctrine",
        text="---\nname: new-doctrine\ndescription: retired\n---\n\n# New doctrine\n",
    )

    result = runner.invoke(main, ["health", "--scope", "skills"])

    row = row_for(result, "retired_skill_present")
    assert row.startswith("WARNING")
    assert "new-doctrine" in row
    assert (
        "retired_skill_present: retired into update-doctrine; run lore init to "
        "reconcile" in row
    )


# ---------------------------------------------------------------------------
# Scenario 4 — a SKILL.md with no `name` is an error
# ---------------------------------------------------------------------------


def test_skill_without_name_frontmatter_is_an_error(skills_project, runner):
    from lore.manifest import bytes_digest

    target = skills_project / ".claude" / "skills" / "inquest" / "SKILL.md"
    text = "---\ndescription: no name here\n---\n\n# Inquest\n"
    target.write_text(text, encoding="utf-8")

    # Re-record the hash, so the frontmatter check is what fires and not the
    # edited-since-install one.
    payload = read_manifest(skills_project)
    for row in payload["files"]:
        if row["path"] == ".claude/skills/inquest/SKILL.md":
            row["hash"] = bytes_digest(text.encode("utf-8"))
    write_manifest(skills_project, payload)

    result = runner.invoke(main, ["health", "--scope", "skills"])

    row = row_for(result, "missing_skill_frontmatter")
    assert row.startswith("ERROR")
    assert ".claude/skills/inquest/SKILL.md" in row
    assert (
        "missing_skill_frontmatter: SKILL.md frontmatter is missing 'name'" in row
    )
    assert result.exit_code == 1, result.output


# ---------------------------------------------------------------------------
# Scenario 5 — an unparseable manifest is exactly one error
# ---------------------------------------------------------------------------


def test_unparseable_manifest_is_one_scan_failure(skills_project, runner):
    manifest_path(skills_project).write_text("{not json", encoding="utf-8")

    result = runner.invoke(main, ["health", "--scope", "skills"])

    rows = skills_rows(result)
    assert len(rows) == 1, result.output
    assert rows[0].startswith("ERROR")
    assert ".lore/.install-manifest.json" in rows[0]
    assert "skills_scan_failed:" in rows[0]
    assert result.exit_code == 1, result.output


# ---------------------------------------------------------------------------
# Scenario 6 — a project with no manifest reports nothing
# ---------------------------------------------------------------------------


def test_project_without_a_manifest_reports_nothing(skills_project, runner):
    manifest_path(skills_project).unlink()

    result = runner.invoke(main, ["health", "--scope", "skills"])

    assert skills_rows(result) == [], result.output
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# Scenario 7 — the scope is a first-class token everywhere
# ---------------------------------------------------------------------------


def test_skills_scope_is_accepted_alone(skills_project, runner):
    result = runner.invoke(main, ["health", "--scope", "skills"])
    assert result.exit_code == 0, result.output


def test_skills_scope_is_accepted_space_separated(skills_project, runner):
    (skills_project / ".claude" / "skills" / "inquest" / "SKILL.md").unlink()

    result = runner.invoke(main, ["health", "--scope", "codex", "skills"])

    assert row_for(result, "missing_skill_file").startswith("ERROR")
    assert result.exit_code == 1, result.output


def test_the_full_scan_includes_the_skills_scope(skills_project, runner):
    (skills_project / ".claude" / "skills" / "inquest" / "SKILL.md").unlink()

    result = runner.invoke(main, ["health"])

    assert row_for(result, "missing_skill_file").startswith("ERROR")
    assert result.exit_code == 1, result.output


def test_an_unknown_scope_still_exits_two_naming_skills(skills_project, runner):
    result = runner.invoke(main, ["health", "--scope", "bogus"])

    assert result.exit_code == 2, result.output
    assert "'bogus' is not one of" in result.stderr
    assert "'skills'" in result.stderr


def test_help_lists_the_skills_scope(runner):
    result = runner.invoke(main, ["health", "--help"])

    assert result.exit_code == 0, result.output
    assert "skills" in result.output


# ---------------------------------------------------------------------------
# Scenario 8 — the Python surface reports the same issues
# ---------------------------------------------------------------------------


def test_python_surface_reports_the_same_issue(skills_project):
    from lore.api import health_check

    (skills_project / ".claude" / "skills" / "inquest" / "SKILL.md").unlink()

    report = health_check(skills_project, scope=["skills"])

    assert len(report.errors) == 1
    issue = report.errors[0]
    assert issue.severity == "error"
    assert issue.entity_type == "skills"
    assert issue.check == "missing_skill_file"
    assert issue.id == ".claude/skills/inquest/SKILL.md"
    assert issue.schema_id is None
    assert issue.rule is None
    assert issue.pointer is None


# ---------------------------------------------------------------------------
# Scenario 9 — the access mode is a thing the scope can see
#
# Round 4 of adversarial smoke testing pasted a whole native render into a cli
# project and left a literal `<!-- lore:access native -->` block in another, and
# both exited 0 with a generic "edited since install". The scope this feature
# added had no assertion about the thing the feature does.
# ---------------------------------------------------------------------------


def _rerecord(project_dir: Path, relative: str, text: str) -> None:
    """Record *text*'s digest for *relative*, so only the new check can fire."""
    from lore.manifest import bytes_digest

    payload = read_manifest(project_dir)
    for row in payload["files"]:
        if row["path"] == relative:
            row["hash"] = bytes_digest(text.encode("utf-8"))
    write_manifest(project_dir, payload)


def _other_mode_render(skill_id: str, relative: str) -> str:
    """The packaged file rendered for the mode `skills_project` did not choose."""
    from lore.initplan import AccessMode
    from lore.skills import rendered_bytes

    return rendered_bytes(skill_id, relative, AccessMode.CLI).decode("utf-8")


def test_a_file_rendered_for_the_other_mode_is_an_error(skills_project, runner):
    relative = ".claude/skills/inquest/SKILL.md"
    (skills_project / relative).write_text(
        _other_mode_render("inquest", "SKILL.md"), encoding="utf-8"
    )

    result = runner.invoke(main, ["health", "--scope", "skills"])

    row = row_for(result, "wrong_access_mode")
    assert row.startswith("ERROR")
    assert relative in row
    assert "'cli'" in row and "'native'" in row
    assert result.exit_code == 1, result.output


def test_the_wrong_mode_verdict_replaces_the_generic_edited_one(skills_project, runner):
    (skills_project / ".claude" / "skills" / "inquest" / "SKILL.md").write_text(
        _other_mode_render("inquest", "SKILL.md"), encoding="utf-8"
    )

    result = runner.invoke(main, ["health", "--scope", "skills"])

    assert not [line for line in skills_rows(result) if "modified_skill_file:" in line]


def test_an_ordinary_edit_is_still_only_a_warning(skills_project, runner):
    target = skills_project / ".claude" / "skills" / "inquest" / "SKILL.md"
    target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    result = runner.invoke(main, ["health", "--scope", "skills"])

    assert row_for(result, "modified_skill_file").startswith("WARNING")
    assert result.exit_code == 0, result.output


def test_an_unrendered_access_marker_is_an_error(skills_project, runner):
    relative = ".claude/skills/inquest/SKILL.md"
    target = skills_project / relative
    text = (
        target.read_text(encoding="utf-8")
        + "\n<!-- lore:access native -->\nsecret\n<!-- lore:access end -->\n"
    )
    target.write_text(text, encoding="utf-8")
    _rerecord(skills_project, relative, text)

    result = runner.invoke(main, ["health", "--scope", "skills"])

    row = row_for(result, "unrendered_access_marker")
    assert row.startswith("ERROR")
    assert relative in row
    assert result.exit_code == 1, result.output


def test_a_clean_install_reports_no_access_mode_issue(skills_project, runner):
    result = runner.invoke(main, ["health", "--scope", "skills"])

    assert skills_rows(result) == [], result.output
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# Scenario 10 — frontmatter is audited on both fields, and against the directory
#
# `description` is the field Claude Code selects a skill on, so a skill without
# one is invisible to the agent; `name` has to equal its directory or the skill
# cannot be invoked. Both used to pass because the file merely *had* a `name`.
# ---------------------------------------------------------------------------


def test_skill_without_description_frontmatter_is_an_error(skills_project, runner):
    relative = ".claude/skills/inquest/SKILL.md"
    text = "---\nname: inquest\n---\n\n# Inquest\n"
    (skills_project / relative).write_text(text, encoding="utf-8")
    _rerecord(skills_project, relative, text)

    result = runner.invoke(main, ["health", "--scope", "skills"])

    row = row_for(result, "missing_skill_frontmatter")
    assert row.startswith("ERROR")
    assert "missing 'description'" in row
    assert result.exit_code == 1, result.output


def test_an_empty_description_is_the_same_error(skills_project, runner):
    relative = ".claude/skills/inquest/SKILL.md"
    text = "---\nname: inquest\ndescription: '   '\n---\n\n# Inquest\n"
    (skills_project / relative).write_text(text, encoding="utf-8")
    _rerecord(skills_project, relative, text)

    result = runner.invoke(main, ["health", "--scope", "skills"])

    assert "missing 'description'" in row_for(result, "missing_skill_frontmatter")
    assert result.exit_code == 1, result.output


def test_a_name_that_disagrees_with_its_directory_is_reported(skills_project, runner):
    relative = ".claude/skills/inquest/SKILL.md"
    text = "---\nname: not-inquest\ndescription: audits finished work\n---\n\n# Inquest\n"
    (skills_project / relative).write_text(text, encoding="utf-8")
    _rerecord(skills_project, relative, text)

    result = runner.invoke(main, ["health", "--scope", "skills"])

    row = row_for(result, "skill_name_mismatch")
    assert "not-inquest" in row and "inquest" in row
    assert result.exit_code == 0, result.output


def test_a_reference_file_is_not_held_to_the_skill_frontmatter_rules(
    skills_project, runner
):
    relative = ".claude/skills/store-memory/references/rite.md"
    text = "no frontmatter at all\n"
    (skills_project / relative).write_text(text, encoding="utf-8")
    _rerecord(skills_project, relative, text)

    result = runner.invoke(main, ["health", "--scope", "skills"])

    assert not [line for line in skills_rows(result) if "frontmatter" in line]
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# A corrupt path in a manifest row: one verdict, both surfaces
# ---------------------------------------------------------------------------
#
# Smoke round 7, N2. A NUL byte in a manifest path is none of the shapes the
# path check rejected, so the row was accepted and the first `lstat` on it
# raised `ValueError: embedded null character in path` — `lore init` exit 1,
# no filename, nothing naming the manifest, and every later run wedged the same
# way until the file was hand-edited. Its siblings (`..`, an absolute path)
# were fail-soft: one warning, the legacy fallback, run completes.
#
# `lore health` meanwhile read the same row happily and reported
# `missing_skill_file`. So the same manifest was fatal to one surface and
# tolerable to the other, and neither said the true thing about it. The rule is
# one rule now, and both surfaces reach the same verdict through it.


CORRUPT_ROW_PATHS = {
    "a NUL inside a path": ".claude/skills/a\x00b.md",
    "a path that walks out": "../VICTIM.txt",
    "an absolute path": "/etc/passwd",
    "a file Lore never installs": ".git/config",
}


def _corrupt_row(project_dir: Path, path: str) -> None:
    payload = read_manifest(project_dir)
    payload["files"].append(
        {
            "path": path,
            "kind": "owned",
            "source": "skill:gone",
            "hash": "sha256:deadbeef",
        }
    )
    write_manifest(project_dir, payload)


@pytest.mark.parametrize(
    "path", list(CORRUPT_ROW_PATHS.values()), ids=list(CORRUPT_ROW_PATHS)
)
def test_a_corrupt_manifest_row_is_one_scan_failure(skills_project, runner, path):
    _corrupt_row(skills_project, path)

    result = runner.invoke(main, ["health", "--scope", "skills"])

    rows = skills_rows(result)
    assert len(rows) == 1, result.output
    assert "skills_scan_failed:" in rows[0]
    assert ".lore/.install-manifest.json" in rows[0]
    assert result.exit_code == 1, result.output


@pytest.mark.parametrize(
    "path", list(CORRUPT_ROW_PATHS.values()), ids=list(CORRUPT_ROW_PATHS)
)
def test_lore_init_survives_the_same_row(skills_project, runner, path):
    """Fail-soft, like every other corrupt manifest — never a wedged project."""
    _corrupt_row(skills_project, path)

    result = runner.invoke(main, ["init", "--agent", "claude", "--yes"])

    assert result.exit_code == 0, result.output + result.stderr
    assert "Traceback" not in result.output + result.stderr


@pytest.mark.parametrize(
    "path", list(CORRUPT_ROW_PATHS.values()), ids=list(CORRUPT_ROW_PATHS)
)
def test_lore_init_names_the_manifest_it_could_not_read(skills_project, runner, path):
    _corrupt_row(skills_project, path)

    result = runner.invoke(main, ["init", "--agent", "claude", "--yes"])

    assert ".install-manifest.json" in result.stderr


@pytest.mark.parametrize(
    "path", list(CORRUPT_ROW_PATHS.values()), ids=list(CORRUPT_ROW_PATHS)
)
def test_the_project_converges_on_the_next_run(skills_project, runner, path):
    """The wedge was the defect: a second run has to leave a readable manifest."""
    _corrupt_row(skills_project, path)
    runner.invoke(main, ["init", "--agent", "claude", "--yes"])

    result = runner.invoke(main, ["health", "--scope", "skills"])

    assert result.exit_code == 0, result.output
