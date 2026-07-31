---
name: lore-update
description: After the lore package is upgraded, reconcile this project's customized .lore/codex/codex.md and agent instruction file (CLAUDE.md / AGENTS.md / ...) against the freshly seeded templates — merge in new mechanics (new frontmatter fields, commands, layers) without clobbering project-specific customization.
---

# Lore Update

When the `lore` package is upgraded, new releases add mechanics — new codex frontmatter fields, new commands, new layers, new rules. Two project files carry generic "how Lore works" guidance that silently drifts out of date when this happens:

- **`.lore/codex/codex.md`** — the project-wide codex guide. Heavily customized per project, but large parts describe how Lore and the codex work (layers, content classes, frontmatter fields, commands).
- **The agent instruction file** (`CLAUDE.md`, `AGENTS.md`, ...) — carries Lore usage guidance derived from `.lore/LORE-AGENT.md`.

`lore init` refreshes the *seed* copies of both on every run but **never** overwrites the project's customized versions. The result: the project's files fall behind the installed package. When v0.6 added the `binds:` field, projects whose codex.md predated it had no mention of `binds` — or worse, stale wording that conflicted with the new seed.

This skill closes that gap. It reconciles the two project files against the fresh seeds, adopting new generic mechanics while preserving every project-specific customization.

This is **not** the skill for editing codex content — to add or change a fact in the codex, use `update-codex`. This skill only syncs the generic Lore/codex scaffolding after a version bump.

**This skill does not upgrade the `lore` package.** The user does that themselves (`pip install -U`, `uv`, etc.) before invoking this skill. If the skill finds nothing to merge, the most likely cause is that `lore` was not actually upgraded — say so.

## How it works

`lore init` overwrites Lore-owned seed files but leaves user-tracked files untouched. The skill exploits this:

| File | What `lore init` does | Role here |
|------|-----------------------|-----------|
| `.lore/artifacts/default/codex/codex.md` | Overwritten from the installed package | **Fresh seed** — the target |
| `.lore/codex/codex.md` | Never touched once it exists | **Project file** — what we update |
| `.lore/LORE-AGENT.md` | Overwritten from the installed package | **Fresh seed** — the target |
| `CLAUDE.md` / `AGENTS.md` / ... | Not managed by Lore at all | **Project file** — what we update |

So: run `lore init`, then diff seed-vs-project, then merge.

## The generic-vs-project rule

Every difference between a seed and a project file falls into one of two buckets. This rule decides which:

- **Generic** — describes how *Lore or the codex* works: a command, a frontmatter field, a layer definition, a content-class rule, a naming convention. **Sync it** into the project file.
- **Project-specific** — describes *this project's* domain, examples, chosen layer set, or local conventions. **Keep it untouched.**

When a generic section appears to have been *deliberately* customized by the project (a layer renamed or removed on purpose, a rule reworded to fit the domain), do not silently revert it — **flag the conflict to the user** and let them rule.

## Steps

### 1. Confirm the precondition

Record the installed version:

```
lore --version
```

Confirm with the user that they upgraded `lore` before invoking this skill. If they did not, stop — there will be nothing to merge.

### 2. Refresh the seeds

```
lore init
```

Idempotent and safe: it overwrites only Lore-owned seed files (`.lore/artifacts/default/...`, `.lore/LORE-AGENT.md`, default doctrines/knights/skills/watchers). It never touches `.lore/codex/codex.md`, `.lore/codex/glossary.yaml`, `.lore/config.toml`, or the agent instruction file.

### 3. Part 1 — reconcile `.lore/codex/codex.md`

Compare the fresh seed against the project file:

- Seed: `.lore/artifacts/default/codex/codex.md`
- Project: `.lore/codex/codex.md`

A raw `diff` locates changed regions but is noisy against a customized file — reconcile **semantically**, section by section. Read both files in full, then for each difference apply the generic-vs-project rule:

- New layer definitions, content-class rules, frontmatter fields (e.g. `binds:`), command descriptions (e.g. `lore impacts`), naming conventions → **adopt**.
- This project's layer set, examples, taxonomy tweaks, project rules → **keep**.

Never copy the `id:` frontmatter line — the seed carries `id: example-codex`, the project file carries `id: codex`. Leave the project's `id` as-is.

Merged prose obeys `lore artifact show codex-voice` — read it before writing. Merging a version bump is where changelog narration leaks in: carry the *fact* into the project file, never the delta. Write "`binds:` maps a doc to the code files it governs", not "this release added `binds:`".

If `.lore/codex/codex.md` does not exist, `lore init` already seeded a fresh one — nothing to reconcile.

### 4. Part 2 — reconcile the agent instruction file

Identify the file. **You are an AI agent running this skill — you know your own provider.** Map it:

| Provider | File |
|----------|------|
| Claude Code | `CLAUDE.md` |
| OpenAI Codex | `AGENTS.md` |
| Gemini CLI | `GEMINI.md` |
| Cursor | `.cursor/rules/` or `.cursorrules` |
| GitHub Copilot | `.github/copilot-instructions.md` |
| Other | whatever file your framework reads at the project root |

If your provider's file does not exist, check which instruction file *does* exist at the root and confirm with the user. If none exists, the project skipped GETTING-STARTED Step 1 — offer to create it from `.lore/LORE-AGENT.md`.

Compare the fresh seed against the project file:

- Seed: `.lore/LORE-AGENT.md`
- Project: the file identified above

The agent file mixes project-specific content (personas, project workflows, other tooling) with Lore-derived sections that originate from `.lore/LORE-AGENT.md` — the `lore --help` block, the Roles section, the "Knowing the project" primitives, the Available skills table. Apply the generic-vs-project rule: update the Lore-derived sections to match the new seed; leave everything else untouched. The Available skills table is a frequent drift point — new releases ship new skills.

### 5. Present the merge plan and confirm

Before writing anything, show the user a concise plan: for each file, which sections will change, what is being added, and anything flagged as a possible deliberate-customization conflict. Get explicit confirmation, then apply the edits section by section.

### 6. Verify

```
lore health
lore health --scope voice
```

Must exit 0. Re-read both edited files to confirm they are coherent — no duplicated sections, no orphaned headings, frontmatter intact.

The second run isolates the voice warnings on your merged prose — they report warnings, never errors, so a full-scope run buries them. A warning on `.lore/codex/codex.md` usually means a merged sentence narrated the upgrade instead of stating the mechanic.

### 7. Report

Tell the user:

- Version delta (`lore --version`), if known.
- Per file: sections updated and the specific mechanics added — name the feature (e.g. "added the `binds:` frontmatter field and the `lore impacts` command").
- Project-specific content deliberately preserved.
- Any conflicts flagged for the user's ruling.
- `lore health` status.
