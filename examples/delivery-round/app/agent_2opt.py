"""Generation-2 agent: reverse one segment of the tour (a 2-opt move).

The successor frame adopted by the jump. Same deal with the kernel as the
generation-1 agent: propose one change, let the objective decide.
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
j = rng.randrange(i + 1, len(tour))
tour[i:j] = reversed(tour[i:j])

doc["tour"] = tour
path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
print(f"proposed 2-opt: reversed positions {i}..{j - 1}")
