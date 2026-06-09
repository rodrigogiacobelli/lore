---
name: new-rite
description: Draft, create, or update a rite — and link the codex docs it governs
---

# New Rite

Create or update a Lore rite. A **rite** is procedural memory — the *how-to* counterpart of the codex. The codex stores semantic, factual knowledge ("what is true"); a rite stores a procedure ("how to do or diagnose recurring task X"). Rites are not documentation and not templates that spawn work (that is a doctrine) — they are organised know-how any agent reads and follows in the moment.

A rite has two shapes. A **main rite** (`.lore/rites/main/`) is a node-graph that carries the judgment: branching nodes (`do`/`use` + `then`, `if`/`goto` forks) ending in typed `conclusions`. A **shared step** (`.lore/rites/shared/`) is a pure, reusable procedure — `id`, `title`, `do` only, single exit, no branching, no conclusions — that main rites pull in with `use:`. Judgment lives in the rite; procedure lives in the step.

## Steps

### 1. Decide the shape

- **Branches on a condition, weighs a result, or ends in one of several outcomes?** It is a **main rite**.
- **A single reusable procedure with one exit — one platform, one screen, one query — that reports a fact and never decides?** It is a **shared step**.

A main rite composes shared steps with `use:`. If a procedure repeats across rites, factor it into a shared step.

### 2. Read the design guide and the matching template

```
lore artifact show rite-design
```

`rite-design` is the authoring guide — the two shapes, identity/grouping/retrieval rules, and a full worked example. Then read the skeleton for the shape you chose:

```
lore artifact show rite-main          # main rite skeleton
lore artifact show rite-shared-step   # shared step skeleton
```

Check what already exists so you reuse shared steps rather than duplicate them:

```
lore rite list
lore rite list --shared
lore rite show <similar-rite>
```

### 3. Draft the YAML

**Main rite** — `id, title, summary, trigger, nodes, conclusions`:
```yaml
id: <bare-unique-id>      # globally unique across the whole tree; folder is NOT identity
title: <short human title>
summary: <one line outcome — shown in `lore rite list`, read by the AI matcher>
trigger: <prose cue — the situation in which an agent reaches for this rite>

nodes:
  - id: <entry-node>      # the one node nothing routes to
    use: <shared-step-id> # bare id — Lore finds the step anywhere under shared/
    then: <next-node>
  - id: <a-decision>      # judgment lives in the rite, never in a shared step
    do: <what to weigh>
    then:
      - if: <condition A>
        goto: <node-or-conclusion-key>
      - if: <condition B>
        goto: <node-or-conclusion-key>

conclusions:
  <conclusion-key>:
    audience: <who acts on this outcome>
    response: <what the outcome is / what to tell that audience>
```

**Shared step** — `id, title, summary, do` only:
```yaml
id: <bare-unique-id>      # globally unique across ALL rites; folder is not identity
title: <short human title>
summary: <one line — what this step does (required, like every entity); no trigger>
do: |
  <Plain instructions for the one procedure this step performs.>
  <Say exactly what to read/click/run and what to report back. Keep it small.>
```

Rules to hold while drafting:
- **`id` is bare and globally unique** across every main rite and shared step in any subfolder — like a codex id. The subfolder is cosmetic and only sets the `group`.
- **`use:` names a bare id**, never a path. Discovery is recursive.
- **Main rite well-formedness:** exactly one entry node; every node reachable; every `then`/`goto` points at a node id or a conclusion key (no dangles); every conclusion reached is defined and every defined conclusion is reachable.
- **Shared step is pure:** single exit, no `nodes`/`then`/`goto`/`use`/`conclusions`. If you want to branch, that belongs in the consuming main rite.
- **No outbound links.** A rite must NOT carry `related`/`binds` — the codex points at rites, never the reverse (ADR-014).

### 4. Create or update

Group small steps by platform/system (`portal/`, `backoffice/`, `db/`) so they stay browsable — `--group` is optional (root if omitted).

Create — `new` scaffolds, then `edit --from` puts the body in:

```
lore rite new <id> [--shared] [--group <path>]
lore rite edit <id> [--shared] --from <temp-file>
```

Update an existing rite — `edit` resolves by bare id across the whole tree:

```
lore rite edit <id> [--shared] --from <temp-file>
```

Add `--shared` for a shared step on both commands — it selects the schema and subfolder.

### 5. Validate

```
lore rite show <id>
```

Confirms the rite renders and every `use:`-referenced shared step inlines flat into one document. Then audit reference integrity, graph well-formedness, orphan asymmetry, and global id uniqueness:

```
lore health --scope rites
```

### 6. Link from the codex (optional but encouraged)

Linking is one-directional, codex → rite (ADR-014): a codex doc names the rites it governs in its `rites:` frontmatter field; rites carry no back-link. Identify the codex doc(s) this rite supports and add the rite's id:

```
lore codex edit <doc-id> --add rites=<rite-id>
```

Then re-run `lore health` to confirm no dangling `rites:` reference. The link is a secondary discovery path — agents still find the rite via `lore rite list`, so an unlinked main rite is fine (not a health warning).

## Notes

- **Main rite vs doctrine:** a doctrine is an upstream template that *spawns* quests and missions (planning); a rite is procedural knowledge any agent follows to *do or diagnose* a task at execution time. Don't conflate them.
- **Retrieval is AI-as-matcher only.** Lore never matches a situation to a rite. Write `trigger` (a clear prose cue) and `summary` (a one-line outcome) for the agent who scans `lore rite list` and picks the fit — those two lines are the entire retrieval surface.
- **Orphan asymmetry:** an unused shared step (no main rite `use:`es it) is a health warning; an unlinked main rite (no codex `rites:` points to it) is NOT flagged.
