# AMD Doc-Parsing Zone — Platform Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `omnidocbench-amd` platform repo (shared contracts + dual-platform eval engine + per-model repo template) so a new OmniDocBench v1.6 open-source model can be onboarded by copying a template and implementing one `run_adapter` function.

**Architecture:** Single platform repo `omnidocbench-amd` holds `contracts/` (the interface), `engine/` (a pip package with `linux-rocm` + `windows-hip` backends that orchestrates download→infer→score→publish and owns CDM provisioning), `template/` (cookiecutter per-model repo), `hub/` (registry), and `docs/`. Each model lives in its own repo created from the template and depends on the engine via pip. The adapter is filesystem-decoupled — the engine invokes it as a subprocess and consumes only `out_dir/<stem>.md` + `_run_stats.json`.

**Tech Stack:** Python 3.11 (eval-venv) + 3.12 (engine/adapter OK), pip packaging, JSON Schema (draft 2020-12), pytest, cookiecutter, mkdocs (hub), GitHub Actions (CPU CI). Linux/ROCm GPU: `onnxruntime-rocm` (ROCm EP) + vLLM. Windows/Strix Halo GPU: `onnxruntime-directml` (DirectML EP, per AMD Ryzen AI docs) + llama.cpp/GGUF.

## Global Constraints

