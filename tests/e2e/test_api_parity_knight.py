"""E2E parity tests for `lore knight new / edit / delete` — G7 Red.

Plan: transient-public-api-facade-plan §G7.
Anchor: decisions-011-api-parity-with-cli — when CRUD ops migrate to
`lore.knight.{create,update,delete}_knight` op fns, the user-visible CLI
behaviour (exit code, stdout, stderr, JSON envelope keys) MUST remain
byte-identical to the pre-refactor surface.

These tests pin the parity contract for the refactor that lands in G7
Green. They define the externally observable behaviour the CLI MUST
preserve once it stops doing inline frontmatter parsing + soft-delete
rename and instead delegates to op fns whose return shapes are EXACTLY
`{id, filename}` (update) and `{id, deleted: True}` (delete).

Red phase — every test MUST fail until G7 Green lands (whether by op-fn
absence or CLI envelope drift).
"""

from __future__ import annotations

import json

from lore.cli import main


# Valid knight body fixture used across scenarios.
PERSONA_MD = (
    "---\n"
    "id: {name}\n"
    "title: T\n"
    "summary: S\n"
    "---\n"
    "# body\n"
)

PERSONA_NO_SUMMARY_MD = (
    "---\n"
    "id: reviewer\n"
    "title: Reviewer\n"
    "---\n"
    "# body\n"
)


# ---------------------------------------------------------------------------
# `lore knight edit` — parity contract
# ---------------------------------------------------------------------------


