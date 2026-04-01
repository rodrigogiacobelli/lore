---
name: new-doctrine
description: Draft and create a new doctrine via `lore doctrine new`
---

# New Doctrine

Create a new Lore doctrine. Doctrines are YAML workflow templates that describe a sequence of steps (phases, missions, knights) for a standard body of work. An orchestrator reads them and translates them into quests and missions — doctrines have no execution engine of their own.

## Steps

### 1. Understand the doctrine

Ask the user (or read from context):
- What workflow does this doctrine describe? (e.g. "a bugfix cycle", "a data migration", "an API review")
- What are the phases and their order?
- What types of agents are involved? (knight, constable, human)
- Are there any existing doctrines to use as reference?

### 2. Check existing doctrines

```
lore doctrine list
```

Look at a similar doctrine for reference if one exists:

```
lore doctrine show <similar-doctrine-id>
```

### 3. Draft the YAML

A doctrine file has this structure:

```yaml
id: <slug>
title: <Human Readable Title>
summary: <One sentence description>
name: <slug>
description: >
  Multi-line description of the workflow. Explain the phases, the flow,
  and any important sequencing constraints.

steps:
  - id: <step-slug>
    title: <Step Title>
    type: knight        # knight | constable | human
    priority: 0         # phase number
    knight: <knight-file.md>   # omit if no knight
    notes: >
      Instructions for the agent assigned to this step.
      Be specific. A worker executes this with no other context.
    needs:              # omit if no dependencies
      - <other-step-id>
```

Rules:
- `id` and `name` must be the same slug
- `priority` maps to phase — steps in the same phase have the same priority and can run in parallel
- `needs` creates a dependency — this step cannot start until the listed steps are done
- `constable` steps are orchestrator chores (commits, housekeeping) — no knight needed
- `human` steps require user action — the orchestrator does not claim them

### 4. Write to a temp file and create

Write the YAML to a temporary file, then:

```
lore doctrine new <name> -f <temp-file>
```

### 5. Verify

```
lore doctrine show <name>
```

Check that it validates correctly. If there are errors, fix and re-run `lore doctrine edit <name>`.