- **10 GB NFS at `/workspace`**: the `omnidocbench-amd` repo lives at `/workspace/omnidocbench-amd` and stays CODE-ONLY. All heavy paths — dataset, predictions, venvs, weights, CDM toolchain, `.omnidocbench` checkout — resolve under `${OMNIDOCBENCH_AMD_DATA:-/root/ocr-eval/omnidocbench-amd-data}` (the 437 GB ext4). `.gitignore` excludes `data/`, `predictions/`, `*/.venv/`, `*.gguf`, `eval/.omnidocbench/`. See memory `workspace-10gb-nfs-storage-plan`.
- **Python split**: OmniDocBench scoring breaks on 3.12 → `score` stage runs in an eval-venv (3.11); `infer` runs in the model's venv (3.12 OK). The engine provisions the eval-venv.
- **Per-platform ONNX execution provider**: Linux/ROCm → `onnxruntime-rocm` (ROCm EP); Windows/Strix Halo → `onnxruntime-directml` (DirectML EP, `DmlExecutionProvider`) per [AMD Ryzen AI GPU docs](https://ryzenai.docs.amd.com/en/latest/gpu/ryzenai_gpu.html). Never use ROCm EP on Windows.
- **Adapter contract is filesystem-decoupled**: engine never imports the adapter; it consumes `out_dir/<image_stem>.md` + `_run_stats.json`. Per-page failure → that page scores zero, run continues. Never raise.
- **CDM never faked**: all-exception CDM → `formula_cdm_percent: null` + `metric_quality.formula_cdm.valid: false`. `publish` refuses to write an invalid CDM value.
- **Full-set enforcement**: refuse to publish official evidence when `_run_stats.limit_pages != null`.
- **Dataset revision pinned**: `download` pins the OmniDocBench HF revision (no `latest`).
- **License**: Apache 2.0 for platform + engine. New model repos default Apache 2.0; existing keep theirs.
- **Naming**: new model repos `<Model>-AMD`; existing `-ROCm` repos keep their names.
- **Idempotency**: every `setup.*` self-checks before doing work; re-run is a no-op or resumes.

---

## File Structure

**Create (new platform repo `/workspace/omnidocbench-amd/`):**

| Path | Responsibility |
|---|---|
| `pyproject.toml` | package metadata, deps, `omnidocbench-amd` CLI entry point |
| `.gitignore` | heavy paths (see Global Constraints) |
| `README.md` / `README.zh-CN.md` | zone landing (skeleton; full site = sub-project 1) |
| `LICENSE` | Apache 2.0 |
| `contracts/artifact-schema.json` | JSON Schema for `_run_stats` / `provenance` / `run_summary` / `model_card` (schema_version 1) |
| `contracts/adapter.md` | the `run_adapter` contract (canonical human-readable spec) |
| `contracts/conformance.md` | per-model repo conformance checklist |
| `contracts/badge-policy.md` | verified vs community rules |
| `engine/omnidocbench_amd/__init__.py` | package marker + version |
| `engine/omnidocbench_amd/types.py` | `Platform`, `AdapterConfig`, `PageStatus`, `RunSummary` |
| `engine/omnidocbench_amd/schema.py` | load + validate artifacts against `artifact-schema.json` |
| `engine/omnidocbench_amd/artifact_utils.py` | write/assemble provenance, run_summary, model_card (ported + standardized from `PaddleOCR-VL-ROCm/eval/artifact_utils.py`) |
| `engine/omnidocbench_amd/stages.py` | download / infer / score / publish orchestrator with venv dispatch + gating (ported from `PaddleOCR-VL-ROCm/eval/run_eval.py`) |
| `engine/omnidocbench_amd/backends/base.py` | `Backend` ABC: `ensure_checkout`, `provision_cdm`, `score` |
| `engine/omnidocbench_amd/backends/linux_rocm.py` | Linux/ROCm backend (native TeX Live CDM) |
| `engine/omnidocbench_amd/backends/windows_hip.py` | Windows/HIP backend (port from `omnidocbench-amd-windows/eval-infra/`) |
| `engine/omnidocbench_amd/cdm/setup-linux.sh` | idempotent Linux CDM toolchain |
| `engine/omnidocbench_amd/cdm/setup.ps1` / `setup.sh` | Windows CDM (absorbed) |
| `engine/omnidocbench_amd/cli.py` | argparse CLI wiring stages + cdm + dataset |
| `scripts/check_conformance.py` | validate a per-model repo against `contracts/`; exit 0/1 |
| `scripts/generate_registry.py` | render `hub/registry.yaml` → comparison table |
| `hub/registry.yaml` | model registry (source of truth) |
| `hub/site/` | mkdocs source (skeleton) |
| `template/cookiecutter.json` + `template/{{cookiecutter.repo_name}}/...` | per-model repo cookiecutter |
| `docs/contribute-a-model.md` (+ `.zh-CN.md`) | contributor walkthrough |
| `docs/architecture.md` / `docs/pitfalls.md` / `docs/ci-reality.md` | absorbed + new docs |
| `tests/` | contract, schema, stages, conformance, template tests (CPU) |
| `.github/workflows/ci.yml` | CPU CI: contract + template smoke + engine self-test |

**Modify:**
- `Unlimited-OCR-ROCm/docs/superpowers/specs/2026-07-12-amd-doc-parsing-platform-foundation-design.md` → move into `omnidocbench-amd/docs/superpowers/specs/` (Task 1).

**Port sources (read-only reference, do not modify):**
- `AIwork4me/PaddleOCR-VL-ROCm` → `eval/run_eval.py`, `eval/artifact_utils.py` (engine core).
- `AIwork4me/omnidocbench-amd-windows` → `eval-infra/02-cdm-environment/*`, `adapters/_template/*`, `docs/pitfalls.md`, `docs/architecture.md` (Windows backend + template + docs).

---

## Phase A — CPU-testable MVP foundation

### Task 1: Create the `omnidocbench-amd` repo skeleton

**Files:**
- Create: `/workspace/omnidocbench-amd/{pyproject.toml,.gitignore,README.md,README.zh-CN.md,LICENSE}`
- Create: `/workspace/omnidocbench-amd/docs/superpowers/{specs,plans}/` (empty)
- Move: `Unlimited-OCR-ROCm/docs/superpowers/specs/2026-07-12-amd-doc-parsing-platform-foundation-design.md` → `omnidocbench-amd/docs/superpowers/specs/`
- Copy: this plan → `omnidocbench-amd/docs/superpowers/plans/`

**Interfaces:** Produces the repo the rest of the tasks live in.

- [ ] **Step 1: Create the repo dir and move the spec in**

```bash
mkdir -p /workspace/omnidocbench-amd/docs/superpowers/{specs,plans}
git -C /workspace/omnidocbench-amd init -b main
# move the spec out of Unlimited-OCR-ROCm into the new repo
mv /workspace/Unlimited-OCR-ROCm/docs/superpowers/specs/2026-07-12-amd-doc-parsing-platform-foundation-design.md \
   /workspace/omnidocbench-amd/docs/superpowers/specs/
# copy this plan into the new repo too
cp /workspace/Unlimited-OCR-ROCm/docs/superpowers/plans/2026-07-12-amd-doc-parsing-platform-foundation.md \
   /workspace/omnidocbench-amd/docs/superpowers/plans/
```

- [ ] **Step 2: Write `.gitignore` (heavy paths off the 10 GB NFS)**

```gitignore
# heavy data — lives under $OMNIDOCBENCH_AMD_DATA (big disk), never in the repo
data/
predictions/
*/.venv/
.venv/
*.gguf
*.onnx
eval/.omnidocbench/
__pycache__/
*.pyc
.env.local
# CDM toolchain outputs
cdb-build/
```

- [ ] **Step 3: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "omnidocbench-amd"
version = "0.1.0"
description = "Shared dual-platform (Radeon/Linux + Ryzen AI MAX+ 395/Windows) OmniDocBench v1.6 eval engine + per-model repo template."
readme = "README.md"
requires-python = ">=3.10"
license = { text = "Apache-2.0" }
dependencies = [
  "huggingface_hub>=0.24",
  "pydantic>=2",
  "jsonschema>=4",
  "pyyaml>=6",
  "rich>=13",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-cov", "cookiecutter>=2"]
download = ["huggingface_hub>=0.24"]

[project.scripts]
omnidocbench-amd = "omnidocbench_amd.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["engine/omnidocbench_amd"]

[tool.hatch.build.targets.wheel.force-include]
"contracts/artifact-schema.json" = "omnidocbench_amd/data/artifact-schema.json"
```

- [ ] **Step 4: Write `README.md` + `README.zh-CN.md` skeletons**

```markdown
# omnidocbench-amd

The shared platform for the **AMD Doc Parsing** zone: run OmniDocBench v1.6
open-source document-parsing models on AMD hardware (Radeon + Linux/ROCm, and
Ryzen AI MAX+ 395 + Windows/HIP), with real eval data, out-of-the-box demos,
and bilingual docs.

- `contracts/` — the adapter interface, artifact schema, conformance checklist, badge policy.
- `engine/` — the dual-platform eval engine (pip package).
- `template/` — cookiecutter for a per-model repo.
- `hub/` — model registry + site.

See `docs/contribute-a-model.md` to add a model. Spec: `docs/superpowers/specs/`.
```

Write `README.zh-CN.md` as the optimized Chinese equivalent (mirror instructions + ModelScope first; not a literal translation).

- [ ] **Step 5: Add Apache 2.0 `LICENSE`**

```bash
curl -s https://www.apache.org/licenses/LICENSE-2.0.txt -o /workspace/omnidocbench-amd/LICENSE
```

- [ ] **Step 6: Commit**

```bash
cd /workspace/omnidocbench-amd
git add .
git commit -m "feat: scaffold omnidocbench-amd platform repo + move spec in"
```

---

### Task 2: Contract types + artifact JSON schema + validator

**Files:**
- Create: `engine/omnidocbench_amd/__init__.py`
- Create: `engine/omnidocbench_amd/types.py`
- Create: `contracts/artifact-schema.json`
- Create: `engine/omnidocbench_amd/schema.py`
- Test: `tests/test_schema.py`

**Interfaces:**
- Produces: `Platform`, `AdapterConfig`, `RunSummary`, `PageStatus` (types.py); `validate_artifact(name, obj)` (schema.py); `artifact-schema.json` (`schema_version: 1`).

- [ ] **Step 1: Write the failing test**

`tests/test_schema.py`:
```python
import json
from pathlib import Path
from omnidocbench_amd.schema import validate_artifact, SCHEMA_PATH
from omnidocbench_amd.types import RunSummary, PageStatus, AdapterConfig


def _run_stats_obj():
    return {
        "schema_version": 1,
        "count": 3, "ok": 2, "fail": 1, "fallback": 0, "limit_pages": None,
        "engine": "smoke",
        "stats": [
            {"image": "a.png", "status": "ok", "error": "", "seconds": 0.1, "attempts": 1},
            {"image": "b.png", "status": "failed: timeout", "error": "timeout", "seconds": 5.0, "attempts": 2},
        ],
    }


def test_run_stats_schema_valid():
    validate_artifact("run_stats", _run_stats_obj())  # no exception


def test_run_stats_rejects_missing_field():
    bad = _run_stats_obj(); del bad["count"]
    try:
        validate_artifact("run_stats", bad)
        assert False, "should have raised"
    except Exception:
        pass


def test_runsummary_roundtrip(tmp_path):
    rs = RunSummary(count=3, ok=2, fail=1, fallback=0, limit_pages=None,
                    stats=[PageStatus("a.png", "ok")], engine="smoke")
    p = tmp_path / "_run_stats.json"
    rs.write(p)
    back = RunSummary.from_run_stats(p)
    assert back.count == 3 and back.ok == 2 and back.fail == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /workspace/omnidocbench-amd && python -m pytest tests/test_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: omnidocbench_amd`.

- [ ] **Step 3: Write `engine/omnidocbench_amd/types.py`**

```python
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

Platform = str  # "linux-rocm" | "windows-hip"


@dataclass
class AdapterConfig:
    weights_dir: Path | None = None
    server_url: str = ""
    api_model_name: str = ""
    backend: str = ""               # vllm | llama-cpp-server | onnx-rocm(linux) | onnx-directml(windows) | smoke | ...
    extra: dict = field(default_factory=dict)


@dataclass
class PageStatus:
    image: str
    status: str                     # ok | failed: <reason> | fallback: <reason>
    error: str = ""
    seconds: float = 0.0
    attempts: int = 0


@dataclass
class RunSummary:
    count: int
    ok: int
    fail: int
    fallback: int
    limit_pages: int | None
    stats: list[PageStatus]
    engine: str = ""

    def to_run_stats(self) -> dict:
        return {
            "schema_version": 1,
            "count": self.count, "ok": self.ok, "fail": self.fail,
            "fallback": self.fallback, "limit_pages": self.limit_pages,
            "engine": self.engine,
            "stats": [asdict(s) for s in self.stats],
        }

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_run_stats(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @classmethod
    def from_run_stats(cls, path: Path) -> "RunSummary":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            count=d["count"], ok=d["ok"], fail=d["fail"], fallback=d["fallback"],
            limit_pages=d.get("limit_pages"),
            stats=[PageStatus(**s) for s in d.get("stats", [])],
            engine=d.get("engine", ""),
        )
```

- [ ] **Step 4: Write `contracts/artifact-schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://omnidocbench-amd/schemas/artifact-schema.json",
  "schema_version": 1,
  "$defs": {
    "run_stats": {
      "type": "object",
      "required": ["schema_version", "count", "ok", "fail", "fallback", "limit_pages", "stats"],
      "properties": {
        "schema_version": {"const": 1},
        "count": {"type": "integer"},
        "ok": {"type": "integer"},
        "fail": {"type": "integer"},
        "fallback": {"type": "integer"},
        "limit_pages": {"type": ["integer", "null"]},
        "engine": {"type": "string"},
        "stats": {"type": "array", "items": {
          "type": "object",
          "required": ["image", "status"],
          "properties": {
            "image": {"type": "string"},
            "status": {"type": "string"},
            "error": {"type": "string"},
            "seconds": {"type": "number"},
            "attempts": {"type": "integer"}
          }
        }}
      }
    },
    "provenance": {
      "type": "object",
      "required": ["schema_version", "created_at_utc", "git_commit", "platform", "engine_version", "model_id", "adapter_command", "dataset_manifest_path", "dataset_revision", "prediction_dir", "page_count", "ok_pages", "failed_pages", "metric_result_paths", "run_summary_paths", "run_stats_path"],
      "properties": {
        "schema_version": {"const": 1},
        "created_at_utc": {"type": "string"},
        "git_commit": {"type": "string"},
        "platform": {"enum": ["linux-rocm", "windows-hip"]},
        "engine_version": {"type": "string"},
        "model_id": {"type": "string"},
        "adapter_command": {"type": "string"},
        "vlm_server_url": {"type": "string"},
        "api_model_name": {"type": "string"},
        "scoring_config_path": {"type": "string"},
        "dataset_manifest_path": {"type": "string"},
        "dataset_revision": {"type": "string"},
        "prediction_dir": {"type": "string"},
        "page_count": {"type": "integer"},
        "ok_pages": {"type": "integer"},
        "failed_pages": {"type": "integer"},
        "fallback_pages": {"type": "integer"},
        "metric_result_paths": {"type": "array", "items": {"type": "string"}},
        "run_summary_paths": {"type": "array", "items": {"type": "string"}},
        "run_stats_path": {"type": "string"}
      }
    },
    "run_summary": {
      "type": "object",
      "required": ["schema_version", "save_name", "engine", "cdm", "prediction_count", "ok_pages", "failed_pages", "fallback_pages", "readme_metrics", "metric_quality"],
      "properties": {
        "schema_version": {"const": 1},
        "save_name": {"type": "string"},
        "engine": {"type": "string"},
        "cdm": {"type": "boolean"},
        "prediction_count": {"type": "integer"},
        "ok_pages": {"type": "integer"},
        "failed_pages": {"type": "integer"},
        "fallback_pages": {"type": "integer"},
        "readme_metrics": {
          "type": "object",
          "properties": {
            "text_edit_dist": {"type": ["number", "null"]},
            "reading_order_edit_dist": {"type": ["number", "null"]},
            "table_teds_percent": {"type": ["number", "null"]},
            "formula_cdm_percent": {"type": ["number", "null"]}
          }
        },
        "metric_quality": {
          "type": "object",
          "required": ["formula_cdm"],
          "properties": {"formula_cdm": {
            "type": "object", "required": ["valid"],
            "properties": {"valid": {"type": "boolean"}, "reason": {"type": "string"},
              "sample_count": {"type": ["integer", "null"]}, "exception_case_count": {"type": ["integer", "null"]}}
          }}
        }
      }
    },
    "model_card": {
      "type": "object",
      "required": ["schema_version", "model_id", "model_version", "platforms", "badge", "eval_date", "omnidocbench_version", "overall", "hardware", "artifacts"],
      "properties": {
        "schema_version": {"const": 1},
        "model_id": {"type": "string"},
        "model_version": {"type": "string"},
        "platforms": {"type": "array", "items": {"enum": ["linux-rocm", "windows-hip"]}},
        "badge": {"type": "object",
          "properties": {
            "linux-rocm": {"enum": ["verified", "community", "community-wanted"]},
            "windows-hip": {"enum": ["verified", "community", "community-wanted"]}
          }},
        "eval_date": {"type": "string"},
        "omnidocbench_version": {"type": "string"},
        "overall": {"type": ["number", "null"]},
        "submetrics": {"type": "object"},
        "hardware": {"type": "object",
          "properties": {"gpu": {"type": "string"}, "vram": {"type": "string"}, "rocm_driver": {"type": "string"}}},
        "artifacts": {"type": "object"}
      }
    }
  }
}
```

- [ ] **Step 5: Write `engine/omnidocbench_amd/schema.py`**

```python
from __future__ import annotations
import json
from importlib import resources
from pathlib import Path
from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).parent / "data" / "artifact-schema.json"
_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
_VALIDATORS = {k: Draft202012Validator(v) for k, v in _SCHEMA["$defs"].items()}


