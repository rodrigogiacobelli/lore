# Reference — recording a procedure as a rite

Read this when the knowledge is procedural: how to do or diagnose a recurring
task. A rite is not documentation and not a template that spawns work — that is
a doctrine. It is organised know-how an agent reads and follows in the moment.

## Pick the shape

A rite has two shapes.

- **Main rite** (`.lore/rites/main/`) — a node-graph that carries the judgment:
  branching nodes routed by `then` / `if` / `goto`, ending in typed
  `conclusions`. Choose it when the procedure weighs a result, branches on a
  condition, or ends in one of several outcomes.
- **Shared step** (`.lore/rites/shared/`) — a pure, reusable procedure with a
  single exit: `id`, `title`, `summary`, `do` and nothing else. No branching, no
  trigger, no conclusions. Choose it for one platform, one screen, one query
  that reports a fact and never decides.

A main rite composes shared steps with `use:`. When a procedure repeats across
rites, factor it into a shared step.

## Read the design guide and the skeleton

```
lore artifact show rite-design          # the authoring guide, with a worked example
lore artifact show rite-main            # main-rite skeleton
lore artifact show rite-shared-step     # shared-step skeleton
```

## The two shapes

**Main rite** — `id`, `title`, `summary`, `trigger`, `nodes`, `conclusions`:

```yaml
id: <bare-unique-id>      # globally unique across the tree; the folder is not identity
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

**Shared step** — `id`, `title`, `summary`, `do` only:

```yaml
id: <bare-unique-id>
title: <short human title>
summary: <one line — what this step does; no trigger>
do: |
  <Plain instructions for the one procedure this step performs.>
  <Say exactly what to read, click or run, and what to report back.>
```

## Rules to hold while drafting

- **`id` is bare and globally unique** across every main rite and shared step in
  every subfolder, like a codex id. The subfolder is cosmetic and only sets the
  display `group`.
- **`use:` names a bare id**, never a path. Discovery is recursive.
- **Main-rite well-formedness:** exactly one entry node; every node reachable;
  every `then` / `goto` points at a node id or a conclusion key; every
  conclusion reached is defined and every defined conclusion is reachable.
- **A shared step is pure:** single exit, no `nodes` / `then` / `goto` / `use` /
  `conclusions`. Branching belongs in the consuming main rite.
- **No outbound links.** A rite carries no `related` and no `binds`. The codex
  points at rites; rites never point back.
- **Retrieval is AI-as-matcher.** Lore never matches a situation to a rite.
  `trigger` and `summary` are the entire retrieval surface — write them for the
  agent scanning the list.

## Applying the change

Group small steps by platform or system (`portal/`, `backoffice/`, `db/`) so the
tree stays browsable. The group is optional; omit it for the root.

<!-- lore:access cli -->
**Create** — `new` scaffolds, `edit --from` puts the body in:

```
lore rite new <id> [--shared] [--group <path>]
lore rite edit <id> [--shared] --from <temp-file>
```

**Edit** — `edit` resolves a bare id across the whole tree:

```
lore rite edit <id> [--shared] --from <temp-file>
```

**Delete:**

```
lore rite delete <id>
```

`--shared` selects the shared-step schema and subfolder on `new` and `edit`.
`delete` resolves a bare id across both trees, so it accepts the flag for
parity and ignores it.

**Confirm it renders**, with every `use:` step inlined flat into one document:

```
lore rite show <id>
```
<!-- lore:access end -->
<!-- lore:access native -->
Write the YAML yourself under `.lore/rites/main/<group>/<id>.yaml`, or
`.lore/rites/shared/<group>/<id>.yaml` for a shared step. Create the group
directory if it does not exist; delete the file to retire the rite.

Two things the CLI would have done that you now own:

- **Schema selection.** A main rite and a shared step validate against different
  schemas, and the subfolder is what picks one. A shared step written under
  `main/` fails validation.
- **Id uniqueness across the whole tree.** Grep both trees for the id before you
  write, because the folder is not part of identity.

Read the rite back afterwards the way the next agent will: your file tool does
not inline the `use:` steps, so follow each bare id to its file under
`.lore/rites/shared/` and read the procedure end to end. A step that resolves to
nothing is a `dangling_use`, and `lore health --scope rites` below is what names
it.
<!-- lore:access end -->

## Validate

```
lore health --scope rites
```

This audits reference integrity, graph well-formedness, orphan asymmetry and
global id uniqueness. Fix every error before declaring done.

## Link it from the codex

Linking runs one way, codex → rite: a codex document names the rites it governs
in its `rites:` frontmatter field, and rites carry no back-link. Identify the
document this rite supports and add the rite's id to it — see
`references/codex-doc.md` for the edit.

This is a frontmatter-only change; it writes no prose. Re-run `lore health`
afterwards to confirm no dangling `rites:` reference. The link is a secondary
discovery path — an agent still finds the rite by scanning the list — so an
unlinked main rite is fine and is not a health warning. An unused shared step
is.
