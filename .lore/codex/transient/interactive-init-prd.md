---
id: interactive-init-prd
title: Interactive lore init and Skill Catalogue Consolidation — PRD
summary: An interactive lore init that asks which coding agent the project uses and
  whether agents read and write Lore's local files through the CLI or with their own
  tools, installs the seeded skills where that agent looks for them, and reconciles
  renamed or merged skills across any version upgrade through a hash manifest.
related:
- conceptual-workflows-lore-init
- tech-arch-initialized-project-structure
- tech-arch-agents-md
- tech-arch-source-layout
- tech-arch-api-facade
- decisions-001-dumb-infrastructure
- decisions-006-no-seed-content-tests
- decisions-010-public-api-stability
- decisions-011-api-parity-with-cli
- decisions-012-multi-value-cli-param-convention
- decisions-013-toml-for-config-yaml-for-glossary
- decisions-017-constrained-flags-use-click-choice
---

# Interactive `lore init` and Skill Catalogue Consolidation — PRD

**Author:** Product Manager
**Date:** 2026-08-24

---

## Executive Summary

`lore init` asks the human running it which coding agent the project uses and whether agents operate Lore's local files through the Lore CLI or with their own file tools. It then installs the seeded skills where that agent looks for them, writes the agent's instruction file, and records the answers in `.lore/config.toml`. On every later run it reconciles what it installed against what the current release ships, removing skills that have been renamed or merged and asking before it touches anything the user edited.

The feature also consolidates the seeded skill catalogue from fifteen skills to ten, in three families: memory, machinery, and workflow.

### What Makes This Special

The seeded skills stop being a single opinion about how agents must work. A project that wants every read and write to go through `lore` gets that; a project that would rather its agent use its own tools gets the same skills with the replaceable command layer swapped out. The choice is recorded once and survives upgrades.

---

## Project Classification

| Attribute | Value |
|-----------|-------|
| Project type | CLI tool and importable Python library |
| Primary users | AI coding agents (orchestrator and worker), human developers at a terminal, Realm via `from lore.api import ...`, and the downstream project that receives `src/lore/defaults/` |
| Scale | Single machine, one project per `.lore/` directory; ten seeded skills across at most five agent targets per project |

---

## Success Criteria

### User Success

A human initialising a project names their coding agent once and finds the skills where that agent already looks, with no manual copy step.

A human who prefers their agent to use its own file tools sets that once, and every seeded skill reflects it.

A human upgrading Lore from any earlier version finds renamed and merged skills cleaned up, learns where their customisations now belong, and never loses an edit without having agreed to it first.

A human running `lore init` in a script or CI pipeline sees no prompt and gets the same result as before this feature.

### Technical Success

| Metric | Baseline | Target | Timeline |
|--------|----------|--------|----------|
| Manual steps between `lore init` and a usable skill in Claude Code | 1 (copy `.lore/skills/` into `.claude/skills/`) | 0 | At release |
| Seeded skills | 15 | 10 | At release |
| Skills whose retirement is explained to the upgrading user | 0 | Every retired skill in the ledger | At release |
| `run_init()` calls in Realm requiring change | — | 0 | At release |
| Agent registry entries whose convention is unverified | — | 0 | At release |
| Entity types seeded by `lore init` with no `lore health` scope | 1 (skills) | 0 | At release |

---

## Product Scope

### MVP

