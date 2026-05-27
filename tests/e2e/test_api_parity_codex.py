"""E2E parity tests for `lore codex show` + `lore codex map` — G11 Red.

Plan: transient-public-api-facade-plan §G11.
Anchor: decisions-011-api-parity-with-cli — when the CLI's
`_collect_codex_glossary` orchestration moves INTO
`lore.codex.read_documents_with_glossary`, and the conflict-flag check
moves INTO `lore.codex.map_documents` raising
`ConflictingDepthFlags`, the user-visible CLI surface (exit code,
stdout, stderr, JSON envelope) MUST remain byte-identical.

These tests pin the parity contract for the refactor that lands in G11
Green:

  - `lore codex show <id>` text + JSON output byte-identical pre/post.
  - `lore codex map <id>` exit + stderr unchanged for the conflict path.
  - The op fn `read_documents_with_glossary` returns the SAME JSON
    envelope that `lore --json codex show <id>` already emits today
    (Tech Spec §2 + envelope rule: "every dict CLI emits today IS the
    contract — facade returns dict verbatim").

Red phase — every test MUST fail until G11 Green lands (whether by op-fn
absence or CLI envelope drift).
"""

from __future__ import annotations

import json
from pathlib import Path

from lore.cli import main


# ---------------------------------------------------------------------------
# Fixture seed — codex doc + glossary YAML
# ---------------------------------------------------------------------------


GLOSSARY_FIXTURE = """\
items:
  - keyword: Mission
    definition: The unit of work an agent executes and closes.
  - keyword: Quest
    definition: A live grouping of Missions representing one body of work.
"""


MISSION_DOC_BODY = (
    "A Mission is the unit of work an agent executes and closes.\n"
    "A Mission may belong to a Quest.\n"
)


MISSION_DOC = (
    "---\n"
    "id: conceptual-entities-mission\n"
    "title: Mission\n"
    "summary: Mission entity doc.\n"
    "---\n"
    "\n"
    + MISSION_DOC_BODY
)


def _seed(project_dir: Path) -> None:
    codex_dir = project_dir / ".lore" / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    (codex_dir / "glossary.yaml").write_text(GLOSSARY_FIXTURE, encoding="utf-8")
    (codex_dir / "conceptual-entities-mission.md").write_text(
        MISSION_DOC, encoding="utf-8"
    )


