# Roadmap

Items are **planned, not dated**. No commitment to a specific release date;
AMD/ROCm/ONNX Runtime upstream availability gates several of them.

## Near term

- **Onboard the remaining models** (`unlimited-ocr`, `hunyuan-ocr`) to the
  central registry with real **Linux-ROCm** scores (`community`, then `verified`
  via maintainer Docker reproduction). `paddleocr-vl-1.6` and `mineru2.5` are
  already `community` on Linux-ROCm.
- **Promote `community` results to `verified`** via maintainer Docker
  reproduction (`Dockerfile.repro` + `VERIFIED.yaml`).
- **Pin the OmniDocBench checkout revision** in `LinuxRocmBackend.score()`
  (currently hardcoded to `master`).

## Medium term

- **Windows-HIP backend**: implement `engine/omnidocbench_rocm/backends/windows_hip.py`
  so `get_backend("windows-hip")` works, with Windows-native scoring + the
  Windows CDM toolchain. Until then Windows uses DirectML as a **temporary
  compatibility fallback** in selected model repos (see
  `contracts/backend-policy.md`).
- **Hosted hub site** (MkDocs) rendering `hub/registry.yaml` into a public
  comparison table. Until then `scripts/generate_registry.py` renders Markdown.

## Out of scope (by policy)

- Vulkan, OpenVINO, and general non-ROCm GPU backends as first-class targets.
- Anything that would require fabricating results or auto-promoting a
  `community` result to `verified`.

## How to influence the roadmap

Open a GitHub issue (use the *feature request* or *model onboarding* template)
describing the model or capability and the target platform.
