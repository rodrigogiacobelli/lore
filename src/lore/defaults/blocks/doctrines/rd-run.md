---
id: rd-run
feature: doctrines
---
### 6. Drive the run

Work in dependency order: a mission starts only when everything it depends on is `done`.

- Dispatch every ready `agent` mission to a worker with its brief; independent missions run in parallel.
- Do `constable` missions yourself, inline, as soon as they are ready.
- At a `human` mission stop, say what the user must do, and wait for their answer before going on.
- When a worker returns, check the result against the acceptance criteria, mark the mission `done` and pass its output to the
  missions that need it. If it is blocked or fails, mark it `blocked`, tell the user why and ask how to proceed.
- Show the updated checklist whenever the status changes.
