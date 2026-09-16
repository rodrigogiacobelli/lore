---
id: tdd-feature-lite
title: TDD Feature (Lite) — Doctrine Design
summary: >
  The default path from a settled request to a shipped Lore feature. Cheap recon,
  one expensive architecture step, one decision audit, one human gate, then Opus at
  xhigh effort building each dependency-ordered module lane end to end. Nine steps
  against tdd-feature's eight-plus-sixty, one planning document instead of five, and
  three dev missions instead of forty-five. What survives the collapse is what a
  stronger model does not replace on its own — decision adherence, test-first
  discipline, and a codex that describes what shipped.
---

# TDD Feature (Lite) — Doctrine Design

## Purpose

`tdd-feature` was built when the safe assumption was that a model needed the work
cut small: a scout with two lenses, an architect, an enforcer, a planner, a
grouper, and a red/green/refactor trio plus a commit constable per group. Every
hand-off was a briefing narrow enough that the agent could not go wrong.

That decomposition is no longer free. Run end to end on a large feature it
produced 24 stories, 15 groups, and 60 missions before a line of code was
written. The user aborted at that point, correctly. The replacement — six lane
missions, each owning its full cycle — is the shape this doctrine specifies
natively.

**Kept, because the economics still hold.** Exploration is cheap and a bad
architectural decision is expensive, so recon runs on the small model and
architecture on the big one. The decision audit is kept because it earned its
place empirically: on the run above it found a real ADR-011 breach — a validation
rule living only in `cli.py` with no core-function counterpart — and a codex
document contradicting the code. A stronger architect does not find that, because
it is a fact about code the architect is not reading. Lanes are kept because they
must land in dependency order.

**Collapsed, because the model no longer needs it.** The split between the
business lens and the technical lens. The split between the PRD, the tech spec,
the stories, the index, and the groups. The split between writing a test, making
it pass, and cleaning it up. One recon map. One spec. One mission per lane.

The result is 9 steps and 1 human gate, against 8 fixed steps plus roughly 60
generated ones and 1 gate.

## The Shape

```
branch → recon → feature-spec → adr-audit → [human gate] → foundation → core → surface → scribe
          cheap    expensive      cheap        steer              Opus 5, xhigh              cheap
```

One document carries the whole plan. One gate steers it. Three lane missions build
it in dependency order. Nothing fans out and nothing needs to fan back in.

## Doctrine

| Phase | Mission | Type | Depends On | Input | Output |
|-------|---------|------|------------|-------|--------|
| 0 | branch | constable | — | quest title | `feat/<slug>` off `work` |
| 1 | recon | agent | branch | request + optional PRD | one recon map: relevant codex, binding decisions with each rule in one line, code surface, lane call, verified-vs-inferred |
| 2 | feature-spec | agent | recon | request + recon map + optional PRD | one feature spec in five parts: intent, architecture, decision impact + draft ADRs, test strategy, ordered per-lane implementation plan |
| 3 | adr-audit | agent | feature-spec | spec + every ADR and standards doc + the code the spec touches | spec rewritten to comply, pre-existing breaches listed, unrecorded decisions flagged, verdict `RECONCILED` / `BLOCKED` |
| 4 | spec-gate | human | adr-audit | reconciled spec | Pre-Dev Notes filled; every conflict resolved; every draft ADR ruled on |
| 5 | dev-foundation | agent | spec-gate | spec Parts 2–5 | leaf-module tests + code + 2 commits (or no-op) |
| 6 | dev-core | agent | dev-foundation | spec Parts 2–5 + shipped foundation | storage and business-logic tests + code + 2 commits (or no-op) |
| 7 | dev-surface | agent | dev-core | spec Parts 2–5 + shipped core signatures | `api.py` / `cli.py` / `prompts.py` tests + code + 2 commits (or no-op) |
| 8 | scribe | agent | dev-surface | the quest's real commits + the spec | codex updated, approved ADRs written, `src/lore/defaults/` reconciled, one `docs(...)` commit |

**All nine missions are created upfront.** Nothing in this doctrine is generated at
runtime. That is the point: `tdd-feature` deferred the dev cycle to an
orchestrator loop that turned 15 groups into 60 missions, and there is no such
loop here.

