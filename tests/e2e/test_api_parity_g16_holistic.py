"""E2E parity for the G16 BREAKING wave — additive envelope changes only.

Plan: ``transient-public-api-facade-plan`` §G16 acceptance.
Amendment: ``transient-public-api-facade-create-stdz`` Section D + Section E
breaking list.

This file pins the TWO additive CLI envelope changes ratified by amendment
A2 + Open Item 11 / F-ARTIFACT-MUTATION-CONTRACT:

* ``artifact show --json`` envelope GAINS ``filename`` and ``group`` keys.
* ``watcher delete --json`` envelope GAINS ``deleted_at`` (value ``None``
  for file-backed entities).

Plus the rename parity checks:

* ``codex list`` (CLI path unchanged) routes through ``list_codex`` not
  ``scan_codex``.
* ``artifact list`` (CLI path unchanged) routes through ``list_artifacts``.
* ``doctrine show`` of a missing doctrine emits the not-found path WITHOUT
  raising ``DoctrineError`` internally (``read_doctrine`` returns ``None``).
* ``knight show`` consumes ``read_knight(...)["body"]`` rather than calling
  ``find_knight`` (path-resolution) + ``read_text``.

Red phase — every test below MUST fail until G16 Green lands.
"""

from __future__ import annotations

import json
import textwrap


from lore.cli import main


PERSONA_MD = (
    "---\n"
    "id: reviewer\n"
    "title: Reviewer\n"
    "summary: A reviewer persona.\n"
    "---\n"
    "# body text\n"
)


ARTIFACT_MD = (
    "---\n"
    "id: tmpl\n"
    "title: Template\n"
    "summary: An artifact template.\n"
    "---\n"
    "# body\n"
)


WATCHER_YAML = textwrap.dedent(
    """\
    id: w1
    title: Watcher 1
    summary: Test watcher.
    watch_target: foo
    interval: 60
    action: bar
    """
)


# ---------------------------------------------------------------------------
# Additive envelope change A — artifact show JSON gains filename + group.
# ---------------------------------------------------------------------------


class TestArtifactShowJsonAddsFilenameGroup:
    """``artifact show --json`` envelope gains ``filename`` and ``group``."""

    def _seed(self, project_dir, group=None):
        artifacts = project_dir / ".lore" / "artifacts"
        if group:
            (artifacts / group).mkdir(parents=True, exist_ok=True)
            (artifacts / group / "tmpl.md").write_text(ARTIFACT_MD)
        else:
            artifacts.mkdir(parents=True, exist_ok=True)
            (artifacts / "tmpl.md").write_text(ARTIFACT_MD)

    def test_artifact_show_json_has_filename_key(self, runner, project_dir):
        self._seed(project_dir)
        result = runner.invoke(
            main, ["--json", "artifact", "show", "tmpl"]
        )
        payload = json.loads(result.stdout)
        assert "filename" in payload, (
            "G16 amendment Section D: artifact show JSON gains 'filename'."
        )
        assert payload["filename"] == "tmpl.md"

    def test_artifact_show_json_has_group_key(self, runner, project_dir):
        self._seed(project_dir, group="templates")
        result = runner.invoke(
            main, ["--json", "artifact", "show", "tmpl"]
        )
        payload = json.loads(result.stdout)
        assert "group" in payload, (
            "G16 amendment Section D: artifact show JSON gains 'group'."
        )
        assert payload["group"] == "templates"


# ---------------------------------------------------------------------------
# Additive envelope change B — watcher delete JSON gains deleted_at: None.
# ---------------------------------------------------------------------------


class TestWatcherDeleteJsonAddsDeletedAt:
    """``watcher delete --json`` envelope gains ``deleted_at`` (value ``None``)."""

    def _seed(self, project_dir):
        watchers = project_dir / ".lore" / "watchers"
        watchers.mkdir(parents=True, exist_ok=True)
        (watchers / "w1.yaml").write_text(WATCHER_YAML)

    def test_watcher_delete_json_has_deleted_at_key(
        self, runner, project_dir
    ):
        self._seed(project_dir)
        result = runner.invoke(
            main, ["--json", "watcher", "delete", "w1"]
        )
        payload = json.loads(result.stdout)
        assert "deleted_at" in payload, (
            "G16 amendment A2: watcher delete JSON gains 'deleted_at'."
        )
        assert payload["deleted_at"] is None


# ---------------------------------------------------------------------------
# Rename parity — CLI paths unchanged; internal callable swap.
# ---------------------------------------------------------------------------


class TestArtifactListRoutesThroughListArtifacts:
    """``artifact list`` CLI path uses ``list_artifacts`` (not ``scan_artifacts``)."""

    def test_artifact_list_imports_list_artifacts(self):
        from pathlib import Path

        src = (
            Path(__file__).resolve().parents[2] / "src" / "lore" / "cli.py"
        ).read_text()
        assert "scan_artifacts" not in src, (
            "cli.py must not reference scan_artifacts; use list_artifacts."
        )


class TestCodexListRoutesThroughListCodex:
    """``codex list`` CLI path uses ``list_codex`` (not ``scan_codex``)."""

    def test_codex_list_does_not_reference_scan_codex(self):
        from pathlib import Path

        src = (
            Path(__file__).resolve().parents[2] / "src" / "lore" / "cli.py"
        ).read_text()
        assert "scan_codex" not in src, (
            "cli.py must not reference scan_codex; use list_codex."
        )


class TestDoctrineShowConsumesReadDoctrineNoneOnMiss:
    """``doctrine show`` of a missing doctrine routes through ``read_doctrine``."""

    def test_doctrine_show_missing_exits_nonzero(self, runner, project_dir):
        result = runner.invoke(
            main, ["doctrine", "show", "nonexistent-doctrine"]
        )
        # Behaviour-preserved: CLI emits not-found and exits 1.
        assert result.exit_code != 0

    def test_cli_does_not_import_show_doctrine(self):
        from pathlib import Path

        src = (
            Path(__file__).resolve().parents[2] / "src" / "lore" / "cli.py"
        ).read_text()
        # G16: show_doctrine renamed to read_doctrine; CLI must call the new
        # name. Substring check is sufficient — cli.py never spells the old
        # name except via the rename target.
        assert "show_doctrine" not in src, (
            "cli.py must not reference show_doctrine; use read_doctrine."
        )


class TestKnightShowConsumesReadKnightDict:
    """``knight show`` routes through ``read_knight(...)["body"]``."""

    def _seed(self, project_dir):
        knights = project_dir / ".lore" / "knights"
        knights.mkdir(parents=True, exist_ok=True)
        (knights / "reviewer.md").write_text(PERSONA_MD)

    def test_cli_does_not_call_find_knight_for_show(self):
        from pathlib import Path

        src = (
            Path(__file__).resolve().parents[2] / "src" / "lore" / "cli.py"
        ).read_text()
        assert "find_knight" not in src, (
            "cli.py must not reference find_knight; use read_knight."
        )

    def test_knight_show_json_emits_full_record(self, runner, project_dir):
        """JSON mode emits the full read_knight dict (id/title/summary/body/...)."""
        self._seed(project_dir)
        result = runner.invoke(
            main, ["--json", "knight", "show", "reviewer"]
        )
        payload = json.loads(result.stdout)
        # Per Section D: "Text mode emits body; JSON mode emits whole dict."
        for key in ("id", "title", "summary", "body"):
            assert key in payload, (
                f"knight show --json must emit '{key}' from read_knight dict."
            )
