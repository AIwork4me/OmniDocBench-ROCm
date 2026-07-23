# ROCm Document Parsing Zone — Platform Engine v0.3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the `omnidocbench-rocm` engine to support the locked trust bar, hybrid catalog, and licensing posture — efficiency metrics, 3-tier renderer, reproduction-recipe gate, license/NOTICE conformance, and `list`/`doctor` discovery.

**Architecture:** All changes are inside the hub repo (`omnidocbench-rocm`). The engine stays filesystem-decoupled (never imports adapters). New fields flow through the existing JSON-Schema-validated artifact pipeline (`_run_stats.json` → engine → `run_summary.json`) and the existing conformance gate (`check_repo`). The renderer gains tier-split logic over the existing `registry.yaml`.

**Tech Stack:** Python 3.11+, pytest, jsonschema (artifact validation), PyYAML (registry), argparse (CLI). CPU-only tests (no GPU needed — matches `docs/ci-reality.md`).

## Global Constraints

- **Schema source of truth:** `contracts/artifact-schema.json`; validated via `omnidocbench_rocm.schema.validate_artifact(name, obj)`. Every new artifact field is added there first.
- **Engine never imports adapters** — it reads `_run_stats.json` + `*.md` files only.
- **`_run_stats.json` is written by the adapter** (`RunSummary.write`); the engine reads it. New adapter-reported fields are *optional* (best-effort), never required (backends differ).
- **No fabricated results:** invalid/missing metrics render as `pending`/`—`/null, never a fake number.
- **Brand:** all new symbols use `omnidocbench_rocm` / `omnidocbench-rocm` (enforced by `scripts/check_brand.py`).
- **CPU tests only** in CI; GPU work is operational (runbooks, out of this plan).
- **DRY / YAGNI / TDD / frequent commits** throughout.

## File Structure

**Modify:**
- `contracts/artifact-schema.json` — add `efficiency` (run_stats + run_summary), `license`/`commercial_use` (model_card + registry), `repro_recipe`.
- `engine/omnidocbench_rocm/types.py` — `RunSummary.efficiency` field + serialization.
- `engine/omnidocbench_rocm/artifact_utils.py` — `write_run_summary(..., efficiency=...)`.
- `engine/omnidocbench_rocm/stages.py` — derive latency, propagate efficiency.
- `engine/omnidocbench_rocm/conformance.py` — NOTICE + REPRO + license checks.
- `engine/omnidocbench_rocm/cli.py` — `list` + `doctor` subcommands.
- `scripts/generate_registry.py` — 3-tier split + license column.
- `scripts/validate_registry.py` — require `license`/`commercial_use`.

**Create:**
- `tests/test_efficiency.py`, `tests/test_renderer_tiers.py`, `tests/test_repro_recipe.py`, `tests/test_license_conformance.py`, `tests/test_cli_list_doctor.py`.

**Runbooks (out of this plan — operational):** onboarding the 2 pending models, maintainer `verified` Docker reproductions, the MkDocs site build, the selection-policy doc, Radeon-Cloud workshop. These follow `docs/contribute-a-model.md` / `docs/onboarding-runbook.md`.

---

## Feature A — License / commercial-use fields + NOTICE conformance (ADR-0006)

### Task 1: Add optional `license` + `commercial_use` to the model_card schema

**Files:**
- Modify: `contracts/artifact-schema.json` (the `model_card` sub-schema `properties`)
- Test: `tests/test_schema.py`

**Interfaces:**
- Produces: `model_card` schema now accepts top-level `license: string` and `commercial_use: string` (both optional — restrictive-open models are admitted per ADR-0006).

- [ ] **Step 1: Write the failing test**

```python
def test_model_card_accepts_license_fields():
    from omnidocbench_rocm.schema import validate_artifact
    card = {
        "schema_version": 1, "model_id": "x", "model_version": "0.1",
        "platforms": ["linux-rocm"], "badge": {"linux-rocm": "community"},
        "eval_date": "2026-07-23", "omnidocbench_version": "v1.6",
        "overall": None, "hardware": {}, "artifacts": {},
        "license": "Apache-2.0", "commercial_use": "no restriction",
    }
    validate_artifact("model_card", card)  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /workspace/omnidocbench-rocm && python -m pytest tests/test_schema.py::test_model_card_accepts_license_fields -v`
Expected: FAIL — `jsonschema.ValidationError: Additional properties are not allowed ('license', 'commercial_use' were unexpected)` (if `additionalProperties: false`) or pass spuriously (if not) — confirm the schema currently rejects/ignores them.

- [ ] **Step 3: Add the fields to the schema**

