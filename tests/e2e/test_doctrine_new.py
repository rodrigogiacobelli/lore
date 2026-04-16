"""E2E tests for lore doctrine new — two-file create workflow.

Spec: doctrine-design-file-us-007 (lore codex show doctrine-design-file-us-007)
Workflow: conceptual-workflows-doctrine-new (lore codex show conceptual-workflows-doctrine-new)
"""

import json

from lore.cli import main


# ---------------------------------------------------------------------------
# Scenario 1: Both files created on valid input
# conceptual-workflows-doctrine-new step 7-8: write both files, print success
# ---------------------------------------------------------------------------


def test_doctrine_new_creates_both_files(runner, project_dir, tmp_path):
    """lore doctrine new creates both .yaml and .design.md in doctrines_dir on valid input."""
    yaml_file = tmp_path / "my-workflow.yaml"
    yaml_file.write_text(
        "id: my-workflow\nsteps:\n"
        "  - id: step-one\n    title: First step\n    type: knight\n    knight: some-knight\n"
    )
    design_file = tmp_path / "my-workflow.design.md"
    design_file.write_text(
        "---\nid: my-workflow\ntitle: My Workflow\nsummary: Does things.\n---\n\n# My Workflow\n"
    )
    result = runner.invoke(
        main,
        ["doctrine", "new", "my-workflow", "-f", str(yaml_file), "-d", str(design_file)],
    )
    assert result.exit_code == 0
    assert "Created doctrine my-workflow" in result.output
    doctrines_dir = project_dir / ".lore" / "doctrines"
    assert (doctrines_dir / "my-workflow.yaml").exists()
    assert (doctrines_dir / "my-workflow.design.md").exists()


def test_doctrine_new_success_shows_in_doctrine_show(runner, project_dir, tmp_path):
    """After lore doctrine new, lore doctrine show succeeds."""
    yaml_file = tmp_path / "my-workflow.yaml"
    yaml_file.write_text(
        "id: my-workflow\nsteps:\n"
        "  - id: step-one\n    title: First step\n    type: knight\n    knight: some-knight\n"
    )
    design_file = tmp_path / "my-workflow.design.md"
    design_file.write_text(
        "---\nid: my-workflow\ntitle: My Workflow\nsummary: Does things.\n---\n\n# My Workflow\n"
    )
    runner.invoke(
        main,
        ["doctrine", "new", "my-workflow", "-f", str(yaml_file), "-d", str(design_file)],
    )
    result = runner.invoke(main, ["doctrine", "show", "my-workflow"])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Scenario 2: Missing -f flag fails with error
# conceptual-workflows-doctrine-new step 2: -f required
# ---------------------------------------------------------------------------


def test_doctrine_new_missing_f_flag_fails(runner, project_dir, tmp_path):
    """lore doctrine new without -f prints an error to stderr and exits 1."""
    design_file = tmp_path / "my-workflow.design.md"
    design_file.write_text("---\nid: my-workflow\n---\n")
    result = runner.invoke(
        main,
        ["doctrine", "new", "my-workflow", "-d", str(design_file)],
    )
    assert result.exit_code == 1
    assert "-f/--from is required" in (result.output + (result.stderr or ""))


def test_doctrine_new_missing_f_flag_writes_no_files(runner, project_dir, tmp_path):
    """lore doctrine new without -f writes no files to doctrines_dir."""
    design_file = tmp_path / "my-workflow.design.md"
    design_file.write_text("---\nid: my-workflow\n---\n")
    runner.invoke(
        main,
        ["doctrine", "new", "my-workflow", "-d", str(design_file)],
    )
    doctrines_dir = project_dir / ".lore" / "doctrines"
    assert not (doctrines_dir / "my-workflow.yaml").exists()
    assert not (doctrines_dir / "my-workflow.design.md").exists()


# ---------------------------------------------------------------------------
# Scenario 3: Missing -d flag fails with error
# conceptual-workflows-doctrine-new step 2: -d required
# ---------------------------------------------------------------------------


