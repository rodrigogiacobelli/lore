"""Unit tests for lore.artifact._validate_frontmatter raise type — G2 Red.

Plan: transient-public-api-facade-plan §G2.
Anchor: decisions-011-public-api-stability (ADR-011 — operational modules
must not import or raise click).

These tests fix the raise contract of ``artifact._validate_frontmatter``
to ``ValueError`` (was ``click.ClickException``). The CLI translator in
``cli.py`` must continue to emit identical stderr + exit code for bad
frontmatter input.

Red phase — all tests below MUST fail until G2 Green lands.
"""

from __future__ import annotations

import click
import pytest

import lore.artifact as _a_mod
import lore.schemas as _schemas


# ---------------------------------------------------------------------------
# Unit — _validate_frontmatter raise type is ValueError (not ClickException)
# ---------------------------------------------------------------------------


def test_validate_frontmatter_raises_value_error_on_issues(monkeypatch):
    """artifact._validate_frontmatter raises ValueError when schema returns issues."""
    issue = _schemas.SchemaIssue(
        rule="required",
        pointer="/",
        message="Missing required property 'summary'.",
    )
    monkeypatch.setattr(_schemas, "validate_entity", lambda k, d: [issue])
    if hasattr(_a_mod, "validate_entity"):
        monkeypatch.setattr(_a_mod, "validate_entity", lambda k, d: [issue])

    with pytest.raises(ValueError) as exc:
        _a_mod._validate_frontmatter({"id": "x", "title": "T"})
    assert "Missing required property 'summary'" in str(exc.value)


def test_validate_frontmatter_does_not_raise_click_exception(monkeypatch):
    """artifact._validate_frontmatter MUST NOT raise click.ClickException — ADR-011."""
    issue = _schemas.SchemaIssue(
        rule="required",
        pointer="/",
        message="Missing required property 'summary'.",
    )
    monkeypatch.setattr(_schemas, "validate_entity", lambda k, d: [issue])
    if hasattr(_a_mod, "validate_entity"):
        monkeypatch.setattr(_a_mod, "validate_entity", lambda k, d: [issue])

    with pytest.raises(ValueError):
        try:
            _a_mod._validate_frontmatter({"id": "x", "title": "T"})
        except click.ClickException:  # pragma: no cover — must not match
            pytest.fail(
                "artifact._validate_frontmatter raised click.ClickException; "
                "ADR-011 requires plain ValueError."
            )


def test_validate_frontmatter_rejects_group_key_with_value_error():
    """A frontmatter dict carrying 'group' must raise ValueError (was ClickException)."""
    with pytest.raises(ValueError) as exc:
        _a_mod._validate_frontmatter(
            {"id": "x", "title": "T", "summary": "s", "group": "foo"}
        )
    msg = str(exc.value)
    assert (
        "additionalProperties" in msg
        or "/group" in msg
        or ("group" in msg and "Unknown property" in msg)
    )


def test_validate_frontmatter_no_raise_on_valid_input():
    """Valid frontmatter dict must not raise anything (regression guard)."""
    _a_mod._validate_frontmatter({"id": "x", "title": "T", "summary": "s"})


# ---------------------------------------------------------------------------
# G10 — update_artifact, delete_artifact (CRUD parity with watcher / knight).
# Plan: transient-public-api-facade-plan §G10.
# Anchor: decisions-007-artifact-communication-protocol (Amendment —
# artifact mutation via `lore.api` is in scope) + decisions-010-public-api-stability.
# Canonical envelopes (Review-Ledger CHANGED #5 / FLAG #3):
#   update_artifact -> {id, filename}            (no path, no ok)
#   delete_artifact -> {id, deleted: True}       (no path, no ok)
# ---------------------------------------------------------------------------


VALID_ARTIFACT_MD = (
    "---\n"
    "id: tpl\n"
    "title: Template\n"
    "summary: A reusable artifact template.\n"
    "---\n"
    "# Template body\n"
)

UPDATED_ARTIFACT_MD = (
    "---\n"
    "id: tpl\n"
    "title: Template\n"
    "summary: Updated reusable artifact template.\n"
    "---\n"
    "# Updated template body\n"
)

ARTIFACT_INVALID_FRONTMATTER_MD = (
    "---\n"
    "id: tpl\n"
    "title: Template\n"
    "---\n"
    "# missing summary\n"
)


# ---------------------------------------------------------------------------
# update_artifact
# ---------------------------------------------------------------------------


