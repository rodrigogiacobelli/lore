"""E2E tests for rite storage seeding and schema validation.

Spec: conceptual-workflows-rite-crud (lore codex show conceptual-workflows-rite-crud)
User story: transient-rites-us-1 (lore codex show transient-rites-us-1)

Covers the US-001 E2E scenarios:
  1. `lore init` seeds .lore/rites/main/ + .lore/rites/shared/; health is green.
  2. A valid main rite passes `lore health --scope schemas`.
  3. A main rite missing a required field fails schema validation.
  4. A pure shared step passes schema validation.
  5. A shared step carrying a branching key (`then`) is rejected.

Schema-violation scenarios assert the multi-line ERROR block format defined in
conceptual-workflows-health. Per Click 8.3, stdout/stderr are read separately
(no mix_stderr). Every test MUST fail until US-001 Green lands.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from lore.cli import main
from lore.schemas import load_schema


# Canonical design-doc fixtures (Tech Spec §Exact YAML schemas).
CANONICAL_MAIN_RITE_YAML = """\
id: issue-refund
title: Issue a refund for a returned order
summary: Confirm the customer is reachable, then refund.
trigger: Customer requests a refund on a returned order.
nodes:
  - id: only-step
    do: Find the order by id; confirm it is in 'returned' state.
    then: refunded
conclusions:
  refunded:
    audience: customer-care
    response: Refund posted; share the transaction id.
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


def _write_rite(project_dir: Path, subfolder: str, name: str, text: str) -> None:
    path = project_dir / ".lore" / "rites" / subfolder / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Scenario 1: lore init seeds the rite directories (dir existence + green health)
# ADR-006-no-seed-content — no assertion on seed file content.
# ---------------------------------------------------------------------------


class TestInitSeedsRiteDirs:
    def test_init_seeds_main_and_shared_dirs(self, project_dir):
        # transient-rites-us-1 Scenario 1 — both subfolders exist after init
        assert (project_dir / ".lore" / "rites" / "main").is_dir()
        assert (project_dir / ".lore" / "rites" / "shared").is_dir()

    def test_health_green_after_init(self, runner, project_dir):
        # transient-rites-us-1 Scenario 1 — green health, exit 0, no content assert.
        # Pin the rites schema kinds as registered so this scenario is not a
        # vacuous green: a fresh project must stay green WITH the rite kinds live.
        assert load_schema("main-rite")["$id"] == "lore://schemas/main-rite"
        assert load_schema("shared-step")["$id"] == "lore://schemas/shared-step"
        result = runner.invoke(main, ["health"])
        assert result.exit_code == 0, result.stdout
        assert "Health check passed. No issues found." in result.stdout
        assert "Schema validation: 0 errors" in result.stdout


# ---------------------------------------------------------------------------
# Scenario 2: a valid main rite passes schema validation
# ---------------------------------------------------------------------------


class TestValidMainRiteSchemaClean:
    def test_valid_main_rite_schema_clean(self, runner, project_dir):
        # transient-rites-us-1 Scenario 2 — exit 0, ends with 0 errors.
        # main-rite kind must be registered (else the file is silently ignored
        # and this would be a vacuous green).
        assert load_schema("main-rite")["$id"] == "lore://schemas/main-rite"
        _write_rite(project_dir, "main", "issue-refund", CANONICAL_MAIN_RITE_YAML)
        result = runner.invoke(main, ["health", "--scope", "schemas"])
        assert result.exit_code == 0, result.stdout
        assert result.stdout.rstrip().endswith("Schema validation: 0 errors")


# ---------------------------------------------------------------------------
# Scenario 3: a main rite missing a required field fails schema validation
# ---------------------------------------------------------------------------


class TestMainRiteMissingRequiredField:
    def test_missing_conclusions_emits_error_block(self, runner, project_dir):
        # transient-rites-us-1 Scenario 3 — multi-line ERROR block + 1 error summary
        broken = "\n".join(
            line
            for line in CANONICAL_MAIN_RITE_YAML.splitlines()
            if not line.startswith("conclusions")
            and not line.startswith("  refunded")
            and not line.startswith("    audience")
            and not line.startswith("    response")
        ) + "\n"
        _write_rite(project_dir, "main", "broken", broken)

        result = runner.invoke(main, ["health", "--scope", "schemas"])

        assert result.exit_code == 1, result.stdout
        assert "ERROR .lore/rites/main/broken.yaml" in result.stdout
        assert "  kind: main-rite" in result.stdout
        assert "  schema: lore://schemas/main-rite" in result.stdout
        assert "  rule: required" in result.stdout
        assert "  path:" in result.stdout
        assert "  message:" in result.stdout
        assert "Schema validation: 1 error" in result.stdout


