"""E2E tests for lore codex chaos command — random-walk traversal scenarios.

Workflow: conceptual-workflows-codex-chaos
"""

import textwrap

from lore.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_codex_doc(project_dir, doc_id, *, related=None, omit_related=False):
    """Write a codex document into .lore/codex/ and return its path."""
    related_line = ""
    if not omit_related:
        if related is None:
            related_line = "related: []"
        else:
            items = "\n".join(f"  - {r}" for r in related)
            related_line = f"related:\n{items}"
    content = textwrap.dedent(f"""\
        ---
        id: {doc_id}
        title: {doc_id.replace("-", " ").title()}
        summary: Summary for {doc_id}.
        {related_line}
        ---

        Body of {doc_id}.
    """)
    codex_dir = project_dir / ".lore" / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    path = codex_dir / f"{doc_id}.md"
    path.write_text(content)
    return path


def _parse_table_ids(output: str) -> list[str]:
    """Parse doc IDs from the chaos table output.

    Skips the header line (which starts with whitespace + 'ID') and
    returns the first column of each subsequent row.
    """
    ids = []
    lines = output.strip().splitlines()
    header_seen = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if not header_seen:
            # Header row contains 'ID' as first token
            if stripped.startswith("ID"):
                header_seen = True
            continue
        # Data row: first whitespace-separated token is the doc ID
        ids.append(stripped.split()[0])
    return ids


# ---------------------------------------------------------------------------
# US-001: Core Traversal — Happy Path
# ---------------------------------------------------------------------------


# E2E — Scenario 1: discovery walk returns seed first and non-empty result
# conceptual-workflows-codex-chaos steps 1–4 (validate seed, build adjacency, BFS reachable, random walk)
def test_chaos_discovery_happy_path(runner, project_dir):
    # Given: project_dir with ≥10 connected codex docs anchored at "seed-doc"
    _write_codex_doc(project_dir, "seed-doc", related=["n1", "n2", "n3", "n4", "n5"])
    _write_codex_doc(project_dir, "n1", related=["n6"])
    _write_codex_doc(project_dir, "n2", related=["n7"])
    _write_codex_doc(project_dir, "n3", related=["n8"])
    _write_codex_doc(project_dir, "n4", related=["n9"])
    _write_codex_doc(project_dir, "n5", related=["n10"])
    _write_codex_doc(project_dir, "n6")
    _write_codex_doc(project_dir, "n7")
    _write_codex_doc(project_dir, "n8")
    _write_codex_doc(project_dir, "n9")
    _write_codex_doc(project_dir, "n10")

    result = runner.invoke(main, ["codex", "chaos", "seed-doc", "--threshold", "40"])

    assert result.exit_code == 0
    output = result.output
    # Header row must contain ID, TYPE, TITLE, SUMMARY
    assert "ID" in output
    assert "TYPE" in output
    assert "TITLE" in output
    assert "SUMMARY" in output
    ids = _parse_table_ids(output)
    # Seed is first
    assert ids[0] == "seed-doc"
    # At least one other document beyond seed
    assert len(ids) > 1
    # No duplicates
    assert len(ids) == len(set(ids))
    # All IDs exist in codex
    all_ids = {
        "seed-doc", "n1", "n2", "n3", "n4", "n5",
        "n6", "n7", "n8", "n9", "n10",
    }
    for doc_id in ids:
        assert doc_id in all_ids


# E2E — Scenario 2: leaf node (no related links) returns only the seed
# conceptual-workflows-codex-chaos step 3 (reachable set = {seed}, walk terminates immediately)
def test_chaos_leaf_seed_returns_only_seed(runner, project_dir):
    # Given: project_dir with "leaf-doc" that has no related field
    _write_codex_doc(project_dir, "leaf-doc", omit_related=True)

    result = runner.invoke(main, ["codex", "chaos", "leaf-doc", "--threshold", "40"])

    assert result.exit_code == 0
    ids = _parse_table_ids(result.output)
    assert ids == ["leaf-doc"]
    # stderr is empty
    assert not result.stderr if hasattr(result, "stderr") else True


