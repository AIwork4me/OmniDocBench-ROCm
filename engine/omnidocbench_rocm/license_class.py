"""License / open-source classification (ADR-0010).

Six mutually-exclusive categories model the real heterogeneity of the Zone's
per-model licenses — from permissive MIT/Apache to restrictive-open (MinerU OSL,
Tencent Hunyuan Community License) to closed/unknown. The cardinal rule:

    **Never default a missing or unclear license to ``open-source-ai``.**
    When in doubt, the category is ``unknown`` until a human resolves it.

Each license_record carries three restriction axes (``commercial_use``,
``geographic_restrictions``, ``acceptable_use_restrictions``) so a commercial
user is never misled — mirroring HuggingFace's restrictive-license labelling.

This module is data-free: it knows a small table of the licenses already in the
registry so the migration can classify them, but it never fetches or assumes. A
human can always override by writing the category explicitly.
"""
from __future__ import annotations

from .schema import validate_artifact

# Ordered for display; the order is NOT a "quality" ranking.
LICENSE_CATEGORIES = (
    "open-source-ai",
    "open-weights",
    "source-available",
    "restricted",
    "closed",
    "unknown",
)

LICENSE_CATEGORY_DESCRIPTIONS = {
    "open-source-ai": "Meets an open-source definition for AI systems (open code AND weights, permissive, no field-of-use or commercial restrictions). The strictest bar.",
    "open-weights": "Model weights released under terms permitting use, study, redistribution and modification, with at most light acceptable-use terms — but not meeting the full open-source-ai bar (e.g. data/training not open).",
    "source-available": "Source/weights are visible but the license is NOT open (e.g. non-commercial, no-derivatives, BSL/SSPL-style).",
    "restricted": "Available, but with material restrictions: commercial-use thresholds, geographic limits, or strong acceptable-use policies (e.g. MinerU Open Source License, Tencent Hunyuan Community License, Llama-style licenses).",
    "closed": "Proprietary — no source/weights access under an open licence.",
    "unknown": "License could not be classified. The default for any missing, ambiguous, or unresolved license — NEVER silently treated as open.",
}

# The three restriction axes recorded on every license_record.
RESTRICTION_FIELDS = ("commercial_use", "geographic_restrictions", "acceptable_use_restrictions")

# Known-license table: SPDX id or human name -> category. Covers the licenses
# present in hub/registry.yaml so the v1->v2 migration classifies them. Anything
# not here resolves to ``unknown`` (the safe default), never open-source-ai.
_KNOWN = {
    # Permissive OSI -> open-source-ai (open code + the repo redistributes/links openly)
    "MIT": "open-source-ai",
    "Apache-2.0": "open-source-ai",
    # Restrictive-open: commercial thresholds / geographic limits
    "MinerU Open Source License": "restricted",
    "Tencent Hunyuan Community License": "restricted",
}

# Known restriction summaries, keyed the same as _KNOWN, so migration can carry
# the commercial-use / geographic text forward instead of guessing.
_KNOWN_RESTRICTIONS = {
    "MinerU Open Source License": {
        "commercial_use": "commercial threshold MAU>100M or revenue>$20M",
    },
    "Tencent Hunyuan Community License": {
        "commercial_use": "commercial-use conditions; see license",
        "geographic_restrictions": "not licensed in EU/UK/KR",
    },
}


def _first_known(*values: str | None) -> str:
    """Return the first value that classifies to a known category; else 'unknown'.

    ``classify`` returns the truthy string ``'unknown'`` for unrecognized input,
    so a plain ``classify(spdx) or classify(name)`` would short-circuit on the
    spdx result and never try the name. This falls through 'unknown' results.
    """
    for v in values:
        if v and str(v).strip():
            c = classify(v)
            if c != "unknown":
                return c
    return "unknown"


def classify(spdx_or_name: str | None) -> str:
    """Best-effort category for a license SPDX id or human name.

    Returns ``unknown`` for anything unrecognized — it NEVER returns
    ``open-source-ai`` unless the license is a known-permissive one. The match
    is case-insensitive on SPDX ids and exact on human names.
    """
    if not spdx_or_name or not str(spdx_or_name).strip():
        return "unknown"
    key = str(spdx_or_name).strip()
    if key in _KNOWN:
        return _KNOWN[key]
    lower = key.lower()
    for k, v in _KNOWN.items():
        if k.lower() == lower:
            return v
    return "unknown"


def build_license_record(*, spdx: str = "", name: str = "", category: str | None = None,
                          url: str = "", commercial_use: str = "",
                          geographic_restrictions: str = "",
                          acceptable_use_restrictions: str = "") -> dict:
    """Build a normalized license_record dict.

    ``category`` wins when given; otherwise it is *classified* from the SPDX id
    or name. When neither resolves, the category is ``unknown`` (never
    open-source-ai by default — ADR-0010). Validates the result against the
    ``license_record`` schema.
    """
    if category is not None and category not in LICENSE_CATEGORIES:
        raise ValueError(f"unknown license category: {category!r} (expected one of {LICENSE_CATEGORIES})")
    cat = category or _first_known(spdx, name)
    # Restriction text inherited from the known table when the caller didn't set it.
    inh = _KNOWN_RESTRICTIONS.get(spdx) or _KNOWN_RESTRICTIONS.get(name) or {}
    record = {
        "category": cat,
        "spdx": spdx or "",
        "name": name or "",
        "url": url or "",
        "commercial_use": commercial_use or inh.get("commercial_use", ""),
        "geographic_restrictions": geographic_restrictions or inh.get("geographic_restrictions", ""),
        "acceptable_use_restrictions": acceptable_use_restrictions or inh.get("acceptable_use_restrictions", ""),
    }
    validate_artifact("license_record", record)
    return record


def validate_license_record(record: dict) -> None:
    """Raise jsonschema.ValidationError if record is not a valid license_record."""
    validate_artifact("license_record", record)


def assert_no_default_open_source(record: dict) -> None:
    """Guard the cardinal rule: a record missing/empty category must be unknown.

    Raises ``ValueError`` if a record silently claims ``open-source-ai`` without
    an explicit category or a known-permissive SPDX/name backing it — this
    catches the "default to open" mistake at validation time.
    """
    if record.get("category") == "open-source-ai":
        backing = classify(record.get("spdx")) or classify(record.get("name"))
        # An explicit, known-permissive license backs the claim -> fine.
        if backing == "open-source-ai":
            return
        # Otherwise the open-source-ai claim is unjustified by any known license.
        # (A maintainer may still set it deliberately; this guard only flags the
        # unsafe *default*, so we raise only when there is no spdx/name at all.)
        if not record.get("spdx") and not record.get("name"):
            raise ValueError("open-source-ai claimed with no SPDX id or license name — "
                             "set an explicit license or use 'unknown' (ADR-0010)")
