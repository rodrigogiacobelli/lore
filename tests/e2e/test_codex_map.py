"""E2E tests for `lore codex map` — list-shape table default + scenarios.

Specs:
- codex-map-us-1 — default neighbourhood scan returns list-shape table.
- codex-map-us-8 — seed exclusion + cross-direction dedupe (default + JSON).
- codex-map-us-9 — unknown seed + empty neighbourhood semantics.

Tech spec: codex-map-tech-spec.

This file was rewritten as part of the G1 Red phase. Obsolete tests that
pinned the old positional `--depth` API, full-body default output, and
BFS-order assertions were removed per codex-map-tech-spec § Project
Structure. Downstream Red phases (G2..G7) will re-add coverage for
`--depth-out`, `--depth-in`, `--full`, the conflict-flag UsageError,
and the `--full --json` `{"documents": [...]}` envelope.

CliRunner gotcha (project memory): Click 8.3 removed `mix_stderr=False`.
Use `result.stdout` / `result.stderr` on the result object, or shell out
via `subprocess.run` for true stream separation.
"""

import json
import subprocess
import sys

import pytest

from lore.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_codex_doc(
    project_dir,
    doc_id,
    *,
    related=None,
    omit_related=False,
    body=None,
    subdir=None,
    title=None,
    summary=None,
):
    """Write a codex document into .lore/codex/ and return its path.

    `subdir` (slash-separated) is created under .lore/codex/; the doc is
    placed there. Used to test the GROUP column.
    """
    body_text = body if body is not None else f"Body of {doc_id}."
    title_value = title if title is not None else doc_id.replace("-", " ").title()
    summary_value = summary if summary is not None else f"Summary for {doc_id}."
    lines = [
        "---",
        f"id: {doc_id}",
        f"title: {title_value}",
        f"summary: {summary_value}",
    ]
    if not omit_related:
        if related is None:
            lines.append("related: []")
        else:
            lines.append("related:")
            for r in related:
                lines.append(f"  - {r}")
    lines.extend(["---", "", body_text, ""])
    content = "\n".join(lines)
    codex_dir = project_dir / ".lore" / "codex"
    if subdir:
        codex_dir = codex_dir / subdir
    codex_dir.mkdir(parents=True, exist_ok=True)
    path = codex_dir / f"{doc_id}.md"
    path.write_text(content)
    return path


# ===========================================================================
# US-001 — default neighbourhood scan returns list-shape table
# ===========================================================================


# E2E — Scenario 1: bidirectional default at depth 1 returns both directions.
def test_codex_map_default_returns_list_table_excluding_seed(project_dir, runner):
    """seed -> child-a (outbound), parent-b -> seed (inbound), no other docs.

    Default `lore codex map seed` returns the four-column header
    "ID  GROUP  TITLE  SUMMARY" followed by two rows in alphabetical
    order by id — child-a then parent-b. Seed row is absent. No
    markdown body content in stdout. Exit code 0.
    """
    _write_codex_doc(project_dir, "seed", related=["child-a"])
    _write_codex_doc(project_dir, "child-a", related=[])
    _write_codex_doc(project_dir, "parent-b", related=["seed"])

    result = runner.invoke(main, ["codex", "map", "seed"])

    assert result.exit_code == 0, result.output
    output = result.output
    # Header line contains ID/GROUP/TITLE/SUMMARY column names.
    assert "ID" in output
    assert "GROUP" in output
    assert "TITLE" in output
    assert "SUMMARY" in output
    # Body rows present, alphabetically ordered.
    assert "child-a" in output
    assert "parent-b" in output
    assert output.index("child-a") < output.index("parent-b")
    # Seed row absent — no "seed" appearing as the first column on any row.
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("seed "):
            raise AssertionError(f"seed row leaked into output: {line!r}")
    # No legacy === id === separator in default mode.
    assert "=== seed ===" not in output
    assert "=== child-a ===" not in output


# E2E — Scenario 2: GROUP column matches `lore codex list` derivation.
def test_codex_map_default_group_column_matches_codex_list(project_dir, runner):
    """seed and neighbour under .lore/codex/foo/bar/ — GROUP cell == foo/bar."""
    _write_codex_doc(project_dir, "seed", related=["neighbour"], subdir="foo/bar")
    _write_codex_doc(project_dir, "neighbour", related=[], subdir="foo/bar")

    result = runner.invoke(main, ["codex", "map", "seed"])

    assert result.exit_code == 0, result.output
    # The row for neighbour must contain the group "foo/bar".
    neighbour_lines = [line for line in result.output.splitlines() if "neighbour" in line]
    assert neighbour_lines, "no row for neighbour found"
    assert any("foo/bar" in line for line in neighbour_lines)


# E2E — Scenario 3: Default mode never prints document bodies.
def test_codex_map_default_omits_bodies(project_dir, runner):
    """child-a body contains "SENTINEL-BODY-1234"; default map must not leak it."""
    _write_codex_doc(project_dir, "seed", related=["child-a"])
    _write_codex_doc(
        project_dir, "child-a", related=[], body="SENTINEL-BODY-1234"
    )

    result = runner.invoke(main, ["codex", "map", "seed"])

    assert result.exit_code == 0, result.output
    assert "SENTINEL-BODY-1234" not in result.output


