"""aim: turn a contract plus the journal into one kernel spec.

The only path from research intent to kernel execution. Reads exactly two
inputs — contract.toml and the journal — and emits exactly two outputs — a
spec.yaml the kernel can run, and one spec_issued journal event. Notes,
claims, and any other advisory material never enter this function except via
an adopted successor contract (design §2.3, consumer rule).

Fail-closed refusal ladder, in order:
    R1 journal not bootstrapped / chain broken
    R2 contract not registered, or the file drifted since registration
    R3 an issued spec has no sealed (or abandoned) run yet
    R4 a sealed run has no sealed diagnosis yet
    R5 the generation budget cannot cover this spec's draw

The budget is reserved-not-measured: the draw happens at issue time and an
abandoned run does not refund it.

Instrument surface:
    python -m ros.aim --project DIR [--contract contract.toml]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

import yaml

from . import journal
from ._canon import digest_file

CONTRACT_SCHEMA = "ros2-contract-v1"
CONTRACT_NAME = "contract.toml"
RUNS_ROOT = Path("loop") / "runs"

DIRECTIONS = ("minimize", "maximize")
GUARD_KINDS = ("exit_zero", "unchanged_output", "non_decreasing_number", "non_increasing_number")
NUMERIC_GUARD_KINDS = ("non_decreasing_number", "non_increasing_number")
ON_INCOMPLETE = ("stop", "continue")

_CONTRACT_KEYS = {"schema", "project", "frame", "budget", "agent", "integrity", "revert", "stages"}
_PROJECT_KEYS = {"id", "name"}
_FRAME_KEYS = {"generation", "class", "mechanism"}
_BUDGET_KEYS = {"iterations_total"}
_AGENT_KEYS = {"command", "timeout_seconds", "summary_prefix"}
_STAGE_KEYS = {"id", "prompt", "iterations", "on_incomplete", "integrity", "objective", "guards"}
_OBJECTIVE_KEYS = {"command", "direction", "margin", "target", "timeout_seconds", "proxy_license"}
_GUARD_KEYS = {"id", "command", "kind", "timeout_seconds", "tolerance", "ratchet"}


class ContractError(ValueError):
    """The contract cannot be used as written."""


class AimRefusal(RuntimeError):
    """A precondition failed; the message names the missing input."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code


