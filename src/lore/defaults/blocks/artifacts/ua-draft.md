---
id: ua-draft
feature: artifacts
---
### 3. Draft the artifact

Artifacts are markdown files with YAML frontmatter. The `id` field is the stable identifier.

```markdown
---
id: <slug>
title: <Human Readable Title>
summary: >
  One to two sentences. What this artifact is and when to use it.
---

# <Title>

<Content here. Write for an AI agent reader: be specific and actionable.>
```

Rules:

- `id` must be unique across all artifacts: check the existing ones first.
- `id` should be a stable slug that won't need to change (`pr-review-checklist`, not `checklist-v2`).
- Keep content focused: agents load this in full, so every line costs context.
- If the artifact is a codex-doc skeleton (template for a doc that will govern specific code files), include a commented
  `# binds: []` placeholder in the frontmatter so authors fill it in.
