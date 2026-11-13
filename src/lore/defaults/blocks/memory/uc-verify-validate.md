---
id: uc-verify-validate
feature: memory
commands: [health --scope schemas]
---
### 4. Verify and report

Run `lore health --scope schemas`: it builds the merged validator for the kind and validates every existing doc against it.
**0 errors** means the overlay is well-formed and every doc satisfies it. A `scan_failed` issue naming the overlay means the
overlay itself is malformed; a per-doc error means a doc now violates it (typically a newly `required` field older docs
lack): make the field optional or backfill, then re-run.
