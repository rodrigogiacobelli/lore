---
id: sm-purpose
feature: memory
---
# Store Memory

One entry point for writing to project memory. Use it whenever the user asks you to record, correct, or retire something
the project should remember: "document this", "the codex is wrong about X", "capture this ticket", "write down how we do
Y", "drop that doc". Project memory has three shapes and this skill covers all three:

| Shape | Holds | Lives in |
|---|---|---|
| **Codex document** | Semantic knowledge: what is true about the system today | `.lore/codex/` |
| **Rite** | Procedural knowledge: how to do or diagnose a recurring task | `.lore/rites/` |
| **Source snapshot** | A verbatim copy of an upstream artifact, plus the canonical docs it changed | `.lore/codex/sources/` |
