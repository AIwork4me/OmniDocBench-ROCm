# Self-contained artifacts + MinerU evidence consistency (P0.1 → P1.1)

**Date:** 2026-07-21
**Status:** Approved (design). Implementation plan follows; execution in the same engagement.
**Scope:** Cross-repo. Platform = `OmniDocBench-ROCm` (P0.1, 0.3.0 → 0.3.1). Model = `MinerU-ROCm` (P1.1).
**Branches:** `fix/p0.1-self-contained-artifacts` (platform, from `origin/main` @ `385cd40`); `fix/p1.1-evidence-consistency` (model, from `main` @ `bb4ad48`).

---

## 1. Problem

Everything that describes `mineru2.5`'s current Linux-ROCm result must tell the same story. Today it does not. Two layers of prior work left the model repo split-brain, and the platform's `publish` emits bundles that are not self-contained and not cross-checkable.

### 1.1 The score situation (verified, not asserted)

Target canonical result:

```
Model mineru2.5 | Backend vlm-vllm | Platform linux-rocm | OmniDocBench v1.6/v16
Dataset + scorer revision 2b161d0 | Overall 95.56
Text EditDist 0.0359 | Formula CDM 96.73 | Table TEDS 93.54 | Reading-order EditDist 0.1240
Pages 1651 | OK 1649 | Failed 2 | Fallback 0 | Badge community | Windows-HIP community-wanted
```

**Overall formula** (recorded in `reproducibility.lock.yaml`):

```
Overall = ((1 - text_EditDist) * 100 + formula_CDM * 100 + table_TEDS * 100) / 3
aggregation = page.ALL ; match = quick_match
reading_order EditDist is reported separately and is NOT part of Overall
```

**Recompute check** from the committed v16 CDM `readme_metrics`
(text 0.035888688, CDM 0.967312299, TEDS 0.935391196):

```
(96.411113 + 96.731230 + 93.539120) / 3 = 286.681463 / 3 = 95.560488 ≈ 95.56  ✓
```

**95.46 vs 95.56 — same predictions, CDM submetric differs.** Both derive from the
same 1651-prediction set at `/root/ocr-eval/mineru-vlm-vllm-preds` (commit `b75f788`,
2026-07-19; run_manifest: 1651 attempted / 1649 complete / 2 empty). The entire
+0.10 pp delta is **Formula CDM 96.46 → 96.73**. The 95.56 CDM run is valid
(`metric_quality.formula_cdm.valid:true`, sample_count 2352, exception_case_count 0).
So:

- **95.56** = current OmniDocBench-ROCm platform CDM-scored result (canonical).
- **95.46** = prior standalone score (same predictions, older CDM configuration). Retained as historical, not deleted.

### 1.2 Split-brain in MinerU-ROCm

- **95.56-primary** (2026-07-21 P1 CDM work): `model_card.json`, `reproducibility.lock.yaml`, platform `hub/registry.yaml`, v16 CDM artifact bundle, README results table, README.zh-CN results table.
- **95.46-primary** (2026-07-20 upstream-PR-readiness demotion): README badge + headline, README.zh-CN badge, `docs/reproducibility.md`, `docs/how-it-works.md`, `docs/benchmark-methodology.md`, `CHANGELOG.md`, and `check_repo.py`'s inverted gate (`_STALE="95.56"`, `_CURRENT="95.46"`).

### 1.3 Confirmed defects

**Platform (`origin/main` @ 0.3.0):**

| ID | Defect | Evidence |
|----|--------|----------|
| P0.1-1 | standalone `publish` has no `--backend`; mismatch gate only wired into `run` | `cli.py` publish subparser + dispatch omit `requested_backend`; gate exists in `stage_publish` |
| P0.1-2 | `run --stage publish` guesses `metric_path = predictions.parent/"metric_result.json"`; no `--metric-result` | `cli.py:78` |
| P0.1-3 | `stage_publish` writes only run_summary+provenance; no metric/run_stats copied in; bundle paths point to `<workspace>`/`<eval-root>` | `stages.py:108-120`; committed run_summary/provenance |
| P0.1-4 | no prediction manifest | absent in `results/v16/linux-rocm/` |
| P0.1-5 | provenance `git_commit` = migration commit, not prediction commit; no packaging/prediction-source split | committed provenance `git_commit=f245e7e` vs lock `vlm_vllm=b75f788` |
| P0.1-6 | `scoring_config_path:"."`, `dataset_manifest_path:"."`; no dataset identity / GT sha | 4 provenance files |
| P0.1-7 | no cross-artifact `validate-bundle` | absent |
| P0.1-8 | README overstates registry/CDM status ("no onboarded models", "Linux CDM is a stub") | README + docs |
| P0.1-9 | template `REVISION ?= v1.6`; no CDM/RESUME toggles | `template/…/Makefile:3` |

