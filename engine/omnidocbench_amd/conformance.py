"""Per-model repo conformance checker.

Validates that a model repository satisfies the omnidocbench-amd contracts:
required layout, README sections, examples, engine dependency, and a schema-valid
``model_card.json``. Used in CI and before awarding a ``verified`` badge.

Usage (CLI, via the installed engine)::

    omnidocbench-amd conformance <repo-path>
    # exits 0 (CONFORMANT) or 1 (NON-CONFORMANT + failure list)

Library::

    from omnidocbench_amd.conformance import check_repo
    report = check_repo(Path("path/to/model-repo"))
    if report.ok: ...

The legacy ``python scripts/check_conformance.py <repo-path>`` entrypoint still
works via a thin re-export in ``scripts/check_conformance.py``.
"""
from __future__ import annotations
import json, sys
from dataclasses import dataclass, field
from pathlib import Path

from .schema import validate_artifact

REQUIRED_README_SECTIONS = ["Install", "Demo", "Evaluation", "Reproducibility", "Known Gaps"]


@dataclass
class ConformanceReport:
    ok: bool = True
    failures: list[str] = field(default_factory=list)

    def add(self, msg: str):
        self.failures.append(msg); self.ok = False


def check_repo(repo: Path) -> ConformanceReport:
    repo = Path(repo); r = ConformanceReport()
    if not (repo / "adapter" / "run_adapter.py").exists():
        r.add("missing adapter/run_adapter.py")
    if not (repo / "eval" / "configs" / "omnidocbench_v16.yaml").exists():
        r.add("missing eval/configs/omnidocbench_v16.yaml")
    for plat in ("linux-rocm", "windows-hip"):
        d = repo / "results" / "omnidocbench" / "v16" / plat
        if d.exists() and not any(d.iterdir()):
            r.add(f"empty results/omnidocbench/v16/{plat}/ (declared but no artifacts)")
    for readme in ("README.md", "README.zh-CN.md"):
        p = repo / readme
        if not p.exists():
            r.add(f"missing {readme}"); continue
        text = p.read_text(encoding="utf-8")
        for sec in REQUIRED_README_SECTIONS:
            if sec not in text:
                r.add(f"{readme} missing required section: {sec}")
    if not (repo / "examples").is_dir() or not any((repo / "examples").iterdir()):
        r.add("missing examples/ demo")
    pp = repo / "pyproject.toml"
    if not pp.exists() or "omnidocbench-amd" not in pp.read_text():
        r.add("pyproject.toml does not depend on omnidocbench-amd")
    mc = repo / "model_card.json"
    if mc.exists():
        try:
            validate_artifact("model_card", json.loads(mc.read_text()))
        except Exception as e:
            r.add(f"model_card.json invalid: {e}")
    return r


def main(argv: list[str]) -> int:
    report = check_repo(Path(argv[0]))
    if report.ok:
        print("CONFORMANT"); return 0
    print("NON-CONFORMANT:"); [print(" -", f) for f in report.failures]; return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
