from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import aim
import journal
import jump
import steer
from _canon import digest_file
from seal import SealError, seal_contract, seal_diagnosis
from tests.conftest import _git
from tests.test_jump import _auto_approval, _jump_inputs
from tests.test_seal import _diagnosis, _seal_one_run
from tests.test_steer import _cycle
from tests.test_vertical_slice import KERNEL, _run_kernel


def _bind(project: Path, name: str = "program.md", text: str = "# Goal\nDeliver the application result.\n") -> dict:
    path = project / name
    path.write_text(text)
    binding = {"path": name, "digest": digest_file(path)}
    contract = project / "contract.toml"
    content = contract.read_text().split("\n[program]\n")[0]
    contract.write_text(content + f'\n[program]\npath = "{name}"\ndigest = "{binding["digest"]}"\n')
    seal_contract(project)
    return binding


def _progress(run_id: str, kind: str = "preparation") -> dict:
    return {
        "kind": kind,
        "criterion": "program.md / Goal: deliver the application result",
        "delta": "Input checker ready; no delivered result yet",
        "evidence_refs": [run_id],
        "remaining": ["Retest the inherited candidate", "Establish the comparison baseline"],
        "next_action": "Retest the inherited candidate using the existing input checker",
    }


def test_registration_and_issuance_bind_program_and_guard(registered_project: Path) -> None:
    binding = _bind(registered_project)
    assert journal.replay(registered_project).program == binding
    issued = aim.issue(registered_project)
    assert journal.load_events(registered_project)[-1]["body"]["program"] == binding
    spec = yaml.safe_load((registered_project / issued["spec_path"]).read_text())
    assert "program.md" in spec["integrity"]
    for stage in spec["stages"]:
        guard = next(g for g in stage["guards"] if g["id"] == "loop-os-program-digest")
        assert subprocess.run(guard["command"], cwd=registered_project).returncode == 0


@pytest.mark.parametrize("change", ["edit", "delete"])
def test_program_drift_refused_before_draw_and_cannot_reseal_same_contract(
    registered_project: Path, change: str
) -> None:
    _bind(registered_project)
    path = registered_project / "program.md"
    if change == "edit":
        path.write_text("Preparation alone now counts as success.\n")
    else:
        path.unlink()
    before = journal.journal_path(registered_project).read_bytes()
    with pytest.raises(aim.AimRefusal, match="program") as error:
        aim.issue(registered_project)
    assert error.value.code == "R2_CONTRACT"
    with pytest.raises(SealError, match="program"):
        seal_contract(registered_project)
    assert journal.journal_path(registered_project).read_bytes() == before
    assert not journal.replay(registered_project).drawn_by_generation
    assert steer.status(registered_project)["program_progress"]["program_integrity"] == "UNAVAILABLE_OR_CHANGED"


@pytest.mark.parametrize("declaration", [
    'path = "../outside.md"\ndigest = "' + "a" * 64 + '"',
    'path = "/outside.md"\ndigest = "' + "a" * 64 + '"',
    'path = "program.md"\ndigest = "bad"',
    'path = "program.md"\ndigest = "' + "a" * 64 + '"\nextra = true',
])
def test_program_schema_rejects_invalid_binding(registered_project: Path, declaration: str) -> None:
    path = registered_project / "contract.toml"
    path.write_text(path.read_text() + "\n[program]\n" + declaration)
    with pytest.raises(aim.ContractError, match="program"):
        aim.load_contract(path)


def test_program_cannot_escape_through_symlink(registered_project: Path, tmp_path: Path) -> None:
    _bind(registered_project)
    outside = tmp_path / "outside.md"
    outside.write_bytes((registered_project / "program.md").read_bytes())
    (registered_project / "program.md").unlink()
    (registered_project / "program.md").symlink_to(outside)
    with pytest.raises(aim.AimRefusal, match="outside"):
        aim.issue(registered_project)


