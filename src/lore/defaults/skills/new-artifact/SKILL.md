---
name: new-artifact
description: Draft and create a new artifact file in `.lore/artifacts/`
---

# New Artifact

Create a new Lore artifact. Artifacts are reusable template files stored in `.lore/artifacts/` and accessed by stable ID. They are reference material — templates, checklists, policy documents — that agents retrieve with `lore artifact show <id>`. Create them with `lore artifact new <id> -f <file>` (or edit/delete with the sibling subcommands).

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
- If the artifact is a codex-doc skeleton (template for a doc that will govern specific code files), include a commented `# binds: []` placeholder in the frontmatter so authors fill it in — see the impacts engine section of `.lore/codex/codex.md`

### 4. Create the artifact

Use the CLI (preferred — validates frontmatter and lands the file under `.lore/artifacts/`):

```
lore artifact new <slug> -f draft.md
```

To nest under a subdirectory (e.g. `.lore/artifacts/security/`), pass `--group`:

```
lore artifact new audit-checklist --group security -f draft.md
```

### 5. Verify

```
lore artifact list
lore artifact show <id>
```

Confirm the artifact appears and its content is correct.
