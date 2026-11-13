---
id: iq-purpose
feature: quests
requires: [memory]
---
# Inquest

An inquest is a backward audit of finished work. Use it when a quest is closed but something is wrong (a requirement from
the original request is missing, or a rule the project documents was silently skipped) and you need to know *which* link in
the chain dropped it and *who* ran that link.

A doctrine is a chain: each mission consumes upstream outputs and produces its own. A requirement can fall out at any
handoff. The inquest reconstructs the chain, walks it link by link, and produces a **verdict**: a blame file naming the
culprit link, the failure mode, the responsible party, and the evidence.

## Inputs

You need two things from the user. Ask for any that are missing:

1. **The work**: a quest id (preferred), or a branch / commit range that contains the completed work.
2. **The issue**: a precise statement of what is missing or wrong. "The export endpoint enforces no rate limit" is usable;
   "something feels off" is not. Push back until the issue is concrete and verifiable.
