---
id: interactive-init-us-008
title: US-008 — An install manifest records every file Lore writes and its hash
summary: lore init writes .lore/.install-manifest.json listing every path it installed
  with the sha256 of the rendered bytes, distinguishing files Lore owns whole from
  marked sections inside user-owned files, and falls soft with one warning when the
  manifest is unreadable or carries an unrecognised version.
type: user-story
related:
- interactive-init-prd
- interactive-init-tech-spec
- tech-arch-install-manifest
- tech-arch-initialized-project-structure
- conceptual-workflows-init-reconcile
- conceptual-workflows-error-handling
---

# US-008 — An install manifest records every file Lore writes and its hash

## Metadata

- **ID:** US-008
- **Status:** final
- **Epic:** _Manifest and Reconciliation_
- **Author:** Tech Lead — Tech Planning
- **Date:** 2026-08-25
- **PRD:** `lore codex show interactive-init-prd`
- **Tech Spec:** `lore codex show interactive-init-tech-spec`

---

## Story

As _a developer upgrading Lore_, I want _Lore to keep a record of every file it installed and what that file looked like when it did_, so that _the next upgrade can tell my edits apart from its own output and never destroy the former_.

## Context

FR-25 requires Lore to record every file it writes, with its hash, in an install manifest. Everything the reconciliation algorithm decides (US-009) rests on that record being exact.

Tech Spec §2.1 fixes one hash function in one place and hashes **raw bytes with no newline normalisation**, so a CRLF checkout registers as an edit — the honest answer, since Lore wrote LF. The manifest records the hash of the **rendered** file, after access-mode selection, which is what makes flipping `--access` a clean overwrite rather than a phantom user edit (PRD workflow 4).

Tech Spec §6.2's `kind` field is the safety distinction the draft design lacked. `owned` means Lore wrote the whole file and the hash covers the whole file; the entry is eligible for removal. `section` means Lore wrote a marked block inside a user-owned file, the hash covers **only the rendered block text between the markers**, and the entry is never removable — retiring the source deletes the block and leaves the file otherwise byte-identical. Without that split, retiring an agent would delete a user's `CLAUDE.md`.

`answers` and `targets` are informational. The reconciliation algorithm reads **only `files`** — one source of truth for the decision (`standards-dry`).

---

## Acceptance Criteria

### E2E Scenarios

#### Scenario 1: The manifest lands where nothing needs a gitignore change

**Given** a project initialised by `lore init`
**When** a test inspects `.lore/`
**Then** `.lore/.install-manifest.json` exists, parses as JSON, and `git check-ignore` reports it ignored by the existing `.lore/.gitignore` — whose first line is `*` and which un-ignores only `.gitignore`, `config.toml`, `custom-schemas`, `codex`, `artifacts`, `knights`, `doctrines`, `watchers` and `rites`

#### Scenario 2: Every recorded path is repo-root-relative POSIX

**Given** a project initialised with an agent whose files sit outside `.lore/`
**When** a test reads the manifest's `files` array
**Then** every `path` is relative to the project root, uses `/` separators on every platform, never begins with `/` and never contains `..`, and the array is sorted by `path`

#### Scenario 3: An unreadable manifest warns once and does not stop the run

**Given** a project whose `.lore/.install-manifest.json` contains the bytes `{not json`
**When** the caller runs `lore init`
**Then** stderr carries exactly one line matching `lore: unreadable install manifest at <path>: <reason> (falling back to legacy hashes)`, the command exits 0, and a fresh valid manifest is on disk afterwards

#### Scenario 4: An unrecognised manifest version is treated as unreadable

**Given** a manifest whose `manifest_version` is `99`
**When** the caller runs `lore init`
**Then** the same single warning is emitted, the run proceeds through the legacy path, no unmatched file is removed, and exit is 0

### Unit Test Scenarios

