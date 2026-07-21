"""Tests for the cross-artifact bundle validator."""
import json
from pathlib import Path

from omnidocbench_rocm import stages
from omnidocbench_rocm.bundle_validator import validate_bundle, recompute_overall


def _metric():
    # text 0.034, CDM 0.965, TEDS 0.9424 -> ((96.6 + 96.5 + 94.24)/3) = 95.78
    return {
        "text_block": {"page": {"Edit_dist": {"ALL": 0.034}}},
        "reading_order": {"page": {"Edit_dist": {"ALL": 0.129}}},
        "table": {"page": {"TEDS": {"ALL": 0.9424}}},
        "display_formula": {"page": {"CDM": {"ALL": 0.965}},
                            "metric_debug": {"CDM": {"sample_count": 10, "exception_case_count": 0}}},
    }


def _build_bundle(tmp_path, *, cdm=True, model_id="mineru2.5", engine="vlm-vllm"):
    rs = tmp_path / "_run_stats.json"
    rs.write_text(json.dumps({"schema_version": 1, "count": 3, "ok": 3, "fail": 0,
                              "fallback": 0, "limit_pages": None, "engine": engine, "stats": []}))
    metric = tmp_path / "metric.json"
    metric.write_text(json.dumps(_metric()))
    preds = tmp_path / "preds"; preds.mkdir()
    for n in ("a.md", "b.md", "c.md"):
        (preds / n).write_text("# page\n")
    results = tmp_path / "results" / "v16" / "linux-rocm"
    out = stages.stage_publish(model_id=model_id, platform="linux-rocm", version="v16",
        cdm=cdm, run_stats_path=rs, metric_result_path=metric, results_dir=results,
        git_commit="pack123", engine_version="0.3.1",
        adapter_command="python adapter/run_adapter.py --backend vlm-vllm",
        predictions_dir=preds, dataset_revision="2b161d0",
        ground_truth_sha256="abc", prediction_source_commit="pred456",
        migration_type="native-platform-run")
    return results, out


def _model_card(overall=95.78, model_id="mineru2.5"):
    return {"schema_version": 1, "model_id": model_id, "model_version": "x",
            "platforms": ["linux-rocm"], "badge": {"linux-rocm": "community"},
            "eval_date": "2026-07-21", "omnidocbench_version": "v1.6",
            "overall": overall, "submetrics": {}, "hardware": {}, "artifacts": {}}


def test_recompute_overall_matches_formula():
    assert recompute_overall(_metric()) == 95.78


def test_validate_bundle_conformant(tmp_path):
    results, _ = _build_bundle(tmp_path)
    rep = validate_bundle(results)
    assert rep.ok, rep.failures


def test_validate_bundle_backend_engine_mismatch(tmp_path):
    results, out = _build_bundle(tmp_path, engine="vlm-vllm")
    prov_path = Path(out["provenance"])
    prov = json.loads(prov_path.read_text())
    prov["backend"] = "pipeline"  # drift vs run_summary.engine
    prov_path.write_text(json.dumps(prov))
    rep = validate_bundle(results)
    assert not rep.ok
    assert any("backend" in f.lower() and "engine" in f.lower() for f in rep.failures)


def test_validate_bundle_count_arithmetic(tmp_path):
    results, out = _build_bundle(tmp_path)
    summ_path = Path(out["run_summary"])
    summ = json.loads(summ_path.read_text())
    summ["ok_pages"] = 2  # 2 + 0 + 0 != page_count 3
    summ_path.write_text(json.dumps(summ))
    rep = validate_bundle(results)
    assert not rep.ok
    assert any("ok" in f.lower() and "fail" in f.lower() for f in rep.failures)


def test_validate_bundle_manifest_count_mismatch(tmp_path):
    results, out = _build_bundle(tmp_path)
    man_path = Path(out["prediction_manifest"])
    man = json.loads(man_path.read_text())
    man["prediction_count"] = 99
    man_path.write_text(json.dumps(man))
    rep = validate_bundle(results)
    assert not rep.ok
    assert any("manifest" in f.lower() for f in rep.failures)


def test_validate_bundle_overall_recompute_drift(tmp_path):
    results, _ = _build_bundle(tmp_path)
    mc = _model_card(overall=90.0)  # wrong overall vs recomputed 95.78
    rep = validate_bundle(results, model_card=mc)
    assert not rep.ok
    assert any("overall" in f.lower() for f in rep.failures)


def test_validate_bundle_missing_metric(tmp_path):
    results, out = _build_bundle(tmp_path)
    Path(out["metric_result"]).unlink()
    rep = validate_bundle(results)
    assert not rep.ok
    assert any("metric" in f.lower() for f in rep.failures)


def test_validate_bundle_cdm_flag_matches_save_name(tmp_path):
    results, _ = _build_bundle(tmp_path, cdm=True)
    # Tamper run_summary to claim cdm=False while save_name says _cdm
    summ_path = next(results.glob("*_run_summary.json"))
    summ = json.loads(summ_path.read_text())
    summ["cdm"] = False
    summ_path.write_text(json.dumps(summ))
    rep = validate_bundle(results)
    assert not rep.ok
    assert any("cdm" in f.lower() for f in rep.failures)


def test_validate_bundle_registry_model_card_drift(tmp_path):
    import yaml
    results, _ = _build_bundle(tmp_path)
    mc = _model_card(overall=95.78)
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(yaml.safe_dump([{"model_id": "mineru2.5",
        "repo": "AIwork4me/MinerU-ROCm",
        "platforms": {"linux-rocm": {"badge": "community", "overall": 90.0},
                      "windows-hip": {"badge": "community-wanted", "overall": None}}}]))
    rep = validate_bundle(results, model_card=mc, registry=registry_path)
    assert not rep.ok
    assert any("registry" in f.lower() and "overall" in f.lower() for f in rep.failures)
