# AMD Document-Parsing Model Zone — Platform Foundation Design

**Date:** 2026-07-12
**Status:** Design (awaiting user spec review)
**Sub-projects covered:** 0 (shared contracts) + 2 (dual-platform shared eval engine) + 3 (per-model repo template)
**Spec home:** currently in `Unlimited-OCR-ROCm/docs/superpowers/specs/`; will move into the new `omnidocbench-amd` repo at implementation step 1.

---

## 1. Context & Background

Goal: a top-tier, bilingual (global + Chinese-optimized) open-source **专区 (zone)** for running
OmniDocBench v1.6 open-source document-parsing models on AMD hardware, on two platform
categories:

- **Category 1:** Radeon dGPU + Linux/ROCm
- **Category 2:** Ryzen AI MAX+ 395 (Strix Halo, Radeon 8060S iGPU) + Windows/HIP

Every model ships: real dual-platform OmniDocBench v1.6 eval data, out-of-the-box code + demo,
and trust-enhancing docs. Community can contribute new models. Closed-source models
(Gemini, GPT, Mistral-OCR, mathpix, HunYuan-OCR, Youtu-Parsing, Nanonets, GLM-OCR, …) are
never supported.

### What already exists (this is not greenfield)

Three repos under `AIwork4me` form the foundation:

| Repo | State | Role for the zone |
|---|---|---|
| `Unlimited-OCR-ROCm` | mature, v1.3.0, PyPI, Overall 92.431, full superpowers discipline | Linux/ROCm reference model. **Gap: Linux-only, no Windows path yet.** |
| `PaddleOCR-VL-ROCm` | dual-OS (Win+Linux), ONNX layout + OpenAI-compatible VLM serving (vLLM/ROCm on Linux, llama.cpp/GGUF on Windows), real v1.6 eval artifacts + provenance, bilingual | Most platform-complete reference model |
| `omnidocbench-amd-windows` | model-agnostic Windows eval harness, `adapters/_template/`, 4-phase idempotent setup, all 4 metrics incl. CDM, real results (Overall 95.9475), targets 8060S + RX 7900 XT+ | Already the Windows-side shared engine + adapter template |

### Proven de-facto contracts (lift, don't reinvent)

- **Adapter contract** (from `omnidocbench-amd-windows/adapters/`):
  `run_adapter(img_dir, out_dir, server_url)` → writes `out_dir/<image_stem>.md` per page.
  The eval-infra **never imports the adapter**; it only consumes `.md` files
  (filesystem-decoupled → language/stack-agnostic). Per-page failure → scores zero, run continues.
- **Staged eval pipeline** (from `PaddleOCR-VL-ROCm/eval/`): `download → infer → eval`, each gated.
  Artifact schema already exists: `metric_result.json` + `run_summary.json` (with
  `readme_metrics` + `metric_quality`, refuses to publish invalid CDM) + `provenance.json`.
- **Windows harness architecture** (from `omnidocbench-amd-windows/docs/architecture.md`):
  3 layers — `adapters/` → `eval-infra/` (01-omnidocbench, 02-cdm-environment, 03-scoring,
  04-benchmark) → `scripts/docs`. Idempotent. Windows-native CDM + WSL fallback.
- **Hard constraint:** OmniDocBench eval env needs Python 3.10/3.11 (breaks on 3.12) — must be
  separate from the model inference env. CDM (Node + ImageMagick 7 + TeX Live CJK) is the hard,
  high-value part.

### Hardware reality (confirmed, not assumed)

- Linux/ROCm: this environment (gfx1100 / Radeon PRO W7900 48GB). Unlimited-OCR-ROCm's 92.431
  was produced here.
- Windows/HIP: `omnidocbench-amd-windows` has real Windows-native CDM results dated 2026-07-11,
  targeting Radeon 8060S (Strix Halo) + RX 7900 XT+.

---

## 2. v1 Scope

**In (this spec = platform foundation, sub-projects 0+2+3):**
- Shared contracts: adapter interface, artifact JSON schema, repo conformance checklist, badge policy.
- Shared dual-platform eval engine: `linux-rocm` + `windows-hip` backends, CDM provisioning.
- Per-model repo template (cookiecutter).
- Contributor guide + verification/badge flow.
- `hub/` skeleton + registry generator (site polish is sub-project 1).

