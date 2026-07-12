from pathlib import Path
from scripts.check_conformance import check_repo
FIX = Path(__file__).parent / "fixtures"


def test_conformant_repo_passes():
    report = check_repo(FIX / "conformant")
    assert report.ok, report.failures


def test_nonconformant_repo_fails():
    report = check_repo(FIX / "nonconformant")
    assert not report.ok
    assert any("run_adapter" in f or "README" in f or "results" in f for f in report.failures)
