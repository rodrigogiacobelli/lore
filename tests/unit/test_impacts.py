"""Unit tests for `lore.impacts` — codex-seed branch (US-003 + US-004).

Workflow: conceptual-workflows-impacts.
Tech Spec: lore-impacts-tech-spec.
Stories:
    - lore-impacts-us-003 — codex-seed lookup happy path + declaration order.
    - lore-impacts-us-004 — JSON envelope, ImpactsError, is_glob_pattern kind.

Every import below points at symbols that do NOT exist yet (the `lore.impacts`
module is unwritten as of the Red phase). Import failure counts as a red
test — that is intentional. Green is responsible for creating the module
and exporting these names through `lore.impacts` (and re-exporting from
`lore.models` per Tech Spec FR-15 — covered separately by the models test).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

# Red: every one of these imports is expected to fail until the Green phase
# lands `src/lore/impacts.py`. Wrapped in try/except so collection succeeds
# and the surrounding test suite is not blocked — matches the pattern used
# by other red-phase test files (see tests/unit/test_knight.py).
try:
    from lore.impacts import (  # type: ignore[import-not-found]
        CodexBinding,
        ImpactsError,
        ImpactsResult,
        _load_codex_binds_index,
        classify_token,
        impacts,
    )
except ImportError:  # pragma: no cover — red phase, module not implemented yet
    CodexBinding = None  # type: ignore[assignment,misc]
    ImpactsError = None  # type: ignore[assignment,misc]
    ImpactsResult = None  # type: ignore[assignment,misc]
    _load_codex_binds_index = None  # type: ignore[assignment]
    classify_token = None  # type: ignore[assignment]
    impacts = None  # type: ignore[assignment]

# `_render_impacts_json` was hoisted to `lore.cli` in G3
# (transient-public-api-facade-plan). The few legacy assertions that remain
# below carry unique contracts not covered by the new
# tests/unit/test_cli_impacts_render.py goldens; the rest were deleted.
try:
    from lore.cli import _render_impacts_json  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover — defensive, lore.cli always present
    _render_impacts_json = None  # type: ignore[assignment]

# Cluster C (US-005 / US-006 / US-007) — path-seed symbols. These names do
# not exist in `lore.impacts` yet; same try/except None-fallback pattern as
# the cluster-B block above lets collection succeed while every test below
# fails with AttributeError or NotImplementedError until Green lands.
try:
    from lore.impacts import (  # type: ignore[import-not-found]
        CodeBinding,
        _has_glob_chars,
        _match_pattern,
        _normalize_path_input,
    )
except ImportError:  # pragma: no cover — red phase, symbols not implemented yet
    CodeBinding = None  # type: ignore[assignment,misc]
    _has_glob_chars = None  # type: ignore[assignment]
    _match_pattern = None  # type: ignore[assignment]
    _normalize_path_input = None  # type: ignore[assignment]

# transient-rites-us-5 — the codex `rites:` index helper. `_load_codex_rites_index`
# does not exist yet (it lands in US-005 Green, modelled on
# `_load_codex_binds_index`), so the import fails and the symbol is None until
# Green. Same try/except None-fallback pattern as the clusters above.
try:
    from lore.impacts import (  # type: ignore[import-not-found]
        _load_codex_rites_index,
    )
except ImportError:  # pragma: no cover — red phase, helper not implemented yet
    _load_codex_rites_index = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_codex_entry(
    project_root: Path,
    *,
    entry_id: str,
    binds: list | None = None,
    omit_binds: bool = False,
) -> Path:
    """Write a minimal codex markdown file under ``.lore/codex/``.

    The frontmatter holds the required id/title/summary triple plus an
    optional ``binds:`` list. ``omit_binds=True`` skips the key entirely
    (FR-4 "missing == empty" path).
    """
    fm: dict = {
        "id": entry_id,
        "title": entry_id.replace("-", " ").title(),
        "summary": f"Codex entry {entry_id}.",
    }
    if not omit_binds:
        fm["binds"] = binds if binds is not None else []
    front = yaml.safe_dump(fm, sort_keys=False, default_flow_style=False)
    codex_dir = project_root / ".lore" / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    path = codex_dir / f"{entry_id}.md"
    path.write_text(f"---\n{front}---\nBody for {entry_id}.\n", encoding="utf-8")
    return path


@pytest.fixture()
def tmp_project(tmp_path):
    """Bare project with `.lore/codex/` ready for codex entries."""
    (tmp_path / ".lore" / "codex").mkdir(parents=True)
    return tmp_path


@pytest.fixture(autouse=True)
def _clear_binds_index_cache():
    """Drop the lru_cache between tests so each test sees a clean codex.

    The Tech Spec specifies ``_load_codex_binds_index`` is wrapped in
    ``functools.lru_cache(maxsize=1)``. Different tmp paths would otherwise
    collide if the cache key collapsed. Safe no-op once the cache exists.
    """
    try:
        _load_codex_binds_index.cache_clear()  # type: ignore[attr-defined]
    except AttributeError:
        pass
    yield
    try:
        _load_codex_binds_index.cache_clear()  # type: ignore[attr-defined]
    except AttributeError:
        pass


# ===========================================================================
# US-003 — classify_token
# ===========================================================================


def test_classify_token_bare_id_returns_codex():
    """conceptual-workflows-impacts — Token Classification table.

    Bare lowercase-hyphen tokens (no `/`, no `.`) are codex IDs.
    """
    assert classify_token("tech-arch-source-layout") == "codex"


def test_classify_token_with_slash_returns_path():
    """conceptual-workflows-impacts — Token Classification: `/` → path."""
    assert classify_token("src/lore/cli.py") == "path"


def test_classify_token_with_dot_returns_path():
    """conceptual-workflows-impacts — Token Classification: `.` → path."""
    assert classify_token("README.md") == "path"


def test_classify_token_with_slash_only_returns_path():
    """A token with `/` but no `.` (e.g. a directory) classifies as path."""
    assert classify_token("src/lore") == "path"


def test_classify_token_single_segment_with_dot_returns_path():
    """A bare filename like `Makefile.in` (no `/`, contains `.`) → path."""
    assert classify_token("Makefile.in") == "path"


# ===========================================================================
# US-003 — `impacts()` codex-seed branch returns declaration order
# ===========================================================================


def test_codex_seed_returns_kind_codex(tmp_project):
    """conceptual-workflows-impacts — Step 2 codex-seed result envelope."""
    _write_codex_entry(tmp_project, entry_id="x", binds=["a.py"])
    result = impacts("x", project_root=tmp_project)
    assert result.kind == "codex"


def test_codex_seed_preserves_declaration_order(tmp_project):
    """conceptual-workflows-impacts — Step 2: declaration order from source.

    Authoring order in `binds:` must round-trip exactly through `impacts(...)`
    — neither alphabetised nor de-duplicated by anything below.
    """
    _write_codex_entry(tmp_project, entry_id="x", binds=["z.py", "a.py", "m.py"])
    result = impacts("x", project_root=tmp_project)
    assert tuple(b.path for b in result.codex_items) == ("z.py", "a.py", "m.py")


def test_codex_seed_mixed_exact_and_glob_round_trip(tmp_project):
    """conceptual-workflows-impacts — Step 3: codex-seed items carry kind.

    The codex-seed branch annotates each binding with `kind` (exact/glob)
    based on `is_glob_pattern`, while order remains the author's.
    """
    _write_codex_entry(
        tmp_project,
        entry_id="dec-006-id-references",
        binds=["src/lore/cli.py", "src/lore/**/*.py", "tests/unit/test_models.py"],
    )
    result = impacts("dec-006-id-references", project_root=tmp_project)
    assert tuple(b.path for b in result.codex_items) == (
        "src/lore/cli.py",
        "src/lore/**/*.py",
        "tests/unit/test_models.py",
    )
    assert tuple(b.kind for b in result.codex_items) == ("exact", "glob", "exact")


def test_codex_seed_empty_list_returns_empty_tuple(tmp_project):
    """conceptual-workflows-impacts — Empty Result Behaviour: codex seed."""
    _write_codex_entry(tmp_project, entry_id="empty", binds=[])
    result = impacts("empty", project_root=tmp_project)
    assert result == ImpactsResult(kind="codex", codex_items=())


def test_codex_seed_missing_key_returns_empty_tuple(tmp_project):
    """conceptual-workflows-impacts — FR-4: missing binds == empty binds."""
    _write_codex_entry(tmp_project, entry_id="absent", omit_binds=True)
    result = impacts("absent", project_root=tmp_project)
    assert result == ImpactsResult(kind="codex", codex_items=())


def test_codex_seed_missing_and_empty_are_byte_identical(tmp_project):
    """conceptual-workflows-impacts — FR-4 parity: same value for both forms."""
    _write_codex_entry(tmp_project, entry_id="with-empty", binds=[])
    _write_codex_entry(tmp_project, entry_id="no-key", omit_binds=True)
    r1 = impacts("with-empty", project_root=tmp_project)
    r2 = impacts("no-key", project_root=tmp_project)
    assert r1 == r2


# ===========================================================================
# US-003 — `_load_codex_binds_index` preserves YAML sequence order
# ===========================================================================


def test_load_codex_binds_index_preserves_yaml_sequence_order(tmp_project):
    """conceptual-workflows-impacts — Step 2: order is the author's.

    `parse_frontmatter_doc` with `extra_fields=("binds",)` returns the raw
    list, and PyYAML preserves sequence order naturally; the loader must
    not sort or otherwise re-order entries.
    """
    _write_codex_entry(tmp_project, entry_id="x", binds=["b.py", "a.py"])
    index = _load_codex_binds_index(tmp_project / ".lore" / "codex")
    assert index["x"] == ["b.py", "a.py"]


def test_load_codex_binds_index_returns_empty_list_for_missing_key(tmp_project):
    """conceptual-workflows-impacts — FR-4: missing key materialises as []."""
    _write_codex_entry(tmp_project, entry_id="x", omit_binds=True)
    index = _load_codex_binds_index(tmp_project / ".lore" / "codex")
    assert index["x"] == []


def test_load_codex_binds_index_indexes_every_entry(tmp_project):
    """conceptual-workflows-impacts — Step 2: one pass over the codex dir."""
    _write_codex_entry(tmp_project, entry_id="a", binds=["x.py"])
    _write_codex_entry(tmp_project, entry_id="b", binds=["y.py"])
    _write_codex_entry(tmp_project, entry_id="c", binds=[])
    index = _load_codex_binds_index(tmp_project / ".lore" / "codex")
    assert set(index.keys()) >= {"a", "b", "c"}
    assert index["a"] == ["x.py"]
    assert index["b"] == ["y.py"]
    assert index["c"] == []


# ===========================================================================
# US-004 — ImpactsError shape + unknown-ID error path
# ===========================================================================


def test_impacts_error_is_value_error_subclass():
    """conceptual-workflows-impacts — Python API parity: ImpactsError ⊆ ValueError.

    Realm and other Python-API consumers must be able to `except ValueError`.
    """
    assert issubclass(ImpactsError, ValueError)


def test_unknown_codex_id_raises_impacts_error(tmp_project):
    """conceptual-workflows-impacts — Failure Modes: unknown codex id verbatim.

    The exception message is part of the public contract (orchestrator parses
    stderr in default mode). Spec says: 'Unknown codex id: "<token>"'.
    """
    with pytest.raises(ImpactsError) as exc_info:
        impacts("no-such-id", project_root=tmp_project)
    assert str(exc_info.value) == 'Unknown codex id: "no-such-id"'


def test_unknown_codex_id_does_not_raise_generic_keyerror(tmp_project):
    """Worker code must surface `ImpactsError`, not bubble a raw `KeyError`."""
    with pytest.raises(ImpactsError):
        impacts("no-such-id", project_root=tmp_project)


# ===========================================================================
# US-004 — `_render_impacts_json` codex branch
# Note: declaration-order, empty-envelope, and return-type assertions were
# migrated to tests/unit/test_cli_impacts_render.py during G3. Only the
# kind-respects-producer contract remains here — it pins behavioural
# single-source-of-truth, not output shape, so it lives with the impacts
# producer rather than the renderer goldens.
# ===========================================================================


def test_render_impacts_json_uses_kind_from_codex_binding():
    """The renderer must honour the CodexBinding.kind already set by `impacts()`.

    It should NOT recompute via `is_glob_pattern` from the path — that
    classification belongs to the producer, not the formatter (single
    source of truth, per Tech Spec § "Exact-vs-glob dedup").
    """
    result = ImpactsResult(
        kind="codex",
        codex_items=(
            # Deliberately mark a glob-looking path as exact to detect re-derivation.
            CodexBinding(path="foo[ab].py", kind="exact"),
        ),
    )
    payload = json.loads(_render_impacts_json(result))
    assert payload == {"impacts": [{"path": "foo[ab].py", "kind": "exact"}]}


# ===========================================================================
# US-004 — CodexBinding dataclass shape
# ===========================================================================


def test_codex_binding_is_frozen_dataclass():
    """Tech Spec: `@dataclasses.dataclass(frozen=True)`.

    Frozen guarantees results are hashable/immutable for orchestrators.
    """
    binding = CodexBinding(path="x.py", kind="exact")
    with pytest.raises(Exception):
        binding.path = "y.py"  # type: ignore[misc]


def test_codex_binding_carries_path_and_kind():
    """CodexBinding must expose exactly the two public attributes."""
    binding = CodexBinding(path="x.py", kind="glob")
    assert binding.path == "x.py"
    assert binding.kind == "glob"


def test_impacts_result_is_frozen_dataclass():
    """Tech Spec — ImpactsResult is frozen so the orchestrator can cache it."""
    result = ImpactsResult(kind="codex", codex_items=())
    with pytest.raises(Exception):
        result.kind = "code"  # type: ignore[misc]


def test_impacts_result_default_for_codex_items_is_empty_tuple():
    """Tech Spec — default `codex_items=()` ensures Empty Result Behaviour."""
    result = ImpactsResult(kind="codex")
    assert result.codex_items == ()


# ===========================================================================
# US-005 — `_has_glob_chars` helper
# ===========================================================================


def test_has_glob_chars_star_is_glob():
    """conceptual-workflows-impacts — Step 3 "Literal vs Glob": `*` → glob."""
    assert _has_glob_chars("*") is True


def test_has_glob_chars_question_mark_is_glob():
    """conceptual-workflows-impacts — Step 3 "Literal vs Glob": `?` → glob."""
    assert _has_glob_chars("?") is True


def test_has_glob_chars_bracket_is_glob():
    """conceptual-workflows-impacts — Step 3 "Literal vs Glob": `[` → glob."""
    assert _has_glob_chars("[ab]") is True


def test_has_glob_chars_plain_path_is_not_glob():
    """conceptual-workflows-impacts — Step 3: literal path has no glob chars."""
    assert _has_glob_chars("src/lore/cli.py") is False


def test_has_glob_chars_empty_string_is_not_glob():
    """conceptual-workflows-impacts — Step 3: empty string has no glob chars."""
    assert _has_glob_chars("") is False


def test_has_glob_chars_agrees_with_is_glob_pattern():
    """standards-dry — both glob-detectors must agree across the full alphabet.

    `validators.is_glob_pattern` is the public source of truth; the hot-loop
    local mirror in `impacts._has_glob_chars` must yield identical answers
    for every probe.
    """
    from lore.validators import is_glob_pattern

    probes = ["", "x", "x.y", "*", "?", "[a]", "src/**/*.py", "a?b", "no-globs"]
    for p in probes:
        assert _has_glob_chars(p) is is_glob_pattern(p), p


# ===========================================================================
# US-005 — `_match_pattern` matcher
# ===========================================================================


def test_match_pattern_literal_equality_true():
    """conceptual-workflows-impacts — Step 3 "Literal: exact equality"."""
    assert _match_pattern("src/lore/cli.py", "src/lore/cli.py") is True


def test_match_pattern_literal_inequality_false():
    """conceptual-workflows-impacts — Step 3: literals not equal → False."""
    assert _match_pattern("src/lore/cli.py", "src/lore/other.py") is False


def test_match_pattern_single_star_matches_within_segment():
    """conceptual-workflows-impacts — Step 3 "Plain glob: segment-aware *"."""
    assert _match_pattern("foo.py", "*.py") is True


def test_match_pattern_single_star_does_not_cross_slash():
    """conceptual-workflows-impacts — Step 3: single `*` stops at `/`.

    `*.py` MUST NOT match `a/foo.py` — that is the whole reason `**` exists.
    """
    assert _match_pattern("a/foo.py", "*.py") is False


def test_match_pattern_double_star_spans_single_segment():
    """conceptual-workflows-impacts — Step 3 "Glob with **": one nested dir."""
    assert _match_pattern("src/lore/foo.py", "src/**/*.py") is True


def test_match_pattern_double_star_spans_many_segments():
    """conceptual-workflows-impacts — Step 3 "Glob with **": deep nesting."""
    assert _match_pattern("src/a/b/c/foo.py", "src/**/*.py") is True


def test_match_pattern_segment_glob_does_not_span_directories():
    """conceptual-workflows-impacts — Step 3: narrow glob stays narrow."""
    assert _match_pattern("src/lore/test_models.py", "src/lore/test_*.py") is True
    assert _match_pattern("src/lore/sub/test_x.py", "src/lore/test_*.py") is False


def test_match_pattern_question_mark_matches_single_char():
    """conceptual-workflows-impacts — Step 3 "Plain glob": `?` = one char."""
    assert _match_pattern("foo1.py", "foo?.py") is True
    assert _match_pattern("foo12.py", "foo?.py") is False


def test_match_pattern_character_class_matches():
    """conceptual-workflows-impacts — Step 3 "Plain glob": `[...]` class."""
    assert _match_pattern("fooa.py", "foo[ab].py") is True
    assert _match_pattern("foob.py", "foo[ab].py") is True
    assert _match_pattern("fooc.py", "foo[ab].py") is False


def test_match_pattern_normalises_backslashes_to_posix():
    """conceptual-workflows-impacts — Step 3 "POSIX `/`-joined regardless of platform".

    Backslash-joined inputs must produce the same result as forward-slash.
    """
    assert _match_pattern("src\\lore\\cli.py", "src/lore/cli.py") is True
    assert _match_pattern("src\\lore\\foo.py", "src/**/*.py") is True


def test_match_pattern_double_star_at_root():
    """conceptual-workflows-impacts — Step 3 "Glob with **": top-level `**`."""
    assert _match_pattern("a/b/c.py", "**/*.py") is True
    assert _match_pattern("c.py", "**/*.py") is True


# ===========================================================================
# US-005 — `impacts()` code-seed branch
# ===========================================================================


def test_impacts_code_seed_returns_kind_code(tmp_project):
    """conceptual-workflows-impacts — Step 4: code-seed envelope kind."""
    _write_codex_entry(tmp_project, entry_id="x", binds=["src/lore/cli.py"])
    result = impacts("src/lore/cli.py", project_root=tmp_project)
    assert result.kind == "code"


def test_impacts_code_seed_exact_match(tmp_project):
    """conceptual-workflows-impacts — Step 3 "Literal: exact equality"."""
    _write_codex_entry(
        tmp_project, entry_id="dec-006-id-references", binds=["src/lore/cli.py"]
    )
    result = impacts("src/lore/cli.py", project_root=tmp_project)
    assert result.code_items == (
        CodeBinding(id="dec-006-id-references", match="exact", pattern=None),
    )


def test_impacts_code_seed_glob_match_carries_pattern(tmp_project):
    """conceptual-workflows-impacts — Step 4 "glob carries pattern"."""
    _write_codex_entry(
        tmp_project,
        entry_id="tech-arch-source-layout",
        binds=["src/lore/**/*.py"],
    )
    result = impacts("src/lore/foo.py", project_root=tmp_project)
    assert result.code_items == (
        CodeBinding(
            id="tech-arch-source-layout",
            match="glob",
            pattern="src/lore/**/*.py",
        ),
    )


def test_impacts_code_seed_sorted_alphabetically_by_id(tmp_project):
    """conceptual-workflows-impacts — Step 4 sort: alphabetical by codex id."""
    _write_codex_entry(tmp_project, entry_id="zeta", binds=["src/lore/cli.py"])
    _write_codex_entry(tmp_project, entry_id="alpha", binds=["src/lore/cli.py"])
    _write_codex_entry(tmp_project, entry_id="middle", binds=["src/lore/cli.py"])
    result = impacts("src/lore/cli.py", project_root=tmp_project)
    assert tuple(b.id for b in result.code_items) == ("alpha", "middle", "zeta")


def test_impacts_code_seed_exact_wins_over_glob_dedup(tmp_project):
    """conceptual-workflows-impacts — Step 3 dedup: FR-9 exact precedence.

    Same codex entry binds both an exact path and a glob over the same file:
    output must contain exactly one row, classified `exact`, with pattern None.
    """
    _write_codex_entry(
        tmp_project,
        entry_id="dup",
        binds=["src/lore/cli.py", "src/lore/**/*.py"],
    )
    result = impacts("src/lore/cli.py", project_root=tmp_project)
    assert result.code_items == (
        CodeBinding(id="dup", match="exact", pattern=None),
    )


def test_impacts_code_seed_no_matches_empty_tuple(tmp_project):
    """conceptual-workflows-impacts — Empty Result Behaviour: path seed.

    No raise; just an empty `code_items` tuple.
    """
    _write_codex_entry(tmp_project, entry_id="x", binds=["src/other/foo.py"])
    result = impacts("src/lore/orphan.py", project_root=tmp_project)
    assert result.kind == "code"
    assert result.code_items == ()


def test_impacts_code_seed_skips_empty_and_missing_binds(tmp_project):
    """conceptual-workflows-impacts — FR-4 parity at the code-seed layer.

    Entries with `binds: []` or no `binds:` key must never appear.
    """
    _write_codex_entry(tmp_project, entry_id="entry-empty", binds=[])
    _write_codex_entry(tmp_project, entry_id="entry-missing", omit_binds=True)
    _write_codex_entry(tmp_project, entry_id="good", binds=["src/lore/cli.py"])
    result = impacts("src/lore/cli.py", project_root=tmp_project)
    ids = tuple(b.id for b in result.code_items)
    assert "entry-empty" not in ids
    assert "entry-missing" not in ids
    assert "good" in ids


def test_impacts_code_seed_single_segment_star_does_not_match_subdir(tmp_project):
    """conceptual-workflows-impacts — Step 3: narrow glob stays narrow."""
    _write_codex_entry(
        tmp_project, entry_id="narrow", binds=["src/lore/*.py"]
    )
    result = impacts("src/lore/sub/foo.py", project_root=tmp_project)
    assert result.code_items == ()


# `_load_codex_binds_index` skip-malformed + lru_cache behaviour is already
# locked in by cluster B (the index loader has been live since US-003).
# Cluster C tests would pass immediately and so are intentionally omitted
# per the TDD-red rule.


# ===========================================================================
# US-006 — `_normalize_path_input` happy and failure paths
# ===========================================================================


def test_normalize_path_input_relative_stays_relative(tmp_project):
    """conceptual-workflows-impacts — Step 1: relative paths stay relative."""
    assert _normalize_path_input("src/lore/cli.py", tmp_project) == "src/lore/cli.py"


def test_normalize_path_input_absolute_inside_repo_returns_relative(tmp_project):
    """conceptual-workflows-impacts — Step 1: absolute inside repo → repo-relative.

    Uses `Path.resolve()` so the result is normalised across symlink-free
    inputs. We don't materialise the file because `_normalize_path_input`
    must not require filesystem existence for an in-repo relative output.
    """
    abs_in = str((tmp_project / "src" / "lore" / "cli.py"))
    assert (
        _normalize_path_input(abs_in, tmp_project) == "src/lore/cli.py"
    )


def test_normalize_path_input_absolute_outside_raises(tmp_project):
    """conceptual-workflows-impacts — Failure Modes: outside repo.

    Exact stderr text contract (Tech Spec § "Error Model"):
    `Path is outside the project root: "<token>"`.
    """
    with pytest.raises(ImpactsError) as exc:
        _normalize_path_input("/etc/passwd", tmp_project)
    assert str(exc.value) == 'Path is outside the project root: "/etc/passwd"'


def test_normalize_path_input_dotdot_raises(tmp_project):
    """conceptual-workflows-impacts — Failure Modes: traversal not allowed.

    `..` segment is rejected by string inspection (no `resolve()` needed).
    """
    with pytest.raises(ImpactsError) as exc:
        _normalize_path_input("../foo", tmp_project)
    assert str(exc.value) == 'Path traversal not allowed: "../foo"'


def test_normalize_path_input_dotdot_nested_raises(tmp_project):
    """conceptual-workflows-impacts — NFR-Security: any `..` segment rejected.

    The check is segment-based, not prefix-based — `a/../b` must also fail.
    """
    with pytest.raises(ImpactsError) as exc:
        _normalize_path_input("a/../b", tmp_project)
    assert 'Path traversal not allowed: "a/../b"' == str(exc.value)


def test_normalize_path_input_symlink_resolving_outside_raises(tmp_project):
    """conceptual-workflows-impacts — Step 1: symlinks resolving outside repo.

    Build `tmp_project/link-out` → `tmp_project.parent/outside`. Resolving
    the link lands outside the repo, so `_normalize_path_input` must reject.
    """
    target = tmp_project.parent / "outside-target"
    target.mkdir(exist_ok=True)
    link = tmp_project / "link-out"
    link.symlink_to(target)
    with pytest.raises(ImpactsError):
        _normalize_path_input("link-out", tmp_project)


def test_normalize_path_input_normalises_backslashes(tmp_project):
    """conceptual-workflows-impacts — Step 1: POSIX `/`-joined regardless of platform."""
    assert (
        _normalize_path_input("src\\lore\\cli.py", tmp_project)
        == "src/lore/cli.py"
    )


# ===========================================================================
# US-006 — `_render_impacts_json` code-seed branch
# All four legacy rows (exact-omits-pattern, glob-includes-pattern,
# empty-envelope, preserves-order) were migrated to
# tests/unit/test_cli_impacts_render.py during G3 (renderer hoisted to
# `lore.cli`). The new goldens cover byte-identical output for the same
# scenarios.
# ===========================================================================


# ===========================================================================
# US-006 — `CodeBinding` dataclass shape
# ===========================================================================


def test_code_binding_is_frozen_dataclass():
    """Tech Spec — `CodeBinding` is `@dataclass(frozen=True)`."""
    binding = CodeBinding(id="x", match="exact", pattern=None)
    with pytest.raises(Exception):
        binding.id = "y"  # type: ignore[misc]


def test_code_binding_carries_id_match_pattern():
    """Tech Spec — public attributes: `id`, `match`, `pattern`."""
    binding = CodeBinding(id="x", match="glob", pattern="a/*.py")
    assert binding.id == "x"
    assert binding.match == "glob"
    assert binding.pattern == "a/*.py"


def test_impacts_result_default_for_code_items_is_empty_tuple():
    """Tech Spec — `ImpactsResult` exposes `code_items` defaulting to `()`."""
    result = ImpactsResult(kind="code")
    assert result.code_items == ()


# ===========================================================================
# US-007 — `--direct-links` filter on code-seed
# ===========================================================================


def test_impacts_code_seed_direct_links_filters_globs(tmp_project):
    """conceptual-workflows-impacts — Step 5 filter behaviour.

    Glob matches dropped; exact matches retained.
    """
    _write_codex_entry(
        tmp_project, entry_id="exact-id", binds=["src/lore/cli.py"]
    )
    _write_codex_entry(
        tmp_project, entry_id="glob-id", binds=["src/lore/**/*.py"]
    )
    result = impacts(
        "src/lore/cli.py", project_root=tmp_project, direct_links=True
    )
    assert tuple(b.id for b in result.code_items) == ("exact-id",)
    assert all(b.match == "exact" for b in result.code_items)


def test_impacts_code_seed_direct_links_preserves_alphabetical_sort(tmp_project):
    """conceptual-workflows-impacts — Step 5: sort order unchanged after filter."""
    _write_codex_entry(tmp_project, entry_id="zeta-exact", binds=["src/lore/cli.py"])
    _write_codex_entry(tmp_project, entry_id="alpha-exact", binds=["src/lore/cli.py"])
    _write_codex_entry(tmp_project, entry_id="middle-glob", binds=["src/lore/**/*.py"])
    result = impacts(
        "src/lore/cli.py", project_root=tmp_project, direct_links=True
    )
    assert tuple(b.id for b in result.code_items) == (
        "alpha-exact",
        "zeta-exact",
    )


def test_impacts_code_seed_direct_links_empty_when_only_globs(tmp_project):
    """conceptual-workflows-impacts — Step 5: result may become empty.

    No raise; an empty `code_items` tuple is returned.
    """
    _write_codex_entry(
        tmp_project, entry_id="glob-id", binds=["src/lore/**/*.py"]
    )
    result = impacts(
        "src/lore/cli.py", project_root=tmp_project, direct_links=True
    )
    assert result.kind == "code"
    assert result.code_items == ()


# Codex-seed no-op for `--direct-links` (FR-11) is exercised end-to-end in
# `tests/e2e/test_impacts.py::test_direct_links_is_silent_noop_on_codex_seed`
# alongside the path-seed scenarios; no extra unit test is needed here
# because the codex-seed function signature already accepts the kwarg.


# ===========================================================================
# transient-rites-us-5 — `_load_codex_rites_index`
# Anchors:
#   tech-arch-frontmatter — a new codex edge is read via
#     parse_frontmatter_doc(extra_fields=("rites",)); no new parse helper.
#   decisions-014-link-direction — codex → rite is the only rite edge.
#   _load_codex_binds_index precedent (src/lore/impacts.py) — one scan_codex
#     walk builds {codex_id: [rite_id, ...]}; missing key materialises as [].
# ===========================================================================


def _write_codex_rites_entry(
    project_root: Path,
    *,
    entry_id: str,
    rites: list | None = None,
    omit_rites: bool = False,
) -> Path:
    """Write a minimal codex markdown file carrying an optional `rites:` list.

    Mirrors `_write_codex_entry` but for the codex → rite edge. ``omit_rites``
    skips the key entirely (absent == [] path).
    """
    fm: dict = {
        "id": entry_id,
        "title": entry_id.replace("-", " ").title(),
        "summary": f"Codex entry {entry_id}.",
    }
    if not omit_rites:
        fm["rites"] = rites if rites is not None else []
    front = yaml.safe_dump(fm, sort_keys=False, default_flow_style=False)
    codex_dir = project_root / ".lore" / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    path = codex_dir / f"{entry_id}.md"
    path.write_text(f"---\n{front}---\nBody for {entry_id}.\n", encoding="utf-8")
    return path


def test_load_codex_rites_index_maps_doc_to_rite_ids(tmp_project):
    """transient-rites-us-5 — single scan_codex walk maps codex id -> rite ids."""
    _write_codex_rites_entry(tmp_project, entry_id="ops-refunds", rites=["issue-refund"])
    index = _load_codex_rites_index(tmp_project / ".lore" / "codex")
    assert index["ops-refunds"] == ["issue-refund"]


def test_load_codex_rites_index_preserves_yaml_sequence_order(tmp_project):
    """transient-rites-us-5 — order is the author's; no sort/re-order."""
    _write_codex_rites_entry(tmp_project, entry_id="x", rites=["b-rite", "a-rite"])
    index = _load_codex_rites_index(tmp_project / ".lore" / "codex")
    assert index["x"] == ["b-rite", "a-rite"]


def test_load_codex_rites_index_missing_key_is_empty_list(tmp_project):
    """transient-rites-us-5 — absent `rites:` materialises as [] (== missing)."""
    _write_codex_rites_entry(tmp_project, entry_id="x", omit_rites=True)
    index = _load_codex_rites_index(tmp_project / ".lore" / "codex")
    assert index["x"] == []


def test_load_codex_rites_index_indexes_every_entry(tmp_project):
    """transient-rites-us-5 — one pass over the codex dir indexes all docs."""
    _write_codex_rites_entry(tmp_project, entry_id="a", rites=["r1"])
    _write_codex_rites_entry(tmp_project, entry_id="b", rites=["r2"])
    _write_codex_rites_entry(tmp_project, entry_id="c", rites=[])
    index = _load_codex_rites_index(tmp_project / ".lore" / "codex")
    assert set(index.keys()) >= {"a", "b", "c"}
    assert index["a"] == ["r1"]
    assert index["b"] == ["r2"]
    assert index["c"] == []


def test_load_codex_rites_index_empty_when_codex_dir_absent(tmp_path):
    """transient-rites-us-5 — a missing codex dir yields an empty index, no raise."""
    index = _load_codex_rites_index(tmp_path / ".lore" / "codex")
    assert index == {}
