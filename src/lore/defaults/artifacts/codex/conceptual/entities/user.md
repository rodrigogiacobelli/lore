---
id: example-entity-{entity-name-2}
title: "{Entity Name 2}"
related: []
stability: stable
summary: >
  _One to three sentences. What this entity is and what it does in the system.
  Mention its unique identifier, key attributes, and any deletion semantics._
---

# {Entity Name 2}

_One paragraph. Define what this entity is. What uniquely identifies it? What does it represent in the domain?_

## Core Concepts

| Term | Definition |
|------|------------|
| **{Identifier field}** | _The natural key. Note case sensitivity and immutability._ |
| **{Display field}** | _Optional or display-only. Can it be changed?_ |
| **{Timestamp}** | _Set once at creation; immutable._ |

## How It Works

### Identity

_How is this entity uniquely identified? Can that identifier change? What happens to references if the entity is deleted?_

> Example: Email is the canonical identifier. Case-insensitive. Cannot be changed after registration — a changed identifier is a new record.

### Uniqueness

_What uniqueness constraints apply? What error does the system return on collision?_

> Example: No two records may share the same email. Attempting to create a duplicate returns exit code 2.

### Deletion Constraint

_When can this entity not be deleted? What must be resolved first? Is deletion hard or soft?_

> Example: Cannot be deleted if there are open dependent records. Soft-delete only — the row is retained as a tombstone.

## Edge Cases

- **{Optional field at creation}:** _What defaults apply when omitted._
- **{Immutable field}:** _Cannot be changed after creation and why._
- **{Tombstone behaviour}:** _What happens to references after soft-delete._
