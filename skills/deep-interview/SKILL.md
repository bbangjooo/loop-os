---
name: loop-os-deep-interview
description: Socratic interview that turns a vague research problem into a durable program.md before Loop OS execution
argument-hint: "[--quick|--standard|--deep] <problem or idea>"

source: "Adapted from GJC deep-interview; see README attribution"
---

# Attribution

Adapted from Gajae Code's `deep-interview` skill. Original copyright:
Copyright (c) 2025-2026 Yeachan-Heo and Gajae Code Contributors. The source is
MIT-licensed; see the Loop OS README for the source revision and attribution.

# Loop OS Program Interview

This is the requirements-only front end for Loop OS. It turns a vague or
exploratory problem into `program.md`, the durable research plan that precedes
`contract.toml`.

## Boundary

The interview may inspect the repository and write `program.md`. It MUST NOT:

- edit product or application code;
- create `contract.toml`;
- bootstrap the journal;
- run the kernel, evaluator, or tests as a mutation path;
- commit, push, open a PR, or hand off to an execution workflow.

The output is a plan, not execution approval. Loop OS converts the plan into a
contract only after the interview has completed.

## When to use

Use this interview for vague, exploratory, or high-cost work: strategy
discovery, ML research, architecture exploration, long refactors, or questions
where choosing the wrong objective would waste a generation.

Do not use it for a clear, bounded, low-risk fix or a direct answer. In that
case, leave no interview artifact and use the normal coding path.

## Core rules

1. Ask **one question at a time**.
2. Ask about assumptions, decisions, constraints, and falsifiers—not feature
   inventory.
3. Read the repository before asking about facts the repository can answer.
4. Keep the user's decisions separate from agent suggestions and repository
   facts.
5. Score ambiguity after every answer; ambiguity may rise when the user
   contradicts an established fact or expands scope.
6. Target the weakest clarity dimension next.
7. Never silently choose an unresolved product or research decision.
8. Stop at the first legitimate terminal condition: sufficient clarity, an
   explicit early exit, cancellation, or the bounded round cap.

## Phase 0: Choose the interview depth

Use the requested mode when supplied:

| Mode | Use | Starting threshold |
|---|---|---:|
| `quick` | bounded problem with a few material choices | 0.60 ambiguity |
| `standard` | normal exploratory work | 0.50 ambiguity |
| `deep` | research direction, new model, strategy discovery, or major architecture | 0.35 ambiguity |

With no mode, choose `standard` unless the problem is clearly research-grade;
then choose `deep`. State the selected mode and threshold before the first
question.

## Phase 1: Establish the topology

Before scoring ambiguity, inspect the request and repository and identify the
independent outcomes. Prefer one to six top-level components. Examples:

- quant research: data surface, signal family, portfolio construction,
  validation;
- ML research: task definition, data, architecture, training procedure,
  evaluation;
- refactoring: target subsystem, behavior preservation, performance, rollout.

Ask one confirmation question:

```text
I am reading this as these top-level outcomes:
1. <component>: <one sentence>
2. <component>: <one sentence>

Which component should be added, removed, merged, split, or explicitly deferred?
```

Do not let the most detailed component hide less-detailed sibling outcomes.
Record confirmed components and deferrals in the working interview context.

## Phase 2: Socratic rounds

Track these dimensions for every active component:

- **Goal** — what outcome is actually wanted?
- **Constraints** — what must remain true, and what is explicitly out of scope?
- **Success criteria** — what deterministic or independently checkable evidence
  would count as success?
- **Context** — what existing code, data, environment, or prior work constrains
  the problem?

Use the weakest dimension of the weakest active component for the next question.
Explain briefly why it is the current bottleneck, then ask exactly one
question.

After each answer:

1. restate the decision or fact in compact form;
2. identify contradictions, unresolved assumptions, or scope expansion;
3. update the dimension scores;
4. show the ambiguity change;
5. record the answer and evidence in the working context;
6. ask the next weakest-dimension question unless a terminal condition holds.

Use these formulas as a guide:

```text
greenfield ambiguity = 1 - (goal*0.40 + constraints*0.30 + criteria*0.30)
brownfield ambiguity = 1 - (goal*0.35 + constraints*0.25 + criteria*0.25 + context*0.15)
```

The score is not a claim of scientific truth. It is a pacing signal that makes
unresolved decisions visible.

### Contradictions and scope changes

Never delete a previous decision when a later answer conflicts with it. Mark it
as superseded or unresolved and ask the user which direction is authoritative.

If the user adds a new component, integration, deliverable, or constraint,
increase ambiguity or return to topology confirmation. Do not treat more scope
as progress.

### Auto-answering

If the user explicitly asks the agent to choose, make the assumption visible,
mark it as agent-supplied, and keep its confidence below user-confirmed facts
unless the user confirms it. Never allow an unconfirmed assumption to silently
become a program invariant.

## Phase 3: Closure

Clarity is sufficient only when:

- every active component has a goal, constraints, and success evidence;
- important assumptions have an owner and a falsifier;
- no material contradiction is unresolved;
- non-goals and deferrals are explicit;
- the proposed research budget and human handoff boundary are understood.

The user may exit early from round 3 onward. Report the remaining ambiguity and
the risk of proceeding; do not pretend the interview completed normally.

Hard cancellation stops immediately and preserves no partial `program.md`.
Use a hard cap of 100 rounds as a safety stop.

Before writing the program, present one sentence:

```text
The program will <goal>, under <important constraints>, and success means <evidence>.
```

Ask the user to confirm or correct that sentence.

## Phase 4: Write `program.md`

Write a human-readable, tracked file at the project root. It must describe the
research direction, not a current execution state.

```markdown
# Program: <title>

## Goal
<the durable outcome>

## Research Question
<what the program is trying to discover, explain, or improve>

## Why This Matters
<motivation and the user's intended payoff>

## Search Space and Interventions
<what the agent may change or manipulate during experiments>

## Success Evidence
<what evidence would justify continuing or declaring success>

## Falsifiers and Failure Signals
<what observations would reject the current direction>

## Constraints
- <must remain true>

## Non-Goals and Deferrals
- <explicitly out of scope>

## Human Decision Boundary
<what still requires the user or an external authority>

## Initial Frame Hints
<candidate mechanisms or frames; these are suggestions, not sealed contracts>
```

Do not put runtime state in this file. In particular, do not add
`current_phase`, `next_action`, `pending_obligation`, or mutable iteration
counters. Runtime state belongs to the Loop OS journal.

After writing the file, report its path and the next action:

```text
Program written to program.md. Review it, then run /loop-os:bootstrap so the
contract builder can derive the first execution frame.
```

The interview ends here. It does not write a contract or start Loop OS.