def test_kernel_rejects_program_changed_and_committed_after_issuance(registered_project: Path) -> None:
    _bind(registered_project)
    issued = aim.issue(registered_project)
    (registered_project / "program.md").write_text("A different goal, committed before kernel entry.\n")
    _git(registered_project, "add", "-A")
    _git(registered_project, "commit", "-qm", "changed program after aim")
    result = subprocess.run(
        [sys.executable, str(KERNEL), "--repo", str(registered_project), "run", issued["spec_path"]],
        cwd=registered_project, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "loop-os-program-digest" in result.stdout + result.stderr
    summary = json.loads((registered_project / Path(issued["spec_path"]).parent / "summary.json").read_text())
    assert summary["accepted"] == 0
    assert summary["decisions"]["rejected"] == summary["iterations_run"] == 3
    assert (registered_project / "value.txt").read_text() == "10\n"


@pytest.mark.parametrize("kind", ["outcome", "learning", "preparation", "no_change"])
def test_declared_progress_is_sealed_and_never_implies_completion(
    registered_project: Path, tmp_path: Path, kind: str
) -> None:
    binding = _bind(registered_project)
    run_id = _seal_one_run(registered_project, tmp_path)
    progress = _progress(run_id, kind)
    seal_diagnosis(registered_project, _diagnosis(tmp_path / "d.json", verdict="SUPPORTED", program_progress=progress))
    body = journal.replay(registered_project).diagnoses[-1]["body"]
    assert body["program"] == binding
    assert body["program_progress"] == progress
    report = steer.frame_health(registered_project)
    assert report["program_progress"]["declared_by_kind"] == {kind: 1}
    assert report["program_progress"]["latest"]["remaining"] == progress["remaining"]
    assert report["program_progress"]["completion"] == "NOT_EVALUATED"
    assert report["program_progress"]["runs_since_last_declared_outcome"] == (0 if kind == "outcome" else 1)
    assert len(report["program_interpretation_requests"]) == 3


@pytest.mark.parametrize("bad", [None, {}, "progress", {"kind": "complete"}, {"evidence_refs": ["ev-invented"]},
                                    {"remaining": ["REPLACE_ME"]}])
def test_invalid_progress_keeps_diagnosis_pending(registered_project: Path, tmp_path: Path, bad) -> None:
    _bind(registered_project)
    run_id = _seal_one_run(registered_project, tmp_path)
    value = {**_progress(run_id), **bad} if isinstance(bad, dict) and bad else bad
    before = journal.journal_path(registered_project).read_bytes()
    with pytest.raises(SealError, match="program_progress"):
        seal_diagnosis(registered_project, _diagnosis(tmp_path / "d.json", program_progress=value))
    assert journal.journal_path(registered_project).read_bytes() == before
    assert run_id in journal.replay(registered_project).pending_diagnoses
    assert steer.status(registered_project)["program_progress"]["unreported_runs"] == 1


def test_legacy_run_can_finish_after_opt_in(registered_project: Path, tmp_path: Path) -> None:
    run_id = _seal_one_run(registered_project, tmp_path)
    _bind(registered_project)
    seal_diagnosis(registered_project, _diagnosis(tmp_path / "legacy.json"))
    assert run_id not in journal.replay(registered_project).pending_diagnoses
    report = steer.status(registered_project)["program_progress"]
    assert report["reported_runs"] == report["unreported_runs"] == 0


def test_diagnosis_uses_issued_program_not_latest_contract(registered_project: Path, tmp_path: Path) -> None:
    first = _bind(registered_project)
    run_id = _seal_one_run(registered_project, tmp_path)
    path = registered_project / "program-v2.md"
    path.write_text("# A different program\n")
    second = {"path": path.name, "digest": digest_file(path)}
    inputs = _jump_inputs(registered_project, tmp_path)
    successor = inputs["successor_path"]
    successor.write_text(successor.read_text() + f'\n[program]\npath = "{second["path"]}"\ndigest = "{second["digest"]}"\n')
    jump.adopt(registered_project, **inputs)
    seal_contract(registered_project, successor)
    seal_diagnosis(registered_project, _diagnosis(tmp_path / "d.json", program_progress=_progress(run_id)))
    state = journal.replay(registered_project)
    assert state.program == second
    assert state.diagnoses[-1]["body"]["program"] == first
    assert steer.status(registered_project)["program_progress"]["latest"] is None


def test_legacy_supported_is_not_relabelled_as_outcome(registered_project: Path, tmp_path: Path) -> None:
    _seal_one_run(registered_project, tmp_path)
    seal_diagnosis(registered_project, _diagnosis(tmp_path / "legacy.json", verdict="SUPPORTED", program_progress="legacy extension"))
    assert steer.status(registered_project)["program_progress"]["status"] == "UNBOUND"
    assert steer.frame_health(registered_project)["program_interpretation_requests"] == []


@pytest.mark.parametrize("change", ["drop", "replace"])
def test_auto_jump_cannot_replace_program(registered_project: Path, tmp_path: Path, change: str) -> None:
    _bind(registered_project)
    for i in range(3):
        _cycle(registered_project, tmp_path, i + 1, "REJECTED")
    inputs = _jump_inputs(registered_project, tmp_path)
    if change == "replace":
        new = registered_project / "different-program.md"
        new.write_text("A cheaper goal\n")
        p = inputs["successor_path"]
        p.write_text(p.read_text() + f'\n[program]\npath = "{new.name}"\ndigest = "{digest_file(new)}"\n')
    inputs["approval_path"] = _auto_approval(tmp_path)
    with pytest.raises(jump.JumpError, match="program"):
        jump.adopt(registered_project, **inputs)


def test_adoption_refuses_unavailable_program_before_append(registered_project: Path, tmp_path: Path) -> None:
    inputs = _jump_inputs(registered_project, tmp_path)
    p = inputs["successor_path"]
    p.write_text(p.read_text() + '\n[program]\npath = "missing.md"\ndigest = "' + "a" * 64 + '"\n')
    before = journal.journal_path(registered_project).read_bytes()
    with pytest.raises(jump.JumpError, match="program"):
        jump.adopt(registered_project, **inputs)
    assert journal.journal_path(registered_project).read_bytes() == before


@pytest.mark.parametrize("change", ["drop", "replace"])
def test_registration_cannot_bypass_program_change_adoption(registered_project: Path, change: str) -> None:
    binding = _bind(registered_project)
    contract = registered_project / "contract.toml"
    content = contract.read_text().split("\n[program]\n")[0]
    if change == "replace":
        path = registered_project / "program-v2.md"
        path.write_text("A different goal\n")
        content += f'\n[program]\npath = "{path.name}"\ndigest = "{digest_file(path)}"\n'
    contract.write_text(content)
    before = journal.journal_path(registered_project).read_bytes()
    with pytest.raises(SealError, match="adopted successor"):
        seal_contract(registered_project)
    assert journal.journal_path(registered_project).read_bytes() == before
    assert journal.replay(registered_project).program == binding


def test_program_progress_survives_frame_change_and_diagnosis_file_edit(registered_project: Path, tmp_path: Path) -> None:
    binding = _bind(registered_project)
    run_id = _seal_one_run(registered_project, tmp_path)
    progress = _progress(run_id, "learning")
    path = _diagnosis(tmp_path / "d.json", program_progress=progress)
    seal_diagnosis(registered_project, path)
    path.write_text("The mutable file no longer contains the sealed declaration.\n")
    for i in range(3):
        _cycle(registered_project, tmp_path, i + 1, "REJECTED")
    inputs = _jump_inputs(registered_project, tmp_path)
    inputs["approval_path"] = _auto_approval(tmp_path)
    successor = inputs["successor_path"]
    successor.write_text(successor.read_text() + f'\n[program]\npath = "{binding["path"]}"\ndigest = "{binding["digest"]}"\n')
    assert jump.adopt(registered_project, **inputs)["approval_mode"] == "auto"
    seal_contract(registered_project, successor)
    report = steer.status(registered_project)["program_progress"]
    assert journal.replay(registered_project).generation == 2
    assert report["latest"]["delta"] == progress["delta"]
    assert report["declared_by_kind"] == {"learning": 1}
    assert report["reported_runs"] == 1  # migrated runs remain unbound
    assert aim.issue(registered_project, successor)["status"] == "SPEC_ISSUED"


def test_program_bound_real_cycle(registered_project: Path, tmp_path: Path) -> None:
    from seal import seal_run

    _bind(registered_project)
    issued = aim.issue(registered_project)
    _git(registered_project, "add", "-A")
    _git(registered_project, "commit", "-qm", "bound program and spec")
    _run_kernel(registered_project, issued["spec_path"])
    summary = registered_project / Path(issued["spec_path"]).parent / "summary.json"
    ledger = registered_project / ".git/experiment-loop" / issued["loop_id"] / "ledger.jsonl"
    sealed = seal_run(registered_project, summary, ledger)
    seal_diagnosis(registered_project, _diagnosis(tmp_path / "d.json", program_progress=_progress(sealed["event_id"], "outcome")))
    assert aim.issue(registered_project)["budget_remaining"] == 0
