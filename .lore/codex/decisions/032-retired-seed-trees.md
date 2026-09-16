---
id: decisions-032-retired-seed-trees
title: "ADR-032: A seeded tree Lore stops shipping is removed by an explicit retired-tree list"
summary: >
  ADR recording init.RETIRED_SEED_TREES — the tuple naming a seeded tree Lore has
  stopped shipping. Every lore init run walks each named tree, unlinks
  every regular file in it, reports each removal, and prunes the emptied
  directories, leaving symlinks and unlinkable files alone. Files a project
  authored outside the retired subtree are named once and never touched.
binds:
  - src/lore/init.py
related:
  - decisions-030-knight-entity-removed
  - decisions-024-default-group-is-seeded-boundary
  - conceptual-workflows-init-reconcile
  - conceptual-workflows-lore-init
---

# ADR-032: A seeded tree Lore stops shipping is removed by an explicit retired-tree list

## Context

`lore init` re-seeds each `default/` tree and prunes it of what the release no
longer ships, driven by `init.SEEDED_TREES`. The prune walks only trees still in
that tuple. Removing the `knights` row — the obvious way to stop shipping
knights — therefore stopped anything from ever looking at `.lore/knights/default/`
again, so every seeded knight would stay on disk in every upgraded project,
silently, forever. `conceptual-workflows-init-reconcile`'s reconciliation table
cannot help: those paths are inside `.lore/`, and the manifest records nothing
inside `.lore/`.

## Decision

`init.py` carries a `RETIRED_SEED_TREES` tuple naming a seeded tree Lore has
stopped shipping. Every run walks each named tree, unlinks every regular file in
it, reports each as `Removed <label>/<path> — no longer shipped`, and prunes the
emptied directories, leaving any symlink and any unlinkable file alone exactly
as `_prune_seeded_tree` does.

`.lore/knights/default` is its first entry.

Files a project authored outside the retired tree are not touched; they are
collected and named once so the maintainer knows they are no longer read.

## Rationale

- **Dropping a row from `SEEDED_TREES` orphans files rather than removing
  them.** The prune is reachable only from the seed, so a tree no longer seeded
  is a tree no longer swept.
- **The removal must survive an arbitrary number of skipped releases.** A
  project upgrading from three releases back needs the same sweep as one
  upgrading from the last, which a per-version migration step does not give.
- **A project's own files are not Lore's to delete.** The retired subtree is
  exactly the boundary `decisions-024` already draws, so naming orphans outside
  it and touching nothing is the behaviour that boundary already implies.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Leave the `knights` row in `SEEDED_TREES` with an empty package** | `_defaults_tree_files` would have to walk a package that no longer exists, and the row would claim Lore still ships knights. |
| **A one-off cleanup in `run_init`** | This module was written specifically to avoid a per-version migration chain, and the second retired tree would have to repeat the trick. |
| **Hard-code the removal in `reconcile.py`** | `reconcile` is about paths outside `.lore/`, and its safety property is that a path in neither the desired nor the recorded set is never touched; a seeded tree is in neither set. |

## Consequences

**Easier:**
- Retiring a seeded tree is one row, and it keeps working however many
  releases a project skips before upgrading.
- A maintainer is told exactly which of their own files Lore has stopped
  reading, without any of them being moved or deleted.

**Harder:**
- The tuple is append-only in practice: removing a row stops the sweep for any
  project that has not yet upgraded past it, which is the failure the tuple
  exists to prevent.
- A retired tree's name survives in the source after the entity it held is
  gone, so a search for that entity's name finds a legitimate match here.

## Constraints Imposed

1. **A seeded tree Lore stops shipping gets a `RETIRED_SEED_TREES` row
   in the same change that drops it from `SEEDED_TREES`.** Dropping one without
   the other orphans the files permanently.
2. **Nothing outside the named retired subtree is removed.** Files a project
   authored are named in the report and left on disk.
3. **A symlink and an unlinkable file are skipped, never raised on.** The
   restraint `_prune_seeded_tree` shows applies here unchanged.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-09-16 | accepted | Recorded alongside `RETIRED_SEED_TREES` and its first entry, `.lore/knights/default`. |
