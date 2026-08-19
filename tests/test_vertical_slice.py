"""End-to-end: one full outer-loop cycle on a toy application with the real
kernel — bootstrap → register → aim → kernel run → seal run → seal diagnosis
→ verify → aim again. This is the §10-2 acceptance test: if this passes, the
vertical slice closes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import aim
import journal
from seal import seal_diagnosis, seal_run

from tests.conftest import _git

KERNEL = Path(__file__).parents[1] / "kernel" / "loop.py"


def _run_kernel(project: Path, spec_rel: str) -> None:
    result = subprocess.run(
        [sys.executable, str(KERNEL), "--repo", str(project), "run", spec_rel],
        cwd=project,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"kernel run failed:\n{result.stdout}\n{result.stderr}"


def test_full_cycle_closes(registered_project: Path, tmp_path: Path) -> None:
    project = registered_project

    # aim → spec; the journal is gitignored so the worktree stays clean for the kernel
    issued = aim.issue(project)
    _git(project, "add", "-A")
    _git(project, "commit", "-q", "-m", f"spec {issued['loop_id']}")
    status = _git(project, "status", "--porcelain")
    assert status == "", f"journal or spec leaked into the worktree: {status!r}"

    # kernel run: objective 10 -> target reached or budget exhausted (3 iterations)
    _run_kernel(project, issued["spec_path"])
    summary_path = project / Path(issued["spec_path"]).parent / "summary.json"
    assert summary_path.exists(), "kernel wrote no summary next to the spec"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["spec_digest"] == issued["spec_digest"]
    assert summary["accepted"] >= 1, "the scripted agent should have improved the objective"
    ledger_path = project / ".git" / "experiment-loop" / issued["loop_id"] / "ledger.jsonl"
    assert ledger_path.exists()

    # seal the run; the summary itself is a kernel artifact, untracked is fine
    sealed = seal_run(project, summary_path, ledger_path)
    assert sealed["status"] == "RUN_SEALED"

    # aim must refuse until the diagnosis lands (structural enforcement)
    try:
        aim.issue(project)
        raise AssertionError("aim must refuse while a diagnosis is pending")
    except aim.AimRefusal as refusal:
        assert refusal.code == "R4_PENDING_DIAGNOSIS"

    diagnosis = tmp_path / "diagnosis.json"
    diagnosis.write_text(
        json.dumps(
            {
                "verdict": "SUPPORTED",
                "what_moved": f"objective {summary['objective']['baseline']} -> {summary['objective']['final']}",
                "mechanism_interpretation": "direct decrement, as the toy contract declares",
                "counterfactual": "entry probe held at baseline without the change",
                "next_question": "none — toy frame",
            }
        ),
        encoding="utf-8",
    )
    assert seal_diagnosis(project, diagnosis)["status"] == "DIAGNOSIS_SEALED"

    # chain verifies end to end, and the next aim opens (budget 6, drawn 3)
    events = journal.load_events(project)
    kinds = [e["kind"] for e in events]
    assert kinds == [
        "bootstrap.v1",
        "contract_registered.v1",
        "spec_issued.v1",
        "run_sealed.v1",
        "diagnosis_sealed.v1",
    ]
    second = aim.issue(project)
    assert second["status"] == "SPEC_ISSUED"
    assert second["budget_remaining"] == 0


def test_instruments_work_over_argv(registered_project: Path) -> None:
    """The agent drives instruments as subprocesses; the JSON surface must hold."""
    project = registered_project
    result = subprocess.run(
        [sys.executable, "os/journal.py", "status", "--project", str(project)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parents[1],
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "OK"
    assert payload["next_required"].startswith("issue the next spec")
