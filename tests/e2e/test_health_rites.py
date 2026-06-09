"""E2E tests for `lore health` rite checks.

Spec: conceptual-workflows-health (lore codex show conceptual-workflows-health)

Covers the rite check classes under the new `rites` scope token: reference
integrity (`dangling_use`, `dangling_then`, `dangling_codex_rite`), graph
well-formedness (`no_entry_node`, `multiple_entry_nodes`, `unreachable_node`,
`conclusion_never_reached`, `undefined_conclusion`), the orphan asymmetry
(`orphan_shared_step` warning vs. orphan main rite producing no issue), schema
validation under `--scope schemas`, multi-scope dispatch (`--scope codex
rites`), the additive JSON envelope, the exit-code contract, the verbatim
unknown-scope message, and soft-delete skipping.

Production behaviour does not exist yet — every test MUST fail (missing scope
token, absent checks, or old `Unknown scope:` wording all count as red).
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from lore.cli import main


# ---------------------------------------------------------------------------
# Fixture authoring helpers
# ---------------------------------------------------------------------------


def _rites_dir(project_dir: Path) -> Path:
    return project_dir / ".lore" / "rites"


def seed_main(project_dir: Path, rite_id: str, body: dict) -> Path:
    """Write a main rite YAML at .lore/rites/main/<id>.yaml."""
    d = _rites_dir(project_dir) / "main"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{rite_id}.yaml"
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    return path


def seed_shared(project_dir: Path, step_id: str, body: dict) -> Path:
    """Write a shared step YAML at .lore/rites/shared/<id>.yaml."""
    d = _rites_dir(project_dir) / "shared"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{step_id}.yaml"
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    return path


def write_codex(project_dir: Path, doc_id: str, *, rites: list[str]) -> Path:
    """Write a codex doc carrying a `rites:` frontmatter array."""
    items = "\n".join(f"  - {r}" for r in rites)
    text = (
        "---\n"
        f"id: {doc_id}\n"
        f"title: {doc_id}\n"
        f"summary: summary for {doc_id}\n"
        f"rites:\n{items}\n"
        "---\n"
        f"body for {doc_id}\n"
    )
    d = project_dir / ".lore" / "codex"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{doc_id}.md"
    path.write_text(text, encoding="utf-8")
    return path


def soft_delete(project_dir: Path, kind: str, rite_id: str) -> None:
    """Rename a rite file to <id>.yaml.deleted (soft-delete)."""
    src = _rites_dir(project_dir) / kind / f"{rite_id}.yaml"
    src.rename(src.with_name(f"{rite_id}.yaml.deleted"))


# ---------------------------------------------------------------------------
# Canonical fixture bodies
# ---------------------------------------------------------------------------

# A shared step is a pure single-exit procedure: id, title, do only.
CANONICAL_SHARED_STEP = {
    "id": "read-contact-info",
    "title": "Read contact info",
    "summary": "Read the customer's contact details.",
    "do": "Read the customer's contact details.",
}

# A main rite with (a) a node use:ing a missing shared step and (b) a then/goto
# to an unknown target. Entry is `get-contact`.
RITE_WITH_DANGLING_USE_AND_THEN = {
    "id": "issue-refund-broken",
    "title": "Issue refund (broken)",
    "summary": "Broken refund rite for reference-integrity checks.",
    "trigger": "Customer requests a refund.",
    "nodes": [
        {"id": "get-contact", "use": "read-contact-info", "then": "review-contact"},
        {"id": "review-contact", "do": "Review contact.", "then": "do-refnud"},
    ],
    "conclusions": {
        "done": {"audience": "agent", "response": "Refund issued."},
    },
}

# A well-formed main rite: single entry `locate-order`, all nodes reachable,
# every conclusion reached.
VALID_RITE = {
    "id": "valid-rite",
    "title": "Valid rite",
    "summary": "A well-formed rite.",
    "trigger": "An order needs locating.",
    "nodes": [
        {"id": "locate-order", "do": "Find the order.", "then": "do-refund"},
        {"id": "do-refund", "do": "Refund it.", "then": "refunded"},
    ],
    "conclusions": {
        "refunded": {"audience": "agent", "response": "Refunded."},
    },
}


# ---------------------------------------------------------------------------
# Scenario 1: Reference integrity errors
# ---------------------------------------------------------------------------


def test_rite_reference_integrity(project_dir, runner):
    """Dangling use:, then/goto, and codex rites: each emit an ERROR row, exit 1."""
    seed_main(project_dir, "issue-refund-broken", RITE_WITH_DANGLING_USE_AND_THEN)
    write_codex(project_dir, "ops-refunds", rites=["issue-refund"])  # issue-refund missing
    r = runner.invoke(main, ["health", "--scope", "rites"])
    assert r.exit_code == 1, r.output
    assert (
        'dangling_use: node "get-contact" uses missing shared step '
        '"read-contact-info"' in r.stdout
    )
    assert (
        'dangling_then: node "review-contact" routes to unknown target '
        '"do-refnud"' in r.stdout
    )
    assert (
        'dangling_codex_rite: codex "ops-refunds" references missing rite '
        '"issue-refund"' in r.stdout
    )


# ---------------------------------------------------------------------------
# Scenario 2: Graph well-formedness errors
# ---------------------------------------------------------------------------


def _seed_each_defect(project_dir: Path) -> None:
    """Seed one main rite per graph defect.

    Each rite isolates a single defect so the asserted detail strings are
    unambiguous.
    """
    # no_entry_node: every node has an inbound edge (a 2-cycle).
    seed_main(project_dir, "rite-no-entry", {
        "id": "rite-no-entry",
        "title": "No entry",
        "summary": "Every node has an inbound edge.",
        "trigger": "t",
        "nodes": [
            {"id": "a", "do": "do a", "then": "b"},
            {"id": "b", "do": "do b", "then": "a"},
        ],
        "conclusions": {"k": {"audience": "agent", "response": "r"}},
    })
    # multiple_entry_nodes: locate-order and do-refund both have no inbound edge,
    # but BOTH route onward through `merge`, so every node stays reachable from an
    # entry — the only defect is the two entry points (no spurious unreachable).
    seed_main(project_dir, "rite-multi-entry", {
        "id": "rite-multi-entry",
        "title": "Multi entry",
        "summary": "Two nodes with no inbound edge.",
        "trigger": "t",
        "nodes": [
            {"id": "locate-order", "do": "find", "then": "merge"},
            {"id": "do-refund", "do": "refund", "then": "merge"},
            {"id": "merge", "do": "merge", "then": "done"},
        ],
        "conclusions": {"done": {"audience": "agent", "response": "r"}},
    })
    # unreachable_node: a single entry `start` reaches `done`; `request-update`
    # self-loops, so it has an inbound edge (not an entry → no multiple_entry)
    # yet is unreachable from `start`.
    seed_main(project_dir, "rite-unreachable", {
        "id": "rite-unreachable",
        "title": "Unreachable",
        "summary": "A node nothing routes to.",
        "trigger": "t",
        "nodes": [
            {"id": "start", "do": "start", "then": "done"},
            {"id": "request-update", "do": "ask", "then": "request-update"},
        ],
        "conclusions": {"done": {"audience": "agent", "response": "r"}},
    })
    # conclusion_never_reached: contact-requested defined but no node routes to it.
    seed_main(project_dir, "rite-conclusion-unreached", {
        "id": "rite-conclusion-unreached",
        "title": "Conclusion unreached",
        "summary": "A conclusion nothing routes to.",
        "trigger": "t",
        "nodes": [
            {"id": "start", "do": "start", "then": "done"},
        ],
        "conclusions": {
            "done": {"audience": "agent", "response": "r"},
            "contact-requested": {"audience": "agent", "response": "r2"},
        },
    })
    # undefined_conclusion: do-refund routes to "refunded" — no node or conclusion.
    seed_main(project_dir, "rite-undefined-conclusion", {
        "id": "rite-undefined-conclusion",
        "title": "Undefined conclusion",
        "summary": "Routes to a conclusion-like target that does not exist.",
        "trigger": "t",
        "nodes": [
            {"id": "do-refund", "do": "refund", "then": "refunded"},
        ],
        "conclusions": {"other": {"audience": "agent", "response": "r"}},
    })


def test_rite_graph_wellformedness(project_dir, runner):
    """Each graph defect produces its exact ERROR detail row and flips exit 1."""
    _seed_each_defect(project_dir)
    r = runner.invoke(main, ["health", "--scope", "rites"])
    assert r.exit_code == 1, r.output
    for line in [
        "no_entry_node: no entry node — every node has an inbound edge",
        "multiple_entry_nodes: multiple entry nodes: locate-order, do-refund",
        'unreachable_node: node "request-update" is unreachable',
        'conclusion_never_reached: conclusion "contact-requested" is defined but never reached',
        'undefined_conclusion: node "do-refund" routes to "refunded" — no node or conclusion',
    ]:
        assert line in r.stdout, f"missing: {line}\n--- got ---\n{r.stdout}"


# ---------------------------------------------------------------------------
# Scenario 3: Orphan asymmetry
# ---------------------------------------------------------------------------


def test_rite_orphan_asymmetry(project_dir, runner):
    """Orphan shared step warns (exit stays 0); orphan main rite emits no issue."""
    seed_shared(project_dir, "read-contact-info", CANONICAL_SHARED_STEP)  # used by nobody
    seed_main(project_dir, "lonely", VALID_RITE)  # no codex rites: points here
    r = runner.invoke(main, ["health", "--scope", "rites"])
    assert "WARNING" in r.stdout and "read-contact-info" in r.stdout
    assert "orphan_shared_step: no main rite uses this shared step" in r.stdout
    assert r.exit_code == 0, r.output  # warning-only keeps exit 0
    assert "lonely" not in r.stdout  # orphan main rite emits NO issue


def test_shared_step_missing_summary_is_schema_error(project_dir, runner):
    """A shared step missing the required `summary` surfaces as a schema error.

    Health audits on-disk state via the existing `_check_schemas` path; the
    shared-step schema now requires `summary` (tech-arch-frontmatter), so a
    file written without it fails validation under `--scope schemas` (and the
    default full audit) — the same path that catches a main rite's missing
    required field. The `rites` scope runs only the rite-graph checks
    (dangling_use / orphan / dup-id), not schema validation.
    """
    seed_shared(
        project_dir,
        "no-summary-step",
        {"id": "no-summary-step", "title": "No summary", "do": "Do the thing."},
    )
    r = runner.invoke(main, ["health", "--scope", "schemas"])
    assert r.exit_code == 1, r.output
    assert "no-summary-step" in r.stdout
    assert "shared-step" in r.stdout
    assert "required" in r.stdout


# ---------------------------------------------------------------------------
# Scenario 4: Schema errors under --scope schemas
# ---------------------------------------------------------------------------


# NOTE: Scenario 4 (schema errors under `--scope schemas`) is intentionally NOT
# tested here. The `main-rite`/`shared-step` schema kinds are already wired into
# `_check_schemas` by US-001 (health.py registers both globs), so a `--scope
# schemas` test against a malformed rite passes against current code — it is not
# red and is not US-006's new behaviour. This story only consumes that path
# (Out of Scope: "schema validation runs via the existing _check_schemas path").


# ---------------------------------------------------------------------------
# Scenario 5: Scope isolation and multi-scope
# ---------------------------------------------------------------------------


def _seed_dangling_codex_rite(project_dir: Path) -> None:
    write_codex(project_dir, "ops-refunds", rites=["issue-refund"])  # rite never seeded


def test_rite_scope_multi_runs_both(project_dir, runner):
    """`--scope codex rites` runs codex AND rite checks; dangling_codex_rite fires."""
    _seed_dangling_codex_rite(project_dir)
    both = runner.invoke(main, ["health", "--scope", "codex", "rites"])
    assert "dangling_codex_rite" in both.stdout, both.output


def test_rite_dangling_codex_rite_fires_under_rites_alone(project_dir, runner):
    """`dangling_codex_rite` also fires under `--scope rites` by itself."""
    _seed_dangling_codex_rite(project_dir)
    only_rites = runner.invoke(main, ["health", "--scope", "rites"])
    assert "dangling_codex_rite" in only_rites.stdout, only_rites.output
    assert only_rites.exit_code == 1, only_rites.output


def test_rite_dangling_codex_rite_fires_under_codex_alone(project_dir, runner):
    """`dangling_codex_rite` is a codex-side check — fires under `--scope codex`."""
    _seed_dangling_codex_rite(project_dir)
    only_codex = runner.invoke(main, ["health", "--scope", "codex"])
    assert "dangling_codex_rite" in only_codex.stdout, only_codex.output


# NOTE: a "`--scope rites` does not run codex `related` checks" isolation test is
# omitted at the E2E layer — until `rites` is a valid token the CLI rejects it
# (exit 2) and the absence-assert passes vacuously, so it is not red. The
# positive multi-scope dispatch (codex + rites both run) is covered above; the
# isolation contract is asserted at the unit layer via health_check scope sets.


# ---------------------------------------------------------------------------
# Scenario 6: JSON output is additive
# ---------------------------------------------------------------------------


def test_rite_health_json(project_dir, runner):
    """`--json health --scope rites` emits HealthIssue objects with null schema fields.

    Coherent scenario: the broken rite's `use:` target (`read-contact-info`) is
    ABSENT → `dangling_use` error. A *separate* shared step (`unused-step`) is
    present but no main rite uses it → `orphan_shared_step` warning. One step
    cannot be both absent (dangling) and present-but-unused (orphan), so the two
    behaviours ride on two distinct steps.
    """
    seed_main(project_dir, "issue-refund-broken", RITE_WITH_DANGLING_USE_AND_THEN)
    # read-contact-info is intentionally NOT seeded -> dangling_use fires.
    seed_shared(
        project_dir,
        "unused-step",
        {"id": "unused-step", "title": "Unused", "summary": "Unused step.", "do": "Nobody uses this."},
    )  # present-but-unused -> orphan_shared_step warning
    res = runner.invoke(main, ["--json", "health", "--scope", "rites"])
    out = json.loads(res.stdout)
    assert out["has_errors"] is True
    assert {
        "severity": "error",
        "entity_type": "rites",
        "id": "issue-refund-broken",
        "check": "dangling_use",
        "detail": 'node "get-contact" uses missing shared step "read-contact-info"',
        "schema_id": None,
        "rule": None,
        "pointer": None,
    } in out["issues"]
    assert {
        "severity": "warning",
        "entity_type": "rites",
        "id": "unused-step",
        "check": "orphan_shared_step",
        "detail": "no main rite uses this shared step",
        "schema_id": None,
        "rule": None,
        "pointer": None,
    } in out["issues"]


def test_rite_json_dangling_codex_rite_row(project_dir, runner):
    """`dangling_codex_rite` JSON row is codex-id'd with entity_type rites."""
    _seed_dangling_codex_rite(project_dir)
    res = runner.invoke(main, ["--json", "health", "--scope", "rites"])
    out = json.loads(res.stdout)
    assert {
        "severity": "error",
        "entity_type": "rites",
        "id": "ops-refunds",
        "check": "dangling_codex_rite",
        "detail": 'codex "ops-refunds" references missing rite "issue-refund"',
        "schema_id": None,
        "rule": None,
        "pointer": None,
    } in out["issues"]


