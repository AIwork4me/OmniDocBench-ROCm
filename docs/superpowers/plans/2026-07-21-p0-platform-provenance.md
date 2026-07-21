# P0 — Platform adapter-config + provenance chain: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make OmniDocBench-ROCm carry a user's inference config (backend, server URL, API model name, predictions dir) truthfully and consistently across `CLI → stage_infer → adapter subprocess → _run_stats.json → stage_publish → provenance.json`, so the platform can reliably support multi-backend model repos.

**Architecture:** A pure `_build_adapter_command` forwards config to the adapter subprocess (no `shell=True`); `stage_infer` returns an `InferResult` carrying the real argv; `stage_publish` records the real predictions dir and the adapter-reported backend (`_run_stats.json["engine"]`), refusing to publish on a requested/actual backend mismatch; `run --stage all` threads one config dict into both infer and publish.

**Tech Stack:** Python ≥3.10, argparse (no new CLI framework), jsonschema, pytest, hatchling build. Existing engine package `omnidocbench_rocm`.

**Spec:** `docs/superpowers/specs/2026-07-21-p0-platform-provenance-design.md`
**Branch:** `feat/p0-platform-provenance` (created; spec already committed).

## Global Constraints

Copied verbatim from the spec — every task implicitly includes these:

- **No `shell=True`, no shell string concatenation** in subprocess invocation. Adapter argv built as a `list[str]`.
- **Do not modify** MinerU-ROCm, `hub/registry.yaml` (model state/scores), MinerU historical results, badge tiers. Do not rerun the 1651-page eval.
- **No Windows-HIP backend**, no CLI-framework swap (Typer/Click), no whole-CLI refactor.
- **Filesystem-decoupled**: the engine invokes the adapter as a subprocess and never imports it; no model deps in the engine.
- **No unrelated fixes.** Record other findings as follow-ups (C1–C5 in the spec).
- **Type annotations** on all new/changed signatures; **no swallowed exceptions**; **actionable error messages**; backward-compatible first.
- **CLI / stage / artifact three-layer separation** stays clean.
- **No fake provenance** — every recorded field is real and consistent end-to-end.
- Tests must not depend on GPU, network, or external models.
- Python ≥3.10 → `list[str]` / `dict` / `X | None` syntax is allowed.

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `engine/omnidocbench_rocm/stages.py` | `_build_adapter_command` (pure); `stage_infer`→`InferResult`; `_assert_full_set` returns dict; `stage_publish` gains `predictions_dir` + `requested_backend` + mismatch gate | 1,2,4,5 |
| `engine/omnidocbench_rocm/types.py` | `InferResult` dataclass | 2 |
| `engine/omnidocbench_rocm/artifact_utils.py` | `write_provenance` emits `backend` | 3 |
| `contracts/artifact-schema.json` | `provenance.backend` → required | 3 |
| `engine/omnidocbench_rocm/cli.py` | `infer`/`publish`/`run` flags + helpers + `_orchestrate_run` threading | 6,7 |
| `template/{{cookiecutter.repo_name}}/adapter/run_adapter.py` | accept `--skip-existing` (real skip) | 8 |
| `tests/test_stages.py` | command-build + stage_infer + publish/prediction_dir/backend tests | 1,2,4,5 |
| `tests/test_artifact_utils.py` / `tests/test_schema.py` | provenance backend tests | 3 |
| `tests/test_contract_integration.py` | updated for `InferResult` + `predictions_dir` + backend | 2,4 |
| `tests/test_cli.py` | updated mock + run-threading tests | 7 |
| `tests/test_template.py` | `--skip-existing` template test | 8 |
| `tests/test_smoke_config_pipeline.py` (new) | CPU e2e smoke | 9 |
| `contracts/adapter.md`, `docs/architecture.md`, `docs/contribute-a-model.md`, `docs/onboarding-runbook.md`, `README.md`, `template/.../Makefile` | docs sync | 10 |
| `pyproject.toml`, `engine/omnidocbench_rocm/__init__.py`, `CHANGELOG.md` | version 0.2.0 → 0.3.0 | 11 |

---

## Task 1: `_build_adapter_command` — pure command builder

**Files:**
- Modify: `engine/omnidocbench_rocm/stages.py` (add `_build_adapter_command`; rewrite the `cmd = [...]` construction inside `stage_infer` to call it — but the `stage_infer` return-type change is Task 2; here only swap the `cmd` construction).
- Test: `tests/test_stages.py` (add 7 tests + import).

**Interfaces:**
- Produces: `_build_adapter_command(*, adapter_path: Path, img_dir: Path, out_dir: Path, platform: str, config: dict) -> list[str]`. Forwards `config["backend"]`→`--backend`, `config["server_url"]`→`--server-url`, `config["api_model_name"]`→`--api-model-name`, `config["skip_existing"]`→`--skip-existing`, only when truthy. Unknown keys ignored.

- [ ] **Step 1: Write the 7 failing tests**

Append to `tests/test_stages.py` (the file already imports `sys`, `Path`):

```python
from omnidocbench_rocm.stages import _build_adapter_command


def test_build_adapter_command_minimal():
    cmd = _build_adapter_command(adapter_path=Path("/a/run_adapter.py"),
                                 img_dir=Path("/imgs"), out_dir=Path("/out"),
                                 platform="linux-rocm", config={})
    assert cmd == [sys.executable, "/a/run_adapter.py", "--img-dir", "/imgs",
                   "--out-dir", "/out", "--platform", "linux-rocm"]


def test_build_adapter_command_forwards_backend():
    cmd = _build_adapter_command(adapter_path=Path("/a.py"), img_dir=Path("/i"),
                                 out_dir=Path("/o"), platform="linux-rocm",
                                 config={"backend": "vlm-vllm"})
    assert "--backend" in cmd
    assert cmd[cmd.index("--backend") + 1] == "vlm-vllm"


def test_build_adapter_command_forwards_server_url():
    cmd = _build_adapter_command(adapter_path=Path("/a.py"), img_dir=Path("/i"),
                                 out_dir=Path("/o"), platform="linux-rocm",
                                 config={"server_url": "http://127.0.0.1:8265/v1"})
    assert "--server-url" in cmd
    assert cmd[cmd.index("--server-url") + 1] == "http://127.0.0.1:8265/v1"


def test_build_adapter_command_forwards_api_model_name():
    cmd = _build_adapter_command(adapter_path=Path("/a.py"), img_dir=Path("/i"),
                                 out_dir=Path("/o"), platform="linux-rocm",
                                 config={"api_model_name": "mineru-pro"})
    assert "--api-model-name" in cmd
    assert cmd[cmd.index("--api-model-name") + 1] == "mineru-pro"


def test_build_adapter_command_forwards_skip_existing():
    cmd = _build_adapter_command(adapter_path=Path("/a.py"), img_dir=Path("/i"),
                                 out_dir=Path("/o"), platform="linux-rocm",
                                 config={"skip_existing": True})
    assert "--skip-existing" in cmd


def test_build_adapter_command_omits_empty_values():
    cmd = _build_adapter_command(adapter_path=Path("/a.py"), img_dir=Path("/i"),
                                 out_dir=Path("/o"), platform="linux-rocm",
                                 config={"backend": "", "server_url": None,
                                         "api_model_name": "", "skip_existing": False})
    assert "--backend" not in cmd
    assert "--server-url" not in cmd
    assert "--api-model-name" not in cmd
    assert "--skip-existing" not in cmd


def test_build_adapter_command_handles_paths_with_spaces():
    cmd = _build_adapter_command(adapter_path=Path("/my adapter/run_adapter.py"),
                                 img_dir=Path("/img dir"), out_dir=Path("/out dir"),
                                 platform="linux-rocm",
                                 config={"backend": "v",
                                         "server_url": "http://a b/v1",
                                         "api_model_name": "model name"})
    # spaces stay inside one argv token (no shell splitting/quoting)
    assert "/my adapter/run_adapter.py" in cmd
    assert "/img dir" in cmd
    assert "/out dir" in cmd
    assert "http://a b/v1" in cmd
    assert "model name" in cmd
    assert cmd.count("/my adapter/run_adapter.py") == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_stages.py -k build_adapter_command -v`
Expected: FAIL — `ImportError: cannot import name '_build_adapter_command'`.

- [ ] **Step 3: Implement `_build_adapter_command` and use it in `stage_infer`**

In `engine/omnidocbench_rocm/stages.py`, add the function above `stage_infer` (after the `IMAGE_EXTENSIONS` line):

