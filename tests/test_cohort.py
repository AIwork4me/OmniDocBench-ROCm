"""Cohort manifest: deterministic freeze + field reality (Round-2 P0-2).

The manifest at contracts/cohort.json MUST equal freeze_cohort() (no hand-drift)
and every material field MUST be real (a 40-hex commit object that exists, a
schema sha256 that matches the actual artifact-schema.json at that commit, exit
codes + profiles that match the implementation, release labels that match the
cohort constants). These guard the manifest against silent drift and fabrication.
"""
import hashlib
import json
import subprocess
from pathlib import Path

from omnidocbench_rocm import cli_contract as cc
from omnidocbench_rocm import cohort as coh
from omnidocbench_rocm import conformance_profiles as cp

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "contracts" / "cohort.json"


def _git(*args):
    return subprocess.run(["git", "-C", str(REPO), *args],
                          capture_output=True, text=True, check=True).stdout.strip()


def _git_bytes(*args):
    return subprocess.run(["git", "-C", str(REPO), *args],
                          capture_output=True, check=True).stdout


def test_manifest_present_and_in_sync_with_freeze():
    """contracts/cohort.json must equal a fresh freeze_cohort() (no hand-drift)."""
    assert MANIFEST.exists(), "contracts/cohort.json missing — run scripts/freeze_cohort.py"
    committed = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert committed == coh.freeze_cohort(REPO)


def test_central_commit_is_a_real_40hex_commit_object():
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    c = doc["central_commit"]
    assert len(c) == 40 and all(ch in "0123456789abcdef" for ch in c.lower()), \
        f"central_commit {c!r} is not 40-hex"
    # the commit object must actually exist in the repo
    subprocess.run(["git", "-C", str(REPO), "cat-file", "-e", f"{c}^{{commit}}"],
                   check=True)


def test_schema_sha256_matches_real_artifact_schema_at_commit():
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    c = doc["central_commit"]
    blob = _git_bytes("show", f"{c}:contracts/artifact-schema.json")
    assert doc["artifact_schema"]["sha256"] == hashlib.sha256(blob).hexdigest(), \
        "artifact_schema.sha256 does not match the real schema at central_commit"
    assert doc["artifact_schema"]["$id"] == coh.ARTIFACT_SCHEMA_ID
    assert doc["artifact_schema"]["schema_version"] == coh.ARTIFACT_SCHEMA_VERSION


def test_exit_codes_and_profiles_match_implementation():
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert doc["cli_exit_codes"] == {str(v): k for k, v in cc.EXIT_CODES.items()}
    assert doc["conformance_profiles"] == list(cp.PROFILE_ORDER)


def test_release_labels_and_identity_match_constants():
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert doc["cohort_id"] == coh.COHORT_ID
    assert doc["contract_release"] == coh.CONTRACT_RELEASE
    assert doc["conformance_release"] == coh.CONFORMANCE_RELEASE
    assert doc["schema_version"] == coh.COHORT_MANIFEST_SCHEMA_VERSION
    assert doc["central_repository"] == "AIwork4me/OmniDocBench-ROCm"
    assert doc["result_identity"] == "v3"
