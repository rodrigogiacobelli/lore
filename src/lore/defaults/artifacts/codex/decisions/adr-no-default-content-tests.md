---
id: adr-no-default-content-tests
title: No Content Tests for Default Templates
summary: Policy decision not to write tests that assert content of default templates,
  since defaults evolve continuously and content tests create maintenance friction
  without adding safety value.
---

# ADR: No Content Tests for Default Templates

## Status
Accepted

## Context
Lore ships default artifacts, knights, and doctrines as seed templates. These templates
evolve continuously as the project matures — sections are renamed, restructured, and
refined over time. Writing tests that assert specific content (section names, line counts,
exact wording, knight assignments) creates maintenance friction without adding safety value.

The content is exercised through actual usage by agents and through doctrine-driven
workflows, not through assertions in test suites.

## Decision
Do not write tests that validate the *content* of default templates (artifacts, knights,
doctrines). Tests may assert structural/behavioral properties:
- The init command seeds the expected directories and files (file existence)
- AGENTS.md is created with the required lore markers
- Schema migrations run cleanly
- CLI commands accept valid input and return the correct shape

## Consequences
- Content changes to defaults do not require test updates
- Broken defaults surface through usage rather than CI
- CI stays green across refactors of default terminology and structure
