"""E2E tests for the doctrine show command (text mode and JSON mode).

Spec: doctrine-design-file-us-004 (lore codex show doctrine-design-file-us-004)
Spec: doctrine-design-file-us-005 (lore codex show doctrine-design-file-us-005)
Workflow: conceptual-workflows-doctrine-show
"""

import json
from pathlib import Path

from lore.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_pair(project_dir, stem, yaml_content, design_content):
    """Write a paired .design.md + .yaml at the given stem path."""
    base = project_dir / ".lore" / "doctrines" / stem
    base.parent.mkdir(parents=True, exist_ok=True)
    Path(str(base) + ".design.md").write_text(design_content)
    Path(str(base) + ".yaml").write_text(yaml_content)


def _write_design(project_dir, stem, design_content):
    """Write only a .design.md (orphaned — no matching .yaml)."""
    base = project_dir / ".lore" / "doctrines" / stem
    base.parent.mkdir(parents=True, exist_ok=True)
    Path(str(base) + ".design.md").write_text(design_content)


def _write_yaml(project_dir, stem, yaml_content):
    """Write only a .yaml (YAML-only — no matching .design.md)."""
    base = project_dir / ".lore" / "doctrines" / stem
    base.parent.mkdir(parents=True, exist_ok=True)
    Path(str(base) + ".yaml").write_text(yaml_content)


# ---------------------------------------------------------------------------
# Scenario 1: Shows design file followed by separator followed by YAML
# conceptual-workflows-doctrine-show step 5: CLI prints design, "---", YAML verbatim
# ---------------------------------------------------------------------------


def test_doctrine_show_text_mode_verbatim_dump(project_dir, runner):
    """E2E Scenario 1: stdout shows raw design content, separator, raw YAML content."""
    design_content = (
        "---\n"
        "id: feature-implementation\n"
        "title: Feature Implementation\n"
        "summary: E2E spec-driven pipeline...\n"
        "---\n"
        "\n"
        "# Feature Implementation\n"
        "\n"
        "Some design content.\n"
    )
    yaml_content = (
        "id: feature-implementation\n"
        "steps:\n"
        "  - id: business-scout\n"
        "    title: Map codex from the business perspective\n"
        "    type: knight\n"
        "    knight: scout\n"
        "    priority: 2\n"
    )
    _write_pair(
        project_dir,
        "feature-implementation/feature-implementation",
        yaml_content,
        design_content,
    )
    result = runner.invoke(main, ["doctrine", "show", "feature-implementation"])
    assert result.exit_code == 0
    assert design_content in result.output
    assert "\n---\n" in result.output
    assert yaml_content in result.output
    # Verify order: design before YAML
    assert result.output.index(design_content) < result.output.index(yaml_content)


def test_doctrine_show_exit_code_zero_on_success(project_dir, runner):
    """E2E Scenario 1: exit code is 0 when both files exist."""
    _write_pair(
        project_dir,
        "feature-implementation/feature-implementation",
        yaml_content="id: feature-implementation\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
        design_content="---\nid: feature-implementation\ntitle: Feature Implementation\nsummary: Spec pipeline.\n---\n",
    )
    result = runner.invoke(main, ["doctrine", "show", "feature-implementation"])
    assert result.exit_code == 0


def test_doctrine_show_stdout_is_not_empty_on_success(project_dir, runner):
    """E2E Scenario 1: stdout contains output when doctrine is found."""
    _write_pair(
        project_dir,
        "feature-implementation/feature-implementation",
        yaml_content="id: feature-implementation\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
        design_content="---\nid: feature-implementation\ntitle: Feature Implementation\nsummary: Spec pipeline.\n---\n",
    )
    result = runner.invoke(main, ["doctrine", "show", "feature-implementation"])
    assert result.exit_code == 0
    assert result.output.strip() != ""


# ---------------------------------------------------------------------------
# Scenario 2: Missing design file exits with error
# conceptual-workflows-doctrine-show step 3 / error-handling
# ---------------------------------------------------------------------------


