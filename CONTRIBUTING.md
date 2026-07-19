# Contributing to OmniDocBench-ROCm

Thank you for helping adapt open-source document-parsing models to the AMD ROCm
software stack. This guide is the short version; the full walkthrough lives at
[`docs/contribute-a-model.md`](docs/contribute-a-model.md).

## Scope

OmniDocBench-ROCm targets the **ROCm** stack (HIP, MIGraphX, ONNX Runtime
MIGraphX EP, PyTorch-ROCm, vLLM-ROCm, llama.cpp-HIP). **DirectML** is a
*temporary Windows compatibility fallback* only; **Vulkan / OpenVINO** are out
of scope. See [`contracts/backend-policy.md`](contracts/backend-policy.md).

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
is maintainer-run; trust comes from the tiered badge model, not from a green CI
check. See [`docs/ci-reality.md`](docs/ci-reality.md).

## Before you open a PR

- `python -m pytest -q` is green.
- `python scripts/check_brand.py` reports clean (it forbids the pre-0.2.0 brand
  strings outside the sanctioned record files: `docs/superpowers/**`,
  `docs/audits/**`, `docs/adr/**`, `CHANGELOG.md`).
- `python scripts/validate_registry.py hub/registry.yaml` is valid (if you
  touched the registry).
- No fabricated results, and no auto-promotion of a result to `verified`.

## License

Contributions are licensed under Apache-2.0 (see [`LICENSE`](LICENSE)).
