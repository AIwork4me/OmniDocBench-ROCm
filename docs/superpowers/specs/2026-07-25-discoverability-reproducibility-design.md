# Zone discoverability + reproducibility surface

**Date:** 2026-07-25
**Status:** Design approved. Implementation plan pending.
**Scope:** OmniDocBench-ROCm platform repo + all 4 per-model repos (MinerU-ROCm, HunyuanOCR-ROCm, PaddleOCR-VL-ROCm, Unlimited-OCR-ROCm).

---

## 1. Problem

### 1.1 Discoverability regression

A developer opening `AIwork4me/OmniDocBench-ROCm` today sees:

- **README comparison table is stale** — `hunyuan-ocr` still shows `community-wanted` even though the model was onboarded with Overall 93.64 and the registry was updated.
- **README.zh-CN.md is substantially stale** — describes the registry as "initial placeholder" and CDM as a "scaffold stub," both long outdated.
- **No clear landing experience** — no hero section, no "what is this," no quickstart. A new visitor must read 200+ lines of README to understand the project's purpose.
- **Comparison table is a manual Markdown snippet** — not auto-generated from the source of truth (`hub/registry.yaml`). Every registry update requires a manual README edit (and has fallen behind).

### 1.2 Reproducibility is invisible

Each model repo has evaluation evidence, but a developer (human or agent) cannot discover how to reproduce a result without deep exploration:

- **PaddleOCR-VL-ROCm has no reproduction recipe at all.**
- **HunyuanOCR-ROCm has `reproducibility.lock.yaml`** — machine-verifiable, but not a pasteable quickstart for a human.
- **MinerU-ROCm has `reproducibility.lock.yaml`** — same gap.
- **No per-model file tells a developer** "run this one command on your AMD GPU and you'll get the same score."
- **Agent discovery is ad hoc** — Codex / Claude Code / other agents cannot locate reproduction instructions without custom heuristics per repo.

### 1.3 Toolchain inconsistency

The cookiecutter template produces `REPRO.yaml` with all TODO stubs. The actual repos use `reproducibility.lock.yaml`. PaddleOCR-VL has neither. There is no single contract for "what a model repo's reproducible surface looks like."

---

## 2. Design

### 2.1 Principles

| Principle | Meaning |
|---|---|
| **Convention over configuration** | An agent or human knows where every file is without querying a hub — the file names and locations are the contract. |
| **One command to reproduce** | A human with an AMD GPU can paste one command and get the published score, ±0.5 tolerance. |
| **Agent-parseable first** | YAML frontmatter in human docs so agents read structured data without NLP. |
| **Graceful degradation** | Old repos without `reproduce.md` or `REPRO.yaml` are handled with a documented fallback chain, not broken. |
| **Self-contained evidence** | Every repo carries its own proof — the hub only indexes. No repo depends on another for its claims. |

### 2.2 Per-model repo surface (convention)

Each per-model repo MUST contain these files at the root level:

| File | Role | Consumer |
|---|---|---|
| `model_card.json` | Identity + scores + badge | Human, agent, platform tooling |
| `reproduce.md` | Human paste-and-run quickstart + agent frontmatter | Human first, agent second |
| `REPRO.yaml` | Machine-verifiable lockfile (SHA-locked weights, env snapshot) | Agent, CI, `omnidocbench-rocm verify` |

### 2.3 `reproduce.md` schema

#### Frontmatter (YAML, between `---` delimiters)

```yaml
---
model_id: hunyuan-ocr
backend: vllm
hardware:
  gpu: "AMD gfx1100"
  vram_min_gb: 48
environment:
  type: docker
  image: "ghcr.io/AIwork4me/hunyuan-ocr-rocm:v0.1.0"
  rocm: "7.2"
command: |
  docker run --rm -it \
    --device=/dev/kfd --device=/dev/dri \
    --group-add video ${IMAGE} \
    python adapter/run_adapter.py \
    --platform linux-rocm --backend vllm \
    --server-url http://127.0.0.1:10000/v1
expected_overall: {value: 93.64, tolerance: 0.5}
---
```

**Required frontmatter fields:** `model_id`, `backend`, `hardware.gpu`, `environment.type`, `command`, `expected_overall.value`.