def validate_artifact(name: str, obj: dict) -> None:
    """Raise jsonschema.ValidationError if obj fails the named sub-schema."""
    if name not in _VALIDATORS:
        raise KeyError(f"unknown artifact: {name}")
    _VALIDATORS[name].validate(obj)
```

`engine/omnidocbench_amd/__init__.py`:
```python
__version__ = "0.1.0"
```

- [ ] **Step 6: Install dev + run tests to verify pass**

```bash
cd /workspace/omnidocbench-amd
pip install -e ".[dev]"
python -m pytest tests/test_schema.py -v
```
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add engine/ contracts/artifact-schema.json tests/test_schema.py
git commit -m "feat(contracts): artifact JSON schema + types + validator"
```

---

### Task 3: Port + standardize `artifact_utils.py`

**Files:**
- Create: `engine/omnidocbench_amd/artifact_utils.py`
- Test: `tests/test_artifact_utils.py`
- Reference: `AIwork4me/PaddleOCR-VL-ROCm/eval/artifact_utils.py`

**Interfaces:**
- Consumes: `RunSummary` (Task 2), `validate_artifact` (Task 2).
- Produces: `analyze_metric_quality(metric) -> dict`, `extract_readme_metrics(metric) -> dict`, `write_run_summary(...)`, `write_provenance(...)`, `write_model_card(...)`.

- [ ] **Step 1: Write the failing test**

`tests/test_artifact_utils.py`:
```python
import json
from pathlib import Path
from omnidocbench_amd import artifact_utils as au


def _metric(all_cdm_except=False):
    return {
        "text_block": {"page": {"Edit_dist": {"ALL": 0.034}}},
        "reading_order": {"page": {"Edit_dist": {"ALL": 0.129}}},
        "table": {"page": {"TEDS": {"ALL": 0.9424}}},
        "display_formula": {"page": {"CDM": {"ALL": 0.965}},
                            "metric_debug": {"CDM": {"sample_count": 10, "exception_case_count": 10 if all_cdm_except else 0}}},
    }


def test_readme_metrics_extracts_four():
    m = au.extract_readme_metrics(_metric())
    assert m["text_edit_dist"] == 0.034
    assert abs(m["table_teds_percent"] - 94.24) < 0.01
    assert m["formula_cdm_percent"] == 96.5


def test_invalid_cdm_nulled():
    m = au.extract_readme_metrics(_metric(all_cdm_except=True))
    assert m["formula_cdm_percent"] is None
    q = au.analyze_metric_quality(_metric(all_cdm_except=True))
    assert q["formula_cdm"]["valid"] is False


def test_write_run_summary_validates(tmp_path):
    rs_path = tmp_path / "_run_stats.json"
    rs_path.write_text(json.dumps({
        "schema_version": 1, "count": 1651, "ok": 1650, "fail": 1, "fallback": 0,
        "limit_pages": None, "engine": "official", "stats": []}))
    metric_path = tmp_path / "metric.json"
    metric_path.write_text(json.dumps(_metric()))
    out = tmp_path / "run_summary.json"
    au.write_run_summary(save_name="m_v16_quick_match", run_stats_path=rs_path,
                         metric_result_path=metric_path, destination=out, cdm=False)
    from omnidocbench_amd.schema import validate_artifact
    validate_artifact("run_summary", json.loads(out.read_text()))  # no exception
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_artifact_utils.py -v`
Expected: FAIL — `ModuleNotFoundError: omnidocbench_amd.artifact_utils`.

- [ ] **Step 3: Port `artifact_utils.py`**

Port `analyze_metric_quality`, `extract_readme_metrics`, `write_run_summary`, `write_provenance` verbatim in logic from `PaddleOCR-VL-ROCm/eval/artifact_utils.py` (fetch via `gh api repos/AIwork4me/PaddleOCR-VL-ROCm/contents/eval/artifact_utils.py -H "Accept: application/vnd.github.raw"`), then:
- Add `"schema_version": 1` to every emitted object (`run_summary`, `provenance`).
- In `write_run_summary`, after building `summary`, call `validate_artifact("run_summary", summary)`; in `write_provenance`, call `validate_artifact("provenance", provenance)`.
- Add the new `write_model_card` function:

```python
def write_model_card(*, destination, model_id, model_version, platforms, badge,
                     omnidocbench_version, overall, submetrics, hardware, artifacts, eval_date):
    card = {
        "schema_version": 1,
        "model_id": model_id, "model_version": model_version,
        "platforms": platforms, "badge": badge, "eval_date": eval_date,
        "omnidocbench_version": omnidocbench_version,
        "overall": overall, "submetrics": submetrics,
        "hardware": hardware, "artifacts": artifacts,
    }
    validate_artifact("model_card", card)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination
```

Keep `_nested`, `_nested_number`, `load_json`, `copy_metric_report` from the source unchanged.

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_artifact_utils.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add engine/omnidocbench_amd/artifact_utils.py tests/test_artifact_utils.py
git commit -m "feat(engine): port + standardize artifact_utils (schema v1, model_card)"
```

---

### Task 4: `stages.py` orchestrator (download/infer/score/publish)

**Files:**
- Create: `engine/omnidocbench_amd/stages.py`
- Create: `engine/omnidocbench_amd/_paths.py`
- Test: `tests/test_stages.py`
- Reference: `AIwork4me/PaddleOCR-VL-ROCm/eval/run_eval.py`

**Interfaces:**
- Consumes: `RunSummary` (Task 2), `artifact_utils` (Task 3).
- Produces: `stage_download`, `stage_infer`, `stage_score`, `stage_publish`, `run_stage`.

- [ ] **Step 1: Write the failing test (fake adapter → infer → artifacts)**

`tests/test_stages.py`:
```python
import json, subprocess, sys
from pathlib import Path
from omnidocbench_amd import stages


FAKE_ADAPTER = '''
from pathlib import Path
from omnidocbench_amd.types import RunSummary, PageStatus
IMG_EXT = {".png", ".jpg"}
def run_adapter(img_dir, out_dir, *, platform, config):
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    imgs = sorted(p for p in Path(img_dir).iterdir() if p.suffix.lower() in IMG_EXT)
    stats = []
    for i in imgs:
        (out_dir / f"{i.stem}.md").write_text(f"# {i.stem}\\n", encoding="utf-8")
        stats.append(PageStatus(i.name, "ok"))
    rs = RunSummary(len(imgs), len(imgs), 0, 0, None, stats, engine="smoke")
    rs.write(out_dir / "_run_stats.json")
    return rs.to_run_stats()
'''


def test_stage_infer_runs_adapter_subprocess(tmp_path, monkeypatch):
    img_dir = tmp_path / "imgs"; img_dir.mkdir()
    (img_dir / "a.png").write_bytes(b"x"); (img_dir / "b.png").write_bytes(b"x")
    adapter = tmp_path / "fake_adapter.py"; adapter.write_text(FAKE_ADAPTER)
    out_dir = tmp_path / "preds"
    summary = stages.stage_infer(
        adapter_path=adapter, img_dir=img_dir, out_dir=out_dir,
        platform="linux-rocm", config={})
    assert summary["count"] == 2 and summary["ok"] == 2
    assert (out_dir / "a.md").exists() and (out_dir / "_run_stats.json").exists()


def test_stage_publish_refuses_limited_subset(tmp_path):
    rs = tmp_path / "_run_stats.json"
    rs.write_text(json.dumps({"schema_version": 1, "count": 10, "ok": 10, "fail": 0,
                              "fallback": 0, "limit_pages": 10, "engine": "smoke", "stats": []}))
    try:
        stages._assert_full_set(rs)  # private helper used by publish
        assert False, "should refuse limited subset"
    except SystemExit:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stages.py -v`
Expected: FAIL — `ModuleNotFoundError: omnidocbench_amd.stages`.

- [ ] **Step 3: Write `engine/omnidocbench_amd/_paths.py` (NFS-safe data root)**

```python
import os
from pathlib import Path

def data_root() -> Path:
    """Heavy data root on the big disk, never the 10 GB NFS repo."""
    return Path(os.environ.get("OMNIDOCBENCH_AMD_DATA", "/root/ocr-eval/omnidocbench-amd-data"))

def dataset_dir(version: str) -> Path:
    return data_root() / "datasets" / version

def eval_venv(platform: str) -> Path:
    return data_root() / "eval-venv" / platform

