"""E2E tests for the `lore artifact new` command — US-004.

Spec: group-param-us-004 (lore codex show group-param-us-004)
anchor: conceptual-workflows-artifact-list (first write path)
"""

import json

from lore.cli import main


_VALID_BODY = (
    "---\n"
    "id: fi-review\n"
    "title: Review\n"
    "summary: s\n"
    "---\n"
    "body\n"
)


def _combined(result):
    """Return stdout + stderr for CliRunner result — matches watcher_crud pattern."""
    return (result.output or "") + (
        result.stderr if hasattr(result, "stderr") else ""
    )


# ---------------------------------------------------------------------------
# Scenario 1: Nested artifact create — happy path
# ---------------------------------------------------------------------------


class TestArtifactNewNestedHappyPath:
    """Scenario 1: --group creates nested artifact, exit 0, success message."""

    def test_exit_code_zero(self, runner, project_dir):
        # Spec: US-004 Scenario 1 — exit code 0
        (project_dir / "review.md").write_text(_VALID_BODY)
        result = runner.invoke(
            main,
            [
                "artifact",
                "new",
                "fi-review",
                "--group",
                "codex/templates",
                "--from",
                "review.md",
            ],
        )
        assert result.exit_code == 0

    def test_success_message_exact(self, runner, project_dir):
        # Spec: US-004 Scenario 1 — stdout `Created artifact fi-review (group: codex/templates)`
        (project_dir / "review.md").write_text(_VALID_BODY)
        result = runner.invoke(
            main,
            [
                "artifact",
                "new",
                "fi-review",
                "--group",
                "codex/templates",
                "--from",
                "review.md",
            ],
        )
        assert (
            result.output.strip()
            == "Created artifact fi-review (group: codex/templates)"
        )

    def test_file_written_at_nested_path(self, runner, project_dir):
        # Spec: US-004 Scenario 1 — file at .lore/artifacts/codex/templates/fi-review.md
        (project_dir / "review.md").write_text(_VALID_BODY)
        runner.invoke(
            main,
            [
                "artifact",
                "new",
                "fi-review",
                "--group",
                "codex/templates",
                "--from",
                "review.md",
            ],
        )
        assert (
            project_dir / ".lore/artifacts/codex/templates/fi-review.md"
        ).exists()


# ---------------------------------------------------------------------------
# Scenario 2: Nested artifact create — JSON envelope
# ---------------------------------------------------------------------------


class TestArtifactNewNestedJsonEnvelope:
    """Scenario 2: --json flag returns JSON envelope with id/group/filename/path."""

    def test_json_envelope_exact(self, runner, project_dir):
        # Spec: US-004 Scenario 2 — stdout parses as expected JSON
        (project_dir / "review.md").write_text(_VALID_BODY)
        result = runner.invoke(
            main,
            [
                "artifact",
                "new",
                "fi-review",
                "--group",
                "codex/templates",
                "--from",
                "review.md",
                "--json",
            ],
        )
        assert result.exit_code == 0
        assert json.loads(result.output) == {
            "id": "fi-review",
            "group": "codex/templates",
            "filename": "fi-review.md",
            "path": ".lore/artifacts/codex/templates/fi-review.md",
        }


# ---------------------------------------------------------------------------
# Scenario 3: Root artifact create — --group omitted, JSON group is null
# ---------------------------------------------------------------------------


class TestArtifactNewRootJsonNullGroup:
    """Scenario 3: --group omitted → JSON group is null, file written at root."""

    def test_json_group_is_null(self, runner, project_dir):
        # Spec: US-004 Scenario 3 — JSON `group` key equals null
        body = "---\nid: transient-note\ntitle: T\nsummary: s\n---\nbody\n"
        (project_dir / "note.md").write_text(body)
        result = runner.invoke(
            main,
            ["artifact", "new", "transient-note", "--from", "note.md", "--json"],
        )
        assert result.exit_code == 0
        assert json.loads(result.output)["group"] is None

    def test_file_written_at_artifacts_root(self, runner, project_dir):
        # Spec: US-004 Scenario 3 — file at .lore/artifacts/transient-note.md
        body = "---\nid: transient-note\ntitle: T\nsummary: s\n---\nbody\n"
        (project_dir / "note.md").write_text(body)
        result = runner.invoke(
            main,
            ["artifact", "new", "transient-note", "--from", "note.md", "--json"],
        )
        assert result.exit_code == 0
        assert (project_dir / ".lore/artifacts/transient-note.md").exists()

    def test_success_message_without_group_suffix(self, runner, project_dir):
        # Spec: US-004 — text mode success without group suffix
        body = "---\nid: transient-note\ntitle: T\nsummary: s\n---\nbody\n"
        (project_dir / "note.md").write_text(body)
        result = runner.invoke(
            main, ["artifact", "new", "transient-note", "--from", "note.md"]
        )
        assert result.exit_code == 0
        assert result.output.strip() == "Created artifact transient-note"


