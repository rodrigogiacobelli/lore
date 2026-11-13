---
id: uc-backfill-harness
feature: memory
route: harness
---
Backfill one doc at a time. Add the key to each document's frontmatter block yourself, in the type the overlay declares (a
scalar as a plain value, an array as a YAML list). To drop a custom field again, remove it from the overlay's
`properties` and `required`, then delete the key from every doc that carries it: a doc holding a field no overlay declares
fails with `Unknown property`. Nothing validates a hand-edit as you make it, so check the whole batch at the end.