In `contracts/artifact-schema.json`, inside the `model_card.properties` object (alongside `backend`, `execution_provider`, etc.), add:

```json
    "license": {"type": "string"},
    "commercial_use": {"type": "string"},
```

Do **not** add them to the `model_card.required` array (optional — ADR-0006 admits models without them during transition, but conformance Task 4 will require them).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /workspace/omnidocbench-rocm && python -m pytest tests/test_schema.py::test_model_card_accepts_license_fields -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /workspace/omnidocbench-rocm
git add contracts/artifact-schema.json tests/test_schema.py
git commit -m "feat(schema): admit license + commercial_use in model_card (ADR-0006)"
```

### Task 2: Require `license` + `commercial_use` in registry entries

**Files:**
- Modify: `scripts/validate_registry.py`
- Test: `tests/test_registry_validation.py`

**Interfaces:**
- Consumes: registry row dict (`model_id`, `repo`, `platforms`, …).
- Produces: `validate_registry(rows)` now returns an error string for any row missing `license` or `commercial_use`.

- [ ] **Step 1: Write the failing test**

```python
GOOD_LICENSE = [{"model_id": "x", "repo": "AIwork4me/X-ROCm",
                 "license": "Apache-2.0", "commercial_use": "no restriction",
                 "platforms": {"linux-rocm": {"badge": "verified", "overall": 95.0}}}]

def test_registry_requires_license():
    from scripts.validate_registry import validate_registry  # or import via package
    bad = [{k: v for k, v in GOOD_LICENSE[0].items() if k != "license"}]
    errors = validate_registry(bad)
    assert any("license" in e for e in errors), errors

def test_registry_requires_commercial_use():
    from scripts.validate_registry import validate_registry
    bad = [{k: v for k, v in GOOD_LICENSE[0].items() if k != "commercial_use"}]
    errors = validate_registry(bad)
    assert any("commercial_use" in e for e in errors), errors
```

> Note: if `scripts/` is not importable as a package, add `import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))` at the top of the test, or import via the engine's existing script-import helper (check how `tests/test_registry_validation.py` currently imports — match it).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /workspace/omnidocbench-rocm && python -m pytest tests/test_registry_validation.py::test_registry_requires_license tests/test_registry_validation.py::test_registry_requires_commercial_use -v`
Expected: FAIL (no error raised today).

- [ ] **Step 3: Add the validation rule**

In `scripts/validate_registry.py`, inside the per-row loop in `validate_registry`, after the `repo` check and before the `platforms` check, add:

```python
        if not r.get("license"):
            errors.append(f"{ctx}: missing license")
        if not r.get("commercial_use"):
            errors.append(f"{ctx}: missing commercial_use")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /workspace/omnidocbench-rocm && python -m pytest tests/test_registry_validation.py -v`
Expected: PASS (both new tests + existing ones).

- [ ] **Step 5: Commit**

```bash
cd /workspace/omnidocbench-rocm
git add scripts/validate_registry.py tests/test_registry_validation.py
git commit -m "feat(registry): require license + commercial_use per entry (ADR-0006)"
```

### Task 3: Conformance requires a `NOTICE` file

**Files:**
- Modify: `engine/omnidocbench_rocm/conformance.py` (`check_repo`)
- Test: `tests/test_license_conformance.py`

**Interfaces:**
- Consumes: `check_repo(repo: Path) -> ConformanceReport` (existing).
- Produces: report gains a failure `missing NOTICE file` when `repo/NOTICE` is absent.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
from omnidocbench_rocm.conformance import check_repo

def test_conformance_requires_notice(tmp_path):
    repo = tmp_path / "model-repo"
    (repo / "adapter").mkdir(parents=True)
    (repo / "adapter" / "run_adapter.py").write_text("# stub\n")
    (repo / "eval" / "configs").mkdir(parents=True)
    (repo / "eval" / "configs" / "omnidocbench_v16.yaml").write_text("version: v1.6\n")
    # ... create the other files check_repo already requires (mirror tests/test_conformance.py fixture)
    report = check_repo(repo)
    assert any("NOTICE" in f for f in report.failures), report.failures

def test_conformance_passes_with_notice(tmp_path):
    repo = tmp_path / "model-repo"
    # ... same setup as above ...
    (repo / "NOTICE").write_text("Model-ROCm\nApache-2.0\n")
    report = check_repo(repo)
    assert "missing NOTICE file" not in report.failures
```

> Match the exact conformant-repo fixture already used in `tests/test_conformance.py` (copy its setup helper) so the only difference is the `NOTICE` file.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /workspace/omnidocbench-rocm && python -m pytest tests/test_license_conformance.py::test_conformance_requires_notice -v`
Expected: FAIL (no NOTICE failure today).

