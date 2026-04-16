---
id: decisions-011-api-parity-with-cli
title: 'ADR-011: Python API must be safe and behaviourally equivalent to the CLI'
summary: Establishes that every lore.db function exposed in the public API must be
  self-contained and safe to call directly — no pre-validation, post-processing, or
  business logic may live exclusively in the CLI layer. The CLI becomes a thin formatting
  wrapper. Any gap is a bug.
related:
- decisions-010-public-api-stability
- standards-separation-of-concerns
- tech-api-surface
- tech-db-schema
- tech-arch-validators
---

# ADR-011: Python API must be safe and behaviourally equivalent to the CLI

**Status:** ACCEPTED

## Context

`lore.db` is now a public API (ADR-010). External consumers — Realm, user scripts, future integrations — import and call these functions directly, bypassing the CLI entirely.

An audit of the CLI layer against `lore.db` found three classes of gap where the CLI adds logic that `lore.db` does not replicate:

1. **Input validation in the CLI only** — e.g. `add_board_message` rejects empty messages in the CLI but the DB function accepts them silently.
2. **Return value gaps** — e.g. `close_mission` returns `quest_closed: bool` but not which quest was closed. The CLI re-queries to recover this. An API caller cannot.
3. **Status change detection** — e.g. `claim_mission` does not return the new quest status. The CLI re-queries before and after to detect the change.

These gaps mean that a Python script calling `lore.db` directly does not get the same guarantees as a user running the CLI. This is unacceptable for a public API.

## Decision

**Every function in `lore.db` that is part of the public API must be self-contained and safe to call directly.**

Specifically:

1. **All input validation moves into `lore.validators`.** Business rules live in `src/lore/validators.py` — a dedicated, import-safe module with no dependencies on the rest of `lore`. Both `lore.db` and `cli.py` import from `validators` and call the same functions. The CLI may keep its own validation calls for UX (early exit, click-formatted errors) but must not be the *only* place a rule is enforced — and must never duplicate logic that already exists in `validators`.

2. **All relevant state changes are reflected in the return value.** If an operation has side effects (quest status derived, quest auto-closed, block reason cleared), the return dict must include enough information for the caller to know what happened without issuing follow-up queries.

3. **The CLI becomes a thin formatting wrapper.** It calls db functions, formats results for human or JSON output, and exits. It adds no business logic that a Python caller would need to replicate.

**Validation ownership is now locked (ADR-012 refactor, Decision 1):**

- `validators.py` is the foundation utility. It has no imports from any `lore.*` module
  and is callable by any layer.
- `db.py` is the authoritative enforcement layer. Write operations that are Realm-callable
  retain their `validators.*` calls (e.g., `add_board_message`, `claim_mission`,
  `create_quest`, `create_mission`).
- `cli.py` pre-checks are the redundant layer. Where `db.py` already enforces a rule,
  the `cli.py` pre-check is removed rather than kept in sync. `cli.py` validation
  helpers (`_validate_mission_id`, `_validate_entity_id`, etc.) are thin UX translators
  that delegate entirely to `validators.*` — they contain no local regex logic.

**Exception:** `remove_dependency` does not retain a format check in `db.py`. Its
contract is existence-based: a malformed ID produces a "not found" response, which is
acceptable for a delete-by-existence operation. This is explicitly documented in
`tech-arch-source-layout` and in REFACTOR-15.

## Consequences

- `lore.validators` is the single source of truth for all business rules.
- `lore.db` enforces rules by calling validators — it contains no inline validation logic.
- `cli.py` calls the same validators for UX purposes — it never owns a rule.
- The CLI is guaranteed to produce identical outcomes to equivalent direct API calls.
- As new API functions are added, their validation goes into `lore.validators` first. Any rule that exists only in the CLI is a bug.
- Existing gaps are bugs and must be fixed before the API is considered stable. See `spec-api-parity-gap-analysis` for the fix plan.
- CLI helpers (`_validate_mission_id`, `_validate_entity_id`, `_validate_sender_id`,
  `_validate_name`) contain no inline regex. Each delegates to the corresponding
  `validators.*` function and translates the result into a Click-formatted error.
- `validators.py` exports: `validate_message`, `validate_entity_id`,
  `validate_mission_id`, `validate_priority`, `validate_name`,
  `validate_quest_id_loose`, `route_entity`.
- `validate_quest_id_loose` uses the pattern `^q-[a-z0-9]{4,8}$` and is documented for
  test-DB-inserted IDs only. It must not be used for new ID creation.

## Alternatives Rejected

**Keep business logic in the CLI, expose a separate "safe API" layer.** Rejected — two codepaths diverge over time and create exactly the class of bugs we are trying to prevent.

**Document the gaps and leave them to callers.** Rejected — the gaps involve data integrity (empty board messages) and information loss (which quest auto-closed). Callers should not need to know about internal CLI re-querying patterns.