def test_doctrine_show_missing_design_file_exits_1(project_dir, runner):
    """E2E Scenario 2: missing design file → exit 1 with 'design file missing' error."""
    _write_yaml(
        project_dir,
        "feature-implementation/feature-implementation",
        "id: feature-implementation\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
    )
    result = runner.invoke(main, ["doctrine", "show", "feature-implementation"])
    assert result.exit_code == 1
    combined = result.output + (result.stderr if result.stderr else "")
    assert "feature-implementation" in combined
    assert "design file missing" in combined


def test_doctrine_show_missing_design_file_error_contains_exact_phrase(project_dir, runner):
    """E2E Scenario 2: error output contains exact phrase 'design file missing'."""
    _write_yaml(
        project_dir,
        "feature-implementation/feature-implementation",
        "id: feature-implementation\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
    )
    result = runner.invoke(main, ["doctrine", "show", "feature-implementation"])
    assert result.exit_code == 1
    combined = result.output + (result.stderr if result.stderr else "")
    # Must contain the new specific error phrase from show_doctrine()
    assert "design file missing" in combined


# ---------------------------------------------------------------------------
# Scenario 3: Missing YAML file exits with error
# conceptual-workflows-doctrine-show step 3 / error-handling
# ---------------------------------------------------------------------------


def test_doctrine_show_missing_yaml_file_exits_1(project_dir, runner):
    """E2E Scenario 3: missing YAML file → exit 1 with 'YAML file missing' error."""
    _write_design(
        project_dir,
        "feature-implementation/feature-implementation",
        "---\nid: feature-implementation\ntitle: Feature Implementation\n---\n",
    )
    result = runner.invoke(main, ["doctrine", "show", "feature-implementation"])
    assert result.exit_code == 1
    combined = result.output + (result.stderr if result.stderr else "")
    assert "YAML file missing" in combined


def test_doctrine_show_missing_yaml_file_references_id(project_dir, runner):
    """E2E Scenario 3: error message references the doctrine id."""
    _write_design(
        project_dir,
        "feature-implementation/feature-implementation",
        "---\nid: feature-implementation\ntitle: Feature Implementation\n---\n",
    )
    result = runner.invoke(main, ["doctrine", "show", "feature-implementation"])
    assert result.exit_code == 1
    combined = result.output + (result.stderr if result.stderr else "")
    assert "feature-implementation" in combined


# ---------------------------------------------------------------------------
# Scenario 4: Nonexistent doctrine exits with error
# conceptual-workflows-doctrine-show step 3 / error-handling
# ---------------------------------------------------------------------------


def test_doctrine_show_nonexistent_exits_1(project_dir, runner):
    """E2E Scenario 4: nonexistent doctrine → exit 1 via show_doctrine() DoctrineError."""
    result = runner.invoke(main, ["doctrine", "show", "nonexistent"])
    assert result.exit_code == 1
    combined = result.output + (result.stderr if result.stderr else "")
    # New behavior: show_doctrine() raises DoctrineError "Doctrine 'nonexistent' not found"
    # (note single quotes, not "not found in .lore/doctrines/" from the old code)
    assert "Doctrine 'nonexistent' not found" in combined


def test_doctrine_show_nonexistent_references_id_in_error(project_dir, runner):
    """E2E Scenario 4: error uses show_doctrine() single-quoted format, not old double-quoted."""
    result = runner.invoke(main, ["doctrine", "show", "nonexistent"])
    assert result.exit_code == 1
    combined = result.output + (result.stderr if result.stderr else "")
    # New behavior from show_doctrine(): single-quoted id, no "in .lore/doctrines/" suffix
    assert "Doctrine 'nonexistent' not found" in combined


# ---------------------------------------------------------------------------
# Scenario 5: Doctrine in a subdirectory is found by ID
# conceptual-workflows-doctrine-show step 2: recursive search
# ---------------------------------------------------------------------------


def test_doctrine_show_subdirectory_found(project_dir, runner):
    """E2E Scenario 5: doctrine nested in subdirectory is found by ID alone."""
    _write_pair(
        project_dir,
        "feature-implementation/quick-feature-implementation",
        yaml_content="id: quick-feature-implementation\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
        design_content="---\nid: quick-feature-implementation\ntitle: Quick Feature Implementation\n---\n",
    )
    result = runner.invoke(main, ["doctrine", "show", "quick-feature-implementation"])
    assert result.exit_code == 0
    assert "quick-feature-implementation" in result.output


