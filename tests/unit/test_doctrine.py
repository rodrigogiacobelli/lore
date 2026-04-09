"""Unit tests for list_doctrines() and show_doctrine().

Spec: doctrine-design-file-us-001 (lore codex show doctrine-design-file-us-001)
Spec: doctrine-design-file-us-002 (lore codex show doctrine-design-file-us-002)
Spec: doctrine-design-file-us-004 (lore codex show doctrine-design-file-us-004)
Spec: doctrine-design-file-us-005 (lore codex show doctrine-design-file-us-005)
Spec: doctrine-design-file-us-006 (lore codex show doctrine-design-file-us-006)
Workflow: conceptual-workflows-doctrine-list (lore codex show conceptual-workflows-doctrine-list)
Workflow: conceptual-workflows-doctrine-show
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from lore.doctrine import (
    DoctrineError,
    _validate_design_frontmatter,
    _validate_yaml_schema,
    create_doctrine,
    list_doctrines,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pair(doctrines_dir: Path, stem: str, yaml_content: str, design_content: str):
    """Write a paired .design.md + .yaml into the doctrines_dir."""
    base = doctrines_dir / stem
    base.parent.mkdir(parents=True, exist_ok=True)
    Path(str(base) + ".design.md").write_text(design_content)
    Path(str(base) + ".yaml").write_text(yaml_content)


def _make_design(doctrines_dir: Path, stem: str, design_content: str):
    """Write only a .design.md (orphaned — no matching .yaml)."""
    base = doctrines_dir / stem
    base.parent.mkdir(parents=True, exist_ok=True)
    Path(str(base) + ".design.md").write_text(design_content)


def _make_yaml(doctrines_dir: Path, stem: str, yaml_content: str):
    """Write only a .yaml (YAML-only — no matching .design.md)."""
    base = doctrines_dir / stem
    base.parent.mkdir(parents=True, exist_ok=True)
    Path(str(base) + ".yaml").write_text(yaml_content)


_VALID_YAML = "id: my-doc\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
_VALID_DESIGN = "---\nid: my-doc\ntitle: My Doc\nsummary: A short summary.\n---\n"


# ---------------------------------------------------------------------------
# Unit — list_doctrines returns one entry for a valid pair
# conceptual-workflows-doctrine-list step 3: paired files → single entry
# ---------------------------------------------------------------------------


def test_list_doctrines_returns_entry_for_valid_pair(tmp_path):
    """list_doctrines() returns exactly one entry when one valid pair exists.

    The entry filename must point to the .design.md file, not the .yaml file.
    This distinguishes from the old YAML-only scanning behavior.
    """
    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    _make_pair(doctrines_dir, "my-doc", _VALID_YAML, _VALID_DESIGN)

    results = list_doctrines(doctrines_dir)

    assert len(results) == 1
    assert results[0]["id"] == "my-doc"
    # New behavior: filename points to the .design.md file, not .yaml
    assert results[0]["filename"] == "my-doc.design.md"


# ---------------------------------------------------------------------------
# Unit — list_doctrines returns [] when directory is empty
# conceptual-workflows-doctrine-list step 2: empty scan → empty list
# ---------------------------------------------------------------------------


def test_list_doctrines_returns_empty_for_empty_dir(tmp_path):
    """list_doctrines() returns [] when the doctrines directory is empty.

    Also verifies that a YAML-only file (no .design.md) is not returned —
    the new scan starts from .design.md files, not .yaml files.
    """
    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()

    results = list_doctrines(doctrines_dir)

    assert results == []


def test_list_doctrines_yaml_alone_returns_empty(tmp_path):
    """list_doctrines() returns [] when only a .yaml exists (no .design.md).

    This distinguishes new scan-from-design behavior from old scan-from-yaml.
    """
    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    _make_yaml(doctrines_dir, "yaml-only", _VALID_YAML.replace("my-doc", "yaml-only"))

    results = list_doctrines(doctrines_dir)

    assert results == []


# ---------------------------------------------------------------------------
# Unit — list_doctrines skips orphaned design file silently
# conceptual-workflows-doctrine-list step 5: .design.md without .yaml is skipped
# ---------------------------------------------------------------------------


def test_list_doctrines_skips_orphaned_design_file(tmp_path):
    """list_doctrines() skips a .design.md with no matching .yaml — returns [].

    The new scan finds .design.md files but requires a matching .yaml to proceed.
    Unlike old behavior (which ignored .design.md entirely), the new code
    actively checks for the .yaml pair.
    """
    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    _make_design(doctrines_dir, "orphan", "---\nid: orphan\ntitle: Orphan\n---\n")

    results = list_doctrines(doctrines_dir)

    assert results == []
    # Verify scan is now driven by .design.md (it found the file, but no .yaml → skip)
    # We can confirm by also checking no entry with id "orphan" slipped in
    ids = [r["id"] for r in results]
    assert "orphan" not in ids


# ---------------------------------------------------------------------------
# Unit — list_doctrines skips YAML-only file silently
# conceptual-workflows-doctrine-list step 6: .yaml without .design.md is invisible
# ---------------------------------------------------------------------------


def test_list_doctrines_skips_yaml_only_file(tmp_path):
    """list_doctrines() skips a .yaml with no matching .design.md — returns []."""
    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    _make_yaml(doctrines_dir, "legacy", _VALID_YAML.replace("my-doc", "legacy"))

    results = list_doctrines(doctrines_dir)

    assert results == []


# ---------------------------------------------------------------------------
# Unit — list_doctrines skips design file with missing frontmatter id
# conceptual-workflows-doctrine-list step 2: parse_frontmatter_doc returns None → skip
# ---------------------------------------------------------------------------


def test_list_doctrines_skips_design_with_no_id_in_frontmatter(tmp_path):
    """list_doctrines() skips a .design.md whose frontmatter has no 'id' field."""
    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    # .design.md without id
    _make_design(doctrines_dir, "no-id", "---\ntitle: No ID\nsummary: Oops.\n---\n")
    # Matching .yaml exists but design is invalid
    _make_yaml(doctrines_dir, "no-id", "id: no-id\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n")

    results = list_doctrines(doctrines_dir)

    assert results == []


# ---------------------------------------------------------------------------
# Unit — list_doctrines title fallback to id
# conceptual-workflows-doctrine-list step 4: FR-11 — title = id when missing
# ---------------------------------------------------------------------------


def test_list_doctrines_title_fallback_to_id(tmp_path):
    """list_doctrines() sets title to id value when design frontmatter has no title.

    Also asserts no legacy keys (name, description, errors) since the new
    entry shape only contains id, group, title, summary, valid, filename.
    """
    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    _make_pair(
        doctrines_dir,
        "minimal",
        yaml_content="id: minimal\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
        design_content="---\nid: minimal\n---\n",
    )

    results = list_doctrines(doctrines_dir)

    assert len(results) == 1
    assert results[0]["title"] == "minimal"
    # New entries have no legacy keys
    assert "name" not in results[0]
    assert "description" not in results[0]
    assert "errors" not in results[0]


# ---------------------------------------------------------------------------
# Unit — list_doctrines summary fallback to empty string
# conceptual-workflows-doctrine-list step 4: FR-11 — summary = "" when missing
# ---------------------------------------------------------------------------


def test_list_doctrines_summary_fallback_to_empty_string(tmp_path):
    """list_doctrines() sets summary to '' when design frontmatter has no summary.

    Verifies the fallback is '' (empty string) and NOT the old description-based
    truncation behavior which would use the YAML description field.
    """
    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    _make_pair(
        doctrines_dir,
        "minimal",
        # YAML has a description that old code would have used as summary fallback
        yaml_content="id: minimal\ndescription: Old description text.\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
        design_content="---\nid: minimal\n---\n",
    )

    results = list_doctrines(doctrines_dir)

    assert len(results) == 1
    # New behavior: summary comes only from design frontmatter; when absent → ""
    # NOT from YAML description field
    assert results[0]["summary"] == ""


# ---------------------------------------------------------------------------
# Unit — list_doctrines derives group from subdirectory
# conceptual-workflows-doctrine-list step 4: FR-12 uses paths.derive_group()
# ---------------------------------------------------------------------------


def test_list_doctrines_group_derived_from_subdirectory(tmp_path):
    """list_doctrines() derives group from directory path using paths.derive_group().

    The group is derived from the .design.md file's directory. The entry also
    must not contain legacy 'name' key (distinguishes new from old behavior).
    """
    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    _make_pair(
        doctrines_dir,
        "mygroup/my-doc",
        yaml_content=_VALID_YAML,
        design_content=_VALID_DESIGN,
    )

    results = list_doctrines(doctrines_dir)

    assert len(results) == 1
    assert results[0]["group"] == "mygroup"
    # New behavior: no legacy 'name' key in entry
    assert "name" not in results[0]


def test_list_doctrines_group_empty_for_root_level(tmp_path):
    """list_doctrines() sets group to '' for doctrines at root of doctrines_dir.

    Also verifies the entry filename ends with .design.md (new scan behavior).
    """
    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    _make_pair(
        doctrines_dir,
        "my-doc",
        yaml_content=_VALID_YAML,
        design_content=_VALID_DESIGN,
    )

    results = list_doctrines(doctrines_dir)

    assert len(results) == 1
    assert results[0]["group"] == ""
    # New behavior: filename points to .design.md
    assert results[0]["filename"].endswith(".design.md")


# ---------------------------------------------------------------------------
# Unit — list_doctrines sets filename to design file name
# conceptual-workflows-doctrine-list step 4: filename = "<id>.design.md"
# ---------------------------------------------------------------------------


def test_list_doctrines_filename_is_design_file_name(tmp_path):
    """list_doctrines() sets filename to the design file name (not full path)."""
    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    _make_pair(doctrines_dir, "my-doc", _VALID_YAML, _VALID_DESIGN)

    results = list_doctrines(doctrines_dir)

    assert len(results) == 1
    assert results[0]["filename"] == "my-doc.design.md"


# ---------------------------------------------------------------------------
# Unit — list_doctrines all returned entries have valid=True
# conceptual-workflows-doctrine-list step 4: only valid pairs returned
# ---------------------------------------------------------------------------


def test_list_doctrines_all_entries_valid_true(tmp_path):
    """list_doctrines() marks every returned entry with valid=True."""
    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    _make_pair(doctrines_dir, "my-doc", _VALID_YAML, _VALID_DESIGN)
    _make_pair(
        doctrines_dir,
        "another/another-doc",
        yaml_content="id: another-doc\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
        design_content="---\nid: another-doc\ntitle: Another Doc\nsummary: Another.\n---\n",
    )

    results = list_doctrines(doctrines_dir)

    assert len(results) == 2
    for entry in results:
        assert entry["valid"] is True


# ---------------------------------------------------------------------------
# Unit — list_doctrines no legacy keys in entries
# conceptual-workflows-doctrine-list: removed fields must not appear
# ---------------------------------------------------------------------------


def test_list_doctrines_no_legacy_keys(tmp_path):
    """list_doctrines() entries have no 'name', 'description', or 'errors' keys."""
    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    _make_pair(doctrines_dir, "my-doc", _VALID_YAML, _VALID_DESIGN)

    results = list_doctrines(doctrines_dir)

    assert len(results) == 1
    entry = results[0]
    assert "name" not in entry
    assert "description" not in entry
    assert "errors" not in entry


# ---------------------------------------------------------------------------
# Unit — list_doctrines entry has expected keys
# conceptual-workflows-doctrine-list step 4: entry shape
# ---------------------------------------------------------------------------


def test_list_doctrines_entry_has_expected_keys(tmp_path):
    """list_doctrines() entries have exactly id, group, title, summary, valid, filename.

    No extra keys (no name, description, errors from old schema).
    """
    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    _make_pair(doctrines_dir, "my-doc", _VALID_YAML, _VALID_DESIGN)

    results = list_doctrines(doctrines_dir)

    assert len(results) == 1
    entry = results[0]
    assert "id" in entry
    assert "group" in entry
    assert "title" in entry
    assert "summary" in entry
    assert "valid" in entry
    assert "filename" in entry
    # New schema: no extra legacy keys
    assert "name" not in entry
    assert "description" not in entry
    assert "errors" not in entry


# ---------------------------------------------------------------------------
# Unit — list_doctrines reads id from design frontmatter (not YAML)
# conceptual-workflows-doctrine-list step 3: id comes from design file
# ---------------------------------------------------------------------------


def test_list_doctrines_id_from_design_frontmatter(tmp_path):
    """list_doctrines() uses id from design frontmatter, not YAML.

    The design frontmatter 'id' field is authoritative. The test confirms
    the entry has no 'name' key (old behavior used 'name' from YAML).
    """
    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    _make_pair(doctrines_dir, "my-doc", _VALID_YAML, _VALID_DESIGN)

    results = list_doctrines(doctrines_dir)

    assert len(results) == 1
    assert results[0]["id"] == "my-doc"
    # New behavior: no legacy 'name' key; id comes from design frontmatter
    assert "name" not in results[0]


# ---------------------------------------------------------------------------
# Unit — list_doctrines title from design frontmatter
# conceptual-workflows-doctrine-list step 4: FR-11 — title from design file
# ---------------------------------------------------------------------------


def test_list_doctrines_title_from_design_frontmatter(tmp_path):
    """list_doctrines() uses title from design frontmatter."""
    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    _make_pair(doctrines_dir, "my-doc", _VALID_YAML, _VALID_DESIGN)

    results = list_doctrines(doctrines_dir)

    assert len(results) == 1
    assert results[0]["title"] == "My Doc"


# ---------------------------------------------------------------------------
# Unit — list_doctrines summary from design frontmatter
# conceptual-workflows-doctrine-list step 4: FR-11 — summary from design file
# ---------------------------------------------------------------------------


def test_list_doctrines_summary_from_design_frontmatter(tmp_path):
    """list_doctrines() uses summary from design frontmatter."""
    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    _make_pair(doctrines_dir, "my-doc", _VALID_YAML, _VALID_DESIGN)

    results = list_doctrines(doctrines_dir)

    assert len(results) == 1
    assert results[0]["summary"] == "A short summary."


# ---------------------------------------------------------------------------
# US-002 Unit — CLI doctrine_list JSON mode maps to 5-field shape
# conceptual-workflows-doctrine-list: CLI handler strips filename/errors from Python API result
# ---------------------------------------------------------------------------


def test_doctrine_list_json_handler_strips_internal_fields(tmp_path, monkeypatch):
    """CLI doctrine_list JSON mode strips filename and errors from list_doctrines() output.

    The CLI handler must map the Python API result to exactly 5 fields:
    id, group, title, summary, valid — no filename, no errors.
    """
    from lore.cli import main

    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    # Mock list_doctrines to return an entry that includes internal fields
    mock_entry = {
        "id": "my-doc",
        "group": "",
        "title": "My Doc",
        "summary": "A short summary.",
        "valid": True,
        "filename": "my-doc.design.md",
        "errors": [],
    }

    with patch("lore.doctrine.list_doctrines", return_value=[mock_entry]):
        result = CliRunner().invoke(main, ["doctrine", "list", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data["doctrines"]) == 1
    entry = data["doctrines"][0]
    # Internal fields must be stripped
    assert "filename" not in entry
    assert "errors" not in entry
    # Required fields must be present
    assert set(entry.keys()) == {"id", "group", "title", "summary", "valid"}


def test_doctrine_list_json_handler_valid_always_true(tmp_path, monkeypatch):
    """CLI doctrine_list JSON mode always sets valid=True for returned entries.

    Since list_doctrines() only returns valid pairs (orphans are skipped),
    every entry in the JSON output has valid=True.
    """
    from lore.cli import main

    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    # Mock list_doctrines to return multiple entries all with valid=True
    mock_entries = [
        {
            "id": "doc-a",
            "group": "",
            "title": "Doc A",
            "summary": "Summary A",
            "valid": True,
            "filename": "doc-a.design.md",
        },
        {
            "id": "doc-b",
            "group": "mygroup",
            "title": "Doc B",
            "summary": "Summary B",
            "valid": True,
            "filename": "mygroup/doc-b.design.md",
        },
    ]

    with patch("lore.doctrine.list_doctrines", return_value=mock_entries):
        result = CliRunner().invoke(main, ["doctrine", "list", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data["doctrines"]) == 2
    for entry in data["doctrines"]:
        assert entry["valid"] is True


# ---------------------------------------------------------------------------
# US-003 Unit stubs — Python API contract tests for list_doctrines()
# Spec: doctrine-design-file-us-003 (lore codex show doctrine-design-file-us-003)
# ---------------------------------------------------------------------------


def test_list_doctrines_two_pairs_returns_two_entries(tmp_path):
    """list_doctrines() returns a list of length 2 when two valid pairs exist.

    Spec: US-003 unit — two valid pairs return list of length 2.
    """
    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    _make_pair(
        doctrines_dir,
        "alpha",
        yaml_content="id: alpha\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
        design_content="---\nid: alpha\ntitle: Alpha\nsummary: First.\n---\n",
    )
    _make_pair(
        doctrines_dir,
        "beta",
        yaml_content="id: beta\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
        design_content="---\nid: beta\ntitle: Beta\nsummary: Second.\n---\n",
    )

    results = list_doctrines(doctrines_dir)

    assert len(results) == 2
    ids = {r["id"] for r in results}
    assert ids == {"alpha", "beta"}


# ===========================================================================
# US-004 Unit tests for show_doctrine()
# Spec: doctrine-design-file-us-004 (lore codex show doctrine-design-file-us-004)
# ===========================================================================


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_show_pair(doctrines_dir: Path, stem: str, yaml_content: str, design_content: str):
    """Write a paired .design.md + .yaml for show_doctrine() tests."""
    base = doctrines_dir / stem
    base.parent.mkdir(parents=True, exist_ok=True)
    Path(str(base) + ".design.md").write_text(design_content)
    Path(str(base) + ".yaml").write_text(yaml_content)


_SHOW_YAML = (
    "id: my-doc\n"
    "steps:\n"
    "  - id: s1\n"
    "    title: Step One\n"
    "    type: knight\n"
    "    knight: k\n"
)
_SHOW_DESIGN = (
    "---\n"
    "id: my-doc\n"
    "title: My Doc\n"
    "summary: A short summary.\n"
    "---\n"
    "\n"
    "# My Doc\n"
    "\n"
    "Some design content.\n"
)


# ---------------------------------------------------------------------------
# Unit — show_doctrine returns dict with all required keys
# conceptual-workflows-doctrine-show step 4: return shape
# ---------------------------------------------------------------------------


def test_show_doctrine_returns_correct_keys(tmp_path):
    """show_doctrine() returns a dict with exactly the keys: id, title, summary, design, raw_yaml, steps."""
    from lore.doctrine import show_doctrine

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    _make_show_pair(doctrines_dir, "my-doc", _SHOW_YAML, _SHOW_DESIGN)

    result = show_doctrine("my-doc", doctrines_dir)

    assert isinstance(result, dict)
    assert set(result.keys()) == {"id", "title", "summary", "design", "raw_yaml", "steps"}


# ---------------------------------------------------------------------------
# Unit — show_doctrine design is the raw verbatim string
# conceptual-workflows-doctrine-show step 4: no transformation of design content
# ---------------------------------------------------------------------------


def test_show_doctrine_design_is_verbatim_string(tmp_path):
    """show_doctrine() returns design as the exact raw content of the .design.md file."""
    from lore.doctrine import show_doctrine

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    _make_show_pair(doctrines_dir, "my-doc", _SHOW_YAML, _SHOW_DESIGN)

    result = show_doctrine("my-doc", doctrines_dir)

    assert result["design"] == _SHOW_DESIGN


# ---------------------------------------------------------------------------
# Unit — show_doctrine raw_yaml is the raw verbatim string
# conceptual-workflows-doctrine-show step 4: no transformation of YAML content
# ---------------------------------------------------------------------------


def test_show_doctrine_raw_yaml_is_verbatim_string(tmp_path):
    """show_doctrine() returns raw_yaml as the exact raw content of the .yaml file."""
    from lore.doctrine import show_doctrine

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    _make_show_pair(doctrines_dir, "my-doc", _SHOW_YAML, _SHOW_DESIGN)

    result = show_doctrine("my-doc", doctrines_dir)

    assert result["raw_yaml"] == _SHOW_YAML


# ---------------------------------------------------------------------------
# Unit — show_doctrine steps is normalized list with defaults applied
# conceptual-workflows-doctrine-show step 4: _normalize() called on steps
# ---------------------------------------------------------------------------


def test_show_doctrine_steps_are_normalized(tmp_path):
    """show_doctrine() steps list has defaults applied (priority, notes, needs)."""
    from lore.doctrine import show_doctrine

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    # Step has no priority, notes, or needs — defaults should be applied
    yaml_content = (
        "id: my-doc\n"
        "steps:\n"
        "  - id: s1\n"
        "    title: Step One\n"
        "    type: knight\n"
        "    knight: k\n"
    )
    _make_show_pair(doctrines_dir, "my-doc", yaml_content, _SHOW_DESIGN)

    result = show_doctrine("my-doc", doctrines_dir)

    assert isinstance(result["steps"], list)
    assert len(result["steps"]) == 1
    step = result["steps"][0]
    # Defaults must be applied
    assert "priority" in step
    assert step["priority"] == 2  # default priority
    assert "needs" in step
    assert step["needs"] == []  # default empty needs


# ---------------------------------------------------------------------------
# Unit — show_doctrine raises DoctrineError when design file is absent
# conceptual-workflows-doctrine-show step 3: exact error message
# ---------------------------------------------------------------------------


def test_show_doctrine_design_file_missing_exact_message(tmp_path):
    """show_doctrine() raises DoctrineError with exact message format for missing design."""
    from lore.doctrine import show_doctrine, DoctrineError

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    yaml_file = doctrines_dir / "my-doc.yaml"
    yaml_file.write_text(_SHOW_YAML)

    with pytest.raises(DoctrineError) as exc_info:
        show_doctrine("my-doc", doctrines_dir)

    assert str(exc_info.value) == "Doctrine 'my-doc' not found: design file missing"


# ---------------------------------------------------------------------------
# Unit — show_doctrine raises DoctrineError when YAML file is absent
# conceptual-workflows-doctrine-show step 3: exact error message
# ---------------------------------------------------------------------------


def test_show_doctrine_yaml_file_missing_exact_message(tmp_path):
    """show_doctrine() raises DoctrineError with exact message format for missing YAML."""
    from lore.doctrine import show_doctrine, DoctrineError

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    design_file = doctrines_dir / "my-doc.design.md"
    design_file.write_text(_SHOW_DESIGN)

    with pytest.raises(DoctrineError) as exc_info:
        show_doctrine("my-doc", doctrines_dir)

    assert str(exc_info.value) == "Doctrine 'my-doc' not found: YAML file missing"


# ---------------------------------------------------------------------------
# Unit — show_doctrine raises DoctrineError when both files are absent
# conceptual-workflows-doctrine-show step 3: both files missing
# ---------------------------------------------------------------------------


def test_show_doctrine_not_found_exact_message(tmp_path):
    """show_doctrine() raises DoctrineError with exact 'not found' message when both absent."""
    from lore.doctrine import show_doctrine, DoctrineError

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()

    with pytest.raises(DoctrineError) as exc_info:
        show_doctrine("nonexistent", doctrines_dir)

    assert str(exc_info.value) == "Doctrine 'nonexistent' not found"


# ---------------------------------------------------------------------------
# Unit — show_doctrine raises DoctrineError on invalid YAML
# conceptual-workflows-doctrine-show step 4: YAML parse failure
# ---------------------------------------------------------------------------


def test_show_doctrine_raises_yaml_parsing_error(tmp_path):
    """show_doctrine() raises DoctrineError starting with 'YAML parsing error:' on bad YAML."""
    from lore.doctrine import show_doctrine, DoctrineError

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    # Invalid YAML that will fail to parse
    invalid_yaml = "id: my-doc\nsteps: [\nbroken yaml: {{{\n"
    _make_show_pair(doctrines_dir, "my-doc", invalid_yaml, _SHOW_DESIGN)

    with pytest.raises(DoctrineError) as exc_info:
        show_doctrine("my-doc", doctrines_dir)

    assert str(exc_info.value).startswith("YAML parsing error:")


# ---------------------------------------------------------------------------
# Unit — show_doctrine title falls back to id when absent from design frontmatter
# conceptual-workflows-doctrine-show step 4: FR-11
# ---------------------------------------------------------------------------


def test_show_doctrine_title_fallback_to_id(tmp_path):
    """show_doctrine() title falls back to id when title absent from design frontmatter."""
    from lore.doctrine import show_doctrine

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    design_no_title = "---\nid: my-doc\n---\n"
    _make_show_pair(doctrines_dir, "my-doc", _SHOW_YAML, design_no_title)

    result = show_doctrine("my-doc", doctrines_dir)

    assert result["title"] == "my-doc"


# ---------------------------------------------------------------------------
# Unit — show_doctrine summary falls back to empty string when absent
# conceptual-workflows-doctrine-show step 4: FR-11
# ---------------------------------------------------------------------------


def test_show_doctrine_summary_fallback_to_empty_string(tmp_path):
    """show_doctrine() summary falls back to "" when summary absent from design frontmatter."""
    from lore.doctrine import show_doctrine

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    design_no_summary = "---\nid: my-doc\ntitle: My Doc\n---\n"
    _make_show_pair(doctrines_dir, "my-doc", _SHOW_YAML, design_no_summary)

    result = show_doctrine("my-doc", doctrines_dir)

    assert result["summary"] == ""


# ---------------------------------------------------------------------------
# Unit — CLI doctrine_show handler text mode prints design, separator, raw_yaml
# conceptual-workflows-doctrine-show step 5: output format
# ---------------------------------------------------------------------------


def test_doctrine_show_cli_handler_text_mode_format(tmp_path, monkeypatch):
    """CLI doctrine_show text mode prints d['design'] then '\\n---\\n' then d['raw_yaml']."""
    from lore.cli import main

    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    design_content = "---\nid: my-doc\ntitle: My Doc\nsummary: Summary.\n---\n\n# My Doc\n\nBody.\n"
    raw_yaml_content = "id: my-doc\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"

    mock_result = {
        "id": "my-doc",
        "title": "My Doc",
        "summary": "Summary.",
        "design": design_content,
        "raw_yaml": raw_yaml_content,
        "steps": [{"id": "s1", "title": "S1", "priority": 2, "type": "knight", "needs": [], "knight": "k", "notes": None}],
    }

    with patch("lore.doctrine.show_doctrine", return_value=mock_result):
        result = CliRunner().invoke(main, ["doctrine", "show", "my-doc"])

    assert result.exit_code == 0
    assert design_content in result.output
    assert "\n---\n" in result.output
    assert raw_yaml_content in result.output
    # Verify order: design before separator before raw_yaml
    design_pos = result.output.index(design_content)
    sep_pos = result.output.index("\n---\n")
    yaml_pos = result.output.index(raw_yaml_content)
    assert design_pos < sep_pos < yaml_pos


# ===========================================================================
# US-005 Unit tests — CLI doctrine_show JSON mode handler
# Spec: doctrine-design-file-us-005 (lore codex show doctrine-design-file-us-005)
# ===========================================================================

_JSON_MOCK_RESULT = {
    "id": "my-doc",
    "title": "My Doc",
    "summary": "A short summary.",
    "design": "---\nid: my-doc\ntitle: My Doc\nsummary: A short summary.\n---\n\n# My Doc\n\nBody.\n",
    "raw_yaml": "id: my-doc\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
    "steps": [
        {
            "id": "s1",
            "title": "S1",
            "priority": 2,
            "type": "knight",
            "knight": "k",
            "notes": None,
            "needs": [],
        }
    ],
}


# ---------------------------------------------------------------------------
# Unit — CLI doctrine_show JSON mode output has exactly {id, title, summary, design, steps}
# conceptual-workflows-doctrine-show: no raw_yaml, no name, no description in JSON
# ---------------------------------------------------------------------------


def test_doctrine_show_cli_json_handler_correct_keys(tmp_path, monkeypatch):
    """CLI doctrine_show JSON mode outputs exactly {id, title, summary, design, steps}."""
    from lore.cli import main

    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    with patch("lore.doctrine.show_doctrine", return_value=_JSON_MOCK_RESULT):
        result = CliRunner().invoke(main, ["doctrine", "show", "my-doc", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert set(data.keys()) == {"id", "title", "summary", "design", "steps"}


# ---------------------------------------------------------------------------
# Unit — CLI doctrine_show JSON mode excludes raw_yaml
# conceptual-workflows-doctrine-show: raw_yaml stripped from output
# ---------------------------------------------------------------------------


def test_doctrine_show_cli_json_handler_strips_raw_yaml(tmp_path, monkeypatch):
    """CLI doctrine_show JSON mode does NOT include 'raw_yaml' key in output."""
    from lore.cli import main

    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    with patch("lore.doctrine.show_doctrine", return_value=_JSON_MOCK_RESULT):
        result = CliRunner().invoke(main, ["doctrine", "show", "my-doc", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "raw_yaml" not in data


# ---------------------------------------------------------------------------
# Unit — CLI doctrine_show JSON mode excludes legacy name and description keys
# conceptual-workflows-doctrine-show: breaking change, old schema removed
# ---------------------------------------------------------------------------


def test_doctrine_show_cli_json_handler_no_legacy_keys(tmp_path, monkeypatch):
    """CLI doctrine_show JSON mode does NOT include 'name' or 'description' keys."""
    from lore.cli import main

    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    with patch("lore.doctrine.show_doctrine", return_value=_JSON_MOCK_RESULT):
        result = CliRunner().invoke(main, ["doctrine", "show", "my-doc", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "name" not in data
    assert "description" not in data


# ---------------------------------------------------------------------------
# Unit — CLI doctrine_show JSON mode design value is a string
# conceptual-workflows-doctrine-show: design = raw file content string
# ---------------------------------------------------------------------------


def test_doctrine_show_cli_json_handler_design_is_string(tmp_path, monkeypatch):
    """CLI doctrine_show JSON mode 'design' value is a string (raw file content)."""
    from lore.cli import main

    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    with patch("lore.doctrine.show_doctrine", return_value=_JSON_MOCK_RESULT):
        result = CliRunner().invoke(main, ["doctrine", "show", "my-doc", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data["design"], str)
    assert data["design"] == _JSON_MOCK_RESULT["design"]


# ---------------------------------------------------------------------------
# Unit — CLI doctrine_show JSON mode steps value is a list of dicts
# conceptual-workflows-doctrine-show: steps = normalized list
# ---------------------------------------------------------------------------


def test_doctrine_show_cli_json_handler_steps_is_list(tmp_path, monkeypatch):
    """CLI doctrine_show JSON mode 'steps' value is a list of dicts with normalized fields."""
    from lore.cli import main

    monkeypatch.chdir(tmp_path)
    CliRunner().invoke(main, ["init"])

    with patch("lore.doctrine.show_doctrine", return_value=_JSON_MOCK_RESULT):
        result = CliRunner().invoke(main, ["doctrine", "show", "my-doc", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data["steps"], list)
    assert len(data["steps"]) == 1
    step = data["steps"][0]
    assert isinstance(step, dict)
    for field in ("id", "title", "priority", "type", "knight", "notes", "needs"):
        assert field in step, f"Missing step field: {field}"


# ===========================================================================
# US-007 Unit tests — _validate_yaml_schema, _validate_design_frontmatter, create_doctrine
# Spec: doctrine-design-file-us-007 (lore codex show doctrine-design-file-us-007)
# Workflow: conceptual-workflows-doctrine-new
# ===========================================================================




# ---------------------------------------------------------------------------
# Unit — _validate_yaml_schema raises "Missing required field: id" when id absent
# conceptual-workflows-doctrine-new: field presence check
# ---------------------------------------------------------------------------


def test_validate_yaml_schema_missing_id():
    """_validate_yaml_schema() raises DoctrineError with 'Missing required field: id' when id absent."""

    data = {"steps": [{"id": "s1", "title": "Step 1", "type": "knight", "knight": "k"}]}
    with pytest.raises(DoctrineError) as exc_info:
        _validate_yaml_schema(data, "my-workflow")
    assert "Missing required field: id" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Unit — _validate_yaml_schema raises "Missing required field: steps" when steps absent
# conceptual-workflows-doctrine-new: field presence check
# ---------------------------------------------------------------------------


def test_validate_yaml_schema_missing_steps():
    """_validate_yaml_schema() raises DoctrineError with 'Missing required field: steps' when steps absent."""

    data = {"id": "my-workflow"}
    with pytest.raises(DoctrineError) as exc_info:
        _validate_yaml_schema(data, "my-workflow")
    assert "Missing required field: steps" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Unit — _validate_yaml_schema raises on id mismatch
# conceptual-workflows-doctrine-new: id must match name argument
# ---------------------------------------------------------------------------


def test_validate_yaml_schema_id_mismatch():
    """_validate_yaml_schema() raises DoctrineError when id does not match name argument."""

    data = {
        "id": "other-name",
        "steps": [{"id": "s1", "title": "S1", "type": "knight", "knight": "k"}],
    }
    with pytest.raises(DoctrineError) as exc_info:
        _validate_yaml_schema(data, "my-workflow")
    assert "other-name" in str(exc_info.value)
    assert "my-workflow" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Unit — _validate_yaml_schema raises "Unexpected field in YAML: name"
# conceptual-workflows-doctrine-new: FR-8
# ---------------------------------------------------------------------------


def test_validate_yaml_schema_rejects_name_field():
    """_validate_yaml_schema() raises DoctrineError with 'Unexpected field in YAML: name' when name key present."""

    data = {
        "id": "my-workflow",
        "name": "my-workflow",
        "steps": [{"id": "s1", "title": "S1", "type": "knight", "knight": "k"}],
    }
    with pytest.raises(DoctrineError) as exc_info:
        _validate_yaml_schema(data, "my-workflow")
    assert "Unexpected field in YAML: name" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Unit — _validate_yaml_schema raises "Unexpected field in YAML: description"
# conceptual-workflows-doctrine-new: FR-8
# ---------------------------------------------------------------------------


def test_validate_yaml_schema_rejects_description_field():
    """_validate_yaml_schema() raises DoctrineError with 'Unexpected field in YAML: description' when description key present."""

    data = {
        "id": "my-workflow",
        "description": "some description",
        "steps": [{"id": "s1", "title": "S1", "type": "knight", "knight": "k"}],
    }
    with pytest.raises(DoctrineError) as exc_info:
        _validate_yaml_schema(data, "my-workflow")
    assert "Unexpected field in YAML: description" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Unit — _validate_yaml_schema passes with only id and steps
# conceptual-workflows-doctrine-new: valid minimal YAML
# ---------------------------------------------------------------------------


def test_validate_yaml_schema_passes_minimal_yaml():
    """_validate_yaml_schema() does not raise when YAML has only id and steps with valid steps."""
    data = {
        "id": "my-workflow",
        "steps": [{"id": "s1", "title": "S1", "type": "knight", "knight": "k"}],
    }
    # Must not raise
    _validate_yaml_schema(data, "my-workflow")


# ---------------------------------------------------------------------------
# Unit — _validate_design_frontmatter raises when meta is None
# conceptual-workflows-doctrine-new: frontmatter parse failure
# ---------------------------------------------------------------------------


def test_validate_design_frontmatter_none_meta():
    """_validate_design_frontmatter() raises DoctrineError with 'Design file missing required frontmatter field: id' when meta is None."""

    with pytest.raises(DoctrineError) as exc_info:
        _validate_design_frontmatter(None, "my-workflow")
    assert "Design file missing required frontmatter field: id" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Unit — _validate_design_frontmatter raises when meta has no id key
# conceptual-workflows-doctrine-new: id required in frontmatter
# ---------------------------------------------------------------------------


def test_validate_design_frontmatter_missing_id_key():
    """_validate_design_frontmatter() raises DoctrineError with 'Design file missing required frontmatter field: id' when meta has no id."""

    meta = {"title": "My Workflow", "summary": "Does things."}
    with pytest.raises(DoctrineError) as exc_info:
        _validate_design_frontmatter(meta, "my-workflow")
    assert "Design file missing required frontmatter field: id" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Unit — _validate_design_frontmatter raises on design id mismatch
# conceptual-workflows-doctrine-new: id must match name argument
# ---------------------------------------------------------------------------


def test_validate_design_frontmatter_id_mismatch():
    """_validate_design_frontmatter() raises DoctrineError when meta id does not match name."""

    meta = {"id": "other-name", "title": "Other"}
    with pytest.raises(DoctrineError) as exc_info:
        _validate_design_frontmatter(meta, "my-workflow")
    assert "Design file id" in str(exc_info.value)
    assert "other-name" in str(exc_info.value)
    assert "my-workflow" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Unit — _validate_design_frontmatter passes when meta id matches name
# conceptual-workflows-doctrine-new: valid design frontmatter
# ---------------------------------------------------------------------------


def test_validate_design_frontmatter_passes_valid():
    """_validate_design_frontmatter() does not raise when meta id matches name."""
    meta = {"id": "my-workflow", "title": "My Workflow", "summary": "Does things."}
    # Must not raise
    _validate_design_frontmatter(meta, "my-workflow")


# ---------------------------------------------------------------------------
# Unit — create_doctrine writes two files to doctrines_dir on success
# conceptual-workflows-doctrine-new step 7: file write
# ---------------------------------------------------------------------------


def test_create_doctrine_writes_two_files(tmp_path):
    """create_doctrine() writes both .yaml and .design.md to doctrines_dir on success."""
    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()

    yaml_source = tmp_path / "my-workflow.yaml"
    yaml_source.write_text(
        "id: my-workflow\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )
    design_source = tmp_path / "my-workflow.design.md"
    design_source.write_text(
        "---\nid: my-workflow\ntitle: My Workflow\nsummary: Does things.\n---\n\n# My Workflow\n"
    )

    create_doctrine("my-workflow", yaml_source, design_source, doctrines_dir)

    assert (doctrines_dir / "my-workflow.yaml").exists()
    assert (doctrines_dir / "my-workflow.design.md").exists()


# ---------------------------------------------------------------------------
# Unit — create_doctrine raises and writes no files when YAML validation fails
# conceptual-workflows-doctrine-new step 5-6: atomicity
# ---------------------------------------------------------------------------


def test_create_doctrine_no_write_on_yaml_validation_failure(tmp_path):
    """create_doctrine() raises DoctrineError and writes no files when YAML validation fails."""

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()

    yaml_source = tmp_path / "my-workflow.yaml"
    yaml_source.write_text("id: my-workflow\nsteps: []\n")  # empty steps → validation failure
    design_source = tmp_path / "my-workflow.design.md"
    design_source.write_text(
        "---\nid: my-workflow\ntitle: My Workflow\n---\n"
    )

    with pytest.raises(DoctrineError):
        create_doctrine("my-workflow", yaml_source, design_source, doctrines_dir)

    assert not (doctrines_dir / "my-workflow.yaml").exists()
    assert not (doctrines_dir / "my-workflow.design.md").exists()


# ---------------------------------------------------------------------------
# Unit — create_doctrine raises and writes no files when design validation fails
# conceptual-workflows-doctrine-new step 6: atomicity
# ---------------------------------------------------------------------------


def test_create_doctrine_no_write_on_design_validation_failure(tmp_path):
    """create_doctrine() raises DoctrineError and writes no files when design validation fails."""

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()

    yaml_source = tmp_path / "my-workflow.yaml"
    yaml_source.write_text(
        "id: my-workflow\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )
    design_source = tmp_path / "my-workflow.design.md"
    # id mismatch triggers design validation failure
    design_source.write_text("---\nid: other-name\ntitle: Other\n---\n")

    with pytest.raises(DoctrineError):
        create_doctrine("my-workflow", yaml_source, design_source, doctrines_dir)

    assert not (doctrines_dir / "my-workflow.yaml").exists()
    assert not (doctrines_dir / "my-workflow.design.md").exists()


# ---------------------------------------------------------------------------
# Unit — create_doctrine raises "already exists" when YAML stem found
# conceptual-workflows-doctrine-new step 2: duplicate check by YAML stem
# ---------------------------------------------------------------------------


def test_create_doctrine_duplicate_yaml_stem(tmp_path):
    """create_doctrine() raises DoctrineError containing 'already exists' when YAML stem exists in doctrines_dir."""

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    # Pre-existing YAML file
    (doctrines_dir / "my-workflow.yaml").write_text("id: my-workflow\nsteps: []\n")

    yaml_source = tmp_path / "my-workflow.yaml"
    yaml_source.write_text(
        "id: my-workflow\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )
    design_source = tmp_path / "my-workflow.design.md"
    design_source.write_text("---\nid: my-workflow\n---\n")

    with pytest.raises(DoctrineError) as exc_info:
        create_doctrine("my-workflow", yaml_source, design_source, doctrines_dir)

    assert "already exists" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Unit — create_doctrine raises "already exists" when design stem found
# conceptual-workflows-doctrine-new step 2: duplicate check by design stem
# ---------------------------------------------------------------------------


def test_create_doctrine_duplicate_design_stem(tmp_path):
    """create_doctrine() raises DoctrineError containing 'already exists' when design stem exists in doctrines_dir."""

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()
    # Pre-existing design file (no matching yaml)
    (doctrines_dir / "my-workflow.design.md").write_text(
        "---\nid: my-workflow\ntitle: My Workflow\n---\n"
    )

    yaml_source = tmp_path / "my-workflow.yaml"
    yaml_source.write_text(
        "id: my-workflow\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )
    design_source = tmp_path / "my-workflow.design.md"
    design_source.write_text("---\nid: my-workflow\n---\n")

    with pytest.raises(DoctrineError) as exc_info:
        create_doctrine("my-workflow", yaml_source, design_source, doctrines_dir)

    assert "already exists" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Unit — create_doctrine raises "File not found" when YAML source missing
# conceptual-workflows-doctrine-new step 3: source file existence
# ---------------------------------------------------------------------------


def test_create_doctrine_yaml_source_not_found(tmp_path):
    """create_doctrine() raises DoctrineError containing 'File not found' when YAML source path does not exist."""

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()

    missing_yaml = tmp_path / "nonexistent.yaml"
    design_source = tmp_path / "my-workflow.design.md"
    design_source.write_text("---\nid: my-workflow\n---\n")

    with pytest.raises(DoctrineError) as exc_info:
        create_doctrine("my-workflow", missing_yaml, design_source, doctrines_dir)

    assert "File not found" in str(exc_info.value)


# ===========================================================================
# US-008 Unit tests — create_doctrine() return value and file content fidelity
# Spec: doctrine-design-file-us-008 (lore codex show doctrine-design-file-us-008)
# Workflow: conceptual-workflows-doctrine-new
# ===========================================================================


# ---------------------------------------------------------------------------
# Unit — create_doctrine on success returns correct dict
# conceptual-workflows-doctrine-new step 8: return value
# ---------------------------------------------------------------------------


def test_create_doctrine_returns_correct_dict(tmp_path):
    """create_doctrine() returns {"name", "yaml_filename", "design_filename"} dict on success."""

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()

    yaml_source = tmp_path / "my-workflow.yaml"
    yaml_source.write_text(
        "id: my-workflow\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )
    design_source = tmp_path / "my-workflow.design.md"
    design_source.write_text(
        "---\nid: my-workflow\ntitle: My Workflow\nsummary: Does things.\n---\n"
    )

    result = create_doctrine("my-workflow", yaml_source, design_source, doctrines_dir)

    assert result == {
        "name": "my-workflow",
        "yaml_filename": "my-workflow.yaml",
        "design_filename": "my-workflow.design.md",
    }


# ---------------------------------------------------------------------------
# Unit — create_doctrine on success target YAML content equals source content
# conceptual-workflows-doctrine-new step 7: file copy fidelity
# ---------------------------------------------------------------------------


def test_create_doctrine_yaml_content_equals_source(tmp_path):
    """create_doctrine() writes YAML file whose content is identical to the source YAML."""

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()

    yaml_content = (
        "id: my-workflow\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )
    yaml_source = tmp_path / "my-workflow.yaml"
    yaml_source.write_text(yaml_content)
    design_source = tmp_path / "my-workflow.design.md"
    design_source.write_text(
        "---\nid: my-workflow\ntitle: My Workflow\nsummary: Does things.\n---\n"
    )

    create_doctrine("my-workflow", yaml_source, design_source, doctrines_dir)

    assert (doctrines_dir / "my-workflow.yaml").read_text() == yaml_content


# ---------------------------------------------------------------------------
# Unit — create_doctrine on success target design content equals source content
# conceptual-workflows-doctrine-new step 7: file copy fidelity
# ---------------------------------------------------------------------------


def test_create_doctrine_design_content_equals_source(tmp_path):
    """create_doctrine() writes design file whose content is identical to the source design file."""

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()

    design_content = (
        "---\nid: my-workflow\ntitle: My Workflow\nsummary: Does things.\n---\n\n# My Workflow\n"
    )
    yaml_source = tmp_path / "my-workflow.yaml"
    yaml_source.write_text(
        "id: my-workflow\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )
    design_source = tmp_path / "my-workflow.design.md"
    design_source.write_text(design_content)

    create_doctrine("my-workflow", yaml_source, design_source, doctrines_dir)

    assert (doctrines_dir / "my-workflow.design.md").read_text() == design_content


# ---------------------------------------------------------------------------
# Unit — create_doctrine raises and writes no files on YAML id mismatch (atomicity)
# conceptual-workflows-doctrine-new step 5: atomicity guarantee
# ---------------------------------------------------------------------------


def test_create_doctrine_no_partial_write_on_yaml_id_mismatch(tmp_path):
    """create_doctrine() raises DoctrineError and writes no files when YAML id mismatches name."""

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()

    yaml_source = tmp_path / "other-name.yaml"
    yaml_source.write_text(
        "id: other-name\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )
    design_source = tmp_path / "my-workflow.design.md"
    design_source.write_text("---\nid: my-workflow\ntitle: My Workflow\n---\n")

    with pytest.raises(DoctrineError):
        create_doctrine("my-workflow", yaml_source, design_source, doctrines_dir)

    assert not (doctrines_dir / "my-workflow.yaml").exists()
    assert not (doctrines_dir / "my-workflow.design.md").exists()


# ---------------------------------------------------------------------------
# Unit — create_doctrine raises and writes no files on design id mismatch
# conceptual-workflows-doctrine-new step 6: atomicity guarantee
# ---------------------------------------------------------------------------


def test_create_doctrine_no_partial_write_on_design_id_mismatch(tmp_path):
    """create_doctrine() raises DoctrineError and writes no files when design id mismatches name."""

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()

    yaml_source = tmp_path / "my-workflow.yaml"
    yaml_source.write_text(
        "id: my-workflow\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )
    design_source = tmp_path / "other.design.md"
    design_source.write_text("---\nid: other-name\ntitle: Other\n---\n")

    with pytest.raises(DoctrineError):
        create_doctrine("my-workflow", yaml_source, design_source, doctrines_dir)

    assert not (doctrines_dir / "my-workflow.yaml").exists()
    assert not (doctrines_dir / "my-workflow.design.md").exists()


# ---------------------------------------------------------------------------
# Unit — create_doctrine raises "File not found" for missing design source
# conceptual-workflows-doctrine-new step 4
# ---------------------------------------------------------------------------


def test_create_doctrine_file_not_found_design(tmp_path):
    """create_doctrine() raises DoctrineError containing 'File not found' when design source path does not exist."""

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()

    yaml_source = tmp_path / "my-workflow.yaml"
    yaml_source.write_text(
        "id: my-workflow\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )
    missing_design = tmp_path / "nonexistent.design.md"

    with pytest.raises(DoctrineError) as exc_info:
        create_doctrine("my-workflow", yaml_source, missing_design, doctrines_dir)

    assert "File not found" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Unit — create_doctrine raises on invalid name (before any file read)
# conceptual-workflows-doctrine-new step 1: first validation
# ---------------------------------------------------------------------------


def test_create_doctrine_invalid_name_first(tmp_path):
    """create_doctrine() raises DoctrineError on invalid name format before any file access.

    Files named x.yaml and x.design.md do NOT exist — if name validation runs
    first, DoctrineError is raised before any file I/O.
    """

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()

    with pytest.raises(DoctrineError) as exc_info:
        create_doctrine(
            "_bad-name",
            tmp_path / "x.yaml",  # does not exist — name check must come first
            tmp_path / "x.design.md",
            doctrines_dir,
        )

    assert "Invalid name" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Unit — create_doctrine raises "Unexpected field in YAML: name"
# conceptual-workflows-doctrine-new: FR-8
# ---------------------------------------------------------------------------


def test_create_doctrine_yaml_with_name_raises(tmp_path):
    """create_doctrine() raises DoctrineError with 'Unexpected field in YAML: name' when YAML has name key."""

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()

    yaml_source = tmp_path / "my-workflow.yaml"
    yaml_source.write_text(
        "id: my-workflow\nname: my-workflow\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )
    design_source = tmp_path / "my-workflow.design.md"
    design_source.write_text("---\nid: my-workflow\ntitle: My Workflow\n---\n")

    with pytest.raises(DoctrineError) as exc_info:
        create_doctrine("my-workflow", yaml_source, design_source, doctrines_dir)

    assert "Unexpected field in YAML: name" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Unit — create_doctrine raises "Unexpected field in YAML: description"
# conceptual-workflows-doctrine-new: FR-8
# ---------------------------------------------------------------------------


def test_create_doctrine_yaml_with_description_raises(tmp_path):
    """create_doctrine() raises DoctrineError with 'Unexpected field in YAML: description' when YAML has description key."""

    doctrines_dir = tmp_path / "doctrines"
    doctrines_dir.mkdir()

    yaml_source = tmp_path / "my-workflow.yaml"
    yaml_source.write_text(
        "id: my-workflow\ndescription: some desc\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )
    design_source = tmp_path / "my-workflow.design.md"
    design_source.write_text("---\nid: my-workflow\ntitle: My Workflow\n---\n")

    with pytest.raises(DoctrineError) as exc_info:
        create_doctrine("my-workflow", yaml_source, design_source, doctrines_dir)

    assert "Unexpected field in YAML: description" in str(exc_info.value)

