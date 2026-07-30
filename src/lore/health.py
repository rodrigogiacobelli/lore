"""Health check module — audits all five file-based entity types."""

import dataclasses
import re
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import yaml

# Re-exported at module scope so tests can monkeypatch `health.get_validator`
# and `_check_schemas` can resolve its default via `sys.modules[__name__]`.
from lore.schemas import _validator_for as get_validator  # noqa: F401
from lore.schemas import project_validator_for as project_get_validator  # noqa: F401

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
    """Structured health check result.

    Attributes:
        errors: Issues with severity ``error`` (or escalated warnings).
        warnings: Non-error issues.
        report_path: Filesystem path of the markdown report when
            ``health_check`` was called with ``write_report=True``; otherwise
            ``None``.
        schemas_ran: ``True`` when the run included the ``schemas`` or
            ``glossary`` scope (drives schema-summary rendering on the CLI).
    """
    errors: tuple[HealthIssue, ...]
    warnings: tuple[HealthIssue, ...]
    report_path: Path | None = None
    schemas_ran: bool = False

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    @property
    def issues(self) -> tuple[HealthIssue, ...]:
        """All issues in insertion order (errors then warnings)."""
        return self.errors + self.warnings


_ALL_SCOPES = ("codex", "artifacts", "doctrines", "knights", "watchers", "glossary", "schemas", "bindings", "rites")

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
    ("glossary",                    "glossary",                    "codex",     "glossary.yaml"),
    ("main-rite",                   "main-rite",                   "rites",     "main/**/*.yaml"),
    ("shared-step",                 "shared-step",                 "rites",     "shared/**/*.yaml"),
)

# Schema kinds whose payload lives in a leading YAML frontmatter block.
_FRONTMATTER_SCHEMA_KINDS: frozenset[str] = frozenset({
    "knight-frontmatter",
    "codex-frontmatter",
    "codex-source-frontmatter",
    "artifact-frontmatter",
    "doctrine-design-frontmatter",
})

_ARTIFACT_ID_PATTERN = re.compile(r"\bfi-[a-z0-9-]+\b")

# Warning checks that escalate to the errors bucket so they raise the exit
# code even though the issue's severity remains "warning" in the report.
_ESCALATED_WARNING_CHECKS: frozenset[str] = frozenset({
    "alias_keyword_collision",
})


def _parse_frontmatter(filepath: Path) -> dict | None:
    """Return parsed YAML frontmatter dict, or None if absent or invalid.

    Tolerates a uniform leading-whitespace indent on the opening ``---`` fence
    (e.g. dedented test fixtures whose multi-line ``related`` block defeats
    ``textwrap.dedent``); the same prefix is stripped from every frontmatter
    line before YAML parsing. The body is not modified.
    """
    try:
        text = filepath.read_text()
        first, _, _ = text.partition("\n")
        stripped = first.lstrip(" ")
        pad_len = len(first) - len(stripped)
        if pad_len and stripped == "---":
            pad = " " * pad_len
            text = "\n".join(
                line[pad_len:] if line.startswith(pad) else line
                for line in text.split("\n")
            )
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
    """Audit codex documents for missing IDs, broken related links, island nodes,
    and the source one-way-link rule (FR-8, FR-10a)."""
    issues: list[HealthIssue] = []
    if not codex_dir.exists():
        return issues

    transient_dir = codex_dir / "transient"
    sources_dir = codex_dir / "sources"

    known_ids: set[str] = set()
    source_ids: set[str] = set()           # subset of known_ids under sources/
    docs: list[tuple[dict, bool]] = []     # (fm, is_source)

    for filepath in codex_dir.rglob("*.md"):
        if filepath.is_relative_to(transient_dir):
            continue
        is_source = filepath.is_relative_to(sources_dir)
        fm = _parse_frontmatter(filepath)
        if fm is None or not fm.get("id"):
            if is_source:
                # Source frontmatter issues are reported by _check_schemas.
                continue
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
        if is_source:
            source_ids.add(doc_id)
        docs.append((fm, is_source))

    # Related-link pass: broken links for everyone; canonical_links_to_source for non-sources only.
    referenced_ids: set[str] = set()
    for fm, is_source in docs:
        doc_id = str(fm["id"])
        related = fm.get("related") or []
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
                continue
            if (not is_source) and ref_id in source_ids:
                issues.append(HealthIssue(
                    severity="error",
                    entity_type="codex",
                    id=doc_id,
                    check="canonical_links_to_source",
                    detail=f"canonical doc links to source '{ref_id}' — the source→canonical rule is one-way",
                ))

    # Island-node pass: excludes every source id (sources are inbound-orphans by design).
    # Carve-out: 'codex' is the project-wide root guide; no inbound links by design.
    for doc_id in known_ids - source_ids:
        if doc_id == "codex":
            continue
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
    from lore.knight import _find_knight as find_knight
    project_root = knights_dir.parent.parent

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
                    knight_path = find_knight(project_root, knight_stem)
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
    from lore.knight import _find_knight as find_knight

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
        knight_path = find_knight(project_root, knight_stem)
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


