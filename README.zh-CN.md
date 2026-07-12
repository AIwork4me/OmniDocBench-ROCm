# omnidocbench-amd

**AMD 文档解析专区**的共享平台：在 AMD 硬件（Radeon + Linux/ROCm，以及
Ryzen AI MAX+ 395 + Windows/HIP）上运行 OmniDocBench v1.6 开源文档解析模型，
提供真实评测数据、开箱即用的示例与中英双语文档。

## 国内获取模型与数据

- **模型镜像**：优先从 [ModelScope](https://modelscope.cn/) 拉取，避免 HuggingFace
  网络问题；HuggingFace 镜像站作为备选。
- **数据集**：OmniDocBench v1.6 评测数据可通过 ModelScope 或本仓库的下载脚本获取。

## 仓库结构

- `contracts/` — 适配器接口、产物 schema、一致性清单、徽章策略。
- `engine/` — 双平台评测引擎（pip 包）。
- `template/` — 单模型仓库的 cookiecutter 模板。
- `hub/` — 模型注册表与站点。

新增模型请参见 `docs/contribute-a-model.md`。设计规格见 `docs/superpowers/specs/`。
