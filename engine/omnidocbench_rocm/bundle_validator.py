"""Cross-artifact consistency validator for published result bundles.

A "bundle" is the set of ``<save_name>_*`` artifacts that :func:`stage_publish`
writes into a ``results/omnidocbench/<version>/<platform>/`` directory. This
validator checks that every artifact in the bundle is internally consistent
(counts, backend, platform, CDM flag, dataset revision) and that referenced
paths resolve. With ``--model-card`` and ``--registry`` it also checks the
Overall recomputes from the committed metric and matches both the model card
and the registry row.

Used by ``omnidocbench-rocm validate-bundle`` (CLI) and by per-model
``scripts/validate_platform_artifacts.py`` wrappers in CI.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .artifact_utils import analyze_metric_quality, load_json
from .conformance import ConformanceReport


def _nested(value: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def _num(metric: dict, *keys: str) -> float | None:
    value = _nested(metric, *keys)
    return value if isinstance(value, (int, float)) else None


def recompute_overall(metric: dict) -> float | None:
    """Recompute the OmniDocBench v1.6 Overall from a raw metric_result dict.

    ``Overall = ((1 - text_EditDist)*100 + formula_CDM*100 + table_TEDS*100) / 3``
    at ``page.ALL``. Returns ``None`` when any input is missing or the CDM is
    flagged invalid (so the formula cannot be applied honestly).
    """
    text = _num(metric, "text_block", "page", "Edit_dist", "ALL")
    teds = _num(metric, "table", "page", "TEDS", "ALL")
    cdm = _num(metric, "display_formula", "page", "CDM", "ALL")
    if text is None or teds is None or cdm is None:
        return None
    quality = analyze_metric_quality(metric)
    if not quality["formula_cdm"]["valid"]:
        return None
    return round(((1 - text) * 100 + cdm * 100 + teds * 100) / 3, 2)


def _resolves(path_str: str, bundle_dir: Path) -> bool:
    """True when a recorded path resolves within reach of the bundle.

    Accepts: empty (optional field), a redacted runtime placeholder (contains
    ``<``), an absolute path that exists, a CWD-relative path that exists, or a
    sibling file present in ``bundle_dir``.
    """
    if not path_str:
        return True
    if "<" in path_str:  # redacted runtime source path (<workspace>/..., <eval-root>/...)
        return True
    p = Path(path_str)
    if p.is_absolute() and p.exists():
        return True
    if p.exists():  # CWD-relative (e.g. run from repo root)
        return True
    if (bundle_dir / p.name).exists():  # committed sibling copy
        return True
    return False


def validate_bundle(results_dir: Path, *, model_card: dict | Path | None = None,
                    registry: dict | Path | None = None) -> ConformanceReport:
    """Validate every ``<save_name>_*`` bundle in ``results_dir``."""
    results_dir = Path(results_dir)
    r = ConformanceReport()
    if not results_dir.is_dir():
        r.add(f"results_dir not found: {results_dir}")
        return r

    model_card_obj = _coerce_dict(model_card)
    registry_obj = _coerce_dict(registry)

    summaries = sorted(results_dir.glob("*_run_summary.json"))
    if not summaries:
        r.add(f"no bundles (*_run_summary.json) found in {results_dir}")

    for summary_path in summaries:
        save_name = summary_path.name[: -len("_run_summary.json")]
        _validate_one(results_dir, save_name, r)

    if model_card_obj:
        _validate_model_card(results_dir, model_card_obj, r)
        if registry_obj:
            _validate_registry(registry_obj, model_card_obj, r)
    return r


def _coerce_dict(value):
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    p = Path(value)
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8")
    if p.suffix == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def _load_optional(results_dir: Path, name: str) -> dict | None:
    p = results_dir / name
    return load_json(p) if p.exists() else None


def _validate_one(results_dir: Path, save_name: str, r: ConformanceReport) -> None:
    ctx = f"bundle {save_name!r}"
    summ = _load_optional(results_dir, f"{save_name}_run_summary.json")
    prov = _load_optional(results_dir, f"{save_name}_provenance.json")
    metric = _load_optional(results_dir, f"{save_name}_metric_result.json")
    stats = _load_optional(results_dir, f"{save_name}_run_stats.json")
    manifest = _load_optional(results_dir, f"{save_name}_prediction_manifest.json")
    identity = (_load_optional(results_dir, f"{save_name}_dataset_identity.json")
                or _load_optional(results_dir, f"{save_name}_dataset_manifest.json"))

    if summ is None:
        r.add(f"{ctx}: missing run_summary"); return
    if prov is None:
        r.add(f"{ctx}: missing provenance")
    if metric is None:
        r.add(f"{ctx}: missing metric_result")
    if stats is None:
        r.add(f"{ctx}: missing run_stats")
    if manifest is None:
        r.add(f"{ctx}: missing prediction_manifest")

    # platform implied by results_dir layout .../<platform>/
    expected_platform = results_dir.name
    if prov and prov.get("platform") != expected_platform:
        r.add(f"{ctx}: provenance.platform {prov.get('platform')!r} != dir platform {expected_platform!r}")

    # save_name starts with the model id
    if prov and not save_name.startswith(prov.get("model_id", "") + "_"):
        r.add(f"{ctx}: save_name does not start with model_id {prov.get('model_id')!r}")

    # backend == engine
    if summ and prov and summ.get("engine") != prov.get("backend"):
        r.add(f"{ctx}: run_summary.engine {summ.get('engine')!r} != provenance.backend {prov.get('backend')!r}")

    # prediction_count == page_count
    if summ and prov and summ.get("prediction_count") != prov.get("page_count"):
        r.add(f"{ctx}: run_summary.prediction_count {summ.get('prediction_count')} != "
              f"provenance.page_count {prov.get('page_count')}")

    # ok + fail + fallback == page_count
    if summ:
        ok, fail, fb = summ.get("ok_pages"), summ.get("failed_pages"), summ.get("fallback_pages")
        if ok is not None and summ.get("prediction_count") is not None and ok + (fail or 0) + (fb or 0) != summ["prediction_count"]:
            r.add(f"{ctx}: ok+fail+fallback ({ok}+{fail}+{fb}) != prediction_count {summ['prediction_count']}")

    # manifest count == ok pages
    if manifest and summ and manifest.get("prediction_count") != summ.get("ok_pages"):
        r.add(f"{ctx}: prediction_manifest count {manifest.get('prediction_count')} != ok_pages {summ.get('ok_pages')}")

    # CDM flag matches save_name suffix
    if summ is not None:
        cdm_expected = save_name.endswith("_cdm")
        if bool(summ.get("cdm")) != cdm_expected:
            r.add(f"{ctx}: run_summary.cdm {summ.get('cdm')} != save_name CDM suffix ({cdm_expected})")

    # dataset revision consistent
    if prov and identity and prov.get("dataset_revision") and identity.get("revision"):
        if prov.get("dataset_revision") != identity.get("revision"):
            r.add(f"{ctx}: provenance.dataset_revision {prov.get('dataset_revision')!r} != "
                  f"identity revision {identity.get('revision')!r}")

    # referenced paths resolve
    if summ:
        for key in ("metric_result_path", "run_stats_path"):
            if not _resolves(str(summ.get(key, "")), results_dir):
                r.add(f"{ctx}: run_summary.{key} does not resolve: {summ.get(key)!r}")
    if prov:
        for key in ("run_stats_path",):
            if not _resolves(str(prov.get(key, "")), results_dir):
                r.add(f"{ctx}: provenance.{key} does not resolve: {prov.get(key)!r}")
        for key in ("metric_result_paths", "run_summary_paths"):
            for pth in prov.get(key, []) or []:
                if not _resolves(str(pth), results_dir):
                    r.add(f"{ctx}: provenance.{key} entry does not resolve: {pth!r}")


def _validate_model_card(results_dir: Path, model_card: dict, r: ConformanceReport) -> None:
    """Overall recomputed from the canonical metric must match the model card."""
    model_id = model_card.get("model_id")
    # Find the CDM metric for this model (canonical), else any metric.
    candidates = sorted(results_dir.glob(f"{model_id}_*_cdm_metric_result.json"))
    if not candidates:
        candidates = sorted(results_dir.glob(f"{model_id}_*_metric_result.json"))
    if not candidates:
        r.add(f"model_card: no metric_result found for model_id {model_id!r} in {results_dir}")
        return
    metric = load_json(candidates[0])
    recomputed = recompute_overall(metric)
    card_overall = model_card.get("overall")
    if recomputed is None:
        r.add("model_card: Overall could not be recomputed (missing submetrics or invalid CDM)")
        return
    if card_overall is None or round(float(card_overall), 2) != recomputed:
        r.add(f"model_card: overall {card_overall} != recomputed {recomputed}")


def _validate_registry(registry: list | dict, model_card: dict, r: ConformanceReport) -> None:
    rows = registry if isinstance(registry, list) else [registry]
    model_id = model_card.get("model_id")
    row = next((x for x in rows if isinstance(x, dict) and x.get("model_id") == model_id), None)
    if row is None:
        r.add(f"registry: model_id {model_id!r} not present")
        return
    plats = row.get("platforms", {}) or {}
    for plat, entry in plats.items():
        if not isinstance(entry, dict):
            continue
        reg_overall = entry.get("overall")
        # Only check platforms the model card actually claims a badge for.
        if plat not in (model_card.get("badge") or {}):
            continue
        if reg_overall is not None and model_card.get("overall") is not None:
            if round(float(reg_overall), 2) != round(float(model_card["overall"]), 2):
                r.add(f"registry: {model_id}/{plat} overall {reg_overall} != model_card overall {model_card['overall']}")
