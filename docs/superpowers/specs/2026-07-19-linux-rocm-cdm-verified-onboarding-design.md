# Design: Linux-ROCm engine readiness for verified onboarding (CDM + Docker repro) — PaddleOCR-VL flagship

- **Date:** 2026-07-19
- **Status:** Approved (design) — pending spec review, then implementation plan
- **Branch:** `feat/linux-rocm-cdm-verified-onboarding`
- **Repo:** `OmniDocBench-ROCm` (platform repo; `github.com/AIwork4me/OmniDocBench-ROCm`)
- **Approach:** Approach 1 — platform-repo work only. The PaddleOCR-VL adapter port + vLLM/ROCm serving is a follow-on spec in `PaddleOCR-VL-ROCm`.

---

## 1. North star (why this spec exists)

The 0.2.0 rebrand made the platform honest, branded, and well-tooled — but the
registry is **empty** (3 models, `community-wanted`, no scores). An empty
registry is the single biggest thing preventing OmniDocBench-ROCm from being a
top-tier open-source evaluation platform. The differentiators of a top-tier
platform (cf. vLLM, llama.cpp, MIGraphX, ONNX Runtime) are:

1. **Real, independently reproducible scores** — a `verified` badge (maintainer
   Docker reproduction within tolerance), not self-attested numbers.
2. **The hard metric actually works** — CDM (formula matching) end-to-end. Most
   projects hand-wave or skip CDM; a platform that produces real, reproducible
   CDM scores is a serious eval platform, not a toy.
3. **Depth before breadth** — one gold-standard, fully-verified, CDM-complete
   flagship entry proves the platform end-to-end and is stronger than three
   partial `community`-only entries.

**This spec's north star is a verified flagship entry:**

> *PaddleOCR-VL on Linux-ROCm: Edit_dist + TEDS + **CDM**, reproducible inside a
> pinned Docker image, recorded in `VERIFIED.yaml`, badge `verified` in
> `hub/registry.yaml`.*

To make that reachable, this spec makes **CDM end-to-end-usable** and the
**verified Docker-reproduction path** first-class platform deliverables — not
"future work." `community` is the intermediate state, not the终点.

## 2. What's broken today (the gaps this closes)

