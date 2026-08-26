---
id: conceptual-entities-skill
title: Skill
summary: What a Skill is — a seeded instruction file that teaches a coding agent one
  Lore-shaped task. Covers the ten shipped skills and their three families, where a
  skill installs for each agent target, the access mode that swaps its command layer,
  the retirement ledger that carries a renamed skill forward, and why a skill has no
  CLI command group.
related:
- conceptual-entities-artifact
- conceptual-entities-doctrine
- conceptual-entities-knight
- conceptual-entities-rite
- conceptual-workflows-lore-init
- conceptual-workflows-init-interactive
- conceptual-workflows-init-reconcile
- conceptual-workflows-health
- tech-arch-skill-catalogue
- tech-arch-agents-md
- tech-arch-install-manifest
- tech-cli-entity-crud-matrix
- decisions-006-id-references
---

# Skill

A **Skill** is a seeded instruction file that teaches a coding agent how to perform one Lore-shaped task — record a decision into the codex, answer a question from project memory, author a doctrine, start a quest. `lore init` installs skills into the directory the project's coding agent reads them from, and the agent invokes one by name when the task at hand matches.

A skill is not a Lore-managed entity in the sense the other seven are. It has no ID retrieval, no `lore skill` command group, and no place in the CRUD matrix (`tech-cli-entity-crud-matrix`). It is a file Lore installs, tracks and reconciles, and an agent reads.

## The Ten Skills

| Family | Skill | What it does |
|---|---|---|
| memory | `store-memory` | Records knowledge into project memory — a codex document, a rite, or a source snapshot — creating, editing or deleting as the request requires. |
| memory | `retrieve-memory` | Answers a question from project memory, consulting both the codex and the rites. |
| machinery | `update-doctrine` | Authors or edits a doctrine. |
| machinery | `update-knight` | Authors or edits a knight persona. |
| machinery | `update-watcher` | Authors or edits a watcher. |
| machinery | `update-artifact` | Authors or edits an artifact template. |
| machinery | `update-custom-schema` | Authors or edits a project custom-schema overlay. |
| workflow | `start-quest` | Reads a doctrine, creates a quest and its missions. |
| workflow | `inquest` | Audits finished work and traces a missed requirement to the link that dropped it. |
| workflow | `sync-codex-guide` | Reconciles the project's `CODEX.md` against the seeded template. |

## Families

The three families are the unit a person selects at `lore init`:

- **memory** — project memory: the codex, the rites and the glossary, consulted together.
- **machinery** — Lore's own configuration entities: doctrines, knights, watchers, artifacts, custom schemas.
- **workflow** — multi-step processes over quests and missions.

A family is selected or not selected as a whole. `conceptual-workflows-init-interactive` holds the prompt and its flag.

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

## The Access Mode

Each skill is authored once and installed in one of two access modes, recorded per project:

- **`cli`** — the skill tells the agent to operate Lore's local files through `lore` commands.
- **`native`** — the skill tells the agent to use its own file tools for codex documents, rites and the glossary, and states what that costs: no glossary auto-surface on read, no multi-ID deduplication, no group derivation.

The mode swaps the skill's **command layer**, not a preamble. Everything else in the skill is identical between the two.

Three commands stay in both modes — `lore codex map`, `lore codex chaos` and `lore impacts` — because no file tool reproduces a precomputed graph traversal. Artifacts, knights, doctrines, watchers, and every SQLite-backed entity keep the by-ID CLI rule in both modes (`decisions-006-id-references`).

`tech-arch-skill-catalogue` holds how the two renderings come out of one authored file.

## Lifecycle

1. **Authored** in the Lore package, one `SKILL.md` per skill with both access-mode blocks present.
2. **Selected** by family at `lore init`.
3. **Rendered** into the recorded access mode and written to each destination.
4. **Recorded** in the install manifest, with the hash of the rendered bytes.
5. **Reconciled** on every later `lore init`: replaced when the shipped content changes, removed when the release stops shipping it, kept when the project has edited it.
6. **Retired** when a release renames it or merges it into another skill. The retirement ledger names the successor and the reason, and `lore init` quotes both when it removes the file.

A retired skill a person has edited is never deleted. `lore init` names the skill that replaced it and leaves the edit in place, so the porting is the person's to do.

## Auditing

`lore health --scope skills` reports what the manifest and the disk disagree about: a recorded file missing, a file edited since install, a retired skill still present, and a `SKILL.md` whose frontmatter has no `name`. `conceptual-workflows-health` holds the severities and the exit-code consequence.

A project with no install manifest — one initialised before manifests existed — produces no findings from this scope. That is a legitimate state, not a defect.
