# Lore

Lore is your project task manager.

```bash
lore --help
Usage: lore [OPTIONS] COMMAND [ARGS]...

  Lore — Agent Task Manager.

  Lore organises agent work into two core entity types:

  Quest   — a body of work (feature, fix, or refactor).
  Mission — a single executable task assigned to an agent.

  Supporting entities:

  Knight   — a reusable agent persona attached to missions.
  Doctrine — workflow templates that guide how missions are executed.
  Codex    — project documentation, searchable and graph-traversable.
  Rite     — procedural memory: how to do or diagnose a recurring task.
  Artifact — reusable template files referenced by stable ID.
  Watcher  — definitions for agents that monitor and react to project state.

  Run any command group with --help for details on that concept.

Options:
  --version  Show the version and exit.
  --json     Output as JSON.
  --help     Show this message and exit.

Commands:
  stats     Show aggregate statistics across all quests and missions.
  oracle    Generate human-readable markdown reports in .lore/reports/.
  init      Initialize a Lore project in the current directory.
  new       Create quests and missions.
  claim     Claim one or more missions (open -> in_progress).
  done      Close one or more missions or quests.
  block     Mark a mission as blocked with a reason.
  unblock   Unblock a blocked mission, returning it to open status.
  ready     Show the highest priority unblocked mission(s), sorted by...
  needs     Declare dependencies between missions using colon-pair syntax.
  unneed    Remove dependencies between missions using colon-pair syntax.
  list      List quests.
  missions  List missions across all quests, or scoped to one quest.
  knight    Manage knight personas — reusable markdown files that tell...
  doctrine  Manage doctrine templates — YAML files that describe the...
  edit      Edit a quest or mission.
  delete    Delete a quest or mission.
  show      Show details of a quest or mission.
  rite      Manage rites — procedural memory ("how to do or diagnose...
  codex     Access project documentation — a set of typed markdown...
  impacts   Surface codex<->code bindings.
  glossary  Access the project glossary — the controlled vocabulary at...
  artifact  Access project artifacts — reusable template files stored...
  board     Manage board messages for quests and missions.
  watcher   Manage watcher definitions stored in .lore/watchers/.
  health    Audit the file-based entity types plus the schemas, bindings,...
```

## Entities

Lore organises agent work and project knowledge around the entities below. The primary CLI verb is listed parenthetically; run `lore <verb> --help` for flags. Codex layout and codex commands are documented separately in `.lore/codex/codex.md`.

### Quest

A body of work — a feature, a fix, or a refactor — that holds one or more Missions. A Quest has a title, summary, priority, and status (`open`, `in_progress`, `done`, `blocked`). Quests are the unit a human sees on a board; Missions are what agents execute. (`lore new quest` / `lore list` / `lore show` / `lore done`)

*Example:* "Add OAuth login" is a Quest whose Missions are "design the auth flow", "implement the endpoint", "write E2E tests".

### Mission

A single executable task assigned to one agent. Each Mission has a type (`knight`, `constable`, or `human`), a status, a priority, a description, acceptance criteria, and an optional Knight persona. Mission *type* drives orchestrator dispatch: `knight` missions are claimed and handed to a worker agent; `constable` missions are inline orchestrator chores; `human` missions are left for the human. (`lore new mission` / `lore claim` / `lore ready` / `lore done` / `lore block` / `lore unblock`)

*Example:* "Write the failing E2E test for the new /login endpoint" is a `knight` Mission inside the OAuth Quest.

### Knight

A reusable agent persona stored as markdown under `.lore/knights/`. Attached to a Mission to tell the worker agent how to behave — voice, focus, output format. (`lore knight list` / `lore knight show` / `lore knight new` / `lore knight edit` / `lore knight delete`)

*Example:* The `tech-writer` knight tells the worker to update codex docs in place rather than draft new ones.

### Doctrine

A workflow template stored as YAML under `.lore/doctrines/`. Generates a Quest's Missions when the user runs `/start-quest`. A Doctrine encodes the *shape* of a kind of work — which Missions, in which order, with which Knights. (`lore doctrine list` / `lore doctrine show` / `lore doctrine new` / `lore doctrine edit` / `lore doctrine delete`)

