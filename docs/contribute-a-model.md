# Contribute a Model

How to add an open-source document-parsing model to the **OmniDocBench-ROCm**
zone and get it scored on OmniDocBench v1.6 on AMD hardware. This guide is the
9-step path from proposal to a verified badge. The contract you implement is
[`contracts/adapter.md`](../contracts/adapter.md); the checklist that gates
your repo is [`contracts/conformance.md`](../contracts/conformance.md).

> 中文版（针对国内网络优化，镜像/ModelScope 优先）：[`contribute-a-model.zh-CN.md`](contribute-a-model.zh-CN.md).

---

## Prerequisites

Before you start, confirm you have the hardware, OS, and environment. The zone
targets two platform categories; you can contribute to **one or both**.

### AMD GPUs that work

| Platform | GPU | Notes |
|---|---|---|
| `linux-rocm` (Radeon dGPU + Linux/ROCm) | gfx1100 (Radeon PRO W7900 48GB, RX 7900 XT/XTX) | ROCm 6.x. The reference 92.431 (Unlimited-OCR) was produced on gfx1100. |
| `windows-hip` (Ryzen AI MAX+ 395 + Windows/HIP) | Strix Halo Radeon 8060S iGPU; RX 7900 XT+ dGPU | Windows 11, HIP SDK / DirectML. Real Windows-native CDM results exist (2026-07-11). |

Other AMD GPUs may work but are not actively tested. If you have a different
gfx architecture (e.g. gfx1030, gfx1151), open an issue first — we'll help you
check ROCm/HIP compatibility.

### OS, disk, network

- **OS:** Linux (Ubuntu 22.04+ recommended) for `linux-rocm`; Windows 11 for
  `windows-hip`. Both can run via WSL2 where helpful.
- **Disk:** ~50 GB free. OmniDocBench v1.6 dataset (~5 GB), model weights
  (varies, 5–40 GB), CDM toolchain (TeX Live 2026 + IM7 + Node, ~8 GB), and
  eval venvs.
- **Network:** GitHub, HuggingFace, CTAN, and PyPI must be reachable. Behind
  the China firewall? Use the [CN guide](contribute-a-model.zh-CN.md) —
  mirrors and ModelScope come first there.

### Python versions (the split that matters)

OmniDocBench's scoring code breaks on Python 3.12 (uses `inspect.getargspec`,
`distutils`, `imp`). The zone works around this with **two venvs**:

| Venv | Python | What runs in it |
|---|---|---|
| **eval-venv** | 3.11 (or 3.10) | OmniDocBench `pdf_validation.py` — the `score` stage. Engine provisions this. |
| **model venv** | 3.12 (or whatever the model needs) | The adapter's inference. The `infer` stage. |

The engine is a thin shim that dispatches subprocesses to the correct venv.
You don't manage this split yourself — `make setup-linux` / `make setup-windows`
provisions the eval-venv; you install your model's deps in its own venv.

---

## The 9-step flow

```
1 Propose → 2 Scaffold → 3 Provision → 4 Implement → 5 Demo → 6 Eval → 7 Publish → 8 Submit → 9 Verified
```

Each step has a rough time budget assuming the hardware + weights are ready.

### Step 1 — Propose (minutes)

Open an issue in `AIwork4me/OmniDocBench-ROCm` titled "I want to add model X".
The maintainer confirms:

- It's **open-source** (open weights + open code). Closed-source models
  (Gemini, GPT, Mistral-OCR, mathpix, HunYuan-OCR, Youtu-Parsing, Nanonets,
  GLM-OCR, …) are never supported.
- It's **in scope** — a document-parsing model (not a general VLM unless it
  has a doc-parsing path).
- It's **not a duplicate** of an existing or in-progress model.

**Time:** a round-trip on the issue. **Exit:** maintainer says "go ahead".

### Step 2 — Scaffold (10 min)

Generate a conformant repo from the cookiecutter template:

```bash
pip install cookiecutter
cookiecutter gh:AIwork4me/OmniDocBench-ROCm --directory template
# prompts: repo_name (Model-ROCm), model_slug, model_id, model_version, license
```

This gives you the full structure: `adapter/run_adapter.py` (with a `smoke`
backend that needs no GPU), `adapter/adapter_config.py`, `Makefile`, bilingual
READMEs, `eval/configs/omnidocbench_v16.yaml`, `examples/`, CI workflow, and
the `results/omnidocbench/v16/{linux-rocm,windows-hip}/` dirs.

