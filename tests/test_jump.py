from __future__ import annotations

import json
from pathlib import Path

import pytest

import autonomy
import journal
import jump
import note
import steer
from seal import SealError, seal_contract
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


def test_revoke_rolls_the_frame_back(registered_project: Path, tmp_path: Path) -> None:
    successor = _successor(registered_project, tmp_path)
    inputs = _jump_inputs(registered_project, tmp_path)
    adopted = jump.adopt(registered_project, **{**inputs, "successor_path": successor})
    seal_contract(registered_project, successor)
    assert journal.replay(registered_project).generation == 2
    result = jump.revoke(registered_project, adopted["event_id"], "reviewer retracted after new evidence")
    assert result["status"] == "REVOKED"
    state = journal.replay(registered_project)
    # The registration that cited the adoption is void on replay; the frame
    # falls back to generation 1's registered contract.
    assert state.generation == 1
    assert result["generation_now"] == 1
    # Re-registering generation 2 now needs a fresh adoption.
    with pytest.raises(SealError, match="adoption"):
        seal_contract(registered_project, successor)


def test_revoke_window_closes_when_budget_is_drawn(registered_project: Path, tmp_path: Path) -> None:
    import aim

    successor = _successor(registered_project, tmp_path)
    inputs = _jump_inputs(registered_project, tmp_path)
    adopted = jump.adopt(registered_project, **{**inputs, "successor_path": successor})
    seal_contract(registered_project, successor)
    aim.issue(registered_project, successor)  # generation 2 draws budget
    with pytest.raises(jump.JumpError, match="cannot be revoked"):
        jump.revoke(registered_project, adopted["event_id"], "too late")


def test_revoke_requires_an_active_adoption_and_a_reason(registered_project: Path, tmp_path: Path) -> None:
    with pytest.raises(jump.JumpError, match="non-empty reason"):
        jump.revoke(registered_project, "ev-whatever", " ")
    with pytest.raises(jump.JumpError, match="no active adoption"):
        jump.revoke(registered_project, "ev-whatever", "reason")
    inputs = _jump_inputs(registered_project, tmp_path)
    adopted = jump.adopt(registered_project, **inputs)
    jump.revoke(registered_project, adopted["event_id"], "first revoke")
    with pytest.raises(jump.JumpError, match="no active adoption"):
        jump.revoke(registered_project, adopted["event_id"], "double revoke")


def _auto_approval(tmp_path: Path) -> Path:
    path = tmp_path / "approval.auto.json"
    path.write_text(
        json.dumps({"mode": "auto", "basis": "core-preserved"}), encoding="utf-8"
    )
    return path


def _full_auto_approval(tmp_path: Path) -> Path:
    path = tmp_path / "approval.full-auto.json"
    path.write_text(
        json.dumps(
            {
                "mode": "full_auto",
                "decision": "change the constitution because the current measurement is exhausted",
                "evidence": "the dossier and three failed mechanisms support a new objective",
                "goal_continuity": "the successor keeps the user's end outcome while changing its proxy",
                "risk_assessment": "the new measurement may weaken comparability across generations",
                "rollback_plan": "revoke before the first draw or open a corrective successor afterward",
            }
        ),
        encoding="utf-8",
    )
    return path


def _close_frame(project: Path, tmp_path: Path) -> None:
    """Three REJECTED diagnoses close the class without drawing budget."""
    for index in (1, 2, 3):
        _cycle(project, tmp_path, index, "REJECTED")


def test_auto_approval_adopts_when_core_is_preserved(registered_project: Path, tmp_path: Path) -> None:
    _close_frame(registered_project, tmp_path)
    inputs = _jump_inputs(registered_project, tmp_path)
    # Frame exploration is free under auto: new prompt, fewer iterations.
    successor = inputs["successor_path"]
    successor.write_text(
        successor.read_text(encoding="utf-8")
        .replace("Lower the number in value.txt by exactly 1.", "Climb toward zero from above.")
        .replace("iterations = 3", "iterations = 2"),
        encoding="utf-8",
    )
    inputs["approval_path"] = _auto_approval(tmp_path)
    result = jump.adopt(registered_project, **inputs)
    assert result["status"] == "ADOPTED"
    assert result["approval_mode"] == "auto"
    events = journal.load_events(registered_project)
    body = next(e for e in events if e["kind"] == "adoption.v1")["body"]
    assert body["approval_mode"] == "auto"
    assert len(body["core_digest"]) == 64
    assert len(body["core_baseline_contract_digest"]) == 64


