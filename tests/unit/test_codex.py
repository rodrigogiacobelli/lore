"""Unit tests for codex.map_documents and codex._read_related.

Spec: codex-map-us-1 (lore codex show codex-map-us-1)
Tech arch: tech-arch-codex-map (lore codex show tech-arch-codex-map)
"""

import random
import textwrap
from pathlib import Path

import pytest

from lore.codex import _read_related
from lore.codex import chaos_documents
from lore.codex import list_codex


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_doc(
    codex_dir: Path,
    doc_id: str,
    *,
    related: list[str] | None = None,
    omit_related: bool = False,
) -> Path:
    """Write a minimal valid codex document into codex_dir and return the path."""
    lines = [
        "---",
        f"id: {doc_id}",
        f"title: {doc_id.replace('-', ' ').title()}",
        f"summary: Summary for {doc_id}.",
    ]
    if not omit_related:
        if related is None:
            lines.append("related: []")
        else:
            lines.append("related:")
            for r in related:
                lines.append(f"  - {r}")
    lines.extend(["---", "", f"Body of {doc_id}.", ""])
    content = "\n".join(lines)
    filepath = codex_dir / f"{doc_id}.md"
    filepath.write_text(content)
    return filepath


def _make_codex_dir(tmp_path: Path) -> Path:
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    return codex_dir


# ---------------------------------------------------------------------------
# map_documents tests live in tests/unit/test_codex_map.py — rewritten
# against the new signature `(codex_dir, start_id, *, depth_out=1,
# depth_in=1, full=False)`. The legacy positional `depth` tests previously
# at this location were removed per codex-map-tech-spec § Project Structure.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# _read_related — core contract
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 3 (_read_related core contract)
def test_read_related_returns_sorted_valid_ids(tmp_path):
    """_read_related returns sorted list of valid IDs present in the index."""
    codex_dir = _make_codex_dir(tmp_path)
    doc_path = _write_doc(codex_dir, "doc-a", related=["doc-c", "doc-b"])
    _write_doc(codex_dir, "doc-b")
    _write_doc(codex_dir, "doc-c")

    # Build a minimal index as map_documents would
    index = {
        "doc-a": {"id": "doc-a", "path": doc_path},
        "doc-b": {"id": "doc-b", "path": codex_dir / "doc-b.md"},
        "doc-c": {"id": "doc-c", "path": codex_dir / "doc-c.md"},
    }

    result = _read_related(doc_path, index)

    assert result == sorted(result)
    assert set(result) == {"doc-b", "doc-c"}


# ---------------------------------------------------------------------------
# _read_related — filters dead links
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 3 (dead link filter)
def test_read_related_filters_ids_not_in_index(tmp_path):
    """_read_related filters out IDs not present in the index."""
    codex_dir = _make_codex_dir(tmp_path)
    doc_path = _write_doc(codex_dir, "doc-a", related=["doc-b", "ghost-id"])
    _write_doc(codex_dir, "doc-b")

    index = {
        "doc-a": {"id": "doc-a", "path": doc_path},
        "doc-b": {"id": "doc-b", "path": codex_dir / "doc-b.md"},
    }

    result = _read_related(doc_path, index)

    assert "ghost-id" not in result
    assert "doc-b" in result


# ---------------------------------------------------------------------------
# _read_related — absent field
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 3 (absent field)
def test_read_related_returns_empty_for_absent_field(tmp_path):
    """_read_related returns [] when related field is absent from frontmatter."""
    codex_dir = _make_codex_dir(tmp_path)
    doc_path = _write_doc(codex_dir, "doc-a", omit_related=True)
    index = {"doc-a": {"id": "doc-a", "path": doc_path}}

    result = _read_related(doc_path, index)

    assert result == []


# ---------------------------------------------------------------------------
# _read_related — null field
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 3 (null field)
def test_read_related_returns_empty_for_null_related(tmp_path):
    """_read_related returns [] when related field is explicitly null."""
    codex_dir = _make_codex_dir(tmp_path)
    content = textwrap.dedent("""\
        ---
        id: doc-a
        title: Doc A
        summary: summary.
        related: null
        ---

        Body.
    """)
    doc_path = codex_dir / "doc-a.md"
    doc_path.write_text(content)
    index = {"doc-a": {"id": "doc-a", "path": doc_path}}

    result = _read_related(doc_path, index)

    assert result == []


# ---------------------------------------------------------------------------
# _read_related — empty list
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 3 (empty list)
def test_read_related_returns_empty_for_empty_list(tmp_path):
    """_read_related returns [] when related is an empty list."""
    codex_dir = _make_codex_dir(tmp_path)
    doc_path = _write_doc(codex_dir, "doc-a", related=[])
    index = {"doc-a": {"id": "doc-a", "path": doc_path}}

    result = _read_related(doc_path, index)

    assert result == []


# ---------------------------------------------------------------------------
# _read_related — defensive: null entries dropped
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 3 (defensive parsing — null entries dropped)
def test_read_related_drops_null_entries(tmp_path):
    """_read_related drops null entries in the related list."""
    codex_dir = _make_codex_dir(tmp_path)
    content = textwrap.dedent("""\
        ---
        id: doc-a
        title: Doc A
        summary: summary.
        related:
          - doc-b
          - null
          - doc-c
        ---

        Body.
    """)
    doc_path = codex_dir / "doc-a.md"
    doc_path.write_text(content)
    _write_doc(codex_dir, "doc-b")
    _write_doc(codex_dir, "doc-c")
    index = {
        "doc-a": {"id": "doc-a", "path": doc_path},
        "doc-b": {"id": "doc-b", "path": codex_dir / "doc-b.md"},
        "doc-c": {"id": "doc-c", "path": codex_dir / "doc-c.md"},
    }

    result = _read_related(doc_path, index)

    assert None not in result
    assert "doc-b" in result
    assert "doc-c" in result


# ---------------------------------------------------------------------------
# _read_related — defensive: non-string entries cast and trimmed
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map step 3 (defensive parsing — non-string cast and trimmed)
def test_read_related_casts_non_string_entries(tmp_path):
    """_read_related casts non-string entries (e.g. integers) to str and strips whitespace."""
    codex_dir = _make_codex_dir(tmp_path)
    # Write a doc whose related list has an integer entry that, when cast, matches an index key
    content = textwrap.dedent("""\
        ---
        id: doc-a
        title: Doc A
        summary: summary.
        related:
          - 42
        ---

        Body.
    """)
    doc_path = codex_dir / "doc-a.md"
    doc_path.write_text(content)
    _write_doc(codex_dir, "42")
    index = {
        "doc-a": {"id": "doc-a", "path": doc_path},
        "42": {"id": "42", "path": codex_dir / "42.md"},
    }

    result = _read_related(doc_path, index)

    # The integer 42 should be cast to "42" and matched in the index
    assert "42" in result


# ---------------------------------------------------------------------------
# US-2: map_documents depth-boundary tests live in test_codex_map.py against
# the new directional kwargs. The legacy `depth=N` boundary tests previously
# here were removed per codex-map-tech-spec.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# US-3: CLI command registration unit checks
# ---------------------------------------------------------------------------


