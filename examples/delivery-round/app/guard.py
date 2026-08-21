"""The guard: the tour must still visit every city exactly once. Without it,
shortening the route by dropping stops would look like progress."""

import json
import sys
from pathlib import Path

tour = json.loads(Path("tour.json").read_text())["tour"]
sys.exit(0 if sorted(tour) == list(range(12)) else 1)
