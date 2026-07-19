# Linux-ROCm Engine Readiness for Verified Onboarding — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the OmniDocBench-ROCm Linux-ROCm engine produce real, reproducible, CDM-inclusive scores and reach a `verified` flagship entry — by fixing `score()` (config rendering + pinned revision + CDM variant), adding an end-to-end-usable host CDM toolchain, a self-contained `Dockerfile.repro` + `VERIFIED.yaml` tolerance check, a 3.11 eval-venv, and an onboarding runbook whose success definition is a verified entry.

**Architecture:** `score()` renders an OmniDocBench config YAML (CDM = a metric-list variant) and invokes `pdf_validation --config <rendered>` (single arg); the OmniDocBench checkout is pinned to one ref. The host CDM toolchain (`texlive-full`/IM7/gs/node) is the fast `community` path; a self-contained `Dockerfile.repro` pins the same toolchain for the `verified` scoring reproduction. `verified` reproduces **scoring** from committed predictions (the CDM-toolchain-sensitive part), not inference.

**Tech Stack:** Python 3.11 (eval-venv) / 3.12 (engine dev), hatchling, pyyaml, jsonschema, argparse, bash provisioning, Docker (for the repro image, executed on a Docker-capable box — not in this env).

## Global Constraints

- **Repo / branch:** `/workspace/omnidocbench-rocm`, branch `feat/linux-rocm-cdm-verified-onboarding` (already checked out). Remote `AIwork4me/OmniDocBench-ROCm`.
- **Platform-repo scope only (Approach 1).** PaddleOCR-VL adapter + serving is OUT of scope (follow-on spec). Windows/DirectML out of scope.
- **`verified` bar (first flagship):** reproduce **scoring** (Edit_dist + TEDS + CDM) from committed predictions in the pinned Docker image, within tolerance. **Do NOT force full inference-in-Docker** for the first run.
- **No faking.** CDM-invalid shows as `pending`/null, never a number. `publish` refuses `limit_pages != null` subsets (full-set enforcement). No auto-promotion to `verified`.
- **Schema stays v1.** No metric-formula changes. Frozen: `OmniDocBench` (upstream), platform keys `linux-rocm`/`windows-hip`, results path.
- **Heavy data off `/workspace`:** eval-venv, datasets, predictions live under `${OMNIDOCBENCH_ROCM_DATA:-/root/ocr-eval/omnidocbench-rocm-data}` (`engine/omnidocbench_rocm/_paths.py`). Never on the 10 GB NFS repo.
- **Confirmed box facts:** `gfx1100` present; OmniDocBench checkout at `/workspace/OmniDocBench` (real entry `src/core/pipeline.py`, CLI `--config`/`-c`); CDM enabled via `display_formula.metric: [Edit_dist, CDM]` + `cdm_workers` (precedent `configs/unlimited_rocm_30_cdm.yaml`); `/usr/bin/python3.11` (3.11.15) available; **Docker is NOT installed in this env** (the repro step runs on a Docker-capable maintainer box).
- **Gated execution:** the 1651-page GPU eval and the Docker `verified` repro are resumable gated steps — made ready by this plan, not scripted minute-by-minute. "Gated = when, not whether."

---

## Commit 1 — `feat(engine): real score() with config rendering, pinned revision, CDM variant`

### Task 1.1: Default scoring-config template + `OMNIDOCBENCH_V16_REF` constant

**Files:**
- Create: `engine/omnidocbench_rocm/data/omnidocbench_v16.yaml.tmpl`
- Create: `engine/omnidocbench_rocm/_refs.py`

- [ ] **Step 1: Determine the v1.6 ref from the checkout:**
```bash
git -C /workspace/OmniDocBench tag --list '*1.6*' '*v1.6*' 2>/dev/null
git -C /workspace/OmniDocBench rev-parse HEAD
```
Use the v1.6 tag if present; otherwise use the printed HEAD short SHA. Record it as `OMNIDOCBENCH_V16_REF` below.
- [ ] **Step 2: Create `engine/omnidocbench_rocm/_refs.py`** (replace `<REF>` with the value from Step 1):
```python
"""Pinned upstream refs so dataset and scorer stay aligned and reproducible."""
from __future__ import annotations

# OmniDocBench checkout commit matching the v1.6 dataset. Must align with the
# revision stage_download pins. Bump only with a coordinated dataset bump.
OMNIDOCBENCH_V16_REF = "<REF>"
```
- [ ] **Step 3: Create the template `engine/omnidocbench_rocm/data/omnidocbench_v16.yaml.tmpl`** (the non-CDM base; paths are overwritten by the renderer):
```yaml
end2end_eval:
  metrics:
    text_block: {metric: [Edit_dist]}
    display_formula: {metric: [Edit_dist]}
    table: {metric: [TEDS, Edit_dist], teds_workers: 13}
    reading_order: {metric: [Edit_dist]}
  dataset:
    dataset_name: end2end_dataset
    ground_truth: {data_path: PLACEHOLDER}
    prediction: {data_path: PLACEHOLDER}
    match_method: quick_match
    match_workers: 13
    quick_match_truncated_timeout_sec: 300
    match_timeout_sec: 420
    timeout_fallback_max_chunk_span: 10
    timeout_fallback_order_penalty: 0.1
```

