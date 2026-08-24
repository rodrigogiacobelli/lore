---
id: decisions-021-health-reports-are-ephemeral-by-default
title: "ADR-021: Health reports are ephemeral by default; persistence is a project config policy"
summary: >
  ADR making the markdown report `lore health` produces a by-product a project
  opts into rather than a file every run leaves behind. Persistence is governed
  by the root-level `health-report-retention` key in `.lore/config.toml` —
  `none` (the default, and the fallback for every failure mode), `latest` (keep
  exactly one report), or `all` (keep every report). The policy is resolved
  inside `health_check`, never at the CLI seam, and `lore health` carries no
  retention flag. Pruning is confined to `health-*.md` sitting directly in
  `.lore/codex/transient/`, is fail-soft, and never runs under `none`.
binds:
  - src/lore/config.py
  - src/lore/health.py
  - src/lore/init.py
related:
  - codex
  - conceptual-workflows-health
  - conceptual-workflows-lore-init
  - conceptual-workflows-glossary
  - tech-arch-initialized-project-structure
  - decisions-011-api-parity-with-cli
  - decisions-013-toml-for-config-yaml-for-glossary
  - decisions-019-overlay-scope-stops-at-transient
---

# ADR-021: Health reports are ephemeral by default; persistence is a project config policy

## Context

`.lore/codex/transient/` is the in-flight layer, and its content class is
defined by one test: a document there is safe to delete once the feature it
belongs to has shipped and its facts have moved into a stable layer. PRDs, tech
specs, context maps, and user stories all pass that test.

`lore health` wrote one timestamped `health-<timestamp>.md` into that layer on
every invocation, and nothing removed them. A health report belongs to no
feature, so no feature's completion ever made one deletable. A project that ran
the audit in a pre-commit hook, in CI, or once per agent dispatch accumulated
one file per run, and the layer whose whole purpose is to stay small filled
with the output of the command that audits it. Every accumulated report was
also a codex document — walked by the codex scan, counted by `lore codex list`,
and returned by `lore codex search`, pushing the working documents an agent
actually needs further down the result.

Nothing about the file was load-bearing. The console table, `--json`, and the
returned `HealthReport` each already carried every issue the file carried.

Key forces:

- **Force 1 — a report is a by-product, not a working document.** The in-flight
  layer is defined by a deletion test tied to a feature shipping. The audit's
  own output has no feature behind it, so it never satisfies the test that
  governs everything else in the layer.
- **Force 2 — three channels already carry the result.** Console output,
  `--json`, and `HealthReport` are the interfaces every caller uses. The file is
  a fourth copy of the same data, and the only one that outlives the run.
- **Force 3 — persistence is a project preference, not a Lore-wide truth.** A
  project that diffs successive audits, or archives them as a CI artefact,
  wants the file on disk. A project driving agents in a loop wants it gone.
  Neither answer is correct for the other project.
- **Force 4 — a per-run flag is the wrong seam.** ADR-011
  (`decisions-011-api-parity-with-cli`) requires that no behaviour a caller
  depends on live only in the CLI. A `--retention` flag would put the policy
  where a Python caller of `health_check` has to reimplement it, and would ask
  the operator to retype a standing preference on every invocation.

## Decision

**The report is opt-in, and a project opts in through `.lore/config.toml`.**

1. **`health-report-retention` governs persistence.** It is a root-level string
   key in `.lore/config.toml` — TOML per ADR-013
   (`decisions-013-toml-for-config-yaml-for-glossary`) — with three tokens:
   - `none` — `lore health` writes no file. Console, `--json`, and
     `HealthReport` output are unaffected. Reports already on disk stay where
     they are.
   - `latest` — every `health-*.md` sitting directly in
     `.lore/codex/transient/` is unlinked, then the report for this run is
     written. Exactly one report survives an audit.
   - `all` — the report is written and nothing is pruned.
2. **`none` is the default and the fallback for every failure mode.** A missing
   config file, unparseable TOML, a value of the wrong type, and a value
   outside the token set each resolve to `none`. A missing file is silent;
   the other three each emit one stderr warning under the existing
   at-most-one-config-warning-per-process latch.
3. **The policy is resolved inside `health_check`, not the CLI.** `lore health`
   calls `health_check(write_report=True, timestamp=...)` and formats the
   result. Per ADR-011, a Python caller reaching `health_check` directly gets
   the identical policy without replicating a line of it.
4. **`lore health` carries no retention flag.** Its options, output, and exit
   codes are what they were; the project config decides the rest.
5. **An explicit `retention=` argument overrides the config, and an unknown
   token raises.** `health_check(..., retention="latest")` ignores the config
   key. A token outside the set raises
   `ValueError("Unknown retention: 'x'. Valid values: none, latest, all.")`
   unconditionally, mirroring how an unknown `scope` token is handled — an
   argument a programmer typed is a programming error, while a value a project
   wrote into a config file is a user error that falls soft.
6. **Pruning is narrow and fail-soft.** `latest` matches `health-*.md` directly
   under `.lore/codex/transient/` — not recursively, and not any other document
   in the layer. An unlink that fails is skipped, so an undeletable file never
   aborts an audit.
