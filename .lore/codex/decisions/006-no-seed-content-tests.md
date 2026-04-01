---
id: "006"
title: "Do not test seed default file content"
summary: "ADR recording the decision that tests must never assert on the specific content of seed default files (defaults/ directory). Only structure and existence are valid test targets."
related: ["technical-test-guidelines", "001"]
stability: stable
---

# ADR 006 — Do Not Test Seed Default File Content

## Context

Lore ships a set of seed default files (watchers, doctrines, knights) under `src/lore/defaults/`. These files are copied into a project's `.lore/` directory on `lore init`. They are living templates — their content evolves as the project matures, with titles, action values, and comments updated as features are refined.

Early E2E tests in `tests/e2e/test_lore_init.py` asserted specific field values from these seed files (e.g., `title == "Update Changelog"`, `action == "update-changelog"`, presence of a specific inline comment). Every time a seed file was updated, one or more tests broke — not because behaviour was wrong, but because hardcoded expected values no longer matched.

## Decision

Tests must never assert on the specific content of seed default files. The following are **valid** test targets for seeded defaults:

- The file **exists** at the expected path after `lore init`.
- The file is **valid YAML** (can be parsed without error).
- Required structural fields are **present** (e.g., `id` key exists).
- The file is **overwritten** by re-init (i.e., a modified value no longer appears after re-init — without pinning the expected replacement value).

The following are **forbidden** test targets for seeded defaults:

- Asserting a specific value for any field (e.g., `data.get("title") == "Some Title"`).
- Asserting the presence of any specific inline comment or prose string.
- Asserting a specific value for `action`, `interval`, `summary`, or any other content field.

## Rationale

Seed default files are design artifacts, not stable contracts. Their content is part of the user experience and will change as the project evolves. Pinning test assertions to specific content values creates a false sense of regression coverage while generating noise on every content update. The real invariant is existence, parseability, and structural completeness — not specific values.

## Alternatives Rejected

**Snapshot testing (store expected file content and diff).** Rejected because it requires manual snapshot updates on every content change and provides no meaningful coverage of behaviour. It would create the same maintenance burden as hardcoded assertions.

**Parametrize tests against seed files at runtime.** Rejected because it would couple the test to the implementation of the seed file discovery mechanism, not to the CLI behaviour being tested.

**Keep content tests but update them on every seed change.** Rejected because this is exactly the pattern that produced the failures. Content tests for seed defaults are structurally incorrect — they test the wrong layer.
