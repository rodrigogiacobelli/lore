"""Unit tests for lore.rite.scan_rites — the rite storage loader.

Spec: transient-rites-us-1 (lore codex show transient-rites-us-1)
Workflow: conceptual-workflows-rite-crud / conceptual-workflows-rite-list

scan_rites(rites_dir, *, shared=False) -> list[dict]
  - main rites only by default (.lore/rites/main/*.yaml)
  - shared=True returns shared steps only (.lore/rites/shared/*.yaml)
  - empty dir -> []
  - results sorted by id
  - skips *.yaml.deleted files (soft-delete)

These tests import lore.rite directly (no CliRunner) per
technical-test-guidelines §2. They MUST fail until US-001 Green lands
src/lore/rite.py + lore.paths.rites_dir.
"""

from __future__ import annotations


# Canonical design-doc fixtures (Tech Spec §Exact YAML schemas).
MAIN_RITE_YAML = (
    "id: {id}\n"
    "title: {id} title\n"
    "summary: Confirm the customer is reachable, then refund.\n"
    "trigger: Customer requests a refund on a returned order.\n"
    "nodes:\n"
    "  - id: only\n"
    "    do: Do the thing.\n"
    "    then: done\n"
    "conclusions:\n"
    "  done:\n"
    "    audience: customer-care\n"
    "    response: Done.\n"
)

SHARED_STEP_YAML = (
    "id: {id}\n"
    "title: {id} title\n"
    "summary: Read and report the contact info.\n"
    "do: Read and report back the contact info.\n"
)


def _make_rite_dirs(root):
    """Create .lore/rites/{main,shared} under root and return rites_dir path."""
    from lore.paths import rites_dir, rites_main_dir, rites_shared_dir

    rites_main_dir(root).mkdir(parents=True)
    rites_shared_dir(root).mkdir(parents=True)
    return rites_dir(root)


def _seed_main(root, ids):
    from lore.paths import rites_main_dir

    for rid in ids:
        (rites_main_dir(root) / f"{rid}.yaml").write_text(
            MAIN_RITE_YAML.format(id=rid)
        )


def _seed_shared(root, ids):
    from lore.paths import rites_shared_dir

    for rid in ids:
        (rites_shared_dir(root) / f"{rid}.yaml").write_text(
            SHARED_STEP_YAML.format(id=rid)
        )


class TestScanRitesMainDefault:
    """scan_rites returns main rites only by default."""

    def test_returns_main_rites_only(self, tmp_path):
        # transient-rites-us-1 — main default returns main rites, not shared
        from lore.rite import scan_rites

        rdir = _make_rite_dirs(tmp_path)
        _seed_main(tmp_path, ["issue-refund"])
        _seed_shared(tmp_path, ["read-contact-info"])
        ids = [r["id"] for r in scan_rites(rdir)]
        assert ids == ["issue-refund"]

    def test_results_sorted_by_id(self, tmp_path):
        # transient-rites-us-1 — results in sorted order
        from lore.rite import scan_rites

        rdir = _make_rite_dirs(tmp_path)
        _seed_main(tmp_path, ["b-rite", "a-rite", "c-rite"])
        ids = [r["id"] for r in scan_rites(rdir)]
        assert ids == ["a-rite", "b-rite", "c-rite"]


class TestScanRitesShared:
    """scan_rites(shared=True) returns shared steps only."""

    def test_returns_shared_steps_only(self, tmp_path):
        # transient-rites-us-1 — shared=True reads shared/ only
        from lore.rite import scan_rites

        rdir = _make_rite_dirs(tmp_path)
        _seed_main(tmp_path, ["issue-refund"])
        _seed_shared(tmp_path, ["step-x"])
        ids = [s["id"] for s in scan_rites(rdir, shared=True)]
        assert ids == ["step-x"]

    def test_shared_results_sorted_by_id(self, tmp_path):
        # transient-rites-us-1 — shared results sorted by id
        from lore.rite import scan_rites

        rdir = _make_rite_dirs(tmp_path)
        _seed_shared(tmp_path, ["zeta", "alpha"])
        ids = [s["id"] for s in scan_rites(rdir, shared=True)]
        assert ids == ["alpha", "zeta"]


