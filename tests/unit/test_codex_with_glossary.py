"""Unit tests for `lore.codex.read_documents_with_glossary` — G11 Red.

Plan: transient-public-api-facade-plan §G11.
Spec source: transient-public-api-facade-tech-spec §2 (Codex composition).

`read_documents_with_glossary` absorbs the orchestration currently done
inline in `cli.codex_show` via `_collect_codex_glossary`. The op fn
returns a composed envelope of RAW items (NOT pre-rendered markdown).

Contract (Tech Spec §2 + Plan G11 acceptance):

    read_documents_with_glossary(
        project_root: Path,
        doc_ids: list[str],
        *,
        skip_glossary: bool = False,
    ) -> {"documents": [...], "glossary": [...]}

  - EXACT key set: {"documents", "glossary"} — no `error`, no `warning`,
    no `ok`.
  - documents = list of raw doc records (id/title/summary/body shape from
    `read_document`). Order preserved.
  - glossary = list of raw glossary item dicts/objects — NEVER a
    pre-rendered `## Glossary` markdown string (Review-Ledger FLAG #6).
  - skip_glossary=True short-circuits the glossary lookup: returns
    `glossary == []` and does NOT read the glossary file.
  - Missing doc id "fails soft" — flows into the envelope rather than
    raising. (Plan §G11 acceptance: "missing doc id flows into envelope").

Every test in this module MUST fail until G11 Green lands.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixtures — minimal codex + glossary on disk
# ---------------------------------------------------------------------------


GLOSSARY_FIXTURE = """\
items:
  - keyword: Mission
    definition: The unit of work an agent executes and closes.
  - keyword: Quest
    definition: A live grouping of Missions representing one body of work.
