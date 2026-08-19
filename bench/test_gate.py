"""Gate problems 2-4 — capability floor, denominator honesty, crash resume.

These run the measurement engine (bench/run.py) with the scripted baseline
agent and assert the governance floors that must hold for ANY agent, plus the
baseline's known behavior so a capability regression in the harness itself is
caught.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import aim
import journal
from seal import SealError, seal_run

sys.path.insert(0, str(Path(__file__).parent))
import problems as P
from run import run_problem, value_of
from harness import _git, issue_and_commit, make_project, run_kernel


# ---------------------------------------------------------- capability -----

def test_planted_easy_is_fully_recovered(tmp_path: Path) -> None:
    row = run_problem(P.planted_easy(), "scripted", "", tmp_path)
    assert row["reached"] is True
    assert row["recovery"] == 1.0
    assert row["final_x"] == 137
    assert row["denominator_covers_ledger"] is True


def test_deceptive_traps_the_baseline_and_the_record_shows_it(tmp_path: Path) -> None:
    """The greedy baseline MUST get stuck at the false floor — that is what
    makes it a baseline. The measured record proves the harness detects the
    trap instead of papering over it. A smarter agent's uplift is measured
    against exactly this row."""
    row = run_problem(P.deceptive(), "scripted", "", tmp_path)
    assert row["reached"] is False
    assert row["final_value"] == 10  # the comfortable floor, not the optimum
    assert 0 < row["recovery"] < 1
    assert row["denominator_covers_ledger"] is True


def test_needle_starves_the_baseline_honestly(tmp_path: Path) -> None:
    row = run_problem(P.planted_needle(), "scripted", "", tmp_path)
    assert row["reached"] is False
    assert row["recovery"] == 0.0
    # Every probe of the flat plain still lands in the denominator.
    assert row["evaluations_logged"] > row["ledger_iterations"]


# ------------------------------------------------------------- honesty -----

def test_noise_shows_selection_effect_but_no_false_claim(tmp_path: Path) -> None:
    """Pure noise + greedy selection = apparent in-sample improvement. The
    system's job is not to prevent that; it is to record the honest
    denominator, keep the holdout out of reach, and never let the record say
    SUPPORTED."""
    row = run_problem(P.noise(), "scripted", "", tmp_path)
    assert row["is_gain"] > 0  # the selection effect is real and visible
    assert row["false_claim"] is False
    assert row["denominator_covers_ledger"] is True
    # Hidden probes (the agent evaluates 9 candidates per iteration) dominate
    # the ledger count — the denominator catches what the ledger cannot see.
    assert row["evaluations_logged"] > row["ledger_iterations"] * 2
    # The holdout does not reproduce the in-sample gain: the measured OOS
    # gain must fall short of the selection-inflated IS gain. The gap itself is
    # recorded, not asserted away. (Deterministic given fixed seeds.)
    assert row["oos_gain"] < row["is_gain"]


# -------------------------------------------------------- crash resume -----

OBJECTIVE = "from pathlib import Path\nprint(Path('value.txt').read_text().strip())\n"
DECREMENT = (
    "from pathlib import Path\n"
    "p = Path('value.txt')\n"
    "p.write_text(str(int(p.read_text().strip()) - 1) + '\\n')\n"
)


def _project(tmp_path: Path, scripts: Path) -> Path:
    objective = scripts / "objective.py"
    objective.write_text(OBJECTIVE, encoding="utf-8")
    agent = scripts / "agent.py"
    agent.write_text(DECREMENT, encoding="utf-8")
    return make_project(
        tmp_path,
        {"value.txt": "3\n", "app.py": "X = 1\n"},
        [],
        agent_command=[sys.executable, str(agent)],
        objective=objective,
        total=6,
        per_run=3,
    )


def test_resume_from_every_seam_with_no_double_draw(tmp_path: Path, scripts: Path) -> None:
    """Kill the session at each seam; a fresh session resumes from replay
    alone. The budget must be drawn exactly once per issued spec."""
    project = _project(tmp_path, scripts)

    # Seam 1: died right after aim (spec issued, never run).
    issued = issue_and_commit(project)
    state = journal.replay(project)  # fresh session: replay is the resume
    assert list(state.pending_runs) == [issued["spec_digest"]]
    with pytest.raises(aim.AimRefusal) as refusal:
        aim.issue(project)  # a confused second session cannot double-draw
    assert refusal.value.code == "R3_PENDING_RUN"

    # Seam 2: run finished, session died before sealing.
    result = run_kernel(project, issued["spec_path"])
    assert result.returncode == 0
    summary = project / Path(issued["spec_path"]).parent / "summary.json"
    ledger = project / ".git" / "experiment-loop" / issued["loop_id"] / "ledger.jsonl"
    state = journal.replay(project)
    assert list(state.pending_runs) == [issued["spec_digest"]]  # still pending
    sealed = seal_run(project, summary, ledger)

    # Sealing twice (a replayed session re-running its notes) is refused.
    with pytest.raises(SealError, match="already sealed"):
        seal_run(project, summary, ledger)

    # Seam 3: sealed, died before the diagnosis.
    state = journal.replay(project)
    assert list(state.pending_diagnoses) == [sealed["event_id"]]
    with pytest.raises(aim.AimRefusal) as refusal:
        aim.issue(project)
    assert refusal.value.code == "R4_PENDING_DIAGNOSIS"

    # The draw happened exactly once across all three "sessions".
    assert journal.replay(project).drawn_by_generation == {1: 3}
    assert _git(project, "status", "--porcelain", "--untracked-files=no") == ""
