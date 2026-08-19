from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

import aim
import journal
from _canon import digest_file
from seal import seal_contract

from conftest import write_contract

KERNEL = Path(__file__).parents[1] / "kernel" / "loop.py"


def _load_kernel():
    spec = importlib.util.spec_from_file_location("experiment_loop", KERNEL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["experiment_loop"] = module
    spec.loader.exec_module(module)
    return module


def test_refuses_without_journal(project: Path, objective: Path, agent: Path) -> None:
    write_contract(project, objective, agent)
    with pytest.raises(aim.AimRefusal) as error:
        aim.issue(project)
    assert error.value.code == "R1_JOURNAL"


def test_refuses_unregistered_contract(project: Path, objective: Path, agent: Path) -> None:
    write_contract(project, objective, agent)
    journal.append_event(project, "bootstrap.v1", {"project_id": "toy", "lineage": []})
    with pytest.raises(aim.AimRefusal) as error:
        aim.issue(project)
    assert error.value.code == "R2_CONTRACT"


def test_refuses_drifted_contract(registered_project: Path) -> None:
    contract = registered_project / "contract.toml"
    contract.write_text(
        contract.read_text(encoding="utf-8").replace("iterations_total = 6", "iterations_total = 600"),
        encoding="utf-8",
    )
    with pytest.raises(aim.AimRefusal, match="drifted") as error:
        aim.issue(registered_project)
    assert error.value.code == "R2_CONTRACT"


def test_refuses_while_a_run_is_pending(registered_project: Path) -> None:
    aim.issue(registered_project)
    with pytest.raises(aim.AimRefusal) as error:
        aim.issue(registered_project)
    assert error.value.code == "R3_PENDING_RUN"


def test_refuses_while_a_diagnosis_is_pending(registered_project: Path) -> None:
    issued = aim.issue(registered_project)
    journal.append_event(
        registered_project,
        "run_sealed.v1",
        {"spec_digest": issued["spec_digest"], "origin": "issued"},
    )
    with pytest.raises(aim.AimRefusal) as error:
        aim.issue(registered_project)
    assert error.value.code == "R4_PENDING_DIAGNOSIS"


def _close_cycle(project: Path, issued: dict) -> None:
    run = journal.append_event(
        project, "run_sealed.v1", {"spec_digest": issued["spec_digest"], "origin": "issued"}
    )
    journal.append_event(
        project,
        "diagnosis_sealed.v1",
        {"run_seal_id": run["event_id"], "spec_digest": issued["spec_digest"]},
    )


def test_budget_is_reserved_not_refunded(registered_project: Path) -> None:
    # total=6, per_run=3: two issues fit, the third must refuse.
    first = aim.issue(registered_project)
    _close_cycle(registered_project, first)
    second = aim.issue(registered_project)
    assert second["budget_remaining"] == 0
    _close_cycle(registered_project, second)
    with pytest.raises(aim.AimRefusal) as error:
        aim.issue(registered_project)
    assert error.value.code == "R5_BUDGET"


def test_abandoned_run_burns_budget(registered_project: Path) -> None:
    first = aim.issue(registered_project)
    journal.append_event(
        registered_project,
        "run_abandoned.v1",
        {"spec_digest": first["spec_digest"], "reason": "crash"},
    )
    second = aim.issue(registered_project)  # pending cleared, budget still drawn
    assert second["budget_remaining"] == 0


def test_issued_spec_is_valid_for_the_kernel(registered_project: Path) -> None:
    """The strongest aim test: the kernel itself must accept the emitted spec."""
    issued = aim.issue(registered_project)
    kernel = _load_kernel()
    spec = kernel.load_spec(registered_project / issued["spec_path"])
    assert spec.loop_id == issued["loop_id"]
    assert [stage.stage_id for stage in spec.stages] == ["main"]
    # The contract itself must be pinned so the frame cannot drift mid-run.
    assert "contract.toml" in spec.integrity_paths
    # proxy_license must not leak into the kernel spec (closed schema).
    text = (registered_project / issued["spec_path"]).read_text(encoding="utf-8")
    assert "proxy_license" not in text


def test_spec_digest_in_event_matches_the_file(registered_project: Path) -> None:
    issued = aim.issue(registered_project)
    assert digest_file(registered_project / issued["spec_path"]) == issued["spec_digest"]


def test_proxy_license_is_mandatory(project: Path, objective: Path, agent: Path) -> None:
    path = write_contract(project, objective, agent)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    path.write_text(
        "".join(line for line in lines if not line.startswith("proxy_license")),
        encoding="utf-8",
    )
    with pytest.raises(aim.ContractError, match="proxy_license"):
        aim.load_contract(path)


def test_unknown_contract_key_is_refused(project: Path, objective: Path, agent: Path) -> None:
    path = write_contract(project, objective, agent)
    path.write_text(path.read_text(encoding="utf-8") + "\n[extra]\nx = 1\n", encoding="utf-8")
    with pytest.raises(aim.ContractError, match="unknown keys"):
        aim.load_contract(path)


def test_tolerance_on_non_numeric_guard_is_refused(project: Path, objective: Path, agent: Path) -> None:
    path = write_contract(project, objective, agent)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            'kind = "exit_zero"', 'kind = "exit_zero"\ntolerance = 0.1'
        ),
        encoding="utf-8",
    )
    with pytest.raises(aim.ContractError, match="numeric"):
        aim.load_contract(path)


def test_registration_seal_then_aim(project: Path, objective: Path, agent: Path) -> None:
    write_contract(project, objective, agent)
    journal.append_event(project, "bootstrap.v1", {"project_id": "toy", "lineage": []})
    result = seal_contract(project)
    assert result["status"] == "CONTRACT_REGISTERED"
    again = seal_contract(project)
    assert again["status"] == "ALREADY_REGISTERED"
    issued = aim.issue(project)
    assert issued["status"] == "SPEC_ISSUED"
    assert issued["loop_id"] == "toy-descent-g1-001"
