# Governance

## Maintainers

OmniDocBench-ROCm is currently maintained by **@AIwork4me**
(see [`CODEOWNERS`](../CODEOWNERS)). The project is small; decisions are made by
the maintainer on the public record (PRs, issues, ADRs). As the contributor
base grows, maintainers can be added by PR to this file and `CODEOWNERS`.

## Decision records

Architecturally significant decisions are recorded as ADRs under
[`docs/adr/`](adr/):

- [ADR-0001 — ROCm project boundary](adr/0001-rocm-project-boundary.md)
- [ADR-0002 — Package and CLI migration; legacy surface dropped](adr/0002-package-and-cli-migration.md)

A new ADR is added when a decision is hard to reverse or non-obvious from the
code (the brand, the backend boundary, schema evolution, the trust model).

## Badge authority

- The `check_conformance` gate is **automated** and runs in CI; passing it is
  necessary for any badge.
- `community` badges are self-attested by a contributor who commits
  provenance-complete artifacts; CI verifies the structure.
- `verified` badges are **maintainer-assigned**: a maintainer reproduces the
  result in a clean Docker environment and commits a `VERIFIED.yaml`. No result
  is ever auto-promoted to `verified`.

See [`contracts/badge-policy.md`](../contracts/badge-policy.md).

## Brand and honesty

The product surface is kept free of the pre-0.2.0 brand by
`scripts/check_brand.py` (runs in CI). Documentation must match the code: there
is no fabricated Windows backend, no fabricated CDM toolchain, and no fabricated
result. The audit record is
[`docs/audits/2026-07-omnidocbench-rocm-migration-audit.md`](audits/2026-07-omnidocbench-rocm-migration-audit.md).

## Security

Report vulnerabilities privately (not via a public issue). See
[`SECURITY.md`](../SECURITY.md).
