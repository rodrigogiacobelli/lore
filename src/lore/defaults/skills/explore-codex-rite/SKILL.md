---
name: explore-codex-rite
description: Research a question across both the codex (what-is-true) and rites (how-to), traversing whichever surface fits
---

# Explore Codex + Rite

Research a question that may need both kinds of project memory at once. Lore stores knowledge on two surfaces:

- **Codex** — semantic, factual knowledge: *what is true*. A graph of typed markdown docs you search, map, and traverse. (Standalone skill: `explore-codex`.)
- **Rites** — procedural memory: *how to do or diagnose X*. Node-graph main rites that carry judgment, composed from pure shared steps. (Standalone skill: `explore-rite`.)

Most real questions are one or the other; some need both — "what is our refund policy *and* how do I issue one", "what does this subsystem do *and* how do I diagnose it when it fails". This skill decides which surface to hit, traverses each, and stitches the answer together.

## Pick the surface

| The question is about… | Surface | Entry command |
|------------------------|---------|---------------|
| A fact, definition, design, constraint, or how something works | Codex | `lore codex search <kw>` |
| A vocabulary term | Glossary | `lore glossary search <kw>` |
| The code a doc governs (or the docs a file governs) | Impacts | `lore impacts <id-or-path>` |
| A step-by-step procedure to *do* or *diagnose* a recurring task | Rite | `lore rite list` / `lore rite search <kw>` |

A "what / why / where" question is codex. A "how do I" question is a rite. When a question carries both, run both — they are complementary, not alternatives.

## The bridge: codex → rite

Links point **one way**: a codex doc names the rites it governs in its `rites:` frontmatter field; rites carry no links back. So the natural flow is codex-first when you have one — find the governing doc, read it for the *what*, then follow its `rites:` field to the *how*.

## Steps

### 1. Classify and enter

Decide what the question is really asking. If it needs facts, start in the codex; if it needs a procedure, start in the rites; if both, start in the codex (it bridges to rites, not the reverse).

Codex entry:
```
lore codex search <keyword>
lore codex show <id1> <id2> ...
```

Rite entry:
```
lore rite list                 # scan triggers + summaries, match yourself
lore rite search <keyword>     # keyword-browse main rites
```

### 2. Traverse the codex for the *what*

From the most relevant doc, walk its neighbours and pull in implementation when needed:

```
lore codex map <id>            # neighbours; --full for bodies, --depth/-out/-in to tune
lore codex chaos <id> --threshold 50   # serendipitous discovery
lore impacts <codex-id>        # the code files the doc governs
```

Read enough to answer the factual half of the question.

### 3. Cross to the rites for the *how*

If the relevant codex doc has a `rites:` field, those are the procedures attached to that knowledge — read them:

```
lore rite show <id>            # full node-graph, shared steps inlined
```

If no codex doc bridged you, match a rite directly by scanning triggers in `lore rite list` — retrieval is AI-as-matcher, so pick the rite whose `trigger` fits your situation. Follow the nodes to a typed `conclusion`; do not improvise past it.

### 4. Answer, citing both surfaces

Stitch the factual and procedural halves into one answer. Cite what you used — codex IDs for facts (`per lore codex show ...`) and rite IDs for procedures (`per lore rite show ..., conclusion: ...`). If a surface lacks the answer, say so for that half rather than inferring across the gap — and if a needed procedure has no matching rite, flag it as a candidate for the `new-rite` skill.