**Model (`main` @ `bb4ad48`):**

| ID | Defect | Evidence |
|----|--------|----------|
| P1.1-1 | README badge + headline = 95.46 (should be 95.56-primary) | `README.md:11,20`; `README.zh-CN.md:9` |
| P1.1-2 | `check_repo.py` hardcodes inverted score gate | `check_repo.py:130-143` |
| P1.1-3 | `results/v16/linux-rocm/README.md` + `README.md:170` claim "not yet generated / directory is empty" | stale vs real artifacts present |
| P1.1-4 | `platform = ["omnidocbench-rocm>=0.2.0"]` | `pyproject.toml:36` |
| P1.1-5 | Makefile `eval-mineru2.5-linux` hardcodes `--skip-existing`, no `--cdm`, no toggles | `Makefile:41-54` |
| P1.1-6 | CI runs only check_repo + pytest; no conformance, no artifact validation | `.github/workflows/ci.yml` |
| P1.1-7 | `adapter_command` incomplete (missing `--img-dir`/`--out-dir`) | committed provenance |
| P1.1-8 | `model_card.artifacts.metric_result` points at non-CDM file while provenance/summary are CDM | `model_card.json:31` |

### 1.4 Already correct (do not redo)

- `REVISION ?= 2b161d0` in MinerU Makefile; platform `origin/main` already has mineru2.5@95.56 in `hub/registry.yaml`; v0.3.0 `publish` already requires `--predictions-dir`; `stage_publish` already has the `requested_backend` mismatch gate; `validate_registry.py` structural checks; full 1651-prediction set + `_run_stats.json` survive at `/root/ocr-eval/mineru-vlm-vllm-preds`; legacy `run_manifest.json` records the real prediction commit `b75f788`.

---

## 2. Approach decisions

**A. Reuse the existing valid CDM metric; do not re-score.** The committed CDM `metric_result.json` recomputes to 95.56 with valid CDM. Re-publish it through hardened tooling. The prediction manifest is generated fresh from the real 1649 non-empty files. No re-inference, no re-scoring, no synthesis.

**B. `validate-bundle` is an engine subcommand.** `omnidocbench-rocm validate-bundle <dir> [--model-card …] [--registry …]` in a new `bundle_validator.py`, beside `conformance`. The model repo calls it via a thin `scripts/validate_platform_artifacts.py`. The engine owns the artifact contract; the validator lives with it.

**C. README registry table = CI consistency check.** Assert the platform README registry block matches `render_table(hub/registry.yaml)`. Lighter than auto-injecting markdown; still eliminates the dual source of truth. `generate_registry.py` remains the canonical renderer.

**D. Full 1649-entry prediction manifest.** Deterministic (sorted, sha256, size_bytes), non-empty `.md` only, plus `failed_pages[]`. ~150 KB, committable.

**E. Source-path redaction stays model-side.** The platform writes real paths; MinerU's `scripts/redact_internal.py` (run post-publish) rewrites `/root/ocr-eval`→`<eval-root>`, `/workspace/`→`<workspace>/`, IP/hostname/venv. Repo-relative committed-copy paths are untouched; runtime `source_*` paths redact automatically.

---

## 3. Platform design (OmniDocBench-ROCm, 0.3.0 → 0.3.1)

### 3.1 CLI (`cli.py`)
- `publish` subparser: add `--backend` (default `""`); dispatch passes `requested_backend=a.backend`.
- `run` subparser: add `--metric-result` (default `""`); `--stage publish` requires it → `SystemExit("run --stage publish requires --metric-result")`. Remove the `predictions.parent/"metric_result.json"` guess. `--stage all` keeps using `stage_score()` return; infer/score/download ignore it.
- `publish` + `run`: add `--prediction-source-commit`, `--prediction-source-command`, `--prediction-source-run-manifest`, `--migration-type`.