class TestScanRitesEmpty:
    """Empty directory returns []."""

    def test_empty_main_returns_empty_list(self, tmp_path):
        # transient-rites-us-1 — empty dir -> []
        from lore.rite import scan_rites

        rdir = _make_rite_dirs(tmp_path)
        assert scan_rites(rdir) == []

    def test_empty_shared_returns_empty_list(self, tmp_path):
        # transient-rites-us-1 — empty shared dir -> []
        from lore.rite import scan_rites

        rdir = _make_rite_dirs(tmp_path)
        assert scan_rites(rdir, shared=True) == []


class TestScanRitesSkipsDeleted:
    """*.yaml.deleted files are skipped (soft-delete, watcher precedent)."""

    def test_skips_yaml_deleted_main(self, tmp_path):
        # transient-rites-us-1 — skips *.yaml.deleted files
        from lore.paths import rites_main_dir
        from lore.rite import scan_rites

        rdir = _make_rite_dirs(tmp_path)
        _seed_main(tmp_path, ["a-rite", "b-rite"])
        # Soft-delete a-rite.
        (rites_main_dir(tmp_path) / "a-rite.yaml").rename(
            rites_main_dir(tmp_path) / "a-rite.yaml.deleted"
        )
        ids = [r["id"] for r in scan_rites(rdir)]
        assert "a-rite" not in ids
        assert ids == ["b-rite"]

    def test_skips_yaml_deleted_shared(self, tmp_path):
        # transient-rites-us-1 — skips *.yaml.deleted shared steps
        from lore.paths import rites_shared_dir
        from lore.rite import scan_rites

        rdir = _make_rite_dirs(tmp_path)
        _seed_shared(tmp_path, ["keep", "drop"])
        (rites_shared_dir(tmp_path) / "drop.yaml").rename(
            rites_shared_dir(tmp_path) / "drop.yaml.deleted"
        )
        ids = [s["id"] for s in scan_rites(rdir, shared=True)]
        assert ids == ["keep"]


class TestScanRitesReturnShape:
    """Each returned entry is a dict carrying at least the id."""

    def test_returns_list_of_dicts_with_id(self, tmp_path):
        # transient-rites-us-1 — return shape is list[dict] with id key
        from lore.rite import scan_rites

        rdir = _make_rite_dirs(tmp_path)
        _seed_main(tmp_path, ["issue-refund"])
        result = scan_rites(rdir)
        assert isinstance(result, list)
        assert all(isinstance(r, dict) for r in result)
        assert result[0]["id"] == "issue-refund"


# ---------------------------------------------------------------------------
# search_rites — case-insensitive substring browse over main rites.
# Spec: conceptual-workflows-rite-search step 1.
# ---------------------------------------------------------------------------


class TestSearchRites:
    """search_rites matches id/title/summary/trigger, case-insensitive."""

    def test_case_insensitive_match_returns_rite(self, tmp_path):
        from lore.rite import search_rites

        rdir = _make_rite_dirs(tmp_path)
        _seed_main(tmp_path, ["issue-refund"])
        ids = [r["id"] for r in search_rites(rdir, "REFUND")]
        assert ids == ["issue-refund"]

    def test_no_match_returns_empty_list(self, tmp_path):
        from lore.rite import search_rites

        rdir = _make_rite_dirs(tmp_path)
        _seed_main(tmp_path, ["issue-refund"])
        assert search_rites(rdir, "zzzznomatch") == []

    def test_matches_over_id(self, tmp_path):
        from lore.rite import search_rites

        rdir = _make_rite_dirs(tmp_path)
        _seed_main(tmp_path, ["issue-refund"])
        ids = [r["id"] for r in search_rites(rdir, "issue-ref")]
        assert ids == ["issue-refund"]

    def test_matches_over_summary(self, tmp_path):
        from lore.rite import search_rites

        rdir = _make_rite_dirs(tmp_path)
        _seed_main(tmp_path, ["issue-refund"])
        # MAIN_RITE_YAML summary contains "reachable".
        ids = [r["id"] for r in search_rites(rdir, "reachable")]
        assert ids == ["issue-refund"]

    def test_matches_over_trigger(self, tmp_path):
        from lore.rite import search_rites

        rdir = _make_rite_dirs(tmp_path)
        _seed_main(tmp_path, ["issue-refund"])
        # MAIN_RITE_YAML trigger contains "returned order".
        ids = [r["id"] for r in search_rites(rdir, "returned order")]
        assert ids == ["issue-refund"]

    def test_matches_over_title(self, tmp_path):
        from lore.rite import search_rites

        rdir = _make_rite_dirs(tmp_path)
        _seed_main(tmp_path, ["issue-refund"])
        # MAIN_RITE_YAML title is "issue-refund title".
        ids = [r["id"] for r in search_rites(rdir, "issue-refund title")]
        assert ids == ["issue-refund"]

    def test_searches_main_only_not_shared(self, tmp_path):
        from lore.rite import search_rites

        rdir = _make_rite_dirs(tmp_path)
        _seed_shared(tmp_path, ["read-contact-info"])
        # No main rites seeded; shared steps must not be searched.
        assert search_rites(rdir, "read-contact-info") == []


