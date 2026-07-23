import os
from pathlib import Path

CDM = Path(__file__).resolve().parent.parent / "engine" / "omnidocbench_rocm" / "cdm"


def test_setup_script_exists_and_executable():
    p = CDM / "setup-linux.sh"
    assert p.exists()
    assert os.access(p, os.X_OK)
    text = p.read_text(encoding="utf-8")
    assert "texlive-full" in text
    assert "ImageMagick 7" in text or "IM7" in text or "magick" in text
    assert "already present" in text  # idempotency marker


def test_smoke_probe_exists_and_executable():
    p = CDM / "smoke_cdm.sh"
    assert p.exists()
    assert os.access(p, os.X_OK)
    assert "grayscale" in p.read_text(encoding="utf-8")  # #grayscale guard


def test_runner_imports():
    from omnidocbench_rocm.cdm_runner import provision_cdm_linux
    assert callable(provision_cdm_linux)
