"""E2E parity tests for `lore doctrine edit / delete` — G8 Red.

Plan: transient-public-api-facade-plan §G8.
Anchor: decisions-011-api-parity-with-cli — when CRUD ops migrate to
`lore.doctrine.{update,delete}_doctrine` op fns, the user-visible CLI
behaviour (exit code, stdout, stderr, JSON envelope keys) MUST remain
byte-identical to the pre-refactor surface at cli.py:1423-1529.

These tests pin the parity contract for the refactor that lands in G8
Green. They define the externally observable behaviour the CLI MUST
preserve once it stops doing inline YAML field-preservation + soft-delete
rename and instead delegates to op fns whose return shapes are EXACTLY
`{name, filename}` (update) and `{name, deleted: True}` (delete).

Red phase — every test MUST fail until G8 Green lands (whether by op-fn
absence or CLI envelope drift).
"""

from __future__ import annotations

import json

from lore.cli import main


# ---------------------------------------------------------------------------
# YAML fixtures
# ---------------------------------------------------------------------------


VALID_DOCTRINE_YAML = (
    "id: tdd\n"
    "title: TDD\n"
    "summary: Test-driven development workflow.\n"
    "description: A doctrine for TDD.\n"
    "steps:\n"
    "  - id: red\n"
    "    title: Red\n"
    "  - id: green\n"
    "    title: Green\n"
)

# New content omitting id/title/summary — field-preservation merge target.
PARTIAL_DOCTRINE_YAML = (
    "description: Updated description for TDD.\n"
    "steps:\n"
    "  - id: red\n"
    "    title: Red\n"
    "  - id: green\n"
    "    title: Green\n"
    "  - id: refactor\n"
    "    title: Refactor\n"
)

FULL_UPDATED_DOCTRINE_YAML = (
    "id: tdd\n"
    "title: TDD v2\n"
    "summary: Updated TDD doctrine.\n"
    "description: Updated description.\n"
    "steps:\n"
    "  - id: red\n"
    "    title: Red\n"
    "  - id: green\n"
    "    title: Green\n"
)

SCHEMA_INVALID_YAML = (
    "id: tdd\n"
    "title: TDD\n"
    "summary: Missing steps field.\n"
    "description: A doctrine missing the steps field.\n"
)


def _seed_doctrine(project_dir, name: str = "tdd", body: str = VALID_DOCTRINE_YAML) -> None:
    """Write a valid .yaml into .lore/doctrines/ for test setup."""
    doctrines = project_dir / ".lore" / "doctrines"
    doctrines.mkdir(parents=True, exist_ok=True)
    (doctrines / f"{name}.yaml").write_text(body)


# ---------------------------------------------------------------------------
# `lore doctrine edit` — parity contract
# ---------------------------------------------------------------------------