### Task 1.2 (TDD): `render_config()` — config rendering + CDM variant

**Files:**
- Create: `engine/omnidocbench_rocm/config_render.py`
- Test: `tests/test_config_render.py`

**Interfaces:**
- Produces: `render_config(template_path: Path, *, prediction_path: Path, gt_path: Path, cdm: bool, workers: int = 13) -> Path` (writes a rendered YAML to a tempfile and returns its path — avoids polluting the package data dir). When `cdm=True`, `display_formula.metric` becomes `[Edit_dist, CDM]` and `cdm_workers` is set.

- [ ] **Step 1: Write the failing test `tests/test_config_render.py`:**
```python
import yaml
from pathlib import Path
from omnidocbench_rocm.config_render import render_config

TEMPLATE = Path(__file__).resolve().parent.parent / "engine" / "omnidocbench_rocm" / "data" / "omnidocbench_v16.yaml.tmpl"


def _load(p):
    return yaml.safe_load(Path(p).read_text())


def test_render_paths_nocdm(tmp_path):
    out = render_config(TEMPLATE, prediction_path=Path("/preds/x"),
                        gt_path=Path("/data/OmniDocBench.json"), cdm=False)
    cfg = _load(out)["end2end_eval"]
    assert cfg["dataset"]["prediction"]["data_path"] == "/preds/x"
    assert cfg["dataset"]["ground_truth"]["data_path"] == "/data/OmniDocBench.json"
    assert cfg["metrics"]["display_formula"]["metric"] == ["Edit_dist"]


def test_render_cdm_variant(tmp_path):
    out = render_config(TEMPLATE, prediction_path=Path("/preds/x_cdm"),
                        gt_path=Path("/data/OmniDocBench.json"), cdm=True)
    df = _load(out)["end2end_eval"]["metrics"]["display_formula"]
    assert df["metric"] == ["Edit_dist", "CDM"]
    assert df["cdm_workers"] == 13
```
- [ ] **Step 2: Run — expect FAIL** (`ModuleNotFoundError: omnidocbench_rocm.config_render`):
```bash
python -m pytest tests/test_config_render.py -q
```
- [ ] **Step 3: Create `engine/omnidocbench_rocm/config_render.py`:**
```python
"""Render an OmniDocBench scoring config from a template.

OmniDocBench scoring is config-driven: ``pdf_validation.py --config <yaml>``.
Predictions + ground truth live *inside* the config, not as CLI flags. CDM is
enabled by adding ``CDM`` to ``display_formula.metric`` (+ ``cdm_workers``).
"""
from __future__ import annotations
import os
import tempfile
import yaml
from pathlib import Path


def render_config(template_path: Path, *, prediction_path: Path,
                  gt_path: Path, cdm: bool, workers: int = 13) -> Path:
    """Render the template into a concrete config YAML and return its path.

    Overwrites ``dataset.prediction.data_path`` + ``dataset.ground_truth.data_path``.
    When ``cdm`` is True, appends ``CDM`` to ``display_formula.metric`` and sets
    ``cdm_workers`` (matches the ``unlimited_rocm_30_cdm.yaml`` precedent).
    Writes to a tempfile so the package data dir is not polluted; pdf_validation
    reads it by absolute path.
    """
    template_path = Path(template_path)
    cfg = yaml.safe_load(template_path.read_text(encoding="utf-8"))
    ds = cfg["end2end_eval"]["dataset"]
    ds["prediction"]["data_path"] = str(prediction_path)
    ds["ground_truth"]["data_path"] = str(gt_path)
    if cdm:
        df = cfg["end2end_eval"]["metrics"]["display_formula"]
        metric = df.setdefault("metric", [])
        if "CDM" not in metric:
            metric.append("CDM")
        df.setdefault("cdm_workers", workers)
    fd, name = tempfile.mkstemp(prefix="omnidocbench_cfg_", suffix=".yaml")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(yaml.safe_dump(cfg, sort_keys=False))
    return Path(name)
```
- [ ] **Step 4: Run — expect PASS:**
```bash
python -m pytest tests/test_config_render.py -q
```

### Task 1.3 (TDD): `score()` uses the rendered config + single-arg invocation + pinned revision

**Files:**
- Modify: `engine/omnidocbench_rocm/backends/linux_rocm.py`
- Test: `tests/test_backends.py` (extend)

**Interfaces:**
- Produces: `LinuxRocmBackend.score(*, predictions_dir, version, cdm, run_stats_path, scoring_config=None, dataset_dir=None) -> Path`. `scoring_config` overrides the template path (model-repo override); `dataset_dir` locates `OmniDocBench.json`. Invocation is `[venv_python, pdf_validation.py, "--config", <rendered>]`. Checkout pinned via `OMNIDOCBENCH_V16_REF`.

