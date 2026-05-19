"""E2E tests for `lore health --scope bindings` — US-001 + US-002.

Workflow: conceptual-workflows-health (lore codex show conceptual-workflows-health)

US-001 — Scope vocabulary surface: `bindings` is a first-class `--scope` token,
combinable per ADR-012, visible in `--help`, named in invalid-scope error
messages, and routed through the default-all-scopes path.

US-002 — Literal-path `dead_binding` branch of `_check_bindings`: any literal
`binds:` path that doesn't exist on disk surfaces as one `dead_binding` row per
missing literal, with two exact `detail` wordings (`file not found` vs
`resolves outside project root`) and deterministic id-sorted ordering.

Production code does not exist yet — every test MUST fail (import errors /
behaviour mismatches both count as red).
"""

from __future__ import annotations

import json
from pathlib import Path

from lore.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_codex_doc(
    project_dir: Path,
    doc_id: str,
    *,
    binds: list[str] | None = None,
    related: list[str] | None = None,
    body: str = "",
) -> Path:
    """Write a codex doc at .lore/codex/<doc_id>.md with the requested frontmatter.

    Supports both `binds:` (US-002 surface) and `related:` (US-001 Scenario 3
    co-test) so a single helper can author every fixture in this module.
    """
    binds_block = ""
    if binds is not None:
        if binds:
            # Quote each entry so YAML aliases like leading `*` parse as strings.
            items = "\n".join(f'  - "{b}"' for b in binds)
            binds_block = f"binds:\n{items}\n"
        else:
            binds_block = "binds: []\n"

    related_block = ""
    if related is not None:
        if related:
            items = "\n".join(f"  - {r}" for r in related)
            related_block = f"related:\n{items}\n"
        else:
            related_block = "related: []\n"

    fm_body = (
        "---\n"
        f"id: {doc_id}\n"
        f"title: {doc_id}\n"
        f"summary: summary for {doc_id}\n"
        f"{binds_block}{related_block}"
        "---\n"
        f"{body}\n"
    )
    codex_dir = project_dir / ".lore" / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    path = codex_dir / f"{doc_id}.md"
    path.write_text(fm_body, encoding="utf-8")
    return path


# ===========================================================================
# US-001 — Scope vocabulary surface
# ===========================================================================


# ---------------------------------------------------------------------------
# Scenario 1: `--scope bindings` is accepted on an empty project
# ---------------------------------------------------------------------------


def test_scope_bindings_accepted_empty_project(project_dir, runner):
    """US-001 Scenario 1 — empty project: `--scope bindings` exits 0 with success line."""
    res = runner.invoke(main, ["health", "--scope", "bindings"])
    assert res.exit_code == 0, res.output
    assert res.stdout == "Health check passed. No issues found.\n"
    assert (res.stderr or "") == ""


# ---------------------------------------------------------------------------
# Scenario 2: `--help` lists `bindings` as a valid scope token
# ---------------------------------------------------------------------------


def test_help_lists_bindings_scope(project_dir, runner):
    """US-001 Scenario 2 — `--help` advertises `bindings` last in the choice list."""
    res = runner.invoke(main, ["health", "--help"])
    assert res.exit_code == 0, res.output
    # Click renders Choice as [a|b|c]; assert the full eight-token block appears.
    assert (
        "[codex|artifacts|doctrines|knights|watchers|schemas|glossary|bindings]"
        in res.stdout
    )


# ---------------------------------------------------------------------------
# Scenario 3: Multi-value scope per ADR-012
# ---------------------------------------------------------------------------


def test_scope_bindings_plus_codex_runs_both(project_dir, runner):
    """US-001 Scenario 3 — `--scope bindings codex` runs both checkers in one invocation."""
    _seed_codex_doc(project_dir, "entry-a", binds=["src/missing.py"])
    _seed_codex_doc(project_dir, "entry-b", related=["nonexistent"])
    res = runner.invoke(
        main, ["--json", "health", "--scope", "bindings", "codex"]
    )
    assert res.exit_code == 1, res.output
    payload = json.loads(res.stdout)
    checks = {i["check"] for i in payload["issues"]}
    assert "dead_binding" in checks
    assert "broken_related_link" in checks