- [ ] **Step 3: Add the NOTICE check**

In `engine/omnidocbench_rocm/conformance.py`, inside `check_repo`, alongside the existing `if not (repo / "adapter" / "run_adapter.py").exists(): r.add(...)` checks, add:

```python
    if not (repo / "NOTICE").exists():
        r.add("missing NOTICE file")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /workspace/omnidocbench-rocm && python -m pytest tests/test_license_conformance.py tests/test_conformance.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /workspace/omnidocbench-rocm
git add engine/omnidocbench_rocm/conformance.py tests/test_license_conformance.py
git commit -m "feat(conformance): require per-repo NOTICE (ADR-0006)"
```

---

## Feature B — Efficiency metrics (ADR-0003)

### Task 4: Optional `efficiency` in RunSummary + run_stats/run_summary schemas

**Files:**
- Modify: `engine/omnidocbench_rocm/types.py` (`RunSummary`), `contracts/artifact-schema.json`
- Test: `tests/test_efficiency.py`

**Interfaces:**
- Produces: `RunSummary(..., efficiency: dict | None = None)`; `to_run_stats()`/`from_run_stats()` round-trip it. Schema accepts optional `efficiency: {latency_s_per_page, peak_vram_mb, gpu}` on both `run_stats` and `run_summary`.

- [ ] **Step 1: Write the failing test**

```python
import json
from pathlib import Path
from omnidocbench_rocm.types import RunSummary, PageStatus
from omnidocbench_rocm.schema import validate_artifact

def test_runsummary_roundtrips_efficiency(tmp_path):
    eff = {"latency_s_per_page": 1.23, "peak_vram_mb": 38912, "gpu": "gfx1100"}
    rs = RunSummary(count=2, ok=2, fail=0, fallback=0, limit_pages=None,
                    stats=[PageStatus("a.png", "ok", seconds=1.0, attempts=1),
                           PageStatus("b.png", "ok", seconds=1.46, attempts=1)],
                    engine="vllm", efficiency=eff)
    p = tmp_path / "_run_stats.json"
    rs.write(p)
    validate_artifact("run_stats", json.loads(p.read_text()))  # schema accepts efficiency
    back = RunSummary.from_run_stats(p)
    assert back.efficiency == eff
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /workspace/omnidocbench-rocm && python -m pytest tests/test_efficiency.py::test_runsummary_roundtrips_efficiency -v`
Expected: FAIL — `RunSummary.__init__() got an unexpected keyword argument 'efficiency'` (or schema rejects the extra property).

- [ ] **Step 3a: Add the field to RunSummary**

In `engine/omnidocbench_rocm/types.py`, add `efficiency: dict | None = None` to the `RunSummary` dataclass (after `engine`). Update `to_run_stats()` to include `"efficiency": self.efficiency` **only when not None**, and `from_run_stats(path)` to read `obj.get("efficiency")`. Match how the existing code omits None values (check the current `to_run_stats` — if it always includes `engine`, mirror that style for `efficiency` but guard None to keep `smoke` runs clean).

- [ ] **Step 3b: Add `efficiency` to the schemas**

In `contracts/artifact-schema.json`, add to **both** `run_stats.properties` and `run_summary.properties`:

```json
    "efficiency": {
      "type": "object",
      "properties": {
        "latency_s_per_page": {"type": "number"},
        "peak_vram_mb": {"type": "integer"},
        "gpu": {"type": "string"}
      },
      "additionalProperties": false
    }
```

