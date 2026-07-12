"""Pytest conftest: make ``scripts/`` importable as a package.

``check_conformance.py`` lives in ``scripts/`` (not the engine package), so
``from scripts.check_conformance import check_repo`` only resolves when the repo
root is on ``sys.path``. pytest adds the rootdir for test collection, but we
insert it explicitly to make the import work regardless of invocation cwd.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