# E2E — Scenario 4: Rows sorted alphabetically by id.
def test_codex_map_default_rows_sorted_alphabetically(project_dir, runner):
    """seed with three outbound neighbours zebra, apple, mango at depth 1.

    Row order: apple, mango, zebra — regardless of declaration order.
    """
    _write_codex_doc(project_dir, "seed", related=["zebra", "apple", "mango"])
    _write_codex_doc(project_dir, "zebra", related=[])
    _write_codex_doc(project_dir, "apple", related=[])
    _write_codex_doc(project_dir, "mango", related=[])

    result = runner.invoke(main, ["codex", "map", "seed"])

    assert result.exit_code == 0, result.output
    output = result.output
    # Must be the table renderer, not the legacy `=== id ===` body dump.
    assert "=== seed ===" not in output
    assert "=== apple ===" not in output
    assert "=== zebra ===" not in output
    # Table must have a header line.
    assert "ID" in output and "GROUP" in output
    pos_apple = output.index("apple")
    pos_mango = output.index("mango")
    pos_zebra = output.index("zebra")
    assert pos_apple < pos_mango < pos_zebra


# ===========================================================================
# US-008 — seed exclusion + cross-direction dedupe
# ===========================================================================


# E2E — Scenario 1: Seed absent in default text mode.
def test_codex_map_seed_absent_default_text(project_dir, runner):
    """seed with one outbound child-a and one inbound parent-b.

    Rows for child-a and parent-b present; no row whose ID column == "seed".
    """
    _write_codex_doc(project_dir, "seed", related=["child-a"])
    _write_codex_doc(project_dir, "child-a", related=[])
    _write_codex_doc(project_dir, "parent-b", related=["seed"])

    result = runner.invoke(main, ["codex", "map", "seed"])

    assert result.exit_code == 0, result.output
    assert "child-a" in result.output
    assert "parent-b" in result.output
    # No row whose first column is "seed".
    for line in result.output.splitlines():
        if line.strip().startswith("seed "):
            raise AssertionError(f"seed leaked into output: {line!r}")


# E2E — Scenario 3: Cross-direction neighbour deduplicated in default mode.
def test_codex_map_default_dedupes_cross_direction(project_dir, runner):
    """Mutual citation seed <-> shared; row for shared exactly once."""
    _write_codex_doc(project_dir, "seed", related=["shared"])
    _write_codex_doc(project_dir, "shared", related=["seed"])

    result = runner.invoke(main, ["codex", "map", "seed", "--depth", "1"])

    assert result.exit_code == 0, result.output
    # `shared` ID appears in exactly one row (header column is "ID", not "shared").
    shared_row_count = sum(
        1
        for line in result.output.splitlines()
        if line.strip().startswith("shared ") or line.strip() == "shared"
    )
    assert shared_row_count == 1


# E2E — Scenario 5: Seed absent in default JSON mode.
def test_codex_map_seed_absent_default_json(project_dir, runner):
    """`lore --json codex map seed` — top-level "codex" list has no seed entry."""
    _write_codex_doc(project_dir, "seed", related=["child-a"])
    _write_codex_doc(project_dir, "child-a", related=[])
    _write_codex_doc(project_dir, "parent-b", related=["seed"])

    result = runner.invoke(main, ["--json", "codex", "map", "seed"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert "codex" in data
    ids = [d["id"] for d in data["codex"]]
    assert "seed" not in ids
    assert "child-a" in ids
    assert "parent-b" in ids


# ===========================================================================
# US-009 — unknown seed + empty neighbourhood semantics
# ===========================================================================


# E2E — Scenario 1: Unknown seed in default mode exits 1 with "not found".
def test_codex_map_unknown_seed_default_exits_one(project_dir):
    """`lore codex map does-not-exist` → exit 1, stderr has pinned message."""
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from lore.cli import main; main()",
            "codex",
            "map",
            "does-not-exist",
        ],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )

    assert proc.returncode == 1
    assert proc.stdout == ""
    assert 'Document "does-not-exist" not found' in proc.stderr


# E2E — Scenario 2: Unknown seed under --json returns JSON error envelope.
def test_codex_map_unknown_seed_json_envelope(project_dir):
    """`lore --json codex map does-not-exist` → exit 1, stderr JSON envelope."""
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from lore.cli import main; main()",
            "--json",
            "codex",
            "map",
            "does-not-exist",
        ],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stderr.strip())
    assert payload == {"error": 'Document "does-not-exist" not found'}


# E2E — Scenario 4: Empty neighbourhood prints "No related documents."
def test_codex_map_empty_neighbourhood_default_text(project_dir, runner):
    """Single doc seed with no related and no citers — exit 0, sentinel line."""
    _write_codex_doc(project_dir, "seed", related=[])

    result = runner.invoke(main, ["codex", "map", "seed"])

    assert result.exit_code == 0, result.output
    assert "No related documents." in result.output


