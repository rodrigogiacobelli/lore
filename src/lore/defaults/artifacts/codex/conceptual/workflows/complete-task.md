---
id: example-workflow-{workflow-name}
title: "{Workflow Name}"
related: []
stability: stable
entities_involved:
  - example-entity-{entity-name}
summary: >
  _One to three sentences. What triggers this workflow? What does the system do?
  What is the end state?_
---

# {Workflow Name}

_One paragraph. Describe what triggers this workflow and what the system does from start to finish._

## Preconditions

- _The record must exist and not be soft-deleted._
- _The status must be in a valid state for this operation._
- _The actor must be {role or context}._

> List all conditions that must be true before the workflow can execute.

## Steps

1. **{Step name}** — _Description. What is checked, fetched, or computed._

2. **{Step name}** — _Description. What is written, updated, or emitted. Note any transaction boundaries._

3. **{Step name}** — _Description. Any post-commit side effects (notifications, logs). Note failure tolerance._

> Steps should be at the level of "what the system does", not "what code runs". Use plain language.

## Failure Modes

| Failure point | Behaviour | Exit code |
|---------------|-----------|-----------|
| {Record not found} | _Error message to stderr_ | 1 |
| {Invalid state transition} | _Error message to stderr_ | 1 |
| {Database write fails} | _Error message with detail; state unchanged_ | 1 |
| {Side-effect fails} | _Warning to stderr; primary operation is not rolled back_ | 0 |

## Out of Scope

- _What this workflow explicitly does not do. Helps prevent scope creep in implementations._
- _What other commands or operations handle instead._
