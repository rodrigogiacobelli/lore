---
id: conceptual-workflows-lore-init
title: lore init Behaviour
summary: What `lore init` does when it runs — the plan/apply split, the answers that
  shape the plan, the ordered write sequence from directory creation through database
  setup, seeded defaults, rendered skills, agent instruction files and the install
  manifest, plus the idempotency guarantees, the headless defaults, and the
  accepted-and-ignored `--json` flag.
binds:
- src/lore/init.py
- src/lore/cli.py
- tests/e2e/test_lore_init.py
- tests/e2e/test_init_root_gitignore_retired.py
- tests/unit/test_lore_init.py
related:
- conceptual-workflows-init-features
- conceptual-workflows-init-interactive
- conceptual-workflows-init-reconcile
- conceptual-workflows-json-output
- conceptual-workflows-health
- conceptual-workflows-glossary
- conceptual-entities-glossary
- conceptual-entities-skill
- tech-arch-initialized-project-structure
- tech-arch-agents-md
- tech-arch-install-manifest
- tech-arch-skill-catalogue
- tech-arch-schemas
- decisions-001-dumb-infrastructure
- decisions-013-toml-for-config-yaml-for-glossary
- decisions-018-overlays-are-path-discovered-config
- decisions-021-health-reports-are-ephemeral-by-default
- decisions-037-index-is-a-top-level-lore-directory
- conceptual-workflows-index
- decisions-032-retired-seed-trees
- ref-lore_cli-commands
---

# `lore init` Behaviour

`lore init` initialises a Lore project in the current working directory. It runs in two halves: it **plans**, then it **applies**.

Planning reads the project as it stands, works out every file the current Lore release would write, remove or leave alone, and produces that list without touching disk. Applying performs the list. Nothing is written before the plan exists, which is what lets `lore init` show a person the whole change set and ask for confirmation before the first byte lands.

`lore init` is **idempotent**. Running it twice in succession with the same answers produces the same files and reports no second round of changes.

Every seed file `lore init` ships — default doctrines, watchers, artifacts, skills, and the seeded codex root — must pass `lore health --scope schemas` on a freshly-initialised project. A default file that fails its JSON Schema is an install-time regression, because the first health check after install emits schema errors on seed content.

`tech-arch-initialized-project-structure` holds the resulting on-disk layout.

## What the Plan Depends On

The plan depends on these answers:

| Answer | What it decides |
|---|---|
| Agents | Which coding agents the project uses. Each selected agent has an instruction file and, for some, a native skills directory. |
| Routes | For each of Memory, Doctrines, Artifacts and Watchers, whether agents read it and write it with their own file tools (`harness`), with `lore` commands (`cli`) or not at all (`off`). A feature with both routes `off` is not installed. |
| Opt-in capabilities | Six yes/no answers that teach `lore health`, `lore index` and the codex graph commands for the features that are on. |
| Quests | Whether the quest and mission commands are taught. It needs the Lore CLI and nothing else. |
| Skills gitignore | Whether the installed skills are tracked in version control. |

`conceptual-workflows-init-features` holds the feature model, the rules for which answers apply and what each combination installs. A person at a terminal answers them at a prompt; `conceptual-workflows-init-interactive` describes that flow and the command-line flag equivalent to each answer. A caller with no terminal answers them with flags, with keyword arguments to `plan_init`, or not at all.

`lore init` records every answer in `.lore/config.toml` and reuses them on every later run, so a project is asked once. `--reconfigure` asks again, and asking needs a terminal: a run without one passes the answers as flags or stops with a usage error, because the recorded answers are the only record of what the project installed.

A project recorded under the earlier `init-access-mode` and `init-skill-families` keys is migrated once. `--access` and `--skills` remain as deprecated aliases for the route and feature answers; the unreleased per-feature keys (`init-<feature>-read` and the like) are migrated the same way.

### Headless defaults

When no answer is supplied by any means — no flag, no recorded value, no terminal — `lore init` selects: no agents unless the project's own files show one, Memory read and write on the `harness` route, Doctrines, Artifacts and Watchers read and write on the `cli` route, every opt-in capability on, Quests on, skills installed at `.lore/skills/`, and no agent instruction file. All ten skills and every seeded default install, so a Realm deployment or a CI pipeline that upgrades Lore gets the file set it got before it could ask anything.

## The Write Sequence

