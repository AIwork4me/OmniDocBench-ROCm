# Design: P0 — fix the platform's adapter-config + provenance chain

- **Date:** 2026-07-21
- **Status:** Approved (design) — pending spec review, then implementation plan
- **Branch:** `feat/p0-platform-provenance`
- **Repo:** `OmniDocBench-ROCm` (platform repo; `github.com/AIwork4me/OmniDocBench-ROCm`)
- **Approach:** Platform-repo work only. Do **not** touch MinerU-ROCm, the registry, committed results, or badges.

---

## 1. North star (why this spec exists)

The platform must carry a user's inference configuration — **backend, server
URL, API model name, predictions directory** — truthfully and consistently
across the whole chain:

```
CLI flags → stage_infer → adapter subprocess → _run_stats.json → stage_publish → provenance.json
```

Today that chain is broken in three places: the engine never forwards inference
config to the adapter; provenance records a **wrong** predictions directory; and
the service config in provenance is decoupled from what actually ran. This makes
the platform unable to reliably support multi-backend model repos (e.g.
MinerU-ROCm with a VLM-server backend vs a local pipeline backend). P0 fixes the
platform so a follow-on can connect a model. **No model is connected in P0.**

The bar is a top-tier open-source infra project (cf. vLLM, ONNX Runtime):
provenance is an **evidence chain**, never a self-attested guess; the contract
doc and the implementation must not diverge; and every CLI knob flows end-to-end
or is refused.

---

## 2. What's broken today (verified by reading the code)

| # | Problem | Evidence |
|---|---|---|
| 1 | `run` accepts `--server-url` / `--api-model-name` but they reach only `stage_publish` | `cli.py:154-155` → `cli.py:66,88-89` |
| 2 | `_orchestrate_run()` calls `stage_infer(..., config={})`; standalone `infer` too | `cli.py:47,75-76,173` |
| 3 | `stage_infer()` ignores `config` — fixed 7-element argv (`--img-dir/--out-dir/--platform` only) | `stages.py:38-40` |
| 4 | `stage_publish()` writes `predictions_dir=results_dir.parent` — the *publish-evidence* dir, not where `.md` live | `stages.py:85` |
| 5 | provenance service config is publish-only, never tied to what the adapter ran | `server_url`/`api_model_name` flow only into `stage_publish` |

**Three sharpening findings:**

1. **The contract already says the right thing.** `contracts/adapter.md` §1
   documents that the engine forwards `--backend/--server-url/--api-model-name`
   and that `_run_stats.json["engine"]` *is* the backend. The **template
   adapter already accepts** those three flags (`run_adapter.py:69-71`) and
   writes `engine=cfg["backend"]`. So this is closing an
   *implementation-vs-contract* gap, not changing the contract. The template
   does **not** accept `--skip-existing`.
2. **`stage_infer`'s return value is discarded** in both `run --stage all` and
   standalone `infer` (score/publish re-read `_run_stats.json` from disk via the
   path). Surfacing the real argv back to `_orchestrate_run` is non-disruptive.
3. **The schema already has an optional `backend`** on provenance
   (`artifact-schema.json:54`) — never written. And
   `predictions_dir(model_id, platform)` already gives the real predictions dir
   for `run --stage all`. **No `provenance.json` is committed anywhere in the
   repo** (grep-verified) → making `backend` schema-required is safe.

Baseline: `pytest -q` → 53 passed; clean working tree on `main`.

---

## 3. Goals / non-goals

### Goals (first-class deliverables)

1. `stage_infer` forwards a real config (`backend/server_url/api_model_name/
   skip_existing`) to the adapter subprocess, built by a pure, unit-tested
   command-builder; no `shell=True`.
2. Provenance records the **real** predictions directory, sourced explicitly.
3. Provenance records the **adapter-reported** backend (`_run_stats.json["engine"]`)
   and **refuses to publish** when a requested backend disagrees with it.
4. `run --stage all` uses **one** config for both infer and publish
   (server_url/api_model_name/backend consistent end-to-end).
5. `adapter_command` in provenance is the **actual executed argv**
   (`shlex.join`), not a hand-typed guess.
