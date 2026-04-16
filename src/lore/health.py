"""Health check module — audits all five file-based entity types."""

import dataclasses
import re
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import yaml

if TYPE_CHECKING:
    from jsonschema import Draft202012Validator


@dataclasses.dataclass(frozen=True)
class HealthIssue:
    """Structured health check issue (severity, entity_type, id, check, detail)."""
    severity: str      # "error" | "warning"
    entity_type: str   # "codex" | "artifacts" | "doctrines" | "knights" | "watchers" | schema kind
    id: str            # entity ID or filepath string when ID is unknown
    check: str         # e.g. "broken_related_link", "missing_frontmatter", "schema"
    detail: str        # human-readable explanation
    schema_id: str | None = None  # e.g. "lore://schemas/knight-frontmatter" (schema check only)
    rule: str | None = None       # JSON Schema validator name (schema check only)
    pointer: str | None = None    # JSON pointer to offending field (schema check only)

    @classmethod
    def from_dict(cls, d: dict) -> "HealthIssue":
        return cls(
            severity=d["severity"],
            entity_type=d["entity_type"],
            id=d["id"],
            check=d["check"],
            detail=d["detail"],
            schema_id=d.get("schema_id"),
            rule=d.get("rule"),
            pointer=d.get("pointer"),
        )


@dataclasses.dataclass(frozen=True)
class HealthReport:
    """Structured health check result (errors, warnings)."""
    errors: tuple[HealthIssue, ...]
    warnings: tuple[HealthIssue, ...]

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    @property
    def issues(self) -> tuple[HealthIssue, ...]:
        """All issues in insertion order (errors then warnings)."""
        return self.errors + self.warnings


_ALL_SCOPES = ("codex", "artifacts", "doctrines", "knights", "watchers", "schemas")

# Schema-validated entity kinds. Each tuple is:
#   (entity_type label used on HealthIssue,
#    schema kind fed to lore.schemas.load_schema / _validator_for,
#    entity root under .lore/,
#    glob pattern evaluated under that root).
_SCHEMA_KINDS: tuple[tuple[str, str, str, str], ...] = (
    ("doctrine-yaml",               "doctrine-yaml",               "doctrines", "**/*.yaml"),
    ("doctrine-design-frontmatter", "doctrine-design-frontmatter", "doctrines", "**/*.design.md"),
    ("knight",                      "knight-frontmatter",          "knights",   "**/*.md"),
    ("watcher",                     "watcher-yaml",                "watchers",  "**/*.yaml"),
    ("codex",                       "codex-frontmatter",           "codex",     "**/*.md"),
    ("artifact",                    "artifact-frontmatter",        "artifacts", "**/*.md"),
)

# Schema kinds whose payload lives in a leading YAML frontmatter block.
_FRONTMATTER_SCHEMA_KINDS: frozenset[str] = frozenset({
    "knight-frontmatter",
    "codex-frontmatter",
    "artifact-frontmatter",
    "doctrine-design-frontmatter",
})

_ARTIFACT_ID_PATTERN = re.compile(r"\bfi-[a-z0-9-]+\b")


def _parse_frontmatter(filepath: Path) -> dict | None:
    """Return parsed YAML frontmatter dict, or None if absent or invalid."""
    try:
        text = filepath.read_text()
        parts = text.split("---", 2)
        if len(parts) < 3:
            return None
        fm = yaml.safe_load(parts[1])
        return fm if isinstance(fm, dict) else None
    except Exception:
        return None


def _is_knight_soft_deleted(knights_dir: Path, knight_stem: str) -> bool:
    """Return True if the knight has a .md.deleted file in knights_dir."""
    if not knights_dir.exists():
        return False
    return bool(list(knights_dir.rglob(f"{knight_stem}.md.deleted")))


def _build_artifact_index(artifacts_dir: Path) -> set[str]:
    """Return set of all known artifact IDs."""
    if not artifacts_dir.exists():
        return set()
    ids: set[str] = set()
    for filepath in artifacts_dir.rglob("*.md"):
        fm = _parse_frontmatter(filepath)
        if fm and fm.get("id"):
            ids.add(str(fm["id"]))
    return ids


