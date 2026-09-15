---
id: decisions-027-glossary-collision-resolves-local-first
title: "ADR-027: A glossary keyword collision resolves local-first"
summary: >
  ADR resolving a keyword shared by a local glossary item and an inherited
  one: read_glossary_item and the auto-surface matcher return the local item,
  because both must answer with a single item. scan_glossary (list and
  search) keeps both rows visible, each carrying its origin, so the
  collision itself is never hidden.
binds:
  - src/lore/glossary.py
related:
  - decisions-001-dumb-infrastructure
  - conceptual-workflows-nested-projects
  - conceptual-workflows-glossary
  - conceptual-entities-glossary
  - conceptual-workflows-impacts
---

# ADR-027: A glossary keyword collision resolves local-first

## Context

Glossary inheritance means a project sees its own glossary items plus
everything an ancestor exports as `[shared].glossary = true`. A local item and
an inherited item can share the same keyword. Two callers need one answer
regardless of a collision: `read_glossary_item` returns a single
`GlossaryItem | None`, and the auto-surface matcher that scans document prose
for known keywords must return a deduplicated list, not two competing
definitions for the same term.

## Decision

On a keyword collision between a local item and an inherited one, the **local
item wins** for every lookup that must answer with a single item
(`read_glossary_item`, the auto-surface matcher). `scan_glossary` — the
listing and search path — keeps both rows visible, each carrying its origin,
so the collision itself is never hidden; only a single-answer lookup collapses
it.

## Rationale

- **Local-first matches the project's own stated rule for the whole
  feature** — a project preserves what it sees in its own folder, not what
  sits above or below it. Applied to a keyword instead of to a seeded default,
  this is the same instinct ADR-024 applies to files.
- **This does not breach ADR-001.** The return types force a single answer
  regardless of which item is chosen — `GlossaryItem | None`,
  a deduplicated list — and the rule is fixed and written down here, not
  inferred at runtime from surrounding context. An inferred-at-runtime
  resolution is the shape ADR-001 actually rejects; a fixed, documented
  precedence is not.
- **Lore already resolves an analogous collision the same way.** `lore
  impacts` reports a codex entry that matches a path both exactly and via a
  glob pattern once, not twice — one deterministic answer for two ways of
  matching the same target. This ADR applies the same instinct to a glossary
  keyword matched both locally and by inheritance.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Reject the collision (fail loudly)** | Would break every command that reads a document whose auto-surfaced keyword collides with an inherited one, for no benefit — both definitions stay visible via `list`/`search` regardless of which lookup wins. |
| **Ancestor wins** | Inverts the project's own stated rule that a project sees what is in its own folder first; would let an ancestor silently override a project's own vocabulary. |
| **Merge or concatenate both definitions** | Neither consuming caller accepts two definitions where one string is expected; would require a new return shape that nothing else in the feature asks for. |

## Consequences

**Easier:**
- A project's own terminology always governs its own codex, regardless of
  what a tree above it exports.

**Harder:**
- An ancestor's carefully-written definition can be silently shadowed by a
  same-named local item its author did not realise collided, discoverable
  only by running `lore glossary list` or `lore glossary search`.

## Constraints Imposed

1. **`read_glossary_item` and the auto-surface matcher return the local item
   on a collision**; an inherited item is a candidate only when no local item
   shares its keyword.
2. **`scan_glossary` returns every item, local and inherited, each carrying
   its origin** — a collision is discoverable there even though a
   single-answer lookup hides it.
3. **`lore health`'s glossary checks run over the project's own glossary file
   only.** An inherited item is never a candidate for this project's own
   duplicate-keyword check.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-09-02 | accepted | Recorded alongside glossary inheritance and the local-first resolution in `read_glossary_item` and the auto-surface matcher. |