# E2E — Scenario 5: --depth 0 returns empty result (seed always excluded).
def test_codex_map_depth_0_returns_empty(project_dir, runner):
    """Seed with one outbound and one inbound neighbour; --depth 0 → empty."""
    _write_codex_doc(project_dir, "seed", related=["child-a"])
    _write_codex_doc(project_dir, "child-a", related=[])
    _write_codex_doc(project_dir, "parent-b", related=["seed"])

    result = runner.invoke(main, ["codex", "map", "seed", "--depth", "0"])

    assert result.exit_code == 0, result.output
    assert "No related documents." in result.output
    # And neighbours must NOT appear — depth 0 means no expansion.
    for line in result.output.splitlines():
        stripped = line.strip()
        # The header line contains TITLE etc; neighbour ids must not be row prefixes.
        assert not stripped.startswith("child-a "), (
            f"child-a leaked into --depth 0 output: {line!r}"
        )
        assert not stripped.startswith("parent-b "), (
            f"parent-b leaked into --depth 0 output: {line!r}"
        )


# ===========================================================================
# Command surface — kept from the legacy file (still valid post-refactor).
# ===========================================================================


# Command is registered under the codex group.
def test_map_subcommand_accessible_under_codex_group(project_dir, runner):
    """`lore codex map <doc>` does not raise "No such command"."""
    _write_codex_doc(project_dir, "some-doc", related=[])

    result = runner.invoke(main, ["codex", "map", "some-doc"])

    assert "No such command" not in result.output
    assert result.exit_code == 0


# Help text refers to map's purpose.
def test_codex_map_help_output(project_dir, runner):
    """`lore codex map --help` lists DOC_ID and a sensible synopsis."""
    result = runner.invoke(main, ["codex", "map", "--help"])

    assert result.exit_code == 0
    assert "codex map [OPTIONS] DOC_ID" in result.output
    assert "Map a codex document cluster" in result.output


# Parent group help lists `map`.
def test_codex_group_help_lists_map_subcommand(project_dir, runner):
    result = runner.invoke(main, ["codex", "--help"])

    assert result.exit_code == 0
    assert "map" in result.output


# Missing positional argument is a UsageError.
def test_map_missing_doc_id_produces_usage_error(project_dir, runner):
    result = runner.invoke(main, ["codex", "map"], catch_exceptions=False)

    assert result.exit_code == 2
    assert "Missing argument 'DOC_ID'." in result.output


# Extra positional arguments are rejected.
def test_map_extra_positional_arguments_rejected(project_dir, runner):
    result = runner.invoke(
        main, ["codex", "map", "doc-a", "doc-b"], catch_exceptions=False
    )

    assert result.exit_code == 2
    assert "Got unexpected extra argument" in result.output


# Negative --depth is rejected by Click's IntRange.
def test_negative_depth_is_rejected_by_click(project_dir, runner):
    """`--depth -1` → exit 2, error about invalid value."""
    _write_codex_doc(project_dir, "seed", related=[])

    result = runner.invoke(main, ["codex", "map", "seed", "--depth", "-1"])

    assert result.exit_code == 2
    assert "Invalid value for '--depth'" in result.output


# Local --json on the subcommand is rejected (global flag only).
def test_local_json_flag_on_map_subcommand_is_rejected(project_dir, runner):
    _write_codex_doc(project_dir, "some-doc", related=[])

    result = runner.invoke(main, ["codex", "map", "some-doc", "--json"])

    assert result.exit_code == 2


# ===========================================================================
# US-002 — Outbound-only deep walk via --depth-out (E2E)
# ===========================================================================


# Pinned conflict message — must match cli.py and the PRD byte-for-byte.
_CONFLICT_MSG = (
    "--depth cannot be combined with --depth-in or --depth-out. "
    "Use --depth for symmetric traversal, or --depth-in and/or "
    "--depth-out for directional traversal."
)


# E2E — Scenario 1: `--depth-out 2` returns depth-1 and depth-2 outbound only
# eager-impl from G1; locking in
def test_codex_map_depth_out_2_includes_depth2_outbound_only(project_dir, runner):
    """seed -> a -> b -> c (depth 3); parent-x -> seed (inbound). --depth-out 2 -> [a, b]."""
    _write_codex_doc(project_dir, "seed", related=["a"])
    _write_codex_doc(project_dir, "a", related=["b"])
    _write_codex_doc(project_dir, "b", related=["c"])
    _write_codex_doc(project_dir, "c", related=[])
    _write_codex_doc(project_dir, "parent-x", related=["seed"])

    result = runner.invoke(main, ["codex", "map", "seed", "--depth-out", "2"])

    assert result.exit_code == 0, result.output
    output = result.output
    assert "a" in output
    assert "b" in output
    # c at depth 3 must be absent — check no row starts with "c ".
    for line in output.splitlines():
        stripped = line.strip()
        assert not stripped.startswith("c "), f"c leaked: {line!r}"
    # parent-x absent — inbound disabled.
    for line in output.splitlines():
        stripped = line.strip()
        assert not stripped.startswith("parent-x "), f"parent-x leaked: {line!r}"
    # seed absent.
    for line in output.splitlines():
        stripped = line.strip()
        assert not stripped.startswith("seed "), f"seed leaked: {line!r}"
    # alphabetical order: a before b.
    assert output.index("a") < output.index("b")


