---
id: conceptual-workflows-doctrine-show
title: lore doctrine show Behaviour
summary: What the system does internally when `lore doctrine show <name>` runs — recursive search for a matched design file and YAML pair, verbatim rendering of both files with a separator (text mode), or structured JSON output (JSON mode). Raises an error if either file is missing.
related: ["conceptual-entities-doctrine", "conceptual-workflows-doctrine-list", "tech-cli-commands", "tech-doctrine-internals"]
---

# `lore doctrine show` Behaviour

`lore doctrine show <name>` displays the full content of a doctrine — both the `.design.md` documentation and the `.yaml` steps file. The command searches recursively across the full `.lore/doctrines/` tree by doctrine ID. If either file is missing, the command exits with an error; there is no fallback to displaying only one file.

## Preconditions

- The Lore project has been initialised (`.lore/` directory exists).
- A doctrine with the given ID exists as a complete pair (`<name>.design.md` and `<name>.yaml` both present under `.lore/doctrines/`).

## Steps

### 1. Locate both files

`show_doctrine(name, doctrines_dir)` searches recursively under `.lore/doctrines/` for:
- `<name>.design.md`
- `<name>.yaml`

Both searches are independent. The function detects which combination of files is present before raising any error.

### 2. Handle missing files

If either file is absent, a `DoctrineError` is raised and the CLI prints to stderr and exits with code 1.

| Situation | Error message | Exit code |
|---|---|---|
| Design file missing | `Doctrine '<name>' not found: design file missing` | 1 |
| YAML file missing | `Doctrine '<name>' not found: YAML file missing` | 1 |
| Both files missing | `Doctrine '<name>' not found` | 1 |

### 3. Read and validate both files

- The design file is read verbatim (raw string, including frontmatter block).
- The YAML file is parsed and validated against the doctrine schema (`_validate_yaml_schema`).
- If the YAML is invalid (parse error, missing fields, rejected fields), a `DoctrineError` is raised and the CLI exits with code 1.
- The `steps` list is normalised via `_normalize()` — defaults are applied for any missing optional fields.
- `id`, `title`, and `summary` are extracted from the design file frontmatter (`title` falls back to `id`; `summary` falls back to `""`).

### 4. Render output

**Text mode (default):**

The full raw content of the `.design.md` file is printed verbatim (including the frontmatter block), followed by a separator line (`---`), followed by the full raw content of the `.yaml` file verbatim. No transformation of either file.

Example:
```
---
id: feature-implementation
title: Feature Implementation
summary: E2E spec-driven pipeline...
---

# Feature Implementation

## Doctrine
...
<full body of feature-implementation.design.md>

---

id: feature-implementation
steps:
  - id: business-scout
    ...
<full content of feature-implementation.yaml>
```

**JSON mode (`--json`):**

Returns a structured object. The `design` field contains the full raw string content of the `.design.md` file (including the frontmatter block). The `steps` field contains the normalized step list. The `raw_yaml` field (present in the Python return value) is excluded from JSON output.

```json
{
  "id": "feature-implementation",
  "title": "Feature Implementation",
  "summary": "E2E spec-driven pipeline...",
  "design": "---\nid: feature-implementation\ntitle: Feature Implementation\n...\n",
  "steps": [
    {
      "id": "business-scout",
      "title": "Map codex from the business perspective",
      "priority": 2,
      "type": "knight",
      "knight": "scout",
      "notes": null,
      "needs": []
    }
  ]
}
```

Exit code 0 on success. Exit code 1 with `{"error": "<message>"}` on failure.

## Python API

The `show_doctrine(doctrine_id, doctrines_dir)` function can be called directly from Python:

```python
from pathlib import Path
from lore.doctrine import show_doctrine, DoctrineError

doctrines_dir = Path(".lore/doctrines")
try:
    result = show_doctrine("feature-implementation", doctrines_dir)
except DoctrineError as e:
    print(f"Error: {e}")
```

Return shape:
```python
{
    "id": str,
    "title": str,
    "summary": str,
    "design": str,      # raw .design.md content (including frontmatter)
    "raw_yaml": str,    # raw .yaml content (for CLI verbatim dump; excluded from --json output)
    "steps": list[dict] # normalized step dicts with defaults applied
}
```

To construct a typed `Doctrine` model from this result:

```python
from lore.models import Doctrine

doctrine_obj = Doctrine.from_dict(result)
```

## Failure Modes

| Failure point | Message (stderr) | Exit code |
|---|---|---|
| Design file not found | `Doctrine '<name>' not found: design file missing` | 1 |
| YAML file not found | `Doctrine '<name>' not found: YAML file missing` | 1 |
| Both files missing | `Doctrine '<name>' not found` | 1 |
| YAML parse error | `YAML parsing error: <details>` | 1 |
| YAML schema error | Specific validation error | 1 |

## Out of Scope

- Displaying only the design file if the YAML is missing — both files are required.
- Editing doctrine content — use `lore doctrine edit`.
- Listing all doctrines — use `lore doctrine list`.

## Related

- conceptual-workflows-doctrine-list (lore codex show conceptual-workflows-doctrine-list) — how doctrine listing works
- conceptual-workflows-doctrine-new (lore codex show conceptual-workflows-doctrine-new) — how doctrine creation works
- tech-doctrine-internals (lore codex show tech-doctrine-internals) — module-level implementation details
- tech-cli-commands (lore codex show tech-cli-commands) — full CLI reference
