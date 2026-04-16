---
id: decisions-007-artifact-communication-protocol
title: Artifact instances are the official communication protocol between pipeline
  steps
summary: 'ADR recording the decision that official communication between steps in
  a multi-step pipeline (human or AI) happens through artifact instances, not through
  prose in mission descriptions or side channels. Each step declares an input artifact
  and produces an output artifact. This makes handoffs auditable and forces every
  step to produce something concrete before the next step can start.

  '
related:
- decisions-009-mission-self-containment
- tech-db-schema
---

# ADR-007: Artifact instances are the official communication protocol between pipeline steps

**Status:** ACCEPTED

## Context

The adversarial-spec doctrine is a multi-step pipeline. Each step consumes the
output of the previous step and produces output that the next step consumes.
Before this decision, the handoff between steps was implicit: a step would
append content to a file, and the next step would read that file by convention.
There was no explicit declaration of what a step consumed or produced, and no
enforcement that the output existed before the next step began.

This created two failure modes:

1. **Missing outputs.** A step could complete without producing its expected
   output, and the next step would proceed anyway — reading a partial or
   stale file.

2. **Unstructured handoffs.** Human steps in particular had no defined format
   for their contribution. Human input arrived as unstructured prose in mission
   descriptions, which then had to be interpreted by the next AI step. This
   interpretation was a source of lost requirements and incorrect scope
   assumptions.

The introduction of Phase 1 (Requirements) made this problem acute. Phase 1
includes human steps that must communicate their review comments and sign-off
to AI steps in a structured, auditable way.

## Decision

Official communication between steps in a pipeline happens through **artifact
instances** — files on disk that are instances of a defined artifact template.

Each step in a doctrine that passes information to a downstream step must:

1. Declare which artifact instance it reads as input (by file path in the
   mission description).
2. Produce or append to an artifact instance as output (also referenced by
   file path).

Human steps follow the same protocol. A human step reads the artifact instance
produced by the previous step and appends their contribution to it using the
section provided by the template. The artifact instance is the official record
of the human's input — not the mission description, not a chat message, not a
verbal summary.

The consolidating step at the end of a phase reads the final artifact instance
(which by that point contains all prior contributions) and produces the next
artifact — typically the business spec or full spec.

## Consequences

- Every handoff is traceable. The artifact instance on disk is the record of
  what was agreed, reviewed, and signed off.
- Human steps have a defined format. The template provides sections for human
  contribution; the human fills in those sections and nothing else.
- Steps cannot be skipped silently. If the expected input artifact does not
  exist or is incomplete (e.g. human sign-off section is empty), the next step
  should block rather than proceed on incomplete input.
- Artifact templates must be designed with the pipeline in mind. Each template
  should make clear which sections are produced by which step type.

## Artefacts covered by this decision

| Phase | Step | Input | Output |
|-------|------|-------|--------|
| Phase 1 | intake (knight) | unstructured human request (mission description) | `preliminary-analysis` instance |
| Phase 1 | intake-review (human) | `preliminary-analysis` instance | same file + Human Review Comments section |
| Phase 1 | codex-check (knight) | `preliminary-analysis` + comments | `refined-analysis` instance |
| Phase 1 | intake-signoff (human) | `refined-analysis` instance | same file + Final Comments and Sign-off section |
| Phase 1 | spec-write (knight) | `refined-analysis` + sign-off | `transient-business-spec` instance in `specs/` |
| Phase 2+ | (existing steps) | spec in `specs/` | spec in `specs/` (append or rewrite) |

## Alternatives considered

**Passing content through mission descriptions.** The orchestrator could
summarise the previous step's output in the next mission's description. This
was rejected because it is lossy (summaries lose detail), introduces an
interpretation layer, and is not auditable — the mission description is
ephemeral, the artifact instance is not.

**Freeform file conventions.** Steps could write to any file by convention
without a template. This was rejected because it produces inconsistent output
and gives human steps no structure to follow.
