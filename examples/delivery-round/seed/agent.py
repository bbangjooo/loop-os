"""A scripted stand-in for the LLM agent: proposes one 2-opt move.

The real thing is a `claude -p {prompt}` command in the contract's [agent] block.
This script keeps the example deterministic and free of API calls, and it is
deliberately *not* an oracle — it picks a segment to reverse at random and has no
idea whether that shortens the round. Roughly half its proposals make the tour
worse, and the kernel throws those away with `git reset --hard`.

That is the whole point of the inner loop: the agent proposes, the objective
measures, and the kernel decides. Nothing here trusts the proposal.

The seed comes from EXPERIMENT_LOOP_ITERATION, which the kernel sets for the agent
process. A rejected iteration is reverted, so without the iteration index the next
attempt would re-propose the same rejected move forever.
"""

import json
import os
import random
from pathlib import Path

path = Path("tour.json")
doc = json.loads(path.read_text())
tour = doc["tour"]

seed = int(os.environ.get("EXPERIMENT_LOOP_ITERATION", "0"))
rng = random.Random(seed)

i = rng.randrange(1, len(tour) - 1)
j = rng.randrange(i + 1, len(tour))
tour[i:j] = reversed(tour[i:j])

doc["tour"] = tour
path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
print(f"proposed 2-opt: reversed positions {i}..{j - 1}")
