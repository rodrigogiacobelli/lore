"""Unit tests for ``lore.frontmatter_edit.update_frontmatter_fields``.

Spec: ``transient-frontmatter-field-edit-spec`` Section D.

Red phase — every test below MUST fail until the new module lands.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml


# ---------------------------------------------------------------------------
# Fixtures — minimal on-disk seeds for each of the four kinds.
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    for sub in ("knights", "doctrines", "artifacts", "watchers"):
        (tmp_path / ".lore" / sub).mkdir(parents=True)
    return tmp_path


KNIGHT_BODY = (
    "# Heading\n"
    "\n"
    "Some prose.\n"
    "\n"
    "```python\n"
    "print('hi')\n"
    "```\n"
    "\n"
    "Trailing line.   \n"  # trailing whitespace preserved
)

KNIGHT_MD = (
    "---\n"
    "id: tester\n"
    "title: Tester\n"
    "summary: A test knight.\n"
    "---\n"
    + KNIGHT_BODY
)

ARTIFACT_BODY = (
    "Body of artifact.\n"
    "\n"
    "```yaml\n"
    "foo: bar\n"
    "```\n"
    "\n"
    "End.\n"
)

ARTIFACT_MD = (
    "---\n"
    "id: tmpl\n"
    "title: Template\n"
    "summary: A test artifact.\n"
    "---\n"
    + ARTIFACT_BODY
)

DOCTRINE_YAML = (
    "id: workflow\n"
    "title: Workflow\n"
    "summary: A doctrine.\n"
    "steps:\n"
    "  - id: s1\n"
    "    title: Step 1\n"
    "    type: human\n"
)

WATCHER_YAML = (
    "id: watch\n"
    "title: Watcher\n"
    "summary: A test watcher.\n"
    "watch_target:\n"
    "  - src/a.py\n"
    "  - src/b.py\n"
    "interval: on_commit\n"
    "action:\n"
    "  - bash: echo hi\n"
)


def _seed_knight(project_root: Path, name: str = "tester") -> Path:
    fp = project_root / ".lore" / "knights" / f"{name}.md"
    fp.write_text(KNIGHT_MD)
    return fp


def _seed_artifact(project_root: Path, name: str = "tmpl") -> Path:
    fp = project_root / ".lore" / "artifacts" / f"{name}.md"
    fp.write_text(ARTIFACT_MD)
    return fp


def _seed_doctrine(project_root: Path, name: str = "workflow") -> Path:
    fp = project_root / ".lore" / "doctrines" / f"{name}.yaml"
    fp.write_text(DOCTRINE_YAML)
    return fp


def _seed_watcher(project_root: Path, name: str = "watch") -> Path:
    fp = project_root / ".lore" / "watchers" / f"{name}.yaml"
    fp.write_text(WATCHER_YAML)
    return fp


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _split_frontmatter(text: str) -> tuple[dict, str]:
    parts = text.split("---", 2)
    assert len(parts) >= 3, "Expected markdown+frontmatter file"
    return yaml.safe_load(parts[1]), parts[2]


# ---------------------------------------------------------------------------
# 1) Knight: --set summary round-trips with body preservation
# ---------------------------------------------------------------------------


class TestKnightSet:
    def test_set_summary_round_trips_and_body_preserved(self, project_root):
        from lore.frontmatter_edit import update_frontmatter_fields

        fp = _seed_knight(project_root)
        _, original_body = _split_frontmatter(fp.read_text())

        result = update_frontmatter_fields(
            project_root,
            "knight",
            "tester",
            set_fields={"summary": "Updated summary."},
            unset_fields=None,
            add_to_list=None,
            remove_from_list=None,
        )
        assert result == {"id": "tester", "filename": "tester.md", "updated_at": None}

        meta, new_body = _split_frontmatter(fp.read_text())
        assert meta["summary"] == "Updated summary."
        # body must be byte-identical
        assert new_body == original_body


# ---------------------------------------------------------------------------
# 2) Doctrine: --set title round-trips; steps preserved
# ---------------------------------------------------------------------------


class TestDoctrineSet:
    def test_set_title_round_trips_and_steps_preserved(self, project_root):
        from lore.frontmatter_edit import update_frontmatter_fields

        fp = _seed_doctrine(project_root)
        result = update_frontmatter_fields(
            project_root,
            "doctrine",
            "workflow",
            set_fields={"title": "New Title"},
            unset_fields=None,
            add_to_list=None,
            remove_from_list=None,
        )
        assert result == {
            "id": "workflow",
            "filename": "workflow.yaml",
            "updated_at": None,
        }
        data = yaml.safe_load(fp.read_text())
        assert data["title"] == "New Title"
        assert data["steps"] == [{"id": "s1", "title": "Step 1", "type": "human"}]


# ---------------------------------------------------------------------------
# 3) Artifact: --set summary round-trips, body bit-identical via SHA
# ---------------------------------------------------------------------------


class TestArtifactSet:
    def test_set_summary_body_sha_identical(self, project_root):
        from lore.frontmatter_edit import update_frontmatter_fields

        fp = _seed_artifact(project_root)
        _, original_body = _split_frontmatter(fp.read_text())
        original_body_sha = hashlib.sha256(original_body.encode()).hexdigest()

        result = update_frontmatter_fields(
            project_root,
            "artifact",
            "tmpl",
            set_fields={"summary": "Updated."},
            unset_fields=None,
            add_to_list=None,
            remove_from_list=None,
        )
        assert result == {"id": "tmpl", "filename": "tmpl.md", "updated_at": None}

        meta, new_body = _split_frontmatter(fp.read_text())
        assert meta["summary"] == "Updated."
        assert hashlib.sha256(new_body.encode()).hexdigest() == original_body_sha


# ---------------------------------------------------------------------------
# 4) Watcher: --set interval to a valid enum value; counter-test invalid
# ---------------------------------------------------------------------------


class TestWatcherSetEnum:
    def test_set_interval_daily_succeeds(self, project_root):
        from lore.frontmatter_edit import update_frontmatter_fields

        fp = _seed_watcher(project_root)
        result = update_frontmatter_fields(
            project_root,
            "watcher",
            "watch",
            set_fields={"interval": "daily"},
            unset_fields=None,
            add_to_list=None,
            remove_from_list=None,
        )
        assert result == {"id": "watch", "filename": "watch.yaml", "updated_at": None}
        data = yaml.safe_load(fp.read_text())
        assert data["interval"] == "daily"

    def test_set_interval_invalid_raises_and_no_write(self, project_root):
        from lore.frontmatter_edit import update_frontmatter_fields

        fp = _seed_watcher(project_root)
        pre_sha = _sha(fp)
        with pytest.raises(ValueError):
            update_frontmatter_fields(
                project_root,
                "watcher",
                "watch",
                set_fields={"interval": "banana"},
                unset_fields=None,
                add_to_list=None,
                remove_from_list=None,
            )
        assert _sha(fp) == pre_sha


# ---------------------------------------------------------------------------
# 5) Watcher: --add / --remove watch_target list mutations + uniqueItems
# ---------------------------------------------------------------------------


class TestWatcherAddRemoveList:
    def test_add_and_remove_watch_target_round_trip(self, project_root):
        from lore.frontmatter_edit import update_frontmatter_fields

        fp = _seed_watcher(project_root)
        update_frontmatter_fields(
            project_root,
            "watcher",
            "watch",
            set_fields=None,
            unset_fields=None,
            add_to_list={"watch_target": ["src/x.py"]},
            remove_from_list=None,
        )
        update_frontmatter_fields(
            project_root,
            "watcher",
            "watch",
            set_fields=None,
            unset_fields=None,
            add_to_list={"watch_target": ["src/y.py"]},
            remove_from_list=None,
        )
        data = yaml.safe_load(fp.read_text())
        assert "src/x.py" in data["watch_target"]
        assert "src/y.py" in data["watch_target"]

        # remove src/x.py
        update_frontmatter_fields(
            project_root,
            "watcher",
            "watch",
            set_fields=None,
            unset_fields=None,
            add_to_list=None,
            remove_from_list={"watch_target": ["src/x.py"]},
        )
        data = yaml.safe_load(fp.read_text())
        assert "src/x.py" not in data["watch_target"]
        assert "src/y.py" in data["watch_target"]

    def test_idempotent_re_add_is_noop(self, project_root):
        from lore.frontmatter_edit import update_frontmatter_fields

        fp = _seed_watcher(project_root)
        # add src/y.py once, then again — uniqueItems means dup is silently ignored
        update_frontmatter_fields(
            project_root,
            "watcher",
            "watch",
            set_fields=None,
            unset_fields=None,
            add_to_list={"watch_target": ["src/y.py"]},
            remove_from_list=None,
        )
        data1 = yaml.safe_load(fp.read_text())
        len1 = len(data1["watch_target"])
        update_frontmatter_fields(
            project_root,
            "watcher",
            "watch",
            set_fields=None,
            unset_fields=None,
            add_to_list={"watch_target": ["src/y.py"]},
            remove_from_list=None,
        )
        data2 = yaml.safe_load(fp.read_text())
        assert len(data2["watch_target"]) == len1


# ---------------------------------------------------------------------------
# 6) Idempotent --unset of missing field
# ---------------------------------------------------------------------------


class TestIdempotentUnsetMissing:
    def test_unset_nonexistent_key_succeeds_byte_identical(self, project_root):
        from lore.frontmatter_edit import update_frontmatter_fields

        fp = _seed_knight(project_root)
        pre_sha = _sha(fp)
        result = update_frontmatter_fields(
            project_root,
            "knight",
            "tester",
            set_fields=None,
            unset_fields=["nonexistent_key"],
            add_to_list=None,
            remove_from_list=None,
        )
        assert result["id"] == "tester"
        # File rewrite may have different bytes (re-serialize), but semantic
        # frontmatter must be unchanged AND body byte-identical.
        meta, body = _split_frontmatter(fp.read_text())
        assert "nonexistent_key" not in meta
        assert meta["id"] == "tester"
        assert meta["title"] == "Tester"
        assert meta["summary"] == "A test knight."
        # Body must remain byte-identical
        _, original_body = _split_frontmatter(KNIGHT_MD)
        assert body == original_body
        # pre_sha reference kept for symmetry — not asserted (re-serialization
        # may change FM bytes even for no-op unset).
        _ = pre_sha


# ---------------------------------------------------------------------------
# 7) Idempotent --remove of value not in list
# ---------------------------------------------------------------------------


class TestIdempotentRemoveValueNotInList:
    def test_remove_value_not_in_list_succeeds_list_unchanged(self, project_root):
        from lore.frontmatter_edit import update_frontmatter_fields

        fp = _seed_watcher(project_root)
        result = update_frontmatter_fields(
            project_root,
            "watcher",
            "watch",
            set_fields=None,
            unset_fields=None,
            add_to_list=None,
            remove_from_list={"watch_target": ["src/never_added.py"]},
        )
        assert result["id"] == "watch"
        data = yaml.safe_load(fp.read_text())
        assert data["watch_target"] == ["src/a.py", "src/b.py"]


# ---------------------------------------------------------------------------
# 8) Schema invariant: --unset required field rejected, file untouched
# ---------------------------------------------------------------------------


class TestRejectsUnsetRequired:
    @pytest.mark.parametrize(
        "kind,name,seed",
        [
            ("knight", "tester", _seed_knight),
            ("doctrine", "workflow", _seed_doctrine),
            ("artifact", "tmpl", _seed_artifact),
            ("watcher", "watch", _seed_watcher),
        ],
    )
    def test_unset_id_rejected_file_untouched(self, project_root, kind, name, seed):
        from lore.frontmatter_edit import update_frontmatter_fields

        fp = seed(project_root)
        pre_sha = _sha(fp)
        with pytest.raises(ValueError) as exc:
            update_frontmatter_fields(
                project_root,
                kind,
                name,
                set_fields=None,
                unset_fields=["id"],
                add_to_list=None,
                remove_from_list=None,
            )
        assert "Missing required property 'id'" in str(exc.value)
        assert _sha(fp) == pre_sha


# ---------------------------------------------------------------------------
# 9) Schema invariant: --set unknown field rejected
# ---------------------------------------------------------------------------


class TestRejectsUnknownField:
    def test_set_unknown_field_on_knight_raises_and_no_write(self, project_root):
        from lore.frontmatter_edit import update_frontmatter_fields

        fp = _seed_knight(project_root)
        pre_sha = _sha(fp)
        with pytest.raises(ValueError) as exc:
            update_frontmatter_fields(
                project_root,
                "knight",
                "tester",
                set_fields={"bogus": "1"},
                unset_fields=None,
                add_to_list=None,
                remove_from_list=None,
            )
        assert "Unknown property 'bogus'" in str(exc.value)
        assert _sha(fp) == pre_sha


# ---------------------------------------------------------------------------
# 10) Type coercion — exercised via the CLI helper directly.
# Integer and boolean fields don't appear on the in-scope schemas; we
# unit-test the coercion helper directly with synthetic types instead.
# ---------------------------------------------------------------------------


class TestCoerceScalarForSchema:
    def test_coerce_string_passthrough(self):
        from lore.frontmatter_edit import _coerce_scalar_for_schema

        assert _coerce_scalar_for_schema("knight-frontmatter", "title", "hi") == "hi"

    def test_coerce_integer_from_string(self):
        # Synthetic test via dispatch on a known-int schema field — none on
        # in-scope kinds, so we call with a kind whose schema we mock via
        # monkeypatch of load_schema. Use a small ad-hoc strategy: rely on
        # implementation reading `schemas.load_schema`. Without an
        # in-scope int field we exercise the integer branch by patching.
        import lore.schemas as schemas_mod
        from lore.frontmatter_edit import _coerce_scalar_for_schema

        # Doctrine step priority is an integer but lives inside a structured
        # array. We can't reach it via top-level set anyway. Use a direct
        # patch of load_schema to inject a synthetic int-typed field.
        original = schemas_mod.load_schema

        def fake(kind):
            if kind == "synthetic-int":
                return {"properties": {"count": {"type": "integer"}}}
            return original(kind)

        schemas_mod.load_schema = fake
        try:
            assert _coerce_scalar_for_schema("synthetic-int", "count", "7") == 7
        finally:
            schemas_mod.load_schema = original

    def test_coerce_integer_bad_raises(self):
        import lore.schemas as schemas_mod
        from lore.frontmatter_edit import _coerce_scalar_for_schema

        original = schemas_mod.load_schema

        def fake(kind):
            if kind == "synthetic-int":
                return {"properties": {"count": {"type": "integer"}}}
            return original(kind)

        schemas_mod.load_schema = fake
        try:
            with pytest.raises(ValueError):
                _coerce_scalar_for_schema("synthetic-int", "count", "notanumber")
        finally:
            schemas_mod.load_schema = original

    def test_coerce_boolean(self):
        import lore.schemas as schemas_mod
        from lore.frontmatter_edit import _coerce_scalar_for_schema

        original = schemas_mod.load_schema

        def fake(kind):
            if kind == "synthetic-bool":
                return {"properties": {"flag": {"type": "boolean"}}}
            return original(kind)

        schemas_mod.load_schema = fake
        try:
            assert _coerce_scalar_for_schema("synthetic-bool", "flag", "true") is True
            assert _coerce_scalar_for_schema("synthetic-bool", "flag", "FALSE") is False
            with pytest.raises(ValueError):
                _coerce_scalar_for_schema("synthetic-bool", "flag", "maybe")
        finally:
            schemas_mod.load_schema = original

    def test_coerce_array_string_comma_split(self):
        from lore.frontmatter_edit import _coerce_scalar_for_schema

        # watcher watch_target is array-of-string. The CLI uses this for --set.
        out = _coerce_scalar_for_schema("watcher-yaml", "watch_target", "src/a.py, src/b.py")
        assert out == ["src/a.py", "src/b.py"]

    def test_coerce_structured_array_rejected(self):
        from lore.frontmatter_edit import _coerce_scalar_for_schema

        # watcher 'action' is array of structured objects — CLI rejection path.
        with pytest.raises(ValueError) as exc:
            _coerce_scalar_for_schema("watcher-yaml", "action", "anything")
        assert "structured items" in str(exc.value) or "structured" in str(exc.value)


# ---------------------------------------------------------------------------
# 11) Body byte preservation through full --set flow.
# ---------------------------------------------------------------------------


class TestBodyBytePreservation:
    @pytest.mark.parametrize(
        "kind,name,seed",
        [
            ("knight", "tester", _seed_knight),
            ("artifact", "tmpl", _seed_artifact),
        ],
    )
    def test_body_bytes_preserved_after_set(self, project_root, kind, name, seed):
        from lore.frontmatter_edit import update_frontmatter_fields

        fp = seed(project_root)
        _, original_body = _split_frontmatter(fp.read_text())
        update_frontmatter_fields(
            project_root,
            kind,
            name,
            set_fields={"title": "X"},
            unset_fields=None,
            add_to_list=None,
            remove_from_list=None,
        )
        _, new_body = _split_frontmatter(fp.read_text())
        assert new_body == original_body


# ---------------------------------------------------------------------------
# 12) Atomic write — no partial write on validation failure.
# ---------------------------------------------------------------------------


class TestAtomicNoPartialWriteOnFailure:
    def test_unset_required_no_replace_call_no_tmp_left(self, monkeypatch, project_root):
        import os

        from lore.frontmatter_edit import update_frontmatter_fields

        fp = _seed_knight(project_root)
        replace_calls = []
        original_replace = os.replace

        def counting_replace(src, dst):
            replace_calls.append((str(src), str(dst)))
            return original_replace(src, dst)

        monkeypatch.setattr(os, "replace", counting_replace)
        with pytest.raises(ValueError):
            update_frontmatter_fields(
                project_root,
                "knight",
                "tester",
                set_fields=None,
                unset_fields=["id"],
                add_to_list=None,
                remove_from_list=None,
            )
        assert replace_calls == []
        # No tmp files left behind
        tmps = [p for p in fp.parent.iterdir() if p.name != fp.name]
        assert tmps == []


# ---------------------------------------------------------------------------
# 13) No mutations supplied — rejected.
# ---------------------------------------------------------------------------


class TestNoMutationsSupplied:
    def test_all_none_raises(self, project_root):
        from lore.frontmatter_edit import update_frontmatter_fields

        _seed_knight(project_root)
        with pytest.raises(ValueError) as exc:
            update_frontmatter_fields(
                project_root,
                "knight",
                "tester",
                set_fields=None,
                unset_fields=None,
                add_to_list=None,
                remove_from_list=None,
            )
        assert "No frontmatter mutations" in str(exc.value)

    def test_all_empty_raises(self, project_root):
        from lore.frontmatter_edit import update_frontmatter_fields

        _seed_knight(project_root)
        with pytest.raises(ValueError):
            update_frontmatter_fields(
                project_root,
                "knight",
                "tester",
                set_fields={},
                unset_fields=[],
                add_to_list={},
                remove_from_list={},
            )


# ---------------------------------------------------------------------------
# 14) Entity not found — per kind.
# ---------------------------------------------------------------------------


class TestEntityNotFound:
    @pytest.mark.parametrize(
        "kind", ["knight", "doctrine", "artifact", "watcher"],
    )
    def test_ghost_name_raises(self, project_root, kind):
        from lore.frontmatter_edit import update_frontmatter_fields

        with pytest.raises(ValueError) as exc:
            update_frontmatter_fields(
                project_root,
                kind,
                "ghost",
                set_fields={"title": "X"},
                unset_fields=None,
                add_to_list=None,
                remove_from_list=None,
            )
        assert "not found" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# 15) Unknown kind — rejected.
# ---------------------------------------------------------------------------


class TestUnknownKind:
    def test_unknown_kind_raises(self, project_root):
        from lore.frontmatter_edit import update_frontmatter_fields

        with pytest.raises(ValueError) as exc:
            update_frontmatter_fields(
                project_root,
                "bogus-kind",
                "x",
                set_fields={"title": "X"},
                unset_fields=None,
                add_to_list=None,
                remove_from_list=None,
            )
        assert "Unknown kind" in str(exc.value)


# ---------------------------------------------------------------------------
# 16) API is exported.
# ---------------------------------------------------------------------------


class TestFacadeExport:
    def test_update_frontmatter_fields_in_api_all(self):
        from lore import api

        assert "update_frontmatter_fields" in api.__all__

    def test_update_frontmatter_fields_identity_reexport(self):
        from lore import api
        from lore.frontmatter_edit import update_frontmatter_fields

        assert api.update_frontmatter_fields is update_frontmatter_fields
