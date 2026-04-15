"""Unit tests for the codex_list CLI handler.

These tests are written RED-first: they describe the *desired* behaviour
after US-1 is implemented (replacing TYPE with GROUP via _format_table).
Every test must FAIL against the current production code.

Source: codex-list-group-us-1 (Unit Test Scenarios section)
"""

import pytest
from click.testing import CliRunner
from pathlib import Path

from lore.cli import main, _format_table


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner():
    """Return a Click CliRunner."""
    return CliRunner()


@pytest.fixture()
def project_dir(tmp_path, monkeypatch):
    """Initialised lore project with codex documents in both a subdirectory
    and at the root of .lore/codex/ — covers all US-1 acceptance criteria.
    """
    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)

    # Document at root of .lore/codex/ (GROUP should be empty string)
    (codex_dir / "root-doc.md").write_text(
        "---\nid: root-doc\ntitle: Root Document\ntype: concept\nsummary: A root-level doc.\n---\n"
    )

    # Document in a subdirectory (GROUP should be "tech-arch")
    sub_dir = codex_dir / "tech-arch"
    sub_dir.mkdir(parents=True, exist_ok=True)
    (sub_dir / "source-layout.md").write_text(
        "---\nid: source-layout\ntitle: Source Layout\ntype: architecture\nsummary: Describes source layout.\n---\n"
    )

    return tmp_path


# ---------------------------------------------------------------------------
# Test: header contains GROUP
# Source: US-1 Unit Test Scenarios — header line output by _format_table contains "GROUP"
# ---------------------------------------------------------------------------


def test_codex_list_header_contains_group(runner, project_dir):
    """The header line produced by codex list must contain the column label GROUP."""
    result = runner.invoke(main, ["codex", "list"])
    assert result.exit_code == 0
    non_empty_lines = [l for l in result.output.split("\n") if l.strip()]
    assert len(non_empty_lines) >= 1, "Expected at least a header line"
    header = non_empty_lines[0]
    assert "GROUP" in header, f"Expected 'GROUP' in header, got: {header!r}"


# ---------------------------------------------------------------------------
# Test: header does NOT contain TYPE
# Source: US-1 Unit Test Scenarios — header line does not contain "TYPE"
# ---------------------------------------------------------------------------


def test_codex_list_header_does_not_contain_type(runner, project_dir):
    """The header line must NOT contain the old TYPE column label."""
    result = runner.invoke(main, ["codex", "list"])
    assert result.exit_code == 0
    non_empty_lines = [l for l in result.output.split("\n") if l.strip()]
    assert len(non_empty_lines) >= 1, "Expected at least a header line"
    header = non_empty_lines[0]
    assert "TYPE" not in header, f"Expected 'TYPE' to be absent from header, got: {header!r}"


# ---------------------------------------------------------------------------
# Test: subdirectory document has correct GROUP value
# Source: US-1 Unit Test Scenarios — GROUP is the subdirectory name for a document one level deep
# ---------------------------------------------------------------------------


