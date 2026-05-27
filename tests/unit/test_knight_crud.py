"""Unit tests for lore.knight._validate_frontmatter raise type — G2 Red.

Plan: transient-public-api-facade-plan §G2.
Anchor: decisions-011-public-api-stability (ADR-011 — operational modules
must not import or raise click).

These tests fix the raise contract of ``knight._validate_frontmatter``
to ``ValueError`` (was ``click.ClickException``). The CLI translator in
``cli.py`` must continue to emit identical stderr + exit code for bad
frontmatter input.

Red phase — all tests below MUST fail until G2 Green lands.
"""

from __future__ import annotations

import click
import pytest

import lore.knight as _k_mod
import lore.schemas as _schemas


# ---------------------------------------------------------------------------
# Unit — _validate_frontmatter raise type is ValueError (not ClickException)
# ---------------------------------------------------------------------------


def test_validate_frontmatter_raises_value_error_on_issues(monkeypatch):
    """knight._validate_frontmatter raises ValueError when schema returns issues."""
    issue = _schemas.SchemaIssue(
        rule="required",
        pointer="/",
        message="Missing required property 'summary'.",
    )
    monkeypatch.setattr(_schemas, "validate_entity", lambda k, d: [issue])
    if hasattr(_k_mod, "validate_entity"):
        monkeypatch.setattr(_k_mod, "validate_entity", lambda k, d: [issue])

    with pytest.raises(ValueError) as exc:
        _k_mod._validate_frontmatter({"id": "pm", "title": "PM"})
    assert "Missing required property 'summary'" in str(exc.value)


def test_validate_frontmatter_does_not_raise_click_exception(monkeypatch):
    """knight._validate_frontmatter MUST NOT raise click.ClickException — ADR-011."""
    issue = _schemas.SchemaIssue(
        rule="required",
        pointer="/",
        message="Missing required property 'summary'.",
    )
    monkeypatch.setattr(_schemas, "validate_entity", lambda k, d: [issue])
    if hasattr(_k_mod, "validate_entity"):
        monkeypatch.setattr(_k_mod, "validate_entity", lambda k, d: [issue])

    # ClickException is NOT a ValueError — catch only Click would now miss.
    # Assert that catching only ClickException no longer catches the raise.
    with pytest.raises(ValueError):
        try:
            _k_mod._validate_frontmatter({"id": "pm", "title": "PM"})
        except click.ClickException:  # pragma: no cover — must not match
            pytest.fail(
                "knight._validate_frontmatter raised click.ClickException; "
                "ADR-011 requires plain ValueError."
            )


def test_validate_frontmatter_real_missing_summary_raises_value_error():
    """Real (unmocked) schema run: missing summary raises ValueError with golden text."""
    with pytest.raises(ValueError) as exc:
        _k_mod._validate_frontmatter({"id": "pm", "title": "PM"})
    assert "Missing required property 'summary'" in str(exc.value)


def test_validate_frontmatter_no_raise_on_valid_input():
    """Valid frontmatter dict must not raise anything (regression guard)."""
    # Should be a no-op; if it raises ValueError on valid input, contract broken.
    _k_mod._validate_frontmatter({"id": "pm", "title": "PM", "summary": "s"})


# ---------------------------------------------------------------------------
# G7 — read_knight, update_knight, delete_knight (CRUD parity with watcher).
# Plan: transient-public-api-facade-plan §G7.
# Anchor: decisions-010-public-api-stability + Review-Ledger CHANGED #5 —
# canonical envelopes are `{id, filename}` for update and
# `{id, deleted: True}` for delete. NO `path`, NO `ok` keys (FLAG #3).
# ---------------------------------------------------------------------------


VALID_KNIGHT_MD = (
    "---\n"
    "id: pm\n"
    "title: PM\n"
    "summary: Product manager persona.\n"
    "---\n"
    "# PM body\n"
)

UPDATED_KNIGHT_MD = (
    "---\n"
    "id: pm\n"
    "title: PM\n"
    "summary: Updated product manager persona.\n"
    "---\n"
    "# PM updated body\n"
)

INVALID_FRONTMATTER_MD = (
    "---\n"
    "id: pm\n"
    "title: PM\n"
    "---\n"
    "# missing summary\n"
)


# ---------------------------------------------------------------------------
# read_knight
# ---------------------------------------------------------------------------


