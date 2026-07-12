# 贡献一个模型

如何把一个开源文档解析模型加入 **AMD 文档解析模型专区**，并在 AMD 硬件上跑通 OmniDocBench v1.6 评测。本指南是从提案到 `verified` 徽章的 9 步路径。你要实现的契约见 [`contracts/adapter.md`](../contracts/adapter.md)；通过审核的检查清单见 [`contracts/conformance.md`](../contracts/conformance.md)。

> English version: [`contribute-a-model.md`](contribute-a-model.md).

**本中文版针对国内网络环境优化：镜像、ModelScope、CTAN/PyPI 国内源一律前置，不是英文版的直译。** 在国内请优先按本页操作。

---

## 前置条件

开始前请确认硬件、系统、环境。专区面向两类平台，你可以只贡献**其中一个**。

### 可用的 AMD GPU

| 平台 | GPU | 说明 |
|---|---|---|
| `linux-rocm`（Radeon 独显 + Linux/ROCm） | gfx1100（Radeon PRO W7900 48GB、RX 7900 XT/XTX） | ROCm 6.x。参考成绩 92.431（Unlimited-OCR）即在 gfx1100 上产出。 |
| `windows-hip`（Ryzen AI MAX+ 395 + Windows/HIP） | Strix Halo Radeon 8060S 核显；RX 7900 XT+ 独显 | Windows 11，HIP SDK / DirectML。已有真实的 Windows 原生 CDM 结果（2026-07-11）。 |

其它 AMD GPU 架构（如 gfx1030、gfx1151）可能可用但未持续测试。如果你手上是其它架构，先开 issue，我们帮你确认 ROCm/HIP 兼容性。

### 系统、磁盘、网络

- **系统：** `linux-rocm` 用 Linux（推荐 Ubuntu 22.04+）；`windows-hip` 用 Windows 11。必要时可借助 WSL2。
- **磁盘：** 预留约 50 GB。OmniDocBench v1.6 数据集（约 5 GB）、模型权重（5–40 GB 不等）、CDM 工具链（TeX Live 2026 + IM7 + Node，约 8 GB）、评测 venv。
- **网络（国内重点）：** 直连 GitHub / HuggingFace / CTAN / PyPI 基本不通。**先配镜像**（见下方「国内镜像配置」一节），再开始任何下载。

### 国内镜像配置（先做这一步）

国内环境最大的坑是网络。专区沿用了 `omnidocbench-amd-windows` 的镜像探测方案——**一次性配好，后续脚本自动读取**：

| 来源 | 可用镜像 / 替代源 |
|---|---|
| HuggingFace | **ModelScope**（`modelscope.cn`，国内托管，同模型同数据集）——优先用 |
| GitHub | `ghproxy.net` / `ghfast.top` 前缀代理 |
| CTAN（TeX Live） | USTC / 清华 TUNA CTAN 镜像 |
| PyPI | 清华 / USTC PyPI 镜像 |
| Microsoft Store（WSL） | 直接绕过，用 USTC rootfs 导入（见 `pitfalls.md#wsl`） |

配置方式：在每台机器上跑一次镜像探测脚本，它会逐个探测可用源并写入 `mirrors.env`，后续所有 `setup` / `score` 脚本都读这个文件。**跳过这一步，第一个 `git clone` 或 `huggingface-cli download` 就会挂死。**

权重下载优先用 **ModelScope**（`modelscope` CLI 或 `hf_transfer` + `HF_ENDPOINT` 指向国内镜像）。ModelScope 在国内速度和稳定性都远好于直连 HuggingFace。

### Python 版本（关键的分拆）

OmniDocBench 的评测代码在 Python 3.12 下会坏（用了 `inspect.getargspec`、`distutils`、`imp` 等 3.12 已移除的 API）。专区用**两个 venv** 解决：

| venv | Python 版本 | 跑什么 |
|---|---|---|
| **eval-venv** | 3.11（或 3.10） | OmniDocBench `pdf_validation.py`——即 `score` 阶段。引擎自动创建。 |
| **模型 venv** | 3.12（或模型需要的版本） | 适配器的推理。即 `infer` 阶段。 |

引擎是一个薄壳，按阶段把子进程派发到正确的 venv。你不用自己管这个分拆——`make setup-linux` / `make setup-windows` 会建好 eval-venv；你只需把模型依赖装进它自己的 venv。

---

## 9 步流程

```
1 提案 → 2 脚手架 → 3 环境准备 → 4 实现 → 5 Demo → 6 评测 → 7 发布 → 8 提交 → 9 Verified
```

每步标注的时间假设硬件和权重已就绪。

### 第 1 步 — 提案（几分钟）

在 `AIwork4me/OmniDocBench-AMD` 开一个 issue，标题「我想加入模型 X」。维护者确认：

