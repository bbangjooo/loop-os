"""Generation-1 agent: swap two adjacent stops.

A scripted stand-in for the LLM. Not an oracle — it picks the position at random
and has no idea whether the swap helps; the kernel measures and decides. Seeded
from EXPERIMENT_LOOP_ID / EXPERIMENT_LOOP_ITERATION, set by the kernel.
"""

import json
import os
import random
from pathlib import Path

path = Path("tour.json")
doc = json.loads(path.read_text())
tour = doc["tour"]

seed = f"{os.environ.get('EXPERIMENT_LOOP_ID', '')}:{os.environ.get('EXPERIMENT_LOOP_ITERATION', '0')}"
rng = random.Random(seed)

i = rng.randrange(1, len(tour) - 1)
tour[i], tour[i + 1] = tour[i + 1], tour[i]

doc["tour"] = tour
path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
print(f"proposed swap at positions {i},{i + 1}")
