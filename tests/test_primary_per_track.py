"""Registry check primary-per-track semantics (ADR-0016): multiple valid results
per (model, platform) are allowed when exactly one is `primary` (multi-backend);
ambiguity is flagged only when no primary is designated."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from omnidocbench_rocm.registry import check, generate, BEGIN_MARKER, END_MARKER


def _write(tmp_path, canonical_rows, reg_overall):
    (tmp_path / "canonical.json").write_text(json.dumps({"schema_version": 2, "results": canonical_rows}))
    (tmp_path / "registry.yaml").write_text(
        f"- model_id: m\n  name: M\n  repo: o/m\n  license: Apache-2.0\n"
        f"  platforms:\n    linux-rocm:\n      badge: community\n      overall: {reg_overall}\n",
        encoding="utf-8")
    (tmp_path / "README.md").write_text(f"# R\n\n{BEGIN_MARKER}\n{END_MARKER}\n", encoding="utf-8")


def _row(rid, overall, primary=False):
    return {"result_id": rid, "model_id": "m", "platform": "linux-rocm",
            "backend": "vllm", "precision": "fp16",
            "benchmark": {"name": "OmniDocBench", "version": "v1.6"},
            "overall": overall, "assurance": "submitted", "status": "valid",
            **({"primary": True} if primary else {})}


def test_multi_valid_with_one_primary_is_ok(tmp_path):
    rows = [_row("m-a", 93.0, primary=True), _row("m-b", 91.0)]  # 2 valid, 1 primary
    _write(tmp_path, rows, 93.0)
    generate(tmp_path / "registry.yaml", tmp_path / "canonical.json", tmp_path / "README.md", write=True)
    ok, problems = check(tmp_path / "registry.yaml", tmp_path / "canonical.json", tmp_path / "README.md")
    assert ok, problems  # multi-backend allowed; primary (93.0) mirrors registry


def test_multi_valid_with_no_primary_is_ambiguous(tmp_path):
    rows = [_row("m-a", 93.0), _row("m-b", 91.0)]  # 2 valid, NEITHER primary
    _write(tmp_path, rows, 93.0)
    generate(tmp_path / "registry.yaml", tmp_path / "canonical.json", tmp_path / "README.md", write=True)
    ok, problems = check(tmp_path / "registry.yaml", tmp_path / "canonical.json", tmp_path / "README.md")
    assert not ok
    assert any("no `primary`" in p for p in problems)


def test_single_valid_passes(tmp_path):
    _write(tmp_path, [_row("m-a", 93.0)], 93.0)
    generate(tmp_path / "registry.yaml", tmp_path / "canonical.json", tmp_path / "README.md", write=True)
    ok, problems = check(tmp_path / "registry.yaml", tmp_path / "canonical.json", tmp_path / "README.md")
    assert ok, problems
