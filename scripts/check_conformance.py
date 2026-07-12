"""Legacy entrypoint — re-exports the engine's conformance checker.

The canonical implementation now lives in
:mod:`omnidocbench_amd.conformance` (installed with the engine). This shim
keeps existing callers working:

- Library: ``from scripts.check_conformance import check_repo`` (Task 9 tests)
- CLI: ``python scripts/check_conformance.py <repo-path>`` (platform CI)

For new callers prefer the installed engine directly::

    omnidocbench-amd conformance <repo-path>
"""
from omnidocbench_amd.conformance import check_repo, ConformanceReport, main, REQUIRED_README_SECTIONS

__all__ = ["check_repo", "ConformanceReport", "main", "REQUIRED_README_SECTIONS"]

if __name__ == "__main__":
    import sys; sys.exit(main(sys.argv[1:]))
