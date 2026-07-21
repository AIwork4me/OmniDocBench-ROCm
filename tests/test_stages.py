import json, subprocess, sys
from pathlib import Path
from omnidocbench_rocm import stages
from omnidocbench_rocm.stages import _build_adapter_command


# Fake adapter: defines run_adapter per the canonical contract
# (run_adapter(img_dir, out_dir, *, platform, config) -> RunSummary) AND is
# self-executing as a subprocess, because stage_infer invokes it via
# `subprocess.run([sys.executable, adapter, --img-dir, ...])` and never imports it.
FAKE_ADAPTER = '''
import argparse
from pathlib import Path
from omnidocbench_rocm.types import RunSummary, PageStatus
IMG_EXT = {".png", ".jpg"}
def run_adapter(img_dir, out_dir, *, platform, config):
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    imgs = sorted(p for p in Path(img_dir).iterdir() if p.suffix.lower() in IMG_EXT)
    stats = []
    for i in imgs:
        (out_dir / f"{i.stem}.md").write_text(f"# {i.stem}\\n", encoding="utf-8")
        stats.append(PageStatus(i.name, "ok"))
    rs = RunSummary(len(imgs), len(imgs), 0, 0, None, stats, engine="smoke")
    rs.write(out_dir / "_run_stats.json")
    return rs.to_run_stats()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--img-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--platform", required=True)
    a = ap.parse_args()
    run_adapter(a.img_dir, a.out_dir, platform=a.platform, config={})
'''


def test_stage_infer_runs_adapter_subprocess(tmp_path, monkeypatch):
    img_dir = tmp_path / "imgs"; img_dir.mkdir()
    (img_dir / "a.png").write_bytes(b"x"); (img_dir / "b.png").write_bytes(b"x")
    adapter = tmp_path / "fake_adapter.py"; adapter.write_text(FAKE_ADAPTER)
    out_dir = tmp_path / "preds"
    result = stages.stage_infer(
        adapter_path=adapter, img_dir=img_dir, out_dir=out_dir,
        platform="linux-rocm", config={})
    assert result.run_stats["count"] == 2 and result.run_stats["ok"] == 2
    assert (out_dir / "a.md").exists() and (out_dir / "_run_stats.json").exists()


def test_stage_publish_refuses_limited_subset(tmp_path):
    rs = tmp_path / "_run_stats.json"
    rs.write_text(json.dumps({"schema_version": 1, "count": 10, "ok": 10, "fail": 0,
                              "fallback": 0, "limit_pages": 10, "engine": "smoke", "stats": []}))
    try:
        stages._assert_full_set(rs)  # private helper used by publish
        assert False, "should refuse limited subset"
    except SystemExit:
        pass


def test_build_adapter_command_minimal():
    cmd = _build_adapter_command(adapter_path=Path("/a/run_adapter.py"),
                                 img_dir=Path("/imgs"), out_dir=Path("/out"),
                                 platform="linux-rocm", config={})
    assert cmd == [sys.executable, "/a/run_adapter.py", "--img-dir", "/imgs",
                   "--out-dir", "/out", "--platform", "linux-rocm"]


def test_build_adapter_command_forwards_backend():
    cmd = _build_adapter_command(adapter_path=Path("/a.py"), img_dir=Path("/i"),
                                 out_dir=Path("/o"), platform="linux-rocm",
                                 config={"backend": "vlm-vllm"})
    assert "--backend" in cmd
    assert cmd[cmd.index("--backend") + 1] == "vlm-vllm"


def test_build_adapter_command_forwards_server_url():
    cmd = _build_adapter_command(adapter_path=Path("/a.py"), img_dir=Path("/i"),
                                 out_dir=Path("/o"), platform="linux-rocm",
                                 config={"server_url": "http://127.0.0.1:8265/v1"})
    assert "--server-url" in cmd
    assert cmd[cmd.index("--server-url") + 1] == "http://127.0.0.1:8265/v1"


def test_build_adapter_command_forwards_api_model_name():
    cmd = _build_adapter_command(adapter_path=Path("/a.py"), img_dir=Path("/i"),
                                 out_dir=Path("/o"), platform="linux-rocm",
                                 config={"api_model_name": "mineru-pro"})
    assert "--api-model-name" in cmd
    assert cmd[cmd.index("--api-model-name") + 1] == "mineru-pro"


def test_build_adapter_command_forwards_skip_existing():
    cmd = _build_adapter_command(adapter_path=Path("/a.py"), img_dir=Path("/i"),
                                 out_dir=Path("/o"), platform="linux-rocm",
                                 config={"skip_existing": True})
    assert "--skip-existing" in cmd


