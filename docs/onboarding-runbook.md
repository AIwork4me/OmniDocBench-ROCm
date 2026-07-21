# Onboarding runbook: from provisioned to a `verified` flagship entry

This is the procedure that takes a per-model repo from "the box is
provisioned" to a **`verified` flagship entry** in
[`hub/registry.yaml`](../hub/registry.yaml). It is the canonical sequence a
contributor or maintainer follows for any model on Linux/ROCm. The worked
example throughout is **PaddleOCR-VL** (the first v1 model), but the steps are
model-agnostic.

> **Success definition.** This runbook's终点 is a **`verified`** entry in the
> registry — a maintainer Docker reproduction of the committed `overall` score
> within tolerance, recorded in a committed `VERIFIED.yaml`. A `community`
> entry is the **step-6 checkpoint**, not the finish line.

> **What is gated, not scripted.** Two steps are **resumable gated execution**,
> not minute-by-minute scripted commands in this runbook:
>
> - **Step 2** — the full 1651-page adapter run is a gated GPU job. The
>   runbook makes it *ready* (serving + adapter contract); the actual run is
>   resumable background work.
> - **Step 7** — the maintainer Docker reproduction runs on a Docker-capable
>   box (Docker is absent in the dev env). The runbook makes it *ready*
>   (`Dockerfile.repro` + `check_verified.py`); the reproduction itself is the
>   final gate.
>
> Both are called out explicitly where they occur. Do not treat their absence
> of a one-liner here as a gap — they are inherently multi-hour, resumable
> jobs.

> **Prerequisites out of scope here.** This runbook references the model's
> **adapter** (`adapter/run_adapter.py`) and **serving** (e.g. PaddleOCR-VL on
> vLLM/ROCm) as prerequisites — they must exist before Step 2. The
> PaddleOCR-VL adapter + its vLLM/ROCm serving land in a **follow-on spec**
> (`PaddleOCR-VL-ROCm`); this runbook does not build them. See
> [`contracts/adapter.md`](../contracts/adapter.md) for the contract the
> adapter implements.

---

## The seven steps at a glance

| # | Step | Gate / output | Gated? |
|---|------|---------------|--------|
| 1 | Pin revision + provision 3.11 eval-venv | eval-venv ready | no |
| 2 | Run the adapter over the full 1651-page set | `predictions/` + `_run_stats.json` | **resumable GPU job** |
| 3 | Score Edit_dist + TEDS on host | `metric_result.json` | no |
| 4 | Provision CDM + score CDM on host (via `.venv`) | CDM in `metric_result.json` | no |
| 5 | Publish (full-set enforced) | `run_summary.json` + `provenance.json` | no |
| 6 | Conformance + community | `hub/registry.yaml` → `community` | no (checkpoint, not终点) |
| 7 | Maintainer Docker reproduction (Edit_dist + TEDS **+ CDM**) → verified | `VERIFIED.yaml` + `verified` badge | **Docker-box gate** |

---

## Step 1 — Pin revision + provision the 3.11 eval-venv

Pin the OmniDocBench dataset download to the engine's pinned v1.6 ref so the
**dataset and the scorer stay aligned** (the scorer is checked out at the same
commit). The pinned ref lives in
[`engine/omnidocbench_rocm/_refs.py`](../engine/omnidocbench_rocm/_refs.py)
(``OMNIDOCBENCH_V16_REF = "2b161d0"``) and the engine refuses an unpinned
(`None`) revision. Then provision the box:

```bash
# Pin the dataset download to the engine's pinned ref.
omnidocbench-rocm dataset download --version v16 --revision 2b161d0

# Provision the Python 3.11 eval-venv (OmniDocBench breaks on 3.12).
make setup-linux
```

