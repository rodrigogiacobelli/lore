---
id: conceptual-workflows-init-features
title: Init Features and Routes
summary: The feature model `lore init` installs from - the always-on core (Doctrines,
  Artifacts, `lore health`), the one global route, Memory with its search, index and
  graph opt-ins, Quests & Missions and the derived doctrine-quest link, Watchers, the
  questions asked in order and when each is skipped, what each answer installs (skills,
  instruction text, getting-started page, seeded defaults), the line caps and the
  no-leaked-command guarantee, the headless defaults, and the deprecated `--access` and
  `--skills` aliases and the retired per-feature keys with their one-time migration.
binds:
- src/lore/initplan.py
- src/lore/blocks.py
- src/lore/blocklint.py
- src/lore/legacy_init.py
- src/lore/skills.py
- src/lore/defaults/blocks/**
- src/lore/defaults/skills-catalogue.yaml
- tests/e2e/test_init_features.py
- tests/unit/test_initplan.py
- tests/unit/test_blocks_shipped.py
related:
- conceptual-workflows-lore-init
- conceptual-workflows-init-interactive
- conceptual-workflows-init-reconcile
- conceptual-workflows-health
- conceptual-entities-skill
- tech-arch-skill-catalogue
- tech-arch-agents-md
- tech-arch-install-manifest
- tech-arch-initialized-project-structure
- decisions-001-dumb-infrastructure
- decisions-006-id-references
- decisions-006-no-seed-content-tests
- decisions-011-api-parity-with-cli
- decisions-013-toml-for-config-yaml-for-glossary
---

# Init Features and Routes

**Role: the person deciding what Lore does in their project.** `lore init` installs the skills, instruction text, getting-started page and seeded defaults that the project's chosen features use, and nothing else. A project that keeps its documentation as files and never touches the Lore CLI receives instruction text with one `lore` command in it: `lore health`.

## The Core and the Route

**Doctrines**, **Artifacts** and **validation** (`lore health`) are the core. They are always installed and cannot be turned off. The only choice about them is the mechanism, answered once for the whole project:

| Route | Meaning |
|---|---|
| `harness` | The agent uses its own file tools (Read, Write, Edit, Grep) on the files under `.lore/`. |
| `cli` | The agent uses `lore` commands. |

The route is cross-feature: Doctrines, Artifacts, Memory read and write, and Watchers all follow it. There is no per-feature route and no way to tell agents nothing. Validation is not a route question: `lore health` is the Lore CLI whatever the route, so a harness project is still taught `lore health` and no other command unless it opts in.

## Optional Features

| Feature | Holds | Needs the Lore CLI | Question |
|---|---|---|---|
| Memory | codex, rites, glossary | No: read and write follow the route | `--memory` |
| Memory search | `lore codex search`, `lore rite search`, `lore glossary search` | Yes | `--memory-search` |
| Memory index | `lore index search`, `lore index build` and the `update-index` skill | Yes | `--memory-index` |
| Memory graph and bindings | `lore codex map`, `lore codex chaos`, `lore impacts` | Yes | `--memory-graph` |
| Quests & Missions | quests, missions, board, `lore.db` | Yes | `--quests` |
| Watchers | `.lore/watchers/` | No: follows the route | `--watchers` |

A feature that needs the Lore CLI is a plain yes or no. A project that picked `harness` at the top and then adds Quests or Memory search uses the CLI for those parts; there is no per-feature harness option for them. The three Memory opt-ins are asked, and mean something, only while Memory is on; `Profile.normalized` drops them otherwise.

## The Doctrine-Quest Link

Doctrines are always on, so Quests is always legal and the link is **derived** whenever Quests is on: the `/start-quest` skill, the instruction text that starts a quest from a doctrine with `-D`, and the orchestrator reading a doctrine. It is never a question. Without Quests, nothing teaches the quest commands or `-D`; the core `/run-doctrine` skill, installed with Doctrines, runs the doctrine itself: it plans the missions from the design table, asks before dispatching, briefs a worker for each `agent` mission, does `constable` missions inline, stops for `human` missions and keeps a visible checklist, with no quest or mission command.

## The Questions

An interactive run asks, in this order, each question that no flag, no recorded answer and no earlier answer settles:

1. Agents.
2. The route, then Memory, Memory search, Memory index, Memory graph, Quests and Watchers. The three Memory opt-ins are skipped while Memory is off.
3. Whether to append to an existing instruction file, how installed skills are tracked in git, and how to resolve conflicts, each only when its case arises.
4. The confirmation.

`Profile.applies` in `lore.initplan` holds the skip rule, and the command line asks whatever it reports. The cursor at the route question is the recorded or migrated route, else `cli`. The default at each yes/no question is the recorded or migrated value, else no. `conceptual-workflows-init-interactive` holds the flag for each question.

## Resolving the Answers

`plan_init` resolves every answer in one order: an explicit argument, then a deprecated alias translation, then the value recorded in `.lore/config.toml`, then the base layer. The base layer is the headless defaults, or the one-time migration when the project records nothing under the current keys.

After the merge, a Memory opt-in with Memory off is dropped. The dropped answer is silent when it came from the config file, an alias or the base layer. It raises an error naming the argument and the rule when the caller passed it explicitly:

```
memory_graph needs Memory on: set memory to true.
```

The command line reports a contradiction that the arguments alone show (`--memory-graph yes --memory no`) as a usage error with exit 2 before reading any file.

## What Each Answer Installs

### Skills

A skill is installed when at least one block of its `SKILL.md` survives the answers. Only `store-memory` ships reference files; every other skill points at the seeded artifact (`lore artifact show <id>` on the CLI route, the path under `.lore/artifacts/default/` on the harness route). A skill with no surviving block is never written, and no instruction text or other skill mentions it.

| Skill | Installed when |
|---|---|
| `update-doctrine`, `update-artifact`, `run-doctrine` | Always |
| `retrieve-memory`, `store-memory`, `update-custom-schema`, `sync-codex-guide` | Memory is on |
| `update-index` | Memory and Memory index are on |
| `update-watcher` | Watchers is on |
| `start-quest` | Quests is on |
| `inquest` | Quests and Memory are on |

Within an installed skill, the route chooses between a harness variant and a CLI variant of each step. A harness variant states what reading files instead of asking Lore gives up: glossary terms are not attached to what the agent reads, a rite's `use:` steps are not inlined, and a document's group is its directory. A step that searches, indexes or traverses the graph appears only when that opt-in is on, and a step that validates always uses `lore health`.

### Instruction text

`.lore/LORE-AGENT.md` and the marked block inside each selected agent's instruction file hold the same text, assembled from the blocks that survive. The text never exceeds 100 lines including its two marker lines. The skills table lists exactly the installed skills.

### The getting-started page

`.lore/GETTING-STARTED.md` is rendered from blocks by the same rules. It mentions a feature's directory only when that feature is on.

### Seeded defaults

Seeding follows the owning feature of the content. Doctrines and Artifacts are core, so their defaults are written for every project except the files whose subject is an optional feature:

| Seeded content | Written when |
|---|---|
| `.lore/` directory, `.lore/.gitignore`, `lore.db`, `config.toml`, `GETTING-STARTED.md` | Always |
| Every default doctrine, including `update-changelog` | Always |
| The artifacts `feature-implementation/*` and `lore-design-documents/doctrine-design.md` | Always |
| `.lore/codex/codex.md`, `.lore/codex/glossary.yaml`, `.lore/rites/`, the artifacts `codex/`, `rites/` and the codex, glossary, rite and inquest design documents | Memory is on |
| The artifact `lore-design-documents/mission-design.md` | Quests is on |
| `watchers/default/change-log-updates.yaml` | Watchers is on |

A file a profile does not keep is not written, and when it is on disk the prune removes it as a file the release no longer ships. Turning a feature off therefore removes its `default/` tree, its skills and its instruction text through the reconciliation that already exists. Files the project authored, `codex.md` and `glossary.yaml` are never removed.

The seeded doctrines are written for the full Lore. A harness project still receives them, and their `lore` lines are the cost of that choice (`scripts/check_seed_gates.py` counts them).

### Reference documents

A Lore-shipped reference document (the codex voice rules, the rite design guide, the doctrine and mission design documents, the inquest method) is named by id with `lore artifact show` on the `cli` route, and by its path under `.lore/artifacts/default/` on the `harness` route.

## The Guarantees

Every instruction text and every skill file is assembled from tagged blocks, and the block set is checked mechanically:

| Guarantee | Bound |
|---|---|
| Instruction text | At most 100 lines for every combination of answers |
| A skill file | At most 100 lines, except `store-memory` (150 and its three references), `update-index` (120), `sync-codex-guide` (110) and `update-doctrine` (110) |
| A command whose feature is off | Appears in no instruction text, skill or getting-started page |
| `lore health` | Granted to every profile |
| A skill with no surviving block | Is not installed and is mentioned nowhere |
| A mention of a skill | Survives only where the skill is installed |

`scripts/check_blocks.py` proves these over all combinations of answers from the tags alone, and `tests/unit/test_blocks_shipped.py` re-checks the rendered output for the fixture profiles and for all 72 distinct profiles. Neither reads a word of prose (`decisions-006-no-seed-content-tests`). `tech-arch-skill-catalogue` holds the block format.

## Worked Profiles

| Profile | Installs |
|---|---|
| Route `harness`, nothing optional | `update-doctrine`, `update-artifact`, `run-doctrine`; every default doctrine and the core artifacts; instruction text whose only commands are `lore health` |
| Route `harness`, Memory only | The same plus `retrieve-memory`, `store-memory`, `update-custom-schema`, `sync-codex-guide`; the codex and rites seeds; still no command but `lore health` |
| The same plus Memory search | The same, and `lore codex search` in the text and the skills |
| Route `cli`, Quests only | `update-doctrine`, `update-artifact`, `run-doctrine`, `start-quest`; the quest commands and the link; the doctrine and artifact commands |
| Route `cli`, everything | All eleven skills and every seed |

## Headless Defaults

With no flag, no recorded answer and no terminal, `lore init` selects route `cli` with Memory, its three opt-ins, Quests and Watchers all on. All eleven skills install and every seed ships. No agent is selected unless the project's own files show one (`conceptual-workflows-lore-init`).

## Deprecated Aliases and Migration

`--access {cli,native}` and `--skills FAMILY [FAMILY ...]` remain accepted. `lore.legacy_init` translates both onto the answers above, and `plan_init(access_mode=..., skill_families=...)` takes the same tokens, so the command line and the Python API behave identically. The command line prints one `Warning:` sentence per alias to stderr naming the replacement flags; `InitPlan.notices` carries the same sentences.

| Alias | Becomes |
|---|---|
| `--access native` | `--route harness` |
| `--access cli` | `--route cli` |
| `--skills F...` | The complete profile for those families, with the access mode given or the current route |
| `--skills none` | Nothing optional: the core alone |

A flag for the new answers given in the same call overrides the alias for that one answer.

Two earlier models are migrated once, with a notice:

| Source | New answers |
|---|---|
| `init-access-mode` and `init-skill-families` (pre-0.14) | Family `memory`: Memory with search, index and graph on. Family `workflow`: Quests on. Family `machinery`: Watchers on. The route follows the access mode (`native` is `harness`), except that a project with `machinery` or `workflow` but no `memory` keeps `cli`, because those skills always used the CLI. |
| The fifteen `init-<feature>-read/-write/-validate` keys of the pre-release 0.14.0 build | Memory on when either Memory route was not `off`; search on when the Memory read route was `cli`; index, graph and Quests keep their values; Watchers on when either Watchers route was not `off`; the route is `cli` when any route that was on was `cli`, else `harness`. The validate keys carry nothing forward. |

`apply_init` writes the ten answers to `.lore/config.toml`, so the second run finds recorded answers and does not migrate. The retired keys stay in the file, untouched and ignored (`decisions-013-toml-for-config-yaml-for-glossary`).
