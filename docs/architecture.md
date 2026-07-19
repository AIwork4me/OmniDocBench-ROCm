# Architecture

How OmniDocBench-ROCm fits together. Read this alongside
[`contracts/adapter.md`](../contracts/adapter.md) (the contract every adapter
implements) and [`docs/contribute-a-model.md`](contribute-a-model.md) (how to
add a model).

> **Reality note.** Only the **Linux-ROCm** backend is implemented today. The
> **Windows-HIP** backend is planned/onboarding (`get_backend("windows-hip")`
> raises an explicit not-implemented error). CDM on Linux/ROCm is provisioned
> end-to-end on the host by
> [`engine/omnidocbench_rocm/cdm/setup-linux.sh`](../engine/omnidocbench_rocm/cdm/setup-linux.sh)
> + [`smoke_cdm.sh`](../engine/omnidocbench_rocm/cdm/smoke_cdm.sh) (the fast
> `community` path) and is reproducible via
> [`engine/omnidocbench_rocm/docker/Dockerfile.repro`](../engine/omnidocbench_rocm/docker/Dockerfile.repro)
> (the `verified` path). Windows-native CDM remains planned. See the
> "CDM ownership" section below and [`pitfalls.md`](pitfalls.md) for the known
> failure modes.

---

## The topology (Topology A)

A single **platform repo** (`OmniDocBench-ROCm/`) holds the shared contracts,
the eval engine, the per-model repo template, and the hub registry. Each model
lives in its **own** repo (`<Model>-ROCm/`), generated from the template. The
engine never imports an adapter — it consumes the adapter's filesystem output —
so model repos can be in any stack.

```text
OmniDocBench-ROCm/                    <- this repo (platform)
  contracts/      adapter contract, artifact schema, conformance, badges, backend policy
  engine/         omnidocbench_rocm/  (pip package: stages, backends, schema, conformance)
  template/       cookiecutter -> <Model>-ROCm/
  hub/            registry.yaml (source of truth for the comparison table; initial placeholder)
  docs/           contribute-a-model, architecture, pitfalls, ci-reality, governance, roadmap
  scripts/        check_conformance.py, generate_registry.py, validate_registry.py, check_brand.py

<Model>-ROCm/     (one per model, from the template)
  adapter/        run_adapter.py + adapter_config.py + setup/
  eval/configs/   omnidocbench_v16.yaml
  results/        omnidocbench/v16/<platform>/   (the artifact bundle)
  examples/       demo.png + run_demo.{sh,ps1}
  model_card.json the hub registry entry
  Makefile        make demo / eval-linux / eval-windows / publish / setup-*
```

### The data flow

```text
OmniDocBench v1.6 (1651 pages) --> adapter/run_adapter.py --> predictions/<model>/*.md
                                                              |  + _run_stats.json
                                  engine (linux-rocm | windows-hip*)
                                  v
              metric_result.json + run_summary.json + provenance.json + model_card.json
                                  |  scripts/check_conformance.py
                                  v
                hub/registry.yaml --> badge (verified/community) + comparison table
```

\* `windows-hip` is planned/onboarding, not yet implemented.

The adapter is **filesystem-decoupled**: the engine invokes it as a subprocess
and reads only `out_dir/<image_stem>.md` + `out_dir/_run_stats.json`. This is
the contract that makes scores comparable across models and across platforms —
the engine doesn't care what language the adapter is written in or what
inference backend it calls.

---

## The engine: four stages

`engine/omnidocbench_rocm/stages.py` orchestrates four gated stages:

```text
download --> infer --> score --> publish
 (HF)      (adapter    (OmniDocBench  (assemble run_summary + provenance +
            subprocess) pdf_validation conformance + badge)
            in eval-venv)
```

