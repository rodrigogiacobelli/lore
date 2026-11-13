---
id: sg-delta
feature: memory
---
Merging a version bump is where changelog narration leaks in. Carry the *fact* into the project file, never the delta:
write "`binds:` maps a document to the code files it governs", not "this release added `binds:`". If
`.lore/codex/codex.md` does not exist, the setup already seeded a fresh one and there is nothing to reconcile.
