# OmniDocBench-ROCm 0.2.0 Transition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebrand the platform from OmniDocBench-AMD to OmniDocBench-ROCm (product/dist/package/CLI/template), define the ROCm backend policy, fix every doc/reality inconsistency, add registry validation + a brand-residue gate + governance, and ship as 6 reviewable commits on `refactor/omnidocbench-rocm`.

**Architecture:** Rename the Python package `engine/omnidocbench_amd/` → `engine/omnidocbench_rocm/` and the PyPI dist `omnidocbench-amd` → `omnidocbench-rocm`; drop the legacy surface entirely (never published, no downstream). Add optional backward-compatible fields to artifact schema v1 (no v2 bump). Make unimplemented backends fail honestly. Add a brand-residue gate that forbids the old brand everywhere except internal-record directories.

**Tech Stack:** Python ≥3.10, hatchling build, argparse CLI, jsonschema, pyyaml, cookiecutter, pytest, GitHub Actions.

## Global Constraints

(Copied verbatim from the approved spec. Every task implicitly includes these.)

- **Frozen / unchanged:** the upstream benchmark name `OmniDocBench`; the model-repo names `HunyuanOCR-ROCm`, `PaddleOCR-VL-ROCm`, `MinerU-ROCm`; the platform keys `linux-rocm` and `windows-hip`; the results path `results/omnidocbench/v16/<platform>/`.
- **No metric changes:** do not modify the OmniDocBench scorer algorithm or any public metric formula. Do not fabricate any Windows backend, CDM toolchain, eval result, or AMD/ROCm/ONNX-RT roadmap date. Do not auto-promote any result to `verified`.
- **Schema stays v1:** only optional backward-compatible fields are added; existing artifacts must still validate.
- **No history rewrite:** deleted files remain in git history.
- **Version:** `0.1.0` → `0.2.0`.
- **Branch:** `refactor/omnidocbench-rocm` (already created and checked out).
- **Brand-residue gate** (added in Task 6.9): forbidden tokens `OmniDocBench-AMD`, `omnidocbench-amd`, `omnidocbench_amd`, `AMD Doc Parsing`, `Model-AMD`, `omnidocbench-amd-windows` must not appear outside `docs/superpowers/**`, `docs/audits/**`, `docs/adr/**`, `CHANGELOG.md`. `DirectML` and `Vulkan` are NOT forbidden (their *use* is governed by `contracts/backend-policy.md`). `windows-hip` and the path segment `omnidocbench/` are retained.
- **Commit convention:** the 6 commits follow spec §9 with one documented refinement — the brand gate (`scripts/check_brand.py`) is created in Task 6.9 (final commit), not Task 3, so that no intermediate commit is ever red (docs that the gate scans are only clean after the docs rewrite). This keeps every commit independently green.

### Mechanical-rename convention (used throughout)

For pure find/replace renames (no judgment), each task states the **exact transform** and the **verification command** rather than reproducing every line. The transform is always one of:
- `omnidocbench_amd` → `omnidocbench_rocm` (Python identifiers / paths)
- `omnidocbench-amd` → `omnidocbench-rocm` (distribution / CLI strings)
- `OmniDocBench-AMD` → `OmniDocBench-ROCm` (product / repo)
- `AMD Doc Parsing` → `OmniDocBench-ROCm` (program name)

Verification for any rename task: `grep -RnE '<old_token>' <paths>` must return only the documented intentional residuals (none after Task 3), then `python -m pytest -q` must be green.

---

## Commit 1 — `docs: define OmniDocBench-ROCm scope and migration`

Scope: audit doc, ADR-0001, ADR-0002, backend-policy contract (EN+zh), delete the 3 stale AMD-era superpowers docs, fix inbound references to them. All new files are brand-clean (or in excluded dirs); no scanned file gains residue.

### Task 1.1: Migration audit doc

**Files:**
- Create: `docs/audits/2026-07-omnidocbench-rocm-migration-audit.md`

- [ ] **Step 1: Write the audit doc.** It must enumerate, with real counts and file lists, the four status buckets (Implemented / Partial / Design-only / Non-goal) from spec §1, the brand-residue token table, the PyPI evidence (`omnidocbench-amd` 404 never published; `omnidocbench-rocm` 404 available), and the downstream evidence (the 3 model repos do not pip-depend on this package). Use the exact findings already gathered (engine modules list, `windows_hip.py` absent, `cdm/` absent, no MkDocs/GPU-CI/registry-sync, template Makefile bug). Title: `# Migration Audit — OmniDocBench-AMD → OmniDocBench-ROCm (2026-07-19)`. This file lives under `docs/audits/` so it may freely use the old brand as evidence.

### Task 1.2: ADR-0001 (project boundary)

**Files:**
- Create: `docs/adr/0001-rocm-project-boundary.md`

- [ ] **Step 1: Write the ADR.** Standard ADR header (Status: Accepted; Date: 2026-07-19). Context: project scope is the AMD ROCm open-source compute stack. Decision: first-class ROCm backends = HIP, MIGraphX, ONNX Runtime MIGraphX EP, PyTorch-ROCm, vLLM-ROCm, llama.cpp-HIP; DirectML = temporary Windows compatibility fallback only; Vulkan/OpenVINO/non-ROCm = out of scope. Consequences: platform keys `linux-rocm`/`windows-hip` retained; DirectML results must be labelled `compatibility fallback` and cannot earn a ROCm-native badge; Windows MIGraphX is not currently production-ready and no roadmap date is quoted. Lives under `docs/adr/` (may reference old brand).

### Task 1.3: ADR-0002 (package + CLI migration, legacy surface dropped)

**Files:**
- Create: `docs/adr/0002-package-and-cli-migration.md`

- [ ] **Step 1: Write the ADR.** Decision: rename dist `omnidocbench-amd`→`omnidocbench-rocm`, package `omnidocbench_amd`→`omnidocbench_rocm`, CLI `omnidocbench-amd`→`omnidocbench-rocm`, template default `Model-AMD`→`Model-ROCm`, version → `0.2.0`. **Drop the legacy compatibility surface entirely** (no shim module, no legacy console-script, no second PyPI dist). Justification with evidence: `omnidocbench-amd` was never published to PyPI (404) and no pip downstream consumer exists (verified across the three model repos). Reversibility: low cost — a shim can be added later if a real consumer appears. Lives under `docs/adr/`.

### Task 1.4: Backend policy contract (EN + zh)

**Files:**
- Create: `contracts/backend-policy.md`
- Create: `contracts/backend-policy.zh-CN.md`

- [ ] **Step 1: Write `contracts/backend-policy.md`.** Sections: (1) First-class ROCm backends (HIP Runtime/HIP SDK, MIGraphX, ONNX Runtime MIGraphX EP, PyTorch-ROCm, vLLM-ROCm, llama.cpp-HIP); (2) Transitional backend — DirectML, permitted only on Windows where an equivalent ROCm/MIGraphX capability is unavailable, with the six conditions from spec §V verbatim (label `compatibility fallback`; no ROCm-native badge; provenance records real EP; never described as MIGraphX/ROCm-EP; target backend recorded as MIGraphX; deprecated→removed once a real path exists); (3) Out of scope — Vulkan, OpenVINO, general non-ROCm GPU backends; (4) Dimension separation — `platform` (linux-rocm|windows-hip) is distinct from OS, runtime/backend, execution provider, and compatibility status, which are carried by optional artifact fields; (5) explicit note: Windows MIGraphX is not currently production-ready; no roadmap date claimed. **Must be brand-clean** (it is in `contracts/`, a scanned path): use only `OmniDocBench-ROCm`/`omnidocbench-rocm`.
- [ ] **Step 2: Write `contracts/backend-policy.zh-CN.md`** as the Simplified-Chinese mirror of the same content.

### Task 1.5: Delete the stale AMD-era superpowers docs

**Files:**
- Delete: `docs/superpowers/specs/2026-07-12-amd-doc-parsing-platform-foundation-design.md`
- Delete: `docs/superpowers/plans/2026-07-12-amd-doc-parsing-platform-foundation.md`
- Delete: `docs/superpowers/HANDOFF-phaseA-paddleocrvl-onboarding-2026-07-12.md`

