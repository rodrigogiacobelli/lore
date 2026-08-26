---
name: update-knight
description: Create or edit a knight persona — its behaviour, expertise and hard rules
---

# Update Knight

Author a Lore knight. This skill **creates a knight or edits an existing one**, whichever the request calls for — "give the tech-writer knight a rule about voice" and "I need a security-auditor persona" both land here.

Knights are reusable markdown files that tell a worker agent **who they are and how they work** — their behavioral DNA, domain expertise, and hard constraints. They encode the *how*; mission notes encode the *what*.

## Creating or editing

- **Editing** — the knight exists. Read it in full first (`lore knight show <name>`), change only what the request names, and leave the rest of the persona alone. A knight is injected verbatim into a worker's context, so an unrelated rewrite changes behaviour nobody asked to change.
- **Creating** — no knight covers this role. Run the whole flow below.

Knights are reached through the Lore CLI in every access mode: the knight tree hides a `default/` versus flat split, slash-derived groups and `.deleted` soft-delete naming, and `lore show <mission-id>` splices a knight's contents into the mission it is attached to.

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
lore knight show <similar-or-target-knight>
```

Read the standards this role has to honour, so the knight's Rules section repeats none of them wrongly:

<!-- lore:access cli -->
```
lore codex list --filter standards
lore codex show <standards-id> <decision-id>
```
<!-- lore:access end -->
<!-- lore:access native -->
Read the standards and decision documents under `.lore/codex/` with your own file tool, and grep the tree when you do not know the id. Glossary terms are not attached to what you read — look up an unfamiliar one in `.lore/codex/glossary.yaml`.
<!-- lore:access end -->

`lore codex map <id>` and `lore impacts <path-or-id>` stay on the CLI in every mode when you need to see what a standard reaches.

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

### 4. Write to a temp file, then create or replace

Write the content to a temporary file, then:

```
lore knight new <name> -f <temp-file>     # new knight
lore knight edit <name> -f <temp-file>    # replace an existing one
```

The name should be a short slug (e.g. `security-auditor`, `db-migrator`). To nest under a subdirectory, pass `--group <subdir>` on `new`. To retire a knight, `lore knight delete <name>` — a soft delete, so the file is renamed rather than destroyed.

### 5. Verify

```
lore knight show <name>
```
