#!/usr/bin/env python3
"""Author a diagnosis file from a run's summary.json.

In real use the agent writes this after reading the evidence; the example
scripts it so the run is deterministic. The verdict rule is the honest one:
a run that accepted nothing is evidence against the frame's mechanism.
"""

import json
import sys
from pathlib import Path

summary_path, out_path, mechanism = sys.argv[1], sys.argv[2], sys.argv[3]
s = json.loads(Path(summary_path).read_text())

its = s["iterations"]
accepts = sum(1 for i in its if i["decision"] == "accepted")
start = its[0]["objective_before"]
end = next((i["objective_after"] for i in reversed(its) if i["decision"] == "accepted"), start)
n = len(its)

if accepts > 0:
    verdict = "SUPPORTED"
    mech = (f"The mechanism ({mechanism}) still produces accepted moves: "
            f"{accepts} of {n} proposals improved the round and every accepted state kept the guard passing.")
    counter = f"Without the accepted moves the round would still measure {start:.1f}; nothing else writes tour.json."
    nextq = f"Acceptances are thinning — how many more inversions can this move class still fix before it is exhausted?"
else:
    verdict = "REJECTED"
    mech = (f"The mechanism ({mechanism}) produced nothing this run: 0 of {n} proposals improved the round. "
            "The frame's falsifier has fired — the move class is exhausted at this tour, not unlucky.")
    counter = (f"If the class still had inversions to fix, at least one of {n} distinct proposals should have "
               f"been accepted; the round stayed at {start:.1f} for all of them.")
    nextq = "What move class can change what this one cannot — crossings that no adjacent swap removes in one step?"

diag = {
    "verdict": verdict,
    "what_moved": f"objective {start:.1f} -> {end:.1f}; {accepts} of {n} iterations accepted; denominator {n}",
    "mechanism_interpretation": mech,
    "counterfactual": counter,
    "next_question": nextq,
}
Path(out_path).write_text(json.dumps(diag, indent=2) + "\n", encoding="utf-8")
print(f"diagnosis {verdict} -> {out_path}")
