"""E2E tests for the codex list, search, and show commands.

Spec: conceptual-workflows-codex (lore codex show conceptual-workflows-codex)
"""

import json

import pytest

from lore.cli import main
from lore.codex import scan_codex, read_document, search_documents


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_codex_doc(project_dir, rel_path, content):
    """Helper to write a markdown file into .lore/codex/."""
    doc_path = project_dir / ".lore" / "codex" / rel_path
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(content)
    return doc_path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_DOC = """\
---
id: my-doc
title: My Document
summary: A short summary of my document.
---

# My Document

Body text here.
"""

TRANSIENT_DOC = """\
---
id: transient-placeholder
title: Transient Placeholder
summary: This is a transient marker.
---
"""

NO_FRONTMATTER_DOC = """\
# No Frontmatter

This file has no YAML frontmatter delimiters.
"""

INVALID_YAML_DOC = """\
---
id: [unclosed
title: Bad YAML
summary: This has invalid YAML.
---
"""

DOC_ALPHA = """\
---
id: alpha-doc
title: Alpha Document
summary: The alpha document.
---

# Alpha Document

Alpha body content here.
"""

DOC_BETA = """\
---
id: beta-doc
title: Beta Document
summary: The beta document.
---

# Beta Document

Beta body content here.
"""

TITLE_MATCH_DOC = """\
---
id: cli-reference
title: CLI Command Reference
summary: Overview of all available commands.
---

# CLI Command Reference

Body text here.
"""

SUMMARY_MATCH_DOC = """\
---
id: arch-overview
title: Architecture Overview
summary: This document covers the database schema in detail.
---

# Architecture Overview

Body text about architecture.
"""

NO_MATCH_DOC = """\
---
id: unrelated-topic
title: Unrelated Topic
summary: Nothing interesting here.
---

# Unrelated Topic

Completely unrelated content.
"""

CASE_SENSITIVITY_DOC = """\
---
id: mixed-case-doc
title: Mixed Case DOCUMENT Title
summary: Summary with MiXeD CaSe keyword present.
---

# Mixed Case Document

Body text.
"""


# ---------------------------------------------------------------------------
# Unit tests: scan_codex()
# ---------------------------------------------------------------------------


