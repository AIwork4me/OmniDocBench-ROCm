"""Shared dispatch for the fake standard-CLI fixtures.

Each behavior fixture (success/partial/fatal/badjson/backend_mismatch) is a
one-liner that calls ``main("<behavior>")``. The fixtures implement the FULL
standard CLI contract (version/capabilities/doctor/parse --json) so the
behavioral conformance profiles can exercise every command + exit code without a
GPU or a real model. Python puts a script's own directory on ``sys.path[0]``,
so ``from _common import main`` resolves when the fixture is run directly.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path


def _emit(obj: dict) -> int:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    return 0


def _noisy_emit(obj: dict) -> int:
    """badjson behavior: prefix the JSON with log noise so it is NOT pure JSON."""
    sys.stdout.write("[fake-cli] booting...\n")
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    sys.stdout.write("[fake-cli] done.\n")
    return 0


def _list_images(img_dir: str) -> list[str]:
    d = Path(img_dir)
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_file())


def main(behavior: str) -> int:
    argv = sys.argv[1:]
    if not argv:
        print("usage: <cli> {version|capabilities|doctor|parse} ... --json", file=sys.stderr)
        return 2
    cmd = argv[0]
    rest = argv[1:]
    noisy = behavior == "badjson"
    emit = _noisy_emit if noisy else _emit

    if cmd == "version" and "--json" in rest:
        return emit({"name": f"fake-cli-{behavior}", "version": "0.0.1", "schema_version": 1})

    if cmd == "capabilities" and "--json" in rest:
        return emit({"platforms": [{"platform": "linux-rocm", "backend": "onnx-rocm",
                                     "precision": "fp16", "interface": "standard-cli"}],
                     "interfaces": ["standard-cli"]})

    if cmd == "doctor" and "--json" in rest:
        return emit({"status": "ready", "checks": {"offline": True, "weights_present": True}})

    if cmd == "parse":
        # crude arg parse: --img-dir X --out-dir Y --platform P [--backend B]
        def _flag(name):
            if name in rest:
                i = rest.index(name)
                return rest[i + 1] if i + 1 < len(rest) else ""
            return ""
        img_dir = _flag("--img-dir")
        out_dir = _flag("--out-dir")
        platform = _flag("--platform") or "linux-rocm"
        requested_backend = _flag("--backend")
        # doctor/offline under OMNIDOCS_OFFLINE is honored implicitly (no network used)

        if behavior == "fatal":
            sys.stderr.write("fake-cli: simulated fatal crash\n")
            return 5  # FATAL

        images = _list_images(img_dir)
        if not images:
            return emit({"schema_version": 1, "status": "failed", "pages": [],
                         "backend": "onnx-rocm", "error": "no images"})

        if behavior == "backend_mismatch":
            # always reports onnx-rocm; a different requested backend -> exit 3
            if requested_backend and requested_backend != "onnx-rocm":
                emit({"schema_version": 1, "status": "failed",
                      "backend": "onnx-rocm", "pages": [],
                      "error": f"backend mismatch: requested {requested_backend!r}"})
                return 3  # BACKEND_MISMATCH
            pages = [{"image": im, "status": "ok", "seconds": 0.1} for im in images]
            return emit(_result(pages, "onnx-rocm", platform))

        if behavior == "partial":
            pages = []
            failed = 0
            for i, im in enumerate(images):
                if i % 2 == 1:
                    pages.append({"image": im, "status": "failed", "error": "simulated page failure"})
                    failed += 1
                else:
                    pages.append({"image": im, "status": "ok", "seconds": 0.1})
            obj = _result(pages, "onnx-rocm", platform)
            obj["status"] = "partial"
            obj["failed"] = failed
            sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
            return 1  # PARTIAL

        # success (also the path for badjson's parse)
        pages = [{"image": im, "status": "ok", "seconds": 0.1} for im in images]
        return emit(_result(pages, "onnx-rocm", platform))

    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2  # USAGE


def _result(pages: list[dict], backend: str, platform: str) -> dict:
    return {"schema_version": 1, "status": "ok", "backend": backend, "engine": backend,
            "page_count": len(pages), "ok": sum(1 for p in pages if p["status"] == "ok"),
            "failed": sum(1 for p in pages if p["status"] == "failed"), "skipped": 0,
            "output_dir": "", "full_set": True, "pages": pages}
