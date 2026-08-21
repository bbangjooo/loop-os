#!/usr/bin/env python3
"""Render the comparison chart from the runs' actual summary.json files.

Requires matplotlib; the example prints a notice and skips the chart without it.
"""

import argparse
import json
from pathlib import Path


def retained_series(summary_paths):
    series = []
    for p in summary_paths:
        s = json.loads(Path(p).read_text())
        for it in s["iterations"]:
            if not series:
                series.append(it["objective_before"])
            series.append(it["objective_after"] if it["decision"] == "accepted" else series[-1])
    return series


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop-only", nargs="+", required=True, help="summary.json of the loop-only run")
    ap.add_argument("--with-os", nargs="+", required=True, help="summary.json files of the OS path, in order")
    ap.add_argument("--jump-at", type=int, required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed — skipping the chart (pip install matplotlib to get it)")
        return

    alone = retained_series(args.loop_only)
    withos = retained_series(args.with_os)

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    ax.plot(range(len(alone)), alone, label=f"kernel (loop only) ({alone[-1]:.0f})")
    ax.plot(range(len(withos)), withos, label=f"kernel + OS ({withos[-1]:.0f})")
    ax.axvline(args.jump_at, ls="--", lw=1, color="gray", alpha=0.7)
    ax.annotate("jump: swap → 2-opt", xy=(args.jump_at, alone[0]),
                xytext=(6, -4), textcoords="offset points", fontsize=9, color="gray")
    ax.set_title("Find the shortest route through 12 delivery stops")
    ax.set_xlabel("iteration")
    ax.set_ylabel("route length")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(args.out)
    print(f"chart -> {args.out}")


if __name__ == "__main__":
    main()
