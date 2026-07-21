# P1 Migration Playbook

Canonical step-by-step workflow for migrating a per-model repository to the
OmniDocBench-ROCm platform contract. Proven on MinerU-ROCm.

---

## Phase 0: Assessment

```bash
cd <model-repo>

# 1. Audit current state
git grep -n -i -e "omnidocbench-amd" -e "OmniDocBench-AMD" -e "omnidocbench_amd" \
  ':!docs/superpowers/' ':!*.pyc' | wc -l   # target: 0 (unexplained)

# 2. Verify claims in spec
# - pyproject.toml depends on old platform?
# - Makefile calls old CLI?
# - model_card declares platforms with no results?
# - adapter handles empty predictions? skip-existing semantics?
# - README has 5 conformance sections? Honest status?

# 3. Run baseline conformance
omnidocbench-rocm conformance .     # note all failures
```

---

## Phase 1: Platform Name Migration

```bash
# Bulk rename across all source files (NOT docs/superpowers or CHANGELOG)
# Pattern:  omnidocbench-amd  →  omnidocbench-rocm
#           OmniDocBench-AMD   →  OmniDocBench-ROCm
#           omnidocbench_amd   →  omnidocbench_rocm

# Key files to update:
# - pyproject.toml:   platform = ["omnidocbench-rocm>=0.2.0"]
# - Makefile:         omnidocbench-rocm conformance .
# - README.md / README.zh-CN.md
# - adapter/run_adapter.py  (docstring)
# - scripts/check_repo.py:  ENGINE_MODULES tuple
# - .github/workflows/ci.yml
# - CONTRIBUTING.md, NOTICE, docs/*.md
```

**Rules:**
- CHANGELOG entries are historical — add migration note, keep old names
- `docs/superpowers/` design records — leave unchanged
- Archive results — mark as "historical name for omnidocbench-rocm"

---

## Phase 2: Adapter Contract Hardening

The platform template (`omnidocbench-rocm/template`) implements the basic contract.
Add these mandatory improvements:

### 2.1 Empty prediction → failure
```python
# After inference, before write:
if not isinstance(md, str):
    raise TypeError(f"prediction is not a string (got {type(md).__name__})")
if not md.strip():
    raise RuntimeError("empty prediction")
```

### 2.2 Skip-existing with content validation
```python
if skip_existing and out_md.exists():
    existing = out_md.read_text(encoding="utf-8")
    if not existing.strip():
        stats.append(PageStatus(img.name, "failed: existing prediction is empty", ...))
        continue
    stats.append(PageStatus(img.name, "ok", seconds=0.0, attempts=0))
    resumed_existing += 1
    continue
```

### 2.3 Conservation check (before writing)
```python
if ok + fail + fallback != count:
    raise RuntimeError(f"stats conservation violation: ok={ok} fail={fail} ...")
if len(stats) != count:
    raise RuntimeError(f"stats length mismatch")
```

### 2.4 Cleanup on failure
```python
except Exception:
    if out_md.exists():
        out_md.unlink()   # don't leave empty/corrupt .md files
```

---

## Phase 3: Model Cards

- `platforms[]`: only platforms with actual results
- `badge.<platform>`: `community` if results exist, `community-wanted` if not
- `artifacts`: point at actual files, not placeholders
- Multi-model-card repos: the canonical card is `model_card.json`; extras need `note` field

---

## Phase 4: README

Both `README.md` and `README.zh-CN.md` must contain these headers:
- **Install** — how to install
- **Demo** — one-command smoke demo
- **Evaluation** — exact platform CLI commands with backend/server_url/api_model_name
- **Reproducibility** — hardware, driver, commit, artifact locations
- **Known Gaps** — limitations, missing platforms, empty outputs

**Honesty rules:**
- Setup scripts are stubs? Say so.
- Conformance not yet tested? Say so.
- VLM has 2 empty outputs? Say so.
- Windows-hip is community-wanted? Say so.

---

## Phase 5: Makefile

Required targets:
```
setup-linux / setup-windows    # provisioning
demo                           # smoke contract test
smoke-test                     # pytest
eval-<model>-linux             # platform evaluation
conformance                    # omnidocbench-rocm conformance .
```

---

## Phase 6: Results Directory

```bash
mkdir -p results/omnidocbench/v16/linux-rocm/
# Add README explaining platform-standard artifacts location
# NO fake artifacts — leave empty until score/publish runs
```

---

## Phase 7: Tests

Use `tests/test_dispatcher_contract.py` from MinerU-ROCm as template.
Required test categories:

1. Empty prediction (5 tests): empty string, whitespace, non-string, no file left, run continues
2. Skip-existing (5 tests): non-empty=ok, conservation, empty=fail, every page in stats, mixed scenario
3. Conservation (2 tests): ok+fail+fallback==count, len(stats)==count
4. CLI/backend selection (5 tests): smoke/pipeline/vllm selection, unknown backend error
5. Platform integration (3 tests): pyproject declares platform, Makefile uses platform, no legacy refs

---

## Phase 8: Score + Publish

### 8.1 Generate _run_stats.json from existing predictions
```bash
python scripts/generate_run_stats.py \
  --gt-json <OmniDocBench.json> \
  --predictions-dir <preds-dir> \
  --engine <backend-name>
```

### 8.2 Run platform scoring
```bash
OMNIDOCBENCH_CHECKOUT=<path> \
omnidocbench-rocm score \
  --platform linux-rocm \
  --predictions-dir <preds-dir> \
  --version v16 \
  --cdm \
  --run-stats <preds-dir>/_run_stats.json \
  --dataset-dir <dataset-dir>
```

### 8.3 Run platform publish
```bash
omnidocbench-rocm publish \
  --model-id <model-id> \
  --platform linux-rocm \
  --version v16 \
  --cdm \
  --run-stats <preds-dir>/_run_stats.json \
  --metric-result <metric_result.json> \
  --results-dir results/omnidocbench/v16/linux-rocm \
  --predictions-dir <preds-dir> \
  --git-commit "$(git rev-parse HEAD)" \
  --adapter-command "python adapter/run_adapter.py --backend <backend> --platform linux-rocm" \
  --dataset-revision 2b161d0
```

### 8.4 Redact internal paths
```bash
python scripts/redact_internal.py
```

---

## Phase 9: Verify + Push

```bash
omnidocbench-rocm conformance .     # must be CONFORMANT
python scripts/check_repo.py        # must be clean
pytest tests/ -q                    # all pass
git push origin feat/p1-migration   # push to branch
gh pr create ...                    # create PR
gh pr merge ...                     # merge
```

---

## Phase 10: Registry

Update `hub/registry.yaml` in the OmniDocBench-ROCm platform repo:
```yaml
- model_id: <model-id>
  platforms:
    linux-rocm: {badge: community, overall: <score>}
    windows-hip: {badge: community-wanted, overall: null}
```

Separate PR to the platform repo.

---

## Troubleshooting

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| CDM score timeout | `apt-get` tries unreachable repos | Skip `cdm setup` if toolchain installed; run `score --cdm` directly |
| `check_repo` leaks internal paths | Absolute paths in JSON artifacts | Run `scripts/redact_internal.py` |
| Push rejected (main) | Branch protection | Push to feature branch, create PR |
| `stale info` on push | Tracking ref mismatch | `git fetch origin main:refs/remotes/origin/main` then push |