# ---------------------------------------------------------------------------
# Scenario 4: Invalid scope token error mentions `bindings`
# ---------------------------------------------------------------------------


def test_invalid_scope_message_lists_bindings(project_dir, runner):
    """US-001 Scenario 4 — typo on `--scope` surfaces click usage-error naming `bindings`."""
    res = runner.invoke(main, ["health", "--scope", "bindigns"])
    assert res.exit_code == 2, res.output  # click usage-error path
    err = res.stderr or res.output
    assert "bindings" in err


# ---------------------------------------------------------------------------
# Scenario 5: Default-all-scopes runs the bindings checker
# ---------------------------------------------------------------------------


def test_default_all_scopes_runs_bindings(project_dir, runner):
    """US-001 Scenario 5 — `lore health --json` (no `--scope`) routes through bindings."""
    _seed_codex_doc(project_dir, "entry-a", binds=["src/missing.py"])
    res = runner.invoke(main, ["--json", "health"])
    assert res.exit_code == 1, res.output
    payload = json.loads(res.stdout)
    bindings_rows = [i for i in payload["issues"] if i["check"] == "dead_binding"]
    assert len(bindings_rows) == 1
    assert bindings_rows[0]["id"] == "entry-a"
    assert bindings_rows[0]["entity_type"] == "codex"


# ===========================================================================
# US-002 — Literal-path `dead_binding` branch
# ===========================================================================


# ---------------------------------------------------------------------------
# Scenario 1: Single dead literal emits exactly one dead_binding row
# ---------------------------------------------------------------------------


def test_dead_literal_binding_one_row(project_dir, runner):
    """US-002 Scenario 1 — one missing literal → one dead_binding row with exact fields."""
    _seed_codex_doc(
        project_dir,
        "tech-arch-source-layout",
        binds=["src/lore/cli.py"],
    )
    # Sanity: ensure src/lore/cli.py absent under the project root.
    assert not (project_dir / "src" / "lore" / "cli.py").exists()
    res = runner.invoke(main, ["--json", "health", "--scope", "bindings"])
    assert res.exit_code == 1, res.output
    payload = json.loads(res.stdout)
    assert payload["issues"] == [{
        "severity": "error",
        "entity_type": "codex",
        "id": "tech-arch-source-layout",
        "check": "dead_binding",
        "detail": '"src/lore/cli.py" — file not found',
        "schema_id": None,
        "rule": None,
        "pointer": None,
    }]


# ---------------------------------------------------------------------------
# Scenario 2: Literal that exists on disk is silent
# ---------------------------------------------------------------------------


def test_existing_literal_silent(project_dir, runner):
    """US-002 Scenario 2 — literal pointing at a real file emits zero rows."""
    (project_dir / "src" / "lore").mkdir(parents=True)
    (project_dir / "src" / "lore" / "cli.py").write_text("# real file\n")
    _seed_codex_doc(
        project_dir, "tech-arch-source-layout", binds=["src/lore/cli.py"]
    )
    res = runner.invoke(main, ["--json", "health", "--scope", "bindings"])
    assert res.exit_code == 0, res.output
    assert json.loads(res.stdout)["issues"] == []


# ---------------------------------------------------------------------------
# Scenario 3: Each dead literal in the same entry's binds list produces a row
# ---------------------------------------------------------------------------


def test_two_dead_literals_same_entry_two_rows(project_dir, runner):
    """US-002 Scenario 3 — two missing literals on one entry → two rows in declaration order."""
    _seed_codex_doc(
        project_dir,
        "entry-a",
        binds=["src/missing-one.py", "src/missing-two.py"],
    )
    res = runner.invoke(main, ["--json", "health", "--scope", "bindings"])
    assert res.exit_code == 1, res.output
    issues = json.loads(res.stdout)["issues"]
    assert len(issues) == 2
    assert all(
        i["id"] == "entry-a" and i["check"] == "dead_binding" for i in issues
    )
    assert issues[0]["detail"] == '"src/missing-one.py" — file not found'
    assert issues[1]["detail"] == '"src/missing-two.py" — file not found'


