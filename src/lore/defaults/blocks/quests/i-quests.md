---
id: i-quests
feature: quests
---
## Quests and missions

A **quest** is a body of work (a feature, a fix, a refactor) that holds **missions**. A **mission** is one task for
one agent, with a status (`open`, `in_progress`, `done`, `blocked`), a priority, a description and acceptance
criteria. Its type drives dispatch: `agent` missions go to a worker, `constable` missions are orchestrator chores
handled inline, `human` missions are left for the human. You are either the orchestrator or a worker.
