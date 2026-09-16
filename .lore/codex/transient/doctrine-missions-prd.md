---
id: doctrine-missions-prd
title: Doctrine Missions — PRD
summary: 'Knights are removed and doctrines become a directory of prose — a design
  document for the orchestrator plus one mission file per step, each merging the former
  knight persona with the former YAML step notes. One authoritative copy of every
  reusable instruction, no YAML, no second entity to keep in sync.

  '
related:
- decisions-001-dumb-infrastructure
- decisions-003-soft-delete-semantics
- decisions-004-mission-type-dumb-storage
- decisions-006-id-references
- decisions-010-public-api-stability
- decisions-011-api-parity-with-cli
- decisions-012-multi-value-cli-param-convention
- decisions-013-toml-for-config-yaml-for-glossary
- decisions-017-constrained-flags-use-click-choice
- decisions-024-default-group-is-seeded-boundary
- conceptual-entities-doctrine
- tech-arch-source-layout
- tech-cli-entity-crud-matrix
---

# Doctrine Missions — PRD

**Author:** Product Manager
**Date:** 2026-09-15

---

## Executive Summary

A Lore doctrine is today two files — a `.design.md` an orchestrator reads and a
`.yaml` carrying the step graph — and each of its steps names a Knight, a third
file holding the persona the worker agent adopts. Authoring a doctrine therefore
means authoring across three places, and the same instruction routinely lands in
two of them: the YAML step notes say what to do, the knight says how to be, and
the boundary between them is a judgment call made afresh every time. This feature
collapses the three into one. A doctrine becomes a directory: one design document
for the orchestrator, and one mission file per step for the worker, each mission
file merging what used to be the knight persona with what used to be the step
notes. The Knight entity is removed outright.

### What Makes This Special

There is exactly one authoritative copy of every reusable instruction, and it
lives beside the doctrine that uses it. The orchestrator reads prose and decides;
Lore stores prose and splices it. Nothing is duplicated because there is nowhere
left to duplicate it to.

---

## Project Classification

| Attribute | Value |
|-----------|-------|
| Project type | CLI tool and importable Python library (`lore-agent-task-manager`) |
| Primary users | AI agents driving the CLI (orchestrator and worker), human developers at a terminal, Realm via `from lore.api import ...`, and downstream projects receiving `src/lore/defaults/` on `lore init` |
| Scale | Single-file SQLite per project; one repository per project; no server, no daemon |

---

## Success Criteria

### User Success

An orchestrator agent runs one command, `lore doctrine show <id>`, and has
everything it needs to plan a quest: the design prose and the list of missions
available. It never reads a mission body, because it never needs to — it names
the mission on the created Lore mission and `lore show <mission-id>` delivers
that body to the worker.

A worker agent runs one command, `lore show <mission-id>`, and receives its
feature-specific description and its full reusable instructions together, in one
response.

An author editing a doctrine changes one file. There is no second place where the
same instruction lives, and no decision to make about which of two files an
instruction belongs in.

### Technical Success

| Metric | Baseline | Target | Timeline |
|--------|----------|--------|----------|
| Places one reusable instruction can live | 2 (knight body, YAML step notes) | 1 (mission file) | v0.12.0 |
| Files touched to author a 5-step doctrine | 7 (design + yaml + 5 knights) | 6 (design + 5 missions), in one CLI call | v0.12.0 |
| Commands an orchestrator runs to read a doctrine | 1 | 1 | v0.12.0 |
| Commands a worker runs to receive its instructions | 1 (`lore show`) | 1 (`lore show`) | v0.12.0 |
| Entity types in Lore | 7 | 6 | v0.12.0 |
| Packaged schemas | 12 | 11 | v0.12.0 |

---

## Product Scope

### MVP

- A doctrine is a directory `.lore/doctrines/<group>/<doctrine>/` containing
  `<doctrine>.design.md` and `missions/<mission-id>.md`.
- Doctrine mission files carry `id`, `title`, `summary` frontmatter and a prose
  body. Nothing else.