def predictions_dir(model_id: str, platform: str) -> Path:
    return data_root() / "predictions" / model_id / platform
```

- [ ] **Step 4: Write `engine/omnidocbench_amd/stages.py`**

Port the gating + stage structure from `PaddleOCR-VL-ROCm/eval/run_eval.py` (`stage_download`, `stage_infer`, `_ensure_omnidocbench_checkout`, `_resolve_report_path`, `_validate_full_prediction_stats`), then:

```python
from __future__ import annotations
import json, subprocess, sys, importlib.util
from pathlib import Path
from . import artifact_utils as au
from .types import RunSummary
from ._paths import dataset_dir, eval_venv, predictions_dir

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".gif"}


def stage_download(version: str, revision: str | None = None) -> Path:
    """Pin revision; fetch OmniDocBench manifest + images to dataset_dir(version)."""
    from .download_omnidocbench import download_dataset
    if revision is None:
        raise SystemExit("OmniDocBench revision MUST be pinned for reproducibility (got None).")
    target = dataset_dir(version)
    resolved = download_dataset(repo_id="opendatalab/OmniDocBench", target=target, revision=revision)
    print(f"[download] OmniDocBench {version} ready: {resolved}")
    return target


def stage_infer(*, adapter_path: Path, img_dir: Path, out_dir: Path,
                platform: str, config: dict) -> dict:
    """Invoke the adapter as a SUBPROCESS (filesystem-decoupled). Never import it."""
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(adapter_path),
           "--img-dir", str(img_dir), "--out-dir", str(out_dir),
           "--platform", platform]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"adapter failed ({proc.returncode}):\n{proc.stderr}")
    rs_path = out_dir / "_run_stats.json"
    if not rs_path.exists():
        raise SystemExit(f"adapter wrote no _run_stats.json: {rs_path}")
    return json.loads(rs_path.read_text(encoding="utf-8"))


def _assert_full_set(run_stats_path: Path) -> None:
    rs = json.loads(Path(run_stats_path).read_text(encoding="utf-8"))
    if rs.get("limit_pages") is not None:
        raise SystemExit(
            f"Refusing to publish official evidence from limited predictions "
            f"(limit_pages={rs['limit_pages']}). Run full unbounded inference first.")


def stage_score(*, backend, predictions_dir: Path, version: str, cdm: bool,
                run_stats_path: Path) -> Path:
    """Run pdf_validation.py inside the backend's eval-venv (3.11)."""
    return backend.score(predictions_dir=predictions_dir, version=version, cdm=cdm,
                         run_stats_path=run_stats_path)


def stage_publish(*, model_id: str, platform: str, version: str, cdm: bool,
                  run_stats_path: Path, metric_result_path: Path, results_dir: Path,
                  git_commit: str, engine_version: str, adapter_command: str,
                  server_url: str = "", api_model_name: str = "",
                  scoring_config_path: str = "", dataset_manifest_path: str = "",
                  dataset_revision: str = "") -> dict:
    _assert_full_set(run_stats_path)
    save_name = f"{model_id}_{version}_quick_match{'_cdm' if cdm else ''}"
    summary_path = results_dir / f"{save_name}_run_summary.json"
    provenance_path = results_dir / f"{save_name}_provenance.json"
    au.write_run_summary(save_name=save_name, run_stats_path=run_stats_path,
                         metric_result_path=metric_result_path, destination=summary_path, cdm=cdm)
    au.write_provenance(destination=provenance_path, git_commit=git_commit, engine=engine_version,
                        server_url=server_url, api_model_name=api_model_name,
                        adapter_command=adapter_command, scoring_config_path=Path(scoring_config_path),
                        dataset_manifest_path=Path(dataset_manifest_path),
                        predictions_dir=results_dir.parent, metric_result_paths=[metric_result_path],
                        run_summary_paths=[summary_path], run_stats_path=run_stats_path)
    return {"run_summary": str(summary_path), "provenance": str(provenance_path)}
```

(Note: `stage_download`'s `download_dataset` is implemented in Task 6's `download_omnidocbench.py`; for now `stage_download` is exercised only in integration. The unit tests here cover `stage_infer` + `_assert_full_set`.)

- [ ] **Step 5: Run tests to verify pass**

Run: `python -m pytest tests/test_stages.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add engine/omnidocbench_amd/stages.py engine/omnidocbench_amd/_paths.py tests/test_stages.py
git commit -m "feat(engine): stages orchestrator (subprocess infer, gated publish)"
```

---

### Task 5: Backend ABC + `linux_rocm` backend (Edit_dist+TEDS; CDM hook)

**Files:**
- Create: `engine/omnidocbench_amd/backends/__init__.py`
- Create: `engine/omnidocbench_amd/backends/base.py`
- Create: `engine/omnidocbench_amd/backends/linux_rocm.py`
- Test: `tests/test_backends.py`

**Interfaces:**
- Consumes: `_paths` (Task 4), OmniDocBench checkout.
- Produces: `Backend` ABC, `LinuxRocmBackend` with `.ensure_checkout()`, `.provision_cdm()`, `.score(...)`.

- [ ] **Step 1: Write the failing test (mocked subprocess)**

`tests/test_backends.py`:
```python
from pathlib import Path
from unittest.mock import patch
from omnidocbench_amd.backends.linux_rocm import LinuxRocmBackend


def test_score_invokes_pdf_validation_in_eval_venv(tmp_path):
    backend = LinuxRocmBackend(checkout=tmp_path / "odb")
    (tmp_path / "odb").mkdir()
    (tmp_path / "odb" / "pdf_validation.py").write_text("# stub")
    metric_path = tmp_path / "result" / "m_v16_quick_match_metric_result.json"
    metric_path.parent.mkdir(parents=True)
    metric_path.write_text("{}")
    with patch("omnidocbench_amd.backends.linux_rocm.subprocess.run") as run:
        run.return_value.returncode = 0
        out = backend.score(predictions_dir=tmp_path / "preds", version="v16",
                            cdm=False, run_stats_path=tmp_path / "rs.json")
    assert out.name == "m_v16_quick_match_metric_result.json"
    assert run.call_args.args[0][1].endswith("pdf_validation.py")  # runs the checkout's script
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_backends.py -v`
Expected: FAIL — `ModuleNotFoundError: omnidocbench_amd.backends`.

- [ ] **Step 3: Write `backends/base.py`**

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path


class Backend(ABC):
    """Platform-specific scoring + CDM provisioning."""

    @abstractmethod
    def ensure_checkout(self, revision: str) -> Path: ...

    @abstractmethod
    def provision_cdm(self) -> None: ...

    @abstractmethod
    def score(self, *, predictions_dir: Path, version: str, cdm: bool,
              run_stats_path: Path) -> Path:
        """Run pdf_validation.py in the eval-venv (3.11). Return metric_result path."""
```

`backends/__init__.py`:
```python
from .base import Backend
from .linux_rocm import LinuxRocmBackend

def get_backend(platform: str, checkout: Path | None = None) -> Backend:
    if platform == "linux-rocm":
        return LinuxRocmBackend(checkout=checkout)
    if platform == "windows-hip":
        from .windows_hip import WindowsHipBackend
        return WindowsHipBackend(checkout=checkout)
    raise ValueError(f"unknown platform: {platform}")
```

- [ ] **Step 4: Write `backends/linux_rocm.py`**

```python
from __future__ import annotations
import subprocess, sys
from pathlib import Path
from .base import Backend
from .._paths import eval_venv

PDF_VALIDATION = "pdf_validation.py"
RESULT_DIR = Path("result")


class LinuxRocmBackend(Backend):
    def __init__(self, checkout: Path | None = None):
        self.checkout = checkout

    def ensure_checkout(self, revision: str) -> Path:
        if self.checkout and (self.checkout / PDF_VALIDATION).exists():
            return self.checkout
        raise SystemExit(
            f"OmniDocBench checkout not found at {self.checkout}. Clone + pin {revision}:\n"
            f"  git clone https://github.com/opendatalab/OmniDocBench.git {self.checkout}\n"
            f"  cd {self.checkout} && git checkout {revision} && pip install -e .")

    def provision_cdm(self) -> None:
        # Task 14 implements real CDM; for now this is the no-CDM path.
        print("[cdm] linux-rocm: provision via engine/omnidocbench_amd/cdm/setup-linux.sh (Task 14)")

    def score(self, *, predictions_dir: Path, version: str, cdm: bool,
              run_stats_path: Path) -> Path:
        checkout = self.ensure_checkout(revision="master")  # v1.6 = master; pinned by caller
        venv_python = str(eval_venv("linux-rocm") / "bin" / "python")
        save = f"{predictions_dir.name}_quick_match"
        cmd = [venv_python, str(checkout / PDF_VALIDATION),
               "--config", str(version), "--predictions", str(predictions_dir)]
        subprocess.run(cmd, cwd=checkout, check=True)
        return checkout / RESULT_DIR / f"{save}_metric_result.json"
```

- [ ] **Step 5: Run tests to verify pass**

Run: `python -m pytest tests/test_backends.py -v`
Expected: PASS (1 test).

- [ ] **Step 6: Commit**

```bash
git add engine/omnidocbench_amd/backends/ tests/test_backends.py
git commit -m "feat(engine): Backend ABC + linux_rocm backend (Edit_dist/TEDS)"
```

---

