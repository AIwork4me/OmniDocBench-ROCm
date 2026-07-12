# Handoff — Phase A shipped → PaddleOCR-VL onboarding (sub-project 4)

**Date:** 2026-07-12
**Author:** Claude (this session)
**Audience:** (a) the colleague doing the **Windows/Strix Halo** PaddleOCR-VL eval; (b) future Claude session(s) doing the **Linux/Radeon** adaptation + eval + finalizing the onboarding.

> Status in one line: the **platform foundation (Phase A) is shipped** (PR #1 merged to `main`, CI green). No model has run through the new platform end-to-end yet — **PaddleOCR-VL will be the first**, validating the contracts against a real model. This doc splits that work into a Windows track (colleague), a Linux track (Claude), and a finalization step.

---

## 1. Where things stand

- **Repo:** [github.com/AIwork4me/OmniDocBench-AMD](https://github.com/AIwork4me/OmniDocBench-AMD) (public). `main` is the source of truth. `feat/platform-foundation` is the merged feature branch (can be deleted).
- **Phase A shipped** (PR #1, merge commit `84b91e2`; rename commit `3821d97` on top). On `main` now:
  - **Shared contracts** (`contracts/`): adapter interface, artifact JSON schema (`schema_version: 1`), conformance checklist, badge policy.
  - **Dual-platform eval engine** (`engine/omnidocbench_amd/`, pip package `omnidocbench-amd`): 4-stage orchestrator (download→infer→score→publish), `linux_rocm` backend, artifact_utils (schema-validated writes, CDM-validity nulling, full-set enforcement), CLI `omnidocbench-amd cdm|dataset|infer|score|publish|run|conformance`.
  - **Per-model template** (`template/`, cookiecutter): `--backend smoke` adapter, Makefile, bilingual READMEs, `model_card.json`, CI.
  - **Conformance + trust:** `check_conformance.py` + `omnidocbench-amd conformance <repo>`; tiered badges (`verified`/`community`/`community-wanted`); honest trust model (CI is CPU-only — no native AMD GPU runners on GitHub Actions).
  - **Hub registry** (`hub/registry.yaml`): 3 v1 models seeded (PaddleOCR-VL-1.6, Unlimited-OCR, MinerU2.5), all `community-wanted` until onboarded.
  - **Docs:** contributor guide (EN + CN-optimized), architecture, pitfalls (absorbed from `omnidocbench-amd-windows`), ci-reality, adapter contract.
  - **CI:** `.github/workflows/ci.yml` (CPU: pytest 25/25 + conformance + cookiecutter render).
- **NOT done (deferred → folds into sub-project 4 / Phase B):** real CDM provisioning on Linux (Task 14); the `windows-hip` backend port (Task 15); running ANY real model end-to-end through the new platform (Task 16).
- **Read these first:** `docs/superpowers/specs/2026-07-12-amd-doc-parsing-platform-foundation-design.md` (the design) · `docs/contribute-a-model.md` (the 9-step contributor flow) · `contracts/adapter.md` + `contracts/artifact-schema.json` (the contract).

## 2. The goal — PaddleOCR-VL onboarding (sub-project 4)

Onboard **PaddleOCR-VL-1.6** as the first real model on the platform, on **both** platforms, producing **real OmniDocBench v1.6 eval data** that lands in `PaddleOCR-VL-ROCm` and registers in the hub with a badge. This validates the contracts against a real model (the Task 8 integration test only used a smoke adapter) and produces the zone's first credible numbers.

### Division of labor

| Track | Owner | Platform | Status |
|---|---|---|---|
| **A. Windows/Strix Halo eval** | **Colleague** | Ryzen AI MAX+ 395 (Radeon 8060S) + Windows/HIP | pending |
| **B. Linux/Radeon adaptation + eval** | **Claude** (future session) | Radeon dGPU (gfx1100 / W7900) + Linux/ROCm | pending |
| **C. Finalize onboarding** | **Claude** (after A + B) | both | pending |

Tracks A and B are **independent** and can run in parallel. C starts when both produce conformant artifacts.

---

## 3. Track A — Colleague: Windows/Strix Halo PaddleOCR-VL eval

**Objective:** a full OmniDocBench v1.6 (1651-page) PaddleOCR-VL-1.6 eval on the Strix Halo Windows box, producing artifacts that conform to the new platform's schema, landing in `PaddleOCR-VL-ROCm/results/omnidocbench/v16/windows-hip/`.

**Reuse the proven harness, don't reinvent:** `AIwork4me/omnidocbench-amd-windows` already does Windows/HIP PaddleOCR-VL-1.6 eval end-to-end (Overall 95.9475 recorded), with Windows-native CDM + WSL fallback + a `paddleocr-vl-1.6` reference adapter. Run the full eval there.

**Concrete steps:**
1. On the Strix Halo Windows box, clone `AIwork4me/omnidocbench-amd-windows`, follow its README (4-phase idempotent setup: omnidocbench dataset → CDM environment → paddleocr-vl-1.6 adapter → scoring). It targets Radeon 8060S (Strix Halo) + RX 7900 XT+.
2. Run the **full** 1651-page eval (not a subset — the platform refuses to publish evidence from `limit_pages != null` predictions). Capture: `metric_result.json` (the 4 metrics: text Edit-dist, reading-order Edit-dist, table TEDS, formula CDM), per-page `.md` predictions, `_run_stats.json`.
3. **Format the output to the new platform's schema** (this is the bridge from the old harness to the new platform):
   - `provenance.json` — see `contracts/artifact-schema.json` `$defs.provenance`. Required fields: `schema_version: 1`, `created_at_utc`, `git_commit`, `platform: "windows-hip"`, `engine_version`, `model_id: "paddleocr-vl-1.6"`, `adapter_command`, `dataset_manifest_path`, `dataset_revision` (PINNED — no `latest`), `prediction_dir`, `page_count`, `ok_pages`, `failed_pages`, `metric_result_paths`, `run_summary_paths`, `run_stats_path`.
   - `run_summary.json` — `$defs.run_summary`: `save_name`, `engine`, `cdm: true`, `prediction_count: 1651`, `ok/failed/fallback_pages`, `readme_metrics {text_edit_dist, reading_order_edit_dist, table_teds_percent, formula_cdm_percent}`, `metric_quality.formula_cdm.valid` (must be `true` — if every CDM sample raised, CDM is `pending`/null, NOT a faked number).
   - `model_card.json` — `$defs.model_card`: `model_id`, `model_version`, `platforms: ["linux-rocm","windows-hip"]`, `badge: {windows-hip: "community", linux-rocm: "community-wanted"}` (until Claude's Linux track fills linux-rocm), `overall`, `hardware {gpu: "Radeon 8060S", vram, rocm_driver}`, artifact links.
4. Place the bundle in `PaddleOCR-VL-ROCm/results/omnidocbench/v16/windows-hip/`.
5. **Windows ONNX = `onnxruntime-directml`** (DirectML EP, `DmlExecutionProvider`, via Microsoft Olive) per [AMD Ryzen AI GPU docs](https://ryzenai.docs.amd.com/en/latest/gpu/ryzenai_gpu.html). **Never ROCm EP on Windows.**

**Tooling note:** the new `windows-hip` backend (Task 15) is NOT yet built. For Track A you don't need it — the existing `omnidocbench-amd-windows` harness produces the raw results; you just format them to the schema above. (Task 15 — porting that harness into the engine's `windows-hip` backend — is a later cleanup, optional for A.)

**Definition of done for A:** `PaddleOCR-VL-ROCm/results/omnidocbench/v16/windows-hip/` contains a schema-valid `provenance.json` + `run_summary.json` + `model_card.json` (windows-hip `community`) + the per-page `.md` + `metric_result.json`, from a full 1651-page run.

---

## 4. Track B — Claude (future): Linux/Radeon PaddleOCR-VL adaptation + eval

**Objective:** run PaddleOCR-VL-1.6 through the new platform's `linux-rocm` backend on the gfx1100/W7900 box, producing conformant artifacts in `PaddleOCR-VL-ROCm/results/omnidocbench/v16/linux-rocm/`. This is where the deferred Phase-B Linux work lands.

**Reuse `AIwork4me/PaddleOCR-VL-ROCm`** — it already does PaddleOCR-VL on Linux (ONNX layout `PP-DocLayoutV3` via ONNXRuntime + ROCm-backed VLM serving via vLLM or llama.cpp). Its `eval/` dir (`run_eval.py`, `artifact_utils.py`, `PaddleOCRVLROCm_img2md.py`) is literally what the new engine was ported from.

**Concrete steps:**
1. **Port the adapter to the new contract.** Create `PaddleOCR-VL-ROCm/adapter/run_adapter.py` implementing `run_adapter(img_dir, out_dir, *, platform="linux-rocm", config) -> dict` per `contracts/adapter.md` (the engine invokes it as a subprocess, consumes `out_dir/<stem>.md` + `_run_stats.json`). It can shell out to the existing `PaddleOCRVLROCm_img2md.py` logic. Add `adapter/adapter_config.py` + `adapter/setup/00-install-deps.sh` (ONNX `onnxruntime-rocm` ROCm EP for layout + vLLM/ROCm server for the VLM).
2. **Build the deferred Linux CDM (Task 14):** `engine/omnidocbench_amd/cdm/setup-linux.sh` (idempotent apt: texlive-full + ImageMagick 7 + ghostscript + nodejs) + wire `LinuxRocmBackend.provision_cdm()` + the `--cdm` / `--docker` path (Docker image `ghcr.io/zeng-weijun/omnidocbench-eval:repro-ubuntu2204` for `verified`-grade reproducibility).
3. **Resolve the `# TODO Task 16` items in `engine/omnidocbench_amd/backends/linux_rocm.py`** (these are the real-eval blockers the CPU MVP left as placeholders):
   - `score()`'s `pdf_validation.py` CLI args are a placeholder — wire the real invocation (config-driven, the way OmniDocBench's `pdf_validation.py` actually expects: a YAML config pointing at the predictions dir + GT manifest, not `--config <version> --predictions <dir>`). Confirm against `OmniDocBench/src/cli.py`.
   - `img_dir` derivation (`dataset_dir(version)/images`) — confirm against the real OmniDocBench v1.6 layout.
   - `config` forwarding — `stage_infer` accepts `config` but doesn't pass it to the adapter subprocess; if the PaddleOCR-VL adapter needs config beyond `.env.local`, add `--config <json>`.
   - `revision="master"` hardcoded in `score()` — plumb a pinned revision instead.
4. **Provision the eval-venv (Python 3.11)** — OmniDocBench scoring breaks on 3.12. `engine` provisions it under `$OMNIDOCBENCH_AMD_DATA/eval-venv/linux-rocm`. The model inference venv (PaddleOCR-VL) can be 3.12.
5. **Run the full 1651-page eval** via `omnidocbench-amd run --stage all --platform linux-rocm --version v16 --revision <pin> --adapter PaddleOCR-VL-ROCm/adapter/run_adapter.py --model-id paddleocr-vl-1.6 ...` (or `make eval-linux` from the template-rendered repo). Produce `provenance.json` + `run_summary.json` + per-page `.md` + `metric_result.json` in `results/omnidocbench/v16/linux-rocm/`.
6. **Cross-check:** Linux Overall should be in the same ballpark as the Windows result (the two engines should agree to within drift tolerance; large divergence = a bug, investigate).

**Definition of done for B:** `PaddleOCR-VL-ROCm/results/omnidocbench/v16/linux-rocm/` contains a schema-valid artifact bundle from a full run; `linux_rocm.score()` no longer has placeholder CLI args (the `# TODO Task 16`s are resolved).

---

## 5. Track C — Claude (after A + B): finalize the onboarding

1. Both platform bundles exist under `PaddleOCR-VL-ROCm/results/omnidocbench/v16/{linux-rocm,windows-hip}/`.
2. `PaddleOCR-VL-ROCm` passes `omnidocbench-amd conformance .` (the per-model repo conforms: adapter, eval config, both results dirs non-empty, bilingual READMEs with required sections, `pyproject.toml` depends on `omnidocbench-amd`, `model_card.json` schema-valid).
3. Update `model_card.json` badges: `{linux-rocm: "community", windows-hip: "community"}`.
4. Update `OmniDocBench-AMD/hub/registry.yaml`: set `paddleocr-vl-1.6` platforms to the real Overall scores, badges `community`.
5. **(Optional, for `verified`)** Maintainer reproduces both platforms via the Docker CDM path → commits `VERIFIED.yaml` → badges → `verified`. This is the first `verified` row in the zone.

---

## 6. The contract both tracks must satisfy (so A and B produce compatible output)

- **Adapter:** `run_adapter(img_dir: Path, out_dir: Path, *, platform: Literal["linux-rocm","windows-hip"], config: dict) -> dict`. Writes `out_dir/<image_stem>.md` (UTF-8) per page + `_run_stats.json`. Filesystem-decoupled (engine invokes as subprocess, never imports). Per-page failure → that page scores zero, run continues, never raise. → `contracts/adapter.md`.
- **Artifacts:** 4 files, all `schema_version: 1` → `contracts/artifact-schema.json`: `_run_stats.json`, `provenance.json`, `run_summary.json`, `model_card.json` (+ `metric_result.json` = raw OmniDocBench passthrough).
- **Conformance:** `omnidocbench-amd conformance <repo>` must exit 0 → `contracts/conformance.md` + `contracts/badge-policy.md`.
- **Per-platform ONNX EP:** Linux = `onnxruntime-rocm` (ROCm EP); Windows = `onnxruntime-directml` (DirectML EP). Never ROCm EP on Windows.
- **No faking:** invalid CDM (all-exception) → `formula_cdm_percent: null`; `limit_pages != null` → publish refused.

## 7. Existing assets to reuse (do not rebuild)

- **`AIwork4me/PaddleOCR-VL-ROCm`** — the dual-OS model repo. Its `eval/` is the engine's lineage. Port its adapter to the new contract; its `results/omnidocbench/v16/` already has some provenance/run_summary artifacts (llama.cpp/GGUF route) as a formatting reference.
- **`AIwork4me/omnidocbench-amd-windows`** — the proven Windows harness (colleague's Track A). Will eventually be absorbed into the engine's `windows-hip` backend (Task 15) + archived, but that's not blocking.
- **`OmniDocBench-AMD` engine** — the `linux-rocm` backend is ready except the `# TODO Task 16` real-CLI items; `windows-hip` is lazy-imported (build in Task 15 / Track A doesn't need it).

## 8. Environment + process gotchas (both parties)

- **git push can't update existing branches** from this env (MITM proxy breaks `git-receive-pack`). Workaround: push the commit on a throwaway NEW branch, then `gh api --method PATCH repos/AIwork4me/<repo>/git/refs/heads/<branch> -f sha=<full-40>`, then delete the throwaway. Or for merging: `gh pr merge <n> --merge`. Creating branches + `gh api` + `gh pr merge` all work. (See memory `github-push-from-env.md`.) **On a normal Windows/Linux box without this proxy, plain `git push` works — this gotcha is specific to Claude's sandbox env.**
- **`workflow` scope** is now on the gh token (refreshed 2026-07-12) — pushing `.github/workflows/*.yml` works.
- **10 GB NFS at `/workspace`** (Claude's env): repos stay code-only; heavy data (dataset, predictions, venvs, weights, CDM toolchain) under `${OMNIDOCBENCH_AMD_DATA:-/root/ocr-eval/omnidocbench-amd-data}`. The per-model repo's `.gitignore` excludes `data/`, `predictions/`, `*.gguf`, venvs.
- **Python split:** OmniDocBench scoring needs 3.10/3.11 (breaks on 3.12) — separate eval-venv from the model inference venv.
- **Dev venv (Claude's env):** `/root/ocr-eval/omnidocbench-amd-venv` (`. /root/ocr-eval/omnidocbench-amd-venv/bin/activate`; `pip install -e ".[dev]"` from the `OmniDocBench-AMD` repo).
- **Progress ledger:** `OmniDocBench-AMD/.superpowers/sdd/progress.md` (gitignored scratch — the durable record of what each task did + the deferred Minors + the push protocol).

## 9. When Claude resumes (Track B / C)

1. Re-read this handoff + the ledger + `contracts/`.
2. **Check Track A status first** — is `PaddleOCR-VL-ROCm/results/omnidocbench/v16/windows-hip/` populated + schema-valid? (If yes, proceed to B; the Windows numbers also give B a cross-check target.)
3. Do Track B (Linux). Resolve the `# TODO Task 16`s as part of it — they block real eval.
4. Do Track C (finalize) once both bundles exist.
5. The whole onboarding is itself a spec→plan→execute cycle (brainstorm the PaddleOCR-VL onboarding spec first if the contracts need adjustment; the platform foundation contracts are the starting point, not necessarily final — real-model onboarding is what pressure-tests them).

---

## 10. Quick links

- Repo: https://github.com/AIwork4me/OmniDocBench-AMD
- Spec: `docs/superpowers/specs/2026-07-12-amd-doc-parsing-platform-foundation-design.md`
- Plan: `docs/superpowers/plans/2026-07-12-amd-doc-parsing-platform-foundation.md`
- Contracts: `contracts/{adapter.md, artifact-schema.json, conformance.md, badge-policy.md}`
- Contributor guide: `docs/contribute-a-model.md` (+ `.zh-CN.md`)
- Reference model repos: `AIwork4me/PaddleOCR-VL-ROCm`, `AIwork4me/Unlimited-OCR-ROCm`
- Windows harness: `AIwork4me/omnidocbench-amd-windows`
- AMD Windows GPU docs (DirectML): https://ryzenai.docs.amd.com/en/latest/gpu/ryzenai_gpu.html