## Missions

- **branch** — Cuts `feat/<slug>` off `work` and publishes the slug. Orchestrator chore.
- **recon** — Reads the codex, the whole decision record, and the real source tree in one pass and produces the single map everything downstream is built on, with an explicit verified-vs-inferred split.
- **feature-spec** — Writes the one planning document, in five parts, self-contained enough that a dev lane builds from it without opening the recon map, the codex, or an ADR.
- **adr-audit** — Reconciles both the spec and the existing code it touches against every settled decision, and ends in `RECONCILED` or `BLOCKED`.
- **spec-gate** — The human resolves every conflict, rules on every draft ADR, and writes the decisions into the spec's Pre-Dev Notes. The doctrine's only steering point.
- **dev-foundation** — Builds the leaf-module lane end to end: red, green, check, commit, refactor, check, commit.
- **dev-core** — Builds the storage and business-logic lane end to end, against the foundation lane's committed signatures.
- **dev-surface** — Builds the `api.py` / `cli.py` / `prompts.py` lane end to end, against the core lane's committed signatures.
- **scribe** — Reconciles the codex, the approved ADRs, and `src/lore/defaults/` with the quest's real commits, then commits once.

Three of those briefs exist nowhere else. `recon` is a single pass whose output is
the spine of decision adherence, where `tdd-feature`'s scout is one lens per
mission with no mandate for a binding-rule table or a verified-vs-inferred split.
The dev lane brief owns red, green and refactor inside one mission, so the
guarantees the three-mission split made structural had to be written into its
rules instead. And `scribe` replaces two upstream briefs at once: `tdd-feature`'s
codex-apply is framed for plan-time work and does not touch seeds, while its
defaults-review touches only seeds — one worker reading one diff does both.

`feature-spec` and `adr-audit` carry the Architect and the ADR & Standards
Enforcer briefs, unchanged in substance from `tdd-feature`; the audit is widened
to read the code the spec touches, not only the spec.

### Phase is not priority

`lore new mission -p` accepts 0–4 only. Phases 5 through 8 clamp to priority 4 and
`needs` carries the real order — every mission in this doctrine is chained, so the
dependency graph fully determines execution and priority is nearly cosmetic.
Never pass a phase number as `-p`; it fails at mission creation.

## What Each Heavy Step Became

| tdd-feature | tdd-feature-lite |
|-------------|------------------|
| `scout` (business map + technical map) | `recon` — one map, plus the binding decision table and a verified-vs-inferred split |
| `tech-spec` (consumes a mandatory upstream PRD) | `feature-spec` Parts 1–2 — the PRD becomes an optional input, not a precondition |
| `adr-enforce` | `adr-audit` — same brief, widened to audit the existing code the spec touches, not only the spec |
| `spec-gate` | unchanged — still the only human gate, still also the pre-development pause |
| `tech-planning` (24 stories + index) | `feature-spec` Part 5 — an ordered unit list per lane, inside the spec |
| `codex-apply` (runs before development, documents the plan) | folded into `scribe`, moved after development, documents the commits |
| `group-stories` (15 groups + spec commit) | gone — Part 5 *is* the dispatch order |
| Red + Green + Refactor + Dev Commit × 15 groups | `dev-foundation` + `dev-core` + `dev-surface`, each owning its full cycle |
| `defaults-review` | folded into `scribe` — same pass, same input, same commit |

Sixty dev missions become three. Five planning documents become one.

## Model Allocation

The Lore doctrine format has no `model` field, so every agent mission file opens
with a `Dispatch:` line and this table is the reference. **Pass model and effort
explicitly on every dispatch.** Inheriting the session default runs the whole
pipeline on one tier and defeats the split in both directions — it overpays for
recon and, far worse, underpays for architecture.

