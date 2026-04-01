---
id: conceptual-workflows-mission-type
title: Mission Type Field
summary: >
  What the system does when a mission type is set, displayed, and updated — free-form string schema, null display guards across all four output sites, CLI acceptance, and oracle rendering.
related: ["conceptual-entities-mission", "decisions-004"]
stability: stable
---

# Mission Type Field

The `mission_type` field is a free-form string on the `missions` table. Lore does not interpret, validate, or constrain its value. It is an opaque label that orchestrators and agents can use to signal the kind of work a mission requires.

## Schema

`mission_type` is stored as `TEXT NULL` in the `missions` table. NULL means "no type set". There is no enumeration and no length limit enforced by the DB layer.

## Setting on Create

`lore new mission -T <type>` or `lore new mission --type <type>` sets `mission_type` at creation time. Omitting the flag leaves the field NULL.

## Setting on Edit

`lore edit <mission-id> -T <type>` or `--type <type>` updates the `mission_type` of an existing mission. There is no dedicated "clear type" flag — setting `mission_type = NULL` requires direct DB manipulation.

## Display Sites

`mission_type` appears in four places in the CLI. All four guard against NULL to avoid printing `[None]` or empty brackets.

### 1. `lore missions` listing

```
  q-xxxx/m-yyyy  P2  [open]  [coding]  My Task  [knight.md]
```

`[<mission_type>]` is rendered between the status bracket and the title. When `mission_type` is NULL the bracket is omitted entirely.

### 2. `lore ready` output

Same line format as `lore missions`.

### 3. `lore show <mission-id>` (text mode)

A `Type: <value>` line is printed after `Priority:` only when `mission_type` is non-null:

```
Mission: q-xxxx/m-yyyy
Title: My Task
Status: open
Priority: 2
Type: coding
```

### 4. `lore show <quest-id>` (inline mission list)

```
○ m-yyyy  My Task [coding]
```

The `[<mission_type>]` bracket is appended to the title when non-null.

## JSON Representation

In all JSON output sites, `mission_type` is always present as a key. Its value is either the string value or `null`:

```json
{"id": "q-xxxx/m-yyyy", "mission_type": "coding", ...}
{"id": "q-xxxx/m-zzzz", "mission_type": null, ...}
```

## Oracle Reports

When `lore oracle` generates a mission file, `mission_type` is included as a metadata field if non-null. The oracle does not group, filter, or sort by mission type.

## Failure Modes

| Failure point | Behaviour | Exit code |
|---|---|---|
| No validation on value | Any non-empty string is accepted | — |
| NULL display guard missing (regression) | Would produce `[None]` in output — covered by tests | — |

## Out of Scope

- Enumerated types — `mission_type` is intentionally free-form.
- Filtering `lore missions` or `lore ready` by type.
- Clearing `mission_type` back to NULL via the CLI.
