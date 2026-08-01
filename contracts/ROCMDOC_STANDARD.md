# ROCmDoc Standard 1.0

> AMD 文档解析适配、证据与复现标准
>
> 状态：Proposed Standard
>
> 版本：1.0.0-draft.1
>
> 日期：2026-07-31

## 1. 目的与范围

本标准为 ROCm 文档解析模型提供统一的用户体验、评测接入、结果身份、证据、品质和社区协作规则。它适用于中央评测仓及任何组织或个人维护的兼容模型仓。

中央仓 MUST 是本标准、JSON Schema、conformance profiles 和 comparison tracks 的唯一规范事实源。模型仓 MUST 锁定中央仓的不可变 commit；MUST NOT 复制并独立演化第二套中央 Schema。

本标准不要求所有模型使用相同语言、推理框架或服务协议。互操作边界是 CLI、JSON、文件系统和可验证证据。

## 2. 规范性关键词

- MUST / MUST NOT：不满足即 NON-CONFORMANT。
- SHOULD / SHOULD NOT：可以偏离，但 MUST 在 `QUALITY_STATUS.md` 说明原因和影响。
- MAY：可选能力。

## 3. 体系结构

ROCmDoc 规定两个接口边界和三个事实源。

### 3.1 面向用户的统一 CLI

达到 `runtime-core` 的模型仓 MUST 提供等价命令：

```text
<model>-rocm version --json
<model>-rocm capabilities --json
<model>-rocm doctor [--platform P] [--backend B] --json
<model>-rocm parse --input PATH --output-dir DIR \
  [--platform auto|linux-rocm|windows-hip] \
  [--backend auto|BACKEND] [--format markdown] --json
```

- `version` MUST 返回 CLI、适配器和合同版本。
- `capabilities` MUST 区分 `supported`、`experimental`、`planned` 和 `unsupported`。
- `doctor` MUST 只诊断；MUST NOT 静默安装、下载模型或修改系统。
- `parse` MUST 接受图片或图片目录；模型确实支持时 MAY 接受 PDF。
- `--json` 模式下 stdout MUST 只包含一个 JSON 文档；日志 MUST 写入 stderr。
- `--platform auto` MAY 用于交互体验，但 publish/benchmark MUST 使用显式平台。
- 结果 MUST 记录 `resolved_platform` 和 `actual_backend`，不得照抄请求值。

为兼容 benchmark，以下形式 MUST 映射到同一份 `ParseRequest`，不得维护两套实现：

```text
<model>-rocm parse --img-dir D --out-dir O --platform P --backend B --json
```

标准 exit codes（与 `contracts/cli-contract.md` §2 和 `omnidocbench_rocm.cli_contract.EXIT_CODES` 一致；模型仓 spec-lock 锁定同一映射，三者必须同步）：

| Code | Name | 语义 |
| ---: | --- | --- |
| 0 | OK | 全部成功 |
| 1 | PARTIAL | 运行完成，但部分页失败（per-page 失败已捕获、运行继续，R2） |
| 2 | USAGE | 参数或误用错误 |
| 3 | BACKEND_MISMATCH | 请求的 `--backend` 与实际运行的 backend 不一致 |
| 4 | CONTRACT | stdout 不是合法 JSON 或缺失必需字段 |
| 5 | FATAL | 未捕获崩溃 / 无输出 |

环境/依赖/设备/模型是否就绪由 `doctor --json`（`status: ready|not-ready`）诊断，**不**作为单独的 parse 进程码；若 parse 因环境原因无法运行，按 FATAL(5) 退出，就绪细节归于 `doctor`。本表是唯一规范映射，**不得静默重编号**；确需新增进程码时必须以兼容方式追加（不占用 0–5）并走 RFC/ADR（§10 QS-6）。

### 3.2 面向评测的 subprocess/filesystem adapter

模型仓 MUST 提供：

```text
python adapter/run_adapter.py \
  --img-dir D --out-dir O --platform P --backend B
```

适配器 MUST：

- 为每页输出一个 UTF-8 `<image_stem>.md`；
- 输出 `_run_stats.json`；
- 单页失败时继续处理其余页面并如实记录；
- 报告实际 backend、失败、fallback、重试和 resume；
- 产生确定性、可枚举的 artifact 路径。

适配器 MUST NOT：

- 导入或运行中央 scorer；
- 写入 `metric_result.json`、canonical result 或平台审阅结论；
- 把 smoke/placeholder 输出作为真实 OCR 发布；
- 因单页失败而丢失整个批次的运行记录；
- 从操作系统名称推断正式发布平台。

