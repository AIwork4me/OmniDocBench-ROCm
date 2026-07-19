# Changelog

## 0.2.0 — OmniDocBench-ROCm transition (2026-07-19)

- **Brand:** renamed the platform from OmniDocBench-AMD to **OmniDocBench-ROCm**;
  PyPI dist `omnidocbench-rocm`, Python package `omnidocbench_rocm`, CLI
  `omnidocbench-rocm`, cookiecutter default `Model-ROCm`. `OmniDocBench`
  (the upstream benchmark), the platform keys `linux-rocm` / `windows-hip`,
  and the existing model-repo names are unchanged.
- **Legacy surface dropped:** no `omnidocbench-amd` shim, CLI alias, or second
  PyPI distribution. `omnidocbench-amd` was never published and has no pip
  downstream consumers — see
  `docs/audits/2026-07-omnidocbench-rocm-migration-audit.md`.
- **Backend policy:** new `contracts/backend-policy.md` (+ zh-CN) — first-class
  ROCm backends (HIP, MIGraphX, ONNX Runtime MIGraphX EP, PyTorch-ROCm,
  vLLM-ROCm, llama.cpp-HIP); DirectML is a temporary Windows compatibility
  fallback; Vulkan / OpenVINO out of scope.
- **Docs honesty:** `architecture.md` rewritten to match code (no fabricated
  Windows backend or CDM toolchain); `get_backend("windows-hip")` now raises an
  explicit `NotImplementedError`; `provision_cdm` no longer references a
  nonexistent toolchain path.
- **Schema:** optional fields (`backend`, `execution_provider`,
  `backend_family`, `compatibility_status`, `target_backend`) added to the
  `model_card` and `provenance` `$defs`; `schema_version` stays 1
  (backward-compatible).
- **Template:** fixed `make eval-windows` silently running Linux (split into
  two recipes with explicit `--platform`); cookiecutter default `Model-ROCm`;
  dependency `omnidocbench-rocm>=0.2.0`.
- **Registry:** new `scripts/validate_registry.py` (model_id / repo / platform
  / badge / overall / duplicate checks) wired into CI. Registry remains an
  honest placeholder (3 models, `community-wanted`, no scores).
- **CI:** Python 3.10 / 3.11 / 3.12 matrix; package build + wheel metadata
  checks; registry validation; brand-residue gate
  (`scripts/check_brand.py`); `permissions: contents: read`.
- **Governance:** added CHANGELOG, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY,
  SUPPORT, CITATION, CODEOWNERS, issue/PR templates, `docs/governance.md`,
  `docs/roadmap.md`, and ADRs 0001–0002.

## 0.1.0

Initial platform: shared Linux-ROCm OmniDocBench v1.6 eval engine, cookiecutter
per-model template, contracts, badge policy, and an initial placeholder
registry.
