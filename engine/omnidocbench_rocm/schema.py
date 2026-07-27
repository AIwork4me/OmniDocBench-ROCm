from __future__ import annotations
import json
from pathlib import Path
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012


def _find_schema() -> Path:
    # 1. installed package data (built wheel)
    pkg = Path(__file__).parent / "data" / "artifact-schema.json"
    if pkg.exists():
        return pkg
    # 2. editable-dev: walk up from this file to the repo root's contracts/
    for parent in Path(__file__).parents:
        cand = parent / "contracts" / "artifact-schema.json"
        if cand.exists():
            return cand
    raise FileNotFoundError("artifact-schema.json not found in package data or contracts/")


SCHEMA_PATH = _find_schema()
_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

# The v2 $defs cross-reference siblings (e.g. model_card_v2 -> result_record /
# license_record via "#/$defs/..."). A per-$def validator built from the bare
# sub-schema cannot resolve those refs (its base URI is empty, and a same-doc
# wrapper "$ref": "#/$defs/x" is resolved against the wrapper itself, not the
# full document). The robust fix: register the WHOLE document under its $id and
# reach each $def through an ABSOLUTE ref ("<$id>#/$defs/<name>"), which
# referencing resolves via the registry regardless of the validator's base URI.
_DOC_ID = _SCHEMA.get("$id", "")
_REGISTRY = Registry().with_resource(
    uri=_DOC_ID,
    resource=Resource.from_contents(_SCHEMA, default_specification=DRAFT202012),
)

# FORMAT_CHECKER enforces `format: date-time` (RFC3339) and `format: date` on the
# v2 result_record / canonical_result $defs. The v1 $defs carry no `format`
# keywords, so enabling this is backward-compatible — existing v1 artifacts are
# unaffected, and v2 artifacts get real RFC3339 enforcement.
_FORMAT_CHECKER = Draft202012Validator.FORMAT_CHECKER
_VALIDATORS = {
    name: Draft202012Validator(
        {"$ref": f"{_DOC_ID}#/$defs/{name}"},
        registry=_REGISTRY,
        format_checker=_FORMAT_CHECKER,
    )
    for name in _SCHEMA["$defs"]
}


def available_artifacts() -> list[str]:
    """Return the sorted list of validatable $def names (v1 + v2)."""
    return sorted(_VALIDATORS)


def validate_artifact(name: str, obj: dict) -> None:
    """Raise jsonschema.ValidationError if obj fails the named sub-schema."""
    if name not in _VALIDATORS:
        raise KeyError(f"unknown artifact: {name}")
    _VALIDATORS[name].validate(obj)


def iter_validation_errors(name: str, obj: dict) -> list[str]:
    """Return a sorted list of human-readable validation errors (empty = valid).

    Unlike :func:`validate_artifact` (which raises on the first error), this
    collects every error so a migration/conformance report can list them all.
    """
    if name not in _VALIDATORS:
        raise KeyError(f"unknown artifact: {name}")
    return sorted(e.message for e in _VALIDATORS[name].iter_errors(obj))
