---
id: fi-tech-spec
title: Tech Spec
summary: Template for the final Tech Spec produced by the Architect after incorporating
  user feedback from the Tech Spec Draft review and insights from the Crazy Tech Spec.
  This is the authoritative technical document — clean, complete, all decisions made.
  Flows to BA, Tech Writer, and Tech Lead.
---

# {Feature Name} — Tech Spec

**Author:** Architect
**Date:** {date}
**Supersedes:** _{Tech Spec Draft codex ID}_
**Input:** _{PRD codex ID}_

---

## Core Architectural Decisions

| Priority | Decision | Choice | Rationale |
|----------|----------|--------|-----------|
| Critical | _{decision}_ | _{choice}_ | _{why}_ |
| Important | _{decision}_ | _{choice}_ | _{why}_ |
| Deferred | _{decision}_ | _{post-MVP}_ | _{why deferred}_ |

---

## Data Architecture

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | _{choice}_ | _{why}_ |
| ORM / query layer | _{choice}_ | _{why}_ |
| Migration approach | _{choice}_ | _{why}_ |
| Data validation | _{choice}_ | _{why}_ |

---

## API & Communication

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API style | _{choice}_ | _{why}_ |
| Error response format | _{choice}_ | _{why}_ |
| Versioning strategy | _{choice}_ | _{why}_ |

---

## Implementation Patterns

### Naming Conventions

**Database:** _{convention}_
**API / CLI:** _{convention}_
**Code:** _{convention}_

### Error Handling

_{How errors are caught, formatted, and surfaced to users._

### Output Formats

**Success:**
```
{example output}
```

**Error:**
```
{example error output}
```

---

## Project Structure

```
{project-root}/
  {path/to/new-file.ext}         # Purpose
  {path/to/modified-file.ext}    # What changes
  tests/
    e2e/
      {test_feature.ext}         # E2E test suite
    unit/
      {test_component.ext}       # Unit tests
```

---

## Test Strategy

### E2E Coverage

_Each E2E scenario must reference the relevant workflow document by codex ID (`lore codex search workflow` to find it)._

| Workflow (from PRD) | Workflow codex ID | Test scenario | Priority |
|---------------------|------------------|---------------|----------|
| _{Workflow name}_ | `lore codex show {conceptual-workflows-id}` | _{What the E2E test will verify}_ | _{High/Medium}_ |

### Unit Coverage

_Each unit scenario must reference the relevant workflow document by codex ID (`lore codex search workflow` to find it)._

| Component | Workflow codex ID | Scenarios to cover |
|-----------|------------------|---------------------|
| _{module/function}_ | `lore codex show {conceptual-workflows-id}` | _{list of cases}_ |

### Test Conventions

_{Test file naming, directory conventions, fixture strategy, assertion style._

---

## Crazy Tech Spec Findings

_Record which ideas from the Crazy Tech Spec were adopted, rejected, or deferred._

| Idea | Decision | Rationale |
|------|----------|-----------|
| _{Idea A}_ | _{Adopted / Rejected / Deferred}_ | _{why}_ |
| _{Idea B}_ | _{Adopted / Rejected / Deferred}_ | _{why}_ |

---

## Migration & Rollback

_{What changes to existing data or APIs this introduces, and how to roll back if needed._

---

## Change Log

| Version | Change | Reason |
|---------|--------|--------|
| 1.0 | Initial Tech Spec | _{Summarise key decisions made from draft feedback}_ |