- `lore doctrine show <id>` returns the design body plus a mission index;
  `--mission <id>` returns one mission body.
- `lore doctrine new` and `lore doctrine edit` write the directory, taking the
  design and the mission files as space-separated arguments.
- `lore new mission -D <doctrine>/<mission>` records the reference;
  `lore show <mission-id>` splices that mission file's body into its output.
- The Knight entity is removed: module, CLI group, public API names, schema,
  health scope, seeded files.
- `frontmatter_edit`'s existing `doctrine` kind is repointed from the deleted
  `<doctrine>.yaml` onto `<doctrine>.design.md`, so
  `lore doctrine edit --set / --unset / --add / --remove` keeps working against
  the design document's frontmatter. Its `knight` kind is removed.
- `mission_type` token `knight` becomes `agent`.
- Migration v6→v7 drops `missions.knight`, adds `missions.doctrine_mission`, and
  rewrites `mission_type` from `knight` to `agent`.
- `lore health --scope doctrines` audits the new shape and reports old-shape
  leftovers as warnings.
- A new `mission-design.md` artifact, a rewritten `doctrine-design.md` artifact,
  the four seeded doctrines converted, and the affected seeded skills updated.

### Post-MVP

- A `lore doctrine mission` subcommand group, if per-mission CRUD outgrows the
  flags on `lore doctrine edit`.
- Field-level frontmatter editing of a doctrine mission file
  (`--set` / `--unset` / `--add` / `--remove`).

### Out of Scope

- **Lore does not execute a doctrine.** It stores the prose and surfaces it;
  dispatch stays entirely with the consuming orchestrator (ADR-001, ADR-004).
- **No machine-readable step graph.** A doctrine carries no step ids, no `type`,
  no `phase`, no `needs` in any file Lore parses. Cycle detection, step
  validation and step normalisation are deleted, not relocated.
- **No `lore doctrine mission` subcommand group.** `lore doctrine edit` covers
  per-mission create, replace and remove.
- **No `doctrine-mission` kind in `frontmatter_edit`.** A mission file's
  frontmatter is edited by supplying a replacement file, not field by field. This
  is a decision not to add a new kind; it is distinct from the existing
  `doctrine` kind, which is repointed and kept.
- **No migration of authored knights into doctrine missions.** Lore reports the
  orphaned files; converting them is the project's editorial work.
- **No compatibility shim.** `lore knight *`, the knight API names and the
  doctrine YAML reader are removed outright, not deprecated in place.
- **No changes to quest and mission management.** `lore new`, `claim`, `done`,
  `block`, `needs`, `ready`, `board` and the priority model are untouched beyond
  the two mission flags named above.

---

## User Workflows

### Read a doctrine to plan a quest — AI agent (orchestrator)

**Persona:** The orchestrator agent, running the `start-quest` skill.
**Situation:** It has a settled feature request and a doctrine id, and must turn
them into a quest and its missions.
**Goal:** Learn the doctrine's shape in as few round-trips as possible.

**Steps:**

1. The orchestrator runs `lore doctrine show tdd-feature-lite`.
2. Lore prints the body of `tdd-feature-lite.design.md` verbatim, then a
   `--- Missions ---` section listing each mission's `id` and `title`, sorted by
   id. Exit 0.
3. With `--json`, Lore prints
   `{"doctrine": {"id", "title", "summary", "design", "missions": [{"id", "title", "summary"}], "origin"}}`
   on stdout. `raw_yaml` and `steps` are absent — those keys no longer exist.
4. The orchestrator reads the design prose, decides the step order and types
   from it, and proceeds to create missions. It does not read a mission body.

**Critical decision points:** A doctrine whose directory holds no `missions/`
still resolves and still prints its design; the index is empty.
**Success signal:** The design prose and the mission index arrive in one command.

**Python surface:** `lore.api.read_doctrine(project_root, doctrine_id, scope=None, mission=None)`
returns that same dict, or `None` when the **doctrine** does not resolve. With
`mission="red"` the returned dict carries an additional `mission` key holding
`{"id", "title", "summary", "body"}` when that mission exists, and `None` when the
doctrine resolves but the mission does not.

