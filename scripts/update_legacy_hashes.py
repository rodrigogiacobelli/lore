#!/usr/bin/env python3
"""Regenerate ``src/lore/defaults/legacy-hashes.json`` — a release pre-flight step.

A project initialised before the install manifest existed has no record of what
Lore installed. `lore.reconcile.legacy_recorded` rebuilds one by matching the
files under ``.lore/skills/`` against every hash Lore has ever shipped for that
path; this script is what puts those hashes on the shelf.

Run it from the repository root before cutting a release (``ops-publish-pypi``)::

    python scripts/update_legacy_hashes.py

It hashes every file under ``src/lore/defaults/skills/``, prefixes each relative
path with ``.lore/skills/`` and **unions** the result into the existing file.
Rows are never removed: a project may hop from 0.8 to 0.14 in one upgrade and
needs every intermediate hash to recognise what it has. Running it twice on an
unchanged tree produces a byte-identical file.

Each file is hashed **once per access mode**, because a skill is rendered on
its way to disk: the ``<!-- lore:access ... -->`` blocks are resolved for the
project's answer, so the raw source under ``src/`` is bytes no project has ever
held. A row carrying only the raw digest matches nothing installed by 0.10.0 or
later — which is precisely the projects that commit their skills and gitignore
their manifest, and so reconcile through this table on every fresh clone. A
file with no access blocks renders identically either way and records one
digest.

Run it **before** a release renames or deletes a skill directory, or the
pre-consolidation hashes are gone from the working tree and the upgrade path for
existing projects has nothing to match against.

Two rows in the table are **historical only** and this script neither writes
nor removes them (``merge`` keeps every row it did not produce):

``.lore/skills/.gitignore`` and ``.lore/LORE-AGENT.md``. Every release up to
0.9.0 wrote both verbatim, one variant per release, and their digests are
recorded from the published wheels. From 0.10.0 both are *rendered* — the
listing from the answered skill set, the agent doc from the access mode and the
install roots — so there is no single byte sequence a release could record, and
none is needed: a project initialised by 0.10.0 or later has an install
manifest, which is a better record than any hash table. What the historical
rows buy is the upgrade itself. Without them the copy of the listing that the
pre-feature ``GETTING-STARTED.md`` told people to make into ``.claude/skills/``
reads as the user's own file and survives an upgrade pointing at thirteen
deleted directories, and the agent doc keeps advertising skills the same run
deleted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from lore.initplan import AccessMode  # noqa: E402  (needs the path insert above)
from lore.manifest import bytes_digest  # noqa: E402
from lore.skills import render as render_for_access  # noqa: E402  (this module has its own `render`)

LEGACY_HASHES_VERSION = 1
LEGACY_SKILLS_PREFIX = ".lore/skills/"
SKIPPED_NAMES = frozenset({".gitignore"})

DEFAULT_SKILLS_DIR = REPO_ROOT / "src" / "lore" / "defaults" / "skills"
DEFAULT_TARGET = REPO_ROOT / "src" / "lore" / "defaults" / "legacy-hashes.json"


def installed_digests(source: str, path: str) -> list[str]:
    """The digests *source* can have once installed — one per access mode.

    ``lore.skills.render`` is the one thing that decides what an installed skill
    says, so it decides what this table records. Deduplicated and sorted: a file
    with no access blocks renders the same bytes for every mode.
    """
    return sorted(
        {
            bytes_digest(render_for_access(source, mode, source=path).encode("utf-8"))
            for mode in AccessMode
        }
    )


def collect(skills_dir: Path) -> dict[str, list[str]]:
    """Hash every shipped skill file as installed, keyed by the path it installs to."""
    fresh: dict[str, list[str]] = {}
    for candidate in sorted(skills_dir.rglob("*")):
        if not candidate.is_file() or candidate.name in SKIPPED_NAMES:
            continue
        relative = candidate.relative_to(skills_dir).as_posix()
        key = LEGACY_SKILLS_PREFIX + relative
        fresh[key] = installed_digests(
            candidate.read_text(encoding="utf-8"), f"skills/{relative}"
        )
    return fresh


def read_existing(target: Path) -> dict[str, list[str]]:
    """Return the rows already on the shelf, or an empty table for a first run."""
    if not target.is_file():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    return dict(payload.get("files", {}))


def merge(existing: dict[str, list[str]], fresh: dict[str, list[str]]) -> dict[str, list[str]]:
    """Union *fresh* into *existing*, removing nothing and deduplicating hashes."""
    merged = {path: list(hashes) for path, hashes in existing.items()}
    for path, hashes in fresh.items():
        merged[path] = sorted(set(merged.get(path, [])) | set(hashes))
    return {path: sorted(set(merged[path])) for path in sorted(merged)}


def render(table: dict[str, list[str]]) -> str:
    """Serialise *table*, deterministically, so an unchanged tree rewrites byte-identically."""
    payload = {"legacy_hashes_version": LEGACY_HASHES_VERSION, "files": table}
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def update(skills_dir: Path, target: Path) -> dict[str, list[str]]:
    """Union the hashes of *skills_dir* into *target* and return the merged table."""
    table = merge(read_existing(target), collect(skills_dir))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(table), encoding="utf-8")
    return table


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skills-dir", type=Path, default=DEFAULT_SKILLS_DIR)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    args = parser.parse_args(argv)
    update(args.skills_dir, args.target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