def _build_doctrine_name_index(doctrines_dir: Path) -> set[str]:
    """Return set of doctrine stems where both .yaml AND .design.md exist (complete pairs)."""
    if not doctrines_dir.exists():
        return set()
    stems = set()
    for p in doctrines_dir.rglob("*.design.md"):
        stem = p.name.replace(".design.md", "")
        if (doctrines_dir / (stem + ".yaml")).exists():
            stems.add(stem)
    return stems


def _check_codex(codex_dir: Path) -> list[HealthIssue]:
    """Audit codex documents for missing IDs, broken related links, and island nodes."""
    issues: list[HealthIssue] = []

    if not codex_dir.exists():
        return issues

    # Parse all files once; cache frontmatter by doc ID
    known_ids: set[str] = set()
    docs: list[dict] = []

    transient_dir = codex_dir / "transient"
    for filepath in codex_dir.rglob("*.md"):
        if filepath.is_relative_to(transient_dir):
            continue
        fm = _parse_frontmatter(filepath)
        if fm is None or not fm.get("id"):
            issues.append(HealthIssue(
                severity="error",
                entity_type="codex",
                id=str(filepath.relative_to(codex_dir)),
                check="missing_frontmatter",
                detail="field 'id' absent",
            ))
            continue
        doc_id = str(fm["id"])
        known_ids.add(doc_id)
        docs.append(fm)

    # Check related links and collect referenced IDs
    referenced_ids: set[str] = set()

    for fm in docs:
        doc_id = str(fm["id"])
        related = fm.get("related")
        if not related:
            continue
        for entry in related:
            if entry is None:
                continue
            ref_id = str(entry).strip()
            referenced_ids.add(ref_id)
            if ref_id not in known_ids:
                issues.append(HealthIssue(
                    severity="error",
                    entity_type="codex",
                    id=doc_id,
                    check="broken_related_link",
                    detail=f"related ID '{ref_id}' does not exist",
                ))

    # Island nodes: docs with valid IDs not referenced by any other doc
    for doc_id in known_ids:
        if doc_id not in referenced_ids:
            issues.append(HealthIssue(
                severity="warning",
                entity_type="codex",
                id=doc_id,
                check="island_node",
                detail="no documents link here",
            ))

    return issues


def _check_artifacts(artifacts_dir: Path) -> list[HealthIssue]:
    """Audit artifact files for missing required frontmatter fields."""
    issues: list[HealthIssue] = []

    if not artifacts_dir.exists():
        return issues

    project_root = artifacts_dir.parent.parent
    for filepath in artifacts_dir.rglob("*.md"):
        relative_path = str(filepath.relative_to(project_root))
        fm = _parse_frontmatter(filepath) or {}
        for field in ("id", "title", "summary"):
            if not fm.get(field):
                issues.append(HealthIssue(
                    severity="error",
                    entity_type="artifacts",
                    id=relative_path,
                    check="missing_frontmatter",
                    detail=f"field '{field}' absent",
                ))
                break

    return issues