A bare `None` therefore means exactly one thing — the doctrine missed — and the
two failure cases stay distinguishable from the return value alone. This is what
lets the CLI emit a different message and the same exit code for each without
performing its own existence check, which ADR-011 forbids. It also keeps the
existing read-shape rule that a `read_*` function returns `None` on a miss rather
than raising.

### Read one mission body — AI agent or human

**Persona:** A human author checking what a mission tells a worker, or an agent
that needs the body without a Lore mission to hang it on.
**Goal:** Retrieve one doctrine mission file by id.

**Steps:**

1. Run `lore doctrine show tdd-feature-lite --mission recon`.
2. Lore prints the body of `.lore/doctrines/.../tdd-feature-lite/missions/recon.md`
   verbatim, frontmatter stripped. Exit 0.
3. With `--json`, stdout carries
   `{"mission": {"id": "recon", "title": "...", "summary": "...", "body": "..."}}`.
4. When the doctrine exists but the mission does not, stderr carries
   `Mission "recon" not found in doctrine "tdd-feature-lite"` and the exit code
   is 1. With `--json`, stderr carries `{"error": "<that same message>"}`.
5. When the doctrine itself does not resolve, stderr carries
   `Doctrine "tdd-feature-lite" not found` and the exit code is 1 — the existing
   message and code for that case, unchanged. The CLI tells the two apart from
   `read_doctrine`'s return value alone.

**Critical decision points:** `--mission` takes exactly one value — it is a
single-value flag, not a multi-value one, so ADR-012 does not apply.
**Success signal:** One mission body, no design prose around it.

### Create a doctrine — AI agent (running the `update-doctrine` skill)

**Persona:** An agent authoring a new doctrine from a design conversation.
**Goal:** Land a complete doctrine directory in one call.

**Steps:**

1. The agent writes the design document and each mission file into its scratchpad.
2. It runs:
   `lore doctrine new tdd-feature-lite --group default -d /tmp/design.md -m /tmp/recon.md /tmp/feature-spec.md /tmp/scribe.md`
3. Lore validates: the doctrine name; that no doctrine of that id already exists
   anywhere in the subtree; that the design file's frontmatter satisfies
   `doctrine-design-frontmatter` and its `id` equals the doctrine name; and that
   every mission file's frontmatter satisfies `doctrine-mission-frontmatter` with
   its `id` equal to that file's stem.
4. On success Lore writes the whole directory atomically — no partial doctrine is
   ever left on disk — and prints
   `Created doctrine tdd-feature-lite with 3 missions in group default`. Exit 0.
   With `--json`, stdout carries
   `{"created": "tdd-feature-lite", "group": "default", "missions": ["feature-spec", "recon", "scribe"], "path": ".lore/doctrines/default/tdd-feature-lite/"}`.
5. On any validation failure Lore writes nothing, prints the message to stderr,
   and exits 1. With `--json`, stderr carries `{"error": "<message>"}`.

**Critical decision points:** Both `-d` and at least one `-m` are required; a
doctrine with no missions is rejected with
`At least one mission file is required (-m)`. Two `-m` files sharing a stem is an
error, not a silent last-wins.
**Success signal:** `lore doctrine show <id>` returns the design and every mission.

**Python surface:**
`lore.api.create_doctrine(project_root, name, design_content, missions, group=None)`
where `missions` is a mapping of mission id to file content. Returns
`{"created", "group", "missions", "path"}`. Raises `ValueError` with the same
message on every condition that exits 1 above.

### Edit a doctrine — AI agent

**Persona:** An agent revising one mission after a doctrine proves imprecise in
practice.
**Goal:** Change one mission without re-supplying the rest.

**Steps:**

1. Run `lore doctrine edit tdd-feature-lite -m /tmp/recon.md`.
2. Lore replaces `missions/recon.md` and leaves every other mission and the
   design document untouched. It prints
   `Updated doctrine tdd-feature-lite (missions replaced: recon)`. Exit 0.
