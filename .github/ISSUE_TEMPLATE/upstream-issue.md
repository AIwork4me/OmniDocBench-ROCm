---
name: Upstream issue / PR
about: Track an OmniDocBench / model-upstream issue or PR that affects this zone (NOT a zone result)
title: "[Upstream] <repo>: <short>"
labels: upstream
---

## Upstream target
- Repo (OmniDocBench / a model repo / EvalScope / …):
- Upstream issue/PR link:

## Why it matters to this zone
- Affects: contract / scorer / dataset / a model adapter / reproducibility
- Expected impact on existing results (new comparison track needed? result_id change?):

## Current zone state
- Affected `result_id`(s) / track(s):

## Note
Upstream/paper results NEVER enter a ROCm comparison track (ROCmDoc Standard
§7.2). This issue is for tracking only — zone results are imported via immutable
source imports, not from upstream `main`.
