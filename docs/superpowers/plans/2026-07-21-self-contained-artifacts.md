# Self-contained artifacts + MinerU evidence consistency — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline, this engagement). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every surface describing `mineru2.5`'s Linux-ROCm result tell one self-contained, auditable story at Overall 95.56 (CDM), and harden the platform `publish` so all bundles are self-contained + cross-validatable.

**Architecture:** Two phases. **Phase A** (platform `OmniDocBench-ROCm`, branch `fix/p0.1-self-contained-artifacts` from `origin/main`@`385cd40`, 0.3.0→0.3.1): harden CLI, make `publish` emit self-contained bundles (copied metric/run_stats/scoring/dataset-identity + prediction manifest), split prediction-source vs packaging provenance, add `validate-bundle`, fix docs/template, registry↔model_card cross-check. **Phase B** (model `MinerU-ROCm`, branch `fix/p1.1-evidence-consistency` from `main`@`bb4ad48`): install platform 0.3.1 editable, unify 95.56-primary, data-driven gate, purge stale claims, bump dep, split CI, regenerate the bundle from the existing 1649 predictions, verify end-to-end.

**Tech Stack:** Python 3.11/3.12, argparse, jsonschema (Draft 2020-12), PyYAML, pytest. No new deps.

## Global Constraints (verbatim from spec)

- Canonical result: mineru2.5 / vlm-vllm / linux-rocm / v1.6·v16 / revision `2b161d0` / Overall **95.56** / Text 0.0359 / CDM 96.73 / TEDS 93.54 / read-order 0.1240 / 1651 pages / ok 1649 / fail 2 / fallback 0 / badge community / windows-hip community-wanted.
- Overall formula: `((1 - text_EditDist)*100 + formula_CDM*100 + table_TEDS*100) / 3`, agg `page.ALL`, `quick_match`; reading_order NOT in Overall. Recomputes to 95.5605.
- 95.46 = prior standalone (same predictions, CDM 96.46); retained as historical, never deleted silently.
- Prediction-producing commit = `b75f788419d35a4210c201159a6c67923d60d65c`. Dataset/scorer revision = `2b161d0`.
- Reuse the existing valid CDM metric; do NOT re-score or re-infer. Prediction set: `/root/ocr-eval/mineru-vlm-vllm-preds` (1651 md, 1649 non-empty, 2 empty).
- Platform version target: **0.3.1**. Model pins `omnidocbench-rocm>=0.3.1,<0.4`.
- No forged artifacts; no hand-written `_run_stats.json`; no manifest from samples; migration commit ≠ prediction commit; no real IPs/hostnames/absolute private paths in committed provenance (redacted via MinerU `scripts/redact_internal.py` post-publish).
- Stop at `community`; do NOT create `VERIFIED.yaml`.

---

# PHASE A — Platform (OmniDocBench-ROCm)

Branch: `fix/p0.1-self-contained-artifacts` (already created from `origin/main`).

## Task A1: `copy_artifact` + `write_prediction_manifest` + `write_dataset_identity`

**Files:**
- Modify: `engine/omnidocbench_rocm/artifact_utils.py` (add 3 functions; add `import hashlib`)
- Test: `tests/test_artifact_utils.py` (extend)

**Interfaces (produces):**
- `copy_artifact(*, source: Path, destination: Path) -> Path`
- `write_prediction_manifest(*, predictions_dir: Path, destination: Path, model_id: str, platform: str, backend: str, run_stats: dict) -> Path`
- `write_dataset_identity(*, destination: Path, dataset: str, version: str, revision: str, ground_truth_file: str, ground_truth_sha256: str) -> Path`

- [ ] **Step 1: Write failing tests** (append to `tests/test_artifact_utils.py`)

```python
import hashlib, json
from pathlib import Path
from omnidocbench_rocm import artifact_utils as au

def test_copy_artifact_copies_and_creates_parent(tmp_path):
    src = tmp_path / "s.json"; src.write_text("{}")
    dst = tmp_path / "nested" / "deep" / "d.json"
    out = au.copy_artifact(source=src, destination=dst)
    assert out == dst and dst.read_text() == "{}"

def test_copy_artifact_fails_when_source_missing(tmp_path):
    import pytest
    with pytest.raises(FileNotFoundError):
        au.copy_artifact(source=tmp_path / "nope", destination=tmp_path / "d")

def test_prediction_manifest_hashes_nonempty_and_is_deterministic(tmp_path):
    preds = tmp_path / "preds"; preds.mkdir()
    (preds / "b.md").write_text("hello"); (preds / "a.md").write_text("world")
    (preds / "empty.md").write_text("")          # excluded
    rs = {"count": 3, "ok": 2, "fail": 1, "stats": [
        {"image": "x.png", "status": "failed: empty prediction", "error": "empty prediction"}]}
    dst = tmp_path / "m.json"
    p1 = au.write_prediction_manifest(predictions_dir=preds, destination=dst,
        model_id="m", platform="linux-rocm", backend="vlm-vllm", run_stats=rs)
    m = json.loads(dst.read_text())
    assert m["prediction_count"] == 2
    assert [f["relative_path"] for f in m["files"]] == ["a.md", "b.md"]  # sorted
    assert m["files"][0]["sha256"] == hashlib.sha256(b"world").hexdigest()
    assert m["hash_algorithm"] == "sha256"
    assert m["failed_pages"][0]["reason"] == "empty prediction"
    # deterministic
    dst2 = tmp_path / "m2.json"
    au.write_prediction_manifest(predictions_dir=preds, destination=dst2,
        model_id="m", platform="linux-rocm", backend="vlm-vllm", run_stats=rs)
    assert dst2.read_text() == dst.read_text()

def test_dataset_identity_records_revision_and_gt_sha(tmp_path):
    dst = tmp_path / "ident.json"
    au.write_dataset_identity(destination=dst, dataset="OmniDocBench", version="v1.6",
        revision="2b161d0", ground_truth_file="OmniDocBench.json",
        ground_truth_sha256="abc123")
    ident = json.loads(dst.read_text())
    assert ident["revision"] == "2b161d0"
    assert ident["ground_truth_sha256"] == "abc123"
    assert ident["ground_truth_file"] == "OmniDocBench.json"
```

