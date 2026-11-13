---
id: uc-write-overlay
feature: memory
---
### 3. Guard, then write

Run the add-only guard below **before** writing so a malformed overlay never lands, and shape the overlay as shown. Only when both checks pass, write `.lore/custom-schemas/<kind>.yaml`, creating the
file or rewriting it with the existing fields plus your change.
