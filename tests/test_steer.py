from __future__ import annotations

import json
from pathlib import Path

import pytest

from ros import aim, journal, note, steer
from ros.seal import seal_diagnosis, seal_run


def _summary(path: Path, spec_digest: str, baseline: float, final: float) -> Path:
    path.write_text(
        json.dumps(
            {
                "loop_id": "toy-descent-g1-001",
                "run_id": "r",
                "spec_digest": spec_digest,
                "iterations_run": 3,
                "accepted": 1,
                "decisions": {"accepted": 1, "rejected": 2},
                "stopped": "budget_exhausted",
                "objective": {"baseline": baseline, "final": final, "target": 0},
            }
        ),
        encoding="utf-8",
    )
    return path


def _ledger(path: Path) -> Path:
    path.write_text('{"iteration":1}\n{"iteration":2}\n{"iteration":3}\n', encoding="utf-8")
    return path


def _cycle(project: Path, tmp_path: Path, index: int, verdict: str) -> None:
    """One migrated run + diagnosis with the given verdict."""
    spec_digest = format(index, "064x")
    summary = _summary(tmp_path / f"summary{index}.json", spec_digest, 10 - index, 9 - index)
    ledger = _ledger(tmp_path / f"ledger{index}.jsonl")
    seal_run(project, summary, ledger, migrated=True)
    diagnosis = tmp_path / f"d{index}.json"
    diagnosis.write_text(
        json.dumps(
            {
                "verdict": verdict,
                "what_moved": f"run {index}",
                "mechanism_interpretation": "direct decrement failed to generalize",
                "counterfactual": "entry probe held",
                "next_question": "n",
            }
        ),
        encoding="utf-8",
    )
    seal_diagnosis(project, diagnosis)


def test_status_aggregates_classes_and_notes(registered_project: Path, tmp_path: Path) -> None:
    _cycle(registered_project, tmp_path, 1, "REJECTED")
    note.record(registered_project, "idea", {"text": "x"}, [])
    result = steer.status(registered_project)
    assert result["class_states"]["toy_descent"]["runs"] == 1
    assert result["class_states"]["toy_descent"]["verdicts"] == {"REJECTED": 1}
    assert result["notes_by_kind"] == {"idea": 1}


def test_frame_health_carries_evidence_not_verdicts(registered_project: Path, tmp_path: Path) -> None:
    _cycle(registered_project, tmp_path, 1, "REJECTED")
    packet = steer.frame_health(registered_project)
    row = packet["margin_trajectory"][0]
    assert (row["baseline"], row["final"]) == (9, 8)
    assert row["verdict"] == "REJECTED"
    ids = [r["id"] for r in packet["interpretation_requests"]]
    assert ids == ["stagnation", "assumption_misfit", "frame_misfit"]
    flat = json.dumps(packet)
    assert "stagnating" not in flat  # the packet never judges


def test_class_closes_at_three_rejections(registered_project: Path, tmp_path: Path) -> None:
    for i in (1, 2):
        _cycle(registered_project, tmp_path, i, "REJECTED")
    assert steer.residual(registered_project)["closed_classes"] == []
    _cycle(registered_project, tmp_path, 3, "REJECTED")
    tasks = steer.residual(registered_project)["closed_classes"]
    assert len(tasks) == 1
    assert tasks[0]["class"] == "toy_descent"
    assert len(tasks[0]["rejected_attempts"]) == 3
    assert "commitment" in tasks[0]["instruction"]


def test_inconclusive_does_not_close_a_class(registered_project: Path, tmp_path: Path) -> None:
    for i, verdict in enumerate(("REJECTED", "REJECTED", "INCONCLUSIVE"), start=1):
        _cycle(registered_project, tmp_path, i, verdict)
    assert steer.residual(registered_project)["closed_classes"] == []


def test_dossier_requires_a_verified_rival_draft(registered_project: Path) -> None:
    with pytest.raises(journal.JournalError, match="rival_draft"):
        steer.dossier(registered_project, "note-missing")


def test_dossier_binds_rival_frame_and_obligations(registered_project: Path, tmp_path: Path) -> None:
    _cycle(registered_project, tmp_path, 1, "REJECTED")
    rival = note.record(
        registered_project,
        "rival_draft",
        {
            "commitment_rejected": "the number wants to go down",
            "proposed_frame": "the number wants to go up",
            "mechanism": "inversion",
            "falsifier": "descent keeps working",
        },
        [],
    )
    result = steer.dossier(registered_project, rival["note_id"])
    assert result["rival_draft"]["note_id"] == rival["note_id"]
    assert result["current_frame"]["class"] == "toy_descent"
    steps = [o["step"] for o in result["authoring_obligations"]]
    assert steps == ["successor_contract", "independent_review", "human_approval", "adoption"]
