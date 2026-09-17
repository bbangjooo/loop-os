"""Prepare a reproducible cafe search ablation, run two fresh sessions, grade frozen code."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import math
import os
import random
import signal
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "app"))
from cafe import score

TASK = """Improve policy.py to reduce average time from each customer's arrival to service.
This is a deterministic toy cafe with one barista and one automatic machine.
Each of 12 orders needs prep -> brew -> serve. Prep and serve occupy the barista;
brew occupies only the machine. The machine can brew up to two orders together
if their family and brew duration match. Durations come from the order, never
from the proposed plan. Serving must start within 12 seconds after brewing.
Every order needs each operation exactly once; respect arrivals and resource
exclusivity. A plan is a list of {kind, orders: [integer ids], start: integer}.
schedule(orders) must be a general pure function using only the standard library;
it must not inspect files, seeds, process state, or evaluator internals at runtime.
The input includes the complete day's orders, so advance scheduling is allowed.
Keep the policy efficient: grading a batch of 64 days has a 15-second limit.

Only edit policy.py and research notes. Read cafe.py for the exact constraints.
Run `python3 objective.py` for ALL performance measurements; do not replicate
the scorer or tune against unlogged local simulations. Invalid attempts also
cost a call. Do not run concurrent evaluations or edit config/scorer/trial logs.
The fixed training days are in config.json. Final code will be frozen and graded
on additional days not supplied to you. Stay inside this workspace, use no web,
other sessions, installed skills, examples or outside solutions. Do not spawn
agents. Preserve the best valid policy you observed as policy.py when finishing.
Record your hypothesis, falsifier, trial interpretation and final rationale in
research.json. Final response: what changed, final measured score and uncertainty.

