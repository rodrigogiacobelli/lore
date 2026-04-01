---
id: example-constraints
title: Constraints
related: []
stability: stable
summary: >
  Hard limits that must never be violated: runtime requirements, legal/compliance,
  performance budgets, compatibility rules, and explicit "never do" rules.
  Agents must check this before proposing changes that touch system boundaries.
---

# Constraints

_These are non-negotiable. Unlike design principles (which are guidelines with trade-offs), constraints are walls. Any change that would violate a constraint must be rejected, regardless of other benefits._

## Runtime

| Constraint | Value | Notes |
|-----------|-------|-------|
| Operating systems | _e.g. Linux, macOS, Windows_ | _Any known incompatibilities_ |
| Language version | _e.g. Python ≥ 3.11_ | _Minimum version that must run_ |
| Memory | _e.g. ≤ 50 MB RSS at rest_ | _If applicable_ |
| Network | _e.g. must work fully offline_ | _If applicable_ |
| Disk | _e.g. database must not exceed 1 GB_ | _If applicable_ |

## Legal and Compliance

| Constraint | Details |
|-----------|---------|
| _e.g. GDPR_ | _What it requires in this project. Data residency, deletion rights, etc._ |
| _e.g. License compatibility_ | _Forbidden dependency licenses. e.g. GPL cannot be used in a proprietary product._ |
| _e.g. Audit logging_ | _What must be logged, retention period._ |

> Remove this section if no legal or compliance constraints apply.

## Performance

| Operation | Budget | Notes |
|-----------|--------|-------|
| _e.g. `list` with 1000 records_ | _≤ 200ms_ | _Measured on reference hardware_ |
| _e.g. Cold start_ | _≤ 500ms_ | _ |

> Remove this section if no performance budgets are defined.

## Compatibility

| Constraint | Details |
|-----------|---------|
| _e.g. Database format_ | _Must remain backward-compatible across versions. No breaking migrations._ |
| _e.g. Config file format_ | _Existing config files from v1.x must continue to work._ |
| _e.g. API stability_ | _Public API follows semver; no breaking changes in minor versions._ |

## Never Do

_An explicit list of things that must never happen in this codebase. These are the rules that get broken when there is no central place to record them._

- **Never {action}:** _Why this is forbidden. What to do instead._
- **Never {action}:** _Reason._
- **Never hardcode credentials:** _Use environment variables or a secrets manager. Configuration is in `{config-location}`._
