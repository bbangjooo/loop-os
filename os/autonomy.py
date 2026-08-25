"""Config-driven autonomy policy and evidence-preserving journal recovery.

Full-auto is deliberately a project-local capability, not a global default.
The tracked `.loop-os/config.toml` is the cross-harness policy source for Codex
and Claude.  This instrument writes and validates it; other instruments trust
only its validated shape and digest.  The old `.loop-os-full-auto.json` grant
remains a read-only compatibility input for one migration window.

Journal recovery never deletes the damaged bytes.  It archives the original
journal and anchor, rebuilds a canonical chain from the currently readable
event records, seals the agent's decision file, and writes a fresh anchor.
The recovery therefore restores liveness without pretending the incident did
not happen.

Instrument surface:
    python os/autonomy.py enable  --project DIR --approved-by TEXT --statement TEXT
    python os/autonomy.py disable --project DIR --reason TEXT
    python os/autonomy.py status  --project DIR
    python os/autonomy.py migrate --project DIR
    python os/autonomy.py recover --project DIR --decision FILE [--project-id ID]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import tomllib
from pathlib import Path
from typing import Any

import journal
from _canon import canonical_json, digest_bytes, digest_file


CONFIG_SCHEMA = "loop-os-config-v1"
CONFIG_DIR = ".loop-os"
CONFIG_NAME = "config.toml"
LEGACY_GRANT_SCHEMA = "loop-os-full-auto-v1"
LEGACY_GRANT_NAME = ".loop-os-full-auto.json"
GRANT_SCOPES = ("constitutional_jump", "journal_recovery", "continuous_goal")
RECOVERY_DECISION_FIELDS = (
    "damage_assessment",
    "evidence_considered",
    "continuation_rationale",
    "accepted_uncertainty",
)


class AutonomyError(RuntimeError):
    """A full-auto config or recovery input is absent or invalid."""


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def config_path(project: Path) -> Path:
    return project.resolve() / CONFIG_DIR / CONFIG_NAME


def legacy_grant_path(project: Path) -> Path:
    return project.resolve() / LEGACY_GRANT_NAME


def grant_path(project: Path) -> Path:
    """Compatibility name for the active authority source path."""
    configured = config_path(project)
    return configured if configured.exists() else legacy_grant_path(project)


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


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _render_config(
    *,
    mode: str,
    approved_by: str,
    statement: str,
    granted_at: str,
    disabled_at: str | None = None,
    disable_reason: str | None = None,
) -> bytes:
    full_auto = mode == "full_auto"
    lines = [
        f"schema = {_toml_string(CONFIG_SCHEMA)}",
        "",
        "[autonomy]",
        f"mode = {_toml_string(mode)}",
        f"constitutional_jumps = {_toml_string('agent' if full_auto else 'human')}",
        f"journal_recovery = {_toml_string('agent' if full_auto else 'human')}",
        f"continue_until = {_toml_string('external_goal' if full_auto else 'generation')}",
        "independent_review = true",
        "",
        "[autonomy.grant]",
        f"approved_by = {_toml_string(approved_by)}",
        f"statement = {_toml_string(statement)}",
        f"granted_at = {_toml_string(granted_at)}",
    ]
    if disabled_at is not None:
        lines.append(f"disabled_at = {_toml_string(disabled_at)}")
    if disable_reason is not None:
        lines.append(f"disable_reason = {_toml_string(disable_reason)}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AutonomyError(f"Loop OS config file not found: {path}")
    try:
        value = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError) as error:
        raise AutonomyError(f"Loop OS config is not valid TOML: {error}") from error
    if value.get("schema") != CONFIG_SCHEMA:
        raise AutonomyError(f"Loop OS config has wrong schema: {value.get('schema')!r}")
    policy = value.get("autonomy")
    if not isinstance(policy, dict):
        raise AutonomyError("Loop OS config carries no [autonomy] table")
    grant = policy.get("grant")
    if not isinstance(grant, dict):
        raise AutonomyError("Loop OS config carries no [autonomy.grant] table")
    mode = policy.get("mode")
    if mode not in ("governed", "full_auto"):
        raise AutonomyError(f"Loop OS config autonomy.mode is invalid: {mode!r}")
    expected = {
        "constitutional_jumps": "agent" if mode == "full_auto" else "human",
        "journal_recovery": "agent" if mode == "full_auto" else "human",
        "continue_until": "external_goal" if mode == "full_auto" else "generation",
    }
    for key, expected_value in expected.items():
        if policy.get(key) != expected_value:
            raise AutonomyError(
                f"Loop OS config {key} must be {expected_value!r} when mode={mode!r}"
            )
    if policy.get("independent_review") is not True:
        raise AutonomyError("Loop OS config must keep independent_review=true")
    approved_by = grant.get("approved_by")
    statement = grant.get("statement")
    granted_at = grant.get("granted_at")
    if not isinstance(approved_by, str) or not approved_by.strip():
        raise AutonomyError("Loop OS config grant carries no approved_by")
    if not isinstance(statement, str) or not statement.strip():
        raise AutonomyError("Loop OS config grant carries no statement")
    if not isinstance(granted_at, str) or not granted_at.strip():
        raise AutonomyError("Loop OS config grant carries no granted_at")
    return {
        "schema": CONFIG_SCHEMA,
        "mode": mode,
        "enabled": mode == "full_auto",
        "approved_by": approved_by,
        "statement": statement,
        "granted_at": granted_at,
        "scopes": list(GRANT_SCOPES) if mode == "full_auto" else [],
        "disabled_at": grant.get("disabled_at"),
        "disable_reason": grant.get("disable_reason"),
        "source": "config",
    }


def _load_legacy_grant(path: Path) -> dict[str, Any]:
    grant = _load_object(path, "legacy full-auto grant")
    if grant.get("schema") != LEGACY_GRANT_SCHEMA:
        raise AutonomyError(f"legacy full-auto grant has wrong schema: {grant.get('schema')!r}")
    scopes = grant.get("scopes")
    if not isinstance(scopes, list) or any(scope not in GRANT_SCOPES for scope in scopes):
        raise AutonomyError("legacy full-auto grant carries invalid scopes")
    return {**grant, "mode": "full_auto" if grant.get("enabled") is True else "governed", "source": "legacy"}


def _load_policy(project: Path) -> dict[str, Any]:
    configured = config_path(project)
    if configured.exists():
        return _load_config(configured)
    legacy = legacy_grant_path(project)
    if legacy.exists():
        return _load_legacy_grant(legacy)
    raise AutonomyError(f"Loop OS config file not found: {configured}")


def _retire_legacy(project: Path, *, migrated_to: Path) -> None:
    """Make old readers fail safe after the new config becomes authoritative."""
    path = legacy_grant_path(project)
    if not path.exists():
        return
    legacy = _load_object(path, "legacy full-auto grant")
    retired = {
        **legacy,
        "enabled": False,
        "migrated_to": str(migrated_to.relative_to(project)),
        "migrated_at": legacy.get("migrated_at") or _now(),
    }
    _atomic_write(path, (json.dumps(retired, indent=2, ensure_ascii=True) + "\n").encode("utf-8"))


def load_grant(project: Path, *, required_scope: str | None = None) -> dict[str, Any]:
    grant = _load_policy(project)
    if grant.get("enabled") is not True:
        raise AutonomyError("full-auto mode is disabled")
    if not str(grant.get("approved_by", "")).strip():
        raise AutonomyError("full-auto authority carries no approved_by")
    if not str(grant.get("statement", "")).strip():
        raise AutonomyError("full-auto authority carries no statement")
    scopes = grant.get("scopes", [])
    if required_scope is not None and required_scope not in scopes:
        raise AutonomyError(f"full-auto grant does not authorize {required_scope!r}")
    return grant


def enable(project: Path, approved_by: str, statement: str) -> dict[str, Any]:
    project = project.resolve()
    if not approved_by.strip() or not statement.strip():
        raise AutonomyError("enable requires non-empty approved_by and statement")
    granted_at = _now()
    path = config_path(project)
    _atomic_write(
        path,
        _render_config(
            mode="full_auto",
            approved_by=approved_by.strip(),
            statement=statement.strip(),
            granted_at=granted_at,
        ),
    )
    _retire_legacy(project, migrated_to=path)
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
                "config_path": str(path.relative_to(project)),
                "config_digest": digest_file(path),
                "approved_by": approved_by.strip(),
                "statement": statement.strip(),
                "scopes": list(GRANT_SCOPES),
            },
        )
        event_id = event["event_id"]
    except journal.JournalError:
        # Enabling must remain possible when the very reason for entering
        # full-auto is a broken journal. Recovery will cite the config digest.
        journal_status = "PENDING_RECOVERY"
    return {
        "status": "FULL_AUTO_ENABLED",
        "config_path": str(path),
        "config_digest": digest_file(path),
        "grant_path": str(path),
        "grant_digest": digest_file(path),
        "journal_status": journal_status,
        **({"event_id": event_id} if event_id else {}),
    }


def disable(project: Path, reason: str) -> dict[str, Any]:
    project = project.resolve()
    if not reason.strip():
        raise AutonomyError("disable requires a non-empty reason")
    current = _load_policy(project)
    path = config_path(project)
    disabled_at = _now()
    _atomic_write(
        path,
        _render_config(
            mode="governed",
            approved_by=str(current.get("approved_by", "legacy grant")),
            statement=str(current.get("statement", "full-auto grant migrated to governed mode")),
            granted_at=str(current.get("granted_at", disabled_at)),
            disabled_at=disabled_at,
            disable_reason=reason.strip(),
        ),
    )
    _retire_legacy(project, migrated_to=path)
    event_id = None
    try:
        event_id = journal.append_event(
            project,
            "autonomy_changed.v1",
            {
                "enabled": False,
                "config_path": str(path.relative_to(project)),
                "config_digest": digest_file(path),
                "reason": reason.strip(),
            },
        )["event_id"]
    except journal.JournalError:
        pass
    return {
        "status": "FULL_AUTO_DISABLED",
        "config_path": str(path),
        "grant_path": str(path),
        **({"event_id": event_id} if event_id else {}),
    }


def status(project: Path) -> dict[str, Any]:
    project = project.resolve()
    configured = config_path(project)
    legacy = legacy_grant_path(project)
    if not configured.exists() and not legacy.exists():
        return {
            "status": "FULL_AUTO_DISABLED",
            "mode": "governed",
            "reason": "Loop OS config absent",
            "config_path": str(configured),
            "migration_required": False,
        }
    grant = _load_policy(project)
    path = grant_path(project)
    return {
        "status": "FULL_AUTO_ENABLED" if grant.get("enabled") is True else "FULL_AUTO_DISABLED",
        "mode": grant.get("mode"),
        "source": grant.get("source"),
        "migration_required": grant.get("source") == "legacy",
        "config_path": str(configured),
        "grant_path": str(path),
        "config_digest": digest_file(path),
        "grant_digest": digest_file(path),
        "approved_by": grant.get("approved_by"),
        "scopes": grant.get("scopes", []),
    }


def migrate(project: Path) -> dict[str, Any]:
    """Expand a legacy JSON grant into config.toml, then retire the old source.

    The legacy file is preserved with enabled=false so old readers fail safe.
    Re-running is idempotent once config.toml exists.
    """
    project = project.resolve()
    configured = config_path(project)
    legacy_path = legacy_grant_path(project)
    if configured.exists():
        _load_config(configured)
        _retire_legacy(project, migrated_to=configured)
        return {
            "status": "ALREADY_MIGRATED",
            "config_path": str(configured),
            "config_digest": digest_file(configured),
        }
    legacy = _load_legacy_grant(legacy_path)
    legacy_original_digest = digest_file(legacy_path)
    approved_by = str(legacy.get("approved_by", "")).strip()
    statement = str(legacy.get("statement", "")).strip()
    granted_at = str(legacy.get("granted_at", "")).strip()
    if not approved_by or not statement or not granted_at:
        raise AutonomyError("legacy full-auto grant lacks approved_by, statement, or granted_at")
    mode = "full_auto" if legacy.get("enabled") is True else "governed"
    _atomic_write(
        configured,
        _render_config(
            mode=mode,
            approved_by=approved_by,
            statement=statement,
            granted_at=granted_at,
            disabled_at=legacy.get("disabled_at") if mode == "governed" else None,
            disable_reason=legacy.get("disable_reason") if mode == "governed" else None,
        ),
    )
    _retire_legacy(project, migrated_to=configured)
    event_id = None
    journal_status = "RECORDED"
    try:
        journal.load_events(project)
        journal.check_anchor(project)
        event_id = journal.append_event(
            project,
            "autonomy_changed.v1",
            {
                "enabled": mode == "full_auto",
                "source": "legacy-migration",
                "config_path": str(configured.relative_to(project)),
                "config_digest": digest_file(configured),
                "legacy_grant_original_digest": legacy_original_digest,
                "legacy_grant_retired_digest": digest_file(legacy_path),
            },
        )["event_id"]
    except journal.JournalError:
        journal_status = "PENDING_RECOVERY"
    return {
        "status": "CONFIG_MIGRATED",
        "mode": mode,
        "config_path": str(configured),
        "config_digest": digest_file(configured),
        "journal_status": journal_status,
        **({"event_id": event_id} if event_id else {}),
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
    authority_path = grant_path(project)
    authority_archive = (
        "autonomy-config.toml" if authority_path.suffix == ".toml" else "legacy-grant.json"
    )
    _archive_once(recovery_dir / authority_archive, authority_path.read_bytes())

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
            "config_digest": digest_file(authority_path),
            "grant_digest": digest_file(authority_path),
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

    migrate_parser = sub.add_parser("migrate")
    migrate_parser.add_argument("--project", type=Path, required=True)

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
        elif args.command == "migrate":
            result = migrate(args.project)
        else:
            result = recover(args.project, args.decision, args.project_id)
        return _emit(result)
    except (AutonomyError, journal.JournalError) as error:
        return _emit({"status": "REFUSED", "reason": str(error)}, ok=False)


if __name__ == "__main__":
    sys.exit(main())
