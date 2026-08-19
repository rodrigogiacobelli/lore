---
name: draft-prd
description: Co-author a PRD for Lore through a one-question-at-a-time interview that challenges assumptions and is grounded in the codex, the ADRs, the standards, and the code, then write it using the fi-prd artifact into the transient codex. Use when the user wants to draft a PRD before running the tdd-feature doctrine, which requires a settled PRD to already exist.
---

# Draft PRD

Co-author a Product Requirements Document with the user, interactively.

Lore's `tdd-feature` doctrine has **no PRD step** — it names a settled PRD as a hard precondition and refuses to start without one. This skill is how that PRD gets written. You interview the user, challenge their thinking, ground every question in what already exists, and converge on a complete, scoped PRD together.

The output is the `fi-prd` artifact written into `.lore/codex/transient/`. When you finish, the user runs `/start-quest tdd-feature` and the pipeline picks up at `branch` → `scout` with the PRD codex ID passed into the mission descriptions. No rework.

## Non-negotiable rules

1. **One question at a time. Always.** Ask a single question, wait for the answer, then decide the next question from that answer. Never present a numbered list of questions, never bundle "and also." Each answer reshapes what you ask next — that is the entire point.
2. **Investigate before you ask.** Never ask the user something the codex, the ADRs, the standards, or the code already answers. Do the search first; ask only what genuinely needs a human decision. A lazy question ("should deleting this hard-delete the row?") when ADR-003 already settles soft-delete for every entity wastes the user's time and signals you didn't look.
3. **Challenge assumptions.** You are not a stenographer. When the request conflicts with a settled ADR or standard, duplicates something that exists, or skips a hard constraint, push back with the evidence. Surface the cheaper or simpler path. The user can overrule you — but they decide with the tradeoff in front of them.
4. **Never invent scope.** If the user didn't surface it, it doesn't enter the PRD. Scope creep starts here. When you think something is missing, *ask* — don't silently add it.
5. **You write; the user decides.** Resolve every open question with the user before writing. The final PRD has no "TBD," no deferred decisions, no questions left for downstream agents.

## Step 1 — Get the raw request

If the user already described the feature, restate it back in one or two sentences and confirm you've got it right. If they invoked this skill cold with no description, ask for the feature in their own words — that's your one opening question.

Do not start interviewing yet. You investigate first.

## Step 2 — Investigate before interviewing

Build context so your questions are sharp. Spend real effort here.

**Codex.** Use the `explore-codex` skill, or run directly:

- `lore codex search <feature-keywords>` — 2–4 searches from different angles
- `lore codex map <id> --depth 1` on whatever you find — traverse neighbours
- `lore impacts <path>` — when the request names a file or area, find the docs that govern it
- `lore impacts <codex-id>` — when assessing how far a doc's rules reach
- `lore glossary search <term>` — when the request introduces vocabulary

Lore's codex is self-hosted and dense. The layers that bind a PRD are `decisions/` (the ADRs) and `standards/` — read **both groups in full** before interviewing:

```
lore codex list --filter decisions standards
lore codex show <every-adr-and-standard-that-could-touch-the-feature>
```

Then read the orientation and architecture docs the feature lands on:

```
lore codex show codex tech-overview tech-arch-source-layout
```

`lore codex show codex` carries the codex's own layer rules, the transient-layer contract, and the frontmatter schema — you need all three at write time. Also read the guardrails in `CLAUDE.md`.

**Code.** Lore is a single typed Python package with a `src/` layout. Search the real tree — never guess a path:

- `src/lore/` — one module per concern (`cli.py`, `db.py`, `codex.py`, `validators.py`, `health.py`, …); `tech-arch-source-layout` maps every file
- `src/lore/api.py` — the public facade; `__all__` is the contract
- `src/lore/schemas/*.yaml` — the packaged frontmatter and entity schemas
- `src/lore/migrations/` — the DB schema version chain
- `src/lore/defaults/` — everything a fresh `lore init` seeds into a *target* project
- `tests/unit/` and `tests/e2e/` — the pytest suite
- `pyproject.toml` — what is actually a dependency

Dispatch an `Explore` agent for broad fan-out ("does anything like X already exist?"). The goal is a reuse-first map.

**Check both surfaces.** Lore ships every capability twice — as a Click command and as a `lore.api` function (ADR-011). For anything the user says already exists, confirm it exists on *both* surfaces before treating it as done.

Come out of this step with: which modules the feature touches, what already exists to reuse, which ADRs and standards bind it, whether it needs a DB migration or a schema change, whether it changes what `lore init` seeds, and a list of the genuine unknowns only the user can resolve.

## Step 3 — Interview, one question at a time

Now drive the conversation. Walk the PRD's shape, but let the user's answers set the order and depth. Ask the highest-leverage open question first — usually the one whose answer unlocks the most downstream questions.

**Coverage checklist** (these map to `fi-prd` sections — you must be able to fill every one before writing):