### Task 6: Dataset downloader (pinned revision)

**Files:**
- Create: `engine/omnidocbench_amd/download_omnidocbench.py`
- Test: `tests/test_download.py`
- Reference: `AIwork4me/PaddleOCR-VL-ROCm/eval/download_omnidocbench.py`

**Interfaces:**
- Produces: `VERSIONS` dict, `download_dataset(repo_id, target, revision) -> Path`.

- [ ] **Step 1: Write the failing test (no network; monkeypatch snapshot_download)**

`tests/test_download.py`:
```python
from pathlib import Path
from unittest.mock import patch
from omnidocbench_amd import download_omnidocbench as dl


def test_download_requires_pinned_revision(tmp_path):
    try:
        dl.download_dataset("opendatalab/OmniDocBench", tmp_path, revision=None)
        assert False
    except SystemExit:
        pass


def test_download_calls_snapshot_with_revision(tmp_path):
    with patch("omnidocbench_amd.download_omnidocbench.snapshot_download") as snap:
        snap.return_value = str(tmp_path)
        out = dl.download_dataset("opendatalab/OmniDocBench", tmp_path, revision="v1.6")
        assert out == tmp_path
        assert snap.call_args.kwargs["revision"] == "v1.6"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_download.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Port `download_omnidocbench.py`**

Port `download_dataset` + `VERSIONS` from `PaddleOCR-VL-ROCm/eval/download_omnidocbench.py` (fetch via `gh api ... contents/eval/download_omnidocbench.py`). Enforce: if `revision is None`, `raise SystemExit("revision must be pinned")`. Expose `snapshot_download` as a module-level import (`from huggingface_hub import snapshot_download`) so the test can monkeypatch it.

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_download.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add engine/omnidocbench_amd/download_omnidocbench.py tests/test_download.py
git commit -m "feat(engine): dataset downloader (pinned revision)"
```

---

### Task 7: Engine CLI

**Files:**
- Create: `engine/omnidocbench_amd/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `stages` (Task 4), `backends.get_backend` (Task 5), `download_omnidocbench` (Task 6).
- Produces: `main(argv)`, registered as `omnidocbench-amd` console script.

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:
```python
import sys
from unittest.mock import patch
from omnidocbench_amd.cli import main


def test_cli_score_dispatches_to_stage_score(tmp_path):
    argv = ["omnidocbench-amd", "score", "--platform", "linux-rocm",
            "--predictions-dir", str(tmp_path), "--version", "v16",
            "--run-stats", str(tmp_path / "rs.json")]
    with patch("omnidocbench_amd.cli.stage_score") as score, \
         patch("omnidocbench_amd.cli.get_backend") as gb:
        gb.return_value.score.return_value = tmp_path / "metric.json"
        main(argv[1:])
        assert score.called or gb.return_value.score.called


def test_cli_cdm_setup_dispatches():
    with patch("omnidocbench_amd.cli.get_backend") as gb:
        main(["cdm", "setup", "--platform", "linux-rocm"])
        gb.return_value.provision_cdm.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write `cli.py`**

```python
from __future__ import annotations
import argparse, sys
from pathlib import Path
from . import stages
from .backends import get_backend


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="omnidocbench-amd")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("cdm"); sp.add_argument("setup"); sp.add_argument("--platform", required=True)
    dp = sub.add_parser("dataset"); dp.add_argument("download"); dp.add_argument("--version", default="v16"); dp.add_argument("--revision", required=True)
    ip = sub.add_parser("infer"); ip.add_argument("--adapter", required=True); ip.add_argument("--img-dir", required=True)
    ip.add_argument("--out-dir", required=True); ip.add_argument("--platform", required=True)
    sc = sub.add_parser("score"); sc.add_argument("--platform", required=True); sc.add_argument("--predictions-dir", required=True)
    sc.add_argument("--version", default="v16"); sc.add_argument("--cdm", action="store_true"); sc.add_argument("--run-stats", required=True)
    pu = sub.add_parser("publish"); pu.add_argument("--model-id", required=True); pu.add_argument("--platform", required=True)
    pu.add_argument("--version", default="v16"); pu.add_argument("--cdm", action="store_true")
    pu.add_argument("--run-stats", required=True); pu.add_argument("--metric-result", required=True)
    pu.add_argument("--results-dir", required=True); pu.add_argument("--git-commit", required=True)
    pu.add_argument("--adapter-command", required=True); pu.add_argument("--server-url", default="")
    pu.add_argument("--api-model-name", default=""); pu.add_argument("--scoring-config", default="")
    pu.add_argument("--dataset-manifest", default=""); pu.add_argument("--dataset-revision", required=True)
    rn = sub.add_parser("run"); rn.add_argument("--stage", default="all"); rn.add_argument("--platform", required=True)

    a = p.parse_args(argv)
    if a.cmd == "cdm":
        get_backend(a.platform).provision_cdm(); return 0
    if a.cmd == "dataset":
        stages.stage_download(a.version, a.revision); return 0
    if a.cmd == "infer":
        stages.stage_infer(adapter_path=Path(a.adapter), img_dir=Path(a.img_dir),
                           out_dir=Path(a.out_dir), platform=a.platform, config={}); return 0
    if a.cmd == "score":
        b = get_backend(a.platform)
        stages.stage_score(backend=b, predictions_dir=Path(a.predictions_dir), version=a.version,
                           cdm=a.cdm, run_stats_path=Path(a.run_stats)); return 0
    if a.cmd == "publish":
        import omnidocbench_amd
        stages.stage_publish(model_id=a.model_id, platform=a.platform, version=a.version, cdm=a.cdm,
                             run_stats_path=Path(a.run_stats), metric_result_path=Path(a.metric_result),
                             results_dir=Path(a.results_dir), git_commit=a.git_commit,
                             engine_version=omnidocbench_amd.__version__, adapter_command=a.adapter_command,
                             server_url=a.server_url, api_model_name=a.api_model_name,
                             scoring_config_path=a.scoring_config, dataset_manifest_path=a.dataset_manifest,
                             dataset_revision=a.dataset_revision); return 0
    if a.cmd == "run":
        raise SystemExit("orchestrated 'run' is wired in Task 13 (needs all stages + backend)")
    return 1
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add engine/omnidocbench_amd/cli.py tests/test_cli.py
git commit -m "feat(engine): omnidocbench-amd CLI (cdm/dataset/infer/score/publish)"
```

---

### Task 8: Contract integration test (fake adapter → engine → validated artifacts)

**Files:**
- Test: `tests/test_contract_integration.py`
- Test fixture: `tests/fixtures/fake_adapter.py`

**Interfaces:** Validates the whole CPU slice end-to-end (download mocked; infer + publish real).

- [ ] **Step 1: Write the integration test**

`tests/fixtures/fake_adapter.py` — a real conformant adapter using `--backend smoke`:
```python
from __future__ import annotations
import argparse, json
from pathlib import Path
from omnidocbench_amd.types import RunSummary, PageStatus
IMG_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def run_adapter(img_dir: Path, out_dir: Path, *, platform: str, config: dict) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    imgs = sorted(p for p in img_dir.iterdir() if p.suffix.lower() in IMG_EXT)
    stats = []
    for i in imgs:
        (out_dir / f"{i.stem}.md").write_text(f"# {i.stem}\n\n(smoke output)\n", encoding="utf-8")
        stats.append(PageStatus(i.name, "ok", seconds=0.01, attempts=1))
    rs = RunSummary(len(imgs), len(imgs), 0, 0, None, stats, engine="smoke")
    return rs.write(out_dir / "_run_stats.json").read_text() and rs.to_run_stats()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--img-dir", required=True); p.add_argument("--out-dir", required=True)
    p.add_argument("--platform", required=True); p.add_argument("--backend", default="smoke")
    a = p.parse_args(); run_adapter(Path(a.img_dir), Path(a.out_dir), platform=a.platform, config={})
```

`tests/test_contract_integration.py`:
```python
import json
from pathlib import Path
from omnidocbench_amd import stages
from omnidocbench_amd.schema import validate_artifact

FIXTURE_ADAPTER = Path(__file__).parent / "fixtures" / "fake_adapter.py"


def test_fake_adapter_infer_then_publish(tmp_path):
    imgs = tmp_path / "imgs"; imgs.mkdir()
    for n in ("a.png", "b.png", "c.png"): (imgs / n).write_bytes(b"x")
    preds = tmp_path / "preds"
    summary = stages.stage_infer(adapter_path=FIXTURE_ADAPTER, img_dir=imgs, out_dir=preds,
                                 platform="linux-rocm", config={})
    assert summary["ok"] == 3 and summary["limit_pages"] is None

    # fake a metric_result so publish can assemble
    rs = preds / "_run_stats.json"
    metric = tmp_path / "metric.json"
    metric.write_text(json.dumps({
        "text_block": {"page": {"Edit_dist": {"ALL": 0.05}}},
        "reading_order": {"page": {"Edit_dist": {"ALL": 0.13}}},
        "table": {"page": {"TEDS": {"ALL": 0.93}}},
        "display_formula": {"page": {"CDM": {"ALL": 0.95}}, "metric_debug": {"CDM": {"sample_count": 5, "exception_case_count": 0}}},
    }))
    results = tmp_path / "results"; results.mkdir()
    out = stages.stage_publish(model_id="fake-model", platform="linux-rocm", version="v16", cdm=False,
                               run_stats_path=rs, metric_result_path=metric, results_dir=results,
                               git_commit="abc123", engine_version="0.1.0",
                               adapter_command="python fake_adapter.py", dataset_revision="v1.6")
    summary_obj = json.loads(Path(out["run_summary"]).read_text())
    validate_artifact("run_summary", summary_obj)
    assert summary_obj["readme_metrics"]["text_edit_dist"] == 0.05
    prov_obj = json.loads(Path(out["provenance"]).read_text())
    validate_artifact("provenance", prov_obj)
    assert prov_obj["platform"] == "linux-rocm" and prov_obj["dataset_revision"] == "v1.6"
```