def _require_mapping(value: Any, allowed: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{where} must be a table")
    unknown = set(value) - allowed
    if unknown:
        raise ContractError(f"{where} has unknown keys: {sorted(unknown)}")
    return value


def _require_text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{where} must be a non-empty string")
    return value


def _require_argv(value: Any, where: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(i, str) for i in value):
        raise ContractError(f"{where} must be a non-empty list of strings")
    return value


def load_contract(path: Path) -> dict[str, Any]:
    """Parse and strictly validate a contract. Unknown keys are errors."""
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ContractError(f"cannot read contract: {error}") from error
    _require_mapping(raw, _CONTRACT_KEYS, "contract")
    if raw.get("schema") != CONTRACT_SCHEMA:
        raise ContractError(f"schema must be {CONTRACT_SCHEMA!r}")

    project = _require_mapping(raw.get("project"), _PROJECT_KEYS, "project")
    _require_text(project.get("id"), "project.id")

    frame = _require_mapping(raw.get("frame"), _FRAME_KEYS, "frame")
    if not isinstance(frame.get("generation"), int) or frame["generation"] < 1:
        raise ContractError("frame.generation must be a positive integer")
    _require_text(frame.get("class"), "frame.class")
    _require_text(frame.get("mechanism"), "frame.mechanism")

    budget = _require_mapping(raw.get("budget"), _BUDGET_KEYS, "budget")
    if not isinstance(budget.get("iterations_total"), int) or budget["iterations_total"] < 1:
        raise ContractError("budget.iterations_total must be a positive integer")

    agent = _require_mapping(raw.get("agent"), _AGENT_KEYS, "agent")
    _require_argv(agent.get("command"), "agent.command")

    if "integrity" in raw and not (
        isinstance(raw["integrity"], list) and all(isinstance(p, str) for p in raw["integrity"])
    ):
        raise ContractError("integrity must be a list of paths")

    stages = raw.get("stages")
    if not isinstance(stages, list) or not stages:
        raise ContractError("stages must be a non-empty array of tables")
    seen_ids: set[str] = set()
    for index, stage in enumerate(stages):
        where = f"stages[{index}]"
        _require_mapping(stage, _STAGE_KEYS, where)
        stage_id = _require_text(stage.get("id"), f"{where}.id")
        if stage_id in seen_ids:
            raise ContractError(f"duplicate stage id {stage_id!r}")
        seen_ids.add(stage_id)
        _require_text(stage.get("prompt"), f"{where}.prompt")
        if not isinstance(stage.get("iterations"), int) or stage["iterations"] < 1:
            raise ContractError(f"{where}.iterations must be a positive integer")
        if "on_incomplete" in stage and stage["on_incomplete"] not in ON_INCOMPLETE:
            raise ContractError(f"{where}.on_incomplete must be one of {ON_INCOMPLETE}")
        objective = _require_mapping(stage.get("objective"), _OBJECTIVE_KEYS, f"{where}.objective")
        _require_argv(objective.get("command"), f"{where}.objective.command")
        if objective.get("direction") not in DIRECTIONS:
            raise ContractError(f"{where}.objective.direction must be one of {DIRECTIONS}")
        # The statistical seam: every objective must name the contract clause
        # that licenses it as a proxy (design §7). The kernel never sees this
        # field; it exists so the journal can hold the author to it.
        _require_text(objective.get("proxy_license"), f"{where}.objective.proxy_license")
        for gindex, guard in enumerate(stage.get("guards", [])):
            gwhere = f"{where}.guards[{gindex}]"
            _require_mapping(guard, _GUARD_KEYS, gwhere)
            _require_text(guard.get("id"), f"{gwhere}.id")
            _require_argv(guard.get("command"), f"{gwhere}.command")
            if guard.get("kind") not in GUARD_KINDS:
                raise ContractError(f"{gwhere}.kind must be one of {GUARD_KINDS}")
            if guard["kind"] not in NUMERIC_GUARD_KINDS and (
                "tolerance" in guard or "ratchet" in guard
            ):
                raise ContractError(f"{gwhere}: tolerance/ratchet apply only to numeric kinds")
    return raw


def build_spec(contract: dict[str, Any], loop_id: str, contract_path: Path, project: Path) -> dict[str, Any]:
    """Translate a validated contract into the kernel's spec schema.

    proxy_license is stripped (the kernel's schema is closed); the contract
    file itself joins the integrity pins so the frame cannot drift mid-run.
    """
    pins = list(contract.get("integrity", []))
    contract_rel = contract_path.resolve().relative_to(project.resolve())
    if str(contract_rel) not in pins:
        pins.append(str(contract_rel))
    stages = []
    for stage in contract["stages"]:
        objective = {k: v for k, v in stage["objective"].items() if k != "proxy_license"}
        entry: dict[str, Any] = {
            "id": stage["id"],
            "objective": objective,
            "budget": {"iterations": stage["iterations"]},
            "prompt": stage["prompt"],
        }
        if stage.get("guards"):
            entry["guards"] = stage["guards"]
        if stage.get("integrity"):
            entry["integrity"] = stage["integrity"]
        if stage.get("on_incomplete"):
            entry["on_incomplete"] = stage["on_incomplete"]
        stages.append(entry)
    return {
        "loop_id": loop_id,
        "agent": contract["agent"],
        "integrity": pins,
        "stages": stages,
    }


def issue(project: Path, contract_path: Path | None = None) -> dict[str, Any]:
    project = project.resolve()
    contract_path = (contract_path or project / CONTRACT_NAME).resolve()

    # R1 — the journal must exist and its chain must hold.
    try:
        state = journal.replay(project)
    except journal.JournalError as error:
        raise AimRefusal("R1_JOURNAL", str(error)) from error

    contract = load_contract(contract_path)
    contract_digest = digest_file(contract_path)
    generation = contract["frame"]["generation"]

    # R2 — the contract on disk must be the registered one.
    if state.contract_digest is None:
        raise AimRefusal("R2_CONTRACT", "contract not registered; seal it first (ros.seal contract)")
    if state.contract_digest != contract_digest:
        raise AimRefusal(
            "R2_CONTRACT",
            "contract drifted since registration; re-register it or restore the registered text",
        )

    # R3 — every issued spec must be sealed or abandoned before the next aim.
    if state.pending_runs:
        pending = sorted(e["body"]["loop_id"] for e in state.pending_runs.values())
        raise AimRefusal("R3_PENDING_RUN", f"unsealed run(s) for spec(s): {pending}")

    # R4 — every sealed run must carry a sealed diagnosis.
    if state.pending_diagnoses:
        raise AimRefusal(
            "R4_PENDING_DIAGNOSIS",
            f"run(s) awaiting diagnosis: {sorted(state.pending_diagnoses)}",
        )

    # R5 — the draw must fit the generation budget. Reserved, not refunded.
    draw = sum(stage["iterations"] for stage in contract["stages"])
    drawn = state.drawn_by_generation.get(generation, 0)
    total = contract["budget"]["iterations_total"]
    if drawn + draw > total:
        raise AimRefusal(
            "R5_BUDGET",
            f"generation {generation} budget exhausted: drawn={drawn} draw={draw} total={total}",
        )

    sequence = sum(1 for e in state.events if e["kind"] == "spec_issued.v1") + 1
    class_slug = contract["frame"]["class"].replace("_", "-")
    loop_id = f"{class_slug}-g{generation}-{sequence:03d}"
    date = _dt.date.today().isoformat()
    spec_dir = project / RUNS_ROOT / f"{date}-{loop_id}"
    spec_dir.mkdir(parents=True, exist_ok=False)
    spec_path = spec_dir / "spec.yaml"
    spec = build_spec(contract, loop_id, contract_path, project)
    spec_path.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True), encoding="utf-8")

    event = journal.append_event(
        project,
        "spec_issued.v1",
        {
            "loop_id": loop_id,
            "spec_path": str(spec_path.relative_to(project)),
            "spec_digest": digest_file(spec_path),
            "contract_digest": contract_digest,
            "generation": generation,
            "class": contract["frame"]["class"],
            "proxy_licenses": [s["objective"]["proxy_license"] for s in contract["stages"]],
            "draw": draw,
        },
    )
    return {
        "status": "SPEC_ISSUED",
        "loop_id": loop_id,
        "spec_path": str(spec_path.relative_to(project)),
        "spec_digest": event["body"]["spec_digest"],
        "draw": draw,
        "budget_remaining": total - drawn - draw,
        "event_id": event["event_id"],
        "note": "commit the spec before running; the kernel refuses an untracked in-worktree spec",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ros.aim")
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--contract", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        result = issue(args.project, args.contract)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (AimRefusal, ContractError) as error:
        code = getattr(error, "code", "CONTRACT_INVALID")
        print(json.dumps({"status": "REFUSED", "code": code, "reason": str(error)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