- **Problem & users** — what problem, for whom. Lore's personas are the **AI agent** driving the CLI (orchestrator dispatching work, worker executing a mission), the **human developer** at a terminal, **Realm** consuming Lore through `from lore.api import ...`, and the **downstream project** that receives `src/lore/defaults/` on `lore init`. Drives Executive Summary + Project Classification.
- **Surfaces touched** — the core module, the Click group in `cli.py`, `lore.api.__all__`, the SQLite schema and its migration, `src/lore/schemas/`, `lore health` scopes, the `.lore/` on-disk store, `src/lore/defaults/`. Usually known from Step 2; confirm rather than ask blind.
- **Success criteria** — what "winning" looks like, separately for the calling agent and for the human or Realm consumer.
- **Scope in / out** — capability by capability. Challenge each: needed now? Does something already do it? Push for explicit out-of-scope exclusions.
- **Workflows** — exact steps, on **both surfaces**. Not "the agent lists the things" but: `lore thing list --filter ops` prints an `ID GROUP TITLE SUMMARY` table; `lore --json thing list` returns `{"things": [{id, group, title, summary}]}` with `group` slash-joined or `null`; exit 0, or exit 1 with the error envelope on stderr when the store is missing; `lore.api.scan_things(root)` returns the same list of dicts and raises `ThingError` on the same condition. Pin down the command line, the stdout shape, the `--json` envelope, the exit code, the Python call signature, and its return shape or exception. A workflow vague enough that acceptance criteria can't be written from it is not done.
- **Maintainer story** — Lore is a package, so the maintainer's surface is what changes for someone who upgrades it or runs `lore init` fresh: the migration that runs, the seeds that land in `src/lore/defaults/`, the new `lore health` check, the `CHANGELOG.md` entry. State it whenever the feature changes any of those; say "none" explicitly when it changes none.
- **Functional requirements** — discrete, actor-scoped capabilities.
- **Non-functional** — performance is round-trips, not milliseconds: ADR-001 makes "minimise tool calls" a design constraint, so say how many commands an agent runs to complete the workflow. Reliability covers concurrent access (`conceptual-workflows-concurrent-access`). Security is nearly always "Lore has no auth surface — local filesystem and SQLite only" — say so explicitly rather than leaving it blank.

**Challenge against these before accepting any scope.** Each is a settled decision the PRD must not contradict:

| Guardrail | Source | What a violating PRD looks like |
|---|---|---|
| Every capability is a core function plus a thin Click wrapper — the CLI holds no logic | ADR-011, `standards-separation-of-concerns`, `standards-dependency-inversion` | A workflow given only as a CLI command, with no Python call and return shape |
| Public exposure means a name in `lore.api.__all__`, and adding one is a semver event | ADR-010, `standards-facade`, `standards-public-api-stability` | "Realm imports `lore.db.foo`", or a public capability with no `lore.api` story |
| Lore stores and exposes; it never interprets or executes | ADR-001, ADR-004 | Lore dispatching an agent, running a doctrine, firing a watcher, or branching on `mission_type` |
| Zero dependency on Realm or Citadel — not even optional | `CLAUDE.md` | An import, an extra, or a callback into the orchestrator |
| Single-file SQLite, no server, no daemon, no background process | ADR-001 | A watch loop, a sync service, a network listener |
| Agents address entities by ID through the CLI, never by file path | ADR-006 | A step telling an agent to open `.lore/<dir>/<name>.md` directly |
| Deletes are soft | ADR-003 | "removes the row", a hard delete, a cascade delete |
| `--help` teaches the model, it does not only describe syntax — at root and group level | ADR-008 | A new command group with syntax-only help |
| Multi-value flags are space-separated; constrained flags use `click.Choice`, so a bad value is exit 2 | ADR-012, ADR-017 | Repeatable `--flag a --flag b`, or hand-rolled validation exiting 1 |
| `--json` is a documented envelope on stdout; errors carry the error envelope on stderr | `conceptual-workflows-json-output`, `conceptual-workflows-error-handling` | A command whose JSON shape and exit codes the PRD leaves unstated |
| Config is TOML; codex content is YAML and markdown | ADR-013 | A new YAML config file, or config smuggled into a codex doc |
| Links live on the stable, authoritative side | ADR-014 | A rite linking back to a codex doc, or a canonical doc listing a source |
| Custom-schema overlays reach canonical docs and sources, never `transient/` | ADR-018, ADR-019 | A transient doc carrying a project custom key |
| Canonical codex docs state what is true now | ADR-020, `lore artifact show codex-voice` | A PRD asking for changelog narration inside a stable doc |
| Tests never assert on the content of seeded default files | `lore artifact show adr-no-default-content-tests` | An acceptance criterion pinning the wording of a `src/lore/defaults/` file |
| A fresh `lore init` reflects reality | `src/lore/defaults/`, the doctrine's Defaults Review phase | A new entity, skill, or doctrine that nothing seeds |

Where the PRD makes a genuinely new architectural choice no ADR governs, that is fine — note it, and let the downstream `adr-standards-enforcer` flag it for an ADR. Do not invent the ADR here.

