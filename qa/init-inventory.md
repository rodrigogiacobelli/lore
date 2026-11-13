# `lore init` -- QA inventory (route + optional features model)

Machine form: `qa/init-expectations.yaml` (the oracle). Runner: `scripts/qa_init_matrix.py`
(`--only REGEX`, `--random N --seed S`, `--jobs`, `--keep`, `-v`, `--list`, `--report PATH`).
Slice in the normal suite: `tests/qa/test_init_matrix_slice.py` (marker `qa_matrix`).
The oracle is written from the product-owner rule, not from the implementation.

## The rule in one table

| Part | On when | Mechanism | Needs CLI |
|---|---|---|---|
| Artifacts + Doctrines (core) | always | the global route (harness or cli) | no |
| Validate (`lore health`) | always | Lore CLI | yes |
| Memory (codex, rites, glossary) | `memory` | read/write follow the route | no |
| Memory search / index / graph | `memory` + own opt-in | Lore CLI | yes |
| Quests & Missions (incl. `-D`, the start-quest skill, dispatch text) | `quests` | Lore CLI | yes |
| Watchers | `watchers` | read/write follow the route | no |

Answers: `route` harness|cli, `memory`, `memory_search`, `memory_index`, `memory_graph`, `quests`, `watchers`.
Headless defaults: route cli, everything else on.

## Scenario enumeration

| Group | Count | What |
|---|---:|---|
| Fixed matrix | 72 | route 2 x (memory off + memory on x search/index/graph 8 = 9) x quests 2 x watchers 2, agents claude + agents-md |
| Agent samples | 18 | 6 representative profiles x agents {claude}, {agents-md}, {none} |
| Headless | 1 | no answer flags: defaults must be route cli + all on |
| Switches | 8 | same dir init A then B (cli->harness, harness->cli, memory off/on, quests off, watchers off, index off, everything off); result must equal a fresh B |
| Invalid | 2 | bad route token; `--agent none` with another agent (exit 2, nothing written) |
| Migration | 16 | 7 interim-15-key projects + 9 pre-0.14 (`init-access-mode`/`init-skill-families`) projects |
| Random | N | `--random N --seed S` |

Scenario name = `<route>.<m-SIG|m-off>.<q|noq>.<w|now>@<agents>` (S search, I index, G graph).

## Per-profile checks (every scenario)

1. **fixed files** `.lore/{config.toml,.gitignore,.install-manifest.json,lore.db}`.
2. **seeds** exact set (see table below); no seed of an off feature; every shipped artifact must be classified in the oracle.
3. **skills** per agent skills dir == the installed set (table below), no leftover, frontmatter name == dir.
4. **instruction file** per agent: exists, `lore` markers, block <= 100 lines, mentions `lore health`.
5. **commands**: every `lore ...` phrase in instruction block, LORE-AGENT/GETTING-STARTED (if present), every skill + references, must be granted (table below); harness route: no codex/rite/glossary/doctrine/artifact/watcher show|list|new|edit|delete; `-D` only with quests; `start-quest` only with quests; `run-doctrine` is always installed (doctrines are core) and must carry none of `lore new|needs|list|show|ready|board`, ` -D `, `q-xxxx` (oracle `skill_text`).
6. **sizes**: skills <= 100 except store-memory 150, update-index 120, sync-codex-guide 110, update-doctrine 110.
7. **references**: only store-memory has `references/` (codex-doc.md, rite.md, source.md); no link to a missing reference.
8. **extras**: no `{{ }} << >>`; no mention of an uninstalled skill; every mentioned `.lore/...` path exists (illustrative sub-paths under user roots are WARN); off-feature words (codex/rite/glossary; watcher; quest) absent from the instruction text (FAIL) and skills (WARN).
9. **config.toml** holds the answers as `init-route`, `init-memory`, `init-memory-search|index|graph` (memory on), `init-quests`, `init-watchers`.
10. **health**: `lore health` and `lore health --scope skills` exit 0.
11. **idempotent**: second identical run changes no file (hash compare, excluding lore.db and the manifest timestamp); a run that still prints Created/Updated lines is a WARN.

## Expected output by feature

### Seeds

| Seed | Present when |
|---|---|
| all `src/lore/defaults/doctrines/**` -> `.lore/doctrines/default/` | always |
| artifacts `feature-implementation/*` (incl. codex-change-proposal, JC3), `lore-design-documents/doctrine-design.md` | always |
| artifacts `codex/**`, `rites/**`, `lore-design-documents/{codex-voice,glossary-design,rite-design,inquest-design}.md` | memory |
| artifact `lore-design-documents/mission-design.md` | quests |
| `.lore/codex/{codex.md,glossary.yaml}`, `.lore/rites/{main,shared}/` (and these dirs must not exist when memory is off) | memory |
| `.lore/watchers/default/change-log-updates.yaml` | watchers |

### Skills

| Skill | Installed when |
|---|---|
| update-doctrine, update-artifact | always |
| retrieve-memory, store-memory, update-custom-schema, sync-codex-guide | memory |
| update-index | memory and index |
| update-watcher | watchers |
| run-doctrine | always (doctrines are core) |
| start-quest | quests |
| inquest | quests and memory |

### Command grants

| Commands | Granted when |
|---|---|
| `lore health`, `health --scope skills|doctrines|artifacts`, `--help`, `--version`, `--json`, `init` | always |
| `lore doctrine|artifact list|show|new|edit|delete` | route = cli |
| `lore codex|rite|glossary list|show|new|edit|delete` | memory and cli |
| `lore codex|rite|glossary search` | memory and search (any route) |
| `lore index [build|search]`, `health --scope index` | memory and index |
| `lore codex map|chaos|impacts`, `lore impacts`, `health --scope bindings` | memory and graph |
| `health --scope codex|rites|glossary|voice|schemas` | memory |
| `lore watcher list|show|new|edit|delete` | watchers and cli |
| `health --scope watchers` | watchers |
| quest/mission verbs (`new claim done block unblock ready needs unneed deps list missions show stats oracle board edit delete`), `-D` | quests (any route) |

