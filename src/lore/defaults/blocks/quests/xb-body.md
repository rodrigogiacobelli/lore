---
id: xb-body
feature: quests
---
#### What goes in a mission description

The worker already receives the doctrine mission body through `-D`, so do not restate it. The description carries what is
specific to this run: the feature context and acceptance criteria, relevant paths or constraints from the user's input, and
the board wiring (which mission ids this worker posts to; use the real ids, a worker cannot guess an id that did not exist
until you created the quest).