- [ ] **Step 1: Add failing tests** to `tests/test_backends.py`:
```python
def test_score_invokes_pdf_validation_with_config_only(tmp_path):
    """score() renders a config and calls pdf_validation --config <path> (no --predictions)."""
    from omnidocbench_rocm.backends.linux_rocm import LinuxRocmBackend
    backend = LinuxRocmBackend(checkout=tmp_path / "odb")
    (tmp_path / "odb").mkdir()
    (tmp_path / "odb" / "pdf_validation.py").write_text("# stub")
    (tmp_path / "result").mkdir()
    preds = tmp_path / "preds"; preds.mkdir()
    ds_dir = tmp_path / "ds"; ds_dir.mkdir()
    (ds_dir / "OmniDocBench.json").write_text("{}")
    with patch("omnidocbench_rocm.backends.linux_rocm.subprocess.run") as run, \
         patch("omnidocbench_rocm.backends.linux_rocm.eval_venv") as ev:
        ev.return_value = tmp_path / "venv"
        (tmp_path / "venv" / "bin").mkdir(parents=True)
        (tmp_path / "venv" / "bin" / "python").write_text("#!/bin/sh\n")
        backend.score(predictions_dir=preds, version="v16", cdm=False,
                      run_stats_path=tmp_path / "rs.json", dataset_dir=ds_dir)
    cmd = run.call_args.args[0]
    assert cmd[1].endswith("pdf_validation.py")
    assert cmd[2] == "--config"
    assert "--predictions" not in cmd


def test_score_cdm_variant_rendered(tmp_path):
    from omnidocbench_rocm.backends.linux_rocm import LinuxRocmBackend
    import yaml
    backend = LinuxRocmBackend(checkout=tmp_path / "odb")
    (tmp_path / "odb").mkdir(); (tmp_path / "odb" / "pdf_validation.py").write_text("# stub")
    (tmp_path / "result").mkdir()
    preds = tmp_path / "preds_cdm"; preds.mkdir()
    ds_dir = tmp_path / "ds"; ds_dir.mkdir(); (ds_dir / "OmniDocBench.json").write_text("{}")
    captured = {}
    def fake_run(cmd, **kw):
        captured["config"] = cmd[3]
        (tmp_path / "result" / "preds_cdm_quick_match_metric_result.json").write_text("{}")
        class R: returncode = 0
        return R()
    with patch("omnidocbench_rocm.backends.linux_rocm.subprocess.run", side_effect=fake_run), \
         patch("omnidocbench_rocm.backends.linux_rocm.eval_venv") as ev:
        ev.return_value = tmp_path / "venv"
        (tmp_path / "venv" / "bin").mkdir(parents=True)
        (tmp_path / "venv" / "bin" / "python").write_text("#!/bin/sh\n")
        backend.score(predictions_dir=preds, version="v16", cdm=True,
                      run_stats_path=tmp_path / "rs.json", dataset_dir=ds_dir)
    cfg = yaml.safe_load(open(captured["config"]))["end2end_eval"]["metrics"]["display_formula"]
    assert "CDM" in cfg["metric"]
```
- [ ] **Step 2: Run — expect FAIL** (current `score()` passes `--predictions` and ignores `dataset_dir`/CDM):
```bash
python -m pytest tests/test_backends.py::test_score_invokes_pdf_validation_with_config_only tests/test_backends.py::test_score_cdm_variant_rendered -q
```
- [ ] **Step 3: Replace `engine/omnidocbench_rocm/backends/linux_rocm.py` with:**
```python
from __future__ import annotations
import subprocess
from pathlib import Path
from .base import Backend
from .._paths import eval_venv, data_root
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
        if self.checkout and (self.checkout / PDF_VALIDATION).exists():
            return self.checkout
        raise SystemExit(
            f"OmniDocBench checkout not found at {self.checkout}. "
            f"Clone + pin {revision}:\n"
            f"  git clone https://github.com/opendatalab/OmniDocBench.git {self.checkout}\n"
            f"  cd {self.checkout} && git checkout {revision} && pip install -e ."
        )

    def provision_cdm(self) -> None:
        # Wired in Commit 2 (host CDM toolchain). Kept honest here.
        from .cdm_runner import provision_cdm_linux
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
```
- [ ] **Step 4: Run — expect PASS:**
```bash
python -m pytest tests/test_backends.py -q
```
- [ ] **Step 5: Wire `dataset_dir`/`scoring_config` through `cli.py`.** In `engine/omnidocbench_rocm/cli.py`, add `--scoring-config` (default `""`) and `--dataset-dir` (default `""`) to the `score` and `run` subparsers, and pass them through `stage_score`/`stage_publish` to `backend.score(...)`. (Follow the existing `--adapter`/`--model-id` plumbing pattern; empty string → `None`.)

### Task 1.4: Verify + commit