## Judgement calls -- owner please confirm (oracle reports these as WARN, not FAIL)

1. **Memory seeds `.lore/codex`, `.lore/rites` after a switch to memory off**: see 7.
2. **inquest** installed iff quests AND memory; **inquest-design.md** seeded iff memory only (also tied to quests? the rule says only memory).
3. **feature-implementation/codex-change-proposal.md** is treated as CORE (seeded always): the always-on feature-implementation doctrine references it (`fi-codex-change-proposal`), and `lore health` fails with `broken_artifact_ref` when memory is off and it is not seeded. If the owner wants it memory-only, the doctrine's `codex-proposal` mission must go with it.
4. **Other feature-implementation artifacts** (prd, tech-spec, user-story, ...) treated as core, because the always-on doctrines use them. The rule said "feature-implementation artifacts describing quests only with quests"; I found none that qualify. Overrule by changing the `glob` rows in the oracle.
5. **update-custom-schema, sync-codex-guide, `lore health --scope schemas`** owned by memory (codex schemas / codex guide).
6. **`lore rite search` / `lore glossary search`** granted by the search opt-in like `codex search`.
7. **Switching memory on -> off**: the oracle tolerates leftover `.lore/codex`, `.lore/rites`, `.lore/index` (user-owned after seeding) as WARN. The rule text ("removes the files of the dropped part") could mean they must go: say so and I make it a FAIL.
8. **Pre-0.14 family `machinery`** -> watchers on (the only optional feature it contained); doctrines/artifacts are core.
9. **`run-doctrine` is core, `start-quest` is quests-only** (product owner): `run-doctrine` plans, briefs workers, asks, drives and reports with no quest apparatus; `start-quest` creates the quest and missions. The quest-only `i-quests-doctrine-link` and the plain `i-doctrines-run` instruction blocks are mutually exclusive.
9. **Pre-0.14 route**: `init-access-mode` native/cli maps to route harness/cli even when the memory family is absent (workflow/none-only projects); absent mode with families -> harness (the old default was native) although the new headless default is cli.
10. Retired config keys left in config.toml after migration are a WARN, not a FAIL.
11. Skill table: "every installed skill is listed in the instruction file" is NOT enforced (only that no uninstalled skill is named).

Open question for the implementer, not a judgement: flag syntax. The script reads `lore init --help`; it assumes `--route`, and either `--memory/--no-memory` pairs or `--memory yes|no`. One table at the top of `scripts/qa_init_matrix.py` (`BOOL_FLAGS`, `ROUTE_FLAG`).

## Migration cases (hand-derived expectations, see YAML)

| Case | Old project | Expected |
|---|---|---|
| i15-defaults | 15 interim keys, memory harness, rest cli, quests | route cli, memory on, search off (read != cli), index+graph on, quests, watchers |
| i15-all-harness | all harness | route harness, memory, search off, quests, watchers |
| i15-memory-read-cli-only | memory read cli/write off, rest off, quests false | route cli, memory, search on, index off, graph on, no quests/watchers |
| i15-memory-off-harness-rest | memory off, others harness, watchers write only, quests | route harness, memory off, quests, watchers |
| i15-write-only-memory-watchers-cli | memory write harness only, watchers read cli | route cli, memory (search off), watchers |
| i15-everything-off | all off | route harness, nothing on |
| i15-mixed-write-cli | memory write cli | route cli, memory, quests |
| leg-memory-cli / native | family memory | memory + search/index/graph on, route cli / harness |
| leg-workflow-cli / native | family workflow | quests on, route cli / harness |
| leg-memory-workflow-cli | memory + workflow | both |
| leg-machinery-cli | machinery | watchers on (JC8) |
| leg-all-native | all families | everything on, harness |
| leg-none-native | no families | nothing optional |
| leg-memory-no-mode | memory, no access mode | memory, route harness (JC9) |

After migration: new keys correct, a second run changes nothing, `lore health` passes.

## Results

Last run: against `601d202` (impl commits 6fc4976, 601d202), `--random 20 --seed 7`, 137 scenarios, ~25 s with 8 jobs:
2 pass, 113 warn-only, 22 fail.

| Group | Scenarios | Cause |
|---|---:|---|
| health (`broken_artifact_ref: fi-codex-change-proposal`) | all 20 memory-off + 2 migration | the always-on feature-implementation doctrine references the artifact, which is not seeded when memory is off (JC3) |
| skill-refs / skills (`inquest`) | 7 + 1 migration | the instruction text names `/inquest` while the skill is not installed (memory off, quests on); in some migrations the skill is installed (oracle JC2: quests and memory) |
| WARN: `lore health --scope schemas` with memory off | 20 | text names it (oracle: memory owns schemas, JC5) |
| WARN: second run prints `Updated .gitignore` | all | file content unchanged but reported as updated |
| WARN: retired config keys remain after migration | 16 | JC10 |
| WARN: pre-0.14 workflow-only projects get route cli instead of harness | 2 | JC9 |
| WARN: term-leak words in skills, example paths (`.lore/codex/sources`, ...) | many | illustrative text |

Passing: seeds, skills set, sizes, references, command grants, config round-trip, idempotence (file hashes), switches (except memory-off health), invalid inputs.