- [ ] **Step 2: Run, verify FAIL** — `pytest tests/test_artifact_utils.py -q` → AttributeError/ImportError.

- [ ] **Step 3: Implement** — add `import hashlib` at top of `artifact_utils.py`; append:

```python
def copy_artifact(*, source: Path, destination: Path) -> Path:
    """Copy a required artifact into the results bundle. Fails loudly if the
    source is absent (never silently skip a missing metric/run_stats)."""
    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(f"Artifact source not found: {source}")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return destination


def write_prediction_manifest(*, predictions_dir: Path, destination: Path,
                              model_id: str, platform: str, backend: str,
                              run_stats: dict) -> Path:
    """Deterministic SHA256 manifest of non-empty .md predictions.

    Only existing, non-empty Markdown files are recorded, sorted by
    relative_path. ``failed_pages`` is derived from run_stats entries whose
    status starts with fail/fallback. No absolute host paths are baked in
    beyond ``source_prediction_dir`` (redacted downstream)."""
    predictions_dir = Path(predictions_dir)
    files = []
    for p in sorted(predictions_dir.glob("*.md")):
        size = p.stat().st_size
        if size == 0:
            continue
        files.append({"relative_path": p.name,
                      "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                      "size_bytes": size})
    failed = []
    for item in run_stats.get("stats", []) or []:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", ""))
        if status.startswith(("fail", "fallback")):
            img = item.get("image", "")
            failed.append({"relative_path": (Path(img).stem + ".md") if img else "",
                           "reason": str(item.get("error", status))})
    manifest = {
        "schema_version": 1,
        "model_id": model_id,
        "platform": platform,
        "backend": backend,
        "prediction_count": len(files),
        "expected_page_count": run_stats.get("count"),
        "failed_page_count": run_stats.get("fail"),
        "source_prediction_dir": str(predictions_dir),
        "hash_algorithm": "sha256",
        "files": files,
        "failed_pages": failed,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
                           encoding="utf-8")
    return destination


def write_dataset_identity(*, destination: Path, dataset: str, version: str,
                           revision: str, ground_truth_file: str,
                           ground_truth_sha256: str) -> Path:
    """Minimal dataset identity when no full manifest is available."""
    ident = {"schema_version": 1, "dataset": dataset, "version": version,
             "revision": revision, "ground_truth_file": ground_truth_file,
             "ground_truth_sha256": ground_truth_sha256 or "not_recorded"}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(ident, ensure_ascii=False, indent=2, sort_keys=True),
                           encoding="utf-8")
    return destination
```

- [ ] **Step 4: Run, verify PASS** — `pytest tests/test_artifact_utils.py -q`.
- [ ] **Step 5: Commit** — `feat(artifact_utils): copy_artifact, prediction manifest, dataset identity`.

---

## Task A2: `write_run_summary` / `write_provenance` reference committed copies + migration fields

**Files:**
- Modify: `engine/omnidocbench_rocm/artifact_utils.py` (`write_run_summary`, `write_provenance` signatures + recorded paths)
- Modify: `contracts/artifact-schema.json` (add optional provenance properties)
- Test: `tests/test_artifact_utils.py`, `tests/test_schema.py`

**Interfaces (produces):**
- `write_run_summary(*, save_name, run_stats_path, metric_result_path, committed_metric_result_path, committed_run_stats_path, destination, cdm) -> Path`
- `write_provenance(*, destination, git_commit, engine_version, model_id, platform, server_url, api_model_name, adapter_command, scoring_config_path, dataset_manifest_path, dataset_identity_path, dataset_revision, predictions_dir, prediction_manifest_path, prediction_manifest_sha256, metric_result_paths, run_summary_paths, run_stats_path, source_metric_result_path="", source_run_stats_path="", source_prediction_dir="", packaging_commit="", prediction_source_commit="", prediction_source_command="", prediction_source_run_manifest="", migration_type="") -> Path`

- [ ] **Step 1: Write failing tests** asserting run_summary/provenance point at committed copies and carry migration fields (see Task A3 test bundle for the integrated assertions; here add unit-level checks that `metric_result_path == str(committed_metric_result_path)` and provenance has `packaging_commit`/`prediction_source_commit`/`migration_type`).
- [ ] **Step 2: Run, verify FAIL.**
- [ ] **Step 3: Implement** —
  - `write_run_summary`: replace the two recorded path fields:
    ```python
    "metric_result_path": str(committed_metric_result_path),
    "run_stats_path": str(committed_run_stats_path),
    ```
  - `write_provenance`: add to the dict (all optional, defaulting to `""`):
    ```python
    "packaging_commit": packaging_commit or git_commit,
    "prediction_source_commit": prediction_source_commit,
    "prediction_source_command": prediction_source_command,
    "prediction_source_run_manifest": prediction_source_run_manifest,
    "prediction_manifest_path": str(prediction_manifest_path),
    "prediction_manifest_sha256": prediction_manifest_sha256,
    "dataset_identity_path": str(dataset_identity_path),
    "source_metric_result_path": source_metric_result_path,
    "source_run_stats_path": source_run_stats_path,
    "source_prediction_dir": source_prediction_dir,
    "migration_type": migration_type,
    ```
    Keep `prediction_dir`, `metric_result_paths`, `run_summary_paths`, `run_stats_path` pointing at the committed copies passed in by stage_publish.
  - `contracts/artifact-schema.json` provenance `properties`: add `packaging_commit`, `prediction_source_commit`, `prediction_source_command`, `prediction_source_run_manifest`, `prediction_manifest_path`, `prediction_manifest_sha256`, `dataset_identity_path`, `source_metric_result_path`, `source_run_stats_path`, `source_prediction_dir`, `migration_type` (all `{"type":"string"}`). Do NOT change `required`.