**In (as validation targets only — their actual onboarding/migration is sub-project 4):**
- The 3 reference models: **PaddleOCR-VL-1.6, Unlimited-OCR, MinerU2.5**. Chosen for architectural
  diversity (pure VLM / layout+VLM / layout+formula+OCR pipeline) to prove contract generality.

**Out (later specs):**
- Hub site visual polish (sub-project 1).
- Migration of existing repos + onboarding the 3 models (sub-project 4).
- Scaling beyond 3 models (sub-project 5).

### Success criteria
1. A new model is onboarded by copying the template + implementing one `run_adapter` + running
   `make eval` on both platforms — **no engine code edits**.
2. The 3 reference models each produce the standard artifact bundle (provenance + run_summary +
   per-page `.md` + metric_result) on **both** platforms, with CDM validity checked.
3. A stranger can go from clone → scored model in **half a day per platform** (hardware + weights ready).
4. Badges `verified` / `community` are enforceable via `scripts/check-conformance.py`.

---

## 3. Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| v1 model scope | PaddleOCR-VL-1.6 + Unlimited-OCR + MinerU2.5, contributor-friendly |
| First sub-project | Platform foundation (0+2+3) |
| Trust model | **Tiered badges**: maintainer-reproduced → `verified`; provenance-complete self-attested → `community`; no forced GPU CI |
| Topology | **A**: single platform repo (contracts+engine+template+hub) + independent per-model repos; absorb `omnidocbench-amd-windows` as the `windows-hip` backend |
| Per-model repo naming | New repos `-AMD` (platform-neutral); existing `-ROCm` repos keep their names |
| License | Platform + engine: Apache 2.0; new model repos default Apache 2.0; existing keep theirs |
| Hub brand | "AMD Doc Parsing" / 中文 "AMD 文档解析模型专区" |

---

## 4. Architecture (Topology A)

### Platform repo `omnidocbench-amd/`
```
contracts/
  adapter.md             # the run_adapter contract (canonical)
  artifact-schema.json   # provenance/run_summary/metric_result/model_card JSON schema (schema_version: 1)
  conformance.md         # per-model repo conformance checklist
  badge-policy.md        # verified vs community rules
engine/
  omnidocbench_amd/      # pip package
    stages.py            # download/infer/score/publish orchestrator (from PaddleOCR-VL-ROCm/eval/run_eval.py)
    artifact_utils.py    # (from PaddleOCR-VL-ROCm/eval/artifact_utils.py)
    backends/
      linux_rocm.py      # Linux scoring + CDM (native TeX Live)
      windows_hip.py     # Windows scoring + CDM (native patch + WSL fallback) — absorbed from omnidocbench-amd-windows/eval-infra
    cdm/                 # cross-platform CDM provisioning scripts (bash + ps1)
  pyproject.toml
template/                # cookiecutter: {{cookiecutter.model_slug}}-AMD/
hub/
  registry.yaml          # model registry (source of truth for the comparison table)
  site/                  # mkdocs/docusaurus source
docs/
  contribute-a-model.md (+ .zh-CN.md)
  architecture.md
  pitfalls.md            # absorbed from omnidocbench-amd-windows
  ci-reality.md          # what CI does/doesn't cover (no AMD GPU runners)
scripts/
  check-conformance.py   # validate a per-model repo against contracts/ + enforce badge rules
.github/workflows/       # CI: contract tests, template smoke, engine self-test (CPU-feasible parts)
```

### Per-model repo `<Model>-AMD/` (from template)
```
adapter/
  run_adapter.py         # implements the contract; the ONLY model-specific code
  adapter_config.py      # weights paths, server url, per-platform backend choice
  setup/
    00-install-deps.{sh,ps1}
    01-vlm-server.{sh,ps1}     # linux-rocm→vLLM/ROCm; windows-hip→llama.cpp/HIP-GGUF or vLLM-rocm-win
    02-layout-model.{sh,ps1}   # if model needs layout ONNX
    .env.local.example
eval/configs/omnidocbench_v16.yaml
results/omnidocbench/v16/{linux-rocm,windows-hip}/.gitkeep
examples/demo.png + run_demo.{sh,ps1}
README.md / README.zh-CN.md
docs/{how-it-works,reproducibility,known-gaps,backends}.md
model_card.json
pyproject.toml          # depends on pinned omnidocbench-amd
Makefile                # make demo / eval-linux / eval-windows / publish / setup-*
.github/workflows/ci.yml
.gitignore / LICENSE(Apache-2.0) / CONTRIBUTING.md / CODE_OF_CONDUCT.md
```