# ---------------------------------------------------------------------------
# read_rite — id resolution + non-recursive use:-inline flatten + error paths.
# Spec: transient-rites-us-3 / conceptual-workflows-rite-show.
# These MUST fail until US-003 Green lands read_rite + RiteError.
# ---------------------------------------------------------------------------


# Full node-graph main rite (use:-node + fork) and its referenced shared step.
CANONICAL_MAIN_RITE = """\
id: issue-refund
title: Issue a refund for a returned order
summary: Confirm the customer is reachable, then refund.
trigger: Customer requests a refund on a returned order.
nodes:
  - id: locate-order
    do: Find the order by id; confirm it is in 'returned' state.
    then: get-contact
  - id: get-contact
    use: read-contact-info
    then: review-contact
  - id: review-contact
    do: Decide whether contact details support a refund.
    then:
      - if: email and a current mailing address are present
        goto: do-refund
      - if: anything is missing or the address looks stale
        goto: request-update
  - id: do-refund
    do: Post the refund to billing. Record the txn id.
    then: refunded
  - id: request-update
    do: Ask the customer to confirm contact details first.
    then: contact-requested
conclusions:
  refunded:
    audience: customer-care
    response: Refund posted; share the transaction id.
  contact-requested:
    audience: customer-care
    response: Refund held pending a contact-details update.
"""

CANONICAL_SHARED_STEP = """\
id: read-contact-info
title: Read the user's contact information
summary: Read the user's email, phone, and mailing address from admin.
do: |
  Open the user profile in admin. Read and report back:
    - email
    - phone
    - mailing address, with its last-confirmed date
"""


def _seed_main_text(root, name, text):
    from lore.paths import rites_main_dir

    d = rites_main_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.yaml").write_text(text, encoding="utf-8")


def _seed_shared_text(root, name, text):
    from lore.paths import rites_shared_dir

    d = rites_shared_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.yaml").write_text(text, encoding="utf-8")


class TestReadRiteInlines:
    """read_rite inlines every use:-node FLAT (non-recursive)."""

    def test_inlines_shared_step_on_use_node(self, bare_lore_dir):
        # conceptual-workflows-rite-show step 2 — flatten attached as "step"
        from lore.paths import rites_dir
        from lore.rite import read_rite

        _seed_main_text(bare_lore_dir, "issue-refund", CANONICAL_MAIN_RITE)
        _seed_shared_text(bare_lore_dir, "read-contact-info", CANONICAL_SHARED_STEP)
        rite = read_rite(rites_dir(bare_lore_dir), "issue-refund")
        use_node = next(n for n in rite["nodes"] if n["id"] == "get-contact")
        assert use_node["step"]["id"] == "read-contact-info"  # flatten attached

    def test_inline_is_non_recursive(self, bare_lore_dir):
        # conceptual-workflows-rite-show step 2 — shared step has no nested "step"
        from lore.paths import rites_dir
        from lore.rite import read_rite

        _seed_main_text(bare_lore_dir, "issue-refund", CANONICAL_MAIN_RITE)
        _seed_shared_text(bare_lore_dir, "read-contact-info", CANONICAL_SHARED_STEP)
        rite = read_rite(rites_dir(bare_lore_dir), "issue-refund")
        use_node = next(n for n in rite["nodes"] if n["id"] == "get-contact")
        assert "step" not in use_node["step"]  # non-recursive

    def test_returns_nodes_and_conclusions(self, bare_lore_dir):
        # Unit Test Scenarios — returns dict with nodes and conclusions
        from lore.paths import rites_dir
        from lore.rite import read_rite

        _seed_main_text(bare_lore_dir, "issue-refund", CANONICAL_MAIN_RITE)
        _seed_shared_text(bare_lore_dir, "read-contact-info", CANONICAL_SHARED_STEP)
        rite = read_rite(rites_dir(bare_lore_dir), "issue-refund")
        assert "nodes" in rite
        assert "conclusions" in rite
        assert set(rite["conclusions"]) == {"refunded", "contact-requested"}