- [ ] `lore.manifest.bytes_digest`: returns `"sha256:" + hexdigest` for a bytes input; the prefix is present; the digest of `b""` is stable across calls
- [ ] `lore.manifest.file_digest`: equals `bytes_digest(path.read_bytes())`; a file containing `\r\n` hashes differently from the same file with `\n` (no newline normalisation)
- [ ] `lore.manifest.section_digest`: hashes only the text between the markers, markers excluded; changing prose outside the markers leaves the digest unchanged; changing text inside changes it
- [ ] `lore.manifest.write` / `lore.manifest.load`: round-trip preserves `manifest_version`, `lore_version`, `catalogue_version`, `answers`, `targets` and every `files` entry's `path`, `kind`, `source` and `hash`
- [ ] `lore.manifest.write`: emits `files` sorted by `path`; two writes of the same content differ only in `generated_at`
- [ ] `lore.manifest.load`: an absent file returns `None` with no warning
- [ ] `lore.manifest.load`: unparseable JSON returns `None` and emits one stderr warning naming the path and the reason
- [ ] `lore.manifest.load`: an unrecognised `manifest_version` returns `None` and emits the same single warning
- [ ] `lore.manifest.load`: a manifest whose `files` entry is missing a required key is treated as unreadable, not partially loaded
- [ ] `lore.manifest`: paths are stored POSIX and rehydrated against a supplied project root — asserted with a `PureWindowsPath`-style input to prove no platform separator leaks in
- [ ] `lore.paths.install_manifest_path`: returns `<root>/.lore/.install-manifest.json`

---

## Out of Scope

- Deciding what to do with a recorded entry — US-009.
- The packaged legacy-hash fallback — US-010.
- Writing the manifest at the end of an apply — US-015 (ordering).
- Auditing the manifest through `lore health` — US-021.

---

## References

- PRD: `lore codex show interactive-init-prd` FR-25
- Tech Spec: `lore codex show interactive-init-tech-spec` §2.1, §6.1, §6.2, §15
- `lore codex show tech-arch-install-manifest` — the doc that governs `src/lore/manifest.py`
- `lore codex show conceptual-workflows-error-handling` — the fall-soft warning contract

---

## Tech Notes

### Implementation Approach

- **Files to create:** `src/lore/manifest.py` — `file_digest(path) -> str`, `bytes_digest(data: bytes) -> str`, `section_digest(text: str, begin: str, end: str) -> str`, `load(project_root) -> Manifest | None`, `write(project_root, *, answers, targets, files, lore_version, catalogue_version) -> Path`. Format exactly as Tech Spec §6.2. `MANIFEST_VERSION = 1` as a module constant.
- **Files to modify:** `src/lore/paths.py` — add `install_manifest_path(root: Path) -> Path` beside `config_path` at `src/lore/paths.py:64`.
- **Schema changes:** none. The manifest is generated project data, not a validated entity; an unreadable one is a fall-soft condition, never an error.
- **Dependencies:** US-001 (`PlannedFile` supplies `path`, `kind`, `source`, `digest`).

The warning uses the existing stderr convention from `conceptual-workflows-error-handling`; it is **not** routed through `lore.config`'s one-warning-per-process latch, which belongs to config parsing. One warning per `load` call that fails is the contract.

`generated_at` is an ISO-8601 UTC string (`2026-08-25T14:32:00Z`). It is the only field that differs between two otherwise identical manifests, which is what makes the US-015 idempotency assertion expressible.

### Test File Locations

| Type | Path | Notes |
|------|------|-------|
| E2E | `tests/e2e/test_init_reconcile.py` — NEW | Anchor `conceptual-workflows-init-reconcile`; the manifest lifecycle scenarios. File may only be written after that codex doc exists (`technical-test-guidelines` §3) |
| Unit | `tests/unit/test_manifest.py` — NEW | Digests, round-trip, fall-soft paths |
| Unit | `tests/unit/test_paths.py` — extended | `install_manifest_path` |

### Test Stubs