- [ ] **Step 4: Run** `pytest tests/test_artifact_utils.py tests/test_schema.py -q` → PASS.
- [ ] **Step 5: Commit** — `feat(provenance): record prediction source, migration metadata, committed-copy paths`.

---

## Task A3: `stage_publish` emits the self-contained bundle

**Files:**
- Modify: `engine/omnidocbench_rocm/stages.py` (`stage_publish` signature + body)
- Test: `tests/test_stages.py` (extend the `_publish_inputs` helper + add bundle tests)

**Interfaces (produces):** new `stage_publish(...)` returns `{"run_summary", "provenance", "metric_result", "run_stats", "prediction_manifest", "dataset_identity", "scoring_config"}` (latter three may be `None`).

New `stage_publish` params (added, all keyword, with defaults so existing callers/tests keep working): `scoring_config_path: str = ""`, `dataset_manifest_path: str = ""`, `ground_truth_sha256: str = ""`, `prediction_source_commit: str = ""`, `prediction_source_command: str = ""`, `prediction_source_run_manifest: str = ""`, `migration_type: str = ""`.

- [ ] **Step 1: Write failing tests** in `tests/test_stages.py`:

```python
def test_publish_copies_metric_result_and_run_stats(tmp_path):
    rs, metric, results = _publish_inputs(tmp_path)
    preds = tmp_path / "preds"; preds.mkdir()
    out = stages.stage_publish(model_id="m", platform="linux-rocm", version="v16",
        cdm=True, run_stats_path=rs, metric_result_path=metric, results_dir=results,
        git_commit="c", engine_version="0.3.1", adapter_command="python a.py",
        predictions_dir=preds, dataset_revision="2b161d0")
    assert (results / "m_v16_quick_match_cdm_metric_result.json").exists()
    assert (results / "m_v16_quick_match_cdm_run_stats.json").exists()

def test_publish_cdm_and_non_cdm_do_not_clobber(tmp_path):
    rs, metric, results = _publish_inputs(tmp_path)
    preds = tmp_path / "preds"; preds.mkdir()
    for cdm in (True, False):
        stages.stage_publish(model_id="m", platform="linux-rocm", version="v16",
            cdm=cdm, run_stats_path=rs, metric_result_path=metric, results_dir=results,
            git_commit="c", engine_version="0.3.1", adapter_command="python a.py",
            predictions_dir=preds, dataset_revision="2b161d0")
    names = {p.name for p in results.iterdir()}
    assert "m_v16_quick_match_metric_result.json" in names
    assert "m_v16_quick_match_cdm_metric_result.json" in names

def test_run_summary_references_committed_copies(tmp_path):
    rs, metric, results = _publish_inputs(tmp_path)
    preds = tmp_path / "preds"; preds.mkdir()
    out = stages.stage_publish(model_id="m", platform="linux-rocm", version="v16",
        cdm=False, run_stats_path=rs, metric_result_path=metric, results_dir=results,
        git_commit="c", engine_version="0.3.1", adapter_command="python a.py",
        predictions_dir=preds, dataset_revision="2b161d0")
    summ = json.loads(Path(out["run_summary"]).read_text())
    assert summ["metric_result_path"].endswith("m_v16_quick_match_metric_result.json")
    assert summ["run_stats_path"].endswith("m_v16_quick_match_run_stats.json")

def test_publish_writes_prediction_manifest(tmp_path):
    rs, metric, results = _publish_inputs(tmp_path)
    preds = tmp_path / "preds"; preds.mkdir()
    (preds / "a.md").write_text("x")
    out = stages.stage_publish(model_id="m", platform="linux-rocm", version="v16",
        cdm=False, run_stats_path=rs, metric_result_path=metric, results_dir=results,
        git_commit="c", engine_version="0.3.1", adapter_command="python a.py",
        predictions_dir=preds, dataset_revision="2b161d0")
    prov = json.loads(Path(out["provenance"]).read_text())
    assert prov["prediction_manifest_path"].endswith("_prediction_manifest.json")
    man = json.loads(Path(out["prediction_manifest"]).read_text())
    assert man["prediction_count"] == 1

def test_publish_records_prediction_source_and_packaging(tmp_path):
    rs, metric, results = _publish_inputs(tmp_path)
    preds = tmp_path / "preds"; preds.mkdir()
    out = stages.stage_publish(model_id="m", platform="linux-rocm", version="v16",
        cdm=False, run_stats_path=rs, metric_result_path=metric, results_dir=results,
        git_commit="pack123", engine_version="0.3.1", adapter_command="python a.py",
        predictions_dir=preds, dataset_revision="2b161d0",
        prediction_source_commit="pred456", prediction_source_command="mineru-rocm predict",
        prediction_source_run_manifest="results/.../run_manifest.json",
        migration_type="legacy_predictions_to_platform_artifacts")
    prov = json.loads(Path(out["provenance"]).read_text())
    assert prov["packaging_commit"] == "pack123"
    assert prov["prediction_source_commit"] == "pred456"
    assert prov["migration_type"] == "legacy_predictions_to_platform_artifacts"

def test_publish_rejects_dot_scoring_config(tmp_path):
    import pytest
    rs, metric, results = _publish_inputs(tmp_path)
    preds = tmp_path / "preds"; preds.mkdir()
    with pytest.raises(SystemExit):
        stages.stage_publish(model_id="m", platform="linux-rocm", version="v16",
            cdm=False, run_stats_path=rs, metric_result_path=metric, results_dir=results,
            git_commit="c", engine_version="0.3.1", adapter_command="python a.py",
            predictions_dir=preds, dataset_revision="2b161d0", scoring_config_path=".")

def test_publish_synthesizes_dataset_identity(tmp_path):
    rs, metric, results = _publish_inputs(tmp_path)
    preds = tmp_path / "preds"; preds.mkdir()
    out = stages.stage_publish(model_id="m", platform="linux-rocm", version="v16",
        cdm=False, run_stats_path=rs, metric_result_path=metric, results_dir=results,
        git_commit="c", engine_version="0.3.1", adapter_command="python a.py",
        predictions_dir=preds, dataset_revision="2b161d0",
        ground_truth_sha256="deadbeef")
    assert (results / "m_v16_quick_match_dataset_identity.json").exists()
    ident = json.loads((results / "m_v16_quick_match_dataset_identity.json").read_text())
    assert ident["revision"] == "2b161d0" and ident["ground_truth_sha256"] == "deadbeef"
```

