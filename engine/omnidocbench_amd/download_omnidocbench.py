"""OmniDocBench dataset downloader (pinned revision).

Fetches the Hugging Face dataset ``opendatalab/OmniDocBench`` (the manifest JSON
plus the ``images/`` directory) for a given pinned revision into a managed
target directory. Ports ``download_dataset`` + ``VERSIONS`` from
``AIwork4me/PaddleOCR-VL-ROCm/eval/download_omnidocbench.py``.

Hard rule: the Hugging Face revision MUST be pinned for reproducibility. If
``revision is None``, :func:`download_dataset` raises ``SystemExit`` rather than
silently fetching latest. ``stages.stage_download`` enforces the same rule at
the orchestrator layer; this module enforces it independently so any direct
caller is also protected.
"""
from __future__ import annotations

import logging
from pathlib import Path

from huggingface_hub import snapshot_download

DEFAULT_REPO_ID = "opendatalab/OmniDocBench"

# Fetch the manifest JSON plus the images/ directory. The manifest filename has
# historically been ``OmniDocBench.json``; pull any top-level json plus the
# whole images/ tree to be robust to renames.
ALLOW_PATTERNS = ["*.json", "images/*"]

# Pinned Hugging Face revisions per OmniDocBench version.
# v1.6 = current default dataset (~1,651 pages, matching the OmniDocBench repo's
# ``master`` branch); v1.5 = earlier branch (~1,355 pages). Revisions must be
# pinned (never None) so downloads are reproducible. Callers pass the resolved
# revision into ``download_dataset``; this table is the source of truth for the
# default pin per version.
VERSIONS: dict[str, str] = {
    "v15": "v1.5",
    "v16": "v1.6",
}

log = logging.getLogger("download_omnidocbench")


def download_dataset(
    repo_id: str,
    target: Path,
    revision: str | None,
    *,
    cache_dir: Path | None = None,
) -> Path:
    """Download the manifest + images into ``target`` via ``snapshot_download``.

    Parameters
    ----------
    repo_id:
        Hugging Face dataset repo id (e.g. ``opendatalab/OmniDocBench``).
    target:
        Local directory to materialize the snapshot into.
    revision:
        Pinned Hugging Face revision/branch/commit. **Must not be None** —
        raising here is the reproducibility guard. ``stages.stage_download``
        checks the same condition, but this function enforces it independently.
    cache_dir:
        Optional Hugging Face cache directory.

    Returns
    -------
    Path
        The resolved local directory holding the manifest (``target``).

    Raises
    ------
    SystemExit
        If ``revision is None``.
    """
    if revision is None:
        raise SystemExit(
            "OmniDocBench revision must be pinned for reproducibility (got None)."
        )

    local_dir = snapshot_download(
        repo_id=repo_id,
        revision=revision,
        repo_type="dataset",
        allow_patterns=ALLOW_PATTERNS,
        local_dir=str(target),
        cache_dir=str(cache_dir) if cache_dir else None,
    )
    resolved = Path(local_dir)
    if not resolved.exists():
        raise SystemExit(f"snapshot_download reported a missing directory: {resolved}")
    return resolved
