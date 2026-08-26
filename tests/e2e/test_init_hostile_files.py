"""E2E tests for `lore init` against a project whose files are not what they claim.

Adversarial smoke testing found four ways a real working tree stops `lore init`
dead, two of them with a raw traceback. Each was one instance of a class:

* **A manifest that parses as JSON and is not a manifest.** `manifest.load` is
  fail-soft by contract — `init._recorded_entries` has no other branch — so a
  row carrying a number where a path belongs has to degrade to the legacy-hash
  path exactly as an unreadable file does.
* **A path Lore writes that is occupied by something other than a file.** A
  directory named `config.toml` is the one that was found; every write site has
  the same exposure.
* **A file Lore reads as text that will not decode.** The decoder's message
  carries a byte offset and no filename, which tells nobody which file to fix.
* **A path the filesystem itself refuses.** A read-only file, a read-only
  directory, a read-only project root — all ordinary in a real repo, all
  `PermissionError` tracebacks with an empty stdout.

The tables below are the classes. The reproductions are inside them, but no
test here is about the specific file that happened to be found. The paths that
are *links* rather than files are the same idea and live next door, in
`test_init_symlink_paths.py`.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from lore import manifest
from lore.cli import main

NOT_UTF8 = b"\x1f\x8b\x08\x82\x00\xff\xfe binary payload\n"
"""Bytes no UTF-8 decoder accepts, whatever offset it starts complaining at."""


# ---------------------------------------------------------------------------
# Running the CLI
# ---------------------------------------------------------------------------


@pytest.fixture()
def fresh(tmp_path, monkeypatch):
    """An empty directory that is the working directory for the whole test."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture()
def installed(runner, fresh):
    """A project this release installed for Claude Code."""
    result = runner.invoke(main, ["init", "--agent", "claude", "--yes"])
    assert result.exit_code == 0, result.output
    return fresh


def run_init(runner, *args):
    return runner.invoke(main, ["init", "--agent", "claude", "--yes", *args])


def assert_reported_not_raised(result) -> str:
    """Assert the run failed the way a person can read, and return the message.

    A traceback reaching the terminal is the defect under test, so this checks
    the shape of the failure and not only its exit code: `click` turns a
    reported error into ``SystemExit``, and anything else escaped.
    """
    assert result.exit_code == 1, result.output
    assert result.exception is None or isinstance(result.exception, SystemExit), (
        result.exception
    )
    message = result.stderr + result.stdout
    assert "Traceback" not in message
    return message


# ---------------------------------------------------------------------------
# The manifest — reading and damaging what this release wrote
# ---------------------------------------------------------------------------


def manifest_file(root: Path) -> Path:
    return root / ".lore" / ".install-manifest.json"


def read_manifest(root: Path) -> dict:
    return json.loads(manifest_file(root).read_text(encoding="utf-8"))


def rewrite_manifest(root: Path, payload: dict) -> None:
    manifest_file(root).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def row(key, value):
    """Damage the first ``files`` row."""

    def damage(payload: dict) -> dict:
        payload["files"][0][key] = value
        return payload

    return damage


def top(key, value):
    """Damage a top-level field."""

    def damage(payload: dict) -> dict:
        payload[key] = value
        return payload

    return damage


MALFORMED_MANIFESTS = {
    "a path that is a number": row("path", 7),
    "a path that is null": row("path", None),
    "a kind that is a number": row("kind", 3),
    "a source that is an object": row("source", {"skill": "demo"}),
    "a hash that is a number": row("hash", 1),
    "a hash that is null": row("hash", None),
    "a row that is not an object": top("files", ["not-an-object"]),
    "a files value that is not a list": top("files", {}),
    "answers that are not an object": top("answers", []),
    "targets that are not an object": top("targets", "claude"),
    "a lore_version that is a number": top("lore_version", 10),
    "a catalogue_version that is a string": top("catalogue_version", "2"),
    "a generated_at that is a number": top("generated_at", 0),
    "an unrecognised manifest_version": top("manifest_version", 99),
}


class TestAManifestThatIsNotAManifest:
    """Every shape degrades to the legacy path; none of them stops the run."""

    @pytest.mark.parametrize(
        "damage", list(MALFORMED_MANIFESTS.values()), ids=list(MALFORMED_MANIFESTS)
    )
    def test_the_next_run_falls_back_and_finishes(self, runner, installed, damage):
        rewrite_manifest(installed, damage(read_manifest(installed)))

        result = run_init(runner)

        assert result.exit_code == 0, result.output
        assert "Traceback" not in result.stderr
        assert str(manifest_file(installed)) in result.stderr
        assert "falling back to legacy hashes" in result.stderr

    @pytest.mark.parametrize(
        "damage", list(MALFORMED_MANIFESTS.values()), ids=list(MALFORMED_MANIFESTS)
    )
    def test_the_run_leaves_a_manifest_that_loads(self, runner, installed, damage):
        rewrite_manifest(installed, damage(read_manifest(installed)))

        run_init(runner)

        assert manifest.load(installed) is not None

    def test_manifest_bytes_that_are_not_utf8_fall_back_too(self, runner, installed):
        manifest_file(installed).write_bytes(NOT_UTF8)

        result = run_init(runner)

        assert result.exit_code == 0, result.output
        assert str(manifest_file(installed)) in result.stderr
        assert manifest.load(installed) is not None


