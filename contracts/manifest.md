# Manifest Contract (rocmdoc.yaml)

`rocmdoc.yaml` is a **capability manifest** — a declaration of what a model CAN
do and under what license. It is emphatically **not** a benchmark result
(ADR-0009). Results live in `model_card.json` (v2) and the evidence bundle.

Schema: the `rocmdoc_manifest` `$def` of `contracts/artifact-schema.json`.

## Required top-level fields

| Field | Purpose |
|---|---|
| `schema_version` | `1` |
| `project` | `{name, repo, description}` — this adaptation repo |
| `upstream` | `{name, repo, revision}` — the upstream model project |
| `model` | `{id, version, task, arch}` |
| `licenses` | `{code: license_record, weights: license_record}` |
| `interfaces` | which surfaces: `standard-cli`, `adapter-script`, `api-server` |
| `implementations` | declared platform/backend/precision/interface/status entries |

## The load-bearing rule: result alignment

A published `result_record` may NOT claim a platform+backend the manifest does
NOT declare as `supported` or `experimental`. Concretely:

- A result on a platform the manifest **omits** → fake-support violation.
- A result on a platform the manifest marks `planned`/`unsupported` → violation.
- A result whose backend is not among the platform's declared backends →
  violation (unless the manifest declared the platform with backend `""`, a
  wildcard).

```bash
omnidocbench-rocm manifest rocmdoc.yaml --card model_card.json
# MANIFEST VALID  |  MANIFEST INVALID: <list>
```

This forbids "faking" a supported platform: you cannot publish a result for a
combination you have not declared.

## License records

Each of `licenses.code` / `licenses.weights` is a `license_record` (ADR-0010) with
a required `category` ∈ {`open-source-ai`, `open-weights`, `source-available`,
`restricted`, `closed`, `unknown`}. **Never default to `open-source-ai`** — use
`unknown` until the license is resolved. Weights and code may differ (e.g.
Apache-2.0 code, restricted weights).

## Agreement with capabilities

`<cli> capabilities --json` (standard CLI, ADR-0011) MUST agree with this
manifest's `implementations`. The CLI→adapter bridge reads capabilities from
`rocmdoc.yaml`, so the two cannot drift when the bridge is used.
