---
id: tech-arch-install-manifest
title: Install Manifest
summary: The format of `.lore/.install-manifest.json` — its top-level fields, the per-file
  entries with their `kind` and `source`, and the hashing rule (raw bytes, rendered
  content, marker-block text only for a section). Also covers the packaged legacy-hash
  file that reconciles a project predating the manifest, and how an unrecognised
  manifest version is handled.
binds:
- src/lore/manifest.py
- src/lore/reconcile.py
- src/lore/defaults/legacy-hashes.json
- scripts/update_legacy_hashes.py
- tests/unit/test_manifest.py
related:
- conceptual-workflows-init-reconcile
- conceptual-workflows-lore-init
- conceptual-entities-skill
- tech-arch-initialized-project-structure
- tech-arch-agents-md
- tech-arch-skill-catalogue
- ops-publish-pypi
- decisions-006-no-seed-content-tests
---

# Install Manifest

`.lore/.install-manifest.json` is the record of what `lore init` wrote. It is generated, never edited by hand, and it is the only thing that distinguishes a file Lore installed from a file the project authored. `conceptual-workflows-init-reconcile` holds the rules it feeds; this document holds its shape.

The file needs no gitignore entry. `.lore/.gitignore` opens with `*` and un-ignores a fixed list of trees, so a dot-file at the `.lore/` root is already ignored.

Its entries name paths **outside** `.lore/` — `.claude/skills/…`, `CLAUDE.md`, `.gitignore` — so every path is stored repo-root-relative in POSIX form regardless of platform, and resolved against the project root when read.

## Format

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
      "path": ".claude/skills/store-memory/SKILL.md",
      "kind": "owned",
      "source": "skill:store-memory",
      "hash": "sha256:1f3a5b7c9d0e2f4a6b8c1d3e5f7092a4b6c8d0e2f4a6b8c1d3e5f7092a4b6c8d"
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

`files` is a list of objects sorted by `path`, not a path-keyed map: each entry carries `kind` and `source`, so a map would nest an object under every key anyway. Sorting makes successive manifests diffable.

`answers` and `targets` are informational. They let the report say that the access mode moved from `native` to `cli`, and they let a deselected agent with an empty skill set still be detected. The reconciliation algorithm reads `files` and nothing else — one source of truth for the decision.

## `kind`

Two values, and the distinction is the safety property.

**`owned`** — Lore wrote the whole file. `hash` covers the whole file. Eligible for removal.

**`section`** — Lore wrote a marked block inside a file the project owns. `hash` covers **only the rendered text between the markers**, markers excluded. Never removable: when its source is retired the block is deleted and the file is left otherwise byte-identical.

Without that split, deselecting an agent would delete a project's `CLAUDE.md`.

## `source`

A stable token naming what produced the entry, used to group the plan and to explain a removal:

| Token | Produced by |
|---|---|
| `skill:<id>` | A rendered skill file, including its `references/` files |
| `agent-instructions:<agent-id>` | A marked block in that agent's instruction file |
| `lore-agent` | `.lore/LORE-AGENT.md` |
| `skills-gitignore:<agent-id>` | The generated `.gitignore` in that agent's skills directory |
| `root-gitignore` | Retired. The marked block an older release wrote into the project's root `.gitignore`. No release produces it; a manifest carrying the row is still read, and the row is what tells the next run to delete the block. |

## Hashing

One hash function, one place: `manifest.file_digest(path)` and `manifest.bytes_digest(data)`, both returning `"sha256:" + hexdigest`.

Content is hashed as **raw bytes**, with no newline normalisation. A CRLF checkout therefore registers as an edit, which is the honest answer — Lore wrote LF.

The hash covers the **rendered** content, after access-mode selection. Flipping the access mode changes every affected hash, so those files classify as clean overwrites of unmodified files rather than as phantom user edits. This is what makes changing the access mode a supported operation rather than a wall of conflicts.

For a `section` entry the digest covers the marker-block text alone, so editing prose elsewhere in the same file never registers as a conflict.

## Legacy Hashes

`src/lore/defaults/legacy-hashes.json` is packaged and read-only. It maps a repo-relative path to every hash Lore has ever shipped for it:

```json
{
  "legacy_hashes_version": 1,
  "files": {
    ".lore/skills/new-doctrine/SKILL.md": [
      "sha256:aa1b…",
      "sha256:bb2c…"
    ]
  }
}
```

**Scope: `.lore/skills/**` only.** That was the only place Lore ever installed a skill before the manifest existed, so it is the only tree the catalogue consolidation can orphan. Everything else Lore seeds lives under a `default/` subtree that re-init overwrites in place.

`.lore/skills/.gitignore` is deliberately absent from the file. It is generated per release, so its historical hashes vary with the shipped skill list; an unmatched file is kept, and a stale gitignore listing retired directories inside a tree `.lore/.gitignore` already ignores wholesale is harmless.

**Generation.** `scripts/update_legacy_hashes.py` runs as a release pre-flight step (`ops-publish-pypi`). It hashes every file under `src/lore/defaults/skills/`, prefixes each relative path with `.lore/skills/`, and unions the result into the existing file. Rows are never removed: a project may hop from 0.8 to 0.14 and needs every intermediate hash. The script is idempotent — running it twice on an unchanged tree produces a byte-identical file.

Because the file sits under `src/lore/defaults/`, `decisions-006-no-seed-content-tests` applies: tests assert that it exists, parses, and carries the required top-level shape, never that a particular hash is present.

## Version Handling

`manifest_version` is `1`. `manifest.load` treats an unrecognised value exactly as it treats an unparseable file: one warning on stderr, then the legacy-hash fallback, then a fresh manifest written at the end of the run. Every unmatched file is kept. That keeps a downgrade safe — an older Lore reading a newer manifest degrades to caution rather than to a wrong decision.

`lore_version` and `catalogue_version` are informational, recording which release and which catalogue produced the entries.
