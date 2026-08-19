"""note: the advisory lane. LLM observations become citable, tamper-evident
data — and nothing more.

Notes carry zero authority (design: the only path from a note to a spec is a
jump adoption). Content lives in .journal/notes.jsonl; each append also seals
the note's digest into the canonical journal (note_sealed.v1), which is what
makes a note citable by a dossier without letting its content near aim.

Screens (fail-closed, shape only):
  - kind must be one of NOTE_KINDS
  - signal-bearing kinds require non-empty evidence_refs
  - external_evidence requires summary / source_locator / snapshot_digest /
    claims / limitations — the OS never fetches; retrieval happened outside
    and only the digest enters the record
  - rival_draft requires commitment_rejected / proposed_frame / mechanism /
    falsifier, and once any external_evidence note exists the project is
    opted into prior binding: every new rival_draft must cite at least one
    external_evidence note id in refs

Instrument surface:
    python -m ros.note --project DIR --kind KIND --body JSON_FILE [--refs id ...]
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from pathlib import Path
from typing import Any

from . import journal
from ._canon import canonical_json, digest_bytes

NOTES_NAME = "notes.jsonl"

NOTE_KINDS = (
    "observation",
    "anomaly",
    "assumption_conflict",
    "idea",
    "external_evidence",
    "rival_draft",
)
SIGNAL_BEARING_KINDS = ("observation", "anomaly", "assumption_conflict")
EXTERNAL_EVIDENCE_FIELDS = ("summary", "source_locator", "snapshot_digest", "claims", "limitations")
RIVAL_DRAFT_FIELDS = ("commitment_rejected", "proposed_frame", "mechanism", "falsifier")


class NoteError(RuntimeError):
    """The note fails a screen; the message names the missing part."""


def notes_path(project: Path) -> Path:
    return project / journal.JOURNAL_DIR / NOTES_NAME


def _existing_notes(project: Path) -> list[dict[str, Any]]:
    path = notes_path(project)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _screen(kind: str, body: dict[str, Any], refs: list[str], existing: list[dict[str, Any]]) -> None:
    if kind not in NOTE_KINDS:
        raise NoteError(f"kind must be one of {NOTE_KINDS}")
    if kind in SIGNAL_BEARING_KINDS and not refs:
        raise NoteError(f"{kind} is signal-bearing and requires at least one evidence ref")
    if kind == "external_evidence":
        for field in EXTERNAL_EVIDENCE_FIELDS:
            value = body.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                raise NoteError(f"external_evidence requires non-empty {field!r}")
    if kind == "rival_draft":
        for field in RIVAL_DRAFT_FIELDS:
            value = body.get(field)
            if not isinstance(value, str) or not value.strip():
                raise NoteError(f"rival_draft requires non-empty {field!r}")
        evidence_ids = {n["note_id"] for n in existing if n["kind"] == "external_evidence"}
        if evidence_ids:  # prior binding is active once any external evidence exists
            if not evidence_ids.intersection(refs):
                raise NoteError(
                    "prior binding active: a rival_draft must cite at least one "
                    f"external_evidence note id in refs (known: {sorted(evidence_ids)})"
                )


def record(project: Path, kind: str, body: dict[str, Any], refs: list[str]) -> dict[str, Any]:
    project = project.resolve()
    journal.load_events(project)  # the journal must exist and verify first
    existing = _existing_notes(project)
    _screen(kind, body, refs, existing)
    note = {
        "note_id": "note-" + secrets.token_hex(6),
        "kind": kind,
        "refs": refs,
        "body": body,
    }
    line = canonical_json(note).encode("utf-8")
    with notes_path(project).open("ab") as handle:
        handle.write(line + b"\n")
    event = journal.append_event(
        project,
        "note_sealed.v1",
        {"note_id": note["note_id"], "kind": kind, "note_digest": digest_bytes(line), "refs": refs},
    )
    return {"status": "NOTE_SEALED", "note_id": note["note_id"], "event_id": event["event_id"]}


def load_notes(project: Path) -> list[dict[str, Any]]:
    """Notes whose digests match their seals; a tampered note is dropped with
    its seal reported, never silently trusted."""
    sealed = {
        e["body"]["note_id"]: e["body"]["note_digest"]
        for e in journal.load_events(project)
        if e["kind"] == "note_sealed.v1"
    }
    verified: list[dict[str, Any]] = []
    path = notes_path(project)
    if not path.exists():
        return verified
    for line in path.read_bytes().splitlines():
        if not line.strip():
            continue
        note = json.loads(line)
        if sealed.get(note.get("note_id")) == digest_bytes(line):
            verified.append(note)
    return verified


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ros.note")
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--body", type=Path, required=True, help="JSON file authored by the agent")
    parser.add_argument("--refs", nargs="*", default=[])
    args = parser.parse_args(argv)
    try:
        body = json.loads(args.body.read_text(encoding="utf-8"))
        result = record(args.project, args.kind, body, list(args.refs))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (NoteError, journal.JournalError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "REFUSED", "reason": str(error)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
