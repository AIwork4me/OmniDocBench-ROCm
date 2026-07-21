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
hub/         registry.yaml — the comparison-table source of truth (initial placeholder)
docs/        contribute-a-model, architecture, pitfalls, ci-reality, governance, roadmap
```

## Current Status (honest)

- **Implemented:** the Linux-ROCm eval engine — four-stage pipeline
  (`download → infer → score → publish`), the `omnidocbench-rocm` CLI, the
  conformance checker, the artifact schema, the cookiecutter template, and a
  CPU-only CI.
- **Partial:** CDM (formula matching) provisioning is a scaffolded stub on
  Linux, not wired end-to-end; scoring currently pins the OmniDocBench checkout
  to `master`.
- **Planned / onboarding:** the **Windows-HIP** backend
  (`get_backend("windows-hip")` raises an explicit not-implemented error today),
  end-to-end CDM provisioning, a hosted hub site, and GPU CI.
- **Registry:** an **initial placeholder**, not a leaderboard — 3 models
  (`paddleocr-vl-1.6`, `unlimited-ocr`, `mineru2.5`) are listed as
  `community-wanted` on both platforms with no scores yet.
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
omnidocbench-rocm cdm setup --platform <p>            # provision CDM (partial/planned)
omnidocbench-rocm dataset download --version v16 --revision <git-rev>
omnidocbench-rocm infer --adapter <path> --img-dir <d> --out-dir <d> --platform <p>
omnidocbench-rocm score --platform <p> --predictions-dir <d> --version v16 --run-stats <path>
omnidocbench-rocm publish --model-id <m> --platform <p> ...   # assembles run_summary + provenance
omnidocbench-rocm run --stage all ...                 # download -> infer -> score -> publish
omnidocbench-rocm conformance <repo-path>             # CONFORMANT | NON-CONFORMANT
```

## Supported Platforms

| Platform | Status |
|---|---|
| `linux-rocm` | Implemented (score path real; CDM partial) |
| `windows-hip` | Planned / onboarding (raises not-implemented today) |

## Evaluation and Reproducibility

- The OmniDocBench dataset revision is **pinned** (the engine refuses an
  unpinned `None` revision).
- `publish` **refuses** to publish official evidence from a limited subset
  (`limit_pages` must be `null` — full-set enforcement).
- Every published run carries `run_summary.json` + `provenance.json`
  (git commit, platform, engine version, adapter command, dataset revision).
  `provenance.backend` is the **adapter-reported** engine
  (`_run_stats.json["engine"]`), and `publish` refuses to run if it disagrees
  with the requested `--backend`.

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

`hub/registry.yaml` is the source of truth for the comparison table. Today it is
an **initial placeholder** (3 models, `community-wanted`, no scores) — not a
complete leaderboard. `scripts/validate_registry.py` checks its structure;
`scripts/generate_registry.py` renders it to Markdown.

## Roadmap

Near-term (planned, not dated): onboard the three v1 models with real
Linux-ROCm scores; Windows-HIP backend; end-to-end CDM (Linux first); a hosted
hub site. See [`docs/roadmap.md`](docs/roadmap.md).

## Contributing

[`CONTRIBUTING.md`](CONTRIBUTING.md). Before a PR: `pytest -q` green,
`python scripts/check_brand.py` clean, `python scripts/validate_registry.py` valid.

## Governance / Security / License

- Governance: [`docs/governance.md`](docs/governance.md)
- Security: [`SECURITY.md`](SECURITY.md) · Support: [`SUPPORT.md`](SUPPORT.md)
- License: Apache-2.0 ([`LICENSE`](LICENSE)) · Cite: [`CITATION.cff`](CITATION.cff)