class TestScanCodexAllDocumentsAppear:
    """scan_codex() returns all documents with expected fields."""

    def test_returns_list(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "doc-a.md").write_text(VALID_DOC)
        result = scan_codex(codex_dir)
        assert isinstance(result, list)

    def test_document_has_id_field(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "doc-a.md").write_text(VALID_DOC)
        result = scan_codex(codex_dir)
        assert len(result) == 1
        assert result[0]["id"] == "my-doc"

    def test_document_has_title_field(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "doc-a.md").write_text(VALID_DOC)
        result = scan_codex(codex_dir)
        assert result[0]["title"] == "My Document"

    def test_document_has_summary_field(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "doc-a.md").write_text(VALID_DOC)
        result = scan_codex(codex_dir)
        assert result[0]["summary"] == "A short summary of my document."

    def test_document_has_path_field(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "doc-a.md").write_text(VALID_DOC)
        result = scan_codex(codex_dir)
        assert "path" in result[0]

    def test_walks_subdirectories_recursively(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        subdir = codex_dir / "technical" / "cli"
        subdir.mkdir(parents=True)
        (subdir / "nested-doc.md").write_text(VALID_DOC)
        result = scan_codex(codex_dir)
        assert len(result) == 1
        assert result[0]["id"] == "my-doc"


class TestScanCodexTransientDocumentsIncluded:
    """scan_codex() includes all valid documents regardless of id prefix."""

    def test_transient_id_doc_is_included(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "transient.md").write_text(TRANSIENT_DOC)
        result = scan_codex(codex_dir)
        assert len(result) == 1
        assert result[0]["id"] == "transient-placeholder"

    def test_transient_and_valid_both_included(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "transient.md").write_text(TRANSIENT_DOC)
        (codex_dir / "real-doc.md").write_text(VALID_DOC)
        result = scan_codex(codex_dir)
        assert len(result) == 2
        ids = {d["id"] for d in result}
        assert ids == {"transient-placeholder", "my-doc"}


class TestScanCodexEmptyOrMissingDirectory:
    """scan_codex() returns empty list when directory is empty or absent."""

    def test_missing_codex_dir_returns_empty_list(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        result = scan_codex(codex_dir)
        assert result == []

    def test_empty_codex_dir_returns_empty_list(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        result = scan_codex(codex_dir)
        assert result == []

    def test_missing_dir_does_not_raise(self, tmp_path):
        codex_dir = tmp_path / "nonexistent" / "path"
        result = scan_codex(codex_dir)
        assert result == []


class TestScanCodexInvalidFrontmatterSkipped:
    """scan_codex() silently skips files with missing or invalid frontmatter."""

    def test_file_without_frontmatter_skipped(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "no-fm.md").write_text(NO_FRONTMATTER_DOC)
        result = scan_codex(codex_dir)
        assert result == []

    def test_file_with_invalid_yaml_skipped(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "bad-yaml.md").write_text(INVALID_YAML_DOC)
        result = scan_codex(codex_dir)
        assert result == []

    def test_invalid_file_skipped_valid_still_returned(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "no-fm.md").write_text(NO_FRONTMATTER_DOC)
        (codex_dir / "valid.md").write_text(VALID_DOC)
        result = scan_codex(codex_dir)
        assert len(result) == 1
        assert result[0]["id"] == "my-doc"

    def test_file_missing_required_id_field_skipped(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        content = "---\ntitle: No ID Doc\nsummary: Missing the id field.\n---\n"
        (codex_dir / "no-id.md").write_text(content)
        result = scan_codex(codex_dir)
        assert result == []

    def test_file_missing_required_title_field_skipped(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        content = "---\nid: no-title-doc\nsummary: Missing the title field.\n---\n"
        (codex_dir / "no-title.md").write_text(content)
        result = scan_codex(codex_dir)
        assert result == []


class TestScanCodexSortedAlphabetically:
    """scan_codex() returns documents sorted alphabetically by id."""

    def test_multiple_docs_sorted_by_id(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        doc_z = "---\nid: zebra-doc\ntitle: Zebra Document\nsummary: Z doc.\n---\n"
        doc_a = "---\nid: alpha-doc\ntitle: Alpha Document\nsummary: A doc.\n---\n"
        doc_m = "---\nid: middle-doc\ntitle: Middle Document\nsummary: M doc.\n---\n"
        (codex_dir / "zzz.md").write_text(doc_z)
        (codex_dir / "aaa.md").write_text(doc_a)
        (codex_dir / "mmm.md").write_text(doc_m)
        result = scan_codex(codex_dir)
        ids = [d["id"] for d in result]
        assert ids == ["alpha-doc", "middle-doc", "zebra-doc"]

    def test_sort_is_stable_on_repeated_calls(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        for i in range(5):
            content = f"---\nid: doc-{i:02d}\ntitle: Document {i}\nsummary: Summary {i}.\n---\n"
            (codex_dir / f"file-{i}.md").write_text(content)
        result1 = scan_codex(codex_dir)
        result2 = scan_codex(codex_dir)
        assert [d["id"] for d in result1] == [d["id"] for d in result2]


# ---------------------------------------------------------------------------
# Integration tests: lore codex list (human-readable)
# ---------------------------------------------------------------------------


class TestCodexListHumanOutput:
    """lore codex list renders table with correct columns and content."""

    def test_exit_code_0_with_documents(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["codex", "list"])
        assert result.exit_code == 0

    def test_output_contains_id(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["codex", "list"])
        assert "my-doc" in result.output

    def test_output_contains_title(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["codex", "list"])
        assert "My Document" in result.output

    def test_output_contains_group(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["codex", "list"])
        assert "GROUP" in result.output

    def test_output_contains_summary(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["codex", "list"])
        assert "A short summary of my document." in result.output

    def test_table_has_id_column_header(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["codex", "list"])
        assert "ID" in result.output

    def test_table_has_group_column_header(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["codex", "list"])
        assert "GROUP" in result.output

    def test_table_has_title_column_header(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["codex", "list"])
        assert "TITLE" in result.output

    def test_table_has_summary_column_header(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["codex", "list"])
        assert "SUMMARY" in result.output

    def test_transient_id_doc_shown(self, runner, project_dir):
        _write_codex_doc(project_dir, "transient.md", TRANSIENT_DOC)
        _write_codex_doc(project_dir, "real.md", VALID_DOC)
        result = runner.invoke(main, ["codex", "list"])
        assert "transient-placeholder" in result.output
        assert "my-doc" in result.output


class TestCodexListEmptyState:
    """lore codex list with no documents outputs correct empty message.

    These tests use a bare directory (no lore init) so the codex is truly
    empty — lore init ships stable codex docs, so an init'd project is not empty.
    """

    def test_exit_code_0_when_no_documents(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".lore" / "codex").mkdir(parents=True)
        result = runner.invoke(main, ["codex", "list"])
        assert result.exit_code == 0

    def test_empty_message_displayed(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".lore" / "codex").mkdir(parents=True)
        result = runner.invoke(main, ["codex", "list"])
        assert "No codex documents found." in result.output

    def test_exit_code_0_when_only_transient_id_doc(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write_codex_doc(tmp_path, "transient.md", TRANSIENT_DOC)
        result = runner.invoke(main, ["codex", "list"])
        assert result.exit_code == 0

    def test_transient_id_doc_shown_in_list(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write_codex_doc(tmp_path, "transient.md", TRANSIENT_DOC)
        result = runner.invoke(main, ["codex", "list"])
        assert "transient-placeholder" in result.output


class TestCodexListInvalidFrontmatterSkipped:
    """lore codex list silently excludes files without valid frontmatter."""

    def test_file_without_frontmatter_excluded(self, runner, project_dir):
        _write_codex_doc(project_dir, "no-fm.md", NO_FRONTMATTER_DOC)
        _write_codex_doc(project_dir, "valid.md", VALID_DOC)
        result = runner.invoke(main, ["codex", "list"])
        assert result.exit_code == 0
        assert "my-doc" in result.output

    def test_only_invalid_files_shows_empty_message(self, runner, tmp_path, monkeypatch):
        # Uses a bare directory so the only file present is the invalid one
        monkeypatch.chdir(tmp_path)
        _write_codex_doc(tmp_path, "no-fm.md", NO_FRONTMATTER_DOC)
        result = runner.invoke(main, ["codex", "list"])
        assert result.exit_code == 0
        assert "No codex documents found." in result.output


# ---------------------------------------------------------------------------
# Integration tests: lore codex list --json
# ---------------------------------------------------------------------------


class TestCodexListJsonOutput:
    """lore codex list --json emits valid JSON with correct schema."""

    def test_exit_code_0_with_json_flag(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["--json", "codex", "list"])
        assert result.exit_code == 0

    def test_json_output_is_valid_json(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["--json", "codex", "list"])
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_json_output_has_codex_key(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["--json", "codex", "list"])
        data = json.loads(result.output)
        assert "codex" in data

    def test_json_codex_is_a_list(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["--json", "codex", "list"])
        data = json.loads(result.output)
        assert isinstance(data["codex"], list)

    def test_json_document_has_id_field(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["--json", "codex", "list"])
        data = json.loads(result.output)
        ids = [d["id"] for d in data["codex"]]
        assert "my-doc" in ids

    def test_json_document_has_group_field(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["--json", "codex", "list"])
        data = json.loads(result.output)
        records = [d for d in data["codex"] if d["id"] == "my-doc"]
        assert len(records) == 1
        assert "group" in records[0]

    def test_json_document_has_title_field(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["--json", "codex", "list"])
        data = json.loads(result.output)
        records = [d for d in data["codex"] if d["id"] == "my-doc"]
        assert len(records) == 1
        assert records[0]["title"] == "My Document"

    def test_json_document_has_summary_field(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["--json", "codex", "list"])
        data = json.loads(result.output)
        records = [d for d in data["codex"] if d["id"] == "my-doc"]
        assert len(records) == 1
        assert records[0]["summary"] == "A short summary of my document."

    def test_json_document_does_not_have_path_field(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["--json", "codex", "list"])
        data = json.loads(result.output)
        records = [d for d in data["codex"] if d["id"] == "my-doc"]
        assert len(records) == 1
        assert "path" not in records[0]

    def test_json_empty_state_returns_empty_codex_array(self, runner, tmp_path, monkeypatch):
        # Uses a bare directory so the codex is truly empty (lore init ships stable docs)
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".lore" / "codex").mkdir(parents=True)
        result = runner.invoke(main, ["--json", "codex", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == {"codex": []}

    def test_json_transient_id_doc_included(self, runner, tmp_path, monkeypatch):
        # Uses a bare directory so the only doc is the transient-id doc
        monkeypatch.chdir(tmp_path)
        _write_codex_doc(tmp_path, "transient.md", TRANSIENT_DOC)
        result = runner.invoke(main, ["--json", "codex", "list"])
        data = json.loads(result.output)
        ids = [d["id"] for d in data["codex"]]
        assert "transient-placeholder" in ids

    def test_json_documents_sorted_by_id(self, runner, project_dir):
        doc_z = "---\nid: zebra-doc\ntitle: Zebra Document\nsummary: Z doc.\n---\n"
        doc_a = "---\nid: alpha-doc\ntitle: Alpha Document\nsummary: A doc.\n---\n"
        _write_codex_doc(project_dir, "zzz.md", doc_z)
        _write_codex_doc(project_dir, "aaa.md", doc_a)
        result = runner.invoke(main, ["--json", "codex", "list"])
        data = json.loads(result.output)
        # Filter to only the two docs added by this test; stable docs from lore init are also present
        ids = [d["id"] for d in data["codex"] if d["id"] in ("alpha-doc", "zebra-doc")]
        assert ids == ["alpha-doc", "zebra-doc"]


# ---------------------------------------------------------------------------
# Unit tests: read_document()
# ---------------------------------------------------------------------------


class TestReadDocumentKnownId:
    """read_document() returns the correct record for a known ID."""

    def test_returns_dict_for_known_id(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "my-doc.md").write_text(VALID_DOC)
        result = read_document(codex_dir, "my-doc")
        assert isinstance(result, dict)

    def test_result_has_id_field(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "my-doc.md").write_text(VALID_DOC)
        result = read_document(codex_dir, "my-doc")
        assert result["id"] == "my-doc"

    def test_result_has_title_field(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "my-doc.md").write_text(VALID_DOC)
        result = read_document(codex_dir, "my-doc")
        assert result["title"] == "My Document"

    def test_result_has_summary_field(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "my-doc.md").write_text(VALID_DOC)
        result = read_document(codex_dir, "my-doc")
        assert result["summary"] == "A short summary of my document."

    def test_result_has_body_field(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "my-doc.md").write_text(VALID_DOC)
        result = read_document(codex_dir, "my-doc")
        assert "body" in result

    def test_body_contains_document_content(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "my-doc.md").write_text(VALID_DOC)
        result = read_document(codex_dir, "my-doc")
        assert "# My Document" in result["body"]

    def test_body_contains_body_text(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "my-doc.md").write_text(VALID_DOC)
        result = read_document(codex_dir, "my-doc")
        assert "Body text here." in result["body"]

    def test_body_does_not_contain_frontmatter_yaml(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "my-doc.md").write_text(VALID_DOC)
        result = read_document(codex_dir, "my-doc")
        assert "id: my-doc" not in result["body"]
        assert "title: My Document" not in result["body"]
        assert "summary: A short summary" not in result["body"]

    def test_body_does_not_start_with_blank_lines(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "my-doc.md").write_text(VALID_DOC)
        result = read_document(codex_dir, "my-doc")
        assert not result["body"].startswith("\n")


class TestReadDocumentUnknownId:
    """read_document() returns None for an unknown ID."""

    def test_returns_none_for_unknown_id(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "my-doc.md").write_text(VALID_DOC)
        result = read_document(codex_dir, "nonexistent-id")
        assert result is None

    def test_returns_none_when_codex_empty(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        result = read_document(codex_dir, "any-id")
        assert result is None

    def test_returns_none_when_codex_missing(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        result = read_document(codex_dir, "any-id")
        assert result is None

    def test_does_not_raise_for_unknown_id(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        result = read_document(codex_dir, "does-not-exist")
        assert result is None


# ---------------------------------------------------------------------------
# Integration tests: lore codex show (human-readable)
# ---------------------------------------------------------------------------


class TestCodexShowHumanOutput:
    """lore codex show <id> renders body with separator for a known ID."""

    def test_exit_code_0_for_known_id(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["codex", "show", "my-doc"])
        assert result.exit_code == 0

    def test_output_contains_separator_with_id(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["codex", "show", "my-doc"])
        assert "=== my-doc ===" in result.output

    def test_output_contains_body_content(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["codex", "show", "my-doc"])
        assert "# My Document" in result.output

    def test_output_contains_body_text(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["codex", "show", "my-doc"])
        assert "Body text here." in result.output

    def test_output_does_not_contain_frontmatter(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["codex", "show", "my-doc"])
        assert "id: my-doc" not in result.output
        assert "title: My Document" not in result.output


class TestCodexShowUnknownId:
    """lore codex show <id> exits 1 and writes error to stderr for unknown ID."""

    def test_exit_code_1_for_unknown_id(self, runner, project_dir):
        result = runner.invoke(main, ["codex", "show", "bad-id"])
        assert result.exit_code == 1

    def test_error_message_written_to_stderr(self, runner, project_dir):
        result = runner.invoke(main, ["codex", "show", "bad-id"])
        assert "bad-id" in result.stderr

    def test_error_message_names_the_missing_id(self, runner, project_dir):
        result = runner.invoke(main, ["codex", "show", "missing-doc"])
        assert "missing-doc" in result.stderr

    def test_no_output_to_stdout_for_unknown_id(self, runner, project_dir):
        result = runner.invoke(main, ["codex", "show", "missing-doc"])
        assert result.stdout == ""

    def test_error_message_format(self, runner, project_dir):
        result = runner.invoke(main, ["codex", "show", "missing-doc"])
        assert 'Document "missing-doc" not found' in result.stderr


# ---------------------------------------------------------------------------
# Integration tests: lore codex show --json
# ---------------------------------------------------------------------------


class TestCodexShowJsonOutput:
    """lore codex show --json emits valid JSON with correct schema."""

    def test_exit_code_0_for_known_id_with_json_flag(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["--json", "codex", "show", "my-doc"])
        assert result.exit_code == 0

    def test_json_output_is_valid_json(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["--json", "codex", "show", "my-doc"])
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_json_output_has_documents_key(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["--json", "codex", "show", "my-doc"])
        data = json.loads(result.output)
        assert "documents" in data

    def test_json_documents_is_a_list(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["--json", "codex", "show", "my-doc"])
        data = json.loads(result.output)
        assert isinstance(data["documents"], list)

    def test_json_documents_has_one_entry_for_single_id(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["--json", "codex", "show", "my-doc"])
        data = json.loads(result.output)
        assert len(data["documents"]) == 1

    def test_json_document_has_id_field(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["--json", "codex", "show", "my-doc"])
        data = json.loads(result.output)
        assert data["documents"][0]["id"] == "my-doc"

    def test_json_document_has_title_field(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["--json", "codex", "show", "my-doc"])
        data = json.loads(result.output)
        assert data["documents"][0]["title"] == "My Document"

    def test_json_document_has_summary_field(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["--json", "codex", "show", "my-doc"])
        data = json.loads(result.output)
        assert data["documents"][0]["summary"] == "A short summary of my document."

    def test_json_document_has_body_field(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["--json", "codex", "show", "my-doc"])
        data = json.loads(result.output)
        assert "body" in data["documents"][0]

    def test_json_body_contains_document_content(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["--json", "codex", "show", "my-doc"])
        data = json.loads(result.output)
        assert "# My Document" in data["documents"][0]["body"]

    def test_json_body_does_not_contain_frontmatter(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["--json", "codex", "show", "my-doc"])
        data = json.loads(result.output)
        body = data["documents"][0]["body"]
        assert "id: my-doc" not in body
        assert "title: My Document" not in body


class TestCodexShowJsonUnknownId:
    """lore codex show --json exits 1 with JSON error on stderr for unknown ID."""

    def test_exit_code_1_for_unknown_id_with_json_flag(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "codex", "show", "bad-id"])
        assert result.exit_code == 1

    def test_json_error_written_to_stderr(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "codex", "show", "bad-id"])
        assert result.stderr.strip() != ""

    def test_json_error_is_valid_json(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "codex", "show", "bad-id"])
        data = json.loads(result.stderr)
        assert isinstance(data, dict)

    def test_json_error_has_error_key(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "codex", "show", "bad-id"])
        data = json.loads(result.stderr)
        assert "error" in data

    def test_json_error_message_names_the_missing_id(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "codex", "show", "missing-doc"])
        data = json.loads(result.stderr)
        assert "missing-doc" in data["error"]

    def test_json_error_message_format(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "codex", "show", "missing-doc"])
        data = json.loads(result.stderr)
        assert data["error"] == 'Document "missing-doc" not found'

    def test_no_output_to_stdout_for_unknown_id_with_json_flag(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "codex", "show", "missing-doc"])
        assert result.stdout == ""


class TestCodexShowVariadicApi:
    """lore codex show uses nargs=-1 (variadic) — tests for single-ID path."""

    def test_single_id_works_as_positional_arg(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["codex", "show", "my-doc"])
        assert result.exit_code == 0

    def test_single_id_produces_separator(self, runner, project_dir):
        _write_codex_doc(project_dir, "my-doc.md", VALID_DOC)
        result = runner.invoke(main, ["codex", "show", "my-doc"])
        assert "=== my-doc ===" in result.output


# ---------------------------------------------------------------------------
# Unit tests: search_documents()
# ---------------------------------------------------------------------------


class TestSearchDocumentsKeywordInTitle:
    """search_documents() returns documents where keyword appears in title."""

    def test_keyword_in_title_returns_document(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "cli-ref.md").write_text(TITLE_MATCH_DOC)
        result = search_documents(codex_dir, "CLI")
        assert len(result) == 1
        assert result[0]["id"] == "cli-reference"

    def test_keyword_in_title_partial_match(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "cli-ref.md").write_text(TITLE_MATCH_DOC)
        result = search_documents(codex_dir, "Command")
        assert len(result) == 1
        assert result[0]["id"] == "cli-reference"

    def test_no_title_match_returns_empty_list(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "cli-ref.md").write_text(TITLE_MATCH_DOC)
        result = search_documents(codex_dir, "nonexistent-keyword-xyz")
        assert result == []


class TestSearchDocumentsKeywordInSummary:
    """search_documents() returns documents where keyword appears in summary."""

    def test_keyword_in_summary_returns_document(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "arch.md").write_text(SUMMARY_MATCH_DOC)
        result = search_documents(codex_dir, "database schema")
        assert len(result) == 1
        assert result[0]["id"] == "arch-overview"

    def test_keyword_only_in_body_not_matched(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "arch.md").write_text(SUMMARY_MATCH_DOC)
        result = search_documents(codex_dir, "Body text about architecture")
        assert result == []


class TestSearchDocumentsCaseInsensitive:
    """search_documents() performs case-insensitive keyword matching."""

    def test_lowercase_keyword_matches_uppercase_title(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "cli-ref.md").write_text(TITLE_MATCH_DOC)
        result = search_documents(codex_dir, "cli")
        assert len(result) == 1
        assert result[0]["id"] == "cli-reference"

    def test_uppercase_keyword_matches_lowercase_title(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "arch.md").write_text(SUMMARY_MATCH_DOC)
        result = search_documents(codex_dir, "DATABASE SCHEMA")
        assert len(result) == 1
        assert result[0]["id"] == "arch-overview"

    def test_mixed_case_keyword_matches(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "mixed.md").write_text(CASE_SENSITIVITY_DOC)
        result = search_documents(codex_dir, "MiXeD")
        assert len(result) == 1
        assert result[0]["id"] == "mixed-case-doc"


class TestSearchDocumentsNoMatches:
    """search_documents() returns empty list when no documents match."""

    def test_no_match_returns_empty_list(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "cli-ref.md").write_text(TITLE_MATCH_DOC)
        result = search_documents(codex_dir, "zzz-no-match-xyz")
        assert result == []

    def test_empty_codex_dir_returns_empty_list(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        result = search_documents(codex_dir, "anything")
        assert result == []

    def test_missing_codex_dir_returns_empty_list(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        result = search_documents(codex_dir, "anything")
        assert result == []


class TestSearchDocumentsResultShape:
    """search_documents() returns documents with expected field shape (no path)."""

    def test_result_has_id_field(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "cli-ref.md").write_text(TITLE_MATCH_DOC)
        result = search_documents(codex_dir, "CLI")
        assert "id" in result[0]

    def test_result_has_title_field(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "cli-ref.md").write_text(TITLE_MATCH_DOC)
        result = search_documents(codex_dir, "CLI")
        assert "title" in result[0]

    def test_result_does_not_have_path_field(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "cli-ref.md").write_text(TITLE_MATCH_DOC)
        result = search_documents(codex_dir, "CLI")
        assert "path" not in result[0]

    def test_result_does_not_have_body_field(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "cli-ref.md").write_text(TITLE_MATCH_DOC)
        result = search_documents(codex_dir, "CLI")
        assert "body" not in result[0]


class TestSearchDocumentsOrdering:
    """search_documents() returns results ordered alphabetically by id."""

    def test_results_sorted_by_id(self, tmp_path):
        codex_dir = tmp_path / ".lore" / "codex"
        codex_dir.mkdir(parents=True)
        doc_z = "---\nid: zebra-guide\ntitle: Zebra Guide\nsummary: Guide about something important.\n---\n"
        doc_a = "---\nid: alpha-guide\ntitle: Alpha Guide\nsummary: Another guide about something important.\n---\n"
        doc_m = "---\nid: middle-guide\ntitle: Middle Guide\nsummary: Middle guide about something important.\n---\n"
        (codex_dir / "zzz.md").write_text(doc_z)
        (codex_dir / "aaa.md").write_text(doc_a)
        (codex_dir / "mmm.md").write_text(doc_m)
        result = search_documents(codex_dir, "important")
        ids = [d["id"] for d in result]
        assert ids == ["alpha-guide", "middle-guide", "zebra-guide"]


# ---------------------------------------------------------------------------
# Integration tests: lore codex search (human-readable)
# ---------------------------------------------------------------------------


class TestCodexSearchHumanOutputMatchingDocuments:
    """lore codex search renders table with matching documents."""

    def test_exit_code_0_with_matching_documents(self, runner, project_dir):
        _write_codex_doc(project_dir, "cli-ref.md", TITLE_MATCH_DOC)
        result = runner.invoke(main, ["codex", "search", "CLI"])
        assert result.exit_code == 0

    def test_output_contains_matching_document_id(self, runner, project_dir):
        _write_codex_doc(project_dir, "cli-ref.md", TITLE_MATCH_DOC)
        result = runner.invoke(main, ["codex", "search", "CLI"])
        assert "cli-reference" in result.output

    def test_output_contains_matching_document_title(self, runner, project_dir):
        _write_codex_doc(project_dir, "cli-ref.md", TITLE_MATCH_DOC)
        result = runner.invoke(main, ["codex", "search", "CLI"])
        assert "CLI Command Reference" in result.output

    def test_output_contains_matching_document_summary(self, runner, project_dir):
        _write_codex_doc(project_dir, "cli-ref.md", TITLE_MATCH_DOC)
        result = runner.invoke(main, ["codex", "search", "CLI"])
        assert "Overview of all available commands." in result.output

    def test_table_has_id_column_header(self, runner, project_dir):
        _write_codex_doc(project_dir, "cli-ref.md", TITLE_MATCH_DOC)
        result = runner.invoke(main, ["codex", "search", "CLI"])
        assert "ID" in result.output

    def test_non_matching_document_excluded(self, runner, project_dir):
        _write_codex_doc(project_dir, "cli-ref.md", TITLE_MATCH_DOC)
        _write_codex_doc(project_dir, "unrelated.md", NO_MATCH_DOC)
        result = runner.invoke(main, ["codex", "search", "CLI"])
        assert "unrelated-topic" not in result.output

    def test_summary_match_returns_document(self, runner, project_dir):
        _write_codex_doc(project_dir, "arch.md", SUMMARY_MATCH_DOC)
        result = runner.invoke(main, ["codex", "search", "database schema"])
        assert "arch-overview" in result.output


class TestCodexSearchHumanOutputCaseInsensitive:
    """lore codex search keyword matching is case-insensitive."""

    def test_lowercase_keyword_matches_uppercase_title(self, runner, project_dir):
        _write_codex_doc(project_dir, "cli-ref.md", TITLE_MATCH_DOC)
        result = runner.invoke(main, ["codex", "search", "cli"])
        assert result.exit_code == 0
        assert "cli-reference" in result.output

    def test_uppercase_keyword_matches_lowercase_content(self, runner, project_dir):
        _write_codex_doc(project_dir, "arch.md", SUMMARY_MATCH_DOC)
        result = runner.invoke(main, ["codex", "search", "DATABASE SCHEMA"])
        assert result.exit_code == 0
        assert "arch-overview" in result.output


class TestCodexSearchHumanOutputNoMatches:
    """lore codex search with no matches outputs empty state and exits 0."""

    def test_exit_code_0_with_no_matches(self, runner, project_dir):
        _write_codex_doc(project_dir, "cli-ref.md", TITLE_MATCH_DOC)
        result = runner.invoke(main, ["codex", "search", "zzz-no-match-xyz"])
        assert result.exit_code == 0

    def test_empty_state_message_displayed(self, runner, project_dir):
        _write_codex_doc(project_dir, "cli-ref.md", TITLE_MATCH_DOC)
        result = runner.invoke(main, ["codex", "search", "zzz-no-match-xyz"])
        assert 'No documents matching "zzz-no-match-xyz".' in result.output

    def test_empty_state_message_includes_keyword(self, runner, project_dir):
        keyword = "myspecialkeyword"
        result = runner.invoke(main, ["codex", "search", keyword])
        assert f'No documents matching "{keyword}".' in result.output


# ---------------------------------------------------------------------------
# Integration tests: lore codex search --json
# ---------------------------------------------------------------------------


class TestCodexSearchJsonOutputMatchingDocuments:
    """lore codex search --json emits valid JSON with correct schema."""

    def test_exit_code_0_with_json_flag(self, runner, project_dir):
        _write_codex_doc(project_dir, "cli-ref.md", TITLE_MATCH_DOC)
        result = runner.invoke(main, ["--json", "codex", "search", "CLI"])
        assert result.exit_code == 0

    def test_json_output_is_valid_json(self, runner, project_dir):
        _write_codex_doc(project_dir, "cli-ref.md", TITLE_MATCH_DOC)
        result = runner.invoke(main, ["--json", "codex", "search", "CLI"])
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_json_output_has_documents_key(self, runner, project_dir):
        _write_codex_doc(project_dir, "cli-ref.md", TITLE_MATCH_DOC)
        result = runner.invoke(main, ["--json", "codex", "search", "CLI"])
        data = json.loads(result.output)
        assert "documents" in data

    def test_json_document_has_id_field(self, runner, project_dir):
        _write_codex_doc(project_dir, "cli-ref.md", TITLE_MATCH_DOC)
        result = runner.invoke(main, ["--json", "codex", "search", "CLI"])
        data = json.loads(result.output)
        assert data["documents"][0]["id"] == "cli-reference"

    def test_json_document_does_not_have_path_field(self, runner, project_dir):
        _write_codex_doc(project_dir, "cli-ref.md", TITLE_MATCH_DOC)
        result = runner.invoke(main, ["--json", "codex", "search", "CLI"])
        data = json.loads(result.output)
        assert "path" not in data["documents"][0]

    def test_json_document_does_not_have_body_field(self, runner, project_dir):
        _write_codex_doc(project_dir, "cli-ref.md", TITLE_MATCH_DOC)
        result = runner.invoke(main, ["--json", "codex", "search", "CLI"])
        data = json.loads(result.output)
        assert "body" not in data["documents"][0]

    def test_json_documents_sorted_by_id(self, runner, project_dir):
        doc_z = "---\nid: z-guide\ntitle: Z Guide about CLI commands\nsummary: Z summary.\n---\n"
        doc_a = "---\nid: a-guide\ntitle: A Guide about CLI commands\nsummary: A summary.\n---\n"
        _write_codex_doc(project_dir, "z-guide.md", doc_z)
        _write_codex_doc(project_dir, "a-guide.md", doc_a)
        result = runner.invoke(main, ["--json", "codex", "search", "CLI"])
        data = json.loads(result.output)
        # Filter to the two docs added by this test; stable docs from lore init also match "CLI"
        ids = [d["id"] for d in data["documents"] if d["id"] in ("a-guide", "z-guide")]
        assert ids == ["a-guide", "z-guide"]


class TestCodexSearchJsonOutputNoMatches:
    """lore codex search --json with no matches returns empty documents array."""

    def test_exit_code_0_with_no_matches_json_flag(self, runner, project_dir):
        _write_codex_doc(project_dir, "cli-ref.md", TITLE_MATCH_DOC)
        result = runner.invoke(main, ["--json", "codex", "search", "zzz-no-match"])
        assert result.exit_code == 0

    def test_json_empty_state_returns_empty_documents_array(self, runner, project_dir):
        _write_codex_doc(project_dir, "cli-ref.md", TITLE_MATCH_DOC)
        result = runner.invoke(main, ["--json", "codex", "search", "zzz-no-match"])
        data = json.loads(result.output)
        assert data == {"documents": []}

    def test_json_empty_codex_returns_empty_documents_array(self, runner, project_dir):
        result = runner.invoke(main, ["--json", "codex", "search", "anything"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == {"documents": []}


# ---------------------------------------------------------------------------
# Duplicate ID deduplication
# ---------------------------------------------------------------------------


class TestCodexShowDuplicateIdsHumanOutput:
    """lore codex show deduplicates repeated IDs — human-readable output."""

    def test_duplicate_ids_separator_appears_once_in_output(self, runner, project_dir):
        _write_codex_doc(project_dir, "alpha.md", DOC_ALPHA)
        result = runner.invoke(main, ["codex", "show", "alpha-doc", "alpha-doc"])
        assert result.output.count("=== alpha-doc ===") == 1

    def test_duplicate_ids_body_appears_once(self, runner, project_dir):
        _write_codex_doc(project_dir, "alpha.md", DOC_ALPHA)
        result = runner.invoke(main, ["codex", "show", "alpha-doc", "alpha-doc"])
        assert result.output.count("Alpha body content here.") == 1

    def test_duplicate_ids_with_other_id_each_doc_once(self, runner, project_dir):
        _write_codex_doc(project_dir, "alpha.md", DOC_ALPHA)
        _write_codex_doc(project_dir, "beta.md", DOC_BETA)
        result = runner.invoke(
            main, ["codex", "show", "alpha-doc", "beta-doc", "alpha-doc"]
        )
        assert result.output.count("=== alpha-doc ===") == 1
        assert result.output.count("=== beta-doc ===") == 1

    def test_triplicate_ids_separator_appears_once(self, runner, project_dir):
        _write_codex_doc(project_dir, "alpha.md", DOC_ALPHA)
        result = runner.invoke(
            main, ["codex", "show", "alpha-doc", "alpha-doc", "alpha-doc"]
        )
        assert result.output.count("=== alpha-doc ===") == 1

    def test_duplicate_ids_preserves_first_occurrence_order(self, runner, project_dir):
        _write_codex_doc(project_dir, "alpha.md", DOC_ALPHA)
        _write_codex_doc(project_dir, "beta.md", DOC_BETA)
        result = runner.invoke(
            main, ["codex", "show", "alpha-doc", "beta-doc", "alpha-doc"]
        )
        separators = [line for line in result.output.splitlines() if line.startswith("===")]
        assert separators == ["=== alpha-doc ===", "=== beta-doc ==="]


class TestCodexShowDuplicateIdsJsonOutput:
    """lore codex show --json deduplicates repeated IDs — machine-readable output."""

    def test_duplicate_ids_json_documents_list_has_one_entry(self, runner, project_dir):
        _write_codex_doc(project_dir, "alpha.md", DOC_ALPHA)
        result = runner.invoke(
            main, ["--json", "codex", "show", "alpha-doc", "alpha-doc"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["documents"]) == 1

    def test_duplicate_ids_json_document_id_is_correct(self, runner, project_dir):
        _write_codex_doc(project_dir, "alpha.md", DOC_ALPHA)
        result = runner.invoke(
            main, ["--json", "codex", "show", "alpha-doc", "alpha-doc"]
        )
        data = json.loads(result.output)
        assert len(data["documents"]) == 1 and data["documents"][0]["id"] == "alpha-doc"

    def test_duplicate_ids_with_other_json_correct_count(self, runner, project_dir):
        _write_codex_doc(project_dir, "alpha.md", DOC_ALPHA)
        _write_codex_doc(project_dir, "beta.md", DOC_BETA)
        result = runner.invoke(
            main, ["--json", "codex", "show", "alpha-doc", "beta-doc", "alpha-doc"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["documents"]) == 2

    def test_duplicate_ids_json_order_first_occurrence(self, runner, project_dir):
        _write_codex_doc(project_dir, "alpha.md", DOC_ALPHA)
        _write_codex_doc(project_dir, "beta.md", DOC_BETA)
        result = runner.invoke(
            main, ["--json", "codex", "show", "alpha-doc", "beta-doc", "alpha-doc"]
        )
        data = json.loads(result.output)
        ids = [d["id"] for d in data["documents"]]
        assert ids == ["alpha-doc", "beta-doc"]

    def test_triplicate_ids_json_has_one_document(self, runner, project_dir):
        _write_codex_doc(project_dir, "alpha.md", DOC_ALPHA)
        result = runner.invoke(
            main, ["--json", "codex", "show", "alpha-doc", "alpha-doc", "alpha-doc"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["documents"]) == 1