# ---------------------------------------------------------------------------
# Scenario 4: Literal whose symlink escapes the project root is dead_binding
# ---------------------------------------------------------------------------


def test_symlink_escaping_project_root_is_dead_binding(
    project_dir, tmp_path, runner
):
    """US-002 Scenario 4 — symlink target outside project_root → "resolves outside project root"."""
    # `project_dir` lives under `tmp_path`; create the escape target as a sibling
    # to guarantee it is outside the project root after Path.resolve().
    outside = tmp_path.parent / "escape-target"
    outside.write_text("escape\n")
    try:
        (project_dir / "src").mkdir()
        (project_dir / "src" / "escape.py").symlink_to(outside)
        _seed_codex_doc(
            project_dir,
            "decisions-006-id-references",
            binds=["src/escape.py"],
        )
        res = runner.invoke(main, ["--json", "health", "--scope", "bindings"])
        assert res.exit_code == 1, res.output
        issues = json.loads(res.stdout)["issues"]
        assert issues == [{
            "severity": "error",
            "entity_type": "codex",
            "id": "decisions-006-id-references",
            "check": "dead_binding",
            "detail": '"src/escape.py" — resolves outside project root',
            "schema_id": None,
            "rule": None,
            "pointer": None,
        }]
    finally:
        if outside.exists():
            outside.unlink()


# ---------------------------------------------------------------------------
# Scenario 5: Plain-text CLI rendering of dead_binding
# ---------------------------------------------------------------------------


def test_plaintext_render_dead_binding(project_dir, runner):
    """US-002 Scenario 5 — non-JSON path renders the canonical ERROR line."""
    _seed_codex_doc(
        project_dir,
        "tech-arch-source-layout",
        binds=["src/lore/cli.py"],
    )
    res = runner.invoke(main, ["health", "--scope", "bindings"])
    assert res.exit_code == 1, res.output
    assert (
        'ERROR  codex  tech-arch-source-layout  dead_binding: '
        '"src/lore/cli.py" — file not found'
    ) in res.stdout


# ---------------------------------------------------------------------------
# Scenario 6: Deterministic ordering across runs (sorted by codex id ascending)
# ---------------------------------------------------------------------------


def test_dead_binding_rows_sorted_by_codex_id(project_dir, runner):
    """US-002 Scenario 6 — repeated runs are byte-identical, rows sorted by codex id."""
    _seed_codex_doc(project_dir, "z-entry", binds=["src/missing-z.py"])
    _seed_codex_doc(project_dir, "a-entry", binds=["src/missing-a.py"])
    r1 = runner.invoke(main, ["--json", "health", "--scope", "bindings"])
    r2 = runner.invoke(main, ["--json", "health", "--scope", "bindings"])
    assert r1.exit_code == 1, r1.output
    assert r1.stdout == r2.stdout
    ids_in_order = [i["id"] for i in json.loads(r1.stdout)["issues"]]
    assert ids_in_order == ["a-entry", "z-entry"]


# ===========================================================================
# US-003 — `empty_glob_binding` warning + lazy single-walk + skip-list
# Workflow: conceptual-workflows-health (lore codex show conceptual-workflows-health)
# Workflow: conceptual-workflows-impacts (lore codex show conceptual-workflows-impacts)
# ===========================================================================


# ---------------------------------------------------------------------------
# Scenario 1: Empty glob emits one warning, exit 0
# ---------------------------------------------------------------------------


def test_empty_glob_binding_warns_exit_zero(project_dir, runner):
    """US-003 Scenario 1 — forward-looking glob → one empty_glob_binding warning, exit 0."""
    _seed_codex_doc(
        project_dir,
        "conceptual-workflows-impacts",
        binds=["src/lore/impacts/**/*.py"],
    )
    # src/lore/impacts/ does NOT exist anywhere on disk under project_dir.
    assert not (project_dir / "src" / "lore" / "impacts").exists()
    res = runner.invoke(main, ["--json", "health", "--scope", "bindings"])
    assert res.exit_code == 0, res.output
    issues = json.loads(res.stdout)["issues"]
    assert issues == [{
        "severity": "warning",
        "entity_type": "codex",
        "id": "conceptual-workflows-impacts",
        "check": "empty_glob_binding",
        "detail": '"src/lore/impacts/**/*.py" — pattern matches zero files',
        "schema_id": None,
        "rule": None,
        "pointer": None,
    }]