中央评测引擎 MUST 通过 subprocess/JSON/filesystem 调用适配器；MUST NOT 导入模型仓 Python runtime。

### 3.3 可选 HTTP profile

实现 MAY 提供：

```text
GET  /health
GET  /v1/capabilities
POST /v1/parse
```

HTTP 不是 1.0 最低合规要求。OpenAI-compatible 推理服务 MAY 作为内部 transport，但不得被描述为 ROCmDoc 公共文档解析 API。

### 3.4 三个事实源

| 事实源 | 唯一职责 | 禁止内容 |
| --- | --- | --- |
| `rocmdoc.yaml` | 能力、接口、实现、平台、许可证约束 | benchmark 分数 |
| `model_card_v2.json` | 结果索引、track、primary selection、证据引用 | 无法追溯的 headline |
| evidence bundle | 原始/派生证据、provenance、metrics、prediction manifest、环境锁 | 模型能力营销 |

README 中的平台矩阵、分数、状态和保证等级 MUST 由事实源生成。模型仓 MUST NOT 手写跨模型榜单；跨模型视图由中央仓生成。

## 4. 模型仓最低结构

达到 `base` 的模型仓 MUST 或 SHOULD 具有：

```text
.rocmdoc/spec-lock.json              # MUST
rocmdoc.yaml                         # MUST
model_card_v2.json                   # MUST；可为空 results[]
QUALITY_STATUS.md                    # MUST；自动生成
adapter/run_adapter.py               # runtime/benchmark profile MUST
eval/configs/omnidocbench_v16.yaml   # v1.6 profile MUST
REPRO.yaml                           # 发布结果时 MUST
reproduce.md                         # 发布结果时 MUST
README.md                            # MUST
README.zh-CN.md                      # SHOULD
CONTRIBUTING.md                      # MUST
CODE_OF_CONDUCT.md                   # MUST
SECURITY.md                          # MUST
LICENSE                              # MUST
NOTICE                               # 许可证不同或存在派生物时 MUST
CITATION.cff                         # benchmarked 仓库 SHOULD
.github/workflows/ci.yml             # MUST
tests/                               # MUST
```

`QUALITY_STATUS.md` MUST 由 conformance 工具生成，MUST 展示合同锁、通过的 profiles、未解决阻塞和检查时间；MUST NOT 作为手工事实源。

## 5. Spec lock

`.rocmdoc/spec-lock.json` MUST 包含：

- `central_repository`；
- `central_commit`；
- `contract_release`；
- `conformance_release`；
- schemas、result identity 和生成器版本；
- 本地规范 snapshot 的 SHA-256（如存在 snapshot）。

`central_commit` MUST 是真实存在、不可变的 commit。branch、`main`、未提交工作区或 floating package version MUST NOT 充当锁。合同升级 MUST 由工具生成差异报告。

## 6. 请求与响应

跨语言权威接口 MUST 是 JSON Schema Draft 2020-12；Python 类型仅为同构 SDK。

最小 `ParseRequest v1`：

```json
{
  "schema_version": 1,
  "input": {"path": "...", "kind": "image|image-directory|pdf"},
  "output_dir": "...",
  "platform": "auto|linux-rocm|windows-hip",
  "backend": "auto|<backend>",
  "format": "markdown",
  "options": {}
}
```

最小 `ParseResult v1`：

```json
{
  "schema_version": 1,
  "status": "success|partial|failed",
  "resolved_platform": "linux-rocm|windows-hip",
  "actual_backend": "<backend>",
  "pages": [],
  "summary": {"count": 0, "ok": 0, "failed": 0, "fallback": 0},
  "artifacts": [],
  "warnings": []
}
```

Schema MUST 使用稳定 `$id`。所有路径、枚举、错误与 partial 语义 MUST 由 Schema 和 profile fixtures 共同验证。

## 7. 结果身份与比较

### 7.1 Result identity v3

每个结果 MUST 由规范化 `run_spec` 计算身份：

```text
run_spec_hash = sha256(canonical_json(run_spec))
result_id = <model>__<platform>__<backend>__<precision>__<benchmark>__<short-run-spec-hash>
```

`run_spec` MUST 覆盖：

- model ID、不可变 model revision、weights digest；
- implementation ID、平台、backend/version、precision、quantization、topology；
- benchmark/version、dataset revision、page-set hash、subset、scorer revision、protocol；
- prompt、preprocess、postprocess 和 runtime config hash。