3. `-d` alone replaces the design document and touches no mission.
4. An `-m` file whose stem names no existing mission adds that mission.
5. `lore doctrine edit tdd-feature-lite --remove-mission refactor lint`
   soft-deletes both to `<id>.md.deleted` per ADR-003 and prints
   `Updated doctrine tdd-feature-lite (missions removed: lint, refactor)`.
   `--remove-mission` is multi-value and space-separated per ADR-012.
6. Passing none of `-d`, `-m`, `--remove-mission` is a usage error:
   `Nothing to update: pass -d, -m, or --remove-mission`, exit 1.
7. `--remove-mission` naming a mission that does not exist exits 1 with
   `Mission "lint" not found in doctrine "tdd-feature-lite"`, and nothing is
   removed.
8. Removing the last remaining mission is rejected — a doctrine keeps at least
   one mission, matching the create rule.

**Critical decision points:** `-m` merges by stem; it never wipes the set. The
only way to remove a mission is `--remove-mission`.
**Success signal:** The untouched missions are still present and byte-identical.

**Python surface:**
`lore.api.update_doctrine(project_root, name, design_content=None, missions=None, remove_missions=None)`
returns `{"updated", "design_replaced", "missions_replaced", "missions_removed"}`
and raises `ValueError` on each condition above.

### Assign a doctrine mission to a Lore mission — AI agent (orchestrator)

**Persona:** The orchestrator creating the quest's missions.
**Goal:** Point each Lore mission at its doctrine mission so the worker gets the
instructions without the orchestrator copying them.

**Steps:**

1. Run
   `lore new mission -q q-a1b2 "Map the codex and the binding decisions" -D tdd-feature-lite/recon -T agent -p 1 -d "<feature context>"`.
2. Lore stores `tdd-feature-lite/recon` in `missions.doctrine_mission` verbatim.
   It does not resolve or validate the reference at write time — consistent with
   ADR-004's storage posture and with how `missions.knight` behaved.
3. Output and exit code are unchanged from today's `lore new mission`.
4. `lore edit mission q-a1b2/m-c3d4 -D tdd-feature-lite/feature-spec` changes the
   reference; `--no-doctrine-mission` clears it. Passing both is a usage error,
   exactly as `--knight` and `--no-knight` are today.

**Critical decision points:** The reference form is `<doctrine-id>/<mission-id>`.
A bare mission id is stored as given and fails to resolve at read time.
**Success signal:** `lore show <mission-id>` carries the spliced body.

**Python surface:** `lore.api.create_mission(..., doctrine_mission=None, ...)` and
`lore.api.update_mission(..., doctrine_mission=None, remove_doctrine_mission=False, ...)`,
replacing the `knight` and `remove_knight` keyword arguments.

### Receive a mission as a worker — AI agent (worker)

**Persona:** A subagent handed a mission id and nothing else.
**Goal:** Learn what to do in one command.

**Steps:**

1. Run `lore show q-a1b2/m-c3d4`.
2. Lore prints the mission's title, status, priority, type, description, board
   messages — and, when `doctrine_mission` is set and resolves, the body of that
   doctrine mission file under a `--- Mission Instructions ---` heading.
3. With `--json`, the mission envelope carries `doctrine_mission` (the stored
   reference string, or `null`) and `doctrine_mission_contents` (the resolved
   body, or `null`). The keys `knight` and `knight_contents` no longer exist.
4. When the reference does not resolve, `doctrine_mission` keeps its stored value
   and `doctrine_mission_contents` is `null`. Exit 0, no error — the same silent
   behaviour a missing knight has today. `lore health` is what reports it.

**Critical decision points:** Resolution happens at read time, never at write
time. A doctrine edited after a mission was created changes what that mission's
worker reads.
**Success signal:** Description and instructions arrive together, one call.

**Python surface:** `lore.api.get_mission_detail(project_root, mission_id, include_doctrine_mission=True)`
returns the same dict, replacing the `include_knight` keyword.

### Audit a project after upgrading — human developer

**Persona:** A maintainer who has upgraded `lore` and re-run `lore init`.
**Goal:** Find out what the upgrade broke and what is now unread.

