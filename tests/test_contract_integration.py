"""End-to-end contract integration test (fake adapter -> engine -> artifacts).

Exercises the REAL :func:`stage_infer` (subprocess) + REAL :func:`stage_publish`
(no mocks) against a conformant fake adapter. Validates the whole CPU slice
(Tasks 2-7): a fake adapter runs through ``stage_infer`` (subprocess) ->
``stage_publish`` (assembles artifacts), then the produced ``run_summary.json``
+ ``provenance.json`` are validated against the schema. If this test passes,
the engine integrates correctly.
"""
import json
from pathlib import Path

from omnidocbench_rocm import stages
from omnidocbench_rocm.schema import validate_artifact

FIXTURE_ADAPTER = Path(__file__).parent / "fixtures" / "fake_adapter.py"


def test_fake_adapter_infer_then_publish(tmp_path):
    # 3 images -> stage_infer (REAL subprocess)
    imgs = tmp_path / "imgs"
    imgs.mkdir()
    for name in ("a.png", "b.png", "c.png"):
        (imgs / name).write_bytes(b"x")
    preds = tmp_path / "preds"
    summary = stages.stage_infer(adapter_path=FIXTURE_ADAPTER, img_dir=imgs,
                                 out_dir=preds, platform="linux-rocm", config={})
    assert summary["ok"] == 3
    assert summary["limit_pages"] is None

    # fake a metric_result so publish can assemble readme_metrics
    run_stats = preds / "_run_stats.json"
    metric = tmp_path / "metric.json"
    metric.write_text(json.dumps({
        "text_block": {"page": {"Edit_dist": {"ALL": 0.05}}},
        "reading_order": {"page": {"Edit_dist": {"ALL": 0.13}}},
        "table": {"page": {"TEDS": {"ALL": 0.93}}},
        "display_formula": {
            "page": {"CDM": {"ALL": 0.95}},
            "metric_debug": {"CDM": {"sample_count": 5, "exception_case_count": 0}},
        },
    }))

    # stage_publish (REAL) -> assemble + validate run_summary + provenance
    results = tmp_path / "results"
    results.mkdir()
    out = stages.stage_publish(
        model_id="fake-model", platform="linux-rocm", version="v16", cdm=False,
        run_stats_path=run_stats, metric_result_path=metric, results_dir=results,
        git_commit="abc123", engine_version="0.1.0",
        adapter_command="python fake_adapter.py", dataset_revision="v1.6",
    )

    summary_obj = json.loads(Path(out["run_summary"]).read_text(encoding="utf-8"))
    validate_artifact("run_summary", summary_obj)
    assert summary_obj["readme_metrics"]["text_edit_dist"] == 0.05
    assert summary_obj["readme_metrics"]["reading_order_edit_dist"] == 0.13
    assert summary_obj["readme_metrics"]["table_teds_percent"] == 93.0
    assert summary_obj["readme_metrics"]["formula_cdm_percent"] == 95.0

    prov_obj = json.loads(Path(out["provenance"]).read_text(encoding="utf-8"))
    validate_artifact("provenance", prov_obj)
    assert prov_obj["platform"] == "linux-rocm"
    assert prov_obj["dataset_revision"] == "v1.6"
