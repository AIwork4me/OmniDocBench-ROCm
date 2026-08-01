# ROCmDoc Zone — Maintainer Decisions Pending (round-2, 2026-08-01)

> **RESOLVED 2026-08-01** — the maintainer adopted the non-binding leans: **D1 = vllm** (already the explicit, non-auto-highest primary in card + central; no edit needed), **D2 = A** (the 6 evidence-complete results → `submitted` with an `assurance_migration` note), **D3 = A** (primary-uniqueness key is now `(model_id, platform, comparison_track_id)`; Standard §7.3 reworded + ADR-0021 + detector + tests; `registry.check` unchanged). After D2+D3, `check_drift` = **0 findings** (was 7); `make ci` 308 passed. Each enactment was per-step verified by an independent subagent.
>
> **Open follow-on (not part of these decisions):** the 94.05 transformers result is `superseded` in the central store (Stage-A identity-hash remediation) but `valid` in the `HunyuanOCR-ROCm` model card — a model-repo sync to do separately.
>
> ---
>
> Three value-decisions were deliberately deferred to the maintainer per document P0-6 ("Claude Code 不得替人做价值选择"). This brief prepares verified facts + options; it does NOT decide. Each section ends with the specific question. Data re-derived from the canonical store @ commit `3f3be4a`. Non-binding observations are labeled as such — the choice is yours.

## Common context — the zone-wide identity gap

All 11 valid results carry **7/7 reproduction-critical identity fields as `unknown`** (model_revision, weights_sha256, page_set_hash, and the 4 inference config hashes). The v3 identity migration captured the *structure* but not the *values*. So strict P0-5 flags every `evidence-complete` result. Decision 2 is the *policy*; per-result identity pinning is the eventual root-cause fix (a separate, larger effort — see Decision 2 Option C).

## Decision 1 — Hunyuan primary (linux-rocm, v1.6-full track)

Valid candidates (the superseded 94.05 is shown for context only — it cannot be primary):

| result_id | backend | overall | status | primary | producer_assurance | identity |
|---|---|---:|---|---|---|---|
| `…vllm…38a99096c23d` | vllm | **93.64** | valid | **True (current)** | evidence-complete | 7/7 unknown |
| `…llama-cpp…9afe77319b08` | llama-cpp | 92.09 | valid | False | submitted | 7/7 unknown |
| `…transformers…311589508444` | transformers | 94.05 | **superseded** | False | evidence-complete | 7/7 unknown |
| (legacy) `…default…8bae5c861c6d` | (stub) | 93.64 | superseded | — | — | — |

**Question:** which valid result is Hunyuan's primary (the recommended path)?
- Keep **vllm 93.64** (current; vLLM is the zone's standard recommended path — Ovis golden = vLLM/ROCm).
- Switch to **llama-cpp 92.09** (submitted, lower score).
- The 94.05 transformers is **superseded** — it can only become primary after its identity is pinned and it is re-imported under a NEW result_id, then re-evaluated.

*Non-binding observation:* vllm 93.64 is the natural primary (zone-standard backend, current, highest *valid* score). The identity gap affects it equally but that is Decision 2's concern, not a reason to demote it here.
**Impact:** README headline + central-leaderboard primary row.

## Decision 2 — Assurance-ceiling enforcement policy (6 results)

The 6 `evidence-complete` results the new `unknown-identity-assurance-ceiling` detector flags (all 7/7 unknown identity): `hunyuan-ocr` vllm 93.64 (primary — ties to Decision 1), `logics-parsing-v2` vllm 93.19, and `mineru2.5` ×4 (linux pipeline, linux vlm-vllm, windows pipeline, windows vlm-llamacpp). Per strict P0-5 they cannot honestly exceed `submitted`. Policy options:

| Option | What it does | Honesty | Disruption | Cost |
|---|---|---|---|---|
| **A. Retroactive downgrade** | Set all 6 → `submitted` now (audited, with migration reason) | Most honest (matches strict P0-5) | High — zone-wide displayed-assurance drop | Low |
| **B. Prospective-only** | Enforce the ceiling for NEW imports; grandfather the 6 with a visible note | Less honest (leaves a known overclaim in place) | Low | Low |
| **C. Pin real identity hashes** | Fill model_revision / weights_sha256 / page_set_hash / inference hashes for the 6 → ceiling clears legitimately | Most honest + actually reproducible | Medium | **High** (per-result provenance: weights digest, HF revision, configs; changes result_ids → re-import) |

**Question:** which policy? (A = honest sweep, cheap, reversible; B = least disruption but leaves an overclaim; C = the real fix, but a project.)
*Non-binding observation:* **A** is the honest interim (cheap, reversible, matches the Standard); **C** is the real destination; **B** risks leaving a known overclaim visible in the public store.

## Decision 3 — mineru2.5 dual-primary + primary-key semantics

mineru2.5 has **2 primaries on the v1.6-full track**:

| result_id | platform | backend | overall | producer_assurance |
|---|---|---|---:|---|
| `…vlm-vllm…69a85af9bd8e` | linux-rocm | vlm-vllm | 95.56 | evidence-complete |
| `…vlm-llamacpp…ae0d908ab9d6` | windows-hip | vlm-llamacpp | 95.46 | evidence-complete |

- `registry.check` keys primary-uniqueness by **(model_id, platform)** → 1 primary per platform → clean (enshrined in `test_primary_per_track`).
- The new `multiple-primaries-per-track` detector keys by **(model_id, comparison_track_id)** per Standard §7.3 literal → 2 primaries on the full track → flagged.

**Options:**
- **A. Adopt `(model_id, platform, comparison_track_id)`** as the primary key: keep BOTH primaries (one per platform); update Standard §7.3 wording + the detector + its test to match. (Most permissive; a spec/ADR edit.)
- **B. Demote one** (e.g. keep linux vlm-vllm 95.56 primary; windows vlm-llamacpp → non-primary alternate). Keeps §7.3 literal `(model,track)`. (Loses the per-platform primary signal.)
- **C. Split tracks by platform** (linux-full vs windows-full tracks) so each has its own primary. (Heavier; changes `track_id` semantics + every shipped card's track.)

**Question:** which semantics — one-primary-per-platform (A), or strict one-primary-per-track (B/C)?
*Non-binding observation:* **A** is least disruptive and matches how multi-platform models naturally have a best result per platform — but it is a spec change (§7.3 + an ADR). **Do NOT silently change `registry.check`** — it is test-locked; reconcile via ADR.

## What I need from you

A one-line answer per decision, e.g. `D1: vllm; D2: A; D3: A`. Once you decide, I execute the chosen option as an audited, per-step-verified change (e.g. for D2-A: downgrade the 6 → `submitted` with a migration reason, regen canonical + QUALITY_STATUS, re-run `make ci`). None of these is decided or done by me.
