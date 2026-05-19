"""E2E tests for `lore impacts` — codex-seed lookup (US-003 + US-004).

Workflow: conceptual-workflows-impacts.
Tech Spec: lore-impacts-tech-spec.
Stories:
    - lore-impacts-us-003 — codex-seed lookup happy path (text mode).
    - lore-impacts-us-004 — JSON envelope, unknown-ID errors, kind classification.

Click 8.3 gotcha (project memory + tester standards reference):
`mix_stderr=False` was removed from CliRunner. Use `result.stdout` and
`result.stderr` separately. The default CliRunner already separates the
two streams, no init kwarg required.

These tests target the codex-seed branch only. Path-seed scenarios live
in a sibling story (US-005 / US-006) and a sibling Red mission.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

from lore.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_codex_entry(
    project_dir: Path,
    *,
    entry_id: str,
    binds: list | None = None,
    omit_binds: bool = False,
) -> Path:
    """Write a minimal codex entry under ``.lore/codex/<entry_id>.md``.

    Mirrors the helper used in ``tests/e2e/test_health_schemas_binds.py``
    so the two suites stay in lockstep on what a valid `binds:` entry
    looks like on disk.
    """
    fm: dict = {
        "id": entry_id,
        "title": entry_id.replace("-", " ").title(),
        "summary": f"Codex entry {entry_id}.",
    }
    if not omit_binds:
        fm["binds"] = binds if binds is not None else []
    front = yaml.safe_dump(fm, sort_keys=False, default_flow_style=False)
    path = project_dir / ".lore" / "codex" / f"{entry_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{front}---\nBody for {entry_id}.\n", encoding="utf-8")
    return path


# ===========================================================================
# Command surface — `lore impacts` is a top-level command
# ===========================================================================


def test_impacts_command_is_registered_at_top_level(project_dir, runner):
    """conceptual-workflows-impacts — `lore impacts` is a top-level surface.

    Per Tech Spec § "CLI Command" → "Registration": sibling to `lore codex`,
    NOT a subcommand under `lore codex`.
    """
    result = runner.invoke(main, ["impacts", "--help"])
    assert result.exit_code == 0, result.output
    assert "No such command" not in result.output
    assert "impacts" in result.output


def test_impacts_help_lists_token_argument(project_dir, runner):
    """The help text should advertise the positional TOKEN argument."""
    result = runner.invoke(main, ["impacts", "--help"])
    assert result.exit_code == 0
    assert "TOKEN" in result.output or "token" in result.output


def test_impacts_help_lists_json_flag(project_dir, runner):
    """The help text must mention the `--json` flag (FR-12)."""
    result = runner.invoke(main, ["impacts", "--help"])
    assert result.exit_code == 0
    assert "--json" in result.output


def test_impacts_missing_token_argument_is_usage_error(project_dir, runner):
    """Running `lore impacts` with no token exits 2 (Click UsageError)."""
    result = runner.invoke(main, ["impacts"], catch_exceptions=False)
    assert result.exit_code == 2
    assert "Missing argument" in result.output


# ===========================================================================
# US-003 — Scenario 1: mixed exact + glob bindings, declaration order
# ===========================================================================


def test_codex_seed_mixed_bindings_declaration_order(project_dir, runner):
    """conceptual-workflows-impacts — Steps 2+3 codex-seed text render.

    Mixed exact + glob bindings render one per line in declaration order,
    no annotation, trailing newline. stderr empty, exit 0.
    """
    _write_codex_entry(
        project_dir,
        entry_id="dec-006-id-references",
        binds=[
            "src/lore/cli.py",
            "src/lore/**/*.py",
            "tests/unit/test_models.py",
        ],
    )
    result = runner.invoke(main, ["impacts", "dec-006-id-references"])
    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    assert result.stdout == (
        "src/lore/cli.py\nsrc/lore/**/*.py\ntests/unit/test_models.py\n"
    )


# ===========================================================================
# US-003 — Scenario 2: empty `binds: []` → no output, exit 0
# ===========================================================================


def test_codex_seed_empty_binds_list_exits_zero_no_output(project_dir, runner):
    """conceptual-workflows-impacts — Empty Result Behaviour: codex seed.

    `binds: []` produces no stdout, no stderr, exit 0 (FR-14).
    """
    _write_codex_entry(project_dir, entry_id="entry-a", binds=[])
    result = runner.invoke(main, ["impacts", "entry-a"])
    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert result.stderr == ""


# ===========================================================================
# US-003 — Scenario 3: missing `binds:` key → identical to empty list
# ===========================================================================


def test_codex_seed_missing_binds_key_behaves_like_empty(project_dir, runner):
    """conceptual-workflows-impacts — Step 2: missing binds == empty list (FR-4)."""
    _write_codex_entry(project_dir, entry_id="entry-b", omit_binds=True)
    result = runner.invoke(main, ["impacts", "entry-b"])
    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert result.stderr == ""


# ===========================================================================
# US-003 — Scenario 4: declaration order, not alphabetical
# ===========================================================================


def test_codex_seed_preserves_non_alphabetical_declaration_order(project_dir, runner):
    """conceptual-workflows-impacts — Determinism: codex-seed author order."""
    _write_codex_entry(
        project_dir,
        entry_id="ordered",
        binds=["z/last.py", "a/first.py", "m/middle.py"],
    )
    result = runner.invoke(main, ["impacts", "ordered"])
    assert result.exit_code == 0, result.output
    assert result.stdout == "z/last.py\na/first.py\nm/middle.py\n"


# ===========================================================================
# US-003 — Scenario 5: bare ID routes to codex branch, not path branch
# ===========================================================================


def test_token_without_slash_or_dot_routes_to_codex(project_dir, runner):
    """conceptual-workflows-impacts — Token Classification: no `/` and no `.` → codex.

    The implementation must NOT misclassify a bare id as a path and emit
    "Path is outside the project root".
    """
    _write_codex_entry(
        project_dir,
        entry_id="tech-arch-source-layout",
        binds=["src/lore/cli.py"],
    )
    result = runner.invoke(main, ["impacts", "tech-arch-source-layout"])
    assert result.exit_code == 0, result.output
    assert "Path is outside the project root" not in result.stderr
    assert "Path is outside the project root" not in result.output
    assert "src/lore/cli.py" in result.stdout


# ===========================================================================
# US-004 — Scenario 1: --json envelope on a populated entry
# ===========================================================================


def test_json_envelope_codex_seed_populated(project_dir, runner):
    """conceptual-workflows-impacts — Step 3 codex-seed JSON mode.

    Envelope keyed `impacts`; items shaped `{path, kind}` in declaration order;
    `kind` is `"exact"` or `"glob"` per `is_glob_pattern`.
    """
    _write_codex_entry(
        project_dir,
        entry_id="dec-006-id-references",
        binds=["src/lore/cli.py", "src/lore/**/*.py"],
    )
    result = runner.invoke(
        main, ["impacts", "dec-006-id-references", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    assert json.loads(result.stdout) == {
        "impacts": [
            {"path": "src/lore/cli.py", "kind": "exact"},
            {"path": "src/lore/**/*.py", "kind": "glob"},
        ]
    }


# ===========================================================================
# US-004 — Scenario 2: empty JSON envelope
# ===========================================================================


def test_json_envelope_codex_seed_empty(project_dir, runner):
    """conceptual-workflows-impacts — Empty Result Behaviour: `{"impacts": []}`.

    Must emit the envelope, NOT a bare empty string (FR-14).
    """
    _write_codex_entry(project_dir, entry_id="entry-empty", binds=[])
    result = runner.invoke(main, ["impacts", "entry-empty", "--json"])
    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    assert json.loads(result.stdout) == {"impacts": []}


def test_json_envelope_codex_seed_missing_key_is_empty(project_dir, runner):
    """conceptual-workflows-impacts — FR-4 parity in JSON mode."""
    _write_codex_entry(project_dir, entry_id="no-binds", omit_binds=True)
    result = runner.invoke(main, ["impacts", "no-binds", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"impacts": []}


# ===========================================================================
# US-004 — Scenario 3: unknown ID in default mode
# ===========================================================================


def test_unknown_codex_id_default_mode(project_dir, runner):
    """conceptual-workflows-impacts — Failure Modes: unknown codex id, exit 1.

    Exact stderr text: `Unknown codex id: "no-such-id"` with trailing newline.
    Empty stdout. Subprocess used so the stderr stream is the real one
    (CliRunner separates stdout/stderr in Click 8.3, but we also pin the
    exact bytes via subprocess to defeat any future renderer changes).
    """
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from lore.cli import main; main()",
            "impacts",
            "no-such-id",
        ],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )
    assert proc.returncode == 1
    assert proc.stdout == ""
    assert proc.stderr == 'Unknown codex id: "no-such-id"\n'


def test_unknown_codex_id_default_mode_via_runner(project_dir, runner):
    """conceptual-workflows-impacts — Scenario 3 via CliRunner.

    Click 8.3 keeps stderr separate by default; the test pins the same
    error message + exit code without shelling out.
    """
    result = runner.invoke(main, ["impacts", "no-such-id"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert 'Unknown codex id: "no-such-id"' in result.stderr


# ===========================================================================
# US-004 — Scenario 4: unknown ID in JSON mode
# ===========================================================================


def test_unknown_codex_id_json_mode(project_dir, runner):
    """conceptual-workflows-impacts — Failure Modes JSON form.

    stderr parses as `{"error": "Unknown codex id: \"no-such-id\""}`,
    stdout is empty, exit 1.
    """
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from lore.cli import main; main()",
            "impacts",
            "no-such-id",
            "--json",
        ],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )
    assert proc.returncode == 1
    assert proc.stdout == ""
    payload = json.loads(proc.stderr.strip())
    assert payload == {"error": 'Unknown codex id: "no-such-id"'}


def test_unknown_codex_id_json_mode_via_runner(project_dir, runner):
    """conceptual-workflows-impacts — Scenario 4 via CliRunner."""
    result = runner.invoke(main, ["impacts", "no-such-id", "--json"])
    assert result.exit_code == 1
    assert result.stdout == ""
    payload = json.loads(result.stderr.strip())
    assert payload == {"error": 'Unknown codex id: "no-such-id"'}


# ===========================================================================
# US-004 — Scenario 5: kind classification covers every glob char
# ===========================================================================


def test_kind_classification_covers_every_glob_char(project_dir, runner):
    """conceptual-workflows-impacts — Step 3: `*`, `?`, `[` each force glob."""
    _write_codex_entry(
        project_dir,
        entry_id="x",
        binds=["foo.py", "foo/*.py", "foo?.py", "foo[ab].py"],
    )
    result = runner.invoke(main, ["impacts", "x", "--json"])
    assert result.exit_code == 0, result.output
    items = json.loads(result.stdout)["impacts"]
    assert [item["kind"] for item in items] == ["exact", "glob", "glob", "glob"]
    assert [item["path"] for item in items] == [
        "foo.py",
        "foo/*.py",
        "foo?.py",
        "foo[ab].py",
    ]


# ===========================================================================
# US-004 — Scenario 6: determinism across invocations
# ===========================================================================


def test_determinism_two_invocations_byte_identical(project_dir, runner):
    """conceptual-workflows-impacts — Determinism: byte-identical stdout.

    Two consecutive invocations against an unchanged repo must produce
    byte-equal stdout in both default and `--json` modes.
    """
    _write_codex_entry(project_dir, entry_id="x", binds=["a.py", "b.py"])

    r1 = runner.invoke(main, ["impacts", "x"])
    r2 = runner.invoke(main, ["impacts", "x"])
    assert r1.exit_code == 0
    assert r2.exit_code == 0
    assert r1.stdout == r2.stdout

    j1 = runner.invoke(main, ["impacts", "x", "--json"])
    j2 = runner.invoke(main, ["impacts", "x", "--json"])
    assert j1.exit_code == 0
    assert j2.exit_code == 0
    assert j1.stdout == j2.stdout


# ===========================================================================
# Stdout/stderr stream separation (CliRunner / Click 8.3)
# ===========================================================================


def test_codex_seed_success_writes_only_to_stdout(project_dir, runner):
    """Success path puts every binding on stdout, nothing on stderr."""
    _write_codex_entry(project_dir, entry_id="x", binds=["a.py", "b.py"])
    result = runner.invoke(main, ["impacts", "x"])
    assert result.exit_code == 0, result.output
    assert "a.py" in result.stdout
    assert "b.py" in result.stdout
    assert result.stderr == ""


def test_codex_seed_unknown_id_writes_only_to_stderr(project_dir, runner):
    """Error path puts the message on stderr, leaves stdout empty."""
    result = runner.invoke(main, ["impacts", "no-such-id"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr != ""


# ===========================================================================
# Cluster C (US-005 + US-006 + US-007) — code-seed lookup + --direct-links.
#
# Path-seed branch raises NotImplementedError in the current source — every
# test below should fail until Green lands the implementation. No production
# code is allowed in this Red phase.
# ===========================================================================


# ---------------------------------------------------------------------------
# US-005 — code-seed default text mode
# ---------------------------------------------------------------------------


def test_code_seed_mixed_exact_and_glob_sorted_alphabetically(project_dir, runner):
    """conceptual-workflows-impacts — Step 4 sort: alphabetical by codex id.

    Scenario 1: text mode mixes exact (unannotated) + glob (annotated).
    Sort is alphabetical; entries whose globs don't match are excluded.
    """
    _write_codex_entry(
        project_dir,
        entry_id="dec-006-id-references",
        binds=["src/lore/cli.py"],
    )
    _write_codex_entry(
        project_dir,
        entry_id="tech-arch-source-layout",
        binds=["src/lore/**/*.py"],
    )
    _write_codex_entry(
        project_dir,
        entry_id="conceptual-entities-knight",
        binds=["docs/knights/*.md"],
    )
    result = runner.invoke(main, ["impacts", "src/lore/cli.py"])
    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    assert result.stdout == (
        "dec-006-id-references\n"
        "tech-arch-source-layout  (glob: src/lore/**/*.py)\n"
    )


def test_code_seed_exact_and_glob_on_same_entry_dedupes_to_exact(project_dir, runner):
    """conceptual-workflows-impacts — Step 3 dedup: FR-9 exact precedence.

    Scenario 2: a single entry matching both exactly and via glob appears
    once, unannotated.
    """
    _write_codex_entry(
        project_dir,
        entry_id="dup-entry",
        binds=["src/lore/cli.py", "src/lore/**/*.py"],
    )
    result = runner.invoke(main, ["impacts", "src/lore/cli.py"])
    assert result.exit_code == 0, result.output
    assert result.stdout.count("dup-entry") == 1
    assert "(glob:" not in result.stdout


def test_code_seed_no_matches_empty_stdout_exit_zero(project_dir, runner):
    """conceptual-workflows-impacts — Empty Result Behaviour: path seed, no matches.

    Scenario 3: FR-14 empty result → exit 0, empty stdout/stderr.
    """
    _write_codex_entry(project_dir, entry_id="x", binds=["src/other/foo.py"])
    result = runner.invoke(main, ["impacts", "src/lore/orphan.py"])
    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert result.stderr == ""


def test_code_seed_recursive_glob_spans_multiple_segments(project_dir, runner):
    """conceptual-workflows-impacts — Step 3 "Glob with **": multi-segment match.

    Scenario 4: `**` spans arbitrarily deep nesting.
    """
    _write_codex_entry(
        project_dir,
        entry_id="tech-arch-source-layout",
        binds=["src/lore/**/*.py"],
    )
    result = runner.invoke(main, ["impacts", "src/lore/sub/deeper/foo.py"])
    assert result.exit_code == 0, result.output
    assert (
        "tech-arch-source-layout  (glob: src/lore/**/*.py)" in result.stdout
    )


def test_code_seed_single_segment_glob_does_not_span_directories(project_dir, runner):
    """conceptual-workflows-impacts — Step 3 "Plain glob": single `*` stays in one segment.

    Scenario 5: `src/lore/*.py` MUST NOT match `src/lore/sub/foo.py`.
    """
    _write_codex_entry(
        project_dir, entry_id="narrow-entry", binds=["src/lore/*.py"]
    )
    result = runner.invoke(main, ["impacts", "src/lore/sub/foo.py"])
    assert result.exit_code == 0, result.output
    assert "narrow-entry" not in result.stdout


def test_code_seed_empty_or_missing_binds_never_appears(project_dir, runner):
    """conceptual-workflows-impacts — FR-4 parity at the code-seed layer.

    Scenario 6: empty `binds:` and missing `binds:` are both excluded.
    """
    _write_codex_entry(project_dir, entry_id="entry-empty", binds=[])
    _write_codex_entry(project_dir, entry_id="entry-missing", omit_binds=True)
    result = runner.invoke(main, ["impacts", "src/lore/cli.py"])
    assert result.exit_code == 0, result.output
    assert "entry-empty" not in result.stdout
    assert "entry-missing" not in result.stdout


def test_code_seed_determinism(project_dir, runner):
    """conceptual-workflows-impacts — Determinism: byte-identical stdout.

    Scenario 7: two invocations against unchanged state produce byte-equal
    stdout.
    """
    _write_codex_entry(project_dir, entry_id="a", binds=["src/lore/cli.py"])
    _write_codex_entry(
        project_dir, entry_id="b", binds=["src/lore/**/*.py"]
    )
    r1 = runner.invoke(main, ["impacts", "src/lore/cli.py"])
    r2 = runner.invoke(main, ["impacts", "src/lore/cli.py"])
    assert r1.exit_code == 0, r1.output
    assert r2.exit_code == 0, r2.output
    assert r1.stdout == r2.stdout


def test_code_seed_malformed_entry_silently_skipped(project_dir, runner):
    """conceptual-workflows-impacts — Step 2: malformed `binds:` silently skipped.

    Scenario 8: read-tool never refuses; authoritative rejection lives in
    `lore health --scope schemas`.
    """
    _write_codex_entry(project_dir, entry_id="good", binds=["src/lore/cli.py"])
    bad_path = project_dir / ".lore" / "codex" / "bad.md"
    bad_path.write_text(
        "---\n"
        "id: bad\n"
        "title: Bad\n"
        "summary: Bad entry.\n"
        "binds:\n"
        "  - 123\n"
        "---\nBody.\n",
        encoding="utf-8",
    )
    result = runner.invoke(main, ["impacts", "src/lore/cli.py"])
    assert result.exit_code == 0, result.output
    assert "good" in result.stdout
    assert "bad" not in result.stdout


# ---------------------------------------------------------------------------
# US-006 — path normalisation, traversal, JSON envelope
# ---------------------------------------------------------------------------


def test_absolute_path_inside_repo_normalises_to_relative(project_dir, runner):
    """conceptual-workflows-impacts — Step 1: absolute → repo-relative.

    Scenario 1: absolute path inside repo yields identical output to its
    relative form. The cwd fixture chdir-s to `project_dir`, so this is
    purely about absolute-vs-relative input parity.
    """
    _write_codex_entry(
        project_dir,
        entry_id="dec-006-id-references",
        binds=["src/lore/cli.py"],
    )
    abs_path = str((project_dir / "src" / "lore" / "cli.py"))
    result = runner.invoke(main, ["impacts", abs_path])
    assert result.exit_code == 0, result.output
    assert result.stdout == "dec-006-id-references\n"


def test_path_outside_repo_rejected_text_mode(project_dir, runner):
    """conceptual-workflows-impacts — Failure Modes: path outside repo.

    Scenario 2: exit 1, stderr exactly the error message + newline.
    """
    result = runner.invoke(main, ["impacts", "/etc/passwd"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == 'Path is outside the project root: "/etc/passwd"\n'


def test_dotdot_traversal_rejected_text_mode(project_dir, runner):
    """conceptual-workflows-impacts — Failure Modes: traversal not allowed.

    Scenario 3: any `..` segment is rejected before any filesystem touch.
    """
    result = runner.invoke(main, ["impacts", "../foo.py"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == 'Path traversal not allowed: "../foo.py"\n'


def test_symlink_resolving_outside_repo_rejected(project_dir, runner):
    """conceptual-workflows-impacts — Step 1: symlinks resolving outside repo.

    Scenario 4: NFR-Security. Build `tests/data/link-out` → outside target.
    """
    target = project_dir.parent / "outside-target"
    target.mkdir(exist_ok=True)
    (project_dir / "tests" / "data").mkdir(parents=True, exist_ok=True)
    (project_dir / "tests" / "data" / "link-out").symlink_to(target)
    result = runner.invoke(main, ["impacts", "tests/data/link-out"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Path is outside the project root:" in result.stderr


def test_json_envelope_code_seed_mixed_matches(project_dir, runner):
    """conceptual-workflows-impacts — Step 4 JSON code-seed shape.

    Scenario 5: exact rows lack a `pattern` key; glob rows carry it.
    """
    _write_codex_entry(
        project_dir,
        entry_id="dec-006-id-references",
        binds=["src/lore/cli.py"],
    )
    _write_codex_entry(
        project_dir,
        entry_id="tech-arch-source-layout",
        binds=["src/lore/**/*.py"],
    )
    result = runner.invoke(main, ["impacts", "src/lore/cli.py", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "impacts": [
            {"id": "dec-006-id-references", "match": "exact"},
            {
                "id": "tech-arch-source-layout",
                "match": "glob",
                "pattern": "src/lore/**/*.py",
            },
        ]
    }
    items = json.loads(result.stdout)["impacts"]
    assert "pattern" not in items[0]


def test_json_envelope_code_seed_empty(project_dir, runner):
    """conceptual-workflows-impacts — Empty Result Behaviour: `{"impacts": []}`.

    Scenario 6: no matches → empty envelope, exit 0.
    """
    result = runner.invoke(main, ["impacts", "src/lore/orphan.py", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"impacts": []}


def test_json_error_outside_repo(project_dir, runner):
    """conceptual-workflows-impacts — Failure Modes JSON form: outside repo.

    Scenario 7: stderr parses as `{"error": "..."}`, exit 1.
    """
    result = runner.invoke(main, ["impacts", "/etc/passwd", "--json"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert json.loads(result.stderr) == {
        "error": 'Path is outside the project root: "/etc/passwd"'
    }


def test_json_error_traversal(project_dir, runner):
    """conceptual-workflows-impacts — Failure Modes JSON form: traversal.

    Scenario 8: `..` token → stderr JSON `{"error": "..."}`, exit 1.
    """
    result = runner.invoke(main, ["impacts", "../foo", "--json"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert json.loads(result.stderr) == {
        "error": 'Path traversal not allowed: "../foo"'
    }


# ---------------------------------------------------------------------------
# US-007 — `--direct-links`
# ---------------------------------------------------------------------------


def test_direct_links_drops_glob_rows_default_output(project_dir, runner):
    """conceptual-workflows-impacts — Step 5: rows where `match == "glob"` dropped.

    Scenario 1: glob row gone, no leftover annotation, no whitespace artifact.
    """
    _write_codex_entry(
        project_dir,
        entry_id="dec-006-id-references",
        binds=["src/lore/cli.py"],
    )
    _write_codex_entry(
        project_dir,
        entry_id="tech-arch-source-layout",
        binds=["src/lore/**/*.py"],
    )
    result = runner.invoke(
        main, ["impacts", "src/lore/cli.py", "--direct-links"]
    )
    assert result.exit_code == 0, result.output
    assert result.stdout == "dec-006-id-references\n"
    assert "tech-arch-source-layout" not in result.stdout
    assert "(glob:" not in result.stdout


def test_direct_links_drops_glob_rows_json_output(project_dir, runner):
    """conceptual-workflows-impacts — Step 5: JSON shape unchanged, glob rows dropped.

    Scenario 2: only exact rows remain in the JSON envelope.
    """
    _write_codex_entry(
        project_dir,
        entry_id="dec-006-id-references",
        binds=["src/lore/cli.py"],
    )
    _write_codex_entry(
        project_dir,
        entry_id="tech-arch-source-layout",
        binds=["src/lore/**/*.py"],
    )
    result = runner.invoke(
        main, ["impacts", "src/lore/cli.py", "--direct-links", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "impacts": [{"id": "dec-006-id-references", "match": "exact"}]
    }


def test_direct_links_only_globs_yields_empty(project_dir, runner):
    """conceptual-workflows-impacts — Step 5: result may become empty → FR-14.

    Scenario 3: all globs dropped → nothing on stdout, exit 0.
    """
    _write_codex_entry(
        project_dir,
        entry_id="tech-arch-source-layout",
        binds=["src/lore/**/*.py"],
    )
    result = runner.invoke(
        main, ["impacts", "src/lore/cli.py", "--direct-links"]
    )
    assert result.exit_code == 0, result.output
    assert result.stdout == ""


# US-007 Scenario 4 (`--direct-links` no-op on codex seed) and Scenario 5
# (the same under `--json`) are not asserted as separate red tests here:
# they describe a "do nothing different" contract on the existing codex
# branch, and the kwarg is already accepted (no-op by default). They would
# pass immediately, violating the Red rule "if a test passes immediately
# it is not testing new behavior" (see knight: tdd-red). The Green phase
# is constrained to leave the codex branch untouched, so the existing
# 45 cluster-A/B tests guard against regression there.
#
# The CLI thin-translator contract (US-007 unit AC: "handler forwards
# direct_links unchanged") is exercised implicitly by the three code-seed
# `--direct-links` scenarios above: if the CLI dropped the flag, those
# tests would fail.
