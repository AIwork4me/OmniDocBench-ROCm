# Support

## How to get help

- **Using a model / reproducing a score:** read the model repo's `README.md`
  (`Evaluation` + `Reproducibility` sections) and
  [`docs/ci-reality.md`](docs/ci-reality.md) (why a green CI check is not the
  same as a real result).
- **Adding a model:** [`docs/contribute-a-model.md`](docs/contribute-a-model.md).
- **The adapter contract:** [`contracts/adapter.md`](contracts/adapter.md).
- **Backend policy (what is/isn't supported):**
  [`contracts/backend-policy.md`](contracts/backend-policy.md).
- **Bugs and feature requests:** open a GitHub issue using one of the issue
  templates (bug report, feature request, model onboarding).

## Trust model (read before relying on a number)

Scores carry a per-platform badge (`contracts/badge-policy.md`):

- `community-wanted` — no results for that platform yet.
- `community` — provenance-complete and conformant, self-attested (not
  independently reproduced).
- `verified` — a maintainer reproduced the result in a clean Docker environment.

CI verifies structure, not numbers. Read the badge, not the CI status, to know
how much to trust a score.
