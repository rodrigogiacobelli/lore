---
id: conceptual-workflows-rite-show
title: lore rite show Behaviour
summary: What the system does internally when `lore rite show <id> [<id> ...]` runs — rendering a main rite's full node-graph with every use:-referenced shared step inlined flat (no recursion), multi-id fail-fast retrieval with dedup, bare-shared-step resolution, the structured JSON envelope that attaches the inlined step on the use-node, and the not-found / dangling-use error paths.
binds:
- src/lore/rite.py
- src/lore/cli.py
- tests/e2e/test_rite_show.py
- tests/unit/test_rite.py
related:
  - conceptual-entities-rite
  - conceptual-workflows-rite-list
  - conceptual-workflows-doctrine-show
  - conceptual-workflows-error-handling
  - conceptual-workflows-json-output
  - ref-lore_cli-commands
---

# `lore rite show` Behaviour

`lore rite show <id> [<id> ...]` renders a rite in full. For a main rite it
prints the entire node-graph and conclusions, **inlining every `use:`-referenced
shared step** into one flat document so an agent gets the complete picture in a
single call (precedent: conceptual-workflows-doctrine-show). Inlining is
**non-recursive** — shared steps don't `use:` anything.

## Preconditions

- The Lore project has been initialised.
- Each given id resolves to a main rite or a shared step (not soft-deleted), and
  every shared step a shown main rite `use:`es exists.

## Steps

### 1. Resolve each id (fail-fast)

`read_rite(rites_dir, rite_id)` resolves `<id>` by its **bare id**, scanning
`main/` then `shared/` **recursively** for the file whose `id:` matches — the
codex resolution model (`lore codex show <id>`). The subfolder a rite lives in is
irrelevant to resolution. A bare **shared-step** id is also resolvable — when the
matching id is a shared step, it is rendered alone. Multiple ids are accepted and
deduped via `dict.fromkeys`.

The command is **fail-fast**: if any id (or any shared step a main rite
references via `use:`) is missing, **zero partial output** is emitted before the
error — matching the codex/artifact `show` rule (ref-lore_cli-commands).

### 2. Inline `use:` steps (by id, across the tree)

For each `use`-node in a main rite, the referenced shared step is resolved **by
id** anywhere under `shared/` (recursive) and inlined in place — the `use:` value
is a bare id, never a path, and the step may live in a different group than the
main rite. No recursion (a shared step has no `use:`). A `use:` id that matches no
shared step anywhere is a dangling-`use:` error at show time.

### 3. Render output

**Text mode** — main rite with shared steps inlined where `use:` appears:
```
=== issue-refund ===
# Issue a refund for a returned order

Trigger: Customer requests a refund on a returned order.
Summary: Confirm the customer is reachable, then refund.

[locate-order]  Find the order by id; confirm it is in 'returned' state.
  -> get-contact

[get-contact]  use: read-contact-info
  read-contact-info — Read the user's contact information
    Open the user profile in admin. Read and report back:
      - email
      - phone
      - mailing address, with its last-confirmed date
  -> review-contact

[review-contact]  Decide whether contact details support a refund.
  if email and a current mailing address are present -> do-refund
  if anything is missing or the address looks stale -> request-update

[do-refund]  Post the refund to billing. Record the txn id.
  -> (conclusion) refunded

[request-update]  Ask the customer to confirm contact details first.
  -> (conclusion) contact-requested

Conclusions:
  refunded  (audience: customer-care)
    Refund posted; share the transaction id.
  contact-requested  (audience: customer-care)
    Refund held pending a contact-details update.
```

Multiple ids: each block is separated by `=== <id> ===` (codex `show`
precedent).

### 4. JSON mode

`lore rite show` accepts a local `--json` (mirroring `lore show`) in addition to
the global flag. The envelope is structured, with each inlined shared step
attached to its `use`-node under a `"step"` key (the flatten):

```json
{
  "rites": [
    {
      "id": "issue-refund",
      "title": "Issue a refund for a returned order",
      "summary": "Confirm the customer is reachable, then refund.",
      "trigger": "Customer requests a refund on a returned order.",
      "nodes": [
        {"id": "locate-order", "do": "Find the order by id; confirm it is in 'returned' state.", "then": "get-contact"},
        {"id": "get-contact", "use": "read-contact-info", "then": "review-contact",
         "step": {"id": "read-contact-info", "title": "Read the user's contact information", "summary": "Look up the customer's email and phone on file.", "do": "Open the user profile in admin. Read and report back:\n  - email\n  - phone\n  - mailing address, with its last-confirmed date\n"}},
        {"id": "review-contact", "do": "Decide whether contact details support a refund.",
         "then": [{"if": "email and a current mailing address are present", "goto": "do-refund"},
                  {"if": "anything is missing or the address looks stale", "goto": "request-update"}]},
        {"id": "do-refund", "do": "Post the refund to billing. Record the txn id.", "then": "refunded"},
        {"id": "request-update", "do": "Ask the customer to confirm contact details first.", "then": "contact-requested"}
      ],
      "conclusions": {
        "refunded": {"audience": "customer-care", "response": "Refund posted; share the transaction id."},
        "contact-requested": {"audience": "customer-care", "response": "Refund held pending a contact-details update."}
      }
    }
  ]
}
```

A shown bare shared-step id returns the bare shared-step object inside `rites`.
Errors emit `{"error": "<message>"}` to stderr.

## Python API

```python
from lore.api import read_rite, RiteError
from pathlib import Path

rites_dir = Path(".lore/rites")
try:
    rite = read_rite(rites_dir, "issue-refund")   # dict; use-nodes carry resolved steps
except RiteError as e:
    print(f"Error: {e}")
```

`read_rite` resolves the bare id recursively across the whole tree and returns
the rite dict with a resolved inline of every `use:` step (each looked up by id
across `shared/`). `RiteError` (subclass of `ValueError`) covers not-found,
dangling-`use:`, and ambiguous-duplicate-id at show time. CLI and Python
behaviour are identical (ADR-011).

## Failure Modes

| Failure | Message (stderr) | JSON (stderr) | Exit |
|---|---|---|---|
| Rite id not found | `Rite "<id>" not found` | `{"error": "Rite \"<id>\" not found"}` | 1 |
| Rite soft-deleted | `Rite "<id>" not found (deleted on <ts>)` | `{"error": "...", "deleted_at": "<ts>"}` | 1 |
| Dangling `use:` at show time | `Rite "<id>": shared step "<use-id>" not found` | `{"error": "Rite \"<id>\": shared step \"<use-id>\" not found"}` | 1 |
| Any id missing in a multi-arg call | first failing id's message (fail-fast, no partial output) | same | 1 |

## Out of Scope

- Recursive inlining — shared steps don't `use:` other steps.
- Editing rite content — use `lore rite edit` (conceptual-workflows-rite-crud).
- Listing rites — use `lore rite list` (conceptual-workflows-rite-list).

## Related

- conceptual-entities-rite (lore codex show conceptual-entities-rite) — the node-graph and shared-step model
- conceptual-workflows-doctrine-show (lore codex show conceptual-workflows-doctrine-show) — the show-precedent this mirrors
- conceptual-workflows-rite-list (lore codex show conceptual-workflows-rite-list) — listing rites
- conceptual-workflows-error-handling (lore codex show conceptual-workflows-error-handling) — fail-fast and exit-code contract
- ref-lore_cli-commands (lore codex show ref-lore_cli-commands) — full CLI reference
