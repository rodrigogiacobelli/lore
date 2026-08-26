---
id: interactive-init-tech-spec
title: Interactive lore init and Skill Catalogue Consolidation — Tech Spec
summary: Architecture for an interactive lore init built on a plan/apply split, a
  hash install manifest with a packaged legacy-hash fallback for cross-version reconciliation,
  a seeded agent registry and skill catalogue, and an access-mode block renderer that
  ships one authored source per skill.
type: tech-spec
related:
- interactive-init-prd
- interactive-init-technical-map
- interactive-init-business-map
- conceptual-workflows-lore-init
- conceptual-workflows-health
- conceptual-workflows-error-handling
- conceptual-workflows-json-output
- conceptual-workflows-help
- conceptual-workflows-validators
- conceptual-workflows-schema-migrations
- tech-arch-initialized-project-structure
- tech-arch-agents-md
- tech-arch-source-layout
- tech-arch-api-facade
- tech-arch-project-root-detection
- tech-overview
- technical-test-guidelines
- standards-separation-of-concerns
- standards-single-responsibility
- standards-dependency-inversion
- standards-dry
- standards-public-api-stability
- decisions-001-dumb-infrastructure
- decisions-006-id-references
- decisions-006-no-seed-content-tests
- decisions-008-help-as-teaching-interface
- decisions-010-public-api-stability
- decisions-011-api-parity-with-cli
- decisions-012-multi-value-cli-param-convention
- decisions-013-toml-for-config-yaml-for-glossary
- decisions-017-constrained-flags-use-click-choice
- decisions-020-codex-voice-is-enforced
- decisions-021-health-reports-are-ephemeral-by-default
- ref-lore_cli-commands
- ref-lore_api-core
---

# Interactive `lore init` and Skill Catalogue Consolidation — Tech Spec

**Author:** Architect
**Date:** 2026-08-25
**Supersedes:** _(no draft — this spec is produced directly from the PRD)_
**Input:** `lore codex show interactive-init-prd`

Context maps: `lore codex show interactive-init-technical-map interactive-init-business-map`.

---

## 0. What the PRD Deferred, and How It Is Settled

The PRD names five decisions as Tech Spec territory. Each is answered here, once, with its trace.

| Deferred item | Ruling | Section |
|---|---|---|
| `lore --json init` behaviour, envelope, exit codes | No envelope. The flag stays accepted-and-ignored; exit 0; text output. The permanent exception in `ref-lore_cli-commands` is unchanged. | §3.1 |
| Whether `--dry-run` exists | Yes. It renders the plan and writes nothing. | §3.2 |
| `InitPlan` shape and `plan_init` / `apply_init` signatures | Frozen dataclasses in a new leaf module `lore/initplan.py`; re-exported by name from `lore.api`. | §5 |
| Install manifest and legacy-hash file formats | `.lore/.install-manifest.json` (project, generated) and `src/lore/defaults/legacy-hashes.json` (packaged). | §6 |
| Access-mode injection mechanism | HTML-comment block selection in one authored `SKILL.md` per skill. No template engine, no variables. | §7 |
| Agent-registry data format | `src/lore/defaults/agents.yaml`, loaded from package data at import time. | §8 |

Three constraint collisions the Scout flagged are resolved in §3.1 (`--json`), §8.2 (`click.Choice` against a data-driven registry), and §5.1 (`api.py` purity against `InitPlan`). A fourth, ADR-012 against ADR-017, is settled in §3.4. Four ADRs need in-place amendment and a fifth needs a name correction; §13 lists them and §16 records why each is unavoidable.

---

## 1. Core Architectural Decisions