# ---------------------------------------------------------------------------
# Scenario 2: Glob with one match is silent
# ---------------------------------------------------------------------------


def test_glob_one_match_silent(project_dir, runner):
    """US-003 Scenario 2 — `?` wildcard glob matching one file → zero rows for THAT entry.

    A second entry carries an empty glob so the test fails red until the glob
    branch is wired: without it, the matching glob is vacuously silent AND the
    empty glob is vacuously silent (no warning emitted), which is wrong.
    """
    (project_dir / "src" / "lore").mkdir(parents=True)
    (project_dir / "src" / "lore" / "cli.py").write_text("# real\n")
    _seed_codex_doc(project_dir, "entry-a", binds=["src/lore/cl?.py"])
    _seed_codex_doc(project_dir, "entry-b", binds=["src/missing/**/*.py"])
    res = runner.invoke(main, ["--json", "health", "--scope", "bindings"])
    assert res.exit_code == 0, res.output
    issues = json.loads(res.stdout)["issues"]
    # entry-a's glob matched → no row for entry-a.
    assert not any(i["id"] == "entry-a" for i in issues)
    # entry-b's glob did NOT match → exactly one warning row for entry-b.
    entry_b_rows = [i for i in issues if i["id"] == "entry-b"]
    assert len(entry_b_rows) == 1
    assert entry_b_rows[0]["check"] == "empty_glob_binding"


# ---------------------------------------------------------------------------
# Scenario 3: Glob with many matches is silent
# ---------------------------------------------------------------------------


def test_glob_many_matches_silent(project_dir, runner):
    """US-003 Scenario 3 — `**` glob matching 3 files → zero rows for THAT entry.

    Paired with a sibling empty-glob entry so a no-op glob branch still fails.
    """
    (project_dir / "src" / "lore").mkdir(parents=True)
    for name in ("a.py", "b.py", "c.py"):
        (project_dir / "src" / "lore" / name).write_text("")
    _seed_codex_doc(project_dir, "entry-a", binds=["src/lore/**/*.py"])
    _seed_codex_doc(project_dir, "entry-b", binds=["src/missing/**/*.py"])
    res = runner.invoke(main, ["--json", "health", "--scope", "bindings"])
    assert res.exit_code == 0, res.output
    issues = json.loads(res.stdout)["issues"]
    assert not any(i["id"] == "entry-a" for i in issues)
    entry_b_rows = [i for i in issues if i["id"] == "entry-b"]
    assert len(entry_b_rows) == 1
    assert entry_b_rows[0]["check"] == "empty_glob_binding"


# ---------------------------------------------------------------------------
# Scenario 4: Mixed literal + glob in one entry, only the glob is empty
# ---------------------------------------------------------------------------


def test_mixed_binds_only_glob_empty(project_dir, runner):
    """US-003 Scenario 4 — two existing literals + one empty glob → one warning only."""
    (project_dir / "src" / "lore").mkdir(parents=True)
    (project_dir / "src" / "lore" / "cli.py").write_text("")
    (project_dir / "src" / "lore" / "health.py").write_text("")
    _seed_codex_doc(
        project_dir,
        "entry-x",
        binds=[
            "src/lore/cli.py",
            "src/missing/**/*.py",
            "src/lore/health.py",
        ],
    )
    res = runner.invoke(main, ["--json", "health", "--scope", "bindings"])
    assert res.exit_code == 0, res.output
    issues = json.loads(res.stdout)["issues"]
    assert issues == [{
        "severity": "warning",
        "entity_type": "codex",
        "id": "entry-x",
        "check": "empty_glob_binding",
        "detail": '"src/missing/**/*.py" — pattern matches zero files',
        "schema_id": None,
        "rule": None,
        "pointer": None,
    }]


# ---------------------------------------------------------------------------
# Scenario 5: Plain-text CLI rendering of empty_glob_binding
# ---------------------------------------------------------------------------


