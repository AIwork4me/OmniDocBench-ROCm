# Roadmap

Items are **planned, not dated**. No commitment to a specific release date;
AMD/ROCm/ONNX Runtime upstream availability gates several of them.

## Near term

- **Onboard the three v1 models** (`paddleocr-vl-1.6`, `unlimited-ocr`,
  `mineru2.5`) to the central registry with real **Linux-ROCm** scores
  (`community`, then `verified` via maintainer Docker reproduction).
- **End-to-end CDM provisioning** on Linux (replace the current scaffold stub
  with a real `engine/omnidocbench_rocm/cdm/` toolchain; texlive + ImageMagick 7
  + Ghostscript).
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