**Optional frontmatter fields:** `hardware.vram_min_gb`, `environment.image`, `environment.rocm`, `expected_overall.tolerance` (defaults to 0.5).

#### Body (Markdown, human-facing)

| Section | Content |
|---|---|
| **Prerequisites** | 3 hardware checks: `rocminfo` output, `/dev/kfd` accessible, VRAM ≥ minimum |
| **Quickstart** | `git clone` → `docker run` or bare-metal venv → wait → see score |
| **Expected output** | Overall value ± tolerance |
| **If it fails** | Link to `omnidocbench-rocm/docs/pitfalls.md` |

### 2.4 `REPRO.yaml` schema

Machine-verifiable lockfile. Replaces the current ad-hoc `reproducibility.lock.yaml`.

**Required fields:**

| Field | Type | Description |
|---|---|---|
| `schema_version` | `int` | `1` |
| `model_id` | `string` | e.g. `hunyuan-ocr` |
| `platform` | `string` | `linux-rocm` or `windows-hip` |
| `backend` | `string` | e.g. `vllm` |
| `overall` | `number` | Published Overall score |
| `tolerance` | `number` | Acceptable delta (default 0.5) |
| `command` | `string` | Full reproduction command |
| `weights` | `object` | `{model: "tencent/HunyuanOCR", revision: "abc123", sha256: "..."}` |
| `environment` | `object` | `{type: "docker", image: "...", rocm: "7.2"}` |
| `hardware` | `object` | `{gpu: "AMD gfx1100", vram_mb: 49152}` |
| `dataset` | `object` | `{name: "OmniDocBench", version: "v1.6", revision: "2b161d0", gt_sha256: "..."}` |
| `git_commit` | `string` | Repo commit that produced this file |

### 2.5 Results bundle discovery convention

The evidence bundle for each model+platform resides at:

```
results/omnidocbench/{version}/{platform}/{model_id}_{version}_quick_match_cdm_*.json
```

Agents discover bundles by:
1. Read `model_card.json` → `platforms` array
2. For each platform, look in `results/omnidocbench/v16/{platform}/`
3. Match files by `{model_id}_v16_quick_match_cdm_` prefix

### 2.6 Multi-model repo convention

A repo MAY contain supplementary model cards for additional models (e.g., `model_card.pipeline.json` for `mineru-pipeline` alongside `model_card.json` for `mineru2.5`).

- `model_card.json` = primary model (required)
- `model_card.<variant>.json` = supplementary model (optional)
- Each supplementary card MUST have its own `reproduce.<variant>.md` and `REPRO.<variant>.yaml` if it claims a community badge

### 2.7 Agent discovery priority

When an agent opens a model repo root:

1. Read `model_card.json` → confirm `model_id`, `platforms`, `overall`
2. Read `reproduce.md` → extract frontmatter `command` + `expected_overall`
3. Read `REPRO.yaml` → cross-check `overall` matches `model_card.json`
4. If bundle exists, validate bundle artifacts against `model_card.json`

### 2.8 Legacy fallback chain

For repos that predate this convention (PaddleOCR-VL-ROCm, and current state of HunyuanOCR/MinerU):

| Priority | File | Action |
|---|---|---|
| 1 | `reproduce.md` | Use (post-upgrade path) |
| 2 | `REPRO.yaml` | Use |
| 3 | `reproducibility.lock.yaml` (legacy) | Use for machine-verification only; warn: "no human reproduce.md" |
| 4 | `README.md` | Heuristic extraction of benchmark commands (last resort, unreliable) |

### 2.9 Platform-level changes

#### 2.9a Auto-generated comparison table

`scripts/generate_registry.py` renders `hub/registry.yaml` into a Markdown comparison table. This table MUST be the source of truth rendered in:

- `README.md` (English)
- `README.zh-CN.md` (Simplified Chinese)
- Any future hosted Hub site

The table is generated via:

```
make registry-table   # OR: python scripts/generate_registry.py
```

Registry updates trigger re-generation. The CI validates that the rendered README table matches `registry.yaml` (otherwise CI fails).

**Table columns:**