6. Full test coverage (no GPU/network) + CPU-only end-to-end smoke.
7. Docs + contract + template stay aligned with the implementation.

### Non-goals (explicitly out of scope)

- Do **not** modify MinerU-ROCm.
- Do **not** touch `hub/registry.yaml` (model state/scores), move MinerU
  history, rerun the 1651-page eval, or change badge tiers.
- Do **not** implement Windows-HIP, refactor the whole CLI, or introduce a new
  CLI framework (Typer/Click).
- Do **not** change the filesystem-decoupled adapter principle or import model
  deps into the engine.
- Do **not** fix unrelated bugs (record them as follow-ups).

---

## 4. Strategic framing (locked in)

| # | Decision | Choice |
|---|---|---|
| D1 | `stage_infer` return type | New `InferResult` dataclass (`run_stats: dict`, `adapter_argv: list[str]`) in `types.py` |
| D2 | `backend` source of truth | `write_provenance` derives `backend` from the `_run_stats.json["engine"]` it already loads; the requested-vs-actual mismatch gate lives in `stage_publish` |
| D3 | `--skip-existing` scope | Add to the **template adapter** (real skip, counts skipped as ok) **and** document in `contracts/adapter.md` — keeps contract/impl aligned |
| D4 | schema `backend` | **required** in `contracts/artifact-schema.json` (safe — no committed provenance) |
| D5 | `--predictions-dir` | **required** on standalone `publish`; **auto-derive** `predictions_dir(model_id, platform)` on `run` (all stages) with optional override |
| D6 | `run` path derivation | derive `run_stats_path` + `metric_result_path` from the **resolved** predictions dir, not a separately auto-computed `out_dir` |
| B1 | version | bump **0.2.0 → 0.3.0** (breaking CLI change); ripple-edit the 2 docker-tag lines in `onboarding-runbook.md`; ADR/audit mentions of `0.2.0` are historical → untouched |
| B2 | exceptions | keep `SystemExit` (matches existing convention); typed exceptions are a follow-up |
| B3 | `--adapter-command` override | on `run`, emit a one-line stderr note when the user overrides the recorded-actual |

**Trust model (stated plainly in docs):** `provenance.backend` is
**adapter-self-reported** (`_run_stats.json["engine"]`), not independently
verified by the engine — the same trust model as `limit_pages`. The mismatch
gate catches *unintentional* config drift, not a lying adapter.

---

## 5. Architecture decisions

### AD1 — `_build_adapter_command`: pure command builder

New pure function in `stages.py` (unit-tested in isolation):

```python
def _build_adapter_command(*, adapter_path: Path, img_dir: Path, out_dir: Path,
                           platform: str, config: dict) -> list[str]:
    cmd = [sys.executable, str(adapter_path), "--img-dir", str(img_dir),
           "--out-dir", str(out_dir), "--platform", platform]
    if config.get("backend"):           cmd += ["--backend", str(config["backend"])]
    if config.get("server_url"):        cmd += ["--server-url", str(config["server_url"])]
    if config.get("api_model_name"):    cmd += ["--api-model-name", str(config["api_model_name"])]
    if config.get("skip_existing"):     cmd += ["--skip-existing"]
    return cmd
```

Rules: no shell string concatenation, no `shell=True`; empty/`None`/`False`
omit the flag (truthy check); unknown config keys ignored; paths/URLs/model
names passed as separate argv elements → spaces safe by construction.

### AD2 — `stage_infer` returns `InferResult` (carries the real argv)

```python
# types.py — new
@dataclass
class InferResult:
    run_stats: dict
    adapter_argv: list[str]

# stages.py
def stage_infer(*, adapter_path, img_dir, out_dir, platform, config) -> InferResult:
    cmd = _build_adapter_command(adapter_path=adapter_path, img_dir=img_dir,
                                 out_dir=out_dir, platform=platform, config=config)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"adapter failed (exit {proc.returncode}):\n{proc.stderr}")
    rs_path = Path(out_dir) / "_run_stats.json"
    if not rs_path.exists():
        raise SystemExit(f"adapter wrote no _run_stats.json: {rs_path}")
    return InferResult(run_stats=json.loads(rs_path.read_text(encoding="utf-8")),
                       adapter_argv=cmd)
```