### Data flow (per platform)
```
OmniDocBench v1.6 (1651 pages) ──► adapter/run_adapter.py ──► predictions/<model>/*.md
                                                                │
                                  engine (linux-rocm | windows-hip)
                                ▼
              metric_result.json + run_summary.json + provenance.json + model_card.json
                                │  scripts/check-conformance.py
                                ▼
                hub/registry.yaml ──► badge (verified/community) + comparison table
```

The adapter is **filesystem-decoupled** (engine never imports it; only consumes `.md` +
`_run_stats.json`) → language/stack-agnostic → the contract that makes scores comparable across
models and platforms.

---

## 5. Shared Contracts (sub-project 0)

### 5.1 Adapter interface (`contracts/adapter.md`)
```python
def run_adapter(img_dir: Path, out_dir: Path, *,
                platform: Literal["linux-rocm", "windows-hip"],
                config: AdapterConfig) -> RunSummary:
    """Write out_dir/<image_stem>.md (UTF-8) for every page image in img_dir."""
```
- `platform` is an explicit arg (adapter branches on platform-specific serving: vLLM/ROCm on
  Linux, llama.cpp/HIP-GGUF or vLLM-rocm-win on Windows).
- `config: AdapterConfig` is loaded from `adapter/adapter_config.py` with `.env.local` overrides
  (weights paths, server_url, backend, api_model_name).
- Returns standardized `RunSummary` (count/ok/fail/fallback/limit_pages/per-page status) →
  written as `_run_stats.json`.
- **Iron rules:** engine never imports adapter (filesystem-decoupled); per-page failure caught
  + logged → missing page scores zero, run continues; output `out_dir/<image-basename-no-ext>.md`.
- Backend-agnostic: adapter may call any inference backend. Template gives recommended backends
  per model-type.
- Output conventions for scoring: formulas as LaTeX `$...$`/`$$...$$`; tables as HTML/LaTeX/pipe
  (OmniDocBench matcher normalizes all three); reading order = document order.

### 5.2 Artifact JSON schema (`contracts/artifact-schema.json`, `schema_version: 1`)
- `provenance.json`: `created_at_utc`, `git_commit` (platform repo + engine version), `platform`,
  `engine_version`, `model_id`, `adapter_command`, `vlm_server_url`, `api_model_name`,
  `scoring_config_path`, `dataset_manifest_path` + `revision`, `prediction_dir`, page counts,
  `metric_result_paths`, `run_summary_paths`, `run_stats_path`.
- `run_summary.json`: `save_name`, `engine`, `cdm`, `prediction_count`, ok/fail/fallback,
  `readme_metrics` {text_edit_dist, reading_order_edit_dist, table_teds_percent,
  formula_cdm_percent}, `metric_quality` {formula_cdm: {valid, reason, sample_count,
  exception_case_count}}.
- `_run_stats.json` (adapter-produced, consumed by the engine): `count`, `ok`, `fail`,
  `fallback`, `limit_pages`, per-page `stats[]` ({image, status, error, seconds, attempts}).
- `metric_result.json`: raw OmniDocBench output (passthrough; schema owned by OmniDocBench).
- `model_card.json` (new — the hub registry entry): `model_id`, `model_version`, `platforms[]`,
  `badge` (per-platform map: `{linux-rocm, windows-hip} → verified | community | community-wanted`),
  `eval_date`, `OmniDocBench_version`, `overall`, submetrics,
  `hardware` {gpu, vram, ROCm/driver version}, artifact links.

### 5.3 Repo conformance checklist (`contracts/conformance.md` + `scripts/check-conformance.py`)
A per-model repo is conformant iff:
- Has `adapter/run_adapter.py` implementing the contract (signature + output convention).
- Has `eval/configs/omnidocbench_v16.yaml`.
- Each declared platform has `results/omnidocbench/v16/<platform>/` with the full artifact bundle.
- Has `README.md` + `README.zh-CN.md` with required sections (per-platform install, demo, eval
  results table, reproducibility, known gaps).
- Has `examples/` with a working demo (≥1 image + run command).
- `pyproject.toml` depends on a pinned `omnidocbench-amd`.
- CI runs `check-conformance` + a smoke infer on a tiny subset.

