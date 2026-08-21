"""The evaluator: total length of the delivery round. Prints one number on the
last line — that is the whole contract between an application and the kernel.

The city coordinates live here, integrity-pinned: the agent may reorder the
tour, never move a city.
"""

import json
from math import dist
from pathlib import Path

CITIES = [
    (67.71, 78.49),
    (52.05, 51.15),
    (39.35, 99.68),
    (28.94, 14.83),
    (26.11, 26.04),
    (32.74, 26.79),
    (10.76, 32.55),
    (31.11, 56.92),
    (20.16, 7.08),
    (20.26, 54.24),
    (38.86, 73.35),
    (80.31, 41.44),
]

tour = json.loads(Path("tour.json").read_text())["tour"]
points = [CITIES[i] for i in tour]
length = sum(dist(points[i], points[(i + 1) % len(points)]) for i in range(len(points)))
print(f"{length:.3f}")