**Steps:**

1. Run `lore health --scope doctrines`.
2. For each authored doctrine still in the old shape, Lore emits **warnings**:
   `doctrines  tdd-feature  missing_missions_dir  no missions/ directory — this doctrine is not readable in the current shape`
   and
   `doctrines  tdd-feature  stray_yaml  tdd-feature.yaml is no longer read`.
   Warnings never affect the exit code, so the run exits 0 on these alone.
3. For each Lore mission that is active and whose `doctrine_mission` does not
   resolve, Lore emits an **error**:
   `doctrines  tdd-feature-lite/recon  missing_file  referenced by q-a1b2/m-c3d4 but not found on disk`,
   and exits 1. This replaces today's `_check_knights` audit at the same severity.
4. `lore health --scope knights` now exits 2 with Click's standard
   `Invalid value for '--scope': 'knights' is not one of ...` — the token is gone
   from the `click.Choice` (ADR-017).

**Critical decision points:** Old-shape doctrines warn rather than fail, so an
upgraded project's CI does not go red until the maintainer chooses to act.
**Success signal:** Every unread file is named, and nothing unread is silent.

### Upgrade a project — human developer

**Persona:** A maintainer running `lore init` on an existing project after
upgrading the package.

**Steps:**

1. The database migrates v6→v7: `missions.knight` is dropped,
   `missions.doctrine_mission TEXT` is added, and every row whose `mission_type`
   is `knight` is rewritten to `agent`. `schema_version` becomes `7`.
2. `reconcile` removes `.lore/knights/default/**` — a seeded default under
   ADR-024 — and names it in the removal report.
3. `.lore/doctrines/default/**` is reseeded in the new shape; the old paired
   files there are removed by the same seeded-default mechanism.
4. Knights the project authored outside `default/` are user files. Lore leaves
   them on disk untouched and names them in the report as no longer read, so the
   maintainer knows to fold them into doctrine missions.
5. The `update-knight` skill is removed from the installed set and reported as
   retired into `update-doctrine`.

**Critical decision points:** Lore deletes no file the project authored.
**Success signal:** The report distinguishes what Lore removed from what it left
behind and no longer reads.

---

## Functional Requirements

### Doctrine storage

- **FR-1:** A doctrine is a directory named for its id, holding
  `<id>.design.md` and a `missions/` directory of `.md` files.
- **FR-2:** A doctrine's group is derived from the path of the directory that
  contains the doctrine directory, so existing `--filter` behaviour over
  `lore doctrine list` is unchanged.
- **FR-3:** A doctrine mission file carries `id`, `title` and `summary`
  frontmatter, validated by a packaged `doctrine-mission-frontmatter` schema, and
  its `id` equals its filename stem.
- **FR-4:** No file in a doctrine carries step order, step type, phase or
  dependencies. Lore parses no workflow structure from a doctrine.

### Doctrine retrieval

- **FR-5:** An agent reads a doctrine's design and mission index in one command.
- **FR-6:** An agent reads one mission body by doctrine id and mission id.
- **FR-7:** Both retrievals are available on the CLI and through `lore.api`, with
  identical return shapes (ADR-011).
- **FR-8:** A doctrine is addressed by id, never by file path (ADR-006).

### Doctrine authoring

- **FR-9:** An agent creates a complete doctrine — design plus one or more
  missions — in a single atomic call.
- **FR-10:** An agent replaces the design, replaces or adds individual missions,
  and removes missions, in a single call, without re-supplying untouched files.
- **FR-11:** A removed mission is soft-deleted (ADR-003).
- **FR-12:** A doctrine always has at least one mission; create and edit both
  enforce it.

### Mission assignment and delivery

- **FR-13:** A Lore mission records a doctrine mission reference of the form
  `<doctrine-id>/<mission-id>`, stored verbatim and never interpreted at write
  time (ADR-004).
- **FR-14:** `lore show <mission-id>` resolves that reference at read time and
  splices the mission body into its output.
- **FR-15:** An unresolvable reference yields null contents and exit 0; it is
  reported by `lore health`, not by the read.