# conceptual-workflows-codex-map (command registered as "map" under codex group)
def test_codex_map_command_registered_in_codex_group():
    """Inspect the codex Click group's commands dict.

    Assert "map" is a key in codex.commands.
    """
    from lore.cli import codex

    assert "map" in codex.commands


# conceptual-workflows-codex-map (doc_id is a required positional argument)
def test_codex_map_doc_id_is_required_argument():
    """The 'map' command must have a required positional param named 'doc_id'."""
    from lore.cli import codex_map
    import click

    param_names = [p.name for p in codex_map.params]
    assert "doc_id" in param_names

    doc_id_param = next(p for p in codex_map.params if p.name == "doc_id")
    assert isinstance(doc_id_param, click.Argument)
    assert doc_id_param.required


# The legacy `--depth defaults to 1` test was removed: after the refactor,
# `--depth` defaults to None (the handler resolves the effective budgets).
# Coverage for the new default — depth_out=1, depth_in=1 at the Python API
# level — lives in tests/unit/test_codex_map.py.


# ---------------------------------------------------------------------------
# US-001 / US-002 / US-003 / US-004: chaos_documents unit stubs
# ---------------------------------------------------------------------------


# Unit — seed is first element of returned list
# conceptual-workflows-codex-chaos step 4 (seed document always first entry in result per FR-4)
def test_chaos_documents_seed_is_first(tmp_path):
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed-doc", related=["neighbour-a", "neighbour-b"])
    _write_doc(codex_dir, "neighbour-a")
    _write_doc(codex_dir, "neighbour-b")

    result = chaos_documents(tmp_path, "seed-doc", threshold=100, rng=random.Random(42))

    assert result is not None
    assert result[0]["id"] == "seed-doc"


# Unit — returns None when start_id not in index
# conceptual-workflows-codex-chaos step 1 (validate seed: absent → return None)
def test_chaos_documents_unknown_seed_returns_none(tmp_path):
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "doc-a")
    _write_doc(codex_dir, "doc-b")

    result = chaos_documents(tmp_path, "missing", threshold=50)

    assert result is None


# Unit — leaf seed (no related links) returns list of length 1
# conceptual-workflows-codex-chaos step 3 (reachable set size == 1 → return immediately)
def test_chaos_documents_leaf_seed_returns_only_seed(tmp_path):
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "leaf-doc", omit_related=True)

    result = chaos_documents(tmp_path, "leaf-doc", threshold=40)

    assert result is not None
    assert len(result) == 1
    assert result[0]["id"] == "leaf-doc"


# Unit — does not write, create, or modify any file in codex directory
# conceptual-workflows-codex-chaos (chaos traversal is read-only per NFR)
def test_chaos_documents_does_not_modify_codex(tmp_path):
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed-doc", related=["doc-b", "doc-c"])
    _write_doc(codex_dir, "doc-b", related=["doc-d"])
    _write_doc(codex_dir, "doc-c")
    _write_doc(codex_dir, "doc-d", related=["doc-e"])
    _write_doc(codex_dir, "doc-e")

    files_before = {p: p.stat().st_mtime for p in codex_dir.rglob("*.md")}
    count_before = len(list(codex_dir.rglob("*.md")))

    chaos_documents(tmp_path, "seed-doc", threshold=50)

    files_after = {p: p.stat().st_mtime for p in codex_dir.rglob("*.md")}
    count_after = len(list(codex_dir.rglob("*.md")))

    assert count_after == count_before
    for path, mtime in files_before.items():
        assert files_after[path] == mtime


# Unit — threshold=100 returns full connected component
# conceptual-workflows-codex-chaos step 4 (walk exhausts reachable set when threshold=100)
def test_chaos_documents_threshold_100_returns_all_reachable(tmp_path):
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "doc-1", related=["doc-2", "doc-3"])
    _write_doc(codex_dir, "doc-2", related=["doc-4"])
    _write_doc(codex_dir, "doc-3", related=["doc-5"])
    _write_doc(codex_dir, "doc-4")
    _write_doc(codex_dir, "doc-5")

    result = chaos_documents(tmp_path, "doc-1", threshold=100, rng=random.Random(0))

    assert result is not None
    ids = [d["id"] for d in result]
    assert len(ids) == 5
    assert set(ids) == {"doc-1", "doc-2", "doc-3", "doc-4", "doc-5"}
    assert len(ids) == len(set(ids))


# Unit — no duplicate IDs in result (seeded RNG)
# conceptual-workflows-codex-chaos step 4 (visited set prevents revisiting nodes)
def test_chaos_documents_no_duplicate_ids(tmp_path):
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "seed-doc", related=["n1", "n2", "n3"])
    for i in range(1, 10):
        prev = f"n{i}"
        nxt = f"n{i + 1}" if i < 9 else None
        _write_doc(codex_dir, prev, related=[nxt] if nxt else [])
    _write_doc(codex_dir, "n9")

    result = chaos_documents(tmp_path, "seed-doc", threshold=50, rng=random.Random(42))

    assert result is not None
    ids = [d["id"] for d in result]
    assert len(ids) == len(set(ids))


# Unit — cyclic related graphs (A→B→A) do not produce duplicate entries
# conceptual-workflows-codex-chaos step 4 (visited set applied before appending to result)
def test_chaos_documents_cyclic_graph_no_duplicates(tmp_path):
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "doc-a", related=["doc-b"])
    _write_doc(codex_dir, "doc-b", related=["doc-a"])

    result = chaos_documents(tmp_path, "doc-a", threshold=100, rng=random.Random(0))

    assert result is not None
    ids = [d["id"] for d in result]
    assert len(ids) == 2
    assert len(ids) == len(set(ids))


# Unit — non-determinism: different seeds produce different result sets
# conceptual-workflows-codex-chaos step 4 (rng.choice picks different neighbours per seed)
def test_chaos_documents_different_rng_seeds_produce_different_results(tmp_path):
    codex_dir = _make_codex_dir(tmp_path)
    # Build a 10-node graph where seed-doc connects to n1..n9, each connected to the next
    _write_doc(codex_dir, "seed-doc", related=["n1", "n2", "n3", "n4", "n5"])
    _write_doc(codex_dir, "n1", related=["n6"])
    _write_doc(codex_dir, "n2", related=["n7"])
    _write_doc(codex_dir, "n3", related=["n8"])
    _write_doc(codex_dir, "n4", related=["n9"])
    _write_doc(codex_dir, "n5")
    _write_doc(codex_dir, "n6")
    _write_doc(codex_dir, "n7")
    _write_doc(codex_dir, "n8")
    _write_doc(codex_dir, "n9")

    result_a = chaos_documents(tmp_path, "seed-doc", threshold=50, rng=random.Random(1))
    result_b = chaos_documents(tmp_path, "seed-doc", threshold=50, rng=random.Random(2))

    assert result_a is not None
    assert result_b is not None
    # At least one of these result sets differs — they are non-deterministic across RNG seeds
    assert {d["id"] for d in result_a} != {d["id"] for d in result_b}