def _check_doctrines(
    doctrines_dir: Path,
    knights_dir: Path,
    artifacts_dir: Path,
) -> list[HealthIssue]:
    """Audit doctrines for orphaned files, broken knight refs, and broken artifact refs."""
    from lore.knight import find_knight

    issues: list[HealthIssue] = []

    if not doctrines_dir.exists():
        return issues

    artifact_index = _build_artifact_index(artifacts_dir)

    # Collect stems for .design.md and .yaml files
    design_stems: set[str] = set()
    yaml_stems: set[str] = set()

    for filepath in doctrines_dir.rglob("*.design.md"):
        stem = filepath.name.replace(".design.md", "")
        design_stems.add(stem)

    for filepath in doctrines_dir.rglob("*.yaml"):
        yaml_stems.add(filepath.stem)

    # Orphaned .yaml without .design.md
    for stem in yaml_stems - design_stems:
        issues.append(HealthIssue(
            severity="error",
            entity_type="doctrines",
            id=stem,
            check="orphaned_file",
            detail=".design.md missing",
        ))

    # Orphaned .design.md without .yaml
    for stem in design_stems - yaml_stems:
        issues.append(HealthIssue(
            severity="error",
            entity_type="doctrines",
            id=stem,
            check="orphaned_file",
            detail=".yaml missing",
        ))

    # Check complete pairs for knight refs and artifact refs
    for stem in design_stems & yaml_stems:
        # Find the yaml file
        yaml_files = list(doctrines_dir.rglob(f"{stem}.yaml"))
        if not yaml_files:
            continue
        yaml_file = yaml_files[0]

        try:
            data = yaml.safe_load(yaml_file.read_text())
            if not isinstance(data, dict):
                continue
            steps = data.get("steps") or []
            for position, step in enumerate(steps, start=1):
                if not isinstance(step, dict):
                    continue
                # Use step id trailing number if available (e.g. "step-3" → 3)
                step_num = position
                step_id = step.get("id", "")
                if step_id and step_id.startswith("step-"):
                    try:
                        step_num = int(step_id[5:])
                    except ValueError:
                        pass

                # Knight ref check
                knight_name = step.get("knight")
                if knight_name:
                    # Strip .md suffix if present (some doctrines use filename form)
                    knight_stem = knight_name[:-3] if knight_name.endswith(".md") else knight_name
                    knight_path = find_knight(knights_dir, knight_stem)
                    if knight_path is None and not _is_knight_soft_deleted(knights_dir, knight_stem):
                        issues.append(HealthIssue(
                            severity="error",
                            entity_type="doctrines",
                            id=stem,
                            check="broken_knight_ref",
                            detail=f"'{knight_name}' not found (step {step_num})",
                        ))

                # Artifact ref in notes
                notes = step.get("notes")
                if notes and isinstance(notes, str):
                    for match in _ARTIFACT_ID_PATTERN.finditer(notes):
                        artifact_id = match.group(0)
                        if artifact_id not in artifact_index:
                            issues.append(HealthIssue(
                                severity="error",
                                entity_type="doctrines",
                                id=stem,
                                check="broken_artifact_ref",
                                detail=f"'{artifact_id}' not found (step {step_num})",
                            ))
        except Exception:
            continue

    return issues


def _check_knights(knights_dir: Path, project_root: Path) -> list[HealthIssue]:
    """Audit knight refs from active missions."""
    from lore.db import list_missions
    from lore.knight import find_knight

    issues: list[HealthIssue] = []

    try:
        grouped = list_missions(project_root, include_closed=False)
    except Exception:
        return issues

    # Group mission IDs by knight name
    knight_to_missions: dict[str, list[str]] = {}
    for mission_list in grouped.values():
        for mission in mission_list:
            knight_name = mission["knight"]
            if not knight_name:
                continue
            knight_to_missions.setdefault(knight_name, []).append(mission["id"])

    for knight_name, mission_ids in knight_to_missions.items():
        # Strip .md suffix if present
        knight_stem = knight_name[:-3] if knight_name.endswith(".md") else knight_name
        knight_path = find_knight(knights_dir, knight_stem)
        if knight_path is not None:
            continue

        if _is_knight_soft_deleted(knights_dir, knight_stem):
            continue

        mission_ids_str = ", ".join(mission_ids)
        issues.append(HealthIssue(
            severity="error",
            entity_type="knights",
            id=knight_name,
            check="missing_file",
            detail=f"referenced by {mission_ids_str} but not found on disk",
        ))

    return issues


def _check_watchers(watchers_dir: Path, doctrines_dir: Path) -> list[HealthIssue]:
    """Audit watcher files for invalid YAML and broken doctrine refs."""
    issues: list[HealthIssue] = []

    if not watchers_dir.exists():
        return issues

    doctrine_index = _build_doctrine_name_index(doctrines_dir)

    for filepath in watchers_dir.rglob("*.yaml"):
        # Parse YAML directly to catch errors list_watchers silently skips
        try:
            data = yaml.safe_load(filepath.read_text())
        except yaml.YAMLError as exc:
            mark = exc.context_mark or exc.problem_mark
            line_num = mark.line + 1 if mark else 0
            issues.append(HealthIssue(
                severity="error",
                entity_type="watchers",
                id=filepath.stem,
                check="invalid_yaml",
                detail=f"parse failed at line {line_num}",
            ))
            continue

        if not isinstance(data, dict):
            continue

        watcher_id = str(data.get("id", filepath.stem))
        action = data.get("action")

        if action and isinstance(action, str):
            # Extract doctrine name: if "doctrine: name" format, use after ':'
            if ":" in action:
                doctrine_name = action.split(":", 1)[1].strip()
            else:
                doctrine_name = action.strip()

            if doctrine_name and doctrine_name not in doctrine_index:
                issues.append(HealthIssue(
                    severity="error",
                    entity_type="watchers",
                    id=watcher_id,
                    check="broken_doctrine_ref",
                    detail=f"'{doctrine_name}' not found",
                ))

    return issues