### 3.2 `artifact_utils.py`
- `copy_artifact(*, source, destination) -> Path`: source must exist (else raise), `destination.parent.mkdir(parents=True, exist_ok=True)`, `shutil.copyfile`, return destination. Replaces ad-hoc `copy_metric_report`.
- `write_prediction_manifest(*, predictions_dir, destination, model_id, platform, backend, run_stats) -> Path`:
  ```json
  {
    "schema_version": 1,
    "model_id": "mineru2.5", "platform": "linux-rocm", "backend": "vlm-vllm",
    "prediction_count": 1649, "expected_page_count": 1651, "failed_page_count": 2,
    "source_prediction_dir": "<redacted>", "hash_algorithm": "sha256",
    "files": [{"relative_path": "page_xxx.md", "sha256": "…", "size_bytes": 1234}],
    "failed_pages": [{"relative_path": "…", "reason": "empty prediction"}]
  }
  ```
  Only non-empty `.md`; sorted by `relative_path`; deterministic.
- `write_dataset_identity(...)`: minimal `{schema_version, dataset:"OmniDocBench", version:"v1.6", revision, ground_truth_file:"OmniDocBench.json", ground_truth_sha256}` when no manifest file is supplied.
- `write_run_summary` / `write_provenance`: accept committed (repo-relative) artifact paths as the primary `*_path(s)` fields; add optional `source_metric_result_path`, `source_run_stats_path`, `source_prediction_dir`. Provenance gains optional `packaging_commit`, `prediction_source_commit`, `prediction_source_command`, `prediction_source_run_manifest`, `prediction_manifest_path`, `prediction_manifest_sha256`, `migration_type`, `dataset_identity_path`, `scoring_config_path` (real).

### 3.3 `stage_publish` self-contained bundle
Sequence:
1. `_assert_full_set` + backend gate (unchanged).
2. Compute `save_name` (CDM suffix → clobber-safe).
3. `copy_artifact` metric_result → `<save_name>_metric_result.json`; run_stats → `<save_name>_run_stats.json`.
4. Copy scoring config → `<save_name>_scoring_config.yaml` (when provided); reject `"."`.
5. Emit dataset identity (copy real manifest or synthesize) → `<save_name>_dataset_identity.json`; reject `"."` for `dataset_manifest_path` (synthesize instead).
6. `write_prediction_manifest` → `<save_name>_prediction_manifest.json`.
7. `write_run_summary` / `write_provenance` referencing the **committed copies** (repo-relative) + `source_*` runtime paths.
8. Reject `scoring_config_path == "."` and `dataset_manifest_path == "."`.

### 3.4 Schema (`contracts/artifact-schema.json`)
- Add the new optional provenance properties (no change to `required` → non-breaking; `additionalProperties` already unset).

### 3.5 `bundle_validator.py` + `validate-bundle` CLI
Checks (each a test):
- `model_card.model_id` == save_name-implied model id; `provenance.model_id` == model_card.
- `provenance.platform` == target; `provenance.backend` == `run_summary.engine`.
- `run_summary.prediction_count` == `provenance.page_count`; ok+fail+fallback == page_count.
- prediction manifest count == ok pages; manifest `failed_page_count` == failed pages.
- dataset revision consistent across provenance/identity/lock.
- metric_result + run_stats files present and resolvable within bundle.
- all `*_path(s)` in run_summary/provenance resolve (committed copies).
- CDM bundle `cdm==true`; non-CDM `cdm==false`.
- **Overall recompute**: from metric_result via the documented formula == model_card `overall` == registry `overall` (within rounding).

### 3.6 Docs + template
- README: registry block reflects reality (mineru2.5 community 95.56; paddleocr community 95.77; unlimited/hunyuan community-wanted). CDM status: "implemented and exercised by community runs; verified-Docker reproduction remains the promotion path; Windows-native CDM planned." Remove "stub" / "no onboarded models".
- Sync `docs/architecture.md`, `docs/roadmap.md`, `docs/ci-reality.md`.
- Template `Makefile`: `REVISION ?= 2b161d0`; add `CDM ?= 1`, `RESUME ?= 0`, `CDM_FLAG`, `RESUME_FLAG`; eval targets use them.
- `pyproject.toml` → `0.3.1`; CHANGELOG; CITATION.

### 3.7 Registry cross-check
- `validate_registry.py` (extend) or new check: registry overall == model_card overall; badge ==; model_id ==; repo == expected. Reject drift. (Cross-repo: the model card lives in MinerU; the check takes `--model-card`.)

---

## 4. Model design (MinerU-ROCm)

### 4.1 Unify 95.56-primary
- README badge + headline + table; README.zh-CN. `model_card.artifacts.metric_result` → **CDM** file (fix cdm/non-cdm mismatch).
- 95.46 only as: `Prior standalone: 95.46 / Current platform CDM: 95.56 / Δ +0.10 pp`, with the same-predictions/CDM-delta explanation.