def test_doctrine_new_missing_d_flag_fails(runner, project_dir, tmp_path):
    """lore doctrine new without -d prints an error to stderr and exits 1."""
    yaml_file = tmp_path / "my-workflow.yaml"
    yaml_file.write_text("id: my-workflow\nsteps: []\n")
    result = runner.invoke(
        main,
        ["doctrine", "new", "my-workflow", "-f", str(yaml_file)],
    )
    assert result.exit_code == 1
    assert "-d/--design is required" in (result.output + (result.stderr or ""))


def test_doctrine_new_missing_d_flag_writes_no_files(runner, project_dir, tmp_path):
    """lore doctrine new without -d writes no files to doctrines_dir."""
    yaml_file = tmp_path / "my-workflow.yaml"
    yaml_file.write_text("id: my-workflow\nsteps: []\n")
    runner.invoke(
        main,
        ["doctrine", "new", "my-workflow", "-f", str(yaml_file)],
    )
    doctrines_dir = project_dir / ".lore" / "doctrines"
    assert not (doctrines_dir / "my-workflow.yaml").exists()


# ---------------------------------------------------------------------------
# Scenario 4: Scaffold path removed — no flags fails with error
# conceptual-workflows-doctrine-new: old scaffold path no longer exists
# ---------------------------------------------------------------------------


def test_doctrine_new_no_flags_no_scaffold(runner, project_dir):
    """lore doctrine new without -f or -d exits 1 and does NOT generate a scaffold YAML."""
    result = runner.invoke(main, ["doctrine", "new", "my-workflow"])
    assert result.exit_code == 1
    doctrines_dir = project_dir / ".lore" / "doctrines"
    assert not (doctrines_dir / "my-workflow.yaml").exists()


# ---------------------------------------------------------------------------
# Scenario 5: Invalid name fails with error
# conceptual-workflows-doctrine-new step 2: validate_name() from validators.py
# ---------------------------------------------------------------------------


def test_doctrine_new_invalid_name_fails(runner, project_dir, tmp_path):
    """lore doctrine new with an invalid name (_bad) prints 'Invalid name' and exits 1."""
    yaml_file = tmp_path / "bad.yaml"
    yaml_file.write_text("id: _bad\nsteps: []\n")
    design_file = tmp_path / "bad.design.md"
    design_file.write_text("---\nid: _bad\n---\n")
    result = runner.invoke(
        main,
        ["doctrine", "new", "_bad", "-f", str(yaml_file), "-d", str(design_file)],
    )
    assert result.exit_code == 1
    assert "Invalid name" in (result.output + (result.stderr or ""))


def test_doctrine_new_invalid_name_writes_no_files(runner, project_dir, tmp_path):
    """lore doctrine new with invalid name writes no files to doctrines_dir."""
    yaml_file = tmp_path / "bad.yaml"
    yaml_file.write_text("id: _bad\nsteps: []\n")
    design_file = tmp_path / "bad.design.md"
    design_file.write_text("---\nid: _bad\n---\n")
    runner.invoke(
        main,
        ["doctrine", "new", "_bad", "-f", str(yaml_file), "-d", str(design_file)],
    )
    doctrines_dir = project_dir / ".lore" / "doctrines"
    assert not (doctrines_dir / "_bad.yaml").exists()


# ---------------------------------------------------------------------------
# Scenario 6: Duplicate doctrine fails with error
# conceptual-workflows-doctrine-new step 3: duplicate check
# ---------------------------------------------------------------------------


