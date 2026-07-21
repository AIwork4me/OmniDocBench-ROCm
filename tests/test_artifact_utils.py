import hashlib
import json
from pathlib import Path

import pytest

from omnidocbench_rocm import artifact_utils as au


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
    from omnidocbench_rocm.schema import validate_artifact
    validate_artifact("run_summary", json.loads(out.read_text()))  # no exception


def test_write_provenance_validates(tmp_path):
    from omnidocbench_rocm.schema import validate_artifact
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


def test_provenance_contains_backend(tmp_path):
    rs = tmp_path / "_run_stats.json"
    rs.write_text(json.dumps({"schema_version": 1, "count": 3, "ok": 3, "fail": 0, "fallback": 0, "limit_pages": None, "engine": "vllm", "stats": []}))
    out = tmp_path / "prov.json"
    au.write_provenance(destination=out, git_commit="c", engine_version="0.3.0",
                        model_id="m", platform="linux-rocm", server_url="",
                        api_model_name="", adapter_command="python a.py",
                        scoring_config_path=tmp_path / "c.yaml",
                        dataset_manifest_path=tmp_path / "m.json",
                        dataset_revision="v1.6", predictions_dir=tmp_path / "preds",
                        metric_result_paths=[tmp_path / "metric.json"],
                        run_summary_paths=[tmp_path / "rs.json"], run_stats_path=rs)
    prov = json.loads(out.read_text())
    assert prov["backend"] == "vllm"


# ── copy_artifact / prediction manifest / dataset identity ────────────────────

def test_copy_artifact_copies_and_creates_parent(tmp_path):
    src = tmp_path / "s.json"; src.write_text("{}")
    dst = tmp_path / "nested" / "deep" / "d.json"
    out = au.copy_artifact(source=src, destination=dst)
    assert out == dst and dst.read_text() == "{}"


def test_copy_artifact_fails_when_source_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        au.copy_artifact(source=tmp_path / "nope", destination=tmp_path / "d.json")


def test_prediction_manifest_hashes_nonempty_and_is_deterministic(tmp_path):
    preds = tmp_path / "preds"; preds.mkdir()
    (preds / "b.md").write_text("hello"); (preds / "a.md").write_text("world")
    (preds / "empty.md").write_text("")  # excluded
    rs = {"count": 3, "ok": 2, "fail": 1, "stats": [
        {"image": "a.png", "status": "ok"},
        {"image": "b.png", "status": "ok"},
        {"image": "empty.png", "status": "failed: empty prediction", "error": "empty prediction"}]}
    dst = tmp_path / "m.json"
    au.write_prediction_manifest(predictions_dir=preds, destination=dst, model_id="m",
                                 platform="linux-rocm", backend="vlm-vllm", run_stats=rs)
    m = json.loads(dst.read_text())
    assert m["prediction_count"] == 2
    assert [f["relative_path"] for f in m["files"]] == ["a.md", "b.md"]  # sorted
    assert m["files"][0]["sha256"] == hashlib.sha256(b"world").hexdigest()
    assert m["hash_algorithm"] == "sha256"
    assert m["failed_pages"][0]["reason"] == "empty prediction"
    # deterministic across runs
    dst2 = tmp_path / "m2.json"
    au.write_prediction_manifest(predictions_dir=preds, destination=dst2, model_id="m",
                                 platform="linux-rocm", backend="vlm-vllm", run_stats=rs)
    assert dst2.read_text() == dst.read_text()


def test_prediction_manifest_run_driven_ignores_stray_files(tmp_path):
    """A dirty preds dir with stragglers not in the run: manifest counts only
    the run's pages (run-driven), so prediction_count == ok."""
    preds = tmp_path / "preds"; preds.mkdir()
    (preds / "a.md").write_text("x"); (preds / "b.md").write_text("y")
    (preds / "stray.md").write_text("not part of the run")  # must be ignored
    rs = {"count": 2, "ok": 2, "fail": 0, "stats": [
        {"image": "a.png", "status": "ok"}, {"image": "b.png", "status": "ok"}]}
    dst = tmp_path / "m.json"
    au.write_prediction_manifest(predictions_dir=preds, destination=dst, model_id="m",
                                 platform="linux-rocm", backend="vlm-vllm", run_stats=rs)
    m = json.loads(dst.read_text())
    assert m["prediction_count"] == 2
    assert {f["relative_path"] for f in m["files"]} == {"a.md", "b.md"}
    assert all(f["relative_path"] != "stray.md" for f in m["files"])


def test_prediction_manifest_counts_match_run_stats(tmp_path):
    preds = tmp_path / "preds"; preds.mkdir()
    for n in ("a.md", "b.md", "c.md"):
        (preds / n).write_text("x")
    rs = {"count": 4, "ok": 3, "fail": 1, "stats": [
        {"image": "a.png", "status": "ok"}, {"image": "b.png", "status": "ok"},
        {"image": "c.png", "status": "ok"},
        {"image": "d.png", "status": "failed: empty prediction", "error": "empty"}]}
    dst = tmp_path / "m.json"
    au.write_prediction_manifest(predictions_dir=preds, destination=dst, model_id="m",
                                 platform="linux-rocm", backend="vlm-vllm", run_stats=rs)
    m = json.loads(dst.read_text())
    assert m["prediction_count"] == rs["ok"] == 3
    assert m["expected_page_count"] == 4 and m["failed_page_count"] == 1


