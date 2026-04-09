---
name: new-knight
description: Draft and create a new knight persona via `lore knight new`
---

# New Knight

Create a new Lore knight. Knights are reusable markdown files that tell a worker agent **who they are and how they work** — their behavioral DNA, domain expertise, and hard constraints. They encode the *how*; mission notes encode the *what*.

A knight must be generic enough to be assigned to any mission by an orchestrator, including ad-hoc quests. Never tie a knight to a specific doctrine or mission sequence.

## Steps

### 1. Understand the knight

Ask the user (or read from context):
- What role does this knight play? (e.g. "a security auditor", "a database migration specialist")
- How do they approach their work? What is their methodology?
- What hard constraints apply — things that are always true regardless of the mission?
- What should they never do?

### 2. Check existing knights

```
lore knight list
```

Look at a similar knight for reference:

```
lore knight show <similar-knight>
```

### 3. Draft the knight content

A knight file is markdown injected directly into the worker agent's context. Write it in second person — the agent reads this as their own identity.

Structure:
```markdown
---
id: <slug>
title: <Title>
summary: <One sentence: role and primary contribution.>
---
# <Title>

<One paragraph: who you are and your primary goal.>

## How You Work

<Behavioral approach. This is the core of the knight — how they think, what they
prioritize, what methodology they follow, what tools they use and how. Include
domain expertise and decision-making principles. Write as if teaching someone
how to inhabit this role, not what to do on a specific task.>

## Rules

- <Hard constraint always true for this role — not task-specific>
- <What they must never do>
- <Quality bars they always maintain>
```

What belongs in the knight vs the mission notes:
- **Knight**: "I always read the PRD before designing" (always true for an Architect)
- **Mission**: "Read the PRD at codex ID X" (specific to this task)
- **Knight**: "No production code — ever" (always true for TDD Red)
- **Mission**: "The failing tests are in tests/feature-x.py" (specific to this task)

If you are unsure whether something belongs in the knight or the mission — ask: is this always true for this role, regardless of which task they are assigned? If yes, it belongs in the knight.

### 4. Write to a temp file and create

Write the content to a temporary file, then:

```
lore knight new <name> -f <temp-file>
```

The name should be a short slug (e.g. `security-auditor`, `db-migrator`).

### 5. Verify

```
lore knight show <name>
```