def _resolve_schema_candidates(entity_root: Path, glob: str) -> list[Path]:
    """Resolve a ``_SCHEMA_KINDS`` glob entry to a sorted list of files.

    Globs containing ``*`` are passed through ``Path.glob``. Globs without any
    ``*`` are treated as literal filenames under ``entity_root`` (used for
    the single-file ``glossary.yaml`` schema row).
    """
    if "*" in glob:
        return sorted(entity_root.glob(glob))
    literal = entity_root / glob
    return [literal] if literal.is_file() else []


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
    get_validator: "Callable[[str], Draft202012Validator] | None" = None,  # noqa: F811
) -> list[HealthIssue]:
    """Validate every entity file on disk against its packaged JSON Schema.

    Walks the six entity globs; missing entity directories are a silent no-op.
    Emits one HealthIssue(check="schema") per underlying schema violation —
    multiple violations on the same file are preserved (not aggregated).
    """
    import sys

    from lore.schemas import _OVERLAY_KINDS, SchemaIssue, _issue_from_error

    if get_validator is None:
        get_validator = sys.modules[__name__].get_validator
    project_get_validator = sys.modules[__name__].project_get_validator  # noqa: F811

    issues: list[HealthIssue] = []
    lore_dir = project_root / ".lore"

    for entity_label, schema_kind, root_name, glob in _SCHEMA_KINDS:
        entity_root = lore_dir / root_name
        if not entity_root.exists():
            continue

        schema_id = f"lore://schemas/{schema_kind}"
        validator = None
        try:
            if schema_kind in _OVERLAY_KINDS:
                validator = project_get_validator(schema_kind, project_root)
            else:
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

        # --- per-file kind overrides under the codex entity root ---
        # (Tech Spec FR-10 Critical decision: in-loop dispatch, not a new
        # _SCHEMA_KINDS row.)
        sources_override: tuple[str, str, "Draft202012Validator"] | None = None
        if entity_label == "codex":
            source_schema_id = "lore://schemas/codex-source-frontmatter"
            try:
                src_validator = project_get_validator(
                    "codex-source-frontmatter", project_root
                )
                resolved_source_id = str(
                    src_validator.schema.get("$id", source_schema_id)
                )
                sources_override = (
                    "codex-source",
                    resolved_source_id,
                    src_validator,
                )
            except Exception as exc:
                issues.append(HealthIssue(
                    severity="error",
                    entity_type="codex-source",
                    id=source_schema_id,
                    check="scan_failed",
                    detail=f"{source_schema_id}: {exc}",
                    schema_id=source_schema_id,
                ))
        sources_dir = entity_root / "sources"
        transient_dir = entity_root / "transient"

        candidates = _resolve_schema_candidates(entity_root, glob)

        # Overlays are canonical-codex governance. Transient working docs —
        # including the reports `lore health` writes itself — validate against
        # the packaged schema alone, so a newly required custom field never
        # turns them into errors. Resolved only when the subtree has files, so
        # projects without one keep a single validator lookup.
        transient_override: tuple[str, str, "Draft202012Validator"] | None = None
        if entity_label == "codex" and any(
            p.is_relative_to(transient_dir) for p in candidates
        ):
            packaged_schema_id = f"lore://schemas/{schema_kind}"
            try:
                packaged_validator = get_validator(schema_kind)
                transient_override = (
                    entity_label,
                    str(packaged_validator.schema.get("$id", packaged_schema_id)),
                    packaged_validator,
                )
            except Exception as exc:
                issues.append(HealthIssue(
                    severity="error",
                    entity_type=entity_label,
                    id=packaged_schema_id,
                    check="scan_failed",
                    detail=f"{packaged_schema_id}: {exc}",
                    schema_id=packaged_schema_id,
                ))
        # --- END ---

        if (
            validator is None
            and sources_override is None
            and transient_override is None
        ):
            continue

        for filepath in candidates:
            if not filepath.is_file():
                continue

            is_transient_file = (
                entity_label == "codex" and filepath.is_relative_to(transient_dir)
            )
            is_source_file = (
                entity_label == "codex"
                and not is_transient_file
                and filepath.is_relative_to(sources_dir)
            )
            if is_transient_file:
                if transient_override is None:
                    continue
                active_label, active_schema_id, active_validator = transient_override
                active_kind = schema_kind
            elif is_source_file:
                if sources_override is None:
                    continue
                active_label, active_schema_id, active_validator = sources_override
                active_kind = "codex-source-frontmatter"
            else:
                if validator is None:
                    continue
                active_label = entity_label
                active_kind = schema_kind
                active_validator = validator
                active_schema_id = schema_id

            rel = filepath.relative_to(project_root).as_posix()
            try:
                data, schema_issues = _load_schema_payload(filepath, active_kind)
                if not schema_issues:
                    schema_issues = [_issue_from_error(err) for err in active_validator.iter_errors(data)]
            except Exception as exc:
                schema_issues = [SchemaIssue(rule="read-failed", pointer="/", message=str(exc))]

            for si in schema_issues:
                issues.append(HealthIssue(
                    severity="error",
                    entity_type=active_label,
                    id=rel,
                    check="schema",
                    detail=si.message,
                    schema_id=active_schema_id,
                    rule=si.rule,
                    pointer=si.pointer,
                ))

    return issues