class TestKnightEditParity:
    """`lore knight edit` JSON envelope + exit + stderr unchanged through G7."""

    def _seed(self, project_dir, name: str = "reviewer") -> None:
        knights = project_dir / ".lore" / "knights"
        knights.mkdir(parents=True, exist_ok=True)
        (knights / f"{name}.md").write_text(PERSONA_MD.format(name=name))

    def test_edit_existing_knight_exit_zero(self, runner, project_dir):
        """knight edit on existing knight exits 0."""
        self._seed(project_dir, "reviewer")
        (project_dir / "new.md").write_text(PERSONA_MD.format(name="reviewer"))
        result = runner.invoke(
            main, ["knight", "edit", "reviewer", "--from", str(project_dir / "new.md")]
        )
        assert result.exit_code == 0

    def test_edit_existing_knight_stdout_message(self, runner, project_dir):
        """knight edit stdout exactly 'Updated knight {name}'."""
        self._seed(project_dir, "reviewer")
        (project_dir / "new.md").write_text(PERSONA_MD.format(name="reviewer"))
        result = runner.invoke(
            main, ["knight", "edit", "reviewer", "--from", str(project_dir / "new.md")]
        )
        assert result.output.strip() == "Updated knight reviewer"

    def test_edit_existing_knight_json_envelope_is_id_filename_exact(
        self, runner, project_dir
    ):
        """knight edit --json returns EXACTLY {id, filename} — no path, no ok."""
        self._seed(project_dir, "reviewer")
        (project_dir / "new.md").write_text(PERSONA_MD.format(name="reviewer"))
        result = runner.invoke(
            main,
            [
                "--json",
                "knight",
                "edit",
                "reviewer",
                "--from",
                str(project_dir / "new.md"),
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload == {"id": "reviewer", "filename": "reviewer.md", "updated_at": None}

    def test_edit_existing_knight_json_has_no_path_key(self, runner, project_dir):
        """knight edit --json MUST NOT include a 'path' key (FLAG #3)."""
        self._seed(project_dir, "reviewer")
        (project_dir / "new.md").write_text(PERSONA_MD.format(name="reviewer"))
        result = runner.invoke(
            main,
            [
                "--json",
                "knight",
                "edit",
                "reviewer",
                "--from",
                str(project_dir / "new.md"),
            ],
        )
        payload = json.loads(result.output)
        assert "path" not in payload

    def test_edit_existing_knight_json_has_no_ok_key(self, runner, project_dir):
        """knight edit --json MUST NOT include an 'ok' key (CHANGED #5)."""
        self._seed(project_dir, "reviewer")
        (project_dir / "new.md").write_text(PERSONA_MD.format(name="reviewer"))
        result = runner.invoke(
            main,
            [
                "--json",
                "knight",
                "edit",
                "reviewer",
                "--from",
                str(project_dir / "new.md"),
            ],
        )
        payload = json.loads(result.output)
        assert "ok" not in payload

    def test_edit_existing_knight_json_uses_id_not_name(self, runner, project_dir):
        """knight edit --json uses 'id' key (watcher canonical), not 'name'."""
        self._seed(project_dir, "reviewer")
        (project_dir / "new.md").write_text(PERSONA_MD.format(name="reviewer"))
        result = runner.invoke(
            main,
            [
                "--json",
                "knight",
                "edit",
                "reviewer",
                "--from",
                str(project_dir / "new.md"),
            ],
        )
        payload = json.loads(result.output)
        assert "id" in payload
        assert payload["id"] == "reviewer"

    def test_edit_missing_knight_exit_one(self, runner, project_dir):
        """knight edit on missing knight exits 1."""
        (project_dir / "new.md").write_text(PERSONA_MD.format(name="ghost"))
        result = runner.invoke(
            main, ["knight", "edit", "ghost", "--from", str(project_dir / "new.md")]
        )
        assert result.exit_code == 1

    def test_edit_missing_knight_stderr_contains_not_found(self, runner, project_dir):
        """knight edit on missing knight surfaces a 'not found' message."""
        (project_dir / "new.md").write_text(PERSONA_MD.format(name="ghost"))
        result = runner.invoke(
            main, ["knight", "edit", "ghost", "--from", str(project_dir / "new.md")]
        )
        combined = result.output + (result.stderr if hasattr(result, "stderr") else "")
        assert "not found" in combined.lower()
        assert "ghost" in combined

    def test_edit_invalid_frontmatter_exit_one(self, runner, project_dir):
        """knight edit with invalid frontmatter exits 1."""
        self._seed(project_dir, "reviewer")
        (project_dir / "bad.md").write_text(PERSONA_NO_SUMMARY_MD)
        result = runner.invoke(
            main, ["knight", "edit", "reviewer", "--from", str(project_dir / "bad.md")]
        )
        assert result.exit_code == 1

    def test_edit_invalid_frontmatter_stderr_contains_summary(
        self, runner, project_dir
    ):
        """knight edit with invalid frontmatter surfaces the schema golden text."""
        self._seed(project_dir, "reviewer")
        (project_dir / "bad.md").write_text(PERSONA_NO_SUMMARY_MD)
        result = runner.invoke(
            main, ["knight", "edit", "reviewer", "--from", str(project_dir / "bad.md")]
        )
        combined = (result.output or "") + (
            result.stderr if hasattr(result, "stderr") else ""
        )
        assert "Missing required property 'summary'" in combined

    def test_edit_invalid_frontmatter_does_not_modify_file(
        self, runner, project_dir
    ):
        """knight edit with invalid frontmatter leaves original file intact."""
        self._seed(project_dir, "reviewer")
        original = (project_dir / ".lore" / "knights" / "reviewer.md").read_text()
        (project_dir / "bad.md").write_text(PERSONA_NO_SUMMARY_MD)
        runner.invoke(
            main, ["knight", "edit", "reviewer", "--from", str(project_dir / "bad.md")]
        )
        assert (
            project_dir / ".lore" / "knights" / "reviewer.md"
        ).read_text() == original


# ---------------------------------------------------------------------------
# `lore knight delete` — parity contract
# ---------------------------------------------------------------------------


class TestKnightDeleteParity:
    """`lore knight delete` JSON envelope + exit + stderr unchanged through G7."""

    def _seed(self, project_dir, name: str = "reviewer") -> None:
        knights = project_dir / ".lore" / "knights"
        knights.mkdir(parents=True, exist_ok=True)
        (knights / f"{name}.md").write_text(PERSONA_MD.format(name=name))

    def test_delete_existing_knight_exit_zero(self, runner, project_dir):
        """knight delete on existing knight exits 0."""
        self._seed(project_dir, "reviewer")
        result = runner.invoke(main, ["knight", "delete", "reviewer"])
        assert result.exit_code == 0

    def test_delete_existing_knight_stdout_message(self, runner, project_dir):
        """knight delete stdout exactly 'Deleted knight {name}'."""
        self._seed(project_dir, "reviewer")
        result = runner.invoke(main, ["knight", "delete", "reviewer"])
        assert result.output.strip() == "Deleted knight reviewer"

    def test_delete_existing_knight_soft_deletes_file(self, runner, project_dir):
        """knight delete renames .md to .md.deleted on disk."""
        self._seed(project_dir, "reviewer")
        runner.invoke(main, ["knight", "delete", "reviewer"])
        assert not (project_dir / ".lore" / "knights" / "reviewer.md").exists()
        assert (project_dir / ".lore" / "knights" / "reviewer.md.deleted").exists()

    def test_delete_existing_knight_json_envelope_is_id_deleted_exact(
        self, runner, project_dir
    ):
        """knight delete --json returns EXACTLY {id, deleted: True} — no path, no ok."""
        self._seed(project_dir, "reviewer")
        result = runner.invoke(main, ["--json", "knight", "delete", "reviewer"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload == {"id": "reviewer", "deleted": True, "deleted_at": None}

    def test_delete_existing_knight_json_has_no_path_key(self, runner, project_dir):
        """knight delete --json MUST NOT include a 'path' key."""
        self._seed(project_dir, "reviewer")
        result = runner.invoke(main, ["--json", "knight", "delete", "reviewer"])
        payload = json.loads(result.output)
        assert "path" not in payload

    def test_delete_existing_knight_json_has_no_ok_key(self, runner, project_dir):
        """knight delete --json MUST NOT include an 'ok' key."""
        self._seed(project_dir, "reviewer")
        result = runner.invoke(main, ["--json", "knight", "delete", "reviewer"])
        payload = json.loads(result.output)
        assert "ok" not in payload

    def test_delete_existing_knight_json_uses_id_not_name(self, runner, project_dir):
        """knight delete --json uses 'id' (watcher canonical), not 'name'."""
        self._seed(project_dir, "reviewer")
        result = runner.invoke(main, ["--json", "knight", "delete", "reviewer"])
        payload = json.loads(result.output)
        assert payload.get("id") == "reviewer"

    def test_delete_missing_knight_exit_one(self, runner, project_dir):
        """knight delete on missing knight exits 1."""
        result = runner.invoke(main, ["knight", "delete", "ghost"])
        assert result.exit_code == 1

    def test_delete_missing_knight_stderr_contains_not_found(
        self, runner, project_dir
    ):
        """knight delete on missing knight surfaces a 'not found' message."""
        result = runner.invoke(main, ["knight", "delete", "ghost"])
        stderr = result.stderr if hasattr(result, "stderr") else ""
        combined = (result.output or "") + (stderr or "")
        assert "not found" in combined.lower()
        assert "ghost" in combined


# ---------------------------------------------------------------------------
# `lore knight new` — parity guard (must keep working through the refactor)
# ---------------------------------------------------------------------------


class TestKnightNewParity:
    """`lore knight new` exit + stdout + json parity through the G7 refactor.

    G7 refactors the CLI handler to drop its inline frontmatter parse and
    delegate to `create_knight` (whose `_validate_frontmatter` is invoked
    internally). User-visible surface MUST stay identical.
    """

    def test_new_root_exit_zero(self, runner, project_dir):
        """knight new from file with valid content exits 0."""
        (project_dir / "p.md").write_text(PERSONA_MD.format(name="reviewer"))
        result = runner.invoke(
            main, ["knight", "new", "reviewer", "--from", str(project_dir / "p.md")]
        )
        assert result.exit_code == 0

    def test_new_root_stdout_message(self, runner, project_dir):
        """knight new from file with valid content prints 'Created knight {name}'."""
        (project_dir / "p.md").write_text(PERSONA_MD.format(name="reviewer"))
        result = runner.invoke(
            main, ["knight", "new", "reviewer", "--from", str(project_dir / "p.md")]
        )
        assert result.output.strip() == "Created knight reviewer"

    def test_new_missing_summary_exit_one(self, runner, project_dir):
        """knight new with missing-summary frontmatter exits 1 (golden parity)."""
        (project_dir / "p.md").write_text(PERSONA_NO_SUMMARY_MD)
        result = runner.invoke(
            main, ["knight", "new", "reviewer", "--from", str(project_dir / "p.md")]
        )
        assert result.exit_code == 1

    def test_new_missing_summary_stderr_golden_text(self, runner, project_dir):
        """knight new with missing-summary surfaces 'Missing required property summary'."""
        (project_dir / "p.md").write_text(PERSONA_NO_SUMMARY_MD)
        result = runner.invoke(
            main, ["knight", "new", "reviewer", "--from", str(project_dir / "p.md")]
        )
        stderr = result.stderr if hasattr(result, "stderr") else ""
        combined = (result.output or "") + (stderr or "")
        assert "Missing required property 'summary'" in combined

    def test_new_missing_summary_no_file_written(self, runner, project_dir):
        """knight new with missing-summary leaves no file on disk."""
        (project_dir / "p.md").write_text(PERSONA_NO_SUMMARY_MD)
        runner.invoke(
            main, ["knight", "new", "reviewer", "--from", str(project_dir / "p.md")]
        )
        assert not (project_dir / ".lore" / "knights" / "reviewer.md").exists()
