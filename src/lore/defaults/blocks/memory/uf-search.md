---
id: uf-search
feature: memory
capabilities: [memory-index]
---
## Making the search find it

**The match is a plain substring of the whole query**, casefolded, against the member ids, the name and the summary. It does
not split the query into words, so `soft delete` does not find "soft-delete". **Spell out, at least once and unhyphenated,
the phrase a reader would actually type**, and run the queries a cold agent would send; when one misses, fix the summary.