# E2E — Scenario 2: `--depth-out 1` does not surface backlinks
# eager-impl from G1; locking in
def test_codex_map_depth_out_1_ignores_backlinks(project_dir, runner):
    """seed (related:[]), cite-a (related:[seed]). --depth-out 1 -> empty."""
    _write_codex_doc(project_dir, "seed", related=[])
    _write_codex_doc(project_dir, "cite-a", related=["seed"])

    result = runner.invoke(main, ["codex", "map", "seed", "--depth-out", "1"])

    assert result.exit_code == 0, result.output
    assert "No related documents." in result.output


# E2E — Scenario 3: `--depth-out 0` returns empty neighbourhood
# eager-impl from G1; locking in
def test_codex_map_depth_out_0_returns_empty(project_dir, runner):
    """seed (related:[a]), a (related:[]). --depth-out 0 -> empty."""
    _write_codex_doc(project_dir, "seed", related=["a"])
    _write_codex_doc(project_dir, "a", related=[])

    result = runner.invoke(main, ["codex", "map", "seed", "--depth-out", "0"])

    assert result.exit_code == 0, result.output
    assert "No related documents." in result.output


# E2E — Scenario 4: Negative `--depth-out` rejected by Click IntRange(min=0)
# eager-impl from G1; locking in
def test_codex_map_depth_out_negative_exits_two(project_dir, runner):
    """`--depth-out -1` -> exit 2 (Click IntRange rejection)."""
    _write_codex_doc(project_dir, "seed", related=[])

    result = runner.invoke(main, ["codex", "map", "seed", "--depth-out", "-1"])

    assert result.exit_code == 2
    assert "Invalid value for '--depth-out'" in result.output


# ===========================================================================
# US-003 — Inbound-only backlink scan via --depth-in (E2E)
# ===========================================================================


# E2E — Scenario 1: `--depth-in 1` returns inbound citers only
# eager-impl from G1; locking in
def test_codex_map_depth_in_1_returns_backlinks_only(project_dir, runner):
    """seed (related:[outbound-x]); cite-a/b/c (related:[seed]); outbound-x (related:[]).

    --depth-in 1 -> rows: cite-a, cite-b, cite-c in alphabetical order.
    outbound-x absent.
    """
    _write_codex_doc(project_dir, "seed", related=["outbound-x"])
    _write_codex_doc(project_dir, "outbound-x", related=[])
    _write_codex_doc(project_dir, "cite-a", related=["seed"])
    _write_codex_doc(project_dir, "cite-b", related=["seed"])
    _write_codex_doc(project_dir, "cite-c", related=["seed"])

    result = runner.invoke(main, ["codex", "map", "seed", "--depth-in", "1"])

    assert result.exit_code == 0, result.output
    output = result.output
    assert "cite-a" in output
    assert "cite-b" in output
    assert "cite-c" in output
    # outbound-x must be absent — no row line starts with "outbound-x ".
    for line in output.splitlines():
        stripped = line.strip()
        assert not stripped.startswith("outbound-x "), (
            f"outbound-x leaked: {line!r}"
        )
    # seed absent.
    for line in output.splitlines():
        stripped = line.strip()
        assert not stripped.startswith("seed "), f"seed leaked: {line!r}"
    # alphabetical order.
    assert output.index("cite-a") < output.index("cite-b") < output.index("cite-c")


# E2E — Scenario 2: `--depth-in 1` ignores outbound edges from seed
# eager-impl from G1; locking in
def test_codex_map_depth_in_1_ignores_outbound(project_dir, runner):
    """seed (related:[outbound-x]), no citers. --depth-in 1 -> empty."""
    _write_codex_doc(project_dir, "seed", related=["outbound-x"])
    _write_codex_doc(project_dir, "outbound-x", related=[])

    result = runner.invoke(main, ["codex", "map", "seed", "--depth-in", "1"])

    assert result.exit_code == 0, result.output
    assert "No related documents." in result.output


# E2E — Scenario 3: `--depth-in 0` returns empty
# eager-impl from G1; locking in
def test_codex_map_depth_in_0_returns_empty(project_dir, runner):
    """seed with inbound citers; --depth-in 0 -> empty."""
    _write_codex_doc(project_dir, "seed", related=[])
    _write_codex_doc(project_dir, "cite-a", related=["seed"])
    _write_codex_doc(project_dir, "cite-b", related=["seed"])

    result = runner.invoke(main, ["codex", "map", "seed", "--depth-in", "0"])

    assert result.exit_code == 0, result.output
    assert "No related documents." in result.output


