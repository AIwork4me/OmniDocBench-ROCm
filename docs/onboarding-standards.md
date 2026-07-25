# Onboarding Standards — per-model repository delivery specifications

**Date:** 2026-07-25
**Status:** Canonical. Every model onboarded to OmniDocBench-ROCm MUST meet these
specifications. Enforcement is via `omnidocbench-rocm conformance` (exit 0) and
`omnidocbench-rocm validate-bundle` (exit 0).

**Scope:** All per-model repositories generated from `template/` and registered in
`hub/registry.yaml`.

**Companion docs:** [`onboarding-runbook.md`](onboarding-runbook.md) is the
procedural HOW (step-by-step commands). This document is the specification of
WHAT every repo must contain and WHAT quality gates it must pass.

---

## 1. The 7-stage onboarding flow

```
1 Scaffold → 2 Implement → 3 License Check → 4 Eval + Publish → 5 Fill Evidence → 6 Verify → 7 Register
```

| # | Stage | Deliverable | Gate |
|---|---|---|---|
| 1 | **Scaffold** | Working repo from `cookiecutter` | Directory structure exists |
| 2 | **Implement** | `adapter/run_adapter.py` + `eval/configs/omnidocbench_v16.yaml` + `examples/` + `pyproject.toml` (depends on `omnidocbench-rocm`) | Adapter runs smoke backend without GPU |
| 3 | **License Check** | Confirmed upstream license, restriction zones, commercial terms | No unresolvable license issues |
| 4 | **Eval + Publish** | Full 1,651-page inference + score + publish → 6-artifact bundle in `results/` | `omnidocbench-rocm validate-bundle` CONFORMANT |
| 5 | **Fill Evidence** | `model_card.json` + `reproduce.md` + `REPRO.yaml` + README sections + `README.zh-CN.md` | All files present and schema-valid |
| 6 | **Verify** | `conformance` + `validate-bundle` + `pytest` all green | All gates pass |
| 7 | **Register** | PR to `hub/registry.yaml` | Merged to platform `main` |

---

## 2. Root-level file checklist

`✅` = Stage 6 (Verify) enforces. `⚪` = Recommended. Both tiers listed.

| File | Tier | Enforced by | Notes |
|---|---|---|---|
| `model_card.json` | ✅ | `conformance` #8 | Schema-valid per `contracts/artifact-schema.json` `model_card` `$def` |
| `reproduce.md` | ✅ | This standard | YAML frontmatter + 4-section body (see §3) |
| `REPRO.yaml` | ✅ | This standard | Schema v1 flat lockfile (see §4) |
| `README.md` | ✅ | `conformance` #4, #5 | Contains Install, Demo, Evaluation, Reproducibility, Known Gaps |
| `README.zh-CN.md` | ✅ | `conformance` #4, #5 | Human-translated, not machine-only. Same 5 sections |
| `adapter/run_adapter.py` | ✅ | `conformance` #1 | Implements [`contracts/adapter.md`](../contracts/adapter.md) |
| `eval/configs/omnidocbench_v16.yaml` | ✅ | `conformance` #2 | Scoring config for the v1.6 dataset |
| `results/omnidocbench/v16/<platform>/` | ✅ | `conformance` #3 | Non-empty when platform declared — contains 6-artifact bundle (see §5) |
| `examples/` | ✅ | `conformance` #6 | Non-empty. Must contain `demo.png` + `run_demo.sh` |
| `pyproject.toml` | ✅ | `conformance` #7 | Must declare `omnidocbench-rocm` dependency |
| `CHANGELOG.md` | ⚪ | — | Release history |
| `CITATION.cff` | ⚪ | — | Citation metadata |
| `CODE_OF_CONDUCT.md` | ⚪ | — | |
| `CONTRIBUTING.md` | ⚪ | — | |
| `LICENSE` | ⚪ | — | Repo license file |
| `LICENSES/` | ⚪ | — | SPDX reuse compliance directory |
| `Makefile` | ⚪ | — | Common targets (`install`, `demo`, `test`) |
| `NOTICE` | ⚪ | — | Third-party notices |
| `REUSE.toml` | ⚪ | — | Reuse lint configuration |
| `SECURITY.md` | ⚪ | — | |
| `SUPPORT.md` | ⚪ | — | |
| `.github/workflows/ci.yml` | ⚪ | — | CPU-only CI: ruff, pytest, brand/conformance checks |
| `conftest.py` | ⚪ | — | Pytest root fixture |

