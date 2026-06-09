---
id: decisions-016-rite-json-envelope-omits-group
title: "ADR-016: Rites are recursive and grouped like every other entity; JSON envelopes carry group"
summary: >
  ADR recording that rites are discovered recursively and carry a group derived
  from their subfolder path, bringing them in line with every other Lore entity.
  A rite's identity is its id, globally unique across the entire main/ + shared/
  tree (the codex model); the subfolder path is cosmetic. The rite
  list/new/delete --json envelopes CARRY the group key (root → null), reversing
  the original flat/no-group decision.
binds:
  - src/lore/cli.py
  - src/lore/rite.py
related:
  - conceptual-entities-rite
  - conceptual-workflows-rite-list
  - conceptual-workflows-rite-crud
  - conceptual-workflows-json-output
  - decisions-011-api-parity-with-cli
---

# ADR-016: Rites are recursive and grouped like every other entity; JSON envelopes carry `group`

## Context

The JSON output contract (conceptual-workflows-json-output) establishes that
every `list` and `new` envelope carries a `group` key — slash-joined when the
entity lives in a nested subdirectory, `null` at the entity root. This holds
across all five other `list` commands (codex/artifact/knight/doctrine/watcher)
and all four other `new` commands (doctrine/knight/watcher/artifact). Each of
those entities is discovered recursively (rglob) and derives its `group` from
its path relative to its base directory.

Rites originally shipped as the lone exception: a flat id space split only by
kind — `main/` for full rites and `shared/` for shared steps — with no
recursion, no `--group`, no `--filter`, and a JSON envelope that omitted the
`group` key. That divergence made rites the one entity an integrator had to
special-case, and it prevented authors from organising a growing rite library
into folders.

Key forces:

- **Every other file-backed entity is recursive and grouped.** Rites being flat
  was a one-off that broke parity and forced special-casing in tooling.
- **Identity should not depend on folder.** Like the codex, a rite's identity is
  its `id:` field — globally unique across the entire tree — and the folder is
  purely organisational.
- **The kind split (`main` vs `shared`) is orthogonal to grouping** and is
  already carried by the `kind` field and the separate `list` envelope keys
  (`rites` vs `shared_steps`). Grouping is an additional, independent axis.

## Decision

Rites are discovered **recursively** under `main/` and `shared/`, and each rite
carries a **`group`** derived from its path relative to `main/`/`shared/`
(slash-joined; root → empty/`null`), exactly like every other entity. A rite's
identity is its `id:`, **globally unique across the whole `main/` + `shared/`
tree** (the codex model); the subfolder path is cosmetic — it derives the
`group` used only for display and filtering, never for identity.

- `lore rite list` recurses, shows a **GROUP column**, and supports
  **`--filter GROUP…`** (space-separated, ADR-012), like the other list commands.
- `lore rite new <name> [--shared] --group <path>` places the file at
  `main/<group>/<name>.yaml` (or `shared/<group>/...`); `--group` is optional
  (root if omitted). Id uniqueness is enforced across the whole tree.
- `lore rite show <id>` / `edit <id>` / `delete <id>` take the **bare id** and
  resolve it by recursively scanning for the matching `id` (mirroring how
  `lore codex show <id>` and watcher edit/delete resolve). `use:` references the
  bare id and resolves by scanning the whole `shared/` tree.
- The rite `--json` envelopes for `list`, `new`, and `delete` **CARRY the
  `group` key** (root → `null`):
  - `lore rite list --json` → `{"rites": [{id, group, trigger, summary}]}`;
    `--shared` → `{"shared_steps": [{id, group, title, summary}]}`.
  - `lore rite new --json` → `{"id", "kind", "group", "filename", "path"}`.
  - `lore rite delete --json` → `{"id", "group", "deleted_at"}`.

There is **no longer a carve-out** in conceptual-workflows-json-output: rites now
follow the group-key-always rule like every other entity.

## Rationale

- **Parity over exception.** A single recursive, grouped model across all six
  file-backed entities removes the rite special-case from both the mental model
  and any integrator's code.
- **Id is identity, folder is cosmetic** — the codex model. Authors can reorganise
  rites into folders without breaking `use:` references or `show`/`edit`/`delete`,
  because resolution is by id, not path.
- **Field-presence-always is restored.** `group` is always present on the rite
  envelopes (null at root), so consumers need no rite-specific branch.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Keep rites flat and omit `group` (original decision)** | Made rites the lone non-recursive entity; forced special-casing in tooling and blocked folder organisation of a growing rite library. |
| **Recurse but keep `group` off the JSON envelope** | Half-measure that still breaks the json-output contract and leaves consumers unable to read the group they can see in the table. |
| **Derive identity from path (folder-qualified ids)** | Rejected — diverges from the codex model, makes `use:` references brittle, and breaks when a rite is moved between folders. |

## Consequences

**Easier:**
- Rites share one model with every other entity; integrators write no
  rite-specific code.
- Authors organise rites into subfolders; ids stay stable references.

**Harder:**
- Id uniqueness must be enforced across the whole tree (a duplicate id in two
  subfolders is an error), and health gains a `duplicate_rite_id` check.

## Constraints Imposed

1. **Rite ids are globally unique across the entire `main/` + `shared/` tree.**
   A duplicate id in two files anywhere is a `duplicate_rite_id` health error.
2. **`group` is carried on `rite list`, `rite new`, and `rite delete` JSON**
   (root → `null`), per the json-output contract — no rite carve-out.
3. **`show`/`edit`/`delete`/`use:` resolve by bare id recursively** across the
   whole tree; the subfolder path never participates in identity.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-06-02 | accepted | Initial decision — rite list/new/delete JSON envelopes OMIT the group key; rites are a flat namespace with no recursion, --group, or --filter. Recorded during Rites codex-apply; flagged by the ADR & Standards Audit as a divergence from the json-output contract |
| 2026-06-02 | revised | Reversed the flat/no-group decision. Rites are now discovered recursively and carry a group derived from their subfolder path, like every other entity; ids are globally unique across the whole tree (codex model); the list/new/delete --json envelopes CARRY group (root → null). The json-output carve-out is removed and health gains a duplicate_rite_id check |