| Priority | Decision | Choice | Rationale |
|---|---|---|---|
| Critical | Where interactivity sits relative to the core | **Plan/apply split.** `plan_init(...) -> InitPlan` computes; `apply_init(plan) -> InitResult` writes. Prompting exists only in the CLI layer and only to fill `plan_init` parameters. | ADR-011 forbids logic that lives only in the CLI. Every prompt's *effect* is a keyword parameter on `plan_init`, so a Python caller reaches the same behaviour without a terminal. FR-32, FR-33. |
| Critical | `run_init()` compatibility | **Signature unchanged: zero arguments, returns `list[str]`.** It is `apply_init(plan_init())` plus message rendering. | FR-34. Pinned by `tests/e2e/test_api_parity_init.py` (Review-Ledger CHANGED #9). A positional-arg change is a major bump under `standards-public-api-stability`. |
| Critical | Upgrade correctness across any version gap | **Three-way reconciliation** of desired (what the installed Lore version renders) against recorded (the manifest) against on-disk bytes. No per-version migration chain. | FR-31. A migration chain makes every intermediate step permanent code and breaks on skipped releases. One table (§6.4) is correct for any hop, including a downgrade. |
| Critical | Safety of user files | **A path in neither `recorded` nor `desired` is never written, moved, or deleted.** A path in `desired` that Lore did not install is a conflict, not an overwrite. | FR-28 and the PRD reliability NFR "a file the user authored is never lost without the user having agreed to its replacement". §6.5 states the FR-28 reading this requires. |
| Critical | Prompt gate | **`sys.stdout.isatty()`**, evaluated in `cli.py` only. A false result selects defaults silently; it never fails. | FR-9. PRD headless workflow: "Absence of a terminal must select defaults silently rather than fail." |
| Important | One authored source per skill | **Access-mode blocks** marked with `<!-- lore:access cli -->` / `<!-- lore:access native -->` / `<!-- lore:access end -->`, resolved by line-range selection at install time. | FR-19, `standards-dry`. ADR-001 rejected a template engine; block selection has no variables and no expression language. |
| Important | What agent-native mode covers | **Codex documents, rites, and the glossary — nothing else.** Artifacts, knights, doctrines, watchers, quests, missions, board, `codex map`, `codex chaos`, `impacts` and `health` keep the CLI in both modes. | FR-16, FR-17, FR-18, and `decisions-006-id-references`, which this narrows rather than repeals. §7.3 gives the per-entity test. |
| Important | Agent registry as data | **`src/lore/defaults/agents.yaml`**, read through `importlib.resources` at import time, cached with `functools.lru_cache`. | FR-11, FR-12. Package data (not project data) because `lore init` runs where no `.lore/` exists — `tech-arch-project-root-detection` documents init as that special case. |
| Important | Multi-value flag syntax | **Space-separated**, via a `SpaceSeparatedChoice` Click `Option` subclass that keeps `type=click.Choice(...)` intact. | ADR-012 requires `--agent claude codex`; Click 8.3.2 raises `TypeError: nargs=-1 is not supported for options`, and the `--scope` trailing-positional trick cannot serve two multi-value flags on one command. §3.4. |
| Important | Conflict policy tokens | **`skip` (default) and `overwrite`.** No `keep-new`. | PRD FR-27: refused means untouched. PRD Out of Scope rules out migrating an edited skill's content into its successor, which is the only thing a `.new` sibling would serve. |
| Important | Where `InitPlan` lives | **`src/lore/initplan.py`** — a stdlib-only leaf module — re-exported through `api.py`'s "Operational dataclasses" section. | `tech-arch-api-facade` pins zero `def`/`class` in `api.py`. `HealthReport`, `SchemaIssue` and `ImpactsResult` already live in their producing modules, not `models.py`; `models.py` is the entity-record index. A leaf module keeps `reconcile.py` from importing `init.py` (`standards-dependency-inversion`). |
| Deferred | Skills installed at user scope (`~/.claude/skills/`) | Post-MVP | PRD Post-MVP. Project scope is the only scope the manifest can reconcile safely, because a user-scope install is shared across projects and no single project owns it. |
| Deferred | The seven unverified agent conventions | Post-MVP | PRD Out of Scope and FR-13: every shipped registry entry has a verified convention. Adding a row is a data edit (FR-12), so no code changes when they are verified. |
| Deferred | A `lore skill` command group | Rejected | PRD Out of Scope. Skills are seeded files with no retrieval path; `lore health --scope skills` (FR-37) is the audit surface instead. |

---

## 2. Data Architecture

| Decision | Choice | Rationale |
|---|---|---|
| Database | Unchanged — SQLite at `.lore/lore.db`. This feature adds no table, no column, no migration. | Everything the feature stores is file-based. `SCHEMA_VERSION` stays 6. |
| ORM / query layer | Unchanged. `init.py` calls `lore.db.init_database` exactly as today. | No new DB surface. |
| Migration approach | **None for the database.** File-state migration is the reconciliation algorithm in §6.4, which is versionless by construction. | FR-31. |
| Data validation | Three layers. (a) JSON Schema for the packaged registry and catalogue via a new `agents` / `skill-catalogue` schema kind. (b) `click.Choice` at the CLI boundary for `--agent`, `--access`, `--skills`, `--on-existing-agent-file`, `--skills-gitignore`, `--on-conflict` (ADR-017). (c) `lore.validators` for the same token sets so a Python caller is equally safe (ADR-011). | ADR-017 for the exit-2 misuse contract; ADR-011 requires the business function to reject the same tokens. `conceptual-workflows-validators` two-layer model. |
| New config keys | Four root-level keys in `.lore/config.toml`, all `init-` prefixed. §9. | ADR-013 (TOML, flat, forward-compatible), ADR-021's worked precedent for adding a root-level key. |

### 2.1 Hashing

One hash function, one place: `manifest.file_digest(path) -> str` and `manifest.bytes_digest(data: bytes) -> str`, both returning `"sha256:" + hexdigest`. Content is hashed as raw bytes with no newline normalisation, so a CRLF checkout registers as an edit — which is the honest answer, since Lore wrote LF.

The manifest records the hash of the **rendered** file, after access-mode selection. Flipping `--access` therefore changes every affected hash and classifies as a clean overwrite of an unmodified file rather than a phantom user edit. This is the mechanism the PRD's fourth user workflow depends on.

For a marker-section entry (§6.2 `kind: "section"`) the hash covers **the rendered section text between the markers, markers excluded**, not the whole file. A user editing prose outside the markers never registers as a conflict.

---

## 3. API & Communication

| Decision | Choice | Rationale |
|---|---|---|
| API style | Two new callables (`plan_init`, `apply_init`) plus four new validators, five new frozen dataclasses and two enums — thirteen names — all re-exported through `lore.api.__all__`. | ADR-010: `lore.api.__all__` is the contract. Adding names is a minor bump. |
| Error response format | Unchanged. Text errors to stderr; exit 1 for application errors, exit 2 for usage errors. No JSON envelope on `lore init`. | `conceptual-workflows-error-handling`. §3.1. |
| Versioning strategy | Minor bump: `0.9.0` → `0.10.0`, with a `CHANGELOG.md` entry (§11). Thirteen `__all__` names, four new fields on the exported `Config` dataclass, a new hard runtime dependency, and a raised `click` floor. No removals, no signature changes to existing names. | `standards-public-api-stability` semver table; ADR-010 requires `CHANGELOG.md` and `__all__` to move together. |

### 3.1 `lore init` and `--json` — the exception stands

`ref-lore_cli-commands` records `--json` as unsupported on `lore init` and `lore oracle`, and calls the exception permanent. `conceptual-workflows-json-output` records the observable behaviour: "`lore init` always produces text output regardless of the flag." Both stay true.

**Ruling: `lore init` gains no JSON envelope, and `lore --json init` keeps its current behaviour — the flag is accepted, has no effect, and the command prints text and exits 0.**

Three reasons, in order of weight:

1. **The PRD forbids the alternative.** Its headless success criterion is that a caller in a script or CI pipeline "gets the same result as before this feature". Copying the `lore oracle` precedent — reject `--json` with exit 2 — would turn a working `lore --json init` in someone's CI into a hard failure that initialises nothing. `lore oracle` can afford exit 2 because it has always behaved that way; `lore init` has not.
2. **The machine surface already exists and is strictly richer.** `plan_init` returns a typed `InitPlan` with every create, overwrite, removal and conflict, and `apply_init` performs it. Realm imports Lore (`vision-camelot-system`); it does not shell out. A JSON envelope would be a second machine contract over the same information, which `standards-dry` rejects.
3. **The command is now human-first.** ADR-001 is being amended (§13) to admit exactly that command class. A structured envelope for a command whose defining feature is stopping to ask a person is the wrong seam.

**Consequence for `--help`:** ADR-008 makes help the teaching surface, so `lore init --help` states the fact rather than leaving a silently-ignored flag to be discovered:

```
  JSON output is not supported for this command. Use the Python API —
  lore.api.plan_init() returns a typed InitPlan describing every create,
  overwrite, removal and conflict without performing any of them.
```

No ADR is raised and no recorded contract changes.

**One ADR line has to move with it, though.** ADR-001's principle list still reads "**JSON output.** All commands support `--json` for programmatic consumption by agents." That sentence has been false since `lore init` and `lore oracle` were carved out, and `ref-lore_cli-commands` records the carve-out as **permanent**. Declining `--json` here relies on that exception being settled, so leaving ADR-001 asserting the opposite would leave this spec resting on a line the decision record contradicts. ADR-001 is already open for in-place amendment (§13); the amendment narrows the bullet to "every command whose output is data supports `--json`; a command whose output is a side-effecting human report — `lore init`, `lore oracle` — is the recorded permanent exception, and its machine surface is `lore.api`." This records nothing new: it brings the ADR body into line with a contract `ref-lore_cli-commands` already holds.

**And one codex fact is wrong today.** `conceptual-workflows-json-output` states under "Commands That Do Not Support JSON" that "`lore oracle` does not produce JSON output. The `--json` flag is accepted but has no effect", and its failure-mode table says "Oracle with --json → Flag ignored; text output produced → 0". `src/lore/cli.py:352-358` does the opposite: it prints `Error: JSON output is not supported for 'lore oracle'.` to stderr and calls `ctx.exit(2)`. The two commands the exception covers behave differently from each other, and the doc records only one of the behaviours. Reason 1 above turns on precisely that difference, so the correction is a precondition of this ruling rather than a tidy-up — §13 names it.

### 3.2 `--dry-run`

`lore init --dry-run` renders the FR-7 summary and writes nothing. Exit 0.

It earns its place because the `isatty` gate creates a hazard without it: `lore init | tee upgrade.log` is not a terminal, so no prompt fires and the full plan — removals included — applies unseen. `--dry-run` is the only way to read the plan before an upgrade in that situation, and it costs one boolean that maps onto `plan_init` with no `apply_init` call. It traces to FR-32 and to the reliability NFR.

`--dry-run` and `--yes` compose; `--dry-run` wins (nothing is written).

### 3.3 Full flag surface on `lore init`

| Flag | Type | Click default | Resolved default (in `plan_init`) | Prompt it replaces | Persisted |
|---|---|---|---|---|---|
| `--agent ID [ID ...]` | `SpaceSeparatedChoice` over registry ids | `None` | `init-agents`, else none | Q1 agents | `init-agents` |
| `--access {cli,native}` | `click.Choice` | `None` | `init-access-mode`, else `native` | Q2 access mode | `init-access-mode` |
| `--skills FAMILY [FAMILY ...]` | `SpaceSeparatedChoice` over `memory` `machinery` `workflow` `all` `none` | `None` | `init-skill-families`, else all three families | Q3 skill families | `init-skill-families` |
| `--on-existing-agent-file {append,skip}` | `click.Choice` | `"append"` | `"append"` | Q4 existing instruction file | no |
| `--gitignore / --no-gitignore` | flag pair | `None` | `True` | Q5a root `.gitignore` | no |
| `--skills-gitignore {lore-only,none,all}` | `click.Choice` | `None` | `init-skills-gitignore`, else `lore-only` | Q5b installed-skill tracking | `init-skills-gitignore` |
| `--on-conflict {skip,overwrite}` | `click.Choice` | `"skip"` | `"skip"` | Q7 edited-file conflict | no |
| `-y, --yes` | flag | off | — | Q6 summary confirm, and every other prompt | no |
| `--reconfigure` | flag | off | — | forces re-prompting despite recorded answers (FR-10) | no |
| `--dry-run` | flag | off | — | — | no |

**No flag carries a config-derived Click default, and `cli.py` never reads a config key.** A Click default is evaluated at decorator time, where no project root exists; more importantly, ADR-011 forbids a rule that lives only in the CLI, and ADR-021 constraint 2 already settled the shape for a command-scoped config key — `health_check` resolves `health-report-retention`, and "no caller — `lore health` included — reads the key and decides for itself. A second reader of that key is a duplicate implementation and an ADR-011 violation." The four `init-*` keys get the same treatment: **`plan_init` is the only reader.** A flag left unset arrives as `None`, and §5.3's resolution order (argument → `.lore/config.toml` → built-in default) runs inside `plan_init`.

The CLI therefore preselects each prompt from `InitPlan.answers` on the first `plan_init` call, never from `load_config()`. That is what makes the recorded answers visible to a human at the prompt (FR-10) without giving the key a second reader.

`--force` is deliberately absent: `--yes --on-conflict overwrite` says the same thing explicitly and composes, and ADR-001 argues against a second flag for one behaviour.

`--agent none` is a registry id (§8.1) and cannot be combined with another id:

```
$ lore init --agent none claude
Usage: lore init [OPTIONS]
Try 'lore init --help' for help.

Error: --agent none cannot be combined with other agents.
```

Exit 2, raised as `click.UsageError` in the handler body before any I/O — the same mechanism and exit code `lore codex map` uses for conflicting depth flags (`conceptual-workflows-error-handling`).

**The rule is not the CLI's.** ADR-011 is explicit that "any rule that exists only in the CLI is a bug", and that validation ownership sits in `lore.validators` with the operational layer as the authoritative enforcement point. `none`-exclusivity is a business rule about a selection, not argv parsing, so it lives in `validators.validate_agent_selection(agents) -> str | None` (the error-message-or-`None` shape every validator except `validate_rite_id` uses). `plan_init` calls it and raises `ValueError` on a non-`None` return; `cli.py` calls the same validator for UX and translates the message into a `click.UsageError`. Neither layer owns a second copy of the rule, which is the ADR-011 pattern `_validate_mission_id` already follows.

### 3.4 `SpaceSeparatedChoice` — how ADR-012 and ADR-017 both hold

ADR-012 requires `--agent claude codex`, not `--agent claude --agent codex`. Two mechanisms exist in this codebase and neither works here:

- `nargs=-1` on an option raises `TypeError: nargs=-1 is not supported for options` on Click 8.3.2 (verified).
- `lore health --scope` pairs `multiple=True` with a trailing variadic positional `extra_scopes`. A command may have only one variadic positional, and `lore init` needs two multi-value flags, so the extra tokens could not be attributed to `--agent` versus `--skills`.

`cli.py` therefore gains one `click.Option` subclass, ~25 lines, that greedily consumes following non-flag tokens into the option's value list:

```python
class SpaceSeparatedChoice(click.Option):
    """Multi-value option using space-separated syntax (ADR-012).

    Validation stays with ``click.Choice`` (ADR-017): an out-of-set token —
    first or greedily consumed — raises ``BadParameter`` and exits 2 with
    Click's standard message.
    """

    def add_to_parser(self, parser, ctx):
        super().add_to_parser(parser, ctx)
        for opt in self.opts:
            parsed = parser._long_opt.get(opt) or parser._short_opt.get(opt)
            if parsed is None:
                continue
            original = parsed.process

            def process(value, state, _orig=original, _name=self.name):
                _orig(value, state)
                extra = []
                while state.rargs:
                    nxt = state.rargs[0]
                    if nxt.startswith("-") and nxt != "-":
                        break
                    extra.append(state.rargs.pop(0))
                if extra:
                    current = state.opts.get(_name)
                    if isinstance(current, list):
                        current.extend(extra)
                    else:
                        state.opts[_name] = (
                            [current, *extra] if current is not None else list(extra)
                        )

            parsed.process = process
```

This is argv parsing, not business logic, so it belongs in `cli.py` under `standards-separation-of-concerns`. The closed-set validator is still `click.Choice`, so the message wording and exit code ADR-017 pins are untouched:

```
$ lore init --agent claude bogus
Usage: lore init [OPTIONS]
Try 'lore init --help' for help.

Error: Invalid value for '--agent': 'bogus' is not one of 'agents-md', 'claude', 'cursor', 'gemini', 'none', 'qwen'.
```

Exit 2. A repeated flag (`--agent claude codex --agent gemini`) accumulates rather than crashing; it is not the documented form, and `--help` shows only the space-separated form.

**Does `SpaceSeparatedChoice` need its own ADR? No — ADR-012 is amended in place instead (§13).**

The subclass changes the *parser*, not the *validator*. `type=click.Choice(...)` still owns the closed set, so every one of ADR-017's three Constraints Imposed holds untouched: the mechanism is `click.Choice`, an out-of-set token is a `BadParameter`/`UsageError` on stderr, and the exit code is 2. ADR-017 reserves a new ADR for "changing the enforcement mechanism away from `click.Choice`, rewording the invalid-value message, or changing the exit code" — none of which happens here.

ADR-012 is a different matter. It does not merely require the space-separated *syntax*; its Decision names the mechanism ("Click parameter definition uses `nargs=-1` (or `multiple=True` with nargs=-1 semantics)") and its Consequences assert a fact about the codebase ("The `--scope` flag on `lore health` uses `nargs=-1` in Click"). The first is unavailable — `nargs=-1` on an option raises `TypeError` — and the second is not what `lore health` does: it pairs `multiple=True` with a trailing variadic positional. The parenthetical "or `multiple=True` with nargs=-1 semantics" is the clause `SpaceSeparatedChoice` satisfies, so the *decision* is intact and only its mechanism prose is wrong.

A standalone ADR would therefore put two decisions records over one subject — the same argument §13 uses to fold the agent registry into `tech-arch-agents-md` rather than give it its own doc — and would leave ADR-012's incorrect mechanism sentence standing next to it. The correct home for "here is how space-separated multi-value is actually achieved on Click 8.3.x" is ADR-012's body. This project amends ADRs in place, so that is where it goes, with a dated `## Status History` row recording the mechanism correction and the private-API dependency the raised `click` floor (§11) now guards.

---

## 4. Implementation Patterns

### 4.1 Naming Conventions

**Database:** unchanged — no schema change.

**API / CLI:** flags are kebab-case; TOML keys are kebab-case and carry the `init-` prefix that `health-report-retention` established for command-scoped settings; Python parameters are snake_case and mirror the flag name minus the prefix (`--access` → `access_mode`, `--skills` → `skill_families`).

**Code:** new modules are lowercase single words. Frozen dataclasses are `CapWords`. Enum members are upper-case with lower-case string values, matching `QuestStatus`.

### 4.2 Error Handling

| Condition | Behaviour | Exit |
|---|---|---|
| Out-of-set value for any constrained flag | `click.Choice` → `BadParameter` → stderr, Click's standard wording | 2 |
| `--agent none` combined with another id | `click.UsageError` in the handler, before any I/O | 2 |
| Human answers "no" at the summary confirm | `No changes applied.` on stdout; nothing written | 0 |
| Ctrl-C at any prompt | `click.Abort()` → Click prints `Aborted!` to stderr; nothing written | 1 |
| `--agent` names an id absent from the registry, called through `plan_init` | `ValueError: Unknown agent: 'x'. Known agents: agents-md, claude, cursor, gemini, none, qwen.` | — |
| `agents` combines `none` with another id, called through `plan_init` | `ValueError: --agent none cannot be combined with other agents.` — the same text `cli.py` puts in its `UsageError`, from the same `validators.validate_agent_selection` call (ADR-011) | — |
| `--access` / `--skills` / `--on-conflict` token invalid through `plan_init` | `ValueError` with the same shape | — |
| Packaged `agents.yaml` or `skills-catalogue.yaml` unparseable or schema-invalid | `RuntimeError` naming the packaged file — a build defect, never a user error | 1 |
| `.lore/.install-manifest.json` unparseable | One stderr warning `lore: unreadable install manifest at <path>: <reason> (falling back to legacy hashes)`; reconciliation proceeds through the §6.6 fallback | 0 |
| An unlink during removal fails | That path is skipped and reported as `! Kept <path> — could not remove: <reason>`; the run continues | 0 |
| A write fails mid-apply | The exception propagates; the manifest is written last (§6.7) so a partial apply is re-reconciled correctly on the next run | 1 |

The `ValueError` shapes mirror `health_check`'s unknown-`scope` and unknown-`retention` raises: a token a programmer typed is a programming error and raises; a token a project wrote into `.lore/config.toml` is a user error and falls soft to the default with one warning (ADR-021 constraint 6).

### 4.3 Output Formats

**First initialisation, interactive (PRD workflow 1).** The prompts fire in the mission's fixed order; `?` lines are questionary, everything after the summary rule is Lore's own output.

```
$ lore init
? Which coding agents does this project use?  (space to toggle, enter to accept)
❯ ◉ Claude Code            CLAUDE.md + .claude/skills/
  ◯ AGENTS.md              Codex, Cursor, Windsurf, Zed, Amp, OpenCode
  ◯ Gemini CLI             GEMINI.md
  ◯ Qwen Code              QWEN.md
  ◯ Cursor (native rules)  .cursor/rules/lore.mdc
  ◯ None                   skills to .lore/skills/, no instruction file

? How should agents read and write Lore's local files?
  (codex, rites and the glossary only — quests, missions, artifacts, knights,
   doctrines and watchers always go through the CLI)
❯ Their own tools     Read/Write/Edit directly; `lore health` validates after
  The Lore CLI        every read and write goes through `lore ...`

? Which skill families should be installed?
❯ ◉ memory     2 skills   store-memory, retrieve-memory
  ◉ workflow   3 skills   start-quest, inquest, sync-codex-guide
  ◯ machinery  5 skills   update-doctrine, update-knight, update-watcher, update-artifact, update-custom-schema

? CLAUDE.md already exists and carries no Lore markers. What should Lore do?
❯ Append a Lore section    wrapped in <!-- lore:begin --> … <!-- lore:end -->
  Leave it alone           .lore/LORE-AGENT.md is written either way

? Add Lore's entries to the project's root .gitignore? (Y/n) Y

? How should the installed skills be tracked in git?
❯ Ignore Lore's skills, track my own    writes .claude/skills/.gitignore
  Track everything                      teammates get skills without installing lore
  Ignore the whole directory            one line in the root .gitignore

Plan for /home/dev/acme (agents: claude · access: native · families: memory, workflow)

  Create   .lore/                                        and 41 seeded files
  Create   .lore/.install-manifest.json
  Create   .lore/LORE-AGENT.md
  Create   .claude/skills/store-memory/SKILL.md
  Create   .claude/skills/store-memory/references/codex-doc.md
  Create   .claude/skills/store-memory/references/rite.md
  Create   .claude/skills/store-memory/references/source.md
  Create   .claude/skills/retrieve-memory/SKILL.md
  Create   .claude/skills/start-quest/SKILL.md
  Create   .claude/skills/inquest/SKILL.md
  Create   .claude/skills/sync-codex-guide/SKILL.md
  Create   .claude/skills/.gitignore
  Section  CLAUDE.md                                     appends <!-- lore:begin --> block
  Section  .gitignore                                    appends # lore:begin block

  13 create · 2 section · 0 overwrite · 0 remove · 0 conflict

? Apply this plan? (Y/n) Y

Initialized Lore project:
  Created .lore/ directory
  Created .gitignore
  Created lore.db (schema version 6)
  Created doctrines/default/update-changelog.yaml
  … 37 more seeded files …
  Created LORE-AGENT.md
  Created .claude/skills/store-memory/SKILL.md
  Created .claude/skills/store-memory/references/codex-doc.md
  Created .claude/skills/store-memory/references/rite.md
  Created .claude/skills/store-memory/references/source.md
  Created .claude/skills/retrieve-memory/SKILL.md
  Created .claude/skills/start-quest/SKILL.md
  Created .claude/skills/inquest/SKILL.md
  Created .claude/skills/sync-codex-guide/SKILL.md
  Created .claude/skills/.gitignore
  Updated CLAUDE.md (Lore section)
  Updated .gitignore (Lore section)
  Created .install-manifest.json
```

**Upgrade with renamed skills and two edited files (PRD workflow 2).** Recorded answers come from `.lore/config.toml`, so Q1–Q3 and Q5 do not fire; only the conflict prompt and the summary confirm do.

```
$ lore init
? 2 skills you edited would be overwritten. What should Lore do?
❯ Leave mine alone      you may miss new mechanics; the report names the successor
  Overwrite             discard my edits, take the shipped version

Plan for /home/dev/acme (agents: claude · access: native · families: memory, workflow)

  Create   .claude/skills/store-memory/SKILL.md
  Create   .claude/skills/store-memory/references/codex-doc.md
  Create   .claude/skills/store-memory/references/rite.md
  Create   .claude/skills/store-memory/references/source.md
  Create   .claude/skills/retrieve-memory/SKILL.md
  Create   .claude/skills/sync-codex-guide/SKILL.md
  Overwrite .claude/skills/start-quest/SKILL.md
  Overwrite .claude/skills/inquest/SKILL.md
  Remove   .claude/skills/new-rite/SKILL.md               merged into store-memory
  Remove   .claude/skills/update-codex/SKILL.md           merged into store-memory
  Remove   .claude/skills/ingest-source/SKILL.md          merged into store-memory
  Remove   .claude/skills/refresh-source/SKILL.md         merged into store-memory
  Remove   .claude/skills/explore-rite/SKILL.md           merged into retrieve-memory
  Remove   .claude/skills/explore-codex-rite/SKILL.md     merged into retrieve-memory
  Remove   .claude/skills/lore-update/SKILL.md            renamed; agent-file half replaced by the CLAUDE.md marker block
  Conflict .claude/skills/explore-codex/SKILL.md          you edited this; it is now `retrieve-memory` — port your changes, then delete the old directory
  Conflict .claude/skills/new-doctrine/SKILL.md           you edited this; it is now `update-doctrine` — port your changes, then delete the old directory
  Section  CLAUDE.md                                      replaces <!-- lore:begin --> block
  Overwrite .claude/skills/.gitignore

  6 create · 1 section · 3 overwrite · 7 remove · 2 conflict

? Apply this plan? (Y/n) Y

Initialized Lore project:
  Skipped lore.db (already exists)
  … 41 seeded files updated …
  Created .claude/skills/store-memory/SKILL.md
  … 5 more created …
  Updated .claude/skills/start-quest/SKILL.md
  Updated .claude/skills/inquest/SKILL.md
  Removed .claude/skills/new-rite/SKILL.md — merged into store-memory
  … 6 more removed …
  ! Kept  .claude/skills/explore-codex/SKILL.md
          you edited this; it is now `retrieve-memory` — port your changes,
          then delete the old directory
  ! Kept  .claude/skills/new-doctrine/SKILL.md
          you edited this; it is now `update-doctrine` — port your changes,
          then delete the old directory
  Updated CLAUDE.md (Lore section)
  Updated .install-manifest.json
```

**Headless initialisation (PRD workflow 3).** Not a terminal, no `--agent`. Byte-for-byte the pre-feature file set, plus the manifest.

```
$ lore init < /dev/null | cat
Initialized Lore project:
  Created .lore/ directory
  Created .gitignore
  Created lore.db (schema version 6)
  Created doctrines/default/update-changelog.yaml
  … seeded defaults …
  Created LORE-AGENT.md
  Created skills/store-memory/SKILL.md
  … the ten skills under .lore/skills/ …
  Created .install-manifest.json
```

**`--dry-run`:**

```
$ lore init --dry-run
Plan for /home/dev/acme (agents: claude · access: native · families: memory, workflow)

  Remove   .claude/skills/new-doctrine/SKILL.md           renamed into update-doctrine
  Overwrite .claude/skills/start-quest/SKILL.md

  0 create · 0 section · 1 overwrite · 1 remove · 0 conflict

Dry run — no files written.
```

**Declined summary:**

```
? Apply this plan? (Y/n) n
No changes applied.
```

Exit 0.

**Errors:**

```
$ lore init --access agentic
Usage: lore init [OPTIONS]
Try 'lore init --help' for help.

Error: Invalid value for '--access': 'agentic' is not one of 'cli', 'native'.
```
Exit 2.

```
$ lore init --skills memory typo
Usage: lore init [OPTIONS]
Try 'lore init --help' for help.

Error: Invalid value for '--skills': 'typo' is not one of 'memory', 'machinery', 'workflow', 'all', 'none'.
```
Exit 2.

---

## 5. Public API

### 5.1 Where the types live

`tech-arch-api-facade` pins `api.py` at zero `def` and zero `class`, so nothing may be defined there. Two homes were available:

- `lore.models` — the entity-record index. Every member mirrors an on-disk or DB record and carries `from_row` / `from_dict`.
- **The producing module** — `HealthIssue` and `HealthReport` live in `health.py`, `SchemaIssue` in `schemas.py`, `CodeBinding` / `ImpactsResult` in `impacts.py`. `api.py` collects them under an explicit `# --- Operational dataclasses (sourced from their owning modules) ---` comment.

`InitPlan` is an operational result with no persisted counterpart, so the second precedent applies. It does not live in `init.py`, because `reconcile.py` and `skills.py` both construct `PlannedFile` values and `init.py` imports both — a leaf module keeps the dependency arrow one-directional (`standards-dependency-inversion`).

**`src/lore/initplan.py`** imports stdlib only (`dataclasses`, `enum`, `pathlib`) and no `lore.*` module, matching `validators.py`'s foundation position.

### 5.2 The types

```python
# src/lore/initplan.py

class AccessMode(StrEnum):
    CLI = "cli"
    NATIVE = "native"


class FileAction(StrEnum):
    CREATE = "create"        # not on disk, or on disk and byte-identical to desired
    OVERWRITE = "overwrite"  # Lore installed it, it is unmodified, content changed
    SECTION = "section"      # a marked block inside a user-owned file
    REMOVE = "remove"        # Lore installed it, it is unmodified, no longer shipped
    CONFLICT = "conflict"    # edited since install, or present but never installed
    KEEP = "keep"            # retired and edited — reported, never touched


@dataclass(frozen=True)
class AgentTarget:
    id: str                        # "claude"
    label: str                     # "Claude Code"
    instruction_file: str | None   # "CLAUDE.md", repo-root-relative POSIX
    skills_dir: str | None         # ".claude/skills", repo-root-relative POSIX


@dataclass(frozen=True)
class PlannedFile:
    path: str                      # repo-root-relative POSIX
    action: FileAction
    kind: str                      # "owned" | "section"
    source: str                    # "skill:store-memory" | "agent-instructions:claude" | "root-gitignore" | "skills-gitignore:claude"
    digest: str | None             # sha256 of the rendered bytes; None for REMOVE/KEEP
    detail: str | None             # ledger reason, or the conflict explanation


@dataclass(frozen=True)
class InitAnswers:
    agents: tuple[str, ...]
    access_mode: AccessMode
    skill_families: tuple[str, ...]
    on_existing_agent_file: str     # "append" | "skip"
    root_gitignore: bool
    skills_gitignore: str           # "lore-only" | "none" | "all"
    on_conflict: str                # "skip" | "overwrite"


@dataclass(frozen=True)
class InitPlan:
    project_root: Path
    answers: InitAnswers
    targets: tuple[AgentTarget, ...]
    files: tuple[PlannedFile, ...]          # sorted by path
    prompts_needed: tuple[str, ...]         # conditional prompts this plan justifies
    conflicts: tuple[PlannedFile, ...]      # the FileAction.CONFLICT subset, for the Q7 gate

    @property
    def has_changes(self) -> bool: ...
    def counts(self) -> dict[str, int]: ...  # {"create": 13, "section": 2, ...}


@dataclass(frozen=True)
class InitResult:
    project_root: Path
    messages: tuple[str, ...]     # the list run_init() returns
    applied: tuple[PlannedFile, ...]
    skipped: tuple[PlannedFile, ...]
    manifest_path: Path
```

`prompts_needed` is what lets the CLI know a conditional prompt is warranted without the core function owning a prompt. `plan_init` is called once with whatever is known, the CLI inspects `prompts_needed`, asks, and calls `plan_init` again with the answers filled in. Two plan computations, no prompt inside the core — this is how ADR-011 is satisfied without a callback.

### 5.3 Signatures

```python
def plan_init(
    project_root: Path | None = None,
    *,
    agents: list[str] | None = None,
    access_mode: str | None = None,
    skill_families: list[str] | None = None,
    on_existing_agent_file: str = "append",
    root_gitignore: bool | None = None,
    skills_gitignore: str | None = None,
    on_conflict: str = "skip",
    reconfigure: bool = False,
) -> InitPlan:
    """Compute what an initialisation would do, without performing it."""


def apply_init(plan: InitPlan) -> InitResult:
    """Perform a previously computed initialisation."""


def run_init() -> list[str]:
    """Unchanged. Equivalent to apply_init(plan_init()).messages, as a list."""
```

`project_root=None` resolves to `Path.cwd()`, preserving `run_init`'s behaviour and honouring `tech-arch-project-root-detection`'s rule that `lore init` is the documented exception to `find_project_root()`.

Every keyword defaulting to `None` resolves in this order: explicit argument → `.lore/config.toml` → built-in default. `reconfigure=True` skips the config layer for the four persisted answers, which is what `--reconfigure` means (FR-10). **`plan_init` is the only reader of the four `init-*` keys** (§3.3, ADR-011, ADR-021 constraint 2) — a Python caller passing nothing gets exactly what a human passing no flag gets.

`skill_families` accepts the two aggregate tokens `all` and `none` on both surfaces. They are resolved by `skills.resolve_families()` in the business layer, not by `cli.py`, so `plan_init(skill_families=["all"])` and `--skills all` are the same call (ADR-011). Only the expanded family list is written to `init-skill-families`, which is why §9.1's allowed item set is the three concrete families and never `all` or `none`.

Every token set `plan_init` accepts is checked through `lore.validators` — `validate_access_mode`, `validate_skill_family`, `validate_agent_id`, `validate_agent_selection` — so the Python surface rejects exactly what `click.Choice` rejects at the CLI boundary. ADR-017 makes Click's exit-2 wording the *user-facing misuse* contract while requiring the business function to reject the same tokens; these four validators are how both halves hold.

`run_init()` with an empty project therefore produces: no agents, skills at `.lore/skills/`, all three families, no instruction file — the pre-feature behaviour, which is FR-34 and the pinned parity test.

### 5.4 `lore.api.__all__` additions

Thirteen names, appended to the existing domain blocks rather than sprinkled (`tech-arch-api-facade`):

- Operational dataclasses block: `AccessMode`, `FileAction`, `AgentTarget`, `PlannedFile`, `InitAnswers`, `InitPlan`, `InitResult`.
- Init / reports / config block: `plan_init`, `apply_init` (beside the existing `run_init`).
- Validators block: `validate_access_mode`, `validate_skill_family`, `validate_agent_id`, `validate_agent_selection`.

All four validators are exported, not one. Every one of the twelve functions in `validators.py` is already in `lore.api.__all__`, and `standards-public-api-stability` is explicit that "adding a new name to the public surface requires re-exporting it through `lore.api`, adding it to `lore.api.__all__`, and updating the changelog." Shipping three of the four validators as importable-but-unexported would create exactly the "models-only contract that nobody honours" ADR-010 was written to end.

Thirteen `__all__` additions plus four new fields on the exported `Config` dataclass are all additive, so the semver table in `standards-public-api-stability` puts this at a minor bump with no breaking-change notice. The `CHANGELOG.md` entry is mandatory, not optional — see §11.

Underscore aliases for `cli.py` (which may import only from `lore.api`, enforced by `tests/unit/test_cli_imports_only_api.py`):

```python
from lore import prompts as _prompts    # noqa: F401
from lore import agents as _agents      # noqa: F401
from lore import skills as _skills      # noqa: F401
```

`_agents` and `_skills` are needed at `cli.py` **import** time, because `click.Choice` evaluates its set when the decorator runs. `_prompts` must not pull `questionary` into that import: `prompts.py` imports `questionary` lazily inside its functions, so `import lore.api` stays cheap for every other command. Pulling `prompt_toolkit` into every `lore ready` would violate ADR-001's minimise-tool-cost principle for no benefit.

---

## 6. Install Manifest and Reconciliation

### 6.1 Location

`.lore/.install-manifest.json`, project-local, generated. It needs no `.gitignore` change: `.lore/.gitignore` opens with `*` and un-ignores only `.gitignore`, `config.toml`, `custom-schemas`, `codex`, `artifacts`, `knights`, `doctrines`, `watchers` and `rites`, so a dot-file at the `.lore/` root is already ignored.

It records paths **outside** `.lore/` (`.claude/skills/…`, `CLAUDE.md`, `.gitignore`), so every path is stored repo-root-relative in POSIX form regardless of platform. `apply_init` resolves each against `plan.project_root`.

### 6.2 Format

```json
{
  "manifest_version": 1,
  "lore_version": "0.10.0",
  "catalogue_version": 2,
  "generated_at": "2026-08-25T14:32:00Z",
  "answers": {
    "agents": ["claude"],
    "access_mode": "native",
    "skill_families": ["memory", "workflow"],
    "skills_gitignore": "lore-only"
  },
  "targets": {"claude": ".claude/skills"},
  "files": [
    {
      "path": ".claude/skills/.gitignore",
      "kind": "owned",
      "source": "skills-gitignore:claude",
      "hash": "sha256:9c02b1f4a8e7d3c5b6a19f8e2d7c4b3a5e6f7081920a3b4c5d6e7f8091a2b3c4"
    },
    {
      "path": ".claude/skills/store-memory/SKILL.md",
      "kind": "owned",
      "source": "skill:store-memory",
      "hash": "sha256:1f3a5b7c9d0e2f4a6b8c1d3e5f7092a4b6c8d0e2f4a6b8c1d3e5f7092a4b6c8d"
    },
    {
      "path": ".claude/skills/store-memory/references/rite.md",
      "kind": "owned",
      "source": "skill:store-memory",
      "hash": "sha256:2a4c6e8092b4d6f8a0c2e4f608a2c4e6f8092b4d6f8a0c2e4f608a2c4e6f8092"
    },
    {
      "path": ".gitignore",
      "kind": "section",
      "source": "root-gitignore",
      "hash": "sha256:5e7f9a1b3c5d7e9f0a2b4c6d8e0f2a4b6c8d0e2f4a6b8c0d2e4f6a8b0c2d4e6f"
    },
    {
      "path": "CLAUDE.md",
      "kind": "section",
      "source": "agent-instructions:claude",
      "hash": "sha256:7b9d1f3a5c7e9012b4d6f8a0c2e4f60820a2c4e6f8091b3d5f7a9c1e3f5079b1"
    }
  ]
}
```

`files` is a list of objects sorted by `path`, not a path-keyed map, because each entry carries `kind` and `source` and a map would nest an object under every key anyway. Sorting makes successive manifests diffable.

`kind` is the safety distinction the draft design lacked:

- **`owned`** — Lore wrote the whole file. `hash` covers the whole file. Eligible for removal.
- **`section`** — Lore wrote a marked block inside a user-owned file. `hash` covers **only the rendered block text between the markers**. Never removable: when the source is retired, the block is deleted and the file is left otherwise byte-identical.

Without that split, retiring an agent would delete a user's `CLAUDE.md`.

`answers` and `targets` are informational — they let the report say "access mode changed native → cli" and let a deselected agent with an empty skill set still be detected. The reconciliation algorithm reads **only `files`**; there is one source of truth for the decision (`standards-dry`).

### 6.3 Legacy hashes

`src/lore/defaults/legacy-hashes.json`, packaged, read-only:

```json
{
  "legacy_hashes_version": 1,
  "files": {
    ".lore/skills/new-doctrine/SKILL.md": [
      "sha256:aa1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f9",
      "sha256:bb2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90a"
    ],
    ".lore/skills/explore-codex/SKILL.md": [
      "sha256:cc3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90a1b"
    ]
  }
}
```

**Scope: `.lore/skills/**` only.** Before this feature, that was the only place Lore ever installed a skill, so it is the only tree the consolidation can orphan. Everything else Lore seeds lives under a `default/` subtree that re-init already overwrites in place and that this feature does not touch.

**Generation:** `scripts/update_legacy_hashes.py`, run as a release pre-flight step (`ops-publish-pypi`). It hashes every file under `src/lore/defaults/skills/`, prefixes each relative path with `.lore/skills/`, and unions the result into the existing file. Rows are never removed — a project may hop 0.8 → 0.14 and needs every intermediate hash. The script is idempotent; running it twice on an unchanged tree produces a byte-identical file.

Because the file sits under `src/lore/defaults/`, `decisions-006-no-seed-content-tests` applies: tests assert it exists, parses, and has the required top-level shape, never that a particular hash is present.

### 6.4 The reconciliation table

```
desired  = the set of (path, kind, rendered-bytes) this release would write, given the answers
recorded = manifest.files, or the §6.6 legacy fallback when no manifest exists
on_disk  = the actual bytes at each path
```

For every path in `recorded ∪ desired`:

| in `recorded` | in `desired` | on-disk state | Action | Reported |
|---|---|---|---|---|
| — | yes | absent | `CREATE` | yes |
| — | yes | present, hash == desired | `CREATE` | no — already correct |
| — | yes | present, hash != desired | `CONFLICT` (`"not installed by Lore"`) | always |
| yes | yes | absent | `CREATE` (restore) | yes |
| yes | yes | hash == recorded, desired == recorded | no-op | no |
| yes | yes | hash == recorded, desired != recorded | `OVERWRITE` | yes |
| yes | yes | hash != recorded | `CONFLICT` (`"edited since install"`) | always |
| yes | — | hash == recorded | `REMOVE`, with the ledger reason | yes |
| yes | — | hash != recorded | `KEEP`, with the ledger successor | always |
| yes | — | absent | forget — dropped from the next manifest | no |
| — | — | anything | never read, never written, never deleted | — |

For a `section` entry, "hash" means the digest of the text between the markers, and `REMOVE` means "delete the marked block and leave the rest of the file untouched".

`CONFLICT` resolution is the `on_conflict` answer: `skip` leaves the file untouched and reports the successor; `overwrite` performs the write the row would otherwise have carried. Under `skip`, a conflicted `REMOVE` candidate becomes `KEEP`.

**`REMOVE` is a hard unlink, and that does not breach ADR-003.** `decisions-003-soft-delete-semantics` requires soft-delete for every entity — `.deleted` renaming for file entities — and states there are "no special cases for 'this entity can be hard-deleted'". Its Scope paragraph draws the boundary this feature sits outside of: the ADR governs "data entities managed by the `lore` CLI — quests, missions, and dependency rows … and file entities (knights, doctrines)". A skill is not one. It has no `lore delete` path, no ID retrieval, and no CRUD surface at all — §1 rejects a `lore skill` command group outright — so there is no delete operation for a soft-delete policy to attach to. `lore init` already overwrites every `default/` subtree destructively on re-init, which is the same class of write against the same class of file. What replaces the ADR-003 guarantee here is the hash test: a path is only ever unlinked when the manifest says Lore wrote it *and* its bytes still match what Lore wrote, so the bytes being destroyed are bytes Lore itself produced and can reproduce. Anything else becomes `KEEP` or `CONFLICT`. Recording this explicitly matters because "`lore init` permanently deletes a file under `.claude/`" reads as an ADR-003 breach on any review that stops at the summary.

**Directory pruning.** After removals, `apply_init` walks each removed path's ancestors upward, removing any directory that is now empty, and stops at the first non-empty directory or at the target skills root, whichever comes first. The target root itself is never removed. A directory containing anything Lore did not install is by definition non-empty and survives.

### 6.5 What FR-28 means

FR-28 reads "Lore never reads, moves, or deletes a file it did not install." Taken literally against a path in `desired`, it would forbid the hash comparison that keeps a user's own `.claude/skills/store-memory/SKILL.md` from being clobbered — the opposite of the reliability NFR two lines below it in the PRD.

**The operative reading: Lore never reads, writes, moves or deletes any path outside `recorded ∪ desired`.** A path in `desired` is one Lore is about to write, so hashing it first is the mechanism that makes the never-lose-a-user-file guarantee true. The reconciliation table's last row is the FR-28 safety property, and the "present but never installed" row is what stops a `desired` path from becoming a silent overwrite.

### 6.6 No manifest — the legacy fallback

A project initialised before the manifest existed has none. `reconcile.legacy_recorded(project_root)` builds a synthetic `recorded` set:

1. Walk `.lore/skills/**` on disk.
2. For each file, look its repo-relative path up in the packaged `legacy-hashes.json`.
3. A hit whose on-disk hash is in the historical set becomes a `recorded` entry with `kind: "owned"` and that hash — Lore shipped it and nobody edited it, so it is safe to remove or overwrite.
4. Any other file — path unknown, or hash unmatched — is **not** added to `recorded`. It falls into the never-touched row and stays.

The bias errs toward keeping files, which is the correct direction. After one `lore init` a real manifest exists and the fallback never runs again for that project.

`.lore/skills/.gitignore` is generated per release, so its historical hashes vary with the shipped skill list. It is deliberately absent from `legacy-hashes.json`: an unmatched file is kept, and a stale gitignore listing retired directories inside a tree that `.lore/.gitignore` already ignores wholesale is harmless. FR-28 holds.

### 6.7 Apply ordering

`apply_init` writes in this order, and the manifest **last**:

1. `.lore/` directory, `.lore/.gitignore`, database, seeded `default/` trees, `.lore/GETTING-STARTED.md`, user-tracked skeletons — unchanged from today.
2. Rendered skills, in path order.
3. `.lore/LORE-AGENT.md`.
4. Agent instruction-file marker blocks.
5. Root `.gitignore` marker block.
6. Skills gitignore.
7. Removals, then directory pruning.
8. `.lore/.install-manifest.json`.

Manifest-last means an interrupted run leaves the previous manifest on disk. The next `lore init` then sees the old `recorded` set, finds the already-written files' hashes differ from it, and classifies them as conflicts rather than silently overwriting. That is a slightly noisy but strictly safe recovery, and it satisfies the PRD reliability NFR "an interrupted `lore init` leaves a project that a subsequent `lore init` reconciles to a correct state."

---

## 7. Skill Catalogue and Access-Mode Injection

### 7.1 The catalogue

`src/lore/defaults/skills-catalogue.yaml` — a sibling of `agents.yaml` at the `defaults/` root, deliberately **not** inside `skills/`, so the skills tree stays exactly one directory per skill and the renderer never has to exclude a file.

```yaml
version: 2

families:
  memory:    Project memory — codex, rites and glossary, consulted together
  machinery: Lore's own configuration entities
  workflow:  Multi-step processes over quests and missions

skills:
  - id: store-memory
    family: memory
    references: [codex-doc.md, rite.md, source.md]
  - id: retrieve-memory
    family: memory
  - id: update-doctrine
    family: machinery
  - id: update-knight
    family: machinery
  - id: update-watcher
    family: machinery
  - id: update-artifact
    family: machinery
  - id: update-custom-schema
    family: machinery
  - id: start-quest
    family: workflow
  - id: inquest
    family: workflow
  - id: sync-codex-guide
    family: workflow

retired:
  new-doctrine:       {into: update-doctrine,      reason: renamed}
  new-knight:         {into: update-knight,        reason: renamed}
  new-watcher:        {into: update-watcher,       reason: renamed}
  new-artifact:       {into: update-artifact,      reason: renamed}
  new-custom-schema:  {into: update-custom-schema, reason: renamed}
  lore-update:        {into: sync-codex-guide,     reason: "renamed; agent-file half replaced by the CLAUDE.md marker block"}
  new-rite:           {into: store-memory,         reason: merged into store-memory}
  update-codex:       {into: store-memory,         reason: merged into store-memory}
  ingest-source:      {into: store-memory,         reason: merged into store-memory}
  refresh-source:     {into: store-memory,         reason: merged into store-memory}
  explore-codex:      {into: retrieve-memory,      reason: merged into retrieve-memory}
  explore-rite:       {into: retrieve-memory,      reason: merged into retrieve-memory}
  explore-codex-rite: {into: retrieve-memory,      reason: merged into retrieve-memory}
```

The per-skill `description` is authored once, in the skill's own `SKILL.md` frontmatter, and is not duplicated in the catalogue (`standards-dry`). The catalogue carries structure — id, family, reference files, retirement — and nothing an agent reads.

`retired` rows are append-only. A user hopping several releases needs every intermediate rename explained, and `reason` is quoted verbatim in the removal report (FR-29).

The ingestion boundary that governs `store-memory` (a source snapshot only for an artifact authored outside the project and outside the conversation, identifiable well enough to re-fetch and diff) is FR-22 behaviour and belongs in `store-memory/SKILL.md`, not in the catalogue. A rule an agent must apply lives where the agent reads it.

### 7.2 The access-mode renderer

One authored `SKILL.md` per skill. Text outside any block is unconditional. Text inside a block survives only when its mode is selected.

```markdown
<!-- lore:access cli -->
Read documents with `lore codex show <id1> <id2>`. Batch IDs into one call —
`show` deduplicates and appends matched glossary terms.
<!-- lore:access end -->
<!-- lore:access native -->
Read documents directly from `.lore/codex/<layer>/<id>.md` with your own file
tool. Glossary terms are not auto-attached; run `lore glossary search <term>`
when a term is unfamiliar.
<!-- lore:access end -->

Traverse the graph with `lore codex map <id>` and `lore codex chaos <id>`, and
cross the codex↔code boundary with `lore impacts <path>`. No file tool
reproduces a precomputed traversal, so these stay in both modes.
```

`skills.render(text: str, mode: AccessMode) -> str`:

1. Scan for `<!-- lore:access MODE -->` … `<!-- lore:access end -->` regions.
2. Keep a region's body verbatim with its two marker lines stripped when `MODE == mode`.
3. Drop the whole region, markers and a single trailing newline included, otherwise.
4. Blocks never nest. An unterminated block, an unknown `MODE`, or an `end` with no opener raises `ValueError` naming the file and line.

FR-18 falls out of the authoring convention: `lore codex map`, `lore codex chaos` and `lore impacts` are written outside any block, so they appear in both modes without a special case. No third `both` token is needed.

`.lore/LORE-AGENT.md` and every agent instruction-file block go through the same renderer, which fixes the second half of the problem the business map identified — the seeded instruction file carries its own "Lore CLI commands" section, and that section is an access-mode layer like any other.

### 7.3 What agent-native mode covers

`decisions-006-id-references` requires agents to reach Lore-managed entities by ID through the CLI, naming artifacts, codex documents, knights and doctrines. Agent-native mode contradicts that for at least one entity type, so the scope has to be drawn deliberately rather than left to each skill author.

The test is FR-18's own: a command stays CLI-only when it does something a file tool cannot reproduce.

| Surface | Native mode | Why |
|---|---|---|
| Codex read (`list`, `search`, `show`) | **yes** | Grep and Read reproduce it. The cost — glossary auto-surface, multi-ID dedup, group derivation — is stated in the skill text so the agent knows what it gave up. |
| Codex write (`new`, `edit`, `delete`) | **yes** | Write and Edit reproduce it; `lore health --scope schemas` validates the result. |
| Rites read and write | **yes** | Same as codex; `lore health --scope rites` validates the graph afterwards. |
| Glossary read and write | **yes** | One YAML file with a schema; `lore health --scope glossary` validates it. |
| `lore codex map`, `lore codex chaos`, `lore impacts` | **never** | FR-18. Two-budget directional BFS, a random walk with a reachable-subgraph termination ratio, and a bidirectional `binds:` index. No file read reproduces any of the three. |
| Artifacts, knights, doctrines, watchers | **never** | `lore doctrine show` runs normalisation, step validation and cycle detection; `lore show <mission-id>` splices knight contents; every one of the four hides a `default/` versus flat split, slash-derived groups and `.deleted` soft-delete naming. This is exactly the layout-is-an-implementation-detail argument ADR-006 was written on. |
| Quests, missions, board, dependencies | **never** | SQLite-backed. |
| `lore health` | **never** | It is the validator native mode leans on. |

So agent-native mode covers **the three file-backed knowledge stores — codex, rites, glossary — and nothing else.** `decisions-006-id-references` needs an in-place amendment recording that carve-out (§13); it is narrowed, not repealed, and the four entity types its rationale defends hardest keep the rule intact.

### 7.4 Instruction-file rendering

`src/lore/defaults/docs/LORE-AGENT.md` stops being a file `lore init` copies verbatim and becomes the packaged template that produces one rendered text. That rendered text lands in two kinds of place:

- **`.lore/LORE-AGENT.md`** — always written, `kind: "owned"`, manifest-tracked. It is the canonical rendered instruction text and the only artefact when no agent is selected, which is exactly today's behaviour and therefore the FR-9 parity anchor.
- **Each selected agent's instruction file** — the same text inside `<!-- lore:begin -->` … `<!-- lore:end -->`, `kind: "section"`, manifest-tracked (FR-15).

Two regions in the template are generated rather than authored:

- `<!-- lore:access ... -->` blocks, resolved per §7.2.
- `<!-- lore:skills-table -->` … `<!-- lore:skills-table end -->`, replaced by a table of exactly the installed skills and their install path. The hand-maintained thirteen-row table in the current `LORE-AGENT.md` is what the business map flagged as invalidated by the consolidation; generating it means the catalogue is the one place a skill's existence is recorded (`standards-dry`).

Rendered marker block, as written into `CLAUDE.md`:

```markdown
<!-- lore:begin -->
# Lore

Lore is your project task manager. Run `lore --help` for the command surface.

… entities, roles, knowing-the-project sections, access-mode-resolved …

## Available skills

| Skill | What it does | Where |
|---|---|---|
| `store-memory` | Record knowledge into project memory | `.claude/skills/store-memory/` |
| `retrieve-memory` | Answer a question from project memory | `.claude/skills/retrieve-memory/` |
| `start-quest` | Read a doctrine, create a quest and its missions | `.claude/skills/start-quest/` |
| `inquest` | Audit finished work, trace a missed requirement to its culprit link | `.claude/skills/inquest/` |
| `sync-codex-guide` | Reconcile this project's codex.md against the seeded template | `.claude/skills/sync-codex-guide/` |
<!-- lore:end -->
```

**FR-4 answers are two, not three.** The draft design offered `append`, `separate` (write `LORE-AGENT.md` yourself) and `skip`. Because `.lore/LORE-AGENT.md` is now always written, `separate` and `skip` produce identical bytes on disk and differ only in a printed hint. The prompt offers `append` (add the marked block, preserve everything else) and `skip` (leave the file alone; `.lore/LORE-AGENT.md` is there to wire up). Fewer options is ADR-001-aligned and the collapsed option is recorded in §16.

The prompt fires only in the FR-4 case — the file exists and carries no Lore markers. A file that does not exist is created with markers; a file that already has markers has its block replaced (FR-15). Neither asks.

### 7.5 Where skills install

| Selection | Skills land at | Instruction file |
|---|---|---|
| An agent with a `skills_dir` (today: Claude Code) | that directory | its `instruction_file`, marker block |
| An agent with `skills_dir: null` | `.lore/skills/` | its `instruction_file`, marker block, including a pointer to `.lore/skills/` |
| Several agents, at least one with a `skills_dir` | each such directory, plus `.lore/skills/` when at least one selected agent lacks one | each agent's file |
| `none`, or no agent at all | `.lore/skills/` | none — `.lore/LORE-AGENT.md` only |

FR-14 exactly. Installing into two directories for a project using both Claude Code and an `AGENTS.md` agent costs duplicated bytes and buys a working setup for both; the manifest tracks each copy independently, so deselecting one agent removes only its copy.

### 7.6 Gitignore behaviour

**Root `.gitignore` (FR-5)**, appended inside `#`-comment markers, replaced in place on re-run:

```gitignore
# lore:begin — managed by `lore init`; edits between these markers are replaced
.lore/lore.db
.lore/lore.db-wal
.lore/lore.db-shm
.lore/reports/
.lore/.install-manifest.json
# lore:end
```

Every line names a Lore-generated artefact that is never committed. The block overlaps `.lore/.gitignore`, which git also honours; the redundancy is deliberate, because a human auditing a repository reads the root file, and a project that vendors `.lore/` differently keeps working. When `--skills-gitignore all` is chosen and a native skills directory exists, one further line (`.claude/skills/`) joins the block.

`.lore/codex/transient/` is deliberately absent: `!codex/**` un-ignores the transient layer on purpose, and many projects — this one included — track in-flight PRDs and specs.

**Skills gitignore (FR-6)**, written at the target skills directory when `--skills-gitignore lore-only`:

```gitignore
# Auto-generated by `lore init`. Lists the skills Lore installed here so they
# stay untracked. Your own skills in this directory are not ignored.
inquest/
retrieve-memory/
start-quest/
store-memory/
sync-codex-guide/
```

`none` writes no file. `all` writes no file and adds the directory to the root block instead. All three are manifest-tracked as `owned`, so switching answers removes the previous file cleanly.

The prompt fires only when a selected agent has a native skills directory, per FR-6. For `.lore/skills/` the existing `skills/` line in `.lore/.gitignore` already ignores the whole tree, so `_write_skills_gitignore`'s current unconditional write disappears. A `.lore/skills/.gitignore` left behind by an earlier release is not in `recorded` and is therefore never touched (§6.6).

---

## 8. Agent Registry

### 8.1 Format and shipped content

`src/lore/defaults/agents.yaml`:

```yaml
version: 1

agents:
  - id: claude
    label: Claude Code
    instruction_file: CLAUDE.md
    skills_dir: .claude/skills

  - id: agents-md
    label: AGENTS.md — Codex, Cursor, Windsurf, Zed, Amp, OpenCode
    instruction_file: AGENTS.md
    skills_dir: null

  - id: gemini
    label: Gemini CLI
    instruction_file: GEMINI.md
    skills_dir: null

  - id: qwen
    label: Qwen Code
    instruction_file: QWEN.md
    skills_dir: null

  - id: cursor
    label: Cursor — native rules
    instruction_file: .cursor/rules/lore.mdc
    skills_dir: null

  - id: none
    label: None — skills to .lore/skills/, no instruction file
    instruction_file: null
    skills_dir: null
```

Six rows: the five conventions the PRD records as verified, plus `none`.

**No `verified` field.** FR-13 requires every shipped entry to have a verified convention, so the field would carry one legal value on every row — a stored constant, which `standards-dry` rejects. Presence in the file is the verification. The Post-MVP item that ships unverified entries introduces the field alongside the first row that needs it.

**`none` is a registry row, not a CLI sentinel**, so `click.Choice` covers the token for free (ADR-017) and the checkbox renders it like any other option. Combining it with another id is a usage error (§3.3) rather than silent precedence, because silently dropping a selection a human made is the kind of hidden behaviour ADR-001 rules out.

Adding an agent is one YAML block: no `init.py` edit, no `cli.py` edit, no test edit beyond the structural cross-check. That is FR-11 and FR-12.

### 8.2 Loading, and how `click.Choice` gets its set

`click.Choice(...)` evaluates when the decorator runs — at `lore.cli` import. The registry therefore has to be readable at import time, and it is: it is **package** data reached through `importlib.resources`, not project data. `lore init` runs where no `.lore/` exists, so a project-local registry could never have worked.

```python
# src/lore/agents.py — stdlib + yaml only, zero lore.* imports

@functools.lru_cache(maxsize=1)
def load_registry() -> tuple[AgentTarget, ...]: ...

@functools.lru_cache(maxsize=1)
def agent_ids() -> tuple[str, ...]: ...     # sorted; feeds click.Choice

def get_agent(agent_id: str) -> AgentTarget: ...   # raises ValueError on miss
```

```python
# src/lore/cli.py
@click.option("--agent", "agents", cls=SpaceSeparatedChoice, multiple=True,
              type=click.Choice(list(_agents.agent_ids())), ...)
```

`agents.py` imports `dataclasses`, `functools`, `importlib.resources`, `yaml` and `lore.initplan` — nothing else. One `yaml.safe_load` of a ~1 KB packaged file, cached for the process, on every `lore` invocation. `skills.family_ids()` follows the identical pattern for `--skills`.

The two files are validated against packaged JSON Schemas (`lore://schemas/agents`, `lore://schemas/skill-catalogue`) at load time. A failure is a build defect, so it raises `RuntimeError` naming the packaged path rather than degrading — a shipped registry that does not parse means `lore init` cannot do its job at all.

**Neither kind is overlayable.** Validation goes through `schemas.load_schema(kind)` directly and never through `schemas.resolve_merged_schema(kind, project_root)`, which is generic over `kind` and would otherwise let a project drop `.lore/custom-schemas/agents.yaml` in place and change how a **packaged** file validates. `decisions-018-overlays-are-path-discovered-config` scopes an overlay to "user-owned project configuration addressed by its canonical path", in the same class as `.lore/config.toml` and `.lore/codex/glossary.yaml` — files a team owns and edits. `agents.yaml` and `skills-catalogue.yaml` are neither: they ship inside the wheel, a project cannot edit them, and FR-12's "a maintainer adds an agent by editing seeded data" means the Lore maintainer editing the package, not a consumer editing their checkout. `.lore/custom-schemas/agents.yaml` is not a recognised overlay path, and the v1 overlay kinds stay `codex-frontmatter` and `codex-source-frontmatter`.

---

## 9. Config Keys and the Regenerated Header

### 9.1 New keys

Four root-level keys, `init-` prefixed to match `health-report-retention`'s command-scoped naming:

| Key | Type | Default | Governs |
|---|---|---|---|
| `init-agents` | array of strings | `[]` | Which agents `lore init` targets (FR-10) |
| `init-access-mode` | `"cli"` \| `"native"` | `"native"` | Which command layer is injected into each skill (FR-16, FR-17) |
| `init-skill-families` | array of strings | `["memory", "machinery", "workflow"]` | Which families install (FR-3) |
| `init-skills-gitignore` | `"lore-only"` \| `"none"` \| `"all"` | `"lore-only"` | How installed skills are tracked in git (FR-6) |

`config.py` currently handles `bool` and `str`. It gains:

- `list` entries in `_EXPECTED_TYPE`.
- `_ALLOWED_ITEM_VALUES: dict[str, tuple[str, ...]]` — per-item token sets for list keys.
- Fail-soft parity with the scalar path: a list containing an unknown token drops the whole key to its default with one stderr warning, `lore: invalid value for init-skill-families at <path> (expected items from: memory, machinery, workflow); using default`, under the existing one-warning-per-process latch.

`Config` gains four frozen fields. It is exported through `lore.api.__all__`, so this is a minor bump per `standards-public-api-stability`.

### 9.2 Default skill families — interactive versus headless

The PRD says two different things about the same answer, and both are right for their context.

- **Interactive** (workflow 1, step 4): memory and workflow preselected, machinery unselected.
- **Headless** (workflow 3, step 3): "the behaviour of the release before this feature" — today every shipped skill installs.

**Ruling: the non-interactive default is all three families; the interactive checkbox preselects memory and workflow.** A Realm deployment that depends on `update-doctrine` existing keeps it across the upgrade, and a human at a terminal gets the smaller set the PRD's own walkthrough describes. Whichever the human confirms is written to `init-skill-families` and reused thereafter (FR-10).

### 9.3 Regenerating the known-key header (FR-36)

`config.render_known_keys_header() -> str` builds the comment block from `_FROM_TOML`, `_EXPECTED_TYPE`, `_ALLOWED_VALUES`, `DEFAULT_CONFIG` and a new `_KEY_DOC: dict[str, str]` one-line description table. Adding a setting stays a one-field, one-row-per-table edit, and no header text is hand-copied (`standards-dry`).

On an **absent** `.lore/config.toml`, `lore init` writes header plus every key at its default — unchanged from today.

On a **present** file, `lore init` replaces **only the leading contiguous run of `#` lines**, from the first line of the file to the first line that is not a comment. Every non-comment line is left byte-identical, so values, ordering, blank lines and inline comments all survive.

```toml
# Project-level Lore configuration. The comment block above the first setting
# is regenerated by `lore init`; edits inside it are replaced.
#
# Known keys (additional keys are accepted, preserved, and ignored):
#   show-glossary-on-codex-commands : bool, default true
#       append a ## Glossary block to `lore codex show` output
#   health-report-retention         : "none" | "latest" | "all", default "none"
#       none   - lore health writes no report file (console/API output only)
#       latest - keep only the newest report, pruning older ones
#       all    - keep every report
#   init-agents                     : list of "agents-md" | "claude" | "cursor" | "gemini" | "none" | "qwen", default []
#       which coding agents `lore init` installs skills and instructions for
#   init-access-mode                : "cli" | "native", default "native"
#       whether skills tell agents to use the Lore CLI or their own file tools
#   init-skill-families             : list of "machinery" | "memory" | "workflow", default ["memory", "machinery", "workflow"]
#       which seeded skill families `lore init` installs
#   init-skills-gitignore           : "lore-only" | "none" | "all", default "lore-only"
#       how the installed skills are tracked in git
show-glossary-on-codex-commands = true
health-report-retention = "none"
init-agents = ["claude"]
init-access-mode = "native"
init-skill-families = ["memory", "workflow"]
init-skills-gitignore = "lore-only"
```

This bends ADR-013's "seed in place, skip if present" rule for the comment block only, which is what FR-36 asks for. §13 records the required in-place amendment. The generated block's first line states that it is regenerated, so the social contract matches the `<!-- lore:begin -->` marker blocks: inside is Lore's, outside is yours.

---

## 10. `lore health --scope skills` (FR-37)

`skills` joins the `--scope` token set. Adding a token is explicitly non-breaking under ADR-017; the `click.Choice` mechanism, wording and exit-2 contract are untouched.

`health._check_skills(project_root)` reads `.lore/.install-manifest.json` and the packaged catalogue, and walks only the paths the manifest names.

| Check | Severity | Detail |
|---|---|---|
| `missing_skill_file` | error | `"<path> — recorded in the install manifest but missing on disk"` |
| `modified_skill_file` | warning | `"<path> — edited since install; lore init will ask before overwriting"` |
| `retired_skill_present` | warning | `"<id> — retired into <into>; run lore init to reconcile"` |
| `missing_skill_frontmatter` | error | `"<path> — SKILL.md frontmatter is missing 'name'"` |
| `skills_scan_failed` | error | `"<manifest-path>: <reason>"` — the manifest exists and does not parse |

`entity_type="skills"`. `schema_id`, `rule` and `pointer` are `null`, matching every non-schema check.

**A missing manifest emits nothing.** `conceptual-workflows-health` records `scan_failed` for a checker whose directory is missing, but a project that predates the manifest is a legitimate state, exactly as an absent `.lore/custom-schemas/` is the zero-overlay baseline (ADR-018) and an absent glossary is a valid empty glossary. Reporting an error would fail CI on every project that has not yet re-initialised.

The severity split follows the existing convention: Lore claiming to have installed a file that is gone is a real inconsistency and flips exit 1; a user editing a skill is legitimate and warns.

```
$ lore health --scope skills
ERROR    skills  .claude/skills/inquest/SKILL.md  missing_skill_file: recorded in the install manifest but missing on disk
WARNING  skills  .claude/skills/start-quest/SKILL.md  modified_skill_file: edited since install; lore init will ask before overwriting
WARNING  skills  new-doctrine  retired_skill_present: retired into update-doctrine; run lore init to reconcile
```

Exit 1.

---

## 11. Adjacent Corrections

**FR-38 — the schema version message.** `init._format_db_status` hardcodes `"  Created lore.db (schema version 1)"` at `src/lore/init.py:241`; `lore.db.SCHEMA_VERSION` is 6. It becomes `f"  Created lore.db (schema version {SCHEMA_VERSION})"` with `SCHEMA_VERSION` imported from `lore.db`, which `init.py` already imports `init_database` from.

**Stale codex, in scope.** `tech-arch-agents-md` and `conceptual-workflows-lore-init` both document an `AGENTS.md` create/marker/backup branch with zero references anywhere in `src/lore/` (FR-35). Both are rewritten around the registry, the marker block and the FR-4 prompt.

**Stale codex, added to scope.** `tech-arch-initialized-project-structure` binds `src/lore/init.py`, shows `AGENTS.md` at the project root, and omits `.lore/skills/` and `.lore/LORE-AGENT.md` — all of which `init.py` writes today. Both context maps flagged it, and it is wrong the moment this feature ships. It joins the rewrite scope.

**Two further drifts this feature must not inherit.** `tech-overview` says Python 3.10+ where ADR-013 records the 3.11 minimum, and says "No extras, no optional dependencies" where `questionary` is about to be a hard dependency. Both lines change in the same pass. `conceptual-workflows-health` states that `lore.models` hosts `HealthIssue` and `HealthReport`; `src/lore/health.py:23,49` is where they actually live, and the source wins — the sentence is corrected while the doc gains the `skills` scope.

**Packaging.** `pyproject.toml`'s `[tool.hatch.build.targets.wheel]` still names `src/lore/defaults/AGENTS.md`, a file that no longer exists. It becomes `src/lore/defaults/**/*` so `agents.yaml`, `skills-catalogue.yaml` and `legacy-hashes.json` are guaranteed into the wheel. `questionary>=2.0,<3.0` joins `dependencies`. The version moves `0.9.0` → `0.10.0`.

**The `click` floor moves `>=8.0,<9.0` → `>=8.3,<9.0`.** `SpaceSeparatedChoice` (§3.4) overrides `Option.add_to_parser`, whose signature in the shipped Click is `(self, parser: _OptionParser, ctx: Context)` — a private type — and reaches `parser._long_opt`, `parsed.process`, `state.rargs` and `state.opts`, all private. The prototype was verified on 8.3.2 and on nothing else. ADR-017 makes the `BadParameter` wording and the exit-2 code a contract; a parser hook that silently stops consuming the greedy tail on an older in-range Click would break that contract at runtime rather than at install time, which is the worse failure. The floor states the verified range instead. `test_package_distribution.py` gains an assertion that the declared floor is not below the version the parser hook is exercised against.

**`CHANGELOG.md` gains a `0.10.0` entry.** ADR-010's Consequences require contributors to "update `CHANGELOG.md` and `lore.api.__all__` together whenever the public API changes", and `standards-public-api-stability`'s Rules for Contributors repeat it twice ("every release that changes the public API must include a `CHANGELOG.md` entry"). The entry is `Added` — the thirteen `__all__` names, the four `Config` fields, the four `init-*` config keys, the `skills` health scope, the `lore init` flag surface — plus `Changed` for the raised Python-side dependency floors and the skill-catalogue consolidation. No `Removed` section and no `BREAKING CHANGE:` block: nothing leaves `__all__` and no signature narrows. The retired skills are seeded files, not public API names.

---

## 12. Project Structure

```
lore/
  CHANGELOG.md                               # + a 0.10.0 entry (ADR-010; standards-public-api-stability)
  pyproject.toml                             # + questionary dep; click floor >=8.3,<9.0; version 0.10.0;
                                             #   wheel artifacts glob fixed
  scripts/
    update_legacy_hashes.py                  # NEW — release pre-flight; unions shipped skill hashes into legacy-hashes.json
  src/
    lore/
      initplan.py                            # NEW — stdlib-only leaf: AccessMode, FileAction, AgentTarget,
                                             #       PlannedFile, InitAnswers, InitPlan, InitResult
      agents.py                              # NEW — packaged agent registry loader (load_registry, agent_ids, get_agent)
      skills.py                              # NEW — catalogue loader, family resolution, retirement ledger,
                                             #       access-mode block renderer (render), desired-file enumeration
      manifest.py                            # NEW — read/write .lore/.install-manifest.json; file_digest, bytes_digest,
                                             #       section_digest; packaged legacy-hashes loader
      reconcile.py                           # NEW — the §6.4 table: reconcile(desired, recorded, project_root) -> tuple[PlannedFile, ...]
                                             #       plus legacy_recorded() and prune_empty_dirs()
      prompts.py                             # NEW — CLI-layer questionary prompts; imports questionary LAZILY inside
                                             #       each function; imports no lore.* module except lore.initplan
      init.py                                # plan_init / apply_init added; run_init becomes a two-line wrapper;
                                             #       _format_db_status uses db.SCHEMA_VERSION (FR-38);
                                             #       _write_skills_gitignore removed; docs/ split (GETTING-STARTED copied,
                                             #       LORE-AGENT rendered); marker-block writers for instruction files
                                             #       and the root .gitignore
      cli.py                                 # SpaceSeparatedChoice class; ten new flags on `lore init`; prompt
                                             #       orchestration behind sys.stdout.isatty(); plan rendering;
                                             #       enriched --help stating no --json
      api.py                                 # + 13 __all__ names; + _prompts/_agents/_skills underscore aliases
      config.py                              # + 4 init-* keys; list type support; _ALLOWED_ITEM_VALUES; _KEY_DOC;
                                             #       render_known_keys_header()
      health.py                              # + "skills" in _ALL_SCOPES; + _check_skills()
      paths.py                               # + install_manifest_path(root); + skills_dir(root); + lore_agent_path(root)
      validators.py                          # + validate_access_mode, validate_skill_family, validate_agent_id,
                                             #   validate_agent_selection (none-exclusivity — ADR-011, not a cli.py rule)
      schemas/
        agents.yaml                          # NEW — lore://schemas/agents
        skill-catalogue.yaml                 # NEW — lore://schemas/skill-catalogue
      defaults/
        agents.yaml                          # NEW — the six shipped registry rows
        skills-catalogue.yaml                # NEW — 10 skills, 3 families, 13 retirement rows
        legacy-hashes.json                   # NEW — packaged historical hashes for .lore/skills/**
        docs/
          LORE-AGENT.md                      # now a render source: access blocks + <!-- lore:skills-table -->
          GETTING-STARTED.md                 # unchanged, still copied verbatim
        skills/
          store-memory/SKILL.md              # NEW — replaces update-codex, new-rite, ingest-source, refresh-source
          store-memory/references/codex-doc.md   # NEW
          store-memory/references/rite.md        # NEW
          store-memory/references/source.md      # NEW
          retrieve-memory/SKILL.md           # NEW — replaces explore-codex, explore-rite, explore-codex-rite
          update-doctrine/SKILL.md           # renamed from new-doctrine/
          update-knight/SKILL.md             # renamed from new-knight/
          update-watcher/SKILL.md            # renamed from new-watcher/
          update-artifact/SKILL.md           # renamed from new-artifact/
          update-custom-schema/SKILL.md      # renamed from new-custom-schema/
          start-quest/SKILL.md               # access blocks added
          inquest/SKILL.md                   # access blocks added
          sync-codex-guide/SKILL.md          # renamed from lore-update/, scope narrowed to codex.md
          # DELETED: explore-codex/, explore-codex-rite/, explore-rite/, ingest-source/,
          #          lore-update/, new-artifact/, new-custom-schema/, new-doctrine/,
          #          new-knight/, new-rite/, new-watcher/, refresh-source/, update-codex/
  tests/
    e2e/
      test_lore_init.py                      # extended — schema version message, headless parity, .lore/LORE-AGENT.md
      test_init_interactive.py               # NEW — prompt sequence, flag equivalents, isatty gate, summary confirm
      test_init_reconcile.py                 # NEW — manifest lifecycle, the §6.4 table, legacy fallback, conflicts
      test_health_skills.py                  # NEW — the five skills-scope checks
      test_api_parity_init.py                # extended — plan_init/apply_init parity; run_init() stays zero-arg
      test_config.py                         # extended — the four init-* keys, list fail-soft, header regeneration
    unit/
      test_initplan.py                       # NEW — dataclass shapes, counts(), has_changes
      test_agents.py                         # NEW — registry loading, unknown id, lru_cache, no lore.* imports
      test_skills.py                         # NEW — access-mode renderer against test-authored fixtures; family resolution
      test_manifest.py                       # NEW — digests, round-trip, unreadable-manifest fallback
      test_reconcile.py                      # NEW — every row of the §6.4 table; directory pruning
      test_prompts.py                        # NEW — lazy questionary import; answer normalisation
      test_lore_init.py                      # extended — plan/apply split, marker-block writers, SCHEMA_VERSION
      test_config.py                         # extended — list type table, header renderer
      test_health.py                         # extended — _check_skills
      test_paths.py                          # extended — three new path helpers
      test_validators.py                     # extended — four new validators
      test_api_surface.py                    # extended — the thirteen new __all__ names
      test_api_all_matches_spec.py           # extended — same
      test_cli_imports_only_api.py           # unchanged rule; cli.py reaches prompts/agents/skills via lore.api aliases
      test_adr011_no_click_in_operational.py # extended — prompts.py imports neither click nor any lore.* but initplan
      test_package_distribution.py           # extended — the three new defaults data files ship in the wheel
```

---

## 13. Codex and ADR Work This Spec Requires

`technical-test-guidelines` makes the codex the spec for E2E tests: a `conceptual-workflows-*` document has to exist **before** the test that cites it. Two of the three new E2E files therefore depend on new codex documents, which makes the codex work a precondition rather than a follow-up.

**New codex documents:**

| ID | Layer | Anchors | `binds:` |
|---|---|---|---|
| `conceptual-workflows-init-interactive` | conceptual/workflows | `tests/e2e/test_init_interactive.py` | — |
| `conceptual-workflows-init-reconcile` | conceptual/workflows | `tests/e2e/test_init_reconcile.py` | — |
| `tech-arch-install-manifest` | technical | manifest and legacy-hash formats, the §6.4 table, the hashing rule | `src/lore/manifest.py`, `src/lore/reconcile.py` |
| `tech-arch-skill-catalogue` | technical | catalogue format, families, retirement ledger, the access-mode renderer | `src/lore/skills.py`, `src/lore/defaults/skills-catalogue.yaml` |

The `binds:` column is not optional decoration. ADR-014 fixes codex → code as the one direction a code link may point, held on the codex side because code carries no frontmatter, and it is what makes `lore impacts src/lore/reconcile.py` reach the doc that governs it. `tech-arch-agents-md` picks up `src/lore/agents.py` and `src/lore/defaults/agents.yaml` in its rewrite for the same reason.

**No canonical document may name `interactive-init-tech-spec`, `interactive-init-prd`, or either context map in `related:`.** All four live in `codex/transient/` and are deleted when the feature lands, which would leave a broken `related` edge that `lore health` reports on every run afterwards. The transient documents point at canonical docs, never the reverse — the same asymmetry ADR-014 fixes for `source → canonical`, applied to the layer that is disposable by design.

**Rewritten in place** (ADR-020: current state, no migration narrative): `conceptual-workflows-lore-init`, `tech-arch-agents-md` (absorbing the agent registry — a separate registry doc would split one subject across two files), `tech-arch-initialized-project-structure`.

**Updated:** `tech-arch-source-layout` (six new modules, the `init.py` split, and lines 83–84's skills-tree listing, which names `new-doctrine`, `new-knight`, `explore-codex` and `new-custom-schema` — every one of them retired), `tech-overview` (Python floor, the dependency table, the layering diagram), `conceptual-workflows-health` (`skills` scope; the stale `lore.models` sentence), `ref-lore_cli-commands` (the `lore init` flag surface; the `--json` exception restated as unchanged; **and the `lore init` row, which still documents the `AGENTS.md` → `AGENTS.md.old` backup branch that grep finds nowhere in `src/lore/` — the same stale behaviour FR-35 removes from `tech-arch-agents-md`**), `ref-lore_api-core`, `api-reference`, `api-guide`, `standards-public-api-stability` (`__all__`), `tech-arch-api-facade` (**its underscore-alias block is enumerated verbatim and gains `_prompts`, `_agents`, `_skills`; its `__all__` layout section says types are sourced from `lore.models`, while `api.py:20` already carries an `Operational dataclasses` block that seven of the new names join**), `ops-installation`, `ops-publish-pypi` (the legacy-hash pre-flight step), `conceptual-workflows-json-output` (**the `lore oracle` correction from §3.1 — the doc records the flag as accepted-and-ignored at exit 0, the code rejects it at exit 2 — plus the `lore init` sentence restated as unchanged**), `tech-cli-entity-crud-matrix` (record that skills are deliberately absent), `CHANGELOG.md` (§11 — required by ADR-010 and `standards-public-api-stability`, not a codex document but the same release obligation).

`conceptual-workflows-lore-init`'s rewrite must state that `lore --json init` is accepted, ignored, and exits 0, because §14.1 anchors that scenario to it and `technical-test-guidelines` §3 permits a test to cover only behaviour its cited document describes.

**ADR amendments — in place, body plus a dated `## Status History` row, matching the table format in ADRs 013/017/020/021. No superseding ADR, and no ADR marked superseded.**

| ADR | Why |
|---|---|
| `decisions-001-dumb-infrastructure` | Named by the PRD. Every principle in it — short commands, smart defaults, no flags required, minimise tool calls — was written for an agent-only caller. Nothing in it admits a command that stops and asks a human. The amendment adds the human-first interactive command class and the `isatty` gate that keeps agent callers on the old path. **It also narrows the "JSON output — all commands support `--json`" bullet** to match the permanent exception `ref-lore_cli-commands` already records (§3.1). Declining `--json` on `lore init` depends on that exception being settled, so the ADR body cannot be left asserting the opposite. |
| `decisions-012-multi-value-cli-param-convention` | §3.4. The decision — space-separated, never repeatable flags — is unchanged and `SpaceSeparatedChoice` satisfies it. What is wrong is the recorded mechanism: the Decision's `nargs=-1` raises `TypeError: nargs=-1 is not supported for options` on an option, and the Consequences' claim that "`--scope` on `lore health` uses `nargs=-1` in Click" describes a `multiple=True` + trailing-variadic-positional implementation. The amendment corrects both, names `SpaceSeparatedChoice` as the mechanism for any command needing more than one multi-value flag, and records that it rides on Click parser internals — which is why §11 raises the `click` floor to the verified `>=8.3`. Ruling on the open question the Architect raised: **no standalone ADR.** ADR-017 is untouched (the validator is still `click.Choice`, the wording and exit 2 unchanged), and a second ADR over multi-value flags would leave ADR-012's incorrect mechanism prose standing beside it. |
| `decisions-006-id-references` | Agent-native mode lets an agent read and write codex documents, rites and the glossary with its own tools, which the ADR forbids by name for the codex. §7.3 draws the carve-out; the amendment records it and restates that artifacts, knights, doctrines and watchers keep the by-ID rule in both modes. This ADR has no Status History table yet; the amendment adds one. |
| `decisions-013-toml-for-config-yaml-for-glossary` | FR-36 regenerates the known-key comment header on a `.lore/config.toml` that already exists, which is an exception to the ADR's "seed in place, skip if present" rule. The amendment records that the exception covers the leading comment block only and that no setting line is ever rewritten. |

**ADR text correction — no decision change, no Status History row.** `decisions-018-overlays-are-path-discovered-config` names the `new-custom-schema` scaffolding skill twice, at lines 68 and 115, as the authoring path for an overlay. This feature renames that skill to `update-custom-schema` (§7.1's retirement ledger). The ADR's decision — authoring help comes from a scaffolding skill rather than a CLI entity command, and an overlay is reached by path rather than by ID — is untouched; only the skill's name changes. A name correction is not a decision change, so the body is corrected in place and the Status History table is left alone. Adding a status row for a rename would put noise in the one table a reader scans to learn whether a decision moved.

The `decisions-006-` prefix is shared by two unrelated ADRs (`decisions-006-id-references` and `decisions-006-no-seed-content-tests`). Every reference in this spec uses the full codex id, never the bare number.

**No new ADR is required.** `--json` on `lore init` is declined (§3.1), so the recorded permanent exception stands unchanged, and `SpaceSeparatedChoice` amends ADR-012 in place rather than raising its own (§3.4). Four ADRs are amended in place; none is superseded and none is marked superseded.

---

## 14. Test Strategy

### 14.1 E2E Coverage

Every PRD user workflow maps to a scenario. Each E2E file cites exactly one `conceptual-workflows-*` id in its module docstring, and the file slug is that id minus the prefix (`technical-test-guidelines` §3–4). `test_health_skills.py` follows the established `test_health_<scope>.py` precedent set by `test_health_bindings.py`, `test_health_rites.py` and `test_health_voice.py`, all of which cite `conceptual-workflows-health`.

**The codex ID column below decides the file, not the topic.** `technical-test-guidelines` §3 binds an E2E file to exactly one document and permits it to test only behaviour that document describes, so a scenario anchored to `conceptual-workflows-error-handling` cannot sit in `test_init_interactive.py` — that would give one file two anchors and break the rule the guidelines were written to enforce. Six scenarios therefore land in files that already exist and already carry the right anchor:

| Scenario | File | Cited id |
|---|---|---|
| Constrained-flag misuse (`--access agentic`, `--agent bogus`, `--skills memory typo`) | `tests/e2e/test_error_handling.py` — extended | `conceptual-workflows-error-handling` |
| `--agent none` combined | `tests/e2e/test_error_handling.py` — extended | `conceptual-workflows-error-handling` |
| `lore init --help` | `tests/e2e/test_help_group_param.py` — extended | `conceptual-workflows-help` |
| `lore --json init` | `tests/e2e/test_lore_init.py` — extended | `conceptual-workflows-lore-init` |
| API parity | `tests/e2e/test_api_parity_init.py` — extended | `conceptual-workflows-python-api` |
| Headless, headless-with-flags, idempotency, config header, schema version | `tests/e2e/test_lore_init.py` — extended | `conceptual-workflows-lore-init` |

The remaining scenarios split between the two new files by their cited id: `conceptual-workflows-init-interactive` → `test_init_interactive.py`, `conceptual-workflows-init-reconcile` → `test_init_reconcile.py`, `conceptual-workflows-health` → `test_health_skills.py`. `lore --json init` moves to the `lore-init` anchor rather than the `json-output` one because no `tests/e2e/test_json_output.py` exists to extend and the guidelines forbid a second anchor in an existing file — which is why §13 requires the `conceptual-workflows-lore-init` rewrite to state the `--json` behaviour.

| Workflow (from PRD) | Workflow codex ID | Test scenario | Priority |
|---|---|---|---|
| First initialisation — human developer | `lore codex show conceptual-workflows-init-interactive` | With `stdout` forced to a TTY and questionary answers injected, `lore init` prompts in the mission's fixed order, prints a summary before any write, and on confirmation produces `.claude/skills/` with the selected families, a `CLAUDE.md` marker block, an updated root `.gitignore`, `.lore/config.toml` carrying the four `init-*` keys, and `.lore/.install-manifest.json`. Asserted on paths, counts and manifest structure — never on rendered skill prose. | High |
| First initialisation — declined summary | `lore codex show conceptual-workflows-init-interactive` | Answering "no" at the confirm prints `No changes applied.`, exits 0, and leaves zero files created outside `.lore/` — the pre-write-summary guarantee. | High |
| First initialisation — existing instruction file | `lore codex show conceptual-workflows-init-interactive` | A pre-existing `CLAUDE.md` with user content and no markers triggers the FR-4 prompt; `append` preserves every original byte and adds the block; `skip` leaves the file byte-identical and still writes `.lore/LORE-AGENT.md`. | High |
| Upgrade with renamed skills | `lore codex show conceptual-workflows-init-reconcile` | A project seeded with the previous catalogue and a manifest, then re-initialised: retired skills are removed with the ledger reason quoted, unmodified skills are overwritten silently, no retired directory remains, and the new manifest lists exactly the current file set. | High |
| Upgrade — an edited skill, declined | `lore codex show conceptual-workflows-init-reconcile` | Two skills edited after install; the conflict prompt fires; `skip` leaves both byte-identical, applies everything else, and names the successor for each in the report. | High |
| Upgrade — an edited skill, accepted | `lore codex show conceptual-workflows-init-reconcile` | `--on-conflict overwrite` replaces both edited files and reports them as overwrites, not conflicts. | High |
| Upgrade across a version gap with no manifest | `lore codex show conceptual-workflows-init-reconcile` | `.lore/skills/` populated with pristine previous-release files and one user-authored skill and no manifest: legacy hashes match the shipped ones and they are removed; the user-authored skill is untouched and reported as kept. | High |
| A file Lore never installed | `lore codex show conceptual-workflows-init-reconcile` | A user-authored `.claude/skills/store-memory/SKILL.md` at a path Lore wants: classified `CONFLICT`, never overwritten under the default `skip`, and its bytes are identical after the run. This is the FR-28 safety property. | High |
| Headless initialisation — Realm and CI | `lore codex show conceptual-workflows-lore-init` | With `stdout` not a TTY and no flags, no prompt appears, skills land in `.lore/skills/`, no instruction file is written outside `.lore/`, and the created path set equals the pre-feature set plus the manifest. | High |
| Headless with explicit flags | `lore codex show conceptual-workflows-lore-init` | `lore init --agent claude --access native --yes` produces the interactive result with no prompt. | High |
| Changing the access mode | `lore codex show conceptual-workflows-init-reconcile` | `lore init --access cli` after a `native` install: every installed skill is classified `OVERWRITE` (not `CONFLICT`), and an edited skill is still `CONFLICT`. This is the rendered-hash property from §2.1. | High |
| Idempotency | `lore codex show conceptual-workflows-lore-init` | Two consecutive runs with the same answers: the second reports zero creates, zero overwrites, zero removals, and writes a byte-identical manifest apart from `generated_at`. | High |
| `--dry-run` | `lore codex show conceptual-workflows-init-interactive` | Prints the summary, writes nothing — asserted by a recursive mtime and path-set snapshot taken before and after. | High |
| Constrained-flag misuse | `lore codex show conceptual-workflows-error-handling` | `--access agentic`, `--agent bogus`, `--skills memory typo` each exit 2 with Click's `Invalid value for '<flag>'` wording on stderr (ADR-017). | High |
| Space-separated multi-value | `lore codex show conceptual-workflows-init-interactive` | `--agent claude agents-md --skills memory workflow` parses both flags correctly and applies both selections (ADR-012). Plus the five `SpaceSeparatedChoice` cases: a following flag stops consumption, a bare `-` is consumed as a value, an out-of-set token in the greedy tail still exits 2 with Click's wording, and a repeated flag accumulates rather than raising. | High |
| `--agent none` combined | `lore codex show conceptual-workflows-error-handling` | `--agent none claude` exits 2 with the `UsageError` message and writes nothing. | Medium |
| `lore --json init` | `lore codex show conceptual-workflows-lore-init` | Exits 0, prints the text summary, emits no JSON — the permanent exception, pinned. | High |
| `lore init --help` | `lore codex show conceptual-workflows-help` | Help names every flag and states that JSON output is unsupported, pointing at `lore.api.plan_init` (ADR-008). | Medium |
| Reconfiguring | `lore codex show conceptual-workflows-init-interactive` | Recorded answers suppress Q1–Q3 and Q5b on a re-run; `--reconfigure` makes all of them fire again (FR-10). | High |
| Skills audit | `lore codex show conceptual-workflows-health` | `--scope skills` reports each of the five checks; a project with no manifest reports nothing and exits 0; a deleted installed skill exits 1. | High |
| Config header regeneration | `lore codex show conceptual-workflows-lore-init` | An existing `.lore/config.toml` written before the `init-*` keys existed gains them in the header while every setting line stays byte-identical (FR-36). | High |
| Schema version message | `lore codex show conceptual-workflows-lore-init` | The `Created lore.db (schema version N)` line matches `lore.db.SCHEMA_VERSION`, asserted against the constant rather than a literal so a future migration does not break the test (FR-38). | High |
| API parity | `lore codex show conceptual-workflows-python-api` | `run_init()` is still callable with zero arguments and produces the headless file set; `plan_init()` returns an `InitPlan` and writes nothing; `apply_init(plan)` produces exactly the paths the plan named. | High |

### 14.2 Unit Coverage

| Component | Workflow codex ID | Scenarios to cover |
|---|---|---|
| `lore.reconcile.reconcile` | `lore codex show conceptual-workflows-init-reconcile` | Every one of the eleven rows in the §6.4 table, each as its own case; `section` entries hashing only the marked block; `on_conflict` turning a conflicted remove into a keep; deterministic path ordering |
| `lore.reconcile.legacy_recorded` | `lore codex show conceptual-workflows-init-reconcile` | Hash hit → recorded; hash miss → absent; unknown path → absent; missing packaged file → raises; a project with no `.lore/skills/` → empty |
| `lore.reconcile.prune_empty_dirs` | `lore codex show conceptual-workflows-init-reconcile` | Empty chain removed up to the root; stops at the first non-empty ancestor; never removes the target root; a directory holding a user file survives |
| `lore.manifest` | `lore codex show conceptual-workflows-init-reconcile` | `file_digest` / `bytes_digest` / `section_digest` stability and the `sha256:` prefix; round-trip write→read; unreadable JSON → warning plus `None`; absent file → `None`; POSIX paths preserved on every platform; `files` sorted by path |
| `lore.skills.render` | `lore codex show conceptual-workflows-init-interactive` | Fixtures authored **inside the test**, never read from `src/lore/defaults/`: cli block kept and native dropped, and the reverse; unblocked text always kept; adjacent blocks; a block at end-of-file with no trailing newline; unterminated block → `ValueError` naming the line; unknown mode token → `ValueError`; `end` with no opener → `ValueError`; nesting → `ValueError` |
| `lore.skills` catalogue | `lore codex show conceptual-workflows-init-interactive` | Family resolution including `all` and `none`; `retired` lookup returns `into` and `reason`; an unknown family raises; desired-file enumeration for a given family set and target |
| `lore.agents` | `lore codex show conceptual-workflows-init-interactive` | `agent_ids()` sorted and cached; `get_agent` on a known id; unknown id → `ValueError` listing the known set; `none` carries two `None` fields; the module imports no `lore.*` beyond `lore.initplan` |
| `lore.initplan` | `lore codex show conceptual-workflows-python-api` | Every dataclass is frozen; `counts()` totals per action; `has_changes` false for an all-no-op plan; `conflicts` is exactly the `CONFLICT` subset |
| `lore.init.plan_init` | `lore codex show conceptual-workflows-lore-init` | Resolution order argument → config → default, per keyword; `reconfigure=True` skips the config layer; `project_root=None` → `Path.cwd()`; unknown agent / access / family tokens raise `ValueError` with the documented wording; `prompts_needed` populated only in the FR-4, FR-6 and conflict cases |
| `lore.init.apply_init` | `lore codex show conceptual-workflows-lore-init` | Writes in the §6.7 order with the manifest last; an unlink failure is skipped and reported; a `section` removal deletes only the block; `InitResult.applied` plus `skipped` partitions `plan.files` |
| `lore.init` marker writers | `lore codex show conceptual-workflows-lore-init` | Create when absent; replace between markers when present; append when present without markers; content outside the markers byte-identical; `#`-comment markers for `.gitignore`, HTML markers for markdown |
| `lore.config` | `lore codex show conceptual-workflows-lore-init` | List-typed keys parse; a wrong element type drops the key with one warning; an out-of-set item drops the key with one warning; the one-warning-per-process latch still holds across a scalar and a list failure; `render_known_keys_header()` names every key in `_FROM_TOML`; header replacement leaves non-comment lines byte-identical |
| `lore.health._check_skills` | `lore codex show conceptual-workflows-health` | Each of the five checks in isolation; absent manifest → zero issues; unparseable manifest → one `skills_scan_failed`; severity mapping; `entity_type="skills"` and three `None` schema fields |
| `lore.validators` | `lore codex show conceptual-workflows-validators` | `validate_access_mode`, `validate_skill_family`, `validate_agent_id`, `validate_agent_selection` accept the valid sets and reject everything else; `validate_agent_selection` rejects `none` combined with any other id and accepts `none` alone; zero `lore.*` imports preserved |
| `lore.prompts` | `lore codex show conceptual-workflows-init-interactive` | `questionary` is imported lazily — asserted by AST inspection showing no module-level import; each prompt function normalises its return into the `plan_init` parameter shape; a `None` return (Ctrl-C) propagates as an abort signal |
`SpaceSeparatedChoice` is deliberately **absent from this table.** It is defined in `cli.py`, and `technical-test-guidelines` §2 requires unit tests to "import from `lore.*` modules directly — never from `lore.cli`", §6 lists `from lore.cli import main` as a prohibited pattern in a unit file, and §8 says a test that needs to invoke the CLI "belongs in `tests/e2e/` — move it there". A handful of existing unit files (`test_cli_codex_list.py`) breach that rule; a new spec does not get to inherit the breach. Its five cases — space-separated values collected, a following flag stopping consumption, a bare `-` consumed as a value, an out-of-set token in the greedy tail still raising `BadParameter`, and a repeated flag accumulating rather than raising — extend the **Space-separated multi-value** E2E scenario in §14.1, where a `CliRunner` is the sanctioned tool and `conceptual-workflows-init-interactive` is the anchor.

### 14.3 Test Conventions

Files, classes and methods follow `technical-test-guidelines`: no `SCENARIO-NNN`, no `TestAC<N>_*`, no `US-N`; unit tests never import `lore.cli`; every fixture comes from `tests/conftest.py` or `tests/unit/conftest.py` and no new `conftest.py` is added.

**`decisions-006-no-seed-content-tests` shapes the catalogue half decisively.** The ADR forbids asserting a specific value or prose string from anything under `src/lore/defaults/`, which rules out the obvious test — "the rendered `store-memory/SKILL.md` contains `lore codex show`". Two moves replace it:

1. **The renderer is tested on fixture text authored in the test file.** `skills.render` is a pure string function; feeding it a five-line fixture proves block selection completely, and no seed content is touched.
2. **The shipped tree is tested structurally.** Valid targets: exactly ten directories under `src/lore/defaults/skills/`; each holds a `SKILL.md`; each `SKILL.md` parses and carries `name` and `description` frontmatter; `skills-catalogue.yaml` parses, validates against `lore://schemas/skill-catalogue`, and its `skills[].id` set equals the directory-name set in both directions; every `retired` key names an `into` that is a current skill id; `store-memory`'s declared `references` all exist on disk; every `<!-- lore:access ... -->` region in every shipped file is terminated and names `cli` or `native`. Every one of these is existence, parseability, or structural completeness — the three targets the ADR names as valid.

The last item is the important one: it proves the access-mode blocks are **well-formed** across the whole shipped tree without asserting a single word of their content.

A fixture in `tests/e2e/conftest.py` — `legacy_skills_project` — materialises a project seeded with the previous catalogue, a manifest or no manifest, and optional edits, so the reconciliation scenarios read as data rather than setup.

Prompting is exercised by monkeypatching the functions in `lore.prompts` to return canned answers and forcing `sys.stdout.isatty` to `True`. No E2E test drives `prompt_toolkit`; the prompt library is a dependency, not a subject.

---

## 15. Migration & Rollback

**What changes for an existing project.** Re-running `lore init` after the upgrade removes the thirteen retired skill directories from `.lore/skills/` — or from `.claude/skills/` once an agent is selected — and installs the ten current ones. An edited skill is never removed without the human agreeing. `.lore/config.toml` gains four keys and a regenerated header; every existing setting line survives byte-identical. `.lore/LORE-AGENT.md` is rewritten from a raw copy to a rendered file. `.lore/skills/.gitignore` is no longer generated, and an existing one is left where it is.

**What changes for a Python consumer.** Nothing breaks. `run_init()` keeps its zero-argument signature and its `list[str]` return, which is the pinned contract in `tests/e2e/test_api_parity_init.py`. Ten names are added to `lore.api.__all__` and four fields to the exported `Config` dataclass — additive, minor bump, no removals and no signature changes.

**What changes for the CLI.** Ten flags are added to `lore init`. No existing flag changes meaning, no exit code changes, and `lore --json init` behaves exactly as it does today.

**Rollback.** Downgrading the package and re-running `lore init` reconciles correctly without special handling: the older release's `desired` set is the older catalogue, the manifest on disk is the newer one, and the §6.4 table removes what the older release no longer ships. This is the same property that makes forward hops work, applied in reverse — which is why there is no migration chain to unwind.

The one asymmetry worth naming: an older release cannot read `manifest_version: 1` if a future version bumps it. `manifest.load` treats an unrecognised `manifest_version` exactly as an unreadable manifest — one stderr warning, fall through to the legacy path, keep every unmatched file. The bias stays toward keeping files.

---

## 16. Ideas Considered and Rejected

| Idea | Decision | Rationale |
|---|---|---|
| Reject `--json` on `lore init` with exit 2, matching `lore oracle` | **Rejected** | Would break a CI pipeline running `lore --json init` today, contradicting the PRD's headless success criterion. `lore oracle` can afford exit 2 because it has always behaved that way. |
| Give `lore init` a JSON envelope and overturn the permanent exception | **Rejected** | `plan_init` returns strictly more information than an envelope could, and Realm imports rather than shells out. A second machine contract over the same data is what `standards-dry` exists to prevent. |
| Per-version migration steps for the skill rename | **Rejected** | Each step becomes permanent code and a 0.8 → 0.14 hop has to replay all of them in order. The three-way reconciliation is one algorithm, correct for any hop including skipped releases and downgrades. |
| `keep-new` conflict policy writing `<name>.new` siblings | **Rejected** | The siblings are untracked files Lore does not record, which reintroduces the orphan accumulation the manifest exists to end. The PRD rules out migrating an edited skill's content into its successor, which is the only thing they would serve. |
| A `separate` answer to FR-4 writing `LORE-AGENT.md` at the project root | **Rejected** | `.lore/LORE-AGENT.md` is always written, so `separate` and `skip` produce identical bytes and differ only in a printed hint. A root-level copy would also collide by name with the `.lore/` one. |
| A `verified: true` field on every registry row | **Rejected** | FR-13 makes it constant across every shipped row. The Post-MVP item that ships unverified entries introduces the field with the first row that needs it. |
| A `both` token for access-mode blocks | **Rejected** | Text outside any block is already unconditional, which is where FR-18's three commands are authored. A third token would give two ways to say one thing. |
| Template variables (`{{access_mode}}`) in `SKILL.md` | **Rejected** | ADR-001 rejected a template engine on the grounds that Lore would have to understand and evaluate templates. Block selection is line-range arithmetic with no expression language. |
| Two authored copies of each skill, one per access mode | **Rejected** | FR-19 requires one authored source per skill, and twenty files drift where ten do not. |
| Symlinking `.claude/skills/` at `.lore/skills/` | **Rejected** | PRD Out of Scope. ADR-001 targets Windows, where symlink creation needs elevated privileges. |
| `InitPlan` in `lore.models` | **Rejected** | `models.py` is the entity-record index — every member mirrors a DB row or a file with a `from_row` / `from_dict` hydrator. `HealthReport`, `SchemaIssue` and `ImpactsResult` set the precedent for operational result types living in their producing module. |
| `InitPlan` in `init.py` | **Rejected** | `reconcile.py` and `skills.py` construct `PlannedFile` values and `init.py` imports both, so the types have to sit below all three (`standards-dependency-inversion`). |
| A `SpaceSeparatedChoice`-free design using `lore health --scope`'s trailing positional | **Rejected** | A command may have one variadic positional; `lore init` has two multi-value flags and the extra tokens could not be attributed to one or the other. |
| Repeatable flags (`--agent claude --agent codex`) | **Rejected** | ADR-012 names this form as wrong by example. The subclass keeps the space-separated form working without touching the `click.Choice` validator. |
| A standalone ADR for `SpaceSeparatedChoice` | **Rejected** | It leaves ADR-012's incorrect `nargs=-1` mechanism prose standing beside a second record of the same subject. ADR-017 is untouched — `click.Choice` is still the validator, the wording and exit 2 unchanged — so the only ADR with anything to say is ADR-012, amended in place (§3.4, §13). |
| Leaving `--agent none` exclusivity as a `cli.py`-only `UsageError` | **Rejected** | ADR-011: "any rule that exists only in the CLI is a bug." A Python caller passing `agents=["none", "claude"]` would get a silently different outcome from the same input at the CLI. The rule moves to `validators.validate_agent_selection` and both layers call it (§3.3). |
| Config-derived Click defaults on the `init-*` flags | **Rejected** | ADR-021 constraint 2 settled the shape for a command-scoped key: the business function is its only reader, and a second reader "is a duplicate implementation and an ADR-011 violation." `plan_init` resolves; `cli.py` preselects from `InitPlan.answers` (§3.3). |
| Exporting only `validate_access_mode` and leaving the other three validators internal | **Rejected** | All twelve functions in `validators.py` are already in `lore.api.__all__`, and `standards-public-api-stability` requires a new public name to be re-exported and changelogged. A partial export recreates the unhonoured contract ADR-010 replaced. |
| A `--force` flag | **Rejected** | `--yes --on-conflict overwrite` says the same thing explicitly and composes; ADR-001 argues against a second flag for one behaviour. |
| `.lore/codex/transient/` in the root `.gitignore` block | **Rejected** | `!codex/**` un-ignores the transient layer deliberately, and projects track in-flight PRDs and specs there. |
| A `[init]` TOML table instead of `init-` prefixed root keys | **Rejected** | ADR-013 chose a flat key-value shape, and ADR-021 rejected a `[health]` table on the same grounds. `health-report-retention` already establishes the command-prefix convention. |
| Legacy hashes covering every seeded tree rather than skills alone | **Rejected** | Doctrines, knights, artifacts and watchers all live under a `default/` subtree that re-init overwrites in place and that reconciliation does not manage. Widening the file adds rows nothing reads. |
| `scan_failed` when `.lore/.install-manifest.json` is absent | **Rejected** | A project that predates the manifest is a legitimate state, exactly as an absent `.lore/custom-schemas/` is the zero-overlay baseline. An error would fail CI on every project that has not yet re-initialised. |
| Asserting rendered skill content in tests | **Rejected** | `decisions-006-no-seed-content-tests` forbids it. The renderer is proved on test-authored fixtures and the shipped tree is proved structurally. |
| Prompting inside `plan_init` via a callback | **Rejected** | ADR-011 requires the effect of every prompt to be a parameter on the core function. `prompts_needed` plus a second `plan_init` call keeps the core prompt-free and testable without a terminal. |
| Importing `questionary` at `lore.prompts` module level | **Rejected** | `api.py` aliases `_prompts` for `cli.py`, so a module-level import would pull `prompt_toolkit` into every `lore ready`. ADR-001 makes per-invocation cost a design constraint. |

---

## 17. Change Log

| Version | Change | Reason |
|---|---|---|
| 1.0 | Initial Tech Spec | Settles the five decisions the PRD deferred: `--json` declined on `lore init` with the permanent exception intact and `--dry-run` added in its place; `InitPlan` and its companions in a stdlib-only `lore/initplan.py` re-exported through the facade; a `kind`-aware install manifest with a skills-scoped packaged legacy-hash fallback and an eleven-row reconciliation table; access-mode injection by HTML-comment block selection over one authored source per skill; and a six-row packaged agent registry read at import time so `click.Choice` and a data-driven registry both hold. Resolves the three Scout-flagged collisions, adds a `SpaceSeparatedChoice` option class so two multi-value flags can coexist under ADR-012 and ADR-017, and names the three ADRs that need in-place amendment. |
| 1.1 | ADR & Standards reconciliation | The ADR & Standards Enforcer rewrote the spec to match the settled decision record. Ten reconciliations and six coverage fills, listed in §18. Rules on the open question from §3.4: `SpaceSeparatedChoice` gets no ADR of its own; ADR-012 is amended in place instead. |

---

## 18. ADR & Standards Audit

Performed against every document in the `decisions` group and every standards, convention and contract document in the codex. Section numbers below point at the reconciled text.

### Reconciled

Spec lines rewritten because a settled ADR or standard required it.

| # | ADR / standard | Old spec text | New spec text | §  |
|---|---|---|---|---|
| 1 | **ADR-011**, **ADR-021** constraint 2 | Flag table default column: "from config, else none" / "from config, else `native`" / "from config, else all three families" / "from config, else `lore-only`" — a Click default sourced from `.lore/config.toml`, which makes `cli.py` a second reader of the four `init-*` keys | Click default is `None` for all four; a separate "Resolved default (in `plan_init`)" column carries the config lookup; plus the rule that `cli.py` never reads a config key and preselects prompts from `InitPlan.answers` | §3.3 |
| 2 | **ADR-011** ("any rule that exists only in the CLI is a bug") | `--agent none` exclusivity raised "as `click.UsageError` in the handler body", with no `plan_init` counterpart anywhere in the spec | The rule moves to `validators.validate_agent_selection`; `plan_init` raises `ValueError` with the same text; `cli.py` calls the same validator and translates it into the `UsageError`; a row added to the §4.2 error table | §3.3, §4.2 |
| 3 | **ADR-010**, **standards-public-api-stability** | "Ten names" added to `lore.api.__all__`; Validators block gains `validate_access_mode` alone, while §12 declared three new validators in `validators.py` | Thirteen names; all four validators exported, matching the twelve-of-twelve export rate `validators.py` already has | §5.4, §3, §12 |
| 4 | **ADR-010** Consequences, **standards-public-api-stability** Rules for Contributors | No mention of `CHANGELOG.md` anywhere in the spec, while thirteen `__all__` names and four `Config` fields are added | `CHANGELOG.md` gains a `0.10.0` entry with its exact Added/Changed content stated; added to the §12 tree and the §3 versioning row | §11, §12, §3 |
| 5 | **ADR-017** constraints 1–3 | `click>=8.0,<9.0` unchanged, while `SpaceSeparatedChoice` overrides `Option.add_to_parser` and reaches `parser._long_opt`, `parsed.process`, `state.rargs`, `state.opts` — all private, verified on 8.3.2 alone | Floor raised to `click>=8.3,<9.0`, with the reason stated: a parser hook that silently stops consuming on an older in-range Click breaks ADR-017's exit-2 contract at runtime instead of at install time. **Also listed under Escalations** — it narrows the supported environment | §11 |
| 6 | **ADR-001** (`JSON output. All commands support --json`), **ref-lore_cli-commands** (permanent exception) | §3.1 declines `--json` and asserts "no recorded contract changes", leaving ADR-001's blanket bullet asserting the opposite of the exception the ruling rests on | The ADR-001 in-place amendment is widened to narrow that bullet to match the already-recorded permanent exception. Records nothing new — brings the ADR body into line with `ref-lore_cli-commands` | §3.1, §13 |
| 7 | **technical-test-guidelines** §3 (one anchor per E2E file; only behaviour that document describes) | §14.1 anchored four scenarios to `conceptual-workflows-error-handling`, `-help` and `-json-output` without naming a file, which would have given `test_init_interactive.py` three anchors | A file-assignment table routes them to the existing `test_error_handling.py`, `test_help_group_param.py`, `test_lore_init.py` and `test_api_parity_init.py`; the `lore --json init` row is re-anchored to `conceptual-workflows-lore-init`, and §13 now requires that doc's rewrite to state the `--json` behaviour | §14.1, §13 |
| 8 | **technical-test-guidelines** §2, §6, §8 (unit tests never import `lore.cli`) | `SpaceSeparatedChoice` listed as a §14.2 **unit** coverage component, though it is defined in `cli.py` and its five cases need a `CliRunner` | Removed from §14.2 with the guideline quoted, and its five cases folded into the §14.1 Space-separated multi-value E2E scenario. The existing `test_cli_codex_list.py` breach is named, not inherited | §14.1, §14.2 |
| 9 | **ADR-014** (codex → code, `binds` held on the codex side) | The four new codex documents were listed with no `binds:` and no rule about inbound links from canonical docs | A `binds:` column added to the new-document table; `tech-arch-agents-md` picks up `agents.py` and `agents.yaml`; plus the rule that no canonical doc may `related:` a `codex/transient/` document that this feature deletes | §13 |
| 10 | **ADR-011** (parity of accepted tokens) | `--skills` accepts `all` and `none`, but §9.1's `init-skill-families` allows only the three concrete families, with nothing saying where the aggregates resolve or whether `plan_init` accepts them | Aggregates resolve in `skills.resolve_families()` in the business layer, are accepted identically on both surfaces, and are never persisted; plus a sentence naming the four validators as how ADR-017's "the business function may also reject an unknown token" half is satisfied | §5.3 |

### Coverage filled

Cross-cutting gaps closed directly in the spec.

| # | Gap | Filled with | Required by | §  |
|---|---|---|---|---|
| 1 | `REMOVE` hard-unlinks files, and the spec never addressed the soft-delete rule | A boundary paragraph: ADR-003's Scope covers entities managed by the `lore` CLI; a skill has no `lore delete` path, no ID retrieval and no CRUD surface. The hash test is what replaces the guarantee — only bytes Lore wrote and can reproduce are ever destroyed | **ADR-003** | §6.4 |
| 2 | Two new packaged schema kinds with no statement on overlayability, while `resolve_merged_schema(kind, project_root)` is generic over `kind` | Both validate through `load_schema(kind)` and never through the overlay resolver; `.lore/custom-schemas/agents.yaml` is not a recognised overlay path; v1 overlay kinds stay as ADR-018 lists them | **ADR-018** | §8.2 |
| 3 | `tech-arch-api-facade` absent from the update list, though its underscore-alias block is enumerated verbatim and gains three entries | Added to §13's Updated list, with both stale parts named | **ADR-010**, `tech-arch-api-facade` | §13 |
| 4 | `ref-lore_cli-commands`'s `lore init` row still documents the `AGENTS.md` → `AGENTS.md.old` backup branch — the same phantom behaviour FR-35 removes from `tech-arch-agents-md` | Named explicitly in §13's Updated entry for that document | FR-35, **ADR-020** (current state) | §13 |
| 5 | `tech-arch-source-layout` lines 83–84 list four skills by name, every one of them retired by §7.1 | Named explicitly in §13's Updated entry | §7.1 retirement ledger | §13 |
| 6 | `conceptual-workflows-json-output` records `lore oracle --json` as accepted-and-ignored at exit 0; `src/lore/cli.py:352-358` rejects it at exit 2. §3.1's first reason turns on that difference | The correction is called out as a precondition of the §3.1 ruling, not a tidy-up, and added to §13's Updated entry for the document | **ADR-020**, §3.1 | §3.1, §13 |

### Unrecorded decisions

New architectural choices for the tech-writer to record. None contradicts a settled ADR.

| Decision | Home | Action |
|---|---|---|
| `SpaceSeparatedChoice` as the mechanism for a command needing more than one multi-value flag, and the private-Click-parser dependency it carries | **`decisions-012-multi-value-cli-param-convention`, amended in place** — not a new ADR | Correct the Decision's `nargs=-1` (unavailable on options) and the Consequences' claim about `lore health --scope`; name the subclass; record the `click>=8.3` floor as the guard. Add a dated `## Status History` row |
| ADR-001's `--json` bullet narrowed to match the recorded permanent exception | `decisions-001-dumb-infrastructure`, in place | Folded into the amendment the PRD already commits to; one extra clause, same Status History row |
| `new-custom-schema` → `update-custom-schema` in ADR-018's body (lines 68, 115) | `decisions-018-overlays-are-path-discovered-config`, in place | Name correction only. The decision is unchanged, so **no** Status History row |
| Agent-native mode's per-entity carve-out | `decisions-006-id-references`, in place | Already in §13. Adds the ADR's first Status History table |
| The config-header exception to seed-in-place | `decisions-013-toml-for-config-yaml-for-glossary`, in place | Already in §13 |
| The human-first interactive command class | `decisions-001-dumb-infrastructure`, in place | Already in §13, committed by the PRD |

Four ADRs are amended in place (001, 006-id-references, 012, 013) and one takes a name-only correction (018). No superseding ADR is created and none is marked superseded.

### Deferral violations

None. Every item the PRD defers is carried as Deferred or Rejected in §1 with its PRD trace: user-scope skill installation, the seven unverified agent conventions, a `lore skill` command group, symlinking, migrating an edited skill's content, and a `verified` registry field. No section builds any of them.

### Escalations

Two, both for the human gate. Neither blocks planning.

1. **The `click` floor moves `>=8.0` → `>=8.3`.** This narrows the environments Lore installs into, which is a product decision rather than an ADR consequence. The alternative is to keep `>=8.0` and have the implementation mission verify the parser hook against 8.0, 8.1 and 8.2 before shipping. The spec takes the conservative option because ADR-017 makes the exit-2 behaviour a contract and a silently-degraded greedy tail breaks it at runtime; the gate may prefer the verification route.
2. **ADR-017's Constraint 3 says a mechanism change "requires a superseding ADR."** This project amends ADRs in place and never marks one superseded — §13 says so, and ADRs 013/017/020/021 all carry in-place `## Status History` tables. ADR-017's own wording contradicts the practice it lives under. This feature changes nothing about ADR-017, so no action is taken here; the inconsistency is flagged because the next architect who does need to change a constrained-flag mechanism will read "superseding ADR" as an instruction.

### Verdict

**RECONCILED.**

---

## 19. Spec Gate — Review Notes

**Reviewed:** 2026-08-25 · **Verdict:** approved, proceed to Phase 5.

Reviewed by the orchestrator under the standing autonomous authorization the user granted when starting this quest, not by the user directly. The audit verdict is `RECONCILED`, both escalations resolve against recorded project practice rather than product preference, and no deferral violations were found — the conditions the orchestrator set for acting in the user's stead. The user reviews this section retrospectively.

### Escalation 1 — Click floor raised to `>=8.3,<9.0`: upheld

The conservative option stands. Evidence gathered at the gate:

- The project already develops and tests on Click 8.3.2 — `.venv` resolves to it, and `tests/e2e/test_api_parity_codex.py` already uses the 8.3 `result.stderr` API behind `hasattr` guards.
- Lore installs via `uv tool install`, so a fresh resolve takes current Click. The narrowed floor excludes almost no real install.
- The failure mode decides it. A parser hook that silently stops consuming on an older in-range Click breaks ADR-017's exit-2 contract **at runtime**, on a user's machine, as a wrong exit code rather than an error. Verifying on 8.0/8.1/8.2 would trade an install-time failure for a runtime one, and would have to be re-verified on every patch release of a private API.

No implementation mission needs to verify the parser hook on 8.0–8.2.

### Escalation 2 — ADR-017 constraint 3 contradicts amend-in-place: fix it here

ADR-017 constraint 3 states that a mechanism change "requires a superseding ADR". This project amends ADRs in place — body edit plus a dated `## Status History` row — and never marks one superseded. The constraint is wrong about project practice, and the enforcer is right that the next architect will read it as an instruction.

Treat it exactly as ADR-012's mechanism prose was treated: the decision is intact, only the prose is wrong. **Add ADR-017 to the in-place amendment list in §13**, correcting constraint 3 to require an in-place amendment with a Status History row. This is a correction to recorded practice, not a new decision, so it needs no ADR of its own.

That brings the amendment list to five in place — 001, 006-id-references, 012, 013, 017 — plus the name-only correction to 018. Still no superseding ADR.

### Confirmed without change

- `--json` on `lore init` stays accepted-and-ignored at exit 0. Copying `lore oracle`'s exit-2 rejection would break `lore --json init` in existing pipelines, which the PRD's headless success criterion forbids.
- Correcting `conceptual-workflows-json-output` on `lore oracle` is a precondition, not a tidy-up. Reason 1 above turns on the doc disagreeing with `cli.py:352-358`, so the doc must be right before it can be cited.
- Package-data agent registry, `initplan.py` as a stdlib-only leaf, and the FR-28 reading all stand as the architect settled them.

### One note for Tech Planning

The ten reconciliations moved real behaviour, most consequentially `--agent none` exclusivity out of `cli.py` into `validators.validate_agent_selection`. Story acceptance criteria must test that rule through **both** surfaces. A story that only asserts the CLI `UsageError` recreates the ADR-011 breach the enforcer just removed.