`adapter_argv[0]` is the engine's `sys.executable` (env-specific absolute path).
`shlex.join(adapter_argv)` is the provenance `adapter_command` —
reproducible-by-inspection, POSIX-quoted, not `cmd.exe`-pasteable (documented).

### AD3 — real `predictions_dir` (D5 split rule + D6 path derivation)

- **standalone `publish`**: `--predictions-dir` is `required=True` (argparse).
- **`run`** (all/infer/score/publish): `--predictions-dir` optional, defaults to
  `predictions_dir(model_id, platform)`, override allowed.
- `stage_publish(predictions_dir: Path, ...)` is a **required kwarg** (no
  default) → forces every internal caller to pass a real dir.
- In `_orchestrate_run`, once `predictions_dir` is resolved, derive
  `run_stats_path = predictions_dir / "_run_stats.json"` and
  `metric_result_path = predictions_dir.parent / "metric_result.json"` from it
  (D6 — prevents predictions_dir and run_stats_path diverging on an override).

### AD4 — backend source-of-truth + mismatch gate (D2)

`write_provenance` derives `backend` from the run_stats it already loads:

```python
provenance = {
    ...,
    "backend": run_stats.get("engine", ""),   # adapter-reported
    ...,
}
```

The mismatch gate lives in `stage_publish` (which has the *requested* backend):

```python
def stage_publish(*, ..., predictions_dir: Path, requested_backend: str = "", ...):
    run_stats = _assert_full_set(run_stats_path)   # now RETURNS the loaded dict
    actual_backend = run_stats.get("engine", "")
    if requested_backend and requested_backend != actual_backend:
        raise SystemExit(
            f"Refusing to publish: requested backend {requested_backend!r} "
            f"does not match adapter-reported engine {actual_backend!r}.")
    ...
```

Semantics: the gate fires **iff the user asserted `--backend`** (truthy). Empty
requested → no gate, just record. `requested=""`, actual="" → records `""`
honestly. Mismatch (including empty-actual-when-requested) → hard refuse.
`requested_backend` is threaded only from `run` (where `--backend` lives);
standalone `publish` has no `--backend` (records actual only).

### AD5 — provenance fields

| Field | Source |
|---|---|
| `backend` | `run_stats["engine"]` (adapter-reported); **schema-required** (D4) |
| `vlm_server_url` | the same `server_url` passed to infer **and** publish (single source) |
| `api_model_name` | same — passed to infer **and** publish |
| `adapter_command` | `a.adapter_command or shlex.join(infer_result.adapter_argv)` on `run`; user-supplied (required) on standalone `publish` |
| `prediction_dir` | the resolved real predictions dir (AD3) |

Schema field names are **unchanged** (`vlm_server_url`, `prediction_dir`
singular) — no rename migration. Internal param names use `predictions_dir`
(matches `_paths.predictions_dir`); the JSON key stays `prediction_dir`.

server_url/api_model_name consistency is **guaranteed by single-source
construction** (one config dict feeds both infer and publish), not runtime-
verified against adapter behavior (the adapter does not report them).

### AD6 — CLI surface

```python
# infer — add:
ip.add_argument("--backend", default="")
ip.add_argument("--server-url", default="")
ip.add_argument("--api-model-name", default="")
ip.add_argument("--skip-existing", action="store_true")

# run — add:
rn.add_argument("--backend", default="")
rn.add_argument("--skip-existing", action="store_true")
rn.add_argument("--predictions-dir", default="",
                help="predictions dir; defaults to predictions_dir(model_id, platform)")

# publish — add:
pu.add_argument("--predictions-dir", required=True)
```

`run` already has `--server-url` / `--api-model-name`; these now feed **both**
the infer config and publish. A single helper builds the config once:

```python
def _infer_config_from_args(a) -> dict:
    return {"backend": a.backend, "server_url": a.server_url,
            "api_model_name": a.api_model_name, "skip_existing": bool(a.skip_existing)}

def _resolve_predictions_dir(a, default: Path) -> Path:
    return Path(a.predictions_dir) if getattr(a, "predictions_dir", "") else default
```