`check-conformance.py` exits 0/1 with a report; used in CI and before awarding `verified`.

### 5.4 Badge / trust policy (`contracts/badge-policy.md`)
- `community`: provenance-complete (all artifacts present + valid + reproducible commands
  documented) + passes `check-conformance`. Self-attested. **Per-platform** — a contributor with
  only Linux may submit `community` for `linux-rocm` only; `windows-hip` shows `community-wanted`.
- `verified`: maintainer has reproduced eval on maintainer hardware on **both claimed platforms**
  (Docker path) from the published commands, signed off via a `VERIFIED.yaml` (who/when/hardware/
  reproduced-commit).
- Promotion: `community` → `verified` via a maintainer PR adding the verification record.
- Invalid CDM (all-exception) → CDM shown as `pending`/null; badge not blocked but flagged.

---

## 6. Shared Dual-Platform Eval Engine (sub-project 2)

### 6.1 Ownership split
- **Engine owns:** dataset download (v1.6 manifest + 1651 images), scoring (`pdf_validation.py`),
  dual-platform CDM provisioning, artifact generation, 4-stage orchestration.
- **Adapter owns:** inference only (img_dir → .md).
- Engine invokes the adapter as a **subprocess** (never imports it); consumes `.md` + `_run_stats.json`.

### 6.2 Four stages (`engine/omnidocbench_amd/stages.py`, from `run_eval.py`, each gated)
```
download ──► infer ──► score ──► publish
 (HF)      (adapter subprocess) (OmniDocBench) (assemble model_card + conformance)
```
- `download`: fetch v1.6 manifest + images to `data/omnidocbench/v16/`; **revision pinned**
  (current default `latest`+warn becomes enforced pin for reproducibility).
- `infer`: ping inference server first (clear exit if unreachable); invoke adapter subprocess;
  per-page failures caught → zero, continue.
- `score`: run `pdf_validation.py` inside the **eval-venv** (this is the existing `eval` stage,
  renamed); config→save_name→result mapping deterministic; `_cdm` suffix prevents clobbering.
- `publish`: assemble `model_card.json` + run `check-conformance.py`; emit badge suggestion.

### 6.3 Two backends
| Concern | `linux-rocm` | `windows-hip` |
|---|---|---|
| CDM toolchain | native apt: texlive-full + IM7 + gs + node | absorbed from omnidocbench-amd-windows: `windows-cdm.patch` + native TeX Live, or WSL fallback |
| OmniDocBench checkout | native git clone (pin commit) | native or WSL |
| Scoring script | `score.sh` | `score.ps1` / `score-cdm.sh` |
| eval-venv | Python 3.11 (apt/uv) | Python 3.11 (winget/uv) |

### 6.4 Python version split (critical)
OmniDocBench scoring breaks on 3.12. Design: engine provisions a separate **eval-venv (3.11)**;
`infer` runs in the model's inference venv (may be 3.12); `score` runs in eval-venv. `stages.py`
is a thin shim dispatching subprocesses to the correct venv. Resolves the
Unlimited-OCR-ROCm (3.12) vs OmniDocBench (3.11) conflict.

### 6.5 CDM ownership (highest value)
Engine **exclusively** owns CDM provisioning so contributors don't each fight the 20+ debug sessions.
- `engine/cdm/setup-linux.sh` (idempotent apt) + `setup.ps1`/`setup.sh` (Windows, absorbed from
  `omnidocbench-amd-windows/eval-infra/02-cdm-environment`).
- **Docker reproducible path:** `ghcr.io/zeng-weijun/omnidocbench-eval:repro-ubuntu2204` (already
  referenced) — `score` can opt-in to run inside it on both platforms (Docker Desktop on Windows,
  native Docker on Linux). **Recommended for `verified` runs** to maximize reproducibility.
- CDM is opt-in via `score --cdm`; contributors can run Edit_dist + TEDS only (no `--cdm`) for a
  first pass, defer CDM.

### 6.6 Engine CLI
```
omnidocbench-amd cdm setup   --platform linux-rocm|windows-hip
omnidocbench-amd dataset download --version v16
omnidocbench-amd infer  --adapter <path> --platform ... --version v16
omnidocbench-amd score  --platform ... --predictions-dir ... [--cdm] [--docker]
omnidocbench-amd publish --model-card ...
omnidocbench-amd run --stage all ...
```
Python orchestration is a pip package; CDM scripts ship as package data (also available via
`git clone` of the platform repo).

