"""Unit tests for scripts/check_seed_gates.py — the release pre-flight for seed gates.

The script reads prose, so these tests feed it files authored here: nothing
asserts what a shipped seed says (decisions-006-no-seed-content-tests). Running
it over the shipped seeds is the release pre-flight, not a test.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from lore import init

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_seed_gates.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_seed_gates", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _world(tmp_path: Path, text: str) -> Path:
    seed = tmp_path / "doctrines" / "demo" / "mission.md"
    seed.parent.mkdir(parents=True)
    seed.write_text(text, encoding="utf-8")
    return tmp_path


def _gate(*requires: str) -> init._SeedGate:
    return init._SeedGate("doctrines", "demo/", requires)


class TestPhrasesIn:
    def test_prose_and_code_are_both_read(self):
        script = _load()
        known = {"done": 1, "codex show": 1, "health --scope voice": 1}
        found = script.phrases_in(
            "When finished run lore done. Then `lore codex show x` and lore health --scope voice.",
            known,
        )
        assert found == {"done", "codex show", "health --scope voice"}

    def test_a_phrase_with_no_grant_row_is_ignored(self):
        script = _load()
        assert script.phrases_in("the lore of the land", {"done": 1}) == set()


class TestCheck:
    def test_a_capability_the_gate_does_not_imply_is_a_problem(self, tmp_path):
        script = _load()
        root = _world(tmp_path, "Run `lore codex map x` and lore done.")
        problems, _ = script.check(gates=[_gate("watchers")], root=root)
        assert len(problems) == 2
        assert any("codex map" in line and "cap:memory-graph" in line for line in problems)
        assert any("lore done" in line for line in problems)

    def test_a_gate_that_implies_them_is_clean(self, tmp_path):
        script = _load()
        root = _world(tmp_path, "Run `lore codex map x` and lore done.")
        problems, _ = script.check(
            gates=[_gate("quests", "cap:memory-graph")], root=root
        )
        assert problems == []

    def test_a_route_level_mention_is_counted_not_reported_as_a_problem(self, tmp_path):
        script = _load()
        root = _world(tmp_path, "Read it with `lore codex show x`.")
        problems, routes = script.check(gates=[_gate("watchers")], root=root)
        assert problems == []
        assert routes and "memory.cli" in routes[0]

    def test_a_core_row_is_ungated_by_ruling_and_only_counted(self, tmp_path):
        script = _load()
        root = _world(tmp_path, "Run lore done, then `lore codex map x`.")
        problems, routes = script.check(gates=[_gate()], root=root)
        assert problems == []
        assert len(routes) == 2

    def test_a_memory_row_may_describe_the_memory_opt_ins(self, tmp_path):
        script = _load()
        root = _world(tmp_path, "Try `lore codex map x` and `lore codex search y`.")
        problems, routes = script.check(gates=[_gate("memory")], root=root)
        assert problems == []
        assert len(routes) == 2

    def test_a_memory_row_may_not_speak_of_another_feature(self, tmp_path):
        script = _load()
        root = _world(tmp_path, "Finish with lore done.")
        problems, _ = script.check(gates=[_gate("memory")], root=root)
        assert len(problems) == 1
