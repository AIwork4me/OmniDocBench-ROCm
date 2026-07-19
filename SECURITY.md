# Security Policy

## Reporting a vulnerability

Please **do not** open a public GitHub issue for a security vulnerability.
Instead, report it privately to the maintainers via GitHub's "Report a
vulnerability" feature on the repository, or open a private security advisory.

Include, where possible: a description of the issue, the affected component
(engine, template, contracts, CI), steps to reproduce, and any impact
assessment. We will acknowledge receipt and coordinate a fix and disclosure.

## Scope

This project is an evaluation/adaptation platform for document-parsing models on
ROCm. It does not run untrusted model weights in CI, and CI never reaches a
GPU. Issues concerning the upstream OmniDocBench scorer, model weights, or
third-party inference backends should be reported to their respective projects.

## Integrity expectations

- Do not commit fabricated evaluation results. The full-set enforcement
  (`limit_pages` must be `null` to publish) and the `metric_quality` fields
  exist to make faking hard.
- Do not commit secrets (`.env.local` is gitignored). Adapter weights and
  endpoints belong in machine-local config, not the repo.

## Supported versions

Only the latest 0.2.x line receives security fixes.
