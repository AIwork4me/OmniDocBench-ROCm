# OmniDocBench-ROCm

> Open adaptation, evaluation, reproduction, and collaboration for document-parsing models on the **AMD ROCm** software stack.

OmniDocBench-ROCm is the shared platform for running open-source document-parsing
models against [OmniDocBench v1.6](https://github.com/opendatalab/OmniDocBench)
on AMD hardware, with a filesystem-decoupled adapter contract that makes scores
**comparable across models and across platforms**, honest tiered trust badges,
real evaluation data, out-of-the-box demos, and bilingual docs.

```text
contracts/   the adapter interface, artifact schema, conformance, badge + backend policy
engine/      omnidocbench_rocm — the pip-installable eval engine (Linux-ROCm implemented)
template/    cookiecutter for a per-model repo (default: Model-ROCm)
hub/         registry.yaml — the comparison-table source of truth
docs/        contribute-a-model, architecture, pitfalls, ci-reality, governance, roadmap
```

## Current Status (honest)

- **Implemented:** the Linux-ROCm eval engine — four-stage pipeline
  (`download → infer → score → publish`), the `omnidocbench-rocm` CLI, the
  conformance checker, the artifact schema, the cookiecutter template, a
  cross-artifact `validate-bundle` checker, and a CPU-only CI.
- **CDM:** Linux host CDM provisioning and scoring are **implemented and
  exercised** by community runs (real formula-CDM scores, e.g. mineru2.5 at
  CDM 96.73). Verified Docker reproduction remains the promotion path from
  `community` to `verified`. Windows-native CDM remains planned.
- **Planned / onboarding:** the **Windows-HIP** backend
  (`get_backend("windows-hip")` raises an explicit not-implemented error today),
  a hosted hub site, and GPU CI.
- **Registry:** real state, not a placeholder — `mineru2.5` is `community` on
  `linux-rocm` (Overall 95.56), `paddleocr-vl-1.6` is `community` on both
  platforms (Overall 95.77), and `unlimited-ocr` / `hunyuan-ocr` are
  `community-wanted`. See the Registry section and `hub/registry.yaml`.
- **DirectML** is a *temporary Windows compatibility fallback* used in selected
  model repos where an equivalent ROCm/MIGraphX path is not yet available; it is
  **not** a first-class project backend.

## Why OmniDocBench-ROCm

- **Comparable scores.** The adapter contract is the filesystem boundary: the
  engine invokes your adapter as a subprocess and consumes only
  `out_dir/<image_stem>.md` + `_run_stats.json`. Your adapter can be in any
  stack; scores are still comparable.
- **Honest trust.** There is no AMD GPU runner in CI, so trust comes from
  tiered badges — not from a green checkmark. See `docs/ci-reality.md`.
- **ROCm-first.** The long-term boundary is the ROCm software stack.

## Scope

- **First-class backends:** HIP, MIGraphX, ONNX Runtime MIGraphX EP,
  PyTorch-ROCm, vLLM-ROCm, llama.cpp-HIP.
- **Transitional:** DirectML — temporary Windows compatibility fallback only.
- **Out of scope:** Vulkan, OpenVINO, general non-ROCm GPU backends.

> ROCm defines the long-term software-stack boundary. DirectML is only a
> temporary Windows compatibility fallback and is not a first-class project
> backend.

Full detail: [`contracts/backend-policy.md`](contracts/backend-policy.md).

## Architecture

One paragraph: a platform repo (this one) holds the shared contracts, the
engine, the template, and the registry; each model lives in its own repo
generated from the template. The engine never imports an adapter — it consumes
the adapter's filesystem output — so model repos can be in any stack.
Platform keys are `linux-rocm` (implemented) and `windows-hip` (planned).

See [`docs/architecture.md`](docs/architecture.md).

## Quick Start

```bash
pip install omnidocbench-rocm
omnidocbench-rocm --help
```

## CLI

```text
omnidocbench-rocm cdm setup --platform <p>            # provision CDM (Linux host)
omnidocbench-rocm dataset download --version v16 --revision <git-rev>
omnidocbench-rocm infer --adapter <path> --img-dir <d> --out-dir <d> --platform <p>
omnidocbench-rocm score --platform <p> --predictions-dir <d> --version v16 --run-stats <path>
omnidocbench-rocm publish --model-id <m> --platform <p> ...   # self-contained bundle (run_summary + provenance + metric + run_stats + prediction manifest)
omnidocbench-rocm run --stage all ...                 # download -> infer -> score -> publish
omnidocbench-rocm conformance <repo-path>             # CONFORMANT | NON-CONFORMANT
omnidocbench-rocm validate-bundle <results-dir>       # cross-artifact consistency (optional --model-card / --registry)
```

## Supported Platforms

| Platform | Status |
|---|---|
| `linux-rocm` | Implemented (score + CDM real; exercised by community runs) |
| `windows-hip` | Planned / onboarding (raises not-implemented today) |

## Evaluation and Reproducibility

- The OmniDocBench dataset revision is **pinned** (the engine refuses an
  unpinned `None` revision).
- `publish` **refuses** to publish official evidence from a limited subset
  (`limit_pages` must be `null` — full-set enforcement).
- Every published run emits a **self-contained bundle** into
  `results/omnidocbench/<version>/<platform>/`: `run_summary.json`,
  `provenance.json`, `metric_result.json`, `run_stats.json`, a deterministic
  SHA256 `prediction_manifest.json`, and a dataset identity. Every artifact
  reference resolves within the repo (runtime source paths are recorded as
  redacted `source_*` fields). `provenance.backend` is the **adapter-reported**
  engine (`_run_stats.json["engine"]`); `publish` refuses to run if it disagrees
  with the requested `--backend`. Provenance distinguishes the packaging commit
  from the `prediction_source_commit` (the real inference commit). Validate any
  bundle with `omnidocbench-rocm validate-bundle <dir>`.

Run inference + scoring + publish in one shot, forwarding backend/server flags
to the adapter (e.g. a MinerU2.5-class VLM on vLLM/ROCm — illustrative):

```bash
omnidocbench-rocm run --stage all --platform linux-rocm --version v16 --revision <git-rev> \
  --adapter adapter/run_adapter.py --model-id <model-id> \
  --backend vlm-vllm --server-url http://127.0.0.1:8000/v1 --api-model-name <model-name> \
  --git-commit $(git rev-parse HEAD) --results-dir results/omnidocbench/v16/linux-rocm
```

## Trust and Badge Model

CI is CPU-only and verifies **structure**, not numbers. Trust comes from the
per-platform badge ([`contracts/badge-policy.md`](contracts/badge-policy.md)):

`community-wanted` → (submit results + pass conformance) → `community` →
(maintainer Docker reproduction + `VERIFIED.yaml`) → `verified`.

Read [`docs/ci-reality.md`](docs/ci-reality.md) before trusting any number.

## Add a Model

[`docs/contribute-a-model.md`](docs/contribute-a-model.md) is the walkthrough.
Short version: generate a repo from the template, implement
`adapter/run_adapter.py` (replace `_infer`), run the `smoke` backend with no GPU,
then `omnidocbench-rocm conformance .`.

```bash
cookiecutter https://github.com/AIwork4me/OmniDocBench-ROCm.git --directory template
```

## Registry

`hub/registry.yaml` is the source of truth for the comparison table. Current
state:

| Model | Repo | linux-rocm | windows-hip |
|---|---|---|---|
| `mineru2.5` | AIwork4me/MinerU-ROCm | community (95.56) | community-wanted () |
| `paddleocr-vl-1.6` | AIwork4me/PaddleOCR-VL-ROCm | community (95.77) | community (95.77) |
| `unlimited-ocr` | AIwork4me/Unlimited-OCR-ROCm | community-wanted () | community-wanted () |
| `hunyuan-ocr` | AIwork4me/HunyuanOCR-ROCm | community-wanted () | community-wanted () |

(The table above is the output of `scripts/generate_registry.py` over
`hub/registry.yaml` — one source of truth, rendered.) `scripts/validate_registry.py`
checks structure and (with `--model-card`) cross-checks the registry Overall /
badge against a model card; `omnidocbench-rocm validate-bundle` checks a
published bundle end-to-end.

## Roadmap

Near-term (planned, not dated): onboard `unlimited-ocr` and `hunyuan-ocr` with
real Linux-ROCm scores; the Windows-HIP backend; a hosted hub site; GPU CI.
See [`docs/roadmap.md`](docs/roadmap.md).

## Contributing

[`CONTRIBUTING.md`](CONTRIBUTING.md). Before a PR: `pytest -q` green,
`python scripts/check_brand.py` clean, `python scripts/validate_registry.py` valid.

## Governance / Security / License

- Governance: [`docs/governance.md`](docs/governance.md)
- Security: [`SECURITY.md`](SECURITY.md) · Support: [`SUPPORT.md`](SUPPORT.md)
- License: Apache-2.0 ([`LICENSE`](LICENSE)) · Cite: [`CITATION.cff`](CITATION.cff)
