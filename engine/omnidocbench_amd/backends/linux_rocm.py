from __future__ import annotations
import subprocess
from pathlib import Path
from .base import Backend
from .._paths import eval_venv

PDF_VALIDATION = "pdf_validation.py"
RESULT_DIR = Path("result")


class LinuxRocmBackend(Backend):
    """Runs OmniDocBench ``pdf_validation.py`` (Edit_dist + TEDS) in the
    eval-venv on a Linux/ROCm host.

    The metric_result filename follows OmniDocBench's ``build_save_name``
    convention: ``m_<version>_quick_match_metric_result.json`` (the
    ``m_`` prefix mirrors the dataset version tag used by the caller).
    """

    def __init__(self, checkout: Path | None = None):
        self.checkout = checkout

    def ensure_checkout(self, revision: str) -> Path:
        if self.checkout and (self.checkout / PDF_VALIDATION).exists():
            return self.checkout
        raise SystemExit(
            f"OmniDocBench checkout not found at {self.checkout}. "
            f"Clone + pin {revision}:\n"
            f"  git clone https://github.com/opendatalab/OmniDocBench.git {self.checkout}\n"
            f"  cd {self.checkout} && git checkout {revision} && pip install -e ."
        )

    def provision_cdm(self) -> None:
        # Task 14 implements real CDM; for now this is the no-CDM path.
        print("[cdm] linux-rocm: provision via engine/omnidocbench_amd/cdm/setup-linux.sh (Task 14)")

    def score(self, *, predictions_dir: Path, version: str, cdm: bool,
              run_stats_path: Path) -> Path:
        checkout = self.ensure_checkout(revision="master")  # v1.6 = master; pinned by caller
        venv_python = str(eval_venv("linux-rocm") / "bin" / "python")
        save = f"m_{version}_quick_match"
        cmd = [venv_python, str(checkout / PDF_VALIDATION),
               "--config", str(version), "--predictions", str(predictions_dir)]
        subprocess.run(cmd, cwd=checkout, check=True)
        return checkout / RESULT_DIR / f"{save}_metric_result.json"
