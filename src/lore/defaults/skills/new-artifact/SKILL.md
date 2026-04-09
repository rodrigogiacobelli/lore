---
name: new-artifact
description: Draft and create a new artifact file in `.lore/artifacts/`
---

# New Artifact

Create a new Lore artifact. Artifacts are reusable, read-only template files stored in `.lore/artifacts/` and accessed by stable ID. They are reference material — templates, checklists, policy documents — that agents retrieve with `lore artifact show <id>`. There is no `artifact new` CLI command; artifacts are created directly on disk.

## Steps

### 1. Understand the artifact

Ask the user (or read from context):
- What is this artifact for? (e.g. "a PR review checklist", "an incident report template")
- Who retrieves it and when?

### 2. Check existing artifacts

```
lore artifact list
```

Look at a similar artifact for reference:

```
lore artifact show <similar-artifact-id>
```

### 3. Draft the artifact

Artifacts are markdown files with YAML frontmatter. The `id` field is the stable identifier used in `lore artifact show <id>`.

```markdown
---
id: <slug>
title: <Human Readable Title>
summary: >
  One to two sentences. What this artifact is and when to use it.
---

# <Title>

<Content here. Write for an AI agent reader — be specific and actionable.>
```

Rules:
- `id` must be unique across all artifacts — check `lore artifact list` first
- `id` should be a stable slug that won't need to change (e.g. `pr-review-checklist`, not `checklist-v2`)
- Keep content focused — agents load this in full, so every line costs context

### 4. Write to `.lore/artifacts/`

Write the file directly:

```
.lore/artifacts/<slug>.md
```

You may create subdirectories for organisation (e.g. `.lore/artifacts/security/audit-checklist.md`).

### 5. Verify

```
lore artifact list
lore artifact show <id>
```

Confirm the artifact appears and its content is correct.
