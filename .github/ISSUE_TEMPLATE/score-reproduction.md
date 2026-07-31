---
name: Score reproduction
about: Re-score committed predictions with the locked scorer (no inference GPU required)
title: "[Score repro] <model> / <result_id>"
labels: score-reproduction
---

## Which contribution path?
- [x] Reproduce a score (ROCmDoc Standard §8 score_reproduction)

## Target
- Model repo:
- `result_id`:
- Comparison track:

## Source predictions (immutable)
- Commit / artifact hash of the predictions:
- Prediction manifest (files + count + sha256):

## Scorer lock
- Scorer revision / commit:
- Dataset revision:
- Scoring protocol + metric set:

## Result
- Reproduced overall (within tolerance |Δ| ≤ 0.5):
- Delta vs committed:
- Reproduction command + toolchain:

## Output
- Computed metric file + arithmetic-consistency note (metrics ↔ run summary ↔ provenance):
