#!/usr/bin/env python3
"""Lint the shipped instruction blocks — a release pre-flight and a CI step.

Checks the tagged blocks under ``src/lore/defaults/blocks/`` and the skill
catalogue against rules L1 to L10 (``lore.blocklint``): every block parses and
sits where its feature says; every command a block uses is declared, has a row
in ``commands.yaml`` and is implied by the block's own tags; no instruction
document or skill file can render over its line cap; every mention of a skill is
closed over all profiles. Nothing reads prose.

Run it from the repository root::

    python scripts/check_blocks.py

Prints one ``CODE where: detail`` line per problem and exits 1 when there is any.
"""

from __future__ import annotations

import sys

from lore.blocklint import lint


def main() -> int:
    problems = lint()
    for problem in problems:
        print(f"{problem.code} {problem.where}: {problem.detail}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