def test_plaintext_render_empty_glob(project_dir, runner):
    """US-003 Scenario 5 — non-JSON path renders the canonical WARNING line for empty_glob_binding."""
    _seed_codex_doc(
        project_dir,
        "conceptual-workflows-impacts",
        binds=["src/lore/impacts/**/*.py"],
    )
    res = runner.invoke(main, ["health", "--scope", "bindings"])
    assert res.exit_code == 0, res.output
    assert (
        'WARNING  codex  conceptual-workflows-impacts  empty_glob_binding: '
        '"src/lore/impacts/**/*.py" — pattern matches zero files'
    ) in res.stdout


# ---------------------------------------------------------------------------
# Scenario 6: Skip-list excludes `.lore`, `.git`, `node_modules`, `__pycache__`
# ---------------------------------------------------------------------------


def test_glob_skip_list_excludes_dotlore_and_friends(project_dir, runner):
    """US-003 Scenario 6 — Markdown only inside .lore/ → glob still reports empty."""
    # The `project_dir` fixture runs `lore init`, which seeds .lore/codex/*.md
    # files. Those .md files MUST NOT count toward `**/*.md` matches.
    _seed_codex_doc(project_dir, "entry-a", binds=["**/*.md"])
    res = runner.invoke(main, ["--json", "health", "--scope", "bindings"])
    assert res.exit_code == 0, res.output
    issues = json.loads(res.stdout)["issues"]
    assert len(issues) == 1
    assert issues[0]["check"] == "empty_glob_binding"
    assert issues[0]["detail"] == '"**/*.md" — pattern matches zero files'


# ---------------------------------------------------------------------------
# Scenario 7: Codex entry with no binds key (or `binds: []`) is silent
# ---------------------------------------------------------------------------


def test_no_binds_and_empty_binds_silent_glob_scope(project_dir, runner):
    """US-003 Scenario 7 — entries without globs are silent, but a sibling empty glob warns.

    Combines no-binds + empty-binds + a third entry with an empty glob; only
    the third should produce one warning. A no-op glob branch fails this red.
    """
    _seed_codex_doc(project_dir, "no-binds-entry")  # binds key omitted
    _seed_codex_doc(project_dir, "empty-binds-entry", binds=[])
    _seed_codex_doc(project_dir, "glob-entry", binds=["nowhere/**/*.py"])
    res = runner.invoke(main, ["--json", "health", "--scope", "bindings"])
    assert res.exit_code == 0, res.output
    issues = json.loads(res.stdout)["issues"]
    # only the glob-entry should produce a warning row.
    assert [i["id"] for i in issues] == ["glob-entry"]
    assert issues[0]["check"] == "empty_glob_binding"


# ===========================================================================
# US-004 — Reporting / exit-code / scan_failed envelope contract
# Workflow: conceptual-workflows-health (lore codex show conceptual-workflows-health)
# ===========================================================================


# ---------------------------------------------------------------------------
# Scenario 1: dead_binding row shape — schema_id/rule/pointer all null
# ---------------------------------------------------------------------------


def test_us004_dead_binding_envelope_null_schema_fields(project_dir, runner):
    """US-004 Scenario 1 — dead_binding row has schema_id/rule/pointer all None."""
    _seed_codex_doc(project_dir, "entry-a", binds=["src/missing.py"])
    res = runner.invoke(main, ["--json", "health", "--scope", "bindings"])
    assert res.exit_code == 1, res.output
    report = json.loads(res.stdout)
    assert report["issues"] == [{
        "severity": "error",
        "entity_type": "codex",
        "id": "entry-a",
        "check": "dead_binding",
        "detail": '"src/missing.py" — file not found',
        "schema_id": None,
        "rule": None,
        "pointer": None,
    }]
    assert report["has_errors"] is True


# ---------------------------------------------------------------------------
# Scenario 2: empty_glob_binding row shape — schema_id/rule/pointer all null
# ---------------------------------------------------------------------------


