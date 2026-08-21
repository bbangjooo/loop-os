"""The guard: the tour must still visit every city exactly once.

Without this, shortening the route by deleting stops would look like progress.
The kernel reverts any iteration that fails this check.
"""

import json
import sys
from pathlib import Path

cities = json.loads(Path("cities.json").read_text())["cities"]
tour = json.loads(Path("tour.json").read_text())["tour"]

if sorted(tour) != list(range(len(cities))):
    print(f"invalid tour: {tour}", file=sys.stderr)
    sys.exit(1)

sys.exit(0)
