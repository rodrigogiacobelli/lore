---
id: mission-design
title: Mission Design
summary: >
  Template for a doctrine mission file. One mission file is one worker's whole
  brief: who it is, how it works, what it may never do, what it reads, what it
  does, when it is finished, and what it hands on. Fill it in, save it as
  <mission-id>.md, and pass it to `lore doctrine new -m` or
  `lore doctrine edit -m`.
---

# Mission Design

A doctrine is a directory: `<doctrine-id>.design.md` for the orchestrator, and one `missions/<mission-id>.md` for each worker. This is the template for one of those mission files.

A mission file is the single authoritative copy of everything a worker needs that is not specific to the feature it is working on. The feature-specific part — which story, which file, which bug — arrives in the Lore mission's own description. `lore show <mission-id>` hands the worker both in one call.

## Frontmatter

Every mission file opens with exactly three keys, and no others:

```yaml
---
id: mission-id
title: What this mission does, in one line
summary: One or two sentences an orchestrator reads when picking missions.
---
```

- `id` must equal the filename stem. `missions/red.md` declares `id: red`.
- `title` is what `lore doctrine show <doctrine-id>` prints in the mission index.
- `summary` is read by an orchestrator deciding what this mission is for.

`lore health --scope schemas` validates these three against the `doctrine-mission-frontmatter` schema; `lore health --scope doctrines` checks the id against the filename.

## Body

Everything below the frontmatter is prose. Lore never parses it — it hands the body to the worker verbatim. Write it as instructions addressed to the worker, in the second person.

### Role

Open with a heading naming the role and one paragraph stating who the worker is and what their job is.

```markdown
# TDD Red — Test Writer

You are a test-first developer. Your job is to write failing tests that define
the behavior specified by acceptance criteria. You do not write production code.
```

### How You Work

The behavioral approach, methodology, and domain expertise this role brings. This is the part that holds across every run of the mission — the judgment the worker applies, not the steps it follows.

### Hard Rules

Constraints that are always true for this role, regardless of what the Lore mission asks for. Write each one as a prohibition or an obligation the worker can check itself against.

```markdown
## Hard Rules

- **No production code** — not even stubs or empty functions
- **No modifying test files** — tests are the specification
- If refactoring breaks a test, **revert the refactor** — tests are the source of truth
```

### Inputs

What the worker reads before it acts, and the exact command that fetches each one. Name artifacts by id and the command that retrieves them — `lore artifact show <artifact-id>` — never by file path. Name codex documents by id — `lore codex show <id>`. Say which inputs arrive on the board and which arrive in the mission description.

### Steps

What the worker does, in order. Show exact commands in fenced blocks. Where a step has a quality bar, state the bar in the step rather than leaving it to the worker's taste.

### Done Criteria

The checks the worker runs before marking the mission done, written so each one has a yes-or-no answer. Close with the board message it posts, if any, and:

```markdown
Mark done: `lore done <mission-id>`
```

### Hands On

One line: what this mission produces and which mission receives it. A terminal mission says so.

## Rules for the Author

- **One mission file is the only home for its instructions.** If two missions need the same paragraph, each carries its own copy — there is no include mechanism and a shared file would be a second place to update.
- **No workflow structure in a mission file.** Order, dependencies, phase and type live in the design document's table, where the orchestrator reads them. A mission file never says "this runs after X" except as the Hands On line's plain prose.
- **Address every entity by id.** `lore artifact show fi-prd`, `lore codex show <id>`, `lore doctrine show <doctrine-id> --mission <mission-id>`. A constructed path in a mission body is a defect.
- **Write for a worker with no conversation behind it.** The worker reads this file cold, alongside one Lore mission description. A sentence that resolves against anything else fails that reader.
- **The mission id is stable.** Lore missions store the reference `<doctrine-id>/<mission-id>` verbatim; renaming a mission file breaks every mission pointing at it, and `lore health --scope doctrines` reports each one as an error.

## Checklist

Before handing the file to `lore doctrine new` or `lore doctrine edit`:

- [ ] Frontmatter carries exactly `id`, `title`, `summary`, and `id` equals the filename stem
- [ ] The role paragraph says who the worker is in the second person
- [ ] Hard Rules are checkable prohibitions, not aspirations
- [ ] Every input names an id and the command that retrieves it
- [ ] Every step a worker could get wrong states its quality bar
- [ ] Done Criteria are yes-or-no checks, and end with `lore done <mission-id>`
- [ ] Hands On names the receiving mission, or says the mission is terminal
- [ ] No file path is offered as the way to reach a doctrine, artifact or codex document
- [ ] The mission appears in the design document's table and its Missions list
