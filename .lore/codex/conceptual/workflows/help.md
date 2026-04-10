---
id: conceptual-workflows-help
title: Help Output Contract
summary: >
  What the enriched --help output for each command group must contain — the teaching-interface contract established by decisions-008.
related: ["decisions-008-help-as-teaching-interface", "tech-cli-commands"]
stability: stable
---

# Help Output Contract

Every `lore` command and subcommand exposes `--help` text. The help text is the primary self-documentation surface for agents discovering the tool's capabilities. This document defines the contract for what each help output must include.

## Top-Level (`lore --help`)

The root help must describe:

- The two core entity types: `Quest` and `Mission`, with one-line definitions.
- The two supporting entities: `Knight` and `Doctrine`.
- A pointer to subcommand groups: `Run any command group with --help for details on that concept.`

Example (from the CLI source):

```
Lore — Agent Task Manager.

Lore organises agent work into two core entity types:

  Quest   — a body of work (feature, fix, or refactor).
  Mission — a single executable task assigned to an agent.

Supporting entities:

  Knight   — a reusable agent persona attached to missions.
  Doctrine — workflow templates that guide how missions are executed.

Run any command group with --help for details on that concept.
```

## Command Group Help

Each command group's help string (the docstring of the `@main.group()` function) must:

1. State what the group manages in one sentence.
2. Explain the primary use pattern with at least one example command.
3. Describe the relationship to other entities where relevant.

### `lore knight --help`

Must explain:
- Knights are reusable markdown files encoding how a worker agent approaches work.
- How to assign: `lore new mission -k <name>.md`.
- What happens on `lore show <mission-id>`: knight contents are included.
- Distinction: knights encode the "how"; mission descriptions encode the "what".

### `lore doctrine --help`

Must explain:
- Doctrines are YAML workflow templates describing step sequences and suggested knights.
- Doctrines have no execution engine — they are passive guidance read with `lore doctrine show <name>`.

### `lore artifact --help`

Must explain:
- Artifacts are reusable template files stored in `.lore/artifacts/`.
- Access is via stable ID using `lore artifact list` and `lore artifact show <id>`.
- Artifacts are read-only via the CLI.

### `lore codex --help`

Must explain:
- Codex is a set of typed markdown files maintained in `.lore/codex/`.
- Preference for multi-ID retrieval: `lore codex show id1 id2` over multiple calls.

### `lore new --help`

Must explain:
- Quest and Mission creation.
- That missions without `-q` are standalone.
- An example sequence: create a quest, then attach missions.

### `lore missions --help`

Must include:
- The four mission statuses: `open`, `in_progress`, `blocked`, `closed`.
- That `mission_type` is free-form and not interpreted by Lore.
- Pointer to `lore ready` for finding the next mission to dispatch.

### `lore oracle --help`

Must clarify:
- Reports are wiped and regenerated on every run.
- Do not store custom files in `.lore/reports/`.
- Intended for human stakeholders, not agent consumption.
- JSON output is not supported.

### `lore ready --help`

Must describe:
- Blocked and closed missions are excluded.
- Optional `count` argument for multiple results.

### `lore done --help`

Must describe:
- For missions: transitions to closed and unblocks dependents.
- For quests: use only when `auto_close` is disabled.

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| `--help` on any command | Help text to stdout | 0 |

## Out of Scope

- The exact wording of help text — the contract is the presence of documented concepts, not literal strings.
- Interactive help paging.