- [ ] **Step 1: Delete the three files.**
```bash
git rm docs/superpowers/specs/2026-07-12-amd-doc-parsing-platform-foundation-design.md \
       docs/superpowers/plans/2026-07-12-amd-doc-parsing-platform-foundation.md \
       docs/superpowers/HANDOFF-phaseA-paddleocrvl-onboarding-2026-07-12.md
```

### Task 1.6: Fix inbound references to the deleted docs

**Files:**
- Modify: `contracts/adapter.md` (remove the "Spec reference: §5.1 of `docs/superpowers/specs/2026-07-12-...`" line)
- Modify: any other file referencing `2026-07-12-amd-doc-parsing`

- [ ] **Step 1: Find all inbound references** (excluding the deleted docs' own directory):
```bash
grep -RnE '2026-07-12-amd-doc-parsing' . --exclude-dir=.git --exclude-dir=docs/superpowers
```
- [ ] **Step 2: Remove each hit.** In `contracts/adapter.md`, delete the blockquote line `> Spec reference: §5.1 of \`docs/superpowers/specs/2026-07-12-amd-doc-parsing-platform-foundation-design.md\`.`. Leave the rest of `adapter.md` untouched (its R6 rebrand is Task 4.3). Fix any other hits found in Step 1 by removing the dead reference.

### Task 1.7: Verify + commit

- [ ] **Step 1: Verify tests still green** (no code changed, but confirm):
```bash
python -m pytest -q
```
Expected: all pass.
- [ ] **Step 2: Commit.**
```bash
git add docs/audits/2026-07-omnidocbench-rocm-migration-audit.md \
        docs/adr/0001-rocm-project-boundary.md \
        docs/adr/0002-package-and-cli-migration.md \
        contracts/backend-policy.md contracts/backend-policy.zh-CN.md \
        contracts/adapter.md
git commit -m "docs: define OmniDocBench-ROCm scope and migration

Co-Authored-By: Claude <noreply@anthropic.com>"
```
(The `git rm` from Task 1.5 is already staged.)

---

## Commit 2 — `refactor: rename package and CLI to omnidocbench-rocm`

Scope: rename the package directory, all internal imports + docstrings, `pyproject.toml`, `scripts/check_conformance.py`, all test imports, `__version__`, CLI `prog`, schema `$id`. **Intentional residuals left for Task 3** (the "legacy dependency surface"): the conformance dependency-check literal in `omnidocbench_rocm/conformance.py` (line ~64) and the two fixture `dependencies` lines still say `omnidocbench-amd` — these are consistent with each other so tests stay green, and Task 3 switches them. No brand gate exists yet, so Commit 2 is green.

### Task 2.1: Rename the package directory

- [ ] **Step 1: git mv the package** (preserves history):
```bash
git mv engine/omnidocbench_amd engine/omnidocbench_rocm
```

### Task 2.2: Update engine internals (imports, docstrings, prog, version, $id)

**Files:**
- Modify: every file under `engine/omnidocbench_rocm/`
- Modify: `contracts/artifact-schema.json` (`$id` only)

- [ ] **Step 1: Apply the identifier/CLI/docstring transform** across the package, EXCEPT the conformance dependency-check literal in `conformance.py` (the line containing `"omnidocbench-amd" not in`). For every other occurrence: `omnidocbench_amd`→`omnidocbench_rocm` and `omnidocbench-amd`→`omnidocbench-rocm`.
- [ ] **Step 2: Set `engine/omnidocbench_rocm/__init__.py`** to:
```python
__version__ = "0.2.0"
```
- [ ] **Step 3: Set the CLI prog in `engine/omnidocbench_rocm/cli.py`** — change `p = argparse.ArgumentParser(prog="omnidocbench-amd")` to:
```python
    p = argparse.ArgumentParser(prog="omnidocbench-rocm")
```
(The `import omnidocbench_amd` at top of cli.py and the `omnidocbench_amd.__version__` references become `omnidocbench_rocm` via the Step-1 transform.)
- [ ] **Step 4: Change the schema `$id` in `contracts/artifact-schema.json`:**
```json
  "$id": "https://omnidocbench-rocm/schemas/artifact-schema.json",
```
- [ ] **Step 5: Verify the only intentional residual** is the conformance dependency check:
```bash
grep -RnE 'omnidocbench[-_]amd' engine/
```
Expected: exactly the line(s) in `engine/omnidocbench_rocm/conformance.py` containing the dependency-check literal and its failure message string — no other hits.

### Task 2.3: Update `pyproject.toml`

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Replace the whole file with:**
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "omnidocbench-rocm"
version = "0.2.0"
description = "OmniDocBench-ROCm: open adaptation, evaluation, reproduction, and collaboration platform for document-parsing models on the AMD ROCm software stack."
readme = "README.md"
requires-python = ">=3.10"
license = { text = "Apache-2.0" }
dependencies = [
  "huggingface_hub>=0.24",
  "jsonschema>=4",
  "pyyaml>=6",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-cov", "cookiecutter>=2", "build"]
download = ["huggingface_hub>=0.24"]

[project.scripts]
omnidocbench-rocm = "omnidocbench_rocm.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["engine/omnidocbench_rocm"]

[tool.hatch.build.targets.wheel.force-include]
"contracts/artifact-schema.json" = "omnidocbench_rocm/data/artifact-schema.json"
```

### Task 2.4: Update `scripts/check_conformance.py`

**Files:**
- Modify: `scripts/check_conformance.py`

- [ ] **Step 1: Apply transform** — `omnidocbench_amd`→`omnidocbench_rocm` and `omnidocbench-amd`→`omnidocbench-rocm` throughout (import line + docstring). The import becomes:
```python
from omnidocbench_rocm.conformance import check_repo, ConformanceReport, main, REQUIRED_README_SECTIONS
```

### Task 2.5: Update all test imports + the conformant-fixture adapter + fake_adapter

**Files:**
- Modify: `tests/test_backends.py`, `tests/test_cli.py`, `tests/test_artifact_utils.py`, `tests/test_contract_integration.py`, `tests/test_download.py`, `tests/test_schema.py`, `tests/test_stages.py`
- Modify: `tests/fixtures/conformant/adapter/run_adapter.py`
- Modify: `tests/fixtures/fake_adapter.py`

- [ ] **Step 1: Apply the identifier transform** (`omnidocbench_amd`→`omnidocbench_rocm`) across all listed test files and fixtures. In `tests/test_cli.py` also change the literal `argv = ["omnidocbench-amd", "score", ...]` to `["omnidocbench-rocm", "score", ...]` (the `omnidocbench-amd`→`omnidocbench-rocm` transform covers this). The `patch("omnidocbench_amd.cli.…")` targets become `patch("omnidocbench_rocm.cli.…")`.
- [ ] **Step 2: Verify no test imports the old name:**
```bash
grep -RnE 'omnidocbench[-_]amd' tests/test_*.py tests/fixtures/fake_adapter.py tests/fixtures/conformant/adapter/run_adapter.py
```
Expected: no hits. (The fixture `pyproject.toml` files still contain `omnidocbench-amd` — that is the intentional Task-3 residual; do not touch them here.)

### Task 2.6: Reinstall + verify green

- [ ] **Step 1: Reinstall the renamed package editable:**
```bash
python -m pip install -e ".[dev]"
```
- [ ] **Step 2: Confirm the new surface imports and the old is gone:**
```bash
python -c "import omnidocbench_rocm; print(omnidocbench_rocm.__version__)"
python -c "from omnidocbench_rocm.types import RunSummary; print('ok')"
python -c "import omnidocbench_amd" 2>&1 | grep -q "No module named" && echo "legacy import correctly absent"
```
Expected: `0.2.0`; `ok`; `legacy import correctly absent`.
- [ ] **Step 3: Full test suite:**
```bash
python -m pytest -q
```
Expected: all pass (same count as baseline).
- [ ] **Step 4: Confirm CLI runs:**
```bash
omnidocbench-rocm --help
```
Expected: usage text with `prog` `omnidocbench-rocm`.

### Task 2.7: Commit

- [ ] **Step 1:**
```bash
git add -A
git commit -m "refactor: rename package and CLI to omnidocbench-rocm

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Commit 3 — `refactor: drop legacy omnidocbench-amd surface; conformance requires omnidocbench-rocm`

Scope (TDD): switch the conformance dependency check + both fixtures to `omnidocbench-rocm`; make `get_backend("windows-hip")` raise an explicit honest error; make `provision_cdm` honest. After this commit, `grep -RnE 'omnidocbench[-_]amd' engine/ tests/ scripts/ pyproject.toml` returns nothing.

### Task 3.1 (TDD): conformance requires `omnidocbench-rocm`

**Files:**
- Test: `tests/test_conformance.py`
- Modify: `engine/omnidocbench_rocm/conformance.py` (dependency-check literal + message)
- Modify: `tests/fixtures/conformant/pyproject.toml`, `tests/fixtures/conformant/README.md`, `tests/fixtures/conformant/README.zh-CN.md`
- Modify: `tests/fixtures/nonconformant/pyproject.toml`

**Interfaces:**
- Produces: `check_repo()` now requires the literal `omnidocbench-rocm` in a model repo's `pyproject.toml`; failure message `pyproject.toml does not depend on omnidocbench-rocm`.

- [ ] **Step 1: Add a failing test** to `tests/test_conformance.py` (append):
```python
def test_old_engine_dep_fails_conformance(tmp_path):
    """A repo that still depends on the old omnidocbench-amd is non-conformant."""
    import shutil
    src = FIX / "conformant"
    dst = tmp_path / "repo"
    shutil.copytree(src, dst)
    pp = dst / "pyproject.toml"
    pp.write_text(pp.read_text().replace("omnidocbench-rocm", "omnidocbench-amd"))
    report = check_repo(dst)
    assert not report.ok
    assert any("omnidocbench-rocm" in f for f in report.failures)
```
- [ ] **Step 2: Run it — expect FAIL** (the check still looks for `omnidocbench-amd`):
```bash
python -m pytest tests/test_conformance.py::test_old_engine_dep_fails_conformance -q
```
Expected: FAIL (the fixture currently says `omnidocbench-amd`, so `check_repo` passes and `report.ok` is True → assertion fails).
- [ ] **Step 3: Switch the dependency check** in `engine/omnidocbench_rocm/conformance.py`:
```python
    if not pp.exists() or "omnidocbench-rocm" not in pp.read_text():
        r.add("pyproject.toml does not depend on omnidocbench-rocm")
```
- [ ] **Step 4: Update both fixtures** — in `tests/fixtures/conformant/pyproject.toml` and `tests/fixtures/nonconformant/pyproject.toml` change the dependency to `omnidocbench-rocm>=0.2.0`, and in the conformant `pyproject.toml` description change `omnidocbench-amd` → `omnidocbench-rocm`. Also apply the `omnidocbench-amd`→`omnidocbench-rocm` transform to `tests/fixtures/conformant/README.md` and `README.zh-CN.md`.
- [ ] **Step 5: Run the conformance tests — expect PASS:**
```bash
python -m pytest tests/test_conformance.py -q
```
Expected: all pass, including the new test and the existing conformant/nonconformant tests.

### Task 3.2 (TDD): honest `windows-hip` backend error

**Files:**
- Test: `tests/test_backends.py`
- Modify: `engine/omnidocbench_rocm/backends/__init__.py`

**Interfaces:**
- Produces: `get_backend("windows-hip")` raises `NotImplementedError`; `get_backend("linux-rocm")` returns `LinuxRocmBackend`; unknown platform still raises `ValueError`.

- [ ] **Step 1: Add failing tests** to `tests/test_backends.py` (append):
```python
import pytest
from omnidocbench_rocm.backends import get_backend


def test_windows_hip_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="windows-hip"):
        get_backend("windows-hip")


def test_linux_rocm_backend_resolves():
    b = get_backend("linux-rocm")
    assert b.__class__.__name__ == "LinuxRocmBackend"


def test_unknown_platform_raises_value_error():
    with pytest.raises(ValueError):
        get_backend("does-not-exist")
```
- [ ] **Step 2: Run — expect FAIL** on `test_windows_hip_raises_not_implemented` (current code lazy-imports a missing module → `ModuleNotFoundError`, not `NotImplementedError`):
```bash
python -m pytest tests/test_backends.py -q
```
Expected: FAIL (`ModuleNotFoundError: No module named 'omnidocbench_rocm.backends.windows_hip'`).
- [ ] **Step 3: Replace `engine/omnidocbench_rocm/backends/__init__.py` with:**
```python
from __future__ import annotations
from pathlib import Path
from .base import Backend
from .linux_rocm import LinuxRocmBackend

__all__ = ["Backend", "LinuxRocmBackend", "get_backend"]

_WINDOWS_HIP_NOT_IMPLEMENTED = (
    "The 'windows-hip' backend is planned/onboarding and not yet implemented. "
    "Linux-ROCm is the only implemented backend today; see "
    "contracts/backend-policy.md for the platform roadmap."
)


def get_backend(platform: str, checkout: Path | None = None) -> Backend:
    """Return the platform backend.

    Only ``linux-rocm`` is implemented today. ``windows-hip`` is planned
    (onboarding) and raises a clear, honest error rather than pretending a
    backend exists. See ``contracts/backend-policy.md``.
    """
    if platform == "linux-rocm":
        return LinuxRocmBackend(checkout=checkout)
    if platform == "windows-hip":
        raise NotImplementedError(_WINDOWS_HIP_NOT_IMPLEMENTED)
    raise ValueError(f"unknown platform: {platform}")
```
- [ ] **Step 4: Run — expect PASS:**
```bash
python -m pytest tests/test_backends.py -q
```
Expected: all pass.

### Task 3.3: Honest `provision_cdm` (no bogus path)

**Files:**
- Modify: `engine/omnidocbench_rocm/backends/linux_rocm.py`

- [ ] **Step 1: Replace the `provision_cdm` body** (the method whose body prints a reference to a nonexistent `cdm/setup-linux.sh`) with:
```python
    def provision_cdm(self) -> None:
        # CDM provisioning is partially scaffolded (Linux) and not wired
        # end-to-end; Windows CDM is planned. Do not reference a toolchain
        # path that does not exist. See contracts/backend-policy.md.
        print("[cdm] linux-rocm: CDM provisioning not yet implemented (planned)")
```
- [ ] **Step 2: Verify no nonexistent-path references and no old brand in engine:**
```bash
grep -RnE 'omnidocbench[-_]amd|engine/omnidocbench_rocm/cdm' engine/
```
Expected: no hits.

### Task 3.4: Verify + commit

- [ ] **Step 1: Full suite green + no residuals in code:**
```bash
python -m pytest -q
grep -RnE 'omnidocbench[-_]amd' engine/ tests/ scripts/ pyproject.toml
```
Expected: all tests pass; grep returns no hits.
- [ ] **Step 2: Commit.**
```bash
git add -A
git commit -m "refactor: drop legacy omnidocbench-amd surface; conformance requires omnidocbench-rocm

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Commit 4 — `refactor: migrate contracts and templates to ROCm`

Scope (TDD where applicable): schema optional fields; contracts rebrand + R6 Vulkan/DirectML fix; cookiecutter `Model-ROCm` default; template dep/CLI/URLs/model_card; **Makefile `eval-linux`/`eval-windows` split + test**; template docs (DirectML fallback-only, no Vulkan rec); `test_template.py` default assertion.

### Task 4.1 (TDD): schema optional fields (v1 preserved)

**Files:**
- Test: `tests/test_schema.py`
- Modify: `contracts/artifact-schema.json`

**Interfaces:**
- Produces: `model_card` and `provenance` `$defs` accept optional `backend`, `execution_provider`, `backend_family`, `compatibility_status`, `target_backend`. Existing v1 artifacts still validate.

- [ ] **Step 1: Add failing tests** to `tests/test_schema.py` (append):
```python
from omnidocbench_rocm.schema import validate_artifact


def test_model_card_accepts_optional_backend_fields():
    card = {
        "schema_version": 1, "model_id": "x", "model_version": "0.1",
        "platforms": ["linux-rocm"], "badge": {"linux-rocm": "community"},
        "eval_date": "2026-07-19", "omnidocbench_version": "v1.6",
        "overall": None, "hardware": {}, "artifacts": {},
        "backend": "vllm-rocm", "execution_provider": "ROCMExecutionProvider",
        "backend_family": "rocm", "compatibility_status": "first-class",
        "target_backend": "migraphx",
    }
    validate_artifact("model_card", card)  # must not raise


def test_existing_v1_artifact_still_validates():
    minimal = {
        "schema_version": 1, "model_id": "x", "model_version": "0.1",
        "platforms": ["linux-rocm"], "badge": {"linux-rocm": "community"},
        "eval_date": "2026-07-19", "omnidocbench_version": "v1.6",
        "overall": None, "hardware": {}, "artifacts": {},
    }
    validate_artifact("model_card", minimal)  # must not raise
```
- [ ] **Step 2: Run — expect FAIL** on `test_model_card_accepts_optional_backend_fields`:
```bash
python -m pytest tests/test_schema.py -q
```
Expected: PASS for the v1 artifact (jsonschema allows unknown props by default) but if a strict test fails, proceed; the real requirement is the optional fields are *documented* in the schema. (jsonschema Draft202012 permits additional properties unless `additionalProperties: false`, so existing tests pass. If both already pass, the test still documents intent — keep it.)
- [ ] **Step 3: Add the optional fields** to both `model_card.properties` and `provenance.properties` in `contracts/artifact-schema.json` (insert after the last existing property in each block):
```json
        "backend": {"type": "string"},
        "execution_provider": {"type": "string"},
        "backend_family": {"type": "string"},
        "compatibility_status": {"type": "string"},
        "target_backend": {"type": "string"}
```
(The `$id` was already changed to `omnidocbench-rocm` in Task 2.2.)
- [ ] **Step 4: Run — expect PASS:**
```bash
python -m pytest tests/test_schema.py -q
```
Expected: all pass.

### Task 4.2: Cookiecutter default `Model-ROCm`

**Files:**
- Modify: `template/cookiecutter.json`

- [ ] **Step 1: Replace `template/cookiecutter.json` with:**
```json
{
  "repo_name": "Model-ROCm",
  "model_slug": "model",
  "model_id": "model",
  "model_version": "0.1.0",
  "license": ["Apache-2.0", "MIT"]
}
```

### Task 4.3: Template `pyproject.toml` dependency + name

**Files:**
- Modify: `template/{{cookiecutter.repo_name}}/pyproject.toml`

- [ ] **Step 1: Replace the dependencies line:**
```toml
[project]
name = "{{cookiecutter.repo_name | lower}}"
version = "{{cookiecutter.model_version}}"
license = { text = "{{cookiecutter.license}}" }
dependencies = ["omnidocbench-rocm>=0.2.0"]
[project.optional-dependencies]
dev = ["pytest"]
```

### Task 4.4 (TDD): Makefile platform-target fix

**Files:**
- Test: `tests/test_makefile_targets.py`
- Modify: `template/{{cookiecutter.repo_name}}/Makefile`

**Interfaces:**
- Produces: two separate recipes `eval-linux` (passes `--platform linux-rocm`, results to `linux-rocm/`) and `eval-windows` (passes `--platform windows-hip`, results to `windows-hip/`); no shared `PLATFORM` default between them; CLI is `omnidocbench-rocm`.

- [ ] **Step 1: Create the failing test `tests/test_makefile_targets.py`:**
```python
"""Assert the template Makefile's eval-linux/eval-windows targets pass the
correct --platform (spec §VIII: the old shared-PLATFORM-default bug, where
`make eval-windows` silently ran Linux, must stay fixed). Parses recipe text
rather than invoking make (no render needed)."""
from pathlib import Path

MAKEFILE = Path(__file__).resolve().parent.parent / "template" / "{{cookiecutter.repo_name}}" / "Makefile"


def _recipe(target: str) -> str:
    text = MAKEFILE.read_text()
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith(f"{target}:"))
    body = []
    for l in lines[start + 1:]:
        if l and not l.startswith("\t") and not l.startswith(" "):
            break
        body.append(l)
    return "\n".join(body)


def test_targets_are_separate_recipes():
    text = MAKEFILE.read_text()
    assert "eval-linux eval-windows:" not in text
    assert text.count("eval-linux:") == 1
    assert text.count("eval-windows:") == 1


def test_eval_linux_uses_linux_rocm():
    r = _recipe("eval-linux")
    assert "--platform linux-rocm" in r
    assert r.rstrip().endswith("linux-rocm")


def test_eval_windows_uses_windows_hip():
    r = _recipe("eval-windows")
    assert "--platform windows-hip" in r
    assert r.rstrip().endswith("windows-hip")
```
- [ ] **Step 2: Run — expect FAIL:**
```bash
python -m pytest tests/test_makefile_targets.py -q
```
Expected: FAIL (current Makefile has the shared `eval-linux eval-windows:` rule with `$(PLATFORM)`).
- [ ] **Step 3: Replace `template/{{cookiecutter.repo_name}}/Makefile` with:**
```makefile
PLATFORM ?= linux-rocm
VERSION  ?= v16
REVISION ?= v1.6
MODEL_ID ?= {{cookiecutter.model_id}}

setup-linux:
	bash adapter/setup/00-install-deps.sh
setup-windows:
	powershell -ExecutionPolicy Bypass -File adapter\setup\00-install-deps.ps1

demo:
	OUT=$$(mktemp -d); omnidocbench-rocm infer --adapter adapter/run_adapter.py --img-dir examples --out-dir $$OUT --platform $(PLATFORM); ls $$OUT

eval-linux:
	omnidocbench-rocm run --stage all --platform linux-rocm --version $(VERSION) --revision $(REVISION) \
	  --adapter adapter/run_adapter.py --model-id $(MODEL_ID) \
	  --git-commit $$(git rev-parse HEAD) --results-dir results/omnidocbench/$(VERSION)/linux-rocm

eval-windows:
	omnidocbench-rocm run --stage all --platform windows-hip --version $(VERSION) --revision $(REVISION) \
	  --adapter adapter/run_adapter.py --model-id $(MODEL_ID) \
	  --git-commit $$(git rev-parse HEAD) --results-dir results/omnidocbench/$(VERSION)/windows-hip

publish:
	omnidocbench-rocm conformance . && echo CONFORMANT

smoke-test:
	python -m pytest
```
- [ ] **Step 4: Run — expect PASS:**
```bash
python -m pytest tests/test_makefile_targets.py -q
```
Expected: all pass.

### Task 4.5: Rebrand remaining template internals (CLI + URLs + docs)

**Files (apply transform `omnidocbench-amd`→`omnidocbench-rocm`, `omnidocbench_amd`→`omnidocbench_rocm`, `OmniDocBench-AMD`→`OmniDocBench-ROCm`, and any `github.com/AIwork4me/OmniDocBench-AMD`→`github.com/AIwork4me/OmniDocBench-ROCm`):**
- Modify: `template/{{cookiecutter.repo_name}}/.github/workflows/ci.yml`
- Modify: `template/{{cookiecutter.repo_name}}/CONTRIBUTING.md`
- Modify: `template/{{cookiecutter.repo_name}}/README.md`
- Modify: `template/{{cookiecutter.repo_name}}/README.zh-CN.md`
- Modify: `template/{{cookiecutter.repo_name}}/adapter/run_adapter.py`
- Modify: `template/{{cookiecutter.repo_name}}/docs/how-it-works.md`
- Modify: `template/{{cookiecutter.repo_name}}/docs/reproducibility.md`

- [ ] **Step 1: Apply the four transforms** across the listed files. For GitHub URLs, ensure every occurrence points to `https://github.com/AIwork4me/OmniDocBench-ROCm`.
- [ ] **Step 2: Verify template is brand-clean:**
```bash
grep -RnE 'omnidocbench[-_]amd|OmniDocBench-AMD|AIwork4me/OmniDocBench-AMD' template/
```
Expected: no hits.

### Task 4.6: Template `docs/backends.md` — DirectML fallback-only, no Vulkan recommendation

**Files:**
- Modify: `template/{{cookiecutter.repo_name}}/docs/backends.md`

- [ ] **Step 1: Edit the backend-recommendation table** so the Windows VLM cell no longer recommends Vulkan. Change any `llama.cpp/GGUF (HIP or Vulkan)` to `llama.cpp/GGUF (HIP)`, and add a line below the table: "DirectML is a **temporary Windows compatibility fallback** only (used where an equivalent ROCm/MIGraphX path is not yet available); it is not a first-class backend. See the platform repo's `contracts/backend-policy.md`. Vulkan is out of scope."

### Task 4.7: Template `model_card.json` — optional fields + ROCm brand

**Files:**
- Modify: `template/{{cookiecutter.repo_name}}/model_card.json`

- [ ] **Step 1: Update to use the new optional fields and ROCm branding.** Set content (a valid `model_card` v1 with the new optional keys, `community-wanted` badges, `overall: null`):
```json
{
  "schema_version": 1,
  "model_id": "{{cookiecutter.model_id}}",
  "model_version": "{{cookiecutter.model_version}}",
  "platforms": ["linux-rocm", "windows-hip"],
  "badge": {
    "linux-rocm": "community-wanted",
    "windows-hip": "community-wanted"
  },
  "eval_date": "",
  "omnidocbench_version": "v1.6",
  "overall": null,
  "hardware": {},
  "artifacts": {},
  "backend": "",
  "execution_provider": "",
  "backend_family": "rocm",
  "compatibility_status": "first-class",
  "target_backend": ""
}
```
- [ ] **Step 2: Verify it validates** (after install):
```bash
python -c "import json; from omnidocbench_rocm.schema import validate_artifact; validate_artifact('model_card', json.load(open('template/{{cookiecutter.repo_name}}/model_card.json'))); print('valid')"
```
Expected: `valid`.

### Task 4.8: `test_template.py` — `SmokeModel-ROCm`

**Files:**
- Modify: `tests/test_template.py`

- [ ] **Step 1: Change `SmokeModel-AMD` → `SmokeModel-ROCm`** in both `extra_context` calls. (Leaves the rest of the test logic intact.)
- [ ] **Step 2: Run the template tests:**
```bash
python -m pytest tests/test_template.py -q
```
Expected: all pass (render → conformance → smoke).

### Task 4.9: Contracts rebrand + R6 fix

**Files:**
- Modify: `contracts/adapter.md`, `contracts/badge-policy.md`, `contracts/conformance.md`

- [ ] **Step 1: Apply the transform** (`omnidocbench-amd`→`omnidocbench-rocm`, `omnidocbench_amd`→`omnidocbench_rocm`, `OmniDocBench-AMD`→`OmniDocBench-ROCm`, `Model-AMD`→`Model-ROCm`, `AMD Doc Parsing`→`OmniDocBench-ROCm`) across all three files.
- [ ] **Step 2: In `contracts/adapter.md` R6**, change the Windows VLM recommendation from `llama.cpp/GGUF (HIP or Vulkan)` to `llama.cpp/GGUF (HIP)`, and reframe the Windows ONNX row as "DirectML compatibility fallback (target: MIGraphX / ONNX Runtime MIGraphX EP when available)". Add the note that Vulkan is out of scope.
- [ ] **Step 3: Verify contracts are brand-clean:**
```bash
grep -RnE 'omnidocbench[-_]amd|OmniDocBench-AMD|AMD Doc Parsing|Model-AMD' contracts/
```
Expected: no hits.

### Task 4.10: Verify + commit

- [ ] **Step 1: Full suite + render smoke:**
```bash
python -m pytest -q
python -c "from cookiecutter.main import cookiecutter; cookiecutter('template', no_input=True, output_dir='/tmp/c4')"
python /tmp/c4/Model-ROCm/adapter/run_adapter.py --img-dir /tmp/c4/Model-ROCm/examples --out-dir /tmp/c4smoke --platform linux-rocm --backend smoke && echo SMOKE_OK
grep -RnE 'omnidocbench[-_]amd|OmniDocBench-AMD|Model-AMD' template/ contracts/
```
Expected: tests pass; render produces `/tmp/c4/Model-ROCm`; `SMOKE_OK`; grep no hits.
- [ ] **Step 2: Commit.**
```bash
git add -A
git commit -m "refactor: migrate contracts and templates to ROCm

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Commit 5 — `ci: expand migration and package quality gates`

Scope (TDD): registry validator; CI matrix + quality gates + `permissions: contents: read`; governance files; registry.yaml/generator rebrand. (The brand-residue gate script + its CI step are added in Task 6.9, after docs are clean.)

### Task 5.1 (TDD): registry validator

**Files:**
- Test: `tests/test_registry_validation.py`
- Create: `scripts/validate_registry.py`

**Interfaces:**
- Produces: `validate_registry(rows: list[dict]) -> list[str]` (empty = valid); CLI `python scripts/validate_registry.py [hub/registry.yaml]` exits 0/1. Checks: model_id present; repo well-formed `owner/name`; platform keys in {linux-rocm, windows-hip}; badge in {verified, community, community-wanted}; overall is number|null; duplicate model_id; missing platform data.

- [ ] **Step 1: Create the failing test `tests/test_registry_validation.py`:**
```python
from pathlib import Path
import yaml
from scripts.validate_registry import validate_registry

GOOD = [{"model_id": "x", "repo": "AIwork4me/X-ROCm",
         "platforms": {"linux-rocm": {"badge": "verified", "overall": 95.0},
                       "windows-hip": {"badge": "community-wanted", "overall": None}}}]


def test_valid_registry():
    assert validate_registry(GOOD) == []


def test_duplicate_and_bad_fields():
    rows = [
        {"model_id": "x", "repo": "bad repo", "platforms": {}},
        {"model_id": "x", "repo": "AIwork4me/Y-ROCm",
         "platforms": {"linux-rocm": {"badge": "garbage", "overall": "high"}}},
    ]
    errs = validate_registry(rows)
    assert any("duplicate" in e for e in errs)
    assert any("illegal repo" in e for e in errs)
    assert any("missing platforms" in e for e in errs)
    assert any("bad badge" in e for e in errs)
    assert any("overall" in e for e in errs)


def test_real_registry_valid():
    reg = Path(__file__).resolve().parent.parent / "hub" / "registry.yaml"
    rows = yaml.safe_load(reg.read_text()) or []
    assert validate_registry(rows) == []
```
- [ ] **Step 2: Run — expect FAIL** (module missing):
```bash
python -m pytest tests/test_registry_validation.py -q
```
Expected: FAIL (`ModuleNotFoundError: scripts.validate_registry`).
- [ ] **Step 3: Create `scripts/validate_registry.py`:**
```python
#!/usr/bin/env python3
"""Validate hub/registry.yaml structure for the OmniDocBench-ROCm registry.

Checks each entry: model_id present; repo well-formed owner/name; platform
keys valid; badge enum; overall type (number|null); no duplicate model_id;
no missing platform data. Exit 0 = valid, 1 = invalid.
"""
from __future__ import annotations
import sys
from pathlib import Path
import yaml

PLATFORMS = {"linux-rocm", "windows-hip"}
BADGES = {"verified", "community", "community-wanted"}


def validate_registry(rows: list[dict]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for i, r in enumerate(rows):
        ctx = f"entry#{i}"
        if not isinstance(r, dict):
            errors.append(f"{ctx}: not a mapping"); continue
        mid = r.get("model_id")
        if not mid or not isinstance(mid, str):
            errors.append(f"{ctx}: missing model_id")
        elif mid in seen:
            errors.append(f"{ctx}: duplicate model_id '{mid}'")
        else:
            seen.add(mid)
        repo = r.get("repo")
        if not isinstance(repo, str) or repo.count("/") != 1 or any(c.isspace() for c in repo):
            errors.append(f"{ctx}: illegal repo '{repo}' (expected owner/name)")
        plats = r.get("platforms")
        if not isinstance(plats, dict) or not plats:
            errors.append(f"{ctx}: missing platforms data"); continue
        for k, v in plats.items():
            if k not in PLATFORMS:
                errors.append(f"{ctx}: unknown platform key '{k}'"); continue
            if not isinstance(v, dict):
                errors.append(f"{ctx}.{k}: not a mapping"); continue
            if v.get("badge") not in BADGES:
                errors.append(f"{ctx}.{k}: bad badge '{v.get('badge')}'")
            overall = v.get("overall")
            if overall is not None and not isinstance(overall, (int, float)):
                errors.append(f"{ctx}.{k}: overall must be number or null")
    return errors


def main(argv: list[str]) -> int:
    path = Path(argv[0]) if argv else Path("hub/registry.yaml")
    rows = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    errors = validate_registry(rows)
    if not errors:
        print(f"registry: valid ({len(rows)} models)"); return 0
    print("registry: INVALID")
    for e in errors:
        print(" -", e)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```
- [ ] **Step 4: Run — expect PASS:**
```bash
python -m pytest tests/test_registry_validation.py -q
python scripts/validate_registry.py hub/registry.yaml
```
Expected: tests pass; `registry: valid (3 models)`.

### Task 5.2: Governance files

**Files (Create — brand-clean, ROCm-branded, real content, no placeholders):**
- `CHANGELOG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SUPPORT.md`, `CITATION.cff`, `CODEOWNERS`
- `.github/ISSUE_TEMPLATE/bug-report.md`, `.github/ISSUE_TEMPLATE/feature-request.md`, `.github/ISSUE_TEMPLATE/model-onboarding.md`
- `.github/PULL_REQUEST_TEMPLATE.md`

- [ ] **Step 1: `CHANGELOG.md`** — top entry:
```markdown
# Changelog

## 0.2.0 — OmniDocBench-ROCm transition (2026-07-19)

- **Brand:** renamed the platform from OmniDocBench-AMD to **OmniDocBench-ROCm**;
  PyPI dist `omnidocbench-rocm`, Python package `omnidocbench_rocm`, CLI
  `omnidocbench-rocm`, template default `Model-ROCm`.
- **Legacy surface dropped:** no `omnidocbench-amd` shim/CLI/dist (it was never
  published and has no pip downstream consumers — see
  `docs/audits/2026-07-omnidocbench-rocm-migration-audit.md`).
- **Backend policy:** new `contracts/backend-policy.md` — first-class ROCm
  backends; DirectML is a temporary Windows compatibility fallback; Vulkan /
  OpenVINO out of scope.
- **Docs honesty:** `architecture.md` rewritten to match code (no fabricated
  Windows backend or CDM toolchain); `windows-hip` now raises an explicit
  not-implemented error.
- **Schema:** optional fields added to artifact schema v1 (backward-compatible;
  no version bump).
- **Template:** fixed `make eval-windows` silently running Linux; cookiecutter
  default `Model-ROCm`; dep `omnidocbench-rocm>=0.2.0`.
- **CI:** Python 3.10/3.11/3.12 matrix, package build + metadata checks,
  registry validation, brand-residue gate, `permissions: contents: read`.
```
  (`CHANGELOG.md` legitimately names the old brand — it is excluded from the brand gate.)
- [ ] **Step 2: `CONTRIBUTING.md`** — how to add a model (point to `docs/contribute-a-model.md`), the conformance gate (`omnidocbench-rocm conformance .`), badge tiers, CPU-only CI reality, code style. Brand-clean.
- [ ] **Step 3: `CODE_OF_CONDUCT.md`** — Contributor Covenant 2.1 (standard text).
- [ ] **Step 4: `SECURITY.md`** — report-vulnerability policy (report privately, no GPU/eval-result fabrication), supported versions (0.2.x).
- [ ] **Step 5: `SUPPORT.md`** — how to get help (GitHub Issues, `community-wanted` vs `community` vs `verified`, pointers to docs).
- [ ] **Step 6: `CITATION.cff`** — `title: OmniDocBench-ROCm`, version 0.2.0, repository `https://github.com/AIwork4me/OmniDocBench-ROCm`, license Apache-2.0.
- [ ] **Step 7: `CODEOWNERS`** — `* @AIwork4me` (or the maintainer handle).
- [ ] **Step 8: `.github/ISSUE_TEMPLATE/`** — three templates: `bug-report.md`, `feature-request.md`, `model-onboarding.md` (the last with fields: model_id, target platform(s), intended backend, badge goal). All brand-clean.
- [ ] **Step 9: `.github/PULL_REQUEST_TEMPLATE.md`** — checklist: conformance passes, no old-brand residue (`python scripts/check_brand.py`), tests green, docs updated, no fabricated results.
- [ ] **Step 10: Verify governance files are brand-clean** (CHANGELOG is the only one allowed to name the old brand):
```bash
grep -RnE 'omnidocbench[-_]amd|OmniDocBench-AMD|AMD Doc Parsing|Model-AMD' CHANGELOG.md CONTRIBUTING.md CODE_OF_CONDUCT.md SECURITY.md SUPPORT.md CITATION.cff CODEOWNERS .github/
```
Expected: hits only inside `CHANGELOG.md`.

### Task 5.3: Registry + generator rebrand

**Files:**
- Modify: `hub/registry.yaml` (comments only — data unchanged)
- Modify: `scripts/generate_registry.py` (docstring: soften the "mkdocs, sub-project 1" hub-site claim)

- [ ] **Step 1: In `hub/registry.yaml`** update the header comments to ROCm branding and state honestly: "Rendered as a Markdown comparison table by `scripts/generate_registry.py`. A hosted MkDocs hub site is planned, not yet implemented." Do not change any model_id/repo/badge/overall values.
- [ ] **Step 2: In `scripts/generate_registry.py`** docstring, change "the hub site (mkdocs, sub-project 1)" to "a Markdown comparison table (a hosted hub site is planned, not yet implemented)". Apply any `omnidocbench-amd`/`omnidocbench_amd` transform if present (none expected).

### Task 5.4: CI workflow — matrix + gates + permissions

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Replace `.github/workflows/ci.yml` with:**
```yaml
name: ci
on: [push, pull_request]
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ['3.10', '3.11', '3.12']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: python -m pytest -q
      - run: python -c "import omnidocbench_rocm; print(omnidocbench_rocm.__version__)"
      - run: omnidocbench-rocm --help
      - run: python scripts/check_conformance.py tests/fixtures/conformant
      - run: python -c "from cookiecutter.main import cookiecutter; cookiecutter('template', no_input=True, output_dir='/tmp/t')"
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e ".[dev]"
      - run: python scripts/validate_registry.py hub/registry.yaml
      - run: python scripts/check_brand.py
      - run: python -m build
      - run: |
          set -e
          ws=(dist/*.whl); test -e "$ws"
          python -m pip install --force-reinstall "$ws"
      - run: omnidocbench-rocm --help
      - run: python -c "import omnidocbench_rocm; from omnidocbench_rocm.types import RunSummary"
      - name: Rendered template conformance + smoke
        run: |
          set -e
          python -c "from cookiecutter.main import cookiecutter; cookiecutter('template', no_input=True, output_dir='/tmp/r')"
          python scripts/check_conformance.py /tmp/r/Model-ROCm
          python /tmp/r/Model-ROCm/adapter/run_adapter.py --img-dir /tmp/r/Model-ROCm/examples --out-dir /tmp/smoke --platform linux-rocm --backend smoke
```
  (Note: the `python scripts/check_brand.py` step runs the gate created in Task 6.9; it is present in the YAML now and will pass once Task 6 completes. If you prefer the gate step land in the same commit as the script, move this one line into Task 6.9 — either ordering is fine since both land before the PR is pushed.)
- [ ] **Step 2: Lint the YAML mentally / with python:**
```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('yaml ok')"
```
Expected: `yaml ok`.

### Task 5.5: Verify + commit

- [ ] **Step 1:**
```bash
python -m pytest -q
python scripts/validate_registry.py hub/registry.yaml
python -m build
```
Expected: tests pass; registry valid; wheel + sdist built under `dist/`.
- [ ] **Step 2: Commit.**
```bash
git add -A
git commit -m "ci: expand migration and package quality gates

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Commit 6 — `docs: complete ROCm project documentation`

Scope: rewrite READMEs (EN + zh) and `architecture.md` to match reality; rebrand `ci-reality.md` / `contribute-a-model.md`(.zh-CN) / `pitfalls.md`; add `governance.md` + `roadmap.md`; **add the brand-residue gate (`scripts/check_brand.py` + test)** now that every scanned file is clean. After this commit the gate passes.

### Task 6.1: Rewrite `README.md` (15-section structure, honest Current Status)

**Files:**
- Modify: `README.md` (full rewrite)

- [ ] **Step 1: Replace `README.md`** with a mature open-source landing page using these sections, all honest:
  1. **Hero / one-line value** — "OmniDocBench-ROCm: open adaptation, evaluation, reproduction, and collaboration for document-parsing models on the AMD ROCm software stack."
  2. **Current Status** — Linux-ROCm eval engine implemented (score path real; CDM partial); Windows-HIP backend planned/onboarding; registry is an initial placeholder (3 models, `community-wanted`, no scores yet); DirectML is a temporary Windows compatibility fallback in selected model repos.
  3. **Why OmniDocBench-ROCm** — comparable cross-model/cross-platform scores via a filesystem-decoupled adapter contract; tiered trust badges; honest CI.
  4. **Scope** — ROCm first-class / DirectML transitional / Vulkan+OpenVINO out of scope (link `contracts/backend-policy.md`). Include the verbatim line: "ROCm defines the long-term software-stack boundary. DirectML is only a temporary Windows compatibility fallback and is not a first-class project backend."
  5. **Architecture** — one-paragraph + link to `docs/architecture.md`.
  6. **Quick Start** — `pip install omnidocbench-rocm`; `omnidocbench-rocm --help`.
  7. **CLI** — subcommands list (`cdm`/`dataset`/`infer`/`score`/`publish`/`run`/`conformance`).
  8. **Supported Platforms** — `linux-rocm` (implemented); `windows-hip` (planned).
  9. **Evaluation and Reproducibility** — pinned dataset revision, full-set enforcement, provenance artifacts.
  10. **Trust and Badge Model** — verified/community/community-wanted; link `contracts/badge-policy.md` and `docs/ci-reality.md`.
  11. **Add a Model** — link `docs/contribute-a-model.md` and the cookiecutter template.
  12. **Registry** — "initial placeholder, not a leaderboard"; link `hub/registry.yaml`.
  13. **Roadmap** — link `docs/roadmap.md`.
  14. **Contributing** — link `CONTRIBUTING.md`.
  15. **Governance / Security / License** — links to `docs/governance.md`, `SECURITY.md`, `LICENSE` (Apache-2.0).
  GitHub URL `https://github.com/AIwork4me/OmniDocBench-ROCm` throughout. Brand-clean (no old-brand tokens).

### Task 6.2: Rewrite `README.zh-CN.md` (mirror)

**Files:**
- Modify: `README.zh-CN.md` (full rewrite)

- [ ] **Step 1: Replace `README.zh-CN.md`** with the Simplified-Chinese mirror of the 15-section README. Same facts, same honesty, same links. Brand-clean.

### Task 6.3: Rewrite `docs/architecture.md` to match reality

**Files:**
- Modify: `docs/architecture.md` (full rewrite)

- [ ] **Step 1: Replace `docs/architecture.md`** with a reality-correct version:
  - Title `# Architecture`; product name `OmniDocBench-ROCm`; topology uses `Model-ROCm/` and `engine/omnidocbench_rocm/`.
  - **Two backends section:** `linux-rocm` = implemented (score path via `pdf_validation.py` in the eval-venv; CDM = partial scaffold, not end-to-end); `windows-hip` = planned/onboarding (raises `NotImplementedError` today). Remove the fabricated "Windows / WSL boundary (absorbed)" section, the `cdm/setup-*.sh` / `score.ps1` / `score-cdm.sh` claims, and every `omnidocbench-amd-windows` reference.
  - Keep the accurate parts: the four-stage pipeline, filesystem-decoupled adapter contract, the Python 3.11/3.12 venv split, the config→save_name→result mapping, idempotency.
  - CDM ownership: state honestly that CDM provisioning is engine-owned but only partially scaffolded today (Linux), with Windows planned.
  - Brand-clean (scanned path): no `omnidocbench-amd`/`OmniDocBench-AMD`/`omnidocbench_amd`/`omnidocbench-amd-windows`/`AMD Doc Parsing`.

### Task 6.4: Rebrand `docs/ci-reality.md`

**Files:**
- Modify: `docs/ci-reality.md`

- [ ] **Step 1: Apply transform** (`omnidocbench-amd`→`omnidocbench-rocm`, `omnidocbench_amd`→`omnidocbench_rocm`, `OmniDocBench-AMD`→`OmniDocBench-ROCm`).
- [ ] **Step 2: Mark the aspirational GPU self-test honest.** In the "GPU test" table, change the "Engine self-test … `windows-hip` (Strix Halo)" row to mark `windows-hip` as **planned** (Linux-ROCm only today), or remove the windows-hip mention from that row. Keep the rest (no GPU runner, CPU-only CI, tiered badges) as-is — it is already accurate.

### Task 6.5: Rebrand `docs/contribute-a-model.md` + `.zh-CN.md`

**Files:**
- Modify: `docs/contribute-a-model.md`, `docs/contribute-a-model.zh-CN.md`

- [ ] **Step 1: Apply the full transform** (`omnidocbench-amd`→`omnidocbench-rocm`, `omnidocbench_amd`→`omnidocbench_rocm`, `OmniDocBench-AMD`→`OmniDocBench-ROCm`, `Model-AMD`→`Model-ROCm`, `AMD Doc Parsing`→`OmniDocBench-ROCm`, remove `omnidocbench-amd-windows` references). Update any `cookiecutter` example to produce `Model-ROCm` and use CLI `omnidocbench-rocm`. GitHub URLs → `OmniDocBench-ROCm`.

### Task 6.6: Rebrand `docs/pitfalls.md`

**Files:**
- Modify: `docs/pitfalls.md`

- [ ] **Step 1: Apply the transform** (`omnidocbench-amd`→`omnidocbench-rocm`, `omnidocbench_amd`→`omnidocbench_rocm`, remove `omnidocbench-amd-windows` references). Keep the CDM technical notes (`#posix`, `#grayscale`, `#cdm-zero`) but reframe any claim of a working Windows CDM toolchain as planned/not-yet-implemented where applicable.

### Task 6.7: Create `docs/governance.md` + `docs/roadmap.md`

**Files:**
- Create: `docs/governance.md`, `docs/roadmap.md`

- [ ] **Step 1: `docs/governance.md`** — maintainer model (single maintainer `AIwork4me` for now, path to add maintainers), badge authority (maintainers assign `verified`; conformance gate is automated), how decisions are recorded (ADRs under `docs/adr/`), security reporting pointer. Brand-clean.
- [ ] **Step 2: `docs/roadmap.md`** — honest, no fabricated dates: near-term = onboard PaddleOCR-VL / Unlimited-OCR / MinerU2.5 to the central registry with real Linux-ROCm scores; Windows-HIP backend onboarding; CDM provisioning end-to-end (Linux first); hosted hub site (planned). Mark each item as planned, not dated. Brand-clean.

### Task 6.8 (TDD): brand-residue gate

**Files:**
- Test: `tests/test_brand_residue.py`
- Create: `scripts/check_brand.py`

**Interfaces:**
- Produces: `find_residue(root: Path | None = None) -> list[tuple[str, int, str]]` (rel-path, line, token); CLI exits 0 (clean) / 1 (residue). Excludes `docs/superpowers/**`, `docs/audits/**`, `docs/adr/**`, `CHANGELOG.md`; skips `.git`/`__pycache__`/`.pytest_cache`/`dist`/`build`/`*.egg-info`.

- [ ] **Step 1: Create the failing test `tests/test_brand_residue.py`:**
```python
from pathlib import Path
from scripts.check_brand import find_residue

ROOT = Path(__file__).resolve().parent.parent


def test_repo_is_brand_clean():
    assert find_residue(ROOT) == [], find_residue(ROOT)


def test_exclusions_and_detection(tmp_path):
    (tmp_path / "README.md").write_text("bad: omnidocbench-amd\n")
    (tmp_path / "engine").mkdir()
    (tmp_path / "engine" / "x.py").write_text("# omnidocbench_amd\n")
    (tmp_path / "docs" / "superpowers").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "s.md").write_text("ok: omnidocbench-amd\n")
    (tmp_path / "docs" / "audits").mkdir(parents=True)
    (tmp_path / "docs" / "audits" / "a.md").write_text("ok: OmniDocBench-AMD\n")
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "docs" / "adr" / "0001.md").write_text("ok: omnidocbench-amd\n")
    (tmp_path / "CHANGELOG.md").write_text("ok: omnidocbench-amd\n")
    hits = find_residue(tmp_path)
    rels = sorted(h[0] for h in hits)
    assert rels == ["README.md", "engine/x.py"]
```
- [ ] **Step 2: Run — expect FAIL** on `test_repo_is_brand_clean` (the docs were just rewritten clean in 6.3–6.6, but the gate module does not exist yet):
```bash
python -m pytest tests/test_brand_residue.py -q
```
Expected: FAIL (`ModuleNotFoundError: scripts.check_brand`).
- [ ] **Step 3: Create `scripts/check_brand.py`:**
```python
#!/usr/bin/env python3
"""Brand-residue gate for OmniDocBench-ROCm.

Fails if any forbidden old-brand token appears outside the internal-record
exclusion set. The product/user-facing surface must be clean.

Excluded (internal engineering records that legitimately discuss the rename):
  docs/superpowers/**, docs/audits/**, docs/adr/**, CHANGELOG.md

Exit 0 = clean, 1 = residue found. Intended for CI and local use.
"""
from __future__ import annotations
import sys
from pathlib import Path

FORBIDDEN = (
    "OmniDocBench-AMD",
    "omnidocbench-amd",
    "omnidocbench_amd",
    "AMD Doc Parsing",
    "Model-AMD",
    "omnidocbench-amd-windows",
)

EXCLUDED_DIRS = ("docs/superpowers", "docs/audits", "docs/adr")
EXCLUDED_FILES = ("CHANGELOG.md",)
SKIP_NAMES = {".git", "__pycache__", ".pytest_cache", "dist", "build", ".eggs"}


def _excluded(rel_posix: str) -> bool:
    if rel_posix in EXCLUDED_FILES:
        return True
    for d in EXCLUDED_DIRS:
        if rel_posix == d or rel_posix.startswith(d + "/"):
            return True
    return False


def find_residue(root: Path | str | None = None) -> list[tuple[str, int, str]]:
    root = Path(root) if root else Path(__file__).resolve().parent.parent
    hits: list[tuple[str, int, str]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        parts = path.relative_to(root).parts
        if any(p in SKIP_NAMES or p.endswith(".egg-info") for p in parts):
            continue
        rel_posix = path.relative_to(root).as_posix()
        if _excluded(rel_posix):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for tok in FORBIDDEN:
            for i, line in enumerate(text.splitlines(), 1):
                if tok in line:
                    hits.append((rel_posix, i, tok))
    return hits


def main(argv: list[str]) -> int:
    root = Path(argv[0]) if argv else None
    hits = find_residue(root)
    if not hits:
        print("brand-residue: clean")
        return 0
    print("brand-residue: FORBIDDEN old-brand tokens found:")
    for f, i, tok in hits:
        print(f"  {f}:{i}: '{tok}'")
    print("Allowed only in: docs/superpowers/**, docs/audits/**, docs/adr/**, CHANGELOG.md")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```
- [ ] **Step 4: Run the gate — expect clean:**
```bash
python scripts/check_brand.py
python -m pytest tests/test_brand_residue.py -q
```
Expected: `brand-residue: clean`; tests pass. If the gate reports hits, fix the named files (they must be rebrand misses in scanned paths) and re-run until clean.

### Task 6.9: Verify + commit

- [ ] **Step 1: Full Phase-5-style verification (local):**
```bash
python -m pytest -q
python -m build
python -m pip install --force-reinstall dist/*.whl
omnidocbench-rocm --help
python -c "import omnidocbench_rocm; print(omnidocbench_rocm.__version__)"
python scripts/check_conformance.py tests/fixtures/conformant
python scripts/validate_registry.py hub/registry.yaml
python scripts/check_brand.py
python -c "from cookiecutter.main import cookiecutter; cookiecutter('template', no_input=True, output_dir='/tmp/c6')"
python /tmp/c6/Model-ROCm/adapter/run_adapter.py --img-dir /tmp/c6/Model-ROCm/examples --out-dir /tmp/c6smoke --platform linux-rocm --backend smoke && echo SMOKE_OK
```
Expected: every command succeeds; version `0.2.0`; brand-residue clean; `SMOKE_OK`. **Capture real output for the final report.**
- [ ] **Step 2: Commit.**
```bash
git add -A
git commit -m "docs: complete ROCm project documentation

Rewrites READMEs and architecture.md to match reality (no fabricated
Windows backend or CDM toolchain), rebrands the remaining docs, adds
governance/roadmap, and introduces the brand-residue gate.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Post-implementation: push, PR, gated remote rename

### Task 7.1: Push branch + open PR

- [ ] **Step 1: Confirm branch state** (6 commits on top of `1a5166f`):
```bash
git log --oneline main..HEAD
git status --short
```
Expected: 6 commits listed; clean tree.
- [ ] **Step 2: Push** (per memory `github-push-from-env`: trust the MITM proxy cert; `gh auth` already configured for AIwork4me):
```bash
git push -u origin refactor/omnidocbench-rocm
```
- [ ] **Step 3: Open the PR** with title `refactor: upgrade platform to OmniDocBench-ROCm`. PR body sections: summary, audit findings, the brand mapping table, the 6-commit list, verification output (paste Task 6.9 real output), the gated remote-rename checklist (Task 7.2), and the note that DirectML is a transitional fallback. End the PR body with the Claude Code generated-with line.

### Task 7.2: Remote rename — PREPARE ONLY, do not run until CI green + user go

- [ ] **Step 1: Do NOT run these yet.** They are the gated handoff. After CI on the PR is green and the user explicitly approves:
```bash
gh repo rename OmniDocBench-ROCm --repo AIwork4me/OmniDocBench-AMD --yes
git remote set-url origin https://github.com/AIwork4me/OmniDocBench-ROCm.git
git remote -v
gh repo view AIwork4me/OmniDocBench-ROCm
```
- [ ] **Step 2: Post-rename redirect check** (after the rename): confirm `https://github.com/AIwork4me/OmniDocBench-AMD` 301-redirects to `.../OmniDocBench-ROCm`. Report the result.

---

## Final delivery report (produce after Task 7.1)

Compile into the PR body / a final message:
1. Audit summary (from `docs/audits/...`).
2. Architecture decisions (ADR-0001, ADR-0002).
3. Modified/created/deleted file manifest.
4. Compatibility strategy (legacy surface dropped; evidence).
5. Test commands + real output (Task 6.9 captured output).
6. Incomplete items (any verification that could not run locally, e.g. actual GitHub Actions).
7. Risks (from spec §12).
8. Pre-rename checklist (Task 7.2).
9. PR title + body.

## Self-review notes

- Spec coverage: every spec section (§1–§13) maps to a task above — audit (1.1), ADRs (1.2–1.3), backend policy (1.4), stale-doc deletion (1.5), brand mapping + rename (2.x), legacy-surface drop + honest windows-hip (3.x), schema evolution (4.1), template + Makefile (4.2–4.8), contracts (4.9), registry validation (5.1), CI matrix (5.4), governance (5.2), README + architecture reality (6.1–6.6), governance/roadmap docs (6.7), brand gate (6.8), verification (6.9), push/PR/gated-rename (7.x).
- Documented refinement: brand gate moved from commit 3 to commit 6 (Task 6.8) so no intermediate commit is red.
- Type/name consistency: `get_backend`, `LinuxRocmBackend`, `validate_registry`, `find_residue`, `check_repo`, `RunSummary` used consistently; CLI `omnidocbench-rocm`; package `omnidocbench_rocm` throughout.
