"""jump: adopt a successor frame in one atomic append.

No workflow engine, no receipts, no phases. Adoption is a single journal
event citing the digests of four files that must already exist — a dossier
(steer), a successor contract (author), an independent review (separate
session/model route, honest declaration), and an approval. A missing or
mismatched file makes the event impossible to construct; that is the whole
enforcement (design rule C: ordering is data dependency).

Approval has two tiers by default. An ordinary jump may present approval.json
{"mode": "auto", ...}; this instrument then verifies, from the files and the
journal alone, that the successor changes the frame and nothing else:

  - [core] (the human-sealed constitution) canonically unchanged
  - project.id unchanged, budget.iterations_total not raised, [revert] unchanged
  - the set of stage objective measurements (command, direction, margin,
    target, proxy_license) exactly equal — the evaluator is part of the
    constitution even though it lives in stages (timeout_seconds is exempt:
    a liveness knob whose misuse fails closed, never a looser measurement)
  - every successor stage carries every current guard (per stage, so a decoy
    stage cannot park them), and top-level integrity carries every current
    pin, stage-level included (adding guards or pins is allowed)
  - the current frame actually closed: the class has three REJECTED
    diagnoses (steer's rule), or the generation budget is fully drawn with
    all runs sealed-or-abandoned, all diagnoses in, and at least one
    diagnosis recorded — an auto jump before closure is frame-shopping

Anything else — touching [core], swapping the evaluator, shedding a guard,
inflating the budget, jumping from an open frame — is constitutional: it
needs the human-authored approval.json {"approved_by", "statement"}.

An explicitly enabled project-local `.loop-os/config.toml` adds a third, opt-in tier:
approval.json {"mode":"full_auto", ...}.  It may authorize a constitutional
jump after an independent PASS review, but it must carry the agent's decision,
evidence, goal continuity, risk assessment, and rollback plan.  The config and approval digests
are sealed into the adoption event, so autonomy changes who decides, not
whether the decision leaves evidence.  The ledger records approval_mode.

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

import autonomy
import journal
from aim import ContractError, load_contract
from steer import CLASS_CLOSURE_THRESHOLD
from _canon import canonical_json, digest_bytes, digest_file


class JumpError(RuntimeError):
    """An adoption input is missing or inconsistent."""


# The evaluator lives in stages, but it is constitution: these are the fields
# whose change would alter what counts as success, so the auto tier freezes
# them alongside [core].
_OBJECTIVE_MEASUREMENT_KEYS = ("command", "direction", "margin", "target", "proxy_license")
_GUARD_MEASUREMENT_KEYS = ("command", "kind", "tolerance", "ratchet")
_FULL_AUTO_APPROVAL_FIELDS = (
    "decision",
    "evidence",
    "goal_continuity",
    "risk_assessment",
    "rollback_plan",
)


def _objective_set(contract: dict[str, Any]) -> set[str]:
    return {
        canonical_json({k: s["objective"].get(k) for k in _OBJECTIVE_MEASUREMENT_KEYS})
        for s in contract["stages"]
    }


def _stage_guard_set(stage: dict[str, Any]) -> set[str]:
    return {
        canonical_json({k: g.get(k) for k in _GUARD_MEASUREMENT_KEYS})
        for g in stage.get("guards", [])
    }


def _guard_set(contract: dict[str, Any]) -> set[str]:
    guards: set[str] = set()
    for s in contract["stages"]:
        guards |= _stage_guard_set(s)
    return guards


def _integrity_pins(contract: dict[str, Any]) -> set[str]:
    pins = set(contract.get("integrity", []))
    for s in contract["stages"]:
        pins.update(s.get("integrity", []))
    return pins


def _frame_closed(state: journal.JournalState, current: dict[str, Any]) -> bool:
    # Class closure mirrors steer's frame-health rule (same constant, same
    # class scope) so the two surfaces can never disagree about "closed".
    rejected = sum(
        1
        for e in state.events
        if e["kind"] == "diagnosis_sealed.v1"
        and e["body"].get("class") == current["frame"]["class"]
        and e["body"].get("verdict") == "REJECTED"
    )
    if rejected >= CLASS_CLOSURE_THRESHOLD:
        return True
    # Budget closure demands accounted evidence, not just spent draws: every
    # issued spec sealed or abandoned, every sealed run diagnosed, and at
    # least one diagnosis in this generation — a budget burned entirely by
    # abandons is not a measured frame and does not license an auto jump.
    drawn = state.drawn_by_generation.get(state.generation, 0)
    if drawn < current["budget"]["iterations_total"]:
        return False
    if state.pending_runs or state.pending_diagnoses:
        return False
    return any(
        e["kind"] == "diagnosis_sealed.v1" and e["body"].get("generation") == state.generation
        for e in state.events
    )


def _verify_auto_grant(
    project: Path, state: journal.JournalState, successor: dict[str, Any]
) -> str:
    """Auto approval's whole basis, verified from the files and the journal,
    never trusted from approval.json. Returns the core digest for the ledger."""
    if state.contract_digest is None:
        raise JumpError(
            "auto approval needs a registered contract to compare against; "
            "this project has none"
        )
    registration = next(
        (
            e
            for e in reversed(state.events)
            if e["kind"] == "contract_registered.v1"
            and e["body"]["contract_digest"] == state.contract_digest
        ),
        None,
    )
    if registration is None:
        raise JumpError("no registration event matches the replayed contract digest")
    contract_rel = registration["body"].get("contract_path")
    if not contract_rel:
        raise JumpError("registration event carries no contract_path; auto approval unavailable")
    current_path = project / contract_rel
    if not current_path.is_file() or digest_file(current_path) != state.contract_digest:
        raise JumpError(
            "the registered contract's text is no longer at its registered path; "
            "auto approval cannot establish the current constitution — author the "
            "successor at a different path and keep the registered text in place, "
            "or use human approval"
        )
    try:
        current = load_contract(current_path)
    except ContractError as error:
        raise JumpError(f"registered contract invalid: {error}") from error

    current_core = current.get("core")
    if not current_core:
        raise JumpError(
            "auto approval requires a [core] section in the registered contract; "
            "without a sealed constitution every jump needs human approval"
        )
    successor_core = successor.get("core")
    if not successor_core:
        raise JumpError(
            "successor omits [core]; copy the registered contract's [core] verbatim, "
            "or use human approval"
        )
    if canonical_json(successor_core) != canonical_json(current_core):
        raise JumpError(
            "successor changes [core]; that is a constitutional jump — "
            "human approval.json (approved_by, statement) required"
        )
    if successor["project"]["id"] != current["project"]["id"]:
        raise JumpError("successor changes project.id; human approval required")
    if successor["budget"]["iterations_total"] > current["budget"]["iterations_total"]:
        raise JumpError(
            "successor raises budget.iterations_total; a frame may not grant "
            "itself more budget — human approval required"
        )
    if canonical_json(successor.get("revert")) != canonical_json(current.get("revert")):
        raise JumpError(
            "successor changes [revert]; revert semantics decide what a rejected "
            "iteration leaves behind — human approval required"
        )
    if _objective_set(successor) != _objective_set(current):
        raise JumpError(
            "successor changes the set of stage objectives (command/direction/margin/"
            "target/proxy_license); the measurement is constitutional — human approval required"
        )
    # Guards apply per stage in the kernel, so a union comparison could be
    # satisfied by parking every guard on a decoy stage: each successor stage
    # must carry every current guard itself.
    current_guards = _guard_set(current)
    for stage in successor["stages"]:
        if not _stage_guard_set(stage) >= current_guards:
            raise JumpError(
                f"successor stage {stage['id']!r} drops or weakens a guard; every "
                "stage must carry all current guards under auto approval — "
                "human approval required"
            )
    # Same decoy risk for stage-level pins: the successor must pin everything
    # the current frame pinned anywhere at top level, where it is global.
    if not set(successor.get("integrity", [])) >= _integrity_pins(current):
        raise JumpError(
            "successor's top-level integrity must carry every current integrity pin "
            "(top-level and stage); pins may only be added under auto approval — "
            "human approval required"
        )
    if not _frame_closed(state, current):
        raise JumpError(
            "current frame is not closed (budget remains and fewer than three "
            "REJECTED diagnoses); an auto jump from an open frame is frame-shopping "
            "— finish the generation or use human approval"
        )
    return digest_bytes(canonical_json(current_core).encode("utf-8"))


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


def _verify_full_auto_approval(project: Path, approval: dict[str, Any]) -> str:
    """Validate the pre-authorized agent decision and return its config digest."""
    autonomy.load_grant(project, required_scope="constitutional_jump")
    for field in _FULL_AUTO_APPROVAL_FIELDS:
        value = approval.get(field)
        if not isinstance(value, str) or not value.strip():
            raise JumpError(f"full_auto approval field {field!r} must be non-empty text")
    return digest_file(autonomy.grant_path(project))


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
    core_digest: str | None = None
    grant_digest: str | None = None
    if approval.get("mode") == "auto":
        core_digest = _verify_auto_grant(project, state, successor)
        approval_mode = "auto"
    elif approval.get("mode") == "full_auto":
        grant_digest = _verify_full_auto_approval(project, approval)
        approval_mode = "full_auto"
    else:
        if not str(approval.get("approved_by", "")).strip() or not str(approval.get("statement", "")).strip():
            raise JumpError("approval must carry approved_by and statement, written by the human")
        approval_mode = "human"

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
            "approval_mode": approval_mode,
            **(
                {
                    "full_auto_config_digest": grant_digest,
                    "full_auto_grant_digest": grant_digest,
                }
                if grant_digest
                else {}
            ),
            **(
                {
                    "core_digest": core_digest,
                    "core_baseline_contract_digest": state.contract_digest,
                }
                if core_digest
                else {}
            ),
        },
    )
    return {
        "status": "ADOPTED",
        "event_id": event["event_id"],
        "approval_mode": approval_mode,
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
    except (JumpError, autonomy.AutonomyError, journal.JournalError) as error:
        print(json.dumps({"status": "REFUSED", "reason": str(error)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