_GLOSSARY_REL_ID = ".lore/codex/glossary.yaml"


def _glossary_schema_issues(project_root: Path) -> list[HealthIssue]:
    """Return only the schema issues for the glossary file (family 1)."""
    return [
        i for i in _check_schemas(project_root)
        if i.entity_type == "glossary" and i.check == "schema"
    ]


def _glossary_duplicate_keyword_issues(items: list) -> list[HealthIssue]:
    """Two items sharing a casefolded keyword (family 2, error)."""
    issues: list[HealthIssue] = []
    seen: dict[str, int] = {}
    for idx, item in enumerate(items):
        kw = item.keyword.casefold()
        if kw in seen:
            issues.append(HealthIssue(
                severity="error",
                entity_type="glossary",
                id=_GLOSSARY_REL_ID,
                check="duplicate_keyword",
                detail=f"'{kw}' appears in items[{seen[kw]}] and items[{idx}]",
            ))
        else:
            seen[kw] = idx
    return issues


def _glossary_alias_collision_issues(items: list) -> list[HealthIssue]:
    """Alias on item A casefold-equals keyword of another item B (family 2, warning)."""
    issues: list[HealthIssue] = []
    for item_a in items:
        for alias in item_a.aliases:
            alias_cf = alias.casefold()
            for item_b in items:
                if item_b is item_a:
                    continue
                if alias_cf == item_b.keyword.casefold():
                    issues.append(HealthIssue(
                        severity="warning",
                        entity_type="glossary",
                        id=_GLOSSARY_REL_ID,
                        check="alias_keyword_collision",
                        detail=(
                            f"alias '{alias_cf}' on '{item_a.keyword}' "
                            f"collides with keyword '{item_b.keyword}'"
                        ),
                    ))
    return issues


