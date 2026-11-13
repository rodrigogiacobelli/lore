"""Small slice of the independent `lore init` QA matrix (scripts/qa_init_matrix.py).

Run the whole matrix with `python scripts/qa_init_matrix.py`; this slice keeps a
handful of scenarios in the normal suite.  Deselect with `-m "not qa_matrix"`.
"""
from __future__ import annotations

import importlib.util
import types
from pathlib import Path

import pytest

pytestmark = pytest.mark.qa_matrix

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("qa_init_matrix", ROOT / "scripts" / "qa_init_matrix.py")
qa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qa)  # type: ignore[union-attr]

SLICE = [
    r"^headless-default$",
    r"^cli\.m-SIG\.q\.w@claude\+agents-md$",
    r"^harness\.m-off\.noq\.now@claude\+agents-md$",
    r"^harness\.m-SIG\.q\.w@claude\+agents-md$",
    r"^switch\.cli-to-harness$",
    r"^migrate\.i15-all-harness$",
    r"^migrate\.leg-memory-cli$",
]


@pytest.mark.parametrize("pattern", SLICE)
def test_init_scenario(pattern: str, tmp_path: Path) -> None:
    oracle = qa.Oracle()
    scenarios = qa.build_scenarios(oracle, types.SimpleNamespace(only=pattern, random=0, seed=0))
    assert len(scenarios) == 1, f"{pattern} matched {len(scenarios)} scenarios"
    scenario, findings, _ = qa.run_scenario(oracle, scenarios[0], tmp_path, keep=False)
    fails = [f"{c}: {m}" for s, c, m in findings.items if s == "FAIL"]
    assert not fails, f"{scenario['name']}:\n" + "\n".join(fails[:25])
