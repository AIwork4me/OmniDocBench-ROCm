from pathlib import Path
from scripts.check_conformance import check_repo
FIX = Path(__file__).parent / "fixtures"


def test_conformant_repo_passes():
    report = check_repo(FIX / "conformant")
    assert report.ok, report.failures


def test_nonconformant_repo_fails():
    report = check_repo(FIX / "nonconformant")
    assert not report.ok
    assert any("run_adapter" in f for f in report.failures)
    assert any("README" in f for f in report.failures)
    assert any("results" in f for f in report.failures)


def test_wrong_engine_dep_fails_conformance(tmp_path):
    """A repo whose pyproject does not depend on omnidocbench-rocm is non-conformant."""
    import shutil
    src = FIX / "conformant"
    dst = tmp_path / "repo"
    shutil.copytree(src, dst)
    pp = dst / "pyproject.toml"
    pp.write_text(
        pp.read_text(encoding="utf-8").replace(
            "omnidocbench-rocm", "some-other-engine"
        ),
        encoding="utf-8",
    )
    report = check_repo(dst)
    assert not report.ok
    assert any("omnidocbench-rocm" in f for f in report.failures)


def test_conformance_reads_project_text_as_utf8(monkeypatch):
    """Guard against locale-dependent reads on Windows (for example CP936)."""
    original_read_text = Path.read_text

    def require_utf8(path, *args, **kwargs):
        if FIX in path.parents and path.name in {
            "README.md",
            "README.zh-CN.md",
            "pyproject.toml",
            "model_card.json",
        }:
            encoding = kwargs.get("encoding", args[0] if args else None)
            assert encoding == "utf-8", f"locale-dependent read: {path}"
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", require_utf8)
    report = check_repo(FIX / "conformant")
    assert report.ok, report.failures
