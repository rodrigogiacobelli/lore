---
id: uc-purpose
feature: memory
---
# Update Custom Schema

Author a custom frontmatter field for a codex doc kind without hand-writing JSON-Schema: this skill **creates an overlay or
edits an existing one** ("make `owner` required", "add a `reviewed_at` field").

A **custom-schema overlay** at `.lore/custom-schemas/<kind>.yaml` adds project-specific fields on top of the packaged
schema of a codex doc kind. Overlays are **add-only**: you may add new keys (and mark them required), but never
override, redefine or drop a packaged field. The resolver merges the overlay onto the packaged base, so a doc that carries
a custom field validates the same way everywhere.
