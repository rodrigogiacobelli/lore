---
id: example-relationship-{entity-a}--{entity-b}
title: "{Entity A} to {Entity B}"
related: []
stability: stable
summary: >
  _One to three sentences. What are the two named roles in this relationship?
  What is the cardinality? What is mutable vs immutable?_
---

# {Entity A} to {Entity B}

_One paragraph. Describe the nature of the connection. How many roles exist between these two entities? What is the cardinality (one-to-many, many-to-many)?_

## Named Roles

### {Role 1} (immutable)

_Describe this role. How is it set? Can it be changed? What happens to it if the related entity is deleted?_

> Example: Creator — set at record creation from context; immutable; retained as a tombstone reference if the entity is later deleted.

### {Role 2} (mutable)

_Describe this role. Is it optional? Can it be changed? What command or operation changes it?_

> Example: Assignee — optional; changed with an edit command; at most one at a time; removal sets the field to null.

## Data on the Connection

_How is this relationship stored? Join table or columns on an entity? Which columns?_

| Column | Role | Mutable |
|--------|------|---------|
| `{column_1}` | {Role 1} | No |
| `{column_2}` | {Role 2} | Yes |

> Note: Replace with a join table description if the relationship uses a separate table.

## Business Rules

- **{Rule 1}:** _Description_
- **{Rule 2}:** _Description_
- **{Guard rule}:** _When is this relationship blocked (e.g. deletion guard)?_

## Concrete Examples

### {Scenario Name}

_Describe a typical scenario with command examples and resulting state._

```
$ {command}
{output}
```

→ `{field_1}` = {value}
→ `{field_2}` = {value}