Also update the existing `_publish_inputs` calls if needed (they pass `engine="vllm"`/`"pipeline"` and no scoring_config → fine; `dataset_revision="v1.6"` stays valid).

- [ ] **Step 2: Run, verify FAIL.**
- [ ] **Step 3: Implement** — rewrite `stage_publish` body (`stages.py`) to:

```python
def stage_publish(*, model_id, platform, version, cdm, run_stats_path, metric_result_path,
                  results_dir, git_commit, engine_version, adapter_command, predictions_dir,
                  requested_backend="", server_url="", api_model_name="",
                  scoring_config_path="", dataset_manifest_path="", dataset_revision="",
                  ground_truth_sha256="", prediction_source_commit="",
                  prediction_source_command="", prediction_source_run_manifest="",
                  migration_type=""):
    run_stats = _assert_full_set(run_stats_path)
    actual_backend = run_stats.get("engine", "")
    if requested_backend and requested_backend != actual_backend:
        raise SystemExit(f"Refusing to publish: requested backend {requested_backend!r} "
                         f"does not match adapter-reported engine {actual_backend!r}.")
    if scoring_config_path == "." or dataset_manifest_path == ".":
        raise SystemExit("Refusing to publish: scoring_config_path/dataset_manifest_path "
                         "must be real paths, not '.'.")
    results_dir = Path(results_dir); results_dir.mkdir(parents=True, exist_ok=True)
    save_name = f"{model_id}_{version}_quick_match{'_cdm' if cdm else ''}"
    committed_metric = results_dir / f"{save_name}_metric_result.json"
    committed_stats  = results_dir / f"{save_name}_run_stats.json"
    au.copy_artifact(source=metric_result_path, destination=committed_metric)
    au.copy_artifact(source=run_stats_path, destination=committed_stats)
    # scoring config (optional, real path only)
    committed_scoring = None
    if scoring_config_path:
        committed_scoring = results_dir / f"{save_name}_scoring_config.yaml"
        au.copy_artifact(source=Path(scoring_config_path), destination=committed_scoring)
    # dataset identity: copy real manifest OR synthesize
    if dataset_manifest_path and Path(dataset_manifest_path).is_file():
        committed_dataset = results_dir / f"{save_name}_dataset_manifest.json"
        au.copy_artifact(source=Path(dataset_manifest_path), destination=committed_dataset)
    else:
        committed_dataset = results_dir / f"{save_name}_dataset_identity.json"
        au.write_dataset_identity(destination=committed_dataset, dataset="OmniDocBench",
            version=version, revision=dataset_revision,
            ground_truth_file="OmniDocBench.json", ground_truth_sha256=ground_truth_sha256)
    # prediction manifest
    committed_manifest = results_dir / f"{save_name}_prediction_manifest.json"
    au.write_prediction_manifest(predictions_dir=predictions_dir, destination=committed_manifest,
        model_id=model_id, platform=platform, backend=actual_backend, run_stats=run_stats)
    manifest_sha = hashlib.sha256(committed_manifest.read_bytes()).hexdigest()
    summary_path = results_dir / f"{save_name}_run_summary.json"
    provenance_path = results_dir / f"{save_name}_provenance.json"
    au.write_run_summary(save_name=save_name, run_stats_path=run_stats_path,
        metric_result_path=metric_result_path, committed_metric_result_path=committed_metric,
        committed_run_stats_path=committed_stats, destination=summary_path, cdm=cdm)
    au.write_provenance(destination=provenance_path, git_commit=git_commit,
        engine_version=engine_version, model_id=model_id, platform=platform,
        server_url=server_url, api_model_name=api_model_name, adapter_command=adapter_command,
        scoring_config_path=Path(scoring_config_path), dataset_manifest_path=Path(dataset_manifest_path),
        dataset_identity_path=committed_dataset, dataset_revision=dataset_revision,
        predictions_dir=predictions_dir, prediction_manifest_path=committed_manifest,
        prediction_manifest_sha256=manifest_sha, metric_result_paths=[committed_metric],
        run_summary_paths=[summary_path], run_stats_path=committed_stats,
        source_metric_result_path=str(metric_result_path), source_run_stats_path=str(run_stats_path),
        source_prediction_dir=str(predictions_dir), packaging_commit=git_commit,
        prediction_source_commit=prediction_source_commit, prediction_source_command=prediction_source_command,
        prediction_source_run_manifest=prediction_source_run_manifest, migration_type=migration_type)
    return {"run_summary": str(summary_path), "provenance": str(provenance_path),
            "metric_result": str(committed_metric), "run_stats": str(committed_stats),
            "prediction_manifest": str(committed_manifest),
            "dataset_identity": str(committed_dataset),
            "scoring_config": str(committed_scoring) if committed_scoring else None}
```
Add `import hashlib` to `stages.py`.

