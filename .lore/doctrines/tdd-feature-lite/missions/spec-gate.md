---
id: spec-gate
title: Resolve every conflict, rule on every draft ADR, and release development
summary: The doctrine's only human gate and its pre-development pause. The human resolves every Part 3 conflict, rules on every draft ADR, settles every audit escalation, and writes the decisions into the spec's Pre-Dev Notes.
---

# Spec Gate

You are the human at the gate. This is the doctrine's only steering point, and it is deliberately also the pre-development pause. Nothing is dispatched past it until it closes.

## How You Work

The spec that reaches you has already been rewritten to obey every settled decision. What is left for you is what the record does not settle: the conflicts the architect found and did not resolve, the new decisions it drafted as ADRs, and whatever the audit could not fix mechanically.

Your decisions go into the spec's Pre-Dev Notes section. That section is what the dev lanes read; a decision made only in chat does not reach them.

## Hard Rules

- A blank Resolution cell in the Part 3 conflicts table blocks this gate
- Every draft ADR is approved, amended, or rejected **in writing** — silence is not approval
- If the verdict is `BLOCKED`, it is resolved, not waived
- Decisions are written into the spec's Pre-Dev Notes, never left in conversation

## Inputs

Your board carries the spec ID and the audit verdict.

- Read the spec: `lore codex show <spec-id>` — including the ADR & Standards Audit section at the bottom

## Steps

Before marking done:

- Every row in the Part 3 conflicts table has a Resolution: comply, amend the decision, or supersede it. A blank Resolution cell blocks this gate.
- Every draft ADR in Part 3 is approved, amended, or rejected in writing.
- Every escalation the audit listed is settled.
- If the verdict is `BLOCKED`, it is resolved — not waived.
- Confirm the feature branch is `feat/<feature-slug>` off `work`.

Write your decisions into the spec's Pre-Dev Notes section. That section is what the dev lanes read; a decision made only in chat does not reach them.

## Done Criteria

- No Resolution cell in the Part 3 conflicts table is blank.
- Every draft ADR carries a written approval, amendment, or rejection.
- Every audit escalation is settled and the verdict is no longer `BLOCKED`.
- The branch is confirmed as `feat/<feature-slug>` off `work`.
- The Pre-Dev Notes section carries every decision you made.

Mark done.

## Hands On

The settled spec with its Pre-Dev Notes, to the dev-foundation mission and every dev lane after it.
