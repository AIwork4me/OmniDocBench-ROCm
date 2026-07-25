"""Schema + conformance checks tied to ADR-0003 (repro recipe).

These cover the ``repro_recipe`` artifact sub-schema (a ``REPRO.yaml`` at repo
root pinning command, weights revision, backend, and environment) and the
``check_repo`` gate that fails when that file is missing. Kept separate from
``test_conformance.py`` so the general layout checks and the reproduction gate
evolve independently — same split as ``test_license_conformance.py``.
"""
from pathlib import Path

import yaml

from omnidocbench_rocm.conformance import check_repo
from omnidocbench_rocm.schema import validate_artifact

# Minimal conformant layout — mirrors ``tests/fixtures/conformant`` but built
# inline so the only delta between ``test_conformance_requires_repro_yaml`` and
# ``test_conformance_passes_with_repro_yaml`` is the ``REPRO.yaml`` file.
_REQUIRED_README_SECTIONS = ["Install", "Demo", "Evaluation", "Reproducibility", "Known Gaps"]

REPRO = {
    "command": "omnidocbench-rocm infer --adapter adapter/run_adapter.py "
    "--img-dir <v16> --out-dir preds",
    "weights_revision": "de8f10ad2f00a0cefd790b526de8a65dcfdb3205",
    "backend": "vllm",
    "environment": "/opt/venv (vLLM 0.16.1 ROCm)",
}


def _build_conformant_repo(repo: Path) -> None:
    """Create a repo that passes every existing check_repo requirement.

    The REPRO.yaml file is intentionally omitted so callers can add it (or not)
    to isolate the ADR-0003 gate.
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
    (repo / "NOTICE").write_text("fixture-model\nApache-2.0\n")


def test_repro_recipe_schema_valid():
    validate_artifact("repro_recipe", REPRO)  # must not raise


def test_repro_recipe_rejects_missing_field():
    bad = dict(REPRO); del bad["weights_revision"]
    try:
        validate_artifact("repro_recipe", bad)
        assert False, "should have raised"
    except Exception:
        pass


def test_conformance_requires_repro_yaml(tmp_path):
    repo = tmp_path / "model-repo"
    _build_conformant_repo(repo)
    report = check_repo(repo)
    assert any("REPRO.yaml" in f for f in report.failures), report.failures


def test_conformance_passes_with_repro_yaml(tmp_path):
    repo = tmp_path / "model-repo"
    _build_conformant_repo(repo)
    (repo / "REPRO.yaml").write_text(yaml.safe_dump(REPRO))
    report = check_repo(repo)
    assert "missing REPRO.yaml" not in report.failures