# ---------------------------------------------------------------------------
# Scenario 7: Unknown scope token
# ---------------------------------------------------------------------------


def test_rite_unknown_scope(project_dir, runner):
    """Unknown scope is rejected by Click's Choice validation (usage error, exit 2).

    The shipped contract keeps `type=click.Choice(_VALID_SCOPES)` on `--scope`,
    so an invalid token is a Click usage error (exit 2), and `rites` now appears
    among the listed valid choices.
    """
    r = runner.invoke(main, ["health", "--scope", "xyz"])
    assert r.exit_code == 2, r.output
    assert "'xyz' is not one of" in r.stderr
    assert "'rites'" in r.stderr


def test_rites_scope_accepted_on_empty_project(project_dir, runner):
    """`--scope rites` is a valid token: clean empty project exits 0."""
    r = runner.invoke(main, ["health", "--scope", "rites"])
    assert r.exit_code == 0, r.output
    assert r.stdout == "Health check passed. No issues found.\n"


# ---------------------------------------------------------------------------
# Scenario 8: Deleted rites are skipped
# ---------------------------------------------------------------------------


def test_rite_deleted_main_skipped(project_dir, runner):
    """A soft-deleted main rite is ignored by every rite check."""
    seed_main(project_dir, "broken", RITE_WITH_DANGLING_USE_AND_THEN)
    soft_delete(project_dir, "main", "broken")  # -> broken.yaml.deleted
    r = runner.invoke(main, ["health", "--scope", "rites"])
    assert "broken" not in r.stdout, r.output
    assert r.exit_code == 0, r.output


