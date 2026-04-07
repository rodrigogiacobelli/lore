---
id: conceptual-relationships-watcher--doctrine
title: "Watcher to Doctrine"
related:
  - conceptual-entities-watcher
  - conceptual-entities-doctrine
  - conceptual-workflows-watcher-crud
stability: stable
summary: >
  A Watcher's action field may name a Doctrine by filename stem. There is no FK.
  Lore stores and surfaces the reference but never executes it. Execution is the
  consuming layer's responsibility (Realm, CI, human).
---

# Watcher to Doctrine

A Watcher is a passive trigger declaration. Its `action` field names what should happen when the Watcher's condition fires. When the action is a Doctrine, the field holds the Doctrine's filename stem. Lore stores and surfaces this reference without validating it and without executing it. Execution belongs to the consuming layer — Realm, a CI pipeline, or a human operator.

## Named Roles

### Named Doctrine (passive target)

The Doctrine whose filename stem appears in the Watcher's `action` field. The Doctrine plays no active role in the Watcher's storage, validation, or display. It is the consuming layer that reads the Watcher's action and decides to execute the Doctrine.

### Referring Watcher (active declarer)

The Watcher that names the Doctrine in its `action` field. The Watcher declares intent; it does not enforce or verify the Doctrine's existence.

## Data on the Connection

The reference is stored as a text value inside the Watcher's YAML file.

| Location | Field | Mutable |
|----------|-------|---------|
| Watcher YAML | `action` | Yes (edit the Watcher file) |

There is no FK, no join table, and no database column linking Watchers to Doctrines.

## Business Rules

- **No validation:** Lore does not check whether the named Doctrine exists when storing or displaying a Watcher. A Watcher with `action: non-existent-doctrine` is valid in Lore's model.
- **One action per Watcher:** The `action` field is a single optional string. A Watcher with no `action` is valid.
- **Lore never executes:** Lore stores and surfaces Watcher definitions. The consuming layer (Realm, CI, human) is responsible for polling Watchers, evaluating conditions, and triggering the named action.
- **Doctrine changes do not affect Watchers:** Renaming or deleting a Doctrine has no effect on Watcher records. The stale name persists in the Watcher file until manually updated.
- **Consuming layer resolves:** When Realm (or any consumer) reads a Watcher and its `action` names a Doctrine, the consumer is responsible for loading and executing that Doctrine.

## Concrete Examples

### Watcher naming a Doctrine

```yaml
# .lore/watchers/on-pr-merged.yaml
id: on-pr-merged
condition: "github.event == 'pull_request.merged'"
action: feature-build-workflow
```

→ Lore stores this without checking whether `feature-build-workflow` doctrine exists.

### Consuming layer executes the Doctrine

```
# Realm polls watchers:
$ lore watcher list
on-pr-merged  condition: ...  action: feature-build-workflow

# Realm evaluates the condition, then:
$ lore doctrine show feature-build-workflow
# Realm creates a Quest and Missions from the Doctrine steps
```

→ Lore's role ends at surfacing the Watcher. Execution is Realm's responsibility.

### Watcher with no action

```yaml
id: on-deploy-complete
condition: "deploy.status == 'success'"
# action is omitted — valid in Lore
```
