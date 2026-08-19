"""jump: adopt a successor frame in one atomic append.

No workflow engine, no receipts, no phases. Adoption is a single journal
event citing the digests of four files that must already exist — a dossier
(steer), a successor contract (author), an independent review (separate
session/model route, honest declaration), and a human approval. A missing or
mismatched file makes the event impossible to construct; that is the whole
enforcement (design rule C: ordering is data dependency).

Registering a contract with a higher generation is refused by os/seal.py until
an adoption event covering that generation exists — so the ritual's order is
carried by the data, not by a state machine.

Instrument surface:
    python os/jump.py adopt  --project DIR --dossier F --successor F --review F --approval F
    python os/jump.py revoke --project DIR --adoption EVENT_ID --reason TEXT
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import journal
from aim import ContractError, load_contract
from _canon import digest_file


class JumpError(RuntimeError):
    """An adoption input is missing or inconsistent."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise JumpError(f"{label} file not found: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise JumpError(f"{label} is not valid JSON: {error}") from error
    if not isinstance(value, dict):
        raise JumpError(f"{label} must be a JSON object")
    return value


def adopt(
    project: Path,
    dossier_path: Path,
    successor_path: Path,
    review_path: Path,
    approval_path: Path,
) -> dict[str, Any]:
    project = project.resolve()
    state = journal.replay(project)

    dossier = _load_json(dossier_path, "dossier")
    rival = dossier.get("rival_draft") or {}
    rival_note_id = rival.get("note_id")
    if not rival_note_id:
        raise JumpError("dossier carries no rival_draft.note_id; produce it with os/steer.py dossier")
    current_frame = dossier.get("current_frame") or {}
    if state.contract_digest and current_frame.get("contract_digest") != state.contract_digest:
        raise JumpError(
            "dossier was built against a different registered contract; regenerate it"
        )

    try:
        successor = load_contract(successor_path)
    except ContractError as error:
        raise JumpError(f"successor contract invalid: {error}") from error
    successor_generation = successor["frame"]["generation"]
    if state.generation is not None and successor_generation != state.generation + 1:
        raise JumpError(
            f"successor generation must be {state.generation + 1}, got {successor_generation}"
        )

    review = _load_json(review_path, "review")
    if review.get("independent") is not True or not str(review.get("reviewer", "")).strip():
        raise JumpError(
            "review must declare reviewer and independent=true "
            "(authored in a separate session/model route; declaration, honestly limited)"
        )
    if review.get("verdict") != "PASS":
        raise JumpError(f"review verdict must be PASS, got {review.get('verdict')!r}")

    approval = _load_json(approval_path, "approval")
    if not str(approval.get("approved_by", "")).strip() or not str(approval.get("statement", "")).strip():
        raise JumpError("approval must carry approved_by and statement, written by the human")

    event = journal.append_event(
        project,
        "adoption.v1",
        {
            "rival_note_id": rival_note_id,
            "successor_generation": successor_generation,
            "successor_class": successor["frame"]["class"],
            "dossier_digest": digest_file(dossier_path),
            "successor_contract_digest": digest_file(successor_path),
            "review_digest": digest_file(review_path),
            "approval_digest": digest_file(approval_path),
        },
    )
    return {
        "status": "ADOPTED",
        "event_id": event["event_id"],
        "successor_generation": successor_generation,
        "successor_class": successor["frame"]["class"],
        "next_required": "register the successor contract (os/seal.py contract), then os/aim.py",
    }


def revoke(project: Path, adoption_event_id: str, reason: str) -> dict[str, Any]:
    """Undo an adoption while nothing irreversible happened under it. The
    window closes at the successor's first spec_issued: once budget is drawn
    the honest path forward is another jump, never a rewrite. Revocation also
    voids any registration that cited the adoption (reducer skips it), so the
    frame falls back to the previous registration on the next replay."""
    project = project.resolve()
    if not reason.strip():
        raise JumpError("revoke requires a non-empty reason")
    state = journal.replay(project)
    adoption = next((a for a in state.adoptions if a["event_id"] == adoption_event_id), None)
    if adoption is None:
        raise JumpError(
            f"no active adoption {adoption_event_id!r} (unknown or already revoked)"
        )
    successor_generation = adoption["body"]["successor_generation"]
    drawn = any(
        e["kind"] == "spec_issued.v1" and e["body"]["generation"] == successor_generation
        for e in state.events
    )
    if drawn:
        raise JumpError(
            f"generation {successor_generation} has already drawn budget (spec_issued exists); "
            "an adoption with spent budget cannot be revoked — open another jump instead"
        )
    event = journal.append_event(
        project,
        "adoption_revoked.v1",
        {"adoption_event_id": adoption_event_id, "reason": reason},
    )
    rolled_back = journal.replay(project)
    return {
        "status": "REVOKED",
        "event_id": event["event_id"],
        "generation_now": rolled_back.generation,
        "contract_digest_now": rolled_back.contract_digest,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jump")
    sub = parser.add_subparsers(dest="command", required=True)

    ad = sub.add_parser("adopt")
    ad.add_argument("--project", type=Path, required=True)
    ad.add_argument("--dossier", type=Path, required=True)
    ad.add_argument("--successor", type=Path, required=True)
    ad.add_argument("--review", type=Path, required=True)
    ad.add_argument("--approval", type=Path, required=True)

    rv = sub.add_parser("revoke")
    rv.add_argument("--project", type=Path, required=True)
    rv.add_argument("--adoption", required=True, help="adoption.v1 event id")
    rv.add_argument("--reason", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "adopt":
            result = adopt(args.project, args.dossier, args.successor, args.review, args.approval)
        else:
            result = revoke(args.project, args.adoption, args.reason)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (JumpError, journal.JournalError) as error:
        print(json.dumps({"status": "REFUSED", "reason": str(error)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