# ---------------------------------------------------------------------------
# Scenario 4: a shared step is a pure procedure
# ---------------------------------------------------------------------------


class TestPureSharedStepSchemaClean:
    def test_pure_shared_step_schema_clean(self, runner, project_dir):
        # transient-rites-us-1 Scenario 4 — id/title/do only validates clean.
        # shared-step kind must be registered (else vacuous green).
        assert load_schema("shared-step")["$id"] == "lore://schemas/shared-step"
        _write_rite(
            project_dir, "shared", "read-contact-info", CANONICAL_SHARED_STEP_YAML
        )
        result = runner.invoke(main, ["health", "--scope", "schemas"])
        assert result.exit_code == 0, result.stdout
        assert result.stdout.rstrip().endswith("Schema validation: 0 errors")


# ---------------------------------------------------------------------------
# Scenario 5: a shared step with branching/conclusions is rejected
# ---------------------------------------------------------------------------


class TestSharedStepWithThenRejected:
    def test_shared_step_with_then_rejected(self, runner, project_dir):
        # transient-rites-us-1 Scenario 5 — additionalProperties at /then
        bad = CANONICAL_SHARED_STEP_YAML + "then: next-thing\n"
        _write_rite(project_dir, "shared", "read-contact-info", bad)

        result = runner.invoke(main, ["health", "--scope", "schemas"])

        assert result.exit_code == 1, result.stdout
        assert "ERROR .lore/rites/shared/read-contact-info.yaml" in result.stdout
        assert "  kind: shared-step" in result.stdout
        assert "  schema: lore://schemas/shared-step" in result.stdout
        assert "  rule: additionalProperties" in result.stdout
        assert "  path: /then" in result.stdout
        assert (
            "  message: Unknown property 'then' — allowed keys are id, title, summary, do."
            in result.stdout
        )
        assert "Schema validation: 1 error" in result.stdout


# ---------------------------------------------------------------------------
# Scenario 6: a shared step missing summary is rejected (tech-arch-frontmatter)
# ---------------------------------------------------------------------------


class TestSharedStepMissingSummaryRejected:
    def test_shared_step_without_summary_rejected(self, runner, project_dir):
        bad = "\n".join(
            line
            for line in CANONICAL_SHARED_STEP_YAML.splitlines()
            if not line.startswith("summary:")
        ) + "\n"
        _write_rite(project_dir, "shared", "read-contact-info", bad)

        result = runner.invoke(main, ["health", "--scope", "schemas"])

        assert result.exit_code == 1, result.stdout
        assert "ERROR .lore/rites/shared/read-contact-info.yaml" in result.stdout
        assert "  kind: shared-step" in result.stdout
        assert "  rule: required" in result.stdout
        assert "Schema validation: 1 error" in result.stdout

    def test_shared_step_with_summary_validates_clean(self, runner, project_dir):
        _write_rite(
            project_dir, "shared", "read-contact-info", CANONICAL_SHARED_STEP_YAML
        )
        result = runner.invoke(main, ["health", "--scope", "schemas"])
        assert result.exit_code == 0, result.stdout
        assert result.stdout.rstrip().endswith("Schema validation: 0 errors")


# ===========================================================================
# Write surface — lore rite new / edit / delete (US-004)
# Spec: conceptual-workflows-rite-crud (Create / Edit / Delete step sequences)
#       conceptual-workflows-error-handling (exit codes, {"error": ...} to stderr)
# Click 8.3: stdout/stderr read separately (no mix_stderr).
# These MUST fail until US-004 Green lands new/edit/delete.
# ===========================================================================