class TestDoctrineEditParity:
    """`lore doctrine edit` JSON envelope + exit + stderr unchanged through G8."""

    def test_edit_existing_doctrine_exit_zero(self, runner, project_dir):
        """doctrine edit on existing doctrine exits 0."""
        _seed_doctrine(project_dir, "tdd")
        (project_dir / "new.yaml").write_text(FULL_UPDATED_DOCTRINE_YAML)
        result = runner.invoke(
            main,
            ["doctrine", "edit", "tdd", "--from", str(project_dir / "new.yaml")],
        )
        assert result.exit_code == 0

    def test_edit_existing_doctrine_stdout_message(self, runner, project_dir):
        """doctrine edit stdout exactly 'Updated doctrine {name}'."""
        _seed_doctrine(project_dir, "tdd")
        (project_dir / "new.yaml").write_text(FULL_UPDATED_DOCTRINE_YAML)
        result = runner.invoke(
            main,
            ["doctrine", "edit", "tdd", "--from", str(project_dir / "new.yaml")],
        )
        assert result.output.strip() == "Updated doctrine tdd"

    def test_edit_existing_doctrine_json_envelope_is_name_filename_exact(
        self, runner, project_dir
    ):
        """doctrine edit --json returns EXACTLY {name, filename} — no extras."""
        _seed_doctrine(project_dir, "tdd")
        (project_dir / "new.yaml").write_text(FULL_UPDATED_DOCTRINE_YAML)
        result = runner.invoke(
            main,
            [
                "--json",
                "doctrine",
                "edit",
                "tdd",
                "--from",
                str(project_dir / "new.yaml"),
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload == {"id": "tdd", "filename": "tdd.yaml", "updated_at": None}

    def test_edit_existing_doctrine_json_has_no_path_key(self, runner, project_dir):
        """doctrine edit --json MUST NOT include a 'path' key (FLAG #3)."""
        _seed_doctrine(project_dir, "tdd")
        (project_dir / "new.yaml").write_text(FULL_UPDATED_DOCTRINE_YAML)
        result = runner.invoke(
            main,
            [
                "--json",
                "doctrine",
                "edit",
                "tdd",
                "--from",
                str(project_dir / "new.yaml"),
            ],
        )
        payload = json.loads(result.output)
        assert "path" not in payload

    def test_edit_existing_doctrine_json_has_no_ok_key(self, runner, project_dir):
        """doctrine edit --json MUST NOT include an 'ok' key (CHANGED #5)."""
        _seed_doctrine(project_dir, "tdd")
        (project_dir / "new.yaml").write_text(FULL_UPDATED_DOCTRINE_YAML)
        result = runner.invoke(
            main,
            [
                "--json",
                "doctrine",
                "edit",
                "tdd",
                "--from",
                str(project_dir / "new.yaml"),
            ],
        )
        payload = json.loads(result.output)
        assert "ok" not in payload

    def test_edit_existing_doctrine_json_uses_id_not_name(self, runner, project_dir):
        """doctrine edit --json uses 'id' post-G16 (was 'name')."""
        _seed_doctrine(project_dir, "tdd")
        (project_dir / "new.yaml").write_text(FULL_UPDATED_DOCTRINE_YAML)
        result = runner.invoke(
            main,
            [
                "--json",
                "doctrine",
                "edit",
                "tdd",
                "--from",
                str(project_dir / "new.yaml"),
            ],
        )
        payload = json.loads(result.output)
        assert payload.get("id") == "tdd"
        assert "name" not in payload

    def test_edit_partial_content_preserves_existing_fields_on_disk(
        self, runner, project_dir
    ):
        """doctrine edit with partial content preserves id/title/summary on disk."""
        import yaml

        _seed_doctrine(project_dir, "tdd")
        (project_dir / "new.yaml").write_text(PARTIAL_DOCTRINE_YAML)
        result = runner.invoke(
            main,
            ["doctrine", "edit", "tdd", "--from", str(project_dir / "new.yaml")],
        )
        assert result.exit_code == 0
        merged = yaml.safe_load(
            (project_dir / ".lore" / "doctrines" / "tdd.yaml").read_text()
        )
        assert merged.get("id") == "tdd"
        assert merged.get("title") == "TDD"
        assert merged.get("summary") == "Test-driven development workflow."
        # New fields landed
        assert merged.get("description") == "Updated description for TDD."

    def test_edit_missing_doctrine_exit_one(self, runner, project_dir):
        """doctrine edit on missing doctrine exits 1."""
        (project_dir / "new.yaml").write_text(FULL_UPDATED_DOCTRINE_YAML)
        result = runner.invoke(
            main,
            ["doctrine", "edit", "ghost", "--from", str(project_dir / "new.yaml")],
        )
        assert result.exit_code == 1

    def test_edit_missing_doctrine_stderr_contains_not_found(
        self, runner, project_dir
    ):
        """doctrine edit on missing doctrine surfaces a 'not found' message."""
        (project_dir / "new.yaml").write_text(FULL_UPDATED_DOCTRINE_YAML)
        result = runner.invoke(
            main,
            ["doctrine", "edit", "ghost", "--from", str(project_dir / "new.yaml")],
        )
        combined = (result.output or "") + (
            result.stderr if hasattr(result, "stderr") else ""
        )
        assert "not found" in combined.lower()
        assert "ghost" in combined

    def test_edit_invalid_schema_exit_one(self, runner, project_dir):
        """doctrine edit with schema-invalid content exits 1."""
        _seed_doctrine(project_dir, "tdd")
        (project_dir / "bad.yaml").write_text(SCHEMA_INVALID_YAML)
        result = runner.invoke(
            main, ["doctrine", "edit", "tdd", "--from", str(project_dir / "bad.yaml")]
        )
        assert result.exit_code == 1

    def test_edit_invalid_schema_does_not_modify_file(self, runner, project_dir):
        """doctrine edit with invalid schema leaves the existing file untouched."""
        _seed_doctrine(project_dir, "tdd")
        original = (
            project_dir / ".lore" / "doctrines" / "tdd.yaml"
        ).read_text()
        (project_dir / "bad.yaml").write_text(SCHEMA_INVALID_YAML)
        runner.invoke(
            main, ["doctrine", "edit", "tdd", "--from", str(project_dir / "bad.yaml")]
        )
        assert (
            project_dir / ".lore" / "doctrines" / "tdd.yaml"
        ).read_text() == original


# ---------------------------------------------------------------------------
# `lore doctrine delete` — parity contract
# ---------------------------------------------------------------------------


class TestDoctrineDeleteParity:
    """`lore doctrine delete` JSON envelope + exit + stderr unchanged through G8."""

    def test_delete_existing_doctrine_exit_zero(self, runner, project_dir):
        """doctrine delete on existing doctrine exits 0."""
        _seed_doctrine(project_dir, "tdd")
        result = runner.invoke(main, ["doctrine", "delete", "tdd"])
        assert result.exit_code == 0

    def test_delete_existing_doctrine_stdout_message(self, runner, project_dir):
        """doctrine delete stdout exactly 'Deleted doctrine {name}'."""
        _seed_doctrine(project_dir, "tdd")
        result = runner.invoke(main, ["doctrine", "delete", "tdd"])
        assert result.output.strip() == "Deleted doctrine tdd"

    def test_delete_existing_doctrine_soft_deletes_yaml(self, runner, project_dir):
        """doctrine delete renames .yaml -> .yaml.deleted on disk."""
        _seed_doctrine(project_dir, "tdd")
        runner.invoke(main, ["doctrine", "delete", "tdd"])
        assert not (project_dir / ".lore" / "doctrines" / "tdd.yaml").exists()
        assert (
            project_dir / ".lore" / "doctrines" / "tdd.yaml.deleted"
        ).exists()

    def test_delete_existing_doctrine_json_envelope_is_name_deleted_exact(
        self, runner, project_dir
    ):
        """doctrine delete --json returns EXACTLY {name, deleted: True} — no extras."""
        _seed_doctrine(project_dir, "tdd")
        result = runner.invoke(main, ["--json", "doctrine", "delete", "tdd"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload == {"id": "tdd", "deleted": True, "deleted_at": None}

    def test_delete_existing_doctrine_json_has_no_path_key(self, runner, project_dir):
        """doctrine delete --json MUST NOT include a 'path' key."""
        _seed_doctrine(project_dir, "tdd")
        result = runner.invoke(main, ["--json", "doctrine", "delete", "tdd"])
        payload = json.loads(result.output)
        assert "path" not in payload

    def test_delete_existing_doctrine_json_has_no_ok_key(self, runner, project_dir):
        """doctrine delete --json MUST NOT include an 'ok' key."""
        _seed_doctrine(project_dir, "tdd")
        result = runner.invoke(main, ["--json", "doctrine", "delete", "tdd"])
        payload = json.loads(result.output)
        assert "ok" not in payload

    def test_delete_existing_doctrine_json_uses_id_not_name(self, runner, project_dir):
        """doctrine delete --json uses 'id' post-G16 (was 'name')."""
        _seed_doctrine(project_dir, "tdd")
        result = runner.invoke(main, ["--json", "doctrine", "delete", "tdd"])
        payload = json.loads(result.output)
        assert payload.get("id") == "tdd"
        assert "name" not in payload

    def test_delete_missing_doctrine_exit_one(self, runner, project_dir):
        """doctrine delete on missing doctrine exits 1."""
        result = runner.invoke(main, ["doctrine", "delete", "ghost"])
        assert result.exit_code == 1

    def test_delete_missing_doctrine_stderr_contains_not_found(
        self, runner, project_dir
    ):
        """doctrine delete on missing doctrine surfaces a 'not found' message."""
        result = runner.invoke(main, ["doctrine", "delete", "ghost"])
        stderr = result.stderr if hasattr(result, "stderr") else ""
        combined = (result.output or "") + (stderr or "")
        assert "not found" in combined.lower()
        assert "ghost" in combined
