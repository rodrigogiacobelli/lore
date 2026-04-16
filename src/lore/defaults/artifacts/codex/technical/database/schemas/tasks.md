---
id: example-tech-schema-{entity-name}
title: Schema — {entity name}
summary: Database schema for the {entity} table. Columns, constraints, indexes, and
  notes on nullable fields and soft-delete pattern.
---

# Schema — {Entity Name}

```sql
CREATE TABLE IF NOT EXISTS {table_name} (
    id              TEXT        PRIMARY KEY,
    {field_1}       TEXT        NOT NULL,
    {field_2}       TEXT        NOT NULL DEFAULT '{default_value}'
                                CHECK ({field_2} IN ('{val_a}', '{val_b}')),
    {optional_field} TEXT       NULL,
    created_at      TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    deleted_at      TEXT        NULL
);
```

> Replace fields to match the actual schema. Remove `deleted_at` if hard-delete is used.

## Column Notes

| Column | Notes |
|--------|-------|
| `id` | _ID format (e.g. ULID with prefix `x-`). Generated in application code._ |
| `{field_1}` | _Constraints and validation rules (e.g. empty string rejected at CLI layer)._ |
| `{field_2}` | _Allowed values, default, transition rules if it's a status field._ |
| `updated_at` | _Must be explicitly set on UPDATE. No ON UPDATE trigger in this database._ |
| `deleted_at` | _NULL = active. Set on soft-delete. No hard delete._ |

## Indexes

| Index | Columns | Purpose |
|-------|---------|---------|
| PRIMARY | `id` | _Lookup by ID_ |
| `idx_{table}_{field}` | `{field}` | _Description_ |

## Foreign Keys

| Column | References | On delete |
|--------|-----------|-----------|
| `{fk_column}` | `{other_table}(id)` | _Soft-delete tombstone; no CASCADE_ |