# Unit — bidirectional adjacency: inbound-only related link is traversable
# conceptual-workflows-codex-chaos step 2 (bidirectional adjacency pre-pass: A→B registers B as neighbour of A and A as neighbour of B)
def test_chaos_documents_bidirectional_adjacency(tmp_path):
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "doc-a", related=["doc-b"])
    _write_doc(codex_dir, "doc-b", omit_related=True)

    result = chaos_documents(tmp_path, "doc-b", threshold=100, rng=random.Random(0))

    assert result is not None
    ids = [d["id"] for d in result]
    assert "doc-a" in ids


# Unit — raises ValueError when threshold below 30
# conceptual-workflows-codex-chaos step 2 (validate_chaos_threshold called before index load)
def test_chaos_documents_raises_for_threshold_below_30(tmp_path):
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "any-doc")

    import pytest as _pytest
    with _pytest.raises(ValueError):
        chaos_documents(tmp_path, "any-doc", threshold=29)


# Unit — chaos_documents returns None when start_id absent from non-empty codex index
# conceptual-workflows-codex-chaos step 1 (validate seed: absent from index → return None)
def test_chaos_documents_returns_none_for_unknown_id(tmp_path):
    # Given: codex with "doc-a"; start_id = "missing"
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "doc-a")

    # When: chaos_documents(tmp_path, "missing", threshold=50)
    result = chaos_documents(tmp_path, "missing", threshold=50)

    # Then: result is None
    assert result is None, f"Expected None but got {result!r}"


# Unit — chaos_documents returns None even when codex is non-empty
# conceptual-workflows-codex-chaos step 1 (index lookup: only exact match returns non-None)
def test_chaos_documents_returns_none_even_with_non_empty_codex(tmp_path):
    # Given: codex with 5 connected docs none of which has id "ghost"
    codex_dir = _make_codex_dir(tmp_path)
    _write_doc(codex_dir, "doc-1", related=["doc-2"])
    _write_doc(codex_dir, "doc-2", related=["doc-3"])
    _write_doc(codex_dir, "doc-3", related=["doc-4"])
    _write_doc(codex_dir, "doc-4", related=["doc-5"])
    _write_doc(codex_dir, "doc-5")

    # When: chaos_documents(tmp_path, "ghost", threshold=40)
    result = chaos_documents(tmp_path, "ghost", threshold=40)

    # Then: result is None
    assert result is None, f"Expected None but got {result!r}"


# Unit — CLI handler writes correct error to stderr and exits 1 when chaos_documents returns None
# conceptual-workflows-codex-chaos Failure Modes (CLI handler translates None → stderr message + exit 1)
def test_chaos_cli_handler_stderr_on_none_result(runner, tmp_path):
    # Given: project at tmp_path with no "phantom-id" in codex
    # Uses global --json flag (ctx.obj["json"]=True) to test that JSON mode also exits 1
    # and emits JSON error envelope — this fails until the CLI handler checks ctx.obj["json"]
    import json
    import subprocess
    import sys

    lore_dir = tmp_path / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    codex_dir = lore_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    _write_doc(codex_dir, "other-doc")

    # Plain-text mode: exit 1, correct message on stderr, empty stdout
    proc_plain = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "phantom-id", "--threshold", "50"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert proc_plain.returncode == 1, f"Expected exit code 1 but got {proc_plain.returncode}"
    assert 'Document "phantom-id" not found' in proc_plain.stderr, (
        f"Expected error message in stderr but got: {proc_plain.stderr!r}"
    )
    assert proc_plain.stdout == "", f"Expected empty stdout but got: {proc_plain.stdout!r}"

    # JSON mode via global flag (ctx.obj["json"] = True): must emit JSON error envelope, not plain text
    # This assertion fails until codex_chaos checks ctx.obj.get("json", False)
    proc_json_global = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "--json", "codex", "chaos", "phantom-id", "--threshold", "50"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert proc_json_global.returncode == 1
    error_envelope = json.loads(proc_json_global.stderr)
    assert error_envelope == {"error": 'Document "phantom-id" not found'}, (
        f"Expected JSON envelope on stderr in --json mode; got plain text: {proc_json_global.stderr!r}"
    )


# Unit — CLI handler writes JSON error envelope to stderr in JSON mode when chaos_documents returns None
# conceptual-workflows-codex-chaos Failure Modes (JSON mode: {"error": ...} to stderr, exit 1)
def test_chaos_cli_handler_json_error_envelope_on_none_result(runner, tmp_path):
    # Given: project at tmp_path with no "ghost-id"; json mode active via --json flag on codex_chaos
    # --json placed at end of command per memory/feedback_json_flag_placement.md convention
    import json
    import subprocess
    import sys

    lore_dir = tmp_path / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    codex_dir = lore_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    _write_doc(codex_dir, "other-doc")

    proc = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "ghost-id", "--threshold", "50", "--json"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    # --json is not yet registered on codex_chaos; exit code will be 2 until implemented
    assert proc.returncode == 1, f"Expected exit code 1 but got {proc.returncode}"
    assert proc.stdout == "", f"Expected empty stdout but got: {proc.stdout!r}"
    error_envelope = json.loads(proc.stderr)
    assert error_envelope == {"error": 'Document "ghost-id" not found'}, (
        f"Unexpected JSON error envelope: {error_envelope!r}"
    )


# Unit — nothing written to stdout in either mode when chaos_documents returns None
# conceptual-workflows-codex-chaos Failure Modes (nothing on stdout on error)
def test_chaos_cli_handler_no_stdout_on_not_found(runner, tmp_path):
    # Given: project at tmp_path with no "gone-id"
    # Verifies that --json flag is accepted (exit 1, not 2) and stdout is empty in both modes
    import subprocess
    import sys

    lore_dir = tmp_path / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    codex_dir = lore_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    _write_doc(codex_dir, "other-doc")

    # When: invoked without --json flag
    proc_plain = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "gone-id", "--threshold", "50"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    # When: invoked with --json flag at end (should be accepted, not produce Click option error)
    proc_json = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "gone-id", "--threshold", "50", "--json"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    # Then: stdout is empty in both cases
    assert proc_plain.stdout == "", (
        f"Expected empty stdout in plain-text mode but got: {proc_plain.stdout!r}"
    )
    # --json must be recognised (exit 1, not 2) for this assertion to be meaningful
    assert proc_json.returncode == 1, (
        f"Expected exit 1 in JSON mode (--json not yet implemented on codex_chaos); "
        f"got {proc_json.returncode}"
    )
    assert proc_json.stdout == "", (
        f"Expected empty stdout in JSON mode but got: {proc_json.stdout!r}"
    )