- **开源**（权重 + 代码都开放）。闭源模型（Gemini、GPT、Mistral-OCR、mathpix、混元 OCR、优图 Parsing、Nanonets、GLM-OCR 等）永不支持。
- **在范围内**——是文档解析模型（纯通用 VLM 除非有文档解析路径，否则不算）。
- **不重复**——不是已有或在做的模型。

**耗时：** issue 来回一轮。**完成标志：** 维护者回复「可以」。

### 第 2 步 — 脚手架（10 分钟）

用 cookiecutter 模板生成合规仓库：

```bash
pip install cookiecutter
cookiecutter gh:AIwork4me/OmniDocBench-AMD --directory template
# 提示：repo_name (Model-AMD)、model_slug、model_id、model_version、license
```

> 国内若 `gh:` 协议慢，可先 `git clone` 专区仓库再 `cookiecutter <本地路径>/template`。

生成的仓库已包含完整结构：`adapter/run_adapter.py`（带一个不需要 GPU 的 `smoke` 后端）、`adapter/adapter_config.py`、`Makefile`、中英双语 README、`eval/configs/omnidocbench_v16.yaml`、`examples/`、CI 工作流、以及 `results/omnidocbench/v16/{linux-rocm,windows-hip}/` 目录。

推到你自己的 fork（如 `AIwork4me/<Model>-AMD`）。

**耗时：** 10 分钟。**完成标志：** 仓库已能 `make smoke-test` 和 `make demo`（smoke 后端）。

### 第 3 步 — 环境准备（30 分钟 – 2 小时，一次性）

准备引擎 + 模型权重 +（可选）CDM：

```bash
# 引擎 + eval-venv（Python 3.11）+ OmniDocBench 检出
make setup-linux        # 或：make setup-windows

# 你的模型权重 + 推理服务（路径写进 adapter/setup/.env.local）
bash adapter/setup/00-install-deps.sh        # Linux
powershell -ExecutionPolicy Bypass -File adapter\setup\00-install-deps.ps1   # Windows

# CDM 工具链（首次可跳过，见第 6 步）
omnidocbench-amd cdm setup --platform linux-rocm
```

所有步骤都是**幂等**的——装过再跑是空操作，中断后能续跑。权重放进 gitignore 的 `models/` 目录；`.env.local` 记录绝对路径。

**国内提示：** 权重走 ModelScope；TeX Live 走 USTC/清华 CTAN 镜像；PyPI 走清华源。`mirrors.env` 配好后这些自动生效。

**耗时：** 镜像快 + 权重有缓存则 30 分钟；大模型 + 慢链路 + 建 CDM 工具链可能要 2 小时。**完成标志：** `omnidocbench-amd dataset download --version v16 --revision v1.6` 成功；`make demo` 能跑。

### 第 4 步 — 实现（几小时 – 一天）

这是唯一与模型相关的代码。编辑 `adapter/run_adapter.py`：

1. 把 `_infer(img, platform, config)` 的函数体替换成你模型的推理（图 → Markdown）。
2. 在 `adapter/adapter_config.py` 里把 `BACKEND` 设为你的后端（`vllm`、`llama-cpp-server`、`onnx-rocm`、`onnx-directml` 等），填好 `SERVER_URL`、`API_MODEL_NAME`、`WEIGHTS_DIR`。
3. 如果模型用到 ONNX（版面/流水线），按平台选执行提供者：Linux 用 `onnxruntime-rocm`（ROCm EP），Windows 用 `onnxruntime-directml`（DirectML EP）。见 [`contracts/adapter.md`](../contracts/adapter.md) §R6。
4. 保留 `run_adapter` 签名、`out_dir/<image_stem>.md` 输出约定、逐页 `try/except`（绝不上抛）、以及 `_run_stats.json` 写入。

**耗时：** vLLM 服务的 VLM 几小时（主要是接线）；多阶段流水线（版面 + 公式 + OCR）或自定义 ONNX 路径可能要一天。**完成标志：** `make demo` 对 `examples/demo.png` 产出合理的 Markdown。

### 第 5 步 — Demo（5 分钟）

```bash
make demo
# 等价于：omnidocbench-amd infer --adapter adapter/run_adapter.py --img-dir examples --out-dir <临时目录>
```

检查单页输出像不像真实的文档解析（标题、正文、公式为 `$...$`、表格）。如果一团糟，先修 `_infer`，别急着跑全量。

**耗时：** 5 分钟。**完成标志：** 一份能给人看的 `.md`。

### 第 6 步 — 评测（每平台 20 分钟 – 2 小时）

跑完整的 OmniDocBench v1.6 评测（1651 页）：

