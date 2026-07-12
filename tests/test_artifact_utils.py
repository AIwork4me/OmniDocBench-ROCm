import json
from pathlib import Path
from omnidocbench_amd import artifact_utils as au


def _metric(all_cdm_except=False):
    return {
        "text_block": {"page": {"Edit_dist": {"ALL": 0.034}}},
        "reading_order": {"page": {"Edit_dist": {"ALL": 0.129}}},
        "table": {"page": {"TEDS": {"ALL": 0.9424}}},
        "display_formula": {"page": {"CDM": {"ALL": 0.965}},
                            "metric_debug": {"CDM": {"sample_count": 10, "exception_case_count": 10 if all_cdm_except else 0}}},
    }


def test_readme_metrics_extracts_four():
    m = au.extract_readme_metrics(_metric())
    assert m["text_edit_dist"] == 0.034
    assert abs(m["table_teds_percent"] - 94.24) < 0.01
    assert m["formula_cdm_percent"] == 96.5


def test_invalid_cdm_nulled():
    m = au.extract_readme_metrics(_metric(all_cdm_except=True))
    assert m["formula_cdm_percent"] is None
    q = au.analyze_metric_quality(_metric(all_cdm_except=True))
    assert q["formula_cdm"]["valid"] is False


def test_write_run_summary_validates(tmp_path):
    rs_path = tmp_path / "_run_stats.json"
    rs_path.write_text(json.dumps({
        "schema_version": 1, "count": 1651, "ok": 1650, "fail": 1, "fallback": 0,
        "limit_pages": None, "engine": "official", "stats": []}))
    metric_path = tmp_path / "metric.json"
    metric_path.write_text(json.dumps(_metric()))
    out = tmp_path / "run_summary.json"
    au.write_run_summary(save_name="m_v16_quick_match", run_stats_path=rs_path,
                         metric_result_path=metric_path, destination=out, cdm=False)
    from omnidocbench_amd.schema import validate_artifact
    validate_artifact("run_summary", json.loads(out.read_text()))  # no exception


def test_write_provenance_validates(tmp_path):
    from omnidocbench_amd.schema import validate_artifact
    rs = tmp_path / "_run_stats.json"
    rs.write_text(json.dumps({"schema_version": 1, "count": 3, "ok": 3, "fail": 0, "fallback": 0, "limit_pages": None, "engine": "official", "stats": []}))
    out = tmp_path / "provenance.json"
    au.write_provenance(destination=out, git_commit="abc123", engine_version="0.1.0",
                        model_id="m", platform="linux-rocm", server_url="http://x",
                        api_model_name="m.gguf", adapter_command="python a.py",
                        scoring_config_path=tmp_path / "c.yaml",
                        dataset_manifest_path=tmp_path / "OmniDocBench.json",
                        dataset_revision="v1.6", predictions_dir=tmp_path / "preds",
                        metric_result_paths=[tmp_path / "metric.json"],
                        run_summary_paths=[tmp_path / "rs.json"], run_stats_path=rs)
    prov = json.loads(out.read_text())
    validate_artifact("provenance", prov)
    assert prov["platform"] == "linux-rocm" and prov["dataset_revision"] == "v1.6" and prov["engine_version"] == "0.1.0"
