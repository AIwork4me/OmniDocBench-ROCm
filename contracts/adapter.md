# Adapter Contract (canonical)

This is the canonical, human-readable contract every per-model adapter must
satisfy. It is the single interface that makes scores **comparable across
models and across platforms**. The machine-checkable companion is
`scripts/check_conformance.py` (existence + signature + output convention); the
runtime types live in `engine/omnidocbench_amd/types.py`.

> Spec reference: §5.1 of
> `docs/superpowers/specs/2026-07-12-amd-doc-parsing-platform-foundation-design.md`.

---

## 1. The signature

```python
def run_adapter(img_dir: Path, out_dir: Path, *,
                platform: Literal["linux-rocm", "windows-hip"],
                config: AdapterConfig) -> RunSummary:
    """Write out_dir/<image_stem>.md (UTF-8) for every page image in img_dir."""
```

| Argument | Meaning |
|---|---|
| `img_dir` | Directory of page images (OmniDocBench v1.6 = 1651 pages). The adapter lists and sorts it itself. |
| `out_dir` | Predictions directory the adapter must create (`mkdir -p`) and write into. |
| `platform` | **Explicit arg.** The adapter branches on platform-specific serving: vLLM/ROCm on Linux, llama.cpp/HIP-GGUF or vLLM-rocm-win on Windows. Never infer the platform from the OS — the engine tells you. |
| `config` | An `AdapterConfig` (see §2). Carries weights paths, server URL, backend name, API model name. |

Returns a standardized `RunSummary` (§3). The reference implementation in
`template/{{cookiecutter.repo_name}}/adapter/run_adapter.py` is the worked
example — copy it and replace the `_infer` body.

### CLI form

The engine invokes the adapter as a **subprocess**
(`python adapter/run_adapter.py --img-dir ... --out-dir ... --platform ...`),
so `run_adapter.py` must also be runnable as a script with an `argparse`
`__main__` block (the template ships one). The `--platform` flag is required;
`--backend`, `--server-url`, `--api-model-name` populate the `config` dict.

---

## 2. `AdapterConfig` — where settings come from

```python
@dataclass
class AdapterConfig:
    weights_dir: Path | None = None
    server_url: str = ""          # vLLM / OpenAI-compatible server URL
    api_model_name: str = ""      # model name as registered on the server
    backend: str = ""             # vllm | llama-cpp-server | onnx-rocm | onnx-directml | smoke | ...
    extra: dict = field(default_factory=dict)
```

Source of truth, layered (later overrides earlier):

1. **`adapter/adapter_config.py`** — the module's `as_dict()` returns the
   defaults for this model (backend, server URL, weights dir, API model name).
   This is what makes a cloned repo runnable.
2. **`adapter/setup/.env.local`** — machine-specific overrides (absolute
   weights paths, the port a local server is on, a hosted endpoint URL). The
   `.env.local.example` in the template documents the keys. `.env.local` is
   gitignored; never commit it.
3. **CLI flags / engine `config` dict** — the engine's `infer` stage may pass
   `config={"backend": ..., "server_url": ..., "api_model_name": ...}`; these
   win over the module defaults.

The template's `_load_adapter_config()` shows the import dance that makes this
work whether the adapter runs as a package module or as a bare subprocess.

---

## 3. `RunSummary` and `_run_stats.json`

The adapter returns a `RunSummary` and writes it to
`out_dir/_run_stats.json`. The engine **consumes only this file + the `.md`
outputs** — it never imports the adapter.

```python
@dataclass
class RunSummary:
    count: int                       # total page images seen
    ok: int                          # wrote a .md successfully
    fail: int                        # per-page failure (caught, recorded)
    fallback: int                    # used a fallback path (recorded)
    limit_pages: int | None          # null = full set (required to publish)
    stats: list[PageStatus]          # per-page detail
    engine: str = ""                 # which backend ran

@dataclass
class PageStatus:
    image: str
    status: str                      # "ok" | "failed: <reason>" | "fallback: <reason>"
    error: str = ""
    seconds: float = 0.0
    attempts: int = 0
```

`_run_stats.json` shape (`schema_version: 1`):

```json
{
  "schema_version": 1,
  "count": 1651, "ok": 1648, "fail": 3, "fallback": 0,
  "limit_pages": null,
  "engine": "vllm",
  "stats": [{"image": "0000001.jpg", "status": "ok", "seconds": 1.4, "attempts": 1}, ...]
}
```

The engine reads `_run_stats.json` to: (a) gate `publish` — `limit_pages`
must be `null` to publish official evidence (full-set enforcement); (b) drive
the `run_summary.json` ok/fail/fallback counts; (c) detect a totally-dead run
(zero predictions).

---

## 4. The iron rules

These are non-negotiable. `check_conformance.py` enforces the structural ones;
the engine relies on the behavioral ones.

### R1 — Filesystem-decoupled (the engine never imports the adapter)

The engine invokes the adapter as a **subprocess** and consumes only
`out_dir/<image_stem>.md` + `out_dir/_run_stats.json`. The adapter may be
written in any language or stack that can write files and emit the stats JSON
— the contract is the filesystem boundary, not a Python import. This is what
makes the zone language-agnostic and keeps model dependencies out of the
scoring environment.

### R2 — Per-page failure → zero, run continues (never raise)

A failure on one page **must** be caught, recorded in `_run_stats.json` as a
`failed` `PageStatus`, and the run **continues** to the next page. The adapter
**must never raise** out of `run_adapter` for a per-page error. A missing page
scores zero downstream; a crashed adapter scores nothing and breaks the whole
run. Wrap the per-page inference in `try/except` (the template shows this).

