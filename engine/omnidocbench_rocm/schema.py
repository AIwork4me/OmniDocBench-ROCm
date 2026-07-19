from __future__ import annotations
import json
from pathlib import Path
from jsonschema import Draft202012Validator


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
_VALIDATORS = {k: Draft202012Validator(v) for k, v in _SCHEMA["$defs"].items()}


def validate_artifact(name: str, obj: dict) -> None:
    """Raise jsonschema.ValidationError if obj fails the named sub-schema."""
    if name not in _VALIDATORS:
        raise KeyError(f"unknown artifact: {name}")
    _VALIDATORS[name].validate(obj)