# ---------------------------------------------------------------------------
# A directory where Lore has to write a file
# ---------------------------------------------------------------------------


OCCUPIED_PATHS = (
    ".lore/config.toml",
    ".lore/codex/codex.md",
    ".lore/codex/glossary.yaml",
    ".lore/LORE-AGENT.md",
    "CLAUDE.md",
    ".claude/skills/store-memory/SKILL.md",
)
"""One path per write site: the seeded files, the rendered doc, the marked
block inside the one file the project owns, and an installed skill.

The root `.gitignore` used to sit in this list and was the path that found the
defect: a directory there stopped the run after nineteen files had landed with
no manifest written. No release writes it now, so a directory at that path is
not a path this run has anything to say about."""


class TestADirectoryWhereAFileBelongs:
    @pytest.mark.parametrize("relative", OCCUPIED_PATHS)
    def test_the_run_names_the_path_and_the_repair(self, runner, fresh, relative):
        occupied = fresh / relative
        occupied.mkdir(parents=True)

        message = assert_reported_not_raised(run_init(runner))

        assert str(occupied) in message
        assert "move or remove it" in message

    @pytest.mark.parametrize("relative", OCCUPIED_PATHS)
    def test_an_already_installed_project_reports_it_the_same_way(
        self, runner, installed, relative
    ):
        occupied = installed / relative
        if occupied.is_file():
            occupied.unlink()
        occupied.mkdir(parents=True, exist_ok=True)

        message = assert_reported_not_raised(run_init(runner))

        assert str(occupied) in message


# ---------------------------------------------------------------------------
# A file Lore has to read as text that will not decode
# ---------------------------------------------------------------------------


UNDECODABLE_PATHS = (
    ".lore/config.toml",
    "CLAUDE.md",
)
"""The files a run reads as text and did not itself just render: the project's
config, and the instruction file its marked block lives in."""


class TestAFileThatIsNotText:
    @pytest.mark.parametrize("relative", UNDECODABLE_PATHS)
    def test_the_run_names_the_file_rather_than_a_byte_offset(
        self, runner, installed, relative
    ):
        target = installed / relative
        target.write_bytes(NOT_UTF8)

        message = assert_reported_not_raised(run_init(runner))

        assert str(target) in message
        assert "not valid UTF-8 text" in message
        assert "codec" not in message

    def test_a_recorded_section_target_that_is_binary_is_named(self, runner, installed):
        # A second agent's instruction file, recorded by an earlier run and not
        # selected by this one: a `section` row the reconciler has to read and
        # this release does not write. The path is one Lore installs to, which
        # is the only kind a manifest may name.
        blob = installed / "AGENTS.md"
        blob.write_bytes(NOT_UTF8)
        payload = read_manifest(installed)
        payload["files"].append(
            {
                "path": "AGENTS.md",
                "kind": "section",
                "source": "agent-instructions:agents-md",
                "hash": "sha256:" + "0" * 64,
            }
        )
        rewrite_manifest(installed, payload)

        message = assert_reported_not_raised(run_init(runner))

        assert str(blob) in message
        assert "not valid UTF-8 text" in message

    def test_an_installed_file_is_hashed_as_bytes_and_never_decoded(
        self, runner, installed
    ):
        """A skill Lore owns is compared by raw digest, so binary is no obstacle."""
        target = installed / ".claude" / "skills" / "store-memory" / "SKILL.md"
        assert target.is_file()
        target.write_bytes(NOT_UTF8)

        result = run_init(runner)

        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# A path the filesystem itself refuses
# ---------------------------------------------------------------------------


ROOT_USER = hasattr(os, "geteuid") and os.geteuid() == 0

pytestmark_not_root = pytest.mark.skipif(
    ROOT_USER, reason="root ignores the permission bits these cases rely on"
)