def test_build_adapter_command_omits_empty_values():
    cmd = _build_adapter_command(adapter_path=Path("/a.py"), img_dir=Path("/i"),
                                 out_dir=Path("/o"), platform="linux-rocm",
                                 config={"backend": "", "server_url": None,
                                         "api_model_name": "", "skip_existing": False})
    assert "--backend" not in cmd
    assert "--server-url" not in cmd
    assert "--api-model-name" not in cmd
    assert "--skip-existing" not in cmd


def test_build_adapter_command_handles_paths_with_spaces():
    cmd = _build_adapter_command(adapter_path=Path("/my adapter/run_adapter.py"),
                                 img_dir=Path("/img dir"), out_dir=Path("/out dir"),
                                 platform="linux-rocm",
                                 config={"backend": "v",
                                         "server_url": "http://a b/v1",
                                         "api_model_name": "model name"})
    # spaces stay inside one argv token (no shell splitting/quoting)
    assert "/my adapter/run_adapter.py" in cmd
    assert "/img dir" in cmd
    assert "/out dir" in cmd
    assert "http://a b/v1" in cmd
    assert "model name" in cmd
    assert cmd.count("/my adapter/run_adapter.py") == 1


from omnidocbench_rocm.types import InferResult

# Fake adapter that accepts the forwarded config flags, echoes its argv to
# _argv.json, writes one .md per image, and writes _run_stats.json with
# engine=<--backend>. Used by the stage_infer config-forwarding tests.
FAKE_ADAPTER_CFG = '''
import argparse, json, sys
from pathlib import Path
from omnidocbench_rocm.types import RunSummary, PageStatus
p = argparse.ArgumentParser()
p.add_argument("--img-dir", required=True)
p.add_argument("--out-dir", required=True)
p.add_argument("--platform", required=True)
p.add_argument("--backend", default="smoke")
p.add_argument("--server-url", default="")
p.add_argument("--api-model-name", default="")
p.add_argument("--skip-existing", action="store_true")
a = p.parse_args()
out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
(out / "_argv.json").write_text(json.dumps(sys.argv[1:]))
imgs = sorted(q for q in Path(a.img_dir).iterdir() if q.suffix.lower() in {".png", ".jpg"})
for i in imgs:
    (out / f"{i.stem}.md").write_text("# " + i.stem + "\\n", encoding="utf-8")
rs = RunSummary(len(imgs), len(imgs), 0, 0, None,
                [PageStatus(i.name, "ok") for i in imgs], engine=a.backend)
rs.write(out / "_run_stats.json")
'''

# Fake adapter that exits non-zero with a stderr line.
FAKE_ADAPTER_FAIL = '''
import sys
sys.stderr.write("boom: model exploded\\n")
sys.exit(3)
'''


def test_stage_infer_invokes_adapter_with_config(tmp_path):
    img_dir = tmp_path / "imgs"; img_dir.mkdir()
    (img_dir / "a.png").write_bytes(b"x")
    adapter = tmp_path / "cfg_adapter.py"; adapter.write_text(FAKE_ADAPTER_CFG)
    out_dir = tmp_path / "preds"
    stages.stage_infer(adapter_path=adapter, img_dir=img_dir, out_dir=out_dir,
                       platform="linux-rocm",
                       config={"backend": "vlm-vllm", "server_url": "http://x/v1",
                               "api_model_name": "m", "skip_existing": True})
    argv = json.loads((out_dir / "_argv.json").read_text())
    assert "--backend" in argv and "vlm-vllm" in argv
    assert "--server-url" in argv and "http://x/v1" in argv
    assert "--api-model-name" in argv and "m" in argv
    assert "--skip-existing" in argv


def test_stage_infer_reads_run_stats(tmp_path):
    img_dir = tmp_path / "imgs"; img_dir.mkdir()
    (img_dir / "a.png").write_bytes(b"x")
    adapter = tmp_path / "cfg_adapter.py"; adapter.write_text(FAKE_ADAPTER_CFG)
    out_dir = tmp_path / "preds"
    result = stages.stage_infer(adapter_path=adapter, img_dir=img_dir, out_dir=out_dir,
                                platform="linux-rocm", config={"backend": "vlm-vllm"})
    assert isinstance(result, InferResult)
    assert result.run_stats["count"] == 1
    assert result.run_stats["engine"] == "vlm-vllm"
    assert result.adapter_argv[0] == sys.executable
    assert "--backend" in result.adapter_argv


def test_stage_infer_reports_adapter_stderr_on_failure(tmp_path):
    img_dir = tmp_path / "imgs"; img_dir.mkdir()
    (img_dir / "a.png").write_bytes(b"x")
    adapter = tmp_path / "fail_adapter.py"; adapter.write_text(FAKE_ADAPTER_FAIL)
    out_dir = tmp_path / "preds"
    try:
        stages.stage_infer(adapter_path=adapter, img_dir=img_dir, out_dir=out_dir,
                           platform="linux-rocm", config={})
        assert False, "should have raised SystemExit"
    except SystemExit as e:
        assert "boom: model exploded" in str(e)
        assert "3" in str(e)


