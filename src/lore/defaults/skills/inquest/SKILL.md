---
name: inquest
description: Audit finished work against its original intent and trace a missed requirement to the link in the chain that dropped it
---

# Inquest

An inquest is a backward audit of finished work. Use it when a quest is closed but something is wrong — a requirement from the original request is missing, or a codex mandate ("the codex says do X") was silently skipped — and you need to know *which* link in the chain dropped it and *who* ran that link.

A doctrine is a chain: each step consumes upstream outputs and produces its own. A requirement can fall out at any handoff. The inquest reconstructs the chain, walks it link by link, and produces a **verdict** — a blame file naming the culprit link, the failure mode, the responsible party, and the evidence.

This skill orchestrates evidence collection. The tracing methodology lives in the `inquest-design` artifact — retrieve it and follow it.

## Inputs

You need two things from the user. Ask for any that are missing:

1. **The work** — a quest ID (preferred), or a branch / commit range that contains the completed work.
2. **The issue** — a precise statement of what is missing or wrong. "The export endpoint enforces no rate limit" is usable; "something feels off" is not. Push back until the issue is concrete and verifiable.

## Steps

### 1. Load the methodology

```
lore artifact show inquest-design
```

Follow it. The steps below collect the evidence it needs.

### 2. Reconstruct the chain

Identify the doctrine that drove the work and list its steps in dependency order:

```
lore show <quest-id>
lore missions -q <quest-id>
lore doctrine show <doctrine-id>
```

For each doctrine step record: step ID, knight, mission ID, mission status. `lore show <mission-id>` returns the knight persona and the mission notes the executing agent actually received — those notes are the instructions that link was held to.

### 3. Collect the evidence

Per the `inquest-design` artifact, gather:

- **The original intent** — the quest description and the first transient doc (PRD / context map) in `.lore/codex/transient/`.
- **The intermediate outputs** — every transient doc in `.lore/codex/transient/`. These are the per-link outputs: PRD, tech spec, user stories.
- **The handoffs** — `lore board` messages passed between missions.
- **The commits** — `git log` and `git show <sha>` for the range that delivered the work. Commit messages reference `US-xxx` story IDs.
- **The codex obligations** — for every file the work touched, run `lore impacts <path>`. Any codex doc that binds a touched file is a mandate the executing agent was obligated to honor. This is how you find a skipped "the codex says do X".

### 4. Trace the custody chain

Apply the methodology: pin the requirement to its origin, then walk each link asking the two-part custody question — present inbound? present outbound? The culprit is the first link where the requirement entered but did not leave. Classify the failure mode.

### 5. Write the verdict

Write the blame file to `.lore/codex/transient/inquest-<slug>.md` using the verdict template in the `inquest-design` artifact. `<slug>` is a short kebab-case name for the issue.

The verdict is a transient codex doc — frontmatter `id`, `title`, `summary`. It is retrievable with `lore codex show inquest-<slug>` and survives `oracle` runs (unlike `.lore/reports/`, which is wiped on every run).

### 6. Present the verdict

Summarize for the user: the culprit link, the failure mode, the responsible party, and the recommended remediation. Do not re-open missions or re-run steps — the inquest reports, the human decides.

## Notes

- An inquest assigns blame to a *link*, not always an *agent*. If every executor faithfully honored its instructions and the requirement still vanished, the doctrine is at fault — no step owned the requirement. Say so plainly; that is a doctrine defect, not an agent defect.
- An **override** — an executor that saw the requirement and explicitly decided against it — may be a legitimate judgment call. Flag it for the human; do not condemn it.
- One inquest, one requirement. If the work has several missing requirements, run a separate inquest per requirement.
- The inquest is read-only on the audited work. It produces one verdict file and changes nothing else.