def _glossary_do_not_use_collision_issues(items: list) -> list[HealthIssue]:
    """``do_not_use`` term casefold-equals any keyword or alias on another item,
    or appears in the ``do_not_use`` list of 2+ items (intra-file collision, error)."""
    issues: list[HealthIssue] = []
    for item_a in items:
        for term in item_a.do_not_use:
            term_cf = term.casefold()
            for item_b in items:
                if item_b is item_a:
                    continue
                collisions: list[str] = []
                if term_cf == item_b.keyword.casefold():
                    collisions.append(item_b.keyword)
                collisions.extend(a for a in item_b.aliases if term_cf == a.casefold())
                for collider in collisions:
                    issues.append(HealthIssue(
                        severity="error",
                        entity_type="glossary",
                        id=_GLOSSARY_REL_ID,
                        check="do_not_use_collision",
                        detail=(
                            f"'{term_cf}' in do_not_use of '{item_a.keyword}' "
                            f"collides with keyword/alias '{collider}'"
                        ),
                    ))
    # Cross-item duplicate do_not_use terms — one row per duplicated term.
    term_to_keywords: dict[str, list[str]] = {}
    for item in items:
        seen_in_item: set[str] = set()
        for term in item.do_not_use:
            term_cf = term.casefold()
            if term_cf in seen_in_item:
                continue
            seen_in_item.add(term_cf)
            term_to_keywords.setdefault(term_cf, []).append(item.keyword)
    for term_cf, keywords in term_to_keywords.items():
        if len(keywords) < 2:
            continue
        issues.append(HealthIssue(
            severity="error",
            entity_type="glossary",
            id=_GLOSSARY_REL_ID,
            check="do_not_use_collision",
            detail=(
                f"'{term_cf}' appears in do_not_use of multiple items: "
                + ", ".join(f"'{k}'" for k in keywords)
            ),
        ))
    return issues


_BINDINGS_SKIP_DIRS: frozenset[str] = frozenset(
    {".git", ".lore", "node_modules", "__pycache__"}
)


def _symlink_escapes_root(entry: Path, root_resolved: Path) -> bool:
    """Return ``True`` if *entry* is a symlink whose target resolves outside *root_resolved*.

    Non-symlinks return ``False``. ``OSError`` (broken link, etc.) is treated
    as an escaper — the path is excluded.
    """
    if not entry.is_symlink():
        return False
    try:
        entry.resolve().relative_to(root_resolved)
    except (OSError, ValueError):
        return True
    return False


def _walk_repo_files(project_root: Path) -> list[str]:
    """Return sorted POSIX repo-relative paths for files under *project_root*.

    Excludes the well-known skip dirs in ``_BINDINGS_SKIP_DIRS`` and drops
    symlinks whose target resolves outside ``project_root.resolve()``.
    ``PermissionError``/``OSError`` on a subdirectory are caught per
    ``iterdir`` call — the offending subtree is treated as empty and walking
    continues with sibling entries.
    """
    root_resolved = project_root.resolve()
    results: list[str] = []

    def _walk(dirpath: Path, rel_parts: tuple[str, ...]) -> None:
        try:
            entries = list(dirpath.iterdir())
        except (PermissionError, OSError):
            return
        for entry in entries:
            if _symlink_escapes_root(entry, root_resolved):
                continue
            child_parts = rel_parts + (entry.name,)
            if entry.is_dir():
                if entry.name in _BINDINGS_SKIP_DIRS:
                    continue
                _walk(entry, child_parts)
            elif entry.is_file():
                results.append("/".join(child_parts))

    _walk(project_root, ())
    results.sort()
    return results