**Glossary gate.** If the feature introduces vocabulary and you are tempted to add it to `.lore/codex/glossary.yaml`, run `lore artifact show glossary-design` first. Entity names and named workflows never belong there — each already owns a document. The PRD may name a term; it must not schedule a glossary entry that fails the gate.

**How to ask:**

- Default to a plain conversational question and wait. This is the natural mode for open-ended PRD decisions.
- Use the `AskUserQuestion` tool when the decision is genuinely a choice between a few discrete options you can name — it makes the tradeoff legible. Still one question per call.
- When you ask, bring your evidence. "ADR-012 fixes multi-value flags as space-separated, and `--filter` already works that way — does this flag follow the same shape, or is there a reason it takes one value only?" beats "how should the flag work?"
- Track open questions as you go. When an answer raises a new ambiguity, queue it; don't drop it. You may show a short running "still open" list between questions so the user sees the shrinking frontier — but never ask more than one at once.
- Know when to stop. When every checklist item is resolved and no open question remains, move on. Don't pad the interview.

## Step 4 — Synthesize and confirm

Before writing anything, play back the whole thing in prose: scope in and out, the workflows on both surfaces, the requirements, the maintainer story, the success criteria. Explicitly state any assumption you're carrying. Ask the user to confirm or correct — this is the last gate before the file exists.

If the playback surfaces a gap, return to Step 3 (still one question at a time).

## Step 5 — Write the PRD

Retrieve the template and fill it from the interview — nothing invented, nothing deferred:

```
lore artifact show fi-prd
```

Create the doc **through the CLI**, never by hand — the codex root doc requires it so frontmatter normalisation and schema validation run. Write the draft to your scratchpad directory first, then:

```
lore codex new <feature-slug>-prd --group transient -f <scratchpad>/<feature-slug>-prd.md
```

Your draft file carries the frontmatter plus the filled template body:

```markdown
---
id: <feature-slug>-prd
title: <Feature Name> — PRD
summary: <one-line product brief>
related:
  - <codex-ids-the-feature-touches>
---

# <Feature Name> — PRD
...
```

**Transient frontmatter takes packaged fields only** — `id`, `title`, `summary`, and optionally `related`, `binds`, `rites`. Custom-schema overlays stop at the transient boundary (ADR-019), so any project-specific key is rejected as an unknown property.

Filling rules:

- **Omit the `**Supersedes:**` line and the whole `## Change Log` section.** This interview replaces the PRD Draft, so there is nothing to supersede; and the codex takes no changelog narration — `CHANGELOG.md` and git hold that.
- **Leave Pre-Architecture Notes empty** — that section belongs to the user, appended after they review.
- Fill Project Classification with Lore's real values: a CLI tool and importable Python library, whose primary users are AI agents, human developers, and Realm.
- Every workflow step must be concrete enough that acceptance criteria drop straight out of it, and must state the behaviour on **both** the CLI and the `lore.api` surface — including the `--json` envelope and the exit code.
- Keep the maintainer story first-class whenever the feature changes a migration, a schema, a `lore health` check, or `src/lore/defaults/`.
- Write in present tense. No "v1 will", no "later we add" — the PRD states what the feature is.

The PRD lands in `transient/`, where voice rules V1–V4 are relaxed but V5–V10 still bind: name every actor, use one name per thing, make every claim checkable, and stay out of the sales register. Run `lore artifact show codex-voice` if you need the table.

Then verify:

```
.venv/bin/lore health --scope codex voice
```

Fix any complaint on the new file.

## Step 6 — Hand off

Tell the user the PRD's codex ID and that `tdd-feature`'s precondition is now satisfied. Offer to kick off the quest via the `start-quest` skill — but don't start it without their go-ahead.

Two things to flag at handoff:

- The doctrine's Phase 0 Branch constable checks out `feat/<feature-slug>` **off `work`** and stops if the current branch is anything else. Check `git branch --show-current` and say so if it isn't `work`.
- The doctrine's human gate (`spec-gate`) reviews the **Tech Spec**, not this PRD. So if the user wants to change product scope, the moment is now, before the quest starts.

## Notes

- This skill replaces *authoring*, not *review*.
- **`lore` on your PATH is a frozen tool install.** It does not see uncommitted changes under `src/lore/` — `.venv/bin/lore` does. When the answer depends on unreleased code, use the venv binary, and verify a capability against `src/lore/` rather than against whichever binary answered first.
- **"Does Lore do X" and "does a `lore init`-ed project get X" are different questions.** This repo's own `.lore/` is customised and drifts from `src/lore/defaults/`. A doctrine, knight, or skill present here is not necessarily seeded, and vice versa. Never answer one question with the other's evidence.
- **`CLAUDE.md` calls `lore.models.__all__` the public API. ADR-010 supersedes that line** — `lore.api.__all__` is the contract, and `models.py` is an internal typed-record index. When the two disagree, the ADR wins.
- If the request is purely a documentation change, this is the wrong tool — use `update-codex`. If it is a one-line fix, skip both the PRD and the doctrine.
- Keep the interview honest: a PRD that hides an unresolved decision behind soft language just moves the cost downstream to the architect. Resolve it now or name it as an explicit out-of-scope exclusion.