`_orchestrate_run` threads: `stage_infer(config=_infer_config_from_args(a))`;
`stage_publish(predictions_dir=<resolved>, requested_backend=a.backend,
adapter_command=<resolved>, server_url=a.server_url, api_model_name=...)`.
For `--stage all`, `adapter_command = a.adapter_command or shlex.join(infer_result.adapter_argv)`;
if the user passed `--adapter-command`, emit the B3 override note to stderr.

### AD7 — template `--skip-existing` (D3)

- `template/.../adapter/run_adapter.py`: add `--skip-existing` (store_true);
  in the loop, `if skip_existing and (out_dir/f"{stem}.md").exists():` record a
  `PageStatus` with status **exactly `"ok"`** (the template's ok-count is an
  *exact* match on `status == "ok"` — `run_adapter.py:52` — so `"ok: skipped"`
  would silently undercount ok and break `count == ok+fail+fallback`),
  `seconds=0.0`, `attempts=0`, and **count it** — never omit, so
  `count`/`limit_pages is null` full-set enforcement still holds. Pass
  `skip_existing` into the `config` dict.
- `contracts/adapter.md` §1 CLI form: list `--skip-existing` as an optional
  forwarded flag and note "skipped pages are recorded as `ok` and still counted;
  never reduce the full set."

### AD8 — version bump 0.2.0 → 0.3.0 + CHANGELOG (B1)

- `pyproject.toml`: `version = "0.3.0"`.
- `engine/omnidocbench_rocm/__init__.py`: `__version__ = "0.3.0"`.
- `docs/onboarding-runbook.md`: the 2 `omnidocbench-rocm-repro:0.2.0` docker
  tags → `:0.3.0` (lines ~263, ~280).
- ADR/audit mentions of `0.2.0` are **historical** → untouched.
- `CHANGELOG.md`: new `## 0.3.0` section (move/extend the `Unreleased` content)
  documenting: backend/server/api config now forwarded to the adapter;
  `run --stage all` uses one config for infer+publish; standalone `publish`
  now **requires** `--predictions-dir` (the one breaking change, with one-line
  migration); provenance gains `backend` (schema-required, adapter-reported) +
  the mismatch gate; `adapter_command` now records the real argv.

---

## 6. Data flow (the chain P0 guarantees)

```
CLI  --backend / --server-url / --api-model-name / --skip-existing
 │
 └─► _infer_config_from_args(a)            (ONE dict)
       │
       ├─► stage_infer(config=…) ─► _build_adapter_command ─► subprocess (no shell=True)
       │        │                       │
       │        │                       └─► InferResult.adapter_argv   (the real command)
       │        │
       │        └─► _run_stats.json["engine"]                          (adapter-reported backend)
       │
       └─► stage_publish(predictions_dir=<resolved>, requested_backend=a.backend,
                        server_url=…, api_model_name=…,
                        adapter_command = a.adapter_command or shlex.join(adapter_argv))
              │
              ├─► mismatch gate:  requested_backend  vs  run_stats["engine"]   (hard refuse on drift)
              │
              └─► write_provenance(predictions_dir=real, backend=run_stats["engine"],
                                    vlm_server_url=…, api_model_name=…,
                                    adapter_command=<real argv>)  ─► provenance.json
```

backend / server_url / api_model_name / prediction_dir are **consistent, real,
and verified** end to end.

---

## 7. File manifest

**Code (4)**
- `engine/omnidocbench_rocm/types.py` — add `InferResult`.
- `engine/omnidocbench_rocm/stages.py` — `_build_adapter_command`;
  `stage_infer`→`InferResult` + stderr in error; `_assert_full_set` returns the
  dict; `stage_publish` gains required `predictions_dir` + `requested_backend` +
  mismatch gate + passes real `predictions_dir` to `write_provenance`.
- `engine/omnidocbench_rocm/artifact_utils.py` — `write_provenance` emits
  `backend = run_stats["engine"]`.
- `engine/omnidocbench_rocm/cli.py` — `infer`/`run`/`publish` args;
  `_orchestrate_run` threading; `_infer_config_from_args`, `_resolve_predictions_dir`;
  B3 override note.

