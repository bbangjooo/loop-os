"""Pipelined cafe policy.

Mechanism: the starting policy serialises prep -> brew -> serve per order, so the
barista idles during every brew and the machine idles during every prep/serve.
Here a deterministic greedy simulator pipelines the two resources (barista preps
the next order while the machine brews), batches two compatible orders into one
brew, and serves as soon as a brew finishes.  The prep priority order is then
improved by a bounded steepest-descent swap search using the true objective
(mean serve-start minus arrival).
"""

SERVE_DEADLINE = 12
MAX_PASSES = 8
TOP_CONFIGS = 4
MAX_SIMS = 1600  # fixed node budget per day (no clock deadline)


def _simulate(orders, seq, pair_wait, feed_machine=False,
              serve_spt=False, gate=2):
    """Greedy run of one prep priority order.  Returns (cost, plan) or None."""
    n = len(orders)
    arrival = [o["arrival"] for o in orders]
    prep = [o["prep"] for o in orders]
    brew = [o["brew"] for o in orders]
    serve = [o["serve"] for o in orders]
    key = [(o["family"], o["brew"]) for o in orders]
    rank = [0] * n
    for pos, i in enumerate(seq):
        rank[i] = pos

    stage = [0] * n            # 0 waiting prep, 1 prepped, 2 brewing, 3 brewed, 4 served
    brew_end = [0] * n
    serve_start = [0] * n
    plan = []

    barista_free = 0
    prep_running = None        # (order, end)
    machine_busy = None        # (orders, end)
    machine_free = 0
    served = 0
    t = min(arrival)

    while served < n:
        if prep_running is not None and prep_running[1] <= t:
            stage[prep_running[0]] = 1
            prep_running = None
        if machine_busy is not None and machine_busy[1] <= t:
            for i in machine_busy[0]:
                stage[i] = 3
                brew_end[i] = machine_busy[1]
            machine_free = machine_busy[1]
            machine_busy = None

        if barista_free <= t and prep_running is None:
            ready = [i for i in range(n) if stage[i] == 3]
            cand = [i for i in range(n) if stage[i] == 0 and arrival[i] <= t]
            if ready and feed_machine and cand and machine_busy is None:
                # Machine starves unless something is prepped; slot a prep in
                # first when every waiting serve still meets its deadline.
                if not any(stage[i] == 1 for i in range(n)):
                    j = min(cand, key=lambda x: (rank[x], x))
                    if all(t + prep[j] - brew_end[i] <= SERVE_DEADLINE for i in ready):
                        ready = []
            if ready:
                if serve_spt:
                    i = min(ready, key=lambda x: (serve[x], brew_end[x], x))
                else:
                    i = min(ready, key=lambda x: (brew_end[x], x))
                if t - brew_end[i] > SERVE_DEADLINE:
                    return None
                serve_start[i] = t
                stage[i] = 4
                served += 1
                barista_free = t + serve[i]
                plan.append({"kind": "serve", "orders": [i], "start": t})
            else:
                if cand:
                    i = min(cand, key=lambda x: (rank[x], x))
                    stage[i] = -1
                    prep_running = (i, t + prep[i])
                    barista_free = t + prep[i]
                    plan.append({"kind": "prep", "orders": [i], "start": t})

        if machine_busy is None and machine_free <= t:
            waiting = [i for i in range(n) if stage[i] == 1]
            pending_serves = sum(1 for i in range(n) if stage[i] == 3)
            if waiting and pending_serves < gate:
                i = min(waiting, key=lambda x: (rank[x], x))
                partners = [j for j in waiting if j != i and key[j] == key[i]]
                start = t
                batch = [i]
                if partners:
                    batch.append(min(partners))
                elif pair_wait and prep_running is not None:
                    j = prep_running[0]
                    if key[j] == key[i] and prep_running[1] <= t + pair_wait:
                        start = prep_running[1]
                        batch = None  # defer: re-enter loop at that time
                if batch is not None:
                    batch.sort()
                    for j in batch:
                        stage[j] = 2
                    end = start + brew[i]
                    machine_busy = (batch, end)
                    plan.append({"kind": "brew", "orders": batch, "start": start})

        # advance time to the next event
        nxt = []
        if prep_running is not None:
            nxt.append(prep_running[1])
        if machine_busy is not None:
            nxt.append(machine_busy[1])
        if barista_free > t:
            nxt.append(barista_free)
        if machine_free > t:
            nxt.append(machine_free)
        for i in range(n):
            if stage[i] == 0 and arrival[i] > t:
                nxt.append(arrival[i])
            elif stage[i] == 3 and brew_end[i] > t:
                nxt.append(brew_end[i])
        nxt = [x for x in nxt if x > t]
        if not nxt:
            if served < n:
                return None
            break
        t = min(nxt)

    for i in range(n):
        if stage[i] != 4 or serve_start[i] - brew_end[i] > SERVE_DEADLINE:
            return None
    cost = sum(serve_start[i] - arrival[i] for i in range(n)) / n
    return cost, plan