```python
def _build_adapter_command(*, adapter_path: Path, img_dir: Path, out_dir: Path,
                           platform: str, config: dict) -> list[str]:
    """Build the adapter subprocess argv. Forwards only truthy config keys.

    No shell=True, no string concatenation: every value is a separate argv
    element, so paths/URLs/model names with spaces are safe by construction.
    Unknown config keys are ignored.
    """
    cmd = [sys.executable, str(adapter_path),
           "--img-dir", str(img_dir), "--out-dir", str(out_dir),
           "--platform", platform]
    if config.get("backend"):
        cmd += ["--backend", str(config["backend"])]
    if config.get("server_url"):
        cmd += ["--server-url", str(config["server_url"])]
    if config.get("api_model_name"):
        cmd += ["--api-model-name", str(config["api_model_name"])]
    if config.get("skip_existing"):
        cmd += ["--skip-existing"]
    return cmd
```

Then in `stage_infer`, replace the literal `cmd = [sys.executable, str(adapter_path), "--img-dir", str(img_dir), "--out-dir", str(out_dir), "--platform", platform]` block with:

```python
    cmd = _build_adapter_command(adapter_path=adapter_path, img_dir=img_dir,
                                 out_dir=out_dir, platform=platform, config=config)
```

(Leave the rest of `stage_infer` — the `subprocess.run`, returncode check, `_run_stats.json` read, and `return json.loads(...)` — unchanged for now. Task 2 changes the return type.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_stages.py -v`
Expected: PASS — all stage tests green, including the 7 new ones. (The existing `test_stage_infer_runs_adapter_subprocess` still passes: `config={}` produces the minimal 7-element argv, which the existing `FAKE_ADAPTER` accepts.)

- [ ] **Step 5: Commit**

```bash
git add engine/omnidocbench_rocm/stages.py tests/test_stages.py
git commit -m "feat(stages): pure _build_adapter_command forwards infer config

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: `InferResult` + `stage_infer` returns the real argv

**Files:**
- Modify: `engine/omnidocbench_rocm/types.py` (add `InferResult`).
- Modify: `engine/omnidocbench_rocm/stages.py` (`stage_infer` returns `InferResult`; richer error message keeps stderr).
- Test: `tests/test_stages.py` (add fake-adapter constants + 3 tests; update existing `test_stage_infer_runs_adapter_subprocess`).

**Interfaces:**
- Consumes: `_build_adapter_command` (Task 1).
- Produces: `InferResult` in `omnidocbench_rocm.types` with fields `run_stats: dict` and `adapter_argv: list[str]`. `stage_infer(...)` now returns `InferResult` (was `dict`). Downstream (Task 7) reads `infer_result.adapter_argv`.

- [ ] **Step 1: Add `InferResult` and update the existing test (these define the new contract)**

In `engine/omnidocbench_rocm/types.py`, add after the `RunSummary` class:

```python
@dataclass
class InferResult:
    """What stage_infer returns: the loaded run_stats + the actual adapter argv.

    adapter_argv is the real subprocess command (argv[0] = sys.executable); the
    engine serializes it (shlex.join) into provenance.adapter_command so the
    recorded command is the one that actually ran, not a hand-typed guess.
    """
    run_stats: dict
    adapter_argv: list[str]
```

In `tests/test_stages.py`, update the existing test's assertions (it currently does `summary["count"]`):

```python
def test_stage_infer_runs_adapter_subprocess(tmp_path, monkeypatch):
    img_dir = tmp_path / "imgs"; img_dir.mkdir()
    (img_dir / "a.png").write_bytes(b"x"); (img_dir / "b.png").write_bytes(b"x")
    adapter = tmp_path / "fake_adapter.py"; adapter.write_text(FAKE_ADAPTER)
    out_dir = tmp_path / "preds"
    result = stages.stage_infer(
        adapter_path=adapter, img_dir=img_dir, out_dir=out_dir,
        platform="linux-rocm", config={})
    assert result.run_stats["count"] == 2 and result.run_stats["ok"] == 2
    assert (out_dir / "a.md").exists() and (out_dir / "_run_stats.json").exists()
```

- [ ] **Step 2: Add the 3 new failing tests + fake-adapter constants**

Append to `tests/test_stages.py`:

```python
from omnidocbench_rocm.types import InferResult

# Fake adapter that accepts the forwarded config flags, echoes its argv to
# _argv.json, writes one .md per image, and writes _run_stats.json with
# engine=<--backend>. Used by the stage_infer config-forwarding tests.
FAKE_ADAPTER_CFG = '''
import argparse, json, sys
from pathlib import Path
from omnidocbench_rocm.types import RunSummary, PageStatus
p = argparse.ArgumentParser()
p.add_argument("--img-dir", required=True)
p.add_argument("--out-dir", required=True)
p.add_argument("--platform", required=True)
p.add_argument("--backend", default="smoke")
p.add_argument("--server-url", default="")
p.add_argument("--api-model-name", default="")
p.add_argument("--skip-existing", action="store_true")
a = p.parse_args()
out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
(out / "_argv.json").write_text(json.dumps(sys.argv[1:]))
imgs = sorted(q for q in Path(a.img_dir).iterdir() if q.suffix.lower() in {".png", ".jpg"})
for i in imgs:
    (out / f"{i.stem}.md").write_text("# " + i.stem + "\\n", encoding="utf-8")
rs = RunSummary(len(imgs), len(imgs), 0, 0, None,
                [PageStatus(i.name, "ok") for i in imgs], engine=a.backend)
rs.write(out / "_run_stats.json")
'''

# Fake adapter that exits non-zero with a stderr line.
FAKE_ADAPTER_FAIL = '''
import sys
sys.stderr.write("boom: model exploded\\n")
sys.exit(3)
'''


def test_stage_infer_invokes_adapter_with_config(tmp_path):
    img_dir = tmp_path / "imgs"; img_dir.mkdir()
    (img_dir / "a.png").write_bytes(b"x")
    adapter = tmp_path / "cfg_adapter.py"; adapter.write_text(FAKE_ADAPTER_CFG)
    out_dir = tmp_path / "preds"
    stages.stage_infer(adapter_path=adapter, img_dir=img_dir, out_dir=out_dir,
                       platform="linux-rocm",
                       config={"backend": "vlm-vllm", "server_url": "http://x/v1",
                               "api_model_name": "m", "skip_existing": True})
    argv = json.loads((out_dir / "_argv.json").read_text())
    assert "--backend" in argv and "vlm-vllm" in argv
    assert "--server-url" in argv and "http://x/v1" in argv
    assert "--api-model-name" in argv and "m" in argv
    assert "--skip-existing" in argv


def test_stage_infer_reads_run_stats(tmp_path):
    img_dir = tmp_path / "imgs"; img_dir.mkdir()
    (img_dir / "a.png").write_bytes(b"x")
    adapter = tmp_path / "cfg_adapter.py"; adapter.write_text(FAKE_ADAPTER_CFG)
    out_dir = tmp_path / "preds"
    result = stages.stage_infer(adapter_path=adapter, img_dir=img_dir, out_dir=out_dir,
                                platform="linux-rocm", config={"backend": "vlm-vllm"})
    assert isinstance(result, InferResult)
    assert result.run_stats["count"] == 1
    assert result.run_stats["engine"] == "vlm-vllm"
    assert result.adapter_argv[0] == sys.executable
    assert "--backend" in result.adapter_argv


def test_stage_infer_reports_adapter_stderr_on_failure(tmp_path):
    img_dir = tmp_path / "imgs"; img_dir.mkdir()
    (img_dir / "a.png").write_bytes(b"x")
    adapter = tmp_path / "fail_adapter.py"; adapter.write_text(FAKE_ADAPTER_FAIL)
    out_dir = tmp_path / "preds"
    try:
        stages.stage_infer(adapter_path=adapter, img_dir=img_dir, out_dir=out_dir,
                           platform="linux-rocm", config={})
        assert False, "should have raised SystemExit"
    except SystemExit as e:
        assert "boom: model exploded" in str(e)
        assert "3" in str(e)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_stages.py -v`
Expected: FAIL — `test_stage_infer_reads_run_stats` fails (`InferResult` instance check: `stage_infer` still returns a `dict`); `test_stage_infer_runs_adapter_subprocess` fails (`dict has no attribute 'run_stats'`).

- [ ] **Step 4: Change `stage_infer` to return `InferResult`**

In `engine/omnidocbench_rocm/stages.py`, update the imports and `stage_infer`:

```python
from .types import RunSummary, InferResult
```

Replace the `stage_infer` body's tail (the returncode check onward) so the full function reads:

```python
def stage_infer(*, adapter_path: Path, img_dir: Path, out_dir: Path,
                platform: str, config: dict) -> InferResult:
    """Invoke the adapter as a SUBPROCESS (filesystem-decoupled). Never import it.

    Returns the loaded _run_stats.json plus the actual argv that ran (so the
    engine can record the real command in provenance).
    """
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    cmd = _build_adapter_command(adapter_path=adapter_path, img_dir=img_dir,
                                 out_dir=out_dir, platform=platform, config=config)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"adapter failed (exit {proc.returncode}):\n{proc.stderr}")
    rs_path = out_dir / "_run_stats.json"
    if not rs_path.exists():
        raise SystemExit(f"adapter wrote no _run_stats.json: {rs_path}")
    run_stats = json.loads(rs_path.read_text(encoding="utf-8"))
    return InferResult(run_stats=run_stats, adapter_argv=cmd)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_stages.py -v`
Expected: PASS — all stage tests green.

- [ ] **Step 6: Commit**

```bash
git add engine/omnidocbench_rocm/types.py engine/omnidocbench_rocm/stages.py tests/test_stages.py
git commit -m "feat(stages): stage_infer returns InferResult with real argv

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: `provenance.backend` (adapter-reported) + schema-required

**Files:**
- Modify: `engine/omnidocbench_rocm/artifact_utils.py` (`write_provenance` emits `backend`).
- Modify: `contracts/artifact-schema.json` (add `backend` to the `provenance` `required` list — line 32).
- Test: `tests/test_artifact_utils.py` (+1), `tests/test_schema.py` (+1).

**Interfaces:**
- Produces: `provenance.backend` (string) = `_run_stats.json["engine"]`, now schema-required. `write_provenance` derives it internally (no new param).

- [ ] **Step 1: Write the 2 failing tests**

In `tests/test_artifact_utils.py`, append:

```python
def test_provenance_contains_backend(tmp_path):
    rs = tmp_path / "_run_stats.json"
    rs.write_text(json.dumps({"schema_version": 1, "count": 3, "ok": 3, "fail": 0,
                              "fallback": 0, "limit_pages": None, "engine": "vllm",
                              "stats": []}))
    out = tmp_path / "prov.json"
    au.write_provenance(destination=out, git_commit="c", engine_version="0.3.0",
                        model_id="m", platform="linux-rocm", server_url="",
                        api_model_name="", adapter_command="python a.py",
                        scoring_config_path=tmp_path / "c.yaml",
                        dataset_manifest_path=tmp_path / "m.json",
                        dataset_revision="v1.6", predictions_dir=tmp_path / "preds",
                        metric_result_paths=[tmp_path / "metric.json"],
                        run_summary_paths=[tmp_path / "rs.json"], run_stats_path=rs)
    prov = json.loads(out.read_text())
    assert prov["backend"] == "vllm"
```

In `tests/test_schema.py`, append:

```python
def test_provenance_schema_accepts_backend():
    base = {"schema_version": 1, "created_at_utc": "t", "git_commit": "c",
            "platform": "linux-rocm", "engine_version": "0.3.0", "model_id": "m",
            "adapter_command": "python a.py", "dataset_manifest_path": "m.json",
            "dataset_revision": "v1.6", "prediction_dir": "/p", "page_count": 3,
            "ok_pages": 3, "failed_pages": 0, "metric_result_paths": [],
            "run_summary_paths": [], "run_stats_path": "/r.json", "backend": "vllm"}
    validate_artifact("provenance", base)  # has backend -> valid
    bad = dict(base); del bad["backend"]
    try:
        validate_artifact("provenance", bad)
        assert False, "provenance should require backend"
    except Exception:
        pass
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_artifact_utils.py::test_provenance_contains_backend tests/test_schema.py::test_provenance_schema_accepts_backend -v`
Expected: FAIL — `test_provenance_contains_backend` (no `backend` key); `test_provenance_schema_accepts_backend` (backend not required yet, so the `bad` case validates and hits `assert False`).

- [ ] **Step 3: Emit `backend` in `write_provenance`; make it schema-required**

In `engine/omnidocbench_rocm/artifact_utils.py`, inside the `provenance = { ... }` dict in `write_provenance` (which already does `run_stats = load_json(run_stats_path)` at line 182), add this key next to `"prediction_dir"`:

```python
        "backend": run_stats.get("engine", ""),   # adapter-reported (_run_stats.json)
```

In `contracts/artifact-schema.json`, line 32, add `"backend"` to the `provenance` `required` list:

```json
      "required": ["schema_version", "created_at_utc", "git_commit", "platform", "engine_version", "model_id", "adapter_command", "dataset_manifest_path", "dataset_revision", "prediction_dir", "page_count", "ok_pages", "failed_pages", "metric_result_paths", "run_summary_paths", "run_stats_path", "backend"],
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_artifact_utils.py tests/test_schema.py tests/test_contract_integration.py -v`
Expected: PASS. (`test_write_provenance_validates` still passes: its run_stats has `engine="official"`, so `backend` is emitted; `test_fake_adapter_infer_then_publish` still passes — its provenance is produced by `write_provenance`, which now emits `backend`.)

- [ ] **Step 5: Commit**

```bash
git add engine/omnidocbench_rocm/artifact_utils.py contracts/artifact-schema.json tests/test_artifact_utils.py tests/test_schema.py
git commit -m "feat(provenance): record adapter-reported backend (schema-required)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: `stage_publish` takes the real `predictions_dir`

**Files:**
- Modify: `engine/omnidocbench_rocm/stages.py` (`stage_publish` signature gains required `predictions_dir: Path`; passes it to `write_provenance` instead of `results_dir.parent`).
- Test: `tests/test_stages.py` (+2), `tests/test_contract_integration.py` (pass `predictions_dir`).

**Interfaces:**
- Consumes: `write_provenance(predictions_dir=...)` (already a param; now gets a real value).
- Produces: `stage_publish(*, ..., predictions_dir: Path, ...)` — **required kwarg** (no default). `requested_backend` is added in Task 5.

- [ ] **Step 1: Write the 2 failing tests + update the integration test**

In `tests/test_stages.py`, append:

```python
def _publish_inputs(tmp_path, engine="vllm"):
    rs = tmp_path / "_run_stats.json"
    rs.write_text(json.dumps({"schema_version": 1, "count": 3, "ok": 3, "fail": 0,
                              "fallback": 0, "limit_pages": None, "engine": engine,
                              "stats": []}))
    metric = tmp_path / "metric.json"
    metric.write_text(json.dumps({
        "text_block": {"page": {"Edit_dist": {"ALL": 0.1}}},
        "reading_order": {"page": {"Edit_dist": {"ALL": 0.1}}},
        "table": {"page": {"TEDS": {"ALL": 0.9}}},
        "display_formula": {"page": {"CDM": {"ALL": 0.9}},
                            "metric_debug": {"CDM": {"sample_count": 1, "exception_case_count": 0}}},
    }))
    results = tmp_path / "results"; results.mkdir()
    return rs, metric, results


def test_publish_records_real_predictions_dir(tmp_path):
    rs, metric, results = _publish_inputs(tmp_path)
    real_preds = tmp_path / "the_real_predictions"; real_preds.mkdir()
    out = stages.stage_publish(model_id="m", platform="linux-rocm", version="v16",
                               cdm=False, run_stats_path=rs, metric_result_path=metric,
                               results_dir=results, git_commit="c", engine_version="0.3.0",
                               adapter_command="python a.py", predictions_dir=real_preds,
                               dataset_revision="v1.6")
    prov = json.loads(Path(out["provenance"]).read_text())
    assert prov["prediction_dir"] == str(real_preds)


def test_publish_does_not_use_results_dir_parent_as_prediction_dir(tmp_path):
    rs, metric, results = _publish_inputs(tmp_path)
    real_preds = tmp_path / "the_real_predictions"; real_preds.mkdir()
    out = stages.stage_publish(model_id="m", platform="linux-rocm", version="v16",
                               cdm=False, run_stats_path=rs, metric_result_path=metric,
                               results_dir=results, git_commit="c", engine_version="0.3.0",
                               adapter_command="python a.py", predictions_dir=real_preds,
                               dataset_revision="v1.6")
    prov = json.loads(Path(out["provenance"]).read_text())
    assert prov["prediction_dir"] != str(results.parent)
    assert prov["prediction_dir"] == str(real_preds)
```

In `tests/test_contract_integration.py`, the `stage_publish(...)` call currently omits `predictions_dir`. Add `predictions_dir=preds,` to its kwargs (it already has `results_dir=results`), and add a backend assertion after the existing provenance assertions:

```python
    out = stages.stage_publish(
        model_id="fake-model", platform="linux-rocm", version="v16", cdm=False,
        run_stats_path=run_stats, metric_result_path=metric, results_dir=results,
        git_commit="abc123", engine_version="0.1.0",
        adapter_command="python fake_adapter.py", dataset_revision="v1.6",
        predictions_dir=preds,
    )
```

and at the end of that test:

```python
    assert prov_obj["backend"] == "smoke"   # fake_adapter writes engine="smoke"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_stages.py -k "predictions_dir" tests/test_contract_integration.py -v`
Expected: FAIL — `test_publish_records_real_predictions_dir` / `test_publish_does_not_use_results_dir_parent...` fail with `TypeError: stage_publish() missing 1 required keyword-only argument: 'predictions_dir'`; `test_contract_integration` fails the same way.

- [ ] **Step 3: Add required `predictions_dir` to `stage_publish`**

In `engine/omnidocbench_rocm/stages.py`, change the `stage_publish` signature to insert `predictions_dir: Path` after `adapter_command: str` (keeping all existing params/defaults), and change the `write_provenance(...)` call to pass `predictions_dir=predictions_dir`:

```python
def stage_publish(*, model_id: str, platform: str, version: str, cdm: bool,
                  run_stats_path: Path, metric_result_path: Path, results_dir: Path,
                  git_commit: str, engine_version: str, adapter_command: str,
                  predictions_dir: Path,
                  server_url: str = "", api_model_name: str = "",
                  scoring_config_path: str = "", dataset_manifest_path: str = "",
                  dataset_revision: str = "") -> dict:
    _assert_full_set(run_stats_path)
    save_name = f"{model_id}_{version}_quick_match{'_cdm' if cdm else ''}"
    summary_path = results_dir / f"{save_name}_run_summary.json"
    provenance_path = results_dir / f"{save_name}_provenance.json"
    au.write_run_summary(save_name=save_name, run_stats_path=run_stats_path,
                         metric_result_path=metric_result_path, destination=summary_path, cdm=cdm)
    au.write_provenance(
        destination=provenance_path, git_commit=git_commit, engine_version=engine_version,
        model_id=model_id, platform=platform, server_url=server_url,
        api_model_name=api_model_name, adapter_command=adapter_command,
        scoring_config_path=Path(scoring_config_path),
        dataset_manifest_path=Path(dataset_manifest_path),
        dataset_revision=dataset_revision, predictions_dir=predictions_dir,
        metric_result_paths=[metric_result_path], run_summary_paths=[summary_path],
        run_stats_path=run_stats_path)
    return {"run_summary": str(summary_path), "provenance": str(provenance_path)}
```

(The only changes vs. today: `predictions_dir: Path` is now a required kwarg, and `write_provenance(...)` gets `predictions_dir=predictions_dir` instead of `predictions_dir=results_dir.parent`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_stages.py tests/test_contract_integration.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/omnidocbench_rocm/stages.py tests/test_stages.py tests/test_contract_integration.py
git commit -m "fix(publish): record the REAL predictions_dir, not results_dir.parent

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: backend mismatch gate + `_assert_full_set` returns the dict

**Files:**
- Modify: `engine/omnidocbench_rocm/stages.py` (`_assert_full_set` returns the loaded dict; `stage_publish` gains `requested_backend` + the mismatch gate).
- Test: `tests/test_stages.py` (+4: the 3 backend tests + the `_assert_full_set` return).

**Interfaces:**
- Consumes: `write_provenance` (Task 3) emits `backend` from the same `run_stats` the gate reads.
- Produces: `stage_publish(*, ..., requested_backend: str = "")`. If truthy and `!= run_stats["engine"]`, raises `SystemExit` with an actionable message. `_assert_full_set(path) -> dict` (returns the loaded run_stats on success; still raises on `limit_pages is not None`).

- [ ] **Step 1: Write the 4 failing tests**

Append to `tests/test_stages.py`:

```python
def test_assert_full_set_returns_run_stats(tmp_path):
    rs = tmp_path / "_run_stats.json"
    rs.write_text(json.dumps({"schema_version": 1, "count": 3, "ok": 3, "fail": 0,
                              "fallback": 0, "limit_pages": None, "engine": "x", "stats": []}))
    loaded = stages._assert_full_set(rs)
    assert loaded["engine"] == "x"


def test_publish_uses_adapter_reported_backend(tmp_path):
    rs, metric, results = _publish_inputs(tmp_path, engine="pipeline")
    preds = tmp_path / "preds"; preds.mkdir()
    out = stages.stage_publish(model_id="m", platform="linux-rocm", version="v16",
                               cdm=False, run_stats_path=rs, metric_result_path=metric,
                               results_dir=results, git_commit="c", engine_version="0.3.0",
                               adapter_command="python a.py", predictions_dir=preds,
                               requested_backend="", dataset_revision="v1.6")
    prov = json.loads(Path(out["provenance"]).read_text())
    assert prov["backend"] == "pipeline"


def test_publish_rejects_requested_backend_mismatch(tmp_path):
    rs, metric, results = _publish_inputs(tmp_path, engine="pipeline")
    preds = tmp_path / "preds"; preds.mkdir()
    try:
        stages.stage_publish(model_id="m", platform="linux-rocm", version="v16",
                             cdm=False, run_stats_path=rs, metric_result_path=metric,
                             results_dir=results, git_commit="c", engine_version="0.3.0",
                             adapter_command="python a.py", predictions_dir=preds,
                             requested_backend="vlm-vllm", dataset_revision="v1.6")
        assert False, "should refuse mismatched backend"
    except SystemExit as e:
        msg = str(e)
        assert "vlm-vllm" in msg and "pipeline" in msg
        assert "Refusing to publish" in msg


def test_publish_allows_empty_requested_backend(tmp_path):
    rs, metric, results = _publish_inputs(tmp_path, engine="smoke")
    preds = tmp_path / "preds"; preds.mkdir()
    out = stages.stage_publish(model_id="m", platform="linux-rocm", version="v16",
                               cdm=False, run_stats_path=rs, metric_result_path=metric,
                               results_dir=results, git_commit="c", engine_version="0.3.0",
                               adapter_command="python a.py", predictions_dir=preds,
                               requested_backend="", dataset_revision="v1.6")
    prov = json.loads(Path(out["provenance"]).read_text())
    assert prov["backend"] == "smoke"   # recorded, no gate when nothing requested
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_stages.py -k "assert_full_set_returns or publish_uses_adapter or publish_rejects or publish_allows_empty" -v`
Expected: FAIL — `requested_backend` is not yet a kwarg (`TypeError`); `_assert_full_set` returns `None` (the `_returns_run_stats` test fails).

- [ ] **Step 3: Make `_assert_full_set` return the dict; add the gate to `stage_publish`**

In `engine/omnidocbench_rocm/stages.py`, change `_assert_full_set` to return the loaded dict:

```python
def _assert_full_set(run_stats_path: Path) -> dict:
    rs = json.loads(Path(run_stats_path).read_text(encoding="utf-8"))
    if rs.get("limit_pages") is not None:
        raise SystemExit(
            f"Refusing to publish official evidence from limited predictions "
            f"(limit_pages={rs['limit_pages']}). Run full unbounded inference first.")
    return rs
```

In `stage_publish`, add the `requested_backend` param (after `predictions_dir: Path`) and the gate at the top of the body:

```python
def stage_publish(*, model_id: str, platform: str, version: str, cdm: bool,
                  run_stats_path: Path, metric_result_path: Path, results_dir: Path,
                  git_commit: str, engine_version: str, adapter_command: str,
                  predictions_dir: Path, requested_backend: str = "",
                  server_url: str = "", api_model_name: str = "",
                  scoring_config_path: str = "", dataset_manifest_path: str = "",
                  dataset_revision: str = "") -> dict:
    run_stats = _assert_full_set(run_stats_path)
    actual_backend = run_stats.get("engine", "")
    if requested_backend and requested_backend != actual_backend:
        raise SystemExit(
            f"Refusing to publish: requested backend {requested_backend!r} "
            f"does not match adapter-reported engine {actual_backend!r}.")
    save_name = f"{model_id}_{version}_quick_match{'_cdm' if cdm else ''}"
    # ... (rest unchanged: summary_path, provenance_path, write_run_summary,
    #      write_provenance(..., predictions_dir=predictions_dir, ...), return)
```

(Replace the `_assert_full_set(run_stats_path)` line at the top of the body with the `run_stats = _assert_full_set(...)` + `actual_backend` + gate block above; leave everything below unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_stages.py -v`
Expected: PASS — including the existing `test_stage_publish_refuses_limited_subset` (it still hits the raise path; the return value isn't asserted there).

- [ ] **Step 5: Commit**

```bash
git add engine/omnidocbench_rocm/stages.py tests/test_stages.py
git commit -m "feat(publish): refuse backend mismatch; _assert_full_set returns dict

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: CLI `infer` + `publish` flags

**Files:**
- Modify: `engine/omnidocbench_rocm/cli.py` (add `_infer_config_from_args`; add flags to the `infer` and `publish` subparsers; wire the standalone `infer`/`publish` handlers).
- Test: `tests/test_cli.py` (+2).

**Interfaces:**
- Consumes: `stage_infer(config=...)` (Tasks 1–2), `stage_publish(predictions_dir=..., requested_backend=...)` (Tasks 4–5). `requested_backend` is **not** exposed on standalone `publish` (spec §3 adds `--backend` only to `infer`/`run`); standalone publish records the actual backend only.
- Produces: `_infer_config_from_args(a) -> dict` (reused by Task 7's `run`).

- [ ] **Step 1: Write the 2 failing tests**

Append to `tests/test_cli.py`:

```python
def test_cli_infer_forwards_config(tmp_path):
    with patch("omnidocbench_rocm.cli.stage_infer") as inf:
        rc = main(["infer", "--adapter", "a.py", "--img-dir", "i", "--out-dir", "o",
                   "--platform", "linux-rocm", "--backend", "vlm-vllm",
                   "--server-url", "http://x/v1", "--api-model-name", "m", "--skip-existing"])
        assert rc == 0
        cfg = inf.call_args.kwargs["config"]
        assert cfg["backend"] == "vlm-vllm"
        assert cfg["server_url"] == "http://x/v1"
        assert cfg["api_model_name"] == "m"
        assert cfg["skip_existing"] is True


def test_cli_publish_requires_predictions_dir():
    with pytest.raises(SystemExit) as exc:
        main(["publish", "--model-id", "m", "--platform", "linux-rocm",
              "--run-stats", "r.json", "--metric-result", "m.json",
              "--results-dir", "r", "--git-commit", "c",
              "--adapter-command", "x", "--dataset-revision", "v1.6"])
    assert exc.value.code == 2   # argparse missing-required-arg
```

(`test_cli.py` already imports `patch`, `pytest`, `main`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py::test_cli_infer_forwards_config tests/test_cli.py::test_cli_publish_requires_predictions_dir -v`
Expected: FAIL — `--backend`/`--server-url`/etc. unrecognized by `infer` (`SystemExit` from argparse); `--predictions-dir` not required by `publish` (so the publish call proceeds and does not raise).

- [ ] **Step 3: Add the helper + the subparser flags + handler wiring**

In `engine/omnidocbench_rocm/cli.py`, add this module-level helper (e.g. above `_orchestrate_run`):

```python
def _infer_config_from_args(a) -> dict:
    """One source of truth for the adapter config dict. Shared by `infer` and `run`.

    Empty strings / False are omitted downstream by _build_adapter_command.
    """
    return {"backend": a.backend,
            "server_url": a.server_url,
            "api_model_name": a.api_model_name,
            "skip_existing": bool(a.skip_existing)}
```

Extend the `infer` subparser (after `--platform`):

```python
    ip.add_argument("--backend", default="")
    ip.add_argument("--server-url", default="")
    ip.add_argument("--api-model-name", default="")
    ip.add_argument("--skip-existing", action="store_true")
```

Extend the `publish` subparser (add alongside the existing `--results-dir`):

```python
    pu.add_argument("--predictions-dir", required=True,
                    help="real predictions dir (where the .md files live)")
```

Change the standalone `infer` handler (in `main`) to build the config:

```python
    if a.cmd == "infer":
        stage_infer(adapter_path=Path(a.adapter), img_dir=Path(a.img_dir),
                    out_dir=Path(a.out_dir), platform=a.platform,
                    config=_infer_config_from_args(a))
        return 0
```

Change the standalone `publish` handler to pass the real predictions dir:

```python
    if a.cmd == "publish":
        stage_publish(
            model_id=a.model_id, platform=a.platform, version=a.version, cdm=a.cdm,
            run_stats_path=Path(a.run_stats), metric_result_path=Path(a.metric_result),
            results_dir=Path(a.results_dir), git_commit=a.git_commit,
            engine_version=omnidocbench_rocm.__version__,
            adapter_command=a.adapter_command, predictions_dir=Path(a.predictions_dir),
            server_url=a.server_url, api_model_name=a.api_model_name,
            scoring_config_path=a.scoring_config, dataset_manifest_path=a.dataset_manifest,
            dataset_revision=a.dataset_revision)
        return 0
```

(Standalone `publish` passes no `requested_backend` — defaults to `""`; the actual backend is still recorded.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS — all CLI tests green, including the pre-existing `test_cli_run_all_orchestrates_four_stages_in_order` (it patches the four stages with `**kw` lambdas; `--backend`/`--skip-existing`/`--predictions-dir` are not yet on `run` so the existing `run` invocation still parses — Task 7 adds them).

- [ ] **Step 5: Commit**

```bash
git add engine/omnidocbench_rocm/cli.py tests/test_cli.py
git commit -m "feat(cli): infer forwards config; publish requires --predictions-dir

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: CLI `run` threading (one config for infer + publish)

**Files:**
- Modify: `engine/omnidocbench_rocm/cli.py` (add `import shlex`, `import sys`; add `--backend`/`--skip-existing`/`--predictions-dir` to the `run` subparser; add `_resolve_predictions_dir`; rewrite `_orchestrate_run` to thread one config, derive paths from the resolved predictions dir (D6), derive `adapter_command` from the real argv (B3 override note)).
- Test: `tests/test_cli.py` (update the existing run-order test's mock to return `InferResult`; +4 new tests).

**Interfaces:**
- Consumes: `_infer_config_from_args` (Task 6), `InferResult` (Task 2), `stage_publish(predictions_dir=, requested_backend=, ...)` (Tasks 4–5), `_paths.predictions_dir`.
- Produces: `_orchestrate_run` threads the same `backend`/`server_url`/`api_model_name` into both `stage_infer` (config) and `stage_publish` (requested_backend / server_url / api_model_name); `adapter_command` defaults to `shlex.join(infer_result.adapter_argv)`.

- [ ] **Step 1: Update the existing run-order test mock + write the 4 new failing tests**

In `tests/test_cli.py`, update the `stage_infer` mock in `test_cli_run_all_orchestrates_four_stages_in_order` so it returns an `InferResult` (it currently returns `{"count": 0, "ok": 0}`). Add the import and change the side_effect:

```python
from omnidocbench_rocm.types import InferResult
```

```python
        inf.side_effect = lambda **kw: (
            call_order.append("infer")
            or InferResult(run_stats={"count": 0, "ok": 0},
                           adapter_argv=[sys.executable, "fake.py", "--backend", "x"]))
```

(`test_cli.py` already imports `sys`.) The order/count assertions stay.

Append the 4 new tests:

```python
def test_run_all_uses_same_backend_for_infer_and_publish(tmp_path):
    with patch("omnidocbench_rocm.cli.stage_download"), \
         patch("omnidocbench_rocm.cli.stage_infer") as inf, \
         patch("omnidocbench_rocm.cli.stage_score") as sc, \
         patch("omnidocbench_rocm.cli.stage_publish") as pub, \
         patch("omnidocbench_rocm.cli.get_backend"):
        inf.return_value = InferResult(run_stats={"count": 0, "ok": 0},
                                       adapter_argv=[sys.executable, "fake.py"])
        sc.return_value = tmp_path / "metric.json"
        rc = main(["run", "--stage", "all", "--platform", "linux-rocm",
                   "--version", "v16", "--revision", "2b161d0", "--adapter", "fake.py",
                   "--model-id", "m", "--git-commit", "c", "--results-dir", str(tmp_path),
                   "--backend", "vlm-vllm"])
        assert rc == 0
        assert inf.call_args.kwargs["config"]["backend"] == "vlm-vllm"
        assert pub.call_args.kwargs["requested_backend"] == "vlm-vllm"


def test_run_all_forwards_server_url_and_api_model_name(tmp_path):
    with patch("omnidocbench_rocm.cli.stage_download"), \
         patch("omnidocbench_rocm.cli.stage_infer") as inf, \
         patch("omnidocbench_rocm.cli.stage_score") as sc, \
         patch("omnidocbench_rocm.cli.stage_publish") as pub, \
         patch("omnidocbench_rocm.cli.get_backend"):
        inf.return_value = InferResult(run_stats={"count": 0, "ok": 0},
                                       adapter_argv=[sys.executable, "fake.py"])
        sc.return_value = tmp_path / "metric.json"
        rc = main(["run", "--stage", "all", "--platform", "linux-rocm",
                   "--version", "v16", "--revision", "2b161d0", "--adapter", "fake.py",
                   "--model-id", "m", "--git-commit", "c", "--results-dir", str(tmp_path),
                   "--server-url", "http://x/v1", "--api-model-name", "m"])
        assert rc == 0
        cfg = inf.call_args.kwargs["config"]
        assert cfg["server_url"] == "http://x/v1" and cfg["api_model_name"] == "m"
        kw = pub.call_args.kwargs
        assert kw["server_url"] == "http://x/v1" and kw["api_model_name"] == "m"


def test_run_all_passes_out_dir_to_publish(tmp_path):
    from omnidocbench_rocm._paths import predictions_dir
    with patch("omnidocbench_rocm.cli.stage_download"), \
         patch("omnidocbench_rocm.cli.stage_infer") as inf, \
         patch("omnidocbench_rocm.cli.stage_score") as sc, \
         patch("omnidocbench_rocm.cli.stage_publish") as pub, \
         patch("omnidocbench_rocm.cli.get_backend"):
        inf.return_value = InferResult(run_stats={"count": 0, "ok": 0},
                                       adapter_argv=[sys.executable, "fake.py"])
        sc.return_value = tmp_path / "metric.json"
        rc = main(["run", "--stage", "all", "--platform", "linux-rocm",
                   "--version", "v16", "--revision", "2b161d0", "--adapter", "fake.py",
                   "--model-id", "m", "--git-commit", "c", "--results-dir", str(tmp_path)])
        assert rc == 0
        assert pub.call_args.kwargs["predictions_dir"] == predictions_dir("m", "linux-rocm")


def test_run_all_adapter_command_override_note(tmp_path, capsys):
    with patch("omnidocbench_rocm.cli.stage_download"), \
         patch("omnidocbench_rocm.cli.stage_infer") as inf, \
         patch("omnidocbench_rocm.cli.stage_score") as sc, \
         patch("omnidocbench_rocm.cli.stage_publish"), \
         patch("omnidocbench_rocm.cli.get_backend"):
        inf.return_value = InferResult(run_stats={"count": 0, "ok": 0},
                                       adapter_argv=[sys.executable, "fake.py"])
        sc.return_value = tmp_path / "metric.json"
        rc = main(["run", "--stage", "all", "--platform", "linux-rocm",
                   "--version", "v16", "--revision", "2b161d0", "--adapter", "fake.py",
                   "--model-id", "m", "--git-commit", "c", "--results-dir", str(tmp_path),
                   "--adapter-command", "user-supplied-cmd"])
        assert rc == 0
        err = capsys.readouterr().err.lower()
        assert "overriding" in err or "user-supplied" in err
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL — `--backend`/`--skip-existing`/`--predictions-dir` not recognized on `run` (argparse `SystemExit`); the override-note test fails (no note printed yet).

- [ ] **Step 3: Wire `run` — imports, subparser flags, helpers, `_orchestrate_run`**

In `engine/omnidocbench_rocm/cli.py`, add imports at the top:

```python
import shlex
import sys
```

Add `--backend` / `--skip-existing` / `--predictions-dir` to the `run` subparser (alongside the existing `--server-url`/`--api-model-name`):

```python
    rn.add_argument("--backend", default="",
                    help="adapter backend to request (e.g. vlm-vllm, pipeline); empty = adapter default")
    rn.add_argument("--skip-existing", action="store_true",
                    help="infer only: skip pages whose .md already exists")
    rn.add_argument("--predictions-dir", default="",
                    help="predictions dir; defaults to predictions_dir(model_id, platform)")
```

Add the resolver helper next to `_infer_config_from_args`:

```python
def _resolve_predictions_dir(a, default: Path) -> Path:
    """Resolved predictions dir: explicit --predictions-dir, else the canonical default."""
    raw = getattr(a, "predictions_dir", "") or ""
    return Path(raw) if raw else default
```

Rewrite `_orchestrate_run` so it (a) derives paths from the resolved predictions dir (D6), (b) threads one config into infer, (c) derives `adapter_command` from the real argv with a B3 override note:

```python
def _orchestrate_run(a) -> int:
    """Run the four-stage pipeline (download -> infer -> score -> publish).

    For --stage all the stages execute in order, threading artifacts and ONE
    inference config into both infer and publish (so provenance records exactly
    what ran). Single-stage values dispatch to just that stage.
    """
    stage = a.stage
    img_dir = dataset_dir(a.version) / "images"
    default_preds = predictions_dir(a.model_id, a.platform)
    predictions = _resolve_predictions_dir(a, default_preds)
    run_stats_path = predictions / "_run_stats.json"
    infer_config = _infer_config_from_args(a)

    if stage == "download":
        stage_download(a.version, a.revision)
        return 0

    if stage == "infer":
        stage_infer(adapter_path=Path(a.adapter), img_dir=img_dir,
                    out_dir=predictions, platform=a.platform, config=infer_config)
        return 0

    if stage == "score":
        backend = get_backend(a.platform)
        stage_score(backend=backend, predictions_dir=predictions, version=a.version,
                    cdm=a.cdm, run_stats_path=run_stats_path,
                    scoring_config=(Path(a.scoring_config) if a.scoring_config else None),
                    dataset_dir=(Path(a.dataset_dir) if a.dataset_dir else None))
        return 0

    if stage == "publish":
        metric_path = predictions.parent / "metric_result.json"
        stage_publish(
            model_id=a.model_id, platform=a.platform, version=a.version, cdm=a.cdm,
            run_stats_path=run_stats_path, metric_result_path=metric_path,
            results_dir=Path(a.results_dir), git_commit=a.git_commit,
            engine_version=omnidocbench_rocm.__version__,
            adapter_command=a.adapter_command, predictions_dir=predictions,
            requested_backend=a.backend, server_url=a.server_url,
            api_model_name=a.api_model_name, scoring_config_path=a.scoring_config,
            dataset_manifest_path=a.dataset_manifest, dataset_revision=a.revision)
        return 0

    # stage == "all": full pipeline in order.
    stage_download(a.version, a.revision)
    infer_result = stage_infer(adapter_path=Path(a.adapter), img_dir=img_dir,
                               out_dir=predictions, platform=a.platform, config=infer_config)
    backend = get_backend(a.platform)
    metric_result_path = stage_score(
        backend=backend, predictions_dir=predictions, version=a.version, cdm=a.cdm,
        run_stats_path=run_stats_path,
        scoring_config=(Path(a.scoring_config) if a.scoring_config else None),
        dataset_dir=(Path(a.dataset_dir) if a.dataset_dir else None))
    if a.adapter_command:
        print("[run] note: using user-supplied --adapter-command; overriding "
              "the recorded adapter argv.", file=sys.stderr)
        adapter_command = a.adapter_command
    else:
        adapter_command = shlex.join(infer_result.adapter_argv)
    stage_publish(
        model_id=a.model_id, platform=a.platform, version=a.version, cdm=a.cdm,
        run_stats_path=run_stats_path, metric_result_path=metric_result_path,
        results_dir=Path(a.results_dir), git_commit=a.git_commit,
        engine_version=omnidocbench_rocm.__version__,
        adapter_command=adapter_command, predictions_dir=predictions,
        requested_backend=a.backend, server_url=a.server_url,
        api_model_name=a.api_model_name, scoring_config_path=a.scoring_config,
        dataset_manifest_path=a.dataset_manifest, dataset_revision=a.revision)
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS — all CLI tests green, including the updated `test_cli_run_all_orchestrates_four_stages_in_order`.

- [ ] **Step 5: Commit**

```bash
git add engine/omnidocbench_rocm/cli.py tests/test_cli.py
git commit -m "feat(cli): run threads one config into infer+publish; real adapter_command

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 8: template adapter `--skip-existing`

**Files:**
- Modify: `template/{{cookiecutter.repo_name}}/adapter/run_adapter.py` (accept `--skip-existing`; real skip; skipped pages recorded as exactly `"ok"` and counted).
- Test: `tests/test_template.py` (+1).

**Interfaces:**
- Produces: the rendered adapter accepts `--skip-existing`; skipped pages stay `ok` and are counted (full-set enforcement unaffected).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_template.py`:

```python
def test_rendered_template_skip_existing_counts_and_preserves(tmp_path):
    import json
    out = cookiecutter(str(TEMPLATE), no_input=True,
                       extra_context={"repo_name": "SkipModel-ROCm", "model_slug": "skipmodel"},
                       output_dir=str(tmp_path))
    adapter = Path(out) / "adapter" / "run_adapter.py"
    imgs = tmp_path / "imgs"; imgs.mkdir()
    (imgs / "a.png").write_bytes(b"x"); (imgs / "b.png").write_bytes(b"x")
    outdir = tmp_path / "out"; outdir.mkdir()
    (outdir / "a.md").write_text("SENTINEL", encoding="utf-8")  # pre-existing
    proc = subprocess.run([sys.executable, str(adapter), "--img-dir", str(imgs),
                           "--out-dir", str(outdir), "--platform", "linux-rocm",
                           "--backend", "smoke", "--skip-existing"])
    assert proc.returncode == 0
    assert (outdir / "a.md").read_text(encoding="utf-8") == "SENTINEL"  # not overwritten
    assert (outdir / "b.md").exists()                                  # new page written
    rs = json.loads((outdir / "_run_stats.json").read_text())
    assert rs["count"] == 2 and rs["ok"] == 2                          # both counted
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_template.py::test_rendered_template_skip_existing_counts_and_preserves -v`
Expected: FAIL — the rendered adapter exits 2 (unrecognized `--skip-existing`).

- [ ] **Step 3: Add `--skip-existing` to the template adapter**

In `template/{{cookiecutter.repo_name}}/adapter/run_adapter.py`:

In `run_adapter`, add a `skip_existing` flag read from the merged config and honor it in the loop. Replace the loop body so it reads:

```python
def run_adapter(img_dir: Path, out_dir: Path, *, platform: str, config: dict) -> dict:
    assert platform in PLATFORMS, f"unknown platform: {platform}"
    adapter_config = _load_adapter_config()
    cfg = {**adapter_config.as_dict(), **config}
    out_dir.mkdir(parents=True, exist_ok=True)
    imgs = sorted(p for p in Path(img_dir).iterdir() if p.suffix.lower() in IMG_EXT)
    stats: list[PageStatus] = []
    backend = cfg.get("backend", "smoke")
    skip_existing = bool(cfg.get("skip_existing"))
    for i in imgs:
        try:
            target = out_dir / f"{i.stem}.md"
            if skip_existing and target.exists():
                # Skipped pages are recorded as exactly "ok" (the ok-count is an
                # exact match on "ok") and still counted — never reduce the full set.
                stats.append(PageStatus(i.name, "ok", seconds=0.0, attempts=0))
                continue
            if backend == "smoke":
                md = f"# {i.stem}\n\n(smoke output — wire your model here)\n"
            else:
                md = _infer(i, platform, cfg)  # TODO-replace: your model's inference
            target.write_text(md, encoding="utf-8")
            stats.append(PageStatus(i.name, "ok", seconds=0.0, attempts=1))
        except Exception as e:  # per-page failure → record, continue, never raise
            stats.append(PageStatus(i.name, f"failed: {e}", error=str(e)))
    rs = RunSummary(len(imgs), sum(1 for s in stats if s.status == "ok"),
                    sum(1 for s in stats if s.status.startswith("failed")),
                    sum(1 for s in stats if s.status.startswith("fallback")),
                    cfg.get("limit_pages"), stats, engine=backend)
    rs.write(out_dir / "_run_stats.json")
    return rs.to_run_stats()
```

In the `__main__` block, add the flag and pass it into `config`:

```python
if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--img-dir", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--platform", required=True, choices=PLATFORMS)
    p.add_argument("--backend", default="smoke")
    p.add_argument("--server-url", default="")
    p.add_argument("--api-model-name", default="")
    p.add_argument("--skip-existing", action="store_true")
    a = p.parse_args()
    run_adapter(Path(a.img_dir), Path(a.out_dir), platform=a.platform,
                config={"backend": a.backend, "server_url": a.server_url,
                        "api_model_name": a.api_model_name, "skip_existing": a.skip_existing})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_template.py -v`
Expected: PASS — both template tests green (the pre-existing `test_rendered_template_smoke_backend_runs` is unaffected: it does not pass `--skip-existing`).

- [ ] **Step 5: Commit**

```bash
git add template/{{cookiecutter.repo_name}}/adapter/run_adapter.py tests/test_template.py
git commit -m "feat(template): adapter accepts --skip-existing (real skip, counted)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 9: CPU-only end-to-end smoke

**Files:**
- Create: `tests/test_smoke_config_pipeline.py` (2 tests: standalone infer+publish via the real CLI; `run --stage all` recording the real argv in provenance).

**Interfaces:**
- Consumes: the full CLI (Tasks 6–7), real `stage_infer` subprocess path, real `stage_publish`.

- [ ] **Step 1: Write the smoke tests**

Create `tests/test_smoke_config_pipeline.py`:

```python
"""CPU-only end-to-end smoke for the P0 config + provenance chain.

Drives the REAL CLI (in-process) against a fake adapter that echoes its argv,
writes .md, and writes _run_stats.json(engine=<backend>). Verifies the whole
chain: config forwarded to the adapter, and provenance records the real
prediction_dir / backend / server_url / api_model_name / adapter_command.
No GPU, no network, no OmniDocBench scoring.
"""
import json
import shlex
from pathlib import Path

from omnidocbench_rocm.cli import main

# Fake adapter: accepts the forwarded flags, echoes argv to _argv.json, writes
# one .md per image, writes _run_stats.json with engine=<--backend>.
FAKE_ADAPTER = '''
import argparse, json, sys
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument("--img-dir", required=True)
p.add_argument("--out-dir", required=True)
p.add_argument("--platform", required=True)
p.add_argument("--backend", default="smoke")
p.add_argument("--server-url", default="")
p.add_argument("--api-model-name", default="")
p.add_argument("--skip-existing", action="store_true")
a = p.parse_args()
out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
(out / "_argv.json").write_text(json.dumps(sys.argv[1:]))
imgs = sorted(q for q in Path(a.img_dir).iterdir() if q.suffix.lower() in {".png", ".jpg"})
for i in imgs:
    (out / f"{i.stem}.md").write_text("# " + i.stem + "\\n", encoding="utf-8")
json.dump({"schema_version": 1, "count": len(imgs), "ok": len(imgs), "fail": 0,
           "fallback": 0, "limit_pages": None, "engine": a.backend, "stats": []},
          open(out / "_run_stats.json", "w"))
'''

METRIC = {
    "text_block": {"page": {"Edit_dist": {"ALL": 0.1}}},
    "reading_order": {"page": {"Edit_dist": {"ALL": 0.1}}},
    "table": {"page": {"TEDS": {"ALL": 0.9}}},
    "display_formula": {"page": {"CDM": {"ALL": 0.9}},
                        "metric_debug": {"CDM": {"sample_count": 1, "exception_case_count": 0}}},
}


def test_smoke_infer_then_publish_records_real_config(tmp_path):
    adapter = tmp_path / "fake_adapter.py"; adapter.write_text(FAKE_ADAPTER)
    imgs = tmp_path / "imgs"; imgs.mkdir()
    (imgs / "a.png").write_bytes(b"x")
    preds = tmp_path / "preds"
    metric = tmp_path / "metric.json"; metric.write_text(json.dumps(METRIC))
    results = tmp_path / "results"; results.mkdir()

    rc = main(["infer", "--adapter", str(adapter), "--img-dir", str(imgs),
               "--out-dir", str(preds), "--platform", "linux-rocm",
               "--backend", "vlm-vllm", "--server-url", "http://127.0.0.1:8265/v1",
               "--api-model-name", "mineru-pro", "--skip-existing"])
    assert rc == 0
    argv = json.loads((preds / "_argv.json").read_text())
    assert "vlm-vllm" in argv and "http://127.0.0.1:8265/v1" in argv
    assert "mineru-pro" in argv and "--skip-existing" in argv

    rc = main(["publish", "--model-id", "mineru2.5", "--platform", "linux-rocm",
               "--version", "v16", "--run-stats", str(preds / "_run_stats.json"),
               "--metric-result", str(metric), "--results-dir", str(results),
               "--git-commit", "abc", "--adapter-command", "python fake_adapter.py",
               "--dataset-revision", "2b161d0", "--predictions-dir", str(preds)])
    assert rc == 0
    prov = json.loads(next(results.glob("*_provenance.json")).read_text())
    assert prov["prediction_dir"] == str(preds)
    assert prov["backend"] == "vlm-vllm"
    assert prov["vlm_server_url"] == "http://127.0.0.1:8265/v1"
    assert prov["api_model_name"] == "mineru-pro"


def test_smoke_run_all_records_real_adapter_command(tmp_path, monkeypatch):
    adapter = tmp_path / "fake_adapter.py"; adapter.write_text(FAKE_ADAPTER)
    data_root = tmp_path / "data"
    monkeypatch.setenv("OMNIDOCBENCH_ROCM_DATA", str(data_root))
    # dataset_dir(v16)/images must exist for stage_infer's img_dir
    (data_root / "datasets" / "v16" / "images").mkdir(parents=True)
    (data_root / "datasets" / "v16" / "images" / "a.png").write_bytes(b"x")
    results = tmp_path / "results"; results.mkdir()
    metric = tmp_path / "metric.json"; metric.write_text(json.dumps(METRIC))

    # Mock the network/dataset + scoring stages; let infer + publish run for real.
    import omnidocbench_rocm.cli as cli
    monkeypatch.setattr(cli, "stage_download", lambda *a, **k: None)
    monkeypatch.setattr(cli, "stage_score", lambda **k: metric)
    monkeypatch.setattr(cli, "get_backend", lambda *a, **k: None)

    rc = main(["run", "--stage", "all", "--platform", "linux-rocm", "--version", "v16",
               "--revision", "2b161d0", "--adapter", str(adapter), "--model-id", "m",
               "--git-commit", "abc", "--results-dir", str(results), "--backend", "vlm-vllm"])
    assert rc == 0
    preds_dir = data_root / "predictions" / "m" / "linux-rocm"
    argv = json.loads((preds_dir / "_argv.json").read_text())
    prov = json.loads(next(results.glob("*_provenance.json")).read_text())
    assert prov["adapter_command"] == shlex.join(argv)
    assert prov["backend"] == "vlm-vllm"
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/test_smoke_config_pipeline.py -v`
Expected: PASS (both). If a test fails, fix the wiring — do not weaken the assertions.

- [ ] **Step 3: Commit**

```bash
git add tests/test_smoke_config_pipeline.py
git commit -m "test: CPU e2e smoke for config + provenance chain

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 10: docs sync

**Files:**
- Modify: `contracts/adapter.md`, `docs/architecture.md`, `docs/contribute-a-model.md`, `docs/onboarding-runbook.md`, `README.md`, `template/{{cookiecutter.repo_name}}/Makefile`.

No tests; verify `python scripts/check_brand.py` stays clean afterward.

- [ ] **Step 1: `contracts/adapter.md` — document `--skip-existing` and the backend source**

In §1 "CLI form", update the sentence listing forwarded flags to include `--skip-existing`:

```markdown
(`python adapter/run_adapter.py --img-dir ... --out-dir ... --platform ...`),
so `run_adapter.py` must also be runnable as a script with an `argparse`
`__main__` block (the template ships one). The `--platform` flag is required;
`--backend`, `--server-url`, `--api-model-name` populate the `config` dict, and
`--skip-existing` (optional) tells the adapter to skip pages whose `.md` already
exists (skipped pages are recorded as `ok` and still counted — never reduce the
full set).
```

Add a short note under §3 (`RunSummary` and `_run_stats.json`) stating the engine records `provenance.backend := _run_stats.json["engine"]` (adapter-reported), and refuses to publish when a requested `--backend` disagrees with it.

- [ ] **Step 2: `docs/architecture.md` — provenance section**

In the "Config -> save_name -> result mapping" section (or a new short paragraph under the engine-stages table), state: provenance now records the **real** `prediction_dir`, the **adapter-reported** `backend` (`_run_stats.json["engine"]`), and the **actual** `adapter_command` (`shlex.join` of the executed argv); `run --stage all` threads one inference config into both infer and publish, and `stage_publish` refuses to publish when a requested backend does not match the adapter-reported engine.

- [ ] **Step 3: `docs/onboarding-runbook.md` — Step 5 publish requires `--predictions-dir`; add a `run --stage all --backend` example**

In Step 5, add `--predictions-dir predictions/<model>` to the `omnidocbench-rocm publish` command (it is now required) and note the migration. Add a "or, in one shot" block showing the `run --stage all --backend vlm-vllm --server-url ... --api-model-name ...` example from the spec. (Do **not** edit the two `omnidocbench-rocm-repro:0.2.0` docker tags here — Task 11 bumps them to `:0.3.0`.)

- [ ] **Step 4: `docs/contribute-a-model.md` + `README.md` — examples with backend/server flags**

In contribute-a-model.md Step 4/6, mention the adapter receives `--backend`/`--server-url`/`--api-model-name`/`--skip-existing` from the engine. In README.md's quick-start/eval section, show a one-line `omnidocbench-rocm run --stage all --backend ... --server-url ... --api-model-name ...` example (MinerU2.5-class VLM, illustrative only — do not reference MinerU-ROCm specifics).

- [ ] **Step 5: `template/{{cookiecutter.repo_name}}/Makefile` — eval targets show the new flags**

Add make variables (defaults empty → behavior unchanged when unset) and insert the optional `$(if ...)` flags **before** the `--results-dir` line. The recipe must still **end with** `linux-rocm` (the `test_makefile_targets.py` parser asserts `r.rstrip().endswith("linux-rocm")` / `"windows-hip")`, satisfied today by the `--results-dir .../linux-rocm` line — keep that line last).

```makefile
BACKEND       ?=
SERVER_URL    ?=
API_MODEL_NAME ?=

eval-linux:
	omnidocbench-rocm run --stage all --platform linux-rocm --version $(VERSION) --revision $(REVISION) \
	  --adapter adapter/run_adapter.py --model-id $(MODEL_ID) \
	  $(if $(BACKEND),--backend $(BACKEND)) \
	  $(if $(SERVER_URL),--server-url $(SERVER_URL)) \
	  $(if $(API_MODEL_NAME),--api-model-name $(API_MODEL_NAME)) \
	  --git-commit $$(git rev-parse HEAD) --results-dir results/omnidocbench/$(VERSION)/linux-rocm
```

(Mirror the same structure in `eval-windows` with `--platform windows-hip` and `--results-dir results/omnidocbench/$(VERSION)/windows-hip` last. Verify with `python -m pytest tests/test_makefile_targets.py -v` — both `--platform <plat>` membership and `endswith` must hold.)

- [ ] **Step 6: Verify brand gate + makefile test; commit**

Run: `python scripts/check_brand.py && python -m pytest tests/test_makefile_targets.py -v`
Expected: brand clean; makefile test green (adjust flag placement per Step 5 note if it breaks the recipe-end assertion).

```bash
git add contracts/adapter.md docs/architecture.md docs/contribute-a-model.md docs/onboarding-runbook.md README.md template/{{cookiecutter.repo_name}}/Makefile
git commit -m "docs: backend/server config forwarding + real prediction_dir + backend gate

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 11: version bump 0.2.0 → 0.3.0 + CHANGELOG + final gates

**Files:**
- Modify: `pyproject.toml` (`version`), `engine/omnidocbench_rocm/__init__.py` (`__version__`), `CHANGELOG.md` (new `## 0.3.0` section), `docs/onboarding-runbook.md` (the two `:0.2.0` docker tags → `:0.3.0`).

- [ ] **Step 1: Bump version**

`pyproject.toml`: `version = "0.3.0"`.
`engine/omnidocbench_rocm/__init__.py`: `__version__ = "0.3.0"`.

- [ ] **Step 2: Ripple the docker tags**

In `docs/onboarding-runbook.md`, change the two `omnidocbench-rocm-repro:0.2.0` occurrences (in the Step 7 `docker build -t` and `docker run` examples) to `:0.3.0`. Leave ADR/audit historical mentions of `0.2.0` untouched.

- [ ] **Step 3: CHANGELOG**

Add a `## 0.3.0` section at the top of `CHANGELOG.md` (above the existing `## Unreleased` or fold the unreleased items in). Document:

- **Breaking:** standalone `publish` now requires `--predictions-dir` (the real predictions dir). Migration: add `--predictions-dir <dir>`.
- `stage_infer` now forwards `--backend`/`--server-url`/`--api-model-name`/`--skip-existing` to the adapter (the contract always promised this; the engine now honors it).
- `run --stage all` threads one inference config into both infer and publish.
- `provenance.json` gains `backend` (schema-required), sourced from the adapter-reported `_run_stats.json["engine"]`; `stage_publish` refuses to publish when a requested `--backend` does not match it.
- `provenance.prediction_dir` is now the real predictions dir (was wrongly `results_dir.parent`).
- `provenance.adapter_command` is now the actual executed argv (`shlex.join`), overridable via `--adapter-command` (with a stderr note).
- The template adapter accepts `--skip-existing`.

- [ ] **Step 4: Run ALL quality gates**

```bash
python -m pytest -q
python scripts/check_brand.py
python scripts/validate_registry.py
python -m build
```
Expected: all pass; `python -m build` produces `dist/omnidocbench_rocm-0.3.0-py3-none-any.whl`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml engine/omnidocbench_rocm/__init__.py CHANGELOG.md docs/onboarding-runbook.md
git commit -m "chore: bump 0.2.0 -> 0.3.0 (breaking: publish requires --predictions-dir)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review (run after writing — done)

**1. Spec coverage:**
- §3.1 `infer` flags → Task 6. ✓
- §3.2 `run` flags + one-config → Task 7. ✓
- §4 `_build_adapter_command` + stage_infer → Tasks 1–2. ✓
- §5 real `predictions_dir` (split rule D5) → Tasks 4 (stage), 6 (publish CLI), 7 (run auto-derive). ✓
- §6.1 backend from `_run_stats.json["engine"]` + mismatch gate → Tasks 3, 5. ✓
- §6.2 server_url/api_model_name into infer AND publish → Task 7 (run), Task 6 (standalone infer/publish). ✓
- §6.3 `adapter_command` from real argv → Task 7 (+ smoke Task 9). ✓
- §6.4 schema `backend` required → Task 3. ✓
- §7 test list → all 19 named tests mapped across Tasks 1–9. ✓
- §8 docs → Task 10. ✓
- §11 gates → Task 11. ✓
- AD7 template `--skip-existing` → Task 8. ✓
- AD8 version 0.3.0 + CHANGELOG + docker ripple → Task 11. ✓
- D6 path derivation → Task 7 (`_orchestrate_run` derives from resolved `predictions`). ✓
- B3 override note → Task 7. ✓

**2. Placeholder scan:** none — every code step shows complete code; every test is fully written.

**3. Type consistency:** `InferResult(run_stats: dict, adapter_argv: list[str])` is identical wherever it appears (types.py, stages.py, test_stages.py, test_cli.py, test_smoke). `_build_adapter_command`, `_infer_config_from_args`, `_resolve_predictions_dir`, `stage_publish(predictions_dir, requested_backend)`, `stage_infer(...)->InferResult` signatures match across tasks. The provenance JSON key is `prediction_dir` / `vlm_server_url` / `backend` (schema names); the Python params are `predictions_dir` / `server_url` — consistent with the spec's note.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-21-p0-platform-provenance.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
