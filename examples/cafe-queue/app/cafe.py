"""Deterministic toy cafe. Times are simulated seconds, not real cafe estimates."""
from __future__ import annotations

import json
import math
import random
import subprocess
import sys
import tempfile
from pathlib import Path

MENU = {
    "espresso": {"family": "coffee", "prep": 1, "brew": 4, "serve": 1},
    "latte": {"family": "coffee", "prep": 2, "brew": 4, "serve": 3},
    "tea": {"family": "tea", "prep": 1, "brew": 3, "serve": 1},
}


class InvalidPlan(ValueError):
    pass


def orders(seed: int, count: int = 12) -> list[dict]:
    rng = random.Random(seed)
    arrival = 0
    result = []
    for i in range(count):
        arrival += rng.choice((0, 0, 1, 2, 4))
        drink = rng.choice(tuple(MENU))
        result.append({"id": i, "arrival": arrival, "drink": drink, **MENU[drink]})
    return result


def validate(jobs: list[dict], plan: list[dict]) -> list[float]:
    """Validate every operation before calculating receipt-to-service times."""
    if not isinstance(plan, list) or len(plan) > 3 * len(jobs):
        raise InvalidPlan("plan must be a list of at most three operations per order")
    by_id = {j["id"]: j for j in jobs}
    steps = {}
    resources = {"barista": [], "machine": []}
    for op in plan:
        if not isinstance(op, dict) or set(op) != {"kind", "orders", "start"}:
            raise InvalidPlan("operation keys must be kind, orders, start")
        kind, ids, start = op["kind"], op["orders"], op["start"]
        if not isinstance(kind, str) or kind not in ("prep", "brew", "serve"):
            raise InvalidPlan("unknown operation kind")
        if type(start) is not int or not 0 <= start <= 100_000:
            raise InvalidPlan("start must be an integer in [0, 100000]")
        capacity = 2 if kind == "brew" else 1
        if not isinstance(ids, list) or not 1 <= len(ids) <= capacity:
            raise InvalidPlan(f"{kind} capacity is {capacity}")
        if any(type(i) is not int or i not in by_id for i in ids) or len(set(ids)) != len(ids):
            raise InvalidPlan("unknown or duplicate order id")
        selected = [by_id[i] for i in ids]
        if kind == "brew" and len({(j["family"], j["brew"]) for j in selected}) != 1:
            raise InvalidPlan("a brew batch needs the same family and duration")
        end = start + selected[0][kind]
        resources["machine" if kind == "brew" else "barista"].append((start, end))
        for i in ids:
            if (i, kind) in steps:
                raise InvalidPlan("an order operation was performed twice")
            steps[i, kind] = (start, end)
    waits = []
    for j in jobs:
        i = j["id"]
        if any((i, k) not in steps for k in ("prep", "brew", "serve")):
            raise InvalidPlan(f"order {i} is missing an operation")
        prep, brew, serve = (steps[i, k] for k in ("prep", "brew", "serve"))
        if prep[0] < j["arrival"] or brew[0] < prep[1] or serve[0] < brew[1]:
            raise InvalidPlan("arrival or operation precedence violated")
        if serve[0] - brew[1] > 12:
            raise InvalidPlan("freshness: serving must start within 12 seconds of brewing")
        waits.append(serve[1] - j["arrival"])
    for resource, spans in resources.items():
        spans.sort()
        if any(b[0] < a[1] for a, b in zip(spans, spans[1:])):
            raise InvalidPlan(f"overlapping operations on {resource}")
    return waits


def score(policy_path: Path, seeds: list[int]) -> dict:
    cases = [orders(seed) for seed in seeds]
    # Only plans cross the process boundary. Candidate code never runs alongside
    # this validator and cannot replace its globals or mutate its input objects.
    worker = """import json, sys, types
payload = json.load(sys.stdin)
module = types.ModuleType('cafe_candidate')
sys.modules[module.__name__] = module
exec(compile(payload['source'], 'policy.py', 'exec'), module.__dict__)
print(json.dumps([module.schedule(jobs) for jobs in payload['cases']]))
"""
    with tempfile.TemporaryDirectory(prefix="cafe-policy-") as directory:
        try:
            result = subprocess.run(
                [sys.executable, "-I", "-c", worker], cwd=directory,
                input=json.dumps({"source": policy_path.read_text(), "cases": cases}),
                text=True, capture_output=True, timeout=10,
            )
        except subprocess.TimeoutExpired as error:
            raise InvalidPlan("policy exceeded 10 seconds") from error
    if result.returncode:
        raise InvalidPlan(f"policy process failed: {result.stderr[-1000:]}")
    try:
        plans = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise InvalidPlan("policy must return plans without printing extra output") from error
    if not isinstance(plans, list) or len(plans) != len(cases):
        raise InvalidPlan("policy must return one plan per day")
    waits = []
    per_day = []
    for seed, jobs, plan in zip(seeds, cases, plans):
        day = validate(jobs, plan)
        waits.extend(day)
        per_day.append({"seed": seed, "mean_wait": sum(day) / len(day)})
    if not waits:
        raise ValueError("at least one scenario is required")
    return {
        "valid": True, "mean_wait": sum(waits) / len(waits),
        "p95_wait": sorted(waits)[math.ceil(0.95 * len(waits)) - 1],
        "max_wait": max(waits), "orders": len(waits), "per_day": per_day,
    }