- [ ] **Step 4: Run** `pytest tests/test_stages.py -q` → PASS (including the existing `test_publish_*` backend/prediction_dir tests).
- [ ] **Step 5: Commit** — `feat(publish): emit self-contained result bundles`.

---

## Task A4: CLI — `publish --backend`, `run --metric-result`, migration flags

**Files:**
- Modify: `engine/omnidocbench_rocm/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:** `publish` adds `--backend`; `run` adds `--metric-result`, `--prediction-source-commit`, `--prediction-source-command`, `--prediction-source-run-manifest`, `--migration-type`; `publish` adds the four migration flags.

- [ ] **Step 1: Write failing tests** (append to `tests/test_cli.py`):

```python
def test_publish_cli_forwards_requested_backend(tmp_path):
    with patch("omnidocbench_rocm.cli.stage_publish") as pub:
        pub.return_value = {"run_summary": "x"}
        main(["publish", "--model-id", "m", "--platform", "linux-rocm",
              "--run-stats", str(tmp_path/"r.json"), "--metric-result", str(tmp_path/"m.json"),
              "--results-dir", str(tmp_path), "--predictions-dir", str(tmp_path/"p"),
              "--git-commit", "c", "--adapter-command", "x", "--dataset-revision", "2b161d0",
              "--backend", "vlm-vllm"])
        assert pub.call_args.kwargs["requested_backend"] == "vlm-vllm"