# E2E — Scenario 3: threshold=100 exhausts full reachable subgraph
# conceptual-workflows-codex-chaos step 4 (walk terminates when no unvisited reachable neighbours remain)
def test_chaos_threshold_100_exhausts_reachable_subgraph(runner, project_dir):
    # Given: project_dir with connected component of exactly 6 docs rooted at "root-doc"
    _write_codex_doc(project_dir, "root-doc", related=["r1", "r2"])
    _write_codex_doc(project_dir, "r1", related=["r3", "r4"])
    _write_codex_doc(project_dir, "r2", related=["r5"])
    _write_codex_doc(project_dir, "r3")
    _write_codex_doc(project_dir, "r4")
    _write_codex_doc(project_dir, "r5")

    result = runner.invoke(main, ["codex", "chaos", "root-doc", "--threshold", "100"])

    assert result.exit_code == 0
    ids = _parse_table_ids(result.output)
    assert len(ids) == 6
    assert set(ids) == {"root-doc", "r1", "r2", "r3", "r4", "r5"}
    assert ids[0] == "root-doc"
    assert len(ids) == len(set(ids))


# E2E — Scenario 4: threshold=30 terminates early on large graph
# conceptual-workflows-codex-chaos step 4 (threshold stopping criterion: discovered/reachable >= 0.30)
def test_chaos_threshold_30_terminates_early(runner, project_dir):
    # Given: project_dir with 20 docs all connected from "big-seed"
    neighbours = [f"b{i}" for i in range(1, 20)]
    _write_codex_doc(project_dir, "big-seed", related=neighbours)
    for n in neighbours:
        _write_codex_doc(project_dir, n)

    result = runner.invoke(main, ["codex", "chaos", "big-seed", "--threshold", "30"])

    assert result.exit_code == 0
    ids = _parse_table_ids(result.output)
    assert ids[0] == "big-seed"
    # Walk terminates before exhausting all 20 docs
    assert len(ids) < 20
    # No duplicates
    assert len(ids) == len(set(ids))


# E2E — Scenario 5: non-determinism — distinct results across repeated invocations
# conceptual-workflows-codex-chaos step 4 (random walk picks unvisited neighbour at random each step)
def test_chaos_non_determinism_across_invocations(runner, project_dir):
    # Given: project_dir with ≥10 docs connected from "varied-seed"
    neighbours = [f"v{i}" for i in range(1, 11)]
    _write_codex_doc(project_dir, "varied-seed", related=neighbours)
    for n in neighbours:
        _write_codex_doc(project_dir, n)

    results = []
    for _ in range(10):
        r = runner.invoke(main, ["codex", "chaos", "varied-seed", "--threshold", "40"])
        assert r.exit_code == 0
        ids = frozenset(_parse_table_ids(r.output))
        results.append(ids)

    # At least two of the ten invocations must differ
    assert len(set(results)) > 1


# E2E — Scenario 6: chaos subcommand discoverable via lore codex --help
# conceptual-workflows-codex-chaos (command is registered under the codex CLI group per FR-12)
def test_chaos_command_discoverable_via_help(runner, project_dir):
    result = runner.invoke(main, ["codex", "--help"])

    assert result.exit_code == 0
    assert "chaos" in result.output


# ---------------------------------------------------------------------------
# US-002: Error Handling — Unknown Seed ID
# ---------------------------------------------------------------------------


# E2E — Scenario 1: unknown seed ID in plain-text mode
# conceptual-workflows-codex-chaos Failure Modes table (Seed document not found → stderr, exit 1)
def test_chaos_unknown_id_plain_text(runner, project_dir):
    # Given: project_dir with a valid codex that has no document "nonexistent-id"
    import subprocess
    import sys

    _write_codex_doc(project_dir, "existing-doc", related=[])

    proc = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "nonexistent-id", "--threshold", "50"],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )

    assert proc.returncode == 1
    assert 'Document "nonexistent-id" not found' in proc.stderr
    assert proc.stdout == ""

    # Full error contract: --json flag must also be accepted (exit 1, not Click option error exit 2)
    # This assertion fails until --json is registered on codex_chaos
    proc_json_check = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "nonexistent-id", "--threshold", "50", "--json"],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )
    assert proc_json_check.returncode != 2, (
        f"--json flag not yet accepted by codex_chaos (got Click option error exit 2); "
        f"stderr={proc_json_check.stderr!r}"
    )


