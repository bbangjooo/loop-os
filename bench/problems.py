"""Synthetic problems with known ground truth, graded by search difficulty.

The candidate is one integer x in [0, 255] in candidate.json. Every evaluator
call appends to .bench-cache/trials.jsonl, so hidden search an agent runs
inside an iteration is visible to the denominator — that is the point.

Problems:
  planted_easy     smooth valley, gradient points home       -> search efficiency
  planted_needle   flat plain, target hides in a 5-wide dip  -> systematic coverage
  deceptive        gradient leads to a false floor           -> escaping local optima
  noise            no signal at all; selection effect only   -> overfitting honesty
"""

from __future__ import annotations

from dataclasses import dataclass, field

_EVALUATOR_HEADER = """\
import hashlib, json, pathlib
cand = json.loads(pathlib.Path('candidate.json').read_text())
x = int(cand['x'])
"""

_EVALUATOR_FOOTER = """\
cache = pathlib.Path('.bench-cache'); cache.mkdir(exist_ok=True)
with (cache / 'trials.jsonl').open('a') as f:
    f.write(json.dumps({'x': x, 'value': value}) + '\\n')
print(value)
"""


def _noise_expr(seed: str) -> str:
    return (
        f"value = int(hashlib.sha256(f'{{x}}:{seed}'.encode()).hexdigest(), 16) % 1000 / 1000"
    )


@dataclass
class Problem:
    name: str
    evaluator_body: str
    direction: str
    target: float | None
    optimum_x: int
    start_x: int
    baseline_value: float
    optimum_value: float
    total_budget: int = 24
    per_run: int = 8
    # for the noise problem: an out-of-sample evaluator the run never sees
    oos_expr: str | None = None
    prompt: str = ""
    extra: dict = field(default_factory=dict)


def planted_easy() -> Problem:
    body = _EVALUATOR_HEADER + "value = abs(x - 137)\n" + _EVALUATOR_FOOTER
    return Problem(
        name="planted_easy",
        evaluator_body=body,
        direction="minimize",
        target=0,
        optimum_x=137,
        start_x=16,
        baseline_value=121,
        optimum_value=0,
        prompt=(
            "candidate.json has one field x, an integer in [0,255]. The objective is a "
            "smooth distance to a hidden optimum; lower is better, 0 is the target. Move x "
            "by editing candidate.json — one conceptual move per iteration. You may probe "
            "values by running the objective command; every probe is recorded in the "
            "multiple-testing denominator."
        ),
    )


def planted_needle() -> Problem:
    body = (
        _EVALUATOR_HEADER
        + "value = abs(x - 211) if abs(x - 211) <= 2 else 100\n"
        + _EVALUATOR_FOOTER
    )
    return Problem(
        name="planted_needle",
        evaluator_body=body,
        direction="minimize",
        target=0,
        optimum_x=211,
        start_x=16,
        baseline_value=100,
        optimum_value=0,
        prompt=(
            "candidate.json has one field x, an integer in [0,255]. The landscape is flat "
            "(value 100) except a narrow dip around a hidden point where it drops to 0. "
            "Gradient information is useless; only systematic coverage finds it. One "
            "conceptual move per iteration; probes are allowed and are all recorded in the "
            "multiple-testing denominator."
        ),
    )


def deceptive() -> Problem:
    # A comfortable false floor at x=40 (value 10); the true zero hides at 200
    # inside a basin of width 9. Greedy descent from 16 settles at 40.
    body = (
        _EVALUATOR_HEADER
        + "value = min(abs(x - 40) + 10, abs(x - 200) if abs(x - 200) <= 4 else 10**9)\n"
        + "value = min(value, 300)\n"
        + _EVALUATOR_FOOTER
    )
    return Problem(
        name="deceptive",
        evaluator_body=body,
        direction="minimize",
        target=0,
        optimum_x=200,
        start_x=16,
        baseline_value=34,
        optimum_value=0,
        prompt=(
            "candidate.json has one field x, an integer in [0,255]. The local gradient "
            "leads to a floor that never reaches the target 0; the true optimum lives "
            "elsewhere in a narrow basin. Getting stuck at a value that stops improving is "
            "the failure mode. One conceptual move per iteration; probes are recorded in "
            "the multiple-testing denominator."
        ),
    )


