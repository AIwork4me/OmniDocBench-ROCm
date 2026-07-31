"""Result Identity v3 — run_spec + run_spec_hash (Round-2 ADR-0015).

v2 identity (:func:`model_card_v2.make_result_id`) derived an id from only
``(model, platform, backend, precision, benchmark_version)`` and — critically —
*masked* a missing backend/precision as the literal ``"default"``. That made two
scientifically-different runs collapse to one id, and let a central platform
fabricate a ``default/default`` result that no sub-repo ever produced (the drift
Round-2 exists to kill).

Identity v3 derives the id from the FULL run specification:

    run_spec = {model, implementation, benchmark, inference}
    run_spec_hash = sha256(canonical_json(run_spec))
    result_id_v3  = "<model-slug>-<benchmark-slug>-<short16hex>"

Rules enforced here (Round-2 §3.3):

  * Same run_spec -> same hash -> same id (deterministic, reproducible).
  * Any scientifically-material field change -> a different hash -> a new id.
  * A field whose value is genuinely unknown MUST be the literal string
    ``"unknown"`` — never masked as ``"default"``. ``"default"`` is treated as a
    malformed/legacy value and flagged.
  * A valid result that still carries backend/precision == 'default' is
    ``insufficient identity`` and is barred from the default comparison table.
  * Legacy v2 result_ids are preserved verbatim in ``legacy_result_ids``; nothing
    is silently overwritten.

This module is PURE (no I/O, no network) so it is safe to import at package
import time and trivially unit-testable.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

UNKNOWN = "unknown"
DEFAULT = "default"  # the v2 anti-pattern sentinel — a valid result must NOT use it

# The full, scientifically-material identity surface (Round-2 §3.3). A result
# whose value for ANY of these is absent OR == UNKNOWN has *insufficient
# identity* for the default comparison table (the id is still well-formed; the
# result is just not allowed into head-to-head comparison until completed).
CRITICAL_IDENTITY_FIELDS = (
    "model.model_id",
    "implementation.implementation_id",
    "implementation.platform",
    "implementation.backend",
    "implementation.precision",
    "benchmark.benchmark_id",
    "benchmark.benchmark_version",
)


def _slug(value: Any) -> str:
    """Lowercase alphanumeric slug; non-alnum collapses to '-'; empty -> 'x'."""
    s = "".join(c if c.isalnum() else "-" for c in str(value).lower()).strip("-")
    return s or "x"


def canonical_json(obj: Any) -> str:
    """Deterministic JSON serialization used for hashing.

    Dict keys are sorted recursively; separators are compact; non-ASCII is kept
    verbatim (encoded as UTF-8 bytes for hashing). Lists keep their order — list
    order IS scientifically meaningful (e.g. a multi-GPU topology), so it is part
    of the identity, not normalized away.
    """
    return json.dumps(_sort_keys(obj), sort_keys=False, separators=(",", ":"),
                      ensure_ascii=False)


def _sort_keys(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _sort_keys(obj[k]) for k in sorted(obj, key=str)}
    if isinstance(obj, list):
        return [_sort_keys(v) for v in obj]
    return obj


def run_spec_hash(run_spec: dict) -> str:
    """``sha256:<64hex>`` of the canonical JSON of ``run_spec``."""
    if not isinstance(run_spec, dict):
        raise TypeError(f"run_spec must be a dict, got {type(run_spec).__name__}")
    digest = hashlib.sha256(canonical_json(run_spec).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def short_hash(run_spec: dict, n: int = 16) -> str:
    """First ``n`` hex chars of the run_spec hash (default 16; collision-safe for
    the current dataset scope — see ADR-0015)."""
    return run_spec_hash(run_spec)[len("sha256:"): len("sha256:") + n]


def make_result_id_v3(model_id: str, benchmark_id: str, run_spec: dict,
                      short_len: int = 16) -> str:
    """Deterministic v3 result id: ``<model>-<benchmark>-<short16hex>``.

    Same run_spec -> same id; any material change -> a different id.
    """
    return f"{_slug(model_id)}-{_slug(benchmark_id)}-{short_hash(run_spec, short_len)}"


def _dotted(run_spec: dict, path: str) -> Any:
    cur: Any = run_spec
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def missing_critical(run_spec: dict) -> list[str]:
    """Critical identity fields that are ABSENT (not set at all).

    These are a hard error: a result must at minimum *state* each critical field,
    even if the value is the explicit literal ``unknown``.
    """
    return [p for p in CRITICAL_IDENTITY_FIELDS if _dotted(run_spec, p) is None]


def insufficient_identity(run_spec: dict) -> list[str]:
    """Critical fields that are absent OR explicitly ``unknown``.

    A result with insufficient identity is well-formed (its id is still computed)
    but is barred from the DEFAULT comparison table until the identity is
    completed (Round-2 §3.3 req 10). Never auto-promote it.
    """
    out: list[str] = []
    for p in CRITICAL_IDENTITY_FIELDS:
        v = _dotted(run_spec, p)
        if v is None or v == UNKNOWN:
            out.append(p)
    return out


def uses_default_sentinel(run_spec: dict) -> list[str]:
    """Critical fields still carrying the legacy ``default`` mask (the v2 bug).

    A valid result must not use ``default`` for backend/precision — Round-2 §3.3
    req 8. Returns the offending dotted paths (empty = clean).
    """
    flagged = []
    for p in ("implementation.backend", "implementation.precision"):
        if _dotted(run_spec, p) == DEFAULT:
            flagged.append(p)
    return flagged


def build_run_spec(*, model: dict | None = None, implementation: dict | None = None,
                   benchmark: dict | None = None, inference: dict | None = None) -> dict:
    """Assemble a run_spec dict from its four sub-objects (all optional).

    Missing sub-objects become empty dicts; the caller is responsible for setting
    each critical field explicitly (use :func:`missing_critical` to check).
    """
    return {
        "model": dict(model or {}),
        "implementation": dict(implementation or {}),
        "benchmark": dict(benchmark or {}),
        "inference": dict(inference or {}),
    }