def test_dataset_identity_records_revision_and_gt_sha(tmp_path):
    dst = tmp_path / "ident.json"
    au.write_dataset_identity(destination=dst, dataset="OmniDocBench", version="v1.6",
                              revision="2b161d0", ground_truth_file="OmniDocBench.json",
                              ground_truth_sha256="abc123")
    ident = json.loads(dst.read_text())
    assert ident["revision"] == "2b161d0"
    assert ident["ground_truth_sha256"] == "abc123"
    assert ident["ground_truth_file"] == "OmniDocBench.json"


# ── run_summary / provenance: committed-copy refs + migration fields ─────────

def _rs_metric(tmp_path, engine="vllm"):
    rs = tmp_path / "_run_stats.json"
    rs.write_text(json.dumps({"schema_version": 1, "count": 3, "ok": 3, "fail": 0,
                              "fallback": 0, "limit_pages": None, "engine": engine, "stats": []}))
    metric = tmp_path / "metric.json"
    metric.write_text(json.dumps(_metric()))
    return rs, metric


def test_run_summary_prefers_committed_copy_paths(tmp_path):
    rs, metric = _rs_metric(tmp_path)
    out = tmp_path / "summary.json"
    committed_metric = tmp_path / "bundle" / "m_metric_result.json"
    committed_stats = tmp_path / "bundle" / "m_run_stats.json"
    au.write_run_summary(save_name="m_v16_quick_match", run_stats_path=rs,
                         metric_result_path=metric, destination=out, cdm=False,
                         committed_metric_result_path=committed_metric,
                         committed_run_stats_path=committed_stats)
    summ = json.loads(out.read_text())
    assert summ["metric_result_path"] == str(committed_metric)
    assert summ["run_stats_path"] == str(committed_stats)


def test_run_summary_falls_back_to_runtime_paths(tmp_path):
    """Backward-compat: without committed_* the recorded paths are the runtime sources."""
    rs, metric = _rs_metric(tmp_path)
    out = tmp_path / "summary.json"
    au.write_run_summary(save_name="m_v16_quick_match", run_stats_path=rs,
                         metric_result_path=metric, destination=out, cdm=False)
    summ = json.loads(out.read_text())
    assert summ["metric_result_path"] == str(metric)
    assert summ["run_stats_path"] == str(rs)


def test_provenance_records_migration_and_source_fields(tmp_path):
    from omnidocbench_rocm.schema import validate_artifact
    rs, _ = _rs_metric(tmp_path)
    manifest = tmp_path / "pred_manifest.json"
    ident = tmp_path / "dataset_identity.json"
    out = tmp_path / "prov.json"
    au.write_provenance(destination=out, git_commit="pack1", engine_version="0.3.1",
                        model_id="mineru2.5", platform="linux-rocm", server_url="",
                        api_model_name="mineru-pro", adapter_command="python a.py",
                        scoring_config_path=tmp_path / "c.yaml",
                        dataset_manifest_path=tmp_path / "m.json",
                        dataset_identity_path=ident, dataset_revision="2b161d0",
                        predictions_dir=tmp_path / "preds",
                        prediction_manifest_path=manifest, prediction_manifest_sha256="deadbeef",
                        metric_result_paths=[tmp_path / "metric.json"],
                        run_summary_paths=[tmp_path / "rs.json"], run_stats_path=rs,
                        source_metric_result_path=str(tmp_path / "metric.json"),
                        source_run_stats_path=str(rs), source_prediction_dir=str(tmp_path / "preds"),
                        prediction_source_commit="b75f788",
                        prediction_source_command="mineru-rocm predict vlm-vllm",
                        prediction_source_run_manifest="results/.../run_manifest.json",
                        migration_type="legacy_predictions_to_platform_artifacts")
    prov = json.loads(out.read_text())
    validate_artifact("provenance", prov)
    assert prov["packaging_commit"] == "pack1"
    assert prov["prediction_source_commit"] == "b75f788"
    assert prov["migration_type"] == "legacy_predictions_to_platform_artifacts"
    assert prov["prediction_manifest_sha256"] == "deadbeef"
    assert prov["dataset_identity_path"] == str(ident)
    assert prov["source_prediction_dir"] == str(tmp_path / "preds")


def test_provenance_migration_fields_optional_and_defaulted(tmp_path):
    """Backward-compat: old callers (no migration kwargs) still validate."""
    from omnidocbench_rocm.schema import validate_artifact
    rs, _ = _rs_metric(tmp_path)
    out = tmp_path / "prov.json"
    au.write_provenance(destination=out, git_commit="c", engine_version="0.3.0",
                        model_id="m", platform="linux-rocm", server_url="",
                        api_model_name="", adapter_command="python a.py",
                        scoring_config_path=tmp_path / "c.yaml",
                        dataset_manifest_path=tmp_path / "m.json",
                        dataset_revision="v1.6", predictions_dir=tmp_path / "preds",
                        metric_result_paths=[tmp_path / "metric.json"],
                        run_summary_paths=[tmp_path / "rs.json"], run_stats_path=rs)
    prov = json.loads(out.read_text())
    validate_artifact("provenance", prov)  # no exception
    assert prov["packaging_commit"] == "c"
    assert prov["migration_type"] == ""
