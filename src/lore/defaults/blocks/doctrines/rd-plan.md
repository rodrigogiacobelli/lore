---
id: rd-plan
feature: doctrines
---
### 3. Plan the missions

For each mission in the doctrine (or the trimmed subset) list its mission id, title, type, phase and depends-on, from the
design table. Keep this list as a visible checklist in your own task list or notes, one line per mission with its status
(`pending`, `running`, `done`, `blocked`), and update it as the run moves. When the run is trimmed, keep the original phase
numbers and drop dependencies on skipped missions.

#### Mission types

`agent` goes to a worker (a subagent); `constable` is an orchestrator chore you do inline yourself; `human` needs the user,
so stop and ask, and never do it yourself.