- [ ] **Step 1: Full suite + brand gate:**
```bash
python -m pytest -q
python scripts/check_brand.py
```
- [ ] **Step 2: Commit.**
```bash
git add -A
git commit -m "feat(engine): real score() with config rendering, pinned revision, CDM variant

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Commit 2 — `feat(cdm): host CDM toolchain + smoke probe`

### Task 2.1: `setup-linux.sh` (idempotent CDM toolchain) + `smoke_cdm.sh`

**Files:**
- Create: `engine/omnidocbench_rocm/cdm/setup-linux.sh`
- Create: `engine/omnidocbench_rocm/cdm/smoke_cdm.sh`
- Create: `engine/omnidocbench_rocm/cdm_runner.py` (the `provision_cdm_linux()` called from `linux_rocm.py`)

- [ ] **Step 1: Create `engine/omnidocbench_rocm/cdm/setup-linux.sh`:**
```bash
#!/usr/bin/env bash
# Idempotent host CDM toolchain for Linux/ROCm: texlive-full + ImageMagick 7 +
# ghostscript + node. The CDM metric compiles formulas (LaTeX) -> PDF ->
# rasterize (IM7) -> color-match. IM6 silently flattens color formulas to
# grayscale (#grayscale); this script enforces IM7. See docs/pitfalls.md.
set -euo pipefail

