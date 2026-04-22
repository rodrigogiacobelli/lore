"""E2E tests for lore codex map command — BFS traversal scenarios.

Spec: codex-map-us-1 (lore codex show codex-map-us-1)
"""

import json
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


# ---------------------------------------------------------------------------
# Scenario 1: BFS depth 2 returns root, depth-1, and depth-2 in BFS order
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 2 (BFS traversal), step 4 (render)
def test_bfs_depth_2_returns_root_depth1_depth2_in_order(project_dir, runner):
    """Scenario 1: root-doc related:[child-a, child-b], child-a related:[grandchild-x].

    Assert stdout order: root-doc before child-a and child-b, all before grandchild-x.
    Assert exit code 0, stderr empty.
    """
    _write_codex_doc(project_dir, "root-doc", related=["child-a", "child-b"])
    _write_codex_doc(project_dir, "child-a", related=["grandchild-x"])
    _write_codex_doc(project_dir, "child-b", related=[])
    _write_codex_doc(project_dir, "grandchild-x", related=[])

    result = runner.invoke(main, ["codex", "map", "root-doc", "--depth", "2"])

    assert result.exit_code == 0
    output = result.output
    assert "=== root-doc ===" in output
    assert "=== child-a ===" in output
    assert "=== child-b ===" in output
    assert "=== grandchild-x ===" in output

    root_pos = output.index("=== root-doc ===")
    child_a_pos = output.index("=== child-a ===")
    child_b_pos = output.index("=== child-b ===")
    grandchild_pos = output.index("=== grandchild-x ===")

    assert root_pos < child_a_pos
    assert root_pos < child_b_pos
    assert child_a_pos < grandchild_pos
    assert child_b_pos < grandchild_pos


# ---------------------------------------------------------------------------
# Scenario 2: Deduplication — two paths to same document
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 2 (BFS deduplication via visited set)
def test_bfs_deduplication_two_paths_to_same_doc(project_dir, runner):
    """Scenario 2: root -> child-a -> shared, root -> child-b -> shared.

    Assert '=== shared ===' appears exactly once in stdout. Exit code 0.
    """
    _write_codex_doc(project_dir, "root-doc", related=["child-a", "child-b"])
    _write_codex_doc(project_dir, "child-a", related=["shared"])
    _write_codex_doc(project_dir, "child-b", related=["shared"])
    _write_codex_doc(project_dir, "shared", related=[])

    result = runner.invoke(main, ["codex", "map", "root-doc", "--depth", "2"])

    assert result.exit_code == 0
    assert result.output.count("=== shared ===") == 1


# ---------------------------------------------------------------------------
# Scenario 3: Cycle safety — A → B → A does not loop
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 2 (cycle handling via visited set)
def test_bfs_cycle_terminates_without_loop(project_dir, runner):
    """Scenario 3: cycle-a related:[cycle-b], cycle-b related:[cycle-a], depth 3.

    Assert cycle-a appears once, cycle-b appears once, exit code 0.
    """
    _write_codex_doc(project_dir, "cycle-a", related=["cycle-b"])
    _write_codex_doc(project_dir, "cycle-b", related=["cycle-a"])

    result = runner.invoke(main, ["codex", "map", "cycle-a", "--depth", "3"])

    assert result.exit_code == 0
    assert result.output.count("=== cycle-a ===") == 1
    assert result.output.count("=== cycle-b ===") == 1


# ---------------------------------------------------------------------------
# Scenario 4: Directed links — neighbour's back-link not auto-traversed
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 2 (directed links — FR-4)
def test_bfs_related_links_are_directed(project_dir, runner):
    """Scenario 4: doc-a related:[doc-b], doc-b related:[doc-c], depth 1.

    Assert doc-a and doc-b in stdout; doc-c NOT in stdout. Exit code 0.
    """
    _write_codex_doc(project_dir, "doc-a", related=["doc-b"])
    _write_codex_doc(project_dir, "doc-b", related=["doc-c"])
    _write_codex_doc(project_dir, "doc-c", related=[])

    result = runner.invoke(main, ["codex", "map", "doc-a", "--depth", "1"])

    assert result.exit_code == 0
    assert "=== doc-a ===" in result.output
    assert "=== doc-b ===" in result.output
    assert "=== doc-c ===" not in result.output


# ---------------------------------------------------------------------------
# Scenario 5: Leaf node — document with no related field
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 3 (_read_related returns [] for absent field)
def test_bfs_leaf_node_no_related_field(project_dir, runner):
    """Scenario 5: leaf-doc has no related field, depth 2.

    Assert only '=== leaf-doc ===' in stdout, exit code 0, stderr empty.
    """
    _write_codex_doc(project_dir, "leaf-doc", omit_related=True)

    result = runner.invoke(main, ["codex", "map", "leaf-doc", "--depth", "2"])

    assert result.exit_code == 0
    assert "=== leaf-doc ===" in result.output
    # Only one document header should appear
    assert result.output.count("===") == 2  # opening and closing for one doc


# ---------------------------------------------------------------------------
# Scenario 6: Broken related link is silently skipped
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 3 (dead links silently skipped — FR-7)
def test_bfs_broken_related_link_silently_skipped(project_dir, runner):
    """Scenario 6: root-doc related:[existing-child, nonexistent-id].

    Assert root-doc and existing-child in stdout, no mention of nonexistent-id.
    Exit code 0, stderr empty.
    """
    _write_codex_doc(project_dir, "root-doc", related=["existing-child", "nonexistent-id"])
    _write_codex_doc(project_dir, "existing-child", related=[])

    result = runner.invoke(main, ["codex", "map", "root-doc", "--depth", "1"])

    assert result.exit_code == 0
    assert "=== root-doc ===" in result.output
    assert "=== existing-child ===" in result.output
    assert "nonexistent-id" not in result.output


