"""seal: the only write path into the journal for evidence and judgment.

Three subcommands, each one append:

  contract   pin the current contract.toml (registration; aim requires it)
  run        seal a finished kernel run: summary + ledger (+ trials) digests
  diagnosis  seal an LLM-authored diagnosis file against a sealed run

The agent authors judgment *files*; this instrument turns them into citable
journal facts. It validates shape, never meaning — meaning stays in the file,
readable by whoever replays the evidence.

Instrument surface:
    python -m ros.seal contract  --project DIR [--contract contract.toml]
    python -m ros.seal run       --project DIR --summary PATH --ledger PATH
                                 [--trials PATH] [--migrated]
    python -m ros.seal abandon   --project DIR --spec-digest DIGEST --reason TEXT
    python -m ros.seal diagnosis --project DIR --file PATH [--run RUN_SEAL_EVENT_ID]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import journal
from .aim import CONTRACT_NAME, ContractError, load_contract
from ._canon import digest_file

VERDICTS = ("SUPPORTED", "REJECTED", "INCONCLUSIVE")
DIAGNOSIS_FIELDS = ("what_moved", "mechanism_interpretation", "counterfactual", "next_question")


class SealError(RuntimeError):
    """A seal precondition failed; the message names the missing input."""


def seal_contract(project: Path, contract_path: Path | None = None) -> dict[str, Any]:
    project = project.resolve()
    contract_path = (contract_path or project / CONTRACT_NAME).resolve()
    contract = load_contract(contract_path)
    contract_digest = digest_file(contract_path)
    state = journal.replay(project)
    if state.contract_digest == contract_digest:
        return {"status": "ALREADY_REGISTERED", "contract_digest": contract_digest}
    # A generation bump is a frame transition: it must cite an adoption event
    # whose digest matches this exact contract text (ordering by data, not by
    # a state machine).
    generation = contract["frame"]["generation"]
    if state.generation is not None and generation > state.generation:
        adopted = any(
            a["body"]["successor_generation"] == generation
            and a["body"]["successor_contract_digest"] == contract_digest
            for a in state.adoptions
        )
        if not adopted:
            raise SealError(
                f"registering generation {generation} requires an adoption event "
                "citing this contract's digest (ros.jump)"
            )
    event = journal.append_event(
        project,
        "contract_registered.v1",
        {
            "contract_path": str(contract_path.relative_to(project)),
            "contract_digest": contract_digest,
            "generation": contract["frame"]["generation"],
            "class": contract["frame"]["class"],
        },
    )
    return {"status": "CONTRACT_REGISTERED", "contract_digest": contract_digest, "event_id": event["event_id"]}


def _registered_class(state: journal.JournalState) -> str | None:
    for event in reversed(state.events):
        if event["kind"] == "contract_registered.v1":
            return event["body"].get("class")
    return None


def seal_run(
    project: Path,
    summary_path: Path,
    ledger_path: Path,
    trials_path: Path | None = None,
    migrated: bool = False,
) -> dict[str, Any]:
    project = project.resolve()
    for label, path in (("summary", summary_path), ("ledger", ledger_path)):
        if not path.is_file():
            raise SealError(f"{label} file not found: {path}")
    if trials_path is not None and not trials_path.is_file():
        raise SealError(f"trials file not found: {trials_path}")

    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SealError(f"summary is not valid JSON: {error}") from error
    spec_digest = summary.get("spec_digest")
    if not isinstance(spec_digest, str) or not spec_digest:
        raise SealError("summary carries no spec_digest; it is not a kernel summary")

    state = journal.replay(project)
    if spec_digest in state.sealed_spec_digests:
        raise SealError(f"a run for spec_digest {spec_digest[:12]}… is already sealed")
    issued = state.pending_runs.get(spec_digest)
    if issued is None and not migrated:
        raise SealError(
            "no issued spec matches this summary's spec_digest; "
            "use --migrated only for runs that predate this journal"
        )

    # The honest multiple-testing denominator: the ledger counts iterations the
    # loop saw; trials.jsonl counts evaluator calls the agent made *inside*
    # iterations. Claimable N is the larger of the two (crypto-new af_eval
    # doctrine, promoted to the seal itself).
    ledger_iterations = sum(1 for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip())
    trials_count = None
    if trials_path is not None:
        trials_count = sum(1 for line in trials_path.read_text(encoding="utf-8").splitlines() if line.strip())

    # The frame that governs this run, so projections can aggregate per class
    # without re-reading the contract. Falls back to the issuance event.
    issued_body = issued["body"] if issued is not None else {}
    body: dict[str, Any] = {
        "origin": "migration" if migrated else "issued",
        "class": issued_body.get("class") or _registered_class(state),
        "generation": issued_body.get("generation") or state.generation,
        "spec_digest": spec_digest,
        "loop_id": summary.get("loop_id"),
        "run_id": summary.get("run_id"),
        "summary_path": str(summary_path),
        "summary_digest": digest_file(summary_path),
        "ledger_path": str(ledger_path),
        "ledger_digest": digest_file(ledger_path),
        "ledger_iterations": ledger_iterations,
        "iterations_run": summary.get("iterations_run"),
        "accepted": summary.get("accepted"),
        "decisions": summary.get("decisions"),
        "stopped": summary.get("stopped"),
        "objective": summary.get("objective"),
        "trials_denominator": max(
            ledger_iterations, trials_count if trials_count is not None else 0
        ),
    }
    if issued is not None:
        body["spec_issued_id"] = issued["event_id"]
    if trials_path is not None:
        body["trials_path"] = str(trials_path)
        body["trials_digest"] = digest_file(trials_path)
        body["trials_count"] = trials_count
    event = journal.append_event(project, "run_sealed.v1", body)
    return {
        "status": "RUN_SEALED",
        "event_id": event["event_id"],
        "spec_digest": spec_digest,
        "trials_denominator": body["trials_denominator"],
        "next_required": "author a diagnosis file and seal it (ros.seal diagnosis)",
    }


def seal_abandon(project: Path, spec_digest: str, reason: str) -> dict[str, Any]:
    project = project.resolve()
    state = journal.replay(project)
    if spec_digest not in state.pending_runs:
        raise SealError(f"no pending run for spec_digest {spec_digest[:12]}…")
    if not reason.strip():
        raise SealError("abandon requires a non-empty reason")
    event = journal.append_event(
        project,
        "run_abandoned.v1",
        {"spec_digest": spec_digest, "reason": reason},
    )
    return {
        "status": "RUN_ABANDONED",
        "event_id": event["event_id"],
        "note": "the draw is not refunded; budget stays spent (reserved-not-measured)",
    }


def seal_diagnosis(project: Path, file_path: Path, run_seal_id: str | None = None) -> dict[str, Any]:
    project = project.resolve()
    if not file_path.is_file():
        raise SealError(f"diagnosis file not found: {file_path}")
    try:
        diagnosis = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SealError(f"diagnosis is not valid JSON: {error}") from error

    verdict = diagnosis.get("verdict")
    if verdict not in VERDICTS:
        raise SealError(f"verdict must be one of {VERDICTS}, got {verdict!r}")
    for field in DIAGNOSIS_FIELDS:
        value = diagnosis.get(field)
        if not isinstance(value, str) or not value.strip():
            raise SealError(f"diagnosis field {field!r} must be non-empty text")
        if "REPLACE_ME" in value:
            raise SealError(f"diagnosis field {field!r} still contains REPLACE_ME")

    state = journal.replay(project)
    if not state.pending_diagnoses:
        raise SealError("no sealed run is awaiting a diagnosis")
    if run_seal_id is None:
        if len(state.pending_diagnoses) > 1:
            raise SealError(
                f"multiple runs await diagnosis; pass --run one of {sorted(state.pending_diagnoses)}"
            )
        run_seal_id = next(iter(state.pending_diagnoses))
    if run_seal_id not in state.pending_diagnoses:
        raise SealError(f"run seal {run_seal_id!r} is not awaiting a diagnosis")

    run_event = state.pending_diagnoses[run_seal_id]
    event = journal.append_event(
        project,
        "diagnosis_sealed.v1",
        {
            "run_seal_id": run_seal_id,
            "spec_digest": run_event["body"]["spec_digest"],
            "class": run_event["body"].get("class"),
            "generation": run_event["body"].get("generation"),
            "diagnosis_path": str(file_path),
            "diagnosis_digest": digest_file(file_path),
            "verdict": verdict,
        },
    )
    return {"status": "DIAGNOSIS_SEALED", "event_id": event["event_id"], "verdict": verdict}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ros.seal")
    sub = parser.add_subparsers(dest="command", required=True)

    contract = sub.add_parser("contract")
    contract.add_argument("--project", type=Path, required=True)
    contract.add_argument("--contract", type=Path, default=None)

    run = sub.add_parser("run")
    run.add_argument("--project", type=Path, required=True)
    run.add_argument("--summary", type=Path, required=True)
    run.add_argument("--ledger", type=Path, required=True)
    run.add_argument("--trials", type=Path, default=None)
    run.add_argument("--migrated", action="store_true")

    abandon = sub.add_parser("abandon")
    abandon.add_argument("--project", type=Path, required=True)
    abandon.add_argument("--spec-digest", required=True)
    abandon.add_argument("--reason", required=True)

    diagnosis = sub.add_parser("diagnosis")
    diagnosis.add_argument("--project", type=Path, required=True)
    diagnosis.add_argument("--file", type=Path, required=True)
    diagnosis.add_argument("--run", default=None)

    args = parser.parse_args(argv)
    try:
        if args.command == "contract":
            result = seal_contract(args.project, args.contract)
        elif args.command == "run":
            result = seal_run(args.project, args.summary, args.ledger, args.trials, args.migrated)
        elif args.command == "abandon":
            result = seal_abandon(args.project, args.spec_digest, args.reason)
        else:
            result = seal_diagnosis(args.project, args.file, args.run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (SealError, journal.JournalError, ContractError) as error:
        print(json.dumps({"status": "REFUSED", "reason": str(error)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
