---
id: example-workflow-{workflow-name-user-facing}
title: '{Workflow Name — User Facing}'
summary: _One to three sentences. Who performs this workflow, what is their goal,
  and what is the key decision point or outcome?_
---

# {Workflow Name — User Facing}

_User-facing workflows describe what a person does to accomplish a goal — not what the system does internally. Steps are commands or UI actions. The `persona` frontmatter field identifies the role._

## Prerequisites

- _{Prerequisite 1 — e.g. tool is installed, dependency record exists}_
- _{Prerequisite 2}_

## Steps

### 1. {First action}

_Describe what the user does and why. Include the command or UI interaction._

```
$ {command} {arguments}
{expected output}
```

> **Decision point — {choice}?** _Explain the fork and when each path applies. Example: assign now vs assign later._

### 2. {Second action}

_Continue the step-by-step narrative._

```
$ {command}
{output}
```

### 3. Verify the result

_How does the user confirm the operation succeeded?_

```
$ {verification command}
{expected output showing success}
```

If the result is not as expected:
- _{Troubleshooting step 1}_
- _{Troubleshooting step 2}_

---

## Decision Points

**{Decision 1}?** _When to take each path. What are the trade-offs._

**{Decision 2}?** _When to take each path._

## Out of Scope

- _{Feature or scenario this workflow does not cover. Link to the workflow that does._}
