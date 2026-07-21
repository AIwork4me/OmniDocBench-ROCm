#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate _run_stats.json from existing predictions for platform scoring.

Usage:
    python scripts/generate_run_stats.py \
      --gt-json OmniDocBench.json \
      --predictions-dir <preds-dir> \
      --engine vlm-vllm \
      --out <preds-dir>/_run_stats.json
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path


def generate_stats(gt_json: Path, pred_dir: Path, engine: str) -> dict:
    with open(gt_json, encoding="utf-8") as f:
        gt = json.load(f)

    gt_stems = set()
    for entry in gt:
        ip = entry.get("page_info", {}).get("image_path", "")
        if ip:
            gt_stems.add(Path(ip).stem)

    stats = []
    ok = fail = 0
    for stem in sorted(gt_stems):
        md = pred_dir / f"{stem}.md"
        if md.exists():
            try:
                content = md.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                stats.append({"image": f"{stem}.png", "status": "failed: unreadable file",
                              "error": "unreadable", "seconds": 0.0, "attempts": 0})
                fail += 1
                continue
            if not content.strip():
                stats.append({"image": f"{stem}.png", "status": "failed: empty prediction",
                              "error": "empty prediction", "seconds": 0.0, "attempts": 0})
                fail += 1
            else:
                stats.append({"image": f"{stem}.png", "status": "ok",
                              "seconds": 0.0, "attempts": 0})
                ok += 1
        else:
            stats.append({"image": f"{stem}.png", "status": "failed: missing prediction",
                          "error": "prediction not found", "seconds": 0.0, "attempts": 0})
            fail += 1

    count = len(gt_stems)
    assert ok + fail == count, f"ok={ok} fail={fail} != count={count}"
    assert len(stats) == count

    return {
        "schema_version": 1,
        "count": count,
        "ok": ok,
        "fail": fail,
        "fallback": 0,
        "limit_pages": None,
        "engine": engine,
        "stats": stats,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Generate _run_stats.json from predictions")
    p.add_argument("--gt-json", required=True, help="OmniDocBench.json ground truth")
    p.add_argument("--predictions-dir", required=True, help="Directory of .md prediction files")
    p.add_argument("--engine", required=True, help="Backend name (e.g. vlm-vllm, pipeline)")
    p.add_argument("--out", required=True, help="Output path for _run_stats.json")
    args = p.parse_args(argv)

    rs = generate_stats(Path(args.gt_json), Path(args.predictions_dir), args.engine)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated: count={rs['count']} ok={rs['ok']} fail={rs['fail']} engine={rs['engine']} -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