# E2E — Scenario 2: unknown seed ID in JSON mode — error goes to stderr as JSON envelope
# conceptual-workflows-codex-chaos Failure Modes table (Seed not found, JSON mode → {"error": ...} to stderr, exit 1)
def test_chaos_unknown_id_json_mode(runner, project_dir):
    # Given: project_dir with a valid codex that has no document "bad-id"
    # --json placed at end of command per memory/feedback_json_flag_placement.md convention
    import json
    import subprocess
    import sys

    _write_codex_doc(project_dir, "existing-doc", related=[])

    proc = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "bad-id", "--threshold", "50", "--json"],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )

    # --json is not yet registered on codex_chaos; exit code will be 2 until implemented
    assert proc.returncode == 1, (
        f"Expected exit 1 with JSON error envelope; got {proc.returncode}. "
        f"(--json flag not yet implemented on codex_chaos)"
    )
    assert proc.stdout == ""
    error_envelope = json.loads(proc.stderr)
    assert error_envelope == {"error": 'Document "bad-id" not found'}


# E2E — Scenario 3: valid codex exists but specific ID is absent — no side effects
# conceptual-workflows-codex-chaos Failure Modes table + NFR (traversal is read-only, no writes)
def test_chaos_absent_id_no_side_effects(runner, project_dir):
    # Given: project_dir with docs "doc-alpha" and "doc-beta" but no "doc-gamma"
    # Also verifies: JSON mode must be accepted (exit 1, not 2) for completeness of the no-side-effects contract
    import subprocess
    import sys

    _write_codex_doc(project_dir, "doc-alpha", related=["doc-beta"])
    _write_codex_doc(project_dir, "doc-beta", related=[])

    codex_dir = project_dir / ".lore" / "codex"
    mtimes_before = {p: p.stat().st_mtime for p in codex_dir.rglob("*.md")}
    count_before = len(list(codex_dir.rglob("*.md")))

    proc = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "doc-gamma", "--threshold", "40"],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )

    assert proc.returncode == 1
    assert 'Document "doc-gamma" not found' in proc.stderr
    assert proc.stdout == ""

    # No side effects: no files created, modified, or deleted
    mtimes_after = {p: p.stat().st_mtime for p in codex_dir.rglob("*.md")}
    count_after = len(list(codex_dir.rglob("*.md")))
    assert count_after == count_before
    for path, mtime in mtimes_before.items():
        assert mtimes_after[path] == mtime

    # JSON mode: --json must also produce exit 1 (not 2) with no side effects
    # This assertion fails until --json is implemented on codex_chaos
    proc_json = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "doc-gamma", "--threshold", "40", "--json"],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )
    assert proc_json.returncode == 1, (
        f"Expected exit 1 in JSON mode; got {proc_json.returncode} "
        f"(--json not yet implemented on codex_chaos)"
    )
    assert proc_json.stdout == ""


# ---------------------------------------------------------------------------
# US-003: Output Formats — JSON Mode
# ---------------------------------------------------------------------------


