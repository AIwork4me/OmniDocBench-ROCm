"""Tests for the CLI -> adapter bridge (ADR-0011, §10 adapter-contract preservation)."""
import json
import subprocess
import sys
from pathlib import Path
import pytest

REPO = Path(__file__).resolve().parents[1]
CONF = REPO / "tests" / "fixtures" / "conformant"


def _bridge(*args, cwd=None):
    p = subprocess.run([sys.executable, "-m", "omnidocbench_rocm.cli_bridge", *args],
                       capture_output=True, text=True, cwd=cwd or REPO)
    return p


def test_version_json():
    p = _bridge("version", "--json")
    assert p.returncode == 0
    obj = json.loads(p.stdout)
    assert obj["name"] and obj["version"]


def test_doctor_json_status():
    p = _bridge("doctor", "--json", "--repo", str(CONF))
    assert p.returncode == 0
    obj = json.loads(p.stdout)
    assert obj["status"] in ("ready", "not-ready")
    assert "checks" in obj


def test_parse_success(tmp_path):
    # the conformant fixture adapter reports engine='fixture'; request a matching backend
    p = _bridge("parse", "--adapter", str(CONF / "adapter" / "run_adapter.py"),
                "--img-dir", str(CONF / "examples"), "--out-dir", str(tmp_path / "out"),
                "--platform", "linux-rocm", "--backend", "fixture", "--json")
    assert p.returncode == 0, p.stderr
    obj = json.loads(p.stdout)
    assert obj["status"] == "ok"
    assert obj["backend"] == "fixture"
    assert obj["page_count"] >= 1


def test_parse_backend_mismatch_exits_3(tmp_path):
    p = _bridge("parse", "--adapter", str(CONF / "adapter" / "run_adapter.py"),
                "--img-dir", str(CONF / "examples"), "--out-dir", str(tmp_path / "out"),
                "--platform", "linux-rocm", "--backend", "vllm", "--json")
    assert p.returncode == 3  # requested vllm, adapter reports fixture
    obj = json.loads(p.stdout)
    assert obj["status"] == "failed" and "mismatch" in obj.get("error", "")


def test_parse_missing_adapter_exits_usage(tmp_path):
    p = _bridge("parse", "--adapter", str(tmp_path / "nope.py"),
                "--img-dir", str(CONF / "examples"), "--out-dir", str(tmp_path / "o"),
                "--platform", "linux-rocm", "--json")
    assert p.returncode == 2  # USAGE
