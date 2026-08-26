"""Unit tests for lore.manifest — the install-manifest record and its digests.

The manifest is what tells a file Lore installed apart from a file the project
authored. Everything the reconciliation table decides rests on the digests here
being exact: raw bytes with no newline normalisation, the rendered content after
access-mode selection, and — for a marked block inside a user-owned file — only
the text between the markers.

An unreadable manifest is a fall-soft condition, never an error: one stderr
warning, ``None`` back, and the caller drops to the legacy-hash fallback.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from lore import manifest
from lore.initplan import FileAction, PlannedFile

BEGIN = "<!-- lore:begin -->"
END = "<!-- lore:end -->"


def _planned(path: str, *, kind: str = "owned", source: str = "skill:demo", digest: str = "sha256:abc") -> PlannedFile:
    return PlannedFile(
        path=path,
        action=FileAction.CREATE,
        kind=kind,
        source=source,
        digest=digest,
        detail=None,
    )


def _write(tmp_path, *files: PlannedFile, **overrides):
    payload = {
        "answers": {"agents": ["claude"], "access_mode": "native"},
        "targets": {"claude": ".claude/skills"},
        "lore_version": "0.10.0",
        "catalogue_version": 2,
    }
    payload.update(overrides)
    return manifest.write(tmp_path, files=files, **payload)


# ---------------------------------------------------------------------------
# bytes_digest
# ---------------------------------------------------------------------------


class TestBytesDigest:
    def test_carries_the_sha256_prefix(self):
        assert manifest.bytes_digest(b"hello").startswith("sha256:")

    def test_is_the_hexdigest_of_the_input(self):
        assert manifest.bytes_digest(b"hello") == "sha256:" + hashlib.sha256(b"hello").hexdigest()

    def test_empty_input_is_stable_across_calls(self):
        assert manifest.bytes_digest(b"") == manifest.bytes_digest(b"")

    def test_different_inputs_differ(self):
        assert manifest.bytes_digest(b"a") != manifest.bytes_digest(b"b")


# ---------------------------------------------------------------------------
# file_digest
# ---------------------------------------------------------------------------


class TestFileDigest:
    def test_equals_the_digest_of_the_files_bytes(self, tmp_path):
        target = tmp_path / "skill.md"
        target.write_bytes(b"body\n")
        assert manifest.file_digest(target) == manifest.bytes_digest(b"body\n")

    def test_does_not_normalise_newlines(self, tmp_path):
        lf = tmp_path / "lf.md"
        crlf = tmp_path / "crlf.md"
        lf.write_bytes(b"one\ntwo\n")
        crlf.write_bytes(b"one\r\ntwo\r\n")
        assert manifest.file_digest(lf) != manifest.file_digest(crlf)


# ---------------------------------------------------------------------------
# section_digest / section_text
# ---------------------------------------------------------------------------


class TestSectionDigest:
    def test_ignores_text_outside_the_markers(self):
        first = f"my prose\n{BEGIN}\nblock\n{END}\ntrailing\n"
        second = f"REWRITTEN prose\n{BEGIN}\nblock\n{END}\nDIFFERENT trailing\n"
        assert manifest.section_digest(first, BEGIN, END) == manifest.section_digest(second, BEGIN, END)

    def test_changes_when_the_marked_text_changes(self):
        first = f"prose\n{BEGIN}\nblock\n{END}\n"
        second = f"prose\n{BEGIN}\nother\n{END}\n"
        assert manifest.section_digest(first, BEGIN, END) != manifest.section_digest(second, BEGIN, END)

    def test_excludes_the_marker_lines_themselves(self):
        text = f"{BEGIN}\nblock\n{END}\n"
        assert manifest.section_digest(text, BEGIN, END) == manifest.bytes_digest(b"block\n")

    def test_raises_when_the_block_is_absent(self):
        with pytest.raises(ValueError):
            manifest.section_digest("no markers here\n", BEGIN, END)


class TestSectionText:
    def test_returns_the_text_between_the_markers(self):
        text = f"prose\n{BEGIN}\nblock\nmore\n{END}\ntail\n"
        assert manifest.section_text(text, BEGIN, END) == "block\nmore\n"

    def test_returns_none_when_the_opener_is_absent(self):
        assert manifest.section_text("prose only\n", BEGIN, END) is None

    def test_returns_none_when_the_closer_is_absent(self):
        assert manifest.section_text(f"{BEGIN}\nblock\n", BEGIN, END) is None

    def test_empty_block_is_an_empty_string_not_none(self):
        assert manifest.section_text(f"{BEGIN}\n{END}\n", BEGIN, END) == ""


# ---------------------------------------------------------------------------
# write / load round-trip
# ---------------------------------------------------------------------------


class TestWriteAndLoad:
    def test_write_returns_the_manifest_path(self, tmp_path):
        from lore.paths import install_manifest_path

        assert _write(tmp_path, _planned(".claude/skills/a/SKILL.md")) == install_manifest_path(tmp_path)

    def test_round_trip_preserves_every_recorded_field(self, tmp_path):
        _write(
            tmp_path,
            _planned(".claude/skills/demo/SKILL.md", source="skill:demo", digest="sha256:one"),
            _planned("CLAUDE.md", kind="section", source="agent-instructions:claude", digest="sha256:two"),
        )
        loaded = manifest.load(tmp_path)

        assert loaded.manifest_version == manifest.MANIFEST_VERSION
        assert loaded.lore_version == "0.10.0"
        assert loaded.catalogue_version == 2
        assert loaded.answers == {"agents": ["claude"], "access_mode": "native"}
        assert loaded.targets == {"claude": ".claude/skills"}
        assert [(e.path, e.kind, e.source, e.hash) for e in loaded.files] == [
            (".claude/skills/demo/SKILL.md", "owned", "skill:demo", "sha256:one"),
            ("CLAUDE.md", "section", "agent-instructions:claude", "sha256:two"),
        ]

    def test_files_are_written_sorted_by_path(self, tmp_path):
        _write(
            tmp_path,
            _planned(".claude/skills/z/SKILL.md"),
            _planned(".claude/skills/a/SKILL.md"),
            _planned(".claude/skills/m/SKILL.md"),
        )
        payload = json.loads((tmp_path / ".lore" / ".install-manifest.json").read_text())
        assert [entry["path"] for entry in payload["files"]] == [
            ".claude/skills/a/SKILL.md",
            ".claude/skills/m/SKILL.md",
            ".claude/skills/z/SKILL.md",
        ]

    def test_entries_with_no_digest_are_not_recorded(self, tmp_path):
        removal = PlannedFile(
            path=".claude/skills/gone/SKILL.md",
            action=FileAction.REMOVE,
            kind="owned",
            source="skill:gone",
            digest=None,
            detail="renamed",
        )
        _write(tmp_path, _planned(".claude/skills/kept/SKILL.md"), removal)
        assert [entry.path for entry in manifest.load(tmp_path).files] == [
            ".claude/skills/kept/SKILL.md"
        ]

    def test_two_writes_of_the_same_content_differ_only_in_generated_at(self, tmp_path):
        _write(tmp_path, _planned(".claude/skills/a/SKILL.md"))
        first = json.loads((tmp_path / ".lore" / ".install-manifest.json").read_text())
        _write(tmp_path, _planned(".claude/skills/a/SKILL.md"))
        second = json.loads((tmp_path / ".lore" / ".install-manifest.json").read_text())

        del first["generated_at"]
        del second["generated_at"]
        assert first == second

    def test_generated_at_is_an_iso_utc_stamp(self, tmp_path):
        _write(tmp_path, _planned(".claude/skills/a/SKILL.md"))
        stamp = manifest.load(tmp_path).generated_at
        assert stamp.endswith("Z")
        assert len(stamp) == len("2026-08-25T14:32:00Z")

    def test_write_creates_the_lore_directory_when_absent(self, tmp_path):
        target = _write(tmp_path, _planned(".claude/skills/a/SKILL.md"))
        assert target.is_file()

    def test_stores_backslash_paths_as_posix(self, tmp_path):
        _write(tmp_path, _planned(".claude\\skills\\demo\\SKILL.md"))
        payload = json.loads((tmp_path / ".lore" / ".install-manifest.json").read_text())
        assert payload["files"][0]["path"] == ".claude/skills/demo/SKILL.md"

    def test_stored_paths_never_leak_a_platform_separator(self, tmp_path):
        _write(tmp_path, _planned(".claude\\skills\\demo\\SKILL.md"))
        assert all("\\" not in entry.path for entry in manifest.load(tmp_path).files)


class TestResolvePath:
    def test_rehydrates_a_posix_path_against_the_project_root(self, tmp_path):
        resolved = manifest.resolve_path(tmp_path, ".claude/skills/demo/SKILL.md")
        assert resolved == tmp_path / ".claude" / "skills" / "demo" / "SKILL.md"

    def test_a_root_level_path_resolves_directly_under_the_root(self, tmp_path):
        assert manifest.resolve_path(tmp_path, "CLAUDE.md") == tmp_path / "CLAUDE.md"


# ---------------------------------------------------------------------------
# load — the fall-soft paths
# ---------------------------------------------------------------------------


class TestLoadFallsSoft:
    def test_absent_manifest_returns_none_without_warning(self, tmp_path, capsys):
        assert manifest.load(tmp_path) is None
        assert capsys.readouterr().err == ""

    def test_unparseable_manifest_returns_none_and_warns_once(self, tmp_path, capsys):
        target = tmp_path / ".lore" / ".install-manifest.json"
        target.parent.mkdir(parents=True)
        target.write_text("{not json")

        assert manifest.load(tmp_path) is None
        stderr = capsys.readouterr().err
        assert len(stderr.strip().splitlines()) == 1
        assert stderr.startswith(f"lore: unreadable install manifest at {target}: ")
        assert stderr.rstrip().endswith("(falling back to legacy hashes)")

    def test_every_failing_load_warns_again(self, tmp_path, capsys):
        target = tmp_path / ".lore" / ".install-manifest.json"
        target.parent.mkdir(parents=True)
        target.write_text("{not json")

        manifest.load(tmp_path)
        capsys.readouterr()
        manifest.load(tmp_path)
        assert capsys.readouterr().err != ""

    def test_unknown_manifest_version_returns_none_and_warns(self, tmp_path, capsys):
        target = tmp_path / ".lore" / ".install-manifest.json"
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps({"manifest_version": 99, "files": []}))

        assert manifest.load(tmp_path) is None
        stderr = capsys.readouterr().err
        assert len(stderr.strip().splitlines()) == 1
        assert "99" in stderr

    def test_a_files_entry_missing_a_required_key_is_unreadable(self, tmp_path, capsys):
        target = tmp_path / ".lore" / ".install-manifest.json"
        target.parent.mkdir(parents=True)
        target.write_text(
            json.dumps(
                {
                    "manifest_version": manifest.MANIFEST_VERSION,
                    "files": [
                        {
                            "path": ".claude/skills/a/SKILL.md",
                            "kind": "owned",
                            "source": "skill:a",
                            "hash": "sha256:1",
                        },
                        {
                            "path": ".claude/skills/b/SKILL.md",
                            "kind": "owned",
                            "source": "skill:b",
                        },
                    ],
                }
            )
        )

        assert manifest.load(tmp_path) is None
        assert "hash" in capsys.readouterr().err

    def test_a_non_object_payload_is_unreadable(self, tmp_path, capsys):
        target = tmp_path / ".lore" / ".install-manifest.json"
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps([1, 2, 3]))

        assert manifest.load(tmp_path) is None
        assert capsys.readouterr().err != ""

    def test_a_non_list_files_value_is_unreadable(self, tmp_path, capsys):
        target = tmp_path / ".lore" / ".install-manifest.json"
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps({"manifest_version": manifest.MANIFEST_VERSION, "files": {}}))

        assert manifest.load(tmp_path) is None
        assert capsys.readouterr().err != ""


class TestManifestByPath:
    def test_indexes_every_entry_by_its_path(self, tmp_path):
        _write(tmp_path, _planned(".claude/skills/b/SKILL.md", digest="sha256:b"), _planned(".claude/skills/a/SKILL.md", digest="sha256:a"))
        by_path = manifest.load(tmp_path).by_path
        assert set(by_path) == {
            ".claude/skills/a/SKILL.md",
            ".claude/skills/b/SKILL.md",
        }
        assert by_path[".claude/skills/a/SKILL.md"].hash == "sha256:a"


# ---------------------------------------------------------------------------
# load — a manifest whose JSON parses but whose shape is wrong
# ---------------------------------------------------------------------------


def _valid_payload() -> dict:
    """The smallest manifest this release reads without complaint."""
    return {
        "manifest_version": manifest.MANIFEST_VERSION,
        "lore_version": "0.10.0",
        "catalogue_version": 2,
        "generated_at": "2026-08-25T17:10:22Z",
        "answers": {"agents": ["claude"]},
        "targets": {"claude": ".claude/skills"},
        "files": [
            {
                "path": ".claude/skills/demo/SKILL.md",
                "kind": "owned",
                "source": "skill:demo",
                "hash": "sha256:abc",
            }
        ],
    }


def _bad_row(**overrides) -> dict:
    """A valid manifest whose single ``files`` row carries *overrides*."""
    payload = _valid_payload()
    payload["files"][0].update(overrides)
    return payload


def _bad_top(**overrides) -> dict:
    """A valid manifest whose top-level fields carry *overrides*."""
    payload = _valid_payload()
    payload.update(overrides)
    return payload


MALFORMED_MANIFESTS: dict[str, dict] = {
    "path is a number": _bad_row(path=7),
    "path holds a NUL byte": _bad_row(path=".claude/skills/a\x00b.md"),
    "path holds a bare NUL": _bad_row(path="\x00"),
    "path holds a control character": _bad_row(path=".claude/skills/a\x07b.md"),
    "path names a file Lore never installs": _bad_row(path=".git/config"),
    "path names the project's own notes": _bad_row(path="notes/mine.md"),
    "path names a directory above the skills root": _bad_row(path=".claude/config"),
    "path walks out of the project": _bad_row(path="../VICTIM.txt"),
    "path is absolute": _bad_row(path="/etc/passwd"),
    "path is empty": _bad_row(path=""),
    "path is null": _bad_row(path=None),
    "path is a list": _bad_row(path=[".claude/skills"]),
    "kind is a number": _bad_row(kind=3),
    "source is an object": _bad_row(source={"skill": "demo"}),
    "hash is a number": _bad_row(hash=1),
    "hash is null": _bad_row(hash=None),
    "a row is a string": _bad_top(files=["not-an-object"]),
    "a row is a list": _bad_top(files=[[]]),
    "a row is null": _bad_top(files=[None]),
    "files is a string": _bad_top(files="everything"),
    "answers is a list": _bad_top(answers=[]),
    "targets is a string": _bad_top(targets="claude"),
    "lore_version is a number": _bad_top(lore_version=10),
    "catalogue_version is a string": _bad_top(catalogue_version="2"),
    "generated_at is a number": _bad_top(generated_at=0),
}
"""Every way a manifest can parse as JSON and still not be a manifest.