```bash
make eval-linux          # 或：make eval-windows
# = omnidocbench-amd run --stage all --platform linux-rocm --version v16 --revision v1.6
```

这会跑四个阶段：`download → infer → score → publish`，在 `results/omnidocbench/v16/<platform>/` 产出产物包：`metric_result.json`、`run_summary.json`、`provenance.json`、`_run_stats.json`。

**CDM（高价值指标）：** CDM（公式匹配，通过 LaTeX→PDF→PNG 颜色匹配）用 `--cdm` 开启。**第一遍先不开 `--cdm`**（只跑 Edit_dist + TEDS）验证流水线；然后建好 CDM 工具链（`omnidocbench-amd cdm setup --platform ...`）再带 `--cdm` 重跑。CDM 由引擎统一管理，但出了名的折腾——如果失败，看 [`pitfalls.md`](pitfalls.md)（`#cdm-zero` 决策树覆盖了 CDM 静默得 0 的六种原因）。

**耗时：** 推理 20–40 分钟（VLM，gfx1100 上约 1 秒/页）；评分再加 10–30 分钟（带 CDM 更久，每个公式要编译 LaTeX）。**完成标志：** 产物包存在，`run_summary.json` 的 `readme_metrics` 非零。

### 第 7 步 — 发布（10 分钟）

```bash
make publish
# = omnidocbench-amd conformance .   （跑 check_conformance.py）
```

修复所有不合规项（README 缺章节、results 目录空、`pyproject.toml` 没依赖 `omnidocbench-amd`、`model_card.json` 不合法）。检查清单见 [`contracts/conformance.md`](../contracts/conformance.md)。

然后提交 `results/` 产物包 + `model_card.json`。这就是你的**来源完整**证据。

**耗时：** 10 分钟（假设第 6 步产出了合法产物）。**完成标志：** `check_conformance.py` 退出码 0（`CONFORMANT`）。

### 第 8 步 — 提交（几分钟）

向 `AIwork4me/OmniDocBench-AMD` 开 PR，把你的模型加进 `hub/registry.yaml`，`badge` 填 `community`（没有的平台填 `community-wanted`），附上你仓库的链接。CI 会对你的仓库跑 `check-conformance`。

**耗时：** 来回一轮。**完成标志：** 你的模型出现在对比表里，所贡献的平台带 `community` 徽章。

### 第 9 步 — Verified（可选，维护者操作）

维护者在干净的 Docker 环境（`ghcr.io/zeng-weijun/omnidocbench-eval:repro-ubuntu2204`）里，在**你声明的两个平台**上复现你的评测，确认 `overall` 在容差内，然后往你仓库提交一份 `VERIFIED.yaml`。你的徽章从 `community` 升为 `verified`。见 [`contracts/badge-policy.md`](../contracts/badge-policy.md)。

**耗时：** 维护者侧操作；你只需保持仓库可复现。**完成标志：** `verified` 徽章。

---

## 「我只有一个平台」

完全没问题，这是常态。徽章是**按平台独立**的——见 [`contracts/badge-policy.md`](../contracts/badge-policy.md)。

- 你有的平台出 `community`（比如 `linux-rocm`）。
- 另一个平台在 registry 里显示 `community-wanted`——这是给有该硬件的贡献者的信号：这个模型在那边有人想要。
- 之后可以（你自己或别的贡献者 PR）补上缺失的平台，不影响已 working 的一侧。

**你不需要两个平台都齐才能贡献。** 大多数贡献者会从一个平台开始。

---

## 哪里求助

- **报错 / 失败：** 先按症状搜 [`pitfalls.md`](pitfalls.md)——按你看到的现象组织，每条都有 根因 → 修复 → 验证。CDM 相关条目（`#cdm-zero`、`#grayscale`、`#mathcolor` 等）是仓库里最有价值的几页。
- **架构 / 「怎么拼到一起的」：** [`architecture.md`](architecture.md)。
- **你在实现的契约：** [`contracts/adapter.md`](../contracts/adapter.md)。
- **问题 / 提案：** 在 `AIwork4me/OmniDocBench-AMD` 开 issue。维护者在 issue 里回复。

仓库里维护着一份「适合新手的模型」清单（开源、文档全、接起来简单的模型）。想根据你的硬件要推荐，开 issue 问一声。

---

## 太长不看

```bash
cookiecutter gh:AIwork4me/OmniDocBench-AMD --directory template   # 2 脚手架
make setup-linux                                                   # 3 环境准备
$EDITOR adapter/run_adapter.py adapter/adapter_config.py           # 4 实现
make demo                                                          # 5 Demo
make eval-linux                                                    # 6 评测
make publish                                                       # 7 发布
# PR 到 hub/registry.yaml                                          # 8 提交
```

契约就一个函数。剩下的引擎搞定。
