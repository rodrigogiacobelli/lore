"""E2E tests for the `binds:` schema cluster (US-001 + US-002).

Red — schema-validation-us-001 + schema-validation-us-002 of the
`lore impacts` feature.
Workflow: conceptual-workflows-impacts (lore codex show conceptual-workflows-impacts)

Drives the user-facing surface for `binds:` validation via
``lore health --scope schemas``. The codex schema patch is implied by:

- US-001 acceptance scenarios: well-formed `binds:` does not trip the
  schema walker (exit 0; the offending id/`binds` never named).
- US-002 rejection scenarios: malformed `binds:` raises a non-zero
  exit and the failing entry id appears in the output.

US-001 Scenario 5 (``lore impacts <path>`` parity for missing vs
empty `binds:`) is anchored here but executed by the downstream
impacts-CLI cluster; not tested in this Red batch.

Every test MUST fail before the schema patch lands. Without the patch,
`additionalProperties: false` on the codex schema rejects every entry
that has any `binds:` key, so the acceptance tests fail (non-zero exit
with the seeded `example` id appearing in output). The rejection tests
fail because the schema does not yet enforce the specific rules
(minLength, uniqueItems, pattern) — although a few may flip green
purely from `additionalProperties: false` rejecting `binds:` outright;
those tests are nevertheless required and are the same pattern Green
will keep green once the schema is patched correctly.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from lore.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_codex_entry(
    project_dir: Path,
    *,
    entry_id: str,
    binds: list | None = None,
    omit_binds: bool = False,
) -> Path:
    """Write a codex entry to ``.lore/codex/<entry_id>.md``.

    If ``omit_binds`` is True, the `binds:` key is not emitted at all.
    Otherwise, ``binds`` (which may be an empty list or contain
    non-string items) is serialized via PyYAML.
    """
    fm: dict = {
        "id": entry_id,
        "title": entry_id.title(),
        "summary": f"Codex entry {entry_id}.",
    }
    if not omit_binds:
        fm["binds"] = binds if binds is not None else []
    # default_flow_style=False keeps a block-style mapping that mirrors
    # what a human author would write.
    front = yaml.safe_dump(fm, sort_keys=False, default_flow_style=False)
    path = project_dir / ".lore" / "codex" / f"{entry_id}.md"
    _write(path, f"---\n{front}---\nBody for {entry_id}.\n")
    return path


def _combined_output(result) -> str:
    """Concatenate stdout and stderr for content assertions."""
    out = result.stdout if result.stdout is not None else ""
    # Click's CliRunner returns empty stderr when mix_stderr=True; the
    # existing health tests assert on result.output. We use both to be
    # robust to either configuration.
    err = ""
    try:
        err = result.stderr or ""
    except (AttributeError, ValueError):
        err = ""
    return out + err


# ===========================================================================
# US-001 — well-formed `binds:` passes `lore health --scope schemas`
# ===========================================================================


class TestHealthAcceptsBinds:
    """US-001 E2E scenarios — exit 0; offending id/`binds` never mentioned."""

    def test_literal_path_bindings_pass_schema(self, runner, project_dir):
        """Scenario 1: literal path bindings pass schema.

        conceptual-workflows-impacts — Preconditions: `binds:` must
        validate before lookups work.
        """
        _write_codex_entry(
            project_dir,
            entry_id="example",
            binds=["src/lore/cli.py", "src/lore/impacts.py"],
        )
        result = runner.invoke(main, ["health", "--scope", "schemas"])
        assert result.exit_code == 0, result.output
        assert "example" not in result.output

    def test_glob_bindings_pass_schema(self, runner, project_dir):
        """Scenario 2: glob bindings pass schema.

        conceptual-workflows-impacts — Token Classification + Step 3
        "match every binding".
        """
        _write_codex_entry(
            project_dir,
            entry_id="example",
            binds=[
                "src/lore/**/*.py",
                "tests/unit/test_*.py",
                "src/lore/?.py",
            ],
        )
        result = runner.invoke(main, ["health", "--scope", "schemas"])
        assert result.exit_code == 0, result.output
        assert "example" not in result.output

    def test_empty_binds_list_accepted(self, runner, project_dir):
        """Scenario 4: `binds: []` is accepted.

        conceptual-workflows-impacts — FR-4 "missing == empty list".
        """
        _write_codex_entry(project_dir, entry_id="example", binds=[])
        result = runner.invoke(main, ["health", "--scope", "schemas"])
        assert result.exit_code == 0, result.output
        assert "example" not in result.output


# ===========================================================================
# US-002 — malformed `binds:` rejected by `lore health --scope schemas`
# ===========================================================================


class TestHealthRejectsBinds:
    """US-002 E2E scenarios — non-zero exit; offending id named."""

    def test_non_string_entry_rejected(self, runner, project_dir):
        """Scenario 1: `binds: [123]` (non-string) rejected.

        conceptual-workflows-impacts — Failure Modes: malformed `binds:`
        on disk surfaced by `lore health`. Green emits a `type`-rule
        violation under `/binds/...`, not the `additionalProperties`
        blanket rejection of `binds:` itself.
        """
        _write_codex_entry(project_dir, entry_id="bad", binds=[123])
        result = runner.invoke(main, ["health", "--scope", "schemas"])
        assert result.exit_code != 0, result.output
        combined = _combined_output(result)
        assert "bad" in combined
        assert "rule: type" in combined, (
            f"expected items.type violation, output was:\n{combined}"
        )

    def test_absolute_path_entry_rejected(self, runner, project_dir):
        """Scenario 2: `binds: ['/etc/passwd']` rejected.

        conceptual-workflows-impacts — Step 1 path normalisation:
        absolute / outside-repo banned. Green fires `not` (or `pattern`)
        on the leading-`/` rule.
        """
        _write_codex_entry(project_dir, entry_id="bad", binds=["/etc/passwd"])
        result = runner.invoke(main, ["health", "--scope", "schemas"])
        assert result.exit_code != 0, result.output
        combined = _combined_output(result)
        assert "bad" in combined
        assert "rule: not" in combined or "rule: pattern" in combined, (
            f"expected not/pattern violation, output was:\n{combined}"
        )

    def test_leading_dotdot_traversal_rejected(self, runner, project_dir):
        """Scenario 3: `binds: ['../up/foo.py']` rejected.

        conceptual-workflows-impacts — Failure Modes: "Path traversal
        not allowed".
        """
        _write_codex_entry(project_dir, entry_id="bad", binds=["../up/foo.py"])
        result = runner.invoke(main, ["health", "--scope", "schemas"])
        assert result.exit_code != 0, result.output
        combined = _combined_output(result)
        assert "bad" in combined
        assert "rule: not" in combined or "rule: pattern" in combined, (
            f"expected not/pattern violation, output was:\n{combined}"
        )

    def test_embedded_dotdot_segment_rejected(self, runner, project_dir):
        """Scenario 4: `binds: ['src/../etc/passwd']` rejected.

        conceptual-workflows-impacts — Failure Modes: any `..` segment
        banned, not only leading `..`.
        """
        _write_codex_entry(
            project_dir, entry_id="bad", binds=["src/../etc/passwd"]
        )
        result = runner.invoke(main, ["health", "--scope", "schemas"])
        assert result.exit_code != 0, result.output
        combined = _combined_output(result)
        assert "bad" in combined
        assert "rule: not" in combined or "rule: pattern" in combined, (
            f"expected not/pattern violation, output was:\n{combined}"
        )

    def test_empty_string_entry_rejected(self, runner, project_dir):
        """Scenario 5: `binds: ['']` rejected.

        conceptual-workflows-impacts — Preconditions: `minLength: 1`.
        The failure cites the `minLength` rule, not the blanket
        `additionalProperties` rejection that fires today.
        """
        _write_codex_entry(project_dir, entry_id="bad", binds=[""])
        result = runner.invoke(main, ["health", "--scope", "schemas"])
        assert result.exit_code != 0, result.output
        combined = _combined_output(result)
        assert "bad" in combined
        assert "rule: minLength" in combined, (
            f"expected minLength violation, output was:\n{combined}"
        )

    def test_duplicate_entries_rejected(self, runner, project_dir):
        """Scenario 6: `binds: ['src/lore/cli.py', 'src/lore/cli.py']` rejected.

        conceptual-workflows-impacts — Preconditions: `uniqueItems`.
        """
        _write_codex_entry(
            project_dir,
            entry_id="bad",
            binds=["src/lore/cli.py", "src/lore/cli.py"],
        )
        result = runner.invoke(main, ["health", "--scope", "schemas"])
        assert result.exit_code != 0, result.output
        combined = _combined_output(result)
        assert "bad" in combined
        assert "rule: uniqueItems" in combined, (
            f"expected uniqueItems violation, output was:\n{combined}"
        )


# ===========================================================================
# Cross-story sanity — clean codex + clean default fixtures stay clean
# ===========================================================================


class TestHealthBindsAdditiveContract:
    """Sanity guard — adding `binds:` doesn't disturb other codex entries."""

    def test_clean_project_with_binds_entry_passes_full_health(
        self, runner, project_dir
    ):
        """Adding a well-formed `binds:` entry leaves `lore health` exit 0.

        The default-init project ships with codex seeds — none of those
        seeds should regress when `binds:` becomes a recognized field.
        The bound path is materialised on disk so the US-001 bindings
        checker stays silent (a missing file would correctly fire
        dead_binding — covered by US-002 tests, not this additive guard).
        """
        (project_dir / "src" / "lore").mkdir(parents=True, exist_ok=True)
        (project_dir / "src" / "lore" / "cli.py").write_text("# real file\n")
        _write_codex_entry(
            project_dir,
            entry_id="example",
            binds=["src/lore/cli.py"],
        )
        result = runner.invoke(main, ["health"])
        assert result.exit_code == 0, result.output