# ---------------------------------------------------------------------------
# Scenario 4: Duplicate name anywhere in subtree rejected
# ---------------------------------------------------------------------------


class TestArtifactNewDuplicateSubtreeRejected:
    """Scenario 4: duplicate stem anywhere under .lore/artifacts/ → exit 1, no write."""

    def _seed_existing(self, project_dir):
        existing_dir = project_dir / ".lore/artifacts/default/codex"
        existing_dir.mkdir(parents=True, exist_ok=True)
        (existing_dir / "overview.md").write_text(
            "---\nid: overview\ntitle: T\nsummary: s\n---\nbody\n"
        )
        (project_dir / "o.md").write_text(
            "---\nid: overview\ntitle: T\nsummary: s\n---\nbody\n"
        )

    def test_exit_code_one(self, runner, project_dir):
        # Spec: US-004 Scenario 4 — exit code 1 on subtree duplicate
        self._seed_existing(project_dir)
        result = runner.invoke(
            main,
            ["artifact", "new", "overview", "--group", "other", "--from", "o.md"],
        )
        assert result.exit_code == 1

    def test_stderr_contains_already_exists(self, runner, project_dir):
        # Spec: US-004 Scenario 4 — stderr contains `Error: artifact 'overview' already exists`
        self._seed_existing(project_dir)
        result = runner.invoke(
            main,
            ["artifact", "new", "overview", "--group", "other", "--from", "o.md"],
        )
        combined = _combined(result)
        assert "already exists" in combined
        assert "overview" in combined

    def test_no_file_created_in_new_group(self, runner, project_dir):
        # Spec: US-004 Scenario 4 — error is duplicate AND no file under .lore/artifacts/other/
        self._seed_existing(project_dir)
        result = runner.invoke(
            main,
            ["artifact", "new", "overview", "--group", "other", "--from", "o.md"],
        )
        # Error must come from duplicate detection, not from "no such command"
        assert "already exists" in _combined(result)
        assert not (project_dir / ".lore/artifacts/other").exists()


# ---------------------------------------------------------------------------
# Scenario 5: Missing required frontmatter fields rejected
# ---------------------------------------------------------------------------


class TestArtifactNewMissingFrontmatterRejected:
    """Scenario 5: body missing required frontmatter field → exit 1, stderr names field."""

    def test_exit_code_one(self, runner, project_dir):
        # Spec: US-004 Scenario 5 — missing `summary` → exit 1
        (project_dir / "bad.md").write_text("---\nid: bad-one\ntitle: T\n---\nbody\n")
        result = runner.invoke(
            main, ["artifact", "new", "bad-one", "--from", "bad.md"]
        )
        assert result.exit_code == 1

    def test_stderr_names_missing_field(self, runner, project_dir):
        # Spec: US-004 Scenario 5 — stderr identifies `summary`
        (project_dir / "bad.md").write_text("---\nid: bad-one\ntitle: T\n---\nbody\n")
        result = runner.invoke(
            main, ["artifact", "new", "bad-one", "--from", "bad.md"]
        )
        assert "summary" in _combined(result)

    def test_no_file_written(self, runner, project_dir):
        # Spec: US-004 Scenario 5 — error identifies summary AND no file written
        (project_dir / "bad.md").write_text("---\nid: bad-one\ntitle: T\n---\nbody\n")
        result = runner.invoke(
            main, ["artifact", "new", "bad-one", "--from", "bad.md"]
        )
        # Error must be from frontmatter validation, not from "no such command"
        assert "summary" in _combined(result)
        artifacts_dir = project_dir / ".lore/artifacts"
        assert artifacts_dir.exists()
        assert not any(artifacts_dir.rglob("bad-one.md"))


# ---------------------------------------------------------------------------
# Additional: invalid --group rejected before any filesystem write
# Spec: US-004 Unit AC — validate_group raises before write
# ---------------------------------------------------------------------------


class TestArtifactNewInvalidGroupRejected:
    """Invalid --group values are rejected with exit 1 before writing anything."""

    def test_invalid_group_exit_one(self, runner, project_dir):
        # Spec: US-004 — invalid group like `../escape` rejected
        (project_dir / "review.md").write_text(_VALID_BODY)
        result = runner.invoke(
            main,
            [
                "artifact",
                "new",
                "fi-review",
                "--group",
                "../escape",
                "--from",
                "review.md",
            ],
        )
        assert result.exit_code == 1

    def test_invalid_group_no_file_written(self, runner, project_dir):
        # Spec: US-004 — error identifies group validation AND no file written
        (project_dir / "review.md").write_text(_VALID_BODY)
        result = runner.invoke(
            main,
            [
                "artifact",
                "new",
                "fi-review",
                "--group",
                "../escape",
                "--from",
                "review.md",
            ],
        )
        combined = _combined(result).lower()
        # Error must come from group validation, not from "no such command"
        assert "group" in combined
        artifacts_dir = project_dir / ".lore/artifacts"
        assert artifacts_dir.exists()
        assert not any(artifacts_dir.rglob("fi-review.md"))