7. **Lore never removes a report the caller did not ask it to remove.** Under
   `none` the pruning path does not run, so adopting the default leaves an
   existing pile of reports untouched for a human to delete.

## Rationale

- **Absence is the honest default because the file duplicates output the caller
  already holds.** Writing it costs a project a growing directory and buys
  nothing the same run printed. A default that costs something must earn it,
  and this one cannot.
- **A standing preference belongs in config, not in a flag.** Whether a project
  keeps audit history is decided once, by whoever set the project up. A flag
  re-asks that settled question on every invocation and gets it wrong whenever
  someone forgets to pass it.
- **Resolving the policy in `health_check` keeps one implementation.** ADR-011
  makes the CLI a formatting wrapper. Reading the config key inside
  `health_check` means Realm, a script, and `lore health` all get the same
  answer, and the behaviour is testable without a CLI runner.
- **`latest` is the only bounded-history mode worth having.** It answers "what
  did the last audit say" — the question a diff or a CI artefact asks — at a
  fixed cost of one file. A larger bound answers no question that re-running a
  cheap audit does not answer better.
- **Fail-soft throughout, because an audit must not manufacture failures.**
  `lore health` exists to report on a project's state. A config typo, or one
  stale report with hostile permissions, must degrade to the default and let
  the audit finish rather than turn the diagnostic into the defect.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Keep writing every report and document a cleanup step** | This is the state that produced the problem. A cleanup step nobody runs is not a retention policy, and the accumulation is monotonic — the longer a project uses the audit, the worse its transient layer gets. |
| **A `--no-report` or `--retention` flag on `lore health`** | Puts the policy at the CLI seam that ADR-011 exists to keep empty, forcing every Python caller to reimplement it. It also converts a project-level preference into a per-invocation decision, which is the wrong grain and the wrong person's choice. |
| **A boolean key, `write-health-report = true/false`** | Two states cannot express three. "Keep exactly one" would need a second key, and two coupled booleans admit a meaningless combination. One constrained string keeps the states enumerable and the invalid ones unrepresentable. |
| **Keep the last N reports, or expire them by age** | Needs a count or a duration key plus time arithmetic, all to bound a file three other channels already duplicate. `latest` is the N=1 case; no reader has a use for N=5 that re-running the audit does not serve. |
| **Ship `latest` as the default instead of `none`** | Makes a fresh project's first audit delete files it never asked Lore to manage, and still leaves a report behind that nobody requested. A default that writes and deletes is harder to reason about than one that does neither. |
| **Delete pre-existing reports when the policy is `none`** | An audit that removes user files as a side effect of reading them is a destructive read. `none` means "write nothing", not "clean up"; the operator who accumulated the reports deletes them. |
| **Write reports outside the codex, e.g. under `.lore/reports/`** | `lore oracle` owns `.lore/reports/` and wipes the directory on every run, so a health report there is destroyed by an unrelated command. Relocating the file also sidesteps the actual question, which is whether it should exist at all. |
| **A `[health]` TOML table instead of a root-level key** | ADR-013 chose a flat, human-edited key-value shape for `.lore/config.toml` precisely to avoid nesting. One setting does not justify a table, and a table sets a precedent that splits the file's namespace for every setting after it. |

## Consequences

**Easier:**

- The in-flight layer holds in-flight working documents and nothing else, so
  `lore codex list` and `lore codex search` return the documents an agent came
  for.
- A project that wants audit history opts in with one line of config, and gets
  a bounded pile (`latest`) or an unbounded one (`all`) by naming which.
- `health_check` is fully exercisable without touching disk: the default is a
  read-only audit that never consults the config.

**Harder:**

- A caller that expected a report file after every run has to set
  `health-report-retention` explicitly. Nothing in the console output announces
  that the file was skipped.
- `.lore/config.toml` holds more than one setting, so the
  one-warning-per-process latch means a warning about one key suppresses the
  warning about the other within the same run.
- Under `latest`, the prune runs before the write, so a write that fails after
  a successful prune leaves the layer with no report at all.

## Constraints Imposed

1. **`none` is the default, and every failure mode resolves to it.** Changing
   the default is a breaking contract change and requires editing this ADR in
   place.
2. **Policy resolution lives in `health_check`.** No caller — `lore health`
   included — reads `health-report-retention` and decides for itself. A second
   reader of that key is a duplicate implementation and an ADR-011 violation.
3. **`lore health` carries no retention flag.** Adding one reopens the seam this
   ADR closed.
4. **Pruning stays confined to `health-*.md` directly under
   `.lore/codex/transient/`.** Non-recursive, and no other document in the layer
   is ever a candidate for deletion.
5. **The token set is `none`, `latest`, `all`.** Adding a token is additive.
   Removing or renaming one, or changing which token is the default, is a
   breaking contract change.
6. **An invalid config value falls soft; an invalid argument raises.** A bad
   `health-report-retention` value warns once and uses the default. A bad
   `retention=` argument to `health_check` raises `ValueError` regardless of
   `write_report`.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-08-24 | accepted | Recorded alongside the `health-report-retention` config key, the `retention` argument on `health_check`, and the `none` default seeded by `lore init`. |
