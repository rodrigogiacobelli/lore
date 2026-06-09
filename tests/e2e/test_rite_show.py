"""E2E tests for the rite show command (text mode and JSON mode).

Spec: conceptual-workflows-rite-show (lore codex show conceptual-workflows-rite-show)
Workflow: conceptual-workflows-error-handling

`lore rite show <id> [<id> ...]` renders a rite in full, inlining every
`use:`-referenced shared step FLAT (non-recursive) into one document. Multiple
ids are deduped (dict.fromkeys) and the command is fail-fast — zero partial
output if any id or any referenced shared step is missing. A bare shared-step
id renders the step alone. The JSON envelope attaches the resolved shared step
as a "step" key on the use:-node.

Per Click 8.3, stdout/stderr are read separately (no mix_stderr). Every test
MUST fail until US-003 Green lands `lore rite show`.
"""

from __future__ import annotations

import json
from pathlib import Path

from lore.cli import main


# ---------------------------------------------------------------------------
# Canonical fixtures (Tech Spec §Exact YAML schemas + story rendered output).
# ---------------------------------------------------------------------------

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

CANCEL_ORDER_RITE = """\
id: cancel-order
title: Cancel an order
summary: Cancel an order before it ships.
trigger: Customer requests a cancellation.
nodes:
  - id: only
    do: Cancel the order in the system.
    then: cancelled
conclusions:
  cancelled:
    audience: customer-care
    response: Order cancelled.
"""

CANONICAL_SHARED_STEP_YAML = """\
id: read-contact-info
title: Read the user's contact information
summary: Read the user's email, phone, and mailing address from admin.
do: |
  Open the user profile in admin. Read and report back:
    - email
    - phone
    - mailing address, with its last-confirmed date
"""

# The resolved shared-step object as it appears in JSON output.
CANONICAL_SHARED_STEP = {
    "id": "read-contact-info",
    "title": "Read the user's contact information",
    "summary": "Read the user's email, phone, and mailing address from admin.",
    "do": (
        "Open the user profile in admin. Read and report back:\n"
        "  - email\n"
        "  - phone\n"
        "  - mailing address, with its last-confirmed date\n"
    ),
}


def _seed_main(project_dir: Path, name: str, text: str) -> None:
    path = project_dir / ".lore" / "rites" / "main" / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_shared(project_dir: Path, name: str, text: str) -> None:
    path = project_dir / ".lore" / "rites" / "shared" / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _soft_delete(project_dir: Path, subfolder: str, name: str) -> None:
    src = project_dir / ".lore" / "rites" / subfolder / f"{name}.yaml"
    src.rename(src.with_suffix(".yaml.deleted"))


# ---------------------------------------------------------------------------
# Scenario 1: Show a main rite with an inlined shared step (text)
# conceptual-workflows-rite-show step 2 (inline use: steps, flat)
# ---------------------------------------------------------------------------


class TestShowMainRiteInlinesShared:
    def test_show_main_rite_inlines_shared(self, project_dir, runner):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE)
        _seed_shared(project_dir, "read-contact-info", CANONICAL_SHARED_STEP_YAML)
        result = runner.invoke(main, ["rite", "show", "issue-refund"])
        assert result.exit_code == 0
        assert "=== issue-refund ===" in result.stdout
        assert "# Issue a refund for a returned order" in result.stdout
        assert "Trigger: Customer requests a refund on a returned order." in result.stdout
        assert "Summary: Confirm the customer is reachable, then refund." in result.stdout
        assert (
            "[locate-order]  Find the order by id; confirm it is in 'returned' state."
            in result.stdout
        )
        assert "  -> get-contact" in result.stdout

    def test_show_inlines_use_node_body(self, project_dir, runner):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE)
        _seed_shared(project_dir, "read-contact-info", CANONICAL_SHARED_STEP_YAML)
        result = runner.invoke(main, ["rite", "show", "issue-refund"])
        assert result.exit_code == 0
        assert "[get-contact]  use: read-contact-info" in result.stdout
        # The shared step is inlined under its use:-node.
        assert (
            "    read-contact-info — Read the user's contact information"
            in result.stdout
        )
        assert "      Open the user profile in admin. Read and report back:" in result.stdout
        assert "        - email" in result.stdout
        assert "        - phone" in result.stdout

    def test_show_renders_fork_branches(self, project_dir, runner):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE)
        _seed_shared(project_dir, "read-contact-info", CANONICAL_SHARED_STEP_YAML)
        result = runner.invoke(main, ["rite", "show", "issue-refund"])
        assert result.exit_code == 0
        assert "[review-contact]  Decide whether contact details support a refund." in result.stdout
        assert (
            "  if email and a current mailing address are present -> do-refund"
            in result.stdout
        )
        assert (
            "  if anything is missing or the address looks stale -> request-update"
            in result.stdout
        )

    def test_show_renders_conclusion_targets_and_block(self, project_dir, runner):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE)
        _seed_shared(project_dir, "read-contact-info", CANONICAL_SHARED_STEP_YAML)
        result = runner.invoke(main, ["rite", "show", "issue-refund"])
        assert result.exit_code == 0
        assert "  -> (conclusion) refunded" in result.stdout
        assert "  -> (conclusion) contact-requested" in result.stdout
        assert "Conclusions:" in result.stdout
        assert "  refunded  (audience: customer-care)" in result.stdout
        assert "    Refund posted; share the transaction id." in result.stdout
        assert "  contact-requested  (audience: customer-care)" in result.stdout
        assert "    Refund held pending a contact-details update." in result.stdout