"""


def _write_doc(codex_dir: Path, doc_id: str, body: str) -> None:
    """Write a minimal valid codex doc."""
    content = (
        "---\n"
        f"id: {doc_id}\n"
        f"title: {doc_id.replace('-', ' ').title()}\n"
        f"summary: Summary for {doc_id}.\n"
        "---\n"
        "\n"
        f"{body}"
    )
    (codex_dir / f"{doc_id}.md").write_text(content, encoding="utf-8")


def _seed(project_root: Path) -> None:
    """Seed a project_root with codex docs + a glossary file."""
    codex_dir = project_root / ".lore" / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    (codex_dir / "glossary.yaml").write_text(GLOSSARY_FIXTURE, encoding="utf-8")
    _write_doc(
        codex_dir,
        "conceptual-entities-mission",
        "A Mission is the unit of work. A Mission belongs to a Quest.\n",
    )
    _write_doc(
        codex_dir,
        "conceptual-entities-other",
        "Some other doc with no glossary terms.\n",
    )


# ---------------------------------------------------------------------------
# Import surface — function exists on lore.codex
# ---------------------------------------------------------------------------


class TestReadDocumentsWithGlossaryImport:
    """`read_documents_with_glossary` must live on `lore.codex` post-G11."""

    def test_function_is_importable_from_lore_codex(self):
        from lore.codex import read_documents_with_glossary  # noqa: F401

    def test_function_is_callable(self):
        from lore.codex import read_documents_with_glossary

        assert callable(read_documents_with_glossary)


# ---------------------------------------------------------------------------
# Envelope shape — EXACT key set {documents, glossary}
# ---------------------------------------------------------------------------


class TestReadDocumentsWithGlossaryEnvelope:
    """Envelope keys are EXACTLY `documents` + `glossary` — nothing else."""

    def test_envelope_is_dict(self, tmp_path: Path):
        from lore.codex import read_documents_with_glossary

        _seed(tmp_path)
        result = read_documents_with_glossary(
            tmp_path, ["conceptual-entities-mission"]
        )
        assert isinstance(result, dict)

    def test_envelope_key_set_is_exactly_documents_and_glossary(
        self, tmp_path: Path
    ):
        from lore.codex import read_documents_with_glossary

        _seed(tmp_path)
        result = read_documents_with_glossary(
            tmp_path, ["conceptual-entities-mission"]
        )
        assert set(result.keys()) == {"documents", "glossary"}

    def test_envelope_has_no_error_key(self, tmp_path: Path):
        from lore.codex import read_documents_with_glossary

        _seed(tmp_path)
        result = read_documents_with_glossary(
            tmp_path, ["conceptual-entities-mission"]
        )
        assert "error" not in result

    def test_envelope_has_no_ok_key(self, tmp_path: Path):
        from lore.codex import read_documents_with_glossary

        _seed(tmp_path)
        result = read_documents_with_glossary(
            tmp_path, ["conceptual-entities-mission"]
        )
        assert "ok" not in result

    def test_envelope_has_no_warning_key(self, tmp_path: Path):
        from lore.codex import read_documents_with_glossary

        _seed(tmp_path)
        result = read_documents_with_glossary(
            tmp_path, ["conceptual-entities-mission"]
        )
        assert "warning" not in result

    def test_documents_is_a_list(self, tmp_path: Path):
        from lore.codex import read_documents_with_glossary

        _seed(tmp_path)
        result = read_documents_with_glossary(
            tmp_path, ["conceptual-entities-mission"]
        )
        assert isinstance(result["documents"], list)

    def test_glossary_is_a_list(self, tmp_path: Path):
        from lore.codex import read_documents_with_glossary

        _seed(tmp_path)
        result = read_documents_with_glossary(
            tmp_path, ["conceptual-entities-mission"]
        )
        assert isinstance(result["glossary"], list)


# ---------------------------------------------------------------------------
# Documents — raw read_document records, order preserved
# ---------------------------------------------------------------------------


class TestReadDocumentsWithGlossaryDocuments:
    """`documents` carries raw `read_document` records, not rendered text."""

    def test_documents_contains_one_record_per_id(self, tmp_path: Path):
        from lore.codex import read_documents_with_glossary

        _seed(tmp_path)
        result = read_documents_with_glossary(
            tmp_path,
            ["conceptual-entities-mission", "conceptual-entities-other"],
        )
        assert len(result["documents"]) == 2

    def test_documents_have_id_title_summary_body_keys(self, tmp_path: Path):
        """Each document record carries raw fields from read_document."""
        from lore.codex import read_documents_with_glossary

        _seed(tmp_path)
        result = read_documents_with_glossary(
            tmp_path, ["conceptual-entities-mission"]
        )
        doc = result["documents"][0]
        # Raw record — same shape as lore.codex.read_document return value.
        assert "id" in doc
        assert "title" in doc
        assert "summary" in doc
        assert "body" in doc

    def test_documents_preserve_input_order(self, tmp_path: Path):
        """Doc ids in result follow the order given by the caller."""
        from lore.codex import read_documents_with_glossary

        _seed(tmp_path)
        result = read_documents_with_glossary(
            tmp_path,
            ["conceptual-entities-other", "conceptual-entities-mission"],
        )
        ids = [d["id"] for d in result["documents"]]
        assert ids == [
            "conceptual-entities-other",
            "conceptual-entities-mission",
        ]

    def test_documents_carry_raw_body_not_rendered_markdown(
        self, tmp_path: Path
    ):
        """Body is raw markdown source — never the `=== id ===` CLI envelope."""
        from lore.codex import read_documents_with_glossary

        _seed(tmp_path)
        result = read_documents_with_glossary(
            tmp_path, ["conceptual-entities-mission"]
        )
        body = result["documents"][0]["body"]
        # The CLI prepends `=== <id> ===` — the op fn must NOT.
        assert not body.startswith("=== ")


# ---------------------------------------------------------------------------
# Glossary — raw items, never pre-rendered markdown (FLAG #6)
# ---------------------------------------------------------------------------


class TestReadDocumentsWithGlossaryGlossaryRaw:
    """`glossary` list carries raw items, never `## Glossary` markdown text."""

    def test_glossary_is_not_a_string(self, tmp_path: Path):
        """FLAG #6: glossary value MUST be a list, NEVER a rendered string."""
        from lore.codex import read_documents_with_glossary

        _seed(tmp_path)
        result = read_documents_with_glossary(
            tmp_path, ["conceptual-entities-mission"]
        )
        assert not isinstance(result["glossary"], str)

    def test_glossary_items_are_not_rendered_markdown_strings(
        self, tmp_path: Path
    ):
        """Each glossary entry must be a structured item, not a `**X** — Y` line."""
        from lore.codex import read_documents_with_glossary

        _seed(tmp_path)
        result = read_documents_with_glossary(
            tmp_path, ["conceptual-entities-mission"]
        )
        # Each entry must NOT be a string (no pre-rendered markdown).
        for entry in result["glossary"]:
            assert not isinstance(entry, str)

    def test_glossary_items_expose_keyword_and_definition(
        self, tmp_path: Path
    ):
        """Each glossary entry exposes keyword + definition (raw fields).

        Whether entry is a GlossaryItem dataclass or a dict is left open;
        what matters is the consumer can read `keyword` + `definition`
        without parsing rendered markdown.
        """
        from lore.codex import read_documents_with_glossary

        _seed(tmp_path)
        result = read_documents_with_glossary(
            tmp_path, ["conceptual-entities-mission"]
        )
        assert len(result["glossary"]) >= 1
        for entry in result["glossary"]:
            # Accept either dataclass attr or dict key form.
            keyword = (
                getattr(entry, "keyword", None)
                if not isinstance(entry, dict)
                else entry.get("keyword")
            )
            definition = (
                getattr(entry, "definition", None)
                if not isinstance(entry, dict)
                else entry.get("definition")
            )
            assert keyword is not None
            assert definition is not None

    def test_glossary_does_not_contain_glossary_block_header(
        self, tmp_path: Path
    ):
        """Sanity: no `## Glossary` markdown header anywhere in the value."""
        from lore.codex import read_documents_with_glossary

        _seed(tmp_path)
        result = read_documents_with_glossary(
            tmp_path, ["conceptual-entities-mission"]
        )
        # Walk all string fields of every entry — none should be the
        # rendered block header.
        for entry in result["glossary"]:
            if isinstance(entry, dict):
                for v in entry.values():
                    if isinstance(v, str):
                        assert "## Glossary" not in v


