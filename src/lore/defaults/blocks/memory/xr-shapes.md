---
id: xr-shapes
feature: memory
---
## The two shapes

**Main rite**: `id`, `title`, `summary`, `trigger`, `nodes`, `conclusions`:

```yaml
id: <bare-unique-id>      # globally unique across the tree; the folder is not identity
title: <short human title>
summary: <one line outcome, read by the AI matcher>
trigger: <prose cue: the situation in which an agent reaches for this rite>

nodes:
  - id: <entry-node>      # the one node nothing routes to
    use: <shared-step-id> # bare id; the step is found anywhere under shared/
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

**Shared step**: `id`, `title`, `summary`, `do` only:

```yaml
id: <bare-unique-id>
title: <short human title>
summary: <one line: what this step does; no trigger>
do: |
  <Plain instructions for the one procedure this step performs.>
  <Say exactly what to read, click or run, and what to report back.>
```