def test_rite_deleted_shared_skipped(project_dir, runner):
    """A soft-deleted shared step never warns as an orphan."""
    seed_shared(project_dir, "read-contact-info", CANONICAL_SHARED_STEP)
    soft_delete(project_dir, "shared", "read-contact-info")
    r = runner.invoke(main, ["health", "--scope", "rites"])
    assert "orphan_shared_step" not in r.stdout, r.output
    assert r.exit_code == 0, r.output


# ---------------------------------------------------------------------------
# Recursive discovery + duplicate-rite-id collision (codex model)
# ---------------------------------------------------------------------------


def _seed_main_grouped(project_dir: Path, group: str, rite_id: str, body: dict) -> Path:
    d = _rites_dir(project_dir) / "main"
    d = d.joinpath(*group.split("/"))
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{rite_id}.yaml"
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    return path


def test_rite_checks_recurse_into_subfolders(project_dir, runner):
    """A graph defect in a nested subfolder rite is still flagged."""
    _seed_main_grouped(project_dir, "diagnostics/network", "broken", RITE_WITH_DANGLING_USE_AND_THEN)
    r = runner.invoke(main, ["health", "--scope", "rites"])
    assert r.exit_code == 1, r.output
    assert "dangling_use" in r.stdout


def test_duplicate_rite_id_across_subfolders_errors(project_dir, runner):
    """Same id in two files anywhere across the tree → duplicate_rite_id error, exit 1."""
    _seed_main_grouped(project_dir, "aaa", "valid-rite", VALID_RITE)
    _seed_main_grouped(project_dir, "bbb", "valid-rite", VALID_RITE)
    r = runner.invoke(main, ["health", "--scope", "rites"])
    assert r.exit_code == 1, r.output
    assert "duplicate_rite_id" in r.stdout
    assert 'rite id "valid-rite" defined in multiple files' in r.stdout