def test_auto_approval_refused_while_frame_is_open(registered_project: Path, tmp_path: Path) -> None:
    inputs = _jump_inputs(registered_project, tmp_path)
    inputs["approval_path"] = _auto_approval(tmp_path)
    with pytest.raises(jump.JumpError, match="not closed"):
        jump.adopt(registered_project, **inputs)


def test_auto_approval_refused_when_core_changes(registered_project: Path, tmp_path: Path) -> None:
    _close_frame(registered_project, tmp_path)
    inputs = _jump_inputs(registered_project, tmp_path)
    successor = inputs["successor_path"]
    successor.write_text(
        successor.read_text(encoding="utf-8").replace(
            'goal = "drive the number in value.txt to 0"',
            'goal = "drive the number in value.txt below 5"',
        ),
        encoding="utf-8",
    )
    inputs["approval_path"] = _auto_approval(tmp_path)
    with pytest.raises(jump.JumpError, match="constitutional"):
        jump.adopt(registered_project, **inputs)
    # The loosened frame still opens with a human signature.
    human = tmp_path / "approval.human.json"
    human.write_text(
        json.dumps({"approved_by": "bbangjo", "statement": "loosen the target knowingly"}),
        encoding="utf-8",
    )
    result = jump.adopt(registered_project, **{**inputs, "approval_path": human})
    assert result["approval_mode"] == "human"


def test_auto_approval_refused_without_a_sealed_core(registered_project: Path, tmp_path: Path) -> None:
    _close_frame(registered_project, tmp_path)
    contract_path = registered_project / "contract.toml"
    text = contract_path.read_text(encoding="utf-8")
    stripped = text.replace('[core]\ngoal = "drive the number in value.txt to 0"\n\n', "")
    contract_path.write_text(stripped, encoding="utf-8")
    seal_contract(registered_project)  # same generation, re-registration
    inputs = _jump_inputs(registered_project, tmp_path)
    inputs["approval_path"] = _auto_approval(tmp_path)
    with pytest.raises(jump.JumpError, match=r"\[core\] section in the registered contract"):
        jump.adopt(registered_project, **inputs)


def test_auto_approval_refused_when_budget_is_inflated(registered_project: Path, tmp_path: Path) -> None:
    _close_frame(registered_project, tmp_path)
    inputs = _jump_inputs(registered_project, tmp_path)
    successor = inputs["successor_path"]
    successor.write_text(
        successor.read_text(encoding="utf-8").replace(
            "iterations_total = 6", "iterations_total = 60"
        ),
        encoding="utf-8",
    )
    inputs["approval_path"] = _auto_approval(tmp_path)
    with pytest.raises(jump.JumpError, match="more budget"):
        jump.adopt(registered_project, **inputs)


def test_auto_approval_refused_when_registered_text_is_gone(registered_project: Path, tmp_path: Path) -> None:
    _close_frame(registered_project, tmp_path)
    inputs = _jump_inputs(registered_project, tmp_path)
    contract_path = registered_project / "contract.toml"
    contract_path.write_text(
        contract_path.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8"
    )
    inputs["approval_path"] = _auto_approval(tmp_path)
    with pytest.raises(jump.JumpError, match="registered path"):
        jump.adopt(registered_project, **inputs)


def test_auto_approval_refused_on_unregistered_project(project: Path, tmp_path: Path) -> None:
    journal.append_event(project, "bootstrap.v1", {"project_id": "toy", "lineage": []})
    dossier = tmp_path / "dossier.json"
    dossier.write_text(
        json.dumps({"rival_draft": {"note_id": "n1"}, "current_frame": {}}), encoding="utf-8"
    )
    review = tmp_path / "review.json"
    review.write_text(
        json.dumps({"reviewer": "r", "independent": True, "verdict": "PASS"}), encoding="utf-8"
    )
    with pytest.raises(jump.JumpError, match="registered contract to compare"):
        jump.adopt(
            project,
            dossier,
            _successor(project, tmp_path, generation=2),
            review,
            _auto_approval(tmp_path),
        )


