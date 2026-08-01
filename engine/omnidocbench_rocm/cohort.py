"""Central contract cohort manifest (Round-2 P0-2).

A single machine-readable statement of WHICH central contract a compatible
model repo locks:

  * the immutable central commit on the public default branch that carries the
    umbrella Standard (``contracts/ROCMDOC_STANDARD.md``);
  * the contract + conformance release labels;
  * the aggregate schema (``$id`` + content sha256 at that commit);
  * the conformance profile set;
  * the result-identity algorithm;
  * the standard exit codes;
  * the generator that produced the manifest.

Every field is DERIVED from real repo state — no hand-editing, no fabricated
SHA. :func:`freeze_cohort` is deterministic and idempotent, so a committed
``contracts/cohort.json`` can be drift-checked by re-running it. Model-repo
spec-locks MUST agree with this manifest (enforced by the zone consistency
check); a model repo locking a different central_commit / release / schema is on
a different cohort and MUST NOT claim round-2 parity.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

from . import cli_contract as cc
from . import conformance_profiles as cp

# Cohort identity + release labels. These advance by SemVer/RFC when the contract
# changes (Standard §14); they are the single source consumed by freeze_cohort,
# the spec-lock cohort block, and the zone consistency check.
COHORT_ID = "rocmdoc-1.0"
CONTRACT_RELEASE = "rocmdoc-contracts-0.4.0"
CONFORMANCE_RELEASE = "rocmdoc-conformance-0.4.0"
COHORT_MANIFEST_SCHEMA_VERSION = 1

ARTIFACT_SCHEMA_ID = "https://omnidocbench-rocm/schemas/artifact-schema.json"
ARTIFACT_SCHEMA_VERSION = 1
STANDARD_PATH = "contracts/ROCMDOC_STANDARD.md"
SCHEMA_PATH = "contracts/artifact-schema.json"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=True).stdout.strip()


def _git_bytes(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, check=True).stdout


def _ref_exists(repo: Path, ref: str) -> bool:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", ref],
                          capture_output=True).returncode == 0


def _default_branch(repo: Path) -> str:
    """The public default branch ref that carries the shipped contract.

    First available of ``main`` / ``origin/main`` / ``HEAD`` so the freeze is
    robust in local, CI, and shallow checkouts. The LOCKED commit is always taken
    from this branch (never a feature tip), so the manifest reflects what is
    actually shipped, not what is in flight.
    """
    for ref in ("main", "origin/main", "HEAD"):
        if _ref_exists(repo, ref):
            return ref
    raise RuntimeError("no git ref found to derive the locked contract commit")


def central_repository(repo: Path | str) -> str:
    """``OWNER/REPO`` parsed from the origin remote (fallback: the raw URL)."""
    url = _git(Path(repo), "remote", "get-url", "origin")
    m = re.search(r"github\.com[/:]([^/]+/[^/]+?)(?:\.git)?$", url)
    return m.group(1) if m else url


def locked_commit(repo: Path | str) -> str:
    """The immutable commit on the default branch carrying the umbrella Standard.

    Last non-merge commit on the default branch touching ``ROCMDOC_STANDARD.md``
    — the real, shipped contract commit (never a floating branch tip or a merge).
    """
    repo = Path(repo)
    ref = _default_branch(repo)
    return _git(repo, "log", "-1", "--no-merges", "--format=%H", ref,
                "--", STANDARD_PATH)


def _blob_sha256(repo: Path, commit: str, path: str) -> str:
    blob = _git_bytes(repo, "show", f"{commit}:{path}")
    return hashlib.sha256(blob).hexdigest()


def _first_match(pattern: str, text: str) -> str:
    m = re.search(pattern, text, re.MULTILINE)
    return m.group(1).strip() if m else "unknown"


def freeze_cohort(repo_root: Path | str) -> dict:
    """Derive the cohort manifest from real repo state (deterministic, idempotent).

    Reads only committed git content at the locked commit (never the working
    tree), so the manifest reflects the shipped contract exactly. Re-running on
    an unchanged contract reproduces the same bytes.
    """
    repo = Path(repo_root)
    commit = locked_commit(repo)
    commit_date = _git(repo, "show", "-s", "--format=%cI", commit)
    pyproject = _git_bytes(repo, "show", f"{commit}:pyproject.toml").decode("utf-8", "replace")
    standard = _git_bytes(repo, "show", f"{commit}:{STANDARD_PATH}").decode("utf-8", "replace")
    pkg = _first_match(r'^version\s*=\s*"([^"]+)"', pyproject)
    standard_version = _first_match(r"版本[：:]\s*([0-9][^\n]*)", standard)
    return {
        "schema_version": COHORT_MANIFEST_SCHEMA_VERSION,
        "cohort_id": COHORT_ID,
        "central_repository": central_repository(repo),
        "central_commit": commit,
        "central_commit_date": commit_date,
        "central_branch_at_lock": "main",
        "contract_release": CONTRACT_RELEASE,
        "conformance_release": CONFORMANCE_RELEASE,
        "central_package_version": pkg,
        "standard_version": standard_version,
        "artifact_schema": {
            "$id": ARTIFACT_SCHEMA_ID,
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "sha256": _blob_sha256(repo, commit, SCHEMA_PATH),
        },
        "conformance_profiles": list(cp.PROFILE_ORDER),
        "result_identity": "v3",
        "cli_exit_codes": {str(code): name for name, code in cc.EXIT_CODES.items()},
        "generator": {
            "tool": "omnidocbench-rocm",
            "command": "python scripts/freeze_cohort.py",
            "module": "omnidocbench_rocm.cohort.freeze_cohort",
            "version": pkg,
        },
    }