未知事实 MUST 写为 `unknown`，并限制 assurance；MUST NOT 填入推测值。影响输出的字段变化 MUST 产生新 result ID。历史结果 MUST 保留，只能标记 `superseded`、`retracted` 或 `invalid` 并记录原因。

### 7.2 Comparison track

跨模型比较 MUST 同时匹配 benchmark version、subset、page-set hash、scorer revision、scoring protocol 和 metric set。

OmniDocBench v1.6 track MUST 固定 upstream commit、dataset revision 和 page-set hash；MUST NOT 跟随 floating `main`。v1.7 或其它版本 MUST 使用独立 track。第三方入口只有在上述字段完全一致时才可并入同一 track。

### 7.3 Primary selection

每个 `model_id + comparison_track_id` MUST 最多有一个 primary result。选择记录 MUST 包含 `result_id`、`selected_by`、`selected_at`、`rationale` 和 `policy_version`。

系统 MUST NOT 自动把最高分选为 primary。实验 backend、fallback、不同精度或已知缺陷可能使最高分不适合作为推荐结果。

## 8. 证据与信任

生产者提交状态与平台审阅 MUST 分离：

```text
producer_assurance:
  submitted
  evidence-complete

platform_review:
  evidence_integrity: PASS|FAIL
  score_reproduction: PASS|FAIL|NOT_RUN
  inference_reproduction: PASS|FAIL|NOT_RUN
  cross_hardware_reproduction: PASS|FAIL|NOT_RUN
```

- `evidence_integrity PASS` 仅证明 Schema、hash、引用和算术一致。
- `score_reproduction PASS` 证明对既有 predictions 重新评分得到容差内结果。
- `inference_reproduction PASS` 证明从锁定模型和环境重新推理并评分。
- `NOT_RUN` 是诚实状态，不等于失败。

旧 `community/verified` badge MAY 保留兼容映射，但 MUST NOT 成为新结果的事实源或主展示。

## 9. Conformance profiles

| Profile | 证明范围 | GPU 要求 |
| --- | --- | --- |
| `base` | 根文件、Schema、spec-lock、许可证、文档一致 | 否 |
| `runtime-core` | CLI、JSON、exit codes、offline fixtures | 否 |
| `benchmark-omnidocbench-v16` | adapter 输出、backend match、失败与 full-set 身份 | CI fixture 不需要；发布推理需要 |
| `reproducible-score` | identity、hash、算术、track、primary | 重新评分通常不需要推理 GPU |
| `inference-reproduced` | 独立完成完整推理与评分 | 是 |

Profiles 是累积的；系统 MUST NOT 用单一模糊的全局 PASS 代替逐项状态。

## 10. 品质门禁

### QS-0 安全与仓库卫生

- MUST NOT 提交 token、密码、credential URL、私有 endpoint、用户文档或敏感日志。
- git remotes MUST NOT 包含凭证。
- CI MUST 使用最小权限；第三方 Actions SHOULD 锁定不可变 revision。
- MUST 提供私密安全报告渠道和 secret scanning。
- 已暴露凭证的本地删除不代表处置完成；所有者 MUST 撤销或轮换。

### QS-1 许可证与来源

- MUST 分别声明 adapter code、upstream code、model weights、dataset 和派生 artifact 的许可证。
- 缺少证据时 MUST 默认为 `unknown`。
- MUST NOT 把 source-available、地域限制或商用阈值模型称为开放源代码模型。
- MUST NOT 重新分发无明确许可的权重。
- NOTICE 与 SPDX/REUSE 元数据 MUST 对应真实文件。

### QS-2 接口与文档

- 双语文档的安装、Demo、评测、限制和许可证语义 MUST 一致。
- smoke 与 real demo MUST 明确区分。
- `doctor --json` MUST NOT 泄露凭证或敏感本地路径。
- headline MUST 来自事实源，或清楚标记 external/self-reported。
- 模型仓 MUST NOT 手工维护跨模型排名。

### QS-3 测试与 CI

- MUST 检查 lint、unit、Schema、contract、README/QUALITY_STATUS drift。
- MUST 覆盖 success、partial、fatal、bad-json 和 backend-mismatch fixtures。
- 无 GPU CI MUST NOT 声称完成 GPU 验证。
- smoke backend MUST 输出 placeholder 标记，publish gate MUST 拒绝它。
- SHOULD 为关键适配和后处理提供 golden fixtures。

