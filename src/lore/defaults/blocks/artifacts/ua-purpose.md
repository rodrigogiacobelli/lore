---
id: ua-purpose
feature: artifacts
---
# Update Artifact

Author a Lore artifact. This skill **creates an artifact or edits an existing one**, whichever the request calls for: "add
a step to the PR review checklist" and "I need an incident report template" both land here.

Artifacts are reusable template files stored in `.lore/artifacts/` and accessed by stable id. They are reference material
(templates, checklists, policy documents) that agents pull into context by id.

## Creating or editing

- **Editing**: the artifact exists. Read it in full first, and keep the `id` stable. Agents and doctrines reference an
  artifact by id; renaming one silently breaks every mission note that names it.
- **Creating**: nothing covers this material yet. Run the whole flow below.
