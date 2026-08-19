"""steer: read-only projections over the journal and the notes.

Evidence without verdicts. Every projection assembles facts and, where a
judgment is genuinely required, emits an interpretation request naming the
question, the reader who must answer it (the LLM), and the note kind that
turns the answer into a citable signal. The projection itself never says
"stagnating" — that seam is deliberate (survived from the old frame-health
surface).

Projections:
  status        research-level state: budget, class states, pending inputs
  frame-health  per-class margin trajectory + interpretation requests
  residual      for closed classes: the rejected mechanisms and the jump task
  dossier       everything a jump needs, keyed by one rival_draft note id

Instrument surface:
    python -m ros.steer {status|frame-health|residual} --project DIR
    python -m ros.steer dossier --project DIR --rival NOTE_ID
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from . import journal, note

CLASS_CLOSURE_THRESHOLD = 3  # REJECTED diagnoses that close a class (old-world rule)

INTERPRETATION_REQUESTS = [
    {
        "id": "stagnation",
        "question": "Is the margin trajectory failing to approach the target across recent runs?",
        "if_judged_yes": "record an `anomaly` note citing the run seal event ids",
    },
    {
        "id": "assumption_misfit",
        "question": "Does any sealed evidence contradict an assumption the contract's mechanism states?",
        "if_judged_yes": "record an `assumption_conflict` note citing the evidence",
    },
    {
        "id": "frame_misfit",
        "question": "Do the rejections share a commitment that would explain them all if false?",
        "if_judged_yes": "record a `rival_draft` note (prior binding applies if external evidence exists)",
    },
]

AUTHORING_OBLIGATIONS = [
    {"step": "successor_contract", "owner": "author", "artifact": "a ros2-contract-v1 file with generation = current + 1"},
    {"step": "independent_review", "owner": "independent_reviewer", "artifact": "review JSON authored in a separate session/model route"},
    {"step": "human_approval", "owner": "designated_human", "artifact": "approval JSON written by the human"},
    {"step": "adoption", "owner": "author", "artifact": "ros.jump citing the dossier, successor, review, approval digests"},
]


def _runs_with_class(state: journal.JournalState) -> list[dict[str, Any]]:
    """Runs annotated with a class, falling back to the contract registered at
    reduction time for early journals that predate the class field."""
    current_class = None
    annotated = []
    for event in state.events:
        if event["kind"] == "contract_registered.v1":
            current_class = event["body"].get("class")
        elif event["kind"] == "run_sealed.v1":
            body = dict(event["body"])
            body.setdefault("class", None)
            if body["class"] is None:
                body["class"] = current_class or "unknown"
            annotated.append({"event_id": event["event_id"], **body})
    return annotated


def _diagnoses_by_run(state: journal.JournalState) -> dict[str, dict[str, Any]]:
    return {d["body"]["run_seal_id"]: d["body"] for d in state.diagnoses}


def _class_states(state: journal.JournalState) -> dict[str, dict[str, Any]]:
    runs = _runs_with_class(state)
    verdicts = _diagnoses_by_run(state)
    classes: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"runs": 0, "verdicts": defaultdict(int), "closed": False}
    )
    for run in runs:
        entry = classes[run["class"]]
        entry["runs"] += 1
        diagnosis = verdicts.get(run["event_id"])
        if diagnosis:
            entry["verdicts"][diagnosis.get("verdict", "UNKNOWN")] += 1
    for entry in classes.values():
        entry["verdicts"] = dict(entry["verdicts"])
        entry["closed"] = entry["verdicts"].get("REJECTED", 0) >= CLASS_CLOSURE_THRESHOLD
    return dict(classes)


def status(project: Path) -> dict[str, Any]:
    state = journal.replay(project)
    notes = note.load_notes(project)
    return {
        "status": "OK",
        "project_id": state.project_id,
        "generation": state.generation,
        "drawn_by_generation": state.drawn_by_generation,
        "pending_runs": [e["body"]["loop_id"] for e in state.pending_runs.values()],
        "pending_diagnoses": sorted(state.pending_diagnoses),
        "class_states": _class_states(state),
        "notes_by_kind": dict(_count_kinds(notes)),
        "adoptions": len(state.adoptions),
    }


def _count_kinds(notes: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for item in notes:
        counts[item["kind"]] += 1
    return counts


def frame_health(project: Path) -> dict[str, Any]:
    state = journal.replay(project)
    runs = _runs_with_class(state)
    verdicts = _diagnoses_by_run(state)
    trajectory = []
    for run in runs:
        objective = run.get("objective") or {}
        diagnosis = verdicts.get(run["event_id"])
        trajectory.append(
            {
                "run_seal_id": run["event_id"],
                "class": run["class"],
                "generation": run.get("generation"),
                "loop_id": run.get("loop_id"),
                "baseline": objective.get("baseline"),
                "final": objective.get("final"),
                "target": (objective.get("target") if isinstance(objective, dict) else None),
                "stopped": run.get("stopped"),
                "accepted": run.get("accepted"),
                "trials_denominator": run.get("trials_denominator"),
                "verdict": diagnosis.get("verdict") if diagnosis else None,
            }
        )
    return {
        "status": "OK",
        "class_states": _class_states(state),
        "margin_trajectory": trajectory,
        "interpretation_requests": INTERPRETATION_REQUESTS,
        "note": "this packet carries evidence, not verdicts; the reader answers the requests",
    }


def residual(project: Path) -> dict[str, Any]:
    state = journal.replay(project)
    classes = _class_states(state)
    verdicts = _diagnoses_by_run(state)
    runs = _runs_with_class(state)
    tasks = []
    for class_name, entry in classes.items():
        if not entry["closed"]:
            continue
        rejected = [
            {
                "run_seal_id": run["event_id"],
                "loop_id": run.get("loop_id"),
                "diagnosis_digest": verdicts[run["event_id"]].get("diagnosis_digest"),
            }
            for run in runs
            if run["class"] == class_name
            and verdicts.get(run["event_id"], {}).get("verdict") == "REJECTED"
        ]
        tasks.append(
            {
                "class": class_name,
                "rejected_attempts": rejected,
                "instruction": (
                    "read the rejected diagnoses; state the commitment their mechanisms "
                    "share, then propose a frame in which that commitment is false "
                    "(record it as a rival_draft note)"
                ),
            }
        )
    return {"status": "OK", "closed_classes": tasks, "closure_threshold": CLASS_CLOSURE_THRESHOLD}


def dossier(project: Path, rival_note_id: str) -> dict[str, Any]:
    """A map of the climb, not a lift: everything a jump must carry, keyed by
    one rival_draft note. It performs nothing."""
    state = journal.replay(project)
    notes = note.load_notes(project)
    rival = next(
        (n for n in notes if n["note_id"] == rival_note_id and n["kind"] == "rival_draft"), None
    )
    if rival is None:
        raise journal.JournalError(f"no verified rival_draft note with id {rival_note_id!r}")
    contract_event = next(
        (e for e in reversed(state.events) if e["kind"] == "contract_registered.v1"), None
    )
    evidence_refs = [
        n for n in notes if n["kind"] == "external_evidence" and n["note_id"] in rival["refs"]
    ]
    return {
        "status": "OK",
        "rival_draft": rival,
        "current_frame": contract_event["body"] if contract_event else None,
        "external_priors": evidence_refs,
        "class_states": _class_states(state),
        "budget_drawn": state.drawn_by_generation,
        "authoring_obligations": AUTHORING_OBLIGATIONS,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ros.steer")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "frame-health", "residual"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--project", type=Path, required=True)
    doss = sub.add_parser("dossier")
    doss.add_argument("--project", type=Path, required=True)
    doss.add_argument("--rival", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            result = status(args.project)
        elif args.command == "frame-health":
            result = frame_health(args.project)
        elif args.command == "residual":
            result = residual(args.project)
        else:
            result = dossier(args.project, args.rival)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except journal.JournalError as error:
        print(json.dumps({"status": "REFUSED", "reason": str(error)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
