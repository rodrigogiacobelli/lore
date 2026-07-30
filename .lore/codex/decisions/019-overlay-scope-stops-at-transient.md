---
id: decisions-019-overlay-scope-stops-at-transient
title: 'ADR-019: Custom-schema overlays govern canonical codex docs and sources, never
  the transient subtree'
summary: ADR fixing the blast radius of a .lore/custom-schemas/<kind>.yaml overlay to
  canonical codex documents and the sources/ layer. Transient working docs under
  .lore/codex/transient/ validate against the packaged schema alone at every seam
  (lore health, lore codex new, lore codex edit), because they are scratch artefacts
  of an in-flight feature — including the reports lore health writes itself — and must
  never be governed by project-authored required fields.
related:
- decisions-018-overlays-are-path-discovered-config
- tech-arch-schemas
- conceptual-workflows-health
- conceptual-workflows-codex
---

# ADR-019: Custom-schema overlays govern canonical codex docs and sources, never the transient subtree

## Context

ADR-018 (`decisions-018-overlays-are-path-discovered-config`) classed a
`.lore/custom-schemas/<kind>.yaml` overlay as user-owned, path-discovered project
config. It settled *what an overlay is*. It did not settle *which documents an
overlay governs*.

The shipped implementation answered that question implicitly: every file matched
by the codex entity glob. The codex glob is `.lore/codex/**/*.md`, which includes
`.lore/codex/transient/` — the in-flight working subtree that holds PRDs, tech
specs, context maps, user stories, and the markdown reports `lore health` writes
into `codex/transient/health-<timestamp>.md` on every run.

That made the feature self-defeating. Declaring one required custom field:

- turned every previously written health report into a `schema` error, and made
  each subsequent `lore health` run write one more failing report — the audit
  manufactured its own failures, monotonically;
- made `lore codex new <name> --group transient` refuse to create the PRD or
  tech spec a doctrine's spec pipeline depends on, because the working doc did
  not carry a governance field that has no meaning for scratch work.

The codex link-integrity pass already skipped `transient/` (broken-link,
island-node, and source-direction checks all exclude it). Schema validation did
not. The boundary existed in one half of `lore health` and not the other, and
nothing recorded which half was intentional.

## Decision

An overlay's blast radius is **canonical codex documents and the `sources/`
layer**. Documents under `.lore/codex/transient/` are **out of overlay scope** and
validate against the **packaged** schema alone.

Concretely:

- `codex-frontmatter` overlays apply to canonical docs; `codex-source-frontmatter`
  overlays apply to `sources/*`; neither applies under `transient/`.
- The exemption holds at **every** seam that validates a codex doc — the
  `lore health` schema scan, `lore codex new`, `lore codex edit -f`, and
  `lore codex edit --set/--unset/--add/--remove`. One rule, no seam-specific
  behaviour.
- Transient docs are exempt from the **overlay**, not from **validation**. The
  packaged schema still applies in full: `id`, `title`, and `summary` are still
  required and `additionalProperties` is still `false`. A transient doc missing
  `summary` is still a health error.
- Because the packaged schema keeps `additionalProperties: false`, a transient
  doc that *carries* a declared custom key is rejected as an unknown property.
  Custom fields are canonical-codex governance; a scratch doc does not get to
  opt in to them.
- A malformed overlay never blinds the transient subtree. The subtree never
  consulted the overlay, so its packaged validation still runs while the
  canonical kind reports its single `scan_failed`.

## Rationale

**Transient docs are scratch, and governance fields are not.** The codex root
index defines `transient/` as "in-flight working documents for the current
feature cycle, deleted when the feature ships." A custom field exists to record
something a team wants to know about its *permanent* knowledge — an owner, a
review date, a classification. Demanding it on a document that will be deleted
in a week is cost with no payoff, and it taxes exactly the moment a project is
least able to pay it: mid-feature, when the spec pipeline is writing.

**A health audit must not manufacture its own failures.** `lore health` writes
its report into the subtree it audits. Any rule the report's own frontmatter
cannot satisfy makes the exit code a function of how many times health has been
run before. An audit whose result depends on its own history is not an audit.
Excluding the subtree the audit writes into is the only fix that does not
constrain what a project may put in an overlay.

**The boundary already existed; this records it and completes it.** The codex
link-integrity checks skip `transient/` today. Extending the same boundary to
schema overlays makes `transient/` mean one thing across all of `lore health`
instead of two.

**Exempt from the overlay, not from validation.** Dropping transient docs from
schema validation entirely would let a working doc lose its `id` or `summary`
silently — and transient docs are addressable (`lore codex show <prd-id>`,
`lore codex search`), so the packaged contract still has to hold. The exemption
is scoped to the project-authored layer, which is the layer that caused the
problem.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Apply overlay `properties` to transient docs but drop overlay `required`** | Custom fields would be optional-but-allowed in scratch docs. Softer, but it makes an overlay mean two different schemas depending on the path, and it invites custom governance metadata into documents that are deleted on ship. The line is cleaner where "custom fields are canonical-only" is a single sentence. |
| **Exempt only the `health-*.md` reports** | Fixes the self-referential failure and nothing else. `lore codex new --group transient` would still refuse to create a PRD, and the exemption would hinge on a filename prefix — a rule no author could predict. |
| **Make `lore health` skip `transient/` in the schema scan only** | Leaves the write path (`codex new` / `codex edit`) enforcing a rule the audit does not, so a doc that cannot be created is also never flagged. Scope must be identical at every seam or the two disagree. |
| **Drop transient docs from schema validation entirely** | Transient docs are retrievable by id; losing the packaged `id`/`title`/`summary` guarantee would break `lore codex show` and `search` for exactly the documents a feature cycle depends on. |
| **Let each project configure the scope** | Requires the config surface ADR-018 deliberately rejected. Overlays are discovered by filename with zero config; a scope key would be the first exception. |

## Consequences

**Easier:**
- Declaring a required custom field is now a safe, self-contained act: it
  constrains permanent codex knowledge and leaves the feature pipeline and
  `lore health`'s own output untouched.
- `transient/` means one thing across the whole audit — excluded from link
  integrity and from project-authored schema rules alike.

**Harder:**
- A project that genuinely wants a custom field on a working doc cannot have it;
  the doc must graduate out of `transient/` first. This is the intended
  trade-off — see the first row of Alternatives.
- Every future codex-validating seam must route through the shared
  `codex._overlay_root` helper rather than passing `project_root` straight into
  `validate_entity`. A seam that forgets reintroduces the bug silently.

## Constraints Imposed

1. **One scope rule, all seams.** Any code path that validates codex frontmatter
   resolves its overlay root through `codex._overlay_root(project_root, filepath)`,
   which returns `None` for paths under `.lore/codex/transient/`. No seam
   open-codes the decision.
2. **Transient docs stay packaged-validated.** The exemption removes the overlay,
   never the packaged schema. `lore health` still errors on a transient doc with
   broken or incomplete frontmatter.
3. **Custom keys are rejected under `transient/`.** The packaged
   `additionalProperties: false` is not relaxed for the transient subtree.
4. **The scope is fixed, not configurable.** Consistent with ADR-018, overlays
   carry no configuration surface; the transient boundary is not a project
   setting.