def test_doctrine_new_duplicate_fails(runner, project_dir, tmp_path):
    """lore doctrine new fails with 'already exists' error when the doctrine already exists."""
    doctrines_dir = project_dir / ".lore" / "doctrines"
    (doctrines_dir / "my-workflow.yaml").write_text("id: my-workflow\nsteps: []\n")
    yaml_file = tmp_path / "my-workflow.yaml"
    yaml_file.write_text(
        "id: my-workflow\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )
    design_file = tmp_path / "my-workflow.design.md"
    design_file.write_text("---\nid: my-workflow\n---\n")
    result = runner.invoke(
        main,
        ["doctrine", "new", "my-workflow", "-f", str(yaml_file), "-d", str(design_file)],
    )
    assert result.exit_code == 1
    assert "already exists" in (result.output + (result.stderr or ""))


def test_doctrine_new_duplicate_does_not_overwrite(runner, project_dir, tmp_path):
    """lore doctrine new does not overwrite an existing doctrine."""
    doctrines_dir = project_dir / ".lore" / "doctrines"
    original_content = "id: my-workflow\nsteps: []\n"
    (doctrines_dir / "my-workflow.yaml").write_text(original_content)
    yaml_file = tmp_path / "my-workflow.yaml"
    yaml_file.write_text(
        "id: my-workflow\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )
    design_file = tmp_path / "my-workflow.design.md"
    design_file.write_text("---\nid: my-workflow\n---\n")
    runner.invoke(
        main,
        ["doctrine", "new", "my-workflow", "-f", str(yaml_file), "-d", str(design_file)],
    )
    assert (doctrines_dir / "my-workflow.yaml").read_text() == original_content


# ---------------------------------------------------------------------------
# Scenario 7: YAML id mismatch fails with error
# conceptual-workflows-doctrine-new step 4-5: _validate_yaml_schema id check
# ---------------------------------------------------------------------------


def test_doctrine_new_yaml_id_mismatch_fails(runner, project_dir, tmp_path):
    """lore doctrine new fails when YAML id does not match command argument."""
    yaml_file = tmp_path / "other-name.yaml"
    yaml_file.write_text(
        "id: other-name\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )
    design_file = tmp_path / "my-workflow.design.md"
    design_file.write_text("---\nid: my-workflow\n---\n")
    result = runner.invoke(
        main,
        ["doctrine", "new", "my-workflow", "-f", str(yaml_file), "-d", str(design_file)],
    )
    assert result.exit_code == 1
    assert "does not match" in (result.output + (result.stderr or ""))


def test_doctrine_new_yaml_id_mismatch_writes_no_files(runner, project_dir, tmp_path):
    """lore doctrine new writes no files when YAML id doesn't match name argument."""
    yaml_file = tmp_path / "other-name.yaml"
    yaml_file.write_text(
        "id: other-name\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )
    design_file = tmp_path / "my-workflow.design.md"
    design_file.write_text("---\nid: my-workflow\n---\n")
    runner.invoke(
        main,
        ["doctrine", "new", "my-workflow", "-f", str(yaml_file), "-d", str(design_file)],
    )
    doctrines_dir = project_dir / ".lore" / "doctrines"
    assert not (doctrines_dir / "my-workflow.yaml").exists()


# ---------------------------------------------------------------------------
# Scenario 8: Design file id mismatch fails with error
# conceptual-workflows-doctrine-new step 6: _validate_design_frontmatter id check
# ---------------------------------------------------------------------------


def test_doctrine_new_design_id_mismatch_fails(runner, project_dir, tmp_path):
    """lore doctrine new fails when design file id does not match command argument."""
    yaml_file = tmp_path / "my-workflow.yaml"
    yaml_file.write_text(
        "id: my-workflow\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )
    design_file = tmp_path / "other.design.md"
    design_file.write_text("---\nid: other-name\n---\n")
    result = runner.invoke(
        main,
        ["doctrine", "new", "my-workflow", "-f", str(yaml_file), "-d", str(design_file)],
    )
    assert result.exit_code == 1
    assert "Design file id" in (result.output + (result.stderr or ""))


# ---------------------------------------------------------------------------
# Scenario 9: YAML with legacy 'name' field fails
# conceptual-workflows-doctrine-new: FR-8 rejected fields
# ---------------------------------------------------------------------------


def test_doctrine_new_yaml_with_legacy_name_fails(runner, project_dir, tmp_path):
    """lore doctrine new fails with 'Unexpected field in YAML: name' when YAML has name key."""
    yaml_file = tmp_path / "my-workflow.yaml"
    yaml_file.write_text(
        "id: my-workflow\nname: my-workflow\n"
        "steps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )
    design_file = tmp_path / "my-workflow.design.md"
    design_file.write_text("---\nid: my-workflow\n---\n")
    result = runner.invoke(
        main,
        ["doctrine", "new", "my-workflow", "-f", str(yaml_file), "-d", str(design_file)],
    )
    assert result.exit_code == 1
    assert "Unknown property 'name'" in (result.output + (result.stderr or ""))


# ---------------------------------------------------------------------------
# Scenario 10: YAML with legacy 'description' field fails
# conceptual-workflows-doctrine-new: FR-8 rejected fields
# ---------------------------------------------------------------------------


def test_doctrine_new_yaml_with_legacy_description_fails(runner, project_dir, tmp_path):
    """lore doctrine new fails with 'Unexpected field in YAML: description' when YAML has description key."""
    yaml_file = tmp_path / "my-workflow.yaml"
    yaml_file.write_text(
        "id: my-workflow\ndescription: some desc\n"
        "steps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )
    design_file = tmp_path / "my-workflow.design.md"
    design_file.write_text("---\nid: my-workflow\n---\n")
    result = runner.invoke(
        main,
        ["doctrine", "new", "my-workflow", "-f", str(yaml_file), "-d", str(design_file)],
    )
    assert result.exit_code == 1
    assert "Unknown property 'description'" in (result.output + (result.stderr or ""))


# ---------------------------------------------------------------------------
# Scenario 11: Atomicity — no partial write on YAML validation failure
# conceptual-workflows-doctrine-new step 6: both files written or neither
# ---------------------------------------------------------------------------


def test_doctrine_new_atomic_no_partial_write(runner, project_dir, tmp_path):
    """lore doctrine new writes neither file when YAML validation fails (empty steps)."""
    yaml_file = tmp_path / "my-workflow.yaml"
    yaml_file.write_text("id: my-workflow\nsteps: []\n")  # empty steps → validation error
    design_file = tmp_path / "my-workflow.design.md"
    design_file.write_text(
        "---\nid: my-workflow\ntitle: My Workflow\n---\n"
    )
    result = runner.invoke(
        main,
        ["doctrine", "new", "my-workflow", "-f", str(yaml_file), "-d", str(design_file)],
    )
    assert result.exit_code == 1
    doctrines_dir = project_dir / ".lore" / "doctrines"
    assert not (doctrines_dir / "my-workflow.yaml").exists()
    assert not (doctrines_dir / "my-workflow.design.md").exists()


# ---------------------------------------------------------------------------
# Scenario 12: JSON mode on success
# conceptual-workflows-doctrine-new + conceptual-workflows-json-output
# ---------------------------------------------------------------------------


def test_doctrine_new_json_mode_success(runner, project_dir, tmp_path):
    """lore doctrine new --json prints JSON with name, yaml_filename, design_filename on success."""
    yaml_file = tmp_path / "my-workflow.yaml"
    yaml_file.write_text(
        "id: my-workflow\nsteps:\n  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )
    design_file = tmp_path / "my-workflow.design.md"
    design_file.write_text("---\nid: my-workflow\ntitle: My Workflow\nsummary: A workflow.\n---\n")
    result = runner.invoke(
        main,
        [
            "doctrine",
            "new",
            "my-workflow",
            "-f",
            str(yaml_file),
            "-d",
            str(design_file),
            "--json",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["name"] == "my-workflow"
    assert data["yaml_filename"] == "my-workflow.yaml"
    assert data["design_filename"] == "my-workflow.design.md"
    assert data["group"] is None


# ---------------------------------------------------------------------------
# Scenario 13: Source file not found fails with error
# conceptual-workflows-doctrine-new step 3: source file existence check
# ---------------------------------------------------------------------------


def test_doctrine_new_source_yaml_not_found(runner, project_dir, tmp_path):
    """lore doctrine new fails with 'File not found' when the -f source path does not exist."""
    design_file = tmp_path / "my-workflow.design.md"
    design_file.write_text("---\nid: my-workflow\n---\n")
    result = runner.invoke(
        main,
        [
            "doctrine",
            "new",
            "my-workflow",
            "-f",
            "/tmp/missing-nonexistent-lore-test.yaml",
            "-d",
            str(design_file),
        ],
    )
    assert result.exit_code == 1
    assert "File not found" in (result.output + (result.stderr or ""))


# ===========================================================================
# US-001 E2E tests — lore doctrine new --group
# Spec: group-param-us-001 (lore codex show group-param-us-001)
# Workflow: conceptual-workflows-doctrine-new
# ===========================================================================


def _write_doctrine_sources(tmp_path, yaml_name, design_name, *, name):
    yaml_file = tmp_path / yaml_name
    yaml_file.write_text(
        f"id: {name}\nsteps:\n"
        "  - id: step-one\n    title: First step\n    type: knight\n    knight: some-knight\n"
    )
    design_file = tmp_path / design_name
    design_file.write_text(
        f"---\nid: {name}\ntitle: {name}\nsummary: Does things.\n---\n\n# {name}\n"
    )
    return yaml_file, design_file


def test_doctrine_new_nested_happy_path(runner, project_dir, tmp_path):
    """lore doctrine new --group a/b creates yaml+design under nested subdirs."""
    yaml_file, design_file = _write_doctrine_sources(
        tmp_path, "ranker.yaml", "ranker.design.md", name="keyword-ranker"
    )
    result = runner.invoke(
        main,
        [
            "doctrine",
            "new",
            "keyword-ranker",
            "--group",
            "seo-analysis/keyword-analysers",
            "-f",
            str(yaml_file),
            "-d",
            str(design_file),
        ],
    )
    assert result.exit_code == 0
    assert (
        result.output.strip()
        == "Created doctrine keyword-ranker (group: seo-analysis/keyword-analysers)"
    )
    doctrines_dir = project_dir / ".lore" / "doctrines"
    assert (
        doctrines_dir / "seo-analysis" / "keyword-analysers" / "keyword-ranker.yaml"
    ).exists()
    assert (
        doctrines_dir
        / "seo-analysis"
        / "keyword-analysers"
        / "keyword-ranker.design.md"
    ).exists()


def test_doctrine_new_nested_json_envelope(runner, project_dir, tmp_path):
    """lore doctrine new --group ... --json emits full dict envelope with group and path."""
    yaml_file, design_file = _write_doctrine_sources(
        tmp_path, "ranker.yaml", "ranker.design.md", name="keyword-ranker"
    )
    result = runner.invoke(
        main,
        [
            "doctrine",
            "new",
            "keyword-ranker",
            "--group",
            "seo-analysis/keyword-analysers",
            "-f",
            str(yaml_file),
            "-d",
            str(design_file),
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == {
        "name": "keyword-ranker",
        "group": "seo-analysis/keyword-analysers",
        "yaml_filename": "keyword-ranker.yaml",
        "design_filename": "keyword-ranker.design.md",
        "path": ".lore/doctrines/seo-analysis/keyword-analysers/keyword-ranker.yaml",
    }


def test_doctrine_new_single_segment_group(runner, project_dir, tmp_path):
    """Single-segment --group writes under exactly one nested level."""
    yaml_file, design_file = _write_doctrine_sources(
        tmp_path, "seo.yaml", "seo.design.md", name="seo-tool"
    )
    result = runner.invoke(
        main,
        [
            "doctrine",
            "new",
            "seo-tool",
            "--group",
            "seo-analysis",
            "-f",
            str(yaml_file),
            "-d",
            str(design_file),
        ],
    )
    assert result.exit_code == 0
    assert result.output.strip() == "Created doctrine seo-tool (group: seo-analysis)"
    doctrines_dir = project_dir / ".lore" / "doctrines"
    assert (doctrines_dir / "seo-analysis" / "seo-tool.yaml").exists()
    assert (doctrines_dir / "seo-analysis" / "seo-tool.design.md").exists()


def test_doctrine_new_mkdir_idempotent(runner, project_dir, tmp_path):
    """Pre-existing target group dir does not cause error; files land inside it."""
    doctrines_dir = project_dir / ".lore" / "doctrines"
    (doctrines_dir / "existing-group").mkdir(parents=True)
    yaml_file, design_file = _write_doctrine_sources(
        tmp_path, "d.yaml", "d.design.md", name="new-doc"
    )
    result = runner.invoke(
        main,
        [
            "doctrine",
            "new",
            "new-doc",
            "--group",
            "existing-group",
            "-f",
            str(yaml_file),
            "-d",
            str(design_file),
        ],
    )
    assert result.exit_code == 0
    assert (doctrines_dir / "existing-group" / "new-doc.yaml").exists()
    assert (doctrines_dir / "existing-group" / "new-doc.design.md").exists()


def test_doctrine_new_duplicate_in_subtree_rejected(runner, project_dir, tmp_path):
    """Duplicate name anywhere under doctrines_dir is rejected regardless of --group."""
    doctrines_dir = project_dir / ".lore" / "doctrines"
    (doctrines_dir / "seo-analysis").mkdir(parents=True)
    (doctrines_dir / "seo-analysis" / "ranker.yaml").write_text(
        "id: ranker\nsteps:\n  - id: s\n    title: t\n    type: knight\n    knight: k\n"
    )
    (doctrines_dir / "seo-analysis" / "ranker.design.md").write_text(
        "---\nid: ranker\ntitle: Ranker\nsummary: S.\n---\n"
    )
    yaml_file, design_file = _write_doctrine_sources(
        tmp_path, "ranker.yaml", "ranker.design.md", name="ranker"
    )
    result = runner.invoke(
        main,
        [
            "doctrine",
            "new",
            "ranker",
            "--group",
            "other-feature",
            "-f",
            str(yaml_file),
            "-d",
            str(design_file),
        ],
    )
    assert result.exit_code == 1
    combined = result.output + (result.stderr or "")
    assert "already exists" in combined
    assert not (doctrines_dir / "other-feature").exists()


def test_doctrine_new_invalid_group_rejected(runner, project_dir, tmp_path):
    """Invalid --group value (path traversal) is rejected via validate_group before any write."""
    yaml_file, design_file = _write_doctrine_sources(
        tmp_path, "d.yaml", "d.design.md", name="new-doc"
    )
    result = runner.invoke(
        main,
        [
            "doctrine",
            "new",
            "new-doc",
            "--group",
            "../etc",
            "-f",
            str(yaml_file),
            "-d",
            str(design_file),
        ],
    )
    assert result.exit_code == 1
    combined = result.output + (result.stderr or "")
    assert "invalid group" in combined
    doctrines_dir = project_dir / ".lore" / "doctrines"
    assert not (doctrines_dir / "new-doc.yaml").exists()


# ---------------------------------------------------------------------------
# US-010 — Create-time validators delegate to lore.schemas
# Spec: schema-validation-us-010
# Workflow: conceptual-workflows-doctrine-new
# ---------------------------------------------------------------------------


def test_us010_doctrine_new_rejects_hallucinated_stability_field(runner, project_dir, tmp_path):
    """A design file with extra frontmatter key `stability` must be rejected via schema,
    with stderr mentioning additionalProperties or /stability, and no files written."""
    yaml_file = tmp_path / "fi.yaml"
    yaml_file.write_text(
        "id: fi\nsteps:\n"
        "  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )
    design_file = tmp_path / "fi.design.md"
    design_file.write_text(
        "---\nid: fi\ntitle: FI\nsummary: short.\nstability: stable\n---\n\n# body\n"
    )
    result = runner.invoke(
        main,
        ["doctrine", "new", "fi", "-f", str(yaml_file), "-d", str(design_file)],
    )
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr or "")
    assert ("additionalProperties" in combined) or ("/stability" in combined) or ("stability" in combined)
    doctrines_dir = project_dir / ".lore" / "doctrines"
    assert not (doctrines_dir / "fi.yaml").exists()
    assert not (doctrines_dir / "fi.design.md").exists()


def test_us010_doctrine_new_rejects_design_missing_summary(runner, project_dir, tmp_path):
    """Design file frontmatter missing `summary:` must surface the golden schema error."""
    yaml_file = tmp_path / "fi.yaml"
    yaml_file.write_text(
        "id: fi\nsteps:\n"
        "  - id: s1\n    title: S1\n    type: knight\n    knight: k\n"
    )
    design_file = tmp_path / "fi.design.md"
    design_file.write_text("---\nid: fi\ntitle: FI\n---\n\n# body\n")
    result = runner.invoke(
        main,
        ["doctrine", "new", "fi", "-f", str(yaml_file), "-d", str(design_file)],
    )
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr or "")
    assert "Missing required property 'summary'" in combined
    doctrines_dir = project_dir / ".lore" / "doctrines"
    assert not (doctrines_dir / "fi.yaml").exists()
