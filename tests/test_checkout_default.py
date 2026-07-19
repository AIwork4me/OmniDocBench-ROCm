from pathlib import Path
from omnidocbench_rocm._paths import checkout
from omnidocbench_rocm.backends.linux_rocm import LinuxRocmBackend


def test_checkout_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("OMNIDOCBENCH_CHECKOUT", str(tmp_path))
    assert checkout() == tmp_path


def test_checkout_default(monkeypatch):
    monkeypatch.delenv("OMNIDOCBENCH_CHECKOUT", raising=False)
    assert checkout() == Path("/workspace/OmniDocBench")


def test_backend_uses_default_checkout_when_none(monkeypatch, tmp_path):
    """get_backend('linux-rocm') builds LinuxRocmBackend(checkout=None); ensure_checkout
    must fall back to the OMNIDOCBENCH_CHECKOUT default instead of SystemExit."""
    (tmp_path / "pdf_validation.py").write_text("# stub")
    monkeypatch.setenv("OMNIDOCBENCH_CHECKOUT", str(tmp_path))
    b = LinuxRocmBackend()  # no explicit checkout, like get_backend() builds
    assert b.ensure_checkout() == tmp_path


def test_explicit_checkout_overrides_default(monkeypatch, tmp_path):
    other = tmp_path / "explicit"
    other.mkdir()
    (other / "pdf_validation.py").write_text("# stub")
    monkeypatch.setenv("OMNIDOCBENCH_CHECKOUT", "/nonexistent/default")
    b = LinuxRocmBackend(checkout=other)
    assert b.ensure_checkout() == other
