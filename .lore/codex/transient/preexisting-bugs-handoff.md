---
id: preexisting-bugs-handoff
title: Pre-existing bugs surfaced during the interactive-init quest — handoff
summary: Three defects found while building interactive lore init that predate it and were deliberately left unfixed, with reproductions verified against the branch head, plus one behaviour a product ruling reclassified as intended.
related:
  - interactive-init-prd
  - conceptual-workflows-health
  - conceptual-workflows-lore-init
---

# Pre-existing bugs surfaced during the interactive-init quest — handoff

Quest `q-3c9c` built interactive `lore init` and, through a code review and eight rounds of adversarial testing, surfaced three defects that belong to code the quest did not introduce. Each was left unfixed on purpose: fixing unrelated code inside a feature branch hides the change from the reviewer who would otherwise judge it on its own terms.

Every reproduction below was re-run against the branch head and still fails. Each item is sized for its own quest.

---

## 1. `lore health --scope knights` dies whenever a doctrine-driven quest is open

**Severity:** high — the scope is unusable for the whole duration of any quest, which is exactly when a health check matters.

### What happens

```
lore health
  ERROR  knights  knights  scan_failed: Invalid knight name: path separators not allowed
```

`lore health` still completes and other scopes still report, but the knights scope produces nothing.

### Why

`_check_knights` (`src/lore/health.py:396`) reads the `knight` field off every open mission and passes it to `_find_knight` (`src/lore/knight.py:100`), which rejects any name containing a path separator as a traversal guard:

```python
if "/" in name or "\\" in name:
    raise ValueError("Invalid knight name: path separators not allowed")
```

Doctrines write grouped knight names — `tdd-feature/defaults-reviewer.md`, `feature-implementation/scout.md` — and `lore new mission -k` accepts them without complaint. So any open mission created from a doctrine breaks the scan. `lore knight list` and `lore knight show` resolve the same grouped names correctly, so the two paths disagree about what a valid knight name is.

`src/lore/health.py:293` calls `_find_knight` the same way and is worth checking alongside it.

### Reproduce

```
lore new mission -q <quest> "x" -k tdd-feature/defaults-reviewer.md -T knight
lore health --scope knights
```

The error clears when the mission closes, because `list_missions(include_closed=False)` stops returning it — which is why the bug is invisible between quests and reliable during one.

### Fix direction

Resolve grouped names the way `lore knight show` does. The traversal guard is protecting against an untrusted path, but a knight name that came out of the database was written by a doctrine, not by an attacker. Either resolve the group before the guard, or give `_check_knights` a resolver that accepts group-qualified ids.

**Introduced:** `a44efaa` ("feat: API and CLI parity"), which predates this quest's first commit.

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