def test_us004_empty_glob_envelope_warning_no_errors(project_dir, runner):
    """US-004 Scenario 2 — empty_glob_binding row is a warning; has_errors False; exit 0."""
    _seed_codex_doc(project_dir, "entry-b", binds=["src/missing/**/*.py"])
    res = runner.invoke(main, ["--json", "health", "--scope", "bindings"])
    assert res.exit_code == 0, res.output
    report = json.loads(res.stdout)
    assert report["issues"] == [{
        "severity": "warning",
        "entity_type": "codex",
        "id": "entry-b",
        "check": "empty_glob_binding",
        "detail": '"src/missing/**/*.py" — pattern matches zero files',
        "schema_id": None,
        "rule": None,
        "pointer": None,
    }]
    assert report["has_errors"] is False


# ---------------------------------------------------------------------------
# Scenario 3: Mixed run — exit 1 driven by has_errors partition
# ---------------------------------------------------------------------------


def test_us004_mixed_bindings_exit_one_from_has_errors(project_dir, runner):
    """US-004 Scenario 3 — one dead literal + one empty glob → exit 1, has_errors True."""
    _seed_codex_doc(project_dir, "dead-one", binds=["src/missing.py"])
    _seed_codex_doc(project_dir, "empty-one", binds=["src/no-such/**/*.py"])
    res = runner.invoke(main, ["--json", "health", "--scope", "bindings"])
    assert res.exit_code == 1, res.output
    report = json.loads(res.stdout)
    checks = {i["check"] for i in report["issues"]}
    assert checks == {"dead_binding", "empty_glob_binding"}
    assert report["has_errors"] is True


# ---------------------------------------------------------------------------
# Scenario 4: Bindings checker crash emits one scan_failed row;
#             other scopes continue (FR-16)
# ---------------------------------------------------------------------------


def test_us004_check_bindings_crash_isolates_scope(project_dir, runner, monkeypatch):
    """US-004 Scenario 4 — _check_bindings raise → one scan_failed row; codex scope still runs."""
    import lore.health

    _seed_codex_doc(
        project_dir, "entry-broken-related", related=["nonexistent"]
    )

    def _boom(_p):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(lore.health, "_check_bindings", _boom)

    res = runner.invoke(
        main, ["--json", "health", "--scope", "bindings", "codex"]
    )
    assert res.exit_code == 1, res.output
    issues = json.loads(res.stdout)["issues"]

    scan_failed_rows = [i for i in issues if i["check"] == "scan_failed"]
    assert len(scan_failed_rows) == 1
    row = scan_failed_rows[0]
    assert row["severity"] == "error"
    assert row["entity_type"] == "bindings"
    assert row["id"] == "bindings"
    assert "simulated failure" in row["detail"]
    assert row["schema_id"] is None
    assert row["rule"] is None
    assert row["pointer"] is None

    # _check_codex was NOT aborted by the bindings crash.
    related_rows = [i for i in issues if i["check"] == "broken_related_link"]
    assert len(related_rows) == 1
    assert related_rows[0]["id"] == "entry-broken-related"


# ---------------------------------------------------------------------------
# Scenario 5: Plaintext renderer keeps bindings rows in the same issues table
# ---------------------------------------------------------------------------


def test_us004_markdown_report_no_new_bindings_section(project_dir, runner):
    """US-004 Scenario 5 — bindings rows render in the standard flat issues list."""
    _seed_codex_doc(project_dir, "dead-one", binds=["src/missing.py"])
    _seed_codex_doc(project_dir, "empty-one", binds=["src/no-such/**/*.py"])
    res = runner.invoke(main, ["health", "--scope", "bindings"])
    # Both rows present in stdout.
    assert 'dead_binding: "src/missing.py" — file not found' in res.stdout
    assert (
        'empty_glob_binding: "src/no-such/**/*.py" — pattern matches zero files'
        in res.stdout
    )
    # No "Bindings" subheading distinct from other checks.
    assert "## Bindings" not in res.stdout
    assert "### Bindings" not in res.stdout


# ---------------------------------------------------------------------------
# Scenario 6: Empty-glob-only run exits 0 even on --scope bindings alone
# ---------------------------------------------------------------------------


