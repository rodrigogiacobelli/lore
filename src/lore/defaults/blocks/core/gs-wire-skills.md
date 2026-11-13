---
id: gs-wire-skills
feature: core
requires: ['pseudo:skills']
---
## What the setup did

For each agent you selected it wrote an instruction file and installed the skills:

| Agent | Instruction file | Skills install to |
|---|---|---|
| Claude Code | `CLAUDE.md` | `.claude/skills/` |
| Codex, Cursor, Windsurf, Zed, Amp, OpenCode | `AGENTS.md` | `.lore/skills/` |
| Gemini CLI | `GEMINI.md` | `.lore/skills/` |
| Qwen Code | `QWEN.md` | `.lore/skills/` |
| Cursor, native rules | `.cursor/rules/lore.mdc` | `.lore/skills/` |
| None | none | `.lore/skills/` |