The four found by smoke testing are in here, but the class is what is under
test: `load` promises the caller a ``Manifest`` or ``None``, and a payload that
cannot produce one has to take the ``None`` branch whatever shape its damage
takes.
"""


class TestLoadRejectsAMalformedShape:
    @pytest.mark.parametrize(
        "payload",
        list(MALFORMED_MANIFESTS.values()),
        ids=list(MALFORMED_MANIFESTS),
    )
    def test_returns_none_and_warns_like_an_unreadable_file(self, tmp_path, capsys, payload):
        target = tmp_path / ".lore" / ".install-manifest.json"
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps(payload))

        assert manifest.load(tmp_path) is None
        stderr = capsys.readouterr().err
        assert len(stderr.strip().splitlines()) == 1
        assert stderr.startswith(f"lore: unreadable install manifest at {target}: ")
        assert stderr.rstrip().endswith("(falling back to legacy hashes)")


class TestLoadLetsNoExceptionEscape:
    """The fail-soft promise `_recorded_entries` rests on, held for any failure."""

    def test_bytes_that_are_not_utf8_are_unreadable(self, tmp_path, capsys):
        target = tmp_path / ".lore" / ".install-manifest.json"
        target.parent.mkdir(parents=True)
        target.write_bytes(b'{"m\x82\xff": 1}')

        assert manifest.load(tmp_path) is None
        assert str(target) in capsys.readouterr().err

    def test_an_unexpected_exception_from_parsing_still_falls_soft(
        self, tmp_path, capsys, monkeypatch
    ):
        _write(tmp_path, _planned(".claude/skills/a/SKILL.md"))

        def boom(payload):
            raise RecursionError("too deep")

        monkeypatch.setattr(manifest, "_parse", boom)
        assert manifest.load(tmp_path) is None
        stderr = capsys.readouterr().err
        assert str(tmp_path) in stderr
        assert "RecursionError" in stderr
        assert "too deep" in stderr


# ---------------------------------------------------------------------------
# Which paths a manifest may name
# ---------------------------------------------------------------------------
#
# A manifest is generated and never hand-edited, and this module's own contract
# calls it untrusted input. Every removal `lore init` performs targets a path
# from here, so "which paths may a row name" is the whole of what stands
# between a corrupt manifest and an unlink.
#
# Smoke round 7 found the two gaps. A NUL byte is none of the shapes
# `escape_reason` rejected, so the row was accepted and the first `lstat` on it
# raised `ValueError: embedded null character in path` — exit 1, no filename,
# and every later `lore init` wedged the same way, while the `..` and absolute
# rows beside it were fail-soft. And a `REMOVE` row could name *any* path
# inside the project — `.git/config` was deleted, reported as
# `Removed .git/config — no longer installed here`, exit 0 — while the write
# side already refused any path this release does not produce.


ACCEPTED_PATHS = (
    ".claude/skills/inquest/SKILL.md",
    ".claude/skills/inquest/references/rite.md",
    ".claude/skills/.gitignore",
    ".lore/skills/store-memory/SKILL.md",
    ".lore/skills/.gitignore",
    ".lore/LORE-AGENT.md",
    "CLAUDE.md",
    "AGENTS.md",
    "GEMINI.md",
    ".cursor/rules/lore.mdc",
    ".gitignore",
)
"""Every kind of path this release installs to: a skill file, a nested skill
reference, the generated listing at a skills root, the rendered agent doc and
each agent's instruction file — plus the root `.gitignore`, which no release
writes any more and every one still has to be able to *remove* a block from.
A release that stopped accepting it would reject the manifest of every project
carrying the retired block, and lose the record of everything else in it."""


REFUSED_PATHS = {
    "a NUL inside a component": ".claude/skills/a\x00b.md",
    "a NUL alone": "\x00",
    "a NUL at the end": ".claude/skills/inquest/SKILL.md\x00",
    "a bell character": ".claude/skills/\x07/SKILL.md",
    "a git internal": ".git/config",
    "the project's source": "src/lore/init.py",
    "a dotfile at the root": ".env",
    "a sibling of a skills root": ".claude/settings.json",
    "an instruction file that is not one": "README.md",
    "the manifest itself": ".lore/.install-manifest.json",
    "the database": ".lore/lore.db",
    "a walk out of the project": "../VICTIM.txt",
    "an absolute path": "/etc/passwd",
    "an empty path": "",
    "whitespace only": "   ",
}
"""Everything a generated manifest cannot have written. The last three were
already refused as shapes; the rest are the same question asked of the path's
destination rather than of its spelling."""


class TestUnownableReason:
    @pytest.mark.parametrize("path", ACCEPTED_PATHS)
    def test_a_path_this_release_installs_to_is_accepted(self, path):
        assert manifest.unownable_reason(path) is None

    @pytest.mark.parametrize("path", ACCEPTED_PATHS)
    def test_a_windows_spelling_of_the_same_path_is_accepted(self, path):
        assert manifest.unownable_reason(path.replace("/", "\\")) is None

    @pytest.mark.parametrize(
        "path", list(REFUSED_PATHS.values()), ids=list(REFUSED_PATHS)
    )
    def test_anything_else_is_refused_with_a_reason(self, path):
        reason = manifest.unownable_reason(path)

        assert reason, f"{path!r} was accepted"
        assert not reason.endswith("."), "the reason is a phrase, not a sentence"

    def test_a_nul_says_what_is_wrong_with_it(self):
        reason = manifest.unownable_reason(".claude/skills/a\x00b.md")

        assert reason is not None
        assert "NUL" in reason or "null" in reason

    def test_the_escape_shapes_keep_their_own_wording(self):
        assert "walks out of the project" in (
            manifest.unownable_reason("../VICTIM.txt") or ""
        )
        assert "is absolute" in (manifest.unownable_reason("/etc/passwd") or "")


class TestEveryPathThisReleaseWritesSurvivesTheRule:
    """The rule is derived from the registry and the skills roots, so a row this
    release could actually write can never be one it then refuses to read."""

    def test_the_manifest_a_real_plan_produces_parses_back(self, tmp_path):
        from lore import init as init_module

        rows = [
            _planned(path, source="skill:demo") for path in ACCEPTED_PATHS
        ]
        _write(tmp_path, *rows)

        loaded = manifest.load(tmp_path)

        assert loaded is not None
        assert {entry.path for entry in loaded.files} == set(ACCEPTED_PATHS)
        assert init_module.LORE_AGENT_PATH in ACCEPTED_PATHS

    def test_every_registry_instruction_file_is_ownable(self):
        from lore.agents import load_registry

        for row in load_registry():
            if row.instruction_file:
                assert manifest.unownable_reason(row.instruction_file) is None

    def test_every_registry_skills_directory_is_ownable(self):
        from lore.agents import load_registry

        for row in load_registry():
            if row.skills_dir:
                assert manifest.unownable_reason(f"{row.skills_dir}/x/SKILL.md") is None