class TestUpdateArtifact:
    """update_artifact(tmp_path, name, content) — unit tests for G10."""

    def test_update_artifact_returns_exact_id_filename_shape(self, tmp_path):
        """update_artifact returns {id, filename, updated_at: None} per field-edit parity."""
        from lore.artifact import update_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        (artifacts_dir / "tpl.md").write_text(VALID_ARTIFACT_MD)
        result = update_artifact(tmp_path, "tpl", UPDATED_ARTIFACT_MD)
        assert result == {"id": "tpl", "filename": "tpl.md", "updated_at": None}

    def test_update_artifact_return_keys_are_exactly_id_and_filename(self, tmp_path):
        """update_artifact return dict key set is {id, filename, updated_at}."""
        from lore.artifact import update_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        (artifacts_dir / "tpl.md").write_text(VALID_ARTIFACT_MD)
        result = update_artifact(tmp_path, "tpl", UPDATED_ARTIFACT_MD)
        assert set(result.keys()) == {"id", "filename", "updated_at"}

    def test_update_artifact_return_has_no_path_key(self, tmp_path):
        """update_artifact return dict MUST NOT contain a 'path' key (FLAG #3)."""
        from lore.artifact import update_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        (artifacts_dir / "tpl.md").write_text(VALID_ARTIFACT_MD)
        result = update_artifact(tmp_path, "tpl", UPDATED_ARTIFACT_MD)
        assert "path" not in result

    def test_update_artifact_return_has_no_ok_key(self, tmp_path):
        """update_artifact return dict MUST NOT contain an 'ok' key (CHANGED #5)."""
        from lore.artifact import update_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        (artifacts_dir / "tpl.md").write_text(VALID_ARTIFACT_MD)
        result = update_artifact(tmp_path, "tpl", UPDATED_ARTIFACT_MD)
        assert "ok" not in result

    def test_update_artifact_overwrites_file_with_new_content(self, tmp_path):
        """update_artifact writes the new content to the existing file."""
        from lore.artifact import update_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        artifact_file = artifacts_dir / "tpl.md"
        artifact_file.write_text(VALID_ARTIFACT_MD)
        update_artifact(tmp_path, "tpl", UPDATED_ARTIFACT_MD)
        assert artifact_file.read_text() == UPDATED_ARTIFACT_MD

    def test_update_artifact_raises_value_error_when_not_found(self, tmp_path):
        """update_artifact raises ValueError when the artifact does not exist."""
        from lore.artifact import update_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            update_artifact(tmp_path, "nonexistent", UPDATED_ARTIFACT_MD)

    def test_update_artifact_raises_value_error_on_invalid_frontmatter(self, tmp_path):
        """update_artifact runs frontmatter validation INSIDE — raises ValueError."""
        from lore.artifact import update_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        (artifacts_dir / "tpl.md").write_text(VALID_ARTIFACT_MD)
        with pytest.raises(ValueError) as exc:
            update_artifact(tmp_path, "tpl", ARTIFACT_INVALID_FRONTMATTER_MD)
        assert "summary" in str(exc.value).lower()

    def test_update_artifact_invalid_frontmatter_does_not_modify_file(self, tmp_path):
        """update_artifact rejects invalid frontmatter BEFORE any write reaches disk."""
        from lore.artifact import update_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        artifact_file = artifacts_dir / "tpl.md"
        artifact_file.write_text(VALID_ARTIFACT_MD)
        with pytest.raises(ValueError):
            update_artifact(tmp_path, "tpl", ARTIFACT_INVALID_FRONTMATTER_MD)
        # original content intact
        assert artifact_file.read_text() == VALID_ARTIFACT_MD

    def test_update_artifact_raises_on_missing_frontmatter_block(self, tmp_path):
        """update_artifact runs frontmatter parse INSIDE op fn (not in CLI)."""
        from lore.artifact import update_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        (artifacts_dir / "tpl.md").write_text(VALID_ARTIFACT_MD)
        with pytest.raises(ValueError):
            update_artifact(tmp_path, "tpl", "no frontmatter at all\n")

    def test_update_artifact_rejects_path_traversal_name(self, tmp_path):
        """update_artifact raises ValueError on path-traversal names."""
        from lore.artifact import update_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            update_artifact(tmp_path, "../etc/passwd", UPDATED_ARTIFACT_MD)

    def test_update_artifact_preserves_nested_group_location(self, tmp_path):
        """update_artifact does not move the file out of its group subdirectory."""
        from lore.artifact import update_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        nested = artifacts_dir / "codex-templates"
        nested.mkdir(parents=True)
        artifact_file = nested / "tpl.md"
        artifact_file.write_text(VALID_ARTIFACT_MD)
        update_artifact(tmp_path, "tpl", UPDATED_ARTIFACT_MD)
        # file stays under codex-templates/
        assert artifact_file.exists()
        assert artifact_file.read_text() == UPDATED_ARTIFACT_MD
        # MUST NOT appear at the root level
        assert not (artifacts_dir / "tpl.md").exists()


# ---------------------------------------------------------------------------
# delete_artifact
# ---------------------------------------------------------------------------


