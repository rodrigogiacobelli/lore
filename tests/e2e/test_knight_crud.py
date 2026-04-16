"""E2E tests for `lore knight new` — US-002 (group-param-us-002).

Spec: group-param-us-002 (lore codex show group-param-us-002)
Workflow: conceptual-workflows-knight-crud
"""

import json

from lore.cli import main


PERSONA_MD = "---\nid: {name}\ntitle: T\nsummary: S\n---\n# body\n"


# ---------------------------------------------------------------------------
# Scenario 2: Root knight create — JSON envelope with group=None
# anchor: conceptual-workflows-json-output
# ---------------------------------------------------------------------------


class TestKnightNewRootJson:
    def test_root_json_exit_zero(self, runner, project_dir):
        # Spec: group-param-us-002 Scenario 2
        (project_dir / "reviewer.md").write_text(PERSONA_MD.format(name="reviewer"))
        result = runner.invoke(
            main,
            ["knight", "new", "reviewer", "--from", "reviewer.md", "--json"],
        )
        assert result.exit_code == 0

    def test_root_json_group_is_null(self, runner, project_dir):
        # Spec: group-param-us-002 Scenario 2 — group key is null at root
        (project_dir / "reviewer.md").write_text(PERSONA_MD.format(name="reviewer"))
        result = runner.invoke(
            main,
            ["knight", "new", "reviewer", "--from", "reviewer.md", "--json"],
        )
        payload = json.loads(result.output)
        assert payload["group"] is None

    def test_root_json_contains_path_and_name(self, runner, project_dir):
        # Spec: group-param-us-002 Tech Notes — JSON envelope returns full dict (group + path)
        (project_dir / "reviewer.md").write_text(PERSONA_MD.format(name="reviewer"))
        result = runner.invoke(
            main,
            ["knight", "new", "reviewer", "--from", "reviewer.md", "--json"],
        )
        payload = json.loads(result.output)
        assert payload["name"] == "reviewer"
        assert "path" in payload
        assert payload["path"].endswith(".lore/knights/reviewer.md")


# ---------------------------------------------------------------------------
# Scenario 3: Nested knight create — happy path with --group flag
# anchor: conceptual-workflows-knight-crud
# ---------------------------------------------------------------------------


