---
id: fi-prd-draft
title: PRD Draft
group: feature-implementation
summary: >
  Template for the PM to write the initial PRD Draft from raw user input.
  Covers executive summary, success criteria, user workflows, functional and
  non-functional requirements. The user appends unstructured feedback directly
  to this file before the PM produces the final PRD.
---

# {Feature Name} — PRD Draft

**Author:** Product Manager
**Date:** {date}
**Input:** _{raw user input}_

---

## Executive Summary

_{One paragraph: what this feature is, who it is for, and what problem it solves._

### What Makes This Special

_{The single differentiator — what this does that alternatives do not._

---

## Project Classification

| Attribute | Value |
|-----------|-------|
| Project type | _{web app / CLI tool / API / library / ...}_ |
| Primary users | _{persona or role}_ |
| Scale | _{expected user count / throughput at launch}_ |

---

## Success Criteria

### User Success

_{What "winning" looks like for end users — problem resolved, goal achieved._

### Technical Success

_{Performance thresholds, reliability targets, compliance requirements._

| Metric | Baseline | Target | Timeline |
|--------|----------|--------|----------|
| _{...}_ | _{...}_ | _{...}_ | _{...}_ |

---

## Product Scope

### MVP

_{Essential capabilities required to prove core value. Keep this list ruthlessly small._

- _{Capability 1}_
- _{Capability 2}_

### Post-MVP

- _{Feature 1}_

### Out of Scope

- _{Explicit exclusions to prevent scope creep}_

---

## User Workflows

### {Workflow Name} — {User Type}

**Persona:** _{Name, role, context}_
**Situation:** _{Current challenge or pain point}_
**Goal:** _{What they want to achieve}_

**Steps:**
1. _{Opening scene}_
2. _{User action — specific command, click, or interaction}_
3. _{System response — exact output or state change}_
4. _{Resolution}_

**Critical decision points:** _{Where things could go wrong or fork}_
**Success signal:** _{How the user knows they succeeded}_
**Requirements revealed:** _{Specific capabilities this workflow exposes}_

---

## Functional Requirements

### {Capability Area 1}

- **FR-1:** {Actor} can {capability}.
- **FR-2:** {Actor} can {capability}.

### {Capability Area 2}

- **FR-3:** {Actor} can {capability}.

---

## Non-Functional Requirements

### Performance

- _{e.g. P95 response time < 200 ms}_

### Security

- _{e.g. All data at rest encrypted with AES-256}_

### Reliability

- _{e.g. 99.9% uptime SLA}_

---

## Open Questions

| # | Question | Owner | Priority |
|---|----------|-------|----------|
| 1 | _{Question}_ | _{PM / User / Architect}_ | _{High / Medium / Low}_ |
