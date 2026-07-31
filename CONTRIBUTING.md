# Contributing to OmniDocBench-ROCm

Thank you for helping adapt open-source document-parsing models to the AMD ROCm
software stack. This guide is the short version; the full walkthrough lives at
[`docs/contribute-a-model.md`](docs/contribute-a-model.md).

## Scope

OmniDocBench-ROCm targets the **ROCm** stack (HIP, MIGraphX, ONNX Runtime
MIGraphX EP, PyTorch-ROCm, vLLM-ROCm, llama.cpp-HIP). **DirectML** is a
*temporary Windows compatibility fallback* only; **Vulkan / OpenVINO** are out
of scope. See [`contracts/backend-policy.md`](contracts/backend-policy.md).

## Ways to contribute

Anyone can contribute — the zone is not limited to the `AIwork4me` namespace
(ROCmDoc Standard §12, §13.1). Five low-friction paths, each with its own evidence
bar (see the issue templates in `.github/ISSUE_TEMPLATE/`):

1. **Adopt a model** — create or maintain a model adapter (start from the
   `template/` cookiecutter). See *Adding a model* below.
2. **Share a hardware run** — submit a real run report on a new AMD GPU / ROCm
   version (raises `cross_hardware_reproduction` over time). Issue template:
   `hardware-result`.
3. **Reproduce a score** — re-score committed predictions with the locked scorer
   (no inference GPU required). Raises `platform_review.score_reproduction`.
4. **Reproduce inference** — independently re-run full inference + scoring on AMD
   hardware. Raises `platform_review.inference_reproduction`.
5. **Docs / tests / translation / golden fixtures** — no GPU needed; improves
   bilingual consistency, fixtures, CI, and the standard itself.

Trust is recorded as split `producer_assurance` + `platform_review`
(`evidence_integrity` / `score_reproduction` / `inference_reproduction` /
`cross_hardware_reproduction`), never as a single flattened badge — see
[`contracts/ROCMDOC_STANDARD.md`](contracts/ROCMDOC_STANDARD.md) §8.

## Adding a model

1. Generate a repo from the template:
   `cookiecutter https://github.com/AIwork4me/OmniDocBench-ROCm.git` (or a local
   checkout) → defaults to `Model-ROCm`.
2. Implement `adapter/run_adapter.py` (replace the `_infer` body; keep the
   signature, the `.md` output convention, the per-page `try/except`, and the
   `_run_stats.json` write). See [`contracts/adapter.md`](contracts/adapter.md).
3. Run the smoke backend with no GPU:
   `python adapter/run_adapter.py --img-dir examples --out-dir /tmp/out --platform linux-rocm --backend smoke`.
4. Run conformance: `omnidocbench-rocm conformance .` (must print `CONFORMANT`).

## CI reality

There is **no AMD GPU runner** in CI — CI is CPU-only and checks the contract,
the schema, the template, conformance, and (now) the brand. Real GPU evaluation
is maintainer-run; trust comes from the split `producer_assurance` /
`platform_review` model (ROCmDoc Standard §8), not from a green CI check. The
legacy `community/verified` badge is retained only as a lossy compatibility
projection — see [`contracts/badge-policy.md`](contracts/badge-policy.md)
(legacy). See [`docs/ci-reality.md`](docs/ci-reality.md).

## Before you open a PR

- `python -m pytest -q` is green.
- `python scripts/check_brand.py` reports clean (it forbids the pre-0.2.0 brand
  strings outside the sanctioned record files: `docs/superpowers/**`,
  `docs/audits/**`, `docs/adr/**`, `CHANGELOG.md`).
- `python scripts/validate_registry.py hub/registry.yaml` is valid (if you
  touched the registry).
- No fabricated results, no auto-selection of the highest score as primary, and
  no inflation of `producer_assurance` / `platform_review` (score-reproduction
  is not inference-reproduction; `NOT_RUN` stays `NOT_RUN`). Unknown identity
  fields stay `unknown`.

## DCO (Developer Certificate of Origin)

This project uses **DCO 1.1** (no CLA). Each commit MUST be signed off:
add `Signed-off-by: Your Name <you@example.com>` to each commit (git's
`-s`/`--signoff` flag does this). By signing off you attest to the
[Developer Certificate of Origin](https://developercertificate.org/). AI-assisted
contributions are welcome; the human author attests and signs off.

## License

Contributions are licensed under Apache-2.0 (see [`LICENSE`](LICENSE)).
