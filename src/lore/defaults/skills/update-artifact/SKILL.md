---
name: update-artifact
description: Create or edit an artifact — a reusable template, checklist or policy file
---

# Update Artifact

Author a Lore artifact. This skill **creates an artifact or edits an existing one**, whichever the request calls for — "add a step to the PR review checklist" and "I need an incident report template" both land here.

Artifacts are reusable template files stored in `.lore/artifacts/` and accessed by stable ID. They are reference material — templates, checklists, policy documents — that agents retrieve with `lore artifact show <id>`.

## Creating or editing

- **Editing** — the artifact exists. Read it in full first (`lore artifact show <id>`), and keep the `id` stable. Agents and doctrines reference an artifact by id; renaming one silently breaks every mission note that names it.
- **Creating** — nothing covers this material yet. Run the whole flow below.

## Is it an artifact at all?

An artifact is material an agent *pulls into context to follow*: a template to fill in, a checklist to run, a gate to pass. A fact about how the system works is a codex document, and a step-by-step procedure for a recurring task is a rite — both belong to `store-memory`, not here. Check before you write:

<!-- lore:access cli -->
```
lore codex search <keyword>
lore rite search <keyword>
```
<!-- lore:access end -->
<!-- lore:access native -->
Grep `.lore/codex/**/*.md` and `.lore/rites/**/*.yaml` for the keyword and read the candidates directly. Glossary terms are not attached to what you read — look up an unfamiliar one in `.lore/codex/glossary.yaml`.
<!-- lore:access end -->

Artifacts themselves are reached through the Lore CLI in every access mode: the artifact tree hides a `default/` versus flat split, slash-derived groups and `.deleted` soft-delete naming, and the id is the only stable handle on a file whose path may move.

## Steps

### 1. Understand the artifact

Ask the user (or read from context):
- What is this artifact for? (e.g. "a PR review checklist", "an incident report template")
- Who retrieves it and when?

### 2. Check existing artifacts

```
lore artifact list
lore artifact show <similar-or-target-artifact-id>
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

### 4. Create or edit the artifact

The CLI validates frontmatter and lands the file under `.lore/artifacts/`:

```
lore artifact new <slug> -f draft.md      # new artifact
lore artifact edit <slug> -f draft.md     # replace an existing one
```

To nest under a subdirectory (e.g. `.lore/artifacts/security/`), pass `--group` on `new`:

```
lore artifact new audit-checklist --group security -f draft.md
```

To retire an artifact, `lore artifact delete <slug>` — a soft delete, so the file is renamed rather than destroyed. Check `lore doctrine list` first for a doctrine whose mission notes still name the id.

### 5. Verify

```
lore artifact list
lore artifact show <id>
```

Confirm the artifact appears and its content is correct.
