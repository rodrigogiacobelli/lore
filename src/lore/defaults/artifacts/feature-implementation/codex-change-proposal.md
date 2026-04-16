---
id: fi-codex-change-proposal
title: Codex Change Proposal
summary: Template for the Tech Writer to propose additions, updates, or deletions
  to the project codex after the Tech Spec is complete. Lists every document to create,
  update, or retire — with rationale for each. The Tech Writer applies these changes
  directly after the proposal is written (no separate AR step).
---

# {Feature Name} — Codex Change Proposal

**Author:** Tech Writer
**Date:** {date}
**PRD:** `lore codex show {prd-id}`
**Tech Spec:** `lore codex show {tech-spec-id}`

---

## Orientation

_Summary of what this feature changes in the project's documented understanding. One paragraph._

---

## Documents to Create

| Proposed ID | Type | Group | Title | Rationale |
|-------------|------|-------|-------|-----------|
| _{id}_ | _{decision / technical / operations / ...}_ | _{codex group}_ | _{title}_ | _{why this new doc is needed}_ |

### Draft Content

_For each document to create, provide a content outline or full draft below._

#### {Proposed ID}

_{Draft content or detailed outline}_

---

## Documents to Update

| Existing ID | Section(s) | Proposed Change | Rationale |
|-------------|------------|-----------------|-----------|
| _{id}_ | _{section name}_ | _{what changes}_ | _{why}_ |

### Update Details

_For each document to update, describe the specific changes._

#### {Existing ID}

**Current state:** _{brief description of what it says now}_
**Proposed change:** _{what to add, modify, or remove}_

---

## Documents to Retire

| Existing ID | Rationale |
|-------------|-----------|
| _{id}_ | _{why this document is no longer needed or has been superseded}_ |

---

## Consistency Check

_Verify that the proposed changes do not contradict existing codex documents._

- _{Doc A}_ — _{no conflict / updated to align}_
- _{Doc B}_ — _{no conflict / updated to align}_

---

## Workflow Coverage

_For every new or changed CLI command in this feature, there must be a corresponding workflow doc. For every new user-facing flow, there must be a corresponding workflow doc. List each one — whether it is being created, updated, or confirmed unchanged._

| Command / Flow | Workflow ID | Action |
|----------------|-------------|--------|
| _{command or flow name}_ | _{conceptual-workflows-...}_ | _{create / update / no change needed}_ |

---

## Coverage Gaps

_Any aspects of the feature that should be documented but are not addressed above. Flag these explicitly rather than leaving them undocumented._

- _{Gap 1 — why it's out of scope for this proposal}_
