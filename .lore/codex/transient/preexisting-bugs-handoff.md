---
id: preexisting-bugs-handoff
title: Pre-existing bugs surfaced during the interactive-init quest — handoff
summary: Three defects found while building interactive lore init that predate it and were deliberately left unfixed, with reproductions verified against the branch head, plus one behaviour a product ruling reclassified as intended. Bug 1 is now fixed; the resolver pattern it called for lives in doctrine.py.
related:
  - interactive-init-prd
  - conceptual-workflows-health
  - conceptual-workflows-lore-init
---

# Pre-existing bugs surfaced during the interactive-init quest — handoff

Quest `q-3c9c` built interactive `lore init` and, through a code review and eight rounds of adversarial testing, surfaced three defects that belong to code the quest did not introduce. Each was left unfixed on purpose: fixing unrelated code inside a feature branch hides the change from the reviewer who would otherwise judge it on its own terms.

Every reproduction below was re-run against the branch head and still fails. Each item is sized for its own quest.

---

## 1. `lore health --scope knights` — FIXED

**Status:** closed. The Knight entity is removed outright: there is no `knights` scope, no `_check_knights`, no `_find_knight`, and no `missions.knight` column.

The pattern the bug called for now lives in `doctrine.py` as a deliberate resolver pair. `_find_doctrine_dir` is strict — a name that came from a user refuses a path separator outright — while `_resolve_doctrine_mission` is permissive about the one separator a *stored* `<doctrine-id>/<mission-id>` reference legitimately carries, and refuses an absolute path, any `..` segment, and any shape that is not exactly two segments. `health.py` imports `_resolve_doctrine_mission` rather than re-deriving the question, so the two paths cannot disagree about what a valid reference is.

See `ref-lore_doctrine-module` and `decisions-033-unresolvable-reference-is-silent-on-read`.

---

## 2. A custom field declared only in a source overlay is never coerced

**Severity:** medium — a project cannot use a typed custom field on source documents at all.

### What happens

An overlay at `.lore/custom-schemas/codex-source-frontmatter.yaml` declaring an integer field validates correctly, but `--set` never coerces the value, so the string reaches the validator and fails:

```
lore codex edit mysrc --set review_year=2026
  '2026' is not of type 'integer'
```

The same field declared in `codex-frontmatter.yaml` works, which is what makes the failure look arbitrary.

### Why

At `src/lore/cli.py:1653` the coercion path resolves its schema as:

```python
"codex-frontmatter" if kind == "codex" else raw_schema_kind
```

and immediately below sets `coerce_root = project_root if kind == "codex" else None`. The comment reads "Codex is the only overlay-eligible kind" — but ADR-019 fixes overlay scope at canonical codex documents **and the sources layer**, stopping only at `transient/`. Sources are overlay-eligible, so the assumption is wrong. With `coerce_root` `None`, the merged schema is never consulted and the raw string is passed through, while validation resolves the real doc-type kind and rejects it.

### Reproduce

```
lore init --agent none --yes
mkdir -p .lore/custom-schemas
printf 'properties:\n  review_year:\n    type: integer\n' > .lore/custom-schemas/codex-source-frontmatter.yaml
# create a doc under sources/ with id mysrc, then:
lore codex edit mysrc --set review_year=2026
```

### Fix direction

Resolve the coercion schema from the document's own kind, and pass `project_root` for every overlay-eligible kind rather than for `codex` alone. ADR-019 already names the eligible set; read it from there instead of restating it in a conditional.