This is an isolated test of search instructions, not a full Loop OS cycle.
The evaluator and its budget are already provided. Do not bootstrap a journal,
create contracts, call the kernel, install dependencies, or change the task.
"""

CONTROL = """Use the original mechanism-first approach: inspect the starting solution,
form a falsifiable mechanism for improving it, implement and measure a candidate,
interpret the result, and use what you learned for the next candidate. Keep
failures visible and respect the fixed objective, validity constraints and budget.
"""


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def bounded(command, *, cwd=None, timeout=15, stdout_path=None):
    """Stop the owned process group before freezing outputs after a timeout."""
    with ExitStack() as stack:
        output = stack.enter_context(stdout_path.open("w")) if stdout_path else subprocess.PIPE
        with subprocess.Popen(command, cwd=cwd, stdout=output, stderr=subprocess.PIPE,
                              text=True, start_new_session=True) as process:
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                process.communicate()
                raise
            if stdout_path:
                stdout = stdout_path.read_text()
            return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def prepare(out: Path, seed: int, budget: int) -> dict:
    if out.exists():
        raise ValueError("output already exists; use a fresh directory")
    if budget < 1 or seed < 0:
        raise ValueError("budget must be positive and seed nonnegative")
    out.mkdir(parents=True)
    reference = (ROOT / "references/frame-exploration.md").read_text()
    extra = reference.split("## Generate before comparing\n", 1)[1].split("## Record and hand off", 1)[0]
    train = [seed * 1000 + i for i in range(8)]
    # Coordinator-side holdout is intentionally not copied into either workspace.
    holdout = [seed * 1000 + i for i in range(100, 164)]
    manifest = {"schema": "cafe-search-ablation-v1", "seed": seed,
                "eval_budget": budget, "train_seeds": train, "holdout_seeds": holdout,
                "reference_sha256": hashlib.sha256(reference.encode()).hexdigest(),
                "source_sha256": {name: hashlib.sha256((HERE / "app" / name).read_bytes()).hexdigest()
                                  for name in ("cafe.py", "objective.py", "policy.py")},
                "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "study": "search-instruction ablation, not full outer-loop comparison"}
    for arm in ("control", "exploration"):
        app = out / arm
        shutil.copytree(HERE / "app", app, ignore=shutil.ignore_patterns("__pycache__"))
        write_json(app / "config.json", {"train_seeds": train, "eval_budget": budget})
        (app / ".gitignore").write_text(".evaluations/\n__pycache__/\n")
        guidance = CONTROL
        if arm == "exploration":
            guidance += "\nApply this additional generation/comparison procedure. Store its finalized candidates and comparison in exploration.json. References to contract/evaluator workflow here mean the provided objective.py and fixed budget.\n\n" + extra
        (app / "TASK.md").write_text(TASK + "\n" + guidance)
        for args in (("init", "-q", "-b", "study"),
                     ("config", "user.email", "cafe@example.invalid"),
                     ("config", "user.name", "Cafe Example"),
                     ("add", "-A"), ("commit", "-q", "-m", "Initial cafe task")):
            subprocess.run(["git", *args], cwd=app, check=True, capture_output=True)
    write_json(out / "manifest.json", manifest)
    return manifest


def grade_frozen(policy: Path, seeds: list[int]) -> dict:
    # A subprocess bounds pathological candidate execution. Only the frozen source
    # is loaded; final grading uses this checkout's scorer, never an edited copy.
    command = [sys.executable, str(Path(__file__).resolve()), "_grade",
               "--policy", str(policy), "--seeds", json.dumps(seeds)]
    try:
        result = bounded(command, timeout=15)
        if result.returncode:
            return {"valid": False, "error": result.stderr[-1000:]}
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {"valid": False, "error": "policy exceeded 15 seconds"}
    except json.JSONDecodeError:
        return {"valid": False, "error": "policy polluted the grading output"}


def compare(out: Path) -> dict:
    manifest = json.loads((out / "manifest.json").read_text())
    for name, digest in manifest["source_sha256"].items():
        if hashlib.sha256((HERE / "app" / name).read_bytes()).hexdigest() != digest:
            raise ValueError("example sources changed since preparation; grade with the original checkout")
    frozen = out / "frozen"
    if frozen.exists():
        raise ValueError("comparison already frozen; use another pair for a new run")
    frozen.mkdir()
    # Freeze BOTH arms before revealing either holdout result.
    for arm in ("control", "exploration"):
        shutil.copy2(out / arm / "policy.py", frozen / f"{arm}.py")
    baseline = grade_frozen(HERE / "app/policy.py", manifest["holdout_seeds"])
    rows = {}
    for arm in ("control", "exploration"):
        app = out / arm
        source = frozen / f"{arm}.py"
        row = {"policy_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
               "train": grade_frozen(source, manifest["train_seeds"]),
               "holdout": grade_frozen(source, manifest["holdout_seeds"])}
        changed = []
        for name in ("cafe.py", "objective.py"):
            if (app / name).read_bytes() != (HERE / "app" / name).read_bytes():
                changed.append(name)
        config = json.loads((app / "config.json").read_text())
        if config != {"train_seeds": manifest["train_seeds"], "eval_budget": manifest["eval_budget"]}:
            changed.append("config.json")
        trials = app / ".evaluations/trials.jsonl"
        row["evaluations_logged"] = len(trials.read_text().splitlines()) if trials.exists() else 0
        row["integrity_changes"] = changed
        row["eligible"] = not changed and row["evaluations_logged"] <= manifest["eval_budget"] and row["train"]["valid"] and row["holdout"]["valid"]
        session = out / f"{arm}-session.json"
        if session.exists():
            data = json.loads(session.read_text())
            row["session"] = {k: data.get(k) for k in ("is_error", "subtype", "modelUsage", "usage", "total_cost_usd", "duration_ms", "wall_seconds")}
            limits = manifest.get("session_limits", {})
            def within(value, ceiling):
                return type(value) in (float, int) and math.isfinite(value) and 0 <= value <= ceiling
            row["session_within_limits"] = (
                within(data.get("total_cost_usd"), limits.get("usd_per_arm", -1))
                and within(data.get("wall_seconds"), limits.get("timeout_seconds", -1))
            )
            row["eligible"] = row["eligible"] and not data.get("is_error", True) and row["session_within_limits"]
        rows[arm] = row
    comparable = all(r["eligible"] for r in rows.values())
    models = [set(r.get("session", {}).get("modelUsage") or {}) for r in rows.values()]
    if not models[0] or models[0] != models[1]:
        comparable = False
    report = {"manifest": manifest, "fifo_holdout": baseline, "arms": rows,
              "comparable": comparable, "holdout_delta_exploration_minus_control":
              rows["exploration"]["holdout"]["mean_wait"] - rows["control"]["holdout"]["mean_wait"] if comparable else None,
              "interpretation": "One pair is a pilot, not evidence of general creativity improvement. Negative delta favors exploration. Logged evaluations are a lower bound if protocol is violated."}
    write_json(out / "comparison.json", report)
    return report


def pilot(out: Path, seed: int, budget: int, model: str | None, usd: float, timeout: int):
    if not math.isfinite(usd) or usd <= 0 or timeout <= 0:
        raise ValueError("USD and time limits must be positive and finite")
    if shutil.which("claude") is None:
        raise ValueError("pilot requires a configured Claude Code CLI; demo needs no model")
    manifest = prepare(out, seed, budget)
    manifest["session_limits"] = {"requested_model": model, "usd_per_arm": usd,
                                  "timeout_seconds": timeout}
    manifest["claude_version"] = subprocess.check_output(["claude", "--version"], text=True).strip()
    write_json(out / "manifest.json", manifest)
    order = ["control", "exploration"]
    random.Random(seed).shuffle(order)
    write_json(out / "execution-order.json", order)
    for arm in order:
        command = ["claude", "-p", "Read TASK.md and complete the study task.",
                   "--safe-mode", "--disable-slash-commands", "--output-format", "stream-json", "--verbose",
                   "--tools", "Bash,Read,Write,Edit,Glob,Grep", "--allowedTools", "Bash,Read,Write,Edit,Glob,Grep",
                   "--permission-mode", "dontAsk", "--no-session-persistence", "--max-budget-usd", str(usd)]
        if model:
            command += ["--model", model]
        print(f"Starting {arm}", flush=True)
        started = time.monotonic()
        try:
            run = bounded(command, cwd=out / arm, timeout=timeout,
                          stdout_path=out / f"{arm}-session.jsonl")
            (out / f"{arm}-stderr.log").write_text(run.stderr)
            (out / f"{arm}-session.jsonl").write_text(run.stdout)
            try:
                events = [json.loads(line) for line in run.stdout.splitlines() if line.strip()]
                result = next(e for e in reversed(events) if e.get("type") == "result")
            except (json.JSONDecodeError, StopIteration):
                result = {"is_error": True, "error": run.stdout[-2000:]}
            if run.returncode:
                result["is_error"] = True
        except subprocess.TimeoutExpired:
            result = {"is_error": True, "error": "session timeout"}
        result["wall_seconds"] = time.monotonic() - started
        write_json(out / f"{arm}-session.json", result)
        print(f"Finished {arm}; error={result.get('is_error')}", flush=True)
    print(json.dumps(compare(out), indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "pilot"):
        p = sub.add_parser(name)
        p.add_argument("--out", type=Path, required=True)
        p.add_argument("--seed", type=int, default=0)
        p.add_argument("--eval-budget", type=int, default=12)
        if name == "pilot":
            p.add_argument("--model", help="omit to use the configured Claude model")
            p.add_argument("--usd-per-arm", type=float, default=2.0)
            p.add_argument("--timeout", type=int, default=600)
    p = sub.add_parser("compare")
    p.add_argument("--out", type=Path, required=True)
    sub.add_parser("demo")
    p = sub.add_parser("_grade")
    p.add_argument("--policy", type=Path, required=True)
    p.add_argument("--seeds", required=True)
    args = parser.parse_args()
    if args.command == "_grade":
        print(json.dumps(score(args.policy, json.loads(args.seeds))))
    elif args.command == "demo":
        print(json.dumps(score(HERE / "app/policy.py", list(range(8))), indent=2))
    elif args.command == "prepare":
        print(json.dumps(prepare(args.out.resolve(), args.seed, args.eval_budget), indent=2))
    elif args.command == "compare":
        print(json.dumps(compare(args.out.resolve()), indent=2))
    else:
        pilot(args.out.resolve(), args.seed, args.eval_budget, args.model, args.usd_per_arm, args.timeout)


if __name__ == "__main__":
    main()
