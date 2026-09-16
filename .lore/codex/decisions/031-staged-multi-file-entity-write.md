---
id: decisions-031-staged-multi-file-entity-write
title: "ADR-031: A multi-file entity write is staged in a temp directory and renamed into place"
summary: >
  ADR recording that doctrine.py uses lore.safewrite, and that create_doctrine
  builds the complete directory in a dot-prefixed staging directory inside
  .lore/doctrines/ and moves it into place with one os.replace, so no partial
  doctrine is ever left on disk. update_doctrine validates everything first and
  then writes per file; its guarantee is scoped to validation failure.
binds:
  - src/lore/doctrine.py
  - src/lore/safewrite.py
related:
  - decisions-029-doctrine-is-prose-not-a-graph
  - conceptual-entities-doctrine
  - conceptual-workflows-doctrine-new
  - ref-lore_doctrine-module
---

# ADR-031: A multi-file entity write is staged in a temp directory and renamed into place

## Context

No entity module used `lore.safewrite`; `doctrine.py`, `knight.py`, `rite.py`,
`artifact.py` and `watcher.py` all wrote with plain `Path.write_text()`, and the
two-file `create_doctrine` wrote the YAML and then the design file with no
atomicity between them. `safewrite` existed and was used by `init.py`,
`manifest.py` and `reconcile.py`, and gives per-file atomicity plus a symlink
and escape refusal. The directory model's create path writes 1 + N files at
once, and the promise is that no partial doctrine is ever left on disk.

## Decision

`doctrine.py` uses `lore.safewrite`.

`create_doctrine` validates everything, builds the complete directory in a
staging directory whose name begins with `.` inside `.lore/doctrines/`, writes
each file through `safewrite.atomic_write_text`, and moves the whole tree into
place with one `os.replace`. Doctrine discovery skips any path segment
beginning with `.` or ending `.deleted`, which is what makes the staging
directory invisible while it exists.

`update_doctrine` validates everything first and then writes per file; its
guarantee is scoped to validation failure and is stated as such.

## Rationale

- **A 1 + N file write has no per-file atomicity that adds up to a whole.**
  Writing the design and then each mission leaves a window in which
  `lore doctrine show` half-answers, and no amount of per-file care closes it.
- **The skip rule already existed and costs nothing to reuse.** A dot-prefixed
  directory is invisible to discovery for the same reason a `.deleted` one is,
  so staging needs no second mechanism to stay hidden.
- **`os.replace` on the same filesystem is the one move that is atomic.**
  Staging inside `.lore/doctrines/` guarantees the rename does not cross a
  filesystem boundary.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Sequential `write_text`, as before** | Cannot deliver the guarantee for 1 + N files, and would leave a half-built doctrine that `lore doctrine show` would then half-answer. |
| **`tempfile.mkdtemp` outside `.lore/`** | `os.replace` across filesystems fails, and `/tmp` on a user's machine is routinely a different one. |
| **Extend the staged swap to `update_doctrine`** | A rebuild would have to copy every `.md.deleted` tombstone to preserve it, for a crash window nobody has reported, and the edit guarantee is scoped to validation failure. |

## Consequences

**Easier:**
- `lore doctrine new` either produces a complete, readable doctrine or leaves
  the tree exactly as it was, with no intermediate state any reader can see.
- `doctrine.py` inherits `safewrite`'s symlink and escape refusal on every
  file it writes, without a second guard of its own.

**Harder:**
- A crash between the last staged write and the `os.replace` leaves a
  dot-prefixed directory behind. It is invisible to every read, but it is not
  cleaned up until the next create of the same name.
- `update_doctrine` and `create_doctrine` now offer different guarantees, and a
  caller reading only one of them may assume the stronger one applies to both.

## Constraints Imposed

1. **Every file `doctrine.py` writes goes through `safewrite`.** A direct
   `Path.write_text()` in that module is a defect.
2. **The staging directory lives inside `.lore/doctrines/` and its name begins
   with `.`.** Moving it elsewhere breaks the atomic rename.
3. **`create_doctrine` writes nothing until every validation rule has passed.**
   Validation and writing are separate phases, in that order.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-09-16 | accepted | Recorded alongside `create_doctrine`'s staged build, the first use of `lore.safewrite` by an entity module. |