- [ ] **Step 2: Run test to verify pass**

Run: `python -m pytest tests/test_contract_integration.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_contract_integration.py tests/fixtures/fake_adapter.py
git commit -m "test(engine): contract integration (fake adapter → validated artifacts)"
```

---

### Task 9: `check_conformance.py`

**Files:**
- Create: `scripts/check_conformance.py`
- Create: `contracts/conformance.md`
- Create: `contracts/badge-policy.md`
- Test: `tests/test_conformance.py` + fixtures `tests/fixtures/conformant/` and `tests/fixtures/nonconformant/`

**Interfaces:**
- Produces: `check_repo(path) -> ConformanceReport`, CLI `python scripts/check_conformance.py <repo>` exit 0/1.

- [ ] **Step 1: Write the failing test**

`tests/test_conformance.py`:
```python
from pathlib import Path
from scripts.check_conformance import check_repo
FIX = Path(__file__).parent / "fixtures"


def test_conformant_repo_passes():
    report = check_repo(FIX / "conformant")
    assert report.ok, report.failures


def test_nonconformant_repo_fails():
    report = check_repo(FIX / "nonconformant")
    assert not report.ok
    assert any("run_adapter" in f or "README" in f or "results" in f for f in report.failures)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_conformance.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Build fixture repos**

Create `tests/fixtures/conformant/` with: `adapter/run_adapter.py` (copy of the smoke adapter signature), `eval/configs/omnidocbench_v16.yaml`, `results/omnidocbench/v16/linux-rocm/.gitkeep`, `README.md` + `README.zh-CN.md` (with required section headers: Install, Demo, Evaluation, Reproducibility, Known Gaps), `examples/demo.png` + `run_demo.sh`, `pyproject.toml` (depends on `omnidocbench-amd`), `model_card.json` (valid against schema).

Create `tests/fixtures/nonconformant/` missing `adapter/run_adapter.py` and `README.zh-CN.md`.

- [ ] **Step 4: Write `scripts/check_conformance.py`**

```python
from __future__ import annotations
import json, sys
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED_README_SECTIONS = ["Install", "Demo", "Evaluation", "Reproducibility", "Known Gaps"]


@dataclass
class ConformanceReport:
    ok: bool = True
    failures: list[str] = field(default_factory=list)

    def add(self, msg: str):
        self.failures.append(msg); self.ok = False


def check_repo(repo: Path) -> ConformanceReport:
    repo = Path(repo); r = ConformanceReport()
    if not (repo / "adapter" / "run_adapter.py").exists():
        r.add("missing adapter/run_adapter.py")
    if not (repo / "eval" / "configs" / "omnidocbench_v16.yaml").exists():
        r.add("missing eval/configs/omnidocbench_v16.yaml")
    for plat in ("linux-rocm", "windows-hip"):
        d = repo / "results" / "omnidocbench" / "v16" / plat
        if d.exists() and not any(d.iterdir()):
            r.add(f"empty results/omnidocbench/v16/{plat}/ (declared but no artifacts)")
    for readme in ("README.md", "README.zh-CN.md"):
        p = repo / readme
        if not p.exists():
            r.add(f"missing {readme}"); continue
        text = p.read_text(encoding="utf-8")
        for sec in REQUIRED_README_SECTIONS:
            if sec not in text:
                r.add(f"{readme} missing required section: {sec}")
    if not (repo / "examples").is_dir() or not any((repo / "examples").iterdir()):
        r.add("missing examples/ demo")
    pp = repo / "pyproject.toml"
    if not pp.exists() or "omnidocbench-amd" not in pp.read_text():
        r.add("pyproject.toml does not depend on omnidocbench-amd")
    mc = repo / "model_card.json"
    if mc.exists():
        from omnidocbench_amd.schema import validate_artifact
        try:
            validate_artifact("model_card", json.loads(mc.read_text()))
        except Exception as e:
            r.add(f"model_card.json invalid: {e}")
    return r


def main(argv: list[str]) -> int:
    report = check_repo(Path(argv[0]))
    if report.ok:
        print("CONFORMANT"); return 0
    print("NON-CONFORMANT:"); [print(" -", f) for f in report.failures]; return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

Make `scripts/` importable: add `conftest.py` at repo root with `sys.path.insert(0, str(Path(__file__).parent))` so `from scripts.check_conformance import ...` works.

- [ ] **Step 5: Write `contracts/conformance.md` + `contracts/badge-policy.md`**

`conformance.md`: list the checklist exactly as `check_repo` enforces it (the script is the source of truth; the doc mirrors it). `badge-policy.md`: `community` = provenance-complete + passes `check_conformance`; `verified` = maintainer reproduced both claimed platforms (Docker) + `VERIFIED.yaml` committed; per-platform `community-wanted` for missing side.

- [ ] **Step 6: Run tests to verify pass**

Run: `python -m pytest tests/test_conformance.py -v`
Expected: PASS (2 tests).

- [ ] **Step 7: Commit**

```bash
git add scripts/check_conformance.py contracts/conformance.md contracts/badge-policy.md tests/test_conformance.py tests/fixtures/ conftest.py
git commit -m "feat(contracts): check_conformance + badge policy + fixtures"
```

---

### Task 10: Cookiecutter per-model template + smoke backend

**Files:**
- Create: `template/cookiecutter.json`
- Create: `template/{{cookiecutter.repo_name}}/{adapter/run_adapter.py,adapter/adapter_config.py,adapter/setup/00-install-deps.sh,adapter/setup/00-install-deps.ps1,adapter/setup/.env.local.example,eval/configs/omnidocbench_v16.yaml,results/omnidocbench/v16/linux-rocm/.gitkeep,results/omnidocbench/v16/windows-hip/.gitkeep,examples/run_demo.sh,examples/run_demo.ps1,README.md,README.zh-CN.md,docs/how-it-works.md,docs/reproducibility.md,docs/known-gaps.md,docs/backends.md,model_card.json,pyproject.toml,Makefile,.github/workflows/ci.yml,.gitignore,LICENSE,CONTRIBUTING.md,CODE_OF_CONDUCT.md}`
- Test: `tests/test_template.py`

**Interfaces:** Produces a repo that passes `check_conformance` after cookiecutter render.

- [ ] **Step 1: Write the failing test**

`tests/test_template.py`:
```python
import subprocess, sys
from pathlib import Path
from cookiecutter.main import cookiecutter
from scripts.check_conformance import check_repo

TEMPLATE = Path(__file__).parent.parent / "template"


def test_rendered_template_passes_conformance(tmp_path):
    out = cookiecutter(str(TEMPLATE), no_input=True,
                       extra_context={"repo_name": "SmokeModel-AMD", "model_slug": "smokemodel"},
                       output_dir=str(tmp_path))
    report = check_repo(Path(out))
    assert report.ok, report.failures


def test_rendered_template_smoke_backend_runs(tmp_path):
    out = cookiecutter(str(TEMPLATE), no_input=True,
                       extra_context={"repo_name": "SmokeModel-AMD", "model_slug": "smokemodel"},
                       output_dir=str(tmp_path))
    adapter = Path(out) / "adapter" / "run_adapter.py"
    imgs = tmp_path / "imgs"; imgs.mkdir(); (imgs / "a.png").write_bytes(b"x")
    proc = subprocess.run([sys.executable, str(adapter), "--img-dir", str(imgs),
                           "--out-dir", str(tmp_path / "out"), "--platform", "linux-rocm",
                           "--backend", "smoke"])
    assert proc.returncode == 0
    assert (tmp_path / "out" / "a.md").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_template.py -v`
Expected: FAIL — template not found.

- [ ] **Step 3: Write `template/cookiecutter.json`**

```json
{
  "repo_name": "Model-AMD",
  "model_slug": "model",
  "model_id": "model",
  "model_version": "0.1.0",
  "license": ["Apache-2.0", "MIT"]
}
```

- [ ] **Step 4: Write the template `run_adapter.py` (smoke backend default)**