class TestReadRiteErrors:
    """read_rite raises RiteError on not-found and dangling use:."""

    def test_not_found_raises(self, bare_lore_dir):
        # conceptual-workflows-rite-show step 1 — not-found
        import pytest

        from lore.paths import rites_dir
        from lore.rite import RiteError, read_rite

        with pytest.raises(RiteError, match='Rite "nope" not found'):
            read_rite(rites_dir(bare_lore_dir), "nope")

    def test_dangling_use_raises(self, bare_lore_dir):
        # conceptual-workflows-rite-show step 2 — dangling use: at show time
        import pytest

        from lore.paths import rites_dir
        from lore.rite import RiteError, read_rite

        _seed_main_text(bare_lore_dir, "issue-refund", CANONICAL_MAIN_RITE)  # shared/ empty
        with pytest.raises(RiteError, match='shared step "read-contact-info" not found'):
            read_rite(rites_dir(bare_lore_dir), "issue-refund")

    def test_bare_shared_step_resolves(self, bare_lore_dir):
        # conceptual-workflows-rite-show step 1 + decisions-016 — bare shared id
        from lore.paths import rites_dir
        from lore.rite import read_rite

        _seed_shared_text(bare_lore_dir, "read-contact-info", CANONICAL_SHARED_STEP)
        result = read_rite(rites_dir(bare_lore_dir), "read-contact-info")
        assert result["id"] == "read-contact-info"

    def test_main_resolves_before_shared(self, bare_lore_dir):
        # Tech Notes — read_rite resolves main/ first, falling back to shared/
        from lore.paths import rites_dir
        from lore.rite import read_rite

        _seed_main_text(bare_lore_dir, "issue-refund", CANONICAL_MAIN_RITE)
        _seed_shared_text(bare_lore_dir, "read-contact-info", CANONICAL_SHARED_STEP)
        rite = read_rite(rites_dir(bare_lore_dir), "issue-refund")
        # A main rite carries nodes; a bare shared step would not.
        assert "nodes" in rite


class TestNodeGraphWalkResolvesTargets:
    """The node-graph walk resolves then/goto/use targets (shared with _check_rites)."""

    def test_walk_resolves_targets(self, bare_lore_dir):
        # conceptual-workflows-rite-show step 2 — then/goto/use resolution
        from lore.paths import rites_dir
        from lore.rite import read_rite

        _seed_main_text(bare_lore_dir, "issue-refund", CANONICAL_MAIN_RITE)
        _seed_shared_text(bare_lore_dir, "read-contact-info", CANONICAL_SHARED_STEP)
        rite = read_rite(rites_dir(bare_lore_dir), "issue-refund")
        # straight `then`, fork `goto`, and `use` all resolve to existing nodes.
        assert {n["id"] for n in rite["nodes"]} >= {
            "locate-order",
            "get-contact",
            "do-refund",
        }


# ---------------------------------------------------------------------------
# create_rite / update_rite / delete_rite — the write surface.
# Spec: conceptual-workflows-rite-crud (create/edit/delete step sequences)
#       decisions-011-api-parity-with-cli (self-contained validated functions)
# These MUST fail until US-004 Green lands create_rite/update_rite/delete_rite.
# ---------------------------------------------------------------------------


def _dump(data):
    """Serialise a dict to YAML text (body source for create/update)."""
    import yaml

    return yaml.safe_dump(data, sort_keys=False)


