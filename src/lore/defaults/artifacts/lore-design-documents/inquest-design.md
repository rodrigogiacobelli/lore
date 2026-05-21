---
id: inquest-design
title: Inquest — Chain-of-Custody Procedure
summary: >
  Procedure for auditing finished work against its original intent and
  tracing a missed requirement to the link in the doctrine chain that
  dropped it. Pin the requirement to its origin, reconstruct the chain,
  walk each link with the two-part custody question, classify the failure
  mode, and write a verdict. Used by the `inquest` skill — run this
  whenever a quest closed but a requirement went missing.
---

# Inquest — Chain-of-Custody Procedure

An inquest answers one question: a requirement is missing from finished work — **which link in the chain dropped it, and who ran that link?**

A doctrine is a chain of links. Each step (link) consumes the outputs of upstream links and produces its own. The original request enters at the head of the chain; delivered code and docs leave at the tail. A requirement is a piece of intent that must survive every handoff. When it does not, it died in custody at exactly one link — this procedure finds that link.

The output is a **verdict**: a blame file that names the culprit link, the failure mode, the responsible party, and the evidence.

## Vocabulary

- **Requirement (R)** — the precise thing that is missing or wrong. State it as one verifiable sentence: "The export endpoint enforces no rate limit" — not "rate limiting is off."
- **Link** — one doctrine step, executed by one knight (or constable / human) in one mission, producing one or more outputs.
- **Custody** — a link *holds* R when R is present in what it consumed (inbound) and obligated to be present in what it produced (outbound).
- **Origin** — the link where R *first should have existed*. Everything upstream of the origin is irrelevant to the inquest.

## Step 1 — Pin the requirement and its origin

Write R as one verifiable sentence. Then find where R should have entered the chain. There are two origin classes:

- **External origin** — R is in the original request. It should appear in the quest description or the first transient doc (PRD / context map). The origin link is the first step that consumed the request.
- **Codex origin** — R is mandated by a codex document — a standard, an ADR, a constraint ("the codex says do X"). An agent at some link was obligated to honor it because a codex doc binds a file that link touched. Find these by running `lore impacts <path>` on every touched file. The origin link is the first step obligated to honor that codex doc.

If R has no origin in either class — it is in neither the request nor the codex — then R is not a dropped requirement. It is a *new* request. Stop: there is no one to blame. Report that and end the inquest.

## Step 2 — Reconstruct the chain

List the doctrine steps in dependency order (`needs`). For each link, record:

| Field | Source |
|---|---|
| Step ID, title | `lore doctrine show <id>` |
| Knight (executor) | doctrine step `knight:` |
| Mission ID, status | `lore missions -q <quest-id>` |
| Instructions given | `lore show <mission-id>` — the mission notes the agent actually received |
| Inbound (what it consumed) | upstream link outputs + board messages |
| Outbound (what it produced) | transient docs, files, commits |

The inbound of a link is the outbound of its upstream links. That equality is the custody handoff — the place a requirement is most often dropped.

## Step 3 — Walk the chain

Start at the origin link. At each link, ask the **two-part custody question**:

1. **Inbound** — was R present in what this link consumed?
2. **Outbound** — was R present in what this link produced?

Record one of four states per link:

| Inbound | Outbound | Meaning |
|---|---|---|
| yes | yes | R survived this link — continue downstream |
| yes | no  | **R died here** — this is the culprit link |
| no  | yes | R was introduced here (the origin) — continue downstream |
| no  | no  | R never reached this link — the break is upstream |

The culprit is the **first** link with `inbound=yes, outbound=no`. If R never appears outbound anywhere, the culprit is the **origin link itself** — it never captured R at all.

## Step 4 — Classify the failure mode

The verdict must name *which* failure occurred — the remedy differs per mode:

| Mode | Signature | Responsible party |
|---|---|---|
| **Drop** | R was in the input; the executor silently omitted it from the output | The executor — knight + mission |
| **Never-captured** | R was in the *request* but the first link never wrote it into the first transient doc | The first link's executor — intake failure |
| **Distortion** | R is present in the output but weakened or wrong — not absent, degraded | The executor — partial fault |
| **Override** | The executor saw R and explicitly decided against it — visible in a commit message, mission notes, or a board message | A judgment call. **May be legitimate. Flag for the human — do not condemn.** |
| **Instruction gap** | R was in the input, but no step's mission notes — and the doctrine itself — ever told any executor to carry R. Every executor faithfully did what it was told. | The **doctrine**, not any agent. A doctrine defect. |

The instruction-gap case is the most important distinction. If you cannot point to an instruction that obligated a specific executor to carry R, you cannot blame that executor. Blame the chain design instead: the doctrine has no link that owns R.

## Step 5 — Write the verdict

Write the blame file to `.lore/codex/transient/inquest-<slug>.md`:

```markdown
---
id: inquest-<slug>
title: "Inquest: <one-line issue>"
summary: >
  Verdict of the inquest into <issue>. Culprit: <link>.
  Failure mode: <mode>. Responsible: <party>.
---

# Inquest: <one-line issue>

## The Requirement

<R as one verifiable sentence.> Origin: <external request | codex:<doc-id>>.

## The Chain

| Link | Executor | Mission | Inbound R? | Outbound R? |
|------|----------|---------|------------|-------------|
| <step-id> | <knight> | <mission-id> | yes/no | yes/no |
| ... | | | | |

## Verdict

- **Culprit link:** <step-id> — <title>
- **Failure mode:** <Drop | Never-captured | Distortion | Override | Instruction gap>
- **Responsible:** <knight + mission-id | the doctrine <id> | the original request>

## Evidence

- <transient doc / file / commit SHA — quote the exact line, or name the exact omission, that proves it>
- <`lore impacts <path>` output proving the codex obligation, if the origin is a codex mandate>

## Remediation

<One concrete action. Re-run a step? Amend the doctrine to add a link that
owns R? Fix a codex binding? Name it.>
```

## Rules

- **One inquest, one requirement.** If the work has several missing requirements, run a separate inquest per requirement — a verdict that blames three links for three issues is unreadable.
- **The inquest is read-only on the audited work.** It produces one verdict file and changes nothing else — no re-opened missions, no reverts. The inquest reports; the human decides.
- **Evidence is mandatory.** Every claim in the verdict cites a transient doc, a file, a commit SHA, or a command output. A verdict with no evidence is an accusation, not a finding.
- **Blame a link, not always an agent.** The doctrine itself is a valid culprit — that is the instruction-gap mode.
- **An override is a finding, not a conviction.** Surface it; let the human rule on it.
