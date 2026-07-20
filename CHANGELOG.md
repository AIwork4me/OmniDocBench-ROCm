# Changelog

## Unreleased (post-0.2.0 fixes)

- **CDM works on the host** (PR #7): `omnidocbench-rocm score --cdm` via the
  OmniDocBench checkout's `.venv` produces real CDM scores (verified: CDM 0.3012,
  0 exceptions). Previous claims that "CDM needs Docker / is not viable on host"
  (PRs #5–#6) were a **misdiagnosis** caused by two bugs in the debugging
  tooling, not a host limitation:
  1. The provisioned eval-venv broke CDM's `multiprocessing.Pool(200)` workers
     ("AssertionError: can only join a started process"). The OmniDocBench
     checkout's `.venv` (Python 3.11) works correctly.
     `evalenv/setup-linux.sh` now detects + symlinks the checkout's `.venv`
     instead of creating a separate one.
  2. Ad-hoc test scripts read the wrong JSON key (`ALL_page_avg` — that's
     Edit_dist's key). CDM is at `display_formula.page.CDM.ALL`. The engine's
     own `artifact_utils.py` always read the correct key.
  The host TeX (Debian texlive 2023) + Arphic `gkaiu` font + ImageMagick 7 all
  work correctly for CDM. HunyuanOCR-ROCm's CDM 0.8964 was produced in this same
  environment and is trustworthy.
- **CLI checkout default** (PR #4): `_paths.checkout()` (`OMNIDOCBENCH_CHECKOUT`
  env, default `/workspace/OmniDocBench`); `ensure_checkout` falls back to it
  when the backend is built with `checkout=None`. Fixes `omnidocbench-rocm
  score/run` raising SystemExit.
- **CDM toolchain fixes** (PR #5): `cdm/setup-linux.sh` IM7 source URL switched
  from the 404 `imagemagick.org` path to the GitHub tag archive (7.1.2-8); IM7
  presence check now verifies the version (not just the `magick` binary, which
  may be the IM6 legacy wrapper); CJK-font section warns when `gkai00mp.tfm` is
  absent.
- **PR #6 (superseded by #7):** briefly based `Dockerfile.repro` on the
  official OmniDocBench image + claimed "CDM not viable on host." The Dockerfile
  base change is retained (valid for verified-repro pinning); the "not viable"
  docs were reverted by PR #7.

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