| Stage | What it does | Gate |
|---|---|---|
| `download` | Fetch the v1.6 manifest + page images. **Revision is pinned** (the engine refuses an unpinned `None`). | revision != None |
| `infer` | Invoke the adapter as a subprocess. Per-page failures are caught -> zero, run continues. | adapter exits 0; `_run_stats.json` written |
| `score` | Run `pdf_validation.py` inside the **eval-venv** (Python 3.11). `config -> save_name -> result` mapping is deterministic; the `_cdm` suffix on a CDM predictions dir prevents clobbering the Edit_dist-only run. | checkout present; eval-venv Python correct |
| `publish` | Assemble `run_summary.json` + `provenance.json`; run `check_conformance.py`; emit a badge suggestion. **Refuses to publish official evidence from `limit_pages != null` subsets** (full-set enforcement). | `_run_stats.json` says full set; artifacts schema-valid |

Each stage validates its prerequisites and exits with a clear message rather
than crashing. The `omnidocbench-rocm` CLI (`engine/omnidocbench_rocm/cli.py`)
exposes `cdm`, `dataset`, `infer`, `score`, `publish`, `run`, and
`conformance` subcommands.

---

## The backends (reality)

The engine dispatches platform-specific work to a backend
(`engine/omnidocbench_rocm/backends/`):

| Backend | Status | Notes |
|---|---|---|
| `linux-rocm` (`LinuxRocmBackend`) | **Implemented** | `score()` renders the scoring config and runs `pdf_validation.py` in the eval-venv (Python 3.11). `provision_cdm()` runs [`cdm/setup-linux.sh`](../engine/omnidocbench_rocm/cdm/setup-linux.sh) (host CDM toolchain). The OmniDocBench checkout revision is pinned to `OMNIDOCBENCH_V16_REF` (`2b161d0`). |
| `windows-hip` | **Planned / onboarding** | `get_backend("windows-hip")` raises `NotImplementedError`. No `windows_hip.py` exists. Windows-native CDM is planned (see [`pitfalls.md`](pitfalls.md) status note). See `contracts/backend-policy.md`. |

There is no fabricated Windows CDM toolchain and no `score.ps1`. When the
Windows-HIP backend lands, this section will describe it for real.

---

## The Python version split (critical)

OmniDocBench's scoring code breaks on Python 3.12 (uses `inspect.getargspec`,
`distutils`, `imp` — all removed in 3.12). It works on 3.10 and 3.11. But modern
model inference (vLLM, recent transformers) often wants 3.12. The platform
resolves this with **two venvs**:

```text
                    stages.py (thin shim, dispatches subprocesses)
                          |
            +-------------+-------------+
            v                           v
   model venv (3.12)              eval-venv (3.11)
   infer stage runs here          score stage runs here
   (adapter + its deps)           (OmniDocBench pdf_validation)
```

- `infer` runs in the model's inference venv (may be 3.12).
- `score` runs in the eval-venv (3.11), provisioned by the engine.
- `stages.py` is a thin shim that dispatches subprocesses to the correct venv.

Contributors don't manage this split — `make setup-*` provisions the eval-venv;
the model's deps go in its own venv.

---

## CDM ownership (the highest-value part — provisioned + smoke-checked)

CDM (Consistent Distance Metric) matches formulas by: compile each formula to a
color-coded PDF -> rasterize to PNG -> match colored bounding boxes between
ground truth and prediction. It is the hardest, highest-value metric.

**The engine owns CDM provisioning** (so contributors don't each fight the 20+
debug sessions documented in `pitfalls.md`). On Linux/ROCm, CDM is now
**end-to-end-usable on the host** via two pieces:

- [`engine/omnidocbench_rocm/cdm/setup-linux.sh`](../engine/omnidocbench_rocm/cdm/setup-linux.sh)
  — idempotent host provisioning: `texlive-full` + **ImageMagick 7** (not the
  IM6 default that silently flattens color formulas to grayscale — see
  [`#grayscale`](pitfalls.md#grayscale)) + `ghostscript` + `node` + CJK fonts,
  and enables PDF write in the IM7 policy. `make provision-cdm` runs it.
- [`engine/omnidocbench_rocm/cdm/smoke_cdm.sh`](../engine/omnidocbench_rocm/cdm/smoke_cdm.sh)
  — a smoke probe that compiles one color-coded formula, rasterizes it, and
  asserts the PNG is **not grayscale**. This catches the
  [`#grayscale`](pitfalls.md#grayscale) and [`#posix`](pitfalls.md#posix)
  branches directly and exercises the `pdflatex → magick` path end-to-end; the
  remaining [`#cdm-zero`](pitfalls.md#cdm-zero) branches
  ([`#mathcolor`](pitfalls.md#mathcolor), [`#gkaiu-map`](pitfalls.md#gkaiu-map),
  [`#texlive-cjk`](pitfalls.md#texlive-cjk)) still require walking the decision
  tree in [`pitfalls.md`](pitfalls.md). Exit 0 = toolchain is CDM-capable.

This host path is the **fast `community` path** — good enough to produce a real
CDM score for a conformant, provenance-complete entry.

**Honesty caveats — what CDM is *not*.** CDM is provisioned + smoke-checked, not
"fully automated" or "always works". The [`#cdm-zero`](pitfalls.md#cdm-zero)
failure modes are real and documented; if the smoke probe fails, walk the tree.
On an all-exception result the CDM metric is recorded as **`pending`/null —
never a faked number.** Do not claim CDM is "done/automatic".

### Docker reproducible path (the `verified` path)

For maximum reproducibility, the `verified`-badge path runs `score` inside a
pinned Docker image built from
[`engine/omnidocbench_rocm/docker/Dockerfile.repro`](../engine/omnidocbench_rocm/docker/Dockerfile.repro),
which pins the exact TeX Live / ImageMagick 7 / Ghostscript versions and the
OmniDocBench scorer at `OMNIDOCBENCH_REF=OMNIDOCBENCH_V16_REF`. It reproduces
**scoring** (Edit_dist + TEDS + CDM) from committed predictions. Maintainer
reproductions + a `VERIFIED.yaml` tolerance-checked by
[`scripts/check_verified.py`](../scripts/check_verified.py) are the gate for the
`verified` badge. See the [onboarding runbook](onboarding-runbook.md) Step 7.

---

## Config -> save_name -> result mapping

```text
save_name = basename(prediction_path) + "_" + match_method
```

The `_cdm` suffix on a CDM predictions dir gives the CDM run a different
`save_name` so it doesn't clobber the Edit_dist-only run. `results/omnidocbench/v16/<platform>/`
ends up with:

```text
<save_name>_metric_result.json      # raw OmniDocBench output
<save_name>_run_summary.json        # readme_metrics + metric_quality
<save_name>_provenance.json         # git_commit, platform, engine_version, ...
_run_stats.json                     # adapter-produced, engine-consumed
```

---

## Idempotency

Every `setup.*` script self-checks before doing work. Re-running after success
is fast and prints `already installed` / `already present`. This is what makes
the repo safe to point an agent at: re-running the pipeline is a no-op once
provisioned, and resumes cleanly after a partial run.

---

## Where to look next

- Onboarding a model to a `verified` flagship entry -> [`onboarding-runbook.md`](onboarding-runbook.md)
- Adding a model -> [`contribute-a-model.md`](contribute-a-model.md)
- The contract you implement -> [`contracts/adapter.md`](../contracts/adapter.md)
- Backend policy -> [`contracts/backend-policy.md`](../contracts/backend-policy.md)
- Why CDM is hard -> [`pitfalls.md`](pitfalls.md) (the `#cdm-zero` decision tree)
- What CI does and doesn't cover -> [`ci-reality.md`](ci-reality.md)
- Badge tiers -> [`contracts/badge-policy.md`](../contracts/badge-policy.md)
- Conformance checklist -> [`contracts/conformance.md`](../contracts/conformance.md)