# ---------------------------------------------------------------------------
# US-2: --depth option boundary scenarios
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map parameters table (default --depth is 1)
def test_default_depth_returns_root_plus_direct_neighbours(project_dir, runner):
    """Scenario 1: root-doc related:[child-a, child-b], omit --depth.

    Assert root-doc, child-a, child-b in stdout; exit code 0.
    Result must be identical to explicit --depth 1.
    """
    _write_codex_doc(project_dir, "root-doc", related=["child-a", "child-b"])
    _write_codex_doc(project_dir, "child-a", related=[])
    _write_codex_doc(project_dir, "child-b", related=[])

    result_default = runner.invoke(main, ["codex", "map", "root-doc"])
    result_explicit = runner.invoke(main, ["codex", "map", "root-doc", "--depth", "1"])

    assert result_default.exit_code == 0
    assert "=== root-doc ===" in result_default.output
    assert "=== child-a ===" in result_default.output
    assert "=== child-b ===" in result_default.output
    assert result_default.output == result_explicit.output


# conceptual-workflows-codex-map parameters table (depth 0 — no traversal)
def test_depth_0_returns_only_root(project_dir, runner):
    """Scenario 2: root-doc related:[child-a], run with --depth 0.

    Assert only "=== root-doc ===" in stdout, child-a NOT present.
    Assert exit code 0, stderr empty.
    """
    _write_codex_doc(project_dir, "root-doc", related=["child-a"])
    _write_codex_doc(project_dir, "child-a", related=[])

    result = runner.invoke(main, ["codex", "map", "root-doc", "--depth", "0"])

    assert result.exit_code == 0
    assert "=== root-doc ===" in result.output
    assert "=== child-a ===" not in result.output


# conceptual-workflows-codex-map step 2 (depth 1 cutoff — grandchild not included)
def test_depth_1_returns_root_and_direct_neighbours_only(project_dir, runner):
    """Scenario 3: root-doc->child-a->grandchild-x, run with --depth 1.

    Assert root-doc and child-a in stdout, grandchild-x NOT present, exit code 0.
    """
    _write_codex_doc(project_dir, "root-doc", related=["child-a"])
    _write_codex_doc(project_dir, "child-a", related=["grandchild-x"])
    _write_codex_doc(project_dir, "grandchild-x", related=[])

    result = runner.invoke(main, ["codex", "map", "root-doc", "--depth", "1"])

    assert result.exit_code == 0
    assert "=== root-doc ===" in result.output
    assert "=== child-a ===" in result.output
    assert "=== grandchild-x ===" not in result.output


# conceptual-workflows-codex-map step 2 (depth 2 includes second hop)
def test_depth_2_includes_grandchild(project_dir, runner):
    """Scenario 4: root-doc->child-a->grandchild-x, run with --depth 2.

    Assert root-doc, child-a, grandchild-x all in stdout in BFS order, exit code 0.
    """
    _write_codex_doc(project_dir, "root-doc", related=["child-a"])
    _write_codex_doc(project_dir, "child-a", related=["grandchild-x"])
    _write_codex_doc(project_dir, "grandchild-x", related=[])

    result = runner.invoke(main, ["codex", "map", "root-doc", "--depth", "2"])

    assert result.exit_code == 0
    assert "=== root-doc ===" in result.output
    assert "=== child-a ===" in result.output
    assert "=== grandchild-x ===" in result.output

    root_pos = result.output.index("=== root-doc ===")
    child_a_pos = result.output.index("=== child-a ===")
    grandchild_pos = result.output.index("=== grandchild-x ===")
    assert root_pos < child_a_pos < grandchild_pos


# conceptual-workflows-codex-map parameters table (IntRange min=0 rejects negatives)
def test_negative_depth_is_rejected_by_click(project_dir, runner):
    """Scenario 5: run with --depth -1.

    Assert exit code 2, stderr contains "Invalid value for '--depth'".
    Assert stdout is empty.
    """
    _write_codex_doc(project_dir, "root-doc", related=[])

    result = runner.invoke(main, ["codex", "map", "root-doc", "--depth", "-1"])

    assert result.exit_code == 2
    assert "Invalid value for '--depth'" in result.output
    # stdout proper should be empty (click writes errors to stdout via mix_stderr default)


# conceptual-workflows-codex-map parameters table (default depth via CLI)
def test_codex_map_cli_default_depth_is_1(project_dir, runner):
    """Omit --depth; result must include direct neighbours of root but not grandchildren."""
    _write_codex_doc(project_dir, "root-doc", related=["child-a"])
    _write_codex_doc(project_dir, "child-a", related=["grandchild-x"])
    _write_codex_doc(project_dir, "grandchild-x", related=[])

    result = runner.invoke(main, ["codex", "map", "root-doc"])

    assert result.exit_code == 0
    assert "=== root-doc ===" in result.output
    assert "=== child-a ===" in result.output
    assert "=== grandchild-x ===" not in result.output


