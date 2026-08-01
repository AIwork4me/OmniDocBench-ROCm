# ROCmDoc Zone Audit — Final (round-2 convergence, session 2026-08-01)

> Scope: central `OmniDocBench-ROCm` + six model repos. Method: every claim below is
> a verified fact, re-derived by an independent verifier per step (8/8 steps this
> session passed independent re-verification). Audit date: 2026-08-01. This is a
> POINT-IN-TIME snapshot (current PR/shipping/drift state), not a regenerated dashboard.
> Working state: all session changes are LOCAL + UNCOMMITTED on central branch
> `feat/rocmdoc-1.0-governance` (HEAD still `8a4ecee`); no push/merge/tag/release done.

## A. What this session delivered (Stage A of the chosen plan — central gating artifacts + audit)

Each step was executed then independently verified by a fresh subagent (commands re-run, not trusted):

| # | Step | Outcome | Verifier |
|---|------|---------|----------|
| 1 | Map central contracts + engine | 10 map claims confirmed; 4 material gaps found (dual producer, no supersede field, track-id omits page_set_hash, primary keyed by (model,platform) not (model,track)) | PASS |
| 2 | Audit 94.05 commit rewrite | `8a4ecee` added 94.05 BUT switched producer `rebuild_canonical`→`generate_hub`, dropping 10 legacy rows; no score rewritten; data safe in `hub/legacy/` | PASS |
| 3 | Remediate 94.05 → superseded + alias | 94.05 set `superseded` (+reason/alias in note/supersession, +`license_category=restricted`); canonical regenerated via `rebuild_canonical` → 10 legacy rows restored, 22 total (11 valid / 10 superseded / 1 retracted); drift=0; `make ci` green; hunyuan primary (vLLM 93.64) intact | PASS |
| 4 | Fix exit-code doc divergence | `ROCMDOC_STANDARD.md §3.1` aligned to implemented `{0 OK/1 PARTIAL/2 USAGE/3 BACKEND_MISMATCH/4 CONTRACT/5 FATAL}`; env→doctor note; no-silent-renumber note; +recurrence guard test (proven to fail on the old drifted doc) | PASS |
| 5 | Cohort manifest | `contracts/cohort.json` derived deterministically from the real shipped contract commit `17b5d65`; **all 6 model spec-locks match it** (P0-2 cross-repo verified); schema sha256 `eed086d5…`; drift-guarded | PASS |
| 6 | v1.6 track catalog (Option B) | `contracts/tracks.json` with REAL hashes: `gt_manifest_sha256 a45cd84b…`, `page_set_hash ffd94b8e…` (1651 pages, independently re-derived); upstream/scorer `2b161d0…`; `make_track_id` UNCHANGED; canary page_set honestly `unknown` | PASS |
| 7 | QUALITY_STATUS generator | Deterministic (cohort commit, no wall clock, no moving HEAD); `--check` drift guard wired into `make ci`; honestly surfaces the 7 drift findings; parameterized for reuse | PASS |
| 8 | Identity validators (P0-5/P0-6) | `unknown-identity-assurance-ceiling` + `multiple-primaries-per-track` added to `check_drift` as REPORT-ONLY detectors (no auto-downgrade/demote); registry `(model,platform)` keying untouched | PASS |

Central gate after all steps: **`make ci` → 307 passed, all gates green** (was 284 at round-1 baseline).

## B. Round-2 document reconciliation (P0/P1 → status)