# A schema-valid main rite as a parsed dict (single-step, straight conclusion).
CANONICAL_MAIN_RITE_DICT = {
    "id": "issue-refund",
    "title": "Issue a refund for a returned order",
    "summary": "Confirm the customer is reachable, then refund.",
    "trigger": "Customer requests a refund on a returned order.",
    "nodes": [
        {
            "id": "only-step",
            "do": "Find the order by id; confirm it is in 'returned' state.",
            "then": "refunded",
        }
    ],
    "conclusions": {
        "refunded": {
            "audience": "customer-care",
            "response": "Refund posted; share the transaction id.",
        }
    },
}

CANONICAL_SHARED_STEP_DICT = {
    "id": "read-contact-info",
    "title": "Read the user's contact information",
    "summary": "Read the user's contact info from admin.",
    "do": "Open the user profile in admin and report the contact info.",
}


def _drop_key(d, key):
    """Return a copy of dict *d* with *key* removed."""
    out = dict(d)
    out.pop(key, None)
    return out


def _rites_root(root):
    """Resolve rites_dir for the test project root."""
    from lore.paths import rites_dir

    return rites_dir(root)


class TestCreateRite:
    """create_rite validates name + schema pre-write, dup-detects, writes."""

    def test_create_main_returns_envelope_with_group(self, bare_lore_dir):
        # conceptual-workflows-rite-crud Create — envelope carries group (root → None)
        from lore.rite import create_rite

        out = create_rite(
            _rites_root(bare_lore_dir), "issue-refund", _dump(CANONICAL_MAIN_RITE_DICT)
        )
        assert out == {
            "id": "issue-refund",
            "kind": "main",
            "group": None,
            "filename": "issue-refund.yaml",
            "path": ".lore/rites/main/issue-refund.yaml",
        }
        assert out["group"] is None

    def test_create_main_writes_file(self, bare_lore_dir):
        # conceptual-workflows-rite-crud Create — body written under main/
        from lore.rite import create_rite

        create_rite(
            _rites_root(bare_lore_dir), "issue-refund", _dump(CANONICAL_MAIN_RITE_DICT)
        )
        assert (_rites_root(bare_lore_dir) / "main/issue-refund.yaml").is_file()

    def test_create_shared_writes_under_shared(self, bare_lore_dir):
        # conceptual-workflows-rite-crud Create — shared=True writes shared/, kind shared
        from lore.rite import create_rite

        out = create_rite(
            _rites_root(bare_lore_dir),
            "read-contact-info",
            _dump(CANONICAL_SHARED_STEP_DICT),
            shared=True,
        )
        assert out["kind"] == "shared"
        assert out["path"] == ".lore/rites/shared/read-contact-info.yaml"
        assert (_rites_root(bare_lore_dir) / "shared/read-contact-info.yaml").is_file()

    def test_create_invalid_name_raises(self, bare_lore_dir):
        # conceptual-workflows-rite-crud Name validation — invalid name rejected
        import pytest

        from lore.rite import RiteError, create_rite

        with pytest.raises(RiteError):
            create_rite(
                _rites_root(bare_lore_dir), "bad name", _dump(CANONICAL_MAIN_RITE_DICT)
            )

    def test_create_schema_invalid_body_raises_pre_write(self, bare_lore_dir):
        # conceptual-workflows-rite-crud Create step 3 — schema-invalid body rejected, not written
        import pytest

        from lore.rite import RiteError, create_rite

        with pytest.raises(RiteError):
            create_rite(
                _rites_root(bare_lore_dir),
                "ok",
                _dump(_drop_key(CANONICAL_MAIN_RITE_DICT, "nodes")),
            )
        assert not (_rites_root(bare_lore_dir) / "main/ok.yaml").exists()

    def test_create_cross_subfolder_dup_raises(self, bare_lore_dir):
        # conceptual-workflows-rite-crud Create step 4 — main/x + shared/x clash rejected
        import pytest

        from lore.rite import RiteError, create_rite

        create_rite(
            _rites_root(bare_lore_dir), "issue-refund", _dump(CANONICAL_MAIN_RITE_DICT)
        )
        with pytest.raises(RiteError, match="already exists"):
            create_rite(
                _rites_root(bare_lore_dir),
                "issue-refund",
                _dump({**CANONICAL_SHARED_STEP_DICT, "id": "issue-refund"}),
                shared=True,
            )


