---
id: fi-tech-spec-draft
title: Tech Spec Draft
group: feature-implementation
summary: >
  Template for the Architect to write the initial Tech Spec Draft from the
  final PRD and pre-architecture feedback. Covers architectural decisions,
  implementation patterns, project structure, and test strategy. The user
  appends unstructured feedback directly to this file before the Architect
  produces the final Tech Spec.
---

# {Feature Name} — Tech Spec Draft

**Author:** Architect
**Date:** {date}
**Input:** _{PRD codex ID}_

---

## Core Architectural Decisions

| Priority | Decision | Choice | Rationale |
|----------|----------|--------|-----------|
| Critical | _{e.g. Database choice}_ | _{choice}_ | _{why}_ |
| Critical | _{e.g. Auth strategy}_ | _{choice}_ | _{why}_ |
| Important | _{e.g. API style}_ | _{choice}_ | _{why}_ |
| Deferred | _{e.g. Caching layer}_ | _{post-MVP}_ | _{why deferred}_ |

---

## Data Architecture

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | _{e.g. SQLite / PostgreSQL}_ | _{why}_ |
| ORM / query layer | _{e.g. raw SQL / SQLAlchemy}_ | _{why}_ |
| Migration approach | _{e.g. Alembic / manual}_ | _{why}_ |
| Data validation | _{e.g. Pydantic / Zod}_ | _{why}_ |

---

## API & Communication

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API style | _{e.g. REST / GraphQL / CLI}_ | _{why}_ |
| Error response format | _{e.g. RFC 7807 / custom JSON}_ | _{why}_ |
| Versioning strategy | _{e.g. URL prefix / none}_ | _{why}_ |

---

## Implementation Patterns

_These rules prevent divergence between agents. Every section is a contract._

### Naming Conventions

**Database:** _{e.g. snake_case plural tables}_
**API / CLI:** _{e.g. hyphenated flags, plural noun endpoints}_
**Code:** _{e.g. snake_case files, PascalCase classes}_

### Error Handling

_{How errors are caught, formatted, and surfaced to users._

### Output Formats

**Success (example):**
```
{example output}
```

**Error (example):**
```
{example error output}
```

---

## Project Structure

_File-level layout for every file that will be added or modified._

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

_Which user workflows from the PRD must have E2E test coverage. No workflow is optional._
_Each E2E scenario must reference the relevant workflow document by codex ID (`lore codex search workflow` to find it)._

| Workflow (from PRD) | Workflow codex ID | Test scenario | Priority |
|---------------------|------------------|---------------|----------|
| _{Workflow name}_ | `lore codex show {conceptual-workflows-id}` | _{What the E2E test will verify}_ | _{High/Medium}_ |

### Unit Coverage

_Which components and edge cases require unit tests._
_Each unit scenario must reference the relevant workflow document by codex ID (`lore codex search workflow` to find it)._

| Component | Workflow codex ID | Scenarios to cover |
|-----------|------------------|---------------------|
| _{module/function}_ | `lore codex show {conceptual-workflows-id}` | _{list of cases}_ |

### Test Conventions

_{Test file naming, directory conventions, fixture strategy, assertion style._

---

## Migration & Rollback

_{What changes to existing data or APIs this introduces, and how to roll back if needed._

---

## Open Questions

| # | Question | Owner | Priority |
|---|----------|-------|----------|
| 1 | _{Question}_ | _{Architect / User}_ | _{High / Medium}_ |