### 6.7 Absorption map for `omnidocbench-amd-windows` (migration in sub-project 4; mapping fixed here)
| Existing | Destination |
|---|---|
| `eval-infra/01..04` | `engine/backends/windows_hip/` + shared `engine/cdm/` + shared scoring |
| `adapters/_template/` | upgraded to `template/` (cookiecutter) |
| `adapters/paddleocr-vl-1.6/` | merged into `PaddleOCR-VL-ROCm` repo's `adapter/` |
| `docs/pitfalls.md`, `architecture.md` | platform repo `docs/` |
| the repo itself | archived + redirect to `omnidocbench-amd` + `PaddleOCR-VL-ROCm` |

---

## 7. Per-Model Repo Template (sub-project 3)

Cookiecutter `template/` generates a conformant `<Model>-AMD` repo (structure in §4).

- **`Makefile` is the contributor's main interface:** `make demo`, `make eval-linux`,
  `make eval-windows`, `make publish`, `make setup-linux`, `make setup-windows`. Hides engine
  complexity — contributors mostly type `make`.
- **Dual-platform paired scripts** `.sh`/`.ps1`, same numbered steps, idempotent, `.env.local` for
  machine paths, `mirrors.env`-aware (China firewall, carried from omnidocbench-amd-windows).
- **`run_adapter.py` ships a `--backend smoke`** so CI smoke works without a GPU (outputs a
  placeholder `.md`); real inference replaces the stub body.