class TestReadKnight:
    """read_knight(tmp_path, name) — unit tests for G7."""

    def test_read_knight_returns_file_body_string_on_hit(self, tmp_path):
        """read_knight returns the full file contents as a str when found."""
        from lore.knight import read_knight

        knights_dir = tmp_path / ".lore" / "knights"
        knights_dir.mkdir(parents=True)
        (knights_dir / "pm.md").write_text(VALID_KNIGHT_MD)
        knight_record = read_knight(tmp_path, "pm")
        assert knight_record is not None
        assert knight_record["body"] == "# PM body\n"

    def test_read_knight_returns_none_on_miss(self, tmp_path):
        """read_knight returns None when the knight does not exist."""
        from lore.knight import read_knight

        knights_dir = tmp_path / ".lore" / "knights"
        knights_dir.mkdir(parents=True)
        assert read_knight(tmp_path, "nonexistent") is None

    def test_read_knight_returns_none_when_dir_missing(self, tmp_path):
        """read_knight returns None when knights_dir itself does not exist."""
        from lore.knight import read_knight

        _knights_dir = tmp_path / ".lore" / "knights"
        # do not mkdir — directory absent
        assert read_knight(tmp_path, "pm") is None

    def test_read_knight_rejects_path_traversal_via_find_knight_guard(self, tmp_path):
        """read_knight must raise ValueError on path-traversal name (find_knight guard)."""
        from lore.knight import read_knight

        knights_dir = tmp_path / ".lore" / "knights"
        knights_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            read_knight(tmp_path, "../etc/passwd")

    def test_read_knight_rejects_backslash_path_traversal(self, tmp_path):
        """read_knight rejects names containing backslashes (Windows-style traversal)."""
        from lore.knight import read_knight

        knights_dir = tmp_path / ".lore" / "knights"
        knights_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            read_knight(tmp_path, "..\\etc\\passwd")

    def test_read_knight_finds_nested_group(self, tmp_path):
        """read_knight resolves a knight stored under a group subdirectory."""
        from lore.knight import read_knight

        knights_dir = tmp_path / ".lore" / "knights"
        nested = knights_dir / "feature-implementation"
        nested.mkdir(parents=True)
        (nested / "scout.md").write_text(VALID_KNIGHT_MD)
        rec = read_knight(tmp_path, "scout")
        assert rec is not None
        assert rec["id"] == "pm"  # id comes from frontmatter

    def test_read_knight_returns_dict_type(self, tmp_path):
        """read_knight return type is dict on hit (post-G16, was str)."""
        from lore.knight import read_knight

        knights_dir = tmp_path / ".lore" / "knights"
        knights_dir.mkdir(parents=True)
        (knights_dir / "pm.md").write_text(VALID_KNIGHT_MD)
        result = read_knight(tmp_path, "pm")
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# update_knight
# ---------------------------------------------------------------------------


