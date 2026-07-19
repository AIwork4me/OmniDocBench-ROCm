# fixture-model（一致性示例）

一个符合规范的单模型示例仓库，用于测试 `check_conformance`。
它满足一致性清单中的每一项。

## 安装 (Install)

```bash
pip install -e .
```

依赖 `omnidocbench-rocm` 引擎包。

## 演示 (Demo)

参见 `examples/run_demo.sh`，一键运行冒烟测试。

## 评测 (Evaluation)

```bash
omnidocbench-rocm infer --adapter adapter/run_adapter.py --platform linux-rocm
```

评测配置位于 `eval/configs/omnidocbench_v16.yaml`。

## 可复现性 (Reproducibility)

`results/omnidocbench/v16/linux-rocm/` 下的结果可在声明的硬件上由已提交的
适配器与配置复现。provenance 与 run_summary 产物由引擎生成并通过 schema 校验。

## 已知局限 (Known Gaps)

- 本仓库为示例：适配器输出占位文本，并非真实 OCR 结果。
- 暂未提交 Windows/HIP 平台结果。
