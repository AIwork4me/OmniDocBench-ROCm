from __future__ import annotations
import subprocess
from pathlib import Path
from .base import Backend
from .._paths import eval_venv, data_root, checkout as checkout_path
from .._refs import OMNIDOCBENCH_V16_REF
from ..config_render import render_config

PDF_VALIDATION = "pdf_validation.py"
RESULT_DIR = Path("result")
DEFAULT_TEMPLATE = Path(__file__).resolve().parent.parent / "data" / "omnidocbench_v16.yaml.tmpl"


class LinuxRocmBackend(Backend):
    """Runs OmniDocBench ``pdf_validation.py`` (Edit_dist + TEDS [+ CDM]) in the
    3.11 eval-venv on a Linux/ROCm host. Scoring is config-driven: predictions
    and ground truth live inside the rendered config, and pdf_validation takes a
    single ``--config <yaml>`` argument.
    """

    def __init__(self, checkout: Path | None = None):
        self.checkout = checkout

    def ensure_checkout(self, revision: str = OMNIDOCBENCH_V16_REF) -> Path:
        # Fall back to the OMNIDOCBENCH_CHECKOUT default when no explicit path
        # is given (get_backend() builds the backend with checkout=None).
        co = self.checkout or checkout_path()
        if (co / PDF_VALIDATION).exists():
            return co
        raise SystemExit(
            f"OmniDocBench checkout not found at {co} (pdf_validation.py missing). "
            f"Clone + pin {revision}:\n"
            f"  git clone https://github.com/opendatalab/OmniDocBench.git {co}\n"
            f"  cd {co} && git checkout {revision} && pip install -e .\n"
            f"  (or set OMNIDOCBENCH_CHECKOUT to an existing checkout)"
        )

    def provision_cdm(self) -> None:
        # Wired in Commit 2 (host CDM toolchain). Kept honest here.
        from ..cdm_runner import provision_cdm_linux
        provision_cdm_linux()

    def score(self, *, predictions_dir: Path, version: str, cdm: bool,
              run_stats_path: Path, scoring_config: Path | None = None,
              dataset_dir: Path | None = None) -> Path:
        checkout = self.ensure_checkout()
        template = Path(scoring_config) if scoring_config else DEFAULT_TEMPLATE
        ds_dir = Path(dataset_dir) if dataset_dir else data_root() / "datasets" / version
        gt_path = ds_dir / "OmniDocBench.json"
        if not gt_path.exists():
            raise SystemExit(f"ground truth not found: {gt_path} (run the download stage)")
        rendered = render_config(template, prediction_path=Path(predictions_dir),
                                 gt_path=gt_path, cdm=cdm)
        venv_python = str(eval_venv("linux-rocm") / "bin" / "python")
        save = f"{Path(predictions_dir).name}_quick_match"
        cmd = [venv_python, str(checkout / PDF_VALIDATION), "--config", str(rendered)]
        subprocess.run(cmd, cwd=checkout, check=True)
        return checkout / RESULT_DIR / f"{save}_metric_result.json"