class TestKnightNewNestedHappyPath:
    def test_nested_create_exit_zero(self, runner, project_dir):
        # Spec: group-param-us-002 Scenario 3
        (project_dir / "persona.md").write_text(PERSONA_MD.format(name="on-prd-ready"))
        result = runner.invoke(
            main,
            [
                "knight",
                "new",
                "on-prd-ready",
                "--group",
                "feature-implementation",
                "--from",
                "persona.md",
            ],
        )
        assert result.exit_code == 0

    def test_nested_create_stdout_includes_group(self, runner, project_dir):
        # Spec: group-param-us-002 Scenario 3 — stdout exact with group suffix
        (project_dir / "persona.md").write_text(PERSONA_MD.format(name="on-prd-ready"))
        result = runner.invoke(
            main,
            [
                "knight",
                "new",
                "on-prd-ready",
                "--group",
                "feature-implementation",
                "--from",
                "persona.md",
            ],
        )
        assert (
            result.output.strip()
            == "Created knight on-prd-ready (group: feature-implementation)"
        )

    def test_nested_create_file_in_group_dir(self, runner, project_dir):
        # Spec: group-param-us-002 Scenario 3 — file under group subdirectory
        (project_dir / "persona.md").write_text(PERSONA_MD.format(name="on-prd-ready"))
        runner.invoke(
            main,
            [
                "knight",
                "new",
                "on-prd-ready",
                "--group",
                "feature-implementation",
                "--from",
                "persona.md",
            ],
        )
        assert (
            project_dir
            / ".lore/knights/feature-implementation/on-prd-ready.md"
        ).exists()

    def test_nested_json_envelope_group_and_path(self, runner, project_dir):
        # Spec: group-param-us-002 Tech Notes — JSON envelope contains group + path
        (project_dir / "persona.md").write_text(PERSONA_MD.format(name="on-prd-ready"))
        result = runner.invoke(
            main,
            [
                "knight",
                "new",
                "on-prd-ready",
                "--group",
                "feature-implementation",
                "--from",
                "persona.md",
                "--json",
            ],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["group"] == "feature-implementation"
        assert payload["name"] == "on-prd-ready"
        assert payload["path"].endswith(
            ".lore/knights/feature-implementation/on-prd-ready.md"
        )


# ---------------------------------------------------------------------------
# Scenario 4: Nested knight — deep path auto-mkdir
# anchor: conceptual-workflows-knight-crud
# ---------------------------------------------------------------------------


class TestKnightNewDeepPathAutoMkdir:
    def test_deep_path_exit_zero(self, runner, project_dir):
        # Spec: group-param-us-002 Scenario 4
        (project_dir / "p.md").write_text(PERSONA_MD.format(name="lead"))
        result = runner.invoke(
            main,
            ["knight", "new", "lead", "--group", "team-a/reviewers", "--from", "p.md"],
        )
        assert result.exit_code == 0

    def test_deep_path_creates_intermediate_dirs(self, runner, project_dir):
        # Spec: group-param-us-002 Scenario 4 — mkdir parents=True
        (project_dir / "p.md").write_text(PERSONA_MD.format(name="lead"))
        runner.invoke(
            main,
            ["knight", "new", "lead", "--group", "team-a/reviewers", "--from", "p.md"],
        )
        assert (project_dir / ".lore/knights/team-a").is_dir()
        assert (project_dir / ".lore/knights/team-a/reviewers").is_dir()
        assert (project_dir / ".lore/knights/team-a/reviewers/lead.md").exists()


# ---------------------------------------------------------------------------
# Scenario 5: Duplicate name anywhere in subtree rejected
# anchor: conceptual-workflows-knight-crud
# ---------------------------------------------------------------------------


class TestKnightNewDuplicateSubtreeRejected:
    def test_duplicate_subtree_exit_one(self, runner, project_dir):
        # Spec: group-param-us-002 Scenario 5
        (project_dir / ".lore/knights/team-a").mkdir(parents=True)
        (project_dir / ".lore/knights/team-a/reviewer.md").write_text(
            PERSONA_MD.format(name="reviewer")
        )
        (project_dir / "p.md").write_text(PERSONA_MD.format(name="reviewer"))
        result = runner.invoke(
            main,
            ["knight", "new", "reviewer", "--group", "team-b", "--from", "p.md"],
        )
        assert result.exit_code == 1

    def test_duplicate_subtree_error_message(self, runner, project_dir):
        # Spec: group-param-us-002 Scenario 5 — stderr contains "already exists"
        (project_dir / ".lore/knights/team-a").mkdir(parents=True)
        (project_dir / ".lore/knights/team-a/reviewer.md").write_text(
            PERSONA_MD.format(name="reviewer")
        )
        (project_dir / "p.md").write_text(PERSONA_MD.format(name="reviewer"))
        result = runner.invoke(
            main,
            ["knight", "new", "reviewer", "--group", "team-b", "--from", "p.md"],
        )
        combined = result.output + (result.stderr or "")
        assert "already exists" in combined
        assert "reviewer" in combined


# ---------------------------------------------------------------------------
# US-010 — Create-time knight validator delegates to lore.schemas
# Spec: schema-validation-us-010
# Workflow: conceptual-workflows-knight-crud
# ---------------------------------------------------------------------------


_KNIGHT_NO_SUMMARY_MD = "---\nid: pm\ntitle: PM\n---\n# body\n"


def test_us010_knight_new_missing_summary_golden_error(runner, project_dir):
    """Missing `summary:` in knight frontmatter must surface the exact US-005 error text."""
    (project_dir / "p.md").write_text(_KNIGHT_NO_SUMMARY_MD)
    result = runner.invoke(main, ["knight", "new", "pm", "--from", "p.md"])
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr or "")
    assert "Missing required property 'summary'" in combined
    assert not (project_dir / ".lore" / "knights" / "pm.md").exists()


def test_us010_knight_new_rejects_extra_stability_field(runner, project_dir):
    """An extra frontmatter field must be rejected via schema additionalProperties."""
    body = "---\nid: pm-extra\ntitle: PM\nsummary: s\nstability: stable\n---\n# body\n"
    (project_dir / "p.md").write_text(body)
    result = runner.invoke(main, ["knight", "new", "pm-extra", "--from", "p.md"])
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr or "")
    assert ("additionalProperties" in combined) or ("stability" in combined)
    assert not (project_dir / ".lore" / "knights" / "pm-extra.md").exists()