"""The journal: the project's only canonical record.

An append-only, hash-chained JSONL file at <project>/.journal/events.jsonl.
Only instruments append to it (design rule: the agent never writes it
directly). Each line carries `prev`, the sha256 of the previous raw line, so
any edit to sealed history breaks the chain and `verify` reports it. The
workflow holds no other state: what exists in this file *is* where we are.

Instrument surface:
    python -m ros.journal bootstrap --project DIR --project-id ID [--lineage name=digest ...]
    python -m ros.journal verify    --project DIR
    python -m ros.journal status    --project DIR
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import secrets
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ._canon import canonical_json, digest_bytes

JOURNAL_SCHEMA = "ros2-journal-v1"
JOURNAL_DIR = ".journal"
JOURNAL_NAME = "events.jsonl"
GENESIS = "GENESIS"

EVENT_KINDS = (
    "bootstrap.v1",
    "contract_registered.v1",
    "spec_issued.v1",
    "run_sealed.v1",
    "run_abandoned.v1",
    "diagnosis_sealed.v1",
    "note_sealed.v1",
    "claim_sealed.v1",
    "adoption.v1",
)


class JournalError(RuntimeError):
    """The journal is unusable or an append precondition failed."""


def journal_path(project: Path) -> Path:
    return project / JOURNAL_DIR / JOURNAL_NAME


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_lines(path: Path) -> list[bytes]:
    if not path.exists():
        return []
    raw = path.read_bytes()
    if not raw:
        return []
    return raw.split(b"\n")[:-1] if raw.endswith(b"\n") else raw.split(b"\n")


def _repair_truncated_tail(path: Path) -> None:
    """A crash mid-append leaves a partial last line; drop it before appending
    so two records cannot fuse. Mirrors the kernel ledger's behaviour."""
    lines = _read_lines(path)
    if not lines:
        return
    try:
        json.loads(lines[-1])
    except json.JSONDecodeError:
        path.write_bytes(b"".join(line + b"\n" for line in lines[:-1]))


def append_event(project: Path, kind: str, body: dict[str, Any]) -> dict[str, Any]:
    """The single write path into the journal. Returns the appended event."""
    if kind not in EVENT_KINDS:
        raise JournalError(f"unknown event kind: {kind}")
    path = journal_path(project)
    if kind == "bootstrap.v1":
        if path.exists() and path.read_bytes().strip():
            raise JournalError("journal already bootstrapped; bootstrap is not repeatable")
        path.parent.mkdir(parents=True, exist_ok=True)
    else:
        if not path.exists():
            raise JournalError("journal not bootstrapped; run bootstrap first")
        _repair_truncated_tail(path)
    lines = _read_lines(path)
    prev = digest_bytes(lines[-1]) if lines else GENESIS
    event = {
        "journal_schema": JOURNAL_SCHEMA,
        "event_id": "ev-" + secrets.token_hex(6),
        "kind": kind,
        "recorded_at": _now(),
        "prev": prev,
        "body": body,
    }
    with path.open("ab") as handle:
        handle.write(canonical_json(event).encode("utf-8") + b"\n")
    return event


def load_events(project: Path) -> list[dict[str, Any]]:
    """Verify the chain and return the events. Fail closed on any break."""
    path = journal_path(project)
    if not path.exists():
        raise JournalError("journal not bootstrapped")
    lines = _read_lines(path)
    events: list[dict[str, Any]] = []
    prev = GENESIS
    for index, line in enumerate(lines, start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise JournalError(f"line {index} is not valid JSON: {error}") from error
        if event.get("journal_schema") != JOURNAL_SCHEMA:
            raise JournalError(f"line {index} has wrong journal_schema")
        if event.get("prev") != prev:
            raise JournalError(
                f"hash chain broken at line {index}: prev={event.get('prev')!r} expected {prev!r}"
            )
        if canonical_json(event).encode("utf-8") != line:
            raise JournalError(f"line {index} is not in canonical form; sealed history was edited")
        events.append(event)
        prev = digest_bytes(line)
    if not events:
        raise JournalError("journal is empty")
    if events[0]["kind"] != "bootstrap.v1":
        raise JournalError("first event is not bootstrap.v1")
    return events


def head_digest(project: Path) -> str:
    lines = _read_lines(journal_path(project))
    if not lines:
        raise JournalError("journal is empty")
    return digest_bytes(lines[-1])


@dataclass
class JournalState:
    """Pure reduction of the event list. This dataclass is the only 'workflow
    state' in the system, and it is recomputed from the file every time."""

    project_id: str = ""
    lineage: list[dict[str, str]] = field(default_factory=list)
    contract_digest: str | None = None
    generation: int | None = None
    # spec_digest -> spec_issued event, for specs with no run_sealed/abandoned yet
    pending_runs: dict[str, dict[str, Any]] = field(default_factory=dict)
    # run_sealed event_id -> run_sealed event, for runs with no diagnosis yet
    pending_diagnoses: dict[str, dict[str, Any]] = field(default_factory=dict)
    sealed_spec_digests: set[str] = field(default_factory=set)
    drawn_by_generation: dict[int, int] = field(default_factory=dict)
    runs_sealed: list[dict[str, Any]] = field(default_factory=list)
    diagnoses: list[dict[str, Any]] = field(default_factory=list)
    notes: list[dict[str, Any]] = field(default_factory=list)
    claims: list[dict[str, Any]] = field(default_factory=list)
    adoptions: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)


