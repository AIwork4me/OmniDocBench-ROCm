"""Model Card v2 helpers (ADR-0007).

A v2 card holds one ``result_record`` per platform+backend+precision+benchmark
combination. This module provides:

  * :func:`make_result_id` — a UNIQUE and REPRODUCIBLE id for a combination
    (deterministic slug of the tuple + a 12-hex sha256 suffix). Same inputs always
    yield the same id; different tuples never collide.
  * :func:`derive_platforms` — the platforms array is DERIVED from the results,
    never hand-written.
  * :func:`validate_card_v2` — full structural validation: schema + the v2
    invariants (platforms match derivation, result_ids unique, primary_result_id
    resolves, no model-wide assurance/badge propagation).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from . import assurance
from .schema import iter_validation_errors, validate_artifact

DEFAULT_BENCHMARK = {"name": "OmniDocBench", "version": "v1.6"}


def _slug(value: Any) -> str:
    """Lowercase alphanumeric slug; non-alnum collapses to '-'; empty -> 'x'."""
    s = "".join(c if c.isalnum() else "-" for c in str(value).lower()).strip("-")
    return s or "x"


def result_tuple(*, model_id: str, platform: str, backend: str = "",
                 precision: str = "", benchmark_version: str = "") -> tuple:
    """The canonical tuple a result_id is derived from."""
    return (str(model_id), str(platform), str(backend or "default"),
            str(precision or "default"), str(benchmark_version or "v1.6"))


def make_result_id(*, model_id: str, platform: str, backend: str = "",
                   precision: str = "", benchmark_version: str = "") -> str:
    """Return a unique, reproducible result_id for the combination.

    Shape: ``<model>__<platform>__<backend>__<precision>__<bench>__<sha12>``.
    The 12-hex sha256 of the canonical tuple guarantees uniqueness even when two
    human slugs collide, while keeping the id reproducible (same tuple -> same id).
    """
    tup = result_tuple(model_id=model_id, platform=platform, backend=backend,
                       precision=precision, benchmark_version=benchmark_version)
    canon = json.dumps(list(tup), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canon.encode("utf-8")).hexdigest()[:12]
    model_id_s = _slug(model_id)
    return "__".join([
        model_id_s,
        _slug(platform),
        _slug(backend or "default"),
        _slug(precision or "default"),
        _slug(benchmark_version or "v1.6"),
        digest,
    ])


def derive_platforms(results: list[dict]) -> list[str]:
    """Return the sorted, de-duplicated platforms implied by the results.

    Platforms are NEVER hand-written in v2 — they are the set of
    ``coverage.platform`` values present across the result records.
    """
    plats = []
    for res in results or []:
        cov = res.get("coverage") or {}
        plat = cov.get("platform")
        if plat and plat not in plats:
            plats.append(plat)
    return sorted(plats)


def derive_primary_result_id(card: dict) -> str | None:
    """The explicit primary_result_id if set; else None (NEVER auto-pick highest).

    ADR-0012: the primary result is an explicit maintainer choice. We do not
    infer it from the highest score.
    """
    return card.get("primary_result_id")


def result_id_duplicates(results: list[dict]) -> list[str]:
    """Return the result_ids that appear more than once (empty = all unique)."""
    seen: dict[str, int] = {}
    for res in results or []:
        rid = res.get("result_id")
        if rid is not None:
            seen[rid] = seen.get(rid, 0) + 1
    return sorted(rid for rid, n in seen.items() if n > 1)


def validate_card_v2(card: dict) -> list[str]:
    """Return all structural problems with a v2 card (empty = valid).

    Checks: JSON-schema validity (incl. RFC3339/sha256 formats), platforms match
    the derivation when present, result_ids are unique, primary_result_id (if set)
    resolves to a real result, no model-wide assurance/badge propagation field.
    """
    problems: list[str] = []
    problems += [f"schema: {m}" for m in iter_validation_errors("model_card_v2", card)]
    results = card.get("results") or []

    # platforms must equal the derivation when present
    if "platforms" in card:
        derived = derive_platforms(results)
        if sorted(card["platforms"]) != sorted(derived):
            problems.append(f"platforms {card['platforms']!r} != derived {derived!r} "
                            "(platforms are derived from results; remove or correct)")

    # result_id uniqueness
    for dup in result_id_duplicates(results):
        problems.append(f"duplicate result_id: {dup!r}")

    # primary_result_id must resolve
    primary = card.get("primary_result_id")
    if primary is not None:
        ids = {r.get("result_id") for r in results}
        if primary not in ids:
            problems.append(f"primary_result_id {primary!r} does not match any result_id")

    # per-result assurance validity + no cross-result propagation
    problems += assurance.validate_results_assurance(results)
    propagated = assurance.check_no_propagation(card)
    if propagated:
        problems.append(f"model-wide assurance/badge field(s) {propagated!r} imply cross-result "
                        "propagation — set assurance per result (ADR-0008)")

    # status sanity: a status must be one of the enum (schema already enforces,
    # but surface a clearer message for the common retraction case)
    for i, res in enumerate(results):
        st = res.get("status")
        if st not in (None, "valid", "invalid", "retracted", "superseded"):
            problems.append(f"results[{i}]: bad status {st!r}")
    return problems


def assert_card_v2(card: dict) -> None:
    """Raise ValueError if the card has any structural problem."""
    problems = validate_card_v2(card)
    if problems:
        raise ValueError("invalid model_card_v2: " + "; ".join(problems))


def normalize_card_v2(card: dict) -> dict:
    """Return a canonical copy: platforms derived, results sorted by result_id.

    Deterministic normalization is what makes the generator output stable and
    the migration idempotent (migrate(migrate(x)) == migrate(x)).
    """
    out = dict(card)
    out["schema_version"] = 2
    results = sorted(card.get("results") or [], key=lambda r: r.get("result_id", ""))
    out["results"] = results
    out["platforms"] = derive_platforms(results)
    return out