class TestUpdateRite:
    """update_rite refuses create-via-edit, re-validates, overwrites."""

    def test_update_not_found_raises(self, bare_lore_dir):
        # conceptual-workflows-rite-crud Edit step 1 — must already exist
        import pytest

        from lore.rite import RiteError, update_rite

        with pytest.raises(RiteError, match="not found"):
            update_rite(
                _rites_root(bare_lore_dir),
                "issue-refund",
                _dump(CANONICAL_MAIN_RITE_DICT),
            )

    def test_update_overwrites_and_returns_full_entity(self, bare_lore_dir):
        # conceptual-workflows-rite-crud Edit — overwrite in place, full parsed entity returned
        from lore.rite import create_rite, update_rite

        create_rite(
            _rites_root(bare_lore_dir), "issue-refund", _dump(CANONICAL_MAIN_RITE_DICT)
        )
        out = update_rite(
            _rites_root(bare_lore_dir),
            "issue-refund",
            _dump({**CANONICAL_MAIN_RITE_DICT, "summary": "U"}),
        )
        assert out["summary"] == "U"
        assert out["id"] == "issue-refund"

    def test_update_schema_invalid_body_raises(self, bare_lore_dir):
        # conceptual-workflows-rite-crud Edit step 3 — re-validate before write
        import pytest

        from lore.rite import RiteError, create_rite, update_rite

        create_rite(
            _rites_root(bare_lore_dir), "issue-refund", _dump(CANONICAL_MAIN_RITE_DICT)
        )
        with pytest.raises(RiteError):
            update_rite(
                _rites_root(bare_lore_dir),
                "issue-refund",
                _dump(_drop_key(CANONICAL_MAIN_RITE_DICT, "nodes")),
            )


class TestDeleteRite:
    """delete_rite soft-deletes via .yaml.deleted; not-found raises."""

    def test_delete_not_found_raises(self, bare_lore_dir):
        # conceptual-workflows-rite-crud Delete — absent rite raises
        import pytest

        from lore.rite import RiteError, delete_rite

        with pytest.raises(RiteError, match="not found"):
            delete_rite(_rites_root(bare_lore_dir), "issue-refund")

    def test_delete_returns_id_and_deleted_at(self, bare_lore_dir):
        # conceptual-workflows-rite-crud Delete — returns {id, deleted_at}
        from lore.rite import create_rite, delete_rite

        create_rite(
            _rites_root(bare_lore_dir), "issue-refund", _dump(CANONICAL_MAIN_RITE_DICT)
        )
        out = delete_rite(_rites_root(bare_lore_dir), "issue-refund")
        assert set(out) == {"id", "group", "deleted_at"}
        assert out["id"] == "issue-refund"
        assert out["group"] is None

    def test_delete_renames_to_yaml_deleted(self, bare_lore_dir):
        # conceptual-workflows-rite-crud Delete — soft-delete rename
        from lore.rite import create_rite, delete_rite

        create_rite(
            _rites_root(bare_lore_dir), "issue-refund", _dump(CANONICAL_MAIN_RITE_DICT)
        )
        delete_rite(_rites_root(bare_lore_dir), "issue-refund")
        assert (
            _rites_root(bare_lore_dir) / "main/issue-refund.yaml.deleted"
        ).is_file()
        assert not (_rites_root(bare_lore_dir) / "main/issue-refund.yaml").exists()

    def test_delete_shared(self, bare_lore_dir):
        # conceptual-workflows-rite-crud Delete — shared step soft-deleted under shared/
        from lore.rite import create_rite, delete_rite

        create_rite(
            _rites_root(bare_lore_dir),
            "read-contact-info",
            _dump(CANONICAL_SHARED_STEP_DICT),
            shared=True,
        )
        delete_rite(_rites_root(bare_lore_dir), "read-contact-info", shared=True)
        assert (
            _rites_root(bare_lore_dir) / "shared/read-contact-info.yaml.deleted"
        ).is_file()


# ---------------------------------------------------------------------------
# Recursive discovery + group derivation + globally-unique ids.
# Rites mirror the codex model: id is identity; subfolder path is a cosmetic
# group used for display/filter only (decisions-016).
# ---------------------------------------------------------------------------