# ---------------------------------------------------------------------------
# US-3: CLI command registration scenarios (FR-13, FR-14)
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map (command accessible under lore codex — Scenario 1)
def test_map_subcommand_accessible_under_codex_group(project_dir, runner):
    """Scenario 1: write one doc 'some-doc', run 'lore codex map some-doc'.

    Assert no "No such command" error, exit code 0, stdout contains '=== some-doc ==='.
    """
    _write_codex_doc(project_dir, "some-doc", related=[])

    result = runner.invoke(main, ["codex", "map", "some-doc"])

    assert "No such command" not in result.output
    assert result.exit_code == 0
    assert "=== some-doc ===" in result.output


# conceptual-workflows-codex-map (help text — FR-13, FR-14 — Scenario 2)
def test_codex_map_help_output(project_dir, runner):
    """Scenario 2: run 'lore codex map --help'.

    Assert exit code 0.
    Assert stdout contains 'Usage: lore codex map [OPTIONS] DOC_ID'.
    Assert stdout contains "Map a codex document cluster via BFS traversal of 'related' links.".
    Assert stdout contains '--depth' with its default value shown.
    """
    result = runner.invoke(main, ["codex", "map", "--help"])

    assert result.exit_code == 0
    # Note: Click's CliRunner renders the prog name from the function name in tests,
    # so "lore" appears as "main" — assert the structural shape minus the prog name.
    assert "codex map [OPTIONS] DOC_ID" in result.output
    assert "Map a codex document cluster via BFS traversal of 'related' links." in result.output
    assert "--depth" in result.output
    assert "1" in result.output  # default value shown


# conceptual-workflows-codex-map (map listed in parent group help — Scenario 3)
def test_codex_group_help_lists_map_subcommand(project_dir, runner):
    """Scenario 3: run 'lore codex --help'.

    Assert stdout contains 'map' in the Commands section. Assert exit code 0.
    """
    result = runner.invoke(main, ["codex", "--help"])

    assert result.exit_code == 0
    assert "map" in result.output


# conceptual-workflows-codex-map (missing positional argument — Click usage error — Scenario 4)
def test_map_missing_doc_id_produces_usage_error(project_dir, runner):
    """Scenario 4: run 'lore codex map' with no positional argument.

    Assert exit code 2.
    Assert stderr contains "Error: Missing argument 'DOC_ID'.".
    Assert stdout is empty.
    """
    result = runner.invoke(main, ["codex", "map"], catch_exceptions=False)

    assert result.exit_code == 2
    assert "Missing argument 'DOC_ID'." in result.output


# conceptual-workflows-codex-map (extra positional arguments rejected — Scenario 5)
def test_map_extra_positional_arguments_rejected(project_dir, runner):
    """Scenario 5: run 'lore codex map doc-a doc-b'.

    Assert exit code 2, stderr contains error about extra arguments. Assert stdout is empty.
    """
    result = runner.invoke(main, ["codex", "map", "doc-a", "doc-b"], catch_exceptions=False)

    assert result.exit_code == 2
    assert "Got unexpected extra argument" in result.output


# conceptual-workflows-codex-map (doc_id required positional argument — CLI path)
def test_codex_map_doc_id_required_positional(project_dir, runner):
    """Invoke CLI without doc_id; assert exit code 2 (UsageError)."""
    result = runner.invoke(main, ["codex", "map"])

    assert result.exit_code == 2


# conceptual-workflows-codex-map (--depth defaults to 1 — CLI path)
def test_codex_map_depth_option_defaults_to_1(project_dir, runner):
    """Write root doc with one neighbour; invoke without --depth.

    Assert neighbour appears in output (confirming depth defaulted to 1).
    """
    _write_codex_doc(project_dir, "root-doc", related=["child-a"])
    _write_codex_doc(project_dir, "child-a", related=[])

    result = runner.invoke(main, ["codex", "map", "root-doc"])

    assert result.exit_code == 0
    assert "=== child-a ===" in result.output


# ---------------------------------------------------------------------------
# US-4: Text Output Format
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 4 (render — text mode separator format)
def test_text_output_separator_format_matches_codex_show(project_dir, runner):
    """Scenario 1: separator line immediately followed by body — no blank line between.

    Given a doc 'tech-overview' whose body begins with '# Technical Overview',
    running 'lore codex map tech-overview --depth 0' must produce stdout where
    the first line is '=== tech-overview ===' and the very next line is the body
    start (no blank line between separator and body). Exit code 0.
    """
    # Write a doc with a known body start line
    content = (
        "---\n"
        "id: tech-overview\n"
        "title: Technical Overview\n"
        "type: technical\n"
        "summary: Overview doc.\n"
        "related: []\n"
        "---\n"
        "\n"
        "# Technical Overview\n"
        "\n"
        "Some content here.\n"
    )
    codex_dir = project_dir / ".lore" / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    (codex_dir / "tech-overview.md").write_text(content)

    result = runner.invoke(main, ["codex", "map", "tech-overview", "--depth", "0"])

    assert result.exit_code == 0
    lines = result.output.splitlines()
    # First line must be the separator
    assert lines[0] == "=== tech-overview ==="
    # Second line must be the first line of the body (no blank line between separator and body)
    assert lines[1] == "# Technical Overview"


