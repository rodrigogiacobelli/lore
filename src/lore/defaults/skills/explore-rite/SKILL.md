---
name: explore-rite
description: Browse and read rites to find the right how-to procedure for a task or diagnosis
---

# Explore Rite

Use the Lore rites to find the procedure for doing or diagnosing a recurring task. Rites are procedural memory — the *how-to* counterpart of the codex. Where the codex answers "what is true", a rite answers "how do I do or diagnose X". A **main rite** is a node-graph that carries the judgment (branches, forks, typed conclusions); a **shared step** is a pure, reusable procedure that main rites pull in with `use:`.

Retrieval is **AI-as-matcher**: Lore never matches a situation to a rite for you. You read each rite's `trigger` (the prose cue) and `summary` (the one-line outcome) from `lore rite list`, pick the fit yourself, then `lore rite show` it to follow the steps.

## When to use which command

| Goal | Command |
|------|---------|
| Browse all main rites (id, group, trigger, summary) | `lore rite list` |
| Browse reusable shared steps | `lore rite list --shared` |
| Narrow a group by slash-token | `lore rite list --filter <a/b>` |
| Keyword-browse by id, title, summary, or trigger | `lore rite search <keyword>` |
| Read one or more rites in full (shared steps inlined) | `lore rite show <id1> <id2> ...` |
| Find the rites a codex doc governs | read that doc's `rites:` frontmatter field |

A `lore rite show` inlines every shared step a main rite pulls in via `use:`, so one call gives you the complete, follow-it-now procedure — you do not chase the steps separately.

## Steps

### 1. Scan the list and match a trigger

Start by reading the triggers and summaries:

```
lore rite list
```

The `trigger` is the cue that should fire ("a customer asks for a refund on a returned order"); the `summary` is the outcome the rite produces. Match your situation against the triggers and pick the rite whose trigger fits. If many rites share a group, narrow with `--filter`:

```
lore rite list --filter diagnostics/network
```

If a keyword captures the task better than scanning, search:

```
lore rite search refund
```

`search` covers main rites only — id, title, summary, and trigger. Use `lore rite list --shared` to browse the reusable steps directly.

### 2. Read the matched rite in full

```
lore rite show <id>
```

This prints the whole node-graph with every `use:` shared step inlined. Read the branches and the typed `conclusions` so you know each outcome before you start. Batch multiple IDs in one call when comparing candidates:

```
lore rite show issue-refund diagnose-failed-charge
```

### 3. Follow the rite

Walk the nodes in order. At each `do`/`use` node, run the instruction and carry its result to the `then` edge; at a fork, evaluate the `if` and `goto` the matching node. Stop when you hit a `conclusion` — that typed outcome is the rite's answer. The judgment lives in the rite; do not improvise past a conclusion.

### 4. Pivot from the codex

Links point one way: a codex doc lists the rites it governs in its `rites:` frontmatter field — rites carry no outbound links back. When a question starts from a codex doc, read its `rites:` field to find the procedures attached to it:

```
lore codex show <codex-id>
```

For broad factual research, or to find the codex doc that governs a topic in the first place, use the `explore-codex` skill. To research a question that spans both what-is-true and how-to at once, use the `explore-codex-rite` skill.

### 5. Report the outcome

State the rite you followed and the conclusion you reached (e.g. "per `lore rite show diagnose-failed-charge`, conclusion: fraud-hold — escalate"). If no rite's trigger matches the situation, say so plainly rather than forcing a near-miss rite onto it — a missing rite is a signal to author one with the `new-rite` skill, not to improvise.
