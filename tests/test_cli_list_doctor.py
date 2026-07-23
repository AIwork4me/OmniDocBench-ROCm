"""Tests for the ``omnidocbench-rocm list`` discovery subcommand (ADR-0005).

``list`` loads a registry.yaml and prints each ``model_id`` + best badge
(+ license) as text or JSON. It reuses the package-level registry loader +
``_best_badge`` (moved out of ``scripts/`` so the installed CLI can import
them without a ``scripts/`` path hack).
"""
import json

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
