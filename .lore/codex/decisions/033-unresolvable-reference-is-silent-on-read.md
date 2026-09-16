---
id: decisions-033-unresolvable-reference-is-silent-on-read
title: "ADR-033: An unresolvable doctrine mission is silent on read and reported only by lore health"
summary: >
  ADR recording that a read never reports a broken reference. lore show on an
  unresolvable doctrine_mission prints the stored reference, omits the mission
  instructions section entirely, exits 0 and prints nothing else; --json carries
  the stored reference and doctrine_mission_contents null. lore health --scope
  doctrines is the single reporter, at ERROR severity, for active missions only.
binds:
  - src/lore/doctrine.py
  - src/lore/health.py
  - src/lore/db.py
related:
  - decisions-030-knight-entity-removed
  - conceptual-workflows-show
  - conceptual-workflows-health
  - conceptual-relationships-doctrine--mission
---

# ADR-033: An unresolvable doctrine mission is silent on read and reported only by `lore health`

## Context

`lore show <mission-id>` printed `Warning: knight file "x" not found in
.lore/knights/` on stdout when a mission's knight did not resolve, and
`lore health --scope knights` reported the same condition as an error. A worker
agent parsing `lore show` saw a warning line inside what it was reading as its
brief, and the same fact was reported twice by two commands with two
severities.

## Decision

A read never reports a broken reference.

`lore show` on an unresolvable `doctrine_mission` prints the stored reference,
omits the `--- Mission Instructions ---` section entirely, exits 0 and prints
nothing else; `--json` carries the stored reference and
`doctrine_mission_contents: null`.

`lore health --scope doctrines` is the single reporter, at ERROR severity, for
active missions only.

## Rationale

- **Diagnostic text inside a worker's brief is indistinguishable from
  content.** A worker reading `lore show` output as instructions has no way to
  tell a warning line from a line it is supposed to act on.
- **One fact deserves one reporter.** Two commands reporting the same condition
  at two severities forces a reader to decide which one is authoritative.
- **A read failing for an authoring mistake blocks the wrong person.** The
  worker did not edit the doctrine; refusing to hand it the rest of its brief
  helps nobody.

## Alternatives Considered

| Option | Why rejected |
|--------|-------------|
| **Keep the warning line** | It puts diagnostic text inside a worker's instructions, where it is indistinguishable from content. |
| **Exit non-zero on an unresolvable reference** | A worker would be unable to read a mission whose doctrine was edited under it, which is a read failing for an authoring mistake. |
| **Report it on stderr instead of stdout** | Still a second reporter of a fact `lore health` owns, and stderr noise on a successful read trains agents to ignore stderr. |

## Consequences

**Easier:**
- A worker's brief is content and nothing else, so an agent can parse it
  without a rule for discarding diagnostic lines.
- The repair path is one command: `lore health --scope doctrines` names every
  dangling reference, one row per reference however many missions carry it.

**Harder:**
- A maintainer who edits a doctrine and breaks a reference learns about it only
  when `lore health` is run, not at the moment a worker reads the mission.
- A `--json` consumer must distinguish "no reference stored" from "reference
  stored but unresolvable" by reading two fields rather than one.

## Constraints Imposed

1. **No read command reports a broken reference.** `lore show` and the
   `lore.api` read functions return the stored reference and null contents,
   exit 0, and print no diagnostic.
2. **`lore health --scope doctrines` is the single reporter, at ERROR
   severity.** Adding a second reporter requires amending this ADR.
3. **Only active missions are reported.** A closed or deleted mission carrying
   a dangling reference raises nothing.

## Status History

| Date | Status | Note |
|------|--------|------|
| 2026-09-16 | accepted | Recorded alongside `_dangling_doctrine_missions` in `health.py` and the silent read path in `lore show`. |