def _seed_main_grouped_text(root, group, name, text):
    from lore.paths import rites_main_dir

    d = rites_main_dir(root).joinpath(*group.split("/"))
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.yaml").write_text(text, encoding="utf-8")


def _seed_shared_grouped_text(root, group, name, text):
    from lore.paths import rites_shared_dir

    d = rites_shared_dir(root).joinpath(*group.split("/"))
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.yaml").write_text(text, encoding="utf-8")


class TestScanRitesRecursive:
    """scan_rites recurses into subfolders and derives a group per record."""

    def test_discovers_rite_in_subfolder(self, tmp_path):
        from lore.paths import rites_dir
        from lore.rite import scan_rites

        _make_rite_dirs(tmp_path)
        _seed_main_grouped_text(
            tmp_path, "diagnostics/network", "deep", MAIN_RITE_YAML.format(id="deep")
        )
        ids = [r["id"] for r in scan_rites(rites_dir(tmp_path))]
        assert ids == ["deep"]

    def test_group_derived_from_path(self, tmp_path):
        from lore.paths import rites_dir
        from lore.rite import scan_rites

        _make_rite_dirs(tmp_path)
        _seed_main_grouped_text(
            tmp_path, "diagnostics/network", "deep", MAIN_RITE_YAML.format(id="deep")
        )
        rec = scan_rites(rites_dir(tmp_path))[0]
        assert rec["group"] == "diagnostics/network"

    def test_root_group_is_empty_string(self, tmp_path):
        from lore.paths import rites_dir
        from lore.rite import scan_rites

        _make_rite_dirs(tmp_path)
        _seed_main(tmp_path, ["flat"])
        rec = scan_rites(rites_dir(tmp_path))[0]
        assert rec["group"] == ""

    def test_sorted_by_group_then_id(self, tmp_path):
        from lore.paths import rites_dir
        from lore.rite import scan_rites

        _make_rite_dirs(tmp_path)
        _seed_main(tmp_path, ["z-root"])
        _seed_main_grouped_text(tmp_path, "aaa", "child", MAIN_RITE_YAML.format(id="child"))
        recs = scan_rites(rites_dir(tmp_path))
        assert [(r["group"], r["id"]) for r in recs] == [("", "z-root"), ("aaa", "child")]

    def test_shared_recurses_and_groups(self, tmp_path):
        from lore.paths import rites_dir
        from lore.rite import scan_rites

        _make_rite_dirs(tmp_path)
        _seed_shared_grouped_text(
            tmp_path, "io", "read-contact-info", SHARED_STEP_YAML.format(id="read-contact-info")
        )
        rec = scan_rites(rites_dir(tmp_path), shared=True)[0]
        assert rec["id"] == "read-contact-info"
        assert rec["group"] == "io"
        assert rec["summary"] == "Read and report the contact info."


class TestCreateRiteGroup:
    """create_rite places the file under the --group subpath and validates it."""

    def test_create_with_group_writes_under_subfolder(self, bare_lore_dir):
        from lore.rite import create_rite

        out = create_rite(
            _rites_root(bare_lore_dir),
            "issue-refund",
            _dump(CANONICAL_MAIN_RITE_DICT),
            group="diagnostics/network",
        )
        assert out["group"] == "diagnostics/network"
        assert out["path"] == ".lore/rites/main/diagnostics/network/issue-refund.yaml"
        assert (
            _rites_root(bare_lore_dir) / "main/diagnostics/network/issue-refund.yaml"
        ).is_file()

    def test_create_shared_with_group(self, bare_lore_dir):
        from lore.rite import create_rite

        out = create_rite(
            _rites_root(bare_lore_dir),
            "read-contact-info",
            _dump(CANONICAL_SHARED_STEP_DICT),
            shared=True,
            group="io",
        )
        assert out["path"] == ".lore/rites/shared/io/read-contact-info.yaml"

    def test_create_invalid_group_raises(self, bare_lore_dir):
        import pytest

        from lore.rite import RiteError, create_rite

        with pytest.raises(RiteError):
            create_rite(
                _rites_root(bare_lore_dir),
                "issue-refund",
                _dump(CANONICAL_MAIN_RITE_DICT),
                group="../escape",
            )