- Interactive prompting in `lore init`, active only when standard output is a terminal.
- Prompt for the coding agents the project uses, from a seeded registry of verified conventions.
- Prompt for the access mode: agents use the Lore CLI for local files, or agents use their own tools.
- Prompt for which skill families to install.
- Prompt, when a selected agent's instruction file already exists without Lore's markers, for how to treat it.
- Prompt for appending Lore's entries to the project's root `.gitignore`.
- Prompt, when an agent with a native skills directory is selected, for whether the installed skills are tracked in version control.
- Prompt, when reconciliation finds skills the user has edited, for permission to overwrite them.
- A summary of every create, overwrite, and removal, confirmed before anything is written.
- A command-line flag for every prompt, so the whole flow is reachable without a terminal.
- Persistence of the answers in `.lore/config.toml`, reused on later runs unless `--reconfigure` is passed.
- An install manifest recording every file `lore init` writes and its hash.
- Reconciliation of the manifest against the current release on every run: create, overwrite, remove, or ask.
- A fallback for projects that predate the manifest, matching on-disk files against hashes Lore has shipped before.
- A retirement ledger naming where every removed skill went, quoted in the summary.
- Installation of skills only where the selected agent reads them.
- Access-mode injection into each seeded skill at install time, from one authored source per skill.
- The consolidated ten-skill catalogue, including `store-memory` with its reference files.
- `plan_init`, `apply_init` and `InitPlan` on the public API, with `run_init()` preserved as a no-argument call.
- Updates to `tech-arch-agents-md` and `conceptual-workflows-lore-init` so both describe the shipped behaviour.
- Regeneration of the known-key comment header in `.lore/config.toml` from the loader's own registry.
- A `skills` scope for `lore health`.
- Correction of the hardcoded schema version in the `lore init` database status message.
- An in-place amendment to ADR-001 admitting a human-first interactive command class, with a dated Status History row.

### Post-MVP

- Agent registry entries whose conventions are not yet verified.
- A prompt for installing skills at user scope rather than project scope.

### Out of Scope

- The seven agent conventions this PRD could not verify: Cline, Roo Code, Windsurf, Crush, Aider, Goose, and Grok. Users of those tools select `AGENTS.md` or `none`.
- A `lore skill` CLI command group. Skills stay seeded files with no retrieval path.
- Symlinking an agent's skills directory at `.lore/skills/`. ADR-001 targets Windows, where symlink creation needs elevated privileges.
- The shape of the `--json` envelope for `lore init`, its exit codes, and whether a `--dry-run` flag exists. These are Tech Spec decisions.
- Migrating the content of a skill the user edited into its renamed successor. Lore reports where the edits belong; the user moves them.
- Treating web research or agent-gathered documentation as an ingestion. `store-memory` writes a source snapshot only for an artifact authored outside the project and outside the conversation.

---

## User Workflows

### First initialisation — human developer

**Persona:** A developer adopting Lore on an existing repository, working in Claude Code.
**Situation:** They run `lore init` and receive fifteen skills in `.lore/skills/`, which Claude Code does not read. Nothing tells them to copy the directory into `.claude/skills/`, and the skills instruct their agent to route every read and write through the Lore CLI whether they want that or not.
**Goal:** A working Lore project whose skills their agent can find and whose conventions match how they want to work.

**Steps:**

1. The developer runs `lore init` in the repository root.
2. Lore detects that standard output is a terminal and prompts for the coding agents the project uses, offering the seeded registry with Claude Code preselected. The developer confirms.
3. Lore prompts for the access mode, with "agents use their own tools" preselected. The developer confirms.
4. Lore prompts for the skill families to install, with memory and workflow preselected and machinery unselected.
5. Lore finds `CLAUDE.md` already present without Lore's markers and prompts for how to treat it.
6. Lore prompts for appending its entries to the root `.gitignore`, and for whether the installed skills are tracked in version control.
7. Lore prints a summary naming every file it creates and every file it overwrites, and asks for confirmation.
8. On confirmation Lore writes `.lore/`, installs the selected skills into `.claude/skills/` with the access mode injected, writes the Lore section of `CLAUDE.md`, updates `.gitignore`, records the answers in `.lore/config.toml`, and writes the install manifest.

**Critical decision points:** An existing `CLAUDE.md` must never be overwritten wholesale. The summary must be shown before any file is written, not after.
**Success signal:** The developer's agent invokes a Lore skill by name in the next session without the developer having copied anything.

### Upgrade with renamed skills — human developer

**Persona:** A developer who initialised the project on an earlier Lore release and has edited two of the seeded skills.
**Situation:** The new release renames six skills, merges seven into two, and retires one. Because `lore init` only ever writes files, the old and new names would both sit on disk, and the generated skills gitignore would stop covering the old ones — so they would surface as untracked files.
**Goal:** A clean upgrade that removes what Lore installed, keeps what they wrote, and tells them where their edits now belong.

**Steps:**

