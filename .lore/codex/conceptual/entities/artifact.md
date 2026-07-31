---
id: conceptual-entities-artifact
title: Artifact
summary: >
  What an Artifact is — a reusable template file stored in .lore/artifacts/
  and accessed by stable ID via the read-only CLI (list + show). Covers the
  artifact lifecycle, the four namespaces lore init seeds under
  .lore/artifacts/default/ (codex/, feature-implementation/,
  lore-design-documents/, rites/), and what agents and maintainers do with
  artifacts.
related:
  - conceptual-entities-doctrine
  - conceptual-entities-knight
  - conceptual-entities-glossary
  - conceptual-workflows-lore-init
  - tech-arch-initialized-project-structure
  - ref-lore_cli-commands
  - conceptual-relationships-artifact--doctrine
  - decisions-020-codex-voice-is-enforced
---

# Artifact

An Artifact is a reusable template file stored in the project's `.lore/artifacts/` directory. Artifacts provide agents and maintainers with blank scaffolds for producing structured documents — business specifications, full technical specifications, user stories, or any other document type a project needs. Agents retrieve artifacts by their stable IDs through the CLI; they never read `.lore/artifacts/` directly.

Artifacts are first-class Lore entities alongside Doctrines (lore codex show conceptual-entities-doctrine) and Knights (lore codex show conceptual-entities-knight). Like Doctrines and Knights, they are seeded by `lore init`. The CLI provides two read commands: `lore artifact list` (discover artifacts by ID and summary) and `lore artifact show <id> [id ...]` (retrieve the full body of one or more templates). Artifact files are managed directly on disk — there is no CLI command to create or delete artifacts. The CLI is read-only; file management follows the same pattern as codex documents. For CLI commands see ref-lore_cli-commands (lore codex show ref-lore_cli-commands).

## Properties

Every artifact file contains a YAML frontmatter block with three required fields:

- **`id`** — A stable identifier used to retrieve the artifact. Must be unique within the project. IDs are alphanumeric strings that may include hyphens and underscores.
- **`title`** — A short human-readable name displayed in listings.
- **`summary`** — A one-line description of what the artifact contains. Displayed in listings alongside the ID.

The file body after the frontmatter delimiter is the artifact's content — the template scaffold itself. The body is returned verbatim by `lore artifact show` with leading blank lines stripped.

## Python API

`Artifact` is exported from `lore.models` as a typed, immutable dataclass. Python consumers import it as:

```python
from lore.models import Artifact
```

Fields: `id`, `title`, `summary`, `content`. The `content` field holds the full template body (the text below the frontmatter) — note that the underlying `read_artifact()` function returns this as a `"body"` key, but the typed model exposes it as `content` for clarity at the Realm boundary.

`Artifact.from_dict()` accepts the dict returned by `read_artifact()`. It does **not** accept `scan_artifacts()` output — that function returns dicts without a `"body"` key, which causes `KeyError`. Callers must use `read_artifact()` as the construction source.

Artifact objects are immutable — attempting to assign to any field raises `FrozenInstanceError`.

## Lifecycle

Artifacts have two states from the user's perspective:

- **Exists** — The artifact file is present with valid frontmatter. It appears in `lore artifact list` and can be retrieved with `lore artifact show <id>`.
- **Removed** — The file has been deleted or renamed manually on disk. It no longer appears in listings or retrieval.

Artifact files are managed directly on disk. There is no CLI command to create or delete artifacts — add new artifact files by placing a correctly formatted `.md` file in `.lore/artifacts/`, and remove them by deleting or renaming the file directly.

## Shipped Namespaces

`lore init` seeds artifact templates into `.lore/artifacts/default/`, placing four subdirectories inside it:

- **`default/feature-implementation/`** — Blank scaffold templates for the documents an agent pipeline produces: `fi-prd`, `fi-prd-draft`, `fi-tech-spec`, `fi-tech-spec-draft`, `fi-user-story`, `fi-user-story-index`, `fi-context-map`, `fi-codex-change-proposal`, and the two divergent-brainstorm passes `fi-crazy-prd` and `fi-crazy-tech-spec`. Agents retrieve them with `lore artifact show fi-prd` (and the analogous IDs). Doctrine step notes name these IDs, and `lore health` resolves every `fi-` token in a step note against the artifact index.

- **`default/codex/`** — Example codex documents demonstrating well-formed entries across entity, technical, and operations layers. All IDs in this namespace are prefixed `example-` to prevent collision with IDs in the project's own `.lore/codex/`. These serve as reference material for agents producing new codex entries.

- **`default/lore-design-documents/`** — Authoring guides and gates for Lore's own entity types: `codex-voice`, `doctrine-design`, `glossary-design`, `inquest-design`, and `rite-design`. These hold rules rather than blanks — an agent retrieves one to read before authoring, not to fill it in. `codex-voice` is the normative statement of the voice every canonical codex document uses and the rule set `lore health --scope voice` checks (`decisions-020-codex-voice-is-enforced`).

- **`default/rites/`** — Copy-paste skeletons for the two rite shapes: `rite-main` (the node-graph main rite) and `rite-shared-step` (the pure, single-exit shared step).

That an artifact can carry a rule set rather than a blank scaffold is the reason the voice rules ship as an artifact instead of a `standards/` document: `standards/` is project-owned territory, and an artifact reaches every project through `lore init` (`decisions-020-codex-voice-is-enforced`).

The `default/` directory is listed in `.lore/.gitignore` so Lore-seeded artifacts are not committed to user repositories. User-created artifact files placed directly in `.lore/artifacts/` or any subdirectory outside `default/` are git-tracked normally.

## What Users Do with Artifacts

**Orchestrators** discover available artifacts with `lore artifact list` and reference artifact IDs in mission descriptions when assigning template-producing tasks to workers. Doctrine step notes also reference artifact IDs — agents reading a doctrine can see exactly which template to retrieve.

**Worker agents** retrieve the full template body with `lore artifact show <id>`. The body provides the scaffold they fill in to produce the output document. Workers do not navigate `.lore/artifacts/` files directly.

**Project maintainers** add custom artifacts by placing a correctly structured `.md` file with YAML frontmatter in `.lore/artifacts/`. Custom artifacts behave identically to shipped defaults from the agent's perspective — they are discoverable by ID via `lore artifact list` and retrievable with `lore artifact show`.

**Re-initialisation** (`lore init` run on an existing project) overwrites files that match shipped default names with their latest versions. User-created files with non-default names are never touched by re-init. Users who need to customise a default template should create a new artifact with a different name rather than modifying the default file in place.

## ID Namespace

Artifact IDs are separate from Codex document IDs. `lore artifact show codex` and `lore codex show codex` are distinct operations on distinct namespaces. There is no cross-namespace collision detection — the same string can be a valid ID in both namespaces independently.

## Related

- Doctrine (lore codex show conceptual-entities-doctrine) — step notes in Doctrines reference artifact IDs where a template is needed
- Knight (lore codex show conceptual-entities-knight) — knights that produce template-derived documents reference artifact IDs in an `## Artifacts` section
- conceptual-workflows-lore-init (lore codex show conceptual-workflows-lore-init) — the init step that seeds `.lore/artifacts/`
- ref-lore_cli-commands (lore codex show ref-lore_cli-commands) — `lore artifact` command reference
