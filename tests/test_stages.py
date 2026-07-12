import json, subprocess, sys
from pathlib import Path
from omnidocbench_amd import stages


# Fake adapter: defines run_adapter per the canonical contract
# (run_adapter(img_dir, out_dir, *, platform, config) -> RunSummary) AND is
# self-executing as a subprocess, because stage_infer invokes it via
# `subprocess.run([sys.executable, adapter, --img-dir, ...])` and never imports it.
FAKE_ADAPTER = '''
import argparse
from pathlib import Path
from omnidocbench_amd.types import RunSummary, PageStatus
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