| Tier | Missions | Why |
|------|----------|-----|
| **Opus 5, xhigh effort** | `feature-spec`, `dev-foundation`, `dev-core`, `dev-surface` | The architect turns something vague into something precise and is the only reasoning step in the pipeline; everything the heavy doctrine split across six documents and three review passes now rests on it. Each dev lane owns a whole lane — tests, implementation, and cleanup — with no downstream reviewer to catch it. |
| **Opus 5, medium effort** | `adr-audit` | Rule-matching against a settled ruleset. Judgment is bounded, but 21 ADRs and 6 standards documents are dense and a miss ships as a violation. |
| **Sonnet, or Opus at low effort** | `recon`, `scribe` | Search, and prose against a settled decision and a settled diff. Sonnet is the floor even here: a cheap recon that reports alignment it never verified poisons every step after it. |
| **n/a** | `branch` (constable, handled inline), `spec-gate` (human) | Not dispatched. |

**Running `feature-spec` on the session default silently converts this doctrine
into a worse version of `tdd-feature`** — same guarantees removed, none of the
capability that justified removing them. The allocation is not decoration.

## The Lanes

`tdd-feature`'s dev cycles were carved by story grouping — a runtime decision,
made by an agent, on 24 inputs. This doctrine carves them by the one structure
Lore actually has: the module dependency hierarchy that
`standards-dependency-inversion` establishes. The arrow points inward, so the
lanes are fixed, and there are exactly three.

| Lane | Owns | Why it lands where it does |
|------|------|---------------------------|
| **foundation** | `validators.py`, `paths.py`, `ids.py`, `frontmatter.py`, `initplan.py`, `graph.py`, `config.py`, `root.py`, `schemas/` and its packaged YAML | Leaf modules — zero or near-zero `lore.*` imports, and everything else imports them. A signature fixed later is every later lane rebuilt. |
| **core** | `db.py`, `models.py`, `priority.py`, `migrations/`, `doctrine.py`, `rite.py`, `watcher.py`, `artifact.py`, `codex.py`, `glossary.py`, `impacts.py`, `health.py`, `oracle.py`, `init.py`, `skills.py`, `manifest.py`, `reconcile.py`, `agents.py` | Where the behaviour lives. ADR-011 makes the CLI a thin wrapper, so whatever the surface will expose must exist here first as a callable function. |
| **surface** | `api.py`, `cli.py`, `prompts.py` | Both consumers meet the system here — humans through the CLI, Realm through `from lore.api import ...`. It codes against core functions that already exist and work, reading the shipped modules for exact signatures. |

Lore has no frontend, no deployment, and no vault, so it has no lane for them.
`src/lore/defaults/` is seeded content rather than behaviour, and belongs to the
scribe.

**Splitting a lane.** When Part 5 lists many units in one lane, the orchestrator
splits that lane into several missions against the same lane's mission file,
running sequentially, each carrying its own units on its board. The spec's
"Suggested Splits" section names the split points. This is the escape hatch that
keeps a large feature from landing in one enormous mission — and it is a mission
count that grows linearly with the work, not multiplicatively with the grouping.

**Skipping a lane.** A lane the recon map marks out of scope, or whose Part 5
section reads Skipped, marks done immediately with no commit. A pure-CLI change
and a pure-storage change flow through the same doctrine with no fork.

**Sequential, never parallel** — even where lanes are file-disjoint. Concurrent
committing agents race the git index; the failure mode is corrupted staged state,
not a merge conflict.

## Development Cycle Shape

Each dev lane mission runs the full cycle inside one mission:

```
red (tests written, run, and observed failing for the right reason)
  → green (minimum code)
  → check the binding table against the real diff
  → commit
  → refactor (behaviour unchanged)
  → check again
  → commit
```

Two commits per lane: a working checkpoint and a clean one.

The three-mission Red/Green/Refactor split existed to make the guarantees
structural — the Red worker could not write production code because it was a
different agent. Collapsing the split removes that structure, so the guarantees
are written into each dev lane mission file's rules **and repeated in each lane's
steps**:

- Tests are written and observed failing before the implementation exists.
- A test is never weakened, skipped, marked `xfail`, deleted, or mocked around to
  reach green.
- A test is never edited to accommodate production code that does not work.

Repetition here is deliberate. There is no Red mission enforcing this now, and no
reviewer downstream who would notice.

`pytest`, `ruff`, and `mypy` are clean before each of the two commits, and never
by suppression: no `# type: ignore`, no `# noqa`, no broadened `Any`, no loosened
config, no deleted assertion.

