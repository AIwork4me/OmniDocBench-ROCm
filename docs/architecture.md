# Architecture

How the AMD Doc Parsing zone fits together. Read this alongside
[`contracts/adapter.md`](../contracts/adapter.md) (the contract every adapter
implements) and [`docs/contribute-a-model.md`](contribute-a-model.md) (how to
add a model).

This document supersedes and absorbs the architecture notes from the
`omnidocbench-amd-windows` repo (the Windows-side eval harness that became the
`windows-hip` backend). The Windows/WSL boundary and CDM toolchain notes
live on in [`pitfalls.md`](pitfalls.md); this page covers the platform-repo
topology and the shared engine.

---

## The topology (Topology A)

A single **platform repo** (`omnidocbench-amd/`) holds the shared contracts,
the dual-platform eval engine, the per-model repo template, and the hub
registry. Each model lives in its **own** repo (`<Model>-AMD/`), generated
from the template. The engine never imports an adapter — it consumes the
adapter's filesystem output — so model repos can be in any stack.

```
omnidocbench-amd/                         <- this repo (platform)
  contracts/        adapter contract, artifact schema, conformance, badges
  engine/           omnidocbench_amd/  (pip package: stages, backends, cdm)
  template/         cookiecutter -> <Model>-AMD/
  hub/              registry.yaml (source of truth for the comparison table)
  docs/             contribute-a-model, architecture, pitfalls, ci-reality
  scripts/          check_conformance.py, generate_registry.py

<Model>-AMD/        (one per model, from the template)
  adapter/          run_adapter.py + adapter_config.py + setup/
  eval/configs/     omnidocbench_v16.yaml
  results/          omnidocbench/v16/<platform>/  (the artifact bundle)
  examples/         demo.png + run_demo.{sh,ps1}
  model_card.json   the hub registry entry
  Makefile          make demo / eval-linux / eval-windows / publish / setup-*
```

### The data flow (per platform)

```
OmniDocBench v1.6 (1651 pages) ──► adapter/run_adapter.py ──► predictions/<model>/*.md
                                                                │  + _run_stats.json
                                engine (linux-rocm | windows-hip)
                                ▼
              metric_result.json + run_summary.json + provenance.json + model_card.json
                                │  scripts/check_conformance.py
                                ▼
                hub/registry.yaml ──► badge (verified/community) + comparison table
```

The adapter is **filesystem-decoupled**: the engine invokes it as a subprocess
and reads only `out_dir/<image_stem>.md` + `out_dir/_run_stats.json`. This is
the contract that makes scores comparable across models and across platforms —
the engine doesn't care what language the adapter is written in or what
inference backend it calls.

---

## The engine: four stages

`engine/omnidocbench_amd/stages.py` orchestrates four gated stages, ported
from `AIwork4me/PaddleOCR-VL-ROCm/eval/run_eval.py`:

```
download ──► infer ──► score ──► publish
 (HF/MS)   (adapter     (OmniDocBench   (assemble model_card +
            subprocess)  pdf_validation  conformance + badge)
            in eval-venv)
```

| Stage | What it does | Gate |
|---|---|---|
| `download` | Fetch the v1.6 manifest + 1651 page images to `data/omnidocbench/v16/`. **Revision is pinned** (the old `latest` default is now an enforced pin for reproducibility). | revision != None |
| `infer` | Ping the inference server first (clear exit if unreachable). Invoke the adapter as a subprocess. Per-page failures are caught → zero, run continues. | server reachable; adapter exits 0; `_run_stats.json` written |
| `score` | Run `pdf_validation.py` inside the **eval-venv** (Python 3.11). `config → save_name → result` mapping is deterministic; the `_cdm` suffix on a CDM predictions dir prevents clobbering the Edit_dist-only run. | checkout present; eval-venv Python correct; CDM ready if `--cdm` |
| `publish` | Assemble `run_summary.json` + `provenance.json` + `model_card.json`; run `check_conformance.py`; emit a badge suggestion. **Refuses to publish official evidence from `limit_pages != null` subsets** (full-set enforcement). | `_run_stats.json` says full set; artifacts schema-valid |

Each stage validates its prerequisites and exits with a clear message rather
than crashing. The `omnidocbench-amd` CLI (`engine/omnidocbench_amd/cli.py`)
exposes `cdm`, `dataset`, `infer`, `score`, `publish`, `run`, and
`conformance` subcommands.

---

## The two backends

The engine dispatches platform-specific work to a backend
(`engine/omnidocbench_amd/backends/`):

| Concern | `linux-rocm` | `windows-hip` |
|---|---|---|
| CDM toolchain | native apt: texlive-full + IM7 + gs + node | absorbed from `omnidocbench-amd-windows`: `windows-cdm.patch` + native TeX Live, or WSL fallback |
| OmniDocBench checkout | native git clone (pin commit) | native or WSL |
| Scoring script | `score.sh` | `score.ps1` / `score-cdm.sh` |
| eval-venv | Python 3.11 (apt/uv) | Python 3.11 (winget/uv) |

Both backends share the same `stages.py` / `artifact_utils.py` core; they
differ only in platform-specific subprocess invocation. The `windows-hip`
backend is lazy-imported so the engine works on a Linux-only box without the
Windows backend installed.

### The Windows / WSL boundary (absorbed)

CDM on Windows has two supported toolchain paths (carried over from
`omnidocbench-amd-windows`):

- **Windows-native CDM** — the local fast path, after `windows-cdm.patch` is
  applied and `verify-windows.ps1` passes.
- **WSL CDM** — the compatibility/reference path, with an isolated Linux TeX
  Live 2026 + ImageMagick 7 + Ghostscript stack inside WSL Ubuntu 22.04.

