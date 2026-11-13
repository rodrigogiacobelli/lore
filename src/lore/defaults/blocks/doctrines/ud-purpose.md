---
id: ud-purpose
feature: doctrines
---
# Update Doctrine

Author a Lore doctrine. This skill **creates a doctrine or edits an existing one**, whichever the request calls for: "add
a review mission to `tdd-implementation`" and "build me a hotfix workflow" both land here.

A doctrine is a directory of prose for a standard body of work: a design document that says how the work is done, and one
mission file per reusable instruction. An orchestrator reads the design and translates it into a quest and its missions; a
worker is handed one mission body. Lore parses none of it: order, type and dependencies are the orchestrator's to read out
of the design prose.

A mission file is the full execution spec for its worker. The worker receives that body plus its Lore mission's own
description and nothing else, so it must be able to finish the task from those two alone.
