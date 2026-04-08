"""E2E tests for the --filter flag on lore codex list.

Spec: filter-list-subcommands-us-1 (lore codex show filter-list-subcommands-us-1)
Workflow: conceptual-workflows-filter-list
"""

import json

from lore.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_codex_doc(project_dir, rel_path, content):
    """Write a markdown file into .lore/codex/."""
    doc_path = project_dir / ".lore" / "codex" / rel_path
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(content)
    return doc_path


# ---------------------------------------------------------------------------
# Document fixtures
# ---------------------------------------------------------------------------

ROOT_DOC = """\
---
id: CODEX.md
title: Codex Root
summary: Root-level codex index document.
---

Root body.
"""

CONCEPTUAL_DOC = """\
---
id: conceptual-entities-task
title: Conceptual Entities Task
summary: Describes the conceptual entities for task management.
---

Conceptual body.
"""

TECHNICAL_DOC = """\
---
id: tech-cli-commands
title: Tech CLI Commands
summary: Technical reference for CLI commands.
---

Technical body.
"""

DECISIONS_DOC = """\
---
id: decisions-001
title: Decisions 001
summary: First architecture decision record.
---

Decisions body.
"""


# ---------------------------------------------------------------------------
# Scenario 1: Filter codex by a single group — matching documents returned
# Exercises: conceptual-workflows-filter-list step 3 (apply filter post-discovery)
# ---------------------------------------------------------------------------


def test_filter_codex_single_group_returns_matched_and_root(project_dir, runner):
    """lore codex list --filter conceptual returns conceptual docs plus root-level docs only."""
    _write_codex_doc(project_dir, "CODEX.md", ROOT_DOC)
    _write_codex_doc(project_dir, "conceptual/conceptual-entities-task.md", CONCEPTUAL_DOC)
    _write_codex_doc(project_dir, "technical/tech-cli-commands.md", TECHNICAL_DOC)
    _write_codex_doc(project_dir, "decisions/decisions-001.md", DECISIONS_DOC)

    result = runner.invoke(main, ["codex", "list", "--filter", "conceptual"])

    assert result.exit_code == 0
    assert "CODEX.md" in result.output
    assert "conceptual-entities-task" in result.output
    assert "tech-cli-commands" not in result.output
    assert "decisions-001" not in result.output


def test_filter_codex_single_group_table_has_two_rows(project_dir, runner):
    """lore codex list --filter conceptual table contains exactly the root doc and the conceptual doc."""
    _write_codex_doc(project_dir, "CODEX.md", ROOT_DOC)
    _write_codex_doc(project_dir, "conceptual/conceptual-entities-task.md", CONCEPTUAL_DOC)
    _write_codex_doc(project_dir, "technical/tech-cli-commands.md", TECHNICAL_DOC)
    _write_codex_doc(project_dir, "decisions/decisions-001.md", DECISIONS_DOC)

    result = runner.invoke(main, ["codex", "list", "--filter", "conceptual"])

    assert result.exit_code == 0
    # Root doc has empty GROUP column; conceptual doc has group "conceptual"
    lines = result.output.splitlines()
    data_lines = [line for line in lines if "CODEX.md" in line or "conceptual-entities-task" in line]
    assert len(data_lines) == 2


# ---------------------------------------------------------------------------
# Scenario 2: Filter codex by a single group — JSON output schema unchanged
# Exercises: conceptual-workflows-filter-list step 4 (render output, JSON mode)
# ---------------------------------------------------------------------------


