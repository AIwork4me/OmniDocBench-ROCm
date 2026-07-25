# Zone discoverability + reproducibility surface

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every community-badged model repo a standard `reproduce.md` + `REPRO.yaml` surface, auto-generate the hub comparison table from `registry.yaml`, and restructure the platform README with a hero section so a developer or AI agent can discover and reproduce any model's results in a single paste.

**Architecture:** Platform repo defines the contract (`contracts/discovery.md` + template), model repos follow it. Comparison table is auto-rendered from `registry.yaml` and embedded in README. Reproduce.md uses YAML frontmatter for agent parsing + Markdown body for human reading.

**Tech Stack:** YAML, Markdown, Python (existing `omnidocbench_rocm.registry`), shell, GitHub Actions (CI).

## Global Constraints

- `reproduce.md` frontmatter MUST use `model_id`, `backend`, `hardware.gpu`, `environment.type`, `command`, `expected_overall.value` as required fields
- `REPRO.yaml` MUST carry `schema_version: 1` and all 12 required fields from the spec
- Comparison table in README MUST be auto-generated via `python scripts/generate_registry.py hub/registry.yaml` — no hand-edited rows
- CI MUST validate table-readme-consistency (fail on drift)
- Legacy `reproducibility.lock.yaml` files are renamed to `REPRO.yaml`, not deleted
- Per-model repos commit to their own `main`; the platform repo commits to `main`

---

### Task 1: Platform — discovery contract

**Files:**
- Create: `contracts/discovery.md`

**Interfaces:**
- Produces: `contracts/discovery.md` — single file documenting 7 conventions: root-level files, `reproduce.md` frontmatter schema, `REPRO.yaml` schema, results bundle pattern, multi-model rule, agent priority, legacy fallback chain. All subsequent tasks reference this.

- [ ] **Step 1: Write `contracts/discovery.md`**

Write `contracts/discovery.md` with these 7 sections:

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add contracts/discovery.md
git commit -m "docs(discovery): agent-readable model repo surface contract

Defines 7 conventions: root files, reproduce.md frontmatter, REPRO.yaml schema,
bundle location, multi-model repos, agent priority, legacy fallback."
```

---

### Task 2: Platform — README hero restructure + auto-generated comparison table

**Files:**
- Modify: `README.md` — full restructure
- Reference: `scripts/generate_registry.py` — already exists, no code change
- Reference: `engine/omnidocbench_rocm/registry.py` — `render_hub()` already exists

**Interfaces:**
- Consumes: `contracts/discovery.md` (references it)
- Consumes: `hub/registry.yaml` (auto-renders from it)
- Produces: `README.md` with hero section + auto-generated hub comparison + quickstart

- [ ] **Step 1: Write replacement README.md**

Write `README.md` with 3-zone structure. The comparison table section uses `<!-- registry-table -->` comment markers that `scripts/generate_registry.py` can replace (to be wired in Task 3):

```markdown
# OmniDocBench-ROCm

> The trusted comparison of document-parsing models on AMD ROCm.
> Benchmarked on real AMD GPUs. Reproducible. Open.

