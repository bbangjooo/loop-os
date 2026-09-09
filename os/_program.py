"""Program identity and declared progress; never a goal-completion evaluator."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Any

from _canon import digest_file

PROGRESS_KINDS = ("outcome", "learning", "preparation", "no_change")
GUARD_ID = "loop-os-program-digest"
_PROGRESS_FIELDS = {"kind", "criterion", "delta", "evidence_refs", "remaining", "next_action"}


def validate_declaration(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != {"path", "digest"}:
        raise ValueError("program must contain exactly path and digest")
    path = value["path"]
    if (not isinstance(path, str) or not path.strip() or Path(path).is_absolute()
            or ".." in Path(path).parts or Path(path) == Path(".")):
        raise ValueError("program.path must be a file path inside the project")
    digest = value["digest"]
    if (not isinstance(digest, str) or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)):
        raise ValueError("program.digest must be a lowercase SHA-256 hex digest")


def check_binding(project: Path, binding: dict[str, str] | None) -> None:
    if binding is None:
        return
    validate_declaration(binding)
    path = project / binding["path"]
    try:
        if not path.resolve().is_relative_to(project.resolve()):
            raise ValueError("program.path resolves outside the project")
        if not path.is_file() or digest_file(path) != binding["digest"]:
            raise ValueError("program is missing or changed; restore the pinned version or review a new contract")
    except OSError as error:
        raise ValueError(f"cannot read pinned program: {error}") from error


def digest_guard(binding: dict[str, str]) -> dict[str, Any]:
    # Ordinary kernel guard, checked at entry and after mutations. Integrity
    # paths alone only compare to the bytes present when a run starts.
    return {
        "id": GUARD_ID,
        "kind": "exit_zero",
        "command": [
            sys.executable, "-c",
            "import hashlib,pathlib,sys; p=pathlib.Path(sys.argv[1]); "
            "sys.exit(0 if p.resolve().is_relative_to(pathlib.Path.cwd().resolve()) "
            "and p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==sys.argv[2] else 1)",
            binding["path"], binding["digest"],
        ],
        "timeout_seconds": 30,
    }


def validate_progress(value: Any, run_id: str, event_ids: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != _PROGRESS_FIELDS:
        raise ValueError(f"program_progress must contain exactly {sorted(_PROGRESS_FIELDS)}")
    if value["kind"] not in PROGRESS_KINDS:
        raise ValueError(f"program_progress.kind must be one of {PROGRESS_KINDS}")
    for key in ("criterion", "delta", "next_action"):
        text = value[key]
        if not isinstance(text, str) or not text.strip() or "REPLACE_ME" in text:
            raise ValueError(f"program_progress.{key} must be non-empty text without REPLACE_ME")
    for key in ("evidence_refs", "remaining"):
        items = value[key]
        if not isinstance(items, list) or not all(
            isinstance(s, str) and s.strip() and "REPLACE_ME" not in s for s in items
        ):
            raise ValueError(f"program_progress.{key} must be a list of non-empty strings")
    refs = value["evidence_refs"]
    if run_id not in refs or not set(refs) <= event_ids:
        raise ValueError("program_progress.evidence_refs must include this run seal and only existing journal event ids")


def project_progress(project: Path, state: Any) -> dict[str, Any]:
    """Journal-derived declarations. No semantic grading or completion claim."""
    binding = state.program
    if binding is None:
        return {"status": "UNBOUND", "program": None, "completion": "NOT_EVALUATED"}
    integrity_error = None
    try:
        check_binding(project, binding)
        integrity = "MATCH"
    except ValueError as error:
        integrity = "UNAVAILABLE_OR_CHANGED"
        integrity_error = str(error)
    runs = [r for r in state.runs_sealed if r["body"].get("program") == binding]
    diagnoses = {d["body"]["run_seal_id"]: d for d in state.diagnoses}
    reports = []
    last_outcome = -1
    for index, run in enumerate(runs):
        diagnosis = diagnoses.get(run["event_id"])
        body = diagnosis["body"] if diagnosis else {}
        progress = body.get("program_progress")
        if body.get("program") != binding or progress is None:
            continue
        if progress["kind"] == "outcome":
            last_outcome = index
        reports.append({
            "run_seal_id": run["event_id"],
            "diagnosis_event_id": diagnosis["event_id"],
            "diagnosis_digest": body["diagnosis_digest"],
            **progress,
        })
    return {
        "status": "BOUND",
        "program": binding,
        "program_integrity": integrity,
        "integrity_error": integrity_error,
        "reported_runs": len(reports),
        "unreported_runs": len(runs) - len(reports),
        "declared_by_kind": dict(Counter(r["kind"] for r in reports)),
        "runs_since_last_declared_outcome": len(runs) - last_outcome - 1,
        "latest": reports[-1] if reports else None,
        "completion": "NOT_EVALUATED",
        "note": "Kinds are author declarations, not verified goal progress; missing reports are unknown, not no_change.",
    }
