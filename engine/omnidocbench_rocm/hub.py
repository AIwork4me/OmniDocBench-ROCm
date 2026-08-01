"""Central Hub: deterministic generation + drift checking (Round-2 ADR-0012/0013).

The public Hub (``hub/canonical_results.json`` + the README generated-results
block + the comparison table) is DERIVED, never hand-maintained. Its only
authoritative inputs are:

    hub/imports/<model>/<result>/   (immutable source imports)
    + the per-import platform_review (central review records)

This module provides:

  * :func:`generate_hub` — derive canonical result rows from the imports store;
  * :func:`check_drift` — find fact drift between the canonical file, the imports,
    and a legacy registry (old scores, default/default stubs, missing sources,
    duplicate ids, verified-badge-without-review).

Scores NEVER come from the registry; assurance is always split into
producer_assurance + platform_review. Pure data functions (no network).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from . import assurance as A
from . import source_import as SI


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #

def load_canonical(path: Path | str) -> list[dict]:
    """Read hub/canonical_results.json -> its ``results`` list (or [] )."""
    p = Path(path)
    if not p.exists():
        return []
    doc = json.loads(p.read_text(encoding="utf-8"))
    return doc.get("results") or []


def load_imports_store(hub_dir: Path | str) -> list[dict]:
    """All persisted import_records under hub/imports/."""
    return [rec for _, _, rec in SI.iter_imports(hub_dir)]


# --------------------------------------------------------------------------- #
# generation
# --------------------------------------------------------------------------- #

def generate_hub(hub_dir: Path | str) -> dict:
    """Derive the canonical_results document from the imports store.

    Deterministic: rows are sorted by (model_id, result_id). A row carries its
    immutable ``source`` so the Hub is traceable. Scores come verbatim from each
    imported result; assurance is split. Superseded/retracted/invalid rows are
    RETAINED (history) but flagged so the renderer can hide them by default.
    """
    rows = [SI.to_public_row(rec) for rec in load_imports_store(hub_dir)]
    rows.sort(key=lambda r: (str(r.get("model_id")), str(r.get("result_id"))))
    return {"schema_version": 2,
            "source_of_truth": "derived from hub/imports/ (Round-2 ADR-0013); README + table are derived",
            "results": rows}


def rebuild_canonical(hub_dir: Path | str) -> dict:
    """Rebuild the FULL canonical_results document: quarantined legacy rows
    (from ``hub/legacy/``, valid→superseded) + every imported result
    (from ``hub/imports/``). This is the single deterministic producer of the
    public Hub's canonical store (Round-2 §8/§9) — run it after any import
    change; ``regen_hub`` wires it together with the README regeneration.

    Schema-validates every row (raises on any invalid). Idempotent.
    """
    from .schema import iter_validation_errors
    hub_dir = Path(hub_dir)
    rows: list[dict] = []
    legacy_path = hub_dir / "legacy" / "canonical_results.legacy.json"
    if legacy_path.exists():
        for r in json.loads(legacy_path.read_text(encoding="utf-8")).get("results", []):
            r2 = dict(r)
            if r2.get("status") == "valid":           # quarantine old default/default stubs
                r2["status"] = "superseded"
            rows.append(r2)
    for _model, _rid, rec in SI.iter_imports(hub_dir):
        rows.append(SI.to_public_row(rec))
    problems = [f"canonical[{i}] {r.get('result_id')}: {m}"
                for i, r in enumerate(rows) for m in iter_validation_errors("canonical_result", r)]
    if problems:
        raise ValueError("invalid canonical rows:\n  - " + "\n  - ".join(problems[:8]))
    rows.sort(key=lambda r: (str(r.get("model_id")), str(r.get("result_id"))))
    return {"schema_version": 2,
            "source_of_truth": "derived from hub/imports/ (ADR-0013); quarantined legacy retained from hub/legacy/.",
            "results": rows}


# --------------------------------------------------------------------------- #
# drift
# --------------------------------------------------------------------------- #

def _is_defaultish(v) -> bool:
    return v in ("", "default", None)


def check_drift(*, canonical_rows: list[dict], imports: list[dict] | None = None,
                registry_scores: dict | None = None) -> list[dict]:
    """Return a list of machine-readable drift findings (empty = no drift).

    Each finding: {kind, severity, result_id?, detail}. Findings:

      * ``default-default-identity``  a VALID canonical row whose backend/precision
        is default/empty (the v2 anti-pattern; Round-2 §3.3/§9.2).
      * ``missing-source``            a canonical row with no immutable source
        (registry-only stub; not actually imported — Round-2 §3.1).
      * ``score-mismatch``            a canonical row's overall != its import's.
      * ``duplicate-result-id``       a result_id appears more than once.
      * ``registry-score-as-fact``    a legacy registry score disagrees with the
        canonical row (old score must NOT be a fact source — §3.6).
      * ``verified-without-review``   a row implies a verified/score-reproduced
        assurance but has no platform_review backing it (§11).
    """
    imports = imports or []
    findings: list[dict] = []

    by_id: dict[str, int] = {}
    imports_by_id = {((r.get("imported_result") or {}).get("result_id")): r for r in imports}

    # The registry mirrors ONLY the PRIMARY result per (model, platform) (ADR-0016);
    # alternate backends legitimately carry different scores. So registry-score-as-
    # fact must compare against the primary row only — never alternates (else every
    # multi-backend repo would false-positive). Mirrors registry.check() primary-per-track.
    primary_rids: set[str] = set()
    _groups: dict[tuple, list[dict]] = {}
    for _r in canonical_rows:
        if _r.get("status", "valid") != "valid":
            continue
        _groups.setdefault((_r.get("model_id"), _r.get("platform")), []).append(_r)
    for _rs in _groups.values():
        _prims = [r for r in _rs if r.get("primary") is True]
        rep = _prims[0] if len(_prims) == 1 else _rs[0]
        if rep.get("result_id") is not None:
            primary_rids.add(rep["result_id"])

    for row in canonical_rows:
        rid = row.get("result_id")
        by_id[rid] = by_id.get(rid, 0) + 1
        status = row.get("status", "valid")

        # default/default anti-pattern on a VALID row
        if status == "valid":
            if _is_defaultish(row.get("backend")) or _is_defaultish(row.get("precision")):
                findings.append({"kind": "default-default-identity", "severity": "high",
                                 "result_id": rid,
                                 "detail": f"valid row backend={row.get('backend')!r} "
                                           f"precision={row.get('precision')!r}; a valid result must not be default/default"})

        # missing immutable source — only a PUBLIC (valid) result must carry one;
        # superseded/retracted/invalid legacy rows are retained for history and
        # are not held to the public-source requirement (Round-2 §8).
        if status == "valid" and not row.get("source"):
            findings.append({"kind": "missing-source", "severity": "medium",
                             "result_id": rid,
                             "detail": "canonical row has no immutable source reference (registry-only stub; not imported)"})

        # score mismatch vs its import
        imp = imports_by_id.get(rid)
        if imp is not None:
            src_overall = ((imp.get("imported_result") or {}).get("metrics") or {}).get("overall")
            if src_overall is not None and row.get("overall") is not None \
                    and abs(src_overall - row["overall"]) > 1e-9:
                findings.append({"kind": "score-mismatch", "severity": "high",
                                 "result_id": rid,
                                 "detail": f"canonical overall {row['overall']} != imported {src_overall}"})

        # registry score as fact source — ONLY for the primary row of each
        # (model, platform); the registry mirrors the primary, so an alternate
        # backend's different score is NOT drift (ADR-0016).
        if registry_scores and rid in primary_rids:
            reg = (registry_scores.get(rid)
                   or registry_scores.get(row.get("model_id"))
                   or registry_scores.get((row.get("model_id"), row.get("platform"))))
            if row.get("overall") is not None and reg is not None \
                    and abs(reg - row["overall"]) > 1e-9:
                findings.append({"kind": "registry-score-as-fact", "severity": "high",
                                 "result_id": rid,
                                 "detail": f"registry score {reg} != canonical {row['overall']} (registry is not a fact source)"})

        # verified-without-review — a reproduction claim (in `assurance` OR the
        # retained `source_assurance`) without an accepted platform_review is a
        # claim the platform has not backed (ADR-0013). Checking source_assurance
        # catches imports whose original *-reproduced claim was honestly mapped to
        # producer_assurance but still requires review before it counts.
        pr = row.get("platform_review") or {}
        claim = None
        for _field in ("assurance", "source_assurance"):
            _v = row.get(_field)
            if _v in ("score-reproduced", "inference-reproduced", "cross-hardware-reproduced"):
                claim = (_field, _v)
                break
        if claim and pr.get("status") != "accepted":
            findings.append({"kind": "verified-without-review", "severity": "high",
                             "result_id": rid,
                             "detail": f"{claim[0]}={claim[1]!r} but platform_review.status={pr.get('status')!r} (no review record backs the reproduction claim)"})

    for rid, n in by_id.items():
        if n > 1:
            findings.append({"kind": "duplicate-result-id", "severity": "high",
                             "result_id": rid, "detail": f"result_id appears {n} times (must be globally unique)"})

    # unknown-identity assurance ceiling (Round-2 P0-5): a result whose
    # producer_assurance exceeds `submitted` but whose run_spec reproduction-
    # critical fields are unknown is overclaiming producer evidence depth — the
    # platform did not receive reproduction-pinning inputs. Reported, NOT
    # auto-downgraded (a downgrade is a maintainer decision, never automatic).
    from . import run_spec as rs
    for row in canonical_rows:
        if row.get("status", "valid") != "valid":
            continue
        if row.get("producer_assurance") != "evidence-complete":
            continue
        rec = imports_by_id.get(row.get("result_id"))
        spec = (rec.get("imported_result") or {}).get("run_spec") if rec else None
        if isinstance(spec, dict):
            unk = rs.unknown_reproduction_critical(spec)
            if unk:
                findings.append({"kind": "unknown-identity-assurance-ceiling",
                                 "severity": "high", "result_id": row.get("result_id"),
                                 "detail": f"producer_assurance=evidence-complete but reproduction-critical "
                                           f"identity unknown {unk} (P0-5: cap at submitted until pinned)"})

    # multiple primaries per (model_id, comparison_track_id) — Standard §7.3.
    # NOTE: registry.check keys on (model, platform) to permit multi-backend
    # results (ADR-0016, enshrined in test_primary_per_track). This is the
    # STRICTER track-level uniqueness the Standard §7.3 mandates, reported
    # separately so a maintainer can reconcile the two semantics (e.g. mineru2.5
    # has one primary per platform but two on the full track across platforms).
    # Reported, NOT auto-demoted.
    _prim: dict[tuple, list[str]] = {}
    for row in canonical_rows:
        if row.get("status", "valid") != "valid" or row.get("primary") is not True:
            continue
        key = (row.get("model_id"), row.get("comparison_track_id"))
        _prim.setdefault(key, []).append(str(row.get("result_id")))
    for (mid, tid), rids in _prim.items():
        if len(rids) > 1:
            findings.append({"kind": "multiple-primaries-per-track", "severity": "high",
                             "result_id": rids[0],
                             "detail": f"{len(rids)} primary results for model={mid!r} "
                                       f"track={tid!r}: {rids} (Standard §7.3: at most one "
                                       "primary per model+track)"})

    return findings