def test_doctrine_show_subdirectory_output_contains_separator(project_dir, runner):
    """E2E Scenario 5: output from subdirectory doctrine still contains separator."""
    _write_pair(
        project_dir,
        "feature-implementation/quick-feature-implementation",
        yaml_content="id: quick-feature-implementation\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
        design_content="---\nid: quick-feature-implementation\ntitle: Quick Feature Implementation\n---\n",
    )
    result = runner.invoke(main, ["doctrine", "show", "quick-feature-implementation"])
    assert result.exit_code == 0
    assert "\n---\n" in result.output


# ===========================================================================
# US-005 JSON mode scenarios
# Spec: doctrine-design-file-us-005 (lore codex show doctrine-design-file-us-005)
# ===========================================================================


# ---------------------------------------------------------------------------
# Scenario 1: JSON output has correct shape on success
# conceptual-workflows-doctrine-show step 3-4 + conceptual-workflows-json-output
# ---------------------------------------------------------------------------


def test_doctrine_show_json_mode_correct_shape(project_dir, runner):
    """E2E Scenario 1 (JSON): stdout is valid JSON with {id, title, summary, design, steps}."""
    design_content = (
        "---\n"
        "id: feature-implementation\n"
        "title: Feature Implementation\n"
        "summary: E2E spec-driven pipeline...\n"
        "---\n"
        "\n"
        "# Feature Implementation\n"
    )
    yaml_content = (
        "id: feature-implementation\n"
        "steps:\n"
        "  - id: business-scout\n"
        "    title: Map codex from the business perspective\n"
        "    type: knight\n"
        "    knight: scout\n"
        "    priority: 2\n"
    )
    _write_pair(
        project_dir,
        "feature-implementation/feature-implementation",
        yaml_content,
        design_content,
    )
    result = runner.invoke(main, ["doctrine", "show", "feature-implementation", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["id"] == "feature-implementation"
    assert data["title"] == "Feature Implementation"
    assert data["summary"] == "E2E spec-driven pipeline..."
    assert isinstance(data["design"], str)
    assert design_content in data["design"]
    assert isinstance(data["steps"], list)
    step = data["steps"][0]
    assert step == {
        "id": "business-scout",
        "title": "Map codex from the business perspective",
        "priority": 2,
        "type": "knight",
        "knight": "scout",
        "notes": None,
        "needs": [],
    }


def test_doctrine_show_json_mode_exit_code_zero_on_success(project_dir, runner):
    """E2E Scenario 1 (JSON): exit code is 0 when doctrine is found."""
    _write_pair(
        project_dir,
        "feature-implementation/feature-implementation",
        yaml_content="id: feature-implementation\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
        design_content="---\nid: feature-implementation\ntitle: Feature Implementation\nsummary: Spec pipeline.\n---\n",
    )
    result = runner.invoke(main, ["doctrine", "show", "feature-implementation", "--json"])
    assert result.exit_code == 0


def test_doctrine_show_json_mode_output_is_valid_json(project_dir, runner):
    """E2E Scenario 1 (JSON): stdout is parseable JSON."""
    _write_pair(
        project_dir,
        "feature-implementation/feature-implementation",
        yaml_content="id: feature-implementation\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
        design_content="---\nid: feature-implementation\ntitle: Feature Implementation\nsummary: Spec pipeline.\n---\n",
    )
    result = runner.invoke(main, ["doctrine", "show", "feature-implementation", "--json"])
    assert result.exit_code == 0
    # Must not raise
    data = json.loads(result.output)
    assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# Scenario 2: JSON output error on missing design file
# conceptual-workflows-doctrine-show step 3 / conceptual-workflows-error-handling
# ---------------------------------------------------------------------------


def test_doctrine_show_json_error_missing_design(project_dir, runner):
    """E2E Scenario 2 (JSON): missing design file → exit 1, stdout has {"error": ...}."""
    _write_yaml(
        project_dir,
        "feature-implementation/feature-implementation",
        "id: feature-implementation\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
    )
    result = runner.invoke(main, ["doctrine", "show", "feature-implementation", "--json"])
    assert result.exit_code == 1
    data = json.loads(result.output)
    assert "error" in data
    assert "design file missing" in data["error"]


# ---------------------------------------------------------------------------
# Scenario 3: JSON output error on missing YAML file
# conceptual-workflows-doctrine-show step 3 / conceptual-workflows-error-handling
# ---------------------------------------------------------------------------


def test_doctrine_show_json_error_missing_yaml(project_dir, runner):
    """E2E Scenario 3 (JSON): missing YAML file → exit 1, stdout has {"error": ...}."""
    _write_design(
        project_dir,
        "feature-implementation/feature-implementation",
        "---\nid: feature-implementation\ntitle: Feature Implementation\n---\n",
    )
    result = runner.invoke(main, ["doctrine", "show", "feature-implementation", "--json"])
    assert result.exit_code == 1
    data = json.loads(result.output)
    assert "error" in data
    assert "YAML file missing" in data["error"]


# ---------------------------------------------------------------------------
# Scenario 4: raw_yaml key absent from JSON output
# conceptual-workflows-doctrine-show: raw_yaml is CLI-internal, not in JSON output
# ---------------------------------------------------------------------------


def test_doctrine_show_json_no_raw_yaml_key(project_dir, runner):
    """E2E Scenario 4 (JSON): JSON output does NOT contain 'raw_yaml' key."""
    _write_pair(
        project_dir,
        "feature-implementation/feature-implementation",
        yaml_content="id: feature-implementation\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
        design_content="---\nid: feature-implementation\ntitle: Feature Implementation\n---\n",
    )
    result = runner.invoke(main, ["doctrine", "show", "feature-implementation", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "raw_yaml" not in data


def test_doctrine_show_json_no_name_or_description_keys(project_dir, runner):
    """E2E Scenario 4 (JSON): JSON output does NOT contain 'name' or 'description' keys."""
    _write_pair(
        project_dir,
        "feature-implementation/feature-implementation",
        yaml_content="id: feature-implementation\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n",
        design_content="---\nid: feature-implementation\ntitle: Feature Implementation\n---\n",
    )
    result = runner.invoke(main, ["doctrine", "show", "feature-implementation", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "name" not in data
    assert "description" not in data


# ---------------------------------------------------------------------------
# Scenario 5: steps normalized — defaults applied for missing optional fields
# conceptual-workflows-doctrine-show step 4: _normalize() applied
# ---------------------------------------------------------------------------


def test_doctrine_show_json_steps_normalized(project_dir, runner):
    """E2E Scenario 5 (JSON): step defaults (priority=2, notes=None, needs=[]) applied."""
    _write_pair(
        project_dir,
        "my-doctrine",
        yaml_content=(
            "id: my-doctrine\n"
            "steps:\n"
            "  - id: step-one\n"
            "    title: First step\n"
            "    type: knight\n"
            "    knight: some-knight\n"
        ),
        design_content="---\nid: my-doctrine\ntitle: My Doctrine\n---\n",
    )
    result = runner.invoke(main, ["doctrine", "show", "my-doctrine", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    step = data["steps"][0]
    assert step["priority"] == 2
    assert step["notes"] is None
    assert step["needs"] == []


def test_doctrine_show_json_steps_all_seven_fields(project_dir, runner):
    """E2E Scenario 5 (JSON): each step has all seven fields: id, title, priority, type, knight, notes, needs."""
    _write_pair(
        project_dir,
        "my-doctrine",
        yaml_content=(
            "id: my-doctrine\n"
            "steps:\n"
            "  - id: step-one\n"
            "    title: First step\n"
            "    type: knight\n"
            "    knight: some-knight\n"
        ),
        design_content="---\nid: my-doctrine\ntitle: My Doctrine\n---\n",
    )
    result = runner.invoke(main, ["doctrine", "show", "my-doctrine", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    step = data["steps"][0]
    for field in ("id", "title", "priority", "type", "knight", "notes", "needs"):
        assert field in step, f"Missing field: {field}"