```python
# E2E — Scenario 1: The manifest lands where nothing needs a gitignore change
# Exercises: lore codex show conceptual-workflows-init-reconcile — Recorded (see tech-arch-install-manifest — Format)
def test_manifest_written_and_already_gitignored(project_dir):
    pass


# E2E — Scenario 2: Every recorded path is repo-root-relative POSIX
# Exercises: lore codex show conceptual-workflows-init-reconcile — Recorded (see tech-arch-install-manifest — Format)
def test_manifest_paths_are_posix_relative_and_sorted(project_dir):
    pass


# E2E — Scenario 3: An unreadable manifest warns once and does not stop the run
# Exercises: lore codex show conceptual-workflows-init-reconcile — A Project With No Manifest
def test_unreadable_manifest_warns_once_and_exits_zero(project_dir, runner):
    pass


# E2E — Scenario 4: An unrecognised manifest version is treated as unreadable
# Exercises: lore codex show conceptual-workflows-init-reconcile — A Project With No Manifest
def test_unknown_manifest_version_falls_through_to_legacy(project_dir, runner):
    pass


# Unit — bytes_digest shape
# Exercises: lore codex show conceptual-workflows-init-reconcile — Recorded (see tech-arch-install-manifest — Hashing)
def test_bytes_digest_carries_sha256_prefix_and_is_stable():
    pass


# Unit — file_digest hashes raw bytes
# Exercises: lore codex show conceptual-workflows-init-reconcile — Recorded (see tech-arch-install-manifest — Hashing)
def test_file_digest_does_not_normalise_newlines():
    pass


# Unit — section_digest covers only the marked block
# Exercises: lore codex show conceptual-workflows-init-reconcile — Recorded (see tech-arch-install-manifest — Hashing)
def test_section_digest_ignores_text_outside_the_markers():
    pass


# Unit — round-trip
# Exercises: lore codex show conceptual-workflows-init-reconcile — Recorded (see tech-arch-install-manifest — Format)
def test_manifest_write_read_round_trip(tmp_path):
    pass


# Unit — files sorted by path
# Exercises: lore codex show conceptual-workflows-init-reconcile — Recorded (see tech-arch-install-manifest — Format)
def test_manifest_files_sorted_by_path(tmp_path):
    pass


# Unit — absent manifest is silent
# Exercises: lore codex show conceptual-workflows-init-reconcile — A Project With No Manifest
def test_absent_manifest_returns_none_without_warning(tmp_path, capsys):
    pass


# Unit — unparseable manifest warns once
# Exercises: lore codex show conceptual-workflows-init-reconcile — A Project With No Manifest
def test_unparseable_manifest_returns_none_and_warns_once(tmp_path, capsys):
    pass


# Unit — unknown manifest_version
# Exercises: lore codex show conceptual-workflows-init-reconcile — A Project With No Manifest
def test_unknown_manifest_version_returns_none_and_warns(tmp_path, capsys):
    pass


# Unit — a malformed files entry is not partially loaded
# Exercises: lore codex show conceptual-workflows-init-reconcile — Recorded (see tech-arch-install-manifest — Format)
def test_missing_required_key_in_files_entry_is_unreadable(tmp_path):
    pass


# Unit — POSIX storage on every platform
# Exercises: lore codex show conceptual-workflows-init-reconcile — Recorded (see tech-arch-install-manifest — Format)
def test_paths_are_stored_posix_regardless_of_platform(tmp_path):
    pass


# Unit — paths.install_manifest_path
# Exercises: lore codex show conceptual-workflows-init-reconcile — Recorded (see tech-arch-install-manifest — Format)
def test_install_manifest_path_points_into_dot_lore():
    pass
```

### Complexity Estimate

**M** — a small module of pure functions plus JSON I/O, but the hashing contract (raw bytes, rendered content, section-only for marker entries) is load-bearing for every later story and has to be exactly right.

### Standards References

- `lore codex show conceptual-workflows-error-handling` — stderr warnings, exit codes
- `lore codex show standards-dry` — `files` is the only input to the reconciliation decision
- `lore codex show technical-test-guidelines`
