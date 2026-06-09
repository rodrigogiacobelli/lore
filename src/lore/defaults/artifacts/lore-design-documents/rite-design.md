---
id: rite-design
title: Rite Design Guide
summary: >
  How to author rites — Lore's procedural memory ("how to do or diagnose
  recurring task X"). Explains the main-rite node-graph, the pure shared step,
  recursive grouping, globally-unique ids, and AI-as-matcher retrieval, then
  walks one complete worked example end to end. Read this before writing a rite;
  use `lore artifact show rite-main` / `rite-shared-step` for the bare skeletons.
---

# Rite Design Guide

A **rite** is procedural memory: the *how-to* counterpart of the codex. The codex
stores semantic, factual knowledge ("what is true"); a rite stores a procedure
("how to do or diagnose recurring task X"). Rites are not documentation and not
templates that spawn work (that is a doctrine) — they are organised know-how any
agent can read and follow in the moment.

## The two shapes

**Main rite** (`.lore/rites/main/…`) — a small node-graph that carries the
judgment. Nodes have a `do` (an instruction) or a `use` (pull in a shared step),
an edge `then` (a straight next, or a fork of `if`/`goto`), and the graph ends in
one of a set of typed `conclusions`.

**Shared step** (`.lore/rites/shared/…`) — a small, reusable, *pure* procedure:
just `id`, `title`, `summary`, `do`. One platform, one screen, one query. It runs
and reports; it never branches and never concludes. A shared step is a *step*, not
a mini-rite — it has no nodes and cannot `use:` another step. `summary` is a
one-line what-it-does (required, like every entity); it carries no `trigger` —
only main rites are matched by situation, a shared step is pulled in by id.

The split is the whole point: **judgment lives in the rite, procedure lives in the
step.** A step says "read the contact info and report it"; the rite decides what
to do based on what came back.

## Identity, grouping, retrieval

- **IDs are globally unique, like codex ids.** A rite or shared step is
  identified by its `id` across the entire tree — the subfolder is *not* part of
  identity. `use: read-contact-info` resolves that bare id wherever it lives under
  `shared/`. Two files sharing an id anywhere is an error (`lore health`).
- **Folders are cosmetic groups.** `.lore/rites/main/` and `shared/` discover
  **recursively**, exactly like every other Lore entity; the subfolder path
  becomes the `group` shown by `lore rite list` and filterable with `--filter`.
  Group small shared steps by platform — `shared/portal/…`, `shared/backoffice/…`,
  `shared/db/…` — so they stay browsable.
