"""E2E CLI tests for codex CRUD — Red phase.

Spec: ``transient-codex-crud-spec`` Sections B + D test 15.

Covers ``lore codex new / edit / delete`` parity with the API envelope.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from lore.cli import main


CODEX_DOC = (
    "---\n"
    "id: my-doc\n"
    "title: My Doc\n"
    "summary: A test doc.\n"
    "---\n"
    "# body\n"
)


def _write_source(project_dir: Path, name: str, content: str) -> Path:
    p = project_dir / name
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# lore codex new
# ---------------------------------------------------------------------------


class TestCodexNew:
    def test_creates_doc_from_file(self, runner, project_dir):
        src = _write_source(project_dir, "src.md", CODEX_DOC)
        result = runner.invoke(
            main, ["codex", "new", "my-doc", "-f", str(src)]
        )
        assert result.exit_code == 0, (result.output, result.stderr)
        target = project_dir / ".lore" / "codex" / "my-doc.md"
        assert target.exists()

    def test_creates_doc_with_group(self, runner, project_dir):
        src = _write_source(project_dir, "src.md", CODEX_DOC)
        result = runner.invoke(
            main,
            [
                "codex",
                "new",
                "my-doc",
                "-f",
                str(src),
                "--group",
                "decisions",
            ],
        )
        assert result.exit_code == 0, (result.output, result.stderr)
        target = project_dir / ".lore" / "codex" / "decisions" / "my-doc.md"
        assert target.exists()

    def test_json_envelope_parity_with_api(self, runner, project_dir):
        src = _write_source(project_dir, "src.md", CODEX_DOC)
        cli_result = runner.invoke(
            main, ["--json", "codex", "new", "my-doc", "-f", str(src)]
        )
        assert cli_result.exit_code == 0, cli_result.output
        cli_env = json.loads(cli_result.stdout)
        assert set(cli_env.keys()) == {"id", "filename", "group", "doc_type"}
        assert cli_env["id"] == "my-doc"
        assert cli_env["doc_type"] == "codex"

    def test_unknown_type_rejected(self, runner, project_dir):
        src = _write_source(project_dir, "src.md", CODEX_DOC)
        result = runner.invoke(
            main,
            ["codex", "new", "my-doc", "-f", str(src), "--type", "bogus"],
        )
        assert result.exit_code != 0

    def test_type_codex_source_uses_correct_schema(self, runner, project_dir):
        # codex-source requires related minItems: 1 — give it one.
        src_content = (
            "---\n"
            "id: rk-001\n"
            "title: Realm Source\n"
            "summary: A source.\n"
            "related:\n"
            "  - alpha\n"
            "---\n"
            "# body\n"
        )
        src = _write_source(project_dir, "src.md", src_content)
        result = runner.invoke(
            main,
            [
                "codex",
                "new",
                "rk-001",
                "-f",
                str(src),
                "--group",
                "sources/realm",
            ],
        )
        assert result.exit_code == 0, (result.output, result.stderr)


# ---------------------------------------------------------------------------
# lore codex edit (whole-file and field-mode)
# ---------------------------------------------------------------------------


class TestCodexEdit:
    def _seed_doc(self, project_dir: Path) -> None:
        (project_dir / ".lore" / "codex" / "my-doc.md").write_text(CODEX_DOC)

    def test_edit_whole_file(self, runner, project_dir):
        self._seed_doc(project_dir)
        new_content = (
            "---\n"
            "id: my-doc\n"
            "title: Updated\n"
            "summary: Now updated.\n"
            "---\n"
            "# new body\n"
        )
        src = _write_source(project_dir, "new.md", new_content)
        result = runner.invoke(
            main, ["codex", "edit", "my-doc", "-f", str(src)]
        )
        assert result.exit_code == 0, (result.output, result.stderr)
        text = (project_dir / ".lore" / "codex" / "my-doc.md").read_text()
        meta = yaml.safe_load(text.split("---", 2)[1])
        assert meta["title"] == "Updated"

    def test_edit_field_set_summary(self, runner, project_dir):
        self._seed_doc(project_dir)
        result = runner.invoke(
            main,
            ["codex", "edit", "my-doc", "--set", "summary=New summary."],
        )
        assert result.exit_code == 0, (result.output, result.stderr)
        text = (project_dir / ".lore" / "codex" / "my-doc.md").read_text()
        meta = yaml.safe_load(text.split("---", 2)[1])
        assert meta["summary"] == "New summary."

    def test_edit_field_add_related(self, runner, project_dir):
        self._seed_doc(project_dir)
        result = runner.invoke(
            main,
            ["codex", "edit", "my-doc", "--add", "related=other-doc"],
        )
        assert result.exit_code == 0, (result.output, result.stderr)
        text = (project_dir / ".lore" / "codex" / "my-doc.md").read_text()
        meta = yaml.safe_load(text.split("---", 2)[1])
        assert "other-doc" in meta["related"]

    def test_edit_field_add_binds(self, runner, project_dir):
        self._seed_doc(project_dir)
        result = runner.invoke(
            main,
            ["codex", "edit", "my-doc", "--add", "binds=src/x.py"],
        )
        assert result.exit_code == 0, (result.output, result.stderr)
        text = (project_dir / ".lore" / "codex" / "my-doc.md").read_text()
        meta = yaml.safe_load(text.split("---", 2)[1])
        assert "src/x.py" in meta["binds"]

    def test_edit_field_rejects_absolute_binds(self, runner, project_dir):
        self._seed_doc(project_dir)
        result = runner.invoke(
            main,
            ["codex", "edit", "my-doc", "--add", "binds=/absolute/path"],
        )
        assert result.exit_code != 0

    def test_edit_mutex_rejected(self, runner, project_dir):
        self._seed_doc(project_dir)
        src = _write_source(project_dir, "new.md", CODEX_DOC)
        result = runner.invoke(
            main,
            [
                "codex",
                "edit",
                "my-doc",
                "-f",
                str(src),
                "--set",
                "summary=X",
            ],
        )
        assert result.exit_code != 0
        combined = (result.stdout or "") + (result.stderr or "")
        assert "Cannot combine" in combined


# ---------------------------------------------------------------------------
# lore codex delete
# ---------------------------------------------------------------------------


class TestCodexDelete:
    def test_delete_doc(self, runner, project_dir):
        target = project_dir / ".lore" / "codex" / "my-doc.md"
        target.write_text(CODEX_DOC)
        result = runner.invoke(main, ["codex", "delete", "my-doc"])
        assert result.exit_code == 0, (result.output, result.stderr)
        assert not target.exists()
        assert (
            project_dir / ".lore" / "codex" / "my-doc.md.deleted"
        ).exists()

    def test_delete_seeded_id_protected(self, runner, project_dir):
        # The init fixture seeds codex/codex.md (id=codex) — try to delete
        result = runner.invoke(main, ["codex", "delete", "codex"])
        assert result.exit_code != 0
        combined = (result.stdout or "") + (result.stderr or "")
        assert "protected" in combined or "Cannot delete" in combined

    def test_delete_not_found(self, runner, project_dir):
        result = runner.invoke(main, ["codex", "delete", "ghost"])
        assert result.exit_code != 0

    def test_json_envelope_parity(self, runner, project_dir):
        target = project_dir / ".lore" / "codex" / "my-doc.md"
        target.write_text(CODEX_DOC)
        result = runner.invoke(main, ["--json", "codex", "delete", "my-doc"])
        assert result.exit_code == 0, (result.output, result.stderr)
        env = json.loads(result.stdout)
        assert env["id"] == "my-doc"
        assert env["deleted"] is True
        assert env["deleted_at"] is None
        assert env["doc_type"] == "codex"
