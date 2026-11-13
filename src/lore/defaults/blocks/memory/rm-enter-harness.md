---
id: rm-enter-harness
feature: memory
route: harness
---
| Goal | Where |
|---|---|
| Find documents by keyword | grep `.lore/codex/**/*.md` |
| Read a document | read `.lore/codex/<layer>/<id>.md` |
| See the whole taxonomy | list `.lore/codex/` |
| Read the vocabulary | read `.lore/codex/glossary.yaml` |

Reading files gives up two things, which are now yours to do. **Glossary terms are not attached** to what you read: look
up an unfamiliar term in the glossary file. **The group is the directory:** a document's or rite's subfolder is its group,
so grep for the id rather than guessing the path.