# Canonical parsed-dict fixtures (Tech Spec §Exact YAML schemas).
CANONICAL_MAIN_RITE = {
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

CANONICAL_SHARED_STEP = {
    "id": "read-contact-info",
    "title": "Read the user's contact information",
    "summary": "Read the user's contact info from admin.",
    "do": "Open the user profile in admin and report the contact info.",
}


def _dump(data: dict) -> str:
    return yaml.safe_dump(data, sort_keys=False)


def _write_yaml(path: Path, data: dict) -> Path:
    path.write_text(_dump(data), encoding="utf-8")
    return path


def _drop_key(d: dict, key: str) -> dict:
    out = dict(d)
    out.pop(key, None)
    return out


def _seed_main(project_dir: Path, name: str, data: dict) -> None:
    _write_rite(project_dir, "main", name, _dump(data))


def _seed_shared(project_dir: Path, name: str, data: dict) -> None:
    _write_rite(project_dir, "shared", name, _dump(data))


# ---------------------------------------------------------------------------
# Scenario 1: Create a main rite from a file
# ---------------------------------------------------------------------------


class TestRiteNewMainFromFile:
    """new <name> --from <file> creates a main rite; envelope omits group."""

    def test_new_main_stdout_and_exit(self, runner, project_dir, tmp_path):
        body = _write_yaml(tmp_path / "r.yaml", CANONICAL_MAIN_RITE)
        r = runner.invoke(main, ["rite", "new", "issue-refund", "--from", str(body)])
        assert r.exit_code == 0
        assert r.stdout.strip() == "Created rite main/issue-refund.yaml"

    def test_new_main_file_written(self, runner, project_dir, tmp_path):
        body = _write_yaml(tmp_path / "r.yaml", CANONICAL_MAIN_RITE)
        runner.invoke(main, ["rite", "new", "issue-refund", "--from", str(body)])
        assert (project_dir / ".lore/rites/main/issue-refund.yaml").exists()

    def test_new_main_json_envelope_carries_group(self, runner, project_dir, tmp_path):
        body = _write_yaml(tmp_path / "r.yaml", CANONICAL_MAIN_RITE)
        r = runner.invoke(
            main, ["--json", "rite", "new", "x", "--from", str(body)]
        )
        j = json.loads(r.stdout)
        assert j == {
            "id": "x",
            "kind": "main",
            "group": None,
            "filename": "x.yaml",
            "path": ".lore/rites/main/x.yaml",
        }
        assert j["group"] is None

    def test_new_main_with_group_writes_subfolder(self, runner, project_dir, tmp_path):
        body = _write_yaml(tmp_path / "r.yaml", CANONICAL_MAIN_RITE)
        r = runner.invoke(
            main,
            ["--json", "rite", "new", "x", "--group", "diagnostics/network", "--from", str(body)],
        )
        j = json.loads(r.stdout)
        assert j["group"] == "diagnostics/network"
        assert j["path"] == ".lore/rites/main/diagnostics/network/x.yaml"
        assert (
            project_dir / ".lore/rites/main/diagnostics/network/x.yaml"
        ).exists()

    def test_new_main_group_stdout(self, runner, project_dir, tmp_path):
        body = _write_yaml(tmp_path / "r.yaml", CANONICAL_MAIN_RITE)
        r = runner.invoke(
            main,
            ["rite", "new", "x", "--group", "diagnostics", "--from", str(body)],
        )
        assert r.exit_code == 0
        assert r.stdout.strip() == "Created rite main/diagnostics/x.yaml"


# ---------------------------------------------------------------------------
# Scenario 2: Create a shared step from stdin
# ---------------------------------------------------------------------------


class TestRiteNewSharedFromStdin:
    """new <name> --shared (body on stdin) creates a shared step."""

    def test_new_shared_stdout_and_exit(self, runner, project_dir):
        r = runner.invoke(
            main,
            ["rite", "new", "read-contact-info", "--shared"],
            input=_dump(CANONICAL_SHARED_STEP),
        )
        assert r.exit_code == 0
        assert r.stdout.strip() == "Created shared step shared/read-contact-info.yaml"

    def test_new_shared_json_kind_and_path(self, runner, project_dir):
        r = runner.invoke(
            main,
            ["--json", "rite", "new", "s2", "--shared"],
            input=_dump(CANONICAL_SHARED_STEP),
        )
        j = json.loads(r.stdout)
        assert j["kind"] == "shared"
        assert j["path"] == ".lore/rites/shared/s2.yaml"


# ---------------------------------------------------------------------------
# Scenario 3: new error table
# ---------------------------------------------------------------------------


class TestRiteNewErrors:
    """The new error table: stderr message + exit 1; JSON {"error": ...}."""

    def test_invalid_name(self, runner, project_dir, tmp_path):
        good = _write_yaml(tmp_path / "r.yaml", CANONICAL_MAIN_RITE)
        r = runner.invoke(main, ["rite", "new", "bad name", "--from", str(good)])
        assert r.exit_code == 1
        assert r.stderr.strip() == (
            "Invalid name: must be alphanumeric, hyphens, underscores only."
        )

    def test_duplicate_id(self, runner, project_dir, tmp_path):
        good = _write_yaml(tmp_path / "r.yaml", CANONICAL_MAIN_RITE)
        runner.invoke(main, ["rite", "new", "issue-refund", "--from", str(good)])
        r = runner.invoke(main, ["rite", "new", "issue-refund", "--from", str(good)])
        assert r.exit_code == 1
        assert r.stderr.strip() == 'Rite "issue-refund" already exists.'

    def test_duplicate_cross_subfolder(self, runner, project_dir, tmp_path):
        # main/issue-refund + shared/issue-refund clash — flat namespace
        good = _write_yaml(tmp_path / "r.yaml", CANONICAL_MAIN_RITE)
        runner.invoke(main, ["rite", "new", "issue-refund", "--from", str(good)])
        step = _write_yaml(
            tmp_path / "s.yaml", {**CANONICAL_SHARED_STEP, "id": "issue-refund"}
        )
        r = runner.invoke(
            main, ["rite", "new", "issue-refund", "--shared", "--from", str(step)]
        )
        assert r.exit_code == 1
        assert r.stderr.strip() == 'Rite "issue-refund" already exists.'

    def test_from_file_missing(self, runner, project_dir):
        r = runner.invoke(main, ["rite", "new", "ok", "--from", "/nope.yaml"])
        assert r.exit_code == 1
        assert r.stderr.strip() == "File not found: /nope.yaml"

    def test_empty_stdin(self, runner, project_dir):
        r = runner.invoke(main, ["rite", "new", "ok"], input="")
        assert r.exit_code == 1
        assert r.stderr.strip() == "No content provided on stdin."

    def test_schema_invalid_body(self, runner, project_dir, tmp_path):
        bad = _write_yaml(
            tmp_path / "bad.yaml", _drop_key(CANONICAL_MAIN_RITE, "conclusions")
        )
        r = runner.invoke(main, ["rite", "new", "ok2", "--from", str(bad)])
        assert r.exit_code == 1
        assert r.stderr.strip().startswith("Invalid rite:")

    def test_shared_step_with_branching_key(self, runner, project_dir, tmp_path):
        sbad = _write_yaml(tmp_path / "sbad.yaml", {**CANONICAL_SHARED_STEP, "then": "x"})
        r = runner.invoke(
            main, ["rite", "new", "ok3", "--shared", "--from", str(sbad)]
        )
        assert r.exit_code == 1
        assert r.stderr.strip() == (
            "Invalid shared step: additionalProperties at /then — unknown key"
        )

    def test_json_error_envelope_to_stderr(self, runner, project_dir):
        r = runner.invoke(
            main, ["--json", "rite", "new", "ok", "--from", "/nope.yaml"]
        )
        assert json.loads(r.stderr) == {"error": "File not found: /nope.yaml"}


# ---------------------------------------------------------------------------
# Scenario 4: Edit replaces an existing rite
# ---------------------------------------------------------------------------


class TestRiteEditReplace:
    """edit <name> --from <file> overwrites in place; JSON is full entity."""

    def test_edit_main_stdout_and_exit(self, runner, project_dir, tmp_path):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE)
        repl = _write_yaml(
            tmp_path / "r2.yaml", {**CANONICAL_MAIN_RITE, "summary": "Updated."}
        )
        r = runner.invoke(main, ["rite", "edit", "issue-refund", "--from", str(repl)])
        assert r.exit_code == 0
        assert r.stdout.strip() == "Updated rite issue-refund"

    def test_edit_main_json_full_entity(self, runner, project_dir, tmp_path):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE)
        repl = _write_yaml(
            tmp_path / "r2.yaml", {**CANONICAL_MAIN_RITE, "summary": "Updated."}
        )
        r = runner.invoke(
            main, ["--json", "rite", "edit", "issue-refund", "--from", str(repl)]
        )
        j = json.loads(r.stdout)
        assert j["id"] == "issue-refund"
        assert j["summary"] == "Updated."

    def test_edit_shared_stdout(self, runner, project_dir, tmp_path):
        _seed_shared(project_dir, "read-contact-info", CANONICAL_SHARED_STEP)
        s = _write_yaml(tmp_path / "s.yaml", {**CANONICAL_SHARED_STEP, "title": "T"})
        r = runner.invoke(
            main, ["rite", "edit", "read-contact-info", "--shared", "--from", str(s)]
        )
        assert r.exit_code == 0
        assert r.stdout.strip() == "Updated shared step read-contact-info"


