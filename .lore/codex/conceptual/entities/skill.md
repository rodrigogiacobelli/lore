---
id: conceptual-entities-skill
title: Skill
summary: What a Skill is — a seeded instruction file that teaches a coding agent one
  Lore-shaped task. Covers the eleven shipped skills and the answers that install each,
  where a skill installs for each agent target, how the routes and capabilities choose
  the blocks a skill is assembled from, the retirement ledger that carries a renamed
  skill forward, and why a skill has no CLI command group.
related:
- conceptual-entities-artifact
- conceptual-entities-doctrine
- conceptual-entities-rite
- conceptual-workflows-lore-init
- conceptual-workflows-init-features
- conceptual-workflows-init-interactive
- conceptual-workflows-init-reconcile
- conceptual-workflows-health
- tech-arch-skill-catalogue
- tech-arch-agents-md
- tech-arch-install-manifest
- tech-cli-entity-crud-matrix
- decisions-006-id-references
- conceptual-workflows-index
- decisions-039-authored-entry-is-keyed-by-its-hub
---

# Skill

A **Skill** is a seeded instruction file that teaches a coding agent how to perform one Lore-shaped task — record a decision into the codex, answer a question from project memory, author a doctrine, start a quest. `lore init` installs skills into the directory the project's coding agent reads them from, and the agent invokes one by name when the task at hand matches.

A skill is not a Lore-managed entity in the sense the other seven are. It has no ID retrieval, no `lore skill` command group, and no place in the CRUD matrix (`tech-cli-entity-crud-matrix`). It is a file Lore installs, tracks and reconciles, and an agent reads.

## The Eleven Skills

| Skill | Installed when | What it does |
|---|---|---|
| `retrieve-memory` | Memory read is not `off` | Answers a question from project memory, consulting both the codex and the rites. |
| `store-memory` | Memory write is not `off` | Records knowledge into project memory — a codex document, a rite, or a source snapshot — creating, editing or deleting as the request requires. |
| `update-custom-schema` | Memory write is not `off` | Authors or edits a project custom-schema overlay. |
| `update-index` | Memory index is on | Authors and refreshes the codex index — the slug, name and summary for each cluster of documents Lore has partitioned. The only writer of `.lore/index/authored.yaml`. |
| `sync-codex-guide` | Memory write is not `off`, Artifacts is on, and Memory validate and graph are on | Reconciles the project's `codex.md` against the seeded template. |
| `update-doctrine` | Doctrines write is not `off` | Authors or edits a doctrine. |
| `update-artifact` | Artifacts write is not `off` | Authors or edits an artifact template. |
| `update-watcher` | Watchers write is not `off` | Authors or edits a watcher. |
| `run-doctrine` | Always (Doctrines are core) | Teaches how a doctrine runs: reads the design, plans the missions from its table, asks before dispatching, briefs a worker for each `agent` mission and drives the run itself, with no quest or mission command. |
| `start-quest` | Quests is on | Reads a doctrine and creates a quest and its missions from it. |
| `inquest` | Quests is on | Audits finished work and traces a missed requirement to the link that dropped it. |

## Materialisation

A skill is installed when at least one block of its `SKILL.md` survives the project's answers. A skill with no surviving block is never written, and no instruction text and no other skill mentions it. A reference file is written when at least one of its blocks survives and its skill is installed. `conceptual-workflows-init-features` holds the answers and `tech-arch-skill-catalogue` holds the block format.

The three families (memory, machinery, workflow) are the retired selection model. The deprecated `--skills` alias still accepts their names and maps them onto the features.

## Where a Skill Installs

A skill is installed only where the selected agent reads it. There is no manual copy step.

| Project's selection | Skills land at |
|---|---|
| An agent with a native skills directory (Claude Code: `.claude/skills/`) | that directory |
| An agent with no native skills mechanism | `.lore/skills/`, and the agent's instruction file points there |
| Several agents, at least one with a native directory | each such directory, plus `.lore/skills/` when at least one selected agent has none |
| No agent, or `none` | `.lore/skills/` |

Installing into two directories for a project that uses both Claude Code and an `AGENTS.md` agent costs duplicated bytes and buys a working setup for both. Each copy is tracked independently, so deselecting one agent removes only its copy.

On disk a skill is one directory named for its id, holding `SKILL.md` and, for the skills that ship them, a `references/` directory of supporting files that `SKILL.md` names.

## Routes and Capabilities

Each skill is authored once as tagged blocks and assembled for the project's answers. A route chooses between two variants of a step:

- **`cli`** — the step tells the agent to operate Lore's files through `lore` commands.
- **`harness`** — the step tells the agent to use its own file tools, and states what that costs: glossary terms are not attached to what the agent reads, a rite's `use:` steps are not inlined, and a document's group is its directory.

A capability adds or removes the steps that run `lore health`, `lore index` or the graph commands. A command whose capability is off appears in no skill (`decisions-006-id-references` holds which entity types are reached by ID through the CLI and which by path).

Every skill file is at most 100 lines, except four `store-memory` files: `SKILL.md` (140), `references/codex-doc.md` (112), `references/rite.md` (140) and `references/source.md` (135). Material beyond the cap sits in `references/` files that the skill names and an agent reads on demand.

## Lifecycle

1. **Authored** in the Lore package as tagged blocks listed per file in the skill catalogue.
2. **Selected** by the project's answers at `lore init`.
3. **Assembled** from the surviving blocks and written to each destination.
4. **Recorded** in the install manifest, with the hash of the rendered bytes.
5. **Reconciled** on every later `lore init`: replaced when the shipped content changes, removed when the release stops shipping it, kept when the project has edited it.
6. **Retired** when a release renames it or merges it into another skill. The retirement ledger names the successor and the reason, and `lore init` quotes both when it removes the file.

A retired skill a person has edited is never deleted. `lore init` names the skill that replaced it and leaves the edit in place, so the porting is the person's to do.

## Auditing

`lore health --scope skills` reports what the manifest and the disk disagree about: a recorded file missing, a file edited since install, a retired skill still present, and a `SKILL.md` whose frontmatter has no `name`. `conceptual-workflows-health` holds the severities and the exit-code consequence.

A project with no install manifest — one initialised before manifests existed — produces no findings from this scope. That is a legitimate state, not a defect.