**Contracts/docs (8)**
- `contracts/adapter.md` — `--skip-existing` in CLI form; backend provenance source.
- `contracts/artifact-schema.json` — `backend` → **required** in `provenance`.
- `docs/architecture.md` — provenance: backend source, real prediction_dir, gate.
- `docs/contribute-a-model.md` — infer/publish examples with backend/server flags.
- `docs/onboarding-runbook.md` — Step 5 standalone `publish` requires
  `--predictions-dir`; `run --stage all` example with `--backend`; docker tags → 0.3.0.
- `README.md` — quick example with `--backend`.
- `template/{{cookiecutter.repo_name}}/Makefile` — eval targets show
  `--backend`/`--server-url`/`--api-model-name`/`--skip-existing` via vars.
- `template/{{cookiecutter.repo_name}}/adapter/run_adapter.py` — accept
  `--skip-existing` (AD7).

**Versioning (3)** — `pyproject.toml`, `engine/omnidocbench_rocm/__init__.py`,
`CHANGELOG.md` (AD8).

**Tests (5)**
- `tests/test_stages.py` — 7 command-build + 3 stage_infer + 3 prediction_dir + 3 backend-consistency.
- `tests/test_cli.py` (extend) or new `tests/test_run_config.py` — 2 run-threading.
- `tests/test_schema.py` / `tests/test_artifact_utils.py` — provenance backend
  (schema-required + emitted).
- `tests/test_contract_integration.py` — pass `predictions_dir`; assert `backend`.
- new `tests/test_smoke_config_pipeline.py` — CPU e2e smoke.

---

## 8. Test manifest (maps task §7)

**Command builder** (`test_stages.py`)
- `test_build_adapter_command_minimal`
- `test_build_adapter_command_forwards_backend`
- `test_build_adapter_command_forwards_server_url`
- `test_build_adapter_command_forwards_api_model_name`
- `test_build_adapter_command_forwards_skip_existing`
- `test_build_adapter_command_omits_empty_values`
- `test_build_adapter_command_handles_paths_with_spaces`

**stage_infer** (`test_stages.py`; inline tmp fake adapter that echoes argv to
`_argv.json` + writes `.md` + `_run_stats.json(engine=backend)`)
- `test_stage_infer_invokes_adapter_with_config`
- `test_stage_infer_reads_run_stats` (returns `InferResult` with both fields)
- `test_stage_infer_reports_adapter_stderr_on_failure`

**run config threading** (`test_cli.py`/`test_run_config.py`; monkeypatch the 4 stages)
- `test_run_all_uses_same_backend_for_infer_and_publish`
- `test_run_all_forwards_server_url_and_api_model_name`

**prediction_dir**
- `test_publish_records_real_predictions_dir`
- `test_run_all_passes_out_dir_to_publish`
- `test_publish_does_not_use_results_dir_parent_as_prediction_dir`

**backend consistency**
- `test_publish_uses_adapter_reported_backend`
- `test_publish_rejects_requested_backend_mismatch`
- `test_publish_allows_empty_requested_backend`

**provenance schema**
- `test_provenance_contains_backend`
- `test_provenance_schema_accepts_backend` (also covers required)

**Updated existing** (the `InferResult` return-type change + required
`predictions_dir` kwarg ripple into three existing tests — all must be updated,
not just extended)
- `test_stages.py::test_stage_infer_runs_adapter_subprocess` — accesses
  `summary["count"]`/`summary["ok"]`; now `summary.run_stats["count"]`.
- `test_contract_integration.py::test_fake_adapter_infer_then_publish` —
  `summary["ok"]` → `summary.run_stats["ok"]`; pass `predictions_dir`; assert
  `provenance["backend"]`.
- `test_cli.py::test_cli_run_all_orchestrates_four_stages_in_order` — its
  `stage_infer` mock returns a plain dict; `_orchestrate_run` now reads
  `infer_result.adapter_argv`, so the mock must return an `InferResult`
  (`InferResult(run_stats={...}, adapter_argv=[...])`). Keep the order assertion;
  may add infer-config / publish-kwargs assertions.

