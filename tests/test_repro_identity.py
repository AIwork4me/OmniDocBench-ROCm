"""Tests for repro_identity helpers (identity-pinning, Round-2 P0-5 / Decision 2-C)."""
from pathlib import Path

import pytest

from omnidocbench_rocm import repro_identity as ri

_REPRO = {"command": "python adapter/run_adapter.py --backend vllm",
          "environment": {"type": "venv", "image": "vllm-0221b"},
          "hardware": {"gpu": "AMD gfx1100", "vram_mb": 49152},
          "git_commit": "abc123"}
_VLLM_SERVING = {"backend": "vllm", "backend_version": "0.22.1", "dtype": "bf16",
                 "topology": "embedded-python"}


def test_deterministic():
    a = ri.make_runtime_config_hash(_REPRO, _VLLM_SERVING)
    b = ri.make_runtime_config_hash(_REPRO, _VLLM_SERVING)
    assert a == b
    assert a.startswith("sha256:") and len(a) == 7 + 64


def test_changes_with_serving_and_command():
    base = ri.make_runtime_config_hash(_REPRO, _VLLM_SERVING)
    # different serving axis -> different hash
    llama = {"backend": "llama-cpp", "backend_version": "x", "dtype": "bf16", "topology": "managed"}
    assert ri.make_runtime_config_hash(_REPRO, llama) != base
    # different command -> different hash
    repro2 = dict(_REPRO, command="python adapter/run_adapter.py --backend llama-cpp")
    assert ri.make_runtime_config_hash(repro2, _VLLM_SERVING) != base


def test_reproduces_ovis_poc_value():
    """The Ovis identity-PoC (2026-08-01) computed runtime_config_hash
    `0c6ce8b6...` from the real Ovis REPRO.yaml + its vLLM serving axis. The helper
    must reproduce it exactly. Skipped if the model repo isn't co-located (central CI
    must not hard-depend on a model-repo path)."""
    ovis_repro = Path("/workspace/OvisOCR2-ROCm/REPRO.yaml")
    if not ovis_repro.exists():
        pytest.skip("Ovis REPRO.yaml not co-located; skipping PoC-value reproduction")
    assert ri.make_runtime_config_hash(ovis_repro, _VLLM_SERVING) == \
        "sha256:0c6ce8b6c8c934e2a0e38eada02862096cf0258adead609fadf9d9947922b260"
