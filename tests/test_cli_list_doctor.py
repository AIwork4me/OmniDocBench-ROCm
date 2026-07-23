"""Tests for the ``omnidocbench-rocm list`` discovery subcommand (ADR-0005) and
the ``doctor`` readiness subcommand (ADR-0005 readiness hint).

``list`` loads a registry.yaml and prints each ``model_id`` + best badge
(+ license) as text or JSON. It reuses the package-level registry loader +
``_best_badge`` (moved out of ``scripts/`` so the installed CLI can import
them without a ``scripts/`` path hack).

``doctor`` runs ``check_repo`` and prints a READY / NOT READY verdict plus a
best-effort readiness hint (``adapter_config.py present: <bool>``).
"""
import json

from pathlib import Path

import yaml

REG = """
- model_id: a
  repo: AIwork4me/A-ROCm
  license: Apache-2.0
  commercial_use: none
  platforms:
    linux-rocm: {badge: verified, overall: 95.0}
- model_id: b
  repo: AIwork4me/B-ROCm
  license: MIT
  commercial_use: none
  platforms:
    linux-rocm: {badge: community, overall: 93.0}
"""


def test_cli_list_text(tmp_path):
    reg = tmp_path / "registry.yaml"; reg.write_text(REG)
    from omnidocbench_rocm.cli import main
    rc = main(["list", "--registry", str(reg), "--format", "text"])
    assert rc == 0


def test_cli_list_json(tmp_path, capsys):
    reg = tmp_path / "registry.yaml"; reg.write_text(REG)
    from omnidocbench_rocm.cli import main
    rc = main(["list", "--registry", str(reg), "--format", "json"])
    out = json.loads(capsys.readouterr().out)
    ids = [m["model_id"] for m in out]
    assert ids == ["a", "b"] and out[0]["best_badge"] == "verified"


# ---------------------------------------------------------------------------
# doctor subcommand (ADR-0005 readiness hint)
# ---------------------------------------------------------------------------

# Minimal conformant layout — mirrors the helper pattern in
# ``test_license_conformance.py`` / ``test_repro_recipe.py`` but built to pass
# every current ``check_repo`` gate (incl. NOTICE + REPRO.yaml) so the clean-repo
# test can drop the ``adapter_config.py`` readiness hint on top.
_REQUIRED_README_SECTIONS = ["Install", "Demo", "Evaluation", "Reproducibility", "Known Gaps"]

REPRO = {
    "command": "omnidocbench-rocm infer --adapter adapter/run_adapter.py "
    "--img-dir <v16> --out-dir preds",
    "weights_revision": "de8f10ad2f00a0cefd790b526de8a65dcfdb3205",
    "backend": "vllm",
    "environment": "/opt/venv (vLLM 0.16.1 ROCm)",
}


def _build_conformant_repo(repo: Path) -> None:
    """Create a repo that passes every current ``check_repo`` requirement."""
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
    (repo / "REPRO.yaml").write_text(yaml.safe_dump(REPRO))


def test_cli_doctor_reports_missing_notice(tmp_path, capsys):
    from omnidocbench_rocm.cli import main
    repo = tmp_path / "repo"; (repo / "adapter").mkdir(parents=True)
    (repo / "adapter" / "run_adapter.py").write_text("# stub\n")
    rc = main(["doctor", str(repo)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "NOTICE" in out  # missing NOTICE flagged


def test_cli_doctor_clean_repo(tmp_path, capsys):
    repo = tmp_path / "repo"
    _build_conformant_repo(repo)
    # The readiness hint keys off adapter/adapter_config.py — include it so the
    # hint reports ``True`` on a clean repo.
    (repo / "adapter" / "adapter_config.py").write_text("# stub\n")
    from omnidocbench_rocm.cli import main
    rc = main(["doctor", str(repo)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "READY: repo is conformant." in out
    assert "adapter_config.py present: True" in out


def test_cli_doctor_clean_repo_without_adapter_config(tmp_path, capsys):
    repo = tmp_path / "repo"
    _build_conformant_repo(repo)
    # adapter_config.py absent — repo is still conformant, hint reports False.
    from omnidocbench_rocm.cli import main
    rc = main(["doctor", str(repo)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "READY: repo is conformant." in out
    assert "adapter_config.py present: False" in out
