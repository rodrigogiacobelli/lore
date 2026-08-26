---
name: sync-codex-guide
description: Reconcile this project's customized .lore/codex/codex.md against the freshly seeded template after a lore upgrade
---

# Sync Codex Guide

When the `lore` package is upgraded, new releases add codex mechanics — new
frontmatter fields, new layers, new content classes, new rules. One project file
carries generic "how the codex works" guidance and silently drifts out of date
when that happens:

**`.lore/codex/codex.md`** — the project-wide codex guide. Heavily customized
per project, but large parts of it describe how Lore and the codex work.

`lore init` refreshes the *seed* copy on every run and never overwrites the
project's customized version, so the project's guide falls behind the installed
package. When a release added the `binds:` field, projects whose `codex.md`
predated it had no mention of `binds` — or worse, stale wording that contradicted
the new seed.

This skill closes that gap.

**The agent instruction file is not this skill's job.** `CLAUDE.md`, `AGENTS.md`
and their siblings carry Lore's guidance inside `<!-- lore:begin -->` …
`<!-- lore:end -->` markers, and `lore init` rewrites that block itself on every
run, from the same rendered text it writes to `.lore/LORE-AGENT.md`. Nothing
outside the markers is touched, so there is nothing to reconcile. Re-run
`lore init` and the block is current.

**This skill does not edit codex content.** To add or change a fact, use
`store-memory`. This one syncs the generic scaffolding after a version bump and
nothing else.

**This skill does not upgrade the `lore` package.** The user does that
themselves before invoking it. If the skill finds nothing to merge, the most
likely cause is that `lore` was never actually upgraded — say so.

## How it works

`lore init` overwrites Lore-owned seed files and leaves user-tracked files
alone. The skill exploits exactly that asymmetry:

| File | What `lore init` does | Role here |
|------|-----------------------|-----------|
| `.lore/artifacts/default/codex/codex.md` | Overwritten from the installed package | **Fresh seed** — the target |
| `.lore/codex/codex.md` | Never touched once it exists | **Project file** — what we update |

So: run `lore init`, then compare seed against project, then merge.

## The generic-versus-project rule

Every difference between the seed and the project file falls into one of two
buckets, and this rule decides which:

- **Generic** — describes how *Lore or the codex* works: a command, a
  frontmatter field, a layer definition, a content-class rule, a naming
  convention. **Sync it** into the project file.
- **Project-specific** — describes *this project's* domain, examples, chosen
  layer set, or local conventions. **Leave it alone.**

When a generic section looks *deliberately* customized — a layer renamed or
removed on purpose, a rule reworded to fit the domain — do not silently revert
it. Flag the conflict and let the user rule.

## Steps

### 1. Confirm the precondition

```
lore --version
```

Confirm with the user that they upgraded `lore` before invoking this skill. If
they did not, stop — there will be nothing to merge.

### 2. Refresh the seed

```
lore init --yes
```

Idempotent and safe. `--yes` accepts the resolved answer for every question, so
the run stays unattended even from a terminal.

It overwrites only Lore-owned files. The default trees —
`.lore/artifacts/default/`, `doctrines/default/`, `knights/default/`,
`watchers/default/` — are replaced in place, and `.lore/LORE-AGENT.md` is
re-rendered. Installed skills go through reconciliation instead: one you have
edited is reported and left alone unless you pass `--on-conflict overwrite`. It
never touches `.lore/codex/codex.md` or `.lore/codex/glossary.yaml`, it rewrites
only the leading comment block of `.lore/config.toml` and leaves every settings
line as you set it, and it replaces only the marked block inside an agent
instruction file.

### 3. Reconcile `.lore/codex/codex.md`

Compare the fresh seed against the project file:

- Seed: the `example-codex` artifact
- Project: `.lore/codex/codex.md`

A raw `diff` locates the changed regions but is noisy against a customized
file — reconcile **semantically**, section by section. Read both files in full,
then apply the generic-versus-project rule to every difference:

- New layer definitions, content-class rules, frontmatter fields, command
  descriptions, naming conventions → **adopt**.
- This project's layer set, examples, taxonomy tweaks, local rules → **keep**.

Never copy the `id:` frontmatter line. The seed carries `id: example-codex`; the
project file carries `id: codex`. Leave the project's id as it is.

Read the seed through the CLI in every access mode — the access mode covers the
codex, the rites and the glossary, and the seed is an **artifact**, whose id is
the only stable handle on a file whose path may move:

```
lore artifact show example-codex
```

<!-- lore:access cli -->
Read the project file, and apply the merged body, through the CLI — it
normalises frontmatter and runs schema validation, including any project
overlay:

```
lore codex show codex
lore codex edit codex -f <merged-body>.md
```
<!-- lore:access end -->
<!-- lore:access native -->
Read `.lore/codex/codex.md` directly with your own file tool and write the
merged body back to it yourself.

Two things the CLI would have done that you now own: frontmatter normalisation,
and validation against the merged schema, including any
`.lore/custom-schemas/` overlay this project declares. `lore health` in step 4
is what catches both — do not skip it.
<!-- lore:access end -->

Merged prose obeys the project's voice rules. Read them before writing:

```
lore artifact show codex-voice
```

Merging a version bump is where changelog narration leaks in. Carry the *fact*
into the project file, never the delta: write "`binds:` maps a document to the
code files it governs", not "this release added `binds:`".

If `.lore/codex/codex.md` does not exist, `lore init` already seeded a fresh
one — there is nothing to reconcile.

### 4. Present the merge plan and confirm

Before writing anything, show the user a concise plan: which sections change,
what is being added, and anything flagged as a possible deliberate-customization
conflict. Get explicit confirmation, then apply the edits section by section.

### 5. Verify

```
lore health
lore health --scope voice
```

Both must exit 0. `lore health` is the validator every access mode leans on, so
it stays on the CLI. Re-read the edited file to confirm it is coherent — no
duplicated sections, no orphaned headings, frontmatter intact.

The second run isolates the voice warnings on your merged prose; a full-scope
run buries them. A voice warning on `.lore/codex/codex.md` usually means a
merged sentence narrated the upgrade instead of stating the mechanic.

### 6. Report

Tell the user:

- The version, from `lore --version`.
- The sections updated and the specific mechanics adopted — name the feature,
  e.g. "added the `binds:` frontmatter field and the `lore impacts` command".
- The project-specific content deliberately preserved.
- Any conflicts flagged for the user's ruling.
- The `lore health` result.