### R3 — Output convention: one `<image_stem>.md` per page, UTF-8

For each `img_dir/<stem>.<ext>` the adapter writes
`out_dir/<stem>.md` (UTF-8). The stem is the image basename **without
extension**. One Markdown file per page image, no more, no less. The engine's
`save_name = basename(predictions_dir) + "_" + match_method`, so the
predictions directory name is what distinguishes runs (the `_cdm` suffix on a
CDM predictions dir prevents clobbering the Edit_dist-only run).

### R4 — Output conventions for scoring (so the matcher sees what it expects)

| Element | Convention |
|---|---|
| Formulas | LaTeX: inline `$...$`, display `$$...$$`. Do not pretty-print math as plain text. |
| Tables | HTML, LaTeX, or pipe tables — OmniDocBench's matcher normalizes all three. Pick one and be consistent. |
| Reading order | Document order (top-to-bottom, left-to-right as the document flows). The reading-order metric scores sequence divergence. |
| Images | Markdown image syntax `![](path)` is stripped by `md_tex_filter`; do not wrap figures in HTML `<div>` wrappers (they survive the filter and perturb text matching — see `pitfalls.md#official-pretty-markdown`). |

### R5 — Backend-agnostic

The adapter may call any inference backend — vLLM, llama.cpp, an ONNX runtime,
a remote API, a shell pipeline. The contract doesn't care. The template's
`adapter_config.py::BACKEND` and the `--backend` flag are how you tell the
adapter which path to take; branch on it inside `_infer`. The `smoke` backend
ships a no-GPU placeholder so the repo is runnable in CI without a GPU.

### R6 — Per-platform ONNX execution provider (when the model uses ONNX)

When the adapter uses an ONNX layout or pipeline model, the execution provider
is **platform-specific**:

| Platform | ONNX package | Execution provider |
|---|---|---|
| `linux-rocm` | `onnxruntime-rocm` | ROCm EP (`ROCMExecutionProvider`) |
| `windows-hip` | `onnxruntime-directml` | DirectML EP (`DmlExecutionProvider`), via Microsoft Olive for conversion/optimization |

Reference for the Windows DirectML path:
<https://ryzenai.docs.amd.com/en/latest/gpu/ryzenai_gpu.html>.

VLM serving is similarly platform-split: Linux → vLLM/ROCm; Windows →
llama.cpp/GGUF (HIP or Vulkan). See the per-model `docs/backends.md` for the
recommended backend per model type.

---

## 5. What the adapter must NOT do

- **Must not import eval/scoring code.** The adapter only emits Markdown. It
  never reads scores, never imports `pdf_validation`, never touches the
  OmniDocBench checkout.
- **Must not read or write `metric_result.json`, `run_summary.json`, or
  `provenance.json`.** Those are engine-owned (`publish` stage assembles them).
  The adapter writes only `.md` files and `_run_stats.json`.
- **Must not assume a specific working directory or a parent package.** It runs
  as a bare subprocess; use absolute paths from `img_dir`/`out_dir` and the
  `_load_adapter_config()` pattern for sibling imports.
- **Must not run CDM.** CDM is exclusively engine-owned
  (`engine/omnidocbench_amd/cdm/`), so contributors don't each fight the 20+
  debug sessions documented in `pitfalls.md`.
- **Must not fake `_run_stats.json`.** If inference didn't run, don't emit ok
  statuses. The engine's full-set enforcement and conformance checks rely on
  honest counts.

---

## 6. Reference implementation

The template's `adapter/run_adapter.py` is the canonical starting point:

```python
def run_adapter(img_dir, out_dir, *, platform, config):
    cfg = {**adapter_config.as_dict(), **config}
    out_dir.mkdir(parents=True, exist_ok=True)
    imgs = sorted(p for p in Path(img_dir).iterdir() if p.suffix.lower() in IMG_EXT)
    stats = []
    for i in imgs:
        try:
            md = _infer(i, platform, cfg)        # <- replace this
            (out_dir / f"{i.stem}.md").write_text(md, encoding="utf-8")
            stats.append(PageStatus(i.name, "ok", seconds=..., attempts=1))
        except Exception as e:                    # per-page fail -> record, continue
            stats.append(PageStatus(i.name, f"failed: {e}", error=str(e)))
    rs = RunSummary(len(imgs), ok=..., fail=..., fallback=..., limit_pages=cfg.get("limit_pages"), stats=stats, engine=cfg["backend"])
    rs.write(out_dir / "_run_stats.json")
    return rs.to_run_stats()
```

To onboard a model: copy the template, replace `_infer` with your model's
inference (img → Markdown), keep the signature, the `.md` convention, the
per-page `try/except`, and the `_run_stats.json` write. Nothing else in the
contract changes.

---

## 7. How the engine uses this

```
engine stage_infer:
    subprocess: python adapter/run_adapter.py --img-dir ... --out-dir ... --platform ...
    reads: out_dir/_run_stats.json  (RunSummary)
    never imports adapter/run_adapter.py
          |
          v
engine stage_score:
    consumes out_dir/*.md  via OmniDocBench pdf_validation.py (in eval-venv 3.11)
    produces metric_result.json
          |
          v
engine stage_publish:
    _assert_full_set(_run_stats.json)   # limit_pages must be null
    assembles run_summary.json + provenance.json
    runs check_conformance.py -> badge suggestion
```

The adapter's job ends at `_run_stats.json` + the `.md` files. Everything
downstream is the engine's responsibility.