### 4.2 Data-driven gate
- Delete `_STALE/_CURRENT_VLM_OVERALL`. Read current overall from `lock.benchmark.full_1651.vlm_vllm.overall`.
- Assert README headline == lock; README.zh-CN == lock; model_card == lock; run_summary metrics == lock; registry == model_card.

### 4.3 Stale-claim purge
- `results/v16/linux-rocm/README.md`, `README.md:170`, `docs/known-gaps.md`, `docs/reproducibility.md`, `CHANGELOG.md`: "Platform-standard artifacts generated 2026-07-21. Canonical bundle in `results/omnidocbench/v16/linux-rocm/`. Legacy `results/omnidocbench/v1.6/` retained for historical comparison + prediction-source provenance."

### 4.4 Build + CI
- `platform = ["omnidocbench-rocm>=0.3.1,<0.4"]`.
- Makefile: `CDM ?= 1`/`RESUME ?= 0` flags; `eval-mineru2.5-linux` uses `$(CDM_FLAG) $(RESUME_FLAG)`; drop unconditional `--skip-existing`.
- CI: split `core` (pytest, ruff, reuse, check_repo, build, pip check) + `platform-contract` (install pinned `omnidocbench-rocm>=0.3.1,<0.4` — from PyPI when shipped, else `git+…@<P0.1 pin>`; `omnidocbench-rocm conformance .`; `scripts/validate_platform_artifacts.py`).

### 4.5 Regenerate bundle (mineru2.5 + pipeline)
- `publish` from `/root/ocr-eval/mineru-vlm-vllm-preds` + existing CDM metric with `--backend vlm-vllm`, `--prediction-source-commit b75f788…`, `--prediction-source-run-manifest results/omnidocbench/v1.6/vlm-vllm/run_manifest.json`, `--migration-type legacy_predictions_to_platform_artifacts`, full `adapter_command`. Then `redact_internal.py`.
- Pipeline stays supplementary (not in registry), same bundle standard, license-risk note retained.

---

## 5. Execution order + verification gates

1. **Platform P0.1**: implement (TDD) → `pytest -q`, `check_brand.py`, `validate_registry.py`, `generate_registry.py`, `python -m build`, `pip check` → layered commits → push → PR.
2. Install platform editable → **MinerU P1.1**: implement → re-publish bundle from existing preds → `pytest -q`, `ruff`, `reuse lint`, `check_repo.py`, `validate_platform_artifacts.py`, `omnidocbench-rocm conformance .`, `validate-bundle …`, `build`, `pip check` → required `git grep` sweep (every residual 95.46/95.56/`<workspace>`/`"."` explained) → layered commits → push → PR.
3. **Cross-repo report** (section 十 format): starting state; 95.56 decision + formula proof; per-file changes; bundle file list + SHA256; provenance chain (prediction `b75f788` vs packaging commit vs scoring vs dataset rev `2b161d0`); cross-file consistency table; real test/conformance/validate-bundle output; remaining risks; PR links. **Stop at community; no `VERIFIED.yaml`.**

## 6. Commit layering (no squash)

- Platform: `fix(cli)` → `feat(publish)` → `feat(provenance)` → `feat(validation)` → `docs` → `test`.
- Model: `fix(results)` → `fix(docs)` → `fix(gates)` → `build` → `ci` → `chore(results)`.

## 7. Prohibitions (carried from the task)

No forged artifacts; no hand-written `_run_stats.json`; no manifest from sample predictions; no passing off the migration commit as the prediction commit; no silent deletion of 95.46; no calling 95.56 a new inference result; no registry-as-truth; no formula tweaks to hit a target; no lowering the empty-output failure bar; no restoring unconditional `--skip-existing`; no pipeline in registry; no Windows-HIP = community; no removing the license note; no floating-`main` CI dep; no empty placeholder files to pass conformance; no real IPs/hostnames/usernames/absolute private paths in provenance.

## 8. Risks

- The 95.46→95.56 reversal overturns a *deliberate* 2026-07-20 demotion. Justified by: same predictions, CDM 96.46→96.73, recomputes to 95.56. CHANGELOG must state the reversal explicitly (auditable, not silent).
- Legacy run_manifest command is minimal (`mineru-rocm predict vlm-vllm`); record the fullest known form and mark clearly rather than fabricate flags.
- Windows-HIP results dir must satisfy conformance's non-empty check without fake artifacts — verify its state during implementation.
