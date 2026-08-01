"""Identity-pinning helpers (Round-2 P0-5 / Decision 2 Option C).

Derive reproduction-critical hashes from a model repo's REPRO.yaml so a result's
``run_spec`` identity can be PINNED from real, verifiable inputs instead of left
``unknown``. Most fields are direct file/content hashes or REPRO/catalog values;
the ``runtime_config_hash`` is the one with a CONSTRUCTED definition (canonical
JSON of the REPRO runtime fields + the serving axis), so it gets a helper here
rather than being hand-assembled at enactment time.

This module is the reusable tool for pinning identity across the zone's results
(Ovis PoC 2026-08-01 proved the pipeline on real data).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def load_repro(repro_path: Path | str) -> dict:
    """Load a model repo's REPRO.yaml as a dict."""
    import yaml  # local import; yaml is a model-repo/eval dependency, not engine-core
    return yaml.safe_load(Path(repro_path).read_text(encoding="utf-8"))


def make_runtime_config_hash(repro_path: Path | str, serving: dict) -> str:
    """sha256 of the canonical JSON of the runtime config.

    The runtime config = the REPRO fields that affect the run but are NOT already
    captured in ``run_spec.implementation`` (command, environment, hardware,
    git_commit) plus a ``serving`` axis (the backend/version/dtype/topology the
    caller supplies from the result's implementation block). Deterministic: values
    are YAML-parsed (so ``>-`` scalars drop trailing newlines), keys are sorted,
    separators are compact. Reproduces the Ovis PoC value when given the Ovis
    REPRO + its vLLM serving axis.
    """
    repro = load_repro(repro_path) if not isinstance(repro_path, dict) else repro_path
    cfg = {
        "command": repro.get("command"),
        "environment": repro.get("environment"),
        "hardware": repro.get("hardware"),
        "git_commit": repro.get("git_commit"),
        "serving": serving,
    }
    canon = json.dumps(cfg, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canon.encode("utf-8")).hexdigest()