- **Retrieval is AI-as-matcher.** Lore never matches a situation to a rite for
  you. An agent reads `lore rite list` (each rite's `trigger` + `summary`) and
  picks the fit itself. Write the `trigger` as a clear prose cue and the `summary`
  as a one-line outcome — those two lines are the entire retrieval surface.
- **Links point one way: codex → rite.** A codex doc lists the rites it governs
  via its `rites:` field. Rites carry no `related`/`binds` — they get distilled
  and rewritten often, so outbound links would just go stale.

## Worked example

A small customer-operations domain across a **portal**, a **backoffice** billing
system, and a **db**. Five granular shared steps, grouped by platform; two main
rites that compose them — one "do" rite, one "diagnose" rite.

### Shared steps

`shared/portal/find-order.yaml`
```yaml
id: find-order
title: Find an order in the customer portal
summary: Search the portal by order id and report the order's id, state, total, and last change date.
do: |
  Open the customer portal and search Orders by the order id the caller gave you.
  Report back the order id and state, the total and currency, and the date of the
  most recent state change. If nothing matches, say so — do not guess a near match.
```

`shared/portal/read-contact-info.yaml`
```yaml
id: read-contact-info
title: Read the customer's contact information in the portal
summary: Read the customer's email, phone, and mailing address from the portal profile.
do: |
  Open the customer profile in the portal. Read and report back: email, phone, and
  mailing address with its last-confirmed date. Note any field that is blank or
  whose last-confirmed date is older than 12 months.
```

`shared/backoffice/read-fraud-flag.yaml`
```yaml
id: read-fraud-flag
title: Read the fraud-risk flag in the backoffice
summary: Report the order's fraud-risk flag and reason code from the backoffice Risk panel.
do: |
  Open the order in the backoffice Risk panel. Report the fraud-risk flag
  (clear / review / blocked) and the reason code beside it, exactly as shown.
  Do not interpret a "review" as either clear or blocked.
```

`shared/backoffice/post-refund.yaml`
```yaml
id: post-refund
title: Post a refund in the backoffice
summary: Refund the order total to the original payment method and report the transaction id.
do: |
  Open the order in the backoffice Billing panel and refund the order total to the
  original payment method. Report the refund transaction id and the refunded
  amount. If Billing rejects it, report the exact message and stop — do not retry.
```

`shared/db/query-account-status.yaml`
```yaml
id: query-account-status
title: Query an account's status in the database
summary: Run the read-only account-status query and report status, locked_reason, and last login.
do: |
  Run the read-only account-status query, substituting the account id:

      SELECT status, locked_reason, last_login_at
      FROM accounts WHERE id = :account_id;

  Report status (active / locked / closed), locked_reason if locked, and
  last_login_at. Read-only — never run an UPDATE or DELETE from this step.
```

### Main rite — a "do" rite

`main/billing/issue-refund.yaml`. Note every `use:` names a **bare id** — Lore
finds the step regardless of which subfolder it lives in.
```yaml
id: issue-refund
title: Issue a refund for a returned order
summary: Confirm the order is returned and the customer reachable and not fraud-flagged, then refund.
trigger: A customer asks for a refund on an order they have returned.

nodes:
  - id: find-order
    use: find-order                 # bare id; the step lives in shared/portal/
    then: check-returned

  - id: check-returned              # judgment lives here, not in the step
    do: Confirm the order is in the 'returned' state.
    then:
      - if: the order is returned
        goto: read-contact
      - if: the order is in any other state
        goto: not-returned

  - id: read-contact
    use: read-contact-info
    then: review-contact

  - id: review-contact
    do: Decide whether the contact details are complete and current enough to refund.
    then:
      - if: email and a current mailing address are present
        goto: read-fraud
      - if: anything is missing or the last-confirmed date is stale
        goto: request-update

  - id: read-fraud
    use: read-fraud-flag
    then: assess-fraud

  - id: assess-fraud
    do: Decide whether the fraud-risk flag permits an automatic refund.
    then:
      - if: the flag is clear
        goto: post-refund
      - if: the flag is review or blocked
        goto: fraud-hold

  - id: post-refund
    use: post-refund
    then: refunded

  - id: request-update
    do: Ask the customer to confirm their contact details before the refund proceeds.
    then: contact-requested

conclusions:
  refunded:
    audience: customer-care
    response: Refund posted; share the transaction id with the customer.
  contact-requested:
    audience: customer-care
    response: Refund held pending a contact-details update from the customer.
  fraud-hold:
    audience: risk-team
    response: Refund held on a fraud flag; route to the risk team with the reason code.
  not-returned:
    audience: customer-care
    response: Order is not in a returned state; explain the return must complete first.
```

`lore rite show issue-refund` inlines every shared step flat into one document:
```
=== issue-refund ===
# Issue a refund for a returned order

Trigger: A customer asks for a refund on an order they have returned.
Summary: Confirm the order is returned and the customer reachable and not fraud-flagged, then refund.

[find-order]  use: find-order
    find-order — Find an order in the customer portal
      Open the customer portal and search Orders by the order id …
  -> check-returned

[check-returned]  Confirm the order is in the 'returned' state.
  -> if the order is returned: read-contact
  -> if the order is in any other state: not-returned

…

Conclusions:
  refunded  (audience: customer-care)
    Refund posted; share the transaction id with the customer.
  …
```

### Main rite — a "diagnose" rite

`main/support/diagnose-failed-login.yaml` — same shape, used to *diagnose* rather
than *do*. A three-way fork on the account status, reusing the db and portal
steps:
```yaml
id: diagnose-failed-login
title: Diagnose a customer's failed login
summary: Read the account status, then route to unlock, credential reset, or escalation.
trigger: A customer reports they cannot log in and basic retries have not helped.

nodes:
  - id: query-status
    use: query-account-status
    then: assess-status

  - id: assess-status
    do: Decide the cause of the failed login from the account status.
    then:
      - if: status is locked
        goto: unlock
      - if: status is active (so credentials are the likely cause)
        goto: verify-contact
      - if: status is closed or unrecognised
        goto: escalate

  - id: unlock
    do: Confirm the customer's identity, then clear the lockout on the account.
    then: account-unlocked

  - id: verify-contact
    use: read-contact-info
    then: send-reset

  - id: send-reset
    do: Send a credentials-reset link to the confirmed email on file.
    then: credentials-reset

  - id: escalate
    do: Hand the case to engineering with the account-status output attached.
    then: escalated

conclusions:
  account-unlocked:
    audience: customer-care
    response: Lockout cleared; ask the customer to try logging in again.
  credentials-reset:
    audience: customer-care
    response: Reset link sent to the confirmed email; advise the customer to follow it.
  escalated:
    audience: engineering
    response: Account is closed or in an unknown state; engineering to investigate.
```

### What `lore rite list` shows

The group is derived from the subfolder; ids stay bare:
```
ID                      GROUP    TRIGGER                                                       SUMMARY
diagnose-failed-login   support  A customer reports they cannot log in and basic retries …     Read the account status, then route to unlock, credential reset, or escalation.
issue-refund            billing  A customer asks for a refund on an order they have returned.  Confirm the order is returned and the customer reachable …
```
`lore rite list --shared --filter portal` narrows to the portal steps;
`lore rite list --shared` lists every step with its `GROUP`.

## Authoring checklist

1. **Is it procedure, not fact?** Facts go in the codex. A rite is steps + the
   judgment between them.
2. **Is it reusable enough to be shared, and judgment-free?** Then it is a shared
   step (`id`, `title`, `do`, single exit). If it branches, it is a main rite.
3. **One entry, no dangles, reachable nodes, matched conclusions.** Run `lore
   health --scope rites` — it checks reference integrity, graph well-formedness,
   the orphan asymmetry (an unused shared step is flagged; an unlinked main rite
   is fine), and global id uniqueness.
4. **Trigger + summary carry retrieval.** Write them for the agent who will scan
   `lore rite list` and decide whether this is the rite for the situation.
5. **Link from the codex, not the rite.** If a codex doc governs this rite, add
   the rite's id to that doc's `rites:` field.

## Rite vs doctrine

A **doctrine** is an upstream, authored template that *spawns* quests and missions
— it plans work. A **rite** is procedural knowledge any agent (knight or not)
follows to carry out or diagnose a recurring task. Doctrine = how work is
organised; rite = how a task is actually done.