### QS-4 Benchmark 证据

- full-set 发布 MUST 有 page-set hash、scorer revision、dataset revision 和 protocol。
- 单页失败 MUST 进入正式分母，不得无说明排除。
- prediction manifest MUST 记录文件、数量和 hash。
- metrics、run summary、provenance 与 model card MUST 算术一致。
- 失败、fallback、重试和 resume MUST 可见。
- upstream self-report、producer submission、score reproduction 和 inference reproduction MUST 使用不同字段。

### QS-5 发布与供应链

- MUST 使用 SemVer、CHANGELOG 和可复现构建命令。
- release artifact MUST 对应 git tag 并提供 digest。
- 发布前 MUST 生成 SBOM 或许可证报告。
- SHOULD 逐步采用 SLSA provenance 和签名 attestation。
- 安装文档 SHOULD 避免未固定、未校验的远程脚本执行。

### QS-6 治理与维护

- MUST 用 `MAINTAINERS.yaml` 或等价文件标明 adapter/backend/platform owners 和 reviewers。
- 规范变更 MUST 走 RFC/ADR。
- breaking contract 变更 MUST 提升 major；兼容新增 SHOULD 提升 minor。
- deprecated 能力 MUST 至少保留一个 minor release 的迁移窗口。
- 结果更正 MUST 保留审计历史，不得静默改分。

## 11. 自动检查接口

实现 SHOULD 提供：

```text
rocmdoc-conformance check . --profile base
rocmdoc-conformance check . --profile runtime-core
rocmdoc-conformance check . --profile benchmark-omnidocbench-v16
rocmdoc-conformance check . --profile reproducible-score
rocmdoc-conformance render-quality-status . --check
rocmdoc-conformance audit-zone --repos-root <ROOT> --report zone-audit.json
```

现有 `omnidocbench-rocm conformance-profiles` MAY 作为兼容别名。工具改名 MUST NOT 破坏已存在用户流程。

## 12. 中央导入与发布

- 中央 importer MUST 只接受不可变 `{repository, commit, result_id, artifact hashes}`。
- canonical store MUST 由 importer 生成，MUST NOT 手工编辑。
- 默认专区视图 MUST 每个 `model + track` 只展示 primary valid result。
- `superseded`、`invalid` 和历史结果 MUST 保留在审计视图。
- README/榜单 MUST 由 canonical store 生成，并在 CI 使用 `--check` 防止漂移。
- 合规只取决于公开标准与证据，MUST NOT 以仓库 namespace 或组织所有权为条件。

## 13. 社区贡献与归属

中央仓 MUST 提供至少以下贡献路径：

- Adopt a Model：创建或维护模型适配器；
- Hardware Run：在新 AMD 硬件/系统上提交运行证据；
- Score Reproduction：重放 predictions 与 scorer；
- Inference Reproduction：独立重跑完整推理；
- Docs/Test/Translation：改进文档、fixtures、CI 和翻译。

每个导入结果 MUST 保留 producer、adapter author、evidence contributor、reviewer 和 upstream attribution。贡献者 MUST 保有其 adapter 工作的可见署名；中央仓不夺取外部仓库所有权。

项目 SHOULD 采用 DCO、Contributor Covenant、REUSE/SPDX、结构化 issue forms、PR evidence checklist、good-first-issue/help-wanted 标签以及公开 RFC/ADR 讨论。

## 14. 版本与兼容

- 本标准使用 SemVer。
- Schema 的 `$id` 与版本 MUST 稳定且可解析。
- 1.x 内兼容新增 MAY 通过 minor release 发布。
- 删除字段、改变语义或破坏 CLI/adapter MUST 提升 major。
- legacy v1 cards/badges MAY 被读取，但 MUST 映射为明确的 deprecated representation。
- 模型仓锁定新合同前，中央 commit、合同包与 conformance 包 MUST 已存在且可验证。

## 15. 合规声明

模型仓只能声明它实际通过的 profile，并 MUST 附：

- spec-lock；
- conformance 工具版本；
- 完整命令与 exit code；
- PASS/FAIL/BLOCKED/NOT_RUN；
- 生成的 `QUALITY_STATUS.md`；
- 发布结果所需的 evidence references。

结构检查、重新评分和重新推理是不同事实，MUST NOT 互相替代。无法核验的事实保持 `unknown`；未执行的验证保持 `NOT_RUN`。
