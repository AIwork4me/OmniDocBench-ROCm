"""CPU-only end-to-end smoke for the P0 config + provenance chain.

Drives the REAL CLI (in-process) against a fake adapter that echoes its argv,
writes .md, and writes _run_stats.json(engine=<backend>). Verifies the whole
chain: config forwarded to the adapter, and provenance records the real
prediction_dir / backend / server_url / api_model_name / adapter_command.
No GPU, no network, no OmniDocBench scoring.
"""
import json
import shlex
from pathlib import Path

from omnidocbench_rocm.cli import main

# Fake adapter: accepts the forwarded flags, echoes the FULL invocation
# ([sys.executable] + sys.argv) to _argv.json, writes one .md per image, and
# writes _run_stats.json with engine=<--backend>. Pure stdlib — no engine import.
FAKE_ADAPTER = '''
import argparse, json, sys
from pathlib import Path
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
(out / "_argv.json").write_text(json.dumps([sys.executable] + sys.argv))
imgs = sorted(q for q in Path(a.img_dir).iterdir() if q.suffix.lower() in {".png", ".jpg"})
for i in imgs:
    (out / f"{i.stem}.md").write_text("# " + i.stem + "\\n", encoding="utf-8")
json.dump({"schema_version": 1, "count": len(imgs), "ok": len(imgs), "fail": 0,
           "fallback": 0, "limit_pages": None, "engine": a.backend, "stats": []},
          open(out / "_run_stats.json", "w"))
'''

METRIC = {
    "text_block": {"page": {"Edit_dist": {"ALL": 0.1}}},
    "reading_order": {"page": {"Edit_dist": {"ALL": 0.1}}},
    "table": {"page": {"TEDS": {"ALL": 0.9}}},
    "display_formula": {"page": {"CDM": {"ALL": 0.9}},
                        "metric_debug": {"CDM": {"sample_count": 1, "exception_case_count": 0}}},
}


def test_smoke_infer_then_publish_records_real_config(tmp_path):
    adapter = tmp_path / "fake_adapter.py"; adapter.write_text(FAKE_ADAPTER)
    imgs = tmp_path / "imgs"; imgs.mkdir()
    (imgs / "a.png").write_bytes(b"x")
    preds = tmp_path / "preds"
    metric = tmp_path / "metric.json"; metric.write_text(json.dumps(METRIC))
    results = tmp_path / "results"; results.mkdir()

    rc = main(["infer", "--adapter", str(adapter), "--img-dir", str(imgs),
               "--out-dir", str(preds), "--platform", "linux-rocm",
               "--backend", "vlm-vllm", "--server-url", "http://127.0.0.1:8265/v1",
               "--api-model-name", "mineru-pro", "--skip-existing"])
    assert rc == 0
    argv = json.loads((preds / "_argv.json").read_text())
    assert "vlm-vllm" in argv and "http://127.0.0.1:8265/v1" in argv
    assert "mineru-pro" in argv and "--skip-existing" in argv

    rc = main(["publish", "--model-id", "mineru2.5", "--platform", "linux-rocm",
               "--version", "v16", "--run-stats", str(preds / "_run_stats.json"),
               "--metric-result", str(metric), "--results-dir", str(results),
               "--git-commit", "abc", "--adapter-command", "python fake_adapter.py",
               "--dataset-revision", "2b161d0", "--predictions-dir", str(preds),
               "--server-url", "http://127.0.0.1:8265/v1", "--api-model-name", "mineru-pro"])
    assert rc == 0
    prov = json.loads(next(results.glob("*_provenance.json")).read_text())
    assert prov["prediction_dir"] == str(preds)
    assert prov["backend"] == "vlm-vllm"
    assert prov["vlm_server_url"] == "http://127.0.0.1:8265/v1"
    assert prov["api_model_name"] == "mineru-pro"


def test_smoke_run_all_records_real_adapter_command(tmp_path, monkeypatch):
    adapter = tmp_path / "fake_adapter.py"; adapter.write_text(FAKE_ADAPTER)
    data_root = tmp_path / "data"
    monkeypatch.setenv("OMNIDOCBENCH_ROCM_DATA", str(data_root))
    # dataset_dir(v16)/images must exist for stage_infer's img_dir
    (data_root / "datasets" / "v16" / "images").mkdir(parents=True)
    (data_root / "datasets" / "v16" / "images" / "a.png").write_bytes(b"x")
    results = tmp_path / "results"; results.mkdir()
    metric = tmp_path / "metric.json"; metric.write_text(json.dumps(METRIC))

    # Mock the network/dataset + scoring stages; let infer + publish run for real.
    import omnidocbench_rocm.cli as cli
    monkeypatch.setattr(cli, "stage_download", lambda *a, **k: None)
    monkeypatch.setattr(cli, "stage_score", lambda **k: metric)
    monkeypatch.setattr(cli, "get_backend", lambda *a, **k: None)

    rc = main(["run", "--stage", "all", "--platform", "linux-rocm", "--version", "v16",
               "--revision", "2b161d0", "--adapter", str(adapter), "--model-id", "m",
               "--git-commit", "abc", "--results-dir", str(results), "--backend", "vlm-vllm"])
    assert rc == 0
    preds_dir = data_root / "predictions" / "m" / "linux-rocm"
    argv = json.loads((preds_dir / "_argv.json").read_text())
    prov = json.loads(next(results.glob("*_provenance.json")).read_text())
    assert prov["adapter_command"] == shlex.join(argv)
    assert prov["backend"] == "vlm-vllm"
