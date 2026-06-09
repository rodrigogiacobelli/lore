---
id: rite-main
title: Main Rite Template
summary: >
  Copy-paste skeleton for a main rite — the node-graph form of procedural memory
  ("how to do or diagnose recurring task X"). Lives under `.lore/rites/main/`
  (optionally in a subfolder, which becomes its group). A main rite holds the
  judgment: branching nodes, shared-step `use:` references, and typed
  conclusions. See `lore artifact show rite-design` for worked examples and the
  full authoring rules.
---

# Main Rite Template

A **main rite** is a small node-graph: an entry node, edges (`then`), optional
forks (`if`/`goto`), reusable steps pulled in with `use:`, ending in one of a set
of typed `conclusions`. The judgment lives here in the rite — shared steps only
*do* and *report*, they never decide.

Create with `lore rite new <id> --group <path>` (group optional), then `lore rite
edit <id> --from <file>`. The `id` is globally unique across the whole tree; the
subfolder is cosmetic and becomes the `group` shown in `lore rite list`.

```yaml
id: {bare-unique-id}                    # globally unique; folder is NOT part of identity
title: {short human title}
summary: {one line — what this rite accomplishes; shown in `lore rite list` + read by the AI matcher}
trigger: {prose cue — the situation in which an agent should reach for this rite}

nodes:
  - id: {first-node}                    # the entry node = the one node nothing routes to
    do: {what the agent does at this step, in plain instruction}
    then: {next-node-id}                # straight edge

  - id: {step-using-a-shared-procedure}
    use: {shared-step-id}               # bare id — Lore finds it anywhere under shared/
    then: {next-node-id}

  - id: {a-decision}                    # judgment lives in the rite, never in a shared step
    do: {what to weigh}
    then:                               # fork — a list of if/goto
      - if: {condition A}
        goto: {node-or-conclusion-key}
      - if: {condition B}
        goto: {node-or-conclusion-key}

  - id: {a-terminal-node}
    do: {final action}
    then: {conclusion-key}              # routing to a conclusion key ends the rite

conclusions:
  {conclusion-key}:
    audience: {who acts on this outcome, e.g. customer-care}
    response: {what to tell that audience / what the outcome is}
  {another-conclusion-key}:
    audience: {…}
    response: {…}
```

## Rules

- **`id` is bare and globally unique** across every rite and shared step, in any
  subfolder — exactly like a codex id. The folder only sets the `group`.
- **Every `then`/`goto` must point** at a node `id` in this rite or a key in
  `conclusions`. Nothing may dangle.
- **One entry node** (exactly one node with no inbound edge); every node must be
  reachable; every conclusion reached must be defined, and vice versa. `lore
  health --scope rites` enforces all of this.
- **`use:` takes the shared step's bare id**, never a path. Keep judgment out of
  the shared step — branch here, in the rite.
- Required fields: `id, title, summary, trigger, nodes, conclusions`. A rite must
  NOT carry `related`/`binds` — the codex points at rites (`rites:`), never the
  reverse.