*Example:* The `feature-implementation` doctrine generates Scout → PRD → Tech Spec → Stories → Dev cycle Missions for any new feature.

### Codex

Typed markdown docs under `.lore/codex/` describing facts about the system as it exists today. Every doc has frontmatter (`id`, `title`, `summary`, optional `related`, optional `binds`, optional `rites`) and a markdown body — plus any project-local custom fields declared in a `.lore/custom-schemas/<kind>.yaml` overlay, which apply to canonical docs and `sources/` but never to `transient/`. The codex is a graph: `related` links connect docs both ways. A codex doc links to the rites it governs via `rites:` — the edge runs codex→rite only, never the reverse. See `.lore/codex/codex.md` for the layout, three content classes, impacts engine, and naming rules. (`lore codex list` / `lore codex search` / `lore codex show` / `lore codex new` / `lore codex edit` / `lore codex delete` / `lore codex map` / `lore codex chaos`)

### Glossary

Controlled vocabulary at `.lore/codex/glossary.yaml` — small, project-specific terms only. Auto-surfaced when terms appear in `lore codex show` output. Not for entities (they have codex docs) and not for named workflows (they have workflow docs). (`lore glossary list` / `lore glossary search` / `lore glossary show` / `lore glossary new` / `lore glossary edit` / `lore glossary delete`)

*Example:* "Constable" — a project-invented label for a Mission type the orchestrator handles inline — qualifies.

### Rite

Procedural memory — "how to do or diagnose recurring task X" — stored as YAML under `.lore/rites/`, a sibling of the codex. Where the codex holds *semantic* knowledge (what is true), a rite holds *procedural* knowledge (what to do, step by step). Two shapes: a **main rite** (`main/`) is a node-graph of steps — each node either a `do:` action or a `use:` of a shared step, routed by `then`/`if`/`goto` and terminating in typed `conclusions:` — and a **shared step** (`shared/`) is a pure, single-exit procedure (`id`/`title`/`summary`/`do` only, no branching, no trigger) that main rites pull in by bare id with `use:`. Discovery is recursive; a rite's subfolder becomes a cosmetic `group` for display/filter only, and its `id:` is globally unique like the codex. Agents find a rite by reading `lore rite list` and picking the matching trigger themselves — Lore never matches a situation. Rites link to nothing; a codex doc points at the rites it governs via its `rites:` field (codex→rite, never the reverse — ADR-014). (`lore rite list` (GROUP column, `--filter`) / `lore rite show` (inlines shared steps) / `lore rite search` / `lore rite new --group` / `lore rite edit` / `lore rite delete`)

*Example:* A `refund-customer` main rite branches on order age and reason, `use:`-ing a shared `verify-payment-method` step, and ends in `refund-issued` / `escalate-to-human` conclusions.

### Artifact

Reusable template files referenced by stable ID under `.lore/artifacts/`. Agents `lore artifact show <id>` to pull a template (a PR-review checklist, a glossary-design gate, an ADR skeleton) into their working context. (`lore artifact list` / `lore artifact show` / `lore artifact new` / `lore artifact edit` / `lore artifact delete`)

*Example:* `glossary-design` is the three-question gate every glossary edit must pass.

### Watcher

A reactive-agent definition stored under `.lore/watchers/`. Declares a project-state condition and a Knight that runs when the condition fires. (`lore watcher list` / `lore watcher show` / `lore watcher new` / `lore watcher edit` / `lore watcher delete`)

*Example:* A `pr-ready` watcher could run a `code-reviewer` knight whenever a Mission transitions to `done`.

### Board message

A piece of state attached to a Quest or Mission — a note, a question, a hand-off. Plain text addressed to the next agent or to the human. (`lore board add` / `lore board list` / `lore board delete`)

*Example:* "Blocked on schema migration approval — pinging the human" attached to a Mission.

### Dependency

A `needs` edge between two Missions: Mission A `needs` Mission B means B must reach `done` before A can leave the `open` queue. Shown in `lore ready` ordering. (`lore needs` / `lore unneed`)

*Example:* The "implement endpoint" Mission `needs` the "design auth flow" Mission.

## Roles

You are either the orchestrator (dispatching missions) or a worker (executing one).

