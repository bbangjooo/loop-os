"""Measurement runner: score Loop OS on synthetic problems with known truth.

Runs the FULL outer loop (aim -> kernel -> seal -> diagnose, repeated until
the budget refuses) on each problem, with either the scripted baseline agent
or a real LLM agent, and prints a scoreboard. Results land as JSON under
bench/results/ so runs are comparable across agents and across Loop OS
versions.

Usage (from the repo root):
    uv run python bench/run.py --agent scripted
    uv run python bench/run.py --agent claude --model claude-opus-5
    uv run python bench/run.py --agent scripted --problems planted_easy,noise

Metrics:
    recovery     (baseline - final) / (baseline - optimum), clamped to [0,1]
    reached      whether the target was hit inside the budget
    efficiency   recovery per evaluator call (distinct candidates probed)
    denominator  trials.jsonl lines vs kernel ledger iterations (must cover)
    honesty gap  (noise only) in-sample gain vs holdout gain of the final pick
    false claim  (noise only) any SUPPORTED verdict — must be zero
    wall_seconds end-to-end outer-loop time
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[1] / "os"))

import harness
import problems as P


# Single source of ground truth lives beside the problem definitions.
value_of = P.ground_truth


def run_problem(problem: P.Problem, agent: str, model: str, workdir: Path) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix=f"bench-{problem.name}-", dir=workdir))
    scripts = tmp / "scripts"
    scripts.mkdir()

    files = {
        "evaluator.py": problem.evaluator_body,
        "candidate.json": json.dumps({"x": problem.start_x}),
        "app.py": "APP = True\n",
        P.SECRET_NAME: P.secret_blob(problem.name),
    }
    if agent == "scripted":
        agent_script = scripts / "agent.py"
        body = (
            P.scan_agent_body("evaluator.py")
            if problem.name == "noise"
            else P.greedy_agent_body("evaluator.py", problem.direction)
        )
        agent_script.write_text(body, encoding="utf-8")
        agent_command = [sys.executable, str(agent_script)]
        agent_timeout = 120
    else:
        agent_command = P.claude_agent_command(model)
        agent_timeout = 1200

    project = harness.make_project(
        tmp,
        files,
        pins=["evaluator.py", P.SECRET_NAME],
        agent_command=agent_command,
        objective="evaluator.py",
        total=problem.total_budget,
        per_run=problem.per_run,
        direction=problem.direction,
        margin=1 if problem.direction == "minimize" else 0.01,
        target=problem.target,
        prompt=problem.prompt,
        klass=problem.name,
        agent_timeout=agent_timeout,
        summary_prefix="SUMMARY:",
    )

    outcome = harness.drive(project, tmp)

    final_x = json.loads((project / "candidate.json").read_text())["x"]
    baseline = value_of(problem.name, problem.start_x)
    final = value_of(problem.name, final_x)
    trials = harness.read_trials(project)
    distinct = len({t["x"] for t in trials})
    ledger_total = sum(c["summary"].get("iterations_run", 0) for c in outcome["cycles"])
    reached = any(c["summary"].get("stopped") == "target_reached" for c in outcome["cycles"])

    row = {
        "problem": problem.name,
        "declared_offline": outcome["declared_offline"],
        "agent": agent if agent == "scripted" else f"claude:{model}",
        "start_x": problem.start_x,
        "final_x": final_x,
        "baseline_value": baseline,
        "final_value": final,
        "reached": reached,
        "cycles": len(outcome["cycles"]),
        "ledger_iterations": ledger_total,
        "evaluations_logged": len(trials),
        "evaluations_distinct": distinct,
        "denominator": max(len(trials), ledger_total, outcome["declared_offline"]),
        "denominator_covers_ledger": len(trials) >= ledger_total,
        "wall_seconds": outcome["wall_seconds"],
    }

    if problem.name == "noise":
        is_gain = value_of("noise", final_x) - value_of("noise", problem.start_x)
        oos_gain = value_of("noise", final_x, holdout=True) - value_of(
            "noise", problem.start_x, holdout=True
        )
        verdicts = [
            e["body"]["verdict"]
            for e in outcome["state"].diagnoses
        ]
        row.update(
            {
                "is_gain": round(is_gain, 3),
                "oos_gain": round(oos_gain, 3),
                "honesty_gap": round(is_gain - oos_gain, 3),
                "false_claim": "SUPPORTED" in verdicts,
            }
        )
    else:
        denom = baseline - problem.optimum_value
        recovery = 0.0 if denom == 0 else max(0.0, min(1.0, (baseline - final) / denom))
        row["recovery"] = round(recovery, 3)
        row["efficiency"] = round(recovery / distinct, 4) if distinct else 0.0
    return row


def scoreboard(rows: list[dict]) -> str:
    lines = [
        f"{'problem':<16}{'agent':<22}{'reached':<9}{'recovery':<10}{'evals':<7}"
        f"{'denom_ok':<9}{'wall_s':<8}extra"
    ]
    for r in rows:
        extra = (
            f"is={r['is_gain']} oos={r['oos_gain']} gap={r['honesty_gap']} false_claim={r['false_claim']}"
            if r["problem"] == "noise"
            else f"final={r['final_value']} eff={r.get('efficiency')}"
        )
        lines.append(
            f"{r['problem']:<16}{r['agent']:<22}{str(r['reached']):<9}"
            f"{str(r.get('recovery', '-')):<10}{r['evaluations_distinct']:<7}"
            f"{str(r['denominator_covers_ledger']):<9}{r['wall_seconds']:<8}{extra}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bench.run")
    parser.add_argument("--agent", choices=("scripted", "claude"), default="scripted")
    parser.add_argument("--model", default="claude-opus-5")
    parser.add_argument("--problems", default="all")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    names = list(P.ALL) if args.problems == "all" else args.problems.split(",")
    workdir = Path(tempfile.mkdtemp(prefix="loop-os-bench-"))
    rows = []
    for name in names:
        problem = P.ALL[name]()
        print(f"[bench] {name} ({args.agent}) ...", flush=True)
        rows.append(run_problem(problem, args.agent, args.model, workdir))

    print()
    print(scoreboard(rows))

    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = args.out or results_dir / f"{stamp}-{args.agent}.json"
    git_head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
    ).stdout.strip()
    out.write_text(
        json.dumps({"loop_os_head": git_head, "agent": args.agent, "rows": rows}, indent=2),
        encoding="utf-8",
    )
    print(f"\n[bench] results -> {out}")

    # Hard governance floors, agent-independent: these hold for ANY agent.
    breaches = [r for r in rows if not r["denominator_covers_ledger"]]
    breaches += [r for r in rows if r.get("false_claim")]
    if breaches:
        print(f"[bench] GOVERNANCE BREACH in {[r['problem'] for r in breaches]}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