def test_us004_empty_glob_only_run_exits_zero(project_dir, runner):
    """US-004 Scenario 6 — empty-glob-only project on --scope bindings exits 0."""
    _seed_codex_doc(project_dir, "entry-a", binds=["src/no-such/**/*.py"])
    res = runner.invoke(main, ["health", "--scope", "bindings"])
    assert res.exit_code == 0, res.output


# ===========================================================================
# US-005 — Python API parity over lore.models.health_check
# Workflow: conceptual-workflows-health (lore codex show conceptual-workflows-health)
# ADR-011 — decisions-011-api-parity-with-cli
# ===========================================================================


# ---------------------------------------------------------------------------
# Scenario 1: CLI --json issues == health_check(...) issues (element-for-element)
# ---------------------------------------------------------------------------


def test_us005_cli_python_api_parity_for_bindings(project_dir, runner):
    """US-005 Scenario 1 — CLI JSON `issues` == health_check report rows, row-for-row.

    Seeds: one dead literal, one empty glob, one existing literal (silent).
    Asserts the CLI `issues` array and `[dataclasses.asdict(i) for i in report.issues]`
    are equal element-for-element; ids are sorted ascending (entry-a, entry-b).
    """
    import dataclasses

    from lore.models import health_check

    _seed_codex_doc(project_dir, "entry-a", binds=["src/missing.py"])
    _seed_codex_doc(project_dir, "entry-b", binds=["src/empty/**/*.py"])
    (project_dir / "src" / "lore").mkdir(parents=True, exist_ok=True)
    (project_dir / "src" / "lore" / "cli.py").write_text("")
    _seed_codex_doc(project_dir, "entry-c", binds=["src/lore/cli.py"])

    cli_res = runner.invoke(main, ["--json", "health", "--scope", "bindings"])
    cli_issues = json.loads(cli_res.stdout)["issues"]

    report = health_check(project_dir, scope=["bindings"])
    py_issues = [dataclasses.asdict(i) for i in report.issues]

    assert cli_issues == py_issues
    # id-sorted: entry-a before entry-b; entry-c silent (no row).
    assert [i["id"] for i in cli_issues] == ["entry-a", "entry-b"]


# ---------------------------------------------------------------------------
# Scenario 3: health_check returns HealthReport with HealthIssue elements
# ---------------------------------------------------------------------------


def test_us005_health_check_returns_healthreport_with_healthissues(project_dir):
    """US-005 Scenario 3 — public API returns HealthReport[HealthIssue]."""
    from lore.models import HealthIssue, HealthReport, health_check

    _seed_codex_doc(project_dir, "entry-a", binds=["src/missing.py"])
    report = health_check(project_dir, scope=["bindings"])
    assert isinstance(report, HealthReport)
    assert report.has_errors is True
    assert all(isinstance(i, HealthIssue) for i in report.issues)
    assert report.issues[0].check == "dead_binding"


# ---------------------------------------------------------------------------
# Scenario 4: Multi-scope Python call invokes both checkers exactly once
# ---------------------------------------------------------------------------


def test_us005_health_check_python_multi_scope(project_dir):
    """US-005 Scenario 4 — `scope=["bindings", "codex"]` invokes both, no duplicates."""
    from lore.models import health_check

    _seed_codex_doc(project_dir, "entry-a", binds=["src/missing.py"])
    _seed_codex_doc(project_dir, "entry-b", related=["nonexistent"])
    report = health_check(project_dir, scope=["bindings", "codex"])
    checks = [i.check for i in report.issues]
    assert "dead_binding" in checks
    assert "broken_related_link" in checks
    assert checks.count("dead_binding") == 1
    assert checks.count("broken_related_link") == 1
    assert report.has_errors is True


# ---------------------------------------------------------------------------
# Scenario 5: Default scope (omitted) includes bindings
# ---------------------------------------------------------------------------


def test_us005_health_check_default_scope_includes_bindings(project_dir):
    """US-005 Scenario 5 — `health_check(project_root)` (no scope) routes through bindings."""
    from lore.models import health_check

    _seed_codex_doc(project_dir, "entry-a", binds=["src/missing.py"])
    report = health_check(project_dir)
    assert any(i.check == "dead_binding" for i in report.issues)
    assert report.has_errors is True