def _load_schema_payload(path: Path, schema_kind: str):
    """Read a file and extract the dict to be schema-validated.

    Returns ``(data, issues)``. On success ``issues`` is empty and ``data`` is
    the parsed YAML mapping (or raw YAML document for non-frontmatter kinds).
    On failure ``data`` is ``None`` and ``issues`` holds one
    ``SchemaIssue`` describing why the payload is unreachable.
    """
    from lore.schemas import (
        MISSING_FRONTMATTER_MESSAGE,
        NON_MAPPING_FRONTMATTER_MESSAGE,
        SchemaIssue,
    )

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, [SchemaIssue(rule="read-failed", pointer="/", message=str(exc))]

    def _missing_fm(msg: str) -> list["SchemaIssue"]:
        return [SchemaIssue(rule="missing-frontmatter", pointer="/", message=msg)]

    if schema_kind in _FRONTMATTER_SCHEMA_KINDS:
        parts = text.split("---", 2) if text.startswith("---") else []
        if len(parts) < 3:
            return None, _missing_fm(MISSING_FRONTMATTER_MESSAGE)
        try:
            data = yaml.safe_load(parts[1])
        except yaml.YAMLError as exc:
            return None, [SchemaIssue(rule="yaml-parse", pointer="/", message=str(exc))]
        if not isinstance(data, dict):
            return None, _missing_fm(NON_MAPPING_FRONTMATTER_MESSAGE)
        return data, []

    # Full-document YAML kinds (doctrine-yaml, watcher-yaml).
    try:
        return yaml.safe_load(text), []
    except yaml.YAMLError as exc:
        return None, [SchemaIssue(rule="yaml-parse", pointer="/", message=str(exc))]


def _check_schemas(
    project_root: Path,
    get_validator: "Callable[[str], Draft202012Validator] | None" = None,
) -> list[HealthIssue]:
    """Validate every entity file on disk against its packaged JSON Schema.

    Walks the six entity globs; missing entity directories are a silent no-op.
    Emits one HealthIssue(check="schema") per underlying schema violation —
    multiple violations on the same file are preserved (not aggregated).
    """
    from lore.schemas import SchemaIssue, _issue_from_error, _validator_for

    get_validator = get_validator or _validator_for

    issues: list[HealthIssue] = []
    lore_dir = project_root / ".lore"

    for entity_label, schema_kind, root_name, glob in _SCHEMA_KINDS:
        entity_root = lore_dir / root_name
        if not entity_root.exists():
            continue

        schema_id = f"lore://schemas/{schema_kind}"
        try:
            validator = get_validator(schema_kind)
            schema_id = str(validator.schema.get("$id", schema_id))
        except Exception as exc:
            issues.append(HealthIssue(
                severity="error",
                entity_type=entity_label,
                id=schema_id,
                check="scan_failed",
                detail=f"{schema_id}: {exc}",
                schema_id=schema_id,
            ))
            continue

        for filepath in sorted(entity_root.glob(glob)):
            if not filepath.is_file():
                continue

            rel = filepath.relative_to(project_root).as_posix()
            try:
                data, schema_issues = _load_schema_payload(filepath, schema_kind)
                if not schema_issues:
                    schema_issues = [_issue_from_error(err) for err in validator.iter_errors(data)]
            except Exception as exc:
                schema_issues = [SchemaIssue(rule="read-failed", pointer="/", message=str(exc))]

            for si in schema_issues:
                issues.append(HealthIssue(
                    severity="error",
                    entity_type=entity_label,
                    id=rel,
                    check="schema",
                    detail=si.message,
                    schema_id=schema_id,
                    rule=si.rule,
                    pointer=si.pointer,
                ))

    return issues


def _humanize_timestamp(timestamp: str) -> str:
    """Convert a filename-safe timestamp like 2026-04-09T14-32-00 to 2026-04-09T14:32:00."""
    date_part, sep, time_part = timestamp.partition("T")
    if not sep:
        return timestamp
    return f"{date_part}T{time_part.replace('-', ':')}"