class TestDeleteArtifact:
    """delete_artifact(tmp_path, name) — unit tests for G10."""

    def test_delete_artifact_returns_exact_id_deleted_shape(self, tmp_path):
        """delete_artifact returns EXACTLY {id, deleted: True} — no path, no ok."""
        from lore.artifact import delete_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        (artifacts_dir / "tpl.md").write_text(VALID_ARTIFACT_MD)
        result = delete_artifact(tmp_path, "tpl")
        assert result == {"id": "tpl", "deleted": True, "deleted_at": None}

    def test_delete_artifact_return_keys_are_exactly_id_and_deleted(self, tmp_path):
        """delete_artifact return dict key set is EXACTLY {'id', 'deleted'} — no extras."""
        from lore.artifact import delete_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        (artifacts_dir / "tpl.md").write_text(VALID_ARTIFACT_MD)
        result = delete_artifact(tmp_path, "tpl")
        assert set(result.keys()) == {"id", "deleted", "deleted_at"}

    def test_delete_artifact_return_has_no_path_key(self, tmp_path):
        """delete_artifact return dict MUST NOT contain a 'path' key (FLAG #3)."""
        from lore.artifact import delete_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        (artifacts_dir / "tpl.md").write_text(VALID_ARTIFACT_MD)
        result = delete_artifact(tmp_path, "tpl")
        assert "path" not in result

    def test_delete_artifact_return_has_no_ok_key(self, tmp_path):
        """delete_artifact return dict MUST NOT contain an 'ok' key (CHANGED #5)."""
        from lore.artifact import delete_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        (artifacts_dir / "tpl.md").write_text(VALID_ARTIFACT_MD)
        result = delete_artifact(tmp_path, "tpl")
        assert "ok" not in result

    def test_delete_artifact_renames_to_md_deleted(self, tmp_path):
        """delete_artifact soft-deletes via .md -> .md.deleted rename."""
        from lore.artifact import delete_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        artifact_file = artifacts_dir / "tpl.md"
        artifact_file.write_text(VALID_ARTIFACT_MD)
        delete_artifact(tmp_path, "tpl")
        assert not artifact_file.exists()
        assert (artifacts_dir / "tpl.md.deleted").exists()

    def test_delete_artifact_deleted_file_preserves_content(self, tmp_path):
        """delete_artifact — the .md.deleted file contains the original content."""
        from lore.artifact import delete_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        artifact_file = artifacts_dir / "tpl.md"
        artifact_file.write_text(VALID_ARTIFACT_MD)
        delete_artifact(tmp_path, "tpl")
        deleted_file = artifacts_dir / "tpl.md.deleted"
        assert deleted_file.read_text() == VALID_ARTIFACT_MD

    def test_delete_artifact_preserves_group_subdirectory(self, tmp_path):
        """delete_artifact renames in place inside a group subdirectory."""
        from lore.artifact import delete_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        nested = artifacts_dir / "codex-templates"
        nested.mkdir(parents=True)
        artifact_file = nested / "tpl.md"
        artifact_file.write_text(VALID_ARTIFACT_MD)
        delete_artifact(tmp_path, "tpl")
        assert not artifact_file.exists()
        assert (nested / "tpl.md.deleted").exists()

    def test_delete_artifact_raises_value_error_when_not_found(self, tmp_path):
        """delete_artifact raises ValueError when artifact does not exist."""
        from lore.artifact import delete_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            delete_artifact(tmp_path, "nonexistent")

    def test_delete_artifact_idempotent_on_already_deleted(self, tmp_path):
        """delete_artifact is idempotent: second delete of already-soft-deleted returns same envelope."""
        from lore.artifact import delete_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        artifact_file = artifacts_dir / "tpl.md"
        artifact_file.write_text(VALID_ARTIFACT_MD)
        first = delete_artifact(tmp_path, "tpl")
        second = delete_artifact(tmp_path, "tpl")
        assert first == {"id": "tpl", "deleted": True, "deleted_at": None}
        assert second == {"id": "tpl", "deleted": True, "deleted_at": None}

    def test_delete_artifact_rejects_path_traversal_name(self, tmp_path):
        """delete_artifact raises ValueError on path-traversal names."""
        from lore.artifact import delete_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            delete_artifact(tmp_path, "../etc/passwd")

    def test_delete_artifact_rejects_backslash_path_traversal(self, tmp_path):
        """delete_artifact raises ValueError on backslash path-traversal names."""
        from lore.artifact import delete_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            delete_artifact(tmp_path, "..\\etc\\passwd")


# ---------------------------------------------------------------------------
# create_artifact — frontmatter validation lives INSIDE op fn (not CLI).
# G10 also drops the duplicate parse in cli.py:artifact_new; this is a unit
# guard that the op fn itself raises ValueError when CLI stops doing it.
# ---------------------------------------------------------------------------


class TestCreateArtifactValidatesFrontmatterInside:
    """create_artifact runs frontmatter validation internally — not in CLI."""

    def test_create_artifact_raises_value_error_on_missing_summary(self, tmp_path):
        """create_artifact raises ValueError when frontmatter lacks summary."""
        from lore.artifact import create_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        with pytest.raises(ValueError) as exc:
            create_artifact(tmp_path, "tpl", ARTIFACT_INVALID_FRONTMATTER_MD)
        assert "summary" in str(exc.value).lower()

    def test_create_artifact_missing_frontmatter_raises_value_error(self, tmp_path):
        """create_artifact raises ValueError when content has no frontmatter block."""
        from lore.artifact import create_artifact

        artifacts_dir = tmp_path / ".lore" / "artifacts"
        artifacts_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            create_artifact(tmp_path, "tpl", "no frontmatter at all\n")