# ---------------------------------------------------------------------------
# skip_glossary=True — short-circuit
# ---------------------------------------------------------------------------


class TestReadDocumentsWithGlossarySkipGlossary:
    """`skip_glossary=True` returns empty glossary and does NOT read the file."""

    def test_skip_glossary_true_returns_empty_glossary(self, tmp_path: Path):
        from lore.codex import read_documents_with_glossary

        _seed(tmp_path)
        result = read_documents_with_glossary(
            tmp_path,
            ["conceptual-entities-mission"],
            skip_glossary=True,
        )
        assert result["glossary"] == []

    def test_skip_glossary_true_still_returns_documents(self, tmp_path: Path):
        """Documents are not affected by `skip_glossary`."""
        from lore.codex import read_documents_with_glossary

        _seed(tmp_path)
        result = read_documents_with_glossary(
            tmp_path,
            ["conceptual-entities-mission"],
            skip_glossary=True,
        )
        assert len(result["documents"]) == 1
        assert result["documents"][0]["id"] == "conceptual-entities-mission"

    def test_skip_glossary_true_preserves_exact_envelope_keys(
        self, tmp_path: Path
    ):
        """Envelope shape is unchanged when `skip_glossary=True`."""
        from lore.codex import read_documents_with_glossary

        _seed(tmp_path)
        result = read_documents_with_glossary(
            tmp_path,
            ["conceptual-entities-mission"],
            skip_glossary=True,
        )
        assert set(result.keys()) == {"documents", "glossary"}

    def test_skip_glossary_true_does_not_read_glossary_file(
        self, tmp_path: Path, monkeypatch
    ):
        """`skip_glossary=True` short-circuits — glossary scan never runs.

        Boobytrap `match_glossary` to raise; skip_glossary must dodge it.
        """
        from lore import glossary as _glossary
        from lore.codex import read_documents_with_glossary

        _seed(tmp_path)

        def _boom(*args, **kwargs):
            raise AssertionError(
                "match_glossary called despite skip_glossary=True"
            )

        monkeypatch.setattr(_glossary, "match_glossary", _boom)

        result = read_documents_with_glossary(
            tmp_path,
            ["conceptual-entities-mission"],
            skip_glossary=True,
        )
        assert result["glossary"] == []

    def test_skip_glossary_default_is_false(self, tmp_path: Path):
        """Default `skip_glossary=False`: glossary IS scanned + populated."""
        from lore.codex import read_documents_with_glossary

        _seed(tmp_path)
        result = read_documents_with_glossary(
            tmp_path, ["conceptual-entities-mission"]
        )
        # Mission body mentions both 'Mission' and 'Quest'.
        assert len(result["glossary"]) >= 1


# ---------------------------------------------------------------------------
# Missing doc id — fail-soft into envelope (Plan G11 acceptance)
# ---------------------------------------------------------------------------


class TestReadDocumentsWithGlossaryMissingDoc:
    """A missing doc id flows into the envelope without raising."""

    def test_missing_doc_does_not_raise(self, tmp_path: Path):
        """Missing doc id must NOT propagate as an exception."""
        from lore.codex import read_documents_with_glossary

        _seed(tmp_path)
        # No raise: result must be returned even for an unknown id.
        try:
            result = read_documents_with_glossary(tmp_path, ["does-not-exist"])
        except Exception as exc:  # pragma: no cover — failure path is the assert
            pytest.fail(
                f"Missing doc id must fail soft, but raised: {type(exc).__name__}: {exc}"
            )
        assert isinstance(result, dict)

    def test_missing_doc_envelope_keys_unchanged(self, tmp_path: Path):
        """Envelope keys stay exactly {documents, glossary} on a missing id."""
        from lore.codex import read_documents_with_glossary

        _seed(tmp_path)
        result = read_documents_with_glossary(tmp_path, ["does-not-exist"])
        assert set(result.keys()) == {"documents", "glossary"}

    def test_mixed_missing_and_present_documents_list(self, tmp_path: Path):
        """A mix of present + missing ids — present resolve, missing flow soft.

        The present id appears in `documents`. The missing id either
        appears as a record carrying an `error`/`not_found`-style marker
        OR is omitted — both are acceptable fail-soft strategies per the
        plan ("flows into envelope"). What is NOT acceptable: raising,
        or returning the bare `documents` list without the present id.
        """
        from lore.codex import read_documents_with_glossary

        _seed(tmp_path)
        result = read_documents_with_glossary(
            tmp_path,
            ["conceptual-entities-mission", "does-not-exist"],
        )
        ids_present = [
            d.get("id")
            for d in result["documents"]
            if isinstance(d, dict) and d.get("id")
        ]
        assert "conceptual-entities-mission" in ids_present
