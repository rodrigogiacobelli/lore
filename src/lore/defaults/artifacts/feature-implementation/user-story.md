---
id: fi-user-story
title: User Story
group: feature-implementation
summary: >
  Template for a single user story in the feature-implementation workflow.
  Used by the BA for both draft and final states. Includes mandatory E2E
  and unit test specifications — every acceptance criterion must map to a
  testable scenario. Tech Notes section is filled by the Tech Lead, not the BA.
---

## Metadata

- **ID:** US-{number}
- **Status:** draft | final
- **Epic:** _{epic-name}_
- **Author:** Business Analyst
- **Date:** {date}
- **PRD:** `lore codex show {prd-id}`
- **Tech Spec:** `lore codex show {tech-spec-id}`

---

## Story

As a _{role}_, I want _{specific action}_, so that _{concrete outcome}_.

## Context

_{Why this story exists. Which PRD workflow or functional requirement it fulfills. What the user is trying to accomplish and why it matters. Be specific — name the workflow from the PRD._

---

## Acceptance Criteria

_Every criterion is a testable scenario. Specify exact inputs, commands, flags, or interactions. Specify exact expected outputs, error messages, or state changes. Vague criteria will be rejected._

### E2E Scenarios

#### Scenario 1: {Descriptive name — happy path}

**Given** _{initial system state}_
**When** _{exact user action — e.g. `lore list --json` or "user clicks Submit with valid data"}_
**Then** _{exact expected outcome — include precise output format, status codes, or UI state}_

#### Scenario 2: {Descriptive name — edge case or error path}

**Given** _{initial state}_
**When** _{action}_
**Then** _{exact expected outcome}_

_(Add more scenarios as needed. Every workflow branch from the PRD must have a scenario.)_

### Unit Test Scenarios

_Specific behaviours that are too granular for E2E but must not be skipped._

- [ ] `{module or function}`: _{what to assert — e.g. "returns empty list when no items exist"}_
- [ ] `{module or function}`: _{what to assert}_
- [ ] `{module or function}`: _{edge case — e.g. "raises ValueError when input is None"}_

---

## Out of Scope

_Explicitly list what this story does NOT cover. This prevents scope creep into adjacent stories._

- _{Item 1}_
- _{Item 2}_

---

## References

- PRD: `lore codex show {prd-id}`
- Tech Spec: `lore codex show {tech-spec-id}`
- _{Any other relevant codex document}_

---

## Tech Notes

_(Filled by Tech Lead in tech-notes-draft and tech-notes-final phases — BA must not edit this section)_

### Implementation Approach

_{File-level notes on how to implement this story. References codex docs rather than duplicating them._

- **Files to create:** _{path — purpose}_
- **Files to modify:** _{path — what changes and why}_
- **Schema changes:** _{link to relevant schema doc if applicable}_
- **Dependencies:** _{other stories or systems this depends on}_

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/{test_file}` | _{what suite this belongs to}_ |
| Unit | `tests/unit/{test_file}` | _{what module this covers}_ |

### Test Stubs

_Before writing stubs, search the codex for relevant workflow documents:_
_`lore codex search workflow`._
_Each stub must cite the workflow document it exercises (by codex ID) in a comment._

```python
# E2E — {Scenario 1 name}
# Exercises: lore codex show {workflow-codex-id}, step {N}
def test_{scenario_1_slug}():
    # Given: {initial state setup}
    # When: {action}
    # Then: {assertion}
    pass


# Unit — {unit scenario}
# Exercises: lore codex show {workflow-codex-id}, step {N}
def test_{unit_scenario_slug}():
    # {what this verifies}
    pass
```

### Complexity Estimate

_{S / M / L / XL — one line justification}_
