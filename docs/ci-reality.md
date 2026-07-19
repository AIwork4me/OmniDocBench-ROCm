# CI Reality

What continuous integration does and does not cover in this zone, and where
trust actually comes from. Read this before reading a badge and assuming "CI
passed" means "the result is real."

---

## The hard constraint: no native AMD GPU runner

GitHub Actions has **no native AMD GPU runner**. The hosted `ubuntu-latest`
and `windows-latest` runners are CPU-only. There is no equivalent of NVIDIA's
CUDA runner for ROCm or for the Ryzen AI MAX+ 395 (Strix Halo) iGPU. Spinning
up self-hosted GPU runners for every contributor PR is not feasible and would
not be reproducible across contributor hardware.

This is not a gap we plan to close with CI. It is a fundamental property of
the hardware, and the zone is designed around it.

---

## What CI runs (CPU-only, on every PR)

The platform repo's CI and each per-model repo's CI run on `ubuntu-latest`
(CPU). They cover the things that **can** be honestly checked without a GPU:

| CI check | What it asserts | Where |
|---|---|---|
| **Contract tests** | A fake adapter writes known `.md` → the engine scores it → the artifact schema validates + scores match expectations. Schema fixture positive/negative cases. `model_card.json` generate→validate round-trip. | platform repo `tests/` |
| **Template smoke** | `cookiecutter` renders a conformant repo; `make demo --backend smoke` produces a `.md`; `check-conformance` passes on structure (no GPU needed — the `smoke` backend is a no-GPU placeholder). | platform repo + per-model repo CI |
| **Conformance check** | `check_conformance.py` exits 0 on the per-model repo (required sections present, `pyproject.toml` depends on `omnidocbench-rocm`, results dirs non-empty, `model_card.json` schema-valid). | per-model repo CI |
| **Engine self-import** | `python -c "from omnidocbench_rocm.types import RunSummary"` — the engine is importable in a clean 3.11 env. | per-model repo CI |

These are the CPU-feasible parts of the test pyramid (spec §10). They catch
contract regressions, schema drift, and structural non-conformance. They do
**not** assert that any model actually runs or produces real scores.

---

## What CI does NOT run (GPU, maintainer-run)

Everything that needs an AMD GPU is **maintainer-run on real hardware**, not
in CI. These tests carry a `--gpu` mark (in the pytest sense) and are skipped
on CI runners:

| GPU test | What it asserts | Who runs it | When |
|---|---|---|---|
| **Engine self-test** | A 10-page subset end-to-end on `linux-rocm` (gfx1100): non-zero scores + valid artifacts. (`windows-hip` is planned/onboarding — not yet run.) | maintainer | pre-release |
| **Reference-model regression** | The 3 reference models (PaddleOCR-VL-1.6, Unlimited-OCR, MinerU2.5) each pin a `results/` baseline; `Overall` drift > 0.1 points triggers review. | maintainer | pre-release + on model-repo changes |
| **CDM validity test** | A small formula subset on both platforms must produce non-null valid CDM (catches the `#cdm-zero` failure mode). | maintainer | pre-release + on CDM toolchain changes |

These are the tests that actually validate a real eval. They are not in CI
because they cannot be — they need the hardware.

---

## So where does trust come from? Tiered badges

Because CI cannot prove a result is real, trust comes from the **tiered badge
model** ([`contracts/badge-policy.md`](../contracts/badge-policy.md)), not from
a green CI check:

```
community-wanted  --[submit platform results + pass conformance]-->  community
community         --[maintainer Docker reproduction + VERIFIED.yaml]-->  verified
```

| Badge | Meaning | What backs it |
|---|---|---|
| `community-wanted` | No results for this platform yet. | Nothing (default for an absent platform). |
| `community` | Provenance-complete + conformant, self-attested. | `check_conformance` passes (CI-checked) + committed `results/` bundle with schema-valid `run_summary.json` + `provenance.json`. **Not** maintainer-reproduced. |
| `verified` | A maintainer reproduced the result on this platform in a clean Docker environment. | `check_conformance` passes **and** a maintainer ran the full v1.6 eval in Docker (`ghcr.io/zeng-weijun/omnidocbench-eval:repro-ubuntu2204`) and reproduced the committed `overall` within tolerance, recorded in a committed `VERIFIED.yaml`. |

### The key distinction

- **CI green** means: the contract is sound, the schema is valid, the repo is
  structurally conformant. It does **not** mean the numbers are real.
- **`community`** means: a contributor ran the eval and committed honest,
  provenance-complete artifacts. CI verified the structure. The numbers are
  self-attested, not independently reproduced.
- **`verified`** means: a maintainer with real AMD hardware reproduced the
  result in Docker. This is the only tier that is **independently reproduced**,
  and it is the one to trust for cross-model comparison.

### Why this is honest

Pretending CI could validate GPU results would be dishonest — it can't, and
faking it (e.g. with mocked scores) would be worse. The tiered-badge model
makes the trust level explicit: `community` says "the contributor did this and
the structure checks out"; `verified` says "a maintainer reproduced it." You
read the badge, not the CI status, to know how much to trust a number.

---

## What this means for contributors

- **Your PR doesn't need a GPU to pass CI.** CI runs the CPU checks
  (conformance + smoke). The GPU eval is something *you* run on your hardware
  and commit the results of.
- **`make publish` is the gate for `community`.** It runs `check_conformance`
  locally; if it passes and your `results/` bundle is committed and
  schema-valid, you can submit a `community` badge.
- **Don't fake results.** The `metric_quality.formula_cdm.valid` field and the
  full-set enforcement (`limit_pages` must be `null` to publish) exist to make
  faking hard. Invalid CDM shows as `pending`/null, never a faked number. A
  `community` badge with honest zero-CDM is better than a faked one.
- **For `verified`,** keep your repo reproducible: pinned dataset revision,
  recorded `git_commit`, documented `adapter_command` and scoring config. The
  maintainer reproduction uses exactly these.

---

## What this means for readers of the comparison table

When you look at the hub comparison table:

- A `community` number is real if you trust the contributor (the structure is
  CI-verified, the artifacts are committed and schema-valid, but no one
  independently reproduced it).
- A `verified` number is real if you trust the maintainer reproduction
  (independent Docker reproduction on real AMD hardware, within tolerance,
  recorded in `VERIFIED.yaml`).
- A `community-wanted` column means no one has run that platform yet — the
  model is wanted there but has no data.

This is the same trust model as a paper with code: the authors ran it
(`community`), and reviewers reproduced it (`verified`). CI's role is to
enforce the contract, not to vouch for the numbers.
