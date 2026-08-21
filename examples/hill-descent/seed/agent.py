"""A scripted stand-in for the LLM agent: lowers the number by exactly one.

The real thing is a `claude -p {prompt}` command in the contract's [agent] block.
Using a script here keeps the example deterministic and free of API calls — the
kernel cannot tell the difference, which is the point: it never trusts the agent.
"""

from pathlib import Path

p = Path("value.txt")
p.write_text(str(int(p.read_text().strip()) - 1) + "\n", encoding="utf-8")