def test_auto_approval_refused_when_measurement_changes(registered_project: Path, tmp_path: Path) -> None:
    _close_frame(registered_project, tmp_path)
    inputs = _jump_inputs(registered_project, tmp_path)
    successor = inputs["successor_path"]
    successor.write_text(
        successor.read_text(encoding="utf-8").replace('direction = "minimize"', 'direction = "maximize"'),
        encoding="utf-8",
    )
    inputs["approval_path"] = _auto_approval(tmp_path)
    with pytest.raises(jump.JumpError, match="measurement is constitutional"):
        jump.adopt(registered_project, **inputs)


def test_auto_approval_refused_when_a_guard_is_dropped(registered_project: Path, tmp_path: Path) -> None:
    _close_frame(registered_project, tmp_path)
    inputs = _jump_inputs(registered_project, tmp_path)
    successor = inputs["successor_path"]
    successor.write_text(
        successor.read_text(encoding="utf-8").split("[[stages.guards]]")[0], encoding="utf-8"
    )
    inputs["approval_path"] = _auto_approval(tmp_path)
    with pytest.raises(jump.JumpError, match="drops or weakens a guard"):
        jump.adopt(registered_project, **inputs)


def test_auto_approval_refused_when_integrity_pin_dropped(registered_project: Path, tmp_path: Path) -> None:
    _close_frame(registered_project, tmp_path)
    contract_path = registered_project / "contract.toml"
    contract_path.write_text(
        contract_path.read_text(encoding="utf-8").replace(
            'schema = "ros2-contract-v1"', 'schema = "ros2-contract-v1"\nintegrity = ["app.py"]'
        ),
        encoding="utf-8",
    )
    seal_contract(registered_project)  # same generation, re-registration
    inputs = _jump_inputs(registered_project, tmp_path)  # successor has no integrity pins
    inputs["approval_path"] = _auto_approval(tmp_path)
    with pytest.raises(jump.JumpError, match="integrity pin"):
        jump.adopt(registered_project, **inputs)


def test_auto_approval_refused_when_project_id_changes(registered_project: Path, tmp_path: Path) -> None:
    _close_frame(registered_project, tmp_path)
    inputs = _jump_inputs(registered_project, tmp_path)
    successor = inputs["successor_path"]
    successor.write_text(
        successor.read_text(encoding="utf-8").replace('id = "toy"', 'id = "toy2"'),
        encoding="utf-8",
    )
    inputs["approval_path"] = _auto_approval(tmp_path)
    with pytest.raises(jump.JumpError, match="project.id"):
        jump.adopt(registered_project, **inputs)


def _extra_stage(tmp_path: Path, direction: str, with_guard: bool) -> str:
    guard = (
        '\n[[stages.guards]]\nid = "app-intact"\ncommand = ["python3", "-c", '
        '"import pathlib,sys; sys.exit(0 if pathlib.Path(\'app.py\').exists() else 1)"]\n'
        'kind = "exit_zero"\ntimeout_seconds = 30\n'
        if with_guard
        else ""
    )
    return (
        f'\n[[stages]]\nid = "extra"\nprompt = "extra stage"\niterations = 1\n'
        f'\n[stages.objective]\ncommand = ["python3", "{tmp_path / "objective.py"}"]\n'
        f'direction = "{direction}"\nmargin = 1\ntarget = 0\ntimeout_seconds = 30\n'
        f'proxy_license = "toy contract clause 1: the number itself is the goal, not a proxy."\n'
        + guard
    )


