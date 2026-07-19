## Summary

<!-- What does this PR change, and why? -->

## Checklist

- [ ] `python -m pytest -q` is green
- [ ] `python scripts/check_brand.py` reports clean (it forbids pre-0.2.0 brand
      strings outside the sanctioned record files: `docs/superpowers/**`,
      `docs/audits/**`, `docs/adr/**`, `CHANGELOG.md`)
- [ ] `python scripts/validate_registry.py hub/registry.yaml` is valid (if the
      registry changed)
- [ ] Documentation updated where relevant
- [ ] No fabricated results; no auto-promotion to `verified`
- [ ] DirectML (if mentioned) is labelled a temporary Windows compatibility
      fallback; Vulkan/OpenVINO not recommended as backends

## Notes for reviewers

<!-- Anything non-obvious: a cross-file rename, a schema change, a CI gate. -->
