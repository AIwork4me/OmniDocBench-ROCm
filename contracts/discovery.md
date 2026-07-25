# Discovery contract

This contract defines what an AI agent (Codex, Claude Code, etc.) or a human
developer finds at the root of any **community-badged** per-model repository
in the OmniDocBench-ROCm zone. These conventions are enforced by
`omnidocbench-rocm conformance` — a repo that fails them is `NON-CONFORMANT`.

## 1. Root-level required files

Every per-model repo MUST contain these files at the repo root:

| File | Required | Purpose |
|---|---|---|
| `model_card.json` | Yes | Identity, scores, badge, artifact links |
| `reproduce.md` | Yes (community badge) | Human paste-and-run + agent frontmatter |
| `REPRO.yaml` | Yes (community badge) | Machine-verifiable lockfile |

A `community-wanted` repo MAY omit `reproduce.md` and `REPRO.yaml`.

## 2. `reproduce.md` schema

### Frontmatter (YAML)

The file begins with YAML frontmatter delimited by `---`:

```yaml
---
model_id: "<model>"
backend: "<backend>"
hardware:
  gpu: "<arch>"
  vram_min_gb: <int>                 # optional
environment:
  type: "<docker|venv|conda>"
  image: "<image>"                   # optional (required for docker)
  rocm: "<version>"                  # optional
command: |
  <full shell command>
expected_overall:
  value: <number>
  tolerance: <number>                # optional, default 0.5
---
```

**Required fields:** `model_id`, `backend`, `hardware.gpu`, `environment.type`, `command`,
`expected_overall.value`.

**Optional fields:** `hardware.vram_min_gb`, `environment.image`, `environment.rocm`,
`expected_overall.tolerance` (default 0.5).

### Body (Markdown)

The body after the closing `---` contains human-facing sections:

1. **Prerequisites** — 3 hardware checks (e.g., `rocminfo`, `/dev/kfd`, VRAM)
2. **Quickstart** — paste-and-run commands (docker or venv)
3. **Expected output** — overall ± tolerance, approximate runtime
4. **If it fails** — link to `https://github.com/AIwork4me/OmniDocBench-ROCm/docs/pitfalls.md`

## 3. `REPRO.yaml` schema

Machine-verifiable lockfile. Schema version 1.

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
| `weights` | `object` | `{model: "...", revision: "...", sha256: "..."}` |
| `environment` | `object` | `{type: "docker", image: "...", rocm: "..."}` |
| `hardware` | `object` | `{gpu: "...", vram_mb: <int>}` |
| `dataset` | `object` | `{name: "OmniDocBench", version: "v1.6", revision: "...", gt_sha256: "..."}` |
| `git_commit` | `string` | Repo commit anchoring this lockfile |

## 4. Results bundle location

The evidence bundle for a model+platform lives at:

```
results/omnidocbench/{version}/{platform}/
```

Bundle files are prefixed `{model_id}_{version}_quick_match_cdm_`:
- `_provenance.json`
- `_run_summary.json`
- `_metric_result.json`
- `_run_stats.json`
- `_prediction_manifest.json`
- `_dataset_identity.json`

Agents discover bundles by:
1. Read `model_card.json` → `platforms` array
2. For each platform, glob `results/omnidocbench/v16/{platform}/{model_id}_*_quick_match_cdm_*.json`

## 5. Multi-model repos

A repo MAY contain supplementary model cards (e.g., `model_card.pipeline.json` alongside
`model_card.json`).

- `model_card.json` = primary model (required)
- `model_card.<variant>.json` = supplementary model (optional)
- Each supplementary card at `community` badge MUST have its own `reproduce.<variant>.md`
  and `REPRO.<variant>.yaml`

## 6. Agent discovery priority

When an agent opens a model repo root:

1. Glob `model_card.json` → confirm `model_id`, `platforms`, `overall`
2. Glob `reproduce.md` → parse frontmatter → extract `command` + `expected_overall`
3. Glob `REPRO.yaml` → cross-check `overall` matches `model_card.json`
4. If bundle exists, validate `run_summary.json.readme_metrics` against `model_card.json.submetrics`

## 7. Legacy fallback chain

For repos that predate this contract:

| Priority | File | Action |
|---|---|---|
| 1 | `reproduce.md` | Use (post-upgrade path) |
| 2 | `REPRO.yaml` | Use |
| 3 | `reproducibility.lock.yaml` (legacy) | Use for verification only; warn "no human reproduce.md" |
| 4 | `README.md` | Heuristic extraction (last resort, unreliable) |

References:
- OmniDocBench-ROCm platform: `https://github.com/AIwork4me/OmniDocBench-ROCm`
- Adapter contract: `contracts/adapter.md`
- Badge policy: `contracts/badge-policy.md`
- Pitfalls knowledge base: `docs/pitfalls.md`