`apply_init` writes in a fixed order, and the install manifest last.

### 1. `.lore/` directory

Created if absent. Skipped if present.

### 2. `.lore/.gitignore`

Overwritten from the seed template on every run, so the rules stay current. The template ignores Lore's internal files — database, reports, soft-delete artefacts — while keeping the `.gitignore` file itself, the `codex/` documentation directory, `config.toml`, `custom-schemas/` and the user-owned entity files tracked. Inside each entity directory the `default/` subtree is re-ignored so Lore-seeded defaults are not committed. `tech-arch-initialized-project-structure` holds the template verbatim.

### 3. `lore.db`

If `lore.db` is absent, a fresh database is created at the current schema version and `lore init` reports that version. If it is present, the schema version is checked and pending migrations run.

If `lore.db` is present but has no `lore_meta` table — a corrupted or hand-made database — every table is dropped and the schema is recreated. `lore init` prints `Existing database appears corrupted. Reinitialized lore.db`.

### 4. Seeded default trees

`.lore/doctrines/`, `.lore/artifacts/`, and `.lore/watchers/` are created if absent. Each shipped default file that the project's answers keep is copied into that entity's `default/` subdirectory, overwriting the matching shipped name. User-created files in the flat parent directory are never touched.

A shipped default file is kept when every feature and capability its content speaks of is on (`conceptual-workflows-init-features` lists the conditions). A file the answers do not keep counts as a file the release no longer ships: it is not written, and when it is on disk the run removes it with `Removed <label>/<path> — no longer shipped`. Turning Watchers off therefore removes `.lore/watchers/default/` on the next run.

Artifacts copy recursively, preserving the subdirectory structure beneath `default/` (`default/codex/`, `default/feature-implementation/`, `default/lore-design-documents/`, `default/rites/`). The `bootstrap/` subdirectory is permanently excluded from what `lore init` copies.

The summary prints `Created <entity>/default/<path>` for a new file and `Updated <entity>/default/<path>` for an overwrite.

#### Retired seeded trees

A seeded tree Lore has stopped shipping is named in `init.RETIRED_SEED_TREES` and walked once per run. Every regular file inside it is unlinked and reported as `Removed <label>/<path> — no longer shipped`, the emptied directories are pruned, and a symlink or an unlinkable file is left exactly where `_prune_seeded_tree` would leave it.

Dropping a row from `SEEDED_TREES` is not enough on its own: the prune is reachable only from the seed, so a tree no longer seeded would never be walked again and every file in it would stay on disk forever. `RETIRED_SEED_TREES` is what walks it one last time (lore codex show decisions-032-retired-seed-trees).

Files the project authored **outside** the retired subtree are not touched. They are collected and named once, so the maintainer knows Lore no longer reads them:

```
  Knights outside default/ are no longer read by Lore: .lore/knights/my-reviewer.md
```

### 5. `.lore/GETTING-STARTED.md`

Rendered from blocks for the project's answers and written through the atomic-write path. It names `lore init` and `lore health` only when some CLI is taught, and a feature's directory only when that feature is on. It is not written when no feature is on.

### 6. User-tracked skeletons

Three files hold user-owned content and therefore live outside any `default/` subtree. The codex root and the glossary are written only when Memory is on:

- **`.lore/codex/CODEX.md`** — the project codex root. Written when absent by copying the packaged `example-codex` artifact and rewriting its `id:` line to `codex`. Skipped when present, even if edited.
- **`.lore/codex/glossary.yaml`** — a two-line header comment plus `items: []`. Skipped when present, even if edited.
- **`.lore/config.toml`** — when absent, written with a comment header documenting every known key followed by each key at its default. When present, every setting line survives byte-identical and only the leading comment header is regenerated, from `config.py`'s own key tables. A project that predates a key finds that key documented after the next `lore init`.

These are the two narrow exceptions to the rule that `lore init` does not seed `.lore/codex/` (`decisions-013-toml-for-config-yaml-for-glossary`), plus the project config file. The summary prints `Created codex/CODEX.md`, `Created codex/glossary.yaml` and `Created config.toml` for new files and prints nothing for a file left alone.

### 7. Empty rite directories

`.lore/rites/main/` and `.lore/rites/shared/` are created if absent and left empty. They are created only when Memory is on.