def _check_bindings(project_root: Path) -> list[HealthIssue]:
    """Audit codex ``binds:`` entries.

    Two branches:

    * Literal binds — every literal path that does not exist on disk (or that
      resolves outside ``project_root``) surfaces as one ``dead_binding``
      error row.
    * Glob binds — every glob pattern whose expansion matches zero files in
      the project surfaces as one ``empty_glob_binding`` warning row.

    Rows are ordered by codex id ascending; within an entry, declaration
    order is preserved. The repo file walk is built lazily on the first glob
    seen and reused for the rest of the call.
    """
    from lore.impacts import (
        _has_glob_chars,
        _load_codex_binds_index,
        _normalize_slashes,
        _pattern_to_regex,
    )

    codex_dir = project_root / ".lore" / "codex"
    index = _load_codex_binds_index(codex_dir)
    if not index:
        return []

    issues: list[HealthIssue] = []
    root_resolved = project_root.resolve()
    repo_files: list[str] | None = None  # lazy — only built if a glob is seen

    for codex_id in sorted(index):
        for binding in index[codex_id]:
            pat_norm = _normalize_slashes(binding)
            if not _has_glob_chars(pat_norm):
                candidate = project_root / pat_norm
                try:
                    resolved = candidate.resolve()
                    resolved.relative_to(root_resolved)
                except (OSError, ValueError):
                    issues.append(HealthIssue(
                        severity="error",
                        entity_type="codex",
                        id=codex_id,
                        check="dead_binding",
                        detail=f'"{binding}" — resolves outside project root',
                    ))
                    continue
                if not candidate.exists():
                    issues.append(HealthIssue(
                        severity="error",
                        entity_type="codex",
                        id=codex_id,
                        check="dead_binding",
                        detail=f'"{binding}" — file not found',
                    ))
                continue

            # Glob branch — build repo file index lazily.
            if repo_files is None:
                repo_files = _walk_repo_files(project_root)
            regex = re.compile("^" + _pattern_to_regex(pat_norm) + "$")
            if not any(regex.match(p) for p in repo_files):
                issues.append(HealthIssue(
                    severity="warning",
                    entity_type="codex",
                    id=codex_id,
                    check="empty_glob_binding",
                    detail=f'"{binding}" — pattern matches zero files',
                ))
    return issues


def _check_glossary(project_root: Path) -> list[HealthIssue]:
    """Audit the glossary file. Four phases: schema (short-circuits on error),
    duplicate keyword, alias collision, do_not_use collision."""
    from lore.glossary import scan_glossary

    glossary_file = project_root / ".lore" / "codex" / "glossary.yaml"
    if not glossary_file.exists():
        return []

    schema_issues = _glossary_schema_issues(project_root)
    if schema_issues:
        return schema_issues

    items = scan_glossary(project_root)
    return [
        *_glossary_duplicate_keyword_issues(items),
        *_glossary_alias_collision_issues(items),
        *_glossary_do_not_use_collision_issues(items),
    ]


def _rite_targets(then) -> list[str]:
    """Return the routing targets declared by a node's ``then`` value.

    ``then`` is a single target string or a list of ``{if, goto}`` branches.
    Missing/empty ``then`` yields no targets.
    """
    if then is None:
        return []
    if isinstance(then, str):
        return [then]
    targets: list[str] = []
    if isinstance(then, list):
        for branch in then:
            if isinstance(branch, dict) and branch.get("goto"):
                targets.append(str(branch["goto"]))
    return targets


