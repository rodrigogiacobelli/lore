---
name: new-knight
description: Draft and create a new knight persona via `lore knight new`
---

# New Knight

Create a new Lore knight. Knights are reusable markdown files that tell a worker agent how to approach work — their style, constraints, authority, and perspective. They encode the *how*; mission descriptions encode the *what*.

## Steps

### 1. Understand the knight

Ask the user (or read from context):
- What role does this knight play? (e.g. "a security auditor", "a database migration specialist")
- What is their primary goal and approach?
- What constraints or boundaries apply to them?
- What should they never do?

### 2. Check existing knights

```
lore knight list
```

Look at a similar knight for reference if one exists:

```
lore knight show <similar-knight>
```

### 3. Draft the knight content

A knight file is markdown. Write it from the knight's perspective — this text is injected directly into the worker agent's context. Keep it focused and actionable.

Structure to follow:

```markdown
# <Role Title>

<One sentence: who you are and your primary goal.>

## Your Approach

<How you think and work. 3–5 bullet points.>

## Constraints

<What you must never do or change. Be explicit.>

## Authority

<What you own and can decide without asking. What requires user confirmation.>
```

Keep it under 30 lines. Workers read this on every mission — every word costs context.

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
