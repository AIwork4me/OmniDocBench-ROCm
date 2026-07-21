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
    summary = stages.stage_infer(
        adapter_path=adapter, img_dir=img_dir, out_dir=out_dir,
        platform="linux-rocm", config={})
    assert summary["count"] == 2 and summary["ok"] == 2
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
