"""E2E tests for the rite command-group concept paragraph in --help.

Spec: conceptual-workflows-help (lore codex show conceptual-workflows-help)

A NEW command group MUST carry a concept paragraph (ADR-008). The
`@main.group("rite")` docstring is the verbatim concept paragraph from the
Rites Tech Spec §`lore rite --help`: it defines a rite as procedural memory,
draws the codex-vs-rite distinction, describes the node-graph/`use:` model,
states the AI-as-matcher retrieval rule, lists the command surface, and notes
that rites link to nothing (a codex doc points at rites via its `rites:`
frontmatter field).

Per Click 8.3, stdout/stderr are read separately (no mix_stderr).
"""

from __future__ import annotations

from lore.cli import main


REQUIRED_CONCEPT_PHRASES = (
    "procedural memory",
    "how to do or diagnose recurring task X",
    "codex stores semantic",
    "node-graph",
    "use:",
    "Lore never matches a situation for you",
    "link to nothing",
    "rites: frontmatter field",
)


class TestRiteGroupHelpConcept:
    """`lore rite --help` carries the ADR-008 concept paragraph, exit 0."""

    def test_rite_group_help_contains_concept_phrases(self, runner):
        result = runner.invoke(main, ["rite", "--help"])
        assert result.exit_code == 0
        for phrase in REQUIRED_CONCEPT_PHRASES:
            assert phrase in result.stdout, (
                f"rite --help missing required concept phrase: {phrase!r}"
            )
