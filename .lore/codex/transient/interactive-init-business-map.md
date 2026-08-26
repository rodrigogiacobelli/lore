---
id: interactive-init-business-map
title: Context Map — Interactive lore init and Skill Catalogue Consolidation (business lens)
summary: Business-lens context map for the interactive-init feature — the codex documents that describe the user-facing init workflow, the entities the consolidated skill catalogue authors, the commands the access mode swaps, and the product constraints (ADR-001, ADR-006, ADR-008) the feature has to move or respect.
type: context-map
related:
- interactive-init-prd
- conceptual-workflows-lore-init
- conceptual-workflows-typical-workflow
- conceptual-workflows-health
- conceptual-workflows-codex
- conceptual-workflows-codex-map
- conceptual-workflows-codex-chaos
- conceptual-workflows-impacts
- conceptual-workflows-glossary
- conceptual-workflows-concurrent-access
- conceptual-entities-artifact
- conceptual-entities-doctrine
- conceptual-entities-knight
- conceptual-entities-watcher
- conceptual-entities-rite
- conceptual-entities-glossary
- tech-arch-initialized-project-structure
- tech-arch-agents-md
- decisions-001-dumb-infrastructure
- decisions-006-id-references
- decisions-007-artifact-communication-protocol
- decisions-008-help-as-teaching-interface
- decisions-009-mission-self-containment
- decisions-013-toml-for-config-yaml-for-glossary
- decisions-020-codex-voice-is-enforced
- ops-installation
- vision-camelot-system
- codex
---

# Context Map — Interactive `lore init` and Skill Catalogue Consolidation (business lens)

**Author:** Scout (business lens)
**Date:** 2026-08-25
**Feature:** _`lore init` asks the human which coding agent the project uses and how agents touch Lore's local files, installs the ten seeded skills where that agent looks, and reconciles renamed or merged skills on every later run._
**Lens:** _business_
**PRD:** `lore codex show interactive-init-prd`

---

## Relevant Documents

### The workflow the feature rewrites

| ID | Title | Why relevant |
|----|-------|-------------|
| `conceptual-workflows-lore-init` | `lore init` Behaviour | The document this feature replaces. It is the authored description of today's nine-step, zero-prompt init — including the step-7 `AGENTS.md` create/marker/backup rules that do NOT exist in `src/lore/` — and it is explicitly in scope for rewrite (PRD FR-35). Read it to know exactly which promises to the user are being changed and which (idempotency, "user-created files in the flat parent directory are never touched") must survive. |
| `tech-arch-initialized-project-structure` | Initialized Project Structure | The user-facing inventory of what a person gets after `lore init` — the `.lore/` tree, the file-by-file purposes, and the verbatim `.lore/.gitignore` template. Every item this feature adds (skills at their per-agent destination, the install manifest, the new config keys) or moves changes this picture, and it is the list the pre-write summary screen (FR-7) has to be able to enumerate. Note it is already stale: it shows `AGENTS.md` at root and no `.lore/skills/` or `.lore/docs/`. |
| `tech-arch-agents-md` | AGENTS.md Specification | The authored contract for the agent instruction file the user ends up with — two required sections, the `<!-- lore:begin -->` marker mechanism, and the `AGENTS.md.old` backup. In scope for rewrite (FR-35), and it is the doc that FR-4 (ask the human what to do with a pre-existing instruction file) and FR-15 (replace only the marked section) will be measured against. |
| `conceptual-workflows-typical-workflow` | Typical Workflow | The end-to-end journey a newly initialised project enters — init, then quest and mission creation, dispatch, closure. It is the "day two" experience the first-init prompts are configuring, and the sequence the seeded skills exist to serve. |
| `ops-installation` | Installation | How a human reaches `lore init` in the first place (uv tool / pipx) and how they upgrade. The upgrade command in this doc is the exact trigger for the reconciliation workflow in the PRD's second user workflow; the doc has to keep telling upgraders to re-run `lore init`. |

### Entities the consolidated skill catalogue creates and reads