def test_codex_list_row_uses_derive_group_for_subdirectory(runner, project_dir):
    """A document under .lore/codex/tech-arch/ must display GROUP = 'tech-arch'."""
    result = runner.invoke(main, ["codex", "list"])
    assert result.exit_code == 0
    assert "tech-arch" in result.output, (
        f"Expected 'tech-arch' (GROUP value) in output, got:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# Test: root-level document has empty GROUP
# Source: US-1 Unit Test Scenarios — GROUP is empty string for a document at root of .lore/codex/
# ---------------------------------------------------------------------------


def test_codex_list_group_is_empty_string_for_root_level_doc(runner, project_dir):
    """A document stored directly under .lore/codex/ must have an empty GROUP cell.

    We verify this by checking the row for root-doc uses _format_table layout.
    The root doc row's second column (GROUP) must be blank/empty padding, not
    a type string like 'concept'.
    """
    result = runner.invoke(main, ["codex", "list"])
    assert result.exit_code == 0

    # Build the expected output using _format_table with an empty GROUP for root-doc.
    # The actual output must match this structure — specifically the root-doc row
    # must not contain a non-empty GROUP value in the second column.
    lines = [l for l in result.output.split("\n") if "root-doc" in l]
    assert len(lines) == 1, f"Expected exactly one line for root-doc, got: {lines}"
    root_doc_line = lines[0]

    # The line for root-doc must NOT contain 'concept' (old TYPE value) in column position 2.
    # Under _format_table, the GROUP for root-doc is '' so 'concept' should not appear there.
    # We check that the output line matches the _format_table pattern with empty GROUP.
    # The simplest assertion: the GROUP column value 'concept' (former type) does not appear.
    assert "concept" not in root_doc_line, (
        f"Old TYPE value 'concept' found in root-doc line — GROUP should be empty, got: {root_doc_line!r}"
    )


# ---------------------------------------------------------------------------
# Test: output is produced via _format_table (not manual f-string)
# Source: US-1 Unit Test Scenarios — output is produced via _format_table
# ---------------------------------------------------------------------------


def test_codex_list_uses_format_table_not_fstring(runner, project_dir):
    """The tabular output must exactly match what _format_table would produce.

    We reconstruct the expected output using _format_table with the known
    test data and assert equality with the actual CLI output.
    """
    # Clear the codex dir and add a single, fully known document.
    import shutil
    codex_dir = project_dir / ".lore" / "codex"
    shutil.rmtree(codex_dir)
    codex_dir.mkdir()

    sub_dir = codex_dir / "arch"
    sub_dir.mkdir()
    (sub_dir / "my-doc.md").write_text(
        "---\nid: my-doc\ntitle: My Document\ntype: architecture\nsummary: A summary.\n---\n"
    )

    result = runner.invoke(main, ["codex", "list"])
    assert result.exit_code == 0

    # Expected output via _format_table with GROUP="arch" (not type="architecture")
    expected_lines = _format_table(
        ["ID", "GROUP", "TITLE", "SUMMARY"],
        [["my-doc", "arch", "My Document", "A summary."]],
    )
    expected_output = "\n".join(expected_lines) + "\n"
    assert result.output == expected_output, (
        f"Output does not match _format_table output.\n"
        f"Expected:\n{expected_output!r}\n"
        f"Got:\n{result.output!r}"
    )


# ---------------------------------------------------------------------------
# Test: empty codex shows fallback message
# Source: US-1 Unit Test Scenarios — prints "No codex documents found." when scan_codex returns empty list
# ---------------------------------------------------------------------------


def test_codex_list_empty_scan_prints_no_documents_message(runner, tmp_path, monkeypatch):
    """When no codex documents exist, the output is exactly 'No codex documents found.'
    AND the handler uses _format_table (not a manual f-string) for the non-empty path.

    We verify both:
    1. Empty codex -> fallback message (unchanged by US-1, but still valid)
    2. _format_table is called with GROUP header (not TYPE) when docs exist —
       by adding one doc we confirm the new code path is active.

    Assertion 2 fails against old code because old code uses manual f-strings
    and never calls _format_table, so the tracking will show wrong headers.
    """
    from unittest.mock import patch

    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    import shutil
    import lore.cli as cli_module

    codex_dir = tmp_path / ".lore" / "codex"
    if codex_dir.exists():
        shutil.rmtree(codex_dir)
    codex_dir.mkdir()

    # --- Part 1: empty codex ---
    result_empty = runner.invoke(main, ["codex", "list"])
    assert result_empty.exit_code == 0
    assert result_empty.output.strip() == "No codex documents found.", (
        f"Expected 'No codex documents found.', got: {result_empty.output!r}"
    )

    # --- Part 2: non-empty codex — _format_table must be called with ["ID","GROUP","TITLE","SUMMARY"] ---
    (codex_dir / "lone-doc.md").write_text(
        "---\nid: lone-doc\ntitle: Lone\ntype: concept\nsummary: Lone doc.\n---\n"
    )

    original_format_table = cli_module._format_table
    captured_headers = []

    def tracking_format_table(headers, rows):
        captured_headers.extend(headers)
        return original_format_table(headers, rows)

    with patch.object(cli_module, "_format_table", side_effect=tracking_format_table):
        result_nonempty = runner.invoke(main, ["codex", "list"])

    assert result_nonempty.exit_code == 0

    # This assertion fails against old code because old code never calls _format_table:
    assert captured_headers == ["ID", "GROUP", "TITLE", "SUMMARY"], (
        f"_format_table must be called with ['ID', 'GROUP', 'TITLE', 'SUMMARY'], "
        f"but captured_headers={captured_headers!r}. "
        f"Old code uses manual f-strings and never calls _format_table."
    )


# ===========================================================================
# US-2 Tests — JSON output: "codex" envelope, "group" field, no "type" field
# Source: codex-list-group-us-2 (Unit Test Scenarios section)
# These tests are RED-first: they FAIL against current production code.
# ===========================================================================


@pytest.fixture()
def project_dir_us2(tmp_path, monkeypatch):
    """Initialised lore project with codex documents in a subdirectory and at
    the root of .lore/codex/ — covers all US-2 JSON acceptance criteria.
    """
    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)

    # Document at root of .lore/codex/ (group should be empty string "")
    (codex_dir / "root-doc.md").write_text(
        "---\nid: root-doc\ntitle: Root Document\ntype: concept\nsummary: A root-level doc.\n---\n"
    )

    # Document in a subdirectory (group should be "tech/arch" — slash-joined after US-006/US-007)
    sub_dir = codex_dir / "tech" / "arch"
    sub_dir.mkdir(parents=True, exist_ok=True)
    (sub_dir / "source-layout.md").write_text(
        "---\nid: source-layout\ntitle: Source Layout\ntype: architecture\nsummary: Describes source layout.\n---\n"
    )

    return tmp_path


