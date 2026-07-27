"""CLI -> adapter bridge (ADR-0011, §10 adapter-contract preservation).

Wraps a legacy ``run_adapter.py`` (the adapter-SCRIPT interface from
contracts/adapter.md) so it also speaks the STANDARD CLI contract
(version/capabilities/doctor/parse --json). This lets a per-model repo expose
the new contract without rewriting its adapter, while preserving every iron rule:

  * R1 — the engine never imports the adapter's model runtime. ``parse`` shells
    out to ``run_adapter.py`` as a subprocess and consumes only ``_run_stats.json``
    + the ``.md`` outputs. ``capabilities`` is read from the static ``rocmdoc.yaml``
    (or, best-effort, an isolated subprocess that imports ``adapter_config``).
  * R2 — per-page failure -> recorded, run continues; the bridge maps a non-zero
    fail count to ``status: partial`` + exit 1, never a crash.
  * R3 — one ``<stem>.md`` per page stays the adapter's job; the bridge only
    summarizes it.
  * Backend honesty — the result's ``backend`` is the adapter-reported
    ``_run_stats.json['engine']``; a mismatch with ``--backend`` exits 3.

Invoked as a module so model repos can ship a thin ``cli`` entrypoint pointing
here, or directly::

    python -m omnidocbench_rocm.cli_bridge parse --adapter adapter/run_adapter.py \\
        --img-dir imgs --out-dir out --platform linux-rocm --json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import cli_contract as cc
from . import __version__ as _ENGINE_VERSION

_JSON_ARGS = ("--json",)


def _emit(obj: dict, exit_code: int = cc.EXIT_OK) -> int:
    """Print exactly one JSON document to stdout (pure JSON — exit 4 if not)."""
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    sys.stdout.flush()
    return exit_code


def _capabilities_from_manifest(repo: Path) -> dict | None:
    """Read declared capabilities from rocmdoc.yaml (static, isolation-safe)."""
    mf_path = repo / "rocmdoc.yaml"
    if not mf_path.exists():
        return None
    try:
        import yaml
        mf = yaml.safe_load(mf_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    plats = []
    for impl in mf.get("implementations") or []:
        if impl.get("status", "supported") in ("supported", "experimental"):
            plats.append({
                "platform": impl.get("platform"),
                "backend": impl.get("backend", ""),
                "precision": impl.get("precision", ""),
                "interface": impl.get("interface", "adapter-script"),
            })
    return {"platforms": plats, "interfaces": mf.get("interfaces", [])}


def _capabilities_from_adapter_config(repo: Path) -> dict | None:
    """Best-effort: spawn an ISOLATED subprocess that imports adapter_config.

    Runs in a child interpreter so any model dependency pulled by
    ``adapter_config`` never leaks into the engine process. Returns None if the
    import fails for any reason (the contract degrades to 'declare via manifest').
    """
    adapter_dir = repo / "adapter"
    if not (adapter_dir / "adapter_config.py").exists():
        return None
    probe = (
        "import json,sys\n"
        "try:\n"
        "  import adapter_config as a\n"
        "  d=a.as_dict() if hasattr(a,'as_dict') else {}\n"
        "  print(json.dumps({'backend': d.get('backend',''), 'platforms':"
        " [{'platform':'linux-rocm','backend':d.get('backend','')}]}))\n"
        "except Exception as e:\n"
        "  print(json.dumps({'error': str(e)})); sys.exit(0)\n"
    )
    try:
        proc = subprocess.run([sys.executable, "-c", probe], capture_output=True,
                              text=True, cwd=str(adapter_dir), timeout=20)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    try:
        obj = json.loads(proc.stdout.strip())
    except Exception:
        return None
    if obj.get("error"):
        return None
    return {"platforms": obj.get("platforms", []), "interfaces": ["adapter-script"]}


def _cmd_version(args) -> int:
    return _emit({"name": "omnidocbench-rocm-cli-bridge", "version": _ENGINE_VERSION,
                  "engine_version": _ENGINE_VERSION, "schema_version": 1})


def _cmd_capabilities(args) -> int:
    repo = Path(args.repo) if getattr(args, "repo", None) else Path.cwd()
    obj = _capabilities_from_manifest(repo) or _capabilities_from_adapter_config(repo)
    if obj is None:
        obj = {"platforms": [], "interfaces": [], "warning":
               "no rocmdoc.yaml and no importable adapter_config — declare capabilities via manifest"}
    return _emit(obj)


def _cmd_doctor(args) -> int:
    repo = Path(args.repo) if getattr(args, "repo", None) else Path.cwd()
    adapter = repo / "adapter" / "run_adapter.py"
    status = "ready" if adapter.exists() else "not-ready"
    checks = {
        "run_adapter_present": adapter.exists(),
        "rocmdoc_yaml_present": (repo / "rocmdoc.yaml").exists(),
        "model_card_present": (repo / "model_card.json").exists(),
        "offline": True,
    }
    return _emit({"status": status, "checks": checks})


def _cmd_parse(args) -> int:
    adapter = Path(args.adapter)
    if not adapter.exists():
        return _emit({"schema_version": 1, "status": "failed", "pages": [],
                      "error": f"adapter not found: {adapter}"}, cc.EXIT_USAGE)
    img_dir = Path(args.img_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(adapter), "--img-dir", str(img_dir),
           "--out-dir", str(out_dir), "--platform", args.platform]
    if args.backend:
        cmd += ["--backend", args.backend]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout)
    except subprocess.TimeoutExpired:
        return _emit({"schema_version": 1, "status": "failed", "pages": [],
                      "error": "adapter timed out"}, cc.EXIT_FATAL)
    except Exception as e:
        return _emit({"schema_version": 1, "status": "failed", "pages": [],
                      "error": f"bridge error: {e}"}, cc.EXIT_FATAL)
    if proc.returncode != 0:
        # adapter crashed (R2 violation) — surface as fatal, do not fake success
        return _emit({"schema_version": 1, "status": "failed", "pages": [],
                      "error": f"adapter exit {proc.returncode}: {proc.stderr.strip()[:300]}"},
                     cc.EXIT_FATAL)
    stats_path = out_dir / "_run_stats.json"
    if not stats_path.exists():
        return _emit({"schema_version": 1, "status": "failed", "pages": [],
                      "error": "adapter produced no _run_stats.json"}, cc.EXIT_CONTRACT)
    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    count = int(stats.get("count", 0))
    ok = int(stats.get("ok", 0))
    fail = int(stats.get("fail", 0))
    fallback = int(stats.get("fallback", 0))
    engine = stats.get("engine", "") or ""
    requested = args.backend or ""
    pages = []
    for s in stats.get("stats", []):
        st = s.get("status", "")
        mapped = "ok" if st == "ok" else ("failed" if st.startswith("failed") else "skipped")
        pages.append({"image": s.get("image", ""), "status": mapped,
                      "error": s.get("error", ""), "seconds": s.get("seconds", 0.0)})
    # backend mismatch gate (exit 3) — never silently record the wrong backend
    if requested and engine and requested != engine:
        return _emit({"schema_version": 1, "status": "failed", "pages": pages,
                      "backend": engine, "error": cc.check_backend_match(
                          {"backend": engine}, requested) or "backend mismatch"},
                     cc.EXIT_BACKEND_MISMATCH)
    if count == 0:
        status, exit_code = "failed", cc.EXIT_FATAL
    elif fail > 0 or fallback > 0:
        status, exit_code = "partial", cc.EXIT_PARTIAL
    else:
        status, exit_code = "ok", cc.EXIT_OK
    return _emit({
        "schema_version": 1, "status": status, "backend": engine, "engine": engine,
        "page_count": count, "ok": ok, "failed": fail, "skipped": fallback,
        "output_dir": str(out_dir), "full_set": stats.get("limit_pages") in (None, 0),
        "pages": pages,
    }, exit_code)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="omnidocbench-rocm-cli-bridge",
                                description="Standard-CLI bridge over a legacy run_adapter.py.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("version").add_argument(*_JSON_ARGS, dest="json", action="store_true")

    cap = sub.add_parser("capabilities")
    cap.add_argument(*_JSON_ARGS, dest="json", action="store_true")
    cap.add_argument("--repo", default="")

    doc = sub.add_parser("doctor")
    doc.add_argument(*_JSON_ARGS, dest="json", action="store_true")
    doc.add_argument("--repo", default="")

    par = sub.add_parser("parse")
    par.add_argument("--adapter", required=True)
    par.add_argument("--img-dir", required=True)
    par.add_argument("--out-dir", required=True)
    par.add_argument("--platform", required=True)
    par.add_argument("--backend", default="")
    par.add_argument("--benchmark", default="omnidocbench-v16")
    par.add_argument(*_JSON_ARGS, dest="json", action="store_true")
    par.add_argument("--timeout", type=int, default=3600)

    a = p.parse_args(argv)
    if a.cmd == "version":
        return _cmd_version(a)
    if a.cmd == "capabilities":
        return _cmd_capabilities(a)
    if a.cmd == "doctor":
        return _cmd_doctor(a)
    if a.cmd == "parse":
        return _cmd_parse(a)
    return cc.EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
