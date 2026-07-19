"""A real conformant adapter used by the contract integration test.

Implements the canonical contract::

    run_adapter(img_dir, out_dir, *, platform, config) -> dict

and is self-executing as a subprocess (``--backend smoke``), because
:func:`omnidocbench_rocm.stages.stage_infer` invokes it via
``subprocess.run([sys.executable, adapter, --img-dir, ...])`` and never
imports it. The ``__main__`` block writes ``out_dir/<stem>.md`` per image and
the ``_run_stats.json`` the engine consumes.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from omnidocbench_rocm.types import RunSummary, PageStatus

IMG_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def run_adapter(img_dir: Path, out_dir: Path, *, platform: str, config: dict) -> dict:
    """Smoke backend: emit one ``.md`` per image, all ``ok``, no failures."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    imgs = sorted(p for p in Path(img_dir).iterdir() if p.suffix.lower() in IMG_EXT)
    stats: list[PageStatus] = []
    for img in imgs:
        (out_dir / f"{img.stem}.md").write_text(f"# {img.stem}\n\n(smoke output)\n", encoding="utf-8")
        stats.append(PageStatus(img.name, "ok", seconds=0.01, attempts=1))
    rs = RunSummary(count=len(imgs), ok=len(imgs), fail=0, fallback=0,
                    limit_pages=None, stats=stats, engine="smoke")
    rs.write(out_dir / "_run_stats.json")
    return rs.to_run_stats()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--img-dir", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--platform", required=True)
    p.add_argument("--backend", default="smoke")
    a = p.parse_args()
    run_adapter(Path(a.img_dir), Path(a.out_dir), platform=a.platform, config={})
