from __future__ import annotations

import json
from pathlib import Path

import pytest

import aim
import journal
from seal import SealError, seal_abandon, seal_diagnosis, seal_run


def _summary(path: Path, spec_digest: str, **overrides) -> Path:
    body = {
        "summary_schema": "experiment-loop-summary-v2",
        "loop_id": "toy-descent-g1-001",
        "run_id": "abc123",
        "spec_digest": spec_digest,
        "iterations_run": 3,
        "accepted": 2,
        "decisions": {"accepted": 2, "rejected": 1},
        "stopped": "budget_exhausted",
        "objective": {"baseline": 10, "final": 8},
    }
    body.update(overrides)
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def _ledger(path: Path, lines: int = 3) -> Path:
    path.write_text("".join(json.dumps({"iteration": i}) + "\n" for i in range(1, lines + 1)), encoding="utf-8")
    return path


def test_run_seal_requires_an_issued_spec(registered_project: Path, tmp_path: Path) -> None:
    summary = _summary(tmp_path / "summary.json", "f" * 64)
    ledger = _ledger(tmp_path / "ledger.jsonl")
    with pytest.raises(SealError, match="no issued spec"):
        seal_run(registered_project, summary, ledger)


def test_migrated_run_seal_bypasses_issuance(registered_project: Path, tmp_path: Path) -> None:
    summary = _summary(tmp_path / "summary.json", "f" * 64)
    ledger = _ledger(tmp_path / "ledger.jsonl")
    result = seal_run(registered_project, summary, ledger, migrated=True)
    assert result["status"] == "RUN_SEALED"
    state = journal.replay(registered_project)
    assert state.runs_sealed[0]["body"]["origin"] == "migration"


def test_duplicate_run_seal_is_refused(registered_project: Path, tmp_path: Path) -> None:
    summary = _summary(tmp_path / "summary.json", "f" * 64)
    ledger = _ledger(tmp_path / "ledger.jsonl")
    seal_run(registered_project, summary, ledger, migrated=True)
    with pytest.raises(SealError, match="already sealed"):
        seal_run(registered_project, summary, ledger, migrated=True)


def test_trials_denominator_takes_the_larger_count(registered_project: Path, tmp_path: Path) -> None:
    issued = aim.issue(registered_project)
    summary = _summary(tmp_path / "summary.json", issued["spec_digest"])
    ledger = _ledger(tmp_path / "ledger.jsonl", lines=3)
    trials = tmp_path / "trials.jsonl"
    trials.write_text("".join(json.dumps({"trial": i}) + "\n" for i in range(7)), encoding="utf-8")
    result = seal_run(registered_project, summary, ledger, trials)
    assert result["trials_denominator"] == 7  # agent-side evaluations dominate


def test_summary_without_spec_digest_is_not_a_kernel_summary(
    registered_project: Path, tmp_path: Path
) -> None:
    summary = tmp_path / "summary.json"
    summary.write_text(json.dumps({"loop_id": "x"}), encoding="utf-8")
    ledger = _ledger(tmp_path / "ledger.jsonl")
    with pytest.raises(SealError, match="spec_digest"):
        seal_run(registered_project, summary, ledger, migrated=True)


def _seal_one_run(project: Path, tmp_path: Path) -> str:
    issued = aim.issue(project)
    summary = _summary(tmp_path / "summary.json", issued["spec_digest"], loop_id=issued["loop_id"])
    ledger = _ledger(tmp_path / "ledger.jsonl")
    return seal_run(project, summary, ledger)["event_id"]


def _diagnosis(path: Path, **overrides) -> Path:
    body = {
        "verdict": "REJECTED",
        "what_moved": "objective fell 10 to 8 across 3 iterations",
        "mechanism_interpretation": "the agent lowered the number directly; mechanism as declared",
        "counterfactual": "without the change the objective stays at 10 (entry probe)",
        "next_question": "does the descent survive a tighter guard set",
    }
    body.update(overrides)
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def test_diagnosis_seals_against_the_pending_run(registered_project: Path, tmp_path: Path) -> None:
    run_id = _seal_one_run(registered_project, tmp_path)
    result = seal_diagnosis(registered_project, _diagnosis(tmp_path / "d.json"))
    assert result["status"] == "DIAGNOSIS_SEALED"
    state = journal.replay(registered_project)
    assert not state.pending_diagnoses
    assert state.diagnoses[0]["body"]["run_seal_id"] == run_id


def test_diagnosis_with_replace_me_is_refused(registered_project: Path, tmp_path: Path) -> None:
    _seal_one_run(registered_project, tmp_path)
    bad = _diagnosis(tmp_path / "d.json", counterfactual="REPLACE_ME")
    with pytest.raises(SealError, match="REPLACE_ME"):
        seal_diagnosis(registered_project, bad)


def test_diagnosis_verdict_enum_is_closed(registered_project: Path, tmp_path: Path) -> None:
    _seal_one_run(registered_project, tmp_path)
    bad = _diagnosis(tmp_path / "d.json", verdict="VALIDATED")  # not this system's word
    with pytest.raises(SealError, match="verdict"):
        seal_diagnosis(registered_project, bad)


def test_diagnosis_without_a_pending_run_is_refused(registered_project: Path, tmp_path: Path) -> None:
    with pytest.raises(SealError, match="awaiting"):
        seal_diagnosis(registered_project, _diagnosis(tmp_path / "d.json"))


def test_abandon_requires_a_pending_spec_and_a_reason(registered_project: Path) -> None:
    issued = aim.issue(registered_project)
    with pytest.raises(SealError, match="non-empty reason"):
        seal_abandon(registered_project, issued["spec_digest"], "  ")
    result = seal_abandon(registered_project, issued["spec_digest"], "agent crashed mid-run")
    assert result["status"] == "RUN_ABANDONED"
    with pytest.raises(SealError, match="no pending run"):
        seal_abandon(registered_project, issued["spec_digest"], "again")
