---
id: example-tech-schema-{entity-name-2}
title: Schema — {entity name 2}
summary: Database schema for the {entity-2} table. Natural key, optional display field,
  soft-delete pattern.
---

# Schema — {Entity Name 2}

```sql
CREATE TABLE IF NOT EXISTS {table_name_2} (
    {natural_key}   TEXT    PRIMARY KEY,
    {display_field} TEXT    NOT NULL DEFAULT '',
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    deleted_at      TEXT    NULL
);
```

> Use this template when the entity is identified by a natural key (e.g. email, slug) rather than a generated ID.

## Column Notes

| Column | Notes |
|--------|-------|
| `{natural_key}` | _Natural identifier. Immutable after creation. Used as FK target in other tables. Case-insensitive (stored normalised)._ |
| `{display_field}` | _Optional. Display-only. Can be updated freely. Shown as `(unnamed)` or equivalent if empty._ |
| `created_at` | _Set once at creation. Immutable._ |
| `deleted_at` | _NULL = active. Soft-delete permanent — no undelete._ |

## Indexes

| Index | Columns | Purpose |
|-------|---------|---------|
| PRIMARY | `{natural_key}` | _Lookup and FK target_ |
| `idx_{table}_deleted_at` | `deleted_at` | _Active-record filter_ |