class TestUpdateKnight:
    """update_knight(tmp_path, name, content) — unit tests for G7."""

    def test_update_knight_returns_exact_id_filename_shape(self, tmp_path):
        """update_knight returns {id, filename, updated_at: None} per field-edit parity."""
        from lore.knight import update_knight

        knights_dir = tmp_path / ".lore" / "knights"
        knights_dir.mkdir(parents=True)
        (knights_dir / "pm.md").write_text(VALID_KNIGHT_MD)
        result = update_knight(tmp_path, "pm", UPDATED_KNIGHT_MD)
        assert result == {"id": "pm", "filename": "pm.md", "updated_at": None}

    def test_update_knight_return_keys_are_exactly_id_and_filename(self, tmp_path):
        """update_knight return dict key set is {id, filename, updated_at}."""
        from lore.knight import update_knight

        knights_dir = tmp_path / ".lore" / "knights"
        knights_dir.mkdir(parents=True)
        (knights_dir / "pm.md").write_text(VALID_KNIGHT_MD)
        result = update_knight(tmp_path, "pm", UPDATED_KNIGHT_MD)
        assert set(result.keys()) == {"id", "filename", "updated_at"}

    def test_update_knight_return_has_no_path_key(self, tmp_path):
        """update_knight return dict MUST NOT contain a 'path' key (FLAG #3)."""
        from lore.knight import update_knight

        knights_dir = tmp_path / ".lore" / "knights"
        knights_dir.mkdir(parents=True)
        (knights_dir / "pm.md").write_text(VALID_KNIGHT_MD)
        result = update_knight(tmp_path, "pm", UPDATED_KNIGHT_MD)
        assert "path" not in result

    def test_update_knight_return_has_no_ok_key(self, tmp_path):
        """update_knight return dict MUST NOT contain an 'ok' key (Review-Ledger CHANGED #5)."""
        from lore.knight import update_knight

        knights_dir = tmp_path / ".lore" / "knights"
        knights_dir.mkdir(parents=True)
        (knights_dir / "pm.md").write_text(VALID_KNIGHT_MD)
        result = update_knight(tmp_path, "pm", UPDATED_KNIGHT_MD)
        assert "ok" not in result

    def test_update_knight_overwrites_file_with_new_content(self, tmp_path):
        """update_knight writes the new content to the existing file."""
        from lore.knight import update_knight

        knights_dir = tmp_path / ".lore" / "knights"
        knights_dir.mkdir(parents=True)
        knight_file = knights_dir / "pm.md"
        knight_file.write_text(VALID_KNIGHT_MD)
        update_knight(tmp_path, "pm", UPDATED_KNIGHT_MD)
        assert knight_file.read_text() == UPDATED_KNIGHT_MD

    def test_update_knight_raises_value_error_when_not_found(self, tmp_path):
        """update_knight raises ValueError when the knight does not exist."""
        from lore.knight import update_knight

        knights_dir = tmp_path / ".lore" / "knights"
        knights_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            update_knight(tmp_path, "nonexistent", UPDATED_KNIGHT_MD)

    def test_update_knight_raises_value_error_on_invalid_frontmatter(self, tmp_path):
        """update_knight raises ValueError for invalid frontmatter (missing summary)."""
        from lore.knight import update_knight

        knights_dir = tmp_path / ".lore" / "knights"
        knights_dir.mkdir(parents=True)
        (knights_dir / "pm.md").write_text(VALID_KNIGHT_MD)
        with pytest.raises(ValueError) as exc:
            update_knight(tmp_path, "pm", INVALID_FRONTMATTER_MD)
        assert "summary" in str(exc.value).lower()

    def test_update_knight_invalid_frontmatter_does_not_modify_file(self, tmp_path):
        """update_knight rejects invalid frontmatter BEFORE any write reaches disk."""
        from lore.knight import update_knight

        knights_dir = tmp_path / ".lore" / "knights"
        knights_dir.mkdir(parents=True)
        knight_file = knights_dir / "pm.md"
        knight_file.write_text(VALID_KNIGHT_MD)
        with pytest.raises(ValueError):
            update_knight(tmp_path, "pm", INVALID_FRONTMATTER_MD)
        # original content intact
        assert knight_file.read_text() == VALID_KNIGHT_MD

    def test_update_knight_rejects_path_traversal_name(self, tmp_path):
        """update_knight raises ValueError on path-traversal names."""
        from lore.knight import update_knight

        knights_dir = tmp_path / ".lore" / "knights"
        knights_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            update_knight(tmp_path, "../etc/passwd", UPDATED_KNIGHT_MD)

    def test_update_knight_preserves_nested_group_location(self, tmp_path):
        """update_knight does not move the file out of its group subdirectory."""
        from lore.knight import update_knight

        knights_dir = tmp_path / ".lore" / "knights"
        nested = knights_dir / "feature-implementation"
        nested.mkdir(parents=True)
        knight_file = nested / "scout.md"
        knight_file.write_text(VALID_KNIGHT_MD)
        update_knight(tmp_path, "scout", UPDATED_KNIGHT_MD)
        # file stays under feature-implementation/
        assert knight_file.exists()
        assert knight_file.read_text() == UPDATED_KNIGHT_MD
        # MUST NOT appear at the root level
        assert not (knights_dir / "scout.md").exists()


# ---------------------------------------------------------------------------
# delete_knight
# ---------------------------------------------------------------------------