def test_auto_approval_refused_when_guards_park_on_a_decoy_stage(registered_project: Path, tmp_path: Path) -> None:
    _close_frame(registered_project, tmp_path)
    inputs = _jump_inputs(registered_project, tmp_path)
    successor = inputs["successor_path"]
    # Working stage sheds its guard; a decoy stage carries it, so the union
    # still covers the current guard set — the per-stage check must refuse.
    text = successor.read_text(encoding="utf-8").split("[[stages.guards]]")[0]
    successor.write_text(text + _extra_stage(tmp_path, "minimize", with_guard=True), encoding="utf-8")
    inputs["approval_path"] = _auto_approval(tmp_path)
    with pytest.raises(jump.JumpError, match="drops or weakens a guard"):
        jump.adopt(registered_project, **inputs)


def test_auto_approval_refused_when_an_objective_is_added(registered_project: Path, tmp_path: Path) -> None:
    _close_frame(registered_project, tmp_path)
    inputs = _jump_inputs(registered_project, tmp_path)
    successor = inputs["successor_path"]
    successor.write_text(
        successor.read_text(encoding="utf-8") + _extra_stage(tmp_path, "maximize", with_guard=True),
        encoding="utf-8",
    )
    inputs["approval_path"] = _auto_approval(tmp_path)
    with pytest.raises(jump.JumpError, match="measurement is constitutional"):
        jump.adopt(registered_project, **inputs)


def test_auto_approval_refused_when_revert_changes(registered_project: Path, tmp_path: Path) -> None:
    _close_frame(registered_project, tmp_path)
    inputs = _jump_inputs(registered_project, tmp_path)
    successor = inputs["successor_path"]
    successor.write_text(
        successor.read_text(encoding="utf-8").replace(
            "[frame]", "[revert]\nclean_ignored = false\n\n[frame]"
        ),
        encoding="utf-8",
    )
    inputs["approval_path"] = _auto_approval(tmp_path)
    with pytest.raises(jump.JumpError, match=r"changes \[revert\]"):
        jump.adopt(registered_project, **inputs)


def test_human_approval_records_its_mode(registered_project: Path, tmp_path: Path) -> None:
    inputs = _jump_inputs(registered_project, tmp_path)
    result = jump.adopt(registered_project, **inputs)
    assert result["approval_mode"] == "human"
    events = journal.load_events(registered_project)
    body = next(e for e in events if e["kind"] == "adoption.v1")["body"]
    assert body["approval_mode"] == "human"
    assert "core_digest" not in body


def test_full_auto_grant_can_authorize_constitutional_jump_from_open_frame(
    registered_project: Path, tmp_path: Path
) -> None:
    autonomy.enable(
        registered_project,
        "user invoking full-auto",
        "delegate constitutional decisions to the agent",
    )
    inputs = _jump_inputs(registered_project, tmp_path)
    successor = inputs["successor_path"]
    successor.write_text(
        successor.read_text(encoding="utf-8")
        .replace(
            'goal = "drive the number in value.txt to 0"',
            'goal = "drive the number in value.txt below 5"',
        )
        .replace("iterations_total = 6", "iterations_total = 60"),
        encoding="utf-8",
    )
    inputs["approval_path"] = _full_auto_approval(tmp_path)

    result = jump.adopt(registered_project, **inputs)

    assert result["approval_mode"] == "full_auto"
    body = journal.load_events(registered_project)[-1]["body"]
    assert body["approval_mode"] == "full_auto"
    assert len(body["full_auto_config_digest"]) == 64
    assert len(body["full_auto_grant_digest"]) == 64


def test_full_auto_jump_refused_without_project_grant(
    registered_project: Path, tmp_path: Path
) -> None:
    inputs = _jump_inputs(registered_project, tmp_path)
    inputs["approval_path"] = _full_auto_approval(tmp_path)
    with pytest.raises(autonomy.AutonomyError, match="config file not found"):
        jump.adopt(registered_project, **inputs)


def test_full_auto_approval_requires_auditable_judgment(
    registered_project: Path, tmp_path: Path
) -> None:
    autonomy.enable(registered_project, "user", "delegate constitutional decisions")
    inputs = _jump_inputs(registered_project, tmp_path)
    inputs["approval_path"].write_text(
        json.dumps({"mode": "full_auto", "decision": "continue"}), encoding="utf-8"
    )
    with pytest.raises(jump.JumpError, match="evidence"):
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