# ---------------------------------------------------------------------------
# Test: local --json flag activates JSON output mode
# Source: US-2 Unit Test Scenarios — --json local flag activates JSON output mode
# FAILS: current codex_list has no --json option decorator
# ---------------------------------------------------------------------------


def test_codex_list_local_json_flag_activates_json_mode(runner, project_dir_us2):
    """Running `lore codex list --json` must produce JSON output, not tabular text."""
    import json as _json

    result = runner.invoke(main, ["codex", "list", "--json"])
    assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}. Output:\n{result.output}"
    # Must be parseable as JSON
    try:
        parsed = _json.loads(result.output)
    except _json.JSONDecodeError as exc:
        pytest.fail(f"Output is not valid JSON: {exc}\nOutput was:\n{result.output!r}")
    assert isinstance(parsed, dict), f"Expected a JSON object at top level, got: {type(parsed)}"


# ---------------------------------------------------------------------------
# Test: JSON envelope key is "codex", not "documents"
# Source: US-2 Unit Test Scenarios — JSON output top-level key is "codex", not "documents"
# FAILS: current code emits {"documents": [...]}
# ---------------------------------------------------------------------------


def test_codex_list_json_top_level_key_is_codex(runner, project_dir_us2):
    """The JSON output top-level key must be "codex", not "documents"."""
    import json as _json

    result = runner.invoke(main, ["codex", "list", "--json"])
    assert result.exit_code == 0
    parsed = _json.loads(result.output)
    assert "codex" in parsed, (
        f"Expected top-level key 'codex' in JSON output, got keys: {list(parsed.keys())}"
    )
    assert "documents" not in parsed, (
        f"Key 'documents' must not be present in JSON output; found in: {list(parsed.keys())}"
    )
    assert isinstance(parsed["codex"], list), (
        f"Expected 'codex' value to be a list, got: {type(parsed['codex'])}"
    )


# ---------------------------------------------------------------------------
# Test: each JSON record contains a "group" field
# Source: US-2 Unit Test Scenarios — each JSON record contains "group" derived from derive_group
# FAILS: current code emits records without "group"
# ---------------------------------------------------------------------------


def test_codex_list_json_record_contains_group_field(runner, project_dir_us2):
    """Every record in the JSON output must contain a 'group' key."""
    import json as _json

    result = runner.invoke(main, ["codex", "list", "--json"])
    assert result.exit_code == 0
    parsed = _json.loads(result.output)
    records = parsed.get("codex", [])
    assert len(records) > 0, "Expected at least one document in the codex"
    for record in records:
        assert "group" in record, (
            f"Record missing 'group' key: {record}"
        )


# ---------------------------------------------------------------------------
# Test: "group" matches subdirectory name for a categorised document
# Source: US-2 Scenario 3 — group value matches subdirectory name
# FAILS: current code emits records without "group"
# ---------------------------------------------------------------------------


def test_codex_list_json_group_matches_subdirectory_name(runner, project_dir_us2):
    """The record for source-layout (under tech-arch/) must have group == 'tech-arch'."""
    import json as _json

    result = runner.invoke(main, ["codex", "list", "--json"])
    assert result.exit_code == 0
    parsed = _json.loads(result.output)
    records = parsed.get("codex", [])
    sub_records = [r for r in records if r.get("id") == "source-layout"]
    assert len(sub_records) == 1, f"Expected one record with id='source-layout', got: {sub_records}"
    assert sub_records[0]["group"] == "tech/arch", (
        f"Expected group='tech/arch' (slash-joined, US-007), got: {sub_records[0].get('group')!r}"
    )


# ---------------------------------------------------------------------------
# Test: "group" is empty string for a root-level document
# Source: US-2 Scenario 4 — group is "" for root-level docs (not null, not absent)
# FAILS: current code emits records without "group"
# ---------------------------------------------------------------------------


