from pathlib import Path
import pytest
import yaml
from scripts.validate_registry import validate_registry, validate_against_model_card

GOOD = [{"model_id": "x", "repo": "AIwork4me/X-ROCm",
         "license": "Apache-2.0", "commercial_use": "no restriction",
         "platforms": {"linux-rocm": {"badge": "verified", "overall": 95.0},
                       "windows-hip": {"badge": "community-wanted", "overall": None}}}]


def test_registry_requires_license():
    bad = [{k: v for k, v in GOOD[0].items() if k != "license"}]
    errs = validate_registry(bad)
    assert any("license" in e for e in errs), errs


def test_registry_requires_commercial_use():
    bad = [{k: v for k, v in GOOD[0].items() if k != "commercial_use"}]
    errs = validate_registry(bad)
    assert any("commercial_use" in e for e in errs), errs


def test_valid_registry():
    assert validate_registry(GOOD) == []


def test_model_card_cross_check_consistent():
    mc = {"model_id": "x", "overall": 95.0, "badge": {"linux-rocm": "verified"}}
    assert validate_against_model_card(GOOD, mc, "x", "linux-rocm") == []


def test_model_card_cross_check_drift_rejected():
    mc = {"model_id": "x", "overall": 90.0, "badge": {"linux-rocm": "community"}}
    errs = validate_against_model_card(GOOD, mc, "x", "linux-rocm")
    assert any("overall" in e for e in errs)
    assert any("badge" in e for e in errs)


def test_model_card_cross_check_missing_model():
    mc = {"model_id": "missing", "overall": 95.0, "badge": {"linux-rocm": "verified"}}
    errs = validate_against_model_card(GOOD, mc, "missing", "linux-rocm")
    assert any("no row" in e for e in errs)


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
    """The live hub/registry.yaml must validate after Task 11 populated
    license/commercial_use on every entry (ADR-0006)."""
    reg = Path(__file__).resolve().parent.parent / "hub" / "registry.yaml"
    rows = yaml.safe_load(reg.read_text(encoding="utf-8")) or []
    assert validate_registry(rows) == []


def test_live_registry_validates():
    """Regression (Task 11 Step 1): load the live registry via the package's
    generate_registry loader and assert validate_registry reports no errors."""
    import sys
    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root / "scripts"))
    from generate_registry import generate_registry
    errors = validate_registry(generate_registry(repo_root / "hub" / "registry.yaml"))
    assert errors == [], errors