`template/{{cookiecutter.repo_name}}/adapter/run_adapter.py`:
```python
"""{{cookiecutter.repo_name}} adapter — implements the omnidocbench-amd contract.

Replace the `smoke` branch with your model's inference. Keep the signature and the
out_dir/<image_stem>.md output convention. Per-page failures must be caught and
recorded (a missing page scores zero) — never raise.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from omnidocbench_amd.types import RunSummary, PageStatus

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
PLATFORMS = ("linux-rocm", "windows-hip")


def run_adapter(img_dir: Path, out_dir: Path, *, platform: str, config: dict) -> dict:
    assert platform in PLATFORMS, f"unknown platform: {platform}"
    out_dir.mkdir(parents=True, exist_ok=True)
    imgs = sorted(p for p in Path(img_dir).iterdir() if p.suffix.lower() in IMG_EXT)
    stats: list[PageStatus] = []
    backend = config.get("backend", "smoke")
    for i in imgs:
        try:
            if backend == "smoke":
                md = f"# {i.stem}\n\n(smoke output — wire your model here)\n"
            else:
                md = _infer(i, platform, config)  # TODO-replace: your model's inference
            (out_dir / f"{i.stem}.md").write_text(md, encoding="utf-8")
            stats.append(PageStatus(i.name, "ok", seconds=0.0, attempts=1))
        except Exception as e:  # per-page failure → record, continue, never raise
            stats.append(PageStatus(i.name, f"failed: {e}", error=str(e)))
    rs = RunSummary(len(imgs), sum(1 for s in stats if s.status == "ok"),
                    sum(1 for s in stats if s.status.startswith("failed")),
                    sum(1 for s in stats if s.status.startswith("fallback")),
                    config.get("limit_pages"), stats, engine=backend)
    rs.write(out_dir / "_run_stats.json")
    return rs.to_run_stats()


def _infer(img: Path, platform: str, config: dict) -> str:
    raise NotImplementedError("Replace _infer with your model's inference (img → markdown).")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--img-dir", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--platform", required=True, choices=PLATFORMS)
    p.add_argument("--backend", default="smoke")
    p.add_argument("--server-url", default="")
    p.add_argument("--api-model-name", default="")
    a = p.parse_args()
    run_adapter(Path(a.img_dir), Path(a.out_dir), platform=a.platform,
                config={"backend": a.backend, "server_url": a.server_url, "api_model_name": a.api_model_name})
```

- [ ] **Step 5: Write `Makefile`, `pyproject.toml`, `model_card.json`, READMEs, `setup/` scripts, `examples/`, `docs/`, `.github/workflows/ci.yml`, `.gitignore`, `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`**

`Makefile`:
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
	$(eval OUT := $$(mktemp -d))
	omnidocbench-amd infer --adapter adapter/run_adapter.py --img-dir examples --out-dir $(OUT) --platform $(PLATFORM)
	@ls $(OUT)

eval-linux eval-windows:
	omnidocbench-amd run --stage all --platform $(PLATFORM) --version $(VERSION) --revision $(REVISION)

publish:
	python ../../scripts/check_conformance.py . && echo CONFORMANT

smoke-test:
	python -m pytest
```

`pyproject.toml`:
```toml
[project]
name = "{{cookiecutter.repo_name | lower}}"
version = "{{cookiecutter.model_version}}"
dependencies = ["omnidocbench-amd>=0.1.0"]
[project.optional-dependencies]
dev = ["pytest"]
```

`model_card.json` — a valid placeholder against the schema:
```json
{
  "schema_version": 1,
  "model_id": "{{cookiecutter.model_id}}",
  "model_version": "{{cookiecutter.model_version}}",
  "platforms": ["linux-rocm", "windows-hip"],
  "badge": {"linux-rocm": "community-wanted", "windows-hip": "community-wanted"},
  "eval_date": "",
  "omnidocbench_version": "v1.6",
  "overall": null,
  "submetrics": {},
  "hardware": {"gpu": "", "vram": "", "rocm_driver": ""},
  "artifacts": {}
}
```

`README.md` / `README.zh-CN.md` — include all required section headers (Install, Demo, Evaluation, Reproducibility, Known Gaps) with scaffolding text; CN is optimized (mirrors + ModelScope first). `adapter/setup/00-install-deps.{sh,ps1}` — idempotent stubs that echo "implement provisioning". `.env.local.example` — `SERVER_URL=`, `WEIGHTS_DIR=`. `examples/run_demo.{sh,ps1}` + a tiny `demo.png` (1×1 placeholder). `docs/backends.md` — recommended inference backend per model-type × platform:
| Model type | linux-rocm | windows-hip |
|---|---|---|
| pure VLM | vLLM/ROCm | llama.cpp/GGUF (HIP or Vulkan) |
| layout+VLM | ONNX `onnxruntime-rocm` (ROCm EP) + VLM server | ONNX `onnxruntime-directml` (DirectML EP, via Microsoft Olive) + VLM server |
| pipeline (MinerU2.5) | MinerU on ROCm | MinerU on DirectML/ONNX |
Cite https://ryzenai.docs.amd.com/en/latest/gpu/ryzenai_gpu.html for the Windows DirectML path. `docs/{how-it-works,reproducibility,known-gaps}.md` — scaffolding. `.github/workflows/ci.yml`:
```yaml
on: [push, pull_request]
jobs:
  smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install -e ".[dev]" && pip install omnidocbench-amd
      - run: python -c "from omnidocbench_amd.types import RunSummary"  # engine importable
```
`LICENSE` (Apache-2.0), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` — standard.

- [ ] **Step 6: Run tests to verify pass**

Run: `python -m pytest tests/test_template.py -v`
Expected: PASS (2 tests) — rendered template is conformant + smoke backend runs.

- [ ] **Step 7: Commit**

```bash
git add template/ tests/test_template.py
git commit -m "feat(template): cookiecutter per-model repo + smoke backend + Makefile"
```

---

### Task 11: Hub registry + generator

**Files:**
- Create: `hub/registry.yaml`
- Create: `scripts/generate_registry.py`
- Test: `tests/test_registry.py`

**Interfaces:** Produces `generate_registry(yaml_path) -> list[dict]` rendering the comparison table; consumed by the hub site (sub-project 1).

- [ ] **Step 1: Write the failing test**

`tests/test_registry.py`:
```python
from pathlib import Path
from scripts.generate_registry import generate_registry

REG = """
- model_id: paddleocr-vl-1.6
  repo: AIwork4me/PaddleOCR-VL-ROCm
  platforms:
    linux-rocm: {badge: verified, overall: 95.94}
    windows-hip: {badge: community, overall: 95.94}
- model_id: unlimited-ocr
  repo: AIwork4me/Unlimited-OCR-ROCm
  platforms:
    linux-rocm: {badge: verified, overall: 92.43}
    windows-hip: {badge: community-wanted, overall: null}
"""


def test_generate_registry(tmp_path):
    y = tmp_path / "registry.yaml"; y.write_text(REG)
    rows = generate_registry(y)
    assert len(rows) == 2
    assert rows[0]["platforms"]["linux-rocm"]["badge"] == "verified"
    assert rows[1]["platforms"]["windows-hip"]["badge"] == "community-wanted"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_registry.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write `scripts/generate_registry.py` + `hub/registry.yaml`**

```python
from __future__ import annotations
import yaml
from pathlib import Path

def generate_registry(yaml_path: Path) -> list[dict]:
    return yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8")) or []

def render_table(rows: list[dict]) -> str:
    lines = ["| Model | Repo | linux-rocm | windows-hip |", "|---|---|---|---|"]
    for r in rows:
        p = r["platforms"]
        lines.append(f"| {r['model_id']} | {r['repo']} | "
                     f"{_cell(p.get('linux-rocm'))} | {_cell(p.get('windows-hip'))} |")
    return "\n".join(lines)

def _cell(c): 
    return "—" if not c else f"{c['badge']} ({c.get('overall')})"
```

`hub/registry.yaml` — seed with the 3 v1 models (PaddleOCR-VL-1.6, unlimited-ocr, mineru2.5) all `community-wanted` until sub-project 4 onboards them.

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_registry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add hub/ scripts/generate_registry.py tests/test_registry.py
git commit -m "feat(hub): registry.yaml + comparison-table generator"
```

---

### Task 12: Contributor docs + absorbed docs + `ci-reality.md`

**Files:**
- Create: `docs/contribute-a-model.md` + `docs/contribute-a-model.zh-CN.md`
- Create: `docs/architecture.md` (absorb + extend from `omnidocbench-amd-windows/docs/architecture.md`)
- Create: `docs/pitfalls.md` (absorb from `omnidocbench-amd-windows/docs/pitfalls.md`)
- Create: `docs/ci-reality.md`
- Create: `contracts/adapter.md`

**Interfaces:** Documentation only; no code tests.

- [ ] **Step 1: Fetch the source docs to absorb**

```bash
gh api repos/AIwork4me/omnidocbench-amd-windows/contents/docs/architecture.md -H "Accept: application/vnd.github.raw" > /tmp/odb-arch.md
gh api repos/AIwork4me/omnidocbench-amd-windows/contents/docs/pitfalls.md -H "Accept: application/vnd.github.raw" > /tmp/odb-pitfalls.md
```

- [ ] **Step 2: Write `contracts/adapter.md`**

The canonical human-readable contract — mirror §5.1 of the spec: signature, `platform` arg, `AdapterConfig` source, `RunSummary`/`_run_stats.json`, the iron rules (filesystem-decoupled, per-page fail→zero, never raise), output conventions (LaTeX formulas, HTML/LaTeX/pipe tables, document-order reading order), backend-agnosticism.

- [ ] **Step 3: Write `docs/contribute-a-model.md` + `.zh-CN.md`**

The 9-step flow from spec §8 (Propose → Scaffold → Provision → Implement → Demo → Eval → Publish → Submit → Verified), with prerequisites checklist (AMD GPUs that work: gfx1100/W7900/RX 7900 XT+/Strix Halo 8060S; OS; disk; mirrors; Python 3.11 eval-venv + 3.12 model venv), per-step time budget, the "I only have one platform" path (per-platform `community`), and where to ask for help. CN version optimized (mirrors + ModelScope first).

