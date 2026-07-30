"""Field-level frontmatter editing for file-backed entities.

Spec: ``transient-frontmatter-field-edit-spec``.

Public surface: :func:`update_frontmatter_fields`. Mutates one entity's
frontmatter on disk (markdown+frontmatter or pure-YAML) leaving the body
bit-identical. Dispatches per kind via a small config table; reuses each
entity module's existing locator helper.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml

from lore import artifact as _artifact_mod
from lore import codex as _codex_mod
from lore import knight as _knight_mod
from lore import schemas as _schemas
from lore import validators as _validators
from lore import watcher as _watcher_mod
from lore.paths import entity_location


# ---------------------------------------------------------------------------
# Per-kind dispatch table.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _KindConfig:
    kind: str
    # schema_kind may be a static string OR a callable that resolves the
    # schema per-doc at validation time (codex: doc_type-dependent).
    schema_kind: Callable[[dict, Path, Path], str] | str
    extension: str
    # markdown+frontmatter ("md_fm") vs pure-YAML ("yaml")
    shape: str
    locator: Callable[[Path, str], Path | None]


def _doctrine_locator(project_root: Path, name: str) -> Path | None:
    doctrines_dir = entity_location(project_root, "doctrine")
    direct = doctrines_dir / f"{name}.yaml"
    if direct.exists():
        return direct
    if not doctrines_dir.exists():
        return None
    match = next(iter(doctrines_dir.rglob(f"{name}.yaml")), None)
    return match


def _codex_schema_selector(
    meta: dict, filepath: Path, project_root: Path
) -> str:
    """Pick the right schema for a codex doc at write time.

    Path-derived doc_type (sources/* → codex-source; else codex). Also
    enforces the id ↔ filename-stem invariant (codex-CRUD spec §C.2)
    before any write — raises ValueError on drift.
    """
    expected_id = filepath.stem  # "<name>.md" → "<name>"
    if meta.get("id") != expected_id:
        raise ValueError(
            f"Frontmatter id '{meta.get('id')}' does not match filename '{expected_id}'."
        )
    doc_type = _codex_mod._resolve_doc_type_from_path(project_root, filepath)
    return _codex_mod._DOC_TYPE_SCHEMAS[doc_type]


_KINDS: dict[str, _KindConfig] = {
    "knight": _KindConfig(
        kind="knight",
        schema_kind="knight-frontmatter",
        extension=".md",
        shape="md_fm",
        locator=_knight_mod._find_knight,
    ),
    "doctrine": _KindConfig(
        kind="doctrine",
        schema_kind="doctrine-yaml",
        extension=".yaml",
        shape="yaml",
        locator=_doctrine_locator,
    ),
    "artifact": _KindConfig(
        kind="artifact",
        schema_kind="artifact-frontmatter",
        extension=".md",
        shape="md_fm",
        locator=_artifact_mod._find_artifact,
    ),
    "watcher": _KindConfig(
        kind="watcher",
        schema_kind="watcher-yaml",
        extension=".yaml",
        shape="yaml",
        locator=_watcher_mod._find_watcher,
    ),
    "codex": _KindConfig(
        kind="codex",
        schema_kind=_codex_schema_selector,
        extension=".md",
        shape="md_fm",
        locator=_codex_mod._find_document,
    ),
}


# ---------------------------------------------------------------------------
# CLI helper — schema-driven scalar coercion.
# ---------------------------------------------------------------------------


def _coerce_scalar_for_schema(
    schema_kind: str,
    field: str,
    raw_str: str,
    project_root: Path | None = None,
) -> object:
    """Coerce a CLI-supplied string to the right Python type per the schema.

    String-typed fields: passthrough.
    Integer: ``int(raw_str)`` — raises ``ValueError`` with a field-named message.
    Boolean: case-insensitive ``true`` / ``false`` — anything else raises.
    Array-of-string: comma-split, stripped, empty-element-dropped.
    Array-of-structured (items have ``type: object`` or ``$ref``):
        rejected — CLI must use ``-f``.
    Unknown field: passthrough (let schema validation reject downstream).

    With ``project_root`` the merged (packaged + overlay) schema is consulted,
    so a custom field declared in ``.lore/custom-schemas/`` coerces by its own
    declared type rather than falling through as an unknown field.
    """
    schema = (
        _schemas.resolve_merged_schema(schema_kind, project_root)
        if project_root is not None
        else _schemas.load_schema(schema_kind)
    )
    props = schema.get("properties", {})
    spec = props.get(field)
    if spec is None:
        return raw_str
    type_ = spec.get("type")
    if type_ == "string":
        return raw_str
    if type_ == "integer":
        try:
            return int(raw_str)
        except ValueError as exc:
            raise ValueError(
                f"Field {field!r} expects integer, got: {raw_str!r}"
            ) from exc
    if type_ == "boolean":
        lowered = raw_str.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        raise ValueError(
            f"Field {field!r} expects boolean (true/false), got: {raw_str!r}"
        )
    if type_ == "array":
        items = spec.get("items") or {}
        item_type = items.get("type")
        if "$ref" in items or item_type == "object":
            raise ValueError(
                f"Field {field!r} contains structured items; use -f to edit."
            )
        # Array of scalars — comma split, strip, drop empties.
        return [el.strip() for el in raw_str.split(",") if el.strip()]
    # Unknown/unsupported type — passthrough; schema validate will judge.
    return raw_str


# ---------------------------------------------------------------------------
# Internal helpers.
# ---------------------------------------------------------------------------


def _parse_md_fm(text: str, kind: str) -> tuple[dict, str]:
    """Split a markdown+frontmatter file into (frontmatter_dict, body_str).

    Raises ValueError on parse failure or non-mapping frontmatter.
    The body string is the raw remainder after the second ``---`` delimiter
    (no leading-newline trimming).
    """
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Cannot parse existing {kind}: missing frontmatter")
    try:
        meta = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        raise ValueError(f"Cannot parse existing {kind}: {exc}") from exc
    if not isinstance(meta, dict):
        raise ValueError("Frontmatter is not a mapping")
    return meta, parts[2]


def _parse_yaml_only(text: str, kind: str) -> dict:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"Cannot parse existing {kind}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Frontmatter is not a mapping")
    return data


def _serialize_md_fm(meta: dict, body: str) -> str:
    fm_text = yaml.dump(
        meta, default_flow_style=False, allow_unicode=True, sort_keys=False
    )
    return "---\n" + fm_text + "---" + body


def _serialize_yaml(meta: dict) -> str:
    return yaml.dump(
        meta, default_flow_style=False, allow_unicode=True, sort_keys=False
    )


def _atomic_write(filepath: Path, text: str) -> None:
    """Write text to filepath atomically via tempfile + os.replace."""
    parent = filepath.parent
    parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=filepath.name + ".", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_path, filepath)
    except Exception:
        # Best-effort cleanup; raise the original exception.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _apply_mutations(
    meta: dict,
    *,
    set_fields: dict | None,
    unset_fields: list | None,
    add_to_list: dict | None,
    remove_from_list: dict | None,
) -> dict:
    """Apply the four mutation kinds in fixed order. Returns the mutated dict.

    Mutates a shallow copy of ``meta`` — caller's input is untouched.
    """
    out = dict(meta)
    if set_fields:
        for key, value in set_fields.items():
            out[key] = value
    if unset_fields:
        for key in unset_fields:
            out.pop(key, None)
    if add_to_list:
        for key, values in add_to_list.items():
            existing = out.get(key)
            if existing is None:
                # Bootstrap as new list (will be schema-validated).
                out[key] = list(values)
                continue
            if not isinstance(existing, list):
                raise ValueError(
                    f"Field {key!r} is not a list; cannot add/remove."
                )
            new_list = list(existing)
            for v in values:
                if v not in new_list:
                    new_list.append(v)
            out[key] = new_list
    if remove_from_list:
        for key, values in remove_from_list.items():
            existing = out.get(key)
            if existing is None:
                continue  # idempotent no-op
            if not isinstance(existing, list):
                raise ValueError(
                    f"Field {key!r} is not a list; cannot add/remove."
                )
            new_list = [v for v in existing if v not in values]
            out[key] = new_list
    return out


# ---------------------------------------------------------------------------
# Public entry point.
# ---------------------------------------------------------------------------


def update_frontmatter_fields(
    project_root: Path,
    kind: str,
    name: str,
    *,
    set_fields: dict | None = None,
    unset_fields: list | None = None,
    add_to_list: dict | None = None,
    remove_from_list: dict | None = None,
) -> dict:
    """Mutate frontmatter fields of one file-backed entity.

    Body bytes are passed through verbatim. Schema validation runs against
    the mutated frontmatter BEFORE any disk write; on failure the file is
    untouched. Write is atomic via ``tempfile`` + ``os.replace``.

    Returns ``{"id": name, "filename": <filename>, "updated_at": None}`` on
    success. Raises ``ValueError`` on any validation / lookup / schema
    failure.
    """
    # 1. kind validation
    if kind not in _KINDS:
        raise ValueError(f"Unknown kind: {kind}")
    cfg = _KINDS[kind]

    # 2. name validation
    name_err = _validators.validate_name(name)
    if name_err:
        raise ValueError(name_err)

    # 3. mode-arg validation — at least one mutation group non-empty
    if not (set_fields or unset_fields or add_to_list or remove_from_list):
        raise ValueError("No frontmatter mutations supplied.")

    # 4. locate file
    filepath = cfg.locator(project_root, name)
    if filepath is None:
        raise ValueError(f'{kind.capitalize()} "{name}" not found.')

    text = filepath.read_text()

    # 5. parse
    if cfg.shape == "md_fm":
        meta, body = _parse_md_fm(text, kind)
    else:
        meta = _parse_yaml_only(text, kind)
        body = None

    # 6. apply mutations (in fixed order — see _apply_mutations)
    mutated = _apply_mutations(
        meta,
        set_fields=set_fields,
        unset_fields=unset_fields,
        add_to_list=add_to_list,
        remove_from_list=remove_from_list,
    )

    # 7. schema-validate result BEFORE any disk write
    schema_kind = (
        cfg.schema_kind(mutated, filepath, project_root)
        if callable(cfg.schema_kind)
        else cfg.schema_kind
    )
    # Overlays govern canonical codex docs and sources; transient working docs
    # (and every non-codex kind) resolve the packaged schema.
    overlay_root = _codex_mod._overlay_root(project_root, filepath)
    issues = _schemas.validate_entity(schema_kind, mutated, project_root=overlay_root)
    if issues:
        raise ValueError("\n".join(i.message for i in issues))

    # 8. serialize + atomic write
    if cfg.shape == "md_fm":
        new_text = _serialize_md_fm(mutated, body or "")
    else:
        new_text = _serialize_yaml(mutated)
    _atomic_write(filepath, new_text)

    # 9. return envelope
    return {
        "id": name,
        "filename": filepath.name,
        "updated_at": None,
    }
