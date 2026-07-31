---
id: codex-voice
title: Codex Voice Rules
summary: >
  The single voice every canonical codex document uses. Read this before you
  write or edit any file under `.lore/codex/`. The codex is a state store, not
  a narrative — it describes what is true now, for a reader who arrives cold
  with no conversation behind them. Two tests decide every borderline sentence.
  Ten rules cover the rest. `lore health --scope voice` enforces the mechanical
  ones.
---

# Codex Voice Rules

Every canonical codex document speaks with one voice. This file defines it.

The voice is not a style preference. It follows from four properties the codex already has.

**The codex is a state store.** `lore show` reports that a Mission is `blocked`. It does not report that the Mission was open and is now blocked. Codex documents work the same way: they carry what is true now. Git carries the history. ADRs carry the reasoning.

**The codex is read cold, one document at a time.** An agent runs `lore codex show <id>` with no conversation behind it. A sentence that resolves against context outside the document fails that reader.

**The codex is the source of truth, not a report about it.** A statement in a canonical doc is authoritative. It does not need a hedge, a source, or the story of who agreed to it.

**One fact lives in one file.** A document that restates another document's facts creates two places to update and one place to be wrong.

## The Two Tests

Apply these to any sentence you are unsure about.

**The Fresh-Reader Test.** Does this sentence mean anything to a reader who never saw a previous version of the system? A sentence that only parses as a delta against an earlier state is changelog content. Cut it.

**The Sentence Deletion Test.** Delete the sentence. Is a fact about today lost? If no fact is lost, the sentence was narration. Leave it deleted.

The two tests settle the common ambiguity. "The parent is no longer visible" passes both — it states a fact about the system now. "The `bootstrap/` subdirectory no longer exists" fails both — no fact about today disappears when you cut it.

## The Rules

| # | Rule | Violation | Correct |
|---|---|---|---|
| V1 | Write in the present tense about current state. | "The module previously read each file twice." | "The module reads each file once." |
| V2 | Never narrate a release or a change. | "Introduced this release — previously inline in `cli.py`." | *(delete the clause)* |
| V3 | Never use an expiry hedge. | "currently", "for now", "at the time of writing", "so far" | Delete the word, or state the value it hides. |
| V4 | Never promise future work. | "Validation will be added in a later release." | The promise belongs in `transient/` or in a quest. |
| V5 | Never point outside the document. | "as mentioned above", "the new flag", "this release" | Name the thing, or link to the document that owns it. |
| V6 | Give every behaviour a named actor. | "The file is rejected." | "`lore health` rejects the file." |
| V7 | Use one name for one thing. | "board", then "notes list", then "message log" | Use the name the owning document uses. |
| V8 | Never attribute a fact to the process that produced it. | "We decided to store config in TOML." | "Lore stores config in TOML." (The ADR owns the decision.) |
| V9 | Never use the sales register. | "powerful", "seamless", "robust", "simply", "just" | Delete the word. The sentence survives. |
| V10 | Make every claim checkable. | "Validation is strict." | "`validate_entity` rejects any key absent from the schema." |

## Which Rules Apply Where

Voice is not uniform across the codex. Each layer answers a different question, so each layer gets a different tense budget.

| Layer | Past tense | Future or intent | Reason |
|---|---|---|---|
| `conceptual/`, `technical/`, `api/`, `standards/`, `operations/` | No | No | Pure present state. All ten rules apply. |
| `decisions/` | **Yes** | No | An ADR's Context section is the world before the decision. Dated status-history lines are part of the format. V1 and V2 do not apply. **V3 and V4 still do** — see below. V5–V10 apply. |
| `transient/` | Yes | **Yes** | In-flight work is the entire purpose of the layer. V1–V4 do not apply; V5–V10 do. |
| `sources/` | n/a | n/a | Source bodies are verbatim upstream text. No voice rule applies. Never edit a source to fit this file. |
| `vision/` | — | — | Deferred. `lore health --scope voice` skips this layer. See "The `vision/` deferral" below. |