(Not added to `required` — optional/best-effort per ADR-0003.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /workspace/omnidocbench-rocm && python -m pytest tests/test_efficiency.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /workspace/omnidocbench-rocm
git add engine/omnidocbench_rocm/types.py contracts/artifact-schema.json tests/test_efficiency.py
git commit -m "feat(types): optional efficiency in RunSummary + schemas (ADR-0003)"
```

### Task 5: Engine derives latency + propagates efficiency into run_summary

**Files:**
- Modify: `engine/omnidocbench_rocm/stages.py` (`stage_publish`), `engine/omnidocbench_rocm/artifact_utils.py` (`write_run_summary`)
- Test: `tests/test_efficiency.py` (append)

**Interfaces:**
- Consumes: `_run_stats.json` (`stats[].seconds`, optional `efficiency`).
- Produces: `run_summary.json` gains `efficiency.latency_s_per_page` (mean of ok-page `seconds`), plus any adapter-reported `peak_vram_mb`/`gpu`.

- [ ] **Step 1: Write the failing test**

```python
import json
from pathlib import Path
from omnidocbench_rocm import stages  # or the module exposing stage_publish helpers

def test_derive_latency_from_stats():
    run_stats = {"schema_version": 1, "count": 2, "ok": 2, "fail": 0, "fallback": 0,
                 "limit_pages": None, "engine": "vllm",
                 "stats": [{"image": "a.png", "status": "ok", "seconds": 1.0, "attempts": 1},
                           {"image": "b.png", "status": "ok", "seconds": 3.0, "attempts": 1}]}
    eff = stages._derive_efficiency(run_stats)  # mean of ok-page seconds = 2.0
    assert eff["latency_s_per_page"] == 2.0

def test_derive_efficiency_merges_adapter_reported():
    run_stats = {"schema_version": 1, "count": 1, "ok": 1, "fail": 0, "fallback": 0,
                 "limit_pages": None, "engine": "vllm",
                 "stats": [{"image": "a.png", "status": "ok", "seconds": 2.0, "attempts": 1}],
                 "efficiency": {"peak_vram_mb": 38912, "gpu": "gfx1100"}}
    eff = stages._derive_efficiency(run_stats)
    assert eff["latency_s_per_page"] == 2.0
    assert eff["peak_vram_mb"] == 38912 and eff["gpu"] == "gfx1100"
```

> `stage_publish` end-to-end propagation is already covered by `tests/test_stages.py`'s publish fixture; here we unit-test the pure helper so it is GPU-free and fast.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /workspace/omnidocbench-rocm && python -m pytest tests/test_efficiency.py::test_derive_latency_from_stats tests/test_efficiency.py::test_derive_efficiency_merges_adapter_reported -v`
Expected: FAIL — `AttributeError: module ... has no attribute '_derive_efficiency'`.

- [ ] **Step 3: Implement the helper + wire it through publish**

In `engine/omnidocbench_rocm/stages.py`:

```python
def _derive_efficiency(run_stats: dict) -> dict:
    """latency = mean seconds over ok pages (engine-derived); peak_vram/gpu are
    adapter-reported via run_stats['efficiency'] and merged when present."""
    ok_secs = [s.get("seconds", 0.0) for s in run_stats.get("stats", [])
               if str(s.get("status")).startswith("ok") and s.get("seconds") is not None]
    eff = {"latency_s_per_page": round(sum(ok_secs) / len(ok_secs), 3)} if ok_secs else {}
    reported = run_stats.get("efficiency") or {}
    for k in ("peak_vram_mb", "gpu"):
        if reported.get(k) is not None:
            eff[k] = reported[k]
    return eff
```

In `stage_publish`, after `actual_backend = run_stats.get("engine", "")`, add:

```python
    efficiency = _derive_efficiency(run_stats)
```

and pass `efficiency=efficiency` into the `au.write_run_summary(...)` call.

In `engine/omnidocbench_rocm/artifact_utils.py`, add `efficiency: dict | None = None` to `write_run_summary`'s signature and include `"efficiency": efficiency` in the assembled summary dict **only when truthy** (so runs without efficiency stay clean).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /workspace/omnidocbench-rocm && python -m pytest tests/test_efficiency.py tests/test_stages.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /workspace/omnidocbench-rocm
git add engine/omnidocbench_rocm/stages.py engine/omnidocbench_rocm/artifact_utils.py tests/test_efficiency.py
git commit -m "feat(stages): derive latency + propagate efficiency to run_summary (ADR-0003)"
```

---

## Feature C — Renderer 3-tier split + license column (ADR-0003/0004)

### Task 6: `render_hub` splits rows into flagship / community / incoming

**Files:**
- Modify: `scripts/generate_registry.py`
- Test: `tests/test_renderer_tiers.py`

**Interfaces:**
- Consumes: `generate_registry(yaml_path) -> list[dict]` (unchanged).
- Produces: `render_hub(rows, external_ref_url=None) -> str` — emits `## Flagship comparison (verified)`, `## Community (also evaluated)`, `## Incoming (community-wanted)` sections (each only when non-empty), plus an optional external-reference link section. A model's tier = its **best** badge across platforms (`verified > community > community-wanted`).

- [ ] **Step 1: Write the failing test**

```python
ROWS = [
    {"model_id": "a", "repo": "AIwork4me/A-ROCm", "license": "Apache-2.0", "commercial_use": "none",
     "platforms": {"linux-rocm": {"badge": "verified", "overall": 95.0}}},
    {"model_id": "b", "repo": "AIwork4me/B-ROCm", "license": "MIT", "commercial_use": "none",
     "platforms": {"linux-rocm": {"badge": "community", "overall": 93.0}}},
    {"model_id": "c", "repo": "AIwork4me/C-ROCm", "license": "Apache-2.0", "commercial_use": "none",
     "platforms": {"linux-rocm": {"badge": "community-wanted", "overall": None}}},
]

def test_render_hub_splits_three_tiers():
    from scripts.generate_registry import render_hub
    out = render_hub(ROWS)
    assert "Flagship comparison (verified)" in out and "| a " in out
    assert "Community (also evaluated)" in out and "| b " in out
    assert "Incoming (community-wanted)" in out and "| c " in out
    # c must NOT appear in the flagship section
    flagship = out.split("## Community")[0]
    assert "| c " not in flagship

def test_render_hub_external_reference_is_link_only():
    from scripts.generate_registry import render_hub
    out = render_hub(ROWS, external_ref_url="https://example.com/paper")
    assert "External reference" in out
    assert "https://example.com/paper" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /workspace/omnidocbench-rocm && python -m pytest tests/test_renderer_tiers.py -v`
Expected: FAIL — `ImportError: cannot import name 'render_hub'`.

- [ ] **Step 3: Implement render_hub**

In `scripts/generate_registry.py`, add (keeping `render_table`/`_cell` unchanged):

```python
_BADGE_RANK = {"verified": 3, "community": 2, "community-wanted": 1}

def _best_badge(row: dict) -> str:
    plats = row.get("platforms", {}) or {}
    badges = [v.get("badge", "community-wanted") for v in plats.values() if isinstance(v, dict)]
    return max(badges, key=lambda b: _BADGE_RANK.get(b, 0)) if badges else "community-wanted"

def render_hub(rows: list[dict], external_ref_url: str | None = None) -> str:
    flagship, community, incoming = [], [], []
    for r in rows:
        {"verified": flagship, "community": community}.get(_best_badge(r), incoming).append(r)
    parts = []
    if flagship:
        parts.append("## Flagship comparison (verified)\n\n" + render_table(flagship))
    if community:
        parts.append("## Community (also evaluated)\n\n" + render_table(community))
    if incoming:
        parts.append("## Incoming (community-wanted)\n\n" + render_table(incoming))
    if external_ref_url:
        parts.append(
            "## External reference\n\n"
            "Closed-SOTA calibration: [OmniDocBench paper](" + external_ref_url +
            ") — cited, not reproduced here, never badged.")
    return "\n\n".join(parts) if parts else "(no models)"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /workspace/omnidocbench-rocm && python -m pytest tests/test_renderer_tiers.py tests/test_registry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /workspace/omnidocbench-rocm
git add scripts/generate_registry.py tests/test_renderer_tiers.py
git commit -m "feat(renderer): 3-tier flagship/community/incoming split (ADR-0003/0004)"
```

### Task 7: License column in the rendered table

**Files:**
- Modify: `scripts/generate_registry.py` (`COLUMNS`, `render_table`)
- Test: `tests/test_renderer_tiers.py` (append)

**Interfaces:**
- Produces: each table row shows a `License` column = `row["license"]` (or `—`).

- [ ] **Step 1: Write the failing test**

```python
def test_render_table_shows_license_column():
    from scripts.generate_registry import render_table
    out = render_table(ROWS[:1])
    assert "| License |" in out
    assert "| Apache-2.0 |" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /workspace/omnidocbench-rocm && python -m pytest tests/test_renderer_tiers.py::test_render_table_shows_license_column -v`
Expected: FAIL (no License column today).

- [ ] **Step 3: Add the column**

In `scripts/generate_registry.py`:

```python
COLUMNS = ("Model", "Repo", "License", "linux-rocm", "windows-hip")
```

and in `render_table`, change the row append to include the license cell:

```python
        lines.append(
            "| {model} | {repo} | {license} | {linux} | {windows} |".format(
                model=r.get("model_id", ""),
                repo=r.get("repo", ""),
                license=r.get("license") or "—",
                linux=_cell(platforms.get("linux-rocm")),
                windows=_cell(platforms.get("windows-hip")),
            )
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /workspace/omnidocbench-rocm && python -m pytest tests/test_renderer_tiers.py tests/test_registry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /workspace/omnidocbench-rocm
git add scripts/generate_registry.py tests/test_renderer_tiers.py
git commit -m "feat(renderer): License column in comparison table (ADR-0006)"
```

---

## Feature D — Reproduction-recipe artifact + conformance gate (ADR-0003)

### Task 8: Define the `REPRO.yaml` artifact + require it in conformance

**Files:**
- Modify: `contracts/artifact-schema.json` (new `repro_recipe` sub-schema), `engine/omnidocbench_rocm/conformance.py`
- Test: `tests/test_repro_recipe.py`

**Interfaces:**
- Produces: a `REPRO.yaml` at repo root (exact command, pinned weights revision, backend, venv/docker) — validated by a new `repro_recipe` schema; `check_repo` fails when it's missing.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
from omnidocbench_rocm.conformance import check_repo
from omnidocbench_rocm.schema import validate_artifact
import yaml

REPRO = {
    "command": "omnidocbench-rocm infer --adapter adapter/run_adapter.py --img-dir <v16> --out-dir preds",
    "weights_revision": "de8f10ad2f00a0cefd790b526de8a65dcfdb3205",
    "backend": "vllm",
    "environment": "/opt/venv (vLLM 0.16.1 ROCm)",
}

def test_repro_recipe_schema_valid():
    validate_artifact("repro_recipe", REPRO)  # must not raise

def test_conformance_requires_repro_yaml(tmp_path):
    repo = tmp_path / "model-repo"
    # ... conformant fixture (adapter/, eval/configs/, NOTICE/) but NO REPRO.yaml ...
    report = check_repo(repo)
    assert any("REPRO.yaml" in f for f in report.failures), report.failures

def test_conformance_passes_with_repro_yaml(tmp_path):
    repo = tmp_path / "model-repo"
    # ... same fixture ...
    (repo / "REPRO.yaml").write_text(yaml.safe_dump(REPRO))
    report = check_repo(repo)
    assert "missing REPRO.yaml" not in report.failures
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /workspace/omnidocbench-rocm && python -m pytest tests/test_repro_recipe.py -v`
Expected: FAIL (no `repro_recipe` schema; no REPRO.yaml conformance check).

- [ ] **Step 3a: Add the schema**

In `contracts/artifact-schema.json`, add a new top-level sub-schema alongside `model_card`:

```json
  "repro_recipe": {
    "type": "object",
    "required": ["command", "weights_revision", "backend", "environment"],
    "properties": {
      "command": {"type": "string"},
      "weights_revision": {"type": "string"},
      "backend": {"type": "string"},
      "environment": {"type": "string"}
    },
    "additionalProperties": true
  }
```

> If `schema.py`'s `_VALIDATORS` is built by scanning sub-schemas automatically, this is picked up for free; if it's an explicit dict, register `"repro_recipe"` there (check `schema.py` and mirror how `model_card` is registered).

- [ ] **Step 3b: Add the conformance check**

In `engine/omnidocbench_rocm/conformance.py` `check_repo`, add:

```python
    if not (repo / "REPRO.yaml").exists():
        r.add("missing REPRO.yaml (reproduction recipe — ADR-0003)")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /workspace/omnidocbench-rocm && python -m pytest tests/test_repro_recipe.py tests/test_conformance.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /workspace/omnidocbench-rocm
git add contracts/artifact-schema.json engine/omnidocbench_rocm/conformance.py tests/test_repro_recipe.py
git commit -m "feat(conformance): REPRO.yaml reproduction recipe gate (ADR-0003)"
```

---

## Feature E — `list` / `doctor` discovery CLI (ADR-0005)

### Task 9: `list` subcommand

**Files:**
- Modify: `engine/omnidocbench_rocm/cli.py`
- Test: `tests/test_cli_list_doctor.py`

**Interfaces:**
- Produces: `omnidocbench-rocm list [--registry PATH] [--format text|json]` prints each model_id + best badge.

- [ ] **Step 1: Write the failing test**

```python
import json, subprocess, sys
from pathlib import Path

REG = """
- model_id: a
  repo: AIwork4me/A-ROCm
  license: Apache-2.0
  commercial_use: none
  platforms:
    linux-rocm: {badge: verified, overall: 95.0}
- model_id: b
  repo: AIwork4me/B-ROCm
  license: MIT
  commercial_use: none
  platforms:
    linux-rocm: {badge: community, overall: 93.0}
"""

def test_cli_list_text(tmp_path):
    reg = tmp_path / "registry.yaml"; reg.write_text(REG)
    from omnidocbench_rocm.cli import main
    rc = main(["list", "--registry", str(reg), "--format", "text"])
    assert rc == 0

def test_cli_list_json(tmp_path, capsys):
    reg = tmp_path / "registry.yaml"; reg.write_text(REG)
    from omnidocbench_rocm.cli import main
    rc = main(["list", "--registry", str(reg), "--format", "json"])
    out = json.loads(capsys.readouterr().out)
    ids = [m["model_id"] for m in out]
    assert ids == ["a", "b"] and out[0]["best_badge"] == "verified"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /workspace/omnidocbench-rocm && python -m pytest tests/test_cli_list_doctor.py::test_cli_list_json -v`
Expected: FAIL — `list` is not a registered subcommand (`error: invalid choice`).

- [ ] **Step 3: Register + implement the subcommand**

In `engine/omnidocbench_rocm/cli.py`, after the existing `sub.add_parser(...)` calls, add:

```python
    ls = sub.add_parser("list")
    ls.add_argument("--registry", default="hub/registry.yaml")
    ls.add_argument("--format", default="text", choices=["text", "json"])
```

In the dispatch section, add a handler:

```python
    if a.cmd == "list":
        from scripts.generate_registry import generate_registry, _best_badge  # or import locally
        import json as _json, sys as _sys
        # NOTE: scripts may not be on the path inside the installed package — if so,
        # move generate_registry/_best_badge into the engine package (engine/omnidocbench_rocm/registry.py)
        # and import from there. Prefer that to a scripts/ import at runtime.
        rows = generate_registry(a.registry)
        rows = [{"model_id": r.get("model_id"), "repo": r.get("repo"),
                 "license": r.get("license"), "best_badge": _best_badge(r)} for r in rows]
        if a.format == "json":
            print(_json.dumps(rows, indent=2))
        else:
            for r in rows:
                print(f"{r['model_id']:<24} {r['best_badge']:<16} {r.get('license') or '—'}")
        return 0
```

> **Refactor note:** `generate_registry`/`_best_badge` currently live in `scripts/`. For the CLI to import them cleanly when installed, **move** them into `engine/omnidocbench_rocm/registry.py` and have `scripts/generate_registry.py` become a thin wrapper that imports from the package. Do this refactor as part of this task (update `tests/test_registry.py` import path accordingly). This keeps the engine self-contained (ADR-0005's "single integration seam").

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /workspace/omnidocbench-rocm && python -m pytest tests/test_cli_list_doctor.py tests/test_registry.py tests/test_renderer_tiers.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /workspace/omnidocbench-rocm
git add engine/omnidocbench_rocm/cli.py engine/omnidocbench_rocm/registry.py scripts/generate_registry.py tests/test_cli_list_doctor.py tests/test_registry.py
git commit -m "feat(cli): list subcommand; move registry logic into the package (ADR-0005)"
```

### Task 10: `doctor` subcommand

**Files:**
- Modify: `engine/omnidocbench_rocm/cli.py`, `engine/omnidocbench_rocm/conformance.py` (add `readiness_report`)
- Test: `tests/test_cli_list_doctor.py` (append)

**Interfaces:**
- Consumes: `check_repo(repo)` (Task 3) + adapter-config presence.
- Produces: `omnidocbench-rocm doctor <repo_path>` prints conformance failures + a readiness hint (adapter_config.py present? backend set?).

- [ ] **Step 1: Write the failing test**

```python
def test_cli_doctor_reports_missing_notice(tmp_path, capsys):
    from omnidocbench_rocm.cli import main
    repo = tmp_path / "repo"; (repo / "adapter").mkdir(parents=True)
    (repo / "adapter" / "run_adapter.py").write_text("# stub\n")
    rc = main(["doctor", str(repo)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "NOTICE" in out  # missing NOTICE flagged

def test_cli_doctor_clean_repo(tmp_path, capsys):
    from omnidocbench_rocm.cli import main
    repo = tmp_path / "repo"
    # ... full conformant fixture incl NOTICE + REPRO.yaml ...
    rc = main(["doctor", str(repo)])
    assert rc == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /workspace/omnidocbench-rocm && python -m pytest tests/test_cli_list_doctor.py::test_cli_doctor_reports_missing_notice -v`
Expected: FAIL — `doctor` not a registered subcommand.

- [ ] **Step 3: Register + implement**

In `cli.py`, add the subparser:

```python
    dr = sub.add_parser("doctor")
    dr.add_argument("repo_path")
```

and the handler:

```python
    if a.cmd == "doctor":
        from omnidocbench_rocm.conformance import check_repo
        report = check_repo(Path(a.repo_path))
        if report.ok:
            print("READY: repo is conformant.")
            # best-effort readiness hint
            cfg = Path(a.repo_path) / "adapter" / "adapter_config.py"
            print("  adapter_config.py present:", cfg.exists())
            return 0
        print("NOT READY:")
        for f in report.failures:
            print(" -", f)
        return 1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /workspace/omnidocbench-rocm && python -m pytest tests/test_cli_list_doctor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /workspace/omnidocbench-rocm
git add engine/omnidocbench_rocm/cli.py tests/test_cli_list_doctor.py
git commit -m "feat(cli): doctor readiness subcommand (ADR-0005)"
```

### Task 11: Update existing model_card.json + registry.yaml to the new fields (data migration)

**Files:**
- Modify: `hub/registry.yaml`; the 4 model repos' `model_card.json` (add `license`/`commercial_use`); each model repo gains a `NOTICE` (HunyuanOCR + MinerU already have one; PaddleOCR/Unlimited need one) and a `REPRO.yaml`.

**Interfaces:** none new — populates the fields the above tasks now require.

- [ ] **Step 1: Write a regression test that the live registry validates**

```python
def test_live_registry_validates():
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
    from validate_registry import validate_registry
    from generate_registry import generate_registry
    rows = generate_registry(pathlib.Path(__file__).resolve().parents[1] / "hub" / "registry.yaml")
    errors = validate_registry(rows)
    assert errors == [], errors
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /workspace/omnidocbench-rocm && python -m pytest tests/test_registry_validation.py::test_live_registry_validates -v`
Expected: FAIL — the live `hub/registry.yaml` lacks `license`/`commercial_use`.

- [ ] **Step 3: Populate the fields**

In `hub/registry.yaml`, add to each entry (from each model's NOTICE / upstream license):
- `paddleocr-vl-1.6`: `license: MIT`, `commercial_use: no restriction`
- `unlimited-ocr`: `license: MIT` (verify Baidu Unlimited-OCR weights license — check HF card), `commercial_use: <per license>`
- `mineru2.5`: `license: MinerU Open Source License`, `commercial_use: commercial threshold MAU>100M or revenue>$20M`
- `hunyuan-ocr`: `license: Tencent Hunyuan Community License`, `commercial_use: see license (commercial-use conditions)`

Add `license`/`commercial_use` to each model repo's `model_card.json`. Add a `NOTICE` to PaddleOCR-VL-ROCm + Unlimited-OCR-ROCm (copy MinerU's NOTICE structure). Add a `REPRO.yaml` to each (best-effort command + pinned weights revision + backend + environment — for the 2 `community-wanted` models, populate once they onboard).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /workspace/omnidocbench-rocm && python -m pytest tests/test_registry_validation.py tests/test_conformance.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /workspace/omnidocbench-rocm
git add hub/registry.yaml
git commit -m "chore(registry): populate license/commercial_use for all entries (ADR-0006)"
# then, per model repo:
cd /workspace/PaddleOCR-VL-ROCm && git add NOTICE model_card.json REPRO.yaml && git commit -m "chore: add NOTICE + license fields + REPRO.yaml (ADR-0003/0006)"
# repeat for the other model repos
```

---

## Self-Review (run after writing — findings applied inline)

**1. Spec coverage:** efficiency (spec §5.2) → Tasks 4–5 ✓; renderer 3-tier (§5.3) → Tasks 6–7 ✓; repro recipe (§5.4) → Task 8 ✓; license/NOTICE (§5.7) → Tasks 1–3 + 11 ✓; list/doctor (§5.9) → Tasks 9–10 ✓. Per-category breakdown (§3 completeness) is **rendering of existing `metric_result.json` categories** — not a code task here; it lands with the MkDocs site runbook (out of plan). Noted.

**2. Placeholder scan:** no TBD/TODO/"add error handling". Two intentional `# ...` ellipses mark *reuse of the existing conformant-repo fixture* (defined in `tests/test_conformance.py`) — the implementer copies that fixture, not invents it. Acceptable; flagged in-step.

**3. Type consistency:** `_derive_efficiency` (Task 5) used consistently; `_best_badge` defined in Task 6, consumed in Task 9 (and moved into the package in Task 9's refactor); `render_hub`/`render_table` signatures consistent; `check_repo`/`ConformanceReport` used in Tasks 3, 8, 10. The Task 9 refactor (move `generate_registry`/`_best_badge` from `scripts/` → `engine/omnidocbench_rocm/registry.py`) is called out explicitly so the import path stays consistent.

## Out of plan (runbooks — operational, GPU/content-dependent)

- Onboard `unlimited-ocr` + `hunyuan-ocr` to `community` on linux-rocm (run inference on Radeon, commit bundles) — `docs/onboarding-runbook.md`.
- Maintainer `verified` Docker scoring-repro for the 4 reference models (CPU) + `VERIFIED.yaml` — `docs/onboarding-runbook.md` Step 7.
- MkDocs site build + per-category disclosure rendering — roadmap.
- `docs/selection-policy.md` (reference-set criteria + graduation) — ADR-0004.
- Radeon-Cloud (anruicloud) workshop + cross-link — hardware decision.