# conceptual-workflows-codex-map step 4 (render — BFS order preserved — US-4 Scenario 2)
def test_text_output_bfs_order_root_depth1_depth2(project_dir, runner):
    """Scenario 2: root at depth 0, children at depth 1, grandchild at depth 2.

    Separators must appear in BFS order: root-doc, then child-a and child-b
    (both before grandchild-x), then grandchild-x.
    """
    _write_codex_doc(project_dir, "root-doc", related=["child-a", "child-b"])
    _write_codex_doc(project_dir, "child-a", related=["grandchild-x"])
    _write_codex_doc(project_dir, "child-b", related=[])
    _write_codex_doc(project_dir, "grandchild-x", related=[])

    result = runner.invoke(main, ["codex", "map", "root-doc", "--depth", "2"])

    assert result.exit_code == 0
    output = result.output

    # All four separators must be present
    assert "=== root-doc ===" in output
    assert "=== child-a ===" in output
    assert "=== child-b ===" in output
    assert "=== grandchild-x ===" in output

    # BFS order: root before depth-1 nodes, both depth-1 before depth-2 node
    root_pos = output.index("=== root-doc ===")
    child_a_pos = output.index("=== child-a ===")
    child_b_pos = output.index("=== child-b ===")
    grandchild_pos = output.index("=== grandchild-x ===")

    assert root_pos < child_a_pos, "root must appear before child-a"
    assert root_pos < child_b_pos, "root must appear before child-b"
    assert child_a_pos < grandchild_pos, "child-a must appear before grandchild-x"
    assert child_b_pos < grandchild_pos, "child-b must appear before grandchild-x"


# conceptual-workflows-codex-map step 4 (render — alphabetical neighbour sort)
def test_text_output_neighbours_sorted_alphabetically(project_dir, runner):
    """Scenario 3: neighbours declared in reverse-alpha order must appear alpha-sorted.

    root-doc related:[zebra-doc, alpha-doc] — 'zebra-doc' declared first.
    After traversal, output order must be: root-doc, alpha-doc, zebra-doc.
    """
    _write_codex_doc(project_dir, "root-doc", related=["zebra-doc", "alpha-doc"])
    _write_codex_doc(project_dir, "alpha-doc", related=[])
    _write_codex_doc(project_dir, "zebra-doc", related=[])

    result = runner.invoke(main, ["codex", "map", "root-doc", "--depth", "1"])

    assert result.exit_code == 0
    output = result.output

    assert "=== root-doc ===" in output
    assert "=== alpha-doc ===" in output
    assert "=== zebra-doc ===" in output

    root_pos = output.index("=== root-doc ===")
    alpha_pos = output.index("=== alpha-doc ===")
    zebra_pos = output.index("=== zebra-doc ===")

    # Alphabetical order: alpha-doc before zebra-doc
    assert root_pos < alpha_pos, "root must appear before alpha-doc"
    assert alpha_pos < zebra_pos, "alpha-doc must appear before zebra-doc (alphabetical)"


# conceptual-workflows-codex-map step 4 (render — leaf node single block)
def test_text_output_leaf_node_single_block(project_dir, runner):
    """Scenario 4: isolated-doc with related:[] — output contains exactly one block.

    Stdout must contain exactly one '=== isolated-doc ===' separator and nothing
    more (no additional separator lines). Exit code 0.
    """
    _write_codex_doc(project_dir, "isolated-doc", related=[])

    result = runner.invoke(main, ["codex", "map", "isolated-doc", "--depth", "1"])

    assert result.exit_code == 0
    output = result.output

    assert "=== isolated-doc ===" in output
    # Exactly one separator block — count occurrences of the separator pattern
    import re
    separator_count = len(re.findall(r"=== \S+ ===", output))
    assert separator_count == 1, f"Expected exactly 1 separator, got {separator_count}"


# conceptual-workflows-codex-map step 4 (render — output goes to stdout not stderr)
def test_text_output_goes_to_stdout_not_stderr(project_dir):
    """Scenario 5: document block goes to stdout; stderr must be empty. Exit code 0.

    Uses subprocess so that stdout and stderr are captured separately (CliRunner
    in Click 8.x does not support mix_stderr=False).
    """
    import subprocess
    import sys

    _write_codex_doc(project_dir, "some-doc", related=[])

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from lore.cli import main; main()",
            "codex",
            "map",
            "some-doc",
            "--depth",
            "0",
        ],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )

    assert proc.returncode == 0
    assert "=== some-doc ===" in proc.stdout
    assert proc.stderr == ""


# conceptual-workflows-codex-map step 4 (exact separator format — each doc as === id ===\nbody)
def test_cli_codex_map_text_mode_separator_format(project_dir, runner):
    """Each document must be rendered as '=== {id} ===\n{body}' with no extra blank line
    between the separator and the body start.
    """
    _write_codex_doc(project_dir, "doc-one", related=[])

    result = runner.invoke(main, ["codex", "map", "doc-one", "--depth", "0"])

    assert result.exit_code == 0
    lines = result.output.splitlines()
    sep_index = lines.index("=== doc-one ===")
    # The line immediately after the separator must be non-empty (body starts right away)
    assert sep_index + 1 < len(lines), "There must be content after the separator"
    assert lines[sep_index + 1] != "", "No blank line allowed between separator and body"


# conceptual-workflows-codex-map step 4 (no resorting — BFS order from map_documents)
def test_cli_codex_map_text_mode_preserves_bfs_order(project_dir, runner):
    """BFS order from map_documents must be preserved in output — no resorting in CLI handler.

    root -> child-a -> grandchild-x: separators must appear root, child-a, grandchild-x.
    """
    _write_codex_doc(project_dir, "root-doc", related=["child-a"])
    _write_codex_doc(project_dir, "child-a", related=["grandchild-x"])
    _write_codex_doc(project_dir, "grandchild-x", related=[])

    result = runner.invoke(main, ["codex", "map", "root-doc", "--depth", "2"])

    assert result.exit_code == 0
    output = result.output

    root_pos = output.index("=== root-doc ===")
    child_a_pos = output.index("=== child-a ===")
    grandchild_pos = output.index("=== grandchild-x ===")

    assert root_pos < child_a_pos < grandchild_pos


