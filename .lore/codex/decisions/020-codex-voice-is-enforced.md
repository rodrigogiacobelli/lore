---
id: decisions-020-codex-voice-is-enforced
title: "ADR-020: Canonical codex documents describe current state; the voice rules live in the codex-voice artifact and are enforced as warnings"
summary: >
  ADR recording the codex voice contract. Canonical codex documents carry what is
  true now — git carries history, ADRs carry reasoning, CHANGELOG.md carries what
  changed, and the codex takes none of the three. The rules themselves live in one
  place, the shipped codex-voice artifact, retrieved with lore artifact show
  codex-voice; this ADR records the decision and does not restate them. transient/
  is exempt from the tense rules and decisions/ from the past-tense rules alone,
  sources/ is fully exempt, and vision/ is deferred as an open question.
  Enforcement is lore health --scope voice, warnings only, never affecting the
  exit code.
binds:
  - src/lore/defaults/artifacts/lore-design-documents/codex-voice.md
related:
  - codex
  - conceptual-entities-artifact
  - conceptual-workflows-health
  - decisions-006-no-seed-content-tests
  - decisions-017-constrained-flags-use-click-choice
  - decisions-019-overlay-scope-stops-at-transient
---

# ADR-020: Canonical codex documents describe current state; the voice rules live in the `codex-voice` artifact and are enforced as warnings

## Context

The codex accumulated two kinds of prose that no reader can act on. The first
kind narrated changes: a document explained that a subdirectory had been removed,
or that a helper used to live in `cli.py`. The second kind hedged against its own
expiry, marking a fact as provisional without naming what would change it. Both
kinds parse only against a previous version of the system, and an agent running
`lore codex show <id>` cold has no previous version to parse against.

Three stores already held that material. Git held the history. `decisions/` held
the reasoning. `CHANGELOG.md` held the list of what changed. Every narrated
sentence in a canonical document duplicated one of the three, and the duplicate
was the copy nobody updated.

No document said this was wrong. Authors — human and agent alike — had no rule to
apply and no command to run, so each writer settled the question again from taste.

An evaluation ran alongside this problem: ASD-STE100, the aerospace controlled-language
standard, was tested as an off-the-shelf answer. Three documents were rewritten into
it — `decisions-009-mission-self-containment`, `conceptual-entities-mission`, and
`ops-git-workflow` — and the rewrites are what settled the question. The results are
recorded under Alternatives Considered.

## Decision

**A canonical codex document describes current state.** It carries what is true
now. Git carries the history, `decisions/` carries the reasoning, and
`CHANGELOG.md` carries what changed. The canonical codex takes none of the three.

**The rules live in one file: the `codex-voice` artifact.** Retrieve them with
`lore artifact show codex-voice`. That artifact holds the rule table, the two
tests that settle ambiguous sentences, and the worked examples. This ADR records
the decision behind the artifact and does not restate its contents. One fact
lives in one file; a rule copied into a second document is a rule that goes stale
in one of them.

**The rules ship with Lore.** The artifact is a packaged default at
`src/lore/defaults/artifacts/lore-design-documents/codex-voice.md`, which
`lore init` copies into every new project. A project retrieves the rules by ID
without authoring anything.

**Voice is scoped per layer, not applied uniformly.** Each layer answers a
different question, so each gets a different tense budget. The `codex-voice`
artifact holds the per-layer table; the decisions behind it are:

- **`decisions/` is exempt from the past-tense rules (V1 and V2), and from
  nothing else.** An ADR's Context section is by definition the world before the
  decision, and dated status-history lines are part of the house ADR format.
  V3 and V4 hold: an ADR records a choice already made, so it earns past tense
  but neither a hedge nor a promise of later work. V5–V10 apply. The artifact's
  layer table carries the full budget.
- **`transient/` is exempt from the tense rules (V1–V4).** In-flight work is the
  layer's purpose. A mid-flight feature has a home, and that home is the
  exception — there is no per-document escape hatch anywhere else in the codex.
  V5–V10 still apply.
- **`sources/` is fully exempt.** A source body is verbatim upstream text. No
  voice rule applies to it, and no author edits a source to fit the rules.
- **`vision/` is deferred.** `lore health --scope voice` skips the layer. This is
  an open question, not an oversight: a vision document states intent about a
  system that does not exist yet, which is the one case the present-tense rule
  was not written for. The rule for `vision/` needs its own decision.

**Enforcement is `lore health --scope voice`, and it emits warnings only.** The
scope never contributes to the exit code. Adding `voice` to the `--scope` token
set is a permitted token addition under
`decisions-017-constrained-flags-use-click-choice`; the `click.Choice` mechanism
and the exit-2 contract for an out-of-set token are unchanged.

**The mechanical rules are checked; the judgment rules are not.** The scope
pattern-matches the rules a pattern match can decide and reports each as a
`voice_*` warning. Four rules — named actor, one name per thing, no attribution
to the process that produced a fact, and checkable claims — need judgment no
pattern supplies, and no check covers them. The `codex-voice` artifact names
which rules fall on which side.

## Rationale

**Warnings, because a third of the rules cannot be checked.** Four of the ten
rules need a reader's judgment. A scope that failed the build on the six it can
match would assert a completeness it does not have: a document could pass with
zero mechanical hits and still violate every judgment rule. Worse, a hard failure
on a heuristic that produces false positives — a hedge word quoted inside an error
message, a past tense inside a code comment — trains authors to pass
`--scope` lists that omit `voice`, or to reach for the flag that turns the audit
off. A check people disable enforces nothing. A warning that costs nothing to
leave on keeps reporting for the life of the project.