def test_codex_list_json_group_is_null_for_root_document(runner, project_dir_us2):
    """The record for root-doc (directly under .lore/codex/) must have group is None.

    US-007 Scenario 2/7: JSON envelope normalises empty group to null, never "".
    """
    import json as _json

    result = runner.invoke(main, ["codex", "list", "--json"])
    assert result.exit_code == 0
    parsed = _json.loads(result.output)
    records = parsed.get("codex", [])
    root_records = [r for r in records if r.get("id") == "root-doc"]
    assert len(root_records) == 1, f"Expected one record with id='root-doc', got: {root_records}"
    group_val = root_records[0].get("group", "__MISSING__")
    assert group_val is None, (
        f"Expected group=None for root-level doc (US-007), got: {group_val!r}"
    )


# ---------------------------------------------------------------------------
# Test: JSON records do NOT contain a "type" field
# Source: US-2 Scenario 5 — no record in "codex" array contains a "type" key
# FAILS: current code emits {"type": ...} in each record
# ---------------------------------------------------------------------------


def test_codex_list_json_records_have_no_type_key(runner, project_dir_us2):
    """No record in the JSON output must contain a 'type' key."""
    import json as _json

    result = runner.invoke(main, ["codex", "list", "--json"])
    assert result.exit_code == 0
    parsed = _json.loads(result.output)
    records = parsed.get("codex", [])
    for record in records:
        assert "type" not in record, (
            f"Record must not contain 'type' key, but got: {record}"
        )


# ---------------------------------------------------------------------------
# Test: each JSON record has exactly id, group, title, summary fields
# Source: US-2 Scenario 6 — record schema is exactly {id, group, title, summary}
# FAILS: current code emits {id, type, title, summary} (type instead of group)
# ---------------------------------------------------------------------------


def test_codex_list_json_each_record_has_exactly_four_fields(runner, project_dir_us2):
    """Each JSON record must have exactly the keys: id, group, title, summary."""
    import json as _json

    expected_keys = {"id", "group", "title", "summary"}
    result = runner.invoke(main, ["codex", "list", "--json"])
    assert result.exit_code == 0
    parsed = _json.loads(result.output)
    records = parsed.get("codex", [])
    assert len(records) > 0, "Expected at least one document in the codex"
    for record in records:
        actual_keys = set(record.keys())
        assert actual_keys == expected_keys, (
            f"Expected record keys {expected_keys}, got {actual_keys} in record: {record}"
        )


# ---------------------------------------------------------------------------
# Test: global ctx.obj["json"] = True also activates JSON output mode
# Source: US-2 Unit Test Scenarios — global ctx.obj["json"] also triggers JSON output
# FAILS: current code has no local --json flag; global --json is the only trigger
#        but the JSON branch still emits wrong envelope/fields — tests against correct shape
# ---------------------------------------------------------------------------


def test_codex_list_global_ctx_json_activates_json_mode(runner, project_dir_us2):
    """Running `lore --json codex list` must also produce valid JSON with 'codex' envelope."""
    import json as _json

    result = runner.invoke(main, ["--json", "codex", "list"])
    assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}. Output:\n{result.output}"
    try:
        parsed = _json.loads(result.output)
    except _json.JSONDecodeError as exc:
        pytest.fail(f"Output is not valid JSON: {exc}\nOutput was:\n{result.output!r}")
    assert "codex" in parsed, (
        f"Expected top-level key 'codex' when using global --json flag, got keys: {list(parsed.keys())}"
    )
    assert "documents" not in parsed, (
        f"Key 'documents' must not be present; found in: {list(parsed.keys())}"
    )
    records = parsed["codex"]
    for record in records:
        assert "group" in record, f"Record missing 'group' key: {record}"
        assert "type" not in record, f"Record must not contain 'type' key: {record}"


# ---------------------------------------------------------------------------
# Test: empty codex returns {"codex": []} under JSON mode
# Source: US-2 Unit Test Scenarios — JSON output for empty codex is {"codex": []}
# FAILS: current code emits {"documents": []}
# ---------------------------------------------------------------------------


def test_codex_list_json_empty_codex_returns_codex_empty_array(runner, tmp_path, monkeypatch):
    """When no codex documents exist, JSON output must be {"codex": []}."""
    import json as _json
    import shutil

    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    codex_dir = tmp_path / ".lore" / "codex"
    if codex_dir.exists():
        shutil.rmtree(codex_dir)
    codex_dir.mkdir()

    result = runner.invoke(main, ["codex", "list", "--json"])
    assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}. Output:\n{result.output}"
    try:
        parsed = _json.loads(result.output)
    except _json.JSONDecodeError as exc:
        pytest.fail(f"Output is not valid JSON: {exc}\nOutput was:\n{result.output!r}")
    assert parsed == {"codex": []}, (
        f"Expected {{\"codex\": []}} for empty codex, got: {parsed}"
    )