1. The developer upgrades the `lore` package and runs `lore init`.
2. Lore reads `.lore/config.toml`, finds the recorded answers, and does not re-prompt for them.
3. Lore reads the install manifest and compares it against the files the current release ships and against the bytes on disk.
4. For each file Lore installed and has since retired, whose hash still matches the manifest, Lore marks it for removal and quotes the retirement ledger's reason.
5. For each file the developer edited, Lore marks it as a conflict.
6. Lore prints the summary — creates, overwrites, removals with their reasons, and conflicts — and asks for permission to overwrite the edited files.
7. The developer declines. Lore applies everything else and leaves the edited files untouched, naming in its report the skill each one has been renamed into.
8. Lore writes a new manifest describing what is now installed.

**Critical decision points:** A file Lore never installed is never read, moved, or deleted. A project with no manifest falls back to matching against previously shipped hashes, and keeps any file it cannot match.
**Success signal:** No retired skill name remains on disk, `git status` shows no unexpected untracked files, and both edited files are intact.

### Headless initialisation — Realm and CI

**Persona:** Realm, and any CI pipeline that initialises a project.
**Situation:** These callers have no terminal. A prompt would block indefinitely.
**Goal:** Initialise a project without interaction and without behaviour changing under them.

**Steps:**

1. The caller invokes `lore init`, or calls `run_init()` through `lore.api`.
2. Lore detects that standard output is not a terminal and issues no prompt.
3. With no agent flag passed, Lore installs skills into `.lore/skills/` and writes no agent instruction file — the behaviour of the release before this feature.
4. A caller that wants an agent target and an access mode passes them explicitly, for example `lore init --agent claude --access native --yes`, or passes the equivalent keyword arguments to the API.

**Critical decision points:** Absence of a terminal must select defaults silently rather than fail. The no-argument `run_init()` call must keep working, because it is a pinned contract in the existing API parity tests.
**Success signal:** An existing Realm deployment upgrades Lore and its initialisation path produces the same files as before.

### Changing the access mode — human developer

**Persona:** A developer who chose the Lore CLI mode and now wants their agent to use its own tools.
**Situation:** The answers are recorded in `.lore/config.toml`, so a plain `lore init` will not ask again.
**Goal:** Switch the mode and have every installed skill reflect it.

**Steps:**

1. The developer runs `lore init --reconfigure`, or passes `--access native` directly.
2. Lore prompts with the recorded answers preselected, and the developer changes the access mode.
3. Because the manifest records the hash of each rendered file, every skill whose command layer changes is classified as an overwrite of an unmodified file, and is replaced without a conflict prompt.
4. Lore prints the summary and applies it on confirmation.

**Critical decision points:** The manifest hashes the rendered file, not the authored source, so an access-mode change registers as a real change rather than as a user edit.
**Success signal:** Every installed skill carries the new access mode, and skills the developer edited are still flagged as conflicts rather than silently replaced.

---

## Functional Requirements

### Interactive initialisation

- **FR-1:** A human running `lore init` in a terminal is asked which coding agents the project uses, and may select more than one.
- **FR-2:** A human is asked whether agents operate Lore's local files through the Lore CLI or with their own tools.
- **FR-3:** A human is asked which skill families to install.
- **FR-4:** A human whose selected agent already has an instruction file without Lore's markers is asked how Lore should treat that file.
- **FR-5:** A human is asked whether Lore's entries are appended to the project's root `.gitignore`.
- **FR-6:** A human who selects an agent with a native skills directory is asked whether the installed skills are tracked in version control.
- **FR-7:** A human sees a summary of every file to be created, overwritten, and removed, and confirms it before Lore writes anything.
- **FR-8:** A human may answer any prompt with a command-line flag instead, and may suppress all prompting.
- **FR-9:** A caller without a terminal receives no prompt, and Lore proceeds on defaults and flags alone.
- **FR-10:** A human re-running `lore init` is not asked again for answers already recorded in `.lore/config.toml`, unless they ask to reconfigure.

### Agent targets

- **FR-11:** A human selects agents from a registry seeded with the release, not from a list compiled into the initialisation logic.
- **FR-12:** A maintainer adds an agent to the registry by editing seeded data.
- **FR-13:** Every agent in the shipped registry has a verified instruction-file convention.
- **FR-14:** A human whose selected agent has a native skills directory receives the skills there; a human whose agent has none receives them in `.lore/skills/` and an instruction-file pointer to that directory.
- **FR-15:** Lore writes its section of an agent instruction file between markers, and replaces only that section on later runs.