# E2E — Scenario 1: JSON output on successful walk has correct structure
# conceptual-workflows-codex-chaos step 5 (Render: JSON mode → {"documents": [...]} envelope)
def test_chaos_json_output_valid_structure(runner, project_dir):
    import json

    # Given: project_dir with ≥5 connected docs from "json-seed"
    _write_codex_doc(project_dir, "json-seed", related=["js-n1", "js-n2", "js-n3", "js-n4"])
    _write_codex_doc(project_dir, "js-n1")
    _write_codex_doc(project_dir, "js-n2")
    _write_codex_doc(project_dir, "js-n3")
    _write_codex_doc(project_dir, "js-n4")

    # When: --json placed at end per flag-placement convention
    result = runner.invoke(main, ["codex", "chaos", "json-seed", "--threshold", "60", "--json"])

    # Then: exit 0
    assert result.exit_code == 0, f"Expected exit 0; got {result.exit_code}. output={result.output!r}"
    # stdout is valid JSON (result.stdout is the stdout-only stream in Click 8.2+)
    data = json.loads(result.stdout)
    # top-level object has exactly one key: "documents"
    assert set(data.keys()) == {"documents"}, f"Expected only 'documents' key; got {set(data.keys())}"
    # "documents" is a list
    assert isinstance(data["documents"], list), "Expected 'documents' to be a list"
    # first element's id is "json-seed"
    assert data["documents"][0]["id"] == "json-seed", (
        f"Expected first element id 'json-seed'; got {data['documents'][0]['id']!r}"
    )
    # each element has exactly the keys id, title, summary
    all_codex_ids = {"json-seed", "js-n1", "js-n2", "js-n3", "js-n4"}
    for doc in data["documents"]:
        assert set(doc.keys()) == {"id", "title", "summary"}, (
            f"Document has unexpected keys: {set(doc.keys())}"
        )
        assert doc["id"] in all_codex_ids, f"Unknown id {doc['id']!r} in documents"
    # no duplicate IDs
    ids = [d["id"] for d in data["documents"]]
    assert len(ids) == len(set(ids)), "Duplicate IDs found in documents"


# E2E — Scenario 2: --json flag placed after all positional and named arguments is accepted
# conceptual-workflows-codex-chaos Parameters table (--json flag position convention)
def test_chaos_json_flag_placement_convention(runner, project_dir):
    import json

    # Given: project_dir with "my-doc"
    _write_codex_doc(project_dir, "my-doc", related=[])

    # When: --json placed at end after all positional and named arguments
    result = runner.invoke(main, ["codex", "chaos", "my-doc", "--threshold", "50", "--json"])

    # Then: exit 0
    assert result.exit_code == 0, f"Expected exit 0; got {result.exit_code}. output={result.output!r}"
    # stdout is valid JSON with "documents" envelope (result.stdout is stdout-only in Click 8.2+)
    data = json.loads(result.stdout)
    assert "documents" in data, f"Expected 'documents' key in output; got {set(data.keys())}"


# E2E — Scenario 3: JSON error envelope when seed not found with --json
# conceptual-workflows-codex-chaos Failure Modes (Seed not found, JSON mode → {"error": ...} stderr, exit 1)
def test_chaos_json_error_not_found(runner, project_dir):
    import json

    # Given: project_dir with no "missing-doc"
    _write_codex_doc(project_dir, "existing-doc", related=[])

    # When: --json placed at end per convention
    result = runner.invoke(
        main,
        ["codex", "chaos", "missing-doc", "--threshold", "50", "--json"],
    )

    # Then: exit 1
    assert result.exit_code == 1, f"Expected exit 1; got {result.exit_code}"
    # stdout is empty (result.stdout is the stdout-only stream in Click 8.2+)
    assert result.stdout == "", f"Expected empty stdout; got {result.stdout!r}"
    # stderr parses as JSON {"error": 'Document "missing-doc" not found'}
    error_envelope = json.loads(result.stderr)
    assert error_envelope == {"error": 'Document "missing-doc" not found'}, (
        f"Unexpected error envelope: {error_envelope!r}"
    )


