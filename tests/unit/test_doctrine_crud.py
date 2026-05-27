"""Unit tests for `lore.doctrine.update_doctrine` + `delete_doctrine` — G8 Red.

Plan: transient-public-api-facade-plan §G8.
Anchor: decisions-010-public-api-stability + decisions-011-api-parity-with-cli
+ Review-Ledger CHANGED #5 — canonical envelopes are EXACT key sets:
  - update_doctrine → `{name, filename}`
  - delete_doctrine → `{name, deleted: True}`
No `path`, no `ok`, no extras.

Field-preservation merge (id/title/summary) currently in cli.py:1482-1494
MOVES INTO `update_doctrine`. Missing-doctrine and schema-fail surface
through `DoctrineError` (doctrine still uses `DoctrineError`; ValueError
flip is G15.5, not G8 — see mission description).

Red phase — every test below MUST fail until G8 Green lands.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Fixtures — valid + invalid YAML content blocks
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

# New content omitting id/title/summary — to exercise field-preservation merge.
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

# Updated YAML that also supplies its own id/title/summary explicitly.
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

# Schema-invalid: missing required `steps` field.
SCHEMA_INVALID_YAML = (
    "id: tdd\n"
    "title: TDD\n"
    "summary: Missing steps field.\n"
    "description: A doctrine missing the steps field.\n"
)

# Name-mismatch: id field disagrees with the doctrine name passed to update.
NAME_MISMATCH_YAML = (
    "id: not-tdd\n"
    "title: Wrong ID\n"
    "summary: id mismatches caller arg.\n"
    "description: Should be rejected.\n"
    "steps:\n"
    "  - id: red\n"
    "    title: Red\n"
)


# ---------------------------------------------------------------------------
# update_doctrine
# ---------------------------------------------------------------------------


class TestUpdateDoctrineEnvelope:
    """update_doctrine(tmp_path, name, content) — return shape locked."""

    def test_update_doctrine_returns_exact_name_filename_shape(self, tmp_path):
        """update_doctrine returns {id, filename, updated_at: None} per field-edit parity."""
        from lore.doctrine import update_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        (doctrines_dir / "tdd.yaml").write_text(VALID_DOCTRINE_YAML)
        result = update_doctrine(tmp_path, "tdd", FULL_UPDATED_DOCTRINE_YAML)
        assert result == {"id": "tdd", "filename": "tdd.yaml", "updated_at": None}

    def test_update_doctrine_return_keys_are_exactly_name_and_filename(self, tmp_path):
        """update_doctrine return dict key set is {id, filename, updated_at}."""
        from lore.doctrine import update_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        (doctrines_dir / "tdd.yaml").write_text(VALID_DOCTRINE_YAML)
        result = update_doctrine(tmp_path, "tdd", FULL_UPDATED_DOCTRINE_YAML)
        assert set(result.keys()) == {"id", "filename", "updated_at"}

    def test_update_doctrine_return_has_no_path_key(self, tmp_path):
        """update_doctrine return dict MUST NOT contain a 'path' key (FLAG #3)."""
        from lore.doctrine import update_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        (doctrines_dir / "tdd.yaml").write_text(VALID_DOCTRINE_YAML)
        result = update_doctrine(tmp_path, "tdd", FULL_UPDATED_DOCTRINE_YAML)
        assert "path" not in result

    def test_update_doctrine_return_has_no_ok_key(self, tmp_path):
        """update_doctrine return dict MUST NOT contain an 'ok' key (CHANGED #5)."""
        from lore.doctrine import update_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        (doctrines_dir / "tdd.yaml").write_text(VALID_DOCTRINE_YAML)
        result = update_doctrine(tmp_path, "tdd", FULL_UPDATED_DOCTRINE_YAML)
        assert "ok" not in result

    def test_update_doctrine_return_has_no_name_key(self, tmp_path):
        """update_doctrine envelope uses 'id' post-G16 (was 'name')."""
        from lore.doctrine import update_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        (doctrines_dir / "tdd.yaml").write_text(VALID_DOCTRINE_YAML)
        result = update_doctrine(tmp_path, "tdd", FULL_UPDATED_DOCTRINE_YAML)
        # G16 standardization wave: rename of `name`→`id`.
        assert "name" not in result


class TestUpdateDoctrineDiskBehaviour:
    """update_doctrine writes to disk + preserves filename + group location."""

    def test_update_doctrine_overwrites_file_with_new_content(self, tmp_path):
        """update_doctrine writes merged content to the existing .yaml file."""
        from lore.doctrine import update_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        path = doctrines_dir / "tdd.yaml"
        path.write_text(VALID_DOCTRINE_YAML)
        update_doctrine(tmp_path, "tdd", FULL_UPDATED_DOCTRINE_YAML)
        new_text = path.read_text()
        # New content present
        assert "Updated description." in new_text
        assert "TDD v2" in new_text

    def test_update_doctrine_does_not_create_extra_files(self, tmp_path):
        """update_doctrine leaves only the single existing .yaml — no copies."""
        from lore.doctrine import update_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        (doctrines_dir / "tdd.yaml").write_text(VALID_DOCTRINE_YAML)
        update_doctrine(tmp_path, "tdd", FULL_UPDATED_DOCTRINE_YAML)
        yaml_files = sorted(p.name for p in doctrines_dir.glob("*.yaml"))
        assert yaml_files == ["tdd.yaml"]


class TestUpdateDoctrineFieldPreservationMerge:
    """update_doctrine preserves id/title/summary when caller omits them.

    Mirrors the cli.py:1482-1494 merge that moves INTO the op fn per G8 plan.
    """

    def test_update_doctrine_preserves_existing_id_when_omitted(self, tmp_path):
        """Omitted id in new content → existing id stays on disk."""
        import yaml

        from lore.doctrine import update_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        path = doctrines_dir / "tdd.yaml"
        path.write_text(VALID_DOCTRINE_YAML)
        update_doctrine(tmp_path, "tdd", PARTIAL_DOCTRINE_YAML)
        merged = yaml.safe_load(path.read_text())
        assert merged.get("id") == "tdd"

    def test_update_doctrine_preserves_existing_title_when_omitted(self, tmp_path):
        """Omitted title in new content → existing title stays on disk."""
        import yaml

        from lore.doctrine import update_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        path = doctrines_dir / "tdd.yaml"
        path.write_text(VALID_DOCTRINE_YAML)
        update_doctrine(tmp_path, "tdd", PARTIAL_DOCTRINE_YAML)
        merged = yaml.safe_load(path.read_text())
        assert merged.get("title") == "TDD"

    def test_update_doctrine_preserves_existing_summary_when_omitted(self, tmp_path):
        """Omitted summary in new content → existing summary stays on disk."""
        import yaml

        from lore.doctrine import update_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        path = doctrines_dir / "tdd.yaml"
        path.write_text(VALID_DOCTRINE_YAML)
        update_doctrine(tmp_path, "tdd", PARTIAL_DOCTRINE_YAML)
        merged = yaml.safe_load(path.read_text())
        assert merged.get("summary") == "Test-driven development workflow."

    def test_update_doctrine_uses_new_value_when_field_provided(self, tmp_path):
        """Provided title/summary in new content OVERRIDES existing values."""
        import yaml

        from lore.doctrine import update_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        path = doctrines_dir / "tdd.yaml"
        path.write_text(VALID_DOCTRINE_YAML)
        update_doctrine(tmp_path, "tdd", FULL_UPDATED_DOCTRINE_YAML)
        merged = yaml.safe_load(path.read_text())
        assert merged.get("title") == "TDD v2"
        assert merged.get("summary") == "Updated TDD doctrine."

    def test_update_doctrine_applies_new_description_and_steps(self, tmp_path):
        """New description + steps from caller content land on disk."""
        import yaml

        from lore.doctrine import update_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        path = doctrines_dir / "tdd.yaml"
        path.write_text(VALID_DOCTRINE_YAML)
        update_doctrine(tmp_path, "tdd", PARTIAL_DOCTRINE_YAML)
        merged = yaml.safe_load(path.read_text())
        assert merged.get("description") == "Updated description for TDD."
        step_ids = [s.get("id") for s in merged.get("steps", [])]
        assert step_ids == ["red", "green", "refactor"]


class TestUpdateDoctrineErrorPaths:
    """update_doctrine raises DoctrineError on missing + schema failures."""

    def test_update_doctrine_missing_raises_doctrine_error(self, tmp_path):
        """update_doctrine raises DoctrineError when target doctrine absent."""
        from lore.doctrine import update_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            update_doctrine(tmp_path, "nonexistent", FULL_UPDATED_DOCTRINE_YAML)

    def test_update_doctrine_missing_dir_raises_doctrine_error(self, tmp_path):
        """update_doctrine raises DoctrineError when doctrines_dir absent."""
        from lore.doctrine import update_doctrine

        _doctrines_dir = tmp_path / ".lore" / "doctrines"
        # do NOT mkdir
        with pytest.raises(ValueError):
            update_doctrine(tmp_path, "tdd", FULL_UPDATED_DOCTRINE_YAML)

    def test_update_doctrine_schema_failure_propagates_doctrine_error(self, tmp_path):
        """Schema-invalid content propagates DoctrineError from validation."""
        from lore.doctrine import update_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        (doctrines_dir / "tdd.yaml").write_text(VALID_DOCTRINE_YAML)
        with pytest.raises(ValueError):
            update_doctrine(tmp_path, "tdd", SCHEMA_INVALID_YAML)

    def test_update_doctrine_schema_failure_does_not_modify_file(self, tmp_path):
        """Schema-invalid content leaves the existing file untouched."""
        from lore.doctrine import update_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        path = doctrines_dir / "tdd.yaml"
        path.write_text(VALID_DOCTRINE_YAML)
        with pytest.raises(ValueError):
            update_doctrine(tmp_path, "tdd", SCHEMA_INVALID_YAML)
        # original content untouched on disk
        assert path.read_text() == VALID_DOCTRINE_YAML

    def test_update_doctrine_name_mismatch_raises_doctrine_error(self, tmp_path):
        """update_doctrine rejects content whose id disagrees with caller name."""
        from lore.doctrine import update_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        (doctrines_dir / "tdd.yaml").write_text(VALID_DOCTRINE_YAML)
        with pytest.raises(ValueError):
            update_doctrine(tmp_path, "tdd", NAME_MISMATCH_YAML)


# ---------------------------------------------------------------------------
# delete_doctrine
# ---------------------------------------------------------------------------


class TestDeleteDoctrineEnvelope:
    """delete_doctrine(tmp_path, name) — return shape locked."""

    def test_delete_doctrine_returns_exact_name_deleted_shape(self, tmp_path):
        """delete_doctrine returns EXACTLY {name, deleted: True} — no extras."""
        from lore.doctrine import delete_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        (doctrines_dir / "tdd.yaml").write_text(VALID_DOCTRINE_YAML)
        result = delete_doctrine(tmp_path, "tdd")
        assert result == {"id": "tdd", "deleted": True, "deleted_at": None}

    def test_delete_doctrine_return_keys_are_exactly_name_and_deleted(self, tmp_path):
        """delete_doctrine return dict key set is EXACTLY {'name', 'deleted'}."""
        from lore.doctrine import delete_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        (doctrines_dir / "tdd.yaml").write_text(VALID_DOCTRINE_YAML)
        result = delete_doctrine(tmp_path, "tdd")
        assert set(result.keys()) == {"id", "deleted", "deleted_at"}

    def test_delete_doctrine_return_has_no_path_key(self, tmp_path):
        """delete_doctrine return dict MUST NOT contain a 'path' key (FLAG #3)."""
        from lore.doctrine import delete_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        (doctrines_dir / "tdd.yaml").write_text(VALID_DOCTRINE_YAML)
        result = delete_doctrine(tmp_path, "tdd")
        assert "path" not in result

    def test_delete_doctrine_return_has_no_ok_key(self, tmp_path):
        """delete_doctrine return dict MUST NOT contain an 'ok' key (CHANGED #5)."""
        from lore.doctrine import delete_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        (doctrines_dir / "tdd.yaml").write_text(VALID_DOCTRINE_YAML)
        result = delete_doctrine(tmp_path, "tdd")
        assert "ok" not in result

    def test_delete_doctrine_return_has_no_name_key(self, tmp_path):
        """delete_doctrine uses 'id' post-G16 (was 'name')."""
        from lore.doctrine import delete_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        (doctrines_dir / "tdd.yaml").write_text(VALID_DOCTRINE_YAML)
        result = delete_doctrine(tmp_path, "tdd")
        # G16 standardization: name → id.
        assert "name" not in result

    def test_delete_doctrine_deleted_value_is_true_literal(self, tmp_path):
        """delete_doctrine result['deleted'] is literally True, not truthy-equivalent."""
        from lore.doctrine import delete_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        (doctrines_dir / "tdd.yaml").write_text(VALID_DOCTRINE_YAML)
        result = delete_doctrine(tmp_path, "tdd")
        assert result["deleted"] is True


class TestDeleteDoctrineDiskBehaviour:
    """delete_doctrine soft-deletes via .yaml → .yaml.deleted rename."""

    def test_delete_doctrine_renames_yaml_to_yaml_deleted(self, tmp_path):
        """delete_doctrine renames .yaml -> .yaml.deleted on disk."""
        from lore.doctrine import delete_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        path = doctrines_dir / "tdd.yaml"
        path.write_text(VALID_DOCTRINE_YAML)
        delete_doctrine(tmp_path, "tdd")
        assert not path.exists()
        assert (doctrines_dir / "tdd.yaml.deleted").exists()

    def test_delete_doctrine_soft_delete_preserves_content(self, tmp_path):
        """delete_doctrine .yaml.deleted file contains original YAML content."""
        from lore.doctrine import delete_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        path = doctrines_dir / "tdd.yaml"
        path.write_text(VALID_DOCTRINE_YAML)
        delete_doctrine(tmp_path, "tdd")
        assert (doctrines_dir / "tdd.yaml.deleted").read_text() == VALID_DOCTRINE_YAML


class TestDeleteDoctrineErrorPaths:
    """delete_doctrine raises DoctrineError on missing target."""

    def test_delete_doctrine_missing_raises_doctrine_error(self, tmp_path):
        """delete_doctrine on missing doctrine raises DoctrineError (not idempotent).

        Per G8 chunk spec line 166: 'Raises `DoctrineError` on miss.'
        Mission note: 'per chunk spec delete missing raises'.
        """
        from lore.doctrine import delete_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            delete_doctrine(tmp_path, "ghost")

    def test_delete_doctrine_missing_dir_raises_doctrine_error(self, tmp_path):
        """delete_doctrine raises DoctrineError when doctrines_dir absent."""
        from lore.doctrine import delete_doctrine

        _doctrines_dir = tmp_path / ".lore" / "doctrines"
        # do NOT mkdir
        with pytest.raises(ValueError):
            delete_doctrine(tmp_path, "tdd")

    def test_delete_doctrine_second_delete_raises_doctrine_error(self, tmp_path):
        """delete_doctrine is NOT idempotent — second delete of already-deleted raises."""
        from lore.doctrine import delete_doctrine

        doctrines_dir = tmp_path / ".lore" / "doctrines"
        doctrines_dir.mkdir(parents=True)
        (doctrines_dir / "tdd.yaml").write_text(VALID_DOCTRINE_YAML)
        first = delete_doctrine(tmp_path, "tdd")
        assert first == {"id": "tdd", "deleted": True, "deleted_at": None}
        with pytest.raises(ValueError):
            delete_doctrine(tmp_path, "tdd")