class TestIdUniquenessAcrossTree:
    """A duplicate id in two subfolders anywhere across main+shared is rejected."""

    def test_dup_id_across_subfolders_raises(self, bare_lore_dir):
        import pytest

        from lore.rite import RiteError, create_rite

        create_rite(
            _rites_root(bare_lore_dir),
            "issue-refund",
            _dump(CANONICAL_MAIN_RITE_DICT),
            group="aaa",
        )
        with pytest.raises(RiteError, match="already exists"):
            create_rite(
                _rites_root(bare_lore_dir),
                "issue-refund",
                _dump(CANONICAL_MAIN_RITE_DICT),
                group="bbb",
            )

    def test_dup_id_main_vs_shared_subfolders_raises(self, bare_lore_dir):
        import pytest

        from lore.rite import RiteError, create_rite

        create_rite(
            _rites_root(bare_lore_dir),
            "shared-x",
            _dump({**CANONICAL_SHARED_STEP_DICT, "id": "shared-x"}),
            shared=True,
            group="io",
        )
        with pytest.raises(RiteError, match="already exists"):
            create_rite(
                _rites_root(bare_lore_dir),
                "shared-x",
                _dump({**CANONICAL_MAIN_RITE_DICT, "id": "shared-x"}),
                group="ops",
            )


class TestReadRiteResolvesByIdAcrossTree:
    """read_rite resolves a bare id anywhere in the tree; use: resolves by id."""

    def test_show_finds_rite_in_subfolder(self, bare_lore_dir):
        from lore.paths import rites_dir
        from lore.rite import read_rite

        _seed_main_grouped_text(
            bare_lore_dir, "diagnostics/network", "issue-refund", CANONICAL_MAIN_RITE
        )
        _seed_shared_text(bare_lore_dir, "read-contact-info", CANONICAL_SHARED_STEP)
        rite = read_rite(rites_dir(bare_lore_dir), "issue-refund")
        assert rite["id"] == "issue-refund"

    def test_use_resolves_across_groups(self, bare_lore_dir):
        # main rite in one group; use: target shared step in a DIFFERENT group.
        from lore.paths import rites_dir
        from lore.rite import read_rite

        _seed_main_grouped_text(
            bare_lore_dir, "ops", "issue-refund", CANONICAL_MAIN_RITE
        )
        _seed_shared_grouped_text(
            bare_lore_dir, "io/contact", "read-contact-info", CANONICAL_SHARED_STEP
        )
        rite = read_rite(rites_dir(bare_lore_dir), "issue-refund")
        use_node = next(n for n in rite["nodes"] if n["id"] == "get-contact")
        assert use_node["step"]["id"] == "read-contact-info"


class TestUpdateDeleteResolveByIdInSubfolder:
    """update_rite / delete_rite locate the target file by id, recursively."""

    def test_update_in_subfolder(self, bare_lore_dir):
        from lore.paths import rites_dir
        from lore.rite import read_rite, update_rite

        _seed_main_grouped_text(
            bare_lore_dir, "diagnostics", "issue-refund", CANONICAL_MAIN_RITE
        )
        _seed_shared_text(bare_lore_dir, "read-contact-info", CANONICAL_SHARED_STEP)
        update_rite(
            _rites_root(bare_lore_dir),
            "issue-refund",
            _dump({**CANONICAL_MAIN_RITE_DICT, "summary": "updated"}),
        )
        rite = read_rite(rites_dir(bare_lore_dir), "issue-refund")
        assert rite["summary"] == "updated"
        # File stays in its original subfolder.
        assert (
            _rites_root(bare_lore_dir) / "main/diagnostics/issue-refund.yaml"
        ).is_file()

    def test_delete_in_subfolder_reports_group(self, bare_lore_dir):
        from lore.rite import delete_rite

        _seed_main_grouped_text(
            bare_lore_dir, "diagnostics/network", "issue-refund", CANONICAL_MAIN_RITE
        )
        out = delete_rite(_rites_root(bare_lore_dir), "issue-refund")
        assert out["group"] == "diagnostics/network"
        assert (
            _rites_root(bare_lore_dir)
            / "main/diagnostics/network/issue-refund.yaml.deleted"
        ).is_file()