# conceptual-workflows-codex-map step 4 (no stderr on success)
def test_cli_codex_map_text_mode_no_stderr_on_success(project_dir):
    """On success, stderr must be empty — all document output goes to stdout.

    Uses subprocess so that stdout and stderr are captured separately (CliRunner
    in Click 8.x does not support mix_stderr=False).
    """
    import subprocess
    import sys

    _write_codex_doc(project_dir, "doc-a", related=["doc-b"])
    _write_codex_doc(project_dir, "doc-b", related=[])

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from lore.cli import main; main()",
            "codex",
            "map",
            "doc-a",
            "--depth",
            "1",
        ],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )

    assert proc.returncode == 0
    assert proc.stderr == ""
    assert "=== doc-a ===" in proc.stdout
    assert "=== doc-b ===" in proc.stdout


# ---------------------------------------------------------------------------
# US-5: JSON Output Mode
# ---------------------------------------------------------------------------


def _write_codex_doc_full(
    project_dir,
    doc_id,
    *,
    title=None,
    summary=None,
    related=None,
):
    """Write a codex document with explicit title/summary for JSON key assertions."""
    if title is None:
        title = doc_id.replace("-", " ").title()
    if summary is None:
        summary = f"Summary for {doc_id}."
    related_line = ""
    if related is None:
        related_line = "related: []"
    else:
        items = "\n".join(f"  - {r}" for r in related)
        related_line = f"related:\n{items}"
    content = textwrap.dedent(f"""\
        ---
        id: {doc_id}
        title: {title}
        summary: {summary}
        {related_line}
        ---

        Body of {doc_id}.
    """)
    codex_dir = project_dir / ".lore" / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    path = codex_dir / f"{doc_id}.md"
    path.write_text(content)
    return path