# E2E — Scenario 4: JSON error envelope when threshold is invalid with --json
# conceptual-workflows-codex-chaos Failure Modes (--threshold below 30 → {"error": ...} stderr, exit 1)
def test_chaos_json_error_invalid_threshold(runner, project_dir):
    import json

    # Given: any Lore project with "some-doc"
    _write_codex_doc(project_dir, "some-doc", related=[])

    # When: --threshold 20 (below floor of 30), --json at end
    result = runner.invoke(
        main,
        ["codex", "chaos", "some-doc", "--threshold", "20", "--json"],
    )

    # Then: exit 1
    assert result.exit_code == 1, f"Expected exit 1; got {result.exit_code}"
    # stdout is empty (result.stdout is the stdout-only stream in Click 8.2+)
    assert result.stdout == "", f"Expected empty stdout; got {result.stdout!r}"
    # stderr parses as JSON with an "error" key describing the threshold constraint
    error_envelope = json.loads(result.stderr)
    assert "error" in error_envelope, f"Expected 'error' key in stderr JSON; got {error_envelope!r}"
    assert "threshold" in error_envelope["error"].lower() or "30" in error_envelope["error"], (
        f"Error message does not describe threshold constraint: {error_envelope['error']!r}"
    )


# ---------------------------------------------------------------------------
# US-004: Input Validation — Threshold Range
# ---------------------------------------------------------------------------


# E2E — Scenario 1: --threshold=29 (below floor) is rejected
# conceptual-workflows-codex-chaos Failure Modes (--threshold below 30 → stderr error, exit 1)
def test_chaos_threshold_below_floor_rejected(runner, project_dir):
    # Given: project_dir with "some-doc"
    _write_codex_doc(project_dir, "some-doc", related=[])

    # When: --threshold 29 (below floor of 30)
    result = runner.invoke(main, ["codex", "chaos", "some-doc", "--threshold", "29"])

    # Then: exit 1, stderr contains exact message, stdout empty
    assert result.exit_code == 1, f"Expected exit 1; got {result.exit_code}"
    assert "--threshold must be between 30 and 100" in result.stderr, (
        f"Expected threshold range error in stderr; got {result.stderr!r}"
    )
    assert result.stdout == "", f"Expected empty stdout; got {result.stdout!r}"


# E2E — Scenario 2: --threshold=0 is rejected
# conceptual-workflows-codex-chaos Failure Modes (--threshold below 30 → stderr error, exit 1)
def test_chaos_threshold_zero_rejected(runner, project_dir):
    # Given: project_dir with "some-doc"
    _write_codex_doc(project_dir, "some-doc", related=[])

    # When: --threshold 0 (far below floor)
    result = runner.invoke(main, ["codex", "chaos", "some-doc", "--threshold", "0"])

    # Then: exit 1, stderr contains exact message, stdout empty
    assert result.exit_code == 1, f"Expected exit 1; got {result.exit_code}"
    assert "--threshold must be between 30 and 100" in result.stderr, (
        f"Expected threshold range error in stderr; got {result.stderr!r}"
    )
    assert result.stdout == "", f"Expected empty stdout; got {result.stdout!r}"


# E2E — Scenario 3: --threshold=101 (above ceiling) is rejected
# conceptual-workflows-codex-chaos Failure Modes (--threshold above 100 → stderr error, exit 1)
def test_chaos_threshold_above_ceiling_rejected(runner, project_dir):
    # Given: project_dir with "some-doc"
    _write_codex_doc(project_dir, "some-doc", related=[])

    # When: --threshold 101 (above ceiling of 100)
    result = runner.invoke(main, ["codex", "chaos", "some-doc", "--threshold", "101"])

    # Then: exit 1, stderr contains exact message, stdout empty
    assert result.exit_code == 1, f"Expected exit 1; got {result.exit_code}"
    assert "--threshold must be between 30 and 100" in result.stderr, (
        f"Expected threshold range error in stderr; got {result.stderr!r}"
    )
    assert result.stdout == "", f"Expected empty stdout; got {result.stdout!r}"