**A warning is a prompt to look, not a verdict.** The two tests in the
`codex-voice` artifact settle the flagged sentence. That division of labour only
works if the machine's output is advisory; an error would put the pattern match
in charge of a question it cannot answer.

**One file for the rules, referenced by ID.** The voice rules describe how to
avoid duplicating facts across documents. Restating the rule table inside this
ADR would violate the rule it records, and would produce two tables that drift.
`lore artifact show codex-voice` is one command and returns the current text.

**A shipped artifact reaches every project; a repository document reaches one.**
Artifacts are retrieved by stable ID and are packaged with Lore. Voice is a
property of the codex as a product, so it travels with the product.

**`transient/` is the single exception, and it already is one.**
`decisions-019-overlay-scope-stops-at-transient` fixed the same boundary for
custom-schema overlays: `transient/` holds scratch artefacts of an in-flight
feature and does not carry governance meant for permanent knowledge. Exempting
it from the tense rules extends a boundary that exists rather than inventing a
second one.

## Consequences

**Easier:**

- An author who is unsure about a sentence runs one command
  (`lore artifact show codex-voice`) and gets the rules, the two tests, and
  worked examples. The question is settled by a document rather than by taste.
- `lore health --scope voice` gives a mechanical first pass over six of the ten
  rules, so review attention goes to the four that need it.
- Adding the voice rules to a project costs nothing: `lore init` seeds the
  artifact.

**Harder:**

- A document that legitimately needs to describe a prior state has exactly two
  homes — `decisions/` and `transient/`. An author who wants that prose in
  `conceptual/` or `technical/` cannot have it, and must split the document or
  move the fact.
- The judgment rules have no automated backstop. A document can pass
  `lore health --scope voice` clean and still read as a sales page.
- Rewriting an existing document's prose against the rules produces churn that no
  behaviour change explains, so voice fixes and behaviour edits land as separate
  passes.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **A `standards/codex-voice.md` codex document instead of an artifact** | `standards/` is project-owned territory. Lore ships no document into a project's `standards/` directory — this repository's own `standards/` docs (`dry`, `facade`, `single-responsibility`, and the rest) are authored here, about this codebase. A shipped artifact reaches every project through `lore init`; a document in this repository's `standards/` reaches this repository. |
| **Enforce voice as errors, failing the build** | Four of the ten rules need judgment a pattern match cannot supply, so an error asserts a completeness the check does not have. Heuristic false positives that break a build train authors to drop `voice` from their `--scope` list, which enforces nothing. Warnings cost nothing to leave enabled. |
| **Adopt ASD-STE100 wholesale** | Three trial rewrites settled it. (a) ASD holds the copyright on the specification and its approved-word dictionary of roughly 900 entries, under terms that do not permit redistribution — and Lore ships its rules into every project via `lore init`, so it cannot carry the dictionary. (b) The dictionary is written for aircraft maintenance procedures; its approved senses do not cover the codex's subject matter. (c) The blocking defect: STE has no register for hedging or disagreement. An ADR's Context section argues, weighs, and rejects. In the trial rewrite of `decisions-009-mission-self-containment`, "fragile and lossy" flattened to "weak and loses data" and "a violation of the intent" flattened to "against the intent" — the rejection survives as a fact and loses its force, which is the part of an ADR a later reader needs. Two of STE's mechanical ideas — a named actor for every behaviour, present tense for current state — hold on their own merits and appear in the voice rules as V6 and V1. The standard itself does not. |
| **Per-document opt-out for voice, via a frontmatter key** | A per-document escape hatch makes the exemption a property each author sets, and the set grows monotonically. A mid-flight feature already has a home in `transient/`; a document that needs to narrate change belongs there or in an ADR, not in a stable layer with a flag on it. |
| **Leave voice to review, with no artifact and no check** | This was the state that produced the problem. Every author settled the question independently, and the narrated prose accumulated because nothing named it as a defect. |

## Constraints Imposed

1. **The rules have one home.** The `codex-voice` artifact is the only place the
   voice rules are written. Any document that needs them references
   `lore artifact show codex-voice` rather than copying the rule table.
2. **`lore health --scope voice` never affects the exit code.** Every issue the
   scope reports is a warning. Promoting any `voice_*` issue to an error requires
   its own ADR.
3. **Layer exemptions are fixed, not per-document.** `transient/` is exempt from
   V1–V4, `decisions/` from V1 and V2, `sources/` from all ten. No frontmatter
   key, comment marker, or filename pattern grants an exemption to an individual
   document.
4. **`vision/` stays skipped until a decision covers it.** The skip is recorded
   here as an open question. Enforcing voice on `vision/` requires settling what
   tense a document about an unbuilt system writes in.
5. **The artifact's prose is not pinned by tests.** It is a seed default under
   `src/lore/defaults/`, so `decisions-006-no-seed-content-tests` applies: tests
   assert that the artifact is seeded and retrievable by ID, never that it
   contains a particular sentence.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-07-30 | accepted | Recorded alongside the `codex-voice` artifact and the `lore health --scope voice` check. ASD-STE100 was evaluated through three trial rewrites and rejected; `vision/` deferred as an open question. |
