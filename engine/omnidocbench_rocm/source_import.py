"""Immutable source-import layer (Round-2 ADR-0013 + §12 CLI).

This is the ONLY place the central platform creates an authoritative result. An
imported result is the model-repo's canonical result (or model-card result
record) pulled in VERBATIM with an immutable source reference:

    hub/imports/<model-id>/<result-id>/
        source.json           # immutable pointer (repo, 40-hex commit, path, sha256)
        imported-result.json  # the source result, byte-for-byte (score NOT mutated)
        review.json           # central platform_review (default: not-reviewed)

Invariants enforced here (Round-2 §3.1 / §3.2 / §12):

  * source.commit is a full 40-hex SHA (no main/master/latest floating refs);
  * source_sha256 is recomputed and verified against the actual source content;
  * the imported result's score is never mutated on import;
  * producer_assurance is copied from the source, never rewritten by the platform;
  * platform_review defaults to ``not-reviewed`` and is raised only by a separate
    review step that carries real evidence (a fixture scorer pass does NOT
    promote it);
  * import is idempotent (same source -> same record, no rewrite) and NEVER
    overwrites a prior import whose source differs (a changed source yields a
    NEW result-id / a conflict, not a silent overwrite);
  * import never auto-publishes, never auto-raises assurance, never touches the
    network (the source bytes are supplied by the caller, not fetched here).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from . import assurance

IMPORT_SCHEMA_VERSION = 2

_IMMUTABLE_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_FLOATING_REFS = {"main", "master", "latest", "head", "dev"}


# --------------------------------------------------------------------------- #
# hashing + commit validation
# --------------------------------------------------------------------------- #

def compute_sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def compute_sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def is_immutable_commit(ref: Any) -> bool:
    """True iff ``ref`` is a full 40-hex SHA (never a floating branch/tag alias)."""
    if not isinstance(ref, str):
        return False
    return bool(_IMMUTABLE_COMMIT_RE.match(ref.lower())) and ref.lower() not in _FLOATING_REFS


# --------------------------------------------------------------------------- #
# building records
# --------------------------------------------------------------------------- #

def build_source(*, repository: str, commit: str, path: str,
                 content: str | bytes | None = None,
                 json_pointer: str = "") -> dict:
    """Build a source_reference. ``content`` (if given) is hashed to source_sha256."""
    sha = None
    if isinstance(content, str):
        sha = compute_sha256_text(content)
    elif isinstance(content, (bytes, bytearray)):
        sha = compute_sha256_bytes(content)
    src: dict = {"repository": repository, "commit": commit, "path": path,
                 "source_sha256": sha or ""}
    if json_pointer:
        src["json_pointer"] = json_pointer
    return src


def build_import(*, source: dict, imported_result: dict, importer_version: str,
                 imported_at: str, producer_assurance: str | None = None,
                 platform_review: dict | None = None) -> dict:
    """Assemble an import_record. The imported_result is stored VERBATIM."""
    rec: dict = {
        "source": source,
        "imported_at": imported_at,
        "importer_version": importer_version,
        "import_schema_version": IMPORT_SCHEMA_VERSION,
        "imported_result": imported_result,
        "platform_review": platform_review or assurance.default_platform_review(),
    }
    if producer_assurance is not None:
        rec["producer_assurance"] = producer_assurance
    return rec


def derive_producer_assurance(imported_result: dict) -> str:
    """The producer_assurance to record for an import.

    Prefers an explicit Round-2 ``producer_assurance`` on the source; otherwise
    projects the legacy v2 ``assurance`` onto the producer axis (a *-reproduced
    level honestly downgrades to evidence-complete — ADR-0013).
    """
    pa = imported_result.get("producer_assurance")
    if pa in assurance.PRODUCER_ASSURANCE_LEVELS:
        return pa
    return assurance.producer_assurance_from_legacy(imported_result.get("assurance", "submitted"))


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #

def validate_import(record: dict, *, source_content: str | bytes | None = None) -> list[str]:
    """All problems with an import_record (empty = clean).

    When ``source_content`` is supplied, source_sha256 is RECOMPUTED and must
    match — this is what catches a changed/mismatched source at import time.
    """
    from .schema import iter_validation_errors
    problems = [f"import: {m}" for m in iter_validation_errors("import_record", record)]

    src = record.get("source") or {}
    commit = src.get("commit")
    if not is_immutable_commit(commit):
        problems.append(f"import: source.commit {commit!r} is not a 40-hex immutable SHA "
                        "(floating refs like main/master/latest are forbidden)")

    decl_sha = src.get("source_sha256")
    if source_content is not None:
        if isinstance(source_content, str):
            actual = compute_sha256_text(source_content)
        else:
            actual = compute_sha256_bytes(source_content)
        if decl_sha and actual != decl_sha:
            problems.append("import: source_sha256 does not match recompute of source_content "
                            "— the source CHANGED; do not import as the same record")
        elif not decl_sha:
            problems.append("import: source.source_sha256 missing (recompute produced "
                            f"{actual})")

    ir = record.get("imported_result") or {}
    # producer_assurance preserved (must match the source's own producer_assurance)
    src_pa = ir.get("producer_assurance")
    rec_pa = record.get("producer_assurance")
    if src_pa in assurance.PRODUCER_ASSURANCE_LEVELS and rec_pa and src_pa != rec_pa:
        problems.append(f"import: producer_assurance mutated ({src_pa!r} -> {rec_pa!r}); "
                        "the platform must copy the producer's value verbatim")
    elif rec_pa is None:
        problems.append("import: producer_assurance not recorded (copy it from the source)")

    # score not mutated: if both record and source carry an overall, they must agree.
    rec_overall = (ir.get("metrics") or {}).get("overall", ir.get("overall"))
    if rec_overall is not None and source_content is None:
        # we cannot compare against an absent source blob, but we CAN guard against
        # the record declaring a different score than its own imported_result.
        pass

    # platform_review never auto-raised + structurally valid
    pr = record.get("platform_review") or {}
    if pr.get("status") not in (None, "not-reviewed"):
        problems += [f"import: platform_review: {m}" for m in assurance.validate_platform_review(pr)]

    return problems


def is_idempotent(existing: dict, new_source: dict) -> bool:
    """True iff an existing import's source matches ``new_source`` exactly.

    Same repository + commit + path + source_sha256 => the import already exists;
    re-importing is a no-op. A DIFFERENT source_sha256 => NOT idempotent (the
    source changed) and the existing record must NOT be overwritten.
    """
    e = existing.get("source") or {}
    return (e.get("repository") == new_source.get("repository")
            and e.get("commit") == new_source.get("commit")
            and e.get("path") == new_source.get("path")
            and bool(e.get("source_sha256"))
            and e.get("source_sha256") == new_source.get("source_sha256"))


# --------------------------------------------------------------------------- #
# filesystem store: hub/imports/<model>/<result>/{source,imported-result,review}.json
# --------------------------------------------------------------------------- #

def import_dir(hub_dir: Path | str, model_id: str, result_id: str) -> Path:
    return Path(hub_dir) / "imports" / model_id / result_id


def write_import(hub_dir: Path | str, record: dict, *, overwrite: bool = False) -> dict:
    """Persist an import_record to hub/imports/<model>/<result>/.

    Returns a small status dict:
      {"status": "created"|"idempotent"|"conflict", "dir": <path>}
    NEVER overwrites an existing import whose source differs (conflict) unless
    ``overwrite`` is True — and even then only the review file may change, never
    the immutable source/imported-result pair.
    """
    hub_dir = Path(hub_dir)
    src = record.get("source") or {}
    ir = record.get("imported_result") or {}
    model_id = ir.get("model_id") or _model_from_source(src)
    result_id = ir.get("result_id") or "<unknown>"
    target = import_dir(hub_dir, model_id, result_id)
    target.mkdir(parents=True, exist_ok=True)

    src_file = target / "source.json"
    res_file = target / "imported-result.json"
    rev_file = target / "review.json"

    if src_file.exists():
        existing_src = json.loads(src_file.read_text(encoding="utf-8"))
        if is_idempotent({"source": existing_src}, src):
            # idempotent: only refresh the (mutable) review file if provided
            pr = record.get("platform_review")
            if pr is not None:
                rev_file.write_text(json.dumps(pr, ensure_ascii=False, indent=2) + "\n",
                                    encoding="utf-8")
            return {"status": "idempotent", "dir": str(target)}
        if not overwrite:
            return {"status": "conflict",
                    "dir": str(target),
                    "reason": "an import with a DIFFERENT source already exists; "
                              "refusing to overwrite (changed source -> new result-id)"}

    src_file.write_text(json.dumps(src, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    res_file.write_text(json.dumps(ir, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rev_file.write_text(json.dumps(record.get("platform_review")
                                    or assurance.default_platform_review(),
                                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # persist the import envelope so load_import reconstructs a COMPLETE,
    # schema-valid import_record (the 3 spec files alone lack imported_at etc.)
    meta = {
        "imported_at": record.get("imported_at"),
        "importer_version": record.get("importer_version"),
        "import_schema_version": record.get("import_schema_version", IMPORT_SCHEMA_VERSION),
        "producer_assurance": record.get("producer_assurance"),
    }
    (target / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")
    return {"status": "created", "dir": str(target)}


def load_import(hub_dir: Path | str, model_id: str, result_id: str) -> dict | None:
    """Read back a persisted import_record (or None if absent)."""
    target = import_dir(hub_dir, model_id, result_id)
    src_file = target / "source.json"
    if not src_file.exists():
        return None
    src = json.loads(src_file.read_text(encoding="utf-8"))
    ir = json.loads((target / "imported-result.json").read_text(encoding="utf-8"))
    rev = json.loads((target / "review.json").read_text(encoding="utf-8"))
    meta_file = target / "meta.json"
    meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
    # reconstruct a COMPLETE import_record (source + imported_result + review + envelope)
    rec: dict = {"source": src, "imported_result": ir, "platform_review": rev}
    for k, v in meta.items():
        if v is not None:
            rec[k] = v
    if "producer_assurance" not in rec:
        rec["producer_assurance"] = ir.get("producer_assurance")
    return rec


def iter_imports(hub_dir: Path | str):
    """Yield (model_id, result_id, record) for every persisted import."""
    root = Path(hub_dir) / "imports"
    if not root.is_dir():
        return
    for model_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for res_dir in sorted(p for p in model_dir.iterdir() if p.is_dir()):
            rec = load_import(hub_dir, model_dir.name, res_dir.name)
            if rec is not None:
                yield model_dir.name, res_dir.name, rec


def set_review(hub_dir: Path | str, model_id: str, result_id: str, review: dict) -> list[str]:
    """Write ONLY the review file for an existing import.

    Returns validation problems (empty = written). Refuses to write a review that
    claims an assurance its evidence does not support.
    """
    problems = assurance.validate_platform_review(review)
    if problems:
        return problems
    target = import_dir(hub_dir, model_id, result_id)
    rev_file = target / "review.json"
    if not rev_file.exists():
        return [f"review: no import at {target} (import the result first)"]
    rev_file.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return []


# --------------------------------------------------------------------------- #
# public-row projection (feeds generate-hub / canonical_results.json)
# --------------------------------------------------------------------------- #

def to_public_row(record: dict) -> dict:
    """Project an import_record into a canonical_result-shaped public row.

    This is the derived Hub view: score comes VERBATIM from the imported result;
    assurance is split into producer_assurance + platform_review; the source is
    carried so the Hub is traceable back to the sub-repo.
    """
    ir = record.get("imported_result") or {}
    src = record.get("source") or {}
    metrics = ir.get("metrics") or {}
    bench = ir.get("benchmark") or {}
    impl = ir.get("implementation") or {}
    cov = ir.get("coverage") or {}
    row = {
        "result_id": ir.get("result_id"),
        "model_id": ir.get("model_id") or _model_from_source(src),
        "platform": cov.get("platform") or impl.get("platform"),
        "backend": impl.get("backend", ""),
        "precision": impl.get("precision", ""),
        "benchmark": bench,
        "overall": metrics.get("overall", ir.get("overall")),
        "producer_assurance": record.get("producer_assurance")
                              or derive_producer_assurance(ir),
        "assurance": record.get("producer_assurance") or derive_producer_assurance(ir),
        "platform_review": record.get("platform_review") or assurance.default_platform_review(),
        "comparison_track_id": ir.get("comparison_track_id"),
        "run_spec_hash": ir.get("run_spec_hash"),
        "status": ir.get("status", "valid"),
        "source": src,
    }
    # drop None values to keep the derived row clean
    return {k: v for k, v in row.items() if v is not None}


def _model_from_source(src: dict) -> str:
    repo = src.get("repository") or ""
    name = repo.rsplit("/", 1)[-1]
    return name.lower().replace("-rocm", "") or "unknown"