---

## 3. `reproduce.md` — human + agent reproduction entry

### 3.1 Frontmatter (YAML)

The first bytes of the file MUST be YAML between `---` delimiters.
Agent-first design: an AI reads this block and extracts structured data
without NLP.

```yaml
---
model_id: "<model-id>"
backend: "<backend>"
hardware:
  gpu: "AMD gfx1100"
  vram_min_gb: 48
environment:
  type: "docker"
  rocm: "7.2"
command: |
  <paste-and-run shell command>
expected_overall:
  value: <number>
  tolerance: 0.5
---
```

**Required fields:** `model_id`, `backend`, `hardware.gpu`, `environment.type`,
`command`, `expected_overall.value`.

**Optional fields:** `hardware.vram_min_gb`, `environment.image`,
`environment.rocm`, `expected_overall.tolerance` — when absent, tolerance
defaults to `0.5`.

### 3.2 Body (4 sections)

Every `reproduce.md` body MUST contain exactly these 4 sections, in order:

| # | Section | Content |
|---|---|---|
| 1 | `## Prerequisites` | 3 hardware checks: `rocminfo` output shows GPU + VRAM, `/dev/kfd` accessible, VRAM ≥ minimum |
| 2 | `## Quickstart` | Copy-paste commands. Docker-first (eliminates ROCm/dependency variance). Do NOT invent novel flags — use the exact adapter CLI from §2 |
| 3 | `## Expected output` | Overall ± tolerance. Approximate runtime. CDM sample count. |
| 4 | `## If it fails` | Link to `https://github.com/AIwork4me/OmniDocBench-ROCm/docs/pitfalls.md`. Never write per-model troubleshooting inline |

---

## 4. `REPRO.yaml` — machine-verifiable lockfile

Schema version 1. Flat structure. ONE file covers ONE model on ONE platform.
For multi-model repos (primary + supplementary), use separate files
(`REPRO.yaml`, `REPRO.<variant>.yaml`).

### 4.1 Required fields

| Field | Type | Example | Description |
|---|---|---|---|
| `schema_version` | `int` | `1` | |
| `model_id` | `string` | `"glm-ocr"` | Matches `model_card.json.model_id` |
| `platform` | `string` | `"linux-rocm"` | One of `linux-rocm`, `windows-hip` |
| `backend` | `string` | `"vllm"` | Inference backend |
| `overall` | `number` | `95.22` | Published Overall score — MUST match `model_card.json.overall` |
| `tolerance` | `number` | `0.5` | Acceptable score delta |
| `command` | `string` | `"python adapter/run_adapter.py ..."` | Full reproduction command |
| `weights` | `object` | `{model: "...", revision: "...", sha256: "..."}` | Model weights identity. Use `"not_recorded"` for unknown values — never invent |
| `environment` | `object` | `{type: "docker", image: "...", rocm: "7.2"}` | Runtime environment. `image` may be `"not_recorded"` |
| `hardware` | `object` | `{gpu: "AMD gfx1100", vram_mb: 49152}` | |
| `dataset` | `object` | `{name: "OmniDocBench", version: "v1.6", revision: "2b161d0", gt_sha256: "<sha>"}` | Dataset identity |
| `git_commit` | `string` | `<sha>` | Repo commit anchoring this lockfile |

### 4.2 Style rule

New models MUST use this schema v1 flat format. Legacy detailed-style lockfiles
(100+ lines with nested benchmark sections) from existing repos can remain but
should be migrated to schema v1 over time.

---

## 5. `model_card.json` — standard fields

### 5.1 Required fields (checked by artifact schema)