---

## 9. CPU-only end-to-end smoke (`tests/test_smoke_config_pipeline.py`)

1. Inline fake adapter (tmp file): accepts all forwarded flags, writes received
   argv to `out_dir/_argv.json`, writes `out_dir/<stem>.md`, writes
   `_run_stats.json` with `engine=<backend>`, exits 0. (A second variant exits 1
   with a stderr line for the failure test.)
2. `omnidocbench-rocm infer --adapter <fake> --img-dir … --out-dir … --platform
   linux-rocm --backend vlm-vllm --server-url http://127.0.0.1:8265/v1
   --api-model-name mineru-pro --skip-existing` → assert `_argv.json` shows the
   forwarded flags; assert `.md` + `_run_stats.json` exist.
3. `stage_publish(...)` (or `omnidocbench-rocm publish --predictions-dir …`) →
   assert provenance: `prediction_dir` correct, `backend == "vlm-vllm"`,
   `vlm_server_url` correct, `api_model_name == "mineru-pro"`,
   `adapter_command == shlex.join(<argv from _argv.json>)`.

No GPU, no network, no OmniDocBench scoring.

---

## 10. Quality gates

```bash
pytest -q
python scripts/check_brand.py
python scripts/validate_registry.py
python -m build
```

No ruff/mypy configured. `check_brand` excludes `docs/superpowers/**`, so the
spec/plan files don't trip the brand gate.

---

## 11. Compatibility / migration

- **No break** for `run`/`infer`/`score` without the new flags — config stays
  effectively `{}`, behavior identical to today.
- **One breaking change:** standalone `publish` now **requires**
  `--predictions-dir`. Migration: add `--predictions-dir <real .md dir>`.
  (Version bumped to 0.3.0; documented in CHANGELOG + onboarding-runbook Step 5.)
- `stage_publish` gains a required `predictions_dir` kwarg →
  `test_contract_integration.py` updated to pass it.
- `run --stage publish` does **not** require `--predictions-dir` (auto-derives);
  only standalone `publish` does.

---

## 12. Risks / follow-ups

**Risks carried by this spec (honestly stated):**
- **A5 — infer Python.** `stage_infer` runs the adapter under the engine's
  `sys.executable`, but `docs/architecture.md` says infer belongs in the *model
  venv (3.12)*. This is a **pre-existing** tension, **out of P0 scope**.
  Provenance now *honestly records* which Python ran (via `adapter_command`'s
  `argv[0]`), so the discrepancy is visible. Resolving it (e.g. a
  `--model-venv`/`--adapter-python` flag) is a follow-up.

**Follow-ups (recorded, not done in P0):**
- **C1** — extend `check_conformance` to assert committed
  `provenance.backend == _run_stats.json["engine"]` (closes the "lying
  provenance" gap; `check_conformance` validates only `model_card` today).
- **C2** — store `adapter_argv` as a parallel **list** in provenance
  (machine-actionable) alongside the `shlex` string.
- **C3** — independent backend verification (ceiling = C1; the engine cannot
  truly verify what the adapter ran).
- **C4** — migrate bare `SystemExit` → typed exceptions (`BackendMismatchError`,
  `AdapterError`) translated to exit codes in `cli.main`.
- **C5** — resolve the model-venv vs `sys.executable` infer-Python tension (A5).

---

## 13. Plan-level verifications (resolve during writing-plans, do not block design)

- Exact kwarg order/defaults for the new `stage_publish` signature so all
  callers (CLI ×3, tests ×2) compile.
- Whether `_assert_full_set` returning the dict ripples into any other caller
  (only `stage_publish` calls it today — confirm).
- `argparse` behavior for `--predictions-dir` default `""` vs `None` on `run`
  (use `default=""`, resolve via `_resolve_predictions_dir`).
- Confirm `shlex.join` availability + behavior on the absolute `sys.executable`
  path (stdlib, fine).

---

## 14. Next step

Spec review (user). On approval → `writing-plans` skill produces the
step-by-step implementation plan (saved to
`docs/superpowers/plans/2026-07-21-p0-platform-provenance.md`), then execution.
**No code until the plan is approved.**