def test_duplicate_rite_id_main_vs_shared_errors(project_dir, runner):
    """A clash between a main rite id and a shared step id is flagged."""
    seed_main(project_dir, "valid-rite", VALID_RITE)
    seed_shared(project_dir, "valid-rite", {**CANONICAL_SHARED_STEP, "id": "valid-rite"})
    r = runner.invoke(main, ["health", "--scope", "rites"])
    assert r.exit_code == 1, r.output
    assert "duplicate_rite_id" in r.stdout


def test_use_resolves_by_id_across_recursive_shared(project_dir, runner):
    """A use: target in a nested shared subfolder resolves by id — no dangling_use."""
    main_rite = {
        "id": "uses-nested",
        "title": "Uses a nested shared step",
        "summary": "s",
        "trigger": "t",
        "nodes": [
            {"id": "step", "use": "nested-step", "then": "done"},
        ],
        "conclusions": {"done": {"audience": "agent", "response": "r"}},
    }
    seed_main(project_dir, "uses-nested", main_rite)
    d = _rites_dir(project_dir) / "shared" / "io"
    d.mkdir(parents=True, exist_ok=True)
    (d / "nested-step.yaml").write_text(
        yaml.safe_dump({**CANONICAL_SHARED_STEP, "id": "nested-step"}, sort_keys=False),
        encoding="utf-8",
    )
    r = runner.invoke(main, ["health", "--scope", "rites"])
    assert "dangling_use" not in r.stdout, r.output
    assert r.exit_code == 0, r.output


# ---------------------------------------------------------------------------
# Default-all-scopes runs rites
# ---------------------------------------------------------------------------


def test_default_all_scopes_runs_rites(project_dir, runner):
    """`lore health` with no `--scope` runs the rite checks as part of default-all."""
    seed_main(project_dir, "issue-refund-broken", RITE_WITH_DANGLING_USE_AND_THEN)
    res = runner.invoke(main, ["--json", "health"])
    out = json.loads(res.stdout)
    checks = {i["check"] for i in out["issues"]}
    assert "dangling_use" in checks
    assert res.exit_code == 1, res.output
