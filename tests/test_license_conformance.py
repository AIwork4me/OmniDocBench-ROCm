"""Conformance checks tied to ADR-0006 (per-repo NOTICE).

These cover the licensing-posture requirement that every model repo ships a
``NOTICE`` file. They are kept separate from ``test_conformance.py`` so the
general layout checks and the licensing gate evolve independently.
"""
from pathlib import Path

from omnidocbench_rocm.conformance import check_repo

# Minimal conformant layout — mirrors ``tests/fixtures/conformant`` but built
# inline so the only delta between ``test_conformance_requires_notice`` and
# ``test_conformance_passes_with_notice`` is the ``NOTICE`` file.
_REQUIRED_README_SECTIONS = ["Install", "Demo", "Evaluation", "Reproducibility", "Known Gaps"]


def _build_conformant_repo(repo: Path) -> None:
    """Create a repo that passes every existing check_repo requirement.

    The NOTICE file is intentionally omitted so callers can add it (or not) to
    isolate the ADR-0006 gate.
    """
    (repo / "adapter").mkdir(parents=True)
    (repo / "adapter" / "run_adapter.py").write_text("# stub\n")
    (repo / "eval" / "configs").mkdir(parents=True)
    (repo / "eval" / "configs" / "omnidocbench_v16.yaml").write_text("version: v1.6\n")
    # A declared results dir must hold a real artifact (not just .gitkeep).
    (repo / "results" / "omnidocbench" / "v16" / "linux-rocm").mkdir(parents=True)
    (repo / "results" / "omnidocbench" / "v16" / "linux-rocm" / "_run_stats.json").write_text("{}\n")
    readme = "# fixture-model\n\nA conformant fixture.\n\n"
    for sec in _REQUIRED_README_SECTIONS:
        readme += f"## {sec}\n\nbody\n\n"
    (repo / "README.md").write_text(readme)
    (repo / "README.zh-CN.md").write_text(readme)
    (repo / "examples").mkdir()
    (repo / "examples" / "run_demo.sh").write_text("#!/bin/sh\n")
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "fixture-model"\nversion = "0.0.1"\n'
        'dependencies = ["omnidocbench-rocm>=0.2.0"]\n'
    )


def test_conformance_requires_notice(tmp_path):
    repo = tmp_path / "model-repo"
    _build_conformant_repo(repo)
    report = check_repo(repo)
    assert any("NOTICE" in f for f in report.failures), report.failures


def test_conformance_passes_with_notice(tmp_path):
    repo = tmp_path / "model-repo"
    _build_conformant_repo(repo)
    (repo / "NOTICE").write_text("Model-ROCm\nApache-2.0\n")
    report = check_repo(repo)
    assert "missing NOTICE file" not in report.failures
