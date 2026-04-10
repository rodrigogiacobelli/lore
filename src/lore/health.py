"""Health check module — audits all five file-based entity types."""

import dataclasses
import re
from pathlib import Path

import yaml


@dataclasses.dataclass(frozen=True)
class HealthIssue:
    """Structured health check issue (severity, entity_type, id, check, detail)."""
    severity: str      # "error" | "warning"
    entity_type: str   # "codex" | "artifacts" | "doctrines" | "knights" | "watchers"
    id: str            # entity ID or filepath string when ID is unknown
    check: str         # e.g. "broken_related_link", "missing_frontmatter"
    detail: str        # human-readable explanation

    @classmethod
    def from_dict(cls, d: dict) -> "HealthIssue":
        return cls(
            severity=d["severity"],
            entity_type=d["entity_type"],
            id=d["id"],
            check=d["check"],
            detail=d["detail"],
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


_ALL_SCOPES = ("codex", "artifacts", "doctrines", "knights", "watchers")

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


def _write_report(report: HealthReport, codex_dir: Path, timestamp: str) -> Path:
    """Write markdown report to codex_dir/transient/health-{timestamp}.md."""
    transient_dir = codex_dir / "transient"
    transient_dir.mkdir(parents=True, exist_ok=True)

    filename = f"health-{timestamp}.md"
    filepath = transient_dir / filename

    # Convert timestamp like 2026-04-09T14-32-00 to 2026-04-09T14:32:00
    parts = timestamp.split("T")
    if len(parts) == 2:
        human_ts = f"{parts[0]}T{parts[1].replace('-', ':')}"
    else:
        human_ts = timestamp

    frontmatter = (
        f"---\n"
        f"id: health-{timestamp}\n"
        f"title: Health Report — {human_ts}\n"
        f"summary: lore health report generated at {human_ts} UTC\n"
        f"---\n"
    )

    header = f"\n# Health Report — {human_ts} UTC\n\n"

    if not report.issues:
        body = "No issues found.\n"
    else:
        table_header = "| Severity | Entity Type | ID | Check | Detail |\n"
        table_sep = "|----------|-------------|-----|-------|--------|\n"
        rows = "".join(
            f"| {issue.severity.upper()} | {issue.entity_type} | {issue.id} | {issue.check} | {issue.detail} |\n"
            for issue in report.issues
        )
        body = table_header + table_sep + rows

    filepath.write_text(frontmatter + header + body)
    return filepath


def health_check(
    project_root: Path,
    scope: list[str] | None = None,
) -> HealthReport:
    """Audit file-based entity types and return a HealthReport.

    scope=None audits all five types.
    scope=["codex", "watchers"] audits only those two.
    Never prints to stdout or stderr.
    """
    if scope is None:
        active_scope = list(_ALL_SCOPES)
    else:
        active_scope = list(scope)

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
