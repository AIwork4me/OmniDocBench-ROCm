"""v1 -> v2 model-card migration (ADR-0007).

CLI: ``omnidocbench-rocm migrate-model-card input.json [--check|--in-place|--output PATH]``

Rules:
  * **No guessing.** Only fields with a clear v1 source are carried forward;
    unknowns (git_commit, dataset hashes, page_count, precision) are left absent
    and listed in the report under ``fields_not_carried``.
  * **Idempotent.** Migrating an already-v2 card returns it unchanged
    (``migrate(migrate(x)) == migrate(x)``).
  * **Machine-readable report.** Every assumption (e.g. "v1 had a single overall;
    assigned to the highest-badge platform") is recorded, never silent.
  * v1 ``overall`` is singular while ``badge`` is per-platform. The single overall
    is carried onto the PRIMARY platform (highest badge; first on tie); other
    measured platforms get ``overall: null`` and a report note. This is a
    deterministic *projection*, flagged in the report — not a fabrication.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import assurance, license_class, model_card_v2 as mcv2

_BADGE_RANK = {"verified": 3, "community": 2, "community-wanted": 1}
_MEASURED = {"verified", "community"}  # community-wanted == no result on that platform


def _normalize_eval_date(eval_date: str) -> str:
    """Convert a v1 ``YYYY-MM-DD`` eval_date to RFC3339 ``date-time``.

    Already-datetime strings pass through; empty -> "". This is normalization, not
    fabrication (we never invent a timestamp).
    """
    if not eval_date:
        return ""
    s = str(eval_date).strip()
    if "T" in s:
        return s
    # YYYY-MM-DD -> YYYY-MM-DDT00:00:00Z
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return s + "T00:00:00Z"
    return s


def _primary_platform(platforms: list[str], badge: dict) -> str | None:
    """Highest-badge measured platform; first in declaration order on a tie."""
    candidates = [p for p in platforms if _BADGE_RANK.get((badge or {}).get(p), 0) >= 2]
    pool = candidates or platforms
    if not pool:
        return None
    return max(pool, key=lambda p: _BADGE_RANK.get((badge or {}).get(p), 0))


def migrate_v1_to_v2(v1: dict) -> tuple[dict, dict]:
    """Migrate a v1 model card dict to a v2 card + a machine-readable report.

    Raises ``ValueError`` if the input is neither a recognizable v1 nor v2 card.
    """
    sv = v1.get("schema_version")
    if sv == 2:
        v2 = mcv2.normalize_card_v2(v1)
        return v2, {"migrated": False, "already_v2": True, "input_schema_version": 2,
                    "output_schema_version": 2, "model_id": v1.get("model_id"),
                    "results": [], "changes": [], "warnings": [], "fields_not_carried": []}
    if sv != 1:
        raise ValueError(f"unrecognized schema_version {sv!r}; expected 1 or 2")

    model_id = v1.get("model_id", "")
    platforms = list(v1.get("platforms") or [])
    badge = v1.get("badge") or {}
    overall = v1.get("overall")
    submetrics = v1.get("submetrics") or {}
    bench_ver = v1.get("omnidocbench_version") or "v1.6"
    backend = v1.get("backend") or ""
    hw = v1.get("hardware") or {}
    artifacts = v1.get("artifacts") or {}
    eval_dt = _normalize_eval_date(v1.get("eval_date") or "")

    primary = _primary_platform(platforms, badge)
    measured = [p for p in platforms if (badge or {}).get(p) in _MEASURED]

    report = {
        "migrated": True,
        "already_v2": False,
        "input_schema_version": 1,
        "output_schema_version": 2,
        "model_id": model_id,
        "primary_platform": primary,
        "results": [],
        "warnings": [],
        "fields_not_carried": [],
        "changes": [],
    }
    if primary is not None:
        report["primary_platform_assumption"] = (
            "v1 card carried a single `overall`; projected onto the primary platform "
            f"{primary!r} (highest badge; first on tie). Other measured platforms get overall=null.")
    if overall is None:
        report["warnings"].append("v1 overall was null; result carries overall=null")
    # Fields v1 structurally cannot provide — listed, never guessed.
    report["fields_not_carried"] = [
        "git_commit (absent in v1 model_card)",
        "precision (not a v1 concept; default applied)",
        "page_count / full_set (not in v1 card)",
        "dataset_manifest_sha256 (not in v1 card)",
    ]

    results: list[dict] = []
    for plat in platforms:
        b = badge.get(plat)
        if b not in _MEASURED:
            continue  # community-wanted -> no result on this platform
        is_primary = (plat == primary)
        rid = mcv2.make_result_id(model_id=model_id, platform=plat, backend=backend,
                                  precision="", benchmark_version=bench_ver)
        metrics: dict = {}
        if is_primary:
            metrics = {"overall": overall, **submetrics}
        else:
            metrics = {"overall": None}
            report["warnings"].append(
                f"{plat}: measured (badge={b}) but overall not carried (single v1 overall)")
        implementation = {k: v1[k] for k in
                          ("backend", "execution_provider", "backend_family",
                           "compatibility_status", "target_backend") if v1.get(k)}
        coverage = {"platform": plat}
        prov: dict = {}
        if eval_dt:
            prov["created_at_utc"] = eval_dt
        res = {
            "result_id": rid,
            "status": "valid",
            "assurance": assurance.assurance_from_legacy_badge(b),
            "primary": is_primary or None,
            "benchmark": {"name": "OmniDocBench", "version": bench_ver},
            "implementation": implementation or None,
            "coverage": coverage,
            "metrics": metrics,
        }
        if hw:
            res["hardware"] = dict(hw)
        if artifacts:
            res["artifacts"] = dict(artifacts)
        if prov:
            res["provenance"] = prov
        # drop None-valued top-level keys to keep the record clean
        res = {k: v for k, v in res.items() if v is not None}
        results.append(res)
        report["results"].append({
            "result_id": rid, "platform": plat, "assurance": res["assurance"],
            "overall": metrics.get("overall"), "overall_carried": is_primary and overall is not None,
            "source_badge": b,
        })

    v2: dict = {"schema_version": 2, "model_id": model_id, "results": results}
    if v1.get("model_version"):
        v2["model_version"] = v1["model_version"]
    # license -> normalized license_record (no default open-source; unknown when unclear)
    lic_spdx = v1.get("license") or ""
    lic_record = license_class.build_license_record(
        spdx=lic_spdx, name="" if lic_spdx in ("MIT", "Apache-2.0") else lic_spdx,
        commercial_use=v1.get("commercial_use") or "")
    v2["license"] = lic_record
    if lic_record["category"] == "unknown":
        report["warnings"].append(
            f"license {lic_spdx!r} classified unknown — set an explicit category (ADR-0010)")
    if primary is not None:
        primary_rid = next((r["result_id"] for r in results if r.get("coverage", {}).get("platform") == primary), None)
        if primary_rid:
            v2["primary_result_id"] = primary_rid
    v2 = mcv2.normalize_card_v2(v2)
    return v2, report


def migrate_file(input_path: Path | str, *, output: Path | str | None = None,
                 in_place: bool = False, check: bool = False) -> tuple[dict, dict, int]:
    """Migrate a model-card file. Returns ``(v2_dict, report_dict, exit_code)``.

    Modes: ``--check`` (dry-run, no write; exit 0 if already v2, 1 if it would
    change / is invalid), ``--in-place`` (overwrite input), ``--output PATH``
    (write elsewhere), default (print v2 JSON to stdout via caller).
    """
    input_path = Path(input_path)
    v1 = json.loads(input_path.read_text(encoding="utf-8"))
    v2, report = migrate_v1_to_v2(v1)

    if check:
        if report["already_v2"]:
            return v2, report, 0
        # v1 always needs migration -> check fails (drift)
        return v2, report, 1

    payload = json.dumps(v2, ensure_ascii=False, indent=2) + "\n"
    if in_place:
        input_path.write_text(payload, encoding="utf-8")
    elif output:
        Path(output).write_text(payload, encoding="utf-8")
    return v2, report, 0