### Orchestrator

- `lore ready` → next available mission. Dispatch by type:
  - **`knight`** — claim (`lore claim <id>`), spawn worker agent with the mission ID
  - **`constable`** — claim and handle inline (commit, housekeeping, etc.)
  - **`human`** — do NOT claim, leave for human
- Start a new quest from a doctrine via `/start-quest`.
- Use the relevant skill (table below): the `update-*` skills author a doctrine, knight, watcher, artifact or custom schema — creating or editing as the request requires — and `store-memory` / `retrieve-memory` write and read project memory.

Default doctrines shipped via `lore init`:

| Doctrine                      | What it does                                                                                  |
|-------------------------------|-----------------------------------------------------------------------------------------------|
| `feature-implementation`      | Full E2E spec pipeline — Scout, PRD (crazy + draft + final), Tech Spec, Stories. Four phases. |
| `quick-feature-implementation`| Streamlined spec pipeline — single scout, no crazy phases, single commit at the end.          |
| `tdd-implementation`          | Strict Red-Green-Refactor cycle for one dev-ready story. Hard boundaries between each step.   |
| `update-changelog`            | Single-step changelog update after a merge to `develop`. Triggered by the changelog watcher.  |

### Worker

- You have a mission ID. Run `lore show <id>` — returns description, acceptance criteria, and knight persona in one call.
- Execute. Run `lore done <id>` when finished. Run `lore block <id> "<reason>"` if stuck.
- Do not create quests or missions. Do not claim unassigned work.

## Knowing the project

Read project state before you act. Project memory has two surfaces — the codex
holds what is true, the rites hold how to do or diagnose a recurring task — and
`retrieve-memory` walks both in one pass.

<!-- lore:access cli -->
- **`lore codex search <kw>` / `lore codex show <id1> <id2>`** — typed markdown
  documents under `.lore/codex/`. Batch ids into one `show` call; it deduplicates
  and appends the glossary terms it matched.
- **`lore codex list`** — the whole taxonomy.
- **`lore rite list` / `lore rite search <kw>` / `lore rite show <id>`** —
  procedures. `show` inlines every shared step a rite pulls in with `use:`, so
  one call gives you the complete procedure.
- **`lore glossary list` / `lore glossary search <q>`** — project vocabulary.
<!-- lore:access end -->
<!-- lore:access native -->
- **Codex** — grep `.lore/codex/**/*.md` and read `.lore/codex/<layer>/<id>.md`
  with your own file tool. Write documents there yourself;
  `lore health --scope codex schemas` validates the result.
- **Rites** — read and write `.lore/rites/main/**/*.yaml` and
  `.lore/rites/shared/**/*.yaml` directly; `lore health --scope rites` validates
  the graph afterwards.
- **Glossary** — `.lore/codex/glossary.yaml`, one file with a schema;
  `lore health --scope glossary` validates it.

Three things reading files gives up, which are now yours to do: glossary terms
are not attached to what you read, a rite's `use:` steps are not inlined, and a
document's group is its directory rather than anything in its id.
<!-- lore:access end -->

These four reach past what a file tool can reproduce, so they stay on the CLI
whichever way your project reads the rest:

- **`lore codex map <id>`** — bidirectional traversal of related documents.
- **`lore codex chaos <id> --threshold <30-100>`** — serendipitous discovery.
- **`lore impacts <path>`** — which codex documents govern this file. Run before
  editing code. **`lore impacts <codex-id>`** — which files a document binds.
  Run when assessing a document's reach.
- **`lore health`** — audit codex, rites, schemas, bindings, glossary, voice and
  the skills `lore init` installed. Run after structural changes. It writes no
  report file unless `health-report-retention` in `.lore/config.toml` is
  `"latest"` or `"all"`.

Everything else — artifacts, knights, doctrines, watchers, quests, missions and
board messages — is reached by id through the Lore CLI in every mode. Those
commands run normalisation, validation, cycle detection and content splicing
that no file read reproduces.

## Available skills

Skills are installed into this project. Each is a folder holding a `SKILL.md`
you read before doing the job it names.

<!-- lore:skills-table -->
This region is generated by `lore init` from the skill catalogue.
<!-- lore:skills-table end -->