def _render_issues_table(issues: tuple[HealthIssue, ...]) -> str:
    """Render the markdown issues table, or the zero-issue placeholder."""
    if not issues:
        return "No issues found.\n"
    header = (
        "| Severity | Entity Type | ID | Check | Detail |\n"
        "|----------|-------------|-----|-------|--------|\n"
    )
    rows = "".join(
        f"| {i.severity.upper()} | {i.entity_type} | {i.id} | {i.check} | {i.detail} |\n"
        for i in issues
    )
    return header + rows


def _render_schema_section(issues: tuple[HealthIssue, ...]) -> str:
    """Render the '## Schema validation' section grouped by kind, sorted by path.

    Expects the caller to have already decided the section should be emitted
    (i.e. the ``schemas`` scope ran). Returns the full section text with its
    leading blank line, ready to concatenate to the report body.
    """
    schema_issues = [i for i in issues if i.check == "schema"]
    if not schema_issues:
        return "\n## Schema validation\n\nNo schema errors.\n"

    by_kind: dict[str, list[HealthIssue]] = {}
    for issue in schema_issues:
        by_kind.setdefault(issue.entity_type, []).append(issue)

    kind_blocks: list[str] = []
    for kind in sorted(by_kind):
        entries = sorted(by_kind[kind], key=lambda i: i.id)
        lines = [f"### {kind}"]
        lines.extend(
            f"- `{e.id}` — `{e.rule}` at `{e.pointer}` — {e.detail}"
            for e in entries
        )
        kind_blocks.append("\n".join(lines) + "\n")

    return "\n## Schema validation\n\n" + "\n".join(kind_blocks)


def _write_report(
    report: HealthReport,
    codex_dir: Path,
    timestamp: str,
    schemas_ran: bool = False,
) -> Path:
    """Write markdown report to codex_dir/transient/health-{timestamp}.md."""
    transient_dir = codex_dir / "transient"
    transient_dir.mkdir(parents=True, exist_ok=True)
    filepath = transient_dir / f"health-{timestamp}.md"

    human_ts = _humanize_timestamp(timestamp)
    frontmatter = (
        f"---\n"
        f"id: health-{timestamp}\n"
        f"title: Health Report — {human_ts}\n"
        f"summary: lore health report generated at {human_ts} UTC\n"
        f"---\n"
    )
    header = f"\n# Health Report — {human_ts} UTC\n\n"
    body = _render_issues_table(report.issues)
    schema_section = _render_schema_section(report.issues) if schemas_ran else ""

    filepath.write_text(frontmatter + header + body + schema_section)
    return filepath


def health_check(
    project_root: Path | None = None,
    scope: list[str] | None = None,
    scopes: list[str] | None = None,
) -> HealthReport:
    """Audit file-based entity types and return a HealthReport.

    scope=None audits all scopes in ``_ALL_SCOPES``.
    scope=["codex", "watchers"] audits only those two.
    ``scopes`` is an alias for ``scope`` (US-004 signature).
    Never prints to stdout or stderr.
    """
    selected = scopes if scopes is not None else scope
    active_scope = list(_ALL_SCOPES) if selected is None else list(selected)

    if project_root is None:
        from lore.root import find_project_root
        project_root = find_project_root()

    lore_dir = project_root / ".lore"
    codex_dir = lore_dir / "codex"
    artifacts_dir = lore_dir / "artifacts"
    doctrines_dir = lore_dir / "doctrines"
    knights_dir = lore_dir / "knights"
    watchers_dir = lore_dir / "watchers"

    errors: list[HealthIssue] = []
    warnings: list[HealthIssue] = []

    checkers = {
        "codex": lambda: _check_codex(codex_dir),
        "artifacts": lambda: _check_artifacts(artifacts_dir),
        "doctrines": lambda: _check_doctrines(doctrines_dir, knights_dir, artifacts_dir),
        "knights": lambda: _check_knights(knights_dir, project_root),
        "watchers": lambda: _check_watchers(watchers_dir, doctrines_dir),
        "schemas": lambda: _check_schemas(project_root),
    }

    for scope_name in active_scope:
        checker = checkers.get(scope_name)
        if checker is None:
            continue
        try:
            issues = checker()
        except Exception as exc:
            issues = [HealthIssue(
                severity="error",
                entity_type=scope_name,
                id=scope_name,
                check="scan_failed",
                detail=str(exc),
            )]
        for issue in issues:
            if issue.severity == "error":
                errors.append(issue)
            else:
                warnings.append(issue)

    return HealthReport(errors=tuple(errors), warnings=tuple(warnings))
