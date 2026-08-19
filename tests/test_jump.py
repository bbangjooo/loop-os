from __future__ import annotations

import json
from pathlib import Path

import pytest

from ros import journal, jump, note, steer
from ros.seal import SealError, seal_contract
from tests.conftest import CONTRACT_TEMPLATE
from tests.test_steer import _cycle


def _rival(project: Path) -> str:
    return note.record(
        project,
        "rival_draft",
        {
            "commitment_rejected": "the number wants to go down",
            "proposed_frame": "ascent frame",
            "mechanism": "inversion",
            "falsifier": "descent keeps working",
        },
        [],
    )["note_id"]


def _successor(project: Path, tmp_path: Path, generation: int = 2) -> Path:
    text = CONTRACT_TEMPLATE.format(
        total=6, per_run=3, objective=tmp_path / "objective.py", agent=tmp_path / "agent.py"
    ).replace("generation = 1", f"generation = {generation}").replace(
        'class = "toy_descent"', 'class = "toy_ascent"'
    )
    path = project / "contract.successor.toml"
    path.write_text(text, encoding="utf-8")
    return path


def _jump_inputs(project: Path, tmp_path: Path, generation: int = 2) -> dict[str, Path]:
    dossier_path = tmp_path / "dossier.json"
    dossier_path.write_text(
        json.dumps(steer.dossier(project, _rival(project))), encoding="utf-8"
    )
    review = tmp_path / "review.json"
    review.write_text(
        json.dumps({"reviewer": "codex gpt-5.6-sol", "independent": True, "verdict": "PASS", "notes": "n"}),
        encoding="utf-8",
    )
    approval = tmp_path / "approval.json"
    approval.write_text(
        json.dumps({"approved_by": "bbangjo", "statement": "open the ascent frame"}),
        encoding="utf-8",
    )
    return {
        "dossier_path": dossier_path,
        "successor_path": _successor(project, tmp_path, generation),
        "review_path": review,
        "approval_path": approval,
    }


def test_adoption_is_one_atomic_event(registered_project: Path, tmp_path: Path) -> None:
    _cycle(registered_project, tmp_path, 1, "REJECTED")
    inputs = _jump_inputs(registered_project, tmp_path)
    result = jump.adopt(registered_project, **inputs)
    assert result["status"] == "ADOPTED"
    events = journal.load_events(registered_project)
    adoptions = [e for e in events if e["kind"] == "adoption.v1"]
    assert len(adoptions) == 1
    body = adoptions[0]["body"]
    assert body["successor_generation"] == 2
    assert len(body["dossier_digest"]) == 64


def test_missing_input_makes_adoption_impossible(registered_project: Path, tmp_path: Path) -> None:
    inputs = _jump_inputs(registered_project, tmp_path)
    inputs["approval_path"] = tmp_path / "nonexistent.json"
    with pytest.raises(jump.JumpError, match="approval file not found"):
        jump.adopt(registered_project, **inputs)


def test_review_must_declare_independence_and_pass(registered_project: Path, tmp_path: Path) -> None:
    inputs = _jump_inputs(registered_project, tmp_path)
    inputs["review_path"].write_text(
        json.dumps({"reviewer": "codex", "independent": False, "verdict": "PASS"}), encoding="utf-8"
    )
    with pytest.raises(jump.JumpError, match="independent"):
        jump.adopt(registered_project, **inputs)
    inputs["review_path"].write_text(
        json.dumps({"reviewer": "codex", "independent": True, "verdict": "FAIL"}), encoding="utf-8"
    )
    with pytest.raises(jump.JumpError, match="PASS"):
        jump.adopt(registered_project, **inputs)


def test_successor_generation_must_increment_by_one(registered_project: Path, tmp_path: Path) -> None:
    inputs = _jump_inputs(registered_project, tmp_path, generation=5)
    with pytest.raises(jump.JumpError, match="generation must be 2"):
        jump.adopt(registered_project, **inputs)


def test_stale_dossier_is_refused(registered_project: Path, tmp_path: Path) -> None:
    inputs = _jump_inputs(registered_project, tmp_path)
    dossier = json.loads(inputs["dossier_path"].read_text(encoding="utf-8"))
    dossier["current_frame"]["contract_digest"] = "0" * 64
    inputs["dossier_path"].write_text(json.dumps(dossier), encoding="utf-8")
    with pytest.raises(jump.JumpError, match="different registered contract"):
        jump.adopt(registered_project, **inputs)


def test_generation_bump_requires_adoption(registered_project: Path, tmp_path: Path) -> None:
    successor = _successor(registered_project, tmp_path)
    with pytest.raises(SealError, match="adoption"):
        seal_contract(registered_project, successor)
    inputs = _jump_inputs(registered_project, tmp_path)
    # The adoption must cite this exact successor text, not just any file.
    jump.adopt(registered_project, **{**inputs, "successor_path": successor})
    result = seal_contract(registered_project, successor)
    assert result["status"] == "CONTRACT_REGISTERED"
    state = journal.replay(registered_project)
    assert state.generation == 2
