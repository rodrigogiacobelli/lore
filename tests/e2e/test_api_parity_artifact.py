"""E2E parity tests for `lore artifact new / edit / delete` — G10 Red.

Plan: transient-public-api-facade-plan §G10.
Anchor: decisions-007-artifact-communication-protocol (Amendment — artifact
mutation via `lore.api` in scope) + decisions-011-api-parity-with-cli — once
CRUD ops migrate to `lore.artifact.{create,update,delete}_artifact` op fns,
the user-visible CLI behaviour (exit code, stdout, stderr, JSON envelope
keys) MUST match the watcher canonical envelopes for the brand-new `edit`
and `delete` subcommands (which DO NOT exist today — Review-Ledger CHANGED
#11), and `artifact new` MUST keep its existing surface from the caller's
perspective.

These tests pin the parity contract for G10 Green. They define the
externally observable behaviour the new subcommands MUST honour and the
existing `artifact new` MUST preserve once the CLI stops doing its inline
frontmatter parse and delegates fully to the op fn.

Red phase — every test MUST fail until G10 Green lands (whether by op-fn
absence, CLI subcommand absence, or envelope drift).
"""

from __future__ import annotations

import json

from lore.cli import main


# ---------------------------------------------------------------------------
# Markdown fixtures
# ---------------------------------------------------------------------------


ARTIFACT_MD = (
    "---\n"
    "id: {name}\n"
    "title: T\n"
    "summary: S\n"
    "---\n"
    "# body\n"
)

ARTIFACT_UPDATED_MD = (
    "---\n"
    "id: {name}\n"
    "title: T\n"
    "summary: Updated.\n"
    "---\n"
    "# updated body\n"
)

ARTIFACT_NO_SUMMARY_MD = (
    "---\n"
    "id: tpl\n"
    "title: Template\n"
    "---\n"
    "# body\n"
)


# ---------------------------------------------------------------------------
# `lore artifact edit` — parity contract (subcommand does not exist today)
# ---------------------------------------------------------------------------