# ---------------------------------------------------------------------------
# Scenario 1b: show resolves a bare id recursively across subfolders, and
# use: resolves the shared step by id across groups (decisions-016).
# ---------------------------------------------------------------------------


class TestShowResolvesByIdAcrossTree:
    def _seed_grouped(self, project_dir, subfolder, name, text):
        path = project_dir / ".lore" / "rites" / subfolder / f"{name}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_show_finds_rite_in_subfolder(self, project_dir, runner):
        self._seed_grouped(
            project_dir, "main/diagnostics/network", "issue-refund", CANONICAL_MAIN_RITE
        )
        _seed_shared(project_dir, "read-contact-info", CANONICAL_SHARED_STEP_YAML)
        result = runner.invoke(main, ["rite", "show", "issue-refund"])
        assert result.exit_code == 0
        assert "=== issue-refund ===" in result.stdout

    def test_use_resolves_shared_step_across_groups(self, project_dir, runner):
        self._seed_grouped(project_dir, "main/ops", "issue-refund", CANONICAL_MAIN_RITE)
        self._seed_grouped(
            project_dir, "shared/io/contact", "read-contact-info", CANONICAL_SHARED_STEP_YAML
        )
        result = runner.invoke(main, ["--json", "rite", "show", "issue-refund"])
        assert result.exit_code == 0
        out = json.loads(result.stdout)
        node = next(n for n in out["rites"][0]["nodes"] if n["id"] == "get-contact")
        assert node["step"]["id"] == "read-contact-info"


# ---------------------------------------------------------------------------
# Scenario 2: Show multiple ids with === separators and dedup
# conceptual-workflows-rite-show step 1 (dict.fromkeys dedup) + step 3 (separators)
# ---------------------------------------------------------------------------


class TestShowMultiIdDedup:
    def test_show_multi_id_dedup(self, project_dir, runner):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE)
        _seed_shared(project_dir, "read-contact-info", CANONICAL_SHARED_STEP_YAML)
        _seed_main(project_dir, "cancel-order", CANCEL_ORDER_RITE)
        result = runner.invoke(
            main, ["rite", "show", "issue-refund", "cancel-order", "issue-refund"]
        )
        assert result.exit_code == 0
        assert result.stdout.count("=== issue-refund ===") == 1  # deduped
        assert "=== cancel-order ===" in result.stdout


# ---------------------------------------------------------------------------
# Scenario 3: JSON envelope with inlined step on use-node
# conceptual-workflows-rite-show step 2/4 (step key on use-node; fork then is a list)
# ---------------------------------------------------------------------------


class TestShowJsonStepOnUseNode:
    def test_show_json_envelope_shape(self, project_dir, runner):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE)
        _seed_shared(project_dir, "read-contact-info", CANONICAL_SHARED_STEP_YAML)
        result = runner.invoke(main, ["--json", "rite", "show", "issue-refund"])
        assert result.exit_code == 0
        out = json.loads(result.stdout)
        assert isinstance(out["rites"], list)
        assert out["rites"][0]["id"] == "issue-refund"

    def test_show_json_step_on_use_node(self, project_dir, runner):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE)
        _seed_shared(project_dir, "read-contact-info", CANONICAL_SHARED_STEP_YAML)
        result = runner.invoke(main, ["--json", "rite", "show", "issue-refund"])
        assert result.exit_code == 0
        out = json.loads(result.stdout)
        node = next(n for n in out["rites"][0]["nodes"] if n["id"] == "get-contact")
        assert node["use"] == "read-contact-info"
        assert node["then"] == "review-contact"
        assert node["step"] == CANONICAL_SHARED_STEP  # inlined, exact shape

    def test_show_json_fork_then_is_list_of_if_goto(self, project_dir, runner):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE)
        _seed_shared(project_dir, "read-contact-info", CANONICAL_SHARED_STEP_YAML)
        result = runner.invoke(main, ["--json", "rite", "show", "issue-refund"])
        assert result.exit_code == 0
        out = json.loads(result.stdout)
        fork = next(n for n in out["rites"][0]["nodes"] if n["id"] == "review-contact")
        assert isinstance(fork["then"], list)
        assert fork["then"][0]["goto"] == "do-refund"
        assert fork["then"][0]["if"] == "email and a current mailing address are present"