def _publish_inputs(tmp_path, engine="vllm"):
    rs = tmp_path / "_run_stats.json"
    rs.write_text(json.dumps({"schema_version": 1, "count": 3, "ok": 3, "fail": 0,
                              "fallback": 0, "limit_pages": None, "engine": engine,
                              "stats": []}))
    metric = tmp_path / "metric.json"
    metric.write_text(json.dumps({
        "text_block": {"page": {"Edit_dist": {"ALL": 0.1}}},
        "reading_order": {"page": {"Edit_dist": {"ALL": 0.1}}},
        "table": {"page": {"TEDS": {"ALL": 0.9}}},
        "display_formula": {"page": {"CDM": {"ALL": 0.9}},
                            "metric_debug": {"CDM": {"sample_count": 1, "exception_case_count": 0}}},
    }))
    results = tmp_path / "results"; results.mkdir()
    return rs, metric, results


def test_publish_records_real_predictions_dir(tmp_path):
    rs, metric, results = _publish_inputs(tmp_path)
    real_preds = tmp_path / "the_real_predictions"; real_preds.mkdir()
    out = stages.stage_publish(model_id="m", platform="linux-rocm", version="v16",
                               cdm=False, run_stats_path=rs, metric_result_path=metric,
                               results_dir=results, git_commit="c", engine_version="0.3.0",
                               adapter_command="python a.py", predictions_dir=real_preds,
                               dataset_revision="v1.6")
    prov = json.loads(Path(out["provenance"]).read_text())
    assert prov["prediction_dir"] == str(real_preds)


def test_publish_does_not_use_results_dir_parent_as_prediction_dir(tmp_path):
    rs, metric, results = _publish_inputs(tmp_path)
    real_preds = tmp_path / "the_real_predictions"; real_preds.mkdir()
    out = stages.stage_publish(model_id="m", platform="linux-rocm", version="v16",
                               cdm=False, run_stats_path=rs, metric_result_path=metric,
                               results_dir=results, git_commit="c", engine_version="0.3.0",
                               adapter_command="python a.py", predictions_dir=real_preds,
                               dataset_revision="v1.6")
    prov = json.loads(Path(out["provenance"]).read_text())
    assert prov["prediction_dir"] != str(results.parent)
    assert prov["prediction_dir"] == str(real_preds)


def test_assert_full_set_returns_run_stats(tmp_path):
    rs = tmp_path / "_run_stats.json"
    rs.write_text(json.dumps({"schema_version": 1, "count": 3, "ok": 3, "fail": 0,
                              "fallback": 0, "limit_pages": None, "engine": "x", "stats": []}))
    loaded = stages._assert_full_set(rs)
    assert loaded["engine"] == "x"


def test_publish_uses_adapter_reported_backend(tmp_path):
    rs, metric, results = _publish_inputs(tmp_path, engine="pipeline")
    preds = tmp_path / "preds"; preds.mkdir()
    out = stages.stage_publish(model_id="m", platform="linux-rocm", version="v16",
                               cdm=False, run_stats_path=rs, metric_result_path=metric,
                               results_dir=results, git_commit="c", engine_version="0.3.0",
                               adapter_command="python a.py", predictions_dir=preds,
                               requested_backend="", dataset_revision="v1.6")
    prov = json.loads(Path(out["provenance"]).read_text())
    assert prov["backend"] == "pipeline"


def test_publish_rejects_requested_backend_mismatch(tmp_path):
    rs, metric, results = _publish_inputs(tmp_path, engine="pipeline")
    preds = tmp_path / "preds"; preds.mkdir()
    try:
        stages.stage_publish(model_id="m", platform="linux-rocm", version="v16",
                             cdm=False, run_stats_path=rs, metric_result_path=metric,
                             results_dir=results, git_commit="c", engine_version="0.3.0",
                             adapter_command="python a.py", predictions_dir=preds,
                             requested_backend="vlm-vllm", dataset_revision="v1.6")
        assert False, "should refuse mismatched backend"
    except SystemExit as e:
        msg = str(e)
        assert "vlm-vllm" in msg and "pipeline" in msg
        assert "Refusing to publish" in msg


def test_publish_allows_empty_requested_backend(tmp_path):
    rs, metric, results = _publish_inputs(tmp_path, engine="smoke")
    preds = tmp_path / "preds"; preds.mkdir()
    out = stages.stage_publish(model_id="m", platform="linux-rocm", version="v16",
                               cdm=False, run_stats_path=rs, metric_result_path=metric,
                               results_dir=results, git_commit="c", engine_version="0.3.0",
                               adapter_command="python a.py", predictions_dir=preds,
                               requested_backend="", dataset_revision="v1.6")
    prov = json.loads(Path(out["provenance"]).read_text())
    assert prov["backend"] == "smoke"   # recorded, no gate when nothing requested