# ---------------------------------------------------------------------------
# Scenario 5: Edit error paths
# ---------------------------------------------------------------------------


class TestRiteEditErrors:
    """edit not-found (exit 1), no-source UsageError (exit 2), schema-invalid (exit 1)."""

    def test_edit_not_found(self, runner, project_dir, tmp_path):
        good = _write_yaml(tmp_path / "r.yaml", CANONICAL_MAIN_RITE)
        r = runner.invoke(main, ["rite", "edit", "nope", "--from", str(good)])
        assert r.exit_code == 1
        assert r.stderr.strip() == 'Rite "nope" not found'

    def test_edit_no_source_raises_usage_error_exit_2(self, runner, project_dir):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE)
        r = runner.invoke(main, ["rite", "edit", "issue-refund"], input="")
        assert r.exit_code == 2
        assert (
            "No content provided: pass --from <path> or pipe via stdin." in r.stderr
        )

    def test_edit_schema_invalid_body(self, runner, project_dir, tmp_path):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE)
        bad = _write_yaml(
            tmp_path / "bad.yaml", _drop_key(CANONICAL_MAIN_RITE, "nodes")
        )
        r = runner.invoke(main, ["rite", "edit", "issue-refund", "--from", str(bad)])
        assert r.exit_code == 1
        assert r.stderr.strip().startswith("Invalid rite:")