@pytestmark_not_root
class TestAPathTheFilesystemRefuses:
    """Read-only files and directories are ordinary in a real repo — vendored
    trees, CI checkouts, `chmod -R a-w`. Every one of them reached the user as
    a `PermissionError` traceback with an empty stdout and no named file."""

    def test_a_read_only_installed_file_is_still_updated(self, runner, installed):
        """Lore recorded these bytes and nobody edited them, so the release's
        new content belongs there — and replacing the file needs no write
        permission on the file itself."""
        target = installed / ".claude" / "skills" / "store-memory" / "SKILL.md"
        target.chmod(0o444)

        result = run_init(runner, "--access", "cli")

        assert result.exit_code == 0, result.output
        assert "Traceback" not in result.stderr

    def test_a_read_only_installed_file_keeps_its_permissions(self, runner, installed):
        target = installed / ".claude" / "skills" / "store-memory" / "SKILL.md"
        target.chmod(0o444)

        run_init(runner, "--access", "cli")

        assert stat.S_IMODE(target.stat().st_mode) == 0o444

    def test_a_read_only_parent_directory_names_the_file(self, runner, fresh):
        parent = fresh / ".claude" / "skills"
        parent.mkdir(parents=True)
        parent.chmod(0o555)
        try:
            message = assert_reported_not_raised(run_init(runner))
        finally:
            parent.chmod(0o755)

        assert str(parent) in message
        assert "re-run" in message

    def test_a_read_only_project_root_names_the_path(self, runner, fresh):
        fresh.chmod(0o555)
        try:
            message = assert_reported_not_raised(run_init(runner))
        finally:
            fresh.chmod(0o755)

        assert str(fresh) in message


# ---------------------------------------------------------------------------
# What a refused run leaves behind
# ---------------------------------------------------------------------------


def tree_snapshot(root: Path) -> set[str]:
    """Every path under *root*, as repo-relative POSIX strings."""
    return {
        candidate.relative_to(root).as_posix()
        for candidate in root.rglob("*")
    }


class TestARefusedRunWritesNothing:
    """A stop is a refusal, not a partial application.

    A directory sitting on `.gitignore` used to stop the run *after* `.lore/`,
    the instruction file and every skill had been written — nineteen untracked
    files and no manifest, so nothing knew what had been installed and the next
    run had no record to reconcile against. The paths a run will write are all
    known before the first byte, so they are all checked before the first byte.
    """

    @pytest.mark.parametrize("relative", OCCUPIED_PATHS)
    def test_a_fresh_project_is_left_exactly_as_it_was(self, runner, fresh, relative):
        occupied = fresh / relative
        occupied.mkdir(parents=True)
        before = tree_snapshot(fresh)

        assert_reported_not_raised(run_init(runner))

        assert tree_snapshot(fresh) == before

    @pytest.mark.parametrize("relative", OCCUPIED_PATHS)
    def test_no_manifest_is_invented_for_a_run_that_did_not_happen(
        self, runner, fresh, relative
    ):
        occupied = fresh / relative
        occupied.mkdir(parents=True)

        assert_reported_not_raised(run_init(runner))

        assert not manifest_file(fresh).is_file()


class TestAFailurePartwayThroughStillLeavesAManifest:
    """The write that fails for a reason no check could have predicted.

    A full disk, a revoked permission, a filesystem that goes away mid-run: the
    plan was sound and the tree was sound, and the run still stops with some of
    its files written. What must not also be lost is the record of *which*, or
    the next run has nothing to reconcile against and no way to remove what this
    one left.
    """

    @pytest.fixture()
    def failing_write(self, monkeypatch):
        """Let the first two skills land, then break the writer.

        Keyed on ``SKILL.md`` so the failure lands in the planned half of the
        run: the seeded `.lore/` trees are written first and are not what the
        manifest is a record of.
        """
        from lore import safewrite

        real = safewrite.atomic_write_bytes
        seen = {"count": 0}

        def failing(target, data, *, project_root=None):
            if Path(target).name == "SKILL.md":
                seen["count"] += 1
                if seen["count"] > 2:
                    raise OSError(28, "No space left on device")
            real(target, data, project_root=project_root)

        monkeypatch.setattr(safewrite, "atomic_write_bytes", failing)
        return seen

    def test_the_run_reports_the_failure_rather_than_raising(
        self, runner, fresh, failing_write
    ):
        assert_reported_not_raised(run_init(runner))

    def test_the_manifest_records_what_the_run_managed_to_write(
        self, runner, fresh, failing_write
    ):
        run_init(runner)

        assert manifest_file(fresh).is_file()
        recorded = {row["path"] for row in read_manifest(fresh)["files"]}
        assert recorded
        for path in recorded:
            assert (fresh / path).is_file(), f"{path} recorded but never written"

    def test_the_next_run_finishes_the_job(self, runner, fresh, failing_write):
        run_init(runner)
        failing_write["count"] = -(10**6)  # the filesystem came back

        result = run_init(runner)

        assert result.exit_code == 0, result.output
        assert (fresh / ".claude" / "skills" / "inquest" / "SKILL.md").is_file()