def _seed_chain(project_dir: Path) -> None:
    """Two-node codex chain for `codex map` tests."""
    codex_dir = project_dir / ".lore" / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    (codex_dir / "seed.md").write_text(
        "---\n"
        "id: seed\n"
        "title: Seed\n"
        "summary: Seed doc.\n"
        "related:\n"
        "  - child\n"
        "---\n"
        "\n"
        "Body of seed.\n",
        encoding="utf-8",
    )
    (codex_dir / "child.md").write_text(
        "---\n"
        "id: child\n"
        "title: Child\n"
        "summary: Child doc.\n"
        "related: []\n"
        "---\n"
        "\n"
        "Body of child.\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# `lore codex show` — JSON parity to op fn (envelope verbatim)
# ---------------------------------------------------------------------------


class TestCodexShowParityToOpFn:
    """`lore --json codex show <id>` envelope == `read_documents_with_glossary` return.

    Envelope rule (Plan top): "every dict CLI emits today IS the
    contract — facade returns dict verbatim."
    """

    def test_codex_show_json_matches_op_fn_envelope(self, runner, project_dir):
        """CLI JSON for `codex show` equals the op fn return dict exactly."""
        from lore.codex import read_documents_with_glossary

        _seed(project_dir)
        result = runner.invoke(
            main, ["--json", "codex", "show", "conceptual-entities-mission"]
        )
        assert result.exit_code == 0, result.output
        cli_payload = json.loads(result.stdout)

        op_payload = read_documents_with_glossary(
            project_dir, ["conceptual-entities-mission"]
        )

        # CLI emits raw glossary items via `_glossary_entry_dict` — the
        # op fn return must JSON-serialise to the exact same dict.
        assert json.loads(json.dumps(op_payload, default=_default)) == cli_payload

    def test_codex_show_skip_glossary_json_parity(self, runner, project_dir):
        """`--skip-glossary` CLI path matches `skip_glossary=True` op call."""
        from lore.codex import read_documents_with_glossary

        _seed(project_dir)
        result = runner.invoke(
            main,
            [
                "--json",
                "codex",
                "show",
                "--skip-glossary",
                "conceptual-entities-mission",
            ],
        )
        assert result.exit_code == 0, result.output
        cli_payload = json.loads(result.stdout)
        op_payload = read_documents_with_glossary(
            project_dir,
            ["conceptual-entities-mission"],
            skip_glossary=True,
        )
        assert json.loads(json.dumps(op_payload, default=_default)) == cli_payload
        assert cli_payload["glossary"] == []


def _default(obj):
    """Convert dataclass-style GlossaryItem to dict for json comparison."""
    if hasattr(obj, "__dict__"):
        return {
            k: v
            for k, v in obj.__dict__.items()
            if not k.startswith("_")
        }
    raise TypeError(repr(obj))


# ---------------------------------------------------------------------------
# `lore codex show` — text mode + exit code unchanged
# ---------------------------------------------------------------------------


class TestCodexShowTextParity:
    """Text-mode output for `lore codex show` byte-identical pre/post G11."""

    def test_show_text_mode_exit_zero(self, runner, project_dir):
        _seed(project_dir)
        result = runner.invoke(
            main, ["codex", "show", "conceptual-entities-mission"]
        )
        assert result.exit_code == 0

    def test_show_text_mode_includes_doc_body(self, runner, project_dir):
        _seed(project_dir)
        result = runner.invoke(
            main, ["codex", "show", "conceptual-entities-mission"]
        )
        assert "A Mission is the unit of work" in result.stdout

    def test_show_text_mode_renders_glossary_block(self, runner, project_dir):
        """Text mode rendered glossary block stays (renderer lives CLI-side)."""
        _seed(project_dir)
        result = runner.invoke(
            main, ["codex", "show", "conceptual-entities-mission"]
        )
        assert "## Glossary" in result.stdout
        assert "**Mission** —" in result.stdout
        assert "**Quest** —" in result.stdout

    def test_show_text_mode_skip_glossary_suppresses_block(
        self, runner, project_dir
    ):
        """`--skip-glossary` suppresses the rendered block in text mode."""
        _seed(project_dir)
        result = runner.invoke(
            main,
            [
                "codex",
                "show",
                "--skip-glossary",
                "conceptual-entities-mission",
            ],
        )
        assert result.exit_code == 0
        assert "## Glossary" not in result.stdout

    def test_show_missing_doc_exit_one(self, runner, project_dir):
        """Missing doc id surfaces a 'not found' message + exit 1."""
        _seed(project_dir)
        result = runner.invoke(main, ["codex", "show", "does-not-exist"])
        assert result.exit_code == 1
        combined = (result.stdout or "") + (
            result.stderr if hasattr(result, "stderr") else ""
        )
        assert "not found" in combined.lower()


# ---------------------------------------------------------------------------
# `lore codex map` — conflict gate exit + stderr unchanged
# ---------------------------------------------------------------------------


class TestCodexMapConflictParity:
    """`lore codex map` conflict-flag exit code + stderr unchanged.

    G11 moves the conflict check INTO `map_documents` (raises
    `ConflictingDepthFlags`). The CLI translates that exception
    into the SAME `UsageError` / JSON error envelope emitted today.
    """

    def test_codex_map_depth_plus_depth_in_exit_two_text(
        self, runner, project_dir
    ):
        """Text mode: `--depth` + `--depth-in` exits 2 (click.UsageError)."""
        _seed_chain(project_dir)
        result = runner.invoke(
            main,
            ["codex", "map", "seed", "--depth", "1", "--depth-in", "1"],
        )
        assert result.exit_code == 2

    def test_codex_map_depth_plus_depth_in_stderr_text(
        self, runner, project_dir
    ):
        """Text mode: stderr explains the conflict in unchanged wording."""
        _seed_chain(project_dir)
        result = runner.invoke(
            main,
            ["codex", "map", "seed", "--depth", "1", "--depth-in", "1"],
        )
        stderr = result.stderr if hasattr(result, "stderr") else ""
        combined = (result.stdout or "") + (stderr or "")
        assert "--depth" in combined
        assert "--depth-in" in combined or "--depth-out" in combined

    def test_codex_map_depth_plus_depth_out_exit_two_json(
        self, runner, project_dir
    ):
        """JSON mode: `--depth` + `--depth-out` exits 2 with `{error: ...}`."""
        _seed_chain(project_dir)
        result = runner.invoke(
            main,
            [
                "--json",
                "codex",
                "map",
                "seed",
                "--depth",
                "1",
                "--depth-out",
                "1",
            ],
        )
        assert result.exit_code == 2

    def test_codex_map_depth_plus_depth_out_json_error_envelope(
        self, runner, project_dir
    ):
        """JSON mode: stderr carries `{"error": "..."}` envelope verbatim."""
        _seed_chain(project_dir)
        result = runner.invoke(
            main,
            [
                "--json",
                "codex",
                "map",
                "seed",
                "--depth",
                "1",
                "--depth-out",
                "1",
            ],
        )
        stderr = result.stderr if hasattr(result, "stderr") else ""
        # JSON error printed to stderr (matches codex_map handler today).
        payload = json.loads(stderr.strip())
        assert "error" in payload


# ---------------------------------------------------------------------------
# `lore codex map` — non-conflict paths still work (regression guard)
# ---------------------------------------------------------------------------


class TestCodexMapHappyPathParity:
    """Single-flag and no-flag `codex map` invocations stay green."""

    def test_codex_map_default_no_flags_exit_zero(self, runner, project_dir):
        _seed_chain(project_dir)
        result = runner.invoke(main, ["codex", "map", "seed"])
        assert result.exit_code == 0

    def test_codex_map_depth_only_exit_zero(self, runner, project_dir):
        """`--depth` alone (no directional) exits 0 after G11 wiring."""
        _seed_chain(project_dir)
        result = runner.invoke(
            main, ["codex", "map", "seed", "--depth", "1"]
        )
        assert result.exit_code == 0

    def test_codex_map_depth_out_only_exit_zero(self, runner, project_dir):
        """`--depth-out` alone unchanged from today (FLAG #5)."""
        _seed_chain(project_dir)
        result = runner.invoke(
            main, ["codex", "map", "seed", "--depth-out", "1"]
        )
        assert result.exit_code == 0

    def test_codex_map_depth_in_only_exit_zero(self, runner, project_dir):
        """`--depth-in` alone unchanged from today (FLAG #5)."""
        _seed_chain(project_dir)
        result = runner.invoke(
            main, ["codex", "map", "child", "--depth-in", "1"]
        )
        assert result.exit_code == 0

    def test_codex_map_depth_one_json_returns_codex_list(
        self, runner, project_dir
    ):
        """`--depth 1` JSON envelope keeps the `{codex: [...]}` shape."""
        _seed_chain(project_dir)
        result = runner.invoke(
            main, ["--json", "codex", "map", "seed", "--depth", "1"]
        )
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert "codex" in payload
        ids = [d["id"] for d in payload["codex"]]
        assert "child" in ids
