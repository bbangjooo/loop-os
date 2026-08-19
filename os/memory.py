"""memory: durable claims distilled from sealed diagnoses.

Deterministic extraction — no interpretation happens here. Each sealed
diagnosis yields one claim record carrying the verdict, the class, and the
digest-linked provenance chain (diagnosis -> run seal -> spec). Claims are
advisory retrieval material for future aim/read work; they never gate
anything (the only path from memory to a spec is the author reading it).

Retrieval is exact-class by design: cross-class reads are the discovery
lane's business (analogies live in notes), not memory's.

Instrument surface:
    python os/memory.py extract  --project DIR
    python os/memory.py retrieve --project DIR --class CLASS
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import journal
from _canon import canonical_json, digest_bytes

CLAIMS_NAME = "claims.jsonl"


def claims_path(project: Path) -> Path:
    return project / journal.JOURNAL_DIR / CLAIMS_NAME


def load_claims(project: Path) -> list[dict[str, Any]]:
    """Claims whose digests match their seals; tampered lines are dropped."""
    sealed: dict[str, str] = {}
    for event in journal.load_events(project):
        if event["kind"] == "claim_sealed.v1":
            for item in event["body"]["claims"]:
                sealed[item["claim_id"]] = item["claim_digest"]
    verified: list[dict[str, Any]] = []
    path = claims_path(project)
    if not path.exists():
        return verified
    for line in path.read_bytes().splitlines():
        if not line.strip():
            continue
        claim = json.loads(line)
        if sealed.get(claim.get("claim_id")) == digest_bytes(line):
            verified.append(claim)
    return verified


def extract(project: Path) -> dict[str, Any]:
    """Distill every not-yet-claimed sealed diagnosis into one claim each.
    One journal append per invocation (batch), per the pure-function rule."""
    project = project.resolve()
    state = journal.replay(project)
    already = {c["run_seal_id"] for c in load_claims(project)}
    runs = {e["event_id"]: e["body"] for e in state.runs_sealed}

    new_lines: list[bytes] = []
    sealed_refs: list[dict[str, str]] = []
    for diagnosis in state.diagnoses:
        body = diagnosis["body"]
        run_seal_id = body["run_seal_id"]
        if run_seal_id in already:
            continue
        run = runs.get(run_seal_id, {})
        claim = {
            "claim_id": "claim-" + diagnosis["event_id"].removeprefix("ev-"),
            "class": body.get("class") or run.get("class"),
            "generation": body.get("generation") or run.get("generation"),
            "verdict": body["verdict"],
            "loop_id": run.get("loop_id"),
            "run_seal_id": run_seal_id,
            "spec_digest": body.get("spec_digest"),
            "diagnosis_digest": body["diagnosis_digest"],
            "diagnosis_path": body.get("diagnosis_path"),
        }
        line = canonical_json(claim).encode("utf-8")
        new_lines.append(line)
        sealed_refs.append({"claim_id": claim["claim_id"], "claim_digest": digest_bytes(line)})

    if not new_lines:
        return {"status": "NOTHING_TO_EXTRACT", "claims": 0}
    with claims_path(project).open("ab") as handle:
        for line in new_lines:
            handle.write(line + b"\n")
    event = journal.append_event(project, "claim_sealed.v1", {"claims": sealed_refs})
    return {"status": "CLAIMS_SEALED", "claims": len(sealed_refs), "event_id": event["event_id"]}


def retrieve(project: Path, class_name: str) -> dict[str, Any]:
    claims = [c for c in load_claims(project.resolve()) if c.get("class") == class_name]
    return {"status": "OK", "class": class_name, "claims": claims, "note": "advisory retrieval; grants nothing"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="memory")
    sub = parser.add_subparsers(dest="command", required=True)
    ext = sub.add_parser("extract")
    ext.add_argument("--project", type=Path, required=True)
    ret = sub.add_parser("retrieve")
    ret.add_argument("--project", type=Path, required=True)
    ret.add_argument("--class", dest="class_name", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "extract":
            result = extract(args.project)
        else:
            result = retrieve(args.project, args.class_name)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except journal.JournalError as error:
        print(json.dumps({"status": "REFUSED", "reason": str(error)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