| Doc item | Status | Evidence |
|---|---|---|
| P0-1 source reachability / shipped to default | **PARTIAL** | 3/6 model repos have round-2 (`17b5d65`) on their public default branch (Ovis/Paddle/Hunyuan); 3/6 do NOT (MinerU/Logics/Unlimited — open draft PRs). Cohort manifest (task 5) now centralizes the lock; a zone source-reachability gate is a noted follow-on. Merge is a USER gate. |
| P0-2 freeze a real cohort | **DONE (this session)** | `contracts/cohort.json` pins `17b5d65`; **5/6 model spec-locks pin `17b5d65`** on their round-2 branch (Ovis/Paddle/Hunyuan on `main`; MinerU/Unlimited on `feat/rocmdoc-standard-v2`); **Logics's re-lock (`17b5d65`) is on `chore/rocmdoc-1.0-relock` while PR #1's head still pins ancestor `4556ee1`** (strict ancestor of 17b5d65 — materially consistent, not the frozen cohort) → PR #1 must be retargeted before merge. Deterministic freeze (task 5). |
| P0-3 single fact source, legacy demoted | **DONE (round-1 + reinforced)** | badge-policy→legacy, `COMPATIBILITY.md`, canonical store generated; QUALITY_STATUS now also generated (task 7). |
| P0-4 immutable v1.6 dataset identity | **DONE (this session)** | `contracts/tracks.json` pins upstream commit, dataset revision, GT manifest sha256, sorted page-set hash, page count, scorer revision, metric set, protocol (task 6). |
| P0-5 unknown assurance ceiling + platform-review matrix | **DETECTOR DONE / ENFORCEMENT BLOCKED** | Ceiling validator added (task 8); platform-review 4-field matrix exists (`platform_review_record`); applying the ceiling (6 results) is a maintainer decision. |
| P0-6 primary decisions + result-truth conflicts | **94.05 RESOLVED / PRIMARY DECISIONS BLOCKED** | 94.05 conflict superseded (task 3); per-(model,track) detector added (task 8); mineru2.5 dual-primary + Hunyuan primary are maintainer decisions. |
| P1-1 unified CLI + exit codes | **EXIT-CODE DONE / CLI-unify per-repo** | Exit-code doc divergence fixed + guarded (task 4); cross-repo CLI unification is per-repo (round-1/follow-on). |
| P1-2 `table_tides`→`teds` typo | **DONE (round-1)** | Zone-wide; 0 remaining. |
| P1-3 README/QUALITY_STATUS generated | **DONE** | QUALITY_STATUS generator (task 7); README generated blocks (round-1). |
| P1-4 license split (code/upstream/weights/dataset/artifacts) | **DONE (round-1)** | `license_record` / `code_license_record` / `model_openness_record` split in schema. |
| P1-5 per-result hardware/backend (no single ROCm label) | **DONE (round-1)** | `accelerator_family` (incl. `mixed`) + `components` per-stage. |

## C. Honest drift findings (live `check_drift`) — DETECTED, awaiting maintainer decisions

These are now VISIBLE (were hidden before task 8). Validators report only; they do not auto-fix.