`make setup-linux` runs
[`engine/omnidocbench_rocm/evalenv/setup-linux.sh`](../engine/omnidocbench_rocm/evalenv/setup-linux.sh),
which creates the 3.11 eval-venv at
`$OMNIDOCBENCH_ROCM_DATA/eval-venv/linux-rocm`, installs the pinned OmniDocBench
scorer into it, and is idempotent (re-running prints `already present`).
**Verify:** `$OMNIDOCBENCH_ROCM_DATA/eval-venv/linux-rocm/bin/python --version`
reports `3.11.x`. See [`pitfalls.md`](pitfalls.md#python-version) for why 3.11.

---

## Step 2 — Run the adapter over the full 1651-page set (gated GPU job)

> **This step is a resumable gated GPU job, not a one-liner.** It requires the
> model **served** (e.g. PaddleOCR-VL on vLLM/ROCm) and the model's
> **adapter** (`adapter/run_adapter.py`) ported to the
> [adapter contract](../contracts/adapter.md). The PaddleOCR-VL adapter +
> serving land in a follow-on spec; this runbook treats them as prerequisites.

Once served and the adapter is in place, run it over the **full, unbounded**
1651-page image set. The adapter is invoked as a subprocess and writes one
Markdown file per page plus a `_run_stats.json`:

```bash
# From the per-model repo (e.g. PaddleOCR-VL-ROCm). Resumable — re-running
# skips pages whose .md already exists; per-page failures score zero and the
# run continues (see contracts/adapter.md).
python adapter/run_adapter.py \
  --img-dir <dataset>/images \
  --out-dir predictions/<model> \
  --platform linux-rocm
```

**Hard requirement for any downstream badge:** `_run_stats.json` must record
`limit_pages: null` (the full set). The engine **refuses to publish** official
evidence from a limited subset (see Step 5). Do not pass any `--limit-pages`
flag for a scored run; use it only for smoke tests.

**Verify:** `ls predictions/<model>/*.md | wc -l` is `1651`, and
`predictions/<model>/_run_stats.json` exists with `"limit_pages": null`.

---

## Step 3 — Score Edit_dist + TEDS (no CDM first pass)

Score the predictions without CDM first — Edit_dist and TEDS do not need the
CDM toolchain, so this is the fastest signal that the adapter output is sane:

```bash
omnidocbench-rocm score \
  --platform linux-rocm \
  --predictions-dir predictions/<model> \
  --version v16 \
  --run-stats predictions/<model>/_run_stats.json \
  --dataset-dir <dataset>
```

This renders the scoring config, runs `pdf_validation.py` inside the eval-venv
(3.11), and writes `metric_result.json`. CDM is **omitted** in this pass (no
`--cdm`), so the CDM-sensitive toolchain (TeX Live / ImageMagick 7 /
Ghostscript) is not exercised yet — isolate Edit_dist/TEDS first.

**Verify:** `metric_result.json` exists and `overall` is a plausible number
(not `0.0` — a zero here means the adapter produced no usable predictions; see
[`pitfalls.md #layout`](pitfalls.md#layout) / [`#vlm`](pitfalls.md#vlm)).

---

## Step 4 — Provision CDM + score CDM on host

CDM (Consistent Distance Metric) is the hardest, highest-value metric; it
compiles each formula to a color-coded PDF, rasterizes to PNG, and color-matches
bounding boxes. **CDM works on the host** — verified: the engine produces real
CDM scores (e.g., CDM 0.3012 on 10 formula pages, 0 exceptions).

### Key requirement: use the OmniDocBench checkout's `.venv`

CDM uses `multiprocessing.Pool(200)` for parallel formula rendering. A
separately-created venv may break CDM workers ("AssertionError: can only join a
started process"). The checkout's `.venv` is the known-working scorer venv.
`make setup-linux` (via `evalenv/setup-linux.sh`) detects + symlinks it
automatically.

### Provision + score

```bash
make provision-cdm      # installs IM7 (not IM6); runs cdm/setup-linux.sh
omnidocbench-rocm score --platform linux-rocm --cdm \
  --predictions-dir predictions/<model> --version v16 \
  --run-stats predictions/<model>/_run_stats.json --dataset-dir <dataset>
```

### CDM result keys

In `metric_result.json`, CDM is at:
- `display_formula.page.CDM.ALL` (page-level average — the headline CDM number)
- `display_formula.all.CDM.all` (sample-level average)
- `display_formula.metric_debug.CDM.exception_case_count` (should be 0)

NOT `ALL_page_avg` (that key is Edit_dist-specific).

**On `#cdm-zero` (all-exception / null result).** If CDM is `None`/all-exception,
it is recorded as **`pending`/null — never a faked number.** Walk the
[`#cdm-zero`](pitfalls.md#cdm-zero) decision tree, re-run, and re-score.

---

## Step 5 — Publish (full-set enforced)

Assemble the `run_summary.json` + `provenance.json` artifacts. Standalone
`publish` **requires `--predictions-dir`** — it needs the real predictions
directory to record in provenance and to read `_run_stats.json` from:

```bash
omnidocbench-rocm publish \
  --model-id <model-id> \
  --platform linux-rocm \
  --predictions-dir predictions/<model> \
  --version v16 \
  --run-stats predictions/<model>/_run_stats.json \
  --metric-result <metric_result.json> \
  --results-dir results/omnidocbench/v16/linux-rocm \
  --git-commit $(git -C <model-repo> rev-parse HEAD) \
  --adapter-command "<the command that launched the adapter>" \
  --dataset-revision 2b161d0
```

> **Migration note.** Earlier versions of this runbook omitted
> `--predictions-dir` from `publish`. It is now **required** when invoking
> `publish` standalone: the engine records the real predictions directory in
> `provenance.json` and reads `_run_stats.json` from it. (When you use
> `run --stage all` instead — see below — the engine threads the inference
> config's predictions dir through both stages for you.)

### Or, in one shot

If you would rather run inference + scoring + publish in a single command,
`run --stage all` threads one inference config into both `infer` and `publish`.
For a server-served VLM (e.g. a MinerU2.5-class VLM on vLLM/ROCm), forward the
backend/server flags so the adapter knows where to call:

```bash
omnidocbench-rocm run --stage all --platform linux-rocm --version v16 --revision 2b161d0 \
  --adapter adapter/run_adapter.py --model-id <model-id> \
  --backend vlm-vllm --server-url http://127.0.0.1:8000/v1 --api-model-name <model-name> \
  --git-commit $(git rev-parse HEAD) --results-dir results/omnidocbench/v16/linux-rocm
```

The same `--backend`/`--server-url`/`--api-model-name` flow into the adapter's
`config` dict during `infer`; `publish` then records the **adapter-reported**
backend (from `_run_stats.json["engine"]`) into provenance and refuses to
publish if it disagrees with the `--backend` you requested.

**Full-set enforcement:** `stage_publish` calls `_assert_full_set`, which reads
`_run_stats.json` and refuses with a `SystemExit` if `limit_pages` is not
`null`. A subset run cannot become official evidence. See
[`architecture.md`](architecture.md#the-engine-four-stages) ("publish" row).

**Verify:** `results/omnidocbench/v16/linux-rocm/` contains
`<save_name>_run_summary.json` and `<save_name>_provenance.json`, both
schema-valid (checked by `check_conformance` in Step 6).

---

## Step 6 — Conformance + `community` (checkpoint, not终点)

Run the conformance checker against the per-model repo:

```bash
omnidocbench-rocm conformance <model-repo>
#   -> prints CONFORMANT (exit 0) or NON-CONFORMANT with the failure list
```

`check_repo` enforces the eight checks in
[`contracts/conformance.md`](../contracts/conformance.md) (adapter exists, config exists,
results dir non-empty, bilingual READMEs with the five required sections,
`examples/`, `pyproject.toml` depending on `omnidocbench-rocm`, valid
`model_card.json`). Fix every failure until it prints `CONFORMANT`.

Then update [`hub/registry.yaml`](../hub/registry.yaml): set the model's
`linux-rocm` entry to `community` with the measured `overall`:

```yaml
- model_id: paddleocr-vl-1.6
  repo: AIwork4me/PaddleOCR-VL-ROCm
  platforms:
    linux-rocm: {badge: community, overall: <measured>}
    windows-hip: {badge: community-wanted, overall: null}
```

> **This is the `community` checkpoint.** Provenance-complete and conformant,
> but not yet maintainer-reproduced. It is a real, citable result — but the
> runbook is not done. The终点 is Step 7.

**Verify:** `omnidocbench-rocm conformance` prints `CONFORMANT`;
`registry.yaml` parses (`scripts/validate_registry.py`).

---

## Step 7 — Maintainer Docker reproduction → `verified` (the终点)

> **This step is the Docker-box gate.** It runs on a Docker-capable box
> (Docker is absent in the dev env). The runbook makes it *ready* —
> `Dockerfile.repro`, `make repro-score`, `scripts/check_verified.py`,
> `VERIFIED.yaml` — but the reproduction itself is the final gate. **This is
> the runbook's success definition.**

The Docker path pins the CDM-sensitive toolchain so a `verified` reproduction
is deterministic. It reproduces **scoring** (Edit_dist + TEDS + CDM) from
committed predictions — not inference (inference is deterministic given the
committed model + weights; the toolchain versions are the reproducibility
risk).

### 7a. Build the reproducible image

On a Docker-capable box, build the engine wheel and the image, pinning the
scorer to the same ref as the dataset:

```bash
python -m build     # produces dist/omnidocbench_rocm-0.3.0-py3-none-any.whl
docker build \
  --build-arg OMNIDOCBENCH_REF=2b161d0 \
  -t omnidocbench-rocm-repro:0.3.0 \
  -f engine/omnidocbench_rocm/docker/Dockerfile.repro .
```

`OMNIDOCBENCH_REF` **must** match `OMNIDOCBENCH_V16_REF` (`2b161d0`) so the
scorer in the image is the same commit that produced the committed predictions.

### 7b. Run the reproduction from committed predictions

Either follow [`engine/omnidocbench_rocm/docker/README.md`](../engine/omnidocbench_rocm/docker/README.md)
directly, or run `make repro-score` (which prints the exact `docker run` to
copy). Mount the committed predictions and ground truth:

```bash
docker run --rm \
  -v "$PREDICTIONS":/preds \
  -v "$GT/OmniDocBench.json":/gt/OmniDocBench.json \
  omnidocbench-rocm-repro:0.3.0 \
  score --platform linux-rocm --predictions-dir /preds --version v16 \
        --run-stats /preds/_run_stats.json --dataset-dir /gt
```

### 7c. Record + tolerance-check `VERIFIED.yaml`

Write a `VERIFIED.yaml` at the model-repo root (shape in
[`contracts/badge-policy.md`](../contracts/badge-policy.md)) and run the
tolerance gate (|delta| ≤ 0.5):

```bash
python scripts/check_verified.py VERIFIED.yaml
#   -> VERIFIED PASS: within tolerance: |<rep> - <com>| = <d> <= 0.5
```

### 7d. Promote the registry entry to `verified`

Update [`hub/registry.yaml`](../hub/registry.yaml):

```yaml
- model_id: paddleocr-vl-1.6
  repo: AIwork4me/PaddleOCR-VL-ROCm
  platforms:
    linux-rocm: {badge: verified, overall: <measured>}
    windows-hip: {badge: community-wanted, overall: null}
```

**Done.** A maintainer has reproduced the committed `overall` in a clean,
pinned Docker environment within tolerance, recorded in a committed
`VERIFIED.yaml`. This is the `verified` flagship entry — the runbook's
success definition.

---

## Where to look next

- The adapter contract you implement → [`contracts/adapter.md`](../contracts/adapter.md)
- Badge tiers + promotion → [`contracts/badge-policy.md`](../contracts/badge-policy.md)
- Conformance checklist → [`contracts/conformance.md`](../contracts/conformance.md)
- Why CDM is hard → [`pitfalls.md`](pitfalls.md) (the [`#cdm-zero`](pitfalls.md#cdm-zero) tree)
- How the engine fits together → [`architecture.md`](architecture.md)
- Adding a model (contributor guide) → [`contribute-a-model.md`](contribute-a-model.md)