- `linux_rocm.py::score()` calls `pdf_validation.py --config <version> --predictions <dir>`. The `--predictions` flag **does not exist** — OmniDocBench scoring is config-driven (`pdf_validation.py --config <rendered.yaml>`; predictions live *inside* the config). The current call cannot score anything.
- The OmniDocBench checkout revision is hardcoded to `master` (unpinned → scorer and dataset can drift → non-reproducible).
- `provision_cdm()` is a print stub; there is no `engine/omnidocbench_rocm/cdm/` toolchain; CDM cannot run.
- No 3.11 eval-venv (the old `omnidocbench-amd-venv` is Python 3.12, which breaks OmniDocBench's `inspect.getargspec`/`distutils`/`imp` usage).
- No reproducible Docker scoring path; `verified` is therefore unreachable.

**Confirmed facts (design inputs):**
- `gfx1100` is present on the eval box (`rocminfo`) → a real Linux-ROCm eval is executable here.
- OmniDocBench checkout present at `/workspace/OmniDocBench`; real entry is `src/core/pipeline.py` (`process_args` → argparse `--config`/`-c`).
- CDM is enabled by adding `CDM` to `display_formula.metric` in the config (precedent: `configs/unlimited_rocm_30_cdm.yaml`).
- **Docker is NOT installed in this environment** → the `verified` reproduction step itself runs on a Docker-capable maintainer box; this spec delivers the *capability*, not the in-env execution of that final step.

## 3. Goals / non-goals

### Goals (first-class deliverables)
- **G1 — Engine scoring is real and reproducible:** `score()` renders a config and invokes `pdf_validation --config <rendered>`; revision pinned; CDM is a config variant.
- **G2 — CDM is end-to-end-usable on the host:** an idempotent `setup-linux.sh` (texlive-full + ImageMagick 7 + ghostscript + node) with the known pitfall guards; `provision_cdm()` actually provisions; a CDM score can be produced (not just "script exists").
- **G3 — Verified reproduction path is real:** the platform ships a self-contained `Dockerfile.repro` pinning the toolchain; the engine's `score` runs inside it; `VERIFIED.yaml` + a tolerance check exist; the runbook's terminal step is the maintainer Docker reproduction.
- **G4 — Onboarding runbook whose success definition is a verified flagship entry** (not "a community score").
- **G5 — 3.11 eval-venv provisioning** wired into setup.

### Non-goals (explicitly out of scope this spec)
- PaddleOCR-VL adapter port + vLLM/ROCm serving — follow-on spec in `PaddleOCR-VL-ROCm`.
- The Windows/DirectML track; cross-platform finalize.
- Actually executing the 1651-page GPU eval and the Docker `verified` reproduction — these are **gated execution steps** (the run needs the model served; the `verified` repro needs Docker, absent here). The plan makes everything *ready*; execution is a resumable, separately-gated job. "Gated" means *when*, not *whether* — the north star requires these to fire.
- Onboarding the 2nd/3rd model (breadth) — follows the flagship.

## 4. Strategic framing (locked in)

- **CDM is core, not optional.** G2 is a first-class deliverable. The `#cdm-zero` failure modes (POSIX shell assumptions, IM6 grayscale flattening, all-exception null) are addressed in the toolchain, not deferred.
- **Verified is the target, community is the intermediate.** G3 makes `verified` reachable; the runbook does not stop at `community`.
- **Depth before breadth.** One fully-verified, CDM-complete PaddleOCR-VL entry is the flagship; breadth (Unlimited-OCR, MinerU2.5) follows the same proven path.
- **We own reproducibility.** The platform ships its own `Dockerfile.repro` rather than depending on a third-party image, so pinned versions are under our control.

## 5. Architecture decisions

### AD1 — Engine `score()`: config rendering, single-arg invocation, revision pin, CDM variant
- The engine carries a default template `engine/omnidocbench_rocm/data/omnidocbench_v16.yaml.tmpl` (modeled on `configs/unlimited_rocm_sglang_v16_nocdm.yaml`). `score()` renders it with `dataset.prediction.data_path = <predictions_dir>`, `dataset.ground_truth.data_path = <dataset_dir>/OmniDocBench.json`, `match_method`, worker counts.
- A model repo may override by shipping `eval/configs/omnidocbench_v16.yaml` (already required by the conformance contract); the engine prefers the repo's template if present, else the default.
- `cdm=True` renders the **CDM variant** (`display_formula.metric: [Edit_dist, CDM]`) and scores a `_cdm`-suffixed predictions dir (existing convention — no clobbering the Edit_dist run).
- Invocation: `[venv_python, pdf_validation.py, "--config", <rendered.yaml>]`, `cwd=checkout`. `build_save_name` derives the result filename.
- **Revision pin:** a single engine constant `OMNIDOCBENCH_V16_REF` (a specific OmniDocBench commit aligned with the v1.6 dataset revision from `stage_download`). `ensure_checkout(revision=OMNIDOCBENCH_V16_REF)`. Dataset revision and scorer revision stay aligned and reproducible.
- **Tested without GPU:** mock the subprocess; assert the rendered config has correct prediction/GT paths, the right metric list per `cdm`, and the command is exactly `--config <path>`.

### AD2 — CDM toolchain, host fast path (first-class, end-to-end-usable)
- `engine/omnidocbench_rocm/cdm/setup-linux.sh`: idempotent apt provisioning of `texlive-full`, `ImageMagick 7`, `ghostscript`, `node`. Self-checks (`dpkg -s`, `kpsewhich`, `magick -v`, `gs -v`); prints "already present" on re-run; resumes after partial interruption.
- **Pitfall guards baked in** (from `docs/pitfalls.md`): IM7 not IM6 (IM6 silently flattens color formulas to grayscale → `#grayscale`); CJK fonts for texlive; the `magick` `policy.xml` PDF write enablement; clean `PATH` so `kpsewhich`/`magick`/`gs` resolve (`#posix`).
- `LinuxRocmBackend.provision_cdm()` invokes `setup-linux.sh` (no longer a stub) and verifies the toolchain is functional (a tiny "compile a formula → rasterize → match" smoke that detects the `#cdm-zero` all-exception failure mode before a real run).
- This is the **fast path for `community`**; the Docker path (AD3) is the reproducible path for `verified`.

### AD3 — Verified reproduction path (first-class; the `verified` enabler)
- The platform ships `engine/omnidocbench_rocm/docker/Dockerfile.repro` (self-contained): pins `texlive-full` + IM7 + gs + node + the OmniDocBench checkout at `OMNIDOCBENCH_V16_REF` + the engine; exposes the `score` entrypoint. A `make repro-score` target runs the engine's `score` stage inside this image with a mounted predictions dir.
- **What `verified` reproduces (first flagship):** the **scoring pipeline** (Edit_dist + TEDS + CDM) from the *committed predictions*, in the pinned Docker image, within tolerance. This is the high-value reproducibility — the metric is exquisitely sensitive to the CDM toolchain versions (LaTeX/IM/gs), which the image pins. Inference is deterministic given the committed model+weights, so reproducing scoring is sufficient for a trustworthy `verified` bar. Full inference-in-Docker is a stronger future bar, noted but not required for the first flagship.
- **Engine runs in-container unchanged** — `score()` is container-friendly (no host-specific assumptions beyond the toolchain the image pins). The same rendered-config path serves host and container.
- `VERIFIED.yaml` (schema already in `contracts/badge-policy.md`): maintainer records `docker_image`, `reproduced_overall`, `committed_overall`, `delta`, `tolerance` (0.5), `engine_version`, `git_commit`, `platform`, `date`.
- A tolerance check (`scripts/check_verified.py` or engine subcommand) asserts `|reproduced − committed| ≤ tolerance` before a `verified` badge is accepted.
- The canonical third-party image `ghcr.io/zeng-weijun/omnidocbench-eval:repro-ubuntu2204` is referenced in docs as an alternative; **the platform's own `Dockerfile.repro` is primary** (we own the pinned versions).

### AD4 — 3.11 eval-venv provisioning
- `data_root()/eval-venv/linux-rocm` (Python 3.11 — OmniDocBench scoring breaks on 3.12). `_paths.eval_venv("linux-rocm")` already points here; provisioning = `python3.11 -m venv` + `pip install -e <OmniDocBench checkout>` + scoring deps.
- A setup target provisions it and asserts `python --version` is 3.11 (the architecture's "critical Python split").

### AD5 — Onboarding runbook; success = verified flagship entry
- New `docs/onboarding-runbook.md`: the exact, reproducible procedure from "provisioned" to "verified flagship entry", PaddleOCR-VL as the worked example. Steps:
  1. Pin dataset + scorer revision (`OMNIDOCBENCH_V16_REF`); provision 3.11 eval-venv (`make setup-linux`).
  2. Run the adapter over the full 1651-page set (model repo's `run_adapter.py`; **gated GPU job, resumable**).
  3. `score` Edit_dist + TEDS (no CDM first pass) → `metric_result.json`.
  4. `provision_cdm` + `score --cdm` (CDM variant) → CDM metric; abort to `pending`/null on `#cdm-zero`, never a faked number.
  5. `publish` (full-set enforcement; `limit_pages` must be null) → `run_summary.json` + `provenance.json`.
  6. `conformance` → CONFORMANT; update `hub/registry.yaml` → `community` badge (intermediate).
  7. **Maintainer Docker reproduction** (`make repro-score` via `Dockerfile.repro`) → `VERIFIED.yaml` + tolerance check → registry `verified`. **This is the runbook's success definition.**
- The 1651-page run and the Docker repro are **gated execution steps** (the run needs the served model; the repro needs Docker — not in this env). The runbook makes them explicit and resumable; it does not script them minute-by-minute.

## 6. The flagship entry (definition of done for the program, not this spec)

```
hub/registry.yaml:
  - model_id: paddleocr-vl-1.6
    repo: AIwork4me/PaddleOCR-VL-ROCm
    platforms:
      linux-rocm: {badge: verified, overall: <real number>}
```
backed by: schema-valid `run_summary.json` + `provenance.json` + `VERIFIED.yaml`
(Docker-reproduced within tolerance, CDM-valid). `community` is the checkpoint
after step 6; `verified` after step 7.

## 7. Scope decisions (the four levers)

| Lever | Decision | Rationale |
|---|---|---|
| **A. Config template** | Engine default + model-repo override | Reproducibility + low friction (table-stakes). |
| **B. Revision pin** | One engine constant `OMNIDOCBENCH_V16_REF` | Reproducibility (table-stakes). |
| **C. Runbook** | New `docs/onboarding-runbook.md` | Contributor enablement (table-stakes). |
| **D. CDM** | **Core first-class deliverable** (not optional) | The top-tier differentiator. |

A/B/C are necessary hygiene; **D + AD3 (verified path) are what move the needle
toward top-tier.**

## 8. File manifest (platform repo)

**Created:**
- `engine/omnidocbench_rocm/data/omnidocbench_v16.yaml.tmpl` (default scoring config template)
- `engine/omnidocbench_rocm/cdm/setup-linux.sh` (idempotent CDM toolchain)
- `engine/omnidocbench_rocm/cdm/smoke_cdm.sh` (tiny formula→raster→match probe for `#cdm-zero`)
- `engine/omnidocbench_rocm/docker/Dockerfile.repro` (pinned reproducible scoring image)
- `scripts/check_verified.py` (tolerance check for `VERIFIED.yaml`)
- `docs/onboarding-runbook.md`

**Modified:**
- `engine/omnidocbench_rocm/backends/linux_rocm.py` (`score()` config rendering + single-arg invocation + CDM variant; `ensure_checkout` pinned; `provision_cdm` real)
- `engine/omnidocbench_rocm/__init__.py` or a constants module (`OMNIDOCBENCH_V16_REF`)
- `engine/omnidocbench_rocm/cli.py` (plumb `--scoring-config` / CDM through `score`/`run`)
- `Makefile` / template Makefile (`setup-linux`, `provision-cdm`, `repro-score` targets)
- `contracts/badge-policy.md` (cross-link the tolerance check + `Dockerfile.repro`)
- `tests/test_backends.py`, `tests/test_stages.py` (rendered-config assertions; revision pin; CDM variant)
- `docs/architecture.md`, `docs/pitfalls.md` (update CDM ownership section now that it's real)

## 9. Gated execution (honest constraints)

- The **1651-page GPU eval** needs the PaddleOCR-VL model served (follow-on spec) — gated until the adapter + serving land. Resumable; the runbook defines the resume point.
- The **`verified` Docker reproduction** needs a Docker-capable box; **Docker is absent in this environment**, so that final step is executed by the maintainer on a Docker box. This spec delivers the `Dockerfile.repro` + engine container-path + `VERIFIED.yaml`/tolerance machinery so the step is one command when Docker is available.
- "Gated" = *when* these run, not *whether*. The north star requires both to fire.

## 10. Risks

| Risk | Mitigation |
|---|---|
| `pdf_validation` config shape differs from the Unlimited-OCR precedent | Template modeled on a known-working v1.6 config; first scored run is the validation gate. |
| CDM `#cdm-zero` resurfaces on the host toolchain | `smoke_cdm.sh` probe before any real CDM run; pitfall guards in `setup-linux.sh`. |
| `OMNIDOCBENCH_V16_REF` drifts from the fetched dataset | Single constant sourced from `stage_download`'s pinned revision; a test asserts they match. |
| Docker absent → `verified` can't complete in this env | Spec is explicit: `Dockerfile.repro` is the deliverable; the repro is a maintainer-on-Docker-box step. `community` is reachable here; `verified` needs Docker. |
| Config rendering couples engine to OmniDocBench's config schema | Keep the template minimal + overridable by the model repo; pin the scorer revision so the schema is stable. |

## 11. Plan-level verifications (resolve during writing-plans, do not block design)

- Exact `display_formula.metric` shape for CDM (confirm `[Edit_dist, CDM]` vs `[CDM]` against a working CDM run's config).
- Whether `python3.11` is available on the box for the eval-venv (else provision via `pyenv`/`uv`).
- The `magick policy.xml` edit needed for PDF write in the installed IM7.

## 12. Next step

Upon user approval of this written spec → invoke **writing-plans** to produce the
implementation plan (`docs/superpowers/plans/2026-07-19-linux-rocm-cdm-verified-onboarding.md`),
then execute on this branch. The PaddleOCR-VL adapter + serving follow-on is a
separate brainstorm in `PaddleOCR-VL-ROCm`.
