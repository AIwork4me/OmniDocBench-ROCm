# Security Policy — {{cookiecutter.repo_name}}

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security problems. Report
privately so maintainers can assess and patch before disclosure.

- Preferred: use GitHub's **"Report a vulnerability"** (Security → Advisories) on
  this repo, OR email the maintainer listed in `MAINTAINERS.yaml`.
- If no private channel is configured yet, open a *non-sensitive* GitHub issue
  asking maintainers to set one up (ROCmDoc Standard §10 QS-0).

<!-- TODO: replace with a real private reporting address once confirmed. Do not
     commit a fabricated email. -->

## Scope

This is a **model adapter** repo. In scope: adapter code, the standard CLI,
model-serving wrappers, and repo hygiene (no committed credentials). Out of
scope: vulnerabilities in upstream model weights/frameworks (report upstream) and
the central evaluation engine (report at AIwork4me/OmniDocBench-ROCm).

## Hygiene expectations (ROCmDoc Standard QS-0)

- No tokens, credential URLs, private endpoints, or user documents committed.
- git remotes carry no credentials.
- CI runs with least privilege; third-party Actions pinned to immutable refs.
- Local removal of an exposed credential is NOT remediation — the owner MUST
  revoke/rotate it at the provider.
