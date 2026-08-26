---
name: update-doctrine
description: Create or edit a doctrine, along with the knights and artifacts it needs
---

# Update Doctrine

Author a Lore doctrine. This skill **creates a doctrine or edits an existing one**, whichever the request calls for — "add a review step to `tdd-implementation`" and "build me a hotfix workflow" both land here.

Doctrines are YAML workflow templates that describe a sequence of steps for a standard body of work. An orchestrator reads them and translates them into quests and missions. The mission notes are the full execution spec — a worker agent receives only the mission output and must be able to complete the task from that alone.

## Creating or editing

Decide which you are doing before you draft:

- **Editing** — the doctrine exists. Read it in full first (`lore doctrine show <id>`), change only the steps the request names, and keep every other step byte-identical. Adding a step usually means fixing the `needs` edges around it and the `priority` of everything downstream.
- **Creating** — no doctrine covers this shape of work. Run the whole flow below.

Either way, `lore doctrine show` runs normalisation, step validation and cycle detection, and the doctrine tree hides a `default/` versus flat split and slash-derived groups. Doctrines are reached through the Lore CLI in every access mode, never by reading the YAML off disk.

## Input: Design Doc (preferred)

The user may provide a design doc. If they are unsure of the format, show them the template:

```
lore artifact show doctrine-design
```

When a design doc is provided, use it as the authoritative spec. The table maps directly to doctrine steps — Input becomes what the mission notes tell the agent to read, Output becomes what it must produce.

If no design doc is provided, ask the user for the workflow description before proceeding.

## Steps

### 1. Understand the full scope

From the design doc or the user's description, identify:
- All steps and their order/dependencies
- Which knights are needed (existing or new)
- Which artifacts are needed (existing or new)
- Any human gates, constable steps, or parallel tracks

```
lore doctrine list
lore doctrine show <existing-id>
lore knight list
lore artifact list
```

Align on the project's vocabulary before you name steps and write notes — a doctrine that invents a synonym for a term the project already has costs every downstream agent a translation.

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

For each new artifact in the design doc, create it before writing the doctrine (the doctrine's mission notes will reference them).

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

### 3. Create knights

For each new knight in the design doc, create it before writing the doctrine.

A knight is a markdown file that encodes **who the agent is and how it works** — not what to do on a specific mission. Mission notes handle the what; the knight handles the behavioral DNA.

Structure:
```markdown
---
id: <slug>
title: <Title>
summary: <One sentence: role and primary contribution.>
---
# <Title>

<One paragraph: who you are and your primary goal.>

## How You Work

<Behavioral approach — how this knight thinks, what they prioritize, tools they use,
how they make decisions. Include domain expertise and methodology. This should be
generic enough to apply to any mission this knight is assigned to.>

## Rules

- <Hard constraints that are always true for this role — never task-specific>
- <What they must never do>
- <Quality bars they always maintain>
```

Write to a temp file, then:
```
lore knight new <name> -f <temp-file>
```

Verify: `lore knight show <name>`

### 4. Draft the doctrine YAML

The YAML contains only `id` and `steps` — no title, summary, or description. All metadata lives in the design doc.

```yaml
id: <slug>
steps:
  - id: <step-slug>
    title: <Step Title>
    type: knight        # knight | constable | human
    priority: 0         # phase number — same priority = can run in parallel
    knight: <knight-file.md>   # omit if constable or human
    needs:              # omit if no dependencies
      - <other-step-id>
    notes: |
      <Full execution spec. The agent receives only this — it must be enough.>
      <Inputs: what to read and where to find the IDs (board messages or mission description).>
      <Outputs: exact file paths, frontmatter requirements, what to post to which boards.>
      <Quality requirements: what "done" means for this specific step.>
      Mark done: `lore done <mission-id>`
```

Rules:
- `priority` maps to phase — same priority = parallel-eligible
- `needs` creates a dependency
- `constable` steps are orchestrator chores — no knight needed
- `human` steps require user action — orchestrator does not claim them
- Mission notes must be self-contained — the agent has no other context beyond board messages and the knight prompt
- IDs passed via board messages: "your board messages contain the X ID"
- IDs in the mission description: "your mission description contains the X ID"
- Never tell the agent to run `lore show <mission-id>` — it already received that output. This applies to all step types including human steps.
- When specifying frontmatter for output documents in mission notes, require only `id`, `title`, `summary`

### 5. Write the doctrine

Write the YAML to a temp file, then create or replace it:

```
lore doctrine new <name> -f <temp-file>     # new doctrine
lore doctrine edit <name> -f <temp-file>    # replace an existing one
```

To nest under a subdirectory, pass `--group <subdir>` on `new`. To retire a doctrine, `lore doctrine delete <name>` — a soft delete, so the file is renamed rather than destroyed.

Verify: `lore doctrine show <name>`

### 6. Save the design doc alongside the doctrine

If a design doc was provided, save it as `<doctrine-name>.design.md` in the same directory as the doctrine YAML:

```
.lore/doctrines/<doctrine-name>.design.md
```

Frontmatter requires only `id` (use `<doctrine-name>-design`), `title`, and `summary`. The design doc is the permanent human-readable explanation of the doctrine — the YAML is the machine-readable version. The CLI pairs them by filename prefix.