# ---------------------------------------------------------------------------
# Scenario 4: Bare shared-step id renders the step alone
# conceptual-workflows-rite-show step 1 (shared id resolvable) + decisions-016
# ---------------------------------------------------------------------------


class TestShowBareSharedStep:
    def test_show_bare_shared_step_text(self, project_dir, runner):
        _seed_shared(project_dir, "read-contact-info", CANONICAL_SHARED_STEP_YAML)
        txt = runner.invoke(main, ["rite", "show", "read-contact-info"])
        assert txt.exit_code == 0
        assert "read-contact-info" in txt.stdout
        assert "Read the user's contact information" in txt.stdout
        assert "Read the user's email, phone, and mailing address from admin." in txt.stdout

    def test_show_bare_shared_step_json(self, project_dir, runner):
        _seed_shared(project_dir, "read-contact-info", CANONICAL_SHARED_STEP_YAML)
        result = runner.invoke(main, ["--json", "rite", "show", "read-contact-info"])
        assert result.exit_code == 0
        j = json.loads(result.stdout)
        assert j["rites"][0] == CANONICAL_SHARED_STEP  # bare shared-step object inside rites


# ---------------------------------------------------------------------------
# Scenario 5: Rite not found (fail-fast)
# conceptual-workflows-rite-show step 1 + conceptual-workflows-error-handling
# ---------------------------------------------------------------------------


class TestShowNotFoundFailFast:
    def test_show_not_found_text(self, project_dir, runner):
        r = runner.invoke(main, ["rite", "show", "nope"])
        assert r.exit_code == 1
        assert r.stderr.strip() == 'Rite "nope" not found'

    def test_show_not_found_json(self, project_dir, runner):
        r = runner.invoke(main, ["--json", "rite", "show", "nope"])
        assert r.exit_code == 1
        assert json.loads(r.stderr) == {"error": 'Rite "nope" not found'}

    def test_show_soft_deleted_text(self, project_dir, runner):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE)
        _soft_delete(project_dir, "main", "issue-refund")
        d = runner.invoke(main, ["rite", "show", "issue-refund"])
        assert d.exit_code == 1
        assert 'Rite "issue-refund" not found (deleted on' in d.stderr

    def test_show_soft_deleted_json_has_deleted_at(self, project_dir, runner):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE)
        _soft_delete(project_dir, "main", "issue-refund")
        d = runner.invoke(main, ["--json", "rite", "show", "issue-refund"])
        assert d.exit_code == 1
        err = json.loads(d.stderr)
        assert "deleted_at" in err
        assert 'not found (deleted on' in err["error"]

    def test_show_multi_id_one_missing_no_partial_output(self, project_dir, runner):
        _seed_main(project_dir, "cancel-order", CANCEL_ORDER_RITE)
        m = runner.invoke(main, ["rite", "show", "cancel-order", "nope"])
        assert m.exit_code == 1
        assert "=== cancel-order ===" not in m.stdout  # fail-fast: zero partial output
        assert m.stderr.strip() == 'Rite "nope" not found'


# ---------------------------------------------------------------------------
# Scenario 6: Dangling use: at show time
# conceptual-workflows-rite-show step 2 + conceptual-workflows-error-handling
# ---------------------------------------------------------------------------


class TestShowDanglingUse:
    def test_show_dangling_use_text(self, project_dir, runner):
        # use: read-contact-info, but shared/ is empty
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE)
        r = runner.invoke(main, ["rite", "show", "issue-refund"])
        assert r.exit_code == 1
        assert (
            r.stderr.strip()
            == 'Rite "issue-refund": shared step "read-contact-info" not found'
        )

    def test_show_dangling_use_json(self, project_dir, runner):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE)
        j = runner.invoke(main, ["--json", "rite", "show", "issue-refund"])
        assert j.exit_code == 1
        assert json.loads(j.stderr) == {
            "error": 'Rite "issue-refund": shared step "read-contact-info" not found'
        }

    def test_show_dangling_use_no_partial_output(self, project_dir, runner):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE)
        r = runner.invoke(main, ["rite", "show", "issue-refund"])
        assert r.exit_code == 1
        assert "=== issue-refund ===" not in r.stdout  # fail-fast
