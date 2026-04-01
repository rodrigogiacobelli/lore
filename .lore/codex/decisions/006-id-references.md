---
id: decisions-006-id-references
title: Agents reference entities by ID, never by file path
summary: >
  ADR recording the decision that agents must use Lore CLI commands to access
  artifacts, doctrines, and knights by ID rather than reading file paths
  directly. This enforces the CLI as the only stable interface and prevents
  agents from bypassing the abstraction layer.
related: ["tech-cli-commands"]
stability: stable
---

# ADR-006: Agents reference entities by ID, never by file path

**Status:** ACCEPTED

## Context

Lore manages several categories of reusable entity: Doctrines (YAML workflow
templates), Knights (agent persona files), Codex documents (project
documentation), and Artifacts (reusable content templates). All of these live
on disk as files in predictable directory trees inside `.lore/`.

An agent that knows the file system layout can bypass the CLI entirely and
read any of these files directly — e.g. `Read .lore/artifacts/transient/business-spec.md`
or `cat .lore/knights/developer.md`. This works today. The question is whether
it should be the intended usage.

## Decision

Agents must access Lore-managed entities by ID through the CLI, not by
constructing and reading file paths directly.

- **Artifacts:** `lore artifact show <id>` — never read `.lore/artifacts/…` directly
- **Codex documents:** `lore codex show <id>` — never read `.lore/codex/…` directly
- **Knights:** `lore knight show <name>` — never read `.lore/knights/…` directly
- **Doctrines:** `lore doctrine show <name>` — never read `.lore/doctrines/…` directly

The same principle applies to default entities shipped inside the package
(`src/lore/defaults/`): agents should never construct paths into the package
source tree.

Doctrine step notes and Knight instructions must reference other entities by
their Lore ID, not by path. For example: "retrieve artifact
`transient-business-spec` with `lore artifact show transient-business-spec`"
— not "open `.lore/artifacts/transient/business-spec.md`".

## Rationale

**The CLI is the stable interface; file paths are an implementation detail.**
The directory layout of `.lore/` can change across Lore versions without a
breaking change if the CLI surface stays stable. Agents that hardcode paths
will break silently when the layout changes. Agents that use CLI commands
won't notice.

**Tool call cost matters.** An agent that reads a file at a known path is
using a general-purpose tool call (Read, Bash). An agent that calls
`lore artifact show` is using one targeted CLI call. The CLI result is
already filtered, formatted, and ID-validated. There is no second trip to
discover the path.

**Enforcing tool use keeps orientation predictable.** If agents use the CLI,
the only way to retrieve an artifact is to know its ID. That means every
Doctrine and Knight instruction that references an artifact must state the ID
explicitly. This is self-documenting: an agent reading a Doctrine step can
immediately execute `lore artifact show <id>` without any prior knowledge of
directory structure.

**Parallel to ADR-004 (mission_type).** ADR-004 established that Lore stores
and exposes data but does not interpret it — interpretation belongs to the
consumer. This ADR applies the same boundary in the opposite direction: the
CLI exposes entities by ID; file-path knowledge belongs to the implementation,
not to consumers (agents).

## Consequences

- All Doctrine `notes:` fields that reference entities must use IDs with the
  relevant `lore` command, not file paths.
- All Knight instruction files that direct agents to use templates or other
  entitys must name the entity ID and the retrieval command.
- `AGENTS.md` (default and project-level) must instruct agents to use CLI
  commands for entity access.
- Writers of new Doctrines and Knights must follow this convention or their
  work is non-conforming.
- The `lore artifact list` command becomes critical for discovery: agents
  that don't know an ID upfront must list first, then show.

## Alternatives considered

**Allow both file paths and CLI commands.** Rejected. Dual pathways create
inconsistency and erode the abstraction. Once agents know they can read files
directly, they will do so opportunistically, and the CLI layer becomes
vestigial.

**Store IDs in a registry separate from files.** Rejected. The existing
frontmatter pattern (each file declares its own `id`) is already the
registry. The CLI reads frontmatter at access time; no separate index is
needed.