## Decision Adherence

A better model does not make this self-enforcing. On the reference run the
architect, at full effort, still produced a spec that had to be reconciled — and
the audit found a breach that had been sitting in the tree. So the chain is
carried at five points:

1. **Recon** enumerates every ADR, standards document, and contract that governs a
   file in scope, **stating each rule in one line** — not just its id — and names
   any place the request appears to contradict one, without resolving it.
2. **The architect** carries that table forward with the obligation each rule
   places on the dev lane, writes genuine conflicts into a conflicts table with
   an empty Resolution cell, and drafts an ADR for each new load-bearing decision.
3. **The audit** rewrites every spec line that contradicts a settled decision,
   fills every cross-cutting gap, and — this is the part unique to it — reads the
   *existing implementation* of every file in the spec's structure table and
   reports breaches already in the tree.
4. **The human gate** resolves every conflict — comply, amend, or supersede — and
   approves, amends, or rejects each draft ADR. A blank Resolution cell blocks the
   gate.
5. **Each dev lane** walks the binding table against its own diff before each of
   its two commits. A decision it would have to break to finish is not its to
   break: it blocks and surfaces.

The permanent ADR is written by the scribe after the code lands, exactly as
approved — never invented, amended, or reversed on the scribe's authority. A
decision that changed is edited in place with a dated status-history line, never
superseded by a new document.

## Codex and Defaults Accuracy

The scribe runs *after* development. `tdd-feature` documented the plan before the
code existed; this doctrine documents what shipped, reading the quest's real
commits alongside the spec, with the commits winning wherever they differ. That
also makes the codex's present-state rule honest: the document describes the
system as it is, with no "previously", no "replaces", no archaeology.

The same pass reconciles `src/lore/defaults/` — the seeds every fresh `lore init`
copies into a new project. One agent, one input, one commit; the heavy doctrine's
separate defaults review read the same diff a second time. Seeds default to
untouched, and anything needing product judgment is listed for the human rather
than guessed. `src/lore/defaults/docs/LORE-AGENT.md` is the seeded counterpart of
the repo's own agent instruction file: a shared-section edit lands in both or in
neither.

The scribe runs `lore health` before marking done and commits as
`docs(<slug>): reconcile codex, decisions, and seeded defaults`.

## Pause Points

One. `spec-gate` is the single steering point, and it is deliberately also the
pre-development pause, so the rule "pause before the first Red mission" costs
nothing extra. Everything else auto-dispatches.

If the human's own escalations at the gate are consistently resolvable against
recorded practice rather than product preference — as they were on the reference
run — that is a signal the recon and audit tables are doing their job, not a
signal the gate is unnecessary.

## Artifacts

| Artifact | Purpose |
|----------|---------|
| `tfl-recon-map` | The one recon document. Replaces two `fi-context-map` instances and adds the binding table, code surface, lane call, and verified-vs-inferred sections. |
| `tfl-feature-spec` | The one planning document, in five parts. Replaces `fi-prd`, `fi-tech-spec`, `fi-user-story` × N, and `fi-user-story-index`. Part 5 is the dispatch order. |

The spec is **self-contained by contract**: a dev lane builds a whole lane from
it without opening the recon map, the codex, or an ADR. "Follow standards" is not
a row in its structure table — the rule is written out with its codex id after it.

## Escalation