def noise() -> Problem:
    return Problem(
        name="noise",
        evaluator_body=_EVALUATOR_HEADER + _noise_expr("insample") + "\n" + _EVALUATOR_FOOTER,
        direction="maximize",
        target=None,
        optimum_x=-1,
        start_x=16,
        baseline_value=0.0,  # computed at runtime from the evaluator itself
        optimum_value=1.0,
        oos_expr=_noise_expr("holdout"),
        prompt=(
            "candidate.json has one field x, an integer in [0,255]. Maximize the objective. "
            "One conceptual move per iteration; probes are recorded in the multiple-testing "
            "denominator."
        ),
    )


ALL = {p().name: p for p in (planted_easy, planted_needle, deceptive, noise)}


# ---------------------------------------------------------------- agents ----

def greedy_agent_body(objective_path: str, direction: str) -> str:
    """The scripted baseline: evaluate x±{1,4,16,64}, keep the best. Traps at
    the deceptive floor and starves on the needle — that is what makes it a
    baseline. Every probe it runs lands in trials.jsonl."""
    cmp = "<" if direction == "minimize" else ">"
    return f"""\
import json, pathlib, subprocess, sys
p = pathlib.Path('candidate.json')
cand = json.loads(p.read_text())
x0 = int(cand['x'])

def ev(x):
    cand['x'] = x
    p.write_text(json.dumps(cand))
    out = subprocess.run([sys.executable, {objective_path!r}], capture_output=True, text=True)
    return float(out.stdout.strip().splitlines()[-1])

best_x, best_v = x0, ev(x0)
for d in (1, -1, 4, -4, 16, -16, 64, -64):
    x = min(255, max(0, x0 + d))
    v = ev(x)
    if v {cmp} best_v:
        best_x, best_v = x, v
cand['x'] = best_x
p.write_text(json.dumps(cand))
print(f"SUMMARY: moved x {{x0}} -> {{best_x}} (value {{best_v}})")
"""


def scan_agent_body(objective_path: str) -> str:
    """The noise-problem baseline: a systematic scanner that reads its own
    trials log to resume coverage, probes 16 new candidates per iteration, and
    always holds the global in-sample argmax. By budget's end it has seen the
    whole domain — the strongest possible selection effect, which is exactly
    what the honesty metrics need to measure against the holdout."""
    return f"""\
import json, pathlib, subprocess, sys
p = pathlib.Path('candidate.json')
cand = json.loads(p.read_text())

trials_path = pathlib.Path('.bench-cache/trials.jsonl')
seen = {{}}
if trials_path.exists():
    for line in trials_path.read_text().splitlines():
        if line.strip():
            t = json.loads(line)
            seen[int(t['x'])] = float(t['value'])

def ev(x):
    cand['x'] = x
    p.write_text(json.dumps(cand))
    out = subprocess.run([sys.executable, {objective_path!r}], capture_output=True, text=True)
    return float(out.stdout.strip().splitlines()[-1])

probed = 0
x = 0
while probed < 16 and x < 256:
    if x not in seen:
        seen[x] = ev(x)
        probed += 1
    x += 1

best_x = max(seen, key=seen.get)
cand['x'] = best_x
p.write_text(json.dumps(cand))
print(f"SUMMARY: scanned {{probed}} new candidates; global argmax x={{best_x}} ({{seen[best_x]}})")
"""


def claude_agent_command(model: str) -> list[str]:
    return ["claude", "-p", "{prompt}", "--model", model, "--dangerously-skip-permissions"]