`.lore/index/` is not among them. `lore init` seeds neither half of the codex index and creates neither the directory nor a file inside it; the first `lore index build` creates the directory on its way to writing the render (`decisions-037-index-is-a-top-level-lore-directory`). What `lore init` does write for the index is the `.lore/.gitignore` template's `!index` / `!index/**` / `index/codex.json` lines, which keep the authored half tracked and the render ignored — see `tech-arch-initialized-project-structure`.

### 8. Rendered skills

Each skill that has at least one surviving block is rendered from the blocks the project's answers keep, and written to every place a selected agent reads skills from. An agent with a native skills directory receives them there; an agent without one, and a project with no agent selected at all, receives them at `.lore/skills/`. `conceptual-entities-skill` holds the install-destination rules and `tech-arch-skill-catalogue` holds the catalogue and the renderer.

### 9. `.lore/LORE-AGENT.md`

The rendered agent instruction text, assembled from the blocks the answers keep and at most 100 lines long. It is written whenever any feature is on. When none is, the file and every agent's marked block are removed. Its skills table lists exactly the skills installed and where they landed.

### 10. Agent instruction files

For each selected agent, the same rendered text is written into that agent's instruction file inside `<!-- lore:begin -->` / `<!-- lore:end -->` markers. Content outside the markers is never touched. `tech-arch-agents-md` holds the registry of agents, their instruction-file paths, and the marker mechanism.

### 11. Skills gitignore

Under the `lore-only` answer, a `.gitignore` listing the installed skill directories is written at each install root, so Lore's skills stay untracked while the project's own skills in that directory are not ignored. `none` writes no file. `all` writes a rule ignoring the whole directory, the project's own skills included, at the same place.

### 12. Removals and directory pruning

Files Lore installed that the current release no longer ships are removed, and directories left empty by those removals are pruned. `conceptual-workflows-init-reconcile` holds the rules that decide what may be removed and what is kept.

The project's root `.gitignore` is one of those removals. Lore used to append a block there inside `# lore:begin` / `# lore:end` markers, naming the database and its WAL and SHM siblings, `.lore/reports/` and the install manifest. Every one of those paths is already ignored by the `*` opening `.lore/.gitignore`, so the block decided nothing — delete it from a real project and `git check-ignore -v` reports the identical deciding rule for every path — and no release writes one. A project that still carries it has the marked block deleted and every line outside the markers left byte-identical; a `.gitignore` that held nothing but the block and whitespace is one Lore created and is removed with it. A `.gitignore` with no markers, or none at all, is never read, written or created.

### 13. `.lore/.install-manifest.json`

Written last, recording every file the run wrote and its hash. Writing it last means an interrupted run leaves the previous manifest in place, and the next `lore init` reconciles the half-written project to a correct state. `tech-arch-install-manifest` holds the format.

### 15. Summary

A summary of what was created, updated, removed and kept is printed to stdout.

## What `lore init` Does Not Create

`.lore/reports/` is not created by `lore init`. `lore oracle` creates it on first run.

`.lore/custom-schemas/` is not created by `lore init`. Its absence is the zero-overlay baseline (`decisions-018-overlays-are-path-discovered-config`).

`.lore/codex/` is not seeded with documentation, with the two exceptions in step 6. Documentation is written by agents or by hand.

## `--json`

`lore --json init` is accepted, has no effect, and exits 0 with the same text output as `lore init`. A pipeline that passes the global flag to every command still initialises a project. `lore init --help` states this and points at the Python API instead: `plan_init()` returns a typed plan describing every create, overwrite, removal and conflict without performing any of them.

This is one of the two commands `ref-lore_cli-commands` records as a permanent exception to JSON support. `conceptual-workflows-json-output` holds the difference between the two: `lore init` ignores the flag at exit 0, `lore oracle` rejects it at exit 2.

## Documentation Setup Workflows

After initialisation, project documentation is set up using one of three bundled codex doctrines — not by running scripts or copying templates:

- **`codex-greenfield`** — for a new project with no existing documentation. Scaffolds the conceptual, technical and operations layers.
- **`codex-brownfield-no-docs`** — for an existing codebase with no documentation. An agent reads the source tree, extracts entities and workflows, and writes documentation across all layers.
- **`codex-brownfield-migration`** — for a project whose documentation is in a non-codex format. An agent audits, critiques and migrates existing content into the codex layout.

Each doctrine embeds the guidance an agent needs to complete the work without consulting an external guide.