- [ ] **Step 4: Write `docs/architecture.md`, `docs/pitfalls.md`, `docs/ci-reality.md`**

- `architecture.md`: port `/tmp/odb-arch.md` and extend with the platform-repo topology (§4 of spec), the engine stages, the venv split, the CDM ownership + Docker path.
- `pitfalls.md`: port `/tmp/odb-pitfalls.md` verbatim (CDM, Python version, mirror config, GGUF quant).
- `ci-reality.md`: GitHub Actions has no native AMD GPU runner → CI is CPU-only (contract/template/schema/smoke); GPU tests (engine self-test, reference regression, CDM validity) are maintainer-run on real hardware, `--gpu`-marked; trust comes from tiered badges (verified = maintainer reproduced), not CI.

- [ ] **Step 5: Commit**

```bash
git add docs/ contracts/adapter.md
git commit -m "docs: contributor guide (EN/CN) + architecture + pitfalls + ci-reality + adapter contract"
```

---

### Task 13: Platform CI workflow + `run` orchestrator wiring

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `engine/omnidocbench_amd/cli.py` (wire `run --stage all`)

**Interfaces:** CPU CI runs all tests; `run` orchestrates download→infer→score→publish.

- [ ] **Step 1: Write `.github/workflows/ci.yml`**

```yaml
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install -e ".[dev]"
      - run: python -m pytest -q
      - run: python scripts/check_conformance.py tests/fixtures/conformant
      - run: python -c "from cookiecutter.main import cookiecutter; cookiecutter('template', no_input=True, output_dir='/tmp/t')"
```

- [ ] **Step 2: Wire `run --stage all` in `cli.py`**

Replace the `run` branch's placeholder `raise SystemExit(...)` with a real orchestration that calls `stage_download` → `stage_infer` → `stage_score` → `stage_publish` using `get_backend(platform)` and the adapter path, writing artifacts to `results/omnidocbench/<version>/<platform>/`. Add a test `tests/test_cli.py::test_cli_run_all` that monkeypatches the four stage functions and asserts they are called in order.

- [ ] **Step 3: Run full suite**

Run: `python -m pytest -q`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml engine/omnidocbench_amd/cli.py tests/test_cli.py
git commit -m "feat(ci): platform CPU workflow + wire 'run --stage all' orchestrator"
```

---

## Phase B — Hardware-gated validation tail

> These tasks require real AMD hardware and cannot be TDD'd in a sandbox. Each ends with a manual verification against the published artifact schema + conformance check. Run on the gfx1100/W7900 Linux box (this env) and the Strix Halo Windows box.

### Task 14: Linux CDM provisioning + Docker reproducible path

**Files:**
- Create: `engine/omnidocbench_amd/cdm/setup-linux.sh`
- Modify: `engine/omnidocbench_amd/backends/linux_rocm.py` (`provision_cdm` calls the script; `score` honors `--cdm` + `--docker`)

**Interfaces:** `LinuxRocmBackend.provision_cdm()` installs native TeX Live + IM7 + gs + node; `score(cdm=True, docker=True)` runs `pdf_validation.py` inside `ghcr.io/zeng-weijun/omnidocbench-eval:repro-ubuntu2204`.

- [ ] **Step 1: Write `setup-linux.sh`** — idempotent: `dpkg -s` guards for `texlive-full`, `imagemagick`, `ghostscript`, `nodejs`; install if missing; print `already present` otherwise.
- [ ] **Step 2: Implement `provision_cdm`** to `subprocess.run(["bash", script])`.
- [ ] **Step 3: Implement `--cdm` + `--docker` in `score`** — when `docker=True`, run `docker run --rm -v <checkout>:/work ghcr.io/zeng-weijun/omnidocbench-eval:repro-ubuntu2204 python /work/pdf_validation.py ...`; when `cdm=True` without docker, use the native TeX Live path.
- [ ] **Step 4: Manual verification (hardware)** — on the gfx1100 box, run `omnidocbench-amd cdm setup --platform linux-rocm` then a 10-page CDM subset via the fake adapter; assert `metric_quality.formula_cdm.valid == true` and `formula_cdm_percent` is non-null. Commit.

### Task 15: Windows/HIP backend port

**Files:**
- Create: `engine/omnidocbench_amd/backends/windows_hip.py`
- Create: `engine/omnidocbench_amd/cdm/setup.ps1` + `cdm/setup.sh` (WSL reference path)
- Reference: `AIwork4me/omnidocbench-amd-windows/eval-infra/{01-omnidocbench,02-cdm-environment,03-scoring}/*`

**Interfaces:** `WindowsHipBackend` mirrors `LinuxRocmBackend`'s interface; CDM via `windows-cdm.patch` + native TeX Live, or WSL fallback.

- [ ] **Step 1: Port** `windows_hip.py` from `omnidocbench-amd-windows/eval-infra/03-scoring/score.ps1` + `score-cdm.sh` logic into the `Backend` ABC; port `02-cdm-environment/setup.ps1` + `setup.sh` into `engine/omnidocbench_amd/cdm/`.
- [ ] **Step 2: Add a mocked unit test** `tests/test_backends.py::test_windows_backend_score_dispatches` (mirror the linux test with `subprocess.run` patched) — CPU-passable.
- [ ] **Step 3: Manual verification (hardware)** — on the Strix Halo Windows box, run a 10-page CDM subset for the PaddleOCR-VL adapter via the new backend; assert valid CDM. Commit.

### Task 16: PaddleOCR-VL dual-platform end-to-end validation

**Files (in the `PaddleOCR-VL-ROCm` repo, separate from platform repo):**
- Modify: `PaddleOCR-VL-ROCm/adapter/run_adapter.py` (port to the new contract signature with `platform` arg)
- Modify: `PaddleOCR-VL-ROCm/eval/configs/omnidocbench_v16.yaml` (point at engine)
- Create: `PaddleOCR-VL-ROCm/results/omnidocbench/v16/{linux-rocm,windows-hip}/` artifact bundles
- Modify: `PaddleOCR-VL-ROCm/model_card.json` (fill real metrics + `verified` badge)

**Interfaces:** Proves the platform foundation end-to-end on a real model on both platforms.

- [ ] **Step 1 (linux-rocm, gfx1100 box)** — `omnidocbench-amd run --stage all --platform linux-rocm --version v16 --revision <pin>` against the PaddleOCR-VL adapter; confirm Overall ≈ 95.x matches the existing `omnidocbench-amd-windows` baseline within drift tolerance; run `check_conformance`; commit artifacts.
- [ ] **Step 2 (windows-hip, Strix Halo box)** — same on Windows; confirm Overall ≈ 95.x; commit artifacts.
- [ ] **Step 3** — maintainer reproduces both platforms via Docker → add `VERIFIED.yaml` → set `badge: {linux-rocm: verified, windows-hip: verified}` in `model_card.json`; PR to `hub/registry.yaml`. This is the first `verified` row.

### Task 17 (stretch → sub-project 4): Unlimited-OCR + MinerU2.5 onboarding

Deferred to sub-project 4 (separate spec/plan). Unlimited-OCR needs a Windows path added (decide vLLM-rocm-win vs llama.cpp/GGUF on the Strix Halo box); MinerU2.5 validates the pipeline model-type. Not in this plan's scope.

---

## Self-Review (run after writing)

**1. Spec coverage:**
- §2 scope (contracts+engine+template) → Tasks 1-13 (CPU MVP) + 14-16 (hardware validation). ✓
- §5 contracts (adapter interface, artifact schema, conformance, badge) → Tasks 2, 9, 12. ✓
- §6 engine (4 stages, 2 backends, venv split, CDM ownership, CLI, absorption) → Tasks 3-7, 14, 15. ✓
- §7 template (cookiecutter, Makefile, smoke backend, recommended backends) → Task 10. ✓
- §8 contributor flow → Task 12. ✓
- §9 robustness (per-page fail, gating, CDM validity, full-set, provenance) → Tasks 2, 3, 4, 8. ✓
- §10 testing (contract/template/engine/regression/CDM/CI-reality) → Tasks 2,8,9,10,13 + docs Task 12. ✓
- §11 rollout phases 1-5 → Tasks 1-16 (phase 6 = Task 17 deferred). ✓

**2. Placeholder scan:** Task 10's `run_adapter.py` has a `# TODO-replace` comment inside the template's `_infer` — this is intentional (it's the contributor's fill-in point, with a working `smoke` default), not a plan placeholder. No `TBD`/`implement later` in actionable steps.

**3. Type consistency:** `RunSummary.write` / `from_run_stats` (Task 2) used in Tasks 3, 4, 8, 10 — consistent. `stage_infer` / `stage_score` / `stage_publish` signatures (Task 4) match callers in Task 7 (cli) + Task 13 (run). `Backend.score(predictions_dir, version, cdm, run_stats_path)` (Task 5) matches `stage_score` (Task 4) + cli (Task 7). `check_repo` (Task 9) matches the conformance checklist + template fixtures (Task 10). ✓

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-12-amd-doc-parsing-platform-foundation.md` (in the `Unlimited-OCR-ROCm` repo; Task 1 copies it into the new `omnidocbench-amd` repo). Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