def _fallback(orders):
    plan = []
    t = 0
    for order in sorted(orders, key=lambda o: (o["arrival"], o["id"])):
        t = max(t, order["arrival"])
        for kind in ("prep", "brew", "serve"):
            plan.append({"kind": kind, "orders": [order["id"]], "start": t})
            t += order[kind]
    return plan


def schedule(orders):
    orders = sorted(orders, key=lambda o: o["id"])
    ids = [o["id"] for o in orders]
    index = {o["id"]: k for k, o in enumerate(orders)}
    local = [
        {
            "arrival": o["arrival"],
            "prep": o["prep"],
            "brew": o["brew"],
            "serve": o["serve"],
            "family": o["family"],
        }
        for o in orders
    ]
    n = len(local)
    if n == 0:
        return []

    base = list(range(n))
    seeds = [
        sorted(base, key=lambda i: (local[i]["arrival"], i)),
        sorted(base, key=lambda i: (local[i]["family"], local[i]["arrival"], i)),
        sorted(base, key=lambda i: (local[i]["arrival"], local[i]["prep"] + local[i]["serve"], i)),
        sorted(base, key=lambda i: (local[i]["prep"] + local[i]["serve"], local[i]["arrival"], i)),
    ]
    waits = (0, 1, 2, 3)

    budget = [MAX_SIMS]

    def run(seq, cfg):
        if budget[0] <= 0:
            return None
        budget[0] -= 1
        return _simulate(local, seq, cfg[0], cfg[1], cfg[2], cfg[3])

    # Phase 1: screen every dispatch rule combination on each seed order.
    screened = []
    for si, seed in enumerate(seeds):
        for w in waits:
            for f in (False, True):
                for sp in (False, True):
                    for g in (2, 3):
                        cfg = (w, f, sp, g)
                        r = run(seed, cfg)
                        if r is not None:
                            screened.append((r[0], si, cfg, r[1]))
    if not screened:
        return _fallback(orders)
    screened.sort(key=lambda x: (x[0], x[1], x[2]))

    best = (screened[0][0], screened[0][3])
    # Phase 2: steepest-descent swaps on the most promising starts only.
    for cost0, si, cfg, plan0 in screened[:TOP_CONFIGS]:
        if budget[0] <= 0:
            break
        cur = list(seeds[si])
        cur_cost, cur_plan = cost0, plan0
        for _ in range(MAX_PASSES):
            improved = False
            for a in range(n - 1):
                for b in range(a + 1, n):
                    trial = list(cur)
                    trial[a], trial[b] = trial[b], trial[a]
                    r = run(trial, cfg)
                    if r is not None and r[0] < cur_cost - 1e-9:
                        cur, cur_cost, cur_plan = trial, r[0], r[1]
                        improved = True
            if not improved or budget[0] <= 0:
                break
        if cur_cost < best[0] - 1e-9:
            best = (cur_cost, cur_plan)

    if best is None:
        return _fallback(orders)

    out = []
    for op in best[1]:
        out.append({
            "kind": op["kind"],
            "orders": [ids[j] for j in op["orders"]],
            "start": op["start"],
        })
    _ = index
    return out
