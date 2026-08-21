#!/usr/bin/env python3
"""Render the example's result as one SVG: the round before and after, and the
objective per iteration — including the proposals the kernel threw away.

Stdlib only, so the example stays dependency-free. Colors follow
docs/design-system.md ("Ledger").
"""

import argparse
import json
from pathlib import Path

PAPER = "#f7f5f0"
INK = "#2b2925"
MUTED = "#6b665c"
SOFT = "#8b857b"
RULE = "rgba(43,41,37,0.12)"
ACCENT = "#a63d2f"
MONO = "'Geist Mono', 'SFMono-Regular', Menlo, monospace"


def load(path):
    return json.loads(Path(path).read_text())


def tour_panel(x0, y0, size, cities, tour, stroke, title, value):
    xs = [c["x"] for c in cities]
    ys = [c["y"] for c in cities]
    pad = 16
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    scale = (size - 2 * pad) / span

    def sx(x):
        return x0 + pad + (x - min(xs)) * scale

    def sy(y):
        return y0 + pad + (max(ys) - y) * scale  # flip: SVG y grows downward

    points = " ".join(f"{sx(cities[i]['x']):.1f},{sy(cities[i]['y']):.1f}" for i in tour)
    dots = "".join(
        f'<circle cx="{sx(c["x"]):.1f}" cy="{sy(c["y"]):.1f}" r="2.5" fill="{INK}"/>'
        for c in cities
    )
    return f"""
    <rect x="{x0}" y="{y0}" width="{size}" height="{size}" rx="6" fill="#ffffff" stroke="{RULE}" stroke-width="1"/>
    <polygon points="{points}" fill="none" stroke="{stroke}" stroke-width="1.2"/>
    {dots}
    <text x="{x0}" y="{y0 + size + 20}" fill="{MUTED}" font-size="9" font-family="{MONO}">{title}</text>
    <text x="{x0 + size}" y="{y0 + size + 20}" fill="{stroke}" font-size="9" font-family="{MONO}" text-anchor="end" font-weight="600">{value}</text>"""


def descent_panel(x0, y0, w, h, summary):
    iters = summary["iterations"]
    retained = [iters[0]["objective_before"]]
    proposals = []  # (index, value, accepted)
    for it in iters:
        proposals.append((it["iteration"], it["objective_after"], it["decision"] == "accepted"))
        retained.append(it["objective_after"] if it["decision"] == "accepted" else retained[-1])

    values = [v for _, v, _ in proposals] + retained
    lo, hi = min(values), max(values)
    pad_v = (hi - lo) * 0.08
    lo, hi = lo - pad_v, hi + pad_v
    pad = 16

    def px(i):
        return x0 + pad + i * (w - 2 * pad) / len(iters)

    def py(v):
        return y0 + pad + (hi - v) * (h - 2 * pad) / (hi - lo)

    # Step line of what the tour actually was after each iteration.
    step = f"M {px(0):.1f} {py(retained[0]):.1f}"
    for i in range(1, len(retained)):
        step += f" H {px(i):.1f} V {py(retained[i]):.1f}"

    marks = ""
    for i, v, accepted in proposals:
        if accepted:
            marks += f'<circle cx="{px(i):.1f}" cy="{py(v):.1f}" r="3" fill="{INK}"/>'
        else:
            marks += (
                f'<circle cx="{px(i):.1f}" cy="{py(v):.1f}" r="3" fill="#ffffff" '
                f'stroke="{ACCENT}" stroke-width="1.2"/>'
            )

    first, last = retained[0], retained[-1]
    return f"""
    <rect x="{x0}" y="{y0}" width="{w}" height="{h}" rx="6" fill="#ffffff" stroke="{RULE}" stroke-width="1"/>
    <path d="{step}" fill="none" stroke="{INK}" stroke-width="1.2"/>
    {marks}
    <text x="{x0 + pad}" y="{py(first) - 8:.1f}" fill="{MUTED}" font-size="9" font-family="{MONO}">{first:.0f}</text>
    <text x="{x0 + w - pad}" y="{py(last) - 8:.1f}" fill="{INK}" font-size="9" font-family="{MONO}" text-anchor="end" font-weight="600">{last:.0f}</text>
    <text x="{x0}" y="{y0 + h + 20}" fill="{MUTED}" font-size="9" font-family="{MONO}">objective per iteration</text>
    <circle cx="{x0 + 6}" cy="{y0 + h + 33}" r="3" fill="{INK}"/>
    <text x="{x0 + 14}" y="{y0 + h + 36}" fill="{SOFT}" font-size="9" font-family="{MONO}">kept</text>
    <circle cx="{x0 + 66}" cy="{y0 + h + 33}" r="3" fill="#ffffff" stroke="{ACCENT}" stroke-width="1.2"/>
    <text x="{x0 + 74}" y="{y0 + h + 36}" fill="{SOFT}" font-size="9" font-family="{MONO}">reverted</text>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cities", required=True)
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cities = load(args.cities)["cities"]
    before = load(args.before)["tour"]
    after = load(args.after)["tour"]
    summary = load(args.summary)

    first = summary["iterations"][0]["objective_before"]
    last_kept = first
    for it in summary["iterations"]:
        if it["decision"] == "accepted":
            last_kept = it["objective_after"]

    svg = f"""<svg viewBox="0 0 720 300" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="dr-title dr-desc">
  <title id="dr-title">Delivery round — before and after one Loop OS run</title>
  <desc id="dr-desc">The seed tour crosses itself; after eight iterations of random 2-opt proposals, four accepted and four reverted, the tour is {100 * (first - last_kept) / first:.0f} percent shorter. A step chart shows the objective per iteration with reverted proposals as hollow marks off the line.</desc>
  <rect width="100%" height="100%" fill="{PAPER}"/>
  <text x="24" y="24" fill="{INK}" font-size="10" font-family="{MONO}" letter-spacing="0.06em">the problem: visit all 12 delivery stops in the shortest possible round</text>
  <text x="24" y="38" fill="{SOFT}" font-size="9" font-family="{MONO}">agent proposes a random 2-opt move · kernel keeps only what measures shorter</text>
  {tour_panel(24, 52, 200, cities, before, MUTED, "before", f"{first:.1f}")}
  {tour_panel(256, 52, 200, cities, after, ACCENT, "after", f"{last_kept:.1f}")}
  {descent_panel(488, 52, 208, 200, summary)}
</svg>
"""
    Path(args.out).write_text(svg, encoding="utf-8")
    print(f"chart -> {args.out}")


if __name__ == "__main__":
    main()
