# 后端策略 (Backend Policy)

本契约定义 OmniDocBench-ROCm 支持哪些推理后端，以及在什么条件下可以出现
非 ROCm 后端。它是徽章资格与诚实溯源的权威依据。项目边界决策见 ADR-0001。

平台标识保持为 `linux-rocm` 与 `windows-hip`（不改名；Windows 的官方技术入口
仍是 HIP SDK，而 HIP 属于 ROCm）。

## 1. 一等 ROCm 后端 (First-class ROCm backends)

这些是项目长期支持的目标。使用下列后端产出的结果有资格获得正常的徽章等级
（见 `contracts/badge-policy.md`）：

- **HIP Runtime / HIP SDK**
- **MIGraphX**
- **ONNX Runtime MIGraphX Execution Provider**
- **PyTorch-ROCm**
- **vLLM-ROCm**
- **llama.cpp-HIP**
- 其他明确基于 ROCm/HIP 的开源推理路径。

## 2. 过渡后端 —— DirectML

**DirectML** 仅允许在 Windows 上使用，且仅在该平台暂时缺乏等价的
ROCm/MIGraphX 能力时使用。它是**临时兼容回退**，既不是一等后端，也不与上述
ROCm 路径并列。

使用 DirectML 的模型必须**同时**满足：

1. 文档中将该路径明确标注为 `compatibility fallback`（兼容回退）。
2. 不得获得任何含义为 "ROCm-native" 的徽章。
3. 溯源信息必须在产物的 `execution_provider` 字段中记录真实的执行提供者
   （`DmlExecutionProvider`）。
4. 其结果**绝不能**被描述为 MIGraphX 或 ROCm EP 的结果。
5. `model_card.json` 必须在 `target_backend` 中记录未来目标后端为 MIGraphX
   （即预期的 ROCm 路径）。
6. 当 Windows 上出现正式可用的 ROCm/MIGraphX 路径后，DirectML 路径进入
   `deprecated`（弃用）→ `removed`（移除）流程。

明确声明：**Windows 上的 MIGraphX 目前尚未正式可用。** 本项目不编造、不引用
任何 AMD／ROCm／ONNX Runtime 的路线图或发布时间。

## 3. 不在范围内 (Out of scope)

- **Vulkan**
- **OpenVINO**
- 其他与 ROCm 无关的通用 GPU 后端。

这些不是项目后端。仅可在说明 "不在范围内" 时被提及，不在模板或文档中被推荐。

## 4. 维度分离

不应让一个 `platform` 字符串同时承担平台 + 操作系统 + 运行时/后端 + 执行提供者
+ 兼容状态的全部含义。产物 schema（`contracts/artifact-schema.json`，
schema v1）保留 `platform`（`linux-rocm` | `windows-hip`），并新增**可选**字段，
使每个维度被独立记录：

| 字段 | 含义 | 示例 |
|---|---|---|
| `backend` | 运行时 / 服务栈 | `vllm-rocm`、`migraphx`、`onnxrt-migraphx`、`llama-cpp-hip`、`smoke` |
| `execution_provider` | ONNX 执行提供者（适用时） | `ROCMExecutionProvider`、`DmlExecutionProvider` |
| `backend_family` | 所属家族 | `rocm`、`directml-fallback` |
| `compatibility_status` | 定位 | `first-class`、`transitional-fallback` |
| `target_backend` | 未来目标后端（用于回退行） | `migraphx` |

`schema_version` 保持为 `1`；这些新增字段向后兼容，不会使任何已有的 v1 产物失效。
