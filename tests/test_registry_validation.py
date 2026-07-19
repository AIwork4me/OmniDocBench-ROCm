from pathlib import Path
import yaml
from scripts.validate_registry import validate_registry

GOOD = [{"model_id": "x", "repo": "AIwork4me/X-ROCm",
         "platforms": {"linux-rocm": {"badge": "verified", "overall": 95.0},
                       "windows-hip": {"badge": "community-wanted", "overall": None}}}]


def test_valid_registry():
    assert validate_registry(GOOD) == []


def test_duplicate_and_bad_fields():
    rows = [
        {"model_id": "x", "repo": "bad repo", "platforms": {}},
        {"model_id": "x", "repo": "AIwork4me/Y-ROCm",
         "platforms": {"linux-rocm": {"badge": "garbage", "overall": "high"}}},
    ]
    errs = validate_registry(rows)
    assert any("duplicate" in e for e in errs)
    assert any("illegal repo" in e for e in errs)
    assert any("missing platforms" in e for e in errs)
    assert any("bad badge" in e for e in errs)
    assert any("overall" in e for e in errs)


def test_real_registry_valid():
    reg = Path(__file__).resolve().parent.parent / "hub" / "registry.yaml"
    rows = yaml.safe_load(reg.read_text()) or []
    assert validate_registry(rows) == []
