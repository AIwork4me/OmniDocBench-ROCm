"""Integration tests for the new v2 CLI subcommands (migrate / manifest / license / profiles)."""
import json
import subprocess
import sys
from pathlib import Path
import pytest

REPO = Path(__file__).resolve().parents[1]
FX = REPO / "tests" / "fixtures"


def _cli(*args, cwd=None):
    env = {"PYTHONPATH": str(REPO / "engine")}
    p = subprocess.run([sys.executable, "-m", "omnidocbench_rocm.cli", *args],
                       capture_output=True, text=True, cwd=cwd or REPO, env=env)
    return p


def test_migrate_subcommand_stdout_v2():
    p = _cli("migrate-model-card", str(FX / "v1_model_card.json"))
    assert p.returncode == 0, p.stderr
    obj = json.loads(p.stdout)
    assert obj["schema_version"] == 2


def test_migrate_check_exit_codes():
    p1 = _cli("migrate-model-card", str(FX / "v1_model_card.json"), "--check")
    assert p1.returncode == 1  # v1 -> needs migration
    p2 = _cli("migrate-model-card", str(FX / "v2_model_card.json"), "--check")
    assert p2.returncode == 0  # already v2


def test_license_classify_subcommand():
    p = _cli("license-classify", "Tencent Hunyuan Community License")
    assert p.returncode == 0, p.stderr
    obj = json.loads(p.stdout)
    assert obj["category"] == "restricted"


def test_manifest_subcommand_validates_example():
    p = _cli("manifest", str(REPO / "examples" / "rocmdoc.example.yaml"),
             "--card", str(REPO / "examples" / "model_card_v2.example.json"))
    assert p.returncode == 0, p.stdout + p.stderr


def test_manifest_subcommand_rejects_misalignment(tmp_path):
    # manifest declares only linux-rocm/vllm; a card claiming windows-hip must fail
    import yaml
    mf = tmp_path / "rocmdoc.yaml"
    mf.write_text(yaml.safe_dump({
        "schema_version": 1, "project": {"name": "x"}, "upstream": {"name": "u"},
        "model": {"id": "m"}, "licenses": {"code": {"category": "open-source-ai"}},
        "interfaces": ["adapter-script"],
        "implementations": [{"platform": "linux-rocm", "backend": "vllm", "status": "supported"}],
    }), encoding="utf-8")
    from omnidocbench_rocm.model_card_v2 import make_result_id
    bad_card = {"schema_version": 2, "model_id": "m", "results": [{
        "result_id": make_result_id(model_id="m", platform="windows-hip", backend="x", benchmark_version="v1.6"),
        "status": "valid", "assurance": "submitted",
        "benchmark": {"name": "OmniDocBench", "version": "v1.6"}, "metrics": {"overall": 1.0},
        "coverage": {"platform": "windows-hip"}, "implementation": {"backend": "x"}, "provenance": {}}]}
    card_path = tmp_path / "card.json"
    card_path.write_text(json.dumps(bad_card), encoding="utf-8")
    p = _cli("manifest", str(mf), "--card", str(card_path))
    assert p.returncode == 1
    assert "not declared" in p.stdout or "fake-support" in p.stdout


def test_conformance_profiles_subcommand_passes():
    p = _cli("conformance-profiles", "runtime-core", "--cli",
             str(FX / "fake_cli" / "success.py"))
    assert p.returncode == 0, p.stdout + p.stderr


def test_conformance_profiles_subcommand_fails_on_badjson():
    p = _cli("conformance-profiles", "runtime-core", "--cli",
             str(FX / "fake_cli" / "badjson.py"))
    assert p.returncode == 1