# E2E — Scenario 4: Backlink visible under --depth-in, invisible under --depth-out
# eager-impl from G1; locking in
def test_codex_map_backlink_invisible_under_depth_out(project_dir, runner):
    """seed (related:[]); cite-a (related:[seed]).

    --depth-out 1 -> empty. --depth-in 1 -> row for cite-a.
    """
    _write_codex_doc(project_dir, "seed", related=[])
    _write_codex_doc(project_dir, "cite-a", related=["seed"])

    out_result = runner.invoke(main, ["codex", "map", "seed", "--depth-out", "1"])
    assert out_result.exit_code == 0, out_result.output
    assert "No related documents." in out_result.output

    in_result = runner.invoke(main, ["codex", "map", "seed", "--depth-in", "1"])
    assert in_result.exit_code == 0, in_result.output
    assert "cite-a" in in_result.output


# E2E — Negative --depth-in is rejected by Click's IntRange.
# eager-impl from G1; locking in
def test_codex_map_depth_in_negative_exits_two(project_dir, runner):
    """`--depth-in -1` -> exit 2 (Click IntRange rejection)."""
    _write_codex_doc(project_dir, "seed", related=[])

    result = runner.invoke(main, ["codex", "map", "seed", "--depth-in", "-1"])

    assert result.exit_code == 2
    assert "Invalid value for '--depth-in'" in result.output


# ===========================================================================
# US-004 — Symmetric --depth shortcut and conflict error (E2E)
# ===========================================================================


# E2E — Scenario 1: `--depth N` sets both budgets to N
# eager-impl from G1; locking in
def test_codex_map_depth_2_sets_symmetric_budgets(project_dir, runner):
    """seed -> a -> b; parent-x -> seed; grandparent-y -> parent-x.

    --depth 2 -> four rows: a, b, grandparent-y, parent-x (alphabetical).
    """
    _write_codex_doc(project_dir, "seed", related=["a"])
    _write_codex_doc(project_dir, "a", related=["b"])
    _write_codex_doc(project_dir, "b", related=[])
    _write_codex_doc(project_dir, "parent-x", related=["seed"])
    _write_codex_doc(project_dir, "grandparent-y", related=["parent-x"])

    result = runner.invoke(main, ["codex", "map", "seed", "--depth", "2"])

    assert result.exit_code == 0, result.output
    output = result.output
    assert "a" in output
    assert "b" in output
    assert "grandparent-y" in output
    assert "parent-x" in output
    # seed absent.
    for line in output.splitlines():
        stripped = line.strip()
        assert not stripped.startswith("seed "), f"seed leaked: {line!r}"
    # alphabetical: a < b < grandparent-y < parent-x
    assert (
        output.index("a")
        < output.index("b")
        < output.index("grandparent-y")
        < output.index("parent-x")
    )


# E2E — Scenarios 2/3/4: `--depth` combined with any directional flag is a
# usage error with the pinned conflict message.
# eager-impl from G1; locking in
@pytest.mark.parametrize(
    "extra_flags",
    [
        pytest.param(["--depth-out", "1"], id="depth+depth-out"),
        pytest.param(["--depth-in", "1"], id="depth+depth-in"),
        pytest.param(
            ["--depth-in", "1", "--depth-out", "1"], id="depth+both-directionals"
        ),
    ],
)
def test_codex_map_depth_combined_with_directional_is_usage_error(
    project_dir, runner, extra_flags
):
    """`--depth N` + any directional flag -> exit 2 with pinned conflict substring."""
    _write_codex_doc(project_dir, "seed", related=[])

    result = runner.invoke(
        main, ["codex", "map", "seed", "--depth", "2", *extra_flags]
    )

    assert result.exit_code == 2
    assert f"Error: {_CONFLICT_MSG}" in result.stderr


