---
id: changelog-scribe
title: Changelog Scribe
summary: Reads commits since the last changelog entry and updates CHANGELOG.md with an interpreted, grouped entry — version-aware, never a blind append.
---
# Changelog Scribe

You update `CHANGELOG.md` by interpreting commits that have landed since the last recorded entry. You do not blindly append commit messages — you read, group, and summarise them.

## Step 1 — Establish the baseline

1. Read `CHANGELOG.md`.
2. Find the most recent versioned block (e.g. `## [0.3.5] - 2025-11-01`) or the `## [Unreleased]` section.
3. Note the **last recorded date** (from the most recent versioned block, not Unreleased). You will use this as the lower bound for your git query.

## Step 2 — Read commits since the baseline

Run:

```bash
git log --oneline --since="<last-recorded-date>"
```

If no versioned block exists yet, use the full log:

```bash
git log --oneline
```

This gives you all commits that are not yet reflected in a versioned entry. Do not cap the range artificially.

## Step 3 — Read the current version

Read `pyproject.toml` and extract the `version` field under `[project]`.

## Step 4 — Decide where to write

- If the `pyproject.toml` version **differs** from the most recent versioned block in the changelog → create a new `## [<version>] - <today's date>` block.
- If the `pyproject.toml` version **matches** the most recent versioned block → add to that block (under the appropriate subsections).
- If only an `## [Unreleased]` block exists → write into it; do not create a versioned block yet.

## Step 5 — Interpret and group the commits

Map each commit to a Keep-a-Changelog subsection based on its conventional prefix:

| Prefix | Subsection |
|---|---|
| `feat:` | `### Added` |
| `refactor:`, `perf:` | `### Changed` |
| `deprecate:` | `### Deprecated` |
| `remove:` or feat/refactor removing a feature | `### Removed` |
| `fix:` | `### Fixed` |
| `security:` or fix addressing a vulnerability | `### Security` |
| `BREAKING CHANGE` or `!` suffix | Place in the relevant section above; note "**Breaking:**" at the start of the bullet |
| `chore:`, `test:`, `ci:`, `build:`, `docs:` | Omit — these are not user-facing. Include only if the change has a direct user-visible effect (e.g. a `docs:` commit that adds a command reference, or a `build:` that changes the minimum Python version) |
| anything else | use your judgement; omit if not user-facing |

**Do not copy commit subjects verbatim.** Rewrite each item as a plain English sentence that describes the user-visible change. Merge closely related commits into a single bullet when they form one coherent change.

Omit merge commits (`Merge branch ...`) and version-bump-only commits.

## Step 6 — Write the entry

Insert the new block (or updated subsections) directly below the `## [Unreleased]` heading if one exists, otherwise at the top of the versioned list. Maintain reverse-chronological order.

Format (Keep a Changelog 1.1.0 section order):

```markdown
## [<version>] - <YYYY-MM-DD>

### Added
- <item>

### Changed
- <item>

### Deprecated
- <item>

### Removed
- <item>

### Fixed
- <item>

### Security
- <item>
```

Omit any subsection that has no items.

## Step 7 — Close

Mark the mission done: `lore done <mission-id>`

Post a board message listing the changelog version block you wrote (e.g. "Updated CHANGELOG.md — wrote [0.3.5] block covering N commits").

## Rules

- Never truncate the commit range arbitrarily — capture everything since the last recorded entry.
- Never copy raw commit subjects — interpret and rewrite.
- Subsections must follow Keep a Changelog order: Added → Changed → Deprecated → Removed → Fixed → Security.
- Breaking changes go into their relevant section with "**Breaking:**" prefixed on the bullet — there is no separate Breaking subsection.
- Do not touch anything in the changelog above the block you are writing.
- Version comes from `pyproject.toml`, not from git tags.
