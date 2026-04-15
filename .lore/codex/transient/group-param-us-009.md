---
id: group-param-us-009
title: US-009 Enriched --help teaches --group and slash-delimited filter
summary: Enriched Click help text on the four entity new subcommands gains a --group line and a nested-path example, and the five list subcommands gain a line noting slash-delimited filter tokens, matching ADR-008 teaching contract.
type: user-story
status: final
---

## Metadata

- **ID:** US-009
- **Status:** final
- **Epic:** Help + teaching
- **Author:** Business Analyst
- **Date:** 2026-04-15
- **PRD:** `lore codex show group-param-prd`
- **Tech Spec:** `lore codex show group-param-tech-spec`

---

## Story

As an AI orchestrator agent learning Lore through `--help`, I want `lore doctrine new --help`, `lore knight new --help`, `lore watcher new --help`, `lore artifact new --help`, and the five corresponding `list --help` commands to teach me the `--group` option and the slash-delimited filter grammar with a nested-path example, so that I can discover and use the feature without reading external docs.

## Context

Fulfills functional requirements FR-16 and FR-17 and honours ADR-008 (`decisions-008-help-as-teaching-interface`), which mandates enriched `--help` as the primary teaching interface for AI agents. Every new flag and every user-visible behaviour change in this feature must surface in `--help` in the same commit.

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: Doctrine new help contains --group line and nested example

**When** the user runs `lore doctrine new --help`
**Then** stdout contains the substring `--group`, contains a nested example whose group token uses `/` as the separator (e.g. `seo-analysis/keyword-analysers`), and exit code is 0.

#### Scenario 2: Knight new help contains --group

**When** the user runs `lore knight new --help`
**Then** stdout contains `--group` and a nested example, and exit code is 0.

#### Scenario 3: Watcher new help contains --group

**When** the user runs `lore watcher new --help`
**Then** stdout contains `--group` and a nested example, and exit code is 0.

#### Scenario 4: Artifact new help contains --group

**When** the user runs `lore artifact new --help`
**Then** stdout contains `--group` and a nested example, and exit code is 0.

#### Scenario 5: Doctrine list help documents slash-delimited filter

**When** the user runs `lore doctrine list --help`
**Then** stdout contains a line describing `--filter` and makes clear that filter tokens are slash-delimited (e.g. by showing `--filter a/b/c` in an example), and exit code is 0.

#### Scenario 6: All five list commands advertise slash-delimited filter

**When** the user runs `lore knight list --help`, `lore watcher list --help`, `lore artifact list --help`, and `lore codex list --help`
**Then** each output contains a line that advertises slash-delimited filter tokens via an example containing at least one `/`, and each exits 0.

#### Scenario 7: No new subcommand help still shows hyphen-joined examples

**When** the user runs any of the nine help commands above
**Then** none of the outputs contain a hyphen-joined group example of the form `xxx-yyy` as the filter or group token (only actual single-segment hyphenated names like `keyword-ranker` are allowed — the separator between levels must be `/`).

### Unit Test Scenarios

- [ ] `lore.cli.doctrine_new`: Click command's help text literal contains `--group` and contains a `/` in an example
- [ ] `lore.cli.knight_new`: same assertion
- [ ] `lore.cli.watcher_new`: same assertion
- [ ] `lore.cli.artifact_new`: same assertion
- [ ] `lore.cli.doctrine_list`: Click command's help text documents the slash-delimited filter grammar
- [ ] `lore.cli.knight_list`: same assertion
- [ ] `lore.cli.watcher_list`: same assertion
- [ ] `lore.cli.artifact_list`: same assertion
- [ ] `lore.cli.codex_list`: same assertion

---

## Out of Scope

- Core validation or mkdir logic (covered by US-001..US-005)
- Codex doc updates outside of CLI help text (covered in lock-step by the implementation mission per PRD FR-18 — not a BA story)
- Any change to `--help` for unrelated commands

---

## References

- PRD: `lore codex show group-param-prd`
- Tech Spec: `lore codex show group-param-tech-spec`
- ADR: `lore codex show decisions-008-help-as-teaching-interface`
- Workflow: `lore codex show conceptual-workflows-help`

---

## Tech Notes

### Implementation Approach

- `src/lore/cli.py` — enrich the Click `help` / docstring on the four `new` subcommands and the five `list` subcommands. Each is a simple docstring edit (Click uses the function docstring or a `help=` kwarg on the `@command` decorator; current handlers rely on the function docstring).
  - `doctrine_new` (line ~1248): docstring gains `--group` description plus a nested example such as `lore doctrine new keyword-ranker --group seo-analysis/keyword-analysers -f ranker.yaml -d ranker.design.md`. Also add `@click.option("--group", default=None, help="Nested subdirectory under .lore/doctrines/ (slash-delimited).")` — the option's own help string is the primary teaching surface.
  - `knight_new` (line ~1015): analogous `--group` help plus example `lore knight new on-prd-ready --group feature-implementation --from persona.md`.
  - `watcher_new` (line ~2611): analogous example `lore watcher new nightly --group team-a/triggers -f w.yaml`.
  - `artifact_new` (new subcommand from US-004): example `lore artifact new fi-review --group codex/templates --from review.md`.
  - `doctrine_list`, `knight_list`, `watcher_list`, `artifact_list`, `codex_list`: docstring gains a line about `--filter` accepting slash-delimited tokens, e.g. `lore artifact list --filter default/codex`. Update each `@click.option("--filter", ...)` `help=` string so the per-option help reads "Filter by slash-delimited group token (e.g. a/b/c). Can be repeated."
