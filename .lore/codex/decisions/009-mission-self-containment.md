---
id: decisions-009-mission-self-containment
title: Missions must be self-contained — board messages carry the chain, artifacts carry the content
summary: >
  ADR establishing that a mission must be executable using only its description
  and its board. Board messages are lightweight operational messages posted by
  predecessor agents to guide successor missions (pointers, paths, IDs). They
  are distinct from artifact instances (ADR-007), which carry structured work
  output. The two mechanisms are complementary and operate at different layers
  of formality.
related: ["decisions-007-artifact-communication-protocol", "tech-db-schema", "tech-cli-commands"]
stability: stable
---

# ADR-009: Missions must be self-contained — board messages carry the chain, artifacts carry the content

**Status:** ACCEPTED

## Context

A multi-step pipeline (such as the adversarial-spec doctrine) requires each
step to locate and consume the output of its predecessor. There are three ways
to pass that context to the next agent:

1. **The orchestrator relays it.** After a step completes, the orchestrator
   reads the output, then edits the next mission's description to include file
   paths, IDs, or other operational details.

2. **The mission description is written speculatively.** The orchestrator
   writes all missions upfront with placeholder context it cannot yet know
   (file paths the predecessor hasn't created, IDs that don't exist yet).

3. **The completing agent leaves a message for its successor.** The agent that
   produced the output posts a board message to the next mission's board:
   "I created file X at path Y." The successor reads its board when it starts
   and knows exactly what to consume.

Option 1 requires the orchestrator to stay in the loop between every step — a
violation of the intent that agents work independently. It also requires the
orchestrator to understand the output of every step well enough to summarise
it, which is error-prone and lossy.

Option 2 is impossible for dynamic outputs (file paths generated at runtime,
IDs assigned during execution).

Option 3 makes each mission self-contained. The description is written at
planning time (static intent). The board receives dynamic context at runtime
(what was actually produced). Together they are sufficient.

ADR-007 established that official communication between pipeline steps happens
through artifact instances — structured documents that represent the actual
work output (analyses, specs, stories). ADR-007 did not address how the next
agent *finds* those artifacts, or how lightweight operational context (not
structured output) is passed between steps. The mission board fills that gap.

## Decision

**A mission must be executable using only its description and its board.**

- The **description** is written at planning time by the orchestrator. It
  describes what the mission requires, what it must produce, and where to look.
  It should not contain dynamic context that can only be known at runtime.

- The **board** receives dynamic context at runtime. When an agent completes
  a mission and produces output, it posts a board message to each successor
  mission that needs to know about it. The message is a short operational note:
  a file path, an entity ID, a status, a pointer. Not a summary of the work.

**Board messages and artifact instances are complementary, not competing.**

| | Artifact instance (ADR-007) | Board message (this ADR) |
|---|---|---|
| **What it carries** | Structured work output — the actual deliverable (analysis, spec, story) | Operational pointer — how to find the deliverable ("artifact at path X") |
| **Format** | Template-driven. Defined structure, sections, frontmatter | Free-form text. No template. Short. |
| **Audience** | The pipeline step that consumes it as structured input | The specific mission whose board it was posted to |
| **Persistence** | Permanent record. Retained after the pipeline completes. | Ephemeral operational context. Can be soft-deleted once consumed. |
| **Written by** | The agent that produces the work output | The agent that produced the output, posting a pointer to the next mission |
| **Governed by** | ADR-007 | This ADR |

A completing agent typically does both: writes its work to an artifact instance
(ADR-007) and posts a board message to the next mission pointing to that
artifact. The artifact is the content; the board message is the chain.

**The orchestrator does not relay context between steps.** Once a mission is
dispatched, the orchestrator's job for that mission is done. It does not
monitor output, edit subsequent missions, or act as a relay. The completing
agent and the board handle continuity.

## Rationale

**Orchestrator relay is fragile and lossy.** Summaries lose detail.
Re-encoding output from one agent through an orchestrator before passing it to
the next introduces an interpretation layer that can drop or distort
information.

**Dynamic context cannot be known at planning time.** File paths, IDs, and
other runtime outputs are determined by execution, not by the plan. Speculative
descriptions with placeholder values are either wrong or too vague.

**Self-contained missions are independently auditable.** An agent that needs
to re-execute or debug a mission can read its description and board and
understand the full context without reconstructing the orchestrator's
reasoning.

**The board is not a substitute for a good description.** Static intent —
what the mission is for, what it must produce, what it should not touch —
belongs in the description, written at planning time. The board carries only
what cannot be known until a predecessor runs. Overloading the board with
static context defeats the purpose of the description and makes missions
harder to understand in isolation.

## Consequences

- Completing agents are responsible for posting board messages to successor
  missions when they produce dynamic outputs that successors need.
- Orchestrators write descriptions at planning time with static intent only.
  They do not edit missions after dispatch to relay runtime context.
- The `lore board add <entity-id> "<message>"` command is the mechanism for
  posting. The sender field (optional, Lore ID format) identifies which mission
  or quest the posting agent was executing.
- Doctrine step notes should instruct completing agents to post board messages
  to successor missions when applicable.
- ADR-007 is not modified. Its scope — structured content communication via
  artifact instances — is unchanged. This ADR adds a complementary layer for
  operational chain communication.

## Alternatives considered

**All context in the mission description, written speculatively.** Rejected.
Dynamic outputs (runtime file paths, assigned IDs) cannot be known at planning
time. Placeholder values are inaccurate; overly broad descriptions ("look for
any file matching X pattern") are fragile.

**Orchestrator edits subsequent missions after each step completes.** Rejected.
Requires the orchestrator to stay in the loop between every step, understand
every output format, and make additional CLI calls per step. Violates the
intent of independent agent execution and the "minimise tool calls" principle
(ADR-001).

**Extend artifact instances to carry operational pointers.** Rejected.
Artifacts are structured, template-driven documents meant to be read and
processed as work input. Embedding operational pointers ("file at path X")
inside them conflates content with chain mechanics, bloats the template, and
breaks the clean separation between "what was produced" and "how to find it."