need=()
dpkg -s texlive-full      >/dev/null 2>&1 || need+=(texlive-full)
command -v gs             >/dev/null 2>&1 || need+=(ghostscript)
command -v node           >/dev/null 2>&1 || need+=(nodejs)
if [ ${#need[@]} -gt 0 ]; then
  echo "[cdm] apt install: ${need[*]}"
  sudo apt-get update -qq && sudo apt-get install -y -qq "${need[@]}"
else
  echo "[cdm] texlive/ghostscript/node: already present"
fi

# ImageMagick 7 (NOT the IM6 default on Ubuntu 22.04 — IM6 flattens color).
if ! command -v magick >/dev/null 2>&1; then
  echo "[cdm] installing ImageMagick 7"
  sudo apt-get install -y -qq build-essential pkg-config libjpeg-dev libpng-dev libtiff-dev zlib1g-dev
  IM=7.1.1-38
  curl -fsSL "https://imagemagick.org/archive/releases/ImageMagick-${IM}.tar.xz" -o /tmp/im7.tar.xz
  tar -xf /tmp/im7.tar.xz -C /tmp && cd /tmp/ImageMagick-${IM}
  ./configure --disable-docs && make -j"$(nproc)" && sudo make install && sudo ldconfig
  cd - >/dev/null
else
  echo "[cdm] magick (IM7): already present"
fi

# CJK fonts for texlive (formulas can contain CJK).
sudo apt-get install -y -qq fonts-noto-cjk fonts-noto-cjk-extra 2>/dev/null || true

# Enable PDF write in IM7 policy.xml (default denies PDF).
POLICY="$(magick -configure | awk '/CONFIGURE PATH/{print $2; exit}')policy.xml" 2>/dev/null || true
if [ -n "${POLICY:-}" ] && [ -f "${POLICY}" ] && grep -q 'PDF" write="none"' "${POLICY}"; then
  sudo sed -i 's|PDF" write="none"|PDF" write="allowed"|g' "${POLICY}"
  echo "[cdm] enabled PDF write in ${POLICY}"
fi

echo "[cdm] setup complete"
```
- [ ] **Step 2: Create `engine/omnidocbench_rocm/cdm/smoke_cdm.sh`** (a tiny formula→PDF→PNG probe to detect `#cdm-zero` before a real run):
```bash
#!/usr/bin/env bash
# CDM smoke probe: compile one color-coded formula (LaTeX->PDF), rasterize (IM7),
# and confirm a non-grayscale PNG is produced. Catches #posix / #grayscale /
# #cdm-zero before a full run. Exits 0 = toolchain CDM-capable, 1 = not.
set -euo pipefail
D="$(mktemp -d)"; trap 'rm -rf "$D"' EXIT
cat > "$D/f.tex" <<'TEX'
\documentclass[preview]{standalone}
\usepackage{xcolor}
\begin{document}
{\color{red}$E=mc^2$}
\end{document}
TEX
cd "$D"
pdflatex -interaction=nonstopmode f.tex >/dev/null 2>&1 || { echo "[cdm-smoke] pdflatex failed (#posix?)"; exit 1; }
magick -density 150 f.pdf f.png 2>/dev/null || { echo "[cdm-smoke] magick rasterize failed"; exit 1; }
# Assert the PNG is not grayscale (red channel present):
python3 -c "import sys; from PIL import Image; im=Image.open('$D/f.png').convert('RGB'); r,g,b=im.getpixel((5,5)); sys.exit(0 if r!=g or r!=b else 1)" \
  || { echo "[cdm-smoke] raster is grayscale (#grayscale — IM6/IM7 policy?)"; exit 1; }
echo "[cdm-smoke] OK: toolchain is CDM-capable"
```
  (Note: `smoke_cdm.sh` needs `pdflatex`, `magick`, `python3 PIL`. It is a *probe*; on a box without the toolchain it reports the failure mode rather than passing silently. `Pillow` is added to the eval-venv in Commit 4.)
- [ ] **Step 3: Create `engine/omnidocbench_rocm/cdm_runner.py`:**
```python
"""Host CDM provisioning runner (Linux). Invoked by LinuxRocmBackend.provision_cdm."""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

CDM_DIR = Path(__file__).resolve().parent / "cdm"


def provision_cdm_linux() -> None:
    setup = CDM_DIR / "setup-linux.sh"
    smoke = CDM_DIR / "smoke_cdm.sh"
    print("[cdm] provisioning host CDM toolchain (setup-linux.sh)...")
    subprocess.run(["bash", str(setup)], check=True)
    print("[cdm] running smoke probe (smoke_cdm.sh)...")
    rc = subprocess.run(["bash", str(smoke)]).returncode
    if rc != 0:
        print("[cdm] WARNING: smoke probe failed — CDM scoring will likely yield "
              "all-exception (pending/null). Fix the reported failure mode before "
              "a real --cdm run. See docs/pitfalls.md (#cdm-zero).", file=sys.stderr)
```
- [ ] **Step 4: Make scripts executable + include in the wheel.** `chmod +x` both `.sh` files. Add to `pyproject.toml`:
```toml
[tool.hatch.build.targets.wheel.force-include]
"contracts/artifact-schema.json" = "omnidocbench_rocm/data/artifact-schema.json"
"engine/omnidocbench_rocm/data/omnidocbench_v16.yaml.tmpl" = "omnidocbench_rocm/data/omnidocbench_v16.yaml.tmpl"
"engine/omnidocbench_rocm/cdm" = "omnidocbench_rocm/cdm"
```

### Task 2.2: Static test for the CDM toolchain + commit

**Files:**
- Test: `tests/test_cdm_toolchain.py`

- [ ] **Step 1: Create `tests/test_cdm_toolchain.py`** (static — the scripts' execution is a gated box step; this asserts they exist, are executable, and contain the idempotency/pitfall guards):
```python
import os
from pathlib import Path

CDM = Path(__file__).resolve().parent.parent / "engine" / "omnidocbench_rocm" / "cdm"


def test_setup_script_exists_and_executable():
    p = CDM / "setup-linux.sh"
    assert p.exists()
    assert os.access(p, os.X_OK)
    text = p.read_text()
    assert "texlive-full" in text
    assert "ImageMagick 7" in text or "IM7" in text or "magick" in text
    assert "already present" in text  # idempotency marker


def test_smoke_probe_exists_and_executable():
    p = CDM / "smoke_cdm.sh"
    assert p.exists()
    assert os.access(p, os.X_OK)
    assert "grayscale" in p.read_text()  # #grayscale guard


def test_runner_imports():
    from omnidocbench_rocm.cdm_runner import provision_cdm_linux
    assert callable(provision_cdm_linux)
```
- [ ] **Step 2: Run — expect PASS:**
```bash
python -m pytest tests/test_cdm_toolchain.py -q
```
- [ ] **Step 3: Full suite + commit.**
```bash
python -m pytest -q
git add -A
git commit -m "feat(cdm): host CDM toolchain + smoke probe

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Commit 3 — `feat(verified): Dockerfile.repro + VERIFIED.yaml tolerance check`

### Task 3.1 (TDD): `check_verified.py` tolerance check

**Files:**
- Create: `scripts/check_verified.py`
- Test: `tests/test_check_verified.py`

**Interfaces:**
- Produces: `check_verified(verified: dict, tolerance: float = 0.5) -> tuple[bool, str]` — `(ok, message)`. Reads `reproduced_overall`, `committed_overall`, computes `delta`, asserts `|delta| <= tolerance`. CLI `python scripts/check_verified.py <VERIFIED.yaml>` exits 0/1.

- [ ] **Step 1: Create the failing test `tests/test_check_verified.py`:**
```python
from scripts.check_verified import check_verified

BASE = {"reproduced_overall": 95.0, "committed_overall": 95.2, "tolerance": 0.5}


def test_within_tolerance_passes():
    ok, msg = check_verified({**BASE, "delta": 0.2})
    assert ok and "within" in msg


def test_outside_tolerance_fails():
    ok, msg = check_verified({**BASE, "reproduced_overall": 94.0})
    assert not ok and "tolerance" in msg.lower()


def test_missing_overall_fails():
    ok, msg = check_verified({"reproduced_overall": 95.0})
    assert not ok
```
- [ ] **Step 2: Run — expect FAIL** (`ModuleNotFoundError: scripts.check_verified`):
```bash
python -m pytest tests/test_check_verified.py -q
```
- [ ] **Step 3: Create `scripts/check_verified.py`:**
```python
#!/usr/bin/env python3
"""Tolerance check for a VERIFIED.yaml (the `verified` badge gate).

Asserts |reproduced_overall - committed_overall| <= tolerance (default 0.5).
Exit 0 = passes, 1 = fails. Part of the verified-reproduction path.
"""
from __future__ import annotations
import sys
from pathlib import Path
import yaml


def check_verified(verified: dict, tolerance: float | None = None) -> tuple[bool, str]:
    rep = verified.get("reproduced_overall")
    com = verified.get("committed_overall")
    if rep is None or com is None:
        return False, "missing reproduced_overall or committed_overall"
    tol = tolerance if tolerance is not None else float(verified.get("tolerance", 0.5))
    delta = abs(float(rep) - float(com))
    if delta <= tol:
        return True, f"within tolerance: |{rep} - {com}| = {delta:.3f} <= {tol}"
    return False, f"OUT of tolerance: |{rep} - {com}| = {delta:.3f} > {tol}"


def main(argv: list[str]) -> int:
    path = Path(argv[0]) if argv else Path("VERIFIED.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    ok, msg = check_verified(data)
    print(f"VERIFIED {'PASS' if ok else 'FAIL'}: {msg}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```
- [ ] **Step 4: Run — expect PASS:**
```bash
python -m pytest tests/test_check_verified.py -q
```

### Task 3.2: `Dockerfile.repro` (self-contained reproducible scoring image)

**Files:**
- Create: `engine/omnidocbench_rocm/docker/Dockerfile.repro`
- Create: `engine/omnidocbench_rocm/docker/README.md`

- [ ] **Step 1: Create `engine/omnidocbench_rocm/docker/Dockerfile.repro`** (pins the exact toolchain so a `verified` scoring reproduction is deterministic; runs `score` from committed predictions — **scoring repro, not inference**):
```dockerfile
# Reproducible OmniDocBench-ROCm scoring image (Linux-ROCm verified path).
# Pins the CDM-sensitive toolchain: texlive-full + ImageMagick 7 + ghostscript.
# Reproduces SCORING (Edit_dist + TEDS + CDM) from committed predictions —
# NOT inference. Build on a Docker-capable box (Docker is absent in the dev env).
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
      texlive-full ghostscript nodejs fonts-noto-cjk fonts-noto-cjk-extra \
      git python3.11 python3.11-venv python3-pip curl ca-certificates \
      build-essential pkg-config libjpeg-dev libpng-dev libtiff-dev zlib1g-dev \
      libxml2 libxml2-utils \
 && rm -rf /var/lib/apt/lists/*

# ImageMagick 7 (NOT IM6 — IM6 flattens color formulas to grayscale).
ARG IM_VERSION=7.1.1-38
RUN curl -fsSL "https://imagemagick.org/archive/releases/ImageMagick-${IM_VERSION}.tar.xz" -o /tmp/im7.tar.xz \
 && tar -xf /tmp/im7.tar.xz -C /tmp && cd /tmp/ImageMagick-${IM_VERSION} \
 && ./configure --disable-docs && make -j"$(nproc)" && make install && ldconfig \
 && rm -rf /tmp/im7.tar.xz /tmp/ImageMagick-${IM_VERSION}
# Enable PDF write in IM7 policy.
RUN pol="$(magick -configure 2>/dev/null | awk '/CONFIGURE PATH/{print $2; exit}')policy.xml" || true \
 && [ -n "$pol" ] && [ -f "$pol" ] && sed -i 's|PDF" write="none"|PDF" write="allowed"|g' "$pol" || true

# OmniDocBench scorer pinned to the engine's v1.6 ref; the engine itself.
ARG OMNIDOCBENCH_REF
ARG ENGINE_WHEEL=dist/omnidocbench_rocm-0.2.0-py3-none-any.whl
WORKDIR /opt
RUN python3.11 -m venv /opt/eval-venv \
 && /opt/eval-venv/bin/pip install -U pip
RUN if [ -n "$OMNIDOCBENCH_REF" ]; then \
      git clone https://github.com/opendatalab/OmniDocBench.git /opt/OmniDocBench \
      && cd /opt/OmniDocBench && git checkout "$OMNIDOCBENCH_REF" \
      && /opt/eval-venv/bin/pip install -e . ; fi
COPY ${ENGINE_WHEEL} /tmp/engine.whl
RUN /opt/eval-venv/bin/pip install /tmp/engine.whl Pillow

# Entrypoint: score a mounted predictions dir with a rendered config.
# docker run -v <preds>:/preds -v <OmniDocBench.json>:/gt/OmniDocBench.json \
#   <image> /opt/eval-venv/bin/omnidocbench-rocm score --platform linux-rocm \
#   --predictions-dir /preds --version v16 --run-stats /preds/_run_stats.json --dataset-dir /gt
ENTRYPOINT ["/opt/eval-venv/bin/omnidocbench-rocm"]
```
- [ ] **Step 2: Create `engine/omnidocbench_rocm/docker/README.md`:**
```markdown
# Reproducible scoring image (verified path)

`Dockerfile.repro` pins the CDM-sensitive toolchain (texlive-full + ImageMagick 7
+ ghostscript + node + CJK fonts) so a `verified` scoring reproduction is
deterministic. It reproduces **scoring** (Edit_dist + TEDS + CDM) from committed
predictions — not inference (inference is deterministic given the committed
model+weights; the toolchain versions are the reproducibility risk).

Build (on a Docker-capable box — Docker is absent in the dev env):

    python -m build
    docker build -t omnidocbench-rocm-repro:0.2.0 \
      --build-arg OMNIDOCBENCH_REF=<OMNIDOCBENCH_V16_REF> \
      -f engine/omnidocbench_rocm/docker/Dockerfile.repro .

Run (mount predictions + ground truth):

    docker run --rm \
      -v "$PREDICTIONS":/preds \
      -v "$GT/OmniDocBench.json":/gt/OmniDocBench.json \
      omnidocbench-rocm-repro:0.2.0 \
      score --platform linux-rocm --predictions-dir /preds --version v16 \
            --run-stats /preds/_run_stats.json --dataset-dir /gt

Then verify and record:

    python scripts/check_verified.py VERIFIED.yaml   # |delta| <= 0.5
```

### Task 3.3: badge-policy cross-link + Makefile `repro-score` + commit

**Files:**
- Modify: `contracts/badge-policy.md` (cross-link the tolerance check + `Dockerfile.repro`)
- Modify: `Makefile` (root — add `repro-score` target that documents the docker run)

- [ ] **Step 1: In `contracts/badge-policy.md`**, in the `verified` row / `VERIFIED.yaml` section, add: "Tolerance is machine-checked by `scripts/check_verified.py` (`|reproduced − committed| ≤ 0.5`). The reproduction runs in `engine/omnidocbench_rocm/docker/Dockerfile.repro` (pinned toolchain; reproduces **scoring** from committed predictions)."
- [ ] **Step 2: Create a root `Makefile`** (the platform repo has none) with the `repro-score` target documenting the docker invocation from the docker README (a documented target — actual execution needs Docker). Also add `setup-linux` and `provision-cdm` targets (used by Commits 2/4).
```makefile
.PHONY: setup-linux provision-cdm repro-score test

setup-linux:
	bash engine/omnidocbench_rocm/evalenv/setup-linux.sh

provision-cdm:
	omnidocbench-rocm cdm setup --platform linux-rocm

repro-score:
	@echo "Build the image (Docker-capable box), then:"
	@echo "  docker run --rm -v $$PREDICTIONS:/preds -v $$GT/OmniDocBench.json:/gt/OmniDocBench.json \\"
	@echo "    omnidocbench-rocm-repro:0.2.0 score --platform linux-rocm --predictions-dir /preds --version v16 --run-stats /preds/_run_stats.json --dataset-dir /gt"
	@echo "Then: python scripts/check_verified.py VERIFIED.yaml"

test:
	python -m pytest -q
```
- [ ] **Step 3: Verify + commit.**
```bash
python -m pytest -q
python scripts/check_brand.py
git add -A
git commit -m "feat(verified): Dockerfile.repro + VERIFIED.yaml tolerance check

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Commit 4 — `feat(eval-venv): 3.11 provisioning + setup target`

### Task 4.1: `setup-linux.sh` for the 3.11 eval-venv + Makefile wire

**Files:**
- Create: `engine/omnidocbench_rocm/evalenv/setup-linux.sh`
- Modify: `Makefile` (the `setup-linux` target already added in Commit 3 points here)

- [ ] **Step 1: Create `engine/omnidocbench_rocm/evalenv/setup-linux.sh`:**
```bash
#!/usr/bin/env bash
# Provision the Python 3.11 eval-venv at $OMNIDOCBENCH_ROCM_DATA/eval-venv/linux-rocm.
# OmniDocBench scoring breaks on 3.12 (inspect.getargspec/distutils/imp); 3.11 is required.
set -euo pipefail
DATA_ROOT="${OMNIDOCBENCH_ROCM_DATA:-/root/ocr-eval/omnidocbench-rocm-data}"
VENV="$DATA_ROOT/eval-venv/linux-rocm"
ODB="${OMNIDOCBENCH_CHECKOUT:-/workspace/OmniDocBench}"

if [ -x "$VENV/bin/python" ]; then
  echo "[eval-venv] already present at $VENV ($($VENV/bin/python --version))"
else
  echo "[eval-venv] creating 3.11 venv at $VENV"
  /usr/bin/python3.11 -m venv "$VENV"
fi
ver="$($VENV/bin/python --version 2>&1)"
case "$ver" in *3.11*) echo "[eval-venv] python: $ver";; *) echo "[eval-venv] FATAL: need 3.11, got $ver" >&2; exit 1;; esac

$VENV/bin/pip install -U pip -q
# OmniDocBench scorer (pinned checkout) + CDM smoke needs (Pillow).
if [ -f "$ODB/setup.py" ] || [ -f "$ODB/pyproject.toml" ]; then
  $VENV/bin/pip install -e "$ODB" -q
fi
$VENV/bin/pip install Pillow -q
echo "[eval-venv] ready: $VENV"
```
- [ ] **Step 2: Make executable + include in wheel.** `chmod +x engine/omnidocbench_rocm/evalenv/setup-linux.sh`. Add to `pyproject.toml` force-include:
```toml
"engine/omnidocbench_rocm/evalenv" = "omnidocbench_rocm/evalenv"
```
- [ ] **Step 3: Verify the venv python is 3.11 (gated provisioning — run on the box):**
```bash
bash engine/omnidocbench_rocm/evalenv/setup-linux.sh
/root/ocr-eval/omnidocbench-rocm-data/eval-venv/linux-rocm/bin/python --version
```
Expected: `Python 3.11.x`.
- [ ] **Step 4: Commit.**
```bash
git add -A
git commit -m "feat(eval-venv): 3.11 provisioning + setup target

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Commit 5 — `docs: onboarding runbook (success = verified flagship)`

### Task 5.1: `docs/onboarding-runbook.md` + architecture/pitfalls CDM updates

**Files:**
- Create: `docs/onboarding-runbook.md`
- Modify: `docs/architecture.md` (CDM ownership section — now real)
- Modify: `docs/pitfalls.md` (point at the new toolchain)

- [ ] **Step 1: Create `docs/onboarding-runbook.md`** — the 7-step procedure from spec AD5 (pin revision → 3.11 venv → full 1651-page adapter run [gated GPU] → score Edit_dist+TEDS → provision CDM + score CDM → publish [full-set enforcement] → conformance → registry `community` → **maintainer Docker repro + `VERIFIED.yaml` + `check_verified.py` → registry `verified`**). State explicitly: **success = a verified flagship entry**; `community` is the step-6 checkpoint; the 1651-page run + Docker repro are resumable gated execution steps. PaddleOCR-VL is the worked example (its adapter + serving land in the follow-on spec).
- [ ] **Step 2: Update `docs/architecture.md`** "CDM ownership" section — replace the "partial scaffold / not yet implemented" language with: CDM is now end-to-end-usable via `engine/omnidocbench_rocm/cdm/setup-linux.sh` + `smoke_cdm.sh` (host fast path) and `engine/omnidocbench_rocm/docker/Dockerfile.repro` (verified repro path). Keep the `#cdm-zero` pointer to pitfalls.
- [ ] **Step 3: Update `docs/pitfalls.md`** status note — the Windows-native CDM paths are still planned, but Linux/ROCm CDM is now provisioned by `cdm/setup-linux.sh`; cross-link it.
- [ ] **Step 4: Verify + commit.**
```bash
python -m pytest -q
python scripts/check_brand.py
git add -A
git commit -m "docs: onboarding runbook (success = verified flagship)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Gated execution (after the 5 commits land + merge)

These are **not** plan tasks — they are resumable execution steps the plan makes ready:

- [ ] **G1 — Provision the box:** `make setup-linux` (3.11 venv) + `make provision-cdm` (host CDM toolchain) + run `smoke_cdm.sh` until "CDM-capable".
- [ ] **G2 — PaddleOCR-VL adapter + serving** (follow-on spec in `PaddleOCR-VL-ROCm`): port the adapter to the contract, serve the VLM (vLLM/ROCm).
- [ ] **G3 — Full 1651-page run:** `omnidocbench-rocm run --stage all --platform linux-rocm --revision <pinned> --cdm ...` (resumable background job). Score Edit_dist+TEDS, then CDM.
- [ ] **G4 — Publish + community:** `publish` (full-set enforcement) → `conformance` → update `hub/registry.yaml` → `community`.
- [ ] **G5 — Verified (Docker box):** build `Dockerfile.repro`, run `repro-score` from committed predictions, write `VERIFIED.yaml`, `python scripts/check_verified.py VERIFIED.yaml` → registry `verified`. **This is the runbook's success definition.**

## Self-review

- **Spec coverage:** AD1 (score rendering + pin + CDM) → Commit 1; AD2 (CDM toolchain + smoke) → Commit 2; AD3 (Dockerfile + tolerance) → Commit 3; AD4 (3.11 venv) → Commit 4; AD5 (runbook) → Commit 5; §6 flagship → G1–G5 gated execution. §9 honest gating (Docker absent, gfx1100 present) → Global Constraints + G5. No spec section uncovered.
- **Placeholder scan:** `OMNIDOCBENCH_V16_REF` is resolved by Task 1.1 Step 1 (a command that prints the ref), not left as TBD. All code blocks complete. No "implement later".
- **Type consistency:** `render_config(template_path, *, prediction_path, gt_path, cdm, workers=13) -> Path`; `score(*, predictions_dir, version, cdm, run_stats_path, scoring_config=None, dataset_dir=None) -> Path`; `check_verified(verified, tolerance=None) -> tuple[bool, str]`; `provision_cdm_linux()`. Used consistently across tasks.
