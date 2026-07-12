#!/usr/bin/env bash
# {{cookiecutter.repo_name}} — Linux/ROCm provisioning stub.
# Idempotent: safe to re-run. Replace the body with the real provisioning for
# your model (weights download, vLLM/ONNX runtime install, ROCm EP setup, ...).
set -euo pipefail
echo "[00-install-deps] {{cookiecutter.repo_name}}: implement provisioning (weights, runtime, ROCm EP)"
echo "[00-install-deps] platform=linux-rocm  backend=smoke (no GPU needed for smoke)"