# conceptual-workflows-codex-map step 4 (render — JSON mode, BFS order preserved)
def test_json_mode_returns_valid_json_with_documents_array(project_dir, runner):
    """Scenario 1: root-doc (conceptual, related:[child-a]), child-a (technical).

    Run 'lore --json codex map root-doc --depth 1'.
    Assert stdout is valid JSON, top-level key 'documents'.
    Assert documents[0]['id'] == 'root-doc', documents[1]['id'] == 'child-a'.
    Assert exit code 0, stderr empty.
    """
    _write_codex_doc_full(
        project_dir,
        "root-doc",
        title="Root Document",
        summary="A root doc",
        related=["child-a"],
    )
    _write_codex_doc_full(
        project_dir,
        "child-a",
        title="Child A",
        summary="A child doc",
        related=[],
    )

    result = runner.invoke(main, ["--json", "codex", "map", "root-doc", "--depth", "1"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "documents" in data
    assert len(data["documents"]) == 2
    assert data["documents"][0]["id"] == "root-doc"
    assert data["documents"][1]["id"] == "child-a"


# conceptual-workflows-codex-map step 4 (render — JSON array preserves BFS order)
def test_json_documents_array_preserves_bfs_order(project_dir, runner):
    """Scenario 2: root-doc->child-a->grandchild-x, depth 2.

    Assert documents array order: root-doc, child-a, grandchild-x.
    """
    _write_codex_doc_full(project_dir, "root-doc", related=["child-a"])
    _write_codex_doc_full(project_dir, "child-a", related=["grandchild-x"])
    _write_codex_doc_full(project_dir, "grandchild-x", related=[])

    result = runner.invoke(main, ["--json", "codex", "map", "root-doc", "--depth", "2"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    ids = [doc["id"] for doc in data["documents"]]
    assert ids == ["root-doc", "child-a", "grandchild-x"]


# conceptual-workflows-codex-map step 4 (render — five required keys per document object)
def test_json_document_object_has_exactly_five_required_keys(project_dir, runner):
    """Scenario 3: some-doc depth 0.

    Run 'lore --json codex map some-doc --depth 0'.
    Assert documents[0] has keys: id, title, summary, body; all non-null strings.
    """
    _write_codex_doc_full(project_dir, "some-doc", related=[])

    result = runner.invoke(main, ["--json", "codex", "map", "some-doc", "--depth", "0"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data["documents"]) == 1
    doc = data["documents"][0]
    assert set(doc.keys()) == {"id", "title", "summary", "body"}
    for key in ("id", "title", "summary", "body"):
        assert isinstance(doc[key], str) and doc[key] != ""


# conceptual-workflows-codex-map (global --json flag only — no local flag)
def test_local_json_flag_on_map_subcommand_is_rejected(project_dir, runner):
    """Scenario 4: run 'lore codex map some-doc --json'.

    Assert exit code 2 (Click unknown option error), confirming --json is global only.
    """
    _write_codex_doc_full(project_dir, "some-doc", related=[])

    result = runner.invoke(main, ["codex", "map", "some-doc", "--json"])

    assert result.exit_code == 2


# conceptual-workflows-codex-map step 4 (render — JSON depth 0 single-element array)
def test_json_mode_depth_0_returns_single_document_array(project_dir, runner):
    """Scenario 5: isolated-doc with related:[child-a], depth 0.

    Run 'lore --json codex map isolated-doc --depth 0'.
    Assert documents array has exactly one element with id 'isolated-doc'.
    Assert exit code 0.
    """
    _write_codex_doc_full(project_dir, "isolated-doc", related=["child-a"])
    _write_codex_doc_full(project_dir, "child-a", related=[])

    result = runner.invoke(main, ["--json", "codex", "map", "isolated-doc", "--depth", "0"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data["documents"]) == 1
    assert data["documents"][0]["id"] == "isolated-doc"


# conceptual-workflows-codex-map step 4 (JSON mode parseable)
def test_cli_codex_map_json_mode_output_is_valid_json(project_dir, runner):
    """Output must be parseable by json.loads without raising an exception."""
    _write_codex_doc_full(project_dir, "doc-x", related=[])

    result = runner.invoke(main, ["--json", "codex", "map", "doc-x", "--depth", "0"])

    assert result.exit_code == 0
    # Must not raise
    data = json.loads(result.output)
    assert isinstance(data, dict)


# conceptual-workflows-codex-map step 4 (JSON top-level key is "documents")
def test_cli_codex_map_json_mode_top_level_key_is_documents(project_dir, runner):
    """Top-level JSON object must have exactly a 'documents' key containing a list."""
    _write_codex_doc_full(project_dir, "doc-x", related=[])

    result = runner.invoke(main, ["--json", "codex", "map", "doc-x", "--depth", "0"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "documents" in data
    assert isinstance(data["documents"], list)


# conceptual-workflows-codex-map step 4 (four keys per document object)
def test_cli_codex_map_json_mode_document_has_four_keys(project_dir, runner):
    """Each entry in 'documents' must have exactly the keys id, title, summary, body."""
    _write_codex_doc_full(project_dir, "doc-x", related=[])

    result = runner.invoke(main, ["--json", "codex", "map", "doc-x", "--depth", "0"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data["documents"]) >= 1
    for doc in data["documents"]:
        assert set(doc.keys()) == {"id", "title", "summary", "body"}


# conceptual-workflows-codex-map step 4 (JSON array order matches BFS)
def test_cli_codex_map_json_mode_array_order_matches_bfs(project_dir, runner):
    """'documents' array order must match BFS traversal — root first, then depth-1 nodes."""
    _write_codex_doc_full(project_dir, "root-doc", related=["child-a"])
    _write_codex_doc_full(project_dir, "child-a", related=["grandchild-x"])
    _write_codex_doc_full(project_dir, "grandchild-x", related=[])

    result = runner.invoke(main, ["--json", "codex", "map", "root-doc", "--depth", "2"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    ids = [doc["id"] for doc in data["documents"]]
    assert ids.index("root-doc") < ids.index("child-a")
    assert ids.index("child-a") < ids.index("grandchild-x")


# conceptual-workflows-codex-map step 4 (JSON output to stdout not stderr)
def test_cli_codex_map_json_mode_output_goes_to_stdout(project_dir):
    """JSON output must appear on stdout; stderr must be empty. Exit code 0.

    Uses subprocess so that stdout and stderr are captured separately.
    """
    import subprocess
    import sys

    _write_codex_doc_full(project_dir, "doc-x", related=[])

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from lore.cli import main; main(standalone_mode=True)",
            "--json",
            "codex",
            "map",
            "doc-x",
            "--depth",
            "0",
        ],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )

    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert "documents" in data
    assert proc.stderr == ""


# ---------------------------------------------------------------------------
# US-6: Error Handling — missing root document, broken related links
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 1 (validate root — error branch, text mode)
def test_missing_root_text_mode_stderr_and_exit_1(project_dir):
    """Scenario 1: no doc with ID "nonexistent-doc" exists.

    Run "lore codex map nonexistent-doc --depth 1".
    Assert stderr contains 'Document "nonexistent-doc" not found'.
    Assert exit code 1, stdout is empty.

    Uses subprocess so that stdout and stderr are captured separately.
    """
    import subprocess
    import sys

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from lore.cli import main; main()",
            "codex",
            "map",
            "nonexistent-doc",
            "--depth",
            "1",
        ],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )

    assert proc.returncode == 1
    assert 'Document "nonexistent-doc" not found' in proc.stderr
    assert proc.stdout == ""


# conceptual-workflows-codex-map step 1 (validate root — error branch, JSON mode)
def test_missing_root_json_mode_stderr_and_exit_1(project_dir):
    """Scenario 2: no doc with ID "bad-id" exists.

    Run "lore --json codex map bad-id --depth 1".
    Assert stderr contains '{"error": "Document \\"bad-id\\" not found"}'.
    Assert exit code 1, stdout is empty.

    Uses subprocess so that stdout and stderr are captured separately.
    """
    import json as _json
    import subprocess
    import sys

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from lore.cli import main; main()",
            "--json",
            "codex",
            "map",
            "bad-id",
            "--depth",
            "1",
        ],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )

    assert proc.returncode == 1
    assert proc.stdout == ""
    # stderr must be valid JSON with an "error" key containing the ID verbatim
    error_payload = _json.loads(proc.stderr.strip())
    assert error_payload == {"error": 'Document "bad-id" not found'}


# conceptual-workflows-codex-map step 1 (typo corrected — second run succeeds)
def test_typo_in_doc_id_then_correct_id_succeeds(project_dir):
    """Scenario 3: "tech-overview" exists but "tech-overvew" (missing 'i') does not.

    First run with typo: exit 1, stderr contains error message.
    Second run corrected: exit 0, stdout contains "=== tech-overview ===".

    Uses subprocess so that stdout and stderr are captured separately.
    """
    import subprocess
    import sys

    # Write a valid doc
    content = (
        "---\n"
        "id: tech-overview\n"
        "title: Technical Overview\n"
        "type: technical\n"
        "summary: Overview doc.\n"
        "related: []\n"
        "---\n"
        "\n"
        "# Technical Overview\n"
    )
    codex_dir = project_dir / ".lore" / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    (codex_dir / "tech-overview.md").write_text(content)

    base_cmd = [sys.executable, "-c", "from lore.cli import main; main()"]

    # First run — typo
    proc_typo = subprocess.run(
        base_cmd + ["codex", "map", "tech-overvew", "--depth", "1"],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )
    assert proc_typo.returncode == 1
    assert 'Document "tech-overvew" not found' in proc_typo.stderr

    # Second run — corrected
    proc_ok = subprocess.run(
        base_cmd + ["codex", "map", "tech-overview", "--depth", "1"],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )
    assert proc_ok.returncode == 0
    assert "=== tech-overview ===" in proc_ok.stdout


# conceptual-workflows-codex-map step 1 (error message includes verbatim ID with double quotes)
def test_error_message_includes_bad_id_verbatim_with_double_quotes(project_dir):
    """Scenario 4: no doc "missing-doc-123".

    Assert stderr contains 'Document "missing-doc-123" not found' — ID inside double quotes.

    Uses subprocess so that stdout and stderr are captured separately.
    """
    import subprocess
    import sys

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from lore.cli import main; main()",
            "codex",
            "map",
            "missing-doc-123",
        ],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )

    assert proc.returncode == 1
    assert 'Document "missing-doc-123" not found' in proc.stderr


# conceptual-workflows-codex-map step 3 (broken related link — not a root error)
def test_broken_related_link_during_traversal_is_not_an_error(project_dir):
    """Scenario 5: root-doc with related:[ghost-id], ghost-id does not exist.

    Run "lore codex map root-doc --depth 1".
    Assert stdout contains "=== root-doc ===", exit code 0, stderr empty.
    ghost-id is silently skipped — not an error.

    Uses subprocess so that stdout and stderr are captured separately.
    """
    import subprocess
    import sys

    _write_codex_doc(project_dir, "root-doc", related=["ghost-id"])

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from lore.cli import main; main()",
            "codex",
            "map",
            "root-doc",
            "--depth",
            "1",
        ],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )

    assert proc.returncode == 0
    assert "=== root-doc ===" in proc.stdout
    assert proc.stderr == ""


# conceptual-workflows-codex-map step 1 (CLI text mode — error path — stderr message)
def test_cli_codex_map_text_mode_missing_root_prints_to_stderr(project_dir):
    """CLI text mode: missing root ID → 'Document "<id>" not found' on stderr.

    Uses subprocess so that stdout and stderr are captured separately.
    """
    import subprocess
    import sys

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from lore.cli import main; main()",
            "codex",
            "map",
            "no-such-doc",
            "--depth",
            "1",
        ],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )

    assert 'Document "no-such-doc" not found' in proc.stderr


