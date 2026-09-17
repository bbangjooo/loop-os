"""Pipelined, batching cafe scheduler.

Mechanism: the barista (prep + serve) and the machine (brew) are separate
resources, so preps of later orders belong inside earlier brews.  Compatible
orders (same family and same brew duration) share one brew.  Following the
operating-room analogy, the serve ("closing") interval is reserved on the
barista at the moment a batch is placed, which keeps the 12 second window
feasible by construction; later batches only fill the remaining gaps.

A bounded, deterministic hill climb over batch orderings (swap / move / merge /
split) refines the constructive plan.  Iteration limits are fixed constants.
"""

from bisect import insort

SERVE_WINDOW = 12
MAX_BREW_RETRIES = 40
MAX_SIMS = 8000


def _earliest(busy, t, d):
    """Earliest start >= t with d units free on a resource of busy intervals."""
    cur = t
    for s, e in busy:
        if e <= cur:
            continue
        if s - cur >= d:
            return cur
        if e > cur:
            cur = e
    return cur


def _simulate(batches, info):
    """Place batches in the given order.  Returns (cost, plan) or None."""
    barista = []
    machine = []
    ops = []
    waits = 0
    makespan = 0

    for batch in batches:
        members = [info[i] for i in batch]
        preps = []
        prep_end = 0
        for o in members:
            s = _earliest(barista, o["arrival"], o["prep"])
            insort(barista, (s, s + o["prep"]))
            preps.append((o["id"], s))
            if s + o["prep"] > prep_end:
                prep_end = s + o["prep"]

        brew = members[0]["brew"]
        t = prep_end
        placed = None
        for _ in range(MAX_BREW_RETRIES):
            bs = _earliest(machine, t, brew)
            be = bs + brew
            trial = []
            cur = be
            ok = True
            for o in members:
                ss = _earliest(barista, cur, o["serve"])
                if ss > be + SERVE_WINDOW:
                    ok = False
                    break
                trial.append((o["id"], ss, o["serve"]))
                cur = ss + o["serve"]
            if ok:
                placed = (bs, be, trial)
                break
            t = bs + 1
        if placed is None:
            return None

        bs, be, trial = placed
        insort(machine, (bs, be))
        ops.append({"kind": "brew", "orders": sorted(batch), "start": bs})
        for oid, s in preps:
            ops.append({"kind": "prep", "orders": [oid], "start": s})
        for oid, ss, dur in trial:
            insort(barista, (ss, ss + dur))
            ops.append({"kind": "serve", "orders": [oid], "start": ss})
            waits += ss - info[oid]["arrival"]
            if ss + dur > makespan:
                makespan = ss + dur

    ops.sort(key=lambda op: (op["start"], op["kind"], op["orders"]))
    return (waits, makespan), ops


def _seed_batches(orders, pair):
    ids = [o["id"] for o in sorted(orders, key=lambda o: (o["arrival"], o["id"]))]
    if not pair:
        return [[i] for i in ids]
    info = {o["id"]: o for o in orders}
    batches = []
    used = set()
    for i in ids:
        if i in used:
            continue
        used.add(i)
        mate = None
        for j in ids:
            if j in used:
                continue
            if info[j]["family"] == info[i]["family"] and info[j]["brew"] == info[i]["brew"]:
                mate = j
                break
        if mate is None:
            batches.append([i])
        else:
            used.add(mate)
            batches.append([i, mate])
    return batches


def _neighbours(batches, info):
    n = len(batches)
    for a in range(n):
        for b in range(a + 1, n):
            cand = list(batches)
            cand[a], cand[b] = cand[b], cand[a]
            yield cand
    for a in range(n):
        for b in range(n):
            if a == b:
                continue
            cand = list(batches)
            item = cand.pop(a)
            cand.insert(b, item)
            yield cand
    for a in range(n):
        if len(batches[a]) == 2:
            cand = list(batches)
            x, y = cand[a]
            cand[a] = [x]
            cand.insert(a + 1, [y])
            yield cand
    for a in range(n):
        if len(batches[a]) != 1:
            continue
        for b in range(n):
            if a == b or len(batches[b]) != 1:
                continue
            x, y = batches[a][0], batches[b][0]
            if info[x]["family"] != info[y]["family"] or info[x]["brew"] != info[y]["brew"]:
                continue
            cand = [c for k, c in enumerate(batches) if k != a and k != b]
            cand.insert(min(a, b), [x, y])
            yield cand


def schedule(orders):
    info = {o["id"]: o for o in orders}
    sims = 0
    best = None
    for pair in (True, False):
        start = _seed_batches(orders, pair)
        res = _simulate(start, info)
        sims += 1
        if res is None:
            continue
        if best is None or res[0] < best[0]:
            best = (res[0], start, res[1])

    if best is None:
        # Fall back to the strictly sequential plan, always feasible.
        plan = []
        t = 0
        for o in sorted(orders, key=lambda o: (o["arrival"], o["id"])):
            t = max(t, o["arrival"])
            for kind in ("prep", "brew", "serve"):
                plan.append({"kind": kind, "orders": [o["id"]], "start": t})
                t += o[kind]
        return plan

    def climb(seed, sims):
        res = _simulate(seed, info)
        sims += 1
        if res is None:
            return None, sims
        cost, batches, plan = res[0], seed, res[1]
        improved = True
        while improved and sims < MAX_SIMS:
            improved = False
            for cand in _neighbours(batches, info):
                if sims >= MAX_SIMS:
                    break
                res = _simulate(cand, info)
                sims += 1
                if res is not None and res[0] < cost:
                    cost, batches, plan = res[0], cand, res[1]
                    improved = True
                    break
        return (cost, batches, plan), sims

    overall = best
    for pair in (True, False):
        got, sims = climb(_seed_batches(orders, pair), sims)
        if got is not None and got[0] < overall[0]:
            overall = got

    # Deterministic perturbation restarts: lift one batch to the front, re-climb.
    base = overall[1]
    for k in range(len(base)):
        if sims >= MAX_SIMS:
            break
        seed = [base[k]] + [b for j, b in enumerate(base) if j != k]
        got, sims = climb(seed, sims)
        if got is not None and got[0] < overall[0]:
            overall = got
    return overall[2]
