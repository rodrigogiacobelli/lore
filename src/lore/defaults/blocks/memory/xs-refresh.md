---
id: xs-refresh
feature: memory
---
## Refresh

1. **Read the stored body.** Strip the frontmatter block and the provenance header; keep the verbatim body.
2. **Fetch the fresh version** the way the user specified. Keep it verbatim.
3. **Diff and present.** Compare stored against fresh and summarise in prose: sections added, sections removed, fields
   and values changed. Paste the raw diff only if asked.
4. **Ask what is codex-worthy.** The user may say "none"; then skip to step 6.
5. **Propose and apply canonical updates** for each codex-worthy change, per `references/codex-doc.md`. A diff-driven
   edit is the easiest place to leak a delta into a canonical document: write what is true after the change, never what
   changed.
6. **Overwrite the snapshot**, rewriting `related` from scratch. Do not merge with the prior list. It holds exactly the
   canonical documents you edited in step 5, plus any from an earlier run that are still accurate for the refreshed
   content. Drop the rest.

   If the user vetoed every proposed edit, re-check each existing `related` entry against the fresh content and carry
   forward only what still applies. An empty `related` is an error; when a refresh leaves nothing valid, ask whether to
   abandon the refresh or name a catch-all canonical document.