| Scenario | Orchestrator May | Orchestrator May Not |
|----------|------------------|----------------------|
| Recon reports a conclusion it did not verify | Require the architect to re-check it; re-spawn recon if the map is unusable | Let the architect build on an unverified claim |
| Recon leaves the binding table thin, or lists ids with no rule beside them | Send it back — this table is the spine of decision adherence | Proceed with an unlisted rule governing a file in scope |
| Recon resolves a conflict instead of naming it | Send it back; the gate resolves conflicts | Accept a conflict quietly reconciled by a read-only step |
| The spec leaves a TBD, a "follow standards", or an open question | Block the gate | Dispatch a dev lane against an incomplete spec |
| The audit returns `BLOCKED` | Hold at the gate until the escalations are resolved | Dispatch development on an unresolved conflict |
| The audit reports a pre-existing breach in the tree | Bring it to the user as fix-now or do-not-extend | Let a dev lane decide to fix or extend a breach on its own |
| A Part 3 conflict row is unresolved at the gate | Re-open the gate | Let a dev lane resolve a decision conflict |
| A dev lane would have to break a recorded decision to finish | Stop; bring it to the user as an amend/supersede decision | Accept a silent violation |
| A dev lane weakens, skips, `xfail`s, deletes, or mocks around a test to reach green | Reject the commit; require a real fix | Accept a green suite bought that way |
| A dev lane edits a test during green | Reject; tests change in red or in refactor-for-clarity only | Accept a test rewritten to match broken code |
| A dev lane silences `ruff` or `mypy` rather than fixing the cause | Block; require the root cause | Accept `# noqa`, `# type: ignore`, a broadened `Any`, or a loosened config |
| A dev lane touches another lane's files | Block; route the work to the owning lane | Approve cross-lane edits |
| The surface lane finds a rule it wants to write in `cli.py` | Route it to the core lane — ADR-011 | Approve business logic in the CLI layer |
| A later lane finds a signature differing from the spec | Code against the committed reality; record the divergence | Silently rewrite an already-committed lane |
| A lane's Part 5 unit list is very large | Split that lane into sequential missions against the same lane mission file | Run split missions in parallel — they race the git index |
| A lane has no units in Part 5 | Mark it done with no commit | Create a mission that invents work for an empty lane |
| The scribe documents the spec rather than the commits | Send it back to the diff | Ship a codex describing something that was not built |
| The scribe writes change history into a canonical document | Send it back — canonical layers are present-state | Ship "previously / replaces / now adopted" prose |
| The scribe writes an ADR the human did not approve, or supersedes one | Block | Let a scribe make or reverse a decision |
| The scribe reports `Needs human judgment` on a seed | Surface the listed drift to the user | Squash-merge with seed drift the agent flagged unresolved |

## When to Use Which Doctrine

| Situation | Doctrine |
|-----------|----------|
| Any Lore feature spanning one or more module lanes, default | **`tdd-feature-lite`** |
| A feature large or risky enough to want independent decomposition, per-story briefings, and a hard structural barrier between writing a test and making it pass | `tdd-feature` |
| A change whose entire cost is documentation | the `store-memory` skill, no quest |
| A single well-understood fix with a settled approach and no new decision | a one-off mission against the owning lane's mission file (`-D tdd-feature-lite/dev-foundation`, `dev-core`, or `dev-surface`), no quest |
| A PRD that does not exist yet and needs to be argued out first | the `draft-prd` skill, then this doctrine |

## Git Flow

```
work
└── feat/<feature-slug>          ← created by the branch constable (Phase 0)
     ├── foundation lane          working commit + clean commit
     ├── core lane                working commit + clean commit
     ├── surface lane             working commit + clean commit
     └── docs(...) commit         codex + approved ADRs + reconciled seeds
```

The human squash-merges `feat/<feature-slug>` into `work`. AI agents never merge,
and never touch `work` directly.

Note that the spec documents are **not** committed by a planning step here. The
recon map and the spec live in `.lore/codex/transient/` for the life of the quest
and are deleted by the scribe once their facts live in canonical documents; the
scribe's commit carries what survives.

## Notes

- The trade this doctrine makes: fewer hand-offs and fewer gates, at the cost of
  more riding on one architect and one worker per lane. That is a good trade when
  the architect is Opus at xhigh effort and a bad one when it is not.
- An upstream PRD is an **optional input**, not a precondition. `tdd-feature`
  refuses to start without one; here the architect writes Part 1 itself when there
  is none, and carries the PRD's intent forward without rewriting it when there is.
- The audit step is the one place this doctrine is heavier than its sibling
  `request-to-feature-lite`, which folds decision enforcement entirely into the
  architect. It is kept because on the reference run it found something the
  architect structurally could not: a breach in code the architect never read.
- One quest is one branch. The gate confirms the branch; the scribe's board
  message signals the branch is ready to merge.