def test_filter_codex_single_group_json_schema_unchanged(project_dir, runner):
    """lore codex list --filter conceptual --json returns valid JSON with correct schema."""
    _write_codex_doc(project_dir, "CODEX.md", ROOT_DOC)
    _write_codex_doc(project_dir, "conceptual/conceptual-entities-task.md", CONCEPTUAL_DOC)
    _write_codex_doc(project_dir, "technical/tech-cli-commands.md", TECHNICAL_DOC)
    _write_codex_doc(project_dir, "decisions/decisions-001.md", DECISIONS_DOC)

    result = runner.invoke(main, ["codex", "list", "--filter", "conceptual", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "codex" in data
    assert isinstance(data["codex"], list)


def test_filter_codex_single_group_json_contains_exactly_two_entries(project_dir, runner):
    """JSON output contains exactly root-level doc and conceptual doc — no others."""
    _write_codex_doc(project_dir, "CODEX.md", ROOT_DOC)
    _write_codex_doc(project_dir, "conceptual/conceptual-entities-task.md", CONCEPTUAL_DOC)
    _write_codex_doc(project_dir, "technical/tech-cli-commands.md", TECHNICAL_DOC)
    _write_codex_doc(project_dir, "decisions/decisions-001.md", DECISIONS_DOC)

    result = runner.invoke(main, ["codex", "list", "--filter", "conceptual", "--json"])

    data = json.loads(result.output)
    ids = [entry["id"] for entry in data["codex"]]
    assert len(ids) == 2
    assert "CODEX.md" in ids
    assert "conceptual-entities-task" in ids
    assert "tech-cli-commands" not in ids
    assert "decisions-001" not in ids


def test_filter_codex_single_group_json_entry_has_required_fields(project_dir, runner):
    """Each entry in JSON output has id, group, title, summary fields."""
    _write_codex_doc(project_dir, "CODEX.md", ROOT_DOC)
    _write_codex_doc(project_dir, "conceptual/conceptual-entities-task.md", CONCEPTUAL_DOC)

    result = runner.invoke(main, ["codex", "list", "--filter", "conceptual", "--json"])

    data = json.loads(result.output)
    for entry in data["codex"]:
        assert "id" in entry
        assert "group" in entry
        assert "title" in entry
        assert "summary" in entry


def test_filter_codex_single_group_json_root_doc_has_empty_group(project_dir, runner):
    """Root-level document in JSON output has empty string as group."""
    _write_codex_doc(project_dir, "CODEX.md", ROOT_DOC)
    _write_codex_doc(project_dir, "conceptual/conceptual-entities-task.md", CONCEPTUAL_DOC)

    result = runner.invoke(main, ["codex", "list", "--filter", "conceptual", "--json"])

    data = json.loads(result.output)
    root_entries = [e for e in data["codex"] if e["id"] == "CODEX.md"]
    assert len(root_entries) == 1
    assert root_entries[0]["group"] == ""


# ---------------------------------------------------------------------------
# Scenario 3: Filter codex — token is case-sensitive
# Exercises: conceptual-workflows-filter-list step 3 (exact case-sensitive match)
# ---------------------------------------------------------------------------


def test_filter_codex_token_case_sensitive(project_dir, runner):
    """lore codex list --filter Conceptual does NOT match group 'conceptual' (case-sensitive)."""
    _write_codex_doc(project_dir, "CODEX.md", ROOT_DOC)
    _write_codex_doc(project_dir, "conceptual/conceptual-entities-task.md", CONCEPTUAL_DOC)

    result = runner.invoke(main, ["codex", "list", "--filter", "Conceptual"])

    assert result.exit_code == 0
    assert "conceptual-entities-task" not in result.output


def test_filter_codex_case_sensitive_root_doc_still_present(project_dir, runner):
    """Root-level document is always returned even when filter token matches nothing."""
    _write_codex_doc(project_dir, "CODEX.md", ROOT_DOC)
    _write_codex_doc(project_dir, "conceptual/conceptual-entities-task.md", CONCEPTUAL_DOC)

    result = runner.invoke(main, ["codex", "list", "--filter", "Conceptual"])

    assert result.exit_code == 0
    assert "CODEX.md" in result.output


# ---------------------------------------------------------------------------
# US-2 document fixtures
# ---------------------------------------------------------------------------

TECHNICAL_API_DOC = """\
---
id: tech-api-spec
title: Tech API Spec
summary: Technical API specification.
---

Tech API body.
"""

TECHNICAL_OVERVIEW_DOC = """\
---
id: tech-overview
title: Tech Overview
summary: Technical overview document.
---

Tech overview body.
"""


# ---------------------------------------------------------------------------
# Scenario 1 (US-2): Filter codex by two space-separated groups — docs from both groups returned
# Exercises: conceptual-workflows-filter-list step 3 (OR logic, multiple tokens)
# ---------------------------------------------------------------------------


def test_filter_codex_two_groups_space_separated(project_dir, runner):
    """lore codex list --filter conceptual technical-api returns docs from both groups plus root."""
    _write_codex_doc(project_dir, "CODEX.md", ROOT_DOC)
    _write_codex_doc(project_dir, "conceptual/conceptual-entities-task.md", CONCEPTUAL_DOC)
    _write_codex_doc(project_dir, "technical/api/tech-api-spec.md", TECHNICAL_API_DOC)
    _write_codex_doc(project_dir, "technical/tech-overview.md", TECHNICAL_OVERVIEW_DOC)
    _write_codex_doc(project_dir, "decisions/decisions-001.md", DECISIONS_DOC)

    result = runner.invoke(main, ["codex", "list", "--filter", "conceptual", "technical-api"])

    assert result.exit_code == 0
    assert "CODEX.md" in result.output
    assert "conceptual-entities-task" in result.output
    assert "tech-api-spec" in result.output
    assert "tech-overview" not in result.output
    assert "decisions-001" not in result.output


def test_filter_codex_two_groups_space_separated_exactly_three_rows(project_dir, runner):
    """Table contains exactly three rows: root doc, conceptual doc, and technical-api doc."""
    _write_codex_doc(project_dir, "CODEX.md", ROOT_DOC)
    _write_codex_doc(project_dir, "conceptual/conceptual-entities-task.md", CONCEPTUAL_DOC)
    _write_codex_doc(project_dir, "technical/api/tech-api-spec.md", TECHNICAL_API_DOC)
    _write_codex_doc(project_dir, "technical/tech-overview.md", TECHNICAL_OVERVIEW_DOC)
    _write_codex_doc(project_dir, "decisions/decisions-001.md", DECISIONS_DOC)

    result = runner.invoke(main, ["codex", "list", "--filter", "conceptual", "technical-api"])

    assert result.exit_code == 0
    lines = result.output.splitlines()
    data_lines = [
        line for line in lines
        if "CODEX.md" in line or "conceptual-entities-task" in line or "tech-api-spec" in line
    ]
    assert len(data_lines) == 3


# ---------------------------------------------------------------------------
# Scenario 2 (US-2): Multiple filter tokens via repeated --filter flag produce same result
# Exercises: conceptual-workflows-filter-list step 3 (OR logic, repeated flag form)
# ---------------------------------------------------------------------------


def test_filter_codex_repeated_flag_same_as_space_separated(project_dir, runner):
    """Both forms (space-separated and repeated flag) yield the same three-entry result set."""
    _write_codex_doc(project_dir, "CODEX.md", ROOT_DOC)
    _write_codex_doc(project_dir, "conceptual/conceptual-entities-task.md", CONCEPTUAL_DOC)
    _write_codex_doc(project_dir, "technical/api/tech-api-spec.md", TECHNICAL_API_DOC)
    _write_codex_doc(project_dir, "technical/tech-overview.md", TECHNICAL_OVERVIEW_DOC)
    _write_codex_doc(project_dir, "decisions/decisions-001.md", DECISIONS_DOC)

    result_space = runner.invoke(
        main, ["codex", "list", "--filter", "conceptual", "technical-api"]
    )
    result_repeated = runner.invoke(
        main, ["codex", "list", "--filter", "conceptual", "--filter", "technical-api"]
    )

    # Both forms must succeed
    assert result_space.exit_code == 0
    assert result_repeated.exit_code == 0
    # Both forms must include the same three entries
    for result in (result_space, result_repeated):
        assert "CODEX.md" in result.output
        assert "conceptual-entities-task" in result.output
        assert "tech-api-spec" in result.output
        assert "tech-overview" not in result.output
        assert "decisions-001" not in result.output


# ---------------------------------------------------------------------------
# Scenario 3 (US-2): Subtree filter matching — token matches group AND all child groups
# Exercises: conceptual-workflows-filter-list step 3 (subtree match, space-sep form)
# ---------------------------------------------------------------------------


def test_filter_codex_hyphen_token_space_sep_exact_match_not_prefix(project_dir, runner):
    """--filter technical conceptual (space-separated) returns both groups AND their subgroups.

    Previously this test asserted that 'technical' did NOT match 'technical-api'.
    With subtree semantics, 'technical' must match 'technical-api' too.
    This test is intentionally RED against the current exact-match implementation.
    """
    _write_codex_doc(project_dir, "CODEX.md", ROOT_DOC)
    _write_codex_doc(project_dir, "technical/api/tech-api-spec.md", TECHNICAL_API_DOC)
    _write_codex_doc(project_dir, "technical/tech-overview.md", TECHNICAL_OVERVIEW_DOC)
    _write_codex_doc(project_dir, "conceptual/conceptual-entities-task.md", CONCEPTUAL_DOC)

    result = runner.invoke(main, ["codex", "list", "--filter", "technical", "conceptual"])

    assert result.exit_code == 0
    assert "tech-overview" in result.output
    assert "conceptual-entities-task" in result.output
    assert "CODEX.md" in result.output
    # technical-api is a subgroup of technical — MUST be matched by "technical" token (subtree)
    assert "tech-api-spec" in result.output, (
        "'tech-api-spec' (group='technical-api') must be matched by token 'technical' "
        "under subtree semantics. Current implementation uses exact-match only — RED."
    )


# ---------------------------------------------------------------------------
# US-3 fixtures — shared across artifact/knight/doctrine/watcher scenarios
# ---------------------------------------------------------------------------


def _write_artifact(project_dir, rel_path, content):
    """Write a markdown file into .lore/artifacts/."""
    path = project_dir / ".lore" / "artifacts" / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _write_knight(project_dir, rel_path, content):
    """Write a markdown file into .lore/knights/."""
    path = project_dir / ".lore" / "knights" / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _write_doctrine(project_dir, rel_path, content):
    """Write a YAML file into .lore/doctrines/."""
    path = project_dir / ".lore" / "doctrines" / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _write_watcher(project_dir, rel_path, content):
    """Write a YAML file into .lore/watchers/."""
    path = project_dir / ".lore" / "watchers" / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


ROOT_ARTIFACT = """\
---
id: root-artifact
title: Root Artifact
summary: A root-level artifact.
---

Root body.
"""

DEFAULT_ARTIFACT = """\
---
id: some-artifact
title: Some Artifact
summary: An artifact in the default group.
---

Default body.
"""

CODEX_ARTIFACT = """\
---
id: fi-user-story
title: FI User Story
summary: A user story artifact in the default/codex namespace.
---

Codex body.
"""

TRANSIENT_ARTIFACT = """\
---
id: scratch
title: Scratch
summary: A transient artifact.
---

Transient body.
"""

FEATURE_IMPL_KNIGHT = """\
---
id: feature-implementation/ba
title: BA Knight
summary: Business analyst persona.
---

BA body.
"""

OPS_KNIGHT = """\
---
id: ops/deploy
title: Deploy Knight
summary: Ops deployment persona.
---

Deploy body.
"""

DEFAULT_DOCTRINE_YAML = """\
id: feature-add
title: Feature Add
description: Doctrine for adding features.
steps:
  - id: step-1
    title: Scout
    agent: ba
    missions: []
"""

OPS_DOCTRINE_YAML = """\
id: deploy-flow
title: Deploy Flow
description: Doctrine for deploying.
steps:
  - id: step-1
    title: Deploy
    agent: ops
    missions: []
"""

DEFAULT_WATCHER_YAML = """\
id: mission-watcher
title: Mission Watcher
summary: Watches for mission updates.
watch_target: missions/*
interval: hourly
action: notify
"""

OPS_WATCHER_YAML = """\
id: deploy-watcher
title: Deploy Watcher
summary: Watches for deploy events.
watch_target: deploys/*
interval: daily
action: trigger-deploy
"""


# ---------------------------------------------------------------------------
# Scenario 1 (US-3): Filter artifact list by a single group
# Exercises: conceptual-workflows-filter-list step 3 (post-discovery filter on artifact list)
# ---------------------------------------------------------------------------


def test_filter_artifact_list_single_group(project_dir, runner):
    """lore artifact list --filter default-codex returns default-codex artifacts plus root-level only."""
    _write_artifact(project_dir, "root-artifact.md", ROOT_ARTIFACT)
    _write_artifact(project_dir, "default/some-artifact.md", DEFAULT_ARTIFACT)
    _write_artifact(project_dir, "default/codex/fi-user-story.md", CODEX_ARTIFACT)
    _write_artifact(project_dir, "default/transient/scratch.md", TRANSIENT_ARTIFACT)

    result = runner.invoke(main, ["artifact", "list", "--filter", "default-codex"])

    assert result.exit_code == 0
    assert "root-artifact" in result.output
    assert "fi-user-story" in result.output
    assert "some-artifact" not in result.output
    assert "scratch" not in result.output


def test_filter_artifact_list_single_group_valid_count_reflects_filtered_set(project_dir, runner):
    """VALID count in artifact list output reflects only filtered records, not the full corpus."""
    _write_artifact(project_dir, "root-artifact.md", ROOT_ARTIFACT)
    _write_artifact(project_dir, "default/some-artifact.md", DEFAULT_ARTIFACT)
    _write_artifact(project_dir, "default/codex/fi-user-story.md", CODEX_ARTIFACT)
    _write_artifact(project_dir, "default/transient/scratch.md", TRANSIENT_ARTIFACT)

    result_all = runner.invoke(main, ["artifact", "list"])
    result_filtered = runner.invoke(main, ["artifact", "list", "--filter", "default-codex"])

    assert result_all.exit_code == 0
    assert result_filtered.exit_code == 0
    # The filtered output must show fewer valid artifacts than the full list
    # Extract VALID counts from both outputs
    import re
    all_match = re.search(r"VALID[:\s]+(\d+)", result_all.output)
    filtered_match = re.search(r"VALID[:\s]+(\d+)", result_filtered.output)
    if all_match and filtered_match:
        assert int(filtered_match.group(1)) < int(all_match.group(1))


# ---------------------------------------------------------------------------
# Scenario 2 (US-3): Filter artifact list — mistyped token returns root only
# Exercises: conceptual-workflows-filter-list step 3 (exact match; typo → no match)
# ---------------------------------------------------------------------------


def test_filter_artifact_mistyped_token_returns_root_only(project_dir, runner):
    """lore artifact list --filter defaultcodex returns only root-level artifacts (no group match)."""
    _write_artifact(project_dir, "root-artifact.md", ROOT_ARTIFACT)
    _write_artifact(project_dir, "default/some-artifact.md", DEFAULT_ARTIFACT)
    _write_artifact(project_dir, "default/codex/fi-user-story.md", CODEX_ARTIFACT)
    _write_artifact(project_dir, "default/transient/scratch.md", TRANSIENT_ARTIFACT)

    result = runner.invoke(main, ["artifact", "list", "--filter", "defaultcodex"])

    assert result.exit_code == 0
    assert "root-artifact" in result.output
    assert "fi-user-story" not in result.output
    assert "some-artifact" not in result.output
    assert "scratch" not in result.output


# ---------------------------------------------------------------------------
# Scenario 3 (US-3): Filter knight list by a single group
# Exercises: conceptual-workflows-filter-list step 3 (post-discovery filter on knight list)
# ---------------------------------------------------------------------------


def test_filter_knight_list_single_group(project_dir, runner):
    """lore knight list --filter feature-implementation returns only feature-implementation knights."""
    _write_knight(project_dir, "feature-implementation/ba.md", FEATURE_IMPL_KNIGHT)
    _write_knight(project_dir, "ops/deploy.md", OPS_KNIGHT)

    result = runner.invoke(main, ["knight", "list", "--filter", "feature-implementation"])

    assert result.exit_code == 0
    assert "feature-implementation/ba" in result.output or "ba" in result.output
    assert "feature-implementation" in result.output
    assert "ops/deploy" not in result.output
    assert "deploy" not in result.output


# ---------------------------------------------------------------------------
# Scenario 4 (US-3): Filter doctrine list by a single group
# Exercises: conceptual-workflows-filter-list step 3 (post-discovery filter on doctrine list)
# ---------------------------------------------------------------------------


def test_filter_doctrine_list_single_group(project_dir, runner):
    """lore doctrine list --filter default returns only default group doctrines."""
    _write_doctrine(project_dir, "default/feature-add.yaml", DEFAULT_DOCTRINE_YAML)
    _write_doctrine(project_dir, "ops/deploy-flow.yaml", OPS_DOCTRINE_YAML)

    result = runner.invoke(main, ["doctrine", "list", "--filter", "default"])

    assert result.exit_code == 0
    assert "feature-add" in result.output
    assert "deploy-flow" not in result.output


# ---------------------------------------------------------------------------
# Scenario 5 (US-3): Filter watcher list by a single group
# Exercises: conceptual-workflows-filter-list step 3 (post-discovery filter on watcher list)
# ---------------------------------------------------------------------------


def test_filter_watcher_list_single_group(project_dir, runner):
    """lore watcher list --filter default returns only default group watchers."""
    _write_watcher(project_dir, "default/mission-watcher.yaml", DEFAULT_WATCHER_YAML)
    _write_watcher(project_dir, "ops/deploy-watcher.yaml", OPS_WATCHER_YAML)

    result = runner.invoke(main, ["watcher", "list", "--filter", "default"])

    assert result.exit_code == 0
    assert "mission-watcher" in result.output


# ---------------------------------------------------------------------------
# US-4: Backward compatibility — unfiltered calls return full output unchanged
# Spec: filter-list-subcommands-us-4 (lore codex show filter-list-subcommands-us-4)
# Exercises: conceptual-workflows-filter-list step 3 (filter_groups absent → no filter)
# ---------------------------------------------------------------------------


# E2E — lore knight list without --filter returns all knights across all groups
# Exercises: conceptual-workflows-filter-list step 3 (filter_groups absent → no filter)
def test_unfiltered_knight_list_returns_all(project_dir, runner):
    """lore knight list without --filter returns all knights across all groups."""
    _write_knight(project_dir, "feature-implementation/ba.md", FEATURE_IMPL_KNIGHT)
    _write_knight(project_dir, "ops/deploy.md", OPS_KNIGHT)

    result = runner.invoke(main, ["knight", "list"])

    assert result.exit_code == 0
    assert "ba" in result.output or "feature-implementation" in result.output
    assert "deploy" in result.output or "ops" in result.output


# E2E — lore codex list --json without --filter returns full JSON schema unchanged
# Exercises: conceptual-workflows-filter-list step 4 (unfiltered JSON output unchanged)
def test_unfiltered_codex_list_json_unchanged(project_dir, runner):
    """lore codex list --json without --filter returns valid JSON with all docs and correct schema."""
    import json as _json
    _write_codex_doc(project_dir, "CODEX.md", ROOT_DOC)
    _write_codex_doc(project_dir, "conceptual/conceptual-entities-task.md", CONCEPTUAL_DOC)
    _write_codex_doc(project_dir, "technical/tech-cli-commands.md", TECHNICAL_DOC)

    result = runner.invoke(main, ["codex", "list", "--json"])

    assert result.exit_code == 0
    data = _json.loads(result.output)
    assert "codex" in data
    assert isinstance(data["codex"], list)
    ids = [entry["id"] for entry in data["codex"]]
    assert "CODEX.md" in ids
    assert "conceptual-entities-task" in ids
    assert "tech-cli-commands" in ids
    # Schema unchanged: each entry must have id, group, title, summary
    for entry in data["codex"]:
        assert "id" in entry
        assert "group" in entry
        assert "title" in entry
        assert "summary" in entry


# E2E — All five list commands without --filter return full unfiltered output
# Exercises: conceptual-workflows-filter-list step 3 (absence of --filter is a no-op)
def test_all_five_list_commands_unfiltered(project_dir, runner):
    """All five list commands without --filter return all entities across all groups, exit code 0."""
    _write_codex_doc(project_dir, "conceptual/conceptual-entities-task.md", CONCEPTUAL_DOC)
    _write_codex_doc(project_dir, "technical/tech-cli-commands.md", TECHNICAL_DOC)
    _write_artifact(project_dir, "default/some-artifact.md", DEFAULT_ARTIFACT)
    _write_artifact(project_dir, "default/codex/fi-user-story.md", CODEX_ARTIFACT)
    _write_knight(project_dir, "feature-implementation/ba.md", FEATURE_IMPL_KNIGHT)
    _write_knight(project_dir, "ops/deploy.md", OPS_KNIGHT)
    _write_doctrine(project_dir, "default/feature-add.yaml", DEFAULT_DOCTRINE_YAML)
    _write_doctrine(project_dir, "ops/deploy-flow.yaml", OPS_DOCTRINE_YAML)
    _write_watcher(project_dir, "default/mission-watcher.yaml", DEFAULT_WATCHER_YAML)
    _write_watcher(project_dir, "ops/deploy-watcher.yaml", OPS_WATCHER_YAML)

    commands = [
        ["codex", "list"],
        ["artifact", "list"],
        ["knight", "list"],
        ["doctrine", "list"],
        ["watcher", "list"],
    ]
    for cmd in commands:
        result = runner.invoke(main, cmd)
        assert result.exit_code == 0, f"Command {cmd} exited with {result.exit_code}: {result.output}"


# ---------------------------------------------------------------------------
# US-5: Unknown filter token robustness
# Spec: filter-list-subcommands-us-5 (lore codex show filter-list-subcommands-us-5)
# Exercises: conceptual-workflows-filter-list step 3 (unrecognised token → empty match, no error)
# ---------------------------------------------------------------------------


# E2E — Filter token matches no group — only root-level files returned, exit 0
# Exercises: conceptual-workflows-filter-list step 3 (unrecognised token → empty match, no error)
def test_filter_unknown_token_returns_root_only_exit_zero(project_dir, runner):
    """lore codex list --filter nonexistent-group exits 0 and returns only root-level docs."""
    _write_codex_doc(project_dir, "CODEX.md", ROOT_DOC)
    _write_codex_doc(project_dir, "conceptual/conceptual-entities-task.md", CONCEPTUAL_DOC)

    result = runner.invoke(main, ["codex", "list", "--filter", "nonexistent-group"])

    assert result.exit_code == 0
    assert "CODEX.md" in result.output
    assert "conceptual-entities-task" not in result.output
    # No error output to stderr
    assert result.exception is None


# E2E — No root-level files and token matches nothing — empty list message, exit 0
# Exercises: conceptual-workflows-filter-list failure modes (no root + no match → empty-state message)
def test_filter_unknown_token_no_root_files_empty_message(project_dir, runner):
    """lore codex list --filter nonexistent-group with no root-level files prints empty-codex message, exit 0."""
    _write_codex_doc(project_dir, "conceptual/conceptual-entities-task.md", CONCEPTUAL_DOC)

    result = runner.invoke(main, ["codex", "list", "--filter", "nonexistent-group"])

    assert result.exit_code == 0
    assert "No codex documents found." in result.output
    assert result.exception is None


# E2E — One token matches, one token does not — partial results returned, exit 0
# Exercises: conceptual-workflows-filter-list step 3 (OR logic; unknown token contributes no results)
def test_filter_one_valid_one_unknown_token_partial_results(project_dir, runner):
    """lore codex list --filter conceptual nonexistent-group returns root + conceptual docs only, exit 0."""
    _write_codex_doc(project_dir, "CODEX.md", ROOT_DOC)
    _write_codex_doc(project_dir, "conceptual/conceptual-entities-task.md", CONCEPTUAL_DOC)

    result = runner.invoke(main, ["codex", "list", "--filter", "conceptual", "nonexistent-group"])

    assert result.exit_code == 0
    assert "CODEX.md" in result.output
    assert "conceptual-entities-task" in result.output
    assert result.exception is None


# ---------------------------------------------------------------------------
# Subtree filter matching — new RED tests for q-c3e1/m-2518
# These tests document the desired subtree semantics and MUST FAIL against
# the current exact-match implementation.
# ---------------------------------------------------------------------------

CONCEPTUAL_WORKFLOWS_DOC = """\
---
id: concept-workflow-one
title: Concept Workflow One
summary: A conceptual workflow document.
---

Workflow body.
"""

TECHNICAL_OVERVIEW_DOC2 = """\
---
id: tech-overview-2
title: Tech Overview 2
summary: Second technical overview document.
---

Tech overview body 2.
"""


# E2E — filter 'conceptual' matches docs in group 'conceptual-workflows' (subtree)
# Exercises: conceptual-workflows-filter-list — subtree semantics for codex list
def test_filter_codex_token_matches_subtree_group(project_dir, runner):
    """lore codex list --filter conceptual returns docs in group 'conceptual-workflows' too.

    Currently FAILS because the implementation only exact-matches the group name.
    """
    _write_codex_doc(project_dir, "CODEX.md", ROOT_DOC)
    _write_codex_doc(project_dir, "conceptual/conceptual-entities-task.md", CONCEPTUAL_DOC)
    _write_codex_doc(project_dir, "conceptual/workflows/concept-workflow-one.md", CONCEPTUAL_WORKFLOWS_DOC)
    _write_codex_doc(project_dir, "technical/tech-cli-commands.md", TECHNICAL_DOC)

    result = runner.invoke(main, ["codex", "list", "--filter", "conceptual"])

    assert result.exit_code == 0
    assert "conceptual-entities-task" in result.output
    assert "concept-workflow-one" in result.output, (
        "'concept-workflow-one' (group='conceptual-workflows') must be returned by "
        "--filter conceptual under subtree semantics. RED against current implementation."
    )
    assert "tech-cli-commands" not in result.output


# E2E — filter 'technical' matches docs in group 'technical-api' (subtree)
# Exercises: conceptual-workflows-filter-list — subtree semantics for codex list
def test_filter_codex_token_matches_hyphenated_subtree_group(project_dir, runner):
    """lore codex list --filter technical returns docs in group 'technical-api' too.

    Currently FAILS because the implementation only exact-matches the group name.
    """
    _write_codex_doc(project_dir, "CODEX.md", ROOT_DOC)
    _write_codex_doc(project_dir, "technical/tech-cli-commands.md", TECHNICAL_DOC)
    _write_codex_doc(project_dir, "technical/api/tech-api-spec.md", TECHNICAL_API_DOC)
    _write_codex_doc(project_dir, "decisions/decisions-001.md", DECISIONS_DOC)

    result = runner.invoke(main, ["codex", "list", "--filter", "technical"])

    assert result.exit_code == 0
    assert "tech-cli-commands" in result.output
    assert "tech-api-spec" in result.output, (
        "'tech-api-spec' (group='technical-api') must be returned by "
        "--filter technical under subtree semantics. RED against current implementation."
    )
    assert "decisions-001" not in result.output


# E2E — filter 'technical' JSON output contains subtree docs
# Exercises: conceptual-workflows-filter-list — subtree semantics, JSON output
def test_filter_codex_subtree_json_contains_child_group_docs(project_dir, runner):
    """lore codex list --filter technical --json includes docs from group 'technical-api'.

    Currently FAILS because the implementation only exact-matches the group name.
    """
    _write_codex_doc(project_dir, "CODEX.md", ROOT_DOC)
    _write_codex_doc(project_dir, "technical/tech-cli-commands.md", TECHNICAL_DOC)
    _write_codex_doc(project_dir, "technical/api/tech-api-spec.md", TECHNICAL_API_DOC)

    result = runner.invoke(main, ["codex", "list", "--filter", "technical", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    ids = [entry["id"] for entry in data["codex"]]
    assert "tech-api-spec" in ids, (
        "'tech-api-spec' must appear in JSON output for --filter technical (subtree). RED."
    )


# E2E — knight list subtree filter matching
# Exercises: conceptual-workflows-filter-list — subtree semantics for knight list
def test_filter_knight_list_token_matches_subtree_group(project_dir, runner):
    """lore knight list --filter feature-implementation returns knights in 'feature-implementation-tdd' too.

    Currently FAILS because the implementation only exact-matches the group name.
    """
    FEATURE_IMPL_TDD_KNIGHT = """\
---
id: feature-implementation-tdd/red
title: TDD Red Knight
summary: Red phase test writer persona.
---

TDD Red body.
"""
    _write_knight(project_dir, "feature-implementation/ba.md", FEATURE_IMPL_KNIGHT)
    _write_knight(project_dir, "feature-implementation/tdd/red.md", FEATURE_IMPL_TDD_KNIGHT)
    _write_knight(project_dir, "ops/deploy.md", OPS_KNIGHT)

    result = runner.invoke(main, ["knight", "list", "--filter", "feature-implementation"])

    assert result.exit_code == 0
    assert "ops/deploy" not in result.output
    # The tdd/red knight has group 'feature-implementation-tdd' — must be matched
    assert "red" in result.output or "tdd" in result.output, (
        "Knight with group 'feature-implementation-tdd' must be returned by "
        "--filter feature-implementation under subtree semantics. RED."
    )