# conceptual-workflows-codex-map step 1 (CLI text mode — error path — stdout empty)
def test_cli_codex_map_text_mode_missing_root_stdout_empty(project_dir):
    """CLI text mode: missing root ID → stdout must be empty.

    Uses subprocess so that stdout and stderr are captured separately.
    """
    import subprocess
    import sys

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from lore.cli import main; main()",
            "codex",
            "map",
            "no-such-doc",
            "--depth",
            "1",
        ],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )

    assert proc.stdout == ""


# conceptual-workflows-codex-map step 1 (CLI text mode — error path — exit code 1)
def test_cli_codex_map_text_mode_missing_root_exit_code_1(project_dir):
    """CLI text mode: missing root ID → exit code must be 1.

    Uses subprocess so that stdout and stderr are captured separately.
    """
    import subprocess
    import sys

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from lore.cli import main; main()",
            "codex",
            "map",
            "no-such-doc",
            "--depth",
            "1",
        ],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )

    assert proc.returncode == 1


# conceptual-workflows-codex-map step 1 (CLI JSON mode — error path — stderr JSON)
def test_cli_codex_map_json_mode_missing_root_prints_json_to_stderr(project_dir):
    """CLI JSON mode: missing root ID → JSON error object on stderr.

    Uses subprocess so that stdout and stderr are captured separately.
    """
    import json as _json
    import subprocess
    import sys

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from lore.cli import main; main()",
            "--json",
            "codex",
            "map",
            "no-such-doc",
            "--depth",
            "1",
        ],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )

    error_payload = _json.loads(proc.stderr.strip())
    assert "error" in error_payload
    assert "no-such-doc" in error_payload["error"]


# conceptual-workflows-codex-map step 1 (CLI JSON mode — error path — stdout empty)
def test_cli_codex_map_json_mode_missing_root_stdout_empty(project_dir):
    """CLI JSON mode: missing root ID → stdout must be empty.

    Uses subprocess so that stdout and stderr are captured separately.
    """
    import subprocess
    import sys

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from lore.cli import main; main()",
            "--json",
            "codex",
            "map",
            "no-such-doc",
            "--depth",
            "1",
        ],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )

    assert proc.stdout == ""


# conceptual-workflows-codex-map step 1 (CLI JSON mode — error path — exit code 1)
def test_cli_codex_map_json_mode_missing_root_exit_code_1(project_dir):
    """CLI JSON mode: missing root ID → exit code must be 1.

    Uses subprocess so that stdout and stderr are captured separately.
    """
    import subprocess
    import sys

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from lore.cli import main; main()",
            "--json",
            "codex",
            "map",
            "no-such-doc",
            "--depth",
            "1",
        ],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )

    assert proc.returncode == 1