- **Recommended backends per model-type** (`docs/backends.md`, with the 3 reference models as
  worked examples). Per-platform ONNX execution provider: **Linux/ROCm → `onnxruntime-rocm` (ROCm EP)**; **Windows/Strix Halo → `onnxruntime-directml` (DirectML EP, `DmlExecutionProvider`)** per [AMD Ryzen AI GPU docs](https://ryzenai.docs.amd.com/en/latest/gpu/ryzenai_gpu.html) (Microsoft Olive for ONNX conversion/optimization on Windows). VLM serving: Linux → vLLM/ROCm; Windows → llama.cpp/GGUF (HIP or Vulkan). So: pure VLM → vLLM (Linux) / llama.cpp-GGUF (Windows); layout+VLM → ONNX (`onnxruntime-rocm` | `onnxruntime-directml`) + VLM server; pipeline (MinerU2.5) → MinerU pipeline adapted per platform.

---

## 8. Contributor Flow (`docs/contribute-a-model.md` + `.zh-CN.md`)

```
1 Propose    open issue "I want to add model X" → maintainer confirms open-source + in scope + not duplicate
2 Scaffold   cookiecutter gh:AIwork4me/omnidocbench-amd template → push to contributor fork
3 Provision  make setup-linux / make setup-windows (idempotent; weights, server, CDM via engine)
4 Implement  edit adapter/run_adapter.py (replace inference body; keep signature + .md convention; .env.local for paths)
5 Demo       make demo → verify one image produces sane Markdown
6 Eval       make eval-linux / make eval-windows → full 1651-page run, produces results/.../<platform>/ bundle
7 Publish    make publish → model_card.json + check-conformance.py; fix conformance failures
8 Submit     PR to hub/registry.yaml (badge=community + repo link); CI runs check-conformance
9 Verified   (optional) maintainer reproduces both platforms (Docker) → PR adds VERIFIED.yaml → badge=verified
```

Guide includes: prerequisites checklist (AMD GPUs that work, OS, disk, network/mirrors, Python
versions); per-step time budget; common pitfalls → `docs/pitfalls.md`; the "I only have one
platform" path; where to ask for help.

**Bilingual + friendliness:** README EN/CN side-by-side; CN **optimized not translated** (mirror
instructions first, ModelScope etc. called out); CONTRIBUTING.md (code style, conventional commits
+ PR numbering per existing convention, DCO/CLA); a "good first model" list to lower the barrier.

---

## 9. Robustness (cross-cutting rules)

- **Per-page failure isolation:** adapter catches per-page errors → `_run_stats.json` → missing
  page scores zero, run continues.
- **Stage gating:** each stage validates prerequisites (server reachable, checkout present, CDM
  ready, eval-venv Python correct); clear exit message, no crash.
- **Idempotent provisioning:** every `setup.*` self-checks; re-run is no-op or resumes.
- **CDM validity enforcement:** `metric_quality.formula_cdm.valid`; all-exception → CDM
  `pending`/null, never a faked number; `publish` refuses invalid CDM.
- **Provenance completeness:** `publish`/`check-conformance` verify required fields; incomplete →
  no badge.
- **Full-set enforcement:** refuse to publish official evidence from `limit_pages != null` subsets.
- **Reproducibility:** dataset revision pinned; platform + engine git_commit recorded;
  adapter_command + scoring_config recorded.
- **Determinism:** config→save_name→result mapping; `_cdm` suffix prevents clobbering.

---

## 10. Testing (layered; honest about CI reality)

- **Contract tests** (platform CI, CPU-only): fake adapter writes known `.md` → engine scores →
  assert schema valid + scores match; schema fixture positive/negative cases; model_card
  generate→validate round-trip.
- **Template smoke** (CPU-only): cookiecutter render → `make demo --backend smoke` →
  `check-conformance` passes on structure.
- **Engine self-test** (per platform, GPU, lightweight): 10-page subset end-to-end on linux-rocm
  (this env) + windows-hip (maintainer machine); assert non-zero scores + valid artifacts. Not in
  CI; maintainer-run pre-release.
- **Reference-model regression:** 3 models each pin a `results/` baseline; Overall drift > 0.1
  points triggers review. Maintainer-run.
- **CDM validity test:** small formula subset on both platforms must produce non-null valid CDM.
- **CI reality** (`docs/ci-reality.md`): GitHub Actions has no native AMD GPU runner → CI is
  CPU-only (contract/template/schema/smoke); GPU tests are maintainer-run, `--gpu`-marked. This
  matches the tiered-badge trust model.

---

## 11. Rollout / Build Order (→ writing-plans)

1. Stand up platform repo `omnidocbench-amd` skeleton (contracts/ + engine package skeleton +
   template skeleton + hub/registry skeleton + docs). Move this spec into it.
2. Port engine core: `stages.py` + `artifact_utils.py` (← PaddleOCR-VL-ROCm/eval);
   `backends/windows_hip.py` + CDM scripts (← omnidocbench-amd-windows/eval-infra); new
   `backends/linux_rocm.py` + Linux CDM setup.
3. Build cookiecutter template + `check-conformance.py` + `Makefile` interface + `model_card.json`
   schema.
4. Validate end-to-end against **PaddleOCR-VL** (most complete existing dual-platform repo) on
   both platforms — proves contracts + engine + template.
5. Contributor guide + bilingual docs + hub registry generator + badge logic.
6. (Stretch, → sub-project 4) validate against Unlimited-OCR (needs Windows path) + MinerU2.5
   (new, pipeline type) to prove generality.

---

## 12. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| vLLM-rocm-windows unstable for Unlimited-OCR | llama.cpp/HIP-GGUF fallback (proven for PaddleOCR-VL); per-model recommended backend in `docs/backends.md` |
| CDM env drift (TeX Live / IM7 versions) | pinned Docker image as the `verified` path; native paths best-effort + pitfalls KB |
| Two backends diverge | shared `stages.py`/`artifact_utils.py` core; backends differ only in platform subprocess invocation |
| Contributor friction on CDM | engine owns CDM + Docker path; `--no-cdm` first pass (Edit_dist + TEDS), CDM later |
| GitHub Actions no AMD GPU | CI CPU-only; GPU tests maintainer-run; trust via tiered badges not CI |

---

## 13. Out of Scope (explicit)

- Hub site visual design/polish (sub-project 1).
- Migrating the 3 existing repos fully + onboarding them (sub-project 4).
- Scaling beyond the 3 v1 models (sub-project 5).
- Closed-source models (never).

---

## 14. Open Follow-ups (for later specs / implementation)

- Exact open-source model list beyond v1's 3 (confirm open-weight status of DeepSeek-OCR,
  FireRed-OCR, OCRverse, OpenDoc, DotsOCR, Logics-Parsing, Qwen3-VL-235B before sub-project 5).
- Unlimited-OCR Windows backend choice (vLLM-rocm-win vs llama.cpp/GGUF quant) — decided during
  sub-project 4 onboarding with a real Strix Halo box.
- Hub site generator choice (mkdocs-material vs docusaurus) — sub-project 1.
- DCO/CLA requirement for contributions — confirm with maintainer before CONTRIBUTING.md finalize.