Push it to your fork (e.g. `AIwork4me/<Model>-AMD`).

**Time:** 10 min. **Exit:** a repo that already passes
`make smoke-test` and `make demo` (with the smoke backend).

### Step 3 — Provision (30 min – 2 h, one-time)

Provision the engine + your model's weights + (optionally) CDM:

```bash
# engine + eval-venv (Python 3.11) + OmniDocBench checkout
make setup-linux        # or: make setup-windows

# your model's weights + serving (edit adapter/setup/.env.local for paths)
bash adapter/setup/00-install-deps.sh        # Linux
powershell -ExecutionPolicy Bypass -File adapter\setup\00-install-deps.ps1   # Windows

# CDM toolchain (optional for a first pass — see Step 6)
omnidocbench-rocm cdm setup --platform linux-rocm
```

Everything is **idempotent** — re-running is a no-op once provisioned, and
resumes cleanly after an interrupt. Weights go to a gitignored `models/` dir;
`.env.local` records the absolute paths.

**Time:** 30 min if mirrors are fast and weights are cached; up to 2 h if
downloading a large model over a slow link or building the CDM toolchain.
**Exit:** `omnidocbench-rocm dataset download --version v16 --revision v1.6`
succeeds; `make demo` runs.

### Step 4 — Implement (hours – a day)

This is the only model-specific code. Edit `adapter/run_adapter.py`:

1. Replace the `_infer(img, platform, config)` body with your model's inference
   (image → Markdown).
2. Set `adapter/adapter_config.py::BACKEND` to your backend
   (`vllm`, `llama-cpp-server`, `onnx-rocm`, `onnx-directml`, …) and fill in
   `SERVER_URL`, `API_MODEL_NAME`, `WEIGHTS_DIR`.
3. If your model uses ONNX (layout/pipeline), pick the execution provider per
   platform: `onnxruntime-rocm` (ROCm EP) on Linux, `onnxruntime-directml`
   (DirectML EP) on Windows. See [`contracts/adapter.md`](../contracts/adapter.md) §R6.
4. Keep the `run_adapter` signature, the `out_dir/<image_stem>.md` convention,
   the per-page `try/except` (never raise), and the `_run_stats.json` write.

**The engine forwards these flags to the adapter** (they populate the `config`
dict, overriding `adapter_config.py` defaults):

- `--backend` — which inference path to take (`vllm`, `llama-cpp-server`, …).
- `--server-url` — the vLLM / OpenAI-compatible server URL.
- `--api-model-name` — the model name as registered on the server.
- `--skip-existing` — skip pages whose `.md` already exists (resumable runs;
  skipped pages are recorded as `ok` and still counted — never reduce the full
  set). The template adapter honors this; if you replace the CLI parsing, keep
  it.

`_run_stats.json["engine"]` is what the adapter reports as having actually run,
and that self-report — not the requested `--backend` — is what lands in
`provenance.backend`. If they disagree, `publish` refuses to run.

**Time:** a few hours for a vLLM-served VLM (mostly wiring); up to a day for a
multi-stage pipeline (layout + formula + OCR) or a custom ONNX path.
**Exit:** `make demo` produces sane Markdown from `examples/demo.png`.

### Step 5 — Demo (5 min)

```bash
make demo
# runs: omnidocbench-rocm infer --adapter adapter/run_adapter.py --img-dir examples --out-dir <tmp>
```

Verify the one-page output looks like a real document parse (headings, text,
formulas as `$...$`, tables). If it's garbage, fix `_infer` before burning a
full eval.

**Time:** 5 min. **Exit:** a `.md` you'd show someone.

### Step 6 — Eval (20 min – 2 h per platform)

Run the full OmniDocBench v1.6 eval (1651 pages):

```bash
make eval-linux          # or: make eval-windows
# = omnidocbench-rocm run --stage all --platform linux-rocm --version v16 --revision v1.6
```

For a server-served model, forward the backend/server flags (the Makefile
exposes `BACKEND`, `SERVER_URL`, `API_MODEL_NAME` for this):

```bash
make eval-linux BACKEND=vlm-vllm \
                 SERVER_URL=http://127.0.0.1:8000/v1 \
                 API_MODEL_NAME=<model-name>
```

`run --stage all` threads one inference config into both `infer` and
`publish`, so the published `prediction_dir`, `adapter_command`, and
`backend` fields reflect the run that actually produced the scores.