class TestDeleteKnight:
    """delete_knight(tmp_path, name) — unit tests for G7."""

    def test_delete_knight_returns_exact_id_deleted_shape(self, tmp_path):
        """delete_knight returns EXACTLY {id, deleted: True} — no path, no ok."""
        from lore.knight import delete_knight

        knights_dir = tmp_path / ".lore" / "knights"
        knights_dir.mkdir(parents=True)
        (knights_dir / "pm.md").write_text(VALID_KNIGHT_MD)
        result = delete_knight(tmp_path, "pm")
        assert result == {"id": "pm", "deleted": True, "deleted_at": None}

    def test_delete_knight_return_keys_are_exactly_id_and_deleted(self, tmp_path):
        """delete_knight return dict key set is EXACTLY {'id', 'deleted'} — no extras."""
        from lore.knight import delete_knight

        knights_dir = tmp_path / ".lore" / "knights"
        knights_dir.mkdir(parents=True)
        (knights_dir / "pm.md").write_text(VALID_KNIGHT_MD)
        result = delete_knight(tmp_path, "pm")
        assert set(result.keys()) == {"id", "deleted", "deleted_at"}

    def test_delete_knight_return_has_no_path_key(self, tmp_path):
        """delete_knight return dict MUST NOT contain a 'path' key (FLAG #3)."""
        from lore.knight import delete_knight

        knights_dir = tmp_path / ".lore" / "knights"
        knights_dir.mkdir(parents=True)
        (knights_dir / "pm.md").write_text(VALID_KNIGHT_MD)
        result = delete_knight(tmp_path, "pm")
        assert "path" not in result

    def test_delete_knight_return_has_no_ok_key(self, tmp_path):
        """delete_knight return dict MUST NOT contain an 'ok' key (CHANGED #5)."""
        from lore.knight import delete_knight

        knights_dir = tmp_path / ".lore" / "knights"
        knights_dir.mkdir(parents=True)
        (knights_dir / "pm.md").write_text(VALID_KNIGHT_MD)
        result = delete_knight(tmp_path, "pm")
        assert "ok" not in result

    def test_delete_knight_renames_to_md_deleted(self, tmp_path):
        """delete_knight soft-deletes via .md -> .md.deleted rename."""
        from lore.knight import delete_knight

        knights_dir = tmp_path / ".lore" / "knights"
        knights_dir.mkdir(parents=True)
        knight_file = knights_dir / "pm.md"
        knight_file.write_text(VALID_KNIGHT_MD)
        delete_knight(tmp_path, "pm")
        assert not knight_file.exists()
        assert (knights_dir / "pm.md.deleted").exists()

    def test_delete_knight_deleted_file_preserves_content(self, tmp_path):
        """delete_knight — the .md.deleted file contains the original content."""
        from lore.knight import delete_knight

        knights_dir = tmp_path / ".lore" / "knights"
        knights_dir.mkdir(parents=True)
        knight_file = knights_dir / "pm.md"
        knight_file.write_text(VALID_KNIGHT_MD)
        delete_knight(tmp_path, "pm")
        deleted_file = knights_dir / "pm.md.deleted"
        assert deleted_file.read_text() == VALID_KNIGHT_MD

    def test_delete_knight_preserves_group_subdirectory(self, tmp_path):
        """delete_knight renames in place inside a group subdirectory."""
        from lore.knight import delete_knight

        knights_dir = tmp_path / ".lore" / "knights"
        nested = knights_dir / "feature-implementation"
        nested.mkdir(parents=True)
        knight_file = nested / "scout.md"
        knight_file.write_text(VALID_KNIGHT_MD)
        delete_knight(tmp_path, "scout")
        assert not knight_file.exists()
        assert (nested / "scout.md.deleted").exists()

    def test_delete_knight_idempotent_on_already_deleted(self, tmp_path):
        """delete_knight is idempotent: second delete of already-soft-deleted returns same envelope."""
        from lore.knight import delete_knight

        knights_dir = tmp_path / ".lore" / "knights"
        knights_dir.mkdir(parents=True)
        knight_file = knights_dir / "pm.md"
        knight_file.write_text(VALID_KNIGHT_MD)
        first = delete_knight(tmp_path, "pm")
        second = delete_knight(tmp_path, "pm")
        assert first == {"id": "pm", "deleted": True, "deleted_at": None}
        assert second == {"id": "pm", "deleted": True, "deleted_at": None}

    def test_delete_knight_rejects_path_traversal_name(self, tmp_path):
        """delete_knight raises ValueError on path-traversal names."""
        from lore.knight import delete_knight

        knights_dir = tmp_path / ".lore" / "knights"
        knights_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            delete_knight(tmp_path, "../etc/passwd")

    def test_delete_knight_rejects_backslash_path_traversal(self, tmp_path):
        """delete_knight raises ValueError on backslash path-traversal names."""
        from lore.knight import delete_knight

        knights_dir = tmp_path / ".lore" / "knights"
        knights_dir.mkdir(parents=True)
        with pytest.raises(ValueError):
            delete_knight(tmp_path, "..\\etc\\passwd")
