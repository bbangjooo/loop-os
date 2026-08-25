"""Opt-in full-auto authority and evidence-preserving journal recovery.

Full-auto is deliberately a project-local capability, not a global default.
The user invokes the harness command once; this instrument records that grant
in a tracked file and, when possible, in the journal.  Other instruments trust
only the grant file's validated shape and digest.

Journal recovery never deletes the damaged bytes.  It archives the original
journal and anchor, rebuilds a canonical chain from the currently readable
event records, seals the agent's decision file, and writes a fresh anchor.
The recovery therefore restores liveness without pretending the incident did
not happen.

Instrument surface:
    python os/autonomy.py enable  --project DIR --approved-by TEXT --statement TEXT
    python os/autonomy.py disable --project DIR --reason TEXT
    python os/autonomy.py status  --project DIR
    python os/autonomy.py recover --project DIR --decision FILE [--project-id ID]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path
from typing import Any

import journal
from _canon import canonical_json, digest_bytes, digest_file


GRANT_SCHEMA = "loop-os-full-auto-v1"
GRANT_NAME = ".loop-os-full-auto.json"
GRANT_SCOPES = ("constitutional_jump", "journal_recovery", "continuous_goal")
RECOVERY_DECISION_FIELDS = (
    "damage_assessment",
    "evidence_considered",
    "continuation_rationale",
    "accepted_uncertainty",
)


class AutonomyError(RuntimeError):
    """A full-auto grant or recovery input is absent or invalid."""


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def grant_path(project: Path) -> Path:
    return project.resolve() / GRANT_NAME


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_bytes(data)
    temporary.replace(path)


def _archive_once(path: Path, data: bytes) -> None:
    """Idempotently preserve evidence; never overwrite conflicting bytes."""
    if path.exists():
        if path.read_bytes() != data:
            raise AutonomyError(f"recovery archive collision at {path}")
        return
    _atomic_write(path, data)


def _load_object(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise AutonomyError(f"{label} file not found: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise AutonomyError(f"{label} is not valid JSON: {error}") from error
    if not isinstance(value, dict):
        raise AutonomyError(f"{label} must be a JSON object")
    return value


def load_grant(project: Path, *, required_scope: str | None = None) -> dict[str, Any]:
    path = grant_path(project)
    grant = _load_object(path, "full-auto grant")
    if grant.get("schema") != GRANT_SCHEMA:
        raise AutonomyError(f"full-auto grant has wrong schema: {grant.get('schema')!r}")
    if grant.get("enabled") is not True:
        raise AutonomyError("full-auto mode is disabled")
    if not str(grant.get("approved_by", "")).strip():
        raise AutonomyError("full-auto grant carries no approved_by")
    if not str(grant.get("statement", "")).strip():
        raise AutonomyError("full-auto grant carries no statement")
    scopes = grant.get("scopes")
    if not isinstance(scopes, list) or any(scope not in GRANT_SCOPES for scope in scopes):
        raise AutonomyError("full-auto grant carries invalid scopes")
    if required_scope is not None and required_scope not in scopes:
        raise AutonomyError(f"full-auto grant does not authorize {required_scope!r}")
    return grant


def enable(project: Path, approved_by: str, statement: str) -> dict[str, Any]:
    project = project.resolve()
    if not approved_by.strip() or not statement.strip():
        raise AutonomyError("enable requires non-empty approved_by and statement")
    grant = {
        "schema": GRANT_SCHEMA,
        "enabled": True,
        "approved_by": approved_by.strip(),
        "statement": statement.strip(),
        "scopes": list(GRANT_SCOPES),
        "granted_at": _now(),
    }
    path = grant_path(project)
    _atomic_write(path, (json.dumps(grant, indent=2, ensure_ascii=True) + "\n").encode("utf-8"))
    event_id = None
    journal_status = "RECORDED"
    try:
        journal.load_events(project)
        journal.check_anchor(project)
        event = journal.append_event(
            project,
            "autonomy_changed.v1",
            {
                "enabled": True,
                "grant_path": GRANT_NAME,
                "grant_digest": digest_file(path),
                "approved_by": grant["approved_by"],
                "statement": grant["statement"],
                "scopes": grant["scopes"],
            },
        )
        event_id = event["event_id"]
    except journal.JournalError:
        # Enabling must remain possible when the very reason for entering
        # full-auto is a broken journal.  Recovery will cite the grant digest.
        journal_status = "PENDING_RECOVERY"
    return {
        "status": "FULL_AUTO_ENABLED",
        "grant_path": str(path),
        "grant_digest": digest_file(path),
        "journal_status": journal_status,
        **({"event_id": event_id} if event_id else {}),
    }


def disable(project: Path, reason: str) -> dict[str, Any]:
    project = project.resolve()
    if not reason.strip():
        raise AutonomyError("disable requires a non-empty reason")
    current = load_grant(project)
    disabled = {
        **current,
        "enabled": False,
        "disabled_at": _now(),
        "disable_reason": reason.strip(),
    }
    path = grant_path(project)
    _atomic_write(path, (json.dumps(disabled, indent=2, ensure_ascii=True) + "\n").encode("utf-8"))
    event_id = None
    try:
        event_id = journal.append_event(
            project,
            "autonomy_changed.v1",
            {
                "enabled": False,
                "grant_path": GRANT_NAME,
                "grant_digest": digest_file(path),
                "reason": reason.strip(),
            },
        )["event_id"]
    except journal.JournalError:
        pass
    return {
        "status": "FULL_AUTO_DISABLED",
        "grant_path": str(path),
        **({"event_id": event_id} if event_id else {}),
    }


def status(project: Path) -> dict[str, Any]:
    project = project.resolve()
    path = grant_path(project)
    if not path.exists():
        return {"status": "FULL_AUTO_DISABLED", "reason": "grant file absent"}
    grant = _load_object(path, "full-auto grant")
    return {
        "status": "FULL_AUTO_ENABLED" if grant.get("enabled") is True else "FULL_AUTO_DISABLED",
        "grant_path": str(path),
        "grant_digest": digest_file(path),
        "approved_by": grant.get("approved_by"),
        "scopes": grant.get("scopes", []),
    }


def _validate_decision(path: Path) -> dict[str, Any]:
    decision = _load_object(path, "recovery decision")
    if decision.get("verdict") != "RECOVER_AND_CONTINUE":
        raise AutonomyError("recovery decision verdict must be RECOVER_AND_CONTINUE")
    for field in RECOVERY_DECISION_FIELDS:
        value = decision.get(field)
        if not isinstance(value, str) or not value.strip():
            raise AutonomyError(f"recovery decision field {field!r} must be non-empty text")
    return decision


def _recoverable_event(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("journal_schema") == journal.JOURNAL_SCHEMA
        and value.get("kind") in journal.EVENT_KINDS
        and isinstance(value.get("event_id"), str)
        and isinstance(value.get("recorded_at"), str)
        and isinstance(value.get("body"), dict)
    )


def recover(
    project: Path,
    decision_path: Path,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Archive damaged bytes and accept the readable current records as a
    new canonical chain.  Invalid records are preserved only in the archive
    and listed in the recovery event.  If no bootstrap survives, a new genesis
    requires an explicit project id and cites the damaged journal as lineage."""
    project = project.resolve()
    grant = load_grant(project, required_scope="journal_recovery")
    _validate_decision(decision_path)

    path = journal.journal_path(project)
    original = path.read_bytes() if path.exists() else b""
    original_digest = digest_bytes(original)
    anchor = journal.anchor_path(project)
    original_anchor = anchor.read_bytes() if anchor.exists() else b""
    recovery_dir = project / journal.JOURNAL_DIR / "recovery" / (
        f"{_stamp()}-{original_digest[:12]}"
    )
    recovery_dir.mkdir(parents=True, exist_ok=True)
    _archive_once(recovery_dir / "events.original.jsonl", original)
    if original_anchor:
        _archive_once(recovery_dir / "anchor.original.json", original_anchor)
    _archive_once(recovery_dir / "decision.json", decision_path.read_bytes())
    _archive_once(recovery_dir / "grant.json", grant_path(project).read_bytes())

    retained: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    seen_event_ids: set[str] = set()
    bootstrap_seen = False
    raw_lines = original.splitlines()
    for index, raw_line in enumerate(raw_lines, start=1):
        try:
            value = json.loads(raw_line)
        except json.JSONDecodeError:
            dropped.append({"line": index, "digest": digest_bytes(raw_line), "reason": "invalid_json"})
            continue
        if not _recoverable_event(value):
            dropped.append({"line": index, "digest": digest_bytes(raw_line), "reason": "invalid_event"})
            continue
        if value["event_id"] in seen_event_ids:
            dropped.append({"line": index, "digest": digest_bytes(raw_line), "reason": "duplicate_event_id"})
            continue
        if value["kind"] == "bootstrap.v1":
            if bootstrap_seen:
                dropped.append({"line": index, "digest": digest_bytes(raw_line), "reason": "extra_bootstrap"})
                continue
            bootstrap_seen = True
        elif not bootstrap_seen:
            dropped.append({"line": index, "digest": digest_bytes(raw_line), "reason": "before_bootstrap"})
            continue
        seen_event_ids.add(value["event_id"])
        retained.append(value)

    if not bootstrap_seen:
        if not project_id or not project_id.strip():
            raise AutonomyError(
                "no recoverable bootstrap event; pass --project-id to create a recovery genesis"
            )
        retained = [
            {
                "journal_schema": journal.JOURNAL_SCHEMA,
                "event_id": "ev-recovery-genesis-" + original_digest[:12],
                "kind": "bootstrap.v1",
                "recorded_at": _now(),
                "prev": journal.GENESIS,
                "body": {
                    "project_id": project_id.strip(),
                    "lineage": [{"name": "damaged-journal", "digest": original_digest}],
                },
            }
        ]

    rebuilt_lines: list[bytes] = []
    previous = journal.GENESIS
    for event in retained:
        event = {**event, "prev": previous}
        line = canonical_json(event).encode("utf-8")
        rebuilt_lines.append(line)
        previous = digest_bytes(line)
    _atomic_write(path, b"".join(line + b"\n" for line in rebuilt_lines))
    # Prove the reconstructed prefix is internally valid before extending it.
    journal.load_events(project)

    recovery_event = journal.append_event(
        project,
        "journal_recovered.v1",
        {
            "strategy": "accept-readable-current-records-and-rechain",
            "original_journal_digest": original_digest,
            "original_anchor_digest": digest_bytes(original_anchor) if original_anchor else None,
            "archive_path": str(recovery_dir.relative_to(project)),
            "decision_path": str(decision_path),
            "decision_digest": digest_file(decision_path),
            "grant_digest": digest_file(grant_path(project)),
            "retained_events": len(retained),
            "dropped_records": dropped,
        },
    )
    anchor_payload = journal.write_anchor(project)
    return {
        "status": "JOURNAL_RECOVERED",
        "event_id": recovery_event["event_id"],
        "original_journal_digest": original_digest,
        "archive_path": str(recovery_dir),
        "retained_events": len(retained),
        "dropped_records": len(dropped),
        "new_head": anchor_payload["head"],
        "next_required": "run journal status and continue from its next_required action",
    }