**Why `decisions/` keeps V3 and V4.** An ADR gets past tense because its Context section describes the world before the decision, and that world is over. It does not get hedges or promises. A hedge marks a fact as provisional without saying what would change it, and an ADR is the one document that must not be provisional — it records a decision that was made. A promise about future work is worse: an ADR is where stale roadmap hides longest, because nobody re-reads a decision from two years ago to check whether the thing it promised ever happened. Write what the decision commits to, in the present tense. Work that has not happened belongs in `transient/` or in a quest, not in the record of a choice already made.

**Naming under V7.** Most codex nouns have no glossary entry, and that is deliberate — the glossary gate excludes entity names and named workflows, because each already owns a document. So V7 resolves against the owning document: a term defined by an entity or workflow doc takes the name that document uses in its title and body. Use a glossary term only where an entry exists. When neither exists, pick one name, use it everywhere in the document, and expect the reader to meet it here first.

**The `vision/` deferral.** Vision documents state intent about a system that does not exist yet, which is the one case the present-tense rules were not written for. The layer is skipped rather than exempted: no rule has been decided for it. The deferral ends when someone settles whether a vision document marks intent explicitly ("Planned:", "Not yet built:") or drops the forward-looking content entirely. Until then, a vision document raises no voice warning and receives no voice guarantee.

**A note on `standards/`.** The strict row includes `standards/`, but Lore ships nothing into a project's `standards/` — that is project-owned territory, and it is the reason these rules ship as an artifact instead of a standards document. The rules still apply there: a project that writes its own standards documents holds them to the same voice as the rest of its canonical codex. Lore states the rule; the project writes the prose.

A feature that is mid-flight has a home: `transient/`. That is the whole exception. When the feature ships, its facts move into a stable layer and pick up the full rule set on the way.

## Worked Examples

### Changelog content in a stable document

> The `bootstrap/` subdirectory that previously existed alongside these namespaces has been eliminated. Its orientation guidance was absorbed into the Codex root.

Fails V1 and V2. The reader does not know the old layout and does not need to. Write what is true:

> Orientation guidance lives in the Codex root.

### An expiry hedge

> `DependencyType` currently only supports `"blocks"`.

Fails V3. The word "currently" adds nothing and marks the sentence as expiring. Write:

> `DependencyType` has one value: `"blocks"`.

### A missing actor

> Any file with an undeclared frontmatter key is rejected.

Fails V6. The reader cannot tell whether the CLI, the schema validator, or `lore health` does the rejecting. Write:

> `validate_entity_file` rejects any file with an undeclared frontmatter key.

### A legitimate past tense

> Rites originally shipped as the lone exception: a flat id space split only by `main/` and `shared/`.

This sits in `decisions/016-rite-json-envelope-omits-group.md`. Prior state is what an ADR Context section is for. Correct as written.

## Enforcement

Run this before you finish any codex edit:

```bash
lore health --scope voice
```

The scope reports warnings, never errors. It checks the mechanical rules only:

| Issue ID | Rule | Skipped in |
|---|---|---|
| `voice_past_narration` | V1, V2 | `decisions/`, `transient/`, `sources/`, `vision/` |
| `voice_expiry_hedge` | V3 | `transient/`, `sources/`, `vision/` |
| `voice_forward_promise` | V4 | `transient/`, `sources/`, `vision/` |
| `voice_dangling_deixis` | V5 | `sources/`, `vision/` |
| `voice_sales_register` | V9 | `sources/`, `vision/` |

V6, V7, V8, and V10 need judgment that a pattern match cannot supply. No check covers them. Read them yourself before you finish.

A warning is a prompt to look, not proof of a defect. When a flagged sentence passes both tests in "The Two Tests", leave it and move on.

## When in Doubt

Cut the clause. A codex document that says less about today is recoverable — a reader runs one more command. A codex document that narrates a change the reader cannot see costs that reader the time to work out which parts still hold.

If the fact you want to write is about work in progress, it belongs in `transient/`. If it is about why the system took its shape, it belongs in an ADR. If it is about what changed, it belongs in `CHANGELOG.md` and in git. The canonical codex takes none of the three.