def _scan_main_rites(main_dir: Path) -> list[dict]:
    """Parse every non-deleted ``main/**/*.yaml`` rite into a dict (recursive)."""
    if not main_dir.is_dir():
        return []
    rites: list[dict] = []
    for filepath in sorted(main_dir.rglob("*.yaml")):
        if not filepath.is_file():
            continue
        try:
            data = yaml.safe_load(filepath.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if isinstance(data, dict):
            rites.append(data)
    return rites


def _scan_rite_id_files(rites_dir: Path) -> list[tuple[str, Path]]:
    """Return ``(id, filepath)`` for every non-deleted rite across the tree.

    Scans ``main/`` then ``shared/`` recursively. The id is the file's ``id:``
    field, falling back to its stem. Used for the duplicate-id collision check.
    """
    out: list[tuple[str, Path]] = []
    for sub in ("main", "shared"):
        subdir = rites_dir / sub
        if not subdir.is_dir():
            continue
        for filepath in sorted(subdir.rglob("*.yaml")):
            if not filepath.is_file():
                continue
            try:
                data = yaml.safe_load(filepath.read_text(encoding="utf-8"))
            except yaml.YAMLError:
                continue
            rid = str(data.get("id", filepath.stem)) if isinstance(data, dict) else filepath.stem
            out.append((rid, filepath))
    return out


def _check_dangling_codex_rites(project_root: Path) -> list[HealthIssue]:
    """Return ``dangling_codex_rite`` rows for codex ``rites:`` naming a missing rite.

    Codex-side reference-integrity check that depends on the rite index, so it
    runs under both the ``rites`` and ``codex`` scopes.
    """
    from lore.impacts import _load_codex_rites_index

    codex_dir = project_root / ".lore" / "codex"
    main_dir = project_root / ".lore" / "rites" / "main"
    main_ids = {str(r.get("id")) for r in _scan_main_rites(main_dir) if r.get("id")}

    issues: list[HealthIssue] = []
    index = _load_codex_rites_index(codex_dir)
    for codex_id in sorted(index):
        for ref in index[codex_id]:
            if ref not in main_ids:
                issues.append(HealthIssue(
                    severity="error",
                    entity_type="rites",
                    id=codex_id,
                    check="dangling_codex_rite",
                    detail=f'codex "{codex_id}" references missing rite "{ref}"',
                ))
    return issues


def _check_rites(project_root: Path) -> list[HealthIssue]:
    """Audit rites: reference integrity, graph well-formedness, orphan asymmetry.

    Three classes (all errors except the orphan-shared-step warning):

    * Reference integrity — ``dangling_use``, ``dangling_then``,
      ``dangling_codex_rite``.
    * Graph well-formedness (per main rite) — ``no_entry_node``,
      ``multiple_entry_nodes``, ``unreachable_node``,
      ``conclusion_never_reached``, ``undefined_conclusion``.
    * Orphans — ``orphan_shared_step`` (warning); an orphan main rite is NOT
      flagged.

    Skips ``*.yaml.deleted`` files. ``schema_id``/``rule``/``pointer`` are null
    on every row (schema checks ride on ``_check_schemas``).
    """
    issues: list[HealthIssue] = []
    rites_dir = project_root / ".lore" / "rites"
    main_dir = rites_dir / "main"
    shared_dir = rites_dir / "shared"

    # Duplicate-id collision across the whole main+shared tree. A rite's id is
    # globally unique (codex model); the same id in two files anywhere is an
    # error, like a codex id collision.
    id_files: dict[str, list[Path]] = {}
    for rid, filepath in _scan_rite_id_files(rites_dir):
        id_files.setdefault(rid, []).append(filepath)
    for rid in sorted(id_files):
        paths = id_files[rid]
        if len(paths) > 1:
            rels = ", ".join(
                str(p.relative_to(rites_dir)) for p in sorted(paths)
            )
            issues.append(HealthIssue(
                severity="error",
                entity_type="rites",
                id=rid,
                check="duplicate_rite_id",
                detail=f'rite id "{rid}" defined in multiple files: {rels}',
            ))

    # Known shared-step ids (non-deleted), resolved by id across the recursive
    # shared/ tree.
    shared_ids: set[str] = set()
    if shared_dir.is_dir():
        for filepath in sorted(shared_dir.rglob("*.yaml")):
            if not filepath.is_file():
                continue
            try:
                data = yaml.safe_load(filepath.read_text(encoding="utf-8"))
            except yaml.YAMLError:
                continue
            sid = str(data.get("id", filepath.stem)) if isinstance(data, dict) else filepath.stem
            shared_ids.add(sid)

    main_rites = _scan_main_rites(main_dir)
    used_shared: set[str] = set()

    for rite in main_rites:
        rite_id = str(rite.get("id", ""))
        nodes = rite.get("nodes") or []
        node_ids = [str(n.get("id")) for n in nodes if isinstance(n, dict) and n.get("id")]
        node_id_set = set(node_ids)
        conclusions = rite.get("conclusions") or {}
        conclusion_keys = set(conclusions.keys()) if isinstance(conclusions, dict) else set()

        # Reference integrity: dangling use.
        for node in nodes:
            if not isinstance(node, dict):
                continue
            use_id = node.get("use")
            if use_id is not None:
                used_shared.add(str(use_id))
                if str(use_id) not in shared_ids:
                    issues.append(HealthIssue(
                        severity="error",
                        entity_type="rites",
                        id=rite_id,
                        check="dangling_use",
                        detail=f'node "{node.get("id")}" uses missing shared step "{use_id}"',
                    ))

        # Pre-pass: build inbound edges + the set of reached conclusions.
        inbound: set[str] = set()
        reached_conclusions: set[str] = set()
        for node in nodes:
            if not isinstance(node, dict):
                continue
            for target in _rite_targets(node.get("then")):
                if target in node_id_set:
                    inbound.add(target)
                elif target in conclusion_keys:
                    reached_conclusions.add(target)

        # Classify routes to unknown targets. A node WITH an inbound edge
        # "looked like a missing node id" mid-chain → dangling_then. An entry
        # node (no inbound edge) routing to an unknown terminal target "looked
        # like a missing conclusion key" → undefined_conclusion.
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("id"))
            for target in _rite_targets(node.get("then")):
                if target in node_id_set or target in conclusion_keys:
                    continue
                if node_id in inbound:
                    issues.append(HealthIssue(
                        severity="error",
                        entity_type="rites",
                        id=rite_id,
                        check="dangling_then",
                        detail=f'node "{node_id}" routes to unknown target "{target}"',
                    ))
                else:
                    issues.append(HealthIssue(
                        severity="error",
                        entity_type="rites",
                        id=rite_id,
                        check="undefined_conclusion",
                        detail=f'node "{node_id}" routes to "{target}" — no node or conclusion',
                    ))

        # Graph well-formedness — only when there are nodes.
        if node_ids:
            entries = [nid for nid in node_ids if nid not in inbound]
            if not entries:
                issues.append(HealthIssue(
                    severity="error",
                    entity_type="rites",
                    id=rite_id,
                    check="no_entry_node",
                    detail="no entry node — every node has an inbound edge",
                ))
            elif len(entries) > 1:
                issues.append(HealthIssue(
                    severity="error",
                    entity_type="rites",
                    id=rite_id,
                    check="multiple_entry_nodes",
                    detail="multiple entry nodes: " + ", ".join(entries),
                ))

            # Reachability from the entry node(s). A node not reachable from
            # ANY entry is unreachable (seeding from every entry avoids false
            # positives when a rite has more than one entry).
            if entries:
                reachable: set[str] = set()
                stack = list(entries)
                node_by_id = {
                    str(n["id"]): n for n in nodes
                    if isinstance(n, dict) and n.get("id")
                }
                while stack:
                    cur = stack.pop()
                    if cur in reachable:
                        continue
                    reachable.add(cur)
                    for target in _rite_targets(node_by_id.get(cur, {}).get("then")):
                        if target in node_id_set and target not in reachable:
                            stack.append(target)
                for nid in node_ids:
                    if nid not in reachable:
                        issues.append(HealthIssue(
                            severity="error",
                            entity_type="rites",
                            id=rite_id,
                            check="unreachable_node",
                            detail=f'node "{nid}" is unreachable',
                        ))

        # Conclusion reachability: conclusion defined but never reached.
        for ckey in conclusion_keys:
            if ckey not in reached_conclusions:
                issues.append(HealthIssue(
                    severity="error",
                    entity_type="rites",
                    id=rite_id,
                    check="conclusion_never_reached",
                    detail=f'conclusion "{ckey}" is defined but never reached',
                ))

    # Reference integrity: dangling codex rite.
    issues.extend(_check_dangling_codex_rites(project_root))

    # Orphan shared steps (warning).
    for step_id in sorted(shared_ids):
        if step_id not in used_shared:
            issues.append(HealthIssue(
                severity="warning",
                entity_type="rites",
                id=step_id,
                check="orphan_shared_step",
                detail="no main rite uses this shared step",
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
    *,
    write_report: bool = False,
    timestamp: str | None = None,
) -> HealthReport:
    """Audit file-based entity types and return a :class:`HealthReport`.

    Args:
        project_root: Project root containing ``.lore/``. When ``None``,
            resolved via :func:`lore.root.find_project_root`.
        scope: Scopes to audit. ``None`` (default) audits every scope in
            ``_ALL_SCOPES``. Example: ``["codex", "watchers"]`` runs only
            those two.
        scopes: Alias for ``scope`` (kept for US-004 signature parity). When
            both are passed, ``scopes`` wins.
        write_report: When ``True``, writes the markdown report to
            ``<project>/.lore/codex/transient/health-<timestamp>.md`` and
            sets ``HealthReport.report_path``. Default ``False`` is a
            pure read-only audit.
        timestamp: ``%Y-%m-%dT%H-%M-%S`` UTC stamp used in the report
            filename. Only consulted when ``write_report=True``; defaults
            to "now" when omitted.

    Raises:
        ValueError: When ``scope``/``scopes`` contains an unknown token.

    Never prints to stdout or stderr.
    """
    selected = scopes if scopes is not None else scope
    if selected is not None:
        invalid = [s for s in selected if s not in _ALL_SCOPES]
        if invalid:
            raise ValueError(
                f"Unknown scope: '{invalid[0]}'. Valid scopes: "
                + ", ".join(_ALL_SCOPES)
                + "."
            )
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
        "codex": lambda: _check_codex(codex_dir) + _check_dangling_codex_rites(project_root),
        "artifacts": lambda: _check_artifacts(artifacts_dir),
        "doctrines": lambda: _check_doctrines(doctrines_dir, knights_dir, artifacts_dir),
        "knights": lambda: _check_knights(knights_dir, project_root),
        "watchers": lambda: _check_watchers(watchers_dir, doctrines_dir),
        "schemas": lambda: _check_schemas(project_root),
        "glossary": lambda: _check_glossary(project_root),
        "bindings": lambda: _check_bindings(project_root),
        "rites": lambda: _check_rites(project_root),
    }

    seen: set[HealthIssue] = set()
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
            # Dedup the dual-scope dangling_codex_rite row when both codex and
            # rites scopes run.
            if issue.check == "dangling_codex_rite":
                if issue in seen:
                    continue
                seen.add(issue)
            if issue.severity == "error" or issue.check in _ESCALATED_WARNING_CHECKS:
                errors.append(issue)
            else:
                warnings.append(issue)

    schemas_ran = "schemas" in active_scope or "glossary" in active_scope
    report = HealthReport(
        errors=tuple(errors),
        warnings=tuple(warnings),
        schemas_ran=schemas_ran,
    )

    if write_report:
        if timestamp is None:
            import datetime
            timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H-%M-%S"
            )
        report_path = _write_report(report, codex_dir, timestamp, schemas_ran=schemas_ran)
        report = dataclasses.replace(report, report_path=report_path)

    return report