[![Models](https://img.shields.io/badge/models-4-blue)](#)
[![Linux ROCm](https://img.shields.io/badge/platform-linux--rocm-ED1C24)](#)
[![Windows HIP](https://img.shields.io/badge/platform-windows--hip-ED1C24)](#)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

---

<!-- registry-table -->
<!-- generated by scripts/generate_registry.py -- do not edit manually -->

## Flagship comparison (verified)

*No models have reached `verified` tier yet. Community-evaluated models below.*

## Community (also evaluated)

| Model | Repo | License | linux-rocm | windows-hip |
|---|---|---|---|---|
| `paddleocr-vl-1.6` | AIwork4me/PaddleOCR-VL-ROCm | MIT | community (95.77) | community (95.77) |
| `mineru2.5` | AIwork4me/MinerU-ROCm | MinerU Open Source License | community (95.56) | community (95.46) |
| `hunyuan-ocr` | AIwork4me/HunyuanOCR-ROCm | Tencent Hunyuan Community License | community (93.64) | community-wanted |

## Incoming (community-wanted)

| Model | Repo | License | linux-rocm | windows-hip |
|---|---|---|---|---|
| `unlimited-ocr` | AIwork4me/Unlimited-OCR-ROCm | MIT | community-wanted | community-wanted |

<!-- /registry-table -->

## Quickstart — Reproduce a Published Score

Pick any community model and run its adapter. Full dataset (1,651 pages, CDM scoring,
~40 minutes on AMD gfx1100):

```bash
pip install omnidocbench-rocm

omnidocbench-rocm run --stage all \
  --platform linux-rocm --version v16 --revision 2b161d0 \
  --adapter adapter/run_adapter.py --model-id hunyuan-ocr \
  --backend vllm --server-url http://127.0.0.1:10000/v1 \
  --cdm \
  --git-commit $(git rev-parse HEAD) \
  --results-dir results/omnidocbench/v16/linux-rocm
```

For a paste-and-run experience with exact docker images, see each model's
[`reproduce.md`](#per-model-repos) (`contracts/discovery.md`).

## Trust

No AMD GPU in CI ([`docs/ci-reality.md`](docs/ci-reality.md)). Trust comes from
the badge you see next to every score:

| Badge | What it means |
|---|---|
| `community` | Provenance-complete, conformant, self-attested. Real if you trust the contributor. |
| `verified` | Maintainer reproduced in pinned Docker within ±0.5. The one to trust for cross-model comparison. |
| `community-wanted` | Adaptable, no committed result on this platform yet. |

**Overall formula:** `mean(1 - text_edit_dist, table_teds / 100, formula_cdm / 100)`.
Reading-order EditDist is reported separately. All numbers produced on
**AMD gfx1100** (Radeon 7900 XTX / PRO W7900).

Full policy: [`contracts/badge-policy.md`](contracts/badge-policy.md).

## Why OmniDocBench-ROCm

- **Comparable.** Filesystem-decoupled adapter contract — every model scored through the same pipeline.
- **Honest.** Tiered badges, not fake green checks. You know what you're trusting.
- **ROCm-first.** A community taking AMD GPUs seriously for document AI.

## Per-Model Repos

Each community-badged model lives in its own repo with:

| File | Use |
|---|---|
| `reproduce.md` | Paste-and-run reproduction (human) + YAML frontmatter (agent) |
| `REPRO.yaml` | Machine-verifiable lockfile (SHA-locked weights, env, commands) |
| `model_card.json` | Published score, badge, artifact links |
| `results/` | Full evidence bundle (provenance, run_summary, metric, prediction manifest) |

Agents: read [`contracts/discovery.md`](contracts/discovery.md) for the contract.

| Model | Repo | Score |
|---|---|---|
| PaddleOCR-VL 1.6 | [PaddleOCR-VL-ROCm](https://github.com/AIwork4me/PaddleOCR-VL-ROCm) | 95.77 |
| MinerU2.5-Pro | [MinerU-ROCm](https://github.com/AIwork4me/MinerU-ROCm) | 95.56 |
| HunyuanOCR 1.5 | [HunyuanOCR-ROCm](https://github.com/AIwork4me/HunyuanOCR-ROCm) | 93.64 |

## Add a Model

[`docs/contribute-a-model.md`](docs/contribute-a-model.md). One-liner:

```bash
cookiecutter https://github.com/AIwork4me/OmniDocBench-ROCm.git --directory template
```

## Architecture

This repo holds the shared engine, contracts, template, and registry.
Each model lives in its own repo. The engine invokes adapters as subprocesses
— never imports them. [`docs/architecture.md`](docs/architecture.md).

## Repo Map

```
contracts/   adapter interface, artifact schema, badge policy, backend policy, discovery
engine/      pip-installable omnidocbench-rocm eval engine
template/    cookiecutter for per-model repos
hub/         registry.yaml — comparison table source of truth
docs/        contribute-a-model, architecture, pitfalls, ci-reality, governance, roadmap
```

## Roadmap / Contributing

- Near-term: onboard `unlimited-ocr`, host a hub site, Windows-HIP backend
- Medium-term: GPU CI, `verified` tier promotion
- Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md) — `pytest -q` green, `check_brand.py` clean
- Governance: [`docs/governance.md`](docs/governance.md)
- License: Apache-2.0 ([`LICENSE`](LICENSE))
```

- [ ] **Step 2: Verify the comparison table renders correctly**

```bash
python scripts/generate_registry.py hub/registry.yaml
```

Expected: output matches the `<!-- registry-table -->` section above.

- [ ] **Step 3: Run brand check**

```bash
python scripts/check_brand.py
```

Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): hero restructure + auto-generated comparison table

New 3-zone layout: Hero (comparison table, quickstart), Trust (badge tiers,
formula, hardware), Action (add-a-model, per-model repos). Table auto-generated
from hub/registry.yaml via generate_registry.py."
```

---

### Task 3: Platform — README.zh-CN sync

**Files:**
- Modify: `README.zh-CN.md`

**Interfaces:**
- Consumes: `README.md` (mirrors key sections)

- [ ] **Step 1: Write README.zh-CN.md**

Synchronize to match the new README structure. Translate hero, comparison table (auto-generated), quickstart, trust section. Keep all links pointing to English docs (they are the canonical reference).

```markdown
# OmniDocBench-ROCm

> AMD ROCm 上的文档解析模型可信比较。真实 AMD GPU 实测。可复现。开源。

---

<!-- registry-table-zh -->
<!-- generated by scripts/generate_registry.py -- do not edit manually -->

## 旗舰对比（verified 级）

*尚无模型达到 verified 级别。以下为社区评测模型。*

## 社区（community 级）

| 模型 | 仓库 | 许可 | linux-rocm | windows-hip |
|---|---|---|---|---|
| `paddleocr-vl-1.6` | AIwork4me/PaddleOCR-VL-ROCm | MIT | community (95.77) | community (95.77) |
| `mineru2.5` | AIwork4me/MinerU-ROCm | MinerU Open Source License | community (95.56) | community (95.46) |
| `hunyuan-ocr` | AIwork4me/HunyuanOCR-ROCm | Tencent Hunyuan Community License | community (93.64) | community-wanted |

## 待加入（community-wanted 级）

| 模型 | 仓库 | 许可 | linux-rocm | windows-hip |
|---|---|---|---|---|
| `unlimited-ocr` | AIwork4me/Unlimited-OCR-ROCm | MIT | community-wanted | community-wanted |

<!-- /registry-table-zh -->

## 快速开始

```bash
pip install omnidocbench-rocm

omnidocbench-rocm run --stage all \
  --platform linux-rocm --version v16 --revision 2b161d0 \
  --adapter adapter/run_adapter.py --model-id hunyuan-ocr \
  --backend vllm --server-url http://127.0.0.1:10000/v1 \
  --cdm \
  --git-commit $(git rev-parse HEAD) \
  --results-dir results/omnidocbench/v16/linux-rocm
```

## 信任模型

CI 无 AMD GPU。信任来源于每项评分旁的 Badge：

| Badge | 含义 |
|---|---|
| `community` | 来源完整、合约合规、自证。如果你信任贡献者则为真。 |
| `verified` | 维护者在锁定 Docker 环境中复现，偏差 ≤0.5。跨模型对比的可信来源。 |
| `community-wanted` | 可适配，尚未有提交结果。 |

**Overall 公式：** `均值(1 - text_edit_dist, table_teds / 100, formula_cdm / 100)`。
Reading-order EditDist 单独报告。所有数据在 **AMD gfx1100** (Radeon 7900 XTX / PRO W7900) 上产生。

详见：[`contracts/badge-policy.md`](contracts/badge-policy.md)（英文）

## 模型仓库

| 模型 | 仓库 | 分数 |
|---|---|---|
| PaddleOCR-VL 1.6 | [PaddleOCR-VL-ROCm](https://github.com/AIwork4me/PaddleOCR-VL-ROCm) | 95.77 |
| MinerU2.5-Pro | [MinerU-ROCm](https://github.com/AIwork4me/MinerU-ROCm) | 95.56 |
| HunyuanOCR 1.5 | [HunyuanOCR-ROCm](https://github.com/AIwork4me/HunyuanOCR-ROCm) | 93.64 |

## 添加模型

```bash
cookiecutter https://github.com/AIwork4me/OmniDocBench-ROCm.git --directory template
```

详见：[`docs/contribute-a-model.md`](docs/contribute-a-model.md)（英文）

## 许可证

Apache-2.0 ([`LICENSE`](LICENSE))
```

- [ ] **Step 2: Commit**

```bash
git add README.zh-CN.md
git commit -m "docs(readme-zh): sync Chinese README with hero restructure"
```

---

### Task 4: Platform — auto-generated table CI enforcement

**Files:**
- Modify: `.github/workflows/ci.yml` — add table-drift check

**Interfaces:**
- Consumes: `scripts/generate_registry.py`, `hub/registry.yaml`, `README.md`

- [ ] **Step 1: Add CI step for table-readme drift detection**

In `.github/workflows/ci.yml`, after the existing test step, add:

```yaml
      - name: Check comparison table matches registry
        run: |
          python scripts/generate_registry.py hub/registry.yaml > /tmp/current-table.md
          # Extract the auto-generated section from README
          sed -n '/<!-- registry-table -->/,/<!-- \/registry-table -->/p' README.md > /tmp/readme-table.md
          if ! diff /tmp/current-table.md /tmp/readme-table.md; then
            echo "ERROR: README comparison table is stale."
            echo "Run: python scripts/generate_registry.py hub/registry.yaml"
            echo "Then update the <!-- registry-table --> section of README.md."
            exit 1
          fi
          echo "Comparison table up to date ✓"
```

- [ ] **Step 2: Run CI locally to verify**

```bash
python scripts/generate_registry.py hub/registry.yaml > /tmp/current-table.md
sed -n '/<!-- registry-table -->/,/<!-- \/registry-table -->/p' README.md > /tmp/readme-table.md
diff /tmp/current-table.md /tmp/readme-table.md
```

Expected: no differences. If diff shows the generated output format is different from what's embedded in README, update the README section.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml README.md
git commit -m "ci: enforce comparison table matches registry.yaml

Adds CI step that diffs generated table against README section.
Fail on drift — table must be regenerated after registry changes."
```

---

### Task 5: Platform — template update (reproduce.md + REPRO.yaml)

**Files:**
- Create: `template/{{cookiecutter.repo_name}}/reproduce.md` (with frontmatter)
- Create: `template/{{cookiecutter.repo_name}}/REPRO.yaml` (with stubs)
- Delete: `template/{{cookiecutter.repo_name}}/REPRO.yaml` if old one exists
- Modify: `template/cookiecutter.json` — add reproduce fields

**Interfaces:**
- Consumes: `contracts/discovery.md` (follows sections 2, 3)
- Produces: `reproduce.md` + `REPRO.yaml` as cookiecutter output

- [ ] **Step 1: Check current template state**

```bash
ls template/{{cookiecutter.repo_name}}/REPRO.yaml template/{{cookiecutter.repo_name}}/reproduce.md 2>&1
```

- [ ] **Step 2: Write `template/{{cookiecutter.repo_name}}/reproduce.md`**

```markdown
---
model_id: "{{ cookiecutter.model_id }}"
backend: "{{ cookiecutter.backend if cookiecutter.backend is defined else 'TODO' }}"
hardware:
  gpu: "{{ cookiecutter.gpu if cookiecutter.gpu is defined else 'AMD gfx' }}"
environment:
  type: "{{ cookiecutter.env_type if cookiecutter.env_type is defined else 'docker' }}"
command: |
  # TODO: fill in your reproduction command
expected_overall:
  value: 0.0
---

# Reproduce {{ cookiecutter.model_id }} on AMD ROCm

## Prerequisites

1. `rocminfo` outputs GPU info: `rocminfo | grep -E "Name:|VRAM"`
2. `/dev/kfd` accessible: `ls -la /dev/kfd`
3. VRAM >= minimum required (see environment)

## Quickstart

TODO: fill in the paste-and-run command for your model.

```bash
# TODO: docker run or venv command
```

## Expected output

Overall **TODO** (±0.5 tolerance). Full run takes ~TODO.

## If it fails

See [OmniDocBench-ROCm pitfalls](https://github.com/AIwork4me/OmniDocBench-ROCm/docs/pitfalls.md).
```

- [ ] **Step 3: Write `template/{{cookiecutter.repo_name}}/REPRO.yaml`**

```yaml
# REPRO.yaml — machine-verifiable reproduction lockfile.
# schema_version: 1
# Fill in all TODO fields after scoring your model and publishing evidence.

schema_version: 1
model_id: "{{ cookiecutter.model_id }}"
platform: "TODO"
backend: "TODO"
overall: 0.0
tolerance: 0.5
command: "TODO"
weights:
  model: "TODO"
  revision: "TODO"
  sha256: "TODO"
environment:
  type: "TODO"
  image: "TODO"
  rocm: "TODO"
hardware:
  gpu: "TODO"
  vram_mb: 0
dataset:
  name: "OmniDocBench"
  version: "v1.6"
  revision: "2b161d0"
  gt_sha256: "a45cd84b04ad8b793e775089640e6b681209abea33ead54c1828ddca35fae496"
git_commit: "TODO"
```

- [ ] **Step 4: Wire cookiecutter variables**

Add to `template/cookiecutter.json` the reproduce-specific variables:

```json
"backend": "TODO",
"gpu": "AMD gfx",
"env_type": "docker"
```

- [ ] **Step 5: Verify cookiecutter renders**

```bash
pip install cookiecutter -q
cookiecutter --no-input . --directory template --checkout $(git branch --show-current) -o /tmp/test-template model_id=test-model repo_name=TestModel-ROCm model_slug=test-model model_version=0.1.0 license=MIT backend=vllm gpu="AMD gfx1100" env_type=docker
cat /tmp/test-template/TestModel-ROCm/reproduce.md
cat /tmp/test-template/TestModel-ROCm/REPRO.yaml
```

- [ ] **Step 6: Commit**

```bash
git add template/
git commit -m "feat(template): add reproduce.md + REPRO.yaml to cookiecutter

Template now outputs agent-readable reproduce.md with YAML frontmatter
and REPRO.yaml lockfile. Follows contracts/discovery.md conventions."
```

---

### Task 6: HunyuanOCR-ROCm — reproduce.md + rename → REPRO.yaml

**Files:**
- Create: `reproduce.md` (at repo root)
- Rename: `reproducibility.lock.yaml` → `REPRO.yaml`

**Interfaces:**
- Consumes: `contracts/discovery.md` sections 2, 3
- Consumes: existing `reproducibility.lock.yaml` for command + scores + SHA data
- Consumes: existing `model_card.json` for overall + submetrics

- [ ] **Step 1: Write `reproduce.md`**

Extract the reproduction command and scores from `reproducibility.lock.yaml` and `model_card.json`:

```bash
cd /workspace/HunyuanOCR-ROCm
```

Write `reproduce.md`:

```markdown
---
model_id: hunyuan-ocr
backend: vllm
hardware:
  gpu: "AMD gfx1100"
  vram_min_gb: 48
environment:
  type: docker
  rocm: "7.2"
command: |
  # 1. Start vLLM server:
  vllm serve tencent/HunyuanOCR --host 0.0.0.0 --port 10000 --max-model-len 32768

  # 2. Run adapter:
  python adapter/run_adapter.py \
    --platform linux-rocm --backend vllm \
    --server-url http://127.0.0.1:10000/v1 \
    --model tencent/HunyuanOCR \
    --img-dir /root/datasets/OmniDocBench_data/images \
    --out-dir /tmp/hunyuanocr-predictions

  # 3. Score + publish (via omnidocbench-rocm):
  omnidocbench-rocm run --stage score --platform linux-rocm --cdm \
    --predictions-dir /tmp/hunyuanocr-predictions \
    --run-stats /tmp/hunyuanocr-predictions/_run_stats.json --version v16
expected_overall:
  value: 93.64
  tolerance: 0.5
---

# Reproduce HunyuanOCR 93.64 on AMD ROCm

## Prerequisites

```bash
rocminfo | grep -E "Name:|VRAM"    # must show gfx1100 + ≥48 GB
ls -la /dev/kfd                     # must exist
```

## Quickstart

Full 1,651-page evaluation with CDM formula scoring.

```bash
# Start vLLM server on AMD GPU
vllm serve tencent/HunyuanOCR --host 0.0.0.0 --port 10000 --max-model-len 32768

# In another terminal, run adapter
cd /path/to/HunyuanOCR-ROCm
python adapter/run_adapter.py \
  --platform linux-rocm --backend vllm \
  --server-url http://127.0.0.1:10000/v1 \
  --model tencent/HunyuanOCR \
  --img-dir /root/datasets/OmniDocBench_data/images \
  --out-dir /tmp/hunyuanocr-predictions

# Score
omnidocbench-rocm run --stage score --platform linux-rocm --cdm \
  --predictions-dir /tmp/hunyuanocr-predictions \
  --run-stats /tmp/hunyuanocr-predictions/_run_stats.json --version v16
```

## Expected output

Overall **93.64** (±0.5). Text 95.48, Table TEDS 92.97%, Formula CDM 92.46%.

## If it fails

See [OmniDocBench-ROCm pitfalls](https://github.com/AIwork4me/OmniDocBench-ROCm/docs/pitfalls.md).
```

- [ ] **Step 2: Rename lockfile**

```bash
cd /workspace/HunyuanOCR-ROCm
git mv reproducibility.lock.yaml REPRO.yaml
```

- [ ] **Step 3: Commit**

```bash
git add reproduce.md REPRO.yaml
git commit -m "feat: add reproduce.md + rename reproducibility.lock.yaml to REPRO.yaml

Follows contracts/discovery.md conventions. reproduce.md has YAML
frontmatter for agent parsing + Markdown body for human quickstart."
```

---

### Task 7: MinerU-ROCm — reproduce.md + reproduce.pipeline.md + rename → REPRO.yaml

**Files:**
- Create: `reproduce.md` (mineru2.5 VLM)
- Create: `reproduce.pipeline.md` (mineru-pipeline)
- Rename: `reproducibility.lock.yaml` → `REPRO.yaml`
- Rename/Create: `REPRO.pipeline.yaml` from `model_card.pipeline.json` data

**Interfaces:**
- Consumes: `contracts/discovery.md` sections 2, 3, 5 (multi-model)
- Consumes: existing `reproducibility.lock.yaml` for VLM data
- Consumes: `model_card.pipeline.json`, `model_card.windows-hip.json` for pipeline data

- [ ] **Step 1: Write `reproduce.md` for mineru2.5**

```bash
cd /workspace/MinerU-ROCm
```

Write `reproduce.md`:

```markdown
---
model_id: mineru2.5
backend: vllm
hardware:
  gpu: "AMD gfx1100"
  vram_min_gb: 48
environment:
  type: docker
  rocm: "7.2"
command: |
  python -m mineru_rocm runner \
    --backend vlm-vllm --platform linux-rocm \
    --server-url http://127.0.0.1:8265/v1 --api-model-name mineru-pro \
    --img-dir /root/datasets/OmniDocBench_data/images \
    --out-dir /tmp/mineru-predictions

  omnidocbench-rocm run --stage score --platform linux-rocm --cdm \
    --predictions-dir /tmp/mineru-predictions \
    --run-stats /tmp/mineru-predictions/_run_stats.json --version v16
expected_overall:
  value: 95.56
  tolerance: 0.5
---

# Reproduce MinerU2.5-Pro VLM 95.56 on AMD ROCm

## Prerequisites

```bash
rocminfo | grep -E "Name:|VRAM"    # must show gfx1100 + ≥48 GB
ls -la /dev/kfd                     # must exist
```

## Quickstart

```bash
# Start mineru-pro server
python -m mineru_rocm serve-vlm --port 8265

# Run adapter
python -m mineru_rocm runner --backend vlm-vllm --platform linux-rocm \
  --server-url http://127.0.0.1:8265/v1 --api-model-name mineru-pro \
  --img-dir /root/datasets/OmniDocBench_data/images \
  --out-dir /tmp/mineru-predictions

# Score
omnidocbench-rocm run --stage score --platform linux-rocm --cdm \
  --predictions-dir /tmp/mineru-predictions \
  --run-stats /tmp/mineru-predictions/_run_stats.json --version v16
```

## Expected output

Overall **95.56** (±0.5). Text 96.41, Table TEDS 93.54%, Formula CDM 96.73%.

## If it fails

See [OmniDocBench-ROCm pitfalls](https://github.com/AIwork4me/OmniDocBench-ROCm/docs/pitfalls.md).
```

- [ ] **Step 2: Write `reproduce.pipeline.md` for mineru-pipeline**

```markdown
---
model_id: mineru-pipeline
backend: pipeline
hardware:
  gpu: "AMD gfx1100"
  vram_min_gb: 48
environment:
  type: venv
  rocm: "7.2"
command: |
  mineru-rocm predict pipeline \
    --platform linux-rocm --img-dir /root/datasets/OmniDocBench_data/images \
    --out-dir /tmp/mineru-pipeline-predictions

  omnidocbench-rocm run --stage score --platform linux-rocm --cdm \
    --predictions-dir /tmp/mineru-pipeline-predictions \
    --run-stats /tmp/mineru-pipeline-predictions/_run_stats.json --version v16
expected_overall:
  value: 86.48
  tolerance: 0.5
---

# Reproduce MinerU 3.4 Pipeline 86.48 on AMD ROCm

## Prerequisites

```bash
rocminfo | grep -E "Name:|VRAM"    # must show gfx1100 + ≥48 GB
ls -la /dev/kfd                     # must exist
```

## Quickstart

```bash
# Run pipeline adapter
mineru-rocm predict pipeline \
  --platform linux-rocm --img-dir /root/datasets/OmniDocBench_data/images \
  --out-dir /tmp/mineru-pipeline-predictions

# Score
omnidocbench-rocm run --stage score --platform linux-rocm --cdm \
  --predictions-dir /tmp/mineru-pipeline-predictions \
  --run-stats /tmp/mineru-pipeline-predictions/_run_stats.json --version v16
```

## Expected output

Overall **86.48** (±0.5). Text 94.31, Table TEDS 82.79%, Formula CDM ~83%.

## If it fails

See [OmniDocBench-ROCm pitfalls](https://github.com/AIwork4me/OmniDocBench-ROCm/docs/pitfalls.md).
```

- [ ] **Step 3: Rename lockfiles**

```bash
git mv reproducibility.lock.yaml REPRO.yaml
# Create REPRO.pipeline.yaml from pipeline data (if pipeline has its own lockfile data, extract it)
```

- [ ] **Step 4: Commit**

```bash
git add reproduce.md reproduce.pipeline.md REPRO.yaml REPRO.pipeline.yaml
git commit -m "feat: add reproduce.md + reproduce.pipeline.md + REPRO.yaml migration

Multi-model repo: mineru2.5 (VLM) and mineru-pipeline (supplementary).
Follows contracts/discovery.md sections 2, 3, 5."
```

---

### Task 8: PaddleOCR-VL-ROCm — reproduce.md + REPRO.yaml

**Files:**
- Create: `reproduce.md`
- Create: `REPRO.yaml`
- Reference: `model_card.json`

**Interfaces:**
- Consumes: `contracts/discovery.md` sections 2, 3
- Consumes: `model_card.json` for scores
- Consumes: `adapter/run_adapter.py` for command extraction

- [ ] **Step 1: Read existing adapter and README to extract reproduction command**

```bash
cd /workspace/PaddleOCR-VL-ROCm
cat adapter/run_adapter.py | head -30
grep -A5 "run_adapter\|eval" README.md | head -20
```

- [ ] **Step 2: Write `reproduce.md`**

```markdown
---
model_id: paddleocr-vl-1.6
backend: llama-cpp-server
hardware:
  gpu: "AMD gfx1100"
  vram_min_gb: 48
environment:
  type: docker
  rocm: "7.2"
command: |
  # 1. Start llama.cpp server with GGUF:
  llama-server -m models/paddleocr-vl-bf16.gguf \
    --mmproj models/mmproj-bf16.gguf --port 8080 --n-gpu-layers 99

  # 2. Run adapter:
  python adapter/run_adapter.py \
    --platform linux-rocm --backend llama-cpp-server \
    --server-url http://127.0.0.1:8080/v1 \
    --img-dir /root/datasets/OmniDocBench_data/images \
    --out-dir /tmp/paddleocr-predictions

  # 3. Score:
  omnidocbench-rocm run --stage score --platform linux-rocm --cdm \
    --predictions-dir /tmp/paddleocr-predictions \
    --run-stats /tmp/paddleocr-predictions/_run_stats.json --version v16
expected_overall:
  value: 95.77
  tolerance: 0.5
---

# Reproduce PaddleOCR-VL 1.6 (95.77) on AMD ROCm

## Prerequisites

```bash
rocminfo | grep -E "Name:|VRAM"    # must show gfx1100 + ≥48 GB
ls -la /dev/kfd                     # must exist
```

## Quickstart

PaddleOCR-VL uses llama.cpp GGUF with HIP backend + ONNX Runtime for layout detection.

```bash
# 1. Start llama.cpp server
llama-server -m models/paddleocr-vl-bf16.gguf \
  --mmproj models/mmproj-bf16.gguf --port 8080 --n-gpu-layers 99

# 2. Run adapter
python adapter/run_adapter.py \
  --platform linux-rocm --backend llama-cpp-server \
  --server-url http://127.0.0.1:8080/v1 \
  --img-dir /root/datasets/OmniDocBench_data/images \
  --out-dir /tmp/paddleocr-predictions

# 3. Score
omnidocbench-rocm run --stage score --platform linux-rocm --cdm \
  --predictions-dir /tmp/paddleocr-predictions \
  --run-stats /tmp/paddleocr-predictions/_run_stats.json --version v16
```

## Expected output

Overall **95.77** (±0.5). Text 96.88, Table TEDS 93.44%, Formula CDM 93.94%.

## If it fails

See [OmniDocBench-ROCm pitfalls](https://github.com/AIwork4me/OmniDocBench-ROCm/docs/pitfalls.md).
```

- [ ] **Step 3: Write `REPRO.yaml`**

```yaml
# REPRO.yaml — machine-verifiable reproduction lockfile for PaddleOCR-VL 1.6.
# schema_version: 1

schema_version: 1
model_id: paddleocr-vl-1.6
platform: linux-rocm
backend: llama-cpp-server
overall: 95.77
tolerance: 0.5
command: "python adapter/run_adapter.py --platform linux-rocm --backend llama-cpp-server --server-url http://127.0.0.1:8080/v1 --img-dir /root/datasets/OmniDocBench_data/images --out-dir /tmp/paddleocr-predictions"
weights:
  model: "PaddlePaddle/PaddleOCR-VL"
  revision: "not_recorded"
  sha256: "not_recorded"
environment:
  type: docker
  image: "not_recorded"
  rocm: "7.2"
hardware:
  gpu: "AMD gfx1100"
  vram_mb: 49152
dataset:
  name: "OmniDocBench"
  version: "v1.6"
  revision: "2b161d0"
  gt_sha256: "a45cd84b04ad8b793e775089640e6b681209abea33ead54c1828ddca35fae496"
git_commit: "not_recorded (fill from `git log -1 --format=%H` in PaddleOCR-VL-ROCm)"
```

- [ ] **Step 4: Commit**

```bash
git add reproduce.md REPRO.yaml
git commit -m "feat: add reproduce.md + REPRO.yaml

First reproduction recipe for PaddleOCR-VL 1.6. YAML frontmatter for
agent parsing + Markdown body for human quickstart. Follows
contracts/discovery.md."
```

---

### Task 9: Platform — push + merge

**Files:**
- Push: all platform commits (Tasks 1-5)
- Create PR + merge

- [ ] **Step 1: Push platform branch**

```bash
cd /workspace/omnidocbench-rocm
git push origin spec/discoverability-reproducibility
```

- [ ] **Step 2: Verify CI passes**

```bash
gh pr checks 19 --watch
```

- [ ] **Step 3: Merge PR**

```bash
gh pr merge 19 --squash --subject "feat: zone discoverability + reproducibility surface (#19)"
```

---

### Task 10: Per-model — push + merge

**Files:**
- Push: HunyuanOCR-ROCm (Task 6)
- Push: MinerU-ROCm (Task 7)
- Push: PaddleOCR-VL-ROCm (Task 8)

- [ ] **Step 1: Push HunyuanOCR-ROCm + create PR + merge**

```bash
cd /workspace/HunyuanOCR-ROCm
git checkout -b feat/reproduce-surface
git push origin feat/reproduce-surface
gh pr create --base main --head feat/reproduce-surface \
  --title "feat: add reproduce.md + REPRO.yaml" \
  --body "Adds agent-readable reproduce.md with YAML frontmatter and machine-verifiable REPRO.yaml. Renames reproducibility.lock.yaml → REPRO.yaml. Follows contracts/discovery.md."
gh pr merge --squash
git checkout main && git pull origin main
```

- [ ] **Step 2: Push MinerU-ROCm + create PR + merge**

```bash
cd /workspace/MinerU-ROCm
git checkout -b feat/reproduce-surface
git push origin feat/reproduce-surface
gh pr create --base main --head feat/reproduce-surface \
  --title "feat: add reproduce.md + reproduce.pipeline.md + REPRO.yaml" \
  --body "Multi-model repo: mineru2.5 (VLM) + mineru-pipeline (pipeline). Adds reproduce.md frontmatter for agent parsing. Renames reproducibility.lock.yaml → REPRO.yaml. Follows contracts/discovery.md."
gh pr merge --squash
git checkout main && git pull origin main
```

- [ ] **Step 3: Push PaddleOCR-VL-ROCm + create PR + merge**

```bash
cd /workspace/PaddleOCR-VL-ROCm
git checkout -b feat/reproduce-surface
git push origin feat/reproduce-surface
gh pr create --base main --head feat/reproduce-surface \
  --title "feat: add reproduce.md + REPRO.yaml" \
  --body "First reproduction recipe for PaddleOCR-VL 1.6. reproduce.md has YAML frontmatter for agent parsing + Markdown body for human quickstart. Follows contracts/discovery.md."
gh pr merge --squash
git checkout main && git pull origin main
```

---

### Task 11: Verification — end-to-end agent discovery

**Files:**
- No file changes. Verification only.

- [ ] **Step 1: Simulate agent discovery on each model repo**

```bash
# HunyuanOCR-ROCm
cd /workspace/HunyuanOCR-ROCm
echo "=== model_card.json ===" && python3 -c "import json; d=json.load(open('model_card.json')); print(d['model_id'], d['overall'])" && \
echo "=== reproduce.md ===" && python3 -c "import re,yaml; m=re.match(r'^---\n(.*?)\n---', open('reproduce.md').read(), re.DOTALL); print(yaml.safe_load(m.group(1))['command'][:80]) if m else print('NO FRONTMATTER')" && \
echo "=== REPRO.yaml ===" && python3 -c "import yaml; d=yaml.safe_load(open('REPRO.yaml')); print(d['overall'], '==', json.load(open('model_card.json'))['overall'])" 2>&1

# MinerU-ROCm (primary + pipeline)
cd /workspace/MinerU-ROCm
echo "=== model_card.json ===" && python3 -c "import json; d=json.load(open('model_card.json')); print(d['model_id'], d['overall'])" && \
echo "=== reproduce.md ===" && python3 -c "import re,yaml; m=re.match(r'^---\n(.*?)\n---', open('reproduce.md').read(), re.DOTALL); print('OK frontmatter' if m else 'NO FRONTMATTER')" && \
echo "=== reproduce.pipeline.md ===" && test -f reproduce.pipeline.md && echo "exists" && \
echo "=== REPRO.yaml ===" && test -f REPRO.yaml && echo "exists"

# PaddleOCR-VL-ROCm
cd /workspace/PaddleOCR-VL-ROCm
echo "=== model_card.json ===" && python3 -c "import json; d=json.load(open('model_card.json')); print(d['model_id'], d['overall'])" && \
echo "=== reproduce.md ===" && python3 -c "import re,yaml; m=re.match(r'^---\n(.*?)\n---', open('reproduce.md').read(), re.DOTALL); print('OK frontmatter' if m else 'NO FRONTMATTER')" && \
echo "=== REPRO.yaml ===" && test -f REPRO.yaml && echo "exists"
```

- [ ] **Step 2: Verify platform comparison table is up-to-date**

```bash
cd /workspace/omnidocbench-rocm
python scripts/generate_registry.py hub/registry.yaml | diff - <(sed -n '/<!-- registry-table -->/,/<!-- \/registry-table -->/p' README.md | grep -v '<!--')
```

- [ ] **Step 3: Report**

Expected output for each repo:
- `model_card.json`: `model_id` + `overall` found
- `reproduce.md`: YAML frontmatter parseable, `command` field present
- `REPRO.yaml`: `overall` matches `model_card.json.overall`
- Platform README: comparison table matches `registry.yaml`