| Field | Type | Notes |
|---|---|---|
| `schema_version` | `int` | `1` |
| `model_id` | `string` | Short identifier, e.g. `"glm-ocr"` |
| `model_version` | `string` | Semantic version, e.g. `"0.1.0"` |
| `platforms` | `string[]` | At minimum `["linux-rocm"]` |
| `badge` | `object` | `{"linux-rocm": "community", "windows-hip": "community-wanted"}` |
| `eval_date` | `string` | `"YYYY-MM-DD"` — date scoring ran |
| `omnidocbench_version` | `string` | `"v1.6"` |
| `overall` | `number \| null` | `null` for `community-wanted`; number for `community` |
| `submetrics` | `object` | At least 4 keys (see §5.2). `{}` for `community-wanted` |
| `hardware` | `object` | `gpu`, `vram`, `rocm_driver` at minimum |
| `artifacts` | `object` | Keys: `provenance`, `run_summary`, `metric_result`, `run_stats`, `prediction_manifest`, `dataset_identity`. Values: repo-relative paths |

### 5.2 `submetrics` standard keys

Every `community`-badged model card MUST include these 4 sub-keys:

| Key | Type | Source in `metric_result.json` |
|---|---|---|
| `text_edit_dist` | `number` | `text_block.page.Edit_dist.ALL` |
| `reading_order_edit_dist` | `number` | `reading_order.page.Edit_dist.ALL` |
| `table_teds_percent` | `number` | `table.page.TEDS.ALL * 100` |
| `formula_cdm_percent` | `number` | `display_formula.page.CDM.ALL * 100` |

Optional: `table_teds_structure_only_percent` (when available).

### 5.3 Recommended fields

| Field | Type | Notes |
|---|---|---|
| `backend` | `string` | e.g. `"vllm"`, `"llama-cpp-server"` |
| `license` | `string` | Short name, e.g. `"MIT"`, `"MinerU Open Source License"` |
| `commercial_use` | `string` | One-line summary of restrictions |
| `official_reference` | `object` | `{source: "<url>", source_overall: <number>, delta_pp: <number>}` — upstream paper/README anchor |
| `note` | `string` | Supplementary context |

---

## 6. Results bundle — `results/omnidocbench/v16/<platform>/`

### 6.1 Directory convention

```
results/omnidocbench/v16/<platform>/
  {model_id}_v16_quick_match_cdm_provenance.json
  {model_id}_v16_quick_match_cdm_run_summary.json
  {model_id}_v16_quick_match_cdm_metric_result.json
  {model_id}_v16_quick_match_cdm_run_stats.json
  {model_id}_v16_quick_match_cdm_prediction_manifest.json
  {model_id}_v16_quick_match_cdm_dataset_identity.json
```

Example: `results/omnidocbench/v16/linux-rocm/hunyuan-ocr_v16_quick_match_cdm_provenance.json`.

The `{model_id}_v16_quick_match_cdm_` prefix is produced by `omnidocbench-rocm publish`
when invoked with `--cdm`. Never rename these files — agent discovery depends on
the predictable prefix (`contracts/discovery.md` §4).

### 6.2 Scoring config

`eval/configs/omnidocbench_v16.yaml` MUST reference the same `model_id` and
Quick Match settings that produced the bundle. A copy MAY land in the bundle as
`{model_id}_v16_quick_match_cdm_scoring_config.yaml` (optional).

---

## 7. README — bilingual with 5 mandatory sections

### 7.1 English (`README.md`)

Must contain these section headers (the conformance checker matches the bare
word, so `## Install`, `## 安装 (Install)`, `### Installation` all match):

| Section | Minimum content |
|---|---|
| **Install** | `pip install` command + ROCm prerequisites |
| **Demo** | One command using `examples/run_demo.sh` or equivalent smoke test |
| **Evaluation** | `omnidocbench-rocm` command(s) to reproduce published results |
| **Reproducibility** | Hardware (GPU model + VRAM), ROCm driver version, commit hash, link to `REPRO.yaml` |
| **Known Gaps** | Limitation list: which platforms not supported, which backends not tested, any known failures |

### 7.2 Simplified Chinese (`README.zh-CN.md`)

