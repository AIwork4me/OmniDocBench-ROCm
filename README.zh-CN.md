# OmniDocBench-ROCm

> 面向 **AMD ROCm** 软件栈的文档解析模型开放适配、评测、复现与协作平台。

OmniDocBench-ROCm 是在 AMD 硬件上运行开源文档解析模型、对标
[OmniDocBench v1.6](https://github.com/opendatalab/OmniDocBench) 的共享平台。
通过文件系统解耦的适配器契约，让分数**跨模型、跨平台可比**；配合分层的信任徽章、
真实评测数据、开箱即用的示例与中英双语文档。

```text
contracts/   适配器接口、产物 schema、一致性清单、徽章与后端策略
engine/      omnidocbench_rocm —— 可 pip 安装的评测引擎（Linux-ROCm 已实现）
template/    单模型仓库的 cookiecutter 模板（默认：Model-ROCm）
hub/         registry.yaml —— 对比表的事实来源（初始占位）
docs/        contribute-a-model、architecture、pitfalls、ci-reality、治理、路线图
```

## 当前状态（诚实说明）

- **已实现：** Linux-ROCm 评测引擎 —— 四阶段流水线
  （`download → infer → score → publish`）、`omnidocbench-rocm` CLI、一致性检查器、
  产物 schema、cookiecutter 模板、CPU-only CI。
- **部分实现：** CDM（公式匹配）在 Linux 上仅为脚手架桩，尚未端到端打通；打分当前
  将 OmniDocBench 检出固定为 `master`。
- **计划 / 接入中：** **Windows-HIP** 后端（当前 `get_backend("windows-hip")` 直接
  抛出 not-implemented）、端到端 CDM、托管站点、GPU CI。
- **注册表：** **初始占位**，不是排行榜 —— 3 个模型（`paddleocr-vl-1.6`、
  `unlimited-ocr`、`mineru2.5`）在两个平台上均为 `community-wanted`，暂无分数。
- **DirectML** 仅作为部分模型仓在 Windows 上**临时兼容回退**（在尚无等价 ROCm/MIGraphX
  路径时使用），**不是**项目一等后端。

## 为什么选择 OmniDocBench-ROCm

- **分数可比。** 适配器契约就是文件系统边界：引擎以子进程方式调用你的适配器，只消费
  `out_dir/<image_stem>.md` + `_run_stats.json`。适配器可用任意技术栈，分数仍然可比。
- **诚实信任。** CI 没有 AMD GPU runner，信任来自分层徽章，而非绿色对勾。见
  `docs/ci-reality.md`。
- **ROCm 优先。** 长期边界是 ROCm 软件栈。

## 范围

- **一等后端：** HIP、MIGraphX、ONNX Runtime MIGraphX EP、PyTorch-ROCm、vLLM-ROCm、
  llama.cpp-HIP。
- **过渡：** DirectML —— 仅作 Windows 临时兼容回退。
- **不在范围：** Vulkan、OpenVINO、与 ROCm 无关的通用 GPU 后端。

> ROCm 定义了长期软件栈边界。DirectML 只是 Windows 上的临时兼容回退，不是项目一等后端。

详见 [`contracts/backend-policy.zh-CN.md`](contracts/backend-policy.zh-CN.md)。

## 架构

一句话：一个平台仓（本仓）持有共享契约、引擎、模板与注册表；每个模型各住一个由模板
生成的仓库。引擎从不导入适配器 —— 只消费适配器的文件系统输出 —— 因此模型仓可用任意技术栈。
平台标识为 `linux-rocm`（已实现）与 `windows-hip`（计划）。

详见 [`docs/architecture.md`](docs/architecture.md)。

## 快速开始

```bash
pip install omnidocbench-rocm
omnidocbench-rocm --help
```

## CLI

```text
omnidocbench-rocm cdm setup --platform <p>            # 配置 CDM（部分/计划中）
omnidocbench-rocm dataset download --version v16 --revision <git-rev>
omnidocbench-rocm infer --adapter <path> --img-dir <d> --out-dir <d> --platform <p>
omnidocbench-rocm score --platform <p> --predictions-dir <d> --version v16 --run-stats <path>
omnidocbench-rocm publish --model-id <m> --platform <p> ...   # 组装 run_summary + provenance
omnidocbench-rocm run --stage all ...                 # download -> infer -> score -> publish
omnidocbench-rocm conformance <repo-path>             # CONFORMANT | NON-CONFORMANT
```

## 支持的平台

| 平台 | 状态 |
|---|---|
| `linux-rocm` | 已实现（打分路径真实；CDM 部分） |
| `windows-hip` | 计划 / 接入中（当前抛出 not-implemented） |

## 评测与可复现

- OmniDocBench 数据集 revision **强制固定**（引擎拒绝未固定的 `None`）。
- `publish` **拒绝**从有限子集发布官方证据（`limit_pages` 必须为 `null` —— 全量集强制）。
- 每次发布的运行都带 `run_summary.json` + `provenance.json`（git commit、平台、引擎版本、
  适配器命令、数据集 revision）。

## 信任与徽章模型

CI 仅 CPU，校验**结构**而非数字。信任来自按平台的徽章
（[`contracts/badge-policy.md`](contracts/badge-policy.md)）：

`community-wanted` →（提交结果 + 通过一致性）→ `community` →
（维护者 Docker 复现 + `VERIFIED.yaml`）→ `verified`。

信任任何数字前请先读 [`docs/ci-reality.md`](docs/ci-reality.md)。

## 加入模型

[`docs/contribute-a-model.zh-CN.md`](docs/contribute-a-model.zh-CN.md) 是完整 walkthrough。
简版：用模板生成仓库，实现 `adapter/run_adapter.py`（替换 `_infer`），无 GPU 跑 `smoke`
后端，再 `omnidocbench-rocm conformance .`。

```bash
cookiecutter https://github.com/AIwork4me/OmniDocBench-ROCm.git --directory template
```

## 注册表

`hub/registry.yaml` 是对比表的事实来源。目前是**初始占位**（3 个模型、`community-wanted`、
无分数），不是完整排行榜。`scripts/validate_registry.py` 校验其结构；
`scripts/generate_registry.py` 渲染为 Markdown。

## 路线图

近期（计划中，不定日期）：三个 v1 模型带真实 Linux-ROCm 分数接入；Windows-HIP 后端；
端到端 CDM（先 Linux）；托管站点。详见 [`docs/roadmap.md`](docs/roadmap.md)。

## 贡献

[`CONTRIBUTING.md`](CONTRIBUTING.md)。提 PR 前：`pytest -q` 通过、
`python scripts/check_brand.py` 干净、`python scripts/validate_registry.py` 有效。

## 治理 / 安全 / 许可

- 治理：[`docs/governance.md`](docs/governance.md)
- 安全：[`SECURITY.md`](SECURITY.md) · 支持：[`SUPPORT.md`](SUPPORT.md)
- 许可：Apache-2.0（[`LICENSE`](LICENSE)）· 引用：[`CITATION.cff`](CITATION.cff)