### Knight removal

- **FR-16:** No `lore knight` command exists.
- **FR-17:** No knight name appears in `lore.api.__all__`.
- **FR-18:** No knight schema ships and no knight files are seeded.
- **FR-19:** `lore health` offers no `knights` scope.
- **FR-19a:** `lore doctrine edit --set / --unset / --add / --remove` continues to
  edit a doctrine's frontmatter field by field, now against the design document.
  The capability is preserved, not dropped, and its schema becomes
  `doctrine-design-frontmatter`.
- **FR-19b:** `decisions-006-id-references` is edited in place. Its decision is
  unchanged — agents address entities by ID through the CLI, never by file path —
  and only its enumeration of entity categories is stale. It is not superseded and
  not marked superseded.
- **FR-20:** `mission_type` uses `agent`, `constable` and `human`; `knight` is
  not a token any seeded doctrine, skill or document uses.

### Health and upgrade

- **FR-21:** `lore health --scope doctrines` reports old-shape doctrines and
  stray doctrine YAML as warnings.
- **FR-22:** `lore health --scope doctrines` reports an unresolvable
  `doctrine_mission` on an active mission as an error.
- **FR-23:** The v6→v7 migration drops `missions.knight`, adds
  `missions.doctrine_mission`, and rewrites `mission_type` `knight` to `agent`.
- **FR-24:** `reconcile` removes seeded knights, leaves authored knights on disk,
  and names both outcomes in its report.

### Seeded content

- **FR-25:** A `mission-design.md` artifact ships under
  `src/lore/defaults/artifacts/lore-design-documents/`, templating a doctrine
  mission file: the frontmatter, the role the worker adopts, how it works, its
  hard rules, its inputs, its steps, its done criteria, and what it hands on.
- **FR-26:** `doctrine-design.md` is rewritten — no Knight column, no New Knights
  section, Type tokens `agent | constable | human`, and a Missions section
  listing each mission with a one-line purpose.
- **FR-27:** The four seeded doctrines ship in the new shape, with each former
  knight persona merged into the mission file that used it.
- **FR-28:** `skills-catalogue.yaml` retires `update-knight` into
  `update-doctrine`; the machinery family carries four skills.
- **FR-29:** `start-quest`, `update-doctrine`, `inquest` and `sync-codex-guide`
  are updated for the new shape; `update-knight` is removed.
- **FR-30:** `LORE-AGENT.md` and `GETTING-STARTED.md` describe six entity types
  and the `agent` mission type. `LORE-AGENT.md` and the repository's own agent
  instruction file receive the same shared-section edits.

---

## Non-Functional Requirements

### Performance

Performance here is round-trips, not milliseconds — ADR-001 makes minimising tool
calls a design constraint.

- An orchestrator reads a doctrine in **1** command, unchanged from today.
- A worker receives description and instructions in **1** command, unchanged from
  today.
- Authoring a complete doctrine is **1** command regardless of mission count,
  down from 1 + N today (one `lore doctrine new` plus one `lore knight new` per
  persona).
- Replacing one mission is **1** command.

### Security

Lore has no auth surface — local filesystem and SQLite only. Doctrine mission
files are read from within the project's `.lore/` tree, and the existing
path-traversal guard that protected knight lookups applies unchanged to doctrine
and mission id resolution: a reference containing `..` or an absolute path
resolves to nothing rather than escaping the tree. Cross-project reads stay
read-only (ADR-025).

### Reliability

- `lore doctrine new` and `lore doctrine edit` are atomic: a validation failure
  leaves the tree exactly as it was, and no partial doctrine directory is ever
  written.
- Concurrent access follows `conceptual-workflows-concurrent-access` unchanged;
  doctrine files are read-mostly and the write path goes through `safewrite`.
- The v6→v7 migration is idempotent and runs inside the existing migration chain.
- An unresolvable doctrine mission reference degrades to null contents rather
  than failing a worker's `lore show`.

---

## Pre-Architecture Notes

_(Appended by the user after reviewing this PRD — do not edit until sign-off phase)_