# Unit — JSON mode: stdout is a parseable JSON string on success
# conceptual-workflows-codex-chaos step 5 (JSON render: output must be valid JSON)
def test_chaos_cli_json_stdout_is_parseable(runner, tmp_path):
    import json
    import subprocess
    import sys

    # Given: project at tmp_path with connected docs
    lore_dir = tmp_path / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    codex_dir = lore_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    _write_doc(codex_dir, "seed-j1", related=["seed-j2"])
    _write_doc(codex_dir, "seed-j2")

    # When: CLI invoked with --json flag at end
    proc = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "seed-j1", "--threshold", "50", "--json"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    # Then: exit 0, stdout parses as JSON (no exception)
    assert proc.returncode == 0, f"Expected exit 0; got {proc.returncode}. stderr={proc.stderr!r}"
    parsed = json.loads(proc.stdout)  # raises if not valid JSON
    assert parsed is not None


# Unit — JSON mode: parsed JSON has key "documents" whose value is a list
# conceptual-workflows-codex-chaos step 5 (JSON envelope shape: {"documents": [...]})
def test_chaos_cli_json_has_documents_key(runner, tmp_path):
    import json
    import subprocess
    import sys

    # Given: project at tmp_path with connected docs
    lore_dir = tmp_path / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    codex_dir = lore_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    _write_doc(codex_dir, "seed-j3", related=["seed-j4"])
    _write_doc(codex_dir, "seed-j4")

    # When: CLI invoked with --json flag at end
    proc = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "seed-j3", "--threshold", "50", "--json"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert proc.returncode == 0, f"Expected exit 0; got {proc.returncode}. stderr={proc.stderr!r}"
    data = json.loads(proc.stdout)
    # Then: parsed JSON has key "documents" whose value is a list
    assert "documents" in data, f"Expected 'documents' key; got {set(data.keys())}"
    assert isinstance(data["documents"], list), f"Expected list; got {type(data['documents'])}"


# Unit — JSON mode: each document dict has exactly the keys id, title, summary (no other keys)
# conceptual-workflows-codex-chaos step 5 (JSON output: metadata-only, document has exactly 3 keys)
def test_chaos_cli_json_document_fields_exact_keys(runner, tmp_path):
    import json
    import subprocess
    import sys

    # Given: project at tmp_path with connected docs
    lore_dir = tmp_path / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    codex_dir = lore_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    _write_doc(codex_dir, "seed-j5", related=["seed-j6"])
    _write_doc(codex_dir, "seed-j6")

    # When: CLI invoked with --json flag at end
    proc = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "seed-j5", "--threshold", "50", "--json"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert proc.returncode == 0, f"Expected exit 0; got {proc.returncode}. stderr={proc.stderr!r}"
    data = json.loads(proc.stdout)
    # Then: for each doc in result["documents"]: set(doc.keys()) == {"id", "title", "summary"}
    for doc in data["documents"]:
        assert set(doc.keys()) == {"id", "title", "summary"}, (
            f"Document has unexpected keys: {set(doc.keys())}"
        )


# Unit — JSON mode: no "body" key appears in any document dict
# conceptual-workflows-codex-chaos step 5 (JSON output: metadata-only, no body field per spec — body excluded)
def test_chaos_cli_json_document_fields_no_body(runner, tmp_path):
    import json
    import subprocess
    import sys

    # Given: project at tmp_path with connected docs
    lore_dir = tmp_path / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    codex_dir = lore_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    _write_doc(codex_dir, "seed-j7", related=["seed-j8"])
    _write_doc(codex_dir, "seed-j8")

    # When: CLI invoked with --json flag at end
    proc = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "seed-j7", "--threshold", "50", "--json"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert proc.returncode == 0, f"Expected exit 0; got {proc.returncode}. stderr={proc.stderr!r}"
    data = json.loads(proc.stdout)
    # Then: for each doc in result["documents"]: "body" not in doc
    for doc in data["documents"]:
        assert "body" not in doc, f"Unexpected 'body' key in document: {doc!r}"


# Unit — JSON mode: document id values match the IDs returned by chaos_documents
# conceptual-workflows-codex-chaos step 5 (JSON render maps chaos_documents result to envelope)
def test_chaos_cli_json_ids_match_chaos_documents_output(runner, tmp_path):
    import json
    import subprocess
    import sys

    # Given: project at tmp_path with connected docs
    lore_dir = tmp_path / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    codex_dir = lore_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    _write_doc(codex_dir, "seed-j9", related=["seed-j10", "seed-j11"])
    _write_doc(codex_dir, "seed-j10")
    _write_doc(codex_dir, "seed-j11")

    # When: CLI invoked with --json flag at end (threshold 100 to exhaust all reachable)
    proc = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "seed-j9", "--threshold", "100", "--json"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert proc.returncode == 0, f"Expected exit 0; got {proc.returncode}. stderr={proc.stderr!r}"
    data = json.loads(proc.stdout)
    # Then: all IDs in the JSON output exist in the codex and match what chaos_documents would return
    expected_ids = {"seed-j9", "seed-j10", "seed-j11"}
    actual_ids = {d["id"] for d in data["documents"]}
    assert actual_ids == expected_ids, (
        f"Expected IDs {expected_ids}; got {actual_ids}"
    )


# Unit — JSON mode: seed document is first element of documents array
# conceptual-workflows-codex-chaos step 5 (seed always first in result per FR-4)
def test_chaos_cli_json_seed_is_first_element(runner, tmp_path):
    import json
    import subprocess
    import sys

    # Given: project at tmp_path with "seed-doc" connected to others
    lore_dir = tmp_path / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    codex_dir = lore_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    _write_doc(codex_dir, "seed-first", related=["sf-n1", "sf-n2"])
    _write_doc(codex_dir, "sf-n1")
    _write_doc(codex_dir, "sf-n2")

    # When: CLI invoked with --json flag at end
    proc = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "seed-first", "--threshold", "60", "--json"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert proc.returncode == 0, f"Expected exit 0; got {proc.returncode}. stderr={proc.stderr!r}"
    data = json.loads(proc.stdout)
    # Then: first element's id is "seed-first"
    assert data["documents"][0]["id"] == "seed-first", (
        f"Expected first element id 'seed-first'; got {data['documents'][0]['id']!r}"
    )