| ID | Title | Why relevant |
|----|-------|-------------|
| `conceptual-entities-doctrine` | Doctrine | The `machinery` family's `update-doctrine` skill authors these. Defines the paired `.yaml` + `.design.md` model and the `default/` vs flat-directory ownership split — the rule that decides which files a skill may overwrite. |
| `conceptual-entities-knight` | Knight | Authored by `update-knight`. Defines the persona file's what/how separation and how knight contents reach a worker through `lore show`, which is what a knight-writing skill has to produce correctly. |
| `conceptual-entities-watcher` | Watcher | Authored by `update-watcher`. Defines watchers as passive YAML declarations Lore stores but never executes — the boundary an `update-` skill must not overstep. |
| `conceptual-entities-artifact` | Artifact | Authored by `update-artifact`, and the entity type `lore init` already seeds under `.lore/artifacts/default/` in four namespaces. Also the entity every doctrine step references by ID, so the artifact seeding path must keep working unchanged when the skills install path changes. |
| `conceptual-entities-rite` | Rite | Procedural memory — the second store `retrieve-memory` consults alongside the codex (FR-23), and the entity the retired `explore-rite` / `explore-codex-rite` skills used to cover. Defines what a rite is so the merged retrieval skill still covers both stores. |
| `conceptual-entities-glossary` | Glossary | The single user-owned `glossary.yaml` seeded by init and auto-surfaced on `lore codex show`. Part of what `store-memory` and `retrieve-memory` operate over, and one of the two files init writes directly into `.lore/codex/`. |
| `codex` | Codex | The project codex root document, seeded by init as `.lore/codex/CODEX.md` and maintained by the `workflow` family's `sync-codex-guide` skill. Defines the layer structure every memory skill writes into. |

### Commands the access mode decides

| ID | Title | Why relevant |
|----|-------|-------------|
| `conceptual-workflows-codex` | Codex Commands — `lore codex` | The command family whose `list` / `search` / `show` verbs drop out of a skill under agent-native mode and stay under Lore-CLI mode. Read it to see exactly what an agent loses by reading files directly — dedup on multi-ID retrieval, group derivation, glossary auto-attach. |
| `conceptual-workflows-codex-map` | `lore codex map` Behaviour | One of the three commands FR-18 keeps in BOTH access modes. This doc is the argument for that rule: a directional bidirectional BFS over `related` is not something an agent reproduces with a file read. |
| `conceptual-workflows-codex-chaos` | `lore codex chaos` Behaviour | Second of the three commands retained in both modes — a random walk with a reachable-subgraph termination ratio. No file tool substitutes for it. |
| `conceptual-workflows-impacts` | `lore impacts` Behaviour | Third command retained in both modes — the bidirectional codex↔code surfacing over the `binds` field. Same argument: precomputed traversal, not a grep. |
| `conceptual-workflows-glossary` | Glossary Commands — `lore glossary` and auto-surface | `lore codex show` silently appends matched glossary entries, governed by a `.lore/config.toml` key. An agent that reads codex files directly under agent-native mode loses that auto-surface — a user-visible consequence of the access-mode choice that the skills' command layer has to account for. |
| `conceptual-workflows-health` | `lore health` Behaviour | FR-37 adds a `skills` scope. This doc holds the ten existing scopes, the split between "scopes that name an entity type" and "scopes that ask a question", and the per-scope error/warning vocabulary a new scope has to fit into. |

### Product constraints this feature moves or must respect