1. **`unknown-identity-assurance-ceiling`: 6** — every `evidence-complete` result carries all 7 reproduction-critical identity fields as `unknown` (model_revision, weights_sha256, page_set_hash, prompt/pre/post/runtime config hashes): hunyuan vLLM 93.64 (primary), logics 93.19, mineru2.5 ×4. Per strict P0-5 these would cap to `submitted`. **Maintainer decision:** retroactive zone-wide downgrade (honest, sweeping) vs prospective-only enforcement vs pin real identity hashes per result. (The 94.05 — the worst case — was already superseded in task 3 per your decision.)
2. **`multiple-primaries-per-track`: 1** — mineru2.5 has 2 primaries on the full track (linux vlm-vllm + windows vlm-llamacpp). Per-platform this is clean (registry `(model,platform)`); per Standard §7.3 `(model,track)` it is a violation. **Maintainer decision:** reconcile the two semantics (e.g. adopt `(model,platform,track)` or demote one mineru2.5 primary) — this is also a spec/code reconciliation (do NOT silently change `registry.check`; it's enshrined in tests).

## D. Per-repo shipping matrix (P0-1)

| Repo | Default | Round-2 (`17b5d65`) on default? | Open PR |
|---|---|---|---|
| OvisOCR2-ROCm | main | ✅ shipped | — |
| PaddleOCR-VL-ROCm | main | ✅ shipped | — |
| HunyuanOCR-ROCm | main | ✅ shipped | — |
| MinerU-ROCm | main | ❌ not shipped | #20 (draft, `feat/rocmdoc-standard-v2`) |
| Logics-Parsing-ROCm | **master** | ❌ not shipped | #1 (draft, `feat/rocmdoc-standard-v2`) — ⚠ PR #1 **head pins `4556ee1`, not `17b5d65`**; the re-lock lives on `chore/rocmdoc-1.0-relock` (retarget #1 before merge) |
| Unlimited-OCR-ROCm | main | ❌ not shipped | #66 (draft, `feat/rocmdoc-standard-v2`) |

## E. Blockers requiring maintainer / user action

**Maintainer VALUE-decisions (Claude Code must not make these):**
- Hunyuan primary selection (which verified path represents the recommendation) — document P0-6.
- The 6-result assurance-ceiling enforcement policy (C.1) — document P0-5.
- mineru2.5 dual-primary reconciliation + `(model,platform)` vs `(model,track)` semantics (C.2).

**User gates (no push/merge/tag without your authorization):**
- Merge the 3 blocked model-repo PRs (#20 MinerU, #1 Logics, #66 Unlimited) to their default branches once CI is green (round-1 noted the integration debt: Unlimited no-torch CI, MinerU conflict, Logics retarget+CI).
- Commit + push this session's central work (currently local/uncommitted on `feat/rocmdoc-1.0-governance`).
- Merge the central governance branch to `main` (advances the cohort lock; then re-freeze cohort + re-lock model spec-locks).

**Owner-side GitHub actions (cannot be done from the clone):**
- MinerU PAT: revoke/rotate on GitHub if ever exposed (local `.git/config` is clean; local cleanup ≠ remediation).
- GitHub About/description sync (Ovis etc. may still show old scores) — generate a maintainer checklist, don't script-edit remote settings.

**Environment constraints (honest NOT_RUN):**
- No GPU → all score/inference/cross-hardware reproduction = NOT_RUN.
- Git transport to github.com is flaky (times out); `gh`/`api.github.com` work. Source-reachability verification is feasible via gh API + local ancestry with friction.

## F. This session's footprint (central, local/uncommitted)

Modified (8): `Makefile`, `README.md`, `contracts/ROCMDOC_STANDARD.md`, `engine/omnidocbench_rocm/{hub,run_spec}.py`, `hub/canonical_results.json`, the hunyuan 94.05 `imported-result.json`, `tests/test_cli_contract.py`.
New (12): `QUALITY_STATUS.md`, `contracts/{cohort,tracks}.json`, `engine/omnidocbench_rocm/{cohort,quality_status,track_catalog}.py`, `scripts/{freeze_cohort,freeze_tracks,render_quality_status}.py`, `tests/{test_cohort,test_identity_validators,test_quality_status,test_track_catalog}.py`.
Net: +284/−14 across modified; 12 new files. HEAD unchanged at `8a4ecee`. **Nothing committed, pushed, merged, tagged, or released.**

## G. Recommended PR split (dependency order — model-repo facts + stable refs first, central import last)

1. **Central contract PR** (this session): cohort manifest + track catalog + exit-code fix + QUALITY_STATUS generator + identity validators + 94.05 remediation + legacy restore. (One cohesive central change; `make ci` green.)
2. **Model migration PRs** (round-1, re-verified): Ovis/Paddle/Hunyuan already merged; finish MinerU #20 / Unlimited #66 (resolve CI/conflicts, `gh pr ready`, merge); **Logics #1 must first be retargeted to `chore/rocmdoc-1.0-relock`** (its head still pins ancestor `4556ee1`) — USER gate.
3. **Central re-import / re-freeze** (after #1 merges to main): re-freeze `cohort.json` (lock advances), re-lock the 3 newly-shipped repos' spec-locks.
4. **Community/quality + enforcement policy PR**: once you decide the assurance-ceiling + primary policies (E), apply them (downgrade/demote) in an audited commit with migration reasons.

## H. Release-candidate hard gates (document §九) status

1. Central standard + cohort on default, parseable — standard ✓ (main); **cohort.json NOT yet on main** (this session, uncommitted) → PENDING merge.
2. Six repos same-cohort or explicitly incoming — **PARTIAL** (3 shipped / 3 incoming).
3. All central source commits reachable from default/tag — reachability gate is a noted follow-on (network-constrained).
4. Default leaderboard free of unknown-page-set pseudo-same-track / invalid backend / duplicate primary — **BLOCKED** (the 7 findings in C; maintainer decisions).
5. producer_assurance vs platform_review fully split — **DONE**.
6. README/QUALITY_STATUS/package/canonical no conflicting headline — **mostly DONE**; Hunyuan primary headline pending (C/E).
7. Hunyuan primary decided by maintainer — **BLOCKED** (human decision).
8. MinerU PAT revoked/rotated by owner, or remains BLOCKER — **BLOCKED** (owner-side).
9. Zone audit has no unexplained FAIL; GPU/hardware reproduction honestly NOT_RUN — **DELIVERED by this audit.**

**Net:** the central gating ARTIFACTS + DETECTORS (Stage A) are done and verified-green; the zone is not yet a "released cohort" because shipping the 3 repos, the cohort→main merge, and the three maintainer value-decisions remain. None of those are things Claude Code should decide or do without explicit authorization.
