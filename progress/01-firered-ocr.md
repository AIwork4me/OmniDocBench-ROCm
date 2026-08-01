# 01 — FireRed-OCR Step 1 Preflight (2026-08-01)

Read-only preflight. No clone, no code, no run. Establishes the plan + GO/NO-GO + blockers.

## Identity

- **Model**: FireRed-OCR-2B (2B params), base = **Qwen3-VL-2B-Instruct**.
- **Upstream code**: `FireRedTeam/FireRed-OCR` (github). Files: `conv_for_infer.py`, `qwen3_hf_infer.py` (transformers), `qwen3_vllm_infer.py` (vLLM), `LICENSE.txt`, `README.md`.
- **Weights**: `FireRedTeam/FireRed-OCR` (HuggingFace) / ModelScope mirror.
- **OmniDocBench eval script**: `/workspace/OmniDocBench/tools/model_infer/FireRed_OCR_img2md.py` (LOCAL, present — no net-new script needed).
- **Official ref**: OmniDocBench **v1.5** = 92.94 (end-to-end SOTA). (Queue brief listed 93.26 — likely v1.6_full; ref is for SORTING ONLY, never imported.)

## License tri-split → `open-source-ai` (CLEANEST in the queue)

- **Code**: Apache-2.0 — `LICENSE.txt` is the full verbatim Apache 2.0; `conv_for_infer.py`/`qwen3_*_infer.py` are the FireRed code.
- **Weights**: Apache-2.0 — README "License Agreement": *"The code and the weights of FireRed-OCR are licensed under Apache 2.0."*
- **Third-party**: base Qwen3-VL (Apache-2.0), `qwen-vl-utils`. No restricted third-party component in the inference path.
- **Roll-up**: Apache code + Apache weights, no commercial/geo/use restriction → **`open-source-ai`**. (README "Ethics Statement" is a soft AUP, NOT a license term — unlike OpenRAIL-M; does not change the Apache classification.)
- LICENSE_BLOCKED: **none**. GO.

## Inference contract (must match exactly for a valid ROCm result)

From `FireRed_OCR_img2md.py` (OmniDocBench eval) + `conv_for_infer.py`:
- **Model load**: `Qwen3VLForConditionalGeneration.from_pretrained(path, dtype=torch.bfloat16, device_map="auto")` — native transformers class, **no `trust_remote_code`**.
- **Attn**: default (SDPA on ROCm). README's `attn_implementation="flash_attention_2"` is **commented-out optional** — not required.
- **Processor**: `AutoProcessor.from_pretrained`; `apply_chat_template(messages, add_generation_prompt=True, return_dict=True, return_tensors="pt")`.
- **Prompt**: the exact PROMPT string from `conv_for_infer.generate_conv` (PDF→Markdown; formulas→LaTeX `\(…\)`/`\[…\)`; tables→HTML `<table>`; ignore figures). ⚠️ Pin the EXACT bytes from the cloned file at adapter time — the zread extraction mangled LaTeX delimiters; do not hardcode a possibly-mangled copy.
- **Decode**: `model.generate(**inputs, max_new_tokens=8192)`; trim input ids; `batch_decode(skip_special_tokens=True, clean_up_tokenization_spaces=False)`; write one `.md` per page (basename-mapped to v1.6 dataset).
- ⚠️ **Discrepancy**: upstream `qwen3_hf_infer.py` worker calls `generate_conv(data_dict)` + `max_new_tokens=1024`; the OmniDocBench eval calls `generate_conv(image_path)` + `8192`. **Adapter follows the eval contract** (path + 8192) — that is what the leaderboard score is computed from.

## ROCm compatibility matrix

| axis | value | risk |
|---|---|---|
| backend | **transformers SDPA** (correctness path) | none — matches migration-714 transformers-only (ADR-0010) |
| vLLM | `qwen3_vllm_infer.py` exists | **BLOCKED** on ROCm 7.14 (#50603 / ADR-0010) — do not use |
| trust_remote_code | NO (native `Qwen3VLForConditionalGeneration`) | none |
| custom kernels / CUDA wheels | none | none |
| Paddle (VLM path) | none | none |
| precision | bf16 | gfx1100 bf16 ViT fixed on 7.14 (#6416) |
| VRAM | ~5–6 GB (2B bf16) | fits gfx1100 easily |
| transformers version | must expose `Qwen3VLForConditionalGeneration` | **VERIFY** the version in the GA-7.14 env |
| GPU | use `--gpu-ids 0,1,2` (exclude faulty GPU3) | known HW issue |

## GO/NO-GO + blockers

**Verdict: GO** — cleanest port in the queue (Apache×2, native class, no TRC/FA2/kernels, eval script already local). Establishes the v2 adapter template for the rest of the queue.

**Blockers for Steps 2–8 (execution), all environment, not FireRed:**
1. **Clone/weights access** — github.com + huggingface.co direct clone/download are BLOCKED in this container (WebFetch blocked; zread MCP works for READS but not clone). Cannot fetch `conv_for_infer.py` exact bytes or the 2B weights without a mirror/manual transfer.
2. **Exact SHAs UNVERIFIED** — upstream repo commit + HF weights revision must be pinned at scaffold time (fetch via zread/git when access allows); never import with floating `main`/`latest`.
3. **GA-7.14 env** — real 1651-page run needs torch 2.11+rocm7.14; migration-714 Stage 0 NOT yet executed (system env still on broken torch 2.9.1+rocm7.2). See [[migration-714-design-done]].
4. **GPU** — available (gfx1100 ×4, exclude GPU3); fine once env is migrated.

## Proposed Step 2 (scaffold `FireRed-OCR-ROCm`) — gated on blocker #1/#3

- Template from the most-complete existing repo (MinerU-ROCm or OvisOCR2-ROCm: full CLI + model_card_v2 + REPRO).
- Port the eval contract into `adapter/run_adapter.py` (transformers SDPA, bf16, 8192 tokens, exact PROMPT).
- `version`/`capabilities`/`doctor`/`parse` CLI; atomic per-page `.md` + resume; `model_card_v2` (code/weights Apache → `open-source-ai`); `rocmdoc.yaml`; `REPRO.yaml` (pin commits once fetched); hardware matrix; reproducibility.
- CPU/no-GPU contract smoke (synthetic, marked not-scored) — verifies interface only.
- Real smoke → 150-page gate → 1651 full all BLOCKED until env migrated + weights present.

## status: `PLANNED` (Preflight complete; ADAPTING blocked on env)
