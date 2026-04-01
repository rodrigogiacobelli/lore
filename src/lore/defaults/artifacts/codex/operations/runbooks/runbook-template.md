---
id: example-ops-runbook-{name}
title: "Runbook — {Operation Name}"
related: []
stability: stable
summary: >
  Step-by-step procedure for {operation}. When to run it, prerequisites,
  exact commands, checkpoints, and rollback steps.
---

# Runbook — {Operation Name}

## When to Run This

_Describe the trigger: what situation or event requires this runbook to be executed?_

> Example: Run this when a database migration fails mid-deployment. Run this when a release is yanked and users need to be directed to the previous version.

## Prerequisites

- _Who can run this? What role or permissions are required?_
- _What must be true before starting? (e.g. "staging has been verified", "team has been notified")_
- _What credentials or access are needed?_

## Steps

### 1. {Step name}

_Description. What are you doing and why._

```bash
{command}
```

**Checkpoint:** _How do you know this step succeeded? What to check._

---

### 2. {Step name}

_Description._

```bash
{command}
```

**Checkpoint:** _Verification._

---

### 3. Verify the result

_How do you confirm the operation completed successfully?_

```bash
{verification command}
{expected output}
```

## Rollback

_If something goes wrong, how do you undo this operation?_

```bash
{rollback command or procedure}
```

_State whether rollback is always possible, and any data loss implications._

## Known Failure Modes

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| _Error message or behaviour_ | _Cause_ | _Resolution_ |
| _Error message or behaviour_ | _Cause_ | _Resolution_ |