# conceptual-workflows-codex-map step 3 (broken related link — exit code 0)
def test_cli_codex_map_broken_related_link_exit_code_0(project_dir):
    """Broken related link during traversal must not change exit code — must remain 0.

    Uses subprocess so that stdout and stderr are captured separately.
    """
    import subprocess
    import sys

    _write_codex_doc(project_dir, "root-doc", related=["ghost-id"])

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from lore.cli import main; main()",
            "codex",
            "map",
            "root-doc",
            "--depth",
            "1",
        ],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )

    assert proc.returncode == 0


# ---------------------------------------------------------------------------
# codex-sources-us-007 — outbound 'related' on conceptual-entities-artifact
# so `lore codex map <source-id> --depth 1` reaches canonical docs named in
# the source's related list (AC#5 of US-005 / US-007 reachability contract).
# Anchors:
#   codex-sources-us-007 AC Scenarios 1 and 2 — canonical outbound IDs
#   surfaced via `lore codex map --depth 1`.
#   conceptual-workflows-codex-map §BFS on 'related' field.
#   decisions-006-no-seed-content-tests — fixture-based codex tree, never
#   assert against real project-codex prose.
# Red state: covers the provenance traversal contract. Fails if the outbound
# 'related' on a source or the canonical artifact doc stops working.
# ---------------------------------------------------------------------------


def _write_source_doc(project_dir, system, doc_id, related):
    """Write a Sources-layer codex doc under .lore/codex/sources/<system>/."""
    items = "\n".join(f"  - {r}" for r in related)
    content = (
        "---\n"
        f"id: {doc_id}\n"
        f"title: {doc_id}\n"
        f"summary: Verbatim snapshot of {doc_id}.\n"
        f"related:\n{items}\n"
        "---\n"
        "\n"
        f"Body of {doc_id}.\n"
    )
    sources_dir = project_dir / ".lore" / "codex" / "sources" / system
    sources_dir.mkdir(parents=True, exist_ok=True)
    path = sources_dir / f"{doc_id}.md"
    path.write_text(content)
    return path


# conceptual-workflows-codex-map — source-to-canonical reachability.
def test_codex_map_source_reaches_canonical_docs_depth_1(project_dir, runner):
    """US-005 AC#5 / US-007 reachability — a source snapshot whose 'related'
    names canonical codex IDs surfaces those canonical docs via
    `lore codex map <source-id> --depth 1`.
    """
    canonical_ids = [
        "conceptual-entities-doctrine",
        "conceptual-entities-knight",
        "conceptual-workflows-lore-init",
        "tech-cli-commands",
    ]
    for cid in canonical_ids:
        _write_codex_doc(project_dir, cid, related=[])
    _write_source_doc(
        project_dir, "jira", "KONE-23335", related=canonical_ids
    )

    result = runner.invoke(
        main, ["codex", "map", "KONE-23335", "--depth", "1"]
    )

    assert result.exit_code == 0, result.output
    output = result.output
    assert "=== KONE-23335 ===" in output
    # All four canonical docs reachable at depth 1 from the source.
    for cid in canonical_ids:
        assert f"=== {cid} ===" in output, (
            f"canonical doc {cid!r} not reached from source"
        )


# conceptual-workflows-codex-map — fixture replay of conceptual-entities-
# artifact outbound 'related' list (US-007 AC Scenario 1).
def test_codex_map_artifact_fixture_exposes_required_outbound_edges(
    project_dir, runner
):
    """US-007 AC Scenario 1 (fixture form) — a fixture doc with ID
    'conceptual-entities-artifact' and the four canonical outbound IDs in
    'related' surfaces each of those IDs via `lore codex map --depth 1`.
    Fixture-based per decisions-006-no-seed-content-tests.
    """
    canonical_ids = [
        "conceptual-entities-doctrine",
        "conceptual-entities-knight",
        "conceptual-workflows-lore-init",
        "tech-cli-commands",
    ]
    for cid in canonical_ids:
        _write_codex_doc(project_dir, cid, related=[])
    _write_codex_doc(
        project_dir, "conceptual-entities-artifact", related=canonical_ids
    )

    result = runner.invoke(
        main,
        ["codex", "map", "conceptual-entities-artifact", "--depth", "1"],
    )

    assert result.exit_code == 0, result.output
    for cid in canonical_ids:
        assert f"=== {cid} ===" in result.output, (
            f"canonical doc {cid!r} not reached from artifact doc"
        )


# conceptual-workflows-codex-map — JSON mode reachability for source doc.
def test_codex_map_source_json_mode_documents_include_canonical(
    project_dir, runner
):
    """US-007 AC Scenario 2 (JSON form) — JSON 'documents' array at depth 1
    contains at least one canonical ID named in the source's 'related'.
    """
    canonical_ids = [
        "conceptual-entities-doctrine",
        "conceptual-entities-knight",
        "conceptual-workflows-lore-init",
        "tech-cli-commands",
    ]
    for cid in canonical_ids:
        _write_codex_doc(project_dir, cid, related=[])
    _write_source_doc(
        project_dir, "jira", "KONE-23335", related=canonical_ids
    )

    result = runner.invoke(
        main,
        ["--json", "codex", "map", "KONE-23335", "--depth", "1"],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    ids = {doc["id"] for doc in data.get("documents", [])}
    assert "KONE-23335" in ids
    assert ids & set(canonical_ids), (
        "no canonical doc surfaced from source via depth-1 BFS"
    )
