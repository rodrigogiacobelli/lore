"""Unit tests for codex CRUD — Red phase.

Spec: ``transient-codex-crud-spec`` Sections A + D.

Covers ``create_document`` / ``update_document`` / ``delete_document``
on ``lore.codex``, re-exported via ``lore.api``.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


CODEX_DOC = (
    "---\n"
    "id: my-doc\n"
    "title: My Doc\n"
    "summary: A test doc.\n"
    "---\n"
    "# body\n"
)


def _make_doc(doc_id: str, *, related: list[str] | None = None, extra: str = "") -> str:
    """Build a minimal codex doc with optional related list."""
    lines = ["---", f"id: {doc_id}", f"title: {doc_id.title()}", "summary: Test."]
    if related is not None:
        lines.append("related:")
        for r in related:
            lines.append(f"  - {r}")
    if extra:
        lines.append(extra)
    lines.extend(["---", "# body", ""])
    return "\n".join(lines)


@pytest.fixture()
def project_root(tmp_path):
    (tmp_path / ".lore" / "codex").mkdir(parents=True)
    return tmp_path


# ---------------------------------------------------------------------------
# Section D Test 1 — create envelope.
# ---------------------------------------------------------------------------


class TestCreateDocument:
    def test_minimum_envelope(self, project_root):
        from lore.api import create_document

        env = create_document(project_root, "my-doc", CODEX_DOC)
        assert env == {
            "id": "my-doc",
            "filename": "my-doc.md",
            "group": None,
            "doc_type": "codex",
        }
        assert (project_root / ".lore" / "codex" / "my-doc.md").exists()

    def test_group_derives_codex_source(self, project_root):
        from lore.api import create_document

        content = _make_doc("rk-001", related=["alpha"])
        env = create_document(
            project_root, "rk-001", content, group="sources/realm"
        )
        assert env["doc_type"] == "codex-source"
        assert env["group"] == "sources/realm"
        assert env["filename"] == "rk-001.md"
        assert (
            project_root / ".lore" / "codex" / "sources" / "realm" / "rk-001.md"
        ).exists()

    def test_group_codex_source_minitems_required(self, project_root):
        """codex-source schema requires related minItems: 1."""
        from lore.api import create_document

        # Build a doc with NO related field
        content = _make_doc("rk-002")
        with pytest.raises(ValueError):
            create_document(
                project_root, "rk-002", content, group="sources/realm"
            )

    def test_explicit_doc_type_overrides_group(self, project_root):
        """--type codex-source on a non-sources group."""
        from lore.api import create_document

        content = _make_doc("custom-src", related=["alpha"])
        env = create_document(
            project_root,
            "custom-src",
            content,
            group="standards",
            doc_type="codex-source",
        )
        assert env["doc_type"] == "codex-source"

    def test_explicit_doc_type_codex_in_sources_group(self, project_root):
        """--type codex overrides sources/ default."""
        from lore.api import create_document

        content = _make_doc("non-source")
        env = create_document(
            project_root,
            "non-source",
            content,
            group="sources/x",
            doc_type="codex",
        )
        assert env["doc_type"] == "codex"

    def test_unknown_doc_type_rejected(self, project_root):
        from lore.api import create_document

        with pytest.raises(ValueError, match="Unknown doc_type"):
            create_document(
                project_root, "abc", CODEX_DOC, doc_type="bogus-type"
            )

    def test_id_mismatch_rejected(self, project_root):
        """Frontmatter id must match filename."""
        from lore.api import create_document

        content = _make_doc("wrong-id")
        with pytest.raises(ValueError, match="does not match filename"):
            create_document(project_root, "my-doc", content)
        # No file should be created
        assert not (project_root / ".lore" / "codex" / "my-doc.md").exists()

    def test_duplicate_subtree_rejected(self, project_root):
        from lore.api import create_document

        codex = project_root / ".lore" / "codex"
        (codex / "decisions").mkdir()
        (codex / "decisions" / "my-doc.md").write_text(CODEX_DOC)
        # Try to create same id in a different group
        with pytest.raises(ValueError, match="already exists"):
            create_document(project_root, "my-doc", CODEX_DOC, group="standards")

    def test_empty_content_rejected(self, project_root):
        from lore.api import create_document

        with pytest.raises(ValueError, match="empty"):
            create_document(project_root, "my-doc", "")

    def test_missing_frontmatter_rejected(self, project_root):
        from lore.api import create_document

        with pytest.raises(ValueError):
            create_document(project_root, "my-doc", "no frontmatter here")


# ---------------------------------------------------------------------------
# Section D Test 6/7 — update.
# ---------------------------------------------------------------------------


class TestUpdateDocument:
    def test_partial_merge_preserves_fields(self, project_root):
        """Update with only title set — id/summary/related/binds preserved."""
        from lore.api import update_document

        original = (
            "---\n"
            "id: my-doc\n"
            "title: Old Title\n"
            "summary: Original.\n"
            "related:\n"
            "  - alpha\n"
            "binds:\n"
            "  - src/x.py\n"
            "---\n"
            "# body\n"
        )
        (project_root / ".lore" / "codex" / "my-doc.md").write_text(original)

        # New content has only id + title (preserving id, changing title)
        new_content = (
            "---\n"
            "id: my-doc\n"
            "title: New Title\n"
            "---\n"
            "# body\n"
        )
        env = update_document(project_root, "my-doc", new_content)
        assert env["id"] == "my-doc"
        assert env["filename"] == "my-doc.md"
        assert env["updated_at"] is None
        assert env["doc_type"] == "codex"

        # Re-read file: title updated, related and binds preserved
        import yaml
        text = (project_root / ".lore" / "codex" / "my-doc.md").read_text()
        meta = yaml.safe_load(text.split("---", 2)[1])
        assert meta["title"] == "New Title"
        assert meta["summary"] == "Original."
        assert meta["related"] == ["alpha"]
        assert meta["binds"] == ["src/x.py"]

    def test_ambiguous_name_raises(self, project_root):
        from lore.api import update_document

        codex = project_root / ".lore" / "codex"
        (codex / "a").mkdir()
        (codex / "b").mkdir()
        doc_a = (
            "---\nid: overview\ntitle: A\nsummary: A.\n---\n# a\n"
        )
        doc_b = (
            "---\nid: overview\ntitle: B\nsummary: B.\n---\n# b\n"
        )
        (codex / "a" / "overview.md").write_text(doc_a)
        (codex / "b" / "overview.md").write_text(doc_b)

        with pytest.raises(ValueError, match="ambiguous"):
            update_document(project_root, "overview", doc_a)

    def test_not_found_raises(self, project_root):
        from lore.api import update_document

        with pytest.raises(ValueError, match="not found"):
            update_document(project_root, "ghost", CODEX_DOC)


# ---------------------------------------------------------------------------
# Section D Test 8/9/10 — delete.
# ---------------------------------------------------------------------------


class TestDeleteDocument:
    @pytest.mark.parametrize("reserved_id", ["codex"])
    def test_seeded_id_protected(self, project_root, reserved_id):
        from lore.api import delete_document

        codex = project_root / ".lore" / "codex"
        (codex / "codex.md").write_text(
            "---\nid: codex\ntitle: Codex\nsummary: Root.\n---\n# body\n"
        )
        with pytest.raises(ValueError, match="protected"):
            delete_document(project_root, reserved_id)
        # File still exists
        assert (codex / "codex.md").exists()

    def test_hard_rename_to_dot_deleted(self, project_root):
        from lore.api import delete_document, list_codex

        codex = project_root / ".lore" / "codex"
        (codex / "decisions").mkdir()
        target = codex / "decisions" / "foo.md"
        target.write_text(
            "---\nid: foo\ntitle: Foo\nsummary: Foo doc.\n---\n# body\n"
        )

        env = delete_document(project_root, "foo")
        assert env == {
            "id": "foo",
            "deleted": True,
            "deleted_at": None,
            "group": "decisions",
            "doc_type": "codex",
        }
        assert not target.exists()
        assert (codex / "decisions" / "foo.md.deleted").exists()

        # list_codex no longer returns the doc
        ids = {d["id"] for d in list_codex(project_root)}
        assert "foo" not in ids

    def test_idempotent_on_already_deleted(self, project_root):
        from lore.api import delete_document

        codex = project_root / ".lore" / "codex"
        target = codex / "foo.md"
        target.write_text(
            "---\nid: foo\ntitle: Foo\nsummary: F.\n---\n# body\n"
        )
        delete_document(project_root, "foo")
        # Second call: no raise, same envelope shape
        env = delete_document(project_root, "foo")
        assert env["id"] == "foo"
        assert env["deleted"] is True
        assert env["deleted_at"] is None

    def test_not_found_raises(self, project_root):
        from lore.api import delete_document

        with pytest.raises(ValueError, match="not found"):
            delete_document(project_root, "ghost")


# ---------------------------------------------------------------------------
# Public API surface.
# ---------------------------------------------------------------------------


class TestApiSurface:
    def test_create_document_in_api_all(self):
        from lore import api

        assert "create_document" in api.__all__

    def test_update_document_in_api_all(self):
        from lore import api

        assert "update_document" in api.__all__

    def test_delete_document_in_api_all(self):
        from lore import api

        assert "delete_document" in api.__all__