### Access mode

- **FR-16:** An agent reading a skill installed in Lore CLI mode is instructed to use Lore CLI commands for local file operations.
- **FR-17:** An agent reading a skill installed in agent-native mode is instructed to use its own tools for those operations.
- **FR-18:** A skill retains the `lore codex map`, `lore codex chaos`, and `lore impacts` commands in both modes, because no agent file tool reproduces a precomputed graph traversal.
- **FR-19:** A maintainer authors one source per skill, and the access mode is injected when the skill is installed.

### Skill catalogue

- **FR-20:** A human receives ten seeded skills, grouped into the memory, machinery, and workflow families.
- **FR-21:** An agent records knowledge into project memory through `store-memory`, whether that knowledge comes from the conversation or from an upstream artifact, and whether it creates, edits, or deletes.
- **FR-22:** An agent using `store-memory` writes a source snapshot only when the knowledge arrives as an artifact authored outside the project and outside the conversation, and identifiable well enough to be re-fetched and compared later.
- **FR-23:** An agent answers a question from project memory through `retrieve-memory`, which consults both the codex and the rites.
- **FR-24:** An agent authors a doctrine, knight, watcher, artifact, or custom schema through the corresponding `update-` skill, which creates or edits as the request requires.

### Upgrade reconciliation

- **FR-25:** Lore records every file it writes, with its hash, in an install manifest.
- **FR-26:** Lore removes a file it installed that the current release no longer ships, when that file is unchanged since installation.
- **FR-27:** Lore asks before overwriting a file it installed that has since been edited, and leaves it untouched when refused.
- **FR-28:** Lore never reads, moves, or deletes a file it did not install.
- **FR-29:** Lore reports, for every skill it retires, the skill that replaced it.
- **FR-30:** Lore reconciles a project that predates the install manifest by matching files against hashes it has shipped previously, and keeps any file it cannot match.
- **FR-31:** Lore reconciles correctly across any version gap, including skipped releases, without release-specific migration steps.

### Public API

- **FR-32:** Realm computes what an initialisation would do without performing it.
- **FR-33:** Realm performs a previously computed initialisation.
- **FR-34:** Realm calls `run_init()` with no arguments and receives the behaviour it received before this feature.

### Adjacent corrections

- **FR-35:** A reader of `tech-arch-agents-md` and `conceptual-workflows-lore-init` finds the instruction-file behaviour Lore ships.
- **FR-36:** A project initialised before a configuration key existed finds that key documented in its `.lore/config.toml` header after a later `lore init`.
- **FR-37:** A maintainer audits installed skills with `lore health`.
- **FR-38:** A human sees the actual database schema version in the `lore init` status message.

---

## Non-Functional Requirements

### Performance

- An agent completes a memory retrieval in the same number of Lore CLI calls as before the catalogue consolidation. Consolidating three explore skills into `retrieve-memory` does not add a routing round trip.
- An agent in agent-native mode performs local reads with its own tools, spending no Lore CLI invocation on them. ADR-001 makes the number of tool calls a design constraint, and this is the measure that matters.
- A human answers the initialisation prompts in one `lore init` invocation. No prompt requires the human to abort and re-run with different flags.
- Reconciliation hashes only the files named in the manifest and the files the release ships, not the project tree.

### Security

- Lore has no authentication or authorisation surface. It operates on the local filesystem and a local SQLite database.
- Lore writes only inside the project root: `.lore/`, the selected agents' directories and instruction files, and the root `.gitignore`.
- Lore does not fetch the agent registry, the skill catalogue, or any skill content over a network. All of it ships in the package.

### Reliability

- `lore init` is idempotent. Running it twice in succession with the same answers produces the same files and reports no second round of changes.
- An interrupted `lore init` leaves a project that a subsequent `lore init` reconciles to a correct state.
- No prompt blocks a caller that has no terminal.
- A file the user authored is never lost without the user having agreed to its replacement.
- Concurrent access follows the existing model described in `conceptual-workflows-concurrent-access`; `lore init` is a single-writer operation and is not expected to run concurrently with itself.

---

## Pre-Architecture Notes

_(Appended by the user after reviewing this PRD — do not edit until sign-off phase)_