# ---------------------------------------------------------------------------
# Scenario 6: Delete soft-deletes
# ---------------------------------------------------------------------------


class TestRiteDeleteSoft:
    """delete <name> renames to .yaml.deleted; JSON {id, deleted_at}; invisible."""

    def test_delete_main_stdout_and_exit(self, runner, project_dir):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE)
        r = runner.invoke(main, ["rite", "delete", "issue-refund"])
        assert r.exit_code == 0
        assert r.stdout.strip() == "Deleted rite issue-refund"

    def test_delete_renames_to_yaml_deleted(self, runner, project_dir):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE)
        runner.invoke(main, ["rite", "delete", "issue-refund"])
        assert (
            project_dir / ".lore/rites/main/issue-refund.yaml.deleted"
        ).exists()
        assert not (project_dir / ".lore/rites/main/issue-refund.yaml").exists()

    def test_delete_json_id_group_and_deleted_at(self, runner, project_dir):
        _seed_main(project_dir, "other", {**CANONICAL_MAIN_RITE, "id": "other"})
        r = runner.invoke(main, ["--json", "rite", "delete", "other"])
        j = json.loads(r.stdout)
        assert set(j) == {"id", "group", "deleted_at"}
        assert j["id"] == "other"
        assert j["group"] is None

    def test_delete_shared_stdout(self, runner, project_dir):
        _seed_shared(project_dir, "read-contact-info", CANONICAL_SHARED_STEP)
        r = runner.invoke(main, ["rite", "delete", "read-contact-info", "--shared"])
        assert r.exit_code == 0
        assert r.stdout.strip() == "Deleted shared step read-contact-info"

    def test_delete_resolves_rite_in_subfolder(self, runner, project_dir):
        _write_rite(
            project_dir, "main/diagnostics/network", "issue-refund",
            _dump(CANONICAL_MAIN_RITE),
        )
        r = runner.invoke(main, ["--json", "rite", "delete", "issue-refund"])
        j = json.loads(r.stdout)
        assert j["group"] == "diagnostics/network"
        assert (
            project_dir
            / ".lore/rites/main/diagnostics/network/issue-refund.yaml.deleted"
        ).exists()

    def test_delete_invisible_to_list(self, runner, project_dir):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE)
        runner.invoke(main, ["rite", "delete", "issue-refund"])
        lst = runner.invoke(main, ["rite", "list"])
        assert "issue-refund" not in lst.stdout

    def test_delete_invisible_to_show(self, runner, project_dir):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE)
        runner.invoke(main, ["rite", "delete", "issue-refund"])
        show = runner.invoke(main, ["rite", "show", "issue-refund"])
        assert show.exit_code == 1


# ---------------------------------------------------------------------------
# Scenario 7: Delete not-found / already-deleted
# ---------------------------------------------------------------------------


class TestRiteDeleteNotFound:
    """delete absent/already-deleted: stderr message + exit 1, no success path."""

    def test_delete_not_found(self, runner, project_dir):
        r = runner.invoke(main, ["rite", "delete", "nope"])
        assert r.exit_code == 1
        assert r.stderr.strip() == 'Rite "nope" not found'

    def test_delete_already_deleted(self, runner, project_dir):
        _seed_main(project_dir, "issue-refund", CANONICAL_MAIN_RITE)
        runner.invoke(main, ["rite", "delete", "issue-refund"])
        r = runner.invoke(main, ["rite", "delete", "issue-refund"])
        assert r.exit_code == 1
        assert r.stderr.strip() == 'Rite "issue-refund" not found'
