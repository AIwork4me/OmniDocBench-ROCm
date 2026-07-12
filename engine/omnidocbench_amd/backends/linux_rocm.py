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
    convention: ``<predictions_dir.name>_quick_match_metric_result.json``
    (``build_save_name`` = basename(prediction_path) + "_" + match_method).
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
        # TODO Task 16: accept + plumb a pinned revision instead of hardcoding master
        checkout = self.ensure_checkout(revision="master")  # v1.6 = master; pinned by caller
        # TODO Task 16: pass cdm flag + run_stats to pdf_validation / publish
        venv_python = str(eval_venv("linux-rocm") / "bin" / "python")
        # OmniDocBench build_save_name = basename(prediction_path) + "_" + match_method
        save = f"{predictions_dir.name}_quick_match"
        # TODO Task 16: wire version into the scoring config
        cmd = [venv_python, str(checkout / PDF_VALIDATION),
               "--config", str(version), "--predictions", str(predictions_dir)]
        subprocess.run(cmd, cwd=checkout, check=True)
        return checkout / RESULT_DIR / f"{save}_metric_result.json"