# E2E — Scenario 5: `--depth-in` + `--depth-out` together is valid
# eager-impl from G1; locking in
def test_codex_map_depth_in_and_depth_out_combine_without_error(project_dir, runner):
    """seed with inbound citer and outbound child; `--depth-in 1 --depth-out 2`.

    Exit 0; result contains both the outbound child and the inbound citer.
    """
    _write_codex_doc(project_dir, "seed", related=["child"])
    _write_codex_doc(project_dir, "child", related=[])
    _write_codex_doc(project_dir, "parent", related=["seed"])

    result = runner.invoke(
        main,
        [
            "codex",
            "map",
            "seed",
            "--depth-in",
            "1",
            "--depth-out",
            "2",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "child" in result.output
    assert "parent" in result.output


# E2E — Scenario 6: Conflict check fires before seed lookup
# eager-impl from G1; locking in
def test_codex_map_conflict_check_precedes_seed_lookup(project_dir, runner):
    """`codex map does-not-exist --depth 2 --depth-out 1` -> exit 2 (conflict), not exit 1 (not found)."""
    # No doc with id "does-not-exist" exists.

    result = runner.invoke(
        main,
        [
            "codex",
            "map",
            "does-not-exist",
            "--depth",
            "2",
            "--depth-out",
            "1",
        ],
    )

    assert result.exit_code == 2
    assert f"Error: {_CONFLICT_MSG}" in result.stderr
    # MUST NOT be the "not found" path.
    assert 'Document "does-not-exist" not found' not in result.stderr
    assert 'Document "does-not-exist" not found' not in result.output


# E2E — Scenario 7: Conflict error under --json mode emits JSON envelope to stderr
# NOT eager — current impl emits Click default text output, not JSON envelope.
# This test SHOULD FAIL today and become green in G2 Green.
def test_codex_map_conflict_error_json_envelope(project_dir, runner):
    """`lore --json codex map seed --depth 2 --depth-out 1` -> exit 2, JSON envelope on stderr."""
    _write_codex_doc(project_dir, "seed", related=[])

    result = runner.invoke(
        main,
        [
            "--json",
            "codex",
            "map",
            "seed",
            "--depth",
            "2",
            "--depth-out",
            "1",
        ],
    )

    assert result.exit_code == 2
    payload = json.loads(result.stderr.strip())
    assert payload == {"error": _CONFLICT_MSG}


# ===========================================================================
# US-005 — Full-body bidirectional dump via --full (E2E text mode)
# ===========================================================================


# E2E — Scenario 1: --full --depth 2 prints bodies in alphabetical order
# eager-impl from G1/G2; locking in
def test_codex_map_full_text_renders_bodies_excluding_seed(project_dir, runner):
    """seed (rel:[child-a]), child-a body 'Body of child-a.', parent-b (rel:[seed])
    body 'Body of parent-b.', grandparent-c (rel:[parent-b]) body 'Body of grandparent-c.'.
    --full --depth 2 -> alphabetical block dump excluding seed.
    """
    _write_codex_doc(project_dir, "seed", related=["child-a"])
    _write_codex_doc(project_dir, "child-a", related=[], body="Body of child-a.")
    _write_codex_doc(project_dir, "parent-b", related=["seed"], body="Body of parent-b.")
    _write_codex_doc(
        project_dir, "grandparent-c", related=["parent-b"], body="Body of grandparent-c."
    )

    result = runner.invoke(main, ["codex", "map", "seed", "--full", "--depth", "2"])

    assert result.exit_code == 0, result.stderr
    out = result.stdout
    assert "=== child-a ===" in out
    assert "Body of child-a." in out
    assert "=== grandparent-c ===" in out
    assert "Body of grandparent-c." in out
    assert "=== parent-b ===" in out
    assert "Body of parent-b." in out
    # Alphabetical order by id.
    assert (
        out.index("=== child-a ===")
        < out.index("=== grandparent-c ===")
        < out.index("=== parent-b ===")
    )
    # Seed absent.
    assert "=== seed ===" not in out


# E2E — Scenario 2: --full composes with --depth-out
# eager-impl from G1/G2; locking in
def test_codex_map_full_composes_with_depth_out(project_dir, runner):
    """seed -> a -> b outbound chain; parent-x -> seed inbound.
    --full --depth-out 1 -> exactly one body block for 'a'.
    """
    _write_codex_doc(project_dir, "seed", related=["a"])
    _write_codex_doc(project_dir, "a", related=["b"], body="Body of a.")
    _write_codex_doc(project_dir, "b", related=[], body="Body of b.")
    _write_codex_doc(project_dir, "parent-x", related=["seed"], body="Body of parent-x.")

    result = runner.invoke(
        main, ["codex", "map", "seed", "--full", "--depth-out", "1"]
    )

    assert result.exit_code == 0, result.stderr
    out = result.stdout
    assert "=== a ===" in out
    assert "Body of a." in out
    assert "=== b ===" not in out
    assert "Body of b." not in out
    assert "=== parent-x ===" not in out
    assert "Body of parent-x." not in out
    assert "=== seed ===" not in out


# E2E — Scenario 3: --full dedupes cross-direction neighbour
# eager-impl from G1/G2; locking in
def test_codex_map_full_dedupes_cross_direction(project_dir, runner):
    """seed (rel:[shared]) and shared (rel:[seed]) -- mutual citation.
    --full --depth 1 -> '=== shared ===' appears exactly once.
    """
    _write_codex_doc(project_dir, "seed", related=["shared"])
    _write_codex_doc(project_dir, "shared", related=["seed"], body="Body of shared.")

    result = runner.invoke(main, ["codex", "map", "seed", "--full", "--depth", "1"])

    assert result.exit_code == 0, result.stderr
    out = result.stdout
    assert out.count("=== shared ===") == 1
    assert "=== seed ===" not in out


# E2E — Scenario 4: --full still rejects --depth with --depth-out
# eager-impl from G1/G2; locking in
def test_codex_map_full_rejects_depth_with_directional(project_dir, runner):
    """--full --depth 2 --depth-out 1 -> exit 2 with pinned conflict message."""
    _write_codex_doc(project_dir, "seed", related=[])

    result = runner.invoke(
        main,
        [
            "codex", "map", "seed",
            "--full", "--depth", "2", "--depth-out", "1",
        ],
    )

    assert result.exit_code == 2
    assert f"Error: {_CONFLICT_MSG}" in result.stderr


# E2E — --full composes with --depth-in (inbound-only full dump).
# eager-impl from G1/G2; locking in
def test_codex_map_full_composes_with_depth_in(project_dir, runner):
    """seed (rel:[a]) outbound; parent-x (rel:[seed]) inbound.
    --full --depth-in 1 -> exactly one block for parent-x, no a, no seed.
    """
    _write_codex_doc(project_dir, "seed", related=["a"])
    _write_codex_doc(project_dir, "a", related=[], body="Body of a.")
    _write_codex_doc(project_dir, "parent-x", related=["seed"], body="Body of parent-x.")

    result = runner.invoke(
        main, ["codex", "map", "seed", "--full", "--depth-in", "1"]
    )

    assert result.exit_code == 0, result.stderr
    out = result.stdout
    assert "=== parent-x ===" in out
    assert "Body of parent-x." in out
    assert "=== a ===" not in out
    assert "=== seed ===" not in out


# E2E — --full empty neighbourhood prints nothing and exits 0.
# eager-impl from G1/G2; locking in
def test_codex_map_full_empty_neighbourhood_text(project_dir, runner):
    """Isolated seed under --full text mode prints empty stdout, exits 0."""
    _write_codex_doc(project_dir, "seed", related=[])

    result = runner.invoke(main, ["codex", "map", "seed", "--full"])

    assert result.exit_code == 0, result.stderr
    assert "===" not in result.stdout
    assert "No related documents." not in result.stdout


# ===========================================================================
# US-006 — Default-mode JSON envelope keyed on `codex` (E2E)
# ===========================================================================


# E2E — Scenario 1: Default --json envelope key is 'codex' with four-key entries.
# eager-impl from G1/G2; locking in
def test_codex_map_default_json_envelope_is_codex(project_dir, runner):
    """child-a at foo/bar/, title='Child A', summary='Child A summary.'."""
    _write_codex_doc(project_dir, "seed", related=["child-a"])
    _write_codex_doc(
        project_dir,
        "child-a",
        related=[],
        subdir="foo/bar",
        title="Child A",
        summary="Child A summary.",
    )

    result = runner.invoke(main, ["--json", "codex", "map", "seed"])

    assert result.exit_code == 0, result.stderr
    parsed = json.loads(result.stdout)
    assert set(parsed.keys()) == {"codex"}
    assert len(parsed["codex"]) == 1
    entry = parsed["codex"][0]
    assert entry == {
        "id": "child-a",
        "group": "foo/bar",
        "title": "Child A",
        "summary": "Child A summary.",
    }
    # No body or related at any entry level.
    assert "body" not in entry
    assert "related" not in entry


# E2E — Scenario 2: Empty neighbourhood emits {"codex": []}.
# eager-impl from G1/G2; locking in
def test_codex_map_default_json_empty_neighbourhood(project_dir, runner):
    """Isolated seed -> stdout exactly '{"codex": []}', exit 0, stderr empty."""
    _write_codex_doc(project_dir, "seed", related=[])

    result = runner.invoke(main, ["--json", "codex", "map", "seed"])

    assert result.exit_code == 0, result.stderr
    parsed = json.loads(result.stdout)
    assert parsed == {"codex": []}
    assert result.stderr == ""


# E2E — Scenario 3: Default --json entries deduped + alphabetical.
# eager-impl from G1/G2; locking in
def test_codex_map_default_json_sorted_and_deduped(project_dir, runner):
    """seed -> zebra, apple, mango; mango <-> seed mutual; ids sorted; mango once."""
    _write_codex_doc(project_dir, "seed", related=["zebra", "apple", "mango"])
    _write_codex_doc(project_dir, "zebra", related=[])
    _write_codex_doc(project_dir, "apple", related=[])
    _write_codex_doc(project_dir, "mango", related=["seed"])  # mutual w/ seed

    result = runner.invoke(main, ["--json", "codex", "map", "seed"])

    assert result.exit_code == 0, result.stderr
    parsed = json.loads(result.stdout)
    ids = [e["id"] for e in parsed["codex"]]
    assert ids == ["apple", "mango", "zebra"]
    assert ids.count("mango") == 1
    assert "seed" not in ids


# E2E — Scenario 4: Empty-string group normalised to null in JSON.
# eager-impl from G1/G2; locking in
def test_codex_map_default_json_empty_group_serialised_as_null(project_dir, runner):
    """Neighbour at codex root (no subdir) -> JSON 'group' is null."""
    _write_codex_doc(project_dir, "seed", related=["root-neighbour"])
    _write_codex_doc(project_dir, "root-neighbour", related=[])  # no subdir

    result = runner.invoke(main, ["--json", "codex", "map", "seed"])

    assert result.exit_code == 0, result.stderr
    parsed = json.loads(result.stdout)
    rn = next((e for e in parsed["codex"] if e["id"] == "root-neighbour"), None)
    assert rn is not None
    assert rn["group"] is None


# E2E — Default --json unknown seed -> error envelope to stderr.
# eager-impl from G1/G2; locking in
def test_codex_map_default_json_unknown_seed_error_envelope(project_dir):
    """`lore --json codex map nope` -> exit non-zero, stderr {'error': ...}."""
    proc = subprocess.run(
        [
            sys.executable, "-c", "from lore.cli import main; main()",
            "--json", "codex", "map", "does-not-exist",
        ],
        capture_output=True, text=True, cwd=str(project_dir),
    )
    assert proc.returncode != 0
    payload = json.loads(proc.stderr.strip())
    assert payload == {"error": 'Document "does-not-exist" not found'}


# ===========================================================================
# US-007 — Full-mode JSON envelope keyed on `documents` (E2E)
# ===========================================================================


# E2E — Scenario 1: --full --json envelope is 'documents' with six-key entry.
# eager-impl from G1/G2; locking in
def test_codex_map_full_json_envelope_is_documents_with_body(project_dir, runner):
    """child-a at foo/bar/ with title 'Child A', summary 'Child A summary.',
    related:['other'], body 'Body content of child-a.'.
    --full --depth 1 -> envelope key 'documents' with one full six-key entry.
    """
    _write_codex_doc(project_dir, "seed", related=["child-a"])
    _write_codex_doc(
        project_dir,
        "child-a",
        related=["other"],
        subdir="foo/bar",
        title="Child A",
        summary="Child A summary.",
        body="Body content of child-a.",
    )
    _write_codex_doc(project_dir, "other", related=[])

    result = runner.invoke(
        main, ["--json", "codex", "map", "seed", "--full", "--depth", "1"]
    )

    assert result.exit_code == 0, result.stderr
    parsed = json.loads(result.stdout)
    assert set(parsed.keys()) == {"documents"}
    # depth 1 outbound from seed -> only child-a (other is at depth 2).
    child_entry = next((e for e in parsed["documents"] if e["id"] == "child-a"), None)
    assert child_entry is not None
    assert set(child_entry.keys()) == {
        "id", "title", "summary", "group", "related", "body",
    }
    assert child_entry["id"] == "child-a"
    assert child_entry["title"] == "Child A"
    assert child_entry["summary"] == "Child A summary."
    assert child_entry["group"] == "foo/bar"
    assert child_entry["related"] == ["other"]
    assert "Body content of child-a." in child_entry["body"]
    # Seed absent.
    assert not any(e["id"] == "seed" for e in parsed["documents"])


# E2E — Scenario 2: Empty under --full --json -> {"documents": []}.
# eager-impl from G1/G2; locking in
def test_codex_map_full_json_empty_neighbourhood(project_dir, runner):
    """Isolated seed under --full --json -> {'documents': []}, exit 0, stderr empty."""
    _write_codex_doc(project_dir, "seed", related=[])

    result = runner.invoke(main, ["--json", "codex", "map", "seed", "--full"])

    assert result.exit_code == 0, result.stderr
    parsed = json.loads(result.stdout)
    assert parsed == {"documents": []}
    assert result.stderr == ""


# E2E — Scenario 3: --full --json deduped + alphabetical.
# eager-impl from G1/G2; locking in
def test_codex_map_full_json_sorted_and_deduped(project_dir, runner):
    """seed <-> shared mutual; seed -> apple outbound.
    --full --depth 1 -> ids ['apple', 'shared'] in order, shared once, seed absent.
    """
    _write_codex_doc(project_dir, "seed", related=["shared", "apple"])
    _write_codex_doc(project_dir, "shared", related=["seed"])
    _write_codex_doc(project_dir, "apple", related=[])

    result = runner.invoke(
        main, ["--json", "codex", "map", "seed", "--full", "--depth", "1"]
    )

    assert result.exit_code == 0, result.stderr
    parsed = json.loads(result.stdout)
    ids = [e["id"] for e in parsed["documents"]]
    assert ids == ["apple", "shared"]
    assert ids.count("shared") == 1
    assert "seed" not in ids


# E2E — Scenario 4: --full --json composes with --depth-out.
# eager-impl from G1/G2; locking in
def test_codex_map_full_json_composes_with_depth_out(project_dir, runner):
    """seed -> a outbound; parent-x -> seed inbound.
    --full --depth-out 1 -> documents has only id='a', no parent-x.
    """
    _write_codex_doc(project_dir, "seed", related=["a"])
    _write_codex_doc(project_dir, "a", related=[], body="Body of a.")
    _write_codex_doc(project_dir, "parent-x", related=["seed"], body="Body of parent-x.")

    result = runner.invoke(
        main, ["--json", "codex", "map", "seed", "--full", "--depth-out", "1"]
    )

    assert result.exit_code == 0, result.stderr
    parsed = json.loads(result.stdout)
    ids = [e["id"] for e in parsed["documents"]]
    assert ids == ["a"]
    assert "parent-x" not in ids
    assert "seed" not in ids


# E2E — --full --json unknown seed -> error envelope.
# eager-impl from G1/G2; locking in
def test_codex_map_full_json_unknown_seed_error_envelope(project_dir):
    """`lore --json codex map nope --full` -> exit non-zero, stderr {'error': ...}."""
    proc = subprocess.run(
        [
            sys.executable, "-c", "from lore.cli import main; main()",
            "--json", "codex", "map", "does-not-exist", "--full",
        ],
        capture_output=True, text=True, cwd=str(project_dir),
    )
    assert proc.returncode != 0
    payload = json.loads(proc.stderr.strip())
    assert payload == {"error": 'Document "does-not-exist" not found'}