| ID | Title | Why relevant |
|----|-------|-------------|
| `decisions-001-dumb-infrastructure` | Dumb infrastructure design principles | The ADR to be amended in place. Its "short commands", "smart defaults", "no flags required for common operations" and "minimise tool calls" principles were all written for an agent-only caller; nothing in it admits a command that stops and asks a human. The amendment must add the human-first interactive command class plus a dated `## Status History` row without creating a superseding ADR. |
| `decisions-006-id-references` | Agents reference entities by ID, never by file path | The sharpest constraint on the access mode. This ADR says agents must reach artifacts, doctrines and knights through `lore ... show <id>`, never by reading `.lore/` paths. "Agents use their own tools" must be scoped so it does not silently repeal this — the tech spec has to state which file classes agent-native mode covers. |
| `decisions-008-help-as-teaching-interface` | CLI `--help` is the primary teaching interface for AI agents | Every new flag added for FR-8 inherits the obligation to teach, not merely describe. It also frames the product question this feature raises: the seeded skills become a second teaching surface alongside `--help`, and the two must not contradict each other. |
| `decisions-013-toml-for-config-yaml-for-glossary` | ADR-013: TOML for project config, YAML for glossary content | Establishes `.lore/config.toml` as the user-owned, never-clobbered project config and the "seed in place, skip if present" rule. The recorded init answers (FR-10) and the regenerated known-key header (FR-36) both land in that file, and FR-36 deliberately bends the "skip if present" rule for the comment block. |
| `decisions-007-artifact-communication-protocol` | Artifact instances are the official communication protocol between pipeline steps | Why the seeded artifacts matter to the user: the shipped development process is carried by artifact templates referenced by ID from doctrine steps. A skill-family choice that omits a family must not orphan the artifacts a retained doctrine references. |
| `decisions-009-mission-self-containment` | Missions must be self-contained | Governs how this map and the PRD reach downstream missions — board messages carry pointers, artifacts carry content. Relevant because the feature's own delivery, and the doctrines the seeded skills drive, both depend on it. |
| `decisions-020-codex-voice-is-enforced` | ADR-020: Canonical codex documents describe current state | Binds the two in-scope doc rewrites. `conceptual-workflows-lore-init` and `tech-arch-agents-md` must be rewritten to describe what ships, with no migration narrative, no "previously", and no changelog voice. |
| `conceptual-workflows-concurrent-access` | Concurrent Access Safety | Named directly by the PRD's reliability NFRs. Establishes the single-writer model that lets `lore init` assume it is not racing another `lore init`. |
| `vision-camelot-system` | Camelot System Vision | Establishes Realm as an importing consumer and the one-way dependency Lore→(nothing). This is the persona behind the headless workflow and behind the hard requirement that `run_init()` keeps working with no arguments. |

---

## How to Use This Map

Every agent that receives this map should:
1. Run `lore codex show <id1> <id2> ...` with all IDs in the tables above
2. Read every document listed before starting their mission
3. Do not explore the codex independently — this map is your entry point

Start with `interactive-init-prd`, then `conceptual-workflows-lore-init`, then `tech-arch-initialized-project-structure`.

---

## Scout Notes

**Glossary.** `.lore/codex/glossary.yaml` holds exactly one entry — `Constable`, with no `do_not_use` list. No term in the PRD collides with it. The vocabulary this feature introduces (skill family, access mode, install manifest, agent registry, retirement ledger) is entirely unglossed. Per the glossary design gate, "skill family" and "access mode" are candidate entries (controlled vocabulary with a real ambiguity cost); named workflows and entity types are not.

**Three of the feature's central nouns have no codex home at all.** Searching `skills`, `manifest`, `hash` and `upgrade` returns only the PRD. There is no `conceptual-entities-skill`, no doc describing `.lore/skills/`, and no doc describing what a Lore upgrade does to an existing project. The seeded skills are currently invisible to the codex even though `lore init` already installs fifteen of them and generates their `.gitignore`. Downstream: the codex-apply mission needs to *create* documents here, not only edit existing ones.

**`tech-arch-initialized-project-structure` is stale in the same way the two in-scope docs are.** It shows `AGENTS.md` at the project root and omits both `.lore/skills/` and `.lore/docs/`, which `init.py` already writes today (`src/lore/init.py:178`, `:193`, `:203`). The PRD names only `tech-arch-agents-md` and `conceptual-workflows-lore-init` as in-scope rewrites. This third doc will be wrong the moment the feature ships and should be added to the codex-apply scope.

**The "upgrade" persona has no documented journey.** `ops-installation` covers installing and building; `ops-publish-pypi` covers releasing. Neither describes what an existing project's maintainer does after upgrading the package. The PRD's second user workflow is the first authored description of it, and it currently exists only in a transient document.

**Retirement affects two hand-maintained tables.** The seeded `LORE-AGENT.md` carries an "Available skills" table naming thirteen of the fifteen shipped skills, and this project's own `CLAUDE.md` carries a ten-row version of the same table. Both list skills by name, so the 15→10 consolidation invalidates both. `LORE-AGENT.md` also carries a "Lore CLI commands" section that is itself an access-mode command layer, so the instruction file has the same swap problem the skills do. Whoever owns the catalogue change owns these tables.