This runs the four stages: `download → infer → score → publish`, producing the
artifact bundle in `results/omnidocbench/v16/<platform>/`:
`metric_result.json`, `run_summary.json`, `provenance.json`, `_run_stats.json`.

**CDM, the high-value metric:** CDM (formula matching via LaTeX→PDF→PNG color
matching) is opt-in via `--cdm`. For a **first pass**, run without `--cdm`
(Edit_dist + TEDS only) to validate the pipeline. Then provision CDM
(`omnidocbench-rocm cdm setup --platform ...`) and re-run with `--cdm`. CDM is
engine-owned and notoriously fiddly — if it fails, see
[`pitfalls.md`](pitfalls.md) (the `#cdm-zero` decision tree covers the six ways
CDM silently scores zero).

**Time:** 20–40 min for inference (VLM, ~1 s/page on gfx1100); scoring adds
10–30 min (CDM adds more, it compiles LaTeX per formula). **Exit:** the
artifact bundle exists and `run_summary.json` has non-zero `readme_metrics`.

### Step 7 — Publish (10 min)

```bash
make publish
# = omnidocbench-rocm conformance .   (runs check_conformance.py)
```

Fix any conformance failures (missing README section, empty results dir,
`pyproject.toml` not depending on `omnidocbench-rocm`, invalid `model_card.json`).
The conformance checklist is in [`contracts/conformance.md`](../contracts/conformance.md).

Then commit the `results/` bundle + `model_card.json`. This is your
**provenance-complete** evidence.

**Time:** 10 min (assuming Step 6 produced valid artifacts). **Exit:**
`check_conformance.py` exits 0 (`CONFORMANT`).

### Step 8 — Submit (minutes)

Open a PR to `AIwork4me/OmniDocBench-ROCm` adding your model to
`hub/registry.yaml` with `badge: community` (or `community-wanted` for the
platform you don't have) and a link to your repo. CI runs
`check-conformance` on your repo.

**Time:** a round-trip. **Exit:** your model appears in the comparison table
with a `community` badge for the platform(s) you shipped.

### Step 9 — Verified (optional, maintainer)

A maintainer reproduces your eval on **both claimed platforms** in a clean
Docker environment (`ghcr.io/zeng-weijun/omnidocbench-eval:repro-ubuntu2204`),
confirming the `overall` score within tolerance, and commits a `VERIFIED.yaml`
to your repo. Your badge moves `community → verified`. See
[`contracts/badge-policy.md`](../contracts/badge-policy.md).

**Time:** maintainer-side; you don't do anything but keep your repo
reproducible. **Exit:** `verified` badge.

---

## "I only have one platform"

That's fine and expected. Badges are **per-platform and independent** — see
[`contracts/badge-policy.md`](../contracts/badge-policy.md).

- Ship `community` for the platform you have (e.g. `linux-rocm`).
- The other platform shows `community-wanted` in the registry — a signal to
  contributors who have that hardware that the model is wanted there.
- You can upgrade the missing side later (yourself or via a contributor PR)
  without touching the side that already works.

You do **not** need both platforms to contribute. Most contributors will start
with one.

---

## Where to ask for help

- **Bugs / failures:** search [`pitfalls.md`](pitfalls.md) by symptom first —
  it's organized by what you'll see, with Root Cause → Fix → Verify for each.
  The CDM entries (`#cdm-zero`, `#grayscale`, `#mathcolor`, …) are the
  highest-value pages in the repo.
- **Architecture / "how does it fit?":** [`architecture.md`](architecture.md).
- **The contract you're implementing:** [`contracts/adapter.md`](../contracts/adapter.md).
- **Questions / proposals:** open an issue in `AIwork4me/OmniDocBench-ROCm`.
  The maintainer responds on issue threads.

A "good first model" list (models that are open-source, well-documented, and
straightforward to wire up) is maintained in the registry — ask in an issue if
you want a recommendation matched to your hardware.

---

## TL;DR

```bash
cookiecutter gh:AIwork4me/OmniDocBench-ROCm --directory template   # 2 Scaffold
make setup-linux                                                   # 3 Provision
$EDITOR adapter/run_adapter.py adapter/adapter_config.py           # 4 Implement
make demo                                                          # 5 Demo
make eval-linux                                                    # 6 Eval
make publish                                                       # 7 Publish
# PR to hub/registry.yaml                                          # 8 Submit
```

The contract is one function. The engine handles the rest.
