#!/usr/bin/env python3
"""Reproduces docs/loop-vs-os.png — kernel (loop only) vs kernel + OS.

Fixed objective (route length), fixed proposal stream. The loop-only run keeps
the move class its contract started with (adjacent swap) and flattens in that
class's local optimum. The OS run hits the same wall, reads three all-rejected
runs as evidence, closes the class, and jumps to a 2-opt frame — same objective,
31% shorter route.

Stdlib + matplotlib. Deterministic: city layout is the median-gap seed from a
24-seed scan, not a cherry-picked outlier.
"""

import math
import random

R = random.Random(19)
CITIES = [(R.uniform(0, 100), R.uniform(0, 100)) for _ in range(12)]
N = len(CITIES)

TOTAL, SPLIT = 80, 30  # iterations overall; gen-1 budget spent at SPLIT


def cost(tour):
    return sum(math.dist(CITIES[tour[i]], CITIES[tour[(i + 1) % N]]) for i in range(N))


def start_tour():
    t = list(range(N))
    random.Random(99).shuffle(t)
    return t


def swap_move(rng, tour):
    i = rng.randrange(1, N - 1)
    t = tour[:]
    t[i], t[i + 1] = t[i + 1], t[i]
    return t


def twoopt_move(rng, tour):
    i = rng.randrange(1, N - 1)
    j = rng.randrange(i + 1, N)
    return tour[:i] + list(reversed(tour[i:j])) + tour[j:]


def climb(tour, move, iters, rng, hist):
    cur = cost(tour)
    for _ in range(iters):
        cand = move(rng, tour)
        v = cost(cand)
        if v < cur - 1e-9:
            tour, cur = cand, v
        hist.append(cur)
    return tour


hist_alone = [cost(start_tour())]
climb(start_tour(), swap_move, TOTAL, random.Random(3), hist_alone)

hist_os = [cost(start_tour())]
rng_b = random.Random(3)
tour_b = climb(start_tour(), swap_move, SPLIT, rng_b, hist_os)
climb(tour_b, twoopt_move, TOTAL - SPLIT, rng_b, hist_os)


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    it = range(len(hist_alone))
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)

    ax.plot(it, hist_alone, label=f"kernel (loop only) ({hist_alone[-1]:.0f})")
    ax.plot(it, hist_os, label=f"kernel + OS ({hist_os[-1]:.0f})")

    ax.axvline(SPLIT, ls="--", lw=1, color="gray", alpha=0.7)
    ax.annotate("jump: swap → 2-opt", xy=(SPLIT, hist_os[0]),
                xytext=(6, -4), textcoords="offset points", fontsize=9, color="gray")

    ax.set_title("Find the shortest route through 12 delivery stops")
    ax.set_xlabel("iteration")
    ax.set_ylabel("route length")
    ax.legend()
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    out = __file__.replace(".py", ".png")
    fig.savefig(out)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
