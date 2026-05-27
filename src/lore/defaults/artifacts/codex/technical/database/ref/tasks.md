---
id: example-ref-app_db-tasks
title: Tasks cluster
summary: Reference doc for the tasks/users cluster — the intent, history, and non-enforced
  rules that schema cannot express. Points at the migration source of truth; does not
  mirror columns.
# related: []  # optional: codex IDs this doc links to outbound (see lore codex map)
# binds: []  # optional: repo-root-relative paths or globs this doc governs (see codex.md "The impacts engine")
---

# Tasks cluster

**Covers:** `tasks`, `users`
**Source of truth:** `db/migrations/`

> Replace the `**Covers:**` list with the actual entities your cluster owns. The list must name every covered entity verbatim — `lore codex search <entity_name>` lands on this doc only when the name appears here.

## Why this exists

_One paragraph. What product capability does this cluster serve? Why are these entities grouped together? What invariants hold across them that no single entity owns alone?_

## Gotchas

_The non-obvious rules a reader needs before writing a query or a migration. Each item is a fact that the schema does not enforce but the team treats as binding._

- _**No FK on `{column}`:** historical reasons — `{rationale}`. Reads must tolerate orphans._
- _**Soft-delete only:** `deleted_at IS NULL` filter required on every read query._
- _**Status transitions are app-side:** the `status` column has a CHECK on the value set, not on transitions. Enforce transitions in `{module}`._
- _**Backfill in progress:** `{column}` is nullable until `{date}`; treat NULL as `{meaning}` until then._

## Shape

_Brief shape note — table count, approximate column count, any partitioning or sharding. Full schema lives in the source-of-truth path above._

| Entity | Approx. columns | Notes |
|--------|-----------------|-------|
| `tasks` | ~10 | _One row per task_ |
| `users` | ~6 | _One row per user_ |

## Ownership

_Which team or codeowner is responsible for migrations and intent in this cluster? When in doubt, who decides?_

## Lifecycle

_Anything dated: deprecation timelines, planned splits, tables scheduled for retirement, columns planned to drop. If nothing applies, delete this section._
