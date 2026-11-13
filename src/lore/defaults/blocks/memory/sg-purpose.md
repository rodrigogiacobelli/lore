---
id: sg-purpose
feature: memory
commands: [init]
mentions: [store-memory]
---
# Sync Codex Guide

When the `lore` package is upgraded, new releases add codex mechanics: new frontmatter fields, new layers, new content
classes, new rules. **`.lore/codex/codex.md`**, the project-wide codex guide, is heavily customized per project but large
parts of it describe how the codex is structured, and `lore init` never overwrites it, so it falls behind the installed
package. This skill closes that gap.

- **The agent instruction file is not this skill's job.** `lore init` rewrites the block it owns in `CLAUDE.md`,
  `AGENTS.md` and their siblings on every run, between a `lore:begin` and a `lore:end` comment marker.
- **This skill does not edit codex content.** To add or change a fact, use `store-memory`. This one syncs the generic
  scaffolding after a version bump and nothing else.
- **This skill does not upgrade the `lore` package.** The user does that first. If there is nothing to merge, the likely
  cause is that `lore` was never upgraded; say so.
