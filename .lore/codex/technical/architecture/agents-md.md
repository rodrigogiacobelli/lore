---
id: tech-arch-agents-md
title: Agent Registry and Instruction Files
summary: The seeded agent registry `lore init` reads (agents.yaml — id, label, instruction
  file, skills directory), how the registry is loaded at import time so click.Choice
  can use it, and the rendered agent instruction text — the `lore-agent` document
  assembled from tagged blocks for the project's answers, its 100-line bound and
  generated skills table, and the marker mechanism that keeps each selected agent's
  instruction file idempotent.
binds:
- src/lore/agents.py
- src/lore/defaults/agents.yaml
- src/lore/schemas/agents.yaml
- src/lore/defaults/blocks/**
- src/lore/defaults/skills-catalogue.yaml
- src/lore/init.py
- tests/unit/test_agents.py
- tests/unit/test_lore_init.py
- tests/e2e/test_lore_init.py
related:
- conceptual-workflows-lore-init
- conceptual-workflows-init-features
- conceptual-workflows-init-interactive
- conceptual-entities-skill
- tech-arch-initialized-project-structure
- tech-arch-skill-catalogue
- tech-arch-install-manifest
- tech-arch-schemas
- decisions-006-id-references
- decisions-008-help-as-teaching-interface
- decisions-017-constrained-flags-use-click-choice
- decisions-018-overlays-are-path-discovered-config
---

# Agent Registry and Instruction Files

A coding agent finds out about Lore by reading an instruction file its own tooling loads on startup. Which file that is depends on the agent: Claude Code reads `CLAUDE.md`, Gemini CLI reads `GEMINI.md`, several agents share `AGENTS.md`. `lore init` asks which agents the project uses, then writes Lore's instructions into each one.

Two pieces make that work: a **registry** naming each agent's conventions, and a **rendered instruction text** written into a marked block inside each agent's file.

## The Registry

`src/lore/defaults/agents.yaml` is seeded package data, not a list compiled into initialisation logic. Adding an agent is one YAML block — no change to `init.py`, `cli.py` or any test beyond the structural cross-check.

```yaml
version: 1

agents:
  - id: claude
    label: Claude Code
    instruction_file: CLAUDE.md
    skills_dir: .claude/skills

  - id: agents-md
    label: AGENTS.md — Codex, Cursor, Windsurf, Zed, Amp, OpenCode
    instruction_file: AGENTS.md
    skills_dir: null

  - id: gemini
    label: Gemini CLI
    instruction_file: GEMINI.md
    skills_dir: null

  - id: qwen
    label: Qwen Code
    instruction_file: QWEN.md
    skills_dir: null

  - id: cursor
    label: Cursor — native rules
    instruction_file: .cursor/rules/lore.mdc
    skills_dir: null

  - id: none
    label: None — skills to .lore/skills/, no instruction file
    instruction_file: null
    skills_dir: null
```

| Field | Meaning |
|---|---|
| `id` | The token a person passes to `--agent` and the key stored in `init-agents`. |
| `label` | The text the checkbox prompt shows. |
| `instruction_file` | Repo-root-relative POSIX path of the file Lore writes its marked block into. `null` means the agent gets no instruction file. |
| `skills_dir` | Repo-root-relative POSIX path of the directory the agent reads skills from. `null` means the agent has no native skills mechanism, so its skills go to `.lore/skills/` and the instruction block points there. |

Every row in the shipped file has a verified convention. There is no `verified` field, because it would carry one value on every row.

`none` is a registry row rather than a CLI sentinel, so `click.Choice` covers the token like any other id and the checkbox renders it like any other option. `validators.validate_agent_selection` rejects `none` combined with another id, at both the CLI boundary and inside `plan_init`.

## Loading

`click.Choice` evaluates its set when the decorator runs, at `lore.cli` import, so the registry has to be readable at import time. It is: `agents.load_registry()` reads it from **package** data through `importlib.resources`, cached with `functools.lru_cache`. Project data could never have served this purpose, because `lore init` runs where no `.lore/` exists yet.

`src/lore/agents.py` imports stdlib and `yaml` only, and no `lore.*` module.

The file validates against `lore://schemas/agents` through `load_schema`, never through the overlay resolver. `.lore/custom-schemas/agents.yaml` is not a recognised overlay path — the overlay kinds stay as `decisions-018-overlays-are-path-discovered-config` lists them. An unparseable or schema-invalid registry raises `RuntimeError` naming the packaged file: it is a build defect, never a user error.

## The Rendered Instruction Text

The `lore-agent` document in `src/lore/defaults/skills-catalogue.yaml` lists the blocks the instruction text is assembled from, in order. `skills.render_document("lore-agent", profile)` keeps the blocks that survive the project's answers (`tech-arch-skill-catalogue` holds the block format and the gate grammar) and joins them. One region is generated rather than authored:

- **The skills table** — the marker pair `<!-- lore:skills-table -->` and `<!-- lore:skills-table end -->` in the `i-skills-table` block is replaced by a table naming exactly the skills installed and the directory each landed in. The catalogue is the one place a skill's existence is recorded, so the table is derived rather than hand-maintained. The block survives only when at least one skill is installed.

The text is at most 100 lines for every combination of answers, including the two marker lines that wrap it in an agent's file: the catalogue caps the assembled document at 98 lines and `scripts/check_blocks.py` proves the bound from the block tags. When no feature is on, no text is rendered at all.

The rendered text lands in two kinds of place:

- **`.lore/LORE-AGENT.md`** — whole-file, manifest-tracked. It is the canonical rendered instruction text and the only artefact when no agent is selected. It is written whenever any feature is on and removed when none is.
- **Each selected agent's `instruction_file`** — the same text inside markers, manifest-tracked as a section. When no feature is on, the block is removed and the rest of the file stays byte-identical.

`.lore/GETTING-STARTED.md` is rendered from the `getting-started` document by the same assembler, with no generated region.

## What the Text Contains

The text is a lightweight entry point, not a copy of the CLI. It carries one section per feature that is on, and each section says only what the project's routes and capabilities allow. A command whose capability is off appears nowhere (`decisions-008-help-as-teaching-interface` governs the teaching; the command-grant table governs what may appear).

| Section | Present when | Contains |
|---|---|---|
| Introduction | Always | What Lore is for this project, and that the sections cover only what is enabled. |
| CLI help | Some CLI is taught | A pointer to `lore --help`. |
| Project memory | Memory is on | The codex, rites and glossary; the route in the project's words; the validate line, and the search, index and graph lines for each opt-in that is on. |
| Doctrines, Artifacts, Watchers | The feature is on | What the entity is, how to read it, how to write it, and the validate line. With Quests off, Doctrines also point at `/run-doctrine`, the core skill that runs a doctrine. |
| Quests and missions | Quests is on | The orchestrator dispatch loop, the worker loop, board messages and dependencies. How `/start-quest` creates a quest from a doctrine. |
| Skills | At least one skill is installed | The generated table. |

The orchestrator loop reads `lore ready`, dispatches by mission type (`agent` claimed and handed to a worker, `constable` claimed and handled inline, `human` left for the human), and passes the mission ID to the worker. The worker loop reads `lore show <mission-id>`, executes, closes with `lore done` and reports a blocker with `lore block`. Workers do not create quests or missions and do not claim work. `decisions-006-id-references` holds which entity types are reached by ID through the CLI and which are read by path.

## The Marker Mechanism

Lore writes its section between HTML comment markers so it can update its own content without disturbing anything else in the file:

```markdown
<!-- lore:begin -->
# Lore

… the rendered instruction text …
<!-- lore:end -->
```

Everything outside the markers belongs to the project. `lore init` never reads it as its own and never rewrites it.

Three cases decide what happens to a selected agent's instruction file:

| State of the file | What `lore init` does |
|---|---|
| Absent | Creates it containing the marked block. No prompt. |
| Present, carries `<!-- lore:begin -->` | Replaces the text between the markers. Content outside is preserved byte-for-byte. No prompt. |
| Present, no Lore markers | Asks. `append` adds the marked block and preserves everything already there; `skip` leaves the file untouched. `.lore/LORE-AGENT.md` is written either way, so a person who skips still has the instruction text to wire up by hand. |

The prompt fires only in the third case. `--on-existing-agent-file {append,skip}` answers it without a terminal, and `conceptual-workflows-init-interactive` holds the prompt order.

The install manifest records a marked block by the hash of the rendered text **between** the markers, excluding the markers themselves, so editing prose elsewhere in `CLAUDE.md` never registers as a conflict. When an agent is deselected, its block is deleted and the rest of the file is left byte-identical — an instruction file is never removed, because Lore did not create the whole of it. `tech-arch-install-manifest` holds the rules.