Why two paths? Because CDM's POSIX shell assumptions (`kpsewhich`, `magick`,
`gs`, `shlex` quoting) break on native Windows, and ImageMagick 6 silently
flattens color formulas to grayscale. The full decision tree is in
[`pitfalls.md`](pitfalls.md) (`#posix`, `#grayscale`, `#cdm-zero`).

```
WINDOWS (PowerShell, Python 3.11)              │     WSL Ubuntu 22.04
                                                │
 adapters/<model>/setup/*.ps1                  │     engine/cdm/setup.sh (9 steps):
  -> predictions/<model>/                      │       TL2026 + IM7 + gs + CJK fonts
                                                │
 03-scoring/score.ps1:                          │     03-scoring/score-cdm.sh:
   Edit_dist + TEDS, or + CDM after             │       Edit_dist + TEDS + CDM
   verify-windows.ps1 ◄─────────────────────────┼──── (clean Linux PATH, no /mnt/c)
                                                │
 verify.ps1 reads metric_result.json ◄─────────┘     (win path or \\wsl$\ share)
```

The WSL path crosses the boundary exactly twice per CDM run: **down** —
`score-cdm.sh` launched from PowerShell with a clean Linux `PATH`; **up** —
`verify.ps1` reads the result JSON via the `\\wsl$\` share. LaTeX compilation,
PDF rasterization, and CDM matching stay entirely on the Linux side.

---

## The Python version split (critical)

OmniDocBench's scoring code breaks on Python 3.12 (uses `inspect.getargspec`,
`distutils`, `imp` — all removed in 3.12). It works on 3.10 and 3.11. But
modern model inference (vLLM, recent transformers) often wants 3.12. The zone
resolves this with **two venvs**:

```
                    stages.py (thin shim, dispatches subprocesses)
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
   model venv (3.12)              eval-venv (3.11)
   infer stage runs here          score stage runs here
   (adapter + its deps)           (OmniDocBench pdf_validation)
```

- `infer` runs in the model's inference venv (may be 3.12).
- `score` runs in the eval-venv (3.11), provisioned by the engine.
- `stages.py` is a thin shim that dispatches subprocesses to the correct venv.

This is what resolved the Unlimited-OCR-ROCm (3.12) vs OmniDocBench (3.11)
conflict. Contributors don't manage this split — `make setup-*` provisions the
eval-venv; the model's deps go in its own venv.

---

## CDM ownership (the highest-value part)

CDM (Consistent Distance Metric) matches formulas by: compile each formula to
a color-coded PDF → rasterize to PNG → match colored bounding boxes between
ground truth and prediction. It is the hardest, highest-value metric — and
the single biggest source of debugging hours (see `pitfalls.md#cdm-zero`).

**The engine exclusively owns CDM provisioning**, so contributors don't each
fight the 20+ debug sessions:

- `engine/omnidocbench_amd/cdm/setup-linux.sh` — idempotent apt install
  (texlive-full + IM7 + gs + node).
- `engine/omnidocbench_amd/cdm/setup.ps1` / `setup.sh` — Windows, absorbed
  from `omnidocbench-amd-windows/eval-infra/02-cdm-environment`.

### Docker reproducible path

For maximum reproducibility (and as the recommended path for `verified`
badges), `score` can opt-in to run inside:

```
ghcr.io/zeng-weijun/omnidocbench-eval:repro-ubuntu2204
```

This pins the exact TeX Live / IM7 / gs versions. It runs via Docker Desktop
on Windows and native Docker on Linux. **Maintainer reproductions for the
`verified` badge use the Docker path.**

### CDM is opt-in

CDM is opt-in via `score --cdm`. Contributors can run Edit_dist + TEDS only
(no `--cdm`) for a first pass, then provision CDM and re-run with `--cdm`.
Invalid CDM (all-exception) is shown as `pending`/null — never a faked number
— and `publish` refuses to publish invalid CDM as a real score.

---

## Config → save_name → result mapping

The scoring layer renders a config **template** into a concrete config, then
runs `pdf_validation.py`. The result file naming is deterministic:

```
save_name = basename(prediction_path) + "_" + match_method
```

The `_cdm` suffix on a CDM predictions dir is deliberate — it gives the CDM
run a different `save_name` so it doesn't clobber the Edit_dist-only run's
results. `results/omnidocbench/v16/<platform>/` ends up with:

```
<save_name>_metric_result.json      # raw OmniDocBench output
<save_name>_run_summary.json        # readme_metrics + metric_quality
<save_name>_provenance.json         # git_commit, platform, engine_version, ...
_run_stats.json                     # adapter-produced, engine-consumed
```

---

## Idempotency everywhere

Every `setup.*` script self-checks before doing work (`Test-Path`, `dpkg -s`,
`kpsewhich`, `[ -x ... ]`, `[ -d ... ]`). Re-running after success is fast and
prints `already installed` / `already present` per step. This is what makes
the repo safe to point an agent at: re-running the whole pipeline is a no-op
once provisioned, and resumes cleanly after a partial/interrupted run.

---

## Where to look next

- Adding a model → [`contribute-a-model.md`](contribute-a-model.md)
- The contract you implement → [`contracts/adapter.md`](../contracts/adapter.md)
- Why CDM is hard → [`pitfalls.md`](pitfalls.md) (the `#cdm-zero` decision tree)
- What CI does and doesn't cover → [`ci-reality.md`](ci-reality.md)
- Badge tiers → [`contracts/badge-policy.md`](../contracts/badge-policy.md)
- Conformance checklist → [`contracts/conformance.md`](../contracts/conformance.md)
