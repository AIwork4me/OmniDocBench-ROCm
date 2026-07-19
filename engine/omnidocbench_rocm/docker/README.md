# Reproducible scoring image (verified path)

`Dockerfile.repro` reproduces **scoring** (Edit_dist + TEDS + CDM) from committed
predictions — not inference (inference is deterministic given the committed
model+weights; the CDM-toolchain versions are the reproducibility risk).

## Base image: OmniDocBench's OFFICIAL verified eval image

`Dockerfile.repro` is `FROM ghcr.io/zeng-weijun/omnidocbench-eval:repro-ubuntu2204`,
OmniDocBench's pre-built verified runtime (Python 3.10 conda env + **TeX Live 2025**
+ ImageMagick 7.1.1-47 + Ghostscript 9.55.0 + **working CJK / Arphic `gkai` fonts**).
It is the known-working CDM environment — the documented reference
(OmniDocBench README; SKILL.md "TeX Live 2025 ... CJK ok").

**Why not rebuild the toolchain from `ubuntu:22.04`?** An earlier version of this
Dockerfile installed Debian `texlive-full` + built IM7 from source. That base
**lacks the Arphic `gkai` font** (not in Ubuntu's apt; `texlive-full` ships other CJK
fonts like `c0so12`, not `gkai00mp`/`gkaiu`), so CDM rendered **blank** — confirmed
by running OmniDocBench's own CDM (`display_formula.CDM = None`). Reusing the official
verified image is the only path known to produce correct CDM.

## Build (on a Docker-capable box — Docker is absent in the dev env)

> **Build-unverified here.** This Dockerfile was not build-tested in the dev
> environment (no Docker). The engine-wheel install assumes the base image's default
> `pip` is its conda env; if the build fails at that step, adjust to
> `conda run -n <env> pip install ...` for the base image's conda-env name.

    python -m build
    docker build -t omnidocbench-rocm-repro:0.2.0 \
      --build-arg OMNIDOCBENCH_REF=2b161d0 \
      -f engine/omnidocbench_rocm/docker/Dockerfile.repro .

`OMNIDOCBENCH_REF` is the engine's pinned v1.6 ref
(`engine/omnidocbench_rocm/_refs.py::OMNIDOCBENCH_V16_REF`), currently `2b161d0`.

## Run (mount predictions + ground-truth dir)

    docker run --rm \
      -v "$PREDICTIONS":/preds \
      -v "$GT_DIR":/gt \
      omnidocbench-rocm-repro:0.2.0 \
      score --platform linux-rocm --predictions-dir /preds --version v16 \
            --run-stats /preds/_run_stats.json --dataset-dir /gt

(`$GT_DIR` is a directory containing `OmniDocBench.json`.)

## Verify and record

    python scripts/check_verified.py VERIFIED.yaml   # |reproduced − committed| <= 0.5

A passing check + a committed `VERIFIED.yaml` is the gate for the `verified` badge.
