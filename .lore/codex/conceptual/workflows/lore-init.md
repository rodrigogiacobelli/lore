---
id: conceptual-workflows-lore-init
title: lore init Behaviour
summary: What the system does internally when `lore init` runs — the ordered sequence of steps from directory creation through database setup, default file seeding (doctrines, knights, artifacts), and AGENTS.md management. Covers idempotency guarantees and the AGENTS.md marker mechanism.
related: ["tech-arch-initialized-project-structure", "tech-arch-agents-md"]
stability: stable
---

# `lore init` Behaviour

`lore init` is **idempotent**. Running it multiple times does not corrupt or overwrite existing data. Each run follows the same ordered sequence of steps.

For what `lore init` creates on disk (the `.lore/` directory layout and file purposes), see tech-arch-initialized-project-structure (lore codex show tech-arch-initialized-project-structure).

## Step Sequence

### 1. Create `.lore/` directory

If `.lore/` does not exist in the current working directory, it is created. If it already exists, this step is skipped.

### 2. Create or update `.lore/.gitignore`

If `.lore/.gitignore` does not exist, it is created with default contents that ignore Lore's internal files (database, reports, soft-delete artefacts) while keeping the `.gitignore` file itself, the `codex/` documentation directory, and user-owned entity files tracked by version control. The `default/` subdirectory within each entity directory is re-ignored so Lore-seeded defaults are not committed to user repositories. If the file already exists, it is overwritten with the latest default contents to ensure the rules are current.

For the authoritative full gitignore template, see tech-arch-initialized-project-structure (lore codex show tech-arch-initialized-project-structure).

### 3. Create or initialise `lore.db`

If `lore.db` does not exist, a fresh database is created with the full schema. If it already exists, the schema version is checked and any pending migrations are run.

If `lore.db` exists but is missing the `lore_meta` table (indicating a corrupted or manually created database), all existing tables are dropped and the schema is recreated from scratch. A warning is printed: `Existing database appears corrupted. Reinitialized lore.db`.

> **Note:** The status message `Created lore.db (schema version 1)` printed by the current implementation contains a stale version number. The actual schema version at creation is 4. This is a known code-level issue (see `init.py` line 54).

### 4. Seed default doctrines

The `.lore/doctrines/` directory is created if it does not exist. Each default doctrine YAML shipped with Lore is copied into `.lore/doctrines/default/`. Files matching shipped default names inside `default/` are **overwritten**. User-created files in the flat parent directory (`.lore/doctrines/`) are not touched.

### 5. Seed default knights

The `.lore/knights/` directory is created if it does not exist. Each default knight markdown file shipped with Lore is copied into `.lore/knights/default/`. Files matching shipped default names inside `default/` are **overwritten**. User-created files in the flat parent directory (`.lore/knights/`) are not touched.

### 6. Seed default artifacts

The `.lore/artifacts/` directory is created if it does not exist. Default artifact template files shipped with Lore are copied recursively into `.lore/artifacts/default/`, preserving the subdirectory structure beneath `default/` (e.g. `default/transient/`, `default/codex/`). Files matching shipped default paths are **overwritten**. User-created files that do not match any shipped default are not touched.

The `bootstrap/` subdirectory is never seeded — it is permanently excluded from what `lore init` copies. The init summary prints `Created artifacts/default/<path>` for newly created files and `Updated artifacts/default/<path>` for files that were overwritten.

### 7. Create or update `AGENTS.md`

`AGENTS.md` is placed at the project root. The template written is the reduced form (~40–50 lines) — a lightweight basics guide that directs agents to `lore --help` for entity and CLI model understanding. It does not reproduce help output or document CLI syntax. The system handles three cases:

- **`AGENTS.md` does not exist:** A fresh Lore `AGENTS.md` is created with the reduced template.
- **`AGENTS.md` contains Lore markers (`<!-- lore:begin -->` and `<!-- lore:end -->`):** The content between the markers is replaced with the latest Lore template. Content outside the markers is preserved.
- **`AGENTS.md` exists without Lore markers:** The existing file is backed up to `AGENTS.md.old` (overwriting any previous backup) and a fresh Lore `AGENTS.md` is written.

For the specification of the generated `AGENTS.md` content and structure, see tech-arch-agents-md (lore codex show tech-arch-agents-md).

### 8. Seed default watchers

The `.lore/watchers/` directory is created if it does not exist. The default watcher YAML shipped with Lore (`change-log-updates.yaml`) is copied into `.lore/watchers/default/`. Files matching shipped default names inside `default/` are **overwritten**. User-created files in the flat parent directory (`.lore/watchers/`) are not touched.

The companion doctrine (`update-changelog.yaml`) is seeded in Step 4 (Seed default doctrines) alongside the existing `adversarial-spec` doctrine.

The init summary prints `Created watchers/default/change-log-updates.yaml` for a newly created file and `Updated watchers/default/change-log-updates.yaml` for an overwrite.

### 9. Print summary

A summary of what was created, updated, or backed up is printed to stdout.

## What `lore init` Does NOT Create

The `reports/` directory is not created by `lore init`. It is created on demand when `lore oracle` runs for the first time.

The `codex/` documentation directory is not seeded by `lore init`. Documentation setup is handled separately through Codex doctrines.

## Documentation Setup Workflows

After initialization, project documentation is set up using one of three bundled Codex doctrines — not by running manual scripts or copying templates:

- **`codex-greenfield`** — For brand-new projects with no existing documentation. A doctrine-driven step sequence that scaffolds conceptual, technical, and operations documentation layers.
- **`codex-brownfield-no-docs`** — For existing codebases with no documentation. An agent reads the source tree, extracts entities and workflows, and writes structured documentation across all layers.
- **`codex-brownfield-migration`** — For projects that already have documentation in a non-Codex format. An agent audits, critiques, and migrates existing content into the structured Codex layout.

Each doctrine embeds all guidance needed for an agent to complete the work without consulting external bootstrap guides. The documentation setup process is fully agent-driven.

## Related

- tech-arch-initialized-project-structure (lore codex show tech-arch-initialized-project-structure) — the `.lore/` directory layout and file purposes
- tech-arch-project-root-detection (lore codex show tech-arch-project-root-detection) — how Lore locates the project root
- tech-arch-agents-md (lore codex show tech-arch-agents-md) — specification of the generated `AGENTS.md`
- tech-cli-commands (lore codex show tech-cli-commands) — `lore init` command reference