def test_run_publish_requires_metric_result(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main(["run", "--stage", "publish", "--platform", "linux-rocm", "--version", "v16",
              "--revision", "2b161d0", "--adapter", "a.py", "--model-id", "m",
              "--git-commit", "c", "--results-dir", str(tmp_path)])
    assert "requires --metric-result" in str(exc.value)

def test_run_publish_uses_explicit_metric_result(tmp_path):
    with patch("omnidocbench_rocm.cli.stage_publish") as pub:
        pub.return_value = {"run_summary": "x"}
        main(["run", "--stage", "publish", "--platform", "linux-rocm", "--version", "v16",
              "--revision", "2b161d0", "--adapter", "a.py", "--model-id", "m",
              "--git-commit", "c", "--results-dir", str(tmp_path),
              "--metric-result", str(tmp_path/"metric.json"),
              "--predictions-dir", str(tmp_path/"p")])
        assert pub.call_args.kwargs["metric_result_path"] == tmp_path/"metric.json"

def test_run_all_defaults_prediction_source_to_current_run(tmp_path):
    with patch("omnidocbench_rocm.cli.stage_download"), \
         patch("omnidocbench_rocm.cli.stage_infer") as inf, \
         patch("omnidocbench_rocm.cli.stage_score") as sc, \
         patch("omnidocbench_rocm.cli.stage_publish") as pub, \
         patch("omnidocbench_rocm.cli.get_backend"):
        inf.return_value = InferResult(run_stats={"count":0,"ok":0},
                                       adapter_argv=[sys.executable, "a.py", "--backend", "x"])
        sc.return_value = tmp_path/"metric.json"
        main(["run", "--stage", "all", "--platform", "linux-rocm", "--version", "v16",
              "--revision", "2b161d0", "--adapter", "a.py", "--model-id", "m",
              "--git-commit", "HEAD1", "--results-dir", str(tmp_path)])
        kw = pub.call_args.kwargs
        assert kw["prediction_source_commit"] == "HEAD1"
        assert kw["migration_type"] == "native-platform-run"
        assert kw["prediction_source_command"] and "--backend" in kw["prediction_source_command"]
```

- [ ] **Step 2: Run, verify FAIL.**
- [ ] **Step 3: Implement** in `cli.py`:
  - `publish` subparser: add `pu.add_argument("--backend", default="", help="expected adapter backend; checked against _run_stats.json['engine']")` and the four migration flags (`--prediction-source-commit/--command/--run-manifest/--migration-type`, all `default=""`).
  - `publish` dispatch: pass `requested_backend=a.backend`, `ground_truth_sha256=a.gt_sha256` (add `--gt-sha256` default `""`), and the four migration kwargs.
  - `run` subparser: add `--metric-result` (default `""`), the four migration flags, `--gt-sha256`.
  - In `_orchestrate_run` `stage=="publish"` block: replace the guessed `metric_path` with:
    ```python
    if not a.metric_result:
        raise SystemExit("run --stage publish requires --metric-result")
    metric_path = Path(a.metric_result)
    ```
    and pass it; also pass the migration kwargs (default `""`).
  - In `_orchestrate_run` `stage=="all"` block: when calling `stage_publish`, add defaults:
    ```python
    prediction_source_commit=(a.prediction_source_commit or a.git_commit),
    prediction_source_command=(a.prediction_source_command or adapter_command),
    prediction_source_run_manifest=a.prediction_source_run_manifest,
    migration_type=(a.migration_type or "native-platform-run"),
    ground_truth_sha256=a.gt_sha256,
    ```
- [ ] **Step 4: Run** `pytest tests/test_cli.py -q` → PASS (existing `run --stage all` kwargs assertions still hold).
- [ ] **Step 5: Commit** — `fix(cli): make staged publish explicit and backend-checked`.

---

## Task A5: `bundle_validator.py` + `validate-bundle` CLI

**Files:**
- Create: `engine/omnidocbench_rocm/bundle_validator.py`
- Modify: `engine/omnidocbench_rocm/cli.py` (add `validate-bundle` subparser + dispatch)
- Test: `tests/test_bundle_validator.py`

**Interfaces:** `validate_bundle(results_dir: Path, *, model_card: Path|None=None, registry: Path|None=None) -> ConformanceReport` (reuse the `conformance.ConformanceReport` shape). Overall recompute helper `_recompute_overall(metric: dict) -> float|None`.

- [ ] **Step 1: Write failing tests** covering: model_id consistency; backend==engine; count arithmetic (ok+fail+fallback==page_count); manifest count==ok; dataset revision consistent; referenced files resolve; cdm flag; overall recompute == model_card == registry; and one negative per dimension.
- [ ] **Step 2: Run, verify FAIL.**
- [ ] **Step 3: Implement** `bundle_validator.py`:
  - Discover bundle files by `save_name` (one `<save_name>_run_summary.json` per bundle in `results_dir`).
  - For each: load run_summary/provenance/metric_result/run_stats/prediction_manifest/dataset_identity; run all checks; record failures.
  - `_recompute_overall(metric)` = `((1-text)*100 + cdm*100 + teds*100)/3` reading `text_block.page.Edit_dist.ALL`, `display_formula.page.CDM.ALL`, `table.page.TEDS.ALL` (skip if CDM invalid per `analyze_metric_quality`); return `round(x, 2)` or `None`.
  - If `--model-card` given: assert `model_card.model_id == provenance.model_id`; `model_card.overall` == recompute (2 dp); `model_card.artifacts.*` resolve.
  - If `--registry` given: find the row matching `model_id`+platform; assert `registry.overall == model_card.overall` and badge match.
  - CLI `validate-bundle <results-dir> [--model-card P] [--registry P]` → print CONFORMANT/NON-CONFORMANT, exit 0/1.
- [ ] **Step 4: Run** `pytest tests/test_bundle_validator.py -q` → PASS.
- [ ] **Step 5: Commit** — `feat(validation): add cross-artifact bundle validator`.

---

## Task A6: Docs + template + version + registry cross-check

**Files:**
- Modify: `README.md`, `docs/architecture.md`, `docs/roadmap.md`, `docs/ci-reality.md`
- Modify: `template/{{cookiecutter.repo_name}}/Makefile`
- Modify: `pyproject.toml`, `CHANGELOG.md`, `CITATION.cff`
- Modify: `scripts/validate_registry.py` (add optional `--model-card` cross-check) + `tests/test_registry_validation.py`

- [ ] **Step 1 (README/CDM):** Edit `README.md` registry block to the real state (mineru2.5 linux-rocm community 95.56; paddleocr-vl-1.6 community 95.77 both; unlimited-ocr community-wanted; hunyuan-ocr community-wanted). Replace any "Linux CDM is a scaffolded stub" / "no onboarded models" wording with: "Linux host CDM provisioning and scoring are implemented and exercised by community runs. Verified Docker reproduction remains the promotion path from community to verified. Windows-native CDM remains planned." Mirror relevant lines in `docs/architecture.md`, `docs/roadmap.md`, `docs/ci-reality.md`.
- [ ] **Step 2 (template Makefile):** set `REVISION ?= 2b161d0`; add
  ```make
  CDM ?= 1
  RESUME ?= 0
  CDM_FLAG = $(if $(filter 1,$(CDM)),--cdm,)
  RESUME_FLAG = $(if $(filter 1,$(RESUME)),--skip-existing,)
  ```
  and append `$(CDM_FLAG) $(RESUME_FLAG)` to `eval-linux`/`eval-windows`.
- [ ] **Step 3 (version):** `pyproject.toml` `version = "0.3.1"`; `CHANGELOG.md` add 0.3.1 entry (self-contained bundles, validate-bundle, provenance split, template revision, registry cross-check); `CITATION.cff` version.
- [ ] **Step 4 (registry cross-check):** extend `scripts/validate_registry.py` with `validate_against_model_card(rows, model_card: dict, model_id: str, platform: str)` asserting overall/badge/model_id/repo agreement; wire optional `--model-card <path> --model-id <id> --platform <plat>` in `main`. Add test.
- [ ] **Step 5: Run gates:** `pytest -q && python scripts/check_brand.py && python scripts/validate_registry.py && python scripts/generate_registry.py | head && python -m build && python -m pip check` → all PASS.
- [ ] **Step 6: Commit (layered):** `docs: align CDM and registry status`, `feat(template): default revision 2b161d0 + CDM/RESUME flags`, `chore: bump 0.3.0 -> 0.3.1`, `feat(registry): model_card cross-check`.

---

## Task A7: Push + open platform PR

- [ ] **Step 1:** `git push -u origin fix/p0.1-self-contained-artifacts`.
- [ ] **Step 2:** Open PR to `AIwork4me/OmniDocBench-ROCm` (title: `P0.1: self-contained publish bundles + validate-bundle (0.3.1)`; body summarizes the 6 commits + the 95.56 recompute proof + verification command output).
- [ ] **Step 3:** Capture the PR URL and the merge commit SHA after merge (needed for the MinerU CI pin).

---

# PHASE B — Model (MinerU-ROCm)

Precondition: platform 0.3.1 installed editable (`pip install -e /workspace/omnidocbench-rocm`). Branch: `fix/p1.1-evidence-consistency` from `main`.

## Task B1: Data-driven gate (replace hardcoded 95.46/95.56)

**Files:**
- Modify: `scripts/check_repo.py` (delete `_STALE_VLM_OVERALL`/`_CURRENT_VLM_OVERALL`; read lock)
- Test: `tests/test_check_repo.py`

- [ ] **Step 1: Write failing tests:** `test_readme_headline_matches_lock`, `test_readme_zh_headline_matches_lock`, `test_model_card_matches_lock`, `test_current_result_appears_once_as_primary`, `test_prior_result_requires_historical_context` (95.46 allowed only alongside 95.56 + "prior"), `test_registry_matches_model_card` (registry snapshot vs model_card).
- [ ] **Step 2: Run, verify FAIL.**
- [ ] **Step 3: Implement:** load `reproducibility.lock.yaml` → `benchmark.full_1651.vlm_vllm.overall` as the single current value. New checks: README headline number == current; README.zh-CN headline == current; `model_card.json overall` == current; 95.46 (prior) permitted only when 95.56 also present in the same doc (comparative context). Keep the no-internal-infra + no-withdrawn-anchor gates.
- [ ] **Step 4: Run** `pytest tests/test_check_repo.py -q` → PASS.
- [ ] **Step 5: Commit** — `fix(gates): replace hard-coded score drift checks with lock-sourced value`.

## Task B2: Unify 95.56-primary across docs

**Files:** `README.md`, `README.zh-CN.md`, `model_card.json`, `docs/reproducibility.md`, `docs/how-it-works.md`, `docs/benchmark-methodology.md`, `CHANGELOG.md`, `results/omnidocbench/v16/linux-rocm/README.md`, `README.md:170`

- [ ] **Step 1:** README badge + headline + At-a-glance → 95.56 (CDM 96.73). README.zh-CN same. Add a "Prior standalone score: 95.46 (same predictions, CDM 96.46); Current platform CDM: 95.56; Δ +0.10 pp" note near the results.
- [ ] **Step 2:** `model_card.json artifacts.metric_result` → `…/mineru2.5_v16_quick_match_cdm_metric_result.json` (fix cdm/non-cdm mismatch). Ensure overall 95.56 + submetrics text 0.0359/CDM 96.73/TEDS 93.54/read-order 0.1240.
- [ ] **Step 3:** Stale-claim purge: `results/omnidocbench/v16/linux-rocm/README.md` + README:170 + `docs/known-gaps.md` + `docs/reproducibility.md` + CHANGELOG → "Platform-standard artifacts generated 2026-07-21. Canonical bundle in `results/omnidocbench/v16/linux-rocm/`. Legacy `results/omnidocbench/v1.6/` retained for historical comparison + prediction-source provenance." Adjust `docs/how-it-works.md`/`benchmark-methodology.md` 95.46→95.56-primary (95.46 historical).
- [ ] **Step 4:** CHANGELOG entry documenting the 95.46→95.56-primary reversal and WHY (same preds, CDM 96.46→96.73, recomputes to 95.5605) — auditable, not silent.
- [ ] **Step 5: Run** `python scripts/check_repo.py` → PASS (the new data-driven gate).
- [ ] **Step 6: Commit (layered):** `fix(results): unify current mineru2.5 result at 95.56`, `fix(docs): remove stale artifact and conformance claims`.

## Task B3: Build + Makefile + CI

**Files:** `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml`, `scripts/validate_platform_artifacts.py` (new), `tests/test_validate_platform_artifacts.py` (new)

- [ ] **Step 1:** `pyproject.toml` → `platform = ["omnidocbench-rocm>=0.3.1,<0.4"]`.
- [ ] **Step 2:** `Makefile`: add `CDM ?= 1`, `RESUME ?= 0`, `CDM_FLAG`, `RESUME_FLAG`; rewrite `eval-mineru2.5-linux`/`eval-pipeline-linux` to use `$(CDM_FLAG) $(RESUME_FLAG)` and drop unconditional `--skip-existing`.
- [ ] **Step 3:** `scripts/validate_platform_artifacts.py`: thin wrapper calling `omnidocbench_rocm.bundle_validator.validate_bundle` over `results/omnidocbench/v16/linux-rocm` with `--model-card model_card.json`; exit 0/1. (TDD a smoke test that it exits 0 on the real bundle once generated, 1 on a tampered one.)
- [ ] **Step 4:** `.github/workflows/ci.yml`: two jobs. `core`: `pip install -e ".[dev]"`, `pytest -q`, `ruff check .`, `python scripts/check_repo.py`, `reuse lint`, `python -m build`, `python -m pip check`. `platform-contract`: `pip install "git+https://github.com/AIwork4me/OmniDocBench-ROCm.git@<P0.1_PIN>"` (or `omnidocbench-rocm>=0.3.1,<0.4` once shipped), `pip install -e ".[dev]"`, `omnidocbench-rocm conformance .`, `python scripts/validate_platform_artifacts.py`.
- [ ] **Step 5: Run** `pytest -q && ruff check . && python scripts/check_repo.py && python scripts/validate_platform_artifacts.py && python -m build && python -m pip check`.
- [ ] **Step 6: Commit (layered):** `build: require omnidocbench-rocm>=0.3.1,<0.4`, `fix(makefile): CDM=1/RESUME=0 defaults; drop unconditional --skip-existing`, `ci: validate platform contract and committed artifacts`.

## Task B4: Regenerate the self-contained bundle from existing predictions

Precondition: the platform PR (Phase A) is installed editable so `publish` has the new behavior.

- [ ] **Step 1 (verify inputs):** confirm `/root/ocr-eval/mineru-vlm-vllm-preds` = 1651 md / 1649 non-empty / 2 empty; `_run_stats.json` count 1651/ok 1649/fail 2; existing CDM metric `results/omnidocbench/v16/linux-rocm/mineru2.5_v16_quick_match_cdm_metric_result.json` recomputes to 95.56; legacy `results/omnidocbench/v1.6/vlm-vllm/run_manifest.json` repo_commit == `b75f788…`.
- [ ] **Step 2 (re-publish mineru2.5):**
  ```bash
  omnidocbench-rocm publish \
    --model-id mineru2.5 --platform linux-rocm --version v16 --cdm \
    --backend vlm-vllm \
    --run-stats /root/ocr-eval/mineru-vlm-vllm-preds/_run_stats.json \
    --metric-result results/omnidocbench/v16/linux-rocm/mineru2.5_v16_quick_match_cdm_metric_result.json \
    --results-dir results/omnidocbench/v16/linux-rocm \
    --predictions-dir /root/ocr-eval/mineru-vlm-vllm-preds \
    --git-commit "$(git rev-parse HEAD)" \
    --adapter-command "python adapter/run_adapter.py --img-dir <images> --out-dir /root/ocr-eval/mineru-vlm-vllm-preds --platform linux-rocm --backend vlm-vllm --server-url http://127.0.0.1:8265/v1 --api-model-name mineru-pro" \
    --server-url http://127.0.0.1:8265/v1 --api-model-name mineru-pro \
    --scoring-config eval/configs/omnidocbench_v16.yaml \
    --dataset-manifest <OmniDocBench.json path> --dataset-revision 2b161d0 \
    --gt-sha256 a45cd84b04ad8b793e775089640e6b681209abea33ead54c1828ddca35fae496 \
    --prediction-source-commit b75f788419d35a4210c201159a6c67923d60d65c \
    --prediction-source-command "mineru-rocm predict vlm-vllm (legacy standalone; see run_manifest.json)" \
    --prediction-source-run-manifest results/omnidocbench/v1.6/vlm-vllm/run_manifest.json \
    --migration-type legacy_predictions_to_platform_artifacts
  ```
  (Resolve concrete `<images>` / `<OmniDocBench.json>` paths at execution from the lock/dataset dir; the published adapter_command is the indexing/validation command for the legacy predictions, clearly distinct from `prediction_source_command`.)
- [ ] **Step 3 (redact):** `python scripts/redact_internal.py` to neutralize any residual host paths in the new bundle.
- [ ] **Step 4 (pipeline):** repeat analogously for `mineru-pipeline` (supplementary; backend `pipeline`; not added to registry).
- [ ] **Step 5 (validate):** `omnidocbench-rocm validate-bundle results/omnidocbench/v16/linux-rocm --model-card model_card.json --registry <platform>/hub/registry.yaml` → CONFORMANT.
- [ ] **Step 6:** Update `model_card.json` artifact paths to the regenerated bundle files; recompute + record bundle SHA256 list for the report.
- [ ] **Step 7: Commit** — `chore(results): regenerate self-contained platform bundles`.

## Task B5: Verify + cross-repo report + push + PR

- [ ] **Step 1 (gates):** `pytest -q && ruff check . && reuse lint && python scripts/check_repo.py && python scripts/validate_platform_artifacts.py && omnidocbench-rocm conformance . && python -m build && python -m pip check`.
- [ ] **Step 2 (grep sweep):** `git grep -n "95.46"`, `git grep -n "95.56"`, `git grep -n "artifacts are not yet generated"`, `git grep -n "directory is empty"`, `git grep -n "omnidocbench-amd"`, `git grep -n "<workspace>"`, `git grep -n "<eval-root>"`, `git grep -n '"scoring_config_path": "."'`, `git grep -n '"dataset_manifest_path": "."'`. Explain every residual (expected: historical 95.46-with-context, `<workspace>`/`<eval-root>` in docs/spike notes + redacted provenance source_*, omnidocbench-amd in CHANGELOG history).
- [ ] **Step 3 (report):** write the section-十 cross-repo report (starting state; 95.56 decision + formula proof; per-file changes; bundle file list + SHA256; provenance chain; cross-file consistency table; real test/conformance/validate-bundle output; remaining risks; PR links).
- [ ] **Step 4:** `git push -u origin fix/p1.1-evidence-consistency`; open PR to `AIwork4me/MinerU-ROCm`.
- [ ] **Step 5:** **Stop at community. Do NOT create `VERIFIED.yaml`.**

---

## Self-Review (spec coverage)

- P0.1-1 → A4; P0.1-2 → A4; P0.1-3 → A1+A2+A3; P0.1-4 → A1+A3; P0.1-5 → A2+A3; P0.1-6 → A3; P0.1-7 → A5; P0.1-8 → A6; P0.1-9 → A6. ✓
- P1.1-1 → B2; P1.1-2 → B1; P1.1-3 → B2; P1.1-4 → B3; P1.1-5 → B3; P1.1-6 → B3; P1.1-7 → B4; P1.1-8 → B2. ✓
- Registry cross-check → A6 + B4 validate-bundle. ✓
- Section 五.1 (95.56 recompute) → verified in spec; encoded in A5 `_recompute_overall` test. ✓
- Prohibitions → Global Constraints + each task's redact/reuse discipline. ✓

No placeholders. Type/param names consistent across A1→A3 (`copy_artifact`, `write_prediction_manifest`, `write_dataset_identity`, `committed_*` paths, migration kwargs). Execution order: A1→A7 then B1→B5; B4 requires platform installed editable.
