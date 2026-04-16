---
id: example-tech-database
title: Database
summary: Database technology, connection setup, migration pattern, and shared access
  conventions. Read before writing any query or migration.
---

# Database

_One paragraph. What database technology? Where is the database file or server? What library is used to talk to it?_

## Connection

_How is a connection opened? Is there a shared factory function? What configuration is applied at connection time (modes, timeouts, pragmas)?_

> Always open connections through `{module}.connect()` — never call the database driver directly. This ensures all required configuration is applied consistently.

## Migration Pattern

_How are schema migrations managed? What tracks the current version? What is the naming convention for migration files? Can migrations be rolled back?_

> Migration files live in `{migrations-dir}/`. Never modify an existing migration file — always add a new one.

## Shared Access Patterns

_Rules that apply to every query in the codebase. These must be followed without exception._

- **{Soft-delete filter}:** _All read queries must filter `WHERE {deleted_at} IS NULL`._
- **{Transaction type}:** _All write transactions must use `{BEGIN IMMEDIATE}` or equivalent._
- **{Timeout}:** _All connections must set a busy/lock timeout._
- **{No cached counts}:** _Counts are always derived from queries, never stored as columns._

> Replace or remove items that don't apply to your database setup.

## Schema Overview

_List the main tables or collections and their one-line purpose._

| Table / Collection | Purpose |
|-------------------|---------|
| `{table_a}` | _Description_ |
| `{table_b}` | _Description_ |