def _emit(payload: dict[str, Any], *, ok: bool = True) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="autonomy")
    sub = parser.add_subparsers(dest="command", required=True)

    enable_parser = sub.add_parser("enable")
    enable_parser.add_argument("--project", type=Path, required=True)
    enable_parser.add_argument("--approved-by", required=True)
    enable_parser.add_argument("--statement", required=True)

    disable_parser = sub.add_parser("disable")
    disable_parser.add_argument("--project", type=Path, required=True)
    disable_parser.add_argument("--reason", required=True)

    status_parser = sub.add_parser("status")
    status_parser.add_argument("--project", type=Path, required=True)

    recover_parser = sub.add_parser("recover")
    recover_parser.add_argument("--project", type=Path, required=True)
    recover_parser.add_argument("--decision", type=Path, required=True)
    recover_parser.add_argument("--project-id", default=None)

    args = parser.parse_args(argv)
    try:
        if args.command == "enable":
            result = enable(args.project, args.approved_by, args.statement)
        elif args.command == "disable":
            result = disable(args.project, args.reason)
        elif args.command == "status":
            result = status(args.project)
        else:
            result = recover(args.project, args.decision, args.project_id)
        return _emit(result)
    except (AutonomyError, journal.JournalError) as error:
        return _emit({"status": "REFUSED", "reason": str(error)}, ok=False)


if __name__ == "__main__":
    sys.exit(main())