Same 5 sections. Must be human-translated (not machine-only). The comparison
table, Overall formula, and license text require manual review — automated
translation of technical terms is unacceptable.

### 7.3 Comparison table

If the repo has ≥2 model variants (e.g., mineru2.5 + mineru-pipeline), the
**Evaluation** section MUST include a comparison table in both READMEs showing
per-variant scores. Single-model repos can omit this.

---

## 8. Adapter — `adapter/run_adapter.py`

### 8.1 CLI contract (from `contracts/adapter.md`)

| Argument | Required | Description |
|---|---|---|
| `--img-dir` | Yes | Input image directory |
| `--out-dir` | Yes | Output `.md` directory |
| `--platform` | Yes | `linux-rocm` or `windows-hip` |
| `--backend` | No | Backend identifier (e.g. `vllm`, `llama-cpp-server`) |
| `--server-url` | No | OpenAI-compatible VLM server URL |
| `--api-model-name` | No | Model name for the API request |
| `--skip-existing` | No | Resume flag — skip images whose `.md` already exists in `out-dir` |

### 8.2 Output contract (7 iron rules)

1. Per-page `.md` output with `{image_stem}.md` naming
2. `_run_stats.json` written to `--out-dir` (schema v1 per `artifact-schema.json`)
3. Single-page failures recorded in `_errors.jsonl` — never crash the entire run
4. `IMG_EXT` set: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tif`, `.tiff`
5. `PLATFORMS = ("linux-rocm", "windows-hip")`
6. `--skip-existing` respects existing `.md` files — no redundant inference
7. Adapter writes to the filesystem only — the engine consumes its output, never imports it

### 8.3 Smoke backend

Every adapter MUST implement a `smoke` backend (or equivalent no-GPU mode) that
produces at least one valid `.md` output without a GPU. This is the CI gate:
`omnidocbench-rocm infer --backend smoke` must succeed on CPU.

---

## 9. Quality gates — `Verify` stage checklist

Every model repo MUST pass ALL of these before entering the `Register` stage:

| # | Gate | Command | Required output |
|---|---|---|---|
| 1 | Conformance | `omnidocbench-rocm conformance .` | `CONFORMANT` (exit 0) |
| 2 | Bundle validation | `omnidocbench-rocm validate-bundle results/omnidocbench/v16/<platform>` | `CONFORMANT` (exit 0) |
| 3 | Lint | `ruff check .` | All checks passed |
| 4 | Format | `ruff format --check .` | No formatting changes needed |
| 5 | Tests | `pytest -q -m "not gpu"` | All green |
| 6 | Brand check | `python scripts/check_brand.py` (if available) | `brand-residue: clean` |
| 7 | Lock integrity | `python scripts/check_repo.py` (if available) | `OK: repo integrity checks passed` |

Gates 1 + 2 are mandatory. Gates 3-7 are recommended where the repo has the
tooling configured (they are in the cookiecutter template — only repos that
predate the template may lack them).

---

## 10. License checklist — run BEFORE eval

Open every model's HuggingFace model card or GitHub README and check:

| Question | Action if answer is negative |
|---|---|
| Is there a declared license on the weights? | **Block.** Do not proceed. Weights with no license (e.g. "PDF-Extract-Kit-1.0") cannot be listed. File an issue on the upstream repo requesting a license declaration |
| Is the license compatible with redistribution-for-evaluation? | Most open licenses (MIT, Apache 2.0, CC-BY, even restrictive-open like MinerU OSL) are fine. Contact maintainer if unclear |
| Are there geographic restriction zones? | Record in `model_card.json.commercial_use` and `registry.yaml`. Example: "not licensed in EU/UK/KR" for HunyuanOCR |
| Is the repo license file (`LICENSE`) consistent with the upstream weights license? | If they differ, add a `NOTICE` file and document both licenses |

---

## 11. CI standards

### 11.1 Required CI checks (every repo MUST have)

```yaml
# Minimum CI: lint + test on CPU
- ruff check .
- ruff format --check .
- pytest -q -m "not gpu"
```

### 11.2 Recommended CI checks

```yaml
# For repos with the cookiecutter tooling:
- reuse lint                     # SPDX compliance
- python -m compileall -q src scripts
- bash -n scripts/*.sh           # shell syntax
- python scripts/check_repo.py   # lock integrity
- python scripts/check_brand.py  # brand hygiene
```

### 11.3 Platform conformance in CI

Add a job that verifies against the platform:

```yaml
- name: Platform conformance
  run: |
    pip install omnidocbench-rocm
    omnidocbench-rocm conformance .
```

This is the single most valuable CI check: it confirms the repo is
structurally valid against the zone's contract.

---

## 12. Entry bar — recommended Overall threshold

Models below the **83-point Overall threshold** are valid `community-wanted`
entries but are NOT recommended for priority onboarding unless they fill a
coverage gap (e.g., unique architecture family, unique language coverage).

| Tier | Overall | Recommendation |
|---|---|---|
| **Priority** | > 93 | Strong scores, worth immediate onboarding |
| **Standard** | 83–93 | Valid entries, onboard when bandwidth permits |
| **Coverage-only** | < 83 or non-VLM pipeline | Only onboard if they represent an architectural family not yet covered |

The threshold of 83 corresponds to the lowest-scoring open-source VLM in the
OmniDocBench v1.6 paper (POINTS-Reader at 83.37). Pipeline tools (Marker at
78.44) and pre-VLM architectures are exceptions — they may be onboarded for
coverage even below the threshold.

---

## 13. Large file policy

Files > 1 MB that are NOT model code (prediction manifests, dataset manifests,
large logs) MUST be excluded from git or stored externally:

| File | Action |
|---|---|
| `*_dataset_manifest.json` > 1MB | Exclude via `.gitignore`. Generate at eval time, reference in `model_card.json.artifacts` as external storage |
| `*_prediction_manifest.json` > 1MB | Same — git-track the SHA256 but host the file externally |
| `.md` prediction files | These are typically < 10KB each and should be committed |
| Logs (`predict.log`, `*.log`) | `.gitignore` — never commit logs |

Rationale: GitHub's HTTP proxy may reject pushes with large pack sizes (MinerU-ROCm's
41MB `dataset_manifest.json` blocked all pushes behind the proxy at `nginx/1.30.0`).
External storage (Git LFS, HuggingFace dataset repo, or S3) avoids this and
keeps clone times fast for contributors.

---

## 14. Cross-repo consistency rules

Every model repo in the OmniDocBench-ROCm zone MUST maintain these invariants:

| Rule | Check |
|---|---|
| `reproduce.md` tolerance = `0.5` | Same as all existing community models |
| All pitfalls links point to `OmniDocBench-ROCm/docs/pitfalls.md` | Never inline per-model troubleshooting |
| Overall formula: `mean(1-text_edit_dist, table_teds/100, formula_cdm/100)` | Reading order NOT included. Same as all published scores |
| Bundle naming: `{model_id}_v16_quick_match_cdm_` prefix | Enforced by engine's `publish` stage. Never rename |
| Results directory: `results/omnidocbench/v16/{platform}/` | Not flat `results/omnidocbench/v16/` |
| `REPRO.yaml` schema version `1` | Flat, not nested |

---

## References

- [Adapter contract](../contracts/adapter.md) — 7 iron rules, CLI spec, output contract
- [Conformance checklist](../contracts/conformance.md) — 8 automated checks
- [Badge policy](../contracts/badge-policy.md) — tier definitions + promotion path
- [Discovery contract](../contracts/discovery.md) — agent-readable repo surface
- [Onboarding runbook](../docs/onboarding-runbook.md) — step-by-step operational HOW
- [Contribute a model](../docs/contribute-a-model.md) — 9-step contribution guide
- [Architecture](../docs/architecture.md) — engine topology + data flow
- [Pitfalls](../docs/pitfalls.md) — 18 debugged failure modes (link here from every `reproduce.md`)
- [Artifact schema](../contracts/artifact-schema.json) — JSON Schema v1 for `model_card`, `run_stats`, `provenance`, `run_summary`, `repro_recipe`
