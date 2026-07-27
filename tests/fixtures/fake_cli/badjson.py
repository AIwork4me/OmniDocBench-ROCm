"""Fake standard-CLI fixture: the 'badjson' behavior.

Invoked by tests/test_conformance_profiles.py via subprocess to exercise the
behavioral conformance profiles without a GPU. See _common.py for the dispatch.
"""
from _common import main

if __name__ == "__main__":
    raise SystemExit(main("badjson"))
