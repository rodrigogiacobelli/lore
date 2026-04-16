---
id: example-tech-api-{domain}
title: API — {Domain} Commands
summary: CLI command reference (or HTTP endpoint reference) for the {domain} domain.
  Covers all sub-commands, options, output shapes, and error codes.
---

# API — {Domain} Commands

_All commands in the `{domain}` domain. For HTTP APIs, replace "command" with "endpoint" and adjust the table format._

## Commands

### `{domain} list`

_Description. What does it return? What filters are available?_

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--{filter}` | `{type}` | _none_ | _Filter description_ |
| `--json` | flag | off | _Output as JSON array_ |

**Output (table):**
```
{column-a}   {column-b}   {column-c}
{example-1}  {val}        {val}
```

**Output (JSON):**
```json
[{"id": "{id}", "{field}": "{value}"}]
```

---

### `{domain} show <id>`

_Description. What is returned for a single record?_

**Exit codes:** `0` success, `1` not found.

---

### `{domain} new <required-arg>`

_Description. What is created? What is required vs optional?_

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--{option}` | `{type}` | _default_ | _Description_ |

**Output:** `Created {domain} {id}`

**Exit codes:** `0` success, `1` validation failure, `2` conflict.

---

### `{domain} edit <id>`

_Description. What can be changed? What cannot?_

**Options:**

| Flag | Type | Description |
|------|------|-------------|
| `--{field}` | `{type}` | _Description_ |

---

### `{domain} delete <id>`

_Soft-delete. The record is excluded from listings but retained in the database._

**Exit codes:** `0` success, `1` not found or blocked by constraint.
