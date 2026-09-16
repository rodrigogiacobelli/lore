---
id: spec-gate
title: Review the reconciled Tech Spec — append feedback
summary: The human reads the reconciled Tech Spec including its ADR & Standards Audit, resolves anything the audit blocked on, and appends feedback directly to the spec before planning starts.
---

# Spec Gate

You are the human reviewing the reconciled Tech Spec. This is the doctrine's steering point: everything downstream — the stories, their sizing, the codex changes, and every dev cycle — is built on the spec as it leaves this gate.

## How You Work

You read the spec as the contract it is about to become, not as a draft. The ADR & Standards Enforcer has already rewritten every line that contradicted a settled decision, so what reaches you is a spec that obeys the record; what it could not settle mechanically is listed for you at the bottom.

Your feedback goes into the file. A decision made only in conversation does not reach the missions that run after this one.

## Hard Rules

- If the audit verdict is `BLOCKED`, resolve the listed escalations before marking done — do not waive them
- Feedback is appended to the Tech Spec file itself, not left in chat
- Do not mark done while an escalation is unsettled

## Inputs

Your board carries the Tech Spec ID, the PRD ID, and the audit verdict.

- Read the reconciled Tech Spec: `lore codex show <tech-spec-id>` — including the ADR & Standards Audit section at the bottom
- Read the PRD for the product intent: `lore codex show <prd-id>`

## Steps

Read the reconciled Tech Spec from your board, including the ADR & Standards Audit section at the bottom.

If the verdict is `BLOCKED`, resolve the listed escalations before proceeding.

Append your feedback directly to the Tech Spec file — no specific format required.

## Done Criteria

- The audit's escalations are settled, not waived.
- Your feedback is written into the Tech Spec file.

Mark done.

## Hands On

The annotated, settled Tech Spec, to the tech-planning and codex-apply missions.
