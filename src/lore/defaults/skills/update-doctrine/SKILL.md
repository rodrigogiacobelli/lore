---
name: update-doctrine
description: Create or edit a doctrine — its design document, its mission files, and the artifacts they need
---

# Update Doctrine

Author a Lore doctrine. This skill **creates a doctrine or edits an existing one**, whichever the request calls for — "add a review mission to `tdd-implementation`" and "build me a hotfix workflow" both land here.

A doctrine is a directory of prose for a standard body of work: a design document that says how the work is done, and one mission file per reusable instruction. An orchestrator reads the design and translates it into a quest and its missions; a worker is handed one mission body. Lore parses none of it — order, type and dependencies are the orchestrator's to read out of the design prose.

A mission file is the full execution spec for its worker. The worker receives that body plus its Lore mission's own description and nothing else, so it must be able to finish the task from those two alone.

## Creating or editing

Decide which you are doing before you draft:

- **Editing** — the doctrine exists. Read it in full first (`lore doctrine show <id>`, then `lore doctrine show <id> --mission <mission-id>` for each mission the change touches), change only what the request names, and leave every other file untouched. `lore doctrine edit` replaces only the files you pass, so a mission nobody names stays byte-identical.
- **Creating** — no doctrine covers this shape of work. Run the whole flow below.

Either way, doctrines are reached through the Lore CLI in every access mode, never by reading files off disk: the doctrine tree hides a `default/` versus flat split and slash-derived groups, and `lore doctrine show` assembles the mission index across the directory.

## Input: Design Doc (preferred)

The user may provide a design doc. If they are unsure of the format, show them the template:

```
lore artifact show doctrine-design
```

When a design doc is provided, use it as the authoritative spec. The table maps directly to mission files — Input becomes what the mission file tells the worker to read, Output becomes what it must produce.

If no design doc is provided, ask the user for the workflow description before proceeding.

## Steps

### 1. Understand the full scope

From the design doc or the user's description, identify:
- All missions and their order/dependencies
- Which artifacts are needed (existing or new)
- Any human gates, constable missions, or parallel tracks

```
lore doctrine list
lore doctrine show <existing-id>
lore doctrine show <existing-id> --mission <mission-id>
lore artifact list
```

Align on the project's vocabulary before you name missions and write their bodies — a doctrine that invents a synonym for a term the project already has costs every downstream worker a translation.

<!-- lore:access cli -->
```
lore glossary list
lore codex search <workflow-keyword>
```
<!-- lore:access end -->
<!-- lore:access native -->
Read `.lore/codex/glossary.yaml` for the vocabulary and grep `.lore/codex/**/*.md` for the workflow this doctrine automates. Glossary terms are not attached to what you read, so look up an unfamiliar one yourself.
<!-- lore:access end -->

`lore codex map <id>` and `lore impacts <path-or-id>` stay on the CLI in every mode when you need to see what a workflow document connects to.

### 2. Create artifacts first

For each new artifact in the design doc, create it before writing the doctrine (the mission files will reference them by id).

Draft the artifact into a temp file:

```markdown
---
id: <slug>
title: <Human Readable Title>
summary: >
  What this artifact is and when to use it.
---

# <Title>

<Content — write for an AI agent reader. Be specific and actionable.>
```

Then create it via the CLI (validates frontmatter and lands the file under `.lore/artifacts/`):

```
lore artifact new <slug> -f <temp-file>
```

To nest under a subdirectory, pass `--group <subdir>`.

Verify: `lore artifact show <id>`

### 3. Draft the design document

The design document is the file `lore doctrine show <name>` prints. Its frontmatter carries exactly `id`, `title` and `summary`, and its `id` must equal the doctrine name.

Fill the `doctrine-design` template: the mission table (phase, mission id, type, depends-on, input, output), the Missions list with a one-line purpose each, the artifacts the doctrine uses, the escalation table, and any notes the orchestrator needs.

Type tokens are `agent`, `constable` and `human`:

- `agent` — dispatched to a worker, which reads the mission file
- `constable` — an orchestrator chore handled inline (commit, housekeeping)
- `human` — requires user action; the orchestrator does not claim it

### 4. Draft one mission file per mission

Retrieve the template before you write the first one:

```
lore artifact show mission-design
```

Every mission in the design table gets a file whose stem is the mission id. Its frontmatter carries exactly `id`, `title` and `summary`, and `id` must equal the filename stem.

The body is the worker's whole brief, in this order: the role it adopts, how it works, its hard rules, its inputs, its steps, its done criteria, and what it hands on. It merges what a persona would say about *who the worker is* with what a step spec would say about *what to do this run*.

Rules:
- Each mission file is self-contained — the worker has no other context beyond board messages and its Lore mission description
- There is no include mechanism; if two missions need the same paragraph, each carries its own copy
- IDs passed via board messages: "your board messages contain the X ID"
- IDs in the mission description: "your mission description contains the X ID"
- Never tell the worker to run `lore show <mission-id>` — it already received that output. This applies to every mission type including human ones.
- Reference artifacts and codex documents by id and the command that fetches them — `lore artifact show <id>`, `lore codex show <id>` — never by file path
- When specifying frontmatter for output documents, require only `id`, `title`, `summary`
- No order, dependency, phase or type belongs in a mission file; that lives in the design table

### 5. Write the doctrine

Pass the design document and every mission file in one call:

```
lore doctrine new <name> -d <design-file> -m <mission-1> <mission-2> <mission-3>
```

To nest under a subdirectory, pass `--group <subdir>` on `new`. The whole directory is created or nothing is.

To change an existing doctrine:

```
lore doctrine edit <name> -d <design-file>               # replace the design
lore doctrine edit <name> -m <mission-file> ...          # replace or add missions
lore doctrine edit <name> --remove-mission <id> ...      # soft-delete missions
lore doctrine edit <name> --set summary="..."            # edit one design frontmatter field
```

A doctrine always keeps at least one mission — `--remove-mission` refuses to empty it.

To retire a doctrine, `lore doctrine delete <name>` — a soft delete, so the directory is renamed rather than destroyed.

### 6. Verify

```
lore doctrine show <name>
lore doctrine show <name> --mission <mission-id>
lore health --scope doctrines schemas
```

`lore doctrine show <name>` prints the design document and a `--- Missions ---` index. Check that every mission in the design table appears in that index and that no mission appears in the index without a row in the table.