def reduce_state(events: list[dict[str, Any]]) -> JournalState:
    state = JournalState(events=events)
    for event in events:
        kind, body = event["kind"], event["body"]
        if kind == "bootstrap.v1":
            state.project_id = body["project_id"]
            state.lineage = body.get("lineage", [])
        elif kind == "contract_registered.v1":
            state.contract_digest = body["contract_digest"]
            state.generation = body["generation"]
        elif kind == "spec_issued.v1":
            state.pending_runs[body["spec_digest"]] = event
            generation = body["generation"]
            state.drawn_by_generation[generation] = (
                state.drawn_by_generation.get(generation, 0) + body["draw"]
            )
        elif kind == "run_sealed.v1":
            state.pending_runs.pop(body["spec_digest"], None)
            state.sealed_spec_digests.add(body["spec_digest"])
            state.pending_diagnoses[event["event_id"]] = event
            state.runs_sealed.append(event)
        elif kind == "run_abandoned.v1":
            state.pending_runs.pop(body["spec_digest"], None)
        elif kind == "diagnosis_sealed.v1":
            state.pending_diagnoses.pop(body["run_seal_id"], None)
            state.diagnoses.append(event)
        elif kind == "note_sealed.v1":
            state.notes.append(event)
        elif kind == "claim_sealed.v1":
            state.claims.append(event)
        elif kind == "adoption.v1":
            state.adoptions.append(event)
    return state


def replay(project: Path) -> JournalState:
    return reduce_state(load_events(project))


def ensure_gitignored(project: Path) -> None:
    """The journal must survive the kernel's `git reset --hard` + `git clean -fd`
    and must not dirty the worktree the kernel insists is clean. A gitignored
    path satisfies both (the same reason the kernel keeps its ledger in .git/
    and crypto-new keeps its evidence cache ignored)."""
    gitignore = project / ".gitignore"
    entry = JOURNAL_DIR + "/"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    if entry not in existing.splitlines():
        with gitignore.open("a", encoding="utf-8") as handle:
            if existing and not existing.endswith("\n"):
                handle.write("\n")
            handle.write(entry + "\n")


def _emit(payload: dict[str, Any], *, ok: bool = True) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ros.journal")
    sub = parser.add_subparsers(dest="command", required=True)

    boot = sub.add_parser("bootstrap")
    boot.add_argument("--project", type=Path, required=True)
    boot.add_argument("--project-id", required=True)
    boot.add_argument("--lineage", action="append", default=[], metavar="NAME=DIGEST")

    for name in ("verify", "status"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--project", type=Path, required=True)

    args = parser.parse_args(argv)
    project = args.project.resolve()

    try:
        if args.command == "bootstrap":
            lineage = []
            for item in args.lineage:
                name, _, value = item.partition("=")
                if not name or not value:
                    raise JournalError(f"lineage must be NAME=DIGEST, got {item!r}")
                lineage.append({"name": name, "digest": value})
            event = append_event(
                project, "bootstrap.v1", {"project_id": args.project_id, "lineage": lineage}
            )
            ensure_gitignored(project)
            return _emit({"status": "BOOTSTRAPPED", "event_id": event["event_id"]})
        if args.command == "verify":
            events = load_events(project)
            return _emit(
                {"status": "VERIFIED", "events": len(events), "head": head_digest(project)}
            )
        state = replay(project)
        next_required: str
        if state.contract_digest is None:
            next_required = "register the contract (ros.seal contract)"
        elif state.pending_runs:
            next_required = "run the kernel for the issued spec, then seal it (ros.seal run)"
        elif state.pending_diagnoses:
            next_required = "author a diagnosis file and seal it (ros.seal diagnosis)"
        else:
            next_required = "issue the next spec (ros.aim)"
        return _emit(
            {
                "status": "OK",
                "project_id": state.project_id,
                "generation": state.generation,
                "contract_digest": state.contract_digest,
                "pending_runs": [e["body"]["spec_digest"] for e in state.pending_runs.values()],
                "pending_diagnoses": list(state.pending_diagnoses),
                "runs_sealed": len(state.runs_sealed),
                "drawn_by_generation": state.drawn_by_generation,
                "next_required": next_required,
            }
        )
    except JournalError as error:
        return _emit({"status": "REFUSED", "reason": str(error)}, ok=False)


if __name__ == "__main__":
    sys.exit(main())
