---
id: conceptual-entities-doctrine
title: Doctrine
summary: What a Doctrine is — a directory holding a design document the orchestrator reads and one mission file of prose per worker. Doctrines are passive; Lore parses no workflow structure out of them. Covers discovery, group derivation, the validation rules, and the .deleted directory rename.
related: ["conceptual-entities-quest", "conceptual-entities-mission", "conceptual-entities-glossary", "ref-lore_doctrine-module", "conceptual-relationships-doctrine--mission", "conceptual-relationships-doctrine--quest"]
binds:
- src/lore/doctrine.py
---

# Doctrine

A Doctrine is a reusable workflow template stored as a directory of prose. The directory holds `<stem>.design.md` — the design document an orchestrator reads — and an optional `missions/` subdirectory of `.md` files, one per reusable instruction. Doctrines are **passive documents**: there is no template engine, no variable substitution, no execution. An orchestrator reads a Doctrine and uses it as a guide when creating the corresponding Quests (lore codex show conceptual-entities-quest) and Missions (lore codex show conceptual-entities-mission) via CLI commands.

Lore parses no workflow structure out of a Doctrine. It reads the design document's frontmatter for identity — `id`, `title`, `summary` — and each mission file's frontmatter for its index entry, and treats every body as an opaque string. Step order, mission type, phases and dependencies are decided by the orchestrator from the design prose (lore codex show decisions-001-dumb-infrastructure).

The design document describes:

- Which missions the workflow involves, and their suggested order and dependencies
- Which type each mission is — `agent`, `constable` or `human`
- What each mission reads and what it produces
- References to Artifact (lore codex show conceptual-entities-artifact) IDs the workflow uses

A mission file is one worker's whole brief: the role it adopts, how it works, its hard rules, its inputs, its steps, its done criteria, and what it hands on. It is the single authoritative copy of every reusable instruction the workflow needs. A Lore Mission reaches one through the reference `<doctrine-id>/<mission-id>` stored in `missions.doctrine_mission` (lore codex show conceptual-relationships-doctrine--mission).

Doctrines are stored in the project's `.lore/doctrines/` directory tree. For module internals see ref-lore_doctrine-module (lore codex show ref-lore_doctrine-module). For CLI commands see ref-lore_cli-commands (lore codex show ref-lore_cli-commands).

## Directory Shape

```
.lore/doctrines/<group…>/<stem>/
├── <stem>.design.md
└── missions/
    ├── <mission-id>.md
    └── <mission-id>.md
```

A directory `D` is a doctrine if and only if `D/<D.name>.design.md` exists. The design file's name is derived from the directory name, which is what makes the directory the unit of identity: a design file sitting anywhere other than a directory of its own name identifies no doctrine.

A mission's id is its filename stem. `missions/red.md` is the mission `red`, and a Lore Mission reaches it as `<doctrine-id>/red`.

## Discovery

`lore init` places bundled default doctrines inside `.lore/doctrines/default/`. User-created doctrines (added via `lore doctrine new`) land directly in `.lore/doctrines/`, or under `--group <path>`. Both `lore doctrine list` and `lore doctrine show` search the full `.lore/doctrines/` directory tree recursively.

**Any path segment beginning with `.` or ending `.deleted` hides everything at and below it.** That one rule makes a soft-deleted doctrine and the staging directory `lore doctrine new` builds equally invisible to every listing, every read, and `lore health`.

A doctrine's **group** is derived from the path between `.lore/doctrines/` and the doctrine directory, so a doctrine at `.lore/doctrines/default/feature-implementation/tdd-implementation/` carries the group `default/feature-implementation`.

`lore doctrine list` returns a flat list of every doctrine found in the tree, in path order. A directory whose design file carries no `id` frontmatter is silently skipped.

`lore doctrine show <name>` resolves a doctrine by its directory name. The search is subtree-wide and the shallowest match wins. Doctrine names are expected to be unique across the tree; `lore health --scope doctrines` reports a duplicate declared id as an error.

## Validation Rules

`lore doctrine new` validates everything before anything reaches disk, in this order:

1. Name format — one path segment, valid identifier characters
2. Group format
3. No doctrine of that name already exists anywhere in the subtree
4. The design document has frontmatter and its `id` matches the command argument
5. The design frontmatter validates against `lore://schemas/doctrine-design-frontmatter`
6. At least one mission file is supplied
7. Each mission id is a valid name
8. Each mission file's frontmatter `id` equals its filename stem
9. Each mission's frontmatter validates against `lore://schemas/doctrine-mission-frontmatter`

Both schemas require exactly `id`, `title` and `summary` and reject any other key.

Only when every rule passes does anything reach disk, and it reaches it whole: `create_doctrine` builds the tree inside a dot-prefixed staging directory and moves it into place with one `os.replace`, so no partial doctrine is ever left behind — a crash mid-write included (lore codex show decisions-031-staged-multi-file-entity-write).

`lore doctrine edit` validates everything first as well, so a validation failure leaves the tree exactly as it was. It merges by stem: a mission the caller does not name is left byte-identical.

A doctrine always keeps at least one live mission. `lore doctrine edit --remove-mission` refuses a removal set that would empty the doctrine.

## Soft-Delete Semantics

`lore doctrine delete <name>` soft-deletes a Doctrine by renaming its directory to `<name>.deleted`. The skip rule then makes the renamed directory invisible everywhere, with no second mechanism (lore codex show decisions-003-soft-delete-semantics).

`lore doctrine edit --remove-mission <id>` soft-deletes one mission file: `missions/<id>.md` becomes `missions/<id>.md.deleted`.

`delete_doctrine` raises `ValueError` when the directory does not exist.

## Example

**`my-workflow/my-workflow.design.md`:**
```markdown
---
id: my-workflow
title: My Workflow
summary: Standard development workflow.
---

# My Workflow

## Doctrine

| Phase | Mission | Type | Depends On | Input | Output |
|-------|---------|------|------------|-------|--------|
| 0 | design | agent | — | Feature request | Design document |
| 0 | review-design | human | design | Design document | Annotated design |
| 1 | implement | agent | review-design | Annotated design | Working code |

## Missions

- **design** — Produces a design document with acceptance criteria.
- **review-design** — Human review of the design.
- **implement** — Implements the reviewed design.
```

**`my-workflow/missions/design.md`:**
```markdown
---
id: design
title: Design the feature
summary: Produces a design document with acceptance criteria.
---

# Designer

You are the Designer. …
```

## Related

- Quest (lore codex show conceptual-entities-quest) — the live grouping of Missions that an orchestrator creates following a Doctrine
- Mission (lore codex show conceptual-entities-mission) — the individual tasks described by a Doctrine's missions
- Artifact (lore codex show conceptual-entities-artifact) — template files referenced by ID in a design or mission body
- ref-lore_doctrine-module (lore codex show ref-lore_doctrine-module) — validation pipeline and module internals
- ref-lore_cli-commands (lore codex show ref-lore_cli-commands) — `lore doctrine` command reference
