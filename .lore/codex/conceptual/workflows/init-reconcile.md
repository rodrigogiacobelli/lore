---
id: conceptual-workflows-init-reconcile
title: Init Reconciliation
summary: How `lore init` reconciles what it installed against what the current release
  ships and against the bytes on disk — the five outcomes (create, overwrite, section,
  remove, conflict), the ruling that Lore owns the files it installs and replaces or
  removes an edited one without asking, the retirement reasons quoted for a removed
  skill, the fallback for a project with no install manifest, and the guarantee that a
  file Lore never installed is never touched.
binds:
- src/lore/reconcile.py
- tests/e2e/test_init_reconcile.py
- tests/unit/test_reconcile.py
related:
- conceptual-workflows-lore-init
- conceptual-workflows-init-interactive
- conceptual-workflows-health
- conceptual-entities-skill
- tech-arch-install-manifest
- tech-arch-skill-catalogue
- tech-arch-agents-md
- decisions-003-soft-delete-semantics
---

# Init Reconciliation

Every `lore init` after the first is an upgrade. The release now installed ships a different set of files from the one that installed the project: skills get renamed, several merge into one, some retire. Reconciliation is how `lore init` works out what to do about each of them.

It compares three things:

| | |
|---|---|
| **Desired** | Every file the installed Lore release would write, given the project's answers. |
| **Recorded** | Every file Lore wrote last time, with the hash it wrote, read from the install manifest. |
| **On disk** | The bytes actually at each of those paths now. |

There is no per-version migration chain. One comparison is correct for any version hop, including skipped releases and a downgrade, because it asks what is true rather than what changed.

## The Outcomes

Every path that appears in either desired or recorded gets exactly one outcome.

| Outcome | When | Reported |
|---|---|---|
| **Create** | Desired, and either absent from disk or already byte-identical to what Lore would write. | Only when the file is actually absent. |
| **Overwrite** | Lore installed it, its bytes still match what Lore wrote, and the release now ships different content. | Yes. |
| **Section** | A marked block inside a file the project owns — an agent instruction file. Only the block is written. The retired root `.gitignore` block is the other kind: recorded by an older release, never written by this one, and removed on the next run. | Yes. |
| **Remove** | Lore installed it and the release no longer ships it. | Yes, with the reason. |
| **Conflict** | The path is desired, and holds a file Lore never installed — or holds something Lore may not touch at all. | Always. |

A path in neither desired nor recorded is never read, never written and never deleted. That is the safety property the whole mechanism exists to hold: `lore init` cannot touch a file the project authored, because it has no record of installing it and no intention of writing it.

The one place Lore reads a file it did not install is a path it is about to write. Hashing it first is exactly what turns a silent overwrite into a reported conflict.

## Lore Owns the Files It Installs

Inside those two sets the rule is the opposite one, and it is a product decision rather than an inference. **A file Lore installed is Lore's, whatever has been done to it since.** If this release still ships it, it is rewritten. If this release has retired it, it is removed and the successor is named. Neither asks.

This is what the seeded trees have always done — `.lore/knights/default/`, `.lore/doctrines/default/`, `.lore/artifacts/default/` and `.lore/watchers/default/` are overwritten in place on every run — and skills were the one tree that behaved differently, keeping an edited file and asking about it. They no longer do. It is **intended behaviour**, not an oversight.

The row that destroys something says so, and for a skill it says where a copy of their own would have survived:

```
Overwrite .claude/skills/inquest/SKILL.md    your edit is discarded — Lore owns this
                                             skill; put your own in .claude/skills/<your-own-id>/
Removed   .claude/skills/new-rite/SKILL.md — merged into store-memory; your edit is discarded
```

Knights, doctrines, artifacts and watchers say where the boundary is with a `default/` subdirectory. Skills install straight into `.claude/skills/` or `.lore/skills/` and have no such marker, so **the id is the boundary**: a directory named after a skill Lore ships belongs to Lore, and one named anything else is never read, moved or deleted by any run. To customise a shipped skill, copy its directory to an id of your own and edit the copy.

Lore does not move a person's edits into the file that replaced their skill. It names the successor and leaves the porting to them.

## Conflicts

One kind of conflict is left: **a path Lore is about to write that holds something Lore did not put there.** A hand-made `.claude/skills/.gitignore` in a directory Lore has never written into, a skill the project authored at an id Lore also ships, a `CLAUDE.md` that is a symlink.

It splits by whether there is a second answer:

- **Not installed by Lore** — the project's own file at a path Lore wants. `skip`, the default, leaves it and Lore writes nothing there; `--on-conflict overwrite` hands the path to Lore. Both answers do something, so this is the one case the run asks about at a terminal.
- **A path Lore may not touch** — a symlink, or a path resolving out of the project through a linked ancestor. Reported the same way and settled by neither answer, because performing the write *is* the escape. No prompt is offered for it.

`--on-conflict` has no say over Lore's own files. It never fires for one, and neither `skip` nor `overwrite` changes what happens to one.

## Removals

A skill Lore retires is removed, and the reason is quoted from the retirement ledger in the skill catalogue:

```
Removed .claude/skills/new-rite/SKILL.md — merged into store-memory
```

A removal is a hard unlink, not a soft delete. `decisions-003-soft-delete-semantics` governs entities the `lore` CLI manages — quests, missions, dependency rows, and the file entities with a `lore delete` path. A skill is none of those: it has no ID retrieval, no CRUD surface and no delete command. What stands in for the soft-delete guarantee is the **record**: a path is unlinked only when something says Lore installed it and this release no longer ships it. The bytes there are not part of that test, because an edited file Lore installed is Lore's too — so the record has to be one that means it, which is why the no-manifest fallback below will not guess a path Lore owns out of a directory it cannot prove Lore wrote into.

Removing a marked block is different: the block is deleted and the rest of the file is left byte-identical. An instruction file is never removed, because Lore did not write the whole of it.

After removals, `lore init` prunes directories left empty, walking upward from each removed path and stopping at the first directory that still holds something or at the skills root, whichever comes first. The skills root itself is never removed, and a directory holding anything Lore did not install survives by definition.

If an unlink fails, that path is skipped and reported as `! Kept <path> — could not remove: <reason>`, and the run continues.

## A Project With No Manifest

A project initialised before the manifest existed has no record of what Lore installed. `lore init` builds a synthetic one: it walks the pre-manifest skills roots, looks each file up against the hashes Lore has shipped for that path in any release, and treats a match as a file Lore installed and nobody edited.

A file whose path is unknown is never even read. A **known** path whose hash matches no shipped version is a file Lore installed and the project has since edited, and the walk still names it — that is what lets a pre-manifest project have an edited current skill rewritten and an edited retired one removed, instead of being told Lore had never installed a file it installed.

That claim is made about a **tree**, never about a single path. A root yielding no exact hash match at all is not a root Lore ever wrote into, so nothing in it is claimed — a project that authored its own `inquest/SKILL.md` in a directory holding nothing of Lore's keeps it, whatever the historical table happens to hold at that name (FR-28). Once a real manifest exists the fallback never runs for that project again.

### Where it looks

The roots are `.lore/skills/` plus the `skills_dir` of **every** agent in the packaged registry, whether or not that agent was selected for this run. `.lore/skills/` is where Lore wrote the files; the agent directories are where they ended up, because the pre-feature `GETTING-STARTED.md` shipped this instruction:

```
cp -r .lore/skills/. .claude/skills/
```

A project that followed the documented workflow has its skills under `.claude/skills/`, and a fallback that walked only `.lore/skills/` would leave every retired directory there — producing exactly the doubled catalogue (`new-doctrine` *and* `update-doctrine`) the consolidation exists to prevent. Every registry directory is walked rather than only the selected ones, because a project that copied into `.claude/skills/` and now initialises for Gemini still needs the stale copies gone.

### How a copy is matched

The historical table is keyed by the path Lore *installed* to, so a candidate at `<root>/<rel>` is looked up as `.lore/skills/<rel>`. The synthetic record is then written at the candidate's real path, which is what the removal targets.

Widening the walk does not widen what gets touched. The path lookup comes before the hash, so a path Lore has never shipped is never even read, and a file is only ever removed when its bytes match bytes Lore itself produced.

The bias errs toward keeping files, which is the correct direction when the evidence is incomplete.

An unreadable or unrecognised manifest is treated the same way: one warning on stderr, then the fallback, then a fresh manifest at the end of the run.

## Interruption

The manifest is written last. An interrupted run therefore leaves the previous manifest in place, and the next `lore init` finds the already-written files disagreeing with it. Every one of those paths is Lore's, so the recovering run writes what this release ships and the project lands where the interrupted run was heading — in one re-run, with the writes reported.

## Auditing Without Running Init

`lore health --scope skills` reports the same disagreements without changing anything: a file the manifest names that is missing on disk, a file edited since install, and a retired skill still present. It reports; `lore init` is what acts. `conceptual-workflows-health` holds the severities.