| Column | Source |
|---|---|
| Model | `model_id` |
| Linux-ROCm | `platforms.linux-rocm.badge` + `platforms.linux-rocm.overall` |
| Windows-HIP | `platforms.windows-hip.badge` + `platforms.windows-hip.overall` |
| License | `license` |
| Commercial Use | `commercial_use` |
| Repo | `repo` (linked) |

Only models with at least one `community` or `verified` platform appear in the comparison table. `community-wanted`-only models are listed separately below as the "Incoming Lane."

#### 2.9b README hero restructure

The README is reorganized into three zones:

**Zone 1 — Hero (above fold, no scroll needed):**
- One-line project description
- Badge bar (model count × platform count × GitHub stars)
- Comparison table (auto-generated from `registry.yaml`)
- One-line best-model reproduction command

**Zone 2 — Trust (trust establishment):**
- Badge tier explanation (community-wanted → community → verified)
- Overall formula: `(1-text_edit_dist + table_teds + formula_cdm) / 3`
- Hardware anchor: all results on AMD gfx1100 (Radeon 7900 XTX / PRO W7900)

**Zone 3 — Action (call to action):**
- Quickstart: install `omnidocbench-rocm`, run a model, see results
- Contribute: link to `docs/contribute-a-model.md`

#### 2.9c New contract: `contracts/discovery.md`

Documents the 7 conventions defined in sections 2.2–2.8. This is the single file an agent reads to understand the entire model repo discovery surface.

#### 2.9d Template update

The cookiecutter template (`template/`) is updated to output:
- `reproduce.md` with valid YAML frontmatter (field stubs filled from `cookiecutter.json`)
- `REPRO.yaml` with schema v1 (field stubs)
- Removes `reproducibility.lock.yaml` from template (replaced by `REPRO.yaml`)

---

## 3. Per-model migration plan

### 3.1 HunyuanOCR-ROCm

| Action | Detail |
|---|---|
| Create `reproduce.md` | Docker command from existing `reproducibility.lock.yaml` |
| Rename `reproducibility.lock.yaml` → `REPRO.yaml` | Schema v1 migration |
| Verify agent discovery | Check frontmatter parseable |

### 3.2 MinerU-ROCm

| Action | Detail |
|---|---|
| Create `reproduce.md` | Two variants: VLM (vLLM) + pipeline (bare-metal) |
| Create `reproduce.pipeline.md` | Supplementary for mineru-pipeline |
| Rename `reproducibility.lock.yaml` → `REPRO.yaml` | Schema v1 migration, two sections for two models |
| Create `REPRO.pipeline.yaml` | Supplementary |

### 3.3 PaddleOCR-VL-ROCm

| Action | Detail |
|---|---|
| Create `reproduce.md` | Extract command from README + eval scripts |
| Create `REPRO.yaml` | Backfill from README scores, adapter config |

### 3.4 Unlimited-OCR-ROCm

| Action | Detail |
|---|---|
| Create `reproduce.md` + `REPRO.yaml` | Post-onboarding; aligned with Phase B when scoring completes |

---

## 4. Non-goals (explicitly out of scope)

- **VERIFIED tier promotion** — requires maintainer Docker reproduction on reference hardware. This spec defines the surface that makes verification possible; actually running the verification is separate.
- **Windows-HIP backend implementation** — the `windows_hip.py` backend is a separate engineering task, not part of this spec.
- **Hosted Hub site** — MkDocs or similar. The generated Markdown comparison table is the immediate deliverable; hosting is medium-term (per roadmap).
- **MkDocs site** — explicitly deferred. The auto-generated Markdown table in README is sufficient for current discoverability needs.

---

## 5. Success criteria

1. A developer pasting `omnidocbench-rocm run` from the README hero section sees a valid score within 10 minutes (smoke/partial) or 2 hours (full)
2. An agent (Codex / Claude Code) opening any community-badged model repo discovers `reproduce.md` and `REPRO.yaml` via root-level glob, without reading any other file
3. CI validates that README comparison table matches `registry.yaml` (fails on drift)
4. All 3 community-badged model entries (PaddleOCR-VL, MinerU2.5, HunyuanOCR) have both `reproduce.md` and `REPRO.yaml` at repo root
5. A developer with an AMD gfx1100 GPU can reproduce HunyuanOCR 93.64 within ±0.5 following `reproduce.md` instructions