class TestArtifactEditParity:
    """`lore artifact edit` JSON envelope + exit + stderr — G10 Green target."""

    def _seed(self, project_dir, name: str = "tpl") -> None:
        artifacts = project_dir / ".lore" / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / f"{name}.md").write_text(ARTIFACT_MD.format(name=name))

    def test_edit_existing_artifact_exit_zero(self, runner, project_dir):
        """artifact edit on existing artifact exits 0."""
        self._seed(project_dir, "tpl")
        (project_dir / "new.md").write_text(ARTIFACT_UPDATED_MD.format(name="tpl"))
        result = runner.invoke(
            main, ["artifact", "edit", "tpl", "--from", str(project_dir / "new.md")]
        )
        assert result.exit_code == 0

    def test_edit_existing_artifact_stdout_message(self, runner, project_dir):
        """artifact edit stdout exactly 'Updated artifact {name}'."""
        self._seed(project_dir, "tpl")
        (project_dir / "new.md").write_text(ARTIFACT_UPDATED_MD.format(name="tpl"))
        result = runner.invoke(
            main, ["artifact", "edit", "tpl", "--from", str(project_dir / "new.md")]
        )
        assert result.output.strip() == "Updated artifact tpl"

    def test_edit_existing_artifact_json_envelope_is_id_filename_exact(
        self, runner, project_dir
    ):
        """artifact edit --json returns EXACTLY {id, filename} — no path, no ok."""
        self._seed(project_dir, "tpl")
        (project_dir / "new.md").write_text(ARTIFACT_UPDATED_MD.format(name="tpl"))
        result = runner.invoke(
            main,
            [
                "--json",
                "artifact",
                "edit",
                "tpl",
                "--from",
                str(project_dir / "new.md"),
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload == {"id": "tpl", "filename": "tpl.md", "updated_at": None}

    def test_edit_existing_artifact_json_has_no_path_key(self, runner, project_dir):
        """artifact edit --json MUST NOT include a 'path' key (FLAG #3)."""
        self._seed(project_dir, "tpl")
        (project_dir / "new.md").write_text(ARTIFACT_UPDATED_MD.format(name="tpl"))
        result = runner.invoke(
            main,
            [
                "--json",
                "artifact",
                "edit",
                "tpl",
                "--from",
                str(project_dir / "new.md"),
            ],
        )
        payload = json.loads(result.output)
        assert "path" not in payload

    def test_edit_existing_artifact_json_has_no_ok_key(self, runner, project_dir):
        """artifact edit --json MUST NOT include an 'ok' key (CHANGED #5)."""
        self._seed(project_dir, "tpl")
        (project_dir / "new.md").write_text(ARTIFACT_UPDATED_MD.format(name="tpl"))
        result = runner.invoke(
            main,
            [
                "--json",
                "artifact",
                "edit",
                "tpl",
                "--from",
                str(project_dir / "new.md"),
            ],
        )
        payload = json.loads(result.output)
        assert "ok" not in payload

    def test_edit_existing_artifact_json_uses_id_not_name(self, runner, project_dir):
        """artifact edit --json uses 'id' (watcher canonical), not 'name'."""
        self._seed(project_dir, "tpl")
        (project_dir / "new.md").write_text(ARTIFACT_UPDATED_MD.format(name="tpl"))
        result = runner.invoke(
            main,
            [
                "--json",
                "artifact",
                "edit",
                "tpl",
                "--from",
                str(project_dir / "new.md"),
            ],
        )
        payload = json.loads(result.output)
        assert payload.get("id") == "tpl"
        assert "name" not in payload

    def test_edit_missing_artifact_exit_one(self, runner, project_dir):
        """artifact edit on missing artifact exits 1."""
        (project_dir / "new.md").write_text(ARTIFACT_UPDATED_MD.format(name="ghost"))
        result = runner.invoke(
            main, ["artifact", "edit", "ghost", "--from", str(project_dir / "new.md")]
        )
        assert result.exit_code == 1

    def test_edit_missing_artifact_stderr_contains_not_found(
        self, runner, project_dir
    ):
        """artifact edit on missing artifact surfaces a 'not found' message."""
        (project_dir / "new.md").write_text(ARTIFACT_UPDATED_MD.format(name="ghost"))
        result = runner.invoke(
            main, ["artifact", "edit", "ghost", "--from", str(project_dir / "new.md")]
        )
        combined = (result.output or "") + (
            result.stderr if hasattr(result, "stderr") else ""
        )
        assert "not found" in combined.lower()
        assert "ghost" in combined

    def test_edit_invalid_frontmatter_exit_one(self, runner, project_dir):
        """artifact edit with invalid frontmatter exits 1."""
        self._seed(project_dir, "tpl")
        (project_dir / "bad.md").write_text(ARTIFACT_NO_SUMMARY_MD)
        result = runner.invoke(
            main, ["artifact", "edit", "tpl", "--from", str(project_dir / "bad.md")]
        )
        assert result.exit_code == 1

    def test_edit_invalid_frontmatter_stderr_contains_summary(
        self, runner, project_dir
    ):
        """artifact edit with invalid frontmatter surfaces the schema golden text."""
        self._seed(project_dir, "tpl")
        (project_dir / "bad.md").write_text(ARTIFACT_NO_SUMMARY_MD)
        result = runner.invoke(
            main, ["artifact", "edit", "tpl", "--from", str(project_dir / "bad.md")]
        )
        combined = (result.output or "") + (
            result.stderr if hasattr(result, "stderr") else ""
        )
        assert "Missing required property 'summary'" in combined

    def test_edit_invalid_frontmatter_does_not_modify_file(
        self, runner, project_dir
    ):
        """artifact edit with invalid frontmatter leaves original file intact."""
        self._seed(project_dir, "tpl")
        original = (
            project_dir / ".lore" / "artifacts" / "tpl.md"
        ).read_text()
        (project_dir / "bad.md").write_text(ARTIFACT_NO_SUMMARY_MD)
        runner.invoke(
            main, ["artifact", "edit", "tpl", "--from", str(project_dir / "bad.md")]
        )
        assert (
            project_dir / ".lore" / "artifacts" / "tpl.md"
        ).read_text() == original


# ---------------------------------------------------------------------------
# `lore artifact delete` — parity contract (subcommand does not exist today)
# ---------------------------------------------------------------------------


class TestArtifactDeleteParity:
    """`lore artifact delete` JSON envelope + exit + stderr — G10 Green target."""

    def _seed(self, project_dir, name: str = "tpl") -> None:
        artifacts = project_dir / ".lore" / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / f"{name}.md").write_text(ARTIFACT_MD.format(name=name))

    def test_delete_existing_artifact_exit_zero(self, runner, project_dir):
        """artifact delete on existing artifact exits 0."""
        self._seed(project_dir, "tpl")
        result = runner.invoke(main, ["artifact", "delete", "tpl"])
        assert result.exit_code == 0

    def test_delete_existing_artifact_stdout_message(self, runner, project_dir):
        """artifact delete stdout exactly 'Deleted artifact {name}'."""
        self._seed(project_dir, "tpl")
        result = runner.invoke(main, ["artifact", "delete", "tpl"])
        assert result.output.strip() == "Deleted artifact tpl"

    def test_delete_existing_artifact_soft_deletes_file(self, runner, project_dir):
        """artifact delete renames .md to .md.deleted on disk."""
        self._seed(project_dir, "tpl")
        runner.invoke(main, ["artifact", "delete", "tpl"])
        assert not (project_dir / ".lore" / "artifacts" / "tpl.md").exists()
        assert (
            project_dir / ".lore" / "artifacts" / "tpl.md.deleted"
        ).exists()

    def test_delete_existing_artifact_json_envelope_is_id_deleted_exact(
        self, runner, project_dir
    ):
        """artifact delete --json returns EXACTLY {id, deleted: True} — no path, no ok."""
        self._seed(project_dir, "tpl")
        result = runner.invoke(main, ["--json", "artifact", "delete", "tpl"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload == {"id": "tpl", "deleted": True, "deleted_at": None}

    def test_delete_existing_artifact_json_has_no_path_key(
        self, runner, project_dir
    ):
        """artifact delete --json MUST NOT include a 'path' key."""
        self._seed(project_dir, "tpl")
        result = runner.invoke(main, ["--json", "artifact", "delete", "tpl"])
        payload = json.loads(result.output)
        assert "path" not in payload

    def test_delete_existing_artifact_json_has_no_ok_key(
        self, runner, project_dir
    ):
        """artifact delete --json MUST NOT include an 'ok' key."""
        self._seed(project_dir, "tpl")
        result = runner.invoke(main, ["--json", "artifact", "delete", "tpl"])
        payload = json.loads(result.output)
        assert "ok" not in payload

    def test_delete_existing_artifact_json_uses_id_not_name(
        self, runner, project_dir
    ):
        """artifact delete --json uses 'id' (watcher canonical), not 'name'."""
        self._seed(project_dir, "tpl")
        result = runner.invoke(main, ["--json", "artifact", "delete", "tpl"])
        payload = json.loads(result.output)
        assert payload.get("id") == "tpl"
        assert "name" not in payload

    def test_delete_missing_artifact_exit_one(self, runner, project_dir):
        """artifact delete on missing artifact exits 1."""
        result = runner.invoke(main, ["artifact", "delete", "ghost"])
        assert result.exit_code == 1

    def test_delete_missing_artifact_stderr_contains_not_found(
        self, runner, project_dir
    ):
        """artifact delete on missing artifact surfaces a 'not found' message."""
        result = runner.invoke(main, ["artifact", "delete", "ghost"])
        stderr = result.stderr if hasattr(result, "stderr") else ""
        combined = (result.output or "") + (stderr or "")
        assert "not found" in combined.lower()
        assert "ghost" in combined


# ---------------------------------------------------------------------------
# `lore artifact new` — parity guard (must keep working through G10 refactor)
# ---------------------------------------------------------------------------


class TestArtifactNewParity:
    """`lore artifact new` exit + stdout + json parity through the G10 refactor.

    G10 refactors the CLI handler to drop its inline frontmatter parse and
    delegate to `create_artifact` (whose `_validate_frontmatter` runs
    internally already — artifact.py:55-69). User-visible surface MUST stay
    identical.
    """

    def test_new_root_exit_zero(self, runner, project_dir):
        """artifact new from file with valid content exits 0."""
        (project_dir / "p.md").write_text(ARTIFACT_MD.format(name="tpl"))
        result = runner.invoke(
            main, ["artifact", "new", "tpl", "--from", str(project_dir / "p.md")]
        )
        assert result.exit_code == 0

    def test_new_root_stdout_message(self, runner, project_dir):
        """artifact new from file with valid content prints 'Created artifact {name}'."""
        (project_dir / "p.md").write_text(ARTIFACT_MD.format(name="tpl"))
        result = runner.invoke(
            main, ["artifact", "new", "tpl", "--from", str(project_dir / "p.md")]
        )
        assert result.output.strip() == "Created artifact tpl"

    def test_new_missing_summary_exit_one(self, runner, project_dir):
        """artifact new with missing-summary frontmatter exits 1 (golden parity)."""
        (project_dir / "p.md").write_text(ARTIFACT_NO_SUMMARY_MD)
        result = runner.invoke(
            main, ["artifact", "new", "tpl", "--from", str(project_dir / "p.md")]
        )
        assert result.exit_code == 1

    def test_new_missing_summary_stderr_golden_text(self, runner, project_dir):
        """artifact new with missing-summary surfaces 'Missing required property summary'."""
        (project_dir / "p.md").write_text(ARTIFACT_NO_SUMMARY_MD)
        result = runner.invoke(
            main, ["artifact", "new", "tpl", "--from", str(project_dir / "p.md")]
        )
        stderr = result.stderr if hasattr(result, "stderr") else ""
        combined = (result.output or "") + (stderr or "")
        assert "Missing required property 'summary'" in combined

    def test_new_missing_summary_no_file_written(self, runner, project_dir):
        """artifact new with missing-summary leaves no file on disk."""
        (project_dir / "p.md").write_text(ARTIFACT_NO_SUMMARY_MD)
        runner.invoke(
            main, ["artifact", "new", "tpl", "--from", str(project_dir / "p.md")]
        )
        assert not (
            project_dir / ".lore" / "artifacts" / "tpl.md"
        ).exists()

    def test_new_with_group_exit_zero(self, runner, project_dir):
        """artifact new with --group exits 0."""
        (project_dir / "p.md").write_text(ARTIFACT_MD.format(name="tpl"))
        result = runner.invoke(
            main,
            [
                "artifact",
                "new",
                "tpl",
                "--from",
                str(project_dir / "p.md"),
                "--group",
                "codex-templates",
            ],
        )
        assert result.exit_code == 0

    def test_new_with_group_writes_to_subdir(self, runner, project_dir):
        """artifact new with --group writes to the subdirectory."""
        (project_dir / "p.md").write_text(ARTIFACT_MD.format(name="tpl"))
        runner.invoke(
            main,
            [
                "artifact",
                "new",
                "tpl",
                "--from",
                str(project_dir / "p.md"),
                "--group",
                "codex-templates",
            ],
        )
        assert (
            project_dir / ".lore" / "artifacts" / "codex-templates" / "tpl.md"
        ).exists()
