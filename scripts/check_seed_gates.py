#!/usr/bin/env python3
"""Check that every seeded default file is gated by the feature it belongs to.

`lore init` seeds default doctrines, artifacts and a watcher. A seeded file has
no block tags, so the guarantee the instruction files and skills get from
assembly is replaced by gating the file instead: each row of
``lore.init.SEED_GATES`` lists the conditions (the block gate grammar) a profile
must hold for the files it governs to be written, and the rows follow the
*owning* feature of the content. Doctrines and Artifacts are core, so their rows
are ungated by ruling.

This script is the release pre-flight for those rows. It reads every shipped
seed file, finds the ``lore <command>`` phrases in it (prose included), looks
each up in the command-grant table, and reports a file whose gate does not imply
the feature or opt-in a phrase needs. Three kinds of mention are not problems and
are only counted, with ``--routes`` listing them: a phrase granted by the route
(``memory.cli``) — the default content is written for the CLI route —, any
phrase in a core (ungated) row, which is written for the full Lore by ruling,
and a Memory opt-in described by a Memory-owned file.

It reads prose, which is why it is a script and not a test
(decisions-006-no-seed-content-tests).

Run it from the repository root::

    python scripts/check_seed_gates.py [--routes]

Prints one ``where: detail`` line per problem and exits 1 when there is any.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from lore import blocklint, blocks, init  # noqa: E402

DEFAULTS = REPO_ROOT / "src" / "lore" / "defaults"
_GROUP_WORDS = frozenset({"codex", "rite", "glossary", "index", "doctrine", "artifact", "watcher", "board"})
_LORE_PHRASE = re.compile(
    r"\blore\s+((?:--[\w-]+\s+)*)([a-z][\w-]*)(?:\s+(--scope\s+[\w -]*|[a-z][\w-]*))?"
)


def phrases_in(text: str, known: Mapping[str, object]) -> set[str]:
    """The command phrases of the grant table that *text* speaks of, prose included."""
    found: set[str] = set()
    for match in _LORE_PHRASE.finditer(text):
        first, second = match.group(2), match.group(3)
        if first in _GROUP_WORDS and second:
            phrase = f"{first} {second}"
        elif first == "health":
            phrase = "health" + (
                f" --scope {second.split()[1]}" if second and second.startswith("--scope") else ""
            )
        else:
            phrase = first
        if phrase in known:
            found.add(phrase)
    return found


ACCEPTED = {
    "artifacts/lore-design-documents/inquest-design.md": (
        "describes the inquest, a Quests skill; the product owner ruled the document "
        "Memory-owned (the inquest skill itself needs Memory and Quests)"
    ),
}
"""Files whose cross-feature mentions are a recorded ruling, with the reason."""


def _documents_owner(gate: init._SeedGate, grants: Sequence[str]) -> bool:
    """True when every grant is an opt-in of a feature the gate itself requires.

    The codex skeleton documents the whole codex surface — search, map, chaos,
    impacts — and is seeded with Memory. That is a description of the owning
    feature, not a leak of another one, so it is counted, not reported.
    """
    owned = {"memory"} & set(gate.requires)
    return bool(owned) and all(g.startswith("cap:memory-") for g in grants)


def check(*, gates: Sequence[init._SeedGate] | None = None, root: Path = DEFAULTS) -> tuple[list[str], list[str]]:
    """``(problems, route_mentions)`` over the seed files under *root*."""
    table = blocks.load_grants()
    problems: list[str] = []
    routes: list[str] = []
    for gate in init.SEED_GATES if gates is None else gates:
        tree = root / gate.package
        for path in sorted(p for p in tree.rglob("*") if p.is_file()):
            relative = path.relative_to(tree).as_posix()
            if not gate.matches(gate.package, relative):
                continue
            block = blocks.parse_block(
                "---\nid: gate\nfeature: core\nrequires: ["
                + ", ".join(gate.requires)
                + "]\n---\nx\n",
                source="gate",
            )
            implied = blocklint.implied_conditions(block)
            if f"{gate.package}/{relative}" in ACCEPTED:
                continue
            for phrase in sorted(phrases_in(path.read_text(encoding="utf-8"), table)):
                grants = [condition.text for condition in table[phrase]]
                if any(g in implied for g in grants):
                    continue
                if (
                    not gate.requires
                    or all("." in g for g in grants)
                    or _documents_owner(gate, grants)
                ):
                    routes.append(f"{gate.package}/{relative}: lore {phrase} needs {' or '.join(grants)}")
                else:
                    problems.append(
                        f"{gate.package}/{relative}: lore {phrase} needs {' or '.join(grants)}, "
                        "which its gate does not imply"
                    )
    return problems, routes


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--routes", action="store_true", help="also list route-level mentions")
    args = parser.parse_args(argv)
    problems, routes = check()
    for line in problems:
        print(line)
    if args.routes:
        for line in routes:
            print(f"route: {line}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
