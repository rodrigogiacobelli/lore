---
id: conceptual-workflows-lore-init
title: lore init Behaviour
summary: What `lore init` does when it runs — the plan/apply split, the ordered write
  sequence from directory creation through database setup, seeded defaults, rendered
  skills, agent instruction files and the install manifest, plus the idempotency
  guarantees, the headless defaults, and the accepted-and-ignored `--json` flag.
binds:
- src/lore/init.py
- src/lore/cli.py
- tests/e2e/test_lore_init.py
- tests/e2e/test_init_root_gitignore_retired.py
- tests/unit/test_lore_init.py
related:
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
- ref-lore_cli-commands
---

# `lore init` Behaviour

`lore init` initialises a Lore project in the current working directory. It runs in two halves: it **plans**, then it **applies**.

Planning reads the project as it stands, works out every file the current Lore release would write, remove or leave alone, and produces that list without touching disk. Applying performs the list. Nothing is written before the plan exists, which is what lets `lore init` show a person the whole change set and ask for confirmation before the first byte lands.

`lore init` is **idempotent**. Running it twice in succession with the same answers produces the same files and reports no second round of changes.

Every seed file `lore init` ships — default doctrines, knights, watchers, artifacts, skills, and the seeded codex root — must pass `lore health --scope schemas` on a freshly-initialised project. A default file that fails its JSON Schema is an install-time regression, because the first health check after install emits schema errors on seed content.

`tech-arch-initialized-project-structure` holds the resulting on-disk layout.

## What the Plan Depends On

Four answers shape the plan:

| Answer | What it decides |
|---|---|
| Agents | Which coding agents the project uses. Each selected agent has an instruction file and, for some, a native skills directory. |
| Access mode | Whether the installed skills tell agents to operate Lore's local files through the Lore CLI (`cli`) or with their own file tools (`native`). |
| Skill families | Which of the three seeded skill families — memory, machinery, workflow — install. |
| Skills gitignore | Whether the installed skills are tracked in version control. |

A person at a terminal answers them at a prompt; `conceptual-workflows-init-interactive` describes that flow and the command-line flag equivalent to each answer. A caller with no terminal answers them with flags, with keyword arguments to `plan_init`, or not at all.

`lore init` records all four in `.lore/config.toml` and reuses them on every later run, so a project is asked once. `--reconfigure` asks again, and asking needs a terminal: a run without one passes the four as flags or stops with a usage error, because the recorded answers are the only record of what the project installed.

### Headless defaults

When no answer is supplied by any means — no flag, no recorded value, no terminal — `lore init` selects: no agents, all three skill families, access mode `native`, skills installed at `.lore/skills/`, and no agent instruction file. That is the same file set `lore init` produced before it could ask anything, so a Realm deployment or a CI pipeline that upgrades Lore gets what it got before.

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

`.lore/doctrines/`, `.lore/knights/`, `.lore/artifacts/`, and `.lore/watchers/` are created if absent. Each shipped default file is copied into that entity's `default/` subdirectory, overwriting the matching shipped name. User-created files in the flat parent directory are never touched.

Artifacts copy recursively, preserving the subdirectory structure beneath `default/` (`default/codex/`, `default/feature-implementation/`, `default/lore-design-documents/`, `default/rites/`). The `bootstrap/` subdirectory is permanently excluded from what `lore init` copies.

The summary prints `Created <entity>/default/<path>` for a new file and `Updated <entity>/default/<path>` for an overwrite.

### 5. `.lore/GETTING-STARTED.md`

Copied verbatim from the package.

### 6. User-tracked skeletons

Three files hold user-owned content and therefore live outside any `default/` subtree:

- **`.lore/codex/CODEX.md`** — the project codex root. Written when absent by copying the packaged `example-codex` artifact and rewriting its `id:` line to `codex`. Skipped when present, even if edited.
- **`.lore/codex/glossary.yaml`** — a two-line header comment plus `items: []`. Skipped when present, even if edited.
- **`.lore/config.toml`** — when absent, written with a comment header documenting every known key followed by each key at its default. When present, every setting line survives byte-identical and only the leading comment header is regenerated, from `config.py`'s own key tables. A project that predates a key finds that key documented after the next `lore init`.

These are the two narrow exceptions to the rule that `lore init` does not seed `.lore/codex/` (`decisions-013-toml-for-config-yaml-for-glossary`), plus the project config file. The summary prints `Created codex/CODEX.md`, `Created codex/glossary.yaml` and `Created config.toml` for new files and prints nothing for a file left alone.

### 7. Empty rite directories

`.lore/rites/main/` and `.lore/rites/shared/` are created if absent and left empty.

### 8. Rendered skills

Each skill in a selected family is rendered — its access-mode blocks resolved to the recorded mode — and written to every place a selected agent reads skills from. An agent with a native skills directory receives them there; an agent without one, and a project with no agent selected at all, receives them at `.lore/skills/`. `conceptual-entities-skill` holds the install-destination rules and `tech-arch-skill-catalogue` holds the catalogue and the renderer.

### 9. `.lore/LORE-AGENT.md`

The rendered agent instruction text, always written. Its access-mode blocks resolve to the recorded mode and its skills table lists exactly the skills installed and where they landed.

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