# Unit — JSON mode: not-found → stderr is JSON error envelope, stdout empty
# conceptual-workflows-codex-chaos Failure Modes (Seed not found, JSON mode)
def test_chaos_cli_json_not_found_stderr_envelope(runner, tmp_path):
    import json
    import subprocess
    import sys

    # Given: project at tmp_path with no "phantom-doc"
    lore_dir = tmp_path / ".lore"
    lore_dir.mkdir(parents=True, exist_ok=True)
    codex_dir = lore_dir / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    _write_doc(codex_dir, "real-doc")

    # When: CLI invoked with --json flag at end and id="phantom-doc"
    proc = subprocess.run(
        [sys.executable, "-c", "from lore.cli import main; main()",
         "codex", "chaos", "phantom-doc", "--threshold", "50", "--json"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    # Then: exit 1, stdout empty, stderr parses as JSON error envelope
    assert proc.returncode == 1, f"Expected exit 1; got {proc.returncode}"
    assert proc.stdout == "", f"Expected empty stdout; got {proc.stdout!r}"
    error_envelope = json.loads(proc.stderr)
    assert error_envelope == {"error": 'Document "phantom-doc" not found'}, (
        f"Unexpected JSON error envelope: {error_envelope!r}"
    )


# Unit — chaos_documents raises ValueError when threshold=29
# conceptual-workflows-codex-chaos step 2 (validate_chaos_threshold called; ValueError on invalid value)
def test_chaos_documents_raises_value_error_for_threshold_29(tmp_path):
    # No codex setup needed — validator fires before any file I/O
    with pytest.raises(ValueError, match="--threshold must be between 30 and 100"):
        chaos_documents(tmp_path, "any-doc", threshold=29)


# Unit — chaos_documents raises ValueError when threshold=101
# conceptual-workflows-codex-chaos step 2 (validate_chaos_threshold called; ValueError on above-ceiling value)
def test_chaos_documents_raises_value_error_for_threshold_101(tmp_path):
    with pytest.raises(ValueError, match="--threshold must be between 30 and 100"):
        chaos_documents(tmp_path, "any-doc", threshold=101)


# Unit — chaos_documents does not raise when threshold=30
# conceptual-workflows-codex-chaos step 2 (validate_chaos_threshold: 30 is valid, no exception)
def test_chaos_documents_no_raise_for_threshold_30(tmp_path):
    # Given: a codex directory with "valid-doc"
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    _write_doc(codex_dir, "valid-doc", related=[])

    # When/Then: no ValueError raised for threshold at floor boundary
    try:
        chaos_documents(tmp_path, "valid-doc", threshold=30)
    except ValueError as exc:
        raise AssertionError(
            f"chaos_documents raised ValueError for threshold=30: {exc}"
        ) from exc


# Unit — chaos_documents does not raise when threshold=100
# conceptual-workflows-codex-chaos step 2 (validate_chaos_threshold: 100 is valid, no exception)
def test_chaos_documents_no_raise_for_threshold_100(tmp_path):
    # Given: a codex directory with "valid-doc"
    codex_dir = tmp_path / ".lore" / "codex"
    codex_dir.mkdir(parents=True)
    _write_doc(codex_dir, "valid-doc", related=[])

    # When/Then: no ValueError raised for threshold at ceiling boundary
    try:
        chaos_documents(tmp_path, "valid-doc", threshold=100)
    except ValueError as exc:
        raise AssertionError(
            f"chaos_documents raised ValueError for threshold=100: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# TestScanCodexFilter — filter_groups parameter on scan_codex
# Spec: filter-list-subcommands-us-1 (lore codex show filter-list-subcommands-us-1)
# Exercises: conceptual-workflows-filter-list step 3 (_apply_filter predicate)
# ---------------------------------------------------------------------------


def _write_filter_doc(codex_dir: "Path", rel_path: str, doc_id: str) -> "Path":
    """Write a minimal codex document at a given relative path within codex_dir."""
    filepath = codex_dir / rel_path
    filepath.parent.mkdir(parents=True, exist_ok=True)
    content = (
        f"---\nid: {doc_id}\ntitle: {doc_id.replace('-', ' ').title()}"
        f"\nsummary: Summary for {doc_id}.\n---\n\nBody.\n"
    )
    filepath.write_text(content)
    return filepath


class TestScanCodexFilter:
    """scan_codex(filter_groups=...) filters results to the requested namespace plus root-level docs."""

    # Unit — filter_groups=["conceptual"] returns conceptual + root only
    # conceptual-workflows-filter-list step 3 (_apply_filter predicate)
    def test_scan_codex_filter_returns_matched_group_and_root(self, bare_lore_dir):
        """scan_codex with filter_groups=["conceptual"] returns conceptual and root-level docs only."""
        codex_dir = bare_lore_dir / ".lore" / "codex"
        _write_filter_doc(codex_dir, "codex.md", "codex")
        _write_filter_doc(codex_dir, "conceptual/conceptual-entities-task.md", "conceptual-entities-task")
        _write_filter_doc(codex_dir, "technical/tech-cli-commands.md", "tech-cli-commands")

        result = list_codex(codex_dir.parent.parent, filter_groups=["conceptual"])

        ids = {d["id"] for d in result}
        assert "codex" in ids
        assert "conceptual-entities-task" in ids
        assert "tech-cli-commands" not in ids

    # Unit — filter_groups=["Conceptual"] returns root only (case-sensitive fail)
    # conceptual-workflows-filter-list step 3 (exact case-sensitive match)
    def test_scan_codex_filter_case_sensitive_no_match(self, bare_lore_dir):
        """scan_codex with filter_groups=["Conceptual"] does not match group "conceptual"."""
        codex_dir = bare_lore_dir / ".lore" / "codex"
        _write_filter_doc(codex_dir, "codex.md", "codex")
        _write_filter_doc(codex_dir, "conceptual/conceptual-entities-task.md", "conceptual-entities-task")

        result = list_codex(codex_dir.parent.parent, filter_groups=["Conceptual"])

        ids = {d["id"] for d in result}
        assert "conceptual-entities-task" not in ids
        assert "codex" in ids

    # Unit — filter_groups=["conceptual", "technical/api"] returns union + root
    # Exercises: conceptual-workflows-filter-list step 3 (OR logic)
    def test_scan_codex_multiple_filter_groups_returns_union(self, bare_lore_dir):
        """scan_codex with filter_groups=["conceptual", "technical/api"] returns union plus root-level docs."""
        codex_dir = bare_lore_dir / ".lore" / "codex"
        _write_filter_doc(codex_dir, "codex.md", "codex")
        _write_filter_doc(codex_dir, "conceptual/conceptual-entities-task.md", "conceptual-entities-task")
        _write_filter_doc(codex_dir, "technical/api/tech-api-spec.md", "tech-api-spec")
        _write_filter_doc(codex_dir, "technical/tech-overview.md", "tech-overview")

        result = list_codex(codex_dir.parent.parent, filter_groups=["conceptual", "technical/api"])

        ids = {d["id"] for d in result}
        assert "codex" in ids
        assert "conceptual-entities-task" in ids
        assert "tech-api-spec" in ids
        assert "tech-overview" not in ids

    # Unit — filter_groups=["technical/api"] excludes technical group files
    # Exercises: conceptual-workflows-filter-list step 3 (exact match excludes parent dir)
    def test_scan_codex_technical_api_excludes_technical_root(self, bare_lore_dir):
        """scan_codex with filter_groups=["technical/api"] excludes files in technical/ (group "technical")."""
        codex_dir = bare_lore_dir / ".lore" / "codex"
        _write_filter_doc(codex_dir, "codex.md", "codex")
        _write_filter_doc(codex_dir, "technical/api/tech-api-spec.md", "tech-api-spec")
        _write_filter_doc(codex_dir, "technical/tech-overview.md", "tech-overview")

        result = list_codex(codex_dir.parent.parent, filter_groups=["technical/api"])

        ids = {d["id"] for d in result}
        assert "codex" in ids
        assert "tech-api-spec" in ids
        assert "tech-overview" not in ids

    # Unit — scan_codex filter_groups=["nonexistent"] returns only root-level files
    # Exercises: conceptual-workflows-filter-list step 3 (_apply_filter: unknown token → empty match)
    def test_scan_codex_unknown_token_returns_root_only(self, bare_lore_dir):
        """scan_codex with filter_groups=["nonexistent"] returns only root-level docs; no exception raised."""
        codex_dir = bare_lore_dir / ".lore" / "codex"
        _write_filter_doc(codex_dir, "codex.md", "codex")
        _write_filter_doc(codex_dir, "conceptual/conceptual-entities-task.md", "conceptual-entities-task")

        result = list_codex(codex_dir.parent.parent, filter_groups=["nonexistent"])

        ids = {d["id"] for d in result}
        assert "codex" in ids
        assert "conceptual-entities-task" not in ids

    # Unit — scan_codex filter_groups=["nonexistent"] with no root-level files returns empty list
    # Exercises: conceptual-workflows-filter-list step 3 (no root + no match → empty list, no exception)
    def test_scan_codex_unknown_token_no_root_returns_empty_list(self, bare_lore_dir):
        """scan_codex with filter_groups=["nonexistent"] and no root-level docs returns empty list — no exception."""
        codex_dir = bare_lore_dir / ".lore" / "codex"
        _write_filter_doc(codex_dir, "conceptual/conceptual-entities-task.md", "conceptual-entities-task")

        result = list_codex(codex_dir.parent.parent, filter_groups=["nonexistent"])

        assert result == []

    # Unit — scan_codex filter_groups=["conceptual", "nonexistent"] returns conceptual + root
    # Exercises: conceptual-workflows-filter-list step 3 (unknown token contributes no results; no error)
    def test_scan_codex_valid_and_unknown_token_partial_match(self, bare_lore_dir):
        """scan_codex with filter_groups=["conceptual", "nonexistent"] returns conceptual + root docs only."""
        codex_dir = bare_lore_dir / ".lore" / "codex"
        _write_filter_doc(codex_dir, "codex.md", "codex")
        _write_filter_doc(codex_dir, "conceptual/conceptual-entities-task.md", "conceptual-entities-task")
        _write_filter_doc(codex_dir, "technical/tech-cli-commands.md", "tech-cli-commands")

        result = list_codex(codex_dir.parent.parent, filter_groups=["conceptual", "nonexistent"])

        ids = {d["id"] for d in result}
        assert "codex" in ids
        assert "conceptual-entities-task" in ids
        assert "tech-cli-commands" not in ids


# ---------------------------------------------------------------------------
# TestScanCodexBackwardCompat — filter_groups=None and [] are no-ops (US-4)
# Spec: filter-list-subcommands-us-4 (lore codex show filter-list-subcommands-us-4)
# Exercises: conceptual-workflows-filter-list step 3 (filter_groups=None → return all)
# ---------------------------------------------------------------------------


class TestScanCodexBackwardCompat:
    """scan_codex with filter_groups=None or [] returns all documents — backward compatible."""

    # Unit — scan_codex filter_groups=None returns all documents (default path)
    # Exercises: conceptual-workflows-filter-list step 3 (filter_groups=None → return all)
    def test_scan_codex_filter_none_returns_all(self, tmp_path):
        """scan_codex with filter_groups=None returns all documents across all groups."""
        codex_dir = tmp_path / ".lore" / "codex"
        _write_filter_doc(codex_dir, "codex.md", "codex")
        _write_filter_doc(codex_dir, "conceptual/conceptual-entities-task.md", "conceptual-entities-task")
        _write_filter_doc(codex_dir, "technical/tech-cli-commands.md", "tech-cli-commands")

        results = list_codex(codex_dir.parent.parent, filter_groups=None)

        ids = [d["id"] for d in results]
        assert "codex" in ids
        assert "conceptual-entities-task" in ids
        assert "tech-cli-commands" in ids

    # Unit — scan_codex filter_groups=[] returns all documents (empty list = no filter)
    # Exercises: conceptual-workflows-filter-list step 3 (empty list treated as no filter)
    def test_scan_codex_filter_empty_list_returns_all(self, tmp_path):
        """scan_codex with filter_groups=[] returns all documents — empty list is a no-op."""
        codex_dir = tmp_path / ".lore" / "codex"
        _write_filter_doc(codex_dir, "codex.md", "codex")
        _write_filter_doc(codex_dir, "conceptual/conceptual-entities-task.md", "conceptual-entities-task")
        _write_filter_doc(codex_dir, "technical/tech-cli-commands.md", "tech-cli-commands")

        results = list_codex(codex_dir.parent.parent, filter_groups=[])

        ids = [d["id"] for d in results]
        assert "codex" in ids
        assert "conceptual-entities-task" in ids
        assert "tech-cli-commands" in ids

    # Unit — scan_codex called without filter_groups argument returns all documents
    # Exercises: backward compat — old callers that never passed filter_groups still work
    def test_scan_codex_no_filter_argument_returns_all(self, tmp_path):
        """scan_codex called without filter_groups (default) returns all documents."""
        codex_dir = tmp_path / ".lore" / "codex"
        _write_filter_doc(codex_dir, "codex.md", "codex")
        _write_filter_doc(codex_dir, "conceptual/conceptual-entities-task.md", "conceptual-entities-task")

        results = list_codex(codex_dir.parent.parent)

        ids = [d["id"] for d in results]
        assert "codex" in ids
        assert "conceptual-entities-task" in ids


# ---------------------------------------------------------------------------
# C1 — the scoped codex read path
#
# Spec: nested-projects-spec (lore codex show nested-projects-spec) — C1
# Decisions: D-3/A-7 (inheritance is unconditional, federation is opt-in),
#            D-4 (what each scope returns), D-8 (bare resolves locally first,
#            qualified never does), D-10 (no codex doc is a seeded default),
#            D-15/D-16 (origin on every row, one sort key), A-2 (transient and
#            sources never export)
# ---------------------------------------------------------------------------


_ANCESTOR_CONFIG = """\
[shared]
exports = ["shared-*"]

[[descendants]]
name = "lore"
path = "lore"
exports = ["direct-doc"]
"""


class TestScopedListCodex:
    def test_an_ancestors_export_arrives_qualified_and_tagged(self, tree):
        # nested-projects-spec — FR-2/FR-15/FR-16: inheritance needs no flag
        from lore.codex import list_codex

        tree.configure(tree.camelot, _ANCESTOR_CONFIG)
        tree.doc(tree.camelot, "shared-one")
        tree.doc(tree.lore, "local-one")

        records = {d["id"]: d for d in list_codex(tree.lore)}

        assert records["camelot:shared-one"]["origin"] == "camelot"
        assert records["local-one"]["origin"] == "self"

    def test_a_descendant_gets_the_block_export_as_well_as_the_shared_one(
        self, tree
    ):
        # nested-projects-spec — FR-3/FR-4: the union of both tables
        from lore.codex import list_codex

        tree.configure(tree.camelot, _ANCESTOR_CONFIG)
        tree.doc(tree.camelot, "shared-one")
        tree.doc(tree.camelot, "direct-doc")

        ids = [d["id"] for d in list_codex(tree.lore)]

        assert ids == ["camelot:direct-doc", "camelot:shared-one"]

    def test_a_block_export_reaches_only_the_project_it_names(self, tree):
        # nested-projects-spec — D-11: identity is the block's path
        from lore.codex import list_codex

        tree.configure(tree.camelot, _ANCESTOR_CONFIG)
        tree.doc(tree.camelot, "direct-doc")
        tree.doc(tree.realm, "own-doc")

        records = list_codex(tree.realm)

        assert [d["id"] for d in records] == ["own-doc"]
        assert records[0]["origin"] == "self"

    def test_an_unexported_ancestor_document_is_invisible(self, tree):
        # nested-projects-spec — FR-5: an export is a curated offer
        from lore.codex import list_codex

        tree.configure(tree.camelot, _ANCESTOR_CONFIG)
        tree.doc(tree.camelot, "private-one")
        tree.doc(tree.lore, "local-one")

        records = list_codex(tree.lore)

        assert [d["id"] for d in records] == ["local-one"]
        assert records[0]["origin"] == "self"

    def test_a_stray_ancestor_with_no_export_table_is_inert(self, tree):
        # nested-projects-spec — D-14: a marker directory above is not a tree
        from lore.codex import list_codex

        tree.doc(tree.camelot, "shared-one")
        tree.doc(tree.lore, "local-one")

        records = list_codex(tree.lore)

        assert [d["id"] for d in records] == ["local-one"]
        assert records[0]["origin"] == "self"

    def test_a_transient_ancestor_document_never_exports(self, tree):
        # nested-projects-spec — A-2: a transient doc is deleted when its
        # feature ships, so exporting one guarantees a dangling reference
        from lore.codex import list_codex

        tree.configure(tree.camelot, '[shared]\nexports = ["*"]\n')
        tree.doc(tree.camelot, "shared-one")
        tree.doc(tree.camelot, "wip-spec", group="transient")

        assert [d["id"] for d in list_codex(tree.lore)] == ["camelot:shared-one"]

    def test_a_source_ancestor_document_never_exports(self, tree):
        # nested-projects-spec — A-2: a source is disposable raw input
        from lore.codex import list_codex

        tree.configure(tree.camelot, '[shared]\nexports = ["*"]\n')
        tree.doc(tree.camelot, "raw-input", group="sources")
        tree.doc(tree.camelot, "shared-one")

        assert [d["id"] for d in list_codex(tree.lore)] == ["camelot:shared-one"]

    def test_a_codex_document_in_a_default_group_still_exports(self, tree):
        # nested-projects-spec — D-10: `lore init` seeds no codex document, so
        # the seeded-default exclusion has nothing to remove from this layer
        from lore.codex import list_codex

        tree.configure(tree.camelot, '[shared]\nexports = ["*"]\n')
        tree.doc(tree.camelot, "grouped-doc", group="default")

        assert [d["id"] for d in list_codex(tree.lore)] == ["camelot:grouped-doc"]

    def test_the_merged_list_is_sorted_on_the_qualified_id(self, tree):
        # nested-projects-spec — D-16: one sort rule, applied to the id a
        # caller can feed back in, never grouped by project
        from lore.codex import list_codex

        tree.configure(tree.camelot, '[shared]\nexports = ["*"]\n')
        tree.doc(tree.camelot, "alpha")
        tree.doc(tree.camelot, "zulu")
        tree.doc(tree.lore, "beta")
        tree.doc(tree.lore, "delta")

        ids = [d["id"] for d in list_codex(tree.lore)]

        assert ids == ["beta", "camelot:alpha", "camelot:zulu", "delta"]

    def test_every_record_carries_its_group(self, tree):
        # nested-projects-spec — FR-16: the GROUP column is rendered from the
        # record, because only the owning project can derive it
        from lore.codex import list_codex

        tree.configure(tree.camelot, '[shared]\nexports = ["*"]\n')
        tree.doc(tree.camelot, "nested-doc", group="conceptual")
        tree.doc(tree.lore, "root-doc")

        groups = {d["id"]: d["group"] for d in list_codex(tree.lore)}

        assert groups == {"camelot:nested-doc": "conceptual", "root-doc": ""}

    def test_scope_all_adds_every_descendant_unfiltered(self, tree):
        # nested-projects-spec — D-4: an ancestor asking for the subtree wants
        # that material, not its own exports reflected back
        from lore.codex import list_codex

        tree.doc(tree.camelot, "own-doc")
        tree.doc(tree.lore, "child-doc")
        tree.doc(tree.realm, "grandchild-doc")

        ids = [d["id"] for d in list_codex(tree.camelot, scope="all")]

        assert ids == ["lore:child-doc", "own-doc", "realm:grandchild-doc"]

    def test_the_default_scope_walks_nothing_downward(self, tree):
        # nested-projects-spec — A-7/N-3: federation is opt-in
        from lore.codex import list_codex

        tree.doc(tree.camelot, "own-doc")
        tree.doc(tree.lore, "child-doc")

        records = list_codex(tree.camelot)

        assert [d["id"] for d in records] == ["own-doc"]
        assert records[0]["origin"] == "self"

    def test_a_named_project_is_read_alone(self, tree):
        # nested-projects-spec — D-4/D-11: `--project` matches a project's own
        # resolved name
        from lore.codex import list_codex

        tree.doc(tree.camelot, "own-doc")
        tree.doc(tree.lore, "child-doc")

        ids = [d["id"] for d in list_codex(tree.camelot, scope="lore")]

        assert ids == ["lore:child-doc"]

    def test_an_unknown_project_name_names_the_projects_in_scope(self, tree):
        # nested-projects-spec — FR-12: the exact message is a contract
        from lore.codex import list_codex
        from lore.projects import UnknownProjectError

        tree.doc(tree.camelot, "own-doc")

        with pytest.raises(UnknownProjectError) as excinfo:
            list_codex(tree.camelot, scope="nope")

        assert str(excinfo.value) == (
            'Unknown project "nope". Projects in scope: lore, realm.'
        )

    def test_an_unknown_project_name_in_a_standalone_project_says_so(self, tree):
        # nested-projects-spec — FR-12: the second exact message
        from lore.codex import list_codex
        from lore.projects import UnknownProjectError

        tree.doc(tree.realm, "own-doc")

        with pytest.raises(UnknownProjectError) as excinfo:
            list_codex(tree.realm, scope="nope")

        assert str(excinfo.value) == (
            'Unknown project "nope". No other Lore project is in scope.'
        )

    def test_group_filters_apply_inside_every_project(self, tree):
        # nested-projects-spec — FR-16: a scoped read keeps every existing
        # filter, applied per project
        from lore.codex import list_codex

        tree.configure(tree.camelot, '[shared]\nexports = ["*"]\n')
        tree.doc(tree.camelot, "kept-doc", group="conceptual")
        tree.doc(tree.camelot, "dropped-doc", group="technical")
        tree.doc(tree.lore, "local-kept", group="conceptual")

        ids = [d["id"] for d in list_codex(tree.lore, ["conceptual"])]

        assert ids == ["camelot:kept-doc", "local-kept"]


class TestScopedSearchDocuments:
    def test_it_tags_and_qualifies_a_match_from_an_ancestor(self, tree):
        # nested-projects-spec — W1: the ancestor's material answers the search
        from lore.codex import search_documents

        tree.configure(tree.camelot, '[shared]\nexports = ["*"]\n')
        tree.doc(tree.camelot, "shared-one", summary="Talks about dispatch.")
        tree.doc(tree.lore, "local-one", summary="Also about dispatch.")

        records = {d["id"]: d for d in search_documents(tree.lore, "dispatch")}

        assert records["camelot:shared-one"]["origin"] == "camelot"
        assert records["local-one"]["origin"] == "self"

    def test_it_never_surfaces_a_transient_ancestor_document(self, tree):
        # nested-projects-spec — A-2 / F-1 item 3: search reads the same scoped
        # listing as `codex list`, so the layer exclusion holds on both paths
        from lore.codex import search_documents

        tree.configure(tree.camelot, '[shared]\nexports = ["*"]\n')
        tree.doc(
            tree.camelot, "wip-spec", group="transient", summary="About dispatch."
        )

        assert search_documents(tree.lore, "dispatch") == []

    def test_it_returns_no_path(self, tree):
        # nested-projects-spec — decisions-006-id-references: an agent
        # addresses an entity by id, never by a foreign file path
        from lore.codex import search_documents

        tree.configure(tree.camelot, '[shared]\nexports = ["*"]\n')
        tree.doc(tree.camelot, "shared-one", summary="About dispatch.")

        records = search_documents(tree.lore, "dispatch")

        assert set(records[0]) == {"id", "title", "summary", "origin"}

    def test_it_is_sorted_on_the_qualified_id(self, tree):
        # nested-projects-spec — D-16
        from lore.codex import search_documents

        tree.configure(tree.camelot, '[shared]\nexports = ["*"]\n')
        tree.doc(tree.camelot, "alpha", summary="About dispatch.")
        tree.doc(tree.lore, "beta", summary="About dispatch.")

        ids = [d["id"] for d in search_documents(tree.lore, "dispatch")]

        assert ids == ["beta", "camelot:alpha"]


class TestScopedReadDocument:
    def test_it_reads_an_inherited_document_by_qualified_id(self, tree):
        # nested-projects-spec — W4: the id a listing returns is the id a
        # caller feeds back in
        from lore.codex import read_document

        tree.configure(tree.camelot, '[shared]\nexports = ["*"]\n')
        tree.doc(tree.camelot, "shared-one", body="Ancestor body.")

        record = read_document(tree.lore, "camelot:shared-one")

        assert record["id"] == "camelot:shared-one"
        assert record["origin"] == "camelot"
        assert record["body"].strip() == "Ancestor body."

    def test_a_bare_id_resolves_locally_first(self, tree):
        # nested-projects-spec — D-8: local wins
        from lore.codex import read_document

        tree.configure(tree.camelot, '[shared]\nexports = ["*"]\n')
        tree.doc(tree.camelot, "twin", body="Ancestor body.")
        tree.doc(tree.lore, "twin", body="Local body.")

        record = read_document(tree.lore, "twin")

        assert record["origin"] == "self"
        assert record["body"].strip() == "Local body."

    def test_a_qualified_id_never_resolves_locally(self, tree):
        # nested-projects-spec — D-8: a codex id is free-form, so a local doc
        # may hold a colon; it is still never reachable through a qualifier
        from lore.codex import read_document

        tree.write(
            tree.lore,
            "codex/colon-doc.md",
            "---\nid: camelot:shared-one\ntitle: Local\nsummary: Local.\n---\n\nLocal body.\n",
        )

        assert read_document(tree.lore, "camelot:shared-one") is None

    def test_an_unexported_ancestor_document_reads_as_a_miss(self, tree):
        # nested-projects-spec — C1: invisible, not an error
        from lore.codex import read_document

        tree.configure(tree.camelot, _ANCESTOR_CONFIG)
        tree.doc(tree.camelot, "private-one")

        assert read_document(tree.lore, "camelot:private-one") is None

    def test_a_local_record_carries_the_self_origin(self, tree):
        # nested-projects-spec — D-15: `origin` is on every record, always
        from lore.codex import read_document

        tree.doc(tree.lore, "local-one")

        assert read_document(tree.lore, "local-one")["origin"] == "self"


class TestScopedReadDocumentsWithGlossary:
    def test_it_threads_the_scope_into_each_document(self, tree):
        # nested-projects-spec — C1: one envelope, scoped the same way
        from lore.codex import read_documents_with_glossary

        tree.configure(tree.camelot, '[shared]\nexports = ["*"]\n')
        tree.doc(tree.camelot, "shared-one")

        envelope = read_documents_with_glossary(
            tree.lore, ["camelot:shared-one"], skip_glossary=True
        )

        assert envelope["documents"][0]["origin"] == "camelot"

    def test_a_missing_id_still_fails_soft(self, tree):
        # nested-projects-spec — C1: the fail-soft path survives a scoped read
        from lore.codex import read_documents_with_glossary

        envelope = read_documents_with_glossary(
            tree.lore, ["no-such-doc"], skip_glossary=True
        )

        assert envelope["documents"] == [{"id": "no-such-doc", "not_found": True}]

    def test_it_surfaces_an_inherited_glossary_term(self, tree):
        # nested-projects-spec — D-22: the auto-surface reads the merged view
        from lore.codex import read_documents_with_glossary

        tree.configure(tree.camelot, "[shared]\nglossary = true\n")
        tree.glossary(tree.camelot, (("Quest", "A body of work."),))
        tree.doc(tree.lore, "local-one", body="This mentions a quest.")

        envelope = read_documents_with_glossary(tree.lore, ["local-one"])

        assert [item.keyword for item in envelope["glossary"]] == ["Quest"]


class TestChaosStaysLocal:
    def test_chaos_never_reads_an_inherited_document(self, tree):
        # nested-projects-spec — D-5: `codex chaos` takes no `--project`, and
        # its termination ratio is defined over this project's own subgraph
        from lore.codex import chaos_documents

        tree.configure(tree.camelot, '[shared]\nexports = ["*"]\n')
        tree.doc(tree.camelot, "shared-one")
        tree.doc(tree.lore, "local-one")

        assert chaos_documents(tree.lore, "camelot:shared-one", 50) is None
        assert [d["id"] for d in chaos_documents(tree.lore, "local-one", 50)] == [
            "local-one"
        ]
