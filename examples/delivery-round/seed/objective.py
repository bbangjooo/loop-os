"""The evaluator: total length of the delivery round. Lower is better.

Prints one number on the last line — that is the whole contract between an
application and the kernel.
"""

import json
from math import dist
from pathlib import Path

cities = json.loads(Path("cities.json").read_text())["cities"]
tour = json.loads(Path("tour.json").read_text())["tour"]

points = [(cities[i]["x"], cities[i]["y"]) for i in tour]
length = sum(dist(points[i], points[(i + 1) % len(points)]) for i in range(len(points)))

print(f"{length:.3f}")
