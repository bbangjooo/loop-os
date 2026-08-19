"""Shared harness: build a disposable application, drive full outer-loop
cycles through the real instruments and the real kernel, collect metrics.

Used by the gate tests (pytest) and the measurement runner (bench/run.py).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import aim
import journal
from seal import seal_contract, seal_diagnosis, seal_run

ROOT = Path(__file__).parents[1]
KERNEL = ROOT / "kernel" / "loop.py"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def run_kernel(project: Path, spec_rel: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(KERNEL), "--repo", str(project), "run", spec_rel],
        cwd=project,
        capture_output=True,
        text=True,
    )


def read_ledger(project: Path, loop_id: str) -> list[dict]:
    path = project / ".git" / "experiment-loop" / loop_id / "ledger.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_trials(project: Path) -> list[dict]:
    path = project / ".bench-cache" / "trials.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


CONTRACT_TEMPLATE = """\
schema = "ros2-contract-v1"

integrity = [{pins}]

[project]
id = "bench"

[frame]
generation = 1
class = "{klass}"
mechanism = "benchmark problem with a known construction; see bench/README.md"

[budget]
iterations_total = {total}

[agent]
command = {agent_command}
timeout_seconds = {agent_timeout}
{summary_prefix_line}

[[stages]]
id = "main"
iterations = {per_run}
prompt = \"\"\"{prompt}\"\"\"

[stages.objective]
command = ["{python}", "{objective}"]
direction = "{direction}"
margin = {margin}
{target_line}
timeout_seconds = 60
proxy_license = "bench construction: the objective is the goal by definition of the synthetic problem"

{guards}
"""

GUARD_TEMPLATE = """\
[[stages.guards]]
id = "{gid}"
command = {command}
kind = "exit_zero"
timeout_seconds = 60
"""


def make_project(
    tmp_path: Path,
    files: dict[str, str],
    pins: list[str],
    agent_command: list[str],
    objective: Path,
    total: int = 24,
    per_run: int = 8,
    direction: str = "minimize",
    margin: float = 1,
    target: float | None = 0,
    guards: list[tuple[str, list[str]]] = (),
    prompt: str = "scripted agent; the prompt is unused",
    klass: str = "bench_class",
    agent_timeout: int = 300,
    summary_prefix: str | None = None,
) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    _git(project.parent, "init", "-q", "-b", "work", str(project))
    _git(project, "config", "user.email", "bench@example.invalid")
    _git(project, "config", "user.name", "Loop OS Bench")
    for name, body in files.items():
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    (project / ".gitignore").write_text(".journal/\n.bench-cache/\n", encoding="utf-8")

    guard_blocks = "\n".join(
        GUARD_TEMPLATE.format(gid=gid, command=json.dumps(command)) for gid, command in guards
    )
    contract = CONTRACT_TEMPLATE.format(
        pins=", ".join(json.dumps(p) for p in pins),
        total=total,
        per_run=per_run,
        agent_command=json.dumps(agent_command),
        agent_timeout=agent_timeout,
        summary_prefix_line=(
            f'summary_prefix = "{summary_prefix}"' if summary_prefix else ""
        ),
        python=sys.executable,
        objective=objective,
        direction=direction,
        margin=margin,
        target_line=f"target = {target}" if target is not None else "",
        guards=guard_blocks,
        prompt=prompt,
        klass=klass,
    )
    (project / "contract.toml").write_text(contract, encoding="utf-8")

    journal.append_event(project, "bootstrap.v1", {"project_id": "bench", "lineage": []})
    seal_contract(project)
    _git(project, "add", "-A")
    _git(project, "commit", "-q", "-m", "bench seed")
    return project


def issue_and_commit(project: Path) -> dict:
    issued = aim.issue(project)
    _git(project, "add", "-A")
    _git(project, "commit", "-q", "-m", f"spec {issued['loop_id']}")
    return issued


def auto_diagnosis(project: Path, tmp_dir: Path, summary: dict, index: int) -> None:
    """Runner-authored diagnosis: the benchmark measures the OS, not prose.
    Shape-valid, honestly mechanical."""
    stopped = summary.get("stopped")
    verdict = "SUPPORTED" if stopped == "target_reached" else "REJECTED"
    body = {
        "verdict": verdict,
        "what_moved": (
            f"objective {summary['objective'].get('baseline')} -> "
            f"{summary['objective'].get('final')} in {summary.get('iterations_run')} iterations"
        ),
        "mechanism_interpretation": "scripted benchmark run; mechanism is the synthetic construction",
        "counterfactual": "entry probe fixed the baseline; rejected iterations were reverted",
        "next_question": "benchmark cycle bookkeeping only",
    }
    path = tmp_dir / f"diagnosis-{index}.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    seal_diagnosis(project, path)


def drive(project: Path, tmp_dir: Path, max_cycles: int = 8) -> dict:
    """Run full outer-loop cycles until the target is reached or the budget
    refuses. Returns raw material for metrics."""
    cycles = []
    started = time.monotonic()
    exhausted = False
    for index in range(max_cycles):
        try:
            issued = issue_and_commit(project)
        except aim.AimRefusal as refusal:
            assert refusal.code == "R5_BUDGET", f"unexpected refusal: {refusal.code}"
            exhausted = True
            break
        result = run_kernel(project, issued["spec_path"])
        assert result.returncode == 0, f"kernel failed:\n{result.stdout}\n{result.stderr}"
        summary_file = project / Path(issued["spec_path"]).parent / "summary.json"
        summary = json.loads(summary_file.read_text(encoding="utf-8"))
        trials = project / ".bench-cache" / "trials.jsonl"
        seal_run(
            project,
            summary_file,
            project / ".git" / "experiment-loop" / issued["loop_id"] / "ledger.jsonl",
            trials if trials.exists() else None,
        )
        auto_diagnosis(project, tmp_dir, summary, index)
        cycles.append({"issued": issued, "summary": summary})
        if summary.get("stopped") == "target_reached":
            break
    state = journal.replay(project)
    return {
        "cycles": cycles,
        "budget_exhausted": exhausted,
        "wall_seconds": round(time.monotonic() - started, 2),
        "state": state,
    }
