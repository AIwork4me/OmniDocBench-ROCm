# Reproducible scoring image (verified path)

`Dockerfile.repro` pins the CDM-sensitive toolchain (texlive-full + ImageMagick 7
+ ghostscript + node + CJK fonts) so a `verified` scoring reproduction is
deterministic. It reproduces **scoring** (Edit_dist + TEDS + CDM) from committed
predictions — not inference (inference is deterministic given the committed
model+weights; the toolchain versions are the reproducibility risk).

Build (on a Docker-capable box — Docker is absent in the dev env):

    python -m build
    docker build -t omnidocbench-rocm-repro:0.2.0 \
      --build-arg OMNIDOCBENCH_REF=<OMNIDOCBENCH_V16_REF> \
      -f engine/omnidocbench_rocm/docker/Dockerfile.repro .

`OMNIDOCBENCH_V16_REF` is the engine's pinned v1.6 ref
(`engine/omnidocbench_rocm/_refs.py::OMNIDOCBENCH_V16_REF`), currently
`2b161d0`. Substitute that value for `<OMNIDOCBENCH_V16_REF>` above.

Run (mount predictions + ground truth):

    docker run --rm \
      -v "$PREDICTIONS":/preds \
      -v "$GT/OmniDocBench.json":/gt/OmniDocBench.json \
      omnidocbench-rocm-repro:0.2.0 \
      score --platform linux-rocm --predictions-dir /preds --version v16 \
            --run-stats /preds/_run_stats.json --dataset-dir /gt

Then verify and record:

    python scripts/check_verified.py VERIFIED.yaml   # |delta| <= 0.5