- ADR-008 compliance: enrichment is on the command level, not the group level — matches the ADR's scoping rule.

### Test File Locations

- Unit: `tests/unit/test_scaffold.py` already performs Click help-text assertions; add a new `tests/unit/test_help_enrichment.py` OR extend the existing scaffold file with a dedicated `TestGroupParamHelpEnrichment` class.
- E2E: new `tests/e2e/test_help_group_param.py` exercising `--help` via the Click runner for each of the nine commands.

### Test Stubs

```python
# tests/e2e/test_help_group_param.py — new file
"""anchor: conceptual-workflows-help (ADR-008 teaching contract)"""

import re

_HYPHEN_GROUP_TOKEN_RE = re.compile(r"--filter\s+[a-z0-9]+-[a-z0-9]+(?!/)")

@pytest.mark.parametrize("cmd", [
    ["doctrine", "new", "--help"],
    ["knight", "new", "--help"],
    ["watcher", "new", "--help"],
    ["artifact", "new", "--help"],
])
def test_new_help_contains_group_and_nested_example(runner, cmd):
    # Scenarios 1-4 — cites conceptual-workflows-help
    result = runner.invoke(main, cmd)
    assert result.exit_code == 0
    assert "--group" in result.output
    # Nested example: some token containing at least one '/'
    assert re.search(r"--group\s+\S*/\S+", result.output) or re.search(r"/[a-z][a-z0-9\-_]+", result.output)

def test_doctrine_list_help_shows_slash_filter(runner):
    # Scenario 5 — cites conceptual-workflows-help
    result = runner.invoke(main, ["doctrine", "list", "--help"])
    assert result.exit_code == 0
    assert "--filter" in result.output
    assert re.search(r"--filter\s+\S*/\S+", result.output) or "/b/c" in result.output

@pytest.mark.parametrize("cmd", [
    ["knight", "list", "--help"],
    ["watcher", "list", "--help"],
    ["artifact", "list", "--help"],
    ["codex", "list", "--help"],
])
def test_all_list_help_advertise_slash_filter(runner, cmd):
    # Scenario 6 — cites conceptual-workflows-help
    result = runner.invoke(main, cmd)
    assert result.exit_code == 0
    assert "/" in result.output  # at least one slash in example region
    assert "--filter" in result.output

@pytest.mark.parametrize("cmd", [
    ["doctrine", "new", "--help"],
    ["knight", "new", "--help"],
    ["watcher", "new", "--help"],
    ["artifact", "new", "--help"],
    ["doctrine", "list", "--help"],
    ["knight", "list", "--help"],
    ["watcher", "list", "--help"],
    ["artifact", "list", "--help"],
    ["codex", "list", "--help"],
])
def test_no_hyphen_joined_group_examples(runner, cmd):
    # Scenario 7 — no old-form examples leak through
    result = runner.invoke(main, cmd)
    assert result.exit_code == 0
    # Assert no "--filter xxx-yyy" or "--group xxx-yyy" where xxx-yyy is intended as
    # a multi-level separator (single hyphenated names like "keyword-ranker" are allowed).
    assert not _HYPHEN_GROUP_TOKEN_RE.search(result.output)
```

```python
# tests/unit/test_help_enrichment.py — new file (or folded into test_scaffold.py)
# anchor: conceptual-workflows-help

@pytest.mark.parametrize("handler_name", [
    "doctrine_new", "knight_new", "watcher_new", "artifact_new",
])
def test_new_click_help_contains_group_and_slash(handler_name):
    # AC unit: Click command docstring/help carries --group + slash example
    from lore import cli
    cmd = getattr(cli, handler_name)
    # Click decorators wrap the function; the help surface is cmd.help or the docstring
    help_text = (cmd.help or cmd.callback.__doc__ or "") + " ".join(
        p.help or "" for p in cmd.params if hasattr(p, "help")
    )
    assert "--group" in help_text
    assert "/" in help_text

@pytest.mark.parametrize("handler_name", [
    "doctrine_list", "knight_list", "watcher_list", "artifact_list", "codex_list",
])
def test_list_click_help_documents_slash_filter(handler_name):
    # AC unit: Click command help documents slash-delimited filter
    from lore import cli
    cmd = getattr(cli, handler_name)
    help_text = (cmd.help or cmd.callback.__doc__ or "") + " ".join(
        p.help or "" for p in cmd.params if hasattr(p, "help")
    )
    assert "--filter" in help_text
    assert "/" in help_text
```

### Complexity Estimate

**S** — docstring / `help=` string edits only, plus two parametrised test modules. No runtime logic change.