# E2E — Scenario 4: --threshold=30 (at floor) is accepted
# conceptual-workflows-codex-chaos Parameters table (--threshold: 30–100 inclusive, 30 is valid minimum)
def test_chaos_threshold_floor_accepted(runner, project_dir):
    # Given: project_dir with "floor-doc"
    _write_codex_doc(project_dir, "floor-doc", related=[])

    # When: --threshold 30 (floor boundary — must be accepted)
    result = runner.invoke(main, ["codex", "chaos", "floor-doc", "--threshold", "30"])

    # Then: exit 0, stdout table has at least one data row (seed "floor-doc"), stderr empty
    assert result.exit_code == 0, (
        f"Expected exit 0 for threshold=30; got {result.exit_code}. stderr={result.stderr!r}"
    )
    ids = _parse_table_ids(result.stdout)
    assert len(ids) >= 1, f"Expected at least one row in table; got rows: {ids}"
    assert ids[0] == "floor-doc", (
        f"Expected seed 'floor-doc' as first row; got {ids[0]!r}"
    )
    assert result.stderr == "", f"Expected empty stderr; got {result.stderr!r}"


# E2E — Scenario 5: --threshold=100 (at ceiling) is accepted
# conceptual-workflows-codex-chaos Parameters table (--threshold: 30–100 inclusive, 100 is valid maximum)
def test_chaos_threshold_ceiling_accepted(runner, project_dir):
    # Given: project_dir with "ceil-doc"
    _write_codex_doc(project_dir, "ceil-doc", related=[])

    # When: --threshold 100 (ceiling boundary — must be accepted)
    result = runner.invoke(main, ["codex", "chaos", "ceil-doc", "--threshold", "100"])

    # Then: exit 0, stdout table has at least one data row, stderr empty
    assert result.exit_code == 0, (
        f"Expected exit 0 for threshold=100; got {result.exit_code}. stderr={result.stderr!r}"
    )
    ids = _parse_table_ids(result.stdout)
    assert len(ids) >= 1, f"Expected at least one row in table; got rows: {ids}"
    assert result.stderr == "", f"Expected empty stderr; got {result.stderr!r}"


# E2E — Scenario 6: --threshold is required — omitting it produces a Click error
# conceptual-workflows-codex-chaos Parameters table (--threshold: required flag)
def test_chaos_threshold_required_flag(runner, project_dir):
    # Given: project_dir with "some-doc"
    _write_codex_doc(project_dir, "some-doc", related=[])

    # When: no --threshold flag provided
    result = runner.invoke(main, ["codex", "chaos", "some-doc"])

    # Then: exit code 2 (Click missing-option error), output references --threshold
    assert result.exit_code == 2, (
        f"Expected Click missing-option exit code 2; got {result.exit_code}"
    )
    assert "--threshold" in result.output, (
        f"Expected '--threshold' in output; got {result.output!r}"
    )


# E2E — Scenario 7: invalid threshold with --json emits JSON error envelope to stderr
# conceptual-workflows-codex-chaos Failure Modes (--threshold below 30, JSON mode → {"error": ...} stderr, exit 1)
def test_chaos_threshold_invalid_json_mode_error_envelope(runner, project_dir):
    import json

    # Given: project_dir with "some-doc"
    _write_codex_doc(project_dir, "some-doc", related=[])

    # When: --threshold 20 (below floor), --json at end per flag-placement convention
    result = runner.invoke(
        main, ["codex", "chaos", "some-doc", "--threshold", "20", "--json"]
    )

    # Then: exit 1, stdout empty, stderr is valid JSON error envelope
    assert result.exit_code == 1, f"Expected exit 1; got {result.exit_code}"
    assert result.stdout == "", f"Expected empty stdout; got {result.stdout!r}"
    error_envelope = json.loads(result.stderr)
    assert error_envelope == {"error": "--threshold must be between 30 and 100"}, (
        f"Expected exact error envelope; got {error_envelope!r}"
    )


# ---------------------------------------------------------------------------
# US-005: Doctrine Integration
# ---------------------------------------------------------------------------


# E2E — Scenario 1: feature-implementation doctrine is structurally valid and loadable
# conceptual-workflows-codex-chaos (FR-16: doctrine update must not break doctrine validation)
def test_feature_impl_doctrine_valid(runner, project_dir):
    result = runner.invoke(main, ["doctrine", "show", "feature-implementation"])

    assert result.exit_code == 0, (
        f"Expected exit 0 (doctrine must remain structurally valid); "
        f"got {result.exit_code}. output={result.output!r}"
    )
